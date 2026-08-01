"""Self-check for the database layer shim. Runs on SQLite only — no PostgreSQL."""
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import database as db


def test_fix_sql_preserves_literal_question_mark():
    out = db._fix_sql("UPDATE t SET msg='Confirm? reply YES' WHERE id=?")
    assert out == "UPDATE t SET msg='Confirm? reply YES' WHERE id=%s"


def test_fix_sql_converts_placeholders():
    assert db._fix_sql("SELECT * FROM pets WHERE id=? AND owner_id=?") == \
        "SELECT * FROM pets WHERE id=%s AND owner_id=%s"


def test_fix_sql_handles_escaped_quote_inside_literal():
    # '' is the SQL escape for a quote; the ? after it is still a literal.
    out = db._fix_sql("INSERT INTO t(a,b) VALUES('it''s ok?', ?)")
    assert out.endswith("VALUES('it''s ok?', %s)")


def test_fix_sql_insert_or_ignore_translation():
    out = db._fix_sql("INSERT OR IGNORE INTO roles (name) VALUES (?)")
    assert out == "INSERT INTO roles (name) VALUES (%s) ON CONFLICT DO NOTHING"


def test_fix_sql_insert_or_replace_translation():
    out = db._fix_sql("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)")
    assert out == "INSERT INTO settings(key,value) VALUES(%s,%s) ON CONFLICT DO NOTHING"


def test_fix_sql_datetime_now():
    assert "NOW()" in db._fix_sql("INSERT INTO t(a) VALUES(datetime('now'))")


def test_fix_sql_translates_the_TWO_ARGUMENT_datetime_form():
    """datetime('now','localtime') must reach PostgreSQL as NOW().

    Only the one-argument form was handled. The reverse translator adds
    'localtime' deliberately — it is what stops SQLite disagreeing with
    PostgreSQL about what day it is — so newer code writes the two-argument
    form, and it went to PostgreSQL verbatim as a call to a function that does
    not exist there. Every CREATE TABLE carrying such a DEFAULT failed and so
    did every UPDATE using it, which left the whole payments schema unusable on
    the production engine while passing perfectly on SQLite.

    NOW() is right for both: PostgreSQL evaluates it in the server's own
    timezone, which is what 'localtime' asks for.
    """
    out = db._fix_sql("UPDATE t SET updated_at=datetime('now','localtime') WHERE id=?")
    assert out == "UPDATE t SET updated_at=NOW() WHERE id=%s"
    assert "datetime(" not in db._fix_sql(
        "CREATE TABLE t (a TEXT DEFAULT (datetime('now', 'localtime')))")


def test_fix_sql_casts_NOW_for_a_TEXT_column_WITH_constraints():
    """PostgreSQL refuses `a TEXT DEFAULT NOW()` outright — "column is of type
    text but default expression is of type timestamp with time zone" — so the
    default is cast. The rule required TEXT and DEFAULT to be adjacent, and a
    perfectly ordinary `created_at TEXT NOT NULL DEFAULT (...)` slipped past it
    and failed at CREATE TABLE on PostgreSQL only."""
    for ddl in ("CREATE TABLE t (a TEXT NOT NULL DEFAULT (datetime('now','localtime')))",
                "CREATE TABLE t (a TEXT UNIQUE NOT NULL DEFAULT (datetime('now')))",
                "CREATE TABLE t (a TEXT DEFAULT (datetime('now')))"):
        out = db._fix_sql(ddl)
        assert "::TEXT" in out, f"uncast NOW() default: {out}"


def test_the_WHOLE_schema_survives_translation_to_postgresql():
    """A sweep, not a sample. Every table the app creates has to be valid on
    the production engine, and these three shapes are silently fatal there
    while passing on SQLite — which is the only engine the suite runs on."""
    import re
    pg = db._fix_sql(db._SCHEMA)
    assert not re.search(r"datetime\(\s*'now'", pg), \
        "a datetime('now') reached PostgreSQL untranslated"
    assert not re.search(r"\bAUTOINCREMENT\b", pg, re.I), \
        "AUTOINCREMENT is not PostgreSQL syntax"
    assert not re.search(
        r"\bTEXT(?:\s+(?:NOT\s+NULL|NULL|UNIQUE))*\s+DEFAULT\s+\(NOW\(\)\)(?!::TEXT)",
        pg, re.I), "a TEXT column defaults to an uncast NOW()"


