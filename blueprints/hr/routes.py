"""
HR / Staff Management Blueprint — Full Edition
Covers: HR dashboard, staff CRUD with full profile, shift assignment,
        performance reviews, roles management.
"""
import hashlib
import logging
from datetime import date
from flask import (
    render_template, request, redirect, url_for,
    session, flash, jsonify,
)
from . import hr_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db

logger = logging.getLogger(__name__)

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

# Roles that may open hr.staff_detail. The attendance and payroll blueprints
# import this so they only render a link to a staff profile the viewer can
# actually open — a link that lands on "you don't have permission" is worse
# than plain text. role_required always lets super_admin through as well.
# The hr role exists in _SEED_ROLES and is granted staff + attendance access.
# It is deliberately NOT granted password resets, record deletion, RBAC admin
# or anything under /payroll/ — an HR officer manages people, not security or pay.
STAFF_VIEW_ROLES = ("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")


def can_view_staff(user) -> bool:
    return (user or {}).get("role") in STAFF_VIEW_ROLES


def _may_act_on(subject_user_id) -> bool:
    """May the caller read or act on a record belonging to `subject_user_id`?

    HR staff may act on anyone; everyone else only on themselves. Reviews and
    warnings were @login_required only, which let any logged-in colleague read
    a review and flip an "acknowledged" flag on someone else's disciplinary
    record. The subject id must come from the stored row, never from the URL —
    the URL is attacker-controlled.
    """
    u = session.get("user") or {}
    if u.get("role") in STAFF_VIEW_ROLES:
        return True
    try:
        return int(u.get("id")) == int(subject_user_id)
    except (TypeError, ValueError):
        return False


def _days_left(expiry) -> int | None:
    """Days from today until `expiry`, or None if there is no expiry date.

    This used to be computed in SQL as `(expiry_date - CURRENT_DATE)`. That is
    PostgreSQL date arithmetic; on SQLite the same expression coerces two ISO
    strings to numbers and returns 0 for every row, so every certification
    rendered as "expiring in 0 days" regardless of its real expiry.
    """
    if not expiry:
        return None
    try:
        return (date.fromisoformat(str(expiry)[:10]) - date.today()).days
    except ValueError:
        return None


_CONTRACT_TYPES = ["Full-time", "Part-time", "Contract", "Probation", "Intern"]
_GENDERS        = ["Male", "Female", "Not specified"]
_REVIEW_STATUSES = ["Draft", "Submitted", "Acknowledged"]

_SALT = "pah_platform_2026"

# Which database the HR schema has been ensured against — not a bare bool.
# A plain "already done" flag is wrong the moment the process talks to more
# than one database (a re-provisioned tenant, a test pointing db._db_path at a
# temp file): the flag latches on the first database and every later one is
# left without users.hire_date / contract_type / the HR tables, which surfaces
# as "no such column: contract_type" from routes that look fine in isolation.
_hr_ready = None


def _db_target():
    """A value identifying the database db.get_db() will hand back."""
    return repr((db._db_path, db._PG_CONFIG))


def _hash(pw: str) -> str:
    return hashlib.sha256(f"{_SALT}{pw}".encode()).hexdigest()


def _add_column(conn, ddl: str) -> None:
    """Run an idempotent ALTER TABLE ... ADD COLUMN.

    `ADD COLUMN IF NOT EXISTS` is PostgreSQL-only (SQLite raises a syntax error),
    so the DDL is written plainly and the already-applied case is detected from
    the error text. On PostgreSQL the statement runs inside a SAVEPOINT so a
    failure does not abort the surrounding transaction.
    """
    try:
        if isinstance(conn, db._PGConn):
            conn.execute(ddl, _protect=True)
        else:
            conn.execute(ddl)
    except Exception as exc:
        msg = str(exc).lower()
        if "duplicate column" in msg or "already exists" in msg:
            logger.debug("HR schema: column already present — %s", ddl)
        else:
            logger.warning("HR schema: ALTER failed — %s (%s)", ddl, exc)


def _ensure_hr_tables():
    global _hr_ready
    target = _db_target()
    if _hr_ready == target:
        return
    conn = db.get_db()
    for ddl in [
        "ALTER TABLE users ADD COLUMN hire_date DATE",
        "ALTER TABLE users ADD COLUMN contract_type VARCHAR(30) DEFAULT 'Full-time'",
        "ALTER TABLE users ADD COLUMN national_id VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN emergency_contact TEXT",
        "ALTER TABLE users ADD COLUMN emergency_phone VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN job_title VARCHAR(100)",
        "ALTER TABLE users ADD COLUMN gender VARCHAR(10)",
        "ALTER TABLE users ADD COLUMN dob DATE",
    ]:
        _add_column(conn, ddl)
    # DDL below is SQLite-flavoured on purpose: models.database._fix_sql translates
    # it to PostgreSQL on the PG path, and there is no reverse translation.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS performance_reviews (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            reviewer_id  INTEGER,
            period       VARCHAR(20) NOT NULL,
            rating       INTEGER CHECK (rating BETWEEN 1 AND 5),
            strengths    TEXT,
            improvements TEXT,
            goals        TEXT,
            comments     TEXT,
            status       VARCHAR(20) DEFAULT 'Draft',
            reviewed_at  DATE,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff_warnings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            issued_by    INTEGER,
            warning_type VARCHAR(20) DEFAULT 'Verbal',
            reason       TEXT,
            action_taken TEXT,
            issued_date  DATE DEFAULT CURRENT_DATE,
            expiry_date  DATE,
            acknowledged BOOLEAN DEFAULT FALSE,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff_certifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            cert_name   VARCHAR(200) NOT NULL,
            issued_by   VARCHAR(200),
            cert_number VARCHAR(100),
            issue_date  DATE,
            expiry_date DATE,
            status      VARCHAR(20) DEFAULT 'Active',
            notes       TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            author_id  INTEGER,
            note       TEXT NOT NULL,
            is_private BOOLEAN DEFAULT TRUE,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS overtime_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            work_date   DATE NOT NULL,
            hours       NUMERIC(4,1) NOT NULL DEFAULT 0,
            reason      TEXT,
            approved_by INTEGER,
            status      VARCHAR(20) DEFAULT 'Pending',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    _hr_ready = target


@hr_bp.before_request
def _init():
    _ensure_hr_tables()


# ── HR DASHBOARD ──────────────────────────────────────────────────────────────

@hr_bp.route("/")
@login_required
def index():
    return redirect(url_for("hr.dashboard"))


