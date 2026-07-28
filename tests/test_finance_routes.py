# -*- coding: utf-8 -*-
"""Finance + service-catalog write routes: does the MONEY come out right?

Every test here POSTs through the real HTTP route and then reads the database
back. Nothing asserts a bare 200 — a route that renders fine while storing the
wrong number is the exact failure this module has produced before (every
accounting figure reporting zero against 393 invoices).

Expected money values are computed independently in the test, at 2dp, and
compared against what the route stored. Where a figure is a derived total
(invoice header vs. its own lines) both sides are read from the database so a
shared-bug can't make them agree by construction.

SQLite, no network.
"""
import re
from datetime import date

import pytest

import models.database as db
from models.security import _CSRF_SESSION_KEY


# ─── helpers ──────────────────────────────────────────────────────────────────

def _csrf(client):
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _owner(name="Finance Route Owner", phone="01099000001"):
    conn = db.get_db()
    with conn:
        oid = conn.execute(
            "INSERT INTO owners (full_name, phone, whatsapp_phone) VALUES (?,?,?)",
            (name, phone, phone),
        ).lastrowid
    conn.close()
    return oid


def _row(sql, params=()):
    conn = db.get_db()
    r = conn.execute(sql, params).fetchone()
    conn.close()
    return r


def _rows(sql, params=()):
    conn = db.get_db()
    rs = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rs]


# The invoice used by most tests. Three lines with per-line discounts, a
# percentage header discount and VAT — i.e. every arithmetic step at once.
#
#   L1  3    x 150.00  -10%  -> 450.00 - 45.00 = 405.00
#   L2  1    x  99.99    0%  ->                   99.99
#   L3  2.5  x  40.40   -5%  -> 101.00 -  5.05 =  95.95
#   subtotal                                     600.94
#   header discount 7.5%   -> round(45.0705, 2) = 45.07
#   tax 14% on 555.87      -> round(77.8218, 2) = 77.82
#   total                                        633.69
_LINES = [
    ("Consultation",   "3",   "150.00", "10", "service"),
    ("Rabies vaccine", "1",    "99.99",  "0", "product"),
    ("Lab panel",      "2.5",  "40.40",  "5", "service"),
]
_EXPECTED_LINE_TOTALS = [405.00, 99.99, 95.95]
_EXPECTED_SUBTOTAL = 600.94
_EXPECTED_DISCOUNT = 45.07
_EXPECTED_TAX = 77.82
_EXPECTED_TOTAL = 633.69


def _make_invoice(auth_client, owner_id, issue_date=None):
    """POST the standard invoice through /finance/invoices/new. Returns its id."""
    form = {
        "owner_id": str(owner_id),
        "issue_date": issue_date or date.today().isoformat(),
        "discount_type": "percent",
        "discount_value": "7.5",
        "tax_rate": "14",
        "notes": "route test invoice",
        "description[]": [l[0] for l in _LINES],
        "qty[]": [l[1] for l in _LINES],
        "unit_price[]": [l[2] for l in _LINES],
        "discount[]": [l[3] for l in _LINES],
        "line_type[]": [l[4] for l in _LINES],
    }
    r = _post(auth_client, "/finance/invoices/new", form)
    assert r.status_code == 200
    inv = _row("SELECT * FROM invoices WHERE owner_id=? ORDER BY id DESC LIMIT 1",
               (owner_id,))
    assert inv is not None, "POST /finance/invoices/new wrote no invoice row"
    return inv["id"]


# ═══ INVOICE ARITHMETIC ═══════════════════════════════════════════════════════

def test_invoice_header_reconciles_with_its_own_lines(auth_client):
    """subtotal/discount/tax/total must each equal the independent computation,
    and the header subtotal must equal the sum of the stored line totals."""
    owner_id = _owner("Reconcile Owner", "01099000010")
    inv_id = _make_invoice(auth_client, owner_id)

    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    lines = _rows("SELECT * FROM invoice_lines WHERE invoice_id=? ORDER BY id", (inv_id,))

    assert len(lines) == 3, "a line was silently dropped"
    assert [round(l["total"], 2) for l in lines] == _EXPECTED_LINE_TOTALS

    line_sum = round(sum(round(l["total"], 2) for l in lines), 2)
    assert round(inv["subtotal"], 2) == line_sum, (
        f"invoice header subtotal {inv['subtotal']} != sum of its lines {line_sum}")
    assert round(inv["subtotal"], 2) == _EXPECTED_SUBTOTAL
    assert round(inv["discount_amount"], 2) == _EXPECTED_DISCOUNT
    assert round(inv["tax_amount"], 2) == _EXPECTED_TAX
    assert round(inv["total"], 2) == _EXPECTED_TOTAL

    # The identity the books rest on.
    assert round(inv["subtotal"] - inv["discount_amount"] + inv["tax_amount"], 2) \
        == round(inv["total"], 2)
    assert round(inv["due_amount"], 2) == _EXPECTED_TOTAL
    assert inv["status"] == "Unpaid"


