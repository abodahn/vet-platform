# -*- coding: utf-8 -*-
"""Client deposits / account credit.

Money taken before there is an invoice -- boarding and surgery deposits. There
was no way to record it at all, so it was either refused or kept on paper.

The balance is DERIVED (SUM over an append-only ledger), never stored, so the
tests here check the ledger and the balance agree after every operation. The
two ways this could lose real money:

  - applying more credit than the client has -> the clinic credits an invoice
    with money nobody paid;
  - applying more than the invoice owes -> the excess vanishes, because an
    invoice cannot go below zero.

Both are asserted.
"""
import pytest

import models.database as db
from tests.conftest import get_csrf


@pytest.fixture()
def owner(app):
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Credit Test Owner", "01000000888"))
            oid = cur.lastrowid
        conn.close()
    return oid


def _invoice(app, oid, total=500.0):
    with app.app_context():
        return db.create_invoice(
            {"owner_id": oid, "issue_date": "2026-08-02", "created_by": "t"},
            [{"line_type": "service", "description": "Consult", "quantity": 1,
              "unit_price": total, "discount": 0, "total": total}])


# ── the ledger ───────────────────────────────────────────────────────────────

def test_a_new_client_has_no_credit(app, owner):
    with app.app_context():
        assert db.owner_credit_balance(owner) == 0.0


def test_a_deposit_raises_the_balance(app, owner):
    with app.app_context():
        db.add_deposit(owner, 1000, "Cash", created_by="reception")
        assert db.owner_credit_balance(owner) == 1000.0


def test_deposits_accumulate(app, owner):
    with app.app_context():
        db.add_deposit(owner, 300, created_by="t")
        db.add_deposit(owner, 250.50, created_by="t")
        assert db.owner_credit_balance(owner) == 550.50


def test_a_deposit_must_be_positive(app, owner):
    with app.app_context():
        with pytest.raises(ValueError):
            db.add_deposit(owner, 0, created_by="t")
        with pytest.raises(ValueError):
            db.add_deposit(owner, -50, created_by="t")


def test_the_history_records_who_took_the_money(app, owner):
    with app.app_context():
        db.add_deposit(owner, 400, "Instapay", reference="TX-9",
                       note="boarding", created_by="Reception A")
        entry = db.list_owner_credits(owner)[0]
    assert entry["kind"] == "deposit"
    assert entry["created_by"] == "Reception A"
    assert entry["method"] == "Instapay"
    assert entry["reference"] == "TX-9"


# ── applying credit ──────────────────────────────────────────────────────────

def test_applying_credit_pays_the_invoice(app, owner):
    inv_id = _invoice(app, owner, 500.0)
    with app.app_context():
        db.add_deposit(owner, 500, created_by="t")
        db.apply_credit(owner, inv_id, 500, created_by="t")
        inv = db.get_invoice(inv_id)
    assert inv["paid_amount"] == 500.0
    assert inv["due_amount"] == 0.0


def test_applying_credit_spends_it(app, owner):
    inv_id = _invoice(app, owner, 500.0)
    with app.app_context():
        db.add_deposit(owner, 800, created_by="t")
        db.apply_credit(owner, inv_id, 500, created_by="t")
        assert db.owner_credit_balance(owner) == 300.0


def test_cannot_apply_more_credit_than_the_client_has(app, owner):
    """Otherwise the clinic credits an invoice with money nobody ever paid."""
    inv_id = _invoice(app, owner, 500.0)
    with app.app_context():
        db.add_deposit(owner, 100, created_by="t")
        with pytest.raises(ValueError):
            db.apply_credit(owner, inv_id, 500, created_by="t")
        assert db.owner_credit_balance(owner) == 100.0, "the balance moved anyway"
        assert db.get_invoice(inv_id)["paid_amount"] == 0.0, "the invoice was paid anyway"


def test_cannot_apply_more_than_the_invoice_owes(app, owner):
    """The excess would vanish: an invoice cannot go below zero, so the credit
    would be consumed and appear nowhere."""
    inv_id = _invoice(app, owner, 200.0)
    with app.app_context():
        db.add_deposit(owner, 1000, created_by="t")
        with pytest.raises(ValueError):
            db.apply_credit(owner, inv_id, 1000, created_by="t")
        assert db.owner_credit_balance(owner) == 1000.0


def test_partial_application_leaves_the_rest_owed(app, owner):
    inv_id = _invoice(app, owner, 500.0)
    with app.app_context():
        db.add_deposit(owner, 200, created_by="t")
        db.apply_credit(owner, inv_id, 200, created_by="t")
        inv = db.get_invoice(inv_id)
        assert inv["due_amount"] == 300.0
        assert db.owner_credit_balance(owner) == 0.0


