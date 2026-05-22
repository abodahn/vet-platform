"""
Aleefy — Complete Platform Database
All 55 tables covering every module.  PostgreSQL backend.

Connection strategy
───────────────────
PostgreSQL connections are served from a ThreadedConnectionPool (min=2, max=20).
Every get_db() call checks out a connection; every close() / __exit__ returns it.
This eliminates the ~5-10 ms TCP handshake overhead that previously occurred on
every single HTTP request and lets the app sustain concurrent load without
exhausting PostgreSQL's connection limit.

Cache strategy
──────────────
Hot read-only data (clinic settings, service catalog prices) is served from an
in-process TTL cache (default 5 min) via _cached_query().  Cache is invalidated
explicitly when those tables are mutated.
"""

import sqlite3, hashlib, os, re, threading, time, logging
import bcrypt as _bcrypt
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

_db_path: str = ""

# ── PostgreSQL connection pool ─────────────────────────────────
_PG_CONFIG: dict = {}
_POOL = None          # psycopg2.pool.ThreadedConnectionPool once configured
_POOL_LOCK = threading.Lock()

# ── In-process TTL cache ───────────────────────────────────────
# { key: (value, expires_at) }
_CACHE: dict = {}
_CACHE_LOCK = threading.Lock()

def _cache_get(key: str):
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0], True
        return None, False

def _cache_set(key: str, value, ttl: int = 300):
    with _CACHE_LOCK:
        _CACHE[key] = (value, time.monotonic() + ttl)

def cache_invalidate(key: str):
    """Call after mutating a cached table so next read is fresh."""
    with _CACHE_LOCK:
        _CACHE.pop(key, None)


def configure_postgres(host="localhost", port=5432, dbname="vetclinic",
                       user="postgres", password="1234",
                       min_conn: int = 2, max_conn: int = 20):
    """Call once at startup to configure the PostgreSQL connection pool.

    Parameters
    ----------
    min_conn : int
        Minimum connections kept alive in the pool (default 2).
    max_conn : int
        Maximum simultaneous connections (default 20).  Raise if you expect
        more than ~15 concurrent Gunicorn workers.
    """
    global _PG_CONFIG, _POOL
    _PG_CONFIG = dict(host=host, port=port, dbname=dbname,
                      user=user, password=password)
    try:
        from psycopg2.pool import ThreadedConnectionPool
        _POOL = ThreadedConnectionPool(min_conn, max_conn, **_PG_CONFIG)
        logger.info(
            "PostgreSQL pool ready — min=%d max=%d  (%s@%s/%s)",
            min_conn, max_conn, user, host, dbname,
        )
    except Exception as exc:
        logger.warning("Could not create PG pool (%s) — falling back to per-request connect", exc)
        _POOL = None


def set_path(path: str) -> None:
    global _db_path
    _db_path = path


# ─────────────────────────────────────────────────────────────────
# PostgreSQL compatibility wrapper
# Makes psycopg2 behave like sqlite3 for all existing query code.
# ─────────────────────────────────────────────────────────────────

_FIX_CACHE: dict = {}


def _fix_sql(sql: str) -> str:
    """Translate SQLite SQL quirks to PostgreSQL."""
    if sql in _FIX_CACHE:
        return _FIX_CACHE[sql]
    s = sql
    # ? -> %s placeholders
    s = s.replace("?", "%s")
    # SQLite datetime function -> PostgreSQL NOW()
    s = s.replace("datetime('now')", "NOW()")
    # SQLite AUTOINCREMENT primary key -> PostgreSQL SERIAL
    s = re.sub(r'\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', 'SERIAL PRIMARY KEY', s, flags=re.IGNORECASE)
    # TEXT DEFAULT (NOW()) -> TEXT DEFAULT (NOW()::TEXT)  keeps column as TEXT
    # while providing a valid PostgreSQL default expression
    s = re.sub(r'\bTEXT(\s+DEFAULT\s+\(NOW\(\)\))', r"TEXT\1::TEXT", s, flags=re.IGNORECASE)
    # INSERT OR IGNORE -> INSERT ... ON CONFLICT DO NOTHING
    has_ignore = bool(re.search(r'\bINSERT\s+OR\s+IGNORE\b', s, re.IGNORECASE))
    if has_ignore:
        s = re.sub(r'\bINSERT\s+OR\s+IGNORE\b', 'INSERT', s, flags=re.IGNORECASE)
        s = s.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    # INSERT OR REPLACE -> INSERT ... ON CONFLICT DO NOTHING (simplified)
    has_replace = bool(re.search(r'\bINSERT\s+OR\s+REPLACE\b', s, re.IGNORECASE))
    if has_replace:
        s = re.sub(r'\bINSERT\s+OR\s+REPLACE\b', 'INSERT', s, flags=re.IGNORECASE)
        s = s.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    _FIX_CACHE[sql] = s
    return s


class _PGCursor:
    """Wraps psycopg2 DictCursor to behave like sqlite3.Cursor.

    Key design: savepoint management uses a *separate* admin cursor so that
    SAVEPOINT/RELEASE statements never overwrite the main cursor's result set.
    """

    def __init__(self, raw_cur, raw_conn):
        self._cur = raw_cur
        self._raw_conn = raw_conn
        self.lastrowid = None
        self.rowcount = 0
        self._sp_seq = 0

    def _new_sp(self) -> str:
        self._sp_seq += 1
        return f"pgsp{abs(id(self)) % 999999}_{self._sp_seq}"

    def _admin(self):
        """Fresh plain cursor for savepoint management (no DictCursor needed)."""
        return self._raw_conn.cursor()

    @staticmethod
    def _clean_params(params):
        """Strip NUL bytes from string parameters — psycopg2 rejects them."""
        if not params:
            return params
        cleaned = []
        for p in params:
            cleaned.append(p.replace('\x00', '') if isinstance(p, str) else p)
        return type(params)(cleaned) if isinstance(params, tuple) else cleaned

    def execute(self, sql, params=()):
        fixed = _fix_sql(sql)
        params = self._clean_params(params)
        is_insert = fixed.strip().upper().startswith('INSERT')

        adm = self._admin()
        sp = self._new_sp()
        adm.execute(f'SAVEPOINT {sp}')

        try:
            # For INSERT, try appending RETURNING id to capture lastrowid
            if is_insert and 'RETURNING' not in fixed.upper():
                sp2 = self._new_sp()
                adm.execute(f'SAVEPOINT {sp2}')
                try:
                    self._cur.execute(
                        fixed.rstrip().rstrip(';') + ' RETURNING id',
                        params or ()
                    )
                    row = self._cur.fetchone()
                    self.lastrowid = row[0] if row else None
                    self.rowcount = self._cur.rowcount
                    adm.execute(f'RELEASE SAVEPOINT {sp2}')
                    adm.execute(f'RELEASE SAVEPOINT {sp}')
                    adm.close()
                    return self
                except Exception:
                    adm.execute(f'ROLLBACK TO SAVEPOINT {sp2}')
                    # fall through to plain execute below

            # Plain execute
            self._cur.execute(fixed, params or ())
            self.rowcount = self._cur.rowcount
            adm.execute(f'RELEASE SAVEPOINT {sp}')

        except Exception as exc:
            try:
                adm.execute(f'ROLLBACK TO SAVEPOINT {sp}')
            except Exception:
                pass
            adm.close()
            raise exc

        adm.close()
        return self

    def executemany(self, sql, params_list):
        fixed = _fix_sql(sql)
        adm = self._admin()
        sp = self._new_sp()
        adm.execute(f'SAVEPOINT {sp}')
        try:
            self._cur.executemany(fixed, params_list)
            self.rowcount = self._cur.rowcount
            adm.execute(f'RELEASE SAVEPOINT {sp}')
        except Exception as exc:
            try:
                adm.execute(f'ROLLBACK TO SAVEPOINT {sp}')
            except Exception:
                pass
            adm.close()
            raise exc
        adm.close()
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __iter__(self):
        return iter(self._cur)

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass


class _PGConn:
    """Wraps a psycopg2 connection to behave like sqlite3.Connection.

    When constructed with a *pool* reference, close() returns the underlying
    connection back to the pool (after a safety rollback) instead of closing
    it — keeping the TCP socket alive for the next request.
    """

    def __init__(self, raw_conn, pool=None):
        import psycopg2.extras
        self._conn = raw_conn
        self._pool = pool
        self._conn.autocommit = False
        self._dict_factory = psycopg2.extras.DictCursor

    def cursor(self):
        return _PGCursor(
            self._conn.cursor(cursor_factory=self._dict_factory),
            self._conn
        )

    def execute(self, sql, params=()):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, params_list):
        cur = self.cursor()
        cur.executemany(sql, params_list)
        return cur

    def executescript(self, script):
        """Execute multi-statement DDL script against PostgreSQL.

        Splits on semicolons, translates SQLite syntax via _fix_sql, and runs
        each statement. Failures on individual statements are silently ignored
        so that IF NOT EXISTS and idempotent DDL work correctly on re-runs.
        """
        import re
        # Strip SQL line comments so they don't interfere with splitting
        cleaned = re.sub(r'--[^\n]*', '', script)
        stmts = cleaned.split(';')
        for stmt in stmts:
            stmt = stmt.strip()
            if not stmt:
                continue
            try:
                self.execute(stmt)
            except Exception:
                pass  # IF NOT EXISTS handles duplicates; savepoints keep tx alive

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        """Return connection to the pool (if pooled) or close it."""
        try:
            if self._pool is not None:
                # Must be in a clean state before returning to pool.
                # A rollback is safe even if nothing is open.
                try:
                    self._conn.rollback()
                except Exception:
                    pass
                self._pool.putconn(self._conn)
            else:
                self._conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *args):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


def get_db():
    """Check out a connection from the pool (or open a fresh one if pooling
    is unavailable) and return it wrapped as a sqlite3-compatible object.

    Always pair with conn.close() or use as a context manager (with conn:).
    """
    if _POOL is not None:
        # Fast path: get from pool (no TCP handshake)
        raw = _POOL.getconn()
        return _PGConn(raw, pool=_POOL)

    if _PG_CONFIG:
        # Pool not ready yet (race at startup) — open a direct connection
        import psycopg2
        raw = psycopg2.connect(**_PG_CONFIG)
        return _PGConn(raw, pool=None)

    # Fallback: SQLite (dev / test mode)
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


# ════════════════════════════════════════════════════════════════
# SCHEMA — ALL 55 TABLES
# ════════════════════════════════════════════════════════════════

