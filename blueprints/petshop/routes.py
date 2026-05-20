"""
Pet Shop & Orders — Full ERP Module
Products, POS orders, stock, finance integration, owner history
"""
from flask import (render_template, request, redirect, url_for,
                   session, flash, current_app, jsonify)
from datetime import datetime
from . import petshop_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _user():
    return session.get("user", {})


def _log(action, entity_type, entity_id, details=""):
    try:
        u = _user()
        db.log_audit(username=u.get("username","?"), role=u.get("role","?"),
                     action=action, module="petshop",
                     entity_type=entity_type, entity_id=str(entity_id), details=details)
    except Exception:
        pass


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_db():
    return db.get_db()


def ensure_petshop_tables():
    conn = _get_db()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ps_categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            name_ar     TEXT,
            description TEXT,
            is_active   INTEGER DEFAULT 1,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ps_products (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id     INTEGER REFERENCES ps_categories(id),
            name            TEXT NOT NULL,
            name_ar         TEXT,
            sku             TEXT UNIQUE,
            barcode         TEXT,
            brand           TEXT,
            species         TEXT DEFAULT 'all',
            description     TEXT,
            cost_price      REAL DEFAULT 0,
            sell_price      REAL DEFAULT 0,
            tax_rate        REAL DEFAULT 0,
            reorder_level   INTEGER DEFAULT 5,
            stock_qty       INTEGER DEFAULT 0,
            unit            TEXT DEFAULT 'unit',
            is_active       INTEGER DEFAULT 1,
            image_url       TEXT,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ps_orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number    TEXT UNIQUE,
            owner_id        INTEGER,
            pet_id          INTEGER,
            source          TEXT DEFAULT 'in-clinic',
            status          TEXT DEFAULT 'draft',
            subtotal        REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            tax_amount      REAL DEFAULT 0,
            total           REAL DEFAULT 0,
            paid_amount     REAL DEFAULT 0,
            change_amount   REAL DEFAULT 0,
            payment_method  TEXT DEFAULT 'Cash',
            payment_ref     TEXT,
            notes           TEXT,
            served_by       TEXT,
            invoice_id      INTEGER,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS ps_order_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id    INTEGER NOT NULL REFERENCES ps_orders(id) ON DELETE CASCADE,
            product_id  INTEGER NOT NULL REFERENCES ps_products(id),
            product_name TEXT,
            qty         REAL DEFAULT 1,
            unit_price  REAL DEFAULT 0,
            discount    REAL DEFAULT 0,
            tax_rate    REAL DEFAULT 0,
            line_total  REAL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ps_stock_movements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id  INTEGER NOT NULL REFERENCES ps_products(id),
            movement    TEXT NOT NULL,
            qty         REAL NOT NULL,
            ref_type    TEXT,
            ref_id      INTEGER,
            notes       TEXT,
            created_by  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """)
    conn.close()


def _next_order_number():
    conn = _get_db()
    row = conn.execute("SELECT MAX(id) FROM ps_orders").fetchone()
    conn.close()
    next_id = (row[0] or 0) + 1
    return f"PS-{datetime.utcnow().strftime('%Y%m')}-{next_id:04d}"


def _deduct_stock(product_id, qty, ref_type, ref_id, username):
    conn = _get_db()
    with conn:
        conn.execute("UPDATE ps_products SET stock_qty = MAX(0, stock_qty - ?) WHERE id=?",
                     (qty, product_id))
        conn.execute(
            "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,ref_id,created_by) VALUES(?,?,?,?,?,?)",
            (product_id, "out", qty, ref_type, ref_id, username)
        )
    conn.close()


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

@petshop_bp.route("/")
@login_required
def index():
    ensure_petshop_tables()
    conn = _get_db()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    stats = {
        "products":      conn.execute("SELECT COUNT(*) FROM ps_products WHERE is_active=1").fetchone()[0],
        "orders_today":  conn.execute("SELECT COUNT(*) FROM ps_orders WHERE date(created_at)=? AND status='paid'", (today,)).fetchone()[0],
        "revenue_today": conn.execute("SELECT COALESCE(SUM(total),0) FROM ps_orders WHERE date(created_at)=? AND status='paid'", (today,)).fetchone()[0],
        "low_stock":     conn.execute("SELECT COUNT(*) FROM ps_products WHERE stock_qty <= reorder_level AND is_active=1").fetchone()[0],
    }
    recent_orders = conn.execute(
        """SELECT o.*, ow.full_name as owner_name FROM ps_orders o
           LEFT JOIN owners ow ON o.owner_id = ow.id
           ORDER BY o.created_at DESC LIMIT 10"""
    ).fetchall()
    low_stock = conn.execute(
        "SELECT * FROM ps_products WHERE stock_qty <= reorder_level AND is_active=1 ORDER BY stock_qty ASC LIMIT 10"
    ).fetchall()
    conn.close()
    return render_template("petshop/dashboard.html",
                           stats=stats,
                           recent_orders=[dict(r) for r in recent_orders],
                           low_stock=[dict(p) for p in low_stock],
                           active="petshop")


# ── PRODUCTS ──────────────────────────────────────────────────────────────────

@petshop_bp.route("/products")
@login_required
def products():
    ensure_petshop_tables()
    conn = _get_db()
    q = request.args.get("q", "")
    cat = request.args.get("cat", "")
    species = request.args.get("species", "")
    query = "SELECT p.*, c.name as cat_name FROM ps_products p LEFT JOIN ps_categories c ON p.category_id=c.id WHERE p.is_active=1"
    params = []
    if q:
        query += " AND (p.name LIKE ? OR p.sku LIKE ? OR p.barcode LIKE ?)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if cat:
        query += " AND p.category_id=?"
        params.append(cat)
    if species:
        query += " AND (p.species=? OR p.species='all')"
        params.append(species)
    query += " ORDER BY p.name"
    products = conn.execute(query, params).fetchall()
    categories = conn.execute("SELECT * FROM ps_categories WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return render_template("petshop/products.html",
                           products=[dict(p) for p in products],
                           categories=[dict(c) for c in categories],
                           q=q, cat=cat, species=species,
                           active="petshop")


@petshop_bp.route("/products/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "receptionist", "support_admin")
def product_new():
    ensure_petshop_tables()
    if request.method == "POST":
        f = request.form
        conn = _get_db()
        try:
            with conn:
                cur = conn.execute(
                    """INSERT INTO ps_products(category_id,name,name_ar,sku,barcode,brand,species,
                          description,cost_price,sell_price,tax_rate,reorder_level,stock_qty,unit)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (f.get("category_id") or None, f.get("name"), f.get("name_ar"),
                     f.get("sku") or None, f.get("barcode"), f.get("brand"),
                     f.get("species","all"), f.get("description"),
                     float(f.get("cost_price") or 0), float(f.get("sell_price") or 0),
                     float(f.get("tax_rate") or 0), int(f.get("reorder_level") or 5),
                     int(f.get("stock_qty") or 0), f.get("unit","unit"))
                )
                pid = cur.lastrowid
                # Record opening stock
                if int(f.get("stock_qty") or 0) > 0:
                    conn.execute(
                        "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,created_by) VALUES(?,?,?,?,?)",
                        (pid, "in", int(f.get("stock_qty") or 0), "opening_stock", _user().get("username","?"))
                    )
            _log("product_created", "product", pid, f"Created: {f.get('name')}")
            flash(f"Product '{f.get('name')}' created.", "success")
            return redirect(url_for("petshop.products"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
        finally:
            conn.close()

    conn = _get_db()
    categories = conn.execute("SELECT * FROM ps_categories WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return render_template("petshop/product_form.html",
                           product=None,
                           categories=[dict(c) for c in categories],
                           active="petshop")


@petshop_bp.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "receptionist", "support_admin")
def product_edit(pid):
    ensure_petshop_tables()
    conn = _get_db()
    product = conn.execute("SELECT * FROM ps_products WHERE id=?", (pid,)).fetchone()
    if not product:
        conn.close()
        flash("Product not found.", "danger")
        return redirect(url_for("petshop.products"))

    if request.method == "POST":
        f = request.form
        try:
            with conn:
                conn.execute(
                    """UPDATE ps_products SET category_id=?,name=?,name_ar=?,sku=?,barcode=?,brand=?,
                          species=?,description=?,cost_price=?,sell_price=?,tax_rate=?,
                          reorder_level=?,unit=?,updated_at=? WHERE id=?""",
                    (f.get("category_id") or None, f.get("name"), f.get("name_ar"),
                     f.get("sku") or None, f.get("barcode"), f.get("brand"),
                     f.get("species","all"), f.get("description"),
                     float(f.get("cost_price") or 0), float(f.get("sell_price") or 0),
                     float(f.get("tax_rate") or 0), int(f.get("reorder_level") or 5),
                     f.get("unit","unit"), _now(), pid)
                )
            _log("product_updated", "product", pid, f"Updated: {f.get('name')}")
            flash("Product updated.", "success")
            conn.close()
            return redirect(url_for("petshop.products"))
        except Exception as e:
            flash(f"Error: {e}", "danger")

    categories = conn.execute("SELECT * FROM ps_categories WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return render_template("petshop/product_form.html",
                           product=dict(product),
                           categories=[dict(c) for c in categories],
                           active="petshop")


@petshop_bp.route("/products/<int:pid>/stock", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def product_stock(pid):
    qty   = int(request.form.get("qty", 0))
    move  = request.form.get("movement", "in")
    notes = request.form.get("notes", "")
    conn  = _get_db()
    with conn:
        if move == "in":
            conn.execute("UPDATE ps_products SET stock_qty = stock_qty + ? WHERE id=?", (qty, pid))
        else:
            conn.execute("UPDATE ps_products SET stock_qty = MAX(0, stock_qty - ?) WHERE id=?", (qty, pid))
        conn.execute(
            "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,notes,created_by) VALUES(?,?,?,?,?,?)",
            (pid, move, qty, "manual_adjustment", notes, _user().get("username","?"))
        )
    conn.close()
    _log("stock_adjusted", "product", pid, f"{move} {qty} units — {notes}")
    flash("Stock updated.", "success")
    return redirect(url_for("petshop.products"))


# ── CATEGORIES ────────────────────────────────────────────────────────────────

@petshop_bp.route("/categories", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def categories():
    ensure_petshop_tables()
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "delete":
            cat_id = request.form.get("cat_id")
            conn = _get_db()
            count = conn.execute("SELECT COUNT(*) FROM ps_products WHERE category_id=?", (cat_id,)).fetchone()[0]
            if count == 0:
                with conn:
                    conn.execute("DELETE FROM ps_categories WHERE id=?", (cat_id,))
                flash("Category deleted.", "success")
            else:
                flash("Cannot delete: category has products.", "danger")
            conn.close()
        else:
            name = request.form.get("name", "").strip()
            if name:
                conn = _get_db()
                with conn:
                    conn.execute("INSERT INTO ps_categories(name, name_ar, description) VALUES(?,?,?)",
                                 (name, request.form.get("name_ar",""), request.form.get("description","")))
                conn.close()
                flash(f"Category '{name}' created.", "success")
        return redirect(url_for("petshop.categories"))

    conn = _get_db()
    cats = conn.execute(
        "SELECT c.*, COUNT(p.id) as product_count FROM ps_categories c "
        "LEFT JOIN ps_products p ON c.id=p.category_id AND p.is_active=1 GROUP BY c.id ORDER BY c.name"
    ).fetchall()
    conn.close()
    return render_template("petshop/categories.html",
                           categories=[dict(c) for c in cats],
                           active="petshop")


# ── ORDERS / POS ──────────────────────────────────────────────────────────────

@petshop_bp.route("/orders")
@login_required
def orders():
    ensure_petshop_tables()
    conn = _get_db()
    status    = request.args.get("status", "")
    q         = request.args.get("q", "")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")
    query = """SELECT o.*,
                      ow.full_name as owner_name,
                      (SELECT COUNT(*) FROM ps_order_items WHERE order_id=o.id) as item_count
               FROM ps_orders o LEFT JOIN owners ow ON o.owner_id=ow.id
               WHERE 1=1"""
    params = []
    if status:
        query += " AND o.status=?"
        params.append(status)
    if q:
        query += " AND (o.order_number LIKE ? OR ow.full_name LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if date_from:
        query += " AND date(o.created_at) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date(o.created_at) <= ?"
        params.append(date_to)
    query += " ORDER BY o.created_at DESC LIMIT 200"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("petshop/orders.html",
                           orders=[dict(o) for o in rows],
                           status=status, q=q,
                           date_from=date_from, date_to=date_to,
                           active="petshop")


@petshop_bp.route("/pos")
@login_required
def pos():
    ensure_petshop_tables()
    conn = _get_db()
    products = conn.execute(
        "SELECT p.*, c.name as cat_name FROM ps_products p "
        "LEFT JOIN ps_categories c ON p.category_id=c.id "
        "WHERE p.is_active=1 AND p.stock_qty > 0 ORDER BY p.name"
    ).fetchall()
    categories = conn.execute("SELECT * FROM ps_categories WHERE is_active=1 ORDER BY name").fetchall()
    conn.close()
    return render_template("petshop/pos.html",
                           products=[dict(p) for p in products],
                           categories=[dict(c) for c in categories],
                           active="petshop")


@petshop_bp.route("/orders/create", methods=["POST"])
@login_required
def order_create():
    ensure_petshop_tables()
    try:
        import json
        data = request.get_json(force=True)
        items      = data.get("items", [])
        owner_id   = data.get("owner_id") or None
        pet_id     = data.get("pet_id") or None
        source     = data.get("source", "in-clinic")
        pay_method = data.get("payment_method", "Cash")
        pay_ref    = data.get("payment_ref", "")
        notes      = data.get("notes", "")
        paid_amt   = float(data.get("paid_amount", 0))
        discount_g = float(data.get("discount_amount", 0))

        if not items:
            return jsonify({"error": "No items"}), 400

        subtotal = sum(float(i["qty"]) * float(i["unit_price"]) for i in items)
        tax_amt  = sum(float(i["qty"]) * float(i["unit_price"]) * float(i.get("tax_rate",0))/100 for i in items)
        total    = subtotal - discount_g + tax_amt
        change   = max(0, paid_amt - total)

        order_num = _next_order_number()
        conn = _get_db()
        with conn:
            cur = conn.execute(
                """INSERT INTO ps_orders(order_number,owner_id,pet_id,source,status,
                      subtotal,discount_amount,tax_amount,total,paid_amount,change_amount,
                      payment_method,payment_ref,notes,served_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (order_num, owner_id, pet_id, source, "paid",
                 subtotal, discount_g, tax_amt, total, paid_amt, change,
                 pay_method, pay_ref, notes, _user().get("username","?"))
            )
            oid = cur.lastrowid
            for item in items:
                qty    = float(item["qty"])
                price  = float(item["unit_price"])
                disc   = float(item.get("discount", 0))
                trate  = float(item.get("tax_rate", 0))
                ltotal = qty * price * (1 - disc/100)
                conn.execute(
                    """INSERT INTO ps_order_items(order_id,product_id,product_name,qty,unit_price,discount,tax_rate,line_total)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (oid, item["product_id"], item["product_name"], qty, price, disc, trate, ltotal)
                )
                # Deduct stock
                conn.execute("UPDATE ps_products SET stock_qty=MAX(0,stock_qty-?) WHERE id=?",
                             (qty, item["product_id"]))
                conn.execute(
                    "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,ref_id,created_by) VALUES(?,?,?,?,?,?)",
                    (item["product_id"], "out", qty, "sale", oid, _user().get("username","?"))
                )
        conn.close()

        # ── Finance bridge: create invoice + payment so revenue shows in accounting ──
        inv_id = None
        try:
            from datetime import date as _date
            inv_data = {
                "owner_id":   owner_id,
                "pet_id":     pet_id,
                "issue_date": _date.today().isoformat(),
                "notes":      f"Pet Shop Order {order_num}",
                "created_by": _user().get("username", ""),
            }
            inv_lines = []
            for item in items:
                qty   = float(item["qty"])
                price = float(item["unit_price"])
                disc  = float(item.get("discount", 0))
                trate = float(item.get("tax_rate", 0))
                lt    = qty * price * (1 - disc / 100) * (1 + trate / 100)
                inv_lines.append({
                    "description": item["product_name"],
                    "quantity":    qty,
                    "unit_price":  price,
                    "discount":    disc,
                    "total":       round(lt, 2),
                    "line_type":   "product",
                })
            inv_id = db.create_invoice(inv_data, inv_lines)
            # Record the payment against the invoice
            if paid_amt > 0 and inv_id:
                db.add_payment(
                    invoice_id=inv_id,
                    owner_id=owner_id or 0,
                    amount=min(paid_amt, total),
                    method=pay_method,
                    reference=pay_ref or order_num,
                    received_by=_user().get("username", ""),
                )
            # Link invoice back to the ps_order
            if inv_id:
                _conn2 = _get_db()
                _conn2.execute("UPDATE ps_orders SET invoice_id=? WHERE id=?", (inv_id, oid))
                _conn2.commit()
                _conn2.close()
        except Exception as _fe:
            # Finance bridge failure is non-fatal — order is already created
            import logging as _logging
            _logging.getLogger(__name__).warning(f"Pet shop finance bridge error: {_fe}")

        _log("order_created", "ps_order", oid, f"Order {order_num}, total={total:.2f}, method={pay_method}")
        return jsonify({"success": True, "order_id": oid, "order_number": order_num,
                        "total": total, "change": change, "invoice_id": inv_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@petshop_bp.route("/orders/<int:oid>")
@login_required
def order_detail(oid):
    ensure_petshop_tables()
    conn = _get_db()
    order = conn.execute(
        "SELECT o.*, ow.full_name as owner_name, ow.phone as owner_phone "
        "FROM ps_orders o LEFT JOIN owners ow ON o.owner_id=ow.id WHERE o.id=?", (oid,)
    ).fetchone()
    if not order:
        conn.close()
        flash("Order not found.", "danger")
        return redirect(url_for("petshop.orders"))
    items = conn.execute("SELECT * FROM ps_order_items WHERE order_id=?", (oid,)).fetchall()
    conn.close()
    return render_template("petshop/order_detail.html",
                           order=dict(order),
                           items=[dict(i) for i in items],
                           active="petshop")


@petshop_bp.route("/orders/<int:oid>/cancel", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def order_cancel(oid):
    conn = _get_db()
    order = conn.execute("SELECT * FROM ps_orders WHERE id=?", (oid,)).fetchone()
    if order and order["status"] not in ("cancelled", "refunded"):
        items = conn.execute("SELECT * FROM ps_order_items WHERE order_id=?", (oid,)).fetchall()
        with conn:
            conn.execute("UPDATE ps_orders SET status='cancelled',updated_at=? WHERE id=?", (_now(), oid))
            for item in items:
                conn.execute("UPDATE ps_products SET stock_qty=stock_qty+? WHERE id=?",
                             (item["qty"], item["product_id"]))
                conn.execute(
                    "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,ref_id,created_by) VALUES(?,?,?,?,?,?)",
                    (item["product_id"], "in", item["qty"], "cancellation", oid, _user().get("username","?"))
                )
    conn.close()
    _log("order_cancelled", "ps_order", oid, f"Order {oid} cancelled, stock restored")
    flash("Order cancelled and stock restored.", "success")
    return redirect(url_for("petshop.order_detail", oid=oid))


# ── REPORTS ───────────────────────────────────────────────────────────────────

@petshop_bp.route("/reports")
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def reports():
    ensure_petshop_tables()
    conn = _get_db()
    date_from = request.args.get("date_from", datetime.utcnow().strftime("%Y-%m-01"))
    date_to   = request.args.get("date_to",   datetime.utcnow().strftime("%Y-%m-%d"))

    # Aggregate stats
    agg = conn.execute(
        """SELECT COUNT(*) as cnt,
                  COALESCE(SUM(total),0) as revenue,
                  COALESCE(SUM(total - discount_amount),0) as net_revenue
           FROM ps_orders WHERE status='paid' AND date(created_at) BETWEEN ? AND ?""",
        (date_from, date_to)
    ).fetchone()
    total_orders   = agg["cnt"]
    total_revenue  = agg["revenue"]

    # Cost = sum of (qty * cost_price) across sold items in period
    total_cost = conn.execute(
        """SELECT COALESCE(SUM(oi.qty * p.cost_price), 0)
           FROM ps_order_items oi
           JOIN ps_orders o ON oi.order_id=o.id
           JOIN ps_products p ON oi.product_id=p.id
           WHERE o.status='paid' AND date(o.created_at) BETWEEN ? AND ?""",
        (date_from, date_to)
    ).fetchone()[0]

    gross_profit  = total_revenue - total_cost
    margin_pct    = (gross_profit / total_revenue * 100) if total_revenue else 0
    avg_order     = (total_revenue / total_orders) if total_orders else 0

    stats = dict(total_orders=total_orders, total_revenue=total_revenue,
                 total_cost=total_cost, gross_profit=gross_profit,
                 margin_pct=margin_pct, avg_order_value=avg_order)

    # Top products
    top_products = conn.execute(
        """SELECT oi.product_name, p.sku,
                  SUM(oi.qty) as qty_sold,
                  SUM(oi.line_total) as revenue
           FROM ps_order_items oi
           JOIN ps_orders o ON oi.order_id=o.id
           LEFT JOIN ps_products p ON oi.product_id=p.id
           WHERE o.status='paid' AND date(o.created_at) BETWEEN ? AND ?
           GROUP BY oi.product_id, oi.product_name, p.sku ORDER BY revenue DESC LIMIT 10""",
        (date_from, date_to)
    ).fetchall()

    # Daily breakdown
    daily = conn.execute(
        """SELECT date(created_at) as order_date,
                  COUNT(*) as order_count,
                  COALESCE(SUM(total),0) as revenue
           FROM ps_orders WHERE status='paid' AND date(created_at) BETWEEN ? AND ?
           GROUP BY date(created_at) ORDER BY order_date DESC""",
        (date_from, date_to)
    ).fetchall()

    # Payment method breakdown
    payment_breakdown = conn.execute(
        """SELECT LOWER(payment_method) as payment_method,
                  COUNT(*) as order_count,
                  COALESCE(SUM(total),0) as revenue
           FROM ps_orders WHERE status='paid' AND date(created_at) BETWEEN ? AND ?
           GROUP BY LOWER(payment_method) ORDER BY revenue DESC""",
        (date_from, date_to)
    ).fetchall()

    low_stock = conn.execute(
        "SELECT * FROM ps_products WHERE stock_qty <= reorder_level AND is_active=1 ORDER BY stock_qty"
    ).fetchall()

    conn.close()
    return render_template("petshop/reports.html",
                           stats=stats,
                           top_products=[dict(p) for p in top_products],
                           daily=[dict(d) for d in daily],
                           payment_breakdown=[dict(p) for p in payment_breakdown],
                           low_stock=[dict(p) for p in low_stock],
                           date_from=date_from, date_to=date_to,
                           active="petshop")


# ── API: product search (for POS autocomplete) ────────────────────────────────

@petshop_bp.route("/api/products/search")
@login_required
def api_search():
    ensure_petshop_tables()
    q = request.args.get("q", "")
    conn = _get_db()
    rows = conn.execute(
        "SELECT id,name,sku,sell_price,stock_qty,tax_rate,unit FROM ps_products "
        "WHERE is_active=1 AND stock_qty>0 AND (name LIKE ? OR sku LIKE ? OR barcode LIKE ?) LIMIT 20",
        (f"%{q}%", f"%{q}%", f"%{q}%")
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ── API: owner search (for POS) ───────────────────────────────────────────────

@petshop_bp.route("/api/owners/search")
@login_required
def api_owners():
    q = request.args.get("q", "")
    conn = _get_db()
    rows = conn.execute(
        "SELECT id,full_name,phone FROM owners WHERE full_name LIKE ? OR phone LIKE ? LIMIT 10",
        (f"%{q}%", f"%{q}%")
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
