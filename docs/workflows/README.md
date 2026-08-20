# The Workflow Book — Contents

**دليل سير العمل — الفهرس**

This book is task-shaped. Each chapter walks a job from the first click to the last,
in the order a clinic actually does it. If you want a field-by-field description of
one screen instead, use the [Reference Manual](../manual/README.md).

Every chapter in this book was written from the route functions and Jinja templates,
not from the UI and not from intent. Each section carries a `Source:` line with
`file:line`. Where a screen does less than its label promises, the chapter says so in
its own **Known limits** section instead of describing the version that does not exist.

Nothing in this book was exercised in a browser. It is read from source.

---

## Chapters, in clinic order

| # | Chapter | File | Modules / URL prefixes | What it covers |
|---|---------|------|------------------------|----------------|
| 1 | **Front Desk** | [`frontdesk.md`](frontdesk.md) | `crm` `/crm/`, `appointments` `/appointments/`, `workflow` `/workflow/` | Registering a client and a pet, booking and rescheduling appointments, running the reception day, the waiting-room TV, and the whole walk-in visit on one page. |
| 2 | **Clinical** | [`clinical.md`](clinical.md) | `visits` `/visits/`, `clinical` `/clinical/` | Opening a visit, SOAP notes and diagnosis, writing prescriptions, closing and billing the visit, the one-screen exam (Hatem Way / طريقة حاتم), lab requests, vaccination recalls, surgeries. |
| 3 | **Services** | [`services.md`](services.md) | `grooming` `/grooming/`, `boarding` `/boarding/`, `inpatient` `/inpatient/`, `telemedicine` `/telemedicine/`, lab `/clinical/lab`, `imaging` `/imaging/` | The six bookable and bedside services: grooming booking to invoice, boarding reservation through check-out, inpatient admit-monitor-discharge, video consultations, lab request to result, imaging capture and read, plus standalone AI photo triage. |
| 4 | **Pharmacy, Inventory & Procurement** | [`pharmacy.md`](pharmacy.md) | `pharmacy` `/pharmacy/`, `inventory` `/inventory/`, `procurement` `/procurement/` | Dispensing a prescription and printing the label, the controlled-drug register, cataloguing and receiving stock, expiry watch, warehouse transfers, suppliers and purchase orders end to end. |
| 5 | **Pet Shop** | [`petshop.md`](petshop.md) | `petshop` `/petshop/` | Retail counter sale (POS), cancelling a sale and restoring stock, product catalogue and pricing, deliveries and stock corrections, low-stock alerts, past-sale lookup, period trading review. |
| 6 | **Finance** | [`finance.md`](finance.md) | `finance` `/finance/`, `accounting` `/accounting/` | Billing a visit and taking money at the counter, manual invoices, estimates and approvals, client deposits and credit, corrections, voids and credit notes, clinic expenses, daily till close, month-end reporting, debt chasing, the monthly budget. |
| 7 | **Insights** | [`insights.md`](insights.md) | `launcher` `/`, `reports` `/reports/`, `ai_assistant` `/ai/`, `petsy` `/petsy/` | The morning dashboard check, the module catalogue, executive and financial reports with period comparison, stock and doctor-revenue reviews, CSV extracts, the custom report builder, and every AI surface (Assistant, Ctrl+K palette, embedded actions, Petsy staff and public modes). |
| 8 | **People** | [`people.md`](people.md) | `hr` `/hr/`, `attendance` `/attendance/`, `payroll` `/payroll/` | Hiring a staff member and giving them a login, shifts and the weekly roster, the daily clock-in/out and correcting a record, the nightly auto-close, leave request through approval, balances, types and public holidays, overtime, salary grades, generating/approving/paying a month of payroll, keeping the staff file, and month-end attendance reporting. **Workflows 1–14** |
| 9 | **System** | [`system.md`](system.md) | `system` `/system/`, `settings` `/settings/`, `auth` `/auth/`, staff accounts under `/hr/staff` | Signing in with or without two-step, the shared reception PC, creating logins and changing what a role can see, clinic identity and branding, backup, restore and USB transfer, stuck maintenance mode, data export, the audit log, offline-sync conflicts, branches and multi-clinic. |
| 10 | **Communications** | [`comms.md`](comms.md) | `whatsapp` `/whatsapp/`, `notifications` `/notifications/` | Connecting the clinic's WhatsApp (token, instance ID, QR), sending one message from the Send Centre, sending a bill from an invoice, messaging a client from their record, message templates, the two reminder screens, bulk campaigns, the nightly 09:00 reminder job (appointment, vaccine, overdue invoice), triggering it by hand, reading the message log, and the notification bell. |
| 11 | **Doctor Workspace** | [`doctor.md`](doctor.md) | `doctor` `/doctor/` | The vet's own day: the personal workspace and its three counters, working today's queue, checking a booked appointment in, opening the medical record (and when to use the Hatem Way instead), My Patients and My Schedule, My Statistics. Read-only except one check-in POST. |
| 12 | **Clinical Decision Support** ⚕ | [`cds.md`](cds.md) | `cds` `/cds/` | Screening a prescription for species contraindications, breed (MDR1) rules and drug interactions; sizing a weight-based dose range; screening a prescription already written, from the pharmacy hand-off. A deterministic rule engine over one curated data file — **read the chapter's opening advisory before using it clinically.** |
| 13 | **Data Migration & Import** | [`migration.md`](migration.md) | `migration` `/migration/` | Bringing a clinic's existing Excel/CSV back-file in through the four-step wizard (upload, map columns, preview, commit behind a verified backup), getting the failed rows back to the clinic and re-importing them, re-running a file or importing a second one, and the command-line importer. |

