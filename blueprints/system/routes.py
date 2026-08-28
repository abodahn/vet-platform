"""
System Monitor Blueprint
"""
import logging
import os
import sys
import glob
import platform as _platform
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (render_template, request, redirect, url_for, session, flash,
                   current_app, jsonify, send_file, abort)
from . import system_bp
from blueprints.auth.routes import (login_required, role_required,
                                    clear_permission_cache, has_permission,
                                    _role_permissions)
from blueprints.settings.routes import LogoError, encode_logo
import models.database as db
import models.audit as audit
import models.backup as bk
from models.sync import get_sync_status_summary, resolve_conflict
from models import clock

logger = logging.getLogger(__name__)


def _db_path():
    return current_app.config.get("DATABASE_PATH", "")


# A patient photo is 16 MB; a clinic database is not. The app-wide
# MAX_CONTENT_LENGTH is raised for the backup-upload route only.
_UPLOAD_LIMIT = 2 * 1024 * 1024 * 1024  # 2 GB


@system_bp.before_app_request
def _backup_maintenance_gate():
    """Hold traffic off the database while a restore is swapping it.

    Registered on this blueprint but applied app-wide via before_app_request,
    so app.py needs no change. How quiescence is achieved, and what it does
    not achieve:

      · The marker is a FILE, so every gunicorn worker process sees it — an
        in-process flag would gate one worker of N.
      · It is checked when a request STARTS. A request already inside a view
        keeps its open connection and is NOT interrupted. On SQLite that is
        safe anyway: the restore goes through SQLite's backup API, which takes
        the write lock and makes stragglers wait or fail, never corrupt.
      · Between the marker being written and the last in-flight request
        finishing there is a window of at most one request. Restoring during
        clinic hours is still a bad idea; restoring while closed is fine.
      · The marker self-expires after MAINTENANCE_MAX_MINUTES so a crashed
        restore cannot lock a clinic out of its own records forever.
    """
    if request.path.startswith(("/static/", "/auth/")):
        return None
    if request.path == "/system/backup/upload" and request.method == "POST":
        # Must happen before app.py's CSRF check touches request.form, which
        # is what triggers the 16 MB limit.
        request.max_content_length = _UPLOAD_LIMIT
    if request.path.startswith("/system/backup"):
        return None
    info = bk.maintenance_active()
    if not info:
        return None
    return render_template(
        "error.html", code=503,
        msg=(f"Maintenance in progress: {info.get('reason', 'database restore')}. "
             f"The system will be back in a few minutes.")), 503


@system_bp.route("/")
@login_required
def index():
    return redirect(url_for("system.monitor"))


@system_bp.route("/monitor")
@role_required("super_admin", "clinic_owner", "support_admin")
def monitor():
    db_path = _db_path()

    # ── DB size ──────────────────────────────────────────────────
    db_size_bytes = 0
    try:
        db_size_bytes = os.path.getsize(db_path)
    except Exception:
        pass
    db_size_kb = round(db_size_bytes / 1024, 1)
    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)

    # ── Row counts ───────────────────────────────────────────────
    tables = ["owners", "pets", "appointments", "visits", "invoices", "items",
              "users", "reminders", "whatsapp_log", "audit_log", "batches", "payments"]
    row_counts = {}
    conn = db.get_db()
    for t in tables:
        try:
            row_counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            row_counts[t] = 0

    # ── Recent backend logs (from new production table) ───────────
    recent_logs = []
    try:
        rows = conn.execute(
            "SELECT * FROM backend_logs ORDER BY timestamp DESC LIMIT 25"
        ).fetchall()
        recent_logs = [dict(r) for r in rows]
    except Exception:
        # Fallback to old app_logs table if backend_logs not ready
        try:
            recent_logs = [dict(r) for r in conn.execute(
                "SELECT * FROM app_logs ORDER BY timestamp DESC LIMIT 25"
            ).fetchall()]
        except Exception:
            pass

    # ── Error count last 24h ──────────────────────────────────────
    error_count_24h = 0
    try:
        cutoff = (clock.utcnow() - timedelta(hours=24)).isoformat()
        error_count_24h = conn.execute(
            "SELECT COUNT(*) FROM backend_logs WHERE level IN ('ERROR','CRITICAL') AND timestamp >= ?",
            (cutoff,)
        ).fetchone()[0]
    except Exception:
        pass

    # ── Active devices ────────────────────────────────────────────
    active_devices = 0
    try:
        cutoff_dev = (clock.utcnow() - timedelta(hours=1)).isoformat()
        active_devices = conn.execute(
            "SELECT COUNT(*) FROM devices WHERE last_online_at >= ? AND is_active=1",
            (cutoff_dev,)
        ).fetchone()[0]
    except Exception:
        pass

    total_devices = 0
    try:
        total_devices = conn.execute(
            "SELECT COUNT(*) FROM devices WHERE is_active=1"
        ).fetchone()[0]
    except Exception:
        pass

    conn.close()

    # ── Sync stats ────────────────────────────────────────────────
    sync_stats = {"pending": 0, "synced": 0, "failed": 0, "conflicts": 0}
    try:
        sync_stats = get_sync_status_summary()
    except Exception:
        pass

    # ── Log files ─────────────────────────────────────────────────
    log_dir = os.path.join(os.path.dirname(db_path), "logs", "backend")
    log_files_info = []
    log_total_mb = 0.0
    retention_days = int(os.environ.get("LOG_FILE_RETENTION_DAYS", 7))
    try:
        if os.path.isdir(log_dir):
            files = sorted(glob.glob(os.path.join(log_dir, "*.log")), reverse=True)
            for f in files[:10]:
                size_kb = round(os.path.getsize(f) / 1024, 1)
                log_total_mb += size_kb / 1024
                mtime = datetime.fromtimestamp(os.path.getmtime(f))
                age_days = (clock.utcnow() - mtime).days
                log_files_info.append({
                    "name": os.path.basename(f),
                    "size_kb": size_kb,
                    "age_days": age_days,
                    "expires_in": max(0, retention_days - age_days),
                })
    except Exception:
        pass
    log_total_mb = round(log_total_mb, 2)

    # ── System info ───────────────────────────────────────────────
    legacy_url     = current_app.config.get("LEGACY_APP_URL", "http://localhost:5000")
    legacy_enabled = current_app.config.get("LEGACY_APP_ENABLED", False)
    sys_info = {
        "python_version":  sys.version.split()[0],
        "platform":        _platform.platform(),
        "flask_version":   _get_flask_version(),
        "db_size_kb":      db_size_kb,
        "db_size_mb":      db_size_mb,
        "db_path":         db_path,
        "app_version":     os.environ.get("APP_VERSION", "1.0.0"),
        "build_number":    os.environ.get("BUILD_NUMBER", "production_final_v1"),
        "release_date":    os.environ.get("RELEASE_DATE", "2026-05-24"),
    }

    # Second place a stale backup gets noticed — the monitor page is opened far
    # more often than the backup page, and this is the whole point of T3.
    # This clinic's backup, not the deployment's — the monitor page is opened
    # far more often than the backup page, so it is where a stale backup is
    # actually noticed, and it has to be reporting the right database.
    with bk.for_current_clinic():
        backup_health = bk.check_and_notify()
    latest_backup = backup_health.get("latest")

    return render_template(
        "system/monitor.html",
        backup_health=backup_health,
        sys_info=sys_info,
        row_counts=row_counts,
        recent_logs=recent_logs,
        legacy_url=legacy_url,
        legacy_enabled=legacy_enabled,
        latest_backup=latest_backup,
        sync_stats=sync_stats,
        error_count_24h=error_count_24h,
        active_devices=active_devices,
        total_devices=total_devices,
        log_files_info=log_files_info,
        log_total_mb=log_total_mb,
        retention_days=retention_days,
        active="monitor",
    )


