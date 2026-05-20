# Gap Analysis & Missing Features
## Premium Animal Hospital — Veterinary ERP Platform

| Field | Value |
|-------|-------|
| **Prepared by** | Platform AI Architect |
| **Reviewed with** | Dr. Hatem El Khateeb |
| **Version** | 1.0 |
| **Date** | May 2026 |
| **Purpose** | Identify what is missing, why it matters, and what to build next |

---

## Priority Legend

| Symbol | Priority | Meaning |
|--------|----------|---------|
| 🔴 | Critical | Platform is functionally incomplete without this |
| 🟡 | High | Significantly reduces platform value without this |
| 🟠 | Medium | Reduces operational efficiency |
| 🔵 | Nice to Have | Competitive differentiator, not a blocker |

---

## Summary Table

| Priority | Count | Top Items |
|----------|-------|-----------|
| 🔴 Critical | 5 | Prescription loop, notifications, automated reminders, file uploads, structured EMR |
| 🟡 High | 7 | Payroll, service catalog, client portal, reporting depth, security hardening, backup, 2FA |
| 🟠 Medium | 6 | Roster planning, AP ledger, stock write-off, commissions, vitals charts, branch_id |
| 🔵 Nice to Have | 5 | Telemedicine, insurance, mobile app, loyalty, calendar sync |

---

## 🔴 CRITICAL GAPS

### GAP-001 — No Closed Prescription → Dispensing → Stock Loop

**What exists today:**
Doctors can write prescriptions in the visit module. Inventory items exist. But there is no connection between the two.

**What is missing:**
- Doctor writes prescription → pharmacist sees a dispensing queue
- Pharmacist reviews → selects specific batch → dispenses quantity
- Dispensing triggers FEFO stock deduction automatically
- Dispensing label printed (pet name, owner, drug, dose, frequency, expiry)
- Controlled drug register entry created automatically

**Why it matters:**
Without this loop, stock is deducted manually (or not at all), prescriptions have no dispensing audit trail, and there is no compliance record for controlled drugs. This is both a business risk and a regulatory risk.

**Effort estimate:** 5–7 days
**Recommended for:** Phase 8 completion

---

### GAP-002 — No In-App Notification System

**What exists today:**
Flash messages confirm actions. There is no persistent notification center.

**What is missing:**
- Bell icon in the topbar with unread count badge
- Notification types:
  - Leave request submitted → notify manager
  - Leave request approved/rejected → notify staff member
  - PO received → notify finance
  - Lab result ready → notify requesting doctor
  - Low stock alert → notify inventory manager
  - Appointment check-in → notify doctor
- Mark as read / mark all as read
- Notification history log

**Why it matters:**
Currently a manager must actively check the attendance dashboard to discover a pending leave request. A doctor does not know when a lab result is ready. These workflows rely on verbal communication, which is exactly what the platform is supposed to replace.

**Effort estimate:** 3–4 days (database table + topbar widget + per-module trigger points)
**Recommended for:** Phase 8 completion

---

### GAP-003 — No Automated WhatsApp Reminder Engine

**What exists today:**
WhatsApp templates can be sent manually to any owner. Message log is maintained.

**What is missing:**
- A scheduled job (cron or background worker) that runs daily and:
  - Finds all appointments scheduled for the next 24 hours
  - Sends the appointment reminder template to each owner automatically
  - Finds all vaccinations due within 7 days
  - Sends vaccine due reminder to owners
  - Finds all invoices overdue by 7+ days
  - Sends payment reminder
- Configuration panel: enable/disable each reminder type, set lead time
- Per-message delivery status update

**Why it matters:**
This is the single highest-ROI feature missing from the platform. Reminder automation directly reduces no-shows, increases vaccination compliance, and accelerates payment collection. It is the primary reason clinics implement communication tools.

**Effort estimate:** 3–4 days (APScheduler or Windows Task Scheduler + trigger logic per reminder type)
**Recommended for:** Immediate — first item in Phase 9

---

### GAP-004 — No File / Document / Image Storage

**What exists today:**
The clinic logo can be stored as base64 in the settings table. Nothing else.

**What is missing:**
- File upload and retrieval system for:
  - Pet photos (stored on CRM pet profile)
  - X-ray and ultrasound images (attached to visit or lab record)
  - External lab PDF reports (attached to lab request)
  - Staff documents: contract, national ID, certificates (attached to HR profile)
  - Supplier documents: quotes, delivery notes (attached to PO)
  - Invoice PDF storage (auto-generated and stored)
- Storage: local filesystem (`/uploads/`) with DB path reference
- Access control: files served only to authenticated users with correct role

**Why it matters:**
Veterinary medicine is inherently visual. X-rays, wound photos, and pre/post-surgery images are clinical data. Without file storage, the platform cannot replace paper files and physical folders. HR and procurement are also incomplete without document attachment.

