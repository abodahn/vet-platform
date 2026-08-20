# The Reference Manual — Contents

**الدليل المرجعي — الفهرس**

This manual is screen-shaped. For every screen it gives what the screen is for, how to
reach it, which roles can open it, every field and control with what it actually does,
every button and its effect, and what the list columns and filters mean. If you want a
task walked end to end instead, use the [Workflow Book](../workflows/README.md).

Every statement here was checked against the route function and the template that
renders it. Each screen ends with a `Source:` line carrying `file:line`. A control that
exists on screen but does nothing, and a database field with no screen behind it, is
listed in that chapter's **Known limits** rather than written up as a working feature.

The product is bilingual (English / العربية) and flips to RTL in Arabic. Where a label
is bilingual in the template, both texts are given as the template renders them.

---

## Chapters, in clinic order

| # | Chapter | File | URL prefixes | Screens covered |
|---|---------|------|--------------|-----------------|
| 1 | **Front Desk** | [`frontdesk.md`](frontdesk.md) | `/crm/` `/appointments/` `/workflow/` | Owners list and profile, new/edit owner, all pets, new/edit pet, pet record, medical-history PDF, day schedule, week calendar, new appointment, appointment detail, reschedule, Reception Workspace, Waiting Room TV, the New Visit walk-in page, and the module's JSON endpoints. **§ 3–20** |
| 2 | **Clinical** | [`clinical.md`](clinical.md) | `/visits/` `/clinical/` `/workflow/` | Medical Visits list, New Visit long form, visit detail with its five POST sub-forms, visit printout, visit→invoice shortcut, the Hatem Way one-screen exam (طريقة حاتم), the six-step New Visit wizard, vaccinations and certificates, lab queue/new/results, surgeries. Plus a table of what each Save writes. **§ 5.1–5.15, § 6** |
| 3 | **Services** | [`services.md`](services.md) | `/grooming/` `/boarding/` `/inpatient/` `/telemedicine/` `/clinical/lab` `/imaging/` | Six modules, each with its own dashboard, list, create and edit screens, status actions and Known limits: Grooming / التجميل (A1–A8), Boarding / الإيواء (B1–B8), Inpatient / التنويم (C1–C5), Telemedicine / الاستشارة عن بُعد (D1–D4), Laboratory / المختبر (E1–E4), Medical Imaging / التصوير الطبي (F1–F7) including the AI photo analyzer. **§ A–G** |
| 4 | **Pharmacy, Inventory & Procurement** | [`pharmacy.md`](pharmacy.md) | `/pharmacy/` `/inventory/` `/procurement/` | Pharmacy / الصيدلية: dispensing queue, prescription detail, what Dispense actually does, label, history, narcotics register (A1–A6). Inventory / المخزون: dashboard, items, new/edit item, item detail, receive stock, alerts, movements, transfer (B1–B8). Procurement / المشتريات: dashboard, suppliers, purchase orders, receiving (C1–C7). Plus how stock actually changes, FEFO, and reorder maths (D1–D3). |
| 5 | **Pet Shop** | [`petshop.md`](petshop.md) | `/petshop/` | Pet Shop & Orders / متجر الحيوانات والطلبات: dashboard, products, new/edit product, categories, Point of Sale, orders list, order detail, reports, background endpoints, and where a shop sale shows up in the rest of the system. **§ 4–13** |
| 6 | **Finance & Accounting** | [`finance.md`](finance.md) | `/finance/` `/accounting/` | Finance / الفواتير والمالية: dashboard, invoices list, new invoice, invoice detail, edit, print and PDF, estimates list/new/detail, client account (deposits and credit), expenses, financial reports. Accounting / المحاسبة: dashboard, Profit & Loss, Cash Flow, expenses, Daily Closing, Monthly Budget. Plus where finance data comes from and goes to. **§ 4–22** |
| 7 | **Insights** | [`insights.md`](insights.md) | `/` `/reports/` `/ai/` `/petsy/` | Home dashboard (لوحة التحكم), Reports dashboard, clinical / financial / inventory / doctor-revenue reports, period comparison, CSV exports, the Custom Report Builder and its results page, the AI Assistant chat and history, the Ctrl+K command palette, the Petsy floating assistant (بيتسي), AI features embedded in other screens, and the administrator configuration reference. **§ 3–19** |
| 8 | **System** | [`system.md`](system.md) | `/system/` `/settings/` `/auth/` `/hr/staff` | Clinic Settings, Roles & Permissions, staff accounts, two-step verification (staff view), My Profile, the shared desk, Backup & Restore, System Monitor, Diagnostics, Audit Log, Sync Dashboard, export all data, Branches / الفروع, multi-clinic, theme and language switches, sign-in/lockout/session rules, scheduled jobs. **§ 3–19** |
| 9 | **WhatsApp & Communications** | [`comms.md`](comms.md) | `/whatsapp/` `/notifications/` | WhatsApp / واتساب: Control Center, Send Center (text / image / file / video, AI draft, phone lookup), campaigns list / new / detail, templates list and form, Pending Reminders, Reminder Admin, the Reminder Scheduler page, Message Log and every log status (Sent / Failed / Not Configured / Not Sent / Pending), Settings, the 09:00 nightly reminder job, and the whole `/whatsapp/api/` surface. Notifications / الإشعارات: the inbox, mark read, the bell badge. **§ 4–20** |
| 10 | **People — HR, Attendance & Payroll** | [`people.md`](people.md) | `/hr/` `/attendance/` `/payroll/` | HR & Staff / الموارد البشرية: dashboard, staff list, new/edit staff, the staff profile and its eight write forms, password reset, shift assignment, roles list, performance reviews, warnings, certifications, HR notes, weekly roster, overtime log, HR attendance search (A1–A23). Attendance & Leave / الحضور والإجازات: dashboard, check in/out, records, record edit, leave requests and approval, shifts, leave types, balances, monthly report, public holidays, Excel export, the nightly auto-close (B1–B16). Payroll / الرواتب: dashboard, salaries, new/edit salary, approve and pay, bulk generate, salary grades, payslip PDF (C1–C13). Plus how the three feed each other. **§ 1–3, A, B, C, D** |
| 11 | **Doctor Workspace** | [`doctor.md`](doctor.md) | `/doctor/` | Doctor Workspace / مساحة الطبيب, Today's Queue, My Patients, My Schedule, My Statistics, the quick-visit redirect and the check-in POST — the module's only write. Plus how the `doctor_name` filter decides what "mine" means, and how this module relates to the Hatem Way exam screen. **§ 1–14** |
| 12 | **Clinical Decision Support** ⚕ | [`cds.md`](cds.md) | `/cds/` | The single Clinical Decision Support / دعم القرار السريري screen field by field, the exact rule set the engine holds, how a dose is calculated, how a drug name is matched, every error and edge case, the two JSON endpoints, and how a veterinarian edits the clinical data file. **Read § 0 first — the data ships marked DRAFT and the rule set is a shortlist, not a formulary. § 0–10** |
| 13 | **Data Migration & Import** | [`migration.md`](migration.md) | `/migration/` | The four wizard screens — Import Your Data, Match your columns, Preview, Import finished — plus the `rows_to_fix.csv` download, the command-line importer, exactly what an import writes to `owners`, `pets` and `visits`, and where imported data surfaces elsewhere. **§ 1–11** |

