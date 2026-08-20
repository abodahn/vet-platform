# Grooming, Boarding, Inpatient, Telemedicine, Lab & Imaging — Reference Manual

**Modules covered:** Grooming / التجميل · Boarding / الإيواء · Inpatient / التنويم ·
Telemedicine / الاستشارة عن بُعد · Laboratory / المختبر · Medical Imaging / التصوير الطبي

This chapter is a **screen-by-screen reference**, organised by screen rather than
by task. For each screen it gives: what the screen is for, how to reach it, which
roles can open it, every field and control with what it does and whether it is
required, every button and its effect, what the list columns mean, and the
filters.

Every statement here was checked against the route function and the template that
renders it. Where a control exists on screen but does nothing, or does something
other than its label says, it is described in that module's **Known limits**
section rather than written up as a working feature. Each screen carries a
`Source:` line with `file:line` so the next writer can verify it.

---

## 0. Modules at a glance

| Module | URL prefix | Blueprint | Permission key |
|---|---|---|---|
| Grooming / التجميل | `/grooming/` | `grooming` | `grooming` |
| Boarding / الإيواء | `/boarding/` | `boarding` | `boarding` |
| Inpatient / التنويم | `/inpatient/` | `inpatient` | `inpatient` |
| Telemedicine / الاستشارة عن بُعد | `/telemedicine/` | `telemedicine` | `telemedicine` |
| Laboratory / المختبر | `/clinical/lab` | `clinical` | `visits` |
| Medical Imaging / التصوير الطبي | `/imaging/` | `imaging` | `imaging` |

Note that the Lab screens live inside the **clinical** blueprint, which is
governed by the **`visits`** grant, not by a grant of its own. There is no "lab"
permission key.

> Source: `platform/app.py:222-281` (blueprint registration),
> `platform/blueprints/grooming/__init__.py:1-3`,
> `platform/blueprints/boarding/__init__.py:1-3`,
> `platform/blueprints/inpatient/__init__.py:1-3`,
> `platform/blueprints/telemedicine/__init__.py:1-3`,
> `platform/blueprints/imaging/__init__.py:1-5`,
> `platform/blueprints/clinical/__init__.py:1-5`,
> `platform/blueprints/auth/routes.py:139-152` (`_BP_PERMISSION`, maps
> `clinical` → `visits`)

---

## 1. Getting into these modules

There are two doors into every one of these modules: the left sidebar, and the
launcher cards on the home page.

### Sidebar → CLINICAL / السريري

| Sidebar entry | Goes to |
|---|---|
| **Lab & Vaccines / المختبر والتطعيمات** | `/clinical/lab` |
| **Inpatient / تنويم** | `/inpatient/` |
| **Grooming / التجميل** | `/grooming/` |
| **Boarding / الإيواء** | `/boarding/` |
| **Telemedicine / الاستشارة عن بُعد** | `/telemedicine/` |
| **Imaging / التصوير الطبي** | `/imaging/` |
| **AI Photo Analyzer / محلل الصور AI** | `/imaging/analyzer` |

All seven links sit in the CLINICAL group — including Grooming and Boarding,
which are operational rather than clinical. **None of the sidebar links carries a
role condition**: every signed-in user sees all seven. A user whose role does not
hold the module grant will see the link, click it, and be bounced to the launcher
with *"You don't have permission to access this page."*

> Source: `platform/templates/base.html:137-179` (CLINICAL nav group, no role
> guard anywhere in it)

### Launcher cards

The launcher home page shows a card per module, grouped by category. Clicking a
card opens the module's `url` directly.

| Card | Category | URL | Status badge |
|---|---|---|---|
| 🔬 Laboratory & Diagnostics / المختبر والتشخيص | Clinical | `/clinical/lab` | Live |
| 🩻 Medical Imaging / التصوير الطبي | Clinical | `/imaging/` | Live |
| 🏥 Inpatient & Hospitalisation / القسم الداخلي والتنويم | Clinical | `/inpatient/` | Live |
| 📹 Telemedicine / الطب عن بُعد | Clinical | `/telemedicine/` | Live |
| ✂️ Grooming / التجميل | Operations | `/grooming/` | Live |
| 🏨 Boarding / Pet Hotel / إيواء الحيوانات | Operations | `/boarding/` | Live |

Unlike the sidebar, launcher cards **are** filtered by role — but by a *separate*
list held on each card, not by the permission grant. The two lists do not always
agree; see §2.

> Source: `platform/blueprints/launcher/routes.py:62-76` (lab), `:139-153`
> (imaging), `:154-168` (inpatient), `:184-199` (telemedicine), `:200-214`
> (grooming), `:215-229` (boarding), `:572-579` (`_visible_modules`, the card
> filter), `platform/templates/launcher.html:600-628` (card links to `mod.url`)

---

## 2. Who can open what

Two independent gates apply to every screen in this chapter, and **both must
pass**:

1. **The module grant.** The role must hold the module's permission key. This is
   enforced for *every* route in the blueprint, including routes that declare no
   role list of their own. `super_admin` bypasses it entirely.
2. **The route's own role list**, where one is declared with `@role_required`.
   A grant can only ever *narrow* — it never widens a route's role list.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-133` (`_permission_denied`, the module gate), `:167-194`
