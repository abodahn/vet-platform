"""
Backup, off-site copy, and restore — Aleefy Platform.

Engines
───────
SQLite      Everything goes through SQLite's own online backup API, in BOTH
            directions. Never shutil.copy2: gunicorn workers hold connections
            open and the database runs in WAL mode, so copying the file out
            from under them — or over them — yields a torn database.
PostgreSQL  pg_dump -Fc  /  pg_restore --clean --single-transaction.

Off-site (both optional, skipped cleanly when unset)
────────────────────────────────────────────────────
BACKUP_OFFSITE_DIR   a second filesystem path: USB drive, NAS, mounted share.
BACKUP_S3_*          any S3-compatible bucket (Backblaze B2, Hetzner, MinIO).
                     Signed with stdlib hmac over `requests` — no new package.

An off-site failure is loud (log + manager notification) but never fails the
local backup. One copy beats zero copies.

Health
──────
The last successful backup is not tracked in a table — the newest readable
archive on disk IS the record. State that can drift from the files it
describes is exactly how "nightly backup OK" was logged while no file existed.
"""
import hashlib
import hmac
import json
import logging
import os
import shutil
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse

logger = logging.getLogger(__name__)

_db_path: str = ""
_backup_dir: str = ""

RETENTION_DAYS = 30

ARCHIVE_EXTS = (".db", ".dump")
ARCHIVE_PREFIXES = ("platform_backup_", "pre_restore_", "uploaded_")

# Older than this and we treat the clinic as having no usable backup.
STALE_AFTER_DAYS = int(os.environ.get("BACKUP_STALE_DAYS", "2") or 2)

# Managers get told at most once per this many hours per alert title, so a
# broken backup does not bury the notification bell.
ALERT_COOLDOWN_HOURS = 24

# A maintenance marker older than this is assumed to be a crashed restore and
# is cleared automatically. A stuck marker would otherwise lock a clinic out of
# its own records, which is a worse outage than the one it guards against.
MAINTENANCE_MAX_MINUTES = 15

_MAINT_FILE = ".maintenance.json"
_ALERT_FILE = ".backup_alerts.json"


def configure(db_path: str, backup_dir: str) -> None:
    global _db_path, _backup_dir
    _db_path = db_path
    _backup_dir = backup_dir
    Path(backup_dir).mkdir(parents=True, exist_ok=True)


# Set only while backing up one specific clinic in a multi-tenant deployment.
# Empty means "use the deployment's own database", which is every single-clinic
# install and the behaviour this module had before tenants existed.
_tenant_dsn: str = ""


@contextmanager
def for_clinic(slug: str, db_path: str = "", pg_dsn: str = ""):
    """Point this module at one clinic's database for the duration of a block.

    Each clinic gets its OWN archive directory. Sharing one would be worse than
    untidy: retention purges by age across the whole directory, so the clinic
    that backs up most often would delete the archives of the ones that do not.

    Restores the previous target on the way out, including on exception — a
    failure mid-loop must not leave the next clinic, or the manual backup
    button, pointed at somebody else's database.
    """
    global _db_path, _backup_dir, _tenant_dsn
    prev = (_db_path, _backup_dir, _tenant_dsn)
    try:
        if slug:
            _backup_dir = str(Path(prev[1]) / slug)
            Path(_backup_dir).mkdir(parents=True, exist_ok=True)
            _db_path = db_path or ""
            _tenant_dsn = pg_dsn or ""
        yield
    finally:
        _db_path, _backup_dir, _tenant_dsn = prev


