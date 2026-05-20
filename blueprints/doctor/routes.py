"""
Doctor Workspace Blueprint — Premium Animal Hospital Platform
Personal dashboard, queue, schedule, patients, and stats for doctors.
"""

from flask import render_template, request, redirect, url_for, flash, session
from . import doctor_bp
from blueprints.auth.routes import login_required
from models.database import get_db
from datetime import date, datetime, timedelta
import sqlite3


def _doctor_name():
    user = session.get("user", {})
    return user.get("full_name") or user.get("username", "")


def _is_admin():
    return session.get("user", {}).get("role") in ("super_admin", "clinic_owner", "branch_manager")


@doctor_bp.route("/")
@login_required
def workspace():
    conn = get_db()
    today = date.today().isoformat()
    doctor = _doctor_name()

    try:
        if _is_admin():
            todays_appointments = conn.execute(
                """SELECT a.*, o.full_name owner_name, o.phone owner_phone,
                   p.pet_name, p.species
                   FROM appointments a
                   JOIN owners o ON o.id = a.owner_id
                   JOIN pets p ON p.id = a.pet_id
                   WHERE DATE(a.appointment_date) = ?
                   ORDER BY a.appointment_date""", (today,)
            ).fetchall()
        else:
            todays_appointments = conn.execute(
                """SELECT a.*, o.full_name owner_name, o.phone owner_phone,
                   p.pet_name, p.species
                   FROM appointments a
                   JOIN owners o ON o.id = a.owner_id
                   JOIN pets p ON p.id = a.pet_id
                   WHERE DATE(a.appointment_date) = ?
                     AND LOWER(a.doctor_name) LIKE ?
                   ORDER BY a.appointment_date""",
                (today, f"%{doctor.lower()}%")
            ).fetchall()
    except Exception:
        todays_appointments = []

    try:
        if _is_admin():
            open_visits = conn.execute(
                """SELECT v.id visit_id, v.chief_complaint, v.visit_date,
                   p.pet_name, o.full_name owner_name
                   FROM visits v
                   JOIN pets p ON p.id = v.pet_id
                   JOIN owners o ON o.id = v.owner_id
                   WHERE v.status = 'Open'
                   ORDER BY v.visit_date DESC LIMIT 10""",
            ).fetchall()
        else:
            open_visits = conn.execute(
                """SELECT v.id visit_id, v.chief_complaint, v.visit_date,
                   p.pet_name, o.full_name owner_name
                   FROM visits v
                   JOIN pets p ON p.id = v.pet_id
                   JOIN owners o ON o.id = v.owner_id
                   WHERE v.status = 'Open'
                     AND LOWER(v.doctor_name) LIKE ?
                   ORDER BY v.visit_date DESC LIMIT 10""",
                (f"%{doctor.lower()}%",)
            ).fetchall()
    except Exception:
        open_visits = []

    try:
        upcoming_vaccinations = conn.execute(
            """SELECT p.pet_name, o.full_name owner_name, o.phone,
               v.vaccine_name, v.next_due_at AS next_due_date
               FROM vaccinations v
               JOIN pets p ON p.id = v.pet_id
               JOIN owners o ON o.id = p.owner_id
               WHERE DATE(v.next_due_at) BETWEEN ? AND ?
               ORDER BY v.next_due_at LIMIT 10""",
            (today, (date.today() + timedelta(days=7)).isoformat())
        ).fetchall()
    except Exception:
        upcoming_vaccinations = []

    try:
        completed_today = conn.execute(
            "SELECT COUNT(*) FROM visits WHERE status='Completed' AND DATE(updated_at)=?",
            (today,)
        ).fetchone()[0]
    except Exception:
        completed_today = 0

    stats = {
        "appointments_today": len(todays_appointments),
        "open_visits": len(open_visits),
        "completed_today": completed_today,
    }

    conn.close()
    return render_template(
        "doctor/workspace.html",
        todays_appointments=todays_appointments,
        open_visits=open_visits,
        upcoming_vaccinations=upcoming_vaccinations,
        doctor_name=doctor,
        stats=stats,
        active="doctor",
        page_title="Doctor Workspace",
    )


