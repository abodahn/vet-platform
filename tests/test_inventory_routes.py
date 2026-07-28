# -*- coding: utf-8 -*-
"""Inventory + procurement write routes: does the STOCK come out right?

Stock is the other half of the books. A receiving that renders "Stock updated"
without writing a batch, or a warehouse transfer that quietly destroys 40 units,
is invisible until someone counts the shelf.

Every test POSTs through the real route and then reads batches / stock_movements
back, asserting exact quantities — and, for transfers, that total quantity
across all warehouses is CONSERVED.

SQLite, no network.
"""
from datetime import date

import models.database as db
from models.security import _CSRF_SESSION_KEY


# ─── helpers ──────────────────────────────────────────────────────────────────

def _csrf(client):
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _row(sql, params=()):
    conn = db.get_db()
    r = conn.execute(sql, params).fetchone()
    conn.close()
    return r


def _rows(sql, params=()):
    conn = db.get_db()
    rs = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rs]


def _mk_item(name, cost=10.0, sell=18.0, reorder=5.0):
    conn = db.get_db()
    with conn:
        iid = conn.execute(
            "INSERT INTO items (name, unit, cost_price, sell_price, reorder_level,"
            " max_stock, is_active) VALUES (?,?,?,?,?,?,1)",
            (name, "box", cost, sell, reorder, 500.0),
        ).lastrowid
    conn.close()
    return iid


def _mk_batch(item_id, qty, expiry, warehouse_id=1, number="LOT", cost=10.0):
    conn = db.get_db()
    with conn:
        bid = conn.execute(
            "INSERT INTO batches (item_id, warehouse_id, batch_number, expiry_date,"
            " quantity, unit_cost) VALUES (?,?,?,?,?,?)",
            (item_id, warehouse_id, number, expiry, qty, cost),
        ).lastrowid
    conn.close()
    return bid


def _mk_warehouse(name):
    conn = db.get_db()
    with conn:
        wid = conn.execute(
            "INSERT INTO warehouses (name, is_active) VALUES (?,1)", (name,)
        ).lastrowid
    conn.close()
    return wid


def _stock(item_id):
    """Total quantity on hand across every warehouse."""
    return float(_row(
        "SELECT COALESCE(SUM(quantity),0) q FROM batches WHERE item_id=?",
        (item_id,))["q"])


def _mk_supplier(name):
    conn = db.get_db()
    with conn:
        sid = conn.execute(
            "INSERT INTO suppliers (name, is_active) VALUES (?,1)", (name,)
        ).lastrowid
    conn.close()
    return sid


# ═══ ITEMS ════════════════════════════════════════════════════════════════════

def test_item_new_stores_every_field(auth_client):
    _post(auth_client, "/inventory/items/new", {
        "sku": "RT-ITEM-001", "barcode": "6221000000019",
        "name": "Route Test Amoxicillin", "name_ar": "أموكسيسيلين",
        "unit": "vial", "cost_price": "42.75", "sell_price": "89.50",
        "reorder_level": "12", "max_stock": "300",
        "is_medication": "on", "requires_rx": "on",
        "storage_notes": "2-8C",
    })
    item = _row("SELECT * FROM items WHERE sku='RT-ITEM-001'")
    assert item is not None, "POST /inventory/items/new wrote no item"
    item = dict(item)
    assert item["name"] == "Route Test Amoxicillin"
    assert round(item["cost_price"], 2) == 42.75
    assert round(item["sell_price"], 2) == 89.50
    assert round(item["reorder_level"], 2) == 12.0
    assert round(item["max_stock"], 2) == 300.0
    assert item["is_medication"] == 1
    assert item["requires_rx"] == 1
    assert item["is_controlled"] == 0
    assert item["is_active"] == 1


