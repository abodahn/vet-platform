# Dashboards, Reports and the AI Assistant — Reference Manual

**Modules covered**

| Module | Arabic | URL prefix | Blueprint |
|---|---|---|---|
| Home / Launcher dashboard | لوحة التحكم | `/` | `launcher` |
| Reports & Executive Dashboard | التقارير ولوحة التحكم التنفيذية | `/reports/` | `reports` |
| AI Assistant | المساعد الذكي | `/ai/` | `ai_assistant` |
| Petsy (floating chat) | بيتسي | `/petsy/` | `petsy` |

This chapter is a **screen-by-screen reference**, not a walkthrough. It
describes only what the code does today. Anything that is present but does not
work, or a control whose label promises more than it delivers, is in
[Known limits](#20-known-limits) rather than described as working.

Every section ends with a `Source:` line giving `file:line` so the next writer
can check the claim against the code.

> Source: `platform/app.py:210,218,221` (imports), `:238,246,249,271-272`
> (registration), `platform/blueprints/reports/__init__.py:1-4`,
> `platform/blueprints/ai_assistant/__init__.py:1-5`,
> `platform/blueprints/petsy/__init__.py:1-3`

---

## 1. Who can open what

Two independent gates apply, and **both must pass**:

1. **The module grant.** Checked inside `login_required`, so it applies to
   every route in a blueprint even when the route carries no role list.
   Blueprint name maps to a permission key: `reports` → `reports`,
   `ai_assistant` → **`ai`**, `petsy` → **`petshop`**, `launcher` → *(no key —
   ungoverned, always open to a signed-in user)*.
2. **The route's own role list**, where one is declared. **No route in
   `/reports/` or `/ai/` declares one.** They carry `@login_required` only, so
   the module grant is the whole gate.

`super_admin` bypasses both. A role that exists in the `roles` table with no
permissions row falls back to the built-in defaults; an unrecognised role is
denied everywhere.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-134` (`_permission_denied`), `:140-151` (`_BP_PERMISSION`),
> `:154-164` (`_permission_for`), `:167-194` (`role_required`)

### Default grants relevant to this chapter

| Role | `reports` | `ai` | `petshop` (Petsy) |
|---|---|---|---|
| super_admin | ✔ (bypass) | ✔ (bypass) | ✔ (bypass) |
| clinic_owner | ✔ | ✔ | ✔ |
| branch_manager | ✔ | ✘ | ✔ |
| doctor | ✔ | ✔ | ✘ |
| nurse | ✘ | ✘ | ✘ |
| reception | ✘ | ✘ | ✔ |
| pharmacist | ✘ | ✘ | ✘ |
| inventory_mgr | ✔ | ✘ | ✔ |
| finance | ✔ | ✘ | ✘ |
| hr | ✘ | ✘ | ✘ |
| groomer | ✘ | ✘ | ✘ |
| boarding_staff | ✘ | ✘ | ✘ |
| support_admin | ✘ | ✘ | ✘ |
| auditor | ✔ | ✘ | ✘ |

These are **defaults seeded into empty roles only**; an administrator can
change any of them on the Roles screen and this table stops being true.

The `petshop` column is informational: **`/petsy/chat` and `/petsy/embed` carry
no `login_required` decorator at all**, so the module gate never runs for them.
The Petsy chat bubble works for every signed-in user, and for anonymous
visitors too. See §17.

> Source: `platform/models/database.py:4302-4331` (`ALL_PERMISSIONS`),
> `:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`),
> `platform/blueprints/petsy/routes.py:755-756,830-831`

### What a denied user sees

A flash message *"You don't have permission to access this page."* and a
redirect to the launcher. A JSON `403` is returned instead **only** when the
path starts with `/api/` or the request's best `Accept` type is
`application/json` — which the in-page `fetch()` calls in these modules do not
send, so they receive the HTML redirect and fail at `r.json()`.

> Source: `platform/blueprints/auth/routes.py:131-134`

---

## 2. The doors in

| Door | Where | Goes to | Role-filtered? |
|---|---|---|---|
| Sidebar → BUSINESS / الأعمال → **Reports / التقارير** | every page | `/reports/dashboard` | **No** |
| Sidebar → PLATFORM / المنصة → **AI Assistant / المساعد الذكي** | every page | `/ai/` | **No** |
| Home → Quick Launch card **Reports / التقارير** (📊) | `/` | `/reports/` | **No** (hardcoded) |
| Home → Quick Launch card **AI Assistant / المساعد الذكي** (🤖) | `/` | `/ai/` | **No** (hardcoded) |
| Home → All Platform Modules → **Reports & Executive Dashboard** | `/` | `/reports/dashboard` | Yes |
| Home → All Platform Modules → **AI Assistant** | `/` | `/ai/` | Yes |
| Ctrl+K command palette → chip **📊 Reports / تقارير** | every page | `/reports` | No |
| Ctrl+K command palette → chip **🤖 AI Chat / دردشة AI** | every page | `/ai` | No |
| Petsy paw button (🐾) | every page, bottom-right | in-page iframe → `/petsy/embed` | No |

The sidebar links, the Quick Launch cards and the palette chips are **not
gated**. A nurse sees all of them, clicks, and is bounced back to the launcher
with the permission flash. Only the "All Platform Modules" grid at the bottom of
the home page is filtered by role.

> Source: `platform/templates/base.html:219-222` (sidebar Reports, inside an
> ungated group), `:259-262` (sidebar AI Assistant), `:853-860` (palette chips),
> `platform/templates/launcher.html:478-488` (hardcoded Quick Launch cards),
> `:593-600` (role-filtered module grid),
> `platform/blueprints/launcher/routes.py:574-579` (`_visible_modules`)

The module-card definitions used by the filtered grid are:

* **AI Assistant / المساعد الذكي** — 🤖, category *Intelligence & AI / الذكاء
  الاصطناعي*, badge *Live*, listed for `super_admin, clinic_owner,
  branch_manager, doctor, nurse, reception, finance, inventory_mgr`.
* **Reports & Executive Dashboard / التقارير ولوحة التحكم التنفيذية** — 📊,
  same category, badge *Live*, listed for `super_admin, clinic_owner,
  branch_manager, finance, auditor`.

The card `roles` list decides only whether the card is **drawn**. Entry is
decided by the module grant in §1, and the two disagree — see
[Known limits](#20-known-limits) §L7.

> Source: `platform/blueprints/launcher/routes.py:355-369` (AI card),
> `:370-384` (Reports card), `:560-571` (category labels)

---

## 3. Screen — Home dashboard (`/`)

**What it is for.** The first screen after sign-in: eight live counters, a
Quick Launch strip, today's appointment list, three status panels, and the full
module grid.

**How to reach it.** Sign in; or the Aleefy logo / `/` from anywhere. A guest is
redirected to the login page — there is no public landing page.

**Who can open it.** Every signed-in user. The `launcher` blueprint has no
permission key, so the module gate does not apply. A user whose role has no
recognised module list sees an empty grid and the flash *"Your account has no
role assigned, or its role is not recognised. Ask an administrator to set your
role."*

> Source: `platform/blueprints/launcher/routes.py:599-639`

### Header

* Greeting: `Good Morning, <full name> 👋` — English only, and always
  "Morning" (see §L5).
* Sub-line: *"Here's what's happening at the clinic today" / "إليك ما يجري في
  العيادة اليوم"*.
* Buttons: **+ New Appointment / موعد جديد** → `/appointments/new`;
  **+ Add Pet / إضافة حيوان** → `/crm/pets/new`.
* Top-bar (only when `LEGACY_APP_ENABLED` is on): **🩺 Open Exam Module /
  وحدة الفحص**, **🧾 Quick Invoice / فاتورة سريعة**. Both open the legacy
  Windows app and are hidden on hosted deployments.

> Source: `platform/templates/launcher.html:7-20,23,328-340`

### KPI cards

Each card is a link. Values are animated counters.

| Card | Arabic | Value shown | Links to |
|---|---|---|---|
| Today's Appointments | مواعيد اليوم | `COUNT(*)` of `appointments` with `appt_date` = today | `/appointments/` |
| Total Pets | إجمالي الحيوانات | `COUNT(*)` of `pets` (all time) | `/crm/owners` |
| Pet Owners | أصحاب الحيوانات | `COUNT(*)` of `owners` (all time) | `/crm/owners` |
| Visits Today | زيارات اليوم | `COUNT(*)` of `visits` with `visit_date` = today | `/visits/` |
| Revenue Today | إيرادات اليوم | `SUM(paid_amount)` of invoices **issued today** with status Paid or Partial, EGP | `/finance/invoices` |
| Unpaid Invoices | فواتير غير مدفوعة | `COUNT(*)` of invoices with status **Unpaid *or* Partial** | `/finance/invoices?status=Unpaid` |
| Reminders | التذكيرات | `COUNT(*)` of `reminders` with status `Pending` | `/whatsapp/control` |
| Outstanding | المستحق | `SUM(due_amount)` of invoices with status Unpaid or Partial, all time, EGP | `/finance/invoices?status=Unpaid` |

"Revenue Today" is an **accrual** figure: it counts money against the day the
invoice was *issued*, not the day the cash arrived. A payment taken today
against last week's invoice does not appear here.

> Source: `platform/templates/launcher.html:360-430`,
> `platform/blueprints/launcher/routes.py:614-628`,
> `platform/models/database.py:3995-4014` (`get_dashboard_stats`)

### Quick Launch strip

Eight fixed cards, in this order and with no role filtering: Appointments /
المواعيد, Pets & Owners / الحيوانات والملاك, Clinical Visits / الزيارات
السريرية, Finance / المالية, Inventory / المخزون, Pet Shop / متجر الحيوانات,
**AI Assistant / المساعد الذكي**, **Reports / التقارير**.

> Source: `platform/templates/launcher.html:440-490`

### Today's Schedule panel

When today's appointment count is zero it shows an empty state and a
**+ Schedule Appointment / جدولة موعد** button. Otherwise it draws a skeleton
loader, then fetches `/appointments/api/queue` and fills a table with columns
**Time / الوقت, Pet / الحيوان, Owner / المالك, Doctor / الطبيب, Status /
الحالة**, plus a **View full calendar / عرض التقويم الكامل** link.

> Source: `platform/templates/launcher.html:497-537,714-795`

### Right-hand panels

| Panel | What it actually shows |
|---|---|
| **🤖 AI Insights / رؤى الذكاء الاصطناعي** | Skeleton on load, then `POST /ai/insights`. The response key is `insights` (an array) but the page reads `d.insight`, so it always falls back to the literal *"AI ready for queries." / "الذكاء الاصطناعي جاهز للاستفسارات."* If the call fails or is denied, the panel becomes a link *"Ask AI for clinic insights →"*. Footer link **Open AI Assistant / فتح المساعد الذكي** → `/ai/`. |
| **📦 Stock Alerts / تنبيهات المخزون** | Reads `stats.low_stock`, which the route never sets, so it is **always** the green *"All stock levels are healthy" / "مستويات المخزون جيدة"*. Footer link **View inventory / عرض المخزون** → `/inventory/`. |
| **🖥️ System / النظام** | Two hardcoded strings — *"All systems operational"* with a green dot, and *"Last backup: today"*. Neither is derived from anything. Footer link **System monitor / مراقبة النظام** → `/system/monitor`. |

> Source: `platform/templates/launcher.html:542-575` (markup),
> `:696-712` (`v3LoadAIInsights`), `:798-813` (init),
> `platform/blueprints/ai_assistant/routes.py:511-581` (`insights`, returns
> `{"insights": [...], "generated_at": ...}`),
> `platform/blueprints/launcher/routes.py:619-628` (stats keys built)

### All Platform Modules

Grouped by category in a fixed order — Clinical, Operations, Inventory & Supply,
Commercial & Retail, Finance, Communication, Workspaces, Intelligence & AI,
Admin & HR, System — each with a count badge. A **Search modules… / ابحث عن
وحدة…** box filters the grid client-side by typed text. Only modules whose
`roles` list contains the user's role are drawn.

> Source: `platform/templates/launcher.html:583-600`,
> `platform/blueprints/launcher/routes.py:560-592`

---

## 4. Screen — Reports dashboard (`/reports/dashboard`)

**What it is for.** Twelve platform-wide KPI tiles, a 30-day revenue bar chart,
a top-services table, and four one-click CSV exports.

**How to reach it.** Sidebar → BUSINESS → Reports; Quick Launch **Reports**
card; module grid card; or `/reports/` which redirects here.

**Who can open it.** Holders of the `reports` grant (§1).

**Filters.** **None.** This screen takes no query parameters and has no date
picker. Every figure is fixed to its own window as listed below.

> Source: `platform/blueprints/reports/routes.py:14-17` (index redirect),
> `:20-32` (dashboard)

### Top-bar buttons

| Button | Goes to |
|---|---|
| 🩺 **Clinical / السريري** | `/reports/clinical` |
| 💰 **Financial / المالي** | `/reports/financial` |
| 📦 **Inventory / المخزون** | `/reports/inventory` |
| 👨‍⚕️ **Doctor Revenue / إيرادات الأطباء** | `/reports/doctor-revenue` |

There is **no button for the Report Builder** on this screen or anywhere else
in the product (§L1).

### Export bar

Label *"Export data: / تصدير البيانات:"* followed by four download links, each
hitting `/reports/export/csv?type=…` — see §9 for exactly what each contains.

📥 **Owners CSV / ملاك CSV** · 📥 **Pets CSV / حيوانات CSV** ·
📥 **Visits CSV / زيارات CSV** · 📥 **Invoices CSV / فواتير CSV**

### KPI tiles

| Tile | Arabic | Exactly what is counted |
|---|---|---|
| Total Owners | إجمالي الملاك | all rows in `owners` |
| Total Pets | إجمالي الحيوانات | all rows in `pets` |
| Visits Today | زيارات اليوم | `visits` where `visit_date` = today |
| Appointments Today | مواعيد اليوم | `appointments` where `appt_date` = today |
| Revenue Today (EGP) | إيرادات اليوم (جنيه) | `SUM(paid_amount)` of invoices issued today, status Paid or Partial |
| Revenue This Month | إيرادات هذا الشهر | same, from the 1st of the current month |
| Unpaid Invoices | فواتير غير مدفوعة | invoices with status Unpaid **or Partial** |
| Outstanding (EGP) | المستحق (جنيه) | `SUM(due_amount)` of invoices with status Unpaid or Partial, all time |
| Low Stock Items | أصناف منخفضة المخزون | active items where `SUM(batches.quantity) <= reorder_level` — **including items whose reorder level is 0** |
| Expiring in 30 Days | تنتهي صلاحيتها خلال 30 يومًا | batches with `quantity > 0` and `expiry_date <= today+30` — **already-expired batches are included** |
| Pending Reminders | تذكيرات معلقة | `reminders` with status `Pending` |
| VIP Owners | ملاك VIP | `owners` with `vip_flag = 1` |

> Source: `platform/templates/reports/dashboard.html:57-118`,
> `platform/models/database.py:3995-4014`

### 📊 Revenue — Last 30 Days / الإيرادات — آخر 30 يوم

An inline SVG bar chart. One bar per day that has at least one qualifying
invoice, from `today − 30` to today, ordered by date. Bar height is the day's
`SUM(paid_amount)` over invoices **issued** that day with status Paid or
Partial (accrual, not cash-at-till). Values under 10 000 print in full; above
that they print as `NNk`. Every fifth bar is labelled with `MM-DD`. A **Total**
line under the chart sums the plotted days. Empty state: *"No revenue data for
last 30 days" / "لا توجد بيانات إيرادات لآخر 30 يوم"*.

> Source: `platform/templates/reports/dashboard.html:122-160`,
> `platform/models/database.py:4016-4026` (`get_revenue_by_day`)

### 🏆 Top Services / أبرز الخدمات

Columns **# · Service / الخدمة · Count / العدد · Revenue / الإيرادات**. Rows are
`invoice_lines` with `line_type = 'service'`, grouped by the line's free-text
`description`, ordered by revenue, top 10. **All time** — there is no date
window on this query. Empty state: *"No service data yet" / "لا توجد بيانات
خدمات بعد"*.

> Source: `platform/templates/reports/dashboard.html:162-191`,
> `platform/models/database.py:4048-4055`

---

## 5. Screen — Clinical report (`/reports/clinical`)

**What it is for.** Three fixed 30-day clinical breakdowns.

**How to reach it.** Reports dashboard → **🩺 Clinical / السريري**, or the same
button on the Financial report.

**Who can open it.** `reports` grant.

**Filters.** **None.** The window is hardcoded to the last 30 days
(`today − 30`); there is no date picker and no query parameter.

**Top-bar buttons.** **← Dashboard / ← لوحة التحكم**, **💰 Financial / 💰 مالي**.

### Panels

| Panel | Rows | Bar length is relative to |
|---|---|---|
| **🩺 Visits by Type — Last 30 Days / الزيارات حسب النوع — آخر 30 يوماً** | `visits.visit_type`, counted, descending. Blank type renders as *Unknown*. | the largest count in the panel |
| **👨‍⚕️ Doctor Workload — Last 30 Days** (English only) | `visits.doctor_name`, counted, descending. Blank renders as *Unassigned*. | the largest count in the panel |
| **🔬 Top Diagnoses — Last 30 Days / 🔬 أكثر التشخيصات — آخر 30 يوماً** | `diagnoses.diagnosis` created in the window, counted, descending, top 10 | the first (largest) row |

The diagnoses table has columns **# · Diagnosis / التشخيص · Cases / الحالات ·
Frequency Bar / شريط التكرار**. The count is printed inside the bar only when
the bar is wider than 15 % of the track.

Empty states are per-panel: *"No visit data for last 30 days"*, *"No doctor
workload data for last 30 days"*, *"No diagnosis data for last 30 days"*.

> Source: `platform/blueprints/reports/routes.py:35-63`,
> `platform/templates/reports/clinical.html:37-119`

---

## 6. Screen — Financial report (`/reports/financial`)

**What it is for.** Six money summary tiles, a revenue chart, and a payment
methods panel, over a chosen date range.

**How to reach it.** Reports dashboard → **💰 Financial / المالي**, or the same
button on the Clinical and Inventory reports.

**Who can open it.** `reports` grant.

### Filter bar

| Control | Field | Required | Default | Effect |
|---|---|---|---|---|
| **From / من** | `date_from`, `<input type="date">` | no | today − 30 days | lower bound on `invoices.issue_date` and `expenses.expense_date` |
| **To / إلى** | `date_to`, `<input type="date">` | no | today | upper bound on the same |
| **🔍 Apply / 🔍 تطبيق** | submit (GET) | — | — | reloads with the range in the query string |
| **📊 Compare Periods / 📊 مقارنة الفترات** | link | — | — | opens `/reports/financial/compare` with the current range — see §7 |

The current range is echoed as `date_from → date_to` beside the buttons.
Both bounds are inclusive (`BETWEEN`).

**Top-bar buttons.** **← Dashboard / ← لوحة التحكم**, **🩺 Clinical / 🩺 سريري**,
**📥 Export CSV / 📥 تصدير CSV** (→ `/reports/export/csv?type=invoices`, the
full 500-row invoice export, **not** the filtered range).

### Summary tiles

| Tile (English only unless noted) | Exactly what it is |
|---|---|
| **Revenue Collected (EGP)** | `SUM(paid_amount)` of invoices **issued in the range** with status Paid or Partial. This is an accrual figure despite the word "Collected" (§L9). |
| **Total Invoiced (EGP) / إجمالي المفوتر (جنيه)** | `SUM(total)` of invoices issued in the range, excluding Cancelled |
| **Outstanding (EGP)** | `SUM(due_amount)` of **all** invoices with status Unpaid or Partial — **the date range is not applied** (§L10) |
| **Expenses (EGP)** | `SUM(amount)` of `expenses` with `expense_date` in the range |
| **Net Revenue (EGP)** | Revenue Collected − Expenses. Green when ≥ 0, red when negative. |
| **Invoices Issued** | count of invoices issued in the range, excluding Cancelled |

> Source: `platform/blueprints/reports/routes.py:66-93`,
> `platform/models/database.py:3940-3992` (`get_finance_summary`),
> `platform/templates/reports/financial.html:80-108`

### 📊 Revenue by Day — Last 30 Days

Same SVG chart as the dashboard, same source. **It always covers the last 30
days from today and ignores the From/To filter** (§L11). Empty state: *"No
revenue data in selected range"* — which is misleading, since the range is not
what was queried.

### 💳 Payment Methods

Always exactly **one** row, labelled **All Payments**, at **100 %**, showing the
count and the `SUM(paid_amount)` of invoices in the range with status Paid or
Partial. The panel is built that way in the route, not derived from the
`payments.method` column (§L12).

> Source: `platform/blueprints/reports/routes.py:73-84`,
> `platform/templates/reports/financial.html:149-174`

---

## 7. Screen — Period comparison (`/reports/financial/compare`)

**What it is for.** The same Financial screen with a previous period of equal
length computed alongside.

**How to reach it.** Financial report → **📊 Compare Periods / 📊 مقارنة
الفترات**. Not linked from anywhere else.

**Who can open it.** `reports` grant.

**Parameters.** `date_from` (default today − 29), `date_to` (default today).
The previous period is derived: it ends the day before `date_from` and has the
same length. Both windows are shown in a blue banner — *"📊 Comparison Mode /
📊 وضع المقارنة"*, `Current: … vs Previous: …` — with an **✕ Exit compare**
link back to the plain Financial screen.

**Delta badges.** Only two tiles carry one:

* **Revenue Collected** — percentage change in `revenue` vs the previous period.
* **Invoices Issued** — percentage change in the invoice count.

A badge is drawn only when the previous-period value is non-zero; a division
against zero yields no badge at all. Green ▲ for a rise, red ▼ for a fall,
rounded to one decimal.

A third figure, `paid_change` (change in Total Invoiced), is computed and
passed to the template but no tile displays it (§L13).

The revenue chart in compare mode covers `delta + 1` days back from **today**
when the selected span is under 90 days, otherwise 30 — again not the selected
window.

> Source: `platform/blueprints/reports/routes.py:270-329`,
> `platform/templates/reports/financial.html:57-108`

---

## 8. Screen — Inventory report (`/reports/inventory`)

**What it is for.** Stock value by category, a low-stock list, and a 90-day
expiry list.

**How to reach it.** Reports dashboard → **📦 Inventory / المخزون**.

**Who can open it.** `reports` grant. (Note this is the `reports` key, not
`inventory` — a role with inventory access but no reports grant cannot open
this screen.)

**Filters.** None.

**Top-bar buttons.** **← Dashboard / ← لوحة التحكم**, **💰 Financial / 💰 مالي**,
**📊 Export Excel / 📊 تصدير Excel** (→ `/reports/inventory/export/xlsx`, §8.1).

### 📊 Stock Value by Category

Columns **Category / الفئة · Items / الأصناف · Value (EGP)**. One row per row in
`item_categories`, ordered by value descending. `Items` counts active items in
the category; `Value` is `SUM(batches.quantity × items.cost_price)`. A category
with no items still appears, with zeros. A blank category name renders as
*Uncategorized*. A grey bar beside each value is scaled against the largest
value in the table.

### ⚠️ Low Stock Items (N)

Columns **Item / الصنف · Category / الفئة · Stock / المخزون · Reorder**. Active
items whose total batch quantity is at or below their reorder level, lowest
stock first, **capped at 50 rows**. Stock prints to one decimal with the item's
unit; Reorder prints as `≥ <level>`. The list scrolls inside the panel above
320 px. Empty state: ✅ *"All items are adequately stocked"*.

### ⏳ Expiry Alerts — Items Expiring within 90 Days (N)

Columns **Item / الصنف · Batch # · Qty / الكمية · Expiry Date / تاريخ الانتهاء ·
Urgency**. Every batch with `quantity > 0` and `expiry_date <= today+90`,
earliest first, **not capped**. Batches that already expired are included.
Urgency is banded off the same date:

| Band | Condition | Chip |
|---|---|---|
| Critical | `expiry_date <= today+30` | 🔴 Critical (<30d), red |
| Warning | `expiry_date <= today+60` | 🟡 Warning (<60d), amber |
| Notice | otherwise (≤ today+90) | 🔵 Notice (<90d), blue |

Empty state: ✅ *"No items expiring within the next 90 days"*.

> Source: `platform/blueprints/reports/routes.py:96-145`,
> `platform/templates/reports/inventory_report.html:38-154`

### 8.1 Action — Export Excel (`/reports/inventory/export/xlsx`)

Downloads `inventory_report_YYYY-MM-DD.xlsx`, sheet **Inventory**, one row per
**active** item (not just low-stock ones), ordered by category then name.

Columns: `Name · SKU · Category · Unit · Stock Qty · Reorder Level ·
Cost Price · Stock Value (EGP) · Status`, where Status is `LOW` when stock is at
or below the reorder level and `OK` otherwise.

The workbook carries a blue title row *"Inventory Report — YYYY-MM-DD"*, a
generated-at timestamp, a styled header row, banded data rows, auto column
widths (capped at 40 characters), and a green **TOTAL** row summing every
numeric column.

If `openpyxl` is not installed the download fails with the flash *"openpyxl is
not installed. Run: pip install openpyxl"* and returns to the inventory report.

> Source: `platform/blueprints/reports/routes.py:148-198`,
> `platform/models/excel_export.py:50-140`

---

## 9. Screen — Doctor revenue report (`/reports/doctor-revenue`)

**What it is for.** Invoiced, collected and pending money per doctor over a
date range, with a per-doctor service-type breakdown.

**How to reach it.** Reports dashboard → **👨‍⚕️ Doctor Revenue / إيرادات
الأطباء**.

**Who can open it.** `reports` grant.

**Top-bar button.** **← Reports / ← التقارير** → `/reports/dashboard`.

### Filter bar

| Control | Field | Required | Default |
|---|---|---|---|
| **From / من** | `date_from` (date) | no | the 1st of the current month |
| **To / إلى** | `date_to` (date) | no | today |
| **Apply / تطبيق** | submit (GET) | — | — |

The selected range is printed as the page sub-title. Rows come from invoices
whose `issue_date` falls in the range, excluding Cancelled, and excluding
invoices with a blank `doctor_name`.

### KPI strip

| Tile | Arabic | Value |
|---|---|---|
| Active Doctors | الأطباء النشطون | number of distinct doctors in the result |
| Total Invoiced (EGP) | إجمالي المفوتر (جنيه) | `SUM(total)` across all rows |
| Collected (EGP) | المحصّل (جنيه) | see the caution below |
| Pending (EGP) | المعلق (جنيه) | see the caution below |
| Collection Rate | معدل التحصيل | Collected ÷ Invoiced × 100, or `—` when Invoiced is 0 |

> **Caution — how Collected and Pending are counted.** *Collected* is the
> **full `total`** of every invoice whose status is exactly `Paid`. *Pending* is
> the **full `total`** of every invoice that is neither `Paid` nor `Cancelled`.
> A part-paid (`Partial`) invoice therefore contributes **nothing** to Collected
> and its **entire value** to Pending — neither column reflects `paid_amount`.
> This does not agree with the Financial report, which uses `paid_amount`.

### Table

Columns: **Doctor / الطبيب · Invoices / الفواتير · Invoiced (EGP) / المفوتر
(جنيه) · Collected / المحصّل · Pending / قيد الانتظار · Collection % / نسبة
التحصيل % · Service Breakdown / توزيع الخدمات**.

* Rows are ordered by Invoiced, descending.
* Pending shows `—` when zero.
* The Collection % bar is capped at 100 %.
* Service Breakdown shows at most the **top 3** `invoice_lines.line_type`
  groups for that doctor as chips `type: amount`; `—` when there are none.
* A bold **TOTAL / الإجمالي** row closes the table.

Below the table, a CSS bar chart **Revenue by Doctor / الإيرادات حسب الطبيب**
plots each doctor's Invoiced against the largest, with the doctor's share of the
grand total on the right.

Empty state: 📊 *"No invoice data found for the selected period." / "لا توجد
بيانات فواتير للفترة المحددة."* with *"Try a different date range." / "جرّب
نطاقاً زمنياً مختلفاً."*

**No commission is calculated or displayed anywhere on this screen**, despite
the route's own description (§L14).

> Source: `platform/blueprints/reports/routes.py:201-267`,
> `platform/templates/reports/doctor_revenue.html:35-171`

---

## 10. Action — CSV exports (`/reports/export/csv`)

**How to reach it.** The four buttons on the Reports dashboard, and the
**📥 Export CSV** button on the Financial report.

**Who can use it.** `reports` grant.

**Parameter.** `type` — one of `owners`, `pets`, `visits`, `invoices`. Default
`owners`.

Downloads `<type>_YYYY-MM-DD.csv`.

| `type` | Columns | Order | Row cap |
|---|---|---|---|
| `owners` | ID, Full Name, Phone, WhatsApp, Email, Address, VIP, Created At | name | none |
| `pets` | ID, Pet Name, Species, Breed, Sex, Owner | pet name | none |
| `visits` | ID, Date, Type, Pet, Owner, Doctor, Status | date descending | **500** |
| `invoices` | Invoice #, Date, Owner, Total, Paid, Due, Status | issue date descending | **500** |

No date filtering is available on any of them. An unrecognised `type` produces a
**completely empty file** — not even a header row (§L15).

> Source: `platform/blueprints/reports/routes.py:332-359`

---

## 11. Screen — Custom Report Builder (`/reports/builder`)

**What it is for.** Pick a data source, tick columns, set a date/status filter,
and run the result to screen, CSV or Excel. Configurations can be saved and
re-run.

**How to reach it.** **By typing the URL.** Nothing in the product links to it
(§L1).

**Who can open it.** `reports` grant.

On first use the route creates the `saved_reports` table if it is missing
(once per database, not per request).

> Source: `platform/blueprints/reports/builder_routes.py:159-196`

### The AI query bar (top of the page)

**AI Report Builder / مُنشئ التقارير بالذكاء الاصطناعي** — a dark panel with:

* A text box, placeholder *"e.g. unpaid invoices from last month · dogs treated
  for vomiting this week · inventory below reorder level" / "مثال: فواتير غير
  مدفوعة من الشهر الماضي · كلاب عولجت من القيء هذا الأسبوع · مخزون أقل من حد
  إعادة الطلب"*. Enter submits.
* Button **🤖 Build Report / 🤖 بناء التقرير**.

It posts the typed text to `POST /ai/nl-report`, which asks the model to return
`{source, date_from, date_to, status, suggestion}`. On success the page selects
the matching source radio, fills **Date From**, **Date To** and **Status
Filter**, and shows a green line with the model's `suggestion`. On any failure
it shows *"⚠️ AI unavailable. Please configure manually."*

**It does not choose columns.** Selecting a source resets the column list to
that source's first six columns, so the AI's effect is limited to the source
and the filters (§L19).

> Source: `platform/templates/reports/builder.html:24-89`,
> `platform/blueprints/ai_assistant/routes.py:687-723`

### 1. Data Source / مصدر البيانات

Radio cards. The first (**Invoices**) is pre-selected.

| Source | Label | Tables joined | Date column | Status values offered |
|---|---|---|---|---|
| `invoices` | Invoices 🧾 | invoices + owners + pets | `i.issue_date` | Unpaid, Paid, Partial, Cancelled |
| `appointments` | Appointments 📅 | appointments + owners + pets | `a.appt_date` | Scheduled, Confirmed, Completed, Cancelled, No Show |
| `visits` | Medical Visits 🏥 | visits + owners + pets | `v.visit_date` | Open, Completed, Cancelled |
| `payments` | Payments Received 💳 | payments + owners + invoices | `py.received_at` | none |
| `owners` | Owners / Clients 👤 | owners | `o.created_at` | none |
| `pets` | Patients (Pets) 🐾 | pets + owners | `p.created_at` | none |
| `expenses` | Expenses 💸 | expenses | `expense_date` | none |
| `inventory` | Inventory 📦 | items + item_categories + suppliers | `i.created_at` | none |

### 2. Columns / الأعمدة

A checkbox grid rebuilt whenever the source changes. **The first six columns of
the chosen source are pre-ticked.** Buttons **All / الكل** and **None / لا شيء**
tick or clear everything.

Available columns per source:

* **Invoices** — Invoice ID, Invoice #, Owner Name, Owner Phone, Pet Name,
  Species, Issue Date, Status, Subtotal, Discount, Total (EGP), Paid, Due,
  Doctor
* **Appointments** — ID, Date, Time, Owner Name, Phone, Pet Name, Species, Type,
  Doctor, Status, Notes
* **Medical Visits** — Visit ID, Visit Date, Owner, Phone, Pet, Species, Visit
  Type, Doctor, Status, Chief Complaint, Weight (kg), Temp (°C)
* **Payments Received** — Payment ID, Date, Owner, Phone, Invoice #, Amount
  (EGP), Method, Reference, Received By
* **Owners / Clients** — ID, Full Name, Phone, Email, Address, Preferred
  Contact, Joined Date, Loyalty Points
* **Patients (Pets)** — Pet ID, Pet Name, Species, Breed, Sex, Date of Birth,
  Weight (kg), Owner, Owner Phone, Registered
* **Expenses** — ID, Date, Category, Description, Amount (EGP), Vendor, Receipt
  Ref, Created By
* **Inventory** — ID, Product Name, Category, SKU, Unit, Reorder Level, Cost
  Price, Sell Price, Supplier

**Stock on hand is deliberately absent from the Inventory source.** It is a sum
over batches, and this builder emits a flat `SELECT` with no aggregation. Use
`/reports/inventory` or its Excel export for on-hand figures.

> Source: `platform/blueprints/reports/builder_routes.py:16-150`,
> `platform/templates/reports/builder.html:96-130,255-284`

### 3. Filters / عوامل التصفية

| Control | Field | Required | Default | Effect |
|---|---|---|---|---|
| **Date From / من تاريخ** | `date_from` (date) | no | empty | `>=` on the source's date column, compared as the first 10 characters of the value |
| **Date To / إلى تاريخ** | `date_to` (date) | no | empty | `<=` on the same |
| **Status Filter / تصفية الحالة** | `status_filter` (select) | no | *— All Statuses —* | exact match on the source's status column. **The whole field is hidden for sources with no status column.** |
| **Row Limit / حد الصفوف** | `limit` (select) | yes (has a default) | 500 | 100 / 250 / 500 / 1000 / 2000 (max). Values above 2000 are clamped server-side. |
| **Output Format / صيغة الإخراج** | `format` (select) | yes (has a default) | View in Browser | View in Browser / عرض في المتصفح · Download CSV / تحميل CSV · Download Excel (.xlsx) / تحميل Excel (.xlsx) |

Leaving a date box empty means that bound is not applied.

### 4. Run Report / تشغيل التقرير

**▶ Run Report / ▶ تشغيل التقرير** posts to `/reports/builder/run`.

Validation, in order:

1. No source, or **no columns ticked** → *"Please select a data source and at
   least one column." / (warning)* and you are returned to the builder.
2. Column names are checked against the source's own whitelist; anything else is
   dropped. If nothing survives → *"No valid columns selected."*
3. On a SQL error the flash is *"Query error: &lt;message&gt;"* and you are
   returned to the builder.

The note beside the button says *"Results open in a new page" / "تُفتح النتائج
في صفحة جديدة"* — they open in the **same** tab.

> Source: `platform/blueprints/reports/builder_routes.py:201-299`,
> `platform/templates/reports/builder.html:132-182`

### 💾 Save Report Config / حفظ إعداد التقرير

A name box (placeholder *"Report name (e.g. Monthly Invoices)" / "اسم التقرير
(مثال: فواتير شهرية)"*) and a **Save / حفظ** button. Saving with an empty name
raises a browser alert *"Please enter a report name."*; an empty name or source
reaching the server produces the flash *"Name and source are required."*

What is stored: the name, the source key, the ticked columns, both dates, the
status filter, the row limit, and the saving user's username. **The output
format is not stored.** Success flash: *Report "&lt;name&gt;" saved.*

> Source: `platform/blueprints/reports/builder_routes.py:304-330`,
> `platform/templates/reports/builder.html:184-191,301-321`

### 📁 Saved Reports / التقارير المحفوظة

Shown only when at least one saved report exists. Newest first, **capped at 50**.
Each row shows the name, a blue chip with the source key, the first 16
characters of the creation timestamp, and `by <username>` when one was
recorded.

| Control | Effect |
|---|---|
| **▶ Run / ▶ تشغيل** | `GET /reports/builder/saved/<id>` — replays the saved configuration and renders the HTML results page. **Always HTML**, never CSV or Excel. A missing id flashes *"Saved report not found."* |
| **🗑** | `POST /reports/builder/saved/<id>/delete`, guarded by a browser `confirm('Delete saved report?')`. Flash: *"Saved report deleted."* |

**Saved reports are not scoped to a user or a branch.** Everyone with the
`reports` grant sees every saved report and can delete any of them (§L17).

> Source: `platform/blueprints/reports/builder_routes.py:335-369`,
> `platform/templates/reports/builder.html:193-219`

---

## 12. Screen — Builder results (`POST /reports/builder/run`, HTML format)

**What it is for.** The rendered output of a builder run.

**Title.** `<Source label> Report`. **Sub-title.** `N row(s) returned`, plus the
date range and status when either was set.

**Top-bar button.** **← Builder / ← المُنشئ**.

### Export bar

* Label *"Export as: / تصدير كـ:"*
* **⬇ CSV** — re-posts the same source, columns, filters and limit with
  `format=csv`. Downloads `report_<source>_<YYYY-MM-DD>.csv`, header row = the
  column labels.
* **⬇ Excel** (green) — same with `format=xlsx`. Downloads
  `report_<source>_<YYYY-MM-DD>.xlsx`, sheet name **Data**, title
  `<Source label> Report`.
* On the right: the row count, or, **when the returned count equals the limit**,
  an amber warning *"⚠ Showing limit of N rows — increase limit or filter
  further"*.

Both export buttons **re-run the query**; they do not export the rows already on
screen.

### Table

One column per ticked column, headed with its label. Empty values render as an
empty cell. When there are no rows, a single centred cell reads *"No data found
for the selected filters." / "لا توجد بيانات للتصفية المحددة."*

A **🖨 Print / 🖨 طباعة** button at the bottom right calls the browser print
dialog; print CSS hides the sidebar, top bar, export bar and all buttons.

> Source: `platform/templates/reports/builder_results.html:1-93`,
> `platform/blueprints/reports/builder_routes.py:257-299`

---

## 13. Screen — AI Assistant chat (`/ai/`)

**What it is for.** A per-user chat with the configured language model, with a
role-specific system prompt and a role-specific set of quick prompts.

**How to reach it.** Sidebar → PLATFORM → **AI Assistant / المساعد الذكي**;
Quick Launch card; module grid card; Ctrl+K palette chip **🤖 AI Chat**.

**Who can open it.** The **`ai`** grant — by default `super_admin`,
`clinic_owner` and `doctor` only (§1, §L8).

**Page sub-title.** *"Powered by **freellmapi** — multi-model router (Gemini ·
GPT · Claude)"* (English only).

> Source: `platform/blueprints/ai_assistant/routes.py:367-381`,
> `platform/templates/ai_assistant/chat.html:1-20`

### Top-bar buttons

| Button | Effect |
|---|---|
| **📋 History / 📋 السجل** | `/ai/history` — §14 |
| **🗑 Clear / 🗑 مسح** | `POST /ai/clear`, guarded by `confirm('Clear all conversation history?')`. Deletes **every** stored exchange for the signed-in user, then flashes *"Conversation history cleared."* Shown only when AI is configured. |

### When AI is not configured

The whole chat panel is replaced by:

> 🤖 **AI Assistant Not Configured / المساعد الذكي غير مُعد**
> The `openai` Python package is required.
> Run in your terminal: `pip install openai`
> Make sure the freellmapi router is running at http://localhost:3001

The **Clear** button, the message list and the input box are all hidden, and the
page's JavaScript is not emitted at all.

"Configured" means: the `openai` package imports **and** either an API key is
set, or the base URL points at localhost/127.0.0.1 **and something is actually
listening on that port** (TCP probe, cached for 60 seconds). The on-screen text
only mentions the package, which is rarely the real cause (§L24).

> Source: `platform/blueprints/ai_assistant/routes.py:90-143`,
> `platform/templates/ai_assistant/chat.html:317-328,386-387`

### Quick Prompts / أسئلة سريعة (left sidebar)

Clicking a button fills the input box; it does **not** send. The set depends on
the signed-in user's role. All button labels and prompts are English only.

| Role | Buttons |
|---|---|
| `doctor`, `super_admin`, `clinic_owner` | 💊 Amoxicillin dosage (10 kg dog) · 🔍 Differentials: vomiting in dogs · ⚠️ Drug interaction: Metro + Phenobarb · 🔧 Pre-anesthetic protocol: cat spay · 🩺 PU/PD workup: senior dog · 🧪 Normal CBC ranges: dogs |
| `nurse` | 🌡️ Normal vitals: adult dog · 💉 SQ injection technique: cat · 😿 Pain assessment signs |
| `reception` | 📅 New appointment checklist · ℹ️ Explaining wellness exams · 🚨 Emergency triage questions |
| `inventory_mgr` | 📦 FEFO explained · 🌡️ Vaccine cold-chain storage · ♻️ Expired medication disposal |
| `pharmacist` | 💬 Patient counseling: Metronidazole · 🧪 Compounding considerations · 🔒 Controlled substance storage |
| `finance` | 🧾 Invoice compliance (Egypt) · 💳 Payment plan options |
| anything else (incl. `branch_manager`) | 🏥 Typical hospital services · 📅 Routine checkup frequency |

The entire sidebar is **hidden below 768 px viewport width**.

> Source: `platform/templates/ai_assistant/chat.html:223-227,238-312`

### The conversation area

* A permanent amber disclaimer bar: *"⚠️ **Disclaimer:** AI suggestions are for
  reference only. Always verify with clinical judgment and a licensed
  veterinarian."*
* On load, the **last 50 stored exchanges** for this user are drawn oldest
  first. Each stored row produces up to two bubbles — the question (👤) and the
  answer (🤖).
* Each bubble carries a timestamp (first 16 characters of `created_at`).
  Assistant bubbles also carry a `⚡ <model>` chip, unless the stored model is
  the literal `none`.
* Empty state: *"Start a conversation — ask a clinical question or use a quick
  prompt on the left."*
* A *"🤖 Thinking…"* indicator appears while a request is in flight.

### The input row

| Control | Behaviour |
|---|---|
| Message box | Placeholder *"Ask a clinical or operational question… (Enter to send, Shift+Enter for newline)"*. **Enter sends**, Shift+Enter inserts a newline. Auto-grows to a maximum of 130 px. |
| **Send ➤** | Sends. Disabled while a request is in flight. |

### What happens on send

`POST /ai/chat` with `{message}`. Server-side:

1. **Throttle check** — `is_rate_limited(ip)`; on a hit, HTTP 429 *"Too many
   requests. Please wait before sending another message."* In practice this
   check reads the failed-login table and never fires for chat traffic (§L23).
2. **Empty message** → HTTP 400 *"Empty message"*.
3. **Over 2000 characters** → HTTP 400 *"Message too long. Maximum 2000
   characters."*
4. The **last 20 stored exchanges** for this user are replayed as conversation
   context, oldest first, then the new message is appended.
5. A role-specific system prompt is prepended. All roles share a base
   instruction: professional, accurate, always disclaim that suggestions need a
   licensed vet's review, answer in the user's language (English or Arabic),
   **stay under 150 words**. Specialisations exist for `doctor`, `nurse`,
   `reception`, `inventory_mgr`, `pharmacist` and `finance`; any other role gets
   a generic one.
6. The exchange is written to `ai_conversations` **whether or not the call
   succeeded** — an error message is stored as the reply.

Failure text shown in the bubble:

* AI not configured → *"🤖 المساعد الذكي غير مُفعَّل على هذا النظام. تواصل مع
  مزوّد النظام لتفعيله. / AI is not enabled on this installation."*
* Configured but the call failed → *"🤖 المساعد الذكي غير متاح مؤقتاً. حاول بعد
  قليل. / The AI assistant is temporarily unavailable."*
* Browser-side network failure → *"⚠️ Network error. Please try again."*

The provider's own error text is never shown; it is logged instead.

> Source: `platform/blueprints/ai_assistant/routes.py:26-41` (limits),
> `:46-87` (prompts), `:156-202` (`call_ai`), `:325-362` (persistence and
> context window), `:427-474` (`chat`),
> `platform/templates/ai_assistant/chat.html:388-505`

---

## 14. Screen — AI conversation history (`/ai/history`)

**What it is for.** A read-only transcript of this user's stored AI exchanges,
grouped by day.

**How to reach it.** AI Assistant → **📋 History / 📋 السجل**. No other link.

**Who can open it.** `ai` grant.

**Content.** The user's most recent **200** stored exchanges, oldest first,
grouped under a `📅 YYYY-MM-DD` heading (a row with no timestamp lands under
*Unknown*). Each exchange renders a blue **👤 You** block and a grey **🤖 AI**
block, each with the first 16 characters of the timestamp.

**Controls.** One top-bar button, **💬 Back to Chat** (English only).

**Empty state.** 📭 *"No conversation history yet."* with a **Start a
conversation** button back to `/ai/`.

There is no search, no filter, no date picker and no delete on this screen —
clearing is only available from the chat screen, and it clears everything.

> Source: `platform/blueprints/ai_assistant/routes.py:477-494`,
> `platform/templates/ai_assistant/history.html:86-135`

---

## 15. Screen — AI command palette (Ctrl+K)

**What it is for.** Ask the assistant a question, or jump to a module, from any
page.

**How to open it.** `Ctrl+K` / `Cmd+K` anywhere; clicking the `Ctrl+K` key-cap
in the top bar; or pressing `Enter` or `/` while focused in the top-bar search
box. `Esc` or a click outside closes it.

**Who can use it.** The palette itself is on every page for every user. The
question box posts to `/ai/chat`, so a user without the `ai` grant gets a
redirect instead of an answer and sees the error line.

### Contents

| Element | Detail |
|---|---|
| Input | Placeholder *"Ask AI anything about your clinic… / اسأل المساعد الذكي عن عيادتك…"*. **Enter** submits. |
| **Quick Navigate / تنقل سريع** chips | 🧾 Invoices/فواتير → `/finance/invoices` · 📋 Estimates/عروض أسعار → `/finance/estimates` · 📅 Appointments/مواعيد → `/appointments` · 🐾 Patients/مرضى → `/crm/owners` · 🏥 Visits/زيارات → `/visits` · 📊 Reports/تقارير → `/reports` · 🎥 Telemedicine/عن بُعد → `/telemedicine` · 🤖 AI Chat/دردشة AI → `/ai` |
| Response area | *"Thinking… / جاري التفكير…"*, then the answer typed out character by character. On failure: *"⚠️ AI service unavailable. / خدمة الذكاء الاصطناعي غير متاحة."*; on an empty reply: *"No response. / لا يوجد رد."* |
| Footer | *"Powered by Aleefy AI / مدعوم من اليفي AI"* · *"Enter to ask · ESC to close / Enter للسؤال · ESC للإغلاق"* |

Questions asked here go through the same `/ai/chat` endpoint as the chat
screen, so **they are stored in the user's AI history** and count toward the
20-exchange context window.

> Source: `platform/templates/base.html:390-398` (search box),
> `:838-869` (palette markup), `:1241-1284` (`v3SearchKey`, `v3OpenCmdPalette`,
> `v3CmdKey`, `v3AskAI`)

---

## 16. Screen — Petsy floating assistant (🐾)

**What it is for.** A second, separate assistant — a chat bubble on every page.
Public visitors get general pet Q&A; signed-in staff additionally get live
clinic data pulled from the database and injected into the prompt.

**How to reach it.** The paw button, fixed bottom-right of every page **for any
signed-in user**. Click to open, click again to close. The button can be
dragged anywhere and snaps to the nearest side; a drag of more than 12 px is
treated as a move rather than a click. Open/closed state is remembered in
`localStorage` under `petsy-open`.

**Panel controls.** Title *"🐾 Petsy AI Assistant / 🐾 مساعد بيتسي الذكي"*,
**—** (minimise to a 52 px strip; the button becomes **□**), **×** (close). The
panel body is an iframe pointing at `/petsy/embed`, loaded lazily on first open.

> Source: `platform/templates/base.html:525,637-664,730-800`

### Inside the panel

* **Staff strip** (signed-in only): *"🔒 Staff Mode — Live clinic data enabled"*
  with a blinking dot.
* **Welcome card** — staff: *"Hi, I'm Petsy! Your internal AI assistant — ask me
  about today's schedule, patients, revenue, stock, and more."*; public:
  *"Hi there! I'm Petsy 🐱 Your friendly vet assistant…"*
* **Quick reply buttons** — clicking one sends it immediately and removes the
  strip.
  * Staff: 📅 Today's appointments · 🏥 Open visits now · 💰 Revenue today ·
    📦 Low stock alerts · 📊 Dashboard summary · 💊 Pending prescriptions
  * Public: 📅 Book appointment · 💉 Vaccination info · 🐶 Dog health tips ·
    🐱 Cat care tips · ⏰ Working hours · 💊 Medication advice
* **Input** — a growing textarea, placeholder *"Ask Petsy anything…"*, and a
  paper-plane send button.
* **Footer** — *"Powered by Petsy AI · &lt;clinic name&gt;"*.

All Petsy UI text is English only.

> Source: `platform/templates/petsy/embed.html:390-454`

### What staff mode actually looks up

The typed message is matched against 18 keyword patterns (English and Arabic).
Only matching topics are queried; if nothing matches, no data is fetched and the
model answers from general knowledge.

Recognised topics: appointments today · upcoming appointments · open visits ·
visits today · pending/unpaid invoices · revenue today · revenue this month ·
low stock · expiry alerts · pending lab results · vaccinations due · attendance
today · recent patients · dashboard summary · owner search · grooming today ·
current boarders · pending prescriptions.

**The only role scoping applied is a doctor filter**: a user whose role is
`doctor` sees only their own appointments and visits. Revenue, unpaid invoices,
stock, attendance and everything else are returned to **any** signed-in user,
including roles with no finance or inventory access (§L26).

> Source: `platform/blueprints/petsy/routes.py:166-204` (`_INTENTS`),
> `:219-290` (fetcher and the doctor filter), `:792-816` (staff branch)

### Limits and failure text

| Limit | Value |
|---|---|
| Message length | 1500 characters → HTTP 400 *"Message too long (max 1500 characters)."* |
| Conversation history sent | last 8 turns, further trimmed to 6000 characters total |
| Per-IP rate limit | 15 requests per 60 seconds → HTTP 429 *"Too many requests — please wait a moment."* |
| Anonymous daily cap | `PETSY_PUBLIC_DAILY_CAP`, default **500** calls/day across the whole installation. **Signed-in staff are exempt.** Over the cap: *"Petsy is resting for today 🐾 Please contact the clinic directly, or try again tomorrow."* |
| Reply length | `AI_MAX_TOKENS`, default **350** tokens |

AI off → *"🐾 بيتسي مش مفعّل على النظام ده. / Petsy is not enabled on this
installation."*; a failed call → *"🐾 Petsy is temporarily unavailable. Please
try again shortly."*; a safety block → *"🐾 My safety filters blocked that
response. Please try rephrasing!"*

`/petsy/chat` is **exempt from CSRF validation** by design, because the widget
is also served to anonymous visitors.

> Source: `platform/blueprints/petsy/routes.py:29-36,44-50,63-67,697-748,755-827`,
> `platform/app.py:349-357`

### `/petsy/widget.js`

Serves an embeddable widget script for external websites, cached one hour, with
`Access-Control-Allow-Origin: *`. No authentication.

> Source: `platform/blueprints/petsy/routes.py:846-856`

---

## 17. AI features embedded in other screens

These are AI endpoints under `/ai/` that have no screen of their own but are
driven from buttons elsewhere. They are listed here for completeness; the
screens that host them are documented in their own chapters.

| Endpoint | Driven from | Control | What it returns |
|---|---|---|---|
| `POST /ai/insights` | Home dashboard | (automatic on load) | Asks for 4 JSON insights over a live snapshot (appointments today, open visits, revenue today, unpaid invoices and total, items at/below reorder level, overdue vaccinations, new clients today). The panel does not display them (§L2). |
| `POST /ai/pet-summary/<pet_id>` | Pet detail | AI summary button → modal with **Print** | A referral-letter-style clinical summary built from the pet record, last 10 visits, last 10 diagnoses, last 8 prescription items and last 8 vaccinations. |
| `POST /ai/draft-message` | WhatsApp Send Center | **AI draft** → modal, language selector, **✅ Use This Message / ✅ استخدم هذه الرسالة**, **Cancel / إلغاء** | A 2–4 sentence WhatsApp message in English or Arabic, signed "Aleefy". |
| `POST /ai/nl-report` | Report Builder | **🤖 Build Report** | Report configuration JSON — §11. |
| `GET /ai/context/visit/<visit_id>` | Visit detail | (automatic when the AI panel opens) | The patient context block. Restricted to `super_admin, clinic_owner, branch_manager, doctor, nurse`; anyone else gets JSON 403 *"Access denied"*. A doctor with a branch assigned is additionally blocked from visits in another branch. |
| `POST /ai/analyze-photo` | Visit detail → AI panel | **📸 Analyze Photo / تحليل الصورة** (file picker, images only) | Vision analysis in four headed sections: Visual Findings, Differential Diagnoses (top 3), Recommended Next Steps, Urgency Level (Emergency/Urgent/Routine). Bounded only by the 16 MB request cap. |
| `POST /ai/discharge-instructions/<visit_id>` | Visit detail | **📋 Discharge Instructions / تعليمات الخروج** — shown **only** when the visit is still `Open` **and** at least one diagnosis exists | Bilingual instructions (English section + Arabic section), each under 200 words, in a modal with **🖨 Print / طباعة**, **📱 WhatsApp / واتساب** (opens wa.me with the first 1000 characters; alerts *"No phone number on file for this owner."* when there is no number) and **Close / إغلاق**. |
| `POST /ai/drug-interactions` | Visit detail (prescription form) and the one-page visit workflow | **💊 Check Interactions / فحص التداخلات الدوائية** | A severity banner. **Fails closed:** no drug named, no other medications on file, an unreachable model, or a reply with no severity all produce a grey *"Not checked"* banner, never a green one. Green appears only for an explicit `safe: true` with a known severity, and even then says *"Screened against known interactions only — species contraindications and dosing are not covered."* |
| `POST /ai/suggest-diagnosis` | One-page visit workflow | **AI differentials** button (the whole strip is hidden when AI is not configured) | Up to 4 differentials, each with likelihood (high/moderate/low), one clause of supporting evidence, and the single test that would confirm or exclude it, plus red flags. Each carries a **Use this / استخدم هذا** button that copies the name into the diagnosis box. Fails loudly and empty — a model that cannot be reached returns `ran: false` and says nothing was checked. |
| `GET /ai/health-alerts` | **nothing** | — | Broken and unreachable from the UI — §L21. |
| `GET /ai/outbreak-radar` | **nothing** | — | No screen calls it — §L22. |

> Source: `platform/blueprints/ai_assistant/routes.py:384-424,511-581,586-641,
> 646-682,687-723,728-786,791-855,860-923,928-984,989-1063,1066-1148`;
> callers: `platform/templates/launcher.html:700`,
> `platform/templates/crm/pet_detail.html:511-515`,
> `platform/templates/whatsapp/send_center.html:118-129`,
> `platform/templates/reports/builder.html:62`,
> `platform/templates/visits/visit_detail.html:40-46,711-787,997-1044,1131-1171`,
> `platform/templates/workflow/index.html:612-645,741,1278-1398`

---

## 18. Configuration (administrator reference)

All AI behaviour is driven by environment variables. There are no in-product
settings screens for any of them.

| Variable | Default | Effect |
|---|---|---|
| `AI_BASE_URL` | `http://localhost:3001/v1` | OpenAI-compatible endpoint |
| `AI_API_KEY` | *(empty)* | Provider key. Empty is allowed **only** when the base URL is localhost/127.0.0.1 and a TCP connection to that port succeeds. |
| `AI_MODEL` | `gemini-2.5-flash` | Model name sent with every request |
| `AI_MAX_TOKENS` | `700` (`350` for Petsy) | Reply length ceiling |
| `AI_TIMEOUT_SECONDS` | `45` | Per-request timeout. SDK retries are disabled, so this is the true ceiling. |
| `PETSY_PUBLIC_DAILY_CAP` | `500` | Anonymous Petsy calls per day, installation-wide |
| `PLATFORM_DEFAULT_LANG` | `en` | Interface language before a user record exists |
| `CLINIC_TIMEZONE` | `Africa/Cairo` | Session timezone; wrong values push after-midnight records out of "today" on every dashboard |

The chat message ceiling (2000 characters) and Petsy's (1500 characters,
6000-character history) are constants in the source, not configurable.

