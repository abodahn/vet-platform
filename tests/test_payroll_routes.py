# -*- coding: utf-8 -*-
"""Payroll — every route on the untested list, plus the arithmetic.

This is the module where a silent bug costs someone their salary. So the
tests here do three things a status-code test does not:

  * every write is read back out of `salaries` and compared field by field;
  * gross, net, allowances, deductions, tax and the absence deduction are
    each computed independently in the test and asserted numerically —
    including the attendance-driven figures `bulk-generate` derives;
  * the IDOR surface is probed as a real nurse session trying to open a
    colleague's payslip, list, export and attendance summary.
"""
import io

import pytest

import models.database as db

CSRF = "payroll-routes-test-token"


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


def _xlsx_rows(payload: bytes):
    """The workbook body. make_workbook puts the title in row 1-2, headers in
    row 3, data from row 4."""
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(payload))
    return [row for row in wb.active.iter_rows(min_row=4, values_only=True)]


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def owner(app):
    return _mkuser(app, "pay_owner", "clinic_owner", "Pay Test Owner")


@pytest.fixture
def finance(app):
    return _mkuser(app, "pay_finance", "finance", "Pay Test Finance")


@pytest.fixture
def hr_officer(app):
    return _mkuser(app, "pay_hr", "hr", "Pay Test HR")


@pytest.fixture
def nurse(app):
    return _mkuser(app, "pay_nurse", "nurse", "Pay Test Nurse")


@pytest.fixture
def employee(app):
    return _mkuser(app, "pay_employee", "groomer", "Pay Test Employee")


@pytest.fixture
def boss(app, owner):
    c = _client(app, owner)
    c.get("/payroll/")          # runs the payroll table bootstrap
    return c


# ─── salary_new ───────────────────────────────────────────────────────────────

def test_salary_new_get_renders(boss):
    assert boss.get("/payroll/salaries/new").status_code == 200


def test_salary_new_writes_the_row_and_computes_gross_and_net(app, boss, employee):
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2026 "
               "AND period_month=5", (employee["id"],))
    r = _post(boss, "/payroll/salaries/new", {
        "user_id": employee["id"], "period_year": "2026", "period_month": "5",
        "basic_salary": "8000", "allowances": "1200",
        "overtime_hours": "10", "overtime_rate": "75",
        "deductions": "300", "absence_deduction": "250", "tax_deduction": "430",
        "notes": "May payroll",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2026 "
                    "AND period_month=5", (employee["id"],))
    assert row is not None, "salaries/new returned 200 but wrote no salary record"

    # every input survived the round trip
    assert float(row["basic_salary"]) == 8000
    assert float(row["allowances"]) == 1200
    assert float(row["overtime_hours"]) == 10
    assert float(row["overtime_rate"]) == 75
    assert float(row["deductions"]) == 300
    assert float(row["absence_deduction"]) == 250
    assert float(row["tax_deduction"]) == 430
    assert row["status"] == "Draft"
    assert row["notes"] == "May payroll"

    # and the arithmetic, computed here rather than trusted
    expected_gross = 8000 + 1200 + 10 * 75            # 9950
    expected_net   = expected_gross - 300 - 250 - 430  # 8970
    assert float(row["gross"]) == expected_gross, "gross is wrong"
    assert float(row["net"]) == expected_net, "NET PAY IS WRONG"


def test_salary_new_defaults_missing_money_fields_to_zero(app, boss, employee):
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2025 "
               "AND period_month=1", (employee["id"],))
    _post(boss, "/payroll/salaries/new", {
        "user_id": employee["id"], "period_year": "2025", "period_month": "1",
        "basic_salary": "5000",
    })
    row = _one(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2025 "
                    "AND period_month=1", (employee["id"],))
    assert float(row["gross"]) == 5000
    assert float(row["net"]) == 5000


def test_salary_new_will_not_duplicate_a_period(app, boss, employee):
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2025 "
               "AND period_month=2", (employee["id"],))
    for basic in ("5000", "9999"):
        _post(boss, "/payroll/salaries/new", {
            "user_id": employee["id"], "period_year": "2025",
            "period_month": "2", "basic_salary": basic,
        })
    rows = _rows(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2025 "
                      "AND period_month=2", (employee["id"],))
    assert len(rows) == 1, "the same employee got two salary records for one month"
    assert float(rows[0]["basic_salary"]) == 5000, "the duplicate overwrote the original"


# ─── a salary to work with ────────────────────────────────────────────────────

