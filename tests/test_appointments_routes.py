# -*- coding: utf-8 -*-
"""Front desk: the appointment book and the waiting-room TV.

Every write here is asserted against the database afterwards, not against the
HTTP status. A route that renders 200 and writes nothing is the failure mode
this codebase keeps producing — the waiting-room display selected a column
that does not exist for months and nobody noticed, because the crash was
swallowed and the page rendered "no one waiting".

The database is shared with the rest of the suite, so every fixture builds its
own owner/pet and every assertion is scoped to rows it created itself.
SQLite, no network.
"""
import json
from datetime import date, timedelta

import pytest

import models.database as db
from blueprints.appointments.routes import mask_owner_name


# ─── helpers ──────────────────────────────────────────────────────────────────

def _csrf(client):
    """The app validates `_csrf_token`; it is seeded by any GET."""
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _row(sql, params=()):
    conn = db.get_db()
    try:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _mk_owner(full_name, phone, **extra):
    cols = ["full_name", "phone"] + list(extra)
    vals = [full_name, phone] + list(extra.values())
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                f"INSERT INTO owners ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                vals)
            return cur.lastrowid
    finally:
        conn.close()


def _mk_pet(owner_id, pet_name, species="Cat"):
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                (owner_id, pet_name, species))
            return cur.lastrowid
    finally:
        conn.close()


def _mk_appt(owner_id, pet_id, appt_date, appt_start="09:00", status="Scheduled",
             doctor_name="", appointment_type="Consultation"):
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
                " appt_end, status, doctor_name, appointment_type, duration_min)"
                " VALUES (?,?,?,?,?,?,?,?,30)",
                (owner_id, pet_id, appt_date, appt_start, "", status, doctor_name,
                 appointment_type))
            return cur.lastrowid
    finally:
        conn.close()


TODAY = date.today().isoformat()
FUTURE = (date.today() + timedelta(days=40)).isoformat()


# ─── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def desk(app):
    """One owner with two pets, one of them named in Arabic only."""
    with app.app_context():
        oid = _mk_owner("Ahmed Zaki Elgohary", "01000000701",
                        full_name_ar="أحمد زكي الجوهري")
        p_en = _mk_pet(oid, "Biscuit", "Dog")
        p_ar = _mk_pet(oid, "لولو", "Cat")
    return {"owner_id": oid, "pet_en": p_en, "pet_ar": p_ar}


# ═══ status transitions ═══════════════════════════════════════════════════════

def test_status_walk_scheduled_to_completed(app, auth_client, desk):
    """scheduled → confirmed → checked-in → completed, verified in the DB."""
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "08:00")

        _post(auth_client, f"/appointments/{aid}/status", {"status": "Confirmed"})
        assert _row("SELECT status FROM appointments WHERE id=?", (aid,))["status"] == "Confirmed"

        _post(auth_client, f"/appointments/{aid}/status", {"status": "Checked-in"})
        r = _row("SELECT status, checked_in_at FROM appointments WHERE id=?", (aid,))
        assert r["status"] == "Checked-in"
        assert r["checked_in_at"], "Checked-in must stamp checked_in_at"

        _post(auth_client, f"/appointments/{aid}/status", {"status": "Completed"})
        r = _row("SELECT status, checked_in_at, checked_out_at FROM appointments WHERE id=?", (aid,))
        assert r["status"] == "Completed"
        assert r["checked_out_at"], "Completed must stamp checked_out_at"
        assert r["checked_in_at"], "completing must not erase the check-in stamp"


def test_no_show_is_recorded(app, auth_client, desk):
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "08:30")
        _post(auth_client, f"/appointments/{aid}/status", {"status": "No-Show"})
        r = _row("SELECT status, checked_out_at FROM appointments WHERE id=?", (aid,))
        assert r["status"] == "No-Show"
        assert r["checked_out_at"]


def test_cancellation_is_recorded(app, auth_client, desk):
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "09:30")
        _post(auth_client, f"/appointments/{aid}/status", {"status": "Cancelled"})
        r = _row("SELECT status, checked_out_at FROM appointments WHERE id=?", (aid,))
        assert r["status"] == "Cancelled"
        assert r["checked_out_at"]


