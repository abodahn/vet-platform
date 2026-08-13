# -*- coding: utf-8 -*-
"""Who a visit is credited to.

visits.doctor_name held the vet actually typed; visits.doctor_id was set to
whoever was logged in, unconditionally. A receptionist saving an exam for
Dr Sara filed the visit under the receptionist.

Nothing reads doctor_id today, which is exactly why this was worth fixing now:
the cost is zero until the first per-vet revenue or commission report exists,
and then it is retroactive across every visit ever recorded, with no way to
reconstruct who actually saw the animal.

NULL rather than a guess when the name matches nobody: the vet field is free
text with a datalist, so a locum typed by hand genuinely has no user id, and
storing the receptionist's would be a lie a report would believe.
"""
from conftest import get_csrf


def _mk_vet(app, full_name, username):
    import models.database as db
    with app.app_context():
        return db.create_user({"username": username, "password": "Str0ng!Pass9",
                               "full_name": full_name, "role": "doctor"})


def _owner_and_pet(app, phone):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                           ("عميل الإسناد", phone)).lastrowid
        pid = conn.execute("INSERT INTO pets(owner_id, pet_name, species, is_active)"
                           " VALUES(?,?,?,1)", (oid, "ريكس", "Dog")).lastrowid
        conn.commit()
        conn.close()
    return oid, pid


def _last_visit(app, pet_id):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT doctor_id, doctor_name, created_by FROM visits"
            " WHERE pet_id=? ORDER BY id DESC LIMIT 1", (pet_id,)).fetchone()
        conn.close()
    return dict(row) if row else None


def test_the_visit_is_credited_to_the_vet_named_not_the_person_typing(auth_client, app):
    import models.database as db
    vet_id = _mk_vet(app, "Dr. Sara Elgohary", "dr_sara_attr")
    oid, pid = _owner_and_pet(app, "01000000961")

    auth_client.post("/visits/exam/%d" % pid, data={
        "owner_id": oid, "pet_id": pid,
        "doctor_name": "Dr. Sara Elgohary",
        "symptom": "يعرج في الرجل الخلفية",
        "visit_date": "2026-08-13",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)

    v = _last_visit(app, pid)
    assert v is not None, "the visit was not saved"
    assert v["doctor_name"] == "Dr. Sara Elgohary"
    assert v["doctor_id"] == vet_id, \
        "the visit is credited to user %s, not to Dr Sara (%s)" % (v["doctor_id"], vet_id)


def test_an_unknown_name_records_nobody_rather_than_the_wrong_person(auth_client, app):
    oid, pid = _owner_and_pet(app, "01000000962")

    auth_client.post("/visits/exam/%d" % pid, data={
        "owner_id": oid, "pet_id": pid,
        "doctor_name": "Dr. Locum Nobody Knows",
        "symptom": "كشف عام",
        "visit_date": "2026-08-13",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)

    v = _last_visit(app, pid)
    assert v["doctor_name"] == "Dr. Locum Nobody Knows"
    assert v["doctor_id"] is None, \
        "an unrecognised vet was credited to user %s" % v["doctor_id"]


def test_a_blank_vet_falls_back_to_whoever_saved_it(auth_client, app):
    """Somebody saw the animal. An empty column would lose that too."""
    oid, pid = _owner_and_pet(app, "01000000963")
    auth_client.post("/visits/exam/%d" % pid, data={
        "owner_id": oid, "pet_id": pid, "doctor_name": "",
        "symptom": "متابعة", "visit_date": "2026-08-13",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)

    v = _last_visit(app, pid)
    assert v["doctor_id"] is not None, "nobody at all was recorded"


def test_the_same_rule_applies_to_the_full_visit_form(auth_client, app):
    """Two INSERT INTO visits sites; both had the bug."""
    vet_id = _mk_vet(app, "Dr. Mostafa Ali", "dr_mostafa_attr")
    oid, pid = _owner_and_pet(app, "01000000964")

    auth_client.post("/visits/new", data={
        "owner_id": oid, "pet_id": pid,
        "doctor_name": "Dr. Mostafa Ali",
        "visit_type": "Consultation",
        "chief_complaint": "سعال",
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=True)

    v = _last_visit(app, pid)
    assert v["doctor_id"] == vet_id, \
        "the full visit form still credits the logged-in user"