> Source: `platform/blueprints/ai_assistant/routes.py:26-41`,
> `platform/blueprints/petsy/routes.py:29-36,63-67`,
> `platform/models/database.py:51-117`, `platform/app.py:373-386`

---

## 19. Data written by these screens

| Table | Written by | Contents |
|---|---|---|
| `ai_conversations` | `/ai/chat` (chat screen and Ctrl+K palette) | one row per exchange: user id, role, prompt, response, model. Deleted per-user by **🗑 Clear**. |
| `saved_reports` | Report Builder → **Save** | name, source key, JSON configuration, creating username, timestamp. Created on first use of the builder. |
| `petsy_usage` | `/petsy/chat`, anonymous calls only | one row per anonymous call, for the daily cap. Created on first use. |
| `audit_log` | Launcher → module card click | `open_module` entries. Nothing in `/reports/` or `/ai/` writes an audit entry. |

The other AI endpoints (`insights`, `pet-summary`, `draft-message`,
`nl-report`, `analyze-photo`, `discharge-instructions`, `drug-interactions`,
`suggest-diagnosis`, `outbreak-radar`, `health-alerts`) **store nothing** — their
output exists only in the browser until the page is left.

> Source: `platform/blueprints/ai_assistant/routes.py:325-338,497-506`,
> `platform/blueprints/reports/builder_routes.py:159-176,321-327`,
> `platform/blueprints/petsy/routes.py:70-113`,
> `platform/blueprints/launcher/routes.py:663-670`