> (`role_required`), `platform/models/database.py:4302-4331`
> (`ALL_PERMISSIONS`), `:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

### Which roles hold each grant out of the box

| Grant | Roles holding it by default |
|---|---|
| `grooming` | clinic_owner, branch_manager, reception, groomer |
| `boarding` | clinic_owner, branch_manager, reception, boarding_staff |
| `inpatient` | clinic_owner, branch_manager, doctor, nurse |
| `telemedicine` | clinic_owner, branch_manager, doctor |
| `imaging` | clinic_owner, branch_manager, doctor, nurse |
| `visits` (governs Lab) | clinic_owner, branch_manager, doctor, nurse, pharmacist |

`super_admin` is absent from the table deliberately: it bypasses both gates.
These lists are a **starting point** that an administrator edits on the Roles
screen — a clinic that has changed its role permissions will not match this
table.

### Effective access, per screen

Only routes that carry their own `@role_required` list are shown with a narrower
answer; everything else is "whoever holds the grant".

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| All Grooming screens | `/grooming/…` | none (login only) | super_admin, clinic_owner, branch_manager, reception, groomer |
| All Boarding screens | `/boarding/…` | none | super_admin, clinic_owner, branch_manager, reception, boarding_staff |
| Inpatient ward dashboard | `GET /inpatient/` | none | super_admin, clinic_owner, branch_manager, doctor, nurse |
| Inpatient stay detail | `GET /inpatient/<id>` | none | same as above |
| Admit patient | `GET/POST /inpatient/admit` | super_admin, clinic_owner, branch_manager, doctor, nurse | same as above |
| Update stay status | `POST /inpatient/<id>/status` | same | same |
| Record a round | `POST /inpatient/<id>/round` | same | same |
| Record a medication | `POST /inpatient/<id>/med` | + pharmacist | super_admin, clinic_owner, branch_manager, doctor, nurse — **not** pharmacist |
| Discharge | `POST /inpatient/<id>/discharge` | super_admin, clinic_owner, branch_manager, doctor | those four only — **a nurse cannot discharge** |
| All Telemedicine screens | `/telemedicine/…` | none | super_admin, clinic_owner, branch_manager, doctor |
| All Lab screens | `/clinical/lab…` | none | super_admin, clinic_owner, branch_manager, doctor, nurse, pharmacist |
| All Imaging screens | `/imaging/…` | none | super_admin, clinic_owner, branch_manager, doctor, nurse |

Two consequences worth knowing:

- **`add_med` names `pharmacist` in its role list, but a pharmacist does not hold
  the `inpatient` grant**, so the module gate stops them before the role list is
  ever consulted. The pharmacist entry on that route has no effect today.
- **The Telemedicine launcher card is shown to `nurse` and `reception`**, but
  neither role holds the `telemedicine` grant. Both will see the card, click it,
  and be bounced back to the launcher.

> Source: `platform/blueprints/inpatient/routes.py:187`, `:292`, `:313`,
> `:350-351`, `:380`, `platform/blueprints/launcher/routes.py:193`
> (telemedicine card roles), `platform/models/database.py:4359-4375`

---

## 3. Conventions shared by these screens

These apply on more than one screen, so they are described once here.

**Owner picker.** Every screen that asks for an owner (`Grooming → New Booking`,
`Boarding → New Booking`, `Inpatient → Admit`, `Telemedicine → New Session`)
renders an **empty** `<select>` plus a *"Type to search… / اكتب للبحث…"* text box
above it, inserted by JavaScript. Type **two or more characters** and the box
queries the server; the dropdown is repopulated with up to 25 matching owners
(name and phone). Fewer than two characters does nothing. If exactly one owner
matches, it is selected automatically and the page's own "load pets" handler
fires as if you had picked it by hand. The owner list is never rendered into the
page, so no client is ever out of reach because the clinic has too many.

> Source: `platform/static/js/platform.js:380-475` (searchable select),
> `platform/blueprints/crm/routes.py:543-560` (`owner_search_json`, returns 25
> matches, minimum 2 characters)

**Pet dropdown.** After an owner is chosen, the pet dropdown is filled by a
background request. Each module uses its own endpoint:
`/crm/owners/<id>/pets-json` (Grooming, Boarding),
`/inpatient/api/owner/<id>/pets` (Inpatient),
`/telemedicine/api/pets/<id>` (Telemedicine). If the request fails the dropdown
shows *"Error loading"* and you cannot submit.

> Source: `platform/blueprints/crm/routes.py:536-540`,
> `platform/blueprints/inpatient/routes.py:398-407`,
> `platform/blueprints/telemedicine/routes.py:365-373`

**JavaScript is required to save anything.** Every non-GET request is checked for
a security token. Most forms in these six modules do **not** contain that token
in their HTML — it is added by JavaScript at the moment you press Submit. With
JavaScript disabled or blocked, every save, status change, check-in, check-out
and discharge in this chapter returns a 403 page reading *"Invalid or missing
security token."*

> Source: `platform/app.py:349-357` (CSRF enforced on every non-GET),
> `platform/models/security.py:261-283`,
> `platform/static/js/platform.js:129-146` (token injected on submit)

**Bilingual labels.** Labels are written `t('English', 'العربية')` and follow the
signed-in user's language. Where a label has no Arabic half in the source
(for example *"Booking Details"*, *"Check-in Date"*, *"Doctor Notes"*), it stays
English in the Arabic interface. This chapter gives both halves where the code
has both.

> Source: `platform/app.py:406-408` (`t()`)

**Money** is displayed and entered in EGP throughout. None of these screens
performs any tax or discount calculation of its own — that happens on the
invoice.

---

# A. Grooming / التجميل

`/grooming/` · blueprint `grooming` · grant `grooming`

Five screens: a dashboard, a bookings list, a new-booking form, an edit form, and
a service catalogue.

---

## A1. Grooming dashboard

**What it is for.** The day view: today's grooming appointments with a one-click
status change, and the next seven days below it.

**How to reach it.** Sidebar → CLINICAL → **Grooming / التجميل**; launcher card
**Grooming**; or the **Dashboard / لوحة التحكم** button on the bookings list.

**Who can open it.** super_admin, clinic_owner, branch_manager, reception,
groomer.

### Top bar

| Button | Effect |
|---|---|
| **+ New Booking / + حجز جديد** | Opens `/grooming/bookings/new` |
| **Services / الخدمات** | Opens `/grooming/services` |

### Stat cards

| Card | What it counts |
|---|---|
| **Today's Bookings** | Every booking whose date falls on today, **including cancelled ones** |
| **This Week / هذا الأسبوع** | Bookings from today to today + 7 days, excluding `Cancelled` |
| **In Progress / جارٍ** | Every booking with status `In Progress`, of any date |

### "📅 Today's Schedule" table

Rows are today's bookings, ordered by booking time.

| Column | Content |
|---|---|
| **Time / الوقت** | First 16 characters of the stored booking date (`YYYY-MM-DD HH:MM`) |
| **Pet / الحيوان** | Pet name, linked to the pet's medical record; species underneath |
| **Owner / المالك** | Owner name, linked to the owner record; phone underneath |
| **Service / الخدمة** | Name from the service catalogue, or `—` if no service was chosen |
| **Groomer / المُجمِّل** | Free-text groomer name, or `—` |
| **Duration / المدة** | Catalogue duration in minutes, or `—` |
| **Price / السعر** | **Catalogue** price of the service in EGP. This ignores any price override on the booking. |
| **Status / الحالة** | Badge: Scheduled (amber) · In Progress (blue) · Completed (green) · anything else red |
| *(last)* | Status dropdown + **✓** button |

The status dropdown offers `Scheduled`, `In Progress`, `Completed`, `Cancelled`.
Pressing **✓** submits that status (see A5). Choosing `Completed` here will raise
an invoice and take you to it.

If there are no bookings today the table shows *"No bookings today."*

### "📆 Upcoming (next 7 days)" table

Shown only when there is at least one upcoming booking. Up to 20 rows, excluding
cancelled ones. Columns: Date / Pet / Owner / Service / Status. Every status is
rendered with the amber "warning" badge here regardless of its actual value.
**View All / عرض الكل** opens the bookings list.

> Source: `platform/blueprints/grooming/routes.py:26-81`,
> `platform/templates/grooming/dashboard.html:1-107`

---

## A2. Grooming bookings list

**What it is for.** The full booking register with filters, and the row actions
that move a booking through its life cycle.

**How to reach it.** `/grooming/bookings` — from the dashboard's **View All**
link, or after saving any booking (every save redirects here).

**Who can open it.** Same as A1.

### Top bar

| Button | Effect |
|---|---|
| **+ New Booking / + حجز جديد** | Opens the new-booking form |
| **Dashboard / لوحة التحكم** | Back to `/grooming/` |

### Filters

| Control | Values | Effect |
|---|---|---|
| Status dropdown | `All`, `Scheduled`, `In Progress`, `Completed`, `Cancelled` | Exact match on the stored status. `All` applies no filter. |
| **date_from** (date box) | any date | Booking date on or after this date |
| **date_to** (date box) | any date | Booking date on or before this date |
| **Filter / تصفية** | — | Applies the filters (submits as a GET, so the filter is in the URL and can be bookmarked) |
| **Clear / مسح** | — | Returns to the unfiltered list |

Results are ordered newest booking date first and **capped at 200 rows**. There
is no paging and no "showing X of Y" indicator — a clinic with more than 200
matching bookings simply will not see the older ones.

### Columns

| Column | Content |
|---|---|
| **#** | Booking id |
| **Date / Time — التاريخ / الوقت** | First 16 characters of the booking date |
| **Pet / الحيوان** | Pet name linked to the medical record; species underneath |
| **Owner / المالك** | Owner name linked to the owner record; phone underneath |
| **Service / الخدمة** | Catalogue service name, or `—` |
| **Groomer / المُجمِّل** | Groomer name, or `—` |
| **Duration / المدة** | Catalogue duration in minutes |
| **Price / السعر** | Catalogue price in EGP — again, not the override |
| **Status / الحالة** | Coloured badge as on the dashboard |
| **Invoice / الفاتورة** | 🧾 #id linked to the invoice, or `—` when none has been raised |
| **Actions / إجراءات** | See below |

### Row actions

| Button | Shown when | Effect |
|---|---|---|
| **✏️ Edit / ✏️ تعديل** | always | Opens the edit form (A4) |
| **▶ Start / ▶ بدء** | status is `Scheduled` | Sets status to `In Progress` |
| **✅ Done / ✅ تم** | status is `Scheduled` or `In Progress` **and** no invoice yet | Asks *"Complete and generate invoice?"*, then completes the booking and raises the invoice (A5) |
| **🧾 Receipt / 🧾 إيصال** | an invoice exists | Opens the invoice |

Empty result: *"No bookings found. / لا توجد حجوزات."*

> Source: `platform/blueprints/grooming/routes.py:84-127`,
> `platform/templates/grooming/bookings_list.html:1-116`

---

## A3. New grooming booking

**What it is for.** Booking a grooming appointment for an existing owner and pet.

**How to reach it.** `/grooming/bookings/new` — the **+ New Booking** button on
the dashboard or the bookings list.

**Who can open it.** Same as A1.

### Card "Patient / المريض"

| Field | Required | Notes |
|---|---|---|
| **Owner * / المالك *** | **Yes** | Type-to-search picker (§3). Nothing is pre-loaded; you must type at least two characters. |
| **Pet * / الحيوان *** | **Yes** | Disabled until an owner is chosen; then filled from that owner's pets. |

### Card "Booking Details"

| Field | Required | Notes |
|---|---|---|
| **Service / الخدمة** | No | Lists only **active** catalogue services, showing name, species, duration and price. Default is *"— No specific service —"*, which stores no service, meaning no price and no duration anywhere afterwards. |
| **Groomer Name / اسم المُجمِّل** | No | Free text. Not validated against staff records. |
| **Booking Date & Time \*** | **Yes** | A date-and-time box. Enforced by both the browser and the server. |
| **Status / الحالة** | No | `Scheduled` / `In Progress` / `Completed`. Defaults to `Scheduled`. **See Known limits A8 — in the Arabic interface this box submits Arabic text.** |
| **Notes / ملاحظات** | No | Free text — special instructions, coat condition, owner requests. |

### Buttons

| Button | Effect |
|---|---|
| **Create Booking / إنشاء حجز** | Validates that owner, pet and date are all present. If any is missing: *"Owner, pet, and booking date are required."* and you are returned to a **blank** form. On success: *"Grooming booking created."* and you land on the bookings list. |
| **Cancel / إلغاء** | Returns to the bookings list without saving |

Creating a booking with status `Completed` from this form does **not** raise an
invoice — invoicing only happens through the status route (A5).

> Source: `platform/blueprints/grooming/routes.py:130-177`,
> `platform/templates/grooming/booking_form.html:1-87`

---

## A4. Edit grooming booking

**What it is for.** Changing the appointment details of an existing booking, and
completing or starting it.

**How to reach it.** `/grooming/bookings/<id>/edit` — the **✏️ Edit** button on
the bookings list. An unknown id flashes *"Booking not found."* and returns to
the list.

**Who can open it.** Same as A1.

### Card "Patient (read-only) / المريض (للقراءة فقط)"

Owner (with phone) and pet (with species), both as links to their records, plus a
button **🐾 Coat, temperament & allergies → / 🐾 الفراء والسلوك والحساسية ←** that
opens the pet record. **The owner and pet on a booking cannot be changed** — to
move a booking to a different animal, cancel it and create a new one.

### Card "Appointment Details / تفاصيل الموعد"

| Field | Required | Notes |
|---|---|---|
| **Service / الخدمة** | No | Same active-services list as A3, with the booking's current service pre-selected. Changing it copies the catalogue price into the Price Override box below (only when that price is non-zero). |
| **Price Override (EGP)** | No | A per-session price. Leave blank to bill the catalogue price. Accepts two decimals, minimum 0. Anything that is not a number is silently ignored and treated as "no override". **This box always renders empty — see Known limits A8.** |
| **Groomer Name / اسم المُجمِّل** | No | Free text |
| **Status / الحالة** | No | `Scheduled` / `In Progress` / `Completed` / `Cancelled` |
| **Date & Time \*** | **Yes** | Pre-filled with the current value. Clearing it and saving flashes *"Booking date is required."* and returns you to this form with nothing saved. |
| **Notes / ملاحظات** | No | Free text |

### Invoice banner

If the booking already has an invoice, a green-edged card appears reading
*"Invoice already generated / الفاتورة صادرة بالفعل"* with the invoice number and
a **View Invoice / Receipt** button.

### Buttons

| Button | Shown when | Effect |
|---|---|---|
| **💾 Save Changes / 💾 حفظ التغييرات** | always | Saves service, price override, groomer, status, date and notes. Flashes *"Grooming booking updated."* and returns to the bookings list. |
| **Cancel / إلغاء** | always | Back to the bookings list, nothing saved |
| **✅ Complete & Generate Invoice** | status is not `Completed`/`Cancelled` and no invoice exists | Confirms, then completes and invoices (A5). **This is a separate form — anything you typed in the fields above is discarded.** |
| **▶ Start Session** | status is `Scheduled` | Sets status to `In Progress`. Same caveat: unsaved edits are lost. |

> Source: `platform/blueprints/grooming/routes.py:180-247`,
> `platform/templates/grooming/booking_edit.html:1-137`

---

## A5. Change booking status (no screen of its own)

`POST /grooming/bookings/<id>/status` — the target of the **✓** button on the
dashboard, **▶ Start** and **✅ Done** on the list, and the two quick buttons on
the edit form.

Behaviour depends on the status being set:

- **Anything other than `Completed`** — the status is written and you are
  returned where you came from, with *"Booking status updated to X."*
- **`Completed`, and the booking has no invoice yet** — the system builds a
  one-line invoice for the owner and pet: description = the service name (or
  *"Grooming Service"* if none was chosen), quantity 1, unit price = **the price
  override if one is set, otherwise the catalogue price**. The invoice id is
  written back onto the booking, the status is set to `Completed`, and you are
  taken **straight to the invoice** with *"Grooming completed ✓ — Invoice #N
  generated."* If invoice creation fails, you get *"Booking completed but invoice
  creation failed: …"* and the booking is still marked `Completed`.
- **`Completed`, and the booking already has an invoice** — only the status is
  written. No second invoice is created and no message is shown.

A booking with no service and no override is invoiced at **0.00 EGP** — there is
no guard against it.

> Source: `platform/blueprints/grooming/routes.py:250-308`

---

## A6. Booking invoice shortcut

`GET /grooming/bookings/<id>/invoice` redirects to the booking's invoice. If the
booking has no invoice it flashes *"No invoice linked to this booking yet."* and
sends you back where you came from. **No screen in the Grooming module links to
this route** — the list and the edit form both link to the invoice directly. It
is reachable only by typing the URL.

> Source: `platform/blueprints/grooming/routes.py:311-323`

---

## A7. Grooming services / خدمات التجميل

**What it is for.** The catalogue of grooming services: what the clinic offers,
for which species, how long it takes and what it costs.

**How to reach it.** `/grooming/services` — the **Services / الخدمات** button on
the grooming dashboard.

**Who can open it.** Same as A1.

The screen is two panels side by side: the table on the left, one add/edit form
on the right.

### Services table

Shows **all** services, active and inactive, ordered by name.

| Column | Content |
|---|---|
| **Name / الاسم** | Service name |
| **Species / النوع** | `All`, `Dog`, `Cat`, `Bird`, `Rabbit` or `Other`. This is a label only — it does **not** filter which services appear when booking a dog versus a cat. |
| **Duration / المدة** | Minutes |
| **Price / السعر** | EGP, two decimals |
| **Active / نشط** | Green *Active / نشط* or red *Inactive / غير نشط*. Only active services appear in the booking dropdowns. |
| **Description / الوصف** | Truncated to one line |
| *(last)* | **Edit / تعديل** button — loads that row into the form on the right and renames the panel *"Edit Service #N"* |

Empty table: *"No services yet."*

### Add / Edit form

The same form does both. When the hidden service id is empty it inserts; when the
**Edit** button has filled it, it updates that service.

| Field | Required | Notes |
|---|---|---|
| **Service Name \*** | **Yes** | Empty name flashes *"Service name is required."* and nothing is saved |
| **Species / النوع** | No | Defaults to `All` |
| **Duration (min) / المدة (دقيقة)** | No | Minimum 5, default 60. Blank is stored as 60. |
| **Price (EGP)** | No | Two decimals, minimum 0, default 0. Blank is stored as 0. |
| **Description / الوصف** | No | Free text |
| **Active / نشط** | No | Checkbox, ticked by default. Unticking hides the service from booking dropdowns but keeps it in this table. |

| Button | Effect |
|---|---|
| **Save Service / حفظ الخدمة** | Inserts or updates; flashes *"Service added."* or *"Service updated."* and reloads the page |
| **Clear / مسح** | Resets the form back to "Add Service" mode. Does not touch the database. |

There is **no delete**. To retire a service, untick **Active**.

> Source: `platform/blueprints/grooming/routes.py:326-377`,
> `platform/templates/grooming/services.html:1-109`

---

## A8. Known limits — Grooming

1. **The Status dropdown on the New Booking form submits Arabic text when the
   interface is Arabic.** Its options carry no value attribute, so the browser
   sends the visible label. A booking created in Arabic is stored with status
   `مجدول`, which matches no filter, gets the red "unknown status" badge, and
   never shows a **Start** or **Done** button. Workaround: create the booking,
   then open **Edit** and set the status there — the edit form's dropdown does
   carry proper values.
   *(`templates/grooming/booking_form.html:52-56`)*

2. **The Price Override box on the edit form always renders empty.** It is filled
   from `booking.price`, a column that does not exist on the bookings table. The
   override you saved yesterday is stored and *is* used when invoicing, but the
   box shows blank when you reopen the booking — so re-saving the form without
   retyping it silently clears the override.
   *(`templates/grooming/booking_edit.html:59`,
   `models/database.py:1896-1911` — no `price` column)*

3. **The Price column on both the dashboard and the bookings list shows the
   catalogue price, never the override.** A booking discounted to 200 EGP still
   displays the catalogue 350 EGP everywhere except on the invoice.
   *(`routes.py:35-43`, `:92-101`)*

4. **The quick-action buttons on the edit form discard unsaved edits.** *Complete
   & Generate Invoice* and *Start Session* are separate forms; anything typed in
   the fields above is not submitted with them. Press **Save Changes** first.
   *(`templates/grooming/booking_edit.html:103-125`)*

5. **A failed create returns a blank form.** When owner, pet or date is missing
   the route redirects to a fresh form; everything typed is lost.
   *(`routes.py:163-166`)*

6. **A booking with no service and no override invoices at 0.00 EGP** with no
   warning. *(`routes.py:270-286`)*

7. **The list is capped at 200 rows with no paging and no warning.** Beyond that
   the oldest matching bookings are unreachable from this screen.
   *(`routes.py:116`)*

8. **No before/after photos, no product usage, no history timeline.** The
   launcher card advertises all three; the database has `before_photo` and
   `after_photo` columns, but no screen writes or displays them, and there is no
   product-usage or timeline screen at all.
   *(`blueprints/launcher/routes.py:205`, `models/database.py:1905-1906`)*

9. **The species on a service is decorative.** Booking a cat still offers
   dog-only services. *(`routes.py:137-139`)*

10. **A service cannot be deleted**, only deactivated. *(`routes.py:342-377`)*

11. **The invoice shortcut route `/grooming/bookings/<id>/invoice` is not linked
    from anywhere.** *(`routes.py:311-323`)*

---

# B. Boarding / الإيواء

`/boarding/` · blueprint `boarding` · grant `boarding`

Five screens: a room-occupancy dashboard, a bookings list, a new-booking form, an
edit form, and room management.

---

## B1. Boarding dashboard

**What it is for.** Which rooms are free right now and which are occupied, at a
glance.

**How to reach it.** Sidebar → CLINICAL → **Boarding / الإيواء**; launcher card
**Boarding / Pet Hotel**; or the **Dashboard / لوحة التحكم** button on the
bookings list.

**Who can open it.** super_admin, clinic_owner, branch_manager, reception,
boarding_staff.

### Top bar

| Button | Effect |
|---|---|
| **+ New Booking / + حجز جديد** | Opens `/boarding/bookings/new` |
| **Manage Rooms** | Opens `/boarding/rooms` |

### Stat cards

| Card | What it counts |
|---|---|
| **Total Rooms** | Active rooms only (inactive rooms are excluded from this whole screen) |
| **Occupied / مشغول** | Active rooms holding a booking with status `Checked-in` |
| **Available / متاح** | Total minus Occupied |
| **Checkout Today** | Bookings whose *expected* checkout date is today **and** whose status is still `Checked-in` |

### Room grid

One tile per active room, ordered by room name. A tile is **amber and labelled
OCCUPIED** when the room holds a `Checked-in` booking, and **green and labelled
FREE** otherwise.

Each tile shows: `Room <name>`, the room type and the nightly rate
(`<rate> EGP/day`). Occupied tiles also show the pet name (linked to its record),
the owner name (linked to theirs), and the check-in and expected-checkout dates.

Occupancy is decided by the **most recent** `Checked-in` booking for that room. A
room with two overlapping check-ins shows only one of them, and there is nothing
on this screen to say a room is double-booked.

**All Bookings → / عرض الكل** opens the bookings list. When no rooms exist at all
the grid reads *"No rooms configured yet. Add rooms →"*.

> Source: `platform/blueprints/boarding/routes.py:10-58`,
> `platform/templates/boarding/dashboard.html:1-72`

---

## B2. Boarding bookings list

**What it is for.** The stay register, and the check-in / check-out buttons.

**How to reach it.** `/boarding/bookings` — from the dashboard's **All Bookings**
link, or after saving any booking.

**Who can open it.** Same as B1.

### Filters

| Control | Values | Effect |
|---|---|---|
| Status dropdown | `All`, `Reserved`, `Checked-in`, `Checked-out`, `Cancelled` | Exact match on the stored status |
| **date_from** | date | Check-in date on or after |
| **date_to** | date | Check-in date on or before |
| **Filter / تصفية** | — | Applies (GET, bookmarkable) |
| **Clear / مسح** | — | Unfiltered list |

Ordered by check-in date, newest first, **capped at 100 rows**.

### Columns

| Column | Content |
|---|---|
| **#** | Booking id |
| **Pet / الحيوان** | Pet name linked to its record; species underneath |
| **Owner / المالك** | Owner name linked to their record; phone underneath as a clickable `tel:` link |
| **Room / الغرفة** | Room name, linked to that room's row on the Rooms screen; room type underneath. `—` when no room was assigned. |
| **Check-in** | Date only (first 10 characters) |
| **Expected Out** | Date only |
| **Rate/Day — السعر/اليوم** | The **room's current** nightly rate. This is looked up live, so changing a room's rate changes what every historic booking in this column appears to have cost. |
| **Status / الحالة** | Reserved (amber) · Checked-in (green) · Checked-out (grey) · anything else red |
| **Invoice / الفاتورة** | 🧾 #id linked to the invoice, or `—` |
| **Actions / إجراءات** | See below |

### Row actions

| Button | Shown when | Effect |
|---|---|---|
| **✏️ Edit / ✏️ تعديل** | always | Opens the edit form (B4) |
| **✅ Check In** | status is `Reserved` **or** `Booked` | Confirms *"Check in this pet now?"*, then sets status to `Checked-in` (B5) |
| **🚪 Check Out** | status is `Checked-in` | Confirms *"Check out and generate invoice?"*, then checks out and bills (B5) |
| **🧾 Receipt / 🧾 إيصال** | an invoice exists **and** status is `Checked-out` | Opens the invoice |

`Booked` is accepted by the Check In button because it is the database default
for the status column, even though no screen ever writes it and it is not in the
status filter list.

Empty result: *"No bookings found. / لا توجد حجوزات."*

> Source: `platform/blueprints/boarding/routes.py:61-111`,
> `platform/templates/boarding/bookings_list.html:1-111`,
> `platform/models/database.py:1931` (status default `Booked`)

---

## B3. New boarding booking

**What it is for.** Registering a pet hotel stay.

**How to reach it.** `/boarding/bookings/new` — **+ New Booking** on the
dashboard or the list.

**Who can open it.** Same as B1.

### Card "Patient / المريض"

| Field | Required | Notes |
|---|---|---|
| **Owner * / المالك *** | **Yes** | Type-to-search picker (§3) |
| **Pet * / الحيوان *** | **Yes** | Filled from the chosen owner |

### Card "Stay Details / تفاصيل الإقامة"

| Field | Required | Notes |
|---|---|---|
| **Room / الغرفة** | No | Active rooms only, each showing name, type and nightly rate. Default *"— No specific room —"*, which leaves the booking unroomed and therefore unbillable at checkout. Choosing a room copies its rate into the box below. |
| **Daily Rate (EGP) / السعر اليومي** | No | **This box is ignored — see Known limits B8.** |
| **Check-in Date \*** | **Yes** | Date only, no time |
| **Expected Checkout / موعد الخروج المتوقع** | No | Date only. Used for the *Checkout Today* stat and the list column; **not** used to calculate the bill. |
| **Status / الحالة** | No | `Reserved` or `Checked-in`. Defaults to `Reserved`. |

### Card "Care Instructions / تعليمات الرعاية"

| Field | Required | Notes |
|---|---|---|
| **Diet Notes** | No | Feeding schedule, food brand, allergies. Stored as the booking's feeding instructions. |
| **Medication Notes / ملاحظات الأدوية** | No | Medications to administer and schedule |
| **Additional Notes** | No | Special care and behaviour notes. Stored as the booking's vet notes. |

### Buttons

| Button | Effect |
|---|---|
| **Create Booking / إنشاء حجز** | Requires owner, pet and check-in date. Missing any: *"Owner, pet, and check-in date are required."* and you are returned to a **blank** form. On success: *"Boarding booking created successfully."* and you land on the bookings list. |
| **Cancel / إلغاء** | Back to the list, nothing saved |

Nothing checks whether the chosen room is already occupied for those dates.
Double-booking a room is accepted silently.

> Source: `platform/blueprints/boarding/routes.py:114-166`,
> `platform/templates/boarding/booking_form.html:1-111`

---

## B4. Edit boarding booking

**What it is for.** Changing room, dates, status and care instructions on an
existing stay, and the check-in / check-out / cancel actions.

**How to reach it.** `/boarding/bookings/<id>/edit` — the **✏️ Edit** button. An
unknown id flashes *"Booking not found."* and returns to the list.

**Who can open it.** Same as B1.

### Card "Patient (read-only) / المريض (للقراءة فقط)"

Owner (with a clickable phone number) and pet, both linked to their records.
Owner and pet cannot be changed.

### Card "Stay Details / تفاصيل الإقامة"

| Field | Required | Notes |
|---|---|---|
| **Room / الغرفة** | No | Active rooms, current one pre-selected. A **Room details → / تفاصيل الغرفة ←** link appears below when a room is assigned. |
| **Status / الحالة** | No | `Reserved` / `Checked-in` / `Checked-out` / `Cancelled`. Setting `Checked-out` here **does not bill anything** — only the Check Out button does. |
| **Check-in Date** | No | Blank clears the stored check-in date, which will then be treated as "1 night" at checkout |
| **Expected Checkout / موعد الخروج المتوقع** | No | Date only |

### Card "Care Instructions / تعليمات الرعاية"

**Diet / Feeding Notes**, **Medication Notes / ملاحظات الأدوية** and
**Additional / Vet Notes** — all free text, all pre-filled with the stored values.

### Invoice banner

When an invoice exists: *"Invoice already generated / الفاتورة صادرة بالفعل"* with
the number and a **View Invoice / عرض الفاتورة** button.

### Buttons

| Button | Shown when | Effect |
|---|---|---|
| **💾 Save Changes / 💾 حفظ التغييرات** | always | Saves room, dates, status and the three note fields. *"Booking updated successfully."*, back to the list. |
| **Cancel / إلغاء** | always | Back to the list, nothing saved |
| **✅ Check In Now / ✅ تسجيل الدخول الآن** | status is `Reserved` | Confirms, then checks in (B5). Unsaved edits are lost. |
| **🚪 Check Out & Invoice** | status is `Checked-in` | Confirms, then checks out and bills (B5). Unsaved edits are lost. |
| **✕ Cancel Booking** | status is not `Checked-out`/`Cancelled` | Confirms *"Cancel this booking?"*, sets status to `Cancelled`, *"Booking cancelled."* |

> Source: `platform/blueprints/boarding/routes.py:169-231`,
> `platform/templates/boarding/booking_edit.html:1-146`

---

## B5. Check in / Check out (no screens of their own)

**Check in** — `POST /boarding/bookings/<id>/checkin`. Sets status to
`Checked-in`. If the booking has no check-in date, today's date is stamped on it;
an existing date is left alone. Flashes *"Pet checked in successfully."* and
returns you where you came from.

**Check out** — `POST /boarding/bookings/<id>/checkout`. This is the only place
boarding is billed.

1. Nights are counted as **today minus the check-in date**, with a floor of 1
   night. The expected checkout date and the time of day are not used. An
   unreadable or missing check-in date falls back to 1 night.
2. The rate used is the room's **current** `price_per_night`.
3. If that rate is greater than zero, a one-line invoice is created for the owner
   and pet: *"Boarding — <room> (N nights)"*, quantity N, unit price the nightly
   rate. The invoice id is written onto the booking and you are taken to the
   invoice with *"Invoice #N created — N night(s) × R EGP = T EGP."*
4. If the rate is zero or no room was assigned, nothing is billed and you get
   *"Checked out (N night(s)). No room rate set — create invoice manually."*
5. If invoice creation itself fails: *"Checked out but invoice creation failed:
   …"*
6. If the booking already has an invoice, no second one is created; you are taken
   to the existing invoice.
7. **In every case** the status becomes `Checked-out` and today's date is written
   into the actual-checkout field.

> Source: `platform/blueprints/boarding/routes.py:234-326`

---

## B6. Booking invoice shortcut

`GET /boarding/bookings/<id>/invoice` redirects to the booking's invoice, or
flashes *"No invoice linked to this booking yet."*. Like its grooming twin, **no
screen links to it**.

> Source: `platform/blueprints/boarding/routes.py:329-341`

---

## B7. Boarding rooms / غرف الإيواء

**What it is for.** Defining the hotel's rooms, their type, capacity and nightly
rate.

**How to reach it.** `/boarding/rooms` — the **Manage Rooms** button on the
boarding dashboard, or the room link in a booking row.

**Who can open it.** Same as B1.

Two panels: the rooms table on the left, one add/edit form on the right.

### Rooms table

Shows **all** rooms, active and inactive, ordered by name. Each row carries an
HTML anchor `#room-<id>`, which is what the *Room details →* links jump to.

