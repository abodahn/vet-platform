# -*- coding: utf-8 -*-
"""Tests for scripts/seed/demo_showcase.py.

Everything here runs against a throwaway file in tmp_path. The one thing that
must never happen is the seeder writing to the configured application
database, so that guard gets its own test.
"""
import importlib.util
import os
import sys

import pytest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SEED_PY = os.path.join(_PLATFORM, "scripts", "seed", "demo_showcase.py")


def _load():
    """Import the seeder by path — scripts/ is not a package."""
    spec = importlib.util.spec_from_file_location("demo_showcase", _SEED_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["demo_showcase"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def seeder():
    return _load()


@pytest.fixture(scope="module")
def seeded(seeder, tmp_path_factory):
    """Seed once; the row-shape tests all read the same throwaway database."""
    import models.database as db
    saved = (db._db_path, db._PG_CONFIG, db._POOL)
    path = str(tmp_path_factory.mktemp("demo") / "demo.db")
    try:
        counts = seeder.run(path, quiet=True)
        yield path, counts
    finally:
        db._db_path, db._PG_CONFIG, db._POOL = saved


def _rows(path, sql, params=()):
    import sqlite3
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _count(path, table, where="1=1"):
    return _rows(path, f"SELECT COUNT(*) AS c FROM {table} WHERE {where}")[0]["c"]


# ── The safety guard ─────────────────────────────────────────────────────────

def test_refuses_the_configured_database(seeder):
    from config import Config
    with pytest.raises(SystemExit) as exc:
        seeder.resolve_guard(Config.DATABASE_PATH, force=False)
    assert "REFUS" in str(exc.value).upper()


def test_refusal_survives_a_relative_or_messy_path(seeder):
    from config import Config
    messy = os.path.join(os.path.dirname(Config.DATABASE_PATH), ".",
                         os.path.basename(Config.DATABASE_PATH))
    with pytest.raises(SystemExit):
        seeder.resolve_guard(messy, force=False)


def test_force_overrides_the_guard(seeder):
    from config import Config
    assert seeder.resolve_guard(Config.DATABASE_PATH, force=True) == \
        os.path.abspath(Config.DATABASE_PATH)


def test_other_paths_are_allowed(seeder, tmp_path):
    target = str(tmp_path / "somewhere.db")
    assert seeder.resolve_guard(target, force=False) == os.path.abspath(target)


def test_cli_exits_nonzero_on_the_real_database(seeder):
    from config import Config
    with pytest.raises(SystemExit) as exc:
        seeder.main(["--db", Config.DATABASE_PATH, "--quiet"])
    assert exc.value.code != 0


# ── Idempotency ──────────────────────────────────────────────────────────────

def test_running_twice_does_not_double_the_data(seeder, tmp_path):
    import models.database as db
    saved = (db._db_path, db._PG_CONFIG, db._POOL)
    try:
        path = str(tmp_path / "twice.db")
        first = seeder.run(path, quiet=True)
        second = seeder.run(path, quiet=True)
        assert first == second
        # And the tables themselves, not just the reported counts.
        for table in ("owners", "pets", "appointments", "visits", "invoices",
                      "payments", "ps_orders", "attendance_records", "users"):
            assert _count(path, table) > 0, table
        assert _count(path, "users", "username LIKE 'dr.%'") == 3
    finally:
        db._db_path, db._PG_CONFIG, db._POOL = saved


def test_wipe_leaves_the_admin_but_clears_demo_scope(seeder, tmp_path):
    import models.database as db
    saved = (db._db_path, db._PG_CONFIG, db._POOL)
    try:
        path = str(tmp_path / "wipe.db")
        seeder.run(path, quiet=True)
        seeder.run(path, wipe_only=True, quiet=True)
        for table in ("owners", "pets", "visits", "invoices", "payments"):
            assert _count(path, table) == 0, table
        assert _count(path, "users", "username = 'admin'") == 1
        assert _count(path, "users", "username LIKE 'dr.%'") == 0
    finally:
        db._db_path, db._PG_CONFIG, db._POOL = saved


# ── Arabic round-trip ────────────────────────────────────────────────────────

INVISIBLE = {chr(c) for c in
             (0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C,
              0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF)}


def test_arabic_is_present_and_carries_no_invisible_marks(seeded):
    path, _ = seeded
    checks = [("owners", "full_name_ar"), ("pets", "pet_name"),
              ("users", "full_name_ar"), ("items", "name_ar"),
              ("ps_products", "name_ar"), ("clinic", "name_ar"),
              ("appointments", "symptoms"), ("diagnoses", "notes")]
    arabic_seen = 0
    for table, col in checks:
        for row in _rows(path, f"SELECT {col} AS v FROM {table} WHERE {col} IS NOT NULL"):
            v = row["v"]
            assert not (set(v) & INVISIBLE), f"invisible mark in {table}.{col}: {v!r}"
            if any("؀" <= ch <= "ۿ" for ch in v):
                arabic_seen += 1
    assert arabic_seen > 100


def test_arabic_compares_equal_after_a_round_trip(seeded):
    path, _ = seeded
    literal = "عيادة أليفي البيطرية"
    stored = _rows(path, "SELECT name_ar FROM clinic WHERE id=1")[0]["name_ar"]
    assert stored == literal


def test_some_pet_names_are_arabic(seeded):
    path, _ = seeded
    names = [r["pet_name"] for r in _rows(path, "SELECT pet_name FROM pets")]
    arabic = [n for n in names if any("؀" <= ch <= "ۿ" for ch in n)]
    assert 10 <= len(arabic) < len(names), "expected a bilingual mix of pet names"


# ── The connected workflow the demo is meant to show ─────────────────────────

def test_appointment_to_visit_to_invoice_to_payment_chain(seeded):
    path, _ = seeded
    chained = _rows(path, """
        SELECT COUNT(DISTINCT a.id) AS c
        FROM appointments a
        JOIN visits   v ON v.appointment_id = a.id
        JOIN invoices i ON i.visit_id = v.id
        JOIN payments p ON p.invoice_id = i.id
    """)[0]["c"]
    assert chained > 50


def test_prescription_deducts_stock(seeded):
    path, _ = seeded
    chained = _rows(path, """
        SELECT COUNT(*) AS c
        FROM prescriptions p
        JOIN prescription_items pi ON pi.prescription_id = p.id
        JOIN stock_movements sm ON sm.reference_type = 'visit'
                               AND sm.reference_id = p.visit_id
                               AND sm.item_id = pi.item_id
        WHERE sm.movement_type = 'out'
    """)[0]["c"]
    assert chained > 50
    assert _count(path, "batches", "quantity < 0") == 0, "stock went negative"


def test_distribution_is_not_uniformly_perfect(seeded):
    """A dataset where everything is paid, present and normal proves nothing."""
    path, _ = seeded
    assert _count(path, "invoices", "status = 'Unpaid'") > 5
    assert _count(path, "invoices", "status = 'Partial'") > 5
    assert _count(path, "invoices", "status = 'Paid'") > 50
    assert _count(path, "appointments", "status = 'No-Show'") > 5
    assert _count(path, "appointments", "status = 'Cancelled'") > 5
    assert _count(path, "lab_results", "is_abnormal = 1") > 5
    assert _count(path, "attendance_records", "status = 'Absent'") > 5
    assert _count(path, "batches",
                  "expiry_date <= date('now','+60 day')") > 0


def test_history_spans_several_months(seeded):
    path, _ = seeded
    row = _rows(path, "SELECT MIN(visit_date) a, MAX(visit_date) b FROM visits")[0]
    assert row["a"][:7] != row["b"][:7]
    months = _rows(path, "SELECT COUNT(DISTINCT substr(visit_date,1,7)) AS c FROM visits")[0]["c"]
    assert months >= 5


def test_today_has_a_populated_schedule(seeded):
    path, _ = seeded
    # _count opens sqlite3 directly, bypassing the app's translation layer, so
    # a bare date('now') here is UTC while the seeder wrote the clinic's local
    # dates. Between midnight and 03:00 in Cairo they differ by a day.
    assert _count(path, "appointments", "appt_date = date('now','localtime')") >= 5
    assert _count(path, "appointments", "appt_date > date('now','localtime')") >= 10


def test_prices_are_egyptian_not_placeholder(seeded):
    path, _ = seeded
    price = _rows(path, "SELECT standard_price FROM service_catalog WHERE code='CONS-GEN'")[0]
    assert 300 <= price["standard_price"] <= 500
    assert _rows(path, "SELECT currency FROM clinic WHERE id=1")[0]["currency"] == "EGP"


def test_phones_look_egyptian(seeded):
    path, _ = seeded
    for row in _rows(path, "SELECT phone FROM owners WHERE phone IS NOT NULL"):
        p = row["phone"]
        assert len(p) == 11 and p[:3] in ("010", "011", "012", "015"), p


def test_the_competitor_gap_modules_have_data(seeded):
    path, counts = seeded
    for table in ("grooming_bookings", "boarding_bookings", "ps_orders",
                  "ps_products", "attendance_records", "salaries",
                  "inpatient_stays", "expenses", "daily_closings"):
        assert _count(path, table) > 0, table