---

## 20. Known limits

Everything below is a real behaviour of the current code, verified in the
source, not a wish list.

### Navigation and access

**L1 — The Report Builder is unreachable from the interface.** No sidebar item,
no button, no card, no link on any template points at `/reports/builder`. The
only way in is to type the URL.
> `grep` over `platform/templates/` finds no `reports.builder` link;
> `platform/templates/reports/dashboard.html:7-12` (the topbar that would carry it)

**L7 — Reports and AI links are shown to users who cannot open them.** The
sidebar BUSINESS group (Reports) and PLATFORM group (AI Assistant), the two
hardcoded Quick Launch cards, and the Ctrl+K palette chips carry no role
condition. A nurse or receptionist clicking any of them is bounced back to the
launcher with a permission flash.
> `platform/templates/base.html:219-222,259-262,853-860`,
> `platform/templates/launcher.html:478-488`

**L8 — The AI Assistant card advertises the module to roles the default grants
deny.** The launcher card lists `branch_manager, nurse, reception, finance,
inventory_mgr` among its roles, but the default `ai` permission is held only by
`clinic_owner` and `doctor` (plus `super_admin`). Those five roles see the card
and are refused entry.
> `platform/blueprints/launcher/routes.py:364` vs
> `platform/models/database.py:4346-4379`