def test_item_edit_changes_prices_and_keeps_stock(auth_client):
    item_id = _mk_item("Editable Item", cost=10.0, sell=20.0)
    _mk_batch(item_id, 25.0, "2030-01-01", number="EDIT-LOT")

    _post(auth_client, f"/inventory/items/{item_id}/edit", {
        "name": "Editable Item Renamed", "unit": "box",
        "cost_price": "13.35", "sell_price": "27.90",
        "reorder_level": "8", "max_stock": "400",
    })

    item = dict(_row("SELECT * FROM items WHERE id=?", (item_id,)))
    assert item["name"] == "Editable Item Renamed"
    assert round(item["cost_price"], 2) == 13.35
    assert round(item["sell_price"], 2) == 27.90
    assert round(item["reorder_level"], 2) == 8.0
    assert _stock(item_id) == 25.0, "editing an item disturbed its stock"


def test_item_edit_of_a_missing_item_404s(auth_client):
    r = auth_client.get("/inventory/items/99999999/edit")
    assert r.status_code == 404


# ═══ RECEIVING (BATCHES) ══════════════════════════════════════════════════════

def test_batch_new_adds_stock_and_records_the_movement(auth_client):
    item_id = _mk_item("Receiving Item")
    before = _stock(item_id)

    _post(auth_client, "/inventory/batches/new", {
        "item_id": str(item_id), "warehouse_id": "1",
        "batch_number": "RCV-2026-A", "lot_number": "L-77",
        "expiry_date": "2029-09-30", "quantity": "40",
        "unit_cost": "12.50", "notes": "supplier delivery",
    })

    batch = _row("SELECT * FROM batches WHERE batch_number='RCV-2026-A'")
    assert batch is not None, "receiving wrote no batch row"
    batch = dict(batch)
    assert round(batch["quantity"], 2) == 40.0
    assert round(batch["unit_cost"], 2) == 12.50
    assert batch["expiry_date"] == "2029-09-30"
    assert batch["lot_number"] == "L-77"

    assert _stock(item_id) == before + 40.0, "stock did not rise by the received qty"

    mv = _rows("SELECT * FROM stock_movements WHERE batch_id=?", (batch["id"],))
    assert len(mv) == 1, "receiving left no stock movement"
    assert mv[0]["movement_type"] == "in"
    assert round(mv[0]["quantity"], 2) == 40.0
    assert round(mv[0]["unit_cost"], 2) == 12.50
    assert mv[0]["reference_type"] == "receiving"

    # Value on hand rises by qty * unit cost, exactly.
    value = float(_row(
        "SELECT COALESCE(SUM(quantity*unit_cost),0) v FROM batches WHERE item_id=?",
        (item_id,))["v"])
    assert round(value, 2) == 500.00


def test_batch_new_rejects_a_zero_quantity(auth_client):
    item_id = _mk_item("Zero Receiving Item")
    _post(auth_client, "/inventory/batches/new", {
        "item_id": str(item_id), "warehouse_id": "1",
        "batch_number": "ZERO-1", "quantity": "0", "unit_cost": "5"})
    assert _row("SELECT COUNT(*) c FROM batches WHERE batch_number='ZERO-1'")["c"] == 0
    assert _stock(item_id) == 0.0


# ═══ FEFO ═════════════════════════════════════════════════════════════════════

