# -*- coding: utf-8 -*-
"""Platform-side routes: AI assistant, public API, uploads, notifications,
settings, launcher, doctor workspace, Petsy widget.

The rule for every test here: POST, then read the database or the filesystem.
A 200 proves the view did not raise; it proves nothing about what was written.

No test in this module may reach the network. `_no_network` is autouse and
replaces the OpenAI client factory with one that raises, so an AI route that
forgets to go through `call_ai()` fails loudly instead of dialling out.
"""
import json
import os
import sqlite3
import time
from datetime import date, timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest

import models.database as db
from blueprints.ai_assistant import routes as ai_routes
from blueprints.launcher import routes as launcher_routes


# ── helpers ───────────────────────────────────────────────────────────────────

PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _csrf(client):
    """The app validates `_csrf_token`; any GET seeds it."""
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data=None, **kw):
    payload = dict(data or {})
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, **kw)


def _post_json(client, url, body):
    return client.post(url, json=body, headers={"X-CSRF-Token": _csrf(client)})


def _conn():
    return db.get_db()


def _scalar(sql, params=()):
    c = _conn()
    try:
        row = c.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        c.close()


def _exec(sql, params=()):
    c = _conn()
    try:
        with c:
            cur = c.execute(sql, params)
            return cur.lastrowid
    finally:
        c.close()


def _become(client, role, user_id=None, username=None, full_name="", **extra):
    """Put a user of `role` in the session. The whole app reads session['user']."""
    with client.session_transaction() as s:
        s["user"] = {
            "id": user_id if user_id is not None else 999001,
            "username": username or f"t_{role}",
            "full_name": full_name or username or f"t_{role}",
            "role": role,
            **extra,
        }
        s["lang"] = "en"
    return client


@pytest.fixture
def admin(app, client):
    """Logged-in super_admin, using the real seeded user row."""
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")
    return c


@pytest.fixture
def admin_id(app):
    with app.app_context():
        return _scalar("SELECT id FROM users WHERE username='admin'")


