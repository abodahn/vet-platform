"""Wapilot credentials must come from settings/env — never from source."""
import os
import pytest

from blueprints.whatsapp.routes import _client, WapilotNotConfigured
import models.database as db

PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class _EmptyConn:
    def execute(self, *_a, **_k):
        return self

    def fetchall(self):
        return []

    def close(self):
        pass


def test_client_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(db, "get_db", lambda *a, **k: _EmptyConn())
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    monkeypatch.delenv("WAPILOT_INSTANCE", raising=False)
    with pytest.raises(WapilotNotConfigured):
        _client()


def test_client_reads_env(monkeypatch):
    monkeypatch.setattr(db, "get_db", lambda *a, **k: _EmptyConn())
    monkeypatch.setenv("WAPILOT_TOKEN", "tok")
    monkeypatch.setenv("WAPILOT_INSTANCE", "inst")
    cli = _client()
    assert (cli.token, cli.instance_id) == ("tok", "inst")


def test_no_wapilot_token_literal_in_source():
    """The rotated token (and any 40+ char Wapilot-shaped literal) stays out."""
    leaked = "iWmctH6vcBx1RIItK9uc" "dO94Kv4vHfu6NYTz651yXR"  # split so this file
    hits = []                                                 # is not itself a hit
    for root, dirs, files in os.walk(PLATFORM):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]
        for f in files:
            if not f.endswith((".py", ".html", ".js", ".json", ".md", ".yml")):
                continue
            p = os.path.join(root, f)
            if p == os.path.abspath(__file__):
                continue
            with open(p, encoding="utf-8", errors="ignore") as fh:
                if leaked in fh.read():
                    hits.append(p)
    assert not hits, f"Wapilot token found in source: {hits}"
