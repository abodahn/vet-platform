"""
CRM Blueprint — Owners & Pets
Aleefy Platform
"""

from flask import render_template, request, redirect, url_for, flash, session, jsonify, make_response
from . import crm_bp
from blueprints.auth.routes import login_required
import models.database as db
import models.concurrency as concurrency
from models.database import get_db, _try_stmt
from datetime import date, datetime, timedelta


# ─────────────────────────────────────────────────────────────
# HELPER UTILITIES
# ─────────────────────────────────────────────────────────────

PER_PAGE = 20

def _calc_age(dob_str):
    """Return human-readable age string from ISO date string."""
    if not dob_str:
        return "Unknown"
    try:
        dob = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
        today = date.today()
        years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if years < 1:
            months = (today.year - dob.year) * 12 + today.month - dob.month
            return f"{max(months,0)} mo"
        return f"{years} yr"
    except Exception:
        return "Unknown"


def _species_emoji(species):
    """Return an emoji for a given species string."""
    if not species:
        return "🐾"
    s = species.lower()
    if "dog" in s or "canine" in s:
        return "🐕"
    if "cat" in s or "feline" in s:
        return "🐈"
    if "rabbit" in s or "bunny" in s:
        return "🐰"
    if "bird" in s or "parrot" in s or "avian" in s:
        return "🐦"
    if "fish" in s:
        return "🐟"
    if "turtle" in s or "tortoise" in s:
        return "🐢"
    if "hamster" in s or "guinea" in s or "rodent" in s:
        return "🐹"
    if "snake" in s or "reptile" in s:
        return "🐍"
    return "🐾"


def _get_owner_stats(conn, owner_id):
    """Aggregate stats for an owner: visit count, last visit, outstanding balance.

    Two queries on a caller-supplied connection. `balance` is the sum of
    due_amount over invoices that are neither Paid nor Cancelled — the same
    definition finance uses, so the number on the CRM screen and the number on
    the invoice screen agree.
    """
    v = conn.execute(
        "SELECT COUNT(*), MAX(visit_date) FROM visits WHERE owner_id=?", (owner_id,)
    ).fetchone()
    balance = conn.execute(
        "SELECT COALESCE(SUM(due_amount),0) FROM invoices"
        " WHERE owner_id=? AND status NOT IN ('Cancelled','Paid')",
        (owner_id,)
    ).fetchone()[0]
    return {
        "visit_count": v[0] or 0,
        "last_visit": v[1],
        "balance": float(balance or 0),
    }


# ─────────────────────────────────────────────────────────────
# PATIENT 360 — the rest of the clinical picture
# ─────────────────────────────────────────────────────────────
#
# db.get_pet_timeline() (models/database.py, read-only) already covers six
# record types in six queries: visits, vaccinations, surgeries, grooming,
# invoices and lab requests. Everything a vet also needs to see on the animal
# — diagnoses, prescriptions, inpatient stays, boarding, imaging, telemedicine,
# pet-shop purchases and follow-ups due — is assembled here.
#
# Cost: FOUR more queries, not one per record type. The five tables guaranteed
# by the core schema go in a single UNION ALL; the three tables that are created
# lazily by their own blueprint or seed script (imaging_studies,
# telemedicine_sessions, ps_orders) get one guarded query each, because a
# missing table would otherwise take the whole UNION down with it.

_CORE_EVENTS_SQL = """
SELECT 'diagnosis' AS etype, d.id AS eid, d.created_at AS dt,
       d.diagnosis AS title, COALESCE(d.severity,'') AS summary,
       COALESCE(d.visit_id,0) AS ref, 0 AS n
  FROM diagnoses d WHERE d.pet_id = ?
UNION ALL
SELECT 'prescription', p.id, p.created_at,
       '', COALESCE(p.status,''), COALESCE(p.visit_id,0),
       (SELECT COUNT(*) FROM prescription_items pi WHERE pi.prescription_id = p.id)
  FROM prescriptions p WHERE p.pet_id = ?
UNION ALL
SELECT 'inpatient', s.id, s.admitted_at,
       COALESCE(s.reason,''), COALESCE(s.ward,''), 0, 0
  FROM inpatient_stays s WHERE s.pet_id = ?
UNION ALL
SELECT 'boarding', b.id, b.check_in,
       '', COALESCE(b.status,''), 0, 0
  FROM boarding_bookings b WHERE b.pet_id = ?
UNION ALL
SELECT 'followup', f.id, f.due_date,
       COALESCE(f.reason,''), COALESCE(f.status,''), 0, 0
  FROM followups f WHERE f.pet_id = ?
"""

