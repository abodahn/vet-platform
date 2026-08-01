# -*- coding: utf-8 -*-
"""The public API can actually be rate limited.

It could not before. _check_rate_limit called sec.is_rate_limited(ip), which
counts rows in login_attempts — a table only record_failed_login ever writes,
and nothing in the public API writes it. So the counter the guard read stayed
empty for public traffic and the limit could never fire at any volume: the
endpoints are unauthenticated, create owners, pets and appointments, and send
WhatsApp messages.
"""
import json

import pytest

import models.security as sec


def _post(client, url, payload, ip="203.0.113.9"):
    return client.post(url, data=json.dumps(payload),
                       content_type="application/json",
                       headers={"X-Forwarded-For": ip})


BOOKING = {"ownerName": "Test Owner", "mobile": "01000000000",
           "petName": "Bes", "date": "2026-09-01"}


def test_flooding_the_booking_endpoint_is_eventually_refused(client):
    """The claim, end to end through the real route."""
    limit = 20
    seen_429 = False
    for i in range(limit + 5):
        r = _post(client, "/api/public/book", BOOKING)
        if r.status_code == 429:
            seen_429 = True
            break
    assert seen_429, \
        f"sent {limit + 5} bookings from one address without being throttled once"


def test_a_429_tells_the_caller_when_to_come_back(client):
    for _ in range(30):
        r = _post(client, "/api/public/book", BOOKING, ip="203.0.113.10")
        if r.status_code == 429:
            assert r.headers.get("Retry-After"), "429 with no Retry-After"
            assert int(r.headers["Retry-After"]) > 0
            return
    pytest.fail("never throttled")


def test_a_throttled_abuser_does_not_block_everyone_else(client):
    """Keyed per address. If one bad actor could shut the booking form for the
    whole internet, the limiter would be a denial-of-service tool."""
    for _ in range(30):
        _post(client, "/api/public/book", BOOKING, ip="203.0.113.11")
    r = _post(client, "/api/public/book", BOOKING, ip="198.51.100.4")
    assert r.status_code != 429, "a different client was caught by someone else's limit"


def test_buckets_are_independent(client):
    """A burst of contact forms must not close the booking form: an owner with
    a sick animal is the one who suffers."""
    for _ in range(20):
        _post(client, "/api/public/contact",
              {"name": "x", "mobile": "01000000000", "message": "hello"},
              ip="203.0.113.12")
    r = _post(client, "/api/public/book", BOOKING, ip="203.0.113.12")
    assert r.status_code != 429, "the contact-form limit also closed bookings"


# ── the primitive underneath ─────────────────────────────────────────────────

def test_throttle_records_the_hit_it_checks(app):
    """The actual bug in one line: the old path checked a counter that its own
    traffic never incremented."""
    with app.app_context():
        for i in range(3):
            over, _ = sec.throttle("t_unit", "1.2.3.4", 3, 60)
            assert over is (i >= 2), f"hit {i + 1} of 3 reported over={over}"


def test_throttle_is_scoped_by_bucket_and_key(app):
    with app.app_context():
        for _ in range(5):
            sec.throttle("t_a", "9.9.9.9", 3, 60)
        assert sec.throttle("t_b", "9.9.9.9", 3, 60)[0] is False, "buckets bled"
        assert sec.throttle("t_a", "8.8.8.8", 3, 60)[0] is False, "keys bled"


def test_the_window_expires(app):
    """A limit that never lifts is a permanent ban after a burst."""
    with app.app_context():
        for _ in range(5):
            sec.throttle("t_win", "7.7.7.7", 3, 60)
        assert sec.throttle("t_win", "7.7.7.7", 3, 60)[0] is True
        # A one-second window: the earlier hits are already outside it.
        assert sec.throttle("t_win", "7.7.7.7", 3, 0)[0] is False


def test_throttle_fails_OPEN_when_its_table_is_unreachable(app, monkeypatch):
    """A booking form that turns real clients away because a throttle table is
    missing is worse than one that briefly lets an abuser through."""
    import models.database as dbm
    monkeypatch.setattr(dbm, "get_db",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    with app.app_context():
        assert sec.throttle("t_broken", "1.1.1.1", 1, 60) == (False, 0)


def test_login_lockout_still_works(app):
    """The throttle uses its own table specifically so login is undisturbed."""
    with app.app_context():
        ip, user = "203.0.113.77", "someone"
        sec.clear_rate_limit(ip, user)
        for _ in range(sec.RATE_LIMIT_MAX):
            sec.record_failed_login(ip, user)
        assert sec.is_rate_limited(ip, user)[0] is True
        sec.clear_rate_limit(ip, user)