@hr_bp.route("/dashboard")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def dashboard():
    conn  = db.get_db()
    today = date.today().isoformat()

    total_staff    = conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]
    total_inactive = conn.execute("SELECT COUNT(*) FROM users WHERE is_active=0").fetchone()[0]

    by_role = [dict(r) for r in conn.execute(
        "SELECT role, COUNT(*) AS cnt FROM users WHERE is_active=1 GROUP BY role ORDER BY cnt DESC"
    ).fetchall()]

    by_contract = [dict(r) for r in conn.execute(
        "SELECT COALESCE(contract_type,'Full-time') AS ctype, COUNT(*) AS cnt "
        "FROM users WHERE is_active=1 GROUP BY ctype ORDER BY cnt DESC"
    ).fetchall()]

    present_today = conn.execute(
        "SELECT COUNT(*) FROM attendance_records WHERE work_date=? AND status='Present'", (today,)
    ).fetchone()[0]
    late_today = conn.execute(
        "SELECT COUNT(*) FROM attendance_records WHERE work_date=? AND status='Late'", (today,)
    ).fetchone()[0]
    on_leave_today = conn.execute(
        "SELECT COUNT(*) FROM leave_requests WHERE status='Approved' AND start_date<=? AND end_date>=?",
        (today, today)
    ).fetchone()[0]
    pending_leaves = conn.execute(
        "SELECT COUNT(*) FROM leave_requests WHERE status='Pending'"
    ).fetchone()[0]

    # Payroll this month
    try:
        pm = conn.execute("""
            SELECT COUNT(*) AS tot,
                   COALESCE(SUM(net),0) AS total_net,
                   COUNT(*) FILTER (WHERE status='Paid') AS paid_cnt,
                   COALESCE(SUM(net) FILTER (WHERE status='Paid'),0) AS paid_net
            FROM salaries
            WHERE period_year=EXTRACT(YEAR FROM CURRENT_DATE)
              AND period_month=EXTRACT(MONTH FROM CURRENT_DATE)
        """).fetchone()
        payroll_stats = dict(pm) if pm else {}
    except Exception:
        payroll_stats = {}

    # Recent hires (last 90 days)
    try:
        recent_hires = [dict(r) for r in conn.execute(
            """SELECT id, full_name, role, hire_date, contract_type, job_title
               FROM users
               WHERE hire_date >= (CURRENT_DATE - INTERVAL '90 days') AND is_active=1
               ORDER BY hire_date DESC LIMIT 6"""
        ).fetchall()]
    except Exception:
        recent_hires = []

    pending_reviews = 0
    try:
        pending_reviews = conn.execute(
            "SELECT COUNT(*) FROM performance_reviews WHERE status='Draft'"
        ).fetchone()[0]
    except Exception:
        pass

    # Staff without shift assignment
    unassigned_shifts = conn.execute("""
        SELECT COUNT(*) FROM users u
        WHERE u.is_active=1
          AND NOT EXISTS (
              SELECT 1 FROM staff_shifts ss
              WHERE ss.user_id=u.id AND (ss.effective_to IS NULL OR ss.effective_to >= ?)
          )
    """, (today,)).fetchone()[0]

    # Birthdays this month (by dob month/day)
    birthdays_this_month = []
    try:
        birthdays_this_month = [dict(r) for r in conn.execute("""
            SELECT id, full_name, role, dob,
                   EXTRACT(DAY FROM dob) AS bday
            FROM users
            WHERE is_active=1 AND dob IS NOT NULL
              AND EXTRACT(MONTH FROM dob) = EXTRACT(MONTH FROM CURRENT_DATE)
            ORDER BY EXTRACT(DAY FROM dob)
        """).fetchall()]
    except Exception:
        pass

    # Work anniversaries this month
    anniversaries_this_month = []
    try:
        anniversaries_this_month = [dict(r) for r in conn.execute("""
            SELECT id, full_name, role, hire_date,
                   EXTRACT(YEAR FROM AGE(hire_date))::int AS years
            FROM users
            WHERE is_active=1 AND hire_date IS NOT NULL
              AND EXTRACT(MONTH FROM hire_date) = EXTRACT(MONTH FROM CURRENT_DATE)
              AND hire_date < CURRENT_DATE
            ORDER BY EXTRACT(DAY FROM hire_date)
        """).fetchall()]
    except Exception:
        pass

    # Certifications expiring in next 30 days
    expiring_certs = []
    try:
        expiring_certs = [dict(r) for r in conn.execute("""
            SELECT sc.id, sc.cert_name, sc.expiry_date, u.full_name, u.id AS user_id
            FROM staff_certifications sc
            JOIN users u ON u.id=sc.user_id
            WHERE sc.expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'
              AND sc.status='Active'
            ORDER BY sc.expiry_date
        """).fetchall()]
        for c in expiring_certs:
            c["days_left"] = _days_left(c["expiry_date"])
    except Exception:
        pass

    # Recent warnings (last 5)
    recent_warnings = []
    try:
        recent_warnings = [dict(r) for r in conn.execute("""
            SELECT sw.id, sw.warning_type, sw.issued_date, sw.reason,
                   u.full_name, u.id AS user_id
            FROM staff_warnings sw JOIN users u ON u.id=sw.user_id
            ORDER BY sw.created_at DESC LIMIT 5
        """).fetchall()]
    except Exception:
        pass

    # Pending overtime approvals
    pending_overtime = 0
    try:
        pending_overtime = conn.execute(
            "SELECT COUNT(*) FROM overtime_log WHERE status='Pending'"
        ).fetchone()[0]
    except Exception:
        pass

    conn.close()
    return render_template("hr/dashboard.html",
        active="hr",
        total_staff=total_staff,
        total_inactive=total_inactive,
        by_role=by_role,
        by_contract=by_contract,
        present_today=present_today,
        late_today=late_today,
        on_leave_today=on_leave_today,
        pending_leaves=pending_leaves,
        payroll_stats=payroll_stats,
        recent_hires=recent_hires,
        pending_reviews=pending_reviews,
        unassigned_shifts=unassigned_shifts,
        birthdays_this_month=birthdays_this_month,
        anniversaries_this_month=anniversaries_this_month,
        expiring_certs=expiring_certs,
        recent_warnings=recent_warnings,
        pending_overtime=pending_overtime,
        role_colors=_ROLE_COLORS,
        today=today,
    )


# ── STAFF LIST ────────────────────────────────────────────────────────────────