| Column | Content |
|---|---|
| **Room #** | Room name / number |
| **Type / النوع** | `Standard`, `Suite`, `ICU` or `Isolation` |
| **Capacity / السعة** | Number of animals. **Recorded only — nothing enforces it.** |
| **Rate/Day — السعر/اليوم** | Nightly rate in EGP |
| **Status / الحالة** | *Occupied / مشغول* when the room has at least one `Checked-in` booking, else *Available / متاح* |
| **Active / نشط** | *Yes / نعم* or *No / لا*. Inactive rooms are hidden from the dashboard and from booking dropdowns. |
| *(last)* | **Edit / تعديل** — loads the row into the form and renames the panel *"Edit Room <name>"* |

Empty table: *"No rooms yet. Add a room to get started."*

### Add / Edit Room form

| Field | Required | Notes |
|---|---|---|
| **Room Number \*** | **Yes** | Free text — `A1`, `Suite-3`. Empty flashes *"Room name / number is required."* Uniqueness is not checked. |
| **Room Type** | No | `Standard` / `Suite` / `ICU` / `Isolation`, default `Standard` |
| **Capacity / السعة** | No | Minimum 1, default 1 |
| **Daily Rate (EGP) / السعر اليومي** | No | Tolerant parser: accepts thousands separators, Arabic digits, spaces and a leading currency symbol. **An unparseable value is stored as 0 with no warning** — see Known limits B8. |
| **Active / نشط** | No | Checkbox, ticked by default |

