"""
Services spine — grooming, boarding, pet shop and telemedicine must reach the
customer and the money, not just sit next to them.

Every assertion here is about a link that has to RESOLVE: the href is built,
then fetched, so a route that was renamed or a parameter that was never added
fails the test instead of shipping a 404.

The other half is the missing case. A walk-in sale has no customer and a fresh
booking has no invoice yet; those must render as plain text, never as a link
to /crm/owners/None.
"""
import re
import pytest

import models.database as db
from blueprints.petshop.routes import ensure_petshop_tables


HREF = re.compile(r'href="(/[^"#?]*)')


def _columns(conn, table):
    cur = conn.execute(f"SELECT * FROM {table} WHERE 1=0")
    return {d[0] for d in cur.description}


@pytest.fixture(scope="module")
def spine(app):
    """One owner, one pet, one invoice, and a booking/order of each shape."""
    with app.app_context():
        ensure_petshop_tables()
        conn = db.get_db()

        # tests/test_pet_shop.py creates ps_orders from its own DDL, which
        # predates the finance bridge and has no invoice_id. Whichever module
        # gets there first, this test must still see the column.
        if "invoice_id" not in _columns(conn, "ps_orders"):
            conn.execute("ALTER TABLE ps_orders ADD COLUMN invoice_id INTEGER")

        owner_id = conn.execute(
            "INSERT INTO owners(full_name, phone) VALUES(?,?)",
            ("Spine Test Owner", "01000000001"),
        ).lastrowid
        pet_id = conn.execute(
            "INSERT INTO pets(owner_id, pet_name, species) VALUES(?,?,?)",
            (owner_id, "Spine Test Pet", "Dog"),
        ).lastrowid
        conn.commit()

        inv_id = db.create_invoice(
            {"owner_id": owner_id, "pet_id": pet_id, "issue_date": "2026-07-28"},
            [{"description": "Spine Test Service", "quantity": 1,
              "unit_price": 100.0, "total": 100.0, "line_type": "service"}],
        )

        groom_id = conn.execute(
            """INSERT INTO grooming_bookings(pet_id, owner_id, groomer_name,
               booking_date, status) VALUES(?,?,?,?,?)""",
            (pet_id, owner_id, "Spine Groomer", "2026-07-28 10:00", "Scheduled"),
        ).lastrowid
        room_id = conn.execute(
            "INSERT INTO boarding_rooms(name, room_type, price_per_night) VALUES(?,?,?)",
            ("SPINE-1", "Suite", 200.0),
        ).lastrowid
        board_id = conn.execute(
            """INSERT INTO boarding_bookings(pet_id, owner_id, room_id, check_in,
               status, invoice_id) VALUES(?,?,?,?,?,?)""",
            (pet_id, owner_id, room_id, "2026-07-20", "Checked-in", inv_id),
        ).lastrowid

        order_id = conn.execute(
            """INSERT INTO ps_orders(order_number, owner_id, pet_id, status,
               subtotal, total, paid_amount, payment_method, invoice_id)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            ("PS-SPINE-0001", owner_id, pet_id, "paid", 100.0, 100.0, 100.0,
             "Cash", inv_id),
        ).lastrowid
        walkin_id = conn.execute(
            """INSERT INTO ps_orders(order_number, owner_id, pet_id, status,
               subtotal, total, paid_amount, payment_method)
               VALUES(?,?,?,?,?,?,?,?)""",
            ("PS-SPINE-0002", None, None, "paid", 50.0, 50.0, 50.0, "Cash"),
        ).lastrowid
        conn.commit()
        conn.close()

    return dict(owner_id=owner_id, pet_id=pet_id, invoice_id=inv_id,
                groom_id=groom_id, board_id=board_id, room_id=room_id,
                order_id=order_id, walkin_id=walkin_id)


def _page(auth_client, path):
    resp = auth_client.get(path)
    assert resp.status_code == 200, f"{path} -> {resp.status_code}"
    return resp.get_data(as_text=True)


def _resolves(auth_client, path):
    """A link is only wired if fetching it works."""
    assert auth_client.get(path).status_code in (200, 302), f"dead link: {path}"


# ── Grooming ──────────────────────────────────────────────────────────────────

def test_grooming_booking_links_to_pet_and_owner(auth_client, spine):
    for path in ("/grooming/bookings",
                 f"/grooming/bookings/{spine['groom_id']}/edit"):
        html = _page(auth_client, path)
        pet = f"/crm/pets/{spine['pet_id']}"
        owner = f"/crm/owners/{spine['owner_id']}"
        assert pet in html, f"{path} does not link the pet"
        assert owner in html, f"{path} does not link the owner"
        _resolves(auth_client, pet)
        _resolves(auth_client, owner)


def test_grooming_booking_without_invoice_has_no_invoice_link(auth_client, spine):
    """The seeded booking was never completed — no invoice may be invented."""
    html = _page(auth_client, f"/grooming/bookings/{spine['groom_id']}/edit")
    assert "/finance/invoices/" not in html


# ── Boarding ──────────────────────────────────────────────────────────────────

def test_boarding_booking_links_pet_owner_invoice_and_room(auth_client, spine):
    html = _page(auth_client, "/boarding/bookings")
    for target in (f"/crm/pets/{spine['pet_id']}",
                   f"/crm/owners/{spine['owner_id']}",
                   f"/finance/invoices/{spine['invoice_id']}"):
        assert target in html, f"boarding list does not link {target}"
        _resolves(auth_client, target)

    assert f"/boarding/rooms#room-{spine['room_id']}" in html
    # The anchor must exist on the target page, or the link lands nowhere.
    assert f'id="room-{spine["room_id"]}"' in _page(auth_client, "/boarding/rooms")


# ── Pet shop ──────────────────────────────────────────────────────────────────

def test_pos_order_links_customer_and_invoice(auth_client, spine):
    html = _page(auth_client, f"/petshop/orders/{spine['order_id']}")
    for target in (f"/crm/owners/{spine['owner_id']}",
                   f"/crm/pets/{spine['pet_id']}",
                   f"/finance/invoices/{spine['invoice_id']}"):
        assert target in html, f"order detail does not link {target}"
        _resolves(auth_client, target)


def test_pos_orders_list_links_customer(auth_client, spine):
    html = _page(auth_client, "/petshop/orders")
    assert f"/crm/owners/{spine['owner_id']}" in html


def test_walkin_order_renders_cleanly_with_no_dead_link(auth_client, spine):
    """No customer on the sale — plain text, and nothing pointing at /None."""
    html = _page(auth_client, f"/petshop/orders/{spine['walkin_id']}")
    assert "Walk-in" in html
    assert "/crm/owners/None" not in html
    assert "/crm/pets/None" not in html
    assert "/finance/invoices/None" not in html

    for link in HREF.findall(html):
        if link.startswith(("/crm/", "/finance/", "/petshop/orders/")):
            _resolves(auth_client, link)


# ── Telemedicine ──────────────────────────────────────────────────────────────

def test_telemedicine_session_links_pet_owner_and_invoice(auth_client, spine):
    from conftest import get_csrf
    resp = auth_client.post("/telemedicine/new", data={
        "_csrf_token": get_csrf(auth_client),
        "owner_id": spine["owner_id"],
        "pet_id": spine["pet_id"],
        "doctor_name": "Dr Spine",
        "scheduled_at": "2026-07-28T10:00",
        "duration_min": "30",
    }, follow_redirects=True)
    assert resp.status_code == 200

    conn = db.get_db()
    sid = conn.execute(
        "SELECT id FROM telemedicine_sessions ORDER BY id DESC LIMIT 1"
    ).fetchone()[0]
    conn.execute("UPDATE telemedicine_sessions SET invoice_id=? WHERE id=?",
                 (spine["invoice_id"], sid))
    conn.commit()
    conn.close()

    html = _page(auth_client, f"/telemedicine/{sid}")
    for target in (f"/crm/owners/{spine['owner_id']}",
                   f"/crm/pets/{spine['pet_id']}",
                   f"/finance/invoices/{spine['invoice_id']}"):
        assert target in html, f"session detail does not link {target}"
        _resolves(auth_client, target)


# ── Catalog ───────────────────────────────────────────────────────────────────

def test_catalog_traces_a_service_to_the_invoice_that_billed_it(auth_client, spine):
    """The price list has to point at real money, not sit there as a leaflet."""
    conn = db.get_db()
    conn.execute(
        """INSERT INTO service_catalog(name, category, standard_price, is_active)
           VALUES(?,?,?,1)""",
        ("Spine Test Service", "Consultation", 100.0),
    )
    conn.execute(
        """INSERT INTO service_catalog(name, category, standard_price, is_active)
           VALUES(?,?,?,1)""",
        ("Spine Never Billed Service", "Consultation", 10.0),
    )
    conn.commit()
    conn.close()

    html = _page(auth_client, "/catalog/")
    assert f"/finance/invoices/{spine['invoice_id']}" in html
    _resolves(auth_client, f"/finance/invoices/{spine['invoice_id']}")
    # A service nobody has billed says so rather than linking nowhere.
    assert "Never billed" in html


# ── Both languages ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", ["en", "ar"])
def test_service_pages_render_in_both_languages(auth_client, spine, lang):
    # app.py reads user["language"] FIRST and only then session["lang"], so
    # setting session["lang"] alone leaves a logged-in user on English and the
    # Arabic half of this test silently passes as a second English run.
    with auth_client.session_transaction() as sess:
        sess["lang"] = lang
        sess["user"] = {**sess["user"], "language": lang}
    for path in ("/grooming/", "/grooming/bookings",
                 "/boarding/", "/boarding/bookings", "/boarding/rooms",
                 "/petshop/", "/petshop/orders",
                 f"/petshop/orders/{spine['walkin_id']}",
                 "/telemedicine/", "/catalog/"):
        _page(auth_client, path)
