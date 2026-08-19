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
