"""
Reports & Analytics Blueprint
"""
import csv
import io
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, session, flash, make_response, send_file
from . import reports_bp
from blueprints.auth.routes import login_required, role_required
import models.database as db
from models.excel_export import make_workbook


@reports_bp.route("/")
@login_required
def index():
    return redirect(url_for("reports.dashboard"))


@reports_bp.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_dashboard_stats()
    revenue_by_day = db.get_revenue_by_day(30)
    top_services = db.get_top_services(10)
    return render_template(
        "reports/dashboard.html",
        stats=stats,
        revenue_by_day=revenue_by_day,
        top_services=top_services,
        active="reports",
    )


@reports_bp.route("/clinical")
@login_required
def clinical():
    conn = db.get_db()
    visits_by_type = [dict(r) for r in conn.execute(
        "SELECT visit_type, COUNT(*) as count FROM visits WHERE visit_date >= date('now', '-30 days') GROUP BY visit_type ORDER BY count DESC"
    ).fetchall()]
    top_diagnoses = [dict(r) for r in conn.execute(
        "SELECT diagnosis, COUNT(*) as count FROM diagnoses WHERE created_at >= datetime('now', '-30 days') GROUP BY diagnosis ORDER BY count DESC LIMIT 10"
    ).fetchall()]
    doctor_workload = [dict(r) for r in conn.execute(
        "SELECT doctor_name, COUNT(*) as visits FROM visits WHERE visit_date >= date('now', '-30 days') GROUP BY doctor_name ORDER BY visits DESC"
    ).fetchall()]
    conn.close()
    max_visits = max((r["count"] for r in visits_by_type), default=1)
    max_doc = max((r["visits"] for r in doctor_workload), default=1)
    return render_template(
        "reports/clinical.html",
        visits_by_type=visits_by_type,
        top_diagnoses=top_diagnoses,
        doctor_workload=doctor_workload,
        max_visits=max_visits,
        max_doc=max_doc,
        active="reports",
    )


@reports_bp.route("/financial")
@login_required
def financial():
    date_from = request.args.get("date_from", (date.today() - timedelta(days=30)).isoformat())
    date_to   = request.args.get("date_to",   date.today().isoformat())
    summary = db.get_finance_summary(date_from, date_to)
    revenue_by_day = db.get_revenue_by_day(30)
    # Payment methods breakdown
    conn = db.get_db()
    payment_methods = [dict(r) for r in conn.execute(
        "SELECT method, COUNT(*) as count, COALESCE(SUM(amount),0) as total FROM payments WHERE received_at BETWEEN ? AND ? GROUP BY method ORDER BY total DESC",
        (date_from + " 00:00:00", date_to + " 23:59:59")
    ).fetchall()]
    conn.close()
    total_paid = sum(p["total"] for p in payment_methods) or 1
    for p in payment_methods:
        p["pct"] = round(p["total"] / total_paid * 100, 1)
    return render_template(
        "reports/financial.html",
        summary=summary,
        revenue_by_day=revenue_by_day,
        payment_methods=payment_methods,
        date_from=date_from,
        date_to=date_to,
        active="reports",
    )


@reports_bp.route("/inventory")
@login_required
def inventory_report():
    conn = db.get_db()
    # Value by category
    value_by_cat = [dict(r) for r in conn.execute(
        """SELECT ic.name as category, COUNT(i.id) as item_count,
           COALESCE(SUM(b.quantity * i.cost_price), 0) as stock_value
           FROM item_categories ic
           LEFT JOIN items i ON i.category_id = ic.id AND i.is_active=1
           LEFT JOIN batches b ON b.item_id = i.id
           GROUP BY ic.id, ic.name ORDER BY stock_value DESC"""
    ).fetchall()]
    # Low stock items
    low_stock = [dict(r) for r in conn.execute(
        """SELECT i.name, i.sku, i.unit, i.reorder_level, ic.name as category,
           COALESCE(SUM(b.quantity),0) as stock_qty
           FROM items i
           LEFT JOIN item_categories ic ON ic.id=i.category_id
           LEFT JOIN batches b ON b.item_id=i.id
           WHERE i.is_active=1
           GROUP BY i.id
           HAVING stock_qty <= i.reorder_level
           ORDER BY stock_qty ASC LIMIT 50"""
    ).fetchall()]
    # Expiry alerts
    today = date.today().isoformat()
    exp_30 = (date.today() + timedelta(days=30)).isoformat()
    exp_60 = (date.today() + timedelta(days=60)).isoformat()
    exp_90 = (date.today() + timedelta(days=90)).isoformat()
    expiry_items = [dict(r) for r in conn.execute(
        """SELECT b.*, i.name as item_name, i.unit,
           CASE
             WHEN b.expiry_date <= ? THEN 'critical'
             WHEN b.expiry_date <= ? THEN 'warning'
             ELSE 'notice'
           END as urgency
           FROM batches b JOIN items i ON i.id=b.item_id
           WHERE b.expiry_date <= ? AND b.quantity > 0
           ORDER BY b.expiry_date""",
        (exp_30, exp_60, exp_90)
    ).fetchall()]
    conn.close()
    return render_template(
        "reports/inventory_report.html",
        value_by_cat=value_by_cat,
        low_stock=low_stock,
        expiry_items=expiry_items,
        active="reports",
    )


