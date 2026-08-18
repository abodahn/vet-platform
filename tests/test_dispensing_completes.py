# -*- coding: utf-8 -*-
"""A prescription must be able to reach "Dispensed".

Found by working a shift as a real `pharmacist` user. Items with no linked stock
item -- free-text medications -- were `continue`d in the dispensing loop, so
they never got dispensed=1. "All done" counts exactly that column, so such a
prescription could never leave "Partial": the pharmacist clicked Dispense,
handed the medicine to the client, and the queue kept the prescription open
forever.

That is not an edge case. The vet's prescription form is a free-text box, so
this was the DEFAULT path -- the pharmacy queue would have filled with
prescriptions that could never be closed, and there was no record anywhere that
the medicine had been handed over.
"""
import pytest

import models.database as db


def _mkuser(app, username, full_name, role):
    # HR no longer ships its own hasher — it wrote SHA-256 with a salt
    # hardcoded in the repo. bcrypt is the app's one scheme now.
    from models.database import _hash_password as _hash
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(username, full_name, role, "
                "password_hash, is_active) VALUES(?,?,?,?,1)",
                (username, full_name, role, _hash("Pass@2026")))
        conn.close()


def _login(app, username):
    c = app.test_client()
    c.post("/auth/login", data={"username": username, "password": "Pass@2026"})
    c.get("/")
    return c


def _csrf(c):
    from models.security import _CSRF_SESSION_KEY
    with c.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


@pytest.fixture()
def rx(app):
    """A prescription of free-text medications, as the vet's form produces."""
    _mkuser(app, "disp.vet", "Dr. Disp Vet", "doctor")
    _mkuser(app, "disp.pharm", "Disp Pharmacist", "pharmacist")
    with app.app_context():
        conn = db.get_db()
        with conn:
            oid = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                               ("Disp Owner", "01066000111")).lastrowid
            pid = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, is_active) VALUES(?,?,?,1)",
                (oid, "DispPet", "Cat")).lastrowid
            vid = conn.execute(
                "INSERT INTO visits(owner_id, pet_id, visit_date, visit_type, status) "
                "VALUES(?,?,datetime('now'),'Consultation','Open')", (oid, pid)).lastrowid
        conn.close()

    c = _login(app, "disp.vet")
    c.post(f"/visits/{vid}/prescription", data={
        "_csrf_token": _csrf(c),
        "medication_name_1": "Maropitant", "dosage_1": "4 mg",
        "frequency_1": "Once daily", "duration_1": "2 days", "route_1": "SC",
        "medication_name_2": "Omeprazole", "dosage_2": "4 mg",
        "frequency_2": "Once daily", "duration_2": "5 days", "route_2": "PO",
    }, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        try:
            rid = conn.execute(
                "SELECT id FROM prescriptions WHERE visit_id=?", (vid,)).fetchone()[0]
        finally:
            conn.close()
    return {"id": rid, "pet": pid, "visit": vid}


def _status(app, rid):
    with app.app_context():
        conn = db.get_db()
        try:
            return conn.execute(
                "SELECT status FROM prescriptions WHERE id=?", (rid,)).fetchone()[0]
        finally:
            conn.close()


def test_a_free_text_prescription_can_be_fully_dispensed(app, rx):
    """The whole bug. It stuck at 'Partial' no matter how many times you clicked."""
    c = _login(app, "disp.pharm")
    c.post(f"/pharmacy/dispense/{rx['id']}",
           data={"_csrf_token": _csrf(c)}, follow_redirects=True)
    assert _status(app, rx["id"]) == "Dispensed", \
        "a prescription of free-text medications could not be completed"


def test_every_line_is_marked_dispensed(app, rx):
    c = _login(app, "disp.pharm")
    c.post(f"/pharmacy/dispense/{rx['id']}",
           data={"_csrf_token": _csrf(c)}, follow_redirects=True)
    with app.app_context():
        conn = db.get_db()
        try:
            left = conn.execute(
                "SELECT COUNT(*) FROM prescription_items "
                "WHERE prescription_id=? AND dispensed=0", (rx["id"],)).fetchone()[0]
        finally:
            conn.close()
    assert left == 0, f"{left} line(s) stayed undispensed"


def test_the_handover_is_recorded_even_without_a_stock_item(app, rx):
    """dispensing_log is the STOCK register (item_id NOT NULL) and an untracked
    drug has no stock movement -- but handing medicine to a client must still
    leave a trace, so it goes to the audit trail."""
    c = _login(app, "disp.pharm")
    c.post(f"/pharmacy/dispense/{rx['id']}",
           data={"_csrf_token": _csrf(c)}, follow_redirects=True)
    with app.app_context():
        conn = db.get_db()
        try:
            rows = conn.execute(
                "SELECT details FROM audit_log WHERE action=?",
                ("dispensed_untracked_medication",)).fetchall()
        finally:
            conn.close()
    assert len(rows) >= 2, "the handover left no record at all"
    joined = " ".join(r["details"] or "" for r in rows)
    assert "Maropitant" in joined, "the record does not say what was handed over"


def test_it_leaves_the_pharmacy_queue(app, rx):
    """The queue is `status != 'Dispensed'`. A prescription that cannot reach
    that status stays on the pharmacist's screen for good."""
    c = _login(app, "disp.pharm")
    c.post(f"/pharmacy/dispense/{rx['id']}",
           data={"_csrf_token": _csrf(c)}, follow_redirects=True)
    html = c.get("/pharmacy/").get_data(as_text=True)
    assert "DispPet" not in html, "a fully dispensed prescription is still in the queue"


def test_dispensing_twice_does_not_double_record(app, rx):
    c = _login(app, "disp.pharm")
    for _ in range(2):
        c.post(f"/pharmacy/dispense/{rx['id']}",
               data={"_csrf_token": _csrf(c)}, follow_redirects=True)
    # Scoped to THIS prescription's line items: the `app` fixture is
    # session-scoped, so audit_log carries entries from every earlier test here.
    with app.app_context():
        conn = db.get_db()
        try:
            ids = [str(r["id"]) for r in conn.execute(
                "SELECT id FROM prescription_items WHERE prescription_id=?",
                (rx["id"],)).fetchall()]
            marks = ",".join("?" for _ in ids)
            n = conn.execute(
                f"SELECT COUNT(*) FROM audit_log WHERE action=? AND entity_id IN ({marks})",
                ("dispensed_untracked_medication", *ids)).fetchone()[0]
        finally:
            conn.close()
    assert n == len(ids), \
        f"re-dispensing recorded the handover again ({n} entries for {len(ids)} items)"


def test_a_role_that_may_not_dispense_is_refused(app, rx):
    """The dispensing loop is where stock leaves the building."""
    _mkuser(app, "disp.recep", "Disp Reception", "reception")
    c = _login(app, "disp.recep")
    c.post(f"/pharmacy/dispense/{rx['id']}",
           data={"_csrf_token": _csrf(c)}, follow_redirects=True)
    assert _status(app, rx["id"]) != "Dispensed", "a receptionist dispensed a prescription"