**L25 — `ai_enabled` is computed on every page render and used nowhere.** The
context processor probes whether AI is usable and injects `ai_enabled` into
every template, with an explicit comment about not offering the Petsy button
when AI is off. No template references it. The Petsy paw appears for every
signed-in user regardless, and answers *"Petsy is not enabled on this
installation."*
> `platform/app.py:379-386,453`; `grep ai_enabled platform/templates/` → no hits

### Home dashboard

**L2 — The AI Insights panel never shows an insight.** `/ai/insights` returns
`{"insights": [ … ]}`; the page reads `d.insight`. The card therefore always
displays the fallback string *"AI ready for queries."* (or, when the request is
denied or fails, a link to the AI Assistant).
> `platform/blueprints/ai_assistant/routes.py:581` vs
> `platform/templates/launcher.html:707`

**L3 — The Stock Alerts panel is permanently green.** It reads
`stats.low_stock`, a key the launcher route never puts in `stats` (the route
builds `owners, pets, bookings_today, pending_reminders, revenue_today,
visits_today, invoices_unpaid, outstanding`). It therefore always renders *"All
stock levels are healthy"*, even with items at zero.
> `platform/templates/launcher.html:556` vs
> `platform/blueprints/launcher/routes.py:619-628`

**L4 — The System panel is static text.** *"All systems operational"* with a
green dot, and *"Last backup: today"*, are literals. Nothing is checked.
> `platform/templates/launcher.html:566-575`

