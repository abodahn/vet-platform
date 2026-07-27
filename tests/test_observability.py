"""
Self-check for the observability layer — version string, Sentry scrubbing,
log retention, idempotent logging.

Stdlib + Flask only: SQLite (in fact no database at all), and **no network**.
Sentry is exercised through a stub module injected into sys.modules, so the
suite proves the wiring without ever contacting sentry.io.

Run:  python -m pytest tests/test_observability.py -q
"""
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config                                                    # noqa: E402
from models import logging_setup                                 # noqa: E402
from models.logging_setup import (                               # noqa: E402
    _redact, _scrub_event, _init_sentry, init_logging,
)

_TAG = "_vet_logging_handler"


def _fresh_app():
    """Flask app rooted in a temp dir so logs/app.log lands outside the project."""
    app = Flask(__name__, root_path=tempfile.mkdtemp(prefix="vetobs_"))

    @app.route("/ping")
    def ping():
        return "pong"

    return app


# ══════════════════════════════════════════════════════════════════════════════
#  T1 — version string
# ══════════════════════════════════════════════════════════════════════════════

def test_version_file_is_the_source_of_truth():
    with open(os.path.join(config.BASE_DIR, "VERSION"), encoding="utf-8") as fh:
        on_disk = fh.read().strip()
    assert on_disk, "VERSION file is empty"
    assert config.VERSION_INFO["version"] == on_disk
    assert config.VERSION_INFO["full"].startswith(on_disk)
    # A date, not a placeholder.
    datetime.strptime(config.VERSION_INFO["built"], "%Y-%m-%d")


