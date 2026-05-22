"""
Clinical Blueprint — Lab Requests, Vaccinations, Surgeries
Aleefy Platform
"""

from flask import (
    render_template, request, redirect, url_for,
    session, flash, abort,
)
from datetime import date, timedelta
from . import clinical_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db


# ── Helpers ───────────────────────────────────────────────────────────────────

COMMON_TESTS = [
    "CBC (Complete Blood Count)",
    "Biochemistry Panel",
    "Urinalysis",
    "X-Ray",
    "Ultrasound",
    "Culture & Sensitivity",
    "Fecal Exam",
    "Heartworm Test",
    "Thyroid Panel",
    "Electrolytes",
    "Blood Glucose",
    "Coagulation Profile",
]

VACCINE_OPTIONS = [
    "Rabies",
    "DHPP (Distemper/Hepatitis/Parvovirus/Parainfluenza)",
    "Bordetella",
    "Leptospirosis",
    "Feline FVRCP",
    "FeLV (Feline Leukemia)",
    "Custom",
]

ANESTHESIA_TYPES = ["General", "Local", "Sedation"]


def _get_lab_requests(status_filter: str = "") -> list:
    conn = db.get_db()
    q = """
        SELECT lr.*, p.pet_name, p.species, o.full_name owner_name,
               v.visit_date, v.doctor_name
        FROM lab_requests lr
        JOIN pets p ON p.id = lr.pet_id
        JOIN owners o ON o.id = p.owner_id
        LEFT JOIN visits v ON v.id = lr.visit_id
        WHERE 1=1
    """
    params: list = []
    if status_filter:
        q += " AND lr.status = ?"
        params.append(status_filter)
    q += " ORDER BY lr.created_at DESC LIMIT 200"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Lab routes ────────────────────────────────────────────────────────────────

@clinical_bp.route("/lab")
@login_required
def lab_list():
    pending     = _get_lab_requests("Pending")
    in_progress = _get_lab_requests("In Progress")
    completed   = _get_lab_requests("Completed")
    return render_template(
        "clinical/lab_list.html",
        active="clinical",
        page_title="Lab Requests",
        pending=pending,
        in_progress=in_progress,
        completed=completed,
    )


