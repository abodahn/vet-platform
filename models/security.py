"""
Production Security Layer — Aleefy Platform
Handles: rate limiting, CSRF tokens, session validation, IP extraction,
password strength, TOTP two-factor authentication
"""
import base64
import hashlib
import io
import logging
import os
import re
import secrets
import threading

# Safe at module level: database.py imports nothing from here.
import models.database as _db
import time
from datetime import datetime, timedelta
from functools import wraps
from flask import session, request, abort, g

logger = logging.getLogger(__name__)

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

# Keyed by DATABASE, not a bare bool: this process serves many clinics and a
# latch recording only "already ran" would build these tables in whichever
# tenant loaded first and leave every clinic provisioned later without them.
_tables_ready = {}

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
    if not _db._ensure_schema_once(_tables_ready, 'login_attempts'):
        return
    from models.database import get_db
    with _lock:
        if not _db._ensure_schema_once(_tables_ready, 'login_attempts'):
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
        _db._schema_done(_tables_ready, 'login_attempts')


def _norm_user(username) -> str:
    """Normalise a username for keying (case-insensitive, trimmed)."""
    return (username or "").strip().lower()


# ── General-purpose throttle ─────────────────────────────────────────────────
#
# Separate from login_attempts on purpose. The public API used to call
# is_rate_limited(ip), which counts rows that ONLY record_failed_login writes —
# so a bot hammering /api/public/book incremented nothing and the check it was
# guarded by could never fire. A limiter has to count the traffic it limits.
#
# Its own table rather than a bucket column on login_attempts because login is
# the single most important path in the system and must not be disturbed by an
# ALTER done for a public endpoint.

_THROTTLE_DDL = """CREATE TABLE IF NOT EXISTS rate_hits (
    bucket TEXT NOT NULL,
    key    TEXT NOT NULL,
    ts     DOUBLE PRECISION NOT NULL
)"""

_throttle_ready = {}


def _ensure_throttle() -> None:
    if not _db._ensure_schema_once(_throttle_ready, "rate_hits"):
        return
    from models.database import get_db
    with _lock:
        if not _db._ensure_schema_once(_throttle_ready, "rate_hits"):
            return
        conn = get_db()
        try:
            conn.execute(_THROTTLE_DDL)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rate_hits "
                         "ON rate_hits(bucket, key, ts)")
            conn.commit()
        finally:
            conn.close()
        _db._schema_done(_throttle_ready, "rate_hits")


