"""Spend protection on the public Petsy endpoint.

/petsy/chat is unauthenticated by design — it is the customer-facing widget —
and every call costs money at the AI provider. Three separate holes existed:

  1. the per-IP limiter keyed on request.remote_addr, which behind a proxy is
     the PROXY's address, so every public visitor shared one bucket;
  2. no message-length limit, so one request could carry an arbitrary payload;
  3. no global ceiling, so anyone with a pool of addresses had unlimited spend.

Runs on SQLite with no PostgreSQL and no network — the AI client is never
called because every test stops at a guard before it.
"""
import pytest

from blueprints.petsy import routes as petsy


def test_real_ip_is_used_not_proxy_address(app):
    """Behind a proxy every visitor would otherwise share one rate-limit bucket."""
    with app.test_request_context(
        "/petsy/chat", method="POST",
        headers={"X-Forwarded-For": "197.1.2.3, 10.0.0.1"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    ):
        from flask import request
        assert petsy._sec.get_real_ip(request) == "197.1.2.3"


def test_empty_message_rejected(client):
    r = client.post("/petsy/chat", json={"message": "   "})
    assert r.status_code == 400


def test_overlong_message_rejected_before_any_ai_call(client):
    r = client.post("/petsy/chat",
                    json={"message": "x" * (petsy._MAX_MSG_CHARS + 1)})
    assert r.status_code == 400
    assert "too long" in (r.get_json() or {}).get("error", "").lower()


def test_history_is_trimmed_to_a_character_budget():
    """Eight turns of 100 KB each costs the same as a thousand short questions."""
    history = [{"role": "user", "content": "y" * 5000} for _ in range(8)]
    kept, total = [], 0
    for m in reversed(history):
        total += len(m["content"])
        if total > petsy._MAX_HISTORY_CHARS:
            break
        kept.insert(0, m)
    assert len(kept) < len(history)
    assert sum(len(m["content"]) for m in kept) <= petsy._MAX_HISTORY_CHARS


def test_daily_cap_blocks_anonymous_calls_once_spent(app, monkeypatch):
    monkeypatch.setattr(petsy, "_PUBLIC_DAILY_CAP", 3)
    with app.app_context():
        allowed = sum(1 for _ in range(10) if petsy._public_budget_left("1.2.3.4"))
    assert allowed == 3, "the cap did not hold"


def test_cap_failure_allows_the_call_but_is_not_silent(app, monkeypatch, caplog):
    """Bookkeeping must never break the widget — but a broken cap is an
    unbounded bill, so it has to be loud."""
    def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(petsy, "_ensure_usage_table",
                        lambda conn: (_ for _ in ()).throw(RuntimeError("db down")))
    with app.app_context():
        with caplog.at_level("ERROR"):
            assert petsy._public_budget_left("1.2.3.4") is True
    assert any("usage accounting failed" in r.message.lower() or
               "usage accounting failed" in r.getMessage().lower()
               for r in caplog.records), "failure was swallowed silently"