def test_version_degrades_without_git(tmp_path, monkeypatch):
    """A deployed clinic has no .git — that must be a blank commit, not a crash."""
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.delenv("BUILD_DATE", raising=False)
    (tmp_path / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    monkeypatch.setattr(config, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "_VERSION_FILE", str(tmp_path / "VERSION"))

    info = config._read_version()
    assert info["version"] == "9.9.9"
    assert info["commit"] == ""
    assert info["full"] == "9.9.9", "no commit -> no '+' suffix"
    datetime.strptime(info["built"], "%Y-%m-%d")


def test_version_degrades_without_version_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.delenv("BUILD_DATE", raising=False)
    monkeypatch.setattr(config, "BASE_DIR", str(tmp_path))
    monkeypatch.setattr(config, "_VERSION_FILE", str(tmp_path / "nope"))

    info = config._read_version()
    assert info["version"] == "0.0.0-unknown"
    assert info["built"] == "unknown"


def test_git_commit_reads_a_loose_ref(tmp_path, monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    sha = "a" * 40
    git = tmp_path / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git / "refs" / "heads" / "main").write_text(sha + "\n", encoding="utf-8")
    monkeypatch.setattr(config, "BASE_DIR", str(tmp_path))

    assert config._git_commit() == sha[:12]

    # Detached HEAD: the sha sits in HEAD itself.
    (git / "HEAD").write_text("b" * 40 + "\n", encoding="utf-8")
    assert config._git_commit() == "b" * 12


def test_git_commit_survives_garbage_and_env_override(tmp_path, monkeypatch):
    git = tmp_path / ".git"
    git.mkdir()
    (git / "HEAD").write_text("not a ref at all\n", encoding="utf-8")
    monkeypatch.setattr(config, "BASE_DIR", str(tmp_path))
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    assert config._git_commit() == "", "a malformed HEAD must not become a version"

    monkeypatch.setenv("GIT_COMMIT", "deadbeefcafebabe")
    assert config._git_commit() == "deadbeefcafe"


def test_version_is_on_every_response_header():
    """Place 2 of 3: an operator can read the build with curl, unauthenticated."""
    app = _fresh_app()
    init_logging(app)
    resp = app.test_client().get("/ping")
    assert resp.headers.get("X-App-Version") == config.VERSION_INFO["full"]
    assert resp.headers.get("X-Request-ID")


def test_version_is_logged_at_startup(caplog):
    """Place 1 of 3: the log the clinic emails you says which build wrote it."""
    with caplog.at_level(logging.INFO, logger="models.logging_setup"):
        init_logging(_fresh_app())
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "Starting version" in text
    assert config.VERSION_INFO["version"] in text
    assert config.CLINIC_ID in text


def test_version_seeds_the_env_names_the_ui_reads():
    """Place 3 of 3: /system/monitor reads these from the environment."""
    assert os.environ.get("APP_VERSION") == config.VERSION_INFO["version"]
    assert os.environ.get("RELEASE_DATE") == config.VERSION_INFO["built"]
    assert os.environ.get("BUILD_NUMBER")


# ══════════════════════════════════════════════════════════════════════════════
#  T2 — Sentry scrubbing and tagging
# ══════════════════════════════════════════════════════════════════════════════

def test_scrub_drops_request_payload():
    event = _scrub_event({
        "request": {
            "url": "https://clinic.example/crm/client/42?token=secret123",
            "query_string": "token=secret123",
            "data": {"pet_name": "Rex", "diagnosis": "FLUTD"},
            "cookies": {"session": "eyJ1c2VyIjo..."},
            "headers": {"Authorization": "Bearer abc", "Cookie": "session=x"},
            "env": {"REMOTE_ADDR": "10.0.0.4"},
        },
    })
    req = event["request"]
    for gone in ("query_string", "data", "cookies", "headers", "env"):
        assert gone not in req, f"{gone} reached the wire"
    assert req["url"] == "https://clinic.example/crm/client/42"
    assert "secret123" not in str(event)


def test_scrub_removes_traceback_locals():
    """A frame of add_invoice() holds the whole invoice."""
    event = _scrub_event({
        "exception": {"values": [{
            "type": "ZeroDivisionError",
            "stacktrace": {"frames": [
                {"function": "add_invoice",
                 "vars": {"total": "4820.00", "owner_name": "Mona Said",
                          "pet": {"name": "Rex", "chip": "9821"}}},
                {"function": "save_visit", "vars": {"diagnosis": "renal failure"}},
            ]},
        }]},
        "threads": {"values": [{"stacktrace": {"frames": [{"vars": {"x": 1}}]}}]},
    })
    blob = str(event)
    for leaked in ("4820.00", "Mona Said", "Rex", "9821", "renal failure"):
        assert leaked not in blob, f"{leaked!r} survived in a stack frame"
    for frame in event["exception"]["values"][0]["stacktrace"]["frames"]:
        assert "vars" not in frame
        assert frame["function"], "the frame itself must survive — that is the point"


@pytest.mark.parametrize("key, value", [
    ("pet_name",        "Rex"),
    ("owner_name",      "Mona Said"),
    ("patient_id_note", "renal failure"),
    ("diagnosis",       "FLUTD"),
    ("prescription",    "meloxicam 0.1mg"),
    ("vaccine_batch",   "LOT-4471"),
    ("invoice_total",   "4820.00"),
    ("payment_amount",  "1200"),
    ("salary",          "9000"),
    ("card_last4",      "4242"),
    ("client_phone",    "+201000000000"),
    ("email",           "a@b.com"),
    ("address",         "12 Nile St"),
    ("national_id",     "29001011234567"),
    ("api_key",         "sk-live-xxx"),
    ("password",        "hunter2"),
    ("POSTGRES_DSN",    "postgresql://u:p@h/db"),
])
def test_scrub_redacts_clinical_financial_and_identifying_keys(key, value):
    event = _scrub_event({"extra": {key: value}})
    assert event["extra"][key] == "[scrubbed]"
    assert value not in str(event)


def test_scrub_keeps_what_makes_the_event_useful():
    event = _scrub_event({
        "extra": {"module": "finance", "row_count": 12, "endpoint": "/finance/export"},
        "contexts": {"runtime": {"name": "CPython", "version": "3.11.4"}},
    })
    assert event["extra"] == {"module": "finance", "row_count": 12,
                              "endpoint": "/finance/export"}
    assert event["contexts"]["runtime"]["name"] == "CPython"


def test_redact_walks_nested_structures():
    out = _redact({"rows": [{"pet_name": "Rex", "qty": 2}], "safe": {"deep": {"total": 9}}})
    assert out["rows"][0]["pet_name"] == "[scrubbed]"
    assert out["rows"][0]["qty"] == 2
    assert out["safe"]["deep"]["total"] == "[scrubbed]"


def test_scrub_tags_the_event_with_clinic_version_and_request_id():
    """20 single-tenant deployments: an untagged event cannot be acted on."""
    app = _fresh_app()
    init_logging(app)

    event = _scrub_event({})
    assert event["tags"]["clinic"] == config.CLINIC_ID
    assert event["tags"]["version"] == config.VERSION_INFO["version"]
    assert event["tags"]["commit"]
    assert "request_id" not in event["tags"], "no request context, no id"

    with app.test_request_context("/ping"):
        from flask import g
        g.request_id = "abcd1234"
        in_req = _scrub_event({})
    assert in_req["tags"]["request_id"] == "abcd1234"


def test_scrub_survives_a_malformed_event():
    assert _scrub_event(None) is None
    assert _scrub_event({"exception": {"values": None}})["tags"]["clinic"]
    assert _scrub_event({"tags": "not-a-dict"})["tags"]["clinic"]


# ── Sentry initialisation, without the network and without the package ────────

class _FakeSentry:
    """Stands in for sentry_sdk. Records init() kwargs; sends nothing anywhere."""

    def __init__(self):
        self.kwargs = None
        self.tags = {}

    def init(self, **kwargs):
        self.kwargs = kwargs

    def set_tag(self, key, value):
        self.tags[key] = value


def test_absent_dsn_changes_nothing(monkeypatch):
    """No DSN: sentry_sdk must not even be imported."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)

    class _Explode:
        def __getattr__(self, name):
            raise AssertionError("sentry_sdk touched with no SENTRY_DSN set")

    monkeypatch.setitem(sys.modules, "sentry_sdk", _Explode())
    _init_sentry(_fresh_app())     # must be a silent no-op

    monkeypatch.setenv("SENTRY_DSN", "")
    _init_sentry(_fresh_app())


def test_dsn_without_the_package_warns_and_keeps_running(monkeypatch, caplog):
    monkeypatch.setenv("SENTRY_DSN", "https://key@o0.ingest.sentry.io/1")
    monkeypatch.setitem(sys.modules, "sentry_sdk", None)   # -> ImportError
    with caplog.at_level(logging.WARNING, logger="models.logging_setup"):
        _init_sentry(_fresh_app())   # no exception
    assert "sentry-sdk is not installed" in caplog.text


def test_dsn_with_the_package_configures_scrubbing(monkeypatch):
    fake = _FakeSentry()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setenv("SENTRY_DSN", "https://key@o0.ingest.sentry.io/1")
    monkeypatch.setenv("FLASK_ENV", "production")

    _init_sentry(_fresh_app())

    kw = fake.kwargs
    assert kw is not None, "init was never called"
    assert kw["send_default_pii"] is False
    assert kw["include_local_variables"] is False
    assert kw["max_breadcrumbs"] == 0
    assert kw["before_send"] is _scrub_event
    assert kw["environment"] == "production"
    assert kw["release"] == f"vet-platform@{config.VERSION_INFO['full']}"
    assert kw["traces_sample_rate"] == 0.0
    assert kw["sample_rate"] == 1.0
    assert fake.tags["clinic"] == config.CLINIC_ID


def test_sample_rates_are_tunable_from_env(monkeypatch):
    fake = _FakeSentry()
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake)
    monkeypatch.setenv("SENTRY_DSN", "https://key@o0.ingest.sentry.io/1")
    monkeypatch.setenv("SENTRY_SAMPLE_RATE", "0.25")
    monkeypatch.setenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")
    _init_sentry(_fresh_app())
    assert fake.kwargs["sample_rate"] == 0.25
    assert fake.kwargs["traces_sample_rate"] == 0.1


# ══════════════════════════════════════════════════════════════════════════════
#  T4 — log retention actually runs
# ══════════════════════════════════════════════════════════════════════════════

def test_retention_deletes_expired_json_logs(tmp_path, monkeypatch):
    """LOG_FILE_RETENTION_DAYS was documented and never applied — prove it now is."""
    import models.logging_db as ldb

    back, front = tmp_path / "backend", tmp_path / "frontend"
    back.mkdir()
    front.mkdir()
    monkeypatch.setattr(ldb, "_LOG_DIR_BACK", back)
    monkeypatch.setattr(ldb, "_LOG_DIR_FRONT", front)
    monkeypatch.setattr(ldb, "_RETENTION", 7)

    # UTC, matching how logging_db names the files.
    today = datetime.now(timezone.utc).replace(tzinfo=None)
    fresh = back / f"backend-{today:%Y-%m-%d}.log"
    stale = back / f"backend-{today - timedelta(days=30):%Y-%m-%d}.log"
    stale_f = front / f"frontend-{today - timedelta(days=30):%Y-%m-%d}.log"
    for p in (fresh, stale, stale_f):
        p.write_text("{}\n", encoding="utf-8")

    assert ldb.cleanup_old_logs() == 2
    assert fresh.exists(), "a log inside the retention window was deleted"
    assert not stale.exists() and not stale_f.exists()


def test_startup_runs_the_retention_sweep(monkeypatch):
    called = []
    monkeypatch.setattr(logging_setup, "_purge_expired_json_logs",
                        lambda: called.append(True))
    init_logging(_fresh_app())
    assert called == [True], "startup did not sweep expired logs"


def test_retention_sweep_never_kills_the_app(monkeypatch, caplog):
    import models.logging_db as ldb
    monkeypatch.setattr(ldb, "cleanup_old_logs",
                        lambda: (_ for _ in ()).throw(OSError("disk gone")))
    with caplog.at_level(logging.WARNING, logger="models.logging_setup"):
        logging_setup._purge_expired_json_logs()   # must not raise
    assert "retention sweep skipped" in caplog.text


# ══════════════════════════════════════════════════════════════════════════════
#  Idempotence — everything above is added inside init_logging
# ══════════════════════════════════════════════════════════════════════════════

def test_init_logging_is_still_idempotent():
    app = _fresh_app()
    init_logging(app)
    handlers = [h for h in logging.getLogger().handlers if getattr(h, _TAG, False)]
    init_logging(app)
    init_logging(_fresh_app())
    after = [h for h in logging.getLogger().handlers if getattr(h, _TAG, False)]
    assert len(after) == len(handlers), "init_logging duplicated handlers"
    assert len(app.before_request_funcs[None]) == 1
    assert len(app.after_request_funcs[None]) == 1