def test_invalid_status_does_not_write(app, auth_client, desk):
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "10:00")
        _post(auth_client, f"/appointments/{aid}/status", {"status": "Vaporised"})
        assert _row("SELECT status FROM appointments WHERE id=?", (aid,))["status"] == "Scheduled"


# ═══ appointments.appt_edit ═══════════════════════════════════════════════════

def test_appt_edit_form_renders(app, auth_client, desk):
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "11:00")
    resp = auth_client.get(f"/appointments/{aid}/edit")
    assert resp.status_code == 200
    assert FUTURE.encode() in resp.data


def test_appt_edit_reschedules_in_the_database(app, auth_client, desk):
    """POST /edit must actually move the appointment, end time included."""
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "11:30")
        new_date = (date.today() + timedelta(days=41)).isoformat()

        _post(auth_client, f"/appointments/{aid}/edit", {
            "appt_date": new_date,
            "appt_start": "14:00",
            "duration_min": "45",
            "doctor_name": "Dr. Reschedule",
            "appointment_type": "Follow-up",
            "priority": "Urgent",
            "reason": "إعادة فحص",
            "notes": "moved by owner",
            "channel": "Phone",
        })

        r = _row("SELECT * FROM appointments WHERE id=?", (aid,))
        assert r["appt_date"] == new_date
        assert r["appt_start"] == "14:00"
        assert r["appt_end"] == "14:45", "end time must be recomputed from duration"
        assert r["duration_min"] == 45
        assert r["doctor_name"] == "Dr. Reschedule"
        assert r["appointment_type"] == "Follow-up"
        assert r["priority"] == "Urgent"
        assert r["reason"] == "إعادة فحص"
        assert r["channel"] == "Phone"


def test_appt_edit_refuses_completed_appointment(app, auth_client, desk):
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "12:00",
                       status="Completed")
        _post(auth_client, f"/appointments/{aid}/edit",
              {"appt_date": "2030-01-01", "appt_start": "07:00", "duration_min": "30"})
        r = _row("SELECT appt_date, appt_start FROM appointments WHERE id=?", (aid,))
        assert r["appt_date"] == FUTURE
        assert r["appt_start"] == "12:00"


def test_appt_edit_double_booking_guard_does_not_write(app, auth_client, desk):
    """A second appointment cannot be moved onto a slot the doctor already has."""
    with app.app_context():
        held = _mk_appt(desk["owner_id"], desk["pet_en"], FUTURE, "16:00",
                        doctor_name="Dr. Clash")
        mover = _mk_appt(desk["owner_id"], desk["pet_ar"], FUTURE, "17:00",
                         doctor_name="Dr. Clash")

        _post(auth_client, f"/appointments/{mover}/edit", {
            "appt_date": FUTURE, "appt_start": "16:00", "duration_min": "30",
            "doctor_name": "Dr. Clash",
        })
        assert _row("SELECT appt_start FROM appointments WHERE id=?",
                    (mover,))["appt_start"] == "17:00"
        assert _row("SELECT appt_start FROM appointments WHERE id=?",
                    (held,))["appt_start"] == "16:00"


# ═══ appointments.api_slots ═══════════════════════════════════════════════════

def _slot(payload, t):
    return next(s for s in payload["slots"] if s["time"] == t)


def test_api_slots_marks_booked_slot_unavailable(app, auth_client, desk):
    day = (date.today() + timedelta(days=60)).isoformat()
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], day, "13:30",
                       doctor_name="Dr. Slotcheck")

    resp = auth_client.get(f"/appointments/api/slots?date={day}&doctor=Dr. Slotcheck")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert _slot(payload, "13:30")["available"] is False
    assert _slot(payload, "14:00")["available"] is True

    # rescheduling that same appointment must not see itself as a conflict
    resp = auth_client.get(
        f"/appointments/api/slots?date={day}&doctor=Dr. Slotcheck&exclude_id={aid}")
    assert _slot(resp.get_json(), "13:30")["available"] is True


