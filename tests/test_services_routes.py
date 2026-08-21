# -*- coding: utf-8 -*-
"""Boarding, grooming and telemedicine — the bookings reception takes all day.

Twenty-one routes, fourteen of them writes. Every write is read back out of the
database: a booking route that renders "Booking created." and inserts nothing
looks identical to one that works, right up until a client arrives for a stay
nobody recorded.

The suite shares one database, so every fixture builds its own owner, pet and
room, and every assertion is scoped to rows it created itself.
SQLite, no network — telemedicine only ever writes a Jitsi URL, it never dials.
"""
from datetime import date, timedelta

import pytest

import models.database as db


# ─── helpers ──────────────────────────────────────────────────────────────────

def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _row(sql, params=()):
    conn = db.get_db()
    try:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _rows(sql, params=()):
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _insert(sql, params):
    conn = db.get_db()
    try:
        with conn:
            return conn.execute(sql, params).lastrowid
    finally:
        conn.close()


def _mk_owner(full_name, phone, **extra):
    cols = ["full_name", "phone"] + list(extra)
    vals = [full_name, phone] + list(extra.values())
    return _insert(
        f"INSERT INTO owners ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
        vals)


def _mk_pet(owner_id, pet_name, species="Dog"):
    return _insert("INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                   (owner_id, pet_name, species))


def _search_ids(client, q):
    """Owner ids the shared type-to-search endpoint returns for `q`."""
    payload = client.get("/crm/owners/search-json", query_string={"q": q}).get_json()
    return {o["id"] for o in payload["owners"]}


TODAY = date.today().isoformat()
SOON = (date.today() + timedelta(days=5)).isoformat()

AR_OWNER = "ياسمين عبد الودود"
AR_PET = "دودو"


@pytest.fixture(scope="module")
def client_pair(app):
    """One Arabic-named owner and their Arabic-named pet."""
    with app.app_context():
        oid = _mk_owner(AR_OWNER, "01000000901")
        pid = _mk_pet(oid, AR_PET, "Dog")
    return {"owner_id": oid, "pet_id": pid}


# ═════════════════════════════════════════════════════════════════════════════
# BOARDING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def room(app):
    """A priced, active boarding room."""
    with app.app_context():
        rid = _insert(
            "INSERT INTO boarding_rooms (name, room_type, capacity,"
            " price_per_night, is_active) VALUES (?,?,?,?,1)",
            ("TEST-KENNEL", "Standard", 1, 180.0))
    return rid


def _mk_booking(owner_id, pet_id, room_id=None, check_in=None, status="Reserved"):
    return _insert(
        "INSERT INTO boarding_bookings (pet_id, owner_id, room_id, check_in,"
        " check_out, status) VALUES (?,?,?,?,?,?)",
        (pet_id, owner_id, room_id, check_in or TODAY, SOON, status))


def test_boarding_new_form_lists_rooms_and_searches_owners(auth_client, room,
                                                           client_pair):
    """The owner box must reach every client, not a rendered slice of them.

    This used to assert the Arabic owner appeared in the page. That passed only
    while the shared test database held fewer owners than the dropdown's
    LIMIT 300 — the same accident that hides the bug on the demo. The form now
    renders no owner list at all, so what matters is that it points at the
    search endpoint, and that the endpoint finds the client.
    """
    resp = auth_client.get("/boarding/bookings/new")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "TEST-KENNEL" in body
    assert "/crm/owners/search-json" in body, "the owner box has no live search"
    assert _search_ids(auth_client, AR_OWNER) >= {client_pair["owner_id"]}, \
        "the owner search cannot find the Arabic-named client"


def test_boarding_booking_is_actually_created(app, auth_client, room, client_pair):
    """POST, then read the row back — linked to the right pet and owner."""
    with app.app_context():
        before = {b["id"] for b in _rows("SELECT id FROM boarding_bookings")}
        _post(auth_client, "/boarding/bookings/new", {
            "owner_id": str(client_pair["owner_id"]),
            "pet_id": str(client_pair["pet_id"]),
            "room_id": str(room),
            "checkin_date": TODAY,
            "expected_checkout": SOON,
            "diet_notes": "نصف كوب مرتين يومياً",
            "medication_notes": "Apoquel 16mg AM",
            "notes": "nervous around other dogs",
            "status": "Reserved",
        })
        made = [b for b in _rows("SELECT * FROM boarding_bookings ORDER BY id")
                if b["id"] not in before]

    assert len(made) == 1, "the boarding form rendered but wrote no booking"
    b = made[0]
    assert b["owner_id"] == client_pair["owner_id"]
    assert b["pet_id"] == client_pair["pet_id"], "booking is not linked to the pet"
    assert b["room_id"] == room
    assert b["check_in"] == TODAY
    assert b["check_out"] == SOON
    assert b["status"] == "Reserved"
    assert b["feeding_instructions"] == "نصف كوب مرتين يومياً"
    assert b["medication_instructions"] == "Apoquel 16mg AM"
    assert b["vet_notes"] == "nervous around other dogs"


def test_boarding_booking_without_required_fields_writes_nothing(app, auth_client,
                                                                 client_pair):
    with app.app_context():
        before = _row("SELECT COUNT(*) n FROM boarding_bookings")["n"]
        _post(auth_client, "/boarding/bookings/new",
              {"owner_id": str(client_pair["owner_id"]), "pet_id": "", "checkin_date": ""})
        assert _row("SELECT COUNT(*) n FROM boarding_bookings")["n"] == before


def test_boarding_edit_form_shows_the_booking(app, auth_client, room, client_pair):
    with app.app_context():
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room)
    resp = auth_client.get(f"/boarding/bookings/{bid}/edit")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert AR_PET in body
    assert AR_OWNER in body