@pytest.fixture
def salary(app, boss, employee):
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2026 "
               "AND period_month=6", (employee["id"],))
    _post(boss, "/payroll/salaries/new", {
        "user_id": employee["id"], "period_year": "2026", "period_month": "6",
        "basic_salary": "7000", "allowances": "500",
        "overtime_hours": "4", "overtime_rate": "60",
        "deductions": "100", "absence_deduction": "0", "tax_deduction": "200",
        "notes": "June payroll",
    })
    row = _one(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2026 "
                    "AND period_month=6", (employee["id"],))
    assert row is not None
    return row


# ─── salary_edit ──────────────────────────────────────────────────────────────

def test_salary_edit_get_renders(boss, salary):
    assert boss.get(f"/payroll/salaries/{salary['id']}/edit").status_code == 200


def test_salary_edit_recomputes_gross_and_net(app, boss, salary):
    r = _post(boss, f"/payroll/salaries/{salary['id']}/edit", {
        "basic_salary": "7500", "allowances": "900",
        "overtime_hours": "6.5", "overtime_rate": "80",
        "deductions": "150", "absence_deduction": "375", "tax_deduction": "260",
        "notes": "June payroll, corrected",
    })
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert float(row["basic_salary"]) == 7500
    assert float(row["allowances"]) == 900
    assert float(row["overtime_hours"]) == 6.5
    assert row["notes"] == "June payroll, corrected"

    expected_gross = 7500 + 900 + 6.5 * 80             # 8920.0
    expected_net   = expected_gross - 150 - 375 - 260   # 8135.0
    assert float(row["gross"]) == expected_gross
    assert float(row["net"]) == expected_net, \
        "editing a salary left a stale net — the employee would be paid the old figure"


def test_salary_edit_rounds_to_two_decimals(app, boss, salary):
    _post(boss, f"/payroll/salaries/{salary['id']}/edit", {
        "basic_salary": "1000.005", "allowances": "0",
        "overtime_hours": "1.333", "overtime_rate": "3",
        "deductions": "0", "absence_deduction": "0", "tax_deduction": "0",
    })
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert float(row["gross"]) == round(1000.005 + 1.333 * 3, 2)
    assert float(row["net"]) == round(1000.005 + 1.333 * 3, 2)


def test_salary_edit_missing_record_redirects(boss):
    assert boss.get("/payroll/salaries/999999/edit",
                    follow_redirects=True).status_code == 200


# ─── approve / pay lifecycle ──────────────────────────────────────────────────

def test_approve_moves_draft_to_approved(app, boss, salary):
    r = _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert row["status"] == "Approved", "approve returned 200 but the status is unchanged"


def test_pay_requires_approval_first(app, boss, salary):
    """A Draft salary must not be payable — approval is the control."""
    _post(boss, f"/payroll/salaries/{salary['id']}/pay",
          {"payment_method": "Cash", "payment_date": "2026-07-01"})
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert row["status"] == "Draft", "an unapproved salary was marked as paid"
    assert row["payment_date"] is None


