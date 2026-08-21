# -*- coding: utf-8 -*-
"""Three ways the one-page visit flow used to lie to the person using it.

The page writes nothing itself: it POSTs to the same routes a browser form
posts to, and those routes answer a refusal the way a form expects — flash the
reason, redirect. fetch() follows that redirect to a 200, so a refusal reaches
the page looking exactly like a success. Everything below is about the gap
between "the POST returned 200" and "the thing happened".

Two kinds of assertion appear here, deliberately:

  * the server contracts the page navigates by (the redirect carries the new
    id, the permission gate answers 403 to an XHR, a refused prescription
    leaves nothing behind) — these pin the mechanism the fix relies on; and
  * the page source, because the logic being fixed is JavaScript inside the
    template and there is no other way to reach it from pytest.
"""
import re

import pytest

import models.database as db


def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, **kw):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    kw.setdefault("follow_redirects", True)
    return client.post(url, data=payload, **kw)


def _become(client, role, full_name):
    """Put a role in the session. The gate reads the session, not the row."""
    with client.session_transaction() as s:
        s["user"] = {"id": 1, "username": role, "full_name": full_name,
                     "role": role, "language": "en"}
        s["lang"] = "en"


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


@pytest.fixture()
def page(client, vet):
    return client.get("/workflow/").get_data(as_text=True)


def _owner(client, name, phone):
    _post(client, "/crm/owners/new", {"full_name": name, "phone": phone,
                                      "whatsapp_phone": phone})
    return next(o for o in client.get(
        "/workflow/api/owners?q=" + phone).get_json() if o["phone"] == phone)


# ── bug-498: the visit must be filed against the animal that was registered ──

def test_registering_a_patient_redirects_to_it_by_id(client, vet):
    """The page has no other way to know which animal it just created, and
    guessing costs the wrong record a diagnosis."""
    owner = _owner(client, "Wrong Animal Owner", "01098100001")
    r = _post(client, "/crm/pets/new",
              {"owner_id": owner["id"], "pet_name": "Bella", "species": "Dog"},
              follow_redirects=False)
    assert r.status_code == 302
    m = re.search(r"/crm/pets/(\d+)", r.headers["Location"])
    assert m, f"the create route no longer identifies the new pet: {r.headers['Location']}"

    with client.application.app_context():
        conn = db.get_db()
        row = conn.execute("SELECT pet_name FROM pets WHERE id=?",
                           (int(m.group(1)),)).fetchone()
        conn.close()
    assert row["pet_name"] == "Bella"


def test_the_last_pet_in_the_list_is_not_the_newest(client, vet):
    """The trap this replaced. /workflow/api/owner/<id>/pets is ordered by NAME
    — for the picker, where alphabetical is what a human wants — so the last
    row is whichever animal sorts last, not the one just registered."""
    owner = _owner(client, "Alphabet Owner", "01098100002")
    _post(client, "/crm/pets/new",
          {"owner_id": owner["id"], "pet_name": "Zeus", "species": "Dog"})
    _post(client, "/crm/pets/new",
          {"owner_id": owner["id"], "pet_name": "Bella", "species": "Cat"})

    pets = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"]
    assert [p["pet_name"] for p in pets] == ["Bella", "Zeus"]
    assert pets[-1]["pet_name"] == "Zeus", \
        "ordering changed — the comment on this endpoint needs revisiting"


def test_the_page_selects_the_new_patient_by_id(page):
    """`.slice(-1)[0]` on a name-ordered list filed the visit, its vitals, its
    prescription and its invoice against another client's animal."""
    assert ".slice(-1)[0]" not in page, \
        "the page is picking the new patient by list position again"
    assert re.search(r"res\.url\.match\(/\\/crm\\/pets\\/\(\\d\+\)/\)", page), \
        "the page no longer reads the new pet id out of the redirect"


