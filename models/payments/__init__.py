# -*- coding: utf-8 -*-
"""Taking money, and being able to prove it afterwards.

WHY THIS EXISTS AT ALL

models.database.add_payment accepted `method`, `reference` and `received_by`
and discarded all three. It never wrote to the `payments` table — it only
incremented invoices.paid_amount. So the system could say an invoice was paid
and could not say who paid it, when, by what means, or against which receipt.
There was no record of a failed attempt, no refund, and nothing stopping the
same payment being taken twice by a double-clicked form.

THE SHAPE

    gateway            how the money moves (cash at the counter, a card online)
    payment_intents    one row per ATTEMPT, including failures
    payments           the ledger: money that actually arrived
    payment_events     append-only history, for disputes and audits

Intents and the ledger are deliberately separate. Collapsing them means either
writing ledger rows for money that never arrived, or throwing away the evidence
of what went wrong.

ADDING A GATEWAY

Subclass Gateway, implement three methods, and register it. Nothing else in the
application changes — routes, templates and reconciliation all work through
this module, which is what "configurable so more gateways can be added later"
has to mean if it is to mean anything.
"""
import json
import logging
import uuid
from decimal import Decimal

import models.database as db
from models.money import to_decimal

logger = logging.getLogger(__name__)

PENDING, SUCCEEDED, FAILED, CANCELLED, REFUNDED = (
    "pending", "succeeded", "failed", "cancelled", "refunded")

# Which status may become which. Enforced in _set_status so a bug cannot mark a
# refunded payment as succeeded again, or re-capture a cancelled one.
_TRANSITIONS = {
    PENDING:   {SUCCEEDED, FAILED, CANCELLED},
    SUCCEEDED: {REFUNDED},
    FAILED:    set(),
    CANCELLED: set(),
    REFUNDED:  set(),
}


class PaymentError(Exception):
    """Anything that stops money being taken. Message is shown to staff."""


class Gateway:
    """One way of moving money. Three methods, no framework."""

    name = ""
    label = ""
    label_ar = ""
    #: True when the clinic collects the money itself and the app only records
    #: it. Cash is the primary method in an Egyptian clinic and must never be
    #: gated behind an online provider being reachable.
    offline = False

    def charge(self, intent: dict) -> dict:
        """Attempt the charge.

        Returns {"status": ..., "gateway_ref": ..., "detail": ...}. Raising is
        also fine — the caller records the failure either way.
        """
        raise NotImplementedError

    def refund(self, intent: dict, amount: Decimal) -> dict:
        raise NotImplementedError

    def verify_callback(self, payload: dict, headers: dict) -> dict:
        """Authenticate a provider callback and say what it means.

        Returns {"gateway_ref": ..., "status": ..., "detail": ...}, or raises
        PaymentError if the callback cannot be authenticated. An unverified
        callback marking an invoice paid is free money for anyone who can post
        to the URL, so the default is to refuse.
        """
        raise PaymentError(f"{self.name} does not accept callbacks")


_REGISTRY: dict = {}


def register(gateway: Gateway) -> None:
    _REGISTRY[gateway.name] = gateway


def get(name: str) -> Gateway:
    # Register on first use if create_app() has not run. Seeders, cron jobs,
    # migrations and tests all take payments without a Flask app, and requiring
    # them to know about init() meant `add_payment(..., method="Cash")` raised
    # "Unknown payment method: 'cash'" outside the web process — caught by the
    # PostgreSQL suite, which does exactly that.
    if not _REGISTRY:
        init()
    gw = _REGISTRY.get((name or "").strip().lower())
    if gw is None:
        raise PaymentError(f"Unknown payment method: {name!r}")
    return gw


def available() -> list:
    """Gateways a clinic can actually use right now, cash first.

    Cash leads because it is how most Egyptian clinics are actually paid, and
    because it keeps working when the internet does not.
    """
    if not _REGISTRY:
        init()
    out = [g for g in _REGISTRY.values() if g.offline or g.configured()]
    # Cash first by name, not by luck: sorting the counter methods by label put
    # "Bank transfer" at the top. Then the rest of the counter methods, then
    # anything that needs the internet.
    return sorted(out, key=lambda g: (not g.offline, g.name != "cash", g.label))


# ── the flow ─────────────────────────────────────────────────────────────────

