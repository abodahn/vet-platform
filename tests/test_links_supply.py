"""Supply-spine links: inventory <-> procurement.

The gap these cover: /inventory/alerts told a clinic what was running out and
offered no way to order it, and a stock movement showed "visit #1180" as dead
text instead of a link to the visit that consumed the stock.

Every assertion here uses a NON-EMPTY list. The alerts page returned a 500 for
any non-empty low-stock list while a 173-route smoke sweep called it clean,
because the smoke database had no low-stock items — so these tests seed the rows
first and then load the page.
"""
import re

import models.database as db
from models.security import _CSRF_SESSION_KEY


def _hrefs(html):
    return set(re.findall(r'href="([^"]+)"', html))


def _csrf(auth_client):
    auth_client.get("/")  # context_processor mints the token
    with auth_client.session_transaction() as sess:
        return sess.get(_CSRF_SESSION_KEY, "")


def _mk_short_item(name="Linkable Short Item", stock=2.0, reorder=40.0, max_stock=480.0):
    """An item below its reorder level, with a supplier and a stocked batch."""
    conn = db.get_db()
    with conn:
        supplier_id = conn.execute(
            "INSERT INTO suppliers (name, contact_name, phone, is_active)"
            " VALUES (?,?,?,1)",
            (f"{name} Supplier", "Mona Fahmy", "01000000001"),
        ).lastrowid
        item_id = conn.execute(
            "INSERT INTO items (name, unit, cost_price, sell_price, reorder_level,"
            " max_stock, supplier_id, is_active) VALUES (?,?,?,?,?,?,?,1)",
            (name, "box", 12.5, 20.0, reorder, max_stock, supplier_id),
        ).lastrowid
        batch_id = conn.execute(
            "INSERT INTO batches (item_id, warehouse_id, batch_number, expiry_date,"
            " quantity, unit_cost) VALUES (?,1,?,?,?,?)",
            (item_id, "LOT-LINK-1", "2027-01-31", stock, 12.5),
        ).lastrowid
    conn.close()
    return supplier_id, item_id, batch_id


def _mk_movement(item_id, reference_type, reference_id, notes):
    conn = db.get_db()
    with conn:
        mid = conn.execute(
            "INSERT INTO stock_movements (item_id, warehouse_id, movement_type,"
            " quantity, reference_type, reference_id, notes, created_by)"
            " VALUES (?,1,'out',1,?,?,?,'tester')",
            (item_id, reference_type, reference_id, notes),
        ).lastrowid
    conn.close()
    return mid


def _mk_visit():
    conn = db.get_db()
    with conn:
        owner_id = conn.execute(
            "INSERT INTO owners (full_name, phone) VALUES (?,?)",
            ("Supply Link Owner", "01000000002"),
        ).lastrowid
        pet_id = conn.execute(
            "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
            (owner_id, "Supplycat", "Cat"),
        ).lastrowid
        visit_id = conn.execute(
            "INSERT INTO visits (owner_id, pet_id, visit_date, visit_type)"
            " VALUES (?,?,?,?)",
            (owner_id, pet_id, "2026-03-05", "Consultation"),
        ).lastrowid
    conn.close()
    return visit_id


# ── the headline gap: low stock -> purchase order ────────────────────────────

def test_alerts_with_low_stock_offers_a_resolvable_order_route(auth_client):
    _, item_id, _ = _mk_short_item("Alerts Order Route Item")

    page = auth_client.get("/inventory/alerts")
    assert page.status_code == 200, "alerts 500s on a non-empty low-stock list"
    html = page.get_data(as_text=True)

    assert "Alerts Order Route Item" in html, "seeded short item not listed"
    assert "No low stock items" not in html, "low-stock list rendered as empty"

    order_links = [h for h in _hrefs(html)
                   if "/procurement/orders/new" in h and f"item_id={item_id}" in h]
    assert order_links, "alerts page offers no way to order the item that is short"

    # A rendered link is not a resolving one.
    for href in order_links:
        form = auth_client.get(href.replace("&amp;", "&"))
        assert form.status_code == 200, f"{href} does not resolve"
        assert f'value="{item_id}" selected' in form.get_data(as_text=True), (
            "PO form did not pre-select the item that was short")


