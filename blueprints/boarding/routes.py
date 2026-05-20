from flask import render_template, request, redirect, url_for, flash, session
from datetime import date, timedelta
from . import boarding_bp
from blueprints.auth.routes import login_required
from models.database import get_db
import models.database as db


@boarding_bp.route("/")
@login_required
def dashboard():
    conn = get_db()

    # Get rooms + current occupant (PostgreSQL-safe: no non-aggregate cols in GROUP BY)
    rooms = conn.execute(
        """SELECT br.id, br.name AS room_number, br.room_type, br.capacity,
                  br.price_per_night AS daily_rate, br.is_active,
                  bb.id AS booking_id, bb.status AS booking_status,
                  bb.check_in AS checkin_date, bb.check_out AS expected_checkout,
                  p.pet_name, o.full_name AS owner_name
           FROM boarding_rooms br
           LEFT JOIN boarding_bookings bb ON bb.id = (
               SELECT id FROM boarding_bookings
               WHERE room_id = br.id AND status = 'Checked-in'
               ORDER BY check_in DESC LIMIT 1
           )
           LEFT JOIN pets p ON p.id = bb.pet_id
           LEFT JOIN owners o ON o.id = bb.owner_id
           WHERE br.is_active = 1
           ORDER BY br.name"""
    ).fetchall()
    # Compute active_bookings count separately to keep query clean
    for i, r in enumerate(rooms):
        rooms[i] = dict(r)
        rooms[i]["active_bookings"] = 1 if r["booking_id"] else 0

    total_rooms = len(rooms)
    occupied = sum(1 for r in rooms if r["active_bookings"] > 0)
    available = total_rooms - occupied

    today = date.today().isoformat()
    checkout_today = conn.execute(
        "SELECT COUNT(*) FROM boarding_bookings WHERE SUBSTRING(check_out::text, 1, 10) = ? AND status = 'Checked-in'",
        [today]
    ).fetchone()[0]

    conn.close()
    return render_template(
        "boarding/dashboard.html",
        rooms=rooms,
        total_rooms=total_rooms,
        occupied=occupied,
        available=available,
        checkout_today=checkout_today,
        active="boarding",
    )


@boarding_bp.route("/bookings")
@login_required
def bookings_list():
    conn = get_db()
    status_filter = request.args.get("status", "All")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = """
        SELECT bb.id, bb.status, bb.invoice_id,
               bb.check_in            AS checkin_date,
               bb.check_out           AS expected_checkout,
               bb.actual_checkout,
               bb.feeding_instructions   AS diet_notes,
               bb.medication_instructions AS medication_notes,
               bb.vet_notes           AS notes,
               p.pet_name, p.species,
               o.full_name AS owner_name, o.phone,
               br.name     AS room_number, br.room_type,
               br.price_per_night     AS daily_rate
        FROM boarding_bookings bb
        JOIN pets   p  ON p.id  = bb.pet_id
        JOIN owners o  ON o.id  = bb.owner_id
        LEFT JOIN boarding_rooms br ON br.id = bb.room_id
        WHERE 1=1
    """
    params = []

    if status_filter and status_filter != "All":
        query += " AND bb.status = ?"
        params.append(status_filter)
    if date_from:
        query += " AND SUBSTRING(bb.check_in::text, 1, 10) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND SUBSTRING(bb.check_in::text, 1, 10) <= ?"
        params.append(date_to)

    query += " ORDER BY bb.check_in DESC LIMIT 100"
    bookings = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "boarding/bookings_list.html",
        bookings=bookings,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        active="boarding",
    )


@boarding_bp.route("/bookings/new", methods=["GET"])
@login_required
def booking_new_form():
    conn = get_db()
    owners = conn.execute(
        "SELECT id, full_name, phone FROM owners ORDER BY full_name LIMIT 300"
    ).fetchall()
    rooms = conn.execute(
        """SELECT id, name AS room_number, room_type, price_per_night AS daily_rate
           FROM boarding_rooms WHERE is_active = 1 ORDER BY name"""
    ).fetchall()
    conn.close()
    return render_template(
        "boarding/booking_form.html",
        owners=owners,
        rooms=rooms,
        active="boarding",
    )


