# Front Desk — Reference Manual

**Modules:** Owners & Pets / الملاك والحيوانات · Appointments / المواعيد · New Visit / زيارة جديدة
**URL prefixes:** `/crm/`, `/appointments/`, `/workflow/`
**Blueprints:** `crm`, `appointments`, `workflow`

This chapter is a **screen-by-screen reference**, not a task walkthrough. It
describes only what the code in `blueprints/crm/routes.py`,
`blueprints/appointments/routes.py`, `blueprints/workflow/routes.py` and their
templates actually does today. A control that does not do what its label
promises, or a field the database holds with no screen behind it, is listed
under [Known limits](#21-known-limits) rather than described as working.

> Source: `platform/app.py:212-214` (imports), `platform/app.py:240-242`
> (blueprints registered), `platform/blueprints/crm/__init__.py:2`,
> `platform/blueprints/appointments/__init__.py:2`,
> `platform/blueprints/workflow/__init__.py:3`

---

## 1. Getting into the front desk

Four doors, and they do not all lead where their names suggest.

| Door | Where | Goes to |
|---|---|---|
| Sidebar → CLINIC / العيادة → **New Visit / زيارة جديدة** | every page | `/workflow/` |
| Sidebar → CLINIC / العيادة → **Appointments / المواعيد** | every page | `/appointments/` (Day schedule) |
| Sidebar → CLINIC / العيادة → **Pets & Owners / الملاك والحيوانات** | every page | `/crm/owners` |
| Sidebar → PLATFORM / المنصة → **Waiting Room TV / شاشة الانتظار** | every page, opens a new tab | `/appointments/waiting-room` |
| Launcher card **Appointments & Reception / المواعيد والاستقبال** (📅) | `/` | `/appointments/` |
| Launcher card **Owners & Pets CRM / إدارة الملاك والحيوانات** (🐾) | `/` | `/crm/owners` |
| Launcher card **Reception Workspace / مساحة عمل الاستقبال** (🖥️) | `/` | `/appointments/reception` |

None of the four sidebar entries carry a role condition — every signed-in user
sees all of them. Whether the page opens is decided after the click, by the
module gate in §2.

There is **no sidebar link and no launcher card** for the week calendar
(`/appointments/calendar`), the all-pets grid (`/crm/pets`) or the Reception
Workspace beyond its launcher card. Those are reached from buttons inside other
screens, listed per screen below.

> Source: `platform/templates/base.html:105-134` (CLINIC group, no role guard),
> `platform/templates/base.html:282-285` (Waiting Room TV),
> `platform/blueprints/launcher/routes.py:32-61` (appointments and CRM cards),
> `platform/blueprints/launcher/routes.py:339-353` (Reception Workspace card)

---

## 2. Who can open what

Two gates apply to every screen in this chapter and **both must pass**:

1. **The module grant.** The role must hold the permission key that governs the
   blueprint. This is checked inside `@login_required`, so it applies to every
   route here — none of them carry a route-level role list. `super_admin`
   bypasses it entirely.
2. **The route's own role list**, where one is declared. **No route in `crm`,
   `appointments` or `workflow` declares one.** The module grant is the only
   gate in practice.

The keys are not named after the blueprints:

| Blueprint | Permission key | Label on the Roles screen |
|---|---|---|
| `crm` | `patients` | Manage Patients & Owners |
| `appointments` | `appointments` | Manage Appointments |
| `workflow` | `visits` | Medical Visits & SOAP |

`workflow` is mapped to `visits` deliberately — the one-page visit flow is the
visits module with a different front door.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-134` (`_permission_denied`, the module gate), `:140-152`
> (`_BP_PERMISSION`), `:405-428` (`has_permission`),
> `platform/models/database.py:4302-4331` (`ALL_PERMISSIONS`),
> `platform/models/database.py:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

### Effective access by role, out of the box

These are the **default** grants an administrator can change on the Roles
screen. A role whose row in `roles` has been edited follows that row instead.

| Role | `/crm/*` | `/appointments/*` | `/workflow/` |
|---|---|---|---|
| super_admin | ✅ (bypasses both gates) | ✅ | ✅ |
| clinic_owner | ✅ | ✅ | ✅ |
| branch_manager | ✅ | ✅ | ✅ |
| doctor | ✅ | ✅ | ✅ |
| nurse | ✅ | ✅ | ✅ |
| **reception** | ✅ | ✅ | ❌ **denied** |
| pharmacist | ✅ | ❌ | ✅ |
| groomer | ✅ | ✅ | ❌ |
| boarding_staff | ✅ | ✅ | ❌ |
| inventory_mgr | ❌ | ❌ | ❌ |
| finance | ❌ | ❌ | ❌ |
| hr | ❌ | ❌ | ❌ |
| support_admin | ❌ | ❌ | ❌ |
| auditor | ❌ | ❌ | ❌ |

**Reception cannot open the walk-in workflow page on default permissions.** See
[Known limits](#21-known-limits), item 1.

When a gate refuses, the user gets the red flash *"You don't have permission to
access this page."* and is sent to the launcher. A request to a path starting
`/api/` or one that asks for JSON gets `403 {"ok": false, "error": "forbidden"}`
instead.

Two routes have **no `@login_required` at all** — `/appointments/waiting-room`
and `/appointments/api/queue`. They are gated by a shared token instead; see
§9.

### CSRF and JavaScript

Every POST is CSRF-checked. The token is **injected into every form by
JavaScript on page load**, not written into the HTML by the templates. A browser
with JavaScript disabled can read these screens but cannot save anything.

> Source: `platform/app.py:349-356` (CSRF enforcement),
> `platform/models/security.py:270-283` (`validate_csrf`),
> `platform/static/js/platform.js:132-145` (token injection),
> `platform/templates/base.html:13` (`<meta name="csrf-token">`)

---

## 3. Owners list — `/crm/owners`

**What it is for.** The client register, and the only place a new client can be
created outside the walk-in workflow page.

**How to reach it.** Sidebar → **Pets & Owners / الملاك والحيوانات**; launcher
card **Owners & Pets CRM**; the **← Owners List / ← قائمة الملاك** button on the
new-owner form; the **👥 Owners / الملاك** button on the all-pets grid.

**Who can open it.** Any role holding `patients` (§2).

### Controls

| Control | Bilingual label | What it does |
|---|---|---|
| Top-right button | ➕ **New Owner** / **مالك جديد** | Opens `/crm/owners/new` (§4) |
| Search box | *Search by name, phone, or email… / ابحث بالاسم أو الهاتف أو البريد…* | GET `?q=`. Matches `full_name`, `phone`, `whatsapp_phone`, `email` — substring, case-sensitivity follows the database collation |
| 🔍 **Search / بحث** | — | Submits the search |
| ✕ **Clear / مسح** | — | Only shown when a search is active; returns to the unfiltered list |
| Row click | — | Opens the owner profile |
| **View / عرض** | — | Opens the owner profile |
| **Edit / تعديل** | — | Opens the edit form |

The Arabic name (`full_name_ar`) is **not searched**. Typing an Arabic name here
finds nothing even when the record holds it.

### Columns

| Column | Bilingual header | Content |
|---|---|---|
| Owner | **Owner / المالك** | Two-letter avatar, name (Arabic name shown instead when the interface is in Arabic and `full_name_ar` is filled), e-mail underneath |
| Phone | **Phone / الهاتف** | 📱 `phone`; 💬 `whatsapp_phone` on a second line when it differs |
| Pets | **Pets / الحيوانات** | 🐾 count of rows in `pets` for this owner |
| Balance | **Balance / الرصيد** | Reads the stored `owners.outstanding_balance` column — **not** computed from invoices. See Known limits, item 4 |
| Status | **Status / الحالة** | ⭐ **VIP / مميز** when `vip_flag` is set, otherwise *Standard / عادي*; plus 🎁 and the loyalty point balance when it is above zero |
| Actions | **Actions / إجراءات** | View / Edit |

### Sorting, paging and counts

- Unfiltered: newest first (`created_at DESC`), 20 per page.
- Searched: alphabetical by `full_name`, 20 per page.
- The **Total Owners / إجمالي الملاك** chip and the page count come from a
  *different* query than the rows. See Known limits, item 5.
- Empty state offers ➕ **Add First Owner / إضافة أول مالك**.

> Source: `platform/blueprints/crm/routes.py:217-238`,
> `platform/models/database.py:3027-3060` (`list_owners`, `count_owners`),
> `platform/templates/crm/owners_list.html:7-12` (top button), `:212-218`
> (search), `:222-287` (table), `:291-315` (paging), `:317-323` (empty state)

---

## 4. New owner — `/crm/owners/new`

**What it is for.** Registering a client.

**How to reach it.** ➕ **New Owner / مالك جديد** on the owners list, or the
**Add First Owner** button in the empty state.

**Who can open it.** Any role holding `patients`.

### Fields

Three cards. Only **Full Name (English)** is required — by both the browser
(`required`) and the server.

**👤 Basic Information / البيانات الأساسية**

| Field | Label | Type | Required | Notes |
|---|---|---|---|---|
| `full_name` | Full Name (English) / الاسم الكامل (إنجليزي) | text | **Yes** | Empty → red flash *"Full name is required."*, form re-rendered with what you typed |
| `full_name_ar` | Full Name (Arabic) / الاسم الكامل (عربي) | text, RTL | No | Saved by a second UPDATE after the row is created |
| `preferred_doctor` | Preferred Doctor / الطبيب المفضل | free text | No | Free text, not a dropdown — nothing validates it against the staff list |

**📞 Contact Details / بيانات التواصل**

| Field | Label | Type | Required | Notes |
|---|---|---|---|---|
| `phone` | Phone / الهاتف | tel | No | Checked for duplicates, see below |
| `whatsapp_phone` | WhatsApp Number / رقم واتساب | tel | No | Hint: *Leave blank if same as phone / اتركه فارغاً إذا كان نفس رقم الهاتف*. Nothing copies the phone into it if you do |
| `email` | Email Address / البريد الإلكتروني | email | No | |
| `preferred_contact` | Preferred Contact Method / وسيلة التواصل المفضلة | select | No | WhatsApp / واتساب · Phone / الهاتف · Email / البريد الإلكتروني. Defaults to WhatsApp |
| `address` | Address (English) / العنوان (إنجليزي) | text | No | |
| `address_ar` | Address (Arabic) / العنوان (عربي) | text, RTL | No | Saved by the same second UPDATE as the Arabic name |

**⚙️ Preferences & Notes / التفضيلات والملاحظات**

| Field | Label | Type | Default | Notes |
|---|---|---|---|---|
| `vip_flag` | Mark as VIP Client / تعيين كعميل مميز | checkbox | off | Drives the ⭐ badge on the list and profile only |
| `marketing_consent` | Consent to receive reminders & offers / الموافقة على استقبال التذكيرات والعروض | checkbox | **on** | Stored, but nothing reads it — Known limits, item 9 |
| `notes` | Internal Notes / ملاحظات داخلية | textarea | — | Shown on the profile |

### Duplicate mobile numbers

The server compares **normalised** numbers before inserting: Arabic-Indic digits
are folded to ASCII, all non-digits stripped, the Egyptian country code and
leading zeros removed. `0100 123 4567`, `+201001234567` and `٠١٠٠١٢٣٤٥٦٧` are
one number to it.

If the number already belongs to somebody, the save is refused with **HTTP 409**
and the red flash names the existing client:
*"<message> Open <name> instead, or use a different number."*

The form is re-rendered so nothing you typed is lost. **There is no clickable
link to that client** — the route hands the template `duplicate_owner_id` and
`duplicate_owner_name`, and the template ignores both. Known limits, item 6.

### Buttons

| Button | Effect |
|---|---|
| ✅ **Create Owner / إنشاء مالك** | Saves, writes an audit entry (`create_owner`), green flash *"Owner '<name>' created successfully."*, redirects to the new owner's profile |
| **Cancel / إلغاء** | Back to the owners list, nothing saved |
| **← Owners List / ← قائمة الملاك** (top right) | Same as Cancel |

> Source: `platform/blueprints/crm/routes.py:245-314`,
> `platform/models/database.py:3068-3079` (`DuplicatePhone`), `:3081-3099`
> (`normalise_phone`), `:3139-3153` (`create_owner`),
> `platform/templates/crm/owner_form.html:146-267`

---

## 5. Owner profile — `/crm/owners/<owner_id>`

**What it is for.** Everything the desk needs about one client on one page:
their animals, their money, their bookings, what was sent to them, and their
loyalty points.

**How to reach it.** Clicking a row or **View** on the owners list; after
creating or editing a client; the **👤 Owner** links on the appointment detail
and pet record screens.

**Who can open it.** Any role holding `patients`. An unknown id gives the flash
*"Owner not found."* and returns to the list.

### Top-right buttons

| Button | Goes to |
|---|---|
| 🐾 **Add Pet / إضافة حيوان** | `/crm/pets/new?owner_id=<id>` |
| 💳 **Account / الحساب** | `/finance/owners/<id>/credit` — a **Finance** screen, so it needs the `invoicing` grant, which doctor, nurse and pharmacist do not hold |
| ✏️ **Edit / تعديل** | `/crm/owners/<id>/edit` |
| ← **Back / رجوع** | Owners list |

### Left column — profile card

Name (Arabic name shown when the interface is Arabic and it is filled), the ⭐
**VIP Client / عميل مميز** badge when set, then: Phone / الهاتف, WhatsApp /
واتساب, Email / البريد الإلكتروني, Address / العنوان, Preferred Contact / وسيلة
التواصل المفضلة, Preferred Doctor / الطبيب المفضل, Member Since / عميل منذ.
Two inline links: ✏️ **Edit / تعديل** and 📅 **Book Appt / حجز موعد** (which
opens the booking form pre-filled with this client).

### Statistics strip

| Tile | Bilingual label | Where the number comes from |
|---|---|---|
| Pets | **Pets / الحيوانات** | Count of the animal cards below |
| Total Visits | **Total Visits / إجمالي الزيارات** | `COUNT(*)` over `visits` for this owner |
| Balance EGP | **Balance EGP / الرصيد بالجنيه** | Sum of `due_amount` over invoices whose status is neither `Paid` nor `Cancelled` — the same definition Finance uses, so the two screens agree |
| Last Visit | **Last Visit / آخر زيارة** | `MAX(visit_date)` |
| No-Shows | **No-Shows / عدم حضور** | Count of appointments with status `No-Show` |

### Sections

| Section | Bilingual heading | Content | Cap |
|---|---|---|---|
| Pets | 🐾 **Pets / الحيوانات** | One card per animal — species emoji, name, age, breed, *Neutered / محوّل* pill. ➕ **Add Pet / إضافة حيوان** header button; when there are none, an *Add first pet → / أضف أول حيوان ←* link | all |
| Recent Visits | 🩺 **Recent Visits / آخر الزيارات** | Date, pet, type, chief complaint, status | 5, newest first |
| Invoices | 🧾 **Invoices / الفواتير** | Invoice number, Date / التاريخ, Pet / الحيوان, Status / الحالة, Total / الإجمالي, Due / المستحق. Header shows *Outstanding / المستحق*. **Unpaid and uncancelled invoices are listed first**, then newest first. Each number links to the Finance invoice page | 25 |
| Appointment History | 📅 **Appointment History / سجل المواعيد** | Date / التاريخ, Time / الوقت, Pet / الحيوان, Type / النوع, Doctor / الطبيب, Status / الحالة. Sub-line totals: *N booked · N no-shows · N cancelled*. No-shows and cancellations are **included** in the list | 25, newest first |
| Communication History | 💬 **Communication History / سجل التواصل** | WhatsApp messages already sent, merged with reminders still queued, newest first. ✉️ **Send Message / إرسال رسالة** opens the WhatsApp send centre — a **WhatsApp** module screen, so it needs the `whatsapp` grant | 20 of each |
| Notes | 📝 **Notes / ملاحظات** | The internal notes field | — |
| Loyalty Points | 🎁 **Loyalty Points / نقاط الولاء** | See below | history capped at 30 |

### Loyalty panel

Three read-outs: **BALANCE / الرصيد** (points), **REDEEM VALUE / قيمة الاستبدال**
(EGP if redeemed, at 1 point = 0.50 EGP), **EARN RATE / معدل الكسب** (1 point per
10 EGP paid — this matches what Finance actually awards when an invoice is paid).

| Control | Effect |
|---|---|
| 🎁 **Redeem 100 pts → 50 EGP credit / استبدال 100 نقطة ← رصيد 50 جنيه** | Shown only when the balance is 100 or more. Asks *"Redeem 100 points for 50 EGP credit?"* first. POSTs to `/crm/owners/<id>/redeem-points`: deducts 100 points and writes a `redemption` row in the points ledger. **No money credit is created anywhere in Finance** — Known limits, item 7 |
| (below 100 points) | A line reading *Minimum N more points needed to redeem (need 100, have N)* |
| ⚙️ **Manual Adjustment / تعديل يدوي** | A collapsible block with **Points (+ or -) / النقاط (+ أو -)** (required, integer, may be negative) and **Reason / السبب** (defaults to `Manual adjustment`), and an **Apply / تطبيق** button. POSTs to `/crm/owners/<id>/adjust-points`. A zero or unparsable value is refused with *"Enter a non-zero adjustment."* Despite the "admin" wording in the code, **any role holding `patients` can use this** — Known limits, item 8 |
| History table | Date / التاريخ, Reason / السبب, By / بواسطة, Points / النقاط |

Neither loyalty action writes an audit entry.

> Source: `platform/blueprints/crm/routes.py:321-439` (page), `:61-81`
> (`_get_owner_stats`), `:446-484` (redeem), `:491-529` (adjust),
> `platform/blueprints/finance/routes.py:60-87` (`_award_points`, earn rate),
> `platform/templates/crm/owner_detail.html:7-20` (top buttons), `:296-380`
> (profile card), `:384-408` (stats), `:411-443` (pets), `:447-471` (visits),
> `:475-525` (invoices), `:529-578` (appointments), `:582-610` (comms), `:614-618`
> (notes), `:624-732` (loyalty)

---

## 6. Edit owner — `/crm/owners/<owner_id>/edit`

Same form as §4 with three differences:

1. The heading reads **Update owner information / تحديث بيانات المالك**, the
   save button reads 💾 **Save Changes / حفظ التغييرات**, and the top-right
   button is **← Back to Profile / ← العودة إلى الملف**.
2. A hidden `_seen_updated_at` field carries the record's timestamp as it was
   when you opened the form. If somebody else saved the same client meanwhile,
   your save is **refused with HTTP 409** and a red flash naming who changed it
   and when: *"<name> changed this while you had it open (<time>). Your changes
   were NOT saved. Reopen it and apply them again so nothing of theirs is
   lost."* Your typing is preserved on screen.
3. The duplicate-mobile check excludes this client, so re-saving without
   changing the number is fine.

Success writes an audit entry (`update_owner`), flashes *"Owner updated
successfully."* and returns to the profile.

> Source: `platform/blueprints/crm/routes.py:567-650`,
> `platform/models/concurrency.py:72-96` (`guard`),
> `platform/templates/crm/owner_form.html:150-152` (the stamp)

---

## 7. All pets — `/crm/pets`

**What it is for.** Finding an animal when you know the pet's name or microchip
but not the owner's.

**How to reach it.** No sidebar link and no launcher card. The only route in is
typing the URL, or arriving from a redirect. Both `/crm/pets` and `/crm/pets/`
work.

**Who can open it.** Any role holding `patients`.

### Controls

| Control | Bilingual label | What it does |
|---|---|---|
| Text box | *Search by name or microchip… / بحث بالاسم أو الميكروشيب…* | Substring match on `pet_name` **or** `microchip_id`. Does not match owner name, breed or species |
| Species select | **All Species / جميع الأنواع** + one option per species found | Filters the results |
| **Filter / تصفية** | — | Submits |
| **Clear / مسح** | — | Returns to the unfiltered grid |
| Counter | *N pet(s) found / N حيوان* | Counts the cards on screen |
| 👥 **Owners / الملاك** (top right) | — | Owners list |
| + **New Pet / حيوان جديد** (top right) | — | **Broken** — leads to an error, see Known limits, item 2 |

### Cards

Species emoji (cat/dog/bird/rabbit, otherwise 🐾), pet name, `species · breed`, a
**Neutered / محوّل** pill when set, then owner name, Sex / الجنس (hidden when
`Unknown`), weight, microchip, and allergies in red with a ⚠ when present.
Clicking a card opens the pet record.

**The grid never shows more than 100 animals**, and the species filter runs
*after* that cut. Known limits, item 3.

Empty state: **Clear filters / مسح التصفية** when a filter is on, otherwise
+ **Add First Pet / إضافة أول حيوان** (which hits the same broken link).

> Source: `platform/blueprints/crm/routes.py:657-679`,
> `platform/models/database.py:3185-3202` (`list_pets`),
> `platform/templates/crm/pets_list.html:6-13` (top buttons), `:18-33`
> (filters), `:37-85` (grid), `:87-103` (empty state)

---

## 8. New pet — `/crm/pets/new?owner_id=<id>`

**What it is for.** Registering an animal against a client.

**How to reach it.** 🐾 **Add Pet / إضافة حيوان** on the owner profile (top
right or the Pets section header), *Add first pet →* in the empty Pets section,
or *Add a pet first →* on the booking form when the selected client has none.

**`owner_id` is mandatory** and comes from the query string or the form. Without
it the page immediately flashes *"Owner ID is required to create a pet."* and
returns to the owners list. An unknown owner gives *"Owner not found."*

**Who can open it.** Any role holding `patients`.

### Fields

Five cards. Only **Pet Name** is required; **Species** is marked with a `*` but
always has a value because *Dog* is pre-selected.

**🐾 Pet Identity / بيانات الحيوان**

| Field | Label | Type | Notes |
|---|---|---|---|
| `species` | Species / النوع | radio tiles | 🐕 Dog / كلب · 🐈 Cat / قطة · 🐰 Rabbit / أرنب · 🐦 Bird / طائر · 🐹 Hamster / هامستر · 🐟 Fish / سمكة · 🐢 Turtle / سلحفاة · 🐾 Other / أخرى. **Dog is pre-selected** on a new record |
| `pet_name` | Pet Name / اسم الحيوان | text | **Required.** Empty → *"Pet name is required."* |
| `breed` | Breed / السلالة | text | Free text |
| `sex` | Sex / الجنس | select | Male / ذكر · Female / أنثى · Unknown / غير معروف (default) |
| `dob` | Date of Birth / تاريخ الميلاد | date | Drives the age shown on the profile and record. Under a year, age reads in months |

**⚖️ Physical Details / البيانات الجسدية**

| Field | Label | Type | Notes |
|---|---|---|---|
| `weight_kg` | Weight (kg) / الوزن (كجم) | number, step 0.1, min 0 | Blank is stored as no value |
| `color` | Color / Markings / اللون / العلامات | text | |
| `microchip_id` | Microchip ID / رقم الميكروشيب | text | Placeholder suggests 15 digits; nothing enforces a length or checks for duplicates |
| `neutered` | Neutered / Spayed / محوّل / معقّم | checkbox | |

**Medical**

| Field | Label | Type | Notes |
|---|---|---|---|
| `allergies` | Known Allergies / الحساسية المعروفة | textarea | Surfaces as a red banner on the pet record, in the walk-in workflow's patient panel, and on the today's-queue rows |
| `chronic_conditions` | Chronic Conditions / الأمراض المزمنة | textarea | |
| `diet_notes` | Diet Notes / ملاحظات التغذية | textarea | Written by a separate UPDATE after the row is created; a failure there is swallowed silently |

**Insurance**

| Field | Label | Type | Notes |
|---|---|---|---|
| `insurance_provider` | Insurance Provider / شركة التأمين | text | |
| `policy_number` | Policy Number / رقم الوثيقة | text | |
| `policy_expiry` | Policy Expiry Date / تاريخ انتهاء الوثيقة | date | The pet record flags it ⚠️ **EXPIRED / منتهية** when past, ⏰ *Expiring soon / تنتهي قريباً* within a month |

Plus a free **notes** textarea.

### Buttons

| Button | Effect |
|---|---|
| ✅ **Register Pet / تسجيل الحيوان** | Saves, writes an audit entry (`create_pet`), flashes *"Pet '<name>' added successfully."*, redirects to the pet record |
| **Cancel / إلغاء** | Back to the owner profile |

> Source: `platform/blueprints/crm/routes.py:686-756`,
> `platform/models/database.py:3212-3226` (`create_pet`),
> `platform/templates/crm/pet_form.html:193-194` (form + hidden owner),
> `:202-227` (species), `:229-253` (identity), `:258-290` (physical), `:293-315`
> (medical), `:318-340` (insurance), `:343-348` (notes), `:351-363` (buttons)

---

## 9. Pet record — `/crm/pets/<pet_id>`

**What it is for.** One animal's whole history in one place.

**How to reach it.** A pet card on the owner profile or the all-pets grid; the
**View Medical Record / عرض السجل الطبي** button on an appointment.

**Who can open it.** Any role holding `patients`. An unknown id flashes *"Pet not
found."* and returns to the **owners** list.

### Top-right buttons

| Button | Goes to / does | Grant needed beyond `patients` |
|---|---|---|
| 📅 **New Appointment / موعد جديد** | Booking form, pre-filled with this owner and pet | `appointments` |
| ✨ **AI Summary / ملخص ذكي** | Opens a dark modal and POSTs to `/ai/pet-summary/<id>` for a narrative clinical summary. The modal has 🖨 **Print / طباعة** and **Close / إغلاق**. On failure it shows *"⚠️ Could not generate summary. Is the AI service running?"* | `ai` — held by **clinic_owner and doctor only** |
| 🩻 **Imaging / التصوير الطبي** | This pet's imaging studies | `imaging` |
| ✏️ **Edit / تعديل** | Edit form (§10) | — |
| 📄 **Medical History PDF / السجل الطبي PDF** | Downloads a PDF (§11) | — |
| ← **Owner / المالك** | The owner profile | — |

### Left column — patient card

Species emoji, name, a **Neutered / محوّل** pill, then Weight / الوزن, Date of
Birth / تاريخ الميلاد (with the calculated age), Color / اللون, Microchip /
الميكروشيب, Chronic Conditions / الأمراض المزمنة, and Insurance / التأمين with
*Policy: / رقم الوثيقة:* and *Expires: / تنتهي في:* plus the expiry flags.

Allergies appear as a **red ⚠️ Allergies: / الحساسية: banner**, not as a row.

Below: a mini owner card linking to the profile, and inline ✏️ **Edit / تعديل**
and 📅 **Book / حجز** links.

### Right column

**⚖️ Weight History / سجل الوزن** — a chart of up to 20 weights recorded on
visits, oldest first, with *Last N measurements / آخر N قياس*.

**📋 Medical Timeline / السجل الزمني الطبي** — every recorded event, newest
first, with an event count. Thirteen event types, each with its own icon and
deep link:

| Icon | Type | Bilingual label | Links to |
|---|---|---|---|
| 🩺 | visit | — | Visit detail |
| 💉 | vaccine | — | Vaccination certificate |
| 🔧 | surgery | — | (no detail page) |
| ✂️ | grooming | — | Grooming booking |
| 🧾 | invoice | — | Finance invoice |
| 🔬 | lab | — | Lab result |
| 🧬 | diagnosis | Diagnosis / تشخيص | The visit it came from |
| 💊 | prescription | Prescription / وصفة طبية | Pharmacy prescription. Summary carries the item count, e.g. *Active · 3 💊* |
| 🏥 | inpatient | Inpatient admission / إقامة داخلية | Stay detail |
| 🏨 | boarding | Boarding stay / إقامة إيواء | Boarding booking |
| 🩻 | imaging | Imaging study / دراسة تصويرية | Imaging study |
| 📹 | telemed | Telemedicine session / جلسة طب عن بُعد | Session detail |
| 🛍️ | purchase | Pet shop purchase / مشتريات من المتجر | Pet shop order |
| 🔔 | followup | Follow-up due / متابعة مستحقة | The visit it came from |

Imaging, telemedicine and pet-shop events come from tables that only exist once
their module has been used; on a fresh install those three simply do not appear,
which is not an error. **Every link lands in a different module and is subject to
that module's grant** — a nurse clicking a 🧾 invoice event is bounced to the
launcher.

**Quick actions row** — 📅 New Appointment / موعد جديد · 🩺 New Visit / زيارة
جديدة · 🩻 Imaging / التصوير الطبي · 🏥 Inpatient / القسم الداخلي · ⚕️ Drug &
Dose Check / فحص الأدوية والجرعات. Each needs its own module's grant.

**💉 Vaccinations / التطعيمات** — a table of Vaccine / اللقاح, Brand / الماركة,
Administered / تاريخ الإعطاء, Next Due / الجرعة التالية, By / بواسطة, with an
➕ **Add / إضافة** button opening the clinical vaccination form.

**📝 Notes / ملاحظات** — the free-text notes field.

> Source: `platform/blueprints/crm/routes.py:763-812` (page), `:84-210`
> (timeline assembly, `_event_url`, `_extra_pet_events`),
> `platform/models/database.py:3242-3285` (`get_pet_timeline`),
> `platform/blueprints/ai_assistant/routes.py:586-589` (AI summary route),
> `platform/templates/crm/pet_detail.html:7-24` (top buttons), `:210-300`
> (patient card), `:303-318` (owner mini), `:327-347` (weight), `:349-395`
> (timeline), `:396-403` (quick actions), `:407-445` (vaccinations), `:450-455`
> (notes), `:470-500` (modal), `:506-538` (JS)

---

## 10. Edit pet — `/crm/pets/<pet_id>/edit`

Identical form to §8. Differences:

- The button reads 💾 **Save Changes / حفظ التغييرات**; **Cancel / إلغاء**
  returns to the pet record; the top-right button is **← Back / رجوع** to the
  record.
- The owner cannot be changed — the hidden `owner_id` is the existing one.
- **There is no concurrent-edit guard here.** Two people editing the same animal
  will overwrite each other silently. Known limits, item 12.
- Success writes an audit entry (`update_pet`), flashes *"Pet updated
  successfully."*, returns to the record.

> Source: `platform/blueprints/crm/routes.py:819-889`,
> `platform/models/database.py:3228-3240` (`update_pet`)

---

## 11. Medical history PDF — `/crm/pets/<pet_id>/history.pdf`

A GET that downloads `<Pet_Name>_medical_history.pdf`. Not a screen — there is
no preview and no options.

Contents, in order: a clinic header (see below) with *Patient Medical History
Report* and the generation date; a patient block (species, breed, sex, age,
microchip, neutered, **ALLERGIES in red** when present, chronic conditions); the
owner's name and phone; a **Vaccination Records** table (Vaccine, Date Given,
Next Due, Batch / Notes) when there are any; and **Visit History** — every visit,
newest first, each with date, type, doctor, weight, complaint, first diagnosis,
latest treatment plan and notes.

Arabic names render correctly — the generator reshapes text and substitutes an
Arabic-capable font.

**The clinic name in the header is always the words "Animal Hospital"** — Known
limits, item 10.

> Source: `platform/blueprints/crm/routes.py:896-1052`

---

## 12. Day schedule — `/appointments/` and `/appointments/schedule`

**What it is for.** One day's bookings as an hourly agenda. This is the default
Appointments screen.

**How to reach it.** Sidebar → **Appointments / المواعيد**; launcher card
**Appointments & Reception**; 📋 **Today / اليوم** on the week calendar; **Back
to Schedule / العودة إلى الجدول** on an appointment; *view all / عرض الكل* on the
Reception Workspace.

**Who can open it.** Any role holding `appointments`.

### Controls

| Control | Bilingual label | Effect |
|---|---|---|
| ➕ **New Appointment / موعد جديد** (top right) | — | Booking form, pre-filled with the day on screen |
| 📆 **Week View / عرض الأسبوع** (top right) | — | `/appointments/calendar` |
| **← Prev / ← السابق** | — | The day before |
| Date picker | — | Jumps to any date; submits on change |
| **Next → / التالي ←** | — | The day after |
| Appointment block | — | Opens the appointment |
| ➕ **Book Appointment / حجز موعد** (empty state) | — | Booking form for that day |

`?date=` accepts `YYYY-MM-DD`. Anything unparsable silently falls back to today.
A **Today / اليوم** badge appears next to the date when you are on it.

### Statistics

**Total / الإجمالي** · **Pending / قيد الانتظار** (`Scheduled` + `Confirmed`) ·
**Checked In / تم الوصول** · **Completed / مكتمل**. All four count only the
appointments loaded for that day.

### Agenda

One row per hour from **08:00 to 20:00**. Each appointment block shows the time
range, the type, an ⚡ **Urgent / عاجل** or 🚨 **Emergency / طوارئ** pill when the
priority is set, a status badge, then 🐾 pet · 👤 owner · 🩺 doctor · the first
50 characters of the reason. Empty hours read *No appointments / لا توجد مواعيد*.

Status colours: Scheduled blue · Confirmed teal · Checked-in purple · Completed
green · Cancelled red · No-Show grey.

**Appointments before 08:00 or from 21:00 onwards are counted in the totals but
appear in no hour row.** Known limits, item 13.

The day is capped at 200 appointments.

> Source: `platform/blueprints/appointments/routes.py:162-216`, `:26-40`
> (status colours and vocabularies), `platform/models/database.py:3288-3306`
> (`list_appointments`),
> `platform/templates/appointments/schedule.html:7-14` (top buttons), `:162-174`
> (day nav), `:176-197` (stats), `:199-241` (agenda), `:243-254` (empty state)

---

## 13. Week calendar — `/appointments/calendar`

**What it is for.** Seven days side by side.

**How to reach it.** 📆 **Week View / عرض الأسبوع** on the day schedule. No
sidebar link, no launcher card.

**Who can open it.** Any role holding `appointments`.

`?week=YYYY-MM-DD` picks the week; the date given is snapped back to its Monday.
An unparsable value falls back to the current week.

| Control | Bilingual label | Effect |
|---|---|---|
| **← Prev Week / ← الأسبوع السابق** | — | Seven days back |
| **This Week / هذا الأسبوع** | — | Current week |
| **Next Week → / الأسبوع التالي ←** | — | Seven days forward |
| Day header click | — | That day's schedule |
| Appointment chip | — | The appointment |

Seven columns, Monday to Sunday, today highlighted. Empty days read *No
appointments / لا توجد مواعيد*. A **Status: / الحالة:** legend sits underneath,
with the note *Click any day to view its schedule / اضغط على أي يوم لعرض جدوله*.

The week is capped at 500 appointments.

> Source: `platform/blueprints/appointments/routes.py:223-265`,
> `:47-60` (`_week_bounds`),
> `platform/templates/appointments/calendar.html:7-10` (top buttons), `:142-151`
> (week nav), `:152-189` (grid), `:191-209` (legend)

---

## 14. New appointment — `/appointments/new`

**What it is for.** Booking.

**How to reach it.** ➕ **New Appointment / موعد جديد** on the day schedule,
week calendar, Reception Workspace, appointment detail and pet record; 📅 **Book
Appt / حجز موعد** on the owner profile; the pet chips and 📅 **Book Appointment
for this Owner / حجز موعد لهذا المالك** on the Reception Workspace.

**Query parameters it honours:** `owner_id`, `pet_id`, `date`.

**Who can open it.** Any role holding `appointments`.

### Fields

**🐾 Patient / المريض**

| Field | Label | Required | Behaviour |
|---|---|---|---|
| `owner_id` | Owner / المالك | **Yes** | A select with a **type-to-search box added above it**. Typing two or more characters queries the server and replaces the options with up to 25 matches (name, phone, WhatsApp or e-mail). A single match is selected automatically. **Only the pre-selected client is in the list before you type** — the box is the way to reach everyone else. Hint: *Start typing to filter, then select / ابدأ الكتابة للتصفية ثم اختر* |
| `pet_id` | Pet / الحيوان | **Yes** | Reloads from the server whenever the owner changes; a lone pet is selected automatically. When the selected client has no animals: *ℹ️ No pets found for this owner. / لا توجد حيوانات لهذا المالك.* with an *Add a pet first → / أضف حيواناً أولاً ←* link |
| `doctor_name` | Doctor / Vet / الطبيب البيطري | No | *— Assign Doctor — / — تعيين طبيب —* plus every active user whose role is doctor, super_admin or clinic_owner, plus the clinic's configured lead vet |

**📋 Appointment Details / تفاصيل الموعد**

| Field | Label | Required | Options / default |
|---|---|---|---|
| `appointment_type` | Type / النوع | **Yes** | Radio tiles: 🩺 Consultation (default) · 💉 Vaccination · 🔧 Surgery · ✂️ Grooming · 🔬 Lab · 📋 Follow-up · 🚨 Emergency. **Labels are English only** |
| `priority` | Priority / الأولوية | No | ✅ Normal / عادي (default) · ⚡ Urgent / عاجل · 🚨 Emergency / طوارئ |
| `appt_date` | Date / التاريخ | **Yes** | Defaults to today or `?date=`. **Past dates are accepted** — Known limits, item 14 |
| `duration_min` | Duration / المدة | No | 15 / 30 (default) / 45 / 60 / 90 / 120 minutes. The end time is calculated from start + duration |
| `channel` | Channel / القناة | No | 🚶 Walk-in (default) · 💬 WhatsApp · 📞 Phone · 🌐 Online. **Labels are English only** |
| `appt_start` | Start Time / وقت البدء | **Yes** | A grid of 30-minute slots from **08:00 to 19:30**, `09:00` pre-selected. Slots already taken by the chosen doctor go grey as soon as the date or doctor changes. Hint: *Grey slots are unavailable for the selected date/doctor / الفترات الرمادية غير متاحة للتاريخ/الطبيب المحدد*. **Grey slots are still clickable** — the server refuses them on submit |

**📝 Reason & Notes / السبب والملاحظات** — `reason` (Reason for Visit / سبب
الزيارة), `symptoms` (Symptoms (if any) / الأعراض (إن وجدت)), `notes` (Internal
Notes / ملاحظات داخلية). All optional.

### What the server checks

1. **Owner and pet must both be present** — otherwise *"Owner and pet are
   required."*
2. **The pet must exist and belong to that owner** — otherwise *"That pet is no
   longer on file for this client. Please re-select the client and pet."* This
   catches a stale form and stops one client's animal being filed under
   another's name.
3. **Double-booking**, but only **when a doctor is chosen**: *"⚠️ <doctor>
   already has an appointment at <time> on <date>. Please choose a different
   slot."* and you are returned to the form with owner, pet and date preserved.
   With no doctor selected there is no such check — Known limits, item 15.

New appointments are always created with status `Scheduled`.

### Buttons

| Button | Effect |
|---|---|
| ✅ **Book Appointment / حجز الموعد** | Saves, writes an audit entry (`create_appointment`), flashes *"Appointment booked successfully."*, goes to that day's schedule |
| **Cancel / إلغاء** | Day schedule, nothing saved |

> Source: `platform/blueprints/appointments/routes.py:272-387`, `:90-117`
> (`_generate_slots`), `:120-142` (`_pet_belongs_to`), `:145-151`
> (`_slot_is_free`), `platform/models/database.py:3321-3338`
> (`create_appointment`), `platform/blueprints/crm/routes.py:543-560`
> (`owner_search_json`), `platform/static/js/platform.js:407-441`
> (`_remoteSearch`), `platform/templates/appointments/appt_form.html:153`
> (form), `:161-192` (owner/pet), `:194-203` (doctor), `:215-227` (type),
> `:229-245` (priority), `:247-251` (date), `:253-260` (duration), `:262-270`
> (channel), `:274-290` (slots), `:294-315` (notes), `:319-323` (buttons),
> `:329-393` (JS)

---

## 15. Appointment detail — `/appointments/<appt_id>`

**What it is for.** One booking, its people, and the buttons that move it
through its statuses.

**How to reach it.** Any appointment block on the day schedule, week calendar or
Reception Workspace; the appointment history table on the owner profile.

**Who can open it.** Any role holding `appointments`. An unknown id flashes
*"Appointment not found."* and returns to the schedule.

### Top-right buttons

| Button | Shown when | Goes to |
|---|---|---|
| **← Schedule / ← الجدول** | always | That day's schedule |
| ✏️ **Reschedule / إعادة جدولة** | status is **not** Completed or Cancelled | The reschedule form (§17) |

### Left card — details

Priority and type badges, then Date / التاريخ, Time / الوقت (with the end time
and duration), Doctor / الطبيب, Channel / القناة, Reason / السبب, Symptoms /
الأعراض, Notes / ملاحظات, Checked In / تم الوصول.

**No-show risk badge.** Shown **only when the status is `Scheduled` or
`Confirmed`**. It loads asynchronously (*Loading risk… / جارٍ حساب المخاطرة…*)
and is clickable — clicking opens 📊 **No-Show Risk Factors / عوامل خطر عدم
الحضور** with the reasons, dismissible with **Dismiss / تجاهل**.

The score is 0-100, banded **high** at 60+, **medium** at 30+, **low** below:

| Contribution | Points | Reason text |
|---|---|---|
| Client has never had an appointment | +15 | *New client — no history* |
| No-show rate | up to +45 (the rate as a percentage, capped) | *No-show rate: N/M appointments (P%)* |
| Cancellation rate above 30% | +10 | *High cancellation rate (P%)* |
| Unpaid invoices | +7 each, capped at +20 | *N unpaid invoice(s)* |
| Last completed visit over 180 days ago | +12 | *Inactive — last visit N days ago* |
| Last completed visit 90-180 days ago | +5 | (no reason line) |
| Slot before 09:00 | +8 | *Early morning slot* |

### Update Status / تحديث الحالة

One button per status — **Scheduled**, **Confirmed**, **Checked-in**,
**Completed**, **Cancelled**, **No-Show**. **The button labels are English
only.** The current status is highlighted. Pressing one:

- Rejects anything outside that list with *"Invalid status: <value>"*.
- Stamps `checked_in_at` when set to **Checked-in**.
- Stamps `checked_out_at` when set to **Completed**, **No-Show** or
  **Cancelled**.
- Writes an audit entry (`update_appointment_status`).
- Flashes *"Appointment status updated to <status>."*
- Returns you to the page you came from.

There is no confirmation prompt on any of them, including Cancelled and
No-Show, and **no status change is ever blocked** — a Completed appointment can
be set back to Scheduled.

### Right column

**Owner / المالك** card with **View Profile / عرض الملف**; **Patient / المريض**
card (Name / الاسم, Species / النوع, Breed / السلالة, Sex / الجنس) with **View
Medical Record / عرض السجل الطبي**; **Quick Actions / إجراءات سريعة** with **New
Appointment / موعد جديد** (pre-filled with the same owner, pet and date) and
**Back to Schedule / العودة إلى الجدول**.

> Source: `platform/blueprints/appointments/routes.py:394-421` (page),
> `:428-449` (status POST), `:629-693` (`_noshowscore`), `:696-700` (risk API),
> `platform/models/database.py:3340-3350` (`update_appointment_status`),
> `platform/templates/appointments/appt_detail.html:6-11` (top buttons),
> `:43-77` (details), `:54-58` (risk badge), `:79-93` (status form), `:96-125`
> (owner/patient), `:127-135` (quick actions), `:140-147` (risk detail),
> `:150-196` (JS)

---

## 16. Reschedule — `/appointments/<appt_id>/edit`

**What it is for.** Moving a booking, or correcting its details.

**How to reach it.** ✏️ **Reschedule / إعادة جدولة** on the appointment.

**Who can open it.** Any role holding `appointments`. **A Completed or Cancelled
appointment cannot be edited** — you get the amber flash *"Cannot edit a
completed or cancelled appointment."* and are returned to the detail page.

### Fields

| Field | Label | Required | Notes |
|---|---|---|---|
| `appt_date` | Date * / التاريخ * | Yes | Reloads the slot grid on change. **No minimum date** |
| `doctor_name` | Doctor / الطبيب | No | *— Any — / — أي —* plus active doctors, super_admins and clinic_owners. Reloads the slot grid on change |
| `appt_start` | Time Slot * / الفترة الزمنية * | Yes | A grid of 08:00-19:30 buttons. **Taken slots are shown in red and genuinely disabled** here, with the tooltip *Already booked / محجوز بالفعل*. This appointment's own slot is excluded from the "taken" set so it does not block itself |
| `duration_min` | Duration (min) / المدة (دقيقة) | No | Recalculates the end time |
| `appointment_type` | Type / النوع | No | The seven types, **English labels only** |
| `priority` | Priority / الأولوية | No | Normal · Urgent · Emergency, **English labels only** |
| `channel` | Channel / القناة | No | Walk-in · WhatsApp · Phone · Online, **English labels only** |
| `reason` | Reason / السبب | No | |
| `notes` | Notes / ملاحظات | No | |

The **owner and pet cannot be changed** — the form has no field for either.
**The status cannot be changed here** either; use the buttons on the detail
page.

### Buttons

| Button | Effect |
|---|---|
| 💾 **Save Reschedule / حفظ إعادة الجدولة** | Re-checks double-booking when a doctor is named (*"⚠️ <doctor> already has an appointment at <time> on <date>."* → back to the form), otherwise saves, writes an audit entry (`reschedule_appointment`), flashes *"Appointment rescheduled successfully."*, returns to the detail page |
| **Cancel / إلغاء** and **← Back / ← رجوع** | Back to the detail page |

> Source: `platform/blueprints/appointments/routes.py:456-537`,
> `platform/templates/appointments/appt_edit.html:6-8` (top button), `:12-35`
> (date/doctor), `:37-52` (slots), `:54-101` (details), `:104-107` (buttons),
> `:122-154` (JS)

---

## 17. Reception Workspace — `/appointments/reception`

**What it is for.** The desk view of today: the agenda on the left, and a
lookup-and-check-in panel on the right.

**How to reach it.** Launcher card **Reception Workspace / مساحة عمل الاستقبال**
only. There is no sidebar link. The card is offered to super_admin,
clinic_owner, branch_manager and reception.

**Who can open it.** Any role holding `appointments` — the launcher card's role
list narrows who *sees* the card, not who may open the URL.

**The date is always today.** There is no date control on this screen.

### Top-right buttons

➕ **New Appointment / موعد جديد** and 📅 **Day Schedule / جدول اليوم**, both for
today.

### Statistics

**Total Today / إجمالي اليوم** · **Checked In / تم الوصول** · **Waiting /
في الانتظار** (`Scheduled` + `Confirmed`) · **Completed / مكتمل**.

### Left — today's agenda

Headed 📅 **Today's Appointments / مواعيد اليوم** with the date and an
appointment count, and an inline ➕ **Book / حجز** button. Below it, the same
hourly 08:00-20:00 agenda as the day schedule. Empty: *No appointments scheduled
for today. / لا توجد مواعيد مجدولة اليوم.* with ➕ **Book First Appointment /
احجز أول موعد**.

### Right — three panels

**🔍 Owner Lookup / البحث عن مالك**
Sub-line: *Search by name or phone to check in / ابحث بالاسم أو الهاتف لتسجيل
الوصول*. Below the box, *N owners registered* — a live count of the whole
`owners` table.

Typing two or more characters searches the server (name, phone, WhatsApp,
e-mail; first 25 matches). Fewer than two characters shows *Type at least 2
characters / اكتب حرفين على الأقل*; a failed request shows *Search failed / فشل
البحث*; no match shows *No match / لا توجد نتائج*.

Clicking a result highlights it and reveals a panel with the client's name and
phone, one chip per animal (each chip books an appointment for that pet today),
and 📅 **Book Appointment for this Owner / حجز موعد لهذا المالك**.

**This panel offers no check-in action**, despite its sub-line. Known limits,
item 16.

**🏥 Checked-In Queue / قائمة الوصول**
Sub-line *N currently checked in*. One row per appointment with status
`Checked-in`: time, pet name, a **Checked In / تم الوصول** badge, owner and
doctor. Clicking a row opens the appointment. Empty: *No patients currently
checked in / لا يوجد مرضى مسجلو الوصول حالياً*.

**🕐 Waiting / Scheduled / في الانتظار / مجدول**
Sub-line *N appointment(s) pending*. **Shows at most 8 rows**; beyond that a
line reads *+N more — view all / عرض الكل* linking to the day schedule. Each row
carries a **Check In / تسجيل وصول** button that POSTs the status straight to
`Checked-in` and returns you here. Empty: *No appointments waiting / لا توجد
مواعيد في الانتظار*.

The whole page is capped at 200 appointments for the day.

> Source: `platform/blueprints/appointments/routes.py:559-605` (page),
> `:612-624` (`api_pets`), `platform/blueprints/launcher/routes.py:339-353`
> (card), `platform/templates/appointments/reception.html:7-15` (top buttons),
> `:235-256` (stats), `:260-318` (agenda), `:324-352` (lookup), `:354-386`
> (checked-in), `:388-434` (waiting), `:441-568` (JS)

---

## 18. Waiting Room TV — `/appointments/waiting-room`

**What it is for.** A full-screen display for the waiting area. Not a staff
screen — it has no navigation, no sidebar and no controls.

**How to reach it.** Sidebar → PLATFORM → **Waiting Room TV / شاشة الانتظار**,
which opens it in a new tab.

### Who can open it — this one is different

This route and its JSON companion `/appointments/api/queue` carry **no
`@login_required`**, so the module gate never runs. Access is decided by
`_waiting_room_authorized()`:

1. **Any signed-in user** is allowed, whatever their role.
2. Otherwise the request must present the `WAITING_ROOM_TOKEN` — as `?t=<token>`
   or the `wr_token` cookie.
3. **If no token is configured at all, anonymous requests are refused.** The
   page returns **404**, and a warning is written to the log telling the
   operator to set `WAITING_ROOM_TOKEN` and open the TV on `?t=<token>` once.

Opening it once with the correct `?t=` sets a one-year `wr_token` cookie so the
page's own 30-second polling stays authorised.

**Anonymous viewers never see a client's full name.** `owner_name` is stripped
and replaced by `owner_display` — first name plus the initial of the last name
(*"Ahmed El Gohary" → "Ahmed E."*). A signed-in staff session keeps the full
name in the JSON.

### What it shows

Clinic name and address in the header, a live clock, then **Today's Queue /
قائمة اليوم** — every appointment for today with status `Scheduled`, `Confirmed`
or `Checked-in`, in start-time order.

| Column | Bilingual header | Content |
|---|---|---|
| # | **#** | Position in the queue, highlighted when checked in |
| Patient | **Patient / المريض** | Species emoji (🐶 Dog · 🐱 Cat · 🐰 Rabbit · 🦜 Bird · 🐾 other), pet name, masked owner name |
| Type | **Type / النوع** | Appointment type |
| Doctor | **Doctor / الطبيب** | Prefixed *Dr.*; a missing doctor renders as *Dr. ?* |
| Est. Wait | **Est. Wait / الانتظار المتوقع** | 🟢 **In Progress / جارٍ** when checked in; **Next up / التالي** when the estimate is zero; otherwise `~N min` |

The wait estimate is arithmetic, not a measurement: 20 minutes per position
ahead of you, less the number already checked in.

Side panel tiles: **In Queue / في الانتظار** · **In Consultation / في الكشف** ·
**Max Wait (min) / أقصى انتظار (دقيقة)** · a fourth tile reading **24** / **Yrs
of Care / سنوات من الرعاية**, which is hard-coded. Below them a rotating health
tip and a welcome ticker.

Empty: *No patients in queue right now / لا يوجد مرضى في قائمة الانتظار حالياً*
and *Walk-ins welcome / المراجعون بدون موعد مرحب بهم*.

**The patient list itself never refreshes.** Known limits, item 17.

> Source: `platform/blueprints/appointments/routes.py:705-758` (token gate),
> `:709-720` (`mask_owner_name`), `:761-798` (`_queue_rows`), `:801-839` (page),
> `:842-851` (`api_queue`),
> `platform/templates/appointments/waiting_room.html:130-143` (header),
> `:145-199` (queue), `:201-226` (stats), `:228-245` (tips/ticker), `:250-298`
> (JS)

---

## 19. New Visit — the walk-in workflow page — `/workflow/`

**What it is for.** The whole visit on one screen — client, animal, examination,
diagnosis, treatment, invoice, payment — without navigating away.

**How to reach it.** Sidebar → CLINIC → **New Visit / زيارة جديدة**. That is the
only door: there is no launcher card and no button on any other screen.

**Who can open it.** Any role holding **`visits`** — clinic_owner,
branch_manager, doctor, nurse, pharmacist and super_admin. **Not reception.**
See Known limits, item 1.

### How it works, and why that matters to you

The page itself writes nothing. Each step POSTs to the ordinary route a browser
form would post to — `/crm/owners/new`, `/crm/pets/new`, `/visits/new`,
`/visits/<id>/diagnosis`, `/visits/<id>/prescription`,
`/clinical/vaccinations/new`, `/visits/<id>/complete`,
`/finance/invoices/<id>/pay`. Two consequences you will feel:

1. **Every one of those routes applies its own module gate.** A doctor or nurse,
   who holds `visits` but not `invoicing`, will get through steps 1-5 and then
   fail at the payment button. Known limits, item 18.
2. After every write the page **re-reads the visit from the server** rather than
   trusting what it just sent, so a half-succeeded save is caught at the next
   step instead of at the end.

### The step strip

**1 Client / العميل → 2 Patient / الحيوان → 3 Examination / الفحص → 4 Diagnosis /
التشخيص → 5 Treatment / العلاج → 6 Invoice & Payment / الفاتورة والدفع**

Steps light up as you pass them and the strip scrolls the current step into view
on a phone. There is a running summary line (Client · Patient · Visit #) and a
sticky **patient panel** on the right that appears once an animal is chosen —
allergies at the top, then species, breed, sex, weight, up to four recent
visits, and the visit number.

### Step 1 — Who is the client? / من هو العميل؟

Opens on **Today's bookings / حجوزات اليوم**: every appointment for today whose
status is not Completed, Cancelled or No-Show, **checked-in patients first**,
then by start time. Each row shows the time, pet and owner name, species,
appointment type, allergies in red, and either *In the waiting room / في
الانتظار* or the raw status.

**Clicking a queue row skips step 2 entirely** — client and animal are both
known — and lands you on the examination step with the appointment's reason
pre-filled into the chief complaint. Failure to load reads *Bookings could not be
loaded. Search above instead. / تعذر تحميل الحجوزات. ابحث بالأعلى بدلاً من ذلك.*
Nobody booked reads *Nobody is booked for today. Search above for a walk-in. /
لا يوجد حجوزات اليوم. ابحث بالأعلى عن حالة طارئة.*

Below that, the search box (*Name or phone… / الاسم أو رقم الهاتف…*). Two or
more characters searches **name, Arabic name, phone or WhatsApp** — the Arabic
name **is** searched here, unlike the owners list — and returns up to 12 results
with a pet count. **Enter picks the first result.** No match reads *No client
matches that. Add them as new. / لا يوجد عميل مطابق. أضفه كعميل جديد.*

**+ New client / عميل جديد** opens an inline form and carries whatever you typed
across: a value that is all digits, spaces, `+` and `-` goes into Phone,
anything else into Full name.

| Field | Label | Required |
|---|---|---|
| `o_full_name` | Full name / الاسم بالكامل | **Yes** |
| `o_full_name_ar` | Name (Arabic) / الاسم بالعربية | No |
| `o_phone` | Phone / الهاتف | **Yes** (the CRM form does not require it) |
| `o_whatsapp_phone` | WhatsApp / واتساب | No — defaults to the phone number |
| `o_email` | Email / البريد | No |
| `o_address` | Address / العنوان | No |

**Save client & continue / حفظ العميل والمتابعة** first searches for the number.
If it is already held, nothing is created — the message reads *"This mobile
number already belongs to <name>. Opening that client — one mobile number, one
client file."* and that client is opened instead. The same happens if the server
returns 409 on a normalised match the exact-string check missed.

Clients created here get **marketing consent off**, unlike the CRM form where it
is on by default. Known limits, item 9.

### Step 2 — Which animal? / أي حيوان؟

Lists the client's animals (name, species, breed, allergies in red), or *This
client has no animals registered yet. / لا يوجد حيوانات مسجلة لهذا العميل.* —
in which case the new-patient form opens by itself.

Buttons: **+ New patient / حيوان جديد**, **← Change client / تغيير العميل**.

| Field | Label | Required | Options |
|---|---|---|---|
| `pt_pet_name` | Name / الاسم | **Yes** | |
| `pt_species` | Species / النوع | — | Cat / قطة (**default**) · Dog / كلب · Bird / طائر · Rabbit / أرنب · Other / أخرى. **Fewer options than the CRM pet form, and a different default** |
| `pt_breed` | Breed / السلالة | No | |
| `pt_sex` | Sex / الجنس | — | Male / ذكر (default) · Female / أنثى. **No Unknown option** |
| `pt_weight_kg` | Weight (kg) / الوزن (كجم) | No | |
| `pt_dob` | Date of birth / تاريخ الميلاد | No | |
| `pt_allergies` | Allergies / الحساسية | No | Placeholder: *Anything that must never be prescribed / أي شيء يجب ألا يوصف أبداً* |

**Save patient & continue / حفظ الحيوان والمتابعة** may select the wrong animal
when the client already has several. Known limits, item 19.

### Step 3 — Examination / الفحص

Above the fields, the animal's allergies as a ⚠ banner and its recent visits.

| Field | Label | Required | Notes |
|---|---|---|---|
| `v_chief_complaint` | Chief complaint / الشكوى الرئيسية | **Yes** | Empty → *What is the animal here for? / ما سبب الزيارة؟* |
| `v_symptoms` | Symptoms / الأعراض | No | |
| `v_visit_type` | Visit type / نوع الزيارة | — | Consultation / كشف (default) · Follow-up / متابعة · Vaccination / تطعيم · Emergency / طوارئ · Surgery / جراحة |
| `v_doctor_name` | Doctor / الطبيب | No | Pre-filled with the signed-in user's own name. Free text |

**Vital signs / العلامات الحيوية** — Weight / الوزن (pre-filled from the
animal's record), Temperature (°C) / الحرارة, Heart rate / النبض, Respiratory
rate / التنفس.

As you type, values outside the general adult reference range are outlined and a
warning appears: *Outside the usual range for a <species>: … / خارج المعدل
المعتاد لـ …* followed by *General adult reference only — age, stress and recent
activity all move these. / مرجع عام للبالغين فقط — العمر والتوتر والنشاط الحديث
تؤثر جميعها.* **Nothing is blocked.**

| Species | Temp °C | Heart rate | Respiratory rate |
|---|---|---|---|
| Dog | 37.8-39.2 | 70-160 | 10-30 |
| Cat | 38.1-39.2 | 140-220 | 20-30 |
| Rabbit | 38.3-39.4 | 180-250 | 30-60 |

Any other species gets no range check at all.

**Start visit & continue / بدء الزيارة والمتابعة** creates the visit. If the
visit type is Vaccination, the vaccination section on step 5 is opened
automatically. Failure reads *Could not start the visit. / تعذر بدء الزيارة.*

### Step 4 — Diagnosis / التشخيص

Hint: *At least one diagnosis is required before the visit can be completed. /
مطلوب تشخيص واحد على الأقل قبل إنهاء الزيارة.*

| Field | Label | Required | Options |
|---|---|---|---|
| `d_diagnosis_text` | Diagnosis / التشخيص | **Yes** | Empty → *A diagnosis is required. / التشخيص مطلوب.* |
| `d_severity` | Severity / الشدة | — | Mild / خفيف · Moderate / متوسط (**default**) · Severe / شديد |
| `d_diagnosis_notes` | Notes / ملاحظات | No | |

**Suggest differentials / اقترح تشخيصات** — shown only when the clinic has AI
configured; the whole strip is hidden otherwise. It sends the complaint,
symptoms, species, vitals and visit history and returns ranked suggestions, each
with a likelihood pill, a *why*, a *To confirm or exclude / للتأكيد أو الاستبعاد*
line, and a **Use this / استخدم هذا** button that fills the diagnosis field.
Red flags come back as *Worth ruling out urgently / يستحق الاستبعاد بشكل عاجل*.

**It never fills the field on its own.** If the model cannot be reached you get
*"The suggestion service could not be reached. Nothing was checked."* — never
silence. Note that `/ai/*` needs the `ai` grant, held by clinic_owner and doctor
only.

**Save diagnosis & continue / حفظ التشخيص والمتابعة** re-reads the visit and
refuses to advance if the diagnosis did not land: *The diagnosis did not save. /
لم يتم حفظ التشخيص.*

### Step 5 — Treatment / العلاج

The animal's allergies are repeated at the top of this step.

**Medication rows.** One row is added automatically when the visit starts;
**+ Add medication / إضافة دواء** adds more, ✕ removes one. Each row: Medication
/ الدواء · Dose / الجرعة · Frequency / التكرار (placeholder `BID`) · Duration /
المدة (placeholder `7 days`) · Qty / الكمية (number, minimum 1, default 1). Rows
with an empty medication name are ignored. Route is always sent as `Oral` and
unit as `unit` — neither is on the form.

**Check interactions / فحص التداخلات** — again only when AI is configured. It
takes the medications already on file for this animal **from the server**, adds
what you have typed, and reports a severity band: Severe interaction / تداخل
شديد · Moderate / متوسط · Mild / خفيف · No interaction found / لا يوجد تداخل ·
Not checked / لم يتم الفحص. With no medication typed it says *Enter a medication
first. / أدخل اسم الدواء أولاً.* If the check cannot run it says so explicitly:
*"The interaction check could not run. This is NOT a statement that the
combination is safe."*

**A vaccination was given / تم إعطاء تطعيم** — a checkbox that reveals:

| Field | Label | Notes |
|---|---|---|
| `vx_vaccine_name` | Vaccine / التطعيم | Rabies / السعار · DHPP · Bordetella · Leptospirosis · Feline FVRCP · FeLV · Other… / أخرى…. Defaults to Feline FVRCP for a cat |
| `vx_custom_vaccine` | Vaccine name / اسم التطعيم | Only shown when *Other…* is chosen; naming it is then required |
| `vx_vaccine_brand` | Brand / الماركة | |
| `vx_batch_number` | Batch number / رقم التشغيلة | |
| `vx_dose_number` | Dose number / رقم الجرعة | Minimum 1, default 1 |
| `vx_site` | Site / موضع الحقن | Subcutaneous / تحت الجلد (default) · Intramuscular / عضلي · Intranasal / أنفي |
| `vx_administered_at` | Given on / تاريخ الإعطاء | Defaults to today |
| `vx_next_due_at` | Next dose due / الجرعة القادمة | **Auto-filled 12 months ahead** of the given date and recalculated whenever the vaccine or date changes |

Under the fields: *The owner is reminded by WhatsApp when this falls due. / يتم
تذكير المالك عبر واتساب عند حلول الموعد.* — or, if you clear the date, the
warning *Without a next-due date no reminder is sent and the animal will lapse. /
بدون تاريخ للجرعة القادمة لن يتم إرسال تذكير وسينتهي مفعول التطعيم.*

**Instructions / تعليمات** — a free textarea sent with the prescription.

| Button | Effect |
|---|---|
| **Save prescription & continue / حفظ الروشتة والمتابعة** | Saves the medication rows, then the vaccination, then completes the visit |
| **No medication — continue / بدون دواء — متابعة** | Skips the medications but **still saves the vaccination** and completes the visit |

The vaccination is deliberately saved **before** the visit is completed, because
completing raises the invoice and a vaccination recorded afterwards would miss
its line on the bill. If the vaccination does not save, the page stops with
*The vaccination was not saved. / لم يتم حفظ التطعيم.*

### Step 6 — Invoice & Payment / الفاتورة والدفع

Completing the visit prices the consultation from the service catalogue and
turns each prescription line into an invoice line. If no invoice comes back the
page says so: *The visit completed but no invoice was raised. / اكتملت الزيارة
لكن لم تصدر فاتورة.*

The summary shows **Invoice / فاتورة**, **Total / الإجمالي**, **Due / المستحق**
and **Status / الحالة**.

**When nothing is due** you get ✓ *Settled in full. / تم السداد بالكامل.* and two
buttons: **Open visit / فتح الزيارة** and **Start another visit / بدء زيارة
أخرى**.

**When there is a balance:**

| Field | Label | Default |
|---|---|---|
| `pay_amount` | Amount / المبلغ | The full balance due |
| `pay_method` | Method / طريقة الدفع | Every payment method registered on this installation. An online gateway stays absent until its keys are configured |
| `pay_reference` | Reference / مرجع | Blank |

Buttons: **Take payment / تحصيل الدفع** and **Open invoice / فتح الفاتورة**.

Overpayment is **refused, not clamped** — the page detects an unchanged balance
and warns *The payment was not accepted. Check the amount against the balance
due. / لم يتم قبول الدفع. راجع المبلغ مقابل المستحق.*

**Instapay.** Choosing `instapay` reveals the clinic's own handle, QR and payment
link, with **Show QR to client / اعرض الكود للعميل** (a full-screen overlay
showing the amount large, the pet name and invoice number, and the code — close
with **Done / تم**, Escape, or clicking outside), **Open payment link / فتح رابط
الدفع**, and **Copy link / نسخ الرابط**. If none of the three are configured the
box reads *No Instapay details are set up yet. Add them under Settings so clients
can scan instead of typing. / لم يتم ضبط بيانات إنستاباي بعد…*

The standing instruction under it: *Client scans and sends. Confirm the transfer
has arrived before recording it, and put the Instapay reference in the field
above so it can be reconciled later.* — the app **records** an Instapay payment,
it does not receive one.

### What this page does not do

Picking a booking from today's queue does **not** move that appointment's
status. Known limits, item 20.

> Source: `platform/blueprints/workflow/routes.py:36-52` (page), `:57-95`
> (client search), `:98-128` (today's queue), `:131-145` (a client's pets),
> `:148-198` (visit state), `:201-225` (pet history),
> `platform/blueprints/clinical/routes.py:251-308` (the vaccination route),
> `platform/app.py:454-459` (payment method list),
> `platform/templates/workflow/index.html:433-440` (step strip), `:448-496`
> (step 1), `:498-546` (step 2), `:548-591` (step 3), `:593-628` (step 4),
> `:630-713` (step 5), `:715-719` (step 6), `:728` (patient panel), `:818-929`
> (client JS), `:931-991` (patient JS), `:993-1024` (visit JS), `:1026-1047`
> (diagnosis JS), `:1049-1110` (treatment JS), `:1112-1247` (invoice JS),
> `:1282-1399` (AI JS), `:1410-1460` (queue JS), `:1471-1516` (vitals),
> `:1583-1676` (vaccination JS), `:1688-1730` (QR overlay)

---

## 20. JSON endpoints

These carry no screen of their own. They are listed so you can tell a broken
page from a broken endpoint.

| Endpoint | Gate | Returns |
|---|---|---|
| `GET /crm/owners/<id>/pets-json` | `patients` | `{"pets": [...]}` — full pet rows |
| `GET /crm/owners/search-json?q=` | `patients` | `{"owners": [...]}` — id, name, phone. **Needs 2+ characters**, returns at most 25, searched against the whole table |
| `GET /appointments/api/pets?owner_id=` | `appointments` | A list of `{id, pet_name, species, breed}`. A missing or unparsable owner id returns `[]`, not an error |
| `GET /appointments/api/slots?date=&doctor=&exclude_id=` | `appointments` | `{date, doctor, slots:[{time, label, available}]}` for 08:00-19:30. With no doctor named, **every slot reads available** |
| `GET /appointments/api/risk-score/<owner_id>?time=` | `appointments` | `{score, level, reasons}` (§15) |
| `GET /appointments/api/queue` | **token or any signed-in session** (§18) | Today's queue. Owner names masked for anonymous callers, full for staff |
| `GET /workflow/api/owners?q=` | `visits` | Up to 12 clients with a pet count. **Needs 2+ characters**; searches name, Arabic name, phone and WhatsApp |
| `GET /workflow/api/today` | `visits` | Today's active bookings, checked-in first |
| `GET /workflow/api/owner/<id>/pets` | `visits` | `{ok, owner, pets}`; 404 `{"ok": false, "error": "Client not found."}` |
| `GET /workflow/api/visit/<id>` | `visits` | `{ok, visit, diagnoses, prescription, vaccinations, invoice}`; 404 when the visit does not exist |
| `GET /workflow/api/pet/<id>/history` | `visits` | `{ok, allergies, visits}` — the last 5 visits with their first diagnosis |

Everything under `/workflow/api/` is **read-only**. Nothing in that blueprint
writes.

> Source: `platform/blueprints/crm/routes.py:536-560`,
> `platform/blueprints/appointments/routes.py:544-552`, `:612-624`, `:696-700`,
> `:842-851`, `platform/blueprints/workflow/routes.py:57-225`

---

## 21. Known limits

Everything below is a real behaviour of the code as it stands. None of it is
speculation.

**1 · Reception cannot open the New Visit page.** `/workflow/` is governed by
the `visits` grant, and the default permission set for the `reception` role does
not include it. A receptionist clicking **New Visit / زيارة جديدة** — the
sidebar entry placed second precisely because it is meant to be reception's
most-used screen — gets *"You don't have permission to access this page."* and
is returned to the launcher. **Workaround:** an administrator ticks *Medical
Visits & SOAP / visits* for the reception role on the Roles screen. Note that
this also opens the whole `visits` and `clinical` modules to them.
*Source: `blueprints/auth/routes.py:140-152`, `models/database.py:4364-4367`,
`templates/base.html:110-117`*

**2 · The "New Pet" button on the all-pets grid is broken.** It links to
`/crm/pets/new` with no `owner_id`, and that route requires one. The result is
the red flash *"Owner ID is required to create a pet."* and a bounce to the
owners list. The **Add First Pet / إضافة أول حيوان** button in the empty state
has the same fault. Add animals from the owner's profile instead.
*Source: `templates/crm/pets_list.html:10-12`, `:98-100`;
`blueprints/crm/routes.py:689-692`*

**3 · The all-pets grid shows at most 100 animals, and the species filter runs
after the cut.** An unfiltered grid is the 100 most recently created pets. A
search is the first 100 matches by name. The species dropdown is then applied in
memory to that slice — so filtering to "Cat" on a clinic with more than 100
animals shows only the cats among the newest 100, with nothing on screen to say
so. The list of species offered in the dropdown is built from the same capped
query, so a species only found on older records never appears as an option.
*Source: `blueprints/crm/routes.py:660-679`; `models/database.py:3185-3202`*

**4 · The Balance column on the owners list is always empty.** It reads the
stored `owners.outstanding_balance` column, which nothing in the application
ever writes — only the demo seed script does. Every real client shows `—` there
regardless of what they owe. The **Balance EGP / الرصيد بالجنيه** tile on the
owner *profile* is computed from live invoices and is correct; use that.
*Source: `templates/crm/owners_list.html:256-262`; `blueprints/crm/routes.py:69-81`;
`scripts/seed/demo_showcase.py:930` is the only writer*

**5 · Owner search by WhatsApp number breaks the paging.** The row query matches
`full_name`, `phone`, `whatsapp_phone` and `email`; the count query behind
*Total Owners* and the page buttons matches only `full_name`, `phone` and
`email`. Searching a number that exists solely as a WhatsApp number returns rows
while the total says zero and no page links are drawn.
*Source: `models/database.py:3036-3042` vs `:3052-3056`*

**6 · The duplicate-mobile message names the existing client but gives you no
way to open them.** The server passes the client's id and name to the template;
the template renders neither, so the instruction *"Open <name> instead"* has
nothing to click. You have to search for them by hand. The walk-in workflow page
does not have this problem — it opens the client for you.
*Source: `blueprints/crm/routes.py:282-285`, `:616-620`; nothing in
`templates/crm/owner_form.html` references `duplicate_owner_id`*

**7 · Redeeming loyalty points creates no credit.** The button is labelled
*Redeem 100 pts → 50 EGP credit*, and the ledger row it writes says
*"Redeemed 100 pts = 50.0 EGP credit"*, but the route only deducts the points and
writes that row. **No credit note, no invoice adjustment and no account credit is
created anywhere in Finance.** The 50 EGP has to be applied by hand.
*Source: `blueprints/crm/routes.py:446-484`*

**8 · Manual point adjustment is not restricted, and neither loyalty action is
audited.** The function is documented as "Admin" but carries no role list, so
any role holding `patients` — including groomer and boarding_staff — can add or
deduct points on any client. Neither redemption nor adjustment writes an audit
entry, unlike owner and pet creation.
*Source: `blueprints/crm/routes.py:491-529`*

**9 · Marketing consent is recorded and never used, and the two client forms
disagree about it.** No code anywhere reads `owners.marketing_consent`; the
WhatsApp and reminder paths do not check it. Separately, the CRM form has the box
ticked by default while the walk-in workflow page does not send the field at all,
so clients registered at the workflow page are stored with consent **off**.
Neither difference has an effect today, but it will the moment something starts
honouring the flag.
*Source: `blueprints/crm/routes.py:260`, `:585`; `models/database.py:3150`;
`templates/workflow/index.html:881-886` (the field is not sent)*

**10 · The medical-history PDF always says "Animal Hospital".** The generator
reads `clinic_name` from the clinic record; the column is called `name`. The
lookup misses, so the fallback string is printed on every PDF, for every clinic.
*Source: `blueprints/crm/routes.py:950`; `models/database.py:1110-1113`*

**11 · No client or animal can be deleted from any screen.** The CRM blueprint
has no delete route. A record created in error can only be edited, not removed.

**12 · The pet edit form has no concurrent-edit protection.** The owner form
carries a `_seen_updated_at` stamp and refuses a stale save; the pet form does
not. Two people editing the same animal at once — increasingly likely now that
one desk PC can hold several signed-in accounts — will silently overwrite each
other, with nothing on screen and nothing in the record to show it happened.
*Source: `blueprints/crm/routes.py:598-609` (owner, guarded) vs `:829-854` (pet,
unguarded)*

**13 · Appointments outside 08:00-20:59 are invisible on the day schedule and
the Reception Workspace.** Both agendas build hour rows for 08 through 20 only
and drop anything that falls outside. The appointment is still counted in the
**Total** tile, so the tile and the visible rows disagree. You cannot create such
an appointment through the booking form (its slots stop at 19:30), but imported
or API-created bookings can land there.
*Source: `blueprints/appointments/routes.py:179-189`, `:580-590`*

**14 · The booking form accepts a date in the past.** The date input asks for a
`min` value the route never supplies, so the attribute renders empty and no
minimum applies; the server does not check either.
*Source: `templates/appointments/appt_form.html:249-250`;
`blueprints/appointments/routes.py:374-387` passes no `today_str`*

**15 · Double-booking is only prevented when a doctor is named.** Both the
booking form and the reschedule form skip the collision check entirely when the
doctor field is left empty, so any number of appointments can be stacked on one
slot with no doctor assigned. The same applies to the greyed-out slots in the
`/appointments/api/slots` response: with no doctor supplied, every slot comes
back available.
*Source: `blueprints/appointments/routes.py:309-312`, `:481-484`, `:96-106`*

**16 · Booked slots are clickable on the booking form.** Unavailable slots are
only given a grey CSS class; the radio button underneath stays enabled, so the
form can be submitted on a taken slot and is refused by the server afterwards.
The reschedule form does this properly — its taken slots are genuinely disabled.
*Source: `templates/appointments/appt_form.html:369-382` vs
`templates/appointments/appt_edit.html:43-48`*

**17 · The Reception Workspace's Owner Lookup cannot check anybody in.** Its
sub-line reads *"Search by name or phone to check in"*, but selecting a client
only offers pet chips and a booking link. Check-in is done from the **Waiting /
Scheduled** panel below it, or from the appointment's own page.
*Source: `templates/appointments/reception.html:328-351`*

**18 · The Waiting Room TV's patient list never refreshes itself.** The
30-second poll updates only the three counters in the side panel; the queue table
is rendered once by the server and is not touched again. A TV left running shows
a stale list until somebody reloads the page. The clock and the health tips do
rotate, which makes the screen look live when it is not.
*Source: `templates/appointments/waiting_room.html:286-298`*

**19 · Doctors and nurses cannot take payment on the New Visit page.** The
payment button POSTs to `/finance/invoices/<id>/pay`, which needs the
`invoicing` grant. Doctor and nurse hold `visits` but not `invoicing`, so they
reach step 6, see the invoice, and get an HTTP error when they press **Take
payment**. The page reports it as *"Could not record the payment. HTTP 403"*.
Only clinic_owner, branch_manager and super_admin can run all six steps on
default permissions.
*Source: `models/database.py:4359-4363`; `blueprints/auth/routes.py:140-152`;
`templates/workflow/index.html:1230-1235`*

**20 · Saving a new patient on the New Visit page can select the wrong
animal.** After the save the page re-reads the client's animals — which come
back **sorted by name** — and takes the last one in the list, assuming it is the
one just created. When the client already has animals and the new name does not
sort last alphabetically, a different animal is carried into the examination
step. Check the name in the patient panel on the right before entering the
complaint.
*Source: `templates/workflow/index.html:954-957`;
`blueprints/workflow/routes.py:139-141` (ordered by `pet_name`)*

**21 · Starting a visit from today's queue does not update the appointment.**
The page notes which booking you picked but never uses it: the appointment keeps
whatever status it had. After completing a visit from the queue you must still
open the appointment and set it to **Completed** by hand, or it will be counted
as pending on the schedule, in the reception counters and on the waiting-room
display.
*Source: `templates/workflow/index.html:1451` sets `state.fromAppointment`, and
nothing else in the file reads it*

**22 · Several dropdowns and buttons are English-only in an Arabic
interface.** Specifically: the six status buttons on the appointment detail page;
the appointment **Type** tiles and **Channel** options on the booking form; the
**Type**, **Priority** and **Channel** dropdowns on the reschedule form; and the
species names in the all-pets filter. They read from the code's own vocabulary
lists rather than through the translation helper.
*Source: `blueprints/appointments/routes.py:37-40` (the vocabularies);
`templates/appointments/appt_detail.html:85-90`;
`templates/appointments/appt_form.html:219-226`, `:265-268`;
`templates/appointments/appt_edit.html:66-89`;
`templates/crm/pets_list.html:24-26`*

**23 · The two "add an animal" forms are not the same form.** The CRM form
offers eight species with Dog pre-selected and a three-way sex field including
*Unknown*; the walk-in workflow form offers five species with **Cat**
pre-selected and only Male/Female. It also has no colour, microchip, neutered,
chronic-conditions, diet or insurance fields. An animal registered at the desk
during a walk-in therefore starts with a thinner record than one registered from
the owner's profile.
*Source: `templates/crm/pet_form.html:206-215`, `:243` vs
`templates/workflow/index.html:518-530`*

**24 · Two small dead controls.** The reschedule form writes a hidden field
named `csrf_token`, which the validator does not read — it reads `_csrf_token`,
which JavaScript injects separately, so the form works and the field does
nothing. And the WhatsApp field on the client forms carries the hint *"Leave
blank if same as phone"*, but nothing copies the phone number into it when you
do; the field is simply stored empty. (The walk-in workflow form does default it
to the phone number.)
*Source: `templates/appointments/appt_edit.html:13`;
`models/security.py:275-279`; `templates/crm/owner_form.html:189-193`;
`templates/workflow/index.html:883`*

**25 · A few cross-module buttons lead to screens the clicker cannot open.**
They are rendered unconditionally and the destination's own grant refuses the
click: 💳 **Account / الحساب** and the invoice links on the owner profile
(`invoicing` — not held by doctor, nurse or pharmacist); ✉️ **Send Message /
إرسال رسالة** (`whatsapp` — held by clinic_owner, branch_manager and reception
only); ✨ **AI Summary / ملخص ذكي** on the pet record (`ai` — held by
clinic_owner and doctor only); and most of the pet-record timeline's deep links.
Separately, the launcher offers the **Owners & Pets CRM** card to the `auditor`
role, which does not hold `patients` and is bounced on arrival.
*Source: `blueprints/auth/routes.py:140-152`; `models/database.py:4346-4379`;
`templates/crm/owner_detail.html:11-13`, `:585-586`;
`templates/crm/pet_detail.html:10-15`; `blueprints/launcher/routes.py:56`*

---

## 22. Quick route index

| Route | Method | Screen | Gate |
|---|---|---|---|
| `/crm/owners` | GET | Owners list (§3) | `patients` |
| `/crm/owners/new` | GET, POST | New owner (§4) | `patients` |
| `/crm/owners/<id>` | GET | Owner profile (§5) | `patients` |
| `/crm/owners/<id>/edit` | GET, POST | Edit owner (§6) | `patients` |
| `/crm/owners/<id>/redeem-points` | POST | Loyalty redemption (§5) | `patients` |
| `/crm/owners/<id>/adjust-points` | POST | Loyalty adjustment (§5) | `patients` |
| `/crm/pets`, `/crm/pets/` | GET | All pets (§7) | `patients` |
| `/crm/pets/new` | GET, POST | New pet (§8) | `patients` |
| `/crm/pets/<id>` | GET | Pet record (§9) | `patients` |
| `/crm/pets/<id>/edit` | GET, POST | Edit pet (§10) | `patients` |
| `/crm/pets/<id>/history.pdf` | GET | Medical history PDF (§11) | `patients` |
| `/appointments/`, `/appointments/schedule` | GET | Day schedule (§12) | `appointments` |
| `/appointments/calendar` | GET | Week calendar (§13) | `appointments` |
| `/appointments/new` | GET, POST | New appointment (§14) | `appointments` |
| `/appointments/<id>` | GET | Appointment detail (§15) | `appointments` |
| `/appointments/<id>/status` | POST | Status change (§15) | `appointments` |
| `/appointments/<id>/edit` | GET, POST | Reschedule (§16) | `appointments` |
| `/appointments/reception` | GET | Reception Workspace (§17) | `appointments` |
| `/appointments/waiting-room` | GET | Waiting Room TV (§18) | token or any session |
| `/workflow/` | GET | New Visit (§19) | `visits` |

JSON endpoints are in §20.
