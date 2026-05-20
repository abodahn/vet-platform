"""
Payroll / Salary Module — Premium Animal Hospital Platform
"""

from flask import render_template, request, redirect, url_for, session, flash, jsonify, send_file
from datetime import date
from . import payroll_bp
import models.database as db
from blueprints.auth.routes import login_required, role_required
from models.excel_export import make_workbook

_ROLES = [
    "super_admin", "clinic_owner", "branch_manager", "doctor", "nurse",
    "reception", "inventory_mgr", "pharmacist", "finance", "groomer",
    "boarding_staff", "support_admin", "auditor",
]

_PAYMENT_METHODS = ["Bank Transfer", "Cash", "Cheque", "Wallet"]

_STATUS_COLORS = {
    "Draft":   "#6b7280",
    "Approved": "#2563eb",
    "Paid":    "#16a34a",
    "Cancelled": "#dc2626",
}


def _ensure_tables():
    conn = db.get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS salary_grades (
            id            SERIAL PRIMARY KEY,
            role          VARCHAR(60) UNIQUE NOT NULL,
            basic_salary  NUMERIC(12,2) NOT NULL DEFAULT 0,
            overtime_rate NUMERIC(8,2)  NOT NULL DEFAULT 0,
            notes         TEXT,
            created_at    TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS salaries (
            id                SERIAL PRIMARY KEY,
            user_id           INTEGER NOT NULL,
            period_year       INTEGER NOT NULL,
            period_month      INTEGER NOT NULL,
            basic_salary      NUMERIC(12,2) NOT NULL DEFAULT 0,
            allowances        NUMERIC(12,2) NOT NULL DEFAULT 0,
            overtime_hours    NUMERIC(6,2)  NOT NULL DEFAULT 0,
            overtime_rate     NUMERIC(8,2)  NOT NULL DEFAULT 0,
            deductions        NUMERIC(12,2) NOT NULL DEFAULT 0,
            absence_deduction NUMERIC(12,2) NOT NULL DEFAULT 0,
            tax_deduction     NUMERIC(12,2) NOT NULL DEFAULT 0,
            gross             NUMERIC(12,2) NOT NULL DEFAULT 0,
            net               NUMERIC(12,2) NOT NULL DEFAULT 0,
            status            VARCHAR(20)   NOT NULL DEFAULT 'Draft',
            payment_method    VARCHAR(40),
            payment_date      DATE,
            notes             TEXT,
            paid_by           INTEGER,
            created_by        INTEGER,
            created_at        TIMESTAMPTZ DEFAULT NOW(),
            updated_at        TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (user_id, period_year, period_month)
        )
    """)
    conn.commit()
    conn.close()


@payroll_bp.before_request
def _init():
    _ensure_tables()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _calc_gross_net(basic, allowances, ot_hours, ot_rate, deductions, absence_ded, tax_ded):
    gross = float(basic) + float(allowances) + float(ot_hours) * float(ot_rate)
    net   = gross - float(deductions) - float(absence_ded) - float(tax_ded)
    return round(gross, 2), round(net, 2)


def _get_attendance_summary(conn, user_id: int, year: int, month: int) -> dict:
    """Pull attendance data for a staff member for the given month.

    Returns:
        total_days      – calendar working days recorded
        present_days    – Present + Late
        absent_days     – Absent (not on approved leave)
        late_count      – Late check-ins
        overtime_hours  – total extra hours beyond standard shift
        absence_deduction_factor – absent_days / working_days (apply to basic)
    """
    import calendar
    from datetime import date as _date

    # All attendance records for this user/period
    records = conn.execute("""
        SELECT work_date, status, hours_worked
        FROM attendance_records
        WHERE user_id = %s
          AND EXTRACT(YEAR  FROM work_date::date) = %s
          AND EXTRACT(MONTH FROM work_date::date) = %s
    """, (user_id, year, month)).fetchall()

    # Get the staff member's standard shift hours (default 8h if no shift assigned)
    shift_row = conn.execute("""
        SELECT sh.start_time, sh.end_time, sh.break_minutes
        FROM staff_shifts ss
        JOIN shifts sh ON sh.id = ss.shift_id
        WHERE ss.user_id = %s
          AND (ss.effective_to IS NULL OR ss.effective_to >= CURRENT_DATE)
        ORDER BY ss.effective_from DESC LIMIT 1
    """, (user_id,)).fetchone()

    if shift_row:
        try:
            from datetime import datetime
            fmt = "%H:%M"
            s = datetime.strptime(str(shift_row["start_time"])[:5], fmt)
            e = datetime.strptime(str(shift_row["end_time"])[:5], fmt)
            standard_hours = (e - s).seconds / 3600 - (shift_row["break_minutes"] or 0) / 60
        except Exception:
            standard_hours = 8.0
    else:
        standard_hours = 8.0

    total_days   = len(records)
    absent_days  = sum(1 for r in records if r["status"] == "Absent")
    late_count   = sum(1 for r in records if r["status"] == "Late")
    present_days = sum(1 for r in records if r["status"] in ("Present", "Late"))

    # Overtime = hours worked beyond standard shift (only on days actually worked)
    overtime_hours = 0.0
    for r in records:
        if r["status"] in ("Present", "Late") and r["hours_worked"]:
            extra = float(r["hours_worked"]) - standard_hours
            if extra > 0:
                overtime_hours += extra

    # Working days in month (Mon–Fri, minus public holidays would be ideal but use total recorded)
    _, days_in_month = calendar.monthrange(year, month)
    working_days = total_days if total_days > 0 else days_in_month

    return {
        "total_days":    total_days,
        "present_days":  present_days,
        "absent_days":   absent_days,
        "late_count":    late_count,
        "overtime_hours": round(overtime_hours, 2),
        "working_days":  working_days,
    }


# ── Dashboard ────────────────────────────────────────────────────────────────

@payroll_bp.route("/")
@login_required
def dashboard():
    conn = db.get_db()
    today = date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))

    stats = conn.execute("""
        SELECT
            COUNT(*)                               AS total,
            COUNT(*) FILTER (WHERE status='Draft')    AS draft,
            COUNT(*) FILTER (WHERE status='Approved') AS approved,
            COUNT(*) FILTER (WHERE status='Paid')     AS paid,
            COALESCE(SUM(net) FILTER (WHERE status='Paid'),0)      AS total_paid,
            COALESCE(SUM(net) FILTER (WHERE status IN ('Draft','Approved')),0) AS total_pending
        FROM salaries
        WHERE period_year=%s AND period_month=%s
    """, (year, month)).fetchone()

    recent = conn.execute("""
        SELECT s.*, u.full_name, u.role
        FROM salaries s
        JOIN users u ON u.id = s.user_id
        WHERE s.period_year=%s AND s.period_month=%s
        ORDER BY s.updated_at DESC LIMIT 20
    """, (year, month)).fetchall()
    recent = [dict(r) for r in recent]

    # Grade coverage — how many active staff have no salary record this period
    active_staff = conn.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE is_active=1 AND role!='super_admin'"
    ).fetchone()["cnt"]

    conn.close()
    return render_template("payroll/dashboard.html",
        active="payroll", stats=dict(stats), recent=recent,
        year=year, month=month, active_staff=active_staff,
        status_colors=_STATUS_COLORS,
    )


# ── List all salaries ─────────────────────────────────────────────────────────

@payroll_bp.route("/salaries")
@login_required
def salaries_list():
    conn = db.get_db()
    today = date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))
    status_f = request.args.get("status", "")

    where  = ["s.period_year=%s", "s.period_month=%s"]
    params = [year, month]
    if status_f:
        where.append("s.status=%s")
        params.append(status_f)

    rows = conn.execute(f"""
        SELECT s.*, u.full_name, u.role
        FROM salaries s
        JOIN users u ON u.id = s.user_id
        WHERE {' AND '.join(where)}
        ORDER BY u.full_name
    """, params).fetchall()
    rows = [dict(r) for r in rows]
    conn.close()
    return render_template("payroll/salaries_list.html",
        active="payroll", rows=rows, year=year, month=month,
        status_f=status_f, status_colors=_STATUS_COLORS,
    )


# ── New salary record ─────────────────────────────────────────────────────────

@payroll_bp.route("/salaries/export/xlsx")
@login_required
def salaries_export_xlsx():
    today = date.today()
    year  = int(request.args.get("year",  today.year))
    month = int(request.args.get("month", today.month))

    conn = db.get_db()
    rows_raw = conn.execute("""
        SELECT u.full_name, u.role,
               s.period_year, s.period_month,
               s.basic_salary, s.allowances,
               s.overtime_hours, s.overtime_rate,
               s.gross_salary, s.deductions,
               s.absence_deduction, s.tax_deduction,
               s.net_salary, s.status, s.payment_date
        FROM salaries s
        JOIN users u ON u.id = s.user_id
        WHERE s.period_year=%s AND s.period_month=%s
        ORDER BY u.full_name
    """, (year, month)).fetchall()
    conn.close()

    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    headers = ["Name", "Role", "Year", "Month",
               "Basic", "Allowances", "OT Hrs", "OT Rate",
               "Gross", "Deductions", "Absence Ded", "Tax Ded",
               "Net Salary", "Status", "Payment Date"]
    rows = [
        [r["full_name"], r["role"], r["period_year"],
         month_names[int(r["period_month"]) - 1],
         float(r["basic_salary"] or 0), float(r["allowances"] or 0),
         float(r["overtime_hours"] or 0), float(r["overtime_rate"] or 0),
         float(r["gross_salary"] or 0), float(r["deductions"] or 0),
         float(r["absence_deduction"] or 0), float(r["tax_deduction"] or 0),
         float(r["net_salary"] or 0), r["status"],
         str(r["payment_date"] or "")[:10]]
        for r in rows_raw
    ]

    try:
        buf = make_workbook(
            title=f"Payroll — {month_names[month - 1]} {year}",
            headers=headers,
            rows=rows,
            sheet_name="Salaries",
        )
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"payroll_{year}_{month:02d}.xlsx",
        )
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("payroll.salaries_list", year=year, month=month))


@payroll_bp.route("/salaries/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def salary_new():
    conn = db.get_db()
    if request.method == "POST":
        f = request.form
        uid   = int(f["user_id"])
        year  = int(f["period_year"])
        month = int(f["period_month"])
        basic = float(f.get("basic_salary", 0))
        allow = float(f.get("allowances", 0))
        ot_h  = float(f.get("overtime_hours", 0))
        ot_r  = float(f.get("overtime_rate", 0))
        ded   = float(f.get("deductions", 0))
        abs_d = float(f.get("absence_deduction", 0))
        tax_d = float(f.get("tax_deduction", 0))
        gross, net = _calc_gross_net(basic, allow, ot_h, ot_r, ded, abs_d, tax_d)
        try:
            conn.execute("""
                INSERT INTO salaries
                  (user_id,period_year,period_month,basic_salary,allowances,
                   overtime_hours,overtime_rate,deductions,absence_deduction,
                   tax_deduction,gross,net,status,notes,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Draft',%s,%s)
            """, (uid, year, month, basic, allow, ot_h, ot_r, ded, abs_d,
                  tax_d, gross, net, f.get("notes",""), session["user"]["id"]))
            conn.commit()
            flash("Salary record created.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error: {e}", "danger")
        conn.close()
        return redirect(url_for("payroll.salaries_list", year=year, month=month))

    staff = conn.execute(
        "SELECT id, full_name, role FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()
    grades = {g["role"]: dict(g) for g in conn.execute(
        "SELECT * FROM salary_grades"
    ).fetchall()}
    conn.close()
    today = date.today()
    return render_template("payroll/salary_form.html",
        active="payroll", action="New", salary=None,
        staff=[dict(s) for s in staff], grades=grades,
        year=today.year, month=today.month,
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@payroll_bp.route("/salaries/<int:sid>")
@login_required
def salary_detail(sid):
    conn = db.get_db()
    row = conn.execute("""
        SELECT s.*, u.full_name, u.role, u.email, u.phone
        FROM salaries s JOIN users u ON u.id=s.user_id
        WHERE s.id=%s
    """, (sid,)).fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "danger")
        return redirect(url_for("payroll.salaries_list"))
    row = dict(row)
    payer = None
    if row.get("paid_by"):
        payer = conn.execute(
            "SELECT full_name FROM users WHERE id=%s", (row["paid_by"],)
        ).fetchone()
    conn.close()
    return render_template("payroll/salary_detail.html",
        active="payroll", salary=row, payer=payer,
        status_colors=_STATUS_COLORS,
    )


# ── Edit ──────────────────────────────────────────────────────────────────────

@payroll_bp.route("/salaries/<int:sid>/edit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def salary_edit(sid):
    conn = db.get_db()
    row = conn.execute("""
        SELECT s.*, u.full_name, u.role FROM salaries s
        JOIN users u ON u.id=s.user_id WHERE s.id=%s
    """, (sid,)).fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "danger")
        return redirect(url_for("payroll.salaries_list"))
    row = dict(row)
    if row["status"] == "Paid":
        flash("Cannot edit a paid salary.", "warning")
        conn.close()
        return redirect(url_for("payroll.salary_detail", sid=sid))

    if request.method == "POST":
        f = request.form
        basic = float(f.get("basic_salary", 0))
        allow = float(f.get("allowances", 0))
        ot_h  = float(f.get("overtime_hours", 0))
        ot_r  = float(f.get("overtime_rate", 0))
        ded   = float(f.get("deductions", 0))
        abs_d = float(f.get("absence_deduction", 0))
        tax_d = float(f.get("tax_deduction", 0))
        gross, net = _calc_gross_net(basic, allow, ot_h, ot_r, ded, abs_d, tax_d)
        conn.execute("""
            UPDATE salaries SET basic_salary=%s,allowances=%s,overtime_hours=%s,
              overtime_rate=%s,deductions=%s,absence_deduction=%s,tax_deduction=%s,
              gross=%s,net=%s,notes=%s,updated_at=NOW()
            WHERE id=%s
        """, (basic, allow, ot_h, ot_r, ded, abs_d, tax_d, gross, net,
              f.get("notes",""), sid))
        conn.commit()
        conn.close()
        flash("Salary updated.", "success")
        return redirect(url_for("payroll.salary_detail", sid=sid))

    staff = conn.execute(
        "SELECT id, full_name, role FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall()
    grades = {g["role"]: dict(g) for g in conn.execute(
        "SELECT * FROM salary_grades"
    ).fetchall()}
    conn.close()
    return render_template("payroll/salary_form.html",
        active="payroll", action="Edit", salary=row,
        staff=[dict(s) for s in staff], grades=grades,
        year=row["period_year"], month=row["period_month"],
    )


# ── Approve / Pay ─────────────────────────────────────────────────────────────

@payroll_bp.route("/salaries/<int:sid>/approve", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def salary_approve(sid):
    conn = db.get_db()
    conn.execute(
        "UPDATE salaries SET status='Approved', updated_at=NOW() WHERE id=%s AND status='Draft'",
        (sid,)
    )
    conn.commit()
    conn.close()
    flash("Salary approved.", "success")
    return redirect(url_for("payroll.salary_detail", sid=sid))


@payroll_bp.route("/salaries/<int:sid>/pay", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def salary_pay(sid):
    conn = db.get_db()
    method = request.form.get("payment_method", "Cash")
    pay_date = request.form.get("payment_date") or date.today().isoformat()
    conn.execute("""
        UPDATE salaries SET status='Paid', payment_method=%s, payment_date=%s,
          paid_by=%s, updated_at=NOW()
        WHERE id=%s AND status='Approved'
    """, (method, pay_date, session["user"]["id"], sid))
    conn.commit()
    conn.close()
    flash("Salary marked as paid.", "success")
    return redirect(url_for("payroll.salary_detail", sid=sid))


# ── Bulk generate for a period ────────────────────────────────────────────────

@payroll_bp.route("/bulk-generate", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def bulk_generate():
    year  = int(request.form.get("year",  date.today().year))
    month = int(request.form.get("month", date.today().month))
    conn  = db.get_db()

    staff = conn.execute("""
        SELECT u.id, u.role
        FROM users u
        WHERE u.is_active=1 AND u.role != 'super_admin'
          AND NOT EXISTS (
            SELECT 1 FROM salaries s
            WHERE s.user_id=u.id AND s.period_year=%s AND s.period_month=%s
          )
    """, (year, month)).fetchall()

    grades = {g["role"]: dict(g) for g in conn.execute(
        "SELECT * FROM salary_grades"
    ).fetchall()}

    created = 0
    for s in staff:
        g    = grades.get(s["role"], {})
        basic = float(g.get("basic_salary", 0))
        ot_r  = float(g.get("overtime_rate", 0))

        # Auto-pull from attendance
        att  = _get_attendance_summary(conn, s["id"], year, month)
        ot_h = att["overtime_hours"]
        abs_d = round(
            (att["absent_days"] / att["working_days"]) * basic, 2
        ) if att["working_days"] > 0 else 0.0

        gross, net = _calc_gross_net(basic, 0, ot_h, ot_r, 0, abs_d, 0)
        try:
            conn.execute("""
                INSERT INTO salaries
                  (user_id,period_year,period_month,basic_salary,overtime_hours,
                   overtime_rate,absence_deduction,gross,net,status,notes,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Draft',%s,%s)
            """, (s["id"], year, month, basic, ot_h, ot_r, abs_d, gross, net,
                  f"Auto: {att['absent_days']} absent, {ot_h}h OT",
                  session["user"]["id"]))
            created += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    flash(f"Bulk generated {created} salary records for {year}-{month:02d}.", "success")
    return redirect(url_for("payroll.salaries_list", year=year, month=month))


# ── Salary grades ─────────────────────────────────────────────────────────────

@payroll_bp.route("/grades", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def salary_grades():
    conn = db.get_db()
    if request.method == "POST":
        for role in _ROLES:
            basic = float(request.form.get(f"basic_{role}", 0))
            ot_r  = float(request.form.get(f"ot_{role}", 0))
            notes = request.form.get(f"notes_{role}", "")
            conn.execute("""
                INSERT INTO salary_grades (role, basic_salary, overtime_rate, notes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (role) DO UPDATE
                  SET basic_salary=EXCLUDED.basic_salary,
                      overtime_rate=EXCLUDED.overtime_rate,
                      notes=EXCLUDED.notes
            """, (role, basic, ot_r, notes))
        conn.commit()
        conn.close()
        flash("Salary grades saved.", "success")
        return redirect(url_for("payroll.salary_grades"))

    grades = {g["role"]: dict(g) for g in conn.execute(
        "SELECT * FROM salary_grades"
    ).fetchall()}
    conn.close()
    return render_template("payroll/salary_grades.html",
        active="payroll", grades=grades, roles=_ROLES,
    )


# ── API — attendance summary for a user/period (used by salary form JS) ───────

@payroll_bp.route("/api/attendance/<int:uid>/<int:year>/<int:month>")
@login_required
def api_attendance_summary(uid, year, month):
    conn = db.get_db()
    summary = _get_attendance_summary(conn, uid, year, month)
    conn.close()
    return jsonify(summary)


# ── API — get grade by role (used by JS autocomplete) ─────────────────────────

@payroll_bp.route("/api/grade/<role>")
@login_required
def api_grade(role):
    conn = db.get_db()
    row = conn.execute(
        "SELECT * FROM salary_grades WHERE role=%s", (role,)
    ).fetchone()
    conn.close()
    if row:
        return jsonify(dict(row))
    return jsonify({"basic_salary": 0, "overtime_rate": 0})
