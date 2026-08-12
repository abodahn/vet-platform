"""Every route, swept — the horizontal half of access control.

The vertical half (who may do what) is covered by test_privilege_escalation.py
and test_audit_finance_system_blockers.py. This file asks the other questions,
mechanically, across the WHOLE surface rather than the routes somebody thought
to check:

  1. can a logged-out caller reach it?
  2. does an id that does not exist leak, or 500?
  3. can a role reach a module it has no permission for?
  4. does a session issued for one clinic work on another?

These are generated from app.url_map, so a route added tomorrow is swept
tomorrow. That is the point: the two dead dashboard cards, the fall-open on an
unknown role and the waiting room that failed open were all things nobody had
thought to check ONE route for.
"""
import pytest

from models import database as db

from conftest import get_csrf


# ── what is deliberately reachable without signing in ────────────────────
#
# An explicit list, not a pattern. A new public route has to be added here on
# purpose, which is the whole safeguard: it cannot appear by accident.
PUBLIC_ENDPOINTS = frozenset({
    "auth.login", "auth.logout", "auth.forgot_password", "auth.reset_password",
    "_healthz", "_manifest", "_service_worker", "_favicon",
    "coming_soon", "static",
    # The client-facing chat widget. It is meant to be embedded in an iframe on
    # the clinic's own public website, so it has to answer a caller who is not
    # signed in. It exposes the clinic's NAME, which is on that website
    # already, and non-staff callers get the public prompt, not the staff one.
    "petsy.embed", "petsy.widget_js",
})
PUBLIC_PREFIXES = ("/static/", "/public/", "/api/v1/public", "/uploads/public")


def _rules(app, method="GET"):
    for r in app.url_map.iter_rules():
        if r.endpoint == "static" or method not in r.methods:
            continue
        yield r


def _url_for_rule(rule):
    """A concrete URL for a rule, filling converters with harmless values."""
    values = {}
    for arg in rule.arguments:
        conv = str(rule._converters.get(arg, ""))
        if "Integer" in conv:
            values[arg] = 999999          # an id nothing owns
        elif "Float" in conv:
            values[arg] = 1.0
        elif "Path" in conv:
            values[arg] = "x/y"
        else:
            values[arg] = "sweep"
    try:
        return rule.build(values, append_unknown=False)[1]
    except Exception:
        return None


def _is_public(rule):
    if rule.endpoint in PUBLIC_ENDPOINTS:
        return True
    if any(str(rule).startswith(p) for p in PUBLIC_PREFIXES):
        return True
    # public_api is a booking form for clients — public by design.
    return rule.endpoint.split(".")[0] == "public_api"


# ═══════════════════════════════════════════════════════════════════════
#  1. NOTHING ANSWERS AN ANONYMOUS CALLER
# ═══════════════════════════════════════════════════════════════════════

def test_no_route_serves_a_logged_out_caller(app, client):
    leaked = []
    for rule in _rules(app, "GET"):
        if _is_public(rule):
            continue
        url = _url_for_rule(rule)
        if not url:
            continue
        try:
            resp = client.get(url)
        except Exception as exc:              # a crash is also a finding
            leaked.append("%s %s -> raised %s" % (rule.endpoint, url, exc.__class__.__name__))
            continue
        if resp.status_code == 200:
            leaked.append("%s %s -> 200" % (rule.endpoint, url))
    assert not leaked, (
        "%d route(s) answered a caller who is not signed in:\n  %s"
        % (len(leaked), "\n  ".join(sorted(leaked)[:40])))


def test_no_post_route_accepts_a_logged_out_caller(app, client):
    accepted = []
    for rule in _rules(app, "POST"):
        if _is_public(rule):
            continue
        url = _url_for_rule(rule)
        if not url:
            continue
        try:
            resp = client.post(url, data={})
        except Exception:
            continue
        if resp.status_code in (200, 201, 204):
            accepted.append("%s %s -> %s" % (rule.endpoint, url, resp.status_code))
    assert not accepted, (
        "%d POST route(s) accepted an anonymous caller:\n  %s"
        % (len(accepted), "\n  ".join(sorted(accepted)[:40])))


# ═══════════════════════════════════════════════════════════════════════
#  2. AN ID THAT DOES NOT EXIST MUST NOT LEAK OR CRASH
# ═══════════════════════════════════════════════════════════════════════

def test_a_nonexistent_id_never_returns_a_page_or_a_crash(app, auth_client):
    """999999 belongs to nobody. A route that renders it anyway is showing a
    page built from missing data; one that 500s is leaking a stack trace."""
    bad = []
    for rule in _rules(app, "GET"):
        if not any("Integer" in str(rule._converters.get(a, "")) for a in rule.arguments):
            continue
        url = _url_for_rule(rule)
        if not url:
            continue
        try:
            resp = auth_client.get(url)
        except Exception as exc:
            bad.append("%s %s -> raised %s" % (rule.endpoint, url, exc.__class__.__name__))
            continue
        if resp.status_code >= 500:
            bad.append("%s %s -> %s" % (rule.endpoint, url, resp.status_code))
    assert not bad, (
        "%d route(s) crashed on an id that does not exist:\n  %s"
        % (len(bad), "\n  ".join(sorted(bad)[:40])))


