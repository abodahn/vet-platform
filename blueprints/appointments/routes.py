"""
Appointments Blueprint
Aleefy Platform
"""

from flask import (
    render_template, request, redirect, url_for,
    flash, session, jsonify
)
from . import appointments_bp
from blueprints.auth.routes import login_required
import models.database as db
from models.database import get_db
from datetime import date, datetime, timedelta


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "Scheduled":  "blue",
    "Confirmed":  "teal",
    "Checked-in": "purple",
    "CheckedIn":  "purple",
    "Completed":  "green",
    "Cancelled":  "red",
    "No-Show":    "gray",
    "NoShow":     "gray",
}

APPT_TYPES    = ["Consultation", "Vaccination", "Surgery", "Grooming", "Lab", "Follow-up", "Emergency"]
PRIORITIES    = ["Normal", "Urgent", "Emergency"]
CHANNELS      = ["Walk-in", "WhatsApp", "Phone", "Online"]
VALID_STATUSES = ["Scheduled", "Confirmed", "Checked-in", "Completed", "Cancelled", "No-Show"]


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _week_bounds(week_str=None):
    """Return (monday, saturday) for the given ISO week string or current week."""
    if week_str:
        try:
            monday = datetime.strptime(week_str, "%Y-%m-%d").date()
            # Snap to Monday
            monday = monday - timedelta(days=monday.weekday())
        except ValueError:
            monday = date.today() - timedelta(days=date.today().weekday())
    else:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
    saturday = monday + timedelta(days=5)
    return monday, saturday


def _build_agenda(appointments, day_str):
    """Build a list of hour slots (8-20) with appointments slotted in."""
    slots = []
    for hour in range(8, 21):
        hour_str = f"{hour:02d}:00"
        appts_in_slot = [
            a for a in appointments
            if a.get("appt_start", "")[:2] == f"{hour:02d}"
        ]
        slots.append({
            "hour": hour_str,
            "label": datetime.strptime(hour_str, "%H:%M").strftime("%-I %p") if hasattr(datetime, "strptime") else hour_str,
            "appointments": appts_in_slot,
        })
    return slots


def _time_label(hour):
    """Convert 24h integer to 12h label."""
    if hour == 12:
        return "12 PM"
    elif hour < 12:
        return f"{hour} AM"
    else:
        return f"{hour - 12} PM"


def _generate_slots(appt_date_str, doctor="", exclude_appt_id=None):
    """Return list of available 30-min slots for a date (8:00–19:30).

    `exclude_appt_id` — when rescheduling, exclude that appointment's own
    slot so it doesn't block itself.
    """
    existing = db.list_appointments(
        date_from=appt_date_str,
        date_to=appt_date_str,
        doctor=doctor,
        limit=200,
    )
    booked_starts = {
        a["appt_start"][:5] for a in existing
        if a["status"] not in ("Cancelled", "No-Show")
        and (exclude_appt_id is None or a["id"] != exclude_appt_id)
    }

    slots = []
    for hour in range(8, 20):
        for minute in (0, 30):
            t = f"{hour:02d}:{minute:02d}"
            slots.append({
                "time": t,
                "label": _time_label(hour) if minute == 0 else f"{_time_label(hour)[:-3]}:{minute:02d}{_time_label(hour)[-3:]}",
                "available": t not in booked_starts,
            })
    return slots


def _slot_is_free(appt_date_str, doctor, appt_start, exclude_appt_id=None):
    """Server-side guard: return True if the slot is free for that doctor."""
    slots = _generate_slots(appt_date_str, doctor, exclude_appt_id=exclude_appt_id)
    for s in slots:
        if s["time"] == appt_start[:5]:
            return s["available"]
    return True   # unknown slot — allow it


def _today_str():
    return date.today().isoformat()