**L5 — The greeting is always "Good Morning", in English.** `hour` is set from
`now.hour if now is defined else 10`, and `now` is never injected into any
template context, so `hour` is permanently 10. The greeting line is also the
only untranslated string in the page header.
> `platform/templates/launcher.html:23,331`; no `now` in
> `platform/app.py:440-465`

**L6 — The top-bar search box does not search.** Typing in *"Search patients,
appointments… / ابحث عن مرضى، مواعيد…"* and pressing Enter (or `/`) opens the AI
command palette. There is no record search behind it.
> `platform/templates/base.html:394-397,1242-1246`

### Reports

**L9 — "Revenue Collected" on the Financial report is not the cash figure.** The
tile shows `revenue` — invoices *issued* in the range that have been paid.
`get_finance_summary()` also computes `collected` (money that actually arrived
in the range, from the payments ledger) and the template never renders it. A
payment taken in the range against an older invoice is invisible on this
screen.
> `platform/models/database.py:3945-3992` vs
> `platform/templates/reports/financial.html:81-85`

**L10 — "Outstanding" ignores the date range.** It sums `due_amount` across all
invoices with status Unpaid or Partial, regardless of the From/To filter. It is
identical no matter what range is chosen.
> `platform/models/database.py:3972-3973`

**L11 — The Financial revenue chart ignores the date range.** It always calls
`get_revenue_by_day(30)` — the last 30 days from today — while the title says
"Last 30 Days" and the empty state says "in selected range". In compare mode it
uses the span length as a days-back count from today, still not the selected
window.
> `platform/blueprints/reports/routes.py:72,301`