def test_applying_credit_lands_in_the_payment_ledger(app, owner):
    """Not a direct write to paid_amount -- it must be a real payment row so it
    is reconcilable and refundable like any other."""
    inv_id = _invoice(app, owner, 500.0)
    with app.app_context():
        db.add_deposit(owner, 500, created_by="t")
        db.apply_credit(owner, inv_id, 500, created_by="t")
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM payments WHERE invoice_id=?",
                         (inv_id,)).fetchone()[0]
        conn.close()
    assert n == 1, "applying credit did not write a payment row"


def test_an_unknown_invoice_is_rejected(app, owner):
    with app.app_context():
        db.add_deposit(owner, 500, created_by="t")
        with pytest.raises(ValueError):
            db.apply_credit(owner, 999999, 100, created_by="t")


# ── refunds ──────────────────────────────────────────────────────────────────

def test_a_refund_lowers_the_balance(app, owner):
    with app.app_context():
        db.add_deposit(owner, 600, created_by="t")
        db.refund_credit(owner, 250, "changed their mind", created_by="t")
        assert db.owner_credit_balance(owner) == 350.0


def test_cannot_refund_more_than_is_held(app, owner):
    with app.app_context():
        db.add_deposit(owner, 100, created_by="t")
        with pytest.raises(ValueError):
            db.refund_credit(owner, 500, created_by="t")
        assert db.owner_credit_balance(owner) == 100.0


def test_the_balance_always_equals_the_sum_of_its_history(app, owner):
    """The invariant the whole design rests on."""
    inv_id = _invoice(app, owner, 300.0)
    with app.app_context():
        db.add_deposit(owner, 1000, created_by="t")
        db.apply_credit(owner, inv_id, 300, created_by="t")
        db.refund_credit(owner, 200, created_by="t")
        entries = db.list_owner_credits(owner)
        assert db.owner_credit_balance(owner) == round(sum(e["amount"] for e in entries), 2)
        assert db.owner_credit_balance(owner) == 500.0


# ── credit is not revenue until it is spent ──────────────────────────────────

def test_a_deposit_alone_is_not_revenue(app, owner):
    with app.app_context():
        conn = db.get_db()
        before = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status!='Cancelled'"
        ).fetchone()[0]
        conn.close()
        db.add_deposit(owner, 5000, created_by="t")
        conn = db.get_db()
        after = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status!='Cancelled'"
        ).fetchone()[0]
        conn.close()
    assert after == before


# ── routes ───────────────────────────────────────────────────────────────────

def test_the_account_page_loads(auth_client, owner):
    assert auth_client.get(f"/finance/owners/{owner}/credit").status_code == 200


def test_recording_a_deposit_through_the_page(auth_client, app, owner):
    auth_client.post(f"/finance/owners/{owner}/credit", data={
        "_csrf_token": get_csrf(auth_client),
        "action": "deposit", "amount": "750", "method": "Cash", "note": "surgery",
    }, follow_redirects=True)
    with app.app_context():
        assert db.owner_credit_balance(owner) == 750.0


def test_over_applying_through_the_route_shows_an_error_not_a_500(auth_client, app, owner):
    inv_id = _invoice(app, owner, 100.0)
    with app.app_context():
        db.add_deposit(owner, 50, created_by="t")
    r = auth_client.post(f"/finance/invoices/{inv_id}/apply-credit", data={
        "_csrf_token": get_csrf(auth_client), "amount": "100",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert db.owner_credit_balance(owner) == 50.0


def test_an_unknown_owner_redirects_rather_than_500s(auth_client):
    assert auth_client.get("/finance/owners/999999/credit").status_code in (200, 302)


# ── the till sees the credit ─────────────────────────────────────────────────

def test_the_invoice_page_offers_held_credit(auth_client, app, owner):
    """A balance nobody is shown at the till may as well not exist -- the real
    failure is taking cash from a client who has already paid."""
    inv_id = _invoice(app, owner, 500.0)
    with app.app_context():
        db.add_deposit(owner, 300, created_by="t")
    html = auth_client.get(f"/finance/invoices/{inv_id}").get_data(as_text=True)
    assert "300.00" in html
    assert f"/finance/invoices/{inv_id}/apply-credit" in html


def test_the_invoice_page_is_unchanged_when_there_is_no_credit(auth_client, app, owner):
    inv_id = _invoice(app, owner, 500.0)
    r = auth_client.get(f"/finance/invoices/{inv_id}")
    assert r.status_code == 200
    assert "apply-credit" not in r.get_data(as_text=True)


def test_a_fully_paid_invoice_does_not_offer_more_credit(auth_client, app, owner):
    inv_id = _invoice(app, owner, 100.0)
    with app.app_context():
        db.add_deposit(owner, 500, created_by="t")
        db.apply_credit(owner, inv_id, 100, created_by="t")
    html = auth_client.get(f"/finance/invoices/{inv_id}").get_data(as_text=True)
    assert "apply-credit" not in html, "offered to apply credit to a settled invoice"