def throttle(bucket: str, key: str, max_hits: int, window: int) -> tuple:
    """Record one hit and report (over_limit, seconds_until_clear).

    Records BEFORE checking — that ordering is the entire fix. Callers use it
    as a gate:

        over, wait = sec.throttle("public_book", ip, 20, 3600)
        if over: return 429

    Fails OPEN on a database error: a public booking form that rejects real
    clients because the throttle table is unavailable is worse than one that
    briefly lets an abuser through, and the error is logged either way.
    """
    from models.database import get_db
    now = time.time()
    cutoff = now - window
    conn = None
    # The WHOLE thing, not just the queries: creating the table and checking out
    # the connection can both fail, and a fail-open guard that still raises from
    # its first two lines is not fail-open at all.
    try:
        _ensure_throttle()
        conn = get_db()
        with _lock:
            conn.execute("INSERT INTO rate_hits (bucket, key, ts) VALUES (?,?,?)",
                         (bucket, key or "unknown", now))
            # Opportunistic cleanup: without it this table grows forever, and
            # nothing else ever visits it.
            conn.execute("DELETE FROM rate_hits WHERE ts < ?", (now - max(window, 3600) * 24,))
            conn.commit()
            row = conn.execute(
                "SELECT ts FROM rate_hits WHERE bucket=? AND key=? AND ts>? "
                "ORDER BY ts DESC LIMIT 1 OFFSET ?",
                (bucket, key or "unknown", cutoff, max_hits - 1)).fetchone()
    except Exception:
        logger.exception("throttle unavailable for %s/%s — allowing the request",
                         bucket, key)
        return False, 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
    if row:
        return True, int(row[0] + window - now) + 1
    return False, 0


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
    """The client IP, from a header the client cannot forge.

    This used to take the LEFTMOST X-Forwarded-For entry. nginx is configured
    with `$proxy_add_x_forwarded_for`, which APPENDS the real peer address to
    whatever the client sent — so the leftmost value is entirely
    attacker-supplied.

    That was demonstrated against the live server: five failed logins carrying
    `X-Forwarded-For: 203.0.113.77` locked that address out of logging in for
    fifteen minutes, and every audit row recorded the forged address. An
    attacker could pick a clinic's office IP and keep its staff out, and poison
    the one column you would look at afterwards to find out who did it.

    X-Real-IP is set by nginx to $remote_addr and is overwritten on every
    request, so a client cannot influence it. Prefer it; fall back to the
    RIGHTMOST X-Forwarded-For hop (the one our own proxy appended) and finally
    to the socket address.
    """
    if req is None:
        req = request
    real_ip = (req.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip
    forwarded_for = req.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        # Rightmost, not leftmost: everything to its left came from the client.
        candidate = forwarded_for.split(",")[-1].strip()
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


# ── TOTP Two-Factor Authentication (RFC 6238) ────────────────────────────────
#
# Opt-in, per user. Nothing here changes behaviour for a user who has not
# enrolled: totp_required() returns False and the login path is untouched.
#
# Optional dependencies. Both are in requirements.txt, but the app must still
# boot and password login must still work if a deploy lands without them.

try:
    import pyotp
except ImportError:                                     # pragma: no cover
    pyotp = None
    logger.warning(
        "pyotp is not installed — two-factor authentication is DISABLED. "
        "Fix with: pip install 'pyotp>=2.9.0'")

try:
    import qrcode
except ImportError:                                     # pragma: no cover
    qrcode = None
    logger.warning(
        "qrcode is not installed — 2FA enrolment will show the text secret "
        "instead of a QR code. Fix with: pip install 'qrcode[pil]>=7.4'")

BACKUP_CODE_COUNT = 10

# bcrypt cost for backup codes. Lower than the rounds=12 used for passwords on
# purpose: a backup code is 48 bits of CSPRNG output, not a human-chosen
# password, so it has no dictionary to defend against — the cost only buys
# protection the entropy already provides, and consume_backup_code() has to
# hash against every unused row.
# ponytail: rounds=10 with a linear scan over <=10 rows; if backup codes ever
# grow to hundreds per user, index a non-secret prefix instead.
_BACKUP_CODE_ROUNDS = 10


# ── Secret at rest ───────────────────────────────────────────────────────────
#
# The TOTP secret is encrypted with a key derived from the app SECRET_KEY, so a
# stolen database file / pg_dump / backup archive is not by itself a second
# factor. The key deliberately introduces NO new operational burden: it is
# derived from a value the deployment already has to set and already has to
# protect (it signs the session cookie), so there is no new secret to rotate,
# distribute, or lose.
#
# Residual risk, stated plainly:
#   * Host compromise defeats this — the running process can decrypt.
#   * Rotating PLATFORM_SECRET_KEY makes every enrolled secret undecryptable.
#     Those users must be reset by an admin and re-enrol. Failure is loud
#     (logged ERROR + login refused), never silent.
#   * If `cryptography` is missing the secret falls back to plaintext with a
#     "plain:" marker and a WARNING — visible, not silent.

_TOTP_ENC_PREFIX = "enc1:"
_TOTP_PLAIN_PREFIX = "plain:"
_fernet_cache: dict = {}


def _fernet():
    """Fernet keyed off SECRET_KEY, or None when it cannot be built."""
    from flask import current_app
    try:
        key_material = current_app.config.get("SECRET_KEY") or ""
    except RuntimeError:
        key_material = ""           # no application context
    if not key_material:
        return None
    hit = _fernet_cache.get(key_material)
    if hit is not None:
        return hit
    try:
        from cryptography.fernet import Fernet
    except ImportError:             # pragma: no cover
        return None
    key = base64.urlsafe_b64encode(
        hashlib.sha256(("aleefy-totp-v1:" + key_material).encode()).digest())
    f = Fernet(key)
    _fernet_cache[key_material] = f
    return f


def _encrypt_secret(secret: str) -> str:
    f = _fernet()
    if f is None:
        logger.warning(
            "TOTP secret is being stored WITHOUT encryption — no SECRET_KEY or "
            "`cryptography` is not installed. A database dump would expose the "
            "second factor. Fix with: pip install 'cryptography>=42.0'")
        return _TOTP_PLAIN_PREFIX + secret
    return _TOTP_ENC_PREFIX + f.encrypt(secret.encode()).decode()


def _decrypt_secret(stored):
    """Plain base32 secret, or None if it cannot be recovered."""
    if not stored:
        return None
    if stored.startswith(_TOTP_PLAIN_PREFIX):
        return stored[len(_TOTP_PLAIN_PREFIX):]
    if not stored.startswith(_TOTP_ENC_PREFIX):
        # Unprefixed legacy value — treat as plaintext rather than lock the user out.
        return stored
    f = _fernet()
    if f is None:
        logger.error("Cannot decrypt a stored TOTP secret: no SECRET_KEY or "
                     "`cryptography` is unavailable.")
        return None
    try:
        return f.decrypt(stored[len(_TOTP_ENC_PREFIX):].encode()).decode()
    except Exception as exc:
        logger.error(
            "Could not decrypt a stored TOTP secret (%s). PLATFORM_SECRET_KEY has "
            "most likely changed. An admin must reset 2FA for this user so they "
            "can re-enrol.", exc)
        return None


# ── Schema (lazy, portable across SQLite and PostgreSQL) ─────────────────────

_totp_ready = {}

_TOTP_DDL = """CREATE TABLE IF NOT EXISTS totp_backup_codes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    code_hash  TEXT NOT NULL,
    created_at TEXT,
    used_at    TEXT
)"""

_TOTP_USER_COLUMNS = (
    ("totp_secret",       "TEXT"),
    ("totp_enabled",      "INTEGER DEFAULT 0"),
    ("totp_confirmed_at", "TEXT"),
    ("last_totp_counter", "INTEGER DEFAULT 0"),
)


def _ensure_totp_schema() -> None:
    """Create the 2FA table and user columns on first use (idempotent).

    models.database._fix_sql() rewrites `?` -> `%s` and
    `INTEGER PRIMARY KEY AUTOINCREMENT` -> `SERIAL PRIMARY KEY`, so this one
    body of SQLite-flavoured DDL is correct on PostgreSQL too.
    """
    if not _db._ensure_schema_once(_totp_ready, 'totp'):
        return
    from models.database import get_db, _try_stmt
    with _lock:
        if not _db._ensure_schema_once(_totp_ready, 'totp'):
            return
        conn = get_db()
        try:
            conn.execute(_TOTP_DDL)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_totp_backup_user "
                         "ON totp_backup_codes(user_id)")
            conn.commit()
            # ADD COLUMN is expected to fail once already applied — _try_stmt
            # takes a PostgreSQL savepoint so the failure cannot poison the
            # surrounding transaction.
            for col, coltype in _TOTP_USER_COLUMNS:
                _try_stmt(conn, f"ALTER TABLE users ADD COLUMN {col} {coltype}")
            conn.commit()
        finally:
            conn.close()
        _db._schema_done(_totp_ready, 'totp')


