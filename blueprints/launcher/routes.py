import os
import socket
import subprocess
import time

from flask import render_template, session, redirect, url_for, current_app
from . import launcher_bp
from blueprints.auth.routes import login_required
import models.database as db


# ─────────────────────────────────────────────
# MODULE DEFINITIONS
# ─────────────────────────────────────────────

# status: "active" | "beta" | "coming_soon" | "planned"
# legacy: True  →  opens the legacy Flask app at LEGACY_APP_URL
# target: "_blank" | "_self"

MODULES = [
    # ── CLINICAL ────────────────────────────────────────────────────────────
    {
        "id":          "examination",
        "name":        "Examination & Medical Records",
        "name_ar":     "الفحص والسجلات الطبية",
        "icon":        "🩺",
        "description": "Full visit workflow · Diagnosis · Prescriptions · Medical history · Visit summary",
        "url_key":     "launcher.launch_legacy",
        "url":         "/launcher/legacy/start",
        "target":      "_blank",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse","reception","staff"],
        "status":      "active",
        "category":    "clinical",
        "color":       "#1a3a6b",
        "badge":       "Live",
    },
    {
        "id":          "appointments",
        "name":        "Appointments & Reception",
        "name_ar":     "المواعيد والاستقبال",
        "icon":        "📅",
        "description": "Calendar · Walk-ins · Check-in/out · Reception queue · Doctor schedule",
        "url_key":     "appointments.schedule",
        "url":         "/appointments/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse","reception","staff"],
        "status":      "active",
        "category":    "clinical",
        "color":       "#0ea5e9",
        "badge":       "Live",
    },
    {
        "id":          "crm",
        "name":        "Owners & Pets CRM",
        "name_ar":     "إدارة الملاك والحيوانات",
        "icon":        "🐾",
        "description": "Owner profiles · Pet records · Medical timeline · Digital passport · Communication history",
        "url_key":     "crm.owners",
        "url":         "/crm/owners",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse","reception","staff","auditor"],
        "status":      "active",
        "category":    "clinical",
        "color":       "#8b5cf6",
        "badge":       "Live",
    },
    {
        "id":          "lab",
        "name":        "Laboratory & Diagnostics",
        "name_ar":     "المختبر والتشخيص",
        "icon":        "🔬",
        "description": "Lab test catalog · Sample collection · Results entry · AI summary · Pet timeline link",
        "url_key":     "clinical.lab",
        "url":         "/clinical/lab",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse"],
        "status":      "active",
        "category":    "clinical",
        "color":       "#06b6d4",
        "badge":       "Live",
    },
    {
        "id":          "vaccination",
        "name":        "Vaccination & Preventive Care",
        "name_ar":     "التطعيمات والرعاية الوقائية",
        "icon":        "💉",
        "description": "Vaccine catalog · Schedules · Certificates · Reminders · Pet passport integration",
        "url_key":     "clinical.vaccinations",
        "url":         "/clinical/vaccinations",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse","reception"],
        "status":      "active",
        "category":    "clinical",
        "color":       "#10b981",
        "badge":       "Live",
    },
    {
        "id":          "surgery",
        "name":        "Surgery & Procedures",
        "name_ar":     "الجراحة والإجراءات",
        "icon":        "🔧",
        "description": "Pre-op checklists · Consent forms · Anesthesia notes · Inventory deduction · Follow-up",
        "url_key":     "clinical.surgeries",
        "url":         "/clinical/surgeries",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse"],
        "status":      "active",
        "category":    "clinical",
        "color":       "#ef4444",
        "badge":       "Live",
    },
    # ── OPERATIONS ───────────────────────────────────────────────────────────
    {
        "id":          "grooming",
        "name":        "Grooming",
        "name_ar":     "التجميل",
        "icon":        "✂️",
        "description": "Service catalog · Booking · Before/after photos · Product usage · History timeline",
        "url_key":     "grooming.index",
        "url":         "/grooming/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","reception","groomer"],
        "status":      "active",
        "category":    "operations",
        "color":       "#f59e0b",
        "badge":       "Live",
    },
    {
        "id":          "boarding",
        "name":        "Boarding / Pet Hotel",
        "name_ar":     "إيواء الحيوانات / فندق الحيوانات",
        "icon":        "🏨",
        "description": "Room management · Bookings · Daily notes · Feeding instructions · WhatsApp updates",
        "url_key":     "boarding.index",
        "url":         "/boarding/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","reception","boarding_staff"],
        "status":      "active",
        "category":    "operations",
        "color":       "#84cc16",
        "badge":       "Live",
    },
    # ── INVENTORY & SUPPLY ────────────────────────────────────────────────────
    {
        "id":          "inventory",
        "name":        "Inventory & Warehouse",
        "name_ar":     "المخزون والمستودع",
        "icon":        "📦",
        "description": "Item master · Batch tracking · Expiry alerts · Stock movements · FEFO · Reorder rules",
        "url_key":     "inventory.index",
        "url":         "/inventory/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","inventory_mgr","pharmacist","doctor"],
        "status":      "active",
        "category":    "inventory",
        "color":       "#f97316",
        "badge":       "Live",
    },
    {
        "id":          "pharmacy",
        "name":        "Pharmacy & Medication",
        "name_ar":     "الصيدلية والأدوية",
        "icon":        "💊",
        "description": "Medication master · Prescription builder · Dispensing · Labels · Controlled drug log",
        "url_key":     "inventory.items_medications",
        "url":         "/inventory/items?is_medication=1",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","pharmacist","doctor","nurse"],
        "status":      "active",
        "category":    "inventory",
        "color":       "#6366f1",
        "badge":       "Live",
    },
    {
        "id":          "procurement",
        "name":        "Procurement & Suppliers",
        "name_ar":     "المشتريات والموردون",
        "icon":        "🛒",
        "description": "Supplier profiles · Purchase orders · Receiving notes · Stock auto-update on receipt",
        "url_key":     "procurement.dashboard",
        "url":         "/procurement/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","inventory_mgr","finance"],
        "status":      "active",
        "category":    "inventory",
        "color":       "#78716c",
        "badge":       "Live",
    },
    # ── FINANCE ──────────────────────────────────────────────────────────────
    {
        "id":          "invoicing",
        "name":        "Billing & Invoicing",
        "name_ar":     "الفواتير والفوترة",
        "icon":        "🧾",
        "description": "Auto-numbered invoices · Services + products · Discounts · Tax · PDF · WhatsApp send",
        "url_key":     "finance.invoices",
        "url":         "/finance/invoices",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","reception","finance","doctor"],
        "status":      "active",
        "category":    "finance",
        "color":       "#22c55e",
        "badge":       "Live",
    },
    {
        "id":          "finance",
        "name":        "Finance & Accounting",
        "name_ar":     "المالية والمحاسبة",
        "icon":        "💰",
        "description": "Revenue tracking · Payments · Expenses · Daily closing · P&L · Cash flow · Budget",
        "url_key":     "accounting.dashboard",
        "url":         "/accounting/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","finance"],
        "status":      "active",
        "category":    "finance",
        "color":       "#16a34a",
        "badge":       "Live",
    },
    # ── COMMUNICATION ─────────────────────────────────────────────────────────
    {
        "id":          "whatsapp",
        "name":        "WhatsApp Communication Center",
        "name_ar":     "مركز التواصل عبر واتساب",
        "icon":        "💬",
        "description": "Message templates · Reminders · Campaigns · Message log · Schedule · Retry failed",
        "url_key":     "whatsapp.control_center",
        "url":         "/whatsapp/control",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","reception"],
        "status":      "active",
        "category":    "communication",
        "color":       "#25d366",
        "badge":       "Live",
    },
    # ── WORKSPACES ────────────────────────────────────────────────────────────
    {
        "id":          "doctor_workspace",
        "name":        "Doctor Workspace",
        "name_ar":     "مساحة عمل الطبيب",
        "icon":        "👨‍⚕️",
        "description": "My patients today · Exam queue · Pet history · Quick prescription · Personal stats",
        "url_key":     "doctor.workspace",
        "url":         "/doctor/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","doctor","branch_manager"],
        "status":      "active",
        "category":    "workspaces",
        "color":       "#1a3a6b",
        "badge":       "Live",
    },
    {
        "id":          "reception_workspace",
        "name":        "Reception Workspace",
        "name_ar":     "مساحة عمل الاستقبال",
        "icon":        "🖥️",
        "description": "Queue management · Waiting room · Check-in/out · Quick booking · Owner lookup",
        "url_key":     "appointments.reception",
        "url":         "/appointments/reception",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","reception"],
        "status":      "active",
        "category":    "workspaces",
        "color":       "#0284c7",
        "badge":       "Live",
    },
    # ── INTELLIGENCE ──────────────────────────────────────────────────────────
    {
        "id":          "ai_assistant",
        "name":        "AI Assistant",
        "name_ar":     "المساعد الذكي",
        "icon":        "🤖",
        "description": "Role-based AI · Medical summaries · Inventory forecasting · Finance insights · Support diagnostics",
        "url_key":     "ai.index",
        "url":         "/ai/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse","reception","finance","inventory_mgr"],
        "status":      "active",
        "category":    "intelligence",
        "color":       "#7c3aed",
        "badge":       "Live",
    },
    {
        "id":          "reports",
        "name":        "Reports & Executive Dashboard",
        "name_ar":     "التقارير ولوحة التحكم التنفيذية",
        "icon":        "📊",
        "description": "Revenue KPIs · Appointment stats · Doctor productivity · Inventory value · WhatsApp success",
        "url_key":     "reports.dashboard",
        "url":         "/reports/dashboard",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","finance","auditor"],
        "status":      "active",
        "category":    "intelligence",
        "color":       "#db2777",
        "badge":       "Live",
    },
    {
        "id":          "service_catalog",
        "name":        "Service & Price Catalog",
        "name_ar":     "كتالوج الخدمات والأسعار",
        "icon":        "📋",
        "description": "Billable services · Prices · Tax rates · Duration · Species-specific · Active/inactive toggle",
        "url_key":     "catalog.index",
        "url":         "/catalog/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","finance","reception","doctor","nurse"],
        "status":      "active",
        "category":    "operations",
        "color":       "#0369a1",
        "badge":       "Live",
    },
    {
        "id":          "pharmacy_dispense",
        "name":        "Pharmacy Dispensing",
        "name_ar":     "صرف الصيدلية",
        "icon":        "💊",
        "description": "Dispensing queue · FEFO batch selection · Controlled drug log · Print labels · History",
        "url_key":     "pharmacy.index",
        "url":         "/pharmacy/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","pharmacist","doctor","nurse","inventory_mgr"],
        "status":      "active",
        "category":    "operations",
        "color":       "#7c3aed",
        "badge":       "Live",
    },
    {
        "id":          "notifications",
        "name":        "Notifications Center",
        "name_ar":     "مركز الإشعارات",
        "icon":        "🔔",
        "description": "In-app alerts · Role-based notifications · Backup alerts · Mark read · Unread count",
        "url_key":     "notifications.index",
        "url":         "/notifications/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","doctor","nurse","reception","finance","inventory_mgr","hr"],
        "status":      "active",
        "category":    "communication",
        "color":       "#dc2626",
        "badge":       "Live",
    },
    # ── ADMIN ─────────────────────────────────────────────────────────────────
    {
        "id":          "attendance",
        "name":        "Attendance & Leave Management",
        "name_ar":     "الحضور وإدارة الإجازات",
        "icon":        "⏱",
        "description": "Check-in/out · Shifts · Leave requests · Balances · Monthly reports · Public holidays",
        "url_key":     "attendance.dashboard",
        "url":         "/attendance/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","hr","staff","doctor","nurse","reception"],
        "status":      "active",
        "category":    "admin",
        "color":       "#0891b2",
        "badge":       "Live",
    },
    {
        "id":          "hr",
        "name":        "Admin & HR",
        "name_ar":     "الإدارة والموارد البشرية",
        "icon":        "👥",
        "description": "Staff management · Schedules · Commissions · Permissions · Department setup",
        "url_key":     "hr.staff",
        "url":         "/hr/staff",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager"],
        "status":      "active",
        "category":    "admin",
        "color":       "#374151",
        "badge":       "Live",
    },
    {
        "id":          "multi_branch",
        "name":        "Multi-Branch Control Center",
        "name_ar":     "مركز التحكم متعدد الفروع",
        "icon":        "🌐",
        "description": "Branch comparison · Cross-branch inventory · Unified reporting · Branch-level P&L",
        "url_key":     "module_stub",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner"],
        "status":      "planned",
        "category":    "admin",
        "color":       "#1e40af",
        "badge":       "Future",
    },
    # ── COMMERCIAL ───────────────────────────────────────────────────────────
    {
        "id":          "petshop",
        "name":        "Pet Shop & POS",
        "name_ar":     "متجر الحيوانات ونقطة البيع",
        "icon":        "🏪",
        "description": "Products · Stock management · Point-of-sale · Orders · Revenue reports · FEFO",
        "url_key":     "petshop.index",
        "url":         "/petshop/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","branch_manager","receptionist","reception","finance","support_admin","staff"],
        "status":      "active",
        "category":    "commercial",
        "color":       "#e8920a",
        "badge":       "Live",
    },
    # ── SYSTEM ────────────────────────────────────────────────────────────────
    {
        "id":          "migration",
        "name":        "Data Migration",
        "name_ar":     "ترحيل البيانات",
        "icon":        "🔄",
        "description": "Import legacy Excel clinic data into the unified platform · Patients · Visits · Owners",
        "url_key":     "migration.index",
        "url":         "/migration/",
        "legacy":      False,
        "roles":       ["super_admin","clinic_owner","support_admin"],
        "status":      "active",
        "category":    "system",
        "color":       "#64748b",
        "badge":       "Live",
    },
    {
        "id":          "system_monitor",
        "name":        "System Monitor & Diagnostics",
        "name_ar":     "مراقبة النظام والتشخيص",
        "icon":        "🖥",
        "description": "App health · DB check · WhatsApp status · Error logs · Audit trail · Support package",
        "url_key":     "system.monitor",
        "url":         "/system/monitor",
        "legacy":      False,
        "roles":       ["super_admin","support_admin"],
        "status":      "active",
        "category":    "system",
        "color":       "#475569",
        "badge":       "Live",
    },
    {
        "id":          "settings",
        "name":        "Settings & Configuration",
        "name_ar":     "الإعدادات والتكوين",
        "icon":        "⚙️",
        "description": "Clinic profile · Users · Roles · Permissions · Theme · Integrations · Backup",
        "url_key":     "legacy_config",
        "legacy":      True,
        "legacy_path": "/config",
        "roles":       ["super_admin","clinic_owner"],
        "status":      "active",
        "category":    "system",
        "color":       "#64748b",
        "badge":       "Live",
    },
]