def create_intent(invoice_id: int, owner_id: int, amount, gateway: str = "cash",
                  *, idempotency_key: str = "", created_by: str = "",
                  currency: str = "EGP", reference: str = "") -> dict:
    """Register an attempt to collect `amount`. Idempotent.

    Re-submitting the same idempotency_key returns the EXISTING intent instead
    of creating a second one. That is what stops a double-clicked Pay button, a
    retried request or a duplicated webhook from taking the money twice.
    """
    amt = to_decimal(amount)
    if amt <= 0:
        raise PaymentError("A payment must be greater than zero.")
    get(gateway)                        # fail fast on an unknown method
    key = idempotency_key or f"auto-{uuid.uuid4()}"

    conn = db.get_db()
    try:
        existing = conn.execute(
            "SELECT * FROM payment_intents WHERE idempotency_key=?", (key,)).fetchone()
        if existing:
            logger.info("duplicate payment suppressed: key=%s intent=%s",
                        key, existing["id"])
            return dict(existing)

        inv = conn.execute(
            "SELECT total, paid_amount, status FROM invoices WHERE id=?",
            (invoice_id,)).fetchone()
        if not inv:
            raise PaymentError("That invoice does not exist.")
        if (inv["status"] or "") == "Cancelled":
            raise PaymentError("That invoice has been cancelled.")

        due = to_decimal(inv["total"]) - to_decimal(inv["paid_amount"])
        if amt > due:
            raise PaymentError(
                f"That is more than the {due:.2f} still owed on this invoice.")

        # Everything that touches `conn` must happen INSIDE this block.
        # `with conn:` commits AND closes — on PostgreSQL close() hands the
        # connection back to the pool, so a query issued after the block opens a
        # fresh transaction on a connection somebody else is about to borrow.
        # The next caller then gets it mid-transaction and psycopg2 raises
        # "set_session cannot be used inside a transaction" from an unrelated
        # place. Invisible on SQLite, where close() really closes and every
        # get_db() opens a new handle.
        with conn:
            cur = conn.execute(
                "INSERT INTO payment_intents"
                "(invoice_id, owner_id, gateway, amount, currency, status,"
                " idempotency_key, created_by, gateway_ref)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                (invoice_id, owner_id, gateway, str(amt), currency, PENDING,
                 key, created_by, (reference or "").strip() or None))
            intent_id = cur.lastrowid
            _event(conn, intent_id, "created",
                   {"amount": str(amt), "gateway": gateway}, created_by)
            row = conn.execute("SELECT * FROM payment_intents WHERE id=?",
                               (intent_id,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def capture(intent_id: int, actor: str = "") -> dict:
    """Run the charge and record whatever happened."""
    intent = _load(intent_id)
    if intent["status"] != PENDING:
        # Not an error: a retried request landing on an already-captured intent
        # should get the same answer as the first, not a second charge.
        return intent

    gw = get(intent["gateway"])
    try:
        result = gw.charge(intent)
    except PaymentError as exc:
        _fail(intent_id, str(exc), actor)
        raise
    except Exception as exc:
        logger.exception("gateway %s raised during capture", intent["gateway"])
        _fail(intent_id, f"{type(exc).__name__}: {exc}", actor)
        raise PaymentError(
            "The payment provider could not be reached. Nothing was charged.")

    status = result.get("status", FAILED)
    if status == SUCCEEDED:
        return _succeed(intent_id, result.get("gateway_ref", ""), actor)
    if status == PENDING:
        # Redirect / 3-D Secure flows finish in the callback.
        _update(intent_id, gateway_ref=result.get("gateway_ref", ""))
        _event_id(intent_id, "awaiting_customer", result, actor)
        return _load(intent_id)
    _fail(intent_id, result.get("detail", "The payment was declined."), actor)
    return _load(intent_id)


def refund(intent_id: int, amount=None, actor: str = "", reason: str = "") -> dict:
    """Refund all or part of a captured payment."""
    intent = _load(intent_id)
    if intent["status"] != SUCCEEDED:
        raise PaymentError("Only a completed payment can be refunded.")

    already = to_decimal(intent["refunded_amount"])
    total = to_decimal(intent["amount"])
    amt = total - already if amount is None else to_decimal(amount)
    if amt <= 0:
        raise PaymentError("A refund must be greater than zero.")
    if already + amt > total:
        raise PaymentError(
            f"Only {total - already:.2f} of this payment is left to refund.")

    gw = get(intent["gateway"])
    result = gw.refund(intent, amt)
    if result.get("status") != SUCCEEDED:
        raise PaymentError(result.get("detail", "The refund was declined."))

    new_total = already + amt
    conn = db.get_db()
    try:
        with conn:
            # Fully refunded moves the status; a partial refund stays
            # 'succeeded' so the remainder can still be refunded later.
            if new_total >= total:
                _set_status(conn, intent_id, REFUNDED)
            conn.execute(
                "UPDATE payment_intents SET refunded_amount=?, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (str(new_total), intent_id))
            # The ledger gets a NEGATIVE row rather than an edited one. An
            # amended payment row destroys the evidence that money was taken
            # and given back, which is the thing a dispute turns on.
            conn.execute(
                "INSERT INTO payments"
                "(invoice_id, owner_id, amount, method, channel, reference,"
                " notes, received_by, received_at)"
                " VALUES(?,?,?,?,?,?,?,?,datetime('now','localtime'))",
                (intent["invoice_id"], intent["owner_id"], str(-amt),
                 f"Refund ({intent['gateway']})", intent["gateway"],
                 result.get("gateway_ref", ""), reason or "Refund", actor))
            _event(conn, intent_id, "refunded",
                   {"amount": str(amt), "reason": reason,
                    "gateway_ref": result.get("gateway_ref", "")}, actor)
    finally:
        conn.close()

    _reconcile_invoice(intent["invoice_id"])
    return _load(intent_id)


def cancel(intent_id: int, actor: str = "", reason: str = "") -> dict:
    intent = _load(intent_id)
    if intent["status"] != PENDING:
        raise PaymentError("Only a pending payment can be cancelled.")
    conn = db.get_db()
    try:
        with conn:
            _set_status(conn, intent_id, CANCELLED)
            _event(conn, intent_id, "cancelled", {"reason": reason}, actor)
    finally:
        conn.close()
    return _load(intent_id)


def handle_callback(gateway_name: str, payload: dict, headers: dict) -> dict:
    """Process a provider callback. Verifies first, always."""
    gw = get(gateway_name)
    verified = gw.verify_callback(payload, headers)   # raises if not authentic

    ref = verified.get("gateway_ref", "")
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT * FROM payment_intents WHERE gateway_ref=? AND gateway=?",
            (ref, gateway_name)).fetchone()
    finally:
        conn.close()
    if not row:
        raise PaymentError(f"No payment matches provider reference {ref!r}")

    intent = dict(row)
    if intent["status"] != PENDING:
        # Providers retry callbacks. Replaying one must not pay an invoice twice.
        logger.info("ignoring repeat callback for intent %s (already %s)",
                    intent["id"], intent["status"])
        return intent

    if verified.get("status") == SUCCEEDED:
        return _succeed(intent["id"], ref, f"callback:{gateway_name}")
    _fail(intent["id"], verified.get("detail", "Declined by the provider."),
          f"callback:{gateway_name}")
    return _load(intent["id"])


def history(invoice_id: int) -> list:
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM payment_intents WHERE invoice_id=? ORDER BY id",
            (invoice_id,)).fetchall()]
    finally:
        conn.close()


