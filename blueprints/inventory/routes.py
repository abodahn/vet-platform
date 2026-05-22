"""
Inventory / Pharmacy Blueprint — Aleefy Platform
"""

from flask import (
    render_template, request, redirect, url_for,
    session, flash, abort,
)
from datetime import date
from . import inventory_bp
import models.database as db
from blueprints.auth.routes import login_required, role_required


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@inventory_bp.route("/")
@login_required
def dashboard():
    low_stock   = db.get_low_stock_items()
    expiry_30   = db.get_expiry_alerts(days=30)
    movements   = db.list_stock_movements(limit=10)

    conn = db.get_db()
    total_items = conn.execute(
        "SELECT COUNT(*) FROM items WHERE is_active=1").fetchone()[0]
    total_value_row = conn.execute(
        "SELECT COALESCE(SUM(b.quantity * b.unit_cost), 0) "
        "FROM batches b JOIN items i ON i.id = b.item_id "
        "WHERE i.is_active=1 AND b.quantity > 0").fetchone()
    total_value = float(total_value_row[0] or 0)
    conn.close()

    return render_template(
        "inventory/dashboard.html",
        active="inventory",
        page_title="Inventory & Pharmacy",
        low_stock=low_stock,
        expiry_alerts=expiry_30,
        movements=movements,
        total_items=total_items,
        total_value=total_value,
        low_stock_count=len(low_stock),
        expiry_count=len(expiry_30),
    )


# ─────────────────────────────────────────────
# ITEMS LIST
# ─────────────────────────────────────────────

@inventory_bp.route("/items")
@login_required
def items_list():
    search       = request.args.get("q", "").strip()
    category_id  = request.args.get("category_id", "")
    is_medication = request.args.get("is_medication", "")

    categories = db.list_categories()

    conn = db.get_db()
    query = """
        SELECT i.*, ic.name as category_name,
               COALESCE(SUM(b.quantity), 0) as current_stock
        FROM items i
        LEFT JOIN item_categories ic ON i.category_id = ic.id
        LEFT JOIN batches b ON b.item_id = i.id AND b.quantity > 0
        WHERE i.is_active = 1
    """
    params = []
    if search:
        query += " AND (i.name LIKE ? OR i.sku LIKE ? OR i.barcode LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if category_id:
        query += " AND i.category_id = ?"
        params.append(category_id)
    if is_medication == "1":
        query += " AND i.is_medication = 1"
    elif is_medication == "0":
        query += " AND i.is_medication = 0"

    query += " GROUP BY i.id, ic.name ORDER BY i.name"
    items = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()

    return render_template(
        "inventory/items_list.html",
        active="inventory",
        page_title="Inventory Items",
        items=items,
        categories=categories,
        search=search,
        category_id=category_id,
        is_medication=is_medication,
    )


# ─────────────────────────────────────────────
# NEW ITEM
# ─────────────────────────────────────────────

@inventory_bp.route("/items/new", methods=["GET", "POST"])
@login_required
def item_new():
    categories = db.list_categories()

    if request.method == "POST":
        f = request.form
        conn = db.get_db()
        try:
            with conn:
                conn.execute(
                    """INSERT INTO items(category_id, sku, barcode, name, name_ar,
                       unit, cost_price, sell_price, reorder_level, max_stock,
                       is_medication, is_controlled, requires_rx, storage_notes,
                       is_active, created_at, updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,datetime('now'),datetime('now'))""",
                    (
                        f.get("category_id") or None,
                        f.get("sku", "").strip() or None,
                        f.get("barcode", "").strip() or None,
                        f.get("name", "").strip(),
                        f.get("name_ar", "").strip() or None,
                        f.get("unit", "unit").strip(),
                        float(f.get("cost_price") or 0),
                        float(f.get("sell_price") or 0),
                        float(f.get("reorder_level") or 10),
                        float(f.get("max_stock") or 1000),
                        1 if f.get("is_medication") else 0,
                        1 if f.get("is_controlled") else 0,
                        1 if f.get("requires_rx") else 0,
                        f.get("storage_notes", "").strip() or None,
                    )
                )
                item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        except Exception as e:
            flash(f"Error creating item: {e}", "danger")
            conn.close()
            return render_template(
                "inventory/item_form.html",
                active="inventory",
                page_title="New Item",
                categories=categories,
                item=None,
            )
        conn.close()
        flash("Item created successfully.", "success")
        return redirect(url_for("inventory.item_detail", item_id=item_id))

    return render_template(
        "inventory/item_form.html",
        active="inventory",
        page_title="New Item",
        categories=categories,
        item=None,
    )


