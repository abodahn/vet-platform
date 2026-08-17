# -*- coding: utf-8 -*-
"""Attendance arithmetic, from the angle that matters: what it pays people.

These stopped being cosmetic when payroll started reading attendance.
bulk_generate takes overtime_hours and absent_days straight from
_get_attendance_summary and turns them into money:

    absence_deduction = (absent_days / working_days) * basic

So every bug below was a wrong salary, every month, for every employee.

The one that reached furthest was the working week. `_business_days` counted
Monday to Friday, which is the American week, in a product sold only in Egypt —
where the weekend is Friday and Saturday. Friday was therefore a working day
nobody attended (marked absent, docked ~4 times a month) and Sunday, a normal
working day, was never counted at all.
"""
from datetime import date, timedelta

import pytest

from models import database as db
from conftest import get_csrf


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def shifts(app):
    """A day shift and a real night shift, both on the Egyptian week.

    T-Day is made the ONLY active shift for the duration, because the
    clinic-wide fallback is "first active shift by id" and the suite shares one
    database: test_attendance_integrity.py does DELETE FROM shifts and inserts
    its own, so whichever row happens to be lowest-id-and-active decides what
    these assertions see. Pinning it keeps the test about the calculation
    instead of about which file ran first. Restored afterwards so the pinning
    does not become the next file's pollution.
    """
    with app.app_context():
        conn = db.get_db()
        was_active = [r["id"] for r in conn.execute(
            "SELECT id FROM shifts WHERE is_active=1").fetchall()]
        # staff_shifts references shifts, so the roster rows go first.
        conn.execute("DELETE FROM staff_shifts WHERE shift_id IN"
                     " (SELECT id FROM shifts WHERE name LIKE 'T-%')")
        conn.execute("DELETE FROM shifts WHERE name LIKE 'T-%'")
        conn.execute("UPDATE shifts SET is_active=0")
        day = conn.execute(
            "INSERT INTO shifts(name, start_time, end_time, break_minutes,"
            " days_of_week, is_active) VALUES(?,?,?,?,?,1)",
            ("T-Day", "08:00", "16:00", 60, "0,1,2,3,4")).lastrowid
        night = conn.execute(
            "INSERT INTO shifts(name, start_time, end_time, break_minutes,"
            " days_of_week, is_active) VALUES(?,?,?,?,?,1)",
            ("T-Night", "22:00", "06:00", 60, "0,1,2,3,4,5,6")).lastrowid
        conn.commit()
        conn.close()

    yield {"day": day, "night": night}

    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM staff_shifts WHERE shift_id IN (?,?)", (day, night))
        conn.execute("DELETE FROM shifts WHERE id IN (?,?)", (day, night))
        for sid in was_active:
            conn.execute("UPDATE shifts SET is_active=1 WHERE id=?", (sid,))
        conn.commit()
        conn.close()


def _staff(app, username, full_name, shift_id=None, role="nurse"):
    with app.app_context():
        uid = db.create_user({"username": username, "password": "Str0ng!Pass9",
                              "full_name": full_name, "role": role})
        if shift_id:
            conn = db.get_db()
            conn.execute(
                "INSERT INTO staff_shifts(user_id, shift_id, effective_from)"
                " VALUES(?,?,?)", (uid, shift_id, "2020-01-01"))
            conn.commit()
            conn.close()
    return uid


# ── the working week ─────────────────────────────────────────────────────────

def test_friday_is_not_a_working_day_and_sunday_is(app, shifts):
    """The single most expensive line in the module.

    2026-08-14 is a Friday and 2026-08-16 is a Sunday.
    """
    from blueprints.attendance.routes import _business_days
    with app.app_context():
        conn = db.get_db()
        friday = _business_days("2026-08-14", "2026-08-14", conn)
        saturday = _business_days("2026-08-15", "2026-08-15", conn)
        sunday = _business_days("2026-08-16", "2026-08-16", conn)
        conn.close()

    assert friday == 0, "Friday still counts as a working day — everyone is " \
                        "marked absent on their day off and docked for it"
    assert saturday == 0, "Saturday still counts as a working day"
    assert sunday == 1, "Sunday is a working day in Egypt and is not being counted"


