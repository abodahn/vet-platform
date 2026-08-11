"""
Finance Blueprint — Aleefy Platform
"""

from flask import (
    render_template, request, redirect, url_for,
    session, flash, abort, send_file,
)
import uuid
from datetime import date, timedelta
from . import finance_bp
import logging

import models.database as db
from models import money, payments

logger = logging.getLogger(__name__)
from blueprints.auth.routes import login_required, role_required
from models.excel_export import make_workbook


def _idem(nonce, what, inv_id):
    """Idempotency key from the form's nonce, scoped to this invoice.

    A missing nonce (an old cached page, a script) falls back to a fresh UUID,
    which is the previous behaviour: no dedup, but never a WRONG dedup across
    two different invoices.
    """
    n = (nonce or "").strip()[:64]
    if not n:
        return "%s-%s-%s" % (what, inv_id, uuid.uuid4().hex)
    return "%s-%s-%s" % (what, inv_id, n)


def _num(raw, default=0.0):
    """A money or quantity box a tired person typed into. Never raises.

    Every one of these used to be a bare float(), so clearing a Qty box — or
    typing "1,200" with the thousands separator an Egyptian keyboard puts
    there — returned a 500 and threw away the whole invoice the user had just
    entered. Twelve call sites across New Invoice, Edit Invoice and New
    Estimate, all with the same shape.
    """
    if raw is None:
        return default
    s = str(raw).strip().replace(",", "")
    # Arabic-Indic digits: a clinic in Cairo types ٥٠٠ and meant 500.
    s = s.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    if not s:
        return default
    try:
        v = float(s)
    except ValueError:
        return default
    return v if v == v and v not in (float("inf"), float("-inf")) else default

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
        "SELECT COUNT(*) FROM invoices WHERE issue_date=? AND status IN ('Paid','Partial')", (today,)
    ).fetchone()[0]

    conn.close()

    # Build chart data
    max_rev = max((r["revenue"] for r in revenue_by_day), default=1) or 1

    return render_template(
        "finance/dashboard.html",
        active="finance",
        page_title="Finance Dashboard",
        # "Today's Revenue" is a till question, so it is money that ARRIVED
        # today — including on invoices raised last week. It used to be the
        # accrual figure, so a day on which the clinic took 120 EGP against an
        # older invoice displayed 0 and nothing reconciled.
        today_revenue=today_summary["collected"],
        month_revenue=month_summary["collected"],
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
    owner_id  = request.args.get("owner_id", type=int)

    invoices = db.list_invoices(
        owner_id=owner_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        limit=200,
    )

    # Name the owner being filtered on, so the chip is readable and links back.
    owner_name = ""
    if owner_id:
        conn = db.get_db()
        row = conn.execute("SELECT full_name FROM owners WHERE id=?", (owner_id,)).fetchone()
        conn.close()
        owner_name = row["full_name"] if row else ""

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
        owner_id=owner_id,
        owner_name=owner_name,
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
    # The owner box searches the server (crm.owner_search_json). It used to
    # render the first 500 owners, so client 501 could not be invoiced at all.
    owners = []
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
            qty  = _num(qtys[i] if i < len(qtys) else 1, 1.0)
            up   = _num(unit_prices[i] if i < len(unit_prices) else 0, 0.0)
            disc = _num(discounts[i] if i < len(discounts) else 0, 0.0)
            # A quantity of 0 is a typo, not a free item, and billing it as 1
            # charged for a line the screen showed as 0.00. A negative price or
            # a discount over 100% would pay the client to take the service.
            if qty <= 0 or up < 0:
                continue
            disc = max(0.0, min(disc, 100.0))
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
            "discount_value": _num(f.get("discount_value")),
            "tax_rate":       _num(f.get("tax_rate")),
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

    conn = db.get_db()
    # get_invoice() returns payments=[] unconditionally; read the real rows.
    invoice["payments"] = [dict(r) for r in conn.execute(
        "SELECT * FROM payments WHERE invoice_id=? ORDER BY received_at, id",
        (inv_id,)
    ).fetchall()]
    # Resolve the visit rather than trusting invoices.visit_id: the column has
    # no enforced FK, so a deleted visit would otherwise render a dead link.
    visit = None
    if invoice.get("visit_id"):
        row = conn.execute(
            "SELECT id, visit_date, visit_type FROM visits WHERE id=?",
            (invoice["visit_id"],)
        ).fetchone()
        if row:
            visit = dict(row)
    conn.close()

    return render_template(
        "finance/invoice_detail.html",
        active="finance",
        page_title=f"Invoice {invoice['invoice_number']}",
        invoice=invoice,
        visit=visit,
        today=date.today().isoformat(),
        # Offer held credit here, where the money is actually being settled --
        # a balance nobody is shown at the till may as well not exist.
        credit_balance=db.owner_credit_balance(invoice["owner_id"]),
        # One nonce per rendered form. A double-clicked Record Payment posts
        # the SAME nonce, so models/payments returns the existing intent
        # instead of taking the money twice — the idempotency this codebase
        # already implements and never supplied a key for. A second, genuine
        # payment arrives from a fresh page with a fresh nonce, so it is not
        # blocked.
        pay_nonce=uuid.uuid4().hex,
        credit_nonce=uuid.uuid4().hex,
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

    # Parsed, not coerced. A bare float() here raised ValueError on any typo --
    # one letter in the amount box returned a 500 page to a receptionist with a
    # client at the counter. Coercing silently to 0 would be worse: "1O0" with a
    # letter O would post as zero and the till would be short with no trace.
    amount, err = money.form_amount(request.form.get("amount"), "payment amount")
    if err:
        flash(err, "danger")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
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
            # Supplied at last. Without it every click minted a fresh
            # auto-<uuid> key, so a double-clicked button was two payments and
            # the client was charged twice.
            idempotency_key=_idem(request.form.get("idem"), "pay", inv_id),
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
    except payments.PaymentError as e:
        # Written for the person at the counter and already says what to do
        # ("that is more than the 120.00 still owed"), so it is shown as-is
        # rather than wrapped in "Error recording payment:".
        flash(str(e), "warning")
    except Exception:
        logger.exception("recording payment on invoice %s failed", inv_id)
        flash("The payment could not be recorded. Nothing was charged — "
              "please try again, or record it in cash.", "danger")

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
    # 'Cancelled' used to fall straight through this check, so a voided invoice
    # could be edited back to life at any amount while its credit note stayed
    # on the books — the void and the invoice both counted.
    if invoice["status"] in ("Paid", "Cancelled"):
        flash("%s invoices cannot be edited. Issue a credit note instead."
              % invoice["status"], "warning")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))

    conn = db.get_db()
    # Only the invoice's own owner is rendered, so the edit form keeps its
    # selection; anyone else is found by typing (crm.owner_search_json).
    owners = [dict(r) for r in conn.execute(
        "SELECT id, full_name, phone FROM owners WHERE id=?", (invoice["owner_id"],)
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
            qty  = _num(qtys[i] if i < len(qtys) else 1, 1.0)
            up   = _num(unit_prices[i] if i < len(unit_prices) else 0, 0.0)
            disc = _num(discounts[i] if i < len(discounts) else 0, 0.0)
            # A quantity of 0 is a typo, not a free item, and billing it as 1
            # charged for a line the screen showed as 0.00. A negative price or
            # a discount over 100% would pay the client to take the service.
            if qty <= 0 or up < 0:
                continue
            disc = max(0.0, min(disc, 100.0))
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

        discount_value = _num(f.get("discount_value"))
        tax_rate       = _num(f.get("tax_rate"))
        subtotal       = sum(l["total"] for l in lines)
        discount_type  = f.get("discount_type", "value")
        discount_amt   = discount_value if discount_type == "value" else round(subtotal * discount_value / 100, 2)
        tax_amount     = round((subtotal - discount_amt) * tax_rate / 100, 2)
        total          = round(subtotal - discount_amt + tax_amount, 2)
        paid_amount    = float(invoice.get("paid_amount") or 0)
        # Editing an invoice BELOW what the client has already handed over is a
        # refund, not an edit. It used to store a negative due_amount and mark
        # the invoice "Paid", so the money owed back to the client existed
        # nowhere on the screen and nowhere in the totals.
        if round(total, 2) < round(paid_amount, 2):
            flash("This invoice already has %.2f paid against it. Lowering it to "
                  "%.2f would owe the client %.2f — issue a credit note or a "
                  "refund instead."
                  % (paid_amount, total, paid_amount - total), "danger")
            conn.close()
            return redirect(url_for("finance.invoice_edit", inv_id=inv_id))
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
    amount, err = money.form_amount(
        request.form.get("amount") or invoice.get("paid_amount")
        or invoice.get("total") or 0, "amount")
    # The parse error used to be discarded, so "12,34x" became 0 and the user
    # was told the amount must be positive — the wrong reason for the failure.
    if err:
        flash(err, "danger")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
    if amount <= 0:
        flash("Credit note amount must be greater than zero.", "danger")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))

    inv_total = float(invoice.get("total") or 0)
    if invoice.get("status") == "Cancelled":
        flash("This invoice is already cancelled. It cannot be credited again.",
              "warning")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
    # A credit note may not exceed what was invoiced. Unbounded, a second click
    # or a mistyped figure credited more than the clinic ever charged.
    if amount > inv_total:
        flash("A credit note cannot exceed the invoice total of %.2f." % inv_total,
              "danger")
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

        # A credit note is not a receivable. create_invoice() sets
        # due_amount = total, which here is NEGATIVE, and Outstanding sums
        # due_amount over Unpaid/Partial — so the credit note pulled its own
        # value out of Outstanding, and cancelling the original pulled the same
        # value out again. One 12,345.67 void moved Outstanding by 24,692.
        # Settling the note at zero leaves exactly one movement.
        conn.execute(
            "UPDATE invoices SET due_amount=0, paid_amount=0, status='Paid'"
            " WHERE id=?", (credit_id,))

        if abs(amount) >= inv_total:
            conn.execute("UPDATE invoices SET status='Cancelled', due_amount=0"
                         " WHERE id=?", (inv_id,))
        else:
            # A PARTIAL credit used to do nothing at all to the original, so
            # the client was still chased for the full amount.
            paid = float(invoice.get("paid_amount") or 0)
            new_due = round(max(0.0, inv_total - amount - paid), 2)
            new_status = ("Paid" if new_due <= 0
                          else ("Partial" if paid > 0 else "Unpaid"))
            conn.execute("UPDATE invoices SET due_amount=?, status=? WHERE id=?",
                         (new_due, new_status, inv_id))
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
        f"🐾 *Aleefy*\n"
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
        f"Thank you for choosing Aleefy 🐾\n"
        f"Happy Pets, Healthy Lives"
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

