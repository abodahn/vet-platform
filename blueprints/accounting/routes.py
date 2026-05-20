"""
Accounting Blueprint — Finance & Accounting module (Module 19)
Premium Animal Hospital Platform
"""

from flask import (
    render_template, request, redirect, url_for,
    session, flash,
)
from datetime import date, timedelta
from . import accounting_bp
from models.database import get_db
from blueprints.auth.routes import login_required


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

@accounting_bp.route("/")
@login_required
def dashboard():
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    conn = get_db()

    # Total revenue this month (paid invoice amounts)
    try:
        month_revenue = float(conn.execute(
            """SELECT COALESCE(SUM(paid_amount), 0)
               FROM invoices
               WHERE status IN ('Paid','Partial')
               AND created_at >= ?""",
            (month_start,)
        ).fetchone()[0] or 0)
    except Exception:
        month_revenue = 0.0

    # Total expenses this month
    try:
        month_expenses = float(conn.execute(
            """SELECT COALESCE(SUM(amount), 0)
               FROM expenses
               WHERE expense_date >= ?""",
            (month_start,)
        ).fetchone()[0] or 0)
    except Exception:
        month_expenses = 0.0

    net_profit = month_revenue - month_expenses
    profit_margin = round((net_profit / month_revenue * 100) if month_revenue > 0 else 0, 1)

    # Top 5 expense categories
    try:
        top_expense_cats = [dict(r) for r in conn.execute(
            """SELECT COALESCE(category, 'General') as category,
                      COALESCE(SUM(amount), 0) as total
               FROM expenses
               WHERE expense_date >= ?
               GROUP BY category
               ORDER BY total DESC
               LIMIT 5""",
            (month_start,)
        ).fetchall()]
    except Exception:
        top_expense_cats = []

    # 12 months revenue vs expenses for bar chart
    chart_data = []
    for i in range(11, -1, -1):
        d = date.today().replace(day=1) - timedelta(days=i * 28)
        m_start = d.replace(day=1).isoformat()
        try:
            next_month = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
            m_end = (next_month - timedelta(days=1)).isoformat()
        except Exception:
            m_end = m_start
        try:
            rev = float(conn.execute(
                """SELECT COALESCE(SUM(paid_amount), 0) FROM invoices
                   WHERE status IN ('Paid','Partial')
                   AND created_at >= ? AND created_at <= ?""",
                (m_start, m_end + " 23:59:59")
            ).fetchone()[0] or 0)
            exp = float(conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date >= ? AND expense_date <= ?",
                (m_start, m_end)
            ).fetchone()[0] or 0)
        except Exception:
            rev = 0.0
            exp = 0.0
        chart_data.append({
            "label": d.strftime("%b %Y"),
            "revenue": rev,
            "expenses": exp,
        })

    max_chart_val = max((max(c["revenue"], c["expenses"]) for c in chart_data), default=1) or 1

    # Recent transactions — last 10 from paid invoices + expenses
    try:
        recent_invoices = [dict(r) for r in conn.execute(
            """SELECT 'revenue' as tx_type, created_at as tx_date,
                      COALESCE(paid_amount, 0) as amount,
                      COALESCE(invoice_number, 'Invoice') as description
               FROM invoices
               WHERE status IN ('Paid','Partial')
               ORDER BY created_at DESC LIMIT 5"""
        ).fetchall()]
    except Exception:
        recent_invoices = []

    try:
        recent_expenses = [dict(r) for r in conn.execute(
            """SELECT 'expense' as tx_type,
                      COALESCE(expense_date, '') as tx_date,
                      COALESCE(amount, 0) as amount,
                      COALESCE(description, category) as description
               FROM expenses
               ORDER BY expense_date DESC, id DESC LIMIT 5"""
        ).fetchall()]
    except Exception:
        recent_expenses = []

    recent_transactions = sorted(
        recent_invoices + recent_expenses,
        key=lambda x: x.get("tx_date") or "",
        reverse=True
    )[:10]

    conn.close()

    return render_template(
        "accounting/dashboard.html",
        active="accounting",
        page_title="Accounting Dashboard",
        month_revenue=month_revenue,
        month_expenses=month_expenses,
        net_profit=net_profit,
        profit_margin=profit_margin,
        top_expense_cats=top_expense_cats,
        chart_data=chart_data,
        max_chart_val=max_chart_val,
        recent_transactions=recent_transactions,
        today=today,
    )


# ─────────────────────────────────────────────
# PROFIT & LOSS REPORT
# ─────────────────────────────────────────────