def test_a_full_week_is_five_days_sunday_to_thursday(app, shifts):
    from blueprints.attendance.routes import _business_days
    with app.app_context():
        conn = db.get_db()
        n = _business_days("2026-08-16", "2026-08-22", conn)   # Sun..Sat
        conn.close()
    assert n == 5, "expected Sun-Thu, got %d days" % n


def test_the_week_comes_from_the_shift_not_from_code(app, shifts):
    """A clinic that opens Saturdays must be able to say so."""
    from blueprints.attendance.routes import _business_days
    with app.app_context():
        conn = db.get_db()
        # T-Day is already the only active shift (see the fixture), so this only
        # has to change its days. Blanket-reactivating everything afterwards is
        # what would leak into the next file.
        conn.execute("UPDATE shifts SET days_of_week=? WHERE id=?",
                     ("0,1,2,3,4,6", shifts["day"]))
        conn.execute("UPDATE shifts SET is_active=0 WHERE id=?", (shifts["night"],))
        conn.commit()
        n = _business_days("2026-08-16", "2026-08-22", conn)
        conn.close()
    assert n == 6, "days_of_week is still ignored — the week is hardcoded"


def test_sunday_is_understood_however_it_was_written(app, shifts):
    """The seeded shifts write Sunday as 7; the Shifts form writes it as 0."""
    from blueprints.attendance.routes import working_weekdays
    with app.app_context():
        conn = db.get_db()
        # Only T-Day and T-Night are active here, and working_weekdays takes the
        # lowest-id active row — so both must stand down for T-Seeded to be the
        # one under test. They are put back before leaving.
        conn.execute("UPDATE shifts SET is_active=0 WHERE id IN (?,?)",
                     (shifts["day"], shifts["night"]))
        sid = conn.execute(
            "INSERT INTO shifts(name, start_time, end_time, days_of_week, is_active)"
            " VALUES('T-Seeded','09:00','17:00','6,7',1)").lastrowid
        conn.commit()
        days = working_weekdays(conn)
        conn.execute("DELETE FROM shifts WHERE id=?", (sid,))
        conn.execute("UPDATE shifts SET is_active=1 WHERE id IN (?,?)",
                     (shifts["day"], shifts["night"]))
        conn.commit()
        conn.close()
    assert days == frozenset({6, 0}), \
        "a shift stored as '6,7' (Sat+Sun) read as %r" % (set(days),)


def test_a_public_holiday_still_does_not_count(app, shifts):
    from blueprints.attendance.routes import _business_days
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM public_holidays WHERE holiday_date=?", ("2026-08-17",))
        conn.execute("INSERT INTO public_holidays(holiday_date, name) VALUES(?,?)",
                     ("2026-08-17", "Test Holiday"))
        conn.commit()
        n = _business_days("2026-08-16", "2026-08-17", conn)   # Sun + Mon(holiday)
        conn.execute("DELETE FROM public_holidays WHERE holiday_date=?", ("2026-08-17",))
        conn.commit()
        conn.close()
    assert n == 1


# ── each employee against their own shift ────────────────────────────────────

def test_a_night_nurse_clocking_in_at_2200_is_not_late(app, shifts):
    from blueprints.attendance.routes import status_for_checkin
    uid = _staff(app, "night_nurse_att", "Night Nurse", shifts["night"])
    with app.app_context():
        conn = db.get_db()
        status, late_by = status_for_checkin(conn, "22:00", uid)
        conn.close()
    assert status == "Present", \
        "the night nurse is marked Late by %d minutes against somebody else's shift" % late_by


