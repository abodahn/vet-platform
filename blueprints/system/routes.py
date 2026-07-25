"""
System Monitor Blueprint
"""
import os
import sys
import glob
import platform as _platform
from datetime import date, datetime, timedelta
from flask import render_template, request, redirect, url_for, session, flash, current_app, jsonify
from . import system_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db
import models.backup as bk
from models.sync import get_sync_status_summary, resolve_conflict


def _db_path():
    return current_app.config.get("DATABASE_PATH", "")


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
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        error_count_24h = conn.execute(
            "SELECT COUNT(*) FROM backend_logs WHERE level IN ('ERROR','CRITICAL') AND timestamp >= ?",
            (cutoff,)
        ).fetchone()[0]
    except Exception:
        pass

    # ── Active devices ────────────────────────────────────────────
    active_devices = 0
    try:
        cutoff_dev = (datetime.utcnow() - timedelta(hours=1)).isoformat()
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
                age_days = (datetime.utcnow() - mtime).days
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

    latest_backup = bk.get_latest_backup()

    return render_template(
        "system/monitor.html",
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


@system_bp.route("/audit")
@role_required("super_admin", "clinic_owner", "support_admin", "auditor")
def audit_log():
    conn = db.get_db()
    # Filters
    f_user   = request.args.get("user", "")
    f_action = request.args.get("action", "")
    f_module = request.args.get("module", "")
    f_from   = request.args.get("date_from", "")
    f_to     = request.args.get("date_to", "")
    q = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if f_user:   q += " AND username=?";          params.append(f_user)
    if f_action: q += " AND action LIKE ?";       params.append(f"%{f_action}%")
    if f_module: q += " AND module=?";            params.append(f_module)
    if f_from:   q += " AND timestamp >= ?";      params.append(f_from + " 00:00:00")
    if f_to:     q += " AND timestamp <= ?";      params.append(f_to + " 23:59:59")
    q += " ORDER BY timestamp DESC LIMIT 200"
    logs = [dict(r) for r in conn.execute(q, params).fetchall()]
    # For filter dropdowns
    users   = [dict(r)["username"] for r in conn.execute("SELECT DISTINCT username FROM audit_log ORDER BY username").fetchall()]
    modules = [dict(r)["module"] for r in conn.execute("SELECT DISTINCT module FROM audit_log ORDER BY module").fetchall()]
    conn.close()
    return render_template(
        "system/audit_log.html",
        logs=logs,
        users=users,
        modules=modules,
        f_user=f_user,
        f_action=f_action,
        f_module=f_module,
        f_from=f_from,
        f_to=f_to,
        active="audit",
    )


@system_bp.route("/settings", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner")
def settings():
    if request.method == "POST":
        f = request.form
        try:
            conn = db.get_db()
            conn.execute(
                "UPDATE clinic SET name=?, name_ar=?, doctor_name=?, phone=?, email=?, address=?, website=?, license_number=?, tax_number=?, currency=?, timezone=?, updated_at=datetime('now') WHERE id=1",
                (f.get("name",""), f.get("name_ar",""), f.get("doctor_name",""),
                 f.get("phone",""), f.get("email",""), f.get("address",""),
                 f.get("website",""), f.get("license_number",""), f.get("tax_number",""),
                 f.get("currency","EGP"), f.get("timezone","Africa/Cairo"))
            )
            conn.commit()
            # Appearance settings
            username = session["user"]["username"]
            for key, category in [("default_theme","appearance"),("default_language","appearance")]:
                val = f.get(key,"")
                if val:
                    conn.execute(
                        "INSERT OR REPLACE INTO settings(key,value,category,updated_at,updated_by) VALUES(?,?,?,datetime('now'),?)",
                        (key, val, category, username)
                    )
            conn.commit()
            conn.close()
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


@system_bp.route("/backup")
@role_required("super_admin", "clinic_owner", "support_admin")
def backup():
    backups = bk.list_backups()
    latest  = bk.get_latest_backup()
    return render_template(
        "system/backup.html",
        backups=backups,
        latest=latest,
        active="backup",
    )


@system_bp.route("/backup/run", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def backup_run():
    result = bk.run_backup()
    if result.get("success"):
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="manual_backup",
            module="system",
            entity_type="backup",
            details=f"Manual backup: {result.get('filename')} ({result.get('size_kb')} KB)",
        )
        flash(f"Backup completed: {result['filename']} ({result['size_kb']} KB)", "success")
    else:
        flash(f"Backup failed: {result.get('error', 'Unknown error')}", "error")
    return redirect(url_for("system.backup"))


@system_bp.route("/backup/<filename>/restore", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def backup_restore(filename):
    """Restore the database from a named backup file."""
    result = bk.restore_backup(filename)

    if result.get("skipped"):
        flash(result["message"], "warning")
    elif result.get("success"):
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="backup_restore",
            module="system",
            entity_type="backup",
            details=f"Restored from: {filename}",
        )
        flash(result["message"], "success")
    else:
        flash(result["message"], "danger")

    return redirect(url_for("system.backup"))


@system_bp.route("/diagnostics")
@role_required("super_admin", "clinic_owner", "support_admin")
def diagnostics():
    checks = []
    db_path = _db_path()
    # 1. DB writable
    try:
        with open(db_path, "a"):
            pass
        checks.append({"name": "Database File Writable", "status": "Pass", "details": db_path})
    except Exception as e:
        checks.append({"name": "Database File Writable", "status": "Fail", "details": str(e)})
    # 2. DB integrity
    try:
        conn = db.get_db()
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        checks.append({"name": "Database Integrity (PRAGMA)", "status": "Pass" if result == "ok" else "Fail", "details": result})
        # 3. Table count
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
        flash(f"Conflict resolved. Kept: {keep} version.", "success")
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
    try:
        db.update_role(role_id, display_name, display_ar, permissions, color)
        db.log_audit(username=session["user"]["username"], role=session["user"]["role"],
                     action="edit_role", module="system", entity_type="role", entity_id=str(role_id),
                     details=f"Updated role id={role_id}")
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
    try:
        db.assign_user_role(user_id, role)
        db.log_audit(username=session["user"]["username"], role=session["user"]["role"],
                     action="assign_role", module="system", entity_type="user", entity_id=str(user_id),
                     details=f"Assigned role '{role}' to user id={user_id}")
        flash("Role assigned successfully.", "success")
    except Exception as e:
        flash(f"Error assigning role: {e}", "danger")
    return redirect(url_for("system.roles_list"))
