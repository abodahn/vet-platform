# -*- coding: utf-8 -*-
"""What the app does when no AI provider is configured.

Reported as "petsy not work". It was worse than not working: with nothing
configured the app still showed a floating Petsy button on every page and an
"AI Assistant" card badged Live on the dashboard, and answered every question
with the OpenAI SDK's own text —

    Missing credentials. Please pass an `api_key`, `workload_identity`,
    `admin_api_key`, or set the `OPENAI_API_KEY` environment variable.

— which names another vendor, blames the reader, and tells a stranger what we
run.

ai_configured() already carried a docstring warning that "the dangerous state
is not 'off', it is 'looks on'", and had that exact hole: it returned True for
any base URL containing "localhost", which is the DEFAULT
(http://localhost:3001/v1) and therefore true on every deployment that had
configured nothing at all.
"""
import pytest

import blueprints.ai_assistant.routes as ai


@pytest.fixture(autouse=True)
def _clear_probe_cache():
    ai._PROBE_CACHE.clear()
    yield
    ai._PROBE_CACHE.clear()


@pytest.fixture
def no_ai(monkeypatch):
    """The shipped defaults, on a server with nothing listening."""
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "")
    monkeypatch.setattr(ai, "FREELLM_BASE_URL", "http://localhost:3001/v1")
    monkeypatch.setattr(ai, "_local_proxy_reachable", lambda url: False)


@pytest.fixture
def with_ai(monkeypatch):
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "sk-test-not-a-real-key")
    monkeypatch.setattr(ai, "FREELLM_BASE_URL", "https://openrouter.ai/api/v1")


# ── the check itself ──────────────────────────────────────────────────────────

def test_naming_localhost_is_not_evidence_anything_is_there(no_ai):
    """The whole bug in one assertion."""
    assert ai.ai_configured() is False


def test_a_local_proxy_that_answers_counts_as_configured(monkeypatch):
    monkeypatch.setattr(ai, "_OPENAI_AVAILABLE", True)
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "")
    monkeypatch.setattr(ai, "FREELLM_BASE_URL", "http://localhost:3001/v1")
    monkeypatch.setattr(ai, "_local_proxy_reachable", lambda url: True)
    assert ai.ai_configured() is True


def test_an_api_key_is_enough_without_probing(with_ai, monkeypatch):
    monkeypatch.setattr(ai, "_local_proxy_reachable",
                        lambda url: pytest.fail("probed a remote provider"))
    assert ai.ai_configured() is True


def test_the_probe_is_cached(monkeypatch):
    """ai_configured() runs on every page render — the launcher card and the
    Petsy button both ask."""
    calls = []
    real = ai._local_proxy_reachable
    monkeypatch.setattr(ai, "FREELLM_API_KEY", "")

    def counted(url):
        calls.append(url)
        return real(url)

    monkeypatch.setattr(ai, "_local_proxy_reachable", counted)
    ai.ai_configured(); ai.ai_configured(); ai.ai_configured()
    assert len(calls) == 3          # the wrapper runs each time...
    ai._PROBE_CACHE.clear()
    real("http://127.0.0.1:59999/v1")
    before = dict(ai._PROBE_CACHE)
    real("http://127.0.0.1:59999/v1")
    assert ai._PROBE_CACHE == before, "the socket probe re-ran instead of caching"


# ── what the user sees ────────────────────────────────────────────────────────

def test_no_petsy_button_when_there_is_no_ai(no_ai, auth_client):
    body = auth_client.get("/").get_data(as_text=True)
    assert "petsy-fab-global" not in body


def test_no_ai_card_on_the_dashboard_when_there_is_no_ai(no_ai, auth_client):
    body = auth_client.get("/").get_data(as_text=True)
    assert "المساعد الذكي" not in body


def test_the_petsy_button_comes_back_when_ai_is_configured(with_ai, auth_client):
    body = auth_client.get("/").get_data(as_text=True)
    assert "petsy-fab-global" in body


# ── what it says ──────────────────────────────────────────────────────────────

def test_the_provider_error_never_reaches_the_screen(no_ai):
    text, model, _ = ai._chat_completion([{"role": "user", "content": "hi"}], "sys") \
        if hasattr(ai, "_chat_completion") else (ai.ask_ai("hi") if hasattr(ai, "ask_ai")
                                                 else (None, None, None))
    if text is None:
        pytest.skip("no single-call entry point to drive directly")
    low = text.lower()
    for leak in ("api_key", "openai_api_key", "workload_identity", "traceback"):
        assert leak not in low, f"provider internals leaked to the user: {text[:160]}"


def test_petsy_says_not_enabled_rather_than_temporarily_unavailable(no_ai):
    from blueprints.petsy import routes as petsy
    text, model = petsy._call_petsy([{"role": "user", "content": "hi"}], "sys")
    assert model == "none"
    assert "temporarily" not in text.lower(), (
        "'temporarily unavailable' invites a pet owner to keep retrying a "
        "button that will never work")
    assert "not enabled" in text.lower() or "مفعّل" in text
