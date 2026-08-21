# -*- coding: utf-8 -*-
"""The app-wide upload ceiling, and the one route that is allowed past it.

A clinic database restored from a USB stick is gigabytes; a patient photo is
not. blueprints/system/routes.py raises the ceiling for POST
/system/backup/upload only, by assigning request.max_content_length inside a
before_app_request hook.

That assignment is only legal on Flask >= 3.1 — on 3.0.x
Request.max_content_length is a read-only property and the assignment raises
"AttributeError: property 'max_content_length' of 'Request' object has no
setter", turning every backup upload into a 500 before the view is reached
(bug-505). requirements.txt still declares Flask>=3.0.0 with no floor, so a
permitted resolution can still pick 3.0.x. These two tests are what notices.

The ceiling is shrunk to a few bytes rather than posting a real 17 MB body:
same code path, same enforcement, none of the seconds.
"""
import io
import os

import pytest

import models.backup as bk


_CEILING = 1024                      # stand-in for the real 16 MB
_OVERSIZED = b"\x00" * (_CEILING * 4)


@pytest.fixture
def tiny_ceiling(app, monkeypatch):
    """Shrink MAX_CONTENT_LENGTH for one test.

    The `app` fixture is session-scoped, so this must be undone — monkeypatch
    does that, a bare assignment would leak a 1 KB ceiling into every test
    that ran afterwards.
    """
    monkeypatch.setitem(app.config, "MAX_CONTENT_LENGTH", _CEILING)
    return app


def _archives():
    """Only the archives — the backup dir also holds alert/lock sidecars that
    move on their own."""
    return {f for f in os.listdir(bk._backup_dir) if f.endswith(".db")}


def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post_oversized(client, url):
    return client.post(
        url,
        data={"_csrf_token": _csrf(client),
              "archive": (io.BytesIO(_OVERSIZED), "from_usb.db")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_an_oversized_upload_is_refused(tiny_ceiling, auth_client):
    """The ceiling is real everywhere else. If this ever stops being a 413 the
    exemption below has been widened into a hole."""
    resp = _post_oversized(auth_client, "/migration/upload")
    assert resp.status_code == 413


def test_the_backup_upload_route_is_exempt_from_the_ceiling(tiny_ceiling,
                                                            auth_client):
    """Not 413, and the view actually read the body: it rejects the garbage on
    its contents. On Flask 3.0.x this is a 500 from the AttributeError."""
    before = _archives()

    resp = _post_oversized(auth_client, "/system/backup/upload")

    assert resp.status_code != 413, "the backup-upload exemption is gone"
    assert resp.status_code == 200, resp.status_code
    assert "not a usable backup" in resp.data.decode("utf-8", "replace")
    assert _archives() == before, \
        "a rejected upload was left on disk"
