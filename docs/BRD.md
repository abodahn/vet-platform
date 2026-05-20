# Business Requirements Document (BRD)
## Premium Animal Hospital — Veterinary ERP Platform

| Field | Value |
|-------|-------|
| **Client** | Dr. Hatem El Khateeb |
| **Platform** | Premium Animal Hospital ERP |
| **Version** | 1.0 |
| **Date** | May 2026 |
| **Status** | Active Development |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Business Context & Objectives](#2-business-context--objectives)
3. [Stakeholders](#3-stakeholders)
4. [Scope](#4-scope)
5. [Functional Requirements by Module](#5-functional-requirements-by-module)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Data Model Summary](#7-data-model-summary)
8. [Roles & Permissions Matrix](#8-roles--permissions-matrix)
9. [Delivery Phases](#9-delivery-phases)
10. [Glossary](#10-glossary)

---

## 1. Executive Summary

This platform is a full-stack, multi-module veterinary clinic ERP system built to replace fragmented manual processes and a legacy monolithic application at Premium Animal Hospital. It covers every operational domain: clinical care, pharmacy, inventory, finance, HR, client relations, and AI-assisted decision-making — all under one branded interface with bilingual (Arabic/English) support and role-based access control.

### Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.x · Flask (Blueprint architecture) |
| Database | SQLite (WAL mode) — PostgreSQL-ready |
| Frontend | Jinja2 templates · Vanilla JS · Custom CSS design system |
| Auth | Session-based · SHA-256 password hashing |
| Language | Bilingual — English primary · Arabic (RTL) secondary |
| Themes | Medical (white/navy/gold) · Logo (navy/yellow) |
| Deployment | Self-hosted · Port 5100 |
| Legacy | Original Flask exam app running in parallel · Port 5000 |

---

## 2. Business Context & Objectives

### 2.1 Problem Statement

The clinic currently operates with:

- A legacy exam app that handles examinations only, with no integration to other workflows
- Manual spreadsheets for inventory tracking, finance reconciliation, and HR records
- No integrated appointment-to-invoice pipeline
- No structured HR, attendance, or leave management
- No central reporting or KPI visibility for management decisions
- Data scattered across multiple unconnected tools

### 2.2 Business Objectives

| # | Objective | Success Metric |
|---|-----------|----------------|
| 1 | Eliminate paper-based and spreadsheet workflows | 100% of daily operations recorded in the platform |
| 2 | Reduce invoice processing time | Invoice created within 2 minutes of service completion |
| 3 | Achieve full inventory traceability | Zero untracked stock movements |
| 4 | Enable data-driven management decisions | Weekly KPI report available without manual effort |
| 5 | Standardize client communication | 100% of appointment reminders sent via WhatsApp |
| 6 | Enforce role-based data access | No unauthorized access to financial or clinical data |
| 7 | Support clinic growth to multi-branch | Multi-branch module ready within 12 months |

### 2.3 Business Rules

- Every clinical action (visit, prescription, lab) must be linked to a verified pet and owner record
- All financial transactions require an associated invoice or expense record
- Stock movements must be traceable to a source document (PO, visit, adjustment)
- Attendance records are immutable by the staff member — only managers can edit
- Leave requests require manager approval before balance is deducted
- Invoices cannot be deleted — only voided with reason
- All system actions are recorded in the audit log

---

## 3. Stakeholders

| Role Code | Title | Responsibilities | Platform Access Level |
|-----------|-------|------------------|-----------------------|
| `super_admin` | Platform Owner / Dr. Hatem | Full system control, configuration | All modules + system |
| `clinic_owner` | Clinic Director | Operations oversight, financial review | All modules |
| `branch_manager` | Branch Head | Branch-level operations management | All operational modules |
| `doctor` | Veterinarian | Clinical examination, diagnosis, prescription | Clinical, pharmacy, AI |
| `nurse` | Vet Nurse / Technician | Clinical support, lab, vaccination | Clinical, lab, pharmacy |
| `reception` | Front-Desk Staff | Client check-in, appointments, invoicing | Appointments, CRM, finance |
| `finance` | Accounts Staff | Billing, payments, accounting, expenses | Finance, invoicing, reports |
| `inventory_mgr` | Warehouse / Stock Manager | Stock management, procurement | Inventory, pharmacy, procurement |
| `hr` | HR Officer | Staff management, attendance, leave | HR, attendance |
| `groomer` | Grooming Specialist | Grooming session management | Grooming only |
| `boarding_staff` | Pet Hotel Staff | Boarding check-in/out, daily notes | Boarding only |
| `auditor` | Internal / External Auditor | Compliance review | Read-only: reports, finance, audit |
| `support_admin` | IT / Support Staff | System health, configuration | System monitor, settings |

---

## 4. Scope

### 4.1 In Scope — Current Platform

| # | Module | Category | Status |
|---|--------|----------|--------|
| 1 | Module Launcher | Platform | ✅ Live |
| 2 | Authentication & Role Management | Platform | ✅ Live |
| 3 | Settings & Theme Configuration | Platform | ✅ Live |
| 4 | Appointments & Reception | Clinical | ✅ Live |
| 5 | Medical Visits & Records | Clinical | ✅ Live |
| 6 | Doctor Workspace | Clinical | ✅ Live |
| 7 | Laboratory & Diagnostics | Clinical | ✅ Live |
| 8 | Vaccination & Preventive Care | Clinical | ✅ Live |
| 9 | Surgery & Procedures | Clinical | ✅ Live |
| 10 | Owners & Pets CRM | CRM | ✅ Live |
| 11 | WhatsApp Communication Center | CRM | ✅ Live |
| 12 | Grooming | Operations | ✅ Live |
| 13 | Boarding / Pet Hotel | Operations | ✅ Live |
| 14 | Inventory & Warehouse | Inventory | ✅ Live |
| 15 | Pharmacy & Medication | Inventory | ✅ Live |
| 16 | Procurement & Suppliers | Inventory | ✅ Live |
| 17 | Billing & Invoicing | Finance | ✅ Live |
| 18 | Finance & Accounting | Finance | ✅ Live |
| 19 | HR & Staff Management | Admin | ✅ Live |
| 20 | Attendance & Leave Management | Admin | ✅ Live |
| 21 | AI Assistant | Intelligence | ✅ Live |
| 22 | Reports & Executive Dashboard | Intelligence | ✅ Live |
| 23 | System Monitor & Audit Log | System | ✅ Live |

### 4.2 Out of Scope — Future Phases

- Customer-facing mobile app / owner self-service portal
- Multi-branch consolidated control center
- Pet insurance billing and claims integration
- Telemedicine / video consultation booking
- External lab system integration (IDEXX, Heska, Vet Lab)
- Payroll disbursement via bank API
- Online booking widget for clinic website
- Google Calendar / Outlook calendar sync
- Customer loyalty / points system

---

## 5. Functional Requirements by Module

### 5.1 Authentication & Authorization

- Username and password login
- SHA-256 hashed passwords with platform salt
- Session-based authentication via Flask sessions
- Role-based route and page access enforcement via `login_required` decorator
- Profile management: full name, language preference, theme
- Master admin account bootstrapped automatically on first run
- Admin-initiated password reset for any staff member

### 5.2 Module Launcher

- Visual card grid of all platform modules grouped by category
- Status badges: Live · Beta · Coming Soon · Planned
- Live stats panel: appointments today, total owners, revenue today, outstanding balance
- Development roadmap section showing phase progress
- Quick-access buttons for legacy exam module and quick invoice
- Module cards clickable — routes to correct blueprint URL

### 5.3 Appointments & Reception

- Daily and weekly calendar view with configurable time slots
- Walk-in registration without a pre-existing booking
- Appointment status lifecycle: Scheduled → Confirmed → Checked-In → In-Progress → Completed → Cancelled
- Doctor and resource assignment per appointment
- Reason for visit and estimated duration
- Reception queue / waiting room view
- One-click conversion from appointment to medical visit
- No-show marking and rebooking

### 5.4 Medical Visits & EMR

- Visit record linked to: pet + owner + doctor + appointment (optional)
- Chief complaint entry (free text)
- Physical examination findings (structured fields)
- Diagnosis entry with notes
- Prescription writing linked to pharmacy inventory
- Treatment plan and post-visit instructions
- Follow-up date scheduling
- Chronological medical timeline per pet
- Discharge summary generation

### 5.5 Doctor Workspace

- Personal dashboard showing today's appointment queue
- Pending and in-progress visit list
- One-click access to full patient chart (pet + history)
- Quick prescription builder from standard item catalog
- Personal productivity statistics (visits completed, revenue generated)
- Ability to flag cases for follow-up or specialist referral

### 5.6 Laboratory & Diagnostics

- Lab test catalog: test name, code, normal range, unit, price
- Sample collection recording: sample type, collection time, collector
- In-house result entry with normal range flagging (high/low/normal)
- Send-out lab tracking (external reference, expected result date)
- AI-generated result interpretation summary
- Results attached to pet medical timeline
- Certificate and report PDF generation

### 5.7 Vaccination & Preventive Care

- Vaccine catalog with product names, batch tracking, and expiry
- Species-based default vaccination schedule templates
- Per-pet vaccination record and schedule
- Due and overdue reminder generation
- Vaccination certificate issuance
- FEFO (First Expiry First Out) batch deduction
- Pet passport integration and print

### 5.8 Surgery & Procedures

- Pre-op checklist and consent form recording
- Anesthesia notes and monitoring record
- Surgery findings and procedure notes
- Post-op care instructions
- Inventory deduction for surgical supplies
- Recovery monitoring notes
- Follow-up appointment scheduling

### 5.9 Owners & Pets CRM

- Owner profile: name, phone, email, address, communication preference, source/referral
- Multiple pets per owner with pet-owner link management
- Per-pet record: species, breed, gender, date of birth, microchip number, weight history, color, photo (future)
- Medical alerts and chronic condition flags on pet profile
- Full chronological medical timeline: visits, labs, vaccines, surgeries, grooming, boarding
- Outstanding balance and payment history visible on owner card
- Communication history log (WhatsApp messages sent)

### 5.10 WhatsApp Communication Center

- Message template library: create, edit, preview, activate/deactivate
- Variable substitution in templates: {owner_name}, {pet_name}, {appointment_date}, etc.
- Manual single-send to any owner
- Bulk campaign: select audience, choose template, schedule or send now
- Message delivery status tracking: Sent · Delivered · Read · Failed
- Full message log with timestamps and delivery status
- Failed message retry queue
- Appointment reminder manual trigger (automated trigger is Phase 9)

### 5.11 Grooming

- Grooming service catalog with name, duration, price, applicable species
- Session booking linked to pet and owner
- Groomer assignment per session
- Pre-session condition notes (matting, skin issues, temperament)
- Post-session notes and recommendations
- Product and supply usage deducted from inventory
- Session history per pet with before/after notes

### 5.12 Boarding / Pet Hotel

- Room and cage inventory: room number/name, type (kennel, suite, cat room), capacity, daily rate, status
- Booking linked to pet and owner with check-in and expected check-out dates
- Feeding schedule and dietary instructions per booking
- Medication administration instructions
- Daily welfare notes (eating, behavior, health observations)
- Booking status lifecycle: Reserved → Checked-In → Checked-Out → Cancelled
- Revenue calculation from stay duration × daily rate

### 5.13 Inventory & Warehouse

- Item master: name, code, category, unit of measure, reorder point, storage conditions
- Batch management per item: lot number, expiry date, supplier, quantity received, cost per unit
- FEFO deduction logic: oldest expiry batch deducted first
- Full stock movement ledger: receipt, dispense (visit/prescription), adjustment, transfer, return, disposal
- Expiry alerts: configurable days-in-advance threshold per item or globally
- Reorder suggestion report: items below reorder point
- Physical stocktake: count entry with variance reporting
- Item search with filters: category, expiry status, stock level

### 5.14 Pharmacy & Medication

- Medication flag on inventory items to separate drugs from supplies
- Prescription-linked dispensing workflow
- Controlled drug register with mandatory reason and authorization recording
- Dispensing label generation: pet name, owner, drug, dose, frequency, expiry
- Expired/returned medication disposal recording
- Prescription history per pet

### 5.15 Procurement & Suppliers

- Supplier profiles: name, contact person, phone, email, payment terms, account number, rating, status
- Purchase order creation with multiple line items (item, quantity, unit cost, total)
- Auto-generated PO numbers: PO-YYYY-NNNNN
- PO status lifecycle: Draft → Submitted → Partially Received → Received → Cancelled
- Goods receipt recording per line item with batch details (lot, expiry, received qty)
- Automatic stock update on goods receipt (new inventory batch created)
- Outstanding PO tracking and supplier balance view
- PO history per supplier

### 5.16 Billing & Invoicing

- Auto-numbered invoices: INV-YYYY-NNNNN
- Invoice linked to: owner + visit (optional) + date
- Line items: services (free-text or catalog) + inventory products (with batch deduction)
- Per-invoice and per-line discount (percentage)
- Tax calculation
- Multiple payment methods: cash, card, bank transfer, cheque
- Partial payment support with remaining balance tracking
- Payment status: Unpaid · Partial · Paid
- Outstanding balance per owner (sum of all unpaid invoices)
- Invoice void with mandatory reason (audit trail preserved)
- PDF generation for printing and sharing
- WhatsApp send of invoice link or PDF to owner

### 5.17 Finance & Accounting

- Daily revenue dashboard by payment method
- Expense recording: amount, category, vendor, date, description
- Expense categories: utilities, rent, salary, supplies, maintenance, other
- Daily closing: end-of-day cash count reconciliation
- Profit and Loss statement for any date range
- Cash flow summary (inflows vs outflows)
- Accounts receivable ageing report (0-30, 31-60, 61-90, 90+ days)
- Revenue breakdown by service category

### 5.18 HR & Staff Management

- Staff profiles: full name, username, role, department, hire date, national ID
- Personal information: phone, email, emergency contact
- Employment details: contract type, base salary, commission rate
- Document tracking: contract, ID copy, certifications (metadata only — file upload is Phase 9)
- Staff status: Active · On Leave · Terminated
- Admin password reset for any staff account
- Commission summary view (calculation in Phase 9)

### 5.19 Attendance & Leave Management

**Attendance Tracking**
- Staff self-service clock-in and clock-out with timestamp
- Manager override: record attendance for any staff member
- Break time recording (deducted from total hours worked)
- Daily attendance status: Present · Late · Absent · Leave · Holiday
- Manager edit of any attendance record with full audit
- Date-range attendance history with filters (staff, status, period)
- Summary statistics: total days, total hours, present count, late count

**Shift Management**
- Shift definitions: name, start time, end time, break minutes, working days, color
- Shift assignment to staff (staff_shifts)
- Visual shift display on attendance records

**Leave Management**
- Leave type catalog: name (EN + AR), days per year, paid/unpaid, color, active status
- Staff leave request submission with date range and reason
- Business day calculation: excludes weekends and public holidays
- Pre-submission balance check against remaining entitlement
- Manager approval / rejection workflow with rejection reason required
- Leave balance tracking per staff per leave type per year: Allocated / Used / Pending / Remaining
- Atomic balance updates: pending on submit → used + pending cleared on approval → pending released on rejection

**Reporting & Admin**
- Leave balance matrix: all staff × all leave types in a single grid view
- Monthly attendance report with per-staff summary cards (present, absent, late, hours)
- Approved leaves calendar view within monthly report
- Public holidays registry with year filter and quick-add Egyptian national holidays
- Export-ready structured data for payroll integration (Phase 9)

### 5.20 AI Assistant

- Role-aware context injection: doctor gets clinical prompts, finance gets accounting prompts, etc.
- Anthropic Claude API integration
- Chat interface with conversation history within session
- Suggested prompt library per role
- Markdown-rendered responses
- No persistent conversation history across sessions (Phase 9)

### 5.21 Reports & Executive Dashboard

- Revenue KPIs: daily, weekly, monthly, year-over-year comparison
- Appointment statistics: bookings, no-shows, completion rate by doctor
- Doctor productivity: visits completed, revenue generated, average visit duration
- Inventory value snapshot: total stock value, low-stock items, expiring items
- Top services by revenue and volume
- Top clients by lifetime spend
- WhatsApp message success rate
- Outstanding receivables summary

### 5.22 System Monitor & Audit Log

- Application health: uptime, memory usage, database file size
- Active session count and recent login history
- Database integrity check (PRAGMA integrity_check)
- Full audit log: user · action · table · record ID · timestamp · before/after values
- Audit log filters: user, date range, action type, module
- System settings: clinic profile (name, logo, address, contact)

---

## 6. Non-Functional Requirements

| Category | Requirement | Target |
|----------|-------------|--------|
| **Performance** | Page load time on LAN | < 2 seconds |
| **Performance** | List query response | < 500ms for up to 10,000 records |
| **Security** | Password storage | SHA-256 with platform salt (bcrypt in Phase 9) |
| **Security** | Session management | Server-side sessions with secure cookie flags |
| **Security** | Form submission | CSRF protection on all state-changing forms |
| **Security** | Role enforcement | Every route decorated with `login_required` + role check |
| **Reliability** | Server process | Auto-restart on crash via process manager |
| **Reliability** | Database | SQLite WAL mode for concurrent reads |
| **Scalability** | Database migration | Schema designed for PostgreSQL migration with no logic changes |
| **Scalability** | Architecture | Blueprint isolation — each module independently deployable |
| **Usability** | Responsive layout | Sidebar collapses on screens ≤ 900px |
| **Usability** | Arabic support | Full RTL layout when language set to Arabic |
| **Usability** | Theme | User theme preference persisted across sessions |
| **Accessibility** | Navigation | ARIA labels on all navigation elements |
| **Accessibility** | Forms | All form fields have associated labels |
| **Audit** | Coverage | All create, update, delete operations logged |
| **Audit** | Content | Log includes: user, action, module, record ID, timestamp |
| **Backup** | Frequency | Daily automated SQLite file backup (Phase 8) |
| **Backup** | Retention | 30-day rolling backup window |

---

## 7. Data Model Summary

### Platform

```
users               id, username, full_name, password_hash, role, department,
                    is_active, hire_date, phone, email, language, theme_preference

clinics             id, name, name_ar, logo_data, address, phone, email, license_no
settings            key, value
audit_log           id, user_id, username, action, module, record_id, details, created_at
```

### Clinical

```
owners              id, full_name, phone, email, address, source, notes, created_at
pets                id, owner_id, name, species, breed, gender, dob, microchip,
                    color, weight, medical_alerts, is_active

appointments        id, pet_id, owner_id, doctor_id, scheduled_at, duration_min,
                    reason, status, notes

visits              id, pet_id, owner_id, doctor_id, appointment_id, visit_date,
                    chief_complaint, examination, diagnosis, treatment_plan,
                    follow_up_date, status

prescriptions       id, visit_id, pet_id, doctor_id, notes, created_at
prescription_items  id, prescription_id, item_id, item_name, dose, frequency,
                    duration, quantity_dispensed

lab_requests        id, visit_id, pet_id, doctor_id, test_name, test_code,
                    sample_type, status, notes, created_at
lab_results         id, request_id, result_value, unit, normal_range, flag,
                    result_notes, resulted_at

vaccinations        id, pet_id, doctor_id, vaccine_name, batch_id, dose,
                    administered_at, next_due, certificate_no

surgeries           id, pet_id, doctor_id, surgery_type, pre_op_notes,
                    anesthesia_notes, procedure_notes, post_op_notes,
                    surgery_date, status
```

### Inventory

```
inventory_items     id, name, category, unit, reorder_point, is_medication,
                    is_controlled, storage_conditions, active

inventory_batches   id, item_id, lot_number, expiry_date, supplier_id,
                    quantity_received, quantity_remaining, unit_cost, received_at

stock_movements     id, item_id, batch_id, movement_type, quantity, reference_type,
                    reference_id, notes, performed_by, created_at

suppliers           id, name, contact_name, phone, email, payment_terms,
                    account_number, rating, is_active

purchase_orders     id, supplier_id, po_number, status, order_date,
                    expected_date, notes, total

po_lines            id, po_id, item_id, item_name, quantity_ordered,
                    quantity_received, unit_cost, total
```

### Finance

```
invoices            id, owner_id, visit_id, invoice_number, invoice_date,
                    subtotal, discount, tax, total, status, notes

invoice_items       id, invoice_id, description, quantity, unit_price,
                    discount, total, item_id

payments            id, invoice_id, amount, method, paid_at, received_by, notes

expenses            id, category, amount, vendor, expense_date, description,
                    recorded_by, created_at

daily_closings      id, closing_date, cash_sales, card_sales, total_revenue,
                    total_expenses, net, cash_counted, difference, closed_by
```

### Operations

```
grooming_services   id, name, species, duration_min, price, is_active
grooming_bookings   id, pet_id, owner_id, service_id, groomer_id, booking_date,
                    status, pre_notes, post_notes, price_charged

boarding_rooms      id, name, type, capacity, price_per_night, status, notes
boarding_bookings   id, pet_id, owner_id, room_id, check_in, check_out,
                    status, feeding_instructions, medication_instructions,
                    daily_rate, total_amount
```

### HR & Attendance

```
shifts              id, name, start_time, end_time, break_minutes,
                    days_of_week, color, is_active

staff_shifts        id, user_id, shift_id, effective_from, effective_to

attendance_records  id, user_id, username, full_name, work_date, check_in,
                    check_out, break_minutes, hours_worked, status,
                    notes, recorded_by, created_at, updated_at

leave_types         id, name, name_ar, days_per_year, is_paid, color, is_active

leave_balances      id, user_id, leave_type_id, year, allocated, used,
                    pending, remaining

leave_requests      id, user_id, username, full_name, leave_type_id,
                    leave_type_name, start_date, end_date, days_requested,
                    reason, status, approved_by, approved_at, rejection_reason

public_holidays     id, name, name_ar, holiday_date
```

### Communication

```
whatsapp_templates  id, name, category, body, variables_json, is_active
whatsapp_messages   id, owner_id, template_id, phone, message_body,
                    status, sent_at, delivered_at, error_message
whatsapp_campaigns  id, template_id, name, audience_filter, sent_count,
                    status, created_at
```

---

## 8. Roles & Permissions Matrix

| Module | super_admin | clinic_owner | branch_manager | doctor | nurse | reception | finance | inventory_mgr | hr | groomer | boarding_staff | auditor |
|--------|:-----------:|:------------:|:--------------:|:------:|:-----:|:---------:|:-------:|:-------------:|:--:|:-------:|:--------------:|:-------:|
| Launcher | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Appointments | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | — |
| Medical Visits | ✅ | ✅ | ✅ | ✅ | ✅ | 👁 | — | — | — | — | — | — |
| Doctor Workspace | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | — | — | — |
| Lab | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | — | — |
| Vaccination | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | — |
| Surgery | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | — | — |
| CRM | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — | — | 👁 |
| WhatsApp | ✅ | ✅ | ✅ | — | — | ✅ | — | — | — | — | — | — |
| Grooming | ✅ | ✅ | ✅ | — | — | ✅ | — | — | — | ✅ | — | — |
| Boarding | ✅ | ✅ | ✅ | — | — | ✅ | — | — | — | — | ✅ | — |
| Inventory | ✅ | ✅ | ✅ | 👁 | — | — | — | ✅ | — | — | — | 👁 |
| Pharmacy | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | — | — | — | — |
| Procurement | ✅ | ✅ | ✅ | — | — | — | ✅ | ✅ | — | — | — | 👁 |
| Invoicing | ✅ | ✅ | ✅ | ✅ | — | ✅ | ✅ | — | — | — | — | 👁 |
| Finance | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | — | 👁 |
| HR | ✅ | ✅ | ✅ | — | — | — | — | — | ✅ | — | — | — |
| Attendance | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — |
| AI Assistant | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | — | — |
| Reports | ✅ | ✅ | ✅ | — | — | — | ✅ | — | — | — | — | ✅ |
| System | ✅ | — | — | — | — | — | — | — | — | — | — | — |
| Settings | ✅ | ✅ | — | — | — | — | — | — | — | — | — | — |

> ✅ Full access · 👁 Read-only · — No access

---

## 9. Delivery Phases

| Phase | Scope | Status | Notes |
|-------|-------|--------|-------|
| **Phase 1** | Platform shell · Module launcher · Two themes · Auth · Role navigation | ✅ Live | Foundation complete |
| **Phase 2** | Admin & HR · Role management · Staff profiles · Password reset | ✅ Live | |
| **Phase 3** | Appointments calendar · Reception workspace · Doctor workspace · Medical visits | ✅ Live | |
| **Phase 4** | Inventory · Warehouse · Batch/Expiry · Pharmacy · Procurement | ✅ Live | |
| **Phase 5** | Finance engine · Invoicing · Payments · Daily closing · P&L · Cash flow | ✅ Live | |
| **Phase 6** | Lab · Vaccination · Surgery · Grooming · Boarding | ✅ Live | |
| **Phase 7** | AI Assistant · Role-based AI · Smart prompts · Reports dashboard | ✅ Live | |
| **Phase 8** | Attendance & Leave · Demo data · Security hardening · Backup | 🔧 In Progress | Attendance done |
| **Phase 9** | Multi-branch · Owner portal · Payroll · WhatsApp automation · External integrations | 🔮 Planned | |

---

## 10. Glossary

| Term | Definition |
|------|------------|
| **BRD** | Business Requirements Document — defines what the system must do |
| **EMR** | Electronic Medical Record — digital pet health record |
| **FEFO** | First Expiry First Out — inventory deduction prioritizing oldest expiry date |
| **SOAP** | Subjective / Objective / Assessment / Plan — clinical note format |
| **PO** | Purchase Order — formal order document sent to a supplier |
| **AP** | Accounts Payable — money owed by the clinic to suppliers |
| **AR** | Accounts Receivable — money owed to the clinic by clients |
| **WAL** | Write-Ahead Logging — SQLite mode enabling concurrent reads |
| **CSRF** | Cross-Site Request Forgery — form attack protection |
| **FEFO** | First Expiry First Out — inventory dispatch priority rule |
| **KPI** | Key Performance Indicator — measurable business metric |
| **RTL** | Right-to-Left — text direction for Arabic language |
| **Blueprint** | Flask architectural unit — isolated module with its own routes and templates |
| **Legacy App** | Original examination Flask app running on port 5000 in parallel |
