"""
Self-check for the route-level fixes (T1-T4). SQLite only — no PostgreSQL.

    D:\\vet\\.venv\\Scripts\\python.exe -m pytest tests/test_route_fixes.py -q

Covers:
  * mask_owner_name()  — Arabic, single-word, empty and messy inputs
  * /appointments/api/queue — never emits owner_name anonymously, honours
    WAITING_ROOM_TOKEN, keeps working for logged-in staff
  * telemedicine price lookup — bound LIKE param, correct column
  * role names used in @role_required actually exist in _SEED_ROLES
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from blueprints.appointments.routes import mask_owner_name, WAITING_ROOM_COOKIE


# ── T2a: owner-name masking ───────────────────────────────────────────────────

@pytest.mark.parametrize("raw, expected", [
    ("Ahmed El Gohary",       "Ahmed G."),   # multi-word -> first + last initial
    ("Ahmed Elgohary",        "Ahmed E."),
    ("Ahmed",                 "Ahmed"),      # single word -> unchanged
    ("أحمد الجوهري",          "أحمد ا."),    # Arabic, two tokens
    ("أحمد",                  "أحمد"),       # Arabic, single token
    ("  Sara   Ali  ",        "Sara A."),    # collapses runs of whitespace
    ("",                      ""),
    (None,                    ""),           # NULL owner name from the DB
    ("   ",                   ""),           # whitespace only -> no blind index
    ("Jean-Luc Picard",       "Jean-Luc P."),
    ("A B",                   "A B."),       # 1-char tokens must not IndexError
])
def test_mask_owner_name(raw, expected):
    assert mask_owner_name(raw) == expected


def test_mask_owner_name_never_returns_full_name():
    full = "Mohamed Hassan Abdelrahman"
    assert mask_owner_name(full) != full
    assert "Abdelrahman" not in mask_owner_name(full)


# ── fixture: one appointment on today's date ──────────────────────────────────

@pytest.fixture
def seeded(app):
    from datetime import date
    from models.database import get_db
    with app.app_context():
        c = get_db()
        c.execute("INSERT INTO owners (full_name, phone) VALUES (?,?)",
                  ("Ahmed El Gohary", "0100000000"))
        oid = c.execute("SELECT id FROM owners WHERE full_name=?",
                        ("Ahmed El Gohary",)).fetchone()[0]
        c.execute("INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                  (oid, "Rex", "Dog"))
        pid = c.execute("SELECT id FROM pets WHERE pet_name=?", ("Rex",)).fetchone()[0]
        c.execute(
            "INSERT INTO appointments (owner_id,pet_id,appt_date,appt_start,"
            "status,doctor_name,appointment_type) VALUES (?,?,?,?,?,?,?)",
            (oid, pid, date.today().isoformat(), "09:00", "Scheduled",
             "Hatem", "Consultation"))
        c.commit()
        c.close()
    return app


# ── T2b: /api/queue leaks nothing and the query actually runs ─────────────────

def test_api_queue_returns_rows_at_all(seeded, client):
    """Regression: the old query referenced a.appt_time / appt_date::text and
    silently returned [] forever."""
    rows = client.get("/appointments/api/queue").get_json()
    assert rows, "queue is empty — the SQL is broken again"
    assert rows[0]["pet_name"] == "Rex"


def test_api_queue_masks_owner_for_anonymous(seeded, client):
    resp = client.get("/appointments/api/queue")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    rows = resp.get_json()
    assert "owner_name" not in rows[0]
    assert rows[0]["owner_display"] == "Ahmed G."
    assert "El Gohary" not in body


def test_waiting_room_page_masks_owner(seeded, client):
    body = client.get("/appointments/waiting-room").get_data(as_text=True)
    assert "Ahmed G." in body
    assert "El Gohary" not in body


def test_api_queue_refuses_without_token_when_configured(seeded, app, client):
    app.config["WAITING_ROOM_TOKEN"] = "tv-secret"
    try:
        assert client.get("/appointments/api/queue").status_code == 404
        assert client.get("/appointments/waiting-room").status_code == 404
        # correct token in the query string
        assert client.get("/appointments/api/queue?t=tv-secret").status_code == 200
        # wrong token stays out
        assert client.get("/appointments/api/queue?t=nope").status_code == 404
    finally:
        app.config.pop("WAITING_ROOM_TOKEN", None)


def test_waiting_room_sets_cookie_so_polling_keeps_working(seeded, app):
    app.config["WAITING_ROOM_TOKEN"] = "tv-secret"
    c = app.test_client()
    try:
        assert c.get("/appointments/waiting-room?t=tv-secret").status_code == 200
        assert c.get_cookie(WAITING_ROOM_COOKIE) is not None
        # the page's own fetch() carries the cookie, no token in the URL
        assert c.get("/appointments/api/queue").status_code == 200
    finally:
        app.config.pop("WAITING_ROOM_TOKEN", None)


def test_logged_in_staff_bypass_token_and_see_full_name(seeded, app):
    """Staff behaviour must not regress: the launcher widget reads owner_name."""
    app.config["WAITING_ROOM_TOKEN"] = "tv-secret"
    c = app.test_client()
    try:
        c.post("/auth/login", data={"username": "admin", "password": "1234"})
        resp = c.get("/appointments/api/queue")
        assert resp.status_code == 200, "staff must not be locked out by the token"
        assert resp.get_json()[0]["owner_name"] == "Ahmed El Gohary"
    finally:
        app.config.pop("WAITING_ROOM_TOKEN", None)


# ── T3: telemedicine price lookup ────────────────────────────────────────────

def test_telemedicine_price_uses_bound_like_and_real_column(app):
    from models.database import get_db
    from blueprints.telemedicine.routes import (
        _telemedicine_price, TELEMEDICINE_FALLBACK_PRICE)
    with app.app_context():
        c = get_db()
        # no matching service yet -> fallback, and no exception
        c.execute("DELETE FROM service_catalog WHERE LOWER(name) LIKE ?", ("%tele%",))
        c.commit()
        assert _telemedicine_price(c) == TELEMEDICINE_FALLBACK_PRICE

        c.execute("INSERT INTO service_catalog (code,name,category,standard_price,"
                  "is_active) VALUES (?,?,?,?,1)",
                  ("TELE1", "Telemedicine Consultation", "Consultation", 250.0))
        c.commit()
        assert _telemedicine_price(c) == 250.0
        c.close()


# ── T1: every gated role name exists ─────────────────────────────────────────

def test_role_required_names_are_seeded():
    import re
    from pathlib import Path
    from models.database import _SEED_ROLES

    seeded = {r[0] for r in _SEED_ROLES}
    owned = ["blueprints/petshop/routes.py", "blueprints/system/routes.py",
             "blueprints/appointments/routes.py", "blueprints/telemedicine/routes.py"]
    root = Path(__file__).parent.parent
    bad = []
    for rel in owned:
        for i, line in enumerate((root / rel).read_text(encoding="utf-8").splitlines(), 1):
            if "@role_required(" not in line:
                continue
            for name in re.findall(r'"([a-z_]+)"', line):
                if name not in seeded:
                    bad.append(f"{rel}:{i} {name}")
    assert not bad, f"unknown role names in @role_required: {bad}"