def test_value_discount_is_subtracted_not_treated_as_a_percentage(auth_client):
    owner_id = _owner("Value Discount Owner", "01099000011")
    form = {
        "owner_id": str(owner_id),
        "issue_date": date.today().isoformat(),
        "discount_type": "value",
        "discount_value": "50",
        "tax_rate": "0",
        "description[]": ["Surgery"],
        "qty[]": ["1"],
        "unit_price[]": ["800.00"],
        "discount[]": ["0"],
        "line_type[]": ["service"],
    }
    _post(auth_client, "/finance/invoices/new", form)
    inv = _row("SELECT * FROM invoices WHERE owner_id=? ORDER BY id DESC LIMIT 1",
               (owner_id,))
    assert round(inv["discount_amount"], 2) == 50.00
    assert round(inv["total"], 2) == 750.00


def test_invoice_with_no_lines_is_rejected(auth_client):
    owner_id = _owner("Empty Invoice Owner", "01099000012")
    before = _row("SELECT COUNT(*) c FROM invoices")["c"]
    _post(auth_client, "/finance/invoices/new", {
        "owner_id": str(owner_id),
        "issue_date": date.today().isoformat(),
        "description[]": ["   "],
        "qty[]": ["1"],
        "unit_price[]": ["10"],
        "discount[]": ["0"],
        "line_type[]": ["service"],
    })
    assert _row("SELECT COUNT(*) c FROM invoices")["c"] == before, \
        "an invoice with no usable lines was still written"


# ═══ PAYMENT / SETTLEMENT ═════════════════════════════════════════════════════

def test_paying_in_instalments_settles_the_invoice_to_paid(auth_client):
    """633.69 in three 211.23 instalments must end Paid with due below half a
    piastre — the float-residue case that used to strand ~1 in 7 invoices on
    'Partial' while the screen showed 0.00 due."""
    owner_id = _owner("Instalment Owner", "01099000020")
    inv_id = _make_invoice(auth_client, owner_id)

    for _ in range(3):
        _post(auth_client, f"/finance/invoices/{inv_id}/pay",
              {"amount": "211.23", "method": "Cash"})

    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    assert round(inv["paid_amount"], 2) == _EXPECTED_TOTAL
    assert abs(inv["due_amount"]) < 0.005, \
        f"due_amount {inv['due_amount']!r} did not settle to zero"
    assert inv["status"] == "Paid", \
        f"fully paid invoice stuck on {inv['status']!r}"


def test_partial_payment_leaves_the_exact_remainder_due(auth_client):
    owner_id = _owner("Partial Owner", "01099000021")
    inv_id = _make_invoice(auth_client, owner_id)

    _post(auth_client, f"/finance/invoices/{inv_id}/pay",
          {"amount": "200.00", "method": "Card"})

    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    assert round(inv["paid_amount"], 2) == 200.00
    assert round(inv["due_amount"], 2) == round(_EXPECTED_TOTAL - 200.00, 2)
    assert inv["status"] == "Partial"


def test_overpayment_is_clamped_to_the_invoice_total(auth_client):
    owner_id = _owner("Overpay Owner", "01099000022")
    inv_id = _make_invoice(auth_client, owner_id)

    _post(auth_client, f"/finance/invoices/{inv_id}/pay",
          {"amount": "1000.00", "method": "Cash"})

    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    assert round(inv["paid_amount"], 2) == _EXPECTED_TOTAL, \
        "paid_amount exceeded the invoice total"
    assert round(inv["due_amount"], 2) == 0.0
    assert inv["status"] == "Paid"


def test_zero_payment_is_rejected(auth_client):
    owner_id = _owner("Zero Pay Owner", "01099000023")
    inv_id = _make_invoice(auth_client, owner_id)
    _post(auth_client, f"/finance/invoices/{inv_id}/pay", {"amount": "0"})
    inv = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))
    assert round(inv["paid_amount"], 2) == 0.0
    assert inv["status"] == "Unpaid"


