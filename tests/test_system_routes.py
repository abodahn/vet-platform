# -*- coding: utf-8 -*-
"""System administration routes: backup, restore, diagnostics, roles, sync,
and the data-migration download.

SAFETY. This module drives backup, upload and restore. Every test that could
overwrite a database calls `_safe(app)` first, which refuses to run unless the
target is the throwaway file conftest created under tmp_path. Destroying the
developer's database while testing backup software would be a memorable irony.

The restore tests that actually swap a file redirect models.backup at a fresh
tmp_path database, so even the session's throwaway DB is never replaced under
the other tests' feet.
"""
import json
import os
import sqlite3
import time
from datetime import date

import pytest

import models.audit as audit
import models.backup as bk
import models.database as db


# ── helpers ───────────────────────────────────────────────────────────────────

def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data=None, **kw):
    payload = dict(data or {})
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, **kw)


def _scalar(sql, params=()):
    c = db.get_db()
    try:
        row = c.execute(sql, params).fetchone()
        return row[0] if row else None
    finally:
        c.close()


def _exec(sql, params=()):
    c = db.get_db()
    try:
        with c:
            return c.execute(sql, params).lastrowid
    finally:
        c.close()


def _text(resp):
    return resp.data.decode("utf-8", "replace")


def _safe(app):
    """Refuse to run a destructive test against anything but the throwaway DB."""
    target = os.path.abspath(app.config["DATABASE_PATH"])
    repo_db = os.path.abspath(os.path.join(app.root_path, "data", "platform.db"))
    assert target != repo_db, (
        f"REFUSING TO RUN: the test app is pointed at the real database {target}")
    assert os.path.abspath(bk._db_path) == target, (
        f"models.backup targets {bk._db_path}, the app targets {target}")
    assert os.path.abspath(bk._backup_dir).startswith(
        os.path.dirname(target)), "backup dir is outside the throwaway tree"
    return target


@pytest.fixture
def admin(app):
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")
    return c


@pytest.fixture(autouse=True)
def _no_maintenance_left_behind():
    """A crashed test must not leave the whole app in 503."""
    yield
    try:
        bk.maintenance_off()
    except Exception:
        pass


def _archives():
    return sorted(f for f in os.listdir(bk._backup_dir) if f.endswith(".db"))


def _plant(name: str, payload: bytes) -> str:
    """Write a file straight into the backup directory and return its name."""
    with open(os.path.join(bk._backup_dir, name), "wb") as fh:
        fh.write(payload)
    return name


def _real_sqlite_bytes(tmp_path, table="notes", body="hello") -> bytes:
    p = tmp_path / "src.db"
    conn = sqlite3.connect(str(p))
    with conn:
        conn.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, body TEXT)")
        conn.execute(f"INSERT INTO {table} (body) VALUES (?)", (body,))
    conn.close()
    return p.read_bytes()


# ═════════════════════════════════════════════════════════════════════════════
# DIAGNOSTICS
# ═════════════════════════════════════════════════════════════════════════════

def test_diagnostics_reports_the_live_database_as_healthy(app, admin):
    target = _safe(app)
    body = _text(admin.get("/system/diagnostics"))
    assert "Database Integrity" in body
    assert "Super Admin User Exists" in body
    assert "Clinic Record" in body
    # The page must name the database it actually checked, not a hardcoded path.
    # On PostgreSQL there IS no database file to name -- the whole page used to
    # raise there, because every check was written against SQLite (a file,
    # PRAGMA, sqlite_master). It now reports the server instead, so the identity
    # assertion has to follow the engine rather than assume a filename.
    import models.database as _db
    if _db.is_postgres():
        assert "Database Server Reachable" in body
        assert "PostgreSQL" in body, "the page did not identify the server it checked"
    else:
        assert os.path.basename(target) in body
    assert 'class="status-fail"' not in body, (
        "a diagnostics check failed on a healthy database")
    assert body.count('class="status-pass"') >= 6


