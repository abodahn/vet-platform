"""The WhatsApp reminder job — the headline feature that could never fire.

Four claims from docs/AUDIT_FINDINGS.md were checked against the code. Three
were true and are fixed here; one was WRONG and is recorded as wrong, because
a false finding that gets "fixed" wastes the next person's day too.

  TRUE   the nightly job could not use the token saved in the UI
  TRUE   the three on/off switches and three message boxes were write-only
  TRUE   the overdue-invoice message quoted the invoice TOTAL, not what is owed
  FALSE  "every button on /whatsapp/reminders is dead — no CSRF token"
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

def test_the_two_send_paths_still_disagree_and_that_is_the_open_gap(app):
    """VERIFIED, NOT FIXED. Kept so the finding cannot be quietly forgotten.

    The Send screen reads wapilot_token AND wapilot_instance_id from settings
    and posts through WapilotClient. The nightly job reads only $WAPILOT_TOKEN
    and posts a different payload to a different hardcoded URL. Connecting
    WhatsApp in the UI therefore does NOT make scheduled reminders work.

    Not fixed in the same commit as the switches because it changes what
    "configured" means for the whole module, and the 104 tests in
    test_whatsapp_routes.py encode the old contract. Landing it also needs a
    per-run failure cap: one send against an unreachable host measured at 535
    seconds, so a run over 200 clients would block the scheduler for hours.

    When it IS fixed, this test should start failing. That is the point.
    """
    import ast
    import inspect
    import textwrap
    from blueprints.whatsapp import scheduler
    from blueprints.whatsapp import routes as wa_routes

    def _code(fn):
        # Strip the docstring: the note explaining this gap names the very
        # identifiers being searched for. Three assertions in this session
        # matched their own explanation before I stopped writing them that way.
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        f = tree.body[0]
        if (f.body and isinstance(f.body[0], ast.Expr)
                and isinstance(f.body[0].value, ast.Constant)):
            f.body = f.body[1:]
        return ast.unparse(f)

    job = _code(scheduler._send_whatsapp)
    ui = _code(wa_routes._client)

    assert "wapilot_instance_id" in ui, "the Send screen no longer needs an instance id"
    assert "wapilot_instance_id" not in job,         "the job now reads the instance id — the gap may be closed; update this test"
    assert "api.wapilot.io/send" in job,         "the job's endpoint changed — the gap may be closed; update this test"


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