@hr_bp.route("/staff")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def staff_list():
    conn            = db.get_db()
    role_filter     = request.args.get("role", "")
    contract_filter = request.args.get("contract", "")
    search          = request.args.get("q", "")
    status_filter   = request.args.get("status", "active")

    q      = "SELECT u.*, b.name AS branch_name FROM users u LEFT JOIN branches b ON u.branch_id=b.id WHERE 1=1"
    params: list = []

    if status_filter == "active":
        q += " AND u.is_active=1"
    elif status_filter == "inactive":
        q += " AND u.is_active=0"
    if role_filter:
        q += " AND u.role=?"; params.append(role_filter)
    if contract_filter:
        q += " AND u.contract_type=?"; params.append(contract_filter)
    if search:
        q += " AND (u.full_name ILIKE ? OR u.username ILIKE ? OR u.email ILIKE ? OR u.job_title ILIKE ?)"
        s = f"%{search}%"; params += [s, s, s, s]
    q += " ORDER BY u.full_name"

    users = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()
    return render_template("hr/staff_list.html",
        users=users, roles=_ROLES, role_colors=_ROLE_COLORS,
        contract_types=_CONTRACT_TYPES,
        role_filter=role_filter, contract_filter=contract_filter,
        search=search, status_filter=status_filter,
        active="hr",
    )


# ── STAFF FORM HELPERS ────────────────────────────────────────────────────────

def _coerce_date(val):
    return val.strip() if val and val.strip() else None


