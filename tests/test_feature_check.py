# -*- coding: utf-8 -*-
"""The report that answers "can THIS box do what the screen claims?"

Every bug found on the first day the demo server was live was one bug, ten
times: the UI advertised something the deployment could not deliver. Legacy
buttons on a Linux server. An AI chat button with no provider. A language
toggle posting nowhere. A go-live gate blind to its own backups. Printed demo
credentials that did not sign in.

1,738 tests missed all of it, because every one asked "does this feature work?"
and none asked "can this machine run it?".

scripts/feature_check.py asks the second question. These tests keep it honest:
a readiness report that says READY when a thing is off is worse than no report,
because it is the same lie one level up.
"""
import importlib.util
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPT = os.path.join(os.path.dirname(_HERE), "scripts", "feature_check.py")


def _load():
    spec = importlib.util.spec_from_file_location("feature_check", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["feature_check"] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fc(monkeypatch, tmp_path):
    from config import Config
    monkeypatch.setattr(Config, "DATABASE_PATH", str(tmp_path / "platform.db"))
    return _load()


def _status(mod, name_starts):
    for status, feature, _detail, _crit in mod._results:
        if feature.startswith(name_starts):
            return status
    return None


# ── it must not call an unconfigured feature ready ────────────────────────────

def test_ai_with_no_provider_is_not_ready(fc, monkeypatch):
    import blueprints.ai_assistant.routes as ai
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "")
    monkeypatch.setattr(ai, "FREELLM_BASE_URL", "http://localhost:3001/v1")
    monkeypatch.setattr(ai, "_local_proxy_reachable", lambda url: False)
    fc._results.clear()
    fc.check_ai()
    assert _status(fc, "AI") == fc.OFF


def test_ai_with_a_key_is_ready(fc, monkeypatch):
    import blueprints.ai_assistant.routes as ai
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-test")
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    fc._results.clear()
    fc.check_ai()
    assert _status(fc, "AI") == fc.READY


def test_whatsapp_without_a_provider_is_not_ready(fc, monkeypatch):
    """The claim "the system messages the owner automatically" was in the sales
    playbook while nothing was configured to send."""
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    monkeypatch.delenv("WAPILOT_INSTANCE", raising=False)
    fc._results.clear()
    fc.check_whatsapp()
    assert _status(fc, "WhatsApp") == fc.OFF


def test_whatsapp_with_a_provider_is_ready(fc, monkeypatch):
    monkeypatch.setenv("WAPILOT_TOKEN", "t0ken")
    monkeypatch.setenv("WAPILOT_INSTANCE", "inst-1")
    fc._results.clear()
    fc.check_whatsapp()
    assert _status(fc, "WhatsApp") == fc.READY


def test_the_legacy_app_enabled_on_linux_is_broken_not_ready(fc, monkeypatch):
    """It is a Windows desktop program. Enabled on a hosted server it is the
    500 that started all of this."""
    monkeypatch.setenv("LEGACY_APP_ENABLED", "1")
    monkeypatch.setattr(fc.sys, "platform", "linux")
    fc._results.clear()
    fc.check_legacy()
    assert _status(fc, "Legacy") == fc.BROKEN


def test_production_without_secure_cookies_is_broken(fc, monkeypatch):
    """Sign-in fails silently over plain HTTP — nothing on screen says why."""
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")
    fc._results.clear()
    fc.check_tls_and_cookies()
    assert _status(fc, "Secure session") == fc.BROKEN


# ── a failed read is not an empty screen ──────────────────────────────────────

def test_a_clinic_it_cannot_read_is_broken_not_ready(fc, monkeypatch):
    """The first version of this script reported "-1 vaccinations due" as fine,
    because it never configured tenancy and was reading the wrong database.
    Third time that mistake was made in one day."""
    from models import tenancy
    monkeypatch.setattr(tenancy, "all_tenants",
                        lambda active_only=True: [{"slug": "ghost"}])
    fc._results.clear()
    fc.check_demo_data()
    assert _status(fc, "Demo data") == fc.BROKEN


def test_it_configures_tenancy_the_way_create_app_does(fc, tmp_path, monkeypatch):
    from models import tenancy
    monkeypatch.setattr(tenancy, "_registry_path", "")
    monkeypatch.delenv("TENANT_REGISTRY", raising=False)
    fc._configure_like_the_app()
    assert tenancy._registry_path == os.path.join(str(tmp_path), "tenants.db")


# ── the report itself ─────────────────────────────────────────────────────────

def test_a_broken_feature_makes_it_exit_non_zero(fc, monkeypatch):
    monkeypatch.setattr(fc, "CHECKS",
                        [lambda: fc.report("Thing", fc.BROKEN, "gone", True)])
    assert fc.run([]) == 1


def test_switched_off_is_not_a_failure(fc, monkeypatch):
    """Turning a feature off is a legitimate deployment choice. Only claiming
    it while it is off is the problem."""
    monkeypatch.setattr(fc, "CHECKS",
                        [lambda: fc.report("Thing", fc.OFF, "not configured")])
    assert fc.run([]) == 0


def test_a_check_that_errors_is_reported_not_swallowed(fc, monkeypatch):
    def explode():
        raise RuntimeError("boom")
    monkeypatch.setattr(fc, "CHECKS", [explode])
    assert fc.run([]) == 1


def test_demo_mode_shows_only_what_a_vet_would_see(fc, monkeypatch, capsys):
    monkeypatch.setattr(fc, "CHECKS", [
        lambda: fc.report("On the screen", fc.OFF, "", True),
        lambda: fc.report("Backend only", fc.OFF, "", False),
    ])
    fc.run(["--demo"])
    out = capsys.readouterr().out
    assert "On the screen" in out
    assert "Backend only" not in out
