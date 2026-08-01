# -*- coding: utf-8 -*-
"""roles.permissions_json actually governs access.

Until now it governed nothing. The machinery — has_permission,
permission_required, the Roles admin screen, db.ALL_PERMISSIONS — was all
present and correct, and `permission_required` appeared on exactly zero routes;
its only occurrence in the whole codebase was inside its own docstring. An
administrator who unticked "Invoicing" for the reception role saw the change
saved, and reception kept full access to invoicing.

That is worse than having no permissions screen at all: it tells the person
responsible for access control that they have restricted something when they
have not.
"""
import json

import pytest

import models.database as db
from blueprints.auth.routes import _permission_for, _perm_cache


@pytest.fixture(autouse=True)
def _isolate_permissions(app):
    """Clear the 60s grant cache AND restore every role afterwards.

    The cache alone was not enough. These tests rewrite roles.permissions_json,
    the database is shared for the whole session, and leaving a role mutated
    changed the outcome of tests in other files that ran later — which showed up
    as a failure in test_system_routes that passed perfectly on its own. A test
    that breaks a different file is worse than no test.
    """
    _perm_cache.clear()
    with app.app_context():
        conn = db.get_db()
        before = {r["name"]: r["permissions_json"]
                  for r in conn.execute("SELECT name, permissions_json FROM roles")}
        conn.close()
    yield
    with app.app_context():
        conn = db.get_db()
        with conn:
            for name, perms in before.items():
                conn.execute("UPDATE roles SET permissions_json=? WHERE name=?",
                             (perms, name))
        conn.close()
    _perm_cache.clear()


def _set_permissions(app, role, perms):
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE roles SET permissions_json=? WHERE name=?",
                         (json.dumps(perms), role))
        conn.close()
    _perm_cache.clear()


def _as(client, role):
    with client.session_transaction() as s:
        s["user"] = {"id": 99, "username": "t", "full_name": "T", "role": role}
        s["lang"] = "en"


# ── the claim ────────────────────────────────────────────────────────────────

def test_revoking_a_permission_actually_denies_access(app, client):
    """The whole point. Reception can reach invoicing; revoke it; it cannot."""
    _set_permissions(app, "reception", ["patients", "appointments", "invoicing"])
    _as(client, "reception")
    assert client.get("/finance/").status_code == 200, "setup: reception should start with access"

    _set_permissions(app, "reception", ["patients", "appointments"])
    r = client.get("/finance/", follow_redirects=False)
    assert r.status_code in (302, 403), \
        "revoking Invoicing changed nothing — the Roles screen is lying to administrators"


def test_granting_a_permission_restores_access(app, client):
    _set_permissions(app, "reception", ["patients"])
    _as(client, "reception")
    assert client.get("/finance/", follow_redirects=False).status_code in (302, 403)
    _set_permissions(app, "reception", ["patients", "invoicing"])
    assert client.get("/finance/").status_code == 200


# ── the ways this could go wrong, which matter more than the happy path ──────

def test_a_role_with_no_permission_data_keeps_working(app, client):
    """An empty grant list means "no data", never "deny all".

    Every role shipped with '[]'. If empty meant deny, the first restart after
    this change would lock a live clinic out of its own system.
    """
    _set_permissions(app, "reception", [])
    _as(client, "reception")
    assert client.get("/crm/owners").status_code == 200, \
        "an empty grant list locked out a role that worked before the upgrade"


def test_super_admin_is_never_locked_out(app, client):
    _set_permissions(app, "super_admin", [])
    _as(client, "super_admin")
    assert client.get("/finance/").status_code == 200


def test_a_grant_can_only_NARROW_never_widen(app, client):
    """The two gates are not interchangeable, and treating them as such was a
    real bug caught by the existing suite.

    Grant keys are per MODULE. Routes inside one module differ enormously in
    blast radius — deleting a WhatsApp template and reading the message log are
    both "whatsapp". An earlier version of this change let the grant REPLACE
    the route's role list, which handed every receptionist the destructive
    routes; test_whatsapp_routes put it plainly: "a receptionist deleted a
    template".

    So: the grant decides which modules you may enter. The route's role list
    still decides what you may do once inside. Both must pass.
    """
    _set_permissions(app, "groomer", [k for k, _ in db.ALL_PERMISSIONS])
    _as(client, "groomer")
    assert client.get("/payroll/", follow_redirects=False).status_code in (302, 403), \
        "granting every permission escalated a groomer into payroll"


