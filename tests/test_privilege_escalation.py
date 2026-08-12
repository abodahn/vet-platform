"""Nobody may grant themselves more than they have.

From docs/AUDIT_FINDINGS.md:

  "Editing an HR Officer's profile silently promotes them to Super Admin"
  "Any hr / branch_manager / support_admin user can promote themselves to
   super_admin from the Edit Staff form"
  "An account can deactivate and demote itself, including the last
   super_admin, with no warning and no way back in"

Every route that writes users.role is covered here. A staff-edit form is an
access-control surface, not an HR form.
"""
import pytest

from models import database as db

from conftest import get_csrf


def _mk_user(username, role, password="x", active=1):
    conn = db.get_db()
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.execute(
        "INSERT INTO users(username, password_hash, full_name, role, is_active)"
        " VALUES(?,?,?,?,?)",
        (username, db._hash_password(password), username.title(), role, active))
    uid = conn.execute("SELECT id FROM users WHERE username=?",
                       (username,)).fetchone()[0]
    conn.commit()
    conn.close()
    return uid


def _role_of(uid):
    conn = db.get_db()
    row = conn.execute("SELECT role, is_active FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return (row["role"], row["is_active"]) if row else (None, None)


def _login(app, username, password="x"):
    c = app.test_client()
    c.post("/auth/login", data={"username": username, "password": password})
    c.get("/")
    return c


def _edit(client, uid, **fields):
    form = {"username": fields.pop("username", "target"),
            "full_name": "Target", "role": fields.pop("role", "nurse"),
            "is_active": fields.pop("is_active", "1"),
            "_csrf_token": get_csrf(client)}
    form.update(fields)
    return client.post("/hr/staff/%d/edit" % uid, data=form, follow_redirects=True)


# ── the escalation itself ────────────────────────────────────────────────

@pytest.mark.parametrize("attacker_role", ["hr", "branch_manager", "support_admin"])
def test_a_privileged_but_not_admin_user_cannot_mint_a_super_admin(app, attacker_role):
    attacker = "esc_%s" % attacker_role
    _mk_user(attacker, attacker_role, password="Escalate@2026!")
    victim_id = _mk_user("esc_victim_%s" % attacker_role, "nurse")

    c = _login(app, attacker, "Escalate@2026!")
    _edit(c, victim_id, username="esc_victim_%s" % attacker_role,
          role="super_admin")

    role, _ = _role_of(victim_id)
    assert role != "super_admin", \
        "%s minted a super_admin from the staff form" % attacker_role


@pytest.mark.parametrize("attacker_role", ["hr", "branch_manager", "support_admin"])
def test_nobody_can_promote_themselves(app, attacker_role):
    attacker = "self_%s" % attacker_role
    uid = _mk_user(attacker, attacker_role, password="Escalate@2026!")

    c = _login(app, attacker, "Escalate@2026!")
    _edit(c, uid, username=attacker, role="super_admin")

    role, _ = _role_of(uid)
    assert role == attacker_role, \
        "%s promoted itself to %s" % (attacker_role, role)


def test_hr_cannot_grant_a_role_above_its_own(app):
    _mk_user("hr_grant", "hr", password="Escalate@2026!")
    victim_id = _mk_user("hr_grant_victim", "nurse")
    c = _login(app, "hr_grant", "Escalate@2026!")
    for above in ("clinic_owner", "branch_manager", "support_admin"):
        _edit(c, victim_id, username="hr_grant_victim", role=above)
        role, _ = _role_of(victim_id)
        assert role != above, "hr granted %s" % above


def test_hr_can_still_do_its_actual_job(app):
    """The guard must not stop HR managing ordinary staff — that is the job."""
    _mk_user("hr_ok", "hr", password="Escalate@2026!")
    victim_id = _mk_user("hr_ok_victim", "nurse")
    c = _login(app, "hr_ok", "Escalate@2026!")
    _edit(c, victim_id, username="hr_ok_victim", role="reception")
    role, _ = _role_of(victim_id)
    assert role == "reception", "HR can no longer reassign ordinary staff"


def test_a_clinic_owner_may_not_mint_a_super_admin(app):
    """Only a super_admin creates a super_admin. An owner runs the clinic; the
    system-wide role is not theirs to hand out."""
    _mk_user("owner_esc", "clinic_owner", password="Escalate@2026!")
    victim_id = _mk_user("owner_esc_victim", "nurse")
    c = _login(app, "owner_esc", "Escalate@2026!")
    _edit(c, victim_id, username="owner_esc_victim", role="super_admin")
    role, _ = _role_of(victim_id)
    assert role != "super_admin"


def test_a_super_admin_can_still_grant_anything(app, auth_client):
    victim_id = _mk_user("sa_victim", "nurse")
    _edit(auth_client, victim_id, username="sa_victim", role="clinic_owner")
    role, _ = _role_of(victim_id)
    assert role == "clinic_owner", "the real administrator was blocked"


# ── locking yourself, or everyone, out ───────────────────────────────────

def test_an_account_cannot_deactivate_itself(app):
    uid = _mk_user("self_off", "clinic_owner", password="Escalate@2026!")
    c = _login(app, "self_off", "Escalate@2026!")
    _edit(c, uid, username="self_off", role="clinic_owner", is_active="")
    _, active = _role_of(uid)
    assert active == 1, "an account switched itself off"


def test_the_last_super_admin_cannot_be_demoted_or_disabled(app, auth_client):
    """With no super_admin there is no way back into the system."""
    conn = db.get_db()
    admins = [r[0] for r in conn.execute(
        "SELECT id FROM users WHERE role='super_admin' AND is_active=1").fetchall()]
    conn.close()
    assert admins, "the fixture database has no super_admin"

    if len(admins) == 1:
        uid = admins[0]
        _edit(auth_client, uid, username="admin", role="clinic_owner")
        role, active = _role_of(uid)
        assert role == "super_admin" and active == 1, \
            "the last super_admin was removed — nobody can get back in"


def test_the_role_written_must_exist(app, auth_client):
    victim_id = _mk_user("bogus_victim", "nurse")
    _edit(auth_client, victim_id, username="bogus_victim", role="wizard")
    role, _ = _role_of(victim_id)
    assert role == "nurse", "a role that does not exist was assigned (%r)" % role


# ── the OTHER writer of users.role ───────────────────────────────────────

def test_the_roles_screen_enforces_the_same_rules(app):
    """A rule enforced on one of two writers is not enforced.

    /system/roles/assign writes users.role as well, so every guard the staff
    form applies has to apply here too.
    """
    _mk_user("sys_hr", "hr", password="Escalate@2026!")
    victim = _mk_user("sys_victim", "nurse")
    c = _login(app, "sys_hr", "Escalate@2026!")
    c.post("/system/roles/assign",
           data={"user_id": str(victim), "role": "super_admin",
                 "_csrf_token": get_csrf(c)}, follow_redirects=True)
    role, _ = _role_of(victim)
    assert role != "super_admin", "the roles screen minted a super_admin"


def test_the_roles_screen_refuses_self_promotion(app):
    uid = _mk_user("sys_self", "hr", password="Escalate@2026!")
    c = _login(app, "sys_self", "Escalate@2026!")
    c.post("/system/roles/assign",
           data={"user_id": str(uid), "role": "clinic_owner",
                 "_csrf_token": get_csrf(c)}, follow_redirects=True)
    role, _ = _role_of(uid)
    assert role == "hr", "promoted itself to %s from the roles screen" % role


def test_an_administrator_can_still_assign_from_the_roles_screen(app, auth_client):
    victim = _mk_user("sys_ok_victim", "nurse")
    auth_client.post("/system/roles/assign",
                     data={"user_id": str(victim), "role": "reception",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)
    role, _ = _role_of(victim)
    assert role == "reception", "the real administrator was blocked"


# ── the policy itself, without HTTP ──────────────────────────────────────

def test_only_a_super_admin_makes_a_super_admin():
    from blueprints.auth.routes import may_grant_role
    for actor in ("clinic_owner", "support_admin", "branch_manager", "hr",
                  "finance", "doctor", "nurse", "reception", "", "wizard"):
        assert may_grant_role(actor, "super_admin") is False, \
            "%s could mint a super_admin" % (actor or "<none>")
    assert may_grant_role("super_admin", "super_admin") is True


def test_nobody_grants_above_their_own_rank():
    from blueprints.auth.routes import may_grant_role
    assert may_grant_role("hr", "branch_manager") is False
    assert may_grant_role("branch_manager", "clinic_owner") is False
    assert may_grant_role("finance", "support_admin") is False
    assert may_grant_role("nurse", "doctor") is False, \
        "a nurse manages nobody and grants nothing"
    # ...and the ordinary case still works
    assert may_grant_role("hr", "nurse") is True
    assert may_grant_role("clinic_owner", "branch_manager") is True
    assert may_grant_role("branch_manager", "reception") is True


def test_an_unknown_role_grants_nothing_and_receives_nothing():
    from blueprints.auth.routes import may_grant_role, role_rank
    assert role_rank("wizard") == 0
    assert may_grant_role("wizard", "nurse") is False
    assert may_grant_role("clinic_owner", "wizard") is False