@doctor_bp.route("/queue")
@login_required
def queue():
    conn = get_db()
    today = date.today().isoformat()
    doctor = _doctor_name()
    now = datetime.now()

    try:
        if _is_admin():
            appointments = conn.execute(
                """SELECT a.*, o.full_name owner_name, o.phone owner_phone,
                   p.pet_name, p.species, p.breed
                   FROM appointments a
                   JOIN owners o ON o.id = a.owner_id
                   JOIN pets p ON p.id = a.pet_id
                   WHERE DATE(a.appointment_date) = ?
                   ORDER BY a.appointment_date""", (today,)
            ).fetchall()
        else:
            appointments = conn.execute(
                """SELECT a.*, o.full_name owner_name, o.phone owner_phone,
                   p.pet_name, p.species, p.breed
                   FROM appointments a
                   JOIN owners o ON o.id = a.owner_id
                   JOIN pets p ON p.id = a.pet_id
                   WHERE DATE(a.appointment_date) = ?
                     AND LOWER(a.doctor_name) LIKE ?
                   ORDER BY a.appointment_date""",
                (today, f"%{doctor.lower()}%")
            ).fetchall()
    except Exception:
        appointments = []

    conn.close()
    return render_template(
        "doctor/queue.html",
        appointments=appointments,
        today=today,
        now=now.strftime("%H:%M"),
        active="doctor",
        page_title="Today's Queue",
    )


@doctor_bp.route("/patients")
@login_required
def my_patients():
    conn = get_db()
    doctor = _doctor_name()

    try:
        if _is_admin():
            patients = conn.execute(
                """SELECT DISTINCT p.id, p.pet_name, p.species, p.breed,
                   o.full_name owner_name, o.phone,
                   MAX(v.visit_date) last_visit
                   FROM visits v
                   JOIN pets p ON p.id = v.pet_id
                   JOIN owners o ON o.id = v.owner_id
                   GROUP BY p.id ORDER BY last_visit DESC LIMIT 100"""
            ).fetchall()
        else:
            patients = conn.execute(
                """SELECT DISTINCT p.id, p.pet_name, p.species, p.breed,
                   o.full_name owner_name, o.phone,
                   MAX(v.visit_date) last_visit
                   FROM visits v
                   JOIN pets p ON p.id = v.pet_id
                   JOIN owners o ON o.id = v.owner_id
                   WHERE LOWER(v.doctor_name) LIKE ?
                   GROUP BY p.id ORDER BY last_visit DESC LIMIT 100""",
                (f"%{doctor.lower()}%",)
            ).fetchall()
    except Exception:
        patients = []

    conn.close()
    return render_template(
        "doctor/patients.html",
        patients=patients,
        doctor_name=doctor,
        active="doctor",
        page_title="My Patients",
    )


@doctor_bp.route("/schedule")
@login_required
def my_schedule():
    conn = get_db()
    doctor = _doctor_name()

    week_offset = int(request.args.get("week", 0))
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_days = [start_of_week + timedelta(days=i) for i in range(7)]
    date_from = week_days[0].isoformat()
    date_to = week_days[-1].isoformat()

    try:
        if _is_admin():
            appointments = conn.execute(
                """SELECT a.*, o.full_name owner_name, p.pet_name, p.species
                   FROM appointments a
                   JOIN owners o ON o.id = a.owner_id
                   JOIN pets p ON p.id = a.pet_id
                   WHERE DATE(a.appointment_date) BETWEEN ? AND ?
                   ORDER BY a.appointment_date""",
                (date_from, date_to)
            ).fetchall()
        else:
            appointments = conn.execute(
                """SELECT a.*, o.full_name owner_name, p.pet_name, p.species
                   FROM appointments a
                   JOIN owners o ON o.id = a.owner_id
                   JOIN pets p ON p.id = a.pet_id
                   WHERE DATE(a.appointment_date) BETWEEN ? AND ?
                     AND LOWER(a.doctor_name) LIKE ?
                   ORDER BY a.appointment_date""",
                (date_from, date_to, f"%{doctor.lower()}%")
            ).fetchall()
    except Exception:
        appointments = []

    # Group by date
    schedule = {}
    for d in week_days:
        schedule[d.isoformat()] = []
    for a in appointments:
        day_key = (a["appointment_date"] or "")[:10]
        if day_key in schedule:
            schedule[day_key].append(a)

    conn.close()
    return render_template(
        "doctor/schedule.html",
        schedule=schedule,
        week_days=week_days,
        today=today,
        week_offset=week_offset,
        doctor_name=doctor,
        active="doctor",
        page_title="My Schedule",
    )


@doctor_bp.route("/visit/<int:visit_id>/quick")
@login_required
def quick_visit(visit_id):
    return redirect(url_for("visits.visit_detail", visit_id=visit_id))


