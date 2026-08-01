# -*- coding: utf-8 -*-
"""AI assistance in the clinical flow.

One rule governs every test here: the system must never imply a check ran that
did not. An unreachable model, a missing key, an unparseable reply — each has to
be visibly "not checked", never silence and never an empty result that a busy
vet reads as an all-clear.

That is not hypothetical. drug_interactions previously returned safe=True when
the AI service was down, so an outage rendered as "Safe to prescribe".
"""
import json

import pytest

import blueprints.ai_assistant.routes as ai


def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


@pytest.fixture()
def vet(app, client):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE role IN ('super_admin','clinic_owner') "
            "ORDER BY id LIMIT 1").fetchone()
        conn.close()
        user = {k: row[k] for k in row.keys()
                if k not in ("password_hash", "totp_secret")}
    with client.session_transaction() as s:
        s["user"] = user
        s["lang"] = "en"
    return user


def _post(client, url, payload):
    return client.post(url, data=json.dumps(payload),
                       content_type="application/json",
                       headers={"X-CSRF-Token": _csrf(client)})


# ── "configured" must mean usable ────────────────────────────────────────────

def test_ai_is_not_configured_without_a_key(monkeypatch):
    """The chat screen reported "configured" from _OPENAI_AVAILABLE alone, which
    only says the openai package imported. With no key the UI promised a working
    assistant and every request failed at the network — the same dangerous
    "looks on" state a half-configured payment gateway has."""
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "")
    monkeypatch.setattr(ai, "FREELLM_BASE_URL", "https://openrouter.ai/api/v1")
    assert ai.ai_configured() is False


def test_a_local_proxy_needs_no_key(monkeypatch):
    """A localhost proxy is legitimately keyless; refusing it would disable AI
    for the deployment this app shipped with."""
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "")
    monkeypatch.setattr(ai, "FREELLM_BASE_URL", "http://localhost:3001/v1")
    assert ai.ai_configured() is True


def test_ai_is_not_configured_without_the_package(monkeypatch):
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", False)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-something")
    assert ai.ai_configured() is False


# ── differentials fail closed ────────────────────────────────────────────────

def test_suggestions_are_refused_when_ai_is_not_configured(client, vet, monkeypatch):
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", False)
    r = _post(client, "/ai/suggest-diagnosis", {"complaint": "Vomiting"})
    body = r.get_json()
    assert body["ran"] is False and body["suggestions"] == []
    assert "not configured" in body["note"].lower()


def test_an_unreachable_model_produces_no_suggestions_and_says_so(
        client, vet, monkeypatch):
    """The failure that matters: an empty list rendered without explanation
    would read as "nothing worth considering"."""
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-test")
    monkeypatch.setattr(ai, "call_ai",
                        lambda *a, **k: ("AI service temporarily unavailable", "none", ""))
    body = _post(client, "/ai/suggest-diagnosis",
                 {"complaint": "Vomiting"}).get_json()
    assert body["ran"] is False
    assert body["suggestions"] == []
    assert "not a statement" in body["note"].lower()


def test_an_empty_complaint_is_refused_before_calling_the_model(client, vet):
    body = _post(client, "/ai/suggest-diagnosis", {"complaint": "   "}).get_json()
    assert body["ran"] is False and body["suggestions"] == []


def test_suggestions_are_returned_with_the_disclaimer(client, vet, monkeypatch):
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-test")
    monkeypatch.setattr(ai, "call_ai", lambda *a, **k: (json.dumps({
        "suggestions": [
            {"diagnosis": "Acute gastroenteritis", "likelihood": "high",
             "why": "acute vomiting with dehydration",
             "rule_out": "abdominal palpation and hydration status"},
        ],
        "red_flags": ["dehydration"],
    }), "test-model", ""))

    body = _post(client, "/ai/suggest-diagnosis",
                 {"complaint": "Vomiting", "species": "Dog"}).get_json()
    assert body["ran"] is True
    assert body["suggestions"][0]["diagnosis"] == "Acute gastroenteritis"
    assert body["red_flags"] == ["dehydration"]
    assert "yours" in body["note"], "the disclaimer that the diagnosis is the vet's is missing"


def test_no_more_than_four_suggestions_reach_the_screen(client, vet, monkeypatch):
    """A long list invites scrolling instead of thinking."""
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-test")
    monkeypatch.setattr(ai, "call_ai", lambda *a, **k: (json.dumps({
        "suggestions": [{"diagnosis": f"D{i}", "likelihood": "low"} for i in range(9)]
    }), "m", ""))
    body = _post(client, "/ai/suggest-diagnosis", {"complaint": "x"}).get_json()
    assert len(body["suggestions"]) == 4


def test_suggestions_require_login(client):
    r = client.post("/ai/suggest-diagnosis", data="{}",
                    content_type="application/json")
    assert r.status_code in (302, 401, 403)


# ── the page hides what it cannot deliver ────────────────────────────────────

def test_the_workflow_page_hides_ai_when_it_is_unavailable(client, vet, monkeypatch):
    """A control that fails when pressed is worse than one never offered — the
    staff member has already committed to the step."""
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", False)
    html = client.get("/workflow/").get_data(as_text=True)
    assert "const AI_ON = false" in html


def test_the_workflow_page_offers_ai_when_it_is_available(client, vet, monkeypatch):
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-test")
    html = client.get("/workflow/").get_data(as_text=True)
    assert "const AI_ON = true" in html
    assert 'id="aiDxStrip"' in html and 'id="aiRxStrip"' in html