def test_pay_records_method_date_and_payer(app, boss, owner, salary):
    _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    r = _post(boss, f"/payroll/salaries/{salary['id']}/pay",
              {"payment_method": "Bank Transfer", "payment_date": "2026-07-05"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert row["status"] == "Paid", "pay returned 200 but the record is not Paid"
    assert row["payment_method"] == "Bank Transfer"
    assert str(row["payment_date"])[:10] == "2026-07-05"
    assert row["paid_by"] == owner["id"], "the payer was not recorded"


def test_pay_defaults_the_date_to_today(app, boss, salary):
    from datetime import date
    _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    _post(boss, f"/payroll/salaries/{salary['id']}/pay", {"payment_method": "Cash"})
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert str(row["payment_date"])[:10] == date.today().isoformat()


def test_a_paid_salary_cannot_be_edited(app, boss, salary):
    _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    _post(boss, f"/payroll/salaries/{salary['id']}/pay", {"payment_method": "Cash"})
    before = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    _post(boss, f"/payroll/salaries/{salary['id']}/edit", {
        "basic_salary": "999999", "allowances": "0", "overtime_hours": "0",
        "overtime_rate": "0", "deductions": "0", "absence_deduction": "0",
        "tax_deduction": "0",
    })
    after = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert float(after["basic_salary"]) == float(before["basic_salary"]), \
        "a paid salary was rewritten"
    assert float(after["net"]) == float(before["net"])


def test_approving_a_paid_salary_does_not_revert_it(app, boss, salary):
    _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    _post(boss, f"/payroll/salaries/{salary['id']}/pay", {"payment_method": "Cash"})
    _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    row = _one(app, "SELECT * FROM salaries WHERE id=?", (salary["id"],))
    assert row["status"] == "Paid", "re-approving reverted a paid salary to Approved"


# ─── salary grades ────────────────────────────────────────────────────────────

def test_salary_grades_get_renders(boss):
    assert boss.get("/payroll/grades").status_code == 200


def test_salary_grades_post_upserts_every_role(app, boss):
    from blueprints.payroll.routes import _ROLES
    payload = {}
    for i, role in enumerate(_ROLES):
        payload[f"basic_{role}"] = str(1000 + i * 100)
        payload[f"ot_{role}"] = str(10 + i)
        payload[f"notes_{role}"] = f"grade for {role}"
    r = _post(boss, "/payroll/grades", payload)
    assert r.status_code == 200
    for i, role in enumerate(_ROLES):
        row = _one(app, "SELECT * FROM salary_grades WHERE role=?", (role,))
        assert row is not None, f"no grade row written for {role}"
        assert float(row["basic_salary"]) == 1000 + i * 100
        assert float(row["overtime_rate"]) == 10 + i
        assert row["notes"] == f"grade for {role}"

    # posting again must update in place, not insert a second row per role
    payload["basic_doctor"] = "24000"
    _post(boss, "/payroll/grades", payload)
    rows = _rows(app, "SELECT * FROM salary_grades WHERE role='doctor'")
    assert len(rows) == 1, "saving grades twice duplicated the doctor grade"
    assert float(rows[0]["basic_salary"]) == 24000


def test_api_grade_returns_the_stored_grade(app, boss):
    _post(boss, "/payroll/grades", {"basic_groomer": "6000", "ot_groomer": "50",
                                    "notes_groomer": "groomer band"})
    r = boss.get("/payroll/api/grade/groomer")
    assert r.status_code == 200
    payload = r.get_json()
    assert float(payload["basic_salary"]) == 6000
    assert float(payload["overtime_rate"]) == 50


def test_api_grade_unknown_role_returns_zeros(boss):
    payload = boss.get("/payroll/api/grade/not_a_real_role").get_json()
    assert payload == {"basic_salary": 0, "overtime_rate": 0}


# ─── bulk generate ────────────────────────────────────────────────────────────

@pytest.fixture
def attendance_month(app, employee):
    """February 2026 for one groomer: 18 present days, one of them a long day
    with 3 hours of overtime, and 2 absences. 20 recorded days in total."""
    _exec(app, "DELETE FROM attendance_records WHERE user_id=? AND work_date "
               "BETWEEN '2026-02-01' AND '2026-02-28'", (employee["id"],))
    with app.app_context():
        conn = db.get_db()
        for day in range(1, 18):        # 1..17 — ordinary 8-hour days
            conn.execute(
                "INSERT INTO attendance_records (user_id, username, full_name, "
                "work_date, status, hours_worked) VALUES (?,?,?,?, 'Present', 8)",
                (employee["id"], employee["username"], employee["full_name"],
                 f"2026-02-{day:02d}"))
        conn.execute(                    # 18th — an 11-hour day: 3h overtime
            "INSERT INTO attendance_records (user_id, username, full_name, "
            "work_date, status, hours_worked) VALUES (?,?,?, '2026-02-18', 'Present', 11)",
            (employee["id"], employee["username"], employee["full_name"]))
        for day in (19, 20):             # two absences
            conn.execute(
                "INSERT INTO attendance_records (user_id, username, full_name, "
                "work_date, status, hours_worked) VALUES (?,?,?,?, 'Absent', 0)",
                (employee["id"], employee["username"], employee["full_name"],
                 f"2026-02-{day:02d}"))
        conn.commit()
        conn.close()
    return {"total_days": 20, "absent_days": 2, "overtime_hours": 3.0}


def test_api_attendance_summary_counts_the_month(boss, employee, attendance_month):
    r = boss.get(f"/payroll/api/attendance/{employee['id']}/2026/2")
    assert r.status_code == 200
    s = r.get_json()
    assert s["total_days"] == 20
    assert s["present_days"] == 18
    assert s["absent_days"] == 2
    assert s["late_count"] == 0
    assert s["overtime_hours"] == 3.0, \
        "overtime is hours beyond the 8-hour standard on days actually worked"
    assert s["working_days"] == 20
    assert s["period_start"] == "2026-02-01"
    assert s["period_end"] == "2026-02-28"


def test_bulk_generate_derives_pay_from_attendance(app, boss, employee, attendance_month):
    """The whole point of bulk-generate: overtime and the absence deduction
    come out of attendance, and gross/net follow from them."""
    _exec(app, "DELETE FROM salaries WHERE period_year=2026 AND period_month=2")
    _post(boss, "/payroll/grades", {"basic_groomer": "6000", "ot_groomer": "50"})

    r = _post(boss, "/payroll/bulk-generate", {"year": "2026", "month": "2"})
    assert r.status_code == 200
    row = _one(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2026 "
                    "AND period_month=2", (employee["id"],))
    assert row is not None, "bulk-generate returned 200 but created no salary record"

    basic, ot_rate = 6000.0, 50.0
    ot_hours = 3.0
    absence_deduction = round((2 / 20) * basic, 2)      # 600.00
    gross = basic + ot_hours * ot_rate                   # 6150.00
    net   = gross - absence_deduction                    # 5550.00

    assert float(row["basic_salary"]) == basic, "the salary grade was not applied"
    assert float(row["overtime_rate"]) == ot_rate
    assert float(row["overtime_hours"]) == ot_hours, \
        "overtime hours were not pulled from attendance"
    assert float(row["absence_deduction"]) == absence_deduction, \
        "the absence deduction does not match absent_days / working_days * basic"
    assert float(row["gross"]) == gross
    assert float(row["net"]) == net, "BULK-GENERATED NET PAY IS WRONG"
    assert row["status"] == "Draft"
    assert "2 absent" in (row["notes"] or "")


def test_bulk_generate_skips_employees_who_already_have_a_record(app, boss, employee):
    _exec(app, "DELETE FROM salaries WHERE period_year=2026 AND period_month=3")
    _post(boss, "/payroll/salaries/new", {
        "user_id": employee["id"], "period_year": "2026", "period_month": "3",
        "basic_salary": "1234",
    })
    _post(boss, "/payroll/bulk-generate", {"year": "2026", "month": "3"})
    rows = _rows(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2026 "
                      "AND period_month=3", (employee["id"],))
    assert len(rows) == 1, "bulk-generate created a second record for the month"
    assert float(rows[0]["basic_salary"]) == 1234, \
        "bulk-generate overwrote a hand-entered salary"


def test_bulk_generate_never_creates_a_super_admin_payslip(app, boss):
    _exec(app, "DELETE FROM salaries WHERE period_year=2026 AND period_month=4")
    _post(boss, "/payroll/bulk-generate", {"year": "2026", "month": "4"})
    admins = _rows(app, "SELECT s.id FROM salaries s JOIN users u ON u.id=s.user_id "
                        "WHERE s.period_year=2026 AND s.period_month=4 "
                        "AND u.role='super_admin'")
    assert admins == []


def test_bulk_generate_running_twice_creates_nothing_new(app, boss):
    _exec(app, "DELETE FROM salaries WHERE period_year=2027 AND period_month=1")
    _post(boss, "/payroll/bulk-generate", {"year": "2027", "month": "1"})
    first = len(_rows(app, "SELECT * FROM salaries WHERE period_year=2027 "
                           "AND period_month=1"))
    _post(boss, "/payroll/bulk-generate", {"year": "2027", "month": "1"})
    second = len(_rows(app, "SELECT * FROM salaries WHERE period_year=2027 "
                            "AND period_month=1"))
    assert first == second and first > 0


# ─── payslip PDF ──────────────────────────────────────────────────────────────

def test_payslip_renders_a_pdf(boss, salary):
    r = boss.get(f"/payroll/salaries/{salary['id']}/payslip")
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "application/pdf", \
        "the payslip route fell back to a redirect instead of producing a PDF"
    assert r.data[:4] == b"%PDF"
    assert "attachment" in r.headers.get("Content-Disposition", "")


def test_payslip_of_a_missing_record_is_404(boss):
    assert boss.get("/payroll/salaries/999999/payslip").status_code == 404


def test_an_employee_may_download_their_own_payslip(app, employee, salary):
    c = _client(app, employee)
    r = c.get(f"/payroll/salaries/{salary['id']}/payslip")
    assert r.status_code == 200
    assert r.data[:4] == b"%PDF", "an employee could not open their own payslip"


# ─── IDOR ─────────────────────────────────────────────────────────────────────

def test_nurse_cannot_open_a_colleagues_payslip(app, nurse, salary):
    """Any logged-in user could open any payslip. Pinned shut."""
    c = _client(app, nurse)
    r = c.get(f"/payroll/salaries/{salary['id']}/payslip", follow_redirects=True)
    assert r.data[:4] != b"%PDF", "a nurse downloaded a colleague's payslip (IDOR)"
    assert r.headers["Content-Type"] != "application/pdf"


def test_nurse_cannot_open_a_colleagues_salary_detail(app, nurse, salary):
    c = _client(app, nurse)
    r = c.get(f"/payroll/salaries/{salary['id']}", follow_redirects=True)
    assert b"Pay Test Employee" not in r.data, \
        "a nurse read a colleague's salary detail (IDOR)"


def test_nurse_salary_list_shows_only_their_own(app, nurse, salary, employee, boss):
    """/payroll/salaries listed every employee's pay to anyone logged in."""
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2026 "
               "AND period_month=6", (nurse["id"],))
    _post(boss, "/payroll/salaries/new", {
        "user_id": nurse["id"], "period_year": "2026", "period_month": "6",
        "basic_salary": "4000",
    })
    c = _client(app, nurse)
    r = c.get("/payroll/salaries?year=2026&month=6")
    assert r.status_code == 200
    assert b"Pay Test Nurse" in r.data, "an employee cannot see their own payslip row"
    assert b"Pay Test Employee" not in r.data, \
        "a nurse read a colleague's pay from the salary list (IDOR)"


def test_nurse_xlsx_export_leaks_no_colleague_pay(app, nurse, salary, employee, boss):
    """The list was scoped but the export beside it was not — same hole, same
    data, one click further along."""
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2026 "
               "AND period_month=6", (nurse["id"],))
    _post(boss, "/payroll/salaries/new", {
        "user_id": nurse["id"], "period_year": "2026", "period_month": "6",
        "basic_salary": "4000",
    })
    c = _client(app, nurse)
    r = c.get("/payroll/salaries/export/xlsx?year=2026&month=6")
    if r.headers.get("Content-Type", "").startswith(
            "application/vnd.openxmlformats"):
        names = [row[0] for row in _xlsx_rows(r.data)]
        assert "Pay Test Employee" not in names, \
            "a nurse exported every employee's pay to xlsx (IDOR)"
    else:
        assert b"Pay Test Employee" not in r.data