_SCHEMA = """
-- ── CORE ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clinic (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL DEFAULT 'Aleefy',
    name_ar     TEXT DEFAULT 'اليفي',
    phone       TEXT, email TEXT, address TEXT, address_ar TEXT,
    website     TEXT, tax_number TEXT, license_number TEXT,
    doctor_name TEXT DEFAULT 'Lead Veterinarian',
    tagline     TEXT DEFAULT 'Happy Pets, Healthy Lives',
    logo_data   TEXT,
    currency    TEXT DEFAULT 'EGP',
    timezone    TEXT DEFAULT 'Africa/Cairo',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS branches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   INTEGER DEFAULT 1,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    phone       TEXT, address TEXT,
    manager_id  INTEGER,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER DEFAULT 1,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    head_id     INTEGER,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT UNIQUE NOT NULL,
    password_hash    TEXT NOT NULL,
    full_name        TEXT,
    full_name_ar     TEXT,
    email            TEXT,
    phone            TEXT,
    role             TEXT NOT NULL DEFAULT 'staff',
    department_id    INTEGER,
    branch_id        INTEGER DEFAULT 1,
    is_active        INTEGER DEFAULT 1,
    theme_preference TEXT DEFAULT 'medical',
    language         TEXT DEFAULT 'en',
    last_login_at    TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS roles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT UNIQUE NOT NULL,
    display_name     TEXT,
    display_name_ar  TEXT,
    permissions_json TEXT DEFAULT '[]',
    color            TEXT DEFAULT '#1a3a6b',
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    user_id     INTEGER,
    username    TEXT, role TEXT, action TEXT, module TEXT,
    entity_type TEXT, entity_id TEXT, details TEXT,
    ip TEXT, user_agent TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    category   TEXT DEFAULT 'general',
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token TEXT UNIQUE,
    user_id       INTEGER,
    username      TEXT, role TEXT, ip TEXT, user_agent TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    last_seen_at  TEXT DEFAULT (datetime('now')),
    ended_at      TEXT
);

-- ── CRM ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS owners (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name         TEXT NOT NULL,
    full_name_ar      TEXT,
    phone             TEXT,
    whatsapp_phone    TEXT,
    email             TEXT,
    address           TEXT,
    address_ar        TEXT,
    preferred_contact TEXT DEFAULT 'WhatsApp',
    preferred_doctor  TEXT,
    preferred_branch  INTEGER DEFAULT 1,
    vip_flag          INTEGER DEFAULT 0,
    outstanding_balance REAL DEFAULT 0.0,
    marketing_consent INTEGER DEFAULT 1,
    notes             TEXT,
    created_by        TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS owner_phones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    phone       TEXT NOT NULL,
    label       TEXT DEFAULT 'Mobile',
    is_whatsapp INTEGER DEFAULT 0,
    is_primary  INTEGER DEFAULT 0,
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id            INTEGER NOT NULL,
    pet_name            TEXT NOT NULL,
    species             TEXT,
    breed               TEXT,
    sex                 TEXT DEFAULT 'Unknown',
    dob                 TEXT,
    weight_kg           REAL,
    color               TEXT,
    microchip_id        TEXT,
    neutered            INTEGER DEFAULT 0,
    allergies           TEXT,
    chronic_conditions  TEXT,
    diet_notes          TEXT,
    insurance_number    TEXT,
    notes               TEXT,
    is_active           INTEGER DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pet_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id      INTEGER NOT NULL,
    filename    TEXT, filetype TEXT, filedata TEXT,
    caption     TEXT,
    uploaded_by TEXT,
    uploaded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
);

-- ── APPOINTMENTS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id         INTEGER NOT NULL,
    pet_id           INTEGER NOT NULL,
    branch_id        INTEGER DEFAULT 1,
    doctor_id        INTEGER,
    doctor_name      TEXT,
    room             TEXT,
    appointment_type TEXT DEFAULT 'Consultation',
    priority         TEXT DEFAULT 'Normal',
    status           TEXT DEFAULT 'Scheduled',
    channel          TEXT DEFAULT 'Walk-in',
    appt_date        TEXT NOT NULL,
    appt_start       TEXT NOT NULL,
    appt_end         TEXT,
    duration_min     INTEGER DEFAULT 30,
    reason           TEXT,
    symptoms         TEXT,
    notes            TEXT,
    confirmed        INTEGER DEFAULT 0,
    reminder_sent    INTEGER DEFAULT 0,
    checked_in_at    TEXT,
    checked_out_at   TEXT,
    created_by       TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id),
    FOREIGN KEY (pet_id)   REFERENCES pets(id)
);

-- ── MEDICAL RECORDS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS visits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER,
    owner_id        INTEGER NOT NULL,
    pet_id          INTEGER NOT NULL,
    doctor_id       INTEGER,
    doctor_name     TEXT,
    branch_id       INTEGER DEFAULT 1,
    room            TEXT,
    visit_date      TEXT NOT NULL,
    visit_type      TEXT DEFAULT 'Consultation',
    status          TEXT DEFAULT 'Open',
    chief_complaint TEXT,
    symptoms        TEXT,
    weight_kg       REAL,
    temp_c          REAL,
    heart_rate      INTEGER,
    respiratory_rate INTEGER,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id),
    FOREIGN KEY (pet_id)   REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER NOT NULL,
    pet_id      INTEGER NOT NULL,
    diagnosis   TEXT NOT NULL,
    diagnosis_code TEXT,
    severity    TEXT DEFAULT 'Moderate',
    is_chronic  INTEGER DEFAULT 0,
    notes       TEXT,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE,
    FOREIGN KEY (pet_id)   REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS treatment_plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER NOT NULL,
    pet_id      INTEGER NOT NULL,
    plan_text   TEXT NOT NULL,
    goals       TEXT,
    duration    TEXT,
    followup_in INTEGER,
    followup_unit TEXT DEFAULT 'days',
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id       INTEGER NOT NULL,
    pet_id         INTEGER NOT NULL,
    owner_id       INTEGER NOT NULL,
    prescribed_by  TEXT,
    status         TEXT DEFAULT 'Active',
    notes          TEXT,
    dispensed_at   TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL,
    item_id         INTEGER,
    medication_name TEXT NOT NULL,
    dosage          TEXT,
    frequency       TEXT,
    duration        TEXT,
    route           TEXT DEFAULT 'Oral',
    quantity        REAL DEFAULT 1,
    unit            TEXT DEFAULT 'tablet',
    instructions    TEXT,
    dispensed       INTEGER DEFAULT 0,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER NOT NULL,
    pet_id      INTEGER NOT NULL,
    test_name   TEXT NOT NULL,
    test_code   TEXT,
    priority    TEXT DEFAULT 'Routine',
    status      TEXT DEFAULT 'Pending',
    sample_type TEXT,
    collected_at TEXT,
    notes       TEXT,
    requested_by TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_request_id  INTEGER NOT NULL,
    pet_id          INTEGER NOT NULL,
    result_text     TEXT,
    result_value    REAL,
    unit            TEXT,
    reference_range TEXT,
    is_abnormal     INTEGER DEFAULT 0,
    reviewed_by     TEXT,
    reviewed_at     TEXT,
    report_data     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (lab_request_id) REFERENCES lab_requests(id)
);

CREATE TABLE IF NOT EXISTS vaccinations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id          INTEGER NOT NULL,
    visit_id        INTEGER,
    vaccine_name    TEXT NOT NULL,
    vaccine_brand   TEXT,
    batch_number    TEXT,
    dose_number     INTEGER DEFAULT 1,
    administered_by TEXT,
    administered_at TEXT NOT NULL,
    next_due_at     TEXT,
    site            TEXT DEFAULT 'Subcutaneous',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS surgeries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id          INTEGER NOT NULL,
    visit_id        INTEGER,
    procedure_name  TEXT NOT NULL,
    surgeon         TEXT,
    anesthetist     TEXT,
    surgery_date    TEXT NOT NULL,
    duration_min    INTEGER,
    anesthesia_type TEXT,
    pre_op_notes    TEXT,
    intra_op_notes  TEXT,
    post_op_notes   TEXT,
    outcome         TEXT DEFAULT 'Successful',
    followup_date   TEXT,
    consent_given   INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS followups (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id     INTEGER,
    pet_id       INTEGER NOT NULL,
    owner_id     INTEGER NOT NULL,
    due_date     TEXT NOT NULL,
    reason       TEXT,
    status       TEXT DEFAULT 'Pending',
    reminder_sent INTEGER DEFAULT 0,
    completed_at TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

-- ── INVENTORY ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS item_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    name_ar     TEXT,
    parent_id   INTEGER,
    description TEXT,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER,
    sku             TEXT UNIQUE,
    barcode         TEXT,
    name            TEXT NOT NULL,
    name_ar         TEXT,
    description     TEXT,
    unit            TEXT DEFAULT 'unit',
    cost_price      REAL DEFAULT 0.0,
    sell_price      REAL DEFAULT 0.0,
    reorder_level   REAL DEFAULT 10.0,
    max_stock       REAL DEFAULT 1000.0,
    is_medication   INTEGER DEFAULT 0,
    is_controlled   INTEGER DEFAULT 0,
    requires_rx     INTEGER DEFAULT 0,
    supplier_id     INTEGER,
    storage_notes   TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES item_categories(id)
);

CREATE TABLE IF NOT EXISTS warehouses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER DEFAULT 1,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    description TEXT,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS batches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER NOT NULL,
    warehouse_id   INTEGER DEFAULT 1,
    batch_number   TEXT,
    lot_number     TEXT,
    manufacture_date TEXT,
    expiry_date    TEXT,
    quantity       REAL DEFAULT 0.0,
    unit_cost      REAL DEFAULT 0.0,
    received_at    TEXT DEFAULT (datetime('now')),
    received_by    TEXT,
    notes          TEXT,
    FOREIGN KEY (item_id)      REFERENCES items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL,
    batch_id        INTEGER,
    warehouse_id    INTEGER DEFAULT 1,
    movement_type   TEXT NOT NULL,  -- in/out/adjustment/transfer/expired/damaged
    quantity        REAL NOT NULL,
    unit_cost       REAL DEFAULT 0.0,
    reference_type  TEXT,           -- visit/purchase/adjustment/etc.
    reference_id    INTEGER,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS reorder_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL UNIQUE,
    reorder_point   REAL DEFAULT 10.0,
    reorder_qty     REAL DEFAULT 50.0,
    preferred_supplier_id INTEGER,
    auto_suggest    INTEGER DEFAULT 1,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- ── PHARMACY ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dosage_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL,
    species     TEXT DEFAULT 'All',
    dosage      TEXT NOT NULL,
    frequency   TEXT,
    route       TEXT DEFAULT 'Oral',
    notes       TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS dispensing_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_item_id INTEGER,
    item_id             INTEGER NOT NULL,
    batch_id            INTEGER,
    visit_id            INTEGER,
    pet_id              INTEGER,
    quantity            REAL NOT NULL,
    dispensed_by        TEXT,
    dispensed_at        TEXT DEFAULT (datetime('now')),
    notes               TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- ── FINANCE ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number  TEXT UNIQUE NOT NULL,
    owner_id        INTEGER NOT NULL,
    pet_id          INTEGER,
    visit_id        INTEGER,
    branch_id       INTEGER DEFAULT 1,
    doctor_name     TEXT,
    issue_date      TEXT NOT NULL,
    due_date        TEXT,
    status          TEXT DEFAULT 'Unpaid',   -- Unpaid/Paid/Partial/Cancelled
    subtotal        REAL DEFAULT 0.0,
    discount_type   TEXT DEFAULT 'value',
    discount_value  REAL DEFAULT 0.0,
    discount_amount REAL DEFAULT 0.0,
    tax_rate        REAL DEFAULT 0.0,
    tax_amount      REAL DEFAULT 0.0,
    total           REAL DEFAULT 0.0,
    paid_amount     REAL DEFAULT 0.0,
    due_amount      REAL DEFAULT 0.0,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   INTEGER NOT NULL,
    line_type    TEXT DEFAULT 'service',  -- service/product/medication
    item_id      INTEGER,
    description  TEXT NOT NULL,
    quantity     REAL DEFAULT 1.0,
    unit_price   REAL DEFAULT 0.0,
    discount     REAL DEFAULT 0.0,
    total        REAL DEFAULT 0.0,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id     INTEGER NOT NULL,
    owner_id       INTEGER NOT NULL,
    amount         REAL NOT NULL,
    method         TEXT DEFAULT 'Cash',   -- Cash/Card/Transfer/Insurance
    channel        TEXT DEFAULT 'Cash',   -- Cash/Visa/Instapay
    reference      TEXT,
    notes          TEXT,
    received_by    TEXT,
    received_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (owner_id)   REFERENCES owners(id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER DEFAULT 1,
    category     TEXT,
    description  TEXT NOT NULL,
    amount       REAL NOT NULL,
    vendor       TEXT,
    receipt_ref  TEXT,
    expense_date TEXT NOT NULL,
    notes        TEXT,
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_closings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id       INTEGER DEFAULT 1,
    closing_date    TEXT NOT NULL,
    cash_sales      REAL DEFAULT 0.0,
    card_sales      REAL DEFAULT 0.0,
    transfer_sales  REAL DEFAULT 0.0,
    total_sales     REAL DEFAULT 0.0,
    total_expenses  REAL DEFAULT 0.0,
    net_revenue     REAL DEFAULT 0.0,
    opening_cash    REAL DEFAULT 0.0,
    closing_cash    REAL DEFAULT 0.0,
    notes           TEXT,
    closed_by       TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ── PROCUREMENT ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    name_ar      TEXT,
    contact_name TEXT,
    phone        TEXT,
    email        TEXT,
    address      TEXT,
    tax_number   TEXT,
    payment_terms TEXT DEFAULT 'Net 30',
    notes        TEXT,
    is_active    INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number    TEXT UNIQUE NOT NULL,
    supplier_id  INTEGER NOT NULL,
    branch_id    INTEGER DEFAULT 1,
    status       TEXT DEFAULT 'Draft',  -- Draft/Sent/Received/Cancelled
    order_date   TEXT NOT NULL,
    expected_date TEXT,
    received_date TEXT,
    subtotal     REAL DEFAULT 0.0,
    tax_amount   REAL DEFAULT 0.0,
    total        REAL DEFAULT 0.0,
    notes        TEXT,
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS po_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id        INTEGER NOT NULL,
    item_id      INTEGER NOT NULL,
    quantity     REAL NOT NULL,
    unit_cost    REAL DEFAULT 0.0,
    total        REAL DEFAULT 0.0,
    received_qty REAL DEFAULT 0.0,
    FOREIGN KEY (po_id)    REFERENCES purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)  REFERENCES items(id)
);

-- ── COMMUNICATIONS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id        INTEGER NOT NULL,
    pet_id          INTEGER,
    appointment_id  INTEGER,
    reminder_type   TEXT NOT NULL,  -- appointment/followup/vaccine/medication/custom
    message         TEXT,
    channel         TEXT DEFAULT 'WhatsApp',
    scheduled_for   TEXT NOT NULL,
    status          TEXT DEFAULT 'Pending',  -- Pending/Sent/Failed/Cancelled
    sent_at         TEXT,
    api_response    TEXT,
    retry_count     INTEGER DEFAULT 0,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

CREATE TABLE IF NOT EXISTS whatsapp_templates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT UNIQUE NOT NULL,
    scenario      TEXT,         -- appointment/followup/vaccine/invoice/custom
    language      TEXT DEFAULT 'en',
    template_text TEXT NOT NULL,
    variables_json TEXT DEFAULT '[]',
    is_active     INTEGER DEFAULT 1,
    is_default    INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS whatsapp_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id  INTEGER,
    owner_id     INTEGER,
    pet_id       INTEGER,
    phone        TEXT,
    message      TEXT,
    template_name TEXT,
    status       TEXT DEFAULT 'Pending',
    http_status  INTEGER,
    response     TEXT,
    error        TEXT,
    sent_at      TEXT DEFAULT (datetime('now'))
);

-- ── GROOMING ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grooming_services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    duration_min INTEGER DEFAULT 60,
    price       REAL DEFAULT 0.0,
    species     TEXT DEFAULT 'All',
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS grooming_bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id        INTEGER NOT NULL,
    owner_id      INTEGER NOT NULL,
    service_id    INTEGER,
    groomer_name  TEXT,
    booking_date  TEXT NOT NULL,
    status        TEXT DEFAULT 'Scheduled',
    notes         TEXT,
    before_photo  TEXT,
    after_photo   TEXT,
    invoice_id    INTEGER,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

-- ── BOARDING ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS boarding_rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    room_type   TEXT DEFAULT 'Standard',   -- Standard/Premium/ICU
    capacity    INTEGER DEFAULT 1,
    price_per_night REAL DEFAULT 0.0,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS boarding_bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id        INTEGER NOT NULL,
    owner_id      INTEGER NOT NULL,
    room_id       INTEGER,
    check_in      TEXT NOT NULL,
    check_out     TEXT,
    actual_checkout TEXT,
    status        TEXT DEFAULT 'Booked',
    feeding_instructions TEXT,
    medication_instructions TEXT,
    vet_notes     TEXT,
    invoice_id    INTEGER,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

-- ── SYSTEM ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    severity    TEXT DEFAULT 'INFO',
    module      TEXT,
    message     TEXT,
    details     TEXT,
    username    TEXT,
    ip          TEXT
);

CREATE TABLE IF NOT EXISTS diagnostic_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT DEFAULT (datetime('now')),
    run_by         TEXT,
    overall_status TEXT,
    passed         INTEGER DEFAULT 0,
    warnings       INTEGER DEFAULT 0,
    failed         INTEGER DEFAULT 0,
    summary        TEXT,
    details_json   TEXT
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    username    TEXT,
    role        TEXT,
    module      TEXT,
    context_type TEXT,   -- visit/pet/inventory/finance/etc.
    context_id  INTEGER,
    prompt      TEXT,
    response    TEXT,
    model_used  TEXT,
    tokens_used INTEGER,
    action_taken TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── ATTENDANCE & LEAVE MANAGEMENT ────────────────────────────
CREATE TABLE IF NOT EXISTS shifts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    name_ar       TEXT,
    start_time    TEXT NOT NULL DEFAULT '08:00',
    end_time      TEXT NOT NULL DEFAULT '17:00',
    break_minutes INTEGER DEFAULT 60,
    days_of_week  TEXT DEFAULT '1,2,3,4,5',
    color         TEXT DEFAULT '#3b82f6',
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS staff_shifts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    shift_id   INTEGER NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to   TEXT,
    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (shift_id) REFERENCES shifts(id)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    full_name       TEXT,
    work_date       TEXT NOT NULL,
    check_in        TEXT,
    check_out       TEXT,
    break_minutes   INTEGER DEFAULT 0,
    hours_worked    REAL DEFAULT 0,
    status          TEXT DEFAULT 'Present',
    notes           TEXT,
    recorded_by     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS leave_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    name_ar         TEXT,
    days_per_year   REAL DEFAULT 21,
    is_paid         INTEGER DEFAULT 1,
    requires_approval INTEGER DEFAULT 1,
    min_notice_days INTEGER DEFAULT 1,
    max_consecutive INTEGER DEFAULT 30,
    color           TEXT DEFAULT '#6366f1',
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    leave_type_id   INTEGER NOT NULL,
    year            INTEGER NOT NULL,
    allocated       REAL DEFAULT 0,
    used            REAL DEFAULT 0,
    pending         REAL DEFAULT 0,
    remaining       REAL DEFAULT 0,
    UNIQUE(user_id, leave_type_id, year),
    FOREIGN KEY (user_id)       REFERENCES users(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    full_name       TEXT,
    leave_type_id   INTEGER NOT NULL,
    leave_type_name TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    days_requested  REAL NOT NULL,
    reason          TEXT,
    status          TEXT DEFAULT 'Pending',
    approved_by     TEXT,
    approved_at     TEXT,
    rejection_reason TEXT,
    attachment_name TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)       REFERENCES users(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
);

CREATE TABLE IF NOT EXISTS public_holidays (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    holiday_date TEXT NOT NULL UNIQUE,
    is_recurring INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attendance_user ON attendance_records(user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(work_date);
CREATE INDEX IF NOT EXISTS idx_leave_user      ON leave_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_leave_dates     ON leave_requests(start_date, end_date);

-- ── INDEXES ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pets_owner         ON pets(owner_id);
CREATE INDEX IF NOT EXISTS idx_appts_date         ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS idx_appts_pet          ON appointments(pet_id);
CREATE INDEX IF NOT EXISTS idx_visits_pet         ON visits(pet_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_visit    ON diagnoses(visit_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_visit ON prescriptions(visit_id);
CREATE INDEX IF NOT EXISTS idx_stock_item         ON stock_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_stock_date         ON stock_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_invoices_owner     ON invoices(owner_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date      ON invoices(issue_date);
CREATE INDEX IF NOT EXISTS idx_payments_invoice   ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_reminders_date     ON reminders(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_batches_expiry     ON batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_owners_phone       ON owners(phone);
CREATE INDEX IF NOT EXISTS idx_owners_name        ON owners(full_name);

-- ── NOTIFICATIONS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    recipient_role TEXT,
    title        TEXT NOT NULL,
    body         TEXT,
    icon         TEXT DEFAULT '🔔',
    link         TEXT,
    module       TEXT,
    entity_type  TEXT,
    entity_id    INTEGER,
    is_read      INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (recipient_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient_id, is_read);

-- ── SERVICE / PRICE CATALOG ───────────────────────────────────
CREATE TABLE IF NOT EXISTS service_catalog (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT UNIQUE,
    name         TEXT NOT NULL,
    name_ar      TEXT,
    category     TEXT DEFAULT 'Consultation',
    description  TEXT,
    standard_price REAL DEFAULT 0,
    tax_rate     REAL DEFAULT 0,
    duration_min INTEGER DEFAULT 0,
    species      TEXT DEFAULT 'All',
    is_active    INTEGER DEFAULT 1,
    sort_order   INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_svc_category ON service_catalog(category, is_active);

-- ── REMINDER RUNS (deduplication) ─────────────────────────────
CREATE TABLE IF NOT EXISTS reminder_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type     TEXT NOT NULL,
    entity_id    INTEGER,
    entity_type  TEXT,
    status       TEXT DEFAULT 'sent',
    run_at       TEXT DEFAULT (datetime('now')),
    UNIQUE(run_type, entity_id, entity_type)
);

-- ── FILE ATTACHMENTS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type  TEXT NOT NULL,
    entity_id    INTEGER NOT NULL,
    filename     TEXT NOT NULL,
    original_name TEXT,
    mime_type    TEXT,
    size_bytes   INTEGER DEFAULT 0,
    category     TEXT DEFAULT 'general',
    caption      TEXT,
    uploaded_by  TEXT,
    uploaded_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_attach_entity ON attachments(entity_type, entity_id);

-- ── BUDGET TARGETS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL UNIQUE,
    monthly_egp REAL NOT NULL DEFAULT 0,
    updated_by  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- ── LOYALTY POINTS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loyalty_points (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    points      INTEGER NOT NULL,
    reason      TEXT,
    ref_type    TEXT DEFAULT 'manual',
    ref_id      INTEGER,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_loyalty_owner ON loyalty_points(owner_id);

-- ── INPATIENT / HOSPITALISATION ───────────────────────────────
CREATE TABLE IF NOT EXISTS inpatient_stays (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id          INTEGER NOT NULL,
    owner_id        INTEGER NOT NULL,
    visit_id        INTEGER,
    ward            TEXT DEFAULT 'General',
    cage_number     TEXT,
    admitted_by     INTEGER NOT NULL,
    reason          TEXT NOT NULL,
    diagnosis       TEXT,
    treatment_plan  TEXT,
    status          TEXT NOT NULL DEFAULT 'Admitted',
    admitted_at     TEXT DEFAULT (datetime('now')),
    expected_discharge DATE,
    discharged_at   TEXT,
    discharge_notes TEXT,
    daily_rate      NUMERIC(10,2) DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id),
    FOREIGN KEY (admitted_by) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_inpatient_pet    ON inpatient_stays(pet_id);
CREATE INDEX IF NOT EXISTS idx_inpatient_status ON inpatient_stays(status);

CREATE TABLE IF NOT EXISTS inpatient_rounds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stay_id     INTEGER NOT NULL,
    recorded_by INTEGER NOT NULL,
    round_time  TEXT DEFAULT (datetime('now')),
    temp_c      REAL,
    heart_rate  INTEGER,
    resp_rate   INTEGER,
    weight_kg   REAL,
    pain_score  INTEGER,
    food_intake TEXT,
    fluid_input REAL,
    fluid_output REAL,
    observations TEXT,
    treatment_given TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (stay_id) REFERENCES inpatient_stays(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inpatient_meds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stay_id     INTEGER NOT NULL,
    given_by    INTEGER,
    medication  TEXT NOT NULL,
    dose        TEXT,
    route       TEXT DEFAULT 'PO',
    given_at    TEXT DEFAULT (datetime('now')),
    notes       TEXT,
    FOREIGN KEY (stay_id) REFERENCES inpatient_stays(id) ON DELETE CASCADE
);
"""

