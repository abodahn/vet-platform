# A day in the life / يوم في العيادة

Three people, one clinic, one day. Not a reference — just the order things
actually happen in, and which screen each moment lives on.

For the field-by-field detail, follow the links into [`../manual/`](../manual/).
For the same jobs with every edge case, see [`../workflows/`](../workflows/).

---

# 1 · Mona, receptionist / موظفة استقبال

Role: `reception`. Granted by default: patients, appointments, invoicing,
catalog, whatsapp, grooming, boarding, petshop, attendance.
*Source: `models/database.py:4365-4367`*

## 08:00 — Open up

Sign in at `/auth/login`. If the desk PC is shared, the second and third person
sign in through **Add a user to this PC / إضافة مستخدم لهذا الجهاز** under the
user menu rather than logging Mona out; switching back is one click, up to five
accounts.

Then open two tabs and leave them open all day:

- `/appointments/reception` — **Reception Workspace**. Today's bookings laid out
  in hour rows from 08:00 to 20:00, with four counters across the top: total,
  checked-in, waiting (Scheduled + Confirmed), completed. A client lookup box
  that asks the server, so it finds client 900 as easily as client 9.
- `/appointments/waiting-room` on the TV, opened once with its token.

*Source: `blueprints/appointments/routes.py:559-610`, `:723-841`;
`blueprints/auth/routes.py:880-1011`*

## 08:20 — First arrival, has an appointment

Find them on the Reception Workspace → set status to **Checked-in**. The TV
picks them up on its next refresh, and the doctor's queue sees them.

Statuses: Scheduled, Confirmed, Checked-in, Completed, Cancelled, No-Show.

*Source: `blueprints/appointments/routes.py:40`, `:428-455`*

## 08:40 — A walk-in with no appointment

The one honest note in this whole page: **`/workflow/` — New Visit / زيارة
جديدة — is not open to `reception` by default.** It is governed by the `visits`
grant, and the seeded reception role does not hold it, even though the sidebar
puts it second because it is meant to be reception's screen. Either an
administrator grants `visits` to reception (which also opens the clinical
module), or Mona does this instead:

1. `/crm/owners` → **➕ New Owner / مالك جديد** if they are new. Full name is the
   only required field; a phone already on file is refused, naming the client
   who has it.
2. Their profile → **🐾 Add Pet / إضافة حيوان**.
3. `/appointments/new` for today, or hand them straight to the vet, who can
   register client and pet from inside the exam screen.

*Source: `blueprints/auth/routes.py:140-152`; `models/database.py:4365-4367`;
`blueprints/crm/routes.py:245-313`, `:686-762`; `templates/base.html:113-118`*

## 09:00 — Phone rings: "can I book Thursday?"

`/appointments/new`. Pick the client, then the pet — the two are checked
together, so a stale form cannot book one client's pet under another client's
name. Then date, start time, duration, doctor, type (Consultation, Vaccination,
Surgery, Grooming, Lab, Follow-up, Emergency) and priority (Normal, Urgent,
Emergency).

`/appointments/calendar` is the week view when someone asks "what have you got
next week".

*Source: `blueprints/appointments/routes.py:37-38`, `:223-271`, `:272-393`*

## 11:30 — A consultation finishes, client comes to the counter

If the vet used the one-screen exam, the invoice already exists and is probably
already paid — Mona only prints it. Otherwise:

- `/finance/invoices/<id>` → **✅ Record Payment / تسجيل الدفع**. Amount, method,
  reference. A typo in the amount is refused by name rather than posted as zero,
  and a double click cannot charge twice.
- Payment awards loyalty points at 1 point per 10 EGP.
- **🖨 Print / طباعة**, **⬇ Download PDF / تحميل PDF**, or
  **📱 Send WhatsApp / إرسال**.

*Source: `blueprints/finance/routes.py:368-430`, `:663-752`*

## 13:00 — Someone buys a bag of food