# ─────────────────────────────────────────────────────────────
# SCHEDULE — TODAY
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/")
@appointments_bp.route("/schedule")
@login_required
def schedule():
    day_str = request.args.get("date", _today_str())
    try:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    except ValueError:
        day = date.today()
        day_str = day.isoformat()

    appointments = db.list_appointments(
        date_from=day_str, date_to=day_str, limit=200
    )

    # Build agenda slots
    agenda = []
    for hour in range(8, 21):
        hour_prefix = f"{hour:02d}"
        appts_in_slot = [
            a for a in appointments
            if (a.get("appt_start") or "")[:2] == hour_prefix
        ]
        agenda.append({
            "hour": hour,
            "label": _time_label(hour),
            "appointments": appts_in_slot,
        })

    # Quick stats
    total = len(appointments)
    checked_in = sum(1 for a in appointments if a["status"] in ("Checked-in", "CheckedIn"))
    completed  = sum(1 for a in appointments if a["status"] == "Completed")
    pending    = sum(1 for a in appointments if a["status"] in ("Scheduled", "Confirmed"))

    prev_day = (day - timedelta(days=1)).isoformat()
    next_day = (day + timedelta(days=1)).isoformat()

    return render_template(
        "appointments/schedule.html",
        appointments=appointments,
        agenda=agenda,
        day=day,
        day_str=day_str,
        prev_day=prev_day,
        next_day=next_day,
        today_str=_today_str(),
        status_colors=STATUS_COLORS,
        total=total,
        checked_in=checked_in,
        completed=completed,
        pending=pending,
        active="appointments",
        page_title="Schedule",
    )


# ─────────────────────────────────────────────────────────────
# CALENDAR — WEEK VIEW
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/calendar")
@login_required
def calendar():
    week_str = request.args.get("week")
    monday, saturday = _week_bounds(week_str)
    sunday = monday + timedelta(days=6)

    # Fetch week appointments
    appointments = db.list_appointments(
        date_from=monday.isoformat(),
        date_to=sunday.isoformat(),
        limit=500,
    )

    # Build day columns
    days = []
    for i in range(7):
        d = monday + timedelta(days=i)
        day_appts = [a for a in appointments if a.get("appt_date") == d.isoformat()]
        days.append({
            "date": d,
            "date_str": d.isoformat(),
            "label": d.strftime("%a"),
            "day_num": d.day,
            "is_today": d == date.today(),
            "appointments": day_appts,
        })

    prev_week = (monday - timedelta(days=7)).isoformat()
    next_week = (monday + timedelta(days=7)).isoformat()

    return render_template(
        "appointments/calendar.html",
        days=days,
        monday=monday,
        sunday=sunday,
        prev_week=prev_week,
        next_week=next_week,
        today_str=_today_str(),
        status_colors=STATUS_COLORS,
        active="appointments",
        page_title="Week Calendar",
    )