# ── Seed data ──────────────────────────────────────────────────
_SEED_ROLES = [
    ("super_admin",    "Super Administrator",   "مدير النظام الأعلى",    "#dc2626"),
    ("clinic_owner",   "Clinic Owner",          "صاحب العيادة",           "#7c3aed"),
    ("branch_manager", "Branch Manager",        "مدير الفرع",             "#1d4ed8"),
    ("doctor",         "Doctor / Veterinarian", "طبيب بيطري",             "#0891b2"),
    ("nurse",          "Nurse / Technician",    "ممرض / تقني",            "#0d9488"),
    ("reception",      "Receptionist",          "موظف استقبال",           "#ca8a04"),
    ("inventory_mgr",  "Inventory Manager",     "مدير المخزون",           "#b45309"),
    ("pharmacist",     "Pharmacist",            "صيدلاني",                "#7c3aed"),
    ("finance",        "Finance User",          "موظف مالية",             "#166534"),
    ("groomer",        "Groomer",               "موظف تجميل",             "#be185d"),
    ("boarding_staff", "Boarding Staff",        "موظف الإيواء",           "#6b7280"),
    ("support_admin",  "Support Admin",         "مدير الدعم الفني",       "#374151"),
    ("auditor",        "Read-only Auditor",     "مدقق للقراءة فقط",       "#6b7280"),
]