def test_boarding_edit_form_404s_gracefully_on_a_missing_booking(auth_client):
    resp = auth_client.get("/boarding/bookings/99999999/edit", follow_redirects=True)
    assert resp.status_code == 200   # redirected to the list, not a crash


def test_boarding_edit_persists_every_field(app, auth_client, room, client_pair):
    with app.app_context():
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room)
        later = (date.today() + timedelta(days=9)).isoformat()
        _post(auth_client, f"/boarding/bookings/{bid}/edit", {
            "room_id": str(room),
            "checkin_date": SOON,
            "expected_checkout": later,
            "status": "Checked-in",
            "diet_notes": "raw diet",
            "medication_notes": "none",
            "notes": "extended stay",
        })
        b = _row("SELECT * FROM boarding_bookings WHERE id=?", (bid,))

    assert b["check_in"] == SOON
    assert b["check_out"] == later
    assert b["status"] == "Checked-in"
    assert b["feeding_instructions"] == "raw diet"
    assert b["vet_notes"] == "extended stay"
    assert b["pet_id"] == client_pair["pet_id"], "editing detached the booking from the pet"


def test_boarding_cancel_sets_the_status(app, auth_client, room, client_pair):
    with app.app_context():
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room)
        _post(auth_client, f"/boarding/bookings/{bid}/cancel", {})
        assert _row("SELECT status FROM boarding_bookings WHERE id=?",
                    (bid,))["status"] == "Cancelled"


def test_boarding_checkin_sets_status_and_keeps_the_booked_date(app, auth_client,
                                                                room, client_pair):
    """COALESCE(check_in, ?) must not overwrite the date the client booked."""
    with app.app_context():
        booked = (date.today() - timedelta(days=2)).isoformat()
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room,
                          check_in=booked)
        _post(auth_client, f"/boarding/bookings/{bid}/checkin", {})
        b = _row("SELECT status, check_in FROM boarding_bookings WHERE id=?", (bid,))
    assert b["status"] == "Checked-in"
    assert b["check_in"] == booked


