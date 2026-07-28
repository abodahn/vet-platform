# -*- coding: utf-8 -*-
"""Visits, clinical records (lab / vaccination / surgery), and imaging.

These are the routes that write a patient's medical record: the SOAP note, the
treatment plan, the prescription, the lab result, the vaccination, the surgery,
the X-ray. A route here that renders 200 and writes nothing is not a cosmetic
bug — it is a treatment that was given and never recorded, or recorded against
the wrong animal.

So no test in this file trusts a status code. Every POST is followed by a read
of the row it claims to have written, and by a check that the next module can
see it.

SQLite, no network — the imaging AI call is patched at its own boundary.
"""
import base64
import io
from datetime import date, timedelta

import models.database as db
from conftest import get_csrf


# 1x1 PNG — the smallest thing the upload route will accept as an image.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQ"
    "DJ/pLvAAAAAElFTkSuQmCC")


# ── helpers ───────────────────────────────────────────────────────────────────

def _post(client, url, data, follow=True, **kw):
    payload = dict(data)
    payload["_csrf_token"] = get_csrf(client)
    return client.post(url, data=payload, follow_redirects=follow, **kw)


def _rows(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def _one(app, sql, params=()):
    rows = _rows(app, sql, params)
    return rows[0] if rows else None


def _mk_case(app, name, pet_name=None, owner_name=None):
    """Owner + pet + open visit — the context every clinical record hangs off."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                (owner_name or (name + " Owner"), "01077700033"))
            owner_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, breed, sex, "
                "weight_kg, is_active) VALUES(?,?,?,?,?,?,1)",
                (owner_id, pet_name or name, "Dog", "Baladi", "Female", 9.5))
            pet_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO visits(owner_id, pet_id, visit_date, doctor_name, "
                "chief_complaint, status) VALUES(?,?,?,?,?,?)",
                (owner_id, pet_id, "2026-07-24", "Dr. Hatem",
                 "Vomiting for two days", "Open"))
            visit_id = cur.lastrowid
        conn.close()
    return {"owner_id": owner_id, "pet_id": pet_id, "visit_id": visit_id}


# ══ VISITS ════════════════════════════════════════════════════════════════════

def test_new_visit_form_carries_the_patient_it_was_opened_for(app, auth_client):
    fx = _mk_case(app, "NewVisitForm")
    r = auth_client.get(
        f"/visits/new?pet_id={fx['pet_id']}&owner_id={fx['owner_id']}")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "NewVisitForm" in html, \
        "the new-visit form does not show the patient it was opened for"
    assert str(fx["pet_id"]) in html, "the form would post without a pet_id"


def test_soap_notes_are_saved_against_the_visit(app, auth_client):
    """SOAP is the clinical narrative. Losing it loses the reasoning."""
    fx = _mk_case(app, "Soap")
    r = _post(auth_client, f"/visits/{fx['visit_id']}/soap", {
        "soap_subjective": "Owner reports vomiting x2 days, still drinking",
        "soap_objective":  "T 39.1, HR 120, abdomen soft, MM pink",
        "soap_assessment": "Acute gastroenteritis, mild dehydration",
        "soap_plan":       "SC fluids, metoclopramide, bland diet 3 days",
    })
    assert r.status_code == 200

    v = _one(app, "SELECT * FROM visits WHERE id=?", (fx["visit_id"],))
    assert v["soap_subjective"] == "Owner reports vomiting x2 days, still drinking"
    assert v["soap_objective"].startswith("T 39.1"), "objective findings lost"
    assert v["soap_assessment"] == "Acute gastroenteritis, mild dehydration"
    assert v["soap_plan"].startswith("SC fluids"), "the plan was not saved"

    # It has to come back on the page a vet reads next.
    html = auth_client.get(f"/visits/{fx['visit_id']}").get_data(as_text=True)
    assert "Acute gastroenteritis" in html, "saved SOAP does not show on the visit"

    assert _rows(app, "SELECT * FROM audit_log WHERE action=? AND entity_id=?",
                 ("soap_update", str(fx["visit_id"]))), \
        "a medical record was edited with no audit entry"


def test_treatment_plan_is_saved_and_then_updated_not_duplicated(app, auth_client):
    fx = _mk_case(app, "Treatment")
    _post(auth_client, f"/visits/{fx['visit_id']}/treatment", {
        "plan_text": "IV fluids 48h then oral", "goals": "Rehydrate, stop vomiting",
        "duration": "5 days", "followup_in": "7", "followup_unit": "days",
    })
    plan = _one(app, "SELECT * FROM treatment_plans WHERE visit_id=?",
                (fx["visit_id"],))
    assert plan, "treatment POST returned OK but saved no plan"
    assert plan["plan_text"] == "IV fluids 48h then oral"
    assert plan["goals"] == "Rehydrate, stop vomiting"
    assert plan["duration"] == "5 days"
    assert int(plan["followup_in"]) == 7
    assert plan["followup_unit"] == "days"

    _post(auth_client, f"/visits/{fx['visit_id']}/treatment",
          {"plan_text": "Revised: oral only", "goals": "Maintain hydration",
           "duration": "3 days", "followup_in": "3", "followup_unit": "days"})
    plans = _rows(app, "SELECT * FROM treatment_plans WHERE visit_id=?",
                  (fx["visit_id"],))
    assert len(plans) == 1, \
        f"editing the plan created a second one ({len(plans)} rows) — which does the vet follow?"
    assert plans[0]["plan_text"] == "Revised: oral only", "the edit did not take"


def test_prescription_written_at_the_visit_reaches_the_pharmacy(app, auth_client):
    """The link the pharmacy queue is built on.

    A prescription that does not carry its pet and owner drops out of the
    dispensing queue's joins and 404s when a pharmacist opens it — which is
    exactly how a prescribed drug ends up never handed over.
    """
    fx = _mk_case(app, "RxFromVisit")
    r = _post(auth_client, f"/visits/{fx['visit_id']}/prescription", {
        "rx_notes": "Give with food",
        "medication_name_1": "Metoclopramide 10mg", "dosage_1": "0.5 mg/kg",
        "frequency_1": "TID", "duration_1": "3 days", "route_1": "PO",
        "quantity_1": "9", "unit_1": "tablet", "instructions_1": "Before meals",
        "medication_name_2": "Omeprazole 20mg", "dosage_2": "1 mg/kg",
        "frequency_2": "SID", "duration_2": "7 days", "route_2": "PO",
        "quantity_2": "7", "unit_2": "capsule", "instructions_2": "Empty stomach",
    })
    assert r.status_code == 200, "prescription POST did not render"

    rx = _one(app, "SELECT * FROM prescriptions WHERE visit_id=?", (fx["visit_id"],))
    assert rx, "prescription POST returned OK but wrote no prescription"
    assert rx["pet_id"] == fx["pet_id"], \
        "the prescription does not know which animal it is for"
    assert rx["owner_id"] == fx["owner_id"], \
        "the prescription does not know who collects it"
    assert rx["notes"] == "Give with food"

    items = _rows(app, "SELECT * FROM prescription_items WHERE prescription_id=? "
                       "ORDER BY id", (rx["id"],))
    assert len(items) == 2, f"two drugs were prescribed, {len(items)} were stored"
    assert items[0]["medication_name"] == "Metoclopramide 10mg"
    assert items[0]["dosage"] == "0.5 mg/kg"
    assert items[0]["frequency"] == "TID"
    assert items[0]["duration"] == "3 days"
    assert float(items[0]["quantity"]) == 9, "the dispensed quantity is wrong"
    assert items[0]["instructions"] == "Before meals"
    assert items[1]["medication_name"] == "Omeprazole 20mg"

    # The pharmacist must be able to find it and open it.
    queue = auth_client.get("/pharmacy/").get_data(as_text=True)
    assert f"/pharmacy/prescription/{rx['id']}" in queue, \
        "a prescription just written is not in the dispensing queue"
    assert auth_client.get(f"/pharmacy/prescription/{rx['id']}").status_code == 200, \
        "the pharmacist cannot open the prescription"

    # And it must show on the visit that wrote it.
    html = auth_client.get(f"/visits/{fx['visit_id']}").get_data(as_text=True)
    assert "Metoclopramide 10mg" in html, "the prescription is missing from the visit"


def test_visit_printout_carries_the_whole_record(app, auth_client):
    """The sheet the owner walks out with — it has to hold the record."""
    fx = _mk_case(app, "Printout")
    _post(auth_client, f"/visits/{fx['visit_id']}/diagnosis",
          {"diagnosis_text": "Acute gastroenteritis", "severity": "Moderate"})
    _post(auth_client, f"/visits/{fx['visit_id']}/treatment",
          {"plan_text": "SC fluids and bland diet"})
    _post(auth_client, f"/visits/{fx['visit_id']}/prescription",
          {"medication_name_1": "Metronidazole 250mg", "quantity_1": "10",
           "dosage_1": "15 mg/kg", "frequency_1": "BID"})

    # The screen the vet reads must show it too — both pages render the
    # diagnosis under a different name than the column it is stored in.
    detail = auth_client.get(f"/visits/{fx['visit_id']}").get_data(as_text=True)
    assert "Acute gastroenteritis" in detail, \
        "the visit page lists the diagnosis row but not the diagnosis"

    r = auth_client.get(f"/visits/{fx['visit_id']}/print")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Printout" in html, "the printout does not name the patient"
    assert "Acute gastroenteritis" in html, "the printout has no diagnosis"
    assert "SC fluids and bland diet" in html, "the printout has no treatment plan"
    assert "Metronidazole 250mg" in html, "the printout has no prescription"


def test_print_of_a_missing_visit_does_not_500(app, auth_client):
    r = auth_client.get("/visits/999999/print", follow_redirects=True)
    assert r.status_code == 200


# ══ CLINICAL — LAB ════════════════════════════════════════════════════════════

def test_clinical_index_lands_somewhere_real(app, auth_client):
    r = auth_client.get("/clinical/", follow_redirects=False)
    assert r.status_code in (301, 302)
    assert "/clinical/vaccinations" in r.headers["Location"]
    assert auth_client.get("/clinical/", follow_redirects=True).status_code == 200


def test_lab_request_form_prefills_from_the_visit(app, auth_client):
    fx = _mk_case(app, "LabForm")
    r = auth_client.get(f"/clinical/lab/new?visit_id={fx['visit_id']}")
    assert r.status_code == 200
    assert "LabForm" in r.get_data(as_text=True), \
        "the lab form does not show which patient the sample is from"


def test_lab_request_is_written_against_its_visit_and_pet(app, auth_client):
    fx = _mk_case(app, "LabNew")
    r = _post(auth_client, "/clinical/lab/new", {
        "visit_id": fx["visit_id"], "pet_id": fx["pet_id"],
        "test_name": "CBC (Complete Blood Count)", "test_code": "CBC-01",
        "priority": "Urgent", "sample_type": "EDTA whole blood",
        "notes": "Suspected anaemia",
    })
    assert r.status_code == 200

    lab = _one(app, "SELECT * FROM lab_requests WHERE visit_id=?", (fx["visit_id"],))
    assert lab, "lab request POST returned OK but requested nothing"
    assert lab["pet_id"] == fx["pet_id"], "the sample is filed under the wrong animal"
    assert lab["test_name"] == "CBC (Complete Blood Count)"
    assert lab["test_code"] == "CBC-01"
    assert lab["priority"] == "Urgent", \
        f"an urgent test was queued as {lab['priority']!r}"
    assert lab["sample_type"] == "EDTA whole blood"
    assert lab["notes"] == "Suspected anaemia"
    assert lab["status"] == "Pending"
    assert lab["requested_by"], "nobody is recorded as having ordered the test"

    html = auth_client.get("/clinical/lab").get_data(as_text=True)
    assert "CBC-01" in html, "a pending lab request is not on the lab worklist"


def test_a_custom_lab_test_keeps_the_name_that_was_typed(app, auth_client):
    fx = _mk_case(app, "LabCustom")
    _post(auth_client, "/clinical/lab/new", {
        "visit_id": fx["visit_id"], "pet_id": fx["pet_id"],
        "test_name": "Custom", "custom_test": "Leishmania PCR",
    })
    lab = _one(app, "SELECT * FROM lab_requests WHERE visit_id=?", (fx["visit_id"],))
    assert lab and lab["test_name"] == "Leishmania PCR", \
        "a custom test was filed as the literal word 'Custom'"


def test_a_lab_request_with_no_test_name_is_not_created(app, auth_client):
    fx = _mk_case(app, "LabBlank")
    _post(auth_client, "/clinical/lab/new",
          {"visit_id": fx["visit_id"], "pet_id": fx["pet_id"], "test_name": ""})
    assert _rows(app, "SELECT * FROM lab_requests WHERE visit_id=?",
                 (fx["visit_id"],)) == [], "an empty lab request was queued"


def test_lab_result_attaches_to_its_request_and_flags_abnormal(app, auth_client):
    """An abnormal result that is not flagged is an abnormal result nobody chases."""
    fx = _mk_case(app, "LabResult")
    _post(auth_client, "/clinical/lab/new", {
        "visit_id": fx["visit_id"], "pet_id": fx["pet_id"],
        "test_name": "Blood Glucose", "sample_type": "Serum"})
    lab = _one(app, "SELECT * FROM lab_requests WHERE visit_id=?", (fx["visit_id"],))

    r = _post(auth_client, f"/clinical/lab/{lab['id']}/results", {
        "result_text": "Marked hyperglycaemia", "result_value": "412.5",
        "unit": "mg/dL", "reference_range": "70-120", "is_abnormal": "on",
    })
    assert r.status_code == 200

    res = _one(app, "SELECT * FROM lab_results WHERE lab_request_id=?", (lab["id"],))
    assert res, "results POST returned OK but recorded no result"
    assert res["pet_id"] == fx["pet_id"], "the result is filed under the wrong animal"
    assert res["result_text"] == "Marked hyperglycaemia"
    assert float(res["result_value"]) == 412.5, \
        f"the numeric result stored as {res['result_value']}"
    assert res["unit"] == "mg/dL"
    assert res["reference_range"] == "70-120"
    assert int(res["is_abnormal"]) == 1, "an abnormal result was stored as normal"
    assert res["reviewed_by"], "no reviewer on a clinical result"
    assert res["reviewed_at"], "no review time on a clinical result"

    after = _one(app, "SELECT * FROM lab_requests WHERE id=?", (lab["id"],))
    assert after["status"] == "Completed", \
        f"a request with results in still reads {after['status']!r}"

    html = auth_client.get(f"/clinical/lab/{lab['id']}").get_data(as_text=True)
    assert "412.5" in html, "the result does not show on the request it belongs to"


def test_a_normal_lab_result_is_not_flagged_abnormal(app, auth_client):
    fx = _mk_case(app, "LabNormal")
    _post(auth_client, "/clinical/lab/new", {
        "visit_id": fx["visit_id"], "pet_id": fx["pet_id"],
        "test_name": "Blood Glucose"})
    lab = _one(app, "SELECT * FROM lab_requests WHERE visit_id=?", (fx["visit_id"],))
    _post(auth_client, f"/clinical/lab/{lab['id']}/results", {
        "result_text": "Within range", "result_value": "94", "unit": "mg/dL"})

    res = _one(app, "SELECT * FROM lab_results WHERE lab_request_id=?", (lab["id"],))
    assert int(res["is_abnormal"]) == 0, \
        "a normal result was flagged abnormal — the flag means nothing if it is always on"


def test_results_for_a_request_that_does_not_exist_are_refused(app, auth_client):
    r = auth_client.post("/clinical/lab/999999/results",
                         data={"result_text": "orphan",
                               "_csrf_token": get_csrf(auth_client)})
    assert r.status_code == 404
    assert _rows(app, "SELECT * FROM lab_results WHERE lab_request_id=?",
                 (999999,)) == []


# ══ CLINICAL — VACCINATION ════════════════════════════════════════════════════

def test_vaccination_form_loads_for_a_pet(app, auth_client):
    fx = _mk_case(app, "VaxForm")
    r = auth_client.get(f"/clinical/vaccinations/new?pet_id={fx['pet_id']}")
    assert r.status_code == 200
    assert "VaxForm" in r.get_data(as_text=True), \
        "the vaccination form does not show which animal is being vaccinated"


def test_vaccination_is_recorded_with_its_due_date(app, auth_client):
    """The due date is the whole point — it is what recalls the animal."""
    fx = _mk_case(app, "Vax")
    due = (date.today() + timedelta(days=10)).isoformat()
    r = _post(auth_client, "/clinical/vaccinations/new", {
        "pet_id": fx["pet_id"], "vaccine_name": "Rabies",
        "vaccine_brand": "Rabisin", "batch_number": "RB-2026-77",
        "dose_number": "2", "administered_at": "2026-07-24",
        "next_due_at": due, "site": "Left shoulder SC",
        "notes": "No adverse reaction observed",
    })
    assert r.status_code == 200

    v = _one(app, "SELECT * FROM vaccinations WHERE pet_id=?", (fx["pet_id"],))
    assert v, "vaccination POST returned OK but recorded no vaccination"
    assert v["vaccine_name"] == "Rabies"
    assert v["vaccine_brand"] == "Rabisin"
    assert v["batch_number"] == "RB-2026-77", \
        "the vaccine batch number was lost — it is what a recall traces"
    assert int(v["dose_number"]) == 2
    assert str(v["administered_at"])[:10] == "2026-07-24"
    assert str(v["next_due_at"])[:10] == due, \
        f"next dose due {v['next_due_at']}, should be {due}"
    assert v["site"] == "Left shoulder SC"
    assert v["administered_by"], "nobody is recorded as having given the injection"

    html = auth_client.get("/clinical/vaccinations").get_data(as_text=True)
    assert "RB-2026-77" in html, "a recorded vaccination is missing from the register"
    assert "Vax" in html and due in html, \
        "a vaccination due in 10 days is not on the upcoming-due list"


def test_a_custom_vaccine_keeps_the_name_that_was_typed(app, auth_client):
    fx = _mk_case(app, "VaxCustom")
    _post(auth_client, "/clinical/vaccinations/new", {
        "pet_id": fx["pet_id"], "vaccine_name": "Custom",
        "custom_vaccine": "Leishmania (CaniLeish)"})
    v = _one(app, "SELECT * FROM vaccinations WHERE pet_id=?", (fx["pet_id"],))
    assert v and v["vaccine_name"] == "Leishmania (CaniLeish)"


def test_vaccination_certificate_survives_arabic_pet_and_clinic(app, auth_client,
                                                                monkeypatch):
    """The certificate an owner carries abroad. Arabic in it was crashing today.

    Arabic needs reshaping and bidi reordering before it reaches the PDF font;
    a clinic only has to type its own name in Arabic to hit it.
    """
    fx = _mk_case(app, "VaxAr", pet_name="مشمش", owner_name="سلمى عبد الرحمن")
    _post(auth_client, "/clinical/vaccinations/new", {
        "pet_id": fx["pet_id"], "vaccine_name": "Rabies",
        "batch_number": "AR-1", "notes": "تم التطعيم بدون مضاعفات"})
    v = _one(app, "SELECT * FROM vaccinations WHERE pet_id=?", (fx["pet_id"],))

    monkeypatch.setattr(db, "get_clinic", lambda: {
        "name": "Aleefy Veterinary Clinic",
        "name_ar": "عيادة أليفي البيطرية",
        "phone": "0223456789", "address": "مدينة نصر، القاهرة",
    })

    r = auth_client.get(f"/clinical/vaccinations/{v['id']}/certificate")
    assert r.status_code == 200, "certificate route did not return the PDF"
    assert r.data[:4] == b"%PDF", \
        f"certificate is not a PDF — got {r.data[:80]!r} (generation failed and redirected)"
    assert len(r.data) > 1000, "the certificate PDF is suspiciously empty"
    assert "application/pdf" in r.headers["Content-Type"]
    assert "attachment" in r.headers.get("Content-Disposition", "")


def test_certificate_for_a_vaccination_that_does_not_exist_is_404(app, auth_client):
    assert auth_client.get("/clinical/vaccinations/999999/certificate").status_code == 404


# ══ CLINICAL — SURGERY ════════════════════════════════════════════════════════

def test_surgery_form_loads(app, auth_client):
    fx = _mk_case(app, "SurgForm")
    r = auth_client.get(f"/clinical/surgeries/new?pet_id={fx['pet_id']}")
    assert r.status_code == 200
    assert "SurgForm" in r.get_data(as_text=True)


def test_surgery_record_keeps_every_note_and_its_outcome(app, auth_client):
    """Pre-op, intra-op and post-op notes are three different records.

    Whatever went wrong in theatre is written in exactly one of them; a field
    quietly dropped on save is the one nobody can produce afterwards.
    """
    fx = _mk_case(app, "Surgery")
    r = _post(auth_client, "/clinical/surgeries/new", {
        "pet_id": fx["pet_id"], "procedure_name": "Ovariohysterectomy",
        "surgeon": "Dr. Hatem", "anesthetist": "Dr. Nour",
        "surgery_date": "2026-07-25", "duration_min": "75",
        "anesthesia_type": "General",
        "pre_op_notes": "Fasted 12h, pre-anaesthetic bloods normal",
        "intra_op_notes": "Mild haemorrhage from left pedicle, ligated",
        "post_op_notes": "Recovered smoothly, extubated 10 min",
        "outcome": "Successful", "followup_date": "2026-08-04",
        "consent_given": "on",
    })
    assert r.status_code == 200

    s = _one(app, "SELECT * FROM surgeries WHERE pet_id=?", (fx["pet_id"],))
    assert s, "surgery POST returned OK but recorded no surgery"
    assert s["procedure_name"] == "Ovariohysterectomy"
    assert s["surgeon"] == "Dr. Hatem"
    assert s["anesthetist"] == "Dr. Nour"
    assert str(s["surgery_date"])[:10] == "2026-07-25"
    assert int(s["duration_min"]) == 75, "anaesthetic duration lost"
    assert s["anesthesia_type"] == "General"
    assert s["pre_op_notes"].startswith("Fasted 12h")
    assert s["intra_op_notes"] == "Mild haemorrhage from left pedicle, ligated", \
        "the intra-operative note — the one that matters in a complaint — was lost"
    assert s["post_op_notes"].startswith("Recovered smoothly")
    assert s["outcome"] == "Successful"
    assert str(s["followup_date"])[:10] == "2026-08-04"
    assert int(s["consent_given"]) == 1, "consent recorded as not given"

    html = auth_client.get("/clinical/surgeries").get_data(as_text=True)
    assert "Ovariohysterectomy" in html and "Surgery" in html, \
        "the surgery is missing from the surgery list"


def test_a_surgery_that_went_wrong_records_that_it_went_wrong(app, auth_client):
    fx = _mk_case(app, "SurgeryBad")
    _post(auth_client, "/clinical/surgeries/new", {
        "pet_id": fx["pet_id"], "procedure_name": "Gastrotomy",
        "outcome": "Complications", "duration_min": "not a number",
        "intra_op_notes": "Cardiac arrest at 40 min, resuscitated",
    })
    s = _one(app, "SELECT * FROM surgeries WHERE pet_id=?", (fx["pet_id"],))
    assert s["outcome"] == "Complications", \
        "an outcome other than Successful was not stored as given"
    assert s["duration_min"] is None, "unparsable duration was stored as a number"
    assert "Cardiac arrest" in s["intra_op_notes"]


def test_a_surgery_without_a_pet_is_not_recorded(app, auth_client):
    before = len(_rows(app, "SELECT id FROM surgeries"))
    _post(auth_client, "/clinical/surgeries/new",
          {"pet_id": "", "procedure_name": "Nobody's operation"})
    assert len(_rows(app, "SELECT id FROM surgeries")) == before, \
        "a surgery was recorded against no animal"


# ══ IMAGING ═══════════════════════════════════════════════════════════════════

def test_imaging_upload_form_lists_pets(app, auth_client):
    fx = _mk_case(app, "ImgForm")
    r = auth_client.get(f"/imaging/upload?pet_id={fx['pet_id']}")
    assert r.status_code == 200
    assert "ImgForm" in r.get_data(as_text=True), \
        "the upload form offers no patient to attach the study to"


def test_uploading_a_study_stores_the_row_and_the_file(app, auth_client):
    fx = _mk_case(app, "ImgUpload")
    r = _post(auth_client, "/imaging/upload", {
        "pet_id": fx["pet_id"], "visit_id": fx["visit_id"],
        "study_type": "X-Ray", "body_region": "Right stifle",
        "notes": "Lateral view, suspected cruciate rupture",
        "image_file": (io.BytesIO(PNG_1PX), "stifle.png"),
    }, content_type="multipart/form-data")
    assert r.status_code == 200

    st = _one(app, "SELECT * FROM imaging_studies WHERE pet_id=?", (fx["pet_id"],))
    assert st, "upload returned OK but stored no study"
    assert st["owner_id"] == fx["owner_id"], "the study lost its owner"
    assert int(st["visit_id"]) == fx["visit_id"], "the study lost its visit"
    assert st["study_type"] == "X-Ray"
    assert st["body_region"] == "Right stifle"
    assert st["notes"] == "Lateral view, suspected cruciate rupture"
    assert st["file_path"], "a study was stored with no image"
    assert not st["ai_analysis"], \
        "AI analysis was recorded although it was never requested"

    # The image itself must come back byte for byte.
    served = auth_client.get(f"/imaging/file/{st['file_path']}")
    assert served.status_code == 200, "the stored X-ray cannot be retrieved"
    assert served.data == PNG_1PX, "the image served back is not the one uploaded"

    detail = auth_client.get(f"/imaging/study/{st['id']}")
    assert detail.status_code == 200
    html = detail.get_data(as_text=True)
    assert "Right stifle" in html and "ImgUpload" in html, \
        "the study page does not show its region or its patient"


def test_a_non_image_upload_is_refused(app, auth_client):
    fx = _mk_case(app, "ImgBadType")
    _post(auth_client, "/imaging/upload", {
        "pet_id": fx["pet_id"], "study_type": "X-Ray",
        "image_file": (io.BytesIO(b"#!/bin/sh\nrm -rf /"), "payload.sh"),
    }, content_type="multipart/form-data")
    assert _rows(app, "SELECT * FROM imaging_studies WHERE pet_id=?",
                 (fx["pet_id"],)) == [], "a non-image file was stored as a study"


def test_upload_without_a_pet_stores_nothing(app, auth_client):
    before = len(_rows(app, "SELECT id FROM imaging_studies"))
    _post(auth_client, "/imaging/upload", {
        "pet_id": "", "study_type": "X-Ray",
        "image_file": (io.BytesIO(PNG_1PX), "orphan.png"),
    }, content_type="multipart/form-data")
    assert len(_rows(app, "SELECT id FROM imaging_studies")) == before, \
        "an imaging study was stored against no animal"


def test_study_detail_of_a_missing_study_does_not_500(app, auth_client):
    r = auth_client.get("/imaging/study/999999", follow_redirects=True)
    assert r.status_code == 200


def test_serve_file_cannot_be_walked_out_of_the_uploads_directory(app, auth_client):
    r = auth_client.get("/imaging/file/..%2F..%2Fconfig.py")
    assert r.status_code == 404, "the image route served a file outside uploads/"


def test_ai_analysis_runs_only_when_asked_and_is_stored(app, auth_client, monkeypatch):
    """The AI call is patched at its own boundary — no network in this suite."""
    import blueprints.imaging.routes as imaging_routes
    calls = []

    def _fake(image_bytes, mime_type, user_note=""):
        calls.append((len(image_bytes), mime_type, user_note))
        return "Severity: 🟡 Moderate. Likely superficial pyoderma."

    monkeypatch.setattr(imaging_routes, "_analyze_image", _fake)

    fx = _mk_case(app, "ImgAI")
    _post(auth_client, "/imaging/upload", {
        "pet_id": fx["pet_id"], "study_type": "Photo", "run_ai": "on",
        "notes": "Skin lesion on flank",
        "image_file": (io.BytesIO(PNG_1PX), "lesion.png"),
    }, content_type="multipart/form-data")

    assert calls, "run_ai was ticked and no analysis was attempted"
    assert calls[0][2] == "Skin lesion on flank", "the clinician's note never reached the model"
    st = _one(app, "SELECT * FROM imaging_studies WHERE pet_id=?", (fx["pet_id"],))
    assert st and "superficial pyoderma" in st["ai_analysis"], \
        "the analysis was produced and then not stored"


def test_analyzer_returns_a_result_for_a_photo(app, auth_client, monkeypatch):
    import blueprints.imaging.routes as imaging_routes
    monkeypatch.setattr(imaging_routes, "_analyze_image",
                        lambda b, m, n="": f"Assessment for {n or 'photo'}")

    r = _post(auth_client, "/imaging/analyzer/analyze",
              {"note": "stray cat, limping",
               "photo": (io.BytesIO(PNG_1PX), "cat.png")},
              content_type="multipart/form-data")
    assert r.status_code == 200
    assert r.get_json()["result"] == "Assessment for stray cat, limping"


def test_analyzer_rejects_a_missing_or_unsupported_photo(app, auth_client):
    r = _post(auth_client, "/imaging/analyzer/analyze", {"note": "no file"},
              content_type="multipart/form-data")
    assert r.status_code == 400
    assert "error" in r.get_json()

    r = _post(auth_client, "/imaging/analyzer/analyze",
              {"photo": (io.BytesIO(b"not an image"), "notes.txt")},
              content_type="multipart/form-data")
    assert r.status_code == 400


def test_analyzer_result_can_be_filed_against_a_patient(app, auth_client):
    fx = _mk_case(app, "ImgSave")
    r = auth_client.post("/imaging/analyzer/save", json={
        "pet_id": fx["pet_id"], "filename": "triage.jpg",
        "result": "Severity: 🔴 Urgent. Open wound, needs debridement.",
        "_csrf_token": get_csrf(auth_client),
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json().get("ok") is True

    st = _one(app, "SELECT * FROM imaging_studies WHERE pet_id=?", (fx["pet_id"],))
    assert st, "the analyzer said it saved and stored nothing"
    assert st["study_type"] == "AI Analysis"
    assert st["owner_id"] == fx["owner_id"], "the saved analysis lost its owner"
    assert "debridement" in st["ai_analysis"], "the assessment text was not stored"
    assert st["file_path"] == "triage.jpg"


def test_analyzer_save_without_a_pet_or_a_result_is_refused(app, auth_client):
    before = len(_rows(app, "SELECT id FROM imaging_studies"))
    tok = get_csrf(auth_client)
    assert auth_client.post("/imaging/analyzer/save",
                            json={"result": "orphan", "_csrf_token": tok}
                            ).status_code == 400
    assert auth_client.post("/imaging/analyzer/save",
                            json={"pet_id": 1, "_csrf_token": tok}
                            ).status_code == 400
    assert len(_rows(app, "SELECT id FROM imaging_studies")) == before


def test_analyzer_save_without_csrf_stores_nothing(app, auth_client):
    fx = _mk_case(app, "ImgNoToken")
    r = auth_client.post("/imaging/analyzer/save",
                         json={"pet_id": fx["pet_id"], "result": "should not persist"})
    assert r.status_code == 403
    assert _rows(app, "SELECT * FROM imaging_studies WHERE pet_id=?",
                 (fx["pet_id"],)) == []