CATEGORY_META = {
    "clinical":      {"label": "Clinical",           "label_ar": "السريرية",       "icon": "🩺"},
    "operations":    {"label": "Operations",          "label_ar": "العمليات",       "icon": "⚙️"},
    "inventory":     {"label": "Inventory & Supply",  "label_ar": "المخزون",        "icon": "📦"},
    "commercial":    {"label": "Commercial & Retail", "label_ar": "التجاري والبيع بالتجزئة", "icon": "🏪"},
    "finance":       {"label": "Finance",             "label_ar": "المالية",        "icon": "💰"},
    "communication": {"label": "Communication",       "label_ar": "التواصل",        "icon": "💬"},
    "workspaces":    {"label": "Workspaces",          "label_ar": "مساحات العمل",   "icon": "🖥️"},
    "intelligence":  {"label": "Intelligence & AI",   "label_ar": "الذكاء الاصطناعي","icon": "🤖"},
    "admin":         {"label": "Admin & HR",          "label_ar": "الإدارة",        "icon": "👥"},
    "system":        {"label": "System",              "label_ar": "النظام",         "icon": "🔧"},
}

_CATEGORY_ORDER = ["clinical","operations","inventory","commercial","finance","communication","workspaces","intelligence","admin","system"]


def _visible_modules(role: str) -> list:
    """Return modules visible to `role`, grouped by category."""
    user_role = role or "staff"
    visible = [m for m in MODULES if user_role in m["roles"] or user_role == "super_admin"]
    return visible


