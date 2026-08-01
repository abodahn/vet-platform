# -*- coding: utf-8 -*-
"""The app survives money arriving as Decimal.

docs/MONEY_PRECISION.md names this the single largest risk in the whole money
exercise, and names it precisely:

    "after this migration, SQLite and PostgreSQL behave differently. On
     PostgreSQL every amount read from the database becomes a Decimal object;
     on SQLite it stays a float. Your test suite runs on SQLite. Your tests
     will pass and production can still break."

This file is the answer to that. It feeds Decimal values through the code that
handles money, on SQLite, so the divergence is testable BEFORE the NUMERIC
migration is applied rather than discovered by a clinic afterwards.

These tests are the gate on that migration. It stays unapplied until they pass,
which is the order docs/MONEY_PRECISION.md prescribes: make the application
Decimal-safe first, change the column types at the PostgreSQL cutover.
"""
from decimal import Decimal

import pytest

from models import excel_export


D = Decimal


# ── Excel export ─────────────────────────────────────────────────────────────

@pytest.mark.skipif(not excel_export._OPENPYXL_OK, reason="openpyxl not installed")
def test_excel_export_totals_decimal_money():
    """The concrete bug: three isinstance checks tested (int, float) only.

    A Decimal is neither, so every amount was treated as text — right-alignment
    lost, and the TOTAL row silently skipping every money column. A clinic would
    have got an export whose totals row was blank or wrong, which is exactly the
    "financial exports produce nothing" failure already fixed once in this
    codebase from a different cause.
    """
    rows = [("INV-001", D("120.50")), ("INV-002", D("79.50"))]
    buf = excel_export.make_workbook("Invoices", ["Invoice", "Total"], rows)
    assert buf is not None

    import openpyxl
    from io import BytesIO
    ws = openpyxl.load_workbook(BytesIO(buf.getvalue())).active
    values = [c.value for row in ws.iter_rows() for c in row]
    assert 200 in [v for v in values if isinstance(v, (int, float, Decimal))] or \
           D("200.00") in [v for v in values if isinstance(v, Decimal)], \
        "the TOTAL row did not sum the Decimal money column"


@pytest.mark.skipif(not excel_export._OPENPYXL_OK, reason="openpyxl not installed")
def test_excel_export_survives_mixed_float_and_decimal():
    """During the cutover a report can join a migrated table to an unmigrated
    one and get both types in the same column."""
    rows = [("A", D("10.25")), ("B", 5.75)]
    assert excel_export.make_workbook("Mixed", ["Item", "Amount"], rows) is not None


# ── JSON ─────────────────────────────────────────────────────────────────────

def test_jsonify_does_not_500_on_decimal(app):
    """Flask's default JSON encoder raises TypeError on Decimal. Any endpoint
    returning an amount would become a 500 the day PostgreSQL is switched on."""
    from flask import jsonify
    with app.test_request_context():
        body = jsonify({"total": D("120.50")}).get_data(as_text=True)
    assert "120.50" in body or "120.5" in body


# ── arithmetic, the quiet one ────────────────────────────────────────────────

def test_money_arithmetic_helper_accepts_both_types(app):
    """float + Decimal raises TypeError in Python. Any place that adds a
    hardcoded 0.0 or a tax rate to a database amount breaks on PostgreSQL, and
    no SQLite test can reach it."""
    from models.money import to_decimal

    assert to_decimal(D("10.25")) + to_decimal(5.75) == D("16.00")
    assert to_decimal("12.10") == D("12.10")
    assert to_decimal(None) == D("0")
    assert to_decimal("") == D("0")
    # Binary float noise must not survive the conversion.
    assert to_decimal(0.1) + to_decimal(0.2) == D("0.30")


def test_money_rounds_half_up_not_bankers(app):
    """Python rounds 2.5 to 2 (banker's rounding). An invoice that rounds
    0.125 down where the printed receipt rounds it up is a dispute at the
    counter."""
    from models.money import to_decimal
    assert to_decimal("0.125", places=2) == D("0.13")
    assert to_decimal("0.135", places=2) == D("0.14")


# ── rendering ────────────────────────────────────────────────────────────────

def test_money_filter_renders_both_types_identically(app):
    """A page must not show 120.50 for one clinic and 120.5 for another
    depending on which database engine it happens to run on."""
    render = app.jinja_env.filters["money"]
    assert render(D("120.50")) == render(120.50) == "120.50"
    assert render(0) == "0.00"
    assert render(None) == "0.00"
    assert render(1234.5) == "1234.50"
