# -*- coding: utf-8 -*-
"""Estimates (quotes) — the feature every competing PIMS had and this did not.

An estimate is a priced plan the client agrees to BEFORE the work happens. The
two things that must never go wrong:

  1. An estimate must not count as revenue. It is a proposal, not a sale.
  2. An approved estimate and the invoice it becomes must total the same. A
     quote the client signed and a bill that says something else is the whole
     reason clinics ask for this feature.

Both are asserted here against the real aggregation queries, not against the
estimate module in isolation.
"""
import pytest

import models.database as db
from tests.conftest import get_csrf


@pytest.fixture()
def owner_and_pet(app):
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Estimate Test Owner", "01000000999"))
            oid = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, is_active) VALUES(?,?,?,1)",
                (oid, "Bandit", "Dog"))
            pid = cur.lastrowid
        conn.close()
    return oid, pid


LINES = [
    {"line_type": "service", "description": "Ovariohysterectomy", "quantity": 1,
     "unit_price": 2500.0, "discount": 0, "total": 2500.0},
    {"line_type": "medication", "description": "Post-op analgesia", "quantity": 3,
     "unit_price": 120.0, "discount": 0, "total": 360.0},
]


def _make(app, oid, pid, **over):
    data = {"owner_id": oid, "pet_id": pid, "issue_date": "2026-08-02",
            "valid_until": "2026-08-16", "created_by": "tester"}
    data.update(over)
    with app.app_context():
        return db.create_estimate(data, LINES)


# ── the money must not leak into the books ───────────────────────────────────

def test_an_estimate_is_not_revenue(app, owner_and_pet):
    """The reason estimates got their own tables.

    Storing them as invoices with status='Estimate' would have been a much
    smaller diff — and every query that sums invoice money while filtering only
    on status!='Cancelled' would have booked this 2860 EGP as earned.
    """
    oid, pid = owner_and_pet
    with app.app_context():
        conn = db.get_db()
        before = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status!='Cancelled'"
        ).fetchone()[0]
        conn.close()

    _make(app, oid, pid)

    with app.app_context():
        conn = db.get_db()
        after = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status!='Cancelled'"
        ).fetchone()[0]
        conn.close()
    assert after == before, "an unapproved estimate was counted as revenue"


def test_an_estimate_creates_no_invoice_row(app, owner_and_pet):
    oid, pid = owner_and_pet
    with app.app_context():
        conn = db.get_db()
        before = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        conn.close()
    _make(app, oid, pid)
    with app.app_context():
        conn = db.get_db()
        after = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        conn.close()
    assert after == before


# ── arithmetic ───────────────────────────────────────────────────────────────

def test_totals_are_computed_from_the_lines(app, owner_and_pet):
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    with app.app_context():
        est = db.get_estimate(est_id)
    assert est["subtotal"] == 2860.0
    assert est["total"] == 2860.0
    assert len(est["lines"]) == 2


def test_discount_and_tax_apply_in_the_same_order_as_an_invoice(app, owner_and_pet):
    """Tax is charged on the discounted amount, not the gross."""
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid, discount_type="percent", discount_value=10, tax_rate=14)
    with app.app_context():
        est = db.get_estimate(est_id)
    assert est["discount_amount"] == 286.0            # 10% of 2860
    assert est["tax_amount"] == pytest.approx(360.36)  # 14% of 2574
    assert est["total"] == pytest.approx(2934.36)


# ── conversion ───────────────────────────────────────────────────────────────

def test_only_an_approved_estimate_converts(app, owner_and_pet):
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    with app.app_context():
        with pytest.raises(ValueError):
            db.convert_estimate(est_id, "tester")


def test_the_invoice_totals_exactly_what_the_client_approved(app, owner_and_pet):
    """The defect this feature exists to prevent."""
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid, discount_type="percent", discount_value=10, tax_rate=14)
    with app.app_context():
        db.decide_estimate(est_id, "Approved", "client")
        inv_id = db.convert_estimate(est_id, "tester")
        est = db.get_estimate(est_id)
        inv = db.get_invoice(inv_id)
    assert inv["total"] == est["total"], "the bill does not match the signed quote"
    assert inv["subtotal"] == est["subtotal"]
    assert inv["discount_amount"] == est["discount_amount"]
    assert inv["tax_amount"] == est["tax_amount"]
    assert len(inv["lines"]) == len(est["lines"])


def test_converting_twice_does_not_bill_the_client_twice(app, owner_and_pet):
    """Two clicks on Convert, or a double-submit, must not create two invoices."""
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    with app.app_context():
        db.decide_estimate(est_id, "Approved", "client")
        first = db.convert_estimate(est_id, "tester")
        second = db.convert_estimate(est_id, "tester")
    assert first == second, "a second conversion created a second invoice"


def test_conversion_marks_the_estimate_converted_and_links_the_invoice(app, owner_and_pet):
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    with app.app_context():
        db.decide_estimate(est_id, "Approved", "client")
        inv_id = db.convert_estimate(est_id, "tester")
        est = db.get_estimate(est_id)
    assert est["status"] == "Converted"
    assert est["invoice_id"] == inv_id


