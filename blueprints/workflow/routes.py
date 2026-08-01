# -*- coding: utf-8 -*-
"""One screen for the whole visit: client -> patient -> exam -> diagnosis ->
treatment -> invoice -> payment.

WHY THIS BLUEPRINT CONTAINS ALMOST NO LOGIC

The steps already exist as routes, and they are not thin. complete_visit alone
is 125 lines: it gates on a diagnosis existing, prices the consultation from the
service catalogue, turns every prescription line into an invoice line, and
raises the invoice. add_prescription and add_diagnosis have their own rules.
Re-implementing any of that here would mean two versions of the clinic's
billing, drifting apart, with the tests only covering one.

So the page POSTs to the SAME routes a receptionist's browser posts to today —
the exact chain tests/test_full_cycle.py drives end to end. This module adds
only READ endpoints: search clients, list their pets, report where a visit has
got to. Nothing here writes.

That is also what makes the page safe: every write still passes through
@login_required, the module permission gate, CSRF validation, and the logic that
1,469 tests cover.
"""
import logging
from datetime import date

from flask import jsonify, render_template, request, session

import models.database as db
from blueprints.auth.routes import login_required

from . import workflow_bp

logger = logging.getLogger(__name__)


@workflow_bp.route("/")
@login_required
def index():
    """The workflow page itself."""
    from blueprints.ai_assistant.routes import ai_configured

    user = session.get("user") or {}
    return render_template(
        "workflow/index.html",
        active="workflow",
        page_title="New Visit",
        doctor_name=user.get("full_name") or "",
        # Decided server-side so an unconfigured clinic never sees a button that
        # cannot work. A control that fails when pressed is worse than one that
        # was never offered — the staff member has already committed to the step.
        ai_available=ai_configured(),
    )


# ── reads ────────────────────────────────────────────────────────────────────

@workflow_bp.route("/api/owners")
@login_required
def api_owners():
    """Search clients by name or phone.

    Deliberately capped and requiring 2 characters: an empty query would return
    the clinic's entire client list to a type-ahead on every keystroke.
    """
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])

    like = f"%{q}%"
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT id, full_name, full_name_ar, phone, whatsapp_phone, email "
            "FROM owners "
            "WHERE full_name LIKE ? OR full_name_ar LIKE ? OR phone LIKE ? "
            "   OR whatsapp_phone LIKE ? "
            "ORDER BY full_name LIMIT 12",
            (like, like, like, like)).fetchall()
    finally:
        conn.close()

    out = []
    for r in rows:
        d = dict(r)
        # Pet count in the result makes "is this the right Ahmed?" answerable
        # without opening the record.
        conn = db.get_db()
        try:
            d["pet_count"] = conn.execute(
                "SELECT COUNT(*) c FROM pets WHERE owner_id=?", (d["id"],)
            ).fetchone()["c"]
        finally:
            conn.close()
        out.append(d)
    return jsonify(out)


@workflow_bp.route("/api/today")
@login_required
def api_today():
    """Who is booked today, and who is already in the waiting room.

    Most visits are not walk-ins. Making reception type a name they already have
    on the screen is the kind of friction that gets a system worked around
    rather than used — so the default view of step one is the queue, and search
    is the fallback for the walk-in.

    Checked-in first: those people are physically in the building.
    """
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT a.id, a.appt_start, a.appointment_type, a.status, a.reason,"
            "       a.doctor_name,"
            "       o.id AS owner_id, o.full_name, o.phone,"
            "       p.id AS pet_id, p.pet_name, p.species, p.breed,"
            "       p.weight_kg, p.allergies "
            "FROM appointments a "
            "JOIN owners o ON o.id = a.owner_id "
            "JOIN pets   p ON p.id = a.pet_id "
            "WHERE a.appt_date = ? "
            "  AND a.status NOT IN ('Completed','Cancelled','No-Show') "
            "ORDER BY CASE a.status WHEN 'Checked-in' THEN 0 ELSE 1 END, "
            "         a.appt_start",
            (date.today().isoformat(),)).fetchall()
    finally:
        conn.close()
    return jsonify([dict(r) for r in rows])


@workflow_bp.route("/api/owner/<int:owner_id>/pets")
@login_required
def api_owner_pets(owner_id):
    conn = db.get_db()
    try:
        owner = conn.execute("SELECT * FROM owners WHERE id=?", (owner_id,)).fetchone()
        if not owner:
            return jsonify({"ok": False, "error": "Client not found."}), 404
        pets = conn.execute(
            "SELECT id, pet_name, species, breed, sex, weight_kg, allergies "
            "FROM pets WHERE owner_id=? ORDER BY pet_name", (owner_id,)).fetchall()
    finally:
        conn.close()
    return jsonify({"ok": True, "owner": dict(owner),
                    "pets": [dict(p) for p in pets]})


@workflow_bp.route("/api/visit/<int:visit_id>")
@login_required
def api_visit(visit_id):
    """Where has this visit got to?

    The page uses this after every write instead of trusting its own memory of
    what it just posted. If a POST half-succeeded, the next step must see the
    real state, not an optimistic one.
    """
    conn = db.get_db()
    try:
        visit = conn.execute(
            "SELECT v.*, o.full_name owner_name, p.pet_name, p.species "
            "FROM visits v "
            "JOIN owners o ON o.id = v.owner_id "
            "JOIN pets p ON p.id = v.pet_id "
            "WHERE v.id=?", (visit_id,)).fetchone()
        if not visit:
            return jsonify({"ok": False, "error": "Visit not found."}), 404

        diagnoses = conn.execute(
            "SELECT id, diagnosis, severity FROM diagnoses WHERE visit_id=? ORDER BY id",
            (visit_id,)).fetchall()
        rx = conn.execute(
            "SELECT pi.medication_name, pi.dosage, pi.frequency, pi.duration,"
            "       pi.quantity, pi.unit "
            "FROM prescriptions pr "
            "JOIN prescription_items pi ON pi.prescription_id = pr.id "
            "WHERE pr.visit_id=? ORDER BY pi.id", (visit_id,)).fetchall()
        invoice = conn.execute(
            "SELECT id, invoice_number, total, paid_amount, due_amount, status "
            "FROM invoices WHERE visit_id=? ORDER BY id DESC LIMIT 1",
            (visit_id,)).fetchone()
    finally:
        conn.close()

    return jsonify({
        "ok": True,
        "visit": dict(visit),
        "diagnoses": [dict(d) for d in diagnoses],
        "prescription": [dict(r) for r in rx],
        "invoice": dict(invoice) if invoice else None,
    })


@workflow_bp.route("/api/pet/<int:pet_id>/history")
@login_required
def api_pet_history(pet_id):
    """Recent visits, so a vet is not examining an animal blind.

    Being able to see "last seen 3 weeks ago for the same complaint" without
    leaving the page is most of the reason to have one page at all.
    """
    conn = db.get_db()
    try:
        rows = conn.execute(
            "SELECT v.id, v.visit_date, v.chief_complaint, v.status,"
            "       (SELECT diagnosis FROM diagnoses d WHERE d.visit_id = v.id "
            "        ORDER BY d.id LIMIT 1) AS diagnosis "
            "FROM visits v WHERE v.pet_id=? ORDER BY v.id DESC LIMIT 5",
            (pet_id,)).fetchall()
        allergies = conn.execute(
            "SELECT allergies FROM pets WHERE id=?", (pet_id,)).fetchone()
    finally:
        conn.close()
    return jsonify({
        "ok": True,
        "allergies": (allergies["allergies"] if allergies else "") or "",
        "visits": [dict(r) for r in rows],
    })
