"""
System Monitor Blueprint
"""
import os
import sys
import platform as _platform
from datetime import date
from flask import render_template, request, redirect, url_for, session, flash, current_app, jsonify
from . import system_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db
import models.backup as bk


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
    db_size_bytes = 0
    try:
        db_size_bytes = os.path.getsize(db_path)
    except Exception:
        pass
    db_size_kb = round(db_size_bytes / 1024, 1)
    db_size_mb = round(db_size_bytes / (1024 * 1024), 2)
    # Row counts
    tables = ["owners", "pets", "appointments", "visits", "invoices", "items",
              "users", "reminders", "whatsapp_log", "audit_log", "batches", "payments"]
    row_counts = {}
    conn = db.get_db()
    for t in tables:
        try:
            row_counts[t] = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        except Exception:
            row_counts[t] = 0
    # Recent app logs
    app_logs = [dict(r) for r in conn.execute(
        "SELECT * FROM app_logs ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()]
    conn.close()
    legacy_url = current_app.config.get("LEGACY_APP_URL", "http://localhost:5000")
    sys_info = {
        "python_version": sys.version.split()[0],
        "platform":       _platform.platform(),
        "flask_version":  _get_flask_version(),
        "db_size_kb":     db_size_kb,
        "db_size_mb":     db_size_mb,
        "db_path":        db_path,
    }
    latest_backup = bk.get_latest_backup()
    return render_template(
        "system/monitor.html",
        sys_info=sys_info,
        row_counts=row_counts,
        app_logs=app_logs,
        legacy_url=legacy_url,
        latest_backup=latest_backup,
        active="system",
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
# ROLES & PERMISSIONS
# ─────────────────────────────────────────────

@system_bp.route("/roles")
@role_required("super_admin", "clinic_owner", "support_admin")
def roles_list():
    roles = db.list_roles()
    users = db.list_users()
    return render_template(
        "system/roles.html",
        roles=roles,
        users=users,
        all_permissions=db.ALL_PERMISSIONS,
        active="roles",
    )


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