def test_nurse_cannot_read_a_colleagues_attendance_summary(app, nurse, employee,
                                                           attendance_month, boss):
    c = _client(app, nurse)
    r = c.get(f"/payroll/api/attendance/{employee['id']}/2026/2")
    assert r.status_code == 403, \
        "a nurse read a colleague's attendance summary through the payroll API (IDOR)"


def test_employee_may_read_their_own_attendance_summary(app, employee, attendance_month):
    c = _client(app, employee)
    r = c.get(f"/payroll/api/attendance/{employee['id']}/2026/2")
    assert r.status_code == 200
    assert r.get_json()["absent_days"] == 2


def test_nurse_cannot_read_the_pay_bands(app, nurse, boss):
    """api/grade hands back the basic salary for any role — a colleague's pay
    by another name."""
    _post(boss, "/payroll/grades", {"basic_doctor": "24000", "ot_doctor": "150"})
    c = _client(app, nurse)
    r = c.get("/payroll/api/grade/doctor")
    leaked = r.status_code == 200 and float(
        (r.get_json() or {}).get("basic_salary") or 0) == 24000
    assert not leaked, "a nurse read the doctor pay band from /payroll/api/grade"


# ─── role gating ──────────────────────────────────────────────────────────────

def _denied(resp):
    return b"permission" in resp.data.lower()


