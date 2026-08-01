# -*- coding: utf-8 -*-
"""Paymob — everything verifiable without a merchant account.

There is no Paymob account yet, so the live flow is unverified and says so in
models/payments/paymob.py. What IS testable is the part that decides whether an
invoice gets marked paid, and that is exactly the part worth testing: a callback
handler that accepts an unsigned request is free treatment for anyone who finds
the URL.

Every test here is about failing CLOSED.
"""
import hashlib
import hmac as hmaclib
import json

import pytest

from models import payments
from models.payments import PaymentError
from models.payments.paymob import PaymobGateway


SECRET = "test_hmac_secret"


@pytest.fixture()
def gw(monkeypatch):
    monkeypatch.setenv("PAYMOB_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("PAYMOB_PUBLIC_KEY", "pk_test_x")
    monkeypatch.setenv("PAYMOB_HMAC_SECRET", SECRET)
    return PaymobGateway()


def _signed(gw, **overrides):
    obj = {
        "amount_cents": 25000, "created_at": "2026-08-01T10:00:00", "currency": "EGP",
        "error_occured": False, "has_parent_transaction": False, "id": 987654,
        "integration_id": 111, "is_3d_secure": True, "is_auth": False,
        "is_capture": False, "is_refunded": False, "is_standalone_payment": True,
        "is_voided": False, "order": {"id": 555}, "owner": 42, "pending": False,
        "source_data": {"pan": "2346", "sub_type": "MasterCard", "type": "card"},
        "success": True,
    }
    obj.update(overrides)
    return {"obj": obj, "hmac": gw.compute_hmac(obj)}


# ── configuration ────────────────────────────────────────────────────────────

def test_unconfigured_paymob_is_not_offered(monkeypatch):
    for var in ("PAYMOB_SECRET_KEY", "PAYMOB_PUBLIC_KEY", "PAYMOB_HMAC_SECRET"):
        monkeypatch.delenv(var, raising=False)
    assert PaymobGateway().configured() is False
    assert "paymob" not in [g.name for g in payments.available()]


def test_HALF_configured_paymob_is_not_offered(monkeypatch):
    """The dangerous state: it would appear in the payment options, send a
    client through checkout, and then be unable to verify the callback saying
    they paid."""
    monkeypatch.setenv("PAYMOB_SECRET_KEY", "sk_test_x")
    monkeypatch.setenv("PAYMOB_PUBLIC_KEY", "pk_test_x")
    monkeypatch.delenv("PAYMOB_HMAC_SECRET", raising=False)
    assert PaymobGateway().configured() is False, \
        "a gateway that cannot verify its own callbacks was offered to clinics"


def test_charging_without_configuration_refuses_and_points_at_cash(monkeypatch):
    monkeypatch.delenv("PAYMOB_SECRET_KEY", raising=False)
    with pytest.raises(PaymentError, match="cash"):
        PaymobGateway().charge({"id": 1, "invoice_id": 1, "owner_id": 1,
                                "amount": "10.00", "idempotency_key": "k"})


# ── callback verification: the part that marks invoices paid ─────────────────

def test_a_correctly_signed_success_callback_is_accepted(gw):
    result = gw.verify_callback(_signed(gw), {})
    assert result["status"] == payments.SUCCEEDED
    assert result["gateway_ref"] == "987654"


def test_an_unsigned_callback_is_refused(gw):
    """Anyone who can POST to the URL would otherwise mark invoices paid."""
    payload = _signed(gw)
    payload.pop("hmac")
    with pytest.raises(PaymentError, match="no signature"):
        gw.verify_callback(payload, {})


def test_a_forged_signature_is_refused(gw):
    payload = _signed(gw)
    payload["hmac"] = "0" * 128
    with pytest.raises(PaymentError, match="did not verify"):
        gw.verify_callback(payload, {})


def test_a_TAMPERED_amount_invalidates_the_signature(gw):
    """The attack that matters: take a real 10 EGP callback and edit it to
    settle a 5,000 EGP invoice."""
    payload = _signed(gw)
    payload["obj"]["amount_cents"] = 1
    with pytest.raises(PaymentError, match="did not verify"):
        gw.verify_callback(payload, {})


def test_a_signature_from_a_DIFFERENT_secret_is_refused(gw, monkeypatch):
    payload = _signed(gw)
    monkeypatch.setenv("PAYMOB_HMAC_SECRET", "someone_elses_secret")
    with pytest.raises(PaymentError, match="did not verify"):
        PaymobGateway().verify_callback(payload, {})


def test_a_declined_transaction_is_reported_as_failed_not_paid(gw):
    result = gw.verify_callback(_signed(gw, success=False), {})
    assert result["status"] == payments.FAILED


def test_error_occured_overrides_success(gw):
    """Paymob can send success=true alongside error_occured=true. Treating that
    as payment would mark a failed transaction paid."""
    result = gw.verify_callback(_signed(gw, success=True, error_occured=True), {})
    assert result["status"] == payments.FAILED


def test_verification_refuses_when_no_secret_is_configured(monkeypatch):
    """Never fall open just because configuration is missing."""
    monkeypatch.delenv("PAYMOB_HMAC_SECRET", raising=False)
    with pytest.raises(PaymentError, match="not configured"):
        PaymobGateway().verify_callback({"obj": {}, "hmac": "x"}, {})


# ── the HMAC itself ──────────────────────────────────────────────────────────

def test_hmac_is_sha512_over_the_signed_fields(gw):
    """Pins the algorithm so a refactor cannot quietly weaken it. The FIELD
    LIST is still TODO(sandbox) — it needs one real callback to confirm — but a
    wrong list rejects genuine callbacks rather than accepting forged ones."""
    obj = _signed(gw)["obj"]
    expected = hmaclib.new(SECRET.encode(),
                           "".join([
                               "25000", "2026-08-01T10:00:00", "EGP", "false",
                               "false", "987654", "111", "true", "false",
                               "false", "false", "true", "false", "555", "42",
                               "false", "2346", "MasterCard", "card", "true",
                           ]).encode(), hashlib.sha512).hexdigest()
    assert gw.compute_hmac(obj) == expected


def test_booleans_serialise_lowercase(gw):
    """Python's str(True) is 'True'; Paymob signs 'true'. Getting this wrong
    rejects every genuine callback."""
    a = gw.compute_hmac(_signed(gw, success=True)["obj"])
    b = gw.compute_hmac(_signed(gw, success=False)["obj"])
    assert a != b


def test_a_missing_nested_field_does_not_crash(gw):
    """A wallet payment has no source_data.pan. A KeyError here would 500 the
    callback endpoint and Paymob would retry it forever."""
    obj = _signed(gw)["obj"]
    del obj["source_data"]
    assert len(gw.compute_hmac(obj)) == 128


# ── amounts ──────────────────────────────────────────────────────────────────

def test_amounts_are_converted_to_piastres(gw, monkeypatch):
    """Paymob works in the smallest unit. Sending 250.00 instead of 25000
    undercharges by a factor of one hundred."""
    captured = {}

    def fake_post(path, payload):
        captured.update(payload)
        return {"client_secret": "cs_test", "id": 4242}

    monkeypatch.setattr(gw, "_post", fake_post)
    monkeypatch.setattr("models.payments.paymob._billing", lambda intent: {})
    result = gw.charge({"id": 1, "invoice_id": 7, "owner_id": 3,
                        "amount": "250.00", "currency": "EGP",
                        "idempotency_key": "k-1"})
    assert captured["amount"] == 25000, f"sent {captured['amount']} instead of 25000"
    assert isinstance(captured["amount"], int)
    assert result["status"] == payments.PENDING, \
        "returning SUCCEEDED here marks invoices paid for anyone who merely opens checkout"
    assert "clientSecret=cs_test" in result["checkout_url"]


# ── the authorization scheme, which is config not code ───────────────────────

def test_auth_scheme_defaults_to_Token_and_is_overridable(monkeypatch):
    """Paymob's docs say `Token <secret>`; some SDKs send `Bearer`. It cannot
    be settled without a real key — probing the live endpoint with a fake one
    returns the same generic 401 for Token, Bearer, Api-Key and no header at
    all — so it is an environment variable rather than a code edit made under
    pressure on the day a clinic's payments are down."""
    from models.payments.paymob import _auth_scheme
    monkeypatch.delenv("PAYMOB_AUTH_SCHEME", raising=False)
    assert _auth_scheme() == "Token"
    monkeypatch.setenv("PAYMOB_AUTH_SCHEME", "Bearer")
    assert _auth_scheme() == "Bearer"
    monkeypatch.setenv("PAYMOB_AUTH_SCHEME", "")
    assert _auth_scheme() == "Token", "an empty value must not send a bare secret"


def test_the_auth_scheme_reaches_the_request_header(gw, monkeypatch):
    seen = {}

    class _Resp:
        status = 200
        def read(self): return b'{"client_secret":"cs","id":1}'
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        seen["auth"] = req.headers.get("Authorization")
        return _Resp()

    monkeypatch.setenv("PAYMOB_AUTH_SCHEME", "Bearer")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("models.payments.paymob._billing", lambda intent: {})
    gw.charge({"id": 1, "invoice_id": 1, "owner_id": 1, "amount": "1.00",
               "currency": "EGP", "idempotency_key": "k"})
    assert seen["auth"] == "Bearer sk_test_x", seen["auth"]
