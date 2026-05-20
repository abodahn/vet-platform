"""
Finance Blueprint — Premium Animal Hospital Platform
"""

from flask import (
    render_template, request, redirect, url_for,
    session, flash, abort, send_file,
)
from datetime import date, timedelta
from . import finance_bp
import models.database as db
from blueprints.auth.routes import login_required, role_required
from models.excel_export import make_workbook

# ─────────────────────────────────────────────
# LOYALTY POINTS HELPER
# ─────────────────────────────────────────────
_POINTS_PER_EGP = 1 / 10   # 1 point per 10 EGP
_REDEEM_RATE    = 0.5       # 100 points = 50 EGP  (i.e. 1 point = 0.5 EGP)
_MIN_REDEEM     = 100       # minimum points to redeem


def _award_points(owner_id: int, amount: float, inv_id: int,
                  actor: str = "") -> int:
    """Award loyalty points for a paid invoice. Returns points awarded."""
    points = max(1, int(amount * _POINTS_PER_EGP))
    conn = db.get_db()
    try:
        with conn:
            conn.execute(
                """INSERT INTO loyalty_points
                   (owner_id, points, reason, ref_type, ref_id, created_by)
                   VALUES (?,?,?,?,?,?)""",
                (owner_id, points, f"Invoice #{inv_id} payment",
                 "invoice", inv_id, actor),
            )
            conn.execute(
                """UPDATE owners
                   SET loyalty_balance = COALESCE(loyalty_balance,0) + ?
                   WHERE id = ?""",
                (points, owner_id),
            )
    finally:
        conn.close()
    return points


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@finance_bp.route("/")
@login_required
def dashboard():
    today      = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    today_summary = db.get_finance_summary(date_from=today, date_to=today)
    month_summary = db.get_finance_summary(date_from=month_start, date_to=today)
    revenue_by_day = db.get_revenue_by_day(days=30)

    conn = db.get_db()
    recent_invoices = [dict(r) for r in conn.execute(
        """SELECT i.*, o.full_name as owner_name, p.pet_name
           FROM invoices i
           LEFT JOIN owners o ON i.owner_id = o.id
           LEFT JOIN pets p ON i.pet_id = p.id
           ORDER BY i.created_at DESC LIMIT 10"""
    ).fetchall()]

    outstanding = float(conn.execute(
        "SELECT COALESCE(SUM(due_amount),0) FROM invoices WHERE status IN ('Unpaid','Partial')"
    ).fetchone()[0] or 0)

    paid_count_today = conn.execute(
        "SELECT COUNT(*) FROM payments WHERE received_at LIKE ?", (f"{today}%",)
    ).fetchone()[0]

    conn.close()

    # Build chart data
    max_rev = max((r["revenue"] for r in revenue_by_day), default=1) or 1

    return render_template(
        "finance/dashboard.html",
        active="finance",
        page_title="Finance Dashboard",
        today_revenue=today_summary["revenue"],
        month_revenue=month_summary["revenue"],
        outstanding=outstanding,
        paid_count_today=paid_count_today,
        recent_invoices=recent_invoices,
        revenue_by_day=revenue_by_day,
        max_rev=max_rev,
        today=today,
    )


# ─────────────────────────────────────────────
# INVOICES LIST
# ─────────────────────────────────────────────

@finance_bp.route("/invoices")
@login_required
def invoices_list():
    status    = request.args.get("status", "")
    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")
    search    = request.args.get("q", "").strip()

    invoices = db.list_invoices(
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=200,
    )

    if search:
        sl = search.lower()
        invoices = [i for i in invoices if
                    sl in (i.get("owner_name") or "").lower() or
                    sl in (i.get("invoice_number") or "").lower() or
                    sl in (i.get("pet_name") or "").lower()]

    total_amount = sum(i.get("total", 0) or 0 for i in invoices)
    total_paid   = sum(i.get("paid_amount", 0) or 0 for i in invoices)
    total_due    = sum(i.get("due_amount", 0) or 0 for i in invoices)

    return render_template(
        "finance/invoices_list.html",
        active="finance",
        page_title="Invoices",
        invoices=invoices,
        status=status,
        date_from=date_from,
        date_to=date_to,
        search=search,
        total_amount=total_amount,
        total_paid=total_paid,
        total_due=total_due,
    )


