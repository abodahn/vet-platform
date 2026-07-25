"""
TOTP two-factor authentication.

Runs on the throwaway SQLite database from conftest with no PostgreSQL and no
network. Every test uses its own X-Forwarded-For address so the DB-backed rate
limiter cannot leak a lockout of 127.0.0.1 into another test module.
"""
import time

import pytest

pyotp = pytest.importorskip("pyotp", reason="pyotp is an optional dependency")

import models.database as db
import models.security as sec


TEST_USER = "twofa_tester"
TEST_PASS = "Str0ng!Passw0rd#2026"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def user_id(app):
    """A user dedicated to this module — never `admin`, which every other test
    module logs in as. Enabling 2FA on a shared account would break them."""
    with app.app_context():
        existing = db.get_user(TEST_USER)
        if existing:
            return existing["id"]
        return db.create_user({
            "username": TEST_USER, "password": TEST_PASS,
            "full_name": "Two Factor Tester", "role": "staff",
        })


@pytest.fixture(autouse=True)
def _clean_2fa(app, user_id, request):
    """Leave no 2FA state and no rate-limit rows behind."""
    yield
    with app.app_context():
        sec.disable_totp(user_id)
        sec.clear_rate_limit(_ip(request), TEST_USER)
        sec.clear_rate_limit(_ip(request), f"2fa:{TEST_USER}")


def _ip(request):
    """A per-test source address, so lockouts cannot cross test boundaries."""
    return "198.51.100." + str(abs(hash(request.node.name)) % 200 + 10)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _hdr(ip):
    return {"X-Forwarded-For": ip}


def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _enrol(app, user_id):
    """Enable 2FA the way the UI does, and return the base32 secret."""
    with app.app_context():
        secret = sec.start_totp_enrolment(user_id)
        assert sec.confirm_totp_enrolment(user_id, pyotp.TOTP(secret).now())
        assert sec.totp_required(user_id)
    return secret


def _code(secret, step_offset=1):
    """A code from a *future* time step by default.

    Confirming enrolment burns the current step (that is the replay defence
    working), so a test that logs in seconds later has to use the next one —
    exactly as a real user does when they log in some time after enrolling.
    """
    return pyotp.TOTP(secret).at(int(time.time()) + step_offset * 30)


def _password_login(client, ip):
    return client.post("/auth/login",
                       data={"username": TEST_USER, "password": TEST_PASS},
                       headers=_hdr(ip))


def _submit_code(client, code, ip):
    client.get("/auth/2fa", headers=_hdr(ip))          # seeds the CSRF token
    return client.post("/auth/2fa",
                       data={"code": code, "_csrf_token": _csrf(client)},
                       headers=_hdr(ip))


def _session_user(client):
    with client.session_transaction() as s:
        return s.get("user")


# ─── Enrolment ────────────────────────────────────────────────────────────────

def test_enrolment_requires_a_valid_code_before_enabling(app, client, user_id, request):
    ip = _ip(request)
    _password_login(client, ip)
    assert _session_user(client), "password-only login should work before enrolling"

    client.get("/auth/profile", headers=_hdr(ip))
    client.post("/auth/profile",
                data={"action": "2fa_start", "_csrf_token": _csrf(client)},
                headers=_hdr(ip))

    with app.app_context():
        status = sec.totp_status(user_id)
        assert status["pending"] and not status["enabled"], \
            "starting enrolment must not enable 2FA on its own"
        secret = sec.get_pending_secret(user_id)
        assert secret

    setup_page = client.get("/auth/profile?setup=1", headers=_hdr(ip))
    assert setup_page.status_code == 200
    assert secret.encode() in setup_page.data, "the key must be typeable by hand"

    # A wrong code must not flip the switch — otherwise a typo during setup
    # locks the user out at their next login.
    client.post("/auth/profile",
                data={"action": "2fa_confirm", "code": "000000",
                      "_csrf_token": _csrf(client)},
                headers=_hdr(ip))
    with app.app_context():
        assert not sec.totp_status(user_id)["enabled"]

    resp = client.post("/auth/profile",
                       data={"action": "2fa_confirm",
                             "code": pyotp.TOTP(secret).now(),
                             "_csrf_token": _csrf(client)},
                       headers=_hdr(ip))
    assert resp.status_code == 200
    with app.app_context():
        status = sec.totp_status(user_id)
        assert status["enabled"]
        assert status["backup_remaining"] == sec.BACKUP_CODE_COUNT, \
            "confirming enrolment must issue backup codes"


