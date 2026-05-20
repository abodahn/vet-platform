"""
Petsy — Animal-inspired AI Chatbot + Internal Platform Search Engine
- Public mode   : general vet / clinic Q&A (no auth)
- Staff mode    : live platform data (authenticated, role-aware)
  Understands natural-language queries about appointments, visits, invoices,
  stock, lab results, staff attendance, revenue, vaccinations, and more.
"""

import re
import time
from collections import defaultdict
from datetime import date, timedelta
from flask import render_template, request, jsonify, make_response, session
from . import petsy_bp

try:
    from openai import OpenAI as _OpenAI
    _OK = True
except ImportError:
    _OpenAI = None
    _OK = False

_BASE_URL = "http://localhost:3001/v1"
_API_KEY  = "freellmapi-4ddad5d50504e98e27a4001eb5422e23a89cc957233ea3d0"
_MODEL    = "gemini-2.5-flash"

# ── Rate limiter (public endpoint) ────────────────────────────────────────────
_rate: dict = defaultdict(list)
_RATE_WIN = 60
_RATE_MAX = 15


def _allow(ip: str) -> bool:
    now = time.time()
    _rate[ip] = [t for t in _rate[ip] if now - t < _RATE_WIN]
    if len(_rate[ip]) >= _RATE_MAX:
        return False
    _rate[ip].append(now)
    return True


# ══════════════════════════════════════════════════════════════════════════════
#  SYSTEM PROMPTS
# ══════════════════════════════════════════════════════════════════════════════

_PUBLIC_SYSTEM = """\
You are Petsy 🐾, the friendly AI chatbot for Premium Animal Hospital (Dr. Hatem El Khateeb).
Respond warmly, professionally, and concisely. Bilingual: English & Arabic — reply in the user's language.

You can help with: services (consultations, vaccinations, surgery, grooming, boarding, pharmacy),
appointments, general pet health advice, medication guidance, pet care tips, and clinic info.

For medical questions always add: ⚕️ Always consult Dr. Hatem or a licensed veterinarian.\
"""

_STAFF_SYSTEM = """\
You are Petsy 🐾, the internal AI assistant for Premium Animal Hospital (Dr. Hatem El Khateeb).
You are speaking with a staff member: {name} ({role}).
Respond professionally and concisely. Bilingual: reply in the user's language.

You have access to LIVE CLINIC DATA injected below (when relevant to the question).
When data is provided, summarise it clearly and helpfully — like a smart dashboard.
When no data is provided, answer from your veterinary and clinic knowledge.

Guidelines:
- Format lists with bullets or a clean table. Use emojis sparingly.
- If the user asks to "show", "list", "find", "how many", "what", "who" — use the data.
- For medical/clinical questions add: ⚕️ Verify with Dr. Hatem or a licensed vet.
- Be concise — staff are busy. Lead with the answer, then details.\
"""


# ══════════════════════════════════════════════════════════════════════════════
#  INTENT DETECTION
# ══════════════════════════════════════════════════════════════════════════════

def _kw(*words):
    """Return a compiled regex that matches any of the given words/phrases."""
    pattern = "|".join(re.escape(w) for w in words)
    return re.compile(pattern, re.IGNORECASE)