def test_payment_awards_loyalty_points_once(auth_client):
    """1 point per 10 EGP, credited to the owner's balance and journalled."""
    owner_id = _owner("Loyalty Owner", "01099000024")
    inv_id = _make_invoice(auth_client, owner_id)

    _post(auth_client, f"/finance/invoices/{inv_id}/pay", {"amount": "250.00"})

    pts = _rows("SELECT * FROM loyalty_points WHERE owner_id=? AND ref_id=?",
                (owner_id, inv_id))
    assert len(pts) == 1
    assert pts[0]["points"] == 25, f"expected 25 points for 250 EGP, got {pts[0]['points']}"
    bal = _row("SELECT COALESCE(loyalty_balance,0) b FROM owners WHERE id=?",
               (owner_id,))["b"]
    assert bal == 25


# ═══ CREDIT NOTES — the reverse direction ═════════════════════════════════════

def test_full_credit_note_reverses_the_invoice_to_a_net_of_zero(auth_client):
    owner_id = _owner("Credit Note Owner", "01099000030")
    inv_id = _make_invoice(auth_client, owner_id)
    _post(auth_client, f"/finance/invoices/{inv_id}/pay",
          {"amount": str(_EXPECTED_TOTAL)})

    r = _post(auth_client, f"/finance/invoices/{inv_id}/credit-note",
              {"amount": str(_EXPECTED_TOTAL), "reason": "Wrong pet charged"})
    assert r.status_code == 200

    credit = dict(_row(
        "SELECT * FROM invoices WHERE owner_id=? AND id<>? ORDER BY id DESC LIMIT 1",
        (owner_id, inv_id)))
    original = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))

    assert round(credit["total"], 2) == -_EXPECTED_TOTAL, \
        "credit note total is not the negative of the invoice it reverses"
    assert round(credit["subtotal"], 2) == -_EXPECTED_TOTAL
    assert round(credit["total"] + original["total"], 2) == 0.0, \
        "invoice + credit note do not net to zero"

    clines = _rows("SELECT * FROM invoice_lines WHERE invoice_id=?", (credit["id"],))
    assert len(clines) == 1
    assert clines[0]["line_type"] == "credit"
    assert round(clines[0]["total"], 2) == -_EXPECTED_TOTAL
    assert "Wrong pet charged" in (clines[0]["description"] or "")

    assert original["status"] == "Cancelled", \
        f"fully credited invoice left on {original['status']!r}"


def test_partial_credit_note_does_not_cancel_the_original(auth_client):
    owner_id = _owner("Partial Credit Owner", "01099000031")
    inv_id = _make_invoice(auth_client, owner_id)
    _post(auth_client, f"/finance/invoices/{inv_id}/pay",
          {"amount": str(_EXPECTED_TOTAL)})

    _post(auth_client, f"/finance/invoices/{inv_id}/credit-note",
          {"amount": "100.00", "reason": "Returned one vial"})

    credit = dict(_row(
        "SELECT * FROM invoices WHERE owner_id=? AND id<>? ORDER BY id DESC LIMIT 1",
        (owner_id, inv_id)))
    original = dict(_row("SELECT * FROM invoices WHERE id=?", (inv_id,)))

    assert round(credit["total"], 2) == -100.00
    assert original["status"] != "Cancelled", \
        "a 100 EGP credit against a 633.69 invoice cancelled the whole invoice"
    assert round(credit["total"] + original["total"], 2) == \
        round(_EXPECTED_TOTAL - 100.00, 2)


def test_credit_note_of_zero_is_rejected(auth_client):
    owner_id = _owner("Zero Credit Owner", "01099000032")
    inv_id = _make_invoice(auth_client, owner_id)
    before = _row("SELECT COUNT(*) c FROM invoices")["c"]
    _post(auth_client, f"/finance/invoices/{inv_id}/credit-note", {"amount": "0"})
    assert _row("SELECT COUNT(*) c FROM invoices")["c"] == before, \
        "a zero-value credit note was written anyway"