def test_finance_role_runs_payroll(app, finance, employee):
    c = _client(app, finance)
    for url in ("/payroll/", "/payroll/salaries", "/payroll/salaries/new",
                "/payroll/grades"):
        r = c.get(url, follow_redirects=True)
        assert r.status_code == 200, url
        assert not _denied(r), f"the finance role was refused {url}"


def test_hr_role_cannot_create_a_salary(app, hr_officer, employee):
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2024 "
               "AND period_month=1", (employee["id"],))
    c = _client(app, hr_officer)
    r = _post(c, "/payroll/salaries/new", {
        "user_id": employee["id"], "period_year": "2024", "period_month": "1",
        "basic_salary": "99999",
    })
    assert _one(app, "SELECT * FROM salaries WHERE user_id=? AND period_year=2024 "
                     "AND period_month=1", (employee["id"],)) is None, \
        "the hr role created a salary record"
    assert _denied(r)


def test_hr_role_cannot_approve_or_pay(app, hr_officer, salary, boss):
    c = _client(app, hr_officer)
    _post(c, f"/payroll/salaries/{salary['id']}/approve")
    assert _one(app, "SELECT * FROM salaries WHERE id=?",
                (salary["id"],))["status"] == "Draft", \
        "the hr role approved a salary"
    _post(boss, f"/payroll/salaries/{salary['id']}/approve")
    _post(c, f"/payroll/salaries/{salary['id']}/pay", {"payment_method": "Cash"})
    assert _one(app, "SELECT * FROM salaries WHERE id=?",
                (salary["id"],))["status"] == "Approved", \
        "the hr role paid a salary"