def events(intent_id: int) -> list:
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM payment_events WHERE intent_id=? ORDER BY id",
            (intent_id,)).fetchall()]
    finally:
        conn.close()


# ── internals ────────────────────────────────────────────────────────────────

def _load(intent_id: int) -> dict:
    conn = db.get_db()
    try:
        row = conn.execute("SELECT * FROM payment_intents WHERE id=?",
                           (intent_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        raise PaymentError(f"No such payment: {intent_id}")
    return dict(row)


def _set_status(conn, intent_id: int, new: str) -> None:
    row = conn.execute("SELECT status FROM payment_intents WHERE id=?",
                       (intent_id,)).fetchone()
    old = row["status"] if row else None
    if new not in _TRANSITIONS.get(old, set()):
        raise PaymentError(f"A {old} payment cannot become {new}.")
    conn.execute("UPDATE payment_intents SET status=?, "
                 "updated_at=datetime('now','localtime') WHERE id=?",
                 (new, intent_id))


def _update(intent_id: int, **fields) -> None:
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                f"UPDATE payment_intents SET {cols}, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (*fields.values(), intent_id))
    finally:
        conn.close()


def _succeed(intent_id: int, gateway_ref: str, actor: str) -> dict:
    intent = _load(intent_id)
    # A reference typed by staff is the reconciliation key — the Instapay or
    # transfer number they will later match against a bank statement. A counter
    # gateway returns a synthetic stub like CASH-12, which must never overwrite
    # it. An online gateway's real reference does take precedence, because that
    # is the one the provider will be queried by.
    if intent.get("gateway_ref") and get(intent["gateway"]).offline:
        gateway_ref = intent["gateway_ref"]
    conn = db.get_db()
    try:
        with conn:
            _set_status(conn, intent_id, SUCCEEDED)
            conn.execute("UPDATE payment_intents SET gateway_ref=? WHERE id=?",
                         (gateway_ref, intent_id))
            # THE LEDGER ROW. This is what add_payment never wrote, and why the
            # system could say an invoice was paid but not by whom or how.
            # received_at is stamped in LOCAL time, explicitly.
            #
            # The column default is datetime('now'), which SQLite evaluates in
            # UTC, while every date this app compares against — issue_date,
            # date.today(), the daily closing window — is the clinic's local
            # date. In Cairo (UTC+3) that put every payment taken after 21:00
            # onto YESTERDAY's till, so three hours of each evening's takings
            # never appeared in "Today's Revenue" and the drawer never
            # reconciled. Passing it explicitly also fixes existing databases,
            # whose baked-in column default cannot be changed by editing the
            # schema.
            conn.execute(
                "INSERT INTO payments"
                "(invoice_id, owner_id, amount, method, channel, reference,"
                " notes, received_by, received_at)"
                " VALUES(?,?,?,?,?,?,?,?,datetime('now','localtime'))",
                (intent["invoice_id"], intent["owner_id"], intent["amount"],
                 get(intent["gateway"]).label, intent["gateway"], gateway_ref,
                 "", actor))
            _event(conn, intent_id, "succeeded", {"gateway_ref": gateway_ref}, actor)
    finally:
        conn.close()
    _reconcile_invoice(intent["invoice_id"])
    return _load(intent_id)


def _fail(intent_id: int, reason: str, actor: str) -> None:
    conn = db.get_db()
    try:
        with conn:
            _set_status(conn, intent_id, FAILED)
            conn.execute("UPDATE payment_intents SET failure_reason=? WHERE id=?",
                         (reason[:500], intent_id))
            _event(conn, intent_id, "failed", {"reason": reason}, actor)
    finally:
        conn.close()


def _reconcile_invoice(invoice_id: int) -> None:
    """Recompute the invoice from the LEDGER, never by incrementing a running
    total.

    Deriving it means a refund, a correction or a replayed callback can never
    leave paid_amount drifting away from the rows that justify it — which is
    exactly what an incrementing total does the first time anything goes wrong.
    """
    conn = db.get_db()
    try:
        with conn:
            row = conn.execute(
                "SELECT total, status FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            if not row:
                return
            paid = conn.execute(
                "SELECT COALESCE(SUM(amount),0) s FROM payments WHERE invoice_id=?",
                (invoice_id,)).fetchone()["s"]
            total = to_decimal(row["total"])
            paid = to_decimal(paid)
            due = total - paid
            if due < 0:
                due = to_decimal(0)
            # Half a piastre, never exact zero: see docs/MONEY_PRECISION.md.
            status = row["status"]
            if status != "Cancelled":
                status = "Paid" if due < to_decimal("0.005") else (
                    "Partial" if paid > 0 else "Unpaid")
            conn.execute(
                "UPDATE invoices SET paid_amount=?, due_amount=?, status=?, "
                "updated_at=datetime('now','localtime') WHERE id=?",
                (str(paid), str(due), status, invoice_id))
    finally:
        conn.close()


def _event(conn, intent_id: int, event: str, detail: dict, actor: str) -> None:
    conn.execute(
        "INSERT INTO payment_events(intent_id, event, detail, actor) VALUES(?,?,?,?)",
        (intent_id, event, json.dumps(detail, ensure_ascii=False), actor or ""))


def _event_id(intent_id: int, event: str, detail: dict, actor: str) -> None:
    conn = db.get_db()
    try:
        with conn:
            _event(conn, intent_id, event, detail, actor)
    finally:
        conn.close()


def init() -> None:
    """Register the built-in gateways. Called from create_app()."""
    from models.payments.cash import counter_gateways
    from models.payments.paymob import PaymobGateway
    for gw in counter_gateways():
        register(gw)
    register(PaymobGateway())


# Legacy form values -> gateway names. The invoice screen has always posted
# these strings, so they keep working unchanged.
_METHOD_ALIASES = {
    "cash": "cash", "نقدي": "cash",
    "card": "card", "visa": "card", "mastercard": "card", "meeza": "card",
    "transfer": "transfer", "bank": "transfer", "bank transfer": "transfer",
    "instapay": "instapay",
    "insurance": "insurance", "تأمين": "insurance",
    "online": "paymob", "paymob": "paymob",
}


def gateway_for_method(method: str) -> str:
    """Map a human payment-method string onto a gateway name.

    Unknown values fall back to cash rather than raising: an unrecognised label
    on a payment a receptionist has already physically taken must still be
    recordable. The label itself is preserved on the ledger row.
    """
    return _METHOD_ALIASES.get((method or "").strip().lower(), "cash")