def _get_flask_version():
    try:
        import flask
        return flask.__version__
    except Exception:
        return "unknown"


AUDIT_PAGE_SIZE = 50

# The Audit Log is the one screen in this blueprint that is not system
# administration, and `auditor` is the read-only role that exists to read it.
#
# @role_required named auditor here and the page refused it anyway, because the
# module gate inside login_required keys EVERY /system route on the single
# `system` permission. auditor holds `audit` and must not hold `system`, so the
# route advertised an access it always denied, with no way to grant it from the
# Roles screen. The gate was wrong, not the role list: `audit` is a real key in
# db.ALL_PERMISSIONS with its own checkbox, and this is the only route it
# governs — so ask that question instead. The session check is repeated from
# login_required rather than reused, because reusing login_required is what
# drags the wrong module gate back in with it.
#
# The roles below are a FALLBACK for a role with no permission data at all —
# same rule as auth.routes.permission_required, and for the same reason: an
# upgrade must not lock a clinic out of its own audit trail. Where grant data
# exists it wins, so unticking Audit Log on the Roles screen closes this page.
#
# ponytail: route-local, because exactly one route is governed by `audit`. The
# platform fix is a per-view permission key honoured by _permission_denied()
# in blueprints/auth/routes.py, which would retire this and known limit #5.
_AUDIT_FALLBACK_ROLES = ("super_admin", "clinic_owner", "support_admin", "auditor")


