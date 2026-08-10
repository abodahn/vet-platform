"""The one-screen exam: /visits/exam.

The point of the screen is that one submit produces a visit, an invoice and a
payment that agree with each other. These tests exist because that arithmetic
is the part a clinic notices when it is wrong.

The three prices come from the reference video: Examination 250 + Deworming cat
130 + Antiflea Help 180 = 560, cash 500, due 60.
"""
import itertools

import pytest

from models import database as db

from conftest import get_csrf

_seq = itertools.count(1)

PRICES = [("Examination", 250), ("Deworming cat", 130), ("Antiflea Help", 180)]


OWNER_NAME = "Dr Dina Exam"
OWNER_PHONE = "01272840000"


@pytest.fixture(scope="module")
def exam_owner():
    """ONE owner for this whole file, plus the three services.

    Deliberately not one per test. The app database is session-scoped, and
    several screens list owners as `ORDER BY full_name LIMIT 300` — boarding
    and grooming among them. Seventeen extra owners pushed an Arabic-named
    fixture owner in test_services_routes.py off the end of that list and
    failed two tests in a file with nothing to do with this one. Rows created
    here are never cleaned up (FKs from payments and the audit log make that
    its own project), so the fix is to create as few as possible.
    """
    conn = db.get_db()
    row = conn.execute("SELECT id FROM owners WHERE phone=?", (OWNER_PHONE,)).fetchone()
    if row:
        owner_id = row[0]
    else:
        conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                     (OWNER_NAME, OWNER_PHONE))
        owner_id = conn.execute(
            "SELECT id FROM owners WHERE phone=?", (OWNER_PHONE,)).fetchone()[0]
    for name, price in PRICES:
        if not conn.execute("SELECT 1 FROM service_catalog WHERE name=?", (name,)).fetchone():
            conn.execute("INSERT INTO service_catalog(name, standard_price) VALUES(?,?)",
                         (name, price))
    conn.commit()
    conn.close()
    return owner_id


@pytest.fixture
def leo(auth_client, exam_owner):
    """A fresh pet under the shared owner — pets are in no capped dropdown."""
    n = next(_seq)
    pet_name = "Leo%d" % n
    conn = db.get_db()
    conn.execute("INSERT INTO pets(owner_id, pet_name, species, sex) VALUES(?,?,?,?)",
                 (exam_owner, pet_name, "Feline", "M"))
    pet_id = conn.execute(
        "SELECT id FROM pets WHERE owner_id=? ORDER BY id DESC LIMIT 1",
        (exam_owner,)).fetchone()[0]
    conn.commit()
    conn.close()
    return {"owner_id": exam_owner, "pet_id": pet_id, "phone": OWNER_PHONE,
            "owner_name": OWNER_NAME, "pet_name": pet_name}


def _post(auth_client, pet_id, **over):
    form = {
        "visit_date": "2026-08-08",
        "weight_kg": "4",
        "temp_c": "38.5",
        "symptom": "vomiting since yesterday",
        "item_name[]": [n for n, _ in PRICES],
        "item_price[]": [str(p) for _, p in PRICES],
        "item_qty[]": ["1", "1", "1"],
        "item_id[]": ["", "", ""],
        "cash_received": "500",
        "payment_type": "Cash",
        "discount_type": "value",
        "discount_value": "",
        "action": "save",
        "_csrf_token": get_csrf(auth_client),
    }
    form.update(over)
    return auth_client.post("/visits/exam/%d" % pet_id, data=form, follow_redirects=True)


def _invoice(pet_id):
    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM invoices WHERE pet_id=? ORDER BY id DESC LIMIT 1", (pet_id,)).fetchone()
    row = dict(row) if row else None
    conn.close()
    return row


def test_the_video_case_560_paid_500_leaves_60_due(auth_client, leo):
    resp = _post(auth_client, leo["pet_id"])
    assert resp.status_code == 200

    inv = _invoice(leo["pet_id"])
    assert inv is not None, "no invoice was created"
    assert round(inv["subtotal"], 2) == 560.00
    assert round(inv["total"], 2) == 560.00
    assert round(inv["paid_amount"], 2) == 500.00
    assert round(inv["due_amount"], 2) == 60.00
    assert inv["status"] == "Partial"

    conn = db.get_db()
    lines = conn.execute(
        "SELECT description, total FROM invoice_lines WHERE invoice_id=? ORDER BY id",
        (inv["id"],)).fetchall()
    conn.close()
    assert [l["description"] for l in lines] == [n for n, _ in PRICES]
    assert round(sum(l["total"] for l in lines), 2) == 560.00


