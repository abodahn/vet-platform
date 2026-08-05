# -*- coding: utf-8 -*-
"""The EN / عربي toggle in the toolbar.

It posted to /settings/lang/<lang>, and the route is /settings/lang reading
request.form["lang"]. Every click 404'd -- and because fetch() resolves on a
404 rather than rejecting, the handler reloaded the page anyway, so the button
looked like it had worked and quietly did nothing.

On a product whose whole differentiator is being Arabic-first, the language
switch being dead in the toolbar is not a small bug. The only working control
was buried on the profile page.
"""
import re
import os

_TEMPLATES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")


def _base_html():
    with open(os.path.join(_TEMPLATES, "base.html"), encoding="utf-8") as fh:
        return fh.read()


def _page_direction(html):
    """The <html> element's dir, not "does rtl appear anywhere".

    The launcher renders every module as an English name with its Arabic name
    underneath, and each of those sits in its own dir="rtl" div -- correctly.
    A substring search on the whole body therefore reports "rtl" on a page that
    is entirely left-to-right.
    """
    m = re.search(r"<html[^>]*\bdir=\"(rtl|ltr)\"", html)
    assert m, "the <html> element has no dir attribute at all"
    return m.group(1)


# ── the route the button has to hit ───────────────────────────────────────────

def test_the_toolbar_posts_to_a_url_that_exists(app):
    """The regression itself: assert the URL in the template is a real rule."""
    html = _base_html()
    m = re.search(r"fetch\('(/settings/lang[^']*)'", html)
    assert m, "language toggle no longer posts anywhere"
    url = m.group(1)
    assert "<" not in url and not url.rstrip("/").endswith(("/en", "/ar")), (
        f"{url} embeds the language in the path; the route takes a form field")

    adapter = app.url_map.bind("demo.aleefy.online")
    adapter.match(url, method="POST")   # raises NotFound if the rule is gone


def test_it_sends_the_language_as_a_form_field(app):
    html = _base_html()
    assert "body:'lang='+encodeURIComponent(lang)" in html.replace(" ", ""), (
        "set_lang() reads request.form['lang'] -- an empty body switches nothing")


def test_it_does_not_reload_when_the_request_failed(app):
    """Reloading on any response is what made a 404 look like success."""
    html = _base_html()
    block = html[html.index("data-lang-btn]"):]
    block = block[:block.index("/* ── User dropdown")] if "User dropdown" in block else block
    assert "resp.ok" in block, "still reloads regardless of the response status"


# ── and it has to actually switch ─────────────────────────────────────────────

def _switch(auth_client, lang):
    from models.security import _CSRF_SESSION_KEY
    with auth_client.session_transaction() as s:
        token = s.get(_CSRF_SESSION_KEY, "")
    r = auth_client.post("/settings/lang", data={"lang": lang, "_csrf_token": token})
    assert r.status_code in (200, 302), f"switch to {lang} returned {r.status_code}"
    return _page_direction(auth_client.get("/").get_data(as_text=True))


def test_switching_to_arabic_flips_the_page_direction(auth_client):
    assert _switch(auth_client, "ar") == "rtl"


def test_switching_back_to_english_flips_it_returns(auth_client):
    _switch(auth_client, "ar")
    assert _switch(auth_client, "en") == "ltr"


def test_an_unknown_language_falls_back_rather_than_breaking(auth_client):
    assert _switch(auth_client, "fr") == "ltr"


# ── the sign-in page needs its own switch ────────────────────────────────────
#
# The toolbar buttons live in the sidebar, and login.html has no sidebar. So the
# first screen anyone sees -- including a vet being shown the demo -- was locked
# to whatever PLATFORM_DEFAULT_LANG the deployment set, with no way out until
# after they had signed in. On an Arabic-first product sold to some clinics that
# work in English, that is the wrong first impression and no way to fix it.

def test_the_sign_in_page_has_a_language_switch(client):
    body = client.get("/auth/login").get_data(as_text=True)
    assert 'name="lang" value="ar"' in body, "no Arabic button on the sign-in page"
    assert 'name="lang" value="en"' in body, "no English button on the sign-in page"


def test_a_signed_out_visitor_can_switch_language(client):
    """No session, no user row -- the route must still take it."""
    assert _page_direction(client.get("/auth/login").get_data(as_text=True)) == "ltr"

    r = client.post("/settings/lang", data={"lang": "ar"})
    assert r.status_code in (200, 302), r.status_code
    assert _page_direction(
        client.get("/auth/login").get_data(as_text=True)) == "rtl"


def test_switching_language_returns_to_the_sign_in_page(client):
    """set_lang redirects to `next`, then the Referer, then the launcher. A
    signed-out visitor sent to the launcher gets bounced back here having
    apparently accomplished nothing, so login.html posts `next` explicitly."""
    body = client.get("/auth/login").get_data(as_text=True)
    assert 'name="next" value="/auth/login"' in body

    r = client.post("/settings/lang", data={"lang": "ar", "next": "/auth/login"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/auth/login")