def test_order_form_prefills_quantity_and_supplier(auth_client):
    supplier_id, item_id, _ = _mk_short_item(
        "Prefill Item", stock=2.0, reorder=40.0, max_stock=480.0)

    form = auth_client.get(
        f"/procurement/orders/new?item_id={item_id}&qty=478&supplier_id={supplier_id}")
    assert form.status_code == 200
    html = form.get_data(as_text=True)

    assert f'value="{item_id}" selected' in html
    assert f'value="{supplier_id}" selected' in html
    assert re.search(r'id="qty_1"[^>]*value="478(\.0)?"', html), "quantity not pre-filled"
    assert re.search(r'id="price_1"[^>]*value="12\.50"', html), "unit cost not pre-filled"


def test_order_form_prefills_every_short_item_at_once(auth_client):
    _, a, _ = _mk_short_item("Bulk Order A")
    _, b, _ = _mk_short_item("Bulk Order B")

    form = auth_client.get(
        f"/procurement/orders/new?item_id={a}&item_id={b}&qty=10&qty=20")
    assert form.status_code == 200
    html = form.get_data(as_text=True)
    assert len(re.findall(r'<tr id="line_\d+"', html)) == 2
    assert re.search(r'id="qty_1"[^>]*value="10(\.0)?"', html)
    assert re.search(r'id="qty_2"[^>]*value="20(\.0)?"', html)


def test_order_form_ignores_a_mismatched_qty_list(auth_client):
    """qty is positional; a short or unparseable list must not shift onto the
    wrong item."""
    _, a, _ = _mk_short_item("Mismatch Qty A")
    _, b, _ = _mk_short_item("Mismatch Qty B")

    form = auth_client.get(
        f"/procurement/orders/new?item_id={a}&item_id={b}&qty=nonsense&qty=20")
    assert form.status_code == 200
    html = form.get_data(as_text=True)
    assert len(re.findall(r'<tr id="line_\d+"', html)) == 2
    # Neither line may claim 20 — that quantity belonged to whichever item the
    # dropped value would have shifted it off.
    assert not re.search(r'id="qty_1"[^>]*value="20(\.0)?"', html)


def test_order_form_drops_unknown_item_ids(auth_client):
    """A stale link must not render a line bound to an item that is gone."""
    form = auth_client.get("/procurement/orders/new?item_id=99999999&qty=5")
    assert form.status_code == 200
    html = form.get_data(as_text=True)
    assert len(re.findall(r'<tr id="line_\d+"', html)) == 1, "phantom line rendered"
    assert 'value="99999999"' not in html


def test_prefilled_form_submits_into_a_real_purchase_order(auth_client):
    """The pre-fill is only useful if the form it produces actually posts."""
    supplier_id, item_id, _ = _mk_short_item("Submit Prefill Item")

    resp = auth_client.post(
        "/procurement/orders/new",
        data={"_csrf_token": _csrf(auth_client), "supplier_id": str(supplier_id),
              "status": "Draft", "item_id_1": str(item_id),
              "quantity_1": "478", "unit_price_1": "12.50"},
        follow_redirects=True)
    assert resp.status_code == 200

    conn = db.get_db()
    line = conn.execute(
        "SELECT po_id, quantity FROM po_lines WHERE item_id=?", (item_id,)).fetchone()
    conn.close()
    assert line is not None, "prefilled PO form did not create a line"
    assert float(line["quantity"]) == 478.0

    detail = auth_client.get(f"/procurement/orders/{line['po_id']}")
    assert detail.status_code == 200
    assert f"/inventory/items/{item_id}" in _hrefs(detail.get_data(as_text=True)), (
        "PO detail does not link its line back to the item it replenishes")


def test_order_submit_keeps_lines_after_a_removed_row(auth_client):
    """Removing a middle row leaves a gap in the field indexes."""
    supplier_id, a, _ = _mk_short_item("Gap Line A")
    _, b, _ = _mk_short_item("Gap Line B")

    auth_client.post(
        "/procurement/orders/new",
        data={"_csrf_token": _csrf(auth_client), "supplier_id": str(supplier_id),
              "status": "Draft",
              "item_id_1": str(a), "quantity_1": "3", "unit_price_1": "1",
              # no _2 — that row was removed in the browser
              "item_id_3": str(b), "quantity_3": "4", "unit_price_3": "1"},
        follow_redirects=True)

    conn = db.get_db()
    kept = conn.execute(
        "SELECT COUNT(*) FROM po_lines WHERE item_id IN (?,?)", (a, b)).fetchone()[0]
    conn.close()
    assert kept == 2, "line after the gap was silently dropped"


# ── stock movement -> the thing that caused it ───────────────────────────────

