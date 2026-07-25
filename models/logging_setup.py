"""
Application logging — rotating file + console, with a per-request correlation ID.

Enable from the app factory with two lines:

    from models.logging_setup import init_logging
    init_logging(app)

What lands on disk (logs/app.log):
    2026-07-25 09:31:02 INFO    [a1b2c3d4] models.logging_setup: GET /auth/login -> 200 in 12.4ms

Deliberately NOT written to disk: request bodies, query strings, cookies,
Authorization headers, session contents. This app handles patient and financial
records; the log is a support tool, not a second copy of the database.

Separate from models/logging_db.py — that one is the structured audit trail in
PostgreSQL. This one is stdlib logging plumbing for "the clinic says it broke
this morning, what does the file say".
"""

import logging
import os
import re
import time
import uuid
from logging.handlers import RotatingFileHandler

from flask import g, has_request_context, request

# ── DSN masking ───────────────────────────────────────────────────────────────
# postgresql://user:pa$$w0rd@host:5432/db  ->  postgresql://user:***@host:5432/db
_DSN_RE = re.compile(r"(?P<head>[A-Za-z][A-Za-z0-9+.\-]*://[^:/@\s]+:)(?P<pw>[^@\s]+)(?P<tail>@)")


def mask_dsn(dsn: str) -> str:
    """Return `dsn` with any inline password replaced by ***. Safe to print.

    # ponytail: regex, not a URL parse — covers scheme://user:pass@host forms only.
    # Ceiling: a DSN that hides credentials elsewhere (key=value, service files)
    # passes through untouched. Switch to urllib.parse if such a form appears.
    """
    if not dsn:
        return ""
    return _DSN_RE.sub(lambda m: m.group("head") + "***" + m.group("tail"), dsn)


# ── Correlation ID ────────────────────────────────────────────────────────────
class RequestIdFilter(logging.Filter):
    """Injects `request_id` on every record so one request's lines can be grepped."""

    def filter(self, record):
        record.request_id = getattr(g, "request_id", "-") if has_request_context() else "-"
        return True


_FORMAT = "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s"
_TAG = "_vet_logging_handler"   # marks handlers we own, so init is idempotent


def _level(app) -> int:
    name = os.environ.get("LOG_LEVEL", "").upper()
    if name:
        return logging.getLevelName(name) if isinstance(logging.getLevelName(name), int) else logging.INFO
    return logging.DEBUG if app.debug else logging.INFO


def init_logging(app) -> None:
    """Configure logging for `app`. Safe to call more than once."""
    level = _level(app)
    root = logging.getLogger()
    root.setLevel(level)

    if not any(getattr(h, _TAG, False) for h in root.handlers):
        fmt = logging.Formatter(_FORMAT)
        id_filter = RequestIdFilter()

        handlers = [logging.StreamHandler()]
        file_error = None

        # Path derived from the app, not a drive letter — this project has moved disks before.
        log_dir = os.path.join(app.root_path, "logs")
        try:
            os.makedirs(log_dir, exist_ok=True)
            handlers.append(RotatingFileHandler(
                os.path.join(log_dir, "app.log"),
                maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8",
            ))
        except OSError as e:
            file_error = e   # read-only FS (some PaaS) — console only, don't kill the app

        for h in handlers:
            h.setLevel(level)
            h.setFormatter(fmt)
            h.addFilter(id_filter)
            setattr(h, _TAG, True)
            root.addHandler(h)

        if file_error is not None:
            logging.getLogger(__name__).warning(
                "File logging disabled (%s: %s) — console only",
                type(file_error).__name__, file_error,
            )

    # Werkzeug's own access log would duplicate ours line for line.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

    if app.extensions.get("vet_logging"):
        return          # request hooks already registered on this app
    app.extensions["vet_logging"] = True

    log = logging.getLogger("request")

    @app.before_request
    def _start_request():
        g.request_id = uuid.uuid4().hex[:8]
        g._req_started = time.perf_counter()

    @app.after_request
    def _log_request(response):
        started = g.pop("_req_started", None)
        ms = (time.perf_counter() - started) * 1000 if started else 0.0
        # Method + path + status + duration only. No query string (tokens),
        # no body (patient/financial data), no cookies, no Authorization header.
        # ponytail: request.path can still carry a record id (/crm/client/42).
        # Ceiling: the log shows which record was touched, never its contents.
        # Scrub to the url_rule pattern if even ids become too much.
        log.info("%s %s -> %s in %.1fms", request.method, request.path, response.status_code, ms)
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        return response

    _init_sentry(app)


def _init_sentry(app) -> None:
    """Optional error aggregation. No-op unless SENTRY_DSN is set and sentry-sdk installed."""
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        logging.getLogger(__name__).warning(
            "SENTRY_DSN is set but sentry-sdk is not installed — error reporting disabled "
            "(pip install sentry-sdk)"
        )
        return
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("FLASK_ENV", "development"),
        send_default_pii=False,   # never ship patient data to a third party
        traces_sample_rate=0.0,
    )
    logging.getLogger(__name__).info("Sentry error reporting enabled")
