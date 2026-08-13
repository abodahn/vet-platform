# -*- coding: utf-8 -*-
"""Booking any appointment from inside the exam screen.

"بس برضه أنا عايز لو أنا جيت أحجز مواعيد يبقى ده موجود … نجيبه جوه الأيقونة دي"

Booking the FOLLOW-UP already worked inline. Everything else — the grooming
slot the owner asks about while paying, a surgery date, a visit for the other
animal — was a link to /appointments/new, which leaves the screen and discards
whatever is half-typed. Note 3 in the same session was explicitly "ما تحولنيش
على صفحة تانية".
"""
import io
from datetime import date, timedelta

from conftest import get_csrf


def _owner_and_pets(app):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        cur = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                           ("صاحب المواعيد", "01000000955"))
        oid = cur.lastrowid
        pets = []
        for nm in ("لولو", "بسبس"):
            c = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, is_active)"
                " VALUES(?,?,?,1)", (oid, nm, "Cat"))
            pets.append(c.lastrowid)
        conn.commit()
        conn.close()
    return oid, pets


def _appts(app, owner_id):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM appointments WHERE owner_id=? ORDER BY id", (owner_id,)).fetchall()]
        conn.close()
    return rows


def test_a_grooming_slot_can_be_booked_without_leaving_the_screen(auth_client, app):
    oid, pets = _owner_and_pets(app)
    when = (date.today() + timedelta(days=3)).isoformat()

    r = auth_client.post("/visits/exam/api/appointment",
                         json={"owner_id": oid, "pet_id": pets[0],
                               "appointment_type": "Grooming", "appt_date": when,
                               "appt_start": "14:00", "doctor_name": "Dr. Sara Elgohary",
                               "reason": "قص شعر"},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})

    assert r.status_code == 200, r.data[:400]
    rows = _appts(app, oid)
    assert len(rows) == 1
    assert rows[0]["appointment_type"] == "Grooming"
    assert rows[0]["appt_date"] == when
    assert rows[0]["appt_start"] == "14:00"
    assert rows[0]["doctor_name"] == "Dr. Sara Elgohary"


def test_the_new_booking_comes_back_in_the_same_response(auth_client, app):
    """So the Planned tab updates without a page load — the whole point."""
    oid, pets = _owner_and_pets(app)
    when = (date.today() + timedelta(days=5)).isoformat()
    r = auth_client.post("/visits/exam/api/appointment",
                         json={"owner_id": oid, "pet_id": pets[1],
                               "appointment_type": "Surgery", "appt_date": when},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    data = r.get_json()
    assert data.get("ok") is True
    assert any(a.get("appointment_type") == "Surgery" for a in data.get("upcoming", [])), \
        "the booking is not in the refreshed list, so the tab would look unchanged"
    assert "upcoming" in data.get("badges", {}), "the Planned badge would not move"


def test_a_missing_time_does_not_silently_lose_the_booking(auth_client, app):
    """appt_start is NOT NULL — this is exactly how follow-ups used to vanish."""
    oid, pets = _owner_and_pets(app)
    when = (date.today() + timedelta(days=2)).isoformat()
    r = auth_client.post("/visits/exam/api/appointment",
                         json={"owner_id": oid, "pet_id": pets[0],
                               "appointment_type": "Consultation",
                               "appt_date": when, "appt_start": ""},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 200
    rows = _appts(app, oid)
    assert len(rows) == 1, "a booking with no time was dropped"
    assert rows[0]["appt_start"] == "09:00"


def test_a_date_is_required(auth_client, app):
    oid, _ = _owner_and_pets(app)
    r = auth_client.post("/visits/exam/api/appointment",
                         json={"owner_id": oid, "appointment_type": "Lab"},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 400
    assert _appts(app, oid) == []


def test_you_cannot_book_another_clients_animal(auth_client, app):
    """A hand-edited request must not attach somebody else's pet."""
    oid_a, pets_a = _owner_and_pets(app)
    oid_b, _ = _owner_and_pets(app)
    when = (date.today() + timedelta(days=1)).isoformat()

    r = auth_client.post("/visits/exam/api/appointment",
                         json={"owner_id": oid_b, "pet_id": pets_a[0],
                               "appointment_type": "Consultation", "appt_date": when},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 400
    assert _appts(app, oid_b) == []


def test_booking_requires_a_login(client, app):
    oid, _ = _owner_and_pets(app)
    r = client.post("/visits/exam/api/appointment",
                    json={"owner_id": oid, "appt_date": date.today().isoformat()})
    assert r.status_code in (302, 401, 403)


def test_the_booking_inputs_do_not_ride_along_with_the_visit():
    """They sit inside <form id="hwForm">.

    A name= on any of them would post it with the examination and land in
    exam_submit's form dict, where a stray appt_date could be mistaken for a
    follow-up.
    """
    src = io.open("templates/visits/exam.html", encoding="utf-8").read()
    i = src.index('id="hwBookFold"')
    block = src[i:src.index("</details>", i)]
    assert "name=" not in block, \
        "an inline booking field carries name= and will be posted with the visit"
    for want in ('id="bkPet"', 'id="bkType"', 'id="bkDate"', 'id="bkTime"'):
        assert want in block, "missing %s" % want


def test_the_calendar_link_is_no_longer_the_primary_action():
    src = io.open("templates/visits/exam.html", encoding="utf-8").read()
    i = src.index('id="lnkBook"')
    tag = src[i - 120:i + 200]
    assert "pf-btn-primary" not in tag, \
        "leaving the screen is still presented as the main way to book"
