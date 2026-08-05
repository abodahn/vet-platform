# -*- coding: utf-8 -*-
"""The pre-handover safety check.

A checklist that lives in someone's head gets skipped on the day it matters --
which is the day you are standing in a clinic with the owner watching. This is
that checklist as a command that exits non-zero.

The tests that matter are the ones proving it actually BLOCKS. A preflight
script that passes everything is worse than none, because it converts "I am not
sure" into false confidence.
"""
import importlib.util
import os
import sys

import pytest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPT = os.path.join(_PLATFORM, "scripts", "preflight.py")

STRONG_KEY = "a" * 64


def _load():
    spec = importlib.util.spec_from_file_location("preflight", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["preflight"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def pf(monkeypatch, tmp_path):
    """A deployment that passes everything, so each test can break one thing.

    Backup health is stubbed because it reads the real backup directory, which
    is machine state, not something this test is about. The backup check gets
    its own tests below, driven directly.
    """
    monkeypatch.setenv("PLATFORM_SECRET_KEY", STRONG_KEY)
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("PLATFORM_ADMIN_PASS", "a-long-enough-password")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "1")
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "https://aleefy.online")
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    # preflight now derives the backup dir and the tenant registry from
    # Config.DATABASE_PATH, exactly as create_app() does. Point that at tmp so
    # a developer's real data/ directory cannot decide whether a test passes.
    # setattr, not setenv: Config reads the environment at import time.
    from config import Config
    dbfile = tmp_path / "platform.db"
    monkeypatch.setattr(Config, "DATABASE_PATH", str(dbfile))
    # check_database() opens that same path, so it has to be a real database.
    # The autouse _restore_db_globals fixture puts models.database back after.
    import models.database as db
    db.use_sqlite(str(dbfile))
    db.init_db(admin_user="admin", admin_pass="preflight-fixture-pass")
    import models.backup as bk
    monkeypatch.setattr(bk, "health",
                        lambda: {"has_backup": True, "stale": False,
                                 "message": "last backup 2 hours ago"})
    return _load()


# ── the backup check itself ──────────────────────────────────────────────────

def test_never_having_backed_up_blocks(pf, monkeypatch):
    """Handing a clinic a system that has never backed up is the one mistake
    you cannot apologise your way out of."""
    import models.backup as bk
    monkeypatch.setattr(bk, "health",
                        lambda: {"has_backup": False, "stale": True, "message": ""})
    assert pf.run([]) == 1
    assert _statuses(pf)["Backups"] == "FAIL"


def test_a_stale_backup_blocks(pf, monkeypatch):
    import models.backup as bk
    monkeypatch.setattr(bk, "health",
                        lambda: {"has_backup": True, "stale": True,
                                 "message": "last backup was 9 days ago"})
    assert pf.run([]) == 1
    assert _statuses(pf)["Backups"] == "FAIL"


def test_an_unreadable_backup_state_blocks_rather_than_passing(pf, monkeypatch):
    """If it cannot tell, it must not say yes."""
    import models.backup as bk
    def explode():
        raise OSError("backup dir is gone")
    monkeypatch.setattr(bk, "health", explode)
    assert pf.run([]) == 1


def _statuses(mod):
    return {name: status for status, name, _ in mod._results}


def test_a_healthy_deployment_passes(pf, capsys):
    rc = pf.run([])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "FAIL" not in out


# ── the checks that must block ────────────────────────────────────────────────

def test_an_unset_signing_key_blocks(pf, monkeypatch, capsys):
    """Session cookies are signed with it. Unset means the published key,
    which means anyone can mint a cookie that says they own the clinic."""
    monkeypatch.delenv("PLATFORM_SECRET_KEY", raising=False)
    assert pf.run([]) == 1
    assert _statuses(pf)["Signing key set"] == "FAIL"


def test_the_shipped_development_key_blocks(pf, monkeypatch):
    monkeypatch.setenv("PLATFORM_SECRET_KEY",
                       "dev-only-key-CHANGE-IN-PRODUCTION-please")
    assert pf.run([]) == 1
    assert _statuses(pf)["Signing key set"] == "FAIL"


def test_a_short_signing_key_blocks(pf, monkeypatch):
    monkeypatch.setenv("PLATFORM_SECRET_KEY", "tooshort")
    assert pf.run([]) == 1


def test_a_non_production_flask_env_blocks(pf, monkeypatch):
    """Production validation is skipped unless FLASK_ENV is exactly
    'production', so forgetting it is how an insecure deployment happens."""
    monkeypatch.setenv("FLASK_ENV", "development")
    assert pf.run([]) == 1
    assert _statuses(pf)["FLASK_ENV=production"] == "FAIL"


