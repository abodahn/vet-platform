# -*- coding: utf-8 -*-
"""The one-page visit flow.

The page itself writes nothing: it POSTs to the existing routes, the same chain
tests/test_full_cycle.py drives end to end. What this file covers is the part
that is new — the read endpoints the page navigates by, and the guarantee that
the sequence it depends on still holds from a single screen.

The read endpoints matter more than they look. The page re-reads server state
after every write instead of trusting what it just sent, because
complete_visit() refuses a visit with no diagnosis — and discovering a diagnosis
had silently failed to save at the invoice step would waste a consultation.
"""
import json

import pytest

import models.database as db


def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=True)


@pytest.fixture()
def vet(app, client):
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


# ── the page ─────────────────────────────────────────────────────────────────

def test_the_page_renders_all_six_steps(client, vet):
    html = client.get("/workflow/").get_data(as_text=True)
    assert html.count('class="wf-step') >= 6, "the stepper is not rendered"
    for panel in ("p1", "p2", "p3", "p4", "p5", "p6"):
        assert f'id="{panel}"' in html, f"step panel {panel} is missing"


def test_the_page_uses_the_csrf_field_the_app_actually_validates(client, vet):
    """The app validates `_csrf_token`, not `csrf_token`. That mismatch has
    caused three separate silent-403 bugs in this codebase, and on this page it
    would make every step fail with no visible reason."""
    html = client.get("/workflow/").get_data(as_text=True)
    assert 'body.set("_csrf_token", CSRF)' in html


def test_payment_methods_come_from_the_registry(client, vet):
    """So a newly registered gateway appears here too, rather than needing this
    template edited."""
    from models import payments
    html = client.get("/workflow/").get_data(as_text=True)
    with client.application.app_context():
        for gw in payments.available():
            assert f'value="{gw.name}"' in html, f"{gw.name} missing from the page"


def test_the_page_requires_login(client):
    r = client.get("/workflow/", follow_redirects=False)
    assert r.status_code == 302 and "/auth/login" in r.headers["Location"]


# ── client search ────────────────────────────────────────────────────────────

def test_owner_search_finds_by_name_and_phone(client, vet, app):
    _post(client, "/crm/owners/new", {
        "full_name": "Workflow Search Owner", "phone": "01099887766",
        "whatsapp_phone": "01099887766"})

    by_name = client.get("/workflow/api/owners?q=Workflow Search").get_json()
    assert any(o["full_name"] == "Workflow Search Owner" for o in by_name)

    by_phone = client.get("/workflow/api/owners?q=01099887766").get_json()
    assert any(o["phone"] == "01099887766" for o in by_phone), \
        "searching by phone found nothing — reception searches by phone"


def test_a_short_query_returns_nothing(client, vet):
    """An empty or one-character query would hand the clinic's entire client
    list to a type-ahead on every keystroke."""
    assert client.get("/workflow/api/owners?q=").get_json() == []
    assert client.get("/workflow/api/owners?q=a").get_json() == []


def test_search_results_carry_a_pet_count(client, vet):
    """"Is this the right Ahmed?" has to be answerable without opening the
    record."""
    rows = client.get("/workflow/api/owners?q=Workflow Search").get_json()
    assert rows and "pet_count" in rows[0]


# ── patient ──────────────────────────────────────────────────────────────────

def test_a_client_with_no_animals_returns_an_empty_list_not_an_error(client, vet, app):
    """The commonest first visit: a new client with nothing registered. The page
    opens the 'new patient' form on this signal, so an error here would dead-end
    the whole flow."""
    _post(client, "/crm/owners/new", {"full_name": "Petless Owner",
                                      "phone": "01055443322"})
    owner = client.get("/workflow/api/owners?q=Petless").get_json()[0]
    data = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()
    assert data["ok"] is True
    assert data["pets"] == []


def test_an_unknown_client_is_a_404_not_a_500(client, vet):
    assert client.get("/workflow/api/owner/999999/pets").status_code == 404


