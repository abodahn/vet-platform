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


def _send_whatsapp(conn, phone: str, message: str, owner_id=None, template_name=""):
    """Insert into whatsapp_log (stub — real API token set via WAPILOT_TOKEN env var)."""
    import os, json
    status = "Pending"
    error = ""
    token = os.environ.get("WAPILOT_TOKEN", "")
    if token:
        try:
            import urllib.request
            payload = json.dumps({"phone": phone, "message": message}).encode()
            req = urllib.request.Request(
                "https://api.wapilot.io/send",
                data=payload,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = "Sent" if resp.status == 200 else "Failed"
        except Exception as e:
            status = "Failed"
            error = str(e)
    else:
        # NEVER report "Sent" for a message that was never transmitted. This
        # previously logged stub-mode sends as Sent, so a clinic saw a green
        # column of reminders that had not left the building — and then blamed
        # clients for not turning up. A reminder system that lies about
        # delivery is worse than having none.
        status = "Not Configured"
        error = ("WhatsApp is not connected — no API token is set. "
                 "Connect it under WhatsApp → Settings.")
        logger.warning(
            "WhatsApp reminder NOT sent to %s (%s): no token configured",
            phone, template_name or "reminder",
        )

    conn.execute(
        "INSERT INTO whatsapp_log(owner_id, phone, message, template_name, status, error, sent_at) VALUES(?,?,?,?,?,?,datetime('now'))",
        (owner_id, phone, message, template_name, status, error)
    )
    return status


def _appointment_reminders(conn) -> int:
    """Remind owners of appointments scheduled for tomorrow."""
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
        msg = (
            f"Dear {a['full_name']},\n"
            f"Reminder: {a['pet_name']} has a {a['appointment_type']} appointment tomorrow "
            f"({a['appt_date']} at {a['appt_start'] or 'TBD'}).\n"
            f"Please arrive 10 minutes early. Reply CONFIRM to confirm."
        )
        status = _send_whatsapp(conn, a["whatsapp_phone"], msg,
                                owner_id=a["owner_id"], template_name="appt_reminder")
        _mark_sent(conn, "appt_reminder", a["id"], "appointment")
        if status in ("Sent", "Pending"):
            sent += 1
    return sent


def _vaccine_reminders(conn) -> int:
    """Remind owners of vaccines due today or overdue by up to 7 days."""
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
        msg = (
            f"Dear {v['full_name']},\n"
            f"{'OVERDUE: ' if overdue else ''}{v['pet_name']} is {'overdue for' if overdue else 'due for'} "
            f"the {v['vaccine_name']} vaccine (due: {v['next_due_at']}).\n"
            f"Please book an appointment at your earliest convenience."
        )
        status = _send_whatsapp(conn, v["whatsapp_phone"], msg,
                                owner_id=v["owner_id"], template_name="vaccine_reminder")
        _mark_sent(conn, "vaccine_reminder", v["id"], "vaccination")
        if status in ("Sent", "Pending"):
            sent += 1
    return sent


def _invoice_reminders(conn) -> int:
    """Remind owners of invoices overdue by 3+ days."""
    today = date.today().isoformat()
    three_days_ago = (date.today() - timedelta(days=3)).isoformat()
    invoices = conn.execute("""
        SELECT inv.id, inv.invoice_number, inv.total, inv.due_date,
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
        msg = (
            f"Dear {inv['full_name']},\n"
            f"Invoice #{inv['invoice_number']} for {inv['total']:.2f} was due on {inv['due_date']} and remains unpaid.\n"
            f"Please contact us to settle your balance. Thank you."
        )
        status = _send_whatsapp(conn, inv["whatsapp_phone"], msg,
                                owner_id=inv["owner_id"], template_name="invoice_reminder")
        _mark_sent(conn, "invoice_reminder", inv["id"], "invoice")
        if status in ("Sent", "Pending"):
            sent += 1
    return sent


def run_reminder_jobs():
    """Entry point called by APScheduler at 09:00 daily."""
    conn = get_db()
    try:
        with conn:
            appts = _appointment_reminders(conn)
            vaccines = _vaccine_reminders(conn)
            invoices = _invoice_reminders(conn)
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