Every chapter opens with the same three sections before the screens start:
**Getting into the module** (the doors in), **Who can open what** (the permission map
per role), and **Conventions** (things true of every screen in that chapter). Read those
once per chapter; they are not repeated per screen.

Source: chapter files as linked; `platform/app.py:237-290` (blueprint registration);
URL prefixes from each `platform/blueprints/<module>/__init__.py`.

---

## A–Z index of screens

Each entry points at the chapter and its section number.

### A
- **Accounting Dashboard / لوحة المحاسبة** — Finance § 16
- **Admit patient / تنويم مريض** — Services C2
- **AI Assistant chat / المساعد الذكي** (`/ai/`) — Insights § 13
- **AI command palette (Ctrl+K)** — Insights § 15
- **AI conversation history** (`/ai/history`) — Insights § 14
- **AI features embedded in other screens** — Insights § 17
- **AI photo analyzer** — Services F5
- **All imaging studies** — Services F1
- **All pets** (`/crm/pets`) — Front Desk § 7
- **Appointment detail** (`/appointments/<id>`) — Front Desk § 15
- **Attendance Dashboard / الحضور والإجازات** (`/attendance/`) — People B1
- **Attendance Records** (`/attendance/records`) — People B3
- **Attendance Records — HR view** (`/hr/attendance`) — People A21
- **Attendance record, edit** (`/attendance/records/edit/<id>`) — People B4
- **Audit Log** (`/system/audit`) — System § 12
- **Auto-close of forgotten check-outs (00:20 job)** — People B16

