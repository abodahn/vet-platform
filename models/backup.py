"""
Automated SQLite Backup System — Aleefy Platform
Daily timestamped backups, 30-day retention, integrity check, status tracking.
"""
import os
import shutil
import sqlite3
import threading
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_db_path: str = ""
_backup_dir: str = ""

RETENTION_DAYS = 30


def configure(db_path: str, backup_dir: str) -> None:
    global _db_path, _backup_dir
    _db_path = db_path
    _backup_dir = backup_dir
    Path(backup_dir).mkdir(parents=True, exist_ok=True)


def run_backup() -> dict:
    """
    Create a timestamped backup of the SQLite database.
    Returns a status dict with success, filename, size_kb, error.
    """
    if not _db_path or not _backup_dir:
        return {"success": False, "error": "Backup not configured", "filename": ""}

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"platform_backup_{ts}.db"
    backup_path = os.path.join(_backup_dir, backup_name)

    try:
        # Use SQLite's online backup API for consistency
        src = sqlite3.connect(_db_path)
        dst = sqlite3.connect(backup_path)
        with dst:
            src.backup(dst)
        src.close()
        dst.close()

        size_kb = round(os.path.getsize(backup_path) / 1024, 1)

        # Integrity check on the backup
        check = _integrity_check(backup_path)

        _purge_old_backups()

        status = {
            "success": check == "ok",
            "filename": backup_name,
            "filepath": backup_path,
            "size_kb": size_kb,
            "integrity": check,
            "timestamp": datetime.now().isoformat(),
            "error": None if check == "ok" else f"Integrity check failed: {check}",
        }
        logger.info(f"Backup completed: {backup_name} ({size_kb} KB), integrity={check}")
        return status

    except Exception as exc:
        logger.error(f"Backup failed: {exc}")
        if os.path.exists(backup_path):
            os.remove(backup_path)
        return {"success": False, "error": str(exc), "filename": "", "timestamp": datetime.now().isoformat()}


def _integrity_check(db_path: str) -> str:
    try:
        conn = sqlite3.connect(db_path)
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        return result  # "ok" on success
    except Exception as e:
        return str(e)


def _purge_old_backups() -> int:
    """Delete backups older than RETENTION_DAYS. Returns number deleted."""
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    deleted = 0
    try:
        for f in Path(_backup_dir).glob("platform_backup_*.db"):
            try:
                ts_str = f.stem.replace("platform_backup_", "")
                file_dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                if file_dt < cutoff:
                    f.unlink()
                    deleted += 1
            except (ValueError, OSError):
                pass
    except Exception as e:
        logger.warning(f"Purge error: {e}")
    return deleted


def list_backups() -> list[dict]:
    """Return list of backup files with metadata, newest first."""
    if not _backup_dir:
        return []
    backups = []
    try:
        for f in sorted(Path(_backup_dir).glob("platform_backup_*.db"), reverse=True):
            try:
                ts_str = f.stem.replace("platform_backup_", "")
                file_dt = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
                size_kb = round(f.stat().st_size / 1024, 1)
                backups.append({
                    "filename": f.name,
                    "filepath": str(f),
                    "size_kb": size_kb,
                    "timestamp": file_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "age_days": (datetime.now() - file_dt).days,
                })
            except (ValueError, OSError):
                pass
    except Exception:
        pass
    return backups


def get_latest_backup() -> dict | None:
    backups = list_backups()
    return backups[0] if backups else None


def verify_backup(filename: str) -> dict:
    """Run integrity check on a specific backup file."""
    path = os.path.join(_backup_dir, filename)
    if not os.path.exists(path):
        return {"success": False, "error": "File not found"}
    result = _integrity_check(path)
    return {"success": result == "ok", "integrity": result}


def restore_backup(filename: str) -> dict:
    """Restore a SQLite backup file over the live database.

    Returns a dict with:
        success   bool
        message   str   (human-readable result or error)
        skipped   bool  (True when running PostgreSQL — restore not applicable)

    IMPORTANT: This replaces the live SQLite file.  Not applicable when
    the platform is running PostgreSQL — in that case `skipped` is True
    and a safe informational message is returned.
    """
    import models.database as _db_mod

    # Detect PostgreSQL mode — if PG config is set, skip
    if getattr(_db_mod, "_PG_CONFIG", {}):
        return {
            "success": False,
            "skipped": True,
            "message": (
                "Restore is only supported for SQLite databases. "
                "Your platform is running PostgreSQL. "
                "To restore, use pg_restore or your hosting provider's backup tools."
            ),
        }

    if not _db_path:
        return {"success": False, "skipped": False, "message": "Database path not configured."}

    backup_path = os.path.join(_backup_dir, filename)
    if not os.path.exists(backup_path):
        return {"success": False, "skipped": False, "message": f"Backup file not found: {filename}"}

    # Safety: integrity check on backup before overwriting live DB
    integrity = _integrity_check(backup_path)
    if integrity != "ok":
        return {
            "success": False,
            "skipped": False,
            "message": f"Backup failed integrity check ({integrity}). Restore aborted for safety.",
        }

    try:
        # Create a safety snapshot of current live DB first
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        pre_restore_name = f"pre_restore_{ts}.db"
        pre_restore_path = os.path.join(_backup_dir, pre_restore_name)
        shutil.copy2(_db_path, pre_restore_path)

        # Restore: copy backup → live DB path
        shutil.copy2(backup_path, _db_path)

        logger.info(f"Restore completed from {filename} (pre-restore saved as {pre_restore_name})")
        return {
            "success": True,
            "skipped": False,
            "message": (
                f"Database restored from {filename}. "
                f"Your previous data was saved as {pre_restore_name}."
            ),
        }
    except Exception as exc:
        logger.error(f"Restore failed: {exc}")
        return {"success": False, "skipped": False, "message": f"Restore failed: {exc}"}