def test_boarding_checkout_bills_the_stay(app, auth_client, room, client_pair):
    """Check out, then verify the invoice exists, is linked, and adds up."""
    with app.app_context():
        checkin = (date.today() - timedelta(days=3)).isoformat()
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room,
                          check_in=checkin, status="Checked-in")
        _post(auth_client, f"/boarding/bookings/{bid}/checkout", {})
        b = _row("SELECT * FROM boarding_bookings WHERE id=?", (bid,))

        assert b["status"] == "Checked-out"
        assert b["actual_checkout"] == TODAY
        assert b["invoice_id"], "checkout did not link an invoice to the booking"

        inv = _row("SELECT * FROM invoices WHERE id=?", (b["invoice_id"],))
        lines = _rows("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv["id"],))

    assert inv["owner_id"] == client_pair["owner_id"]
    assert inv["pet_id"] == client_pair["pet_id"]
    assert len(lines) == 1
    assert lines[0]["quantity"] == 3, "three nights stayed, three nights billed"
    assert float(lines[0]["unit_price"]) == 180.0
    assert float(inv["total"]) == 3 * 180.0
    assert float(inv["due_amount"]) == 3 * 180.0


def test_boarding_checkout_does_not_double_invoice(app, auth_client, room, client_pair):
    with app.app_context():
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room,
                          check_in=TODAY, status="Checked-in")
        _post(auth_client, f"/boarding/bookings/{bid}/checkout", {})
        first = _row("SELECT invoice_id FROM boarding_bookings WHERE id=?", (bid,))["invoice_id"]
        n_before = _row("SELECT COUNT(*) n FROM invoices")["n"]

        _post(auth_client, f"/boarding/bookings/{bid}/checkout", {})
        again = _row("SELECT invoice_id FROM boarding_bookings WHERE id=?", (bid,))["invoice_id"]

        assert again == first
        assert _row("SELECT COUNT(*) n FROM invoices")["n"] == n_before, \
            "checking out twice billed the client twice"


def test_boarding_checkout_without_a_room_rate_still_checks_out(app, auth_client,
                                                                client_pair):
    with app.app_context():
        free = _insert(
            "INSERT INTO boarding_rooms (name, price_per_night, is_active)"
            " VALUES (?,?,1)", ("TEST-FREE", 0.0))
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], free,
                          check_in=TODAY, status="Checked-in")
        _post(auth_client, f"/boarding/bookings/{bid}/checkout", {})
        b = _row("SELECT status, invoice_id FROM boarding_bookings WHERE id=?", (bid,))
    assert b["status"] == "Checked-out"
    assert not b["invoice_id"]


def test_boarding_invoice_link_follows_through_to_the_invoice(app, auth_client,
                                                              room, client_pair):
    with app.app_context():
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room,
                          check_in=TODAY, status="Checked-in")
        _post(auth_client, f"/boarding/bookings/{bid}/checkout", {})
        inv_id = _row("SELECT invoice_id FROM boarding_bookings WHERE id=?",
                      (bid,))["invoice_id"]

    resp = auth_client.get(f"/boarding/bookings/{bid}/invoice")
    assert resp.status_code in (301, 302)
    assert f"/finance/invoices/{inv_id}" in resp.headers["Location"]


def test_boarding_invoice_link_without_an_invoice_goes_back_to_the_list(
        app, auth_client, room, client_pair):
    with app.app_context():
        bid = _mk_booking(client_pair["owner_id"], client_pair["pet_id"], room)
    resp = auth_client.get(f"/boarding/bookings/{bid}/invoice")
    assert resp.status_code in (301, 302)
    assert "/boarding/bookings" in resp.headers["Location"]


def test_boarding_room_new_inserts_the_room(app, auth_client):
    with app.app_context():
        _post(auth_client, "/boarding/rooms/new", {
            "room_number": "TEST-SUITE-A",
            "room_type": "Premium",
            "capacity": "2",
            "daily_rate": "425.50",
            "is_active": "1",
        })
        r = _row("SELECT * FROM boarding_rooms WHERE name=?", ("TEST-SUITE-A",))

    assert r is not None, "the room form rendered but wrote nothing"
    assert r["room_type"] == "Premium"
    assert r["capacity"] == 2
    assert float(r["price_per_night"]) == 425.50
    assert r["is_active"] == 1


