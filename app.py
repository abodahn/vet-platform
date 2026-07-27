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

    # Secure cookie flags
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")

    # Wire database — PostgreSQL via DSN (no hardcoded credentials)
    import re as _re
    pg_dsn = app.config.get("POSTGRES_DSN", "")
    m = _re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', pg_dsn)
    if m:
        db.configure_postgres(
            user=m.group(1), password=m.group(2),
            host=m.group(3), port=int(m.group(4)), dbname=m.group(5)
        )
    else:
        logger.warning(
            "POSTGRES_DSN not set or invalid — falling back to SQLite. "
            "Set POSTGRES_DSN environment variable for production."
        )
    db.set_path(app.config["DATABASE_PATH"])
    db.init_db(
        admin_user=app.config.get("SEED_ADMIN_USER", "admin"),
        admin_pass=app.config.get("SEED_ADMIN_PASS", "1234"),
    )

    # Return every checked-out DB connection at the end of each request.
    # 247 route functions call get_db() with no try/finally; without this a
    # single unhandled exception leaked a pooled connection permanently and
    # ~20 of them exhausted the pool until restart.
    app.teardown_appcontext(db.close_context_connections)

    # Configure backup system
    backup_dir = os.path.join(os.path.dirname(app.config["DATABASE_PATH"]), "backups")
    bk.configure(db_path=app.config["DATABASE_PATH"], backup_dir=backup_dir)

    # ── Blueprints ──────────────────────────────────────────────────────────
    from blueprints.auth         import auth_bp
    from blueprints.launcher     import launcher_bp
    from blueprints.settings     import settings_bp
    from blueprints.crm          import crm_bp
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

        healthy = (checks["database"] == "ok"
                   and checks["scheduler"] != "stopped"
                   and checks["backup"] == "ok")

        body = {"status": "ok" if healthy else "degraded",
                "version": VERSION_INFO["full"]}

        # Operator detail behind the key clinic_env.py already provisions.
        key = (app.config.get("API_V1_KEY") or os.environ.get("API_V1_KEY", "")).strip()
        supplied = request.headers.get("Authorization", "").partition(" ")[2].strip()
        if key and supplied and hmac.compare_digest(supplied, key):
            body["clinic"] = app.config.get("CLINIC_ID", "")
            body["checks"] = checks
            body["last_backup_hours"] = backup.get("age_hours")
            body["commit"] = VERSION_INFO["commit"]
        return jsonify(body), 200 if healthy else 503

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

        # Daily backup at 02:00
        def _daily_backup():
            with app.app_context():
                result = bk.run_backup()
                if not result["success"]:
                    logger.error(f"Scheduled backup failed: {result.get('error')}")
                    db.notify_managers(
                        title="Backup Failed",
                        body=result.get("error", "Unknown error"),
                        icon="❌",
                        link="/system/monitor",
                        module="system"
                    )
                else:
                    logger.info(f"Scheduled backup OK: {result['filename']}")
        scheduler.add_job(_daily_backup, CronTrigger(hour=2, minute=0), id="daily_backup")

        # WhatsApp reminders at 09:00 daily
        def _daily_reminders():
            with app.app_context():
                try:
                    run_reminder_jobs()
                except Exception as e:
                    logger.error(f"Reminder job error: {e}")
        scheduler.add_job(_daily_reminders, CronTrigger(hour=9, minute=0), id="wa_reminders")

        # Rate limit cleanup every hour
        def _cleanup():
            sec.cleanup_rate_limits()
        scheduler.add_job(_cleanup, CronTrigger(minute=0), id="rl_cleanup")

        # Backup health at 09:05. The nightly job can only report a backup it
        # actually attempted — if the job itself stops firing, nothing complains.
        # This checks the archives on disk instead, so a silently dead scheduler
        # is still caught.
        def _backup_health():
            with app.app_context():
                try:
                    bk.check_and_notify()
                except Exception:
                    logger.exception("Backup health check failed")
        scheduler.add_job(_backup_health, CronTrigger(hour=9, minute=5),
                          id="backup_health")

        scheduler.start()
        # Exposed so /healthz can tell "scheduler dead" from "another worker
        # owns it" — without the handle those two look identical.
        app.config["_SCHEDULER"] = scheduler
        logger.info("APScheduler started in pid %s — backup@02:00, "
                    "reminders@09:00, backup health@09:05", os.getpid())
    except Exception as e:
        logger.warning(f"Scheduler not started: {e}")
