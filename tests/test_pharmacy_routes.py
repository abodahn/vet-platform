# -*- coding: utf-8 -*-
"""Pharmacy — dispensing must move stock, or the clinic's shelf is fiction.

The route under test does five things in one transaction: pick a batch by
FEFO, deduct it, write a stock movement, write a dispensing log line, and
mark the prescription. A 200 says nothing about any of them. So every test
here reads the rows back.

The branch that matters most is the failing one. A dispense that "succeeds"
against stock that is not there hands out a drug the clinic does not have
and leaves the stock figure negative or unchanged — nobody finds out until
someone reaches for the box.

SQLite, no network.
"""
import models.database as db
from conftest import get_csrf


# ── helpers ───────────────────────────────────────────────────────────────────

def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = get_csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _rows(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        rows = conn.execute(sql, params).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def _one(app, sql, params=()):
    rows = _rows(app, sql, params)
    return rows[0] if rows else None


def _scalar(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        v = conn.execute(sql, params).fetchone()[0]
        conn.close()
    return v


def _mk_rx(app, name, drug, qty, controlled=0):
    """Owner + pet + visit + a prescription for one stock-linked medication."""
    with app.app_context():
        item_id = db.create_item({
            "name": drug, "sku": "PHTEST-" + name, "category_id": 1,
            "unit": "tablet", "cost_price": 2, "sell_price": 5,
            "is_medication": 1, "is_controlled": controlled,
        })
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                (name + " Owner", "01055500022"))
            owner_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, weight_kg) "
                "VALUES(?,?,?,?)", (owner_id, name, "Cat", 4.0))
            pet_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO visits(owner_id, pet_id, visit_date, doctor_name, "
                "chief_complaint, status) VALUES(?,?,?,?,?,?)",
                (owner_id, pet_id, "2026-07-22", "Dr. Nour", "Fever", "Open"))
            visit_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO prescriptions(visit_id, pet_id, owner_id, "
                "prescribed_by, status) VALUES(?,?,?,?,?)",
                (visit_id, pet_id, owner_id, "Dr. Nour", "Active"))
            rx_id = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO prescription_items(prescription_id, item_id, "
                "medication_name, dosage, quantity, unit) VALUES(?,?,?,?,?,?)",
                (rx_id, item_id, drug, "1 tab", qty, "tablet"))
            pi_id = cur.lastrowid
        conn.close()
    return {"item_id": item_id, "owner_id": owner_id, "pet_id": pet_id,
            "visit_id": visit_id, "rx_id": rx_id, "pi_id": pi_id}


def _stock(app, item_id):
    return float(_scalar(
        app, "SELECT COALESCE(SUM(quantity),0) FROM batches WHERE item_id=?",
        (item_id,)))


# ── the happy path, asserted all the way down ─────────────────────────────────

def test_dispensing_deducts_stock_and_leaves_a_trail(app, auth_client):
    fx = _mk_rx(app, "Deduct", "Amoxiclav 250 Dispense", qty=10)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "PH-A", "2027-06-30", 40, 2)

    assert _stock(app, fx["item_id"]) == 40

    r = _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})
    assert r.status_code == 200, "dispense POST did not render"

    assert _stock(app, fx["item_id"]) == 30, \
        "dispensing 10 tablets did not come off the shelf"

    mv = _one(app, "SELECT * FROM stock_movements WHERE item_id=? AND "
                   "movement_type='Dispensed'", (fx["item_id"],))
    assert mv, "stock moved with no stock_movements row — the audit trail is gone"
    assert float(mv["quantity"]) == 10
    assert mv["reference_type"] == "prescription"
    assert int(mv["reference_id"]) == fx["rx_id"]

    log = _one(app, "SELECT * FROM dispensing_log WHERE prescription_item_id=?",
               (fx["pi_id"],))
    assert log, "nothing was written to the dispensing log"
    assert float(log["quantity"]) == 10
    assert log["pet_id"] == fx["pet_id"], "dispensing logged against the wrong animal"
    assert log["visit_id"] == fx["visit_id"], "dispensing lost its visit"
    assert log["batch_id"] == _one(
        app, "SELECT id FROM batches WHERE item_id=?", (fx["item_id"],))["id"]

    item = _one(app, "SELECT * FROM prescription_items WHERE id=?", (fx["pi_id"],))
    assert item["dispensed"] == 1, "item handed over but not marked dispensed"
    rx = _one(app, "SELECT * FROM prescriptions WHERE id=?", (fx["rx_id"],))
    assert rx["status"] == "Dispensed", \
        f"fully dispensed prescription still reads {rx['status']!r}"
    assert rx["dispensed_at"], "no dispensing timestamp"