@reports_bp.route("/inventory/export/xlsx")
@login_required
def inventory_export_xlsx():
    conn = db.get_db()
    today  = date.today().isoformat()
    exp_90 = (date.today() + timedelta(days=90)).isoformat()

    # All active items with stock quantity + value
    items = [dict(r) for r in conn.execute(
        """SELECT i.name, i.sku, ic.name as category, i.unit,
                  COALESCE(SUM(b.quantity),0) as stock_qty,
                  i.reorder_level, i.cost_price,
                  COALESCE(SUM(b.quantity),0)*i.cost_price as stock_value,
                  CASE WHEN COALESCE(SUM(b.quantity),0) <= i.reorder_level
                       THEN 'LOW' ELSE 'OK' END as stock_status
           FROM items i
           LEFT JOIN item_categories ic ON ic.id = i.category_id
           LEFT JOIN batches b ON b.item_id = i.id
           WHERE i.is_active=1
           GROUP BY i.id, i.name, i.sku, ic.name, i.unit, i.reorder_level, i.cost_price
           ORDER BY ic.name, i.name"""
    ).fetchall()]
    conn.close()

    headers = ["Name", "SKU", "Category", "Unit",
               "Stock Qty", "Reorder Level", "Cost Price",
               "Stock Value (EGP)", "Status"]
    rows = [
        [r["name"], r["sku"] or "", r["category"] or "",
         r["unit"] or "", float(r["stock_qty"]),
         float(r["reorder_level"] or 0), float(r["cost_price"] or 0),
         float(r["stock_value"] or 0), r["stock_status"]]
        for r in items
    ]

    try:
        buf = make_workbook(
            title=f"Inventory Report — {today}",
            headers=headers,
            rows=rows,
            sheet_name="Inventory",
        )
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"inventory_report_{today}.xlsx",
        )
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("reports.inventory_report"))


@reports_bp.route("/doctor-revenue")
@login_required
def doctor_revenue():
    """Revenue and commission breakdown per doctor."""
    today       = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    date_from   = request.args.get("date_from", month_start)
    date_to     = request.args.get("date_to",   today)

    conn = db.get_db()
    # Revenue by doctor, grouped
    by_doctor = [dict(r) for r in conn.execute(
        """SELECT i.doctor_name,
                  COUNT(DISTINCT i.id)           AS invoice_count,
                  COALESCE(SUM(i.net_amount), 0) AS total_invoiced,
                  COALESCE(SUM(CASE WHEN i.status='Paid' THEN i.net_amount ELSE 0 END),0) AS collected,
                  COALESCE(SUM(CASE WHEN i.status!='Paid' AND i.status!='Cancelled'
                                    THEN i.net_amount ELSE 0 END), 0)  AS pending
           FROM invoices i
           WHERE i.issue_date BETWEEN ? AND ?
             AND i.status != 'Cancelled'
             AND i.doctor_name IS NOT NULL
             AND i.doctor_name != ''
           GROUP BY i.doctor_name
           ORDER BY total_invoiced DESC""",
        (date_from, date_to)
    ).fetchall()]

    # Revenue by doctor + service type (for breakdown table)
    by_type = [dict(r) for r in conn.execute(
        """SELECT i.doctor_name, il.line_type,
                  COUNT(*)                         AS line_count,
                  COALESCE(SUM(il.total), 0)       AS subtotal
           FROM invoice_lines il
           JOIN invoices i ON i.id = il.invoice_id
           WHERE i.issue_date BETWEEN ? AND ?
             AND i.status != 'Cancelled'
             AND i.doctor_name IS NOT NULL AND i.doctor_name != ''
           GROUP BY i.doctor_name, il.line_type
           ORDER BY i.doctor_name, subtotal DESC""",
        (date_from, date_to)
    ).fetchall()
    ]
    conn.close()

    # Pivot by_type into a dict: {doctor: [{line_type, count, subtotal}]}
    breakdown = {}
    for row in by_type:
        breakdown.setdefault(row["doctor_name"], []).append(row)

    grand_invoiced  = sum(r["total_invoiced"] for r in by_doctor)
    grand_collected = sum(r["collected"] for r in by_doctor)
    grand_pending   = sum(r["pending"] for r in by_doctor)

    return render_template(
        "reports/doctor_revenue.html",
        active="reports",
        page_title="Doctor Revenue Report",
        by_doctor=by_doctor,
        breakdown=breakdown,
        date_from=date_from,
        date_to=date_to,
        grand_invoiced=grand_invoiced,
        grand_collected=grand_collected,
        grand_pending=grand_pending,
        month_label=date.today().strftime("%B %Y"),
    )


