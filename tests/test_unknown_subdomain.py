# -*- coding: utf-8 -*-
"""What a stranger gets when the subdomain is not a clinic.

Found on the live demo server, not here: every request to an unregistered
subdomain returned 500 instead of the 404 the app has a handler for, because
the 404 page could not render. Then, once it could, the sign-in page started
returning 200 under any subdomain at all -- because UnknownTenant was only
raised at the first database read, and a login form does not read anything.

Neither leaked a record. Both are still wrong, and both are the kind of thing
nobody notices until a customer types their own clinic's name with two Os.
"""
import os

import pytest

import models.database as db
from models import tenancy


@pytest.fixture
def tenanted(app, tmp_path):
    """A registry with exactly one clinic in it, torn down afterwards."""
    saved = tenancy._registry_path
    tenancy.configure(str(tmp_path / "tenants.db"))
    with tenancy._registry() as conn:
        conn.execute(
            "INSERT INTO tenants (slug, name, db_path, status) VALUES (?,?,?,?)",
            ("realclinic", "Real Clinic", str(tmp_path / "realclinic.db"), "active"))
        conn.commit()
    yield
    tenancy.configure(saved)


def _get(app, path, host):
    return app.test_client().get(path, headers={"Host": host})


# ── the 404 has to be reachable ───────────────────────────────────────────────

def test_unknown_subdomain_is_404_not_500(app, tenanted):
    r = _get(app, "/auth/login", "nosuchclinic.aleefy.online")
    assert r.status_code == 404, (
        f"got {r.status_code}. 500 means the error page itself crashed; "
        "200 means the page rendered under a clinic that does not exist.")


def test_the_404_page_actually_renders(app, tenanted):
    """The regression that caused the 500: error.html goes through the same
    context processor as every other template, and that processor called
    get_clinic() -- which raises UnknownTenant again, inside the handler for
    UnknownTenant."""
    r = _get(app, "/", "nosuchclinic.aleefy.online")
    body = r.get_data(as_text=True)
    assert "Traceback" not in body
    assert len(body) > 100, "error page came back empty"


def test_no_login_form_under_an_unregistered_subdomain(app, tenanted):
    """A branded sign-in page on a subdomain that belongs to nobody is a
    phishing surface and a support call."""
    body = _get(app, "/auth/login", "nosuchclinic.aleefy.online").get_data(as_text=True)
    assert 'name="password"' not in body


# ── the boundary itself ───────────────────────────────────────────────────────

def test_unknown_subdomain_never_reaches_the_default_database(app, tenanted):
    """The one that would actually matter: falling through would serve one
    clinic's medical records under another clinic's name."""
    with pytest.raises(tenancy.UnknownTenant):
        with tenancy.use("nosuchclinic"):
            tenancy.target()


def test_a_registered_clinic_still_resolves(app, tenanted):
    with tenancy.use("realclinic"):
        assert tenancy.target()["db_path"].endswith("realclinic.db")


def test_no_subdomain_is_not_a_tenant(app, tenanted):
    """The apex is the marketing site and the health check has no Host at all.
    Both must stay in legacy mode rather than 404."""
    assert tenancy.slug_from_host("aleefy.online") == ""
    assert tenancy.slug_from_host("63.186.196.107") == ""
    assert tenancy.slug_from_host("ip-172-31-18-132") == ""
    assert tenancy.slug_from_host("www.aleefy.online") == ""


# ── the visitor's language ────────────────────────────────────────────────────

def _page_direction(html):
    """The <html> element's dir. Not a substring search on the body: pages that
    show an English label with its Arabic translation underneath put dir="rtl"
    on the translation, correctly, on an otherwise left-to-right page."""
    import re
    m = re.search(r"<html[^>]*\bdir=\"(rtl|ltr)\"", html)
    assert m, "the <html> element has no dir attribute at all"
    return m.group(1)


def test_default_language_is_configurable(app, monkeypatch):
    """Before a user exists there is no user row to read a language from, so
    the sign-in page took a hardcoded "en" -- English first contact for an
    Arabic-first product sold in Cairo."""
    monkeypatch.setenv("PLATFORM_DEFAULT_LANG", "ar")
    assert _page_direction(
        app.test_client().get("/auth/login").get_data(as_text=True)) == "rtl"

    monkeypatch.setenv("PLATFORM_DEFAULT_LANG", "en")
    assert _page_direction(
        app.test_client().get("/auth/login").get_data(as_text=True)) == "ltr"


def test_default_language_falls_back_to_english(app, monkeypatch):
    monkeypatch.delenv("PLATFORM_DEFAULT_LANG", raising=False)
    assert _page_direction(
        app.test_client().get("/auth/login").get_data(as_text=True)) == "ltr"