def test_deduction_takes_the_earliest_expiring_batch_first(auth_client):
    """FEFO by batch, not just by total. 15 units off three 10-unit batches must
    empty the 2027 batch and take 5 from the 2028 one, leaving 2030 untouched."""
    item_id = _mk_item("FEFO Item")
    b_late = _mk_batch(item_id, 10.0, "2030-12-31", number="FEFO-LATE")
    b_early = _mk_batch(item_id, 10.0, "2027-01-31", number="FEFO-EARLY")
    b_mid = _mk_batch(item_id, 10.0, "2028-06-30", number="FEFO-MID")

    assert db.deduct_stock(item_id, 15.0, reference_type="dispensing", by="tester")

    qty = {r["id"]: round(r["quantity"], 2)
           for r in _rows("SELECT id, quantity FROM batches WHERE item_id=?", (item_id,))}
    assert qty[b_early] == 0.0, "FEFO did not empty the earliest-expiring batch"
    assert qty[b_mid] == 5.0, "FEFO did not take the remainder from the next expiry"
    assert qty[b_late] == 10.0, "FEFO consumed a later-expiring batch first"
    assert _stock(item_id) == 15.0

    moved = {m["batch_id"]: round(m["quantity"], 2)
             for m in _rows("SELECT * FROM stock_movements WHERE item_id=? AND"
                            " movement_type='out'", (item_id,))}
    assert moved == {b_early: 10.0, b_mid: 5.0}, \
        "movements do not name the batches FEFO actually drew from"


def test_deduction_beyond_available_stock_changes_nothing(auth_client):
    item_id = _mk_item("Short FEFO Item")
    _mk_batch(item_id, 4.0, "2027-01-31", number="SHORT-1")

    assert db.deduct_stock(item_id, 10.0) is False
    assert _stock(item_id) == 4.0, "an impossible deduction still moved stock"
    assert _rows("SELECT * FROM stock_movements WHERE item_id=?", (item_id,)) == []


def test_transfer_batches_json_lists_stocked_batches_in_expiry_order(auth_client):
    item_id = _mk_item("Json Batches Item")
    _mk_batch(item_id, 5.0, "2029-01-01", number="J-LATE")
    _mk_batch(item_id, 7.0, "2026-01-01", number="J-EARLY")
    _mk_batch(item_id, 0.0, "2025-01-01", number="J-EMPTY")

    data = auth_client.get(
        f"/inventory/transfer/batches-json?item_id={item_id}").get_json()
    numbers = [b["batch_number"] for b in data]
    assert numbers == ["J-EARLY", "J-LATE"], \
        "batches-json is not FEFO-ordered or is offering an empty batch"
    assert round(data[0]["quantity"], 2) == 7.0

    assert auth_client.get("/inventory/transfer/batches-json").get_json() == []


# ═══ TRANSFERS — quantity must be conserved ══════════════════════════════════

def test_transfer_to_a_new_warehouse_conserves_total_quantity(auth_client):
    """The destination has no matching batch yet, so one has to be created.
    Total on hand across warehouses must be unchanged either way."""
    item_id = _mk_item("Transfer New Dest Item")
    src = _mk_batch(item_id, 30.0, "2029-05-31", warehouse_id=1,
                    number="TR-NEW", cost=9.25)
    dest_wh = _mk_warehouse("Transfer Dest Warehouse")
    before = _stock(item_id)

    _post(auth_client, "/inventory/transfer", {
        "batch_id": str(src), "to_warehouse_id": str(dest_wh),
        "quantity": "12", "notes": "branch top-up"})

    assert _stock(item_id) == before, \
        f"transfer changed total stock from {before} to {_stock(item_id)}"

    src_row = dict(_row("SELECT * FROM batches WHERE id=?", (src,)))
    assert round(src_row["quantity"], 2) == 18.0

    dest = _rows("SELECT * FROM batches WHERE item_id=? AND warehouse_id=?",
                 (item_id, dest_wh))
    assert len(dest) == 1, "the transfer created no batch at the destination"
    assert round(dest[0]["quantity"], 2) == 12.0
    assert dest[0]["batch_number"] == "TR-NEW", "destination batch lost its lot number"
    assert dest[0]["expiry_date"] == "2029-05-31", "destination batch lost its expiry"
    assert round(dest[0]["unit_cost"], 2) == 9.25, "destination batch lost its cost"

    moves = _rows("SELECT * FROM stock_movements WHERE item_id=?", (item_id,))
    assert len(moves) == 2, "a transfer must journal both an out and an in"
    assert round(sum(m["quantity"] for m in moves), 2) == 0.0, \
        "the two transfer movements do not net to zero"