### B
- **Backup & Restore** (`/system/backup`) — System § 9
- **Boarding dashboard** — Services B1
- **Boarding bookings list** — Services B2
- **Boarding booking, new / edit** — Services B3, B4
- **Boarding check in / check out** (no screen of its own) — Services B5
- **Boarding rooms / غرف الإيواء** — Services B7
- **Branches / الفروع** — System § 15
- **Builder results** (`POST /reports/builder/run`) — Insights § 12
- **Bulk Generate payroll** (`POST /payroll/bulk-generate`) — People C9

### C
- **Campaign detail** (`/whatsapp/campaigns/<id>`) — Comms § 8
- **Campaigns list** (`/whatsapp/campaigns`) — Comms § 6
- **Cash Flow** — Finance § 18
- **Categories** (`/petshop`) — Pet Shop § 7
- **Certifications & Training / الشهادات والتدريب** (`/hr/certifications`) — People A15
- **Check In / Out / الدخول / الخروج** (`/attendance/checkin`) — People B2
- **Check in, doctor's queue** (`POST /doctor/appointment/<id>/checkin`) — Doctor § 11
- **Client account (deposits & credit)** — Finance § 13
- **Clinic Settings** (`/system/settings`) — System § 3
- **Clinical Decision Support / دعم القرار السريري** ⚕ (`/cds/`) — CDS § 4
- **Clinical report** (`/reports/clinical`) — Insights § 5
- **Column mapping — Match your columns (Step 2)** (`POST /migration/upload`) — Data Migration § 5
- **Command-line importer** (`migrations/excel_import.py`) — Data Migration § 9
- **Controlled drugs — Narcotics register / سجل المخدرات** — Pharmacy A6
- **CSV exports** (`/reports/export/csv`) — Insights § 10
- **Custom Report Builder** (`/reports/builder`) — Insights § 11

### D
- **Daily Closing** — Finance § 20
- **Day schedule** (`/appointments/`, `/appointments/schedule`) — Front Desk § 12
- **Diagnostics** (`/system/diagnostics`) — System § 11
- **Dispensing History / سجل الصرف** — Pharmacy A5
- **Dispensing label / ملصق الصرف** — Pharmacy A4
- **Dispensing Queue / قائمة صرف الصيدلية** — Pharmacy A1
- **Doctor revenue report** (`/reports/doctor-revenue`) — Insights § 9
- **Doctor Workspace / مساحة الطبيب** (`/doctor/`) — Doctor § 5
- **`doctor_name` filter — how "mine" is decided** — Doctor § 3
- **Dose calculation, the exact formula** ⚕ — CDS § 6
- **Dose endpoint (JSON)** (`POST /cds/api/dose`) — CDS § 9
- **Drug data file, editing it** ⚕ (`blueprints/cds/drug_data.json`) — CDS § 10
- **Drug name matching (aliases, combinations, unknowns)** ⚕ — CDS § 7

### E
- **Edit owner** (`/crm/owners/<id>/edit`) — Front Desk § 6
- **Edit pet** (`/crm/pets/<id>/edit`) — Front Desk § 10
- **Edit Invoice** — Finance § 8
- **Edit Item** (inventory) — Pharmacy B3
- **Edit Supplier / تعديل المورد** — Pharmacy C4
- **Estimate detail** — Finance § 12
- **Estimates list** — Finance § 10
- **Expenses — Finance** § 14 · **Accounting** § 19
- **Export all data** (`/system/export/all`) — System § 14

### F
- **Failed import rows — `rows_to_fix.csv`** (`/migration/failed-rows.csv`) — Data Migration § 8
- **Finance Dashboard** — Finance § 4
- **Financial report** (`/reports/financial`) — Insights § 6
- **Financial Reports** (finance module) — Finance § 15

