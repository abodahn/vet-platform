# -*- coding: utf-8 -*-
"""Attendance & leave module — every route on the untested list.

Attendance feeds payroll: `hours_worked` here becomes overtime money there,
and an absent day becomes a deduction. So the tests below do not stop at a
200 — they read the row back and check the hours, the status and the leave
balance arithmetic. They also try, as a real nurse session, to touch a
colleague's attendance and a colleague's report.
"""
import io

import pytest

import models.database as db

CSRF = "attendance-routes-test-token"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _mkuser(app, username, role, full_name):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role, "
                "is_active, branch_id) VALUES (?,?,?,?,1,1)",
                (username, "not-a-real-hash", full_name, role))
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        user = {k: row[k] for k in row.keys()
                if k not in ("password_hash", "totp_secret")}
        conn.close()
    return user


def _client(app, user):
    c = app.test_client()
    with c.session_transaction() as s:
        s["user"] = user
        s["lang"] = "en"
        s["_csrf_token"] = CSRF
    return c


def _post(client, url, data=None, follow=True):
    payload = dict(data or {})
    payload["_csrf_token"] = CSRF
    return client.post(url, data=payload, follow_redirects=follow)


def _rows(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        out = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
    return out


def _one(app, sql, params=()):
    r = _rows(app, sql, params)
    return r[0] if r else None


def _exec(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        conn.execute(sql, params)
        conn.commit()
        conn.close()


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def owner(app):
    return _mkuser(app, "att_owner", "clinic_owner", "Att Test Owner")


@pytest.fixture
def hr_officer(app):
    return _mkuser(app, "att_hr", "hr", "Att Test HR")


@pytest.fixture
def nurse(app):
    return _mkuser(app, "att_nurse", "nurse", "Att Test Nurse")


@pytest.fixture
def colleague(app):
    return _mkuser(app, "att_colleague", "nurse", "Att Test Colleague")


@pytest.fixture
def boss(app, owner):
    return _client(app, owner)


@pytest.fixture
def leave_type(app):
    row = _one(app, "SELECT * FROM leave_types WHERE name=?", ("AttTest Annual",))
    if not row:
        _exec(app, "INSERT INTO leave_types(name,name_ar,days_per_year,is_paid,"
                   "color,is_active) VALUES(?,?,?,1,?,1)",
              ("AttTest Annual", "سنوية", 21, "#6366f1"))
        row = _one(app, "SELECT * FROM leave_types WHERE name=?", ("AttTest Annual",))
    return row


# ─── read routes ──────────────────────────────────────────────────────────────

def test_shifts_list_renders(boss):
    assert boss.get("/attendance/shifts").status_code == 200


def test_leave_types_renders(boss):
    assert boss.get("/attendance/leave-types").status_code == 200


def test_leaves_list_renders(boss):
    assert boss.get("/attendance/leaves").status_code == 200
    assert boss.get("/attendance/leaves?status=Pending").status_code == 200


def test_balances_renders(boss):
    assert boss.get("/attendance/balances").status_code == 200
    assert boss.get("/attendance/balances?year=2026").status_code == 200


def test_holidays_renders(boss):
    assert boss.get("/attendance/holidays").status_code == 200
    assert boss.get("/attendance/holidays?year=2026").status_code == 200


def test_api_today_matches_database(app, boss):
    from datetime import date
    r = boss.get("/attendance/api/today")
    assert r.status_code == 200
    payload = r.get_json()
    today = date.today().isoformat()
    assert payload["date"] == today
    expected = _one(app, "SELECT COUNT(*) AS c FROM attendance_records WHERE work_date=?",
                    (today,))["c"]
    assert len(payload["records"]) == expected


# ─── check-in / check-out ─────────────────────────────────────────────────────

def test_checkin_get_renders(app, nurse):
    c = _client(app, nurse)
    assert c.get("/attendance/checkin").status_code == 200


def test_checkin_creates_my_own_record(app, nurse, monkeypatch):
    from datetime import date, datetime
    # Pin the shift to start now. Check-in is stamped with the wall clock, and
    # once 'Late' was actually implemented this test began asserting Present or
    # Late purely according to what time of day the suite happened to run -- it
    # passed in the morning and failed after 08:15. Pinning the shift keeps the
    # status assertion meaningful instead of weakening it to "either".
    import blueprints.attendance.routes as att
    # default_shift now takes the employee and the date — it resolves each
    # person's OWN shift through staff_shifts instead of returning whichever
    # shift happened to have the lowest id.
    monkeypatch.setattr(att, "default_shift", lambda conn, user_id=None, on_date=None: {
        "start_time": datetime.now().strftime("%H:%M"),
        "end_time": "23:59",
        "break_minutes": 0,
    })
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (nurse["id"], today))
    c = _client(app, nurse)
    r = _post(c, "/attendance/checkin", {"action": "checkin", "notes": "on time"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
               (nurse["id"], today))
    assert row is not None, "check-in returned 200 but wrote no attendance record"
    assert row["status"] == "Present"
    assert row["check_in"], "check-in time was not stored"
    assert row["notes"] == "on time"
    assert row["username"] == nurse["username"]


def test_checkout_computes_hours_worked(app, nurse):
    from datetime import date
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (nurse["id"], today))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, check_in, status) VALUES (?,?,?,?, '08:00', 'Present')",
          (nurse["id"], nurse["username"], nurse["full_name"], today))
    c = _client(app, nurse)
    r = _post(c, "/attendance/checkin", {"action": "checkout", "break_minutes": "30"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
               (nurse["id"], today))
    assert row["check_out"], "check-out returned 200 but stored no check-out time"
    assert row["break_minutes"] == 30
    from blueprints.attendance.routes import _calc_hours
    assert float(row["hours_worked"]) == _calc_hours("08:00", row["check_out"], 30)


def test_double_checkin_does_not_duplicate(app, nurse):
    from datetime import date
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (nurse["id"], today))
    c = _client(app, nurse)
    _post(c, "/attendance/checkin", {"action": "checkin"})
    _post(c, "/attendance/checkin", {"action": "checkin"})
    rows = _rows(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
                 (nurse["id"], today))
    assert len(rows) == 1, "a second check-in created a second record for the same day"