def _grouped(modules: list) -> list:
    """Return list of (category_meta, [modules]) in defined order."""
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for m in modules:
        groups[m["category"]].append(m)
    result = []
    for cat in _CATEGORY_ORDER:
        if cat in groups:
            result.append((CATEGORY_META[cat], groups[cat]))
    return result


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@launcher_bp.route("/")
def index():
    # Show animated landing page for guests; dashboard for logged-in users
    if not session.get("user"):
        return render_template("landing.html")
    user    = session["user"]
    role    = user.get("role", "")
    modules = _visible_modules(role)
    grouped = _grouped(modules)
    legacy_url = current_app.config.get("LEGACY_APP_URL", "http://localhost:5000")

    # Live stats from platform DB
    platform_stats = db.get_dashboard_stats()
    stats = {
        "owners":            platform_stats.get("owners_total", 0),
        "pets":              platform_stats.get("pets_total", 0),
        "bookings_today":    platform_stats.get("appts_today", 0),
        "pending_reminders": platform_stats.get("pending_reminders", 0),
        "revenue_today":     platform_stats.get("revenue_today", 0),
        "visits_today":      platform_stats.get("visits_today", 0),
        "invoices_unpaid":   platform_stats.get("invoices_unpaid", 0),
        "outstanding":       platform_stats.get("outstanding", 0),
    }

    return render_template(
        "launcher.html",
        modules=modules,
        grouped=grouped,
        stats=stats,
        legacy_url=legacy_url,
        active_count=sum(1 for m in modules if m["status"] == "active"),
        total_count=len(MODULES),
    )