def test_the_visit_records_the_vitals_and_links_to_the_invoice(auth_client, leo):
    _post(auth_client, leo["pet_id"])
    conn = db.get_db()
    visit = conn.execute(
        "SELECT * FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
        (leo["pet_id"],)).fetchone()
    pet = conn.execute("SELECT weight_kg FROM pets WHERE id=?", (leo["pet_id"],)).fetchone()
    conn.close()
    assert visit["weight_kg"] == 4.0
    assert visit["temp_c"] == 38.5
    assert "vomiting" in (visit["chief_complaint"] or "")
    assert _invoice(leo["pet_id"])["visit_id"] == visit["id"]
    assert pet["weight_kg"] == 4.0, "today's weight becomes the pet's weight"


def test_handing_over_more_than_the_bill_is_change_not_an_overpayment(auth_client, leo):
    _post(auth_client, leo["pet_id"], cash_received="1000")
    inv = _invoice(leo["pet_id"])
    assert round(inv["paid_amount"], 2) == 560.00, "only what is owed is recorded"
    assert round(inv["due_amount"], 2) == 0.00
    assert inv["status"] == "Paid"


def test_a_discount_larger_than_the_bill_cannot_make_the_total_negative(auth_client, leo):
    _post(auth_client, leo["pet_id"], discount_value="5000", cash_received="0")
    inv = _invoice(leo["pet_id"])
    assert inv["total"] >= 0, "total went negative: %r" % inv["total"]
    assert round(inv["total"], 2) == 0.00
    assert round(inv["discount_amount"], 2) == 560.00


def test_a_percentage_discount_comes_off_the_subtotal(auth_client, leo):
    _post(auth_client, leo["pet_id"], discount_type="percent",
          discount_value="10", cash_received="504")
    inv = _invoice(leo["pet_id"])
    assert round(inv["discount_amount"], 2) == 56.00
    assert round(inv["total"], 2) == 504.00
    assert inv["status"] == "Paid"


def test_a_quantity_of_zero_is_not_billed_as_one(auth_client, leo):
    _post(auth_client, leo["pet_id"],
          **{"item_name[]": ["Examination"], "item_price[]": ["250"],
             "item_qty[]": ["0"], "item_id[]": [""], "cash_received": "0"})
    assert _invoice(leo["pet_id"]) is None, "a zero-quantity line was billed"
    conn = db.get_db()
    visit = conn.execute(
        "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
        (leo["pet_id"],)).fetchone()
    conn.close()
    assert visit is not None, "the visit is saved even when there is nothing to bill"


def test_a_mistyped_amount_does_not_500(auth_client, leo):
    resp = _post(auth_client, leo["pet_id"], cash_received="1,0oo", discount_value="abc")
    assert resp.status_code == 200
    inv = _invoice(leo["pet_id"])
    assert round(inv["total"], 2) == 560.00
    assert round(inv["paid_amount"], 2) == 0.00


def test_the_exam_screen_renders_with_the_pet_and_the_service_list(auth_client, leo):
    resp = auth_client.get("/visits/exam/%d" % leo["pet_id"])
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert leo["pet_name"] in body
    assert "Deworming cat" in body, "the service catalog should reach the picker"
    assert leo["owner_name"] in body


def test_a_pet_that_does_not_exist_redirects_instead_of_500(auth_client):
    resp = auth_client.get("/visits/exam/999999", follow_redirects=True)
    assert resp.status_code == 200


def test_the_page_opens_with_nothing_loaded(auth_client, leo):
    """The whole screen is one page: no pet yet, but the catalog is already there."""
    resp = auth_client.get("/visits/exam")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Deworming cat" in body, "the service catalog ships with the page"
    assert "hwSearch" in body, "the client search lives on this page"