@doctor_bp.route("/appointment/<int:appt_id>/checkin", methods=["POST"])
@login_required
def checkin(appt_id):
    conn = get_db()
    conn.execute(
        "UPDATE appointments SET status='In Progress' WHERE id=?", (appt_id,)
    )
    conn.commit()
    conn.close()
    flash("Patient checked in — appointment is now In Progress.", "success")
    next_url = request.form.get("next") or url_for("doctor.queue")
    return redirect(next_url)


@doctor_bp.route("/stats")
@login_required
def my_stats():
    conn = get_db()
    doctor = _doctor_name()
    today = date.today()
    month_start = today.replace(day=1).isoformat()

    def safe_query(sql, params=()):
        try:
            return conn.execute(sql, params).fetchall()
        except Exception:
            return []

    def safe_scalar(sql, params=(), default=0):
        try:
            row = conn.execute(sql, params).fetchone()
            return row[0] if row else default
        except Exception:
            return default

    doc_filter = f"%{doctor.lower()}%"

    total_visits = safe_scalar(
        "SELECT COUNT(*) FROM visits WHERE LOWER(doctor_name) LIKE ? AND status='Completed'",
        (doc_filter,)
    ) if not _is_admin() else safe_scalar(
        "SELECT COUNT(*) FROM visits WHERE status='Completed'"
    )

    month_visits = safe_scalar(
        "SELECT COUNT(*) FROM visits WHERE LOWER(doctor_name) LIKE ? AND status='Completed' AND DATE(visit_date)>=?",
        (doc_filter, month_start)
    ) if not _is_admin() else safe_scalar(
        "SELECT COUNT(*) FROM visits WHERE status='Completed' AND DATE(visit_date)>=?",
        (month_start,)
    )

    days_in_month = today.day
    avg_per_day = round(month_visits / days_in_month, 1) if days_in_month else 0

    top_diagnoses = safe_query(
        """SELECT d.diagnosis, COUNT(*) cnt
           FROM diagnoses d
           JOIN visits v ON v.id = d.visit_id
           WHERE LOWER(v.doctor_name) LIKE ?
           GROUP BY d.diagnosis ORDER BY cnt DESC LIMIT 5""",
        (doc_filter,)
    ) if not _is_admin() else safe_query(
        "SELECT diagnosis, COUNT(*) cnt FROM diagnoses GROUP BY diagnosis ORDER BY cnt DESC LIMIT 5"
    )

    species_breakdown = safe_query(
        """SELECT p.species, COUNT(*) cnt
           FROM visits v JOIN pets p ON p.id = v.pet_id
           WHERE LOWER(v.doctor_name) LIKE ?
           GROUP BY p.species ORDER BY cnt DESC""",
        (doc_filter,)
    ) if not _is_admin() else safe_query(
        "SELECT p.species, COUNT(*) cnt FROM visits v JOIN pets p ON p.id=v.pet_id GROUP BY p.species ORDER BY cnt DESC"
    )

    # Last 6 months trend
    monthly_trend = []
    for i in range(5, -1, -1):
        m_date = (today.replace(day=1) - timedelta(days=i * 28))
        m_start = m_date.replace(day=1).isoformat()
        m_end = (m_date.replace(day=28) + timedelta(days=4)).replace(day=1).isoformat()
        cnt = safe_scalar(
            "SELECT COUNT(*) FROM visits WHERE status='Completed' AND DATE(visit_date)>=? AND DATE(visit_date)<?",
            (m_start, m_end)
        )
        monthly_trend.append({"month": m_date.strftime("%b"), "count": cnt})

    unique_patients = safe_scalar(
        "SELECT COUNT(DISTINCT pet_id) FROM visits WHERE LOWER(doctor_name) LIKE ? AND status='Completed'",
        (doc_filter,)
    ) if not _is_admin() else safe_scalar(
        "SELECT COUNT(DISTINCT pet_id) FROM visits WHERE status='Completed'"
    )

    conn.close()
    return render_template(
        "doctor/stats.html",
        total_visits=total_visits,
        month_visits=month_visits,
        avg_per_day=avg_per_day,
        unique_patients=unique_patients,
        top_diagnoses=top_diagnoses,
        species_breakdown=species_breakdown,
        monthly_trend=monthly_trend,
        doctor_name=doctor,
        active="doctor",
        page_title="My Statistics",
    )
