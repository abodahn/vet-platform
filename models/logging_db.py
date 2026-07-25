"""
Production Logging System
─────────────────────────
Dual-channel logging: rotating daily log files + PostgreSQL tables.

Channels:
  1. File  — logs/backend/backend-YYYY-MM-DD.log  (7-day retention)
  2. DB    — backend_logs / frontend_logs tables

Usage:
    from models.logging_db import log_backend, log_frontend, cleanup_old_logs

    log_backend(level="ERROR", module="finance", action="export_xlsx",
                http_method="GET", endpoint="/finance/export",
                status_code=500, duration_ms=120,
                error_message=str(e), stack_trace=traceback.format_exc())
"""

import os
import json
import uuid
import logging
import traceback
import threading
from datetime import datetime, timedelta
from pathlib import Path

import models.database as db

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────
_BASE_DIR     = Path(__file__).parent.parent
_LOG_DIR_BACK = _BASE_DIR / "logs" / "backend"
_LOG_DIR_FRONT= _BASE_DIR / "logs" / "frontend"
_RETENTION    = int(os.environ.get("LOG_FILE_RETENTION_DAYS", "7"))
_WRITE_LOCK   = threading.Lock()

_LOG_DIR_BACK.mkdir(parents=True, exist_ok=True)
_LOG_DIR_FRONT.mkdir(parents=True, exist_ok=True)


# ════════════════════════════════════════════════════════════════
# FILE LOGGING
# ════════════════════════════════════════════════════════════════

def _today_log_path(channel: str = "backend") -> Path:
    day = datetime.utcnow().strftime("%Y-%m-%d")
    base = _LOG_DIR_BACK if channel == "backend" else _LOG_DIR_FRONT
    return base / f"{channel}-{day}.log"


def _write_file_log(channel: str, record: dict) -> None:
    """Append one JSON line to today's log file (thread-safe)."""
    path = _today_log_path(channel)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with _WRITE_LOCK:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def cleanup_old_logs() -> int:
    """Delete log files older than LOG_FILE_RETENTION_DAYS. Returns count deleted."""
    cutoff = datetime.utcnow() - timedelta(days=_RETENTION)
    deleted = 0
    for directory in (_LOG_DIR_BACK, _LOG_DIR_FRONT):
        for log_file in directory.glob("*.log"):
            try:
                # Parse date from filename  backend-2026-01-15.log
                stem = log_file.stem  # e.g.  backend-2026-01-15
                parts = stem.rsplit("-", 3)
                if len(parts) >= 4:
                    file_date = datetime.strptime(
                        f"{parts[-3]}-{parts[-2]}-{parts[-1]}", "%Y-%m-%d"
                    )
                    if file_date < cutoff:
                        log_file.unlink()
                        deleted += 1
                        logger.info("Deleted old log file: %s", log_file.name)
            except Exception:
                pass
    return deleted


# ════════════════════════════════════════════════════════════════
# BACKEND LOGGING
# ════════════════════════════════════════════════════════════════