@reports_bp.route("/financial/compare")
@login_required
def financial_compare():
    """Period-over-period comparison for financial report."""
    date_to   = request.args.get("date_to",   date.today().isoformat())
    date_from = request.args.get("date_from", (date.today() - timedelta(days=29)).isoformat())
    # Previous period of same length
    from datetime import datetime
    d1 = datetime.fromisoformat(date_from)
    d2 = datetime.fromisoformat(date_to)
    delta = (d2 - d1).days
    prev_to   = (d1 - timedelta(days=1)).isoformat()
    prev_from = (d1 - timedelta(days=delta+1)).isoformat()

    curr = db.get_finance_summary(date_from, date_to)
    prev = db.get_finance_summary(prev_from, prev_to)

    def _pct_change(curr_val, prev_val):
        if not prev_val:
            return None
        return round((curr_val - prev_val) / prev_val * 100, 1)

    revenue_change  = _pct_change(curr.get("total_revenue", 0),  prev.get("total_revenue", 0))
    invoices_change = _pct_change(curr.get("invoice_count", 0),  prev.get("invoice_count", 0))
    paid_change     = _pct_change(curr.get("total_paid", 0),     prev.get("total_paid", 0))

    revenue_by_day = db.get_revenue_by_day(delta + 1 if delta < 90 else 30)

    conn = db.get_db()
    payment_methods = [dict(r) for r in conn.execute(
        "SELECT method, COUNT(*) as count, COALESCE(SUM(amount),0) as total FROM payments WHERE received_at BETWEEN ? AND ? GROUP BY method ORDER BY total DESC",
        (date_from + " 00:00:00", date_to + " 23:59:59")
    ).fetchall()]
    conn.close()
    total_paid_pm = sum(p["total"] for p in payment_methods) or 1
    for p in payment_methods:
        p["pct"] = round(p["total"] / total_paid_pm * 100, 1)

    return render_template(
        "reports/financial.html",
        summary=curr,
        prev_summary=prev,
        revenue_change=revenue_change,
        invoices_change=invoices_change,
        paid_change=paid_change,
        revenue_by_day=revenue_by_day,
        payment_methods=payment_methods,
        date_from=date_from,
        date_to=date_to,
        prev_from=prev_from,
        prev_to=prev_to,
        compare_mode=True,
        active="reports",
    )


@reports_bp.route("/export/csv")
@login_required
def export_csv():
    rtype = request.args.get("type", "owners")
    conn = db.get_db()
    output = io.StringIO()
    writer = csv.writer(output)
    if rtype == "owners":
        rows = conn.execute("SELECT id, full_name, phone, whatsapp_phone, email, address, vip_flag, created_at FROM owners ORDER BY full_name").fetchall()
        writer.writerow(["ID", "Full Name", "Phone", "WhatsApp", "Email", "Address", "VIP", "Created At"])
    elif rtype == "pets":
        rows = conn.execute("SELECT p.id, p.pet_name, p.species, p.breed, p.sex, o.full_name as owner FROM pets p JOIN owners o ON o.id=p.owner_id ORDER BY p.pet_name").fetchall()
        writer.writerow(["ID", "Pet Name", "Species", "Breed", "Sex", "Owner"])
    elif rtype == "visits":
        rows = conn.execute("SELECT v.id, v.visit_date, v.visit_type, p.pet_name, o.full_name as owner, v.doctor_name, v.status FROM visits v JOIN pets p ON p.id=v.pet_id JOIN owners o ON o.id=v.owner_id ORDER BY v.visit_date DESC LIMIT 500").fetchall()
        writer.writerow(["ID", "Date", "Type", "Pet", "Owner", "Doctor", "Status"])
    elif rtype == "invoices":
        rows = conn.execute("SELECT i.invoice_number, i.issue_date, o.full_name as owner, i.total, i.paid_amount, i.due_amount, i.status FROM invoices i JOIN owners o ON o.id=i.owner_id ORDER BY i.issue_date DESC LIMIT 500").fetchall()
        writer.writerow(["Invoice #", "Date", "Owner", "Total", "Paid", "Due", "Status"])
    else:
        rows = []
    conn.close()
    for row in rows:
        writer.writerow(list(row))
    response = make_response(output.getvalue())
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename={rtype}_{date.today().isoformat()}.csv"
    return response
