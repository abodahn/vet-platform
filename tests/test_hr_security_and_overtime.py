# -*- coding: utf-8 -*-
"""HR's own security and overtime paths.

HR creates the logins a clinic actually uses and records the overtime it
actually pays, and both had defects the rest of the app had already fixed
elsewhere — which is the pattern in this module: a second implementation,
quietly weaker than the first.
"""
import ast
import inspect
import textwrap
from datetime import date

from conftest import get_csrf
from models import database as db

PW = "Str0ng!Pass9"


def _src(fn):
    """Function source with the docstring and comments stripped.

    Via the AST, because an assertion that greps raw source matches the comment
    explaining the very thing it asserts is absent — a mistake made four times
    in this codebase before this helper existed.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    node = tree.body[0]
    if (node.body and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)):
        node.body = node.body[1:]
    return ast.unparse(node)


# ── password hashing ─────────────────────────────────────────────────────────

def test_hr_no_longer_ships_its_own_password_hasher():
    """SHA-256 with a salt hardcoded in a public repo, one salt for every
    clinic. Fast by design, which is the opposite of what a password hash
    needs, and one rainbow table covers every deployment."""
    import blueprints.hr.routes as hr
    assert not hasattr(hr, "_hash"), \
        "HR has a local password hasher again"
    assert not hasattr(hr, "_SALT"), \
        "the shared hardcoded salt is back"


def test_a_staff_account_created_by_hr_gets_bcrypt(auth_client, app):
    auth_client.post("/hr/staff/new", data={
        "username": "hr_bcrypt_check", "password": PW, "confirm_password": PW,
        "full_name": "Bcrypt Check", "role": "nurse", "is_active": "1",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT password_hash FROM users WHERE username=?",
                           ("hr_bcrypt_check",)).fetchone()
        conn.close()
    assert row is not None, "the account was not created"
    assert row["password_hash"].startswith("$2b$"), \
        "HR wrote a %s hash instead of bcrypt" % (
            "legacy SHA-256" if len(row["password_hash"]) == 64 else "non-bcrypt")


def test_an_existing_sha256_account_can_still_log_in(app):
    """Nobody may be locked out by the switch — the legacy hash is accepted
    once and transparently upgraded."""
    import hashlib
    legacy = hashlib.sha256(("pah_platform_2026" + PW).encode()).hexdigest()
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM users WHERE username=?", ("hr_legacy_login",))
        conn.execute(
            "INSERT INTO users(username, password_hash, full_name, role, is_active)"
            " VALUES(?,?,?,?,1)", ("hr_legacy_login", legacy, "Legacy", "nurse"))
        conn.commit()
        assert db.verify_credentials("hr_legacy_login", PW), \
            "an account created before the switch can no longer log in"
        row = conn.execute("SELECT password_hash FROM users WHERE username=?",
                           ("hr_legacy_login",)).fetchone()
        conn.close()
    assert row["password_hash"].startswith("$2b$"), \
        "the legacy hash was not upgraded on successful login"


def test_hr_cannot_create_a_one_character_password(auth_client, app):
    """These are real logins to medical records and money."""
    auth_client.post("/hr/staff/new", data={
        "username": "hr_weak_pw", "password": "1", "confirm_password": "1",
        "full_name": "Weak", "role": "nurse", "is_active": "1",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM users WHERE username=?",
                         ("hr_weak_pw",)).fetchone()[0]
        conn.close()
    assert n == 0, "a clinical login was created with the password '1'"


# ── overtime ─────────────────────────────────────────────────────────────────

def _staff(app, username):
    with app.app_context():
        return db.create_user({"username": username, "password": PW,
                               "full_name": username, "role": "nurse"})


def _ot(app, uid):
    with app.app_context():
        conn = db.get_db()
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM overtime_log WHERE user_id=?", (uid,)).fetchall()]
        conn.close()
    return rows


def test_negative_overtime_is_refused(auth_client, app):
    """Approving one silently reduced the clinic's approved total, and through
    payroll, somebody's pay. A subtraction hidden inside an addition."""
    uid = _staff(app, "ot_negative")
    auth_client.post("/hr/staff/%d/overtime/add" % uid, data={
        "hours": "-5", "work_date": "2026-09-10", "reason": "test",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)
    assert _ot(app, uid) == [], "negative overtime was logged"


def test_zero_overtime_is_refused(auth_client, app):
    uid = _staff(app, "ot_zero")
    auth_client.post("/hr/staff/%d/overtime/add" % uid, data={
        "hours": "0", "work_date": "2026-09-10", "reason": "test",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)
    assert _ot(app, uid) == []


def test_a_mistyped_hours_box_does_not_crash(auth_client, app):
    uid = _staff(app, "ot_typo")
    r = auth_client.post("/hr/staff/%d/overtime/add" % uid, data={
        "hours": "5O", "work_date": "2026-09-10", "reason": "test",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)
    assert r.status_code != 500
    assert _ot(app, uid) == []


def test_double_clicking_does_not_pay_twice(auth_client, app):
    """Three clicks, triple pay, and nothing on screen to show it."""
    uid = _staff(app, "ot_double")
    for _ in range(3):
        auth_client.post("/hr/staff/%d/overtime/add" % uid, data={
            "hours": "2", "work_date": "2026-09-11", "reason": "late surgery",
            "_csrf_token": get_csrf(auth_client),
        }, follow_redirects=True)

    rows = _ot(app, uid)
    assert len(rows) == 1, "%d identical pending rows were written" % len(rows)


def test_a_genuine_second_entry_on_another_day_still_works(auth_client, app):
    """The guard must not block real overtime."""
    uid = _staff(app, "ot_genuine")
    for day in ("2026-09-12", "2026-09-13"):
        auth_client.post("/hr/staff/%d/overtime/add" % uid, data={
            "hours": "2", "work_date": day, "reason": "cover",
            "_csrf_token": get_csrf(auth_client),
        }, follow_redirects=True)
    assert len(_ot(app, uid)) == 2, "a second day's overtime was refused"


def test_the_headline_totals_are_not_capped_at_the_page_size():
    """They were summed in Python over a LIMIT 200 list, so a clinic past 200
    entries read a number a third under the truth, with nothing saying so."""
    import blueprints.hr.routes as hr
    body = _src(hr.overtime_list)
    assert "SUM(" in body.upper(), \
        "the totals are not computed in SQL over all matching rows"
    i_sum = body.upper().index("SUM(")
    i_limit = body.upper().index("LIMIT 200")
    assert i_sum > i_limit, \
        "the aggregate query must be separate from the capped list query"
    assert "total_records" in body, "the record count is still the page length"
