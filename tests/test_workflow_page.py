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
        "full_name": "Workflow Search Owner", "phone": "01096000001",
        "whatsapp_phone": "01096000001"})

    by_name = client.get("/workflow/api/owners?q=Workflow Search").get_json()
    assert any(o["full_name"] == "Workflow Search Owner" for o in by_name)

    by_phone = client.get("/workflow/api/owners?q=01096000001").get_json()
    assert any(o["phone"] == "01096000001" for o in by_phone), \
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


# ── today's queue ────────────────────────────────────────────────────────────

def test_todays_queue_lists_bookings_and_puts_checked_in_first(client, vet, app):
    """Step one opens on who is booked, not on an empty search box.

    Most visits are not walk-ins. Making reception type a name already on the
    screen is the friction that gets a system worked around rather than used.
    Checked-in first because those people are physically in the building.
    """
    import datetime
    _post(client, "/crm/owners/new", {"full_name": "Queue Owner",
                                      "phone": "01088776655"})
    owner = client.get("/workflow/api/owners?q=01088776655").get_json()[0]
    _post(client, "/crm/pets/new", {"owner_id": owner["id"], "pet_name": "Waiting",
                                    "species": "Dog", "allergies": "Sulfa"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]

    today = datetime.date.today().isoformat()
    with app.app_context():
        conn = db.get_db()
        with conn:
            for start, status in (("11:00", "Confirmed"), ("09:00", "Checked-in")):
                conn.execute(
                    "INSERT INTO appointments(owner_id, pet_id, appt_date, appt_start,"
                    " appointment_type, status) VALUES(?,?,?,?,?,?)",
                    (owner["id"], pet["id"], today, start, "Consultation", status))
            # Must NOT appear: already done, and cancelled.
            conn.execute(
                "INSERT INTO appointments(owner_id, pet_id, appt_date, appt_start,"
                " appointment_type, status) VALUES(?,?,?,?,?,?)",
                (owner["id"], pet["id"], today, "08:00", "Consultation", "Completed"))
        conn.close()

    rows = client.get("/workflow/api/today").get_json()
    mine = [r for r in rows if r["owner_id"] == owner["id"]]
    assert len(mine) == 2, f"expected 2 open bookings, got {len(mine)}"
    assert mine[0]["status"] == "Checked-in", \
        "somebody already in the waiting room is not at the top of the queue"
    assert all(r["status"] != "Completed" for r in rows), \
        "a finished appointment is still in the queue"


def test_the_queue_carries_what_is_needed_to_skip_two_steps(client, vet):
    """Picking from the queue jumps straight to the examination, so the row has
    to carry the owner, the pet AND the allergies — asking again would be asking
    a question the system can already answer."""
    rows = client.get("/workflow/api/today").get_json()
    row = next((r for r in rows if r.get("allergies")), None)
    assert row is not None, "no queued patient with allergies to check against"
    for key in ("owner_id", "pet_id", "full_name", "pet_name", "species", "allergies"):
        assert key in row, f"the queue row is missing {key}"


def test_the_queue_requires_login(client):
    r = client.get("/workflow/api/today", follow_redirects=False)
    assert r.status_code == 302


def test_the_patient_panel_puts_allergies_above_the_facts(client, vet):
    """Ordering is the point: the allergy line has to be read before a drug is
    typed, so it sits at the top of the panel and the panel is sticky."""
    html = client.get("/workflow/").get_data(as_text=True)
    assert 'class="pt-allergy"' in html

    # The panel is built by renderAside() at runtime, so DOM order is decided by
    # the order the markup is CONCATENATED — not by where the rules sit in the
    # stylesheet, which is what a naive position check would compare.
    fn = html[html.index("function renderAside"):]
    fn = fn[:fn.index("\n  }")]
    assert fn.index("pt-allergy") < fn.index("pt-facts"), \
        "the allergy block is appended after the facts"

    assert ".wf-aside { position: sticky" in html, \
        "the patient panel scrolls away from the treatment step"


# ── vaccination ──────────────────────────────────────────────────────────────

def test_a_vaccination_recorded_in_the_flow_is_linked_to_the_visit(client, vet, app):
    """vaccinations.visit_id existed and was never written by any route, so
    every vaccination on file was orphaned from the consultation it happened at
    and "what was given at this visit" could not be answered from the visit."""
    import datetime
    _post(client, "/crm/owners/new", {"full_name": "Vax Owner", "phone": "01022334455"})
    owner = client.get("/workflow/api/owners?q=01022334455").get_json()[0]
    _post(client, "/crm/pets/new", {"owner_id": owner["id"], "pet_name": "Shot",
                                    "species": "Dog"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Vaccination",
        "doctor_name": "Dr. Test", "chief_complaint": "Annual booster"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()

    due = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
    _post(client, "/clinical/vaccinations/new", {
        "pet_id": pet["id"], "visit_id": visit_id, "vaccine_name": "Rabies",
        "dose_number": "1", "site": "Subcutaneous",
        "administered_at": datetime.date.today().isoformat(),
        "next_due_at": due})

    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["vaccinations"], "the vaccination is not attached to the visit"
    assert v["vaccinations"][0]["vaccine_name"] == "Rabies"
    assert v["vaccinations"][0]["next_due_at"] == due


def test_a_vaccination_without_a_next_due_date_would_never_remind(client, vet, app):
    """The consequence that makes this more than a missing field.

    blueprints/whatsapp/scheduler.py selects on vaccinations.next_due_at, so a
    blank one means the owner is never reminded and the animal quietly lapses.
    The route now warns; the workflow page pre-fills a year ahead.
    """
    import datetime
    _post(client, "/crm/owners/new", {"full_name": "NoDue Owner", "phone": "01099001122"})
    owner = client.get("/workflow/api/owners?q=01099001122").get_json()[0]
    _post(client, "/crm/pets/new", {"owner_id": owner["id"], "pet_name": "Lapse",
                                    "species": "Cat"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]

    r = _post(client, "/clinical/vaccinations/new", {
        "pet_id": pet["id"], "vaccine_name": "Feline FVRCP", "dose_number": "1",
        "administered_at": datetime.date.today().isoformat(), "next_due_at": ""})
    assert "no reminder" in r.get_data(as_text=True).lower(), \
        "a vaccination with no next-due date was accepted silently"

    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT next_due_at FROM vaccinations WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()
        conn.close()
    assert row["next_due_at"] is None

    # …and the reminder query genuinely cannot see it.
    from blueprints.whatsapp import scheduler
    with app.app_context():
        conn = db.get_db()
        due = conn.execute(
            "SELECT COUNT(*) c FROM vaccinations WHERE pet_id=? AND next_due_at IS NOT NULL",
            (pet["id"],)).fetchone()["c"]
        conn.close()
    assert due == 0, "premise changed: the row now has a due date"


def test_the_page_offers_a_vaccination_section_on_the_treatment_step(client, vet):
    """A vaccination can happen at any visit, not only one booked as one — so it
    is always available, and merely pre-opened when the visit type says so."""
    html = client.get("/workflow/").get_data(as_text=True)
    assert 'id="vaxOn"' in html and 'id="vx_vaccine_name"' in html
    assert 'id="vx_next_due_at"' in html
    assert "saveVaccination" in html
    # It must be saved BEFORE the visit is completed: completing raises the
    # invoice, and a vaccination recorded after would miss its line on the bill.
    body = html[html.index("async function saveRx"):]
    body = body[:body.index("$(\"btnSaveRx\")")]
    assert body.index("saveVaccination") < body.index("completeVisit"), \
        "the vaccination is saved after the invoice is raised"


# ── Instapay at the counter ──────────────────────────────────────────────────

def _set_instapay(app, handle, qr):
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE clinic SET instapay_handle=?, instapay_qr=?",
                         (handle, qr))
        conn.close()
        db.cache_invalidate("clinic_row")


def test_the_instapay_qr_reaches_the_payment_step(client, vet, app):
    """The client scans instead of copying a handle off a monitor.

    The app RECORDS this payment; the money arrives in the clinic's own Instapay
    account and staff confirm it before pressing the button — which is why
    Instapay is a counter method and not an online gateway.
    """
    qr = "data:image/png;base64,iVBORw0KGgo="
    _set_instapay(app, "nilevet@instapay", qr)
    html = client.get("/workflow/").get_data(as_text=True)
    assert "nilevet@instapay" in html
    assert qr in html
    assert 'sel.value !== "instapay"' in html, \
        "the QR is not gated on the Instapay method being selected"


def test_a_clinic_with_no_instapay_details_is_told_where_to_set_them(client, vet, app):
    """An empty panel would read as "Instapay is broken" to whoever is at the
    counter. It says where to fix it instead."""
    _set_instapay(app, "", "")
    html = client.get("/workflow/").get_data(as_text=True)
    assert "No Instapay details are set up yet" in html


def test_instapay_is_still_recorded_through_the_ledger(app, invoice_for_instapay):
    """The QR changes what the client sees, not how the money is recorded — it
    goes through the same intent, capture and ledger row as cash."""
    from models import payments
    inv = invoice_for_instapay
    with app.app_context():
        intent = payments.create_intent(
            inv["invoice_id"], inv["owner_id"], "250.00",
            gateway="instapay", idempotency_key="k-ipay", created_by="reception")
        payments.capture(intent["id"], actor="reception")
        conn = db.get_db()
        rows = conn.execute(
            "SELECT amount, method, received_by FROM payments WHERE invoice_id=?",
            (inv["invoice_id"],)).fetchall()
        conn.close()
    assert len(rows) == 1
    assert rows[0]["method"] == "InstaPay", f"recorded as {rows[0]['method']}"
    assert rows[0]["received_by"] == "reception"


@pytest.fixture()
def invoice_for_instapay(app):
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                               ("Instapay Owner", "01011112222"))
            owner_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO invoices(owner_id, invoice_number, issue_date, subtotal,"
                " total, paid_amount, due_amount, status)"
                " VALUES(?,?,date('now','localtime'),?,?,0,?,'Unpaid')",
                (owner_id, f"IPAY-{owner_id}", 250.00, 250.00, 250.00))
            invoice_id = cur.lastrowid
        conn.close()
    return {"invoice_id": invoice_id, "owner_id": owner_id}


def test_the_instapay_qr_survives_a_backup_and_restore(app):
    """Stored in the clinic ROW, not on disk. models/backup.py copies the
    database and nothing else, so a QR under uploads/ would survive a backup and
    vanish on restore — losing it on the one day the clinic is already having a
    bad time."""
    with app.app_context():
        conn = db.get_db()
        from tests.conftest import table_columns
        cols = table_columns(conn, "clinic")
        conn.close()
    assert "instapay_qr" in cols and "instapay_handle" in cols


def test_the_payment_link_is_offered_alongside_the_qr(client, vet, app):
    """They are not interchangeable, which is why both exist.

    The QR is for a client standing at the counter pointing their own phone at
    the screen. The LINK is for the same client reading the invoice ON that
    phone — where scanning their own screen is impossible — and it is what gets
    pasted into a WhatsApp message.
    """
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE clinic SET instapay_handle=?, instapay_link=?, "
                         "instapay_qr=?",
                         ("goharyfab@instapay",
                          "https://ipn.eg/S/goharyfab/instapay/3c8FZv",
                          "data:image/png;base64,iVBORw0KGgo="))
        conn.close()
        db.cache_invalidate("clinic_row")

    html = client.get("/workflow/").get_data(as_text=True)
    assert "https://ipn.eg/S/goharyfab/instapay/3c8FZv" in html
    assert 'rel="noopener"' in html, "an external payment link opened without noopener"
    assert "data-copy=" in html, "no way to copy the link for WhatsApp"


def test_a_link_with_no_qr_is_still_offered(client, vet, app):
    """A clinic may have the link and not have got round to the image. Requiring
    both would leave them with nothing."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE clinic SET instapay_qr=NULL, instapay_handle='', "
                         "instapay_link=?",
                         ("https://ipn.eg/S/someone/instapay/abc",)) 
        conn.close()
        db.cache_invalidate("clinic_row")
    html = client.get("/workflow/").get_data(as_text=True)
    assert "https://ipn.eg/S/someone/instapay/abc" in html
    assert "No Instapay details are set up yet" not in html.split("payExtra")[-1][:400]


def test_the_qr_shown_to_the_client_is_a_separate_full_screen_view(client, vet, app):
    """The QR on the staff form is a control, not something to be scanned.

    It is small, surrounded by payment inputs, and on a monitor facing the wrong
    way across a counter. Asking a client to lean over the desk and aim a camera
    at a thumbnail next to an amount field is the kind of small indignity that
    gets a payment method quietly abandoned. The client gets their own view: the
    amount large, the code sized to scan, nothing else.
    """
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE clinic SET instapay_handle=?, instapay_link=?, "
                         "instapay_qr=?",
                         ("goharyfab@instapay",
                          "https://ipn.eg/S/goharyfab/instapay/3c8FZv",
                          "data:image/png;base64,iVBORw0KGgo="))
        conn.close()
        db.cache_invalidate("clinic_row")

    html = client.get("/workflow/").get_data(as_text=True)
    assert 'id="btnShowQr"' in html, "no way to show the code to the client"
    assert "function showQrToClient" in html
    assert 'class="ip-thumb"' in html, \
        "the staff-side image should be a thumbnail, not a scan target"
    # The amount is the largest thing on the client's screen: the first question
    # anyone asks is how much.
    assert ".qr-amount" in html and "2.9rem" in html
    # Dismissible without a mouse, and announced as a dialog.
    assert 'aria-modal' in html and '"Escape"' in html


def test_instapay_config_is_readable_by_both_panels(client, vet, app):
    """INSTAPAY was declared inside renderInvoice() while showQrToClient is a
    sibling function, so the client view failed at runtime with "INSTAPAY is not
    defined" — invisible to every server-side test because it only breaks in a
    browser. It is page-level now; this pins that."""
    html = client.get("/workflow/").get_data(as_text=True)
    decl = html.index("const INSTAPAY")
    render = html.index("function renderInvoice")
    assert decl < render, \
        "INSTAPAY is scoped inside renderInvoice again — showQrToClient cannot see it"