def test_diagnostics_is_closed_to_a_role_without_system_access(app, client):
    with client.session_transaction() as s:
        s["user"] = {"id": 1, "username": "r", "role": "reception", "full_name": "R"}
    r = client.get("/system/diagnostics")
    assert r.status_code == 302
    assert "/system/" not in r.headers["Location"]


# ═════════════════════════════════════════════════════════════════════════════
# BACKUP — the archive has to be a database, not just a file
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    bool(os.environ.get("TEST_POSTGRES_DSN")),
    reason="asserts SQLite archive internals; PostgreSQL backups are pg_dump files")
def test_backup_run_produces_a_readable_archive_holding_the_real_rows(app, admin):
    target = _safe(app)
    with app.app_context():
        live_users = _scalar("SELECT COUNT(*) FROM users")
    before = set(_archives())

    r = _post(admin, "/system/backup/run", follow_redirects=True)
    assert r.status_code == 200
    assert "Backup completed" in _text(r), "the route reported no successful backup"

    new = set(_archives()) - before
    assert len(new) == 1, f"expected exactly one new archive, got {sorted(new)}"
    path = os.path.join(bk._backup_dir, new.pop())

    assert os.path.getsize(path) > 512
    with open(path, "rb") as fh:
        assert fh.read(16) == b"SQLite format 3\x00"
    conn = sqlite3.connect(path)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == live_users
        assert conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0] >= 30
    finally:
        conn.close()


@pytest.mark.skipif(
    bool(os.environ.get("TEST_POSTGRES_DSN")),
    reason="asserts SQLite archive internals; PostgreSQL backups are pg_dump files")
def test_backup_run_writes_an_audit_row(app, admin):
    _safe(app)
    with app.app_context():
        before = _scalar("SELECT COUNT(*) FROM audit_log WHERE action='manual_backup'")
    _post(admin, "/system/backup/run", follow_redirects=True)
    with app.app_context():
        assert _scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='manual_backup'"
        ) == before + 1


def test_verify_accepts_a_genuine_archive(app, admin, tmp_path):
    _safe(app)
    name = _plant("platform_backup_20260101_010101.db",
                  _real_sqlite_bytes(tmp_path))
    body = _text(_post(admin, f"/system/backup/{name}/verify", follow_redirects=True))
    assert "is readable and complete" in body


def test_verify_refuses_a_truncated_archive(app, admin):
    """sqlite3 opens a zero-byte file as a valid EMPTY database and reports
    integrity_check = ok. Header and size checks are what stand between the
    clinic and a "successful" restore of nothing."""
    _safe(app)
    for label, payload in [("empty", b""),
                           ("truncated", b"SQLite format 3\x00" + b"\x00" * 100),
                           ("not a database", b"just some text" * 100)]:
        name = _plant(f"platform_backup_2026010{len(payload) % 9}_0000{len(label)}.db",
                      payload)
        body = _text(_post(admin, f"/system/backup/{name}/verify",
                           follow_redirects=True))
        assert "is NOT usable" in body, f"{label} archive was reported usable"


def test_verify_refuses_a_name_that_could_not_have_come_from_us(admin):
    assert _post(admin, "/system/backup/notes.txt/verify").status_code == 400
    assert _post(admin, "/system/backup/.hidden.db/verify").status_code == 400


def test_verify_404s_for_a_plausible_name_that_is_not_there(admin):
    assert _post(admin,
                 "/system/backup/platform_backup_19990101_000000.db/verify"
                 ).status_code == 404


# ── upload from a USB stick ──────────────────────────────────────────────────

def _upload(client, payload: bytes, filename: str):
    return _post(client, "/system/backup/upload",
                 {"archive": (__import__("io").BytesIO(payload), filename)},
                 content_type="multipart/form-data", follow_redirects=True)


def test_upload_keeps_a_verified_archive(app, admin, tmp_path):
    _safe(app)
    before = set(_archives())
    body = _text(_upload(admin, _real_sqlite_bytes(tmp_path), "from_usb.db"))
    assert "Uploaded and verified" in body

    new = set(_archives()) - before
    assert len(new) == 1
    name = new.pop()
    assert name.startswith("uploaded_")
    stored = os.path.join(bk._backup_dir, name)
    conn = sqlite3.connect(stored)
    try:
        assert conn.execute("SELECT body FROM notes").fetchone()[0] == "hello"
    finally:
        conn.close()


