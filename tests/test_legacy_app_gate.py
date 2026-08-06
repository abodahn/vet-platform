# -*- coding: utf-8 -*-
"""The legacy Windows app must not exist on a hosted deployment.

Found by a vet clicking "وحدة الفحص" on the live demo and getting a 500 page.

The legacy examination app is a Windows program that ran on the SAME machine
as the platform, back when the platform was installed on a clinic's own PC.
On a hosted server every assumption behind it is false:

  * subprocess.CREATE_NEW_CONSOLE does not exist off Windows, so the route was
    an AttributeError -> 500.
  * It spawned a process ON THE SERVER on behalf of any logged-in user of any
    clinic.
  * LEGACY_APP_URL is http://localhost:5000, which from a visitor's browser is
    THEIR machine — a connection error on a laptop, a mystery on a phone.

LEGACY_APP_ENABLED already existed as the switch. Only the system monitor page
read it. The launcher, where a user actually clicks, ignored it — so both
legacy buttons sat at the top of the dashboard, which is the first screen
anyone is ever shown.
"""
import pytest


@pytest.fixture
def hosted(app):
    """A hosted deployment: no legacy app, like every real server."""
    prev = app.config.get("LEGACY_APP_ENABLED")
    app.config["LEGACY_APP_ENABLED"] = False
    yield app
    app.config["LEGACY_APP_ENABLED"] = prev


@pytest.fixture
def on_premise(app):
    """The old model: platform and legacy app on one Windows PC."""
    prev = app.config.get("LEGACY_APP_ENABLED")
    app.config["LEGACY_APP_ENABLED"] = True
    yield app
    app.config["LEGACY_APP_ENABLED"] = prev


# ── the 500 ───────────────────────────────────────────────────────────────────

def test_starting_the_legacy_app_is_404_not_500(hosted, auth_client):
    r = auth_client.get("/launcher/legacy/start")
    assert r.status_code == 404, (
        f"got {r.status_code}. 500 means it still tries to spawn a Windows "
        "process on a Linux server.")


def test_it_never_spawns_a_process_on_a_hosted_server(hosted, auth_client, monkeypatch):
    """The part that matters more than the error code."""
    import subprocess
    calls = []
    monkeypatch.setattr(subprocess, "Popen",
                        lambda *a, **k: calls.append(a) or pytest.fail(
                            "spawned a process on the server"))
    auth_client.get("/launcher/legacy/start")
    assert not calls


def test_the_windows_only_flag_is_never_referenced_unguarded():
    """CREATE_NEW_CONSOLE exists only on Windows. Reading it directly is what
    turned this route into a 500 on every Linux deployment."""
    import os
    import re
    here = os.path.dirname(os.path.abspath(__file__))
    src = open(os.path.join(os.path.dirname(here), "blueprints", "launcher",
                            "routes.py"), encoding="utf-8").read()
    # The attribute access in the CALL, not the two mentions of it in prose.
    assert not re.search(r"creationflags\s*=\s*subprocess\.", src), \
        "pass it as getattr(subprocess, 'CREATE_NEW_CONSOLE', 0)"
    assert "getattr(subprocess, \"CREATE_NEW_CONSOLE\", 0)" in src


# ── the buttons ───────────────────────────────────────────────────────────────

def test_the_dashboard_shows_no_legacy_buttons(hosted, auth_client):
    """Both sat in the toolbar of the first screen anyone is shown."""
    body = auth_client.get("/").get_data(as_text=True)
    assert "/launcher/legacy/start" not in body
    assert "/easy/landing" not in body


def test_localhost_5000_is_not_linked_anywhere_on_the_dashboard(hosted, auth_client):
    """From a visitor's browser localhost is THEIR machine, so any such link is
    a connection error they will read as 'the software is broken'."""
    body = auth_client.get("/").get_data(as_text=True)
    assert "localhost:5000" not in body


def test_ping_reports_absent_rather_than_down(hosted, auth_client):
    """'Down' invites someone to go looking for it. There is nothing to find."""
    data = auth_client.get("/launcher/legacy/ping").get_json()
    assert data["enabled"] is False
    assert data["up"] is False


# ── the on-premise model still works ──────────────────────────────────────────

def test_on_premise_still_offers_the_legacy_buttons(on_premise, auth_client):
    """A clinic running this on its own Windows PC alongside the old app is a
    legitimate deployment, and this must not have taken it away."""
    body = auth_client.get("/").get_data(as_text=True)
    assert "/launcher/legacy/start" in body


def test_on_premise_ping_actually_probes(on_premise, auth_client):
    data = auth_client.get("/launcher/legacy/ping").get_json()
    assert data["enabled"] is True
    assert "up" in data


# ── the card that caused it ───────────────────────────────────────────────────

def test_no_module_card_points_at_the_legacy_app(hosted, auth_client):
    """The "examination" card was the FIRST card on the dashboard and its Open
    button went to /launcher/legacy/start. Deleted: the "visits" card already
    does the same workflow, inside the platform, and it works."""
    body = auth_client.get("/").get_data(as_text=True)
    assert "/launcher/legacy/start" not in body
    assert "الفحص والسجلات الطبية" not in body


def test_the_visits_module_is_still_there_to_replace_it(hosted, auth_client):
    """Deleting the broken card must not remove the workflow from the launcher."""
    body = auth_client.get("/").get_data(as_text=True)
    assert "/visits/" in body


def test_no_module_points_off_this_server(app):
    """The settings card carried legacy_path "/config", which the template
    rendered as http://localhost:5000/config — the VISITOR'S machine. Two of
    the dashboard's cards pointed at software that is not there."""
    from blueprints.launcher.routes import MODULES
    offsite = [f"{m['id']} -> {m.get('url') or m.get('legacy_path')}"
               for m in MODULES
               if m.get("legacy") or "localhost" in (m.get("url") or "")]
    assert not offsite, "cards pointing off this server: " + ", ".join(offsite)


def test_every_module_url_is_a_route_this_app_serves(app):
    """The examination card pointed at a route that 500'd, and nothing noticed
    because no test ever asked whether the launcher's own links resolve."""
    from blueprints.launcher.routes import MODULES
    adapter = app.url_map.bind("demo.aleefy.online")
    broken = []
    for mod in MODULES:
        # "planned" / "coming_soon" cards deliberately carry no url — the
        # template sends them to the stub page instead of linking out.
        if mod.get("status") not in ("active", "beta"):
            continue
        url = (mod.get("url") or "").split("?")[0]
        if not url.startswith("/"):
            broken.append(f"{mod['id']} -> {url or '(none)'} (not a local path)")
            continue
        try:
            adapter.match(url, method="GET")
        except Exception:
            broken.append(f"{mod['id']} -> {url}")
    assert not broken, "live launcher cards linking nowhere: " + ", ".join(broken)
