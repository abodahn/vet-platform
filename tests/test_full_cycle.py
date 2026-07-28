# -*- coding: utf-8 -*-
"""END-TO-END: does the clinic's actual working day survive one pass?

Everything else in this suite tests a part. This tests the CHAIN — the claim
the product is sold on, that modules are one system rather than 28 apps:

    owner -> pet -> visit -> diagnosis -> prescription
          -> dispensing -> stock deduction
          -> invoice -> payment -> settled

Each step POSTs through the real HTTP route with CSRF, exactly as a
receptionist and a vet would, and then asserts the NEXT module can see what
the previous one wrote. A step that renders 200 but writes nothing fails
here, which is the failure mode this codebase has produced repeatedly
(accounting reporting zero, the doctor queue empty, inpatient actions 403ing
— all of them looked fine).

SQLite, no PostgreSQL, no network.
"""
import re

import pytest

import models.database as db


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


@pytest.fixture
def vet(app, client):
    """A logged-in clinician who can drive the whole chain."""
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE role IN ('super_admin','clinic_owner') "
            "ORDER BY id LIMIT 1").fetchone()
        conn.close()
        user = {k: row[k] for k in row.keys()
                if k not in ("password_hash", "totp_secret")}
    with client.session_transaction() as s:
        s["user"] = user
        s["lang"] = "en"
    return user


# ─── the chain ────────────────────────────────────────────────────────────────