`/petshop/pos`. Only products that are active and have stock above zero appear.
Cash asks for the amount tendered and shows the change; Card, Transfer and
Instapay are recorded as paid in full. If two tills try to sell the same last
unit, the second one fails rather than both succeeding.

*Source: `blueprints/petshop/routes.py:439-455`, `:457-560`*

## 16:00 — Chase what is outstanding

`/finance/invoices` filtered by status. Open the client at `/crm/owners/<id>`
for their balance — the **Balance EGP / الرصيد بالجنيه** tile there is computed
from live invoices. The Balance column on the owners *list* is a stored field
nothing writes, so it shows `—` for everybody; ignore it.

*Source: `blueprints/finance/routes.py:149-205`; `blueprints/crm/routes.py:61-81`*

## 19:00 — Close the desk

Set any remaining bookings to Completed, Cancelled or No-Show so tomorrow's
Reception Workspace opens clean, then sign out.

**Deeper:** [`../manual/frontdesk.md`](../manual/frontdesk.md) ·
[`../workflows/frontdesk.md`](../workflows/frontdesk.md)

---

# 2 · Dr Hatem, veterinarian / طبيب بيطري

Role: `doctor`. Granted by default: patients, appointments, visits, pharmacy,
reports, catalog, inpatient, telemedicine, imaging, ai, attendance. No money
modules.
*Source: `models/database.py:4359-4361`*

## 08:30 — What does today look like

`/doctor/` — **Doctor Workspace / مساحة الطبيب**. Four things:

