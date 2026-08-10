"""Backup reporting must answer about the CLINIC, not the deployment.

The nightly job writes each clinic's archives into <backup_dir>/<slug> via
backup.for_clinic(). Every reporting path — /healthz, the backup page, the
pre-import safety check — read <backup_dir> itself, so they answered about a
database no clinic owns.

On the live demo that showed as "backup stale, 60 hours" permanently, while the
clinic's real backup was four hours old. An alarm that is always on is worse
than no alarm.
"""
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import models.backup as bk


SLUG = "scopetest"


def _archive(directory, when):
    """A file named the way _stamp_of() parses, so age is read from the name."""
    Path(directory).mkdir(parents=True, exist_ok=True)
    name = "platform_backup_%s.dump" % when.strftime("%Y%m%d_%H%M%S")
    p = Path(directory) / name
    p.write_bytes(b"not a real dump, only the name and mtime matter")
    os.utime(p, (when.timestamp(), when.timestamp()))
    return p


@pytest.fixture
def two_dirs(tmp_path, monkeypatch):
    """A deployment directory with a STALE archive, and a clinic one that is fresh."""
    root = tmp_path / "backups"
    monkeypatch.setattr(bk, "_backup_dir", str(root))
    monkeypatch.setattr(bk, "_db_path", str(tmp_path / "platform.db"))
    monkeypatch.setattr(bk, "_tenant_dsn", "")
    _archive(root, datetime.now() - timedelta(hours=60))          # deployment
    _archive(root / SLUG, datetime.now() - timedelta(hours=4))    # the clinic
    return root


def test_unscoped_health_sees_the_stale_deployment_archive(two_dirs):
    """The behaviour that produced the false alarm — pinned so it stays visible."""
    h = bk.health()
    assert h["has_backup"] is True
    assert h["age_hours"] > 48
    assert h["stale"] is True


def test_scoped_to_the_clinic_the_backup_is_fresh(two_dirs):
    with bk.for_clinic(SLUG, db_path="", pg_dsn=""):
        h = bk.health()
    assert h["age_hours"] < 6, "the clinic's own archive is four hours old"
    assert h["stale"] is False
    assert h["ok"] is True


def test_for_current_clinic_follows_the_resolved_tenant(two_dirs, monkeypatch):
    from models import tenancy
    monkeypatch.setattr(tenancy, "current", lambda: SLUG)
    monkeypatch.setattr(tenancy, "target", lambda slug=None: {"db_path": ""})
    with bk.for_current_clinic():
        h = bk.health()
    assert h["stale"] is False, "for_current_clinic did not follow the tenant"


def test_a_single_clinic_install_is_unaffected(two_dirs, monkeypatch):
    """No slug means no scoping — the behaviour every single-clinic box has."""
    from models import tenancy
    monkeypatch.setattr(tenancy, "current", lambda: "")
    before = bk._backup_dir
    with bk.for_current_clinic():
        assert bk._backup_dir == before
        assert bk.health()["stale"] is True
    assert bk._backup_dir == before


def test_it_restores_the_target_even_when_the_body_raises(two_dirs, monkeypatch):
    """A failure inside must not leave the module aimed at somebody else's data."""
    from models import tenancy
    monkeypatch.setattr(tenancy, "current", lambda: SLUG)
    monkeypatch.setattr(tenancy, "target", lambda slug=None: {"db_path": ""})
    before = bk._backup_dir
    with pytest.raises(RuntimeError):
        with bk.for_current_clinic():
            assert bk._backup_dir != before
            raise RuntimeError("boom")
    assert bk._backup_dir == before


def test_an_unreadable_registry_does_not_break_the_health_probe(two_dirs, monkeypatch):
    """/healthz must answer even when tenancy cannot."""
    from models import tenancy

    def explode():
        raise OSError("registry gone")

    monkeypatch.setattr(tenancy, "current", explode)
    before = bk._backup_dir
    with bk.for_current_clinic():
        assert bk._backup_dir == before
        assert bk.health()["has_backup"] is True


def test_healthz_reports_the_clinic_not_the_deployment(client, two_dirs, monkeypatch):
    """End to end: the probe a human reads."""
    from models import tenancy
    monkeypatch.setattr(tenancy, "current", lambda: SLUG)
    monkeypatch.setattr(tenancy, "target", lambda slug=None: {"db_path": ""})
    body = client.get("/healthz").get_json()
    assert "backup" not in (body.get("degraded") or []), \
        "the probe still reports the deployment's stale archive"


# ── unrelated to backups, but the same shape: reading the clock twice ────


def test_boarding_checkout_reads_the_clock_once(monkeypatch):
    """A checkout crossing midnight must not bill an extra night.

    blueprints/boarding/routes.py stamped actual_checkout from one date.today()
    and counted nights from another. Between the two calls the day can roll
    over — which it did, in a long test run — leaving the booking dated
    yesterday and billed against today: one extra night, at the exact hour
    nobody is checking.
    """
    import ast
    import inspect

    from blueprints.boarding import routes as boarding

    # Count real calls in the parsed function, not occurrences in the text —
    # the comment explaining this very fix mentions date.today() twice.
    tree = ast.parse(inspect.getsource(boarding.checkout))
    calls = sum(
        1 for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute) and n.func.attr == "today"
    )
    assert calls == 1, (
        "checkout() calls date.today() %d times; it must read the clock once "
        "and reuse it, or a midnight checkout bills an extra night" % calls)