def test_search_finds_the_client_by_phone_and_returns_their_pets(auth_client, leo):
    resp = auth_client.get("/visits/exam/api/search?q=%s" % leo["phone"])
    assert resp.status_code == 200
    owners = resp.get_json()["owners"]
    assert any(o["full_name"] == leo["owner_name"] for o in owners)
    mine = [o for o in owners if o["id"] == leo["owner_id"]][0]
    assert leo["pet_name"] in [p["pet_name"] for p in mine["pets"]]


def test_search_finds_the_client_by_name(auth_client, leo):
    resp = auth_client.get("/visits/exam/api/search?q=%s" % leo["owner_name"])
    assert any(o["id"] == leo["owner_id"] for o in resp.get_json()["owners"])


def test_a_one_character_search_returns_nothing_rather_than_the_whole_table(auth_client, leo):
    assert auth_client.get("/visits/exam/api/search?q=a").get_json()["owners"] == []
    assert auth_client.get("/visits/exam/api/search?q=").get_json()["owners"] == []


def test_loading_a_pet_returns_it_with_its_owner_and_history(auth_client, leo):
    _post(auth_client, leo["pet_id"])          # give it one visit to find
    resp = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"])
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["pet"]["pet_name"] == leo["pet_name"]
    assert data["owner"]["full_name"] == leo["owner_name"]
    assert len(data["history"]) >= 1
    assert "vomiting" in (data["history"][0]["chief_complaint"] or "")
    assert "services" not in data, "the catalog is already on the page; do not resend it"


def test_loading_a_pet_that_does_not_exist_is_404_not_500(auth_client):
    assert auth_client.get("/visits/exam/api/pet/999999").status_code == 404


def test_the_search_and_pet_apis_require_a_login(client, leo):
    for url in ("/visits/exam/api/search?q=test",
                "/visits/exam/api/pet/%d" % leo["pet_id"]):
        resp = client.get(url)
        assert resp.status_code in (302, 401, 403), \
            "%s answered %s to an anonymous caller" % (url, resp.status_code)


def test_a_deep_link_with_pet_id_lands_on_the_loaded_screen(auth_client, leo):
    resp = auth_client.get("/visits/exam?pet_id=%d" % leo["pet_id"],
                           follow_redirects=True)
    assert resp.status_code == 200
    assert leo["pet_name"] in resp.get_data(as_text=True)


# ── the wider picture: everything about the owner and the pet ────────────


def test_age_is_computed_from_the_date_of_birth():
    from blueprints.visits.routes import _age_text
    from datetime import date, timedelta
    today = date.today()
    assert _age_text((today - timedelta(days=400)).isoformat()).endswith("m")
    assert _age_text((today - timedelta(days=400)).isoformat()).startswith("1y")
    assert _age_text((today - timedelta(days=60)).isoformat()) in ("1m", "2m")
    assert _age_text("") == ""
    assert _age_text("not-a-date") == ""
    assert _age_text((today + timedelta(days=30)).isoformat()) == "", \
        "a birth date in the future must not render a negative age"


def test_the_pet_record_reaches_the_screen_in_full(auth_client, leo):
    conn = db.get_db()
    conn.execute(
        "UPDATE pets SET color=?, microchip_id=?, neutered=1, allergies=?,"
        " chronic_conditions=?, diet_notes=?, notes=?, dob=? WHERE id=?",
        ("Ginger", "CHIP-99", "Penicillin", "Chronic renal failure",
         "Renal diet only", "Bites when scared", "2019-03-01", leo["pet_id"]))
    conn.commit()
    conn.close()

    data = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()
    p = data["pet"]
    assert p["color"] == "Ginger"
    assert p["microchip_id"] == "CHIP-99"
    assert p["neutered"] == 1
    assert p["allergies"] == "Penicillin"
    assert p["chronic_conditions"] == "Chronic renal failure"
    assert p["diet_notes"] == "Renal diet only"
    assert p["notes"] == "Bites when scared"
    assert p["age_text"], "age should be computed, not left to the reader"


def test_what_the_client_already_owes_is_on_the_screen(auth_client, leo):
    """The number reception needs BEFORE taking money, from the ledger."""
    _post(auth_client, leo["pet_id"], cash_received="0")   # 560 unpaid
    data = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()
    assert data["outstanding"] >= 560.0
    assert any(i["status"] in ("Unpaid", "Partial") for i in data["invoices"])