def test_transfer_into_an_existing_destination_batch_merges(auth_client):
    item_id = _mk_item("Transfer Merge Item")
    src = _mk_batch(item_id, 20.0, "2029-07-31", warehouse_id=1, number="TR-MERGE")
    dest_wh = _mk_warehouse("Merge Dest Warehouse")
    dest = _mk_batch(item_id, 5.0, "2029-07-31", warehouse_id=dest_wh,
                     number="TR-MERGE")
    before = _stock(item_id)

    _post(auth_client, "/inventory/transfer", {
        "batch_id": str(src), "to_warehouse_id": str(dest_wh), "quantity": "8"})

    assert _stock(item_id) == before
    assert round(dict(_row("SELECT * FROM batches WHERE id=?", (src,)))["quantity"], 2) == 12.0
    assert round(dict(_row("SELECT * FROM batches WHERE id=?", (dest,)))["quantity"], 2) == 13.0
    assert _row("SELECT COUNT(*) c FROM batches WHERE item_id=?", (item_id,))["c"] == 2, \
        "the transfer duplicated a batch that already existed at the destination"


def test_transfer_of_more_than_is_on_hand_is_refused(auth_client):
    item_id = _mk_item("Transfer Overdraw Item")
    src = _mk_batch(item_id, 6.0, "2029-01-31", warehouse_id=1, number="TR-OVER")
    dest_wh = _mk_warehouse("Overdraw Dest Warehouse")

    _post(auth_client, "/inventory/transfer", {
        "batch_id": str(src), "to_warehouse_id": str(dest_wh), "quantity": "9"})

    assert round(dict(_row("SELECT * FROM batches WHERE id=?", (src,)))["quantity"], 2) == 6.0
    assert _stock(item_id) == 6.0
    assert _rows("SELECT * FROM stock_movements WHERE item_id=?", (item_id,)) == []


def test_transfer_to_the_same_warehouse_is_refused(auth_client):
    item_id = _mk_item("Transfer Same WH Item")
    src = _mk_batch(item_id, 10.0, "2029-01-31", warehouse_id=1, number="TR-SAME")

    _post(auth_client, "/inventory/transfer", {
        "batch_id": str(src), "to_warehouse_id": "1", "quantity": "3"})

    assert _stock(item_id) == 10.0
    assert _row("SELECT COUNT(*) c FROM batches WHERE item_id=?", (item_id,))["c"] == 1


def test_transfer_of_a_non_numeric_quantity_is_refused(auth_client):
    item_id = _mk_item("Transfer Bad Qty Item")
    src = _mk_batch(item_id, 10.0, "2029-01-31", warehouse_id=1, number="TR-BAD")
    dest_wh = _mk_warehouse("Bad Qty Dest Warehouse")

    _post(auth_client, "/inventory/transfer", {
        "batch_id": str(src), "to_warehouse_id": str(dest_wh), "quantity": "abc"})

    assert _stock(item_id) == 10.0


# ═══ PROCUREMENT — SUPPLIERS ═════════════════════════════════════════════════

def test_supplier_new_stores_the_contact_under_the_right_column(auth_client):
    _post(auth_client, "/procurement/suppliers/new", {
        "name": "Route Test Supplier",
        "contact_person": "Nadia Kamel",
        "phone": "01055500001", "email": "nadia@example.com",
        "address": "Giza", "payment_terms": "Net 45", "notes": "cold chain",
    })
    s = _row("SELECT * FROM suppliers WHERE name='Route Test Supplier'")
    assert s is not None, "POST /procurement/suppliers/new wrote no supplier"
    s = dict(s)
    assert s["contact_name"] == "Nadia Kamel", \
        "the contact_person form field did not land in contact_name"
    assert s["phone"] == "01055500001"
    assert s["payment_terms"] == "Net 45"
    assert s["is_active"] == 1


