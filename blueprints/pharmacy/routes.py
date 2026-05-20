"""
Pharmacy Dispensing Queue — Premium Animal Hospital Platform
Closes the prescription → dispensing → FEFO stock deduction → audit loop.
"""
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, date
from . import pharmacy_bp
from blueprints.auth.routes import login_required
from models.database import get_db, log_audit
import models.database as db

_DISPENSER_ROLES = ("super_admin","clinic_owner","branch_manager","pharmacist","inventory_mgr","nurse","doctor")

def _can_dispense():
    return session.get("user", {}).get("role") in _DISPENSER_ROLES


@pharmacy_bp.route("/")
@login_required
def index():
    """Dispensing queue — all prescriptions pending full dispensing."""
    conn = get_db()
    prescriptions = conn.execute("""
        SELECT pr.*, v.visit_date, v.doctor_name,
               p.pet_name, p.species,
               o.full_name owner_name, o.phone owner_phone,
               (SELECT COUNT(*) FROM prescription_items pi WHERE pi.prescription_id=pr.id) item_count,
               (SELECT COUNT(*) FROM prescription_items pi WHERE pi.prescription_id=pr.id AND pi.dispensed=1) dispensed_count
        FROM prescriptions pr
        JOIN visits v ON v.id=pr.visit_id
        JOIN pets p ON p.id=pr.pet_id
        JOIN owners o ON o.id=pr.owner_id
        WHERE pr.status != 'Dispensed'
        ORDER BY pr.created_at DESC
        LIMIT 100
    """).fetchall()
    conn.close()
    return render_template(
        "pharmacy/index.html",
        active="pharmacy",
        prescriptions=prescriptions,
    )


@pharmacy_bp.route("/history")
@login_required
def history():
    """Recently dispensed prescriptions."""
    conn = get_db()
    date_from = request.args.get("date_from", (date.today()).isoformat())
    records = conn.execute("""
        SELECT dl.*, pr.status,
               p.pet_name, o.full_name owner_name,
               i.name item_name, i.unit,
               b.batch_number, b.expiry_date
        FROM dispensing_log dl
        JOIN prescription_items pi ON pi.id=dl.prescription_item_id
        JOIN prescriptions pr ON pr.id=pi.prescription_id
        JOIN pets p ON p.id=dl.pet_id
        JOIN owners o ON o.id=(SELECT owner_id FROM pets WHERE id=dl.pet_id)
        JOIN items i ON i.id=dl.item_id
        LEFT JOIN batches b ON b.id=dl.batch_id
        WHERE DATE(dl.dispensed_at) >= ?
        ORDER BY dl.dispensed_at DESC
        LIMIT 200
    """, (date_from,)).fetchall()
    conn.close()
    return render_template("pharmacy/history.html", active="pharmacy",
                           records=records, date_from=date_from)


@pharmacy_bp.route("/prescription/<int:rx_id>")
@login_required
def rx_detail(rx_id):
    conn = get_db()
    rx = conn.execute("""
        SELECT pr.*, v.visit_date, v.doctor_name, v.chief_complaint,
               p.pet_name, p.species, p.weight_kg,
               o.full_name owner_name, o.phone
        FROM prescriptions pr
        JOIN visits v ON v.id=pr.visit_id
        JOIN pets p ON p.id=pr.pet_id
        JOIN owners o ON o.id=pr.owner_id
        WHERE pr.id=?
    """, (rx_id,)).fetchone()
    if not rx:
        flash("Prescription not found.", "error")
        conn.close()
        return redirect(url_for("pharmacy.index"))

    items = conn.execute("""
        SELECT pi.*,
               i.name item_name, i.unit, i.is_controlled,
               COALESCE((SELECT SUM(b.quantity) FROM batches b WHERE b.item_id=pi.item_id),0) stock_qty
        FROM prescription_items pi
        LEFT JOIN items i ON i.id=pi.item_id
        WHERE pi.prescription_id=?
    """, (rx_id,)).fetchall()

    # Available batches per item (FEFO order)
    batches_by_item = {}
    for item in items:
        if item["item_id"]:
            batches = conn.execute("""
                SELECT b.*, w.name warehouse_name
                FROM batches b
                LEFT JOIN warehouses w ON w.id=b.warehouse_id
                WHERE b.item_id=? AND b.quantity > 0
                ORDER BY b.expiry_date ASC
            """, (item["item_id"],)).fetchall()
            batches_by_item[item["item_id"]] = [dict(b) for b in batches]

    conn.close()
    return render_template(
        "pharmacy/rx_detail.html",
        active="pharmacy",
        rx=rx, items=items,
        batches_by_item=batches_by_item,
        can_dispense=_can_dispense(),
    )


