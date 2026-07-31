# -*- coding: utf-8 -*-
"""Multi-tenancy — one deployment, many clinics.

The point of this file is the isolation test. Everything else here supports it.

Isolation is the whole reason database-per-tenant was chosen over a clinic_id
column: with row-level tenancy, one forgotten WHERE in any of ~400 queries
silently shows one clinic another clinic's patients, and no test can prove all
400 remembered. Here the boundary is physical, and this file proves it holds
for real records written through the real code path.
"""
import os

import pytest

import models.database as db
from models import provisioning, tenancy


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A throwaway registry. Never touches the developer's own data/ dir."""
    tenancy.configure(str(tmp_path / "tenants.db"))
    monkeypatch.delenv("PLATFORM_TENANT", raising=False)
    yield tmp_path
    tenancy.configure("")


@pytest.fixture()
def two_clinics(registry):
    """Two provisioned clinics, each with its own database."""
    d = str(registry / "tenants")
    provisioning.provision("nilevet", "Nile Vet Hospital",
                           "admin", "NileAdmin@2026", db_dir=d)
    provisioning.provision("deltavet", "Delta Animal Care",
                           "admin", "DeltaAdmin@2026", db_dir=d)
    return "nilevet", "deltavet"


# ── the one that matters ─────────────────────────────────────────────────────

def test_one_clinic_cannot_see_another_clinics_patients(two_clinics):
    """The isolation guarantee, on real rows through the real query path."""
    a, b = two_clinics

    with tenancy.use(a):
        conn = db.get_db()
        with conn:
            conn.execute(
                "INSERT INTO owners(full_name, phone) VALUES(?,?)",
                ("Mahmoud Salah", "01000000001"))
        conn.close()

    with tenancy.use(b):
        conn = db.get_db()
        rows = conn.execute("SELECT full_name FROM owners").fetchall()
        conn.close()
    assert [r["full_name"] for r in rows] == [], \
        "clinic B can read clinic A's client list"

    # ...and A still has its own.
    with tenancy.use(a):
        conn = db.get_db()
        rows = conn.execute("SELECT full_name FROM owners").fetchall()
        conn.close()
    assert [r["full_name"] for r in rows] == ["Mahmoud Salah"]


def test_clinic_identity_does_not_leak_through_the_cache(two_clinics):
    """get_clinic() is cached for 5 minutes in a dict shared by every clinic.

    Before the cache key was namespaced, the first clinic to load a page put
    its row under 'clinic_row' and the next clinic read it straight back —
    showing one clinic another clinic's name, logo and tagline on every screen
    and in the installed PWA icon. A leak with no query involved at all.
    """
    a, b = two_clinics
    with tenancy.use(a):
        assert db.get_clinic()["name"] == "Nile Vet Hospital"
    with tenancy.use(b):
        assert db.get_clinic()["name"] == "Delta Animal Care", \
            "clinic B is being shown clinic A's identity from the cache"
    with tenancy.use(a):
        assert db.get_clinic()["name"] == "Nile Vet Hospital"


def test_lazily_created_tables_exist_for_the_SECOND_clinic(two_clinics):
    """Five modules build their tables on first use behind a process-wide flag.

    A flag that only records "already ran" latches on whichever clinic loaded
    first, leaving every clinic provisioned afterwards without those tables —
    invisible until a second tenant exists, which is exactly why this test does
    the work in first-clinic-then-second order.
    """
    import models.security as sec
    a, b = two_clinics
    for slug in (a, b):
        with tenancy.use(slug):
            sec._ensure_tables()
            conn = db.get_db()
            got = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='login_attempts'").fetchone()
            conn.close()
            assert got, f"{slug} has no login_attempts table: rate limiting is dead there"