def test_the_day_desk_is_still_late_when_it_is_late(app, shifts):
    """The fix must not make lateness unreportable."""
    from blueprints.attendance.routes import status_for_checkin
    uid = _staff(app, "day_desk_att", "Day Desk", shifts["day"])
    with app.app_context():
        conn = db.get_db()
        on_time, _ = status_for_checkin(conn, "08:05", uid)
        late, mins = status_for_checkin(conn, "09:30", uid)
        conn.close()
    assert on_time == "Present", "inside the grace period is not late"
    assert late == "Late" and mins > 0


def test_an_unrostered_employee_still_gets_an_answer(app, shifts):
    """staff_shifts is empty on the live demo — this is the common path."""
    from blueprints.attendance.routes import default_shift
    with app.app_context():
        conn = db.get_db()
        s = default_shift(conn, 999999)
        conn.close()
    assert s["start_time"] and s["end_time"]


# ── the auto-close that paid a night as an hour ──────────────────────────────

def test_a_forgotten_night_shift_closes_at_0600_not_2200(app, shifts):
    """It used to close at the DAY shift's end, i.e. before the check-in, and
    the "arrived after the shift ended" guard then collapsed it to zero."""
    from blueprints.attendance.routes import close_forgotten_checkouts
    uid = _staff(app, "night_forgot_att", "Night Forgot", shifts["night"])
    work_date = "2026-08-10"
    with app.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, check_in, status)"
            " VALUES(?,?,?,'Present')", (uid, work_date, "22:00"))
        conn.commit()
        close_forgotten_checkouts(conn, work_date)
        row = conn.execute(
            "SELECT check_out, hours_worked FROM attendance_records"
            " WHERE user_id=? AND work_date=?", (uid, work_date)).fetchone()
        conn.close()

    assert row["check_out"] == "06:00", \
        "the night record closed at %r" % row["check_out"]
    assert float(row["hours_worked"]) == 7.0, \
        "an eight-hour night minus an hour's break paid %s hours" % row["hours_worked"]


def test_a_forgotten_day_shift_still_closes_at_its_own_end(app, shifts):
    from blueprints.attendance.routes import close_forgotten_checkouts
    uid = _staff(app, "day_forgot_att", "Day Forgot", shifts["day"])
    work_date = "2026-08-11"
    with app.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, check_in, status)"
            " VALUES(?,?,?,'Present')", (uid, work_date, "08:00"))
        conn.commit()
        close_forgotten_checkouts(conn, work_date)
        row = conn.execute(
            "SELECT check_out, hours_worked FROM attendance_records"
            " WHERE user_id=? AND work_date=?", (uid, work_date)).fetchone()
        conn.close()
    assert row["check_out"] == "16:00"
    assert float(row["hours_worked"]) == 7.0


# ── the lunch break that became overtime ─────────────────────────────────────

def test_a_normal_day_earns_no_overtime(app, shifts):
    """08:00-16:00 on an eight-hour shift with an hour's break is not overtime.

    Check-out defaulted break_minutes to 0, storing 8.0 hours, while payroll
    subtracted the shift's 60-minute break from the standard to get 7.0 — and
    paid the 1.0 difference. Every hand-clocked day, ~22 hours a month.
    """
    from blueprints.payroll.routes import _get_attendance_summary
    uid = _staff(app, "ot_check_att", "OT Check", shifts["day"])
    with app.app_context():
        conn = db.get_db()
        # A month of ordinary days, recorded the way check-out records them
        # once the break defaults to the shift's own break.
        for day in range(16, 21):                      # 2026-08-16..20, Sun-Thu
            conn.execute(
                "INSERT INTO attendance_records(user_id, work_date, check_in,"
                " check_out, break_minutes, hours_worked, status)"
                " VALUES(?,?,?,?,?,?,'Present')",
                (uid, "2026-08-%02d" % day, "08:00", "16:00", 60, 7.0))
        conn.commit()
        summary = _get_attendance_summary(conn, uid, 2026, 8)
        conn.close()

    assert summary["overtime_hours"] == 0.0, \
        "a normal day booked %s hours of overtime" % summary["overtime_hours"]