@accounting_bp.route("/pl")
@login_required
def profit_loss():
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    date_from = request.args.get("date_from", month_start)
    date_to = request.args.get("date_to", today)

    conn = get_db()

    # Revenue by service/description
    try:
        revenue_rows = [dict(r) for r in conn.execute(
            """SELECT COALESCE(il.description, 'Service') as item,
                      COALESCE(il.line_type, 'service') as line_type,
                      COALESCE(SUM(il.total), 0) as total,
                      COUNT(*) as count
               FROM invoice_lines il
               JOIN invoices i ON i.id = il.invoice_id
               WHERE i.status IN ('Paid','Partial')
               AND SUBSTRING(i.issue_date::text, 1, 10) >= ?
               AND SUBSTRING(i.issue_date::text, 1, 10) <= ?
               GROUP BY il.description, il.line_type
               ORDER BY total DESC""",
            (date_from, date_to)
        ).fetchall()]
    except Exception:
        try:
            revenue_rows = [dict(r) for r in conn.execute(
                """SELECT 'Invoice Payments' as item, 'revenue' as line_type,
                          COALESCE(SUM(paid_amount), 0) as total, COUNT(*) as count
                   FROM invoices
                   WHERE status IN ('Paid','Partial')
                   AND SUBSTRING(issue_date::text, 1, 10) >= ?
                   AND SUBSTRING(issue_date::text, 1, 10) <= ?""",
                (date_from, date_to)
            ).fetchall()]
        except Exception:
            revenue_rows = []

    # Expenses by category
    try:
        expense_rows = [dict(r) for r in conn.execute(
            """SELECT COALESCE(category, 'General') as category,
                      COALESCE(SUM(amount), 0) as total,
                      COUNT(*) as count
               FROM expenses
               WHERE expense_date >= ? AND expense_date <= ?
               GROUP BY category
               ORDER BY total DESC""",
            (date_from, date_to)
        ).fetchall()]
    except Exception:
        expense_rows = []

    conn.close()

    total_revenue = sum(r.get("total", 0) or 0 for r in revenue_rows)
    total_expenses = sum(r.get("total", 0) or 0 for r in expense_rows)
    net_profit = total_revenue - total_expenses
    profit_margin = round((net_profit / total_revenue * 100) if total_revenue > 0 else 0, 1)

    return render_template(
        "accounting/pl_report.html",
        active="accounting",
        page_title="Profit & Loss Report",
        date_from=date_from,
        date_to=date_to,
        revenue_rows=revenue_rows,
        expense_rows=expense_rows,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=net_profit,
        profit_margin=profit_margin,
    )


# ─────────────────────────────────────────────
# CASH FLOW
# ─────────────────────────────────────────────

@accounting_bp.route("/cashflow")
@login_required
def cash_flow():
    today = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()

    date_from = request.args.get("date_from", month_start)
    date_to = request.args.get("date_to", today)

    conn = get_db()

    movements = []

    # Money in — payments table (received_at is the real column)
    try:
        pay_rows = [dict(r) for r in conn.execute(
            """SELECT SUBSTRING(received_at::text, 1, 10) AS tx_date,
                      amount,
                      COALESCE(method, 'Cash') AS payment_method,
                      COALESCE(reference, 'Invoice Payment') AS description,
                      'in' AS direction
               FROM payments
               WHERE SUBSTRING(received_at::text, 1, 10) >= ?
                 AND SUBSTRING(received_at::text, 1, 10) <= ?
               ORDER BY received_at""",
            (date_from, date_to)
        ).fetchall()]
        movements.extend(pay_rows)
    except Exception:
        # Fallback: use paid invoices
        try:
            inv_pay = [dict(r) for r in conn.execute(
                """SELECT SUBSTRING(issue_date::text, 1, 10) AS tx_date,
                          paid_amount AS amount,
                          'Cash' AS payment_method,
                          COALESCE(invoice_number, 'Invoice') AS description,
                          'in' AS direction
                   FROM invoices
                   WHERE status IN ('Paid','Partial')
                     AND SUBSTRING(issue_date::text, 1, 10) >= ?
                     AND SUBSTRING(issue_date::text, 1, 10) <= ?""",
                (date_from, date_to)
            ).fetchall()]
            movements.extend(inv_pay)
        except Exception:
            pass

    # Money out — expenses
    try:
        expenses = [dict(r) for r in conn.execute(
            """SELECT expense_date AS tx_date,
                      COALESCE(amount, 0) AS amount,
                      'Cash' AS payment_method,
                      COALESCE(description, category, 'Expense') AS description,
                      'out' AS direction
               FROM expenses
               WHERE expense_date >= ? AND expense_date <= ?
               ORDER BY expense_date""",
            (date_from, date_to)
        ).fetchall()]
        movements.extend(expenses)
    except Exception:
        pass

    conn.close()

    # Sort by date
    movements.sort(key=lambda x: x.get("tx_date") or "")

    # Add running balance
    balance = 0.0
    for m in movements:
        amt = float(m.get("amount") or 0)
        if m.get("direction") == "in":
            balance += amt
        else:
            balance -= amt
        m["running_balance"] = balance

    total_in = sum(float(m.get("amount") or 0) for m in movements if m.get("direction") == "in")
    total_out = sum(float(m.get("amount") or 0) for m in movements if m.get("direction") == "out")

    return render_template(
        "accounting/cashflow.html",
        active="accounting",
        page_title="Cash Flow",
        movements=movements,
        date_from=date_from,
        date_to=date_to,
        total_in=total_in,
        total_out=total_out,
        net_flow=total_in - total_out,
    )