def test_checkout_without_checkin_writes_nothing(app, colleague):
    from datetime import date
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], today))
    c = _client(app, colleague)
    _post(c, "/attendance/checkin", {"action": "checkout"})
    assert _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
                (colleague["id"], today)) is None


def test_hours_calculation_handles_a_night_shift(app):
    """22:00 -> 06:00 with a 60-minute break is 7 hours, not a negative number.

    The wrap is now something the CALLER declares, because from two times alone
    it cannot be told apart from a typo: 09:00 -> 07:00 is a 22-hour day if you
    assume a wrap, and a mistyped 17:00 if you do not. It used to always assume
    the wrap, so a corrected record could store 21.98 hours and payroll paid
    fourteen hours of overtime on it.
    """
    from blueprints.attendance.routes import _calc_hours
    assert _calc_hours("22:00", "06:00", 60, overnight=True) == 7.0
    assert _calc_hours("09:00", "17:00", 0) == 8.0
    assert _calc_hours("09:00", "17:30", 30) == 8.0
    assert _calc_hours("", "17:00", 0) == 0.0


def test_a_backwards_day_shift_is_zero_not_twenty_two_hours(app):
    """The typo that used to become overtime."""
    from blueprints.attendance.routes import _calc_hours
    assert _calc_hours("09:00", "07:00", 0) == 0.0, \
        "a day shift ending before it starts was read as an overnight wrap"
    assert _calc_hours("09:00", "07:00", 0, overnight=True) == 22.0, \
        "a real night shift must still wrap when the caller says so"


def test_manager_may_check_a_staff_member_in(app, owner, colleague):
    from datetime import date
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], today))
    c = _client(app, owner)
    r = _post(c, "/attendance/checkin",
              {"action": "checkin", "user_id": colleague["id"], "notes": "by manager"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
               (colleague["id"], today))
    assert row is not None, "a manager could not check a staff member in"
    assert row["recorded_by"] == owner["username"]


# ─── IDOR: a nurse must not touch a colleague's attendance ────────────────────

def test_nurse_cannot_check_in_a_colleague(app, nurse, colleague):
    """POST /attendance/checkin honours a `user_id` field. Only managers may
    aim it at someone else — otherwise any employee can fabricate a
    colleague's attendance, which lands straight in that colleague's pay."""
    from datetime import date
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], today))
    c = _client(app, nurse)
    _post(c, "/attendance/checkin",
          {"action": "checkin", "user_id": colleague["id"], "notes": "forged"})
    assert _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
                (colleague["id"], today)) is None, \
        "a nurse created an attendance record for a colleague (IDOR)"


