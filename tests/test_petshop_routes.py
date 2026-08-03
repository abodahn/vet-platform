# -*- coding: utf-8 -*-
"""Pet-shop POS write routes: does the till agree with the books and the shelf?

A POS sale is the one transaction in the product that touches money AND stock in
the same request. It has to produce, atomically: an order, its lines, a stock
deduction with a movement, an invoice, and a payment that settles it. Anything
short of that is either revenue the accountant never sees or stock the counter
thinks it still has.

Every test drives the real route and reads back ps_orders / ps_order_items /
ps_products / ps_stock_movements / invoices, asserting exact figures.

SQLite, no network.
"""
import pytest

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


def _post_json(client, url, payload):
    return client.post(url, json=payload,
                       headers={"X-CSRF-Token": _csrf(client)})


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


@pytest.fixture(autouse=True)
def petshop_schema(app):
    with app.app_context():
        from blueprints.petshop.routes import ensure_petshop_tables
        ensure_petshop_tables()


def test_table_bootstrap_tops_up_an_older_ps_orders(auth_client):
    """`CREATE TABLE IF NOT EXISTS` never migrates. A database whose ps_orders
    predates the finance bridge has no invoice_id — and tests/test_pet_shop.py
    creates exactly that shape — so every POS sale failed to link its invoice
    inside a warning-only except."""
    from tests.conftest import table_columns
    conn = db.get_db()
    try:
        cols = table_columns(conn, "ps_orders")
    finally:
        conn.close()
    assert "invoice_id" in cols, \
        "ensure_petshop_tables() left an older ps_orders without invoice_id"


def _rows_raw(sql):
    conn = db.get_db()
    rs = conn.execute(sql).fetchall()
    conn.close()
    return rs


_SKU = {"n": 0}


def _product(name, price, stock, cost=0.0, tax_rate=0.0, reorder=5):
    _SKU["n"] += 1
    conn = db.get_db()
    with conn:
        pid = conn.execute(
            """INSERT INTO ps_products (name, sku, sell_price, cost_price, tax_rate,
               stock_qty, reorder_level, is_active) VALUES (?,?,?,?,?,?,?,1)""",
            (name, f"PSRT-{_SKU['n']:05d}", price, cost, tax_rate, stock, reorder),
        ).lastrowid
    conn.close()
    return pid


def _owner(name="Petshop Route Owner", phone="01088000001"):
    conn = db.get_db()
    with conn:
        oid = conn.execute(
            "INSERT INTO owners (full_name, phone) VALUES (?,?)", (name, phone)
        ).lastrowid
    conn.close()
    return oid


def _stock(pid):
    return float(_row("SELECT stock_qty FROM ps_products WHERE id=?", (pid,))["stock_qty"])


# ═══ POS SALE — money, stock and the books in one request ════════════════════

