# -*- coding: utf-8 -*-
"""Taking money, and proving it afterwards.

Before this existed, models.database.add_payment took `method`, `reference` and
`received_by` and threw all three away. It never wrote to the `payments` table
— it only incremented invoices.paid_amount. The system could say an invoice was
paid and could not say by whom, when, or how. There was no record of a failed
attempt, no refund, and nothing stopping a double-clicked button charging twice.

The five cases below are the ones that actually cost a clinic money, so they are
tested first and hardest: duplicates, failures, refunds, cancellations, retries.
"""
from decimal import Decimal

import pytest

import models.database as db
from models import payments
from models.payments import PaymentError


D = Decimal


@pytest.fixture()
def invoice(app):
    """A real unpaid invoice for 250.00."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Payments Test Owner", "01055500001"))
            owner_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO invoices(owner_id, invoice_number, issue_date, "
                "subtotal, total, paid_amount, due_amount, status) "
                "VALUES(?,?,date('now','localtime'),?,?,0,?,'Unpaid')",
                (owner_id, f"PAYTEST-{owner_id}", 250.00, 250.00, 250.00))
            invoice_id = cur.lastrowid
        conn.close()
    return {"invoice_id": invoice_id, "owner_id": owner_id}


def _invoice(app, invoice_id):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
        conn.close()
    return dict(row)


def _ledger(app, invoice_id):
    with app.app_context():
        conn = db.get_db()
        rows = conn.execute(
            "SELECT * FROM payments WHERE invoice_id=? ORDER BY id", (invoice_id,)).fetchall()
        conn.close()
    return [dict(r) for r in rows]


# ── cash, the primary method ─────────────────────────────────────────────────

def test_cash_payment_is_recorded_in_the_LEDGER_not_just_the_total(app, invoice):
    """The whole gap. add_payment moved a number and left no evidence."""
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="cash", idempotency_key="k-cash-1", created_by="reception1")
        payments.capture(intent["id"], actor="reception1")

    rows = _ledger(app, invoice["invoice_id"])
    assert len(rows) == 1, "no ledger row: the payment cannot be reconciled"
    assert D(str(rows[0]["amount"])) == D("250.00")
    assert rows[0]["received_by"] == "reception1", "no record of who took the money"
    assert rows[0]["method"], "no record of how it was paid"

    inv = _invoice(app, invoice["invoice_id"])
    assert inv["status"] == "Paid"
    assert D(str(inv["due_amount"])) == D("0.00")


def test_cash_is_always_offered_even_with_no_gateway_configured(app):
    """A clinic with no merchant account must still be able to take money, and
    cash must keep working when the internet does not."""
    with app.app_context():
        names = [g.name for g in payments.available()]
    assert names and names[0] == "cash", f"cash is not the primary method: {names}"


def test_partial_payments_accumulate_and_settle_exactly(app, invoice):
    """Three instalments on a 250.00 invoice must land on exactly zero due —
    the float-residue bug documented in add_payment left ~14% of instalment
    invoices permanently 'Partial' while the screen showed 0.00."""
    with app.app_context():
        for i, amt in enumerate(("100.00", "100.00", "50.00")):
            intent = payments.create_intent(
                invoice["invoice_id"], invoice["owner_id"], amt,
                gateway="cash", idempotency_key=f"k-part-{i}")
            payments.capture(intent["id"])

    inv = _invoice(app, invoice["invoice_id"])
    assert D(str(inv["paid_amount"])) == D("250.00")
    assert D(str(inv["due_amount"])) == D("0.00")
    assert inv["status"] == "Paid", "settled invoice still shows as Partial"


# ── 1. duplicates ────────────────────────────────────────────────────────────

def test_the_same_payment_cannot_be_taken_twice(app, invoice):
    """A double-clicked Pay button, or a retried request after a timeout."""
    with app.app_context():
        first = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="cash", idempotency_key="same-key")
        second = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="cash", idempotency_key="same-key")
    assert first["id"] == second["id"], "the same key created two payments"

    with app.app_context():
        payments.capture(first["id"])
        payments.capture(second["id"])          # the retry
    assert len(_ledger(app, invoice["invoice_id"])) == 1, "the client was charged twice"


def test_capturing_an_already_captured_payment_is_a_no_op(app, invoice):
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "50.00",
            gateway="cash", idempotency_key="k-recap")
        payments.capture(intent["id"])
        again = payments.capture(intent["id"])
    assert again["status"] == payments.SUCCEEDED
    assert len(_ledger(app, invoice["invoice_id"])) == 1


def test_overpaying_an_invoice_is_refused(app, invoice):
    with app.app_context():
        with pytest.raises(PaymentError, match="still owed"):
            payments.create_intent(invoice["invoice_id"], invoice["owner_id"],
                                   "500.00", gateway="cash", idempotency_key="k-over")


# ── 2. failures ──────────────────────────────────────────────────────────────

def test_a_failed_payment_is_recorded_and_pays_nothing(app, invoice):
    """A failure that leaves no trace is indistinguishable from an attempt that
    never happened — which is what a client disputing a charge relies on."""
    class Failing(payments.Gateway):
        name, label, offline = "failing", "Failing", False
        def configured(self): return True
        def charge(self, intent):
            return {"status": payments.FAILED, "detail": "Card declined"}

    payments.register(Failing())
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="failing", idempotency_key="k-fail")
        result = payments.capture(intent["id"])

    assert result["status"] == payments.FAILED
    assert "declined" in (result["failure_reason"] or "").lower()
    assert _ledger(app, invoice["invoice_id"]) == [], "a failed payment reached the ledger"
    assert _invoice(app, invoice["invoice_id"])["status"] == "Unpaid"


def test_a_gateway_that_explodes_does_not_mark_the_invoice_paid(app, invoice):
    """The dangerous failure: an exception mid-charge must never leave the
    invoice looking settled."""
    class Exploding(payments.Gateway):
        name, label, offline = "exploding", "Exploding", False
        def configured(self): return True
        def charge(self, intent): raise RuntimeError("connection reset")

    payments.register(Exploding())
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="exploding", idempotency_key="k-boom")
        with pytest.raises(PaymentError):
            payments.capture(intent["id"])

    assert _invoice(app, invoice["invoice_id"])["status"] == "Unpaid"
    assert _ledger(app, invoice["invoice_id"]) == []


# ── 3. refunds ───────────────────────────────────────────────────────────────

def test_a_refund_reverses_the_invoice_and_leaves_both_rows(app, invoice):
    """The ledger keeps the payment AND the reversal. An edited row would
    destroy the evidence that money was taken and given back."""
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="cash", idempotency_key="k-ref")
        payments.capture(intent["id"])
        payments.refund(intent["id"], actor="manager", reason="Treatment cancelled")

    rows = _ledger(app, invoice["invoice_id"])
    assert len(rows) == 2, "the refund replaced the payment instead of reversing it"
    assert D(str(rows[0]["amount"])) == D("250.00")
    assert D(str(rows[1]["amount"])) == D("-250.00")

    inv = _invoice(app, invoice["invoice_id"])
    assert D(str(inv["paid_amount"])) == D("0.00")
    assert inv["status"] == "Unpaid", "a fully refunded invoice still says Paid"


def test_a_partial_refund_leaves_the_rest_refundable(app, invoice):
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="cash", idempotency_key="k-partref")
        payments.capture(intent["id"])
        payments.refund(intent["id"], "100.00", actor="manager")
        after = payments.refund(intent["id"], "150.00", actor="manager")
    assert after["status"] == payments.REFUNDED
    assert D(str(_invoice(app, invoice["invoice_id"])["paid_amount"])) == D("0.00")


def test_refunding_more_than_was_paid_is_refused(app, invoice):
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "100.00",
            gateway="cash", idempotency_key="k-overref")
        payments.capture(intent["id"])
        with pytest.raises(PaymentError, match="left to refund"):
            payments.refund(intent["id"], "200.00")


def test_an_unpaid_payment_cannot_be_refunded(app, invoice):
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "100.00",
            gateway="cash", idempotency_key="k-refpending")
        with pytest.raises(PaymentError, match="completed payment"):
            payments.refund(intent["id"])


def test_a_refund_cannot_be_refunded_again(app, invoice):
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "100.00",
            gateway="cash", idempotency_key="k-doubleref")
        payments.capture(intent["id"])
        payments.refund(intent["id"])
        with pytest.raises(PaymentError):
            payments.refund(intent["id"])


# ── 4. cancellation ──────────────────────────────────────────────────────────

def test_a_pending_payment_can_be_cancelled(app, invoice):
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "100.00",
            gateway="cash", idempotency_key="k-cancel")
        after = payments.cancel(intent["id"], actor="reception", reason="Client left")
    assert after["status"] == payments.CANCELLED
    assert _ledger(app, invoice["invoice_id"]) == []


def test_a_captured_payment_cannot_be_cancelled(app, invoice):
    """Cancelling a payment that already took money would silently unpay the
    invoice with no reversal in the ledger. Refund is the correct route."""
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "100.00",
            gateway="cash", idempotency_key="k-cancel2")
        payments.capture(intent["id"])
        with pytest.raises(PaymentError, match="pending"):
            payments.cancel(intent["id"])


def test_an_invoice_that_is_cancelled_refuses_new_payments(app, invoice):
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE invoices SET status='Cancelled' WHERE id=?",
                         (invoice["invoice_id"],))
        conn.close()
        with pytest.raises(PaymentError, match="cancelled"):
            payments.create_intent(invoice["invoice_id"], invoice["owner_id"],
                                   "10.00", gateway="cash", idempotency_key="k-canc-inv")


# ── 5. traceability ──────────────────────────────────────────────────────────

def test_every_step_leaves_an_audit_trail(app, invoice):
    """What a dispute or a chargeback is actually answered with."""
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="cash", idempotency_key="k-audit", created_by="reception1")
        payments.capture(intent["id"], actor="reception1")
        payments.refund(intent["id"], actor="manager", reason="Duplicate charge")
        trail = [e["event"] for e in payments.events(intent["id"])]
    assert trail == ["created", "succeeded", "refunded"], trail


def test_an_illegal_status_change_is_refused(app, invoice):
    """The state machine, not a convention someone can forget."""
    with app.app_context():
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "10.00",
            gateway="cash", idempotency_key="k-sm")
        payments.cancel(intent["id"])
        conn = db.get_db()
        with pytest.raises(PaymentError, match="cannot become"):
            payments._set_status(conn, intent["id"], payments.SUCCEEDED)
        conn.close()


def test_zero_and_negative_payments_are_refused(app, invoice):
    with app.app_context():
        for bad in ("0", "-50.00"):
            with pytest.raises(PaymentError, match="greater than zero"):
                payments.create_intent(invoice["invoice_id"], invoice["owner_id"],
                                       bad, gateway="cash",
                                       idempotency_key=f"k-bad-{bad}")


def test_an_unknown_gateway_is_refused_before_anything_is_written(app, invoice):
    with app.app_context():
        with pytest.raises(PaymentError, match="Unknown payment method"):
            payments.create_intent(invoice["invoice_id"], invoice["owner_id"],
                                   "10.00", gateway="bitcoin",
                                   idempotency_key="k-unknown")
        assert payments.history(invoice["invoice_id"]) == []


# ── the UI is driven by the registry ─────────────────────────────────────────

def test_the_invoice_screen_offers_the_registered_gateways(app, client, invoice):
    """"Configurable so more gateways can be added later" only means something
    if the UI follows the registry. This list used to be five hardcoded
    <option> tags, so a newly registered gateway was unreachable no matter how
    complete its implementation was."""
    with client.session_transaction() as s:
        s["user"] = {"id": 1, "username": "admin", "full_name": "Admin",
                     "role": "super_admin"}
        s["lang"] = "en"
    html = client.get(f"/finance/invoices/{invoice['invoice_id']}").get_data(as_text=True)

    import re
    block = re.search(r'<select name="method".*?</select>', html, re.S)
    assert block, "no payment-method selector on the invoice screen"
    values = re.findall(r'value="([^"]+)"', block.group(0))

    with app.app_context():
        expected = [g.name for g in payments.available()]
    assert values == expected, f"screen offers {values}, registry has {expected}"
    assert values[0] == "cash", "cash is not the first option"


def test_an_unconfigured_online_gateway_is_not_offered_to_staff(app, client, invoice):
    """Offering a method that cannot complete wastes a client's time at the
    counter and strands the invoice as pending."""
    with client.session_transaction() as s:
        s["user"] = {"id": 1, "username": "admin", "full_name": "Admin",
                     "role": "super_admin"}
        s["lang"] = "en"
    html = client.get(f"/finance/invoices/{invoice['invoice_id']}").get_data(as_text=True)
    assert 'value="paymob"' not in html, \
        "Paymob was offered with no keys configured"


def test_insurance_settlements_are_not_recorded_as_cash(app, invoice):
    """The screen has always offered Insurance. With no matching gateway the
    alias fell through to cash, and the clinic would look for that money in a
    drawer it was never in."""
    with app.app_context():
        assert payments.gateway_for_method("Insurance") == "insurance"
        intent = payments.create_intent(
            invoice["invoice_id"], invoice["owner_id"], "250.00",
            gateway="insurance", idempotency_key="k-ins", created_by="reception")
        payments.capture(intent["id"], actor="reception")
    rows = _ledger(app, invoice["invoice_id"])
    assert rows[0]["method"] == "Insurance", f"recorded as {rows[0]['method']}"


def test_payments_work_without_a_flask_app(app, invoice):
    """Seeders, cron jobs and migrations take payments outside create_app().

    Gateways were registered only by create_app(), so `add_payment(...,
    method="Cash")` from a script raised "Unknown payment method: 'cash'".
    Caught by the PostgreSQL suite, which calls db.add_payment directly.
    """
    import models.payments as p
    saved = dict(p._REGISTRY)
    p._REGISTRY.clear()                     # simulate a bare process
    try:
        with app.app_context():
            db.add_payment(invoice["invoice_id"], invoice["owner_id"], 250.00,
                           method="Cash", received_by="seeder")
        rows = _ledger(app, invoice["invoice_id"])
        assert len(rows) == 1 and rows[0]["method"] == "Cash"
    finally:
        p._REGISTRY.clear()
        p._REGISTRY.update(saved)