@contextmanager
def for_current_clinic():
    """Scope the READING functions to the clinic being served right now.

    for_clinic() is explicit on purpose — a restore or a retention purge must
    never silently retarget. But the reporting paths had the opposite problem:
    health(), list_backups() and get_latest_backup() read _backup_dir, which in
    a multi-tenant deployment is the DEPLOYMENT's directory, while the nightly
    job writes each clinic's archives into <backup_dir>/<slug>.

    So every one of them answered about a database no clinic owns. On the live
    demo that meant /healthz reported "backup stale, 60 hours" — permanently,
    and for a reason that had nothing to do with the clinic's data, whose
    backup was in fact four hours old. An alarm that is always on is worse than
    no alarm: it trains everyone to ignore the one time it is real.

    A single-clinic install has no slug, so this is a no-op there and behaviour
    is unchanged. Never raises: a health probe must not fail because the tenant
    registry is unreadable.
    """
    slug = ""
    tgt = {}
    try:
        from models import tenancy
        slug = tenancy.current() or ""
        if slug:
            tgt = tenancy.target(slug) or {}
    except Exception:                      # no registry, no app context, no tenant
        slug = ""
    if not slug:
        yield
        return
    with for_clinic(slug, tgt.get("db_path", ""), tgt.get("pg_dsn", "")):
        yield


def _postgres_dsn() -> str:
    """The DSN this backup should use, or '' when the target is SQLite.

    A per-clinic DSN wins over the deployment's: in a multi-tenant install the
    process-wide POSTGRES_DSN points at whichever database the app started
    with, and using it for every clinic would dump the same database N times
    under N different clinic names — the most dangerous possible outcome,
    because every archive would look present and correct.
    """
    if _tenant_dsn:
        return _tenant_dsn.strip()
    env = os.environ.get("POSTGRES_DSN", "").strip()
    if env:
        return env
    # Fall back to what the app is ACTUALLY connected to.
    #
    # Reading only the environment variable meant the backup chose its engine
    # from configuration that the running process may never have used. A
    # deployment that configures PostgreSQL through the app config rather than
    # POSTGRES_DSN -- which config.py fully supports -- got a backup that went
    # looking for a SQLite file, found nothing, and failed every night with
    # "source database is not there" while the clinic's real data sat in
    # PostgreSQL, unbacked-up.
    #
    # db._PG_CONFIG is set by configure_postgres() from whatever source won, so
    # it is the only honest answer to "which database is this process using".
    try:
        import models.database as _db
        cfg = getattr(_db, "_PG_CONFIG", None)
        if cfg:
            user = quote(str(cfg.get("user", "")), safe="")
            pwd  = quote(str(cfg.get("password", "")), safe="")
            auth = f"{user}:{pwd}@" if user else ""
            return (f"postgresql://{auth}{cfg.get('host','localhost')}:"
                    f"{cfg.get('port',5432)}/{cfg.get('dbname','')}")
    except Exception:
        logger.exception("could not derive a PostgreSQL DSN from the live connection")
    return ""


def _fail(msg: str) -> dict:
    return {"success": False, "error": msg, "filename": "",
            "timestamp": datetime.now().isoformat()}


def resolve_archive(filename: str) -> str:
    """Absolute path of an archive inside the backup dir, or '' if the name is
    not one we could have issued.

    The name arrives from a URL segment and is fed to download AND to restore,
    so this rejects rather than sanitises. Quietly rewriting
    `..\\..\\data\\platform.db` to `platform.db` would turn a traversal attempt
    into a plausible-looking restore of a *different* file — a silent wrong
    answer where the caller deserves a refusal.
    """
    if not _backup_dir or not filename:
        return ""
    name = str(filename).strip()
    if not name or name.startswith("."):
        return ""
    if name != os.path.basename(name.replace("\\", "/")):
        return ""                                   # contained / or \ or ..
    if os.path.splitext(name)[1] not in ARCHIVE_EXTS:
        return ""
    base = Path(_backup_dir).resolve()
    path = (base / name).resolve()
    if path.parent != base:
        return ""
    return str(path)


# ─────────────────────────────────────────────────────────────────
# Maintenance state
# ─────────────────────────────────────────────────────────────────

def maintenance_on(reason: str) -> None:
    """Mark the platform as unavailable. A FILE, not a global, so every
    gunicorn worker process sees it — an in-process flag would gate exactly
    one of N workers and leave the rest writing to a database being replaced.
    """
    with open(os.path.join(_backup_dir, _MAINT_FILE), "w", encoding="utf-8") as fh:
        json.dump({"started": datetime.now().isoformat(timespec="seconds"),
                   "reason": reason, "pid": os.getpid()}, fh)


