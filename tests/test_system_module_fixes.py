# -*- coding: utf-8 -*-
"""The System module's admin screens, and the four ways they misreported reality.

Each test here failed before the fix in the same commit. They are grouped by
the screen they defend, because that is how they break.
"""
import json
import re

import pytest

import models.database as db
from blueprints.auth.routes import _perm_cache


@pytest.fixture(autouse=True)
def _isolate_permissions(app):
    """Same contract as test_permissions_enforced: clear the grant cache and
    put every role's permissions_json back, so a test here cannot change the
    outcome of a test in another file that runs later.
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


def _as(client, role):
    with client.session_transaction() as s:
        s["user"] = {"id": 91, "username": "sysfix", "full_name": "Sys Fix",
                     "role": role}
        s["lang"] = "en"


def _seed_role(app, role, perms):
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("UPDATE roles SET permissions_json=? WHERE name=?",
                         (json.dumps(perms), role))
        conn.close()
    _perm_cache.clear()


# ── bug-497 · the Audit Log names auditor and then locks it out ──────────────

def test_auditor_can_open_the_audit_log(app, client):
    """/system/audit lists `auditor` in its role gate. It has to mean it.

    The module gate keys the whole /system blueprint on the `system` permission,
    and auditor holds `audit` — so the role named on the route was redirected to
    the launcher with "You don't have permission to access this page."
    """
    _seed_role(app, "auditor", db.DEFAULT_ROLE_PERMISSIONS["auditor"])
    _as(client, "auditor")
    r = client.get("/system/audit", follow_redirects=False)
    assert r.status_code == 200, (
        "auditor is named in @role_required on /system/audit but was denied "
        f"(status {r.status_code}) — the module gate is overruling the route")


def test_auditor_still_cannot_open_the_rest_of_system(app, client):
    """Opening the Audit Log must not open Settings, Backup or the Monitor.

    The lazy fix for the test above — handing auditor the `system` grant —
    would pass it and quietly widen a read-only role into a system
    administrator. This is the test that says no.
    """
    _seed_role(app, "auditor", db.DEFAULT_ROLE_PERMISSIONS["auditor"])
    _as(client, "auditor")
    for path in ("/system/monitor", "/system/settings", "/system/backup",
                 "/system/roles", "/system/diagnostics", "/system/sync"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code in (302, 403), \
            f"a read-only auditor reached {path} (status {r.status_code})"


def test_revoking_audit_still_closes_the_audit_log(app, client):
    """The route reads the `audit` grant, so unticking it has to bite."""
    _seed_role(app, "auditor", ["reports", "accounting"])
    _as(client, "auditor")
    r = client.get("/system/audit", follow_redirects=False)
    assert r.status_code in (302, 403), \
        "the Roles screen says auditor has no Audit Log grant; the page opened anyway"


# ── bug-495 · Keep Local / Keep Server post a token the server never reads ───

_HIDDEN = re.compile(r'<input type="hidden" name="([^"]+)" value="([^"]*)"')


def _conflict_row(app, conflict_id="cf-sysfix-1"):
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM sync_conflicts WHERE id=?", (conflict_id,))
            conn.execute(
                "INSERT INTO sync_conflicts (id, sync_queue_id, entity_name, "
                "local_payload, server_payload, conflict_type, resolution_status) "
                "VALUES (?,?,?,?,?,?,?)",
                (conflict_id, "q-sysfix-1", "owners", '{"name":"local"}',
                 '{"name":"server"}', "UPDATE_UPDATE", "PENDING"))
        conn.close()
    return conflict_id


def test_keep_local_form_carries_the_token_the_server_checks(app, auth_client):
    """Post exactly what the rendered form contains — no JavaScript involved.

    The form shipped `csrf_token`; validate_csrf() reads `_csrf_token`. A shim
    in platform.js papered over it in the browser, which meant the form was one
    disabled script away from a 403 and nobody could see why.
    """
    cid = _conflict_row(app)
    page = auth_client.get("/system/sync")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    assert cid in html, "setup: the conflict did not render"

    form = html.split(f'conflicts/{cid}/resolve')[1]
    fields = dict(_HIDDEN.findall(form))
    r = auth_client.post(f"/system/sync/conflicts/{cid}/resolve", data=fields)
    assert r.status_code != 403, \
        "the Keep Local form's own fields fail CSRF — wrong hidden field name"

    with app.app_context():
        conn = db.get_db()
        status = conn.execute(
            "SELECT resolution_status FROM sync_conflicts WHERE id=?", (cid,)
        ).fetchone()[0]
        conn.close()
    assert status.startswith("MANUAL_RESOLVED"), \
        f"the conflict was never resolved (status {status!r})"


# ── bug-496 · the Monitor's Backup Status card invents its own field names ───

def test_monitor_shows_the_backup_date_it_actually_has(app, auth_client, tmp_path):
    """`latest_backup.created_at` does not exist; the key is `timestamp`.

    Jinja resolved the missing attribute to Undefined, `(Undefined or '')[:16]`
    rendered empty, and the Last Backup row was blank on every clinic that had
    a backup.
    """
    import models.backup as bk

    stamp = "20260101_101112"
    src = tmp_path / "bk"
    src.mkdir()
    archive = src / f"platform_backup_{stamp}.db"
    archive.write_bytes(b"SQLite format 3\x00" + b"\0" * 2048)
    bk._backup_dir = str(src)

    r = auth_client.get("/system/monitor")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    # The File row truncates to 32 chars, so match the stem, not the whole name.
    assert archive.stem[:32] in html, "setup: the backup did not reach the page"
    assert "2026-01-01 10:11" in html, \
        "Last Backup rendered blank — the template reads a field the data has not got"


def test_monitor_does_not_report_a_permanent_unknown(app, auth_client, tmp_path):
    """No backup record carries an `integrity` field, so the badge was always
    a red '?'. A monitoring page that always cries wolf is worse than silent.
    """
    import models.backup as bk

    src = tmp_path / "bk2"
    src.mkdir()
    (src / "platform_backup_20260202_090000.db").write_bytes(
        b"SQLite format 3\x00" + b"\0" * 2048)
    bk._backup_dir = str(src)

    html = auth_client.get("/system/monitor").get_data(as_text=True)
    assert ">?<" not in html, \
        "the Backup Status card still shows an unknown-integrity badge"


# ── bug-084 · GET /system/roles used to 500 on an Undefined role key ─────────

def test_roles_screen_renders(auth_client):
    r = auth_client.get("/system/roles")
    assert r.status_code == 200, \
        "GET /system/roles is 500ing again — a role key the template names is " \
        "missing from _SYSTEM_ROLE_PERMS/_SYSTEM_ROLE_COLORS"