def test_the_verified_hole_is_closed(app, client):
    """The concrete finding: a groomer could open the clinic's accounts, its
    purchase orders and its stock. 271 of 376 routes carried only
    @login_required, with no role gate at all."""
    _set_permissions(app, "groomer", db.DEFAULT_ROLE_PERMISSIONS["groomer"])
    _as(client, "groomer")
    for url in ("/accounting/", "/inventory/", "/procurement/", "/finance/"):
        assert client.get(url, follow_redirects=False).status_code in (302, 403), \
            f"a groomer can still open {url}"


def test_self_service_routes_stay_open_without_the_module_grant(app, client):
    """A nurse has no "payroll" grant and must still reach her own payslip.

    "payroll" means may-administer-payroll. Reading your own payslip is not
    administering anything, and gating it behind the module grant locked every
    employee out of their own records — five tests said so by name.
    """
    _set_permissions(app, "nurse", db.DEFAULT_ROLE_PERMISSIONS["nurse"])
    assert "payroll" not in db.DEFAULT_ROLE_PERMISSIONS["nurse"], "premise changed"
    _as(client, "nurse")
    assert client.get("/payroll/salaries", follow_redirects=False).status_code == 200, \
        "an employee cannot reach their own salary record"


def test_self_service_does_NOT_open_the_payroll_admin_screens(app, client):
    """The exemption must stay narrow: it skips the module grant, nothing else.
    The admin routes are still gated by their own role list."""
    _set_permissions(app, "nurse", db.DEFAULT_ROLE_PERMISSIONS["nurse"])
    _as(client, "nurse")
    for url in ("/payroll/", "/payroll/salaries/new"):
        assert client.get(url, follow_redirects=False).status_code in (302, 403), \
            f"a nurse reached the payroll admin screen {url}"


def test_defaults_do_not_overwrite_an_administrators_own_choices(app):
    """Re-running the seeder on every start must not undo the Roles screen."""
    _set_permissions(app, "nurse", ["patients"])
    with app.app_context():
        conn = db.get_db()
        with conn:
            db.seed_default_permissions(conn)
        row = conn.execute(
            "SELECT permissions_json FROM roles WHERE name='nurse'").fetchone()
        conn.close()
    assert json.loads(row[0]) == ["patients"], \
        "the seeder overwrote an administrator's configuration"


def test_a_module_with_no_grantable_key_is_not_silently_denied(app):
    """A blueprint the Roles screen cannot grant must fall back to roles.
    Enforcing against a key no administrator can tick would deny access to a
    permission that is impossible to give."""
    assert _permission_for("nosuchmodule") == ""
    assert _permission_for("") == ""


@pytest.mark.parametrize("blueprint,key", [
    ("crm",          "patients"),      # names differ
    ("finance",      "invoicing"),     # names differ
    ("ai_assistant", "ai"),
    ("clinical",     "visits"),
    ("doctor",       "visits"),
    ("pharmacy",     "pharmacy"),      # names match
    ("payroll",      "payroll"),       # newly grantable
    ("inpatient",    "inpatient"),
    ("telemedicine", "telemedicine"),
    ("imaging",      "imaging"),
    ("petshop",      "petshop"),
])
def test_blueprint_maps_to_the_right_grant_key(blueprint, key):
    assert _permission_for(blueprint) == key


def test_every_mapped_key_really_exists(app):
    """A typo in the map would silently disable enforcement for that module —
    _permission_for returns "" for an unknown key, which falls back to roles."""
    from blueprints.auth.routes import _BP_PERMISSION
    known = {k for k, _ in db.ALL_PERMISSIONS}
    for bp, key in _BP_PERMISSION.items():
        assert key in known, f"{bp} maps to {key!r}, which is not a real permission"


def test_the_five_modules_that_had_no_key_now_have_one(app):
    """These existed with nothing in ALL_PERMISSIONS, so an administrator
    revoking everything still left them wide open with no way to say so."""
    known = {k for k, _ in db.ALL_PERMISSIONS}
    for key in ("payroll", "inpatient", "telemedicine", "imaging", "petshop"):
        assert key in known
