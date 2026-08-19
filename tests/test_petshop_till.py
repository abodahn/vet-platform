# -*- coding: utf-8 -*-
"""The pet shop till, which is where a customer hands over money.

Four defects, all of the same family as the rest of this codebase: the sale
looks right on screen and the books say something else.

  * Card, Transfer and Instapay recorded NO payment. "Amount tendered" is a
    cash idea — nobody types into it for a card — so paid_amount arrived as 0
    and the payment was skipped, while the shop still booked the sale as
    revenue. The clinic's accounts then said a customer owed money they had
    already handed over. Three of the four buttons.
  * The order-level discount never reached the invoice, so every discounted
    sale left the customer owing exactly the discount, permanently.
  * A mistyped discount produced a NEGATIVE total: the till showed 0.00, the
    sale completed, and Revenue Today went DOWN.
  * Every report filtered status='paid'. On the live demo all 172 orders carry
    'completed', so 334,070 EGP of real sales reported as zero.
"""
import pytest

from conftest import get_csrf
from models import database as db


@pytest.fixture()
def product(app):
    with app.app_context():
        conn = db.get_db()
        from blueprints.petshop.routes import ensure_petshop_tables
        ensure_petshop_tables()
        pid = conn.execute(
            "INSERT INTO ps_products(name, sell_price, stock_qty, is_active)"
            " VALUES(?,?,?,1)", ("Till Test Food", 100.0, 500)).lastrowid
        conn.commit()
        conn.close()
    return pid


def _sell(auth_client, product_id, **over):
    body = {
        "items": [{"product_id": product_id, "product_name": "Till Test Food",
                   "qty": 2, "unit_price": 100.0, "tax_rate": 0, "discount": 0}],
        "payment_method": "Cash",
        "discount_amount": 0,
        "paid_amount": 200.0,
    }
    body.update(over)
    return auth_client.post("/petshop/orders/create", json=body,
                            headers={"X-CSRF-Token": get_csrf(auth_client)})


def _invoice(app, invoice_id):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT total, paid_amount, due_amount, status FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        conn.close()
    return dict(row) if row else None


@pytest.mark.parametrize("method", ["Card", "Transfer", "Instapay"])
def test_a_non_cash_sale_is_recorded_as_paid(auth_client, app, product, method):
    """Nobody tenders cash for a card. The sale IS the payment."""
    r = _sell(auth_client, product, payment_method=method, paid_amount=0)
    assert r.status_code == 200, r.data[:300]
    inv_id = r.get_json().get("invoice_id")
    assert inv_id, "no invoice was created"

    inv = _invoice(app, inv_id)
    assert float(inv["paid_amount"]) == 200.0, \
        "a %s sale recorded %s paid — the customer is billed for money they gave you" \
        % (method, inv["paid_amount"])
    assert float(inv["due_amount"]) == 0.0
    assert inv["status"] == "Paid"


def test_cash_still_takes_what_was_tendered_and_gives_change(auth_client, app, product):
    r = _sell(auth_client, product, payment_method="Cash", paid_amount=250.0)
    data = r.get_json()
    assert data["change"] == 50.0, "change is wrong: %s" % data["change"]
    inv = _invoice(app, data["invoice_id"])
    assert float(inv["paid_amount"]) == 200.0, \
        "the till banked the change as well as the sale"


def test_the_order_discount_reaches_the_invoice(auth_client, app, product):
    r = _sell(auth_client, product, discount_amount=50.0, paid_amount=150.0)
    data = r.get_json()
    assert data["total"] == 150.0

    inv = _invoice(app, data["invoice_id"])
    assert float(inv["total"]) == 150.0, \
        "the invoice says %s but the customer paid 150 — they owe the discount forever" \
        % inv["total"]
    assert float(inv["due_amount"]) == 0.0


def test_a_discount_bigger_than_the_basket_cannot_go_negative(auth_client, app, product):
    """The till showed 0.00, the sale went through, Revenue Today went DOWN."""
    r = _sell(auth_client, product, discount_amount=9999.0, paid_amount=0)
    data = r.get_json()
    assert data["total"] >= 0, "a negative-total sale was accepted: %s" % data["total"]
    inv = _invoice(app, data["invoice_id"])
    assert float(inv["total"]) >= 0