_SEED_CATEGORIES = [
    ("Medications", "أدوية"), ("Vaccines", "تطعيمات"),
    ("Consumables", "مستهلكات"), ("Surgical Materials", "مواد جراحية"),
    ("Lab Materials", "مواد مخبرية"), ("Grooming Products", "منتجات تجميل"),
    ("Pet Food", "غذاء حيوانات"), ("Pet Accessories", "إكسسوارات"),
    ("Cleaning", "مواد تنظيف"), ("Office Supplies", "مستلزمات مكتبية"),
]

_SEED_WA_TEMPLATES = [
    ("appointment_reminder", "appointment", "en",
     "Dear {owner_name}, this is a reminder for {pet_name}'s appointment at {clinic_name} on {date} at {time}. Please confirm by replying YES. Thank you!"),
    ("appointment_confirmation", "appointment", "en",
     "Your appointment for {pet_name} at {clinic_name} on {date} at {time} is confirmed. See you soon!"),
    ("followup_reminder", "followup", "en",
     "Dear {owner_name}, it's time for {pet_name}'s follow-up visit at {clinic_name}. Please call us to schedule at your convenience."),
    ("vaccine_due", "vaccine", "en",
     "Dear {owner_name}, {pet_name} is due for {vaccine_name} vaccination. Please contact {clinic_name} to schedule. Stay ahead of preventive care!"),
    ("invoice_sent", "invoice", "en",
     "Dear {owner_name}, your invoice #{invoice_number} for {amount} EGP is ready. Please contact us for payment details. Thank you!"),
    ("appointment_reminder_ar", "appointment", "ar",
     "عزيزي {owner_name}، تذكير بموعد {pet_name} في {clinic_name} يوم {date} الساعة {time}. يرجى التأكيد بالرد بـ نعم. شكراً!"),
]