def test_credit_note_is_audited(auth_client):
    owner_id = _owner("Audited Credit Owner", "01099000033")
    inv_id = _make_invoice(auth_client, owner_id)
    _post(auth_client, f"/finance/invoices/{inv_id}/credit-note", {"amount": "25.00"})
    hits = _rows(
        "SELECT * FROM audit_log WHERE action='credit_note' AND entity_id=?",
        (str(inv_id),))
    assert hits, "credit note left no audit trail"


# ═══ EXPENSES ═════════════════════════════════════════════════════════════════

def test_expense_post_writes_every_field(auth_client):
    _post(auth_client, "/finance/expenses", {
        "category": "Medications",
        "description": "Insulin restock",
        "amount": "1234.56",
        "vendor": "Cairo Vet Supplies",
        "receipt_ref": "RCP-9911",
        "expense_date": "2019-05-05",
        "notes": "quarterly order",
    })
    exp = _row("SELECT * FROM expenses WHERE receipt_ref='RCP-9911'")
    assert exp is not None, "POST /finance/expenses wrote no row"
    exp = dict(exp)
    assert round(exp["amount"], 2) == 1234.56
    assert exp["category"] == "Medications"
    assert exp["description"] == "Insulin restock"
    assert exp["vendor"] == "Cairo Vet Supplies"
    assert exp["expense_date"] == "2019-05-05"


def test_expense_without_amount_or_description_is_rejected(auth_client):
    before = _row("SELECT COUNT(*) c FROM expenses")["c"]
    _post(auth_client, "/finance/expenses",
          {"description": "No money", "amount": "0"})
    _post(auth_client, "/finance/expenses",
          {"description": "   ", "amount": "10"})
    assert _row("SELECT COUNT(*) c FROM expenses")["c"] == before


def test_expenses_list_total_equals_the_sum_of_the_rows_shown(auth_client):
    """The footer total is what a clinic reconciles against; it must be the
    exact sum of the filtered rows, not of everything in the table."""
    window = "2019-06-0"
    amounts = [100.10, 250.25, 33.33]
    for n, amt in enumerate(amounts):
        _post(auth_client, "/finance/expenses", {
            "category": "Utilities",
            "description": f"Window expense {n}",
            "amount": str(amt),
            "expense_date": f"{window}{n + 1}",
        })
    # Something outside the window that must NOT be counted.
    _post(auth_client, "/finance/expenses", {
        "category": "Utilities", "description": "Outside window",
        "amount": "9999.99", "expense_date": "2019-07-01"})

    page = auth_client.get("/finance/expenses?date_from=2019-06-01&date_to=2019-06-30")
    assert page.status_code == 200
    html = page.get_data(as_text=True)

    expected = round(sum(amounts), 2)
    assert f"{expected:,.2f}" in html, \
        f"expenses footer does not show the {expected:,.2f} it filtered to"
    assert "9,999.99" not in html, "an out-of-window expense leaked into the list"


# ═══ REPORTS ══════════════════════════════════════════════════════════════════

def test_reports_figures_match_the_underlying_rows(auth_client):
    """P&L over an isolated historical window: every figure on the page has to
    be derivable from the rows in that window and nothing else."""
    day = "2018-03-14"
    owner_id = _owner("Report Owner", "01099000040")
    inv_id = _make_invoice(auth_client, owner_id, issue_date=day)
    _post(auth_client, f"/finance/invoices/{inv_id}/pay",
          {"amount": str(_EXPECTED_TOTAL)})
    _post(auth_client, "/finance/expenses", {
        "category": "Rent", "description": "Report window rent",
        "amount": "200.00", "expense_date": day})

    page = auth_client.get(f"/finance/reports?date_from={day}&date_to={day}")
    assert page.status_code == 200
    html = page.get_data(as_text=True)

    summary = db.get_finance_summary(date_from=day, date_to=day)
    assert round(summary["invoiced"], 2) == _EXPECTED_TOTAL
    assert round(summary["revenue"], 2) == _EXPECTED_TOTAL
    assert round(summary["expenses"], 2) == 200.00
    assert round(summary["net"], 2) == round(_EXPECTED_TOTAL - 200.00, 2)
    assert summary["invoice_count"] == 1

    # Revenue-by-line-type, grouped: service 405.00 + 95.95, product 99.99.
    by_type = {r["line_type"]: round(r["total"], 2) for r in _rows(
        "SELECT il.line_type, COALESCE(SUM(il.total),0) total FROM invoice_lines il "
        "JOIN invoices i ON i.id=il.invoice_id "
        "WHERE i.issue_date=? AND i.status!='Cancelled' GROUP BY il.line_type", (day,))}
    assert by_type == {"service": 500.95, "product": 99.99}
    # …and those are the numbers rendered ({:,.0f} in the template).
    assert "{:,.0f}".format(500.95) in html
    assert "{:,.0f}".format(200.0) in html


