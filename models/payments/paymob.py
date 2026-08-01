# -*- coding: utf-8 -*-
"""Paymob — online cards and mobile wallets, Egypt.

WHY PAYMOB

It is the gateway an Egyptian veterinary clinic can actually use: local cards,
Vodafone/Etisalat/Orange wallets, Fawry and instalments, settlement to an
Egyptian bank account, and a free sandbox with no upfront cost. Stripe does not
onboard Egyptian entities for payouts, and Fawry direct is heavier to integrate
than a small clinic needs.

WHAT IS NOT VERIFIED

There is no Paymob account yet, so this has NOT been run against the sandbox.
The flow below follows the documented Intention API, and everything testable
without a network is tested. Run scripts/verify_paymob.py once with sandbox
keys to settle the two remaining unknowns:

  1. the exact field set and ordering the HMAC is computed over — still
     TODO(sandbox) below, and the script prints a field-by-field comparison
     against a real callback when it does not match
  2. the Authorization scheme on the intention call — no longer a code TODO.
     Probing the live endpoint with a fake key is useless: Token, Bearer,
     Api-Key and no header at all all return the same generic 401, so the
     error cannot distinguish them. It is now PAYMOB_AUTH_SCHEME, and the
     script tries both and tells you which to set.

Getting HMAC wrong fails CLOSED here — an unverified callback is refused and
no invoice is marked paid — so the failure mode is "payments do not complete",
not "anyone can mark invoices paid".

CONFIGURATION (environment)

    PAYMOB_SECRET_KEY     server-side key for creating intentions
    PAYMOB_PUBLIC_KEY     public key used in the checkout URL
    PAYMOB_HMAC_SECRET    secret the callback signature is verified with
    PAYMOB_BASE           optional; defaults to https://accept.paymob.com
    PAYMOB_AUTH_SCHEME    optional; "Token" (default) or "Bearer"

Unset means the gateway simply does not appear in the payment options. Cash
keeps working regardless — see models/payments/cash.py.
"""
import hashlib
import hmac
import json
import logging
import os
import urllib.request
from decimal import Decimal

from models.money import to_decimal
from models.payments import (Gateway, PaymentError, PENDING, SUCCEEDED, FAILED)

logger = logging.getLogger(__name__)

# The subset of callback fields Paymob signs, in the order it signs them.
# TODO(sandbox): confirm against one real callback before going live. A
# mismatch here rejects every callback rather than accepting a forged one.
_HMAC_FIELDS = (
    "amount_cents", "created_at", "currency", "error_occured", "has_parent_transaction",
    "id", "integration_id", "is_3d_secure", "is_auth", "is_capture",
    "is_refunded", "is_standalone_payment", "is_voided", "order.id",
    "owner", "pending", "source_data.pan", "source_data.sub_type",
    "source_data.type", "success",
)