### G
- **Grooming dashboard** — Services A1
- **Grooming bookings list** — Services A2
- **Grooming booking, new / edit** — Services A3, A4
- **Grooming booking status change** (no screen of its own) — Services A5
- **Grooming services / خدمات التجميل** — Services A7

### H
- **Hatem Way one-screen exam / طريقة حاتم** (`/visits/exam`) — Clinical § 5.6
- **Holidays, Public / العطلات الرسمية** (`/attendance/holidays`) — People B13
- **Home dashboard** (`/`) — Insights § 3
- **HR Dashboard / لوحة الموارد البشرية** (`/hr/dashboard`) — People A1
- **HR notes on a staff profile** — People A17

### I
- **Imaging study detail** — Services F4
- **Imaging study, upload** — Services F3
- **Imaging, one pet's studies** — Services F2
- **Import finished (Step 4 result)** (`POST /migration/commit`) — Data Migration § 7
- **Import Your Data (Step 1)** (`/migration/`) — Data Migration § 4
- **Import, what it actually writes** — Data Migration § 10
- **Imported data, where it shows up elsewhere** — Data Migration § 11
- **Inpatient stay detail** — Services C3
- **Inpatient ward dashboard** — Services C1
- **Inventory Dashboard / لوحة تحكم المخزون** — Pharmacy B1
- **Inventory Items / أصناف المخزون** — Pharmacy B2
- **Inventory report** (`/reports/inventory`) — Insights § 8
- **Invoice detail** — Finance § 7
- **Invoice print & PDF** — Finance § 9
- **Invoices list** — Finance § 5
- **Item detail / تفاصيل الصنف** — Pharmacy B4

### J
- **JSON endpoints (front desk)** — Front Desk § 20
- **JSON endpoints (pet shop)** — Pet Shop § 12

### L
- **Lab request detail and results entry** — Services E3 · Clinical § 5.13
- **Lab request, new** — Services E2 · Clinical § 5.12
- **Lab requests list / queue** — Services E1 · Clinical § 5.11
- **Leave Balances / أرصدة الإجازات** (`/attendance/balances`) — People B11
- **Leave request detail** (`/attendance/leaves/<id>`) — People B7
- **Leave request, new** (`/attendance/leaves/new`) — People B6
- **Leave Requests / طلبات الإجازة** (`/attendance/leaves`) — People B5
- **Leave Types / أنواع الإجازات** (`/attendance/leave-types`) — People B10

### M
- **Message Log — WhatsApp** (`/whatsapp/log`) — Comms § 14
- **Medical history PDF** (`/crm/pets/<id>/history.pdf`) — Front Desk § 11
- **Medical Visits list** (`/visits/`) — Clinical § 5.1
- **Monthly Attendance Report** (`/attendance/report`) — People B12
- **Monthly Budget** — Finance § 21
- **Multi-clinic** — System § 16
- **My Patients** (`/doctor/patients`) — Doctor § 7
- **My Profile** (`/auth/profile`) — System § 7
- **My Schedule** (`/doctor/schedule`) — Doctor § 8
- **My Statistics** (`/doctor/stats`) — Doctor § 9

### N
- **New Campaign** (`/whatsapp/campaigns/new`) — Comms § 7
- **New appointment** (`/appointments/new`) — Front Desk § 14
- **New Estimate** — Finance § 11
- **New Invoice** — Finance § 6
- **New Item** (inventory) — Pharmacy B3
- **New owner** (`/crm/owners/new`) — Front Desk § 4
- **New pet** (`/crm/pets/new?owner_id=<id>`) — Front Desk § 8
- **New Performance Review** (`/hr/performance/new`) — People A10
- **New Product** — Pet Shop § 6
- **New Salary Record** (`/payroll/salaries/new`) — People C4
- **New Staff Member / موظف جديد** (`/hr/staff/new`) — People A3
- **New Purchase Order / أمر شراء جديد** — Pharmacy C6
- **New video consultation** — Services D2
- **New Visit (long form)** (`/visits/new`) — Clinical § 5.2
- **New Visit walk-in page** (`/workflow/`) — Front Desk § 19 · Clinical § 5.7
- **New / Edit WhatsApp template** (`/whatsapp/templates/new`) — Comms § 10
- **Notifications** (`/notifications/`) — Comms § 19