# The clinic's own money, not a client's bill. The finance blueprint maps to
# the "invoicing" grant, which reception legitimately holds so she can take
# payments -- so @login_required alone put the P&L, the expense ledger and
# their export in front of every receptionist. Verified live: rec.yasmine
# loaded /finance/reports and read Revenue 441,605 / Net 107,801, plus rent
# and marketing spend. models/database.py says of this role: "Front desk:
# books, bills and talks to clients. Not the clinic's accounts."
@finance_bp.route("/expenses", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "finance", "auditor")
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
    # expenses.vendor is free text with no supplier_id — link it only when the
    # name matches a real supplier row, otherwise render it as plain text.
    supplier_ids = {r["name"]: r["id"]
                    for r in conn.execute("SELECT id, name FROM suppliers").fetchall()}
    conn.close()

    total_expenses = sum(e.get("amount", 0) or 0 for e in expenses)

    return render_template(
        "finance/expenses_list.html",
        active="finance",
        page_title="Expenses",
        expenses=expenses,
        supplier_ids=supplier_ids,
        total_expenses=total_expenses,
        today=date.today().isoformat(),
        date_from=date_from,
        date_to=date_to,
    )


# ─────────────────────────────────────────────
# REPORTS — P&L
# ─────────────────────────────────────────────

