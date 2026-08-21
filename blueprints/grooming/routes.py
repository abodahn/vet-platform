from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import date, timedelta
from . import grooming_bp
from blueprints.auth.routes import login_required
from models.database import get_db, _try_stmt
import models.database as db


def _ensure_columns(conn):
    """Two columns the UI has always used that the schema never had.

    - grooming_services.description: services.html renders it and posts it, and
      service_new's INSERT/UPDATE named it — so adding or editing ANY grooming
      service raised "no column named description" and 500'd. The whole services
      screen was write-only-broken.
    - grooming_bookings.price_override: see booking_edit_submit.

    Same idiom models/database.py already uses for owners.loyalty_balance and
    the pet insurance columns — _try_stmt logs and returns None instead of
    raising, so every call after the first is a no-op, on both engines.
    """
    _try_stmt(conn, "ALTER TABLE grooming_services ADD COLUMN description TEXT")
    _try_stmt(conn, "ALTER TABLE grooming_bookings ADD COLUMN price_override REAL")


@grooming_bp.route("/")
@login_required
def dashboard():
    conn = get_db()

    today     = date.today().isoformat()
    week_end  = (date.today() + timedelta(days=7)).isoformat()

    today_bookings = conn.execute(
        """SELECT gb.*, p.pet_name, p.species, o.full_name owner_name, o.phone,
           gs.name service_name, gs.duration_min, gs.price
           FROM grooming_bookings gb
           JOIN pets p ON p.id = gb.pet_id
           JOIN owners o ON o.id = gb.owner_id
           LEFT JOIN grooming_services gs ON gs.id = gb.service_id
           WHERE SUBSTRING(gb.booking_date::text, 1, 10) = ?
           ORDER BY gb.booking_date""",
        [today],
    ).fetchall()

    upcoming = conn.execute(
        """SELECT gb.*, p.pet_name, p.species, o.full_name owner_name,
           gs.name service_name, gs.duration_min, gs.price
           FROM grooming_bookings gb
           JOIN pets p ON p.id = gb.pet_id
           JOIN owners o ON o.id = gb.owner_id
           LEFT JOIN grooming_services gs ON gs.id = gb.service_id
           WHERE SUBSTRING(gb.booking_date::text, 1, 10) > ?
             AND SUBSTRING(gb.booking_date::text, 1, 10) <= ?
             AND gb.status NOT IN ('Cancelled')
           ORDER BY gb.booking_date LIMIT 20""",
        [today, week_end],
    ).fetchall()

    stats_today = len(today_bookings)
    stats_week = conn.execute(
        """SELECT COUNT(*) FROM grooming_bookings
           WHERE SUBSTRING(booking_date::text, 1, 10) >= ?
             AND SUBSTRING(booking_date::text, 1, 10) <= ?
             AND status != 'Cancelled'""",
        [today, week_end],
    ).fetchone()[0]
    stats_inprogress = conn.execute(
        "SELECT COUNT(*) FROM grooming_bookings WHERE status='In Progress'"
    ).fetchone()[0]

    conn.close()
    return render_template(
        "grooming/dashboard.html",
        today_bookings=today_bookings,
        upcoming=upcoming,
        stats_today=stats_today,
        stats_week=stats_week,
        stats_inprogress=stats_inprogress,
        active="grooming",
    )


@grooming_bp.route("/bookings")
@login_required
def bookings_list():
    conn = get_db()
    status_filter = request.args.get("status", "All")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")

    query = """
        SELECT gb.id, gb.status, gb.groomer_name, gb.booking_date, gb.notes,
               gb.invoice_id, gb.pet_id, gb.owner_id,
               p.pet_name, p.species,
               o.full_name AS owner_name, o.phone,
               gs.name AS service_name, gs.duration_min, gs.price
        FROM grooming_bookings gb
        JOIN pets p ON p.id = gb.pet_id
        JOIN owners o ON o.id = gb.owner_id
        LEFT JOIN grooming_services gs ON gs.id = gb.service_id
        WHERE 1=1
    """
    params = []

    if status_filter and status_filter != "All":
        query += " AND gb.status = ?"
        params.append(status_filter)
    if date_from:
        query += " AND SUBSTRING(gb.booking_date::text, 1, 10) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND SUBSTRING(gb.booking_date::text, 1, 10) <= ?"
        params.append(date_to)

    query += " ORDER BY gb.booking_date DESC LIMIT 200"
    bookings = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "grooming/bookings_list.html",
        bookings=bookings,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
        active="grooming",
    )


