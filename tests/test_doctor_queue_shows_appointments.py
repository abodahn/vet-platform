# -*- coding: utf-8 -*-
"""The doctor queue must actually list today's appointments — with their time.

Every panel in this module is wrapped in a bare `except` that substitutes an
empty list, so a broken query renders as "Queue is empty today!" rather than a
500. Only an assertion on the rendered row tells a working query from a
swallowed one, which is why these check the HTML and not the status code.

The time cell had the other half of the same schema drift: the templates read
`a.appointment_date`, which does not exist (the columns are `appt_date` and
`appt_start`), so a row that reached the page arrived with a blank time.
"""
from datetime import date

import pytest

import models.database as db

TODAY = date.today().isoformat()
APPT_TIME = "09:15"


def _row_of(html, pet_name):
    """The markup just before `pet_name` — the time cell is the column before it."""
    i = html.find(pet_name)
    assert i != -1, f"{pet_name} is missing from the page"
    return html[max(0, i - 600):i]


@pytest.fixture(scope="module")
def booked(app):
    """One owner, one pet, one appointment today — phone unique to this file."""
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                oid = conn.execute(
                    "INSERT INTO owners (full_name, phone) VALUES (?,?)",
                    ("Queue Owner", "01000000931")).lastrowid
                pid = conn.execute(
                    "INSERT INTO pets (owner_id, pet_name, species, is_active)"
                    " VALUES (?,?,?,1)", (oid, "Zeitoun", "Cat")).lastrowid
                aid = conn.execute(
                    "INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
                    " status, doctor_name) VALUES (?,?,?,?,?,?)",
                    (oid, pid, TODAY, APPT_TIME, "Scheduled", "Dr. Queue House")).lastrowid
        finally:
            conn.close()
    return {"owner_id": oid, "pet_id": pid, "appt_id": aid}


def test_queue_lists_todays_appointment_with_its_time(auth_client, booked):
    html = auth_client.get("/doctor/queue").get_data(as_text=True)
    assert "Zeitoun" in html, "today's appointment is missing from the queue"
    assert APPT_TIME in _row_of(html, "Zeitoun"), "the queue row has no start time"


def test_workspace_lists_todays_appointment_with_its_time(auth_client, booked):
    html = auth_client.get("/doctor/").get_data(as_text=True)
    assert "Zeitoun" in html, "today's appointment is missing from the workspace"
    assert APPT_TIME in _row_of(html, "Zeitoun"), "the workspace row has no start time"


def test_schedule_shows_the_booking_time(auth_client, booked):
    html = auth_client.get("/doctor/schedule").get_data(as_text=True)
    assert APPT_TIME in _row_of(html, "Zeitoun"), "the week view has no start time"


# ── the gap the adversarial verifier found ───────────────────────────────────
#
# Every test above uses auth_client, which signs in as `admin`. The fix report
# claimed both an admin session and a real role='doctor' session had been
# exercised; only the admin one had. That matters here specifically, because
# the queue filters on the signed-in doctor's own name — so the admin path can
# pass while the path an actual vet uses returns nothing.

def _doctor_client(app, full_name):
    """A client signed in as a real user with role='doctor'."""
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT id FROM users WHERE username=?",
                           ("dr_queue_probe",)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role,"
                " is_active) VALUES (?,?,?,?,1)",
                ("dr_queue_probe", db._hash_password("Probe@2026!"),
                 full_name, "doctor"))
            conn.commit()
        else:
            conn.execute("UPDATE users SET full_name=?, role='doctor',"
                         " is_active=1 WHERE username=?",
                         (full_name, "dr_queue_probe"))
            conn.commit()
        conn.close()

    c = app.test_client()
    c.post("/auth/login", data={"username": "dr_queue_probe",
                                "password": "Probe@2026!"})
    c.get("/")
    return c


def test_a_real_doctor_sees_their_own_queue(app, booked):
    """The path an actual vet walks, not the admin one.

    If this ever fails while the admin tests pass, the queue is filtering on
    something only an admin satisfies - which is precisely how bug-215 stayed
    open: the screen looked fine to whoever checked it.
    """
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT doctor_name FROM appointments"
            " WHERE appt_date = date('now','localtime')"
            " AND doctor_name IS NOT NULL AND doctor_name <> ''"
            " ORDER BY id DESC LIMIT 1").fetchone()
        conn.close()
    if not row:
        import pytest
        pytest.skip("no appointment today carries a doctor name to sign in as")

    c = _doctor_client(app, row["doctor_name"])
    r = c.get("/doctor/queue")
    assert r.status_code == 200, "a doctor cannot open the doctor queue"
    body = r.get_data(as_text=True)
    assert "queue" in body.lower() or "طابور" in body


def test_the_queue_is_not_empty_for_the_doctor_it_belongs_to(app, booked):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT doctor_name, pet_id FROM appointments"
            " WHERE appt_date = date('now','localtime')"
            " AND doctor_name IS NOT NULL AND doctor_name <> ''"
            " ORDER BY id DESC LIMIT 1").fetchone()
        pet = None
        if row and row["pet_id"]:
            pet = conn.execute("SELECT pet_name FROM pets WHERE id=?",
                               (row["pet_id"],)).fetchone()
        conn.close()
    if not row or not pet:
        import pytest
        pytest.skip("no today appointment with both a doctor and a pet")

    body = _doctor_client(app, row["doctor_name"]).get(
        "/doctor/queue").get_data(as_text=True)
    assert pet["pet_name"] in body, (
        "the doctor's own patient is missing from their own queue - "
        "this is bug-215 for the role that actually uses the screen")
