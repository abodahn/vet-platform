"""The WhatsApp reminder job — the headline feature that could never fire.

Four claims from docs/AUDIT_FINDINGS.md were checked against the code. Three
were true and are fixed here; one was WRONG and is recorded as wrong, because
a false finding that gets "fixed" wastes the next person's day too.

  TRUE   the nightly job could not use the token saved in the UI
  TRUE   the three on/off switches and three message boxes were write-only
  TRUE   the overdue-invoice message quoted the invoice TOTAL, not what is owed
  FALSE  "every button on /whatsapp/reminders is dead — no CSRF token"

The first of those was left open at the time, with a test written to fail on
the day it closed. It is closed now: the job and the Send screen share one
transport, and a dead connection is abandoned after a handful of failures
instead of holding the scheduler for hours.
"""
import pytest

from models import database as db


def _set(key, value, category="whatsapp"):
    conn = db.get_db()
    conn.execute("DELETE FROM settings WHERE key=?", (key,))
    conn.execute("INSERT INTO settings(key, value, category) VALUES(?,?,?)",
                 (key, value, category))
    conn.commit()
    conn.close()


def _clear(*keys):
    conn = db.get_db()
    for k in keys:
        conn.execute("DELETE FROM settings WHERE key=?", (k,))
    conn.commit()
    conn.close()


# ── ONE send path ────────────────────────────────────────────────────────

def test_the_nightly_job_and_the_send_screen_use_one_transport(app):
    """The gap that made scheduled reminders undeliverable, now closed.

    This test used to assert the OPPOSITE — that the two paths disagreed — and
    was written to start failing on the day it was fixed. That day is this one,
    so it now pins the convergence instead.

    What was wrong: the job read $WAPILOT_TOKEN alone and POSTed
    {"phone","message"} with a Bearer header to https://api.wapilot.io/send,
    while every manual Send button posts {"chat_id","text"} with a `token`
    header to https://api.wapilot.net/api/v2/{instance}/send-message. A clinic
    that connected WhatsApp the only documented way got a working Send Center
    and a nightly job that logged "Not Configured" for every reminder.
    """
    import ast
    import inspect
    import textwrap
    from blueprints.whatsapp import scheduler
    from blueprints.whatsapp import routes as wa_routes

    def _code(fn):
        # Strip the docstring: the note explaining a gap names the very
        # identifiers being searched for, and an assertion that matches its own
        # explanation proves nothing.
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        f = tree.body[0]
        if (f.body and isinstance(f.body[0], ast.Expr)
                and isinstance(f.body[0].value, ast.Constant)):
            f.body = f.body[1:]
        return ast.unparse(f)

    job = _code(scheduler._make_sender)
    ui = _code(wa_routes._client)

    assert "wapilot_instance_id" in ui, "the Send screen no longer needs an instance id"
    assert "wapilot_instance_id" in job, \
        "the nightly job still ignores the instance id saved in Settings"
    assert "wapilot_token" in job, \
        "the nightly job still ignores the token saved in Settings"
    assert "WapilotClient" in job, \
        "the job builds its own transport instead of the one the UI uses"

    send = _code(scheduler._send_whatsapp)
    assert "api.wapilot.io" not in send and "api.wapilot.io" not in job, \
        "the old hardcoded endpoint is still in the job"
    assert "urllib" not in send, \
        "the job still hand-rolls its own HTTP request"


def test_a_dead_connection_does_not_burn_the_whole_night(app):
    """One send against an unreachable host was measured at 535 SECONDS.

    Unbounded, a clinic with 200 clients and a dead instance would hold the
    scheduler thread for most of a day and the next morning's run would queue
    behind it.
    """
    from blueprints.whatsapp import scheduler

    class _DeadClient:
        calls = 0

        def send_message(self, chat_id, text, **kw):
            _DeadClient.calls += 1
            return {}, "urlopen error [Errno 11001] getaddrinfo failed"

    sender = scheduler._Sender(_DeadClient())
    conn = db.get_db()
    try:
        for _ in range(50):
            scheduler._send_whatsapp(conn, "01000000001", "hi", sender=sender)
        conn.commit()
        # Every call logs a row, and this one makes fifty. The suite shares one
        # database, so leaving them behind pushed another file's row out of the
        # control centre's "recent log" window and failed a test that had
        # nothing to do with this one.
        conn.execute("DELETE FROM whatsapp_log WHERE phone='01000000001'")
        conn.commit()
    finally:
        conn.close()

    assert sender.gave_up, "the run never gave up on a dead connection"
    assert _DeadClient.calls <= scheduler._MAX_CONSECUTIVE_FAILURES, \
        "kept dialling a dead host %d times" % _DeadClient.calls


def test_one_bad_number_does_not_abandon_the_run(app):
    """A single wrong number is not the same as the transport being down."""
    from blueprints.whatsapp import scheduler

    class _FlakyClient:
        def __init__(self):
            self.n = 0

        def send_message(self, chat_id, text, **kw):
            self.n += 1
            if self.n == 1:
                return {}, "HTTP 400: invalid chat_id"
            return {"ok": True}, ""

    sender = scheduler._Sender(_FlakyClient())
    conn = db.get_db()
    try:
        first = scheduler._send_whatsapp(conn, "bad", "hi", sender=sender)
        rest = [scheduler._send_whatsapp(conn, "0100000000%d" % i, "hi", sender=sender)
                for i in range(3)]
        conn.commit()
        conn.execute("DELETE FROM whatsapp_log WHERE phone='bad' OR phone LIKE '010000000%'")
        conn.commit()
    finally:
        conn.close()

    assert first == "Failed"
    assert rest == ["Sent", "Sent", "Sent"], \
        "one bad number stopped the other reminders: %r" % (rest,)
    assert not sender.gave_up


