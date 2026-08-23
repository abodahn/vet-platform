"""
Backup / restore tests.

SQLite only, no PostgreSQL, and never the developer's database: every test
runs against a throwaway file under tmp_path. Destroying a real database while
testing backup software would be a memorable irony.

Skipped entirely under TEST_POSTGRES_DSN. These assert the internals of a
SQLite archive -- the magic header, PRAGMA integrity_check, sqlite_master --
and the PostgreSQL path correctly produces a pg_dump instead, which has none of
those. They used to "pass" on a PostgreSQL session only because _postgres_dsn()
read an environment variable the test never set, so the backup went looking for
a SQLite file while the app's data was in PostgreSQL. That was the bug, not the
skip: a deployment configured through app config rather than POSTGRES_DSN got a
nightly backup that failed with "source database is not there".
"""
import os
import sqlite3

import pytest

import models.backup as bk

pytestmark = pytest.mark.skipif(
    bool(os.environ.get("TEST_POSTGRES_DSN")),
    reason="asserts SQLite archive internals; the PostgreSQL path produces a pg_dump",
)


def _seed(path: str, note: str) -> None:
    conn = sqlite3.connect(path)
    with conn:
        conn.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT)")
        conn.execute("INSERT INTO notes (body) VALUES (?)", (note,))
    conn.close()


def _notes(path: str) -> list:
    conn = sqlite3.connect(path)
    rows = [r[0] for r in conn.execute("SELECT body FROM notes ORDER BY id")]
    conn.close()
    return rows


@pytest.fixture
def live(tmp_path, monkeypatch):
    """models.backup pointed at a throwaway database in tmp_path.

    Module globals are process-wide, so they are restored afterwards — the same
    leak conftest guards for models.database.
    """
    monkeypatch.setenv("POSTGRES_DSN", "")
    monkeypatch.delenv("BACKUP_OFFSITE_DIR", raising=False)
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    db_file = tmp_path / "live.db"
    _seed(str(db_file), "before")
    saved = (bk._db_path, bk._backup_dir)
    bk.configure(db_path=str(db_file), backup_dir=str(tmp_path / "backups"))
    yield db_file
    bk.maintenance_off()
    bk._db_path, bk._backup_dir = saved


def _age_backup(name: str, stamp: str) -> str:
    """Rename an archive so it looks older. Age comes from the filename."""
    old = os.path.join(bk._backup_dir, name)
    new = os.path.join(bk._backup_dir, f"platform_backup_{stamp}.db")
    os.rename(old, new)
    return os.path.basename(new)


# ── Backup ────────────────────────────────────────────────────────────────────

def test_backup_is_created_and_passes_integrity(live):
    result = bk.run_backup()
    assert result["success"], result
    assert os.path.exists(result["filepath"])
    assert result["integrity"] == "ok"
    assert bk.verify_backup(result["filename"])["success"]
    assert _notes(result["filepath"]) == ["before"]


def test_failed_backup_reports_failure_not_success(live, tmp_path):
    """The original bug: a backup that could not run logged success anyway."""
    bk._db_path = str(tmp_path / "gone" / "missing.db")
    result = bk.run_backup()
    assert result["success"] is False
    assert result["error"]
    assert result["filename"] == ""
    assert bk.list_backups() == []


def test_backup_takes_the_migration_blueprints_positional_arg(live):
    """blueprints/migration calls run_backup(path) — must not TypeError."""
    assert bk.run_backup(str(live))["success"]


# ── Verification ──────────────────────────────────────────────────────────────