def test_user_can_turn_it_off_again_with_their_password(app, client, user_id, request):
    ip = _ip(request)
    secret = _enrol(app, user_id)
    _password_login(client, ip)
    _submit_code(client, _code(secret), ip)

    page = client.get("/auth/profile", headers=_hdr(ip))
    assert page.status_code == 200
    assert secret.encode() not in page.data, \
        "a confirmed secret must never be shown again"

    client.post("/auth/profile",
                data={"action": "2fa_disable", "password": "wrong",
                      "_csrf_token": _csrf(client)}, headers=_hdr(ip))
    with app.app_context():
        assert sec.totp_required(user_id), "a wrong password must not disable 2FA"

    client.post("/auth/profile",
                data={"action": "2fa_disable", "password": TEST_PASS,
                      "_csrf_token": _csrf(client)}, headers=_hdr(ip))
    with app.app_context():
        assert not sec.totp_required(user_id)
        assert sec.count_backup_codes(user_id) == 0, \
            "disabling must destroy the backup codes too"


def test_secret_is_encrypted_at_rest(app, user_id):
    secret = _enrol(app, user_id)
    with app.app_context():
        row = sec._user_totp_row(user_id)
        stored = row["totp_secret"]
        assert stored.startswith("enc1:"), "secret must not be stored in plaintext"
        assert secret not in stored
        assert sec._decrypt_secret(stored) == secret


# ─── Login gating ─────────────────────────────────────────────────────────────

def test_login_with_2fa_enabled_does_not_set_session_user(app, client, user_id, request):
    ip = _ip(request)
    _enrol(app, user_id)

    resp = _password_login(client, ip)
    assert resp.status_code == 302
    assert "/auth/2fa" in resp.headers["Location"]
    assert _session_user(client) is None, \
        "a correct password alone must never establish a session"
    with client.session_transaction() as s:
        assert s.get("_pending_2fa", {}).get("user_id") == user_id


def test_pending_session_expires(app, client, user_id, request):
    ip = _ip(request)
    _enrol(app, user_id)
    _password_login(client, ip)
    with client.session_transaction() as s:
        assert "_pending_2fa" in s

    with client.session_transaction() as s:
        s["_pending_2fa"] = dict(s["_pending_2fa"], expires_at=time.time() - 1)

    resp = client.get("/auth/2fa", headers=_hdr(ip))
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
    assert _session_user(client) is None
    with client.session_transaction() as s:
        assert "_pending_2fa" not in s, "an expired half-login must be discarded"


def test_valid_code_completes_login(app, client, user_id, request):
    ip = _ip(request)
    secret = _enrol(app, user_id)
    _password_login(client, ip)

    resp = _submit_code(client, _code(secret), ip)
    assert resp.status_code == 302
    user = _session_user(client)
    assert user and user["username"] == TEST_USER
    assert "totp_secret" not in user, "the secret must never reach the session cookie"


def test_replayed_code_is_rejected(app, client, user_id, request):
    ip = _ip(request)
    secret = _enrol(app, user_id)
    code = _code(secret)

    _password_login(client, ip)
    _submit_code(client, code, ip)
    assert _session_user(client), "first use of the code should succeed"
    client.get("/auth/logout", headers=_hdr(ip))

    _password_login(client, ip)
    resp = _submit_code(client, code, ip)
    assert resp.status_code == 200, "a replayed code must not complete login"
    assert _session_user(client) is None
    with app.app_context():
        assert not sec.verify_totp_code(user_id, code)


# ─── Backup codes ─────────────────────────────────────────────────────────────

def test_backup_code_works_exactly_once(app, client, user_id, request):
    ip = _ip(request)
    _enrol(app, user_id)
    with app.app_context():
        codes = sec.generate_backup_codes(user_id)

    _password_login(client, ip)
    resp = _submit_code(client, codes[0], ip)
    assert resp.status_code == 302
    assert _session_user(client)
    with app.app_context():
        assert sec.count_backup_codes(user_id) == sec.BACKUP_CODE_COUNT - 1

    client.get("/auth/logout", headers=_hdr(ip))
    _password_login(client, ip)
    resp = _submit_code(client, codes[0], ip)
    assert resp.status_code == 200, "a spent backup code must not work again"
    assert _session_user(client) is None

    # A different, unspent code still works.
    resp = _submit_code(client, codes[1], ip)
    assert resp.status_code == 302
    assert _session_user(client)


# ─── Rate limiting ────────────────────────────────────────────────────────────

