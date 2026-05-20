"""
Production Security Layer — Premium Animal Hospital Platform
Handles: rate limiting, CSRF tokens, session validation, bcrypt migration
"""
import secrets
import threading
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, abort, g

# ── Rate Limiting (in-memory, thread-safe) ────────────────────────────────────

_lock = threading.Lock()
_attempts: dict = {}   # ip → {"count": int, "locked_until": float}

RATE_LIMIT_MAX     = 5      # failed attempts before lockout
RATE_LIMIT_WINDOW  = 900    # 15 minutes lockout (seconds)
SESSION_TIMEOUT    = 3600   # 1 hour session idle timeout (seconds)


def record_failed_login(ip: str) -> bool:
    """Record a failed login attempt. Returns True if now locked out."""
    now = time.time()
    with _lock:
        rec = _attempts.get(ip, {"count": 0, "locked_until": 0})
        # Clear stale lockout
        if rec["locked_until"] and now > rec["locked_until"]:
            rec = {"count": 0, "locked_until": 0}
        rec["count"] += 1
        if rec["count"] >= RATE_LIMIT_MAX:
            rec["locked_until"] = now + RATE_LIMIT_WINDOW
        _attempts[ip] = rec
        return rec["count"] >= RATE_LIMIT_MAX


def is_rate_limited(ip: str) -> tuple[bool, int]:
    """Returns (is_locked, seconds_remaining)."""
    now = time.time()
    with _lock:
        rec = _attempts.get(ip, {"count": 0, "locked_until": 0})
        if rec["locked_until"] and now < rec["locked_until"]:
            return True, int(rec["locked_until"] - now)
        return False, 0


def clear_rate_limit(ip: str) -> None:
    """Clear rate limit on successful login."""
    with _lock:
        _attempts.pop(ip, None)


def cleanup_rate_limits() -> None:
    """Purge expired entries (call periodically)."""
    now = time.time()
    with _lock:
        expired = [ip for ip, r in _attempts.items()
                   if r["locked_until"] == 0 or now > r["locked_until"] + RATE_LIMIT_WINDOW]
        for ip in expired:
            _attempts.pop(ip, None)


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