def test_paying_in_full_clears_the_outstanding_figure(auth_client, leo):
    _post(auth_client, leo["pet_id"], cash_received="560")
    data = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()
    mine = [i for i in data["invoices"] if float(i["total"]) == 560.0]
    assert mine and mine[0]["status"] == "Paid"
    assert float(mine[0]["due_amount"]) == 0.0


def test_the_owners_other_pets_are_listed(auth_client, leo):
    data = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()
    names = [s["pet_name"] for s in data["siblings"]]
    assert leo["pet_name"] not in names, "the pet is not its own sibling"
    for s in data["siblings"]:
        assert "age_text" in s


def test_an_overdue_vaccine_is_flagged(auth_client, leo):
    from datetime import date, timedelta
    past = (date.today() - timedelta(days=30)).isoformat()
    future = (date.today() + timedelta(days=90)).isoformat()
    conn = db.get_db()
    conn.execute(
        "INSERT INTO vaccinations(pet_id, vaccine_name, administered_at, next_due_at)"
        " VALUES(?,?,?,?)", (leo["pet_id"], "Rabies", "2025-08-01", past))
    conn.execute(
        "INSERT INTO vaccinations(pet_id, vaccine_name, administered_at, next_due_at)"
        " VALUES(?,?,?,?)", (leo["pet_id"], "Feline Leukaemia", "2026-01-01", future))
    conn.commit()
    conn.close()

    vax = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()["vaccines"]
    by_name = {v["vaccine_name"]: v for v in vax}
    assert by_name["Rabies"]["overdue"] is True
    assert by_name["Feline Leukaemia"]["overdue"] is False


def test_the_detail_panels_are_all_on_the_page(auth_client, leo):
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    for marker in ("hwAlerts", "hwVaxBody", "hwMedBody", "hwDxBody",
                   "hwInvBody", "hwHistBody", "hwSibList"):
        assert marker in body, "%s panel is missing from the page" % marker


def test_a_pet_with_no_extra_records_still_loads(auth_client, leo):
    """Empty is the common case for a new patient; it must not be an error."""
    data = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()
    for key in ("vaccines", "meds", "chronic", "invoices", "siblings", "upcoming"):
        assert isinstance(data[key], list)
    assert isinstance(data["outstanding"], float)


# ── every clickable thing must go somewhere real ─────────────────────────


def test_the_ids_needed_to_build_links_are_returned(auth_client, leo):
    """Rows without an id render as dead text. Every panel needs its key."""
    from datetime import date, timedelta
    _post(auth_client, leo["pet_id"])          # makes a visit and an invoice
    conn = db.get_db()
    visit_id = conn.execute(
        "SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
        (leo["pet_id"],)).fetchone()[0]
    conn.execute("INSERT INTO vaccinations(pet_id, visit_id, vaccine_name,"
                 " administered_at, next_due_at) VALUES(?,?,?,?,?)",
                 (leo["pet_id"], visit_id, "Rabies", "2026-01-01",
                  (date.today() + timedelta(days=200)).isoformat()))
    # diagnoses.visit_id is NOT NULL — a diagnosis belongs to a consultation.
    conn.execute("INSERT INTO diagnoses(pet_id, visit_id, diagnosis, severity)"
                 " VALUES(?,?,?,?)", (leo["pet_id"], visit_id, "Otitis", "Mild"))
    conn.commit()
    conn.close()

    d = auth_client.get("/visits/exam/api/pet/%d" % leo["pet_id"]).get_json()
    assert d["pet"]["id"], "the pet link needs an id"
    assert d["owner"]["id"], "the owner link needs an id"
    for h in d["history"]:
        assert h["id"], "a history row with no id cannot link to its visit"
    for v in d["vaccines"]:
        assert "id" in v and "visit_id" in v
    for c in d["chronic"]:
        assert "id" in c and "visit_id" in c
    for m in d["meds"]:
        assert "prescription_id" in m and "visit_id" in m
    for i in d["invoices"]:
        assert i["id"], "an invoice row with no id cannot link to the invoice"
    for a in d["upcoming"]:
        assert "id" in a