def test_boarding_room_new_updates_when_given_an_id(app, auth_client, room):
    with app.app_context():
        _post(auth_client, "/boarding/rooms/new", {
            "room_id": str(room),
            "room_number": "TEST-KENNEL-RENAMED",
            "room_type": "ICU",
            "capacity": "1",
            "daily_rate": "900",
            "is_active": "1",
        })
        r = _row("SELECT * FROM boarding_rooms WHERE id=?", (room,))
    assert r["name"] == "TEST-KENNEL-RENAMED"
    assert r["room_type"] == "ICU"
    assert float(r["price_per_night"]) == 900.0


def test_boarding_room_new_without_a_name_writes_nothing(app, auth_client):
    with app.app_context():
        before = _row("SELECT COUNT(*) n FROM boarding_rooms")["n"]
        _post(auth_client, "/boarding/rooms/new", {"room_number": "  ", "daily_rate": "10"})
        assert _row("SELECT COUNT(*) n FROM boarding_rooms")["n"] == before


# ═════════════════════════════════════════════════════════════════════════════
# GROOMING
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def groom_service(app):
    with app.app_context():
        sid = _insert(
            "INSERT INTO grooming_services (name, species, duration_min, price,"
            " is_active) VALUES (?,?,?,?,1)", ("Test Full Groom", "Dog", 90, 250.0))
    return sid


def _mk_groom_booking(owner_id, pet_id, service_id, when=None, status="Scheduled"):
    return _insert(
        "INSERT INTO grooming_bookings (pet_id, owner_id, service_id, groomer_name,"
        " booking_date, status) VALUES (?,?,?,?,?,?)",
        (pet_id, owner_id, service_id, "Groomer Hana", when or TODAY, status))


def test_grooming_new_form_lists_services_and_searches_owners(auth_client,
                                                              groom_service,
                                                              client_pair):
    resp = auth_client.get("/grooming/bookings/new")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Test Full Groom" in body
    assert "/crm/owners/search-json" in body, "the owner box has no live search"
    assert _search_ids(auth_client, AR_OWNER) >= {client_pair["owner_id"]}


def test_grooming_booking_is_actually_created(app, auth_client, groom_service,
                                              client_pair):
    with app.app_context():
        before = {b["id"] for b in _rows("SELECT id FROM grooming_bookings")}
        _post(auth_client, "/grooming/bookings/new", {
            "owner_id": str(client_pair["owner_id"]),
            "pet_id": str(client_pair["pet_id"]),
            "service_id": str(groom_service),
            "groomer_name": "هناء",
            "booking_date": SOON,
            "status": "Scheduled",
            "notes": "قص الأظافر أيضاً",
        })
        made = [b for b in _rows("SELECT * FROM grooming_bookings ORDER BY id")
                if b["id"] not in before]

    assert len(made) == 1, "the grooming form rendered but wrote no booking"
    b = made[0]
    assert b["owner_id"] == client_pair["owner_id"]
    assert b["pet_id"] == client_pair["pet_id"], "booking is not linked to the pet"
    assert b["service_id"] == groom_service
    assert b["booking_date"] == SOON
    assert b["groomer_name"] == "هناء"
    assert b["notes"] == "قص الأظافر أيضاً"
    assert b["status"] == "Scheduled"


def test_grooming_booking_without_required_fields_writes_nothing(app, auth_client,
                                                                 client_pair):
    with app.app_context():
        before = _row("SELECT COUNT(*) n FROM grooming_bookings")["n"]
        _post(auth_client, "/grooming/bookings/new", {
            "owner_id": str(client_pair["owner_id"]),
            "pet_id": str(client_pair["pet_id"]),
            "booking_date": "",
        })
        assert _row("SELECT COUNT(*) n FROM grooming_bookings")["n"] == before