@pytest.mark.parametrize("label,payload", [
    ("zero-byte", b""),
    ("truncated", b"SQLite format 3\x00" + b"\x00" * 200),
    ("random bytes", b"\x00\x01\x02" * 500),
])
def test_upload_does_not_keep_an_unusable_archive(app, admin, label, payload):
    _safe(app)
    before = set(_archives())
    body = _text(_upload(admin, payload, "from_usb.db"))
    assert "is not a usable backup" in body, f"{label} was accepted"
    assert set(_archives()) == before, f"{label} was left on disk after rejection"


def test_upload_refuses_a_non_archive_extension(app, admin):
    _safe(app)
    before = set(os.listdir(bk._backup_dir))
    body = _text(_upload(admin, b"MZ\x90\x00", "payload.exe"))
    assert "Only .db" in body
    assert set(os.listdir(bk._backup_dir)) == before


def test_upload_with_no_file_selected_changes_nothing(app, admin):
    _safe(app)
    before = set(os.listdir(bk._backup_dir))
    body = _text(_post(admin, "/system/backup/upload", follow_redirects=True))
    assert "Choose a backup file first" in body
    assert set(os.listdir(bk._backup_dir)) == before


def test_upload_writes_an_audit_row(app, admin, tmp_path):
    _safe(app)
    with app.app_context():
        before = _scalar("SELECT COUNT(*) FROM audit_log WHERE action='backup_upload'")
    _upload(admin, _real_sqlite_bytes(tmp_path), "usb.db")
    with app.app_context():
        assert _scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='backup_upload'"
        ) == before + 1


# ═════════════════════════════════════════════════════════════════════════════
# RESTORE — refuse anything unreadable, snapshot before anything readable
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("label,payload", [
    ("zero-byte", b""),
    ("truncated header", b"SQLite format 3\x00" + b"\x00" * 100),
    ("garbage", b"not a database at all" * 40),
])
@pytest.mark.skipif(
    bool(os.environ.get("TEST_POSTGRES_DSN")),
    reason="asserts SQLite archive internals; PostgreSQL backups are pg_dump files")
def test_restore_refuses_a_corrupt_archive_and_touches_nothing(app, admin,
                                                               label, payload):
    """The live database must be byte-identical afterwards and no pre-restore
    snapshot may exist: refusal happens before anything is opened for writing."""
    target = _safe(app)
    with app.app_context():
        users_before = _scalar("SELECT COUNT(*) FROM users")
    size_before = os.path.getsize(target)
    snaps_before = [f for f in os.listdir(bk._backup_dir)
                    if f.startswith("pre_restore_")]

    name = _plant(f"platform_backup_20250101_0000{len(label) % 60:02d}.db", payload)
    body = _text(_post(admin, f"/system/backup/{name}/restore",
                       {"confirm_filename": name}, follow_redirects=True))

    assert "not a usable backup" in body, f"{label} archive was not refused"
    assert "nothing was changed" in body
    assert os.path.getsize(target) == size_before, f"{label} restore touched the DB"
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM users") == users_before
        assert _scalar("PRAGMA integrity_check") == "ok"
    assert [f for f in os.listdir(bk._backup_dir)
            if f.startswith("pre_restore_")] == snaps_before, (
        "a refused restore still snapshotted, so it had already started")
    assert bk.maintenance_active() is None, "maintenance was left on after a refusal"


@pytest.mark.skipif(
    bool(os.environ.get("TEST_POSTGRES_DSN")),
    reason="swaps a SQLite database file; PostgreSQL restores are pg_restore")