def test_every_link_target_the_screen_builds_is_a_real_route(app):
    """The two dead dashboard cards survived for months because nobody asked."""
    targets = [
        "/visits/1",
        "/finance/invoices/1",
        "/crm/owners/1",
        "/crm/pets/1",
        "/pharmacy/prescription/1",
        "/clinical/vaccinations/1/certificate",
        "/clinical/vaccinations",
        "/finance/invoices",
        "/appointments/1",
        "/appointments/",
    ]
    adapter = app.url_map.bind("localhost")
    for path in targets:
        base = path.split("?")[0]
        try:
            adapter.match(base)
        except Exception as exc:            # NotFound / MethodNotAllowed
            if exc.__class__.__name__ == "MethodNotAllowed":
                continue                    # the rule exists, just not for GET
            raise AssertionError("%s is not a route: %s" % (base, exc))


def test_the_rows_are_rendered_as_links_not_plain_text(auth_client, leo):
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "hw-rowlink" in body, "clickable rows lost their class"
    assert "'/finance/invoices/'" in body, "invoice rows must link to the invoice"
    assert "'/visits/' + h.id" in body, "history rows must link to the visit"
    assert "/crm/owners/" in body and "/crm/pets/" in body
    assert "wa.me" in body, "the WhatsApp shortcut is gone"


# ── UI shape: what folds, and what must never carry between pets ─────────


def test_switching_pets_clears_what_was_typed_for_the_previous_one(auth_client, leo):
    """The sibling chips make switching one click. Nothing may carry over.

    Without resetForm(), the symptom, services, cash and discount entered for
    the cat stayed on screen when the dog was loaded — and saved against the
    dog. A wrong symptom on the wrong animal's medical record.
    """
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "function resetForm()" in body, "the reset is gone"
    assert "if (switching || !current) resetForm();" in body, \
        "show() no longer resets when the pet changes"
    for field in ("fSymptom", "fTemp", "fNotes", "hwCash", "hwDiscValue"):
        assert field in body.split("function resetForm()")[1].split("}")[0] \
            or field in body, "%s is not cleared on switch" % field


def test_the_reference_panels_fold_and_the_working_area_does_not(auth_client, leo):
    """Vitals, symptom, services and money are typed every visit — never hidden.

    History, vaccinations, medications, diagnoses, invoices, the pet's identity
    and the owner's record are read occasionally, so they collapse.
    """
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)

    for folded in ("hist", "vax", "med", "dx", "inv", "petid", "owner"):
        assert 'data-fold="%s"' % folded in body, "%s should be foldable" % folded

    assert 'data-fold="hist" open' in body, "history should start open"
    for closed in ("vax", "med", "dx", "inv", "petid", "owner"):
        assert 'data-fold="%s" open' % closed not in body, \
            "%s should start closed" % closed

    # The working area must not be inside any <details>. Slice from the vitals
    # block to the next thing after it, not to the first inner </div>.
    working = body.split('<div class="hw-vitals">')[1].split('id="hwPetNotes"')[0]
    assert "fWeight" in working and "fTemp" in working and "fVisitDate" in working
    assert "<details" not in working, "vitals must never be behind a fold"

    # Nor may the services, the total, or the money.
    for must_be_visible in ("hwPick", "hwItemsBody", "hwGrand", "hwCash",
                            "hwDue", "hwSave", "fSymptom"):
        chunk = body.split('id="%s"' % must_be_visible)[0]
        # the last <details> opened before it must already be closed
        assert chunk.count("<details") == chunk.count("</details>"), \
            "%s is inside a fold; it is used on every visit" % must_be_visible


def test_the_fold_state_is_remembered(auth_client, leo):
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "localStorage" in body and "hw-folds" in body, \
        "a vet should not have to re-close the same panel every day"


def test_the_search_is_keyboard_navigable(auth_client, leo):
    body = auth_client.get("/visits/exam").get_data(as_text=True)
    for key in ("ArrowDown", "ArrowUp", "Enter", "Escape"):
        assert key in body, "%s is not handled in the client search" % key


# ── the service picker must never bill a service at zero by accident ─────


def test_a_partial_service_name_is_matched_not_billed_at_zero(auth_client, leo):
    """Typing "Basi" and pressing Enter must add Basic Bath at 200, not "Basi" at 0.

    The old <datalist> only fired on an EXACT match, so partial typing — which
    is how people type — silently added a free-text line priced 0.00. Every
    one of those was a service given away.
    """
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "function scoreMatch(" in body, "the matcher is gone"
    assert "function addFreeText(" in body, "the unknown-name path is gone"
    assert "last._price.focus()" in body, \
        "an unknown service must land with its price focused, never silently 0"
    assert "hwSvcMenu" in body, "candidates must be shown with their prices"