### O
- **Order detail** (pet shop) — Pet Shop § 10
- **Orders** (pet shop) — Pet Shop § 9
- **Owner profile** (`/crm/owners/<id>`) — Front Desk § 5
- **Owner-pets lookup** (inpatient) — Services C4
- **Overtime Log / سجل العمل الإضافي** (`/hr/overtime`) — People A19
- **Owners list** (`/crm/owners`) — Front Desk § 3

### P
- **Payroll Dashboard / لوحة الرواتب** (`/payroll/`) — People C1
- **Payslip PDF** (`/payroll/salaries/<id>/payslip`) — People C11
- **Performance review detail** (`/hr/performance/<id>`) — People A11
- **Performance Reviews / تقييمات الأداء** (`/hr/performance`) — People A9
- **Period comparison** (`/reports/financial/compare`) — Insights § 7
- **Pet record** (`/crm/pets/<id>`) — Front Desk § 9
- **Pet Shop Dashboard** — Pet Shop § 4
- **Petsy floating assistant / بيتسي** — Insights § 16
- **Point of Sale** — Pet Shop § 8
- **Preview an import (Step 3)** (`POST /migration/preview`) — Data Migration § 6
- **Procurement Dashboard / لوحة المشتريات** — Pharmacy C1
- **Products** — Pet Shop § 5
- **Profit & Loss report** — Finance § 17
- **Purchase Order detail / receiving** — Pharmacy C7
- **Purchase Orders list / أوامر الشراء** — Pharmacy C5

### Q
- **Queue, Today's (doctor)** (`/doctor/queue`) — Doctor § 6
- **Quick visit redirect** (`/doctor/visit/<id>/quick`) — Doctor § 10

### R
- **Reminder Admin** (`/whatsapp/reminder-admin`) — Comms § 12
- **Reminder Scheduler** (`/whatsapp/scheduler`) — Comms § 13
- **Reminders, Pending** (`/whatsapp/reminders`) — Comms § 11
- **Receive Stock / استلام مخزون** — Pharmacy B5
- **Reception Workspace** (`/appointments/reception`) — Front Desk § 17
- **Record surgery** (`/clinical/surgeries/new`) — Clinical § 5.15
- **Record vaccination** (`/clinical/vaccinations/new`) — Clinical § 5.9
- **Reports (pet shop)** — Pet Shop § 11
- **Reports dashboard** (`/reports/dashboard`) — Insights § 4
- **Reschedule** (`/appointments/<id>/edit`) — Front Desk § 16
- **Roles list, read-only** (`/hr/roles`) — People A8
- **Roles & Permissions** (`/system/roles`) — System § 4
- **Roster, weekly** (`/hr/roster`) — People A18
- **Rule set — exactly what the CDS engine knows** ⚕ — CDS § 5

### S
- **Screen endpoint (JSON)** (`POST /cds/api/screen`) — CDS § 9
- **Send Center — WhatsApp** (`/whatsapp/send-center`) — Comms § 5
- **Scheduled jobs** — System § 19
- **Serving image files** — Services F6
- **Session detail (telemedicine)** — Services D3
- **Shared desk** (`/auth/desk/add`) — System § 8
- **Sign-in, lockout and session rules** — System § 18
- **Salaries list** (`/payroll/salaries`) — People C2
- **Salary Grades / درجات الرواتب** (`/payroll/grades`) — People C10
- **Salary record / سجل الراتب** (`/payroll/salaries/<id>`) — People C5
- **Shifts / مناوبات العمل** (`/attendance/shifts`) — People B9
- **Staff accounts** (`/hr/staff`) — System § 5 · the whole record: People A2
- **Staff profile / بيانات الموظف** (`/hr/staff/<id>`) — People A4
- **Stock Alerts / تنبيهات المخزون** — Pharmacy B6
- **Stock Movements / حركات المخزون** — Pharmacy B7
- **Stock Transfer / تحويل مخزون** — Pharmacy B8
- **Supplier detail / بيانات المورد** — Pharmacy C3
- **Suppliers directory / الموردون** — Pharmacy C2
- **Surgeries list** (`/clinical/surgeries`) — Clinical § 5.14
- **Sync Dashboard** (`/system/sync`) — System § 13
- **System Monitor** (`/system/monitor`) — System § 10