def maintenance_off() -> None:
    try:
        os.remove(os.path.join(_backup_dir, _MAINT_FILE))
    except FileNotFoundError:
        pass
    except OSError as exc:
        logger.error("Could not clear maintenance marker: %s", exc)


def maintenance_active() -> dict | None:
    """The live maintenance marker, or None. Auto-clears an expired one."""
    if not _backup_dir:
        return None
    try:
        with open(os.path.join(_backup_dir, _MAINT_FILE), encoding="utf-8") as fh:
            info = json.load(fh)
    except (FileNotFoundError, NotADirectoryError):
        return None
    except (ValueError, OSError) as exc:
        logger.warning("Unreadable maintenance marker (%s) — clearing it", exc)
        maintenance_off()
        return None

    try:
        started = datetime.fromisoformat(str(info.get("started", "")))
    except ValueError:
        started = datetime.min
    if datetime.now() - started > timedelta(minutes=MAINTENANCE_MAX_MINUTES):
        logger.warning("Maintenance marker from %s is stale — clearing it",
                       info.get("started"))
        maintenance_off()
        return None
    info["age_minutes"] = round((datetime.now() - started).total_seconds() / 60, 1)
    return info


# ─────────────────────────────────────────────────────────────────
# Backup
# ─────────────────────────────────────────────────────────────────

def _sqlite_copy(src_path: str, dst_path: str) -> None:
    """Page-level copy through SQLite itself.

    Correct with live connections on either side: SQLite takes the locks, and
    readers of the destination see the change counter bump rather than a
    half-written file. If it cannot get the destination write lock within the
    busy timeout it raises — loudly failing beats quietly corrupting.
    """
    # sqlite3.connect() CREATES a database when the file is not there, and a
    # brand-new empty one passes integrity_check. Copying that onto the live
    # file erases the clinic and reports success, so the source is checked
    # here — the one place every caller (backup, snapshot, restore) goes
    # through — rather than in each of them.
    if not os.path.exists(src_path):
        raise FileNotFoundError(f"source database is not there: {src_path}")
    src = sqlite3.connect(src_path, timeout=30)
    dst = sqlite3.connect(dst_path, timeout=30)
    try:
        dst.execute("PRAGMA busy_timeout = 30000")
        with dst:
            src.backup(dst)
    finally:
        src.close()
        dst.close()


def _run_sqlite_backup(dest_path: str) -> dict:
    try:
        _sqlite_copy(_db_path, dest_path)
        size_kb = round(os.path.getsize(dest_path) / 1024, 1)
        check = _integrity_check(dest_path)
        if check != "ok":
            os.remove(dest_path)
            return _fail(f"Backup failed integrity check: {check}")
        logger.info("Backup completed: %s (%s KB), integrity=ok",
                    os.path.basename(dest_path), size_kb)
        return {"success": True, "filename": os.path.basename(dest_path),
                "filepath": dest_path, "size_kb": size_kb, "engine": "sqlite",
                "integrity": "ok", "timestamp": datetime.now().isoformat(),
                "error": None}
    except Exception as exc:
        logger.error("Backup failed: %s", exc)
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return _fail(str(exc))


