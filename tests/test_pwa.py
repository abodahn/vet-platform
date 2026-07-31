# -*- coding: utf-8 -*-
"""PWA install chain.

"Installable" is not one feature, it is four things that must all be true at
once, and a browser that fails any of them silently declines to offer Install
with no error anywhere. That silence is why this file exists.
"""
import json

import pytest


def test_manifest_is_served_and_valid(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/manifest+json")

    m = json.loads(r.get_data(as_text=True))
    # Chrome refuses to offer installation unless all of these are present.
    for key in ("name", "short_name", "start_url", "display", "icons"):
        assert m.get(key), f"manifest is missing {key}; install prompt will not appear"
    assert m["display"] == "standalone"
    # short_name renders under the home-screen icon and is truncated by the OS
    # somewhere around 12 characters.
    assert len(m["short_name"]) <= 12


def test_manifest_carries_the_clinic_name_not_the_vendor(app, client):
    """A clinic's staff should not find the vendor's name on their phones."""
    import models.database as db

    with app.app_context():
        # Read it through get_clinic() FIRST so the 5-minute cache is populated.
        # Without this the test passes on an empty cache and proves nothing
        # about invalidation.
        db.get_clinic()
        conn = db.get_db()
        conn.execute("UPDATE clinic SET name=?", ("Nile Vet Hospital",))
        conn.commit()
        conn.close()
        db.cache_invalidate("clinic_row")

    m = json.loads(client.get("/manifest.webmanifest").get_data(as_text=True))
    assert m["name"] == "Nile Vet Hospital"


@pytest.mark.parametrize("icon", [
    "/static/images/icon-192.png",
    "/static/images/icon-512.png",
    "/static/images/icon-maskable-512.png",
    "/static/images/apple-touch-icon.png",
])
def test_icons_exist(client, icon):
    """A manifest naming an icon that 404s disables the install prompt."""
    r = client.get(icon)
    assert r.status_code == 200
    assert r.headers["Content-Type"] == "image/png"


def test_service_worker_is_served_from_the_root(client):
    """Scope is the directory the script is served from. At /static/sw.js the
    worker could only ever control /static/* and would never see a navigation,
    so the app would not be installable."""
    r = client.get("/sw.js")
    assert r.status_code == 200
    assert "javascript" in r.headers["Content-Type"]
    assert "no-cache" in r.headers.get("Cache-Control", "")


def test_service_worker_never_caches_pages_or_data(client):
    """The one rule that matters clinically.

    A cached page is a stale medical record, and the cache is shared by every
    account on the device — so caching an authenticated response would also
    show one user's patients to the next person at the reception desktop.
    """
    js = client.get("/sw.js").get_data(as_text=True)
    assert 'startsWith("/static/")' in js, \
        "the worker must restrict caching to static assets"
    # cache.put must be reached only inside the /static/ branch.
    before_guard, _, after_guard = js.partition('startsWith("/static/")')
    assert "cache.put" not in before_guard, \
        "a cache.put ahead of the /static/ guard would store pages and API data"


def _assert_installable(html, where):
    """Each of these is individually sufficient to break installation."""
    assert '<link rel="manifest"' in html, f"{where}: no manifest link, nothing to install"
    assert 'name="theme-color"' in html, f"{where}: no theme colour"
    assert 'rel="apple-touch-icon"' in html, f"{where}: iOS falls back to a screenshot"
    assert "serviceWorker" in html and '"/sw.js"' in html, \
        f"{where}: worker never registered, Chrome will not offer Install"


def test_logged_in_pages_are_installable(auth_client):
    _assert_installable(
        auth_client.get("/", follow_redirects=True).get_data(as_text=True),
        "dashboard")


def test_the_LOGIN_page_is_installable(client):
    """The page that matters most, and the one this originally missed.

    login.html does not extend base.html, so putting the tags only in the base
    left the first page anyone sees — and the page they would actually install
    from — without a manifest. The app was installable in theory and never in
    practice. Checked with an anonymous client on purpose; a logged-in one
    cannot see this page at all, which is exactly how the gap survived.
    """
    _assert_installable(
        client.get("/login", follow_redirects=True).get_data(as_text=True),
        "login")


@pytest.mark.parametrize("template", [
    "templates/login.html",
    "templates/auth/two_factor.html",
    "templates/appointments/waiting_room.html",
    "templates/error.html",
])
def test_every_standalone_page_includes_the_partial(template):
    """Guards the whole class of bug rather than the one instance of it: any
    page not extending base.html must pull the partial in itself."""
    import pathlib
    src = pathlib.Path(template).read_text(encoding="utf-8")
    assert "_pwa_head.html" in src, f"{template} would drop out of the PWA"


def test_manifest_and_worker_are_reachable_without_logging_in(client):
    """Both are fetched by the browser before any session exists. Behind
    @login_required they would 302 to the login page and installation would
    fail with no visible error."""
    for url in ("/manifest.webmanifest", "/sw.js"):
        assert client.get(url).status_code == 200, f"{url} is not public"
