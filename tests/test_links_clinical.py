"""Clinical spine — every clinical record must lead back to its patient and visit.

The audit these tests come from: `visits` was read by 7 modules and `pets` by 15,
but the UI connected none of them. A pharmacist dispensing a drug could not see
the visit that prescribed it. These tests pin the links that fix that, and pin
the two ways they are allowed to be absent: when the related row genuinely does
not exist, and when clinical decision support has not been run.

SQLite only, no network.
"""
import re

import models.database as db
from conftest import get_csrf


# ── Fixtures built straight in the throwaway DB ───────────────────────────────

def _mk_owner_pet(conn, name="Spine Test"):
    cur = conn.execute(
        "INSERT INTO owners(full_name, phone) VALUES(?,?)", (name + " Owner", "0100000000"))
    owner_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO pets(owner_id, pet_name, species, breed, weight_kg) VALUES(?,?,?,?,?)",
        (owner_id, name, "Dog", "Baladi", 12.5))
    return owner_id, cur.lastrowid


def _mk_visit(conn, owner_id, pet_id):
    cur = conn.execute(
        "INSERT INTO visits(owner_id, pet_id, visit_date, doctor_name, chief_complaint, status) "
        "VALUES(?,?,?,?,?,?)",
        (owner_id, pet_id, "2026-07-01", "Dr. Sara", "Lameness", "Completed"))
    return cur.lastrowid


def _mk_prescription(conn, visit_id, pet_id, owner_id, drug="Meloxicam"):
    cur = conn.execute(
        "INSERT INTO prescriptions(visit_id, pet_id, owner_id, prescribed_by, status) "
        "VALUES(?,?,?,?,?)", (visit_id, pet_id, owner_id, "Dr. Sara", "Active"))
    rx_id = cur.lastrowid
    conn.execute(
        "INSERT INTO prescription_items(prescription_id, medication_name, quantity, instructions) "
        "VALUES(?,?,?,?)", (rx_id, drug, 10, "1 tab SID"))
    return rx_id


def _body(html):
    """Page content only — the sidebar links to /visits/ on every page."""
    i = html.find("v3-content")
    return html[i:] if i >= 0 else html


# ── 1. Prescription → the visit that wrote it, the pet, and the owner ─────────

def test_prescription_links_to_its_visit_pet_and_owner(app, auth_client):
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id = _mk_owner_pet(conn, "Linked")
            visit_id = _mk_visit(conn, owner_id, pet_id)
            rx_id = _mk_prescription(conn, visit_id, pet_id, owner_id)
        conn.close()

    html = _body(auth_client.get(f"/pharmacy/prescription/{rx_id}").get_data(as_text=True))

    assert f'href="/visits/{visit_id}"' in html, "prescription must link to the visit that wrote it"
    assert f'href="/crm/pets/{pet_id}"' in html, "prescription must link to the animal receiving it"
    assert f'href="/crm/owners/{owner_id}"' in html, "prescription must link to the owner"

    # Every link on the page has to actually resolve.
    for href in set(re.findall(r'href="(/[^"/][^"]*)"', html)):
        if href.startswith("/static"):
            continue
        assert auth_client.get(href).status_code < 400, f"dead link {href}"


# ── 2. The missing case: a prescription whose visit is not there ──────────────

def test_prescription_without_a_visit_renders_cleanly(app, auth_client):
    """visit_id is NOT NULL, so the real-world gap is a visit row that is gone.

    The page must still open — a pharmacist has to see what is being dispensed —
    and must say the visit is missing instead of offering a dead link.
    """
    with app.app_context():
        conn = db.get_db()
        # The FK is what normally stops this row existing; turn it off to
        # reproduce the state a deleted visit leaves behind.
        conn.execute("PRAGMA foreign_keys=OFF")
        with conn:
            owner_id, pet_id = _mk_owner_pet(conn, "Orphan")
            missing_visit_id = (conn.execute(
                "SELECT COALESCE(MAX(id),0)+1000 FROM visits").fetchone()[0])
            rx_id = _mk_prescription(conn, missing_visit_id, pet_id, owner_id)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()

    resp = auth_client.get(f"/pharmacy/prescription/{rx_id}")
    assert resp.status_code == 200, "a prescription with no visit must still open"
    html = _body(resp.get_data(as_text=True))

    assert "No visit record is linked" in html
    assert f'href="/visits/{missing_visit_id}"' not in html
    assert 'href="/visits/' not in html, "no visit link may be rendered when there is no visit"
    # The pet is still there, so that link must survive.
    assert f'href="/crm/pets/{pet_id}"' in html


# ── 3. Lab request → its visit and its pet ───────────────────────────────────

