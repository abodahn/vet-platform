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
