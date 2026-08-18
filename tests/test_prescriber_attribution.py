# -*- coding: utf-8 -*-
"""A prescription must name the veterinarian who prescribed it.

Found by working a full shift as a real `nurse` user. add_prescription carried
only @login_required, and `visits` is on the nurse grant, so a nurse could write
and sign a prescription under her own name -- it saved, and reached the pharmacy
queue attributed to someone who may not lawfully prescribe. That is the CLINIC's
regulatory exposure, which is precisely why the software should not permit it.

The rule chosen: a nurse may still TYPE a prescription -- a vet dictating while
someone else enters it is how a busy clinic runs, and how paper works -- but the
prescriber recorded must be an actual active veterinarian.
"""
import pytest

import models.database as db
from blueprints.visits.routes import PRESCRIBER_ROLES
from tests.conftest import get_csrf


def _mkuser(app, username, full_name, role):
    # INSERT OR IGNORE: the `app` fixture is session-scoped, so these users
    # outlive the test that created them and the second test would collide on
    # users.username. (IGNORE -> ON CONFLICT DO NOTHING is a faithful
    # translation on PostgreSQL; OR REPLACE is not and the translator refuses it.)
    # HR no longer ships its own hasher — it wrote SHA-256 with a salt
    # hardcoded in the repo. bcrypt is the app's one scheme now.
    from models.database import _hash_password as _hash
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(username, full_name, role, "
                "password_hash, is_active) VALUES(?,?,?,?,1)",
                (username, full_name, role, _hash("Pass@2026")))
        conn.close()


@pytest.fixture()
def scene(app):
    """A vet, a nurse, and an open visit to prescribe against."""
    _mkuser(app, "rx.vet", "Dr. Prescriber", "doctor")
    _mkuser(app, "rx.nurse", "Nurse Typist", "nurse")
    with app.app_context():
        conn = db.get_db()
        with conn:
            oid = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                               ("Rx Owner", "01077000111")).lastrowid
            pid = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, is_active) VALUES(?,?,?,1)",
                (oid, "RxPet", "Dog")).lastrowid
            vid = conn.execute(
                "INSERT INTO visits(owner_id, pet_id, visit_date, visit_type, status) "
                "VALUES(?,?,datetime('now'),'Consultation','Open')", (oid, pid)).lastrowid
        conn.close()
    return {"owner": oid, "pet": pid, "visit": vid}


def _login(app, username):
    c = app.test_client()
    c.post("/auth/login", data={"username": username, "password": "Pass@2026"})
    c.get("/")
    return c


def _rx_count(app):
    with app.app_context():
        conn = db.get_db()
        try:
            return conn.execute("SELECT COUNT(*) FROM prescriptions").fetchone()[0]
        finally:
            conn.close()


def _last_prescriber(app):
    with app.app_context():
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT prescribed_by, notes FROM prescriptions ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return (row["prescribed_by"], row["notes"] or "") if row else (None, "")
        finally:
            conn.close()


LINE = {"medication_name_1": "Tramadol", "dosage_1": "10 mg",
        "frequency_1": "Twice daily", "duration_1": "5 days", "route_1": "PO"}


# ── the hole that was open ───────────────────────────────────────────────────

def test_a_nurse_cannot_sign_a_prescription_in_her_own_name(app, scene):
    c = _login(app, "rx.nurse")
    before = _rx_count(app)
    c.post(f"/visits/{scene['visit']}/prescription",
           data={"_csrf_token": get_csrf(c), **LINE}, follow_redirects=True)
    assert _rx_count(app) == before, \
        "a nurse wrote and signed a prescription with no veterinarian named"


def test_a_nurse_may_enter_one_on_a_vets_behalf(app, scene):
    """Blocking her entirely would break the clinic that actually exists: a vet
    dictates, somebody else types."""
    c = _login(app, "rx.nurse")
    before = _rx_count(app)
    c.post(f"/visits/{scene['visit']}/prescription",
           data={"_csrf_token": get_csrf(c), "prescribed_by": "Dr. Prescriber", **LINE},
           follow_redirects=True)
    assert _rx_count(app) == before + 1, "a valid on-behalf-of prescription was refused"
    who, notes = _last_prescriber(app)
    assert who == "Dr. Prescriber", f"recorded against {who!r} instead of the vet"
    assert "Nurse Typist" in notes, \
        "who actually typed it was not recorded, so a later dispute has one name and needs two"


def test_a_made_up_vet_name_is_refused(app, scene):
    """A free-text box would put the clinic straight back where it started."""
    c = _login(app, "rx.nurse")
    before = _rx_count(app)
    c.post(f"/visits/{scene['visit']}/prescription",
           data={"_csrf_token": get_csrf(c), "prescribed_by": "Dr. Nobody", **LINE},
           follow_redirects=True)
    assert _rx_count(app) == before, "a prescription was recorded against an invented vet"


def test_a_nurse_cannot_name_another_nurse(app, scene):
    c = _login(app, "rx.nurse")
    before = _rx_count(app)
    c.post(f"/visits/{scene['visit']}/prescription",
           data={"_csrf_token": get_csrf(c), "prescribed_by": "Nurse Typist", **LINE},
           follow_redirects=True)
    assert _rx_count(app) == before, "a nurse was accepted as the prescriber"


# ── the vet's own path must not get harder ───────────────────────────────────

def test_a_vet_prescribes_with_no_extra_step(app, scene):
    c = _login(app, "rx.vet")
    before = _rx_count(app)
    c.post(f"/visits/{scene['visit']}/prescription",
           data={"_csrf_token": get_csrf(c), **LINE}, follow_redirects=True)
    assert _rx_count(app) == before + 1, "a vet was blocked from their own prescription"
    who, notes = _last_prescriber(app)
    assert who == "Dr. Prescriber"
    assert "on behalf of" not in notes, "a vet's own prescription was annotated as a transcription"


def test_the_prescription_still_carries_its_patient(app, scene):
    """Without pet and owner it is invisible to the pharmacist who must fill it."""
    c = _login(app, "rx.vet")
    c.post(f"/visits/{scene['visit']}/prescription",
           data={"_csrf_token": get_csrf(c), **LINE}, follow_redirects=True)
    with app.app_context():
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT pet_id, owner_id FROM prescriptions ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
    assert row["pet_id"] == scene["pet"] and row["owner_id"] == scene["owner"]


# ── the form a nurse actually sees ───────────────────────────────────────────

def test_the_nurse_is_offered_the_vets_to_choose_from(app, scene):
    """A form that refuses on submit, with no way to comply, is a dead end."""
    c = _login(app, "rx.nurse")
    html = c.get(f"/visits/{scene['visit']}").get_data(as_text=True)
    assert 'name="prescribed_by"' in html, "no prescriber field was offered to the nurse"
    assert "Dr. Prescriber" in html, "the vet was not listed as selectable"


def test_the_vet_is_not_asked_who_prescribed_it(app, scene):
    c = _login(app, "rx.vet")
    html = c.get(f"/visits/{scene['visit']}").get_data(as_text=True)
    assert 'name="prescribed_by"' not in html, \
        "a vet was asked to name a prescriber for their own prescription"


def test_the_prescriber_roles_are_clinical_only(app):
    """A receptionist or an accountant must never appear in that dropdown."""
    for role in ("reception", "finance", "nurse", "groomer", "hr", "inventory_mgr"):
        assert role not in PRESCRIBER_ROLES, f"{role} is listed as able to prescribe"