def test_api_slots_frees_cancelled_slot(app, auth_client, desk):
    day = (date.today() + timedelta(days=61)).isoformat()
    with app.app_context():
        aid = _mk_appt(desk["owner_id"], desk["pet_en"], day, "15:00",
                       doctor_name="Dr. Slotfree")
        assert _slot(auth_client.get(
            f"/appointments/api/slots?date={day}&doctor=Dr. Slotfree").get_json(),
            "15:00")["available"] is False

        _post(auth_client, f"/appointments/{aid}/status", {"status": "Cancelled"})

    payload = auth_client.get(
        f"/appointments/api/slots?date={day}&doctor=Dr. Slotfree").get_json()
    assert _slot(payload, "15:00")["available"] is True


# ═══ appointments.api_pets ════════════════════════════════════════════════════

def test_api_pets_returns_owners_pets_with_arabic_intact(auth_client, desk):
    resp = auth_client.get(f"/appointments/api/pets?owner_id={desk['owner_id']}")
    assert resp.status_code == 200
    pets = resp.get_json()
    by_id = {p["id"]: p for p in pets}
    assert desk["pet_en"] in by_id and desk["pet_ar"] in by_id
    assert by_id[desk["pet_ar"]]["pet_name"] == "لولو"
    # byte-identical through the JSON serializer, not just visually similar
    assert by_id[desk["pet_ar"]]["pet_name"].encode("utf-8") == "لولو".encode("utf-8")


def test_api_pets_without_owner_id_returns_empty(auth_client):
    assert auth_client.get("/appointments/api/pets").get_json() == []


def test_api_pets_rejects_garbage_owner_id(auth_client):
    assert auth_client.get("/appointments/api/pets?owner_id=abc").get_json() == []


# ═══ appointments.api_risk_score ══════════════════════════════════════════════