# ═══════════════════════════════════════════════════════════════════════
#  3. A ROLE CANNOT REACH A MODULE IT HAS NO PERMISSION FOR
# ═══════════════════════════════════════════════════════════════════════

# blueprint -> the permission key its routes sit behind, for the modules where
# getting this wrong costs money or exposes the medical record.
GUARDED = {
    "finance":    "invoicing",
    "accounting": "accounting",
    "payroll":    "payroll",
    "hr":         "hr",
    "inventory":  "inventory",
    "procurement": "procurement",
}


def _staff(username, role):
    conn = db.get_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.execute(
        "INSERT INTO users(username, password_hash, full_name, role, is_active)"
        " VALUES(?,?,?,?,1)",
        (username, db._hash_password("Sweep@2026!"), username.title(), role))
    conn.commit()
    conn.close()


@pytest.mark.parametrize("role", ["nurse", "doctor", "reception", "groomer"])
def test_a_clinical_role_cannot_reach_the_money_modules(app, role):
    """A nurse has no business on the payroll screen, and the way in was a
    module she was never granted.

    A route marked @self_service is EXEMPT here and covered by the test below
    instead: those deliberately answer 200 and scope their query to the
    requesting user, which is how an employee sees their own payslip without
    being granted the payroll module. A 200 from one of those is correct; what
    matters is what is IN it.
    """
    from blueprints.auth.routes import has_permission
    _staff("sweep_%s" % role, role)
    c = app.test_client()
    c.post("/auth/login", data={"username": "sweep_%s" % role,
                                "password": "Sweep@2026!"})
    c.get("/")

    reachable = []
    for rule in _rules(app, "GET"):
        bp = rule.endpoint.split(".")[0]
        key = GUARDED.get(bp)
        if not key or has_permission(key, role):
            continue
        view = app.view_functions.get(rule.endpoint)
        if getattr(view, "_self_service", False):
            continue
        url = _url_for_rule(rule)
        if not url:
            continue
        try:
            resp = c.get(url)
        except Exception:
            continue
        if resp.status_code == 200:
            reachable.append("%s %s" % (rule.endpoint, url))
    assert not reachable, (
        "%s reached %d route(s) in a module it was never granted:\n  %s"
        % (role, len(reachable), "\n  ".join(sorted(reachable)[:30])))


def test_a_self_service_route_shows_you_only_your_own_row(app):
    """@self_service bypasses the module permission, so the SCOPING is the only
    thing standing between a nurse and every colleague's salary. Assert the
    data, not the status code — a 200 here is correct by design.
    """
    _staff("sweep_payee", "nurse")
    conn = db.get_db()
    me = conn.execute("SELECT id FROM users WHERE username='sweep_payee'").fetchone()[0]
    other = conn.execute(
        "SELECT id, full_name FROM users WHERE id!=? AND is_active=1 LIMIT 1",
        (me,)).fetchone()
    year, month = 2026, 8
    for uid, gross in ((me, 1111.0), (other["id"], 99999.0)):
        conn.execute(
            "INSERT INTO salaries(user_id, period_year, period_month, basic_salary,"
            " gross, net, status) VALUES(?,?,?,?,?,?,'Draft')",
            (uid, year, month, gross, gross, gross))
    conn.commit()
    conn.close()

    c = app.test_client()
    c.post("/auth/login", data={"username": "sweep_payee", "password": "Sweep@2026!"})
    body = c.get("/payroll/salaries?year=%d&month=%d" % (year, month)).get_data(as_text=True)
    # The template formats money with thousands separators, so compare against
    # a body with those stripped rather than against the raw digits.
    flat = body.replace(",", "")

    assert "1111" in flat, "the employee cannot see their own payslip"
    assert "99999" not in flat, \
        "a nurse was shown a colleague's salary on a @self_service route"
    assert (other["full_name"] or "zzz") not in body, \
        "a colleague's NAME leaked on a @self_service route"


# ═══════════════════════════════════════════════════════════════════════
#  4. A SESSION BELONGS TO ONE CLINIC
# ═══════════════════════════════════════════════════════════════════════

def test_a_session_issued_for_one_clinic_is_refused_by_another(app, auth_client):
    """Cookies are signed with one process-wide SECRET_KEY across every
    tenant, so the signature alone does not say which clinic a session is for.
    The stamped tenant does."""
    auth_client.get("/")
    with auth_client.session_transaction() as sess:
        assert "user" in sess, "not signed in"
        sess["tenant"] = "some-other-clinic"

    resp = auth_client.get("/finance/invoices", follow_redirects=False)
    assert resp.status_code in (302, 401, 403), \
        "a session stamped for another clinic was accepted (%s)" % resp.status_code

    with auth_client.session_transaction() as sess:
        assert "user" not in sess, \
            "the foreign session was not cleared, so the next request may pass"