# Tables that may not exist yet: imaging_studies is only created by the
# PostgreSQL migration path and the demo seed, telemedicine_sessions and
# ps_orders are created the first time their module is opened. _try_stmt logs
# and returns None instead of raising — an absent module is an expected state
# on a fresh install, a genuine SQL error still shows up in the log.
_OPTIONAL_EVENTS_SQL = [
    ("imaging", """SELECT i.id, i.created_at, i.study_type, COALESCE(i.body_region,'')
                     FROM imaging_studies i WHERE i.pet_id = ?"""),
    ("telemed", """SELECT ts.id, ts.scheduled_at, COALESCE(ts.chief_complaint,''),
                          COALESCE(ts.status,'')
                     FROM telemedicine_sessions ts WHERE ts.pet_id = ?"""),
    ("purchase", """SELECT o.id, o.created_at, COALESCE(o.order_number,''),
                           COALESCE(o.status,'')
                      FROM ps_orders o WHERE o.pet_id = ?"""),
]

_EVENT_ICONS = {
    "diagnosis": "🧬", "prescription": "💊", "inpatient": "🏥", "boarding": "🏨",
    "followup": "🔔", "imaging": "🩻", "telemed": "📹", "purchase": "🛍️",
}


def _event_url(etype, eid, ref):
    """Deep-link for a timeline event, or None when the module has no detail page."""
    if etype in ("diagnosis", "followup"):
        # Diagnoses and follow-ups live inside the visit that produced them.
        return url_for("visits.visit_detail", visit_id=ref) if ref else None
    if etype == "prescription":
        return url_for("pharmacy.rx_detail", rx_id=eid)
    if etype == "inpatient":
        return url_for("inpatient.stay_detail", stay_id=eid)
    if etype == "boarding":
        return url_for("boarding.booking_edit_form", booking_id=eid)
    if etype == "imaging":
        return url_for("imaging.study_detail", study_id=eid)
    if etype == "telemed":
        return url_for("telemedicine.session_detail", sid=eid)
    if etype == "purchase":
        return url_for("petshop.order_detail", oid=eid)
    return None


def _model_event_url(ev):
    """Deep-link for the six event types db.get_pet_timeline() produces."""
    etype, eid = ev.get("type"), ev.get("id")
    if not eid:
        return None
    if etype == "visit":
        return url_for("visits.visit_detail", visit_id=eid)
    if etype == "invoice":
        return url_for("finance.invoice_detail", inv_id=eid)
    if etype == "lab":
        return url_for("clinical.lab_detail", lab_id=eid)
    if etype == "grooming":
        return url_for("grooming.booking_edit_form", booking_id=eid)
    if etype == "vaccine":
        return url_for("clinical.vaccination_certificate", vacc_id=eid)
    return None


def _extra_pet_events(conn, pet_id):
    """Timeline events db.get_pet_timeline() does not cover. Four queries."""
    events = []
    for r in conn.execute(_CORE_EVENTS_SQL, (pet_id,) * 5).fetchall():
        etype = r["etype"]
        summary = r["summary"] or ""
        if etype == "prescription" and r["n"]:
            # "Active · 3 💊" — the pill counts the items without needing a
            # translatable unit word next to a DB-supplied status.
            summary = f"{summary} · {r['n']} 💊" if summary else f"{r['n']} 💊"
        events.append({
            "dt": r["dt"], "type": etype, "icon": _EVENT_ICONS[etype],
            "title": r["title"] or "", "summary": summary, "id": r["eid"],
            "url": _event_url(etype, r["eid"], r["ref"]),
        })

    for etype, sql in _OPTIONAL_EVENTS_SQL:
        cur = _try_stmt(conn, sql, (pet_id,))
        if cur is None:
            continue   # module never opened on this install — not an error
        for r in cur.fetchall():
            events.append({
                "dt": r[1], "type": etype, "icon": _EVENT_ICONS[etype],
                "title": r[2] or "", "summary": r[3] or "", "id": r[0],
                "url": _event_url(etype, r[0], 0),
            })
    return events


# ─────────────────────────────────────────────────────────────
# OWNERS — LIST
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners")
@login_required
def owners_list():
    q = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", 1)))
    offset = (page - 1) * PER_PAGE

    total = db.count_owners(search=q)
    owners = db.list_owners(search=q, limit=PER_PAGE, offset=offset)

    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

    return render_template(
        "crm/owners_list.html",
        owners=owners,
        q=q,
        page=page,
        total_pages=total_pages,
        total=total,
        active="crm",
        page_title="Owners & Clients",
    )