def _user_totp_row(user_id):
    _ensure_totp_schema()
    from models.database import get_db
    conn = get_db()
    try:
        return conn.execute(
            "SELECT totp_secret, totp_enabled, totp_confirmed_at, last_totp_counter "
            "FROM users WHERE id=?", (user_id,)).fetchone()
    finally:
        conn.close()


# ── State ────────────────────────────────────────────────────────────────────

def totp_available() -> bool:
    """True when this server can do TOTP at all."""
    return pyotp is not None


class TOTPUnavailable(RuntimeError):
    """Raised when an account requires TOTP but the library is missing.

    Deliberately fatal to the login attempt: silently downgrading a
    two-factor account to password-only would remove a security control
    without anyone noticing. See TOTP_FAIL_OPEN for the recovery path.
    """


def totp_required(user_id) -> bool:
    """True when `user_id` must pass a TOTP challenge to finish logging in."""
    row = _user_totp_row(user_id)
    enabled = bool(row and row["totp_enabled"] and row["totp_secret"])
    if enabled and pyotp is None:
        # A missing library must not silently remove a security control.
        # Default is fail CLOSED: the user cannot complete login, and the
        # error names the fix. The escape hatch mirrors CORS_ALLOW_WILDCARD
        # in config.py — a clinic locked out by a bad deploy sets
        # TOTP_FAIL_OPEN=1, restarts, and gets password-only login back
        # while someone installs pyotp. Secure by default, recoverable in
        # one step, and the bypass is always a deliberate act.
        if os.environ.get("TOTP_FAIL_OPEN", "") == "1":
            logger.error(
                "User id=%s has 2FA enabled but pyotp is not installed. "
                "TOTP_FAIL_OPEN=1 is set, so password-only login is being "
                "ALLOWED. This disables two-factor authentication — install "
                "pyotp, restart, and unset TOTP_FAIL_OPEN.", user_id)
            return False
        logger.error(
            "User id=%s has 2FA enabled but pyotp is not installed — refusing "
            "login. Run 'pip install -r requirements.txt' and restart. To "
            "restore password-only access in the meantime, set TOTP_FAIL_OPEN=1.",
            user_id)
        raise TOTPUnavailable(
            "Two-factor authentication is required for this account but is "
            "not available on this server. Contact your administrator."
        )
    return enabled