**Effort estimate:** 4–5 days (upload endpoint + file serving route + attachment UI components per module)
**Recommended for:** Phase 9

---

### GAP-005 — No Structured Clinical Note Format (SOAP)

**What exists today:**
Visit records have free-text fields: chief complaint, examination findings, diagnosis, treatment plan.

**What is missing:**
- SOAP note structure enforced in visit form:
  - **S — Subjective:** owner-reported symptoms and history
  - **O — Objective:** physical exam findings (temperature, heart rate, weight, observations)
  - **A — Assessment:** differential diagnosis with primary and secondary diagnoses
  - **P — Plan:** treatment, prescriptions, follow-up, referrals
- Vital signs structured entry: temperature, heart rate, respiratory rate, weight, body condition score
- Problem list: chronic conditions flagged on the pet record and visible on every future visit
- ICD/VeNom diagnostic code lookup (or custom code catalog)
- Visit templates by species and visit type (wellness, emergency, post-op)

**Why it matters:**
The current free-text approach works for record-keeping but does not enable clinical analytics (what are the most common diagnoses this month?), AI-assisted diagnosis support, or meaningful medical timeline views. SOAP is the international standard for clinical documentation.

**Effort estimate:** 6–8 days
**Recommended for:** Phase 9

---

## 🟡 HIGH PRIORITY GAPS

### GAP-006 — No Payroll Module

**What exists today:**
Attendance records show hours worked per day. HR profiles have base salary and commission rate fields. Leave balances track approved leave days.

**What is missing:**
- Monthly payroll run process:
  - Select month → calculate for all active staff
  - Base salary proration based on attendance (absent days deducted)
  - Overtime calculation (hours worked beyond shift hours)
  - Commission calculation from visit/invoice revenue
  - Deductions: unpaid leave, advances
  - Bonuses: performance, holiday
- Payslip generation (PDF) per staff member
- Payroll run history and approval by manager
- Payroll expense auto-posted to finance module
- Advance salary tracking (deducted from next payroll)

**Why it matters:**
Attendance is tracked but the output (salary calculation) does not exist. The HR module is half-built. Staff payroll is calculated manually in spreadsheets, defeating the purpose of the attendance system.

**Effort estimate:** 8–10 days
**Recommended for:** Phase 9

---

### GAP-007 — No Service / Price Catalog

**What exists today:**
Invoice line items are typed free-text. There is no standard service list with codes and prices.

**What is missing:**
- Service catalog: name, code, category, standard price, tax applicable, active flag
- Catalog loaded as a dropdown when creating invoice line items
- Price auto-fills from catalog — receptionist cannot accidentally misquote
- Service categories: consultation, vaccination, surgery, lab, grooming, boarding, other
- Revenue-by-service reporting (impossible without a catalog)
- Doctor-specific or branch-specific price overrides
- Service catalog linked to appointment types

**Why it matters:**
Without a service catalog, every invoice is an exercise in memorizing prices. Price consistency across staff is impossible. Revenue-by-service reporting (one of the most important management metrics) cannot exist.

**Effort estimate:** 3–4 days
**Recommended for:** Phase 8 completion

---

### GAP-008 — No Client-Facing Portal

**What exists today:**
Owners interact with the clinic only through phone calls and in-person visits.

**What is missing:**
- Read-only web portal for pet owners accessible via a link sent via WhatsApp
- Owner can view:
  - Their pets' upcoming appointments
  - Vaccination schedule and due dates
  - Last visit summary and discharge instructions
  - Outstanding invoices and payment history
- Online appointment request (pending staff confirmation)
- No write access to medical records

**Why it matters:**
Premium clinics are expected to provide client transparency. Owners who can track their pet's health digitally are more compliant with vaccination schedules, more likely to keep appointments, and more loyal to the practice.

**Effort estimate:** 10–12 days (separate blueprint with token-based owner auth)
**Recommended for:** Phase 9

---

### GAP-009 — Reporting is Shallow

**What exists today:**
A reports dashboard exists with some KPI cards.

**What is missing:**
- Interactive date-range comparison: this month vs last month vs same period last year
- Visual charts: bar charts for revenue trend, pie charts for service mix, line charts for appointment volume
- Drill-down: click on a KPI to see the underlying records
- Scheduled reports: email a summary to the clinic owner every Monday at 8am
- Export to Excel and PDF
- Doctor performance leaderboard
- Client lifetime value ranking
- Inventory turnover rate
- Leave utilization report per department

**Why it matters:**
The current reports are static snapshots. Management decisions require trend analysis, comparisons, and exportable data for external stakeholders (accountants, investors, insurance). Without proper reporting, the platform cannot support strategic decisions.

**Effort estimate:** 10–14 days
**Recommended for:** Phase 9