def _run_pg_backup(dest_path: str) -> dict:
    """pg_dump the live PostgreSQL database.

    Previously absent entirely: run_backup() only ever spoke sqlite3, so a
    PostgreSQL deployment produced NO backup while the nightly job logged
    success. That is the worst possible failure — it looks healthy until the
    day you need to restore.
    """
    dsn = _postgres_dsn()
    exe = shutil.which("pg_dump")
    if not exe:
        # Do NOT report success. A missing tool means no backup exists.
        return _fail("pg_dump not found on PATH — PostgreSQL backup cannot run. "
                     "Install postgresql-client on the host.")
    try:
        # -Fc = custom format, compressed and restorable with pg_restore.
        proc = subprocess.run([exe, "--no-password", "-Fc", "-f", dest_path, dsn],
                              capture_output=True, text=True, timeout=1800)
        if proc.returncode != 0 or not os.path.exists(dest_path):
            err = (proc.stderr or "").strip()[:500] or f"pg_dump exited {proc.returncode}"
            if os.path.exists(dest_path):
                os.remove(dest_path)
            logger.error("PostgreSQL backup failed: %s", err)
            return _fail(err)

        size_kb = round(os.path.getsize(dest_path) / 1024, 1)
        if size_kb <= 0:
            os.remove(dest_path)
            return _fail("pg_dump produced an empty file")

        logger.info("PostgreSQL backup completed: %s (%s KB)",
                    os.path.basename(dest_path), size_kb)
        return {"success": True, "filename": os.path.basename(dest_path),
                "filepath": dest_path, "size_kb": size_kb, "engine": "postgresql",
                "integrity": "ok", "timestamp": datetime.now().isoformat(),
                "error": None}
    except subprocess.TimeoutExpired:
        logger.error("pg_dump timed out after 30 minutes")
        return _fail("pg_dump timed out after 30 minutes")


def _create_archive(prefix: str) -> dict:
    """Dump the live database to a new timestamped file. No off-site, no alert.

    Separate from run_backup() because restore_backup() needs a snapshot while
    maintenance mode is already on, which run_backup() correctly refuses.
    """
    if not _backup_dir:
        return _fail("Backup not configured")
    is_pg = bool(_postgres_dsn())
    if not is_pg and not _db_path:
        return _fail("Backup not configured")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = ".dump" if is_pg else ".db"
    dest = os.path.join(_backup_dir, f"{prefix}{ts}{ext}")
    # Two backups inside the same second must not share a name: the pre-restore
    # snapshot would otherwise overwrite the very archive being restored, and
    # the restore would silently put back the data it was supposed to replace.
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(_backup_dir, f"{prefix}{ts}_{n}{ext}")
        n += 1
    return _run_pg_backup(dest) if is_pg else _run_sqlite_backup(dest)


def run_backup(db_path: str = "") -> dict:
    """Create a timestamped backup of the database this deployment uses.

    `db_path` is accepted and ignored — blueprints/migration passed one
    positional argument against a zero-arg signature, so every destructive
    Excel import raised TypeError and ran with NO backup, the error swallowed
    into the results page.

    Returns a status dict with success, filename, size_kb, error, offsite.
    """
    if maintenance_active():
        return _fail("A restore is in progress — backup skipped")

    result = _create_archive("platform_backup_")

    if result["success"]:
        # Retention runs HERE and nowhere else. It used to run inside
        # _run_sqlite_backup, which restore_backup() also reaches through its
        # pre-restore snapshot: restoring an archive older than RETENTION_DAYS
        # purged that archive mid-restore, and the copy that followed put an
        # empty database over the live one and called it a success.
        _purge_dir(_backup_dir)
        result["offsite"] = copy_offsite(result["filepath"])
    else:
        # Every caller — scheduler, manual button, Excel import — routes through
        # here, so one alert covers all of them.
        _alert("Backup FAILED", result.get("error") or "Unknown error")
    return result


def _purge_dir(directory: str) -> int:
    """Delete our own archives older than RETENTION_DAYS. Returns count."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted = 0
    try:
        for f in Path(directory).iterdir():
            if f.suffix not in ARCHIVE_EXTS or not f.name.startswith(ARCHIVE_PREFIXES):
                continue
            stamp = _stamp_of(f.name)
            if stamp and stamp < cutoff:
                try:
                    f.unlink()
                    deleted += 1
                except OSError as exc:
                    logger.warning("Could not delete old backup %s: %s", f.name, exc)
    except OSError as exc:
        logger.warning("Purge error in %s: %s", directory, exc)
    return deleted


def _stamp_of(name: str) -> datetime | None:
    """Creation time encoded in the filename, or None if it isn't."""
    stem = os.path.splitext(name)[0]
    for p in ARCHIVE_PREFIXES:
        if stem.startswith(p):
            try:
                return datetime.strptime(stem[len(p):][:15], "%Y%m%d_%H%M%S")
            except ValueError:
                return None
    return None