_INTENTS = [
    # (intent_name, regex)
    ("appointments_today",    _kw("appointment today","booking today","schedule today",
                                  "موعد اليوم","مواعيد اليوم","appointments today")),
    ("appointments_upcoming", _kw("upcoming appointment","this week","next appointment",
                                  "tomorrow appointment","next few days","المواعيد القادمة")),
    ("visits_open",           _kw("open visit","active visit","current patient","seeing now",
                                  "who is in","who's here now","الزيارات المفتوحة","زيارة مفتوحة")),
    ("visits_today",          _kw("visit today","seen today","patients today",
                                  "زيارات اليوم","مرضى اليوم")),
    ("pending_invoices",      _kw("unpaid","pending invoice","outstanding","owes money",
                                  "not paid","overdue","balance due","فاتورة غير مدفوعة",
                                  "مديونية","فواتير معلقة")),
    ("revenue_today",         _kw("revenue today","income today","collected today",
                                  "payment today","how much today","إيراد اليوم","دخل اليوم")),
    ("revenue_month",         _kw("revenue this month","income this month","monthly revenue",
                                  "this month earnings","إيراد الشهر","دخل الشهر")),
    ("low_stock",             _kw("low stock","running out","reorder","out of stock",
                                  "shortage","need to order","مخزون منخفض","نفذ")),
    ("expiry_alerts",         _kw("expir","about to expire","expiry","expire soon",
                                  "انتهاء صلاحية","قرب انتهاء")),
    ("lab_pending",           _kw("pending lab","lab result","test result","waiting result",
                                  "نتيجة مختبر","تحليل معلق","نتيجة معلقة")),
    ("vaccinations_due",      _kw("vaccination due","vaccine due","overdue vaccine",
                                  "due for vaccine","تطعيم مستحق","موعد التطعيم")),
    ("attendance_today",      _kw("attendance today","who is present","who is absent",
                                  "staff today","حضور اليوم","من حضر","من غاب")),
    ("recent_patients",       _kw("recent patient","new patient","latest patient",
                                  "last patient","new owner","آخر مريض","مريض جديد")),
    ("dashboard_stats",       _kw("summary","overview","dashboard","how many","statistics",
                                  "stats","total today","ملخص","احصائية","كم عدد")),
    ("search_owner",          _kw("find owner","search owner","find client","find patient",
                                  "look up","ابحث عن","جد مريض")),
    ("grooming_today",        _kw("grooming today","grooming appointment","تجميل اليوم")),
    ("boarding_current",      _kw("boarding","who is boarding","current boarders",
                                  "checked in","الإيواء","الحيوانات المقيمة")),
    ("prescriptions_pending", _kw("pending prescription","not dispensed","rx pending",
                                  "وصفة معلقة","وصفة غير صرفت")),
]


def _detect_intents(msg: str) -> list[str]:
    return [name for name, rgx in _INTENTS if rgx.search(msg)]


# ══════════════════════════════════════════════════════════════════════════════
#  LIVE DATA FETCHER
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_row(row: dict, keys: list, sep: str = " | ") -> str:
    return sep.join(str(row.get(k) or "—") for k in keys)


