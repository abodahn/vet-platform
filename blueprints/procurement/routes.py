from flask import render_template, request, redirect, url_for, flash, session
from datetime import date
from . import procurement_bp
from blueprints.auth.routes import login_required
from models.database import get_db


# ── DASHBOARD ────────────────────────────────────────────────────────────────

@procurement_bp.route("/")
@login_required
def dashboard():
    conn = get_db()

    supplier_count = conn.execute("SELECT COUNT(*) FROM suppliers WHERE is_active=1").fetchone()[0]
    open_po_count  = conn.execute(
        "SELECT COUNT(*) FROM purchase_orders WHERE status IN ('Draft','Sent')"
    ).fetchone()[0]
    month_start = date.today().replace(day=1).isoformat()
    received_this_month = conn.execute(
        "SELECT COUNT(*) FROM purchase_orders WHERE status='Received' AND order_date >= ?",
        (month_start,)
    ).fetchone()[0]
    total_spend = conn.execute(
        "SELECT COALESCE(SUM(total),0) FROM purchase_orders WHERE status='Received' AND order_date >= ?",
        (month_start,)
    ).fetchone()[0] or 0.0

    recent_pos = conn.execute(
        """SELECT po.*, s.name AS supplier_name,
                  (SELECT COUNT(*) FROM po_lines WHERE po_id = po.id) AS item_count
           FROM purchase_orders po
           LEFT JOIN suppliers s ON s.id = po.supplier_id
           ORDER BY po.created_at DESC LIMIT 10"""
    ).fetchall()

    conn.close()
    return render_template(
        "procurement/dashboard.html",
        active="procurement",
        supplier_count=supplier_count,
        open_po_count=open_po_count,
        received_this_month=received_this_month,
        total_spend=total_spend,
        recent_pos=recent_pos,
    )


# ── SUPPLIERS ────────────────────────────────────────────────────────────────

@procurement_bp.route("/suppliers")
@login_required
def suppliers_list():
    conn = get_db()
    suppliers = conn.execute(
        """SELECT s.*,
                  (SELECT COUNT(*) FROM purchase_orders WHERE supplier_id = s.id) AS po_count
           FROM suppliers s ORDER BY s.name"""
    ).fetchall()
    conn.close()
    return render_template("procurement/suppliers_list.html", active="procurement", suppliers=suppliers)


@procurement_bp.route("/suppliers/new", methods=["POST"])
@login_required
def supplier_new():
    conn = get_db()
    name = request.form.get("name", "").strip()
    if not name:
        flash("Supplier name is required.", "error")
        return redirect(url_for("procurement.suppliers_list"))

    conn.execute(
        """INSERT INTO suppliers (name, contact_name, phone, email, address, payment_terms, notes, is_active)
           VALUES (?,?,?,?,?,?,?,1)""",
        (name,
         request.form.get("contact_person", "").strip(),
         request.form.get("phone", "").strip(),
         request.form.get("email", "").strip(),
         request.form.get("address", "").strip(),
         request.form.get("payment_terms", "Net 30").strip(),
         request.form.get("notes", "").strip()),
    )
    conn.commit()
    conn.close()
    flash(f"Supplier '{name}' added.", "success")
    return redirect(url_for("procurement.suppliers_list"))


@procurement_bp.route("/suppliers/<int:supplier_id>")
@login_required
def supplier_detail(supplier_id):
    conn = get_db()
    supplier = conn.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone()
    if not supplier:
        flash("Supplier not found.", "error")
        return redirect(url_for("procurement.suppliers_list"))
    pos = conn.execute(
        "SELECT * FROM purchase_orders WHERE supplier_id=? ORDER BY created_at DESC",
        (supplier_id,)
    ).fetchall()
    conn.close()
    return render_template("procurement/supplier_detail.html", active="procurement",
                           supplier=supplier, pos=pos)