def test_movement_with_a_valid_reference_links_to_it(auth_client):
    _, item_id, _ = _mk_short_item("Movement Ref Item")
    visit_id = _mk_visit()
    _mk_movement(item_id, "visit", visit_id, "consumed during visit")

    for url in (f"/inventory/movements?item_id={item_id}",
                f"/inventory/items/{item_id}"):
        page = auth_client.get(url)
        assert page.status_code == 200
        hrefs = _hrefs(page.get_data(as_text=True))
        assert f"/visits/{visit_id}" in hrefs, f"{url} does not link the causing visit"

    assert auth_client.get(f"/visits/{visit_id}").status_code == 200


def test_purchase_order_reference_links_back_to_the_order(auth_client):
    supplier_id, item_id, _ = _mk_short_item("PO Ref Item")
    conn = db.get_db()
    with conn:
        po_id = conn.execute(
            "INSERT INTO purchase_orders (po_number, supplier_id, order_date, status,"
            " total) VALUES (?,?,?,?,?)",
            ("PO-LINK-0001", supplier_id, "2026-03-06", "Received", 100.0),
        ).lastrowid
    conn.close()
    _mk_movement(item_id, "purchase_order", po_id, "received against PO")

    page = auth_client.get(f"/inventory/items/{item_id}")
    assert page.status_code == 200
    assert f"/procurement/orders/{po_id}" in _hrefs(page.get_data(as_text=True))
    assert auth_client.get(f"/procurement/orders/{po_id}").status_code == 200


def test_movement_whose_reference_is_gone_renders_plain_text(auth_client):
    """A reference to a deleted record: no dead link, no crash."""
    _, item_id, _ = _mk_short_item("Dangling Ref Item")
    visit_id = _mk_visit()
    _mk_movement(item_id, "visit", visit_id, "reference about to dangle")

    conn = db.get_db()
    with conn:
        conn.execute("DELETE FROM visits WHERE id=?", (visit_id,))
    conn.close()

    for url in (f"/inventory/movements?item_id={item_id}",
                f"/inventory/items/{item_id}"):
        page = auth_client.get(url)
        assert page.status_code == 200, f"{url} crashed on a dangling reference"
        html = page.get_data(as_text=True)
        assert f"/visits/{visit_id}" not in _hrefs(html), (
            f"{url} renders a dead link to a deleted visit")
        assert f"visit #{visit_id}" in html, "the reference lost its plain-text fallback"