def _save_staff_fields(f, conn, user_id=None):
    full_name         = f.get("full_name", "").strip()
    full_name_ar      = f.get("full_name_ar", "").strip()
    email             = f.get("email", "").strip()
    phone             = f.get("phone", "").strip()
    role              = f.get("role", "reception")
    branch_id         = f.get("branch_id") or None
    is_active         = 1 if f.get("is_active") else 0
    job_title         = f.get("job_title", "").strip()
    contract_type     = f.get("contract_type", "Full-time")
    hire_date         = _coerce_date(f.get("hire_date"))
    national_id       = f.get("national_id", "").strip()
    emergency_contact = f.get("emergency_contact", "").strip()
    emergency_phone   = f.get("emergency_phone", "").strip()
    gender            = f.get("gender", "")
    dob               = _coerce_date(f.get("dob"))

    if user_id:
        conn.execute("""
            UPDATE users SET
                full_name=?, full_name_ar=?, email=?, phone=?,
                role=?, branch_id=?, is_active=?,
                job_title=?, contract_type=?, hire_date=?,
                national_id=?, emergency_contact=?, emergency_phone=?,
                gender=?, dob=?, updated_at=datetime('now')
            WHERE id=?
        """, (full_name, full_name_ar, email, phone,
              role, branch_id, is_active,
              job_title, contract_type, hire_date,
              national_id, emergency_contact, emergency_phone,
              gender, dob, user_id))
    else:
        username = f.get("username", "").strip()
        password = f.get("password", "")
        conn.execute("""
            INSERT INTO users (
                username, password_hash, full_name, full_name_ar, email, phone,
                role, branch_id, is_active, job_title, contract_type, hire_date,
                national_id, emergency_contact, emergency_phone, gender, dob
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (username, _hash(password),
              full_name, full_name_ar, email, phone,
              role, branch_id, is_active,
              job_title, contract_type, hire_date,
              national_id, emergency_contact, emergency_phone,
              gender, dob))
    conn.commit()


def _get_form_deps(conn):
    branches = [dict(r) for r in conn.execute(
        "SELECT * FROM branches WHERE is_active=1 ORDER BY name"
    ).fetchall()]
    shifts = [dict(r) for r in conn.execute(
        "SELECT * FROM shifts WHERE is_active=1 ORDER BY name"
    ).fetchall()]
    return branches, shifts


# ── STAFF NEW ─────────────────────────────────────────────────────────────────

@hr_bp.route("/staff/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def staff_new():
    conn = db.get_db()
    branches, shifts = _get_form_deps(conn)
    conn.close()

    if request.method == "POST":
        f        = request.form
        username = f.get("username", "").strip()
        password = f.get("password", "")
        confirm  = f.get("confirm_password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("hr/staff_form.html",
                roles=_ROLES, branches=branches, shifts=shifts,
                contract_types=_CONTRACT_TYPES, genders=_GENDERS, form=f, active="hr")
        if password != confirm:
            flash("Passwords do not match.", "danger")
            return render_template("hr/staff_form.html",
                roles=_ROLES, branches=branches, shifts=shifts,
                contract_types=_CONTRACT_TYPES, genders=_GENDERS, form=f, active="hr")
        try:
            conn = db.get_db()
            _save_staff_fields(f, conn)
            # Assign initial shift if chosen
            shift_id = f.get("shift_id")
            if shift_id:
                new_row = conn.execute(
                    "SELECT id FROM users WHERE username=?", (username,)
                ).fetchone()
                if new_row:
                    conn.execute(
                        "INSERT INTO staff_shifts(user_id,shift_id,effective_from) VALUES(?,?,?)",
                        (new_row[0], shift_id, date.today().isoformat())
                    )
                    conn.commit()
            conn.close()
            db.log_audit(username=session["user"]["username"],
                         role=session["user"]["role"],
                         action="create", module="hr", entity_type="user",
                         details=f"Created user: {username}", ip=request.remote_addr)
            flash(f"Staff member '{username}' created successfully.", "success")
            return redirect(url_for("hr.staff_list"))
        except Exception as e:
            flash(f"Error creating user: {e}", "danger")
            conn2 = db.get_db()
            branches, shifts = _get_form_deps(conn2)
            conn2.close()
            return render_template("hr/staff_form.html",
                roles=_ROLES, branches=branches, shifts=shifts,
                contract_types=_CONTRACT_TYPES, genders=_GENDERS, form=f, active="hr")

    return render_template("hr/staff_form.html",
        roles=_ROLES, branches=branches, shifts=shifts,
        contract_types=_CONTRACT_TYPES, genders=_GENDERS,
        form={}, active="hr")


# ── STAFF DETAIL ──────────────────────────────────────────────────────────────

@hr_bp.route("/staff/<int:user_id>")
@role_required(*STAFF_VIEW_ROLES)
def staff_detail(user_id):
    conn = db.get_db()
    user = conn.execute(
        "SELECT u.*, b.name AS branch_name FROM users u "
        "LEFT JOIN branches b ON u.branch_id=b.id WHERE u.id=?",
        (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for("hr.staff_list"))
    user = dict(user)

    # Current shift
    shift_info = conn.execute("""
        SELECT ss.*, s.name AS shift_name, s.start_time, s.end_time,
               s.days_of_week, s.color, s.break_minutes
        FROM staff_shifts ss JOIN shifts s ON s.id=ss.shift_id
        WHERE ss.user_id=? AND (ss.effective_to IS NULL OR ss.effective_to >= ?)
        ORDER BY ss.effective_from DESC LIMIT 1
    """, (user_id, date.today().isoformat())).fetchone()
    shift_info = dict(shift_info) if shift_info else None

    all_shifts = [dict(r) for r in conn.execute(
        "SELECT * FROM shifts WHERE is_active=1 ORDER BY name"
    ).fetchall()]

    # Performance reviews
    reviews = [dict(r) for r in conn.execute("""
        SELECT pr.*, u.full_name AS reviewer_name
        FROM performance_reviews pr
        LEFT JOIN users u ON u.id=pr.reviewer_id
        WHERE pr.user_id=? ORDER BY pr.created_at DESC LIMIT 5
    """, (user_id,)).fetchall()]

    # Last 6 salary records
    try:
        salary_history = [dict(r) for r in conn.execute("""
            SELECT id, period_year, period_month, basic_salary, net, status, payment_date
            FROM salaries WHERE user_id=?
            ORDER BY period_year DESC, period_month DESC LIMIT 6
        """, (user_id,)).fetchall()]
    except Exception:
        salary_history = []

    # Attendance this month
    month_start = date.today().replace(day=1).isoformat()
    try:
        att = conn.execute("""
            SELECT
                COUNT(*) FILTER (WHERE status='Present') AS present,
                COUNT(*) FILTER (WHERE status='Absent')  AS absent,
                COUNT(*) FILTER (WHERE status='Late')    AS late,
                COALESCE(SUM(hours_worked),0)            AS total_hours
            FROM attendance_records
            WHERE user_id=? AND work_date >= ?
        """, (user_id, month_start)).fetchone()
        att_summary = dict(att) if att else {}
    except Exception:
        att_summary = {}

    # Leave balances this year
    leave_balances = [dict(r) for r in conn.execute("""
        SELECT lb.*, lt.name, lt.color, lt.is_paid
        FROM leave_balances lb JOIN leave_types lt ON lt.id=lb.leave_type_id
        WHERE lb.user_id=? AND lb.year=?
    """, (user_id, date.today().year)).fetchall()]

    # Recent audit
    audit = [dict(r) for r in conn.execute(
        "SELECT * FROM audit_log WHERE username=? ORDER BY timestamp DESC LIMIT 30",
        (user["username"],)
    ).fetchall()]

    # Warnings
    warnings = []
    try:
        warnings = [dict(r) for r in conn.execute("""
            SELECT sw.*, u.full_name AS issued_by_name
            FROM staff_warnings sw LEFT JOIN users u ON u.id=sw.issued_by
            WHERE sw.user_id=? ORDER BY sw.issued_date DESC
        """, (user_id,)).fetchall()]
    except Exception:
        pass

    # Certifications
    certifications = []
    try:
        certifications = [dict(r) for r in conn.execute(
            "SELECT * FROM staff_certifications WHERE user_id=? ORDER BY expiry_date ASC NULLS LAST",
            (user_id,)
        ).fetchall()]
    except Exception:
        pass

    # HR Notes
    hr_notes = []
    try:
        hr_notes = [dict(r) for r in conn.execute("""
            SELECT sn.*, u.full_name AS author_name
            FROM staff_notes sn LEFT JOIN users u ON u.id=sn.author_id
            WHERE sn.user_id=? ORDER BY sn.created_at DESC LIMIT 20
        """, (user_id,)).fetchall()]
    except Exception:
        pass

    # Overtime log (last 10)
    overtime = []
    try:
        overtime = [dict(r) for r in conn.execute("""
            SELECT ol.*, a.full_name AS approver_name
            FROM overtime_log ol
            LEFT JOIN users a ON a.id=ol.approved_by
            WHERE ol.user_id=? ORDER BY ol.work_date DESC LIMIT 10
        """, (user_id,)).fetchall()]
    except Exception:
        pass

    conn.close()
    return render_template("hr/staff_detail.html",
        staff=user,
        shift_info=shift_info, all_shifts=all_shifts,
        reviews=reviews,
        salary_history=salary_history,
        att_summary=att_summary,
        leave_balances=leave_balances,
        audit=audit,
        warnings=warnings,
        certifications=certifications,
        hr_notes=hr_notes,
        overtime=overtime,
        role_colors=_ROLE_COLORS,
        contract_types=_CONTRACT_TYPES,
        active="hr",
        today=date.today(),
    )


# ── STAFF EDIT ────────────────────────────────────────────────────────────────

@hr_bp.route("/staff/<int:user_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def staff_edit(user_id):
    conn = db.get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for("hr.staff_list"))
    user = dict(user)
    branches, shifts = _get_form_deps(conn)
    conn.close()

    if request.method == "POST":
        try:
            conn = db.get_db()
            _save_staff_fields(request.form, conn, user_id=user_id)
            conn.close()
            db.log_audit(username=session["user"]["username"],
                         role=session["user"]["role"],
                         action="update", module="hr", entity_type="user",
                         entity_id=str(user_id),
                         details=f"Updated user id={user_id}",
                         ip=request.remote_addr)
            flash("Staff member updated successfully.", "success")
            return redirect(url_for("hr.staff_detail", user_id=user_id))
        except Exception as e:
            flash(f"Error updating user: {e}", "danger")

    return render_template("hr/staff_form.html",
        roles=_ROLES, branches=branches, shifts=shifts,
        contract_types=_CONTRACT_TYPES, genders=_GENDERS,
        form=user, editing=True, staff_id=user_id, active="hr")


# ── RESET PASSWORD ────────────────────────────────────────────────────────────

@hr_bp.route("/staff/<int:user_id>/reset-password", methods=["POST"])
@role_required("super_admin", "clinic_owner", "support_admin")
def staff_reset_password(user_id):
    new_password = request.form.get("new_password", "")
    if not new_password or len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
        return redirect(url_for("hr.staff_detail", user_id=user_id))
    try:
        conn = db.get_db()
        conn.execute("UPDATE users SET password_hash=?, updated_at=datetime('now') WHERE id=?",
                     (_hash(new_password), user_id))
        conn.commit()
        conn.close()
        db.log_audit(username=session["user"]["username"],
                     role=session["user"]["role"],
                     action="reset_password", module="hr", entity_type="user",
                     entity_id=str(user_id), ip=request.remote_addr)
        flash("Password reset successfully.", "success")
    except Exception as e:
        flash(f"Error resetting password: {e}", "danger")
    return redirect(url_for("hr.staff_detail", user_id=user_id))


# ── SHIFT ASSIGNMENT ──────────────────────────────────────────────────────────

@hr_bp.route("/staff/<int:user_id>/assign-shift", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def staff_assign_shift(user_id):
    shift_id = request.form.get("shift_id")
    eff_from = request.form.get("effective_from") or date.today().isoformat()
    eff_to   = request.form.get("effective_to") or None
    today    = date.today().isoformat()
    conn     = db.get_db()
    if shift_id:
        conn.execute("""
            UPDATE staff_shifts SET effective_to=?
            WHERE user_id=? AND (effective_to IS NULL OR effective_to >= ?)
        """, (eff_from, user_id, today))
        conn.execute(
            "INSERT INTO staff_shifts(user_id,shift_id,effective_from,effective_to) VALUES(?,?,?,?)",
            (user_id, shift_id, eff_from, eff_to)
        )
        conn.commit()
        flash("Shift assigned successfully.", "success")
    else:
        conn.execute("""
            UPDATE staff_shifts SET effective_to=?
            WHERE user_id=? AND (effective_to IS NULL OR effective_to >= ?)
        """, (today, user_id, today))
        conn.commit()
        flash("Shift removed from staff member.", "info")
    conn.close()
    return redirect(url_for("hr.staff_detail", user_id=user_id))


# ── ROLES LIST ────────────────────────────────────────────────────────────────

@hr_bp.route("/roles")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def roles_list():
    conn  = db.get_db()
    roles = [dict(r) for r in conn.execute("SELECT * FROM roles ORDER BY name").fetchall()]
    for role in roles:
        count = conn.execute(
            "SELECT COUNT(*) FROM users WHERE role=? AND is_active=1", (role["name"],)
        ).fetchone()[0]
        role["user_count"] = count
        role["color"] = role.get("color") or _ROLE_COLORS.get(role["name"], "#6b7280")
    conn.close()
    return render_template("hr/roles_list.html", roles=roles, active="hr")


# ── PERFORMANCE REVIEWS ───────────────────────────────────────────────────────

@hr_bp.route("/performance")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def performance_list():
    conn   = db.get_db()
    period = request.args.get("period", "")
    uid    = request.args.get("user_id", "")

    q = """SELECT pr.*, u.full_name AS staff_name, u.role AS staff_role,
                  r.full_name AS reviewer_name
           FROM performance_reviews pr
           JOIN users u ON u.id=pr.user_id
           LEFT JOIN users r ON r.id=pr.reviewer_id
           WHERE 1=1"""
    params: list = []
    if period:
        q += " AND pr.period=?"; params.append(period)
    if uid:
        q += " AND pr.user_id=?"; params.append(uid)
    q += " ORDER BY pr.created_at DESC LIMIT 100"

    reviews = [dict(r) for r in conn.execute(q, params).fetchall()]
    staff   = [dict(r) for r in conn.execute(
        "SELECT id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()]
    periods = [r[0] for r in conn.execute(
        "SELECT DISTINCT period FROM performance_reviews ORDER BY period DESC"
    ).fetchall()]
    conn.close()
    return render_template("hr/performance_list.html",
        reviews=reviews, staff_list=staff, periods=periods,
        period_filter=period, uid_filter=uid,
        status_filter=request.args.get("status",""),
        is_manager=True, active="hr")


@hr_bp.route("/performance/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def performance_new():
    conn  = db.get_db()
    staff = [dict(r) for r in conn.execute(
        "SELECT id, full_name, role FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()]
    conn.close()

    if request.method == "POST":
        f = request.form
        try:
            conn = db.get_db()
            conn.execute("""
                INSERT INTO performance_reviews
                    (user_id, reviewer_id, period, rating, strengths,
                     improvements, goals, comments, status, reviewed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (int(f["user_id"]), session["user"]["id"],
                  f.get("period", "").strip(),
                  int(f.get("rating") or 3),
                  f.get("strengths", "").strip(),
                  f.get("improvements", "").strip(),
                  f.get("goals", "").strip(),
                  f.get("comments", "").strip(),
                  f.get("status", "Draft"),
                  f.get("reviewed_at") or date.today().isoformat()))
            conn.commit()
            conn.close()
            flash("Performance review created.", "success")
            return redirect(url_for("hr.performance_list"))
        except Exception as e:
            conn.close()
            flash(f"Error: {e}", "danger")

    form = request.form if request.method == "POST" else {}
    return render_template("hr/performance_form.html",
        editing=False, form=form, staff_list=staff,
        review_statuses=_REVIEW_STATUSES, active="hr",
        today=date.today().isoformat())


@hr_bp.route("/performance/<int:rev_id>")
@login_required
def performance_detail(rev_id):
    conn = db.get_db()
    rev  = conn.execute("""
        SELECT pr.*, u.full_name AS staff_name, u.role AS staff_role,
               r.full_name AS reviewer_name
        FROM performance_reviews pr
        JOIN users u ON u.id=pr.user_id
        LEFT JOIN users r ON r.id=pr.reviewer_id
        WHERE pr.id=?
    """, (rev_id,)).fetchone()
    conn.close()
    if not rev:
        flash("Review not found.", "danger")
        return redirect(url_for("hr.performance_list"))
    if not _may_act_on(rev["user_id"]):
        flash("You don't have permission to view this review.", "danger")
        return redirect(url_for("launcher.index"))
    return render_template("hr/performance_detail.html",
        review=dict(rev), role_colors=_ROLE_COLORS, active="hr")


@hr_bp.route("/performance/<int:rev_id>/edit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def performance_edit(rev_id):
    conn = db.get_db()
    rev  = conn.execute("SELECT * FROM performance_reviews WHERE id=?", (rev_id,)).fetchone()
    if not rev:
        conn.close()
        flash("Review not found.", "danger")
        return redirect(url_for("hr.performance_list"))
    rev   = dict(rev)
    staff = [dict(r) for r in conn.execute(
        "SELECT id, full_name, role FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()]
    conn.close()

    if request.method == "POST":
        f = request.form
        try:
            conn = db.get_db()
            conn.execute("""
                UPDATE performance_reviews SET
                    period=?, rating=?, strengths=?, improvements=?,
                    goals=?, comments=?, status=?, reviewed_at=?, updated_at=datetime('now')
                WHERE id=?
            """, (f.get("period"), int(f.get("rating") or 3),
                  f.get("strengths"), f.get("improvements"),
                  f.get("goals"), f.get("comments"),
                  f.get("status", "Draft"),
                  f.get("reviewed_at") or date.today().isoformat(),
                  rev_id))
            conn.commit()
            conn.close()
            flash("Review updated.", "success")
            return redirect(url_for("hr.performance_detail", rev_id=rev_id))
        except Exception as e:
            conn.close()
            flash(f"Error: {e}", "danger")

    form = dict(request.form) if request.method == "POST" else rev
    return render_template("hr/performance_form.html",
        editing=True, form=form, staff_list=staff,
        review_statuses=_REVIEW_STATUSES, active="hr",
        today=date.today().isoformat())


@hr_bp.route("/performance/<int:rev_id>/acknowledge", methods=["POST"])
@login_required
def performance_acknowledge(rev_id):
    conn = db.get_db()
    # Only the employee the review is about (or HR) may acknowledge it.
    rev = conn.execute(
        "SELECT user_id FROM performance_reviews WHERE id=?", (rev_id,)).fetchone()
    if not rev or not _may_act_on(rev["user_id"]):
        conn.close()
        flash("You don't have permission to acknowledge this review.", "danger")
        return redirect(url_for("launcher.index"))
    conn.execute(
        "UPDATE performance_reviews SET status='Acknowledged',updated_at=datetime('now') WHERE id=?",
        (rev_id,)
    )
    conn.commit()
    conn.close()
    flash("Review acknowledged.", "success")
    return redirect(url_for("hr.performance_detail", rev_id=rev_id))


# ── WARNINGS / DISCIPLINARY ───────────────────────────────────────────────────

_WARNING_TYPES = ["Verbal", "Written", "Final Warning", "Suspension"]

@hr_bp.route("/staff/<int:user_id>/warnings/add", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def add_warning(user_id):
    f = request.form
    conn = db.get_db()
    try:
        conn.execute("""
            INSERT INTO staff_warnings
                (user_id, issued_by, warning_type, reason, action_taken,
                 issued_date, expiry_date)
            VALUES (?,?,?,?,?,?,?)
        """, (user_id,
              session["user"]["id"],
              f.get("warning_type", "Verbal"),
              f.get("reason", "").strip(),
              f.get("action_taken", "").strip(),
              f.get("issued_date") or date.today().isoformat(),
              f.get("expiry_date") or None))
        conn.commit()
        flash("Warning recorded.", "warning")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("hr.staff_detail", user_id=user_id))


@hr_bp.route("/staff/<int:user_id>/warnings/<int:warn_id>/acknowledge", methods=["POST"])
@login_required
def acknowledge_warning(user_id, warn_id):
    conn = db.get_db()
    # The subject comes from the stored warning, not from the URL.
    warn = conn.execute(
        "SELECT user_id FROM staff_warnings WHERE id=?", (warn_id,)).fetchone()
    if not warn or not _may_act_on(warn["user_id"]):
        conn.close()
        flash("You don't have permission to acknowledge this warning.", "danger")
        return redirect(url_for("launcher.index"))
    conn.execute("UPDATE staff_warnings SET acknowledged=TRUE WHERE id=?", (warn_id,))
    conn.commit()
    conn.close()
    flash("Warning acknowledged by employee.", "success")
    return redirect(url_for("hr.staff_detail", user_id=user_id))


@hr_bp.route("/staff/<int:user_id>/warnings/<int:warn_id>/delete", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def delete_warning(user_id, warn_id):
    conn = db.get_db()
    conn.execute("DELETE FROM staff_warnings WHERE id=? AND user_id=?", (warn_id, user_id))
    conn.commit()
    conn.close()
    flash("Warning deleted.", "info")
    return redirect(url_for("hr.staff_detail", user_id=user_id))


# ── CERTIFICATIONS / TRAINING ─────────────────────────────────────────────────

@hr_bp.route("/certifications")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def certifications_list():
    conn = db.get_db()
    certs = [dict(r) for r in conn.execute("""
        SELECT sc.*, u.full_name, u.role, u.id AS uid
        FROM staff_certifications sc JOIN users u ON u.id=sc.user_id
        ORDER BY sc.expiry_date ASC NULLS LAST
    """).fetchall()]
    for c in certs:
        c["days_left"] = _days_left(c["expiry_date"])
    conn.close()
    return render_template("hr/certifications_list.html",
        certs=certs, active="hr")


@hr_bp.route("/staff/<int:user_id>/certifications/add", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def add_certification(user_id):
    f = request.form
    conn = db.get_db()
    try:
        conn.execute("""
            INSERT INTO staff_certifications
                (user_id, cert_name, issued_by, cert_number, issue_date, expiry_date, status, notes)
            VALUES (?,?,?,?,?,?,?,?)
        """, (user_id,
              f.get("cert_name", "").strip(),
              f.get("issued_by", "").strip(),
              f.get("cert_number", "").strip(),
              f.get("issue_date") or None,
              f.get("expiry_date") or None,
              f.get("status", "Active"),
              f.get("notes", "").strip()))
        conn.commit()
        flash("Certification added.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("hr.staff_detail", user_id=user_id))


@hr_bp.route("/staff/<int:user_id>/certifications/<int:cert_id>/delete", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def delete_certification(user_id, cert_id):
    conn = db.get_db()
    conn.execute("DELETE FROM staff_certifications WHERE id=? AND user_id=?", (cert_id, user_id))
    conn.commit()
    conn.close()
    flash("Certification removed.", "info")
    return redirect(url_for("hr.staff_detail", user_id=user_id))


# ── HR NOTES ─────────────────────────────────────────────────────────────────

@hr_bp.route("/staff/<int:user_id>/notes/add", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def add_note(user_id):
    note_text = request.form.get("note", "").strip()
    if not note_text:
        flash("Note cannot be empty.", "danger")
        return redirect(url_for("hr.staff_detail", user_id=user_id))
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO staff_notes (user_id, author_id, note) VALUES (?,?,?)",
            (user_id, session["user"]["id"], note_text)
        )
        conn.commit()
        flash("Note saved.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("hr.staff_detail", user_id=user_id))


@hr_bp.route("/staff/<int:user_id>/notes/<int:note_id>/delete", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def delete_note(user_id, note_id):
    conn = db.get_db()
    conn.execute("DELETE FROM staff_notes WHERE id=? AND user_id=?", (note_id, user_id))
    conn.commit()
    conn.close()
    flash("Note deleted.", "info")
    return redirect(url_for("hr.staff_detail", user_id=user_id))


# ── WEEKLY ROSTER ─────────────────────────────────────────────────────────────

from datetime import timedelta

@hr_bp.route("/roster")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def roster():
    week_str = request.args.get("week", date.today().isoformat())
    try:
        anchor = date.fromisoformat(week_str)
    except ValueError:
        anchor = date.today()
    # Monday of the selected week
    week_start = anchor - timedelta(days=anchor.weekday())
    week_days  = [week_start + timedelta(days=i) for i in range(7)]

    conn = db.get_db()

    # All active shifts
    shifts = [dict(r) for r in conn.execute(
        "SELECT * FROM shifts WHERE is_active=1 ORDER BY start_time"
    ).fetchall()]

    # Current shift assignments: user -> shift
    assignments = conn.execute("""
        SELECT ss.user_id, ss.shift_id, s.name shift_name, s.start_time,
               s.end_time, s.color, s.days_of_week,
               u.full_name, u.role
        FROM staff_shifts ss
        JOIN shifts s ON s.id = ss.shift_id
        JOIN users  u ON u.id = ss.user_id
        WHERE u.is_active = 1
          AND ss.effective_from <= ?
          AND (ss.effective_to IS NULL OR ss.effective_to >= ?)
    """, (week_start.isoformat(), week_start.isoformat())).fetchall()
    assignments = [dict(a) for a in assignments]

    # Attendance records for the week
    att_rows = conn.execute("""
        SELECT user_id, work_date, status, check_in, check_out
        FROM attendance_records
        WHERE work_date BETWEEN ? AND ?
    """, (week_start.isoformat(), week_days[-1].isoformat())).fetchall()
    att_map = {}
    for r in att_rows:
        att_map[(r["user_id"], r["work_date"])] = dict(r)

    # Approved leaves for the week
    leave_rows = conn.execute("""
        SELECT user_id, start_date, end_date
        FROM leave_requests
        WHERE status='Approved'
          AND start_date <= ? AND end_date >= ?
    """, (week_days[-1].isoformat(), week_start.isoformat())).fetchall()
    leave_users = set()
    for lr in leave_rows:
        s = date.fromisoformat(str(lr["start_date"]))
        e = date.fromisoformat(str(lr["end_date"]))
        for d in week_days:
            if s <= d <= e:
                leave_users.add((lr["user_id"], d.isoformat()))

    # Staff with no shift assignment
    all_staff = [dict(r) for r in conn.execute(
        "SELECT id, full_name, role FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()]
    assigned_ids = {a["user_id"] for a in assignments}
    unassigned = [s for s in all_staff if s["id"] not in assigned_ids]

    conn.close()

    return render_template("hr/roster.html",
        active="hr",
        today=date.today(),
        week_start=week_start,
        week_days=week_days,
        shifts=shifts,
        assignments=assignments,
        att_map=att_map,
        leave_users=leave_users,
        unassigned=unassigned,
        prev_week=(week_start - timedelta(days=7)).isoformat(),
        next_week=(week_start + timedelta(days=7)).isoformat(),
    )


# ── OVERTIME LOG ─────────────────────────────────────────────────────────────

_OT_STATUSES = ["Pending", "Approved", "Rejected"]

@hr_bp.route("/overtime")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def overtime_list():
    conn  = db.get_db()
    uid   = request.args.get("user_id", type=int)
    status = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")

    clauses = ["1=1"]
    params  = []
    if uid:
        clauses.append("ol.user_id=?"); params.append(uid)
    if status:
        clauses.append("ol.status=?"); params.append(status)
    if date_from:
        clauses.append("ol.work_date>=?"); params.append(date_from)
    if date_to:
        clauses.append("ol.work_date<=?"); params.append(date_to)

    where = " AND ".join(clauses)
    rows = [dict(r) for r in conn.execute(f"""
        SELECT ol.*, u.full_name, u.role,
               a.full_name AS approver_name
        FROM overtime_log ol
        JOIN users u ON u.id = ol.user_id
        LEFT JOIN users a ON a.id = ol.approved_by
        WHERE {where}
        ORDER BY ol.work_date DESC, ol.created_at DESC
        LIMIT 200
    """, params).fetchall()]

    total_hours = sum(float(r.get("hours") or 0) for r in rows if r.get("status") == "Approved")

    staff = [dict(r) for r in conn.execute(
        "SELECT id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()]
    conn.close()

    return render_template("hr/overtime.html",
        active="hr",
        rows=rows,
        staff=staff,
        total_hours=total_hours,
        uid_filter=uid,
        status_filter=status,
        date_from=date_from,
        date_to=date_to,
        ot_statuses=_OT_STATUSES,
    )


@hr_bp.route("/staff/<int:user_id>/overtime/add", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def add_overtime(user_id):
    f    = request.form
    conn = db.get_db()
    try:
        hours = float(f.get("hours") or 0)
        conn.execute("""
            INSERT INTO overtime_log (user_id, work_date, hours, reason, status)
            VALUES (?,?,?,?,?)
        """, (user_id,
              f.get("work_date") or date.today().isoformat(),
              hours,
              f.get("reason", "").strip(),
              "Pending"))
        conn.commit()
        flash(f"{hours}h overtime recorded.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("hr.staff_detail", user_id=user_id))


@hr_bp.route("/overtime/<int:ot_id>/approve", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def approve_overtime(ot_id):
    conn = db.get_db()
    conn.execute(
        "UPDATE overtime_log SET status='Approved', approved_by=? WHERE id=?",
        (session["user"]["id"], ot_id)
    )
    conn.commit()
    conn.close()
    flash("Overtime approved.", "success")
    return redirect(url_for("hr.overtime_list"))


@hr_bp.route("/overtime/<int:ot_id>/reject", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def reject_overtime(ot_id):
    conn = db.get_db()
    conn.execute(
        "UPDATE overtime_log SET status='Rejected' WHERE id=?", (ot_id,)
    )
    conn.commit()
    conn.close()
    flash("Overtime rejected.", "info")
    return redirect(url_for("hr.overtime_list"))


# ── ATTENDANCE SEARCH (HR VIEW) ───────────────────────────────────────────────

@hr_bp.route("/attendance")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def hr_attendance():
    from datetime import timedelta
    conn    = db.get_db()
    today   = date.today()

    # ── filters ──────────────────────────────────────────────────────────────
    q_name     = request.args.get("q", "").strip()
    f_status   = request.args.get("status", "")
    f_branch   = request.args.get("branch_id", "")
    f_from     = request.args.get("date_from", (today - timedelta(days=6)).isoformat())
    f_to       = request.args.get("date_to",   today.isoformat())
    f_user_id  = request.args.get("user_id",   "")
    page       = max(1, request.args.get("page", 1, type=int))
    per_page   = 50

    # base query — join users for branch & role info
    base = """
        FROM attendance_records ar
        JOIN users u ON u.id = ar.user_id
        LEFT JOIN branches b ON b.id = u.branch_id
        WHERE ar.work_date BETWEEN ? AND ?
    """
    params: list = [f_from, f_to]

    if q_name:
        base  += " AND (ar.full_name ILIKE ? OR ar.username ILIKE ?)"
        params += [f"%{q_name}%", f"%{q_name}%"]
    if f_status:
        base  += " AND ar.status=?"
        params.append(f_status)
    if f_branch:
        base  += " AND u.branch_id=?"
        params.append(f_branch)
    if f_user_id:
        base  += " AND ar.user_id=?"
        params.append(f_user_id)

    total = conn.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]

    order  = " ORDER BY ar.work_date DESC, u.full_name"
    limit  = f" LIMIT {per_page} OFFSET {(page-1)*per_page}"
    rows   = [dict(r) for r in conn.execute(
        f"SELECT ar.*, u.role, u.id AS uid, b.name AS branch_name {base}{order}{limit}",
        params
    ).fetchall()]

    # ── summary stats for the filtered range ─────────────────────────────────
    stats = conn.execute(f"""
        SELECT
            COUNT(*) FILTER (WHERE ar.status='Present')  AS present_n,
            COUNT(*) FILTER (WHERE ar.status='Late')     AS late_n,
            COUNT(*) FILTER (WHERE ar.status='Absent')   AS absent_n,
            COUNT(*) FILTER (WHERE ar.status='On Leave') AS on_leave_n,
            COUNT(*)                                     AS total_n,
            COALESCE(AVG(ar.hours_worked) FILTER (WHERE ar.hours_worked > 0), 0) AS avg_hours
        {base}
    """, params).fetchone()
    stats = dict(stats) if stats else {}

    # ── today's live board ────────────────────────────────────────────────────
    today_iso = today.isoformat()
    today_att = [dict(r) for r in conn.execute("""
        SELECT ar.*, u.role, u.id AS uid, b.name AS branch_name
        FROM attendance_records ar
        JOIN users u ON u.id = ar.user_id
        LEFT JOIN branches b ON b.id = u.branch_id
        WHERE ar.work_date = ?
        ORDER BY ar.check_in NULLS LAST, ar.full_name
    """, (today_iso,)).fetchall()]

    # Staff with no attendance record today
    absent_today = [dict(r) for r in conn.execute("""
        SELECT u.id, u.full_name, u.role, b.name AS branch_name
        FROM users u
        LEFT JOIN branches b ON b.id = u.branch_id
        WHERE u.is_active = 1
          AND NOT EXISTS (
              SELECT 1 FROM attendance_records ar
              WHERE ar.user_id = u.id AND ar.work_date = ?
          )
        ORDER BY u.full_name
    """, (today_iso,)).fetchall()]

    branches = [dict(r) for r in conn.execute(
        "SELECT * FROM branches WHERE is_active=1 ORDER BY name"
    ).fetchall()]

    all_staff = [dict(r) for r in conn.execute(
        "SELECT id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()]

    conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template("hr/hr_attendance.html",
        active      = "hr",
        rows        = rows,
        stats       = stats,
        today_att   = today_att,
        absent_today= absent_today,
        branches    = branches,
        all_staff   = all_staff,
        role_colors = _ROLE_COLORS,
        q_name      = q_name,
        f_status    = f_status,
        f_branch    = f_branch,
        f_from      = f_from,
        f_to        = f_to,
        f_user_id   = f_user_id,
        today       = today_iso,
        page        = page,
        per_page    = per_page,
        total       = total,
        total_pages = total_pages,
    )


@hr_bp.route("/attendance/add", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "hr")
def hr_attendance_add():
    f    = request.form
    conn = db.get_db()
    uid  = int(f.get("user_id") or 0)
    if not uid:
        flash("Select a staff member.", "danger")
        return redirect(url_for("hr.hr_attendance"))
    try:
        user = conn.execute(
            "SELECT username, full_name FROM users WHERE id=?", (uid,)
        ).fetchone()
        wdate    = f.get("work_date") or date.today().isoformat()
        check_in = f.get("check_in") or None
        check_out= f.get("check_out") or None
        status   = f.get("status", "Present")
        notes    = f.get("notes", "").strip()

        hours_worked = None
        if check_in and check_out:
            from datetime import datetime as _dt
            t_in  = _dt.strptime(check_in,  "%H:%M")
            t_out = _dt.strptime(check_out, "%H:%M")
            diff  = (t_out - t_in).total_seconds() / 3600
            if diff > 0:
                hours_worked = round(diff, 2)

        # attendance_records carries no UNIQUE(user_id, work_date), so the
        # ON CONFLICT upsert this used to run raised on every call — the route
        # flashed an error, redirected, and wrote nothing. Read-then-write is
        # the same pattern attendance.checkin already uses and needs no index.
        existing = conn.execute(
            "SELECT id FROM attendance_records WHERE user_id=? AND work_date=?",
            (uid, wdate)).fetchone()
        if existing:
            conn.execute("""
                UPDATE attendance_records
                   SET status=?, check_in=?, check_out=?, hours_worked=?,
                       notes=?, recorded_by=?, updated_at=datetime('now')
                 WHERE id=?
            """, (status, check_in, check_out, hours_worked, notes,
                  session["user"]["username"], existing["id"]))
        else:
            conn.execute("""
                INSERT INTO attendance_records
                    (user_id, username, full_name, work_date, status,
                     check_in, check_out, hours_worked, notes, recorded_by)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (uid, user["username"], user["full_name"], wdate, status,
                  check_in, check_out, hours_worked, notes,
                  session["user"]["username"]))
        conn.commit()
        flash("Attendance record saved.", "success")
    except Exception as e:
        flash(f"Error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("hr.hr_attendance"))


@hr_bp.route("/attendance/<int:rec_id>/delete", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "hr")
def hr_attendance_delete(rec_id):
    conn = db.get_db()
    conn.execute("DELETE FROM attendance_records WHERE id=?", (rec_id,))
    conn.commit()
    conn.close()
    flash("Record deleted.", "info")
    return redirect(url_for("hr.hr_attendance"))


# ── HR HEADCOUNT API (JSON) ───────────────────────────────────────────────────

@hr_bp.route("/api/headcount")
@login_required
def api_headcount():
    conn = db.get_db()
    rows = conn.execute(
        "SELECT role, COUNT(*) cnt FROM users WHERE is_active=1 GROUP BY role"
    ).fetchall()
    conn.close()
    return jsonify({r[0]: r[1] for r in rows})