def test_risk_score_new_client(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Brand New Client", "01000000702")
    payload = auth_client.get(f"/appointments/api/risk-score/{oid}").get_json()
    assert payload["score"] == 15
    assert payload["level"] == "low"
    assert any("New client" in r for r in payload["reasons"])


def test_risk_score_rises_with_no_shows(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Serial No-Show", "01000000703")
        pid = _mk_pet(oid, "Ghost")
        for i in range(4):
            _mk_appt(oid, pid, FUTURE, f"0{i+1}:00",
                     status="No-Show" if i < 2 else "Completed")

    payload = auth_client.get(f"/appointments/api/risk-score/{oid}").get_json()
    assert payload["score"] >= 40, payload
    assert payload["level"] in ("medium", "high")
    assert any("No-show rate: 2/4" in r for r in payload["reasons"]), payload["reasons"]


def test_risk_score_early_slot_adds_points(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Early Bird", "01000000704")
    base  = auth_client.get(f"/appointments/api/risk-score/{oid}").get_json()
    early = auth_client.get(f"/appointments/api/risk-score/{oid}?time=07:30").get_json()
    assert early["score"] == base["score"] + 8
    assert any("Early morning" in r for r in early["reasons"])


# ═══ appointments.reception ═══════════════════════════════════════════════════

def test_reception_shows_todays_appointment(app, auth_client, desk):
    with app.app_context():
        _mk_appt(desk["owner_id"], desk["pet_en"], TODAY, "10:30")
    resp = auth_client.get("/appointments/reception")
    assert resp.status_code == 200
    assert "Biscuit" in resp.get_data(as_text=True)


def test_reception_requires_login(client):
    resp = client.get("/appointments/reception")
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")


# ═══ waiting room — public TV display ═════════════════════════════════════════

@pytest.fixture
def wr_token(app):
    """Set WAITING_ROOM_TOKEN for one test and put it back afterwards."""
    import blueprints.appointments.routes as ar
    saved = app.config.get("WAITING_ROOM_TOKEN")
    app.config["WAITING_ROOM_TOKEN"] = "tv-secret-8899"
    yield "tv-secret-8899"
    if saved is None:
        app.config.pop("WAITING_ROOM_TOKEN", None)
    else:
        app.config["WAITING_ROOM_TOKEN"] = saved


@pytest.fixture(scope="module")
def waiting(app, desk):
    """A pet waiting in the queue today, under an Arabic owner name."""
    with app.app_context():
        oid = _mk_owner("منى عبد الرحمن", "01000000705")
        pid = _mk_pet(oid, "مشمش", "Cat")
        aid = _mk_appt(oid, pid, TODAY, "09:15", status="Checked-in")
    return {"owner_id": oid, "pet_id": pid, "appt_id": aid,
            "full_name": "منى عبد الرحمن"}


def test_mask_owner_name_unit():
    assert mask_owner_name("Ahmed Zaki Elgohary") == "Ahmed E."
    assert mask_owner_name("منى عبد الرحمن") == "منى ا."
    assert mask_owner_name("Cher") == "Cher"
    assert mask_owner_name("") == ""
    assert mask_owner_name(None) == ""


def test_waiting_room_queue_is_not_empty(client, waiting):
    """The regression that mattered: the queue query used to name a column that
    does not exist (`a.appt_time` vs `appt_start`) and the crash was swallowed,
    so this display was permanently blank."""
    rows = client.get("/appointments/api/queue").get_json()
    assert any(r["id"] == waiting["appt_id"] for r in rows), \
        "today's checked-in appointment is missing from the waiting-room queue"


def test_waiting_room_api_masks_owner_names_for_the_public(client, waiting):
    rows = client.get("/appointments/api/queue").get_json()
    mine = next(r for r in rows if r["id"] == waiting["appt_id"])
    assert mine["owner_display"] == "منى ا."
    assert "owner_name" not in mine, "full owner name leaked to an anonymous caller"
    # and nobody else's full name leaked either
    for r in rows:
        assert "owner_name" not in r


def test_waiting_room_page_masks_owner_names(client, waiting):
    resp = client.get("/appointments/waiting-room")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert waiting["full_name"] not in body, "full owner name rendered on a public TV"
    assert "منى ا." in body
    assert "مشمش" in body, "the pet name is what the waiting client looks for"


def test_waiting_room_api_gives_staff_the_full_name(auth_client, waiting):
    rows = auth_client.get("/appointments/api/queue").get_json()
    mine = next(r for r in rows if r["id"] == waiting["appt_id"])
    assert mine["owner_name"] == waiting["full_name"]
    assert mine["owner_display"] == "منى ا."


def test_waiting_room_open_when_no_token_configured(app, client, waiting):
    """Documented fail-open: an already-deployed TV must not go blank."""
    assert not (app.config.get("WAITING_ROOM_TOKEN") or "").strip()
    assert client.get("/appointments/waiting-room").status_code == 200
    assert client.get("/appointments/api/queue").status_code == 200


def test_waiting_room_404s_without_token_when_configured(client, wr_token, waiting):
    assert client.get("/appointments/waiting-room").status_code == 404
    assert client.get("/appointments/api/queue").status_code == 404


def test_waiting_room_404s_on_wrong_token(client, wr_token, waiting):
    assert client.get("/appointments/waiting-room?t=nope").status_code == 404
    assert client.get("/appointments/api/queue?t=tv-secret-889").status_code == 404


def test_waiting_room_accepts_correct_token_and_pins_the_cookie(client, wr_token, waiting):
    resp = client.get(f"/appointments/waiting-room?t={wr_token}")
    assert resp.status_code == 200
    assert "wr_token" in resp.headers.get("Set-Cookie", "")
    # the cookie is now on the client, so the page's own polling stays authorized
    assert client.get("/appointments/api/queue").status_code == 200


def test_waiting_room_lets_staff_in_without_a_token(auth_client, wr_token, waiting):
    assert auth_client.get("/appointments/waiting-room").status_code == 200
    assert auth_client.get("/appointments/api/queue").status_code == 200


def test_waiting_room_excludes_finished_and_cancelled(app, client, desk):
    with app.app_context():
        done = _mk_appt(desk["owner_id"], desk["pet_en"], TODAY, "08:45",
                        status="Completed")
        gone = _mk_appt(desk["owner_id"], desk["pet_en"], TODAY, "08:50",
                        status="Cancelled")
    ids = {r["id"] for r in client.get("/appointments/api/queue").get_json()}
    assert done not in ids
    assert gone not in ids
