"""
Field-level audit trail.
────────────────────────
Records *what changed* on a row — old value → new value, per field — not a full
row snapshot and not a bare "row 42 was touched".

Storage: the existing `audit_log` table. No new table, no schema change.
`audit_log` is the live audit table (see the note at the bottom of this file for
the `audit_log` / `audit_logs` split). Its `details` TEXT column carries the
diff as JSON:

    {"price": {"from": "100.0", "to": "125.0"},
     "notes": {"from": null,    "to": "recheck in 2w"}}

Existing rows hold plain English sentences in `details`; readers distinguish the
two by attempting json.loads and checking the result is a dict of dicts
(`parse_details()` below). Nothing has to be backfilled or converted.

Usage — explicit dicts:

    from models.audit import record_change
    record_change("invoices", inv_id, before, after, action="update",
                  module="finance")

Usage — one-liner at the call site (snapshots the row for you):

    from models.audit import audit_row
    with audit_row("roles", role_id, module="system", action="edit_role"):
        db.update_role(role_id, ...)

Portability: SQLite dialect only — `?` placeholders, `datetime('now')`. The
PostgreSQL translation happens in models.database._fix_sql. Never write SERIAL,
TIMESTAMPTZ, NOW() or BOOLEAN here.
"""

import json
import logging
from contextlib import contextmanager

import models.database as db

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# REDACTION
# ══════════════════════════════════════════════════════════════════════════════
#
# An audit trail that records credentials is a credential store with a search
# page bolted on. Matching is by *substring*, case-insensitively, so a column
# added later — whatsapp_api_token, stripe_secret_key, totp_secret_backup — is
# caught without anyone remembering to update this list. Deny by pattern, not by
# exact name: a missed pattern leaks a secret, a spurious match costs one
# unreadable diff line.
#
# Redacted fields are still *reported as changed* (the fact that someone reset a
# password is exactly what an auditor needs) — only the values become "***".

_REDACT_MARKERS = (
    # Credentials and session material
    "password", "passwd", "pwd", "secret", "token", "api_key", "apikey",
    "private_key", "salt", "hash", "totp", "otp_", "_otp", "mfa", "credential",
    "signature", "webhook_url",
    # Payment instruments
    "card_number", "cardnumber", "cvv", "cvc", "iban", "swift",
    "account_number", "routing_number",
    # Government identifiers (Egyptian national ID / passport are held on staff
    # and sometimes on owner records)
    "national_id", "nid_", "passport", "ssn", "tax_id",
)

REDACTED = "***"

# Values longer than this are truncated in the diff. A clinical note or a SOAP
# field can be several KB; storing two full copies of it on every keystroke-save
# is how an audit table becomes larger than the records it audits.
_MAX_VALUE_CHARS = 300

# Columns that change on every UPDATE and carry no audit meaning.
_NOISE_FIELDS = {"updated_at", "modified_at", "last_seen_at", "updated_by"}


def is_redacted(field: str) -> bool:
    """True if `field` must never have its value written to the audit trail."""
    f = (field or "").lower()
    return any(m in f for m in _REDACT_MARKERS)


def _clean(value):
    """Normalise one value for storage: JSON-safe, bounded length."""
    if value is None:
        return None
    if isinstance(value, (int, float, bool)):
        return value
    s = value if isinstance(value, str) else str(value)
    if len(s) > _MAX_VALUE_CHARS:
        return s[:_MAX_VALUE_CHARS] + f"…(+{len(s) - _MAX_VALUE_CHARS} chars)"
    return s


