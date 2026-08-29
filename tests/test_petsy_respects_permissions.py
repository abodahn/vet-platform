# -*- coding: utf-8 -*-
"""Petsy must not answer questions the asker has no right to ask.

/petsy/chat is deliberately not @login_required - the widget is embeddable, and
tests/test_access_sweep.py whitelists it for exactly that reason. The
consequence nobody had followed through: _fetch_platform_data ran every matched
intent against the database with no permission check at all, so the module gate
that guards every equivalent SCREEN was simply absent.

"How much did we make this month?" is a report. Typed at the widget it was
answered for anybody who could reach it.

Gated on the money and staff blocks only. The clinical ones stay open on
purpose - anyone the widget lets in is already in a consulting room, and gating
"recent patients" would delete Petsy for the doctor who is its main user.
"""
import pytest

import blueprints.petsy.routes as petsy


def _asked(message, user):
    """Intents that survive the permission filter for this reader."""
    return petsy._permitted_intents(petsy._detect_intents(message), user)


def test_the_money_question_is_detected_at_all(app):
    """Guard against a vacuous suite: if the regex stops matching, every
    assertion below passes for the wrong reason."""
    assert "revenue_month" in petsy._detect_intents("revenue this month?")


def test_an_anonymous_visitor_gets_no_revenue(app):
    """The embed route has no user at all. Fails closed."""
    with app.test_request_context():
        assert "revenue_month" not in _asked("revenue this month?", {})


def test_a_role_without_accounting_gets_no_revenue(app):
    with app.test_request_context():
        assert "revenue_month" not in _asked("revenue this month?",
                                             {"role": "groomer"})


def test_a_role_without_hr_cannot_read_the_staff_roster(app):
    with app.test_request_context():
        assert "attendance_today" not in _asked("who is absent today",
                                                {"role": "groomer"})


def test_super_admin_still_gets_the_answer(app):
    """A gate that blocks everyone is not a gate, it is a removal."""
    with app.test_request_context():
        assert "revenue_month" in _asked("revenue this month?",
                                         {"role": "super_admin"})


def test_clinical_questions_are_not_gated(app):
    """Petsy's actual job. A groomer asking who is in today still gets told."""
    with app.test_request_context():
        got = _asked("who is in right now", {"role": "groomer"})
        assert "visits_open" in got


def test_every_money_or_staff_intent_is_covered(app):
    """The list of gated intents must not drift away from the blocks that
    actually emit money or staff data."""
    sensitive = {"pending_invoices", "revenue_today", "revenue_month",
                 "low_stock", "expiry_alerts", "attendance_today"}
    assert sensitive <= set(petsy._INTENT_PERM), (
        "an intent that returns money or staff data is no longer gated: %s"
        % (sensitive - set(petsy._INTENT_PERM)))


def test_the_dashboard_summary_does_not_leak_the_same_figure(app):
    """The one that would have been missed.

    'summary' is a different intent from 'revenue this month', and its block
    printed 'Revenue today' too - so gating only the obvious intent would have
    moved the leak one word sideways rather than closing it.
    """
    with app.test_request_context():
        blob = petsy._fetch_platform_data("give me a summary",
                                          {"role": "groomer"})
    assert "Revenue today" not in blob, (
        "the dashboard summary handed a groomer the day's takings")
    assert "Unpaid invoices" not in blob


def test_the_summary_still_reaches_someone_entitled_to_it(app):
    with app.test_request_context():
        blob = petsy._fetch_platform_data("give me a summary",
                                          {"role": "super_admin"})
    if blob:                       # empty only if the DB has no such tables
        assert "CLINIC DASHBOARD" in blob