def test_reports_export_xlsx_returns_a_workbook_that_reconciles(auth_client):
    """The export must be a real .xlsx whose Net column sums to the invoice
    totals in the window — not a redirect back to the report page."""
    openpyxl = pytest.importorskip("openpyxl")
    day = "2018-04-11"
    owner_id = _owner("Xlsx Owner", "01099000041")
    _make_invoice(auth_client, owner_id, issue_date=day)

    resp = auth_client.get(f"/finance/reports/export/xlsx?date_from={day}&date_to={day}")
    assert resp.status_code == 200, "xlsx export did not return the file"
    assert "spreadsheetml" in resp.headers.get("Content-Type", ""), (
        "xlsx export redirected instead of returning a workbook — the query "
        "references invoice columns that do not exist")

    from io import BytesIO
    wb = openpyxl.load_workbook(BytesIO(resp.get_data()))
    ws = wb.active
    headers = [c.value for c in ws[3]]
    assert headers[:4] == ["Invoice #", "Date", "Owner", "Total"]

    data = [r for r in ws.iter_rows(min_row=4, values_only=True)
            if r[0] and r[0] != "TOTAL"]
    assert len(data) == 1, f"expected 1 invoice in the window, got {len(data)}"
    inv_no, d, owner_name, gross, disc, tax, net, status = data[0][:8]
    assert d == day
    assert owner_name == "Xlsx Owner"
    assert round(gross, 2) == _EXPECTED_SUBTOTAL
    assert round(disc, 2) == _EXPECTED_DISCOUNT
    assert round(tax, 2) == _EXPECTED_TAX
    assert round(net, 2) == _EXPECTED_TOTAL
    assert round(gross - disc + tax, 2) == round(net, 2), \
        "the exported columns do not reconcile with each other"
    assert status == "Unpaid"


# ═══ WHATSAPP INVOICE ═════════════════════════════════════════════════════════

def test_invoice_whatsapp_quotes_the_real_figures(auth_client, monkeypatch):
    owner_id = _owner("WA Owner", "01099000050")
    inv_id = _make_invoice(auth_client, owner_id)
    _post(auth_client, f"/finance/invoices/{inv_id}/pay", {"amount": "100.00"})

    sent = {}

    def _fake(phone, message, owner_id=None, template_name=""):
        sent.update(phone=phone, message=message, owner_id=owner_id)
        return "Sent"

    import blueprints.whatsapp.routes as wa
    monkeypatch.setattr(wa, "_send_and_log", _fake)

    r = _post(auth_client, f"/finance/invoices/{inv_id}/whatsapp", {})
    assert r.status_code == 200
    assert sent, "no WhatsApp message was produced"
    assert sent["phone"] == "01099000050"
    msg = sent["message"]
    assert f"{_EXPECTED_TOTAL:.2f}" in msg, "message does not quote the invoice total"
    assert "100.00" in msg, "message does not quote the amount paid"
    assert f"{round(_EXPECTED_TOTAL - 100.00, 2):.2f}" in msg, \
        "message does not quote the balance due"


def test_invoice_whatsapp_without_a_phone_sends_nothing(auth_client, monkeypatch):
    conn = db.get_db()
    with conn:
        owner_id = conn.execute(
            "INSERT INTO owners (full_name, phone) VALUES ('Phoneless Owner', '')"
        ).lastrowid
    conn.close()
    inv_id = _make_invoice(auth_client, owner_id)

    calls = []
    import blueprints.whatsapp.routes as wa
    monkeypatch.setattr(wa, "_send_and_log",
                        lambda *a, **k: calls.append(a) or "Sent")

    _post(auth_client, f"/finance/invoices/{inv_id}/whatsapp", {})
    assert calls == [], "tried to send an invoice to an owner with no phone"


# ═══ SERVICE / PRICE CATALOG ══════════════════════════════════════════════════

