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

from config import CLINIC_ID, VERSION_INFO

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

    # Place 1 of 3 the version is visible: the first line of every log file.
    # "Which build is this clinic on" is answerable from the log they email you.
    logging.getLogger(__name__).info(
        "Starting version %s (commit %s, built %s) — clinic=%s env=%s level=%s",
        VERSION_INFO["version"], VERSION_INFO["commit"] or "n/a",
        VERSION_INFO["built"], CLINIC_ID,
        os.environ.get("FLASK_ENV", "development"), logging.getLevelName(level),
    )

    _purge_expired_json_logs()

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
        # Place 2 of 3: on every response, so `curl -sI https://clinic/auth/login`
        # answers "which build" without an account, a login or an SSH session.
        # A header rather than a new endpoint — nothing to register, nothing to
        # authorise, and it cannot be more exposed than the login page already is.
        response.headers["X-App-Version"] = _VERSION_HEADER
        return response

    _init_sentry(app)


# ── Log retention ─────────────────────────────────────────────────────────────
def _purge_expired_json_logs() -> None:
    """Apply LOG_FILE_RETENTION_DAYS to the JSON logs in logs/backend|frontend.

    models/logging_db.py has shipped cleanup_old_logs() since it was written and
    nothing ever called it, so /system/monitor's "expires in N days" column was
    counting down to nothing and the files grew forever. Startup is the cheapest
    place that is guaranteed to run.

    # ponytail: startup sweep only. Ceiling: an instance that stays up longer
    # than the retention window keeps expired files until the next restart.
    # Upgrade path is a daily scheduler job — see the app.py snippet in the
    # observability notes.
    """
    log = logging.getLogger(__name__)
    try:
        from models.logging_db import cleanup_old_logs
        deleted = cleanup_old_logs()
    except Exception as exc:   # import chain reaches models.database; never fatal
        log.warning("Log retention sweep skipped (%s: %s)", type(exc).__name__, exc)
        return
    if deleted:
        log.info("Log retention: deleted %d expired JSON log file(s)", deleted)


# ── Sentry (optional) ─────────────────────────────────────────────────────────
# The no-payload-on-disk policy at the top of this module applies with more
# force to a third-party service. Any key whose NAME matches this has its VALUE
# replaced before the event leaves the process.
_SCRUB_KEY_RE = re.compile(
    # clinical
    r"pet|animal|patient|owner|client|customer|visit|diagnos|treatment|prescri|"
    r"medicat|drug|dose|vaccin|lab_|specimen|result|symptom|note|chart|weight|"
    # financial
    r"invoice|receipt|payment|price|cost|amount|subtotal|total|discount|tax|"
    r"salary|payroll|wage|balance|credit|iban|card|"
    # identifying
    r"name|phone|mobile|email|address|national|passport|"
    # secrets
    r"password|passwd|secret|token|api_key|apikey|dsn|cookie|authorization",
    re.I,
)
_SCRUBBED = "[scrubbed]"

# Contexts the SDK builds itself (runtime version, OS, device). Left alone so
# the event stays diagnosable — otherwise contexts.runtime.name reads "[scrubbed]".
_SDK_CONTEXTS = {"runtime", "os", "device", "trace", "app", "browser", "profile"}

_VERSION_HEADER = VERSION_INFO["full"]
_RELEASE = f"vet-platform@{VERSION_INFO['full']}"


def _redact(value, _depth: int = 0):
    """Blank the value of any key matching _SCRUB_KEY_RE, recursively.

    Sentry events are JSON-serialisable, so this cannot meet a cycle; the depth
    cap is only there so a pathological nesting cannot burn the stack.
    """
    if _depth > 8:
        return value
    if isinstance(value, dict):
        return {
            k: (_SCRUBBED if _SCRUB_KEY_RE.search(str(k)) else _redact(v, _depth + 1))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact(v, _depth + 1) for v in value]
    return value


def _scrub_event(event, hint=None):
    """Sentry `before_send`. Strips payload, tags the event so it is attributable.

    Without the tags this is unusable at 20 single-tenant deployments: an
    untagged event says something broke, not whose clinic it broke in.
    """
    if not isinstance(event, dict):
        return event

    # Request sections exist only to carry payload — the query string holds
    # tokens, the body holds the patient record, the headers hold the session.
    req = event.get("request")
    if isinstance(req, dict):
        for key in ("data", "cookies", "headers", "env", "query_string"):
            req.pop(key, None)
        url = req.get("url")
        if isinstance(url, str):
            req["url"] = url.split("?", 1)[0]

    # Traceback locals: one frame of add_invoice() holds the whole invoice, one
    # frame of save_visit() holds the whole record. include_local_variables=False
    # already stops these being collected — this is the second lock, because a
    # patient record posted to a third party cannot be un-posted.
    for group in (event.get("exception"), event.get("threads")):
        for entry in (group or {}).get("values") or []:
            for frame in ((entry.get("stacktrace") or {}).get("frames") or []):
                if isinstance(frame, dict):
                    frame.pop("vars", None)

    for section in ("extra", "user"):
        if isinstance(event.get(section), dict):
            event[section] = _redact(event[section])
    ctx = event.get("contexts")
    if isinstance(ctx, dict):
        event["contexts"] = {
            k: (v if k in _SDK_CONTEXTS else _redact(v)) for k, v in ctx.items()
        }

    tags = event.get("tags")
    if not isinstance(tags, dict):
        tags = event["tags"] = {}
    tags.setdefault("clinic", CLINIC_ID)
    tags.setdefault("version", VERSION_INFO["version"])
    tags.setdefault("commit", VERSION_INFO["commit"] or "n/a")
    # Bridges the Sentry event to the clinic's own log file: grep app.log for
    # this id and the surrounding request lines are right there.
    if has_request_context():
        tags.setdefault("request_id", getattr(g, "request_id", "-"))
    return event


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
        release=_RELEASE,               # regressions become attributable to a build
        send_default_pii=False,         # never ship patient data to a third party
        include_local_variables=False,  # a traceback frame holds whole records
        max_breadcrumbs=0,              # breadcrumbs replay log lines verbatim
        before_send=_scrub_event,
        # Errors: keep all of them. 20 clinics do not generate the volume that
        # makes sampling worthwhile, and a dropped event is a support call you
        # cannot answer. Turn down only if the free-tier quota actually bites.
        sample_rate=float(os.environ.get("SENTRY_SAMPLE_RATE", "1.0")),
        # Performance tracing off: it burns the same quota as errors and adds
        # URL and SQL spans that would each need scrubbing, for no support value.
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
    )
    sentry_sdk.set_tag("clinic", CLINIC_ID)
    logging.getLogger(__name__).info(
        "Sentry enabled — release %s, clinic %s", _RELEASE, CLINIC_ID
    )
