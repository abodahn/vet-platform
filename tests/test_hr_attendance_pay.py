# -*- coding: utf-8 -*-
"""HR's attendance screen, which had its own arithmetic and its own bugs.

The attendance module was fixed first. HR turned out to carry a SECOND
implementation of the same calculation — four lines of subtraction in
hr_attendance_add — and every audit blocker in that module lived in it:

  * a night shift is negative (22:00 to 06:00 is -16 hours), so the `if diff > 0`
    guard left hours NULL and the whole night was worth zero overtime
  * the shift's unpaid break was never deducted, while payroll's standard hours
    DO subtract it — so every HR-entered day booked an extra hour of overtime
  * strptime("%H:%M") raises on the full-timestamp format most stored rows use
  * and a status correction arrived with both time boxes empty, because the form
    never carries the existing values, so "mark this day Late" erased the
    clock-in, the clock-out and the hours — and flashed success

payroll.bulk_generate reads hours_worked, so each of these was money.
"""
from datetime import date

import pytest

from models import database as db
from conftest import get_csrf

PW = "Str0ng!Pass9"


@pytest.fixture()
def night_shift(app):
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM staff_shifts WHERE shift_id IN"
                     " (SELECT id FROM shifts WHERE name LIKE 'HRT-%')")
        conn.execute("DELETE FROM shifts WHERE name LIKE 'HRT-%'")
        night = conn.execute(
            "INSERT INTO shifts(name, start_time, end_time, break_minutes,"
            " days_of_week, is_active) VALUES(?,?,?,?,?,1)",
            ("HRT-Night", "22:00", "06:00", 60, "0,1,2,3,4,5,6")).lastrowid
        day = conn.execute(
            "INSERT INTO shifts(name, start_time, end_time, break_minutes,"
            " days_of_week, is_active) VALUES(?,?,?,?,?,1)",
            ("HRT-Day", "08:00", "16:00", 60, "0,1,2,3,4")).lastrowid
        conn.commit()
        conn.close()
    yield {"night": night, "day": day}
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM staff_shifts WHERE shift_id IN (?,?)", (night, day))
        conn.execute("DELETE FROM shifts WHERE id IN (?,?)", (night, day))
        conn.commit()
        conn.close()


def _staff(app, username, shift_id):
    with app.app_context():
        uid = db.create_user({"username": username, "password": PW,
                              "full_name": username.replace("_", " ").title(),
                              "role": "nurse"})
        conn = db.get_db()
        conn.execute("INSERT INTO staff_shifts(user_id, shift_id, effective_from)"
                     " VALUES(?,?,?)", (uid, shift_id, "2020-01-01"))
        conn.commit()
        conn.close()
    return uid


def _rec(app, uid, wdate):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT check_in, check_out, hours_worked, status FROM attendance_records"
            " WHERE user_id=? AND work_date=?", (uid, wdate)).fetchone()
        conn.close()
    return dict(row) if row else None


def _post(auth_client, **kw):
    data = {"_csrf_token": get_csrf(auth_client)}
    data.update(kw)
    return auth_client.post("/hr/attendance/add", data=data, follow_redirects=True)


def test_a_night_shift_is_not_worth_zero(auth_client, app, night_shift):
    """22:00 -> 06:00 minus an hour's break is seven hours, not NULL."""
    uid = _staff(app, "hr_night_pay", night_shift["night"])
    _post(auth_client, user_id=uid, work_date="2026-09-01",
          check_in="22:00", check_out="06:00", status="Present")

    r = _rec(app, uid, "2026-09-01")
    assert r is not None, "the record was not written at all"
    assert r["hours_worked"] is not None, \
        "the night shift stored NULL hours — the whole night is worth no overtime"
    assert float(r["hours_worked"]) == 7.0, \
        "expected 7.0 hours, got %s" % r["hours_worked"]


def test_the_unpaid_break_is_deducted(auth_client, app, night_shift):
    """Payroll subtracts the break from the standard; this side must too, or
    the difference is paid as overtime every single day."""
    uid = _staff(app, "hr_break_pay", night_shift["day"])
    _post(auth_client, user_id=uid, work_date="2026-09-02",
          check_in="08:00", check_out="16:00", status="Present")

    r = _rec(app, uid, "2026-09-02")
    assert float(r["hours_worked"]) == 7.0, \
        "stored %s hours for an eight-hour day with an hour's break" % r["hours_worked"]


def test_correcting_the_status_does_not_erase_the_clock(auth_client, app, night_shift):
    """The form has no value on its time inputs, so a status fix submits blanks."""
    uid = _staff(app, "hr_status_pay", night_shift["day"])
    _post(auth_client, user_id=uid, work_date="2026-09-03",
          check_in="08:05", check_out="16:10", status="Present")
    before = _rec(app, uid, "2026-09-03")
    assert before["check_in"], "fixture did not take"

    # Exactly what the screen sends when somebody only changes the dropdown.
    _post(auth_client, user_id=uid, work_date="2026-09-03",
          check_in="", check_out="", status="Late")

    after = _rec(app, uid, "2026-09-03")
    assert after["status"] == "Late", "the correction did not apply"
    assert after["check_in"] == before["check_in"], \
        "the clock-in was erased by a status change"
    assert after["check_out"] == before["check_out"], \
        "the clock-out was erased by a status change"
    assert float(after["hours_worked"] or 0) == float(before["hours_worked"] or 0), \
        "the hours were zeroed by a status change"


def test_a_day_shift_ending_before_it_starts_is_not_paid(auth_client, app, night_shift):
    """A typo must not become a 22-hour day on a shift that cannot wrap."""
    uid = _staff(app, "hr_typo_pay", night_shift["day"])
    _post(auth_client, user_id=uid, work_date="2026-09-04",
          check_in="09:00", check_out="07:00", status="Present")

    r = _rec(app, uid, "2026-09-04")
    assert float(r["hours_worked"] or 0) == 0.0, \
        "a backwards day shift booked %s hours" % r["hours_worked"]


def test_hr_and_the_attendance_module_agree(app, night_shift):
    """Two implementations of one calculation is how they drifted apart."""
    import ast
    import inspect
    import textwrap
    from blueprints.hr import routes as hr

    # Unparsed from the AST, so COMMENTS ARE GONE. Searching the raw source
    # matched the word this asserts is absent inside the comment explaining
    # why it was removed. An assertion that passes or fails on its own
    # documentation proves nothing about the code, and I have now written
    # that bug four times in this codebase.
    tree = ast.parse(textwrap.dedent(inspect.getsource(hr.hr_attendance_add)))
    fn = tree.body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)):
        fn.body = fn.body[1:]
    body = ast.unparse(fn)

    assert '_calc_hours' in body, \
        'HR computes hours itself again instead of using the attendance helper'
    assert 'strptime' not in body, \
        'HR is parsing times by hand again - that is where the night-shift bug was'