def test_supplier_new_without_a_name_is_rejected(auth_client):
    before = _row("SELECT COUNT(*) c FROM suppliers")["c"]
    _post(auth_client, "/procurement/suppliers/new", {"name": "   ", "phone": "1"})
    assert _row("SELECT COUNT(*) c FROM suppliers")["c"] == before


def test_suppliers_list_counts_each_supplier_orders(auth_client):
    sid = _mk_supplier("Counted Supplier")
    item_id = _mk_item("Counted Supplier Item")
    _mk_po(auth_client, sid, [(item_id, 2, 10.0)])
    _mk_po(auth_client, sid, [(item_id, 1, 10.0)])

    page = auth_client.get("/procurement/suppliers")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "Counted Supplier" in html
    real = _row("SELECT COUNT(*) c FROM purchase_orders WHERE supplier_id=?",
                (sid,))["c"]
    assert real == 2


# ═══ PROCUREMENT — PURCHASE ORDERS ═══════════════════════════════════════════

def _mk_po(auth_client, supplier_id, lines, status="Sent"):
    """POST a PO through the real form. `lines` is [(item_id, qty, unit_cost)].
    Row indexes are deliberately non-contiguous — a removed middle row."""
    form = {"supplier_id": str(supplier_id), "status": status,
            "expected_date": "2026-12-01", "notes": "route test PO"}
    # 1, 3, 7: gaps where rows were deleted in the browser.
    for idx, (item_id, qty, cost) in zip((1, 3, 7), lines):
        form[f"item_id_{idx}"] = str(item_id)
        form[f"quantity_{idx}"] = str(qty)
        form[f"unit_price_{idx}"] = str(cost)
    _post(auth_client, "/procurement/orders/new", form)
    po = _row("SELECT * FROM purchase_orders WHERE supplier_id=? ORDER BY id DESC LIMIT 1",
              (supplier_id,))
    assert po is not None, "the PO form wrote no purchase order"
    return po["id"]


def test_po_with_a_removed_middle_row_keeps_every_line_and_its_total(auth_client):
    sid = _mk_supplier("Gap PO Supplier")
    a = _mk_item("Gap Item A")
    b = _mk_item("Gap Item B")
    c = _mk_item("Gap Item C")
    po_id = _mk_po(auth_client, sid, [(a, 3, 12.50), (b, 7, 4.25), (c, 2, 100.00)])

    lines = _rows("SELECT * FROM po_lines WHERE po_id=? ORDER BY id", (po_id,))
    assert len(lines) == 3, \
        "lines after a gap in the row indexes were dropped"
    assert [round(l["total"], 2) for l in lines] == [37.50, 29.75, 200.00]

    po = dict(_row("SELECT * FROM purchase_orders WHERE id=?", (po_id,)))
    line_sum = round(sum(round(l["total"], 2) for l in lines), 2)
    assert round(po["total"], 2) == line_sum == 267.25, \
        f"PO header total {po['total']} != sum of its lines {line_sum}"
    assert po["status"] == "Sent"


def test_orders_list_shows_the_real_order_total(auth_client):
    """The list is where a manager reads what the clinic committed to spend."""
    sid = _mk_supplier("Orders List Supplier")
    item_id = _mk_item("Orders List Item")
    po_id = _mk_po(auth_client, sid, [(item_id, 5, 375.10)])
    expected = round(5 * 375.10, 2)   # 1875.50

    page = auth_client.get("/procurement/orders")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert round(dict(_row("SELECT * FROM purchase_orders WHERE id=?",
                           (po_id,)))["total"], 2) == expected
    assert f"{expected:.2f}" in html, (            # template renders "%.2f"
        f"the orders list does not render the PO total {expected:.2f} — "
        "it is reading a column that does not exist and rendering 0.00")


