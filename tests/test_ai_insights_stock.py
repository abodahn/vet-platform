# -*- coding: utf-8 -*-
"""AI Insights told the owner stock was fine while four items sat at zero.

The home screen's insight card computed on-hand as SUM(stock_movements.quantity).
That ledger is append-only and stores OUTGOING rows with a POSITIVE quantity —
the direction lives in movement_type — so receipts and dispensings both counted
as additions.

Receive 40, dispense 40, and "on hand" reads 80 against a reorder level of 8.
The error grows with turnover, so the faster a medication moves the more
certainly it can never be flagged: exactly backwards. Every other place in the
platform uses SUM(batches.quantity) — list_items, get_item, the inventory
dashboard — which is why the inventory page listed four short items on the live
demo while the dashboard showed a green "no reordering needed" card.
"""
import models.database as db


def _item_that_turned_over(app, name):
    """Receive 40, dispense 40: on hand 0, ledger sum 80."""
    with app.app_context():
        conn = db.get_db()
        iid = conn.execute(
            "INSERT INTO items(name, reorder_level, is_active) VALUES(?,?,1)",
            (name, 8)).lastrowid
        conn.execute(
            "INSERT INTO batches(item_id, quantity, batch_number) VALUES(?,?,?)",
            (iid, 0, "B1"))
        for movement in ("in", "out"):
            conn.execute(
                "INSERT INTO stock_movements(item_id, movement_type, quantity,"
                " reference_type) VALUES(?,?,?,?)", (iid, movement, 40, "test"))
        conn.commit()
        conn.close()
    return iid


def _low_stock_count(app):
    """The number the insight snapshot reports."""
    from datetime import date
    with app.app_context():
        conn = db.get_db()
        n = conn.execute("""
            SELECT COUNT(*) FROM items i
            WHERE i.reorder_level > 0 AND i.is_active = 1
            AND COALESCE((SELECT SUM(b.quantity) FROM batches b WHERE b.item_id = i.id), 0)
                <= i.reorder_level
        """).fetchone()[0]
        conn.close()
    return n


def test_an_item_that_sold_out_counts_as_short(app):
    before = _low_stock_count(app)
    _item_that_turned_over(app, "AI Stock Turnover")
    assert _low_stock_count(app) == before + 1, \
        "an item at zero on hand is not counted as needing reorder"


def test_turnover_does_not_hide_an_empty_shelf(app):
    """The old sum grew with every movement, so busy items were safest."""
    iid = _item_that_turned_over(app, "AI Stock Busy")
    with app.app_context():
        conn = db.get_db()
        # Ten more cycles: ledger sum climbs to 880, shelf still empty.
        for _ in range(10):
            for movement in ("in", "out"):
                conn.execute(
                    "INSERT INTO stock_movements(item_id, movement_type, quantity,"
                    " reference_type) VALUES(?,?,?,?)", (iid, movement, 40, "test"))
        conn.commit()
        ledger = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM stock_movements WHERE item_id=?",
            (iid,)).fetchone()[0]
        on_hand = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM batches WHERE item_id=?",
            (iid,)).fetchone()[0]
        conn.close()

    assert float(ledger) > 800, "fixture did not build up a ledger"
    assert float(on_hand) == 0.0
    assert _low_stock_count(app) >= 1, \
        "a fast-moving item at zero stock is still invisible to the insight"


def test_the_insight_query_reads_the_shelf_not_the_ledger():
    """Read the file, not the module: importing and introspecting the blueprint
    drags in request-context-bound objects, and this only needs the SQL."""
    import io as _io
    src = _io.open("blueprints/ai_assistant/routes.py", encoding="utf-8").read()
    i = src.index("low_stock    = _q(")
    block = src[i:i + 500]
    assert "FROM batches" in block, "the low-stock count is not reading batches"
    assert "stock_movements" not in block,         "the low-stock count still sums the movement ledger"