def test_dispensing_picks_the_earliest_expiry_batch(app, auth_client):
    """FEFO — the box that expires first leaves first, or stock expires on the shelf."""
    fx = _mk_rx(app, "Fefo", "Meloxicam Fefo", qty=5)
    with app.app_context():
        late = db.add_stock_batch(fx["item_id"], 1, "LATE", "2028-12-31", 20, 2)
        soon = db.add_stock_batch(fx["item_id"], 1, "SOON", "2027-01-31", 20, 2)

    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    q_soon = float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (soon,)))
    q_late = float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (late,)))
    assert q_soon == 15 and q_late == 20, \
        f"FEFO took from the wrong batch (soon={q_soon}, late={q_late})"


def test_dispensing_does_not_reach_for_an_expired_batch(app, auth_client):
    """FEFO sorts by expiry ascending — which puts expired stock first in line.

    "First expired, first out" means the box closest to expiry, not the box
    already past it. Handing an owner a drug that expired in 2020 is the one
    outcome the batch table exists to prevent.
    """
    fx = _mk_rx(app, "Expired", "Cephalexin Expired", qty=5)
    with app.app_context():
        expired = db.add_stock_batch(fx["item_id"], 1, "GONE-OFF", "2020-01-01", 30, 2)
        good = db.add_stock_batch(fx["item_id"], 1, "IN-DATE", "2028-01-01", 30, 2)

    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    assert float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (expired,))) == 30, \
        "an expired batch was dispensed to a patient"
    assert float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (good,))) == 25, \
        "in-date stock was not used"


def test_an_expired_batch_cannot_be_chosen_by_hand_either(app, auth_client):
    fx = _mk_rx(app, "ExpiredPick", "Ampicillin Expired", qty=4)
    with app.app_context():
        expired = db.add_stock_batch(fx["item_id"], 1, "OLD-PICK", "2019-06-30", 20, 2)

    r = _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}",
              {f"batch_{fx['pi_id']}": expired})

    assert float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (expired,))) == 20, \
        "an expired batch was dispensed because the pharmacist picked it"
    assert "expired" in r.get_data(as_text=True).lower(), \
        "no warning that the chosen batch is out of date"


def test_dispensing_honours_an_explicitly_chosen_batch(app, auth_client):
    fx = _mk_rx(app, "PickBatch", "Enrofloxacin Pick", qty=4)
    with app.app_context():
        first = db.add_stock_batch(fx["item_id"], 1, "B1", "2027-02-01", 10, 2)
        chosen = db.add_stock_batch(fx["item_id"], 1, "B2", "2029-02-01", 10, 2)

    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}",
          {f"batch_{fx['pi_id']}": chosen})

    assert float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (chosen,))) == 6, \
        "the pharmacist's chosen batch was not the one deducted"
    assert float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (first,))) == 10


# ── the branch that matters: stock that is not there ──────────────────────────