# ─────────────────────────────────────────────
# NEW INVOICE
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/new", methods=["GET", "POST"])
@login_required
def invoice_new():
    conn = db.get_db()
    owners = [dict(r) for r in conn.execute(
        "SELECT id, full_name, phone FROM owners ORDER BY full_name LIMIT 500"
    ).fetchall()]
    pets = [dict(r) for r in conn.execute(
        "SELECT id, owner_id, pet_name, species FROM pets WHERE is_active=1 ORDER BY pet_name"
    ).fetchall()]
    conn.close()

    if request.method == "POST":
        f = request.form
        owner_id = f.get("owner_id", type=int)
        if not owner_id:
            flash("Owner is required.", "danger")
            return render_template(
                "finance/invoice_form.html",
                active="finance",
                page_title="New Invoice",
                owners=owners,
                pets=pets,
                today=date.today().isoformat(),
            )

        descriptions = f.getlist("description[]")
        qtys         = f.getlist("qty[]")
        unit_prices  = f.getlist("unit_price[]")
        discounts    = f.getlist("discount[]")
        line_types   = f.getlist("line_type[]")

        lines = []
        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            qty  = float(qtys[i] if i < len(qtys) else 1) or 1
            up   = float(unit_prices[i] if i < len(unit_prices) else 0) or 0
            disc = float(discounts[i] if i < len(discounts) else 0) or 0
            disc_amt = up * qty * disc / 100
            total = round(qty * up - disc_amt, 2)
            ltype = line_types[i] if i < len(line_types) else "service"
            lines.append({
                "line_type":   ltype,
                "description": desc.strip(),
                "quantity":    qty,
                "unit_price":  up,
                "discount":    disc,
                "total":       total,
            })

        if not lines:
            flash("At least one line item is required.", "danger")
            return render_template(
                "finance/invoice_form.html",
                active="finance",
                page_title="New Invoice",
                owners=owners,
                pets=pets,
                today=date.today().isoformat(),
            )

        data = {
            "owner_id":       owner_id,
            "pet_id":         f.get("pet_id", type=int),
            "visit_id":       f.get("visit_id", type=int),
            "doctor_name":    f.get("doctor_name", "").strip(),
            "issue_date":     f.get("issue_date") or date.today().isoformat(),
            "due_date":       f.get("due_date", "").strip() or None,
            "discount_type":  f.get("discount_type", "value"),
            "discount_value": float(f.get("discount_value") or 0),
            "tax_rate":       float(f.get("tax_rate") or 0),
            "notes":          f.get("notes", "").strip(),
            "created_by":     session["user"].get("full_name", ""),
        }

        try:
            inv_id = db.create_invoice(data, lines)
        except Exception as e:
            flash(f"Error creating invoice: {e}", "danger")
            return render_template(
                "finance/invoice_form.html",
                active="finance",
                page_title="New Invoice",
                owners=owners,
                pets=pets,
                today=date.today().isoformat(),
            )

        flash("Invoice created successfully.", "success")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))

    return render_template(
        "finance/invoice_form.html",
        active="finance",
        page_title="New Invoice",
        owners=owners,
        pets=pets,
        today=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# INVOICE DETAIL
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/<int:inv_id>")
@login_required
def invoice_detail(inv_id):
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)
    return render_template(
        "finance/invoice_detail.html",
        active="finance",
        page_title=f"Invoice {invoice['invoice_number']}",
        invoice=invoice,
        today=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# RECORD PAYMENT
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/<int:inv_id>/pay", methods=["POST"])
@login_required
def invoice_pay(inv_id):
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)

    amount    = float(request.form.get("amount") or 0)
    method    = request.form.get("method", "Cash")
    reference = request.form.get("reference", "").strip()

    if amount <= 0:
        flash("Payment amount must be greater than zero.", "danger")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))

    try:
        db.add_payment(
            invoice_id=inv_id,
            owner_id=invoice["owner_id"],
            amount=amount,
            method=method,
            reference=reference,
            received_by=session["user"].get("full_name", ""),
        )
        # Award loyalty points (1 point per 10 EGP)
        try:
            pts = _award_points(
                owner_id=invoice["owner_id"],
                amount=amount,
                inv_id=inv_id,
                actor=session["user"].get("full_name", ""),
            )
            flash(f"Payment of {amount:.2f} recorded. +{pts} loyalty points awarded.", "success")
        except Exception:
            flash(f"Payment of {amount:.2f} recorded successfully.", "success")
    except Exception as e:
        flash(f"Error recording payment: {e}", "danger")

    return redirect(url_for("finance.invoice_detail", inv_id=inv_id))