@procurement_bp.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
def supplier_edit(supplier_id):
    conn = get_db()
    supplier = conn.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone()
    if not supplier:
        conn.close()
        flash("Supplier not found.", "error")
        return redirect(url_for("procurement.suppliers_list"))
    if request.method == "POST":
        f = request.form
        name = f.get("name", "").strip()
        if not name:
            flash("Supplier name is required.", "error")
            conn.close()
            return redirect(url_for("procurement.supplier_edit", supplier_id=supplier_id))
        conn.execute(
            """UPDATE suppliers SET name=?, contact_person=?, phone=?, email=?,
               address=?, payment_terms=?, notes=?, is_active=? WHERE id=?""",
            (name,
             f.get("contact_person","").strip(),
             f.get("phone","").strip(),
             f.get("email","").strip(),
             f.get("address","").strip(),
             f.get("payment_terms","Net 30").strip(),
             f.get("notes","").strip(),
             1 if f.get("is_active") else 0,
             supplier_id)
        )
        conn.commit()
        conn.close()
        flash(f"Supplier '{name}' updated.", "success")
        return redirect(url_for("procurement.supplier_detail", supplier_id=supplier_id))
    supplier = dict(supplier)
    conn.close()
    return render_template("procurement/supplier_edit.html", active="procurement",
                           supplier=supplier)


# ── PURCHASE ORDERS ──────────────────────────────────────────────────────────

@procurement_bp.route("/orders")
@login_required
def orders_list():
    conn = get_db()
    status_filter = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")

    q = """SELECT po.*, s.name AS supplier_name,
                  (SELECT COUNT(*) FROM po_lines WHERE po_id = po.id) AS item_count
           FROM purchase_orders po
           LEFT JOIN suppliers s ON s.id = po.supplier_id WHERE 1=1"""
    params = []
    if status_filter and status_filter != "All":
        q += " AND po.status=?"; params.append(status_filter)
    if date_from:
        q += " AND po.order_date>=?"; params.append(date_from)
    if date_to:
        q += " AND po.order_date<=?"; params.append(date_to)
    q += " ORDER BY po.created_at DESC"
    orders = conn.execute(q, params).fetchall()
    conn.close()
    return render_template("procurement/orders_list.html", active="procurement",
                           orders=orders, status_filter=status_filter,
                           date_from=date_from, date_to=date_to)


@procurement_bp.route("/orders/new", methods=["GET"])
@login_required
def order_new_form():
    conn = get_db()
    suppliers = conn.execute("SELECT id, name FROM suppliers WHERE is_active=1 ORDER BY name").fetchall()
    items = conn.execute("SELECT id, name, unit FROM items ORDER BY name").fetchall()
    conn.close()
    return render_template("procurement/order_form.html", active="procurement",
                           suppliers=suppliers, items=items)


@procurement_bp.route("/orders/new", methods=["POST"])
@login_required
def order_new_submit():
    conn = get_db()
    supplier_id   = request.form.get("supplier_id", "").strip()
    expected_date = request.form.get("expected_date", "").strip() or None
    notes         = request.form.get("notes", "").strip()
    status        = request.form.get("status", "Draft").strip()
    user          = session.get("user", {})
    created_by    = user.get("username", "")

    if not supplier_id:
        flash("Please select a supplier.", "error")
        return redirect(url_for("procurement.order_new_form"))

    # Collect line items (indexed form fields: item_id_1, quantity_1, unit_price_1)
    line_items = []
    i = 1
    while True:
        item_id = request.form.get(f"item_id_{i}")
        if item_id is None:
            break
        try:
            qty   = float(request.form.get(f"quantity_{i}", 0) or 0)
            price = float(request.form.get(f"unit_price_{i}", 0) or 0)
        except ValueError:
            qty, price = 0.0, 0.0
        desc = request.form.get(f"description_{i}", "").strip()
        if item_id and qty > 0:
            line_items.append((item_id, desc, qty, price, round(qty * price, 2)))
        i += 1

    if not line_items:
        flash("Please add at least one line item.", "error")
        return redirect(url_for("procurement.order_new_form"))

    total = sum(li[4] for li in line_items)
    # Generate PO number
    n = conn.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    po_number = f"PO-{date.today().year}-{(n+1):05d}"

    cur = conn.execute(
        """INSERT INTO purchase_orders
               (po_number, supplier_id, order_date, expected_date, status, total, notes, created_by)
           VALUES (?,?,date('now'),?,?,?,?,?)""",
        (po_number, supplier_id, expected_date, status, total, notes, created_by),
    )
    po_id = cur.lastrowid
    for item_id, desc, qty, unit_cost, line_total in line_items:
        conn.execute(
            "INSERT INTO po_lines (po_id, item_id, quantity, unit_cost, total) VALUES (?,?,?,?,?)",
            (po_id, item_id, qty, unit_cost, line_total),
        )
    conn.commit()
    conn.close()
    flash(f"Purchase Order {po_number} created.", "success")
    return redirect(url_for("procurement.order_detail", order_id=po_id))


