# -*- coding: utf-8 -*-
"""Licence activation, and the promises made to the clinic about it.

Half of these tests are about cryptography. The other half exist because the
licence design makes three promises to a paying clinic, and a promise nothing
tests is a promise that quietly stops being true:

  - it never blocks access to patient records
  - a replaced computer is noticed, not punished
  - if the supplier goes silent for 90 days, the clinic is not stranded
"""
from datetime import date, timedelta

import pytest

from models import licensing as lic

SECRET = b"secret-for-tests-only"
MACHINE = "77064095"


def _code(expiry, machine=MACHINE, secret=SECRET):
    return lic.make_code(secret, machine, expiry)


# ── the code itself ──────────────────────────────────────────────────────────

def test_a_valid_code_verifies():
    c = _code(date(2027, 8, 31))
    ok, expiry, reason = lic.check_code(c, machine=MACHINE, secret=SECRET)
    assert ok and reason == "ok"
    assert expiry == date(2027, 8, 31)


def test_the_code_is_bound_to_one_machine():
    """The whole point: a clinic cannot pass a working copy to a friend."""
    c = _code(date(2027, 8, 31))
    ok, _, reason = lic.check_code(c, machine="11112222", secret=SECRET)
    assert not ok and reason == "wrong_code"


def test_the_expiry_cannot_be_edited():
    """The date is readable in the code, so it must also be inside the HMAC."""
    c = _code(date(2027, 8, 31))          # 2708-xxxx-xxxx
    tampered = "2812-" + c.split("-", 1)[1]
    ok, _, reason = lic.check_code(tampered, machine=MACHINE, secret=SECRET)
    assert not ok and reason == "wrong_code"


def test_another_clinics_secret_does_not_work():
    a = lic.derive_clinic_secret("master", "clinic-a").encode()
    b = lic.derive_clinic_secret("master", "clinic-b").encode()
    assert a != b
    c = lic.make_code(a, MACHINE, date(2027, 8, 31))
    assert not lic.check_code(c, machine=MACHINE, secret=b)[0]


def test_derivation_is_stable():
    """Same clinic id must always give the same secret, or every existing
    customer's code stops working the next time a code is issued."""
    assert (lic.derive_clinic_secret("master", "hatem-vet")
            == lic.derive_clinic_secret("master", "hatem-vet"))


@pytest.mark.parametrize("bad", [
    "", "hello", "2708-4471", "2708-4471-882", "27134471-8823", "----",
    "2700-1111-2222",          # month 00
])
def test_malformed_codes_are_refused_not_crashed(bad):
    ok, _, reason = lic.check_code(bad, machine=MACHINE, secret=SECRET)
    assert not ok
    assert reason in ("malformed", "wrong_code")


def test_code_is_digits_only():
    """It gets read down a phone line where B and D sound identical."""
    c = _code(date(2027, 8, 31))
    assert c.replace("-", "").isdigit()
    assert lic.machine_id().isdigit()


def test_no_secret_configured_is_reported_not_accepted():
    ok, _, reason = lic.check_code(_code(date(2027, 8, 31)),
                                   machine=MACHINE, secret=b"")
    assert not ok and reason == "no_secret"


# ── the promises ─────────────────────────────────────────────────────────────

def _status_with(app, until):
    with app.app_context():
        import models.database as db
        db.set_setting("license_valid_until", until.isoformat(), "license")
        db.set_setting("license_machine", lic.machine_id(), "license")
        return lic.status()


def test_an_expired_licence_never_blocks_anything(app):
    """The core promise. If this test ever fails, a clinic has been locked out
    of its own patient records, which the offer document says cannot happen."""
    st = _status_with(app, date.today() - timedelta(days=400))
    assert st["blocks_anything"] is False


@pytest.mark.parametrize("days_past", [0, 1, 45, 89, 200, 5000])
def test_no_state_ever_blocks(app, days_past):
    st = _status_with(app, date.today() - timedelta(days=days_past))
    assert st["blocks_anything"] is False


def test_recently_expired_is_quiet(app):
    """60 days of silence, so a clinic renewing late is not alarmed."""
    st = _status_with(app, date.today() - timedelta(days=10))
    assert st["state"] == "lapsed"
    assert st["banner"] == ""


def test_after_the_quiet_period_it_asks(app):
    st = _status_with(app, date.today() - timedelta(days=70))
    assert st["state"] == "lapsed"
    assert st["banner"]


def test_after_90_days_it_stops_asking_forever(app):
    """Auto-grace: if the supplier is unreachable, the clinic is not stranded
    and no vet is left explaining a licence screen to a waiting room."""
    st = _status_with(app, date.today() - timedelta(days=120))
    assert st["state"] == "grace"
    assert st["banner"] == ""


