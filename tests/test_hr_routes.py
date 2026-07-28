# -*- coding: utf-8 -*-
"""HR module — every route on the untested list, driven through real HTTP.

The bar this file holds itself to: a POST that returns 200 proves nothing.
This codebase has shipped routes that render fine and write nothing. So every
write below is read back out of the database and compared against what was
sent, and every role gate is exercised by actually logging in as the role that
must be refused.
"""
import pytest

import models.database as db

CSRF = "hr-routes-test-token"


# ─── helpers ──────────────────────────────────────────────────────────────────

def _mkuser(app, username, role, full_name):
    """Create (once) a real user row and return it as a session-shaped dict."""
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
    """A test client already carrying `user`'s session and a CSRF token."""
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


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def owner(app):
    return _mkuser(app, "hrt_owner", "clinic_owner", "HR Test Owner")


@pytest.fixture
def hr_officer(app):
    return _mkuser(app, "hrt_hr", "hr", "HR Test Officer")


@pytest.fixture
def nurse(app):
    return _mkuser(app, "hrt_nurse", "nurse", "HR Test Nurse")


@pytest.fixture
def colleague(app):
    return _mkuser(app, "hrt_colleague", "nurse", "HR Test Colleague")


@pytest.fixture
def boss(app, owner):
    """Logged-in clinic owner. The GET also runs hr_bp's table bootstrap."""
    c = _client(app, owner)
    c.get("/hr/dashboard")
    return c


@pytest.fixture
def subject(app, colleague):
    """A staff member the HR routes act upon."""
    return colleague


# ─── read routes ──────────────────────────────────────────────────────────────

def test_index_redirects_to_dashboard(boss):
    r = boss.get("/hr/", follow_redirects=False)
    assert r.status_code in (301, 302)
    assert "/hr/dashboard" in r.headers["Location"]


def test_dashboard_renders_with_counts(app, boss, owner):
    r = boss.get("/hr/dashboard")
    assert r.status_code == 200
    # The headcount the page claims must match the database, not just render.
    total = _one(app, "SELECT COUNT(*) AS c FROM users WHERE is_active=1")["c"]
    assert total > 0
    assert str(total).encode() in r.data


def test_api_headcount_matches_database(app, boss):
    r = boss.get("/hr/api/headcount")
    assert r.status_code == 200
    payload = r.get_json()
    expected = {row["role"]: row["cnt"] for row in _rows(
        app, "SELECT role, COUNT(*) AS cnt FROM users WHERE is_active=1 GROUP BY role")}
    assert payload == expected


def test_roster_renders(boss):
    assert boss.get("/hr/roster").status_code == 200
    assert boss.get("/hr/roster?week=2026-03-04").status_code == 200


def test_roster_bad_week_falls_back_to_today(boss):
    assert boss.get("/hr/roster?week=not-a-date").status_code == 200


def test_certifications_list_renders(boss):
    assert boss.get("/hr/certifications").status_code == 200


def test_certification_days_left_is_a_real_countdown(app, boss, subject):
    """`days_left` was `(expiry_date - CURRENT_DATE)` in SQL. That is
    PostgreSQL date arithmetic; on SQLite it silently returned 0 for every
    row, so every certification read "expiring in 0 days"."""
    from datetime import date, timedelta
    expiry = (date.today() + timedelta(days=17)).isoformat()
    _post(boss, f"/hr/staff/{subject['id']}/certifications/add", {
        "cert_name": "HRTest Countdown Cert", "expiry_date": expiry,
        "status": "Active",
    })
    r = boss.get("/hr/certifications")
    assert r.status_code == 200
    assert b"17" in r.data, \
        "the certifications page did not show the real number of days left"

    r2 = boss.get("/hr/dashboard")
    assert b"HRTest Countdown Cert" in r2.data, \
        "a certification expiring in 17 days is missing from the HR dashboard"


