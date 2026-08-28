# -*- coding: utf-8 -*-
"""The "export all my data" ZIP must not contain credentials.

/system/export/all dumps every table to CSV, and the README inside the ZIP tells
the clinic to open the files in Excel and keep a copy. So this archive gets
emailed, copied to a USB stick, and forwarded to whoever asks for "our data".

users.csv was carrying users.password_hash and users.totp_secret. One click
handed over every staff bcrypt hash and every TOTP seed - enough to sign in as
any of them, second factor included, and to keep doing so. It was unconditional
and shipped on every install.

These tests read the actual ZIP the route produces rather than inspecting the
constants, because the constants being right is not the same as the writer
using them.
"""
import csv
import io
import zipfile

import pytest

import models.database as db


@pytest.fixture
def admin(app):
    """Same shape as tests/test_system_routes.py:78 - /system/export/all is
    admin-only, so the plain auth_client gets a 302 and never sees a ZIP."""
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")
    return c


def _export(admin):
    r = admin.get("/system/export/all")
    assert r.status_code == 200, "export returned %d" % r.status_code
    return zipfile.ZipFile(io.BytesIO(r.data))


def _rows(zf, name):
    with zf.open(name) as fh:
        text = fh.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


@pytest.fixture
def a_user_with_secrets(app):
    """A throwaway user row that has something worth stealing in it.

    Deliberately a NEW row. The first version of this fixture UPDATEd the
    lowest-id user, which is `admin` - so it overwrote the very password the
    admin fixture logs in with, and every test after the first got a 302. The
    database is shared for the session, so that would have broken other files
    too, not just this one.
    """
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, "
                    "is_active, totp_secret) VALUES (?,?,?,?,?,?)",
                    ("export_secret_probe", "$2b$12$THISISABCRYPTHASHDONOTLEAKME",
                     "Export Probe", "receptionist", 0, "JBSWY3DPEHPK3PXP"))
        finally:
            conn.close()
    yield
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                conn.execute("DELETE FROM users WHERE username=?",
                             ("export_secret_probe",))
        finally:
            conn.close()


def test_users_csv_carries_no_password_hash(admin, a_user_with_secrets):
    zf = _export(admin)
    assert "users.csv" in zf.namelist(), "users table was not exported at all"
    rows = _rows(zf, "users.csv")
    assert rows, "users.csv is empty - this test would pass vacuously"
    for row in rows:
        assert row.get("password_hash", "") == "", (
            "a bcrypt hash left the server in users.csv")
        assert row.get("totp_secret", "") == "", (
            "a TOTP seed left the server in users.csv")


def test_the_column_is_still_there_just_empty(admin, a_user_with_secrets):
    """Blanked, not dropped - the export should stay a faithful table dump."""
    zf = _export(admin)
    rows = _rows(zf, "users.csv")
    assert "password_hash" in rows[0], "the column was removed rather than blanked"


def test_the_useful_columns_still_come_through(admin, a_user_with_secrets):
    """A redaction that empties the whole file is not a fix."""
    zf = _export(admin)
    rows = _rows(zf, "users.csv")
    assert any(r.get("username") for r in rows), (
        "usernames were lost - the export is no longer the clinic's data")


def test_the_hashed_backup_codes_table_is_not_exported(admin):
    zf = _export(admin)
    assert "totp_backup_codes.csv" not in zf.namelist(), (
        "every row of that table is a hashed second factor")


def test_no_bcrypt_prefix_anywhere_in_the_whole_archive(admin, a_user_with_secrets):
    """The backstop. Whatever the column is called, in whatever table, a bcrypt
    hash must not be anywhere in this ZIP."""
    zf = _export(admin)
    for name in zf.namelist():
        if not name.endswith(".csv"):
            continue
        blob = zf.read(name).decode("utf-8-sig", errors="ignore")
        for marker in ("$2a$", "$2b$", "$2y$"):
            assert marker not in blob, (
                "a bcrypt hash appears in %s" % name)
