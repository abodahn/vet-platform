"""
CRM Blueprint — Owners & Pets
Aleefy Platform
"""

from flask import render_template, request, redirect, url_for, flash, session, jsonify
from . import crm_bp
from blueprints.auth.routes import login_required
import models.database as db
from models.database import get_db
from datetime import date, datetime


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


def _get_owner_stats(owner_id):
    """Return aggregate stats for an owner: visit count, last visit, balance."""
    conn = get_db()
    visit_count = conn.execute(
        "SELECT COUNT(*) FROM visits WHERE owner_id=?", (owner_id,)
    ).fetchone()[0]
    last_visit_row = conn.execute(
        "SELECT MAX(visit_date) FROM visits WHERE owner_id=?", (owner_id,)
    ).fetchone()
    last_visit = last_visit_row[0] if last_visit_row else None
    balance = conn.execute(
        "SELECT COALESCE(SUM(due_amount),0) FROM invoices WHERE owner_id=? AND status NOT IN ('Cancelled','Paid')",
        (owner_id,)
    ).fetchone()[0]
    conn.close()
    return {
        "visit_count": visit_count,
        "last_visit": last_visit,
        "balance": float(balance or 0),
    }


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

        owner_id = db.create_owner(data)

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
    stats = _get_owner_stats(owner_id)

    conn = get_db()
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

        db.update_owner(owner_id, data)

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
            "notes":              request.form.get("notes", "").strip(),
        }
        if not data["pet_name"]:
            flash("Pet name is required.", "danger")
            return render_template("crm/pet_form.html", pet=data, owner=owner,
                                   is_edit=False, active="crm", page_title="New Pet")

        pet_id = db.create_pet(data)

        # Save diet_notes inline if column exists
        try:
            conn = get_db()
            with conn:
                conn.execute("UPDATE pets SET diet_notes=? WHERE id=?", (data["diet_notes"], pet_id))
            conn.close()
        except Exception:
            pass

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
    timeline = db.get_pet_timeline(pet_id)
    vaccinations = db.list_vaccinations(pet_id=pet_id)

    # Weight history for chart
    conn = get_db()
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
    soon_str  = (today.replace(month=today.month + 1) if today.month < 12
                 else today.replace(year=today.year + 1, month=1)).strftime("%Y-%m-%d")

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
            "notes":              request.form.get("notes", "").strip(),
        }
        if not data["pet_name"]:
            flash("Pet name is required.", "danger")
            return render_template("crm/pet_form.html", pet={**pet, **data},
                                   owner=owner, is_edit=True,
                                   active="crm", page_title=f"Edit — {pet['pet_name']}")

        db.update_pet(pet_id, data)

        # Save diet_notes
        diet_notes = request.form.get("diet_notes", "").strip()
        try:
            conn = get_db()
            with conn:
                conn.execute("UPDATE pets SET diet_notes=? WHERE id=?", (diet_notes, pet_id))
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
