"""
Test configuration.

Default (no external services): a throwaway SQLite database in a per-session
temp directory. `POSTGRES_DSN = ""` makes models.database.get_db() take its
SQLite branch, so nothing needs to be installed or running.

Opt-in PostgreSQL:

    TEST_POSTGRES_DSN=postgresql://user:pass@host:port/dbname  pytest tests

The database named in that DSN is DROPped and CREATEd at session start and
dropped again at the end, so point it at a throwaway database only. All
credentials come from the DSN — none are hardcoded here.
"""
import os
import sys
import pytest
from urllib.parse import urlparse, unquote

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from config import Config


# ─── PostgreSQL opt-in ────────────────────────────────────────────────────────

TEST_PG_DSN = os.environ.get("TEST_POSTGRES_DSN", "")

# Test modules that talk to PostgreSQL directly (psycopg2, pg_catalog, PG column
# types) and cannot run on SQLite. They are marked `postgres` and skipped when
# TEST_POSTGRES_DSN is unset.
PG_ONLY_MODULES = {"test_postgres_full.py"}

# ponytail: whole-module granularity. These modules connect to PostgreSQL at
# *import* time, so a per-test marker cannot save them — the import must not
# happen at all. Ceiling: a mixed module with only some PG-only tests would
# need the per-test marker path in pytest_collection_modifyitems below.


def _pg_parts(dsn):
    """(connect-kwargs for the maintenance DB, name of the test DB)."""
    u = urlparse(dsn)
    if not u.hostname or not (u.path or "").strip("/"):
        raise ValueError(
            f"TEST_POSTGRES_DSN is not a usable DSN "
            f"(need postgresql://user:pass@host:port/dbname): {dsn!r}"
        )
    return (
        dict(
            host=u.hostname,
            port=u.port or 5432,
            dbname="postgres",
            user=unquote(u.username or ""),
            password=unquote(u.password or ""),
        ),
        u.path.lstrip("/"),
    )


def _recreate_test_pg_db(drop_only=False):
    """Drop (and optionally recreate) the database named in TEST_POSTGRES_DSN."""
    import psycopg2
    admin_kw, dbname = _pg_parts(TEST_PG_DSN)
    conn = psycopg2.connect(**admin_kw)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (dbname,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{dbname}"')
        if not drop_only:
            cur.execute(f'CREATE DATABASE "{dbname}" ENCODING=\'UTF8\'')
    finally:
        conn.close()


# ─── Collection hooks ─────────────────────────────────────────────────────────

def pytest_ignore_collect(collection_path, config):
    """Keep PG-only modules out of a SQLite run.

    test_postgres_full.py calls db.configure_postgres() at module scope, which
    mutates the process-global connection pool. Importing it during a SQLite
    run would silently redirect every later test at whatever PostgreSQL that
    module points to, so it must not be imported at all.
    """
    if collection_path.name in PG_ONLY_MODULES and not TEST_PG_DSN:
        return True
    return None


def pytest_collection_modifyitems(config, items):
    if TEST_PG_DSN:
        return
    skip_pg = pytest.mark.skip(reason="needs PostgreSQL — set TEST_POSTGRES_DSN")
    for item in items:
        if item.get_closest_marker("postgres"):
            item.add_marker(skip_pg)


def pytest_report_header(config):
    if TEST_PG_DSN:
        _, dbname = _pg_parts(TEST_PG_DSN)
        return f"database: PostgreSQL (TEST_POSTGRES_DSN -> {dbname})"
    return (
        "database: throwaway SQLite (set TEST_POSTGRES_DSN to run the "
        f"postgres-only modules: {', '.join(sorted(PG_ONLY_MODULES))})"
    )


# ─── Session-scoped fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _db_path(tmp_path_factory):
    """Throwaway SQLite file. Also the anchor for backup/upload dirs."""
    return str(tmp_path_factory.mktemp("data") / "test_platform.db")


@pytest.fixture(scope="session")
def app(_db_path):
    if TEST_PG_DSN:
        _recreate_test_pg_db()

    class TestConfig(Config):
        TESTING = True
        DATABASE_PATH = _db_path
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-secret-key"
        # "" -> get_db() falls through to SQLite at DATABASE_PATH.
        POSTGRES_DSN = TEST_PG_DSN
        # Seed password for the throwaway test database. The existing test
        # files post this literal, so it is not configurable away.
        SEED_ADMIN_PASS = "1234"

    application = create_app(TestConfig)

    yield application

    if TEST_PG_DSN:
        _recreate_test_pg_db(drop_only=True)


# ─── Per-test fixtures ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _restore_db_globals():
    """models.database keeps the connection target in module globals.

    Any test that calls db.set_path() / db.configure_postgres() — several do,
    pointing at their own tempdir — otherwise leaves every later test aimed at
    a directory that no longer exists. Snapshot and restore around every test
    so the leak cannot cross a test boundary.
    """
    import models.database as db
    import models.security as sec
    saved = (db._db_path, db._PG_CONFIG, db._POOL)
    yield
    db._db_path, db._PG_CONFIG, db._POOL = saved
    # sec._ensure_tables() latches on a process global, so a test that pointed
    # the DB elsewhere leaves login_attempts "already created" for a database
    # that never got it. Clear the latch with the path it was created against.
    sec._tables_ready = False


@pytest.fixture
def client(app):
    """Fresh unauthenticated test client per test."""
    return app.test_client()


@pytest.fixture
def auth_client(app):
    """Authenticated test client — re-logs in each time."""
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")  # seeds session["_csrf_token"] via context_processor
    return c


def get_csrf(auth_client):
    """Read the current CSRF token from the authenticated client's session."""
    from models.security import _CSRF_SESSION_KEY
    with auth_client.session_transaction() as sess:
        return sess.get(_CSRF_SESSION_KEY, "")