def list_backups() -> list[dict]:
    """Every archive in the backup dir with metadata, newest first."""
    if not _backup_dir:
        return []
    out = []
    try:
        entries = list(Path(_backup_dir).iterdir())
    except OSError:
        return []
    now = datetime.now()
    for f in entries:
        if f.suffix not in ARCHIVE_EXTS or not f.name.startswith(ARCHIVE_PREFIXES):
            continue
        try:
            st = f.stat()
        except OSError:
            continue
        dt = _stamp_of(f.name) or datetime.fromtimestamp(st.st_mtime)
        age = now - dt
        out.append({
            "filename": f.name,
            "filepath": str(f),
            "size_kb": round(st.st_size / 1024, 1),
            "size_mb": round(st.st_size / (1024 * 1024), 2),
            "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "age_days": age.days,
            "age_hours": round(age.total_seconds() / 3600, 1),
            "kind": ("pre-restore" if f.name.startswith("pre_restore_")
                     else "uploaded" if f.name.startswith("uploaded_")
                     else "backup"),
            "engine": "postgresql" if f.suffix == ".dump" else "sqlite",
        })
    out.sort(key=lambda b: b["timestamp"], reverse=True)
    return out


def get_latest_backup() -> dict | None:
    backups = list_backups()
    return backups[0] if backups else None


# ─────────────────────────────────────────────────────────────────
# Verification — never restore something you have not read
# ─────────────────────────────────────────────────────────────────

def _integrity_check(path: str) -> str:
    """'ok', or a plain-language reason the file is not a usable database.

    The magic-header and table-count checks are not decoration: sqlite3 happily
    opens a zero-byte file as a brand-new empty database and reports
    integrity_check = 'ok'. Restoring that would erase the clinic and call it
    a success.
    """
    try:
        if os.path.getsize(path) < 512:
            return "file is empty or truncated"
        with open(path, "rb") as fh:
            if fh.read(16) != b"SQLite format 3\x00":
                return "not a SQLite database file"
        conn = sqlite3.connect(path)
        try:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if result != "ok":
                return result
            tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            if tables < 1:
                return "database has no tables — nothing to restore"
        finally:
            conn.close()
        return "ok"
    except Exception as exc:
        return str(exc)


def _pg_verify(path: str) -> dict:
    exe = shutil.which("pg_restore")
    if not exe:
        return {"success": False,
                "integrity": "pg_restore not installed — cannot verify this dump"}
    try:
        proc = subprocess.run([exe, "--list", path],
                              capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        return {"success": False, "integrity": "pg_restore --list timed out"}
    if proc.returncode != 0:
        return {"success": False,
                "integrity": (proc.stderr or "").strip()[:200] or "unreadable dump"}
    if "TABLE DATA" not in proc.stdout:
        return {"success": False, "integrity": "dump contains no table data"}
    return {"success": True, "integrity": "ok"}


def verify_backup(filename: str) -> dict:
    """Check an archive is readable and complete, without restoring it."""
    path = resolve_archive(filename)
    if not path or not os.path.exists(path):
        return {"success": False, "integrity": "missing", "error": "File not found"}
    if path.endswith(".dump"):
        return _pg_verify(path)
    result = _integrity_check(path)
    return {"success": result == "ok", "integrity": result,
            "error": None if result == "ok" else result}


# ─────────────────────────────────────────────────────────────────
# Restore
# ─────────────────────────────────────────────────────────────────

def _pg_restore(archive: str) -> None:
    exe = shutil.which("pg_restore")
    if not exe:
        raise RuntimeError("pg_restore not found on PATH — install postgresql-client.")
    proc = subprocess.run(
        [exe, "--no-password", "--clean", "--if-exists", "--no-owner",
         "--single-transaction", "-d", _postgres_dsn(), archive],
        capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "").strip()[:500]
                           or f"pg_restore exited {proc.returncode}")