---

### GAP-010 — Security Hardening Not Complete

**What exists today:**
SHA-256 password hashing. Session-based auth. Role guards on routes.

**What is missing:**
- **Password hashing:** SHA-256 is not a password hashing algorithm. Must replace with bcrypt or argon2 (designed to be slow against brute force)
- **Login rate limiting:** No protection against brute-force attacks (100 wrong passwords allowed with no lockout)
- **Session timeout:** No automatic logout after inactivity period
- **Two-factor authentication (2FA):** No second factor for admin or doctor accounts
- **HTTPS enforcement:** No TLS certificate configured — data transmitted in plaintext on the network
- **IP whitelisting:** No option to restrict admin access to office IP only
- **CSRF tokens:** Need verification that all forms have CSRF protection

**Why it matters:**
This is a medical system holding patient data, owner personal information, and financial records. In Egypt and internationally, medical data systems are subject to data protection obligations. A breach would be legally and reputationally catastrophic.

**Effort estimate:** 3–5 days for password migration + rate limiting + session timeout + HTTPS
**Recommended for:** Before any production use with real patient data

---

### GAP-011 — No Automated Database Backup

**What exists today:**
The SQLite database file exists at a configured path. No backup mechanism.

**What is missing:**
- Daily automated copy of the SQLite database file to a backup location
- Timestamped backup files: `platform_backup_2026-05-17.db`
- 30-day rolling window (delete backups older than 30 days)
- Backup to a second local drive AND optionally to cloud (Google Drive, Dropbox, S3)
- Backup status visible in System Monitor
- One-click restore from backup in System Monitor (with confirmation)
- Backup integrity check (verify backup file is not corrupted)

**Why it matters:**
If the server hard drive fails today, all patient records, financial data, and operational history are permanently lost. This is a single point of failure with catastrophic consequences. A backup script takes one afternoon to implement.

**Effort estimate:** 1–2 days
**Recommended for:** Immediate — do this before anything else in production

---

### GAP-012 — No 2FA for Administrator Accounts

**What exists today:**
Username + password only for all roles including super_admin.

**What is missing:**
- TOTP (Time-based One-Time Password) 2FA for `super_admin` and `clinic_owner` roles
- QR code enrollment via Google Authenticator / Authy
- Recovery codes for lost authenticator
- Optional 2FA for all roles (configurable per role in settings)
- Trusted device option (skip 2FA for 30 days on same browser)

**Why it matters:**
Admin accounts have access to all financial records, all patient data, and all staff information. A compromised admin password with no second factor means full data exposure.

**Effort estimate:** 2–3 days (pyotp library)
**Recommended for:** Phase 9 with security hardening

---

## 🟠 MEDIUM PRIORITY GAPS

### GAP-013 — No Roster / Schedule Planning

**What exists today:**
Shifts are defined (Morning, Afternoon, Night). Attendance records who showed up. But there is no roster — no advance planning of who works which days.

**What is missing:**
- Weekly roster view: a grid of staff × days with shift assignments
- Manager creates the roster: drag-and-drop or dropdown assignment
- Staff can view their upcoming schedule
- Roster exported as PDF for printing
- Roster published status (draft vs published — staff can only see published)
- Conflict detection: same staff in two shifts same day
- Roster linked to attendance expected status (absent = did not show for assigned shift)

**Effort estimate:** 5–6 days

---

### GAP-014 — No Accounts Payable Ledger

**What exists today:**
Purchase orders track what was ordered and received. Expenses record cash outflows. But there is no AP tracking.