- today's appointments — filtered to appointments whose `doctor_name` contains
  his full name (managers and owners see everybody's);
- open visits — up to 10 visits still at status `Open`, same name filter;
- vaccinations due in the next 7 days, up to 10, across all pets;
- three counters: appointments today, open visits, visits completed today.

If the queue is empty and it should not be, the name typed on the appointment
does not match his staff record's full name. That is the whole filter.

*Source: `blueprints/doctor/routes.py:25-128`*

## 09:00 — The consultation, on one screen

`/visits/exam` — **Hatem Way / طريقة حاتم**. Search by phone or client name,
pick the pet. If they are new, **+ New client walked in / عميل جديد** registers
client and pet without leaving the page.

The middle column is the visit:

- **This visit / هذه الزيارة** — weight (kg), temp (C), visit date,
  **Seen by / الطبيب المعالج**, pre-filled with whoever is signed in.
- **Symptom or disease / العرض أو المرض**, then
  **Diagnosis / التشخيص** with severity (Mild / Moderate / Severe) and a
  **Chronic / مزمن** tick.
- Foldout panels for **Prescription / الروشتة**,
  **Vaccination given today / تطعيم أُعطي اليوم**,
  **Book the follow-up / حجز المتابعة**, and
  **Attach a photo or file / إرفاق صورة أو ملف**.

The right column is money: **Services and items / الخدمات والأصناف** (type,
press Enter, adjust price / qty / discount %), then **Payment / الدفع** with
cash or Visa, a discount, **Cash received / المبلغ المستلم**, and live
**Change / الباقي** and **Due / المتبقي**.

Left of it all, the client's whole file in tabs: Visit / الكشف,
Pets / الحيوانات, Owner / المالك, Planned / المواعيد, History / السجل,
Medical / طبي, Invoices / الفواتير, Payments / المدفوعات,
Reminders / التذكيرات, Documents / الملفات, Tasks / المهام, Notes / ملاحظات.

**Save visit / حفظ الكشف** — or **Save and print / حفظ وطباعة**, which lands on
the printable invoice — writes, in one go: the visit (status Completed, type
Consultation), the diagnosis, every vaccination row, every prescription line,
a follow-up appointment if a date was set (09:00 if no time given), the
attachment, the invoice, and the payment. Cash above the bill is change, not an
overpayment; anything short shows as Due.

Two things worth knowing:

- Weight entered here also updates the pet's record.
- **Billing a vaccine as a service does not record it.** Only the
  **Vaccination given today** panel writes the vaccine history and the next due
  date the reminder reads. The panel says so on screen.

*Source: `blueprints/visits/routes.py:691-715`, `:827-849`, `:1301-1537`;
`templates/visits/exam.html:105-520`*

## 10:30 — A case that needs working up properly

`/visits/new` for the long form, then `/visits/<id>` to add SOAP, diagnoses,
treatment plan and prescriptions section by section, and **Complete** it when
the work-up is finished.

A prescription is written against the doctor **named on the visit**, not
whoever is logged in — so a nurse can enter it on his behalf and the record
still says Hatem.

*Source: `blueprints/visits/routes.py:67-236`, `:237-464`, `:465-590`*

## 11:15 — Bloods

`/clinical/lab/new` raises the request; `/clinical/lab/<id>` is where the result
goes in when it comes back.

*Source: `blueprints/clinical/routes.py:93-227`*

## 12:00 — X-ray

`/imaging/` for all studies, `/imaging/analyzer` for the AI photo analyser.

*Source: `blueprints/imaging/routes.py:185`, `:339-400`*

## 14:00 — Meds

The prescription he wrote lands in `/pharmacy/`, the dispensing queue: anything
whose status is not `Dispensed`. The pharmacist (or a nurse or doctor — the
dispense action allows super admin, clinic owner, branch manager, pharmacist,
inventory manager, nurse and doctor) picks a batch per line and presses
**💊 Dispense Selected / صرف المحدد**. An expired batch is refused by name and
expiry date.

A medication typed as free text rather than picked from stock is marked
dispensed and written to the audit log, but moves no stock — there is nothing in
inventory to move.

*Source: `blueprints/pharmacy/routes.py:12`, `:18-44`, `:127-282`*

## 17:30 — Before going home

Back to `/doctor/` for anything still Open, and `/visits/` to find a visit again
if a client rings about one.

**Deeper:** [`../manual/clinical.md`](../manual/clinical.md) ·
[`../workflows/clinical.md`](../workflows/clinical.md) ·
[`../manual/pharmacy.md`](../manual/pharmacy.md)

---

# 3 · Nadia, clinic owner / صاحبة العيادة

Role: `clinic_owner`. Every module, plus system, backup, audit and settings.
*Source: `models/database.py:4347`*

## 08:00 — The one-minute look

`/` — the home dashboard. Every module she can open, grouped by category, plus
today's live numbers pulled from the database: owners, pets, bookings today,
pending reminders, revenue today, visits today, unpaid invoices, outstanding.

*Source: `blueprints/launcher/routes.py:599-639`*

## 08:05 — Anything shouting?

- 🔔 in the topbar → `/notifications/` — her 50 most recent, with mark-read.
- `/inventory/alerts` — what is short or expiring.
- `/system/backup` — loading the page runs a health check. If backups have
  stopped, the page says so in red and tells her to press **💾 Back Up Now** and
  call IT if it fails. Retention is stated on screen: 30 days, daily at 02:00.

*Source: `blueprints/notifications/routes.py:8-18`;
`blueprints/inventory/routes.py:475-502`;
`blueprints/system/routes.py:453-478`; `templates/system/backup.html:34-74`*

## 10:00 — How is the month going

`/accounting/` — **Accounting Dashboard**. Revenue this month (paid amounts on
invoices created since the 1st), expenses this month, net profit, profit margin,
and the top five expense categories.

Then the detail:

- `/accounting/pl` — profit and loss.
- `/accounting/cashflow` — cash in and out.
- `/accounting/budget` — the monthly spending target.
- `/finance/reports` — the finance summary (restricted to super admin, clinic
  owner, branch manager, finance and auditor; reception cannot see it), with an
  Excel export at `/finance/reports/export/xlsx`.

*Source: `blueprints/accounting/routes.py:21-155`, `:156`, `:227`, `:540`;
`blueprints/finance/routes.py:846-911`*

## 11:00 — Which doctor, which service, which month

- `/reports/dashboard` — headline stats, revenue by day for 30 days, top 10
  services.
- `/reports/financial` — a date range with a summary and daily revenue.
- `/reports/financial/compare` — one period against another.
- `/reports/doctor-revenue` — invoiced, collected and pending per doctor for a
  date range, with a breakdown by line type.
- `/reports/clinical` — visits by type over 30 days.
- `/reports/inventory` — stock value, with `/reports/inventory/export/xlsx`.
- `/reports/export/csv?type=owners|pets|visits|invoices` — the raw lists.
  Visits and invoices are capped at the 500 most recent.

One caveat on `/reports/financial`: the **payment methods** panel is a single
row labelled *All Payments* at 100%. It is not a real breakdown by method — the
query aggregates every paid and partial invoice into one group. For a genuine
split, read the payments themselves.

*Source: `blueprints/reports/routes.py:20-33`, `:35-65`, `:66-95`, `:96-147`,
`:201-269`, `:270-331`, `:332-359`*

## 13:00 — Somebody changed something

`/system/audit` — the audit log, open to super admin, clinic owner, support
admin and auditor. Logins, failed logins, module opens, record creates and
updates, role assignments, backups, 2FA changes. Role edits record the
permission list before and after, not just "role updated".

*Source: `blueprints/system/routes.py:234-326`, `:886-897`*

## 15:00 — A new nurse starts Monday

1. `/hr/staff` → **+ New Staff / موظف جديد**. Username, a 12-character password,
   role `nurse`, branch, shift.
2. `/system/roles` → **Staff Access / صلاحيات الموظفين** to change a role later.
3. If the default grants are wrong for how this clinic works, edit the role
   under **Custom Roles** — that is the copy the permission check reads. The
   built-in cards higher up the page are a hardcoded display and say plainly
   that they cannot be modified.

*Source: `blueprints/hr/routes.py:581-644`; `blueprints/system/routes.py:856-901`,
`:920-967`; `templates/system/roles.html:147-249`*

## 18:30 — Close the day

`/accounting/closing` — **Daily Closing**. Cash in (payments received today),
cash out (expenses dated today), the net, transaction counts, and a free-text
closing note kept with the last seven days' notes.

Be clear about what this is: **a record of the count, not a till close.** No
period is locked, no float is reconciled, and nothing stops the day being edited
afterwards.

*Source: `blueprints/accounting/routes.py:458-538`*

## Once a month

- `/system/export/all` — the clinic's whole record set in one file, so the data
  is provably hers.
- `/system/diagnostics` and `/system/monitor` — is the machine healthy.
- Check `/auth/2fa/admin` — who has two-step verification on, and who does not.

*Source: `blueprints/system/routes.py:578-662`, `:1012-1065`;
`blueprints/auth/routes.py:827-831`*

**Deeper:** [`../manual/finance.md`](../manual/finance.md) ·
[`../manual/insights.md`](../manual/insights.md) ·
[`../manual/system.md`](../manual/system.md) ·
[`../workflows/system.md`](../workflows/system.md)

---

## What none of these three can do today

Written here so nobody plans a day around it.

- **Nothing can be deleted from the CRM.** There is no delete route for a client
  or a pet on any screen. A record created in error can only be edited.
  *Source: `blueprints/crm/routes.py` — no delete route exists*
- **Reception cannot open New Visit** without a permission change. See above.
- **Loyalty points redeem to nothing.** The redeem button deducts points and
  writes a ledger row saying a credit was created; no credit note, invoice
  adjustment or account credit is created anywhere in Finance. Apply it by hand.
  *Source: `blueprints/crm/routes.py:446-489`*
- **Daily Closing locks nothing.** See above.
- **The payment-method breakdown on `/reports/financial` is one fake row.** See
  above.

More, per module, at the end of each chapter in [`../manual/`](../manual/).