def test_real_overtime_is_still_paid(app, shifts):
    from blueprints.payroll.routes import _get_attendance_summary
    uid = _staff(app, "ot_real_att", "OT Real", shifts["day"])
    with app.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, check_in,"
            " check_out, break_minutes, hours_worked, status)"
            " VALUES(?,?,?,?,?,?,'Present')",
            (uid, "2026-09-16", "08:00", "19:00", 60, 10.0))
        conn.commit()
        summary = _get_attendance_summary(conn, uid, 2026, 9)
        conn.close()
    assert summary["overtime_hours"] == 3.0, \
        "expected 3h over a 7h standard, got %s" % summary["overtime_hours"]


# ── the absence divisor ──────────────────────────────────────────────────────

def test_one_absence_is_not_half_a_months_pay(app, shifts):
    """working_days was "however many rows exist", so an employee with two
    records — one absent — was docked half their basic salary."""
    from blueprints.payroll.routes import _get_attendance_summary
    uid = _staff(app, "absence_att", "Absence Test", shifts["day"])
    with app.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, check_in,"
            " check_out, hours_worked, status) VALUES(?,?,?,?,?,'Present')",
            (uid, "2026-10-18", "08:00", "16:00", 7.0))
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, status)"
            " VALUES(?,?,'Absent')", (uid, "2026-10-19"))
        conn.commit()
        summary = _get_attendance_summary(conn, uid, 2026, 10)
        conn.close()

    assert summary["absent_days"] == 1
    assert summary["working_days"] >= 20, \
        "the absence deduction divides by %d days, so one absence costs " \
        "1/%d of basic salary" % (summary["working_days"], summary["working_days"])


# ── the break as it is actually WRITTEN, not as a fixture supplies it ────────

def test_checking_out_records_the_shifts_break_not_zero(app, shifts):
    """The fix at its source.

    Nobody types the break box, so it arrived as 0 and hours_worked included
    the unpaid lunch. Asserting the stored break rather than the hours, because
    check-out stamps the wall clock and the hours depend on when the suite runs.
    """
    uid = _staff(app, "brk_write_att", "Break Writer", shifts["day"])
    today = date.today().isoformat()
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM attendance_records WHERE user_id=?", (uid,))
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, check_in, status)"
            " VALUES(?,?,?,'Present')", (uid, today, "08:00"))
        conn.commit()
        conn.close()

    c = app.test_client()
    c.post("/auth/login", data={"username": "brk_write_att",
                                "password": "Str0ng!Pass9"}, follow_redirects=True)
    c.post("/attendance/checkin",
           data={"action": "checkout", "_csrf_token": get_csrf(c)},
           follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT break_minutes FROM attendance_records WHERE user_id=? AND work_date=?",
            (uid, today)).fetchone()
        conn.close()
    assert int(row["break_minutes"]) == 60, \
        "check-out stored a %s-minute break; the shift's unpaid hour is " \
        "then paid as overtime" % row["break_minutes"]


def test_an_explicit_break_still_wins(app, shifts):
    """A manager recording a genuinely different break must be believed."""
    uid = _staff(app, "brk_explicit_att", "Break Explicit", shifts["day"])
    today = date.today().isoformat()
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM attendance_records WHERE user_id=?", (uid,))
        conn.execute(
            "INSERT INTO attendance_records(user_id, work_date, check_in, status)"
            " VALUES(?,?,?,'Present')", (uid, today, "08:00"))
        conn.commit()
        conn.close()

    c = app.test_client()
    c.post("/auth/login", data={"username": "brk_explicit_att",
                                "password": "Str0ng!Pass9"}, follow_redirects=True)
    c.post("/attendance/checkin",
           data={"action": "checkout", "break_minutes": "30",
                 "_csrf_token": get_csrf(c)}, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT break_minutes FROM attendance_records WHERE user_id=? AND work_date=?",
            (uid, today)).fetchone()
        conn.close()
    assert int(row["break_minutes"]) == 30