def test_nurse_cannot_check_out_a_colleague(app, nurse, colleague):
    from datetime import date
    today = date.today().isoformat()
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], today))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, check_in, status) VALUES (?,?,?,?, '08:00', 'Present')",
          (colleague["id"], colleague["username"], colleague["full_name"], today))
    c = _client(app, nurse)
    _post(c, "/attendance/checkin",
          {"action": "checkout", "user_id": colleague["id"], "break_minutes": "0"})
    row = _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
               (colleague["id"], today))
    assert row["check_out"] is None, \
        "a nurse checked a colleague out and set their hours_worked (IDOR)"


def test_nurse_report_ignores_a_forged_user_id(app, nurse, colleague):
    """/attendance/report?user_id=X was an IDOR. Pin it shut."""
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], "2026-04-06"))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, status, hours_worked) VALUES (?,?,?,?, 'Present', 9)",
          (colleague["id"], colleague["username"], "Att Test Colleague", "2026-04-06"))
    c = _client(app, nurse)
    r = c.get(f"/attendance/report?year=2026&month=4&user_id={colleague['id']}")
    assert r.status_code == 200
    assert b"Att Test Colleague" not in r.data, \
        "a nurse read a colleague's attendance report via ?user_id= (IDOR)"


def test_nurse_records_list_ignores_a_forged_user_id(app, nurse, colleague):
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], "2026-04-07"))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, status) VALUES (?,?,?,?, 'Present')",
          (colleague["id"], colleague["username"], "Att Test Colleague", "2026-04-07"))
    c = _client(app, nurse)
    r = c.get("/attendance/records?date_from=2026-04-01&date_to=2026-04-30"
              f"&user_id={colleague['id']}")
    assert r.status_code == 200
    assert b"Att Test Colleague" not in r.data


def test_nurse_xlsx_export_is_scoped_to_themselves(app, nurse, colleague):
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], "2026-04-08"))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, status) VALUES (?,?,?,?, 'Present')",
          (colleague["id"], colleague["username"], "Att Test Colleague", "2026-04-08"))
    c = _client(app, nurse)
    r = c.get("/attendance/export/xlsx?date_from=2026-04-01&date_to=2026-04-30"
              f"&user_id={colleague['id']}")
    assert r.status_code == 200
    names = _xlsx_column(r.data, 1)
    assert "Att Test Colleague" not in names, \
        "a nurse exported a colleague's attendance to xlsx (IDOR)"


