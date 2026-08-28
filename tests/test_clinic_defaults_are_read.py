# -*- coding: utf-8 -*-
"""The System Settings dropdowns must actually do something.

Four controls on that page saved, flashed "Settings saved successfully.", and
were then read by NOTHING. The dropdown even redisplayed the saved value on the
next load, which is what made it convincing: it looked exactly like a setting
that worked.

`default_language` is the one that matters commercially. This product is sold
to Egyptian clinics; a clinic switching its interface to Arabic and watching
every screen stay in English is not a cosmetic defect.

These tests pin the resolution ORDER too, because the order is the part that is
easy to get wrong later: a user's own choice must beat the clinic default, or
the one Arabic-preferring vet on an English-defaulted clinic gets overridden on
every page load.
"""
import re

import models.database as db


def _html_tag(body: str) -> str:
    """The <html> element, and only it.

    Searching the whole page for lang="ar" does not work: the sign-in page
    carries a permanent language switcher whose Arabic button is literally
    <button ... lang="ar">عربي</button>, so the substring is present no matter
    what the setting says. The first version of these tests did exactly that
    and passed with the feature switched off.
    """
    m = re.search(r"<html[^>]*>", body)
    assert m, "page has no <html> tag to read the language off"
    return m.group(0)


def _set(app, key, value):
    with app.app_context():
        db.set_setting(key, value, "appearance", "test")


def _lang_seen_by_a_template(client):
    """Render a page and ask what language the context processor chose.

    The sign-in page is deliberate: it is what a VISITOR sees, before any user
    row exists, which is the case the clinic-wide default is FOR.
    """
    return client.get("/auth/login")


def test_the_clinic_language_default_is_actually_used(app, client):
    """The whole point. Set Arabic, see Arabic."""
    _set(app, "default_language", "ar")
    r = _lang_seen_by_a_template(client)
    assert r.status_code == 200
    # templates/login.html lines 2-3 render both of these straight from
    # current_lang, which the context processor sets from `lang`.
    tag = _html_tag(r.get_data(as_text=True))
    assert 'lang="ar"' in tag, (
        "default_language=ar was saved and the page still rendered %s - "
        "the clinic-wide setting is being ignored again" % tag)
    assert 'dir="rtl"' in tag, (
        "language resolved to Arabic but the page is still left-to-right")


def test_a_users_own_language_beats_the_clinic_default(app, client):
    """Order matters. A clinic default must not override a person's choice.

    Uses the anonymous client: auth_client is already signed in, so /auth/login
    answers it with a 302 to the dashboard and the assertion below would have
    nothing to read.
    """
    _set(app, "default_language", "ar")
    with client.session_transaction() as s:
        s["lang"] = "en"          # the person's own choice, higher precedence
    r = client.get("/auth/login")
    assert r.status_code == 200
    tag = _html_tag(r.get_data(as_text=True))
    assert 'lang="en"' in tag, (
        "the clinic default overrode the user's own choice: %s" % tag)


def test_saving_the_setting_takes_effect_immediately(app, client):
    """get_setting caches for 300 seconds.

    The settings route used to write this with its own hand-rolled upsert,
    which never invalidated that cache - so the clinic would have saved Arabic
    and kept seeing English for five minutes, then blamed the save. Writing
    through db.set_setting() is what makes this pass.
    """
    _set(app, "default_language", "en")
    with app.app_context():
        assert db.get_setting("default_language", "") == "en"
    _set(app, "default_language", "ar")
    with app.app_context():
        assert db.get_setting("default_language", "") == "ar", (
            "the cached value survived the write - set_setting did not "
            "invalidate setting:default_language")


def test_the_theme_default_is_read_too(app):
    """Same defect, same page, quieter consequence."""
    _set(app, "default_theme", "logo")
    with app.app_context():
        assert db.get_setting("default_theme", "") == "logo"


def test_no_setting_still_falls_back_cleanly(app, client):
    """An install that has never opened the settings page must still render."""
    _set(app, "default_language", "")
    r = client.get("/auth/login")
    assert r.status_code == 200