**What is missing:**
- Supplier invoice recording (separate from PO — the supplier's invoice to the clinic)
- Payment terms tracking: due date per supplier invoice
- Partial payment to suppliers
- Supplier balance ageing: 0–30, 31–60, 61–90, 90+ days overdue
- Payment scheduling
- Supplier account statement

**Effort estimate:** 4–5 days

---

### GAP-015 — No Formal Stock Write-Off / Adjustment Workflow

**What exists today:**
Stock adjustments can be made directly in inventory. There is a movement record but no approval workflow.

**What is missing:**
- Formal adjustment request: quantity, reason (damaged, expired, lost, stolen, count correction)
- Manager approval required for adjustments above a configurable threshold
- Approved adjustment triggers stock movement with reason code
- Write-off report for accounting (expense posting for written-off stock value)
- Expiry-triggered automatic write-off suggestion for expired batches

**Effort estimate:** 3–4 days

---

### GAP-016 — No Commission Calculation for Doctors

**What exists today:**
Doctor profiles have a commission rate field (percentage). Visit and invoice records reference the doctor.

**What is missing:**
- Commission calculation: revenue attributed to doctor × commission rate for a date range
- Commission basis options: total invoice value, consultation fee only, service subtotal
- Commission report per doctor per month
- Commission approval by manager
- Commission expense posted to finance module
- Commission history per doctor

**Effort estimate:** 3–4 days

---

### GAP-017 — No Vitals / Weight Trend Charts

**What exists today:**
Weight can be recorded on each visit. Data exists but is not visualized.

**What is missing:**
- Weight history chart on pet profile (line chart over time)
- Vital signs trend: temperature, heart rate, blood pressure across visits
- Body condition score history
- Abnormal trend flag (weight loss > 10% over 3 months → alert)
- Printable pet health summary with trend charts

**Effort estimate:** 2–3 days (Chart.js integration)

---

### GAP-018 — No Branch ID on Core Tables

**What exists today:**
The database has no `branch_id` column on any table. All data is assumed to belong to one clinic.

**What is missing:**
- `branch_id` column added to: users, appointments, visits, invoices, inventory_items, inventory_batches, stock_movements, expenses, attendance_records, grooming_bookings, boarding_bookings
- Branches table: id, name, name_ar, address, phone, manager_id, is_active
- All queries filtered by current user's branch (or all branches for super_admin)
- Multi-branch consolidated views for owner and super_admin

**Why this needs to happen now:**
Adding `branch_id` to tables with 0 records is a 1-day migration. Adding it to tables with 100,000 records requires a careful migration with downtime. The longer this waits, the more painful it becomes.

**Effort estimate:** 2–3 days (schema migration + context injection + query filters)
**Recommended for:** Do before going live with real data

---

## 🔵 NICE TO HAVE

### GAP-019 — Telemedicine / Video Consultation

**What is missing:** Video call booking integrated with Zoom or Google Meet. Doctor and owner receive a link. Consultation notes recorded as a visit. Prescription issued post-call.

**Effort estimate:** 5–7 days

---

### GAP-020 — Pet Insurance Integration

**What is missing:** Insurance provider catalog. Coverage lookup by policy number. Claim submission workflow. Insurance payment recording on invoice. Reimbursement tracking.

**Effort estimate:** 15–20 days (heavily dependent on insurance provider APIs)

---

### GAP-021 — Mobile App / PWA

**What is missing:** Native-feeling mobile experience for field staff. Push notifications. Offline capability for boarding and grooming staff. Camera integration for pet photos.

**Effort estimate:** Progressive Web App (PWA) wrapper: 5–7 days. Native app: 60+ days.

---

### GAP-022 — Customer Loyalty Program

**What is missing:** Points earned per visit/invoice. Point balance on owner profile. Redemption against invoice discount. Referral tracking (owner who referred new clients). Membership tier (Silver/Gold/Platinum).

**Effort estimate:** 5–6 days

---

### GAP-023 — Google Calendar / Outlook Sync

**What is missing:** Two-way sync of appointments to doctor's personal calendar. iCal feed URL per doctor. WhatsApp confirmation includes calendar invite link. Outlook plugin for reception.

**Effort estimate:** 4–5 days for one-way iCal feed; 8–10 days for two-way sync

---

## Recommended Action Plan

### Do Immediately (before production go-live)

| # | Action | Gap | Effort |
|---|--------|-----|--------|
| 1 | Automated daily database backup | GAP-011 | 1–2 days |
| 2 | Password migration to bcrypt | GAP-010 | 1 day |
| 3 | Login rate limiting and session timeout | GAP-010 | 1 day |
| 4 | Add branch_id to core tables | GAP-018 | 2–3 days |

### Phase 8 Completion (next sprint)

| # | Action | Gap | Effort |
|---|--------|-----|--------|
| 5 | Service / price catalog | GAP-007 | 3–4 days |
| 6 | In-app notification system | GAP-002 | 3–4 days |
| 7 | Prescription → dispensing → stock loop | GAP-001 | 5–7 days |

### Phase 9 (next quarter)

| # | Action | Gap | Effort |
|---|--------|-----|--------|
| 8 | Automated WhatsApp reminder engine | GAP-003 | 3–4 days |
| 9 | Payroll module | GAP-006 | 8–10 days |
| 10 | File / document storage | GAP-004 | 4–5 days |
| 11 | SOAP clinical note format | GAP-005 | 6–8 days |
| 12 | Reporting depth + charts + export | GAP-009 | 10–14 days |
| 13 | Client owner portal | GAP-008 | 10–12 days |
| 14 | 2FA for admin accounts | GAP-012 | 2–3 days |

---

## Total Effort Summary

| Category | Items | Estimated Days |
|----------|-------|---------------|
| Critical (do now) | 5 | 18–27 days |
| High priority | 7 | 37–50 days |
| Medium priority | 6 | 20–26 days |
| Nice to have | 5 | 39–53 days |
| **Total** | **23** | **114–156 days** |

> Assuming one developer working focused sprints. Many items can run in parallel with two developers.