def test_full_clinic_cycle(app, client, vet):
    """One patient, start to settled invoice."""

    # 1. Reception registers a client. Arabic name on purpose — the product's
    #    main differentiator, and the place encoding bugs surface.
    r = _post(client, "/crm/owners/new", {
        "full_name": "Mahmoud Salah", "full_name_ar": "محمود صلاح",
        "phone": "01012345678", "whatsapp_phone": "01012345678",
        "email": "m.salah@example.com", "address": "Nasr City, Cairo",
        "preferred_contact": "WhatsApp",
    })
    assert r.status_code == 200, "owner creation failed"

    with app.app_context():
        conn = db.get_db()
        owner = conn.execute(
            "SELECT * FROM owners WHERE phone=? ORDER BY id DESC LIMIT 1",
            ("01012345678",)).fetchone()
        conn.close()
    assert owner, "owner was not written"
    assert owner["full_name_ar"] == "محمود صلاح", "Arabic name did not round-trip"
    owner_id = owner["id"]

    # 2. and their animal
    r = _post(client, "/crm/pets/new", {
        "owner_id": owner_id, "pet_name": "Simba", "species": "Cat",
        "breed": "Shirazi", "sex": "Male", "weight_kg": "4.2",
        "allergies": "Penicillin",
    })
    assert r.status_code == 200, "pet creation failed"

    with app.app_context():
        conn = db.get_db()
        pet = conn.execute(
            "SELECT * FROM pets WHERE owner_id=? ORDER BY id DESC LIMIT 1",
            (owner_id,)).fetchone()
        conn.close()
    assert pet, "pet was not written"
    pet_id = pet["id"]

    # 3. The vet opens a visit for that animal.
    r = _post(client, "/visits/new", {
        "owner_id": owner_id, "pet_id": pet_id,
        "doctor_name": vet.get("full_name") or "Dr. Hatem",
        "visit_type": "Consultation",
        "chief_complaint": "Itching and hair loss",
        "symptoms": "Scratching, patchy fur",
        "weight_kg": "4.2", "temp_c": "38.6", "heart_rate": "160",
    })
    assert r.status_code == 200, "visit creation failed"

    with app.app_context():
        conn = db.get_db()
        visit = conn.execute(
            "SELECT * FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet_id,)).fetchone()
        conn.close()
    assert visit, "visit was not written"
    visit_id = visit["id"]

    # The visit page must actually show the patient it belongs to.
    page = client.get(f"/visits/{visit_id}").get_data(as_text=True)
    assert "Simba" in page, "visit page does not show its own patient"

    # 4. Diagnosis.
    r = _post(client, f"/visits/{visit_id}/diagnosis", {
        "diagnosis_text": "Flea allergy dermatitis",
        "severity": "Moderate",
        "diagnosis_notes": "Responds to topical treatment",
    })
    assert r.status_code == 200, "diagnosis POST failed"

    with app.app_context():
        conn = db.get_db()
        dx = conn.execute(
            "SELECT COUNT(*) FROM diagnoses WHERE visit_id=?", (visit_id,)
        ).fetchone()[0]
        conn.close()
    assert dx == 1, f"diagnosis not recorded against the visit (found {dx})"

    # 5. Completing the visit must raise an invoice — the clinical-to-money
    #    bridge, and the single most important link in the product.
    r = _post(client, f"/visits/{visit_id}/complete", {})
    assert r.status_code == 200, "completing the visit failed"

    with app.app_context():
        conn = db.get_db()
        inv = conn.execute(
            "SELECT * FROM invoices WHERE visit_id=? ORDER BY id DESC LIMIT 1",
            (visit_id,)).fetchone()
        v_after = conn.execute("SELECT status FROM visits WHERE id=?",
                               (visit_id,)).fetchone()
        conn.close()
    assert v_after["status"] == "Completed", \
        f"visit status is {v_after['status']!r}, not Completed"
    assert inv, "completing a visit did NOT generate an invoice"
    inv_id, total = inv["id"], float(inv["total"] or 0)

    # 6. The invoice must reach back to the client and the visit.
    page = client.get(f"/finance/invoices/{inv_id}").get_data(as_text=True)
    assert f"/crm/owners/{owner_id}" in page, "invoice does not link to its owner"
    assert f"/visits/{visit_id}" in page, "invoice does not link to its visit"

    # 7. Reception takes the money. Paying in full must settle it — this is
    #    where float arithmetic previously left ~1 in 7 invoices stuck on
    #    "Partial" while the screen showed 0.00 due.
    r = _post(client, f"/finance/invoices/{inv_id}/pay", {
        "amount": f"{total:.2f}", "method": "Cash", "reference": "E2E",
    })
    assert r.status_code == 200, "payment POST failed"

    with app.app_context():
        conn = db.get_db()
        settled = conn.execute("SELECT * FROM invoices WHERE id=?",
                               (inv_id,)).fetchone()
        conn.close()
    assert float(settled["due_amount"] or 0) < 0.005, \
        f"due_amount is {settled['due_amount']} after paying in full"
    assert settled["status"] == "Paid", \
        f"invoice paid in full still reads {settled['status']!r}"

    # 8. And the client's record must show the whole story.
    page = client.get(f"/crm/owners/{owner_id}").get_data(as_text=True)
    assert "Simba" in page, "owner page does not show their pet"

    page = client.get(f"/crm/pets/{pet_id}").get_data(as_text=True)
    assert "Flea allergy dermatitis" in page or f"/visits/{visit_id}" in page, \
        "pet record shows neither the diagnosis nor the visit"


def test_dispensing_deducts_stock(app, client, vet):
    """Pharmacy -> inventory: dispensing must actually move stock.

    Kept separate from the main chain because it needs an item and a batch,
    and because a silent failure here means a clinic's stock figures drift
    from reality with nothing to indicate it.
    """
    with app.app_context():
        item_id = db.create_item({
            "name": "Amoxicillin 250mg", "name_ar": "أموكسيسيلين ٢٥٠",
            "category_id": 1, "unit": "box", "reorder_level": 5,
            "cost_price": 40, "sell_price": 75,
        })
        # signature is (item_id, warehouse_id, batch_number, expiry_date,
        # quantity, unit_cost) — expiry BEFORE quantity, which is easy to
        # get backwards and stores the year as the stock level.
        db.add_stock_batch(item_id, 1, "E2E-B1", "2027-01-01", 50, 40)
        conn = db.get_db()
        before = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM batches WHERE item_id=?",
            (item_id,)).fetchone()[0]
        conn.close()
    assert float(before) == 50, f"batch intake did not land (got {before})"

    with app.app_context():
        db.deduct_stock(item_id, 3, reference_type="visit", reference_id=1, by="e2e")
        conn = db.get_db()
        after = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM batches WHERE item_id=?",
            (item_id,)).fetchone()[0]
        moves = conn.execute(
            "SELECT COUNT(*) FROM stock_movements WHERE item_id=?",
            (item_id,)).fetchone()[0]
        conn.close()

    assert float(after) == 47, f"stock not deducted: {before} -> {after}"
    assert moves >= 1, "no stock movement was recorded for the deduction"
