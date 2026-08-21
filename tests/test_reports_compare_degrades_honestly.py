# -*- coding: utf-8 -*-
"""The financial period comparison must be honest about its baseline.

Three separate ways it was not:

  * the previous window was built from `datetime.fromisoformat(...)`, so
    `prev_from` stringified to '1990-05-31T00:00:00'. Compared against an
    issue_date of '1990-05-31' that sorts the wrong way, and the previous
    period quietly lost its own first day;
  * when the previous period earned nothing the badge rendered as empty
    space, which next to a green revenue figure reads as "no change";
  * an empty date box 500'd the view.

Every window here is in 1990/1991, decades before any seeded or test-created
invoice, so the figures do not move when the rest of the suite runs first.
"""
import pytest

import models.database as db


# Current period: 10 days. Previous period must therefore be 05-31 → 06-09.
CUR_FROM, CUR_TO = "1990-06-10", "1990-06-19"
PREV_FROM, PREV_TO = "1990-05-31", "1990-06-09"

EMPTY_FROM, EMPTY_TO = "1991-06-10", "1991-06-19"

PHONE = "01099900199"          # unique to this file


def _text(resp):
    return resp.data.decode("utf-8", "replace")


@pytest.fixture(scope="module", autouse=True)
def old_invoices(app):
    """400 collected on the FIRST day of the previous period, 300 in the
    current one — a clean -25.0% that only comes out right if that first day
    is inside the window."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            oid = conn.execute(
                "INSERT INTO owners (full_name, phone) VALUES (?,?)",
                ("Compare Baseline", PHONE)).lastrowid
            pid = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                (oid, "Baseline", "Dog")).lastrowid
            for num, day, amount in (("INV-CMP-A", PREV_FROM, 400.0),
                                     ("INV-CMP-B", "1990-06-15", 300.0)):
                conn.execute(
                    "INSERT INTO invoices (invoice_number, owner_id, pet_id,"
                    " issue_date, subtotal, total, paid_amount, due_amount, status)"
                    " VALUES (?,?,?,?,?,?,?,?,'Paid')",
                    (num, oid, pid, day, amount, amount, amount, 0.0))
        conn.close()


def test_the_previous_period_starts_where_it_says_it_starts(auth_client):
    body = _text(auth_client.get(
        f"/reports/financial/compare?date_from={CUR_FROM}&date_to={CUR_TO}"))
    assert f"{PREV_FROM}" in body and f"{PREV_TO}" in body, \
        "the previous window is not the ten days immediately before the current one"
    assert "T00:00:00" not in body, \
        "a datetime leaked into a date field — it also breaks the issue_date compare"
    assert "25.0% vs prev period" in body, (
        "300 against a 400 baseline is -25.0%; a different number means the "
        f"invoice dated {PREV_FROM} fell outside the previous period")


def test_compare_says_so_when_there_is_no_previous_period(auth_client):
    body = _text(auth_client.get(
        f"/reports/financial/compare?date_from={EMPTY_FROM}&date_to={EMPTY_TO}"))
    assert "Comparison Mode" in body, "not the compare page"
    assert "no comparable" in body.lower(), (
        "the previous period is empty, so the change is undefined — the page "
        "renders nothing at all instead of saying so, which reads as 0%")


def test_an_empty_date_box_does_not_crash_the_comparison(auth_client):
    """Clearing From on the financial report and following Compare Periods."""
    r = auth_client.get("/reports/financial/compare?date_from=&date_to=")
    assert r.status_code == 200, "a blank date field returned a 500"