def test_the_page_will_not_guess_which_client_it_created(page):
    """Same failure one step earlier: the phone is stored normalised, so an
    exact string match can miss, and the fallback took the first search hit."""
    assert "rows.find((o) => o.phone === phone) || rows[0]" not in page


# ── bug-499: a refused prescription is not a saved prescription ──────────────

def test_a_nurse_prescription_is_refused_but_answers_200(client, vet, app):
    """The whole reason the page cannot trust the status code.

    add_prescription refuses to record a non-vet as the prescriber — a nurse
    may type one, she may not sign it — and says so with a flash and a
    redirect. Followed, that is a 200 with nothing saved.
    """
    owner = _owner(client, "Nurse Rx Owner", "01098100003")
    _post(client, "/crm/pets/new", {"owner_id": owner["id"],
                                    "pet_name": "Rxcat", "species": "Cat"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Consultation",
        "doctor_name": "Dr. Test", "chief_complaint": "Ear infection"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()

    _become(client, "nurse", "Nurse Nagwa")
    r = _post(client, f"/visits/{visit_id}/prescription", {
        "rx_notes": "", "medication_name_1": "Amoxicillin", "dosage_1": "50 mg",
        "frequency_1": "BID", "duration_1": "7 days", "quantity_1": "14",
        "unit_1": "unit", "route_1": "Oral", "instructions_1": ""})
    assert r.status_code == 200, "a refusal that is not even a 200 needs no read-back"

    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["prescription"] == [], \
        "the prescription saved — this test no longer covers the refusal path"

    # The reason is in the page that comes back, in the markup refusalIn() digs
    # it out of. If base.html renames these classes the page goes back to
    # inventing its own explanation, so this is asserted, not assumed.
    html = r.get_data(as_text=True)
    body = re.sub(r"\s+", " ", html)
    assert re.search(r'class="v3-flash v3-flash-danger".{0,400}?'
                     r'class="v3-flash-msg">[^<]*veterinarian', body), \
        "the refusal reason is no longer readable out of the response"


def test_the_page_reads_the_prescription_back_before_billing(page):
    """Completing the visit raises the invoice. Doing that on the strength of a
    refused prescription bills a consultation with no medication on it."""
    saverx = page[page.index("async function saveRx("):page.index("$(\"btnSaveRx\")")]
    assert "/workflow/api/visit/" in saverx, \
        "saveRx no longer confirms the prescription with the server"
    assert "v.prescription" in saverx


# ── bug-500: a permission refusal is not a declined payment ──────────────────

@pytest.fixture()
def invoice(client, vet, app):
    """A real invoice, raised the way the page raises one."""
    owner = _owner(client, "Payment Truth Owner", "01098100004")
    _post(client, "/crm/pets/new", {"owner_id": owner["id"],
                                    "pet_name": "Payer", "species": "Dog"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Consultation",
        "doctor_name": "Dr. Test", "chief_complaint": "Vaccination due"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()
    _post(client, f"/visits/{visit_id}/diagnosis",
          {"diagnosis_text": "Healthy", "severity": "Mild"})
    _post(client, f"/visits/{visit_id}/complete", {})
    inv = client.get(f"/workflow/api/visit/{visit_id}").get_json()["invoice"]
    assert inv, "no invoice to pay"
    return inv


def test_a_doctor_taking_payment_gets_a_redirect_that_looks_like_success(
        client, invoice):
    """What the page used to see: 200, and a balance that had not moved. It
    blamed the amount, which is not what happened."""
    _become(client, "doctor", "Dr. Hala")
    r = _post(client, f"/finance/invoices/{invoice['id']}/pay",
              {"amount": f"{float(invoice['due_amount']):.2f}", "method": "cash"})
    assert r.status_code == 200

    with client.application.app_context():
        conn = db.get_db()
        paid = conn.execute("SELECT COUNT(*) c FROM payments WHERE invoice_id=?",
                            (invoice["id"],)).fetchone()["c"]
        conn.close()
    assert paid == 0, "the invoicing grant now reaches doctor — this test is moot"


def test_the_same_post_as_an_xhr_is_refused_out_loud(client, invoice):
    """Asking for JSON is what makes the gate answer instead of bouncing. The
    page sends this header for exactly this reason."""
    _become(client, "doctor", "Dr. Hala")
    r = _post(client, f"/finance/invoices/{invoice['id']}/pay",
              {"amount": f"{float(invoice['due_amount']):.2f}", "method": "cash"},
              headers={"Accept": "application/json",
                       "X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 403
    assert r.get_json() == {"ok": False, "error": "forbidden"}


def test_completing_a_visit_lands_a_clinician_on_a_page_they_may_not_read(
        client, vet, app):
    """The trap the other way round, and the reason `res.ok` is not a verdict.

    `/visits/<id>/complete` is the only step that redirects OUT of its own
    module — to the invoice, which needs the `invoicing` grant. Asking for JSON
    turns that into a 403 for a doctor. The visit completed and the invoice was
    raised; refusing here would have told her it had not.
    """
    owner = _owner(client, "Complete Owner", "01098100005")
    _post(client, "/crm/pets/new", {"owner_id": owner["id"],
                                    "pet_name": "Doner", "species": "Dog"})
    pet = client.get(f"/workflow/api/owner/{owner['id']}/pets").get_json()["pets"][0]
    _post(client, "/visits/new", {
        "owner_id": owner["id"], "pet_id": pet["id"], "visit_type": "Consultation",
        "doctor_name": "Dr. Hala", "chief_complaint": "Lame"})
    with app.app_context():
        conn = db.get_db()
        visit_id = conn.execute(
            "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
            (pet["id"],)).fetchone()["id"]
        conn.close()
    _post(client, f"/visits/{visit_id}/diagnosis",
          {"diagnosis_text": "Strain", "severity": "Mild"})

    _become(client, "doctor", "Dr. Hala")
    r = _post(client, f"/visits/{visit_id}/complete", {},
              headers={"Accept": "application/json",
                       "X-Requested-With": "XMLHttpRequest"})

    v = client.get(f"/workflow/api/visit/{visit_id}").get_json()
    assert v["invoice"], "the visit did not bill — this test proves nothing"
    assert v["visit"]["status"] == "Completed"
    assert r.status_code == 403, (
        "the invoice redirect no longer refuses a clinician — if that is "
        "deliberate, completeVisit's comment needs revisiting, not deleting")


def test_the_page_judges_completion_by_the_invoice_not_the_status(page):
    complete = page[page.index("async function completeVisit("):
                    page.index("function renderInvoice(")]
    assert 'if (!res.ok) throw' not in complete, \
        "completeVisit is back to refusing on a status the invoice redirect owns"
    assert "v.invoice" in complete


def test_the_page_asks_for_json_so_a_refusal_arrives_as_one(page):
    # Scoped to postForm: getJSON has always sent this header, so searching the
    # whole page would pass with the writes still going out unlabelled.
    post_form = page[page.index("async function postForm("):page.index("function refusalIn(")]
    assert '"Accept": "application/json"' in post_form, \
        "postForm stopped asking for JSON — every refusal is a silent 200 again"
    assert 'r.status === 403 && text.indexOf(\'"forbidden"\') >= 0' in post_form


def test_a_forbidden_payment_is_not_reported_as_a_bad_amount(page):
    """The message the doctor reads has to be the truth about what happened."""
    handler = page[page.index('postForm("/finance/invoices/"'):]
    handler = handler[:handler.index("finally")]
    assert "res.forbidden" in handler, \
        "the payment step no longer separates a refusal from a decline"
    forbidden = handler.index("res.forbidden")
    decline = handler.index("The payment was not accepted")
    assert forbidden < decline, "the decline message still comes first"
    assert "not permitted to take payments" in handler