def restore_backup(filename: str) -> dict:
    """Replace the live database with a named archive.

    The order is the whole point:
      1. verify the archive          — refuse anything unreadable
      2. maintenance mode ON         — stop new requests reaching the database
      3. snapshot the live database  — restoring the wrong file stays undoable
      4. restore
      5. maintenance mode OFF

    Step 3 is mandatory. If the snapshot fails, nothing is overwritten.

    Returns {success, skipped, message, snapshot}.
    """
    if not _backup_dir:
        return {"success": False, "skipped": False,
                "message": "Backup is not configured on this server."}

    archive = resolve_archive(filename)
    if not archive or not os.path.exists(archive):
        return {"success": False, "skipped": False,
                "message": f"Backup file not found: {filename}"}

    is_pg = bool(_postgres_dsn())
    if is_pg != archive.endswith(".dump"):
        return {"success": False, "skipped": False,
                "message": ("That backup came from a different database engine than "
                            "this server runs. Restore aborted — nothing was changed.")}
    if not is_pg and not _db_path:
        return {"success": False, "skipped": False,
                "message": "Database path is not configured on this server."}

    check = verify_backup(os.path.basename(archive))
    if not check["success"]:
        return {"success": False, "skipped": False,
                "message": (f"That file is not a usable backup "
                            f"({check.get('integrity')}). Restore aborted — "
                            f"nothing was changed.")}

    if maintenance_active():
        return {"success": False, "skipped": False,
                "message": "Another restore is already running. Wait for it to finish."}

    maintenance_on(f"Restoring {os.path.basename(archive)}")
    try:
        snapshot = _create_archive("pre_restore_")
        if not snapshot["success"]:
            return {"success": False, "skipped": False,
                    "message": ("Could not snapshot the current database "
                                f"({snapshot.get('error')}). Restore aborted — "
                                "nothing was changed.")}

        if is_pg:
            _pg_restore(archive)
        else:
            _sqlite_copy(archive, _db_path)

        logger.warning("RESTORE completed from %s (previous data saved as %s)",
                       os.path.basename(archive), snapshot["filename"])
        return {
            "success": True, "skipped": False,
            "snapshot": snapshot["filename"],
            "message": (f"Database restored from {os.path.basename(archive)}. "
                        f"Your previous data was saved as {snapshot['filename']} — "
                        f"restore that file to undo this."),
        }
    except Exception as exc:
        logger.error("Restore failed: %s", exc, exc_info=True)
        _alert("Database restore FAILED", f"{os.path.basename(archive)}: {exc}")
        return {"success": False, "skipped": False,
                "message": f"Restore failed: {exc}"}
    finally:
        maintenance_off()


def accept_upload(fileobj, filename: str) -> dict:
    """Store an archive uploaded from a USB stick and verify it.

    Verified here rather than at restore time so the owner finds out the stick
    is bad while they still have it plugged in.
    """
    if not _backup_dir:
        return {"success": False, "message": "Backup is not configured on this server."}
    # Only the EXTENSION is taken from the submitted name — the destination
    # name is generated here, so a hostile filename has nothing to steer.
    base = os.path.basename(str(filename).replace("\\", "/")).strip()
    if not base.endswith(ARCHIVE_EXTS):
        return {"success": False,
                "message": "Only .db (SQLite) or .dump (PostgreSQL) backup files "
                           "can be uploaded."}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = os.path.splitext(base)[1]
    # Same-second uploads must not share a name, for the same reason
    # _create_archive() disambiguates: a second upload would overwrite the
    # first, and if the second fails verification the os.remove() below would
    # delete the archive that was already there and already good.
    name, n = f"uploaded_{ts}{ext}", 1
    while os.path.exists(os.path.join(_backup_dir, name)):
        name = f"uploaded_{ts}_{n}{ext}"
        n += 1
    dest = resolve_archive(name)
    if not dest:
        return {"success": False, "message": "Could not store the uploaded file."}
    fileobj.save(dest)

    check = verify_backup(os.path.basename(dest))
    if not check["success"]:
        os.remove(dest)
        return {"success": False,
                "message": (f"That file is not a usable backup "
                            f"({check.get('integrity')}). It was not kept.")}
    return {"success": True, "filename": os.path.basename(dest),
            "message": f"Uploaded and verified: {os.path.basename(dest)}"}