def log_backend(
    level:                   str = "INFO",
    module_name:             str = "",
    action_name:             str = "",
    http_method:             str = "",
    endpoint:                str = "",
    status_code:             int = 0,
    duration_ms:             int = 0,
    ip_address:              str = "",
    user_agent:              str = "",
    user_id:                 int = None,
    username:                str = "",
    request_payload_summary: str = "",
    response_payload_summary:str = "",
    error_message:           str = "",
    stack_trace:             str = "",
    correlation_id:          str = "",
    request_id:              str = "",
    metadata:                dict = None,
) -> None:
    correlation_id = correlation_id or str(uuid.uuid4())
    request_id     = request_id     or str(uuid.uuid4())
    ts             = datetime.utcnow().isoformat(timespec="milliseconds")

    record = {
        "ts": ts, "level": level, "correlation_id": correlation_id,
        "request_id": request_id, "user_id": user_id, "username": username,
        "module": module_name, "action": action_name,
        "method": http_method, "endpoint": endpoint,
        "status_code": status_code, "duration_ms": duration_ms,
        "ip": ip_address, "error": error_message,
    }

    # 1. File log
    try:
        _write_file_log("backend", record)
    except Exception:
        pass

    # 2. DB log (non-blocking best-effort)
    try:
        conn = db.get_db()
        conn.execute(
            """INSERT INTO backend_logs
               (correlation_id, request_id, user_id, username, level,
                module_name, action_name, http_method, endpoint,
                status_code, duration_ms, ip_address, user_agent,
                request_payload_summary, response_payload_summary,
                error_message, stack_trace, metadata, created_at)
               VALUES (?,?,?,?,?, ?,?,?,?, ?,?,?,?, ?,?, ?,?,?,?)""",
            (
                correlation_id, request_id, user_id, username, level,
                module_name, action_name, http_method, endpoint,
                status_code, duration_ms, ip_address, user_agent,
                request_payload_summary[:500] if request_payload_summary else "",
                response_payload_summary[:500] if response_payload_summary else "",
                error_message[:2000] if error_message else "",
                stack_trace[:5000] if stack_trace else "",
                json.dumps(metadata or {}),
                ts,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("backend_logs DB write failed: %s", e)


# ════════════════════════════════════════════════════════════════
# FRONTEND LOGGING  (receives from browser via /api/v1/logs/frontend)
# ════════════════════════════════════════════════════════════════

def log_frontend(payload: dict) -> None:
    ts = datetime.utcnow().isoformat(timespec="milliseconds")

    record = {
        "ts": ts,
        "correlation_id": payload.get("correlation_id", str(uuid.uuid4())),
        "session_id":     payload.get("session_id", ""),
        "user_id":        payload.get("user_id"),
        "username":       payload.get("username", ""),
        "level":          payload.get("level", "INFO"),
        "page_url":       payload.get("page_url", ""),
        "route_name":     payload.get("route_name", ""),
        "event_name":     payload.get("event_name", ""),
        "message":        payload.get("message", ""),
        "network_status": payload.get("network_status", "online"),
        "api_endpoint":   payload.get("api_endpoint", ""),
        "api_status_code":payload.get("api_status_code"),
        "error_stack":    payload.get("error_stack", ""),
        "browser_name":   payload.get("browser_name", ""),
        "device_type":    payload.get("device_type", ""),
    }

    # File log
    try:
        _write_file_log("frontend", record)
    except Exception:
        pass

    # DB
    try:
        conn = db.get_db()
        conn.execute(
            """INSERT INTO frontend_logs
               (correlation_id, session_id, user_id, username, level,
                page_url, route_name, component_name, event_name, message,
                browser_name, browser_version, device_type, os_name,
                network_status, api_endpoint, api_status_code,
                error_stack, metadata, created_at)
               VALUES (?,?,?,?,?, ?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?)""",
            (
                record["correlation_id"], record["session_id"],
                record["user_id"], record["username"], record["level"],
                record["page_url"][:500], record["route_name"],
                payload.get("component_name", ""), record["event_name"],
                record["message"][:2000],
                record["browser_name"], payload.get("browser_version", ""),
                record["device_type"], payload.get("os_name", ""),
                record["network_status"],
                record["api_endpoint"], record["api_status_code"],
                record["error_stack"][:5000],
                json.dumps(payload.get("metadata", {})),
                ts,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("frontend_logs DB write failed: %s", e)


# ════════════════════════════════════════════════════════════════
# AUDIT LOGGING
# ════════════════════════════════════════════════════════════════

def log_audit(
    user_id:     int  = None,
    username:    str  = "",
    action_type: str  = "VIEW",
    entity_name: str  = "",
    entity_id:   str  = "",
    old_value:   dict = None,
    new_value:   dict = None,
    ip_address:  str  = "",
    user_agent:  str  = "",
    correlation_id: str = "",
) -> None:
    ts             = datetime.utcnow().isoformat(timespec="milliseconds")
    correlation_id = correlation_id or str(uuid.uuid4())

    try:
        conn = db.get_db()
        conn.execute(
            """INSERT INTO audit_logs
               (correlation_id, user_id, username, action_type,
                entity_name, entity_id, old_value, new_value,
                ip_address, user_agent, created_at)
               VALUES (?,?,?,?, ?,?,?,?, ?,?,?)""",
            (
                correlation_id, user_id, username, action_type,
                entity_name, str(entity_id),
                json.dumps(old_value) if old_value else None,
                json.dumps(new_value) if new_value else None,
                ip_address, user_agent, ts,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("audit_logs DB write failed: %s", e)
