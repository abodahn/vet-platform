"""Cross-module links between HR, attendance and payroll.

The people modules only earn their keep if they behave as one system: a payslip
has to be traceable back to the attendance that produced it, and a staff record
has to reach every facet of that person. These tests pin the links that carry
that, plus the two ways they can break — a missing target and a viewer who is
not allowed at the other end.

SQLite only, no network.
"""
import pytest

import models.database as db


PERIOD_YEAR, PERIOD_MONTH = 2026, 6
PERIOD_FROM, PERIOD_TO = "2026-06-01", "2026-06-30"


def _seed_person(app, username, with_attendance=True):
    """A staff member, their June attendance, and their June payslip."""
    with app.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO users (username,password_hash,full_name,role,is_active) "
            "VALUES (?,?,?,?,1)",
            (username, "x", f"Test {username}", "nurse"))
        uid = conn.execute(
            "SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]

        if with_attendance:
            for day, status, hours in (("2026-06-01", "Present", 8.0),
                                       ("2026-06-02", "Absent", 0.0),
                                       ("2026-06-03", "Late", 7.5),
                                       # outside the period — must not be counted
                                       ("2026-07-01", "Present", 8.0)):
                conn.execute(
                    "INSERT INTO attendance_records "
                    "(user_id,username,full_name,work_date,status,hours_worked) "
                    "VALUES (?,?,?,?,?,?)",
                    (uid, username, f"Test {username}", day, status, hours))

        conn.execute(
            "INSERT INTO salaries (user_id,period_year,period_month,basic_salary,"
            "gross,net,status) VALUES (?,?,?,?,?,?,'Draft')",
            (uid, PERIOD_YEAR, PERIOD_MONTH, 5000, 5000, 4500))
        sid = conn.execute(
            "SELECT id FROM salaries WHERE user_id=?", (uid,)).fetchone()["id"]
        conn.commit()
        conn.close()
    return uid, sid


@pytest.fixture(scope="module")
def worked(app):
    """A staff member who has attendance behind their payslip."""
    # The payroll blueprint creates its tables in before_request.
    app.test_client().get("/payroll/")
    return _seed_person(app, "link_worked")


@pytest.fixture(scope="module")
def unrecorded(app):
    """A staff member whose payslip has no attendance behind it at all."""
    app.test_client().get("/payroll/")
    return _seed_person(app, "link_unrecorded", with_attendance=False)


# ── payslip → the employee, and the attendance that produced it ───────────────

def test_payslip_links_to_the_employee(auth_client, worked):
    uid, sid = worked
    body = auth_client.get(f"/payroll/salaries/{sid}").get_data(as_text=True)
    assert f"/hr/staff/{uid}" in body


def test_payslip_links_to_attendance_for_that_period(auth_client, worked):
    uid, sid = worked
    body = auth_client.get(f"/payroll/salaries/{sid}").get_data(as_text=True)
    # The link must carry the employee AND the period, not just the employee —
    # otherwise it lands on a date range that has nothing to do with the pay.
    assert f"user_id={uid}" in body
    assert f"date_from={PERIOD_FROM}" in body
    assert f"date_to={PERIOD_TO}" in body
    # and it must resolve
    r = auth_client.get(f"/attendance/records?user_id={uid}"
                        f"&date_from={PERIOD_FROM}&date_to={PERIOD_TO}")
    assert r.status_code == 200


def test_payslip_attendance_counts_only_that_period(auth_client, worked):
    """The July record seeded alongside June must not be counted."""
    uid, sid = worked
    body = auth_client.get(f"/payroll/salaries/{sid}").get_data(as_text=True)
    days = body.split("Days Recorded")[1].split("</tr>")[0]
    assert ">3<" in days, days


# ── staff record → their payslips ─────────────────────────────────────────────

def test_staff_detail_links_to_their_payslips(auth_client, worked):
    uid, sid = worked
    body = auth_client.get(f"/hr/staff/{uid}").get_data(as_text=True)
    assert f"/payroll/salaries/{sid}" in body


def test_staff_detail_links_to_their_attendance_and_leave(auth_client, worked):
    uid, _ = worked
    body = auth_client.get(f"/hr/staff/{uid}").get_data(as_text=True)
    assert f"/attendance/records?user_id={uid}" in body
    assert f"/attendance/leaves?user_id={uid}" in body


# ── the missing cases ─────────────────────────────────────────────────────────

def test_payslip_with_no_attendance_renders_cleanly(auth_client, unrecorded):
    uid, sid = unrecorded
    r = auth_client.get(f"/payroll/salaries/{sid}")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "No attendance was recorded" in body
    # The link out is still there — an empty period is not a reason to strand
    # the reader — and it still resolves.
    assert f"user_id={uid}" in body
    assert auth_client.get(f"/attendance/records?user_id={uid}"
                           f"&date_from={PERIOD_FROM}"
                           f"&date_to={PERIOD_TO}").status_code == 200


def test_payslip_for_a_deleted_employee_renders_without_a_dead_link(auth_client, app):
    with app.app_context():
        conn = db.get_db()
        conn.execute(
            "INSERT INTO salaries (user_id,period_year,period_month,basic_salary,"
            "gross,net,status) VALUES (424242,?,?,1000,1000,1000,'Draft')",
            (PERIOD_YEAR, PERIOD_MONTH))
        sid = conn.execute(
            "SELECT id FROM salaries WHERE user_id=424242").fetchone()["id"]
        conn.commit()
        conn.close()
    r = auth_client.get(f"/payroll/salaries/{sid}")
    assert r.status_code == 200
    assert "/hr/staff/424242" not in r.get_data(as_text=True)


# ── a link must not skip an authorisation check ───────────────────────────────

def _as(app, role, user_id):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = {"id": user_id, "username": "probe",
                        "role": role, "full_name": "Probe"}
    return c


def test_colleague_cannot_open_someone_elses_payslip(app, worked):
    uid, sid = worked
    r = _as(app, "nurse", uid + 9999).get(f"/payroll/salaries/{sid}",
                                          follow_redirects=False)
    assert r.status_code == 302


def test_employee_can_open_their_own_payslip(app, worked):
    uid, sid = worked
    r = _as(app, "nurse", uid).get(f"/payroll/salaries/{sid}",
                                   follow_redirects=False)
    assert r.status_code == 200


def test_payroll_role_can_open_any_payslip(app, worked):
    _, sid = worked
    r = _as(app, "finance", 777777).get(f"/payroll/salaries/{sid}",
                                        follow_redirects=False)
    assert r.status_code == 200


def test_attendance_report_ignores_user_id_from_a_non_manager(app, worked):
    """?user_id= must not widen what a non-manager sees."""
    uid, _ = worked
    body = _as(app, "nurse", uid + 9999).get(
        f"/attendance/report?year={PERIOD_YEAR}&month={PERIOD_MONTH}"
        f"&user_id={uid}").get_data(as_text=True)
    assert "Test link_worked" not in body
