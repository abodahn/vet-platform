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