def test_pos_sale_creates_order_invoice_payment_and_deducts_stock(auth_client):
    owner_id = _owner("POS Full Owner", "01088000010")
    p1 = _product("POS Kibble", 45.50, 20)
    p2 = _product("POS Collar", 129.99, 5)

    resp = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": owner_id,
        "payment_method": "Cash",
        "paid_amount": 250.00,
        "items": [
            {"product_id": p1, "product_name": "POS Kibble", "qty": 2,
             "unit_price": 45.50},
            {"product_id": p2, "product_name": "POS Collar", "qty": 1,
             "unit_price": 129.99},
        ],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body.get("success") is True, body

    expected_total = round(2 * 45.50 + 1 * 129.99, 2)   # 220.99
    order = dict(_row("SELECT * FROM ps_orders WHERE id=?", (body["order_id"],)))
    assert order["status"] == "paid"
    assert round(order["subtotal"], 2) == expected_total
    assert round(order["total"], 2) == expected_total
    assert round(order["paid_amount"], 2) == 250.00
    assert round(order["change_amount"], 2) == round(250.00 - expected_total, 2)

    lines = _rows("SELECT * FROM ps_order_items WHERE order_id=? ORDER BY id",
                  (order["id"],))
    assert [round(l["line_total"], 2) for l in lines] == [91.00, 129.99]
    assert round(sum(round(l["line_total"], 2) for l in lines), 2) == \
        round(order["total"], 2), "order total does not equal the sum of its lines"

    # Shelf
    assert _stock(p1) == 18.0
    assert _stock(p2) == 4.0
    moves = _rows("SELECT * FROM ps_stock_movements WHERE ref_type='sale' AND ref_id=?",
                  (order["id"],))
    assert {(m["product_id"], m["movement"], round(m["qty"], 2)) for m in moves} == \
        {(p1, "out", 2.0), (p2, "out", 1.0)}

    # Books
    inv_id = body.get("invoice_id")
    assert inv_id, "the POS sale produced no invoice — the revenue never reaches accounting"
    assert order["invoice_id"] == inv_id, "the order was not linked back to its invoice"
    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    assert inv["owner_id"] == owner_id
    assert round(inv["total"], 2) == expected_total, \
        "the invoice total does not match what the till charged"
    inv_lines = _rows("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,))
    assert round(sum(round(l["total"], 2) for l in inv_lines), 2) == expected_total
    assert round(inv["paid_amount"], 2) == expected_total, \
        "the POS payment was not recorded against the invoice"
    assert abs(inv["due_amount"]) < 0.005
    assert inv["status"] == "Paid"


def test_pos_line_discount_is_carried_into_the_order_total(auth_client):
    """A 10% line discount must come off what the customer is charged, not only
    off the printed line."""
    owner_id = _owner("POS Discount Owner", "01088000011")
    pid = _product("POS Discounted Shampoo", 100.00, 10)

    resp = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": owner_id, "paid_amount": 180.00,
        "items": [{"product_id": pid, "product_name": "POS Discounted Shampoo",
                   "qty": 2, "unit_price": 100.00, "discount": 10}],
    })
    body = resp.get_json()
    assert body.get("success") is True, body

    order = dict(_row("SELECT * FROM ps_orders WHERE id=?", (body["order_id"],)))
    line = _rows("SELECT * FROM ps_order_items WHERE order_id=?", (order["id"],))[0]

    assert round(line["line_total"], 2) == 180.00
    assert round(order["total"], 2) == 180.00, (
        f"order total {order['total']} ignores the 10% line discount that the "
        f"line itself applied ({line['line_total']})")
    assert round(order["subtotal"], 2) == 180.00

    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (order["invoice_id"],)))
    assert round(inv["total"], 2) == round(order["total"], 2), \
        "the invoice and the order disagree about what was charged"


def test_pos_tax_is_added_on_top_of_the_line(auth_client):
    owner_id = _owner("POS Tax Owner", "01088000012")
    pid = _product("POS Taxed Vitamins", 50.00, 10, tax_rate=14.0)

    body = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": owner_id, "paid_amount": 114.00,
        "items": [{"product_id": pid, "product_name": "POS Taxed Vitamins",
                   "qty": 2, "unit_price": 50.00, "tax_rate": 14}],
    }).get_json()
    assert body.get("success") is True, body

    order = dict(_row("SELECT * FROM ps_orders WHERE id=?", (body["order_id"],)))
    assert round(order["subtotal"], 2) == 100.00
    assert round(order["tax_amount"], 2) == 14.00
    assert round(order["total"], 2) == 114.00
    assert round(order["subtotal"] + order["tax_amount"] - order["discount_amount"], 2) \
        == round(order["total"], 2)