# ─────────────────────────────────────────────────────────────
# NEW APPOINTMENT
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/new", methods=["GET", "POST"])
@login_required
def appt_new():
    if request.method == "POST":
        owner_id = request.form.get("owner_id", "").strip()
        pet_id   = request.form.get("pet_id", "").strip()

        if not owner_id or not pet_id:
            flash("Owner and pet are required.", "danger")
        else:
            # Calculate end time
            appt_start   = request.form.get("appt_start", "09:00")
            duration_min = int(request.form.get("duration_min", 30))
            doctor_name  = request.form.get("doctor_name", "").strip()
            appt_date    = request.form.get("appt_date", _today_str())
            try:
                start_dt = datetime.strptime(appt_start, "%H:%M")
                end_dt   = start_dt + timedelta(minutes=duration_min)
                appt_end = end_dt.strftime("%H:%M")
            except ValueError:
                appt_end = ""

            # Server-side double-booking guard
            if doctor_name and not _slot_is_free(appt_date, doctor_name, appt_start):
                flash(f"⚠️ {doctor_name} already has an appointment at {appt_start} on {appt_date}. Please choose a different slot.", "danger")
                return redirect(url_for("appointments.appt_new",
                                        owner_id=owner_id, pet_id=pet_id, date=appt_date))

            data = {
                "owner_id":         int(owner_id),
                "pet_id":           int(pet_id),
                "doctor_name":      doctor_name,
                "appointment_type": request.form.get("appointment_type", "Consultation"),
                "priority":         request.form.get("priority", "Normal"),
                "appt_date":        appt_date,
                "appt_start":       appt_start,
                "appt_end":         appt_end,
                "duration_min":     duration_min,
                "reason":           request.form.get("reason", "").strip(),
                "symptoms":         request.form.get("symptoms", "").strip(),
                "channel":          request.form.get("channel", "Walk-in"),
                "notes":            request.form.get("notes", "").strip(),
                "status":           "Scheduled",
                "created_by":       session["user"].get("username", ""),
            }

            appt_id = db.create_appointment(data)
            db.log_audit(
                username=session["user"].get("username", ""),
                role=session["user"].get("role", ""),
                action="create_appointment",
                module="appointments",
                entity_type="appointment",
                entity_id=str(appt_id),
                details=f"Booked {data['appointment_type']} for pet {pet_id} on {data['appt_date']}",
            )
            flash("Appointment booked successfully.", "success")
            return redirect(url_for("appointments.schedule", date=data["appt_date"]))

    # GET — pre-fill from query params
    prefill_owner_id = request.args.get("owner_id", "")
    prefill_pet_id   = request.args.get("pet_id", "")
    prefill_date     = request.args.get("date", _today_str())

    owners = db.list_owners(limit=500)
    pets   = []

    # If owner pre-selected, load their pets
    selected_owner_id = request.form.get("owner_id") or prefill_owner_id
    if selected_owner_id:
        try:
            pets = db.list_pets(owner_id=int(selected_owner_id))
        except (ValueError, TypeError):
            pets = []

    # Load staff/doctors for dropdown
    conn = get_db()
    doctors = conn.execute(
        "SELECT full_name FROM users WHERE role IN ('doctor','super_admin','clinic_owner') AND is_active=1 ORDER BY full_name"
    ).fetchall()
    conn.close()
    doctors = [dict(r) for r in doctors]

    return render_template(
        "appointments/appt_form.html",
        owners=owners,
        pets=pets,
        doctors=doctors,
        appt_types=APPT_TYPES,
        priorities=PRIORITIES,
        channels=CHANNELS,
        prefill_owner_id=str(prefill_owner_id),
        prefill_pet_id=str(prefill_pet_id),
        prefill_date=prefill_date,
        active="appointments",
        page_title="New Appointment",
    )


# ─────────────────────────────────────────────────────────────
# APPOINTMENT DETAIL
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/<int:appt_id>")
@login_required
def appt_detail(appt_id):
    appt = db.get_appointment(appt_id)
    if not appt:
        flash("Appointment not found.", "danger")
        return redirect(url_for("appointments.schedule"))

    owner = db.get_owner(appt["owner_id"])

    conn = get_db()
    pet_row = conn.execute(
        "SELECT p.*, o.full_name owner_name FROM pets p JOIN owners o ON o.id=p.owner_id WHERE p.id=%s",
        (appt["pet_id"],)
    ).fetchone()
    conn.close()
    pet = dict(pet_row) if pet_row else {}

    return render_template(
        "appointments/appt_detail.html",
        appt=appt,
        owner=owner,
        pet=pet,
        status_colors=STATUS_COLORS,
        valid_statuses=VALID_STATUSES,
        active="appointments",
        page_title=f"Appointment #{appt_id}",
    )


