# -*- coding: utf-8 -*-
"""A batch must never go negative, on any path that decrements one.

The POS oversell was fixed in August by moving the check into the UPDATE:

    UPDATE ps_products SET stock_qty = stock_qty - ? WHERE id = ? AND stock_qty >= ?

Two other paths kept the older check-then-act shape - SELECT the batch, decide
there is enough, then decrement unconditionally. Between those two statements
anything can happen, so two pharmacists dispensing the same batch both passed
the check and both deducted. For a pharmacy that is not an accounting error: the
controlled-drug register is the document an inspector reads, and it stopped
matching the shelf.

These tests drive the SQL directly rather than the routes. The race needs two
interleaved transactions, which a single test client cannot produce, and the
guard being present in the statement is the thing that actually prevents it.
"""
import itertools

import pytest

import models.database as db

_n = itertools.count()


@pytest.fixture
def a_batch(app):
    """An item with a batch holding exactly 10 units."""
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                i = next(_n)
                cur = conn.execute(
                    "INSERT INTO items (name, unit, is_medication) VALUES (?,?,?)",
                    ("Negative Probe %d" % i, "box", 1))
                item_id = cur.lastrowid
                cur = conn.execute(
                    "INSERT INTO batches (item_id, batch_number, quantity, unit_cost) "
                    "VALUES (?,?,?,?)",
                    (item_id, "NEG%d" % i, 10, 1.0))
                batch_id = cur.lastrowid
        finally:
            conn.close()

    yield {"item_id": item_id, "batch_id": batch_id}

    # The `app` fixture is session-scoped: one SQLite file for every test file
    # in the run, so anything left here is still present for the next one.
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                conn.execute("DELETE FROM batches WHERE id=?", (batch_id,))
                conn.execute("DELETE FROM items WHERE id=?", (item_id,))
        finally:
            conn.close()


def _qty(app, batch_id):
    with app.app_context():
        conn = db.get_db()
        try:
            return conn.execute("SELECT quantity FROM batches WHERE id=?",
                                (batch_id,)).fetchone()[0]
        finally:
            conn.close()


def _guarded_deduct(app, batch_id, qty):
    """Exactly the statement the dispensing and transfer paths now run."""
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                cur = conn.execute(
                    "UPDATE batches SET quantity=quantity-? WHERE id=? AND quantity >= ?",
                    (qty, batch_id, qty))
                return cur.rowcount
        finally:
            conn.close()


def test_a_deduct_within_stock_succeeds(app, a_batch):
    assert _guarded_deduct(app, a_batch["batch_id"], 4) == 1
    assert _qty(app, a_batch["batch_id"]) == 6


def test_a_deduct_beyond_stock_changes_nothing(app, a_batch):
    """rowcount 0, and crucially the quantity is untouched - not floored."""
    assert _guarded_deduct(app, a_batch["batch_id"], 11) == 0
    assert _qty(app, a_batch["batch_id"]) == 10


def test_the_second_of_two_claims_on_the_last_units_loses(app, a_batch):
    """The actual oversell. Both callers 'checked' 10 >= 8 and both deducted."""
    b = a_batch["batch_id"]
    assert _guarded_deduct(app, b, 8) == 1      # first pharmacist
    assert _guarded_deduct(app, b, 8) == 0      # second one gets nothing
    assert _qty(app, b) == 2, "the batch went negative - the guard is gone"


def test_exact_stock_is_allowed(app, a_batch):
    """>= not >: dispensing the whole remaining box is normal."""
    assert _guarded_deduct(app, a_batch["batch_id"], 10) == 1
    assert _qty(app, a_batch["batch_id"]) == 0


def test_every_batch_decrement_in_the_app_carries_the_guard():
    """The one that stops this coming back.

    Any UPDATE that subtracts from batches.quantity must carry a
    "AND quantity >= ?" condition. Written as a source check because the race
    itself cannot be reproduced in-process.
    """
    import pathlib
    import re
    offenders = []
    root = pathlib.Path("blueprints")
    pat = re.compile(
        r"UPDATE\s+batches\s+SET\s+quantity\s*=\s*quantity\s*-\s*\?(.*?)\"",
        re.IGNORECASE | re.DOTALL)
    for path in root.rglob("*.py"):
        body = path.read_text(encoding="utf-8", errors="ignore")
        for m in pat.finditer(body):
            if "quantity >=" not in m.group(1):
                line = body[:m.start()].count("\n") + 1
                offenders.append("%s:%d" % (path.as_posix(), line))
    assert not offenders, (
        "these decrement a batch without checking the stock is there, so it "
        "can go negative:\n  " + "\n  ".join(offenders))