def test_dispensing_against_empty_stock_does_not_hand_out_the_drug(app, auth_client):
    """No batch at all. Nothing may be deducted, logged, or marked done."""
    fx = _mk_rx(app, "NoStock", "Ketamine NoStock", qty=6)
    assert _stock(app, fx["item_id"]) == 0

    r = _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})
    assert r.status_code == 200
    assert "Insufficient stock" in r.get_data(as_text=True), \
        "dispensing from an empty shelf reported no problem to the pharmacist"

    assert _stock(app, fx["item_id"]) == 0, "stock went negative dispensing from nothing"
    assert _rows(app, "SELECT * FROM dispensing_log WHERE prescription_item_id=?",
                 (fx["pi_id"],)) == [], "a drug that does not exist was logged as handed over"
    assert _rows(app, "SELECT * FROM stock_movements WHERE item_id=?",
                 (fx["item_id"],)) == []
    assert _one(app, "SELECT * FROM prescription_items WHERE id=?",
                (fx["pi_id"],))["dispensed"] == 0, \
        "item marked dispensed although no stock left the shelf"
    assert _one(app, "SELECT * FROM prescriptions WHERE id=?",
                (fx["rx_id"],))["status"] != "Dispensed", \
        "prescription closed as Dispensed with nothing dispensed"


def test_dispensing_more_than_the_shelf_holds_is_refused(app, auth_client):
    """20 needed, 8 on hand. Partial silent deduction would be the worst outcome."""
    fx = _mk_rx(app, "ShortStock", "Tramadol Short", qty=20)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "SHORT", "2027-05-01", 8, 2)

    r = _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})
    assert "Insufficient stock" in r.get_data(as_text=True)
    assert _stock(app, fx["item_id"]) == 8, \
        "an unfillable prescription still moved stock"
    assert _rows(app, "SELECT * FROM dispensing_log WHERE prescription_item_id=?",
                 (fx["pi_id"],)) == []
    assert _one(app, "SELECT * FROM prescription_items WHERE id=?",
                (fx["pi_id"],))["dispensed"] == 0


def test_a_chosen_batch_without_enough_stock_is_refused(app, auth_client):
    fx = _mk_rx(app, "ThinBatch", "Cefalexin Thin", qty=15)
    with app.app_context():
        thin = db.add_stock_batch(fx["item_id"], 1, "THIN", "2027-03-01", 5, 2)
        db.add_stock_batch(fx["item_id"], 1, "FAT", "2028-03-01", 90, 2)

    r = _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}",
              {f"batch_{fx['pi_id']}": thin})
    assert "Insufficient stock" in r.get_data(as_text=True)
    assert float(_scalar(app, "SELECT quantity FROM batches WHERE id=?", (thin,))) == 5, \
        "a batch was overdrawn below zero"
    assert _stock(app, fx["item_id"]) == 95, \
        "the shortfall was silently taken from another batch"


def test_dispensing_a_partial_quantity_takes_only_that_quantity(app, auth_client):
    fx = _mk_rx(app, "Partial", "Prednisolone Partial", qty=30)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "PART", "2027-08-01", 30, 2)

    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}",
          {f"qty_{fx['pi_id']}": "12"})

    assert _stock(app, fx["item_id"]) == 18, \
        "the quantity the pharmacist typed is not the quantity that left stock"
    log = _one(app, "SELECT * FROM dispensing_log WHERE prescription_item_id=?",
               (fx["pi_id"],))
    assert float(log["quantity"]) == 12


def test_dispensing_twice_does_not_deduct_twice(app, auth_client):
    """A double-submit must not take the drug off the shelf a second time."""
    fx = _mk_rx(app, "Double", "Doxycycline Double", qty=10)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "DBL", "2027-09-01", 25, 2)

    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})
    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    assert _stock(app, fx["item_id"]) == 15, "a resubmitted dispense deducted twice"
    assert len(_rows(app, "SELECT * FROM dispensing_log WHERE prescription_item_id=?",
                     (fx["pi_id"],))) == 1