# ─────────────────────────────────────────────────────────────────
# Off-site copies
# ─────────────────────────────────────────────────────────────────

def offsite_targets() -> list[dict]:
    """Configured off-site targets. Empty list means none — which is itself
    worth showing on the page: backups next to the database are not a backup.
    """
    out = []
    folder = os.environ.get("BACKUP_OFFSITE_DIR", "").strip()
    if folder:
        out.append({"kind": "folder", "label": folder})
    bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
    if bucket:
        endpoint = os.environ.get("BACKUP_S3_ENDPOINT", "").strip().rstrip("/")
        out.append({"kind": "s3", "label": f"{endpoint}/{bucket}"})
    return out


def copy_offsite(path: str) -> list[dict]:
    """Copy one archive to every configured off-site target.

    Never raises. An off-site failure must not turn a good local backup into a
    reported failure — but it is logged at ERROR and notified, because a
    silently missing off-site copy is the failure mode this exists to prevent.
    """
    results = []
    for target in offsite_targets():
        try:
            if target["kind"] == "folder":
                _copy_to_folder(path, target["label"])
            else:
                _s3_put(path)
            logger.info("Off-site copy OK (%s): %s", target["kind"],
                        os.path.basename(path))
            results.append({**target, "ok": True, "error": ""})
        except Exception as exc:
            logger.error("OFF-SITE COPY FAILED (%s -> %s): %s",
                         os.path.basename(path), target["label"], exc)
            results.append({**target, "ok": False, "error": str(exc)[:300]})
            _alert("Off-site backup copy failed",
                   f"{target['label']}: {exc}"[:400])
    return results


def _copy_to_folder(path: str, folder: str) -> None:
    Path(folder).mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, os.path.join(folder, os.path.basename(path)))
    _purge_dir(folder)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _s3_sign(method: str, uri: str, host: str, region: str,
             access: str, secret: str, payload_hash: str, now: datetime) -> dict:
    """AWS SigV4 headers for a single unsigned-payload-free request.

    Hand-rolled over stdlib hmac deliberately: boto3 pulls in botocore for what
    is thirty lines of HMAC, and the brief asked not to add a package silently.
    """
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    day = now.strftime("%Y%m%d")
    headers = {"host": host, "x-amz-content-sha256": payload_hash, "x-amz-date": stamp}
    signed = ";".join(sorted(headers))
    canonical = "\n".join([
        method, uri, "",
        *[f"{k}:{headers[k]}" for k in sorted(headers)], "",
        signed, payload_hash,
    ])
    scope = f"{day}/{region}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", stamp, scope,
                         hashlib.sha256(canonical.encode()).hexdigest()])
    key = f"AWS4{secret}".encode()
    for part in (day, region, "s3", "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={access}/{scope}, "
                                f"SignedHeaders={signed}, Signature={sig}")
    return headers


