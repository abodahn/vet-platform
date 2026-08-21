# -*- coding: utf-8 -*-
"""Dialect regressions on the two oldest raw-SQL blueprints (HR, appointments).

Both modules once shipped SQL only PostgreSQL accepts — PG-flavoured DDL in
_ensure_hr_tables and a hardcoded %s placeholder on the appointment detail
page — and both crashed the route with an OperationalError on SQLite. The
routes below are the exact ones that crashed; they are asserted to render, not
merely to redirect, because a 302 to the login page would pass a status check
while proving nothing about the SQL.
"""
from datetime import date, timedelta

import pytest

import models.database as db


PHONE = "01000000931"  # unique to this file — the suite shares one database


@pytest.fixture(scope="module")
def booking(app):
    """An owner, a pet and one appointment to open the detail page on."""
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                oid = conn.execute(
                    "INSERT INTO owners (full_name, phone) VALUES (?,?)",
                    ("Dialect Test Owner", PHONE)).lastrowid
                pid = conn.execute(
                    "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                    (oid, "Semicolon", "Cat")).lastrowid
                aid = conn.execute(
                    "INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
                    " appt_end, status, doctor_name, appointment_type, duration_min)"
                    " VALUES (?,?,?,?,?,?,?,?,30)",
                    (oid, pid, (date.today() + timedelta(days=3)).isoformat(),
                     "10:00", "", "Scheduled", "", "Consultation")).lastrowid
        finally:
            conn.close()
    return {"owner_id": oid, "pet_id": pid, "appt_id": aid}


def test_appointment_detail_renders_on_sqlite(auth_client, booking):
    """bug-030: the pet lookup used a %s placeholder SQLite cannot parse."""
    r = auth_client.get(f"/appointments/{booking['appt_id']}")
    assert r.status_code == 200
    assert b"Semicolon" in r.data


def test_hr_bootstrap_creates_its_tables_on_sqlite(app, auth_client):
    """bug-023/031: _ensure_hr_tables emitted PG-only DDL SQLite rejects.

    The dashboard GET is what runs the bootstrap, so a 200 here means every
    CREATE TABLE parsed; the table probe afterwards means they were really
    created rather than swallowed by an exception handler.
    """
    assert auth_client.get("/hr/dashboard").status_code == 200
    with app.app_context():
        conn = db.get_db()
        try:
            for table in ("performance_reviews", "staff_warnings",
                          "staff_certifications", "staff_notes", "overtime_log"):
                conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            # The ALTER loop is idempotent and silent; check it actually landed.
            conn.execute("SELECT contract_type, hire_date FROM users LIMIT 1").fetchone()
        finally:
            conn.close()


def test_hr_staff_search_survives_ilike(auth_client):
    """The search filter emits ILIKE, which SQLite has no keyword for."""
    r = auth_client.get("/hr/staff?q=Dialect")
    assert r.status_code == 200


def test_hr_certifications_survives_interval_arithmetic(auth_client):
    """The expiring-soon query uses CURRENT_DATE + INTERVAL '30 days'."""
    r = auth_client.get("/hr/certifications")
    assert r.status_code == 200
