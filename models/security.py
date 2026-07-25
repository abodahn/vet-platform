"""
Production Security Layer — Aleefy Platform
Handles: rate limiting, CSRF tokens, session validation, IP extraction, password strength
"""
import re
import secrets
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, abort, g

# ── Rate Limiting (database-backed — survives restarts and multiple workers) ──
#
# Counters live in the `login_attempts` table, not in process memory: under
# gunicorn with N workers an in-memory dict gives an effective threshold of
# RATE_LIMIT_MAX * N, and every restart resets it to zero.
#
# The table is append-only (one row per failed attempt) and lockout is derived
# by counting rows inside the window. That is deliberate: there is no
# read-modify-write cycle, so concurrent workers cannot lose an increment.
# `_lock` is retained only to serialise writes within a single process, which
# keeps SQLite's writer lock contention down.

_lock = threading.Lock()

RATE_LIMIT_MAX     = 5      # failed attempts before lockout
RATE_LIMIT_WINDOW  = 900    # 15 minutes lockout (seconds)
SESSION_TIMEOUT    = 3600   # 1 hour session idle timeout (seconds)

_tables_ready = False

# DOUBLE PRECISION is deliberate and portable: PostgreSQL REAL is a 4-byte
# float (~7 significant digits) which would round a unix epoch timestamp to the
# nearest ~128 seconds. SQLite gives any type name containing "DOUB" REAL
# affinity, so the same DDL is correct on both engines.
_DDL = """CREATE TABLE IF NOT EXISTS login_attempts (
    ip       TEXT NOT NULL,
    username TEXT NOT NULL DEFAULT '',
    ts       DOUBLE PRECISION NOT NULL
)"""


def _ensure_tables() -> None:
    """Create the login_attempts table on first use (idempotent)."""
    global _tables_ready
    if _tables_ready:
        return
    from models.database import get_db
    with _lock:
        if _tables_ready:
            return
        conn = get_db()
        try:
            conn.execute(_DDL)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_ip "
                         "ON login_attempts(ip, ts)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_user "
                         "ON login_attempts(username, ts)")
            conn.commit()
        finally:
            conn.close()
        _tables_ready = True


def _norm_user(username) -> str:
    """Normalise a username for keying (case-insensitive, trimmed)."""
    return (username or "").strip().lower()


def record_failed_login(ip: str, username: str = None) -> bool:
    """Record a failed login attempt. Returns True if now locked out.

    Keyed on BOTH ip and username so a distributed attack spread across many
    source addresses against one account still trips the lockout.
    """
    _ensure_tables()
    from models.database import get_db
    now = time.time()
    conn = get_db()
    try:
        with _lock:
            conn.execute(
                "INSERT INTO login_attempts (ip, username, ts) VALUES (?,?,?)",
                (ip or "unknown", _norm_user(username), now))
            conn.commit()
    finally:
        conn.close()
    locked, _ = is_rate_limited(ip, username)
    return locked


def is_rate_limited(ip: str, username: str = None) -> tuple[bool, int]:
    """Returns (is_locked, seconds_remaining).

    Locked when EITHER this IP or this username has reached RATE_LIMIT_MAX
    failed attempts inside the window.
    """
    _ensure_tables()
    from models.database import get_db
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW
    conn = get_db()
    try:
        remaining = 0
        for column, value in (("ip", ip), ("username", _norm_user(username))):
            if not value:
                continue
            # The RATE_LIMIT_MAX-th most recent attempt: once it ages out of
            # the window the count drops below the threshold and the lock lifts.
            # Column name is a fixed literal from this tuple, never user input.
            row = conn.execute(
                f"SELECT ts FROM login_attempts WHERE {column}=? AND ts>? "
                "ORDER BY ts DESC LIMIT 1 OFFSET ?",
                (value, cutoff, RATE_LIMIT_MAX - 1)).fetchone()
            if row:
                secs = int(row[0] + RATE_LIMIT_WINDOW - now) + 1
                remaining = max(remaining, secs)
        return (remaining > 0), remaining
    finally:
        conn.close()


def clear_rate_limit(ip: str, username: str = None) -> None:
    """Clear rate limit on successful login (clears both IP and username keys)."""
    _ensure_tables()
    from models.database import get_db
    conn = get_db()
    try:
        with _lock:
            if ip:
                conn.execute("DELETE FROM login_attempts WHERE ip=?", (ip,))
            uname = _norm_user(username)
            if uname:
                conn.execute("DELETE FROM login_attempts WHERE username=?", (uname,))
            conn.commit()
    finally:
        conn.close()


def cleanup_rate_limits() -> None:
    """Purge attempts that have aged out of the window (call periodically)."""
    _ensure_tables()
    from models.database import get_db
    cutoff = time.time() - RATE_LIMIT_WINDOW
    conn = get_db()
    try:
        with _lock:
            conn.execute("DELETE FROM login_attempts WHERE ts<=?", (cutoff,))
            conn.commit()
    finally:
        conn.close()


# ── CSRF Protection ───────────────────────────────────────────────────────────

_CSRF_SESSION_KEY = "_csrf_token"
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Routes that are whitelisted from CSRF (public endpoints)
_CSRF_EXEMPT = {"/auth/login", "/settings/theme", "/settings/lang"}


def generate_csrf_token() -> str:
    if _CSRF_SESSION_KEY not in session:
        session[_CSRF_SESSION_KEY] = secrets.token_hex(32)
    return session[_CSRF_SESSION_KEY]


def validate_csrf() -> bool:
    if request.method in _SAFE_METHODS:
        return True
    if request.path in _CSRF_EXEMPT:
        return True
    token = (
        request.form.get("_csrf_token")
        or request.headers.get("X-CSRF-Token")
        or (request.json.get("_csrf_token") if request.is_json else None)
    )
    expected = session.get(_CSRF_SESSION_KEY)
    if not token or not expected:
        return False
    return secrets.compare_digest(token, expected)


# ── Session Timeout ───────────────────────────────────────────────────────────

_SESSION_LAST_ACTIVE = "_last_active"


def check_session_timeout() -> bool:
    """Returns True if session has timed out."""
    if not session.get("user"):
        return False
    last = session.get(_SESSION_LAST_ACTIVE)
    if not last:
        session[_SESSION_LAST_ACTIVE] = time.time()
        return False
    if time.time() - last > SESSION_TIMEOUT:
        return True
    session[_SESSION_LAST_ACTIVE] = time.time()
    return False


def touch_session() -> None:
    session[_SESSION_LAST_ACTIVE] = time.time()


# ── Real IP Extraction ────────────────────────────────────────────────────────

def get_real_ip(req=None) -> str:
    """Extract the real client IP, trusting X-Forwarded-For from the first proxy.

    Render, Koyeb, and Cloudflare all set X-Forwarded-For.
    We take only the FIRST (leftmost) address — the client IP as seen by the
    first proxy — which is the real client under standard proxy chaining.

    Falls back to request.remote_addr if no forwarding header is present.
    """
    if req is None:
        req = request
    forwarded_for = req.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # "X-Forwarded-For: client, proxy1, proxy2" — take leftmost (client IP)
        candidate = forwarded_for.split(",")[0].strip()
        if candidate:
            return candidate
    return req.remote_addr or "unknown"


# ── Password Strength Validation ─────────────────────────────────────────────

def validate_password_strength(password: str) -> tuple[bool, str]:
    """Validate password complexity. Returns (ok, error_message).

    Rules:
    - Minimum 12 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character (!@#$%^&*()_+-=[]{}|;':\",./<>?)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:'\",.<>?/\\`~]", password):
        return False, "Password must contain at least one special character."
    return True, ""