def test_pos_order_discount_comes_off_the_total(auth_client):
    owner_id = _owner("POS Order Discount Owner", "01088000013")
    pid = _product("POS Bed", 300.00, 10)

    body = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": owner_id, "paid_amount": 275.00, "discount_amount": 25.00,
        "items": [{"product_id": pid, "product_name": "POS Bed",
                   "qty": 1, "unit_price": 300.00}],
    }).get_json()
    order = dict(_row("SELECT * FROM ps_orders WHERE id=?", (body["order_id"],)))
    assert round(order["discount_amount"], 2) == 25.00
    assert round(order["total"], 2) == 275.00
    assert round(order["change_amount"], 2) == 0.0


def test_walk_in_sale_without_an_owner_still_reaches_the_books(auth_client):
    """Counter sale, no customer record. The order must go through AND the
    revenue must land in accounting — a sale that only exists in ps_orders is
    money the P&L never sees."""
    pid = _product("Walk-in Treats", 22.25, 8)

    resp = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": None, "paid_amount": 44.50,
        "items": [{"product_id": pid, "product_name": "Walk-in Treats",
                   "qty": 2, "unit_price": 22.25}],
    })
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body.get("success") is True, body

    order = dict(_row("SELECT * FROM ps_orders WHERE id=?", (body["order_id"],)))
    assert round(order["total"], 2) == 44.50
    assert _stock(pid) == 6.0

    assert body.get("invoice_id"), (
        "a walk-in sale produced no invoice — the finance bridge swallowed the "
        "failure and the revenue is invisible to accounting")
    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (body["invoice_id"],)))
    assert round(inv["total"], 2) == 44.50
    assert inv["status"] == "Paid"


def test_pos_sale_with_no_items_is_rejected(auth_client):
    before = _row("SELECT COUNT(*) c FROM ps_orders")["c"]
    resp = _post_json(auth_client, "/petshop/orders/create",
                      {"owner_id": None, "items": []})
    assert resp.status_code == 400
    assert _row("SELECT COUNT(*) c FROM ps_orders")["c"] == before


def test_pos_never_drives_stock_negative(auth_client):
    pid = _product("POS Nearly Gone", 10.00, 3)
    body = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": _owner("Oversell Owner", "01088000014"), "paid_amount": 100.0,
        "items": [{"product_id": pid, "product_name": "POS Nearly Gone",
                   "qty": 10, "unit_price": 10.00}],
    }).get_json()
    assert body.get("success") is True, body
    assert _stock(pid) == 0.0, "stock went negative on an oversell"


# ═══ CANCELLATION — the reverse direction ════════════════════════════════════

def test_cancelling_an_order_restores_stock_and_reverses_the_invoice(auth_client):
    owner_id = _owner("Cancel Owner", "01088000020")
    pid = _product("Cancelled Chew", 60.00, 12)

    body = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": owner_id, "paid_amount": 180.00,
        "items": [{"product_id": pid, "product_name": "Cancelled Chew",
                   "qty": 3, "unit_price": 60.00}],
    }).get_json()
    oid, inv_id = body["order_id"], body["invoice_id"]
    assert _stock(pid) == 9.0

    _post(auth_client, f"/petshop/orders/{oid}/cancel", {})

    order = dict(_row("SELECT * FROM ps_orders WHERE id=?", (oid,)))
    assert order["status"] == "cancelled"
    assert _stock(pid) == 12.0, "cancelling did not put the stock back"
    back = _rows("SELECT * FROM ps_stock_movements WHERE ref_type='cancellation'"
                 " AND ref_id=?", (oid,))
    assert len(back) == 1 and round(back[0]["qty"], 2) == 3.0

    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    assert inv["status"] == "Cancelled", (
        f"the order was cancelled but its invoice is still {inv['status']!r} — "
        "180.00 EGP of cancelled revenue stays in the P&L")