**L12 — Payment Methods is always a single row.** The panel is hardcoded to one
entry, "All Payments", at 100 %, computed from `invoices.paid_amount`. The
`payments` table has a `method` column (Cash/Card/Transfer/Insurance) and a
`channel` column, and neither is used.
> `platform/blueprints/reports/routes.py:73-84,304-312`;
> `platform/models/database.py:1698-1711`

**L13 — One of the three comparison deltas is never displayed.**
`financial_compare` computes `paid_change` (change in Total Invoiced) and passes
it to the template; no tile renders it. Only Revenue Collected and Invoices
Issued show a badge.
> `platform/blueprints/reports/routes.py:299,318-320` vs
> `platform/templates/reports/financial.html:84,106`

**L14 — The Doctor Revenue report shows no commission.** The route describes
itself as "Revenue and commission breakdown per doctor"; no commission rate,
amount or column exists anywhere in the query or the template. Separately, its
Collected/Pending split counts whole invoice totals by status and never
`paid_amount`, so a part-paid invoice contributes nothing to Collected and its
full value to Pending — a different definition from the Financial report.
> `platform/blueprints/reports/routes.py:204,216-218`

**L15 — An unknown CSV export type downloads an empty file.** The header row is
written inside each `if`/`elif` branch, so `?type=anything-else` returns a
zero-byte CSV rather than an error. The `visits` and `invoices` exports are also
silently capped at 500 rows with no warning on screen.
> `platform/blueprints/reports/routes.py:339-355`