def test_a_licence_in_date_says_nothing(app):
    st = _status_with(app, date.today() + timedelta(days=200))
    assert st["state"] == "active"
    assert st["banner"] == ""


def test_a_replaced_computer_is_noted_not_punished(app):
    with app.app_context():
        import models.database as db
        db.set_setting("license_valid_until",
                       (date.today() + timedelta(days=100)).isoformat(), "license")
        db.set_setting("license_machine", "00000000", "license")   # a different PC
        st = lic.status()
    assert st["machine_changed"] is True
    assert st["blocks_anything"] is False
    assert st["state"] == "active"


def test_status_survives_a_broken_database(app, monkeypatch):
    """This feeds a context processor on every page render. If it can raise,
    one bad setting takes down every screen in the product."""
    import models.database as db
    monkeypatch.setattr(db, "get_setting",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with app.app_context():
        st = lic.status()
        assert st["blocks_anything"] is False
        assert lic.banner() == ""


# ── the screen ───────────────────────────────────────────────────────────────

def test_licence_page_loads_and_shows_the_machine_number(auth_client):
    r = auth_client.get("/system/license")
    assert r.status_code in (200, 403)          # 403 if the test user is not an owner
    if r.status_code == 200:
        assert lic.challenge() in r.get_data(as_text=True)


def test_every_page_still_renders_with_the_banner_wired_in(auth_client):
    """The banner sits in base.html, so a mistake here breaks the whole app."""
    for url in ("/", "/crm/owners", "/finance/invoices"):
        assert auth_client.get(url).status_code in (200, 302, 403, 404)


# ── the phone tool must not drift from the Python ────────────────────────────

def test_phone_tool_issues_the_same_codes_as_python():
    """static/tools/codes/index.html reimplements this algorithm in JavaScript.

    If the two ever disagree the failure is silent and expensive: a code is
    read to a clinic over the phone, the app refuses it, and neither side can
    tell which one is wrong. The clinic concludes the product is broken.

    Skipped rather than failed where node is absent, because a missing
    developer tool is not a defect in the product.
    """
    import json
    import os
    import shutil
    import subprocess

    if not shutil.which("node"):
        pytest.skip("node not installed - cannot check the phone tool")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    gen = os.path.join(root, "scripts", "verify_phone_tool.py")
    check = os.path.join(root, "scripts", "verify_phone_tool.js")
    if not (os.path.exists(gen) and os.path.exists(check)):
        pytest.skip("phone tool verification scripts are not present")

    import sys
    subprocess.run([sys.executable, gen], cwd=root, capture_output=True,
                   text=True, timeout=120, check=True)
    r = subprocess.run(["node", check], cwd=root, capture_output=True,
                       text=True, timeout=120)
    assert r.returncode == 0, (
        "The phone tool and models/licensing.py disagree:\n"
        + (r.stdout or "") + (r.stderr or ""))


def test_phone_tool_contains_no_secret():
    """The file is committed and may be published. It must be a calculator with
    no key in it - the master is pasted on the device and encrypted there."""
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    body = open(os.path.join(root, "static", "tools", "codes", "index.html"),
                encoding="utf-8").read()
    # A stored master would have to appear as a literal long token.
    import re
    for m in re.finditer(r"""(?i)(master|secret)\s*[:=]\s*["'][A-Za-z0-9_\-+/]{16,}["']""", body):
        pytest.fail("the phone tool appears to embed a secret: %s" % m.group(0)[:60])
    assert "localStorage" in body and "PBKDF2" in body, (
        "the phone tool should store the master encrypted, not in the file")


# ── block mode ───────────────────────────────────────────────────────────────
#
# This is the dangerous half of the feature. Every test here exists because the
# failure it guards against means a clinic cannot open its own patient records.

def _mode(monkeypatch, mode):
    monkeypatch.setenv("ALEEFY_LICENSE_MODE", mode)
    # Block mode deliberately refuses to block without a secret - see
    # test_block_mode_without_a_secret_refuses_to_block - so these tests must
    # supply one or they would be asserting the safety valve, not the feature.
    monkeypatch.setenv("ALEEFY_LICENSE_SECRET", "secret-for-block-tests")


def _set_state(app, until):
    with app.app_context():
        import models.database as db
        if until is None:
            db.set_setting("license_valid_until", "", "license")
        else:
            db.set_setting("license_valid_until", until.isoformat(), "license")


def test_default_mode_blocks_nothing(app, monkeypatch):
    """The default must stay banner. A deploy that silently starts blocking
    because someone changed a default would be catastrophic."""
    monkeypatch.delenv("ALEEFY_LICENSE_MODE", raising=False)
    assert lic.enforcement_mode() == "banner"
    _set_state(app, None)
    with app.app_context():
        assert lic.is_blocked() is False


def test_an_unknown_mode_falls_back_to_banner(app, monkeypatch):
    """A typo in the env var must not lock a clinic out."""
    _mode(monkeypatch, "blcok")
    assert lic.enforcement_mode() == "banner"
    _set_state(app, None)
    with app.app_context():
        assert lic.is_blocked() is False


def test_block_mode_blocks_a_never_activated_copy(app, monkeypatch):
    _mode(monkeypatch, "block")
    _set_state(app, None)
    with app.app_context():
        assert lic.is_blocked() is True


def test_block_mode_allows_an_active_licence(app, monkeypatch):
    _mode(monkeypatch, "block")
    _set_state(app, date.today() + timedelta(days=100))
    with app.app_context():
        assert lic.is_blocked() is False


def test_a_late_payer_is_not_locked_out_mid_week(app, monkeypatch):
    """QUIET_DAYS of slack after expiry. A renewal that slips by a fortnight
    must never interrupt a consultation."""
    _mode(monkeypatch, "block")
    _set_state(app, date.today() - timedelta(days=14))
    with app.app_context():
        assert lic.is_blocked() is False


def test_a_long_lapsed_licence_does_block(app, monkeypatch):
    _mode(monkeypatch, "block")
        # 75 days: past QUIET_DAYS, still inside AUTO_GRACE_DAYS
    _set_state(app, date.today() - timedelta(days=75))
    with app.app_context():
        assert lic.is_blocked() is True


def test_auto_grace_is_never_blocked(app, monkeypatch):
    """The safety valve. If the vendor is ill, unreachable, has lost the master
    secret or has sold the business, no clinic may be bricked by it."""
    _mode(monkeypatch, "block")
    for days in (95, 200, 3000):
        _set_state(app, date.today() - timedelta(days=days))
        with app.app_context():
            assert lic.is_blocked() is False, "%d days past expiry was blocked" % days


def test_a_broken_licence_module_fails_open(app, monkeypatch):
    """If reading the licence raises, the answer must be ALLOW. A bug in this
    file must never be the reason a clinic cannot open its records."""
    _mode(monkeypatch, "block")
    monkeypatch.setattr(lic, "status",
                        lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    with app.app_context():
        assert lic.is_blocked() is False


def test_the_licence_page_is_always_reachable(app):
    """Without this a clinic holding a valid code could never type it in."""
    assert "system.license_page" in lic.ALWAYS_ALLOWED
    assert "auth.login" in lic.ALWAYS_ALLOWED
    assert "auth.logout" in lic.ALWAYS_ALLOWED
    assert "static" in lic.ALWAYS_ALLOWED


def test_the_blocked_page_says_the_records_are_safe():
    """Somebody seeing this screen for the first time assumes their data is
    gone. Both languages must say plainly that it is not."""
    body = open("templates/system/blocked.html", encoding="utf-8").read()
    assert "Nothing has been deleted" in body
    assert "لم يُحذف أي شيء" in body
    assert "url_for('system.license_page')" in body   # can actually activate
    assert "url_for('auth.logout')" in body           # and can get out


def test_block_reason_never_sounds_like_a_crash(app):
    with app.app_context():
        _set_state(app, None)
        r = lic.block_reason()
        assert "records are safe" in r
        for scary in ("error", "failed", "exception", "denied", "corrupt"):
            assert scary not in r.lower()


def test_block_mode_without_a_secret_refuses_to_block(app, monkeypatch):
    """Blocking with no secret configured would be a permanent lockout: every
    page held, and every activation code refused with 'no_secret'. There would
    be no way back in through the front door. It must fail open and log."""
    monkeypatch.setenv("ALEEFY_LICENSE_MODE", "block")
    monkeypatch.delenv("ALEEFY_LICENSE_SECRET", raising=False)
    _set_state(app, None)
    with app.app_context():
        assert lic.clinic_secret() == b""
        assert lic.is_blocked() is False, (
            "blocked with no secret - nothing could ever unblock this install")


def test_block_mode_with_a_secret_does_block(app, monkeypatch):
    """The other half: once a secret exists, blocking is recoverable and on."""
    monkeypatch.setenv("ALEEFY_LICENSE_MODE", "block")
    monkeypatch.setenv("ALEEFY_LICENSE_SECRET", "a-real-secret")
    _set_state(app, None)
    with app.app_context():
        assert lic.is_blocked() is True