def diff(before: dict, after: dict) -> dict:
    """Fields that actually changed, as {field: {"from": old, "to": new}}.

    Unchanged fields, noise fields and fields absent from both dicts are
    dropped. Redacted fields keep their key (so "the password was changed" is
    still recorded) but both values become "***".

    Comparison is by string form: SQLite returns 1/0 for INTEGER booleans while
    a form posts "1"/"0", and REAL 100.0 vs the string "100.0" is not a real
    edit. Comparing str() avoids a diff full of type-churn nobody made.
    """
    before = before or {}
    after = after or {}
    out = {}
    for field in sorted(set(before) | set(after)):
        if field in _NOISE_FIELDS:
            continue
        old, new = before.get(field), after.get(field)
        if old is None and new is None:
            continue
        if str(old) == str(new):
            continue
        if is_redacted(field):
            out[field] = {"from": REDACTED, "to": REDACTED}
        else:
            out[field] = {"from": _clean(old), "to": _clean(new)}
    return out


def parse_details(details):
    """Decode an `audit_log.details` value into a diff dict, or None.

    None means "this is a legacy free-text detail, render it as text". Used by
    the audit log template; kept here so the storage format has exactly one
    reader and one writer.
    """
    if not details or not isinstance(details, str):
        return None
    s = details.lstrip()
    if not s.startswith("{"):
        return None
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        return None
    if not isinstance(parsed, dict) or not parsed:
        return None
    if not all(isinstance(v, dict) and ("from" in v or "to" in v)
               for v in parsed.values()):
        return None
    return parsed


# ══════════════════════════════════════════════════════════════════════════════
# WRITE
# ══════════════════════════════════════════════════════════════════════════════

def _current_user():
    """(username, role) from the Flask session, or ("system", "") outside one."""
    try:
        from flask import session, has_request_context
        if has_request_context():
            u = session.get("user") or {}
            return u.get("username", "") or "anonymous", u.get("role", "") or ""
    except Exception:
        logger.debug("audit: no Flask session available", exc_info=True)
    return "system", ""


def _request_meta():
    """(ip, user_agent) from the current request, or ("", "")."""
    try:
        from flask import request, has_request_context
        if has_request_context():
            return request.remote_addr or "", (request.user_agent.string or "")[:200]
    except Exception:
        logger.debug("audit: no Flask request available", exc_info=True)
    return "", ""


def record_change(table, row_id, before, after, action="update",
                  user=None, role=None, module="", ip=None, user_agent=None):
    """Write one audit row describing the fields that changed on `table`.`row_id`.

    Returns the diff that was stored ({} when nothing changed and nothing was
    written). Never raises — see the comment on the except below.
    """
    changes = diff(before, after)
    if not changes:
        # Nothing changed. A "user pressed Save and altered nothing" row is pure
        # noise and there will be a lot of them.
        return {}

    if user is None or role is None:
        auto_user, auto_role = _current_user()
        user = auto_user if user is None else user
        role = auto_role if role is None else role
    if ip is None or user_agent is None:
        auto_ip, auto_ua = _request_meta()
        ip = auto_ip if ip is None else ip
        user_agent = auto_ua if user_agent is None else user_agent

    try:
        conn = db.get_db()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO audit_log"
                    "(username,role,action,module,entity_type,entity_id,details,ip,user_agent) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (user or "", role or "", action or "update", module or "",
                     table or "", "" if row_id is None else str(row_id),
                     json.dumps(changes, ensure_ascii=False, default=str),
                     ip or "", user_agent or ""),
                )
        finally:
            conn.close()
    except Exception:
        # DELIBERATE SWALLOW — the one place it is correct.
        #
        # The audit write is a *side effect* of a business operation that has
        # already been committed. If this INSERT fails (disk full, audit_log
        # locked, PostgreSQL hiccup) and we re-raise, the caller's error handler
        # rolls back or flashes a failure for an invoice that actually saved —
        # so a broken audit trail would start corrupting the financial and
        # medical records it exists to protect. Losing an audit row is bad;
        # losing the invoice is worse.
        #
        # It is NOT silent: exc_info=True puts the full traceback on the ERROR
        # channel, which models/logging_setup.py routes to the rotating backend
        # log and to Sentry when configured. Alert on it.
        logger.error(
            "AUDIT WRITE FAILED — change to %s#%s by %s was NOT recorded: %s",
            table, row_id, user, json.dumps(changes, ensure_ascii=False, default=str)[:500],
            exc_info=True,
        )
    return changes