@pharmacy_bp.route("/dispense/<int:rx_id>", methods=["POST"])
@login_required
def dispense(rx_id):
    if not _can_dispense():
        flash("Access denied.", "error")
        return redirect(url_for("pharmacy.rx_detail", rx_id=rx_id))

    conn = get_db()
    user = session["user"]
    rx = conn.execute("SELECT * FROM prescriptions WHERE id=?", (rx_id,)).fetchone()
    if not rx:
        conn.close()
        flash("Prescription not found.", "error")
        return redirect(url_for("pharmacy.index"))

    items = conn.execute(
        "SELECT * FROM prescription_items WHERE prescription_id=?", (rx_id,)).fetchall()

    errors = []
    dispensed_any = False

    with conn:
        for item in items:
            if item["dispensed"]:
                continue  # already dispensed

            pi_id    = item["id"]
            item_id  = item["item_id"]
            qty_needed = float(item["quantity"] or 0)
            batch_id = request.form.get(f"batch_{pi_id}")
            qty_form = request.form.get(f"qty_{pi_id}")

            if not item_id:
                continue  # free-text item, no inventory

            qty_dispense = float(qty_form) if qty_form else qty_needed

            # Validate batch
            if batch_id:
                batch = conn.execute(
                    "SELECT * FROM batches WHERE id=? AND item_id=?",
                    (batch_id, item_id)).fetchone()
                if not batch:
                    errors.append(f"Invalid batch for {item['medication_name']}")
                    continue
                if batch["quantity"] < qty_dispense:
                    errors.append(f"Insufficient stock in selected batch for {item['medication_name']} (have {batch['quantity']}, need {qty_dispense})")
                    continue
                use_batch_id = int(batch_id)
            else:
                # FEFO: pick oldest expiry batch with enough stock
                fefo = conn.execute(
                    "SELECT * FROM batches WHERE item_id=? AND quantity>=? ORDER BY expiry_date ASC LIMIT 1",
                    (item_id, qty_dispense)).fetchone()
                if not fefo:
                    errors.append(f"Insufficient stock for {item['medication_name']}")
                    continue
                use_batch_id = fefo["id"]
                batch = fefo

            # Deduct stock
            conn.execute("UPDATE batches SET quantity=quantity-? WHERE id=?",
                         (qty_dispense, use_batch_id))

            # Log stock movement
            conn.execute("""
                INSERT INTO stock_movements(item_id,batch_id,movement_type,quantity,
                    reference_type,reference_id,notes,created_by)
                VALUES(?,?,'Dispensed',?,?,?,?,?)
            """, (item_id, use_batch_id, qty_dispense,
                  "prescription", rx_id,
                  f"Dispensed for prescription #{rx_id}",
                  user["username"]))

            # Log in dispensing_log
            conn.execute("""
                INSERT INTO dispensing_log(prescription_item_id,item_id,batch_id,
                    visit_id,pet_id,quantity,dispensed_by,dispensed_at,notes)
                VALUES(?,?,?,?,?,?,?,datetime('now'),?)
            """, (pi_id, item_id, use_batch_id,
                  rx["visit_id"], rx["pet_id"],
                  qty_dispense, user["username"],
                  request.form.get("notes", "")))

            # Mark item as dispensed
            conn.execute("UPDATE prescription_items SET dispensed=1 WHERE id=?", (pi_id,))

            # Controlled drug register
            item_row = conn.execute("SELECT is_controlled FROM items WHERE id=?", (item_id,)).fetchone()
            if item_row and item_row["is_controlled"]:
                conn.execute("""
                    INSERT INTO audit_log(username,role,action,module,entity_type,entity_id,details)
                    VALUES(?,?,?,?,?,?,?)
                """, (user["username"], user["role"], "controlled_drug_dispensed", "pharmacy",
                      "dispensing_log", str(pi_id),
                      f"Item {item_id} qty {qty_dispense} for RX#{rx_id} pet {rx['pet_id']}"))

            dispensed_any = True

    if not errors:
        # Mark prescription as Dispensed if all items done
        all_done = conn.execute(
            "SELECT COUNT(*) FROM prescription_items WHERE prescription_id=? AND dispensed=0",
            (rx_id,)).fetchone()[0] == 0
        new_status = "Dispensed" if all_done else "Partial"
        conn.execute("UPDATE prescriptions SET status=?, dispensed_at=datetime('now') WHERE id=?",
                     (new_status, rx_id))
        conn.commit()
        log_audit(username=user["username"], role=user["role"],
                  action="prescription_dispensed", module="pharmacy",
                  entity_type="prescriptions", entity_id=str(rx_id),
                  details=f"Status={new_status}")
        flash(f"Prescription {'fully' if new_status=='Dispensed' else 'partially'} dispensed.", "success")
    else:
        conn.commit()
        for e in errors:
            flash(e, "error")

    conn.close()
    return redirect(url_for("pharmacy.rx_detail", rx_id=rx_id))


@pharmacy_bp.route("/label/<int:rx_id>/<int:pi_id>")
@login_required
def label(rx_id, pi_id):
    """Print-ready dispensing label."""
    conn = get_db()
    rx = conn.execute("""
        SELECT pr.*, p.pet_name, p.species, p.weight_kg, o.full_name owner_name
        FROM prescriptions pr
        JOIN pets p ON p.id=pr.pet_id
        JOIN owners o ON o.id=pr.owner_id
        WHERE pr.id=?
    """, (rx_id,)).fetchone()
    item = conn.execute("""
        SELECT pi.*, i.name item_name, i.unit
        FROM prescription_items pi
        LEFT JOIN items i ON i.id=pi.item_id
        WHERE pi.id=? AND pi.prescription_id=?
    """, (pi_id, rx_id)).fetchone()
    clinic = db.get_clinic()
    conn.close()
    if not rx or not item:
        flash("Label data not found.", "error")
        return redirect(url_for("pharmacy.rx_detail", rx_id=rx_id))
    return render_template("pharmacy/label.html", rx=rx, item=item, clinic=clinic,
                           dispensed_date=date.today().isoformat())
