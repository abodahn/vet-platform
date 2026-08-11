import logging

from flask import render_template, request, redirect, url_for, flash, session
from . import visits_bp
from blueprints.auth.routes import login_required
from models.database import get_db
import models.database as db
from datetime import date

logger = logging.getLogger(__name__)


@visits_bp.route("/")
@login_required
def visits_list():
    conn = get_db()
    status_filter = request.args.get("status", "All")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    doctor_filter = request.args.get("doctor", "")

    query = """
        SELECT v.*, o.full_name owner_name, o.phone owner_phone,
               p.pet_name, p.species, p.breed
        FROM visits v
        JOIN owners o ON o.id = v.owner_id
        JOIN pets p ON p.id = v.pet_id
        WHERE 1=1
    """
    params = []

    if status_filter and status_filter != "All":
        query += " AND v.status = ?"
        params.append(status_filter)
    if date_from:
        query += " AND DATE(v.visit_date) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND DATE(v.visit_date) <= ?"
        params.append(date_to)
    if doctor_filter:
        query += " AND LOWER(v.doctor_name) LIKE ?"
        params.append(f"%{doctor_filter.lower()}%")

    query += " ORDER BY v.visit_date DESC LIMIT 50"

    visits = conn.execute(query, params).fetchall()

    # Get distinct doctors for filter dropdown
    doctors = conn.execute(
        "SELECT DISTINCT doctor_name FROM visits WHERE doctor_name IS NOT NULL ORDER BY doctor_name"
    ).fetchall()

    conn.close()
    return render_template(
        "visits/visits_list.html",
        visits=visits,
        doctors=doctors,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        doctor_filter=doctor_filter,
        active="visits",
    )


@visits_bp.route("/new", methods=["GET"])
@login_required
def visit_new_form():
    conn = get_db()
    appt_id = request.args.get("appt_id")
    pet_id = request.args.get("pet_id")
    owner_id = request.args.get("owner_id")

    appointment = None
    pet = None
    owner = None

    if appt_id:
        appointment = conn.execute(
            "SELECT * FROM appointments WHERE id=?", (appt_id,)
        ).fetchone()
        if appointment:
            if not pet_id:
                pet_id = appointment["pet_id"]
            if not owner_id:
                owner_id = appointment["owner_id"]

    if pet_id:
        pet = conn.execute("SELECT * FROM pets WHERE id=?", (pet_id,)).fetchone()
    if owner_id:
        owner = conn.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()

    # Only the pre-selected owner is rendered; the rest are found by typing,
    # against crm.owner_search_json. A capped list here silently hid every
    # client past the cap.
    owners = [owner] if owner else []

    conn.close()
    return render_template(
        "visits/visit_form.html",
        appointment=appointment,
        pet=pet,
        owner=owner,
        owners=owners,
        active="visits",
    )


