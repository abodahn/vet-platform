"""
Custom Report Builder — appended to reports blueprint.
Import this module at bottom of routes.py.
"""
import csv
import io
import json
from datetime import date
from flask import (render_template, request, redirect, url_for,
                   flash, session, make_response)
from . import reports_bp
from blueprints.auth.routes import login_required
import models.database as db

# ── Data sources ──────────────────────────────────────────────────────────────
SOURCES = {
    "invoices": {
        "label": "Invoices",
        "table": "invoices i JOIN owners o ON o.id=i.owner_id LEFT JOIN pets p ON p.id=i.pet_id",
        "cols": {
            "i.id": "Invoice ID", "i.invoice_number": "Invoice #",
            "o.full_name": "Owner Name", "o.phone": "Owner Phone",
            "p.pet_name": "Pet Name", "p.species": "Species",
            "i.issue_date": "Issue Date", "i.status": "Status",
            "i.subtotal": "Subtotal", "i.discount_amount": "Discount",
            "i.total": "Total (EGP)", "i.paid_amount": "Paid",
            "i.due_amount": "Due", "i.doctor_name": "Doctor",
        },
        "date_col": "i.issue_date",
        "status_col": "i.status",
        "status_vals": ["Unpaid", "Paid", "Partial", "Cancelled"],
    },
    "appointments": {
        "label": "Appointments",
        "table": "appointments a JOIN owners o ON o.id=a.owner_id JOIN pets p ON p.id=a.pet_id",
        "cols": {
            "a.id": "ID", "a.appt_date": "Date", "a.appt_time": "Time",
            "o.full_name": "Owner Name", "o.phone": "Phone",
            "p.pet_name": "Pet Name", "p.species": "Species",
            "a.appointment_type": "Type", "a.doctor_name": "Doctor",
            "a.status": "Status", "a.notes": "Notes",
        },
        "date_col": "a.appt_date",
        "status_col": "a.status",
        "status_vals": ["Scheduled", "Confirmed", "Completed", "Cancelled", "No Show"],
    },
    "visits": {
        "label": "Medical Visits",
        "table": "visits v JOIN owners o ON o.id=v.owner_id JOIN pets p ON p.id=v.pet_id",
        "cols": {
            "v.id": "Visit ID", "v.visit_date": "Visit Date",
            "o.full_name": "Owner", "o.phone": "Phone",
            "p.pet_name": "Pet", "p.species": "Species",
            "v.visit_type": "Visit Type", "v.doctor_name": "Doctor",
            "v.status": "Status", "v.chief_complaint": "Chief Complaint",
            "v.weight_kg": "Weight (kg)", "v.temp_c": "Temp (°C)",
        },
        "date_col": "v.visit_date",
        "status_col": "v.status",
        "status_vals": ["Open", "Completed", "Cancelled"],
    },
    "payments": {
        "label": "Payments Received",
        "table": "payments py JOIN owners o ON o.id=py.owner_id LEFT JOIN invoices i ON i.id=py.invoice_id",
        "cols": {
            "py.id": "Payment ID", "py.received_at": "Date",
            "o.full_name": "Owner", "o.phone": "Phone",
            "i.invoice_number": "Invoice #", "py.amount": "Amount (EGP)",
            "py.method": "Method", "py.reference": "Reference",
            "py.received_by": "Received By",
        },
        "date_col": "py.received_at",
        "status_col": None,
        "status_vals": [],
    },
    "owners": {
        "label": "Owners / Clients",
        "table": "owners o",
        "cols": {
            "o.id": "ID", "o.full_name": "Full Name",
            "o.phone": "Phone", "o.email": "Email",
            "o.address": "Address", "o.city": "City",
            "o.created_at": "Joined Date", "o.loyalty_balance": "Loyalty Points",
        },
        "date_col": "o.created_at",
        "status_col": None,
        "status_vals": [],
    },
    "pets": {
        "label": "Patients (Pets)",
        "table": "pets p JOIN owners o ON o.id=p.owner_id",
        "cols": {
            "p.id": "Pet ID", "p.pet_name": "Pet Name", "p.species": "Species",
            "p.breed": "Breed", "p.gender": "Gender", "p.dob": "Date of Birth",
            "p.weight": "Weight", "o.full_name": "Owner", "o.phone": "Owner Phone",
            "p.created_at": "Registered",
        },
        "date_col": "p.created_at",
        "status_col": None,
        "status_vals": [],
    },
    "expenses": {
        "label": "Expenses",
        "table": "expenses",
        "cols": {
            "id": "ID", "expense_date": "Date", "category": "Category",
            "description": "Description", "amount": "Amount (EGP)",
            "vendor": "Vendor", "receipt_ref": "Receipt Ref",
            "created_by": "Created By",
        },
        "date_col": "expense_date",
        "status_col": None,
        "status_vals": [],
    },
    "inventory": {
        "label": "Inventory",
        "table": "inventory_items",
        "cols": {
            "id": "ID", "name": "Product Name", "category": "Category",
            "sku": "SKU", "unit": "Unit", "quantity": "Qty in Stock",
            "reorder_level": "Reorder Level", "unit_price": "Unit Price",
            "supplier": "Supplier",
        },
        "date_col": None,
        "status_col": None,
        "status_vals": [],
    },
}


def _ensure_saved_reports():
    conn = db.get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            source      TEXT NOT NULL,
            config_json TEXT NOT NULL,
            created_by  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


# ── Builder landing ───────────────────────────────────────────────────────────

@reports_bp.route("/builder")
@login_required
def builder():
    _ensure_saved_reports()
    conn = db.get_db()
    saved = []
    try:
        saved = [dict(r) for r in conn.execute(
            "SELECT * FROM saved_reports ORDER BY created_at DESC LIMIT 50"
        ).fetchall()]
    except Exception:
        pass
    finally:
        conn.close()
    return render_template("reports/builder.html",
                           sources=SOURCES, saved=saved, active="reports")