# ─────────────────────────────────────────────
# INVOICE EDIT
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/<int:inv_id>/edit", methods=["GET", "POST"])
@login_required
def invoice_edit(inv_id):
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)
    if invoice["status"] == "Paid":
        flash("Paid invoices cannot be edited. Issue a credit note instead.", "warning")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))

    conn = db.get_db()
    owners = [dict(r) for r in conn.execute(
        "SELECT id, full_name, phone FROM owners ORDER BY full_name LIMIT 500"
    ).fetchall()]
    pets = [dict(r) for r in conn.execute(
        "SELECT id, owner_id, pet_name FROM pets WHERE is_active=1 ORDER BY pet_name"
    ).fetchall()]

    if request.method == "POST":
        f = request.form
        descriptions = f.getlist("description[]")
        qtys         = f.getlist("qty[]")
        unit_prices  = f.getlist("unit_price[]")
        discounts    = f.getlist("discount[]")
        line_types   = f.getlist("line_type[]")

        lines = []
        for i, desc in enumerate(descriptions):
            if not desc.strip():
                continue
            qty  = float(qtys[i] if i < len(qtys) else 1) or 1
            up   = float(unit_prices[i] if i < len(unit_prices) else 0) or 0
            disc = float(discounts[i] if i < len(discounts) else 0) or 0
            disc_amt = up * qty * disc / 100
            total = round(qty * up - disc_amt, 2)
            ltype = line_types[i] if i < len(line_types) else "service"
            lines.append({
                "line_type": ltype, "description": desc.strip(),
                "quantity": qty, "unit_price": up,
                "discount": disc, "total": total,
            })

        if not lines:
            flash("At least one line item is required.", "danger")
            conn.close()
            return redirect(url_for("finance.invoice_edit", inv_id=inv_id))

        discount_value = float(f.get("discount_value") or 0)
        tax_rate       = float(f.get("tax_rate") or 0)
        subtotal       = sum(l["total"] for l in lines)
        discount_type  = f.get("discount_type", "value")
        discount_amt   = discount_value if discount_type == "value" else round(subtotal * discount_value / 100, 2)
        tax_amount     = round((subtotal - discount_amt) * tax_rate / 100, 2)
        total          = round(subtotal - discount_amt + tax_amount, 2)
        paid_amount    = float(invoice.get("paid_amount") or 0)
        due_amount     = round(total - paid_amount, 2)
        status         = "Paid" if due_amount <= 0 else ("Partial" if paid_amount > 0 else "Unpaid")

        try:
            # Delete old lines, insert new ones
            conn.execute("DELETE FROM invoice_lines WHERE invoice_id=?", (inv_id,))
            for l in lines:
                conn.execute(
                    """INSERT INTO invoice_lines (invoice_id, line_type, description, quantity,
                       unit_price, discount, total) VALUES (?,?,?,?,?,?,?)""",
                    (inv_id, l["line_type"], l["description"], l["quantity"],
                     l["unit_price"], l["discount"], l["total"])
                )
            conn.execute(
                """UPDATE invoices SET owner_id=?, pet_id=?, doctor_name=?, notes=?,
                   discount_type=?, discount_value=?, discount_amount=?,
                   tax_rate=?, tax_amount=?, subtotal=?, total=?,
                   due_amount=?, status=?, due_date=? WHERE id=?""",
                (f.get("owner_id", type=int) or invoice["owner_id"],
                 f.get("pet_id", type=int),
                 f.get("doctor_name","").strip(),
                 f.get("notes","").strip(),
                 discount_type, discount_value, discount_amt,
                 tax_rate, tax_amount, subtotal, total,
                 due_amount, status,
                 f.get("due_date","") or None,
                 inv_id)
            )
            conn.commit()
            conn.close()
            flash("Invoice updated successfully.", "success")
            return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
        except Exception as e:
            conn.close()
            flash(f"Error updating invoice: {e}", "danger")
            return redirect(url_for("finance.invoice_edit", inv_id=inv_id))

    conn.close()
    return render_template(
        "finance/invoice_edit.html",
        active="finance",
        page_title=f"Edit {invoice['invoice_number']}",
        invoice=invoice,
        owners=owners,
        pets=pets,
        today=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# CREDIT NOTE
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/<int:inv_id>/credit-note", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance")
def invoice_credit_note(inv_id):
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)
    reason = request.form.get("reason", "Credit note").strip() or "Credit note"
    amount = float(request.form.get("amount") or invoice.get("paid_amount") or invoice.get("total") or 0)
    if amount <= 0:
        flash("Credit note amount must be greater than zero.", "danger")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
    try:
        conn = db.get_db()
        # Build credit note invoice
        credit_data = {
            "owner_id":       invoice["owner_id"],
            "pet_id":         invoice.get("pet_id"),
            "visit_id":       None,
            "doctor_name":    invoice.get("doctor_name",""),
            "issue_date":     date.today().isoformat(),
            "due_date":       None,
            "discount_type":  "value",
            "discount_value": 0,
            "tax_rate":       0,
            "notes":          f"Credit note for {invoice['invoice_number']}. Reason: {reason}",
            "created_by":     session["user"].get("full_name",""),
        }
        credit_lines = [{
            "line_type":   "credit",
            "description": f"Credit note — {invoice['invoice_number']}: {reason}",
            "quantity":    1,
            "unit_price":  -abs(amount),
            "discount":    0,
            "total":       -abs(amount),
        }]
        credit_id = db.create_invoice(credit_data, credit_lines)
        # Mark original as Cancelled if full credit
        if abs(amount) >= (invoice.get("total") or 0):
            conn.execute("UPDATE invoices SET status='Cancelled' WHERE id=?", (inv_id,))
            conn.commit()
        conn.close()
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="credit_note",
            module="finance",
            entity_type="invoice",
            entity_id=inv_id,
            details=f"Credit note {credit_id} issued for {invoice['invoice_number']}: {reason}",
            ip=request.remote_addr,
        )
        flash(f"Credit note created successfully.", "success")
        return redirect(url_for("finance.invoice_detail", inv_id=credit_id))
    except Exception as e:
        flash(f"Error creating credit note: {e}", "danger")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))


