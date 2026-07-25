"""
/api/v1  —  Production REST API
─────────────────────────────────
Versioned REST layer with standardized response envelope:

  {
    "success": true/false,
    "data":    {...},
    "error":   null | "message",
    "meta": {
      "version": "1.0",
      "request_id": "uuid",
      "timestamp": "ISO8601"
    }
  }

Endpoints:
  GET  /api/v1/health                  — public health check
  GET  /api/v1/system/diagnostics      — admin only system diagnostics
  POST /api/v1/logs/frontend           — browser sends frontend error logs
  POST /api/v1/sync/push               — device pushes offline queue
  GET  /api/v1/sync/status             — sync queue summary
  GET  /api/v1/sync/conflicts          — list unresolved conflicts
  POST /api/v1/sync/conflicts/:id/resolve — resolve a conflict
  GET  /api/v1/sync/devices            — registered devices
"""

import uuid
import time
import json
import platform
import traceback
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, request, jsonify, session, g

import models.database as db
from models.logging_db import log_backend, log_frontend, log_audit, cleanup_old_logs
from models.sync import (
    enqueue, get_pending, mark_synced, mark_failed, mark_conflict,
    resolve_conflict, get_sync_status_summary, register_device, touch_device_online
)

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

APP_VERSION = os.environ.get("APP_VERSION", "1.0.0")
BUILD_NUMBER = os.environ.get("BUILD_NUMBER", "production_final_v1")


# ── Response helpers ──────────────────────────────────────────

def ok(data=None, status=200, meta=None):
    rid = getattr(g, "request_id", str(uuid.uuid4()))
    body = {
        "success": True,
        "data": data,
        "error": None,
        "meta": {
            "version": "1.0",
            "request_id": rid,
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            **(meta or {}),
        },
    }
    return jsonify(body), status


def err(message, status=400, code=None):
    rid = getattr(g, "request_id", str(uuid.uuid4()))
    body = {
        "success": False,
        "data": None,
        "error": message,
        "code": code,
        "meta": {
            "version": "1.0",
            "request_id": rid,
            "timestamp": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        },
    }
    return jsonify(body), status


# ── Decorators ────────────────────────────────────────────────

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return err("Authentication required", 401, "UNAUTHENTICATED")
        return f(*args, **kwargs)
    return wrapper


def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        role = session.get("role", "")
        if role not in ("super_admin", "clinic_owner", "support_admin"):
            log_backend(
                level="WARNING", module_name="api_v1", action_name="admin_blocked",
                http_method=request.method, endpoint=request.path, status_code=403,
                ip_address=request.remote_addr, user_id=session.get("user_id"),
                username=session.get("username", ""), error_message="Insufficient role"
            )
            return err("Admin access required", 403, "FORBIDDEN")
        return f(*args, **kwargs)
    return wrapper