@pytest.fixture
def patient(app):
    """An owner + pet, created once per test with a unique phone."""
    with app.app_context():
        phone = f"0100{int(time.time() * 1000) % 10_000_000:07d}"
        oid = _exec("INSERT INTO owners (full_name, phone) VALUES (?,?)",
                    ("Test Owner " + phone, phone))
        pid = _exec("INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                    (oid, "Pixel" + phone[-4:], "Cat"))
        return {"owner_id": oid, "pet_id": pid, "phone": phone,
                "pet_name": "Pixel" + phone[-4:]}


# ═════════════════════════════════════════════════════════════════════════════
# AI ASSISTANT
# ═════════════════════════════════════════════════════════════════════════════

class _Completions:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))],
            model="fake-model",
        )


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Nothing in this module may open a socket to a model provider."""
    def _boom():
        raise RuntimeError("network access is not allowed in tests")
    monkeypatch.setattr(ai_routes, "_client", _boom)
    monkeypatch.setattr(ai_routes, "_OPENAI_AVAILABLE", True)


@pytest.fixture
def fake_ai(monkeypatch):
    """Install a canned model reply and hand back the recorder."""
    def _install(reply):
        comp = _Completions(reply)
        monkeypatch.setattr(
            ai_routes, "_client",
            lambda: SimpleNamespace(chat=SimpleNamespace(completions=comp)))
        return comp
    return _install


def _prompt_of(comp, call=0):
    """The text the route actually sent to the model."""
    msgs = comp.calls[call]["messages"]
    return "\n".join(
        m["content"] if isinstance(m["content"], str) else json.dumps(m["content"])
        for m in msgs
    )


# ── drug interactions: must never say "safe" for a check that did not run ─────

def test_drug_interactions_without_a_drug_never_reports_safe(admin, fake_ai):
    comp = fake_ai('{"safe": true, "severity": "none"}')
    r = _post_json(admin, "/ai/drug-interactions", {"new_drug": ""})
    body = r.get_json()
    assert body["safe"] is None
    assert body["severity"] == "unchecked"
    assert comp.calls == [], "no drug named — the model must not be called at all"


def test_drug_interactions_without_co_medication_is_unchecked(admin, fake_ai):
    comp = fake_ai('{"safe": true, "severity": "none"}')
    r = _post_json(admin, "/ai/drug-interactions",
                   {"new_drug": "Paracetamol", "current_medications": [],
                    "species": "Cat"})
    body = r.get_json()
    assert body["safe"] is None
    assert body["severity"] == "unchecked"
    assert "does NOT check species" in body["recommendation"]
    assert comp.calls == []


def test_drug_interactions_fails_closed_when_the_model_is_unreachable(admin):
    """_no_network is still in force: call_ai swallows the error and returns prose.

    That prose does not parse as JSON. The result must be safe=False, never
    the template's green "Safe to prescribe" branch.
    """
    r = _post_json(admin, "/ai/drug-interactions", {
        "new_drug": "Meloxicam",
        "current_medications": ["Enalapril"],
        "species": "Dog",
    })
    body = r.get_json()
    assert body["safe"] is False
    assert body["severity"] == "unchecked"
    assert "NOT a statement that the combination is safe" in body["recommendation"]


def test_drug_interactions_reply_without_severity_fails_closed(admin, fake_ai):
    fake_ai('{"safe": true, "interactions": [], "recommendation": "fine"}')
    body = _post_json(admin, "/ai/drug-interactions", {
        "new_drug": "Meloxicam", "current_medications": ["Enalapril"]}).get_json()
    assert body["severity"] == "unchecked"
    assert body["safe"] is False


def test_drug_interactions_passes_through_a_real_severe_finding(admin, fake_ai):
    comp = fake_ai(json.dumps({
        "safe": False, "severity": "severe",
        "interactions": [{"drugs": "Meloxicam + Enalapril", "effect": "renal"}],
        "recommendation": "Do not co-prescribe.",
    }))
    body = _post_json(admin, "/ai/drug-interactions", {
        "new_drug": "Meloxicam", "current_medications": ["Enalapril"],
        "species": "Dog"}).get_json()
    assert body["severity"] == "severe"
    assert body["safe"] is False
    assert body["interactions"][0]["drugs"] == "Meloxicam + Enalapril"
    # the patient's species and both drugs must reach the model
    sent = _prompt_of(comp)
    assert "Meloxicam" in sent and "Enalapril" in sent and "Dog" in sent


# ── insights: the snapshot must carry real numbers, not silent zeros ──────────

def test_insights_snapshot_carries_the_real_appointment_count(app, admin, fake_ai,
                                                              patient):
    today = date.today().isoformat()
    with app.app_context():
        _exec("INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
              " doctor_name, status) VALUES (?,?,?,?,?,?)",
              (patient["owner_id"], patient["pet_id"], today, "10:00",
               "Dr Insight", "Scheduled"))
        expected = _scalar("SELECT COUNT(*) FROM appointments WHERE appt_date=?",
                           (today,))
        expected_owners = _scalar(
            "SELECT COUNT(*) FROM owners WHERE SUBSTRING(created_at::text,1,10)=?",
            (today,))

    comp = fake_ai('[{"icon":"x","text":"a","type":"info"}]')
    r = _post_json(admin, "/ai/insights", {})
    assert r.status_code == 200
    assert r.get_json()["insights"][0]["text"] == "a"

    sent = _prompt_of(comp)
    assert expected >= 1
    assert f"Appointments today: {expected}" in sent, (
        "the clinic snapshot reported a different number than the database holds "
        "— a swallowed query error would show 0 here")
    assert f"New clients registered today: {expected_owners}" in sent


def test_insights_malformed_json_array_degrades_to_one_info_card(admin, fake_ai):
    fake_ai("Here you go: [not, valid, json]")
    body = _post_json(admin, "/ai/insights", {}).get_json()
    assert len(body["insights"]) == 1
    assert body["insights"][0]["type"] == "info"


def test_insights_reply_with_no_array_at_all_returns_nothing(admin, fake_ai):
    """KNOWN GAP, pinned: the `[{icon...}]` fallback is only reachable when the
    reply contains brackets. A reply with none yields an empty insights list —
    the panel renders as if the clinic had nothing worth flagging."""
    fake_ai("I am not JSON at all.")
    assert _post_json(admin, "/ai/insights", {}).get_json()["insights"] == []


# ── outbreak radar: the cluster query must actually run ───────────────────────

def test_outbreak_radar_flags_a_real_three_pet_cluster(app, admin, patient):
    """The query is wrapped in `except Exception: pass`. If it ever breaks the
    radar reports "no outbreaks" forever, which reads as good news."""
    tag = f"Parvo-{int(time.time() * 1000) % 100000}"
    with app.app_context():
        for i in range(3):
            pid = _exec("INSERT INTO pets (owner_id, pet_name) VALUES (?,?)",
                        (patient["owner_id"], f"{tag}-pet{i}"))
            vid = _exec("INSERT INTO visits (owner_id, pet_id, visit_date) VALUES (?,?,?)",
                        (patient["owner_id"], pid, date.today().isoformat()))
            _exec("INSERT INTO diagnoses (visit_id, pet_id, diagnosis, created_at)"
                  " VALUES (?,?,?,?)",
                  (vid, pid, tag, date.today().isoformat() + " 09:00:00"))

    body = admin.get("/ai/outbreak-radar").get_json()
    mine = [o for o in body["outbreaks"] if o["diagnosis"] == tag]
    assert mine, f"cluster {tag} was not detected — the scan query returned nothing"
    assert mine[0]["pet_count"] == 3
    assert mine[0]["case_count"] == 3
    assert mine[0]["level"] == "alert"
    assert body["alert_count"] >= 1


# ── conversation history is per user ─────────────────────────────────────────

def test_clear_deletes_only_the_calling_users_conversations(app, admin, admin_id):
    other = 987654
    with app.app_context():
        _exec("INSERT INTO ai_conversations (user_id, role, prompt, response)"
              " VALUES (?,?,?,?)", (admin_id, "super_admin", "mine", "r"))
        _exec("INSERT INTO ai_conversations (user_id, role, prompt, response)"
              " VALUES (?,?,?,?)", (other, "doctor", "theirs", "r"))

    r = _post(admin, "/ai/clear")
    assert r.status_code in (302, 200)

    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM ai_conversations WHERE user_id=?",
                       (admin_id,)) == 0
        assert _scalar("SELECT COUNT(*) FROM ai_conversations WHERE user_id=?",
                       (other,)) == 1, "another user's history was deleted"
        _exec("DELETE FROM ai_conversations WHERE user_id=?", (other,))


def test_history_page_shows_a_saved_exchange(app, admin, admin_id):
    with app.app_context():
        _exec("INSERT INTO ai_conversations (user_id, role, prompt, response,"
              " created_at) VALUES (?,?,?,?,?)",
              (admin_id, "super_admin", "HISTORY-MARKER-42", "answer",
               date.today().isoformat() + " 08:00:00"))
    body = admin.get("/ai/history").data.decode("utf-8", "replace")
    assert "HISTORY-MARKER-42" in body


# ── visit context: role gate, and the branch gate that was never armed ───────

@pytest.fixture
def visit(app, patient):
    with app.app_context():
        vid = _exec("INSERT INTO visits (owner_id, pet_id, visit_date, doctor_name,"
                    " chief_complaint, branch_id, status)"
                    " VALUES (?,?,?,?,?,?,?)",
                    (patient["owner_id"], patient["pet_id"],
                     date.today().isoformat(), "Dr House", "limping", 1, "Open"))
        return vid


def test_context_visit_refuses_a_non_clinical_role(client, visit):
    _become(client, "reception")
    r = client.get(f"/ai/context/visit/{visit}")
    assert r.status_code == 403
    assert r.get_json()["error"] == "Access denied"


def test_context_visit_returns_the_patient_to_a_doctor(client, visit, patient):
    _become(client, "doctor", full_name="Dr House", branch_id=1)
    r = client.get(f"/ai/context/visit/{visit}")
    assert r.status_code == 200
    assert patient["pet_name"] in r.get_json()["context"]


def test_context_visit_branch_guard_blocks_a_doctor_from_another_branch(
        app, client, patient):
    """The guard reads visits.branch_id. If the column name ever drifts the
    `except Exception: pass` fallback lets every branch through."""
    with app.app_context():
        vid = _exec("INSERT INTO visits (owner_id, pet_id, visit_date, branch_id)"
                    " VALUES (?,?,?,?)",
                    (patient["owner_id"], patient["pet_id"],
                     date.today().isoformat(), 7))
    _become(client, "doctor", full_name="Dr Elsewhere", branch_id=1)
    r = client.get(f"/ai/context/visit/{vid}")
    assert r.status_code == 403, (
        "a doctor in branch 1 read a visit belonging to branch 7")


# ── remaining AI endpoints ───────────────────────────────────────────────────

def test_pet_summary_404s_for_a_pet_that_does_not_exist(admin, fake_ai):
    fake_ai("summary")
    r = _post_json(admin, "/ai/pet-summary/99999999", {})
    assert r.status_code == 404


def test_pet_summary_sends_the_real_patient_to_the_model(admin, fake_ai, patient):
    comp = fake_ai("A professional summary.")
    body = _post_json(admin, f"/ai/pet-summary/{patient['pet_id']}", {}).get_json()
    assert body["summary"] == "A professional summary."
    assert body["pet_name"] == patient["pet_name"]
    assert patient["pet_name"] in _prompt_of(comp)


def test_draft_message_includes_the_named_client(admin, fake_ai, patient):
    comp = fake_ai("Hello!")
    body = _post_json(admin, "/ai/draft-message",
                      {"context": "vaccine due",
                       "owner_id": patient["owner_id"], "lang": "ar"}).get_json()
    assert body["message"] == "Hello!"
    sent = _prompt_of(comp)
    assert "Test Owner" in sent
    assert "Write in Arabic." in sent


def test_nl_report_rejects_an_empty_query(admin, fake_ai):
    fake_ai("{}")
    assert _post_json(admin, "/ai/nl-report", {"query": ""}).status_code == 400


def test_nl_report_returns_the_parsed_config(admin, fake_ai):
    fake_ai('Sure! {"source":"invoices","date_from":"2026-01-01","date_to":"2026-01-31"}')
    body = _post_json(admin, "/ai/nl-report",
                      {"query": "invoices last January"}).get_json()
    assert body["source"] == "invoices"
    assert body["date_from"] == "2026-01-01"


def test_analyze_photo_rejects_a_request_with_no_image(admin, fake_ai):
    fake_ai("x")
    r = _post_json(admin, "/ai/analyze-photo", {"image_b64": ""})
    assert r.status_code == 400


def test_analyze_photo_forwards_the_image_as_a_data_uri(admin, fake_ai):
    comp = fake_ai("Visual findings: none.")
    body = _post_json(admin, "/ai/analyze-photo",
                      {"image_b64": "QUJD", "mime": "image/png"}).get_json()
    assert body["analysis"] == "Visual findings: none."
    assert "data:image/png;base64,QUJD" in _prompt_of(comp)


def test_analyze_photo_reports_the_failure_instead_of_inventing_findings(admin):
    """_no_network in force — the route must 500 with an error, never a summary."""
    r = _post_json(admin, "/ai/analyze-photo", {"image_b64": "QUJD"})
    assert r.status_code == 500
    assert "error" in r.get_json()
    assert "analysis" not in r.get_json()


def test_discharge_instructions_404s_for_an_unknown_visit(admin, fake_ai):
    fake_ai("x")
    assert _post_json(admin, "/ai/discharge-instructions/99999999",
                      {}).status_code == 404


def test_discharge_instructions_carry_the_recorded_diagnosis(app, admin, fake_ai,
                                                             visit, patient):
    with app.app_context():
        _exec("INSERT INTO diagnoses (visit_id, pet_id, diagnosis) VALUES (?,?,?)",
              (visit, patient["pet_id"], "Otitis externa"))
    comp = fake_ai("**ENGLISH VERSION** rest at home")
    body = _post_json(admin, f"/ai/discharge-instructions/{visit}", {}).get_json()
    assert body["diagnosis"] == "Otitis externa"
    assert body["pet_name"] == patient["pet_name"]
    assert "Otitis externa" in _prompt_of(comp)


# ═════════════════════════════════════════════════════════════════════════════
# PUBLIC API — unauthenticated by design
# ═════════════════════════════════════════════════════════════════════════════

def test_public_health_is_open(client):
    body = client.get("/api/public/health").get_json()
    assert body == {"ok": True, "service": "Aleefy API"}


def test_public_services_exposes_price_list_and_nothing_else(app, client):
    with app.app_context():
        expected = _scalar("SELECT COUNT(*) FROM service_catalog")
    rows = client.get("/api/public/services").get_json()
    assert isinstance(rows, list)
    assert len(rows) == expected
    if rows:
        assert set(rows[0]) == {"id", "name", "standard_price", "category"}, (
            "the public price list leaked additional columns")


def test_public_options_preflight_returns_cors_headers(client):
    """`options_handler` covers the sub-paths Flask has no other rule for.
    Rules that exist (like /book) are answered by Flask's automatic OPTIONS,
    which still passes through the blueprint's CORS after_request."""
    r = client.open("/api/public/anything/at/all", method="OPTIONS")
    assert r.status_code == 204
    assert r.headers["Access-Control-Allow-Origin"]
    assert "POST" in r.headers["Access-Control-Allow-Methods"]

    auto = client.open("/api/public/book", method="OPTIONS")
    assert auto.status_code == 200
    assert auto.headers["Access-Control-Allow-Origin"]


