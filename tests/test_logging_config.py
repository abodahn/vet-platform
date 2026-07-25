"""
Self-check for models/logging_setup.py — stdlib + Flask only, no DB, no network.

Run:  python -m pytest tests/test_logging_config.py -q
"""
import logging
import os
import sys
import tempfile

from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.logging_setup import RequestIdFilter, init_logging, mask_dsn  # noqa: E402

_TAG = "_vet_logging_handler"


def _fresh_app():
    """Flask app rooted in a temp dir so logs/app.log lands outside the project."""
    app = Flask(__name__, root_path=tempfile.mkdtemp(prefix="vetlog_"))

    @app.route("/ping")
    def ping():
        return "pong"

    return app


def _our_handlers():
    return [h for h in logging.getLogger().handlers if getattr(h, _TAG, False)]


def test_init_logging_is_idempotent():
    app = _fresh_app()
    init_logging(app)
    first = len(_our_handlers())
    assert first == 2, f"expected console + file handler, got {first}"

    init_logging(app)          # same app, second call
    init_logging(_fresh_app())  # different app, same process
    assert len(_our_handlers()) == first, "init_logging duplicated handlers"

    # before_request/after_request registered exactly once per app
    assert len(app.before_request_funcs[None]) == 1
    assert len(app.after_request_funcs[None]) == 1


def test_correlation_id_is_injected_and_returned():
    app = _fresh_app()
    init_logging(app)

    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-", "outside a request the id must degrade, not explode"

    resp = app.test_client().get("/ping")
    rid = resp.headers.get("X-Request-ID")
    assert rid and rid != "-" and len(rid) == 8, f"bad X-Request-ID: {rid!r}"

    with app.test_request_context("/ping"):
        from flask import g
        g.request_id = "deadbeef"
        r2 = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
        RequestIdFilter().filter(r2)
        assert r2.request_id == "deadbeef"


def test_mask_dsn_hides_the_password():
    secret = "sup3r-s3cret!"
    masked = mask_dsn(f"postgresql://vetuser:{secret}@ep-x.aws.neon.tech:5432/vetclinic?sslmode=require")
    assert secret not in masked
    assert masked == "postgresql://vetuser:***@ep-x.aws.neon.tech:5432/vetclinic?sslmode=require"

    assert mask_dsn("") == ""
    assert mask_dsn("postgresql://localhost:5432/db") == "postgresql://localhost:5432/db"  # no creds
    assert "hunter2" not in mask_dsn("postgres://u:hunter2@h/d")


if __name__ == "__main__":
    test_init_logging_is_idempotent()
    test_correlation_id_is_injected_and_returned()
    test_mask_dsn_hides_the_password()
    print("all logging self-checks passed")
