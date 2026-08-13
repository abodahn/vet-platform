# -*- coding: utf-8 -*-
"""Receiving stock from the dashboard button.

The form used to emit name="item_id" twice — a hidden field that was empty
whenever no item was preselected, plus the picker. request.form.get(type=int)
returns the FIRST value, int("") fails, and the route rejected the receipt with
"Item and positive quantity are required". The two item-scoped entry points put
item_id in the query string and skipped the picker, so the same button worked
from the item page and failed from the dashboard — which reads as flaky rather
than broken, and is why it survived.
"""
import re

from conftest import get_csrf


def _mk_item(app, name="Amoxicillin 500mg", sku="AMX-500"):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO items(name, sku, unit, is_active) VALUES(?,?,?,1)",
            (name, sku, "box"))
        conn.commit()
        item_id = cur.lastrowid
        conn.close()
    return item_id


def _stock(app, item_id):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        n = conn.execute(
            "SELECT COALESCE(SUM(quantity),0) FROM batches WHERE item_id=?",
            (item_id,)).fetchone()[0]
        conn.close()
    return float(n or 0)


def test_the_form_sends_exactly_one_item_id(auth_client, app):
    """The regression itself, stated as HTML rather than behaviour.

    Asserted separately from the round-trip below because a second field can
    come back without breaking the happy path — it only breaks the arrival that
    has no preselected item, which is the one nobody tests by hand.
    """
    _mk_item(app, "Meloxicam", "MLX-1")
    body = auth_client.get("/inventory/batches/new").data.decode("utf-8")
    assert body.count('name="item_id"') == 1, \
        "more than one item_id field: the first one wins and the receipt is rejected"


def test_stock_arrives_when_no_item_was_preselected(auth_client, app):
    """The dashboard's Receive Stock button, end to end."""
    item_id = _mk_item(app, "Ivermectin", "IVR-9")
    before = _stock(app, item_id)

    token = get_csrf(auth_client)
    r = auth_client.post("/inventory/batches/new", data={
        "item_id": str(item_id),
        "quantity": "12",
        "unit_cost": "40",
        "batch_number": "B-001",
        "_csrf_token": token,
    }, follow_redirects=True)

    assert r.status_code == 200
    body = r.data.decode("utf-8", errors="replace")
    assert "Item and positive quantity are required" not in body, \
        "the receipt was rejected — the item never reached the route"
    assert _stock(app, item_id) == before + 12


def test_the_picker_lists_items_by_name_not_by_id(auth_client, app):
    """Nobody at a counter knows an item's numeric id."""
    _mk_item(app, "Ketamine 10ml", "KET-10")
    body = auth_client.get("/inventory/batches/new").data.decode("utf-8")
    assert "Ketamine 10ml" in body, "the item list is not offered"
    assert re.search(r'<select[^>]*name="item_id"', body), \
        "item is still a free-text/number box rather than a picker"


def test_a_mistyped_quantity_is_reported_not_silently_zero(auth_client, app):
    """"1O0" with a letter O must not book the delivery as nothing.

    Coercing to 0 is worse than refusing: the shelf count goes short with no
    trace of why, and the person who typed it saw a success message.
    """
    item_id = _mk_item(app, "Cefazolin", "CFZ-2")
    before = _stock(app, item_id)

    token = get_csrf(auth_client)
    r = auth_client.post("/inventory/batches/new", data={
        "item_id": str(item_id),
        "quantity": "1O0",
        "unit_cost": "40",
        "_csrf_token": token,
    }, follow_redirects=True)

    assert r.status_code != 500, "a mistyped quantity crashed the page"
    assert _stock(app, item_id) == before, "a mistyped quantity was booked as stock"
    assert "not a valid quantity" in r.data.decode("utf-8", errors="replace"), \
        "the user was not told which box to fix"


def test_a_thousands_separator_is_accepted(auth_client, app):
    """An Egyptian keyboard puts the separator there; 1,200 units is 1200."""
    item_id = _mk_item(app, "Saline 500ml", "SAL-500")
    before = _stock(app, item_id)

    token = get_csrf(auth_client)
    auth_client.post("/inventory/batches/new", data={
        "item_id": str(item_id),
        "quantity": "1,200",
        "unit_cost": "3",
        "_csrf_token": token,
    }, follow_redirects=True)

    assert _stock(app, item_id) == before + 1200