def test_a_negative_quantity_is_refused(auth_client, app, product):
    """Stock deduction is a subtraction — a negative qty mints stock."""
    with app.app_context():
        conn = db.get_db()
        before = conn.execute("SELECT stock_qty FROM ps_products WHERE id=?",
                              (product,)).fetchone()[0]
        conn.close()

    r = auth_client.post("/petshop/orders/create", json={
        "items": [{"product_id": product, "product_name": "Till Test Food",
                   "qty": -5, "unit_price": 100.0, "tax_rate": 0, "discount": 0}],
        "payment_method": "Cash", "paid_amount": 0, "discount_amount": 0,
    }, headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 400, "a negative quantity was accepted"

    with app.app_context():
        conn = db.get_db()
        after = conn.execute("SELECT stock_qty FROM ps_products WHERE id=?",
                             (product,)).fetchone()[0]
        conn.close()
    assert after == before, "stock was created out of nothing"


def test_reports_count_orders_however_the_status_is_spelt():
    """order_create writes 'paid'; all 172 live orders carry 'completed'.

    Every aggregate filtered status='paid', so whichever spelling a row had,
    one whole set was invisible — 334,070 EGP reporting as zero on the demo.
    """
    import io
    src = io.open("blueprints/petshop/routes.py", encoding="utf-8").read()
    assert "status='paid'" not in src, \
        "a report still filters on one spelling of the status"
    assert src.count("NOT IN ('cancelled','refunded')") >= 6, \
        "the aggregates do not count every non-cancelled order"


def test_cancelling_reverses_the_money_not_just_the_invoice(auth_client, app, product):
    """Restoring stock and voiding the invoice while leaving the payment row
    meant a cancelled sale still counted as cash taken."""
    r = _sell(auth_client, product, payment_method="Card", paid_amount=0)
    data = r.get_json()
    oid, inv_id = data["order_id"], data["invoice_id"]

    auth_client.post("/petshop/orders/%d/cancel" % oid,
                     data={"_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        net = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?",
            (inv_id,)).fetchone()[0]
        n = conn.execute("SELECT COUNT(*) FROM payments WHERE invoice_id=?",
                         (inv_id,)).fetchone()[0]
        conn.close()

    assert float(net) == 0.0, \
        "a cancelled sale still shows %s collected" % net
    assert n >= 2, "the reversal replaced the original instead of offsetting it"


# ── the three that were not blockers, but are still wrong ────────────────────

def test_clearing_a_date_box_does_not_500_the_report(auth_client, app, product):
    """A get() default only applies when the key is ABSENT. An emptied input
    submits "", which reached PostgreSQL as ''::date and took the page down —
    verified on the live demo."""
    for qs in ("?date_from=&date_to=",
               "?date_from=2026-01-01&date_to=",
               "?date_from=&date_to=2026-12-31"):
        r = auth_client.get("/petshop/reports" + qs)
        assert r.status_code == 200, \
            "reports %s returned %s" % (qs, r.status_code)


def test_clearing_the_stock_box_does_not_500(auth_client, app, product):
    r = auth_client.post("/petshop/products/%d/stock" % product,
                         data={"qty": "", "movement": "in",
                               "_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)
    assert r.status_code == 200


def test_two_tills_cannot_sell_the_same_last_unit(auth_client, app):
    """The deduction was MAX(0, stock-qty), which never fails: both cashiers
    printed a receipt and the clamp hid it by flooring at zero."""
    with app.app_context():
        conn = db.get_db()
        pid = conn.execute(
            "INSERT INTO ps_products(name, sell_price, stock_qty, is_active)"
            " VALUES(?,?,?,1)", ("Last Unit", 50.0, 1)).lastrowid
        conn.commit()
        conn.close()

    def buy():
        return auth_client.post("/petshop/orders/create", json={
            "items": [{"product_id": pid, "product_name": "Last Unit", "qty": 1,
                       "unit_price": 50.0, "tax_rate": 0, "discount": 0}],
            "payment_method": "Cash", "paid_amount": 50.0, "discount_amount": 0,
        }, headers={"X-CSRF-Token": get_csrf(auth_client)})

    first, second = buy(), buy()
    assert first.status_code == 200, "the first sale should succeed"
    assert second.status_code == 409, \
        "the shop sold a second copy of its last unit (%s)" % second.status_code

    with app.app_context():
        conn = db.get_db()
        left = conn.execute("SELECT stock_qty FROM ps_products WHERE id=?",
                            (pid,)).fetchone()[0]
        conn.close()
    assert left == 0, "stock ended at %s" % left


def test_profit_uses_the_cost_at_the_time_of_sale(auth_client, app):
    """A closed month must stay closed. The report joined ps_products live, so
    a supplier raising a price rewrote last month's profit."""
    with app.app_context():
        conn = db.get_db()
        pid = conn.execute(
            "INSERT INTO ps_products(name, sell_price, cost_price, stock_qty, is_active)"
            " VALUES(?,?,?,?,1)", ("Cost Drift", 100.0, 40.0, 50)).lastrowid
        conn.commit()
        conn.close()

    auth_client.post("/petshop/orders/create", json={
        "items": [{"product_id": pid, "product_name": "Cost Drift", "qty": 1,
                   "unit_price": 100.0, "tax_rate": 0, "discount": 0}],
        "payment_method": "Cash", "paid_amount": 100.0, "discount_amount": 0,
    }, headers={"X-CSRF-Token": get_csrf(auth_client)})

    with app.app_context():
        conn = db.get_db()
        stored = conn.execute(
            "SELECT unit_cost FROM ps_order_items WHERE product_id=? ORDER BY id DESC LIMIT 1",
            (pid,)).fetchone()[0]
        # The supplier puts the price up afterwards.
        conn.execute("UPDATE ps_products SET cost_price=90.0 WHERE id=?", (pid,))
        conn.commit()
        after = conn.execute(
            "SELECT unit_cost FROM ps_order_items WHERE product_id=? ORDER BY id DESC LIMIT 1",
            (pid,)).fetchone()[0]
        conn.close()

    assert float(stored) == 40.0, "the sale did not record what the goods cost"
    assert float(after) == 40.0, \
        "a later price change rewrote the cost of a sale already made"


def test_a_broken_cart_does_not_return_a_python_traceback(auth_client, app):
    """The raw exception text used to go straight to the browser."""
    r = auth_client.post("/petshop/orders/create", json={
        "items": [{"product_id": 999999, "qty": 1}],
        "payment_method": "Cash", "paid_amount": 0, "discount_amount": 0,
    }, headers={"X-CSRF-Token": get_csrf(auth_client)})
    body = r.get_data(as_text=True)
    for leak in ("Traceback", "sqlite3.", "psycopg2.", "KeyError", "line "):
        assert leak not in body, "the error response leaks internals: %s" % leak