def test_restore_is_cancelled_when_the_typed_filename_does_not_match(app, admin,
                                                                     tmp_path):
    target = _safe(app)
    size_before = os.path.getsize(target)
    name = _plant("platform_backup_20250202_020202.db",
                  _real_sqlite_bytes(tmp_path))
    body = _text(_post(admin, f"/system/backup/{name}/restore",
                       {"confirm_filename": "something-else.db"},
                       follow_redirects=True))
    assert "Restore cancelled" in body
    assert os.path.getsize(target) == size_before


def test_restore_refuses_a_traversal_filename(admin):
    assert _post(admin, "/system/backup/evil.txt/restore",
                 {"confirm_filename": "evil.txt"}).status_code == 400


@pytest.mark.parametrize("stamp,why", [
    ("20260303_030303", "older than RETENTION_DAYS — the archive you actually "
                        "reach for when something went wrong months ago"),
    (None, "fresh, taken today"),
])
@pytest.mark.skipif(
    bool(os.environ.get("TEST_POSTGRES_DSN")),
    reason="asserts SQLite archive internals; PostgreSQL backups are pg_dump files")
def test_a_good_restore_snapshots_first_then_swaps(app, admin, tmp_path,
                                                   monkeypatch, stamp, why):
    """Driven through the real route, but pointed at a fresh database in
    tmp_path so the session's throwaway DB is never replaced mid-suite.

    The aged-archive case is a regression guard: retention used to run inside
    the pre-restore snapshot, so restoring an archive older than
    RETENTION_DAYS deleted that archive mid-restore, copied the empty file
    sqlite3.connect() then created over the live database, and reported
    "Database restored". Every row, gone, with a success message.
    """
    _safe(app)
    live = tmp_path / "live.db"
    backups = tmp_path / "backups"
    backups.mkdir()
    conn = sqlite3.connect(str(live))
    with conn:
        conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
        conn.execute("INSERT INTO notes (body) VALUES ('BEFORE')")
    conn.close()

    monkeypatch.setattr(bk, "_db_path", str(live))
    monkeypatch.setattr(bk, "_backup_dir", str(backups))
    stamp = stamp or time.strftime("%Y%m%d_%H%M%S")
    name = f"platform_backup_{stamp}.db"
    (backups / name).write_bytes(_real_sqlite_bytes(tmp_path, body="AFTER"))

    body = _text(_post(admin, f"/system/backup/{name}/restore",
                       {"confirm_filename": name}, follow_redirects=True))
    assert "Database restored" in body

    conn = sqlite3.connect(str(live))
    try:
        assert conn.execute("SELECT body FROM notes").fetchone()[0] == "AFTER"
    finally:
        conn.close()

    snaps = [f for f in os.listdir(str(backups)) if f.startswith("pre_restore_")]
    assert len(snaps) == 1, "the previous database was not snapshotted"
    conn = sqlite3.connect(os.path.join(str(backups), snaps[0]))
    try:
        assert conn.execute("SELECT body FROM notes").fetchone()[0] == "BEFORE", (
            "the snapshot does not contain the data it replaced — the undo is fake")
    finally:
        conn.close()
    assert bk.maintenance_active() is None


# ═════════════════════════════════════════════════════════════════════════════
# MAINTENANCE MODE
# ═════════════════════════════════════════════════════════════════════════════

def test_maintenance_marker_holds_traffic_off_and_the_escape_hatch_clears_it(
        app, admin):
    _safe(app)
    bk.maintenance_on("unit test")
    try:
        blocked = admin.get("/reports/")
        assert blocked.status_code == 503
        assert "Maintenance in progress" in _text(blocked)
        # the backup screens stay reachable, or the operator is locked out too
        assert admin.get("/system/backup").status_code == 200

        r = _post(admin, "/system/backup/maintenance/off", follow_redirects=True)
        assert "Maintenance mode cleared" in _text(r)
        assert bk.maintenance_active() is None
        assert not os.path.exists(os.path.join(bk._backup_dir, bk._MAINT_FILE))
    finally:
        bk.maintenance_off()

    assert admin.get("/reports/").status_code in (200, 302)