def test_lab_request_links_to_its_visit_and_pet(app, auth_client):
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id = _mk_owner_pet(conn, "Labbed")
            visit_id = _mk_visit(conn, owner_id, pet_id)
            cur = conn.execute(
                "INSERT INTO lab_requests(visit_id, pet_id, test_name, priority, status) "
                "VALUES(?,?,?,?,?)", (visit_id, pet_id, "CBC", "Routine", "Pending"))
            lab_id = cur.lastrowid
        conn.close()

    html = _body(auth_client.get(f"/clinical/lab/{lab_id}").get_data(as_text=True))
    assert f'href="/crm/pets/{pet_id}"' in html
    assert f'href="/visits/{visit_id}"' in html


# ── 4. Vaccination → the pet, and that pet's other vaccinations ──────────────

def test_vaccination_links_to_pet_and_its_other_vaccinations(app, auth_client):
    with app.app_context():
        conn = db.get_db()
        with conn:
            _owner_id, pet_id = _mk_owner_pet(conn, "Vaxxed")
            conn.execute(
                "INSERT INTO vaccinations(pet_id, vaccine_name, administered_at, next_due_at) "
                "VALUES(?,?,?,?)", (pet_id, "Rabies", "2026-01-10", "2027-01-10"))
        conn.close()

    html = _body(auth_client.get("/clinical/vaccinations").get_data(as_text=True))
    assert f'href="/crm/pets/{pet_id}"' in html
    assert f"/clinical/vaccinations?pet_id={pet_id}" in html

    filtered = auth_client.get(f"/clinical/vaccinations?pet_id={pet_id}")
    assert filtered.status_code == 200
    assert "Showing vaccinations for" in filtered.get_data(as_text=True)


# ── 5. Clinical decision support: reachable, opt-in, and never a clearance ────

def test_cds_entry_point_does_not_claim_the_prescription_was_checked(app, auth_client):
    """The CDS drug data is a DRAFT that no licensed vet has reviewed.

    The entry point may offer to open it. It must not run on load, and it must
    not let a reader conclude the prescription has been screened or approved.
    """
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id = _mk_owner_pet(conn, "Screened")
            visit_id = _mk_visit(conn, owner_id, pet_id)
            rx_id = _mk_prescription(conn, visit_id, pet_id, owner_id, drug="Meloxicam")
        conn.close()

    html = _body(auth_client.get(f"/pharmacy/prescription/{rx_id}").get_data(as_text=True))

    # Reachable at all — /cds/ had no inbound link from anywhere in the product.
    assert 'action="/cds/"' in html

    # Fail closed: the page states nothing has been checked.
    assert "Not screened" in html
    assert "has not been checked" in html

    # It must never assert a clean result or an approval.
    lowered = html.lower()
    for claim in ("no interaction", "safe to prescribe", "checked and cleared",
                  "screening passed", "approved"):
        assert claim not in lowered, f"CDS entry point must not imply {claim!r}"

    # And it must say plainly that opening the reference is not a check.
    assert "does not check, clear or approve this prescription" in html
    assert "not been reviewed by a licensed veterinarian" in html


def test_cds_entry_point_is_opt_in_and_carries_the_patient_context(app, auth_client):
    """It screens on species/breed/weight, so those are passed — but only when
    a human presses the button. Nothing fires on page load."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            owner_id, pet_id = _mk_owner_pet(conn, "Context")
            visit_id = _mk_visit(conn, owner_id, pet_id)
            rx_id = _mk_prescription(conn, visit_id, pet_id, owner_id, drug="Meloxicam")
        conn.close()

    html = _body(auth_client.get(f"/pharmacy/prescription/{rx_id}").get_data(as_text=True))

    # No auto-run: the only path to CDS is a submit button in a POST form.
    assert "/cds/api/screen" not in html, "CDS must not be invoked from the page automatically"
    assert re.search(r'<form[^>]+action="/cds/"[^>]*method="post"', html, re.I) or \
           re.search(r'<form[^>]+method="post"[^>]*action="/cds/"', html, re.I)
    assert '<button type="submit"' in html

    # The parameters cds.index actually reads.
    drugs = re.search(r'<textarea name="drugs" hidden>(.*?)</textarea>', html, re.S).group(1)
    assert "Meloxicam" in drugs
    assert 'name="species" value="Dog"' in html
    assert 'name="breed" value="Baladi"' in html
    assert 'name="weight_kg" value="12.5"' in html

    # Pressing it lands on a working CDS page.
    assert auth_client.post("/cds/", data={
        "_csrf_token": get_csrf(auth_client),
        "drugs": drugs, "species": "Dog", "breed": "Baladi", "weight_kg": "12.5",
    }).status_code == 200
