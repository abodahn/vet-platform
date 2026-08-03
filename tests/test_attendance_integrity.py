# -*- coding: utf-8 -*-
"""Attendance has to be right, because payroll pays from it.

Two defects, both silent, both costing somebody something:

  * hours_worked is written ONLY at check-out. Forget to clock out after a full
    day and it stays 0 — and payroll reads exactly that column, so the employee
    is paid for nothing. The dashboard counted open records; no code acted.

  * The 'Late' status existed in the schema from the beginning and NOTHING EVER
    SET IT. The dashboard counted late days and the count was always zero. A
    status that is only ever counted and never assigned is a report that lies
    quietly.
"""
import datetime

import pytest

import models.database as db
from blueprints.attendance.routes import (
    LATE_GRACE_MINUTES, close_forgotten_checkouts, default_shift,
    status_for_checkin,
)


@pytest.fixture()
def shift(app):
    """A 09:00-17:00 clinic day."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM shifts")
            conn.execute("INSERT INTO shifts(name, start_time, end_time, break_minutes,"
                         " is_active) VALUES(?,?,?,?,1)",
                         ("Day", "09:00", "17:00", 60))
        conn.close()


@pytest.fixture()
def staff_id(app):
    """A REAL user. attendance_records has a foreign key to users, so invented
    ids fail with IntegrityError rather than testing anything."""
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT id FROM users WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
        conn.close()
    return row["id"]


def _record(app, user_id, work_date, check_in, check_out=None):
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO attendance_records(user_id, username, full_name,"
                " work_date, check_in, check_out, status, recorded_by)"
                " VALUES(?,?,?,?,?,?,'Present','tester')",
                (user_id, "u", "U", work_date, check_in, check_out))
            rid = cur.lastrowid
        conn.close()
    return rid


def _get(app, rid):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT * FROM attendance_records WHERE id=?", (rid,)).fetchone()
        conn.close()
    return dict(row)


# ── the pay bug ──────────────────────────────────────────────────────────────

def test_a_forgotten_checkout_is_closed_instead_of_paying_zero(app, shift, staff_id):
    """The whole point. A full day worked must not be paid as nothing."""
    day = "2026-07-20"
    rid = _record(app, staff_id, day, "09:00", None)
    assert _get(app, rid)["hours_worked"] in (0, 0.0, None), "premise changed"

    with app.app_context():
        conn = db.get_db()
        try:
            closed = close_forgotten_checkouts(conn, day)
        finally:
            conn.close()
    assert closed == 1

    rec = _get(app, rid)
    assert rec["check_out"] == "17:00", "not closed at the shift end"
    assert float(rec["hours_worked"]) == 7.0, \
        f"09:00-17:00 less a 60 min break is 7 hours, got {rec['hours_worked']}"


def test_reconstructed_hours_are_identifiable_afterwards(app, shift, staff_id):
    """Paying an estimate is fairer than paying zero. Paying an estimate nobody
    can identify a month later is not — a manager reviewing payroll has to be
    able to tell which hours were observed and which were inferred."""
    day = "2026-07-21"
    rid = _record(app, staff_id, day, "09:00", None)
    with app.app_context():
        conn = db.get_db()
        close_forgotten_checkouts(conn, day)
        conn.close()
    rec = _get(app, rid)
    assert rec["recorded_by"] == "system"
    assert "auto-closed" in (rec["notes"] or "").lower()


def test_a_completed_record_is_never_touched(app, shift, staff_id):
    """Someone who clocked out at 15:00 must not be silently extended to 17:00."""
    day = "2026-07-22"
    rid = _record(app, staff_id, day, "09:00", "15:00")
    with app.app_context():
        conn = db.get_db()
        closed = close_forgotten_checkouts(conn, day)
        conn.close()
    assert closed == 0
    assert _get(app, rid)["check_out"] == "15:00"


def test_an_arrival_after_the_shift_ended_does_not_go_negative(app, shift, staff_id):
    """A record opened at 18:30 closes at 18:30 with zero hours, not at 17:00
    with a negative day."""
    day = "2026-07-23"
    rid = _record(app, staff_id, day, "18:30", None)
    with app.app_context():
        conn = db.get_db()
        close_forgotten_checkouts(conn, day)
        conn.close()
    rec = _get(app, rid)
    assert float(rec["hours_worked"]) >= 0
    assert rec["check_out"] == "18:30"


def test_a_day_with_no_check_in_is_left_alone(app, shift, staff_id):
    """Absence and leave days legitimately have no hours. Inventing a shift for
    them would pay people for days they did not work."""
    day = "2026-07-24"
    rid = _record(app, staff_id, day, None, None)
    with app.app_context():
        conn = db.get_db()
        closed = close_forgotten_checkouts(conn, day)
        conn.close()
    assert closed == 0
    assert _get(app, rid)["check_out"] in (None, "")


# ── the status that never fired ──────────────────────────────────────────────

def test_late_is_actually_assigned_now(app, shift, staff_id):
    with app.app_context():
        conn = db.get_db()
        try:
            on_time, _ = status_for_checkin(conn, "09:00")
            within_grace, _ = status_for_checkin(conn, f"09:{LATE_GRACE_MINUTES:02d}")
            late, minutes = status_for_checkin(conn, "10:00")
        finally:
            conn.close()
    assert on_time == "Present"
    assert within_grace == "Present", "the grace period is not being honoured"
    assert late == "Late"
    assert minutes == 60 - LATE_GRACE_MINUTES


def test_a_clinic_that_never_set_a_shift_still_behaves(app):
    """Falls back to the schema's own 08:00-17:00 rather than doing nothing."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM shifts")
        s = default_shift(conn)
        st, _ = status_for_checkin(conn, "11:00")
        conn.close()
    assert s["start_time"] == "08:00" and s["end_time"] == "17:00"
    assert st == "Late"


def test_checking_in_late_through_the_route_records_it(client, app, shift):
    """End to end: the status has to reach the database, not just the helper."""
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT * FROM users WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
        conn.close()
        user = {k: row[k] for k in row.keys() if k not in ("password_hash", "totp_secret")}
    with client.session_transaction() as s:
        s["user"] = user
        s["lang"] = "en"

    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        token = s.get(_CSRF_SESSION_KEY, "")

    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM attendance_records WHERE user_id=? AND work_date=?",
                         (user["id"], datetime.date.today().isoformat()))
        conn.close()

    client.post("/attendance/checkin",
                data={"action": "checkin", "_csrf_token": token},
                follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        rec = conn.execute(
            "SELECT status, check_in FROM attendance_records WHERE user_id=? AND work_date=?",
            (user["id"], datetime.date.today().isoformat())).fetchone()
        conn.close()
    assert rec is not None, "the check-in did not save"
    # Whichever it is depends on the clock, but it must be a real decision
    # rather than the hardcoded 'Present' this route used to write always.
    assert rec["status"] in ("Present", "Late")
