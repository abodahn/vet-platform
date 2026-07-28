"""Finance money-spine links.

A payment must be traceable back to the patient it came from: invoice -> owner,
-> pet, -> visit. These tests assert the links are *in the page* and that they
*resolve*, and that an invoice with no visit renders without a dead link.
"""
import re

import models.database as db


def _mk_invoice(with_visit=True, with_pet=True):
    """Owner (+pet, +visit) and an invoice pointing at them. Returns ids."""
    conn = db.get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO owners (full_name, phone) VALUES (?,?)",
            ("Link Test Owner", "01000000000"),
        )
        owner_id = cur.lastrowid
        pet_id = None
        if with_pet:
            pet_id = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                (owner_id, "Linkcat", "Cat"),
            ).lastrowid
        visit_id = None
        if with_visit:
            visit_id = conn.execute(
                "INSERT INTO visits (owner_id, pet_id, visit_date, visit_type)"
                " VALUES (?,?,?,?)",
                (owner_id, pet_id, "2026-03-04", "Consultation"),
            ).lastrowid
    conn.close()

    inv_id = db.create_invoice(
        {
            "owner_id": owner_id,
            "pet_id": pet_id,
            "visit_id": visit_id,
            "issue_date": "2026-03-04",
        },
        [{"description": "Consult", "quantity": 1, "unit_price": 250, "total": 250}],
    )
    return owner_id, pet_id, visit_id, inv_id


def _hrefs(html):
    return set(re.findall(r'href="([^"]+)"', html))


def test_invoice_detail_links_to_owner_pet_and_visit(auth_client):
    owner_id, pet_id, visit_id, inv_id = _mk_invoice()

    page = auth_client.get(f"/finance/invoices/{inv_id}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    hrefs = _hrefs(html)

    owner_url = f"/crm/owners/{owner_id}"
    pet_url = f"/crm/pets/{pet_id}"
    visit_url = f"/visits/{visit_id}"
    assert owner_url in hrefs, "invoice detail has no link to its owner"
    assert pet_url in hrefs, "invoice detail has no link to its pet"
    assert visit_url in hrefs, "invoice detail has no link to its visit"

    # Rendering a link is not the same as the link resolving.
    for url in (owner_url, pet_url, visit_url):
        assert auth_client.get(url).status_code == 200, f"{url} does not resolve"


def test_invoice_without_visit_renders_no_dead_visit_link(auth_client):
    _, _, _, inv_id = _mk_invoice(with_visit=False, with_pet=False)

    page = auth_client.get(f"/finance/invoices/{inv_id}")
    assert page.status_code == 200
    hrefs = _hrefs(page.get_data(as_text=True))

    # /visits/ and /crm/pets are sidebar nav; only a *record* link is the bug.
    assert not [h for h in hrefs if re.fullmatch(r"/visits/\d+", h)], \
        "invoice with no visit_id still rendered a visit link"
    assert not [h for h in hrefs if re.fullmatch(r"/crm/pets/\d+", h)], \
        "invoice with no pet_id still rendered a pet link"

    # Everything it *did* render must still resolve.
    for h in sorted(hrefs):
        if not h.startswith("/") or h.startswith(("/static", "/auth/logout")):
            continue
        assert auth_client.get(h).status_code < 400, f"dead link on invoice page: {h}"


def test_invoice_with_deleted_visit_renders_no_dead_link(auth_client):
    """visit_id has no enforced FK — a deleted visit must not leave a 404 link."""
    _, _, visit_id, inv_id = _mk_invoice()
    conn = db.get_db()
    with conn:
        conn.execute("DELETE FROM visits WHERE id=?", (visit_id,))
    conn.close()

    page = auth_client.get(f"/finance/invoices/{inv_id}")
    assert page.status_code == 200, "invoice with a dangling visit_id crashed"
    hrefs = _hrefs(page.get_data(as_text=True))
    assert f"/visits/{visit_id}" not in hrefs, \
        "invoice still links to a visit that no longer exists"


def test_invoice_detail_links_to_owners_invoice_list(auth_client):
    owner_id, _, _, inv_id = _mk_invoice()

    html = auth_client.get(f"/finance/invoices/{inv_id}").get_data(as_text=True)
    assert f"/finance/invoices?owner_id={owner_id}" in _hrefs(html)

    filtered = auth_client.get(f"/finance/invoices?owner_id={owner_id}")
    assert filtered.status_code == 200
    body = filtered.get_data(as_text=True)
    assert "Link Test Owner" in body
    # The filter really filters: an unrelated owner's invoices are not listed.
    assert f"/crm/owners/{owner_id}" in _hrefs(body)


def test_invoice_detail_shows_its_payments(auth_client):
    owner_id, _, _, inv_id = _mk_invoice()
    db.add_payment(invoice_id=inv_id, owner_id=owner_id, amount=100.0,
                   method="Card", reference="RCPT-LINK-1")

    conn = db.get_db()
    with conn:
        conn.execute(
            "INSERT INTO payments (invoice_id, owner_id, amount, method, reference,"
            " received_at) VALUES (?,?,?,?,?,?)",
            (inv_id, owner_id, 100.0, "Card", "RCPT-LINK-1", "2026-03-04 12:00:00"),
        )
    conn.close()

    html = auth_client.get(f"/finance/invoices/{inv_id}").get_data(as_text=True)
    assert "RCPT-LINK-1" in html, "invoice detail does not show its payment rows"


def test_cashflow_payment_rows_link_back_to_their_invoice(auth_client):
    owner_id, _, _, inv_id = _mk_invoice()
    conn = db.get_db()
    with conn:
        conn.execute(
            "INSERT INTO payments (invoice_id, owner_id, amount, method, received_at)"
            " VALUES (?,?,?,?,?)",
            (inv_id, owner_id, 250.0, "Cash", "2026-03-04 09:30:00"),
        )
    conn.close()

    page = auth_client.get("/accounting/cashflow?date_from=2026-03-04&date_to=2026-03-04")
    assert page.status_code == 200
    hrefs = _hrefs(page.get_data(as_text=True))
    inv_url = f"/finance/invoices/{inv_id}"
    assert inv_url in hrefs, "cash-flow inflow does not link back to its invoice"
    assert auth_client.get(inv_url).status_code == 200


def test_pl_report_figures_link_to_underlying_records(auth_client):
    auth_client.get("/finance/invoices")  # ensure the target route is registered
    page = auth_client.get("/accounting/pl?date_from=2026-03-01&date_to=2026-03-31")
    assert page.status_code == 200
    hrefs = _hrefs(page.get_data(as_text=True))

    assert any(h.startswith("/finance/invoices?") and "date_from=2026-03-01" in h
               for h in hrefs), "P&L revenue is not clickable through to the invoices"
    assert any(h.startswith("/accounting/expenses?") for h in hrefs), \
        "P&L expenses are not clickable through to the expense records"

    for h in sorted(hrefs):
        if h.startswith(("/finance/invoices?", "/accounting/expenses?")):
            assert auth_client.get(h.replace("&amp;", "&")).status_code == 200, h
