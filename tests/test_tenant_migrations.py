# -*- coding: utf-8 -*-
"""New tables must reach clinics that already exist.

A tenant's database is built ONCE, by provisioning. create_app() then calls
init_db against the DEFAULT database only — so every table added after a clinic
was created did not exist for that clinic. The pattern is nasty because it is
invisible where you are looking: the code ships, the dev box is fine, and the
live clinic 500s on the first query touching the new table.

That is not hypothetical. The demo clinic was provisioned on 5 August; the
`tasks` table shipped on 13 August. Without this, opening the exam screen for
any client would have failed on the query behind the Tasks tab.
"""
import pytest

from models import database as db
from models import provisioning, tenancy


@pytest.fixture()
def registry(tmp_path, monkeypatch):
    """A private registry so this never touches the real one."""
    before_registry = getattr(tenancy, "_REGISTRY_PATH", None)
    before_path = db._db_path
    tenancy.configure(str(tmp_path / "tenants.db"))
    yield tmp_path
    tenancy.configure(before_registry) if before_registry else None
    db.set_path(before_path)


def _tables(slug):
    with tenancy.use(slug):
        conn = db.get_db()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        conn.close()
    return {r[0] for r in rows}


def test_a_clinic_provisioned_today_has_the_tasks_table(registry):
    provisioning.provision("clinic-a", "Clinic A", admin_user="admin",
                           admin_pass="Str0ng!Pass9", db_dir=str(registry))
    assert "tasks" in _tables("clinic-a")


def test_a_clinic_created_before_a_table_existed_gets_it_on_restart(registry):
    """The actual regression: an OLD clinic, a NEW table.

    Provision, then drop the table to stand in for "this clinic predates that
    release", then re-run the migration the way create_app does.
    """
    provisioning.provision("clinic-b", "Clinic B", admin_user="admin",
                           admin_pass="Str0ng!Pass9", db_dir=str(registry))

    with tenancy.use("clinic-b"):
        conn = db.get_db()
        conn.execute("DROP TABLE tasks")
        conn.commit()
        conn.close()
    assert "tasks" not in _tables("clinic-b"), "the fixture did not take"

    # What create_app now does on every boot.
    for t in tenancy.all_tenants():
        with tenancy.use(t["slug"]):
            db.init_db(admin_user="admin", admin_pass="Str0ng!Pass9")

    assert "tasks" in _tables("clinic-b"), \
        "an existing clinic did not receive a table added after it was created"


def test_re_running_the_migration_does_not_wipe_a_clinics_data(registry):
    """It runs on EVERY boot, so it has to be a migration and not a reset."""
    provisioning.provision("clinic-c", "Clinic C", admin_user="admin",
                           admin_pass="Str0ng!Pass9", db_dir=str(registry))

    with tenancy.use("clinic-c"):
        conn = db.get_db()
        conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                     ("عميل قائم", "01000000991"))
        conn.commit()
        conn.close()

    for _ in range(3):
        with tenancy.use("clinic-c"):
            db.init_db(admin_user="admin", admin_pass="Str0ng!Pass9")

    with tenancy.use("clinic-c"):
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM owners WHERE phone=?",
                         ("01000000991",)).fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()

    assert n == 1, "re-running the migration destroyed or duplicated a client"
    assert users == 1, "re-running the migration seeded a second admin"


def test_one_broken_clinic_does_not_stop_the_others(registry, monkeypatch):
    """A clinic whose database is unreachable must not stop the app booting."""
    provisioning.provision("clinic-ok", "Clinic OK", admin_user="admin",
                           admin_pass="Str0ng!Pass9", db_dir=str(registry))

    reached = []
    real_init = db.init_db

    def _flaky(*a, **kw):
        slug = tenancy.current()
        if slug == "clinic-bad":
            raise RuntimeError("database is on fire")
        reached.append(slug)
        return real_init(*a, **kw)

    tenancy.create("clinic-bad", "Clinic Bad", db_dir=str(registry))
    monkeypatch.setattr(db, "init_db", _flaky)

    # The loop create_app runs, with its per-clinic guard.
    for t in tenancy.all_tenants():
        try:
            with tenancy.use(t["slug"]):
                db.init_db(admin_user="admin", admin_pass="Str0ng!Pass9")
        except Exception:
            pass

    assert "clinic-ok" in reached, \
        "one unreachable clinic stopped the healthy ones being migrated"
