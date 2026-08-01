#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Confirm the two unverified things about the Paymob integration.

models/payments/paymob.py carries two TODO(sandbox) markers, because the
integration was written from documentation and never run against a real
account. Both fail CLOSED — a wrong HMAC field list rejects genuine callbacks
rather than accepting forged ones — so the risk is "online payments do not
complete", never "anyone can mark invoices paid". This script closes both.

USAGE
-----
1. Create a free Paymob account and open the TEST/sandbox environment.
2. Take the Secret Key, Public Key and HMAC secret from Settings.
3. Set them and run this:

       set PAYMOB_SECRET_KEY=sk_test_...
       set PAYMOB_PUBLIC_KEY=pk_test_...
       set PAYMOB_HMAC_SECRET=...
       python scripts\\verify_paymob.py

   Step 1 runs immediately. Step 2 needs one real test payment — the script
   prints a checkout URL, you pay with Paymob's test card, and then you paste
   the callback JSON back in.

WHAT IT PROVES
--------------
  Step 1  the intention call is accepted -> the Authorization scheme is right
  Step 2  a real callback verifies      -> _HMAC_FIELDS matches what Paymob signs

Nothing here writes to the clinic database. It is a connectivity and signature
check, not a test of the payment flow — tests/test_payments.py covers that.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FLASK_ENV", "development")
os.environ.setdefault("POSTGRES_DSN", "")
os.environ.setdefault("PLATFORM_ADMIN_PASS", "x")

from models.payments.paymob import PaymobGateway, _HMAC_FIELDS   # noqa: E402
from models.payments import PaymentError                          # noqa: E402


def main() -> int:
    gw = PaymobGateway()
    if not gw.configured():
        print("Set PAYMOB_SECRET_KEY, PAYMOB_PUBLIC_KEY and PAYMOB_HMAC_SECRET first.")
        print("All three are required — a gateway that cannot verify its own")
        print("callbacks must never be offered to a clinic.")
        return 2

    print(f"base: {gw._base}\n")

    # ── Step 1: does the intention call work at all? ─────────────────────────
    print("STEP 1  creating a 1.00 EGP intention")
    fake_intent = {
        "id": 0, "invoice_id": 0, "owner_id": 0,
        "amount": "1.00", "currency": "EGP",
        "idempotency_key": "verify-paymob-script",
    }
    # _billing() reads the owners table; this script has no database, so stub it
    # with Paymob's documented placeholders.
    import models.payments.paymob as mod
    mod._billing = lambda intent: {
        "first_name": "Test", "last_name": "Client",
        "phone_number": "01000000000", "email": "test@example.com",
        "street": "NA", "building": "NA", "floor": "NA", "apartment": "NA",
        "city": "NA", "state": "NA", "country": "EG", "postal_code": "NA",
    }

    # Try both documented schemes rather than making the reader edit code and
    # re-run. Probing the live endpoint with a fake key is no help — Token,
    # Bearer, Api-Key and no header at all all return the same generic 401 —
    # so this is the first point at which the question can actually be answered.
    result = None
    for scheme in ("Token", "Bearer"):
        os.environ["PAYMOB_AUTH_SCHEME"] = scheme
        try:
            result = gw.charge(fake_intent)
            working_scheme = scheme
            break
        except PaymentError as exc:
            print(f"  {scheme}: rejected ({exc})")

    if result is None:
        print("\n  Neither scheme worked. Check the key is the SECRET key (not the")
        print("  public one) and that it belongs to the environment in PAYMOB_BASE.")
        return 1

    print(f"  OK — accepted with 'Authorization: {working_scheme} <secret>'.")
    if working_scheme != "Token":
        print(f"  Set PAYMOB_AUTH_SCHEME={working_scheme} in your environment.")
    print(f"  Amount sent: 100 piastres (1.00 EGP). Confirm that on the page.")
    print(f"\n  Pay this with a Paymob TEST card:\n\n    {result['checkout_url']}\n")

    # ── Step 2: does a real callback verify? ─────────────────────────────────
    print("STEP 2  verifying a real callback signature")
    print("  After paying, copy the callback body Paymob posted to your")
    print("  notification URL (or the transaction JSON from the dashboard) and")
    print("  paste it here. Finish with a blank line.\n")
    lines = []
    for line in sys.stdin:
        if not line.strip():
            break
        lines.append(line)
    raw = "".join(lines).strip()
    if not raw:
        print("  SKIPPED — no callback pasted. _HMAC_FIELDS stays unconfirmed.")
        return 0

    try:
        payload = json.loads(raw)
    except ValueError as exc:
        print(f"  Could not parse that as JSON: {exc}")
        return 1

    obj = payload.get("obj") if isinstance(payload.get("obj"), dict) else payload
    received = (payload.get("hmac") or "").strip().lower()
    computed = gw.compute_hmac(obj)

    if not received:
        print("  The pasted payload has no 'hmac' key — paste the whole callback body.")
        return 1

    if computed == received:
        print("  OK — the signature verified.")
        print("  _HMAC_FIELDS matches what Paymob signs. Remove both TODO(sandbox)")
        print("  markers in models/payments/paymob.py.")
        return 0

    print("  MISMATCH — _HMAC_FIELDS does not match what Paymob signed.")
    print(f"    expected {computed[:32]}...")
    print(f"    received {received[:32]}...")
    print("\n  This is the failure the TODO warns about, and it fails CLOSED:")
    print("  genuine callbacks are rejected, forged ones cannot get through.")
    print("\n  To fix, compare the fields Paymob actually signed against the list")
    print("  in models/payments/paymob.py. Current list, in order:\n")
    for field in _HMAC_FIELDS:
        value = obj
        for piece in field.split("."):
            value = (value or {}).get(piece) if isinstance(value, dict) else None
        mark = " " if value is not None else "?"   # '?' = absent from the callback
        print(f"    {mark} {field:<28} {value!r}")
    print("\n  Fields present in the callback but NOT in the list:")
    flat = {k for k in obj if not isinstance(obj[k], (dict, list))}
    extra = sorted(flat - {f.split('.')[0] for f in _HMAC_FIELDS})
    print("    " + (", ".join(extra) if extra else "(none)"))
    return 1


if __name__ == "__main__":
    sys.exit(main())
