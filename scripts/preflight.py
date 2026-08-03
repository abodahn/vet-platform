# -*- coding: utf-8 -*-
"""Is this deployment safe to hand to a clinic?

Run on the server, before go-live, every time:

    python scripts/preflight.py

Exits 0 only when every FAIL is clear. Warnings do not block, but each one is
something a clinic will eventually notice.

This exists because "ready" was spread across config.py's validate(), a runbook,
and whatever the last person remembered. A checklist that lives in someone's
head is a checklist that gets skipped on the day it matters -- which is the day
you are standing in a clinic with the owner watching.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAIL, WARN, OK = "FAIL", "WARN", "OK"

_results = []


def check(name, status, detail=""):
    _results.append((status, name, detail))


# ── security ──────────────────────────────────────────────────────────────────

def check_secret_key():
    key = os.environ.get("PLATFORM_SECRET_KEY", "")
    if not key:
        check("Signing key set", FAIL,
              "PLATFORM_SECRET_KEY is unset. Session cookies would be signed with "
              "the key published in this repository, so anyone could forge a login.")
    elif "CHANGE" in key:
        check("Signing key set", FAIL, "still the shipped development key")
    elif len(key) < 32:
        check("Signing key set", FAIL, f"only {len(key)} chars, need >= 32")
    else:
        check("Signing key set", OK, f"{len(key)} chars")


def check_env():
    env = os.environ.get("FLASK_ENV", "development").lower()
    if env != "production":
        check("FLASK_ENV=production", FAIL,
              f"is '{env}'. Production validation is skipped unless this is "
              "exactly 'production', and DEBUG stays on.")
    else:
        check("FLASK_ENV=production", OK)


def check_admin_password():
    pw = os.environ.get("PLATFORM_ADMIN_PASS", "")
    weak = {"admin", "1234", "password", "Admin", "admin123", "Ahmed@1122"}
    if not pw:
        check("Seed admin password", WARN,
              "PLATFORM_ADMIN_PASS unset -- fine if every clinic is created with "
              "scripts/add_clinic.py, which generates its own")
    elif pw in weak:
        check("Seed admin password", FAIL, "set to a known-weak value")
    elif len(pw) < 12:
        check("Seed admin password", WARN, f"only {len(pw)} chars")
    else:
        check("Seed admin password", OK)


def check_cookies():
    if os.environ.get("SESSION_COOKIE_SECURE", "0") in ("1", "true", "yes"):
        check("Secure cookies", OK)
    else:
        check("Secure cookies", FAIL,
              "SESSION_COOKIE_SECURE is off, so the session cookie is sent over "
              "plain HTTP and can be read off the wire")


def check_cors():
    cors = os.environ.get("CORS_ALLOWED_ORIGIN", "")
    if (not cors or cors == "*") and os.environ.get("CORS_ALLOW_WILDCARD") != "1":
        check("Public API CORS", FAIL,
              "unset or '*' -- the public API would answer any origin")
    else:
        check("Public API CORS", OK, cors or "wildcard explicitly allowed")


def check_repo_secrets():
    """The credential that is already in this repository's history."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "log", "--all", "-S", "Ahmed@1122", "--oneline"],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        n = len([l for l in out.stdout.splitlines() if l.strip()])
    except Exception:
        check("Old password out of git history", WARN, "could not read git history")
        return
    if n:
        check("Old password out of git history", WARN,
              f"appears in {n} commit(s). Anyone given this repository has it. "
              "Rotate it everywhere it is still valid.")
    else:
        check("Old password out of git history", OK)


# ── data safety ───────────────────────────────────────────────────────────────

def check_database():
    import models.database as db
    from config import Config
    try:
        dsn = os.environ.get("POSTGRES_DSN", "")
        if dsn:
            from urllib.parse import urlparse, unquote
            u = urlparse(dsn)
            db.configure_postgres(host=u.hostname, port=u.port or 5432,
                                  dbname=(u.path or "").lstrip("/"),
                                  user=unquote(u.username or ""),
                                  password=unquote(u.password or ""))
            if not db.is_postgres():
                check("Database reachable", FAIL,
                      "POSTGRES_DSN is set but the server refused the connection")
                return
        else:
            db.set_path(Config.DATABASE_PATH)
            check("Using PostgreSQL", WARN,
                  "POSTGRES_DSN unset -- running on SQLite. Fine for one small "
                  "clinic on one machine; not for a hosted multi-clinic server.")
        conn = db.get_db()
        try:
            n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        finally:
            conn.close()
        check("Database reachable", OK, f"{n} user(s)")
    except Exception as exc:
        check("Database reachable", FAIL, str(exc)[:120])


def check_backups():
    import models.backup as bk
    try:
        h = bk.health()
    except Exception as exc:
        check("Backups", FAIL, f"could not read backup health: {str(exc)[:80]}")
        return
    if not h.get("has_backup"):
        check("Backups", FAIL,
              "no backup has ever been taken. Run one and open the archive "
              "before handing this to anyone.")
    elif h.get("stale"):
        check("Backups", FAIL, h.get("message", "the last backup is out of date"))
    else:
        check("Backups", OK, h.get("message", ""))


def check_pg_dump():
    """PostgreSQL backups shell out to pg_dump; without it they fail nightly."""
    if not os.environ.get("POSTGRES_DSN"):
        return
    import shutil
    if shutil.which("pg_dump"):
        check("pg_dump available", OK)
    else:
        check("pg_dump available", FAIL,
              "not on PATH -- PostgreSQL backups cannot run at all")


def check_clinics():
    from models import tenancy
    try:
        rows = tenancy.all_tenants(active_only=False)
    except Exception:
        rows = []
    if not rows:
        check("Clinics registered", WARN,
              "none yet -- single-clinic mode. Use scripts/add_clinic.py to add one.")
    else:
        check("Clinics registered", OK, ", ".join(r["slug"] for r in rows))


# ── main ──────────────────────────────────────────────────────────────────────

CHECKS = [
    check_secret_key, check_env, check_admin_password, check_cookies,
    check_cors, check_repo_secrets, check_database, check_pg_dump,
    check_backups, check_clinics,
]


def run(argv=None):
    p = argparse.ArgumentParser(description="Pre-handover safety check.")
    p.add_argument("--strict", action="store_true",
                   help="treat warnings as failures too")
    args = p.parse_args(argv)

    _results.clear()
    for fn in CHECKS:
        try:
            fn()
        except Exception as exc:
            check(fn.__name__, FAIL, f"check itself errored: {str(exc)[:100]}")

    width = max(len(n) for _, n, _ in _results)
    print()
    for status, name, detail in _results:
        mark = {OK: "  ok  ", WARN: " warn ", FAIL: " FAIL "}[status]
        print(f"[{mark}] {name.ljust(width)}  {detail}")
    print()

    fails = [r for r in _results if r[0] == FAIL]
    warns = [r for r in _results if r[0] == WARN]

    if fails:
        print(f"  {len(fails)} blocking problem(s). Do not hand this over yet.")
        return 1
    if warns and args.strict:
        print(f"  {len(warns)} warning(s), and --strict was given.")
        return 1
    if warns:
        print(f"  Ready, with {len(warns)} warning(s) worth reading above.")
        return 0
    print("  Ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