# ─────────────────────────────────────────────
# INVOICE PRINT
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/<int:inv_id>/print")
@login_required
def invoice_print(inv_id):
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)
    clinic = db.get_clinic()
    return render_template(
        "finance/invoice_print.html",
        invoice=invoice,
        clinic=clinic,
    )


@finance_bp.route("/invoices/<int:inv_id>/pdf")
@login_required
def invoice_pdf(inv_id):
    """Download invoice as a PDF file."""
    from flask import Response
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)
    clinic = db.get_clinic()
    try:
        from models.pdf_generator import generate_invoice_pdf
        pdf_bytes = generate_invoice_pdf(invoice=invoice, clinic=clinic)
        fname = f"invoice-{invoice['invoice_number']}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )
    except RuntimeError as e:
        flash(str(e), "error")
        return redirect(url_for("finance.invoice_print", inv_id=inv_id))
    except Exception as e:
        flash(f"PDF generation failed: {e}", "error")
        return redirect(url_for("finance.invoice_print", inv_id=inv_id))


# ─────────────────────────────────────────────
# WHATSAPP INVOICE SEND
# ─────────────────────────────────────────────

@finance_bp.route("/invoices/<int:inv_id>/whatsapp", methods=["POST"])
@login_required
def invoice_whatsapp(inv_id):
    invoice = db.get_invoice(inv_id)
    if not invoice:
        abort(404)
    # Build message
    lines_text = ""
    for line in (invoice.get("lines") or []):
        lines_text += f"  • {line['description']}: {line['total']:.2f} EGP\n"
    message = (
        f"🐾 *Premium Animal Hospital*\n"
        f"Invoice: *{invoice['invoice_number']}*\n"
        f"Date: {invoice['issue_date']}\n\n"
        f"*Services:*\n{lines_text}\n"
        f"Subtotal: {invoice.get('subtotal',0):.2f} EGP\n"
    )
    if invoice.get("discount_amount"):
        message += f"Discount: -{invoice['discount_amount']:.2f} EGP\n"
    if invoice.get("tax_amount"):
        message += f"Tax: +{invoice['tax_amount']:.2f} EGP\n"
    message += (
        f"*Total: {invoice.get('total',0):.2f} EGP*\n"
        f"Paid: {invoice.get('paid_amount',0):.2f} EGP\n"
        f"*Balance Due: {invoice.get('due_amount',0):.2f} EGP*\n\n"
        f"Thank you for choosing Premium Animal Hospital 🐾\n"
        f"Dr. Hatem El Khateeb"
    )
    # Get owner phone
    phone = invoice.get("owner_phone", "")
    if not phone:
        flash("Owner has no phone number on file.", "warning")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
    # Import send helper from whatsapp blueprint
    try:
        from blueprints.whatsapp.routes import _send_and_log
        status = _send_and_log(phone, message,
                               owner_id=invoice.get("owner_id"),
                               template_name="invoice_whatsapp")
        if status == "Sent":
            flash(f"Invoice sent via WhatsApp to {phone}.", "success")
        else:
            flash("WhatsApp queued / failed — check message log.", "warning")
    except Exception as e:
        flash(f"WhatsApp error: {e}", "danger")
    return redirect(url_for("finance.invoice_detail", inv_id=inv_id))