def test_rate_limit_engages_on_repeated_bad_codes(app, client, user_id, request):
    ip = _ip(request)
    secret = _enrol(app, user_id)
    _password_login(client, ip)

    for _ in range(sec.RATE_LIMIT_MAX):
        _submit_code(client, "000000", ip)

    with app.app_context():
        locked, wait = sec.is_rate_limited(ip, f"2fa:{TEST_USER}")
        assert locked and wait > 0

    # Even the genuine current code is refused while locked out — a 6-digit
    # space is only 10^6, so the lockout is the whole defence here.
    resp = _submit_code(client, _code(secret), ip)
    assert resp.status_code == 200
    assert b"Too many incorrect codes" in resp.data
    assert _session_user(client) is None


# ─── Users who have not enrolled ──────────────────────────────────────────────

def test_user_without_2fa_is_unaffected(app, client, user_id, request):
    """The opt-in guarantee: nothing changes for anyone who has not enrolled."""
    ip = _ip(request)
    with app.app_context():
        assert not sec.totp_required(user_id)

    resp = _password_login(client, ip)
    assert resp.status_code == 302
    assert "/auth/2fa" not in resp.headers["Location"]
    user = _session_user(client)
    assert user and user["username"] == TEST_USER

    # /auth/2fa is not a way in for someone already (or not yet) logged in.
    assert client.get("/auth/2fa", headers=_hdr(ip)).status_code == 302


# ─── Admin reset (lost phone) ─────────────────────────────────────────────────

def test_admin_can_reset_a_user_who_lost_their_phone(app, client, user_id, request):
    ip = _ip(request)
    _enrol(app, user_id)

    admin = app.test_client()
    admin.post("/auth/login", data={"username": "admin", "password": "1234"},
               headers=_hdr(ip))
    page = admin.get("/auth/2fa/admin", headers=_hdr(ip))
    assert page.status_code == 200
    assert TEST_USER.encode() in page.data

    resp = admin.post(f"/auth/2fa/admin/reset/{user_id}",
                      data={"_csrf_token": _csrf(admin)}, headers=_hdr(ip))
    assert resp.status_code == 302
    with app.app_context():
        assert not sec.totp_required(user_id)
        assert "2fa_admin_reset" in [r["action"] for r in db.get_audit_log(50)], \
            "every admin reset must be audit-logged"

    # The point of the reset: they can get back into patient records today.
    resp = _password_login(client, ip)
    assert "/auth/2fa" not in resp.headers["Location"]
    assert _session_user(client)


def test_admin_reset_is_closed_to_ordinary_staff(app, client, user_id, request):
    ip = _ip(request)
    _password_login(client, ip)          # TEST_USER is role "staff"
    client.get("/auth/profile", headers=_hdr(ip))     # seeds the CSRF token
    resp = client.post(f"/auth/2fa/admin/reset/{user_id}",
                       data={"_csrf_token": _csrf(client)}, headers=_hdr(ip))
    assert resp.status_code == 302
    assert "/auth/2fa/admin" not in resp.headers["Location"]
    assert client.get("/auth/2fa/admin", headers=_hdr(ip)).status_code == 302


def test_seeded_admin_still_logs_in_with_password_only(client):
    """The shared seed account must never be dragged into 2FA by this module."""
    resp = client.post("/auth/login", data={"username": "admin", "password": "1234"})
    assert resp.status_code == 302
    with client.session_transaction() as s:
        assert s.get("user", {}).get("username") == "admin"


# ─── Missing-library behaviour ────────────────────────────────────────────────

def test_missing_pyotp_fails_closed(app, user_id, monkeypatch):
    """A missing library must not silently remove a security control.

    If pyotp disappears from a deploy, an account with 2FA enrolled must be
    refused, not quietly downgraded to password-only.
    """
    _enrol(app, user_id)
    with app.app_context():
        monkeypatch.setattr(sec, "pyotp", None)
        monkeypatch.delenv("TOTP_FAIL_OPEN", raising=False)
        with pytest.raises(sec.TOTPUnavailable):
            sec.totp_required(user_id)


def test_missing_pyotp_escape_hatch(app, user_id, monkeypatch):
    """TOTP_FAIL_OPEN=1 restores password-only login for a locked-out clinic.

    Mirrors CORS_ALLOW_WILDCARD: secure by default, recoverable in one
    deliberate step, never inherited by accident.
    """
    _enrol(app, user_id)
    with app.app_context():
        monkeypatch.setattr(sec, "pyotp", None)
        monkeypatch.setenv("TOTP_FAIL_OPEN", "1")
        assert sec.totp_required(user_id) is False