def test_maintenance_off_writes_an_audit_row(app, admin):
    _safe(app)
    with app.app_context():
        before = _scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='maintenance_cleared'")
    _post(admin, "/system/backup/maintenance/off", follow_redirects=True)
    with app.app_context():
        assert _scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='maintenance_cleared'"
        ) == before + 1


# ═════════════════════════════════════════════════════════════════════════════
# ROLES AND PERMISSIONS
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def temp_role(app):
    """A role name unique to this test, cleaned up afterwards."""
    name = f"tmp_role_{int(time.time() * 1000) % 1_000_000}"
    yield name
    with app.app_context():
        _exec("DELETE FROM roles WHERE name=?", (name,))


def test_roles_users_api_returns_staff_without_their_secrets(app, admin):
    rows = admin.get("/system/roles/users").get_json()
    assert isinstance(rows, list) and rows
    assert any(r["username"] == "admin" for r in rows)
    assert set(rows[0]) == {"id", "username", "full_name", "role", "is_active"}, (
        "the staff list leaked columns beyond the five it selects")
    for r in rows:
        assert "password_hash" not in r and "totp_secret" not in r


def test_role_create_stores_the_permission_list_it_was_given(app, admin, temp_role):
    _post(admin, "/system/roles/create", {
        "name": temp_role.upper().replace("_", " "),
        "display_name": "Temp Role", "display_name_ar": "دور",
        "color": "#123456", "permissions": ["patients", "appointments"],
    }, follow_redirects=True)

    with app.app_context():
        row = db.get_db().execute(
            "SELECT * FROM roles WHERE name=?", (temp_role,)).fetchone()
        assert row is not None, "role_create redirected but wrote no row"
        assert json.loads(row["permissions_json"]) == ["patients", "appointments"]
        assert row["display_name"] == "Temp Role"
        assert row["color"] == "#123456"


def test_role_create_without_a_name_writes_nothing(app, admin):
    with app.app_context():
        before = _scalar("SELECT COUNT(*) FROM roles")
    body = _text(_post(admin, "/system/roles/create",
                       {"name": "", "display_name": "X"}, follow_redirects=True))
    assert "required" in body
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM roles") == before


def test_role_edit_rewrites_the_permission_list_and_records_the_diff(
        app, admin, temp_role):
    with app.app_context():
        rid = db.create_role(temp_role, "Before", "", ["patients"], "#000000")
        before_audit = _scalar(
            "SELECT COUNT(*) FROM audit_log WHERE action='edit_role'")

    _post(admin, f"/system/roles/{rid}/edit", {
        "display_name": "After", "display_name_ar": "",
        "color": "#ffffff", "permissions": ["accounting", "reports"],
    }, follow_redirects=True)

    with app.app_context():
        row = db.get_db().execute("SELECT * FROM roles WHERE id=?", (rid,)).fetchone()
        assert json.loads(row["permissions_json"]) == ["accounting", "reports"]
        assert row["display_name"] == "After"
        assert _scalar("SELECT COUNT(*) FROM audit_log WHERE action='edit_role'"
                       ) == before_audit + 1
        details = _scalar("SELECT details FROM audit_log WHERE action='edit_role'"
                          " ORDER BY id DESC LIMIT 1")
        changes = audit.parse_details(details)
        assert changes, "the role edit recorded no field-level diff"
        assert "permissions_json" in changes, (
            "a permission rewrite was audited without saying what changed")
        assert json.loads(changes["permissions_json"]["from"]) == ["patients"]
        assert json.loads(changes["permissions_json"]["to"]) == ["accounting",
                                                                "reports"]


def test_role_edit_takes_effect_immediately_for_has_permission(app, admin,
                                                              temp_role):
    """`_role_permissions` caches for 60s. Without a cache flush on save, an
    admin who revokes access watches nothing happen for a minute."""
    from blueprints.auth.routes import has_permission, clear_permission_cache
    with app.app_context():
        rid = db.create_role(temp_role, "Cached", "", ["accounting"], "#000000")
        clear_permission_cache()
        assert has_permission("accounting.view", temp_role) is True

    _post(admin, f"/system/roles/{rid}/edit", {
        "display_name": "Cached", "permissions": ["patients"],
    }, follow_redirects=True)

    with app.app_context():
        assert has_permission("accounting.view", temp_role) is False, (
            "a revoked permission was still granted from a stale cache")