def test_dispense_without_csrf_moves_no_stock(app, auth_client):
    fx = _mk_rx(app, "RxNoToken", "Gabapentin NoToken", qty=5)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "NT", "2027-10-01", 20, 2)

    r = auth_client.post(f"/pharmacy/dispense/{fx['rx_id']}", data={})
    assert r.status_code == 403
    assert _stock(app, fx["item_id"]) == 20, "a rejected POST still moved stock"


# ── history ───────────────────────────────────────────────────────────────────

def test_history_shows_what_was_just_dispensed(app, auth_client):
    fx = _mk_rx(app, "History", "Ivermectin History", qty=3)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "HIST-B", "2027-11-01", 10, 2)
    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    html = auth_client.get("/pharmacy/history").get_data(as_text=True)
    assert "Ivermectin History" in html, \
        "a dispensing that happened today is missing from today's history"
    assert "History" in html and "HIST-B" in html, \
        "history does not say which patient or which batch"


def test_history_respects_its_date_filter(app, auth_client):
    fx = _mk_rx(app, "HistFilter", "Fenbendazole Filter", qty=2)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "HF-B", "2027-12-01", 10, 2)
    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    html = auth_client.get("/pharmacy/history?date_from=2099-01-01").get_data(as_text=True)
    assert "Fenbendazole Filter" not in html, \
        "the date filter does not filter — history shows records outside the range"


# ── controlled drugs register ─────────────────────────────────────────────────

def test_narcotics_register_records_a_controlled_drug_dispensing(app, auth_client):
    """The narcotics register is a legal document. A missing line is a missing box."""
    fx = _mk_rx(app, "Narcotic", "Morphine Register", qty=2, controlled=1)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "CD-B", "2027-04-01", 10, 2)
    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    html = auth_client.get("/pharmacy/narcotics").get_data(as_text=True)
    assert "Morphine Register" in html, \
        "a controlled drug was dispensed and never reached the narcotics register"
    assert "Narcotic" in html, "the register does not name the patient it went to"

    # and the controlled-drug audit entry
    audit = _rows(app, "SELECT * FROM audit_log WHERE action=? AND entity_id=?",
                  ("controlled_drug_dispensed", str(fx["pi_id"])))
    assert audit, "controlled drug dispensed with no audit_log entry"


def test_narcotics_register_excludes_ordinary_drugs(app, auth_client):
    fx = _mk_rx(app, "Ordinary", "Vitamin B Ordinary", qty=1, controlled=0)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "ORD-B", "2027-04-01", 10, 2)
    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    html = auth_client.get("/pharmacy/narcotics").get_data(as_text=True)
    assert "Vitamin B Ordinary" not in html, \
        "an uncontrolled drug is padding the narcotics register"


# ── the queue ─────────────────────────────────────────────────────────────────

def test_an_undispensed_prescription_is_visible_in_the_queue(app, auth_client):
    """A prescription nobody can see is a treatment nobody gives."""
    fx = _mk_rx(app, "Queued", "Clindamycin Queue", qty=4)
    html = auth_client.get("/pharmacy/").get_data(as_text=True)
    assert f"/pharmacy/prescription/{fx['rx_id']}" in html, \
        "an Active prescription never appeared in the dispensing queue"
    assert "Queued" in html, "the queue does not say which animal the drug is for"


def test_a_dispensed_prescription_leaves_the_queue(app, auth_client):
    fx = _mk_rx(app, "Leaves", "Marbofloxacin Leaves", qty=2)
    with app.app_context():
        db.add_stock_batch(fx["item_id"], 1, "LV-B", "2027-07-01", 10, 2)
    _post(auth_client, f"/pharmacy/dispense/{fx['rx_id']}", {})

    html = auth_client.get("/pharmacy/").get_data(as_text=True)
    assert f"/pharmacy/prescription/{fx['rx_id']}" not in html, \
        "a fully dispensed prescription is still sitting in the queue"