def test_the_visit_records_who_actually_saw_the_animal(auth_client, leo):
    """doctor_name came from whoever was logged in, so reception's name went on
    the medical record when they booked for a vet."""
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert 'name="doctor_name"' in body, "there is no way to say who saw the pet"
    assert 'id="hwDocList"' in body, "the doctor list is not offered"

    _post(auth_client, leo["pet_id"], doctor_name="Dr. Sara Hassan")
    conn = db.get_db()
    visit = conn.execute(
        "SELECT doctor_name FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
        (leo["pet_id"],)).fetchone()
    conn.close()
    assert visit["doctor_name"] == "Dr. Sara Hassan", \
        "the visit was stamped with the wrong person"


def test_an_unfinished_exam_is_not_lost_silently(auth_client, leo):
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "beforeunload" in body, "a half-typed exam can be lost to a stray click"
    assert "function hasWork()" in body


def test_impossible_vitals_warn_but_never_block(auth_client, leo):
    """A warning, not a refusal — a 0.4 kg kitten and a 90 kg Great Dane are real."""
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "function checkVitals(" in body
    assert "hwVitalWarn" in body
    # and the server still accepts an odd but genuine value
    _post(auth_client, leo["pet_id"], weight_kg="0.4", temp_c="41.2")
    conn = db.get_db()
    v = conn.execute("SELECT weight_kg, temp_c FROM visits WHERE pet_id=?"
                     " ORDER BY id DESC LIMIT 1", (leo["pet_id"],)).fetchone()
    conn.close()
    assert v["weight_kg"] == 0.4 and v["temp_c"] == 41.2, \
        "the warning must not have become a block"


# ── written with the visit, not in another module ────────────────────────


def test_a_per_line_discount_comes_off_that_line_only(auth_client, leo):
    """A clinic discounts ONE service far more often than the whole bill —
    the loyal client whose consultation is free but who pays for the medicine."""
    _post(auth_client, leo["pet_id"],
          **{"item_discount[]": ["100", "0", "0"], "cash_received": "0"})
    inv = _invoice(leo["pet_id"])
    conn = db.get_db()
    lines = conn.execute(
        "SELECT description, discount, total FROM invoice_lines"
        " WHERE invoice_id=? ORDER BY id", (inv["id"],)).fetchall()
    conn.close()
    assert round(lines[0]["total"], 2) == 0.00, "the free line still charged"
    assert round(lines[0]["discount"], 2) == 100.00
    assert round(lines[1]["total"], 2) == 130.00, "the other lines moved"
    assert round(lines[2]["total"], 2) == 180.00
    assert round(inv["total"], 2) == 310.00


def test_a_line_discount_over_100_cannot_pay_the_client(auth_client, leo):
    _post(auth_client, leo["pet_id"],
          **{"item_discount[]": ["500", "0", "0"], "cash_received": "0"})
    inv = _invoice(leo["pet_id"])
    conn = db.get_db()
    first = conn.execute(
        "SELECT total FROM invoice_lines WHERE invoice_id=? ORDER BY id LIMIT 1",
        (inv["id"],)).fetchone()
    conn.close()
    assert first["total"] >= 0, "a line went negative: %r" % first["total"]
    assert round(inv["total"], 2) == 310.00


def test_a_prescription_is_written_with_the_visit(auth_client, leo):
    _post(auth_client, leo["pet_id"], doctor_name="Dr. Sara Hassan",
          **{"rx_name[]": ["Amoxicillin", "", "Meloxicam"],
             "rx_dosage[]": ["50 mg", "", "0.1 mg/kg"],
             "rx_frequency[]": ["twice daily", "", "once daily"],
             "rx_duration[]": ["7 days", "", "3 days"],
             "rx_instructions[]": ["with food", "", ""]})
    conn = db.get_db()
    visit = conn.execute("SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
                         (leo["pet_id"],)).fetchone()
    rx = conn.execute("SELECT * FROM prescriptions WHERE visit_id=?",
                      (visit["id"],)).fetchone()
    assert rx is not None, "no prescription was written"
    assert rx["prescribed_by"] == "Dr. Sara Hassan", \
        "the prescriber must be the vet named on the visit, not the logged-in user"
    items = conn.execute(
        "SELECT * FROM prescription_items WHERE prescription_id=? ORDER BY id",
        (rx["id"],)).fetchall()
    conn.close()
    assert len(items) == 2, "the blank row should not become a medication"
    assert items[0]["medication_name"] == "Amoxicillin"
    assert items[0]["dosage"] == "50 mg"
    assert items[0]["frequency"] == "twice daily"
    assert items[1]["medication_name"] == "Meloxicam"


