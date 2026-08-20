# -*- coding: utf-8 -*-
"""The Pet Shop receipt has to actually reach the printer.

The "Print Receipt" button linked to ?print=1 and the route ignored the query
string entirely, so it opened the ordinary order page — full sidebar, no print
stylesheet, no window.print() — and the till printed nothing. These tests pin
the three things that were wrong: the flag is honoured, the page prints itself,
and it carries the clinic's own name rather than a hardcoded one.
"""
import itertools
import re

# The database lives for the whole file, so order_number and sku - both UNIQUE -
# have to differ per call or the second test dies on the first one's rows.
_seq = itertools.count(1)


def _make_order(auth_client, app):
    """A paid order with one line, created straight in the database.

    Returns (order_id, order_number)."""
    n = next(_seq)
    with app.app_context():
        import models.database as db
        from blueprints.petshop.routes import ensure_petshop_tables
        ensure_petshop_tables()
        conn = db.get_db()
        # ps_order_items.product_id is a real foreign key, so the product has to exist.
        pcur = conn.execute(
            "INSERT INTO ps_products (name, sku, sell_price, stock_qty)"
            " VALUES (?,?,?,?)",
            ("Royal Canin Kitten 2kg", "RC-KIT-%d" % n, 125.0, 50))
        pid = pcur.lastrowid
        cur = conn.execute(
            "INSERT INTO ps_orders (order_number, status, subtotal, discount_amount,"
            " tax_amount, total, paid_amount, change_amount, payment_method,"
            " served_by, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            ("PS-RCPT-%d" % n, "paid", 250.0, 25.0, 0.0, 225.0, 250.0, 25.0,
             "Cash", "Reception", "2026-08-20 11:30:00"))
        oid = cur.lastrowid
        conn.execute(
            "INSERT INTO ps_order_items (order_id, product_id, product_name, qty,"
            " unit_price, discount, line_total) VALUES (?,?,?,?,?,?,?)",
            (oid, pid, "Royal Canin Kitten 2kg", 2, 125.0, 25.0, 225.0))
        conn.commit()
        conn.close()
    return oid, "PS-RCPT-%d" % n


def test_print_flag_returns_a_printable_receipt(auth_client, app):
    """?print=1 must render the receipt, not the ordinary order screen."""
    oid, num = _make_order(auth_client, app)

    plain = auth_client.get("/petshop/orders/%d" % oid)
    printed = auth_client.get("/petshop/orders/%d?print=1" % oid)
    assert plain.status_code == 200
    assert printed.status_code == 200

    body = printed.get_data(as_text=True)

    # It must print itself — this is the whole defect.
    assert "window.print()" in body, "the receipt never calls window.print()"
    assert "@media print" in body, "the receipt has no print stylesheet"

    # And it must be a different page from the order screen, not the same one.
    assert body != plain.get_data(as_text=True)


def test_receipt_shows_the_money_and_the_line(auth_client, app):
    oid, num = _make_order(auth_client, app)
    body = auth_client.get("/petshop/orders/%d?print=1" % oid).get_data(as_text=True)

    assert "Royal Canin Kitten 2kg" in body
    assert "225.00" in body          # total
    assert "25.00" in body           # change
    assert num in body               # receipt number


def test_receipt_prints_the_clinics_own_name(auth_client, app):
    """bug-140 and bug-501 were both this: a hardcoded name on paper the clinic
    hands to a customer. The receipt must read the clinic row."""
    with app.app_context():
        import models.database as db
        conn = db.get_db()
        conn.execute("UPDATE clinic SET name=?", ("Dr Hatem Veterinary Centre",))
        conn.commit()
        conn.close()
        db.cache_invalidate("clinic_row")

    oid, num = _make_order(auth_client, app)
    body = auth_client.get("/petshop/orders/%d?print=1" % oid).get_data(as_text=True)
    assert "Dr Hatem Veterinary Centre" in body, "receipt is not reading the clinic row"


def test_cancelled_order_never_prints_as_a_valid_receipt(auth_client, app):
    """A cancelled sale that prints a clean receipt is a refund waiting to happen."""
    oid, num = _make_order(auth_client, app)
    with app.app_context():
        import models.database as db
        conn = db.get_db()
        conn.execute("UPDATE ps_orders SET status='cancelled' WHERE id=?", (oid,))
        conn.commit()
        conn.close()

    body = auth_client.get("/petshop/orders/%d?print=1" % oid).get_data(as_text=True)
    assert "NOT A VALID RECEIPT" in body or "غير صالح" in body


def test_pos_modal_links_with_the_print_flag(app):
    """The POS confirmation modal linked to the order page with no flag, so the
    one receipt staff print most often was the one that never printed."""
    src = (app.jinja_env.get_or_select_template("petshop/pos.html")
           .filename)
    body = open(src, encoding="utf-8").read()
    link = re.search(r"receipt-link'\)\.href\s*=\s*([^;]+);", body)
    assert link, "receipt-link href assignment not found in pos.html"
    assert "print=1" in link.group(1), (
        "POS receipt link does not request the printable view: %s" % link.group(1))