def test_corrupt_archive_is_refused(live):
    name = bk.run_backup()["filename"]
    path = os.path.join(bk._backup_dir, name)
    with open(path, "r+b") as fh:          # truncate: header intact, body gone
        fh.truncate(os.path.getsize(path) // 2)

    check = bk.verify_backup(name)
    assert check["success"] is False

    result = bk.restore_backup(name)
    assert result["success"] is False
    assert "not a usable backup" in result["message"]
    assert _notes(str(live)) == ["before"]          # live database untouched


def test_empty_file_is_not_a_valid_backup(live):
    """sqlite3 reports integrity_check 'ok' for a zero-byte file."""
    path = os.path.join(bk._backup_dir, "platform_backup_20260101_000000.db")
    open(path, "wb").close()
    assert bk.verify_backup(os.path.basename(path))["success"] is False


def test_path_traversal_is_refused(live):
    """`filename` comes from a URL segment — it must never leave the backup dir."""
    for attempt in ("../../platform.db", r"..\..\data\platform.db",
                    "/etc/passwd", ".maintenance.json", ""):
        resolved = bk.resolve_archive(attempt)
        assert resolved == "" or os.path.dirname(resolved) == str(
            bk._backup_dir), attempt
    assert bk.restore_backup("../../platform.db")["success"] is False
    assert os.path.exists(str(live))


# ── Restore ───────────────────────────────────────────────────────────────────

def test_restore_snapshots_the_current_database_first(live):
    name = bk.run_backup()["filename"]
    _seed(str(live), "after")

    result = bk.restore_backup(name)
    assert result["success"], result

    snapshot = result["snapshot"]
    assert snapshot.startswith("pre_restore_")
    # The snapshot must hold what was live at restore time, or the restore is
    # not undoable.
    assert _notes(os.path.join(bk._backup_dir, snapshot)) == ["before", "after"]


def test_restore_round_trips_the_data(live):
    name = bk.run_backup()["filename"]
    _seed(str(live), "after")
    assert _notes(str(live)) == ["before", "after"]

    assert bk.restore_backup(name)["success"]
    assert _notes(str(live)) == ["before"]

    # …and undoing it puts "after" back.
    snapshot = [b for b in bk.list_backups() if b["kind"] == "pre-restore"][0]
    assert bk.restore_backup(snapshot["filename"])["success"]
    assert _notes(str(live)) == ["before", "after"]


def test_restore_clears_maintenance_mode_afterwards(live):
    name = bk.run_backup()["filename"]
    assert bk.restore_backup(name)["success"]
    assert bk.maintenance_active() is None


def test_restore_leaves_no_maintenance_marker_on_failure(live):
    assert bk.restore_backup("platform_backup_20260101_000000.db")["success"] is False
    assert bk.maintenance_active() is None


def test_backup_is_skipped_while_a_restore_is_running(live):
    bk.maintenance_on("test")
    try:
        assert bk.run_backup()["success"] is False
    finally:
        bk.maintenance_off()


def test_stale_maintenance_marker_expires(live, monkeypatch):
    bk.maintenance_on("test")
    assert bk.maintenance_active() is not None
    monkeypatch.setattr(bk, "MAINTENANCE_MAX_MINUTES", -1)
    assert bk.maintenance_active() is None   # a crashed restore cannot lock a clinic out


# ── Upload ────────────────────────────────────────────────────────────────────

class _FakeUpload:
    def __init__(self, src):
        self.src = src

    def save(self, dest):
        with open(self.src, "rb") as s, open(dest, "wb") as d:
            d.write(s.read())


def test_uploaded_backup_is_verified_and_bad_ones_are_dropped(live, tmp_path):
    good = os.path.join(bk._backup_dir, bk.run_backup()["filename"])
    result = bk.accept_upload(_FakeUpload(good), "from_usb.db")
    assert result["success"] and result["filename"].startswith("uploaded_")

    junk = tmp_path / "junk.db"
    junk.write_bytes(b"this is a holiday photo, not a database" * 40)
    bad = bk.accept_upload(_FakeUpload(str(junk)), "junk.db")
    assert bad["success"] is False
    assert not [b for b in bk.list_backups() if b["size_kb"] < 1]


def test_upload_rejects_wrong_extension(live):
    assert bk.accept_upload(None, "invoice.pdf")["success"] is False


# ── Health / staleness ────────────────────────────────────────────────────────

def test_health_reports_no_backup(live):
    h = bk.health()
    assert h["has_backup"] is False and h["stale"] is True


def test_fresh_backup_is_not_stale(live):
    bk.run_backup()
    h = bk.health()
    assert h["has_backup"] and h["stale"] is False and h["ok"]


@pytest.mark.parametrize("stamp,stale", [("20260726_120000", False),   # ~1 day
                                         ("20260720_120000", True)])   # ~8 days
def test_stale_detection_fires_at_the_right_age(live, monkeypatch, stamp, stale):
    """STALE_AFTER_DAYS = 2, so yesterday is fine and last week is not."""
    import datetime as _dt

    class _Now(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 27, 12, 0, 0)

    _age_backup(bk.run_backup()["filename"], stamp)
    monkeypatch.setattr(bk, "datetime", _Now)
    assert bk.health()["stale"] is stale


def test_stale_backup_notifies_managers(live, app, monkeypatch):
    sent = []
    monkeypatch.setattr("models.database.notify_managers",
                        lambda **kw: sent.append(kw))
    _age_backup(bk.run_backup()["filename"], "20200101_000000")
    with app.app_context():
        assert bk.check_and_notify()["stale"] is True
    assert sent and "/system/backup" in sent[0]["link"]

    sent.clear()
    with app.app_context():
        bk.check_and_notify()
    assert sent == []                      # cooldown: alert once, not every page load


def test_failed_backup_notifies_managers(live, app, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr("models.database.notify_managers",
                        lambda **kw: sent.append(kw))
    bk._db_path = str(tmp_path / "gone" / "missing.db")
    with app.app_context():
        assert bk.run_backup()["success"] is False
    assert sent and sent[0]["title"] == "Backup FAILED"


# ── Off-site ──────────────────────────────────────────────────────────────────

def test_offsite_is_skipped_cleanly_when_unset(live):
    assert bk.offsite_targets() == []
    assert bk.run_backup()["offsite"] == []


def test_offsite_folder_copy(live, tmp_path, monkeypatch):
    """UPDATED when off-site copies became encrypted.

    An off-site copy leaves the building - this is the USB-stick case - so it
    is now sealed before it goes and arrives as <name>.enc. The key is set here
    because without one the copy is refused outright, which is the subject of
    tests/test_backup_encryption.py rather than of this one.
    """
    from cryptography.fernet import Fernet
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    usb = tmp_path / "usb"
    monkeypatch.setenv("BACKUP_OFFSITE_DIR", str(usb))
    result = bk.run_backup()
    assert result["offsite"][0]["ok"] is True

    landed = usb / (result["filename"] + bk.ENCRYPTED_SUFFIX)
    assert landed.exists(), "nothing arrived on the stick: %s" % list(usb.iterdir())
    assert not (usb / result["filename"]).exists(), (
        "an unencrypted archive was written to the stick as well")
    assert b"SQLite format 3" not in landed.read_bytes(), (
        "what landed is still a readable database")


def test_offsite_failure_does_not_fail_the_local_backup(live, tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    monkeypatch.setenv("BACKUP_OFFSITE_DIR", str(blocker / "sub"))
    result = bk.run_backup()
    assert result["success"] is True                 # local copy still good
    assert result["offsite"][0]["ok"] is False
    assert result["offsite"][0]["error"]


def test_s3_upload_is_signed_and_uses_path_style(live, monkeypatch):
    # Set for the same reason as the folder test: an unkeyed off-site copy is
    # refused before it reaches the transport, so without this the signing
    # logic under test is never exercised at all.
    from cryptography.fernet import Fernet
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("BACKUP_S3_ENDPOINT", "https://s3.eu-central-003.backblazeb2.com")
    monkeypatch.setenv("BACKUP_S3_BUCKET", "clinic-backups")
    monkeypatch.setenv("BACKUP_S3_KEY", "AKIAEXAMPLE")
    monkeypatch.setenv("BACKUP_S3_SECRET", "shhh")
    monkeypatch.setenv("BACKUP_S3_REGION", "eu-central-003")

    calls = []

    class _Resp:
        status_code = 200
        text = ""

    monkeypatch.setattr("requests.put",
                        lambda url, **kw: calls.append((url, kw)) or _Resp())

    result = bk.run_backup()
    assert result["offsite"][0]["ok"] is True
    url, kw = calls[0]
    # .enc: what goes to the bucket is the sealed copy, not the archive. The
    # object key still carries the archive name so it can be matched back to a
    # local backup by eye.
    assert url.endswith(
        f"/clinic-backups/{result['filename']}{bk.ENCRYPTED_SUFFIX}")
    assert result["filename"] in url, (
        "the object name no longer identifies which backup it is")
    auth = kw["headers"]["Authorization"]
    assert auth.startswith("AWS4-HMAC-SHA256 Credential=AKIAEXAMPLE/")
    assert "eu-central-003/s3/aws4_request" in auth
    assert "SignedHeaders=host;x-amz-content-sha256;x-amz-date" in auth


def test_s3_half_configured_is_an_error_not_a_silent_skip(live, monkeypatch):
    monkeypatch.setenv("BACKUP_S3_BUCKET", "clinic-backups")   # no key/secret
    result = bk.run_backup()
    assert result["success"] is True
    assert result["offsite"][0]["ok"] is False
    assert "half-configured" in result["offsite"][0]["error"]


# ── Routes ────────────────────────────────────────────────────────────────────

def test_backup_page_shows_health(auth_client):
    resp = auth_client.get("/system/backup")
    assert resp.status_code == 200
    assert b"Last successful backup" in resp.data


def test_restore_requires_the_filename_typed_back(auth_client, app):
    import models.backup as _bk
    from tests.conftest import get_csrf
    with app.app_context():
        name = _bk.run_backup()["filename"]
    resp = auth_client.post(f"/system/backup/{name}/restore",
                            data={"confirm_filename": "not-it",
                                  "_csrf_token": get_csrf(auth_client)},
                            follow_redirects=True)
    assert resp.status_code == 200
    assert b"did not match" in resp.data


def test_maintenance_mode_holds_traffic_off(auth_client, app):
    import models.backup as _bk
    _bk.maintenance_on("unit test")
    try:
        assert auth_client.get("/crm/pets").status_code == 503
        # …but the backup page itself stays reachable, or you cannot recover.
        assert auth_client.get("/system/backup").status_code == 200
    finally:
        _bk.maintenance_off()
    assert auth_client.get("/crm/pets").status_code == 200