def test_a_converted_estimate_IS_revenue(app, owner_and_pet):
    """The other half of test_an_estimate_is_not_revenue: once approved and
    converted the money must appear, or the clinic would work for free."""
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    with app.app_context():
        conn = db.get_db()
        before = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status!='Cancelled'"
        ).fetchone()[0]
        conn.close()
        db.decide_estimate(est_id, "Approved", "client")
        db.convert_estimate(est_id, "tester")
        conn = db.get_db()
        after = conn.execute(
            "SELECT COALESCE(SUM(total),0) FROM invoices WHERE status!='Cancelled'"
        ).fetchone()[0]
        conn.close()
    assert after == before + 2860.0


# ── numbering ────────────────────────────────────────────────────────────────

def test_numbers_do_not_collide_after_a_delete(app, owner_and_pet):
    """_next_invoice_number() uses COUNT(*) and repeats a number as soon as a
    row is deleted; estimate_number is UNIQUE, so copying that would raise."""
    oid, pid = owner_and_pet
    first = _make(app, oid, pid)
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM estimates WHERE id=?", (first,))
        conn.close()
    second = _make(app, oid, pid)   # must not raise UNIQUE violation
    with app.app_context():
        assert db.get_estimate(second) is not None


# ── routes ───────────────────────────────────────────────────────────────────

def test_the_estimates_page_loads(auth_client):
    assert auth_client.get("/finance/estimates").status_code == 200


def test_the_new_estimate_form_loads(auth_client):
    assert auth_client.get("/finance/estimates/new").status_code == 200


def test_creating_an_estimate_through_the_form(auth_client, app, owner_and_pet):
    oid, pid = owner_and_pet
    r = auth_client.post("/finance/estimates/new", data={
        "_csrf_token": get_csrf(auth_client),
        "owner_id": oid, "pet_id": pid, "issue_date": "2026-08-02",
        "description[]": "Dental scaling", "qty[]": "1",
        "unit_price[]": "900", "discount[]": "0", "line_type[]": "service",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert any(e["owner_id"] == oid for e in db.list_estimates(owner_id=oid))


def test_an_estimate_with_no_lines_is_rejected(auth_client, owner_and_pet):
    oid, _pid = owner_and_pet
    r = auth_client.post("/finance/estimates/new", data={
        "_csrf_token": get_csrf(auth_client),
        "owner_id": oid, "issue_date": "2026-08-02", "description[]": "   ",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"At least one line item" in r.data


def test_a_converted_estimate_cannot_be_re_decided(auth_client, app, owner_and_pet):
    """Otherwise an invoice would exist with no approved quote behind it."""
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    with app.app_context():
        db.decide_estimate(est_id, "Approved", "client")
        db.convert_estimate(est_id, "tester")
    auth_client.post(f"/finance/estimates/{est_id}/decide", data={
        "_csrf_token": get_csrf(auth_client), "decision": "Declined",
    }, follow_redirects=True)
    with app.app_context():
        assert db.get_estimate(est_id)["status"] == "Converted"


def test_the_print_view_renders(auth_client, app, owner_and_pet):
    oid, pid = owner_and_pet
    est_id = _make(app, oid, pid)
    r = auth_client.get(f"/finance/estimates/{est_id}/print")
    assert r.status_code == 200
    assert b"Ovariohysterectomy" in r.data
    # The client-facing caveat is the point of the printed page.
    assert b"not a bill" in r.data


def test_a_missing_estimate_redirects_rather_than_500s(auth_client):
    assert auth_client.get("/finance/estimates/999999").status_code in (302, 200)


# ── the page's own JavaScript ────────────────────────────────────────────────

def test_the_form_script_only_targets_elements_that_exist(auth_client):
    """Every selector the inline script uses must resolve on the page it ships with.

    This is the defect class that keeps reaching the browser in this codebase:
    the totals silently stop updating and nothing errors server-side, so the
    test suite stays green while the page is visibly broken. Asserted here
    because a rendered-HTML check is the only thing that catches a renamed id.
    """
    import re
    html = auth_client.get("/finance/estimates/new").get_data(as_text=True)
    script = html[html.rindex("<script>"):]

    missing = [i for i in set(re.findall(r"getElementById\(['\"]([^'\"]+)", script))
               if f'id="{i}"' not in html]
    assert not missing, f"script targets ids that are not on the page: {missing}"

    missing_cls = [c for c in set(re.findall(r"querySelectorAll?\(['\"]\.([a-z-]+)", script))
                   if f'class="{c}' not in html and f' {c}"' not in html and f'"{c}"' not in html]
    assert not missing_cls, f"script targets classes that are not on the page: {missing_cls}"


def test_the_form_posts_a_csrf_token(auth_client):
    """platform.js injects one on submit, but only if JavaScript ran. The money
    forms carry it in the markup too so a submit cannot silently 403."""
    html = auth_client.get("/finance/estimates/new").get_data(as_text=True)
    assert 'name="_csrf_token"' in html
