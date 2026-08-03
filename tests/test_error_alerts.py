# -*- coding: utf-8 -*-
"""An unhandled 500 has to reach a human.

Before this, a 500 was written to a log table and that was the end of it.
Nobody watches a log table. The pilot failure mode is: the clinic hits an error
at 11am, works around it, mentions it three days later as "the system was being
weird", and by then the trace has rotated away.

What matters here, in order:

  1. it notifies at all;
  2. it does NOT notify twenty times for one broken page reloaded twenty times,
     because a notification list nobody reads is the same as no notifications;
  3. it never raises -- it runs inside the 500 handler, so a reporter that can
     fail turns one broken page into a crash loop;
  4. it does not put a stack trace in front of clinic staff.
"""
import pytest

import models.database as db
from models import error_alerts


@pytest.fixture(autouse=True)
def _clean_cooldowns():
    error_alerts.reset()
    yield
    error_alerts.reset()


def _notice_count(app):
    with app.app_context():
        conn = db.get_db()
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM notifications WHERE title=?",
                ("A page failed with an error",)).fetchone()[0]
        finally:
            conn.close()


def test_an_error_notifies_the_managers(app):
    before = _notice_count(app)
    with app.app_context():
        assert error_alerts.report("/finance/invoices", ValueError("boom")) is True
    assert _notice_count(app) > before, "a 500 produced no notification"


def test_the_same_error_twice_notifies_once(app):
    """One broken page reloaded is one problem, not twenty."""
    with app.app_context():
        assert error_alerts.report("/finance/invoices", ValueError("boom")) is True
        after_first = _notice_count(app)
        assert error_alerts.report("/finance/invoices", ValueError("boom again")) is False
        assert _notice_count(app) == after_first


def test_the_message_is_not_part_of_the_signature(app):
    """A failing page usually varies only by the id in the message, so
    including it would defeat the cooldown exactly when it is needed."""
    a = error_alerts.signature_for("/pets/1", KeyError("pet 1"))
    b = error_alerts.signature_for("/pets/1", KeyError("pet 2"))
    assert a == b


def test_a_different_page_is_reported_separately(app):
    with app.app_context():
        assert error_alerts.report("/finance/invoices", ValueError("x")) is True
        assert error_alerts.report("/inventory/items", ValueError("x")) is True


def test_a_different_exception_type_is_reported_separately(app):
    with app.app_context():
        assert error_alerts.report("/x", ValueError("a")) is True
        assert error_alerts.report("/x", KeyError("a")) is True


def test_no_stack_trace_reaches_the_notification(app):
    """Staff cannot act on a traceback and it can carry patient data."""
    with app.app_context():
        error_alerts.report("/visits/9", RuntimeError("Traceback: patient Rex, owner 0100"))
        conn = db.get_db()
        try:
            body = conn.execute(
                "SELECT body FROM notifications WHERE title=? ORDER BY id DESC LIMIT 1",
                ("A page failed with an error",)).fetchone()[0]
        finally:
            conn.close()
    assert "Rex" not in body and "0100" not in body
    assert "/visits/9" in body, "the notification did not say which page failed"


def test_reporting_never_raises_even_if_delivery_fails(app, monkeypatch):
    """It runs inside the 500 handler. A reporter that can fail turns one
    broken page into a crash loop."""
    def explode(*a, **kw):
        raise RuntimeError("notifications table is gone")
    monkeypatch.setattr(db, "notify_managers", explode)
    with app.app_context():
        assert error_alerts.report("/anything", ValueError("x")) is False


def test_the_500_handler_actually_calls_it(app, monkeypatch):
    """The wiring, not just the helper.

    Registered through the app's own error handler so a future refactor that
    drops the call is caught here rather than in production.
    """
    seen = []
    monkeypatch.setattr(error_alerts, "report",
                        lambda path, exc, user="": seen.append((path, type(exc))) or True)

    # The registered handler is invoked directly rather than by adding a route:
    # the `app` fixture is session-scoped and has already served requests, and
    # Flask refuses late route registration ("setup method 'route' can no longer
    # be called"). Looking the handler up keeps the test about the wiring.
    from werkzeug.exceptions import InternalServerError
    handler = app.error_handler_spec[None][500][InternalServerError]
    with app.test_request_context("/__boom__"):
        resp, code = handler(RuntimeError("deliberate"))
    assert code == 500
    assert seen and seen[0][0] == "/__boom__", "the 500 handler did not report the error"