def test_role_delete_removes_the_row(app, admin, temp_role):
    with app.app_context():
        rid = db.create_role(temp_role, "Doomed", "", ["patients"], "#000000")
    _post(admin, f"/system/roles/{rid}/delete", follow_redirects=True)
    with app.app_context():
        assert _scalar("SELECT COUNT(*) FROM roles WHERE id=?", (rid,)) == 0


def test_a_role_still_held_by_staff_cannot_be_deleted(app, admin, temp_role):
    """WAS a pinned known gap; now closed.

    users.role is free text with no foreign key, so deleting the role row left
    every holder on an orphan role. The permission check then fell OPEN on an
    unknown role, which meant deleting a role silently promoted everyone who
    held it — a nurse gained Finance, Accounting and Inventory. The fall-open
    is fixed, so the same delete would now lock those people out instead.
    Neither outcome is acceptable silently, so the delete is refused while
    anyone still holds the role.
    """
    with app.app_context():
        rid = db.create_role(temp_role, "Held", "", ["patients"], "#000000")
        uid = _exec("INSERT INTO users (username, password_hash, full_name, role)"
                    " VALUES (?,?,?,?)",
                    (f"holder_{temp_role}", "x", "Holder", temp_role))
    try:
        _post(admin, f"/system/roles/{rid}/delete", follow_redirects=True)
        with app.app_context():
            assert _scalar("SELECT COUNT(*) FROM roles WHERE id=?", (rid,)) == 1, \
                "the role was deleted while staff still held it"
            assert _scalar("SELECT role FROM users WHERE id=?", (uid,)) == temp_role

            # Move the holder off, and it deletes cleanly.
            _exec("UPDATE users SET role='nurse' WHERE id=?", (uid,))
        _post(admin, f"/system/roles/{rid}/delete", follow_redirects=True)
        with app.app_context():
            assert _scalar("SELECT COUNT(*) FROM roles WHERE id=?", (rid,)) == 0, \
                "an unheld role could not be deleted"
    finally:
        with app.app_context():
            _exec("DELETE FROM users WHERE id=?", (uid,))


def test_role_assign_changes_the_users_role_row(app, admin):
    with app.app_context():
        uid = _exec("INSERT INTO users (username, password_hash, full_name, role)"
                    " VALUES (?,?,?,?)", ("assignee_x", "x", "Assignee", "staff"))
    try:
        _post(admin, "/system/roles/assign",
              {"user_id": str(uid), "role": "nurse"}, follow_redirects=True)
        with app.app_context():
            assert _scalar("SELECT role FROM users WHERE id=?", (uid,)) == "nurse"
            assert _scalar(
                "SELECT COUNT(*) FROM audit_log WHERE action='assign_role'"
                " AND entity_id=?", (str(uid),)) >= 1
    finally:
        with app.app_context():
            _exec("DELETE FROM users WHERE id=?", (uid,))


def test_role_assign_without_a_role_changes_nothing(app, admin):
    with app.app_context():
        uid = _exec("INSERT INTO users (username, password_hash, full_name, role)"
                    " VALUES (?,?,?,?)", ("assignee_y", "x", "Assignee", "staff"))
    try:
        body = _text(_post(admin, "/system/roles/assign",
                           {"user_id": str(uid), "role": ""},
                           follow_redirects=True))
        assert "required" in body
        with app.app_context():
            assert _scalar("SELECT role FROM users WHERE id=?", (uid,)) == "staff"
    finally:
        with app.app_context():
            _exec("DELETE FROM users WHERE id=?", (uid,))