**L16 — The Report Builder cannot aggregate.** It emits a flat
`SELECT <columns> FROM <tables> WHERE … LIMIT n`. There is no grouping, no
counting, no summing, no sorting control. This is why stock-on-hand is absent
from the Inventory source.
> `platform/blueprints/reports/builder_routes.py:119-149,228-241`

**L17 — Saved reports are shared and unprotected.** The list is
`SELECT * FROM saved_reports ORDER BY created_at DESC LIMIT 50` with no user,
role or branch filter, and the delete route has no ownership check. Anyone with
the `reports` grant can run or delete anyone else's saved report, and only the
50 newest are ever listed.
> `platform/blueprints/reports/builder_routes.py:186-194,360-369`

**L18 — Saving a report does not save its output format.** `format` is not part
of the stored configuration, and **▶ Run** on a saved report always renders the
HTML results page. A saved "monthly CSV" still has to be exported by hand.
> `platform/blueprints/reports/builder_routes.py:310-316,346-355`

**L19 — The AI report builder does not choose columns.** It returns only
`source`, `date_from`, `date_to` and `status`. Applying a source resets the
column grid to that source's first six columns, so the result is rarely the set
of fields the request described.
> `platform/blueprints/ai_assistant/routes.py:710-712`,
> `platform/templates/reports/builder.html:70-76,263`