def _fetch_platform_data(message: str, user: dict) -> str:
    """
    Detect what the user is asking about, query the DB, and return a
    formatted plain-text data block to inject into the system prompt.
    Returns empty string if no data is relevant.
    """
    try:
        import models.database as db
    except ImportError:
        return ""

    intents = _detect_intents(message)
    if not intents:
        return ""

    role    = user.get("role", "")
    uname   = user.get("full_name", user.get("username", ""))
    today   = date.today().isoformat()
    week_end= (date.today() + timedelta(days=7)).isoformat()
    month_s = date.today().replace(day=1).isoformat()

    blocks = []
    conn   = db.get_db()

    import logging as _log
    _logger = _log.getLogger(__name__)

    # Helper: run a query safely; returns [] / None on failure and logs the error
    def _q(sql, params=()):
        try:
            return conn.execute(sql, params).fetchall()
        except Exception as _e:
            _logger.error("Petsy query error: %s | SQL: %s", _e, sql[:120])
            return []

    def _q1(sql, params=()):
        try:
            return conn.execute(sql, params).fetchone()
        except Exception as _e:
            _logger.error("Petsy query error: %s | SQL: %s", _e, sql[:120])
            return None

    # PostgreSQL-safe date cast: use SUBSTRING so TEXT and TIMESTAMP both work
    # e.g.  SUBSTRING(received_at::text, 1, 10) = '2026-05-20'
    def _date_eq(col):
        return f"SUBSTRING({col}::text, 1, 10)"

    try:
        # ── Doctor filter: doctors only see their own appointments by default ──
        doc_filter = ""
        doc_params_appt: list = []
        if role == "doctor":
            doc_filter = "AND doctor_name = %s"
            doc_params_appt = [uname]

        # ── APPOINTMENTS TODAY ────────────────────────────────────────────────
        if "appointments_today" in intents:
            rows = _q(f"""
                SELECT appt_start, pet_name, o.full_name AS owner,
                       appointment_type, status, doctor_name
                FROM appointments a
                LEFT JOIN owners o ON o.id = a.owner_id
                WHERE appt_date = %s AND status NOT IN ('Cancelled','NoShow')
                {doc_filter}
                ORDER BY appt_start
                LIMIT 30
            """, [today] + doc_params_appt)
            if rows:
                lines = [f"📅 TODAY'S APPOINTMENTS ({today}) — {len(rows)} total:"]
                for r in rows:
                    lines.append(f"  {r['appt_start'] or '?':5}  {r['pet_name'] or '?':<14} "
                                 f"({r['owner'] or '?'})  [{r['status']}]  "
                                 f"{r['appointment_type'] or ''}  Dr.{r['doctor_name'] or '?'}")
                blocks.append("\n".join(lines))
            else:
                blocks.append(f"📅 No appointments found for today ({today}).")

        # ── APPOINTMENTS UPCOMING ─────────────────────────────────────────────
        if "appointments_upcoming" in intents:
            rows = _q(f"""
                SELECT appt_date, appt_start, pet_name, o.full_name AS owner,
                       appointment_type, status, doctor_name
                FROM appointments a
                LEFT JOIN owners o ON o.id = a.owner_id
                WHERE appt_date > %s AND appt_date <= %s
                  AND status NOT IN ('Cancelled','NoShow')
                {doc_filter}
                ORDER BY appt_date, appt_start
                LIMIT 20
            """, [today, week_end] + doc_params_appt)
            if rows:
                lines = [f"📆 UPCOMING APPOINTMENTS (next 7 days) — {len(rows)} total:"]
                for r in rows:
                    lines.append(f"  {str(r['appt_date'])[:10]}  {r['appt_start'] or '':5}  "
                                 f"{r['pet_name'] or '?':<14} ({r['owner'] or '?'})  "
                                 f"[{r['status']}]  Dr.{r['doctor_name'] or '?'}")
                blocks.append("\n".join(lines))
            else:
                blocks.append("📆 No upcoming appointments in the next 7 days.")

        # ── OPEN VISITS ───────────────────────────────────────────────────────
        if "visits_open" in intents:
            rows = _q(f"""
                SELECT v.id, p.pet_name, o.full_name AS owner,
                       v.chief_complaint, v.doctor_name, v.visit_date
                FROM visits v
                JOIN pets  p ON p.id = v.pet_id
                JOIN owners o ON o.id = v.owner_id
                WHERE v.status = 'Open'
                {('AND v.doctor_name = %s' if role=='doctor' else '')}
                ORDER BY v.visit_date DESC
                LIMIT 20
            """, ([uname] if role == "doctor" else []))
            if rows:
                lines = [f"🏥 CURRENTLY OPEN VISITS — {len(rows)} active:"]
                for r in rows:
                    lines.append(f"  Visit #{r['id']}  {r['pet_name']:<14} "
                                 f"({r['owner']})  Dr.{r['doctor_name'] or '?'}  "
                                 f"— {r['chief_complaint'] or 'no complaint noted'}")
                blocks.append("\n".join(lines))
            else:
                blocks.append("🏥 No open visits right now.")

        # ── VISITS TODAY ─────────────────────────────────────────────────────
        if "visits_today" in intents:
            _df = _date_eq("v.visit_date")
            rows = _q(f"""
                SELECT v.id, p.pet_name, o.full_name AS owner,
                       v.status, v.doctor_name, v.visit_type
                FROM visits v
                JOIN pets  p ON p.id = v.pet_id
                JOIN owners o ON o.id = v.owner_id
                WHERE {_df} = %s
                {('AND v.doctor_name = %s' if role=='doctor' else '')}
                ORDER BY v.visit_date
                LIMIT 30
            """, ([today, uname] if role == "doctor" else [today]))
            if rows:
                lines = [f"📋 VISITS TODAY ({today}) — {len(rows)} total:"]
                for r in rows:
                    lines.append(f"  #{r['id']} {r['pet_name']:<14} ({r['owner']})  "
                                 f"[{r['status']}]  {r['visit_type'] or ''}  "
                                 f"Dr.{r['doctor_name'] or '?'}")
                blocks.append("\n".join(lines))
            else:
                blocks.append(f"📋 No visits recorded today ({today}).")

        # ── PENDING INVOICES ──────────────────────────────────────────────────
        if "pending_invoices" in intents:
            rows = _q("""
                SELECT i.invoice_number, o.full_name AS owner,
                       i.total, i.due_amount, i.status, i.issue_date,
                       COALESCE(i.due_amount, i.total) AS balance_due
                FROM invoices i
                LEFT JOIN owners o ON o.id = i.owner_id
                WHERE i.status IN ('Unpaid','Overdue','Partial')
                ORDER BY i.issue_date
                LIMIT 25
            """)
            total = sum(float(r["balance_due"] or 0) for r in rows)
            if rows:
                lines = [f"💸 UNPAID INVOICES — {len(rows)} invoices, "
                         f"total outstanding: {total:,.2f} EGP"]
                for r in rows:
                    lines.append(f"  {r['invoice_number']}  {str(r['issue_date'])[:10]}  "
                                 f"{r['owner'] or '?':<20} "
                                 f"Balance: {float(r['balance_due'] or 0):,.2f} EGP  [{r['status']}]")
                blocks.append("\n".join(lines))
            else:
                blocks.append("💸 No pending invoices — all cleared!")

        # ── REVENUE TODAY ─────────────────────────────────────────────────────
        if "revenue_today" in intents:
            _df = _date_eq("received_at")
            row = _q1(f"""
                SELECT COALESCE(SUM(amount),0) AS collected,
                       COUNT(*) AS transactions
                FROM payments WHERE {_df} = %s
            """, (today,))
            inv = _q1("""
                SELECT COALESCE(SUM(total),0) AS invoiced,
                       COUNT(*) AS count
                FROM invoices WHERE SUBSTRING(issue_date::text,1,10) = %s
                  AND status != 'Cancelled'
            """, (today,))
            if row is not None:
                blocks.append(
                    f"💰 REVENUE TODAY ({today}):\n"
                    f"  Collected (payments): {float(row['collected'] or 0):,.2f} EGP "
                    f"({row['transactions']} transactions)\n"
                    f"  Invoiced today: {float((inv or {}).get('invoiced') or 0):,.2f} EGP "
                    f"({(inv or {}).get('count', 0)} invoices)"
                )

        # ── REVENUE THIS MONTH ────────────────────────────────────────────────
        if "revenue_month" in intents:
            _df = _date_eq("received_at")
            row = _q1(f"""
                SELECT COALESCE(SUM(amount),0) AS collected, COUNT(*) AS tx
                FROM payments WHERE {_df} >= %s
            """, (month_s,))
            exp = _q1("""
                SELECT COALESCE(SUM(amount),0) AS expenses
                FROM expenses WHERE SUBSTRING(expense_date::text,1,10) >= %s
            """, (month_s,))
            if row is not None:
                collected = float(row["collected"] or 0)
                expenses  = float((exp or {}).get("expenses") or 0)
                blocks.append(
                    f"📊 REVENUE THIS MONTH (from {month_s}):\n"
                    f"  Collected: {collected:,.2f} EGP ({row['tx']} payments)\n"
                    f"  Expenses:  {expenses:,.2f} EGP\n"
                    f"  Net profit: {collected - expenses:,.2f} EGP"
                )

        # ── LOW STOCK ─────────────────────────────────────────────────────────
        if "low_stock" in intents:
            rows = _q("""
                SELECT i.name, i.sku, ic.name AS category, i.unit,
                       COALESCE(SUM(b.quantity),0) AS qty,
                       i.reorder_level
                FROM items i
                LEFT JOIN item_categories ic ON ic.id = i.category_id
                LEFT JOIN batches b ON b.item_id = i.id
                WHERE i.is_active = 1
                GROUP BY i.id, i.name, i.sku, ic.name, i.unit, i.reorder_level
                HAVING COALESCE(SUM(b.quantity),0) <= i.reorder_level
                ORDER BY qty ASC
                LIMIT 30
            """)
            if rows:
                lines = [f"⚠️ LOW STOCK ITEMS — {len(rows)} items need reorder:"]
                for r in rows:
                    lines.append(f"  {r['name']:<28} "
                                 f"Stock: {r['qty']} {r['unit'] or ''}  "
                                 f"Reorder at: {r['reorder_level']}  "
                                 f"[{r['category'] or '?'}]")
                blocks.append("\n".join(lines))
            else:
                blocks.append("✅ All stock levels are above reorder points — nothing critical.")

        # ── EXPIRY ALERTS ─────────────────────────────────────────────────────
        if "expiry_alerts" in intents:
            exp90 = (date.today() + timedelta(days=90)).isoformat()
            rows = _q("""
                SELECT b.batch_number, i.name AS item_name, b.quantity, i.unit, b.expiry_date
                FROM batches b JOIN items i ON i.id = b.item_id
                WHERE SUBSTRING(b.expiry_date::text,1,10) <= %s AND b.quantity > 0
                ORDER BY b.expiry_date LIMIT 25
            """, (exp90,))
            if rows:
                lines = [f"⏰ EXPIRY ALERTS — {len(rows)} batches expiring within 90 days:"]
                for r in rows:
                    try:
                        days_left = (date.fromisoformat(str(r["expiry_date"])[:10]) - date.today()).days
                    except Exception:
                        days_left = "?"
                    lines.append(f"  {r['item_name']:<28} "
                                 f"Qty: {r['quantity']} {r['unit'] or ''}  "
                                 f"Expires: {str(r['expiry_date'])[:10]} "
                                 f"({days_left} days)")
                blocks.append("\n".join(lines))
            else:
                blocks.append("✅ No items expiring within 90 days.")

        # ── PENDING LAB REQUESTS ──────────────────────────────────────────────
        if "lab_pending" in intents:
            rows = _q("""
                SELECT lr.id, p.pet_name, o.full_name AS owner,
                       lr.test_name, lr.priority, lr.created_at
                FROM lab_requests lr
                JOIN pets   p ON p.id = lr.pet_id
                JOIN owners o ON o.id = lr.owner_id
                WHERE lr.status IN ('Pending','In Progress')
                ORDER BY lr.priority DESC, lr.created_at
                LIMIT 20
            """)
            if rows:
                lines = [f"🔬 PENDING LAB REQUESTS — {len(rows)} awaiting results:"]
                for r in rows:
                    lines.append(f"  Lab #{r['id']}  {r['pet_name']:<14} ({r['owner']})  "
                                 f"{r['test_name']}  [{r['priority'] or 'Normal'}]  "
                                 f"Ordered: {str(r['created_at'])[:10]}")
                blocks.append("\n".join(lines))
            else:
                blocks.append("🔬 No pending lab requests.")

        # ── VACCINATIONS DUE ──────────────────────────────────────────────────
        if "vaccinations_due" in intents:
            due30 = (date.today() + timedelta(days=30)).isoformat()
            rows = _q("""
                SELECT v.vaccine_name, p.pet_name, o.full_name AS owner, v.next_due_at
                FROM vaccinations v
                JOIN pets   p ON p.id = v.pet_id
                JOIN owners o ON o.id = p.owner_id
                WHERE SUBSTRING(v.next_due_at::text,1,10) BETWEEN %s AND %s
                ORDER BY v.next_due_at
                LIMIT 25
            """, (today, due30))
            if rows:
                lines = [f"💉 VACCINATIONS DUE (next 30 days) — {len(rows)} patients:"]
                for r in rows:
                    try:
                        days = (date.fromisoformat(str(r["next_due_at"])[:10]) - date.today()).days
                        due_str = "today" if days == 0 else f"in {days}d"
                    except Exception:
                        due_str = ""
                    lines.append(f"  {r['pet_name']:<14} ({r['owner']})  "
                                 f"{r['vaccine_name']}  "
                                 f"Due: {str(r['next_due_at'])[:10]} ({due_str})")
                blocks.append("\n".join(lines))
            else:
                blocks.append("💉 No vaccinations due in the next 30 days.")

        # ── STAFF ATTENDANCE ──────────────────────────────────────────────────
        if "attendance_today" in intents:
            rows = _q("""
                SELECT u.full_name, u.role, ar.check_in, ar.check_out, ar.status
                FROM attendance_records ar
                JOIN users u ON u.id = ar.user_id
                WHERE SUBSTRING(ar.work_date::text,1,10) = %s
                ORDER BY ar.check_in
                LIMIT 30
            """, (today,))
            if rows:
                lines = [f"👥 STAFF ATTENDANCE TODAY ({today}) — {len(rows)} records:"]
                for r in rows:
                    ci = str(r["check_in"] or "—")[:5]
                    co = str(r["check_out"] or "—")[:5]
                    lines.append(f"  {r['full_name']:<22} [{r['role']:<15}]  "
                                 f"{r['status']}  in:{ci} out:{co}")
                blocks.append("\n".join(lines))
            else:
                blocks.append(f"👥 No attendance records yet for today ({today}).")

        # ── RECENT / NEW PATIENTS ─────────────────────────────────────────────
        if "recent_patients" in intents:
            rows = _q("""
                SELECT p.pet_name, p.species, p.breed, o.full_name AS owner,
                       o.phone, p.created_at
                FROM pets p JOIN owners o ON o.id = p.owner_id
                ORDER BY p.created_at DESC LIMIT 10
            """)
            if rows:
                lines = ["🐾 MOST RECENT PATIENTS (last 10 registered):"]
                for r in rows:
                    lines.append(f"  {r['pet_name']:<14} {r['species'] or '':<8} "
                                 f"({r['breed'] or 'mixed'})  "
                                 f"Owner: {r['owner']}  {r['phone'] or ''}  "
                                 f"Reg: {str(r['created_at'])[:10]}")
                blocks.append("\n".join(lines))

        # ── DASHBOARD STATS ───────────────────────────────────────────────────
        if "dashboard_stats" in intents:
            _df_v  = _date_eq("visit_date")
            _df_p  = _date_eq("received_at")
            c   = (_q1("SELECT COUNT(*) AS n FROM appointments WHERE appt_date = %s "
                       "AND status NOT IN ('Cancelled','NoShow')", (today,)) or {}).get("n", 0)
            v   = (_q1(f"SELECT COUNT(*) AS n FROM visits WHERE {_df_v} = %s", (today,)) or {}).get("n", 0)
            vo  = (_q1("SELECT COUNT(*) AS n FROM visits WHERE status = 'Open'") or {}).get("n", 0)
            pi  = (_q1("SELECT COUNT(*) AS n FROM invoices WHERE status IN ('Pending','Overdue')") or {}).get("n", 0)
            rev = (_q1(f"SELECT COALESCE(SUM(amount),0) AS s FROM payments WHERE {_df_p} = %s", (today,)) or {}).get("s", 0)
            ls  = _q("SELECT i.id FROM items i LEFT JOIN batches b ON b.item_id=i.id "
                     "WHERE i.is_active=1 GROUP BY i.id, i.reorder_level "
                     "HAVING COALESCE(SUM(b.quantity),0) <= i.reorder_level")
            blocks.append(
                f"📊 CLINIC DASHBOARD — {today}:\n"
                f"  Appointments today:   {c}\n"
                f"  Visits today:         {v}\n"
                f"  Open visits (active): {vo}\n"
                f"  Unpaid invoices:      {pi}\n"
                f"  Revenue today:        {float(rev or 0):,.2f} EGP\n"
                f"  Low stock items:      {len(ls)}"
            )

        # ── GROOMING TODAY ────────────────────────────────────────────────────
        if "grooming_today" in intents:
            rows = _q("""
                SELECT gb.booking_date, gb.start_time, p.pet_name,
                       o.full_name AS owner, gs.name AS service, gb.status
                FROM grooming_bookings gb
                JOIN pets  p ON p.id = gb.pet_id
                JOIN owners o ON o.id = gb.owner_id
                JOIN grooming_services gs ON gs.id = gb.service_id
                WHERE gb.booking_date = %s
                ORDER BY gb.start_time
                LIMIT 20
            """, (today,))
            if rows:
                lines = [f"✂️ GROOMING TODAY ({today}) — {len(rows)} bookings:"]
                for r in rows:
                    lines.append(f"  {r['start_time'] or '?':5}  {r['pet_name']:<14} "
                                 f"({r['owner']})  {r['service']}  [{r['status']}]")
                blocks.append("\n".join(lines))
            else:
                blocks.append(f"✂️ No grooming bookings for today ({today}).")

        # ── BOARDING CURRENT ──────────────────────────────────────────────────
        if "boarding_current" in intents:
            rows = _q("""
                SELECT br.name AS room, p.pet_name, o.full_name AS owner,
                       bb.check_in_date, bb.expected_checkout
                FROM boarding_bookings bb
                JOIN boarding_rooms br ON br.id = bb.room_id
                JOIN pets   p ON p.id = bb.pet_id
                JOIN owners o ON o.id = bb.owner_id
                WHERE bb.status = 'Active'
                ORDER BY bb.check_in_date
                LIMIT 20
            """)
            if rows:
                lines = [f"🏨 CURRENT BOARDERS — {len(rows)} pets staying:"]
                for r in rows:
                    co = str(r["expected_checkout"] or "?")[:10]
                    lines.append(f"  Room {r['room']:<8}  {r['pet_name']:<14} "
                                 f"({r['owner']})  "
                                 f"Check-in: {str(r['check_in_date'])[:10]}  "
                                 f"Expected out: {co}")
                blocks.append("\n".join(lines))
            else:
                blocks.append("🏨 No animals currently boarding.")

        # ── PENDING PRESCRIPTIONS ─────────────────────────────────────────────
        if "prescriptions_pending" in intents:
            rows = _q("""
                SELECT pr.id, p.pet_name, o.full_name AS owner,
                       pr.created_at, pr.status
                FROM prescriptions pr
                JOIN pets   p ON p.id = pr.pet_id
                JOIN owners o ON o.id = pr.owner_id
                WHERE pr.status = 'Active'
                ORDER BY pr.created_at DESC
                LIMIT 20
            """)
            if rows:
                lines = [f"💊 PENDING PRESCRIPTIONS (not yet dispensed) — {len(rows)}:"]
                for r in rows:
                    lines.append(f"  Rx #{r['id']}  {r['pet_name']:<14} ({r['owner']})  "
                                 f"Created: {str(r['created_at'])[:10]}")
                blocks.append("\n".join(lines))
            else:
                blocks.append("💊 All prescriptions have been dispensed.")

        # ── FREE-TEXT OWNER/PATIENT SEARCH ────────────────────────────────────
        if "search_owner" in intents or (not intents and len(message.split()) <= 4):
            clean = re.sub(r'\b(find|search|look up|show|who is|owner|patient|client)\b',
                           '', message, flags=re.IGNORECASE).strip()
            if len(clean) >= 3:
                rows = _q("""
                    SELECT o.full_name, o.phone, p.pet_name, p.species
                    FROM owners o
                    LEFT JOIN pets p ON p.owner_id = o.id
                    WHERE o.full_name ILIKE %s OR p.pet_name ILIKE %s
                    LIMIT 10
                """, (f"%{clean}%", f"%{clean}%"))
                if rows:
                    lines = [f"🔍 SEARCH RESULTS for '{clean}':"]
                    for r in rows:
                        lines.append(f"  {r['full_name']:<22} {r['phone'] or '':<14} "
                                     f"Pet: {r['pet_name'] or '?'} ({r['species'] or '?'})")
                    blocks.append("\n".join(lines))

    except Exception as e:
        _logger.error("Petsy _fetch_platform_data outer error: %s", e, exc_info=True)
    finally:
        conn.close()

    if not blocks:
        return ""
    return "\n\n".join(blocks)