class PaymobGateway(Gateway):
    name = "paymob"
    label = "Card / Wallet"
    label_ar = "بطاقة / محفظة"
    offline = False

    # ── configuration ────────────────────────────────────────────────────────

    @property
    def _secret(self) -> str:
        return os.environ.get("PAYMOB_SECRET_KEY", "").strip()

    @property
    def _public(self) -> str:
        return os.environ.get("PAYMOB_PUBLIC_KEY", "").strip()

    @property
    def _hmac_secret(self) -> str:
        return os.environ.get("PAYMOB_HMAC_SECRET", "").strip()

    @property
    def _base(self) -> str:
        return os.environ.get("PAYMOB_BASE", "https://accept.paymob.com").rstrip("/")

    def configured(self) -> bool:
        """All three or none.

        A half-configured gateway is the dangerous state: it would appear in the
        payment options, take the client through a checkout, and then be unable
        to verify the callback that says they paid.
        """
        return bool(self._secret and self._public and self._hmac_secret)

    # ── charging ─────────────────────────────────────────────────────────────

    def charge(self, intent: dict) -> dict:
        """Create an intention and hand back a checkout URL.

        Returns PENDING, not SUCCEEDED: the client has not paid yet, they have
        been sent somewhere to pay. Only the verified callback moves it on.
        Returning SUCCEEDED here would mark invoices paid for anyone who merely
        opened the checkout page.
        """
        if not self.configured():
            raise PaymentError(
                "Online payment is not set up. Ask an administrator to add the "
                "Paymob keys, or take this payment in cash.")

        # Paymob works in the smallest unit. Sending 120.5 instead of 12050
        # undercharges by a factor of 100, so the conversion is explicit and
        # integer-only.
        piastres = int((to_decimal(intent["amount"]) * 100).to_integral_value())

        payload = {
            "amount": piastres,
            "currency": intent.get("currency") or "EGP",
            "payment_methods": _integration_ids(),
            "items": [{
                "name": f"Invoice {intent['invoice_id']}",
                "amount": piastres,
                "quantity": 1,
            }],
            "billing_data": _billing(intent),
            # Our own key, so a callback can be tied back to this attempt even
            # if the response is lost in transit.
            "special_reference": intent["idempotency_key"],
        }
        notify = os.environ.get("PAYMOB_NOTIFICATION_URL", "").strip()
        redirect = os.environ.get("PAYMOB_REDIRECT_URL", "").strip()
        if notify:
            payload["notification_url"] = notify
        if redirect:
            payload["redirection_url"] = redirect

        data = self._post("/v1/intention/", payload)
        client_secret = data.get("client_secret")
        if not client_secret:
            raise PaymentError("Paymob did not return a checkout session.")

        return {
            "status": PENDING,
            "gateway_ref": str(data.get("id") or client_secret),
            "detail": "Awaiting the customer",
            "checkout_url": (f"{self._base}/unifiedcheckout/"
                             f"?publicKey={self._public}&clientSecret={client_secret}"),
        }

    def refund(self, intent: dict, amount: Decimal) -> dict:
        if not self.configured():
            raise PaymentError("Paymob is not configured.")
        piastres = int((to_decimal(amount) * 100).to_integral_value())
        data = self._post("/api/acceptance/void_refund/refund", {
            "transaction_id": intent.get("gateway_ref"),
            "amount_cents": piastres,
        })
        ok = bool(data.get("success", False))
        return {"status": SUCCEEDED if ok else FAILED,
                "gateway_ref": str(data.get("id") or ""),
                "detail": data.get("message") or ("Refunded" if ok else "Refund declined")}

    # ── callbacks ────────────────────────────────────────────────────────────

    def verify_callback(self, payload: dict, headers: dict) -> dict:
        """Authenticate a Paymob callback, then say what it means.

        Fails CLOSED at every step. A callback marks an invoice PAID, so an
        unauthenticated one is free treatment for anyone who can find the URL.
        """
        if not self._hmac_secret:
            raise PaymentError("Paymob HMAC secret is not configured.")

        obj = payload.get("obj") if isinstance(payload.get("obj"), dict) else payload
        received = (payload.get("hmac") or headers.get("hmac") or "").strip().lower()
        if not received:
            raise PaymentError("Callback carried no signature.")

        expected = self.compute_hmac(obj)
        # Constant-time: a plain == leaks how much of the signature was right,
        # one byte at a time, to anyone willing to retry.
        if not hmac.compare_digest(expected, received):
            logger.warning("Paymob callback signature mismatch for order %s",
                           (obj.get("order") or {}).get("id"))
            raise PaymentError("Callback signature did not verify.")

        success = bool(obj.get("success")) and not bool(obj.get("error_occured"))
        return {
            "gateway_ref": str(obj.get("id") or ""),
            "status": SUCCEEDED if success else FAILED,
            "detail": obj.get("data", {}).get("message") if isinstance(
                obj.get("data"), dict) else ("Paid" if success else "Declined"),
        }

    def compute_hmac(self, obj: dict) -> str:
        """SHA-512 over the signed fields, concatenated in Paymob's order.

        Separated out and made public so it can be exercised by tests and
        checked against one real sandbox callback without touching anything
        else. TODO(sandbox): confirm _HMAC_FIELDS matches what Paymob signs.
        """
        parts = []
        for field in _HMAC_FIELDS:
            value = obj
            for piece in field.split("."):
                value = (value or {}).get(piece) if isinstance(value, dict) else None
            # Paymob serialises booleans lowercase and missing values as empty.
            if isinstance(value, bool):
                parts.append("true" if value else "false")
            elif value is None:
                parts.append("")
            else:
                parts.append(str(value))
        return hmac.new(self._hmac_secret.encode(),
                        "".join(parts).encode(), hashlib.sha512).hexdigest()

    # ── transport ────────────────────────────────────────────────────────────

    def _post(self, path: str, payload: dict) -> dict:
        url = f"{self._base}{path}"
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={
                # Paymob's docs show `Token <secret>` for the Intention API;
                # some SDKs send `Bearer`. Made configurable rather than left as
                # a code TODO because it cannot be settled without a real key:
                # probing the live endpoint with a fake one returns the same
                # generic 401 for Token, Bearer, Api-Key AND no header at all,
                # so the error does not distinguish them.
                # scripts/verify_paymob.py tries both and reports which works.
                "Authorization": f"{_auth_scheme()} {self._secret}",
                "Content-Type": "application/json",
            })
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode() or "{}")
        except urllib.error.HTTPError as exc:
            detail = (exc.read() or b"").decode()[:300]
            logger.error("Paymob %s -> HTTP %s: %s", path, exc.code, detail)
            raise PaymentError(
                "The payment provider rejected the request. "
                "Nothing was charged.") from exc
        except Exception as exc:
            logger.exception("Paymob %s unreachable", path)
            raise PaymentError(
                "Could not reach the payment provider. Nothing was charged. "
                "You can take this payment in cash instead.") from exc


def _auth_scheme() -> str:
    """Authorization scheme for the Intention API — "Token" or "Bearer".

    Overridable with PAYMOB_AUTH_SCHEME so switching it is a config change, not
    a code change made under pressure on the day a clinic's payments are down.
    """
    return os.environ.get("PAYMOB_AUTH_SCHEME", "Token").strip() or "Token"


def _integration_ids() -> list:
    """Which Paymob methods to offer, from PAYMOB_INTEGRATION_IDS.

    Empty means "everything enabled on the account", which is the sane default
    for a clinic that has just signed up.
    """
    raw = os.environ.get("PAYMOB_INTEGRATION_IDS", "").strip()
    if not raw:
        return []
    out = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
        elif part:
            out.append(part)          # slugs like "apple_pay"
    return out


def _billing(intent: dict) -> dict:
    """Paymob rejects an intention with blank billing fields, so unknown values
    are sent as 'NA' — its documented placeholder — rather than empty strings.
    A clinic often has nothing but a phone number for a walk-in client."""
    import models.database as db
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT full_name, phone, email FROM owners WHERE id=?",
            (intent["owner_id"],)).fetchone()
    finally:
        conn.close()
    name = ((row["full_name"] if row else "") or "Client").strip()
    first, _, last = name.partition(" ")
    return {
        "first_name": first or "Client",
        "last_name": last or "NA",
        "phone_number": ((row["phone"] if row else "") or "NA").strip() or "NA",
        "email": ((row["email"] if row else "") or "").strip() or "na@example.com",
        "street": "NA", "building": "NA", "floor": "NA", "apartment": "NA",
        "city": "NA", "state": "NA", "country": "EG", "postal_code": "NA",
    }