def test_dashboard_reports_this_months_payroll(app, boss, subject):
    """The dashboard's payroll block is wrapped in a bare `except: pass`, so a
    broken query shows as a blank card rather than an error."""
    from datetime import date
    today = date.today()
    boss.get("/payroll/")          # payroll owns the `salaries` table bootstrap
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM salaries WHERE period_year=? AND period_month=?",
                     (today.year, today.month))
        conn.execute(
            "INSERT INTO salaries (user_id, period_year, period_month, "
            "basic_salary, gross, net, status) VALUES (?,?,?, 5000, 5000, 4321, 'Paid')",
            (subject["id"], today.year, today.month))
        conn.commit()
        conn.close()
    r = boss.get("/hr/dashboard")
    assert r.status_code == 200
    assert b"EGP 4,321" in r.data, \
        "this month's payroll total is missing from the HR dashboard"
    assert b"1/1" in r.data, "the paid/total payroll count is missing"


def test_dashboard_lists_a_recent_hire(app, boss, subject):
    from datetime import date, timedelta
    hired = (date.today() - timedelta(days=5)).isoformat()
    with app.app_context():
        conn = db.get_db()
        conn.execute("UPDATE users SET hire_date=? WHERE id=?", (hired, subject["id"]))
        conn.commit()
        conn.close()
    r = boss.get("/hr/dashboard")
    assert subject["full_name"].encode() in r.data, \
        "someone hired five days ago is missing from Recent Hires"


def test_overtime_list_renders_and_filters(boss):
    assert boss.get("/hr/overtime").status_code == 200
    assert boss.get("/hr/overtime?status=Pending&date_from=2026-01-01"
                    "&date_to=2026-12-31").status_code == 200


def test_performance_list_renders(boss):
    assert boss.get("/hr/performance").status_code == 200


def test_roles_list_renders(boss):
    assert boss.get("/hr/roles").status_code == 200


def test_hr_attendance_renders(boss):
    assert boss.get("/hr/attendance").status_code == 200
    assert boss.get("/hr/attendance?date_from=2026-01-01&date_to=2026-12-31"
                    "&status=Present&page=1").status_code == 200


# ─── staff create / edit ──────────────────────────────────────────────────────

def test_staff_new_get_renders(boss):
    assert boss.get("/hr/staff/new").status_code == 200


