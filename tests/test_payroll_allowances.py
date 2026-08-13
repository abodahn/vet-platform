# -*- coding: utf-8 -*-
"""Allowances that a clinic can define once per role.

"ويحسب رواتب وبدلات" — salaries AND allowances.

The per-employee half already worked. The half that did not: salary_grades held
only basic_salary and overtime_rate, so there was nowhere to say "housing
allowance = 500 EGP/month for doctors", and bulk_generate — the flow an owner
with 20 staff actually uses — passed a hardcoded 0. Twenty draft payslips, all
short by the allowance, each needing to be opened and corrected by hand.
"""
from datetime import date

from conftest import get_csrf


def _grade(app, role, basic, allowances, ot_rate=0):
    import models.database as db
    # payroll builds its tables lazily in a before_request hook, so a test that
    # writes to them before any payroll page is opened finds nothing there.
    from blueprints.payroll.routes import _ensure_tables
    with app.app_context():
        _ensure_tables()
        conn = db.get_db()
        conn.execute("DELETE FROM salary_grades WHERE role=?", (role,))
        conn.execute(
            "INSERT INTO salary_grades(role, basic_salary, allowances, overtime_rate)"
            " VALUES(?,?,?,?)", (role, basic, allowances, ot_rate))
        conn.commit()
        conn.close()


def _salary(app, user_id, year, month):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM salaries WHERE user_id=? AND period_year=? AND period_month=?",
            (user_id, year, month)).fetchone()
        conn.close()
    return dict(row) if row else None


def test_the_grade_can_carry_an_allowance(app):
    """The column that did not exist."""
    import models.database as db
    _grade(app, "doctor", 8000, 500)
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT allowances FROM salary_grades WHERE role='doctor'").fetchone()
        conn.close()
    assert float(row["allowances"]) == 500


def test_bulk_generate_pays_the_role_allowance(auth_client, app):
    import models.database as db
    uid = None
    with app.app_context():
        uid = db.create_user({"username": "vet_allow", "password": "Str0ng!Pass9",
                              "full_name": "Dr Allowance", "role": "doctor"})
    _grade(app, "doctor", 8000, 500)

    year, month = 2031, 4          # a period no other test touches
    auth_client.post("/payroll/bulk-generate",
                     data={"year": year, "month": month,
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)

    row = _salary(app, uid, year, month)
    assert row is not None, "bulk generate produced no payslip"
    assert float(row["allowances"]) == 500, \
        "the role allowance was not applied (got %s)" % row["allowances"]
    assert float(row["gross"]) >= 8500, \
        "gross %s does not include the allowance" % row["gross"]


def test_a_role_with_no_allowance_is_unaffected(auth_client, app):
    import models.database as db
    with app.app_context():
        uid = db.create_user({"username": "nurse_allow", "password": "Str0ng!Pass9",
                              "full_name": "Nurse NoAllowance", "role": "nurse"})
    _grade(app, "nurse", 4000, 0)

    year, month = 2031, 5
    auth_client.post("/payroll/bulk-generate",
                     data={"year": year, "month": month,
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)

    row = _salary(app, uid, year, month)
    assert row is not None
    assert float(row["allowances"]) == 0
    assert float(row["gross"]) == 4000


def test_the_grades_screen_can_set_it(auth_client, app):
    """Otherwise the column exists and nobody can reach it."""
    r = auth_client.get("/payroll/grades")
    assert r.status_code == 200
    body = r.data.decode("utf-8", errors="replace")
    assert 'name="allow_doctor"' in body, "the grades form has no allowance box"

    auth_client.post("/payroll/grades",
                     data={"basic_doctor": "9000", "allow_doctor": "750",
                           "ot_doctor": "50", "notes_doctor": "",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)

    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT allowances FROM salary_grades WHERE role='doctor'").fetchone()
        conn.close()
    assert row and float(row["allowances"]) == 750, "the allowance did not save"


def test_payroll_forms_use_the_csrf_field_the_validator_reads():
    """These carried name="csrf_token"; validate_csrf reads _csrf_token.

    They only ever saved because platform.js injects the real token into every
    POST form. One disabled script and every payroll form would have 400'd,
    and the hidden field sitting there made it look handled.
    """
    import glob
    import io
    for path in glob.glob("templates/payroll/*.html"):
        src = io.open(path, encoding="utf-8").read()
        assert 'name="csrf_token"' not in src, \
            "%s posts a token under a name nothing validates" % path
