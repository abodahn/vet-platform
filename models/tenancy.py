# -*- coding: utf-8 -*-
"""Multi-tenancy: one deployment, many clinics.

WHY DATABASE-PER-TENANT AND NOT A clinic_id COLUMN
--------------------------------------------------
The alternative was a `clinic_id` on all 74 tables plus a WHERE clause on all
400-odd queries. That was rejected on safety, not on effort. With row-level
tenancy every single query is a place where forgetting one clause silently
shows one clinic another clinic's patients, prescriptions and invoices — and
the code still returns 200, which is exactly the failure mode this codebase has
produced over and over. There is no test that proves 400 queries all remembered.

Giving each clinic its own database makes the isolation physical. A missing
WHERE cannot cross a database boundary, because there is no connection to the
other clinic's data to cross. The whole existing query layer keeps working
untouched, and `models/backup.py` — which already operates on one database —
becomes a per-clinic backup for free.

The cost is honest and bounded: schema migrations run once per tenant, and any
cross-tenant report is a loop. For a clinic SaaS in the tens-to-hundreds of
tenants that is the right trade. Past a few thousand, move to one Postgres
cluster with a schema per tenant — the resolution logic here does not change,
only `_connect()`.

RESOLUTION ORDER
----------------
    1. PLATFORM_TENANT env var      — scripts, cron, single-tenant deploys
    2. X-Tenant request header      — internal calls and tests
    3. host subdomain               — nilevet.aleefy.online -> "nilevet"
    4. nothing                      — legacy single-database mode, unchanged

Step 4 is what keeps this backwards compatible. A deployment that never
provisions a tenant behaves exactly as it did before this module existed,
which is why the existing suite still passes untouched.
"""
import os
import re
import sqlite3
import threading
from contextlib import contextmanager

logger = __import__("logging").getLogger(__name__)

try:
    from flask import g as _flask_g, has_app_context, request
except Exception:                                    # pragma: no cover
    _flask_g = None
    has_app_context = lambda: False                  # noqa: E731
    request = None

_G_KEY = "_tenant"

# Slugs become filenames and PostgreSQL database names, so they are restricted
# rather than escaped. Anything outside this set is rejected at provisioning
# time, which is the only place a slug enters the system.
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])$")

# Hosts that are never a tenant subdomain. "www.aleefy.online" is the marketing
# site, not a clinic called www.
_RESERVED = frozenset({
    "www", "app", "api", "admin", "static", "cdn", "mail", "localhost",
})

_registry_path: str = ""
_lock = threading.RLock()

_DDL = """
CREATE TABLE IF NOT EXISTS tenants (
    slug        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    db_path     TEXT,
    pg_dsn      TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
)
"""


def configure(registry_path: str) -> None:
    """Point the registry at a file. Called once from create_app()."""
    global _registry_path
    with _lock:
        _registry_path = registry_path
        if registry_path:
            os.makedirs(os.path.dirname(registry_path) or ".", exist_ok=True)