def _audit_access(f):
    @wraps(f)
    def gate(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        role = session["user"].get("role", "")
        granted = _role_permissions(role)
        allowed = (role in _AUDIT_FALLBACK_ROLES if granted is None
                   else has_permission("audit", role))
        if not allowed:
            flash("You don't have permission to access this page.", "danger")
            return redirect(url_for("launcher.index"))
        return f(*args, **kwargs)
    return gate


@system_bp.route("/audit")
@_audit_access
def audit_log():
    """Filtered, paginated view of the live `audit_log` table.

    Never SELECTs the whole table: it grows without bound and a clinic that has
    been running for a year has hundreds of thousands of rows. One page of
    AUDIT_PAGE_SIZE plus a COUNT for the pager, nothing more.
    """
    f_user   = request.args.get("user", "").strip()
    f_action = request.args.get("action", "").strip()
    f_module = request.args.get("module", "").strip()
    f_entity = request.args.get("entity_type", "").strip()
    f_eid    = request.args.get("entity_id", "").strip()
    f_from   = request.args.get("date_from", "").strip()
    f_to     = request.args.get("date_to", "").strip()

    where, params = ["1=1"], []
    if f_user:   where.append("username=?");     params.append(f_user)
    if f_action: where.append("action LIKE ?");  params.append(f"%{f_action}%")
    if f_module: where.append("module=?");       params.append(f_module)
    if f_entity: where.append("entity_type=?");  params.append(f_entity)
    if f_eid:    where.append("entity_id=?");    params.append(f_eid)
    if f_from:   where.append("timestamp >= ?"); params.append(f_from + " 00:00:00")
    if f_to:     where.append("timestamp <= ?"); params.append(f_to + " 23:59:59")
    clause = " AND ".join(where)

    page = request.args.get("page", type=int) or 1
    if page < 1:
        page = 1
    offset = (page - 1) * AUDIT_PAGE_SIZE

    conn = db.get_db()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM audit_log WHERE {clause}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM audit_log WHERE {clause} "
            f"ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
            params + [AUDIT_PAGE_SIZE, offset],
        ).fetchall()

        # Filter dropdowns. DISTINCT over the whole table is the one unbounded
        # scan left here; it is cheap next to the row fetch it replaces and the
        # cardinality is tiny (staff count, module count).
        users = [r[0] for r in conn.execute(
            "SELECT DISTINCT username FROM audit_log WHERE username <> '' ORDER BY username"
        ).fetchall()]
        modules = [r[0] for r in conn.execute(
            "SELECT DISTINCT module FROM audit_log WHERE module <> '' ORDER BY module"
        ).fetchall()]
        entities = [r[0] for r in conn.execute(
            "SELECT DISTINCT entity_type FROM audit_log WHERE entity_type <> '' ORDER BY entity_type"
        ).fetchall()]
    finally:
        conn.close()

    # Decode the field-level diff where there is one. Legacy rows carry a plain
    # English sentence in `details`; parse_details() returns None for those and
    # the template falls back to rendering the text.
    logs = []
    for r in rows:
        d = dict(r)
        d["changes"] = audit.parse_details(d.get("details"))
        logs.append(d)

    pages = max(1, (total + AUDIT_PAGE_SIZE - 1) // AUDIT_PAGE_SIZE)
    return render_template(
        "system/audit_log.html",
        logs=logs,
        users=users,
        modules=modules,
        entities=entities,
        f_user=f_user,
        f_action=f_action,
        f_module=f_module,
        f_entity=f_entity,
        f_eid=f_eid,
        f_from=f_from,
        f_to=f_to,
        page=page,
        pages=pages,
        total=total,
        page_size=AUDIT_PAGE_SIZE,
        has_filters=any([f_user, f_action, f_module, f_entity, f_eid, f_from, f_to]),
        active="audit",
    )


@system_bp.route("/settings", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner")
def settings():
    if request.method == "POST":
        f = request.form
        # The logo is resolved first so a rejected image reports its own reason
        # ("not an image", "too large") instead of a generic save failure, and
        # so a bad upload never half-writes the text fields.
        logo_set, logo_val = "", ()
        try:
            if f.get("remove_logo"):
                logo_set, logo_val = ", logo_data=?", (None,)
            else:
                up = request.files.get("logo")
                if up and up.filename:
                    logo_set, logo_val = ", logo_data=?", (encode_logo(up.read()),)

            # Instapay QR. Same all-or-nothing handling as the logo: a bad
            # upload must not half-write the text fields around it.
            from blueprints.settings.routes import QR_MAX_PX
            if f.get("remove_instapay_qr"):
                logo_set += ", instapay_qr=?"
                logo_val += (None,)
            else:
                qr = request.files.get("instapay_qr")
                if qr and qr.filename:
                    logo_set += ", instapay_qr=?"
                    logo_val += (encode_logo(qr.read(), max_px=QR_MAX_PX),)
        except LogoError as e:
            flash(str(e), "danger")
            return redirect(url_for("system.settings"))

        try:
            conn = db.get_db()
            conn.execute(
                "UPDATE clinic SET name=?, name_ar=?, tagline=?, doctor_name=?, phone=?, "
                "email=?, address=?, address_ar=?, website=?, license_number=?, tax_number=?, "
                "currency=?, timezone=?, instapay_handle=?, instapay_link=?, "
                "updated_at=datetime('now')" + logo_set + " WHERE id=1",
                (f.get("name",""), f.get("name_ar",""), f.get("tagline",""),
                 f.get("doctor_name",""),
                 f.get("phone",""), f.get("email",""), f.get("address",""),
                 f.get("address_ar",""),
                 f.get("website",""), f.get("license_number",""), f.get("tax_number",""),
                 f.get("currency","EGP"), f.get("timezone","Africa/Cairo"),
                 f.get("instapay_handle","").strip(),
                 f.get("instapay_link","").strip()) + logo_val
            )
            conn.commit()
            # Appearance settings
            username = session["user"]["username"]
            for key, category in [("default_theme","appearance"),("default_language","appearance")]:
                val = f.get(key,"")
                if val:
                    conn.execute(
                        "INSERT INTO settings(key,value,category,updated_at,updated_by) "
                        "VALUES(?,?,?,datetime('now'),?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                        "category=excluded.category, updated_at=excluded.updated_at, "
                        "updated_by=excluded.updated_by",
                        (key, val, category, username)
                    )
            conn.commit()
            conn.close()
            # get_clinic() caches for 5 minutes and every page, invoice and
            # certificate reads through it. Without this the clinic saves its own
            # name and watches nothing change, then saves again.
            db.cache_invalidate("clinic_row")
            db.log_audit(
                username=session["user"]["username"],
                role=session["user"]["role"],
                action="update",
                module="system",
                entity_type="clinic",
                details="Updated clinic settings",
                ip=request.remote_addr,
            )
            flash("Settings saved successfully.", "success")
        except Exception as e:
            flash(f"Error saving settings: {e}", "danger")
        return redirect(url_for("system.settings"))
    clinic = db.get_clinic()
    conn = db.get_db()
    settings_rows = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings").fetchall()}
    conn.close()
    return render_template(
        "system/settings.html",
        clinic=clinic,
        settings_rows=settings_rows,
        active="settings",
    )


# ─────────────────────────────────────────────
# LICENCE
# ─────────────────────────────────────────────

@system_bp.route("/license", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner")
def license_page():
    """Show the machine's challenge and accept an activation code.

    The clinic reads the challenge to their supplier over the phone and types
    back the code they are given. Nothing here ever blocks access to the
    system - see models/licensing.py for why that is deliberate.
    """
    from models import licensing

    if request.method == "POST":
        # Rate limited because the code is only eight digits. That is ample
        # against a person typing, and nothing at all against a script: 10^8
        # tries with no limit is a weekend's work. Reuses the same limiter the
        # login form uses, so a lockout is visible in the same place.
        from models import security as sec
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
        ip = ip.split(",")[0].strip()
        locked, wait = sec.is_rate_limited(ip, "license-activation")
        if locked:
            flash("Too many attempts. Try again in %d seconds." % wait, "danger")
            return redirect(url_for("system.license_page"))

        ok, msg = licensing.activate(
            request.form.get("code", ""),
            (session.get("user") or {}).get("username", "system"))
        if not ok:
            sec.record_failed_login(ip, "license-activation")
        flash(msg, "success" if ok else "danger")
        return redirect(url_for("system.license_page"))

    return render_template("system/license.html",
                           lic=licensing.status(),
                           active="system")


def _archive_or_abort(filename):
    """Resolve a URL-supplied backup name, or refuse outright.

    CALL THIS INSIDE `with bk.for_current_clinic():` — it resolves against the
    module's current backup directory, so unscoped it looks in the deployment's
    directory while the page listed the clinic's. Archive names are timestamps
    (platform_backup_YYYYMMDD_HHMMSS.dump) and every clinic backs up at 02:00,
    so the names collide across directories: an unscoped restore could open a
    DIFFERENT clinic's dump of the same minute and write it over this one.

    Refusal is a 4xx, never a flash-and-redirect: a redirect reads as "wrong
    file" when the caller is a person and as "keep probing" when it is not.
    400 = the name could not have come from us (traversal, wrong extension);
    404 = a legitimate name for a file that is not here.
    """
    path = bk.resolve_archive(filename)
    if not path:
        abort(400)
    if not os.path.exists(path):
        abort(404)
    return path


def _audit_backup(action: str, details: str) -> None:
    user = session.get("user") or {}
    db.log_audit(
        username=user.get("username", "?"),
        role=user.get("role", "?"),
        action=action,
        module="system",
        entity_type="backup",
        details=details,
    )


@system_bp.route("/backup")
@role_required("super_admin", "clinic_owner", "support_admin")
def backup():
    # Page load is the one thing guaranteed to still happen when the scheduler
    # has quietly died, so this is where a stale backup gets noticed.
    #
    # Scoped to THIS clinic. Unscoped, a clinic opening its own backup page was
    # shown the deployment's archives instead of its own — so the list was
    # empty or ancient while its real nightly backup sat in <backup_dir>/<slug>
    # where the nightly job puts it.
    with bk.for_current_clinic():
        health = bk.check_and_notify()
        backups = bk.list_backups()
        maintenance = bk.maintenance_active()
    return render_template(
        "system/backup.html",
        backups=backups,
        latest=health.get("latest"),
        health=health,
        maintenance=maintenance,
        active="backup",
    )


@system_bp.route("/backup/run", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def backup_run():
    with bk.for_current_clinic():
        result = bk.run_backup()
    if result.get("success"):
        _audit_backup("manual_backup",
                      f"Manual backup: {result.get('filename')} ({result.get('size_kb')} KB)")
        flash(f"Backup completed: {result['filename']} ({result['size_kb']} KB)", "success")
        for off in result.get("offsite") or []:
            if not off.get("ok"):
                flash(f"Off-site copy to {off['label']} FAILED: {off.get('error')}. "
                      f"The local backup is fine, but there is no second copy.", "danger")
    else:
        flash(f"Backup failed: {result.get('error', 'Unknown error')}", "error")
    return redirect(url_for("system.backup"))


@system_bp.route("/backup/<filename>/verify", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def backup_verify(filename):
    """Check a backup is readable — without restoring it."""
    with bk.for_current_clinic():
        _archive_or_abort(filename)
        result = bk.verify_backup(filename)
    if result.get("success"):
        flash(f"{filename} is readable and complete.", "success")
    else:
        flash(f"{filename} is NOT usable: {result.get('integrity')}", "danger")
    return redirect(url_for("system.backup"))


@system_bp.route("/backup/<filename>/download")
@role_required("super_admin", "clinic_owner")
def backup_download(filename):
    """Download a backup, e.g. onto a USB stick."""
    with bk.for_current_clinic():
        path = _archive_or_abort(filename)
    _audit_backup("backup_download", f"Downloaded: {os.path.basename(path)}")
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path))


@system_bp.route("/backup/upload", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def backup_upload():
    """Accept a backup file from a USB stick. Verified before it is kept."""
    fileobj = request.files.get("archive")
    if not fileobj or not fileobj.filename:
        flash("Choose a backup file first.", "warning")
        return redirect(url_for("system.backup"))
    with bk.for_current_clinic():
        result = bk.accept_upload(fileobj, fileobj.filename)
    if result["success"]:
        _audit_backup("backup_upload", f"Uploaded: {result['filename']}")
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")
    return redirect(url_for("system.backup"))


@system_bp.route("/backup/<filename>/restore", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def backup_restore(filename):
    """Restore the database from a named backup file.

    Typing the filename is the confirmation: a modal a tired owner can click
    through at 22:00 is not one.
    """
    with bk.for_current_clinic():
        _archive_or_abort(filename)
        if (request.form.get("confirm_filename") or "").strip() != filename:
            flash("Restore cancelled — the filename you typed did not match.", "warning")
            return redirect(url_for("system.backup"))
        result = bk.restore_backup(filename)

    if result.get("skipped"):
        flash(result["message"], "warning")
    elif result.get("success"):
        _audit_backup("backup_restore",
                      f"Restored from {filename}; previous data saved as "
                      f"{result.get('snapshot')}")
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")

    return redirect(url_for("system.backup"))


@system_bp.route("/backup/maintenance/off", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def backup_maintenance_off():
    """Escape hatch: clear a maintenance marker left by a crashed restore."""
    bk.maintenance_off()
    _audit_backup("maintenance_cleared", "Maintenance mode cleared manually")
    flash("Maintenance mode cleared. The system is serving again.", "success")
    return redirect(url_for("system.backup"))


@system_bp.route("/diagnostics")
@role_required("super_admin", "clinic_owner", "support_admin")
def diagnostics():
    checks = []
    db_path = _db_path()
    # Every check below was written against SQLite: a database FILE, PRAGMA, and
    # sqlite_master. None of the three exists on PostgreSQL, so this whole page
    # -- the one an owner opens to ask "is my system healthy?" -- raised a syntax
    # error on the production engine. Each check now has a PostgreSQL equivalent
    # rather than being skipped, because a health page that quietly checks
    # nothing is worse than one that fails loudly.
    on_pg = db.is_postgres()

    # 1. Storage reachable
    if on_pg:
        try:
            conn = db.get_db()
            server = conn.execute("SELECT version()").fetchone()[0]
            conn.close()
            checks.append({"name": "Database Server Reachable", "status": "Pass",
                           "details": str(server)[:80]})
        except Exception as e:
            checks.append({"name": "Database Server Reachable", "status": "Fail", "details": str(e)})
    else:
        try:
            with open(db_path, "a"):
                pass
            checks.append({"name": "Database File Writable", "status": "Pass", "details": db_path})
        except Exception as e:
            checks.append({"name": "Database File Writable", "status": "Fail", "details": str(e)})
    # 2. DB integrity
    try:
        conn = db.get_db()
        if on_pg:
            # PostgreSQL has no integrity_check. A committed read that touches
            # the catalogue is the equivalent smoke test.
            conn.execute("SELECT 1").fetchone()
            checks.append({"name": "Database Integrity", "status": "Pass",
                           "details": "server responded to a read"})
        else:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            checks.append({"name": "Database Integrity (PRAGMA)", "status": "Pass" if result == "ok" else "Fail", "details": result})
        # 3. Table count
        if on_pg:
            table_count = conn.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE'").fetchone()[0]
        else:
            table_count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        checks.append({"name": "Database Tables", "status": "Pass" if table_count >= 30 else "Warning", "details": f"{table_count} tables found (expected ≥30)"})
        # 4. Admin user exists
        admin_count = conn.execute("SELECT COUNT(*) FROM users WHERE role='super_admin' AND is_active=1").fetchone()[0]
        checks.append({"name": "Super Admin User Exists", "status": "Pass" if admin_count > 0 else "Fail", "details": f"{admin_count} active super_admin user(s)"})
        # 5. Clinic record
        clinic_count = conn.execute("SELECT COUNT(*) FROM clinic").fetchone()[0]
        checks.append({"name": "Clinic Record", "status": "Pass" if clinic_count > 0 else "Fail", "details": f"{clinic_count} clinic record(s)"})
        conn.close()
    except Exception as e:
        checks.append({"name": "Database Connection", "status": "Fail", "details": str(e)})
    # 6. Legacy app directory
    legacy_url = current_app.config.get("LEGACY_APP_URL", "http://localhost:5000")
    legacy_dir = current_app.config.get("LEGACY_APP_DIR", "")
    if legacy_dir:
        exists = os.path.isdir(legacy_dir)
        checks.append({"name": "Legacy App Directory", "status": "Pass" if exists else "Warning", "details": legacy_dir if exists else f"Not found: {legacy_dir}"})
    else:
        checks.append({"name": "Legacy App Directory", "status": "Warning", "details": "LEGACY_APP_DIR not configured"})
    # 7. Python version
    py_ver = sys.version.split()[0]
    checks.append({"name": "Python Version", "status": "Pass", "details": py_ver})
    # 8. Static folder
    static_path = current_app.static_folder
    checks.append({"name": "Static Folder", "status": "Pass" if os.path.isdir(static_path) else "Fail", "details": static_path})
    return render_template(
        "system/diagnostics.html",
        checks=checks,
        legacy_url=legacy_url,
        active="system",
    )


# ─────────────────────────────────────────────
# SYNC DASHBOARD
# ─────────────────────────────────────────────

@system_bp.route("/sync")
@role_required("super_admin", "clinic_owner", "support_admin")
def sync_dashboard():
    conn = db.get_db()

    # Filters
    f_status   = request.args.get("status", "")
    f_device   = request.args.get("device", "")
    f_entity   = request.args.get("entity", "")

    # ── Sync queue ────────────────────────────────────────────────
    queue_items = []
    try:
        q = "SELECT * FROM sync_queue WHERE 1=1"
        params = []
        if f_status: q += " AND status=?";      params.append(f_status)
        if f_device: q += " AND device_id=?";   params.append(f_device)
        if f_entity: q += " AND entity_name=?"; params.append(f_entity)
        q += " ORDER BY created_at DESC LIMIT 100"
        queue_items = [dict(r) for r in conn.execute(q, params).fetchall()]
    except Exception:
        pass

    # ── Conflicts ─────────────────────────────────────────────────
    conflicts = []
    try:
        conflicts = [dict(r) for r in conn.execute(
            "SELECT * FROM sync_conflicts WHERE resolution_status='PENDING' ORDER BY created_at DESC LIMIT 50"
        ).fetchall()]
    except Exception:
        pass

    # ── Devices ───────────────────────────────────────────────────
    devices = []
    try:
        devices = [dict(r) for r in conn.execute(
            "SELECT * FROM devices ORDER BY last_online_at DESC LIMIT 50"
        ).fetchall()]
    except Exception:
        pass

    # ── Filter options ────────────────────────────────────────────
    device_ids = []
    entity_names = []
    try:
        device_ids  = [r[0] for r in conn.execute("SELECT DISTINCT device_id FROM sync_queue").fetchall()]
        entity_names = [r[0] for r in conn.execute("SELECT DISTINCT entity_name FROM sync_queue").fetchall()]
    except Exception:
        pass

    # ── Status summary ────────────────────────────────────────────
    sync_stats = {"pending": 0, "synced": 0, "failed": 0, "conflicts": 0}
    try:
        sync_stats = get_sync_status_summary()
    except Exception:
        pass

    conn.close()
    return render_template(
        "system/sync.html",
        queue_items=queue_items,
        conflicts=conflicts,
        devices=devices,
        sync_stats=sync_stats,
        device_ids=device_ids,
        entity_names=entity_names,
        f_status=f_status,
        f_device=f_device,
        f_entity=f_entity,
        active="sync",
    )


@system_bp.route("/sync/conflicts/<conflict_id>/resolve", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def sync_resolve_conflict(conflict_id):
    keep = request.form.get("keep", "server")
    try:
        resolve_conflict(
            conflict_id=conflict_id,
            resolved_by=session["user"]["id"],
            keep=keep,
        )
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="resolve_conflict",
            module="system",
            entity_type="sync_conflict",
            entity_id=conflict_id,
            details=f"Resolved sync conflict — kept: {keep}",
        )
        # Not "Kept: local version." — nothing pushes the device's copy back
        # over the server record, and saying otherwise is how a clinic loses
        # data believing it was saved. Say what actually happened.
        if str(keep).strip().lower() == "local":
            flash("Conflict closed, marked KEPT LOCAL. The server record is "
                  "unchanged; the device's version is stored on the conflict "
                  "for you to copy across by hand.", "warning")
        else:
            flash("Conflict resolved — the server version is kept.", "success")
    except Exception as e:
        flash(f"Error resolving conflict: {e}", "danger")
    return redirect(url_for("system.sync_dashboard"))


# ─────────────────────────────────────────────
# ROLES & PERMISSIONS
# ─────────────────────────────────────────────

_SYSTEM_ROLE_PERMS = {
    "super_admin":     ["patients","appointments","visits","pharmacy","invoicing","inventory","procurement","reports","whatsapp","catalog","grooming","boarding","hr","attendance","accounting","ai","system","backup","audit","settings"],
    "clinic_owner":    ["patients","appointments","visits","pharmacy","invoicing","inventory","procurement","reports","whatsapp","catalog","grooming","boarding","hr","attendance","accounting","ai","system","backup","audit","settings"],
    "branch_manager":  ["patients","appointments","visits","pharmacy","invoicing","inventory","procurement","reports","whatsapp","catalog","grooming","boarding","hr","attendance","accounting","ai"],
    "doctor":          ["patients","appointments","visits","pharmacy","reports","whatsapp","ai"],
    "nurse":           ["patients","appointments","visits","reports"],
    "reception":       ["patients","appointments","invoicing","whatsapp"],
    "pharmacist":      ["pharmacy","inventory","procurement"],
    "groomer":         ["patients","appointments","grooming"],
    "hr":              ["hr","attendance","reports"],
    "support_admin":   ["system","backup","audit","settings","reports"],
    "staff":           ["patients","appointments"],
}

_SYSTEM_ROLE_COLORS = {
    "super_admin":    "#7c3aed",
    "clinic_owner":   "#0b7a6b",
    "branch_manager": "#1d4ed8",
    "doctor":         "#0891b2",
    "nurse":          "#059669",
    "reception":      "#d97706",
    "pharmacist":     "#7c3aed",
    "groomer":        "#db2777",
    "hr":             "#64748b",
    "support_admin":  "#dc2626",
    "staff":          "#94a3b8",
}

@system_bp.route("/roles")
@role_required("super_admin", "clinic_owner", "support_admin")
def roles_list():
    roles = db.list_roles()
    # Only load user counts — NOT full user rows (users loaded lazily via /roles/users)
    conn = db.get_db()
    count_rows = conn.execute(
        "SELECT role, COUNT(*) as cnt FROM users GROUP BY role"
    ).fetchall()
    conn.close()
    user_counts = {r["role"]: r["cnt"] for r in count_rows}
    return render_template(
        "system/roles.html",
        roles=roles,
        user_counts=user_counts,
        all_permissions=db.ALL_PERMISSIONS,
        system_role_perms=_SYSTEM_ROLE_PERMS,
        system_role_colors=_SYSTEM_ROLE_COLORS,
        active="roles",
    )


@system_bp.route("/roles/users")
@role_required("super_admin", "clinic_owner", "support_admin")
def roles_users_api():
    """JSON endpoint — called lazily when Staff Access tab is opened."""
    conn = db.get_db()
    rows = [dict(r) for r in conn.execute(
        "SELECT id, username, full_name, role, is_active FROM users ORDER BY full_name LIMIT 300"
    ).fetchall()]
    conn.close()
    return jsonify(rows)


@system_bp.route("/roles/create", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def role_create():
    f = request.form
    name         = f.get("name", "").strip()
    display_name = f.get("display_name", "").strip()
    display_ar   = f.get("display_name_ar", "").strip()
    color        = f.get("color", "#1a3a6b").strip()
    permissions  = f.getlist("permissions")
    if not name or not display_name:
        flash("Role name and display name are required.", "danger")
        return redirect(url_for("system.roles_list"))
    try:
        db.create_role(name, display_name, display_ar, permissions, color)
        clear_permission_cache()
        db.log_audit(username=session["user"]["username"], role=session["user"]["role"],
                     action="create_role", module="system", entity_type="role", details=f"Created role: {name}")
        flash(f"Role '{display_name}' created successfully.", "success")
    except Exception as e:
        flash(f"Error creating role: {e}", "danger")
    return redirect(url_for("system.roles_list"))


@system_bp.route("/roles/<int:role_id>/edit", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def role_edit(role_id):
    f = request.form
    display_name = f.get("display_name", "").strip()
    display_ar   = f.get("display_name_ar", "").strip()
    color        = f.get("color", "#1a3a6b").strip()
    permissions  = f.getlist("permissions")
    if not display_name:
        flash("Display name is required.", "danger")
        return redirect(url_for("system.roles_list"))
    # A role with NO permissions cannot be saved.
    #
    # '[]' is stored by roles that were never configured, and the permission
    # loader treats it as "no data — fall back to the built-in role", because
    # every role shipped that way and treating it as "deny all" would lock a
    # live clinic out on the first restart after an upgrade.
    #
    # The consequence was that unticking every box WIDENED the role: a nurse
    # emptied of permissions fell back to the built-in list and gained Finance,
    # Accounting and Inventory, while the screen said "Role updated
    # successfully". Refusing to save the empty case is what removes the
    # ambiguity — the loader can keep its safe fallback, and nobody can create
    # the state that made it wrong.
    if not [p for p in permissions if (p or "").strip()]:
        flash("A role must grant at least one module. To stop this role being "
              "used at all, move its staff to another role and delete it.",
              "danger")
        return redirect(url_for("system.roles_list"))
    try:
        # WORKED EXAMPLE of field-level auditing (models/audit.py).
        #
        # Editing a role silently rewrites who can see medical records and who
        # can touch money, and until now it recorded only "Updated role id=7".
        # This records the actual permission list before and after.
        #
        # The old db.log_audit() call is gone rather than kept alongside: two
        # rows per edit would double the table and give an auditor two entries
        # to reconcile for one action. This one is strictly more informative.
        with audit.audit_row("roles", role_id, module="system", action="edit_role"):
            db.update_role(role_id, display_name, display_ar, permissions, color)
        clear_permission_cache()
        flash("Role updated successfully.", "success")
    except Exception as e:
        flash(f"Error updating role: {e}", "danger")
    return redirect(url_for("system.roles_list"))


@system_bp.route("/roles/<int:role_id>/delete", methods=["POST"])
@role_required("super_admin")
def role_delete(role_id):
    try:
        role = db.get_role(role_id)
        db.delete_role(role_id)
        clear_permission_cache()
        db.log_audit(username=session["user"]["username"], role=session["user"]["role"],
                     action="delete_role", module="system", entity_type="role", entity_id=str(role_id),
                     details=f"Deleted role: {role.get('name') if role else role_id}")
        flash("Role deleted.", "success")
    except Exception as e:
        flash(f"Error deleting role: {e}", "danger")
    return redirect(url_for("system.roles_list"))


@system_bp.route("/roles/assign", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def role_assign():
    user_id = request.form.get("user_id", type=int)
    role    = request.form.get("role", "").strip()
    if not user_id or not role:
        flash("User and role are required.", "danger")
        return redirect(url_for("system.roles_list"))
    # The role has to EXIST. A hardcoded dropdown offered "staff", which is not
    # a role anywhere in this system — assigning it left the user on a name
    # that resolved to nothing. That used to fall open to every module; it now
    # denies, which locks the person out instead. Neither is what the
    # administrator meant, so refuse at the point of assignment.
    known = set(db.DEFAULT_ROLE_PERMISSIONS)
    conn = db.get_db()
    try:
        known.update(r[0] for r in conn.execute("SELECT name FROM roles").fetchall())
    except Exception:
        pass
    finally:
        conn.close()
    if role not in known:
        flash("There is no role called %r. Pick one that exists, or create it "
              "first." % role, "danger")
        return redirect(url_for("system.roles_list"))
    # The same guard the staff form uses: this route writes users.role too, and
    # a rule enforced on one of two writers is not enforced.
    from blueprints.auth.routes import guard_role_change, RoleChangeRefused
    conn = db.get_db()
    try:
        guard_role_change(conn, user_id, role, 1)
    except RoleChangeRefused as e:
        conn.close()
        flash(str(e), "danger")
        return redirect(url_for("system.roles_list"))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    try:
        db.assign_user_role(user_id, role)
        db.log_audit(username=session["user"]["username"], role=session["user"]["role"],
                     action="assign_role", module="system", entity_type="user", entity_id=str(user_id),
                     details=f"Assigned role '{role}' to user id={user_id}")
        flash("Role assigned successfully.", "success")
    except Exception as e:
        flash(f"Error assigning role: {e}", "danger")
    return redirect(url_for("system.roles_list"))


# ─────────────────────────────────────────────────────────────────────────────
# TAKE YOUR DATA WITH YOU
#
# Every screen with a table has an Excel button, and the nightly backup writes a
# database dump. Neither is what a clinic actually needs the day it wants to
# leave, or the day it wants to prove to itself that its records are its own:
# ONE file, containing EVERYTHING, in a format any spreadsheet opens without
# this software and without us.
#
# The Data & Continuity Guarantee promises exactly that in writing. This is the
# code that makes the promise true. A guarantee the software cannot honour is
# worse than no guarantee.
# ─────────────────────────────────────────────────────────────────────────────

# Tables holding operational junk rather than the clinic's records. Excluded so
# the export is the clinic's data, not our logs -- and so it stays a size a
# receptionist can email.
_EXPORT_SKIP = {
    "app_logs", "backend_logs", "frontend_logs", "audit_logs", "sync_queue",
    "sync_conflicts", "rate_hits", "user_sessions", "ai_conversations",
    "petsy_usage", "login_attempts", "sqlite_sequence",
}


def _export_tables(conn):
    """Every table in this clinic's database, minus the operational noise."""
    if db.is_postgres():
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND table_type='BASE TABLE' "
            "ORDER BY table_name").fetchall()
    else:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows if r[0] not in _EXPORT_SKIP
            and not str(r[0]).startswith("sqlite_")]


@system_bp.route("/export/all")
@role_required("super_admin", "clinic_owner")
def export_everything():
    """The whole database as a ZIP of CSVs. Opens in Excel, needs nothing of ours."""
    import csv
    import io as _io
    import zipfile

    conn = db.get_db()
    try:
        tables = _export_tables(conn)
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            written = []
            for table in tables:
                try:
                    cur = conn.execute(f"SELECT * FROM {table}")
                    rows = cur.fetchall()
                    cols = [d[0] for d in cur.description] if cur.description else []
                except Exception:
                    # One unreadable table must not cost the clinic the other 78.
                    db.rollback_quietly(conn)
                    logger.exception("export: skipped table %s", table)
                    continue
                if not cols:
                    continue
                s = _io.StringIO()
                w = csv.writer(s)
                w.writerow(cols)
                for r in rows:
                    w.writerow([r[c] for c in cols])
                # utf-8-sig: without the BOM, Excel on a Windows machine in
                # Egypt opens Arabic names as mojibake, and the clinic concludes
                # its data is corrupt.
                zf.writestr(f"{table}.csv", s.getvalue().encode("utf-8-sig"))
                written.append(f"{table} ({len(rows)})")

            zf.writestr("README.txt",
                        ("Aleefy — full data export\n"
                         "=========================\n\n"
                         "One CSV per table. Open any of them in Excel, Google "
                         "Sheets, or LibreOffice.\nThese files need no software "
                         "from us to read.\n\n"
                         "ملف CSV لكل جدول. تقدر تفتح أي واحد منهم في إكسل.\n"
                         "الملفات دي مش محتاجة أي برنامج مننا عشان تقراها.\n\n"
                         f"Exported: {datetime.now().isoformat(timespec='seconds')}\n"
                         f"Tables: {len(written)}\n\n" + "\n".join(written)
                         ).encode("utf-8-sig"))
    finally:
        conn.close()

    buf.seek(0)
    _audit_backup("data_export", f"Full data export ({len(tables)} tables)")
    return send_file(
        buf, mimetype="application/zip", as_attachment=True,
        download_name=f"aleefy-data-{date.today().isoformat()}.zip")