### T
- **Templates — WhatsApp** (`/whatsapp/templates`) — Comms § 9
- **Telemedicine dashboard** — Services D1
- **Theme and language switches** (`/settings/*`) — System § 17
- **Two-Step Verification, staff view** (`/auth/2fa/admin`) — System § 6

### V
- **Vaccination certificate (PDF)** — Clinical § 5.10
- **Vaccinations** (`/clinical/vaccinations`) — Clinical § 5.8
- **Visit detail** (`/visits/<id>`) — Clinical § 5.3
- **Visit printout** (`/visits/<id>/print`) — Clinical § 5.4
- **Visit → invoice shortcut** (`/visits/<id>/invoice`) — Clinical § 5.5

### W
- **Waiting Room TV** (`/appointments/waiting-room`) — Front Desk § 18
- **WhatsApp Control Center** (`/whatsapp/control`) — Comms § 4
- **WhatsApp Settings** (`/whatsapp/settings`) — Comms § 16
- **Week calendar** (`/appointments/calendar`) — Front Desk § 13
- **What each Save writes (clinical)** — Clinical § 6
- **Where a Pet Shop sale shows up elsewhere** — Pet Shop § 13
- **Warnings / disciplinary record** — People A14
- **Weekly Roster / جدول المناوبات الأسبوعي** (`/hr/roster`) — People A18
- **Where finance data comes from and goes to** — Finance § 22
- **Where HR, attendance and payroll feed each other** — People Part D

---

## Known limits of this manual

These are limits of the **documentation**. Product limits are in each chapter's own
*Known limits* section.

1. *(Cleared.)* This entry said there was no People / HR chapter and that
   `docs/manual/people.md` did not exist. It does — chapter 10 above. Note the one
   overlap it leaves: the staff-account screens at `/hr/staff` are written up **twice**,
   in **System § 5** (where user logins are created) and in **People A2**, from two
   different angles.
   Source: `docs/manual/people.md`; `docs/manual/system.md:486`.

2. **Two registered modules have no chapter in either book** — Service catalogue
   (`/catalog/`) and the REST APIs (`/api/v1/`, `/api/public/`). WhatsApp (`/whatsapp/`)
   and Notifications (`/notifications/`) are covered by **Comms** (`comms.md`); the
   Doctor portal (`/doctor/`), Clinical decision support (`/cds/`) and Data migration
   (`/migration/`) now have chapters 11, 12 and 13. Pharmacy A2 and System § 1 still
   carry the older pointers to CDS and migration; the chapters supersede them.
   Source: `platform/app.py:237-290`; `platform/blueprints/catalog/routes.py`,
   `api_v1/`, `public_api/`.

3. **Front Desk has two broken internal links.** Its intro and § 2 both link to
   `#12-known-limits`, but Known limits is § 21, so the anchor is `#21-known-limits`.
   Both links land nowhere.
   Source: `docs/manual/frontdesk.md:12`, `docs/manual/frontdesk.md:103`,
   `docs/manual/frontdesk.md:1315`.

4. **Section numbering is not uniform across chapters.** Front Desk, Finance, Insights,
   Pet Shop, System, Doctor Workspace, Clinical Decision Support and Data Migration
   number screens `§ N` from the chapter root; Clinical nests every screen under `§ 5`
   as `5.1`–`5.15`; Services uses a letter per module with numbered screens (`A1`, `B3`,
   `F5`); Pharmacy uses `A1`–`A6` / `B1`–`B8` / `C1`–`C7` / `D1`–`D3`. The index above
   uses each chapter's own scheme.

5. **Nothing here was exercised in a browser.** Every chapter states this. Claims are
   read from route functions and templates. Anything that depends on runtime data, a
   background job or a device (camera, printer, WhatsApp session) is described from the
   code path only.

6. **Clinical Decision Support (chapter 12) documents a DRAFT clinical data file.**
   `drug_data.json` ships stamped `DRAFT — NOT YET REVIEWED BY A LICENSED VETERINARIAN`.
   The chapter records what the engine does and where its rule set is silent; it is not
   an endorsement of the clinical content, and absence of a warning in that module is
   never a statement of safety.
   Source: `platform/blueprints/cds/drug_data.json` → `review_status`, `_KNOWN_GAPS`.