# ─────────────────────────────────────────────────────────────
# UPDATE STATUS
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/<int:appt_id>/status", methods=["POST"])
@login_required
def appt_status(appt_id):
    new_status = request.form.get("status", "").strip()
    if new_status not in VALID_STATUSES:
        flash(f"Invalid status: {new_status}", "danger")
        return redirect(url_for("appointments.appt_detail", appt_id=appt_id))

    db.update_appointment_status(appt_id, new_status, username=session["user"].get("username", ""))
    db.log_audit(
        username=session["user"].get("username", ""),
        role=session["user"].get("role", ""),
        action="update_appointment_status",
        module="appointments",
        entity_type="appointment",
        entity_id=str(appt_id),
        details=f"Status → {new_status}",
    )
    flash(f"Appointment status updated to {new_status}.", "success")

    next_url = request.form.get("next") or request.referrer or url_for("appointments.appt_detail", appt_id=appt_id)
    return redirect(next_url)


# ─────────────────────────────────────────────────────────────
# RESCHEDULE / EDIT APPOINTMENT
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/<int:appt_id>/edit", methods=["GET", "POST"])
@login_required
def appt_edit(appt_id):
    appt = db.get_appointment(appt_id)
    if not appt:
        flash("Appointment not found.", "danger")
        return redirect(url_for("appointments.schedule"))

    if appt["status"] in ("Completed", "Cancelled"):
        flash("Cannot edit a completed or cancelled appointment.", "warning")
        return redirect(url_for("appointments.appt_detail", appt_id=appt_id))

    if request.method == "POST":
        appt_date   = request.form.get("appt_date", appt["appt_date"])
        appt_start  = request.form.get("appt_start", appt["appt_start"])
        doctor_name = request.form.get("doctor_name", appt.get("doctor_name", "")).strip()
        duration_min = int(request.form.get("duration_min", appt.get("duration_min", 30)))

        try:
            end_dt   = datetime.strptime(appt_start, "%H:%M") + timedelta(minutes=duration_min)
            appt_end = end_dt.strftime("%H:%M")
        except ValueError:
            appt_end = appt.get("appt_end", "")

        # Double-booking guard (exclude this appointment's own slot)
        if doctor_name and not _slot_is_free(appt_date, doctor_name, appt_start,
                                              exclude_appt_id=appt_id):
            flash(f"⚠️ {doctor_name} already has an appointment at {appt_start} on {appt_date}.", "danger")
            return redirect(url_for("appointments.appt_edit", appt_id=appt_id))

        conn = get_db()
        conn.execute("""
            UPDATE appointments
               SET appt_date=%s, appt_start=%s, appt_end=%s, duration_min=%s,
                   doctor_name=%s, appointment_type=%s, priority=%s,
                   reason=%s, notes=%s, channel=%s, updated_at=NOW()
             WHERE id=%s
        """, (
            appt_date, appt_start, appt_end, duration_min, doctor_name,
            request.form.get("appointment_type", appt.get("appointment_type", "Consultation")),
            request.form.get("priority", appt.get("priority", "Normal")),
            request.form.get("reason", appt.get("reason", "")),
            request.form.get("notes", appt.get("notes", "")),
            request.form.get("channel", appt.get("channel", "Walk-in")),
            appt_id,
        ))
        conn.commit()
        conn.close()

        db.log_audit(
            username=session["user"].get("username", ""),
            role=session["user"].get("role", ""),
            action="reschedule_appointment",
            module="appointments",
            entity_type="appointment",
            entity_id=str(appt_id),
            details=f"Rescheduled to {appt_date} {appt_start} with {doctor_name}",
        )
        flash("Appointment rescheduled successfully.", "success")
        return redirect(url_for("appointments.appt_detail", appt_id=appt_id))

    # GET
    conn = get_db()
    doctors = conn.execute(
        "SELECT full_name FROM users WHERE role IN ('doctor','super_admin','clinic_owner') AND is_active=1 ORDER BY full_name"
    ).fetchall()
    conn.close()

    slots = _generate_slots(appt["appt_date"], appt.get("doctor_name", ""),
                             exclude_appt_id=appt_id)

    return render_template(
        "appointments/appt_edit.html",
        appt=dict(appt),
        doctors=[dict(d) for d in doctors],
        slots=slots,
        appt_types=APPT_TYPES,
        priorities=PRIORITIES,
        channels=CHANNELS,
        active="appointments",
        page_title=f"Reschedule #{appt_id}",
    )