def test_hr_role_cannot_set_pay_grades(app, hr_officer, boss):
    _post(boss, "/payroll/grades", {"basic_auditor": "3000", "ot_auditor": "20"})
    c = _client(app, hr_officer)
    _post(c, "/payroll/grades", {"basic_auditor": "88888", "ot_auditor": "99"})
    row = _one(app, "SELECT * FROM salary_grades WHERE role='auditor'")
    assert float(row["basic_salary"]) == 3000, "the hr role rewrote a pay grade"


def test_hr_role_cannot_bulk_generate(app, hr_officer):
    _exec(app, "DELETE FROM salaries WHERE period_year=2023 AND period_month=1")
    c = _client(app, hr_officer)
    _post(c, "/payroll/bulk-generate", {"year": "2023", "month": "1"})
    assert _rows(app, "SELECT * FROM salaries WHERE period_year=2023 "
                      "AND period_month=1") == [], \
        "the hr role bulk-generated a payroll run"


def test_nurse_cannot_write_payroll(app, nurse, employee, salary):
    c = _client(app, nurse)
    _exec(app, "DELETE FROM salaries WHERE user_id=? AND period_year=2023 "
               "AND period_month=2", (employee["id"],))
    _post(c, "/payroll/salaries/new", {
        "user_id": nurse["id"], "period_year": "2023", "period_month": "2",
        "basic_salary": "500000",
    })
    assert _one(app, "SELECT * FROM salaries WHERE period_year=2023 "
                     "AND period_month=2") is None, "a nurse created their own salary"

    _post(c, f"/payroll/salaries/{salary['id']}/edit", {
        "basic_salary": "500000", "allowances": "0", "overtime_hours": "0",
        "overtime_rate": "0", "deductions": "0", "absence_deduction": "0",
        "tax_deduction": "0",
    })
    assert float(_one(app, "SELECT * FROM salaries WHERE id=?",
                      (salary["id"],))["basic_salary"]) == 7000, \
        "a nurse edited a salary record"


# ─── xlsx export (manager) ────────────────────────────────────────────────────

def test_manager_xlsx_export_carries_the_numbers(app, boss, salary):
    r = boss.get("/payroll/salaries/export/xlsx?year=2026&month=6")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    body = _xlsx_rows(r.data)
    mine = [row for row in body if row[0] == "Pay Test Employee"]
    assert mine, "the payroll export rendered but carried no rows"
    row = mine[0]
    # Name, Role, Year, Month, Basic, Allowances, OT Hrs, OT Rate, Gross,
    # Deductions, Absence Ded, Tax Ded, Net, Status, Payment Date
    assert row[2] == 2026
    assert row[3] == "Jun"
    assert float(row[4]) == 7000
    assert float(row[8]) == 7000 + 500 + 4 * 60      # gross 7740
    assert float(row[12]) == 7740 - 100 - 0 - 200    # net 7440


# ─── anonymous ────────────────────────────────────────────────────────────────

def test_anonymous_is_bounced_from_every_payroll_route(client):
    for url in ("/payroll/", "/payroll/salaries", "/payroll/salaries/new",
                "/payroll/grades", "/payroll/salaries/export/xlsx",
                "/payroll/api/grade/doctor", "/payroll/api/attendance/1/2026/2",
                "/payroll/salaries/1/payslip"):
        r = client.get(url, follow_redirects=False)
        assert r.status_code in (301, 302), f"{url} served an anonymous caller"
        assert "/auth/login" in r.headers["Location"], url