# ─────────────────────────────────────────────
# EXPENSES
# ─────────────────────────────────────────────

@finance_bp.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses_list():
    if request.method == "POST":
        f = request.form
        amount = float(f.get("amount") or 0)
        desc   = f.get("description", "").strip()
        if not desc or amount <= 0:
            flash("Description and valid amount are required.", "danger")
        else:
            conn = db.get_db()
            try:
                with conn:
                    conn.execute(
                        """INSERT INTO expenses(category, description, amount, vendor,
                           receipt_ref, expense_date, notes, created_by)
                           VALUES(?,?,?,?,?,?,?,?)""",
                        (
                            f.get("category", "").strip() or "General",
                            desc,
                            amount,
                            f.get("vendor", "").strip() or None,
                            f.get("receipt_ref", "").strip() or None,
                            f.get("expense_date") or date.today().isoformat(),
                            f.get("notes", "").strip() or None,
                            session["user"].get("full_name", ""),
                        )
                    )
                flash("Expense recorded.", "success")
            except Exception as e:
                flash(f"Error saving expense: {e}", "danger")
            conn.close()
        return redirect(url_for("finance.expenses_list"))

    date_from = request.args.get("date_from", "")
    date_to   = request.args.get("date_to", "")

    conn = db.get_db()
    q = "SELECT * FROM expenses WHERE 1=1"
    params = []
    if date_from:
        q += " AND expense_date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND expense_date <= ?"
        params.append(date_to)
    q += " ORDER BY expense_date DESC, id DESC LIMIT 200"
    expenses = [dict(r) for r in conn.execute(q, params).fetchall()]
    conn.close()

    total_expenses = sum(e.get("amount", 0) or 0 for e in expenses)

    return render_template(
        "finance/expenses_list.html",
        active="finance",
        page_title="Expenses",
        expenses=expenses,
        total_expenses=total_expenses,
        today=date.today().isoformat(),
        date_from=date_from,
        date_to=date_to,
    )


