"""SQLite dialect translation — the mirror of _fix_sql().

Runs on SQLite only; no PostgreSQL required.
"""

import sqlite3

import pytest

from models.database import _fix_sql_sqlite, _SQLiteConn


fix = _fix_sql_sqlite


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:", factory=_SQLiteConn)
    c.row_factory = sqlite3.Row
    yield c
    c.close()


# ── 1. %s placeholders ────────────────────────────────────────────
def test_pct_s_becomes_qmark():
    assert fix("SELECT * FROM t WHERE a=%s AND b=%s") == \
        "SELECT * FROM t WHERE a=? AND b=?"


def test_pct_s_inside_string_literal_untouched():
    assert fix("SELECT '%s' FROM t WHERE a=%s") == "SELECT '%s' FROM t WHERE a=?"


def test_like_pattern_survives():
    sql = "SELECT * FROM t WHERE name LIKE '%foo%' AND id=%s"
    assert fix(sql) == "SELECT * FROM t WHERE name LIKE '%foo%' AND id=?"


def test_strftime_format_literal_survives():
    sql = "SELECT strftime('%Y-%m-%d', d) FROM t"
    assert fix(sql) == sql


def test_qmark_placeholders_untouched():
    sql = "SELECT * FROM t WHERE a=? AND msg='Confirm? reply YES'"
    assert fix(sql) == sql


def test_pct_s_end_to_end(conn):
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO t (name) VALUES (%s)", ("ahmed",))
    row = conn.execute("SELECT name FROM t WHERE name=%s", ("ahmed",)).fetchone()
    assert row["name"] == "ahmed"


# ── 2. ::casts ────────────────────────────────────────────────────
@pytest.mark.parametrize("sql,want", [
    ("SELECT issue_date::text FROM i", "SELECT CAST(issue_date AS TEXT) FROM i"),
    ("SELECT 1::TEXT", "SELECT CAST(1 AS TEXT)"),
    ("SELECT inv.total::numeric", "SELECT CAST(inv.total AS REAL)"),
    ("SELECT (a - b)::int", "SELECT CAST((a - b) AS INTEGER)"),
    ("SELECT SUM(qty)::int", "SELECT CAST(SUM(qty) AS INTEGER)"),
    ("SELECT work_date::date", "SELECT date(work_date)"),
])
def test_casts(sql, want):
    assert fix(sql) == want


def test_cast_inside_string_literal_untouched():
    sql = "SELECT * FROM t WHERE code='a::b'"
    assert fix(sql) == sql


def test_unknown_cast_type_left_alone_so_it_raises(conn):
    assert "::" in fix("SELECT a::tsvector FROM t")
    conn.execute("CREATE TABLE t (a TEXT)")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("SELECT a::tsvector FROM t")


def test_cast_end_to_end(conn):
    conn.execute("CREATE TABLE s (discharged_at TEXT)")
    conn.execute("INSERT INTO s VALUES (datetime('now'))")
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM s WHERE discharged_at::date = CURRENT_DATE"
    ).fetchone()
    assert row["n"] == 1


# ── 3. ILIKE ──────────────────────────────────────────────────────
def test_ilike(conn):
    assert fix("SELECT 1 WHERE a ILIKE ?") == "SELECT 1 WHERE a LIKE ?"
    conn.execute("CREATE TABLE u (name TEXT)")
    conn.execute("INSERT INTO u VALUES ('Ahmed')")
    assert conn.execute("SELECT * FROM u WHERE name ILIKE %s", ("ahm%",)).fetchall()


def test_ilike_inside_literal_untouched():
    sql = "SELECT * FROM t WHERE note='use ILIKE here'"
    assert fix(sql) == sql


# ── 4. NOW() ──────────────────────────────────────────────────────
def test_now(conn):
    # 'localtime' is deliberate: SQLite's datetime('now') is UTC while
    # PostgreSQL's NOW() is server-local, and the whole app reads back against
    # local dates. Without it a row written "today" carried yesterday's date.
    assert fix("UPDATE t SET a=NOW()") == "UPDATE t SET a=datetime('now','localtime')"
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.execute("INSERT INTO t VALUES (NOW())")
    assert conn.execute("SELECT a FROM t").fetchone()["a"]


# ── 5. EXTRACT ────────────────────────────────────────────────────
def test_extract(conn):
    assert fix("SELECT EXTRACT(YEAR FROM d)") == \
        "SELECT CAST(strftime('%Y', d) AS INTEGER)"
    conn.execute("CREATE TABLE e (d TEXT)")
    conn.execute("INSERT INTO e VALUES ('2026-03-09')")
    row = conn.execute(
        "SELECT EXTRACT(YEAR FROM d) y, EXTRACT(MONTH FROM d) m, "
        "EXTRACT(DAY FROM d) dd FROM e"
    ).fetchone()
    assert (row["y"], row["m"], row["dd"]) == (2026, 3, 9)


def test_extract_over_cast_and_current_date(conn):
    conn.execute("CREATE TABLE w (work_date TEXT)")
    conn.execute("INSERT INTO w VALUES ('2026-03-09 08:00:00')")
    row = conn.execute(
        "SELECT COUNT(*) n FROM w WHERE EXTRACT(YEAR FROM work_date::date)=? "
        "AND EXTRACT(MONTH FROM work_date::date)=?", (2026, 3)
    ).fetchone()
    assert row["n"] == 1