def totp_status(user_id) -> dict:
    """Enrolment state for the profile page."""
    row = _user_totp_row(user_id)
    return {
        "available":        totp_available(),
        "enabled":          bool(row and row["totp_enabled"]),
        "pending":          bool(row and row["totp_secret"] and not row["totp_enabled"]),
        "confirmed_at":     (row["totp_confirmed_at"] if row else None),
        "backup_remaining": count_backup_codes(user_id),
    }


def get_pending_secret(user_id):
    """The base32 secret of an UNCONFIRMED enrolment, else None.

    Never returns a secret once 2FA is enabled: showing it again would let
    anyone with a live session clone the authenticator.
    """
    row = _user_totp_row(user_id)
    if not row or row["totp_enabled"] or not row["totp_secret"]:
        return None
    return _decrypt_secret(row["totp_secret"])


# ── Verification ─────────────────────────────────────────────────────────────

def _burn_counter(user_id, counter) -> bool:
    """Record `counter` as consumed. False if another request got there first."""
    from models.database import get_db
    conn = get_db()
    try:
        cur = conn.execute(
            "UPDATE users SET last_totp_counter=? "
            "WHERE id=? AND (last_totp_counter IS NULL OR last_totp_counter < ?)",
            (counter, user_id, counter))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


def verify_totp_code(user_id, code: str) -> bool:
    """Verify a 6-digit TOTP code and burn its time step.

    Replay defence: every accepted code advances `users.last_totp_counter`, and
    any step at or below that is refused. Without it a code shoulder-surfed at
    second 1 of its window stays usable for the remaining 29 (plus the +/-1 step
    drift window, so ~90 seconds in practice).
    """
    if pyotp is None:
        return False
    code = (code or "").strip().replace(" ", "").replace("-", "")
    if not code.isdigit():
        return False
    row = _user_totp_row(user_id)
    if not row:
        return False
    secret = _decrypt_secret(row["totp_secret"])
    if not secret:
        return False

    totp = pyotp.TOTP(secret)
    step = totp.interval
    last = int(row["last_totp_counter"] or 0)
    now = int(time.time())

    # pyotp.verify(valid_window=1) checks exactly these three steps but does not
    # report WHICH one matched — and the matched step is what replay defence
    # needs. So walk the same window and let pyotp generate each code; the
    # RFC 6238 maths stays in the library.
    for offset in (0, -1, 1):
        counter = (now + offset * step) // step
        if counter <= last:
            continue                        # already spent — replay
        if secrets.compare_digest(totp.at(counter * step), code):
            return _burn_counter(user_id, counter)
    return False


# ── Enrolment ────────────────────────────────────────────────────────────────

def start_totp_enrolment(user_id):
    """Generate and store a fresh UNCONFIRMED secret. Returns it, or None."""
    if pyotp is None:
        return None
    _ensure_totp_schema()
    from models.database import get_db
    secret = pyotp.random_base32()
    conn = get_db()
    with conn:
        conn.execute(
            "UPDATE users SET totp_secret=?, totp_enabled=0, "
            "totp_confirmed_at=NULL, last_totp_counter=0 WHERE id=?",
            (_encrypt_secret(secret), user_id))
        conn.execute("DELETE FROM totp_backup_codes WHERE user_id=?", (user_id,))
    conn.close()
    return secret


