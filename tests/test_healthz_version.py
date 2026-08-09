"""/healthz must answer "what is running here" without leaking which build.

The server is a file copy with no .git, so config.py falls back to the
GIT_COMMIT env var that deploy/push_app.sh writes. These tests pin both halves:
the public probe carries the version number, the commit only appears to a
caller holding the operator key.
"""
import importlib

import pytest


@pytest.fixture(autouse=True)
def _restore_version_info():
    """Put config.VERSION_INFO back exactly as it was.

    These tests reload `config` to exercise the GIT_COMMIT fallback, and a
    reload recomputes VERSION_INFO for the WHOLE session — every later test
    sees the new value. That is not hypothetical: with no GIT_COMMIT set,
    _git_commit() reads .git/HEAD, so a commit landing while the suite runs
    changed the value mid-session and broke an unrelated assertion in
    test_observability.py that compares a release string captured at app-import
    time against config.VERSION_INFO read at assert time.

    Restoring the original object, rather than reloading again, means the
    result cannot depend on what git is doing at that moment.
    """
    import config
    saved = config.VERSION_INFO
    yield
    config.VERSION_INFO = saved


def _version_info(monkeypatch, commit="", build_date=""):
    """Re-read config with the given environment — VERSION_INFO is module-level."""
    import config
    monkeypatch.setenv("GIT_COMMIT", commit)
    monkeypatch.setenv("BUILD_DATE", build_date)
    importlib.reload(config)
    return config


def test_the_public_probe_does_not_carry_the_commit(client):
    resp = client.get("/healthz")
    assert resp.status_code in (200, 503)
    body = resp.get_json()
    assert "version" in body
    assert "commit" not in body, "the commit fingerprints the build to anybody"
    assert "+" not in body["version"], (
        "version must be the plain number; %r looks like number+commit"
        % body["version"])


def test_the_operator_key_does_reveal_the_commit(app, client, monkeypatch):
    key = "operator-key-for-this-test"
    monkeypatch.setitem(app.config, "API_V1_KEY", key)
    resp = client.get("/healthz", headers={"Authorization": "Bearer " + key})
    body = resp.get_json()
    for field in ("commit", "built", "full", "checks", "clinic"):
        assert field in body, "%s should be behind the operator key" % field


def test_a_wrong_key_reveals_nothing(app, client, monkeypatch):
    monkeypatch.setitem(app.config, "API_V1_KEY", "the-real-key")
    resp = client.get("/healthz", headers={"Authorization": "Bearer wrong"})
    body = resp.get_json()
    assert "commit" not in body
    assert "checks" not in body


def test_git_commit_env_var_wins_over_reading_dot_git(monkeypatch):
    """The deployed case: no .git on the box, GIT_COMMIT supplies the answer."""
    cfg = _version_info(monkeypatch, commit="a" * 40, build_date="2026-08-09")
    try:
        assert cfg.VERSION_INFO["commit"] == "a" * 12, "truncated to 12 chars"
        assert cfg.VERSION_INFO["built"] == "2026-08-09"
        assert cfg.VERSION_INFO["full"].endswith("+" + "a" * 12)
    finally:
        _version_info(monkeypatch, commit="", build_date="")


def test_no_stamp_and_no_git_is_not_an_error(monkeypatch, tmp_path):
    """A clinic PC has neither. It must still report a version, not blow up."""
    cfg = _version_info(monkeypatch, commit="", build_date="")
    try:
        assert cfg.VERSION_INFO["version"]
        assert cfg.VERSION_INFO["full"] == cfg.VERSION_INFO["version"] or \
            "+" in cfg.VERSION_INFO["full"]
    finally:
        _version_info(monkeypatch, commit="", build_date="")