def test_grooming_edit_persists_every_field(app, auth_client, groom_service,
                                            client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        _post(auth_client, f"/grooming/bookings/{bid}/edit", {
            "service_id": str(groom_service),
            "groomer_name": "Groomer Nour",
            "booking_date": SOON,
            "status": "In Progress",
            "notes": "matted coat",
        })
        b = _row("SELECT * FROM grooming_bookings WHERE id=?", (bid,))

    assert b["groomer_name"] == "Groomer Nour"
    assert b["booking_date"] == SOON
    assert b["status"] == "In Progress"
    assert b["notes"] == "matted coat"
    assert b["pet_id"] == client_pair["pet_id"]


def test_grooming_edit_without_a_date_writes_nothing(app, auth_client, groom_service,
                                                     client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        _post(auth_client, f"/grooming/bookings/{bid}/edit",
              {"booking_date": "", "status": "Cancelled", "groomer_name": "wiped"})
        b = _row("SELECT * FROM grooming_bookings WHERE id=?", (bid,))
    assert b["status"] == "Scheduled"
    assert b["groomer_name"] == "Groomer Hana"


def test_grooming_price_override_reaches_the_invoice(app, auth_client, groom_service,
                                                     client_pair):
    """The edit form has always offered a price override (booking_edit.html:57).

    It was parsed and thrown away — "Booking updated." with the agreed discount
    silently discarded, and the client billed the full catalogue price.
    """
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        _post(auth_client, f"/grooming/bookings/{bid}/edit", {
            "service_id": str(groom_service),
            "groomer_name": "Groomer Hana",
            "booking_date": TODAY,
            "status": "Scheduled",
            "price_override": "160",
        })
        _post(auth_client, f"/grooming/bookings/{bid}/status", {"status": "Completed"})

        inv_id = _row("SELECT invoice_id FROM grooming_bookings WHERE id=?",
                      (bid,))["invoice_id"]
        assert inv_id, "completing the booking created no invoice"
        inv = _row("SELECT * FROM invoices WHERE id=?", (inv_id,))
        line = _rows("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,))[0]

    assert float(line["unit_price"]) == 160.0, \
        "the agreed price was discarded and the catalogue price billed instead"
    assert float(inv["total"]) == 160.0


def test_grooming_status_update_writes_the_status(app, auth_client, groom_service,
                                                  client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        for status in ("In Progress", "Cancelled"):
            _post(auth_client, f"/grooming/bookings/{bid}/status", {"status": status})
            assert _row("SELECT status FROM grooming_bookings WHERE id=?",
                        (bid,))["status"] == status


def test_grooming_completion_bills_the_catalogue_price(app, auth_client,
                                                       groom_service, client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        _post(auth_client, f"/grooming/bookings/{bid}/status", {"status": "Completed"})
        b = _row("SELECT * FROM grooming_bookings WHERE id=?", (bid,))

        assert b["status"] == "Completed"
        assert b["invoice_id"], "a completed grooming session was never invoiced"
        inv = _row("SELECT * FROM invoices WHERE id=?", (b["invoice_id"],))
        line = _rows("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv["id"],))[0]

    assert inv["owner_id"] == client_pair["owner_id"]
    assert inv["pet_id"] == client_pair["pet_id"]
    assert line["description"] == "Test Full Groom"
    assert float(line["unit_price"]) == 250.0
    assert float(inv["total"]) == 250.0


def test_grooming_completion_does_not_double_invoice(app, auth_client, groom_service,
                                                     client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        _post(auth_client, f"/grooming/bookings/{bid}/status", {"status": "Completed"})
        first = _row("SELECT invoice_id FROM grooming_bookings WHERE id=?",
                     (bid,))["invoice_id"]
        n_before = _row("SELECT COUNT(*) n FROM invoices")["n"]

        _post(auth_client, f"/grooming/bookings/{bid}/status", {"status": "Completed"})
        assert _row("SELECT invoice_id FROM grooming_bookings WHERE id=?",
                    (bid,))["invoice_id"] == first
        assert _row("SELECT COUNT(*) n FROM invoices")["n"] == n_before


def test_grooming_invoice_link_follows_through(app, auth_client, groom_service,
                                               client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
        _post(auth_client, f"/grooming/bookings/{bid}/status", {"status": "Completed"})
        inv_id = _row("SELECT invoice_id FROM grooming_bookings WHERE id=?",
                      (bid,))["invoice_id"]

    resp = auth_client.get(f"/grooming/bookings/{bid}/invoice")
    assert resp.status_code in (301, 302)
    assert f"/finance/invoices/{inv_id}" in resp.headers["Location"]


def test_grooming_invoice_link_without_an_invoice_goes_back_to_the_list(
        app, auth_client, groom_service, client_pair):
    with app.app_context():
        bid = _mk_groom_booking(client_pair["owner_id"], client_pair["pet_id"],
                                groom_service)
    resp = auth_client.get(f"/grooming/bookings/{bid}/invoice")
    assert resp.status_code in (301, 302)
    assert "/grooming/bookings" in resp.headers["Location"]


def test_grooming_services_list_shows_services(auth_client, groom_service):
    resp = auth_client.get("/grooming/services")
    assert resp.status_code == 200
    assert "Test Full Groom" in resp.get_data(as_text=True)


def test_grooming_service_new_inserts_the_service(app, auth_client):
    """services.html posts a `description` and renders it back. The INSERT named
    that column and `grooming_services` never had it, so adding or editing any
    grooming service raised "no column named description" — a 500 on the only
    screen that maintains the price list."""
    with app.app_context():
        _post(auth_client, "/grooming/services/new", {
            "name": "قص شعر كامل",
            "species": "Cat",
            "duration_min": "45",
            "price": "175.5",
            "is_active": "1",
            "description": "استحمام وتجفيف وقص",
        })
        s = _row("SELECT * FROM grooming_services WHERE name=?", ("قص شعر كامل",))

    assert s is not None, "the service form rendered but wrote nothing"
    assert s["name"].encode("utf-8") == "قص شعر كامل".encode("utf-8")
    assert s["species"] == "Cat"
    assert int(s["duration_min"]) == 45
    assert float(s["price"]) == 175.5
    assert s["is_active"] == 1
    assert s["description"] == "استحمام وتجفيف وقص"

    # and the list screen shows what was saved
    body = auth_client.get("/grooming/services").get_data(as_text=True)
    assert "استحمام وتجفيف وقص" in body


def test_grooming_service_new_updates_when_given_an_id(app, auth_client, groom_service):
    with app.app_context():
        _post(auth_client, "/grooming/services/new", {
            "service_id": str(groom_service),
            "name": "Test Full Groom Deluxe",
            "species": "Dog",
            "duration_min": "120",
            "price": "400",
            "is_active": "1",
            "description": "",
        })
        s = _row("SELECT * FROM grooming_services WHERE id=?", (groom_service,))
    assert s["name"] == "Test Full Groom Deluxe"
    assert float(s["price"]) == 400.0


def test_grooming_service_new_without_a_name_writes_nothing(app, auth_client):
    with app.app_context():
        before = _row("SELECT COUNT(*) n FROM grooming_services")["n"]
        _post(auth_client, "/grooming/services/new", {"name": " ", "price": "10"})
        assert _row("SELECT COUNT(*) n FROM grooming_services")["n"] == before


# ═════════════════════════════════════════════════════════════════════════════
# TELEMEDICINE
# ═════════════════════════════════════════════════════════════════════════════

def _mk_session(auth_client, owner_id, pet_id=None, when=None, doctor="Dr. Farid"):
    """Create a session through the real route and return its row."""
    _post(auth_client, "/telemedicine/new", {
        "owner_id": str(owner_id),
        "pet_id": str(pet_id) if pet_id else "",
        "doctor_name": doctor,
        "scheduled_at": when or f"{SOON}T10:00",
        "duration_min": "30",
        "chief_complaint": "سعال مستمر",
    })
    return _row("SELECT * FROM telemedicine_sessions ORDER BY id DESC")


def test_telemedicine_session_is_actually_created(app, auth_client, client_pair):
    with app.app_context():
        ts = _mk_session(auth_client, client_pair["owner_id"], client_pair["pet_id"])

    assert ts is not None, "the telemedicine form rendered but wrote nothing"
    assert ts["owner_id"] == client_pair["owner_id"]
    assert ts["pet_id"] == client_pair["pet_id"]
    assert ts["doctor_name"] == "Dr. Farid"
    assert ts["duration_min"] == 30
    assert ts["status"] == "Scheduled"
    assert ts["chief_complaint"] == "سعال مستمر"
    assert ts["room_url"].startswith("https://meet.jit.si/PAH-")
    assert ts["room_token"] in ts["room_url"]


def test_telemedicine_without_owner_or_time_writes_nothing(app, auth_client,
                                                           client_pair):
    with app.app_context():
        before = _row("SELECT COUNT(*) n FROM telemedicine_sessions")["n"]
        _post(auth_client, "/telemedicine/new",
              {"owner_id": str(client_pair["owner_id"]), "scheduled_at": ""})
        _post(auth_client, "/telemedicine/new",
              {"owner_id": "", "scheduled_at": f"{SOON}T11:00"})
        assert _row("SELECT COUNT(*) n FROM telemedicine_sessions")["n"] == before


def test_telemedicine_room_tokens_are_unguessable_and_never_reused(app, auth_client,
                                                                   client_pair):
    """The room URL is the only thing protecting a consultation: anyone holding
    it can walk into the call. It must not be derivable from the session id, the
    owner id or the previous token."""
    tokens = []
    with app.app_context():
        for i in range(24):
            ts = _mk_session(auth_client, client_pair["owner_id"],
                             client_pair["pet_id"], when=f"{SOON}T{8 + i % 12:02d}:00")
            tokens.append((ts["id"], ts["room_token"]))

    values = [t for _, t in tokens]
    assert len(set(values)) == len(values), "a room token was issued twice"

    for tok in values:
        assert len(tok) >= 12, f"token {tok!r} is too short to resist guessing"
        assert set(tok) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")

    # not a counter and not a timestamp: no two consecutive tokens share a
    # meaningful prefix, and issue order carries no ordering information
    for a, b in zip(values, values[1:]):
        common = 0
        while common < len(a) and common < len(b) and a[common] == b[common]:
            common += 1
        assert common <= 3, f"tokens {a!r} and {b!r} look sequential"
    assert values != sorted(values), "tokens increase with the session id"

    # 24 tokens should range over most of the alphabet, not a handful of chars
    assert len(set("".join(values))) > 20, "token alphabet is far too small"
    # 12 chars over 36 symbols is ~62 bits; a URL nobody can walk into
    assert len(set(values[0])) >= 6, f"token {values[0]!r} has almost no variety"


def test_telemedicine_start_marks_the_session_in_progress(app, auth_client,
                                                          client_pair):
    with app.app_context():
        ts = _mk_session(auth_client, client_pair["owner_id"], client_pair["pet_id"])
        _post(auth_client, f"/telemedicine/{ts['id']}/start", {})
        after = _row("SELECT * FROM telemedicine_sessions WHERE id=?", (ts["id"],))

    assert after["status"] == "In Progress"
    assert after["started_at"], "starting a session recorded no start time"
    assert after["room_token"] == ts["room_token"], "starting rotated the room token"


def test_telemedicine_complete_records_notes_and_bills(app, auth_client, client_pair):
    with app.app_context():
        # sort_order -100 so this row is the one the route's
        # `ORDER BY sort_order, id LIMIT 1` picks, whatever else the shared
        # database already holds. Asserted rather than assumed.
        _insert("INSERT INTO service_catalog (code, name, standard_price, is_active,"
                " sort_order) VALUES (?,?,?,1,?)",
                ("TEST-TELE", "Telemedicine consultation", 300.0, -100))
        winner = _row("SELECT code FROM service_catalog WHERE LOWER(name) LIKE ?"
                      " AND is_active=1 ORDER BY sort_order, id LIMIT 1", ("%tele%",))
        assert winner["code"] == "TEST-TELE", (
            "another catalogue entry outranks this test's — the price below is "
            "not the one under test")

        ts = _mk_session(auth_client, client_pair["owner_id"], client_pair["pet_id"])
        _post(auth_client, f"/telemedicine/{ts['id']}/complete",
              {"notes": "أوصي بمتابعة بعد أسبوع"})
        after = _row("SELECT * FROM telemedicine_sessions WHERE id=?", (ts["id"],))

        assert after["status"] == "Completed"
        assert after["ended_at"], "completing a session recorded no end time"
        assert after["notes"] == "أوصي بمتابعة بعد أسبوع"
        assert after["invoice_id"], "a completed consultation was never invoiced"

        inv = _row("SELECT * FROM invoices WHERE id=?", (after["invoice_id"],))
        line = _rows("SELECT * FROM invoice_lines WHERE invoice_id=?", (inv["id"],))[0]

    assert inv["owner_id"] == client_pair["owner_id"]
    assert inv["pet_id"] == client_pair["pet_id"]
    assert float(line["unit_price"]) == 300.0
    assert float(inv["total"]) == 300.0


def test_telemedicine_complete_on_a_missing_session_is_not_a_500(auth_client):
    resp = _post(auth_client, "/telemedicine/99999999/complete", {"notes": "x"})
    assert resp.status_code == 200


def test_telemedicine_cancel_sets_the_status(app, auth_client, client_pair):
    with app.app_context():
        ts = _mk_session(auth_client, client_pair["owner_id"], client_pair["pet_id"])
        _post(auth_client, f"/telemedicine/{ts['id']}/cancel", {})
        after = _row("SELECT status FROM telemedicine_sessions WHERE id=?", (ts["id"],))
    assert after["status"] == "Cancelled"


def test_telemedicine_share_sends_the_room_url(app, auth_client, monkeypatch):
    """No network: the WhatsApp client is replaced, and what the route asked it
    to send is read back out of whatsapp_log."""
    import blueprints.whatsapp.routes as wa

    class _FakeClient:
        def send_message(self, chat_id, message):
            return {"status": 200, "chat_id": chat_id}, None

    monkeypatch.setattr(wa, "_client", lambda: _FakeClient())

    with app.app_context():
        oid = _mk_owner("Sharing Owner", "01000000902", whatsapp_phone="201000000902")
        pid = _mk_pet(oid, "Shadow")
        ts = _mk_session(auth_client, oid, pid)
        _post(auth_client, f"/telemedicine/{ts['id']}/share", {})
        log = _row("SELECT * FROM whatsapp_log WHERE owner_id=? ORDER BY id DESC", (oid,))

    assert log is not None, "share_link reported success but logged nothing"
    assert log["template_name"] == "telemedicine_invite"
    assert log["status"] == "Sent"
    assert log["phone"] == "201000000902"
    assert ts["room_url"] in log["message"], \
        "the message sent to the owner does not contain the room link"


def test_telemedicine_share_without_a_whatsapp_number_sends_nothing(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Unreachable Owner", "01000000903")
        ts = _mk_session(auth_client, oid)
        before = _row("SELECT COUNT(*) n FROM whatsapp_log")["n"]
        resp = _post(auth_client, f"/telemedicine/{ts['id']}/share", {})
        assert resp.status_code == 200
        assert _row("SELECT COUNT(*) n FROM whatsapp_log")["n"] == before


def test_telemedicine_api_pets_returns_that_owners_pets(app, auth_client, client_pair):
    payload = auth_client.get(
        f"/telemedicine/api/pets/{client_pair['owner_id']}").get_json()
    names = [p["pet_name"] for p in payload["pets"]]
    assert AR_PET in names
    assert names[names.index(AR_PET)].encode("utf-8") == AR_PET.encode("utf-8")


def test_telemedicine_api_pets_empty_for_owner_without_pets(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Telemed Petless", "01000000904")
    assert auth_client.get(f"/telemedicine/api/pets/{oid}").get_json() == {"pets": []}


# ═══ auth ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("url", [
    "/boarding/bookings/new",
    "/boarding/bookings/1/edit",
    "/boarding/bookings/1/invoice",
    "/grooming/bookings/new",
    "/grooming/services",
    "/grooming/bookings/1/invoice",
    "/telemedicine/api/pets/1",
])
def test_service_routes_require_login(client, url):
    resp = client.get(url)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")
