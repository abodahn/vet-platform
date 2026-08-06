# -*- coding: utf-8 -*-
"""The findings of the 6 August security audit, each pinned shut.

Twenty-five agents across seven dimensions, every finding re-checked by a
skeptic whose job was to refute it. Seven reported issues died in that review.
These are the nine that survived, and the two that mattered:

  1. An anonymous stranger could POST one booking to /api/public/book with a
     pet named "<img src=x onerror=...>" and it ran in the receptionist's
     browser when she opened the morning's bookings — inside her session,
     reading the CSRF token out of the page and acting as her. No account, no
     password, no CSRF token needed.

  2. A session cookie carried no clinic identity. One SECRET_KEY signs every
     clinic's cookies and get_db() routes by the subdomain, so a login at
     clinic A authenticated against clinic B's database at clinic A's role.
     Proved live before the fix. Harmless with one clinic; the end of the
     business on the day the second one signs.

The audit's own summary of what it could NOT test is in the report: no
authenticated write paths, no business-logic arithmetic, no load, no restore
drill, and no second clinic. These tests cover the fixes, not the gaps.
"""
import os
import re

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(rel):
    with open(os.path.join(_ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


# ── 1. stored XSS from the public booking form ───────────────────────────────

XSS = "<img src=x onerror=alert(1)>"


def test_the_public_booking_api_strips_markup(app):
    """Defence in depth. The templates escape now, but a name is a name and
    markup has no business reaching the database at all."""
    c = app.test_client()
    r = c.post("/api/public/book", json={
        "ownerName": f"Ali {XSS}",
        "mobile": "01000000001",
        "petName": f"Bobby {XSS}",
        "date": "2030-01-01",
    })
    assert r.status_code in (200, 201, 400, 429), r.status_code
    if r.status_code not in (200, 201):
        pytest.skip(f"booking refused ({r.status_code}); the storage path is "
                    "covered by the unit test below")

    import models.database as db
    conn = db.get_db()
    try:
        names = [x[0] for x in conn.execute(
            "SELECT pet_name FROM pets WHERE pet_name LIKE 'Bobby%'").fetchall()]
        owners = [x[0] for x in conn.execute(
            "SELECT full_name FROM owners WHERE full_name LIKE 'Ali%'").fetchall()]
    finally:
        conn.close()
    for v in names + owners:
        assert "<" not in v and ">" not in v, f"markup stored verbatim: {v!r}"


def test_the_cleaner_keeps_real_names_usable():
    """Refusing "O'Brien & Sons" to stop an attack nobody attempted is the
    wrong trade for a clinic."""
    import blueprints.public_api.routes as papi
    src = _read("blueprints/public_api/routes.py")
    assert "def _clean(" in src, "the input cleaner is gone"
    # Apostrophes and ampersands must survive; angle brackets and backticks must not.
    assert re.search(r'ch not in "<>`"', src), "the cleaner no longer strips markup chars"
    assert "&" not in re.search(r'ch not in "([^"]*)"', src).group(1), \
        "stripping & would break real client names"


@pytest.mark.parametrize("template,needle", [
    ("templates/launcher.html", "innerHTML"),
    ("templates/petshop/pos.html", "innerHTML"),
])
def test_the_dashboard_and_pos_no_longer_build_rows_from_strings(template, needle):
    """Both are fed by the public booking API. The launcher is the screen every
    staff member lands on after login — the widest blast radius in the app."""
    src = _read(template)
    for danger in ("innerHTML =\n        '<td>' +", "dd.innerHTML=data.map"):
        assert danger not in src, f"{template} still concatenates HTML from data"


def test_reception_escapes_the_pet_name_it_renders():
    """The one screen the receptionist opens to read a new booking."""
    src = _read("templates/appointments/reception.html")
    assert "escapeHtml(p.pet_name)" in src
    assert "escapeHtml(p.species)" in src
    assert "${p.pet_name}" not in src, "raw interpolation is back"


def test_the_escape_helper_is_global():
    """It existed, correct, in exactly one template. Three others did not get
    the memo, which is the argument for it living where every page loads it."""
    src = _read("static/js/platform.js")
    assert "window.escapeHtml" in src
    for ch in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;", "&#96;"):
        assert ch in src, f"escape table is missing {ch}"


# ── 2. one clinic's session must not open another clinic ─────────────────────

def test_the_session_records_which_clinic_it_was_issued_for():
    src = _read("blueprints/auth/routes.py")
    assert 'session["tenant"] = tenancy.current()' in src, \
        "a cookie with no clinic identity is a bearer token for every clinic"


def test_every_request_checks_the_session_belongs_to_this_clinic():
    """In before_request, not in login_required — it has to hold for a route
    that forgets the decorator too."""
    src = _read("app.py")
    i = src.index("def _security_checks")
    block = src[i:i + 2500]
    assert 'session.get("tenant")' in block
    assert "session.clear()" in block
    assert "tenancy.current()" in block


def test_a_session_from_another_clinic_is_cleared(app):
    """The behaviour, not the source: forge a session marked for a clinic that
    is not this request's, and confirm it does not stay logged in."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["user"] = {"id": 1, "username": "admin", "role": "super_admin"}
        s["tenant"] = "some-other-clinic"
    r = c.get("/", follow_redirects=False)
    assert r.status_code in (302, 401, 403), \
        f"a foreign clinic's session was accepted ({r.status_code})"
    with c.session_transaction() as s:
        assert not s.get("user"), "the foreign session survived"


def test_a_session_for_this_clinic_still_works(app):
    """The fix must not sign everyone out. In legacy single-clinic mode
    tenancy.current() is "" and the session carries "" — they match."""
    from models import tenancy
    c = app.test_client()
    with c.session_transaction() as s:
        s["user"] = {"id": 1, "username": "admin", "role": "super_admin"}
        s["tenant"] = tenancy.current()
    assert c.get("/").status_code == 200


def test_a_session_minted_before_the_fix_is_adopted_not_rejected(app):
    """Logging every user out on deploy is a support call for a one-person
    company. A cookie with no tenant has only ever been able to read the clinic
    it is being presented to."""
    c = app.test_client()
    with c.session_transaction() as s:
        s["user"] = {"id": 1, "username": "admin", "role": "super_admin"}
        s.pop("tenant", None)
    assert c.get("/").status_code == 200


# ── 3. Jinja does not escape backticks or ${ } ───────────────────────────────

def test_jinja_autoescaping_really_does_not_cover_template_literals():
    """The premise of the finding, asserted so nobody 'simplifies' the fix back
    into a backtick string later."""
    from markupsafe import escape
    assert str(escape("${alert(1)}")) == "${alert(1)}"
    assert "`" in str(escape("`;alert(1)//"))


def test_no_template_puts_jinja_output_inside_a_javascript_template_literal():
    """The general form of the bug, swept across all 177 templates.

    A `backtick` string is JavaScript, and Jinja escaping does not reach it —
    an item name of `${fetch(...)}` renders harmlessly in the stock list and
    then EXECUTES when the purchase-order form evaluates the literal. Checked
    as a pattern rather than one line, because the next person to write
    `...{{ x }}...` will not remember this.
    """
    import glob
    offenders = []
    for path in glob.glob(os.path.join(_ROOT, "templates", "**", "*.html"),
                          recursive=True):
        src = _read(os.path.relpath(path, _ROOT))
        for lit in re.findall(r"`[^`]*`", src, re.S):
            for expr in re.findall(r"\{\{(.*?)\}\}", lit, re.S):
                # url_for builds a server-side path; | tojson is the correct
                # escaper for putting data into JavaScript. Everything else in
                # a backtick is a value the server is pasting into JS source.
                if "url_for" in expr or "tojson" in expr:
                    continue
                rel = os.path.relpath(path, _ROOT)
                offenders.append(f"{rel}: {{{{{expr.strip()}}}}}")
    assert not offenders, (
        "Jinja output inside a JS template literal — autoescaping covers HTML "
        "but not ` or ${ }. Use | tojson: " + " | ".join(offenders))


def test_the_purchase_order_form_builds_its_select_in_the_dom():
    src = _read("templates/procurement/order_form.html")
    assert "var itemOptions = `" not in src, "the template literal is back"
    assert "| tojson" in src, "the data should reach JavaScript as JSON"
    assert "buildItemSelect" in src
    assert "o.textContent" in src, "option labels must be set as text, not markup"


# ── 4. the one |safe on unsanitised data ─────────────────────────────────────

def test_the_imaging_analysis_is_escaped_before_it_is_marked_safe():
    src = _read("templates/imaging/study_detail.html")
    assert "ai_analysis | e |" in src, "|safe on unsanitised text is back"


def test_no_template_marks_unescaped_user_text_as_safe():
    """A sweep, not a spot check: |safe applied directly to a value with no
    prior escape is the pattern that caused this."""
    import glob
    offenders = []
    for path in glob.glob(os.path.join(_ROOT, "templates", "**", "*.html"),
                          recursive=True):
        for n, line in enumerate(open(path, encoding="utf-8"), 1):
            if "| safe" not in line and "|safe" not in line:
                continue
            expr = line.split("|")[0]
            # Escaped first, or a macro/known-safe constant — both fine.
            if "| e " in line or "|e " in line or "tojson" in line:
                continue
            # A macro call renders its own markup and autoescapes the values it
            # interpolates -- {{ _render_messages(messages) | safe }} is the
            # correct way to use a macro, not a finding.
            if re.search(r"\{\{\s*_?\w+\s*\(", expr):
                continue
            if re.search(r"\{\{\s*[\w.]*(analysis|notes|description|name|text|body|message|content)",
                         expr, re.I):
                offenders.append(f"{os.path.relpath(path, _ROOT)}:{n}")
    assert not offenders, "unescaped user text marked safe: " + ", ".join(offenders)


# ── 5. reception must not read the clinic's accounts ─────────────────────────

@pytest.mark.parametrize("fn", ["expenses_list", "reports", "reports_export_xlsx"])
def test_the_money_reports_are_role_gated(fn):
    """The finance blueprint maps to the 'invoicing' grant, which reception
    holds so she can take payments. @login_required alone therefore showed her
    the P&L: live, rec.yasmine read Revenue 441,605 and Net 107,801."""
    src = _read("blueprints/finance/routes.py")
    i = src.index(f"def {fn}(")
    head = src[max(0, i - 400):i]
    assert "@role_required(" in head, f"finance.{fn} is still on bare @login_required"
    assert '"reception"' not in head.split("@role_required(")[-1].split(")")[0]


# ── 6. the client must not be able to choose its own IP ──────────────────────

def test_the_client_ip_comes_from_a_header_the_client_cannot_set(app):
    """nginx uses $proxy_add_x_forwarded_for, which appends the real peer to
    whatever the client sent — so the LEFTMOST value is attacker-supplied.
    Proved live: five logins carrying a forged address locked that address out
    for fifteen minutes and poisoned the audit log."""
    import models.security as sec
    with app.test_request_context(headers={
        "X-Forwarded-For": "203.0.113.77, 10.0.0.5",
        "X-Real-IP": "10.0.0.5",
    }):
        assert sec.get_real_ip() == "10.0.0.5"

    with app.test_request_context(headers={"X-Forwarded-For": "203.0.113.77, 10.0.0.5"}):
        assert sec.get_real_ip() == "10.0.0.5", "took the client-supplied hop"


# ── 7. login timing must not reveal whether a username exists ────────────────

def test_an_unknown_username_costs_the_same_as_a_wrong_password(app):
    """~0.26s vs ~0.59s was a reliable oracle for enumerating staff usernames
    anonymously. Asserted on the mechanism, not the clock — a timing assertion
    on a shared CI runner is a flaky test, not a security control."""
    import models.database as db
    assert hasattr(db, "_verify_dummy"), "the constant-time path is gone"
    src = _read("models/database.py")
    i = src.index("def verify_credentials(")
    block = src[i:i + 900]
    assert "_verify_dummy(password)" in block, \
        "verify_credentials returns early for an unknown user again"


def test_the_dummy_verification_actually_runs_bcrypt():
    """A no-op would leave the oracle wide open while looking fixed."""
    import time

    import models.database as db
    t0 = time.perf_counter()
    db._verify_dummy("anything")
    elapsed = time.perf_counter() - t0
    assert elapsed > 0.02, (
        f"the dummy check took {elapsed*1000:.1f}ms — bcrypt cost 12 should be "
        "tens of milliseconds; this is not costing what a real check costs")


# ── 8. the smaller findings, closed after the main four ──────────────────────

def test_the_waiting_room_gate_fails_closed(app, monkeypatch):
    """It used to fail OPEN when no token was configured, so that a clinic's TV
    did not go blank on deploy. The demo server was hand-deployed, never got a
    token, and served the day's pet names, times and doctors to anyone on the
    internet who found /appointments/api/queue.

    Provisioning mints a token for every real clinic, so the only thing this
    breaks is an install that skipped it — which is exactly what should break.
    """
    import blueprints.appointments.routes as ar
    monkeypatch.setattr(ar, "_waiting_room_token", lambda: "")
    monkeypatch.setattr(ar, "_TOKEN_WARNED", True)
    with app.test_request_context("/appointments/api/queue"):
        assert ar._waiting_room_authorized() is False


def test_the_waiting_room_still_opens_with_the_right_token(app, monkeypatch):
    import blueprints.appointments.routes as ar
    monkeypatch.setattr(ar, "_waiting_room_token", lambda: "s3cret")
    with app.test_request_context("/appointments/api/queue?t=s3cret"):
        assert ar._waiting_room_authorized() is True
    with app.test_request_context("/appointments/api/queue?t=wrong"):
        assert ar._waiting_room_authorized() is False


def test_staff_never_need_the_token(app, monkeypatch):
    """The gate is for the anonymous TV, not for the people who work there."""
    import blueprints.appointments.routes as ar
    monkeypatch.setattr(ar, "_waiting_room_token", lambda: "s3cret")
    with app.test_request_context("/appointments/api/queue") as ctx:
        from flask import session
        session["user"] = {"id": 1, "username": "admin"}
        assert ar._waiting_room_authorized() is True


@pytest.mark.parametrize("evil", [
    "http://evil.com", "//evil.com", "https:evil.com", "/\evil.com",
])
def test_the_language_and_theme_switches_cannot_redirect_off_site(app, evil):
    """Both are in _CSRF_EXEMPT, so this is the one open-redirect shape an
    attacker reaches without a token. The helper already existed and was used
    correctly by /auth/login; these two just never called it."""
    c = app.test_client()
    for path, data in (("/settings/lang", {"lang": "ar"}),
                       ("/settings/theme", {"theme": "medical"})):
        r = c.post(path, data={**data, "next": evil})
        loc = r.headers.get("Location", "")
        assert "evil.com" not in loc, f"{path} redirected to {loc}"


def test_an_hr_password_reset_obeys_the_same_rule_as_everywhere_else():
    """This accepted six characters while the rest of the app required twelve —
    on the one path that sets a password FOR somebody else."""
    src = _read("blueprints/hr/routes.py")
    assert "len(new_password) < 6" not in src, "the local six-character rule is back"
    assert "validate_password_strength(new_password)" in src

    import models.security as sec
    ok, _ = sec.validate_password_strength("abc123")
    assert not ok, "six characters should be refused"


def test_no_local_env_file_carries_a_key_that_is_in_git_history():
    """These are gitignored and never deployed, so the exposure only becomes
    real if someone stands up a second production box from this directory."""
    import re
    import subprocess
    for name in (".env", ".env.production", ".env.development"):
        path = os.path.join(_ROOT, name)
        if not os.path.exists(path):
            continue
        m = re.search(r"^PLATFORM_SECRET_KEY=(.+)$",
                      open(path, encoding="utf-8").read(), re.M)
        if not m or len(m.group(1).strip()) < 32:
            continue
        out = subprocess.run(["git", "log", "--oneline", "-S", m.group(1).strip(), "--all"],
                             cwd=_ROOT, capture_output=True, text=True).stdout
        assert not out.strip(), f"{name} carries a key that appears in git history"