@procurement_bp.route("/orders/<int:order_id>")
@login_required
def order_detail(order_id):
    conn = get_db()
    po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (order_id,)).fetchone()
    if not po:
        flash("Purchase order not found.", "error")
        return redirect(url_for("procurement.orders_list"))
    supplier = conn.execute("SELECT * FROM suppliers WHERE id=?", (po["supplier_id"],)).fetchone()
    lines = conn.execute(
        """SELECT pl.*, i.name AS item_name, i.unit
           FROM po_lines pl LEFT JOIN items i ON i.id = pl.item_id
           WHERE pl.po_id=?""",
        (order_id,)
    ).fetchall()
    conn.close()
    return render_template("procurement/order_detail.html", active="procurement",
                           po=po, supplier=supplier, lines=lines)


@procurement_bp.route("/orders/<int:order_id>/receive", methods=["POST"])
@login_required
def order_receive(order_id):
    conn = get_db()
    user = session.get("user", {})
    po = conn.execute("SELECT * FROM purchase_orders WHERE id=?", (order_id,)).fetchone()
    if not po:
        flash("Purchase order not found.", "error")
        return redirect(url_for("procurement.orders_list"))

    conn.execute("UPDATE purchase_orders SET status='Received', received_date=date('now') WHERE id=?",
                 (order_id,))
    # Add stock movements for each line
    lines = conn.execute("SELECT * FROM po_lines WHERE po_id=?", (order_id,)).fetchall()
    for line in lines:
        if line["item_id"]:
            conn.execute(
                """INSERT INTO stock_movements
                       (item_id, warehouse_id, movement_type, quantity, unit_cost, reference_type, reference_id, created_by)
                   VALUES (?,1,'in',?,?,?,?,?)""",
                (line["item_id"], line["quantity"], line["unit_cost"],
                 "purchase_order", order_id, user.get("username", "")),
            )
            # Also add a batch record
            conn.execute(
                """INSERT INTO batches (item_id, warehouse_id, quantity, unit_cost, received_by)
                   VALUES (?,1,?,?,?)""",
                (line["item_id"], line["quantity"], line["unit_cost"], user.get("username", "")),
            )
    conn.commit()
    conn.close()
    flash(f"Purchase Order #{order_id} marked as Received. Stock updated.", "success")
    return redirect(url_for("procurement.order_detail", order_id=order_id))


@procurement_bp.route("/orders/<int:order_id>/status", methods=["POST"])
@login_required
def order_update_status(order_id):
    conn = get_db()
    new_status = request.form.get("status", "").strip()
    if new_status not in {"Draft", "Sent", "Received", "Cancelled"}:
        flash("Invalid status.", "error")
        return redirect(url_for("procurement.order_detail", order_id=order_id))
    conn.execute("UPDATE purchase_orders SET status=? WHERE id=?", (new_status, order_id))
    conn.commit()
    conn.close()
    flash(f"Status updated to {new_status}.", "success")
    return redirect(url_for("procurement.order_detail", order_id=order_id))