@clinical_bp.route("/lab/new", methods=["GET", "POST"])
@login_required
def lab_new():
    visit_id = request.args.get("visit_id") or request.form.get("visit_id")
    visit = None
    pet   = None

    if visit_id:
        visit = db.get_visit(int(visit_id))
        if visit:
            pet = db.get_pet(visit["pet_id"])

    if request.method == "POST":
        user = session["user"]
        test_name = request.form.get("test_name", "").strip()
        custom    = request.form.get("custom_test", "").strip()
        if test_name == "Custom" and custom:
            test_name = custom
        if not test_name:
            flash("Test name is required.", "danger")
            return render_template(
                "clinical/lab_form.html",
                active="clinical",
                page_title="New Lab Request",
                visit=visit, pet=pet,
                common_tests=COMMON_TESTS,
            )

        # Need visit_id and pet_id
        v_id = int(request.form.get("visit_id") or 0)
        p_id = int(request.form.get("pet_id") or 0)
        if not v_id or not p_id:
            flash("Visit and pet are required.", "danger")
            return redirect(url_for("clinical.lab_new"))

        conn = db.get_db()
        with conn:
            conn.execute(
                """INSERT INTO lab_requests
                   (visit_id, pet_id, test_name, test_code, priority, status,
                    sample_type, notes, requested_by)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (v_id, p_id,
                 test_name,
                 request.form.get("test_code", "").strip(),
                 request.form.get("priority", "Routine"),
                 "Pending",
                 request.form.get("sample_type", "").strip(),
                 request.form.get("notes", "").strip(),
                 user.get("full_name", user["username"])),
            )
        conn.close()
        flash(f"Lab request for '{test_name}' created.", "success")
        return redirect(url_for("clinical.lab_list"))

    return render_template(
        "clinical/lab_form.html",
        active="clinical",
        page_title="New Lab Request",
        visit=visit, pet=pet,
        common_tests=COMMON_TESTS,
    )


@clinical_bp.route("/lab/<int:lab_id>", methods=["GET"])
@login_required
def lab_detail(lab_id: int):
    conn = db.get_db()
    row = conn.execute(
        """SELECT lr.*, p.pet_name, p.species, o.full_name owner_name,
                  v.visit_date, v.doctor_name
           FROM lab_requests lr
           JOIN pets p ON p.id = lr.pet_id
           JOIN owners o ON o.id = p.owner_id
           LEFT JOIN visits v ON v.id = lr.visit_id
           WHERE lr.id = ?""",
        (lab_id,),
    ).fetchone()
    if not row:
        conn.close()
        abort(404)
    lab = dict(row)
    results = [dict(r) for r in conn.execute(
        "SELECT * FROM lab_results WHERE lab_request_id = ? ORDER BY created_at DESC",
        (lab_id,),
    ).fetchall()]
    conn.close()
    return render_template(
        "clinical/lab_detail.html",
        active="clinical",
        page_title=f"Lab Request — {lab['test_name']}",
        lab=lab,
        results=results,
    )


@clinical_bp.route("/lab/<int:lab_id>/results", methods=["POST"])
@login_required
def lab_results(lab_id: int):
    user = session["user"]
    conn = db.get_db()
    row = conn.execute("SELECT * FROM lab_requests WHERE id=?", (lab_id,)).fetchone()
    if not row:
        conn.close()
        abort(404)

    is_abnormal = 1 if request.form.get("is_abnormal") else 0
    result_value_raw = request.form.get("result_value", "").strip()
    result_value = float(result_value_raw) if result_value_raw else None

    with conn:
        conn.execute(
            """INSERT INTO lab_results
               (lab_request_id, pet_id, result_text, result_value, unit,
                reference_range, is_abnormal, reviewed_by, reviewed_at)
               VALUES (?,?,?,?,?,?,?,?,datetime('now'))""",
            (lab_id, row["pet_id"],
             request.form.get("result_text", "").strip(),
             result_value,
             request.form.get("unit", "").strip(),
             request.form.get("reference_range", "").strip(),
             is_abnormal,
             user.get("full_name", user["username"])),
        )
        conn.execute(
            "UPDATE lab_requests SET status='Completed' WHERE id=?", (lab_id,)
        )
    conn.close()
    flash("Lab results saved.", "success")
    return redirect(url_for("clinical.lab_detail", lab_id=lab_id))


# ── Vaccination routes ────────────────────────────────────────────────────────

@clinical_bp.route("/vaccinations")
@login_required
def vaccinations():
    upcoming = db.get_upcoming_vaccines(days=30)
    all_vacs = db.list_vaccinations(limit=200)
    return render_template(
        "clinical/vaccinations.html",
        active="clinical",
        page_title="Vaccinations",
        upcoming=upcoming,
        all_vacs=all_vacs,
        today=date.today().isoformat(),
    )


@clinical_bp.route("/vaccinations/new", methods=["GET", "POST"])
@login_required
def vaccination_new():
    pet_id = request.args.get("pet_id") or request.form.get("pet_id")
    pet = db.get_pet(int(pet_id)) if pet_id else None

    if request.method == "POST":
        user = session["user"]
        p_id = int(request.form.get("pet_id") or 0)
        if not p_id:
            flash("Pet is required.", "danger")
            return redirect(url_for("clinical.vaccination_new"))

        vaccine_name = request.form.get("vaccine_name", "").strip()
        custom_vax   = request.form.get("custom_vaccine", "").strip()
        if vaccine_name == "Custom" and custom_vax:
            vaccine_name = custom_vax

        administered_at = request.form.get("administered_at", "").strip() or date.today().isoformat()
        next_due_raw    = request.form.get("next_due_at", "").strip()

        conn = db.get_db()
        with conn:
            conn.execute(
                """INSERT INTO vaccinations
                   (pet_id, vaccine_name, vaccine_brand, batch_number, dose_number,
                    administered_by, administered_at, next_due_at, site, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (p_id, vaccine_name,
                 request.form.get("vaccine_brand", "").strip(),
                 request.form.get("batch_number", "").strip(),
                 int(request.form.get("dose_number", 1) or 1),
                 user.get("full_name", user["username"]),
                 administered_at,
                 next_due_raw or None,
                 request.form.get("site", "Subcutaneous").strip(),
                 request.form.get("notes", "").strip()),
            )
        conn.close()
        flash(f"Vaccination '{vaccine_name}' recorded.", "success")
        return redirect(url_for("clinical.vaccinations"))

    return render_template(
        "clinical/vaccination_form.html",
        active="clinical",
        page_title="Record Vaccination",
        pet=pet,
        vaccine_options=VACCINE_OPTIONS,
        today=date.today().isoformat(),
    )


# ── Surgery routes ────────────────────────────────────────────────────────────

@clinical_bp.route("/surgeries")
@login_required
def surgeries():
    conn = db.get_db()
    rows = conn.execute(
        """SELECT s.*, p.pet_name, p.species, o.full_name owner_name
           FROM surgeries s
           JOIN pets p ON p.id = s.pet_id
           JOIN owners o ON o.id = p.owner_id
           ORDER BY s.surgery_date DESC LIMIT 200""",
    ).fetchall()
    conn.close()
    surgery_list = [dict(r) for r in rows]
    return render_template(
        "clinical/surgeries.html",
        active="clinical",
        page_title="Surgeries",
        surgeries=surgery_list,
    )


@clinical_bp.route("/surgeries/new", methods=["GET", "POST"])
@login_required
def surgery_new():
    pet_id = request.args.get("pet_id") or request.form.get("pet_id")
    pet = db.get_pet(int(pet_id)) if pet_id else None

    if request.method == "POST":
        user = session["user"]
        p_id = int(request.form.get("pet_id") or 0)
        if not p_id:
            flash("Pet is required.", "danger")
            return redirect(url_for("clinical.surgery_new"))

        consent = 1 if request.form.get("consent_given") else 0
        duration_raw = request.form.get("duration_min", "").strip()
        duration = int(duration_raw) if duration_raw.isdigit() else None

        conn = db.get_db()
        with conn:
            conn.execute(
                """INSERT INTO surgeries
                   (pet_id, procedure_name, surgeon, anesthetist, surgery_date,
                    duration_min, anesthesia_type, pre_op_notes, intra_op_notes,
                    post_op_notes, outcome, followup_date, consent_given)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p_id,
                 request.form.get("procedure_name", "").strip(),
                 request.form.get("surgeon", "").strip(),
                 request.form.get("anesthetist", "").strip(),
                 request.form.get("surgery_date", date.today().isoformat()).strip(),
                 duration,
                 request.form.get("anesthesia_type", "General").strip(),
                 request.form.get("pre_op_notes", "").strip(),
                 request.form.get("intra_op_notes", "").strip(),
                 request.form.get("post_op_notes", "").strip(),
                 request.form.get("outcome", "Successful").strip(),
                 request.form.get("followup_date", "").strip() or None,
                 consent),
            )
        conn.close()
        flash("Surgery record saved.", "success")
        return redirect(url_for("clinical.surgeries"))

    return render_template(
        "clinical/surgery_form.html",
        active="clinical",
        page_title="Record Surgery",
        pet=pet,
        anesthesia_types=ANESTHESIA_TYPES,
        today=date.today().isoformat(),
    )