# ─────────────────────────────────────────────
# ITEM DETAIL
# ─────────────────────────────────────────────

@inventory_bp.route("/items/<int:item_id>")
@login_required
def item_detail(item_id):
    conn = db.get_db()
    item = conn.execute(
        "SELECT i.*, ic.name as category_name "
        "FROM items i LEFT JOIN item_categories ic ON ic.id = i.category_id "
        "WHERE i.id = ?", (item_id,)
    ).fetchone()
    if not item:
        conn.close()
        abort(404)
    item = dict(item)

    batches = [dict(r) for r in conn.execute(
        "SELECT b.*, w.name as warehouse_name "
        "FROM batches b LEFT JOIN warehouses w ON w.id = b.warehouse_id "
        "WHERE b.item_id = ? ORDER BY b.expiry_date ASC NULLS LAST",
        (item_id,)
    ).fetchall()]

    # Stock by warehouse
    stock_by_wh = [dict(r) for r in conn.execute(
        "SELECT w.name as warehouse_name, COALESCE(SUM(b.quantity),0) as qty "
        "FROM batches b JOIN warehouses w ON w.id = b.warehouse_id "
        "WHERE b.item_id = ? AND b.quantity > 0 GROUP BY b.warehouse_id",
        (item_id,)
    ).fetchall()]

    movements = db.list_stock_movements(item_id=item_id, limit=20)
    total_stock = sum(b["quantity"] for b in batches if b["quantity"] > 0)
    conn.close()

    return render_template(
        "inventory/item_detail.html",
        active="inventory",
        page_title=item["name"],
        item=item,
        batches=batches,
        stock_by_wh=stock_by_wh,
        movements=movements,
        total_stock=total_stock,
        today=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# EDIT ITEM
# ─────────────────────────────────────────────

@inventory_bp.route("/items/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def item_edit(item_id):
    categories = db.list_categories()
    conn = db.get_db()
    item = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    if not item:
        conn.close()
        abort(404)
    item = dict(item)

    if request.method == "POST":
        f = request.form
        try:
            with conn:
                conn.execute(
                    """UPDATE items SET category_id=?, sku=?, barcode=?, name=?, name_ar=?,
                       unit=?, cost_price=?, sell_price=?, reorder_level=?, max_stock=?,
                       is_medication=?, is_controlled=?, requires_rx=?, storage_notes=?,
                       updated_at=datetime('now') WHERE id=?""",
                    (
                        f.get("category_id") or None,
                        f.get("sku", "").strip() or None,
                        f.get("barcode", "").strip() or None,
                        f.get("name", "").strip(),
                        f.get("name_ar", "").strip() or None,
                        f.get("unit", "unit").strip(),
                        float(f.get("cost_price") or 0),
                        float(f.get("sell_price") or 0),
                        float(f.get("reorder_level") or 10),
                        float(f.get("max_stock") or 1000),
                        1 if f.get("is_medication") else 0,
                        1 if f.get("is_controlled") else 0,
                        1 if f.get("requires_rx") else 0,
                        f.get("storage_notes", "").strip() or None,
                        item_id,
                    )
                )
        except Exception as e:
            flash(f"Error saving item: {e}", "danger")
            conn.close()
            return render_template(
                "inventory/item_form.html",
                active="inventory",
                page_title=f"Edit: {item['name']}",
                categories=categories,
                item=item,
            )
        conn.close()
        flash("Item updated successfully.", "success")
        return redirect(url_for("inventory.item_detail", item_id=item_id))

    conn.close()
    return render_template(
        "inventory/item_form.html",
        active="inventory",
        page_title=f"Edit: {item['name']}",
        categories=categories,
        item=item,
    )


# ─────────────────────────────────────────────
# RECEIVE STOCK (BATCH)
# ─────────────────────────────────────────────

@inventory_bp.route("/batches/new", methods=["GET", "POST"])
@login_required
def batch_new():
    item_id = request.args.get("item_id", type=int) or request.form.get("item_id", type=int)
    warehouses = db.list_warehouses()

    item = None
    if item_id:
        conn = db.get_db()
        row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
        conn.close()
        item = dict(row) if row else None

    if request.method == "POST":
        f = request.form
        iid = f.get("item_id", type=int)
        wid = f.get("warehouse_id", type=int) or 1
        batch_number   = f.get("batch_number", "").strip()
        expiry_date    = f.get("expiry_date", "").strip() or None
        quantity       = float(f.get("quantity") or 0)
        unit_cost      = float(f.get("unit_cost") or 0)
        received_by    = session["user"].get("full_name", "")

        if not iid or quantity <= 0:
            flash("Item and positive quantity are required.", "danger")
            return redirect(request.referrer or url_for("inventory.items_list"))

        # Also store lot_number, manufacture_date, notes if provided
        conn = db.get_db()
        try:
            with conn:
                cur = conn.execute(
                    """INSERT INTO batches(item_id, warehouse_id, batch_number, lot_number,
                       manufacture_date, expiry_date, quantity, unit_cost, received_by, notes)
                       VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (
                        iid, wid, batch_number or None,
                        f.get("lot_number", "").strip() or None,
                        f.get("manufacture_date", "").strip() or None,
                        expiry_date, quantity, unit_cost, received_by,
                        f.get("notes", "").strip() or None,
                    )
                )
                bid = cur.lastrowid
                conn.execute(
                    """INSERT INTO stock_movements(item_id, batch_id, warehouse_id,
                       movement_type, quantity, unit_cost, reference_type, created_by)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (iid, bid, wid, "in", quantity, unit_cost, "receiving", received_by)
                )
        except Exception as e:
            flash(f"Error receiving stock: {e}", "danger")
            conn.close()
            return redirect(url_for("inventory.item_detail", item_id=iid))
        conn.close()
        flash(f"Stock received: {quantity} units added.", "success")
        return redirect(url_for("inventory.item_detail", item_id=iid))

    return render_template(
        "inventory/batch_form.html",
        active="inventory",
        page_title="Receive Stock",
        item=item,
        item_id=item_id,
        warehouses=warehouses,
        today=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# ALERTS
# ─────────────────────────────────────────────

@inventory_bp.route("/alerts")
@login_required
def alerts():
    low_stock    = db.get_low_stock_items()
    expiry_7     = db.get_expiry_alerts(days=7)
    expiry_30    = db.get_expiry_alerts(days=30)
    today_str    = date.today().isoformat()

    # Mark which are 7-day vs 8-30-day
    for item in expiry_30:
        exp = item.get("expiry_date", "")
        if exp and exp <= (date.today().__str__() if False else
                           (date.today().replace(day=date.today().day)).isoformat()):
            item["urgency"] = "expired"
        elif item in expiry_7:
            item["urgency"] = "critical"
        else:
            item["urgency"] = "warning"

    return render_template(
        "inventory/alerts.html",
        active="inventory",
        page_title="Stock Alerts",
        low_stock=low_stock,
        expiry_alerts=expiry_30,
        expiry_7=expiry_7,
        today=today_str,
    )


# ─────────────────────────────────────────────
# MOVEMENTS LOG
# ─────────────────────────────────────────────

@inventory_bp.route("/movements")
@login_required
def movements():
    item_id  = request.args.get("item_id", type=int)
    mv_type  = request.args.get("type", "")
    limit    = request.args.get("limit", 100, type=int)

    all_movements = db.list_stock_movements(item_id=item_id, limit=limit)
    if mv_type:
        all_movements = [m for m in all_movements if m.get("movement_type") == mv_type]

    # For filter dropdown — get items
    conn = db.get_db()
    items_for_filter = [dict(r) for r in conn.execute(
        "SELECT id, name FROM items WHERE is_active=1 ORDER BY name").fetchall()]
    conn.close()

    return render_template(
        "inventory/movements.html",
        active="inventory",
        page_title="Stock Movements",
        movements=all_movements,
        items_for_filter=items_for_filter,
        item_id=item_id,
        mv_type=mv_type,
    )
