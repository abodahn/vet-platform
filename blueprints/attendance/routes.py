"""
Attendance & Leave Management — Premium Animal Hospital Platform
Full HR attendance: check-in/out, shifts, leaves, balances, reports.
"""
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import date, datetime, timedelta
from . import attendance_bp
from blueprints.auth.routes import login_required
from models.database import get_db


# ── helpers ───────────────────────────────────────────────────────────────────

def _calc_hours(check_in: str, check_out: str, break_min: int = 0) -> float:
    """Return net hours worked between two HH:MM strings."""
    try:
        fmt = "%H:%M"
        ci = datetime.strptime(check_in[:5], fmt)
        co = datetime.strptime(check_out[:5], fmt)
        if co < ci:          # night shift crosses midnight
            co += timedelta(days=1)
        mins = (co - ci).seconds // 60 - break_min
        return round(max(0, mins / 60), 2)
    except Exception:
        return 0.0

def _business_days(start: str, end: str, conn) -> int:
    """Count weekdays (Sat=6, Sun=0 depending on locale) excl. public holidays."""
    holidays = {r[0] for r in conn.execute(
        "SELECT holiday_date FROM public_holidays WHERE holiday_date BETWEEN ? AND ?",
        (start, end)).fetchall()}
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    count = 0
    cur = d0
    while cur <= d1:
        if cur.weekday() < 5 and cur.isoformat() not in holidays:
            count += 1
        cur += timedelta(days=1)
    return count

def _get_or_create_balance(conn, user_id: int, lt_id: int, year: int, allocated: float) -> dict:
    row = conn.execute(
        "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
        (user_id, lt_id, year)).fetchone()
    if not row:
        conn.execute(
            """INSERT INTO leave_balances(user_id,leave_type_id,year,allocated,used,pending,remaining)
               VALUES(?,?,?,?,0,0,?)""",
            (user_id, lt_id, year, allocated, allocated))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
            (user_id, lt_id, year)).fetchone()
    return dict(row)

def _allowed_manager(user: dict) -> bool:
    return user.get("role") in ("super_admin", "clinic_owner", "branch_manager", "hr")


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@attendance_bp.route("/")
@login_required
def dashboard():
    conn   = get_db()
    today  = date.today().isoformat()
    user   = session["user"]
    year   = date.today().year

    # Today's attendance summary
    present = conn.execute(
        "SELECT COUNT(*) FROM attendance_records WHERE work_date=? AND status='Present'",
        (today,)).fetchone()[0]
    absent = conn.execute(
        "SELECT COUNT(*) FROM attendance_records WHERE work_date=? AND status='Absent'",
        (today,)).fetchone()[0]
    on_leave = conn.execute(
        """SELECT COUNT(*) FROM leave_requests
           WHERE status='Approved' AND start_date<=? AND end_date>=?""",
        (today, today)).fetchone()[0]
    total_staff = conn.execute("SELECT COUNT(*) FROM users WHERE is_active=1").fetchone()[0]
    checked_in  = conn.execute(
        "SELECT COUNT(*) FROM attendance_records WHERE work_date=? AND check_in IS NOT NULL AND check_out IS NULL",
        (today,)).fetchone()[0]

    # Today's records with user info
    today_records = conn.execute(
        """SELECT ar.*, u.full_name, u.role
           FROM attendance_records ar
           JOIN users u ON u.id = ar.user_id
           WHERE ar.work_date = ? ORDER BY ar.check_in""",
        (today,)).fetchall()

    # Pending leave requests (for managers)
    pending_leaves = []
    if _allowed_manager(user):
        pending_leaves = conn.execute(
            """SELECT lr.*, lt.name AS leave_type_name, lt.color
               FROM leave_requests lr
               JOIN leave_types lt ON lt.id = lr.leave_type_id
               WHERE lr.status = 'Pending' ORDER BY lr.created_at""").fetchall()

    # My pending leaves
    my_pending = conn.execute(
        """SELECT lr.*, lt.name AS leave_type_name, lt.color
           FROM leave_requests lr JOIN leave_types lt ON lt.id=lr.leave_type_id
           WHERE lr.user_id=? ORDER BY lr.created_at DESC LIMIT 5""",
        (user["id"],)).fetchall()

    # My leave balances this year
    my_balances = conn.execute(
        """SELECT lb.*, lt.name, lt.name_ar, lt.color, lt.is_paid
           FROM leave_balances lb JOIN leave_types lt ON lt.id=lb.leave_type_id
           WHERE lb.user_id=? AND lb.year=?""",
        (user["id"], year)).fetchall()

    conn.close()
    return render_template(
        "attendance/dashboard.html",
        active="attendance",
        today=today,
        present=present, absent=absent, on_leave=on_leave,
        total_staff=total_staff, checked_in=checked_in,
        today_records=today_records,
        pending_leaves=pending_leaves,
        my_pending=my_pending,
        my_balances=my_balances,
        is_manager=_allowed_manager(user),
        year=year,
    )