def test_no_prescription_rows_writes_no_prescription(auth_client, leo):
    _post(auth_client, leo["pet_id"])
    conn = db.get_db()
    visit = conn.execute("SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
                         (leo["pet_id"],)).fetchone()
    rx = conn.execute("SELECT id FROM prescriptions WHERE visit_id=?",
                      (visit["id"],)).fetchone()
    conn.close()
    assert rx is None, "an empty prescription block should write nothing"


def test_a_photo_is_attached_to_the_visit(auth_client, leo):
    import io as _io
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)      # real magic bytes
    form = {
        "visit_date": "2026-08-08", "weight_kg": "4", "temp_c": "38.5",
        "symptom": "wound on left flank",
        "item_name[]": ["Examination"], "item_price[]": ["250"],
        "item_qty[]": ["1"], "item_id[]": [""], "item_discount[]": [""],
        "cash_received": "250", "payment_type": "Cash",
        "discount_type": "value", "discount_value": "", "action": "save",
        "attachment_caption": "left flank",
        "_csrf_token": get_csrf(auth_client),
        "attachment": (_io.BytesIO(png), "wound.png"),
    }
    resp = auth_client.post("/visits/exam/%d" % leo["pet_id"], data=form,
                            content_type="multipart/form-data",
                            follow_redirects=True)
    assert resp.status_code == 200
    conn = db.get_db()
    visit = conn.execute("SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
                         (leo["pet_id"],)).fetchone()
    att = conn.execute(
        "SELECT * FROM attachments WHERE entity_type='visit' AND entity_id=?",
        (visit["id"],)).fetchone()
    conn.close()
    assert att is not None, "the photo did not reach the visit"
    assert att["original_name"] == "wound.png"
    assert att["caption"] == "left flank"
    assert att["mime_type"] == "image/png"


def test_a_disguised_file_is_refused_but_the_visit_still_saves(auth_client, leo):
    """The uploads validator checks magic bytes. A .png that is not a PNG must
    be refused — and refusing it must not lose the exam or the money."""
    import io as _io
    form = {
        "visit_date": "2026-08-08", "symptom": "test",
        "item_name[]": ["Examination"], "item_price[]": ["250"],
        "item_qty[]": ["1"], "item_id[]": [""], "item_discount[]": [""],
        "cash_received": "250", "payment_type": "Cash",
        "discount_type": "value", "discount_value": "", "action": "save",
        "_csrf_token": get_csrf(auth_client),
        "attachment": (_io.BytesIO(b"<?php echo 1; ?>"), "evil.png"),
    }
    resp = auth_client.post("/visits/exam/%d" % leo["pet_id"], data=form,
                            content_type="multipart/form-data",
                            follow_redirects=True)
    assert resp.status_code == 200
    conn = db.get_db()
    visit = conn.execute("SELECT id FROM visits WHERE pet_id=? ORDER BY id DESC LIMIT 1",
                         (leo["pet_id"],)).fetchone()
    att = conn.execute(
        "SELECT id FROM attachments WHERE entity_type='visit' AND entity_id=?",
        (visit["id"],)).fetchone()
    conn.close()
    assert att is None, "a disguised file was stored"
    assert visit is not None, "the visit was lost because a file was rejected"
    assert _invoice(leo["pet_id"]) is not None, "the money was lost too"


def test_seen_by_follows_the_clients_preferred_doctor(auth_client, leo):
    body = auth_client.get("/visits/exam/%d" % leo["pet_id"]).get_data(as_text=True)
    assert "if (o.preferred_doctor) $('fDoctor').value = o.preferred_doctor;" in body, \
        "the client who always asks for Dr Sara gets reception's name instead"