# ─────────────────────────────────────────────────────────────
# OWNERS — NEW
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners/new", methods=["GET", "POST"])
@login_required
def owner_new():
    if request.method == "POST":
        data = {
            "full_name":         request.form.get("full_name", "").strip(),
            "full_name_ar":      request.form.get("full_name_ar", "").strip(),
            "phone":             request.form.get("phone", "").strip(),
            "whatsapp_phone":    request.form.get("whatsapp_phone", "").strip(),
            "email":             request.form.get("email", "").strip(),
            "address":           request.form.get("address", "").strip(),
            "address_ar":        request.form.get("address_ar", "").strip(),
            "preferred_contact": request.form.get("preferred_contact", "WhatsApp"),
            "preferred_doctor":  request.form.get("preferred_doctor", "").strip(),
            "vip_flag":          1 if request.form.get("vip_flag") else 0,
            "marketing_consent": 1 if request.form.get("marketing_consent") else 0,
            "notes":             request.form.get("notes", "").strip(),
            "created_by":        session["user"].get("username", ""),
        }
        if not data["full_name"]:
            flash("Full name is required.", "danger")
            return render_template("crm/owner_form.html", owner=data, is_edit=False,
                                   active="crm", page_title="New Owner")

        # A refused mobile is a normal thing to happen at a front desk, not a
        # crash. Name who already has it and link straight to them — the person
        # typing almost always meant that client.
        try:
            owner_id = db.create_owner(data)
        except db.DuplicatePhone as dup:
            flash("%s Open %s instead, or use a different number."
                  % (str(dup), dup.owner_name or "that client"), "danger")
            # 409, not 200. A browser renders the body either way, so the person
            # at the form sees no difference — but a script posting here could
            # not tell a refusal from a success while this returned 200, and the
            # New Visit wizard swallowed it, then carried on under the OTHER
            # client's name. A refusal has to be legible to both callers.
            return render_template("crm/owner_form.html", owner=data, is_edit=False,
                                   active="crm", page_title="New Owner",
                                   duplicate_owner_id=dup.owner_id,
                                   duplicate_owner_name=dup.owner_name), 409

        # Save arabic fields inline (not in helper)
        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE owners SET full_name_ar=?, address_ar=? WHERE id=?",
                (data["full_name_ar"], data["address_ar"], owner_id)
            )
        conn.close()

        db.log_audit(
            username=session["user"].get("username", ""),
            role=session["user"].get("role", ""),
            action="create_owner",
            module="crm",
            entity_type="owner",
            entity_id=str(owner_id),
            details=f"Created owner: {data['full_name']}",
        )
        flash(f"Owner '{data['full_name']}' created successfully.", "success")
        return redirect(url_for("crm.owner_detail", owner_id=owner_id))

    return render_template(
        "crm/owner_form.html",
        owner={},
        is_edit=False,
        active="crm",
        page_title="New Owner",
    )