def _xlsx_column(payload: bytes, col_index: int):
    """Read one column out of the workbook body (data starts at row 4)."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(payload))
    ws = wb.active
    return [row[col_index] for row in ws.iter_rows(min_row=4, values_only=True)]


# ─── xlsx export ──────────────────────────────────────────────────────────────

def test_export_xlsx_contains_the_records(app, boss, colleague):
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], "2026-04-09"))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, status, hours_worked, break_minutes) "
               "VALUES (?,?,?,?, 'Present', 7.5, 30)",
          (colleague["id"], colleague["username"], "Att Test Colleague", "2026-04-09"))
    r = boss.get("/attendance/export/xlsx?date_from=2026-04-09&date_to=2026-04-09")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    names = _xlsx_column(r.data, 1)
    assert "Att Test Colleague" in names, "the export rendered but carried no rows"


# ─── record edit ──────────────────────────────────────────────────────────────

@pytest.fixture
def a_record(app, colleague):
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
          (colleague["id"], "2026-04-10"))
    _exec(app, "INSERT INTO attendance_records (user_id, username, full_name, "
               "work_date, check_in, check_out, status) "
               "VALUES (?,?,?,?, '09:00', '17:00', 'Present')",
          (colleague["id"], colleague["username"], colleague["full_name"], "2026-04-10"))
    return _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
                (colleague["id"], "2026-04-10"))


def test_record_edit_get_renders(boss, a_record):
    assert boss.get(f"/attendance/records/edit/{a_record['id']}").status_code == 200


def test_record_edit_rewrites_times_and_hours(app, boss, a_record):
    r = _post(boss, f"/attendance/records/edit/{a_record['id']}", {
        "check_in": "10:00", "check_out": "19:00", "status": "Late",
        "break_minutes": "45", "notes": "corrected by manager",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM attendance_records WHERE id=?", (a_record["id"],))
    assert str(row["check_in"])[:5] == "10:00"
    assert str(row["check_out"])[:5] == "19:00"
    assert row["status"] == "Late"
    assert row["break_minutes"] == 45
    assert float(row["hours_worked"]) == 8.25, \
        "9 hours minus a 45-minute break is 8.25 — hours_worked was not recomputed"
    assert row["notes"] == "corrected by manager"


def test_record_edit_missing_record_redirects(boss):
    assert boss.get("/attendance/records/edit/999999",
                    follow_redirects=True).status_code == 200


def test_nurse_cannot_edit_an_attendance_record(app, nurse, a_record):
    c = _client(app, nurse)
    _post(c, f"/attendance/records/edit/{a_record['id']}",
          {"check_in": "06:00", "check_out": "23:00", "status": "Present",
           "break_minutes": "0"})
    row = _one(app, "SELECT * FROM attendance_records WHERE id=?", (a_record["id"],))
    assert str(row["check_in"])[:5] == "09:00", \
        "a nurse rewrote an attendance record (and therefore payable hours)"


# ─── shifts ───────────────────────────────────────────────────────────────────

def test_shift_save_creates_then_updates(app, boss):
    r = _post(boss, "/attendance/shifts/save", {
        "name": "AttTest Night", "start_time": "22:00", "end_time": "06:00",
        "break_minutes": "45", "days_of_week": ["1", "2", "3"],
        "color": "#111827", "is_active": "1",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM shifts WHERE name=?", ("AttTest Night",))
    assert row is not None, "shifts/save returned 200 but created no shift"
    assert str(row["start_time"])[:5] == "22:00"
    assert str(row["end_time"])[:5] == "06:00"
    assert row["break_minutes"] == 45
    assert row["days_of_week"] == "1,2,3"
    assert row["is_active"] in (1, True)

    _post(boss, "/attendance/shifts/save", {
        "shift_id": row["id"], "name": "AttTest Night Renamed",
        "start_time": "23:00", "end_time": "07:00", "break_minutes": "30",
        "days_of_week": ["4", "5"], "color": "#222", "is_active": "",
    })
    row2 = _one(app, "SELECT * FROM shifts WHERE id=?", (row["id"],))
    assert row2["name"] == "AttTest Night Renamed"
    assert row2["break_minutes"] == 30
    assert row2["days_of_week"] == "4,5"
    assert row2["is_active"] in (0, False)
    assert len(_rows(app, "SELECT * FROM shifts WHERE name LIKE 'AttTest Night%'")) == 1


def test_shift_save_rejects_a_blank_name(app, boss):
    before = _one(app, "SELECT COUNT(*) AS c FROM shifts")["c"]
    _post(boss, "/attendance/shifts/save", {"name": "   ", "start_time": "08:00"})
    assert _one(app, "SELECT COUNT(*) AS c FROM shifts")["c"] == before


def test_nurse_cannot_save_a_shift(app, nurse):
    before = _one(app, "SELECT COUNT(*) AS c FROM shifts")["c"]
    c = _client(app, nurse)
    _post(c, "/attendance/shifts/save", {"name": "AttTest Nurse Shift"})
    assert _one(app, "SELECT COUNT(*) AS c FROM shifts")["c"] == before, \
        "a nurse created a shift"


def test_nurse_cannot_list_shifts(app, nurse):
    c = _client(app, nurse)
    r = c.get("/attendance/shifts", follow_redirects=True)
    assert b"Access denied" in r.data or b"access denied" in r.data.lower()


# ─── leave types ──────────────────────────────────────────────────────────────

def test_leave_type_save_creates_then_updates(app, boss):
    r = _post(boss, "/attendance/leave-types/save", {
        "name": "AttTest Study Leave", "name_ar": "إجازة دراسية",
        "days_per_year": "7", "is_paid": "1", "color": "#0ea5e9", "is_active": "1",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM leave_types WHERE name=?", ("AttTest Study Leave",))
    assert row is not None, "leave-types/save returned 200 but created nothing"
    assert float(row["days_per_year"]) == 7
    assert row["name_ar"] == "إجازة دراسية"
    assert row["is_paid"] in (1, True)

    _post(boss, "/attendance/leave-types/save", {
        "lt_id": row["id"], "name": "AttTest Study Leave", "days_per_year": "10",
        "is_active": "1",
    })
    row2 = _one(app, "SELECT * FROM leave_types WHERE id=?", (row["id"],))
    assert float(row2["days_per_year"]) == 10
    assert row2["is_paid"] in (0, False), "the unchecked is_paid box did not clear"


def test_leave_type_save_rejects_a_blank_name(app, boss):
    before = _one(app, "SELECT COUNT(*) AS c FROM leave_types")["c"]
    _post(boss, "/attendance/leave-types/save", {"name": ""})
    assert _one(app, "SELECT COUNT(*) AS c FROM leave_types")["c"] == before


def test_nurse_cannot_save_a_leave_type(app, nurse):
    before = _one(app, "SELECT COUNT(*) AS c FROM leave_types")["c"]
    c = _client(app, nurse)
    _post(c, "/attendance/leave-types/save", {"name": "AttTest Nurse Type"})
    assert _one(app, "SELECT COUNT(*) AS c FROM leave_types")["c"] == before


# ─── balances ─────────────────────────────────────────────────────────────────

def test_balance_set_writes_and_computes_remaining(app, boss, colleague, leave_type):
    r = _post(boss, "/attendance/balances/set", {
        "user_id": colleague["id"], "leave_type_id": leave_type["id"],
        "year": "2026", "allocated": "21", "used": "4", "pending": "2",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                    "AND year=?", (colleague["id"], leave_type["id"], 2026))
    assert row is not None, "balances/set returned 200 but wrote no balance"
    assert float(row["allocated"]) == 21
    assert float(row["used"]) == 4
    assert float(row["pending"]) == 2
    # allocated - used, NOT minus pending.
    #
    # This asserted 15 (21-4-2) and that was the bug. Availability is computed
    # elsewhere as `remaining - pending`, so subtracting pending here counts the
    # reservation twice. The damage lands later: leave_approve takes the days
    # off `remaining` AND clears them from `pending`, so once the pending
    # request is approved the employee is permanently down twice what they took.
    assert float(row["remaining"]) == 17, \
        "remaining must be allocated - used; pending is subtracted at read time"


def test_balance_set_replaces_rather_than_duplicates(app, boss, colleague, leave_type):
    for alloc in ("21", "30"):
        _post(boss, "/attendance/balances/set", {
            "user_id": colleague["id"], "leave_type_id": leave_type["id"],
            "year": "2027", "allocated": alloc, "used": "0", "pending": "0",
        })
    rows = _rows(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                      "AND year=?", (colleague["id"], leave_type["id"], 2027))
    assert len(rows) == 1, f"expected one balance row, found {len(rows)}"
    assert float(rows[0]["allocated"]) == 30, "the second write did not take effect"


def test_balance_never_goes_negative(app, boss, colleague, leave_type):
    _post(boss, "/attendance/balances/set", {
        "user_id": colleague["id"], "leave_type_id": leave_type["id"],
        "year": "2028", "allocated": "5", "used": "9", "pending": "0",
    })
    row = _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                    "AND year=?", (colleague["id"], leave_type["id"], 2028))
    assert float(row["remaining"]) == 0


def test_nurse_cannot_set_a_balance(app, nurse, colleague, leave_type):
    c = _client(app, nurse)
    _post(c, "/attendance/balances/set", {
        "user_id": colleague["id"], "leave_type_id": leave_type["id"],
        "year": "2029", "allocated": "99", "used": "0", "pending": "0",
    })
    assert _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                     "AND year=?", (colleague["id"], leave_type["id"], 2029)) is None, \
        "a nurse granted themselves a leave balance"


def test_nurse_cannot_open_the_balances_matrix(app, nurse):
    c = _client(app, nurse)
    r = c.get("/attendance/balances", follow_redirects=True)
    assert b"access denied" in r.data.lower()


# ─── public holidays ──────────────────────────────────────────────────────────

def test_holiday_save_creates_then_updates(app, boss):
    r = _post(boss, "/attendance/holidays/save", {
        "name": "AttTest Founding Day", "name_ar": "يوم التأسيس",
        "holiday_date": "2026-05-11",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM public_holidays WHERE holiday_date=?", ("2026-05-11",))
    assert row is not None, "holidays/save returned 200 but wrote nothing"
    assert row["name"] == "AttTest Founding Day"
    assert row["name_ar"] == "يوم التأسيس"

    _post(boss, "/attendance/holidays/save", {
        "holiday_id": row["id"], "name": "AttTest Founding Day (obs)",
        "holiday_date": "2026-05-12",
    })
    row2 = _one(app, "SELECT * FROM public_holidays WHERE id=?", (row["id"],))
    assert row2["name"] == "AttTest Founding Day (obs)"
    assert str(row2["holiday_date"])[:10] == "2026-05-12"


def test_holiday_save_rejects_missing_fields(app, boss):
    before = _one(app, "SELECT COUNT(*) AS c FROM public_holidays")["c"]
    _post(boss, "/attendance/holidays/save", {"name": "No Date"})
    _post(boss, "/attendance/holidays/save", {"holiday_date": "2026-05-20"})
    assert _one(app, "SELECT COUNT(*) AS c FROM public_holidays")["c"] == before


def test_holiday_delete_removes_the_row(app, boss):
    _post(boss, "/attendance/holidays/save",
          {"name": "AttTest Doomed", "holiday_date": "2026-06-01"})
    row = _one(app, "SELECT * FROM public_holidays WHERE holiday_date=?", ("2026-06-01",))
    assert row is not None
    r = _post(boss, f"/attendance/holidays/{row['id']}/delete")
    assert r.status_code == 200
    assert _one(app, "SELECT * FROM public_holidays WHERE id=?", (row["id"],)) is None


def test_nurse_cannot_delete_a_holiday(app, nurse, boss):
    _post(boss, "/attendance/holidays/save",
          {"name": "AttTest Protected", "holiday_date": "2026-06-02"})
    row = _one(app, "SELECT * FROM public_holidays WHERE holiday_date=?", ("2026-06-02",))
    c = _client(app, nurse)
    _post(c, f"/attendance/holidays/{row['id']}/delete")
    assert _one(app, "SELECT * FROM public_holidays WHERE id=?", (row["id"],)) is not None


def test_holidays_page_filters_by_year(app, boss):
    _post(boss, "/attendance/holidays/save",
          {"name": "AttTest Year Marker", "holiday_date": "2031-01-02"})
    r = boss.get("/attendance/holidays?year=2031")
    assert r.status_code == 200
    assert b"AttTest Year Marker" in r.data, \
        "the holidays page did not list a holiday in the requested year"
    r2 = boss.get("/attendance/holidays?year=2032")
    assert b"AttTest Year Marker" not in r2.data


# ─── leave requests ───────────────────────────────────────────────────────────

def test_leave_new_get_renders(app, nurse, leave_type):
    c = _client(app, nurse)
    assert c.get("/attendance/leaves/new").status_code == 200


def _make_leave(app, user, leave_type, start, end, reason="AttTest leave"):
    c = _client(app, user)
    _post(c, "/attendance/leaves/new", {
        "leave_type_id": leave_type["id"], "start_date": start,
        "end_date": end, "reason": reason,
    })
    return _one(app, "SELECT * FROM leave_requests WHERE user_id=? AND start_date=? "
                     "ORDER BY id DESC LIMIT 1", (user["id"], start))


def test_leave_new_writes_the_request_and_counts_business_days(app, nurse, leave_type):
    # Sun 2026-04-12 .. Thu 2026-04-16 is five working days.
    #
    # This used to say Mon 13 .. Fri 17, because the counter hardcoded the
    # Monday-to-Friday week. In Egypt the weekend is Friday and Saturday, so
    # that range is four working days and one day off — which is exactly the
    # bug that had every employee marked absent on Fridays and docked for it.
    req = _make_leave(app, nurse, leave_type, "2026-04-12", "2026-04-16")
    assert req is not None, "leaves/new returned 200 but wrote no request"
    assert req["status"] == "Pending"
    assert float(req["days_requested"]) == 5, "business days were miscounted"
    assert req["leave_type_name"] == leave_type["name"]
    assert req["username"] == nurse["username"]
    assert req["reason"] == "AttTest leave"


def test_leave_new_skips_weekends_and_holidays(app, nurse, leave_type, boss):
    _post(boss, "/attendance/holidays/save",
          {"name": "AttTest Mid-week Holiday", "holiday_date": "2026-04-22"})
    # Sun 2026-04-19 .. Sat 2026-04-25: five working days (Sun-Thu), minus
    # the Wednesday holiday = 4.
    req = _make_leave(app, nurse, leave_type, "2026-04-19", "2026-04-25")
    assert float(req["days_requested"]) == 4, \
        "a public holiday inside the range was still charged as leave"


def test_leave_new_rejects_backwards_dates(app, nurse, leave_type):
    before = len(_rows(app, "SELECT * FROM leave_requests WHERE user_id=?", (nurse["id"],)))
    c = _client(app, nurse)
    _post(c, "/attendance/leaves/new", {
        "leave_type_id": leave_type["id"], "start_date": "2026-05-10",
        "end_date": "2026-05-01", "reason": "backwards",
    })
    after = len(_rows(app, "SELECT * FROM leave_requests WHERE user_id=?", (nurse["id"],)))
    assert before == after, "an end-before-start leave request was accepted"


def test_leave_new_rejects_missing_fields(app, nurse, leave_type):
    before = len(_rows(app, "SELECT * FROM leave_requests WHERE user_id=?", (nurse["id"],)))
    c = _client(app, nurse)
    _post(c, "/attendance/leaves/new", {"leave_type_id": leave_type["id"]})
    after = len(_rows(app, "SELECT * FROM leave_requests WHERE user_id=?", (nurse["id"],)))
    assert before == after


def test_leave_new_reserves_pending_balance(app, boss, nurse, leave_type):
    _post(boss, "/attendance/balances/set", {
        "user_id": nurse["id"], "leave_type_id": leave_type["id"],
        "year": "2026", "allocated": "21", "used": "0", "pending": "0",
    })
    # Sun 2026-06-07 .. Thu 2026-06-11: five working days on the Egyptian week.
    _make_leave(app, nurse, leave_type, "2026-06-07", "2026-06-11")
    bal = _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                    "AND year=?", (nurse["id"], leave_type["id"], 2026))
    assert float(bal["pending"]) == 5, "the request did not reserve pending balance"
    assert float(bal["remaining"]) == 21, "remaining must not drop until approval"


def test_leave_approve_moves_pending_into_used(app, boss, nurse, leave_type):
    _post(boss, "/attendance/balances/set", {
        "user_id": nurse["id"], "leave_type_id": leave_type["id"],
        "year": "2026", "allocated": "21", "used": "0", "pending": "0",
    })
    req = _make_leave(app, nurse, leave_type, "2026-07-06", "2026-07-08")  # 3 days
    r = _post(boss, f"/attendance/leaves/{req['id']}/approve")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM leave_requests WHERE id=?", (req["id"],))
    assert row["status"] == "Approved", "approve returned 200 but the status is unchanged"
    assert row["approved_by"], "no approver was recorded"
    bal = _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                    "AND year=?", (nurse["id"], leave_type["id"], 2026))
    assert float(bal["used"]) == 3
    assert float(bal["pending"]) == 0
    assert float(bal["remaining"]) == 18


def test_leave_reject_releases_pending_and_stores_reason(app, boss, nurse, leave_type):
    _post(boss, "/attendance/balances/set", {
        "user_id": nurse["id"], "leave_type_id": leave_type["id"],
        "year": "2026", "allocated": "21", "used": "0", "pending": "0",
    })
    req = _make_leave(app, nurse, leave_type, "2026-08-03", "2026-08-05")  # 3 days
    r = _post(boss, f"/attendance/leaves/{req['id']}/reject",
              {"rejection_reason": "Clinic short-staffed that week"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM leave_requests WHERE id=?", (req["id"],))
    assert row["status"] == "Rejected"
    assert row["rejection_reason"] == "Clinic short-staffed that week"
    bal = _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                    "AND year=?", (nurse["id"], leave_type["id"], 2026))
    assert float(bal["pending"]) == 0, "rejecting did not release the reserved days"
    assert float(bal["used"]) == 0
    assert float(bal["remaining"]) == 21


def test_approving_twice_does_not_double_deduct(app, boss, nurse, leave_type):
    _post(boss, "/attendance/balances/set", {
        "user_id": nurse["id"], "leave_type_id": leave_type["id"],
        "year": "2026", "allocated": "21", "used": "0", "pending": "0",
    })
    req = _make_leave(app, nurse, leave_type, "2026-09-07", "2026-09-09")  # 3 days
    _post(boss, f"/attendance/leaves/{req['id']}/approve")
    _post(boss, f"/attendance/leaves/{req['id']}/approve")
    bal = _one(app, "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? "
                    "AND year=?", (nurse["id"], leave_type["id"], 2026))
    assert float(bal["used"]) == 3, "a second approval deducted the days again"


def test_leave_detail_renders_for_the_requester(app, nurse, leave_type):
    req = _make_leave(app, nurse, leave_type, "2026-10-05", "2026-10-06")
    c = _client(app, nurse)
    r = c.get(f"/attendance/leaves/{req['id']}")
    assert r.status_code == 200
    assert b"AttTest leave" in r.data


def test_leave_detail_missing_redirects(boss):
    assert boss.get("/attendance/leaves/999999",
                    follow_redirects=True).status_code == 200


def test_nurse_cannot_read_a_colleagues_leave_request(app, nurse, colleague, leave_type):
    req = _make_leave(app, colleague, leave_type, "2026-11-02", "2026-11-03",
                      reason="AttTest private family matter")
    c = _client(app, nurse)
    r = c.get(f"/attendance/leaves/{req['id']}", follow_redirects=True)
    assert b"AttTest private family matter" not in r.data, \
        "a nurse read a colleague's leave request (IDOR)"


def test_nurse_cannot_approve_their_own_leave(app, nurse, leave_type):
    req = _make_leave(app, nurse, leave_type, "2026-11-09", "2026-11-10")
    c = _client(app, nurse)
    _post(c, f"/attendance/leaves/{req['id']}/approve")
    row = _one(app, "SELECT * FROM leave_requests WHERE id=?", (req["id"],))
    assert row["status"] == "Pending", "a nurse approved their own leave request"


def test_nurse_cannot_reject_a_colleagues_leave(app, nurse, colleague, leave_type):
    req = _make_leave(app, colleague, leave_type, "2026-11-16", "2026-11-17")
    c = _client(app, nurse)
    _post(c, f"/attendance/leaves/{req['id']}/reject", {"rejection_reason": "no"})
    row = _one(app, "SELECT * FROM leave_requests WHERE id=?", (req["id"],))
    assert row["status"] == "Pending"


def test_leaves_list_scopes_a_nurse_to_their_own(app, nurse, colleague, leave_type):
    _make_leave(app, colleague, leave_type, "2026-12-07", "2026-12-08",
                reason="AttTest colleague only")
    c = _client(app, nurse)
    r = c.get(f"/attendance/leaves?user_id={colleague['id']}")
    assert r.status_code == 200
    assert b"AttTest colleague only" not in r.data


# ─── the hr role reaches attendance ───────────────────────────────────────────

def test_hr_role_manages_attendance(app, hr_officer):
    c = _client(app, hr_officer)
    for url in ("/attendance/", "/attendance/records", "/attendance/leaves",
                "/attendance/shifts", "/attendance/leave-types",
                "/attendance/balances", "/attendance/holidays",
                "/attendance/report"):
        r = c.get(url, follow_redirects=True)
        assert r.status_code == 200, url
        assert b"access denied" not in r.data.lower(), f"the hr role was refused {url}"


def test_hr_role_may_edit_an_attendance_record(app, hr_officer, a_record):
    c = _client(app, hr_officer)
    _post(c, f"/attendance/records/edit/{a_record['id']}", {
        "check_in": "08:30", "check_out": "16:30", "status": "Present",
        "break_minutes": "60", "notes": "hr correction",
    })
    row = _one(app, "SELECT * FROM attendance_records WHERE id=?", (a_record["id"],))
    assert str(row["check_in"])[:5] == "08:30"
    assert float(row["hours_worked"]) == 7.0


# ─── anonymous ────────────────────────────────────────────────────────────────

def test_anonymous_is_bounced_from_every_attendance_route(client):
    for url in ("/attendance/", "/attendance/checkin", "/attendance/records",
                "/attendance/leaves", "/attendance/leaves/new",
                "/attendance/shifts", "/attendance/leave-types",
                "/attendance/balances", "/attendance/holidays",
                "/attendance/report", "/attendance/api/today",
                "/attendance/export/xlsx"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302), f"{url} served an anonymous caller"
        assert "/auth/login" in r.headers["Location"], url