@boarding_bp.route("/bookings/new", methods=["POST"])
@login_required
def booking_new_submit():
    conn = get_db()

    pet_id   = request.form.get("pet_id")
    owner_id = request.form.get("owner_id")
    room_id  = request.form.get("room_id") or None
    check_in = request.form.get("checkin_date", "")
    check_out = request.form.get("expected_checkout", "") or None
    diet_notes = request.form.get("diet_notes", "")
    medication_notes = request.form.get("medication_notes", "")
    vet_notes = request.form.get("notes", "")
    status    = request.form.get("status", "Reserved")

    if not pet_id or not owner_id or not check_in:
        flash("Owner, pet, and check-in date are required.", "error")
        conn.close()
        return redirect(url_for("boarding.booking_new_form"))

    conn.execute(
        """INSERT INTO boarding_bookings
               (pet_id, owner_id, room_id, check_in, check_out,
                feeding_instructions, medication_instructions, vet_notes, status)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (pet_id, owner_id, room_id, check_in, check_out,
         diet_notes, medication_notes, vet_notes, status),
    )
    conn.commit()
    conn.close()
    flash("Boarding booking created successfully.", "success")
    return redirect(url_for("boarding.bookings_list"))


@boarding_bp.route("/bookings/<int:booking_id>/edit", methods=["GET"])
@login_required
def booking_edit_form(booking_id):
    conn = get_db()
    booking = conn.execute("""
        SELECT bb.*, p.pet_name, p.species, o.full_name AS owner_name, o.phone
        FROM boarding_bookings bb
        JOIN pets p ON p.id = bb.pet_id
        JOIN owners o ON o.id = bb.owner_id
        WHERE bb.id = ?
    """, (booking_id,)).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("boarding.bookings_list"))
    rooms = conn.execute(
        "SELECT id, name AS room_number, room_type, price_per_night AS daily_rate FROM boarding_rooms WHERE is_active=1 ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template(
        "boarding/booking_edit.html",
        booking=dict(booking),
        rooms=rooms,
        active="boarding",
    )


@boarding_bp.route("/bookings/<int:booking_id>/edit", methods=["POST"])
@login_required
def booking_edit_submit(booking_id):
    conn = get_db()
    room_id           = request.form.get("room_id") or None
    check_in          = request.form.get("checkin_date", "") or None
    check_out         = request.form.get("expected_checkout", "") or None
    status            = request.form.get("status", "Reserved")
    diet_notes        = request.form.get("diet_notes", "")
    medication_notes  = request.form.get("medication_notes", "")
    vet_notes         = request.form.get("notes", "")

    conn.execute("""
        UPDATE boarding_bookings
        SET room_id=?, check_in=?, check_out=?,
            status=?, feeding_instructions=?,
            medication_instructions=?, vet_notes=?
        WHERE id=?
    """, (room_id, check_in, check_out, status,
          diet_notes, medication_notes, vet_notes, booking_id))
    conn.commit()
    conn.close()
    flash("Booking updated successfully.", "success")
    return redirect(url_for("boarding.bookings_list"))


@boarding_bp.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
def booking_cancel(booking_id):
    conn = get_db()
    conn.execute("UPDATE boarding_bookings SET status='Cancelled' WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    flash("Booking cancelled.", "success")
    next_url = request.form.get("next") or url_for("boarding.bookings_list")
    return redirect(next_url)


@boarding_bp.route("/bookings/<int:booking_id>/checkin", methods=["POST"])
@login_required
def checkin(booking_id):
    """Change status from Reserved → Checked-in."""
    conn = get_db()
    today = date.today().isoformat()
    conn.execute(
        "UPDATE boarding_bookings SET status='Checked-in', check_in=COALESCE(check_in, ?) WHERE id=?",
        (today, booking_id),
    )
    conn.commit()
    conn.close()
    flash("Pet checked in successfully.", "success")
    next_url = request.form.get("next") or url_for("boarding.bookings_list")
    return redirect(next_url)


@boarding_bp.route("/bookings/<int:booking_id>/checkout", methods=["POST"])
@login_required
def checkout(booking_id):
    """Check out a pet, calculate the bill, and auto-create an invoice."""
    conn = get_db()
    today = date.today().isoformat()

    booking = conn.execute("""
        SELECT bb.id, bb.owner_id, bb.pet_id, bb.invoice_id,
               bb.check_in, bb.check_out,
               br.price_per_night, br.name AS room_name
        FROM boarding_bookings bb
        LEFT JOIN boarding_rooms br ON br.id = bb.room_id
        WHERE bb.id = ?
    """, (booking_id,)).fetchone()

    inv_id = None
    if booking and not booking["invoice_id"]:
        # Calculate nights stayed
        try:
            checkin_dt = date.fromisoformat(str(booking["check_in"])[:10])
            nights     = max((date.today() - checkin_dt).days, 1)
        except Exception:
            nights = 1

        price_night = float(booking["price_per_night"] or 0)
        total_amt   = round(nights * price_night, 2)
        room_label  = booking["room_name"] or "Room"

        if price_night > 0:
            inv_data = {
                "owner_id":   booking["owner_id"],
                "pet_id":     booking["pet_id"],
                "issue_date": today,
                "notes":      f"Boarding: {room_label} × {nights} night{'s' if nights!=1 else ''}",
                "created_by": session.get("user", {}).get("username", ""),
            }
            lines = [{
                "description": f"Boarding — {room_label} ({nights} night{'s' if nights!=1 else ''})",
                "quantity":    nights,
                "unit_price":  price_night,
                "total":       total_amt,
                "line_type":   "service",
            }]
            try:
                inv_id = db.create_invoice(inv_data, lines)   # uses its own DB conn
                conn.execute(
                    "UPDATE boarding_bookings SET invoice_id=? WHERE id=?",
                    (inv_id, booking_id)
                )
                flash(f"Invoice #{inv_id} created — {nights} night(s) × {price_night:.2f} EGP = {total_amt:.2f} EGP.", "success")
            except Exception as e:
                flash(f"Checked out but invoice creation failed: {e}", "warning")
        else:
            flash(f"Checked out ({nights} night(s)). No room rate set — create invoice manually.", "warning")
    elif booking and booking["invoice_id"]:
        inv_id = booking["invoice_id"]

    # Always mark as checked-out
    conn.execute(
        "UPDATE boarding_bookings SET status='Checked-out', actual_checkout=? WHERE id=?",
        (today, booking_id),
    )
    conn.commit()
    conn.close()

    if inv_id:
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
    flash("Pet checked out.", "success")
    return redirect(url_for("boarding.bookings_list"))


@boarding_bp.route("/bookings/<int:booking_id>/invoice")
@login_required
def booking_invoice(booking_id):
    """Redirect to the invoice for a boarding booking."""
    conn = get_db()
    row = conn.execute(
        "SELECT invoice_id FROM boarding_bookings WHERE id=?", (booking_id,)
    ).fetchone()
    conn.close()
    if row and row["invoice_id"]:
        return redirect(url_for("finance.invoice_detail", inv_id=row["invoice_id"]))
    flash("No invoice linked to this booking yet.", "warning")
    return redirect(request.referrer or url_for("boarding.bookings_list"))


@boarding_bp.route("/rooms")
@login_required
def rooms_list():
    conn = get_db()
    rooms = conn.execute(
        """SELECT br.id, br.name AS room_number, br.room_type, br.capacity,
                  br.price_per_night AS daily_rate, br.is_active,
                  COUNT(bb.id) AS active_bookings
           FROM boarding_rooms br
           LEFT JOIN boarding_bookings bb
               ON bb.room_id = br.id AND bb.status = 'Checked-in'
           GROUP BY br.id ORDER BY br.name"""
    ).fetchall()
    conn.close()
    return render_template(
        "boarding/rooms.html",
        rooms=rooms,
        active="boarding",
    )


@boarding_bp.route("/rooms/new", methods=["POST"])
@login_required
def room_new():
    conn = get_db()
    room_number = request.form.get("room_number", "").strip()
    room_type   = request.form.get("room_type", "Standard")
    capacity    = int(request.form.get("capacity") or 1)
    daily_rate  = float(request.form.get("daily_rate") or 0)
    is_active   = 1 if request.form.get("is_active") else 0

    if not room_number:
        flash("Room name / number is required.", "error")
        conn.close()
        return redirect(url_for("boarding.rooms_list"))

    room_id = request.form.get("room_id")
    if room_id:
        conn.execute(
            """UPDATE boarding_rooms
               SET name=?, room_type=?, capacity=?, price_per_night=?, is_active=?
               WHERE id=?""",
            (room_number, room_type, capacity, daily_rate, is_active, room_id),
        )
        flash("Room updated.", "success")
    else:
        conn.execute(
            """INSERT INTO boarding_rooms (name, room_type, capacity, price_per_night, is_active)
               VALUES (?,?,?,?,?)""",
            (room_number, room_type, capacity, daily_rate, is_active),
        )
        flash("Room added.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("boarding.rooms_list"))