def snapshot(table, row_id):
    """Current contents of one row as a dict, or {} if it is gone/unreadable.

    `table` is interpolated into the SQL — it is a developer-supplied literal at
    every call site, never user input. Guarded to identifier characters anyway.
    """
    if not table or not str(table).replace("_", "").isalnum():
        raise ValueError(f"audit.snapshot: unsafe table name {table!r}")
    try:
        conn = db.get_db()
        try:
            row = conn.execute(
                f"SELECT * FROM {table} WHERE id=?", (row_id,)
            ).fetchone()
        finally:
            conn.close()
        return dict(row) if row else {}
    except Exception:
        # Same rule as record_change: an unreadable snapshot must not break the
        # operation. Logged, not silent.
        logger.error("AUDIT SNAPSHOT FAILED for %s#%s", table, row_id, exc_info=True)
        return {}


@contextmanager
def audit_row(table, row_id, module="", action="update",
              user=None, role=None):
    """One-liner instrumentation: snapshot, run the mutation, record the diff.

        with audit_row("roles", role_id, module="system", action="edit_role"):
            db.update_role(role_id, ...)

    Requires `table` to have an integer `id` primary key — true of every table in
    this schema except `settings` (keyed on `key`) and `sync_queue` (TEXT id).
    For those, and for deletes/inserts where one side has no row, call
    record_change() with explicit dicts.

    If the wrapped block raises, nothing is recorded and the exception
    propagates — a failed operation has no change to audit.

    # ponytail: two extra `SELECT *` per mutation (before and after). Ceiling:
    # on a hot path doing thousands of writes a minute — bulk import, the
    # migration blueprint, a POS batch — that is a real cost. Upgrade path: those
    # callers already hold the row they just built, so they should call
    # record_change() with the dicts they have instead of using this wrapper.
    """
    before = snapshot(table, row_id)
    yield before
    after = snapshot(table, row_id)
    record_change(table, row_id, before, after, action=action,
                  module=module, user=user, role=role)


# ══════════════════════════════════════════════════════════════════════════════
# NOTE — the two audit tables
# ══════════════════════════════════════════════════════════════════════════════
#
# models/database.py declares BOTH `audit_log` (~line 499) and `audit_logs`
# (~line 1520). They are not duplicates of each other in practice:
#
#   audit_log  (singular) — LIVE. Written by models.database.log_audit() from
#       ~25 call sites across 15 blueprints. Read by system.audit_log (the UI),
#       hr.routes (staff activity) and migration.routes (which uses it for
#       *idempotency* — it re-reads entity_id to skip already-migrated visits,
#       so the table is load-bearing beyond display). This module writes here.
#
#   audit_logs (plural) — write-only. Written only by models.logging_db.log_audit(),
#       called only from blueprints/api_v1/routes.py. No SELECT anywhere except a
#       COUNT(*) in the diagnostics endpoint. It has old_value/new_value columns:
#       someone started this same field-level design there and abandoned it.
#
# It is deliberately NOT consolidated. Merging them means a data migration that
# maps one schema onto another on a production database whose audit history is
# the only record of who did what — all the risk, and the only payoff is
# tidiness. `audit_logs` is left exactly as it is, still collecting API-v1 rows.
# See the report / MIGRATIONS.md for the full reasoning.
#
# ponytail: field-level history lives in audit_log.details as JSON rather than
# in dedicated columns. Ceiling: you cannot ask SQL "show every change to
# invoices.total" without a LIKE scan. Upgrade path: when that query is actually
# needed, add an `audit_changes(audit_id, field, old, new)` child table and have
# record_change() fan out into it — the JSON stays as the canonical copy so no
# backfill is required.