def test_pet_history_surfaces_allergies_before_prescribing(client, vet, app):
    """The page shows this on the EXAMINATION step, before any medication is
    entered. An allergy discovered after the prescription is written is a
    clinical incident."""
    _post(client, "/crm/owners/new", {"full_name": "Allergy Owner",
                                      "phone": "01033221100"})
    owner = client.get("/workflow/api/owners?q=Allergy Owner").get_json()[0]
    _post(client, "/crm/pets/new", {
        "owner_id": owner["id"], "pet_name": "Sensitive", "species": "Cat",
        "allergies": "Penicillin"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]

    hist = client.get(f"/workflow/api/pet/{pet['id']}/history").get_json()
    assert hist["allergies"] == "Penicillin"


# ── the sequence, driven exactly as the page drives it ───────────────────────

def test_the_whole_visit_can_be_completed_from_this_one_page(client, vet, app):
    """Every request below is one the page makes, in the order it makes them.

    If this passes, a receptionist can take a walk-in from unknown client to
    settled invoice without leaving /workflow/.
    """
    # 1. client — new, so created inline
    _post(client, "/crm/owners/new", {
        "full_name": "One Page Owner", "full_name_ar": "صاحب صفحة واحدة",
        "phone": "01077665544", "whatsapp_phone": "01077665544"})
    owner = next(o for o in client.get("/workflow/api/owners?q=01077665544").get_json()
                 if o["phone"] == "01077665544")

    # 2. patient — none registered, so created inline
    assert client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"] == []
    _post(client, "/crm/pets/new", {
        "owner_id": owner["id"], "pet_name": "Rocket", "species": "Dog",
        "breed": "Baladi", "sex": "Male", "weight_kg": "12.4"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]

    # 3. examination
    r = _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"],
        "doctor_name": vet.get("full_name") or "Dr. Test",
        "visit_type": "Consultation", "chief_complaint": "Limping on hind leg",
        "symptoms": "Favours left side", "weight_kg": "12.4", "temp_c": "38.4"})
    assert r.status_code == 200
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()

    # 4. diagnosis — and the page verifies it landed, because complete_visit
    #    refuses without one.
    _post(client, f"/visits/{visit_id}/diagnosis", {
        "diagnosis_text": "Soft tissue strain", "severity": "Mild",
        "diagnosis_notes": "Rest advised"})
    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["diagnoses"], "the diagnosis did not save — step 6 would have refused"

    # 5. treatment
    _post(client, f"/visits/{visit_id}/prescription", {
        "rx_notes": "With food", "medication_name_1": "Meloxicam",
        "dosage_1": "0.5 mg", "frequency_1": "SID", "duration_1": "5 days",
        "quantity_1": "5", "unit_1": "unit", "route_1": "Oral",
        "instructions_1": ""})
    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["prescription"] and v["prescription"][0]["medication_name"] == "Meloxicam"

    # 6. complete -> invoice
    _post(client, f"/visits/{visit_id}/complete", {})
    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["invoice"], "completing the visit raised no invoice"
    inv = v["invoice"]
    assert float(inv["total"]) > 0

    # …and payment, through the ledger.
    _post(client, f"/finance/invoices/{inv['id']}/pay",
          {"amount": f"{float(inv['due_amount']):.2f}", "method": "cash"})

    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["invoice"]["status"] == "Paid", "the invoice did not settle"
    assert float(v["invoice"]["due_amount"]) < 0.005

    with app.app_context():
        conn = db.get_db()
        led = conn.execute("SELECT COUNT(*) c FROM payments WHERE invoice_id=?",
                           (inv["id"],)).fetchone()["c"]
        conn.close()
    assert led == 1, "the payment left no ledger row"