def test_returning_id_skips_tables_without_id():
    assert db._PGCursor._returning_id_target("INSERT INTO visits (pet_id) VALUES (%s)") == "visits"
    assert db._PGCursor._returning_id_target("INSERT INTO settings(key) VALUES (%s)") is None
    assert db._PGCursor._returning_id_target(
        "INSERT INTO t(a) VALUES (%s) RETURNING id") is None
    assert db._PGCursor._returning_id_target("SELECT 1") is None


def test_no_id_table_list_matches_EVERY_table_the_app_creates():
    """Guards _TABLES_WITHOUT_ID against drift, across the whole codebase.

    This used to scan db._SCHEMA alone. Eleven modules create tables lazily at
    runtime instead — and one of them, rate_hits, has no `id` column. It was
    therefore invisible here, so INSERT ... RETURNING id would have been
    appended to it and every throttled request would have failed on PostgreSQL
    with UndefinedColumn, while passing on SQLite, which ignores the extra
    clause. Scanning only the tables that happen to live in one string was the
    blind spot, not the missing entry.
    """
    import pathlib

    ddl_sources = [db._SCHEMA]
    root = pathlib.Path(__file__).resolve().parent.parent
    for path in list((root / "models").rglob("*.py")) + \
                list((root / "blueprints").rglob("*.py")):
        ddl_sources.append(path.read_text(encoding="utf-8", errors="ignore"))

    found = set()
    for src in ddl_sources:
        for m in re.finditer(
                r'CREATE TABLE (?:IF NOT EXISTS )?(\w+)\s*\((.*?)\n\s*\)',
                src, re.S | re.I):
            name, body = m.group(1).lower(), m.group(2)
            if not re.search(r'^\s*id\s', body, re.M):
                found.add(name)

    missing = found - set(db._TABLES_WITHOUT_ID)
    assert not missing, (
        f"these tables have no `id` column but are not in _TABLES_WITHOUT_ID, "
        f"so INSERT ... RETURNING id will fail on PostgreSQL: {sorted(missing)}")


def test_get_db_returns_working_sqlite_connection():
    with tempfile.TemporaryDirectory() as d:
        db.set_path(os.path.join(d, "t.db"))
        conn = db.get_db()
        try:
            conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
            cur = conn.execute("INSERT INTO t (name) VALUES (?)", ("Rex?",))
            assert cur.lastrowid == 1
            conn.commit()
            assert conn.execute("SELECT name FROM t WHERE id=?", (1,)).fetchone()[0] == "Rex?"
        finally:
            conn.close()
            conn.close()  # double close must be safe


class _StubCursor:
    """Stands in for a psycopg2 cursor so the PG path is testable without PG."""

    def __init__(self):
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return (7,)


def test_pg_execute_is_bare_and_passes_none_for_empty_params():
    stub = _StubCursor()
    cur = db._PGCursor.__new__(db._PGCursor)
    cur._cur, cur._raw_conn, cur.lastrowid, cur.rowcount, cur._sp_seq = stub, None, None, 0, 0

    # No params -> None, so psycopg2 never interpolates a literal % away.
    cur.execute("SELECT 1 FROM t WHERE name LIKE '%tele%'")
    assert stub.calls[-1] == ("SELECT 1 FROM t WHERE name LIKE '%tele%'", None)

    # INSERT gets exactly one round-trip with RETURNING id appended.
    cur.execute("INSERT INTO visits (pet_id) VALUES (?)", (3,))
    assert stub.calls[-1] == ("INSERT INTO visits (pet_id) VALUES (%s) RETURNING id", (3,))
    assert cur.lastrowid == 7
    assert len(stub.calls) == 2  # no savepoint / no speculative retry

    # id-less table: no RETURNING, and lastrowid resets.
    cur.execute("INSERT INTO settings(key,value) VALUES(?,?)", ("a", "b"))
    assert stub.calls[-1][0].endswith("ON CONFLICT DO NOTHING") is False
    assert "RETURNING" not in stub.calls[-1][0]
    assert cur.lastrowid is None


def test_close_context_connections_without_app_context():
    # No Flask app context active: must be a harmless no-op.
    db.close_context_connections()


def test_close_context_connections_releases_tracked_connections():
    from flask import Flask
    with tempfile.TemporaryDirectory() as d:
        db.set_path(os.path.join(d, "t.db"))
        app = Flask(__name__)
        with app.app_context():
            conn = db.get_db()
            conn.execute("SELECT 1").fetchone()
            db.close_context_connections()
            try:
                conn.execute("SELECT 1")
                raise AssertionError("connection should be closed")
            except Exception as exc:
                assert "closed" in str(exc).lower()
