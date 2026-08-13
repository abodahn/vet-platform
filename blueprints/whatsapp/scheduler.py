"""
WhatsApp Reminder Scheduler — runs daily at 09:00 via APScheduler.
Sends appointment reminders (next-day), vaccine due reminders, and overdue invoice alerts.
Deduplication via reminder_runs table to prevent double-sending.
"""
import logging
from datetime import date, datetime, timedelta, timezone
from models.database import get_db, log_audit

logger = logging.getLogger(__name__)


def _run_stamp() -> str:
    """Timestamp written to reminder_runs — the CLINIC's local time.

    Both sides of the dedup gate must agree on one clock, and they did not:
    _mark_sent stored SQLite's datetime('now'), which is UTC, while the gate
    compared DATE(run_at) against Python's date.today(), which is local. Where
    those differ — anywhere far enough east at 09:00, and Cairo between
    midnight and 03:00 — the gate could never match its own marker, so EVERY
    client was re-reminded on EVERY run.

    Local, not UTC, because the rest of this module already reasons in local
    dates: _appointment_reminders selects tomorrow with date.today() + 1 and
    _vaccine_reminders uses date.today(). "Already reminded today" means the
    clinic's today, and the stored timestamp should read back the way the
    clinic's own screens show it.

    Binding it from Python also makes the two engines agree: _fix_sql rewrites
    datetime('now') to NOW(), which PostgreSQL evaluates in the server's
    timezone rather than the clinic's.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run_date() -> str:
    """Local date, matching the stamp above."""
    return date.today().isoformat()


def _already_sent(conn, run_type: str, entity_id: int, entity_type: str) -> bool:
    row = conn.execute(
        "SELECT id FROM reminder_runs WHERE run_type=? AND entity_id=? AND entity_type=? AND DATE(run_at)=?",
        (run_type, entity_id, entity_type, _run_date())
    ).fetchone()
    return row is not None


def _mark_sent(conn, run_type: str, entity_id: int, entity_type: str):
    # reminder_runs carries UNIQUE(run_type, entity_id, entity_type), while the
    # dedup gate above is per *day*. An entity that stays eligible for several
    # days (an overdue invoice, a vaccine inside its 7-day window) therefore
    # comes back tomorrow and a plain INSERT would violate the key and abort
    # the whole run. Refresh the existing row instead, insert only if new.
    cur = conn.execute(
        "UPDATE reminder_runs SET status='sent', run_at=? "
        "WHERE run_type=? AND entity_id=? AND entity_type=?",
        (_run_stamp(), run_type, entity_id, entity_type)
    )
    if not cur.rowcount:
        conn.execute(
            "INSERT INTO reminder_runs(run_type, entity_id, entity_type, status, run_at) VALUES(?,?,?,'sent',?)",
            (run_type, entity_id, entity_type, _run_stamp())
        )


# After this many sends fail in a row, the run gives up on the rest.
#
# One send against an unreachable host was measured at 535 SECONDS. Without a
# cap, a clinic with 200 clients and a dead WhatsApp instance would keep the
# scheduler thread busy for most of a day, and the following morning's run
# would still be queued behind it. Five failures is enough to tell "this one
# number is bad" from "the transport is down".
_MAX_CONSECUTIVE_FAILURES = 5


class _Sender:
    """The transport for one reminder run, plus its failure budget.

    Built ONCE per run and passed down, rather than resolved per message: the
    settings lookup is a query, and doing it 200 times per night is pure waste.
    It is passed explicitly rather than held in a module global — the globals in
    models.backup and models.tenancy are exactly how this codebase has ended up
    pointing at the wrong clinic before.
    """

    def __init__(self, client, reason: str = ""):
        self.client = client          # None when WhatsApp is not connected
        self.reason = reason          # why, in words a clinic can act on
        self.failures = 0
        self.gave_up = False


def _make_sender(conn) -> _Sender:
    """Resolve the same credentials the Send screen uses.

    The job used to read $WAPILOT_TOKEN alone and POST {"phone","message"} with
    a Bearer header to https://api.wapilot.io/send, while every working manual
    button posts {"chat_id","text"} with a `token` header to
    https://api.wapilot.net/api/v2/{instance}/send-message. Different host,
    path, auth scheme and payload — so a clinic that connected WhatsApp the
    only documented way (scan the QR, save the token in Settings) got a working
    Send Center and a nightly job that logged "Not Configured" for every single
    reminder. There was no configuration under which a scheduled reminder was
    deliverable.

    Reads through the CALLER'S connection. blueprints.whatsapp.routes._client
    opens and closes its own, and closing it mid-run took the job's transaction
    with it — every reminder then produced no log row at all.
    """
    import os
    from .wapilot import WapilotClient

    rows = {r["key"]: r["value"] for r in conn.execute(
        "SELECT key, value FROM settings WHERE category='wapilot'").fetchall()}
    token = (rows.get("wapilot_token") or os.environ.get("WAPILOT_TOKEN", "")).strip()
    iid = (rows.get("wapilot_instance_id")
           or os.environ.get("WAPILOT_INSTANCE", "")).strip()

    if not token or not iid:
        missing = "token" if not token else "instance ID"
        return _Sender(None, "WhatsApp is not connected — no API %s is set. "
                             "Connect it under WhatsApp → Settings." % missing)
    return _Sender(WapilotClient(token, iid))


def _send_whatsapp(conn, phone: str, message: str, owner_id=None,
                   template_name="", sender=None):
    """Send one reminder through the same transport as the Send screen."""
    if sender is None:
        sender = _make_sender(conn)

    if sender.client is None:
        # NEVER report "Sent" for a message that was never transmitted. This
        # previously logged stub-mode sends as Sent, so a clinic saw a green
        # column of reminders that had not left the building — and then blamed
        # clients for not turning up. A reminder system that lies about
        # delivery is worse than having none.
        status, error = "Not Configured", sender.reason
        logger.warning("WhatsApp reminder NOT sent to %s (%s): %s",
                       phone, template_name or "reminder", sender.reason)
    elif sender.gave_up:
        status = "Not Sent"
        error = ("Skipped: %d sends in a row failed, so the rest of this run "
                 "was abandoned rather than left retrying a dead connection."
                 % _MAX_CONSECUTIVE_FAILURES)
    else:
        # chat_id, not phone: the v2 API addresses a conversation.
        _resp, err = sender.client.send_message(str(phone or "").strip(), message)
        if err:
            status, error = "Failed", err
            sender.failures += 1
            if sender.failures >= _MAX_CONSECUTIVE_FAILURES:
                sender.gave_up = True
                logger.error("WhatsApp run abandoned after %d consecutive "
                             "failures; last error: %s", sender.failures, err)
        else:
            status, error = "Sent", ""
            sender.failures = 0

    conn.execute(
        "INSERT INTO whatsapp_log(owner_id, phone, message, template_name, status, error, sent_at) VALUES(?,?,?,?,?,?,datetime('now'))",
        (owner_id, phone, message, template_name, status, error)
    )
    return status


def _wa_setting(conn, key, default=""):
    """One saved WhatsApp setting, or `default`.

    The three switches and the three message boxes on WhatsApp → Settings were
    WRITE-ONLY: wa_settings() persisted reminder_appt_enabled,
    reminder_vaccine_enabled, reminder_invoice_enabled and the matching _msg
    templates, and this module read none of them. Turning appointment
    reminders off did not stop them, and editing the message changed nothing —
    the hardcoded English text below went out either way. A switch that does
    nothing is worse than no switch, because somebody trusts it.
    """
    try:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    except Exception:
        return default
    if not row or row[0] is None or row[0] == "":
        return default
    return row[0]


def _enabled(conn, key) -> bool:
    """A reminder type is ON unless it was explicitly switched off."""
    return str(_wa_setting(conn, key, "1")).strip() not in ("0", "false", "no", "off")


def _render(template, fallback, **fields):
    """Fill {owner}/{pet}/{date}… in a clinic's own message.

    A bad placeholder in text somebody typed must not stop the reminder going
    out, so an unknown field falls back to the built-in wording rather than
    raising inside the nightly job.
    """
    text = (template or "").strip()
    if not text:
        return fallback
    try:
        return text.format(**fields)
    except (KeyError, IndexError, ValueError):
        logger.warning("reminder template has an unknown placeholder — "
                       "using the built-in wording instead")
        return fallback


def _appointment_reminders(conn, sender=None) -> int:
    """Remind owners of appointments scheduled for tomorrow."""
    if not _enabled(conn, "reminder_appt_enabled"):
        logger.info("appointment reminders are switched off in Settings")
        return 0
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    appts = conn.execute("""
        SELECT a.id, a.appt_date, a.appt_start, a.appointment_type,
               o.id owner_id, o.full_name, o.whatsapp_phone,
               p.pet_name
        FROM appointments a
        JOIN owners o ON o.id = a.owner_id
        JOIN pets p ON p.id = a.pet_id
        WHERE a.appt_date = ? AND a.status IN ('Scheduled','Confirmed')
          AND o.whatsapp_phone IS NOT NULL AND o.whatsapp_phone != ''
    """, (tomorrow,)).fetchall()

    sent = 0
    for a in appts:
        if _already_sent(conn, "appt_reminder", a["id"], "appointment"):
            continue
        built_in = (
            f"Dear {a['full_name']},\n"
            f"Reminder: {a['pet_name']} has a {a['appointment_type']} appointment tomorrow "
            f"({a['appt_date']} at {a['appt_start'] or 'TBD'}).\n"
            f"Please arrive 10 minutes early. Reply CONFIRM to confirm."
        )
        msg = _render(_wa_setting(conn, "reminder_appt_msg"), built_in,
                      owner=a["full_name"], pet=a["pet_name"],
                      date=a["appt_date"], time=a["appt_start"] or "TBD",
                      type=a["appointment_type"])
        status = _send_whatsapp(conn, a["whatsapp_phone"], msg,
                                owner_id=a["owner_id"], template_name="appt_reminder",
                                sender=sender)
        _mark_sent(conn, "appt_reminder", a["id"], "appointment")
        if status in ("Sent", "Pending"):
            sent += 1
    return sent


def _vaccine_reminders(conn, sender=None) -> int:
    """Remind owners of vaccines due today or overdue by up to 7 days."""
    if not _enabled(conn, "reminder_vaccine_enabled"):
        logger.info("vaccine reminders are switched off in Settings")
        return 0
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    vaccines = conn.execute("""
        SELECT v.id, v.next_due_at, v.vaccine_name,
               o.id owner_id, o.full_name, o.whatsapp_phone,
               p.pet_name
        FROM vaccinations v
        JOIN pets p ON p.id = v.pet_id
        JOIN owners o ON o.id = p.owner_id
        WHERE v.next_due_at BETWEEN ? AND ?
          AND o.whatsapp_phone IS NOT NULL AND o.whatsapp_phone != ''
    """, (week_ago, today)).fetchall()

    sent = 0
    for v in vaccines:
        if _already_sent(conn, "vaccine_reminder", v["id"], "vaccination"):
            continue
        overdue = v["next_due_at"] < today
        built_in = (
            f"Dear {v['full_name']},\n"
            f"{'OVERDUE: ' if overdue else ''}{v['pet_name']} is {'overdue for' if overdue else 'due for'} "
            f"the {v['vaccine_name']} vaccine (due: {v['next_due_at']}).\n"
            f"Please book an appointment at your earliest convenience."
        )
        msg = _render(_wa_setting(conn, "reminder_vaccine_msg"), built_in,
                      owner=v["full_name"], pet=v["pet_name"],
                      vaccine=v["vaccine_name"], date=v["next_due_at"])
        status = _send_whatsapp(conn, v["whatsapp_phone"], msg,
                                owner_id=v["owner_id"], template_name="vaccine_reminder",
                                sender=sender)
        _mark_sent(conn, "vaccine_reminder", v["id"], "vaccination")
        if status in ("Sent", "Pending"):
            sent += 1
    return sent


def _invoice_reminders(conn, sender=None) -> int:
    """Remind owners of invoices overdue by 3+ days."""
    if not _enabled(conn, "reminder_invoice_enabled"):
        logger.info("invoice reminders are switched off in Settings")
        return 0
    today = date.today().isoformat()
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    invoices = conn.execute("""
        SELECT inv.id, inv.invoice_number, inv.total, inv.due_amount, inv.due_date,
               o.id owner_id, o.full_name, o.whatsapp_phone
        FROM invoices inv
        JOIN owners o ON o.id = inv.owner_id
        WHERE inv.status IN ('Unpaid','Partial')
          AND inv.due_date <= ?
          AND o.whatsapp_phone IS NOT NULL AND o.whatsapp_phone != ''
    """, (three_days_ago,)).fetchall()

    sent = 0
    for inv in invoices:
        if _already_sent(conn, "invoice_reminder", inv["id"], "invoice"):
            continue
        # What is still OWED, not what was invoiced. This quoted inv['total'],
        # so a client who had already paid most of a large invoice was chased
        # for the whole amount — the clinic looked like it had lost the
        # payment, and the client rang up to argue rather than to pay.
        owed = float(inv["due_amount"] if inv["due_amount"] is not None
                     else inv["total"] or 0)
        built_in = (
            f"Dear {inv['full_name']},\n"
            f"Invoice #{inv['invoice_number']} has {owed:.2f} outstanding "
            f"(due {inv['due_date']}).\n"
            f"Please contact us to settle your balance. Thank you."
        )
        msg = _render(_wa_setting(conn, "reminder_invoice_msg"), built_in,
                      owner=inv["full_name"], invoice=inv["invoice_number"],
                      amount="%.2f" % owed, date=inv["due_date"],
                      total="%.2f" % float(inv["total"] or 0))
        status = _send_whatsapp(conn, inv["whatsapp_phone"], msg,
                                owner_id=inv["owner_id"], template_name="invoice_reminder",
                                sender=sender)
        _mark_sent(conn, "invoice_reminder", inv["id"], "invoice")
        if status in ("Sent", "Pending"):
            sent += 1
    return sent


def run_reminder_jobs():
    """Entry point called by APScheduler at 09:00 daily."""
    conn = get_db()
    try:
        with conn:
            # One transport for the whole run, so the failure budget is shared:
            # if the instance is down, the appointment job discovers it and the
            # vaccine and invoice jobs do not each spend five more timeouts
            # rediscovering the same thing.
            sender = _make_sender(conn)
            appts = _appointment_reminders(conn, sender)
            vaccines = _vaccine_reminders(conn, sender)
            invoices = _invoice_reminders(conn, sender)
        conn.commit()
        logger.info(f"Reminder run: {appts} appt, {vaccines} vaccine, {invoices} invoice reminders sent")
        log_audit(
            username="scheduler",
            role="system",
            action="reminder_run",
            module="whatsapp",
            entity_type="scheduler",
            details=f"appt={appts} vaccine={vaccines} invoice={invoices}"
        )
    except Exception as e:
        logger.error(f"run_reminder_jobs error: {e}")
        raise
    finally:
        conn.close()