# ── CHECK-IN / CHECK-OUT ──────────────────────────────────────────────────────

@attendance_bp.route("/checkin", methods=["GET", "POST"])
@login_required
def checkin():
    conn  = get_db()
    today = date.today().isoformat()
    now   = datetime.now().strftime("%H:%M")
    user  = session["user"]

    if request.method == "POST":
        target_user_id = request.form.get("user_id", user["id"])
        action         = request.form.get("action", "checkin")
        notes          = request.form.get("notes", "")
        break_min      = int(request.form.get("break_minutes", 0) or 0)

        rec = conn.execute(
            "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
            (target_user_id, today)).fetchone()

        if action == "checkin":
            if rec:
                flash("Already checked in today.", "warning")
            else:
                u_row = conn.execute("SELECT * FROM users WHERE id=?", (target_user_id,)).fetchone()
                conn.execute(
                    """INSERT INTO attendance_records
                           (user_id,username,full_name,work_date,check_in,status,notes,recorded_by)
                       VALUES(?,?,?,?,?,'Present',?,?)""",
                    (target_user_id,
                     u_row["username"] if u_row else "",
                     u_row["full_name"] if u_row else "",
                     today, now, notes, user["username"]))
                conn.commit()
                flash("Check-in recorded successfully.", "success")

        elif action == "checkout":
            if not rec or not rec["check_in"]:
                flash("No check-in record found for today.", "error")
            elif rec["check_out"]:
                flash("Already checked out.", "warning")
            else:
                hrs = _calc_hours(rec["check_in"], now, break_min)
                conn.execute(
                    """UPDATE attendance_records
                       SET check_out=?, break_minutes=?, hours_worked=?, updated_at=datetime('now')
                       WHERE id=?""",
                    (now, break_min, hrs, rec["id"]))
                conn.commit()
                flash(f"Check-out recorded. Hours worked: {hrs:.1f}h", "success")

        conn.close()
        return redirect(url_for("attendance.checkin"))

    # GET — show today's status
    my_record = conn.execute(
        "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
        (user["id"], today)).fetchone()

    # For managers: all staff and today's records
    staff_list = []
    all_today  = []
    if _allowed_manager(user):
        staff_list = conn.execute(
            "SELECT id, full_name, username, role FROM users WHERE is_active=1 ORDER BY full_name"
        ).fetchall()
        all_today = conn.execute(
            """SELECT ar.*, u.full_name, u.role
               FROM attendance_records ar JOIN users u ON u.id=ar.user_id
               WHERE ar.work_date=? ORDER BY ar.check_in""",
            (today,)).fetchall()

    conn.close()
    return render_template(
        "attendance/checkin.html",
        active="attendance",
        today=today, now=now,
        my_record=my_record,
        staff_list=staff_list,
        all_today=all_today,
        is_manager=_allowed_manager(user),
    )


# ── ATTENDANCE RECORDS ────────────────────────────────────────────────────────

