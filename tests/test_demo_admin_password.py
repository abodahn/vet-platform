# -*- coding: utf-8 -*-
"""The demo seeder must set the password it prints.

Found while standing the demo server up. The documented order is

    python scripts/add_clinic.py --slug demo --name ... --postgres $DSN
    python scripts/seed/demo_showcase.py --postgres $DSN

and following it produced a demo whose printed credentials did not work:
init_db() only creates the admin when the users table is EMPTY, and
add_clinic.py had just put a row in it. The seeder went on to print
"login: admin / <password>" regardless.

The failure mode is reading that line aloud to a customer and watching it be
rejected.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_PLATFORM, "scripts", "seed"))

import models.database as db  # noqa: E402


def _seed(path, password):
    import demo_showcase
    os.environ["DEMO_ADMIN_PASS"] = password
    try:
        demo_showcase.run(str(path), quiet=True)
    finally:
        os.environ.pop("DEMO_ADMIN_PASS", None)


def _can_sign_in(path, password):
    """Through verify_credentials(), so this asserts on the real login path
    rather than on how the hash happens to be stored."""
    db.use_sqlite(str(path))
    return db.verify_credentials("admin", password) is not None


def test_seeder_sets_the_password_it_prints(tmp_path):
    p = tmp_path / "demo.db"
    _seed(p, "Printed@Password1")
    assert _can_sign_in(p, "Printed@Password1")


def test_it_still_sets_it_when_admin_already_exists(tmp_path):
    """The actual bug: a clinic provisioned first, seeded second."""
    p = tmp_path / "demo.db"
    db.use_sqlite(str(p))
    db.init_db(admin_user="admin", admin_pass="ProvisionedFirst9")
    assert _can_sign_in(p, "ProvisionedFirst9")

    _seed(p, "Printed@Password2")
    assert _can_sign_in(p, "Printed@Password2"), (
        "seeder printed a password it did not set -- the demo credential is a lie")
    assert not _can_sign_in(p, "ProvisionedFirst9")


def test_reseeding_is_idempotent(tmp_path):
    """The demo server re-seeds nightly. The credential must survive that."""
    p = tmp_path / "demo.db"
    _seed(p, "Nightly@Reset3")
    _seed(p, "Nightly@Reset3")
    assert _can_sign_in(p, "Nightly@Reset3")
