"""
Offline / Online Sync Engine
──────────────────────────────
Manages the sync_queue and sync_conflicts tables.

Flow:
  Offline  → client writes to local IndexedDB, posts to /api/v1/sync/push on reconnect
  Backend  → applies operations, marks queue items SYNCED or CONFLICT
  Admin    → views pending/failed via /api/v1/sync/status
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Optional

import models.database as db
from models import clock

logger = logging.getLogger(__name__)


# ── Constants ─────────────────────────────────────────────────
STATUS_PENDING  = "PENDING"
STATUS_SYNCING  = "SYNCING"
STATUS_SYNCED   = "SYNCED"
STATUS_FAILED   = "FAILED"
STATUS_CONFLICT = "CONFLICT"

OP_CREATE = "CREATE"
OP_UPDATE = "UPDATE"
OP_DELETE = "DELETE"

MAX_RETRY = 5


# ════════════════════════════════════════════════════════════════
# SYNC QUEUE OPERATIONS
# ════════════════════════════════════════════════════════════════

def enqueue(
    device_id:   str,
    user_id:     int,
    entity_name: str,
    operation:   str,
    payload:     dict,
    local_uuid:  str  = "",
    priority:    int  = 5,
    created_offline_at: str = "",
) -> str:
    """Add an offline action to the sync queue. Returns the queue record UUID."""
    record_id = str(uuid.uuid4())
    local_uuid = local_uuid or record_id
    ts = clock.utcnow().isoformat(timespec="milliseconds")
    offline_ts = created_offline_at or ts

    conn = db.get_db()
    conn.execute(
        """INSERT INTO sync_queue
           (id, local_uuid, device_id, user_id, entity_name, operation_type,
            payload, status, retry_count, priority,
            created_offline_at, created_at, updated_at)
           VALUES (?,?,?,?,?,?, ?,?,?,?, ?,?,?)""",
        (
            record_id, local_uuid, device_id, user_id,
            entity_name, operation,
            json.dumps(payload), STATUS_PENDING, 0, priority,
            offline_ts, ts, ts,
        ),
    )
    conn.commit()
    conn.close()
    logger.info("Enqueued %s %s (uuid=%s)", operation, entity_name, record_id)
    return record_id


def get_pending(device_id: str = "", limit: int = 100) -> list:
    """Return PENDING queue items ordered by priority then created_offline_at."""
    conn = db.get_db()
    if device_id:
        rows = conn.execute(
            """SELECT * FROM sync_queue WHERE status=? AND device_id=?
               ORDER BY priority DESC, created_offline_at ASC LIMIT ?""",
            (STATUS_PENDING, device_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM sync_queue WHERE status=?
               ORDER BY priority DESC, created_offline_at ASC LIMIT ?""",
            (STATUS_PENDING, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_synced(queue_id: str, server_uuid: str = "") -> None:
    ts = clock.utcnow().isoformat(timespec="milliseconds")
    conn = db.get_db()
    conn.execute(
        """UPDATE sync_queue SET status=?, server_uuid=?, synced_at=?, updated_at=?
           WHERE id=?""",
        (STATUS_SYNCED, server_uuid, ts, ts, queue_id),
    )
    conn.commit()
    conn.close()


def mark_failed(queue_id: str, error: str) -> None:
    ts = clock.utcnow().isoformat(timespec="milliseconds")
    conn = db.get_db()
    row = conn.execute(
        "SELECT retry_count FROM sync_queue WHERE id=?", (queue_id,)
    ).fetchone()
    retry = (row["retry_count"] + 1) if row else 1
    new_status = STATUS_FAILED if retry >= MAX_RETRY else STATUS_PENDING
    conn.execute(
        """UPDATE sync_queue
           SET status=?, retry_count=?, last_error=?, last_attempt_at=?, updated_at=?
           WHERE id=?""",
        (new_status, retry, error[:2000], ts, ts, queue_id),
    )
    conn.commit()
    conn.close()


def mark_conflict(queue_id: str, local_payload: dict, server_payload: dict,
                  conflict_type: str = "UPDATE_CONFLICT") -> str:
    """Mark queue item as CONFLICT and create a conflict record."""
    ts  = clock.utcnow().isoformat(timespec="milliseconds")
    cid = str(uuid.uuid4())

    conn = db.get_db()
    conn.execute(
        "UPDATE sync_queue SET status=?, updated_at=? WHERE id=?",
        (STATUS_CONFLICT, ts, queue_id),
    )
    row = conn.execute(
        "SELECT entity_name FROM sync_queue WHERE id=?", (queue_id,)
    ).fetchone()
    entity_name = row["entity_name"] if row else ""
    conn.execute(
        """INSERT INTO sync_conflicts
           (id, sync_queue_id, entity_name, local_payload, server_payload,
            conflict_type, resolution_status, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (
            cid, queue_id, entity_name,
            json.dumps(local_payload), json.dumps(server_payload),
            conflict_type, "PENDING", ts,
        ),
    )
    conn.commit()
    conn.close()
    return cid


def resolve_conflict(conflict_id: str, resolved_by: str,
                     keep: str = "server") -> None:
    """Mark a conflict resolved, recording WHICH side was kept.

    `keep` was accepted, documented as 'server'|'local', and then never used:
    the body wrote a single 'MANUAL_RESOLVED' and nothing else. So choosing
    "Keep Local" discarded the device's version and the screen said "Conflict
    resolved. Kept: local version." — which was not true, and left no trace of
    what had been thrown away.

    The choice is now recorded in resolution_status, so the two outcomes are
    distinguishable afterwards and the local payload stays on the row either
    way. Applying the local payload back over the server record is NOT done
    here: that is a per-entity write this module has no safe generic path for,
    and silently guessing at it would be a worse version of the same bug.
    Callers must tell the user that "keep local" preserves the device's copy
    for review rather than pushing it.
    """
    side = "LOCAL" if str(keep or "").strip().lower() == "local" else "SERVER"
    ts = clock.utcnow().isoformat(timespec="milliseconds")
    conn = db.get_db()
    conn.execute(
        """UPDATE sync_conflicts
           SET resolution_status=?, resolved_by=?, resolved_at=?
           WHERE id=?""",
        ("MANUAL_RESOLVED_" + side, resolved_by, ts, conflict_id),
    )
    conn.commit()
    conn.close()


def get_sync_status_summary() -> dict:
    """Dashboard summary for admin sync status screen."""
    conn = db.get_db()
    def count(status):
        r = conn.execute(
            "SELECT COUNT(*) FROM sync_queue WHERE status=?", (status,)
        ).fetchone()
        return r[0] if r else 0

    pending   = count(STATUS_PENDING)
    syncing   = count(STATUS_SYNCING)
    synced    = count(STATUS_SYNCED)
    failed    = count(STATUS_FAILED)
    conflicts = count(STATUS_CONFLICT)

    last_sync_row = conn.execute(
        "SELECT MAX(synced_at) FROM sync_queue WHERE status='SYNCED'"
    ).fetchone()
    last_sync = last_sync_row[0] if last_sync_row else None

    conflict_pending = conn.execute(
        "SELECT COUNT(*) FROM sync_conflicts WHERE resolution_status='PENDING'"
    ).fetchone()[0]

    conn.close()
    return {
        "pending":          pending,
        "syncing":          syncing,
        "synced":           synced,
        "failed":           failed,
        "conflicts":        conflicts,
        "conflict_pending": conflict_pending,
        "last_sync_at":     last_sync,
        "total_queued":     pending + syncing + synced + failed + conflicts,
    }


# ════════════════════════════════════════════════════════════════
# DEVICE REGISTRY
# ════════════════════════════════════════════════════════════════

def register_device(device_id: str, device_name: str = "",
                    platform: str = "", app_version: str = "",
                    user_id: int = None, branch_id: int = None) -> None:
    ts = clock.utcnow().isoformat(timespec="milliseconds")
    conn = db.get_db()
    existing = conn.execute(
        "SELECT id FROM devices WHERE device_id=?", (device_id,)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE devices SET last_online_at=?, app_version=?, updated_at=?
               WHERE device_id=?""",
            (ts, app_version, ts, device_id),
        )
    else:
        conn.execute(
            """INSERT INTO devices
               (device_id, device_name, branch_id, user_id,
                platform, app_version, last_online_at, is_active,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (device_id, device_name, branch_id, user_id,
             platform, app_version, ts, 1, ts, ts),
        )
    conn.commit()
    conn.close()


def touch_device_online(device_id: str) -> None:
    ts = clock.utcnow().isoformat(timespec="milliseconds")
    conn = db.get_db()
    conn.execute(
        "UPDATE devices SET last_online_at=?, updated_at=? WHERE device_id=?",
        (ts, ts, device_id),
    )
    conn.commit()
    conn.close()