# ── leave ────────────────────────────────────────────────────────────────────

def _leave_type(app, name="T-Annual", days=21):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT id FROM leave_types WHERE name=?", (name,)).fetchone()
        if row:
            lt = row["id"]
        else:
            lt = conn.execute(
                "INSERT INTO leave_types(name, days_per_year, is_active, is_paid)"
                " VALUES(?,?,1,1)", (name, days)).lastrowid
        conn.commit()
        conn.close()
    return lt


def _balance(app, uid, lt, year):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
            (uid, lt, year)).fetchone()
        conn.close()
    return dict(row) if row else None


def test_leave_is_reserved_against_the_year_it_is_taken(app, shifts):
    """A December request for January reserved on THIS year's row while
    approval settled against next year's — so nothing was ever deducted and the
    reservation sat on the old row forever."""
    lt = _leave_type(app)
    uid = _staff(app, "leave_year_att", "Leave Year", shifts["day"])
    next_year = date.today().year + 1

    c = app.test_client()
    c.post("/auth/login", data={"username": "leave_year_att",
                                "password": "Str0ng!Pass9"}, follow_redirects=True)
    c.post("/attendance/leaves/new", data={
        "leave_type_id": lt,
        "start_date": "%d-01-11" % next_year,     # a Sunday-ish week next year
        "end_date": "%d-01-14" % next_year,
        "reason": "family", "_csrf_token": get_csrf(c),
    }, follow_redirects=True)

    bal = _balance(app, uid, lt, next_year)
    assert bal is not None, "no balance row for the year the leave falls in"
    assert float(bal["pending"]) > 0, \
        "the reservation went to a different year's row and is stranded there"


def test_a_leave_type_with_no_balance_row_is_still_tracked(app, shifts):
    """_get_or_create_balance existed and was called by nothing, so these types
    were free: the form showed the full allowance and nothing was ever used."""
    lt = _leave_type(app, "T-Compassionate", 5)
    uid = _staff(app, "leave_new_type_att", "Leave New Type", shifts["day"])
    year = date.today().year
    assert _balance(app, uid, lt, year) is None, "fixture already has a row"

    c = app.test_client()
    c.post("/auth/login", data={"username": "leave_new_type_att",
                                "password": "Str0ng!Pass9"}, follow_redirects=True)
    c.post("/attendance/leaves/new", data={
        "leave_type_id": lt,
        "start_date": "%d-06-14" % year, "end_date": "%d-06-15" % year,
        "reason": "family", "_csrf_token": get_csrf(c),
    }, follow_redirects=True)

    bal = _balance(app, uid, lt, year)
    assert bal is not None, "the leave type is still completely untracked"
    assert float(bal["allocated"]) == 5
    assert float(bal["pending"]) > 0


def test_saving_a_balance_unchanged_does_not_destroy_entitlement(app, shifts):
    """The no-op Save. remaining must be allocated - used, not minus pending."""
    lt = _leave_type(app)
    uid = _staff(app, "bal_noop_att", "Balance NoOp", shifts["day"],
                 role="clinic_owner")

    c = app.test_client()
    c.post("/auth/login", data={"username": "bal_noop_att",
                                "password": "Str0ng!Pass9"}, follow_redirects=True)
    for _ in range(3):
        c.post("/attendance/balances/set", data={
            "user_id": uid, "leave_type_id": lt, "year": "2029",
            "allocated": "21", "used": "4", "pending": "2",
            "_csrf_token": get_csrf(c),
        }, follow_redirects=True)

    bal = _balance(app, uid, lt, 2029)
    assert float(bal["remaining"]) == 17.0, \
        "three saves left remaining at %s instead of 17 (21 allocated - 4 used)" \
        % bal["remaining"]
    available = float(bal["remaining"]) - float(bal["pending"])
    assert available == 15.0, "available days came out at %s" % available