def test_catalog_save_creates_then_updates_the_same_row(auth_client):
    _post(auth_client, "/catalog/save", {
        "code": "cat-rt-1", "name": "Catalog Route Service",
        "category": "Surgery", "standard_price": "250.50",
        "tax_rate": "14", "duration_min": "45", "is_active": "1",
    })
    svc = _row("SELECT * FROM service_catalog WHERE code='CAT-RT-1'")
    assert svc is not None, "POST /catalog/save wrote no service"
    svc = dict(svc)
    assert svc["code"] == "CAT-RT-1", "code was not upper-cased"
    assert round(svc["standard_price"], 2) == 250.50
    assert round(svc["tax_rate"], 2) == 14.0
    assert svc["duration_min"] == 45
    assert svc["category"] == "Surgery"

    _post(auth_client, "/catalog/save", {
        "svc_id": str(svc["id"]), "code": "CAT-RT-1",
        "name": "Catalog Route Service", "category": "Surgery",
        "standard_price": "300.00", "tax_rate": "14",
        "duration_min": "45", "is_active": "1",
    })
    again = _rows("SELECT * FROM service_catalog WHERE code='CAT-RT-1'")
    assert len(again) == 1, "the update created a second row instead of editing"
    assert round(again[0]["standard_price"], 2) == 300.00


def test_catalog_save_rejects_a_duplicate_code(auth_client):
    for name in ("First Dup Service", "Second Dup Service"):
        _post(auth_client, "/catalog/save", {
            "code": "DUP-1", "name": name, "category": "Laboratory",
            "standard_price": "10", "is_active": "1"})
    rows = _rows("SELECT * FROM service_catalog WHERE code='DUP-1'")
    assert len(rows) == 1, "a duplicate service code was accepted"
    assert rows[0]["name"] == "First Dup Service"


def test_catalog_save_requires_a_name(auth_client):
    before = _row("SELECT COUNT(*) c FROM service_catalog")["c"]
    _post(auth_client, "/catalog/save", {"code": "NONAME", "name": "  "})
    assert _row("SELECT COUNT(*) c FROM service_catalog")["c"] == before


def test_catalog_toggle_flips_active_without_losing_the_price(auth_client):
    _post(auth_client, "/catalog/save", {
        "code": "TOG-1", "name": "Toggle Service", "category": "Grooming",
        "standard_price": "77.77", "tax_rate": "5", "duration_min": "30",
        "is_active": "1"})
    svc = dict(_row("SELECT * FROM service_catalog WHERE code='TOG-1'"))
    assert svc["is_active"] == 1

    _post(auth_client, f"/catalog/{svc['id']}/toggle", {})
    off = dict(_row("SELECT * FROM service_catalog WHERE id=?", (svc["id"],)))
    assert off["is_active"] == 0
    assert round(off["standard_price"], 2) == 77.77, "toggling wiped the price"
    assert off["name"] == "Toggle Service"
    assert off["duration_min"] == 30

    _post(auth_client, f"/catalog/{svc['id']}/toggle", {})
    on = dict(_row("SELECT * FROM service_catalog WHERE id=?", (svc["id"],)))
    assert on["is_active"] == 1


def test_catalog_api_list_hides_inactive_services(auth_client):
    _post(auth_client, "/catalog/save", {
        "code": "API-ON", "name": "Api Active Service", "category": "Boarding",
        "standard_price": "12.00", "is_active": "1"})
    _post(auth_client, "/catalog/save", {
        "code": "API-OFF", "name": "Api Inactive Service", "category": "Boarding",
        "standard_price": "13.00"})   # is_active absent -> 0

    data = auth_client.get("/catalog/api/list?category=Boarding").get_json()
    codes = {s["code"] for s in data}
    assert "API-ON" in codes
    assert "API-OFF" not in codes, "api/list returned a deactivated service"
    active = next(s for s in data if s["code"] == "API-ON")
    assert round(active["standard_price"], 2) == 12.00


def test_catalog_api_get_returns_the_row_and_404s_otherwise(auth_client):
    _post(auth_client, "/catalog/save", {
        "code": "API-GET", "name": "Api Get Service", "category": "Treatment",
        "standard_price": "199.99", "is_active": "1"})
    svc = dict(_row("SELECT * FROM service_catalog WHERE code='API-GET'"))

    got = auth_client.get(f"/catalog/api/get/{svc['id']}")
    assert got.status_code == 200
    body = got.get_json()
    assert body["name"] == "Api Get Service"
    assert round(body["standard_price"], 2) == 199.99

    missing = auth_client.get("/catalog/api/get/99999999")
    assert missing.status_code == 404
