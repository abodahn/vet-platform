# -*- coding: utf-8 -*-
"""Five people on one PC, and what stops them overwriting each other.

The clinic has one machine at reception. The vet needs it, then the nurse, then
the owner wants the day's takings. Logging out and back in each time is slow
enough that nobody does it — so everyone works under whichever account happens
to be open, and every "recorded by", "seen by" and per-vet report names the
wrong person. That is invisible afterwards, because the records look ordinary.

So the desk holds up to five signed-in accounts and switching is one click. The
trade is deliberate: anyone at that PC can act as any of the five without a
password. That is the point of the feature — which is exactly why ADDING an
account takes the real password, an account with 2FA is refused outright, and
every switch is written to the audit log.

The second half is the collision. With five accounts on one PC and more on the
next desk, two people editing the same client — or the same attendance record,
which is somebody's pay — is not a rare race.
"""
import pytest

from conftest import get_csrf
from models import database as db

PW = "Str0ng!Pass9"


def _mk(app, username, name, role="nurse"):
    with app.app_context():
        return db.create_user({"username": username, "password": PW,
                               "full_name": name, "role": role})


def _login(client, username):
    return client.post("/auth/login",
                       data={"username": username, "password": PW},
                       follow_redirects=True)


def _who(client):
    with client.session_transaction() as s:
        return (s.get("user") or {}).get("username")


def _desk(client):
    with client.session_transaction() as s:
        return [u.get("username") for u in (s.get("desk") or [])]


# ── the desk ─────────────────────────────────────────────────────────────────

def test_a_second_person_signs_in_without_evicting_the_first(app):
    _mk(app, "desk_a", "Desk A")
    _mk(app, "desk_b", "Desk B")
    c = app.test_client()
    _login(c, "desk_a")

    c.post("/auth/desk/add",
           data={"username": "desk_b", "password": PW, "_csrf_token": get_csrf(c)},
           follow_redirects=True)

    assert set(_desk(c)) == {"desk_a", "desk_b"}, \
        "the desk holds %r" % (_desk(c),)
    assert _who(c) == "desk_a", \
        "adding somebody handed them the screen; it must not change who is active"


def test_adding_a_user_requires_their_real_password(app):
    _mk(app, "desk_c", "Desk C")
    _mk(app, "desk_d", "Desk D")
    c = app.test_client()
    _login(c, "desk_c")

    c.post("/auth/desk/add",
           data={"username": "desk_d", "password": "wrong-password",
                 "_csrf_token": get_csrf(c)}, follow_redirects=True)

    assert "desk_d" not in _desk(c), \
        "a wrong password put somebody on the desk"


def test_switching_needs_no_password_but_changes_who_is_recorded(app):
    _mk(app, "desk_e", "Desk E")
    fid = _mk(app, "desk_f", "Desk F")
    c = app.test_client()
    _login(c, "desk_e")
    c.post("/auth/desk/add",
           data={"username": "desk_f", "password": PW, "_csrf_token": get_csrf(c)},
           follow_redirects=True)

    c.post("/auth/desk/switch/%d" % fid,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)

    assert _who(c) == "desk_f", "the switch did not take"


def test_you_cannot_switch_to_somebody_who_is_not_on_this_desk(app):
    _mk(app, "desk_g", "Desk G")
    stranger = _mk(app, "desk_stranger", "Stranger")
    c = app.test_client()
    _login(c, "desk_g")

    c.post("/auth/desk/switch/%d" % stranger,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)

    assert _who(c) == "desk_g", \
        "switched to an account that never authenticated at this PC"