def test_the_visit_endpoint_reports_progress_at_every_stage(client, vet, app):
    """The page navigates by this. If it reported a stage optimistically the
    user would be advanced past a step that had not actually happened."""
    _post(client, "/crm/owners/new", {"full_name": "Progress Owner",
                                      "phone": "01011223399"})
    owner = client.get("/workflow/api/owners?q=01011223399").get_json()[0]
    _post(client, "/crm/pets/new", {"owner_id": owner["id"], "pet_name": "Step",
                                    "species": "Cat"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Consultation",
        "doctor_name": "Dr. Test", "chief_complaint": "Check-up"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()

    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["ok"] and v["diagnoses"] == [] and v["prescription"] == []
    assert v["invoice"] is None, "an invoice exists before the visit was completed"
    assert v["visit"]["pet_name"] == "Step"


def test_an_unknown_visit_is_a_404_not_a_500(client, vet):
    assert client.get("/workflow/api/visit/999999").status_code == 404


# ── access control ───────────────────────────────────────────────────────────

def test_the_workflow_page_is_governed_by_the_visits_permission(app, client):
    """A new blueprint with no permission key falls open. This one is mapped to
    `visits`, so it inherits the rules the clinical module already has."""
    from blueprints.auth.routes import _permission_for
    assert _permission_for("workflow") == "visits"


# ── the drug-interaction list the visit page builds ──────────────────────────

def test_the_interaction_checker_sees_what_the_animal_is_ALREADY_taking(
        client, vet, app):
    """A patient-safety feature that was silently doing nothing.

    visit_detail.html built this list from `rx.items`. The route passes a
    separate `rx_items` dict, and `items` is a dict METHOD — so on PostgreSQL,
    where rows are dict-like, it resolved to the bound method and crashed the
    page with "'method' object is not iterable". On SQLite rows have no such
    attribute, Jinja returned Undefined, the `is defined` guard skipped the
    loop, and the list was ALWAYS EMPTY. The checker therefore compared the new
    drugs only against each other, never against existing medication — which is
    the one thing it exists to do.
    """
    _post(client, "/crm/owners/new", {"full_name": "Interaction Owner",
                                      "phone": "01066554433"})
    owner = client.get("/workflow/api/owners?q=01066554433").get_json()[0]
    _post(client, "/crm/pets/new", {"owner_id": owner["id"], "pet_name": "Mixer",
                                    "species": "Dog"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Consultation",
        "doctor_name": "Dr. Test", "chief_complaint": "Itching"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()

    _post(client, f"/visits/{visit_id}/prescription", {
        "rx_notes": "", "medication_name_1": "Ketoconazole",
        "dosage_1": "1 tab", "frequency_1": "SID", "duration_1": "10 days",
        "quantity_1": "10", "unit_1": "unit", "route_1": "Oral",
        "instructions_1": ""})

    html = client.get(f"/visits/{visit_id}").get_data(as_text=True)
    assert "Ketoconazole" in html
    marker = "var existing = ["
    assert marker in html, "the interaction list is gone from the page"
    block = html[html.index(marker): html.index(marker) + 400]
    assert "Ketoconazole" in block, \
        "the interaction checker cannot see the medication already prescribed"


def test_a_medication_name_with_an_apostrophe_does_not_break_the_page(
        client, vet, app):
    """Bare single quotes round each name meant one apostrophe would terminate
    the JS string and take the rest of the script with it."""
    _post(client, "/crm/owners/new", {"full_name": "Quote Owner",
                                      "phone": "01044556677"})
    owner = client.get("/workflow/api/owners?q=01044556677").get_json()[0]
    _post(client, "/crm/pets/new", {"owner_id": owner["id"], "pet_name": "Tick",
                                    "species": "Cat"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Consultation",
        "doctor_name": "Dr. Test", "chief_complaint": "Check"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()

    _post(client, f"/visits/{visit_id}/prescription", {
        "rx_notes": "", "medication_name_1": "Dexter's Drops",
        "dosage_1": "2", "frequency_1": "BID", "duration_1": "3 days",
        "quantity_1": "1", "unit_1": "unit", "route_1": "Oral",
        "instructions_1": ""})

    html = client.get(f"/visits/{visit_id}").get_data(as_text=True)

    # Parse the array the page emits rather than string-matching it: the only
    # question that matters is whether a browser can evaluate it, and whether
    # the name survived intact.
    start = html.index("var existing = [") + len("var existing = ")
    end = html.index("]", start) + 1
    raw = html[start:end].replace(",]", "]")          # trailing comma is legal JS, not JSON
    names = json.loads(raw)
    assert "Dexter's Drops" in names,         f"the apostrophe broke the medication out of the list: {names}"