def _run_pg_migrations(conn) -> None:
    """Create any tables/columns that were added after initial PostgreSQL setup.
    Safe to run on every startup — all statements use IF NOT EXISTS / try-except.
    """
    # Budget targets table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS budget_targets (
            id          SERIAL PRIMARY KEY,
            category    TEXT NOT NULL UNIQUE,
            monthly_egp REAL NOT NULL DEFAULT 0,
            updated_by  TEXT,
            updated_at  TIMESTAMP DEFAULT NOW()
        )
    """)
    # Loyalty points table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_points (
            id          SERIAL PRIMARY KEY,
            owner_id    INTEGER NOT NULL,
            points      INTEGER NOT NULL,
            reason      TEXT,
            ref_type    TEXT DEFAULT 'manual',
            ref_id      INTEGER,
            created_by  TEXT,
            created_at  TIMESTAMP DEFAULT NOW(),
            FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_loyalty_owner ON loyalty_points(owner_id)"
    )
    # loyalty_balance column on owners
    try:
        conn.execute("ALTER TABLE owners ADD COLUMN loyalty_balance INTEGER DEFAULT 0")
    except Exception:
        pass


def init_db(admin_user: str = "admin", admin_pass: str = "admin1234") -> None:
    _dir = os.path.dirname(_db_path)
    if _dir:
        os.makedirs(_dir, exist_ok=True)
    conn = get_db()
    with conn:
        conn.executescript(_SCHEMA)
        # PostgreSQL-mode migrations: create tables that were added after initial schema
        if _PG_CONFIG:
            _run_pg_migrations(conn)
        # SOAP columns migration (safe: ADD COLUMN is idempotent via try/except)
        for _col, _type in [
            ("soap_subjective", "TEXT"),
            ("soap_objective",  "TEXT"),
            ("soap_assessment", "TEXT"),
            ("soap_plan",       "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE visits ADD COLUMN {_col} {_type}")
            except Exception:
                pass  # column already exists
        # Loyalty balance column on owners
        try:
            conn.execute("ALTER TABLE owners ADD COLUMN loyalty_balance INTEGER DEFAULT 0")
        except Exception:
            pass  # column already exists
        # Seed default budget targets (idempotent — only if table is empty)
        try:
            if conn.execute("SELECT COUNT(*) FROM budget_targets").fetchone()[0] == 0:
                for _cat, _amt in [
                    ("Medicines/Supplies", 50000),
                    ("Staff Salaries",     120000),
                    ("Utilities",          15000),
                    ("Equipment",          25000),
                    ("Marketing",          10000),
                    ("Miscellaneous",      8000),
                ]:
                    conn.execute(
                        "INSERT INTO budget_targets (category, monthly_egp) VALUES (?,?)",
                        (_cat, _amt)
                    )
        except Exception:
            pass  # Table may not exist yet in this transaction; migrations run next
        # clinic
        if conn.execute("SELECT COUNT(*) FROM clinic").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO clinic (name, name_ar, doctor_name) VALUES (?,?,?)",
                ("Aleefy","اليفي","Lead Veterinarian"),
            )
        # branches
        if conn.execute("SELECT COUNT(*) FROM branches").fetchone()[0] == 0:
            conn.execute("INSERT INTO branches (name, name_ar) VALUES (?,?)",
                         ("Main Branch","الفرع الرئيسي"))
        # roles
        for (rn, rd, rda, rc) in _SEED_ROLES:
            conn.execute(
                "INSERT OR IGNORE INTO roles (name,display_name,display_name_ar,color) VALUES (?,?,?,?)",
                (rn, rd, rda, rc))
        # admin user
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO users (username,password_hash,full_name,role,is_active) VALUES (?,?,?,?,1)",
                (admin_user, _hash(admin_pass), "Platform Administrator", "super_admin"))
        # item categories
        for (cn, cna) in _SEED_CATEGORIES:
            conn.execute("INSERT OR IGNORE INTO item_categories (name,name_ar) VALUES (?,?)", (cn, cna))
        # default warehouse
        if conn.execute("SELECT COUNT(*) FROM warehouses").fetchone()[0] == 0:
            conn.execute("INSERT INTO warehouses (name,name_ar) VALUES (?,?)",
                         ("Main Pharmacy","الصيدلية الرئيسية"))
        # whatsapp templates
        for (tn, sc, lg, txt) in _SEED_WA_TEMPLATES:
            conn.execute(
                "INSERT OR IGNORE INTO whatsapp_templates (name,scenario,language,template_text) VALUES (?,?,?,?)",
                (tn, sc, lg, txt))
        # shifts
        if conn.execute("SELECT COUNT(*) FROM shifts").fetchone()[0] == 0:
            for (sn, st, et, bk, days) in [
                ("Morning Shift",   "08:00", "16:00", 60, "1,2,3,4,5"),
                ("Evening Shift",   "14:00", "22:00", 60, "1,2,3,4,5"),
                ("Night Shift",     "22:00", "06:00", 60, "1,2,3,4,5,6,7"),
                ("Weekend Morning", "09:00", "15:00", 30, "6,7"),
            ]:
                conn.execute(
                    "INSERT INTO shifts(name,start_time,end_time,break_minutes,days_of_week) VALUES(?,?,?,?,?)",
                    (sn, st, et, bk, days))
        # leave types
        if conn.execute("SELECT COUNT(*) FROM leave_types").fetchone()[0] == 0:
            for (ln, la, days, paid) in [
                ("Annual Leave",    "إجازة سنوية",    21, 1),
                ("Sick Leave",      "إجازة مرضية",    14, 1),
                ("Emergency Leave", "إجازة طارئة",     3, 1),
                ("Maternity Leave", "إجازة أمومة",    90, 1),
                ("Unpaid Leave",    "إجازة بدون راتب",30, 0),
                ("Study Leave",     "إجازة دراسية",    5, 1),
            ]:
                conn.execute(
                    "INSERT INTO leave_types(name,name_ar,days_per_year,is_paid) VALUES(?,?,?,?)",
                    (ln, la, days, paid))
        # grooming services
        if conn.execute("SELECT COUNT(*) FROM grooming_services").fetchone()[0] == 0:
            for (n, p, d) in [("Basic Bath","200",60),("Full Grooming","350",90),("Nail Trim","80",20),("Ear Cleaning","100",15)]:
                conn.execute("INSERT INTO grooming_services (name,price,duration_min) VALUES (?,?,?)",(n,p,d))
        # boarding rooms
        if conn.execute("SELECT COUNT(*) FROM boarding_rooms").fetchone()[0] == 0:
            for (n, rt, p) in [("Room A1","Standard",150),("Room A2","Standard",150),("Suite B1","Premium",300),("ICU 1","ICU",500)]:
                conn.execute("INSERT INTO boarding_rooms (name,room_type,price_per_night) VALUES (?,?,?)",(n,rt,p))
        # service catalog
        if conn.execute("SELECT COUNT(*) FROM service_catalog").fetchone()[0] == 0:
            _seed_services(conn)
    conn.close()


def _seed_services(conn) -> None:
    """Seed default service price catalog."""
    services = [
        # code, name, name_ar, category, price, duration_min
        ("CONS-GEN", "General Consultation",   "استشارة عامة",         "Consultation", 150, 20),
        ("CONS-EMG", "Emergency Consultation", "استشارة طارئة",        "Consultation", 300, 30),
        ("CONS-FOL", "Follow-up Consultation", "زيارة متابعة",         "Consultation", 80,  15),
        ("VAC-RAB",  "Rabies Vaccine",         "تطعيم الكلب الأسود",  "Vaccination",  120, 10),
        ("VAC-DHPP", "DHPP Combo Vaccine",     "تطعيم رباعي",          "Vaccination",  150, 10),
        ("VAC-FVR",  "Feline FVRCP Vaccine",   "تطعيم القطط الرباعي", "Vaccination",  130, 10),
        ("LAB-CBC",  "CBC Blood Count",        "صورة دم كاملة",        "Laboratory",   200, 30),
        ("LAB-BIO",  "Biochemistry Panel",     "تحاليل كيميائية",      "Laboratory",   350, 45),
        ("LAB-URI",  "Urinalysis",             "تحليل بول",            "Laboratory",   150, 20),
        ("LAB-XRY",  "X-Ray (1 view)",         "أشعة سينية",           "Laboratory",   300, 20),
        ("LAB-ULT",  "Ultrasound",             "سونار",                "Laboratory",   400, 30),
        ("SRG-SPN",  "Spay/Neuter",           "تعقيم",                "Surgery",      800, 90),
        ("SRG-DEN",  "Dental Cleaning",        "تنظيف الأسنان",        "Surgery",      500, 60),
        ("SRG-MAS",  "Mass Removal",           "استئصال ورم",          "Surgery",      1200,120),
        ("GRM-BTH",  "Basic Bath",             "استحمام بسيط",         "Grooming",     200, 60),
        ("GRM-FUL",  "Full Grooming",          "تجميل كامل",           "Grooming",     350, 90),
        ("GRM-NAL",  "Nail Trim",              "قص أظافر",             "Grooming",     80,  20),
        ("BRD-STD",  "Boarding (Standard)",    "إيواء عادي",           "Boarding",     150, 0),
        ("BRD-PRM",  "Boarding (Premium Suite)","إيواء مميز",          "Boarding",     300, 0),
        ("HOSP-DAY", "Day Hospitalization",    "إقامة نهارية",         "Hospitalization",200,480),
        ("MED-ADM",  "IV Fluid Administration","تعطية سوائل",          "Treatment",    150, 30),
        ("MED-INJ",  "Injection",              "حقنة",                 "Treatment",    50,  5),
        ("MED-WND",  "Wound Dressing",         "تضميد جرح",            "Treatment",    100, 20),
    ]
    for (code, name, name_ar, cat, price, dur) in services:
        conn.execute(
            "INSERT OR IGNORE INTO service_catalog(code,name,name_ar,category,standard_price,duration_min) VALUES(?,?,?,?,?,?)",
            (code, name, name_ar, cat, price, dur))


# ── AUTH ───────────────────────────────────────────────────────
_SALT = "pah_platform_2026"
_BCRYPT_PREFIX = b"$2b$"


def _hash_sha256(pw: str) -> str:
    """Legacy SHA-256 hash (kept for migration detection only)."""
    return hashlib.sha256(f"{_SALT}{pw}".encode()).hexdigest()


def _hash(pw: str) -> str:
    """New primary hash: bcrypt. Used for all new passwords."""
    return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt(rounds=12)).decode()


def _hash_password(pw: str) -> str:
    """Alias for _hash — public API used by HR/reset routes."""
    return _hash(pw)


def _verify_and_migrate(row, password: str, conn) -> bool:
    """
    Verify password against bcrypt (preferred) or SHA-256 (legacy).
    On SHA-256 match, transparently rehash with bcrypt and save.
    Returns True if password matches.
    """
    stored = row["password_hash"]
    # Try bcrypt first (new hashes start with $2b$)
    if stored and stored.startswith("$2b$"):
        try:
            return _bcrypt.checkpw(password.encode(), stored.encode())
        except Exception:
            return False
    # Legacy SHA-256 check
    if stored == _hash_sha256(password):
        # Rehash with bcrypt transparently
        new_hash = _hash(password)
        try:
            conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                         (new_hash, row["id"]))
            conn.commit()
        except Exception:
            pass
        return True
    return False


def verify_credentials(username: str, password: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    if not row:
        conn.close()
        return None
    ok = _verify_and_migrate(row, password, conn)
    conn.close()
    return dict(row) if ok else None

def touch_last_login(user_id: int) -> None:
    from datetime import datetime
    now = datetime.utcnow().isoformat(timespec='seconds')
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET last_login_at=? WHERE id=?", (now, user_id))
    conn.close()

def get_user(username: str) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1",(username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_user_theme(username: str, theme: str) -> None:
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET theme_preference=? WHERE username=?", (theme, username))
    conn.close()

# ── CLINIC ─────────────────────────────────────────────────────
def get_clinic() -> dict:
    """Return clinic row — cached 5 min so context_processor pays zero DB cost."""
    cached, hit = _cache_get("clinic_row")
    if hit:
        return cached
    conn = get_db()
    row = conn.execute("SELECT * FROM clinic LIMIT 1").fetchone()
    conn.close()
    result = dict(row) if row else {}
    _cache_set("clinic_row", result, ttl=300)
    return result

def update_clinic(data: dict, updated_by: str = "system") -> None:
    """Update clinic settings and invalidate the cache."""
    conn = get_db()
    sets = ", ".join(f"{k}=%s" for k in data)
    vals = list(data.values())
    with conn:
        conn.execute(f"UPDATE clinic SET {sets}, updated_at=NOW() WHERE id=1", vals)
    conn.close()
    cache_invalidate("clinic_row")

# ── SETTINGS ───────────────────────────────────────────────────
def get_setting(key: str, default: str = "") -> str:
    cache_key = f"setting:{key}"
    cached, hit = _cache_get(cache_key)
    if hit:
        return cached
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    result = (row[0] or default) if row else default
    _cache_set(cache_key, result, ttl=300)
    return result

def set_setting(key: str, value: str, category: str = "general", updated_by: str = "system") -> None:
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key,value,category,updated_at,updated_by) VALUES(?,?,?,datetime('now'),?)",
            (key, value, category, updated_by))
    conn.close()
    cache_invalidate(f"setting:{key}")

# ── AUDIT ──────────────────────────────────────────────────────
def log_audit(username="", role="", action="", module="",
              entity_type="", entity_id="", details="", ip="", user_agent=""):
    try:
        conn = get_db()
        with conn:
            conn.execute(
                "INSERT INTO audit_log(username,role,action,module,entity_type,entity_id,details,ip,user_agent) VALUES(?,?,?,?,?,?,?,?,?)",
                (username,role,action,module,entity_type,entity_id,details,ip,user_agent))
        conn.close()
    except Exception:
        pass

def get_audit_log(limit: int = 200) -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── HR ─────────────────────────────────────────────────────────
def list_users() -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM users ORDER BY full_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_user(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO users(username,password_hash,full_name,email,phone,role,is_active) VALUES(?,?,?,?,?,?,?)",
            (data["username"], _hash(data.get("password", "changeme")),
             data.get("full_name", ""), data.get("email", ""), data.get("phone", ""),
             data.get("role", "staff"), 1))
        uid = cur.lastrowid
    conn.close()
    return uid

def _create_user_safe(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO users(username,password_hash,full_name,email,phone,role,is_active) VALUES(?,?,?,?,?,?,?)",
            (data["username"], _hash(data.get("password","changeme")),
             data.get("full_name",""), data.get("email",""), data.get("phone",""),
             data.get("role","staff"), 1))
        uid = cur.lastrowid
    conn.close()
    return uid

def toggle_user_active(user_id: int, active: int) -> None:
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (active, user_id))
    conn.close()

def update_user_role(user_id: int, role: str) -> None:
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.close()

# ── CRM — OWNERS ───────────────────────────────────────────────
def list_owners(search: str = "", limit: int = 100, offset: int = 0) -> list:
    """Return owners with pet_count in a single aggregated query (no N+1)."""
    conn = get_db()
    base = (
        "SELECT o.*, COALESCE(pc.cnt, 0) AS pet_count"
        " FROM owners o"
        " LEFT JOIN (SELECT owner_id, COUNT(*) AS cnt FROM pets GROUP BY owner_id) pc"
        "   ON pc.owner_id = o.id"
    )
    if search:
        q = f"%{search}%"
        rows = conn.execute(
            base + " WHERE o.full_name LIKE ? OR o.phone LIKE ?"
                   " OR o.whatsapp_phone LIKE ? OR o.email LIKE ?"
                   " ORDER BY o.full_name LIMIT ? OFFSET ?",
            (q, q, q, q, limit, offset)).fetchall()
    else:
        rows = conn.execute(
            base + " ORDER BY o.created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def count_owners(search: str = "") -> int:
    conn = get_db()
    if search:
        q = f"%{search}%"
        n = conn.execute(
            "SELECT COUNT(*) FROM owners WHERE full_name LIKE ? OR phone LIKE ? OR email LIKE ?",
            (q,q,q)).fetchone()[0]
    else:
        n = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
    conn.close()
    return n

def get_owner(owner_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_owner(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            """INSERT INTO owners(full_name,phone,whatsapp_phone,email,address,
               preferred_contact,preferred_doctor,vip_flag,notes,marketing_consent,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get("full_name",""), data.get("phone",""), data.get("whatsapp_phone",""),
             data.get("email",""), data.get("address",""), data.get("preferred_contact","WhatsApp"),
             data.get("preferred_doctor",""), int(data.get("vip_flag",0)),
             data.get("notes",""), int(data.get("marketing_consent",1)), data.get("created_by","")))
        oid = cur.lastrowid
    conn.close()
    return oid

def update_owner(owner_id: int, data: dict) -> None:
    conn = get_db()
    with conn:
        conn.execute(
            """UPDATE owners SET full_name=?,phone=?,whatsapp_phone=?,email=?,address=?,
               preferred_contact=?,preferred_doctor=?,vip_flag=?,notes=?,marketing_consent=?,
               updated_at=datetime('now') WHERE id=?""",
            (data.get("full_name",""), data.get("phone",""), data.get("whatsapp_phone",""),
             data.get("email",""), data.get("address",""), data.get("preferred_contact","WhatsApp"),
             data.get("preferred_doctor",""), int(data.get("vip_flag",0)),
             data.get("notes",""), int(data.get("marketing_consent",1)), owner_id))
    conn.close()

def delete_owner(owner_id: int) -> None:
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM owners WHERE id=?", (owner_id,))
    conn.close()

def get_owner_balance(owner_id: int) -> float:
    conn = get_db()
    row = conn.execute(
        "SELECT COALESCE(SUM(due_amount),0) FROM invoices WHERE owner_id=? AND status!='Cancelled'",
        (owner_id,)).fetchone()
    conn.close()
    return float(row[0]) if row else 0.0