# ─────────────────────────────────────────────────────────────
# API — AVAILABLE SLOTS
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/api/slots")
@login_required
def api_slots():
    appt_date  = request.args.get("date", _today_str())
    doctor     = request.args.get("doctor", "")
    exclude_id = request.args.get("exclude_id")
    exclude_id = int(exclude_id) if exclude_id and exclude_id.isdigit() else None
    slots = _generate_slots(appt_date, doctor, exclude_appt_id=exclude_id)
    return jsonify({"date": appt_date, "doctor": doctor, "slots": slots})


# ─────────────────────────────────────────────────────────────
# RECEPTION WORKSPACE
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/reception")
@login_required
def reception():
    day_str = date.today().isoformat()
    appointments = db.list_appointments(date_from=day_str, date_to=day_str, limit=200)
    owners = db.list_owners(limit=500)

    # Build quick stats
    total      = len(appointments)
    checked_in = sum(1 for a in appointments if a["status"] in ("Checked-in", "CheckedIn"))
    waiting    = sum(1 for a in appointments if a["status"] in ("Scheduled", "Confirmed"))
    completed  = sum(1 for a in appointments if a["status"] == "Completed")

    # Build agenda slots (8–20)
    agenda = []
    for hour in range(8, 21):
        hour_prefix = f"{hour:02d}"
        appts_in_slot = [
            a for a in appointments
            if (a.get("appt_start") or "")[:2] == hour_prefix
        ]
        agenda.append({
            "hour": hour,
            "label": _time_label(hour),
            "appointments": appts_in_slot,
        })

    return render_template(
        "appointments/reception.html",
        appointments=appointments,
        agenda=agenda,
        owners=owners,
        today_str=day_str,
        status_colors=STATUS_COLORS,
        total=total,
        checked_in=checked_in,
        waiting=waiting,
        completed=completed,
        active="appointments",
        page_title="Reception Workspace",
    )


# ─────────────────────────────────────────────────────────────
# API — PETS BY OWNER (for dynamic pet dropdown)
# ─────────────────────────────────────────────────────────────

@appointments_bp.route("/api/pets")
@login_required
def api_pets():
    owner_id = request.args.get("owner_id", "")
    if not owner_id:
        return jsonify([])
    try:
        pets = db.list_pets(owner_id=int(owner_id))
        return jsonify([{"id": p["id"], "pet_name": p["pet_name"],
                         "species": p.get("species", ""), "breed": p.get("breed", "")}
                        for p in pets])
    except (ValueError, TypeError):
        return jsonify([])


# ── No-Show Risk Predictor ────────────────────────────────────────────────────

