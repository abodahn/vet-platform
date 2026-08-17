"""
Attendance & Leave Management — Aleefy Platform
Full HR attendance: check-in/out, shifts, leaves, balances, reports.
"""
from flask import render_template, request, redirect, url_for, flash, session, jsonify, send_file
import os
from datetime import date, datetime, timedelta
from . import attendance_bp
from blueprints.auth.routes import login_required
from blueprints.hr.routes import can_view_staff
from models.database import get_db
from models import money
from models import concurrency
from models.excel_export import make_workbook


# ── helpers ───────────────────────────────────────────────────────────────────

def hhmm(value) -> str:
    """The clock time out of whatever shape the column happens to hold.

    Two formats live in this column. The app writes "HH:MM" at check-in;
    imported and seeded records carry a full timestamp,
    "2026-08-12 09:27:00". Every helper here used to do `str(value)[:5]`,
    which on the second form yields "2026-" — so _minutes returned 0 and
    _calc_hours returned 0.0 for EVERY such record.

    That was not theoretical. On the live demo 980 of 1078 records are stored
    that way, and the consequences ran through the whole module: lateness
    compared against minute zero so nobody could ever be Late; the nightly
    auto-close computed zero hours and paid nothing; and the edit screen bound
    the raw value into <input type="time">, which rejects it and renders EMPTY —
    so opening a record showed blank times and saving wrote hours_worked = 0.
    That last one is the "editing any attendance record wipes the times and
    zeroes the hours" report, and the format is the whole of it.

    Returns "" for anything with no recognisable time, so callers keep their
    existing "falsy means no time recorded" behaviour.
    """
    s = str(value or "").strip()
    if not s:
        return ""
    # "2026-08-12 09:27:00" / "2026-08-12T09:27" -> the part after the date.
    if len(s) > 8 and (" " in s or "T" in s):
        s = s.replace("T", " ").split(" ", 1)[1].strip()
    parts = s.split(":")
    if len(parts) < 2:
        return ""
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return ""
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return ""
    return "%02d:%02d" % (h, m)


