# Aleefy — User Guide / دليل المستخدم

The friendly front door. Short answers to "how do I…", with a link into the
long books when you need the detail.

There are three books:

| Book | What it is | When to open it |
|---|---|---|
| **Guide** (you are here) | Shortest path to the twenty things people actually do | Every day |
| [`../manual/`](../manual/) | Reference — every screen, every field, every button | "What does this field do?" |
| [`../workflows/`](../workflows/) | The workflow book — a whole job end to end, with edge cases | "Walk me through it, including what goes wrong" |

Everything below was checked against the source. Where a screen does something
other than what it looks like it does, it is written down here rather than
smoothed over — see **[Known limits](#known-limits-read-this-before-you-report-a-bug)**.

**Start here if you are new:**

- **[Getting started](getting-started.md)** — first-time setup, in the order it has to happen.
- **[A day in the life](day-in-the-life.md)** — receptionist, vet, owner.

---

## 1. Signing in

Go to `/auth/login`. Type your username and password, press
**Sign In / تسجيل الدخول**.

Two buttons sit above the form: **EN** and **عربي** pick the language, and the
🌓 button switches light/dark. Both are remembered for your session.

If your account has two-step verification on, the password takes you to
`/auth/2fa` for a 6-digit code — not to the dashboard. A backup code works
there too, and using one tells you how many you have left.

*Source: `blueprints/auth/routes.py:533-616` (login), `:616-685` (2FA),
`templates/login.html:715-795`*

## 2. Finding your way around

- **Home dashboard** — `/`. Every module you are allowed to see, grouped into
  Clinical, Operations, Inventory, Commercial, Finance, Communication,
  Workspaces, Intelligence, Admin, System — plus today's counts (owners, pets,
  bookings today, revenue today, visits today, unpaid invoices, outstanding).
- **Left sidebar** — the same places, in groups: CLINIC / العيادة,
  CLINICAL / السريري, BUSINESS / الأعمال, TEAM / الفريق (managers only),
  PLATFORM / المنصة, SYSTEM / النظام (owner, super admin, support admin only).
- **Ctrl + K** anywhere opens the command palette. So does clicking the topbar
  search box and pressing Enter or `/`.

*Source: `blueprints/launcher/routes.py:599-639`, `:22-556` (the module list),
`templates/base.html:96-325` (sidebar), `:1241-1262` (Ctrl+K)*

> The topbar box says *Search patients, appointments… / ابحث عن مرضى، مواعيد…*
> but it does **not** search records. Enter opens the AI command palette, which
> sends your text to `/ai/chat`. To find a client, use **Pets & Owners /
> الملاك والحيوانات** (`/crm/owners`). *Source: `templates/base.html:1241-1284`*

---

## 3. The twenty most common tasks

Shortest path to each. "→" means click that.

### Front desk

**1 · Register a new client**
`/crm/owners` → **➕ New Owner / مالك جديد**. Only **Full name** is required. A phone number
already on file is refused with the name of the client who has it.
*Source: `blueprints/crm/routes.py:245-313`*