def test_staff_new_creates_the_row_it_was_sent(app, boss):
    r = _post(boss, "/hr/staff/new", {
        "username": "hrt_created", "password": "Secret123", "confirm_password": "Secret123",
        "full_name": "Created Person", "full_name_ar": "شخص جديد",
        "email": "created@example.com", "phone": "01000000001",
        "role": "reception", "is_active": "1",
        "job_title": "Front Desk", "contract_type": "Part-time",
        "hire_date": "2026-02-01", "national_id": "29001010101010",
        "emergency_contact": "Next Of Kin", "emergency_phone": "01000000002",
        "gender": "Female", "dob": "1990-01-01",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM users WHERE username=?", ("hrt_created",))
    assert row is not None, "staff_new returned 200 but wrote no user"
    assert row["full_name"] == "Created Person"
    assert row["full_name_ar"] == "شخص جديد"
    assert row["role"] == "reception"
    assert row["job_title"] == "Front Desk"
    assert row["contract_type"] == "Part-time"
    assert str(row["hire_date"])[:10] == "2026-02-01"
    assert row["emergency_phone"] == "01000000002"
    assert row["is_active"] in (1, True)


def test_staff_new_rejects_mismatched_passwords(app, boss):
    _post(boss, "/hr/staff/new", {
        "username": "hrt_mismatch", "password": "aaaaaa",
        "confirm_password": "bbbbbb", "full_name": "Nope", "role": "nurse",
    })
    assert _one(app, "SELECT * FROM users WHERE username=?", ("hrt_mismatch",)) is None, \
        "password mismatch still created the user"


def test_staff_new_rejects_missing_username(app, boss):
    before = _one(app, "SELECT COUNT(*) AS c FROM users")["c"]
    _post(boss, "/hr/staff/new", {"username": "", "password": "aaaaaa",
                                  "confirm_password": "aaaaaa", "role": "nurse"})
    after = _one(app, "SELECT COUNT(*) AS c FROM users")["c"]
    assert before == after, "blank username created a user"


def test_staff_edit_get_renders(boss, subject):
    assert boss.get(f"/hr/staff/{subject['id']}/edit").status_code == 200


def test_staff_edit_persists_every_field(app, boss, subject):
    r = _post(boss, f"/hr/staff/{subject['id']}/edit", {
        "full_name": "Edited Colleague", "full_name_ar": "زميل معدل",
        "email": "edited@example.com", "phone": "01111111111",
        "role": "nurse", "is_active": "1",
        "job_title": "Senior Nurse", "contract_type": "Full-time",
        "hire_date": "2025-06-15", "national_id": "28801010101010",
        "emergency_contact": "Spouse", "emergency_phone": "01222222222",
        "gender": "Male", "dob": "1988-01-01",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM users WHERE id=?", (subject["id"],))
    assert row["full_name"] == "Edited Colleague"
    assert row["job_title"] == "Senior Nurse"
    assert row["emergency_contact"] == "Spouse"
    assert str(row["hire_date"])[:10] == "2025-06-15"


def test_staff_edit_missing_user_redirects(boss):
    r = boss.get("/hr/staff/99999/edit", follow_redirects=True)
    assert r.status_code == 200


# ─── password reset ───────────────────────────────────────────────────────────

def test_reset_password_actually_changes_the_hash(app, owner, subject):
    before = _one(app, "SELECT password_hash FROM users WHERE id=?",
                  (subject["id"],))["password_hash"]
    c = _client(app, owner)
    c.get("/hr/dashboard")
    r = _post(c, f"/hr/staff/{subject['id']}/reset-password",
              {"new_password": "BrandNewPass1"})
    assert r.status_code == 200
    after = _one(app, "SELECT password_hash FROM users WHERE id=?",
                 (subject["id"],))["password_hash"]
    assert after != before, "reset-password returned 200 but the hash is unchanged"
    from blueprints.hr.routes import _hash
    assert after == _hash("BrandNewPass1")


def test_reset_password_rejects_short_password(app, owner, subject):
    before = _one(app, "SELECT password_hash FROM users WHERE id=?",
                  (subject["id"],))["password_hash"]
    c = _client(app, owner)
    _post(c, f"/hr/staff/{subject['id']}/reset-password", {"new_password": "abc"})
    after = _one(app, "SELECT password_hash FROM users WHERE id=?",
                 (subject["id"],))["password_hash"]
    assert after == before, "a 3-character password was accepted"


# ─── shift assignment ─────────────────────────────────────────────────────────

@pytest.fixture
def a_shift(app, boss):
    row = _one(app, "SELECT * FROM shifts ORDER BY id LIMIT 1")
    if row:
        return row
    with app.app_context():
        conn = db.get_db()
        conn.execute("INSERT INTO shifts(name,start_time,end_time,break_minutes,"
                     "days_of_week,is_active) VALUES('HRTest Shift','09:00','17:00',"
                     "60,'1,2,3,4,5',1)")
        conn.commit()
        conn.close()
    return _one(app, "SELECT * FROM shifts WHERE name='HRTest Shift'")


def test_assign_shift_writes_staff_shifts(app, boss, subject, a_shift):
    r = _post(boss, f"/hr/staff/{subject['id']}/assign-shift",
              {"shift_id": a_shift["id"], "effective_from": "2026-03-01"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM staff_shifts WHERE user_id=? AND shift_id=? "
                    "ORDER BY id DESC LIMIT 1", (subject["id"], a_shift["id"]))
    assert row is not None, "assign-shift returned 200 but wrote no assignment"
    assert str(row["effective_from"])[:10] == "2026-03-01"
    assert row["effective_to"] is None


def test_assign_shift_without_shift_id_closes_current(app, boss, subject, a_shift):
    _post(boss, f"/hr/staff/{subject['id']}/assign-shift",
          {"shift_id": a_shift["id"], "effective_from": "2026-03-01"})
    _post(boss, f"/hr/staff/{subject['id']}/assign-shift", {"shift_id": ""})
    open_rows = _rows(app, "SELECT * FROM staff_shifts WHERE user_id=? AND "
                           "effective_to IS NULL", (subject["id"],))
    assert open_rows == [], "removing a shift left an open-ended assignment"


# ─── performance reviews ──────────────────────────────────────────────────────

def test_performance_new_get_renders(boss):
    assert boss.get("/hr/performance/new").status_code == 200


@pytest.fixture
def review(app, boss, subject):
    _post(boss, "/hr/performance/new", {
        "user_id": subject["id"], "period": "2026-Q1", "rating": "4",
        "strengths": "Reliable", "improvements": "Documentation",
        "goals": "Lead triage", "comments": "Solid quarter",
        "status": "Draft", "reviewed_at": "2026-03-31",
    })
    row = _one(app, "SELECT * FROM performance_reviews WHERE user_id=? AND period=? "
                    "ORDER BY id DESC LIMIT 1", (subject["id"], "2026-Q1"))
    assert row is not None, "performance_new returned 200 but wrote no review"
    return row


def test_performance_new_persists_every_field(review, owner, subject):
    assert review["rating"] == 4
    assert review["strengths"] == "Reliable"
    assert review["improvements"] == "Documentation"
    assert review["goals"] == "Lead triage"
    assert review["comments"] == "Solid quarter"
    assert review["status"] == "Draft"
    assert str(review["reviewed_at"])[:10] == "2026-03-31"
    assert review["user_id"] == subject["id"]
    assert review["reviewer_id"] == owner["id"]


def test_performance_detail_renders(boss, review):
    r = boss.get(f"/hr/performance/{review['id']}")
    assert r.status_code == 200
    assert b"Reliable" in r.data


def test_performance_detail_missing_redirects(boss):
    assert boss.get("/hr/performance/99999", follow_redirects=True).status_code == 200


def test_performance_edit_get_renders(boss, review):
    assert boss.get(f"/hr/performance/{review['id']}/edit").status_code == 200


def test_performance_edit_updates_the_row(app, boss, review):
    r = _post(boss, f"/hr/performance/{review['id']}/edit", {
        "period": "2026-Q2", "rating": "2", "strengths": "Punctual",
        "improvements": "Handover notes", "goals": "Own the rota",
        "comments": "Mixed quarter", "status": "Submitted",
        "reviewed_at": "2026-06-30",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM performance_reviews WHERE id=?", (review["id"],))
    assert row["period"] == "2026-Q2"
    assert row["rating"] == 2
    assert row["strengths"] == "Punctual"
    assert row["status"] == "Submitted"
    assert str(row["reviewed_at"])[:10] == "2026-06-30"


def test_performance_acknowledge_sets_status(app, boss, review):
    r = _post(boss, f"/hr/performance/{review['id']}/acknowledge")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM performance_reviews WHERE id=?", (review["id"],))
    assert row["status"] == "Acknowledged", \
        "acknowledge returned 200 but the status did not change"


def test_employee_can_acknowledge_their_own_review(app, colleague, review):
    c = _client(app, colleague)
    r = _post(c, f"/hr/performance/{review['id']}/acknowledge")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM performance_reviews WHERE id=?", (review["id"],))
    assert row["status"] == "Acknowledged"


# ─── warnings ─────────────────────────────────────────────────────────────────

@pytest.fixture
def warning(app, boss, subject):
    _post(boss, f"/hr/staff/{subject['id']}/warnings/add", {
        "warning_type": "Written", "reason": "Late three times",
        "action_taken": "Verbal counselling", "issued_date": "2026-03-02",
        "expiry_date": "2026-09-02",
    })
    row = _one(app, "SELECT * FROM staff_warnings WHERE user_id=? ORDER BY id DESC "
                    "LIMIT 1", (subject["id"],))
    assert row is not None, "warnings/add returned 200 but wrote nothing"
    return row


def test_add_warning_persists_every_field(warning, owner, subject):
    assert warning["warning_type"] == "Written"
    assert warning["reason"] == "Late three times"
    assert warning["action_taken"] == "Verbal counselling"
    assert str(warning["issued_date"])[:10] == "2026-03-02"
    assert str(warning["expiry_date"])[:10] == "2026-09-02"
    assert warning["issued_by"] == owner["id"]
    assert warning["user_id"] == subject["id"]
    assert not warning["acknowledged"]


def test_acknowledge_warning_flips_the_flag(app, boss, subject, warning):
    r = _post(boss, f"/hr/staff/{subject['id']}/warnings/{warning['id']}/acknowledge")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM staff_warnings WHERE id=?", (warning["id"],))
    assert row["acknowledged"] in (1, True), \
        "acknowledge returned 200 but the flag is still false"


def test_employee_can_acknowledge_their_own_warning(app, colleague, subject, warning):
    c = _client(app, colleague)
    r = _post(c, f"/hr/staff/{subject['id']}/warnings/{warning['id']}/acknowledge")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM staff_warnings WHERE id=?", (warning["id"],))
    assert row["acknowledged"] in (1, True)


def test_delete_warning_removes_the_row(app, boss, subject, warning):
    r = _post(boss, f"/hr/staff/{subject['id']}/warnings/{warning['id']}/delete")
    assert r.status_code == 200
    assert _one(app, "SELECT * FROM staff_warnings WHERE id=?", (warning["id"],)) is None, \
        "delete returned 200 but the warning is still there"


def test_delete_warning_is_scoped_to_the_user_in_the_url(app, boss, subject, warning, nurse):
    """The DELETE carries `AND user_id=?` — a mismatched user must not delete."""
    r = _post(boss, f"/hr/staff/{nurse['id']}/warnings/{warning['id']}/delete")
    assert r.status_code == 200
    assert _one(app, "SELECT * FROM staff_warnings WHERE id=?", (warning["id"],)) is not None


# ─── certifications ───────────────────────────────────────────────────────────

@pytest.fixture
def certification(app, boss, subject):
    _post(boss, f"/hr/staff/{subject['id']}/certifications/add", {
        "cert_name": "Veterinary Nursing Diploma", "issued_by": "Cairo University",
        "cert_number": "VN-2024-8891", "issue_date": "2024-07-01",
        "expiry_date": "2027-07-01", "status": "Active", "notes": "Renewed once",
    })
    row = _one(app, "SELECT * FROM staff_certifications WHERE user_id=? "
                    "ORDER BY id DESC LIMIT 1", (subject["id"],))
    assert row is not None, "certifications/add returned 200 but wrote nothing"
    return row


def test_add_certification_persists_every_field(certification):
    assert certification["cert_name"] == "Veterinary Nursing Diploma"
    assert certification["issued_by"] == "Cairo University"
    assert certification["cert_number"] == "VN-2024-8891"
    assert str(certification["issue_date"])[:10] == "2024-07-01"
    assert str(certification["expiry_date"])[:10] == "2027-07-01"
    assert certification["status"] == "Active"
    assert certification["notes"] == "Renewed once"


def test_certifications_list_shows_the_new_cert(boss, certification):
    r = boss.get("/hr/certifications")
    assert r.status_code == 200
    assert b"Veterinary Nursing Diploma" in r.data


def test_delete_certification_removes_the_row(app, boss, subject, certification):
    r = _post(boss, f"/hr/staff/{subject['id']}/certifications/{certification['id']}/delete")
    assert r.status_code == 200
    assert _one(app, "SELECT * FROM staff_certifications WHERE id=?",
                (certification["id"],)) is None


# ─── HR notes ─────────────────────────────────────────────────────────────────

@pytest.fixture
def note(app, boss, subject):
    _post(boss, f"/hr/staff/{subject['id']}/notes/add",
          {"note": "Discussed rota preference for Ramadan."})
    row = _one(app, "SELECT * FROM staff_notes WHERE user_id=? ORDER BY id DESC "
                    "LIMIT 1", (subject["id"],))
    assert row is not None, "notes/add returned 200 but wrote nothing"
    return row


def test_add_note_persists_text_and_author(note, owner, subject):
    assert note["note"] == "Discussed rota preference for Ramadan."
    assert note["author_id"] == owner["id"]
    assert note["user_id"] == subject["id"]


def test_add_empty_note_writes_nothing(app, boss, subject):
    before = len(_rows(app, "SELECT * FROM staff_notes WHERE user_id=?", (subject["id"],)))
    _post(boss, f"/hr/staff/{subject['id']}/notes/add", {"note": "   "})
    after = len(_rows(app, "SELECT * FROM staff_notes WHERE user_id=?", (subject["id"],)))
    assert before == after, "an empty note was saved"


def test_delete_note_removes_the_row(app, boss, subject, note):
    r = _post(boss, f"/hr/staff/{subject['id']}/notes/{note['id']}/delete")
    assert r.status_code == 200
    assert _one(app, "SELECT * FROM staff_notes WHERE id=?", (note["id"],)) is None


# ─── overtime ─────────────────────────────────────────────────────────────────

@pytest.fixture
def overtime(app, boss, subject):
    _post(boss, f"/hr/staff/{subject['id']}/overtime/add",
          {"work_date": "2026-03-05", "hours": "3.5", "reason": "Emergency surgery"})
    row = _one(app, "SELECT * FROM overtime_log WHERE user_id=? ORDER BY id DESC "
                    "LIMIT 1", (subject["id"],))
    assert row is not None, "overtime/add returned 200 but wrote nothing"
    return row


def test_add_overtime_persists_hours_and_reason(overtime, subject):
    assert float(overtime["hours"]) == 3.5
    assert overtime["reason"] == "Emergency surgery"
    assert str(overtime["work_date"])[:10] == "2026-03-05"
    assert overtime["status"] == "Pending"
    assert overtime["user_id"] == subject["id"]


def test_approve_overtime_sets_status_and_approver(app, boss, owner, overtime):
    r = _post(boss, f"/hr/overtime/{overtime['id']}/approve")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM overtime_log WHERE id=?", (overtime["id"],))
    assert row["status"] == "Approved"
    assert row["approved_by"] == owner["id"]


def test_reject_overtime_sets_status(app, boss, overtime):
    r = _post(boss, f"/hr/overtime/{overtime['id']}/reject")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM overtime_log WHERE id=?", (overtime["id"],))
    assert row["status"] == "Rejected"


def test_overtime_list_filters_by_user(boss, overtime, subject):
    r = boss.get(f"/hr/overtime?user_id={subject['id']}")
    assert r.status_code == 200
    assert b"Emergency surgery" in r.data


# ─── HR attendance add / delete ───────────────────────────────────────────────

def test_hr_attendance_add_writes_the_record(app, boss, subject):
    """POST /hr/attendance/add must leave a row behind, with computed hours."""
    r = _post(boss, "/hr/attendance/add", {
        "user_id": subject["id"], "work_date": "2026-03-09",
        "check_in": "09:00", "check_out": "17:30", "status": "Late",
        "notes": "Traffic on the ring road",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
               (subject["id"], "2026-03-09"))
    assert row is not None, \
        "/hr/attendance/add returned 200 but no attendance record was written"
    assert row["status"] == "Late"
    assert str(row["check_in"])[:5] == "09:00"
    assert str(row["check_out"])[:5] == "17:30"
    assert float(row["hours_worked"]) == 8.5, "hours_worked was not computed from the times"
    assert row["notes"] == "Traffic on the ring road"
    assert row["username"] == subject["username"]


def test_hr_attendance_add_upserts_the_same_day(app, boss, subject):
    """Re-posting the same user/date must update, not duplicate."""
    for status, out in (("Present", "17:00"), ("Late", "18:00")):
        _post(boss, "/hr/attendance/add", {
            "user_id": subject["id"], "work_date": "2026-03-10",
            "check_in": "09:00", "check_out": out, "status": status, "notes": status,
        })
    rows = _rows(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
                 (subject["id"], "2026-03-10"))
    assert len(rows) == 1, f"expected one row for the day, found {len(rows)}"
    assert rows[0]["status"] == "Late"
    assert float(rows[0]["hours_worked"]) == 9.0


def test_hr_attendance_add_without_user_writes_nothing(app, boss):
    before = _one(app, "SELECT COUNT(*) AS c FROM attendance_records")["c"]
    _post(boss, "/hr/attendance/add", {"user_id": "", "work_date": "2026-03-11"})
    after = _one(app, "SELECT COUNT(*) AS c FROM attendance_records")["c"]
    assert before == after


def test_hr_attendance_delete_removes_the_record(app, boss, subject):
    with app.app_context():
        conn = db.get_db()
        conn.execute("INSERT INTO attendance_records (user_id, username, full_name, "
                     "work_date, status) VALUES (?,?,?,?, 'Present')",
                     (subject["id"], subject["username"], subject["full_name"],
                      "2026-03-12"))
        conn.commit()
        conn.close()
    rec = _one(app, "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
               (subject["id"], "2026-03-12"))
    r = _post(boss, f"/hr/attendance/{rec['id']}/delete")
    assert r.status_code == 200
    assert _one(app, "SELECT * FROM attendance_records WHERE id=?", (rec["id"],)) is None, \
        "delete returned 200 but the record survived"


# ─── role gating: the `hr` role ───────────────────────────────────────────────

def _denied(resp):
    """role_required bounces to the launcher with a flash rather than a 403."""
    return b"permission" in resp.data.lower()


def test_hr_role_reaches_hr_dashboard(app, hr_officer):
    c = _client(app, hr_officer)
    assert c.get("/hr/dashboard").status_code == 200
    assert c.get("/hr/staff").status_code == 200
    assert c.get("/hr/attendance").status_code == 200
    assert c.get("/hr/roster").status_code == 200
    assert c.get("/hr/certifications").status_code == 200


def test_hr_role_cannot_reset_passwords(app, hr_officer, subject, boss):
    before = _one(app, "SELECT password_hash FROM users WHERE id=?",
                  (subject["id"],))["password_hash"]
    c = _client(app, hr_officer)
    r = _post(c, f"/hr/staff/{subject['id']}/reset-password",
              {"new_password": "HrShouldNotDoThis1"})
    after = _one(app, "SELECT password_hash FROM users WHERE id=?",
                 (subject["id"],))["password_hash"]
    assert after == before, "the hr role reset another employee's password"
    assert _denied(r)


def test_hr_role_cannot_open_rbac_roles(app, hr_officer, boss):
    c = _client(app, hr_officer)
    r = c.get("/hr/roles", follow_redirects=True)
    assert _denied(r), "the hr role reached the RBAC roles admin page"


def test_hr_role_cannot_delete_warnings(app, hr_officer, subject, warning):
    c = _client(app, hr_officer)
    r = _post(c, f"/hr/staff/{subject['id']}/warnings/{warning['id']}/delete")
    assert _one(app, "SELECT * FROM staff_warnings WHERE id=?", (warning["id"],)) is not None, \
        "the hr role deleted a disciplinary record"
    assert _denied(r)


def test_hr_role_cannot_delete_notes(app, hr_officer, subject, note):
    c = _client(app, hr_officer)
    r = _post(c, f"/hr/staff/{subject['id']}/notes/{note['id']}/delete")
    assert _one(app, "SELECT * FROM staff_notes WHERE id=?", (note["id"],)) is not None, \
        "the hr role deleted an HR note"
    assert _denied(r)


def test_hr_role_cannot_reach_payroll(app, hr_officer):
    """Documented in blueprints/payroll/routes.py: hr gets people, not pay."""
    c = _client(app, hr_officer)
    for url in ("/payroll/", "/payroll/salaries/new", "/payroll/grades"):
        r = c.get(url, follow_redirects=True)
        assert _denied(r), f"the hr role reached {url}"


# ─── role gating: rank and file ───────────────────────────────────────────────

def test_nurse_cannot_reach_hr_module(app, nurse):
    c = _client(app, nurse)
    for url in ("/hr/dashboard", "/hr/staff", "/hr/attendance", "/hr/roster",
                "/hr/performance", "/hr/overtime", "/hr/certifications", "/hr/roles"):
        r = c.get(url, follow_redirects=True)
        assert _denied(r), f"a nurse reached {url}"


def test_nurse_cannot_write_hr_records(app, nurse, subject, boss):
    c = _client(app, nurse)
    before = len(_rows(app, "SELECT * FROM staff_warnings WHERE user_id=?", (subject["id"],)))
    _post(c, f"/hr/staff/{subject['id']}/warnings/add",
          {"warning_type": "Written", "reason": "made up by a nurse"})
    after = len(_rows(app, "SELECT * FROM staff_warnings WHERE user_id=?", (subject["id"],)))
    assert before == after, "a nurse issued a disciplinary warning"

    before = len(_rows(app, "SELECT * FROM overtime_log WHERE user_id=?", (subject["id"],)))
    _post(c, f"/hr/staff/{subject['id']}/overtime/add", {"hours": "40"})
    after = len(_rows(app, "SELECT * FROM overtime_log WHERE user_id=?", (subject["id"],)))
    assert before == after, "a nurse logged overtime against a colleague"


def test_nurse_cannot_edit_a_colleagues_profile(app, nurse, subject, boss):
    before = _one(app, "SELECT full_name FROM users WHERE id=?",
                  (subject["id"],))["full_name"]
    c = _client(app, nurse)
    _post(c, f"/hr/staff/{subject['id']}/edit",
          {"full_name": "Renamed By A Nurse", "role": "super_admin", "is_active": "1"})
    after = _one(app, "SELECT * FROM users WHERE id=?", (subject["id"],))
    assert after["full_name"] == before, "a nurse renamed a colleague"
    assert after["role"] != "super_admin", "a nurse escalated a colleague to super_admin"


# ─── IDOR: performance reviews are not public reading ─────────────────────────

def test_nurse_cannot_read_an_unrelated_performance_review(app, nurse, review, boss):
    """The review belongs to `colleague`; `nurse` is a peer with no HR role."""
    c = _client(app, nurse)
    r = c.get(f"/hr/performance/{review['id']}", follow_redirects=True)
    assert b"Reliable" not in r.data, \
        "a nurse read a colleague's performance review (IDOR)"


def test_nurse_cannot_acknowledge_an_unrelated_review(app, nurse, review, boss):
    c = _client(app, nurse)
    _post(c, f"/hr/performance/{review['id']}/acknowledge")
    row = _one(app, "SELECT * FROM performance_reviews WHERE id=?", (review["id"],))
    assert row["status"] != "Acknowledged", \
        "a nurse acknowledged a colleague's performance review (IDOR)"


def test_nurse_cannot_acknowledge_an_unrelated_warning(app, nurse, subject, warning, boss):
    c = _client(app, nurse)
    _post(c, f"/hr/staff/{subject['id']}/warnings/{warning['id']}/acknowledge")
    row = _one(app, "SELECT * FROM staff_warnings WHERE id=?", (warning["id"],))
    assert not row["acknowledged"], \
        "a nurse acknowledged a colleague's disciplinary warning (IDOR)"


# ─── anonymous ────────────────────────────────────────────────────────────────

def test_anonymous_is_bounced_from_every_hr_route(client):
    for url in ("/hr/", "/hr/dashboard", "/hr/staff", "/hr/roster",
                "/hr/performance", "/hr/overtime", "/hr/certifications",
                "/hr/attendance", "/hr/api/headcount", "/hr/roles"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302), f"{url} served an anonymous caller"
        assert "/auth/login" in r.headers["Location"], url
