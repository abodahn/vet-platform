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


@pytest.fixture
def leo(auth_client):
    """A fresh owner + pet, and the three services, in the shared test DB."""
    n = next(_seq)
    phone = "0127284%04d" % n
    conn = db.get_db()
    conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                 ("Dr Dina %d" % n, phone))
    owner_id = conn.execute("SELECT id FROM owners WHERE phone=?", (phone,)).fetchone()[0]
    conn.execute("INSERT INTO pets(owner_id, pet_name, species, sex) VALUES(?,?,?,?)",
                 (owner_id, "Leo%d" % n, "Feline", "M"))
    pet_id = conn.execute(
        "SELECT id FROM pets WHERE owner_id=? ORDER BY id DESC LIMIT 1", (owner_id,)).fetchone()[0]
    for name, price in PRICES:
        exists = conn.execute("SELECT 1 FROM service_catalog WHERE name=?", (name,)).fetchone()
        if not exists:
            conn.execute("INSERT INTO service_catalog(name, standard_price) VALUES(?,?)",
                         (name, price))
    conn.commit()
    conn.close()
    return {"owner_id": owner_id, "pet_id": pet_id, "phone": phone,
            "owner_name": "Dr Dina %d" % n, "pet_name": "Leo%d" % n}


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


def test_the_picker_finds_the_client_by_phone(auth_client, leo):
    resp = auth_client.get("/visits/exam?q=%s" % leo["phone"])
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert leo["owner_name"] in body
    assert leo["pet_name"] in body