@grooming_bp.route("/bookings/new", methods=["GET"])
@login_required
def booking_new_form():
    conn = get_db()
    # Owner picking is a server-side search (crm.owner_search_json), not a
    # rendered slice of the table — see boarding.booking_new_form.
    owners = []
    services = conn.execute(
        "SELECT * FROM grooming_services WHERE is_active=1 ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template(
        "grooming/booking_form.html",
        owners=owners,
        services=services,
        active="grooming",
    )


@grooming_bp.route("/bookings/new", methods=["POST"])
@login_required
def booking_new_submit():
    user = session.get("user", {})
    conn = get_db()

    pet_id = request.form.get("pet_id")
    owner_id = request.form.get("owner_id")
    service_id = request.form.get("service_id") or None
    groomer_name = request.form.get("groomer_name", "")
    booking_date = request.form.get("booking_date", "")
    status = request.form.get("status", "Scheduled")
    notes = request.form.get("notes", "")

    if not pet_id or not owner_id or not booking_date:
        flash("Owner, pet, and booking date are required.", "error")
        conn.close()
        return redirect(url_for("grooming.booking_new_form"))

    conn.execute(
        """INSERT INTO grooming_bookings(pet_id, owner_id, service_id, groomer_name,
           booking_date, status, notes)
           VALUES(?,?,?,?,?,?,?)""",
        (pet_id, owner_id, service_id, groomer_name, booking_date, status, notes),
    )
    conn.commit()
    conn.close()
    flash("Grooming booking created.", "success")
    return redirect(url_for("grooming.bookings_list"))


@grooming_bp.route("/bookings/<int:booking_id>/edit", methods=["GET"])
@login_required
def booking_edit_form(booking_id):
    conn = get_db()
    booking = conn.execute("""
        SELECT gb.*, p.pet_name, p.species, o.full_name AS owner_name, o.phone
        FROM grooming_bookings gb
        JOIN pets p ON p.id = gb.pet_id
        JOIN owners o ON o.id = gb.owner_id
        WHERE gb.id = ?
    """, (booking_id,)).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("grooming.bookings_list"))
    services = conn.execute(
        "SELECT * FROM grooming_services WHERE is_active=1 ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template(
        "grooming/booking_edit.html",
        booking=dict(booking),
        services=services,
        active="grooming",
    )


@grooming_bp.route("/bookings/<int:booking_id>/edit", methods=["POST"])
@login_required
def booking_edit_submit(booking_id):
    conn = get_db()
    service_id   = request.form.get("service_id") or None
    groomer_name = request.form.get("groomer_name", "")
    booking_date = request.form.get("booking_date", "")
    status       = request.form.get("status", "Scheduled")
    notes        = request.form.get("notes", "")
    price_override = request.form.get("price_override", "")

    # If no booking_date provided keep existing
    if not booking_date:
        flash("Booking date is required.", "error")
        conn.close()
        return redirect(url_for("grooming.booking_edit_form", booking_id=booking_id))

    # The edit form has always offered a price override (booking_edit.html:57).
    # It was parsed into `new_price` and then dropped on the floor: the UPDATE
    # below never mentioned it and grooming_bookings had no column for it, so a
    # receptionist could agree a discount, see "Booking updated", and the
    # invoice would still bill the full catalogue price.
    new_price = None
    if price_override.strip():
        try:
            new_price = float(price_override)
        except ValueError:
            pass

    _ensure_columns(conn)
    conn.execute("""
        UPDATE grooming_bookings
        SET service_id=?, groomer_name=?, booking_date=?,
            status=?, notes=?, price_override=?
        WHERE id=?
    """, (service_id, groomer_name, booking_date, status, notes,
          new_price, booking_id))
    conn.commit()
    conn.close()
    flash("Grooming booking updated.", "success")
    return redirect(url_for("grooming.bookings_list"))