| Button | Effect |
|---|---|
| **Save Room** | Inserts or updates; *"Room added."* / *"Room updated."* |
| **Clear / مسح** | Resets the form to "Add Room" mode |

There is **no delete**. To retire a room, untick **Active**.

> Source: `platform/blueprints/boarding/routes.py:344-398`,
> `platform/templates/boarding/rooms.html:1-110`,
> `platform/models/money.py:55-82` (`form_amount`)

---

## B8. Known limits — Boarding

1. **The "Daily Rate (EGP)" box on the New Booking form does nothing.** It is
   filled in by the room dropdown, it looks editable, and the submit handler
   never reads it. A stay is always billed at the room's rate. Agreeing a special
   nightly rate with a client is not possible on this screen.
   *(`templates/boarding/booking_form.html:44-47`,
   `routes.py:140-148` — `daily_rate` is not among the fields read)*

2. **Changing a room's rate rewrites the apparent cost of every past booking.**
   The Rate/Day column and the checkout calculation both read the room's *current*
   rate; nothing is snapshotted onto the booking.
   *(`routes.py:81`, `:267`, `:282`)*

3. **Checkout ignores the expected-checkout date and bills against today.**
   Checking out a stay three days late bills three extra nights; checking out
   early bills fewer nights than the client agreed.
   *(`routes.py:261-278`)*

4. **Nothing prevents double-booking a room**, and the dashboard shows only the
   most recent check-in per room, so the overlap is invisible.
   *(`routes.py:24-28`, `:135-166`)*

5. **Room capacity is decorative.** A capacity-1 room accepts any number of
   simultaneous bookings. *(`routes.py:365-398`)*

6. **A rate typed as nonsense is silently stored as 0.** The parser returns an
   error message, and the room save discards it. A room saved with a mistyped
   rate bills nothing at checkout, and the only sign is the *"No room rate set"*
   message days later.
   *(`routes.py:372` — the error half of the tuple is thrown away)*

7. **Changing status to `Checked-out` on the edit form does not bill anything**
   and does not stamp an actual-checkout date. Only the **Check Out** button
   does. *(`routes.py:208-215` vs `:251-326`)*

8. **Choosing a room on the edit form throws a JavaScript error.** The handler
   copies the rate into a "dailyRate" box that exists only on the *new* booking
   form. The dropdown still changes, but the error aborts the rest of that
   handler. *(`templates/boarding/booking_edit.html:139-145`)*

9. **The quick-action buttons on the edit form discard unsaved edits** — they are
   separate forms. *(`templates/boarding/booking_edit.html:117-135`)*

10. **A failed create returns a blank form.** *(`routes.py:150-153`)*

11. **The list is capped at 100 rows**, with no paging. *(`routes.py:100`)*

12. **No daily-care notes and no WhatsApp updates.** The launcher card advertises
    both; the only notes on a stay are the three free-text boxes set at booking
    time, and no boarding route sends a message.
    *(`blueprints/launcher/routes.py:220`)*

13. **A room cannot be deleted**, only deactivated. *(`routes.py:365-398`)*

---

# C. Inpatient / التنويم

`/inpatient/` · blueprint `inpatient` · grant `inpatient`

Three screens: the ward dashboard, the admission form, and the stay detail page
(which carries three modal dialogues). This module is for in-clinic **medical**
stays — ICU, post-op recovery, IV therapy, isolation — as distinct from Boarding,
which is recreational.

The module creates its own three tables (`inpatient_stays`, `inpatient_rounds`,
`inpatient_meds`) on first use, once per clinic database.

> Source: `platform/blueprints/inpatient/routes.py:1-9` (module purpose),
> `:38-98` (table creation)

---

## C1. Inpatient ward dashboard

**What it is for.** Every animal currently in the ward, as a card grid ordered by
clinical urgency.

**How to reach it.** Sidebar → CLINICAL → **Inpatient / تنويم**; launcher card
**Inpatient & Hospitalisation**; `/inpatient/`.

**Who can open it.** super_admin, clinic_owner, branch_manager, doctor, nurse.

### Top bar

**+ Admit Patient / + تنويم مريض** opens the admission form.

### Stat cards

| Card | What it counts |
|---|---|
| **Active Stays / الإقامات النشطة** | Every stay whose status is not `Discharged` |
| **Critical / حرج** | Stays with status `Critical` |
| **Ready for Discharge / جاهز للخروج** | Stays with status `Ready for Discharge` |
| **Discharged Today / خرجوا اليوم** | Stays discharged with today's date |

The four counters always cover the whole ward — they do **not** respond to the
filter below.

### Filter bar

| Chip | Effect |
|---|---|
| **All Active / كل النشط** | The default: every stay except `Discharged` |
| **Admitted** | Only stays with that status |
| **Critical** | " |
| **Stable** | " |
| **Ready for Discharge** | " |
| **Discharged** | Only discharged stays — the one way to see historic stays |

The active chip is highlighted. The filter is a URL parameter, so it can be
bookmarked.

### Stay cards

One card per stay. Cards are ordered **Critical first, then Admitted, then
Stable, then everything else**, and within each group newest admission first. The
left edge is colour-coded by status: Admitted blue, Critical red, Stable green,
Ready for Discharge amber, Discharged grey.

Each card shows: 🐾 pet name, species and breed, a status badge, 👤 owner name and
phone, the admission reason (truncated to 80 characters), the ward, the cage
number if one was given, and the admission date. Clicking anywhere on the card
opens the stay detail page.

Empty ward: a 🏥 panel reading *"No active inpatient stays / لا توجد حالات تنويم
نشطة"* with an **Admit First Patient / نوّم أول مريض** button.

> Source: `platform/blueprints/inpatient/routes.py:138-181`,
> `platform/templates/inpatient/dashboard.html:1-81`

---

## C2. Admit patient / تنويم مريض

**What it is for.** Opening a new inpatient stay.

**How to reach it.** `/inpatient/admit` — the **+ Admit Patient** button.

**Who can open it.** super_admin, clinic_owner, branch_manager, doctor, nurse.

| Field | Required | Notes |
|---|---|---|
| **Owner * / المالك *** | **Yes** | Type-to-search picker (§3) |
| **Pet * / الحيوان *** | **Yes** | Filled from the chosen owner. Note that after loading, the **first pet is already selected** — there is no blank "choose one" entry, so a multi-pet owner needs a deliberate choice. |
| **Ward / العنبر** | No | `General`, `ICU`, `Isolation`, `Post-Op`, `Neonatal`, `Exotic`. Defaults to `General`. A label only — wards have no capacity and no occupancy tracking. |
| **Cage / Kennel Number — رقم القفص** | No | Free text, e.g. `K-3`. Not checked against anything, and not checked for double occupancy. |
| **Reason for Admission * / سبب التنويم *** | **Yes** | The chief complaint. Enforced by the browser and by the database. |
| **Initial Diagnosis / التشخيص المبدئي** | No | Working diagnosis, one line |
| **Treatment Plan / خطة العلاج** | No | Free text — IV fluids, monitoring, medications |
| **Expected Discharge Date / تاريخ الخروج المتوقع** | No | Date box, cannot be set earlier than today. **Recorded only — it is not shown on the ward dashboard or on the stay detail page.** |
| **Daily Rate (EGP) / السعر اليومي** | No | Two decimals, minimum 0, default 0. Drives the "Est. cost" figure on the stay detail page. |

| Button | Effect |
|---|---|
| **🏥 Admit Patient / 🏥 تنويم مريض** | Creates the stay with status `Admitted`, stamps who admitted it and the current time, then flashes *"Patient admitted successfully."* and returns to the ward dashboard |
| **Cancel / إلغاء** | Back to the ward dashboard |
| **← Back / ← رجوع** (top bar) | Same |

If the insert fails, the error is shown as *"Error admitting patient: …"* and the
form is redisplayed **empty** — everything typed is lost.

There is no field for linking the stay to a visit; see Known limits C5.

> Source: `platform/blueprints/inpatient/routes.py:186-229`,
> `platform/templates/inpatient/admit.html:1-91`

---

## C3. Stay detail

**What it is for.** The working page for one hospitalised animal: status, patient
context, the round chart, the medication record, and discharge.

**How to reach it.** `/inpatient/<stay_id>` — click a card on the ward dashboard.
An unknown id flashes *"Stay record not found."* and returns to the dashboard.

**Who can open it.** super_admin, clinic_owner, branch_manager, doctor, nurse.

### Header

Pet name and stay number, species, breed and owner. Two top-bar buttons:
**← Ward / ← العنبر** back to the dashboard, and **✔ Discharge / ✔ خروج**, which
opens the discharge dialogue (hidden once the stay is discharged).