# ─────────────────────────────────────────────────────────────
# OWNERS — DETAIL
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners/<int:owner_id>")
@login_required
def owner_detail(owner_id):
    owner = db.get_owner(owner_id)
    if not owner:
        flash("Owner not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    pets = db.list_pets(owner_id=owner_id)

    conn = get_db()
    stats = _get_owner_stats(conn, owner_id)

    # Recent visits
    rows = conn.execute(
        """SELECT v.id, v.visit_date, v.visit_type, v.chief_complaint,
                  v.status, p.pet_name
           FROM visits v
           JOIN pets p ON p.id = v.pet_id
           WHERE v.owner_id = ?
           ORDER BY v.visit_date DESC
           LIMIT 5""",
        (owner_id,)
    ).fetchall()
    recent_visits = [dict(r) for r in rows]

    # Invoices — the receptionist on the phone about an unpaid bill needs the
    # list, not just the total. Unpaid ones first, then newest.
    invoices = [dict(r) for r in conn.execute(
        """SELECT i.id, i.invoice_number, i.issue_date, i.due_date, i.status,
                  i.total, i.paid_amount, i.due_amount, p.pet_name
           FROM invoices i
           LEFT JOIN pets p ON p.id = i.pet_id
           WHERE i.owner_id = ?
           ORDER BY CASE WHEN i.status IN ('Cancelled','Paid') THEN 1 ELSE 0 END,
                    i.issue_date DESC
           LIMIT 25""",
        (owner_id,)
    ).fetchall()]

    # Appointment history, no-shows included — a client who does not turn up is
    # a fact the desk needs before booking the next slot.
    appointments = [dict(r) for r in conn.execute(
        """SELECT a.id, a.appt_date, a.appt_start, a.appointment_type, a.status,
                  a.doctor_name, p.pet_name
           FROM appointments a
           LEFT JOIN pets p ON p.id = a.pet_id
           WHERE a.owner_id = ?
           ORDER BY a.appt_date DESC, a.appt_start DESC
           LIMIT 25""",
        (owner_id,)
    ).fetchall()]
    appt_totals = conn.execute(
        """SELECT COUNT(*),
                  SUM(CASE WHEN status='No-Show'   THEN 1 ELSE 0 END),
                  SUM(CASE WHEN status='Cancelled' THEN 1 ELSE 0 END)
           FROM appointments WHERE owner_id = ?""",
        (owner_id,)
    ).fetchone()
    appt_stats = {
        "total":     appt_totals[0] or 0,
        "no_shows":  appt_totals[1] or 0,
        "cancelled": appt_totals[2] or 0,
    }

    # Communication history — what was actually sent, and what is queued to go.
    comms = [dict(r) for r in conn.execute(
        """SELECT sent_at AS at, 'WhatsApp' AS channel, status,
                  COALESCE(template_name,'') AS subject, COALESCE(message,'') AS body
           FROM whatsapp_log WHERE owner_id = ?
           ORDER BY sent_at DESC LIMIT 20""",
        (owner_id,)
    ).fetchall()]
    comms += [dict(r) for r in conn.execute(
        """SELECT scheduled_for AS at, COALESCE(channel,'') AS channel, status,
                  COALESCE(reminder_type,'') AS subject, COALESCE(message,'') AS body
           FROM reminders WHERE owner_id = ?
           ORDER BY scheduled_for DESC LIMIT 20""",
        (owner_id,)
    ).fetchall()]
    comms.sort(key=lambda c: c["at"] or "", reverse=True)

    # Loyalty points history (last 30 rows)
    lp_rows = conn.execute(
        """SELECT points, reason, ref_type, created_by, created_at
           FROM loyalty_points WHERE owner_id = ?
           ORDER BY created_at DESC LIMIT 30""",
        (owner_id,)
    ).fetchall()
    loyalty_history = [dict(r) for r in lp_rows]

    # Current balance (read from owners.loyalty_balance; fall back to sum)
    loyalty_balance = (owner.get("loyalty_balance") or 0)
    conn.close()

    # Add age to each pet
    for pet in pets:
        pet["_age"] = _calc_age(pet.get("dob"))
        pet["_emoji"] = _species_emoji(pet.get("species"))

    # Points-to-EGP conversion helper for template
    REDEEM_RATE = 0.5   # 1 point = 0.50 EGP

    return render_template(
        "crm/owner_detail.html",
        owner=owner,
        pets=pets,
        stats=stats,
        recent_visits=recent_visits,
        invoices=invoices,
        appointments=appointments,
        appt_stats=appt_stats,
        comms=comms,
        loyalty_history=loyalty_history,
        loyalty_balance=loyalty_balance,
        redeem_rate=REDEEM_RATE,
        active="crm",
        page_title=owner["full_name"],
    )


# ─────────────────────────────────────────────────────────────
# LOYALTY — REDEEM POINTS
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners/<int:owner_id>/redeem-points", methods=["POST"])
@login_required
def redeem_points(owner_id):
    """Deduct 100 points and create a 50 EGP credit on the owner account."""
    _MIN_REDEEM = 100
    _EGP_VALUE  = 50.0

    owner = db.get_owner(owner_id)
    if not owner:
        flash("Owner not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    balance = int(owner.get("loyalty_balance") or 0)
    if balance < _MIN_REDEEM:
        flash(f"Insufficient points. Need {_MIN_REDEEM}, have {balance}.", "warning")
        return redirect(url_for("crm.owner_detail", owner_id=owner_id))

    actor = session["user"].get("full_name", "")
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO loyalty_points
                   (owner_id, points, reason, ref_type, created_by)
                   VALUES (?,?,?,?,?)""",
                (owner_id, -_MIN_REDEEM,
                 f"Redeemed {_MIN_REDEEM} pts = {_EGP_VALUE} EGP credit",
                 "redemption", actor),
            )
            conn.execute(
                "UPDATE owners SET loyalty_balance = loyalty_balance - ? WHERE id = ?",
                (_MIN_REDEEM, owner_id),
            )
    finally:
        conn.close()

    flash(f"Redeemed {_MIN_REDEEM} points for {_EGP_VALUE} EGP credit. "
          f"Remaining balance: {balance - _MIN_REDEEM} pts.", "success")
    return redirect(url_for("crm.owner_detail", owner_id=owner_id))


# ─────────────────────────────────────────────────────────────
# LOYALTY — MANUAL ADJUST (admin)
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners/<int:owner_id>/adjust-points", methods=["POST"])
@login_required
def adjust_points(owner_id):
    """Admin: manually add or deduct loyalty points."""
    owner = db.get_owner(owner_id)
    if not owner:
        flash("Owner not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    try:
        points = int(request.form.get("points") or 0)
    except ValueError:
        points = 0

    if points == 0:
        flash("Enter a non-zero adjustment.", "warning")
        return redirect(url_for("crm.owner_detail", owner_id=owner_id))

    reason = request.form.get("reason", "Manual adjustment").strip() or "Manual adjustment"
    actor  = session["user"].get("full_name", "")
    conn   = get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO loyalty_points
                   (owner_id, points, reason, ref_type, created_by)
                   VALUES (?,?,?,?,?)""",
                (owner_id, points, reason, "manual", actor),
            )
            conn.execute(
                "UPDATE owners SET loyalty_balance = COALESCE(loyalty_balance,0) + ? WHERE id = ?",
                (points, owner_id),
            )
    finally:
        conn.close()

    action = "Added" if points > 0 else "Deducted"
    flash(f"{action} {abs(points)} loyalty points. Reason: {reason}", "success")
    return redirect(url_for("crm.owner_detail", owner_id=owner_id))


# ─────────────────────────────────────────────────────────────
# OWNERS — PETS JSON (for dynamic dropdowns in booking forms)
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners/<int:owner_id>/pets-json")
@login_required
def owner_pets_json(owner_id):
    pets = db.list_pets(owner_id=owner_id)
    return jsonify({"pets": [dict(p) for p in pets]})


@crm_bp.route("/owners/search-json")
@login_required
def owner_search_json():
    """Type-to-search behind every owner dropdown in the app.

    The dropdowns used to render a capped slice of the table (LIMIT 200-500),
    so once a clinic passed the cap its newer clients were simply unselectable
    — no error, no sign anything was missing. The search here runs against the
    WHOLE table and returns the first 25 matches, so what is reachable is not
    decided by how many owners the clinic has.
    """
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"owners": []})
    # full_name_ar travels with the row so the dropdown can label a client the
    # way the clinic recorded them. Returning only the Latin name meant an
    # Arabic-first clinic typed Arabic, matched, and then read a Latin label -
    # the display half of the same defect loc() exists to fix.
    return jsonify({"owners": [
        {"id": o["id"], "full_name": o["full_name"],
         "full_name_ar": o.get("full_name_ar") or "", "phone": o["phone"]}
        for o in db.list_owners(search=q, limit=25)
    ]})


