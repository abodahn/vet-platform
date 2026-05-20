from flask import render_template, request, redirect, url_for, flash, session
from . import visits_bp
from blueprints.auth.routes import login_required
from models.database import get_db
import models.database as db
from datetime import date


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

    # If no context provided, get list of owners + pets for selection
    owners = conn.execute(
        "SELECT id, full_name, phone FROM owners ORDER BY full_name LIMIT 200"
    ).fetchall()

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

    diagnoses = conn.execute(
        "SELECT * FROM diagnoses WHERE visit_id=? ORDER BY created_at",
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
        conn.execute(
            """UPDATE treatment_plans SET plan_text=?, goals=?, duration=?,
               followup_in=?, followup_unit=?, updated_at=datetime('now') WHERE visit_id=?""",
            (plan_text, goals, duration, followup_in, followup_unit, visit_id),
        )
    else:
        conn.execute(
            """INSERT INTO treatment_plans(visit_id, plan_text, goals, duration,
               followup_in, followup_unit, created_by, created_at)
               VALUES(?,?,?,?,?,?,?,datetime('now'))""",
            (visit_id, plan_text, goals, duration, followup_in, followup_unit, user.get("id")),
        )

    conn.commit()
    conn.close()
    flash("Treatment plan saved.", "success")
    return redirect(url_for("visits.visit_detail", visit_id=visit_id) + "#treatment")


@visits_bp.route("/<int:visit_id>/prescription", methods=["POST"])
@login_required
def add_prescription(visit_id):
    user = session.get("user", {})
    conn = get_db()

    rx_notes = request.form.get("rx_notes", "")

    cur = conn.execute(
        """INSERT INTO prescriptions(visit_id, notes, created_by, created_at)
           VALUES(?,?,?,datetime('now'))""",
        (visit_id, rx_notes, user.get("id")),
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
        "SELECT * FROM diagnoses WHERE visit_id=? ORDER BY created_at", (visit_id,)
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