def timed(f):
    """Add X-Response-Time header and log slow requests (>500ms)."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        t0 = time.monotonic()
        response = f(*args, **kwargs)
        ms = int((time.monotonic() - t0) * 1000)
        if isinstance(response, tuple):
            resp, status = response
            resp.headers["X-Response-Time"] = f"{ms}ms"
            if ms > 500:
                log_backend(
                    level="WARNING", module_name="api_v1", action_name=f.__name__,
                    http_method=request.method, endpoint=request.path,
                    duration_ms=ms, status_code=status,
                    error_message=f"Slow request: {ms}ms"
                )
            return resp, status
        return response
    return wrapper


# ════════════════════════════════════════════════════════════════
# HEALTH CHECK — public, no auth
# ════════════════════════════════════════════════════════════════

@api_v1_bp.route("/health")
@timed
def health():
    """
    GET /api/v1/health
    Public endpoint. Returns 200 OK when the app is running.
    Used by load balancers, Koyeb health checks, and uptime monitors.
    """
    db_ok = False
    db_latency_ms = 0
    try:
        t0 = time.monotonic()
        conn = db.get_db()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        db_latency_ms = int((time.monotonic() - t0) * 1000)
        db_ok = True
    except Exception as e:
        db_ok = False

    status_code = 200 if db_ok else 503
    return ok({
        "status":        "healthy" if db_ok else "degraded",
        "app_version":   APP_VERSION,
        "build":         BUILD_NUMBER,
        "environment":   os.environ.get("FLASK_ENV", "development"),
        "database":      "ok" if db_ok else "unavailable",
        "db_latency_ms": db_latency_ms,
        "uptime_check":  datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }, status=status_code)


# ════════════════════════════════════════════════════════════════
# SYSTEM DIAGNOSTICS — admin only
# ════════════════════════════════════════════════════════════════

@api_v1_bp.route("/system/diagnostics")
@require_auth
@require_admin
@timed
def diagnostics():
    """
    GET /api/v1/system/diagnostics
    Admin-only full system diagnostics.
    """
    report = {}

    # DB stats
    try:
        conn = db.get_db()
        t0 = time.monotonic()
        conn.execute("SELECT 1").fetchone()
        db_ping = int((time.monotonic() - t0) * 1000)

        tables = [
            "owners", "pets", "appointments", "visits", "invoices",
            "users", "backend_logs", "frontend_logs", "audit_logs",
            "sync_queue", "sync_conflicts", "devices",
        ]
        table_counts = {}
        for tbl in tables:
            try:
                row = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()
                table_counts[tbl] = row[0] if row else 0
            except Exception:
                table_counts[tbl] = -1
        conn.close()

        report["database"] = {
            "status": "ok", "ping_ms": db_ping, "table_counts": table_counts
        }
    except Exception as e:
        report["database"] = {"status": "error", "error": str(e)}

    # Log file stats
    from pathlib import Path
    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_files = []
    for f in sorted(log_dir.rglob("*.log")):
        log_files.append({
            "file":     f.name,
            "channel":  f.parent.name,
            "size_kb":  round(f.stat().st_size / 1024, 1),
            "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    report["log_files"] = log_files

    # Sync summary
    try:
        report["sync"] = get_sync_status_summary()
    except Exception as e:
        report["sync"] = {"error": str(e)}

    # Error count last 24h
    try:
        conn = db.get_db()
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        err_count = conn.execute(
            "SELECT COUNT(*) FROM backend_logs WHERE level IN ('ERROR','CRITICAL') AND created_at>?",
            (cutoff,)
        ).fetchone()[0]
        active_devices = conn.execute(
            "SELECT COUNT(*) FROM devices WHERE last_online_at>?", (cutoff,)
        ).fetchone()[0]
        conn.close()
        report["errors_last_24h"] = err_count
        report["active_devices_24h"] = active_devices
    except Exception:
        report["errors_last_24h"] = -1

    # System info
    report["system"] = {
        "python_version":  platform.python_version(),
        "platform":        platform.system(),
        "app_version":     APP_VERSION,
        "build":           BUILD_NUMBER,
        "environment":     os.environ.get("FLASK_ENV", "development"),
        "log_retention":   int(os.environ.get("LOG_FILE_RETENTION_DAYS", "7")),
        "timestamp":       datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

    log_audit(
        user_id=session.get("user_id"), username=session.get("username", ""),
        action_type="VIEW", entity_name="system_diagnostics", entity_id="",
        ip_address=request.remote_addr, user_agent=request.user_agent.string[:200],
    )

    return ok(report)


# ════════════════════════════════════════════════════════════════
# FRONTEND LOG RECEIVER
# ════════════════════════════════════════════════════════════════

@api_v1_bp.route("/logs/frontend", methods=["POST"])
def receive_frontend_log():
    """
    POST /api/v1/logs/frontend
    Browser sends batched frontend logs when online.
    Body: { logs: [{...}, ...] }  OR a single log object.
    No auth required — session info embedded in payload.
    Rate limited implicitly by Flask-Limiter on the app level.
    """
    try:
        data = request.get_json(silent=True) or {}
        logs = data.get("logs", [data] if data else [])
        # Enrich with server-side user if session exists
        uid = session.get("user_id")
        uname = session.get("username", "")
        for entry in logs[:50]:  # cap at 50 per batch
            if uid and not entry.get("user_id"):
                entry["user_id"] = uid
                entry["username"] = uname
            log_frontend(entry)
        return ok({"accepted": len(logs[:50])})
    except Exception as e:
        return err("Log ingestion failed", 500)


# ════════════════════════════════════════════════════════════════
# SYNC — PUSH (offline → server)
# ════════════════════════════════════════════════════════════════

@api_v1_bp.route("/sync/push", methods=["POST"])
@require_auth
def sync_push():
    """
    POST /api/v1/sync/push
    Device pushes its pending offline queue items.
    Body: {
      device_id: str,
      items: [{
        local_uuid, entity_name, operation_type,
        payload, created_offline_at, priority
      }]
    }
    """
    data = request.get_json(silent=True) or {}
    device_id = data.get("device_id", "")
    items = data.get("items", [])
    if not device_id:
        return err("device_id is required", 400)
    if not items:
        return ok({"queued": 0})

    user_id = session.get("user_id")
    register_device(device_id, user_id=user_id)
    touch_device_online(device_id)

    queued = 0
    results = []
    for item in items[:200]:  # cap 200 per push
        try:
            qid = enqueue(
                device_id=device_id,
                user_id=user_id,
                entity_name=item.get("entity_name", ""),
                operation=item.get("operation_type", "CREATE"),
                payload=item.get("payload", {}),
                local_uuid=item.get("local_uuid", ""),
                priority=item.get("priority", 5),
                created_offline_at=item.get("created_offline_at", ""),
            )
            results.append({"local_uuid": item.get("local_uuid"), "queue_id": qid, "status": "queued"})
            queued += 1
        except Exception as e:
            results.append({"local_uuid": item.get("local_uuid"), "status": "error", "error": str(e)})

    log_audit(
        user_id=user_id, username=session.get("username", ""),
        action_type="SYNC", entity_name="sync_queue", entity_id=device_id,
        new_value={"queued": queued, "device": device_id},
        ip_address=request.remote_addr,
    )

    return ok({"queued": queued, "results": results})


@api_v1_bp.route("/sync/status")
@require_auth
def sync_status():
    """GET /api/v1/sync/status — queue summary for current user or all (admin)."""
    return ok(get_sync_status_summary())


@api_v1_bp.route("/sync/pending")
@require_auth
@require_admin
def sync_pending():
    """GET /api/v1/sync/pending — full pending list (admin only)."""
    device_id = request.args.get("device_id", "")
    limit = min(int(request.args.get("limit", 100)), 500)
    items = get_pending(device_id=device_id, limit=limit)
    return ok({"items": items, "count": len(items)})


@api_v1_bp.route("/sync/conflicts")
@require_auth
@require_admin
def sync_conflicts_list():
    """GET /api/v1/sync/conflicts — unresolved conflicts."""
    conn = db.get_db()
    rows = conn.execute(
        "SELECT * FROM sync_conflicts WHERE resolution_status='PENDING' ORDER BY created_at DESC LIMIT 200"
    ).fetchall()
    conn.close()
    return ok({"conflicts": [dict(r) for r in rows], "count": len(rows)})


@api_v1_bp.route("/sync/conflicts/<conflict_id>/resolve", methods=["POST"])
@require_auth
@require_admin
def sync_resolve_conflict(conflict_id):
    """POST /api/v1/sync/conflicts/:id/resolve  Body: { keep: 'server'|'local' }"""
    data = request.get_json(silent=True) or {}
    keep = data.get("keep", "server")
    username = session.get("username", "system")
    resolve_conflict(conflict_id, resolved_by=username, keep=keep)
    log_audit(
        user_id=session.get("user_id"), username=username,
        action_type="APPROVE", entity_name="sync_conflict", entity_id=conflict_id,
        new_value={"keep": keep}, ip_address=request.remote_addr,
    )
    return ok({"resolved": conflict_id, "kept": keep})


@api_v1_bp.route("/sync/devices")
@require_auth
@require_admin
def sync_devices():
    """GET /api/v1/sync/devices — all registered devices."""
    conn = db.get_db()
    rows = conn.execute(
        "SELECT * FROM devices ORDER BY last_online_at DESC"
    ).fetchall()
    conn.close()
    return ok({"devices": [dict(r) for r in rows]})


# ════════════════════════════════════════════════════════════════
# LOG MANAGEMENT (admin)
# ════════════════════════════════════════════════════════════════

@api_v1_bp.route("/logs/cleanup", methods=["POST"])
@require_auth
@require_admin
def logs_cleanup():
    """POST /api/v1/logs/cleanup — manually trigger log file retention cleanup."""
    deleted = cleanup_old_logs()
    log_audit(
        user_id=session.get("user_id"), username=session.get("username", ""),
        action_type="DELETE", entity_name="log_files", entity_id="",
        new_value={"deleted_files": deleted}, ip_address=request.remote_addr,
    )
    return ok({"deleted_files": deleted})


@api_v1_bp.route("/logs/backend")
@require_auth
@require_admin
def logs_backend():
    """GET /api/v1/logs/backend?level=ERROR&limit=100&hours=24"""
    level = request.args.get("level", "")
    limit = min(int(request.args.get("limit", 100)), 1000)
    hours = int(request.args.get("hours", 24))
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

    conn = db.get_db()
    if level:
        rows = conn.execute(
            "SELECT * FROM backend_logs WHERE level=? AND created_at>? ORDER BY created_at DESC LIMIT ?",
            (level, cutoff, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM backend_logs WHERE created_at>? ORDER BY created_at DESC LIMIT ?",
            (cutoff, limit)
        ).fetchall()
    conn.close()
    return ok({"logs": [dict(r) for r in rows], "count": len(rows)})


# ════════════════════════════════════════════════════════════════
# VERSION INFO
# ════════════════════════════════════════════════════════════════

@api_v1_bp.route("/version")
def version():
    """GET /api/v1/version — app version info."""
    return ok({
        "app_version":    APP_VERSION,
        "build":          BUILD_NUMBER,
        "api_version":    "v1",
        "environment":    os.environ.get("FLASK_ENV", "development"),
        "released_at":    os.environ.get("RELEASE_DATE", "2026-05-24"),
    })


# ── Global error handlers for this blueprint ─────────────────

@api_v1_bp.errorhandler(404)
def not_found(e):
    return err("Endpoint not found", 404, "NOT_FOUND")


@api_v1_bp.errorhandler(405)
def method_not_allowed(e):
    return err("Method not allowed", 405, "METHOD_NOT_ALLOWED")


@api_v1_bp.errorhandler(500)
def internal_error(e):
    log_backend(
        level="CRITICAL", module_name="api_v1", action_name="unhandled_error",
        http_method=request.method, endpoint=request.path, status_code=500,
        error_message=str(e), stack_trace=traceback.format_exc(),
        ip_address=request.remote_addr,
    )
    return err("Internal server error", 500, "INTERNAL_ERROR")