# ─────────────────────────────────────────────
# EXPENSES LIST
# ─────────────────────────────────────────────

@accounting_bp.route("/expenses")
@login_required
def expenses_list():
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    category = request.args.get("category", "")

    conn = get_db()

    q = "SELECT * FROM expenses WHERE 1=1"
    params = []
    if date_from:
        q += " AND expense_date >= ?"
        params.append(date_from)
    if date_to:
        q += " AND expense_date <= ?"
        params.append(date_to)
    if category:
        q += " AND category = ?"
        params.append(category)
    q += " ORDER BY expense_date DESC, id DESC LIMIT 300"

    try:
        expenses = [dict(r) for r in conn.execute(q, params).fetchall()]
    except Exception:
        expenses = []

    # Get distinct categories for filter dropdown
    try:
        categories = [r[0] for r in conn.execute(
            "SELECT DISTINCT COALESCE(category,'General') FROM expenses ORDER BY 1"
        ).fetchall()]
    except Exception:
        categories = []

    conn.close()

    total_expenses = sum(float(e.get("amount") or 0) for e in expenses)

    return render_template(
        "accounting/expenses_list.html",
        active="accounting",
        page_title="Expenses",
        expenses=expenses,
        categories=categories,
        total_expenses=total_expenses,
        date_from=date_from,
        date_to=date_to,
        selected_category=category,
        today=date.today().isoformat(),
    )


# ─────────────────────────────────────────────
# ADD EXPENSE
# ─────────────────────────────────────────────

@accounting_bp.route("/expenses/new", methods=["POST"])
@login_required
def add_expense():
    f = request.form
    amount_str = f.get("amount", "0")
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        amount = 0.0

    category = f.get("category", "").strip() or "General"
    description = f.get("description", "").strip()
    expense_date = f.get("expense_date") or date.today().isoformat()
    vendor = f.get("vendor", "").strip() or None
    receipt_ref = f.get("receipt_ref", "").strip() or None
    payment_method = f.get("payment_method", "Cash").strip()

    if not description or amount <= 0:
        flash("Description and valid amount are required.", "danger")
        return redirect(url_for("accounting.expenses_list"))

    conn = get_db()
    try:
        with conn:
            # Try with payment_method column, fall back without
            try:
                conn.execute(
                    """INSERT INTO expenses
                       (category, description, amount, expense_date, vendor, receipt_ref,
                        payment_method, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (category, description, amount, expense_date, vendor, receipt_ref,
                     payment_method, session["user"].get("full_name", ""))
                )
            except Exception:
                conn.execute(
                    """INSERT INTO expenses
                       (category, description, amount, expense_date, vendor, receipt_ref, created_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (category, description, amount, expense_date, vendor, receipt_ref,
                     session["user"].get("full_name", ""))
                )
        flash("Expense recorded successfully.", "success")
    except Exception as e:
        flash(f"Error saving expense: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("accounting.expenses_list"))


# ─────────────────────────────────────────────
# DAILY CLOSING
# ─────────────────────────────────────────────

@accounting_bp.route("/closing", methods=["GET", "POST"])
@login_required
def daily_closing():
    today = date.today().isoformat()
    conn = get_db()

    if request.method == "POST":
        note = request.form.get("closing_note", "").strip()
        if note:
            try:
                with conn:
                    conn.execute(
                        """CREATE TABLE IF NOT EXISTS closing_notes
                           (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            closing_date TEXT NOT NULL,
                            note TEXT,
                            created_by TEXT,
                            created_at TEXT DEFAULT (datetime('now')))"""
                    )
                    conn.execute(
                        "INSERT INTO closing_notes (closing_date, note, created_by) VALUES (?, ?, ?)",
                        (today, note, session["user"].get("full_name", ""))
                    )
                flash("Closing note saved.", "success")
            except Exception as e:
                flash(f"Error saving note: {e}", "danger")
        return redirect(url_for("accounting.daily_closing"))

    # Today's summary
    try:
        today_revenue = float(conn.execute(
            """SELECT COALESCE(SUM(amount), 0) FROM payments
               WHERE SUBSTRING(received_at::text, 1, 10) = ?""",
            (today,)
        ).fetchone()[0] or 0)
        tx_count_in = conn.execute(
            "SELECT COUNT(*) FROM payments WHERE SUBSTRING(received_at::text, 1, 10) = ?",
            (today,)
        ).fetchone()[0]
    except Exception:
        try:
            today_revenue = float(conn.execute(
                """SELECT COALESCE(SUM(paid_amount), 0) FROM invoices
                   WHERE status IN ('Paid','Partial')
                     AND SUBSTRING(issue_date::text, 1, 10) = ?""",
                (today,)
            ).fetchone()[0] or 0)
            tx_count_in = conn.execute(
                """SELECT COUNT(*) FROM invoices
                   WHERE status IN ('Paid','Partial')
                     AND SUBSTRING(issue_date::text, 1, 10) = ?""",
                (today,)
            ).fetchone()[0]
        except Exception:
            today_revenue = 0.0
            tx_count_in = 0

    try:
        today_expenses = float(conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE expense_date = ?",
            (today,)
        ).fetchone()[0] or 0)
        tx_count_out = conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE expense_date = ?",
            (today,)
        ).fetchone()[0]
    except Exception:
        today_expenses = 0.0
        tx_count_out = 0

    net_cash = today_revenue - today_expenses

    # Previous 7 days' closings
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS closing_notes
               (id INTEGER PRIMARY KEY AUTOINCREMENT,
                closing_date TEXT NOT NULL,
                note TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now')))"""
        )
        previous_closings = [dict(r) for r in conn.execute(
            """SELECT closing_date, note, created_by, created_at
               FROM closing_notes
               ORDER BY closing_date DESC LIMIT 7"""
        ).fetchall()]
    except Exception:
        previous_closings = []

    conn.close()

    return render_template(
        "accounting/closing.html",
        active="accounting",
        page_title="Daily Closing",
        today=today,
        today_revenue=today_revenue,
        today_expenses=today_expenses,
        net_cash=net_cash,
        tx_count_in=tx_count_in,
        tx_count_out=tx_count_out,
        total_tx=tx_count_in + tx_count_out,
        previous_closings=previous_closings,
    )