def test_cancelling_twice_restores_the_stock_only_once(auth_client):
    owner_id = _owner("Double Cancel Owner", "01088000021")
    pid = _product("Double Cancel Leash", 30.00, 10)

    body = _post_json(auth_client, "/petshop/orders/create", {
        "owner_id": owner_id, "paid_amount": 60.00,
        "items": [{"product_id": pid, "product_name": "Double Cancel Leash",
                   "qty": 2, "unit_price": 30.00}],
    }).get_json()
    oid = body["order_id"]

    _post(auth_client, f"/petshop/orders/{oid}/cancel", {})
    _post(auth_client, f"/petshop/orders/{oid}/cancel", {})

    assert _stock(pid) == 10.0, "a second cancellation invented stock"
    assert _row("SELECT COUNT(*) c FROM ps_stock_movements WHERE"
                " ref_type='cancellation' AND ref_id=?", (oid,))["c"] == 1


# ═══ PRODUCTS ════════════════════════════════════════════════════════════════

def test_product_new_records_its_opening_stock_as_a_movement(auth_client):
    _post(auth_client, "/petshop/products/new", {
        "name": "New Route Product", "sku": "NEW-RT-1", "brand": "Aleefy",
        "species": "dog", "cost_price": "18.40", "sell_price": "31.75",
        "tax_rate": "14", "reorder_level": "6", "stock_qty": "35", "unit": "bag",
    })
    p = _row("SELECT * FROM ps_products WHERE sku='NEW-RT-1'")
    assert p is not None, "POST /petshop/products/new wrote no product"
    p = dict(p)
    assert round(p["cost_price"], 2) == 18.40
    assert round(p["sell_price"], 2) == 31.75
    assert round(p["tax_rate"], 2) == 14.0
    assert p["stock_qty"] == 35
    assert p["reorder_level"] == 6

    mv = _rows("SELECT * FROM ps_stock_movements WHERE product_id=? AND"
               " ref_type='opening_stock'", (p["id"],))
    assert len(mv) == 1, "opening stock was not journalled"
    assert mv[0]["movement"] == "in"
    assert round(mv[0]["qty"], 2) == 35.0


def test_product_new_with_no_opening_stock_journals_nothing(auth_client):
    _post(auth_client, "/petshop/products/new", {
        "name": "Zero Stock Product", "sku": "NEW-RT-2",
        "cost_price": "1", "sell_price": "2", "stock_qty": "0"})
    p = dict(_row("SELECT * FROM ps_products WHERE sku='NEW-RT-2'"))
    assert p["stock_qty"] == 0
    assert _rows("SELECT * FROM ps_stock_movements WHERE product_id=?", (p["id"],)) == []


def test_product_edit_changes_the_price_but_not_the_stock(auth_client):
    pid = _product("Editable Petshop Product", 40.00, 17, cost=20.00)

    _post(auth_client, f"/petshop/products/{pid}/edit", {
        "name": "Editable Petshop Product v2", "sku": "PSRT-EDITED",
        "cost_price": "24.60", "sell_price": "49.90", "tax_rate": "5",
        "reorder_level": "9", "unit": "tin", "species": "cat",
    })
    p = dict(_row("SELECT * FROM ps_products WHERE id=?", (pid,)))
    assert p["name"] == "Editable Petshop Product v2"
    assert round(p["cost_price"], 2) == 24.60
    assert round(p["sell_price"], 2) == 49.90
    assert p["reorder_level"] == 9
    assert p["stock_qty"] == 17, "editing a product changed its stock on hand"


def test_product_edit_of_a_missing_product_redirects_without_writing(auth_client):
    before = _row("SELECT COUNT(*) c FROM ps_products")["c"]
    r = _post(auth_client, "/petshop/products/99999999/edit", {"name": "Ghost"})
    assert r.status_code == 200
    assert _row("SELECT COUNT(*) c FROM ps_products")["c"] == before


