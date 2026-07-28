# -*- coding: utf-8 -*-
"""Inpatient ward — admission, rounds, medication log, discharge.

Every one of the six write routes in this module returned 403 and wrote
nothing, for the module's whole life, because the form field was named
`csrf_token` instead of `_csrf_token`. Nothing about a GET showed it. So
these tests never assert on the response alone: each POST is followed by a
read of the row it was supposed to write.

An inpatient stay is the record of what was done to an animal while it was
in the clinic's care. A round that silently does not save is a temperature
nobody has.

SQLite, no network.
"""
import models.database as db
from conftest import get_csrf


# ── helpers ───────────────────────────────────────────────────────────────────

def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = get_csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _user_id(client):
    with client.session_transaction() as s:
        return s["user"]["id"]


def _mk_patient(conn, name):
    cur = conn.execute(
        "INSERT INTO owners(full_name, phone) VALUES(?,?)",
        (name + " Owner", "01099900011"))
    owner_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO pets(owner_id, pet_name, species, breed, weight_kg) "
        "VALUES(?,?,?,?,?)", (owner_id, name, "Dog", "Baladi", 18.0))
    pet_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO visits(owner_id, pet_id, visit_date, doctor_name, "
        "chief_complaint, status) VALUES(?,?,?,?,?,?)",
        (owner_id, pet_id, "2026-07-20", "Dr. Sara", "Collapse", "Open"))
    return owner_id, pet_id, cur.lastrowid


def _mk_stay(app, auth_client, name, **over):
    """A stay written straight into the DB — the fixture for read/update tests."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id, visit_id = _mk_patient(conn, name)
            cur = conn.execute(
                "INSERT INTO inpatient_stays(pet_id, owner_id, visit_id, ward, "
                "cage_number, admitted_by, reason, status, daily_rate) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (pet_id, owner_id, visit_id, over.get("ward", "ICU"), "C-7",
                 _user_id(auth_client), over.get("reason", "Post-op monitoring"),
                 over.get("status", "Admitted"), 250.0))
            stay_id = cur.lastrowid
        conn.close()
    return {"owner_id": owner_id, "pet_id": pet_id,
            "visit_id": visit_id, "stay_id": stay_id}


def _row(app, sql, params):
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(sql, params).fetchone()
        conn.close()
    return dict(row) if row else None


# ── admit ─────────────────────────────────────────────────────────────────────

def test_admit_form_loads(app, auth_client):
    """The GET the six broken POSTs all looked fine behind."""
    fx = _mk_stay(app, auth_client, "AdmitForm")
    r = auth_client.get("/inpatient/admit")
    assert r.status_code == 200
    assert "AdmitForm Owner" in r.get_data(as_text=True), \
        "admit form does not offer the clinic's owners to admit against"
    assert fx  # fixture used only for the owner list


def test_admit_writes_the_stay(app, auth_client):
    """POST /inpatient/admit must produce a row holding what was sent."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id, visit_id = _mk_patient(conn, "Admitted")
        conn.close()

    r = _post(auth_client, "/inpatient/admit", {
        "pet_id": pet_id, "owner_id": owner_id, "visit_id": visit_id,
        "ward": "ICU", "cage_number": "ICU-3",
        "reason": "Parvovirus — IV fluids",
        "diagnosis": "Canine parvovirus",
        "treatment_plan": "IV LRS 60ml/h, antiemetics",
        "expected_discharge": "2026-08-02",
        "daily_rate": "450.5",
    })
    assert r.status_code == 200, "admit POST did not render"

    stay = _row(app, "SELECT * FROM inpatient_stays WHERE pet_id=?", (pet_id,))
    assert stay, "admission POST returned OK but wrote no stay"
    assert stay["ward"] == "ICU"
    assert stay["cage_number"] == "ICU-3"
    assert stay["reason"] == "Parvovirus — IV fluids"
    assert stay["diagnosis"] == "Canine parvovirus"
    assert stay["treatment_plan"] == "IV LRS 60ml/h, antiemetics"
    assert str(stay["expected_discharge"])[:10] == "2026-08-02"
    assert float(stay["daily_rate"]) == 450.5, \
        f"daily rate stored as {stay['daily_rate']} — the stay bills off this"
    assert stay["status"] == "Admitted"
    assert stay["visit_id"] == visit_id, "stay lost the visit that admitted it"
    assert stay["admitted_by"] == _user_id(auth_client)


