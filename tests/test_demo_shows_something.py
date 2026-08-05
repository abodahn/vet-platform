# -*- coding: utf-8 -*-
"""The demo has to have something on the screens it is shown for.

Found while writing the sales walkthrough, not by any test: every vaccination
in the demo dataset was next due 365 days after it was given, and the visit
history only went back 182 days. So nothing was ever due. The reminder screen,
the overdue count and the WhatsApp reminder queue all rendered empty --
in a demo whose whole pitch includes "the system tells you which animals are
due and messages the owner".

An empty screen during a demo is not a cosmetic problem. It is the feature
failing to exist in front of the person deciding whether to buy.
"""
import os
import sys
from datetime import date, timedelta

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts", "seed"))

import models.database as db  # noqa: E402


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    """Seed the demo dataset once and read it back."""
    import demo_showcase
    path = tmp_path_factory.mktemp("demo") / "demo.db"
    demo_showcase.run(str(path), quiet=True)
    db.use_sqlite(str(path))
    conn = db.get_db()
    yield conn
    conn.close()


def _count(conn, sql, *params):
    return conn.execute(sql, params).fetchone()[0]


TODAY = date.today().isoformat()
IN_30 = (date.today() + timedelta(days=30)).isoformat()
AGO_60 = (date.today() - timedelta(days=60)).isoformat()


def test_something_is_due_for_vaccination_right_now(demo):
    """The screen a vet is shown to explain why the software pays for itself."""
    due = _count(demo,
                 "SELECT COUNT(*) FROM vaccinations "
                 "WHERE next_due_at >= ? AND next_due_at <= ?", TODAY, IN_30)
    assert due >= 5, (
        f"only {due} vaccinations due in the next 30 days — the reminder "
        "screen demos as an empty list")


def test_something_is_already_overdue(demo):
    """Overdue is the number that makes an owner uncomfortable, which is the
    number that sells the reminder feature."""
    overdue = _count(demo,
                     "SELECT COUNT(*) FROM vaccinations "
                     "WHERE next_due_at < ? AND next_due_at >= ?", TODAY, AGO_60)
    assert overdue >= 3, f"only {overdue} recently overdue vaccinations"


def test_the_money_screens_are_not_empty(demo):
    assert _count(demo, "SELECT COUNT(*) FROM invoices WHERE due_amount > 0") >= 20
    assert _count(demo, "SELECT COUNT(*) FROM payments") >= 50


def test_todays_diary_is_not_empty(demo):
    """The first screen anyone opens."""
    n = _count(demo, "SELECT COUNT(*) FROM appointments WHERE appt_date = ?", TODAY)
    assert n >= 3, f"today's appointment board has {n} rows"


def test_there_is_stock_to_reorder(demo):
    """The low-stock alert is the other feature that demos in one glance.

    Stock lives in `batches`, not on the item -- an item is low when the sum of
    its batches has fallen to its reorder level."""
    assert _count(demo, """
        SELECT COUNT(*) FROM items i
        WHERE COALESCE((SELECT SUM(b.quantity) FROM batches b
                        WHERE b.item_id = i.id), 0) <= i.reorder_level
    """) >= 1


def test_every_owner_has_an_arabic_name(demo):
    """The differentiator has to be visible on the very first list he sees."""
    total = _count(demo, "SELECT COUNT(*) FROM owners")
    arabic = _count(demo,
                    "SELECT COUNT(*) FROM owners WHERE COALESCE(full_name_ar,'') <> ''")
    assert arabic == total, f"{total - arabic} owners have no Arabic name"