def _noshowscore(owner_id: int, appt_time: str = "") -> dict:
    """Return a 0-100 no-show risk score with breakdown."""
    conn = get_db()
    score = 0
    reasons = []
    try:
        total   = conn.execute("SELECT COUNT(*) FROM appointments WHERE owner_id=?", (owner_id,)).fetchone()[0]
        noshows = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE owner_id=? AND status IN ('No-Show','NoShow')",
            (owner_id,)).fetchone()[0]
        cancels = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE owner_id=? AND status='Cancelled'",
            (owner_id,)).fetchone()[0]

        if total == 0:
            score += 15
            reasons.append("New client — no history")
        else:
            ns_rate = noshows / total
            c_rate  = cancels / total
            if ns_rate > 0:
                pts = min(45, int(ns_rate * 100))
                score += pts
                reasons.append(f"No-show rate: {noshows}/{total} appointments ({int(ns_rate*100)}%)")
            if c_rate > 0.3:
                score += 10
                reasons.append(f"High cancellation rate ({int(c_rate*100)}%)")

        unpaid = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE owner_id=? AND status='Unpaid'",
            (owner_id,)).fetchone()[0]
        if unpaid > 0:
            pts = min(20, unpaid * 7)
            score += pts
            reasons.append(f"{unpaid} unpaid invoice(s)")

        last_done = conn.execute(
            "SELECT MAX(SUBSTRING(appt_date::text,1,10)) FROM appointments WHERE owner_id=? AND status='Completed'",
            (owner_id,)).fetchone()[0]
        if last_done:
            days_since = (date.today() - date.fromisoformat(str(last_done)[:10])).days
            if days_since > 180:
                score += 12
                reasons.append(f"Inactive — last visit {days_since} days ago")
            elif days_since > 90:
                score += 5

        if appt_time:
            try:
                hour = int(str(appt_time).replace(":", "")[:2])
                if hour < 9:
                    score += 8
                    reasons.append("Early morning slot")
            except Exception:
                pass
    except Exception:
        pass
    finally:
        conn.close()

    score = min(100, score)
    level = "high" if score >= 60 else "medium" if score >= 30 else "low"
    return {"score": score, "level": level, "reasons": reasons}


@appointments_bp.route("/api/risk-score/<int:owner_id>")
@login_required
def api_risk_score(owner_id):
    appt_time = request.args.get("time", "")
    return jsonify(_noshowscore(owner_id, appt_time))


# ── Waiting Room TV Display ───────────────────────────────────────────────────

@appointments_bp.route("/waiting-room")
def waiting_room():
    """Public TV display — no login required."""
    conn = get_db()
    try:
        queue = conn.execute("""
            SELECT a.id, a.appt_time, a.appointment_type, a.priority,
                   o.full_name owner_name, p.pet_name, p.species,
                   a.doctor_name, a.status
            FROM appointments a
            JOIN owners o ON o.id = a.owner_id
            LEFT JOIN pets p ON p.id = a.pet_id
            WHERE SUBSTRING(a.appt_date::text,1,10) = ?
              AND a.status IN ('Scheduled','Confirmed','Checked-in')
            ORDER BY a.appt_time
        """, (date.today().isoformat(),)).fetchall()

        clinic = conn.execute("SELECT * FROM clinic LIMIT 1").fetchone()
        tips = conn.execute(
            "SELECT content FROM notifications WHERE module='system' ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    except Exception:
        queue  = []
        clinic = None
        tips   = []
    finally:
        conn.close()

    queue_list = [dict(r) for r in queue]
    # Estimate wait: each checked-in = 20 min used; estimate per position
    checked_in = sum(1 for q in queue_list if q["status"] == "Checked-in")
    for i, q in enumerate(queue_list):
        q["position"]    = i + 1
        q["wait_min"]    = max(0, (i - checked_in) * 20)
        q["emoji"] = ("🐶" if q.get("species") == "Dog" else
                      "🐱" if q.get("species") == "Cat" else
                      "🐰" if q.get("species") == "Rabbit" else
                      "🦜" if q.get("species") == "Bird" else "🐾")

    return render_template(
        "appointments/waiting_room.html",
        queue=queue_list,
        clinic=clinic,
        today=date.today().strftime("%A, %d %B %Y"),
    )


@appointments_bp.route("/api/queue")
def api_queue():
    """JSON queue for auto-refresh."""
    conn = get_db()
    try:
        rows = conn.execute("""
            SELECT a.id, a.appt_time, a.appointment_type, a.status,
                   o.full_name owner_name, p.pet_name, p.species, a.doctor_name
            FROM appointments a
            JOIN owners o ON o.id = a.owner_id
            LEFT JOIN pets p ON p.id = a.pet_id
            WHERE SUBSTRING(a.appt_date::text,1,10) = ?
              AND a.status IN ('Scheduled','Confirmed','Checked-in')
            ORDER BY a.appt_time
        """, (date.today().isoformat(),)).fetchall()
    except Exception:
        rows = []
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])
