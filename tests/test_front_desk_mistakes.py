# -*- coding: utf-8 -*-
"""What a receptionist actually does wrong.

Both bugs pinned here were found by driving a full day through the real routes
rather than by reading code, and both produced a 500 page while a client stood
at the counter:

  1. Booking a pet that no longer exists -- a stale form, or a record merged in
     another tab -- reached the INSERT and died on the foreign key.
  2. One letter typed in the payment amount box raised ValueError.

The rule for everything here: the app may accept or refuse, but it must never
return a 500, never take money that does not reconcile, and never claim success
while saving nothing.
"""
import pytest

import models.database as db
from models import money
from tests.conftest import get_csrf


@pytest.fixture()
def client_and_pet(app):
    with app.app_context():
        conn = db.get_db()
        with conn:
            oid = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Front Desk Test", "01099000111")).lastrowid
            pid = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, is_active) "
                "VALUES(?,?,?,1)", (oid, "Mistake", "Cat")).lastrowid
        conn.close()
    return oid, pid


# ── booking mistakes ─────────────────────────────────────────────────────────

def test_booking_a_pet_that_does_not_exist_does_not_500(auth_client, client_and_pet):
    """Only "is the field filled in" was checked, so a stale form reached the
    INSERT and raised an unhandled foreign-key error."""
    oid, _ = client_and_pet
    r = auth_client.post("/appointments/new", data={
        "_csrf_token": get_csrf(auth_client),
        "owner_id": oid, "pet_id": 999999, "appt_date": "2026-08-20",
        "appt_start": "09:00", "duration_min": "20",
        "appointment_type": "Consultation", "priority": "Normal",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"no longer on file" in r.data


def test_a_pet_cannot_be_booked_under_another_clients_name(auth_client, app, client_and_pet):
    """Not a crash, a records problem: filed under the wrong client, it follows
    the animal through everything that comes after."""
    _oid, pid = client_and_pet
    with app.app_context():
        conn = db.get_db()
        with conn:
            other = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Somebody Else", "01099000222")).lastrowid
        before = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        conn.close()

    auth_client.post("/appointments/new", data={
        "_csrf_token": get_csrf(auth_client),
        "owner_id": other, "pet_id": pid, "appt_date": "2026-08-20",
        "appt_start": "10:00", "duration_min": "20",
        "appointment_type": "Consultation", "priority": "Normal",
    }, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        after = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        conn.close()
    assert after == before, "a pet was booked under a client who does not own it"


# ── money typed by a human ───────────────────────────────────────────────────

def test_a_letter_in_the_amount_box_does_not_500(auth_client, app, client_and_pet):
    oid, pid = client_and_pet
    with app.app_context():
        inv = db.create_invoice(
            {"owner_id": oid, "pet_id": pid, "issue_date": "2026-08-03"},
            [{"description": "Consult", "quantity": 1, "unit_price": 300, "total": 300}])
    r = auth_client.post(f"/finance/invoices/{inv}/pay", data={
        "_csrf_token": get_csrf(auth_client), "amount": "abc", "method": "Cash",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "not a valid".encode() in r.data


def test_a_typo_does_not_silently_post_zero(auth_client, app, client_and_pet):
    """Coercing to 0 would be worse than the crash: "1O0" with a letter O posts
    as nothing and the till is short with no trace of why."""
    oid, pid = client_and_pet
    with app.app_context():
        inv = db.create_invoice(
            {"owner_id": oid, "pet_id": pid, "issue_date": "2026-08-03"},
            [{"description": "Consult", "quantity": 1, "unit_price": 300, "total": 300}])
    auth_client.post(f"/finance/invoices/{inv}/pay", data={
        "_csrf_token": get_csrf(auth_client), "amount": "1O0", "method": "Cash",
    }, follow_redirects=True)
    with app.app_context():
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM payments WHERE invoice_id=?",
                         (inv,)).fetchone()[0]
        conn.close()
    assert n == 0, "a mistyped amount was recorded as a payment"


# ── the parser itself ────────────────────────────────────────────────────────

def test_form_amount_accepts_what_people_actually_type():
    assert money.form_amount("1500")[0] == 1500.0
    assert money.form_amount("1,500")[0] == 1500.0, "thousands separator rejected"
    assert money.form_amount(" 300 ")[0] == 300.0
    assert money.form_amount("300 EGP")[0] == 300.0
    assert money.form_amount("99.50")[0] == 99.5


def test_form_amount_accepts_arabic_digits():
    """An Arabic keyboard produces ٠-٩, and being usable in Arabic is the
    product's whole differentiator."""
    assert money.form_amount("٣٠٠")[0] == 300.0
    assert money.form_amount("١٥٠٠")[0] == 1500.0


def test_form_amount_reports_rubbish_instead_of_guessing():
    val, err = money.form_amount("abc", "payment amount")
    assert val == 0.0
    assert "payment amount" in err
    assert "abc" in err


def test_form_amount_treats_empty_as_zero_without_an_error():
    assert money.form_amount("") == (0.0, "")
    assert money.form_amount(None) == (0.0, "")


def test_form_amount_keeps_the_sign_for_the_caller_to_judge():
    """Rejecting negatives here would hide a refund path that legitimately
    needs them; the route decides what a negative means."""
    assert money.form_amount("-50")[0] == -50.0