def test_a_grant_alone_does_not_unlock_a_privileged_route(
        app, admin, client, temp_role):
    """Was a pinned KNOWN GAP; now pins the boundary between the two gates.

    It used to read: "NO route and NO template calls has_permission()... So
    granting system and backup to a custom role changes the database and
    changes nothing about access." Routes honour grants now — but a grant says
    which MODULE you may enter, not what you may do inside it. /system/monitor
    still requires the role, so a custom role holding every system permission
    is still refused, and a built-in role stripped of grants keeps working.
    """
    from blueprints.auth.routes import has_permission, clear_permission_cache

    _post(admin, "/system/roles/create", {
        "name": temp_role, "display_name": "Full Access",
        "permissions": ["system", "backup", "audit", "settings"],
    }, follow_redirects=True)

    with app.app_context():
        clear_permission_cache()
        # the data says yes …
        assert has_permission("system.view", temp_role) is True
        assert has_permission("backup.run", temp_role) is True

    # … and the routes do not ask.
    with client.session_transaction() as s:
        s["user"] = {"id": 1, "username": "granted", "role": temp_role,
                     "full_name": "Granted"}
    denied = client.get("/system/monitor")
    assert denied.status_code == 302, (
        "a route now honours permissions_json — update this test")
    assert "/system/" not in denied.headers["Location"]

    # And the mirror image: a built-in role stripped of every permission keeps
    # the access its hardcoded name grants.
    with app.app_context():
        rid = _scalar("SELECT id FROM roles WHERE name='support_admin'")
    if rid:
        _post(admin, f"/system/roles/{rid}/edit",
              {"display_name": "Support Admin", "permissions": []},
              follow_redirects=True)
        with client.session_transaction() as s:
            s["user"] = {"id": 1, "username": "sa", "role": "support_admin",
                         "full_name": "SA"}
        assert client.get("/system/monitor").status_code == 200, (
            "support_admin lost access — a route now reads permissions_json")


# ═════════════════════════════════════════════════════════════════════════════
# SYNC DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def conflict(app):
    cid = f"cf-{int(time.time() * 1000)}"
    qid = f"sq-{int(time.time() * 1000)}"
    with app.app_context():
        _exec("INSERT INTO sync_queue (id, local_uuid, device_id, entity_name,"
              " operation_type, payload, status) VALUES (?,?,?,?,?,?,?)",
              (qid, "u1", "DEVICE-A", "owners", "INSERT", "{}", "PENDING"))
        _exec("INSERT INTO sync_conflicts (id, sync_queue_id, entity_name,"
              " local_payload, server_payload, conflict_type, resolution_status)"
              " VALUES (?,?,?,?,?,?,?)",
              (cid, qid, "owners", "{}", "{}", "UPDATE_UPDATE", "PENDING"))
    yield {"conflict_id": cid, "queue_id": qid}
    with app.app_context():
        _exec("DELETE FROM sync_conflicts WHERE id=?", (cid,))
        _exec("DELETE FROM sync_queue WHERE id=?", (qid,))


def test_sync_dashboard_shows_the_pending_queue_and_conflicts(admin, conflict):
    body = _text(admin.get("/system/sync"))
    assert "DEVICE-A" in body, "a pending sync item did not render"
    assert conflict["conflict_id"] in body, "an unresolved conflict did not render"


def test_sync_dashboard_filter_narrows_the_queue(app, admin, conflict):
    """The conflicts table is not device-filtered, so assert on a queue row
    that has no conflict attached to it."""
    qid = f"sq-plain-{int(time.time() * 1000)}"
    marker = f'{{"marker": "{qid}"}}'      # the payload IS rendered; the id is not
    with app.app_context():
        _exec("INSERT INTO sync_queue (id, local_uuid, device_id, entity_name,"
              " operation_type, payload, status) VALUES (?,?,?,?,?,?,?)",
              (qid, "u2", "DEVICE-B", "pets", "UPDATE", marker, "PENDING"))
    try:
        assert qid in _text(admin.get("/system/sync?device=DEVICE-B"))
        assert qid not in _text(admin.get("/system/sync?device=DEVICE-A"))
        assert qid in _text(admin.get("/system/sync?status=PENDING"))
        assert qid not in _text(admin.get("/system/sync?status=SYNCED"))
    finally:
        with app.app_context():
            _exec("DELETE FROM sync_queue WHERE id=?", (qid,))


