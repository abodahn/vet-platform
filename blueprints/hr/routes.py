"""
HR / Staff Management Blueprint
"""
import hashlib
from flask import render_template, request, redirect, url_for, session, flash
from . import hr_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db

_ROLES = [
    "super_admin", "clinic_owner", "branch_manager", "doctor", "nurse",
    "reception", "inventory_mgr", "pharmacist", "finance", "groomer",
    "boarding_staff", "support_admin", "auditor",
]

_ROLE_COLORS = {
    "super_admin":    "#dc2626",
    "clinic_owner":   "#7c3aed",
    "branch_manager": "#1d4ed8",
    "doctor":         "#0891b2",
    "nurse":          "#0d9488",
    "reception":      "#ca8a04",
    "inventory_mgr":  "#b45309",
    "pharmacist":     "#7c3aed",
    "finance":        "#166534",
    "groomer":        "#be185d",
    "boarding_staff": "#6b7280",
    "support_admin":  "#374151",
    "auditor":        "#6b7280",
}

_SALT = "pah_platform_2026"


def _hash(pw: str) -> str:
    return hashlib.sha256(f"{_SALT}{pw}".encode()).hexdigest()


@hr_bp.route("/")
@login_required
def index():
    return redirect(url_for("hr.staff_list"))


@hr_bp.route("/staff")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def staff_list():
    conn = db.get_db()
    role_filter = request.args.get("role", "")
    search = request.args.get("q", "")
    q = "SELECT u.*, b.name as branch_name FROM users u LEFT JOIN branches b ON u.branch_id = b.id WHERE 1=1"
    params = []
    if role_filter:
        q += " AND u.role = ?"
        params.append(role_filter)
    if search:
        q += " AND (u.full_name LIKE ? OR u.username LIKE ? OR u.email LIKE ?)"
        s = f"%{search}%"
        params += [s, s, s]
    q += " ORDER BY u.full_name"
    users = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return render_template(
        "hr/staff_list.html",
        users=users,
        roles=_ROLES,
        role_colors=_ROLE_COLORS,
        role_filter=role_filter,
        search=search,
        active="hr",
    )


@hr_bp.route("/staff/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def staff_new():
    conn = db.get_db()
    branches = [dict(r) for r in conn.execute("SELECT * FROM branches WHERE is_active=1 ORDER BY name").fetchall()]
    conn.close()
    if request.method == "POST":
        f = request.form
        username = f.get("username", "").strip()
        password = f.get("password", "")
        confirm  = f.get("confirm_password", "")
        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("hr/staff_form.html", roles=_ROLES, branches=branches, form=f, active="hr")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("hr/staff_form.html", roles=_ROLES, branches=branches, form=f, active="hr")
        try:
            conn = db.get_db()
            branch_id = f.get("branch_id") or None
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, full_name_ar, email, phone, role, branch_id, is_active) VALUES (?,?,?,?,?,?,?,?,?)",
                (username, _hash(password), f.get("full_name",""), f.get("full_name_ar",""),
                 f.get("email",""), f.get("phone",""), f.get("role","reception"),
                 branch_id, 1 if f.get("is_active") else 0)
            )
            conn.commit()
            conn.close()
            db.log_audit(
                username=session["user"]["username"],
                role=session["user"]["role"],
                action="create",
                module="hr",
                entity_type="user",
                details=f"Created user: {username}",
                ip=request.remote_addr,
            )
            flash(f"Staff member '{username}' created successfully.", "success")
            return redirect(url_for("hr.staff_list"))
        except Exception as e:
            flash(f"Error creating user: {e}", "danger")
            conn = db.get_db()
            branches = [dict(r) for r in conn.execute("SELECT * FROM branches WHERE is_active=1 ORDER BY name").fetchall()]
            conn.close()
            return render_template("hr/staff_form.html", roles=_ROLES, branches=branches, form=f, active="hr")
    return render_template("hr/staff_form.html", roles=_ROLES, branches=branches, form={}, active="hr")


@hr_bp.route("/staff/<int:user_id>")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def staff_detail(user_id):
    conn = db.get_db()
    user = conn.execute(
        "SELECT u.*, b.name as branch_name FROM users u LEFT JOIN branches b ON u.branch_id = b.id WHERE u.id=?",
        (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for("hr.staff_list"))
    user = dict(user)
    audit = [dict(r) for r in conn.execute(
        "SELECT * FROM audit_log WHERE username=? ORDER BY timestamp DESC LIMIT 50",
        (user["username"],)
    ).fetchall()]
    conn.close()
    return render_template(
        "hr/staff_detail.html",
        staff=user,
        audit=audit,
        role_colors=_ROLE_COLORS,
        active="hr",
    )


@hr_bp.route("/staff/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def staff_edit(user_id):
    conn = db.get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for("hr.staff_list"))
    user = dict(user)
    branches = [dict(r) for r in conn.execute("SELECT * FROM branches WHERE is_active=1 ORDER BY name").fetchall()]
    conn.close()
    if request.method == "POST":
        f = request.form
        try:
            conn = db.get_db()
            branch_id = f.get("branch_id") or None
            is_active = 1 if f.get("is_active") else 0
            conn.execute(
                """UPDATE users SET full_name=?, full_name_ar=?, email=?, phone=?,
                   role=?, branch_id=?, is_active=?, updated_at=datetime('now') WHERE id=?""",
                (f.get("full_name",""), f.get("full_name_ar",""), f.get("email",""),
                 f.get("phone",""), f.get("role", user["role"]), branch_id, is_active, user_id)
            )
            conn.commit()
            conn.close()
            db.log_audit(
                username=session["user"]["username"],
                role=session["user"]["role"],
                action="update",
                module="hr",
                entity_type="user",
                entity_id=str(user_id),
                details=f"Updated user id={user_id}",
                ip=request.remote_addr,
            )
            flash("Staff member updated successfully.", "success")
            return redirect(url_for("hr.staff_detail", user_id=user_id))
        except Exception as e:
            flash(f"Error updating user: {e}", "danger")
    return render_template(
        "hr/staff_form.html",
        roles=_ROLES,
        branches=branches,
        form=user,
        editing=True,
        staff_id=user_id,
        active="hr",
    )


@hr_bp.route("/staff/<int:user_id>/reset-password", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def staff_reset_password(user_id):
    new_password = request.form.get("new_password", "")
    if not new_password or len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("hr.staff_detail", user_id=user_id))
    try:
        conn = db.get_db()
        conn.execute(
            "UPDATE users SET password_hash=?, updated_at=datetime('now') WHERE id=?",
            (_hash(new_password), user_id)
        )
        conn.commit()
        conn.close()
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="reset_password",
            module="hr",
            entity_type="user",
            entity_id=str(user_id),
            ip=request.remote_addr,
        )
        flash("Password reset successfully.", "success")
    except Exception as e:
        flash(f"Error resetting password: {e}", "danger")
    return redirect(url_for("hr.staff_detail", user_id=user_id))


@hr_bp.route("/roles")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def roles_list():
    conn = db.get_db()
    roles = [dict(r) for r in conn.execute("SELECT * FROM roles ORDER BY name").fetchall()]
    # Add user counts
    for role in roles:
        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role=? AND is_active=1", (role["name"],)
        ).fetchone()[0]
        role["user_count"] = count
        role["color"] = role.get("color") or _ROLE_COLORS.get(role["name"], "#6b7280")
    conn.close()
    return render_template("hr/roles_list.html", roles=roles, active="hr")