# ── CRM — PETS ─────────────────────────────────────────────────
def list_pets(owner_id: Optional[int] = None, search: str = "") -> list:
    conn = get_db()
    if owner_id:
        rows = conn.execute(
            "SELECT p.*, o.full_name owner_name FROM pets p JOIN owners o ON o.id=p.owner_id"
            " WHERE p.owner_id=? ORDER BY p.pet_name", (owner_id,)).fetchall()
    elif search:
        q = f"%{search}%"
        rows = conn.execute(
            "SELECT p.*, o.full_name owner_name FROM pets p JOIN owners o ON o.id=p.owner_id"
            " WHERE p.pet_name LIKE ? OR p.microchip_id LIKE ?"
            " ORDER BY p.pet_name LIMIT 100", (q,q)).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, o.full_name owner_name FROM pets p JOIN owners o ON o.id=p.owner_id"
            " ORDER BY p.created_at DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_pet(pet_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT p.*, o.full_name owner_name, o.phone owner_phone, o.whatsapp_phone"
        " FROM pets p JOIN owners o ON o.id=p.owner_id WHERE p.id=?", (pet_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_pet(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            """INSERT INTO pets(owner_id,pet_name,species,breed,sex,dob,weight_kg,
               color,microchip_id,neutered,allergies,chronic_conditions,notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["owner_id"], data.get("pet_name",""), data.get("species",""),
             data.get("breed",""), data.get("sex","Unknown"), data.get("dob",""),
             data.get("weight_kg") or None, data.get("color",""), data.get("microchip_id",""),
             int(data.get("neutered",0)), data.get("allergies",""),
             data.get("chronic_conditions",""), data.get("notes","")))
        pid = cur.lastrowid
    conn.close()
    return pid

def update_pet(pet_id: int, data: dict) -> None:
    conn = get_db()
    with conn:
        conn.execute(
            """UPDATE pets SET pet_name=?,species=?,breed=?,sex=?,dob=?,weight_kg=?,
               color=?,microchip_id=?,neutered=?,allergies=?,chronic_conditions=?,
               notes=?,updated_at=datetime('now') WHERE id=?""",
            (data.get("pet_name",""), data.get("species",""), data.get("breed",""),
             data.get("sex","Unknown"), data.get("dob",""), data.get("weight_kg") or None,
             data.get("color",""), data.get("microchip_id",""),
             int(data.get("neutered",0)), data.get("allergies",""),
             data.get("chronic_conditions",""), data.get("notes",""), pet_id))
    conn.close()

def get_pet_timeline(pet_id: int) -> list:
    """Return all clinical events for a pet, sorted newest first."""
    conn = get_db()
    events = []
    # Visits
    for r in conn.execute("SELECT id, visit_date dt, visit_type etype, chief_complaint summary, status FROM visits WHERE pet_id=? ORDER BY visit_date DESC", (pet_id,)).fetchall():
        events.append({"dt": r["dt"], "type": "visit", "icon": "🩺", "title": f"Visit — {r['etype']}", "summary": r["summary"] or "", "id": r["id"], "status": r["status"]})
    # Vaccinations
    for r in conn.execute("SELECT id, administered_at dt, vaccine_name vname FROM vaccinations WHERE pet_id=? ORDER BY administered_at DESC", (pet_id,)).fetchall():
        events.append({"dt": r["dt"], "type": "vaccine", "icon": "💉", "title": f"Vaccine — {r['vname']}", "summary": "", "id": r["id"]})
    # Surgeries
    for r in conn.execute("SELECT id, surgery_date dt, procedure_name pname, outcome FROM surgeries WHERE pet_id=? ORDER BY surgery_date DESC", (pet_id,)).fetchall():
        events.append({"dt": r["dt"], "type": "surgery", "icon": "🔧", "title": f"Surgery — {r['pname']}", "summary": r["outcome"] or "", "id": r["id"]})
    # Grooming
    for r in conn.execute("SELECT id, booking_date dt, status FROM grooming_bookings WHERE pet_id=? ORDER BY booking_date DESC", (pet_id,)).fetchall():
        events.append({"dt": r["dt"], "type": "grooming", "icon": "✂️", "title": "Grooming", "summary": r["status"], "id": r["id"]})
    # Invoices (linked to pet via invoice table)
    for r in conn.execute(
        "SELECT id, issue_date dt, invoice_number inv_no, total, status FROM invoices WHERE pet_id=? ORDER BY issue_date DESC",
        (pet_id,)
    ).fetchall():
        events.append({
            "dt": r["dt"], "type": "invoice", "icon": "🧾",
            "title": f"Invoice {r['inv_no']} — {r['status']}",
            "summary": f"Total: {r['total']:.2f}" if r["total"] else "",
            "id": r["id"],
        })
    # Lab requests (linked through visits)
    for r in conn.execute(
        """SELECT lr.id, lr.created_at dt, lr.test_name, lr.status
           FROM lab_requests lr
           JOIN visits v ON v.id = lr.visit_id
           WHERE v.pet_id=? ORDER BY lr.created_at DESC""",
        (pet_id,)
    ).fetchall():
        events.append({
            "dt": r["dt"], "type": "lab", "icon": "🔬",
            "title": f"Lab — {r['test_name']}",
            "summary": r["status"] or "",
            "id": r["id"],
        })
    conn.close()
    events.sort(key=lambda x: x["dt"] or "", reverse=True)
    return events

# ── APPOINTMENTS ───────────────────────────────────────────────
def list_appointments(date_from: str = "", date_to: str = "",
                      status: str = "", doctor: str = "",
                      limit: int = 100) -> list:
    conn = get_db()
    q = """SELECT a.*, o.full_name owner_name, o.phone owner_phone,
                  p.pet_name, p.species
           FROM appointments a
           JOIN owners o ON o.id=a.owner_id
           JOIN pets   p ON p.id=a.pet_id
           WHERE 1=1"""
    params: list = []
    if date_from: q += " AND a.appt_date >= ?"; params.append(date_from)
    if date_to:   q += " AND a.appt_date <= ?"; params.append(date_to)
    if status:    q += " AND a.status = ?";      params.append(status)
    if doctor:    q += " AND a.doctor_name LIKE ?"; params.append(f"%{doctor}%")
    q += " ORDER BY a.appt_date, a.appt_start LIMIT ?"; params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_today_appointments() -> list:
    today = date.today().isoformat()
    return list_appointments(date_from=today, date_to=today, limit=200)

def get_appointment(appt_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT a.*, o.full_name owner_name, p.pet_name, p.species FROM appointments a"
        " JOIN owners o ON o.id=a.owner_id JOIN pets p ON p.id=a.pet_id WHERE a.id=?",
        (appt_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_appointment(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            """INSERT INTO appointments(owner_id,pet_id,doctor_name,room,appointment_type,
               priority,status,channel,appt_date,appt_start,appt_end,duration_min,
               reason,symptoms,notes,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data["owner_id"], data["pet_id"], data.get("doctor_name",""),
             data.get("room",""), data.get("appointment_type","Consultation"),
             data.get("priority","Normal"), data.get("status","Scheduled"),
             data.get("channel","Walk-in"), data["appt_date"], data.get("appt_start","09:00"),
             data.get("appt_end",""), data.get("duration_min",30),
             data.get("reason",""), data.get("symptoms",""), data.get("notes",""),
             data.get("created_by","")))
        aid = cur.lastrowid
    conn.close()
    return aid

def update_appointment_status(appt_id: int, status: str, username: str = "") -> None:
    conn = get_db()
    with conn:
        extra = ""
        if status == "Checked-in":
            extra = ", checked_in_at=datetime('now')"
        elif status in ("Completed","No-Show","Cancelled"):
            extra = ", checked_out_at=datetime('now')"
        conn.execute(f"UPDATE appointments SET status=?,updated_at=datetime('now'){extra} WHERE id=?",
                     (status, appt_id))
    conn.close()

def get_appointment_stats_today() -> dict:
    """Return today's appointment counts in a single aggregated query."""
    conn = get_db()
    today = date.today().isoformat()
    rows = conn.execute(
        "SELECT status, COUNT(*) n FROM appointments WHERE appt_date=? GROUP BY status",
        (today,)
    ).fetchall()
    conn.close()
    by_status = {r["status"]: r["n"] for r in rows}
    total = sum(by_status.values())
    return {"total": total, "by_status": by_status, "date": today}

# ── VISITS ─────────────────────────────────────────────────────
def list_visits(pet_id: Optional[int] = None, limit: int = 50) -> list:
    conn = get_db()
    if pet_id:
        rows = conn.execute(
            "SELECT v.*, p.pet_name, o.full_name owner_name FROM visits v"
            " JOIN pets p ON p.id=v.pet_id JOIN owners o ON o.id=v.owner_id"
            " WHERE v.pet_id=? ORDER BY v.visit_date DESC LIMIT ?", (pet_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT v.*, p.pet_name, o.full_name owner_name FROM visits v"
            " JOIN pets p ON p.id=v.pet_id JOIN owners o ON o.id=v.owner_id"
            " ORDER BY v.visit_date DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_visit(visit_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT v.*, p.pet_name, p.species, p.breed, p.weight_kg pet_weight,"
        " o.full_name owner_name, o.phone owner_phone FROM visits v"
        " JOIN pets p ON p.id=v.pet_id JOIN owners o ON o.id=v.owner_id WHERE v.id=?",
        (visit_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_visit_diagnoses(visit_id: int) -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM diagnoses WHERE visit_id=?", (visit_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_visit_prescriptions(visit_id: int) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT p.*, (SELECT json_group_array(json_object('name',pi.medication_name,'dosage',pi.dosage,'freq',pi.frequency,'qty',pi.quantity,'unit',pi.unit,'instructions',pi.instructions))"
        " FROM prescription_items pi WHERE pi.prescription_id=p.id) items_json"
        " FROM prescriptions p WHERE p.visit_id=?", (visit_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_visit(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            """INSERT INTO visits(appointment_id,owner_id,pet_id,doctor_name,room,
               visit_date,visit_type,status,chief_complaint,symptoms,weight_kg,
               temp_c,heart_rate,notes,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get("appointment_id"), data["owner_id"], data["pet_id"],
             data.get("doctor_name",""), data.get("room",""),
             data.get("visit_date", date.today().isoformat()),
             data.get("visit_type","Consultation"), data.get("status","Open"),
             data.get("chief_complaint",""), data.get("symptoms",""),
             data.get("weight_kg") or None, data.get("temp_c") or None,
             data.get("heart_rate") or None, data.get("notes",""),
             data.get("created_by","")))
        vid = cur.lastrowid
    conn.close()
    return vid

def add_diagnosis(visit_id: int, pet_id: int, diagnosis: str,
                  severity: str = "Moderate", notes: str = "", created_by: str = "") -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO diagnoses(visit_id,pet_id,diagnosis,severity,notes,created_by) VALUES(?,?,?,?,?,?)",
            (visit_id, pet_id, diagnosis, severity, notes, created_by))
        did = cur.lastrowid
    conn.close()
    return did

def complete_visit(visit_id: int) -> None:
    conn = get_db()
    with conn:
        conn.execute("UPDATE visits SET status='Completed',updated_at=datetime('now') WHERE id=?",
                     (visit_id,))
    conn.close()

# ── INVENTORY ──────────────────────────────────────────────────
def list_items(search: str = "", category_id: Optional[int] = None,
               low_stock_only: bool = False, limit: int = 100) -> list:
    conn = get_db()
    q = """SELECT i.*, ic.name category_name,
                  COALESCE((SELECT SUM(b.quantity) FROM batches b WHERE b.item_id=i.id),0) stock_qty
           FROM items i LEFT JOIN item_categories ic ON ic.id=i.category_id
           WHERE i.is_active=1"""
    params: list = []
    if search:
        q += " AND (i.name LIKE ? OR i.sku LIKE ? OR i.barcode LIKE ?)"; s=f"%{search}%"; params+=[s,s,s]
    if category_id:
        q += " AND i.category_id=?"; params.append(category_id)
    q += " ORDER BY i.name LIMIT ?"; params.append(limit)
    rows = conn.execute(q, params).fetchall()
    result = [dict(r) for r in rows]
    if low_stock_only:
        result = [r for r in result if r["stock_qty"] <= r["reorder_level"]]
    conn.close()
    return result

def get_item(item_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT i.*, ic.name category_name,"
        " COALESCE((SELECT SUM(b.quantity) FROM batches b WHERE b.item_id=i.id),0) stock_qty"
        " FROM items i LEFT JOIN item_categories ic ON ic.id=i.category_id WHERE i.id=?",
        (item_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_item(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            """INSERT INTO items(category_id,sku,barcode,name,unit,cost_price,sell_price,
               reorder_level,is_medication,is_controlled,requires_rx,supplier_id,storage_notes)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (data.get("category_id"), data.get("sku",""), data.get("barcode",""),
             data["name"], data.get("unit","unit"),
             float(data.get("cost_price",0)), float(data.get("sell_price",0)),
             float(data.get("reorder_level",10)),
             int(data.get("is_medication",0)), int(data.get("is_controlled",0)),
             int(data.get("requires_rx",0)), data.get("supplier_id") or None,
             data.get("storage_notes","")))
        iid = cur.lastrowid
    conn.close()
    return iid

def add_stock_batch(item_id: int, warehouse_id: int, batch_number: str,
                    expiry_date: str, quantity: float, unit_cost: float,
                    received_by: str = "") -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO batches(item_id,warehouse_id,batch_number,expiry_date,quantity,unit_cost,received_by) VALUES(?,?,?,?,?,?,?)",
            (item_id, warehouse_id, batch_number, expiry_date, quantity, unit_cost, received_by))
        bid = cur.lastrowid
        conn.execute(
            "INSERT INTO stock_movements(item_id,batch_id,warehouse_id,movement_type,quantity,unit_cost,reference_type,created_by) VALUES(?,?,?,?,?,?,?,?)",
            (item_id, bid, warehouse_id, "in", quantity, unit_cost, "receiving", received_by))
    conn.close()
    return bid

def deduct_stock(item_id: int, quantity: float, reference_type: str = "dispensing",
                 reference_id: Optional[int] = None, by: str = "") -> bool:
    """Deduct stock using FEFO (First Expiry First Out). Returns True if sufficient stock."""
    conn = get_db()
    available = conn.execute(
        "SELECT COALESCE(SUM(quantity),0) FROM batches WHERE item_id=? AND quantity>0", (item_id,)).fetchone()[0]
    if float(available or 0) < quantity:
        conn.close()
        return False
    remaining = quantity
    batches = conn.execute(
        "SELECT * FROM batches WHERE item_id=? AND quantity>0 ORDER BY expiry_date ASC NULLS LAST",
        (item_id,)).fetchall()
    with conn:
        for b in batches:
            if remaining <= 0:
                break
            use = min(float(b["quantity"]), remaining)
            conn.execute("UPDATE batches SET quantity=quantity-? WHERE id=?", (use, b["id"]))
            conn.execute(
                "INSERT INTO stock_movements(item_id,batch_id,warehouse_id,movement_type,quantity,reference_type,reference_id,created_by) VALUES(?,?,?,?,?,?,?,?)",
                (item_id, b["id"], b["warehouse_id"], "out", use, reference_type, reference_id, by))
            remaining -= use
    conn.close()
    return True

def get_low_stock_items() -> list:
    return list_items(low_stock_only=True, limit=500)

def get_expiry_alerts(days: int = 30) -> list:
    conn = get_db()
    threshold = (date.today() + timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT b.*, i.name item_name, i.unit FROM batches b JOIN items i ON i.id=b.item_id"
        " WHERE b.expiry_date <= ? AND b.quantity > 0 ORDER BY b.expiry_date", (threshold,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_stock_movements(item_id: Optional[int] = None, limit: int = 100) -> list:
    conn = get_db()
    if item_id:
        rows = conn.execute(
            "SELECT sm.*, i.name item_name FROM stock_movements sm JOIN items i ON i.id=sm.item_id"
            " WHERE sm.item_id=? ORDER BY sm.created_at DESC LIMIT ?", (item_id, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT sm.*, i.name item_name FROM stock_movements sm JOIN items i ON i.id=sm.item_id"
            " ORDER BY sm.created_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_categories() -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM item_categories ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_warehouses() -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM warehouses WHERE is_active=1").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── FINANCE ────────────────────────────────────────────────────
def _next_invoice_number() -> str:
    conn = get_db()
    n = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
    conn.close()
    return f"INV-{date.today().year}-{(n+1):05d}"

def create_invoice(data: dict, lines: list) -> int:
    inv_no = _next_invoice_number()
    subtotal = sum(float(l.get("total",0)) for l in lines)
    disc_type = data.get("discount_type","value")
    disc_val  = float(data.get("discount_value",0))
    disc_amt  = disc_val if disc_type == "value" else round(subtotal * disc_val / 100, 2)
    tax_rate  = float(data.get("tax_rate",0))
    tax_amt   = round((subtotal - disc_amt) * tax_rate / 100, 2)
    total     = round(subtotal - disc_amt + tax_amt, 2)
    conn = get_db()
    with conn:
        cur = conn.execute(
            """INSERT INTO invoices(invoice_number,owner_id,pet_id,visit_id,doctor_name,issue_date,
               status,subtotal,discount_type,discount_value,discount_amount,tax_rate,tax_amount,
               total,paid_amount,due_amount,notes,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (inv_no, data["owner_id"], data.get("pet_id"), data.get("visit_id"),
             data.get("doctor_name",""), data.get("issue_date", date.today().isoformat()),
             "Unpaid", subtotal, disc_type, disc_val, disc_amt, tax_rate, tax_amt,
             total, 0.0, total, data.get("notes",""), data.get("created_by","")))
        inv_id = cur.lastrowid
        for line in lines:
            lt = float(line.get("total", float(line.get("quantity",1)) * float(line.get("unit_price",0))))
            conn.execute(
                "INSERT INTO invoice_lines(invoice_id,line_type,item_id,description,quantity,unit_price,discount,total) VALUES(?,?,?,?,?,?,?,?)",
                (inv_id, line.get("line_type","service"), line.get("item_id"),
                 line.get("description",""), float(line.get("quantity",1)),
                 float(line.get("unit_price",0)), float(line.get("discount",0)), lt))
    conn.close()
    return inv_id

def get_invoice(inv_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute(
        "SELECT i.*, o.full_name owner_name, o.phone owner_phone, o.whatsapp_phone,"
        " p.pet_name FROM invoices i JOIN owners o ON o.id=i.owner_id"
        " LEFT JOIN pets p ON p.id=i.pet_id WHERE i.id=?", (inv_id,)).fetchone()
    if not row:
        conn.close()
        return None
    inv = dict(row)
    inv["lines"] = [dict(r) for r in conn.execute(
        "SELECT * FROM invoice_lines WHERE invoice_id=?", (inv_id,)).fetchall()]
    inv["payments"] = [dict(r) for r in conn.execute(
        "SELECT * FROM payments WHERE invoice_id=? ORDER BY received_at DESC", (inv_id,)).fetchall()]
    conn.close()
    return inv

def list_invoices(owner_id: Optional[int] = None, status: str = "",
                  date_from: str = "", date_to: str = "", limit: int = 100) -> list:
    conn = get_db()
    q = "SELECT i.*, o.full_name owner_name, p.pet_name FROM invoices i JOIN owners o ON o.id=i.owner_id LEFT JOIN pets p ON p.id=i.pet_id WHERE 1=1"
    params: list = []
    if owner_id:  q += " AND i.owner_id=?";    params.append(owner_id)
    if status:    q += " AND i.status=?";       params.append(status)
    if date_from: q += " AND i.issue_date>=?";  params.append(date_from)
    if date_to:   q += " AND i.issue_date<=?";  params.append(date_to)
    q += " ORDER BY i.created_at DESC LIMIT ?"; params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_payment(invoice_id: int, owner_id: int, amount: float,
                method: str = "Cash", reference: str = "", received_by: str = "") -> None:
    conn = get_db()
    with conn:
        conn.execute(
            "INSERT INTO payments(invoice_id,owner_id,amount,method,reference,received_by) VALUES(?,?,?,?,?,?)",
            (invoice_id, owner_id, amount, method, reference, received_by))
        # Update invoice paid/due
        paid = conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE invoice_id=?",
                            (invoice_id,)).fetchone()[0]
        total = conn.execute("SELECT total FROM invoices WHERE id=?", (invoice_id,)).fetchone()[0]
        due = max(0.0, float(total) - float(paid))
        status = "Paid" if due == 0 else "Partial"
        conn.execute("UPDATE invoices SET paid_amount=?,due_amount=?,status=?,updated_at=datetime('now') WHERE id=?",
                     (float(paid), due, status, invoice_id))
    conn.close()

def get_finance_summary(date_from: str = "", date_to: str = "") -> dict:
    conn = get_db()
    today = date.today().isoformat()
    df = date_from or today
    dt = date_to   or today
    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM payments WHERE received_at BETWEEN ? AND ?",
        (df+" 00:00:00", dt+" 23:59:59")).fetchone()[0]
    invoiced = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM invoices WHERE issue_date BETWEEN ? AND ? AND status!='Cancelled'",
        (df, dt)).fetchone()[0]
    outstanding = conn.execute(
        "SELECT COALESCE(SUM(due_amount),0) FROM invoices WHERE status IN ('Unpaid','Partial')").fetchone()[0]
    expenses = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date BETWEEN ? AND ?",
        (df, dt)).fetchone()[0]
    inv_count = conn.execute(
        "SELECT COUNT(*) FROM invoices WHERE issue_date BETWEEN ? AND ? AND status!='Cancelled'",
        (df, dt)).fetchone()[0]
    conn.close()
    return {
        "revenue": float(revenue or 0),
        "invoiced": float(invoiced or 0),
        "outstanding": float(outstanding or 0),
        "expenses": float(expenses or 0),
        "net": float(revenue or 0) - float(expenses or 0),
        "invoice_count": int(inv_count or 0),
        "date_from": df, "date_to": dt,
    }

# ── REPORTS ────────────────────────────────────────────────────
def get_dashboard_stats() -> dict:
    conn = get_db()
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    stats = {
        "owners_total":    conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0],
        "pets_total":      conn.execute("SELECT COUNT(*) FROM pets").fetchone()[0],
        "visits_today":    conn.execute("SELECT COUNT(*) FROM visits WHERE visit_date=?", (today,)).fetchone()[0],
        "appts_today":     conn.execute("SELECT COUNT(*) FROM appointments WHERE appt_date=?", (today,)).fetchone()[0],
        "revenue_today":   float(conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE received_at LIKE ?", (f"{today}%",)).fetchone()[0] or 0),
        "revenue_month":   float(conn.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE received_at >= ?", (month_start,)).fetchone()[0] or 0),
        "invoices_unpaid": conn.execute("SELECT COUNT(*) FROM invoices WHERE status IN ('Unpaid','Partial')").fetchone()[0],
        "outstanding":     float(conn.execute("SELECT COALESCE(SUM(due_amount),0) FROM invoices WHERE status IN ('Unpaid','Partial')").fetchone()[0] or 0),
        "low_stock_count": conn.execute("SELECT COUNT(*) FROM items i WHERE (SELECT COALESCE(SUM(b.quantity),0) FROM batches b WHERE b.item_id=i.id) <= i.reorder_level AND i.is_active=1").fetchone()[0],
        "expiry_soon":     conn.execute("SELECT COUNT(*) FROM batches WHERE expiry_date <= ? AND quantity>0", ((date.today()+timedelta(days=30)).isoformat(),)).fetchone()[0],
        "pending_reminders": conn.execute("SELECT COUNT(*) FROM reminders WHERE status='Pending'").fetchone()[0],
        "vip_owners":      conn.execute("SELECT COUNT(*) FROM owners WHERE vip_flag=1").fetchone()[0],
    }
    conn.close()
    return stats

def get_revenue_by_day(days: int = 30) -> list:
    conn = get_db()
    since = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT DATE(received_at) d, COALESCE(SUM(amount),0) revenue FROM payments"
        " WHERE received_at >= ? GROUP BY DATE(received_at) ORDER BY d", (since,)).fetchall()
    conn.close()
    return [{"date": r["d"], "revenue": float(r["revenue"])} for r in rows]

def get_top_services(limit: int = 10) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT description, COUNT(*) count, SUM(total) revenue FROM invoice_lines"
        " WHERE line_type='service' GROUP BY description ORDER BY revenue DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── SUPPLIERS ──────────────────────────────────────────────────
def list_suppliers() -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM suppliers WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_supplier(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO suppliers(name,contact_name,phone,email,address,payment_terms,notes) VALUES(?,?,?,?,?,?,?)",
            (data["name"], data.get("contact_name",""), data.get("phone",""),
             data.get("email",""), data.get("address",""),
             data.get("payment_terms","Net 30"), data.get("notes","")))
        sid = cur.lastrowid
    conn.close()
    return sid

# ── REMINDERS / WHATSAPP ───────────────────────────────────────
def list_reminders(status: str = "", limit: int = 100) -> list:
    conn = get_db()
    q = "SELECT r.*, o.full_name owner_name, o.whatsapp_phone, p.pet_name FROM reminders r JOIN owners o ON o.id=r.owner_id LEFT JOIN pets p ON p.id=r.pet_id WHERE 1=1"
    params: list = []
    if status: q += " AND r.status=?"; params.append(status)
    q += " ORDER BY r.scheduled_for DESC LIMIT ?"; params.append(limit)
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def create_reminder(data: dict) -> int:
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO reminders(owner_id,pet_id,appointment_id,reminder_type,message,channel,scheduled_for,created_by) VALUES(?,?,?,?,?,?,?,?)",
            (data["owner_id"], data.get("pet_id"), data.get("appointment_id"),
             data.get("reminder_type","appointment"), data.get("message",""),
             data.get("channel","WhatsApp"), data["scheduled_for"], data.get("created_by","")))
        rid = cur.lastrowid
    conn.close()
    return rid

def list_wa_templates() -> list:
    conn = get_db()
    rows = conn.execute("SELECT * FROM whatsapp_templates WHERE is_active=1 ORDER BY scenario, name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── VACCINATIONS ───────────────────────────────────────────────
def list_vaccinations(pet_id: Optional[int] = None, limit: int = 100) -> list:
    conn = get_db()
    if pet_id:
        rows = conn.execute(
            "SELECT v.*, p.pet_name FROM vaccinations v JOIN pets p ON p.id=v.pet_id WHERE v.pet_id=? ORDER BY v.administered_at DESC",
            (pet_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT v.*, p.pet_name, o.full_name owner_name FROM vaccinations v"
            " JOIN pets p ON p.id=v.pet_id JOIN owners o ON o.id=p.owner_id"
            " ORDER BY v.administered_at DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_upcoming_vaccines(days: int = 30) -> list:
    conn = get_db()
    threshold = (date.today() + timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT v.*, p.pet_name, o.full_name owner_name, o.whatsapp_phone FROM vaccinations v"
        " JOIN pets p ON p.id=v.pet_id JOIN owners o ON o.id=p.owner_id"
        " WHERE v.next_due_at <= ? AND v.next_due_at >= ? ORDER BY v.next_due_at",
        (threshold, date.today().isoformat())).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── NOTIFICATIONS ─────────────────────────────────────────────

def create_notification(recipient_id: int, title: str, body: str = "",
                         icon: str = "🔔", link: str = "", module: str = "",
                         entity_type: str = "", entity_id: int = None,
                         recipient_role: str = "") -> None:
    try:
        conn = get_db()
        with conn:
            conn.execute(
                """INSERT INTO notifications(recipient_id,recipient_role,title,body,icon,link,module,entity_type,entity_id)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (recipient_id, recipient_role, title, body, icon, link, module, entity_type, entity_id))
        conn.close()
    except Exception:
        pass


def notify_role(role: str, title: str, body: str = "", icon: str = "🔔",
                link: str = "", module: str = "") -> None:
    """Send notification to all active users with a given role."""
    try:
        conn = get_db()
        users = conn.execute(
            "SELECT id FROM users WHERE role=? AND is_active=1", (role,)).fetchall()
        with conn:
            for u in users:
                conn.execute(
                    """INSERT INTO notifications(recipient_id,recipient_role,title,body,icon,link,module)
                       VALUES(?,?,?,?,?,?,?)""",
                    (u["id"], role, title, body, icon, link, module))
        conn.close()
    except Exception:
        pass


def notify_managers(title: str, body: str = "", icon: str = "🔔",
                    link: str = "", module: str = "") -> None:
    """Notify all manager-level roles."""
    for role in ("super_admin", "clinic_owner", "branch_manager", "hr"):
        notify_role(role, title, body, icon, link, module)


def get_user_notifications(user_id: int, limit: int = 20) -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM notifications WHERE recipient_id=? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_unread_notifications(user_id: int) -> int:
    conn = get_db()
    n = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE recipient_id=? AND is_read=0",
        (user_id,)).fetchone()[0]
    conn.close()
    return n


def mark_notifications_read(user_id: int, notif_id: int = None) -> None:
    conn = get_db()
    with conn:
        if notif_id:
            conn.execute("UPDATE notifications SET is_read=1 WHERE id=? AND recipient_id=?",
                         (notif_id, user_id))
        else:
            conn.execute("UPDATE notifications SET is_read=1 WHERE recipient_id=?", (user_id,))
    conn.close()


# ── SERVICE CATALOG ────────────────────────────────────────────

def list_services(category: str = "", active_only: bool = True) -> list:
    conn = get_db()
    q = "SELECT * FROM service_catalog WHERE 1=1"
    params: list = []
    if active_only:
        q += " AND is_active=1"
    if category:
        q += " AND category=?"
        params.append(category)
    q += " ORDER BY category, sort_order, name"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_service(svc_id: int) -> Optional[dict]:
    conn = get_db()
    row = conn.execute("SELECT * FROM service_catalog WHERE id=?", (svc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_service(data: dict) -> int:
    conn = get_db()
    svc_id = data.get("id")
    with conn:
        if svc_id:
            conn.execute(
                """UPDATE service_catalog SET code=?,name=?,name_ar=?,category=?,description=?,
                   standard_price=?,tax_rate=?,duration_min=?,species=?,is_active=?,
                   sort_order=?,updated_at=datetime('now') WHERE id=?""",
                (data.get("code",""), data["name"], data.get("name_ar",""),
                 data.get("category","Consultation"), data.get("description",""),
                 float(data.get("standard_price",0)), float(data.get("tax_rate",0)),
                 int(data.get("duration_min",0)), data.get("species","All"),
                 int(data.get("is_active",1)), int(data.get("sort_order",0)), svc_id))
        else:
            cur = conn.execute(
                """INSERT INTO service_catalog(code,name,name_ar,category,description,standard_price,
                   tax_rate,duration_min,species,is_active,sort_order) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (data.get("code",""), data["name"], data.get("name_ar",""),
                 data.get("category","Consultation"), data.get("description",""),
                 float(data.get("standard_price",0)), float(data.get("tax_rate",0)),
                 int(data.get("duration_min",0)), data.get("species","All"),
                 int(data.get("is_active",1)), int(data.get("sort_order",0))))
            svc_id = cur.lastrowid
    conn.close()
    return svc_id


def service_categories() -> list:
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT category FROM service_catalog WHERE is_active=1 ORDER BY category"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ── LEGACY STATS (Excel) ───────────────────────────────────────
def _xlsx_count(path: str) -> int:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        n = max(0, ws.max_row - 1)
        wb.close()
        return n
    except Exception:
        return 0

def get_legacy_stats(legacy_data_dir: str) -> dict:
    stats = {"owners": 0, "pets": 0, "bookings_today": 0,
             "pending_reminders": 0, "total_bookings": 0}
    try:
        stats["owners"]         = _xlsx_count(os.path.join(legacy_data_dir, "owners.xlsx"))
        stats["pets"]           = _xlsx_count(os.path.join(legacy_data_dir, "pets.xlsx"))
        stats["total_bookings"] = _xlsx_count(os.path.join(legacy_data_dir, "bookings.xlsx"))
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            import openpyxl
            wb = openpyxl.load_workbook(os.path.join(legacy_data_dir,"bookings.xlsx"),read_only=True,data_only=True)
            ws = wb.active
            headers = [c.value for c in next(ws.iter_rows(min_row=1,max_row=1))]
            try:
                di = headers.index("appointment_start")
                for row in ws.iter_rows(min_row=2,values_only=True):
                    if str(row[di] or "").startswith(today): stats["bookings_today"] += 1
            except (ValueError,TypeError): pass
            wb.close()
        except Exception: pass
    except Exception: pass
    return stats


# ── ROLES & PERMISSIONS ────────────────────────────────────────

ALL_PERMISSIONS = [
    ("patients",     "Manage Patients & Owners"),
    ("appointments", "Manage Appointments"),
    ("visits",       "Medical Visits & SOAP"),
    ("pharmacy",     "Pharmacy & Dispensing"),
    ("invoicing",    "Invoicing & Payments"),
    ("inventory",    "Inventory & Stock"),
    ("procurement",  "Procurement & Purchasing"),
    ("reports",      "Reports & Analytics"),
    ("whatsapp",     "WhatsApp Messaging"),
    ("catalog",      "Service Catalog"),
    ("grooming",     "Grooming"),
    ("boarding",     "Boarding"),
    ("hr",           "HR & Staff"),
    ("attendance",   "Attendance & Leave"),
    ("accounting",   "Accounting"),
    ("ai",           "AI Assistant"),
    ("system",       "System Admin"),
    ("backup",       "Backup & Restore"),
    ("audit",        "Audit Log"),
    ("settings",     "Platform Settings"),
]


def list_roles() -> list:
    import json
    conn = get_db()
    rows = conn.execute("SELECT * FROM roles ORDER BY name").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        try:
            d["permissions"] = json.loads(d.get("permissions_json") or "[]")
        except Exception:
            d["permissions"] = []
        result.append(d)
    return result


def get_role(role_id: int) -> Optional[dict]:
    import json
    conn = get_db()
    row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["permissions"] = json.loads(d.get("permissions_json") or "[]")
    except Exception:
        d["permissions"] = []
    return d


def create_role(name: str, display_name: str, display_name_ar: str, permissions: list, color: str) -> int:
    import json
    conn = get_db()
    with conn:
        cur = conn.execute(
            "INSERT INTO roles(name,display_name,display_name_ar,permissions_json,color) VALUES(?,?,?,?,?)",
            (name.strip().lower().replace(" ", "_"), display_name, display_name_ar, json.dumps(permissions), color)
        )
        return cur.lastrowid


def update_role(role_id: int, display_name: str, display_name_ar: str, permissions: list, color: str) -> None:
    import json
    conn = get_db()
    with conn:
        conn.execute(
            "UPDATE roles SET display_name=?,display_name_ar=?,permissions_json=?,color=? WHERE id=?",
            (display_name, display_name_ar, json.dumps(permissions), color, role_id)
        )


def delete_role(role_id: int) -> None:
    conn = get_db()
    with conn:
        conn.execute("DELETE FROM roles WHERE id=?", (role_id,))


def assign_user_role(user_id: int, role: str) -> None:
    conn = get_db()
    with conn:
        conn.execute("UPDATE users SET role=?,updated_at=datetime('now') WHERE id=?", (role, user_id))