def test_a_deactivated_account_cannot_be_switched_back_into(app):
    """The stored copy is not trusted for anything but 'they authenticated here'.

    Otherwise deactivating somebody would leave a working copy of their session
    sitting on a reception PC for as long as the cookie lives.
    """
    _mk(app, "desk_h", "Desk H")
    sacked = _mk(app, "desk_sacked", "Sacked")
    c = app.test_client()
    _login(c, "desk_h")
    c.post("/auth/desk/add",
           data={"username": "desk_sacked", "password": PW,
                 "_csrf_token": get_csrf(c)}, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        conn.execute("UPDATE users SET is_active=0 WHERE id=?", (sacked,))
        conn.commit()
        conn.close()

    c.post("/auth/desk/switch/%d" % sacked,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)

    assert _who(c) == "desk_h", "switched into a deactivated account"
    assert "desk_sacked" not in _desk(c), \
        "the deactivated account is still offered on this PC"


def test_the_desk_stops_at_five(app):
    _mk(app, "desk_owner", "Desk Owner")
    c = app.test_client()
    _login(c, "desk_owner")
    for i in range(6):
        _mk(app, "desk_n%d" % i, "Desk N%d" % i)
        c.post("/auth/desk/add",
               data={"username": "desk_n%d" % i, "password": PW,
                     "_csrf_token": get_csrf(c)}, follow_redirects=True)

    from blueprints.auth.routes import MAX_DESK_USERS
    assert len(_desk(c)) <= MAX_DESK_USERS, \
        "the desk grew to %d accounts" % len(_desk(c))


def test_signing_the_last_person_off_is_a_full_logout(app):
    uid = _mk(app, "desk_solo", "Desk Solo")
    c = app.test_client()
    _login(c, "desk_solo")
    c.post("/auth/desk/remove/%d" % uid,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)
    assert _who(c) is None, "a session was left with no user in it"


def test_signing_the_active_person_off_hands_over_to_whoever_is_left(app):
    _mk(app, "desk_i", "Desk I")
    jid = _mk(app, "desk_j", "Desk J")
    c = app.test_client()
    _login(c, "desk_i")
    c.post("/auth/desk/add",
           data={"username": "desk_j", "password": PW, "_csrf_token": get_csrf(c)},
           follow_redirects=True)
    c.post("/auth/desk/switch/%d" % jid,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)

    c.post("/auth/desk/remove/%d" % jid,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)

    assert _who(c) == "desk_i", "nobody took over the screen"
    assert "desk_j" not in _desk(c)


def test_every_switch_is_written_to_the_audit_log(app):
    """The trade for passwordless switching is that it is never invisible."""
    _mk(app, "desk_k", "Desk K")
    lid = _mk(app, "desk_l", "Desk L")
    c = app.test_client()
    _login(c, "desk_k")
    c.post("/auth/desk/add",
           data={"username": "desk_l", "password": PW, "_csrf_token": get_csrf(c)},
           follow_redirects=True)
    c.post("/auth/desk/switch/%d" % lid,
           data={"_csrf_token": get_csrf(c)}, follow_redirects=True)

    with app.app_context():
        conn = db.get_db()
        n = conn.execute(
            "SELECT COUNT(*) FROM audit_log WHERE action IN ('desk_switch','desk_add')"
        ).fetchone()[0]
        conn.close()
    assert n >= 2, "the shared desk leaves no audit trail"


def test_the_desk_needs_a_login(client):
    assert client.get("/auth/desk/add").status_code in (302, 401, 403)


# ── conflicts ────────────────────────────────────────────────────────────────

def test_a_second_save_of_the_same_client_is_refused(app):
    """Last-write-wins is silent data loss; this makes it a message."""
    import models.concurrency as concurrency
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute(
            "INSERT INTO owners(full_name, phone, updated_at)"
            " VALUES(?,?,?)", ("صاحب متنازع", "01000000933", "2026-08-13 10:00:00")
        ).lastrowid
        conn.commit()

        # What the first editor saw when the form opened.
        seen = concurrency.stamp_of(conn, "owners", oid)
        # Somebody else saves in the meantime.
        conn.execute("UPDATE owners SET full_name=?, updated_at=? WHERE id=?",
                     ("اسم من شخص آخر", "2026-08-13 10:05:00", oid))
        conn.commit()

        with pytest.raises(concurrency.StaleRecord):
            concurrency.guard(conn, "owners", oid, seen)
        conn.close()


def test_an_unchanged_record_saves_normally(app):
    import models.concurrency as concurrency
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute(
            "INSERT INTO owners(full_name, phone, updated_at)"
            " VALUES(?,?,?)", ("صاحب هادئ", "01000000934", "2026-08-13 11:00:00")
        ).lastrowid
        conn.commit()
        concurrency.guard(conn, "owners", oid,
                          concurrency.stamp_of(conn, "owners", oid))
        conn.close()


def test_a_form_that_sends_no_stamp_still_works(app):
    """So the guard can be rolled out one screen at a time."""
    import models.concurrency as concurrency
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute(
            "INSERT INTO owners(full_name, phone) VALUES(?,?)",
            ("صاحب قديم", "01000000935")).lastrowid
        conn.commit()
        concurrency.guard(conn, "owners", oid, None)
        concurrency.guard(conn, "owners", oid, "")
        conn.close()


def test_the_table_name_can_never_come_from_a_request(app):
    """guard() builds SQL by concatenation, so the name is allow-listed."""
    import models.concurrency as concurrency
    with app.app_context():
        conn = db.get_db()
        with pytest.raises(ValueError):
            concurrency.stamp_of(conn, "users; DROP TABLE owners", 1)
        conn.close()


def test_the_client_form_carries_the_stamp(auth_client, app):
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute(
            "INSERT INTO owners(full_name, phone) VALUES(?,?)",
            ("صاحب للنموذج", "01000000936")).lastrowid
        conn.commit()
        conn.close()
    body = auth_client.get("/crm/owners/%d/edit" % oid).get_data(as_text=True)
    assert "_seen_updated_at" in body, \
        "the edit form sends no stamp, so the guard can never fire"


def test_a_colliding_client_save_is_refused_end_to_end(auth_client, app):
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute(
            "INSERT INTO owners(full_name, phone, updated_at) VALUES(?,?,?)",
            ("قبل التعارض", "01000000937", "2026-08-13 09:00:00")).lastrowid
        conn.commit()
        conn.close()

    r = auth_client.post("/crm/owners/%d/edit" % oid, data={
        "full_name": "تعديل متأخر", "phone": "01000000937",
        "_seen_updated_at": "2026-08-13 08:00:00",     # stale on purpose
        "_csrf_token": get_csrf(auth_client),
    }, follow_redirects=False)

    assert r.status_code == 409, \
        "a stale save returned %s — the other person's edit was overwritten" % r.status_code

    with app.app_context():
        conn = db.get_db()
        name = conn.execute("SELECT full_name FROM owners WHERE id=?",
                            (oid,)).fetchone()[0]
        conn.close()
    assert name == "قبل التعارض", "the stale save was written anyway"