def test_movement_with_an_unlinkable_reference_type_is_not_a_link(auth_client):
    """'adjustment' and 'transfer' carry no reference id — nothing to link to."""
    _, item_id, _ = _mk_short_item("Adjustment Ref Item")
    _mk_movement(item_id, "adjustment", None, "stock count correction")

    page = auth_client.get(f"/inventory/items/{item_id}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "stock count correction" in html
    assert not re.search(r'href="[^"]*"[^>]*>\s*adjustment', html)


# ── item -> batches, suppliers, orders; supplier -> items ────────────────────

def test_item_detail_links_its_supplier_and_purchase_orders(auth_client):
    supplier_id, item_id, _ = _mk_short_item("Item Supplier Link")
    conn = db.get_db()
    with conn:
        po_id = conn.execute(
            "INSERT INTO purchase_orders (po_number, supplier_id, order_date, status,"
            " total) VALUES (?,?,?,?,?)",
            ("PO-LINK-0002", supplier_id, "2026-03-07", "Sent", 100.0),
        ).lastrowid
        conn.execute(
            "INSERT INTO po_lines (po_id, item_id, quantity, unit_cost, total)"
            " VALUES (?,?,?,?,?)", (po_id, item_id, 100, 12.5, 1250.0))
    conn.close()

    page = auth_client.get(f"/inventory/items/{item_id}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    hrefs = _hrefs(html)

    assert f"/procurement/suppliers/{supplier_id}" in hrefs, "item does not link its supplier"
    assert f"/procurement/orders/{po_id}" in hrefs, "item does not link its purchase order"
    assert 'id="batches"' in html, "batch list has no anchor for the expiry alerts to target"
    assert "LOT-LINK-1" in html, "item detail does not show its batches"

    for url in (f"/procurement/suppliers/{supplier_id}", f"/procurement/orders/{po_id}"):
        assert auth_client.get(url).status_code == 200


def test_item_with_no_supplier_renders_text_not_a_dead_link(auth_client):
    conn = db.get_db()
    with conn:
        item_id = conn.execute(
            "INSERT INTO items (name, unit, reorder_level, max_stock, is_active)"
            " VALUES (?,?,?,?,1)", ("Orphan Supply Item", "unit", 10, 100)).lastrowid
    conn.close()

    page = auth_client.get(f"/inventory/items/{item_id}")
    assert page.status_code == 200
    assert "No supplier on record" in page.get_data(as_text=True)


def test_supplier_detail_links_its_orders_and_the_items_it_supplies(auth_client):
    supplier_id, item_id, _ = _mk_short_item("Supplier Items Link")
    conn = db.get_db()
    with conn:
        po_id = conn.execute(
            "INSERT INTO purchase_orders (po_number, supplier_id, order_date, status,"
            " total) VALUES (?,?,?,?,?)",
            ("PO-LINK-0003", supplier_id, "2026-03-08", "Received", 987.65),
        ).lastrowid
        conn.execute(
            "INSERT INTO po_lines (po_id, item_id, quantity, unit_cost, total)"
            " VALUES (?,?,?,?,?)", (po_id, item_id, 10, 12.5, 125.0))
    conn.close()

    page = auth_client.get(f"/procurement/suppliers/{supplier_id}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    hrefs = _hrefs(html)

    assert f"/procurement/orders/{po_id}" in hrefs, "supplier does not link its orders"
    assert f"/inventory/items/{item_id}" in hrefs, "supplier does not link the items it supplies"
    assert "Supplier Items Link" in html
    # purchase_orders.total, not the non-existent total_amount that rendered 0.00.
    assert "987.65" in html, "supplier PO total rendered from the wrong column"

    assert auth_client.get(f"/inventory/items/{item_id}").status_code == 200


def test_supplier_edit_saves_the_contact(auth_client):
    """The form field is contact_person; the column is contact_name."""
    supplier_id, _, _ = _mk_short_item("Editable Supplier")
    resp = auth_client.post(
        f"/procurement/suppliers/{supplier_id}/edit",
        data={"_csrf_token": _csrf(auth_client), "name": "Editable Supplier Co",
              "contact_person": "Hoda Naguib", "phone": "01000000003",
              "email": "hoda@example.com", "address": "Cairo",
              "payment_terms": "Net 30", "notes": "", "is_active": "1"},
        follow_redirects=True)
    assert resp.status_code == 200, "supplier save 500s on a bad column name"
    assert "Hoda Naguib" in resp.get_data(as_text=True)


# ── expiry alert -> the batch and the item ───────────────────────────────────

def test_expiry_alert_links_the_batch_and_its_item(auth_client):
    conn = db.get_db()
    with conn:
        item_id = conn.execute(
            "INSERT INTO items (name, unit, reorder_level, max_stock, is_active)"
            " VALUES (?,?,?,?,1)", ("Expiring Link Item", "vial", 5, 50)).lastrowid
        conn.execute(
            "INSERT INTO batches (item_id, warehouse_id, batch_number, expiry_date,"
            " quantity, unit_cost) VALUES (?,1,?,?,?,?)",
            (item_id, "LOT-EXPIRE-1", "2020-01-01", 9.0, 3.0))
    conn.close()

    page = auth_client.get("/inventory/alerts")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert "LOT-EXPIRE-1" in html, "expiring batch not listed"
    assert f"/inventory/items/{item_id}#batches" in _hrefs(html), (
        "expiry alert does not link through to the batch list")
    assert auth_client.get(f"/inventory/items/{item_id}").status_code == 200


# ── both languages ───────────────────────────────────────────────────────────

def test_supply_pages_render_in_arabic(auth_client):
    supplier_id, item_id, _ = _mk_short_item("Arabic Render Item")
    with auth_client.session_transaction() as sess:
        user = dict(sess.get("user") or {})
        user["language"] = "ar"
        sess["user"] = user

    try:
        for url in ("/inventory/alerts", f"/inventory/items/{item_id}",
                    f"/procurement/suppliers/{supplier_id}",
                    f"/procurement/orders/new?item_id={item_id}&qty=5"):
            page = auth_client.get(url)
            assert page.status_code == 200, f"{url} fails in Arabic"
            assert 'dir="rtl"' in page.get_data(as_text=True), f"{url} is not RTL"

        alerts = auth_client.get("/inventory/alerts").get_data(as_text=True)
        # Arrows are not mirrored by the bidi algorithm, so the Arabic string
        # carries its own.
        assert "← طلب" in alerts, "Arabic order label keeps the LTR arrow"
    finally:
        with auth_client.session_transaction() as sess:
            user = dict(sess.get("user") or {})
            user["language"] = "en"
            sess["user"] = user