@attendance_bp.route("/records")
@login_required
def records_list():
    conn      = get_db()
    user      = session["user"]
    date_from = request.args.get("date_from", (date.today() - timedelta(days=29)).isoformat())
    date_to   = request.args.get("date_to",   date.today().isoformat())
    user_filter = request.args.get("user_id", "")
    status_f  = request.args.get("status", "")

    q = """SELECT ar.*, u.full_name, u.role
           FROM attendance_records ar JOIN users u ON u.id=ar.user_id
           WHERE ar.work_date BETWEEN ? AND ?"""
    params = [date_from, date_to]

    if not _allowed_manager(user):
        q += " AND ar.user_id=?"
        params.append(user["id"])
    elif user_filter:
        q += " AND ar.user_id=?"
        params.append(user_filter)

    if status_f:
        q += " AND ar.status=?"
        params.append(status_f)

    q += " ORDER BY ar.work_date DESC, ar.check_in"
    records = conn.execute(q, params).fetchall()

    # Summary stats
    total_days  = len(records)
    total_hours = sum(r["hours_worked"] or 0 for r in records)
    present     = sum(1 for r in records if r["status"] == "Present")
    late        = sum(1 for r in records if r["status"] == "Late")

    staff_list = conn.execute(
        "SELECT id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall() if _allowed_manager(user) else []

    conn.close()
    return render_template(
        "attendance/records_list.html",
        active="attendance",
        records=records,
        date_from=date_from, date_to=date_to,
        user_filter=user_filter, status_f=status_f,
        total_days=total_days, total_hours=total_hours,
        present=present, late=late,
        staff_list=staff_list,
        is_manager=_allowed_manager(user),
    )


@attendance_bp.route("/records/edit/<int:rec_id>", methods=["GET", "POST"])
@login_required
def record_edit(rec_id):
    conn = get_db()
    user = session["user"]
    if not _allowed_manager(user):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.records_list"))

    rec = conn.execute("SELECT * FROM attendance_records WHERE id=?", (rec_id,)).fetchone()
    if not rec:
        flash("Record not found.", "error")
        conn.close()
        return redirect(url_for("attendance.records_list"))

    if request.method == "POST":
        check_in   = request.form.get("check_in", "")
        check_out  = request.form.get("check_out", "")
        status     = request.form.get("status", "Present")
        brk        = int(request.form.get("break_minutes", 0) or 0)
        notes      = request.form.get("notes", "")
        hrs = _calc_hours(check_in, check_out, brk) if check_in and check_out else 0
        conn.execute(
            """UPDATE attendance_records
               SET check_in=?,check_out=?,status=?,break_minutes=?,hours_worked=?,
                   notes=?,updated_at=datetime('now')
               WHERE id=?""",
            (check_in or None, check_out or None, status, brk, hrs, notes, rec_id))
        conn.commit()
        conn.close()
        flash("Attendance record updated.", "success")
        return redirect(url_for("attendance.records_list"))

    u_row = conn.execute("SELECT full_name FROM users WHERE id=?", (rec["user_id"],)).fetchone()
    conn.close()
    return render_template("attendance/record_edit.html", active="attendance",
                           rec=rec, staff_name=u_row["full_name"] if u_row else "")


# ── LEAVE REQUESTS ────────────────────────────────────────────────────────────

@attendance_bp.route("/leaves")
@login_required
def leaves_list():
    conn   = get_db()
    user   = session["user"]
    status_f = request.args.get("status", "")
    user_filter = request.args.get("user_id", "")

    q = """SELECT lr.*, lt.name AS leave_type_name, lt.color,
                  u.full_name AS staff_name
           FROM leave_requests lr
           JOIN leave_types lt ON lt.id = lr.leave_type_id
           JOIN users u ON u.id = lr.user_id
           WHERE 1=1"""
    params = []
    if not _allowed_manager(user):
        q += " AND lr.user_id=?"; params.append(user["id"])
    elif user_filter:
        q += " AND lr.user_id=?"; params.append(user_filter)
    if status_f:
        q += " AND lr.status=?"; params.append(status_f)
    q += " ORDER BY lr.created_at DESC"

    leaves = conn.execute(q, params).fetchall()
    staff_list = conn.execute(
        "SELECT id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall() if _allowed_manager(user) else []
    conn.close()
    return render_template(
        "attendance/leaves_list.html",
        active="attendance",
        leaves=leaves, status_f=status_f, user_filter=user_filter,
        staff_list=staff_list, is_manager=_allowed_manager(user),
    )


@attendance_bp.route("/leaves/new", methods=["GET", "POST"])
@login_required
def leave_new():
    conn  = get_db()
    user  = session["user"]
    year  = date.today().year
    leave_types = conn.execute(
        "SELECT * FROM leave_types WHERE is_active=1 ORDER BY name").fetchall()

    if request.method == "POST":
        lt_id      = request.form.get("leave_type_id")
        start_date = request.form.get("start_date", "")
        end_date   = request.form.get("end_date", "")
        reason     = request.form.get("reason", "")

        if not lt_id or not start_date or not end_date:
            flash("Leave type, start and end dates are required.", "error")
            conn.close()
            return redirect(url_for("attendance.leave_new"))

        if end_date < start_date:
            flash("End date must be on or after start date.", "error")
            conn.close()
            return redirect(url_for("attendance.leave_new"))

        days_req = _business_days(start_date, end_date, conn)
        lt_row   = conn.execute("SELECT * FROM leave_types WHERE id=?", (lt_id,)).fetchone()

        # Check balance
        bal = conn.execute(
            "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
            (user["id"], lt_id, year)).fetchone()
        if bal and (bal["remaining"] - bal["pending"]) < days_req:
            flash(f"Insufficient balance. Available: {bal['remaining'] - bal['pending']:.1f} days.", "warning")

        conn.execute(
            """INSERT INTO leave_requests
                   (user_id,username,full_name,leave_type_id,leave_type_name,
                    start_date,end_date,days_requested,reason,status)
               VALUES(?,?,?,?,?,?,?,?,'Pending')""",
            (user["id"], user["username"], user.get("full_name",""),
             lt_id, lt_row["name"] if lt_row else "",
             start_date, end_date, days_req, reason))
        # Reserve pending balance
        if bal:
            conn.execute(
                "UPDATE leave_balances SET pending=pending+? WHERE user_id=? AND leave_type_id=? AND year=?",
                (days_req, user["id"], lt_id, year))
        conn.commit()
        conn.close()
        flash(f"Leave request submitted for {days_req} day(s). Awaiting approval.", "success")
        return redirect(url_for("attendance.leaves_list"))

    # Pre-fill balances for the form
    balances = {}
    for lt in leave_types:
        bal = conn.execute(
            "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
            (user["id"], lt["id"], year)).fetchone()
        balances[lt["id"]] = dict(bal) if bal else {"remaining": lt["days_per_year"], "pending": 0}

    conn.close()
    return render_template(
        "attendance/leave_form.html",
        active="attendance",
        leave_types=leave_types,
        balances=balances,
        today=date.today().isoformat(),
    )


@attendance_bp.route("/leaves/<int:req_id>")
@login_required
def leave_detail(req_id):
    conn  = get_db()
    user  = session["user"]
    req   = conn.execute(
        """SELECT lr.*, lt.name AS leave_type_name, lt.color, lt.is_paid, lt.days_per_year,
                  u.full_name AS staff_name, u.role AS staff_role
           FROM leave_requests lr
           JOIN leave_types lt ON lt.id=lr.leave_type_id
           JOIN users u ON u.id=lr.user_id
           WHERE lr.id=?""", (req_id,)).fetchone()
    if not req:
        flash("Request not found.", "error")
        conn.close()
        return redirect(url_for("attendance.leaves_list"))
    if req["user_id"] != user["id"] and not _allowed_manager(user):
        flash("Access denied.", "error")
        conn.close()
        return redirect(url_for("attendance.leaves_list"))
    bal = conn.execute(
        "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
        (req["user_id"], req["leave_type_id"], date.today().year)).fetchone()
    conn.close()
    return render_template(
        "attendance/leave_detail.html",
        active="attendance",
        req=req, bal=bal, is_manager=_allowed_manager(user),
    )


@attendance_bp.route("/leaves/<int:req_id>/approve", methods=["POST"])
@login_required
def leave_approve(req_id):
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.leaves_list"))
    conn  = get_db()
    user  = session["user"]
    req   = conn.execute("SELECT * FROM leave_requests WHERE id=?", (req_id,)).fetchone()
    if req and req["status"] == "Pending":
        conn.execute(
            """UPDATE leave_requests SET status='Approved', approved_by=?, approved_at=datetime('now')
               WHERE id=?""",
            (user["username"], req_id))
        # Deduct from balance
        yr = date.fromisoformat(req["start_date"]).year
        conn.execute(
            """UPDATE leave_balances
               SET used=used+?, pending=MAX(0,pending-?), remaining=MAX(0,remaining-?)
               WHERE user_id=? AND leave_type_id=? AND year=?""",
            (req["days_requested"], req["days_requested"], req["days_requested"],
             req["user_id"], req["leave_type_id"], yr))
        conn.commit()
        flash("Leave request approved.", "success")
    conn.close()
    return redirect(url_for("attendance.leave_detail", req_id=req_id))


@attendance_bp.route("/leaves/<int:req_id>/reject", methods=["POST"])
@login_required
def leave_reject(req_id):
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.leaves_list"))
    conn   = get_db()
    reason = request.form.get("rejection_reason", "")
    user   = session["user"]
    req    = conn.execute("SELECT * FROM leave_requests WHERE id=?", (req_id,)).fetchone()
    if req and req["status"] == "Pending":
        conn.execute(
            """UPDATE leave_requests SET status='Rejected', approved_by=?,
               approved_at=datetime('now'), rejection_reason=? WHERE id=?""",
            (user["username"], reason, req_id))
        # Release pending
        yr = date.fromisoformat(req["start_date"]).year
        conn.execute(
            """UPDATE leave_balances SET pending=MAX(0,pending-?)
               WHERE user_id=? AND leave_type_id=? AND year=?""",
            (req["days_requested"], req["user_id"], req["leave_type_id"], yr))
        conn.commit()
        flash("Leave request rejected.", "info")
    conn.close()
    return redirect(url_for("attendance.leave_detail", req_id=req_id))


# ── SHIFTS ────────────────────────────────────────────────────────────────────

@attendance_bp.route("/shifts")
@login_required
def shifts_list():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.dashboard"))
    conn = get_db()
    shifts = conn.execute("SELECT * FROM shifts ORDER BY name").fetchall()
    conn.close()
    return render_template("attendance/shifts.html", active="attendance", shifts=shifts)


@attendance_bp.route("/shifts/save", methods=["POST"])
@login_required
def shift_save():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.dashboard"))
    conn       = get_db()
    shift_id   = request.form.get("shift_id")
    name       = request.form.get("name", "").strip()
    start_time = request.form.get("start_time", "08:00")
    end_time   = request.form.get("end_time",   "17:00")
    break_min  = int(request.form.get("break_minutes", 60) or 60)
    days       = ",".join(request.form.getlist("days_of_week") or ["1","2","3","4","5"])
    color      = request.form.get("color", "#3b82f6")
    is_active  = 1 if request.form.get("is_active") else 0
    if not name:
        flash("Shift name required.", "error")
        conn.close()
        return redirect(url_for("attendance.shifts_list"))
    if shift_id:
        conn.execute(
            "UPDATE shifts SET name=?,start_time=?,end_time=?,break_minutes=?,days_of_week=?,color=?,is_active=? WHERE id=?",
            (name, start_time, end_time, break_min, days, color, is_active, shift_id))
        flash("Shift updated.", "success")
    else:
        conn.execute(
            "INSERT INTO shifts(name,start_time,end_time,break_minutes,days_of_week,color,is_active) VALUES(?,?,?,?,?,?,?)",
            (name, start_time, end_time, break_min, days, color, is_active))
        flash("Shift added.", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("attendance.shifts_list"))


# ── LEAVE TYPES ───────────────────────────────────────────────────────────────

@attendance_bp.route("/leave-types")
@login_required
def leave_types():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.dashboard"))
    conn = get_db()
    types = conn.execute("SELECT * FROM leave_types ORDER BY name").fetchall()
    conn.close()
    return render_template("attendance/leave_types.html", active="attendance", leave_types=types)


@attendance_bp.route("/leave-types/save", methods=["POST"])
@login_required
def leave_type_save():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.dashboard"))
    conn    = get_db()
    lt_id   = request.form.get("lt_id")
    name    = request.form.get("name", "").strip()
    name_ar = request.form.get("name_ar", "").strip()
    days    = float(request.form.get("days_per_year", 21) or 21)
    is_paid = 1 if request.form.get("is_paid") else 0
    color   = request.form.get("color", "#6366f1")
    is_act  = 1 if request.form.get("is_active") else 0
    if not name:
        flash("Leave type name required.", "error")
        conn.close()
        return redirect(url_for("attendance.leave_types"))
    if lt_id:
        conn.execute(
            "UPDATE leave_types SET name=?,name_ar=?,days_per_year=?,is_paid=?,color=?,is_active=? WHERE id=?",
            (name, name_ar, days, is_paid, color, is_act, lt_id))
        flash("Leave type updated.", "success")
    else:
        conn.execute(
            "INSERT INTO leave_types(name,name_ar,days_per_year,is_paid,color,is_active) VALUES(?,?,?,?,?,?)",
            (name, name_ar, days, is_paid, color, is_act))
        flash("Leave type added.", "success")
    conn.commit()
    conn.close()
    return redirect(url_for("attendance.leave_types"))


# ── BALANCES ─────────────────────────────────────────────────────────────────

@attendance_bp.route("/balances")
@login_required
def balances():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.dashboard"))
    conn  = get_db()
    year  = int(request.args.get("year", date.today().year))
    users = conn.execute("SELECT id, full_name, role FROM users WHERE is_active=1 ORDER BY full_name").fetchall()
    ltypes = conn.execute("SELECT * FROM leave_types WHERE is_active=1 ORDER BY name").fetchall()

    # Build matrix: user → {lt_id: balance_row}
    matrix = {}
    for u in users:
        matrix[u["id"]] = {}
        for lt in ltypes:
            bal = conn.execute(
                "SELECT * FROM leave_balances WHERE user_id=? AND leave_type_id=? AND year=?",
                (u["id"], lt["id"], year)).fetchone()
            matrix[u["id"]][lt["id"]] = dict(bal) if bal else None

    conn.close()
    return render_template(
        "attendance/balances.html",
        active="attendance",
        users=users, ltypes=ltypes, matrix=matrix, year=year,
    )


@attendance_bp.route("/balances/set", methods=["POST"])
@login_required
def balance_set():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.balances"))
    conn    = get_db()
    user_id = request.form.get("user_id")
    lt_id   = request.form.get("leave_type_id")
    year    = int(request.form.get("year", date.today().year))
    alloc   = float(request.form.get("allocated", 0) or 0)
    used    = float(request.form.get("used", 0) or 0)
    pending = float(request.form.get("pending", 0) or 0)
    remaining = max(0, alloc - used - pending)
    conn.execute(
        """INSERT OR REPLACE INTO leave_balances
               (user_id,leave_type_id,year,allocated,used,pending,remaining)
           VALUES(?,?,?,?,?,?,?)""",
        (user_id, lt_id, year, alloc, used, pending, remaining))
    conn.commit()
    conn.close()
    flash("Balance updated.", "success")
    return redirect(url_for("attendance.balances", year=year))


# ── REPORT ────────────────────────────────────────────────────────────────────

@attendance_bp.route("/report")
@login_required
def report():
    conn   = get_db()
    user   = session["user"]
    year   = int(request.args.get("year",  date.today().year))
    month  = int(request.args.get("month", date.today().month))
    uid    = request.args.get("user_id", "" if _allowed_manager(user) else str(user["id"]))

    month_start = date(year, month, 1).isoformat()
    if month == 12:
        month_end = date(year, 12, 31).isoformat()
    else:
        month_end = (date(year, month + 1, 1) - timedelta(days=1)).isoformat()

    q = """SELECT ar.*, u.full_name, u.role
           FROM attendance_records ar JOIN users u ON u.id=ar.user_id
           WHERE ar.work_date BETWEEN ? AND ?"""
    params = [month_start, month_end]
    if uid:
        q += " AND ar.user_id=?"; params.append(uid)
    q += " ORDER BY u.full_name, ar.work_date"
    records = conn.execute(q, params).fetchall()

    # Per-user summary
    summary: dict = {}
    for r in records:
        uid_r = r["user_id"]
        if uid_r not in summary:
            summary[uid_r] = {
                "full_name": r["full_name"], "role": r["role"],
                "present": 0, "absent": 0, "late": 0, "leave": 0,
                "total_hours": 0.0,
            }
        s = summary[uid_r]
        st = r["status"] or "Present"
        if st == "Present":  s["present"]     += 1
        elif st == "Absent": s["absent"]      += 1
        elif st == "Late":   s["late"]        += 1
        elif st == "Leave":  s["leave"]       += 1
        s["total_hours"] += r["hours_worked"] or 0

    # Leave requests in range
    leave_q = """SELECT lr.*, lt.name AS leave_type_name, lt.color, u.full_name AS staff_name
                 FROM leave_requests lr
                 JOIN leave_types lt ON lt.id=lr.leave_type_id
                 JOIN users u ON u.id=lr.user_id
                 WHERE lr.status='Approved' AND lr.start_date<=? AND lr.end_date>=?"""
    lparams = [month_end, month_start]
    if uid:
        leave_q += " AND lr.user_id=?"; lparams.append(uid)
    approved_leaves = conn.execute(leave_q, lparams).fetchall()

    staff_list = conn.execute(
        "SELECT id, full_name FROM users WHERE is_active=1 ORDER BY full_name"
    ).fetchall() if _allowed_manager(user) else []

    conn.close()
    return render_template(
        "attendance/report.html",
        active="attendance",
        records=records, summary=summary,
        approved_leaves=approved_leaves,
        year=year, month=month,
        month_start=month_start, month_end=month_end,
        staff_list=staff_list,
        selected_uid=uid,
        month_name=date(year, month, 1).strftime("%B"),
        is_manager=_allowed_manager(user),
    )


# ── PUBLIC HOLIDAYS ───────────────────────────────────────────────────────────

@attendance_bp.route("/holidays")
@login_required
def holidays():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.dashboard"))
    conn = get_db()
    year = int(request.args.get("year", date.today().year))
    holidays_list = conn.execute(
        "SELECT * FROM public_holidays WHERE strftime('%Y',holiday_date)=? ORDER BY holiday_date",
        (str(year),)).fetchall()
    conn.close()
    return render_template("attendance/holidays.html", active="attendance",
                           holidays=holidays_list, year=year)


@attendance_bp.route("/holidays/save", methods=["POST"])
@login_required
def holiday_save():
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.holidays"))
    conn = get_db()
    hid  = request.form.get("holiday_id")
    name = request.form.get("name", "").strip()
    hdate = request.form.get("holiday_date", "")
    name_ar = request.form.get("name_ar", "").strip()
    if not name or not hdate:
        flash("Name and date required.", "error")
        conn.close()
        return redirect(url_for("attendance.holidays"))
    if hid:
        conn.execute("UPDATE public_holidays SET name=?,name_ar=?,holiday_date=? WHERE id=?",
                     (name, name_ar, hdate, hid))
    else:
        conn.execute("INSERT OR IGNORE INTO public_holidays(name,name_ar,holiday_date) VALUES(?,?,?)",
                     (name, name_ar, hdate))
    conn.commit()
    conn.close()
    flash("Holiday saved.", "success")
    return redirect(url_for("attendance.holidays", year=hdate[:4]))


@attendance_bp.route("/holidays/<int:hid>/delete", methods=["POST"])
@login_required
def holiday_delete(hid):
    if not _allowed_manager(session["user"]):
        flash("Access denied.", "error")
        return redirect(url_for("attendance.holidays"))
    conn = get_db()
    conn.execute("DELETE FROM public_holidays WHERE id=?", (hid,))
    conn.commit()
    conn.close()
    flash("Holiday removed.", "success")
    return redirect(url_for("attendance.holidays"))


# ── JSON API ──────────────────────────────────────────────────────────────────

@attendance_bp.route("/api/today")
@login_required
def api_today():
    conn  = get_db()
    today = date.today().isoformat()
    rows  = conn.execute(
        """SELECT ar.user_id, ar.check_in, ar.check_out, ar.status, ar.hours_worked,
                  u.full_name
           FROM attendance_records ar JOIN users u ON u.id=ar.user_id
           WHERE ar.work_date=?""", (today,)).fetchall()
    conn.close()
    return jsonify({"date": today, "records": [dict(r) for r in rows]})