**L20 — Builder Excel exports have no totals row.** Every value is converted to
a string before the workbook is built, so the workbook's numeric TOTAL row never
triggers. The inventory Excel export, which passes real numbers, does get one.
> `platform/blueprints/reports/builder_routes.py:273` vs
> `platform/blueprints/reports/routes.py:175-181`,
> `platform/models/excel_export.py:120-135`

**L27 — Several report screens have no date control at all.** The Reports
dashboard, the Clinical report (fixed at 30 days), the Inventory report, and
the Top Services table (all time) accept no parameters. Only Financial and
Doctor Revenue have From/To boxes.
> `platform/blueprints/reports/routes.py:20-32,35-63,96-145`,
> `platform/models/database.py:4048-4055`

### AI

**L21 — `/ai/health-alerts` is broken and unused.** Its low-stock query reads a
table called `inventory_items`, which does not exist anywhere in the schema or
the migrations (the stock catalogue is `items` + `batches`). The query raises,
a blanket `except Exception: pass` swallows it, and the unpaid-invoice block
that follows never runs — so at best the endpoint returns only overdue-vaccine
alerts. No screen calls it.
> `platform/blueprints/ai_assistant/routes.py:753-784`; `grep inventory_items`
> over `platform/models/` and `platform/db_migrations/` → no hits;
> `platform/blueprints/reports/builder_routes.py:120-122` (same fact noted)

**L22 — `/ai/outbreak-radar` has no user interface.** The endpoint scans the
last 7 days of diagnoses for clusters (2+ distinct pets = *watch*, 3+ = *alert*)
and asks the model for a public-health comment on alerts. Nothing in any
template fetches it.
> `platform/blueprints/ai_assistant/routes.py:928-984`; no caller in
> `platform/templates/`

**L23 — The AI chat rate limit cannot fire.** `/ai/chat` calls
`is_rate_limited(ip)`, which counts rows in `login_attempts` — a table only
`record_failed_login()` ever writes, and only on a failed sign-in. Nothing
records AI usage. A user with no recent failed logins is never throttled,
regardless of volume. The codebase has a general-purpose `throttle()` that does
count what it limits; this route does not use it.
> `platform/blueprints/ai_assistant/routes.py:434-438`,
> `platform/models/security.py:84-93,171-190,193-221`

**L24 — The "not configured" message names the wrong cause.** The panel tells
the reader to `pip install openai` and to check a router on
`http://localhost:3001`. In practice `ai_configured()` most often returns false
because `AI_API_KEY` is unset on a non-localhost base URL, or because nothing is
listening on the local port — neither of which the message mentions.
> `platform/blueprints/ai_assistant/routes.py:90-115` vs
> `platform/templates/ai_assistant/chat.html:317-328`

**L26 — Petsy staff mode is not role-scoped except for doctors.** The only role
condition in the live-data fetcher restricts a `doctor` to their own
appointments and visits. Revenue, unpaid invoices and outstanding balances,
stock levels, staff attendance and prescription queues are returned to any
signed-in user who asks — including roles that cannot open the Finance,
Inventory or HR modules. Petsy's own routes carry no `login_required`, so the
module grant never runs on them either.
> `platform/blueprints/petsy/routes.py:269-276,334,358` (the only role checks),
> `:755-756,830-831` (no decorator)

**L28 — Failed AI replies are stored as conversation history.** `/ai/chat`
writes the exchange whether the call succeeded or not, so *"The AI assistant is
temporarily unavailable"* appears as a saved answer in the history screen and is
replayed into the next request's 20-exchange context window.
> `platform/blueprints/ai_assistant/routes.py:463-467`

**L29 — Clearing history is all-or-nothing.** `/ai/clear` deletes every stored
exchange for the user. There is no per-conversation or per-day delete, and no
delete control on the History screen at all.
> `platform/blueprints/ai_assistant/routes.py:497-506`

**L30 — The Quick Prompts sidebar disappears on phones.** Below 768 px the
sidebar is `display: none`, so mobile users have no quick prompts and no
indication that any exist.
> `platform/templates/ai_assistant/chat.html:223-227`

### Bilingual coverage

**L31 — Large parts of these screens are English-only.** The `t()` helper is
applied inconsistently. Untranslated strings include: the Financial report's
sub-title and all six summary tile labels, its chart and payment-method
headings and empty states; the Clinical report's Doctor Workload panel; most of
the Inventory report (panel titles, the *Reorder*, *Batch #*, *Urgency* columns,
the urgency chips and both empty states); the Doctor Revenue page title; the
builder results page title, row count and truncation warning; the AI chat
disclaimer, placeholder, Send button, empty state and **every quick-prompt
label and prompt**; the AI History sub-title, Back-to-Chat button and empty
state; the home-page greeting; and the whole Petsy panel. On an Arabic-first,
RTL product these read as gaps rather than choices.
> `platform/templates/reports/financial.html:5,83,92,96,101,105,114,151,145,172`,
> `platform/templates/reports/clinical.html:63,79`,
> `platform/templates/reports/inventory_report.html:5,42,51,69,75,84,102,109,115,118,135-139,149`,
> `platform/templates/reports/doctor_revenue.html:3`,
> `platform/templates/reports/builder_results.html:2-4,46`,
> `platform/templates/ai_assistant/chat.html:6,239-311,333,340,372,376-377`,
> `platform/templates/ai_assistant/history.html:5,9,93,95`,
> `platform/templates/launcher.html:331`,
> `platform/templates/petsy/embed.html:396,407-411,420-432,442,454`

---

*Reference date: 2026-08-19. Verified against the working tree at
`D:/vet/platform`.*