def confirm_totp_enrolment(user_id, code: str) -> bool:
    """Flip totp_enabled on, but only after ONE code from the new secret verifies.

    Without this an enrolment typo would enable 2FA against a secret the user's
    phone does not hold, locking them out at the next login.
    """
    if not verify_totp_code(user_id, code):
        return False
    from models.database import get_db
    conn = get_db()
    with conn:
        conn.execute(
            "UPDATE users SET totp_enabled=1, totp_confirmed_at=? WHERE id=?",
            (datetime.utcnow().isoformat(timespec="seconds"), user_id))
    conn.close()
    return True


def disable_totp(user_id) -> None:
    """Turn 2FA off and destroy the secret and every backup code."""
    _ensure_totp_schema()
    from models.database import get_db
    conn = get_db()
    with conn:
        conn.execute(
            "UPDATE users SET totp_secret=NULL, totp_enabled=0, "
            "totp_confirmed_at=NULL, last_totp_counter=0 WHERE id=?", (user_id,))
        conn.execute("DELETE FROM totp_backup_codes WHERE user_id=?", (user_id,))
    conn.close()


def list_totp_users() -> list:
    """Every active user with their 2FA state — for the admin reset screen."""
    _ensure_totp_schema()
    from models.database import get_db
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, username, full_name, role, totp_enabled, totp_confirmed_at "
            "FROM users WHERE is_active=1 ORDER BY username").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Backup codes ─────────────────────────────────────────────────────────────

def generate_backup_codes(user_id) -> list:
    """Replace this user's backup codes. Returns the plaintext ONCE."""
    import bcrypt
    _ensure_totp_schema()
    from models.database import get_db
    codes = [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}"
             for _ in range(BACKUP_CODE_COUNT)]
    now = datetime.utcnow().isoformat(timespec="seconds")
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM totp_backup_codes WHERE user_id=?", (user_id,))
        for code in codes:
            conn.execute(
                "INSERT INTO totp_backup_codes(user_id, code_hash, created_at) "
                "VALUES(?,?,?)",
                (user_id,
                 bcrypt.hashpw(code.encode(),
                               bcrypt.gensalt(rounds=_BACKUP_CODE_ROUNDS)).decode(),
                 now))
    conn.close()
    return codes


def count_backup_codes(user_id) -> int:
    _ensure_totp_schema()
    from models.database import get_db
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM totp_backup_codes "
            "WHERE user_id=? AND used_at IS NULL", (user_id,)).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def consume_backup_code(user_id, code: str) -> bool:
    """Spend one backup code. Single use — the UPDATE is the atomic gate."""
    import bcrypt
    _ensure_totp_schema()
    from models.database import get_db
    code = (code or "").strip().lower().replace(" ", "")
    if not code:
        return False
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT id, code_hash FROM totp_backup_codes "
            "WHERE user_id=? AND used_at IS NULL", (user_id,)).fetchall()
        matched = None
        for r in rows:
            stored = r["code_hash"]
            try:
                calc = bcrypt.hashpw(code.encode(), stored.encode()).decode()
            except (ValueError, TypeError) as exc:
                logger.error("Malformed backup-code hash id=%s for user %s (%s) "
                             "— skipping it", r["id"], user_id, exc)
                continue
            if secrets.compare_digest(calc, stored):
                matched = r["id"]
                break
        if matched is None:
            return False
        # AND used_at IS NULL makes the spend atomic: two concurrent requests
        # with the same code cannot both see rowcount == 1.
        cur = conn.execute(
            "UPDATE totp_backup_codes SET used_at=? WHERE id=? AND used_at IS NULL",
            (datetime.utcnow().isoformat(timespec="seconds"), matched))
        conn.commit()
        return cur.rowcount == 1
    finally:
        conn.close()


# ── Enrolment presentation ───────────────────────────────────────────────────

def totp_provisioning_uri(secret: str, username: str, issuer: str = "Aleefy") -> str:
    if pyotp is None or not secret:
        return ""
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def totp_qr_data_uri(uri: str) -> str:
    """PNG data: URI for `uri`, or "" — callers always also show the text secret."""
    if qrcode is None or not uri:
        return ""
    try:
        buf = io.BytesIO()
        qrcode.make(uri).save(buf, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        logger.warning("Could not render the TOTP QR code (%s) — the user can "
                       "still type the secret in manually", exc)
        return ""