# ── Run a report ──────────────────────────────────────────────────────────────

@reports_bp.route("/builder/run", methods=["POST"])
@login_required
def builder_run():
    _ensure_saved_reports()
    source    = request.form.get("source", "")
    cols      = request.form.getlist("cols")
    date_from = request.form.get("date_from", "")
    date_to   = request.form.get("date_to", "")
    status    = request.form.get("status_filter", "")
    limit     = min(int(request.form.get("limit", 500) or 500), 2000)
    fmt       = request.form.get("format", "html")

    src = SOURCES.get(source)
    if not src or not cols:
        flash("Please select a data source and at least one column.", "warning")
        return redirect(url_for("reports.builder"))

    # Whitelist columns to prevent SQL injection
    allowed    = set(src["cols"].keys())
    safe_cols  = [c for c in cols if c in allowed]
    if not safe_cols:
        flash("No valid columns selected.", "warning")
        return redirect(url_for("reports.builder"))

    col_labels    = [src["cols"][c] for c in safe_cols]
    select_clause = ", ".join(safe_cols)

    query  = f"SELECT {select_clause} FROM {src['table']} WHERE 1=1"
    params = []

    if date_from and src["date_col"]:
        query += f" AND SUBSTRING({src['date_col']}::text,1,10) >= ?"
        params.append(date_from)
    if date_to and src["date_col"]:
        query += f" AND SUBSTRING({src['date_col']}::text,1,10) <= ?"
        params.append(date_to)
    if status and src["status_col"]:
        query += f" AND {src['status_col']} = ?"
        params.append(status)

    query += f" LIMIT {limit}"

    conn = db.get_db()
    try:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    except Exception as e:
        flash(f"Query error: {e}", "error")
        return redirect(url_for("reports.builder"))
    finally:
        conn.close()

    # short key = last segment after dot (for dict lookup)
    def _val(row, col):
        key = col.split(".")[-1]
        return row.get(key, "")

    if fmt == "csv":
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(col_labels)
        for row in rows:
            w.writerow([_val(row, c) for c in safe_cols])
        resp = make_response(out.getvalue())
        resp.headers["Content-Type"] = "text/csv"
        resp.headers["Content-Disposition"] = (
            f'attachment; filename="report_{source}_{date.today()}.csv"'
        )
        return resp

    if fmt == "xlsx":
        try:
            from models.excel_export import make_workbook
            data_rows = [[str(_val(row, c) or "") for c in safe_cols] for row in rows]
            wb = make_workbook(f"{src['label']} Report", col_labels, data_rows)
            resp = make_response(wb.read())
            resp.headers["Content-Type"] = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            resp.headers["Content-Disposition"] = (
                f'attachment; filename="report_{source}_{date.today()}.xlsx"'
            )
            return resp
        except Exception as e:
            flash(f"Excel export error: {e}", "error")

    return render_template(
        "reports/builder_results.html",
        source=source,
        src_label=src["label"],
        col_labels=col_labels,
        safe_cols=safe_cols,
        rows=rows,
        date_from=date_from,
        date_to=date_to,
        status=status,
        limit=limit,
        total=len(rows),
        active="reports",
    )


# ── Save a report ─────────────────────────────────────────────────────────────

@reports_bp.route("/builder/save", methods=["POST"])
@login_required
def builder_save():
    _ensure_saved_reports()
    name   = request.form.get("name", "").strip()
    source = request.form.get("source", "")
    config = {
        "cols":          request.form.getlist("cols"),
        "date_from":     request.form.get("date_from", ""),
        "date_to":       request.form.get("date_to", ""),
        "status_filter": request.form.get("status_filter", ""),
        "limit":         request.form.get("limit", "500"),
    }
    if not name or not source:
        flash("Name and source are required.", "warning")
        return redirect(url_for("reports.builder"))

    conn = db.get_db()
    conn.execute(
        "INSERT INTO saved_reports(name,source,config_json,created_by) VALUES(?,?,?,?)",
        (name, source, json.dumps(config),
         session.get("user", {}).get("username", ""))
    )
    conn.commit()
    conn.close()
    flash(f'Report "{name}" saved.', "success")
    return redirect(url_for("reports.builder"))


# ── Load saved report ─────────────────────────────────────────────────────────

@reports_bp.route("/builder/saved/<int:rid>")
@login_required
def builder_saved(rid):
    _ensure_saved_reports()
    conn = db.get_db()
    row = conn.execute("SELECT * FROM saved_reports WHERE id=?", (rid,)).fetchone()
    conn.close()
    if not row:
        flash("Saved report not found.", "error")
        return redirect(url_for("reports.builder"))

    cfg = json.loads(row["config_json"])
    # Inject config into request.form and call builder_run
    from werkzeug.datastructures import ImmutableMultiDict
    pairs = [("source", row["source"]), ("format", "html")]
    for c in cfg.get("cols", []):
        pairs.append(("cols", c))
    for k in ("date_from", "date_to", "status_filter", "limit"):
        pairs.append((k, cfg.get(k, "")))
    request.form = ImmutableMultiDict(pairs)
    return builder_run()


# ── Delete saved report ───────────────────────────────────────────────────────

@reports_bp.route("/builder/saved/<int:rid>/delete", methods=["POST"])
@login_required
def builder_delete(rid):
    _ensure_saved_reports()
    conn = db.get_db()
    conn.execute("DELETE FROM saved_reports WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    flash("Saved report deleted.", "success")
    return redirect(url_for("reports.builder"))