@grooming_bp.route("/bookings/<int:booking_id>/status", methods=["POST"])
@login_required
def update_booking_status(booking_id):
    conn = get_db()
    new_status = request.form.get("status", "Scheduled")

    # Auto-create invoice when a grooming session is marked Completed
    if new_status == "Completed":
        _ensure_columns(conn)
        booking = conn.execute("""
            SELECT gb.id, gb.owner_id, gb.pet_id, gb.invoice_id,
                   gs.name AS service_name, gs.price, gb.price_override,
                   gb.booking_date
            FROM grooming_bookings gb
            LEFT JOIN grooming_services gs ON gs.id = gb.service_id
            WHERE gb.id = ?
        """, (booking_id,)).fetchone()

        if booking and not booking["invoice_id"]:
            # The price agreed on the booking wins over the catalogue price.
            price = float(booking["price_override"]
                          if booking["price_override"] is not None
                          else (booking["price"] or 0))
            inv_data = {
                "owner_id":   booking["owner_id"],
                "pet_id":     booking["pet_id"],
                "issue_date": date.today().isoformat(),
                "notes":      f"Grooming: {booking['service_name'] or 'Grooming Service'}",
                "created_by": session.get("user", {}).get("username", ""),
            }
            lines = [{
                "description": booking["service_name"] or "Grooming Service",
                "quantity":    1,
                "unit_price":  price,
                "total":       price,
                "line_type":   "service",
            }]
            try:
                inv_id = db.create_invoice(inv_data, lines)   # uses its own DB conn
                conn.execute("UPDATE grooming_bookings SET invoice_id=? WHERE id=?", (inv_id, booking_id))
                conn.execute("UPDATE grooming_bookings SET status=? WHERE id=?", (new_status, booking_id))
                conn.commit()
                conn.close()
                flash(f"Grooming completed ✓ — Invoice #{inv_id} generated.", "success")
                return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
            except Exception as e:
                import traceback; traceback.print_exc()
                flash(f"Booking completed but invoice creation failed: {e}", "warning")

    conn.execute(
        "UPDATE grooming_bookings SET status=? WHERE id=?", (new_status, booking_id)
    )
    conn.commit()
    conn.close()
    if new_status != "Completed":
        flash(f"Booking status updated to {new_status}.", "success")

    next_url = request.form.get("next") or request.referrer or url_for("grooming.bookings_list")
    return redirect(next_url)


@grooming_bp.route("/bookings/<int:booking_id>/invoice")
@login_required
def booking_invoice(booking_id):
    """Redirect to the invoice for a grooming booking."""
    conn = get_db()
    row = conn.execute(
        "SELECT invoice_id FROM grooming_bookings WHERE id=?", (booking_id,)
    ).fetchone()
    conn.close()
    if row and row["invoice_id"]:
        return redirect(url_for("finance.invoice_detail", inv_id=row["invoice_id"]))
    flash("No invoice linked to this booking yet.", "warning")
    return redirect(request.referrer or url_for("grooming.bookings_list"))


@grooming_bp.route("/services")
@login_required
def services_list():
    conn = get_db()
    _ensure_columns(conn)
    services = conn.execute(
        "SELECT * FROM grooming_services ORDER BY name"
    ).fetchall()
    conn.close()
    return render_template(
        "grooming/services.html",
        services=services,
        active="grooming",
    )


@grooming_bp.route("/services/new", methods=["POST"])
@login_required
def service_new():
    conn = get_db()
    _ensure_columns(conn)
    name = request.form.get("name", "").strip()
    species = request.form.get("species", "All")
    duration_min = request.form.get("duration_min") or 60
    price = request.form.get("price") or 0
    is_active = 1 if request.form.get("is_active") else 0
    description = request.form.get("description", "")

    if not name:
        flash("Service name is required.", "error")
        conn.close()
        return redirect(url_for("grooming.services_list"))

    service_id = request.form.get("service_id")
    if service_id:
        conn.execute(
            """UPDATE grooming_services SET name=?, species=?, duration_min=?,
               price=?, is_active=?, description=? WHERE id=?""",
            (name, species, duration_min, price, is_active, description, service_id),
        )
        flash("Service updated.", "success")
    else:
        conn.execute(
            """INSERT INTO grooming_services(name, species, duration_min, price, is_active, description)
               VALUES(?,?,?,?,?,?)""",
            (name, species, duration_min, price, is_active, description),
        )
        flash("Service added.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("grooming.services_list"))