# ─────────────────────────────────────────────
# BUDGET
# ─────────────────────────────────────────────

@accounting_bp.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    today       = date.today().isoformat()
    month_start = date.today().replace(day=1).isoformat()
    conn        = get_db()

    # ── Save updated targets (POST) ──────────────────────────
    if request.method == "POST":
        actor = session["user"].get("full_name", "")
        categories = request.form.getlist("category[]")
        amounts    = request.form.getlist("monthly_egp[]")
        new_cat    = (request.form.get("new_category") or "").strip()
        new_amt    = request.form.get("new_amount") or "0"
        try:
            with conn:
                for cat, amt in zip(categories, amounts):
                    try:
                        v = float(amt)
                    except ValueError:
                        v = 0.0
                    conn.execute(
                        """UPDATE budget_targets
                           SET monthly_egp=?, updated_by=?, updated_at=NOW()
                           WHERE category=?""",
                        (v, actor, cat),
                    )
                if new_cat:
                    try:
                        nv = float(new_amt)
                    except ValueError:
                        nv = 0.0
                    conn.execute(
                        """INSERT INTO budget_targets (category, monthly_egp, updated_by)
                           VALUES (?,?,?)
                           ON CONFLICT (category) DO UPDATE
                           SET monthly_egp=EXCLUDED.monthly_egp, updated_by=EXCLUDED.updated_by""",
                        (new_cat, nv, actor),
                    )
            flash("Budget targets saved.", "success")
        except Exception as e:
            flash(f"Error saving budget: {e}", "danger")
        conn.close()
        return redirect(url_for("accounting.budget"))

    # ── Load from DB ─────────────────────────────────────────
    rows = conn.execute(
        "SELECT category, monthly_egp FROM budget_targets ORDER BY id"
    ).fetchall()

    budget_targets = []
    for row in rows:
        cat    = row["category"]
        budget = float(row["monthly_egp"] or 0)
        try:
            actual = float(conn.execute(
                """SELECT COALESCE(SUM(amount), 0)
                   FROM expenses
                   WHERE expense_date >= ? AND expense_date <= ?
                   AND category = ?""",
                (month_start, today, cat)
            ).fetchone()[0] or 0)
        except Exception:
            actual = 0.0
        budget_targets.append({
            "category":  cat,
            "budget":    budget,
            "actual":    actual,
            "variance":  budget - actual,
            "pct_used":  round((actual / budget * 100) if budget > 0 else 0, 1),
        })

    conn.close()

    total_budget = sum(i["budget"] for i in budget_targets)
    total_actual = sum(i["actual"] for i in budget_targets)

    return render_template(
        "accounting/budget.html",
        active="accounting",
        page_title="Monthly Budget",
        budget_targets=budget_targets,
        total_budget=total_budget,
        total_actual=total_actual,
        month_label=date.today().strftime("%B %Y"),
    )