def enabled() -> bool:
    """True once at least one tenant is registered.

    Deliberately not "is a registry file configured": a fresh install has a
    configured path and no tenants, and must keep behaving as a single clinic.
    """
    if not _registry_path or not os.path.exists(_registry_path):
        return False
    try:
        with _registry() as conn:
            return conn.execute(
                "SELECT 1 FROM tenants WHERE status='active' LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False


def _registry():
    """Connection to the registry itself — a plain sqlite3, never a tenant DB.

    The registry is control-plane data: a few rows, read-mostly. Keeping it in
    SQLite means it works identically whether the clinics are on SQLite or
    PostgreSQL, and it cannot accidentally be routed to a tenant's database.
    """
    conn = sqlite3.connect(_registry_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(_DDL)
    return conn


# ── resolution ────────────────────────────────────────────────────────────────

_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def slug_from_host(host: str) -> str:
    """'nilevet.aleefy.online:5100' -> 'nilevet'. Empty when there is none."""
    if not host:
        return ""
    host = host.strip().lower().rstrip(".")
    # IPv6 arrives bracketed: "[::1]:5100".
    if host.startswith("["):
        return ""
    host = host.split(":")[0]
    # An IP address is not a subdomain. Without this, 127.0.0.1 resolves to a
    # tenant called "127" — so every health check, load-balancer probe and
    # direct-to-container request would 404, and a tenant named "10" would
    # capture traffic aimed at a private-range address.
    if _IPV4_RE.match(host):
        return ""
    parts = host.split(".")
    # Needs a real subdomain: sub.domain.tld. "aleefy.online" has none, and
    # bare "localhost" must never be read as a tenant name.
    if len(parts) < 3 or parts[0] in _RESERVED:
        return ""
    return parts[0] if _SLUG_RE.match(parts[0]) else ""


def resolve() -> str:
    """The tenant slug for the current request, or "" for legacy mode."""
    env = os.environ.get("PLATFORM_TENANT", "").strip().lower()
    if env:
        return env
    if request is None or not has_app_context():
        return ""
    try:
        header = (request.headers.get("X-Tenant") or "").strip().lower()
        if header:
            return header
        return slug_from_host(request.host)
    except Exception:
        # Outside a request context (scheduler, CLI) there is no host to read.
        return ""


# Thread-local override, checked ahead of the request. Provisioning, the
# nightly scheduler and the backup job all need to act as a specific clinic
# with no request in sight, and a thread-local is the only thing that works
# identically inside a request, inside a worker thread and in a CLI script.
_override = threading.local()


@contextmanager
def use(slug: str):
    """Run a block as a given clinic.

        with tenancy.use("nilevet"):
            db.get_db()            # -> nilevet's database

    Restores the previous value on the way out, including on exception, so a
    failure mid-provisioning cannot leave a worker thread permanently pinned
    to somebody else's database.
    """
    prev = getattr(_override, "slug", None)
    _override.slug = (slug or "").strip().lower()
    try:
        yield
    finally:
        _override.slug = prev


def current() -> str:
    """Resolved tenant for this request, cached on `g` for the request's life.

    Cached because _connect() may be called many times per request and each
    call would otherwise re-parse the host.
    """
    override = getattr(_override, "slug", None)
    if override is not None:
        return override
    if _flask_g is None or not has_app_context():
        return resolve()
    slug = getattr(_flask_g, _G_KEY, None)
    if slug is None:
        slug = resolve()
        setattr(_flask_g, _G_KEY, slug)
    return slug


# ── registry reads ────────────────────────────────────────────────────────────

def get(slug: str) -> dict:
    slug = (slug or "").strip().lower()
    if not slug or not _registry_path or not os.path.exists(_registry_path):
        return {}
    with _registry() as conn:
        row = conn.execute("SELECT * FROM tenants WHERE slug=?", (slug,)).fetchone()
    return dict(row) if row else {}


def all_tenants(active_only: bool = True) -> list:
    """Every registered clinic. The scheduler loops over this."""
    if not _registry_path or not os.path.exists(_registry_path):
        return []
    sql = "SELECT * FROM tenants"
    if active_only:
        sql += " WHERE status='active'"
    with _registry() as conn:
        return [dict(r) for r in conn.execute(sql + " ORDER BY slug").fetchall()]


def target(slug: str = None) -> dict:
    """Where the given tenant's data lives: {'db_path':...} or {'pg_dsn':...}.

    Empty dict means legacy mode — the caller uses its configured default.
    """
    slug = current() if slug is None else slug
    if not slug:
        return {}
    row = get(slug)
    if not row:
        # An unknown subdomain must NOT fall through to the default database:
        # that would serve one clinic's records under another clinic's name.
        raise UnknownTenant(slug)
    if row.get("status") != "active":
        raise TenantSuspended(slug)
    return {k: row[k] for k in ("db_path", "pg_dsn") if row.get(k)}


class UnknownTenant(Exception):
    """No clinic is registered under this subdomain."""


class TenantSuspended(Exception):
    """Registered but not active — unpaid, or being migrated."""


# ── provisioning ──────────────────────────────────────────────────────────────

def create(slug: str, name: str, *, db_dir: str = "", pg_dsn: str = "") -> dict:
    """Register a clinic and return its row. Does NOT build the schema —
    provision() in models/provisioning.py does that, so this stays a pure
    registry write that a test can use on its own.
    """
    slug = (slug or "").strip().lower()
    if not _SLUG_RE.match(slug):
        raise ValueError(
            f"invalid slug {slug!r}: 3-32 chars, lowercase letters, digits and "
            "hyphens, not starting or ending with a hyphen")
    if slug in _RESERVED:
        raise ValueError(f"{slug!r} is reserved")
    if not (name or "").strip():
        raise ValueError("a clinic name is required")
    if not _registry_path:
        raise RuntimeError("tenancy.configure() has not been called")

    db_path = "" if pg_dsn else os.path.join(db_dir, f"{slug}.db")
    with _lock, _registry() as conn:
        if conn.execute("SELECT 1 FROM tenants WHERE slug=?", (slug,)).fetchone():
            raise ValueError(f"tenant {slug!r} already exists")
        conn.execute(
            "INSERT INTO tenants(slug, name, db_path, pg_dsn) VALUES(?,?,?,?)",
            (slug, name.strip(), db_path, pg_dsn))
        conn.commit()
    logger.info("tenant registered: %s (%s)", slug, name)
    return get(slug)


def set_status(slug: str, status: str) -> None:
    if status not in ("active", "suspended"):
        raise ValueError("status must be 'active' or 'suspended'")
    with _lock, _registry() as conn:
        conn.execute("UPDATE tenants SET status=? WHERE slug=?", (status, slug))
        conn.commit()