# ── resolution ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("host,want", [
    ("nilevet.aleefy.online",       "nilevet"),
    ("nilevet.aleefy.online:5100",  "nilevet"),
    ("NileVet.Aleefy.Online",       "nilevet"),
    ("aleefy.online",               ""),      # no subdomain
    ("www.aleefy.online",           ""),      # reserved
    ("api.aleefy.online",           ""),      # reserved
    ("localhost",                   ""),
    ("localhost:5100",              ""),
    ("127.0.0.1:5100",              ""),      # an IP is not a tenant
    ("10.0.0.5",                    ""),      # ...nor a private-range one
    ("[::1]:5100",                  ""),      # ...nor IPv6
    ("",                            ""),
    ("-bad.aleefy.online",          ""),      # invalid slug shape
])
def test_slug_from_host(host, want):
    assert tenancy.slug_from_host(host) == want


def test_an_unknown_subdomain_is_refused_not_silently_defaulted(two_clinics):
    """The most dangerous possible failure: an unrecognised subdomain falling
    through to the default database would serve a real clinic's records under
    a stranger's address."""
    with tenancy.use("nosuchclinic"):
        with pytest.raises(tenancy.UnknownTenant):
            tenancy.target()


def test_a_suspended_clinic_is_refused(two_clinics):
    a, _ = two_clinics
    tenancy.set_status(a, "suspended")
    with tenancy.use(a):
        with pytest.raises(tenancy.TenantSuspended):
            tenancy.target()
    tenancy.set_status(a, "active")


def test_use_restores_the_previous_tenant_even_on_exception(two_clinics):
    """A worker thread pinned to the wrong clinic after an error would serve
    the next request from the wrong database."""
    a, b = two_clinics
    with tenancy.use(a):
        with pytest.raises(RuntimeError):
            with tenancy.use(b):
                raise RuntimeError("boom")
        assert tenancy.current() == a


# ── provisioning ─────────────────────────────────────────────────────────────

def test_provisioning_builds_a_usable_clinic(registry):
    row = provisioning.provision("cairovet", "Cairo Vet Clinic",
                                 "admin", "CairoAdmin@2026",
                                 db_dir=str(registry / "tenants"))
    assert row["slug"] == "cairovet" and row["status"] == "active"
    assert os.path.exists(row["db_path"])
    with tenancy.use("cairovet"):
        conn = db.get_db()
        # The schema is really there, and the clinic is branded as itself.
        assert conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"] >= 1
        assert db.get_clinic()["name"] == "Cairo Vet Clinic"
        conn.close()


@pytest.mark.parametrize("slug", [
    "AB",            # too short
    "-nile",         # leading hyphen
    "nile-",         # trailing hyphen
    "nile vet",      # space
    "nile/vet",      # path separator — would escape the tenants directory
    "../etc",        # traversal
    "www",           # reserved
])
def test_bad_slugs_are_rejected(registry, slug):
    """Slugs become filenames and PostgreSQL database names, so they are
    restricted at the door rather than escaped at every use."""
    with pytest.raises(ValueError):
        tenancy.create(slug, "Some Clinic", db_dir=str(registry))


def test_a_duplicate_slug_is_rejected(two_clinics):
    with pytest.raises(ValueError):
        tenancy.create("nilevet", "Someone Else", db_dir="/tmp")


def test_failed_provisioning_leaves_no_half_made_tenant(registry, monkeypatch):
    """A registry row without a schema would resolve, render a login page, and
    then fail on every query behind it."""
    monkeypatch.setattr(db, "init_db",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("disk full")))
    with pytest.raises(RuntimeError):
        provisioning.provision("doomed", "Doomed Clinic", "admin", "Doomed@2026",
                               db_dir=str(registry / "tenants"))
    assert tenancy.get("doomed") == {}, "a half-provisioned tenant was left behind"


def test_a_weak_first_admin_password_is_refused(registry):
    """This account owns a clinic's entire medical record."""
    with pytest.raises(ValueError):
        provisioning.provision("weakvet", "Weak Clinic", "admin", "123",
                               db_dir=str(registry / "tenants"))


# ── backwards compatibility ──────────────────────────────────────────────────

def test_with_no_tenants_registered_nothing_changes(registry):
    """The existing 1,300-test suite runs in exactly this mode. If resolution
    ever started returning a tenant for a plain host, all of it would break."""
    assert tenancy.enabled() is False
    assert tenancy.current() == ""
    assert tenancy.target() == {}, "legacy mode must use the configured default DB"