def test_insecure_cookies_block(pf, monkeypatch):
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    assert pf.run([]) == 1


def test_a_wildcard_cors_origin_blocks(pf, monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "*")
    assert pf.run([]) == 1


def test_an_unset_cors_origin_blocks(pf, monkeypatch):
    """Unset is a live wildcard, not a safe default."""
    monkeypatch.delenv("CORS_ALLOWED_ORIGIN", raising=False)
    assert pf.run([]) == 1


def test_an_explicit_wildcard_escape_hatch_is_allowed(pf, monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGIN", "*")
    monkeypatch.setenv("CORS_ALLOW_WILDCARD", "1")
    pf.run([])
    assert _statuses(pf)["Public API CORS"] == "OK"


def test_a_weak_seed_admin_password_blocks(pf, monkeypatch):
    monkeypatch.setenv("PLATFORM_ADMIN_PASS", "admin")
    assert pf.run([]) == 1


# ── warnings must not block, but must be visible ─────────────────────────────

def test_sqlite_is_a_warning_not_a_failure(pf, capsys):
    """One clinic on one machine is a legitimate deployment."""
    pf.run([])
    assert _statuses(pf).get("Using PostgreSQL") == "WARN"
    assert "SQLite" in capsys.readouterr().out


def test_strict_turns_warnings_into_a_failure(pf):
    assert pf.run([]) == 0
    assert pf.run(["--strict"]) == 1


def test_a_check_that_itself_errors_is_reported_not_swallowed(pf, monkeypatch):
    """A preflight that silently skips a check is worse than no preflight."""
    def explode():
        raise RuntimeError("boom")
    monkeypatch.setattr(pf, "CHECKS", [explode])
    assert pf.run([]) == 1
    assert any(s == "FAIL" for s, _, _ in pf._results)


# ── it has to look where the server actually looks ───────────────────────────
#
# Found on the live demo server: preflight reported "no backup has ever been
# taken" and "no clinics registered" on a box that had a verified backup and a
# registered clinic. models.backup and models.tenancy keep their target in
# module globals that only create_app() sets, and preflight never builds an
# app -- so both checks ran against an unconfigured module and failed shut.
#
# Failing shut is the right default. Failing shut ALWAYS is a gate people
# learn to ignore, which is the same as having no gate at all.

def test_preflight_configures_backup_where_create_app_does(pf, tmp_path):
    import models.backup as bk
    pf._configure_like_the_app()
    assert bk._backup_dir == os.path.join(str(tmp_path), "backups")
    assert bk._db_path == str(tmp_path / "platform.db")


def test_preflight_configures_the_tenant_registry(pf, tmp_path):
    from models import tenancy
    pf._configure_like_the_app()
    assert tenancy._registry_path == os.path.join(str(tmp_path), "tenants.db")


def test_registered_clinics_are_reported_not_missed(pf, tmp_path):
    from models import tenancy
    tenancy.configure(str(tmp_path / "tenants.db"))
    with tenancy._registry() as conn:
        conn.execute(
            "INSERT INTO tenants (slug,name,db_path,status) VALUES (?,?,?,?)",
            ("demo", "Demo Clinic", str(tmp_path / "demo.db"), "active"))
        conn.commit()
    pf.run([])
    assert _statuses(pf).get("Clinics registered") == "OK"


def test_backups_are_checked_per_clinic_not_once_for_the_server(pf, tmp_path,
                                                               monkeypatch):
    """Two clinics, one backed up. The server "has a backup" either way; the
    clinic that does not must still be named and must still block."""
    from models import tenancy
    import models.backup as bk
    tenancy.configure(str(tmp_path / "tenants.db"))
    with tenancy._registry() as conn:
        for slug in ("backedup", "forgotten"):
            conn.execute(
                "INSERT INTO tenants (slug,name,db_path,status) VALUES (?,?,?,?)",
                (slug, slug, str(tmp_path / f"{slug}.db"), "active"))
        conn.commit()

    monkeypatch.setattr(bk, "health", lambda: (
        {"has_backup": True, "stale": False, "message": "1 hour ago"}
        if bk._backup_dir.endswith("backedup")
        else {"has_backup": False, "stale": True, "message": ""}))

    rc = pf.run([])
    st = _statuses(pf)
    assert st.get("Backups: backedup") == "OK"
    assert st.get("Backups: forgotten") == "FAIL"
    assert rc == 1, "a clinic with no backup at all must block go-live"