def test_extract_unsupported_field_left_alone():
    assert "EXTRACT" in fix("SELECT EXTRACT(QUARTER FROM d)")


def test_extract_year_from_age(conn):
    conn.execute("CREATE TABLE h (hire_date TEXT)")
    conn.execute("INSERT INTO h VALUES (date('now','-3 years','-1 day'))")
    conn.execute("INSERT INTO h VALUES (date('now','-3 years','+1 day'))")
    rows = conn.execute(
        "SELECT EXTRACT(YEAR FROM AGE(hire_date))::int AS years FROM h"
    ).fetchall()
    assert [r["years"] for r in rows] == [3, 2]


def test_bare_age_left_alone():
    assert "AGE(" in fix("SELECT AGE(a, b) FROM t").upper()


# ── 6. INTERVAL ───────────────────────────────────────────────────
def test_interval_on_current_date_stays_a_date(conn):
    assert fix("SELECT CURRENT_DATE - INTERVAL '90 days'") == \
        "SELECT date(date('now','localtime'), '-90 days')"
    conn.execute("CREATE TABLE u (hire_date TEXT)")
    # 'localtime' on the seed rows too: CURRENT_DATE is now rewritten to the
    # local clock, and a bare date('now') here is UTC. Mixing the two is the
    # exact bug this translation exists to remove, and it would put the
    # boundary row one day the wrong side.
    conn.execute("INSERT INTO u VALUES (date('now','localtime','-90 days'))")  # boundary
    conn.execute("INSERT INTO u VALUES (date('now','localtime','-91 days'))")
    row = conn.execute(
        "SELECT COUNT(*) n FROM u WHERE hire_date >= (CURRENT_DATE - INTERVAL '90 days')"
    ).fetchone()
    assert row["n"] == 1


def test_interval_addition(conn):
    conn.execute("CREATE TABLE c (expiry_date TEXT)")
    conn.execute("INSERT INTO c VALUES (date('now','+10 days'))")
    conn.execute("INSERT INTO c VALUES (date('now','+40 days'))")
    row = conn.execute(
        "SELECT COUNT(*) n FROM c WHERE expiry_date BETWEEN CURRENT_DATE "
        "AND CURRENT_DATE + INTERVAL '30 days'"
    ).fetchone()
    assert row["n"] == 1


def test_interval_on_now_is_a_timestamp(conn):
    assert fix("DELETE FROM r WHERE run_at < NOW() - INTERVAL '30 days'") == \
        "DELETE FROM r WHERE run_at < datetime(datetime('now','localtime'), '-30 days')"


def test_compound_interval_left_alone():
    # compound intervals stay untranslated so they fail loudly rather than
    # returning a subtly wrong date
    assert "INTERVAL" in fix("SELECT CURRENT_DATE - INTERVAL '1 year 2 months'")


# ── connection/cursor behaviours the 400+ call sites rely on ──────
def test_connection_behaviours(conn):
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, a TEXT)")
    cur = conn.execute("INSERT INTO t (a) VALUES (%s)", ("x",))
    assert cur.lastrowid == 1
    cur = conn.executemany("INSERT INTO t (a) VALUES (%s)", [("y",), ("z",)])
    assert cur.rowcount == 2
    assert conn.execute("UPDATE t SET a=%s", ("q",)).rowcount == 3
    row = conn.execute("SELECT id, a FROM t WHERE id=1").fetchone()
    assert row["a"] == "q" and row[0] == 1 and dict(row) == {"id": 1, "a": "q"}
    assert len(conn.execute("SELECT * FROM t").fetchall()) == 3
    assert len(list(conn.execute("SELECT * FROM t"))) == 3       # iteration
    assert len(list(conn.cursor().execute("SELECT * FROM t"))) == 3
    conn.execute("SELECT 1", _protect=True)                      # PG kwarg tolerated


def test_executescript_and_transaction_semantics(conn):
    conn.executescript("CREATE TABLE a (x INT); CREATE TABLE b (y INT);")
    with conn:
        conn.execute("INSERT INTO a VALUES (%s)", (1,))
    assert conn.execute("SELECT COUNT(*) c FROM a").fetchone()["c"] == 1
    with pytest.raises(RuntimeError):
        with conn:
            conn.execute("INSERT INTO a VALUES (%s)", (2,))
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) c FROM a").fetchone()["c"] == 1


def test_inpatient_dashboard_renders_on_sqlite(auth_client):
    """blueprints/inpatient/routes.py:163 uses `discharged_at::date` and used to
    500 with `unrecognized token: ":"` on SQLite. Regression guard."""
    assert auth_client.get("/inpatient/").status_code == 200


@pytest.mark.parametrize("url", ["/payroll/", "/accounting/"])
def test_pg_flavoured_dashboards_render(auth_client, url):
    """Both are dense in ::text / ::date / EXTRACT. (/hr/ is 302 behind a role
    gate for the seed admin, so it cannot be probed the same way.)"""
    assert auth_client.get(url).status_code == 200


def test_get_db_returns_translating_conn(tmp_path):
    from models import database
    old = database._db_path
    # use_sqlite(), not set_path(): under TEST_POSTGRES_DSN, set_path leaves the
    # PostgreSQL pool in charge, so get_db() returned a _PGConn and this
    # assertion failed while testing nothing about the SQLite path.
    database.use_sqlite(str(tmp_path / "t.db"))
    try:
        c = database.get_db()
        assert isinstance(c, _SQLiteConn)
        c.close()
    finally:
        database.set_path(old)