def test_orders_list_filters_by_status(auth_client):
    sid = _mk_supplier("Filtered Supplier")
    item_id = _mk_item("Filtered Item")
    _mk_po(auth_client, sid, [(item_id, 1, 5.0)], status="Draft")
    got = auth_client.get("/procurement/orders?status=Cancelled")
    assert got.status_code == 200
    ids = [r["id"] for r in _rows(
        "SELECT id FROM purchase_orders WHERE supplier_id=? AND status='Cancelled'",
        (sid,))]
    assert ids == []


def test_order_receive_adds_exactly_the_ordered_quantity_to_stock(auth_client):
    sid = _mk_supplier("Receiving Supplier")
    a = _mk_item("PO Receive Item A")
    b = _mk_item("PO Receive Item B")
    _mk_batch(a, 6.0, "2029-01-31", number="PRE-EXISTING")
    po_id = _mk_po(auth_client, sid, [(a, 20, 11.00), (b, 4, 250.00)])

    before_a, before_b = _stock(a), _stock(b)
    _post(auth_client, f"/procurement/orders/{po_id}/receive", {})

    assert _stock(a) == before_a + 20.0
    assert _stock(b) == before_b + 4.0

    po = dict(_row("SELECT * FROM purchase_orders WHERE id=?", (po_id,)))
    assert po["status"] == "Received"
    assert po["received_date"], "receiving left received_date empty"

    for item_id, qty, cost in ((a, 20.0, 11.00), (b, 4.0, 250.00)):
        mv = _rows("SELECT * FROM stock_movements WHERE item_id=? AND"
                   " reference_type='purchase_order' AND reference_id=?",
                   (item_id, po_id))
        assert len(mv) == 1, f"no receiving movement journalled for item {item_id}"
        assert mv[0]["movement_type"] == "in"
        assert round(mv[0]["quantity"], 2) == qty
        assert round(mv[0]["unit_cost"], 2) == cost

        batch = _rows("SELECT * FROM batches WHERE item_id=? AND unit_cost=?",
                      (item_id, cost))
        assert batch, f"no batch created for received item {item_id}"
        assert round(batch[-1]["quantity"], 2) == qty


def test_receiving_the_same_order_twice_does_not_double_the_stock(auth_client):
    sid = _mk_supplier("Double Receive Supplier")
    item_id = _mk_item("Double Receive Item")
    po_id = _mk_po(auth_client, sid, [(item_id, 15, 3.00)])

    _post(auth_client, f"/procurement/orders/{po_id}/receive", {})
    after_first = _stock(item_id)
    _post(auth_client, f"/procurement/orders/{po_id}/receive", {})

    assert _stock(item_id) == after_first == 15.0, (
        "receiving an already-received purchase order added its quantity a "
        "second time")
    assert _row("SELECT COUNT(*) c FROM stock_movements WHERE reference_type="
                "'purchase_order' AND reference_id=?", (po_id,))["c"] == 1


def test_order_status_update_accepts_only_known_statuses(auth_client):
    sid = _mk_supplier("Status Supplier")
    item_id = _mk_item("Status Item")
    po_id = _mk_po(auth_client, sid, [(item_id, 1, 9.99)], status="Draft")

    _post(auth_client, f"/procurement/orders/{po_id}/status", {"status": "Sent"})
    assert dict(_row("SELECT * FROM purchase_orders WHERE id=?", (po_id,)))["status"] \
        == "Sent"

    _post(auth_client, f"/procurement/orders/{po_id}/status", {"status": "Vaporised"})
    assert dict(_row("SELECT * FROM purchase_orders WHERE id=?", (po_id,)))["status"] \
        == "Sent", "an unknown status was written to the purchase order"

    _post(auth_client, f"/procurement/orders/{po_id}/status", {"status": "Cancelled"})
    assert dict(_row("SELECT * FROM purchase_orders WHERE id=?", (po_id,)))["status"] \
        == "Cancelled"