**2 · Add a pet to a client**
Open the client at `/crm/owners/<id>` → **🐾 Add Pet / إضافة حيوان** on their profile. Do **not**
use the New Pet button on the all-pets grid — it has no client attached and
bounces you back (see Known limits #2).
*Source: `blueprints/crm/routes.py:686-762`*

**3 · Book an appointment**
`/appointments/new` → pick client, then pet, then date, time, doctor, duration.
The pet must belong to the client you picked or the save is refused.
*Source: `blueprints/appointments/routes.py:272-393`*

**4 · Check a client in when they arrive**
`/appointments/reception` (Reception Workspace) or the appointment itself →
set status to **Checked-in**. Valid statuses are Scheduled, Confirmed,
Checked-in, Completed, Cancelled, No-Show.
*Source: `blueprints/appointments/routes.py:40`, `:428-455`, `:559-610`*

**5 · Handle a walk-in with no appointment**
`/workflow/` — **New Visit / زيارة جديدة**. Six steps across one page:
Client / العميل → Patient / الحيوان → Examination / الفحص →
Diagnosis / التشخيص → Treatment / العلاج → Invoice & Payment / الفاتورة والدفع.
Each step posts to the same routes the normal screens use, then re-reads the
visit from the server before moving on.
*Source: `blueprints/workflow/routes.py:36-56`,
`templates/workflow/index.html:427-742`*

**6 · Put the queue on the waiting-room TV**
`/appointments/waiting-room`, opened once with `?t=<WAITING_ROOM_TOKEN>`; the
token is then stored in a cookie for a year. Client names are shortened to
"Ahmed E." on the public display. With no token configured the page returns 404
to anyone not signed in.
*Source: `blueprints/appointments/routes.py:723-841`*

### Clinical

**7 · Run a whole consultation on one screen (Hatem Way / طريقة حاتم)**
`/visits/exam` → search the client by phone or name → pick the pet. Fill
**This visit / هذه الزيارة** (weight, temp, visit date, seen-by), the
symptom and diagnosis, add services in **Services and items / الخدمات
والأصناف**, take the money in **Payment / الدفع**, then
**Save visit / حفظ الكشف** or **Save and print / حفظ وطباعة**.

One submit writes the visit, the diagnosis, any vaccinations recorded, any
prescription, a follow-up appointment if you set a date, the invoice, and the
payment. Cash handed over above the bill is shown as **Change / الباقي**, not
banked; anything short is **Due / المتبقي**.
*Source: `blueprints/visits/routes.py:691-715`, `:827-849`, `:1301-1537`;
`templates/visits/exam.html`*

**8 · Open a long-form visit instead**
`/visits/new` → the full form. `/visits/<id>` is where SOAP, diagnoses,
treatment plan and prescriptions are added afterwards, one section at a time.
*Source: `blueprints/visits/routes.py:67-236`, `:237-464`*

**9 · Write a prescription**
On the exam screen, open **Prescription / الروشتة** and add rows. On a
long-form visit, use the prescription block on `/visits/<id>`. The prescriber
is the doctor **named on the visit**, not whoever is logged in.
*Source: `blueprints/visits/routes.py:355-431`, `:1414-1439`*

**10 · Record a vaccination so the reminder fires**
On the exam screen, open **Vaccination given today / تطعيم أُعطي اليوم** and
fill vaccine, brand, batch, next due. Or use `/clinical/vaccinations/new`.
Billing a vaccine as a service does **not** record it — only this sets the next
due date the reminder reads.
*Source: `blueprints/visits/routes.py:1364-1387`;
`blueprints/clinical/routes.py:251-319`*

**11 · Request a lab test and enter the result**
`/clinical/lab/new` to raise it, `/clinical/lab/<id>` to enter results.
*Source: `blueprints/clinical/routes.py:93-227`*

**12 · Hand the owner a medical history**
Pet record `/crm/pets/<id>` → **📄 Medical History PDF / السجل الطبي PDF**
(`/crm/pets/<id>/history.pdf`).
*Source: `blueprints/crm/routes.py:896-1052`*

### Money

**13 · Raise an invoice by hand**
`/finance/invoices/new` → pick the client (required), optionally the pet, add at
least one line. A line with quantity 0 or a negative price is dropped, not
billed. Per-line discount is a percentage, clamped 0–100.
*Source: `blueprints/finance/routes.py:206-317`*

**14 · Take a payment**
`/finance/invoices/<id>` → **✅ Record Payment / تسجيل الدفع**. Amount, method, reference.
A typo in the amount is refused with a message, never coerced to zero. Paying
awards loyalty points (1 point per 10 EGP). Double-clicking cannot charge twice.
*Source: `blueprints/finance/routes.py:368-430`*

**15 · Get the bill to the client**
From the invoice: **🖨 Print / طباعة**, **⬇ Download PDF / تحميل PDF**, or
**📱 Send WhatsApp / إرسال** — which needs a phone on the client record, and
reports "WhatsApp queued / failed — check message log" if the send did not
confirm.
*Source: `blueprints/finance/routes.py:663-752`*

**16 · Quote before you treat**
`/finance/estimates/new` → `/finance/estimates/<id>` to approve or decline. The
**🧾 Convert to invoice / تحويل إلى فاتورة** button only appears once the
estimate's status is **Approved**.
*Source: `blueprints/finance/routes.py:1003-1111`*

**17 · Record what the clinic spent**
`/finance/expenses` or `/accounting/expenses`. Both are restricted to
super admin, clinic owner, branch manager, finance and auditor — reception
cannot see them.
*Source: `blueprints/finance/routes.py:766-768`;
`blueprints/accounting/routes.py:316-457`*

**18 · Close the day**
`/accounting/closing`. It shows today's cash in (payments received today),
cash out (expenses dated today), the net, and lets you save a closing note.
It does not lock anything — it is a record of the count, not a till close.
*Source: `blueprints/accounting/routes.py:458-538`*

### Stock and retail

**19 · Dispense a prescription**
`/pharmacy/` is the queue of everything not fully dispensed. Open the
prescription → pick a batch per line → **💊 Dispense Selected / صرف المحدد**. An expired batch is
refused by name and date. A medication typed as free text (not a stock item) is
marked dispensed and written to the audit log, but no stock moves — there is no
stock record to move.
*Source: `blueprints/pharmacy/routes.py:18-44`, `:127-282`*

**20 · Sell something over the counter**
`/petshop/pos` → only products that are active **and** have stock above zero
appear. Cash asks for the amount tendered and gives change; Card, Transfer and
Instapay are booked as paid in full. Stock is deducted only if it is actually
there — a sale of the last unit from two tills fails on the second.
*Source: `blueprints/petshop/routes.py:439-455`, `:457-560`*

**Bonus · Receive a delivery** — `/inventory/batches/new?item_id=<id>`: batch
number, expiry, quantity, unit cost, warehouse.
*Source: `blueprints/inventory/routes.py:391-473`*

**Bonus · See what is running out** — `/inventory/alerts`.
*Source: `blueprints/inventory/routes.py:475-502`*

---

## 4. Troubleshooting — what people actually get stuck on

### "You don't have permission to access this page."

Two gates, and both must pass. The **module grant** decides which modules your
role may enter at all; a **role list** on some individual routes decides who may
do a particular thing inside a module. A grant can only narrow, never widen.

Out of the box:

| Role | Modules granted by default |
|---|---|
| `clinic_owner` | everything |
| `branch_manager` | patients, appointments, visits, pharmacy, invoicing, inventory, procurement, reports, whatsapp, catalog, grooming, boarding, attendance, accounting, inpatient, telemedicine, imaging, petshop |
| `doctor` | patients, appointments, visits, pharmacy, reports, catalog, inpatient, telemedicine, imaging, ai, attendance |
| `nurse` | patients, appointments, visits, pharmacy, inpatient, imaging, attendance |
| `reception` | patients, appointments, invoicing, catalog, whatsapp, grooming, boarding, petshop, attendance |
| `pharmacist` | pharmacy, inventory, patients, visits, attendance |
| `inventory_mgr` | inventory, procurement, petshop, reports, attendance |
| `finance` | invoicing, accounting, reports, payroll |
| `hr` | hr, attendance, payroll |
| `groomer` | grooming, appointments, patients, attendance |
| `boarding_staff` | boarding, appointments, patients, attendance |
| `support_admin` | system, backup, audit, settings |
| `auditor` | reports, audit, accounting |

`super_admin` bypasses the grant check entirely.

**Fix:** an owner or super admin opens `/system/roles`, finds the role under
**Custom Roles**, ticks the module, saves. See Known limits #4 for why it is
under "Custom Roles" and not under the built-in card of the same name.

*Source: `blueprints/auth/routes.py:89-190`; `models/database.py:4302-4379`*

### The sidebar shows me a page I cannot open

Correct, and expected. Only the TEAM and SYSTEM sidebar groups are hidden by
role. CLINIC, CLINICAL, BUSINESS and PLATFORM are drawn for everyone, so a
receptionist sees **New Visit / زيارة جديدة** and **Medical Visits / الفحوصات**
and is bounced when she clicks them.
*Source: `templates/base.html:98-290`*

### "Owner ID is required to create a pet."

You used the **New Pet** button on `/crm/pets`. That link carries no client.
Open the client first (`/crm/owners/<id>`) and add the pet from their profile.
*Source: `blueprints/crm/routes.py:689-692`; `templates/crm/pets_list.html:10`, `:98`*

### "Too many failed attempts. Try again in N minute(s)."

Five failed attempts within 15 minutes locks that IP **and** that username for
15 minutes. It clears itself; there is no unlock button. The 2FA code step has
its own separate five-try counter.
*Source: `models/security.py:38-40`, `:194-220`*

### "Password must be at least 12 characters."

Every password path enforces the same rule: 12+ characters, at least one
uppercase, one lowercase, one digit, one special character — even where the box
says "min 6 chars" (the Reset Password field on the staff record does).
*Source: `models/security.py:346-366`; `blueprints/hr/routes.py:545-552`,
`:861-865`; `templates/hr/staff_detail.html:127`*

### How do I change my own password?

`/hr/staff` → your own record → **Reset Password / إعادة تعيين كلمة المرور**.
There is no change-password form on `/auth/profile` — that page carries theme,
language and two-step verification only. The reset route is limited to super
admin, clinic owner and support admin, so everyone else has to ask one of them.
*Source: `templates/profile.html:17-194`; `blueprints/hr/routes.py:852-880`*

### I was signed out in the middle of something

Idle timeout is one hour of no requests; the session cookie itself lasts 24
hours. Sign in again — nothing already saved is lost.
*Source: `models/security.py:40`, `:291-302`; `config.py:120`*

### "Your sign-in request expired. Please log in again."

You sat on the 2FA screen too long. The half-login is parked for a short window
and then dropped. Start at `/auth/login` again.
*Source: `blueprints/auth/routes.py:625-631`*

### I lost my phone and cannot pass 2FA

Use a backup code on the same screen. If they are gone, an owner or super admin
resets your enrolment at `/auth/2fa/admin` — every reset is audit-logged.
Afterwards, enrol again at `/auth/profile` and print the new backup codes; they
are shown once and never again.
*Source: `blueprints/auth/routes.py:733-757`, `:827-878`*

### "Maintenance in progress… The system will be back in a few minutes." (503)

A database restore set a maintenance marker and it was not cleared — usually a
restore that crashed. The marker self-expires, but an owner or super admin can
clear it now: `/system/backup` → **Clear maintenance**
(`POST /system/backup/maintenance/off`). `/auth/*`, `/static/*` and
`/system/backup*` stay reachable while it is set, which is how you get in.
*Source: `blueprints/system/routes.py:34-67`, `:566-576`*

### "Your account has no role assigned, or its role is not recognised."

The dashboard is empty because your role matched nothing. A role that is not in
the built-in list and has no row in the `roles` table is denied everywhere —
this happens when a custom role was deleted while staff still held it. An
administrator reassigns you at `/system/roles` → **Staff Access / صلاحيات
الموظفين**.
*Source: `blueprints/launcher/routes.py:574-580`, `:606-611`;
`blueprints/auth/routes.py:113-129`*

### "There is no role called 'x'. Pick one that exists, or create it first."

Assigning a role that is neither built-in nor in the `roles` table is refused at
the point of assignment rather than silently locking the person out.
*Source: `blueprints/system/routes.py:933-944`*

### The clinic name I saved is not showing

It caches for five minutes, but saving the settings form clears the cache
immediately. If it still shows the old name, you saved on a different clinic
(check the address bar) — or the logo upload was rejected and the whole save was
abandoned, in which case you got a red message naming the reason.
*Source: `blueprints/system/routes.py:328-352`, `:390-393`*

### The waiting-room TV shows nothing / 404

Two different faults. **404 to a visitor** means `WAITING_ROOM_TOKEN` is not
configured, or the URL is missing `?t=<token>` — the display fails closed on
purpose. **Signed in but the list is empty** means nothing today is Scheduled,
Confirmed or Checked-in.
*Source: `blueprints/appointments/routes.py:728-756`, `:769-780`*

### An appointment exists but I cannot see it on the schedule

Both the day schedule and the Reception Workspace build rows for 08:00–20:59
only, and drop anything outside. The **Total** tile still counts it, so the tile
and the rows disagree. You cannot create one through the booking form; imported
or API-created bookings can land there.
*Source: `blueprints/appointments/routes.py:179-189`, `:580-590`*

### A prescription will not leave the queue

`/pharmacy/` lists everything whose status is not `Dispensed`. If some lines are
dispensed and some are not, it stays. Open it and dispense the rest, or check
whether a line's batch was refused for being expired.
*Source: `blueprints/pharmacy/routes.py:18-44`, `:127-282`*

### The POS will not show a product

It only lists products that are `is_active = 1` **and** `stock_qty > 0`. Receive
the stock (`/petshop/products/<id>/stock`) or re-activate the product.
*Source: `blueprints/petshop/routes.py:439-455`*

### The doctor's queue is empty

`/doctor/` filters today's appointments to those whose `doctor_name` contains
your full name. Managers and owners see everybody's. If your staff record's full
name does not match what is typed on the appointment, nothing shows.
*Source: `blueprints/doctor/routes.py:20-56`*

---

## Known limits (read this before you report a bug)

These are real behaviours of the code as it stands, verified in the source. They
are listed here so following this guide never leaves you arguing with the
screen.

1. **The topbar search box does not search.** It opens the AI command palette
   and sends your text to `/ai/chat`. Use `/crm/owners` to find a client.
   *Source: `templates/base.html:1241-1284`*

2. **The New Pet button on `/crm/pets` is broken.** It links to `/crm/pets/new`
   with no `owner_id`, and that route requires one, so it flashes *"Owner ID is
   required to create a pet."* and returns you to the owners list. The
   empty-state button has the same fault.
   *Source: `templates/crm/pets_list.html:10`, `:98`;
   `blueprints/crm/routes.py:689-692`*

3. **Reception cannot open New Visit.** `/workflow/` is governed by the `visits`
   grant, which the default `reception` role does not hold — even though the
   sidebar puts **New Visit / زيارة جديدة** second precisely because it is meant
   to be reception's most-used screen. Granting `visits` to reception also opens
   the whole visits and clinical modules to them.
   *Source: `blueprints/auth/routes.py:140-152`;
   `models/database.py:4365-4367`; `templates/base.html:113-118`*

4. **The Roles screen lists every role twice, and only one copy is real.** The
   cards under Management / Clinical / Front Desk etc. are drawn from a
   hardcoded display list and are marked *"System roles are enforced in code and
   cannot be modified."* The **Custom Roles** section below lists the same roles
   again from the database — and those rows are the ones the permission check
   actually reads, and the ones you can edit. The two lists do not agree: the
   built-in card for `reception`, for example, shows four modules while the
   enforced grant has nine.
   *Source: `blueprints/system/routes.py:771-783` (display map) vs
   `models/database.py:4346-4379` (enforced); `templates/system/roles.html:147-249`*

5. **A role cannot be emptied.** Saving a role with no modules ticked is
   refused, because an empty grant is read as "no data — fall back to the
   built-in list", which would widen the role instead of narrowing it. To stop a
   role being used, move its staff off it and delete it.
   *Source: `blueprints/system/routes.py:881-884`*

6. **The HR staff form cannot assign the HR Officer role.** `hr` is a seeded
   role (HR Officer / موظف الموارد البشرية) with its own grants, but the role
   dropdown on `/hr/staff/new` does not list it. Assign it from
   `/system/roles` → **Staff Access**, which does.
   *Source: `blueprints/hr/routes.py:20-24` vs `models/database.py:2445`;
   `templates/system/roles.html:472-474`*

7. **Daily Closing does not close anything.** It totals today's payments and
   expenses and stores a free-text note. No period is locked, no till is
   reconciled against a counted float, and nothing prevents later edits to the
   day.
   *Source: `blueprints/accounting/routes.py:458-538`*

8. **The WhatsApp invoice message is hardcoded to "Aleefy" and EGP.** It does
   not read the clinic name or the configured currency from settings.
   *Source: `blueprints/finance/routes.py:713-735`*

9. **Free-text medications leave no stock trail.** Dispensing a medication the
   vet typed by name rather than picking from stock marks the line dispensed and
   writes an audit entry, but records no stock movement — because the drug is
   not in inventory and has no movement to record.
   *Source: `blueprints/pharmacy/routes.py:154-181`*

10. **`/reports/*` carries no role gate of its own.** The launcher card is
    restricted, and the module grant `reports` still applies at the blueprint
    level, but there is no additional role list on the individual report routes
    the way there is on `/finance/expenses` and `/finance/reports`.
    *Source: `blueprints/reports/routes.py:14-33` vs
    `blueprints/finance/routes.py:766-768`, `:846-848`*

11. **`/auth/profile` has no change-password form.** The route accepts
    `action=change_password` and would do the right thing with it, but nothing
    on the page posts it. Passwords are changed through `/hr/staff/<id>` →
    **Reset Password**, which only super admin, clinic owner and support admin
    can reach — so a nurse cannot change her own password at all.
    *Source: `blueprints/auth/routes.py:705-730` vs `templates/profile.html:17-194`;
    `blueprints/hr/routes.py:852-854`*

12. **The Reset Password box asks for six characters and the server demands
    twelve.** The input says *"New password (min 6 chars) / كلمة مرور جديدة (6
    أحرف على الأقل)"* with `minlength="6"`, then the save is refused with
    *"Password must be at least 12 characters."*
    *Source: `templates/hr/staff_detail.html:127` vs
    `blueprints/hr/routes.py:861-865`*

The per-module Known limits lists are longer and more specific. See the end of
each chapter in [`../manual/`](../manual/) and
[`../workflows/`](../workflows/).

---

## Where to go next

| I want to… | Go to |
|---|---|
| Set up a brand-new clinic | [getting-started.md](getting-started.md) |
| See how a day actually runs | [day-in-the-life.md](day-in-the-life.md) |
| Know what a specific field does | [`../manual/`](../manual/) — frontdesk, clinical, finance, pharmacy, services, petshop, insights, system |
| Do a whole job end to end, edge cases included | [`../workflows/`](../workflows/) |
| Install, provision or upgrade a clinic | [`../../PROVISIONING.md`](../../PROVISIONING.md) |