def _s3_put(path: str) -> None:
    import requests  # already a dependency (WhatsApp / webhooks)

    endpoint = os.environ.get("BACKUP_S3_ENDPOINT", "").strip().rstrip("/")
    bucket = os.environ.get("BACKUP_S3_BUCKET", "").strip()
    access = os.environ.get("BACKUP_S3_KEY", "").strip()
    secret = os.environ.get("BACKUP_S3_SECRET", "").strip()
    region = os.environ.get("BACKUP_S3_REGION", "").strip() or "us-east-1"
    prefix = os.environ.get("BACKUP_S3_PREFIX", "").strip().strip("/")
    if not (endpoint and bucket and access and secret):
        raise RuntimeError("S3 off-site is half-configured — need BACKUP_S3_ENDPOINT, "
                           "BACKUP_S3_BUCKET, BACKUP_S3_KEY and BACKUP_S3_SECRET")
    if "://" not in endpoint:
        endpoint = "https://" + endpoint

    name = os.path.basename(path)
    key = f"{prefix}/{name}" if prefix else name
    # Path-style addressing: the widest compatibility across B2, Hetzner, MinIO.
    uri = quote(f"/{bucket}/{key}", safe="/")
    headers = _s3_sign("PUT", uri, urlparse(endpoint).netloc, region,
                       access, secret, _sha256_file(path),
                       datetime.now(timezone.utc))

    # ponytail: single PUT, so 5 GB per archive is the ceiling and the file is
    # hashed twice (once to sign, once by the server). Multipart upload — or
    # boto3 — only when a clinic database actually approaches that size.
    with open(path, "rb") as body:
        resp = requests.put(f"{endpoint}{uri}", data=body, headers=headers, timeout=600)
    if resp.status_code >= 300:
        raise RuntimeError(f"S3 PUT returned {resp.status_code}: {resp.text[:200]}")


# ─────────────────────────────────────────────────────────────────
# Health & alerting
# ─────────────────────────────────────────────────────────────────

def health() -> dict:
    """Is there a recent backup? The single question the backup page exists
    to answer, and the one nobody was being asked.
    """
    base = {"stale_after_days": STALE_AFTER_DAYS,
            "offsite": offsite_targets(),
            "engine": "postgresql" if _postgres_dsn() else "sqlite"}
    latest = get_latest_backup()
    if not latest:
        return {**base, "ok": False, "has_backup": False, "latest": None,
                "age_hours": None, "age_days": None, "stale": True,
                "message": "No backup has ever been taken on this server."}
    stale = latest["age_hours"] > STALE_AFTER_DAYS * 24
    return {**base, "ok": not stale, "has_backup": True, "latest": latest,
            "age_hours": latest["age_hours"], "age_days": latest["age_days"],
            "stale": stale,
            "message": (f"Last backup is {latest['age_days']} day(s) old — backups "
                        f"have probably stopped." if stale else
                        f"Last backup {latest['age_hours']} hour(s) ago.")}


def _recent_alert(title: str) -> bool:
    """True if this alert already went out inside the cooldown window."""
    try:
        with open(os.path.join(_backup_dir, _ALERT_FILE), encoding="utf-8") as fh:
            sent = json.load(fh)
        last = datetime.fromisoformat(sent[title])
    except (FileNotFoundError, NotADirectoryError, KeyError, ValueError, OSError):
        return False
    return datetime.now() - last < timedelta(hours=ALERT_COOLDOWN_HOURS)


def _record_alert(title: str) -> None:
    path = os.path.join(_backup_dir, _ALERT_FILE)
    try:
        with open(path, encoding="utf-8") as fh:
            sent = json.load(fh)
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError):
        sent = {}
    sent[title] = datetime.now().isoformat(timespec="seconds")
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(sent, fh)
    except OSError as exc:
        logger.warning("Could not record backup alert timestamp: %s", exc)


def _alert(title: str, body: str) -> None:
    """Tell the managers. Logged at ERROR either way, so the log stays a
    second channel when the notification table is itself the casualty.
    """
    logger.error("BACKUP ALERT — %s: %s", title, body)
    if not _backup_dir or _recent_alert(title):
        return
    try:
        import models.database as db
        db.notify_managers(title=title, body=body, icon="❌",
                           link="/system/backup", module="system")
        _record_alert(title)
    except Exception as exc:
        # Never let a failed notification take the backup down with it — but
        # never swallow it silently either.
        logger.error("Could not deliver backup alert to managers: %s", exc)


def check_and_notify() -> dict:
    """Compute backup health and alert managers when it is bad.

    Covers the case the failure path cannot: a backup that never ran at all.
    A scheduler that died leaves no failure to report, so this must be driven
    by something that still runs — a page view, or a separate daily job.
    """
    h = health()
    if h["stale"]:
        _alert("No backup exists" if not h["has_backup"] else "Backup is out of date",
               h["message"] + " Open System → Backup and run one now.")
    return h