def test_an_unconnected_clinic_is_never_told_a_reminder_was_sent(app):
    from blueprints.whatsapp import scheduler

    sender = scheduler._Sender(None, "WhatsApp is not connected — no API token is set.")
    conn = db.get_db()
    try:
        status = scheduler._send_whatsapp(conn, "01000000002", "hi", sender=sender)
        conn.commit()
        conn.execute("DELETE FROM whatsapp_log WHERE phone='01000000002'")
        conn.commit()
    finally:
        conn.close()
    assert status == "Not Configured", \
        "a message that never left the building was logged as %r" % status


def test_an_unconfigured_clinic_is_told_so_and_nothing_is_claimed_sent(app):
    """A reminder system that lies about delivery is worse than none."""
    from blueprints.whatsapp import scheduler
    _clear("wapilot_token", "wapilot_instance_id")

    conn = db.get_db()
    status = scheduler._send_whatsapp(conn, "01000000000", "hello",
                                      owner_id=None, template_name="t")
    conn.commit()
    row = conn.execute(
        "SELECT status, error FROM whatsapp_log ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    assert status == "Not Configured"
    assert row["status"] == "Not Configured", "an unsent message was logged as sent"
    assert "not connected" in (row["error"] or "").lower()


# ── the switches actually switch ─────────────────────────────────────────

@pytest.mark.parametrize("key,fn", [
    ("reminder_appt_enabled",    "_appointment_reminders"),
    ("reminder_vaccine_enabled", "_vaccine_reminders"),
    ("reminder_invoice_enabled", "_invoice_reminders"),
])
def test_switching_a_reminder_off_actually_stops_it(app, key, fn):
    """These were write-only: wa_settings saved them and the job read none."""
    from blueprints.whatsapp import scheduler
    _set(key, "0")
    conn = db.get_db()
    try:
        assert getattr(scheduler, fn)(conn) == 0, \
            "%s still ran with %s switched off" % (fn, key)
    finally:
        conn.close()
        _clear(key)


def test_a_reminder_is_on_unless_it_was_switched_off(app):
    """A clinic that has never opened Settings must still get reminders."""
    from blueprints.whatsapp import scheduler
    _clear("reminder_appt_enabled")
    conn = db.get_db()
    try:
        assert scheduler._enabled(conn, "reminder_appt_enabled") is True
    finally:
        conn.close()


# ── the clinic's own wording is used ─────────────────────────────────────

def test_the_saved_message_template_is_the_one_that_goes_out(app):
    from blueprints.whatsapp import scheduler
    out = scheduler._render(
        "Ahlan {owner}, {pet} is due for {vaccine} on {date}.",
        "BUILT-IN", owner="Dina", pet="Leo", vaccine="Rabies", date="2026-09-01")
    assert out == "Ahlan Dina, Leo is due for Rabies on 2026-09-01."


def test_a_broken_placeholder_falls_back_instead_of_killing_the_run(app):
    """Text somebody typed must not stop the whole nightly job."""
    from blueprints.whatsapp import scheduler
    out = scheduler._render("Dear {wizard}", "BUILT-IN", owner="Dina")
    assert out == "BUILT-IN"


def test_an_empty_template_uses_the_built_in_wording(app):
    from blueprints.whatsapp import scheduler
    assert scheduler._render("", "BUILT-IN", owner="x") == "BUILT-IN"
    assert scheduler._render(None, "BUILT-IN", owner="x") == "BUILT-IN"


# ── the overdue message quotes what is OWED ──────────────────────────────

def test_the_overdue_message_quotes_the_balance_not_the_invoice_total(app):
    """A client who had already paid most of a large invoice was chased for the
    whole amount, so the clinic looked like it had lost the payment."""
    import inspect
    from blueprints.whatsapp import scheduler
    src = inspect.getsource(scheduler._invoice_reminders)
    assert "due_amount" in src, "the query does not even fetch what is owed"
    assert "{inv['total']:.2f} was due" not in src, \
        "the message still quotes the invoice total"
    assert "owed" in src


# ── the claim that was WRONG ─────────────────────────────────────────────

def test_the_reminder_buttons_were_never_actually_dead(app, auth_client):
    """Recorded because the finding was wrong, and the reasoning is worth keeping.

    The audit said: "Every button on /whatsapp/reminders is dead — no CSRF
    token in the form, so both actions 403." The template genuinely has no
    token in its markup. But base.html carries <meta name="csrf-token"> and
    app.min.js installs a capture-phase submit listener that injects the token
    into any POST form lacking one. The agent read the template and never ran
    the page.

    An explicit token has since been added to both forms anyway — it works
    with JavaScript disabled, and defence in depth on a money screen is cheap.
    """
    body = auth_client.get("/whatsapp/reminders").get_data(as_text=True)
    assert 'name="csrf-token"' in body, "the global token meta tag is gone"
    assert "app.min.js" in body, "the bundle that injects the token is not loaded"
    # The per-row "Mark Sent" form only renders when there ARE reminders, so on
    # an empty page the count is 1 (the send modal). Check the page for at
    # least one and the template source for both.
    assert body.count('name="_csrf_token"') >= 1, \
        "the explicit tokens added to the forms are gone"
    import io as _io
    tpl = _io.open("templates/whatsapp/reminders.html", encoding="utf-8").read()
    assert tpl.count('name="_csrf_token"') >= 2, \
        "one of the two forms lost its explicit token"