@launcher_bp.route("/module/<module_id>")
@login_required
def open_module(module_id: str):
    """Redirect to a module — legacy app or platform stub."""
    user = session["user"]
    role = user.get("role", "")
    legacy_url = current_app.config.get("LEGACY_APP_URL", "http://localhost:5000")

    mod = next((m for m in MODULES if m["id"] == module_id), None)
    if not mod:
        from flask import abort
        abort(404)

    # Access check
    if role not in mod["roles"] and role != "super_admin":
        from flask import flash
        from flask import redirect
        from flask import url_for
        flash("You don't have access to this module.", "danger")
        return redirect(url_for("launcher.index"))

    db.log_audit(
        username=user.get("username", ""),
        role=role,
        action="open_module",
        module=module_id,
        details=mod["name"],
        ip="",
    )

    if mod.get("legacy"):
        path = mod.get("legacy_path", "/")
        from flask import redirect as redir
        return redir(legacy_url + path)

    from flask import redirect as redir
    return redir(url_for("launcher.stub", module_id=module_id))


@launcher_bp.route("/module/<module_id>/stub")
@login_required
def stub(module_id: str):
    mod = next((m for m in MODULES if m["id"] == module_id), None)
    return render_template("stub.html", mod=mod)


def _legacy_port_open(port: int = 5000) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


@launcher_bp.route("/launcher/legacy/start")
@login_required
def launch_legacy():
    """Start the legacy examination app if not running, then redirect to it."""
    legacy_url = current_app.config.get("LEGACY_APP_URL", "http://localhost:5000")
    port = int(legacy_url.rsplit(":", 1)[-1]) if ":" in legacy_url.split("//", 1)[-1] else 5000

    if not _legacy_port_open(port):
        legacy_dir = os.path.abspath(
            os.path.join(current_app.root_path, "..", "ppc_diagnostics_work")
        )
        subprocess.Popen(
            ["python", "app.py"],
            cwd=legacy_dir,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        # Wait up to 12 seconds for the app to bind its port
        for _ in range(24):
            time.sleep(0.5)
            if _legacy_port_open(port):
                break

    return redirect(legacy_url + "/")


@launcher_bp.route("/launcher/legacy/ping")
@login_required
def legacy_ping():
    """Return JSON status of whether the legacy app is reachable."""
    from flask import jsonify
    up = _legacy_port_open(5000)
    return jsonify({"up": up})
