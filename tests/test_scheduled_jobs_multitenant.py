# -*- coding: utf-8 -*-
"""The nightly jobs run once per clinic.

They did not. Backup, WhatsApp reminders, rate-limit cleanup and log retention
each ran once, against whichever database the process happened to start with.
With twenty clinics that meant nineteen were never backed up and never had a
reminder sent — and the backup job logged SUCCESS, because from where it stood
it had succeeded.

A backup that reports success for nineteen databases it never opened is worse
than no backup at all: it stops anyone looking. That is why these tests count
what actually happened rather than trusting a return value.
"""
import os

import pytest

import models.backup as bk
from models import provisioning, tenancy


@pytest.fixture()
def two_clinics(tmp_path, monkeypatch):
    tenancy.configure(str(tmp_path / "tenants.db"))
    monkeypatch.delenv("PLATFORM_TENANT", raising=False)
    d = str(tmp_path / "tenants")
    provisioning.provision("alpha", "Alpha Vet", "admin", "AlphaPass@2026", db_dir=d)
    provisioning.provision("beta", "Beta Vet", "admin", "BetaPass@2026", db_dir=d)
    yield ["alpha", "beta"]
    tenancy.configure("")


def test_each_clinic_yields_every_registered_clinic(two_clinics):
    seen = [slug for slug, _ in tenancy.each_clinic()]
    assert sorted(seen) == ["alpha", "beta"]


def test_each_clinic_selects_that_clinic_while_yielding(two_clinics):
    """Not merely a list of names: the job body must already be scoped, or it
    would back up the default database twice under two clinic names."""
    for slug, _row in tenancy.each_clinic():
        assert tenancy.current() == slug


def test_a_single_clinic_install_still_runs_its_jobs(tmp_path, monkeypatch):
    """With no tenants registered the loop must yield exactly once, or every
    existing single-clinic deployment would silently stop backing up."""
    tenancy.configure(str(tmp_path / "empty.db"))
    monkeypatch.delenv("PLATFORM_TENANT", raising=False)
    try:
        seen = list(tenancy.each_clinic())
    finally:
        tenancy.configure("")
    assert seen == [("", {})]


# ── backup targets ───────────────────────────────────────────────────────────

def test_each_clinic_gets_its_own_archive_directory(tmp_path, two_clinics):
    """Sharing one directory is worse than untidy: retention purges by AGE
    across the whole directory, so the clinic that backs up most often would
    delete the archives of the ones that do not."""
    base = str(tmp_path / "backups")
    bk.configure(db_path=str(tmp_path / "default.db"), backup_dir=base)

    dirs = {}
    for slug, row in tenancy.each_clinic():
        with bk.for_clinic(slug, row.get("db_path", ""), row.get("pg_dsn", "")):
            dirs[slug] = bk._backup_dir
    assert dirs["alpha"] != dirs["beta"], "two clinics share one archive directory"
    assert dirs["alpha"].endswith("alpha") and dirs["beta"].endswith("beta")
    assert bk._backup_dir == base, "the target was not restored after the block"


def test_backup_points_at_the_right_database_per_clinic(tmp_path, two_clinics):
    base = str(tmp_path / "backups")
    bk.configure(db_path=str(tmp_path / "default.db"), backup_dir=base)
    paths = {}
    for slug, row in tenancy.each_clinic():
        with bk.for_clinic(slug, row.get("db_path", ""), row.get("pg_dsn", "")):
            paths[slug] = bk._db_path
    assert paths["alpha"] != paths["beta"]
    assert "alpha" in paths["alpha"] and "beta" in paths["beta"]


def test_a_per_clinic_dsn_wins_over_the_deployment_one(tmp_path, monkeypatch):
    """The most dangerous possible outcome, if this is wrong: the process-wide
    POSTGRES_DSN would dump the SAME database N times under N clinic names, and
    every archive would look present and correct."""
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://u:p@host:5432/deployment_db")
    bk.configure(db_path="", backup_dir=str(tmp_path / "b"))
    assert "deployment_db" in bk._postgres_dsn()
    with bk.for_clinic("alpha", "", "postgresql://u:p@host:5432/alpha_db"):
        assert "alpha_db" in bk._postgres_dsn(), \
            "a clinic's own database was ignored in favour of the deployment's"
    assert "deployment_db" in bk._postgres_dsn(), "the DSN was not restored"


def test_the_target_is_restored_even_when_the_block_raises(tmp_path):
    """A failure mid-loop must not leave the next clinic — or the manual backup
    button — pointed at somebody else's database."""
    base = str(tmp_path / "backups")
    bk.configure(db_path=str(tmp_path / "default.db"), backup_dir=base)
    with pytest.raises(RuntimeError):
        with bk.for_clinic("alpha", str(tmp_path / "alpha.db"), ""):
            raise RuntimeError("boom")
    assert bk._backup_dir == base
    assert bk._db_path == str(tmp_path / "default.db")


# ── one clinic failing must not stop the rest ────────────────────────────────

def test_one_clinic_failing_does_not_skip_the_others(two_clinics):
    """The order is stable, so a raise inside the loop would mean the SAME
    clinics lose their backup every single night."""
    attempted = []

    def job():
        for slug, _row in tenancy.each_clinic():
            try:
                attempted.append(slug)
                if slug == "alpha":
                    raise RuntimeError("alpha's disk is full")
            except Exception:
                continue
    job()
    assert sorted(attempted) == ["alpha", "beta"], \
        "a failure on one clinic stopped the loop"
