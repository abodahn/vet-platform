"""
Premium Animal Hospital — Platform App Factory
"""

import os
import logging
from flask import Flask, session, g, redirect, url_for, request, flash, render_template
from config import Config
import models.database as db
import models.security as sec
import models.backup as bk
from models.logging_setup import init_logging

logger = logging.getLogger(__name__)


def create_app(cfg=None) -> Flask:
    # Validate production config has all required env vars before booting
    import os as _os
    if _os.environ.get("FLASK_ENV", "development").lower() == "production":
        from config import ProductionConfig
        ProductionConfig.validate()   # raises RuntimeError if missing vars
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )
    app.config.from_object(cfg or Config)

    # Logging first — so the POSTGRES_DSN fallback warning below is captured
    init_logging(app)

    # ── The signing key must not be the one published in this repository ─────
    #
    # ProductionConfig.validate() above catches this, but ONLY when FLASK_ENV is
    # literally "production". The default is "development", so a deployment that
    # forgets to set that one variable booted silently on
    # "dev-only-key-CHANGE-IN-PRODUCTION-please" -- a key anybody with a copy of
    # this code knows. Session cookies are signed with it, so knowing it means
    # being able to mint a cookie that says you are the clinic owner. Nothing
    # warned; the app just started.
    #
    # Development keeps working and is told; anything else refuses to serve,
    # because a silent insecure boot is the failure mode that reaches a clinic.
    _key = app.config.get("SECRET_KEY") or ""
    _weak = (not _key) or ("CHANGE" in _key) or len(_key) < 32
    if _weak and not app.config.get("TESTING"):
        if _os.environ.get("FLASK_ENV", "development").lower() == "development":
            logger.warning(
                "SECRET_KEY is the shipped development key. Fine locally; this "
                "app will REFUSE to start with it outside development. Generate "
                'one with: python -c "import secrets; print(secrets.token_hex(64))"')
        else:
            raise RuntimeError(
                "PLATFORM_SECRET_KEY is unset, too short, or still the shipped "
                "development key. Session cookies are signed with it, so this "
                "would let anyone forge a login. Generate one with:\n"
                '  python -c "import secrets; print(secrets.token_hex(64))"')

    # Secure cookie flags
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

    # Wire database — PostgreSQL via DSN (no hardcoded credentials).
    #
    # urlparse, not a hand-rolled regex. The regex this replaces demanded
    # user:password@host:port/db with every part present and non-empty, so it
    # silently rejected DSNs PostgreSQL itself accepts:
    #
    #   postgresql://postgres:@host:5432/db   empty password  (a trust/local setup)
    #   postgresql://postgres@host:5432/db    no password at all
    #   postgresql://u:p@host/db              no port
    #   postgres://u:p@host:5432/db           the common scheme alias
    #   postgresql://u:p%40ss@host:5432/db    a percent-encoded @ in the password
    #
    # And rejection is not loud: the app falls back to SQLite with a warning in
    # a log nobody reads, so a clinic can believe it is running on PostgreSQL
    # while its records sit in a file that a redeploy erases. That is the whole
    # danger — the failure looks like success.
    from urllib.parse import unquote, urlparse
    pg_dsn = (app.config.get("POSTGRES_DSN", "") or "").strip()
    parsed = urlparse(pg_dsn) if pg_dsn else None
    if parsed and parsed.scheme in ("postgresql", "postgres") \
            and parsed.hostname and (parsed.path or "").strip("/"):
        db.configure_postgres(
            user=unquote(parsed.username or "postgres"),
            password=unquote(parsed.password or ""),
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/"),
        )
    elif pg_dsn:
        # Set but unusable is a configuration error, not an absent setting, and
        # the two deserve different words.
        logger.error(
            "POSTGRES_DSN is set but could not be parsed (%r) — falling back to "
            "SQLite. Expected postgresql://user:password@host:port/dbname",
            pg_dsn[:60])
    else:
        logger.warning(
            "POSTGRES_DSN not set — falling back to SQLite. "
            "Set POSTGRES_DSN environment variable for production."
        )
    db.set_path(app.config["DATABASE_PATH"])

    # Multi-tenancy. The registry is a separate file next to the default
    # database; until a clinic is actually provisioned into it, every request
    # resolves to no tenant and the app behaves exactly as a single-clinic
    # install — which is why this needed no change to any of the 376 routes.
    from models import tenancy
    tenancy.configure(os.path.join(
        os.path.dirname(app.config["DATABASE_PATH"]) or ".", "tenants.db"))

    db.init_db(
        admin_user=app.config.get("SEED_ADMIN_USER", "admin"),
        admin_pass=app.config.get("SEED_ADMIN_PASS", "1234"),
    )

    @app.errorhandler(tenancy.UnknownTenant)
    def _unknown_tenant(exc):
        # Explicitly NOT a fall-through to the default database: serving one
        # clinic's records under another clinic's subdomain is the single worst
        # thing a multi-tenant medical system can do.
        logger.warning("request for unregistered tenant %s", exc)
        return render_template(
            "error.html", code=404,
            msg="No clinic is registered at this address."), 404

    @app.errorhandler(tenancy.TenantSuspended)
    def _suspended_tenant(exc):
        return render_template(
            "error.html", code=403,
            msg=("This clinic's account is not active. "
                 "Please contact support.")), 403

    # Return every checked-out DB connection at the end of each request.
    # 247 route functions call get_db() with no try/finally; without this a
    # single unhandled exception leaked a pooled connection permanently and
    # ~20 of them exhausted the pool until restart.
    app.teardown_appcontext(db.close_context_connections)

    # `|money` filter + Decimal-safe JSON. PostgreSQL returns money columns as
    # Decimal and SQLite as float; without these a page renders 120.5 on one
    # engine and 120.50 on the other, and any endpoint returning an amount
    # becomes a 500 on the day PostgreSQL is switched on.
    from models import money
    money.init_app(app)

    # Payment gateways. Cash is always available and needs no configuration;
    # online gateways appear only once their keys are set, so a clinic with no
    # merchant account still takes money exactly as before.
    from models import payments
    payments.init()

    # Configure backup system
    backup_dir = os.path.join(os.path.dirname(app.config["DATABASE_PATH"]), "backups")
    bk.configure(db_path=app.config["DATABASE_PATH"], backup_dir=backup_dir)

    # ── Blueprints ──────────────────────────────────────────────────────────
    from blueprints.auth         import auth_bp
    from blueprints.launcher     import launcher_bp
    from blueprints.settings     import settings_bp
    from blueprints.crm          import crm_bp
    from blueprints.workflow     import workflow_bp
    from blueprints.appointments import appointments_bp
    from blueprints.inventory    import inventory_bp
    from blueprints.finance      import finance_bp
    from blueprints.hr           import hr_bp
    from blueprints.reports      import reports_bp
    from blueprints.whatsapp     import whatsapp_bp
    from blueprints.system       import system_bp
    from blueprints.ai_assistant import ai_bp
    from blueprints.clinical     import clinical_bp
    from blueprints.visits       import visits_bp
    from blueprints.grooming     import grooming_bp
    from blueprints.boarding     import boarding_bp
    from blueprints.doctor       import doctor_bp
    from blueprints.accounting   import accounting_bp
    from blueprints.procurement  import procurement_bp
    from blueprints.attendance   import attendance_bp
    from blueprints.catalog      import catalog_bp
    from blueprints.notifications import notifications_bp
    from blueprints.pharmacy     import pharmacy_bp
    from blueprints.uploads      import uploads_bp
    from blueprints.migration    import migration_bp
    from blueprints.petshop      import petshop_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(launcher_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(crm_bp)
    app.register_blueprint(workflow_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(finance_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(whatsapp_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(clinical_bp)
    app.register_blueprint(visits_bp)
    app.register_blueprint(grooming_bp)
    app.register_blueprint(boarding_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(procurement_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(pharmacy_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(migration_bp,  url_prefix="/migration")
    app.register_blueprint(petshop_bp,    url_prefix="/petshop")

    from blueprints.public_api import public_api_bp
    app.register_blueprint(public_api_bp)

    from blueprints.payroll import payroll_bp
    app.register_blueprint(payroll_bp)

    from blueprints.petsy import petsy_bp
    app.register_blueprint(petsy_bp)

    from blueprints.inpatient import inpatient_bp
    app.register_blueprint(inpatient_bp)

    from blueprints.telemedicine import telemedicine_bp
    app.register_blueprint(telemedicine_bp)

    from blueprints.imaging import imaging_bp
    app.register_blueprint(imaging_bp)

    # Clinical decision support — standalone reference page only. Deliberately
    # NOT wired into add_prescription or dispense as a blocking gate: its drug
    # data is marked DRAFT and unreviewed, and at the expected inventory
    # name-match rate an always-on checker would generate enough "unverified"
    # alerts to train staff past the ones that matter. Gate on the data file's
    # review_status before making it blocking.
    from blueprints.cds import cds_bp
    app.register_blueprint(cds_bp)

    # ── Upload directory ─────────────────────────────────────────────────────
    uploads_path = os.path.join(os.path.dirname(app.config["DATABASE_PATH"]), "uploads")
    os.makedirs(uploads_path, exist_ok=True)
    app.config["UPLOADS_PATH"] = uploads_path
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    # ── APScheduler — background jobs ────────────────────────────────────────
    _start_scheduler(app, backup_dir)

    # ── Security middleware ──────────────────────────────────────────────────
    @app.before_request
    def _security_checks():
        # Session timeout check
        if sec.check_session_timeout():
            session.clear()
            flash("Your session has expired. Please log in again.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        sec.touch_session()

        # CSRF validation
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.path.startswith("/api/public/"):
                pass  # Public API — no CSRF, authenticated by rate limit only
            elif request.path.startswith("/petsy/chat"):
                pass  # Petsy public widget endpoint — rate-limited, no CSRF
            elif not sec.validate_csrf():
                logger.warning(f"CSRF validation failed: {request.path} from {sec.get_real_ip(request)}")
                return render_template("error.html", code=403, msg="Invalid or missing security token. Please go back and try again."), 403

    def _payment_methods():
        """Never let a template-render failure take down a page."""
        try:
            from models import payments
            return payments.available()
        except Exception:
            logger.exception("could not list payment gateways")
            return []

    # ── Context processor ────────────────────────────────────────────────────
    @app.context_processor
    def _inject_globals():
        user = session.get("user") or {}
        theme = user.get("theme_preference") or session.get("theme") or "medical"
        lang  = user.get("language") or session.get("lang") or "en"
        clinic = db.get_clinic()
        # CSRF token for templates
        csrf_token = sec.generate_csrf_token()
        # Unread notification count
        unread_count = 0
        if user.get("id"):
            try:
                unread_count = db.count_unread_notifications(user["id"])
            except Exception:
                pass
        def t(en, ar=""):
            """Return Arabic text when lang=='ar', English otherwise."""
            return ar if (lang == "ar" and ar) else en

        return dict(
            app_title     = app.config.get("APP_TITLE", "Aleefy"),
            app_title_ar  = app.config.get("APP_TITLE_AR", "اليفي"),
            app_subtitle  = app.config.get("APP_SUBTITLE", "Dr. Hatem El Khateeb"),
            app_tagline   = app.config.get("APP_TAGLINE", "Happy Pets, Healthy Lives"),
            legacy_url    = app.config.get("LEGACY_APP_URL", "http://localhost:5000"),
            current_user  = user,
            current_role  = user.get("role", ""),
            current_theme = theme,
            current_lang  = lang,
            clinic        = clinic,
            csrf_token    = csrf_token,
            unread_count  = unread_count,
            # Payment methods, from the registry rather than hardcoded in each
            # template. This is what makes "add a gateway without
            # redevelopment" true: register it and it appears in the UI. An
            # online gateway stays absent until its keys are configured, so a
            # clinic is never offered a method that cannot complete.
            payment_methods = _payment_methods(),
            t             = t,
        )

    # ── Error handlers ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def _404(e):
        return render_template("error.html", code=404, msg="Page not found"), 404

    @app.errorhandler(403)
    def _403(e):
        return render_template("error.html", code=403, msg="Access denied"), 403

    @app.errorhandler(413)
    def _413(e):
        # Werkzeug rejects the body before any view runs, so the import wizard
        # cannot catch this itself. Say what to do, not just what went wrong —
        # a clinic hitting this is mid-migration with its whole history in one
        # spreadsheet and needs to know splitting it is the answer.
        limit_mb = int(app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) / (1024 * 1024))
        return render_template(
            "error.html", code=413,
            msg=(f"That file is larger than {limit_mb} MB. Split it into smaller "
                 f"files — for example one sheet per year, or owners and pets "
                 f"separately — and import them one after another."),
        ), 413

    # ── PWA: installable on a phone, tablet or desktop ───────────────────────
    # Both routes sit at the ROOT deliberately. A service worker's scope is the
    # directory it is served from, so /static/sw.js could only ever control
    # /static/* — it would never see a page navigation. Served from /sw.js it
    # controls the whole app.
    @app.route("/manifest.webmanifest")
    def _manifest():
        from flask import jsonify
        # Generated rather than a static file so the installed icon carries the
        # CLINIC's name, not the vendor's. A clinic that has set its own
        # branding should not find "Aleefy" on its staff's home screens.
        clinic = db.get_clinic()
        name = (clinic.get("name") or "").strip() or app.config.get("APP_TITLE", "Aleefy")
        resp = jsonify({
            "name": name,
            "short_name": name[:12],
            "description": clinic.get("tagline") or "Veterinary clinic management",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "any",
            "background_color": "#F7F5F1",   # --bg
            "theme_color": "#0B7A6B",        # --c-primary
            "dir": "auto",                   # the UI ships in Arabic and English
            "icons": [
                {"src": "/static/images/icon-192.png", "sizes": "192x192",
                 "type": "image/png", "purpose": "any"},
                {"src": "/static/images/icon-512.png", "sizes": "512x512",
                 "type": "image/png", "purpose": "any"},
                {"src": "/static/images/icon-maskable-512.png", "sizes": "512x512",
                 "type": "image/png", "purpose": "maskable"},
            ],
            "shortcuts": [
                {"name": "Today's appointments", "url": "/appointments/"},
                {"name": "New visit", "url": "/visits/new"},
                {"name": "Reception queue", "url": "/clinical/waiting-room"},
            ],
        })
        resp.headers["Content-Type"] = "application/manifest+json"
        # The clinic row is cached 5 minutes; let the manifest go stale no longer.
        resp.headers["Cache-Control"] = "public, max-age=300"
        return resp

    @app.route("/sw.js")
    def _service_worker():
        from flask import send_from_directory
        resp = send_from_directory(app.static_folder, "sw.js",
                                   mimetype="application/javascript")
        # A cached service worker cannot ship its own replacement. Browsers
        # already bypass the HTTP cache for the SW script, but proxies do not.
        resp.headers["Cache-Control"] = "no-cache"
        return resp

    # ── Health ───────────────────────────────────────────────────────────────
    # The public body is a status word and the version — nothing an
    # unauthenticated caller cannot already read from the X-App-Version header
    # on the login page. Deliberately NOT public: FLASK_ENV, file paths, row
    # counts, DB latency. api_v1 stays unregistered; registering it to get a
    # health route would expose eleven other endpoints.
    @app.route("/healthz")
    def _healthz():
        import hmac
        from flask import jsonify
        from config import VERSION_INFO

        checks = {}
        try:
            conn = db.get_db()
            conn.execute("SELECT 1").fetchone()
            conn.close()
            checks["database"] = "ok"
        except Exception as exc:
            logger.warning("healthz: database probe failed: %s", exc)
            checks["database"] = "unavailable"

        sched = app.config.get("_SCHEDULER")
        if sched is None:
            # No handle: either another gunicorn worker owns it (fine) or it died.
            checks["scheduler"] = ("elsewhere"
                                   if app.config.get("_SCHEDULER_LOCK") is None
                                   else "stopped")
        else:
            checks["scheduler"] = "running" if sched.running else "stopped"

        backup = bk.health()
        checks["backup"] = "ok" if backup.get("ok") else "stale"

        # The HTTP status answers ONE question: can this instance serve
        # traffic? Only an unreachable database makes that false.
        #
        # Backup staleness and scheduler state are reported in the body but do
        # NOT fail the probe. Container health checks and upgrade.sh use
        # `curl -fsS`, which treats any non-2xx as failure — so returning 503
        # for a stale backup would restart healthy containers and, worse, make
        # upgrade.sh roll back every upgrade *after* it had already applied the
        # Alembic revision, leaving a new schema running old code. A fresh
        # install legitimately has no backup until the first 02:00 run.
        # Staleness already reaches the operator via notify_managers() and the
        # backup page; it must not also masquerade as a liveness failure.
        serving = checks["database"] == "ok"
        degraded = [k for k, v in checks.items()
                    if (k == "backup" and v != "ok")
                    or (k == "scheduler" and v == "stopped")]

        body = {"status": "ok" if serving and not degraded
                          else "degraded" if serving else "down",
                "version": VERSION_INFO["full"]}
        if degraded:
            body["degraded"] = degraded

        # Operator detail behind the key clinic_env.py already provisions.
        key = (app.config.get("API_V1_KEY") or os.environ.get("API_V1_KEY", "")).strip()
        supplied = request.headers.get("Authorization", "").partition(" ")[2].strip()
        if key and supplied and hmac.compare_digest(supplied, key):
            body["clinic"] = app.config.get("CLINIC_ID", "")
            body["checks"] = checks
            body["last_backup_hours"] = backup.get("age_hours")
            body["commit"] = VERSION_INFO["commit"]
        return jsonify(body), 200 if serving else 503

    @app.after_request
    def _security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://meet.jit.si; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "img-src 'self' data: https://cdn.jsdelivr.net blob:; "
            "connect-src 'self' http://localhost:3001 https://localhost:3001 ws://localhost:3001; "
            "frame-src 'self' https://meet.jit.si; "
            "frame-ancestors 'self';"
        )
        # HSTS — only set over HTTPS (Koyeb/Render/Cloudflare terminate TLS)
        if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        # Permissions policy — disable unused browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        # Remove server fingerprint
        response.headers["Server"] = "PAH-Platform"
        return response

    # ── Global 500 handler — never leak stack traces in production ───────────
    @app.errorhandler(500)
    def _500(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        # Tell somebody. A log table nobody opens is not a support channel: the
        # clinic hits an error, works around it, and mentions it days later as
        # "the system was being weird", by which point there is nothing left to
        # diagnose. Rate-limited per (path, exception type) so one broken page
        # reloaded twenty times is one notification.
        try:
            from models import error_alerts
            error_alerts.report(
                request.path, e,
                user=(session.get("user") or {}).get("username", ""))
        except Exception:
            logger.exception("error alert failed")
        return render_template("error.html", code=500,
                               msg="An internal error occurred. Please try again."), 500

    return app


def _acquire_scheduler_lock(backup_dir: str):
    """Return an open lock file if THIS process should own the scheduler.

    create_app() runs in every gunicorn worker, and workers default to
    cpu*2+1. Without this, 02:00 fires N concurrent backups and 09:00 sends
    every WhatsApp reminder N times — a clinic's clients get the same message
    five times and blame the clinic.

    An OS-level exclusive lock is used rather than a PID file because it is
    released automatically when the process dies, so a crashed worker cannot
    leave the scheduler permanently disabled.
    """
    lock_path = os.path.join(backup_dir, ".scheduler.lock")
    try:
        fh = open(lock_path, "w")
    except OSError as exc:
        logger.warning("Cannot open scheduler lock (%s) — running scheduler "
                       "in this process without exclusion", exc)
        return None
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        return None          # another worker already owns it — expected
    fh.write(str(os.getpid()))
    fh.flush()
    return fh


def _start_scheduler(app, backup_dir: str) -> None:
    """Start APScheduler with daily backup and WhatsApp reminder jobs.

    Only one process wins the lock; the rest return immediately.
    """
    lock = _acquire_scheduler_lock(backup_dir)
    if lock is None:
        logger.info("Scheduler owned by another worker — not starting here")
        return
    # Held for the process lifetime; releasing it would let a second worker
    # start a duplicate scheduler.
    app.config["_SCHEDULER_LOCK"] = lock

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from blueprints.whatsapp.scheduler import run_reminder_jobs

        scheduler = BackgroundScheduler(daemon=True)

        # ── Every nightly job runs ONCE PER CLINIC ───────────────────────────
        #
        # They used to run once, against whichever database the process started
        # with. In a multi-tenant deployment that meant clinic number two
        # onwards was never backed up, never had a WhatsApp reminder sent, and
        # never had its logs swept — while the backup job logged success,
        # because from where it stood it had succeeded. A backup that reports
        # success for nineteen databases it never opened is worse than no
        # backup: it stops anyone looking.
        #
        # One clinic failing must never stop the rest. A raise inside the loop
        # would leave every clinic after it in the list unbacked up, and the
        # order is stable, so the same clinics would lose out every night.
        from models import tenancy

        def _for_every_clinic(job_name, fn):
            done, failed = 0, []
            for slug, row in tenancy.each_clinic():
                label = slug or "default"
                try:
                    fn(slug, row)
                    done += 1
                except Exception:
                    failed.append(label)
                    logger.exception("%s failed for clinic %s", job_name, label)
            if failed:
                logger.error("%s: %d/%d clinics failed — %s",
                             job_name, len(failed), done + len(failed),
                             ", ".join(failed))
            else:
                logger.info("%s: %d clinic(s) OK", job_name, done)
            return done, failed

        # Daily backup at 02:00
        def _daily_backup():
            with app.app_context():
                def one(slug, row):
                    with bk.for_clinic(slug, row.get("db_path", ""),
                                       row.get("pg_dsn", "")):
                        result = bk.run_backup()
                    if not result["success"]:
                        # Named, because "Backup Failed" across twenty clinics
                        # does not tell anyone which database to go and look at.
                        db.notify_managers(
                            title=f"Backup Failed — {slug or 'clinic'}",
                            body=result.get("error", "Unknown error"),
                            icon="❌", link="/system/monitor", module="system")
                        raise RuntimeError(result.get("error") or "backup failed")
                    logger.info("backup OK for %s: %s", slug or "default",
                                result["filename"])
                _for_every_clinic("daily_backup", one)
        scheduler.add_job(_daily_backup, CronTrigger(hour=2, minute=0), id="daily_backup")

        # WhatsApp reminders at 09:00 daily
        def _daily_reminders():
            with app.app_context():
                _for_every_clinic("wa_reminders",
                                  lambda slug, row: run_reminder_jobs())
        scheduler.add_job(_daily_reminders, CronTrigger(hour=9, minute=0), id="wa_reminders")

        # Rate limit cleanup every hour. Per clinic too: the counters live in
        # each clinic's own database, so sweeping only one leaves the others
        # growing forever and their lockouts never expiring.
        def _cleanup():
            with app.app_context():
                _for_every_clinic("rl_cleanup",
                                  lambda slug, row: sec.cleanup_rate_limits())
        scheduler.add_job(_cleanup, CronTrigger(minute=0), id="rl_cleanup")

        # Backup health at 09:05. The nightly job can only report a backup it
        # actually attempted — if the job itself stops firing, nothing complains.
        # This checks the archives on disk instead, so a silently dead scheduler
        # is still caught. Per clinic, because one clinic's healthy archive says
        # nothing about the other nineteen.
        def _backup_health():
            with app.app_context():
                def one(slug, row):
                    with bk.for_clinic(slug, row.get("db_path", ""),
                                       row.get("pg_dsn", "")):
                        bk.check_and_notify()
                _for_every_clinic("backup_health", one)
        scheduler.add_job(_backup_health, CronTrigger(hour=9, minute=5),
                          id="backup_health")

        # Close yesterday's forgotten check-outs, 00:20, before anyone runs a
        # report on the day. hours_worked is only ever written at check-out, so
        # an employee who works a full day and forgets to clock out is paid for
        # ZERO hours — payroll reads exactly that column. Every row this touches
        # is stamped recorded_by='system' and says so in its notes, so a manager
        # can tell reconstructed hours from observed ones.
        def _close_attendance():
            with app.app_context():
                from blueprints.attendance.routes import close_forgotten_checkouts

                def one(slug, row):
                    conn = db.get_db()
                    try:
                        n = close_forgotten_checkouts(conn)
                    finally:
                        conn.close()
                    if n:
                        logger.info("attendance (%s): auto-closed %d forgotten "
                                    "check-out(s)", slug or "default", n)
                _for_every_clinic("attendance_close", one)
        scheduler.add_job(_close_attendance, CronTrigger(hour=0, minute=20),
                          id="attendance_close")

        # LOG_FILE_RETENTION_DAYS between restarts. init_logging() sweeps at
        # startup, which is enough for a clinic PC that reboots — but a VPS
        # instance can stay up for months and would keep expired logs forever.
        def _log_retention():
            with app.app_context():
                from models.logging_db import cleanup_old_logs

                def one(slug, row):
                    n = cleanup_old_logs()
                    if n:
                        logger.info("Log retention (%s): deleted %d expired file(s)",
                                    slug or "default", n)
                _for_every_clinic("log_retention", one)
        scheduler.add_job(_log_retention, CronTrigger(hour=3, minute=30),
                          id="log_retention")

        scheduler.start()
        # Exposed so /healthz can tell "scheduler dead" from "another worker
        # owns it" — without the handle those two look identical.
        app.config["_SCHEDULER"] = scheduler
        logger.info("APScheduler started in pid %s — backup@02:00, "
                    "reminders@09:00, backup health@09:05", os.getpid())
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")
