# -*- coding: utf-8 -*-
"""A record's own name, in the reader's language.

t() localises the INTERFACE. Nothing localised the DATA: the schema carries
full_name_ar, name_ar and pet_name_ar, the clinic fills them in, and every
screen rendered the Latin column anyway. A clinic working in Arabic typed its
clients' Arabic names once and never saw them again -- in the product whose
single loudest claim is that it is Arabic-first.

Found while building the demo instance: 60 seeded clients all had Arabic names
and not one appeared on screen.
"""
import pytest

import models.database as db


@pytest.fixture()
def bilingual_owner(app):
    with app.app_context():
        conn = db.get_db()
        with conn:
            oid = conn.execute(
                "INSERT INTO owners(full_name, full_name_ar, phone) VALUES(?,?,?)",
                ("Ehab Serag", "إيهاب سراج", "01055000111")).lastrowid
            latin_only = conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Latin Only", "01055000222")).lastrowid
        conn.close()
    return oid, latin_only


def _as(client, lang):
    with client.session_transaction() as s:
        u = dict(s.get("user") or {})
        u["language"] = lang
        s["user"] = u
        s["lang"] = lang


def _render(app, expr, **ctx):
    from flask import render_template_string
    with app.test_request_context("/"):
        from flask import session
        session["user"] = {"id": 1, "username": "admin", "role": "super_admin",
                           "language": ctx.pop("lang", "en")}
        return render_template_string(expr, **ctx)


def test_arabic_reader_sees_the_arabic_name(app, bilingual_owner):
    oid, _ = bilingual_owner
    with app.app_context():
        row = dict(db.get_owner(oid)) if hasattr(db, "get_owner") else None
    if row is None:
        with app.app_context():
            conn = db.get_db()
            row = dict(conn.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone())
            conn.close()
    assert _render(app, "{{ loc(o,'full_name') }}", o=row, lang="ar") == "إيهاب سراج"


def test_english_reader_sees_the_latin_name(app, bilingual_owner):
    oid, _ = bilingual_owner
    with app.app_context():
        conn = db.get_db()
        row = dict(conn.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone())
        conn.close()
    assert _render(app, "{{ loc(o,'full_name') }}", o=row, lang="en") == "Ehab Serag"


def test_a_missing_arabic_name_falls_back_rather_than_blanking(app, bilingual_owner):
    """Half-filled records are the normal case during a migration. Showing an
    empty name would be worse than showing the Latin one."""
    _, latin_only = bilingual_owner
    with app.app_context():
        conn = db.get_db()
        row = dict(conn.execute("SELECT * FROM owners WHERE id=?", (latin_only,)).fetchone())
        conn.close()
    assert _render(app, "{{ loc(o,'full_name') }}", o=row, lang="ar") == "Latin Only"


def test_it_survives_a_row_without_the_arabic_column_at_all(app):
    """Plenty of queries select a subset of columns."""
    row = {"full_name": "Partial Row"}
    assert _render(app, "{{ loc(o,'full_name') }}", o=row, lang="ar") == "Partial Row"


def test_it_survives_a_missing_field_and_a_none_row(app):
    assert _render(app, "{{ loc(o,'nope') }}", o={"full_name": "x"}, lang="ar") == ""
    assert _render(app, "{{ loc(None,'full_name') }}", lang="ar") == ""


def test_the_client_list_shows_arabic_names_to_an_arabic_reader(app, bilingual_owner):
    """The screen this was actually broken on."""
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")
    _as(c, "ar")
    html = c.get("/crm/owners", follow_redirects=True).get_data(as_text=True)
    assert "إيهاب سراج" in html, "the client list still shows only Latin names in Arabic"


def test_the_client_list_shows_latin_names_to_an_english_reader(app, bilingual_owner):
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")
    _as(c, "en")
    html = c.get("/crm/owners", follow_redirects=True).get_data(as_text=True)
    assert "Ehab Serag" in html
