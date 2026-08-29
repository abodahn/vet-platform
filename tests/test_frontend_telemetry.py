# -*- coding: utf-8 -*-
"""Browser error telemetry has to actually arrive somewhere.

base.html has captured JS errors, buffered them, kept them in localStorage while
offline and flushed them on reconnect since it was written. It posted them to
/api/v1/logs/frontend - a blueprint app.py has never registered. Every batch
404'd, the .catch re-queued it, and the next flush 404'd too. No browser error
from any clinic has ever reached the server.

The route now lives on system_bp rather than by registering api_v1_bp, because
that blueprint also exposes an unauthenticated /api/v1/health echoing FLASK_ENV,
and switching on nine dormant endpoints to gain one is a bad trade.
"""
import pathlib

import pytest

from conftest import get_csrf


def _post(client, payload):
    """Send the batch the way base.html does - with the CSRF header.

    The endpoint is CSRF-protected like every other POST in the app, and
    base.html sends X-CSRF-Token from the meta tag. A test that omits it is
    testing the CSRF layer, not this route.
    """
    return client.post('/system/logs/frontend', json=payload,
                       headers={'X-CSRF-Token': get_csrf(client)})


def test_the_endpoint_exists(app):
    adapter = app.url_map.bind("localhost")
    from werkzeug.exceptions import NotFound
    try:
        endpoint, _ = adapter.match("/system/logs/frontend", method="POST")
    except NotFound:
        pytest.fail("/system/logs/frontend is not routed")
    assert endpoint == "system.receive_frontend_log"


def test_a_signed_in_batch_is_accepted(auth_client):
    r = _post(auth_client, {"logs": [{"level": "ERROR",
                                      "event_name": "js_error",
                                      "message": "boom"}]})
    assert r.status_code == 200
    assert r.get_json()["accepted"] == 1


def test_an_anonymous_batch_is_discarded_not_redirected(client):
    """Rejected, and NOT with a redirect.

    An anonymous caller has no CSRF token in session, so the CSRF layer answers
    403 before the handler runs. That is the right outcome and the reason this
    route is not @login_required: the sign-in page ships this script too, and a
    302 to the login page is something a fetch() can do nothing useful with.
    A 403 resolves the promise, so the batch is dropped rather than re-queued
    forever by the .catch in base.html.

    What must never happen is a redirect or a 500.
    """
    r = _post(client, {"logs": [{"level": "ERROR", "message": "anon"}]})
    assert r.status_code in (204, 403), (
        "anonymous telemetry returned %d" % r.status_code)
    assert r.status_code not in (301, 302), "a fetch() cannot follow a login redirect"


def test_a_session_without_a_user_is_discarded_quietly(client):
    """The handler's own branch: CSRF passes, but nobody is signed in.

    Happens after a logout, on a page still holding the script. Discarded with
    204 - storing anonymous text would make this a log-poisoning and disk-fill
    endpoint.
    """
    from models.security import _CSRF_SESSION_KEY
    with client.session_transaction() as sess:
        sess[_CSRF_SESSION_KEY] = "tok-for-a-logged-out-session"
        sess.pop("user", None)
    r = client.post("/system/logs/frontend",
                    json={"logs": [{"level": "ERROR", "message": "anon"}]},
                    headers={"X-CSRF-Token": "tok-for-a-logged-out-session"})
    assert r.status_code == 204, (
        "a logged-out batch returned %d - it must be quietly discarded"
        % r.status_code)


def test_the_batch_is_capped(auth_client):
    """A looping device must not be able to write unbounded rows per request."""
    r = _post(auth_client, {"logs": [{"level": "INFO", "message": str(i)}
                                     for i in range(500)]})
    assert r.status_code == 200
    assert r.get_json()["accepted"] == 50


def test_rubbish_does_not_500(auth_client):
    """Failing to record an error must never itself become an error."""
    for payload in ({"logs": "not a list"}, {"logs": [None, 3, "x"]}, {}):
        r = _post(auth_client, payload)
        assert r.status_code in (200, 204), (
            "payload %r produced %d" % (payload, r.status_code))


def test_base_html_posts_to_the_registered_route():
    body = pathlib.Path("templates/base.html").read_text(
        encoding="utf-8", errors="ignore")
    assert "fetch('/system/logs/frontend'" in body
    assert "fetch('/api/v1/logs/frontend'" not in body