def test_admit_without_csrf_writes_nothing(app, auth_client):
    """The exact bug: a POST the server rejects must not look like a success."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id, _ = _mk_patient(conn, "NoToken")
        conn.close()

    r = auth_client.post("/inpatient/admit", data={
        "pet_id": pet_id, "owner_id": owner_id,
        "reason": "Should never be stored",
    })
    assert r.status_code == 403, "a POST with no CSRF token was accepted"
    assert _row(app, "SELECT * FROM inpatient_stays WHERE pet_id=?", (pet_id,)) is None


# ── stay detail ───────────────────────────────────────────────────────────────

def test_stay_detail_shows_the_patient_and_its_records(app, auth_client):
    fx = _mk_stay(app, auth_client, "Detail")
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute(
                "INSERT INTO inpatient_rounds(stay_id, recorded_by, temp_c, "
                "observations) VALUES(?,?,?,?)",
                (fx["stay_id"], _user_id(auth_client), 39.4, "Bright, eating"))
            conn.execute(
                "INSERT INTO inpatient_meds(stay_id, given_by, medication, dose) "
                "VALUES(?,?,?,?)",
                (fx["stay_id"], _user_id(auth_client), "Cerenia", "1mg/kg"))
        conn.close()

    html = auth_client.get(f"/inpatient/{fx['stay_id']}").get_data(as_text=True)
    assert "Detail" in html, "stay page does not show its own patient"
    assert "Bright, eating" in html, "stay page does not show its rounds"
    assert "Cerenia" in html, "stay page does not show the medication log"


def test_stay_detail_of_a_missing_stay_does_not_500(app, auth_client):
    r = auth_client.get("/inpatient/999999", follow_redirects=True)
    assert r.status_code == 200


# ── status ────────────────────────────────────────────────────────────────────

def test_update_status_writes(app, auth_client):
    fx = _mk_stay(app, auth_client, "Status")
    r = _post(auth_client, f"/inpatient/{fx['stay_id']}/status",
              {"status": "Critical"})
    assert r.status_code == 200

    stay = _row(app, "SELECT * FROM inpatient_stays WHERE id=?", (fx["stay_id"],))
    assert stay["status"] == "Critical", \
        f"status POST returned OK but the row still reads {stay['status']!r}"


def test_update_status_rejects_a_status_that_is_not_a_status(app, auth_client):
    fx = _mk_stay(app, auth_client, "BadStatus")
    _post(auth_client, f"/inpatient/{fx['stay_id']}/status", {"status": "Dead?"})
    stay = _row(app, "SELECT * FROM inpatient_stays WHERE id=?", (fx["stay_id"],))
    assert stay["status"] == "Admitted", \
        "an unknown status was written into the ward board"


# ── rounds ────────────────────────────────────────────────────────────────────

def test_add_round_writes_every_vital(app, auth_client):
    """A round is the clinical observation record. Losing a field loses a vital."""
    fx = _mk_stay(app, auth_client, "Round")
    r = _post(auth_client, f"/inpatient/{fx['stay_id']}/round", {
        "round_time": "2026-07-21T08:30",
        "temp_c": "39.8", "heart_rate": "132", "resp_rate": "36",
        "weight_kg": "17.4", "pain_score": "3",
        "food_intake": "Refused breakfast",
        "fluid_input": "240", "fluid_output": "180",
        "observations": "Mucous membranes tacky",
        "treatment_given": "LRS bolus 10ml/kg",
    })
    assert r.status_code == 200

    rnd = _row(app, "SELECT * FROM inpatient_rounds WHERE stay_id=?",
               (fx["stay_id"],))
    assert rnd, "round POST returned OK but recorded no round"
    assert float(rnd["temp_c"]) == 39.8
    assert int(rnd["heart_rate"]) == 132
    assert int(rnd["resp_rate"]) == 36
    assert float(rnd["weight_kg"]) == 17.4
    assert int(rnd["pain_score"]) == 3
    assert rnd["food_intake"] == "Refused breakfast"
    assert float(rnd["fluid_input"]) == 240
    assert float(rnd["fluid_output"]) == 180
    assert rnd["observations"] == "Mucous membranes tacky"
    assert rnd["treatment_given"] == "LRS bolus 10ml/kg"
    assert rnd["recorded_by"] == _user_id(auth_client)
    assert str(rnd["round_time"]).startswith("2026-07-21"), \
        f"round filed under the wrong time: {rnd['round_time']}"


def test_rounds_accumulate_rather_than_overwrite(app, auth_client):
    fx = _mk_stay(app, auth_client, "Rounds2")
    _post(auth_client, f"/inpatient/{fx['stay_id']}/round",
          {"temp_c": "39.0", "observations": "08:00 round"})
    _post(auth_client, f"/inpatient/{fx['stay_id']}/round",
          {"temp_c": "38.4", "observations": "14:00 round"})
    with app.app_context():
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM inpatient_rounds WHERE stay_id=?",
                         (fx["stay_id"],)).fetchone()[0]
        conn.close()
    assert n == 2, f"two rounds were recorded, {n} survived"


def test_add_round_without_csrf_writes_nothing(app, auth_client):
    fx = _mk_stay(app, auth_client, "RoundNoToken")
    r = auth_client.post(f"/inpatient/{fx['stay_id']}/round",
                         data={"temp_c": "41.0", "observations": "lost"})
    assert r.status_code == 403
    assert _row(app, "SELECT * FROM inpatient_rounds WHERE stay_id=?",
                (fx["stay_id"],)) is None


# ── medication administration record ──────────────────────────────────────────

def test_add_med_writes_the_administration(app, auth_client):
    """The MAR is the legal record that a drug went into an animal."""
    fx = _mk_stay(app, auth_client, "Med")
    r = _post(auth_client, f"/inpatient/{fx['stay_id']}/med", {
        "medication": "Metronidazole", "dose": "15 mg/kg",
        "route": "IV", "given_at": "2026-07-21T09:15",
        "notes": "Slow push over 30 min",
    })
    assert r.status_code == 200

    med = _row(app, "SELECT * FROM inpatient_meds WHERE stay_id=?",
               (fx["stay_id"],))
    assert med, "medication POST returned OK but logged no administration"
    assert med["medication"] == "Metronidazole"
    assert med["dose"] == "15 mg/kg"
    assert med["route"] == "IV", \
        f"route stored as {med['route']!r} — IV and PO are not interchangeable"
    assert med["notes"] == "Slow push over 30 min"
    assert med["given_by"] == _user_id(auth_client)
    assert str(med["given_at"]).startswith("2026-07-21")


def test_add_med_without_a_drug_name_records_nothing(app, auth_client):
    """`f["medication"]` is a hard key — a blank submission must not half-write."""
    fx = _mk_stay(app, auth_client, "MedBlank")
    _post(auth_client, f"/inpatient/{fx['stay_id']}/med", {"dose": "1 tab"})
    assert _row(app, "SELECT * FROM inpatient_meds WHERE stay_id=?",
                (fx["stay_id"],)) is None, \
        "a medication row was written with no medication"


# ── discharge ─────────────────────────────────────────────────────────────────

def test_discharge_closes_the_stay(app, auth_client):
    fx = _mk_stay(app, auth_client, "Discharge")
    r = _post(auth_client, f"/inpatient/{fx['stay_id']}/discharge",
              {"discharge_notes": "Eating, hydrated. Home on PO meds x5d."})
    assert r.status_code == 200

    stay = _row(app, "SELECT * FROM inpatient_stays WHERE id=?", (fx["stay_id"],))
    assert stay["status"] == "Discharged", \
        f"discharge POST returned OK, stay still reads {stay['status']!r}"
    assert stay["discharged_at"], "discharged with no discharge time"
    assert stay["discharge_notes"] == "Eating, hydrated. Home on PO meds x5d."

    # And it must leave the active ward board.
    html = auth_client.get("/inpatient/").get_data(as_text=True)
    assert f'/inpatient/{fx["stay_id"]}"' not in html, \
        "a discharged patient is still occupying the ward board"


def test_discharging_twice_does_not_lose_the_first_discharge_notes(app, auth_client):
    fx = _mk_stay(app, auth_client, "Discharge2")
    _post(auth_client, f"/inpatient/{fx['stay_id']}/discharge",
          {"discharge_notes": "Original clinical summary"})
    first = _row(app, "SELECT * FROM inpatient_stays WHERE id=?", (fx["stay_id"],))
    _post(auth_client, f"/inpatient/{fx['stay_id']}/discharge",
          {"discharge_notes": ""})
    second = _row(app, "SELECT * FROM inpatient_stays WHERE id=?", (fx["stay_id"],))
    assert second["discharge_notes"] == "Original clinical summary", \
        "a repeat discharge blanked the discharge summary"
    assert second["discharged_at"] == first["discharged_at"], \
        "a repeat discharge moved the discharge time"


def test_discharge_without_csrf_writes_nothing(app, auth_client):
    fx = _mk_stay(app, auth_client, "DischargeNoToken")
    r = auth_client.post(f"/inpatient/{fx['stay_id']}/discharge",
                         data={"discharge_notes": "lost"})
    assert r.status_code == 403
    stay = _row(app, "SELECT * FROM inpatient_stays WHERE id=?", (fx["stay_id"],))
    assert stay["status"] == "Admitted", "a rejected POST discharged the patient"


# ── owner → pets API (drives the admit form's pet dropdown) ────────────────────

def test_api_owner_pets_returns_that_owners_pets(app, auth_client):
    fx = _mk_stay(app, auth_client, "ApiPets")
    r = auth_client.get(f"/inpatient/api/owner/{fx['owner_id']}/pets")
    assert r.status_code == 200
    pets = r.get_json()
    assert isinstance(pets, list) and pets, "owner with a pet returned an empty list"
    assert [p for p in pets if p["id"] == fx["pet_id"]], \
        "the owner's own pet is missing from their pet list"
    assert pets[0]["pet_name"] == "ApiPets"


def test_api_owner_pets_of_an_unknown_owner_is_empty_not_everyone(app, auth_client):
    r = auth_client.get("/inpatient/api/owner/999999/pets")
    assert r.status_code == 200
    assert r.get_json() == [], "an unknown owner was shown somebody else's animals"