# ─────────────────────────────────────────────
# REPORTS — P&L
# ─────────────────────────────────────────────

@finance_bp.route("/reports")
@login_required
def reports():
    today      = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    date_from = request.args.get("date_from", month_start)
    date_to   = request.args.get("date_to", today)

    summary        = db.get_finance_summary(date_from=date_from, date_to=date_to)
    revenue_by_day = db.get_revenue_by_day(days=30)

    conn = db.get_db()
    # Revenue by service category
    revenue_by_type = [dict(r) for r in conn.execute(
        """SELECT il.line_type, COALESCE(SUM(il.total),0) as total,
              COUNT(*) as count
           FROM invoice_lines il
           JOIN invoices i ON i.id = il.invoice_id
           WHERE i.issue_date BETWEEN ? AND ? AND i.status != 'Cancelled'
           GROUP BY il.line_type ORDER BY total DESC""",
        (date_from, date_to)
    ).fetchall()]

    # Expense by category
    expense_by_cat = [dict(r) for r in conn.execute(
        """SELECT COALESCE(category, 'General') as category,
              COALESCE(SUM(amount),0) as total, COUNT(*) as count
           FROM expenses
           WHERE expense_date BETWEEN ? AND ?
           GROUP BY category ORDER BY total DESC""",
        (date_from, date_to)
    ).fetchall()]

    # Top services
    top_services = db.get_top_services(limit=10)
    conn.close()

    max_rev = max((r["revenue"] for r in revenue_by_day), default=1) or 1

    return render_template(
        "finance/reports.html",
        active="finance",
        page_title="Financial Reports",
        summary=summary,
        date_from=date_from,
        date_to=date_to,
        revenue_by_day=revenue_by_day,
        max_rev=max_rev,
        revenue_by_type=revenue_by_type,
        expense_by_cat=expense_by_cat,
        top_services=top_services,
    )


# ─────────────────────────────────────────────
# REPORTS — EXCEL EXPORT
# ─────────────────────────────────────────────

@finance_bp.route("/reports/export/xlsx")
@login_required
def reports_export_xlsx():
    today       = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    date_from   = request.args.get("date_from", month_start)
    date_to     = request.args.get("date_to", today)

    conn = db.get_db()
    # Invoices in range
    inv_rows = conn.execute(
        """SELECT i.invoice_number, i.issue_date, o.full_name AS owner,
                  i.total_amount, i.discount_amount, i.tax_amount,
                  i.net_amount, i.status
           FROM invoices i
           LEFT JOIN owners o ON o.id = i.owner_id
           WHERE i.issue_date BETWEEN ? AND ?
           ORDER BY i.issue_date""",
        (date_from, date_to)
    ).fetchall()
    conn.close()

    headers = ["Invoice #", "Date", "Owner", "Total", "Discount",
               "Tax", "Net", "Status"]
    rows = [
        [r["invoice_number"], str(r["issue_date"])[:10], r["owner"],
         float(r["total_amount"] or 0), float(r["discount_amount"] or 0),
         float(r["tax_amount"] or 0), float(r["net_amount"] or 0),
         r["status"]]
        for r in inv_rows
    ]

    try:
        buf = make_workbook(
            title=f"Financial Report — {date_from} to {date_to}",
            headers=headers,
            rows=rows,
            sheet_name="Invoices",
        )
        filename = f"finance_report_{date_from}_{date_to}.xlsx"
        return send_file(
            buf,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )
    except RuntimeError as e:
        flash(str(e), "danger")
        return redirect(url_for("finance.reports"))