# ══════════════════════════════════════════════════════════════════════════════
#  AI CALLER
# ══════════════════════════════════════════════════════════════════════════════

def _call_petsy(messages: list, system: str) -> tuple[str, str]:
    if not _OK:
        return "AI requires the openai package. Run: pip install openai", "none"
    try:
        client = _OpenAI(base_url=_BASE_URL, api_key=_API_KEY)
        full   = [{"role": "system", "content": system}, *messages]
        resp   = client.chat.completions.create(
            model=_MODEL, messages=full, max_tokens=800
        )
        text  = resp.choices[0].message.content or ""
        model = ""
        try:
            model = resp._raw_response.headers.get("x-routed-via", "") or resp.model or _MODEL
        except Exception:
            model = resp.model or _MODEL
        return text, model
    except Exception as e:
        return f"Petsy is temporarily unavailable: {e}", "none"


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@petsy_bp.route("/chat", methods=["POST"])
def chat():
    ip = request.remote_addr or "unknown"
    if not _allow(ip):
        return jsonify({"error": "Too many requests — please wait a moment."}), 429

    data    = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Build conversation turns
    messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history[-8:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    messages.append({"role": "user", "content": message})

    # ── Staff mode (authenticated) ────────────────────────────────────────────
    user = session.get("user")
    if user:
        # Fetch live platform data relevant to the question
        platform_data = _fetch_platform_data(message, user)

        # Build staff system prompt
        system = _STAFF_SYSTEM.format(
            name=user.get("full_name", user.get("username", "Staff")),
            role=user.get("role", "staff"),
        )
        if platform_data:
            system += (
                "\n\n══ LIVE CLINIC DATA (fetched right now from the database) ══\n"
                + platform_data
                + "\n══ END OF LIVE DATA ══"
            )

        reply, model = _call_petsy(messages, system)
        return jsonify({
            "reply":      reply,
            "model":      model,
            "staff_mode": True,
            "data_found": bool(platform_data),
        })

    # ── Public mode (not authenticated) ──────────────────────────────────────
    reply, model = _call_petsy(messages, _PUBLIC_SYSTEM)
    return jsonify({"reply": reply, "model": model, "staff_mode": False})


@petsy_bp.route("/embed")
def embed():
    """Standalone embeddable chat page — served inside an iframe."""
    clinic_name = "Premium Animal Hospital"
    is_staff    = bool(session.get("user"))
    try:
        import models.database as db
        c = db.get_clinic()
        clinic_name = c.get("name", clinic_name) if c else clinic_name
    except Exception:
        pass
    return render_template("petsy/embed.html",
                           clinic_name=clinic_name,
                           is_staff=is_staff)


@petsy_bp.route("/widget.js")
def widget_js():
    """Serve the embeddable widget JavaScript for external sites."""
    resp = make_response(render_template(
        "petsy/widget_js.html",
        base_url=request.host_url.rstrip("/"),
    ))
    resp.headers["Content-Type"]              = "application/javascript"
    resp.headers["Cache-Control"]             = "public, max-age=3600"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp
