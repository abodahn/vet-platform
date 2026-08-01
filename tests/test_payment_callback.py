# -*- coding: utf-8 -*-
"""The payment callback endpoint — the URL a provider posts to.

Without this route the online flow can never finish: the client pays, the
provider calls back, nothing listens, and the invoice sits "pending" forever
while the money has actually moved. A gateway with no callback endpoint is a
decorative feature, which is the exact failure pattern this codebase has
produced repeatedly.

It is unauthenticated because a payment provider is not a logged-in member of
staff. Unauthenticated is not untrusted: nothing is believed until the
signature verifies. Every test here is about that boundary.
"""
import json

import pytest

from models import payments
from models.payments import PaymentError


@pytest.fixture()
def stub_gateway():
    """A gateway whose callback verification we control exactly."""
    class Stub(payments.Gateway):
        name, label, offline = "stubpay", "Stub", False
        accept = True
        def configured(self): return True
        def charge(self, intent):
            return {"status": payments.PENDING, "gateway_ref": f"REF-{intent['id']}"}
        def verify_callback(self, payload, headers):
            if not self.accept:
                raise PaymentError("Callback signature did not verify.")
            return {"gateway_ref": payload.get("ref", ""),
                    "status": payments.SUCCEEDED if payload.get("paid") else payments.FAILED}
    gw = Stub()
    payments.register(gw)
    return gw


@pytest.fixture()
def pending(app, stub_gateway):
    """An invoice with a pending online payment awaiting its callback."""
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                               ("Callback Owner", "01055500009"))
            owner_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO invoices(owner_id, invoice_number, issue_date, subtotal,"
                " total, paid_amount, due_amount, status)"
                " VALUES(?,?,date('now','localtime'),?,?,0,?,'Unpaid')",
                (owner_id, f"CB-{owner_id}", 300.00, 300.00, 300.00))
            invoice_id = cur.lastrowid
        conn.close()
        intent = payments.create_intent(invoice_id, owner_id, "300.00",
                                        gateway="stubpay",
                                        idempotency_key=f"cb-{invoice_id}")
        payments.capture(intent["id"])
    return {"intent_id": intent["id"], "invoice_id": invoice_id,
            "ref": f"REF-{intent['id']}"}


def _status(app, invoice_id):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT status, paid_amount FROM invoices WHERE id=?",
                           (invoice_id,)).fetchone()
        conn.close()
    return dict(row)


def _post(client, gateway, payload):
    return client.post(f"/api/public/payments/callback/{gateway}",
                       data=json.dumps(payload), content_type="application/json")


# ── the happy path ───────────────────────────────────────────────────────────

def test_a_verified_success_callback_settles_the_invoice(app, client, pending):
    r = _post(client, "stubpay", {"ref": pending["ref"], "paid": True})
    assert r.status_code == 200
    assert r.get_json()["status"] == payments.SUCCEEDED
    assert _status(app, pending["invoice_id"])["status"] == "Paid"


def test_the_endpoint_is_reachable_without_logging_in(client, pending):
    """Behind @login_required it would 302 to the login page and every online
    payment would hang as pending forever."""
    r = _post(client, "stubpay", {"ref": pending["ref"], "paid": True})
    assert r.status_code != 302, "the provider was redirected to a login page"


# ── the boundary ─────────────────────────────────────────────────────────────

def test_an_unverified_callback_pays_nothing(app, client, pending, stub_gateway):
    """Anyone can POST here. Only a verified signature may move money."""
    stub_gateway.accept = False
    r = _post(client, "stubpay", {"ref": pending["ref"], "paid": True})
    assert r.status_code == 400
    assert _status(app, pending["invoice_id"])["status"] == "Unpaid", \
        "a forged callback marked the invoice paid"


def test_a_rejected_callback_does_not_leak_why(client, pending, stub_gateway):
    """Telling a caller which part of their signature was wrong helps them
    forge a better one."""
    stub_gateway.accept = False
    body = _post(client, "stubpay", {"ref": pending["ref"], "paid": True}).get_json()
    assert "signature" not in json.dumps(body).lower()


def test_a_rejected_callback_returns_400_not_500(client, pending, stub_gateway):
    """A 500 makes providers retry a callback that will never be accepted."""
    stub_gateway.accept = False
    assert _post(client, "stubpay", {"ref": pending["ref"], "paid": True}).status_code == 400


def test_a_callback_for_an_unknown_reference_is_refused(client, pending):
    r = _post(client, "stubpay", {"ref": "REF-does-not-exist", "paid": True})
    assert r.status_code == 400


def test_an_unknown_gateway_is_refused(client):
    assert _post(client, "notagateway", {"ref": "x", "paid": True}).status_code == 400


def test_a_declined_callback_leaves_the_invoice_unpaid(app, client, pending):
    r = _post(client, "stubpay", {"ref": pending["ref"], "paid": False})
    assert r.status_code == 200
    assert r.get_json()["status"] == payments.FAILED
    assert _status(app, pending["invoice_id"])["status"] == "Unpaid"


# ── replays, which providers do routinely ────────────────────────────────────

def test_a_REPLAYED_callback_does_not_pay_the_invoice_twice(app, client, pending):
    """Providers retry callbacks they believe were missed. A replay must be a
    no-op, not a second payment."""
    import models.database as db
    for _ in range(3):
        assert _post(client, "stubpay", {"ref": pending["ref"], "paid": True}).status_code == 200

    with app.app_context():
        conn = db.get_db()
        rows = conn.execute("SELECT COUNT(*) c FROM payments WHERE invoice_id=?",
                            (pending["invoice_id"],)).fetchone()["c"]
        conn.close()
    assert rows == 1, f"a replayed callback wrote {rows} ledger rows"
    assert _status(app, pending["invoice_id"])["status"] == "Paid"


def test_a_LATE_failure_callback_cannot_unpay_a_settled_invoice(app, client, pending):
    """Out-of-order delivery is real. A stale 'failed' arriving after a
    successful capture must not reverse a payment that actually happened —
    that is what a refund is for, and it leaves a ledger entry."""
    _post(client, "stubpay", {"ref": pending["ref"], "paid": True})
    _post(client, "stubpay", {"ref": pending["ref"], "paid": False})
    assert _status(app, pending["invoice_id"])["status"] == "Paid"