def _calc_hours(check_in: str, check_out: str, break_min: int = 0,
                overnight: bool = False) -> float:
    """Net hours between two HH:MM strings. Returns 0.0 on anything unusable.

    `overnight` must be passed for a shift that genuinely crosses midnight.
    This used to wrap WHENEVER check_out < check_in, on the assumption that it
    meant a night shift. It also means a typo: a manager correcting 09:00-17:00
    to 09:00-07:00 produced 21.98 hours, which payroll then paid fourteen hours
    of overtime on. A day shift cannot end before it starts, so on a day shift
    that ordering is an error and is reported as one rather than guessed at.
    """
    ci_s, co_s = hhmm(check_in), hhmm(check_out)
    if not ci_s or not co_s:
        return 0.0
    try:
        fmt = "%H:%M"
        ci = datetime.strptime(ci_s, fmt)
        co = datetime.strptime(co_s, fmt)
    except ValueError:
        return 0.0
    if co < ci:
        if not overnight:
            return 0.0
        co += timedelta(days=1)
    mins = int((co - ci).total_seconds() // 60) - int(break_min or 0)
    return round(max(0, mins / 60), 2)


def default_shift(conn, user_id: int = None, on_date: str = None):
    """The working day THIS employee is judged against.

    It used to take no user at all — "shifts are clinic-wide" — and return
    `ORDER BY id LIMIT 1`, which on a seeded database is Morning 08:00. So the
    night nurse who clocks in at 22:00 was measured against an 08:00 start and
    marked Late by fourteen hours, every night; and close_forgotten_checkouts,
    which closes an open record at "the shift end", closed her 22:00 record at
    16:00 — a check-out BEFORE the check-in, paying roughly an hour for an
    eight-hour night.

    staff_shifts already maps employee to shift and is written by HR's roster
    screen; nothing in attendance consulted it. Where an employee is unrostered
    the clinic-wide first shift is still the only available answer, so that
    remains the fallback rather than an error.
    """
    row = None
    on_date = on_date or date.today().isoformat()
    if user_id:
        try:
            row = conn.execute(
                "SELECT sh.start_time, sh.end_time, sh.break_minutes"
                " FROM staff_shifts ss JOIN shifts sh ON sh.id = ss.shift_id"
                " WHERE ss.user_id=? AND ss.effective_from <= ?"
                "   AND (ss.effective_to IS NULL OR ss.effective_to >= ?)"
                " ORDER BY ss.effective_from DESC LIMIT 1",
                (user_id, on_date, on_date)).fetchone()
        except Exception:
            row = None
    if not row:
        try:
            row = conn.execute(
                "SELECT start_time, end_time, break_minutes FROM shifts "
                "WHERE is_active=1 ORDER BY id LIMIT 1").fetchone()
        except Exception:
            row = None
    if not row:
        return {"start_time": "08:00", "end_time": "17:00", "break_minutes": 60}
    return {"start_time": (row["start_time"] or "08:00")[:5],
            "end_time": (row["end_time"] or "17:00")[:5],
            "break_minutes": int(row["break_minutes"] or 0)}


def shift_crosses_midnight(shift) -> bool:
    """True for a night shift, e.g. 22:00-06:00."""
    return _minutes(shift["end_time"]) <= _minutes(shift["start_time"])


# Minutes after the shift start that still count as on time. Traffic in Cairo
# makes a zero-tolerance clock a source of arguments rather than information.
LATE_GRACE_MINUTES = int(os.environ.get("ATTENDANCE_GRACE_MINUTES", "15"))


def _minutes(value) -> int:
    """Minutes past midnight. Accepts either stored format — see hhmm()."""
    s = hhmm(value)
    if not s:
        return 0
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def status_for_checkin(conn, check_in: str, user_id: int = None) -> tuple:
    """('Present'|'Late', minutes_late) for an arrival time.

    The 'Late' status has existed in this schema from the start and NOTHING
    EVER SET IT — the dashboard counted late days and the count was always
    zero. A status only ever counted and never assigned is a report that lies
    quietly, which is worse than not having the column.

    Measured against the employee's OWN shift. Against the clinic-wide first
    shift, every evening and night worker was permanently Late — which is not a
    cosmetic label: payroll counts late days, and a record that reads Late all
    month is the one a manager docks.
    """
    shift = default_shift(conn, user_id)
    late_by = _minutes(check_in) - _minutes(shift["start_time"]) - LATE_GRACE_MINUTES
    # A night shift starting at 22:00 wraps: clocking in at 00:10 is ten past
    # midnight on a shift that began two hours ago, not fourteen hours early.
    if shift_crosses_midnight(shift) and late_by < -12 * 60:
        late_by += 24 * 60
    if late_by > 0:
        return "Late", late_by
    return "Present", 0


def close_forgotten_checkouts(conn, on_date: str = None) -> int:
    """Close attendance records left open, and return how many.

    THE BUG THIS FIXES COSTS STAFF THEIR PAY. hours_worked is only ever written
    at check-out; nothing else sets it. So an employee who works a full day and
    forgets to clock out has hours_worked = 0, and payroll — which reads exactly
    that column — pays them for nothing. The dashboard counted open records and
    no code acted on the count.

    Closes at the shift end rather than at "now", because a record found open at
    03:00 the next morning did not represent someone working through the night.

    Deliberately NOT silent. Every row it touches is stamped recorded_by='system'
    and says so in its notes, so a manager reviewing the month can see which
    hours were reconstructed rather than observed. Paying an estimate is fairer
    than paying zero; paying an estimate nobody can identify afterwards is not.
    """
    on_date = on_date or (date.today() - timedelta(days=1)).isoformat()
    rows = conn.execute(
        "SELECT id, user_id, check_in, break_minutes FROM attendance_records "
        "WHERE work_date=? AND check_in IS NOT NULL AND check_in <> '' "
        "  AND (check_out IS NULL OR check_out = '')", (on_date,)).fetchall()

    closed = 0
    for r in rows:
        # Each record closes at ITS OWN shift's end. One clinic-wide shift meant
        # a 22:00 night record was closed at 16:00 — an end before the start —
        # and the guard below then collapsed it to zero hours. An eight-hour
        # night was paid as nothing, every night.
        shift = default_shift(conn, r["user_id"], on_date)
        brk = int(r["break_minutes"] or shift["break_minutes"] or 0)
        end = shift["end_time"]
        # Someone who arrived after the shift ended gets their arrival time, so
        # the record closes with zero hours rather than a negative day.
        #
        # NOT for a shift that crosses midnight: on a 22:00-06:00 night the
        # check-in is ALWAYS "after" the end by clock arithmetic, so this guard
        # fired on every single night record, rewrote the end to 22:00 and paid
        # zero for an eight-hour shift. There the wrap is the correct reading.
        if not shift_crosses_midnight(shift) and _minutes(r["check_in"]) > _minutes(end):
            end = r["check_in"]
        hrs = _calc_hours(r["check_in"], end, brk, overnight=shift_crosses_midnight(shift))
        conn.execute(
            "UPDATE attendance_records "
            "SET check_out=?, hours_worked=?, break_minutes=?, "
            "    recorded_by='system', "
            "    notes = TRIM(COALESCE(notes,'') || ?), "
            "    updated_at=datetime('now','localtime') "
            "WHERE id=?",
            (end, hrs, brk,
             f" [auto-closed at shift end {end}; no check-out was recorded]",
             r["id"]))
        closed += 1
    if closed:
        conn.commit()
    return closed

# The Egyptian working week: Sunday to Thursday, weekend Friday and Saturday.
#
# Encoded the way the Shifts screen encodes it — Sun=0, Mon=1 … Sat=6.
_DEFAULT_WORK_DAYS = frozenset({0, 1, 2, 3, 4})


def _day_number(value) -> int:
    """One weekday from days_of_week, normalised to Sun=0 … Sat=6.

    Two conventions are already in the database and they disagree about Sunday.
    The Shifts form writes it as 0 (its checkbox list ends with (0,'Sun')), and
    the seeded shifts write it as 7 ("Weekend Morning" is stored "6,7", meaning
    Saturday and Sunday). % 7 folds 7 onto 0 so both read the same, which is
    also why a stored "7" must never be compared directly against weekday().
    """
    return int(value) % 7


def working_weekdays(conn, user_id: int = None) -> frozenset:
    """Which days of the week this employee — or this clinic — actually works.

    shifts.days_of_week has been in the schema from the beginning, is saved by
    the Shifts screen and rendered back on it, and was READ BY NOTHING. Every
    calculation instead hardcoded `weekday() < 5`, i.e. Monday to Friday, which
    is wrong in the one country this product is sold in: Friday was counted as
    a working day, so every employee was marked absent on their day off and
    docked for it about four times a month, while Sunday — a normal working day
    in Egypt — never counted at all.
    """
    row = None
    if user_id:
        row = conn.execute(
            "SELECT sh.days_of_week FROM staff_shifts ss"
            " JOIN shifts sh ON sh.id = ss.shift_id"
            " WHERE ss.user_id=? AND (ss.effective_to IS NULL OR ss.effective_to >= ?)"
            " ORDER BY ss.effective_from DESC LIMIT 1",
            (user_id, date.today().isoformat())).fetchone()
    if not row:
        row = conn.execute(
            "SELECT days_of_week FROM shifts WHERE is_active=1"
            " ORDER BY id LIMIT 1").fetchone()

    raw = (row["days_of_week"] if row else "") or ""
    days = set()
    for part in str(raw).split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            days.add(_day_number(part))
    # An empty or unparseable setting means nobody has chosen one, not that the
    # clinic never opens.
    return frozenset(days) if days else _DEFAULT_WORK_DAYS


def _business_days(start: str, end: str, conn, user_id: int = None) -> int:
    """Working days between two dates, excluding public holidays.

    Counts against the clinic's real week (see working_weekdays), not a
    hardcoded Monday-to-Friday.
    """
    holidays = {r[0] for r in conn.execute(
        "SELECT holiday_date FROM public_holidays WHERE holiday_date BETWEEN ? AND ?",
        (start, end)).fetchall()}
    work = working_weekdays(conn, user_id)
    d0 = date.fromisoformat(start)
    d1 = date.fromisoformat(end)
    count = 0
    cur = d0
    while cur <= d1:
        # isoweekday() is Mon=1 … Sun=7; % 7 puts Sunday at 0 to match the
        # Shifts screen's own numbering.
        if (cur.isoweekday() % 7) in work and cur.isoformat() not in holidays:
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
        # Only a manager may record attendance for someone else. The GET only
        # renders the staff picker for managers, but the POST honoured any
        # user_id sent — so any employee could fabricate a colleague's hours,
        # and hours_worked is what payroll pays overtime on.
        if str(target_user_id) != str(user["id"]) and not _allowed_manager(user):
            conn.close()
            flash("Access denied.", "error")
            return redirect(url_for("attendance.checkin"))
        action         = request.form.get("action", "checkin")
        notes          = request.form.get("notes", "")
        # The unpaid break defaults to the SHIFT'S break, not to zero.
        #
        # Nobody types this box, so it was always 0: an 08:00-16:00 day stored
        # hours_worked = 8.0 while payroll's standard_hours subtracted the
        # shift's 60-minute break to get 7.0 — and paid the difference as an
        # hour of overtime. Every hand-clocked day, roughly 22 hours a month per
        # employee, invented by the two sides disagreeing about lunch.
        _shift_now = default_shift(conn, target_user_id, today)
        _raw_break = request.form.get("break_minutes")
        break_min  = (int(_raw_break) if str(_raw_break or "").strip().isdigit()
                      else int(_shift_now["break_minutes"] or 0))

        rec = conn.execute(
            "SELECT * FROM attendance_records WHERE user_id=? AND work_date=?",
            (target_user_id, today)).fetchone()

        if action == "checkin":
            if rec:
                flash("Already checked in today.", "warning")
            else:
                u_row = conn.execute("SELECT * FROM users WHERE id=?", (target_user_id,)).fetchone()
                st, late_by = status_for_checkin(conn, now, target_user_id)
                conn.execute(
                    """INSERT INTO attendance_records
                           (user_id,username,full_name,work_date,check_in,status,notes,recorded_by)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (target_user_id,
                     u_row["username"] if u_row else "",
                     u_row["full_name"] if u_row else "",
                     today, now, st, notes, user["username"]))
                conn.commit()
                if st == "Late":
                    # Said plainly at the moment it happens. Discovering it in a
                    # payroll deduction at the end of the month is how a system
                    # loses the staff's trust.
                    flash(f"Checked in at {now} — {late_by} minutes after the "
                          f"shift start (grace {LATE_GRACE_MINUTES} min).", "warning")
                else:
                    flash("Check-in recorded successfully.", "success")

        elif action == "checkout":
            if not rec or not rec["check_in"]:
                flash("No check-in record found for today.", "error")
            elif rec["check_out"]:
                flash("Already checked out.", "warning")
            else:
                hrs = _calc_hours(rec["check_in"], now, break_min,
                                  overnight=shift_crosses_midnight(_shift_now))
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
        can_view_staff=can_view_staff(user),
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
        # Two managers correcting the same day's hours is the collision that
        # costs money: last-write-wins turns one of the two corrections into
        # nothing, and nobody can tell afterwards which one survived.
        try:
            concurrency.guard(conn, "attendance_records", rec_id,
                              request.form.get("_seen_updated_at"))
        except concurrency.StaleRecord as clash:
            conn.close()
            flash(str(clash), "danger")
            return redirect(url_for("attendance.record_edit", rec_id=rec_id))

        shift = default_shift(conn, rec["user_id"], rec["work_date"])
        overnight = shift_crosses_midnight(shift)

        # A day shift cannot end before it starts. This used to be read as a
        # night shift and wrapped, so correcting 17:00 to 07:00 by mistake wrote
        # 21.98 hours and payroll paid fourteen hours of overtime on it. Refuse
        # and say why, rather than store a number nobody typed.
        if check_in and check_out and not overnight \
                and _minutes(check_out) < _minutes(check_in):
            conn.close()
            flash("Check-out is before check-in. This employee is not on a "
                  "night shift, so one of the two times is wrong.", "error")
            return redirect(url_for("attendance.record_edit", rec_id=rec_id))

        hrs = (_calc_hours(check_in, check_out, brk, overnight=overnight)
               if check_in and check_out else 0)
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

    u_row = conn.execute("SELECT id, full_name FROM users WHERE id=?",
                         (rec["user_id"],)).fetchone()
    # The shift this record belongs to: the assignment in force on the work
    # date. Attendance carries no shift_id, so it is resolved through
    # staff_shifts — and is legitimately absent for unrostered staff.
    shift = conn.execute("""
        SELECT sh.id, sh.name, sh.start_time, sh.end_time
        FROM staff_shifts ss JOIN shifts sh ON sh.id = ss.shift_id
        WHERE ss.user_id = ? AND ss.effective_from <= ?
          AND (ss.effective_to IS NULL OR ss.effective_to >= ?)
        ORDER BY ss.effective_from DESC LIMIT 1
    """, (rec["user_id"], rec["work_date"], rec["work_date"])).fetchone()
    conn.close()
    # <input type="time"> only accepts HH:MM. Bound to a full timestamp it
    # silently renders EMPTY, so opening a seeded or imported record showed
    # blank times and saving them back wrote hours_worked = 0 — the record
    # looked wiped by the act of opening it.
    return render_template("attendance/record_edit.html", active="attendance",
                           rec=rec, staff=u_row, shift=shift,
                           check_in_hhmm=hhmm(rec["check_in"]),
                           check_out_hhmm=hhmm(rec["check_out"]),
                           staff_name=u_row["full_name"] if u_row else "",
                           can_view_staff=can_view_staff(user))


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
        can_view_staff=can_view_staff(user),
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

        # Against THIS employee's week: a night nurse rostered across the
        # weekend does not get the same day count as the day desk.
        days_req = _business_days(start_date, end_date, conn, user["id"])
        lt_row   = conn.execute("SELECT * FROM leave_types WHERE id=?", (lt_id,)).fetchone()

        # The year the leave is TAKEN in, not the year it is booked in.
        #
        # This reserved against date.today().year while approve and reject both
        # settle against start_date's year. A request made in December for
        # January reserved days on this year's row and then deducted from next
        # year's — which usually does not exist, so approving it deducted
        # nothing at all and the reservation sat on the old row forever,
        # permanently eating an allowance nobody could get back.
        book_year = date.fromisoformat(start_date).year

        # Create the row if this leave type has never been used before.
        # _get_or_create_balance has existed all along and was called by NOTHING,
        # so any type without a pre-existing row was completely untracked: the
        # form advertised the full days_per_year allowance, the reservation was
        # skipped, approval deducted nothing, and an employee could take the
        # same three weeks every year forever.
        bal = _get_or_create_balance(
            conn, user["id"], lt_id, book_year,
            float(lt_row["days_per_year"] or 0) if lt_row else 0.0)

        available = float(bal["remaining"] or 0) - float(bal["pending"] or 0)
        if available < days_req:
            flash(f"Insufficient balance. Available: {available:.1f} days.", "warning")

        conn.execute(
            """INSERT INTO leave_requests
                   (user_id,username,full_name,leave_type_id,leave_type_name,
                    start_date,end_date,days_requested,reason,status)
               VALUES(?,?,?,?,?,?,?,?,?,'Pending')""",
            (user["id"], user["username"], user.get("full_name",""),
             lt_id, lt_row["name"] if lt_row else "",
             start_date, end_date, days_req, reason))
        # Reserve against the year the leave falls in, so approve and reject —
        # which both use the request's start year — settle the same row.
        conn.execute(
            "UPDATE leave_balances SET pending=pending+? WHERE user_id=? AND leave_type_id=? AND year=?",
            (days_req, user["id"], lt_id, book_year))
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
    # leave_requests.approved_by holds a username, not a user id, so the
    # approver has to be looked up. Still-pending requests have none.
    approver = None
    if req["approved_by"]:
        approver = conn.execute(
            "SELECT id, full_name FROM users WHERE username=?",
            (req["approved_by"],)).fetchone()
    conn.close()
    return render_template(
        "attendance/leave_detail.html",
        active="attendance",
        req=req, bal=bal, approver=approver,
        is_manager=_allowed_manager(user),
        can_view_staff=can_view_staff(user),
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
        # Deduct from the balance for the year the leave is taken in.
        #
        # The row is created if absent. A bare UPDATE here silently did nothing
        # for any leave type that had no row — which was every type nobody had
        # ever hand-seeded — so approving leave deducted nothing and the
        # allowance never moved.
        yr = date.fromisoformat(req["start_date"]).year
        lt = conn.execute("SELECT days_per_year FROM leave_types WHERE id=?",
                          (req["leave_type_id"],)).fetchone()
        _get_or_create_balance(conn, req["user_id"], req["leave_type_id"], yr,
                               float(lt["days_per_year"] or 0) if lt else 0.0)
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
    # Who is on each shift today — one query, grouped in Python rather than a
    # lookup per shift row.
    roster = {}
    for r in conn.execute("""
        SELECT ss.shift_id, u.id, u.full_name, u.role
        FROM staff_shifts ss JOIN users u ON u.id = ss.user_id
        WHERE u.is_active = 1 AND ss.effective_from <= ?
          AND (ss.effective_to IS NULL OR ss.effective_to >= ?)
        ORDER BY u.full_name
    """, (date.today().isoformat(), date.today().isoformat())).fetchall():
        roster.setdefault(r["shift_id"], []).append(dict(r))
    conn.close()
    return render_template("attendance/shifts.html", active="attendance",
                           shifts=shifts, roster=roster,
                           can_view_staff=can_view_staff(session["user"]))


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
    # Sun-Thu when nothing was ticked, matching _DEFAULT_WORK_DAYS. A shift
    # saved with no days used to fall back to Mon-Fri.
    days = ",".join(request.form.getlist("days_of_week")
                    or [str(d) for d in sorted(_DEFAULT_WORK_DAYS)])
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
    days, _    = money.form_amount(request.form.get("days_per_year") or 21, "days per year")
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
    alloc, _   = money.form_amount(request.form.get("allocated"), "allocated days")
    used, _    = money.form_amount(request.form.get("used"), "used days")
    pending, _ = money.form_amount(request.form.get("pending"), "pending days")

    # remaining = allocated - used. NOT minus pending.
    #
    # Every other place treats `remaining` that way: leave_approve does
    # `remaining = remaining - days` while ALSO clearing the same days from
    # pending, and leave_new reads availability as `remaining - pending`. This
    # screen alone subtracted pending a second time, so a manager opening
    # Balances and pressing Save without changing anything wrote a remaining
    # that was short by the pending days. It is not visible immediately and it
    # does not compound — but when that pending request is approved, its days
    # come off `remaining` again, and the employee is permanently down twice
    # what they took.
    remaining = max(0, alloc - used)
    # Explicit ON CONFLICT ... DO UPDATE, not INSERT OR REPLACE.
    #
    # _fix_sql turns "INSERT OR REPLACE" into "ON CONFLICT DO NOTHING", which is
    # the OPPOSITE instruction: on PostgreSQL, editing a balance that already
    # existed kept the old row and the screen still said "Balance updated." The
    # manager saw a success message and nothing changed.
    #
    # This spelling needs no translation -- SQLite has supported it since 3.24
    # and it means the same thing on both engines.
    conn.execute(
        """INSERT INTO leave_balances
               (user_id,leave_type_id,year,allocated,used,pending,remaining)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(user_id,leave_type_id,year) DO UPDATE SET
               allocated=excluded.allocated, used=excluded.used,
               pending=excluded.pending,     remaining=excluded.remaining""",
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
    # Non-managers only ever see themselves — an explicit ?user_id= must not
    # widen that, the same rule records_list already enforces.
    uid    = (request.args.get("user_id", "") if _allowed_manager(user)
              else str(user["id"]))

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
    # substr, not EXTRACT. The previous comment here claimed EXTRACT was "the
    # portable spelling" and it is not: holiday_date is a TEXT column, and
    # PostgreSQL's EXTRACT takes a date/timestamp, so this raised
    # "function pg_catalog.extract(unknown, text) does not exist" -- the exact
    # failure the comment said it was avoiding, just on the other engine.
    # substr() is native to BOTH engines and treats the column as what it
    # actually is, so no translation is involved at all. Dates are stored
    # ISO-first, so the leading four characters are the year.
    holidays_list = conn.execute(
        "SELECT * FROM public_holidays WHERE substr(holiday_date,1,4)=? "
        "ORDER BY holiday_date",
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


# ── EXCEL EXPORT ─────────────────────────────────────────────────────────────

@attendance_bp.route("/export/xlsx")
@login_required
def export_xlsx():
    conn      = get_db()
    user      = session["user"]
    date_from = request.args.get("date_from", (date.today() - timedelta(days=29)).isoformat())
    date_to   = request.args.get("date_to",   date.today().isoformat())
    uid       = request.args.get("user_id", "")

    q = """SELECT ar.work_date, u.full_name, u.role, ar.check_in, ar.check_out,
                  ar.break_minutes, ar.hours_worked, ar.status, ar.notes
           FROM attendance_records ar JOIN users u ON u.id=ar.user_id
           WHERE ar.work_date BETWEEN ? AND ?"""
    params = [date_from, date_to]
    if not _allowed_manager(user):
        q += " AND ar.user_id=?"; params.append(user["id"])
    elif uid:
        q += " AND ar.user_id=?"; params.append(uid)
    q += " ORDER BY ar.work_date DESC, u.full_name"

    rows_raw = conn.execute(q, params).fetchall()
    conn.close()

    headers = ["Date", "Staff Name", "Role", "Check-In", "Check-Out",
               "Break (min)", "Hours Worked", "Status", "Notes"]
    rows = [
        [r["work_date"], r["full_name"], r["role"],
         str(r["check_in"] or ""), str(r["check_out"] or ""),
         r["break_minutes"] or 0, round(float(r["hours_worked"] or 0), 2),
         r["status"] or "", r["notes"] or ""]
        for r in rows_raw
    ]
    try:
        buf = make_workbook(
            title=f"Attendance {date_from} to {date_to}",
            headers=headers, rows=rows, sheet_name="Attendance",
        )
        fname = f"attendance_{date_from}_{date_to}.xlsx"
        return send_file(buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True, download_name=fname)
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("attendance.records_list"))


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