def test_resolving_a_conflict_marks_it_and_records_who_did_it(app, admin, conflict):
    body = _text(_post(admin,
                       f"/system/sync/conflicts/{conflict['conflict_id']}/resolve",
                       {"keep": "local"}, follow_redirects=True))
    # "keep": "local" — and nothing in this system pushes the device's copy
    # back over the server record, so the page must NOT claim it kept the local
    # version. It used to say exactly that.
    assert "Conflict" in body
    assert "KEPT LOCAL" in body, \
        "the page no longer says which side was actually kept"
    with app.app_context():
        row = db.get_db().execute("SELECT * FROM sync_conflicts WHERE id=?",
                                  (conflict["conflict_id"],)).fetchone()
        assert row["resolution_status"] == "MANUAL_RESOLVED_LOCAL", (
            "which side was kept is not recorded, so nobody can tell "
            "afterwards what happened to the device's data")
        assert row["resolved_by"]
        assert row["resolved_at"]
        assert _scalar("SELECT COUNT(*) FROM audit_log"
                       " WHERE action='resolve_conflict' AND entity_id=?",
                       (conflict["conflict_id"],)) == 1


def test_resolving_a_conflict_that_does_not_exist_still_claims_success(app, admin,
                                                                      conflict):
    """KNOWN GAP, pinned: resolve_conflict UPDATEs by id and never checks the
    rowcount, so a stale bookmark reports "Conflict resolved" having done
    nothing. The real conflict must be untouched."""
    body = _text(_post(admin, "/system/sync/conflicts/no-such-id/resolve",
                       {"keep": "server"}, follow_redirects=True))
    assert "Conflict resolved" in body
    with app.app_context():
        assert _scalar("SELECT resolution_status FROM sync_conflicts WHERE id=?",
                       (conflict["conflict_id"],)) == "PENDING"


# ═════════════════════════════════════════════════════════════════════════════
# DATA MIGRATION — failed-rows download
# ═════════════════════════════════════════════════════════════════════════════

def test_failed_rows_redirects_when_nothing_is_staged(admin):
    with admin.session_transaction() as s:
        s.pop("import_file", None)
    r = admin.get("/migration/failed-rows.csv")
    assert r.status_code == 302
    assert "/migration" in r.headers["Location"]


def test_failed_rows_serves_the_staged_csv_as_excel_readable_utf8(app, admin):
    """utf-8-sig, or Excel opens the Arabic columns as mojibake."""
    token = "abc123def456"
    staging = os.path.join(app.config["UPLOADS_PATH"], "import_staging")
    os.makedirs(staging, exist_ok=True)
    csv_path = os.path.join(staging, f"{token}.failed.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write("row,error\n2,اسم المالك مفقود\n")
    try:
        with admin.session_transaction() as s:
            s["import_file"] = {"token": token, "ext": ".xlsx", "name": "x.xlsx"}
        r = admin.get("/migration/failed-rows.csv")
        assert r.status_code == 200
        assert "rows_to_fix.csv" in r.headers["Content-Disposition"]
        assert r.data.startswith(b"\xef\xbb\xbf"), "the BOM Excel needs is missing"
        assert "اسم المالك مفقود" in r.data.decode("utf-8-sig")
    finally:
        os.remove(csv_path)
        with admin.session_transaction() as s:
            s.pop("import_file", None)


def test_failed_rows_rejects_a_token_that_is_not_a_plain_hex_id(app, admin):
    """The token comes out of the session and is pasted into a filesystem path."""
    with admin.session_transaction() as s:
        s["import_file"] = {"token": "../../../data/platform", "ext": ".xlsx",
                            "name": "x.xlsx"}
    try:
        r = admin.get("/migration/failed-rows.csv")
        assert r.status_code == 302, "a traversal token was accepted"
    finally:
        with admin.session_transaction() as s:
            s.pop("import_file", None)
