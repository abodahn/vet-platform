# -*- coding: utf-8 -*-
"""Turning a quotation into an invoice.

Found by instrumenting the request dispatcher across the whole suite: of 412
registered endpoints, `finance.estimate_convert` was the only one no test
reached. It is a money path - it creates an invoice - so it is the worst one to
have been missed.

The function it calls guards against double-conversion by re-reading the
estimate rather than by a UNIQUE constraint, because invoice_id is nullable for
every estimate that never converts. A guard with no test is a guard nobody will
notice losing.
"""
import pytest

from conftest import get_csrf


@pytest.fixture
def approved_estimate(app):
    """An approved estimate with one line, ready to convert."""
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO owners (full_name, phone) VALUES (?,?)",
            ("Estimate Convert Owner", "01098120001"))
        owner_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
            (owner_id, "Quote Cat", "Cat"))
        pet_id = cur.lastrowid
        conn.commit()
        conn.close()

        est_id = db.create_estimate(
            {
                "owner_id": owner_id,
                "pet_id": pet_id,
                "doctor_name": "Dr Quote",
                "issue_date": "2026-08-23",
            },
            [{"description": "Dental scale", "quantity": 1, "unit_price": 900.0}],
        )
        conn = db.get_db()
        conn.execute("UPDATE estimates SET status='Approved' WHERE id=?", (est_id,))
        conn.commit()
        conn.close()
    return {"est_id": est_id, "owner_id": owner_id, "pet_id": pet_id}


def test_an_approved_estimate_becomes_an_invoice(auth_client, app, approved_estimate):
    est_id = approved_estimate["est_id"]
    r = auth_client.post("/finance/estimates/%d/convert" % est_id,
                         data={"_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)
    assert r.status_code == 200

    import models.database as db
    with app.app_context():
        est = db.get_estimate(est_id)
        assert est["invoice_id"], "converting produced no invoice"
        inv = db.get_invoice(est["invoice_id"])
        assert inv, "the estimate points at an invoice that does not exist"
        assert float(inv["total"] or 0) > 0, "the invoice carries no money"


def test_converting_twice_does_not_bill_the_client_twice(auth_client, app,
                                                         approved_estimate):
    """Two clicks on Convert. The second must return the SAME invoice, not
    raise a second one - a clinic that bills a client twice for one quote loses
    the client, and finds out weeks later."""
    est_id = approved_estimate["est_id"]
    for _ in range(2):
        auth_client.post("/finance/estimates/%d/convert" % est_id,
                         data={"_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)

    import models.database as db
    with app.app_context():
        conn = db.get_db()
        n = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE owner_id=?",
            (approved_estimate["owner_id"],)).fetchone()[0]
        conn.close()
    assert n == 1, "converting twice raised %d invoices for one estimate" % n


def test_an_unapproved_estimate_is_refused_out_loud(auth_client, app,
                                                    approved_estimate):
    """A draft quotation must not turn into a bill. And the refusal has to be
    visible - a silent no-op looks identical to success on this screen."""
    import models.database as db
    est_id = approved_estimate["est_id"]
    with app.app_context():
        conn = db.get_db()
        conn.execute("UPDATE estimates SET status='Draft', invoice_id=NULL"
                     " WHERE id=?", (est_id,))
        conn.commit()
        conn.close()

    r = auth_client.post("/finance/estimates/%d/convert" % est_id,
                         data={"_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)
    body = r.get_data(as_text=True)
    assert "approved" in body.lower() or "معتمد" in body, (
        "a draft estimate was refused silently - nothing on screen says why")

    with app.app_context():
        assert not db.get_estimate(est_id)["invoice_id"], (
            "a draft estimate was converted into an invoice")


def test_a_missing_estimate_does_not_500(auth_client):
    r = auth_client.post("/finance/estimates/999999/convert",
                         data={"_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)
    assert r.status_code in (200, 404), "converting a missing estimate crashed"