Order note: services (3) sits with clinical because the same vet is doing the work
on the same patient; pet shop (5) sits with pharmacy because both move stock, and
before finance because a shop sale is money the till has to account for. Chapters
11–13 were written after 1–10 and are appended rather than slotted in, so the
`Chapter N` references inside the earlier chapters stay correct; by clinic order
Doctor Workspace (11) and Clinical Decision Support (12) belong beside Clinical (2),
and Data Migration (13) beside System (9).

Source: chapter files as linked; `platform/app.py:237-290` (every blueprint above is
registered here); URL prefixes from each `platform/blueprints/<module>/__init__.py`.

---

## A–Z index of tasks

Each entry points at the chapter and the numbered workflow inside it.

### A
- **Admit a patient to the ward** — Services § 5
- **AI Assistant, ask it something** — Insights, Workflow 11
- **AI photo triage, standalone** — Services § 9
- **Appointment, book one** — Front Desk, Workflow 3
- **Appointment, check a booked one in (doctor's queue)** — Doctor Workspace, Workflow 3
- **Appointment, reschedule one** — Front Desk, Workflow 4
- **Attendance / clock-in and clock-out** — People, Workflow 3
- **Audit log, find who changed a record** — System, Workflow 14

### B
- **Backup, nightly and manual** — System, Workflow 8
- **Backup, notice it has stopped** — System, Workflow 9
- **Backup, carry it on a USB stick** — System, Workflow 11
- **Boarding, reserve / check in / check out / invoice** — Services § 3
- **Boarding rooms, set them up** — Services § 4
- **Branch setup** — System § 18
- **Branding and clinic identity** — System, Workflow 7
- **Budget, set the monthly spending target** — Finance, Workflow 13

### C
- **Campaign, send WhatsApp to many clients** — Communications, Workflow 7
- **Cancel a shop sale and restore stock** — Pet Shop, Workflow 2
- **Cash, close the day and reconcile the till** — Finance, Workflow 10
- **Categories, organise the shop catalogue** — Pet Shop, Workflow 7
- **Client, register a new one** — Front Desk, Workflow 1
- **Client's whole file, work it at the counter** — Clinical, Workflow 8
- **Column mapping, confirm it for an import file** — Data Migration, Workflow 1
- **Command-line import, no browser** — Data Migration, Workflow 4
- **Controlled-drug register, review and print** — Pharmacy, W-5
- **Credit note, partial** — Finance, Workflow 7
- **CSV bulk extract (the four buttons)** — Insights, Workflow 7
- **Custom report, build one** — Insights, Workflow 8

### D
- **Data, take the clinic's out of the product** — System, Workflow 13
- **Deposit, take one before there is a bill, then spend it** — Finance, Workflow 5
- **Diagnosis, record one** — Clinical, Workflow 2
- **Discharge from the ward** — Services § 5
- **Dispense a prescription** — Pharmacy, W-1
- **Doctor's day, start it (workspace and its counters)** — Doctor Workspace, Workflow 1
- **Doctor revenue, review it** — Insights, Workflow 6
- **Dose, size a weight-based one for one patient** — Clinical Decision Support ⚕, Workflow 2
- **Drug interactions, screen a prescription for them** — Clinical Decision Support ⚕, Workflow 1
- **Drug reference, check a prescription against it** — Pharmacy, W-3 · Clinical Decision Support ⚕, Workflow 3

### E
- **Estimate a surgery, get it approved, then bill it** — Finance, Workflow 4
- **Excel / CSV back-file, import a clinic's** — Data Migration, Workflow 1
- **Expenses the clinic itself paid** — Finance, Workflow 9
- **Expiring stock, monitor it** — Pharmacy, W-11

### F
- **Failed import rows, return them to the clinic and re-import** — Data Migration, Workflow 2
- **Financial period comparison** — Insights, Workflow 4

### G
- **Grooming, book through to invoice** — Services § 1
- **Grooming service catalogue, maintain it** — Services § 2

### H
- **Hatem Way / طريقة حاتم — the one-screen exam** — Clinical, Workflow 6
- **History, hand the record to the owner** — Clinical, Workflow 5

### I
- **Imaging study, capture and read it** — Services § 8
- **Import a clinic's existing records (the four-step wizard)** — Data Migration, Workflow 1
- **Import a second file, or re-run the same one** — Data Migration, Workflow 3
- **Interaction pairs, what the rule set actually covers** — Clinical Decision Support ⚕ § 0.5
- **Invoice a completed visit and take the money** — Finance, Workflow 1
- **Invoice by hand** — Finance, Workflow 2
- **Invoice, correct a wrong one** — Finance, Workflow 6
- **Invoice, get it to the client** — Finance, Workflow 8
- **Invoice, settle an outstanding one later** — Finance, Workflow 3

### L
- **Label, print one for a medicine** — Pharmacy, W-2
- **Lab request, then the result** — Clinical, Workflow 9 · Services § 7
- **Leave, request one** — People, Workflow 6 · **approve or reject** — Workflow 7 · **balances, types, holidays** — Workflow 8
- **Login for a new staff member** — System, Workflow 4
- **Low-stock alert, act on one (shop)** — Pet Shop, Workflow 6
- **Loyalty points, redeem or adjust** — Front Desk, Workflow 10

### M
- **Maintenance mode, clear a stuck one** — System, Workflow 12
- **MDR1 / breed contraindication, check for one** — Clinical Decision Support ⚕, Workflow 1
- **Medical record, open it from the doctor's queue** — Doctor Workspace, Workflow 4
- **Module, find and open one from the catalogue** — Insights, Workflow 2
- **Money that has not come in, chase it** — Finance, Workflow 12 · Front Desk, Workflow 8
- **Month-end reporting** — Finance, Workflow 11
- **Morning dashboard check** — Insights, Workflow 1
- **Multi-clinic, bring a new clinic onto the deployment** — System, Workflow 17
- **My Patients / My Schedule (doctor's own)** — Doctor Workspace, Workflow 5
- **My Statistics (doctor's own)** — Doctor Workspace, Workflow 6

### N
- **Notification bell, read and clear staff alerts** — Communications, Workflow 11
- **No-show risk — judge whether a booking will be honoured** — Front Desk, Workflow 11

### O
- **Offline-sync conflict, resolve one** — System, Workflow 16
- **Overtime, log and approve it** — People, Workflow 9

### P
- **Patient record, read it and hand over its history** — Front Desk, Workflow 9
- **Payroll, generate, approve and pay a month** — People, Workflow 11 · **salary grades** — Workflow 10
- **Pet, register one against a client** — Front Desk, Workflow 2
- **Petsy, staff mode (live clinic data)** — Insights, Workflow 14
- **Petsy, a pet owner's public question** — Insights, Workflow 15
- **POS counter sale** — Pet Shop, Workflow 1
- **Prescription, screen one before you write it** — Clinical Decision Support ⚕, Workflow 1
- **Prescription already written, screen it from the pharmacy page** — Clinical Decision Support ⚕, Workflow 3
- **Prescription, write one (including on another vet's behalf)** — Clinical, Workflow 3
- **Preview an import before anything is saved** — Data Migration, Workflow 1
- **Product, add one to the catalogue** — Pet Shop, Workflow 3
- **Product, re-price or correct one** — Pet Shop, Workflow 4
- **Purchase order, raise it** — Pharmacy, W-15 · **progress it** — W-16 · **receive it** — W-17

### Q
- **Queue, work the doctor's own** — Doctor Workspace, Workflow 2
- **Quick ask from anywhere (Ctrl+K)** — Insights, Workflow 12
- **Quote a surgery or hospital stay** — Finance, Workflow 4

### R
- **Reception day, run it (check-in to closing)** — Front Desk, Workflow 5
- **Reception PC shared by up to five people** — System, Workflow 2
- **Reminders list, work the queue** — Communications, Workflow 6
- **Reminder job, run it by hand (all / appointment / vaccine / invoice)** — Communications, Workflow 9
- **Reminders, the nightly 09:00 automatic job** — Communications, Workflow 8
- **Replenish short stock, alert to purchase order** — Pharmacy, W-10
- **Report, describe one in plain language** — Insights, Workflow 10
- **Report configuration, save and re-run it** — Insights, Workflow 9
- **Reports, executive review** — Insights, Workflow 3
- **Restore the database from a backup** — System, Workflow 10
- **Role, change what it can see** — System, Workflow 5
- **Role, move one person onto a different one** — System, Workflow 6

### S
- **Sale, look up a past one (shop)** — Pet Shop, Workflow 8
- **Sign in for the day** — System, Workflow 1
- **Species contraindication ("do not give X to a cat")** — Clinical Decision Support ⚕, Workflow 1
- **Stock item, catalogue one** — Pharmacy, W-6
- **Stock, receive without a purchase order** — Pharmacy, W-7
- **Stock, read an item's full history** — Pharmacy, W-8
- **Stock movement, trace where it came from** — Pharmacy, W-12
- **Stock, move between warehouses** — Pharmacy, W-13
- **Supplier, add or maintain** — Pharmacy, W-14
- **Supplier, order from a specific one** — Pharmacy, W-15
- **Surgery, record one** — Clinical, Workflow 11
- **System feels wrong, work out why** — System, Workflow 15

### T
- **Templates, WhatsApp message** — Communications, Workflow 5
- **Telemedicine video consultation** — Services § 6
- **Trading review, period (shop)** — Pet Shop, Workflow 9
- **Two-step verification, enrol or reset** — System, Workflow 3

### V
- **Vaccination recall loop** — Clinical, Workflow 10
- **Visit, open a long-form one** — Clinical, Workflow 1
- **Visit, work it up (SOAP, diagnosis, treatment plan)** — Clinical, Workflow 2
- **Visit, close and bill it** — Clinical, Workflow 4
- **Visit, find one again** — Clinical, Workflow 12
- **Void a bill** — Finance, Workflow 7

### W
- **Waiting-room TV** — Front Desk, Workflow 6
- **Weight-based dose range** — Clinical Decision Support ⚕, Workflow 2
- **Walk-in, register one without leaving the exam** — Clinical, Workflow 7
- **Walk-in visit, end to end on one page** — Front Desk, Workflow 7
- **WhatsApp, connect the clinic's number (QR, token, instance ID)** — Communications, Workflow 1
- **WhatsApp, send one message** — Communications, Workflow 2
- **WhatsApp, send a bill from an invoice** — Communications, Workflow 3 · Finance, Workflow 8
- **WhatsApp, message a client from their record** — Communications, Workflow 4
- **WhatsApp message log, read it and diagnose a failure** — Communications, Workflow 10
- **WhatsApp notification bell (staff alerts)** — Communications, Workflow 11

---

## Known limits of this book

These are limits of the **documentation**, not of the product. Product limits live in
each chapter's own *Known limits* section.

1. *(Cleared.)* People (chapter 8) was listed here as unfinished — section 0 only, ending
   at a `<!--PART2-->` marker, with no matching Reference Manual chapter. Both are now
   done: `people.md` carries section 0 plus Workflows 1–14, Known limits, a *Could not
   verify* section and a quick reference, and `docs/manual/people.md` exists.
   Source: `docs/workflows/people.md:19-3396`; `docs/manual/people.md`.

2. **Two registered modules have no chapter in either book.** They are reachable in
   the product but undocumented here:

   | Module | URL prefix | Mentioned in passing |
   |---|---|---|
   | Service catalogue | `/catalog/` | Services § 10 (one line) |
   | REST APIs | `/api/v1/`, `/api/public/` | Insights (public API only) |

   `/whatsapp/` and `/notifications/` came off this list when chapter 10 was written;
   `/doctor/`, `/cds/` and `/migration/` came off it with chapters 11, 12 and 13.
   Source: `platform/app.py:237-290`; `platform/blueprints/catalog/routes.py`,
   `api_v1/`, `public_api/`.

3. **Nothing here was tested in a browser.** Every chapter states this. Claims are
   read from route functions and templates. A behaviour that depends on runtime data,
   a background job or a device (camera, printer, WhatsApp session) is described from
   the code path only.

4. **Section numbering is not uniform across chapters.** Front Desk, Clinical, Finance,
   Pet Shop, System, Doctor Workspace, Clinical Decision Support and Data Migration
   number their tasks `Workflow N`; Pharmacy uses `W-N`; Services uses plain section
   numbers `§ 1`–`§ 9`; Insights uses `Workflow N` plus lettered appendices. The index
   above uses each chapter's own scheme.

5. **Clinical Decision Support (chapter 12) documents a data file that ships marked
   `DRAFT — NOT YET REVIEWED BY A LICENSED VETERINARIAN`.** The chapter describes the
   engine faithfully, including where its rule set is silent; it does not vouch for the
   clinical content. Absence of a warning in that module is never a statement of safety.
   Source: `platform/blueprints/cds/drug_data.json` → `review_status`, `_KNOWN_GAPS`.