@visits_bp.route("/new", methods=["POST"])
@login_required
def visit_new_submit():
    user = session.get("user", {})
    conn = get_db()

    appt_id = request.form.get("appointment_id") or None
    owner_id = request.form.get("owner_id")
    pet_id = request.form.get("pet_id")
    doctor_name = request.form.get("doctor_name", user.get("full_name", ""))
    visit_type = request.form.get("visit_type", "Consultation")
    chief_complaint = request.form.get("chief_complaint", "")
    symptoms = request.form.get("symptoms", "")
    weight_kg = request.form.get("weight_kg") or None
    temp_c = request.form.get("temp_c") or None
    heart_rate = request.form.get("heart_rate") or None
    respiratory_rate = request.form.get("respiratory_rate") or None
    notes = request.form.get("notes", "")

    if not owner_id or not pet_id:
        flash("Owner and pet are required.", "error")
        return redirect(url_for("visits.visit_new_form"))

    cur = conn.execute(
        """INSERT INTO visits(appointment_id, owner_id, pet_id, doctor_id, doctor_name,
           visit_date, visit_type, status, chief_complaint, symptoms,
           weight_kg, temp_c, heart_rate, respiratory_rate, notes, created_by)
           VALUES(?,?,?,?,?,datetime('now'),?,?,?,?,?,?,?,?,?,?)""",
        (
            appt_id,
            owner_id,
            pet_id,
            user.get("id"),
            doctor_name,
            visit_type,
            "Open",
            chief_complaint,
            symptoms,
            weight_kg,
            temp_c,
            heart_rate,
            respiratory_rate,
            notes,
            user.get("id"),
        ),
    )
    conn.commit()
    visit_id = cur.lastrowid
    conn.close()
    flash("Visit created successfully.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id))


@visits_bp.route("/<int:visit_id>")
@login_required
def visit_detail(visit_id):
    conn = get_db()

    visit = conn.execute(
        """SELECT v.*, o.full_name owner_name, o.phone owner_phone,
           p.pet_name, p.species, p.breed, p.sex, p.weight_kg pet_weight,
           p.allergies, p.dob pet_dob, p.color pet_color
           FROM visits v
           JOIN owners o ON o.id = v.owner_id
           JOIN pets p ON p.id = v.pet_id
           WHERE v.id=?""",
        (visit_id,),
    ).fetchone()

    if not visit:
        flash("Visit not found.", "error")
        return redirect(url_for("visits.visits_list"))

    # The column is `diagnosis`; both templates read `diagnosis_text`, so
    # without this alias every diagnosis rendered as an empty line.
    diagnoses = conn.execute(
        "SELECT *, diagnosis AS diagnosis_text FROM diagnoses WHERE visit_id=? "
        "ORDER BY created_at",
        (visit_id,),
    ).fetchall()

    treatment = conn.execute(
        "SELECT * FROM treatment_plans WHERE visit_id=?", (visit_id,)
    ).fetchone()

    prescriptions = conn.execute(
        "SELECT * FROM prescriptions WHERE visit_id=?", (visit_id,)
    ).fetchall()

    rx_items = {}
    for rx in prescriptions:
        items = conn.execute(
            "SELECT * FROM prescription_items WHERE prescription_id=?", (rx["id"],)
        ).fetchall()
        rx_items[rx["id"]] = items

    lab_requests = conn.execute(
        "SELECT * FROM lab_requests WHERE visit_id=? ORDER BY created_at", (visit_id,)
    ).fetchall()

    # Check for linked invoice
    invoice_row = conn.execute(
        "SELECT id, invoice_number FROM invoices WHERE visit_id=?", (visit_id,)
    ).fetchone()
    invoice = dict(invoice_row) if invoice_row else None

    # Who may be named as the prescriber, and whether THIS user is one. A nurse
    # gets a vet to choose from rather than a form that refuses her on submit.
    vets = prescribers(conn)
    user_role = (session.get("user") or {}).get("role")

    conn.close()
    return render_template(
        "visits/visit_detail.html",
        visit=visit,
        diagnoses=diagnoses,
        treatment=treatment,
        prescriptions=prescriptions,
        rx_items=rx_items,
        lab_requests=lab_requests,
        invoice=invoice,
        prescribers=vets,
        can_prescribe=(user_role in PRESCRIBER_ROLES),
        active="visits",
    )


@visits_bp.route("/<int:visit_id>/diagnosis", methods=["POST"])
@login_required
def add_diagnosis(visit_id):
    user = session.get("user", {})
    conn = get_db()

    diagnosis_text = request.form.get("diagnosis_text", "").strip()
    severity = request.form.get("severity", "Mild")
    diagnosis_notes = request.form.get("diagnosis_notes", "")

    if not diagnosis_text:
        flash("Diagnosis text is required.", "error")
        conn.close()
        return redirect(url_for("visits.visit_detail", visit_id=visit_id))

    # Column is `diagnosis` in the schema (not `diagnosis_text`)
    conn.execute(
        """INSERT INTO diagnoses(visit_id, pet_id, diagnosis, severity, notes, created_by, created_at)
           SELECT ?, pet_id, ?, ?, ?, ?, datetime('now') FROM visits WHERE id=?""",
        (visit_id, diagnosis_text, severity, diagnosis_notes, user.get("id"), visit_id),
    )
    conn.commit()
    conn.close()
    flash("Diagnosis added.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id) + "#diagnosis")


@visits_bp.route("/<int:visit_id>/treatment", methods=["POST"])
@login_required
def save_treatment(visit_id):
    user = session.get("user", {})
    conn = get_db()

    plan_text = request.form.get("plan_text", "")
    goals = request.form.get("goals", "")
    duration = request.form.get("duration", "")
    followup_in = request.form.get("followup_in") or None
    followup_unit = request.form.get("followup_unit", "days")

    existing = conn.execute(
        "SELECT id FROM treatment_plans WHERE visit_id=?", (visit_id,)
    ).fetchone()

    if existing:
        # treatment_plans has no updated_at column — naming it here made every
        # edit of a plan raise instead of saving.
        conn.execute(
            """UPDATE treatment_plans SET plan_text=?, goals=?, duration=?,
               followup_in=?, followup_unit=? WHERE visit_id=?""",
            (plan_text, goals, duration, followup_in, followup_unit, visit_id),
        )
    else:
        # pet_id is NOT NULL. Taken from the visit the same way add_diagnosis
        # does it, so the plan cannot be filed under a different animal.
        conn.execute(
            """INSERT INTO treatment_plans(visit_id, pet_id, plan_text, goals, duration,
               followup_in, followup_unit, created_by, created_at)
               SELECT ?, pet_id, ?, ?, ?, ?, ?, ?, datetime('now')
               FROM visits WHERE id=?""",
            (visit_id, plan_text, goals, duration, followup_in, followup_unit,
             user.get("id"), visit_id),
        )

    conn.commit()
    conn.close()
    flash("Treatment plan saved.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id) + "#treatment")


# Roles whose holder may lawfully prescribe. A clinic owner is on the list
# because in a small Egyptian practice the owner IS the vet; a practice where
# that is not true should take the role off its owner account rather than have
# the software guess.
PRESCRIBER_ROLES = ("doctor", "clinic_owner", "super_admin")


def prescribers(conn) -> list:
    """Active staff who may be named as the prescriber."""
    marks = ",".join("?" for _ in PRESCRIBER_ROLES)
    try:
        rows = conn.execute(
            f"SELECT full_name, username FROM users "
            f"WHERE is_active=1 AND role IN ({marks}) ORDER BY full_name",
            PRESCRIBER_ROLES).fetchall()
    except Exception:
        return []
    return [(r["full_name"] or r["username"]) for r in rows]


def _resolve_prescriber(conn, user, requested: str):
    """(name, error). Who this prescription is recorded against.

    A prescriber writing their own prescription needs no extra step. Anyone else
    must name a veterinarian, and the name must match an actual active one --
    a free-text box would let "Dr. Someone" through and put the clinic right
    back where it started.
    """
    available = prescribers(conn)
    requested = (requested or "").strip()

    if user.get("role") in PRESCRIBER_ROLES and not requested:
        return (user.get("full_name") or user.get("username", "")), ""

    if not requested:
        if not available:
            return "", ("No veterinarian is set up on this system, so a "
                        "prescription cannot be attributed to one. Add a user "
                        "with the doctor role first.")
        return "", ("Select the prescribing veterinarian. Only a vet may be "
                    "recorded as the prescriber, though you may enter the "
                    "prescription on their behalf.")

    if requested not in available:
        return "", (f"“{requested}” is not an active veterinarian on this "
                    f"system, so a prescription cannot be recorded against them.")
    return requested, ""


@visits_bp.route("/<int:visit_id>/prescription", methods=["POST"])
@login_required
def add_prescription(visit_id):
    user = session.get("user", {})
    conn = get_db()

    rx_notes = request.form.get("rx_notes", "")

    # A prescription carries pet_id and owner_id (both NOT NULL): the pharmacy
    # queue, the dispensing log and the narcotics register all join on them, so
    # one without them is invisible to the pharmacist who has to fill it.
    # There is no `created_by` column here — the prescriber is `prescribed_by`.
    visit = conn.execute(
        "SELECT pet_id, owner_id FROM visits WHERE id=?", (visit_id,)).fetchone()
    if not visit:
        conn.close()
        flash("Visit not found.", "error")
        return redirect(url_for("visits.visits_list"))

    # A prescription must name the VETERINARIAN who prescribed it.
    #
    # This used to stamp prescribed_by with whoever was logged in. add_prescription
    # is @login_required only and `visits` is on the nurse grant, so a nurse could
    # write and sign a prescription under her own name -- it saved, and went into
    # the pharmacy queue attributed to a person who may not lawfully prescribe.
    # That is the clinic's regulatory exposure, not ours, which is exactly why the
    # software should not make it possible.
    #
    # A nurse may still TYPE it -- a vet dictating while someone else enters it is
    # how a busy clinic actually runs, and how paper works. What she cannot do is
    # be recorded as the prescriber.
    prescriber, perr = _resolve_prescriber(conn, user, request.form.get("prescribed_by", ""))
    if perr:
        conn.close()
        flash(perr, "danger")
        return redirect(url_for("visits.visit_detail", visit_id=visit_id))

    # Who typed it is kept too. If a dispute reaches the record later, "Dr X
    # prescribed, Nurse Y entered it" is the answer; a single name is not.
    typed_by = user.get("full_name") or user.get("username", "")
    if typed_by and typed_by != prescriber:
        rx_notes = (rx_notes + f"\n[entered by {typed_by} on behalf of {prescriber}]").strip()

    cur = conn.execute(
        """INSERT INTO prescriptions(visit_id, pet_id, owner_id, prescribed_by,
           status, notes, created_at)
           VALUES(?,?,?,?,'Active',?,datetime('now'))""",
        (visit_id, visit["pet_id"], visit["owner_id"], prescriber, rx_notes),
    )
    rx_id = cur.lastrowid

    # Dynamic line items: medication_name_1, dosage_1, etc.
    i = 1
    while request.form.get(f"medication_name_{i}"):
        med_name = request.form.get(f"medication_name_{i}", "")
        dosage = request.form.get(f"dosage_{i}", "")
        frequency = request.form.get(f"frequency_{i}", "")
        duration = request.form.get(f"duration_{i}", "")
        route = request.form.get(f"route_{i}", "")
        quantity = request.form.get(f"quantity_{i}") or None
        unit = request.form.get(f"unit_{i}", "")
        instructions = request.form.get(f"instructions_{i}", "")

        conn.execute(
            """INSERT INTO prescription_items(prescription_id, medication_name, dosage,
               frequency, duration, route, quantity, unit, instructions)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (rx_id, med_name, dosage, frequency, duration, route, quantity, unit, instructions),
        )
        i += 1

    conn.commit()
    conn.close()
    flash("Prescription added.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id) + "#prescriptions")


@visits_bp.route("/<int:visit_id>/soap", methods=["POST"])
@login_required
def save_soap(visit_id):
    user = session.get("user", {})
    conn = get_db()
    conn.execute(
        """UPDATE visits SET
               soap_subjective=?, soap_objective=?, soap_assessment=?, soap_plan=?,
               updated_at=datetime('now')
           WHERE id=?""",
        (
            request.form.get("soap_subjective", "").strip(),
            request.form.get("soap_objective",  "").strip(),
            request.form.get("soap_assessment", "").strip(),
            request.form.get("soap_plan",       "").strip(),
            visit_id,
        ),
    )
    conn.commit()
    db.log_audit(
        username=user.get("username", ""),
        role=user.get("role", ""),
        action="soap_update",
        module="visits",
        entity_type="visits",
        entity_id=str(visit_id),
        details="SOAP notes updated",
    )
    conn.close()
    flash("SOAP notes saved.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id) + "#soap")


@visits_bp.route("/<int:visit_id>/complete", methods=["POST"])
@login_required
def complete_visit(visit_id):
    user = session.get("user", {})
    conn = get_db()

    # 1 — Diagnosis required gate
    diag_count = conn.execute(
        "SELECT COUNT(*) FROM diagnoses WHERE visit_id=?", (visit_id,)
    ).fetchone()[0]

    if diag_count == 0:
        flash("Please add at least one diagnosis before completing the visit.", "warning")
        conn.close()
        return redirect(url_for("visits.visit_detail", visit_id=visit_id))

    # 2 — Load visit + patient details
    visit = conn.execute(
        """SELECT v.*, o.full_name owner_name, p.pet_name, p.species
           FROM visits v
           JOIN owners o ON o.id = v.owner_id
           JOIN pets   p ON p.id = v.pet_id
           WHERE v.id=?""",
        (visit_id,),
    ).fetchone()

    # 3 — Mark visit as Completed
    conn.execute(
        "UPDATE visits SET status='Completed', updated_at=datetime('now') WHERE id=?",
        (visit_id,),
    )
    conn.commit()

    # 4 — Auto-generate invoice if one doesn't exist yet
    existing_inv = conn.execute(
        "SELECT id FROM invoices WHERE visit_id=?", (visit_id,)
    ).fetchone()

    if not existing_inv and visit:
        # Build line items from diagnoses (column is `diagnosis`)
        diagnoses_rows = conn.execute(
            "SELECT diagnosis FROM diagnoses WHERE visit_id=?", (visit_id,)
        ).fetchall()
        # Helper: look up price from service_catalog by keyword
        def _lookup_price(keyword: str) -> float:
            row = conn.execute(
                "SELECT standard_price FROM service_catalog WHERE LOWER(name) LIKE ? AND is_active=1 LIMIT 1",
                (f"%{keyword.lower()}%",)
            ).fetchone()
            return float(row["standard_price"]) if row and row["standard_price"] else 0.0

        visit_type_label = visit["visit_type"] if visit else "Consultation"
        consult_price = _lookup_price(visit_type_label) or _lookup_price("consultation")

        lines = []
        for d in diagnoses_rows:
            lines.append({
                "line_type":   "service",
                "description": f"Consultation — {d['diagnosis']}",
                "quantity":    1,
                "unit_price":  consult_price,
                "discount":    0.0,
                "total":       consult_price,
            })

        # Add prescription items as medication lines
        rx_items = conn.execute(
            """SELECT pi.medication_name, pi.quantity, pi.unit
               FROM prescriptions pr
               JOIN prescription_items pi ON pi.prescription_id = pr.id
               WHERE pr.visit_id=?""",
            (visit_id,),
        ).fetchall()
        for item in rx_items:
            qty = float(item["quantity"] or 1)
            med_price = _lookup_price(item["medication_name"])
            lines.append({
                "line_type":   "medication",
                "description": item["medication_name"],
                "quantity":    qty,
                "unit_price":  med_price,
                "discount":    0.0,
                "total":       round(qty * med_price, 2),
            })

        if not lines:
            lines.append({
                "line_type":   "service",
                "description": f"Veterinary Consultation — {visit_type_label}",
                "quantity":    1,
                "unit_price":  consult_price,
                "discount":    0.0,
                "total":       consult_price,
            })

        conn.close()

        inv_data = {
            "owner_id":       visit["owner_id"],
            "pet_id":         visit["pet_id"],
            "visit_id":       visit_id,
            "doctor_name":    visit["doctor_name"] or user.get("full_name", ""),
            "issue_date":     date.today().isoformat(),
            "discount_type":  "value",
            "discount_value": 0.0,
            "tax_rate":       0.0,
            "notes":          f"Auto-generated from visit #{visit_id}. Please update prices.",
            "created_by":     user.get("full_name", ""),
        }
        try:
            inv_id = db.create_invoice(inv_data, lines)
            flash(
                f"Visit completed. Invoice #{inv_id} auto-generated.",
                "success",
            )
            return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
        except Exception as e:
            flash(f"Visit completed but invoice creation failed: {e}", "warning")
            return redirect(url_for("visits.visit_detail", visit_id=visit_id))
    else:
        conn.close()

    flash("Visit marked as Completed.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id))


@visits_bp.route("/<int:visit_id>/invoice")
@login_required
def visit_invoice(visit_id):
    """Redirect to the invoice linked to this visit (or finance new-invoice form pre-filled)."""
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM invoices WHERE visit_id=?", (visit_id,)
    ).fetchone()
    conn.close()
    if row:
        return redirect(url_for("finance.invoice_detail", inv_id=row["id"]))
    # No invoice yet — send to new invoice form pre-filled with visit context
    return redirect(
        url_for("finance.invoice_new") + f"?visit_id={visit_id}"
    )


@visits_bp.route("/<int:visit_id>/print")
@login_required
def visit_print(visit_id):
    conn = get_db()

    visit = conn.execute(
        """SELECT v.*, o.full_name owner_name, o.phone owner_phone,
           p.pet_name, p.species, p.breed, p.sex, p.weight_kg pet_weight,
           p.allergies, p.dob pet_dob
           FROM visits v
           JOIN owners o ON o.id = v.owner_id
           JOIN pets p ON p.id = v.pet_id
           WHERE v.id=?""",
        (visit_id,),
    ).fetchone()

    if not visit:
        flash("Visit not found.", "error")
        return redirect(url_for("visits.visits_list"))

    diagnoses = conn.execute(
        "SELECT *, diagnosis AS diagnosis_text FROM diagnoses WHERE visit_id=? "
        "ORDER BY created_at", (visit_id,)
    ).fetchall()

    treatment = conn.execute(
        "SELECT * FROM treatment_plans WHERE visit_id=?", (visit_id,)
    ).fetchone()

    prescriptions = conn.execute(
        "SELECT * FROM prescriptions WHERE visit_id=?", (visit_id,)
    ).fetchall()

    rx_items = {}
    for rx in prescriptions:
        items = conn.execute(
            "SELECT * FROM prescription_items WHERE prescription_id=?", (rx["id"],)
        ).fetchall()
        rx_items[rx["id"]] = items

    lab_requests = conn.execute(
        "SELECT * FROM lab_requests WHERE visit_id=? ORDER BY created_at", (visit_id,)
    ).fetchall()

    conn.close()
    return render_template(
        "visits/visit_print.html",
        visit=visit,
        diagnoses=diagnoses,
        treatment=treatment,
        prescriptions=prescriptions,
        rx_items=rx_items,
        lab_requests=lab_requests,
    )


# ─────────────────────────────────────────────────────────────────────
# EXAM — the one-screen visit
#
# Modelled on the Windows system Egyptian clinics already use: the vet never
# leaves the page. Vitals, symptom, services, money, receipt — one save.
# /visits/new keeps the long-form workflow; this is the fast lane.
#
# It writes through the SAME functions finance uses (db.create_invoice,
# db.add_payment), so there is one money path in the product, not two.
# ─────────────────────────────────────────────────────────────────────

def _services(conn):
    return [dict(r) for r in conn.execute(
        "SELECT id, name, name_ar, category, standard_price FROM service_catalog"
        " WHERE is_active=1 ORDER BY sort_order, name").fetchall()]


def _medications(conn):
    """What a vet can prescribe. Missing table is not fatal to the screen."""
    try:
        return [r[0] for r in conn.execute(
            "SELECT name FROM items WHERE is_medication=1 AND is_active=1"
            " ORDER BY name LIMIT 400").fetchall()]
    except Exception:
        return []


@visits_bp.route("/exam")
@login_required
def exam_pick():
    """The one screen, with nothing loaded yet.

    Client search happens ON this page through /exam/api/search, so picking a
    client never costs a navigation — same as the dialog in the Windows system
    this copies. ?pet_id= is honoured so a link from elsewhere lands loaded.
    """
    pet_id = request.args.get("pet_id", type=int)
    if pet_id:
        return redirect(url_for("visits.exam_form", pet_id=pet_id))
    conn = get_db()
    services = _services(conn)
    doctors = prescribers(conn)
    meds_list = _medications(conn)
    conn.close()
    return render_template("visits/exam.html", active="visits",
                           today=date.today().isoformat(),
                           pet={}, owner={}, history=[], services=services,
                           doctors=doctors, meds_list=meds_list,
                           vaccines=[], meds=[], chronic=[],
                           invoices=[], siblings=[], upcoming=[], outstanding=0.0)


def _age_text(dob):
    """'3y 4m' from a date of birth, or '' — a vet doses by age, not birthday."""
    if not dob:
        return ""
    try:
        born = date.fromisoformat(str(dob)[:10])
    except ValueError:
        return ""
    today = date.today()
    months = (today.year - born.year) * 12 + (today.month - born.month)
    if today.day < born.day:
        months -= 1
    if months < 0:
        return ""
    return ("%dy %dm" % (months // 12, months % 12)) if months >= 12 else ("%dm" % months)


def _exam_context(conn, pet_id):
    """Everything the exam screen shows, or None if the pet does not exist.

    The screen is meant to be the whole picture, so this is deliberately wide:
    the vet should never have to open another tab to find out that the animal
    in front of them is allergic to something, or that the owner walked out
    owing money last time.
    """
    pet = conn.execute(
        "SELECT * FROM pets WHERE id=? AND is_active=1", (pet_id,)).fetchone()
    if not pet:
        return None
    owner_id = pet["owner_id"]
    owner = conn.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()

    services = [dict(r) for r in conn.execute(
        "SELECT id, name, name_ar, category, standard_price FROM service_catalog"
        " WHERE is_active=1 ORDER BY sort_order, name").fetchall()]
    history = [dict(r) for r in conn.execute(
        "SELECT id, visit_date, visit_type, chief_complaint, symptoms,"
        " weight_kg, temp_c, doctor_name, status FROM visits"
        " WHERE pet_id=? ORDER BY visit_date DESC LIMIT 50", (pet_id,)).fetchall()]

    def rows(sql, args=()):
        """A missing optional table must not take the whole screen down."""
        try:
            return [dict(r) for r in conn.execute(sql, args).fetchall()]
        except Exception:
            return []

    vaccines = rows(
        "SELECT id, visit_id, vaccine_name, vaccine_brand, administered_at,"
        " next_due_at, administered_by, dose_number FROM vaccinations"
        " WHERE pet_id=? ORDER BY COALESCE(administered_at,'') DESC LIMIT 25",
        (pet_id,))
    today_iso = date.today().isoformat()
    for v in vaccines:
        due = (v.get("next_due_at") or "")[:10]
        v["overdue"] = bool(due and due < today_iso)
        v["due_soon"] = bool(due and not v["overdue"] and due <= (
            date.today().replace(day=1).isoformat()[:8] + "28") and due >= today_iso)

    meds = rows(
        "SELECT p.id AS prescription_id, p.visit_id, pi.medication_name, pi.dosage,"
        " pi.frequency, pi.duration, pi.route, pi.dispensed, p.created_at, p.status"
        " FROM prescription_items pi JOIN prescriptions p ON p.id=pi.prescription_id"
        " WHERE p.pet_id=? ORDER BY p.created_at DESC LIMIT 25", (pet_id,))

    chronic = rows(
        "SELECT id, visit_id, diagnosis, severity, is_chronic, created_at"
        " FROM diagnoses WHERE pet_id=? ORDER BY created_at DESC LIMIT 25", (pet_id,))

    invoices = rows(
        "SELECT id, invoice_number, issue_date, total, paid_amount, due_amount,"
        " status FROM invoices WHERE owner_id=? AND status!='Cancelled'"
        " ORDER BY issue_date DESC, id DESC LIMIT 15", (owner_id,))

    siblings = rows(
        "SELECT id, pet_name, species, breed, sex, dob FROM pets"
        " WHERE owner_id=? AND is_active=1 AND id!=? ORDER BY pet_name",
        (owner_id, pet_id))

    upcoming = rows(
        "SELECT id, appt_date, appt_start, appointment_type, doctor_name, status"
        " FROM appointments WHERE pet_id=? AND appt_date>=?"
        " AND status NOT IN ('Cancelled','Completed','No-Show')"
        " ORDER BY appt_date, appt_start LIMIT 5", (pet_id, today_iso))

    # What this client owes across every open invoice. The stored
    # owners.outstanding_balance drifts; the ledger does not.
    owed = rows("SELECT COALESCE(SUM(due_amount),0) AS owed FROM invoices"
                " WHERE owner_id=? AND status IN ('Unpaid','Partial')", (owner_id,))
    outstanding = float(owed[0]["owed"]) if owed else 0.0

    pet_d = dict(pet)
    pet_d["age_text"] = _age_text(pet_d.get("dob"))
    for s in siblings:
        s["age_text"] = _age_text(s.get("dob"))

    return {
        "pet": pet_d,
        "owner": dict(owner) if owner else {},
        "services": services,
        "history": history,
        "vaccines": vaccines,
        "meds": meds,
        "chronic": chronic,
        "invoices": invoices,
        "siblings": siblings,
        "upcoming": upcoming,
        "outstanding": round(outstanding, 2),
    }


@visits_bp.route("/exam/<int:pet_id>", methods=["GET"])
@login_required
def exam_form(pet_id):
    conn = get_db()
    ctx = _exam_context(conn, pet_id)
    conn.close()
    if not ctx:
        flash("Pet not found.", "danger")
        return redirect(url_for("visits.exam_pick"))
    conn2 = get_db()
    doctors = prescribers(conn2)
    meds_list = _medications(conn2)
    conn2.close()
    return render_template("visits/exam.html", active="visits",
                           today=date.today().isoformat(),
                           doctors=doctors, meds_list=meds_list, **ctx)


# ── the one page: search, pick and load without ever navigating ──────
# The Windows system this screen copies opens client management as a DIALOG
# over the exam, not as another screen. These two endpoints are what let the
# page do the same: the vet never loses what is already typed.

@visits_bp.route("/exam/api/search")
@login_required
def exam_api_search():
    from flask import jsonify
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"owners": []})
    like = "%" + q + "%"
    conn = get_db()
    owners = [dict(r) for r in conn.execute(
        "SELECT id, full_name, phone, address FROM owners"
        " WHERE full_name LIKE ? OR phone LIKE ? OR whatsapp_phone LIKE ?"
        " ORDER BY full_name LIMIT 25", (like, like, like)).fetchall()]
    if owners:
        ids = [o["id"] for o in owners]
        marks = ",".join("?" * len(ids))
        pets = [dict(r) for r in conn.execute(
            "SELECT id, owner_id, pet_name, species, breed, sex, dob, weight_kg"
            " FROM pets WHERE is_active=1 AND owner_id IN (" + marks + ")"
            " ORDER BY pet_name", ids).fetchall()]
        for o in owners:
            o["pets"] = [p for p in pets if p["owner_id"] == o["id"]]
    conn.close()
    return jsonify({"owners": owners})


@visits_bp.route("/exam/api/pet/<int:pet_id>")
@login_required
def exam_api_pet(pet_id):
    from flask import jsonify
    conn = get_db()
    ctx = _exam_context(conn, pet_id)
    conn.close()
    if not ctx:
        return jsonify({"error": "not found"}), 404
    # The service catalog is already on the page; sending it again per pet
    # would triple the payload for data that never changes mid-visit.
    ctx.pop("services", None)
    return jsonify(ctx)


@visits_bp.route("/exam/api/client", methods=["POST"])
@login_required
def exam_api_client():
    """Create a client and their first pet, without leaving the exam.

    The walk-in is the case this whole screen exists for, and it was the one
    case it could not handle: the empty state linked away to CRM, which threw
    away anything already typed and put the receptionist three screens from
    the animal in front of her.
    """
    from flask import jsonify
    f = request.get_json(silent=True) or {}
    name = (f.get("full_name") or "").strip()
    phone = (f.get("phone") or "").strip()
    pet_name = (f.get("pet_name") or "").strip()
    if not name:
        return jsonify({"error": "A client name is required."}), 400
    if not pet_name:
        return jsonify({"error": "A pet name is required."}), 400

    conn = get_db()
    try:
        # Same phone, same client. A busy front desk types the same person in
        # twice a week otherwise, and the pet history splits across both.
        existing = None
        if phone:
            existing = conn.execute(
                "SELECT id FROM owners WHERE phone=? OR whatsapp_phone=?",
                (phone, phone)).fetchone()
        if existing:
            owner_id = existing[0]
        else:
            cur = conn.execute(
                "INSERT INTO owners(full_name, phone, whatsapp_phone, address,"
                " created_by) VALUES(?,?,?,?,?)",
                (name, phone, phone, (f.get("address") or "").strip(),
                 (session.get("user") or {}).get("full_name", "")))
            owner_id = cur.lastrowid
        cur = conn.execute(
            "INSERT INTO pets(owner_id, pet_name, species, breed, sex, dob)"
            " VALUES(?,?,?,?,?,?)",
            (owner_id, pet_name, (f.get("species") or "").strip(),
             (f.get("breed") or "").strip(), (f.get("sex") or "Unknown").strip(),
             (f.get("dob") or "").strip() or None))
        pet_id = cur.lastrowid
        conn.commit()
    except Exception:
        logger.exception("could not create client/pet from the exam screen")
        conn.close()
        return jsonify({"error": "Could not save. Check the details and retry."}), 500

    ctx = _exam_context(conn, pet_id)
    conn.close()
    if not ctx:
        return jsonify({"error": "Saved, but could not load the pet."}), 500
    ctx.pop("services", None)
    return jsonify(ctx)


@visits_bp.route("/exam/api/pet", methods=["POST"])
@login_required
def exam_api_add_pet():
    """Add another pet to the client already on screen."""
    from flask import jsonify
    f = request.get_json(silent=True) or {}
    owner_id = f.get("owner_id")
    pet_name = (f.get("pet_name") or "").strip()
    if not owner_id or not pet_name:
        return jsonify({"error": "A pet name is required."}), 400
    conn = get_db()
    owner = conn.execute("SELECT id FROM owners WHERE id=?", (owner_id,)).fetchone()
    if not owner:
        conn.close()
        return jsonify({"error": "Client not found."}), 404
    cur = conn.execute(
        "INSERT INTO pets(owner_id, pet_name, species, breed, sex, dob)"
        " VALUES(?,?,?,?,?,?)",
        (owner_id, pet_name, (f.get("species") or "").strip(),
         (f.get("breed") or "").strip(), (f.get("sex") or "Unknown").strip(),
         (f.get("dob") or "").strip() or None))
    pet_id = cur.lastrowid
    conn.commit()
    ctx = _exam_context(conn, pet_id)
    conn.close()
    if not ctx:
        return jsonify({"error": "Saved, but could not load the pet."}), 500
    ctx.pop("services", None)
    return jsonify(ctx)


def _exam_num(form, name, default=0.0):
    """A money/vitals box a tired person typed into. Never raises."""
    raw = (form.get(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return default


@visits_bp.route("/exam/<int:pet_id>", methods=["POST"])
@login_required
def exam_submit(pet_id):
    """One submit: visit + invoice + payment. Partial payment is normal here —
    the clinic takes what the client has and the rest shows as Due."""
    f = request.form
    user = session.get("user", {})
    conn = get_db()
    ctx = _exam_context(conn, pet_id)
    if not ctx:
        conn.close()
        flash("Pet not found.", "danger")
        return redirect(url_for("visits.exam_pick"))
    owner_id = ctx["pet"]["owner_id"]

    # ── the visit ────────────────────────────────────────────────────
    symptom = (f.get("symptom") or "").strip()
    weight = _exam_num(f, "weight_kg", None) if (f.get("weight_kg") or "").strip() else None
    temp   = _exam_num(f, "temp_c", None) if (f.get("temp_c") or "").strip() else None
    doctor = (f.get("doctor_name") or user.get("full_name", "")).strip()
    visit_date = (f.get("visit_date") or "").strip() or date.today().isoformat()

    cur = conn.execute(
        """INSERT INTO visits(owner_id, pet_id, doctor_id, doctor_name, visit_date,
           visit_type, status, chief_complaint, symptoms, weight_kg, temp_c,
           notes, created_by)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (owner_id, pet_id, user.get("id"), doctor, visit_date,
         "Consultation", "Completed", symptom, symptom, weight, temp,
         (f.get("notes") or "").strip(), user.get("id")))
    conn.commit()
    visit_id = cur.lastrowid

    # Vitals taken today are the pet's current vitals.
    if weight is not None:
        conn.execute("UPDATE pets SET weight_kg=?, updated_at=datetime('now')"
                     " WHERE id=?", (weight, pet_id))
        conn.commit()

    # ── the diagnosis ────────────────────────────────────────────────
    # A symptom is what the owner reports; a diagnosis is what the vet
    # concluded. Recording only the first leaves the medical record with no
    # findings, and the History panel on this very screen has a Diagnoses
    # column that nothing here could ever fill.
    diagnosis = (f.get("diagnosis") or "").strip()
    if diagnosis:
        try:
            conn.execute(
                "INSERT INTO diagnoses(visit_id, pet_id, diagnosis, severity,"
                " is_chronic, created_by) VALUES(?,?,?,?,?,?)",
                (visit_id, pet_id, diagnosis,
                 (f.get("severity") or "").strip() or None,
                 1 if f.get("is_chronic") else 0,
                 user.get("full_name", "")))
            conn.commit()
        except Exception:
            logger.exception("diagnosis not saved for visit %s", visit_id)

    # ── vaccinations given today ─────────────────────────────────────
    # Billing "Rabies vaccine" as a service and RECORDING it are different
    # things. Only the second updates the pet's vaccine history and sets
    # next_due_at — which is what the reminder job reads. Without this a clinic
    # could vaccinate an animal, charge for it, and never remind the owner.
    for i, vname in enumerate(f.getlist("vax_name[]")):
        vname = (vname or "").strip()
        if not vname:
            continue

        def _vat(key, idx=i):
            vals = f.getlist(key)
            return (vals[idx] or "").strip() if idx < len(vals) else ""

        try:
            conn.execute(
                "INSERT INTO vaccinations(pet_id, visit_id, vaccine_name,"
                " vaccine_brand, batch_number, administered_by, administered_at,"
                " next_due_at) VALUES(?,?,?,?,?,?,?,?)",
                (pet_id, visit_id, vname, _vat("vax_brand[]"),
                 _vat("vax_batch[]"), doctor, visit_date,
                 _vat("vax_next_due[]") or None))
            conn.commit()
        except Exception:
            logger.exception("vaccination not saved for visit %s", visit_id)

    # ── the follow-up ────────────────────────────────────────────────
    followup = (f.get("followup_date") or "").strip()
    if followup:
        try:
            conn.execute(
                "INSERT INTO appointments(owner_id, pet_id, doctor_name,"
                " appointment_type, status, appt_date, appt_start, reason,"
                " created_by) VALUES(?,?,?,?,?,?,?,?,?)",
                (owner_id, pet_id, doctor, "Follow-up", "Scheduled", followup,
                 # appt_start is NOT NULL. Passing None silently lost every
                 # follow-up booked without a time — which is most of them,
                 # because the vet picks "in a week", not "in a week at 10:15".
                 (f.get("followup_time") or "").strip() or "09:00",
                 "Follow-up for: %s" % (diagnosis or symptom or "visit"),
                 user.get("full_name", "")))
            conn.commit()
        except Exception:
            logger.exception("follow-up not booked for visit %s", visit_id)

    # ── the prescription ─────────────────────────────────────────────
    # Billing a medication and writing its dosage used to be two different
    # screens, so either the vet opened another module or the owner went home
    # with a box and no instructions. prescribed_by is the doctor NAMED on
    # this visit, not whoever is logged in — reception books for the vet.
    rx_rows = []
    for i, med in enumerate(f.getlist("rx_name[]")):
        med = (med or "").strip()
        if not med:
            continue

        def _at(key, idx=i):
            vals = f.getlist(key)
            return (vals[idx] or "").strip() if idx < len(vals) else ""

        rx_rows.append((med, _at("rx_dosage[]"), _at("rx_frequency[]"),
                        _at("rx_duration[]"), _at("rx_instructions[]")))
    if rx_rows:
        try:
            cur = conn.execute(
                "INSERT INTO prescriptions(visit_id, pet_id, owner_id,"
                " prescribed_by, status, notes) VALUES(?,?,?,?,?,?)",
                (visit_id, pet_id, owner_id, doctor, "Active", ""))
            rx_id = cur.lastrowid
            for med, dose, freq, dur, instr in rx_rows:
                conn.execute(
                    "INSERT INTO prescription_items(prescription_id,"
                    " medication_name, dosage, frequency, duration, instructions)"
                    " VALUES(?,?,?,?,?,?)",
                    (rx_id, med, dose, freq, dur, instr))
            conn.commit()
        except Exception:
            # A prescription that fails to write must not lose the visit that
            # is already saved, nor the money about to be taken.
            logger.exception("prescription not saved for visit %s", visit_id)
    conn.close()

    # ── the attachment ───────────────────────────────────────────────
    # Through the uploads blueprint's own validator, so the magic-byte check
    # and the extension whitelist are the ones that already exist.
    up = request.files.get("attachment")
    if up and up.filename:
        from blueprints.uploads.routes import save_attachment
        res = save_attachment(up, "visit", visit_id, category="visit",
                              caption=(f.get("attachment_caption") or "").strip(),
                              username=user.get("username", ""))
        if not res.get("ok"):
            flash("Photo not attached: %s." % res.get("error", "unknown"), "warning")

    # ── the bill ─────────────────────────────────────────────────────
    names  = f.getlist("item_name[]")
    prices = f.getlist("item_price[]")
    qtys   = f.getlist("item_qty[]")
    ids    = f.getlist("item_id[]")
    discs  = f.getlist("item_discount[]")
    lines = []
    for i, name in enumerate(names):
        name = (name or "").strip()
        if not name:
            continue
        try:
            price = float((prices[i] or "0").replace(",", "")) if i < len(prices) else 0.0
        except ValueError:
            price = 0.0
        try:
            qty = float((qtys[i] or "1").replace(",", "")) if i < len(qtys) else 1.0
        except ValueError:
            qty = 1.0
        # A zero or negative quantity is a typo, not a free item. Billing it
        # as 1 silently charges for something nobody ordered.
        if qty <= 0 or price < 0:
            continue
        try:
            item_id = int(ids[i]) if i < len(ids) and ids[i] else None
        except ValueError:
            item_id = None
        # A per-line discount is a PERCENTAGE, matching invoice_lines.discount
        # and what finance/invoice_new already writes. Clamped to 0..100: a
        # 150% line discount would pay the client to take the service.
        try:
            disc = float((discs[i] or "0").replace(",", "")) if i < len(discs) else 0.0
        except ValueError:
            disc = 0.0
        disc = max(0.0, min(disc, 100.0))
        gross = qty * price
        lines.append({"line_type": "service", "item_id": item_id,
                      "description": name, "quantity": qty,
                      "unit_price": price, "discount": disc,
                      "total": round(gross - gross * disc / 100.0, 2)})

    if not lines:
        flash("Visit saved. No services were billed.", "success")
        return redirect(url_for("visits.visit_detail", visit_id=visit_id))

    inv_id = db.create_invoice({
        "owner_id":       owner_id,
        "pet_id":         pet_id,
        "visit_id":       visit_id,
        "doctor_name":    doctor,
        "issue_date":     visit_date,
        "discount_type":  "percent" if f.get("discount_type") == "percent" else "value",
        "discount_value": max(0.0, _exam_num(f, "discount_value")),
        "tax_rate":       0.0,
        "notes":          (f.get("notes") or "").strip(),
        "created_by":     user.get("full_name", ""),
    }, lines)

    # ── the money ────────────────────────────────────────────────────
    # "Cash" on this screen is what the client HANDED OVER, which may be more
    # than the bill — the difference is change, not an overpayment. Only what
    # the invoice is actually owed gets recorded against it.
    invoice = db.get_invoice(inv_id) or {}
    total   = float(invoice.get("total") or 0.0)
    handed  = max(0.0, _exam_num(f, "cash_received"))
    applied = round(min(handed, total), 2)
    if applied > 0:
        db.add_payment(
            inv_id, owner_id, applied,
            method=("Visa" if f.get("payment_type") == "VISA" else "Cash"),
            received_by=user.get("full_name", ""),
            # One key per invoice: a double-clicked Save cannot bill twice.
            idempotency_key="exam-%s-%s" % (visit_id, inv_id))

    change = round(max(0.0, handed - total), 2)
    due    = round(max(0.0, total - applied), 2)
    msg = "Visit saved. Invoice %s — total %.2f" % (
        invoice.get("invoice_number", ""), total)
    if change:
        msg += ", change %.2f" % change
    if due:
        msg += ", due %.2f" % due
    flash(msg + ".", "success")

    if f.get("action") == "print":
        return redirect(url_for("finance.invoice_print", inv_id=inv_id))
    return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