### Status strip

A colour-edged bar showing the status badge, the admission date, the ward, the
cage number if any, and:

> **N night(s) · Est. cost: X EGP** — nights counted as **today minus the
> admission date** (or discharge date, once discharged), multiplied by the daily
> rate set at admission.

A patient admitted this morning therefore reads **0 nights · 0.00 EGP**. This
figure is an estimate on screen only; nothing bills from it.

On the right, while the stay is not discharged, a small **status form**: a
dropdown of `Admitted`, `Critical`, `Stable`, `Ready for Discharge` (`Discharged`
is deliberately excluded) and an **Update / تحديث** button. Submitting writes the
new status and flashes *"Status updated to X."* An unrecognised value is rejected
with *"Invalid status."*

### Card "🐾 Patient / المريض"

| Row | Content |
|---|---|
| **Allergies / الحساسية** | From the pet record, shown in red. `—` when none. |
| **Chronic / مزمن** | Chronic conditions from the pet record |
| **Owner / المالك** | Name linked to the owner record, plus phone |
| **Admitted by / نوّمه** | Full name of the user who admitted the animal |

Below, up to four link buttons: **🐾 Pet record / ملف الحيوان**,
**🩻 Imaging / الأشعة** (that pet's imaging studies),
**📋 Admitting visit / زيارة التنويم** (only when the stay is linked to a visit),
and **💳 Invoice / الفاتورة** with its number and status (only when an invoice
exists for that visit). When there is no invoice the card reads *"No invoice has
been raised for this stay yet. / لم تُصدر فاتورة لهذه الإقامة بعد."*

The invoice is found **through the admitting visit**, not through the stay. In
practice this means it is never found — see Known limits C5.

### Card "📋 Clinical / سريري"

Reason, Diagnosis and Plan as captured at admission. Diagnosis and Plan are shown
only when they were filled in. **None of the three can be edited after
admission** — there is no edit screen for a stay.

### Section "📊 Clinical Rounds"

A table of every recorded round, newest first, with the count in the heading.
**+ Add Round / + إضافة جولة** (hidden once discharged) opens the round dialogue.

| Column | Content |
|---|---|
| **Time / الوقت** | Round timestamp to the minute |
| **Temp / الحرارة** | °C, or `—` |
| **HR** | Heart rate, or `—` |
| **RR** | Respiratory rate, or `—` |
| **Pain / الألم** | `N/10`, or `—` |
| **Food / الطعام** | Free-text intake note |
| **Fluids I/O — السوائل داخل/خارج** | `<in>mL / <out>mL`. Shown as `—` whenever fluid-in is blank, **even if fluid-out was recorded**. |
| **Observations / الملاحظات** | Free text |
| **By / بواسطة** | Who recorded it |

Empty: *"No rounds recorded yet. / لا توجد جولات مسجلة بعد."*

#### "📊 Record Clinical Round" dialogue

| Field | Required | Notes |
|---|---|---|
| **Temp (°C) / الحرارة** | No | One decimal |
| **Heart Rate / معدل النبض** | No | Whole number |
| **Resp Rate / معدل التنفس** | No | Whole number |
| **Weight (kg) / الوزن** | No | One decimal. **Stored but never displayed anywhere.** |
| **Pain Score (0-10) / درجة الألم** | No | 0 to 10 |
| **Food Intake / كمية الطعام** | No | Free text — *Full / Half / Refused* |
| **Fluid In (mL) / السوائل الداخلة** | No | Whole number |
| **Fluid Out (mL) / السوائل الخارجة** | No | Whole number |
| **Observations / الملاحظات** | No | Free text |
| **Treatment Given / العلاج المُعطى** | No | Free text. **Stored but never displayed anywhere.** |

**Every field is optional** — an entirely blank round saves successfully and
appears in the table as a row of dashes.

| Button | Effect |
|---|---|
| **Save Round / حفظ الجولة** | Records the round, timestamped **now**, attributed to you. *"Round recorded."* On failure: *"Error: …"* |
| **Cancel / إلغاء** | Closes the dialogue, saves nothing |

The round time cannot be set — it is always the moment you press Save. A round
observed at 02:00 and typed up at 07:00 is filed at 07:00.

### Section "💊 Medication Administration"

A table of every dose given, newest first, with the count in the heading.
**+ Give Med / + إعطاء دواء** (hidden once discharged) opens the dialogue.

| Column | Content |
|---|---|
| **Time / الوقت** | Administration timestamp to the minute |
| **Medication / دواء** | Drug name |
| **Dose / الجرعة** | Free text |
| **Route / طريقة الإعطاء** | Purple badge: `PO`, `IV`, `IM`, `SC`, `Topical`, `Nebulisation` or `Intranasal` |
| **Given By / أعطاه** | Who recorded it |
| **Notes / ملاحظات** | Free text |

Empty: *"No medications recorded yet. / لا توجد أدوية مسجلة بعد."*

#### "💊 Record Medication" dialogue

| Field | Required | Notes |
|---|---|---|
| **Medication * / الدواء *** | **Yes** | Free text. **Not linked to the pharmacy or to stock** — recording a dose here does not dispense or decrement anything. |
| **Dose / الجرعة** | No | Free text, e.g. `10mg/kg` |
| **Route / طريقة الإعطاء** | No | The seven routes above, default `PO` |
| **Notes / ملاحظات** | No | One line |

| Button | Effect |
|---|---|
| **Record / تسجيل** | Saves the dose, timestamped **now**, attributed to you. *"Medication recorded."* |
| **Cancel / إلغاء** | Closes, saves nothing |

As with rounds, the administration time cannot be back-dated.

### "✔ Discharge Patient" dialogue

Opened from the **✔ Discharge** button. It states: *"This will mark the stay as
Discharged. Billing can then be generated from Finance."*

| Field | Required | Notes |
|---|---|---|
| **Discharge Notes / Owner Instructions — ملاحظات الخروج / تعليمات المالك** | No | Follow-up date, medications to continue, diet, activity restrictions |

| Button | Effect |
|---|---|
| **Confirm Discharge / تأكيد الخروج** | Sets status to `Discharged`, stamps the discharge time and saves the notes. *"Patient discharged successfully."* You stay on this page, now read-only. |
| **Cancel / إلغاء** | Closes, changes nothing |

Discharging **only closes the stay**. It raises no invoice, produces no printable
discharge summary, and the notes you type are not displayed anywhere afterwards
— see Known limits C5.

Only super_admin, clinic_owner, branch_manager and doctor may discharge. A nurse
sees the button, presses it, and is bounced to the launcher with *"You don't have
permission to access this page."*

> Source: `platform/blueprints/inpatient/routes.py:234-286` (page), `:291-307`
> (status), `:312-344` (round), `:349-374` (medication), `:379-393` (discharge),
> `platform/templates/inpatient/stay_detail.html:1-232`

---

## C4. Owner-pets lookup

`GET /inpatient/api/owner/<owner_id>/pets` returns that owner's pets as JSON. It
is used by the admission form's pet dropdown. Any signed-in user holding the
`inpatient` grant may call it.

> Source: `platform/blueprints/inpatient/routes.py:398-407`

---

## C5. Known limits — Inpatient

1. **A stay can never be linked to a visit, so the invoice link never appears.**
   The admission form has no visit field, and the invoice on the stay detail page
   is looked up through the visit. In practice the Patient card always shows *"No
   invoice has been raised for this stay yet."* and the *Admitting visit* button
   never appears.
   *(`templates/inpatient/admit.html:14-67` — no `visit_id` input;
   `routes.py:203` reads one that is never sent; `routes.py:262-268`)*

2. **Nothing bills an inpatient stay.** There is no invoice generation anywhere in
   the module. The *"Est. cost"* on the stay strip is a display figure that no
   invoice reads. The discharge dialogue tells you to bill from Finance, and that
   is the whole of it. *(`routes.py:272-273`, `:379-393`)*

3. **No discharge summary is produced.** The module docstring says the module
   "generates a discharge summary automatically". No such route or template
   exists, and the discharge notes you type are never rendered on any screen.
   *(`routes.py:1-9` vs `:379-393`;
   `templates/inpatient/stay_detail.html` never reads `discharge_notes`)*

4. **A stay cannot be edited after admission.** Ward, cage, reason, diagnosis,
   treatment plan, expected discharge date and daily rate are all fixed at
   admission. Only the status can change. Moving an animal from General to ICU is
   not possible without deleting and re-admitting — and there is no delete
   either. *(`routes.py:186-229`, `:291-307`)*

5. **Rounds and medications cannot be back-dated, edited or deleted.** Both are
   always stamped with the moment you press Save; both dialogues omit the time
   field that the underlying routes would accept.
   *(`routes.py:326`, `:365` vs `templates/inpatient/stay_detail.html:158-179`,
   `:194-205`)*

6. **Weight and "Treatment Given" are captured on every round and shown nowhere.**
   The rounds table has no column for either.
   *(`templates/inpatient/stay_detail.html:100`, `:165-166`, `:177-178`)*

7. **The Fluids I/O column hides fluid-out when fluid-in is blank.** A round
   recording 300 mL out and nothing in displays as `—`.
   *(`templates/inpatient/stay_detail.html:110`)*

8. **A completely blank round saves.** No field is required.
   *(`routes.py:312-344`)*

9. **Medication records are free text with no pharmacy link.** Nothing checks the
   drug name, nothing decrements stock, nothing cross-checks allergies.
   *(`routes.py:349-374`)*

10. **The expected discharge date is captured and never shown.** Neither the ward
    dashboard nor the stay detail page displays it, and nothing warns when it
    passes. *(`routes.py:210` vs both templates)*

11. **Ward and cage are labels with no occupancy control.** Two animals can be
    admitted to cage K-3 with no warning. *(`routes.py:186-229`)*

12. **A nurse cannot discharge**, although a nurse can admit, record rounds, give
    medications and change status. *(`routes.py:380`)*

13. **`pharmacist` appears on the medication route's role list but cannot reach
    it**, because pharmacists do not hold the `inpatient` grant.
    *(`routes.py:350-351`, `models/database.py:4368`)*

14. **A failed admission returns a blank form.** *(`routes.py:217-219`)*

15. **Two templates in this module are orphans** — `inpatient/list.html` and
    `inpatient/admit_form.html` are rendered by no route. Anything you read in
    them describes nothing that ships.

16. **The ward dashboard has no date range and no paging.** Historic stays are
    reachable only through the *Discharged* filter chip, unbounded and unsorted
    by date beyond the status ordering. *(`routes.py:144-161`)*

---

# D. Telemedicine / الاستشارة عن بُعد

`/telemedicine/` · blueprint `telemedicine` · grant `telemedicine`

Three screens: a dashboard, a new-session form, and a session detail page. Video
is provided by public Jitsi Meet rooms — every session gets a unique random room
at `https://meet.jit.si/PAH-<12-character token>`. No API key, no account and no
app download is involved; the room opens in any browser.

The module creates its `telemedicine_sessions` table on first use. If that fails
the screens still render, but nothing can be saved, and the reason is written to
the application log.

> Source: `platform/blueprints/telemedicine/routes.py:1-3`, `:23-79`

---

## D1. Telemedicine dashboard

**What it is for.** Upcoming consultations to run today, and the archive of past
ones.

**How to reach it.** Sidebar → CLINICAL → **Telemedicine / الاستشارة عن بُعد**;
launcher card **Telemedicine**; the command palette chip 🎥 **Telemedicine**;
`/telemedicine/`.

**Who can open it.** super_admin, clinic_owner, branch_manager, doctor. (The
launcher card is also offered to nurse and reception, who will be refused — §2.)

### Top bar

**+ New Session** opens the new-session form.

### Stat cards

| Card | What it counts |
|---|---|
| **Total Sessions** | Every session ever created, any status |
| **Scheduled / مجدول** | Sessions with status `Scheduled` |
| **Completed / مكتمل** | Sessions with status `Completed` |
| **Today / اليوم** | Sessions scheduled for today, **any status** — including cancelled ones |

### "📅 Upcoming Sessions" table

Sessions with status `Scheduled` or `In Progress`, earliest first, capped at 50.
This is a status filter, not a date filter: **yesterday's un-completed sessions
stay in this table indefinitely.**

| Column | Content |
|---|---|
| **#** | Session id |
| **Date / Time — التاريخ / الوقت** | Scheduled time to the minute |
| **Owner / المالك** | Owner name linked to their record; phone underneath |
| **Pet / الحيوان** | Pet name linked to its record, or `—` when the session has no pet; species underneath |
| **Doctor / الطبيب** | Free-text doctor name, or `—` |
| **Duration / المدة** | Minutes |
| **Status / الحالة** | Green for Completed, red for Cancelled, amber for everything else |
| **Actions / إجراءات** | **View / عرض** opens the session page. **🎥 Join** opens the Jitsi room in a new tab — shown only while status is `Scheduled`, so a session already marked *In Progress* has no Join button here (use the session page). |

Empty: *"No upcoming sessions. Schedule one →"*

### "📋 Past Sessions" table

Sessions with status `Completed` or `Cancelled`, most recent first, capped at 30.

| Column | Content |
|---|---|
| **#** | Session id, linked to the session page |
| **Date / التاريخ** | Scheduled date (no time) |
| **Owner / المالك** | Linked owner name |
| **Pet / الحيوان** | Linked pet name, or `—` |
| **Doctor / الطبيب** | Doctor name |
| **Status / الحالة** | Green when Completed, red otherwise |
| **Invoice / الفاتورة** | 🧾 #id linked to the invoice, or `—` |

Empty: *"No past sessions."*

There are **no filters and no search** on this screen.

> Source: `platform/blueprints/telemedicine/routes.py:84-123`,
> `platform/templates/telemedicine/dashboard.html:1-88`

---

## D2. New video consultation

**What it is for.** Scheduling a session and minting its room link.

**How to reach it.** `/telemedicine/new` — the **+ New Session** button.

**Who can open it.** Same as D1.

### Card "Patient / المريض"

| Field | Required | Notes |
|---|---|---|
| **Owner * / المالك *** | **Yes** | Type-to-search picker (§3) |
| **Pet / الحيوان** | No | Filled from the owner; the first entry is *"— No specific pet —"*. A session with no pet is allowed and is shown as `—` everywhere. |

### Card "Session Details"

| Field | Required | Notes |
|---|---|---|
| **Doctor Name** | No | Free text, pre-filled with your own name. Not validated against staff records, and not used to route the session to anyone. |
| **Duration / المدة** | No | 15 / 30 / 45 / 60 minutes, default 30. Recorded on the invoice line text; it does **not** change the price and does not enforce anything on the call. |
| **Scheduled Date & Time \*** | **Yes** | Date-and-time box. No check that it is in the future, and no check against the doctor's diary. |
| **Chief Complaint / Reason** | No | Why the owner wants a video consultation |

### "How it works" panel

An explanatory card: a unique Jitsi Meet room link is generated automatically and
can be sent to the owner by WhatsApp from the session page; no app download is
needed.

### Buttons

| Button | Effect |
|---|---|
| **🎥 Create Session** | Requires owner and scheduled time. Missing either: *"Owner and scheduled time are required."* and you are returned to a **blank** form. On success a random 12-character room token is generated, the session is created with status `Scheduled`, and you land on the session page with *"Telemedicine session created. Share the room link with the owner."* |
| **Cancel / إلغاء** | Back to the dashboard |
| **← Dashboard / ← لوحة التحكم** (top bar) | Same |

> Source: `platform/blueprints/telemedicine/routes.py:128-172`,
> `platform/templates/telemedicine/new_session.html:1-94`

---

## D3. Session detail

**What it is for.** Running one consultation: joining the call, sending the owner
the link, and closing the session with notes and an invoice.

**How to reach it.** `/telemedicine/<id>` — from either dashboard table. An
unknown id returns a 404 page.

**Who can open it.** Same as D1.

### Status and join card

Colour-edged by status (green Completed, red Cancelled, blue In Progress, amber
otherwise). Shows the status, the scheduled time (while still `Scheduled`), the
duration and the doctor's name.

Beneath it, the **room URL** in a code box with a **📋 Copy / 📋 نسخ** button that
copies it to the clipboard and briefly reads *"✓ Copied!"*.

### Action buttons

| Button | Shown when | Effect |
|---|---|---|
| **🎥 Join Video Call** | status is `Scheduled` or `In Progress` | Opens the Jitsi room in a new tab. Does **not** change the status. |
| **▶ Mark as Started** | status is `Scheduled` | Sets status to `In Progress` and stamps the start time. *"Session started. Click the room link to open the video call."* |
| **✅ Complete Session / ✅ إنهاء الجلسة** | status is `Scheduled` or `In Progress` | Opens the completion dialogue (below) |
| **📱 Send Link via WhatsApp** | the owner has a WhatsApp number **and** the status is not `Cancelled` | Sends the owner a message with their appointment time and the room link. On success: *"Room link sent to <number> via WhatsApp."*; on failure: *"Could not send WhatsApp: …"* |
| **✕ Cancel** | status is neither `Completed` nor `Cancelled` | Confirms *"Cancel this session?"*, sets status to `Cancelled` and returns to the dashboard with *"Session cancelled."* |

If the owner has no WhatsApp number the button is not rendered at all; hitting the
route directly flashes *"Owner has no WhatsApp number registered."*

### "Clinical Notes / ملاحظات سريرية" card

Shown only when there is something to show. Displays the **Chief Complaint /
الشكوى الرئيسية** captured at booking, and **Doctor Notes** captured at
completion. Neither can be edited from this page.

### Invoice card

When an invoice exists: *"Invoice generated"*, the number, and a **View Invoice /
عرض الفاتورة** button.

### Right-hand column

- **Owner / المالك** — name linked to the owner record, phone as a `tel:` link,
  WhatsApp number in green, and email.
- **Patient / المريض** — shown only when a pet was chosen: name linked to its
  record, species and breed, and a **Medical record & visits → / السجل الطبي
  والزيارات ←** link.
- **Session Info** — Scheduled, Duration, Started (if started), Ended (if ended),
  and Created by.

### "✅ Complete Session" dialogue

| Field | Required | Notes |
|---|---|---|
| **Doctor Notes (optional)** | No | Summary of the consultation, findings, recommendations |

**Complete & Generate Invoice** does the following, in order:

1. Sets the status to `Completed`, stamps the end time, and saves the notes. This
   part always succeeds.
2. Looks up the consultation price from the **service catalogue**: the first
   active service whose name contains "tele", using its standard price. If there
   is no such service the price falls back to **0.00**.
3. If the price is greater than zero, raises a one-line invoice for the owner and
   pet — *"Video Consultation — <doctor> (N min)"*, quantity 1 — links it to the
   session, and takes you to the invoice with *"Session completed. Invoice #N
   generated."*
4. If the price is zero, **no invoice is created** and you simply get *"Session
   completed successfully."* with no explanation of why there is no invoice.
5. If invoice creation fails, you get *"Session completed, but the invoice could
   not be generated. Please create it manually."*

> Source: `platform/blueprints/telemedicine/routes.py:177-196` (page), `:201-215`
> (start), `:220-242` (price lookup), `:247-306` (complete), `:311-322` (cancel),
> `:327-360` (WhatsApp), `platform/templates/telemedicine/session_detail.html:1-164`

---

## D4. Known limits — Telemedicine

1. **Billing depends on a service catalogue entry whose name contains "tele".**
   Without one, every completed consultation is free and silent — the price falls
   back to 0.00, no invoice is created, and the success message says nothing
   about it. Set up an active catalogue service named e.g. *Telemedicine
   Consultation* before going live. *(`routes.py:18`, `:220-242`, `:274`)*

2. **The consultation price does not vary with duration.** A 15-minute and a
   60-minute session bill the same single catalogue price; the duration appears
   only in the invoice line text. *(`routes.py:283-289`)*

3. **A session cannot be edited.** There is no edit route. To change the time,
   the doctor, the duration or the pet, cancel and create a new session — which
   mints a new room link.
   *(`platform/blueprints/telemedicine/routes.py` — no edit route exists)*

4. **Upcoming sessions never age out.** The Upcoming table filters on status, not
   on date, so a session that was never completed or cancelled sits at the top of
   the dashboard forever. *(`routes.py:91-100`)*

5. **The "Today" stat counts cancelled sessions.** *(`routes.py:116-118`)*

6. **The Join button is missing from the dashboard once a session is marked
   started.** It is rendered only for `Scheduled`. The session page still has it.
   *(`templates/telemedicine/dashboard.html:51-53`)*

7. **Jitsi rooms are public and protected only by an unguessable URL.** Anyone who
   receives the link can enter the room, before, during or after the appointment.
   There is no waiting room, no password and no expiry. *(`routes.py:72-79`)*

8. **The room is on the public `meet.jit.si` service.** Nothing in this module
   points at a self-hosted or clinic-controlled server, so consultation video
   leaves the clinic's infrastructure entirely. *(`routes.py:74`)*

9. **The doctor's name is free text.** It does not link to a staff record, does
   not put the session in anyone's diary, and does not restrict who may open the
   session. *(`routes.py:137`)*

10. **There is no prescription flow.** The table carries a prescription column
    and no screen ever fills it. *(`routes.py:51`)*

11. **No filters, no search and no paging** on the dashboard; upcoming is capped
    at 50 rows and past at 30. *(`routes.py:99`, `:109`)*

12. **A failed create returns a blank form.** *(`routes.py:142-145`)*

---

# E. Laboratory / المختبر

`/clinical/lab` · blueprint `clinical` · grant **`visits`**

Three screens: the request list, the new-request form, and the request detail
page where results are entered.

**Important:** a lab request is a child of a **visit**. There is no way to raise a
lab request for a pet that is not on a visit, and the *"+ New Lab Request"*
button on the list screen leads to a form that cannot be submitted. Lab requests
are raised from the visit screen. See Known limits E4.

---

## E1. Lab requests list

**What it is for.** The lab's work queue, split into three tabs.

**How to reach it.** Sidebar → CLINICAL → **Lab & Vaccines / المختبر والتطعيمات**;
launcher card **Laboratory & Diagnostics**; `/clinical/lab`.

**Who can open it.** super_admin, clinic_owner, branch_manager, doctor, nurse,
pharmacist. (The launcher card omits pharmacist, who can still reach it by URL or
sidebar.)

### Top bar

**＋ New Lab Request / ＋ طلب مختبر جديد** opens the new-request form — which, on
its own, cannot be submitted (E2).

### Tabs

Three client-side tabs, each with a count badge when it is non-empty. Switching
tabs does not reload the page and does not change the URL, so a tab cannot be
bookmarked or linked.

| Tab | Contents |
|---|---|
| **Pending** | Requests with status `Pending` — everything newly raised |
| **In Progress** | Requests with status `In Progress`. **Always empty — nothing in the application ever sets this status.** |
| **Completed** | Requests with status `Completed` — results have been entered |

Each tab holds up to 200 rows, newest request first. There are **no filters, no
date range and no search** on this screen.

### Columns (all three tabs)

| Column | Content |
|---|---|
| **Date / التاريخ** | The date the request was raised |
| **Pet / الحيوان** | Pet name linked to its record; species and owner name underneath |
| **Test / الفحص** | Test name, with the test code underneath on the Pending tab |
| **Priority / الأولوية** | `Routine` (grey) · `Urgent` (amber) · `STAT` (red) |
| **Status / الحالة** | Pending badge — shown on the Pending tab only |
| **Doctor / الطبيب** | The doctor on the originating **visit**, not the person who raised the request |
| **Actions / إجراءات** | **View / Enter Results — عرض / إدخال النتائج** (Pending), **Enter Results — إدخال النتائج** (In Progress) or **View Results — عرض النتائج** (Completed). All three open the same detail page. |

Empty tabs read *"✅ No pending lab requests."*, *"No tests currently in
progress."* and *"No completed tests yet."*

> Source: `platform/blueprints/clinical/routes.py:46-90`,
> `platform/templates/clinical/lab_list.html:1-250`

---

## E2. New lab request

**What it is for.** Ordering a test against a visit.

**How to reach it.** `/clinical/lab/new?visit_id=<id>` — reached from the visit
screen. Opening `/clinical/lab/new` **without** a visit id (which is what the
list screen's button does) produces a form that cannot be submitted.

**Who can open it.** Same as E1.

### Context card

Shown only when the page was opened with a valid visit id. Displays the patient
(name, species, breed), the owner (name and phone) and the visit (date and type).
When this card is absent, the form will not save.

### Fields

| Field | Required | Notes |
|---|---|---|
| **Test Name / اسم الفحص \*** | **Yes** | A dropdown of twelve common tests: CBC (Complete Blood Count), Biochemistry Panel, Urinalysis, X-Ray, Ultrasound, Culture & Sensitivity, Fecal Exam, Heartworm Test, Thyroid Panel, Electrolytes, Blood Glucose, Coagulation Profile — plus **Custom / Other — مخصص / أخرى** |
| **Custom Test Name / اسم فحص مخصص** | Only when *Custom* is chosen | Appears when *Custom* is selected and becomes required. Whatever you type replaces "Custom" as the test name. Choosing *Custom* and leaving this blank stores the literal test name "Custom". |
| **Test Code / كود الفحص** | No | Free text, e.g. `CBC-001`. Not validated and not linked to any catalogue. |
| **Priority / الأولوية \*** | **Yes** | `Routine / روتيني` (default) · `Urgent / عاجل` · `STAT (Immediate) / STAT (فوري)`. Colour-codes the badge in the list; it does **not** reorder the queue, which is always newest-first. |
| **Sample Type / نوع العينة** | No | Blood (EDTA), Blood (Serum), Urine, Feces, Swab, Tissue Biopsy, Fluid (Pleural), Fluid (Abdominal), Skin Scraping, Other. **In the Arabic interface this box submits Arabic text** — the options carry no value attribute. |
| **Notes / Instructions — ملاحظات / تعليمات** | No | Special instructions for the lab team |

| Button | Effect |
|---|---|
| **Create Lab Request / إنشاء طلب مختبر** | Saves the request with status `Pending`, attributed to you, and returns to the list with *"Lab request for 'X' created."* If the test name is empty, *"Test name is required."* and the form is redisplayed. If the visit or pet is missing, *"Visit and pet are required."* and you are sent back to an empty form. |
| **Cancel / إلغاء** and **← Back to Lab Requests / ← العودة إلى طلبات المختبر** | Return to the list |

> Source: `platform/blueprints/clinical/routes.py:18-31` (test list), `:93-154`,
> `platform/templates/clinical/lab_form.html:1-130`

---

## E3. Lab request detail and results entry

**What it is for.** Reading one request in full and typing its result.

**How to reach it.** `/clinical/lab/<id>` — the action button on any list row. An
unknown id returns a 404 page.

**Who can open it.** Same as E1.

### "🧪 Request Information / بيانات الطلب"

Header badges: the priority badge and the status badge. Then a grid of:

| Item | Content |
|---|---|
| **Test Name / اسم الفحص** | |
| **Test Code / كود الفحص** | Shown only when one was entered |
| **Patient / المريض** | Pet name linked to its record; species underneath |
| **Owner / المالك** | Owner name linked to their record |
| **Visit / الزيارة** | Visit date, linked to the visit — or *"Not linked to a visit / غير مرتبط بزيارة"* |
| **Requesting Doctor / الطبيب الطالب** | The doctor on the visit; shown only when there is one |
| **Sample Type / نوع العينة** | Shown only when one was chosen |
| **Requested / تاريخ الطلب** | Date and time the request was raised |

Below, a **NOTES / ملاحظات** block when notes were entered.

### "📊 Results" card

Shown once at least one result exists. One block per result, **newest first**.
Results marked abnormal get a red border, a pink background and a
**⚠ ABNORMAL / ⚠ غير طبيعي** badge.

Each block shows who entered it and when, then the numeric value with its unit
and reference range (*"Value: 6.5 g/dL | Ref: 4.0–5.5 g/dL"*) when a number was
entered, then the free-text report.

### "✏️ Enter Results / إدخال النتائج" form

Shown **only while the request is not `Completed`**. Once complete, the form is
replaced by a green panel: *"✅ This lab request is complete. Results have been
recorded above."*

| Field | Required | Notes |
|---|---|---|
| **Result Text / Report — نص النتيجة / التقرير** | No | The full report, findings or interpretation |
| **Numeric Value / القيمة الرقمية** | No | Any decimal. Blank stores no value. |
| **Unit / الوحدة** | No | Free text, e.g. `g/dL`, `cells/µL` |
| **Reference Range / المدى المرجعي** | No | Free text, e.g. `4.0–5.5 g/dL`. **Typed by hand every time** — there is no reference-range library. |
| **Mark as Abnormal / تعليم كغير طبيعي** | No | Checkbox. **A manual judgement** — nothing compares the value against the range. |

| Button | Effect |
|---|---|
| **Save Results & Mark Complete / حفظ النتائج وإنهاء الطلب** | Records the result attributed to you and timestamped now, **and sets the request to `Completed` in the same action**. *"Lab results saved."* |
| **Cancel / إلغاء** | Back to the list |

**Every field is optional**, so pressing Save with the form untouched records an
empty result and closes the request.

> Source: `platform/blueprints/clinical/routes.py:157-223`,
> `platform/templates/clinical/lab_detail.html:1-245`

---

## E4. Known limits — Laboratory

1. **The "＋ New Lab Request" button on the list screen leads to a dead end.** It
   opens the form with no visit context, so the form renders without the hidden
   visit and pet fields, and every attempt to submit flashes *"Visit and pet are
   required."* and returns you to the same unusable form. Raise lab requests from
   the visit screen instead.
   *(`templates/clinical/lab_list.html:8-10`;
   `templates/clinical/lab_form.html:43-48` — hidden fields rendered only when a
   visit or pet is in context; `routes.py:122-126`)*

2. **The "In Progress" tab is always empty.** Requests are created `Pending` and
   jump straight to `Completed` when a result is saved. Nothing in the
   application ever writes `In Progress`, and there is no control to set it. A
   sample that has been collected and is at the analyser cannot be distinguished
   from one nobody has touched.
   *(`routes.py:139` writes `Pending`, `:218-220` writes `Completed`)*

3. **Sample collection is not tracked.** The database has a collected-at column
   and no screen writes or shows it. *(`models/database.py:1401`)*

4. **Saving a result always completes the request.** There is no way to record a
   partial or interim result and keep the request open, and no way to add a
   second result afterwards — once completed, the entry form disappears.
   *(`routes.py:204-220`, `templates/clinical/lab_detail.html:187`)*

5. **A completely empty result saves and closes the request.** No field is
   required. *(`routes.py:200-217`)*

6. **Abnormal is a manual tick.** Nothing compares the numeric value to the
   reference range, and reference ranges are free text retyped for every result —
   there is no species- or test-specific range library.
   *(`routes.py:200-217`, `templates/clinical/lab_detail.html:214-226`)*

7. **A request cannot be edited, cancelled or deleted.** A test ordered by mistake
   stays in the Pending queue until somebody saves an empty result against it.
   *(no edit, cancel or delete route exists in `routes.py:77-223`)*

8. **Priority does not affect ordering.** A STAT request appears in the same
   newest-first order as a routine one; only the badge colour differs.
   *(`routes.py:62`)*

9. **The Sample Type dropdown submits Arabic text in the Arabic interface** — its
   options carry no value attribute, so `Blood (EDTA)` is stored as
   `دم (EDTA)` for an Arabic user and as `Blood (EDTA)` for an English one, in
   the same column. *(`templates/clinical/lab_form.html:86-98`)*

10. **Nothing bills a lab test.** No invoice is raised at request or at
    completion, and there is no price on a request.
    *(`routes.py:93-223`)*

11. **No result attachments.** A PDF or an analyser printout cannot be attached —
    only typed text. The database has a report-data column that no screen uses.
    *(`models/database.py:1419`)*

12. **The tabs are not addressable.** Switching tabs does not change the URL, so
    "the completed list" cannot be bookmarked or linked, and a browser refresh
    returns to Pending. *(`templates/clinical/lab_list.html:234-249`)*

13. **No test catalogue and no AI summary**, both of which the launcher card
    advertises. The twelve common tests are a hardcoded list in the source, not a
    manageable catalogue. *(`blueprints/launcher/routes.py:67`,
    `blueprints/clinical/routes.py:18-31`)*

14. **Each tab is capped at 200 rows** with no paging.
    *(`routes.py:62`)*

---

# F. Medical Imaging / التصوير الطبي

`/imaging/` · blueprint `imaging` · grant `imaging`

Five screens: all studies, one pet's studies, the upload form, a study detail
page, and a standalone AI photo analyzer.

Accepted image formats: **JPG, JPEG, PNG, GIF, WebP, BMP, TIFF**, maximum **10
MB** per file. Files are stored under the platform's uploads folder in an
`imaging` subfolder, renamed to a random identifier.

> Source: `platform/blueprints/imaging/routes.py:29-41`

---

## F1. All imaging studies

**What it is for.** The clinic-wide imaging register.

**How to reach it.** Sidebar → CLINICAL → **Imaging / التصوير الطبي**; launcher
card **Medical Imaging**; `/imaging/`.

**Who can open it.** super_admin, clinic_owner, branch_manager, doctor, nurse.

### Top bar

| Button | Effect |
|---|---|
| **🔬 AI Photo Analyzer / 🔬 محلل الصور AI** | Opens the analyzer (F5) |
| **➕ Upload Study / ➕ رفع دراسة** | Opens the upload form (F3) |

### Table

The 100 most recent studies, newest first. **No filters, no search, no paging.**

| Column | Content |
|---|---|
| **Study / الدراسة** | A 50 × 50 thumbnail of the image, or a 🩻 glyph when the study has no file |
| **Pet / الحيوان** | Pet name, linked to **that pet's imaging list** (not to its medical record); species underneath |
| **Type / النوع** | The study type badge |
| **Region / المنطقة** | Body region, or `—` |
| **AI Analysis / تحليل AI** | *✓ AI assessed / ✓ تم التقييم بالذكاء الاصطناعي* in green when an analysis is stored, else `—` |
| **Date / التاريخ** | Date the study was recorded |
| *(last)* | **View / عرض** opens the study page |

Empty: *"No imaging studies yet. Upload the first study →"*

> Source: `platform/blueprints/imaging/routes.py:185-205`,
> `platform/templates/imaging/index.html:1-63`

---

## F2. One pet's studies

**What it is for.** Every imaging record for a single animal, as a gallery.

**How to reach it.** `/imaging/pet/<pet_id>` — the pet link on the all-studies
table, the **🩻 Imaging / الأشعة** button on an inpatient stay, or after saving an
upload. An unknown pet id returns a 404 page.

**Who can open it.** Same as F1.

### Top bar

**➕ Upload Study / ➕ رفع دراسة** (pre-selects this pet), **🔬 AI Analyzer / 🔬 محلل
AI**, and **← Pet Profile / ← ملف الحيوان**.

### Gallery

One tile per study, newest first, **unlimited and unpaged**. Each tile shows the
image (or a 🩻 placeholder), the study-type badge, a green **✓ AI** marker when an
analysis exists, the body region (or *"No region"*), the date, and the first line
of the notes. Clicking anywhere on a tile opens the study page.

Empty: a panel reading *"No imaging studies yet for <pet>"* with **📤 Upload
Study / 📤 رفع دراسة** and **🔬 AI Analyzer** buttons.

> Source: `platform/blueprints/imaging/routes.py:208-230`,
> `platform/templates/imaging/pet_studies.html:1-54`

---

## F3. Upload imaging study

**What it is for.** Filing an X-ray, ultrasound or any clinical image against a
pet, optionally running the AI assessment at the same time.

**How to reach it.** `/imaging/upload`, or `/imaging/upload?pet_id=<id>` from a
pet's gallery, which pre-selects that pet.

**Who can open it.** Same as F1.

| Field | Required | Notes |
|---|---|---|
| **Pet / الحيوان \*** | **Yes** | A dropdown of **every active pet in the clinic**, name and species, ordered by name. This is a plain list with no search — on a large clinic it is a very long dropdown. Pre-selected when the page was opened with a pet id. |
| **Study Type / نوع الدراسة** | No | `X-Ray`, `Ultrasound`, `MRI`, `CT Scan`, `Endoscopy`, `Dermatoscopy`, `Fundoscopy`, `Other`. Defaults to `X-Ray` (the first entry). |
| **Body Region / منطقة الجسم** | No | Free text, e.g. `Chest`, `Abdomen`, `Left Leg` |
| **Image File \*** | **Yes** | One image. JPG, JPEG, PNG, GIF, WebP, BMP or TIFF, up to 10 MB. Only one file per study — a four-view radiographic series needs four separate uploads. |
| **Notes / ملاحظات** | No | Clinical context, reason for imaging. Also passed to the AI as the submitting note when the box below is ticked. |
| **🔬 Run AI analysis on this image (Gemini Vision)** | No | Unticked by default. When ticked, the image is sent for AI assessment **before** the page returns — expect the save to take several seconds longer. |

| Button | Effect |
|---|---|
| **📤 Upload Study / 📤 رفع دراسة** | Validates, saves the file under a random name, optionally runs the AI, records the study against the pet and its owner, then flashes *"Imaging study saved successfully."* and takes you to that pet's gallery. |
| **Cancel / إلغاء** | Back to the all-studies list |

Validation messages, all shown at the top of the same form:

- *"Pet and image file are required."*
- *"Unsupported file type. Use JPG, PNG, GIF, WebP, or TIFF."*
- *"File too large (max 10 MB)."*

**After any of these the form is redisplayed empty** — the pet, type, region,
notes and the file selection are all lost.

The owner recorded on the study is taken from the pet, not asked for.

> Source: `platform/blueprints/imaging/routes.py:233-298`,
> `platform/templates/imaging/upload.html:1-68`

---

## F4. Study detail

**What it is for.** Viewing one study full size with its metadata and AI
assessment.

**How to reach it.** `/imaging/study/<id>` — from either gallery. An unknown id
flashes *"Study not found."* and returns to the all-studies list.

**Who can open it.** Same as F1.

### Left column — the image

The image at up to 500 px tall on a black ground, with the recording date and a
**⬇ Download / ⬇ تحميل** link beneath it. When the study has no file, a 🩻
placeholder reading *"No image file attached / لا يوجد ملف صورة مرفق"*.

### Right column — "Study Details / تفاصيل الدراسة"

| Row | Content |
|---|---|
| **Pet / الحيوان** | Linked to the pet's medical record when the pet still exists |
| **Owner / المالك** | Linked to the owner record when the owner still exists |
| **Visit / الزيارة** | Linked to the visit, or *"Not linked to a visit / غير مرتبطة بزيارة"* — which is what it always says (see F7) |
| **Study Type** | |
| **Body Region** | Or `—` |
| **Recorded by** | The username of whoever uploaded it |
| **Date** | Date and time |
| **NOTES / ملاحظات** | Shown when notes exist |

Pet and owner names are shown as plain text rather than links when the underlying
record has been deleted, so a study whose pet is gone still reads sensibly.

### "🔬 AI Veterinary Analysis / التحليل البيطري بالذكاء الاصطناعي"

The stored AI text, with line breaks preserved and **all markup escaped** —
formatting marks such as `**` are shown literally rather than rendered bold. When
there is no analysis, a panel reads *"No AI analysis for this study."* with a
**Use AI Analyzer → / استخدم محلل AI ←** link.

There is **no button to run the AI on an existing study** — the analysis can only
be requested at upload time, or produced in the analyzer and saved as a new study.

> Source: `platform/blueprints/imaging/routes.py:301-327`,
> `platform/templates/imaging/study_detail.html:1-118`

---

## F5. AI photo analyzer

**What it is for.** Dropping in any animal photo — no pet record needed — and
getting a structured triage assessment back.

**How to reach it.** Sidebar → CLINICAL → **AI Photo Analyzer / محلل الصور AI**
(highlighted in purple); the **🔬 AI Photo Analyzer** button on either gallery;
`/imaging/analyzer`.

**Who can open it.** Same as F1.

### Setup banner

When no Google API key is configured on the server, an amber banner explains that
vision uses the local proxy with Google Gemini as backup and how to add a free
key. It is informational — the analyzer still runs, and may still work through
the proxy.

### Upload card

| Control | Notes |
|---|---|
| **Drop zone** | *"Drop an animal photo here or click to browse / أفلت صورة الحيوان هنا أو اضغط للتصفح"*. Accepts drag-and-drop or a file picker. JPG, PNG, WebP; maximum 10 MB, checked in the browser and again on the server. |
| **Preview** | Appears once a file is chosen, with the file size as a badge |
| **Note box** | Optional. *"describe what you observed — e.g. 'limping since yesterday'…"* — works in Arabic or English and is passed to the AI with the image. |
| **🔬 Analyze with Gemini Vision AI** | Disabled until a photo is chosen. Sends the photo, shows an animated *"Analyzing image with AI... this takes 5–15 seconds"* panel, then renders the result. Network or server errors are reported in a browser alert. |

### Result card

The assessment is rendered with light Markdown formatting, under a header that
carries an automatically derived **severity badge**: 🚨 EMERGENCY, 🔴 Urgent,
🟡 Moderate or 🟢 Minor. The badge is guessed by scanning the returned text for
those words and emoji; **anything the scan does not match is labelled 🟢 Minor**,
including a failure message.

The assessment itself is asked to cover: animal identification, visible
condition, severity, two to four possible diagnoses, immediate first aid,
veterinary urgency, what *not* to do, and a closing reminder that it is an
AI-assisted triage assessment and not a diagnosis.

### Save strip

Below the result: *"Save to patient record: / الحفظ في سجل المريض:"*, a dropdown
of **every active pet in the clinic**, and a **💾 Save to Record / 💾 حفظ في
السجل** button. Saving with no pet selected shows *"Please select a pet to save
the result to."*

Saving creates a new study for that pet with study type **AI Analysis** and notes
*"Via AI Analyzer"*, then takes you to that pet's gallery. **The photo itself is
not stored** — see F7.

### How the analysis is produced

Images are shrunk to 1024 px on the longest side and re-encoded as JPEG before
being sent. Three tiers are tried in order: the local AI proxy (trying several
vision models in turn), then Google Gemini directly if a key is configured, then
— if both fail — a setup-instructions page is returned **as if it were the
analysis**, telling you how to obtain a free Google key.

> Source: `platform/blueprints/imaging/routes.py:51-180` (prompt, compression,
> three-tier analysis), `:339-406` (screen, run, save),
> `platform/templates/imaging/analyzer.html:1-310`

---

## F6. Serving image files

`GET /imaging/file/<filename>` returns a stored image. It requires a signed-in
user holding the `imaging` grant, and the filename is sanitised before use. This
route backs every thumbnail, the full-size view and the Download link.

> Source: `platform/blueprints/imaging/routes.py:330-334`

---

## F7. Known limits — Imaging

1. **A study saved from the AI Analyzer has a broken image.** The save records the
   *browser's* file name as the study's file, but the photo itself was never
   written to the server. The study page then asks for a file that does not exist
   and shows a broken image, with a **⬇ Download** link that fails. Only the AI
   text is really saved. To keep the picture, use **Upload Study** with *Run AI
   analysis* ticked instead.
   *(`routes.py:396-401` stores `filename` with no file write, versus
   `:255-259` in the upload path)*

2. **A study can never be linked to a visit.** The upload form has no visit field,
   so the Visit row on every study reads *"Not linked to a visit"*. Imaging is
   attached to the pet, never to the consultation that ordered it.
   *(`templates/imaging/upload.html:12-57` — no `visit_id` input;
   `routes.py:270` reads one that is never sent)*

3. **The AI cannot be run on an existing study.** The only two ways to get an
   analysis are to tick the box at upload time, or to run the analyzer and save
   its result as a new study. There is no "analyse this" button on the study page.
   *(`routes.py:233-298`, `:301-327`)*

4. **A study cannot be edited or deleted.** A misfiled study — wrong pet, wrong
   type, wrong region — stays wrong. *(no edit or delete route in `routes.py`)*

5. **One image per study.** A radiographic series needs one study per view, with
   no way to group them. *(`routes.py:244`)*

6. **Both pet dropdowns list every active pet with no search**, unlike the
   type-to-search owner pickers used elsewhere in the platform. On a clinic with
   thousands of patients these dropdowns are unusable.
   *(`routes.py:287-289`, `:345-347`)*

7. **A failed upload returns a blank form** — the pet, type, region, notes and the
   file selection are all lost, including after the *"File too large"* message.
   *(`routes.py:246-254` falls through to the GET render)*

8. **When the AI is unavailable, the setup instructions are stored as the
   analysis.** With *Run AI analysis* ticked and no working provider, the study is
   saved with a block of installation instructions in the AI Analysis field,
   displayed under the "AI Veterinary Analysis" header as though it were a
   clinical finding. *(`routes.py:161-180`, `:262-264`)*

9. **The severity badge in the analyzer is a keyword guess, not a classification.**
   It scans the returned text for emoji and the words Emergency, Urgent and
   Moderate. Anything else — including an error message — is badged
   **🟢 Minor**. *(`templates/imaging/analyzer.html:274-284`)*

10. **The AI prompt names a specific veterinarian.** Every assessment ends with an
    instruction to consult "Dr. Hatem or a licensed veterinarian" regardless of
    which clinic is using the system. *(`routes.py:66`)*

11. **No filters, no search, no paging.** The all-studies list is capped at 100
    rows with no way to reach older ones; a pet's gallery is unlimited and
    unpaged. *(`routes.py:196`, `:215-217`)*

12. **The pet column on the all-studies list goes to the imaging gallery, not the
    medical record** — the same wording as elsewhere in the platform, a different
    destination. *(`templates/imaging/index.html:36-38`)*

13. **Images are stored on the application server's filesystem**, not in a
    document store, and are served through the application. There is no DICOM
    support, no viewer tooling (zoom, measure, window/level) and no study
    versioning. *(`routes.py:37-41`, `:330-334`)*

---

# G. Limits that apply across all six modules

1. **Every save needs JavaScript.** The security token on which every POST depends
   is inserted by a script at submit time. With JavaScript off, nothing in this
   chapter can be saved. *(`platform/static/js/platform.js:129-146`,
   `platform/app.py:349-357`)*

2. **The sidebar shows all seven links to everyone.** There is no role condition
   on the CLINICAL nav group, so users routinely click into modules they do not
   hold and get bounced to the launcher.
   *(`platform/templates/base.html:137-179`)*

3. **The launcher card list and the permission grants are maintained separately
   and disagree.** The clearest case is Telemedicine, whose card is offered to
   nurse and reception, neither of whom holds the grant.
   *(`platform/blueprints/launcher/routes.py:193` vs
   `platform/models/database.py:4362-4367`)*

4. **Row caps everywhere, paging nowhere.** Grooming 200, Boarding 100, Lab 200
   per tab, Imaging 100, Telemedicine 50 upcoming / 30 past. In every case the
   screen looks complete when it is not.

5. **Failed form submissions lose everything typed.** Grooming, Boarding,
   Inpatient, Telemedicine and Imaging all redirect or re-render to an empty form
   on a validation failure.

6. **Arabic labels are inconsistently applied.** Several field labels
   (*"Booking Details"*, *"Check-in Date"*, *"Daily Rate"* on some screens,
   *"Doctor Notes"*, *"Session Info"*) have no Arabic half in the source and stay
   English in the Arabic interface. Two dropdowns go further and **store** the
   Arabic label as data: Grooming's new-booking Status box and Lab's Sample Type
   box.
   *(`templates/grooming/booking_form.html:52-56`,
   `templates/clinical/lab_form.html:86-98`)*