# ─────────────────────────────────────────────────────────────
# OWNERS — EDIT
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/owners/<int:owner_id>/edit", methods=["GET", "POST"])
@login_required
def owner_edit(owner_id):
    owner = db.get_owner(owner_id)
    if not owner:
        flash("Owner not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    if request.method == "POST":
        data = {
            "full_name":         request.form.get("full_name", "").strip(),
            "phone":             request.form.get("phone", "").strip(),
            "whatsapp_phone":    request.form.get("whatsapp_phone", "").strip(),
            "email":             request.form.get("email", "").strip(),
            "address":           request.form.get("address", "").strip(),
            "preferred_contact": request.form.get("preferred_contact", "WhatsApp"),
            "preferred_doctor":  request.form.get("preferred_doctor", "").strip(),
            "vip_flag":          1 if request.form.get("vip_flag") else 0,
            "marketing_consent": 1 if request.form.get("marketing_consent") else 0,
            "notes":             request.form.get("notes", "").strip(),
        }
        if not data["full_name"]:
            flash("Full name is required.", "danger")
            return render_template("crm/owner_form.html", owner={**owner, **data},
                                   is_edit=True, active="crm",
                                   page_title=f"Edit — {owner['full_name']}")

        # Somebody else may have saved this client while this form was open —
        # far more likely now that one PC can hold five signed-in accounts.
        # Without this the second save silently discards the first, with
        # nothing on screen and nothing in the record to show it happened.
        try:
            conn = get_db()
            try:
                concurrency.guard(conn, "owners", owner_id,
                                  request.form.get("_seen_updated_at"))
            finally:
                conn.close()
        except concurrency.StaleRecord as clash:
            flash(str(clash), "danger")
            return render_template("crm/owner_form.html", owner={**owner, **data},
                                   is_edit=True, active="crm",
                                   page_title=f"Edit — {owner['full_name']}"), 409

        try:
            db.update_owner(owner_id, data)
        except db.DuplicatePhone as dup:
            flash("%s Open %s instead, or use a different number."
                  % (str(dup), dup.owner_name or "that client"), "danger")
            return render_template("crm/owner_form.html", owner={**owner, **data},
                                   is_edit=True, active="crm",
                                   page_title=f"Edit — {owner['full_name']}",
                                   duplicate_owner_id=dup.owner_id,
                                   duplicate_owner_name=dup.owner_name), 409

        # Update arabic fields
        full_name_ar = request.form.get("full_name_ar", "").strip()
        address_ar   = request.form.get("address_ar", "").strip()
        conn = get_db()
        with conn:
            conn.execute(
                "UPDATE owners SET full_name_ar=?, address_ar=? WHERE id=?",
                (full_name_ar, address_ar, owner_id)
            )
        conn.close()

        db.log_audit(
            username=session["user"].get("username", ""),
            role=session["user"].get("role", ""),
            action="update_owner",
            module="crm",
            entity_type="owner",
            entity_id=str(owner_id),
        )
        flash("Owner updated successfully.", "success")
        return redirect(url_for("crm.owner_detail", owner_id=owner_id))

    return render_template(
        "crm/owner_form.html",
        owner=owner,
        is_edit=True,
        active="crm",
        page_title=f"Edit — {owner['full_name']}",
    )


# ─────────────────────────────────────────────────────────────
# PETS — LIST
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/pets/")
@crm_bp.route("/pets")
@login_required
def pets_list():
    q = request.args.get("q", "").strip()
    species = request.args.get("species", "").strip()

    pets = db.list_pets(search=q)

    if species:
        pets = [p for p in pets if (p.get("species") or "").lower() == species.lower()]

    species_options = sorted({p.get("species", "") for p in db.list_pets() if p.get("species")})

    return render_template(
        "crm/pets_list.html",
        pets=pets,
        q=q,
        species=species,
        species_options=species_options,
        active="crm",
        page_title="All Pets",
    )


# ─────────────────────────────────────────────────────────────
# PETS — NEW
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/pets/new", methods=["GET", "POST"])
@login_required
def pet_new():
    owner_id = request.args.get("owner_id") or request.form.get("owner_id")
    if not owner_id:
        flash("Owner ID is required to create a pet.", "danger")
        return redirect(url_for("crm.owners_list"))

    owner_id = int(owner_id)
    owner = db.get_owner(owner_id)
    if not owner:
        flash("Owner not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    if request.method == "POST":
        weight_raw = request.form.get("weight_kg", "").strip()
        data = {
            "owner_id":           owner_id,
            "pet_name":           request.form.get("pet_name", "").strip(),
            "species":            request.form.get("species", "").strip(),
            "breed":              request.form.get("breed", "").strip(),
            "sex":                request.form.get("sex", "Unknown"),
            "dob":                request.form.get("dob", "").strip() or None,
            "weight_kg":          float(weight_raw) if weight_raw else None,
            "color":              request.form.get("color", "").strip(),
            "microchip_id":       request.form.get("microchip_id", "").strip(),
            "neutered":           1 if request.form.get("neutered") else 0,
            "allergies":          request.form.get("allergies", "").strip(),
            "chronic_conditions": request.form.get("chronic_conditions", "").strip(),
            "diet_notes":         request.form.get("diet_notes", "").strip(),
            "insurance_provider": request.form.get("insurance_provider", "").strip(),
            "policy_number":      request.form.get("policy_number", "").strip(),
            "policy_expiry":      request.form.get("policy_expiry", "").strip() or None,
            "notes":              request.form.get("notes", "").strip(),
        }
        if not data["pet_name"]:
            flash("Pet name is required.", "danger")
            return render_template("crm/pet_form.html", pet=data, owner=owner,
                                   is_edit=False, active="crm", page_title="New Pet")

        pet_id = db.create_pet(data)

        # db.create_pet() INSERTs neither diet_notes nor the three insurance
        # columns, so everything typed into the Insurance box on the New Pet
        # form used to vanish and only reappear if somebody edited the pet
        # afterwards. Same follow-up UPDATE pet_edit does. Not wrapped in a
        # swallow: the columns are guaranteed by _ensure_schema, and silently
        # dropping the insurance details is the bug being fixed here.
        conn = get_db()
        with conn:
            conn.execute(
                """UPDATE pets SET diet_notes=?, insurance_provider=?,
                   policy_number=?, policy_expiry=? WHERE id=?""",
                (data["diet_notes"], data["insurance_provider"],
                 data["policy_number"], data["policy_expiry"], pet_id)
            )
        conn.close()

        db.log_audit(
            username=session["user"].get("username", ""),
            role=session["user"].get("role", ""),
            action="create_pet",
            module="crm",
            entity_type="pet",
            entity_id=str(pet_id),
            details=f"Created pet: {data['pet_name']} for owner {owner_id}",
        )
        flash(f"Pet '{data['pet_name']}' added successfully.", "success")
        return redirect(url_for("crm.pet_detail", pet_id=pet_id))

    return render_template(
        "crm/pet_form.html",
        pet={"owner_id": owner_id},
        owner=owner,
        is_edit=False,
        active="crm",
        page_title="New Pet",
    )


# ─────────────────────────────────────────────────────────────
# PETS — DETAIL
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/pets/<int:pet_id>")
@login_required
def pet_detail(pet_id):
    pet = db.get_pet(pet_id)
    if not pet:
        flash("Pet not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    owner = db.get_owner(pet["owner_id"])
    vaccinations = db.list_vaccinations(pet_id=pet_id)

    # Timeline = the six types the model covers + everything else recorded about
    # this animal anywhere in the product. Ten queries in total, all constant —
    # no per-record lookups.
    timeline = db.get_pet_timeline(pet_id)
    for ev in timeline:
        ev["url"] = _model_event_url(ev)

    conn = get_db()
    timeline += _extra_pet_events(conn, pet_id)
    timeline.sort(key=lambda e: e["dt"] or "", reverse=True)

    # Weight history for chart
    weight_rows = conn.execute(
        "SELECT visit_date, weight_kg FROM visits WHERE pet_id=? AND weight_kg IS NOT NULL ORDER BY visit_date ASC LIMIT 20",
        (pet_id,)
    ).fetchall()
    conn.close()
    weight_history = [{"date": r["visit_date"], "weight": r["weight_kg"]} for r in weight_rows]

    pet["_age"] = _calc_age(pet.get("dob"))
    pet["_emoji"] = _species_emoji(pet.get("species"))

    today = date.today()
    today_str = today.strftime("%Y-%m-%d")
    # Thirty days, not "the same day next month".
    #
    # date.replace(month=today.month + 1) raises ValueError whenever that day
    # does not exist in the next month, so the pet file - the screen the demo
    # script calls the moment the sale happens - returned a 500 on 31 January,
    # 31 March, 31 May, 31 AUGUST, 31 October and every 29th-to-31st of a month
    # landing on February. Seven-ish days a year, invisible on all the others,
    # and the next one is three days from the day this was found.
    soon_str  = (today + timedelta(days=30)).strftime("%Y-%m-%d")

    return render_template(
        "crm/pet_detail.html",
        pet=pet,
        owner=owner,
        timeline=timeline,
        vaccinations=vaccinations,
        weight_history=weight_history,
        today_str=today_str,
        soon_str=soon_str,
        active="crm",
        page_title=pet["pet_name"],
    )


# ─────────────────────────────────────────────────────────────
# PETS — EDIT
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/pets/<int:pet_id>/edit", methods=["GET", "POST"])
@login_required
def pet_edit(pet_id):
    pet = db.get_pet(pet_id)
    if not pet:
        flash("Pet not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    owner = db.get_owner(pet["owner_id"])

    if request.method == "POST":
        weight_raw = request.form.get("weight_kg", "").strip()
        data = {
            "pet_name":           request.form.get("pet_name", "").strip(),
            "species":            request.form.get("species", "").strip(),
            "breed":              request.form.get("breed", "").strip(),
            "sex":                request.form.get("sex", "Unknown"),
            "dob":                request.form.get("dob", "").strip() or None,
            "weight_kg":          float(weight_raw) if weight_raw else None,
            "color":              request.form.get("color", "").strip(),
            "microchip_id":       request.form.get("microchip_id", "").strip(),
            "neutered":           1 if request.form.get("neutered") else 0,
            "allergies":          request.form.get("allergies", "").strip(),
            "chronic_conditions": request.form.get("chronic_conditions", "").strip(),
            "insurance_provider": request.form.get("insurance_provider", "").strip(),
            "policy_number":      request.form.get("policy_number", "").strip(),
            "policy_expiry":      request.form.get("policy_expiry", "").strip() or None,
            "notes":              request.form.get("notes", "").strip(),
        }
        if not data["pet_name"]:
            flash("Pet name is required.", "danger")
            return render_template("crm/pet_form.html", pet={**pet, **data},
                                   owner=owner, is_edit=True,
                                   active="crm", page_title=f"Edit — {pet['pet_name']}")

        db.update_pet(pet_id, data)

        # Save diet_notes + insurance fields directly (may not be in update_pet)
        diet_notes = request.form.get("diet_notes", "").strip()
        try:
            conn = get_db()
            with conn:
                conn.execute(
                    """UPDATE pets SET diet_notes=?, insurance_provider=?,
                       policy_number=?, policy_expiry=? WHERE id=?""",
                    (diet_notes, data["insurance_provider"], data["policy_number"],
                     data["policy_expiry"], pet_id)
                )
            conn.close()
        except Exception:
            pass

        db.log_audit(
            username=session["user"].get("username", ""),
            role=session["user"].get("role", ""),
            action="update_pet",
            module="crm",
            entity_type="pet",
            entity_id=str(pet_id),
        )
        flash("Pet updated successfully.", "success")
        return redirect(url_for("crm.pet_detail", pet_id=pet_id))

    return render_template(
        "crm/pet_form.html",
        pet=pet,
        owner=owner,
        is_edit=True,
        active="crm",
        page_title=f"Edit — {pet['pet_name']}",
    )


# ─────────────────────────────────────────────────────────────
# PET MEDICAL HISTORY PDF
# ─────────────────────────────────────────────────────────────

@crm_bp.route("/pets/<int:pet_id>/history.pdf")
@login_required
def pet_history_pdf(pet_id):
    # The Arabic-safe subclass, not the bare FPDF: core Helvetica carries no
    # Arabic glyphs, so `pdf.cell(0, 8, f"Patient: {pet['pet_name']}")` raised
    # FPDFUnicodeEncodingException — a 500 — for every Arabic-named patient.
    # _ArabicFPDF redirects the font and reshapes the text at the boundary, so
    # every cell() below is covered without touching any of them.
    from models.pdf_generator import _ArabicFPDF as FPDF, _clinic_name

    pet = db.get_pet(pet_id)
    if not pet:
        flash("Pet not found.", "danger")
        return redirect(url_for("crm.owners_list"))

    owner = db.get_owner(pet["owner_id"])
    conn  = get_db()

    # `diagnosis` and `treatment` are NOT columns on visits — they live in
    # diagnoses and treatment_plans. Without these two subqueries v.get()
    # returned None for both and the "Medical History Report" has never
    # carried a diagnosis or a treatment plan on any patient.
    # ponytail: first diagnosis per visit; a visit with several would need
    # an aggregate, and GROUP_CONCAT/STRING_AGG is not portable across both
    # engines. One per visit is what the visit form writes.
    visits = [dict(r) for r in conn.execute("""
        SELECT v.*, COUNT(pi.id) rx_items,
               (SELECT d.diagnosis FROM diagnoses d
                 WHERE d.visit_id = v.id ORDER BY d.id LIMIT 1)   AS diagnosis,
               (SELECT tp.plan_text FROM treatment_plans tp
                 WHERE tp.visit_id = v.id ORDER BY tp.id DESC LIMIT 1) AS treatment
        FROM visits v
        LEFT JOIN prescriptions pr ON pr.visit_id=v.id
        LEFT JOIN prescription_items pi ON pi.prescription_id=pr.id
        WHERE v.pet_id=?
        GROUP BY v.id
        ORDER BY v.visit_date DESC
    """, (pet_id,)).fetchall()]

    vaccinations = [dict(r) for r in conn.execute("""
        SELECT * FROM vaccinations WHERE pet_id=? ORDER BY administered_at DESC
    """, (pet_id,)).fetchall()]

    clinic = db.get_clinic()
    conn.close()

    age_str = _calc_age(pet.get("dob")) or "Unknown"

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Clinic header
    pdf.set_font("Helvetica", "B", 16)
    # `clinic_name` is not a column — the row has `name`/`name_ar` — so the
    # fallback fired every time and every history sheet a clinic handed a
    # customer was headed "Animal Hospital". _clinic_name() is the same helper
    # every other document uses, so this page cannot drift from them again.
    pdf.cell(0, 10, _clinic_name(clinic), ln=True, align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 6, "Patient Medical History Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Generated: {date.today().strftime('%d %b %Y')}", ln=True, align="C")
    pdf.ln(4)

    # Divider
    pdf.set_draw_color(30, 120, 90)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Patient info block
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(30, 80, 60)
    pdf.cell(0, 8, f"Patient: {pet['pet_name']}", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    species = pet.get('species', '')
    breed   = pet.get('breed', '')
    pdf.cell(95, 6, f"Species: {species}  |  Breed: {breed}", ln=False)
    pdf.cell(95, 6, f"Sex: {pet.get('sex','Unknown')}  |  Age: {age_str}", ln=True)
    pdf.cell(95, 6, f"Microchip: {pet.get('microchip_id') or 'N/A'}", ln=False)
    neutered = "Yes" if pet.get("neutered") else "No"
    pdf.cell(95, 6, f"Neutered/Spayed: {neutered}", ln=True)
    if pet.get("allergies"):
        pdf.set_text_color(180, 0, 0)
        pdf.cell(0, 6, f"ALLERGIES: {pet['allergies']}", ln=True)
        pdf.set_text_color(0, 0, 0)
    if pet.get("chronic_conditions"):
        pdf.cell(0, 6, f"Chronic Conditions: {pet['chronic_conditions']}", ln=True)

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 80, 60)
    pdf.cell(0, 7, "Owner Information", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 6, f"Name: {owner.get('full_name','')}", ln=False)
    pdf.cell(95, 6, f"Phone: {owner.get('phone','')}", ln=True)

    pdf.ln(4)
    pdf.set_line_width(0.3)
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # Vaccinations
    if vaccinations:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(30, 80, 60)
        pdf.cell(0, 8, f"Vaccination Records ({len(vaccinations)})", ln=True)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(220, 240, 230)
        pdf.cell(60, 6, "Vaccine", border=1, fill=True)
        pdf.cell(35, 6, "Date Given", border=1, fill=True)
        pdf.cell(35, 6, "Next Due", border=1, fill=True)
        pdf.cell(60, 6, "Batch / Notes", border=1, fill=True, ln=True)
        pdf.set_font("Helvetica", "", 9)
        for v in vaccinations:
            pdf.cell(60, 5, str(v.get("vaccine_name") or "")[:40], border=1)
            pdf.cell(35, 5, str(v.get("administered_at") or "")[:10], border=1)
            pdf.cell(35, 5, str(v.get("next_due_at") or "")[:10], border=1)
            batch_note = str(v.get("batch_number") or "") + " " + str(v.get("notes") or "")
            pdf.cell(60, 5, batch_note.strip()[:40], border=1, ln=True)
        pdf.ln(5)

    # Visit history
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 80, 60)
    pdf.cell(0, 8, f"Visit History ({len(visits)} visits)", ln=True)
    pdf.set_text_color(0, 0, 0)

    for v in visits:
        pdf.set_font("Helvetica", "B", 10)
        visit_type = str(v.get("visit_type") or "Visit")
        visit_date = str(v.get("visit_date") or "")
        doctor     = str(v.get("doctor_name") or "")
        pdf.cell(0, 7, f"{visit_date}  -  {visit_type}  (Dr. {doctor})", ln=True)
        pdf.set_font("Helvetica", "", 9)
        weight = v.get("weight_kg")
        if weight:
            pdf.cell(0, 5, f"  Weight: {weight} kg", ln=True)
        if v.get("chief_complaint"):
            pdf.cell(0, 5, f"  Complaint: {str(v['chief_complaint'])[:100]}", ln=True)
        if v.get("diagnosis"):
            pdf.cell(0, 5, f"  Diagnosis: {str(v['diagnosis'])[:100]}", ln=True)
        if v.get("treatment"):
            pdf.cell(0, 5, f"  Treatment: {str(v['treatment'])[:100]}", ln=True)
        if v.get("notes"):
            pdf.cell(0, 5, f"  Notes: {str(v['notes'])[:80]}", ln=True)
        pdf.set_draw_color(220, 220, 220)
        pdf.line(14, pdf.get_y(), 196, pdf.get_y())
        pdf.ln(3)

    resp = make_response(bytes(pdf.output()))
    resp.headers["Content-Type"] = "application/pdf"
    pet_name_safe = (pet["pet_name"] or "pet").replace(" ", "_")
    resp.headers["Content-Disposition"] = f"attachment; filename={pet_name_safe}_medical_history.pdf"
    return resp