def test_public_book_rejects_incomplete_input_and_writes_nothing(app, client):
    with app.app_context():
        before = _scalar("SELECT COUNT(*) FROM appointments")
    r = client.post("/api/public/book", json={"ownerName": "X"})
    assert r.status_code == 400
    assert "mobile" in r.get_json()["error"]
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM appointments") == before


def test_public_book_creates_owner_pet_and_pending_appointment(app, client):
    phone = f"0111{int(time.time() * 1000) % 10_000_000:07d}"
    when = (date.today() + timedelta(days=3)).isoformat()
    r = client.post("/api/public/book", json={
        "ownerName": "Website Walk-in", "mobile": phone,
        "petName": "Booked", "date": when, "time": "11:30",
        "species": "Dog", "reason": "vaccination", "service": "Vaccination",
        "branch": "Nasr City",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert set(body) == {"ok", "booking_id", "message"}, (
        "the public booking response leaked clinic data")

    with app.app_context():
        appt = _conn().execute("SELECT * FROM appointments WHERE id=?",
                               (body["booking_id"],)).fetchone()
        assert appt is not None, "booking returned an id for a row that is not there"
        assert appt["status"] == "Pending"
        assert appt["channel"] == "Website"
        assert appt["created_by"] == "website"
        assert appt["appointment_type"] == "Vaccination"
        assert appt["appt_date"] == when
        assert appt["appt_start"] == "11:30"
        assert "vaccination" in (appt["notes"] or "")
        assert "Nasr City" in (appt["notes"] or ""), (
            "the branch the client picked was dropped on the floor")
        owner = _conn().execute("SELECT * FROM owners WHERE id=?",
                                (appt["owner_id"],)).fetchone()
        assert owner["phone"] == phone
        assert owner["created_by"] == "website"
        pet = _conn().execute("SELECT * FROM pets WHERE id=?",
                              (appt["pet_id"],)).fetchone()
        assert pet["pet_name"] == "Booked"
        assert pet["species"] == "Dog"


def test_public_book_twice_reuses_the_same_owner_and_pet(app, client):
    phone = f"0112{int(time.time() * 1000) % 10_000_000:07d}"
    payload = {"ownerName": "Repeat Client", "mobile": phone,
               "petName": "Rex", "date": date.today().isoformat()}
    first = client.post("/api/public/book", json=payload).get_json()
    second = client.post("/api/public/book", json=payload).get_json()
    assert first["booking_id"] != second["booking_id"]
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM owners WHERE phone=?", (phone,)) == 1
        oid = _scalar("SELECT owner_id FROM appointments WHERE id=?",
                      (first["booking_id"],))
        assert _scalar("SELECT COUNT(*) FROM pets WHERE owner_id=? AND pet_name=?",
                       (oid, "Rex")) == 1


def test_public_book_queues_a_whatsapp_reminder_when_opted_in(app, client):
    phone = f"0113{int(time.time() * 1000) % 10_000_000:07d}"
    when = (date.today() + timedelta(days=2)).isoformat()
    body = client.post("/api/public/book", json={
        "ownerName": "Opted In", "mobile": phone, "petName": "Milo",
        "date": when, "time": "09:00",
        "reminder": "WhatsApp reminder", "whatsappOptIn": "Yes",
    }).get_json()
    with app.app_context():
        rem = _conn().execute(
            "SELECT * FROM reminders WHERE appointment_id=?",
            (body["booking_id"],)).fetchone()
        assert rem is not None, "opted-in booking queued no reminder"
        assert rem["status"] == "Pending"
        assert rem["scheduled_for"] == f"{when} 09:00:00"
        assert "Milo" in rem["message"]


def test_public_book_without_opt_in_queues_no_reminder(app, client):
    phone = f"0114{int(time.time() * 1000) % 10_000_000:07d}"
    body = client.post("/api/public/book", json={
        "ownerName": "No Consent", "mobile": phone, "petName": "Sam",
        "date": date.today().isoformat(), "reminder": "WhatsApp reminder",
        "whatsappOptIn": "No",
    }).get_json()
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM reminders WHERE appointment_id=?",
                       (body["booking_id"],)) == 0


def test_public_contact_stores_the_message(app, client):
    marker = f"contact-{int(time.time() * 1000)}"
    r = client.post("/api/public/contact", json={
        "name": "Site Visitor", "mobile": "01000000000", "message": marker,
        "email": "v@example.com", "branch": "Main"})
    assert r.get_json()["ok"] is True
    with app.app_context():
        row = _conn().execute(
            "SELECT * FROM contact_messages WHERE message=?", (marker,)).fetchone()
        assert row is not None
        assert row["name"] == "Site Visitor"
        assert row["branch"] == "Main"


def test_public_contact_requires_all_three_fields(app, client):
    r = client.post("/api/public/contact", json={"name": "x"})
    assert r.status_code == 400
    for field in ("mobile", "message"):
        assert field in r.get_json()["error"]


def test_public_emergency_creates_a_same_day_emergency_appointment(app, client):
    phone = f"0115{int(time.time() * 1000) % 10_000_000:07d}"
    r = client.post("/api/public/emergency", json={
        "ownerName": "Panicking Owner", "mobile": phone,
        "description": "hit by a car", "petName": "Bolt"})
    assert r.get_json()["ok"] is True
    with app.app_context():
        oid = _scalar("SELECT id FROM owners WHERE phone=?", (phone,))
        appt = _conn().execute(
            "SELECT * FROM appointments WHERE owner_id=? ORDER BY id DESC LIMIT 1",
            (oid,)).fetchone()
        assert appt["status"] == "Emergency"
        assert appt["appt_date"] == date.today().isoformat()
        assert appt["notes"] == "hit by a car"
        assert appt["channel"] == "Website"
        assert _scalar("SELECT pet_name FROM pets WHERE id=?",
                       (appt["pet_id"],)) == "Bolt"


def test_public_emergency_without_a_pet_name_is_still_recorded(app, client):
    """appointments.pet_id is NOT NULL. A caller who does not name the animal
    must not lose the whole emergency to an integrity error."""
    phone = f"0116{int(time.time() * 1000) % 10_000_000:07d}"
    r = client.post("/api/public/emergency", json={
        "ownerName": "No Pet Name", "mobile": phone,
        "description": "collapsed, breathing badly"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
    with app.app_context():
        oid = _scalar("SELECT id FROM owners WHERE phone=?", (phone,))
        appt = _conn().execute(
            "SELECT * FROM appointments WHERE owner_id=? ORDER BY id DESC LIMIT 1",
            (oid,)).fetchone()
        assert appt is not None, "the emergency was lost"
        assert appt["pet_id"] is not None
        assert appt["status"] == "Emergency"


def test_public_emergency_requires_a_description(app, client):
    r = client.post("/api/public/emergency",
                    json={"ownerName": "x", "mobile": "0100"})
    assert r.status_code == 400
    assert "description" in r.get_json()["error"]


def test_public_endpoints_cannot_read_or_modify_existing_clinic_data(app, client,
                                                                     patient):
    """The public surface is write-plus-price-list. Nothing on it returns an
    owner, a pet or an invoice, and nothing on it updates an existing row."""
    with app.app_context():
        name_before = _scalar("SELECT full_name FROM owners WHERE id=?",
                              (patient["owner_id"],))
    # Booking against an existing phone must reuse, never rename.
    client.post("/api/public/book", json={
        "ownerName": "ATTACKER OVERWRITE", "mobile": patient["phone"],
        "petName": patient["pet_name"], "date": date.today().isoformat()})
    with app.app_context():
        assert _scalar("SELECT full_name FROM owners WHERE id=?",
                       (patient["owner_id"],)) == name_before

    # There is no public read path for owners/pets/invoices. 405 comes from the
    # catch-all OPTIONS rule, which accepts no other method.
    for path in ("/api/public/owners", "/api/public/pets", "/api/public/invoices"):
        assert client.get(path).status_code in (404, 405)


def test_public_book_is_blocked_for_a_rate_limited_ip_and_writes_nothing(app, client):
    """`_check_rate_limit()` reads models.security.is_rate_limited, whose counters
    live in `login_attempts`. Seed a lockout for the test client's IP and the
    booking must be refused before it touches the database."""
    from models.security import RATE_LIMIT_MAX, _ensure_tables
    with app.app_context():
        _ensure_tables()
        now = time.time()
        for _ in range(RATE_LIMIT_MAX):
            _exec("INSERT INTO login_attempts (ip, username, ts) VALUES (?,?,?)",
                  ("127.0.0.1", "", now))
        before = _scalar("SELECT COUNT(*) FROM appointments")
    try:
        r = client.post("/api/public/book", json={
            "ownerName": "Flooder", "mobile": "01099999999",
            "petName": "Bot", "date": date.today().isoformat()})
        assert r.status_code == 429
        assert r.get_json()["ok"] is False
        with app.app_context():
            assert _scalar("SELECT COUNT(*) FROM appointments") == before
    finally:
        with app.app_context():
            _exec("DELETE FROM login_attempts WHERE ip='127.0.0.1'")


def test_public_traffic_does_not_feed_its_own_rate_limiter(app, client):
    """KNOWN GAP, pinned deliberately.

    `login_attempts` is written only by `record_failed_login`. A flood of public
    bookings therefore never increments the counter the public endpoints check,
    so /api/public/* is effectively unthrottled. This test asserts the behaviour
    as it is; if real throttling is added it will fail and must be updated.
    """
    from models.security import _ensure_tables
    with app.app_context():
        _ensure_tables()
        before = _scalar("SELECT COUNT(*) FROM login_attempts WHERE ip='127.0.0.1'")
    for i in range(12):
        r = client.post("/api/public/contact", json={
            "name": "flood", "mobile": "01000000000", "message": f"m{i}"})
        assert r.status_code == 200, f"call {i} was throttled — update this test"
    with app.app_context():
        assert _scalar(
            "SELECT COUNT(*) FROM login_attempts WHERE ip='127.0.0.1'") == before


# ═════════════════════════════════════════════════════════════════════════════
# UPLOADS — extension whitelist, magic bytes, traversal, access matrix
# ═════════════════════════════════════════════════════════════════════════════

def _upload(client, data, filename, entity_type="pet", entity_id=1,
            content_type="image/png"):
    return _post(client, "/uploads/upload", {
        "entity_type": entity_type, "entity_id": str(entity_id),
        "category": "general", "caption": "c",
        "file": (BytesIO(data), filename, content_type),
    }, content_type="multipart/form-data")


def _attach_count(entity_id):
    return _scalar("SELECT COUNT(*) FROM attachments WHERE entity_id=?",
                   (str(entity_id),))


def test_upload_stores_a_real_png_on_disk_and_in_the_database(app, admin):
    eid = 900001
    with app.app_context():
        _exec("DELETE FROM attachments WHERE entity_id=?", (str(eid),))
    _upload(admin, PNG_1PX, "scan.png", entity_id=eid)
    with app.app_context():
        row = _conn().execute("SELECT * FROM attachments WHERE entity_id=?",
                              (str(eid),)).fetchone()
        assert row is not None, "upload returned a redirect but wrote no row"
        assert row["mime_type"] == "image/png"
        assert row["size_bytes"] == len(PNG_1PX)
        assert row["original_name"] == "scan.png"
        assert "/" not in row["filename"] and "\\" not in row["filename"]
        path = os.path.join(app.config["UPLOADS_PATH"], "pet", row["filename"])
        assert os.path.exists(path)
        assert open(path, "rb").read() == PNG_1PX


def test_upload_refuses_an_executable_extension(app, admin):
    eid = 900002
    _upload(admin, b"MZ\x90\x00", "payload.exe", entity_id=eid)
    with app.app_context():
        assert _attach_count(eid) == 0


def test_upload_refuses_a_pdf_wearing_a_png_extension(app, admin):
    eid = 900003
    _upload(admin, b"%PDF-1.4\n%stuff", "not-really.png", entity_id=eid)
    with app.app_context():
        assert _attach_count(eid) == 0, (
            "magic-byte validation let a PDF through as a PNG")


def test_upload_refuses_an_entity_type_outside_the_whitelist(app, admin):
    for bad in ("../../etc", "pet/../..", "unknown"):
        r = _post(admin, "/uploads/upload", {
            "entity_type": bad, "entity_id": "900004",
            "file": (BytesIO(PNG_1PX), "x.png", "image/png"),
        }, content_type="multipart/form-data")
        assert r.status_code == 400
        assert r.get_json()["error"] == "Invalid entity type"
    with app.app_context():
        assert _attach_count(900004) == 0


def test_upload_is_refused_for_a_role_outside_the_entity_access_list(app, client):
    """pharmacist is in no _ACCESS list; a staff-file upload must be refused."""
    _become(client, "pharmacist")
    r = _post(client, "/uploads/upload", {
        "entity_type": "staff", "entity_id": "900005",
        "file": (BytesIO(PNG_1PX), "x.png", "image/png"),
    }, content_type="multipart/form-data")
    assert r.status_code == 403
    with app.app_context():
        assert _attach_count(900005) == 0


@pytest.fixture
def stored_file(app, admin):
    """One real attachment per entity_type, uploaded through the route."""
    made = {}
    with app.app_context():
        for i, etype in enumerate(("visit", "staff", "invoice")):
            eid = 910000 + i
            _exec("DELETE FROM attachments WHERE entity_id=?", (str(eid),))
            _upload(admin, PNG_1PX, f"{etype}.png", entity_type=etype, entity_id=eid)
            row = _conn().execute("SELECT * FROM attachments WHERE entity_id=?",
                                  (str(eid),)).fetchone()
            assert row is not None, f"could not stage a {etype} attachment"
            made[etype] = {"id": row["id"], "entity_id": eid,
                           "filename": row["filename"]}
    return made


@pytest.mark.parametrize("etype,role,allowed", [
    ("visit",   "doctor",      True),
    ("visit",   "nurse",       True),
    ("visit",   "reception",   False),   # reception has no clinical file access
    ("visit",   "pharmacist",  False),
    ("staff",   "hr",          True),
    ("staff",   "doctor",      False),   # HR files are not clinical files
    ("invoice", "finance",     True),
    ("invoice", "reception",   True),
    ("invoice", "nurse",       False),
])
def test_serve_enforces_the_per_role_access_matrix(client, stored_file,
                                                   etype, role, allowed):
    _become(client, role)
    r = client.get(f"/uploads/file/{stored_file[etype]['id']}")
    if allowed:
        assert r.status_code == 200, f"{role} was denied a {etype} file it owns"
        assert r.data == PNG_1PX
    else:
        assert r.status_code == 403, f"{role} downloaded a {etype} file it must not see"


def test_serve_404s_for_an_attachment_that_does_not_exist(admin):
    assert admin.get("/uploads/file/99999999").status_code == 404


def test_serve_refuses_a_traversal_filename_planted_in_the_database(app, admin):
    with app.app_context():
        aid = _exec("INSERT INTO attachments (entity_type, entity_id, filename,"
                    " original_name, mime_type) VALUES (?,?,?,?,?)",
                    ("pet", "920001", "../../platform.db", "x.db", "application/x-sqlite3"))
    r = admin.get(f"/uploads/file/{aid}")
    assert r.status_code == 400, "a traversal path stored in the DB was served"
    with app.app_context():
        _exec("DELETE FROM attachments WHERE id=?", (aid,))


def test_list_attachments_is_empty_for_a_role_without_access(client, stored_file):
    _become(client, "reception")
    assert client.get(f"/uploads/list/visit/{stored_file['visit']['entity_id']}"
                      ).get_json() == []


def test_list_attachments_returns_the_file_for_an_allowed_role(client, stored_file):
    _become(client, "doctor")
    rows = client.get(
        f"/uploads/list/visit/{stored_file['visit']['entity_id']}").get_json()
    assert [r["id"] for r in rows] == [stored_file["visit"]["id"]]


def test_list_attachments_rejects_an_unknown_entity_type(admin):
    assert admin.get("/uploads/list/secrets/1").get_json() == []


def test_delete_by_a_disallowed_role_leaves_the_file_and_the_row(app, client,
                                                                 stored_file):
    att = stored_file["visit"]
    path = os.path.join(app.config["UPLOADS_PATH"], "visit", att["filename"])
    _become(client, "reception")
    _post(client, f"/uploads/delete/{att['id']}")
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM attachments WHERE id=?",
                       (att["id"],)) == 1, "reception deleted a clinical attachment"
    assert os.path.exists(path)


def test_delete_by_an_allowed_role_removes_the_row_and_the_file(app, admin,
                                                                stored_file):
    att = stored_file["invoice"]
    path = os.path.join(app.config["UPLOADS_PATH"], "invoice", att["filename"])
    assert os.path.exists(path)
    _post(admin, f"/uploads/delete/{att['id']}")
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM attachments WHERE id=?",
                       (att["id"],)) == 0
    assert not os.path.exists(path), "the row went but the bytes stayed on disk"


# ═════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def other_user(app):
    """A second real user row. notifications.recipient_id is a real FK."""
    with app.app_context():
        uid = _scalar("SELECT id FROM users WHERE username='notif_other'")
        if uid is None:
            uid = _exec("INSERT INTO users (username, password_hash, full_name, role)"
                        " VALUES (?,?,?,?)",
                        ("notif_other", "x", "Other User", "nurse"))
        return uid


@pytest.fixture
def notifs(app, admin_id, other_user):
    other = other_user
    with app.app_context():
        _exec("DELETE FROM notifications WHERE recipient_id IN (?,?)",
              (admin_id, other))
        mine = [_exec("INSERT INTO notifications (recipient_id, title, is_read)"
                      " VALUES (?,?,0)", (admin_id, f"N{i}")) for i in range(3)]
        theirs = _exec("INSERT INTO notifications (recipient_id, title, is_read)"
                       " VALUES (?,?,0)", (other, "NotYours"))
    yield {"mine": mine, "theirs": theirs, "other": other}
    with app.app_context():
        _exec("DELETE FROM notifications WHERE recipient_id IN (?,?)",
              (admin_id, other))


def test_api_unread_counts_only_this_users_notifications(app, admin, notifs):
    body = admin.get("/notifications/api/unread").get_json()
    assert body["count"] == 3
    assert {i["title"] for i in body["items"]} == {"N0", "N1", "N2"}


def test_mark_read_flips_exactly_one_row(app, admin, admin_id, notifs):
    r = _post(admin, f"/notifications/mark-read/{notifs['mine'][0]}")
    assert r.get_json() == {"ok": True}
    with app.app_context():
        assert _scalar("SELECT is_read FROM notifications WHERE id=?",
                       (notifs["mine"][0],)) == 1
        assert _scalar("SELECT COUNT(*) FROM notifications WHERE recipient_id=?"
                       " AND is_read=0", (admin_id,)) == 2


def test_mark_read_cannot_touch_another_users_notification(app, admin, notifs):
    r = _post(admin, f"/notifications/mark-read/{notifs['theirs']}")
    assert r.get_json() == {"ok": True}      # the route always claims success
    with app.app_context():
        assert _scalar("SELECT is_read FROM notifications WHERE id=?",
                       (notifs["theirs"],)) == 0, (
            "one user marked another user's notification as read")


def test_mark_all_read_clears_only_the_callers_notifications(app, admin, notifs):
    _post(admin, "/notifications/mark-all-read")
    with app.app_context():
        assert admin.get("/notifications/api/unread").get_json()["count"] == 0
        assert _scalar("SELECT is_read FROM notifications WHERE id=?",
                       (notifs["theirs"],)) == 0


# ═════════════════════════════════════════════════════════════════════════════
# SETTINGS
# ═════════════════════════════════════════════════════════════════════════════

def test_set_lang_switches_the_session_language(admin):
    admin.post("/settings/lang", data={"lang": "ar", "next": "/"})
    with admin.session_transaction() as s:
        assert s["lang"] == "ar"
        assert s["user"]["language"] == "ar"
    admin.post("/settings/lang", data={"lang": "en", "next": "/"})
    with admin.session_transaction() as s:
        assert s["lang"] == "en"


def test_set_lang_normalises_an_unknown_language_to_english(admin):
    admin.post("/settings/lang", data={"lang": "fr"})
    with admin.session_transaction() as s:
        assert s["lang"] == "en"


def test_set_lang_does_not_persist_to_the_user_row(app, admin, admin_id):
    """KNOWN GAP, pinned. /settings/theme writes users.theme_preference;
    /settings/lang writes only the session, so the choice is lost at logout."""
    with app.app_context():
        before = _scalar("SELECT language FROM users WHERE id=?", (admin_id,))
    admin.post("/settings/lang", data={"lang": "ar"})
    with app.app_context():
        assert _scalar("SELECT language FROM users WHERE id=?",
                       (admin_id,)) == before
    admin.post("/settings/lang", data={"lang": "en"})


def test_set_lang_redirects_to_the_supplied_next_page(admin):
    r = admin.post("/settings/lang", data={"lang": "en", "next": "/reports/"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/reports/")


# ═════════════════════════════════════════════════════════════════════════════
# LAUNCHER
# ═════════════════════════════════════════════════════════════════════════════

def test_coming_soon_renders_the_requested_module(admin):
    r = admin.get("/coming-soon?module=Radiology&icon=X&eta=Q4+2026"
                  "&feature=DICOM&feature=PACS")
    assert r.status_code == 200
    body = r.data.decode("utf-8", "replace")
    assert "Radiology" in body and "Q4 2026" in body
    assert "DICOM" in body and "PACS" in body


def test_open_module_redirects_to_the_platform_stub(admin):
    r = admin.get("/module/examination")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/module/examination/stub")


def test_open_module_writes_an_audit_row(app, admin):
    before = _scalar("SELECT COUNT(*) FROM audit_log WHERE action='open_module'"
                     " AND module='crm'")
    admin.get("/module/crm")
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM audit_log WHERE action='open_module'"
                       " AND module='crm'") == before + 1


def test_open_module_404s_for_an_unknown_module(admin):
    assert admin.get("/module/there-is-no-such-module").status_code == 404


def test_open_module_refuses_a_role_the_module_does_not_list(client):
    mod = next(m for m in launcher_routes.MODULES
               if "groomer" not in m["roles"] and not m.get("legacy"))
    _become(client, "groomer")
    r = client.get(f"/module/{mod['id']}")
    assert r.status_code == 302
    assert not r.headers["Location"].endswith("/stub"), (
        f"groomer reached {mod['id']}, which lists roles {mod['roles']}")


def test_module_stub_renders(admin):
    assert admin.get("/module/examination/stub").status_code == 200


def test_legacy_ping_reports_the_port_state(admin, monkeypatch):
    monkeypatch.setattr(launcher_routes, "_legacy_port_open", lambda port=5000: True)
    assert admin.get("/launcher/legacy/ping").get_json() == {"up": True}
    monkeypatch.setattr(launcher_routes, "_legacy_port_open", lambda port=5000: False)
    assert admin.get("/launcher/legacy/ping").get_json() == {"up": False}


def test_launch_legacy_does_not_spawn_a_process_when_the_port_is_open(
        app, admin, monkeypatch):
    monkeypatch.setattr(launcher_routes, "_legacy_port_open", lambda port=5000: True)

    def _no_popen(*a, **kw):
        raise AssertionError("launch_legacy spawned a process for a live port")
    monkeypatch.setattr(launcher_routes.subprocess, "Popen", _no_popen)

    r = admin.get("/launcher/legacy/start")
    assert r.status_code == 302
    assert r.headers["Location"].startswith(
        app.config.get("LEGACY_APP_URL", "http://localhost:5000"))


# ═════════════════════════════════════════════════════════════════════════════
# DOCTOR WORKSPACE
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def todays_appt(app, patient):
    with app.app_context():
        aid = _exec(
            "INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
            " doctor_name, status) VALUES (?,?,?,?,?,?)",
            (patient["owner_id"], patient["pet_id"], date.today().isoformat(),
             "14:00", "Dr Queue Test", "Scheduled"))
        return {"id": aid, **patient}


def test_doctor_queue_shows_todays_appointment_for_its_doctor(client, todays_appt):
    """The queue was empty for the module's entire life. Pin it with a real row."""
    _become(client, "doctor", full_name="Dr Queue Test")
    body = client.get("/doctor/queue").data.decode("utf-8", "replace")
    assert todays_appt["pet_name"] in body, (
        "today's appointment did not appear in its own doctor's queue")


def test_doctor_queue_hides_another_doctors_appointment(client, todays_appt):
    _become(client, "doctor", full_name="Dr Somebody Else")
    body = client.get("/doctor/queue").data.decode("utf-8", "replace")
    assert todays_appt["pet_name"] not in body


def test_doctor_workspace_counts_todays_appointments(client, todays_appt):
    _become(client, "doctor", full_name="Dr Queue Test")
    body = client.get("/doctor/").data.decode("utf-8", "replace")
    assert todays_appt["pet_name"] in body


def test_checkin_moves_the_appointment_to_in_progress(app, admin, todays_appt):
    with app.app_context():
        assert _scalar("SELECT status FROM appointments WHERE id=?",
                       (todays_appt["id"],)) == "Scheduled"
    r = _post(admin, f"/doctor/appointment/{todays_appt['id']}/checkin")
    assert r.status_code == 302
    with app.app_context():
        assert _scalar("SELECT status FROM appointments WHERE id=?",
                       (todays_appt["id"],)) == "In Progress", (
            "check-in redirected but the appointment status never changed")


def test_checkin_honours_the_next_parameter(admin, todays_appt):
    r = _post(admin, f"/doctor/appointment/{todays_appt['id']}/checkin",
              {"next": "/doctor/"})
    assert r.headers["Location"].endswith("/doctor/")


def test_checkin_of_an_unknown_appointment_changes_nothing(app, admin):
    """KNOWN GAP, pinned: the route UPDATEs blind and flashes success even when
    the id matches no row."""
    with app.app_context():
        before = _scalar("SELECT COUNT(*) FROM appointments WHERE status='In Progress'")
    r = _post(admin, "/doctor/appointment/99999999/checkin")
    assert r.status_code == 302
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM appointments "
                       "WHERE status='In Progress'") == before


def test_quick_visit_redirects_to_the_visit_detail_page(admin, visit):
    r = admin.get(f"/doctor/visit/{visit}/quick")
    assert r.status_code == 302
    assert r.headers["Location"].endswith(f"/visits/{visit}")


# ═════════════════════════════════════════════════════════════════════════════
# PETSY WIDGET
# ═════════════════════════════════════════════════════════════════════════════

def test_petsy_embed_renders_without_a_session(client):
    r = client.get("/petsy/embed")
    assert r.status_code == 200
    assert b"<" in r.data


def test_petsy_embed_knows_whether_a_staff_member_is_logged_in(admin):
    assert admin.get("/petsy/embed").status_code == 200


def test_petsy_widget_js_is_served_as_javascript_for_any_origin(client):
    r = client.get("/petsy/widget.js")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/javascript")
    assert r.headers["Access-Control-Allow-Origin"] == "*"
    assert "max-age=3600" in r.headers["Cache-Control"]
    body = r.data.decode("utf-8", "replace")
    assert "http://localhost" in body, "the widget carries no callback base URL"