def test_product_stock_adjustments_move_the_count_both_ways(auth_client):
    pid = _product("Adjustable Product", 12.00, 10)

    _post(auth_client, f"/petshop/products/{pid}/stock",
          {"qty": "25", "movement": "in", "notes": "delivery"})
    assert _stock(pid) == 35.0

    _post(auth_client, f"/petshop/products/{pid}/stock",
          {"qty": "10", "movement": "out", "notes": "damaged"})
    assert _stock(pid) == 25.0

    mv = _rows("SELECT * FROM ps_stock_movements WHERE product_id=? AND"
               " ref_type='manual_adjustment' ORDER BY id", (pid,))
    assert [(m["movement"], round(m["qty"], 2)) for m in mv] == \
        [("in", 25.0), ("out", 10.0)]
    assert mv[1]["notes"] == "damaged"


def test_product_stock_out_cannot_go_below_zero(auth_client):
    pid = _product("Underflow Product", 5.00, 4)
    _post(auth_client, f"/petshop/products/{pid}/stock",
          {"qty": "999", "movement": "out"})
    assert _stock(pid) == 0.0


# ═══ CATEGORIES ══════════════════════════════════════════════════════════════

def test_category_add_then_delete_when_empty(auth_client):
    _post(auth_client, "/petshop/categories",
          {"action": "add", "name": "Route Test Category",
           "name_ar": "فئة", "description": "toys"})
    cat = _row("SELECT * FROM ps_categories WHERE name='Route Test Category'")
    assert cat is not None, "POST /petshop/categories wrote no category"

    _post(auth_client, "/petshop/categories",
          {"action": "delete", "cat_id": str(cat["id"])})
    assert _row("SELECT COUNT(*) c FROM ps_categories WHERE id=?",
                (cat["id"],))["c"] == 0


def test_category_with_products_cannot_be_deleted(auth_client):
    _post(auth_client, "/petshop/categories",
          {"action": "add", "name": "Occupied Category"})
    cat = dict(_row("SELECT * FROM ps_categories WHERE name='Occupied Category'"))
    pid = _product("Categorised Product", 9.00, 3)
    conn = db.get_db()
    with conn:
        conn.execute("UPDATE ps_products SET category_id=? WHERE id=?", (cat["id"], pid))
    conn.close()

    _post(auth_client, "/petshop/categories",
          {"action": "delete", "cat_id": str(cat["id"])})
    assert _row("SELECT COUNT(*) c FROM ps_categories WHERE id=?",
                (cat["id"],))["c"] == 1, \
        "a category with products was deleted, orphaning them"


def test_blank_category_name_is_ignored(auth_client):
    before = _row("SELECT COUNT(*) c FROM ps_categories")["c"]
    _post(auth_client, "/petshop/categories", {"action": "add", "name": "   "})
    assert _row("SELECT COUNT(*) c FROM ps_categories")["c"] == before


# ═══ POS LOOKUP APIs ═════════════════════════════════════════════════════════

def test_product_search_returns_only_sellable_products(auth_client):
    ok = _product("Searchable Salmon Pate", 33.00, 6, tax_rate=14.0)
    _product("Searchable Salmon Sold Out", 33.00, 0)

    data = auth_client.get("/petshop/api/products/search?q=Searchable Salmon").get_json()
    ids = {r["id"] for r in data}
    assert ok in ids
    assert all(r["stock_qty"] > 0 for r in data), \
        "the POS offered a product with no stock"
    hit = next(r for r in data if r["id"] == ok)
    assert round(hit["sell_price"], 2) == 33.00
    assert round(hit["tax_rate"], 2) == 14.0


def test_owner_search_matches_name_and_phone(auth_client):
    oid = _owner("Searchable Owner Zaki", "01077712345")

    by_name = auth_client.get("/petshop/api/owners/search?q=Zaki").get_json()
    assert oid in {r["id"] for r in by_name}

    by_phone = auth_client.get("/petshop/api/owners/search?q=01077712345").get_json()
    assert oid in {r["id"] for r in by_phone}
    assert by_phone[0]["phone"] == "01077712345"
