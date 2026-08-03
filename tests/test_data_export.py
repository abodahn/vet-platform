# -*- coding: utf-8 -*-
"""Take your data with you.

The Data & Continuity Guarantee promises, in writing, that a clinic can read
its own records "in open formats, without the system and without us". Every
screen already had an Excel button and the nightly job wrote a database dump,
but neither is what a clinic needs the day it wants to leave: ONE file with
EVERYTHING, that any spreadsheet opens.

A guarantee the software cannot honour is worse than no guarantee, so this
tests the promise rather than the code.
"""
import csv
import io
import zipfile

import pytest

import models.database as db


@pytest.fixture()
def some_records(app):
    with app.app_context():
        conn = db.get_db()
        with conn:
            oid = conn.execute(
                "INSERT INTO owners(full_name, full_name_ar, phone) VALUES(?,?,?)",
                ("Export Owner", "مالك التصدير", "01044000111")).lastrowid
            conn.execute(
                "INSERT INTO pets(owner_id, pet_name, species, is_active) VALUES(?,?,?,1)",
                (oid, "ExportPet", "Cat"))
        conn.close()
    return oid


def _zip(client):
    r = client.get("/system/export/all")
    assert r.status_code == 200, f"export returned {r.status_code}"
    return zipfile.ZipFile(io.BytesIO(r.data))


def test_the_clinic_can_download_everything_at_once(auth_client, some_records):
    z = _zip(auth_client)
    names = z.namelist()
    assert len(names) > 20, f"only {len(names)} files — this is not the whole database"
    for essential in ("owners.csv", "pets.csv", "invoices.csv", "visits.csv"):
        assert essential in names, f"{essential} is missing from the export"


def test_the_records_are_actually_in_there(auth_client, some_records):
    z = _zip(auth_client)
    text = z.read("owners.csv").decode("utf-8-sig")
    assert "Export Owner" in text, "the export does not contain the clinic's own clients"
    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows and "full_name" in rows[0], "the CSV has no usable header row"


def test_arabic_survives_the_round_trip(auth_client, some_records):
    """The whole product is Arabic-first. An export that mangles Arabic names
    tells a clinic its data is corrupt."""
    z = _zip(auth_client)
    text = z.read("owners.csv").decode("utf-8-sig")
    assert "مالك التصدير" in text, "Arabic names did not survive the export"


def test_excel_on_a_windows_machine_will_not_mojibake_it(auth_client, some_records):
    """Without a BOM, Excel in Egypt opens UTF-8 Arabic as gibberish -- and the
    clinic concludes the export is broken rather than that Excel is."""
    z = _zip(auth_client)
    raw = z.read("owners.csv")
    assert raw.startswith(b"\xef\xbb\xbf"), "no UTF-8 BOM; Excel will mangle the Arabic"


def test_it_explains_itself_in_both_languages(auth_client, some_records):
    """A ZIP of 79 CSVs with no note is a puzzle, not a guarantee."""
    z = _zip(auth_client)
    assert "README.txt" in z.namelist()
    readme = z.read("README.txt").decode("utf-8-sig")
    assert "Excel" in readme
    assert "إكسل" in readme, "the note is English-only"


def test_our_logs_are_not_the_clinics_data(auth_client, some_records):
    """The export is the clinic's records, not our operational noise -- and it
    has to stay a size a receptionist can actually email."""
    z = _zip(auth_client)
    names = z.namelist()
    for noise in ("backend_logs.csv", "frontend_logs.csv", "user_sessions.csv",
                  "rate_hits.csv", "login_attempts.csv"):
        assert noise not in names, f"{noise} does not belong in a customer export"


def test_a_receptionist_cannot_walk_out_with_the_database(auth_client, app):
    """This is every client record in one file. It belongs to the owner."""
    from blueprints.hr.routes import _hash
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(username, full_name, role, "
                "password_hash, is_active) VALUES(?,?,?,?,1)",
                ("exp.recep", "Export Reception", "reception", _hash("Pass@2026")))
        conn.close()
    c = app.test_client()
    c.post("/auth/login", data={"username": "exp.recep", "password": "Pass@2026"})
    c.get("/")
    r = c.get("/system/export/all", follow_redirects=False)
    assert r.status_code in (302, 303, 401, 403), \
        f"a receptionist downloaded the entire database (status {r.status_code})"


def test_one_unreadable_table_does_not_lose_the_rest(auth_client, monkeypatch, some_records):
    """A clinic mid-migration can have a broken table. It must still get its
    other 78 -- losing everything because of one is the opposite of a guarantee."""
    import blueprints.system.routes as sysroutes
    real = sysroutes._export_tables
    monkeypatch.setattr(sysroutes, "_export_tables",
                        lambda conn: ["no_such_table_at_all"] + real(conn))
    z = _zip(auth_client)
    assert "owners.csv" in z.namelist(), "one bad table cost the clinic its whole export"
