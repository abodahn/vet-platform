# -*- coding: utf-8 -*-
"""The 'add a clinic' command.

provisioning.provision() could always do this, but nothing outside the test
suite could reach it, so creating a clinic meant importing internals correctly
in a Python shell on a live server. This is the entry point that makes it an
operation instead of a procedure.

What matters:

  - it actually creates a usable clinic (registry row AND schema);
  - it REFUSES an existing slug rather than rebuilding the schema over a
    clinic's live records;
  - the generated password is strong and is not written anywhere;
  - a failure leaves nothing half-made.
"""
import importlib.util
import os
import sys

import pytest

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CLI = os.path.join(_PLATFORM, "scripts", "add_clinic.py")

import models.database as db
from models import tenancy


def _load():
    spec = importlib.util.spec_from_file_location("add_clinic", _CLI)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["add_clinic"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    monkeypatch.delenv("PLATFORM_TENANT", raising=False)
    tenancy.configure(str(tmp_path / "tenants.db"))
    mod = _load()
    yield mod, str(tmp_path / "dbs")
    tenancy.configure("")


def _run(mod, registry_args):
    return mod.main(registry_args)


def test_it_creates_a_usable_clinic(cli, capsys):
    mod, db_dir = cli
    rc = _run(mod, ["--slug", "nilevet", "--name", "Nile Vet", "--db-dir", db_dir])
    assert rc == 0
    row = tenancy.get("nilevet")
    assert row, "no registry row was created"
    # A registry row alone is the dangerous half-state: the subdomain resolves
    # and every query behind it fails. The schema must exist too.
    with tenancy.use("nilevet"):
        conn = db.get_db()
        try:
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 1
            assert conn.execute("SELECT name FROM clinic").fetchone()[0] == "Nile Vet"
        finally:
            conn.close()


def test_it_prints_the_password_exactly_once(cli, capsys):
    mod, db_dir = cli
    _run(mod, ["--slug", "alfa", "--name", "Alfa", "--db-dir", db_dir])
    out = capsys.readouterr().out
    assert "Password  :" in out
    assert "shown once" in out


def test_the_generated_password_is_strong(cli):
    mod, _ = cli
    pw = mod._password()
    assert len(pw) >= 16
    assert len(set(pw)) >= 8, "generated password has too little variety"
    assert mod._password() != mod._password(), "password generator is deterministic"


def test_an_existing_slug_is_refused_not_overwritten(cli, capsys):
    """Re-provisioning would rebuild the schema over a clinic's live records."""
    mod, db_dir = cli
    _run(mod, ["--slug", "dup", "--name", "First", "--db-dir", db_dir])
    with tenancy.use("dup"):
        conn = db.get_db()
        with conn:
            conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                         ("Real Client", "0100"))
        conn.close()

    rc = _run(mod, ["--slug", "dup", "--name", "Second", "--db-dir", db_dir])
    assert rc == 1, "a duplicate slug was accepted"
    assert "already exists" in capsys.readouterr().err

    with tenancy.use("dup"):
        conn = db.get_db()
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM owners WHERE full_name='Real Client'"
            ).fetchone()[0] == 1, "the existing clinic's data was destroyed"
        finally:
            conn.close()


def test_a_short_password_is_rejected(cli, capsys):
    """This account owns the clinic's entire medical record."""
    mod, db_dir = cli
    rc = _run(mod, ["--slug", "weak", "--name", "W", "--db-dir", db_dir,
                    "--admin-pass", "123"])
    assert rc == 1
    # get() returns {} for an unknown slug, not None.
    assert not tenancy.get("weak"), "a rejected clinic was left in the registry"


def test_list_shows_registered_clinics(cli, capsys):
    mod, db_dir = cli
    _run(mod, ["--slug", "one", "--name", "One", "--db-dir", db_dir])
    _run(mod, ["--slug", "two", "--name", "Two", "--db-dir", db_dir])
    capsys.readouterr()
    assert _run(mod, ["--list"]) == 0
    out = capsys.readouterr().out
    assert "one" in out and "two" in out


def test_list_is_honest_when_there_are_none(cli, capsys):
    mod, _ = cli
    assert _run(mod, ["--list"]) == 0
    assert "No clinics registered" in capsys.readouterr().out


def test_the_default_registry_matches_the_one_the_app_reads(monkeypatch, tmp_path):
    """Otherwise the clinic lands in a registry the server never opens.

    create_app() derives the registry as dirname(DATABASE_PATH)/tenants.db. If
    this script defaulted to anything else, then the moment PLATFORM_DB_PATH is
    set -- which it always is in production -- add_clinic would write somewhere
    the app does not look, the subdomain would not resolve, and nothing would
    say why.
    """
    # DATABASE_PATH is patched directly rather than by setting PLATFORM_DB_PATH
    # and reloading config. importlib.reload() builds a NEW Config class object,
    # and app.py holds a reference to the old one from its own import -- so a
    # later test that monkeypatches config.Config silently stops affecting
    # create_app(). That cost one confusing PostgreSQL-only failure in a test
    # file with nothing to do with this one.
    import config as config_mod
    from models import tenancy as t
    monkeypatch.setattr(config_mod.Config, "DATABASE_PATH",
                        str(tmp_path / "prod" / "platform.db"), raising=False)
    t.configure("")
    mod = _load()
    try:
        mod._configure_registry("")
        expected = str(tmp_path / "prod" / "tenants.db")
        assert os.path.normpath(t._registry_path) == os.path.normpath(expected)
    finally:
        t.configure("")


def test_the_url_and_certificate_step_are_printed_when_a_domain_is_given(cli, capsys):
    """Handing over a clinic without a certificate is handing over a warning
    page, so the command that creates it names the step."""
    mod, db_dir = cli
    _run(mod, ["--slug", "nile", "--name", "Nile", "--db-dir", db_dir,
               "--domain", "aleefy.online"])
    out = capsys.readouterr().out
    assert "https://nile.aleefy.online" in out
    assert "certbot" in out
