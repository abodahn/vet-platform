"""
Test configuration — uses an isolated PostgreSQL database (vetclinic_test)
so tests never touch production data.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app
from config import Config


# ─── PostgreSQL test-database setup ──────────────────────────────────────────

def _create_test_pg_db():
    """Drop and recreate the vetclinic_test database."""
    import psycopg2
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="postgres",
        user="postgres", password="1234"
    )
    conn.autocommit = True
    cur = conn.cursor()
    # Terminate any existing connections to the test DB
    cur.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = 'vetclinic_test' AND pid <> pg_backend_pid()
    """)
    cur.execute("DROP DATABASE IF EXISTS vetclinic_test")
    cur.execute("CREATE DATABASE vetclinic_test ENCODING='UTF8'")
    conn.close()


def _drop_test_pg_db():
    """Drop the vetclinic_test database after all tests."""
    import psycopg2
    conn = psycopg2.connect(
        host="localhost", port=5432, dbname="postgres",
        user="postgres", password="1234"
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("""
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname = 'vetclinic_test' AND pid <> pg_backend_pid()
    """)
    cur.execute("DROP DATABASE IF EXISTS vetclinic_test")
    conn.close()


# ─── Session-scoped fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="session")
def _db_path(tmp_path_factory):
    """Dummy path — kept for SQLite backup config compatibility."""
    return str(tmp_path_factory.mktemp("data") / "test_platform.db")


@pytest.fixture(scope="session")
def app(_db_path):
    # Create the isolated test database fresh
    _create_test_pg_db()

    class TestConfig(Config):
        TESTING = True
        DATABASE_PATH = _db_path
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-secret-key"
        # Point to the isolated test database
        POSTGRES_DSN = "postgresql://postgres:1234@localhost:5432/vetclinic_test"

    application = create_app(TestConfig)

    yield application

    # Teardown: close PG connections and drop test DB
    _drop_test_pg_db()


# ─── Per-test fixtures ────────────────────────────────────────────────────────

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
