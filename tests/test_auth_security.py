"""Self-check for the auth/authz security fixes.

Runs on SQLite only — no PostgreSQL, no Flask app, no fixtures:
    D:\\vet\\.venv\\Scripts\\python.exe -m pytest tests/test_auth_security.py -q

Covers:
  T1  open-redirect rejection (safe_redirect_target)
  T2  DB-backed rate limiting, locking on IP *and* on username
  T3  has_permission fail-safe behaviour on malformed / empty permissions_json
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.database as db

# Force the SQLite path at a throwaway file so the dev/prod DB is never touched.
_TMPDIR = tempfile.mkdtemp(prefix="vet_authsec_")
db.set_path(os.path.join(_TMPDIR, "test.db"))
db._PG_CONFIG = {}
db._POOL = None

import models.security as sec
from blueprints.auth.routes import (
    safe_redirect_target, has_permission, clear_permission_cache,
)

FALLBACK = "/home"


def _reset_roles(rows):
    """(re)create a minimal roles table holding `rows` of (name, permissions_json)."""
    conn = db.get_db()
    try:
        conn.execute("DROP TABLE IF EXISTS roles")
        conn.execute("CREATE TABLE roles (name TEXT PRIMARY KEY, permissions_json TEXT)")
        for name, pj in rows:
            conn.execute("INSERT INTO roles (name, permissions_json) VALUES (?,?)", (name, pj))
        conn.commit()
    finally:
        conn.close()
    clear_permission_cache()


# ── T1: open redirect ────────────────────────────────────────────────────────

def test_open_redirect_rejects_offsite():
    for hostile in [
        "//evil.com",                 # protocol-relative — the reported bug
        "///evil.com",
        "http://evil.com",
        "https://evil.com/path",
        "javascript:alert(1)",
        "\\\\evil.com",               # backslash pair
        "/\\evil.com",                # browsers normalise \ to / => //evil.com
        "\\/evil.com",
        "/path\\to\\evil",            # any backslash at all
        "//evil.com/\t",              # control chars stripped by the browser
        "/\n/evil.com",               # becomes //evil.com after stripping
        "  //evil.com",
        "https:evil.com",             # scheme with no slashes
        "relative/path",              # not absolute
        "",
        None,
    ]:
        assert safe_redirect_target(hostile, FALLBACK) == FALLBACK, hostile


def test_open_redirect_allows_local_paths():
    for ok in ["/safe/path", "/", "/patients?id=3", "/a/b/c#frag", "/x%20y"]:
        assert safe_redirect_target(ok, FALLBACK) == ok, ok


# ── T2: rate limiting ────────────────────────────────────────────────────────

def test_rate_limit_locks_on_ip():
    ip, user = "10.0.0.1", "alice"
    sec.clear_rate_limit(ip, user)
    for i in range(sec.RATE_LIMIT_MAX - 1):
        assert sec.record_failed_login(ip, user) is False, i
        assert sec.is_rate_limited(ip, user)[0] is False
    assert sec.record_failed_login(ip, user) is True
    locked, secs = sec.is_rate_limited(ip, user)
    assert locked is True
    assert 0 < secs <= sec.RATE_LIMIT_WINDOW
    sec.clear_rate_limit(ip, user)
    assert sec.is_rate_limited(ip, user)[0] is False


def test_rate_limit_locks_on_username_across_many_ips():
    """A distributed attack: every attempt from a different IP, one account."""
    user = "bob"
    sec.clear_rate_limit(None, user)
    for i in range(sec.RATE_LIMIT_MAX):
        sec.record_failed_login(f"192.168.5.{i}", user)
    # No single IP is over the threshold...
    conn = db.get_db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM login_attempts WHERE ip=?",
                         ("192.168.5.0",)).fetchone()[0]
    finally:
        conn.close()
    assert n == 1
    # ...but the account is locked.
    assert sec.is_rate_limited("192.168.5.99", user)[0] is True
    # An untargeted account from a clean IP is unaffected.
    assert sec.is_rate_limited("192.168.5.99", "carol")[0] is False
    sec.clear_rate_limit(None, user)


def test_rate_limit_username_is_case_insensitive():
    sec.clear_rate_limit("10.0.0.9", "Dave")
    for _ in range(sec.RATE_LIMIT_MAX):
        sec.record_failed_login("10.0.0.9", "Dave")
    assert sec.is_rate_limited("10.0.0.50", "dave")[0] is True
    sec.clear_rate_limit("10.0.0.9", "DAVE")
    assert sec.is_rate_limited("10.0.0.50", "dave")[0] is False


def test_rate_limit_survives_a_process_restart():
    """The whole point of moving counters into the DB."""
    ip, user = "10.0.0.77", "erin"
    sec.clear_rate_limit(ip, user)
    for _ in range(sec.RATE_LIMIT_MAX):
        sec.record_failed_login(ip, user)
    sec._tables_ready.clear()          # simulate a fresh worker process
    assert sec.is_rate_limited(ip, user)[0] is True
    sec.clear_rate_limit(ip, user)


# ── T3: permissions fail-safe ────────────────────────────────────────────────

def test_has_permission_grants_on_valid_json():
    _reset_roles([("doctor", json.dumps(["visits", "patients"]))])
    assert has_permission("visits.edit", "doctor") is True
    assert has_permission("visits", "doctor") is True
    assert has_permission("patients.view", "doctor") is True
    assert has_permission("accounting.view", "doctor") is False


def test_has_permission_fails_closed_on_malformed_json():
    """Unparseable / wrong-shaped data must never grant access."""
    for bad in ["{not json", "[1,2,3", '{"patients": true}', "null", "42",
                '"patients"', "[]", "", None]:
        _reset_roles([("nurse", bad)])
        assert has_permission("patients.view", "nurse") is False, repr(bad)
        assert has_permission("accounting.view", "nurse") is False, repr(bad)


def test_has_permission_fails_closed_on_unknown_role():
    _reset_roles([("doctor", json.dumps(["visits"]))])
    assert has_permission("visits.edit", "ghost_role") is False
    assert has_permission("visits.edit", "") is False
    assert has_permission("", "doctor") is False


def test_has_permission_ignores_junk_entries_but_keeps_valid_ones():
    _reset_roles([("mixed", json.dumps(["patients", None, 7, "  ", " VISITS "]))])
    assert has_permission("patients.view", "mixed") is True
    assert has_permission("visits.edit", "mixed") is True     # trimmed + lowercased
    assert has_permission("accounting.view", "mixed") is False


def test_super_admin_always_passes():
    _reset_roles([("super_admin", "{corrupt")])
    assert has_permission("anything.at.all", "super_admin") is True
    assert has_permission("system.admin", "super_admin") is True


def test_missing_roles_table_fails_closed():
    conn = db.get_db()
    try:
        conn.execute("DROP TABLE IF EXISTS roles")
        conn.commit()
    finally:
        conn.close()
    clear_permission_cache()
    assert has_permission("patients.view", "doctor") is False
    assert has_permission("patients.view", "super_admin") is True


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
    print("all passed")