# The clinic's own money, not a client's bill. The finance blueprint maps to
# the "invoicing" grant, which reception legitimately holds so she can take
# payments -- so @login_required alone put the P&L, the expense ledger and
# their export in front of every receptionist. Verified live: rec.yasmine
# loaded /finance/reports and read Revenue 441,605 / Net 107,801, plus rent
# and marketing spend. models/database.py says of this role: "Front desk:
# books, bills and talks to clients. Not the clinic's accounts."
@finance_bp.route("/reports")
@role_required("super_admin", "clinic_owner", "branch_manager", "finance", "auditor")
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

# The clinic's own money, not a client's bill. The finance blueprint maps to
# the "invoicing" grant, which reception legitimately holds so she can take
# payments -- so @login_required alone put the P&L, the expense ledger and
# their export in front of every receptionist. Verified live: rec.yasmine
# loaded /finance/reports and read Revenue 441,605 / Net 107,801, plus rent
# and marketing spend. models/database.py says of this role: "Front desk:
# books, bills and talks to clients. Not the clinic's accounts."
@finance_bp.route("/reports/export/xlsx")
@role_required("super_admin", "clinic_owner", "branch_manager", "finance", "auditor")
def reports_export_xlsx():
    today       = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    date_from   = request.args.get("date_from", month_start)
    date_to     = request.args.get("date_to", today)

    try:
        conn = db.get_db()
        inv_rows = conn.execute(
            # invoices has no total_amount/net_amount — the gross figure is
            # subtotal and the net is total. Naming the non-existent columns
            # raised, and the except below turned every export into a silent
            # redirect back to the report page.
            """SELECT i.invoice_number, i.issue_date, o.full_name AS owner,
                      i.subtotal AS total_amount, i.discount_amount, i.tax_amount,
                      i.total AS net_amount, i.status
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
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("finance.reports"))


# ─────────────────────────────────────────────
# ESTIMATES (QUOTES)
#
# The one thing every competing PIMS has that this did not. An estimate is a
# priced plan the client agrees to BEFORE the work happens -- for surgery and
# hospitalisation it is what stops the argument at the counter afterwards.
#
# These routes live in the finance blueprint on purpose: _permission_denied()
# gates by blueprint, so they inherit the finance grant. A new blueprint would
# have had no grant key and fallen OPEN to every role.
# ─────────────────────────────────────────────

def _estimate_form_ctx(page_title="New Estimate"):
    conn = db.get_db()
    # Owner box searches the server (crm.owner_search_json), no rendered slice.
    owners = []
    pets = [dict(r) for r in conn.execute(
        "SELECT id, owner_id, pet_name, species FROM pets WHERE is_active=1 "
        "ORDER BY pet_name").fetchall()]
    conn.close()
    return dict(active="finance", page_title=page_title, owners=owners, pets=pets,
                today=date.today().isoformat(),
                default_valid=(date.today() + timedelta(days=14)).isoformat())


@finance_bp.route("/estimates")
@login_required
def estimates_list():
    return render_template(
        "finance/estimates_list.html",
        active="finance",
        page_title="Estimates",
        estimates=db.list_estimates(status=request.args.get("status", "")),
        status=request.args.get("status", ""),
    )


@finance_bp.route("/estimates/new", methods=["GET", "POST"])
@login_required
def estimate_new():
    ctx = _estimate_form_ctx()
    if request.method != "POST":
        return render_template("finance/estimate_form.html", **ctx)

    f = request.form
    owner_id = f.get("owner_id", type=int)
    if not owner_id:
        flash("Owner is required.", "danger")
        return render_template("finance/estimate_form.html", **ctx)

    descriptions = f.getlist("description[]")
    qtys         = f.getlist("qty[]")
    unit_prices  = f.getlist("unit_price[]")
    discounts    = f.getlist("discount[]")
    line_types   = f.getlist("line_type[]")

    lines = []
    for i, desc in enumerate(descriptions):
        if not desc.strip():
            continue
        qty  = _num(qtys[i] if i < len(qtys) else 1, 1.0)
        up   = _num(unit_prices[i] if i < len(unit_prices) else 0, 0.0)
        disc = _num(discounts[i] if i < len(discounts) else 0, 0.0)
        if qty <= 0 or up < 0:
            continue
        disc = max(0.0, min(disc, 100.0))
        lines.append({
            "line_type":   line_types[i] if i < len(line_types) else "service",
            "description": desc.strip(),
            "quantity":    qty,
            "unit_price":  up,
            "discount":    disc,
            "total":       round(qty * up - (up * qty * disc / 100), 2),
        })

    if not lines:
        flash("At least one line item is required.", "danger")
        return render_template("finance/estimate_form.html", **ctx)

    try:
        est_id = db.create_estimate({
            "owner_id":       owner_id,
            "pet_id":         f.get("pet_id", type=int),
            "visit_id":       f.get("visit_id", type=int),
            "doctor_name":    f.get("doctor_name", "").strip(),
            "issue_date":     f.get("issue_date") or date.today().isoformat(),
            "valid_until":    f.get("valid_until", "").strip() or None,
            "discount_type":  f.get("discount_type", "value"),
            "discount_value": _num(f.get("discount_value")),
            "tax_rate":       _num(f.get("tax_rate")),
            "notes":          f.get("notes", "").strip(),
            "created_by":     session["user"].get("full_name", ""),
        }, lines)
    except Exception as e:
        flash(f"Error creating estimate: {e}", "danger")
        return render_template("finance/estimate_form.html", **ctx)

    flash("Estimate created.", "success")
    return redirect(url_for("finance.estimate_detail", est_id=est_id))


@finance_bp.route("/estimates/<int:est_id>")
@login_required
def estimate_detail(est_id):
    est = db.get_estimate(est_id)
    if not est:
        flash("Estimate not found.", "danger")
        return redirect(url_for("finance.estimates_list"))
    return render_template("finance/estimate_detail.html", active="finance",
                           page_title=est["estimate_number"], est=est,
                           today=date.today().isoformat())


@finance_bp.route("/estimates/<int:est_id>/decide", methods=["POST"])
@login_required
def estimate_decide(est_id):
    decision = request.form.get("decision", "")
    if decision not in ("Approved", "Declined", "Sent"):
        flash("Unknown decision.", "danger")
        return redirect(url_for("finance.estimate_detail", est_id=est_id))
    est = db.get_estimate(est_id)
    if not est:
        flash("Estimate not found.", "danger")
        return redirect(url_for("finance.estimates_list"))
    if est.get("status") == "Converted":
        # Re-deciding a converted estimate would leave an invoice with no
        # approved quote behind it.
        flash("This estimate is already invoiced and cannot be changed.", "warning")
        return redirect(url_for("finance.estimate_detail", est_id=est_id))
    db.decide_estimate(est_id, decision, session["user"].get("full_name", ""))
    flash(f"Estimate marked {decision}.", "success")
    return redirect(url_for("finance.estimate_detail", est_id=est_id))


@finance_bp.route("/estimates/<int:est_id>/convert", methods=["POST"])
@login_required
def estimate_convert(est_id):
    try:
        inv_id = db.convert_estimate(est_id, session["user"].get("full_name", ""))
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("finance.estimate_detail", est_id=est_id))
    flash("Invoice created from estimate.", "success")
    return redirect(url_for("finance.invoice_detail", inv_id=inv_id))


@finance_bp.route("/estimates/<int:est_id>/print")
@login_required
def estimate_print(est_id):
    est = db.get_estimate(est_id)
    if not est:
        flash("Estimate not found.", "danger")
        return redirect(url_for("finance.estimates_list"))
    return render_template("finance/estimate_print.html", est=est)


# ─────────────────────────────────────────────
# CLIENT DEPOSITS / ACCOUNT CREDIT
#
# Money taken before there is an invoice: boarding and surgery deposits. There
# was no way to record it at all, so front desks were either refusing deposits
# or keeping them on paper.
# ─────────────────────────────────────────────

@finance_bp.route("/owners/<int:owner_id>/credit", methods=["GET", "POST"])
@login_required
def owner_credit(owner_id):
    conn = db.get_db()
    owner = conn.execute("SELECT id, full_name, phone FROM owners WHERE id=?",
                         (owner_id,)).fetchone()
    conn.close()
    if not owner:
        flash("Owner not found.", "danger")
        return redirect(url_for("finance.invoices_list"))
    owner = dict(owner)

    if request.method == "POST":
        action = request.form.get("action", "deposit")
        try:
            amount, _err = money.form_amount(request.form.get("amount"), "amount")
            if _err:
                flash(_err, "danger")
                return redirect(url_for("finance.owner_credit", owner_id=owner_id))
            if action == "refund":
                db.refund_credit(owner_id, amount,
                                 request.form.get("note", "").strip(),
                                 session["user"].get("full_name", ""))
                flash("Refund recorded.", "success")
            else:
                db.add_deposit(owner_id, amount,
                               request.form.get("method", "Cash"),
                               request.form.get("reference", "").strip(),
                               request.form.get("note", "").strip(),
                               session["user"].get("full_name", ""))
                flash("Deposit recorded.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("finance.owner_credit", owner_id=owner_id))

    return render_template(
        "finance/owner_credit.html",
        active="finance",
        page_title=f"Account — {owner['full_name']}",
        owner=owner,
        balance=db.owner_credit_balance(owner_id),
        entries=db.list_owner_credits(owner_id),
        open_invoices=[i for i in db.list_invoices(owner_id=owner_id)
                       if (i.get("due_amount") or 0) > 0],
    )


@finance_bp.route("/invoices/<int:inv_id>/apply-credit", methods=["POST"])
@login_required
def invoice_apply_credit(inv_id):
    inv = db.get_invoice(inv_id)
    if not inv:
        flash("Invoice not found.", "danger")
        return redirect(url_for("finance.invoices_list"))
    try:
        db.apply_credit(inv["owner_id"], inv_id,
                        money.form_amount(request.form.get("amount"), "amount")[0],
                        session["user"].get("full_name", ""))
        flash("Credit applied to the invoice.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
