# Clinical — Reference Manual

**Modules:** Medical Visits / الزيارات الطبية · Hatem Way one-screen exam / طريقة حاتم ·
New Visit wizard / زيارة جديدة · Lab / المختبر · Vaccinations / التطعيمات · Surgeries / العمليات
**URL prefixes:** `/visits/` · `/clinical/` · `/workflow/`
**Blueprints:** `visits`, `clinical`, `workflow`

This chapter is a **screen-by-screen reference**. It describes only what the code in
`blueprints/visits/routes.py`, `blueprints/clinical/routes.py`,
`blueprints/workflow/routes.py` and their templates does today. Controls whose label
promises more than the code delivers, and fields that exist in the database but have
no screen, are listed under [Known limits](#known-limits) rather than described as
working. Where a label is bilingual in the template, both texts are given.

> Source: `platform/app.py:213,222-223` (imports), `platform/app.py:241,250-251`
> (registration), `platform/blueprints/visits/__init__.py:2`,
> `platform/blueprints/clinical/__init__.py:3`,
> `platform/blueprints/workflow/__init__.py:3`

---

## 1. Getting into the module

| Door | Where | Goes to |
|---|---|---|
| Sidebar → CLINIC / العيادة → **New Visit / زيارة جديدة** | every page | `/workflow/` (the 6-step wizard, **not** `/visits/new`) |
| Sidebar → CLINIC / العيادة → **Medical Visits / الفحوصات** | every page | `/visits/` |
| Sidebar → CLINICAL / السريري → **Lab & Vaccines / المختبر والتطعيمات** | every page | `/clinical/lab` |
| Launcher card **Visits & Consultations / الزيارات والاستشارات** (📝) | `/` | `/visits/` |
| Launcher card **Hatem Way — One-Screen Exam / طريقة حاتم — كشف بشاشة واحدة** (⚡) | `/` | `/visits/exam` |
| Launcher card **Laboratory & Diagnostics / المختبر والتشخيص** (🔬) | `/` | `/clinical/lab` |
| Launcher card **Vaccination & Preventive Care / التطعيمات والرعاية الوقائية** (💉) | `/` | `/clinical/vaccinations` |
| Launcher card **Surgery & Procedures / الجراحة والإجراءات** (🔧) | `/` | `/clinical/surgeries` |
| Visits list topbar **⚡ Hatem Way / طريقة حاتم** | `/visits/` | `/visits/exam` |
| Visits list topbar **+ New Visit / زيارة جديدة** | `/visits/` | `/visits/new` |
| Exam screen link **Alert / Vaccine — تنبيه / تطعيم** | `/visits/exam/<pet_id>` | `/clinical/vaccinations?pet_id=…` |
| Pharmacy prescription detail link **Vaccinations →** | `/pharmacy/prescription/<id>` | `/clinical/vaccinations?pet_id=…` |
| Direct URL | — | `/clinical/` redirects to `/clinical/vaccinations` |

There is **no sidebar entry** for `/clinical/vaccinations` or `/clinical/surgeries`;
they are reached from the launcher cards, from the exam screen, or by typing the URL.
The sidebar's **Lab & Vaccines** entry opens the lab queue only — the lab screens
carry no link across to vaccinations.

Sidebar entries carry **no role condition**: every signed-in user sees them, and a
user whose role lacks the grant is bounced back to the launcher with *"You don't have
permission to access this page."*

> Source: `platform/templates/base.html:112-118` (New Visit → `workflow.index`),
> `:126-129` (Medical Visits), `:145-148` (Lab & Vaccines);
> `platform/blueprints/launcher/routes.py:62-135` (lab, vaccination, surgery, exam and
> visits cards), `:579` (`_visible_modules`);
> `platform/templates/visits/visits_list.html:6-9`;
> `platform/templates/visits/exam.html:1809`;
> `platform/templates/pharmacy/rx_detail.html:25`;
> `platform/blueprints/clinical/routes.py:70-74`

---

## 2. Who can open what

Every route in all three blueprints carries **`@login_required` and nothing else** —
there is no per-route role list anywhere in the clinical, visits or workflow code.
Access is therefore decided entirely by the **module grant** checked inside
`login_required`:

* `visits` blueprint → grant key `visits`
* `clinical` blueprint → grant key `visits` (mapped explicitly)
* `workflow` blueprint → grant key `visits` (mapped explicitly)

`super_admin` bypasses the check. A role with no row in the `roles` table falls back
to the built-in defaults if it is a built-in role, and is **denied** if it is not.

Roles holding the `visits` grant by default (its label on the Roles screen is
**Medical Visits & SOAP**):

| Role | Holds `visits` by default |
|---|---|
| clinic_owner | yes |
| branch_manager | yes |
| doctor | yes |
| nurse | yes |
| pharmacist | yes |
| **reception** | **no** |
| finance, hr, groomer, boarding_staff, inventory_mgr, support_admin, auditor | no |

Reception is the notable gap — see [Known limits](#known-limits) L1.

Inside the module one further rule applies, to **prescriptions only**: only a user
whose role is `doctor`, `clinic_owner` or `super_admin` may be *recorded as the
prescriber*. Anyone else holding the `visits` grant may type the prescription but must
name an active veterinarian on the form. This rule is enforced on the visit-detail
prescription form only (§5.3.4); the exam screen and the wizard do not apply it
(Known limits L6, L7).

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-134` (`_permission_denied`), `:140-163` (blueprint → key map: `clinical` and
> `workflow` both map to `visits`),
> `platform/models/database.py:4302-4330` (`ALL_PERMISSIONS`),
> `:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`),
> `platform/blueprints/visits/routes.py:306-352` (`PRESCRIBER_ROLES`,
> `_resolve_prescriber`)

---

## 3. Conventions that apply to every screen here

**Bilingual labels.** Templates call `t('English', 'العربية')`. Arabic is returned only
when the language is `ar` — taken from the user's `language` column, else
`session['lang']`, else the `PLATFORM_DEFAULT_LANG` environment variable, else English.
Where a template supplies no Arabic string, the English text shows in both languages;
those cases are marked "English only" below.

**CSRF.** Every non-GET request is rejected with a 403 error page unless it carries
`_csrf_token` (form field or JSON key) or an `X-CSRF-Token` header. The visits
templates put the hidden field in the form themselves; the clinical templates
(vaccination, lab-request, lab-results and surgery forms) do **not** — a script in the
shared JavaScript bundle appends the token to any POST form as it is submitted. With
JavaScript disabled those four forms fail with the 403 page.

**Flash messages** appear at the top of the next page: green for success, red for
`danger` / `error`, amber for `warning`.

> Source: `platform/app.py:370-408` (language, `t`), `:449` (`current_lang`),
> `platform/app.py:348-356` (CSRF gate), `platform/models/security.py:270-283`
> (`validate_csrf`), `platform/static/js/platform.js:129-146` (auto-inject),
> `platform/templates/base.html:885` (bundle include)

---

## 4. Map of the screens

| # | Screen | URL | Method(s) |
|---|---|---|---|
| 5.1 | Medical Visits list | `/visits/` | GET |
| 5.2 | New Visit (long form) | `/visits/new` | GET, POST |
| 5.3 | Visit detail | `/visits/<visit_id>` | GET plus five POST sub-forms |
| 5.4 | Visit printout | `/visits/<visit_id>/print` | GET |
| 5.5 | Visit → invoice shortcut | `/visits/<visit_id>/invoice` | GET (redirect) |
| 5.6 | Hatem Way one-screen exam | `/visits/exam`, `/visits/exam/<pet_id>` | GET, POST |
| 5.7 | New Visit wizard (6 steps) | `/workflow/` | GET |
| 5.8 | Vaccinations | `/clinical/vaccinations` | GET |
| 5.9 | Record vaccination | `/clinical/vaccinations/new` | GET, POST |
| 5.10 | Vaccination certificate (PDF) | `/clinical/vaccinations/<vacc_id>/certificate` | GET |
| 5.11 | Lab requests queue | `/clinical/lab` | GET |
| 5.12 | New lab request | `/clinical/lab/new` | GET, POST |
| 5.13 | Lab request detail and results | `/clinical/lab/<lab_id>` and `…/results` | GET, POST |
| 5.14 | Surgeries list | `/clinical/surgeries` | GET |
| 5.15 | Record surgery | `/clinical/surgeries/new` | GET, POST |

> Source: `platform/blueprints/visits/routes.py:13,67,110,163,591,608,691,827,1301`,
> `platform/blueprints/clinical/routes.py:70,77,93,157,190,228,251,320,363,384`,
> `platform/blueprints/workflow/routes.py:36`

---

## 5. The screens

### 5.1 Medical Visits list — `/visits/`

**What it is for.** The register of consultations. One row per visit, newest first.

**How to reach it.** Sidebar → CLINIC → *Medical Visits / الفحوصات*; launcher card
*Visits & Consultations*; the *← Visits / ← الزيارات* button on any visit detail page.

**Who can open it.** Any role holding the `visits` grant (see §2).

#### Filter bar (GET form, submits to the same URL)

| Control | Name | Values | Effect |
|---|---|---|---|
| Status dropdown | `status` | *All / الكل*, *Open / مفتوح*, *Completed / مكتمل*, *Cancelled / ملغى* | Anything other than `All` adds `v.status = ?`. Default `All`. |
| Date from | `date_from` | date picker | `DATE(v.visit_date) >= value` |
| Date to | `date_to` | date picker | `DATE(v.visit_date) <= value` |
| Doctor dropdown | `doctor` | *All Doctors / جميع الأطباء* plus every distinct `doctor_name` already stored on a visit | Case-insensitive `LIKE %value%` on `doctor_name` |
| **Filter / تصفية** | — | submit | Re-runs the list with the filters |
| **Clear / مسح** | — | link | Returns to `/visits/` with no filters |

The dropdown of doctors is built from `SELECT DISTINCT doctor_name FROM visits`, so a
vet who has never been named on a visit does not appear in it.

#### Columns

| Column | Contents |
|---|---|
| `#` | Visit id |
| **Date / التاريخ** | `visit_date`, first 16 characters (date and time) |
| **Pet / الحيوان** | Pet name in bold, species and breed underneath |
| **Owner / المالك** | Owner name, phone underneath |
| **Type / النوع** | `visit_type` |
| **Doctor / الطبيب** | `doctor_name`, or `—` |
| **Chief Complaint / الشكوى الرئيسية** | Truncated to one line with an ellipsis |
| **Status / الحالة** | Badge: amber *Open / مفتوح*, green *Completed / مكتمل*, red for anything else (raw value shown) |
| (last) | **Open / فتح** button → `/visits/<id>` |

Empty result shows *No visits found. / لا توجد زيارات.*

**Hard limit:** the query ends `ORDER BY v.visit_date DESC LIMIT 50`. There is no
paging control, so only the 50 most recent matching visits are ever listed — narrow
with the filters to see older ones.

> Source: `platform/blueprints/visits/routes.py:13-64`,
> `platform/templates/visits/visits_list.html:1-74`

---

### 5.2 New Visit (long form) — `/visits/new`

**What it is for.** Opening a visit record by hand, with vitals and the complaint, and
nothing else. It creates the visit only; diagnosis, treatment, prescription and the
invoice all happen afterwards on the visit-detail screen.

**How to reach it.** *+ New Visit / زيارة جديدة* on the visits list. It also accepts
`?appt_id=`, `?pet_id=` and `?owner_id=` to arrive pre-filled — the appointments screens
link in this way, and when `appt_id` is given the appointment's own pet and owner are
used unless overridden in the query string.

**Who can open it.** Any role holding the `visits` grant.

#### Patient card

| Field | Name | Required | Notes |
|---|---|---|---|
| **Owner / المالك** | `owner_id` | yes (browser `required`, and re-checked on the server) | A `<select>` that starts **empty except for the pre-selected owner**. The shared script turns it into a type-to-search box that queries `/crm/owners/search-json` after two characters and rewrites the options; a single match is selected automatically. |
| **Pet / الحيوان** | `pet_id` | yes (browser `required`, re-checked on the server) | Populated by `filterPets()` from `/crm/owners/<id>/pets-json` when an owner is chosen. Shows *— Select Owner First / اختر المالك أولاً —* until then. |

When a pet arrived through the query string, a grey strip under the selects repeats its
name, species, breed, weight and — in red — **Allergies / الحساسية**.

#### Vitals card (all optional, all free numbers)

| Field | Name | Input |
|---|---|---|
| **Weight (kg) / الوزن (كجم)** | `weight_kg` | number, step 0.01, min 0 |
| **Temperature (°C) / درجة الحرارة (°م)** | `temp_c` | number, step 0.1 |
| **Heart Rate (bpm) / معدل القلب** | `heart_rate` | number |
| **Resp. Rate (brpm) / معدل التنفس** | `respiratory_rate` | number |

#### Visit details card

| Field | Name | Required | Notes |
|---|---|---|---|
| **Visit Type / نوع الزيارة** | `visit_type` | no (defaults to `Consultation`) | Fixed list, English values only: Consultation, Follow-up, Vaccination, Surgery, Emergency, Dental, Wellness, Other |
| **Doctor Name / اسم الطبيب** | `doctor_name` | no | Free text, pre-filled with the signed-in user's full name. The name is matched against active users to set `doctor_id`; when it matches nobody the visit stores the name with **no** doctor id rather than crediting the person who typed it. |
| **Chief Complaint / الشكوى الرئيسية** | `chief_complaint` | browser `required` only — the server accepts an empty value | |
| **Symptoms / History — الأعراض / التاريخ المرضي** | `symptoms` | no | textarea |
| **Notes / ملاحظات** | `notes` | no | textarea |

#### Buttons

* **Create Visit / إنشاء زيارة** — inserts the visit with `status = 'Open'` and
  `visit_date = datetime('now')` (UTC, not local time), then goes to the new visit's
  detail page with *"Visit created successfully."* If owner or pet is missing, it
  flashes *"Owner and pet are required."* and returns to the blank form — **anything
  already typed is lost**.
* **Cancel / إلغاء** — back to the visits list.

> Source: `platform/blueprints/visits/routes.py:67-160`, `:891-919` (`_doctor_id_for`),
> `platform/templates/visits/visit_form.html:1-134`,
> `platform/static/js/platform.js:406-441` (remote search),
> `platform/blueprints/crm/routes.py:545-560` (`owner_search_json`)

---

### 5.3 Visit detail — `/visits/<visit_id>`

**What it is for.** The whole medical record of one consultation, and the place where
SOAP notes, diagnoses, the treatment plan, prescriptions and lab requests are added.

**How to reach it.** **Open / فتح** on the visits list; automatically after creating a
visit; from the exam screen's History table; from `/clinical/lab/<id>` (the *Visit*
field); from the pet and owner screens.

**Who can open it.** Any role holding the `visits` grant.

A missing visit id flashes *"Visit not found."* and returns to the list.

#### Left rail (read-only)

| Card | Contents |
|---|---|
| Patient | Species emoji (dog, cat, bird, rabbit, otherwise a paw), pet name, species · breed, then **Sex / الجنس**, **Record Weight / الوزن المسجل** (the pet's stored weight, not this visit's) and **DOB / تاريخ الميلاد** |
| **⚠️ Allergies / الحساسية** | Red box, shown only when the pet record has allergies |
| **Owner / المالك** | Name, phone and a **WhatsApp / واتساب** link (`wa.me` with `+`, spaces and dashes stripped) |
| **Visit Vitals / العلامات الحيوية** | Weight, temperature and heart rate **recorded on this visit**. Respiratory rate is stored but not shown here. |
| **Visit Info / بيانات الزيارة** | Date, type, doctor, status badge |

#### Topbar buttons

| Button | Shown when | Effect |
|---|---|---|
| **← Visits / ← الزيارات** | always | visits list |
| **🖨 Print / طباعة** | always | opens `/visits/<id>/print` in a new tab (§5.4) |
| **🩻 Imaging / التصوير الطبي** | always | `/imaging/pet/<pet_id>` studies for this patient |
| **📤 Upload Image / رفع صورة** | always | the imaging upload screen for this patient |
| **🧾 Invoice `<number>` / فاتورة** | an invoice row exists with this `visit_id` | that invoice |
| **🧾 Create Invoice / إنشاء فاتورة** | no invoice **and** status is `Completed` | `/visits/<id>/invoice` (§5.5) |
| **💊 Pharmacy / الصيدلية** | the visit has at least one prescription | the pharmacy dispensing queue (not filtered to this visit) |
| **📋 Discharge Instructions / تعليمات الخروج** | status `Open` **and** at least one diagnosis | opens the AI modal described below |
| **✔ Complete Visit / إنهاء الزيارة** | status `Open` **and** at least one diagnosis | posts to `/visits/<id>/complete` after a confirm dialog |
| **✔ Complete Visit** (greyed) | status `Open` and **no** diagnosis | disabled, tooltip *Add a diagnosis first / أضف تشخيصاً أولاً* |
| **✔ Completed / مكتملة** badge | status is not `Open` | not a button |

When the visit is `Open` with no diagnosis, an amber banner also reads *"Add at least
one diagnosis before completing this visit."*

**Everything below is editable only while the visit is `Open`.** Once the status is
`Completed` the five sub-forms disappear and the screen becomes read-only.

#### 5.3.1 Chief complaint

Read-only card, shown only when the visit has one. `symptoms` appears underneath.

#### 5.3.2 SOAP Clinical Notes / ملاحظات SOAP السريرية — POST `/visits/<id>/soap`

Four textareas, each optional, saved together:

| Field | Name | Label |
|---|---|---|
| Subjective | `soap_subjective` | 👤 **Subjective / البيانات الذاتية** *(owner reports / ما يذكره المالك)* |
| Objective | `soap_objective` | 🔍 **Objective / البيانات الموضوعية** *(doctor observes / ما يلاحظه الطبيب)* |
| Assessment | `soap_assessment` | 🧠 **Assessment / التقييم** *(diagnosis / evaluation)* |
| Plan | `soap_plan` | 💊 **Plan / الخطة** *(treatment plan / خطة العلاج)* |

**Save SOAP Notes / حفظ ملاحظات SOAP** overwrites all four columns with whatever the
form contains — clearing a box clears the record — stamps `updated_at`, writes an
audit-log row (`soap_update`), flashes *"SOAP notes saved."* and returns to the `#soap`
anchor. When any of the four is filled, the saved text is also shown above the form in
four grey panels with a green **Recorded / مسجلة** badge.

#### 5.3.3 Diagnosis / التشخيص — POST `/visits/<id>/diagnosis`

Existing diagnoses are listed with their notes, the timestamp, and a severity badge
(green *Mild / بسيط*, amber *Moderate / متوسط*, red *Severe / شديد*, dark red
*Critical / حرج*). The header counts them.

| Field | Name | Required |
|---|---|---|
| **Diagnosis / التشخيص** | `diagnosis_text` | **yes** — an empty value is refused with *"Diagnosis text is required."* |
| **Severity / الشدة** | `severity` | no; defaults to `Mild`. Options Mild, Moderate, Severe, Critical |
| **Notes / ملاحظات** | `diagnosis_notes` | no |

**Add Diagnosis / إضافة تشخيص** inserts one row per submission (the form does not edit
or delete existing ones), copying `pet_id` from the visit, and returns to `#diagnosis`
with *"Diagnosis added."* There is no *chronic* checkbox on this screen even though the
column exists and the exam screen writes it.

#### 5.3.4 Treatment Plan / خطة العلاج — POST `/visits/<id>/treatment`

One plan per visit: saving again updates the existing row rather than adding another.

| Field | Name | Notes |
|---|---|---|
| **Treatment Plan / خطة العلاج** | `plan_text` | textarea |
| **Goals / الأهداف** | `goals` | textarea |
| **Duration / المدة** | `duration` | free text, e.g. *7 days* |
| **Follow-up in / المتابعة خلال** | `followup_in` | number ≥ 1 |
| **Unit / الوحدة** | `followup_unit` | Days / أيام, Weeks / أسابيع, Months / شهور |

**Save Treatment Plan / حفظ خطة العلاج** flashes *"Treatment plan saved."* Nothing is
required. The follow-up interval is **stored only** — no appointment is created from it
and no reminder is sent (contrast the exam screen, §5.6, which books a real
appointment).

#### 5.3.5 Prescriptions / الوصفات الطبية — POST `/visits/<id>/prescription`

Saved prescriptions are shown as one block per prescription (*Rx #1*, *Rx #2* …) with a
table of **Medication / دواء**, **Dosage / الجرعة**, **Frequency / التكرار**,
**Duration / المدة**, **Route / طريقة الإعطاء**, **Qty / الكمية**, plus an ℹ️ line for
per-item instructions and the prescription's notes underneath.

The add form:

| Field | Name | Notes |
|---|---|---|
| **Prescribing veterinarian / الطبيب المعالج** | `prescribed_by` | **Shown only to users who may not prescribe themselves.** A dropdown of active users whose role is doctor, clinic_owner or super_admin, required. If the system has no such user the box is replaced by a red line saying a prescription cannot be recorded. Doctors, clinic owners and super admins do not see this field and are recorded as the prescriber automatically. |
| **Medication / دواء** | `medication_name_1`, `_2`, … | required on line 1 (browser-level) |
| **Dosage / الجرعة** | `dosage_N` | free text |
| **Frequency / التكرار** | `frequency_N` | free text |
| **Duration / المدة** | `duration_N` | free text |
| **Route / طريقة الإعطاء** | `route_N` | —, Oral / فموي, IV, IM, SC, Topical / موضعي, Ophthalmic / عيني, Otic / أذني |
| **Qty / الكمية** | `quantity_N` | number |
| **Prescription Notes / ملاحظات الوصفة** | `rx_notes` | one line for the whole prescription |

Buttons:

* **＋ Add Line / إضافة سطر** — appends another medication row (numbered upwards). The
  added row's labels are **English only**.
* **💊 Check Interactions / فحص التداخلات الدوائية** — posts the typed drugs plus this
  animal's already-prescribed medications to `/ai/drug-interactions` and paints a
  banner: red *SEVERE INTERACTION*, amber *Moderate*, yellow *Mild*, grey
  *Not checked* when the service is unreachable or unsure, green
  *No interaction found in this check* otherwise. The grey state explicitly does not
  mean safe.
* **Save Prescription / حفظ الوصفة** — writes one `prescriptions` row (status `Active`)
  and one item per numbered line. The server reads `medication_name_1`, `_2`, … and
  **stops at the first gap**, so removing a middle line in the browser would drop
  every line after it (the screen only ever appends, so this does not arise in normal
  use). If the prescriber cannot be resolved the whole submission is refused with a red
  message and nothing is saved. When someone other than the named vet enters it, the
  note gets `[entered by X on behalf of Y]` appended.

#### 5.3.6 Lab Requests / طلبات المختبر

Requests already attached to this visit are listed with test name, sample type, notes,
a priority badge (red for Urgent or STAT, blue otherwise) and the date. **View Lab
Module → / عرض وحدة المختبر ←** opens `/clinical/lab`.

The **＋ Request Lab Test / طلب فحص مخبري** form offers **Test Name / اسم الفحص** (with
a datalist of eleven common tests), **Priority / الأولوية** (Routine / Urgent / STAT),
**Sample Type / نوع العينة** and **Notes / ملاحظات** — but its submit handler posts to
`/clinical/lab/request`, **which is not a route in this application**. See Known limits
L2: the request is never created, and the alert *"Error submitting lab request. Please
try from the Lab module."* appears. Use §5.12 instead.

#### 5.3.7 AI assistant, discharge instructions and photo analysis

A floating 🤖 button opens a side panel titled **AI Clinical Assistant / المساعد
السريري الذكي**, which sends each question with the visit id to `/ai/chat`, and offers
**📸 Analyze Photo / تحليل الصورة** (`/ai/analyze-photo`). **📋 Discharge Instructions /
تعليمات الخروج** opens a modal that requests bilingual instructions from
`/ai/discharge-instructions/<visit_id>` and then offers **🖨 Print / طباعة**,
**📱 WhatsApp / واتساب** (opens `wa.me` with the first 1000 characters) and **Close /
إغلاق**. All four depend on the AI service being configured and reachable; each failure
path shows a message rather than silence. Nothing generated here is written to the
visit record — the instructions exist only in the modal until printed or sent.

#### 5.3.8 Complete Visit — POST `/visits/<id>/complete`

In order:

1. **Refuses** if the visit has no diagnosis: *"Please add at least one diagnosis
   before completing the visit."*
2. Sets `status = 'Completed'` and stamps `updated_at`.
3. If no invoice is linked to this visit yet, it builds one:
   * one **service** line per diagnosis, described *"Consultation — `<diagnosis>`"*,
     priced by looking up the first active service catalogue entry whose name contains
     the visit type, falling back to one containing "consultation"; **0.00** if neither
     matches;
   * one **medication** line per prescription item, quantity from the item (1 when
     blank), priced by a catalogue name match, again 0.00 when there is no match;
   * if there are no lines at all, a single consultation line;
   * discount 0, tax 0, note *"Auto-generated from visit #N. Please update prices."*
4. Redirects to the new invoice with *"Visit completed. Invoice #N auto-generated."*
   If invoice creation raises, it flashes *"Visit completed but invoice creation
   failed: …"* and stays on the visit.
5. If an invoice already existed, it simply flashes *"Visit marked as Completed."*

Consequences worth knowing before pressing it: the consultation is billed **once per
diagnosis** (three diagnoses produce three consultation lines), prices are 0.00 unless
the catalogue matches by name, and the redirect target is a Finance screen — a user
without the `invoicing` grant is bounced to the dashboard with a permission message
even though the visit and invoice were both saved (Known limits L3, L4).

> Source: `platform/blueprints/visits/routes.py:163-234` (page),
> `:237-261` (diagnosis), `:264-303` (treatment), `:355-428` (prescription),
> `:432-462` (SOAP), `:465-588` (complete);
> `platform/templates/visits/visit_detail.html:11-62` (topbar), `:66-72` (banner),
> `:76-186` (left rail), `:211-274` (SOAP), `:277-350` (diagnosis),
> `:353-420` (treatment), `:423-586` (prescriptions), `:589-682` (lab),
> `:704-828` (AI panel and modals), `:967-991` (`submitLabRequest`),
> `:1064-1172` (interaction checker)

---

### 5.4 Visit printout — `/visits/<visit_id>/print`

A print-styled page that opens in a new tab and calls `window.print()` on load. It
repeats the patient and owner identity, the doctor, the vitals (weight, temperature,
heart rate), chief complaint and symptoms, then the diagnoses table (#, **Diagnosis /
التشخيص**, Severity — English only, **Notes / ملاحظات**), the treatment plan, every
prescription with its items (Medication, Dosage, Frequency, Duration, Route, Qty,
Instructions) and the visit's lab requests. It is a page, not a PDF: use the browser's
"Save as PDF".

> Source: `platform/blueprints/visits/routes.py:608-661`,
> `platform/templates/visits/visit_print.html:60-178`

---

### 5.5 Visit → invoice shortcut — `/visits/<visit_id>/invoice`

Not a screen. If an invoice is linked to the visit it redirects to that invoice;
otherwise it redirects to `/finance/invoices/new?visit_id=<id>`. The new-invoice screen
ignores that parameter entirely, so nothing is pre-filled and the invoice you create
there is **not** linked back to the visit (Known limits L5).

> Source: `platform/blueprints/visits/routes.py:591-605`,
> `platform/blueprints/finance/routes.py:208-305`,
> `platform/templates/finance/invoice_form.html` (no `visit_id` field)

---

### 5.6 Hatem Way — the one-screen exam — `/visits/exam` and `/visits/exam/<pet_id>`

**What it is for.** The whole consultation on one page: find the client, load the
animal, take vitals, write the symptom and diagnosis, prescribe, record a vaccination,
bill the services, take the cash and print — one form, one Save. It is a **separate
flow** from §5.2/§5.3: what it saves is a visit that is already `Completed`, plus its
invoice and payment.

**How to reach it.** Launcher card *Hatem Way — One-Screen Exam*; the **⚡ Hatem Way /
طريقة حاتم** button on the visits list; `?pet_id=` on `/visits/exam` redirects straight
to that animal's screen. **Long form / النموذج الكامل** and **All visits / كل الزيارات**
in the topbar lead back to §5.2 and §5.1.

**Who can open it.** Any role holding the `visits` grant. (Reception, the role this
screen is written for, does not hold it by default — Known limits L1.)

`/visits/exam/<pet_id>` for a pet that does not exist, or whose record is inactive,
flashes *"Pet not found."* and returns to the empty screen.

#### 5.6.1 Client bar

| Control | Behaviour |
|---|---|
| **Phone or client name / رقم الهاتف أو اسم العميل** (`hwSearch`) | Searches after **2 characters**, 220 ms after you stop typing, against `/visits/exam/api/search`: owner name, phone or WhatsApp number, `LIKE %text%`, first 25 matches, each listed with its active pets as buttons. ↑ ↓ move between pets, Enter picks, Esc closes. |
| **⧉ Second file / ملف ثانٍ** | Opens another blank exam screen in a new tab, so two cases can be open at once. |
| Current client strip | Client name (links to `/crm/owners/<id>`), phone (`tel:` link), WhatsApp link (Egyptian `01…` numbers get a `2` prefix), pet name (links to `/crm/pets/<id>`), species · breed · sex · age, and one chip per other animal of the same client. |

A client found with **no** animals shows a **+ Add first animal / أضف أول حيوان** button
instead of a dead row; it opens the client on the **Pets** tab with the visit form
withheld until an animal exists.

#### 5.6.2 Walk-in: new client and pet

**+ New client walked in / عميل جديد** on the empty state opens a small form:
**Client name / اسم العميل** (required), **Phone / الهاتف**, **Address / العنوان**,
**Pet name / اسم الحيوان** (required), **Species / النوع** (datalist: Canine, Feline,
Avian, Rabbit, Reptile), **Breed / السلالة**, **Sex / الجنس** (—, Male / ذكر,
Female / أنثى), **Date of birth / تاريخ الميلاد**.

**Save and start the exam / حفظ وبدء الكشف** posts to `/visits/exam/api/client`. Both
names are required or the request is refused. **If the phone number already belongs to a
client** — compared after normalising Arabic digits, spaces and the `+20` prefix — the
new animal is filed under that existing client and an amber alert says *"This number
already has a file / The animal was added to `<name>` — one mobile number, one client
file."* The name just typed is not used in that case. **Cancel / إلغاء** closes the form.

#### 5.6.3 Tabs

All twelve tabs are views of two payloads already fetched for this client
(`/visits/exam/api/pet/<id>` and `/visits/exam/api/owner/<id>`); switching tabs makes no
new request. The number on a tab is a live count.

| Tab | Badge counts | Contents |
|---|---|---|
| **Visit / الكشف** | — | The examination itself (§5.6.4–§5.6.8) |
| **Pets / الحيوانات** | pets | One card per animal (species, breed, sex, age, allergy / chronic / overdue-vaccine tags, weight); clicking one loads it into the visit. A fold adds another pet: **Pet name** (required), Species, Breed, Sex, Date of birth → **Add pet and open it / أضف الحيوان وافتحه** |
| **Owner / المالك** | — | Read-only client details: Name, Phone, WhatsApp, Email, Address, Preferred doctor, Contact by, **Outstanding / المديونية**, **Loyalty points / نقاط الولاء**, a VIP badge, plus **Edit client / تعديل العميل** (→ `/crm/owners/<id>`) and a WhatsApp link |
| **Planned / المواعيد** | upcoming | Table: Date, Time, Pet, Type, Doctor, Status (rows link to `/appointments/<id>`), plus the inline booking form below |
| **History / السجل** | visits | Every visit of **every animal this client owns** (see §5.6.9) |
| **Medical / طبي** | overdue vaccines | Three tables: **Vaccinations** (Vaccine, Given, Next due — overdue dates in red, rows link to the PDF certificate), **Medications** (Medication, Dose, Frequency, Date — rows link to `/pharmacy/prescription/<id>`), **Diagnoses** (Diagnosis, Severity, Date — rows link to the visit) |
| **Invoices / الفواتير** | unpaid | Invoice number, Date, Total, Paid, Due (red when > 0), Status pill, and a **Pay / دفع** button on every row still owing (§5.6.10) |
| **Payments / المدفوعات** | payments | Date, Invoice, Amount, Method, Received by |
| **Reminders / التذكيرات** | reminders | WhatsApp log: Date, Type (template name), first 60 characters of the message, Status |
| **Documents / الملفات** | documents | Files attached to this client's pets and visits: File, Caption, Added, By — rows open `/uploads/file/<id>` |
| **Tasks / المهام** | overdue tasks | Tick-box list (Done, Task, Due, For, Priority) and a **New task / مهمة جديدة** row: title (required), Due, Assign to, Priority (Normal / High / Low) → **Add task / أضف المهمة**. Ticking a box marks it done immediately; overdue rows show the date in red |
| **Notes / ملاحظات** | — | The client note and the pet note, read-only |

Which folds are open, which tab was last used and the billing-toggle state are
remembered in the browser (localStorage), not per user account.

#### 5.6.4 Visit tab — clinical column

| Field | Name | Notes |
|---|---|---|
| **Weight (kg) / الوزن (كجم)** | `weight_kg` | Pre-filled from the pet record. Saving it **updates the pet's stored weight**. A value ≤ 0 or > 120 shows *Check the weight / راجع الوزن* — a warning, never a block. |
| **Temp (C) / الحرارة** | `temp_c` | Below 30 or above 45 shows *Check the temperature / راجع درجة الحرارة* |
| **Visit date / تاريخ الزيارة** | `visit_date` | Defaults to today; also becomes the invoice's issue date and the vaccination's administered date |
| **Seen by / الطبيب المعالج** | `doctor_name` | Free text with a datalist of active doctors, clinic owners and super admins. Defaults to the client's *preferred doctor* when the record has one, otherwise the signed-in user. This name is written to the visit, the prescription and the vaccination. |
| **Symptom or disease / العرض أو المرض** | `symptom` | Textarea. Written to **both** `chief_complaint` and `symptoms`. |
| **Diagnosis / التشخيص** | `diagnosis` | Optional. When filled, one diagnosis row is written. |
| **Severity… / الشدة…** | `severity` | blank, Mild / خفيف, Moderate / متوسط, Severe / شديد |
| **Chronic / مزمن** | `is_chronic` | Checkbox; sets the chronic flag on the diagnosis, which is what makes the red *Chronic* alert appear on later visits |
| **Notes / ملاحظات** | `notes` | Written to the visit and copied to the invoice note |
| **Pet details / بيانات الحيوان** (fold) | — | Read-only: Name, Species, Breed, Sex, Date of birth, Age, Colour, Neutered, Microchip, Insurance |
| **Owner / المالك** (fold) | — | Read-only: Name, Phone, WhatsApp, Email, Address, Preferred doctor, Contact by, VIP badge, client note |
| Other pets of this client | — | Chips that switch the exam to a sibling animal |

**Alerts strip** (top of the form, only what applies):

| Alert | Colour | Links to |
|---|---|---|
| **Allergies / الحساسية** | red | — |
| **Chronic / أمراض مزمنة** (from the pet record) | red | — |
| **Chronic / أمراض مزمنة** (diagnoses flagged chronic) | amber | the visit that recorded it |
| **Vaccine overdue / تطعيم متأخر** with the due dates | amber | `/clinical/vaccinations?pet_id=…` |
| **Owes / مديونية** with the amount in EGP | red | `/finance/invoices?owner_id=…&status=Unpaid` |
| **Booked / موعد قادم** (one per upcoming appointment) | blue | `/appointments/<id>` |
| **Diet / النظام الغذائي** | blue | — |

Switching animals clears every typed field first, so nothing is charted against the
wrong patient; if loading an animal fails, the form is cleared and a red *"Could not
open that animal — the form was cleared…"* alert appears rather than leaving the
previous chart on screen.

#### 5.6.5 Visit tab — services and the bill

* **Type to search, then Enter / اكتب للبحث ثم Enter** matches the active service
  catalogue by English name (starts-with first, then contains) and by Arabic name,
  showing up to 12 candidates **with their prices**; ↑ ↓ and Enter choose. Text that
  matches nothing is added as a free line priced **0.00** with the cursor placed in the
  price box.
* Below it, one-tap chips for the **first six** catalogue services (by sort order).
* The table: **Item / الصنف**, **Price / السعر**, **Qty / الكمية**, **Disc % / خصم %**,
  **Total / الإجمالي**, and × to remove the line. Price, quantity and the per-line
  percentage discount are editable; the line total and the running totals recalculate as
  you type. The discount is a **percentage**, clamped to 0–100 in the browser and again
  on the server.
* **Total to pay / الإجمالي المطلوب** and **Items quantity / عدد الأصناف** sit under the
  table. **Hide billing / إخفاء الفاتورة** collapses the two money columns and moves the
  running total onto the button (below 1181 px wide the toggle is hidden because the
  layout is already one column).

A line whose quantity is zero or negative, or whose price is negative, is **silently
dropped by the server** rather than billed as one.

#### 5.6.6 Visit tab — payment

| Control | Name | Notes |
|---|---|---|
| **Payment type / طريقة الدفع** | `payment_type` | *Cash / نقدي* (default) or *VISA*. Anything other than VISA is recorded as Cash. |
| **Discount / الخصم** | `discount_type`, `discount_value` | Whole-invoice discount, `EGP` (value) or `%`. Negative values are treated as 0. |
| **Cash received / المبلغ المستلم** | `cash_received` | What the client handed over |
| **Change / الباقي** | — | handed − total, never below 0 |
| **Due / المتبقي** | — | total − what was applied, never below 0 |

Only `min(handed, total)` is recorded against the invoice; the surplus is change, not an
overpayment. The payment is written with an idempotency key of `exam-<visit>-<invoice>`,
so a double-clicked Save cannot bill twice.

#### 5.6.7 Visit tab — the four folds written with the visit

| Fold | Fields | What it writes |
|---|---|---|
| **Prescription / الروشتة** | Per row: **Medication / الدواء** (datalist of up to 400 active medication items), **Dose / الجرعة**, **Frequency / التكرار**, **Duration / المدة**, × to remove. **+ Add medication / أضف دواء** adds a row. | One `prescriptions` row (status `Active`, prescriber = the *Seen by* name) plus one item per filled row. Rows with an empty medication name are skipped. |
| **Vaccination given today / تطعيم أُعطي اليوم** | Per row: **Vaccine / التطعيم**, **Brand / الماركة**, **Batch / التشغيلة**, **Next due / الموعد القادم** (pre-filled one year after the visit date), × to remove. **+ Record a vaccination / سجّل تطعيم** adds a row. | One vaccination row per filled row, attached to this visit, administered by the *Seen by* name on the visit date. The panel states plainly that billing a vaccine and recording it are different things, and that only this sets the date the reminder uses. |
| **Book the follow-up / حجز المتابعة** | **Date / التاريخ**, **Time / الوقت**, and chips for *1 week / أسبوع*, *2 weeks / أسبوعان*, *1 month / شهر* | An appointment of type **Follow-up**, status **Scheduled**, on that date; the time defaults to **09:00** when left blank; the reason is *"Follow-up for: `<diagnosis or symptom>`"* |
| **Attach a photo or file / إرفاق صورة أو ملف** | File (jpg, jpeg, png, gif, webp, pdf, doc, docx, xls, xlsx) and **Caption / وصف** | One attachment against the visit, through the uploads module's own extension and magic-byte checks. A rejected file does **not** lose the visit: it flashes *"Photo not attached: …"* |

#### 5.6.8 Saving

| Button | Effect |
|---|---|
| **Save visit / حفظ الكشف** (or Ctrl / ⌘ + Enter anywhere on the page) | Saves everything below, then opens the invoice |
| **Save and print / حفظ وطباعة** | The same, then opens the invoice's print view |

What one Save writes, in order: the **visit** (status `Completed`, type always
`Consultation`, chief complaint and symptoms both from the symptom box) → the pet's
**weight** if one was entered → the **diagnosis** → each **vaccination** → the
**follow-up appointment** → the **prescription** → the **attachment** → the **invoice**
from the billed lines → the **payment**. Each of diagnosis, vaccination, follow-up and
prescription is written in its own guarded step: a failure there is logged and skipped
rather than losing the visit and the money.

The confirmation reads *"Visit saved. Invoice `<number>` — total X, change Y, due Z."*
If no services were billed, nothing is invoiced and the message is *"Visit saved. No
services were billed."*, landing on the visit's detail page instead.

Two consequences of the visit being saved as `Completed`: the detail screen (§5.3) will
show it read-only, so SOAP notes, extra diagnoses, a treatment plan, further
prescriptions and lab requests **cannot be added to it afterwards** (Known limits L8);
and the redirect goes to a Finance screen, which a user without the `invoicing` grant
cannot open (Known limits L3).

Leaving the page with unsaved work — a symptom, temperature, note, service line, cash
amount, file, prescription row, diagnosis or vaccination row — triggers the browser's
"leave site?" prompt.

#### 5.6.9 History tab

One row per visit of **every animal this client owns**, newest first, up to 200:
**Date / التاريخ** (always a link to the full visit), **Animal / الحيوان**,
**Type / النوع**, **Symptom or disease / العرض أو المرض**, **Diagnosis / التشخيص**
(chronic ones marked `*`), **Weight / الوزن**, **Temp / الحرارة**, **Doctor / الطبيب**,
**Charged / المبلغ** (the linked invoice's total) and **Paid / السداد** (a Paid /
Partial / Unpaid chip). Rows that have more to show (vaccines, medicines, files, the
invoice number, severities) expand on click into a detail line with **Open the full
visit → / فتح الزيارة كاملة ←**.

#### 5.6.10 Taking money from the Invoices tab

**Pay / دفع** on an unpaid row opens a modal showing the invoice number, **Total**,
**Already paid** and **Still owed**, with the amount pre-filled to the balance,
**Pay it all / سداد كامل**, and a method (Cash / نقدي, VISA, Instapay). **Paid / تم الدفع**
posts to `/finance/invoices/<id>/pay` with a per-dialog nonce so a double click is one
payment. On success the dialog closes, the invoice list refreshes, and either
*"Settled in full / تم السداد بالكامل"* (with a **+ Start a new case / بدء حالة جديدة**
button that resets the screen without a page load) or *"Payment recorded — still owed: X"*
appears. On failure the dialog **stays open** with *"The payment was NOT recorded"*.

Note that this modal is the **Finance** module's route: a signed-in user whose role
lacks the `invoicing` grant gets a redirect instead of a payment, which this screen
reads as success (Known limits L9).

#### 5.6.11 Booking any appointment from the Planned tab

The fold **+ Book an appointment / حجز موعد** carries **Animal / الحيوان** (this
client's animals only), **Type / النوع** (Consultation, Follow-up, Vaccination,
Grooming, Surgery, Lab, Emergency), **Date / التاريخ** (required), **Time / الوقت**
(defaults 09:00), **Doctor / الطبيب**, **Reason / السبب**. **Book it / احجز** posts to
`/visits/exam/api/appointment`; the server refuses an animal that is not registered to
this client. These inputs deliberately carry no form name, so they are never posted with
the examination.

#### 5.6.12 The screen's own endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/visits/exam/api/search?q=` | GET | Client search (min 2 characters, 25 owners with their pets) |
| `/visits/exam/api/pet/<pet_id>` | GET | Everything about one animal and its owner |
| `/visits/exam/api/owner/<owner_id>` | GET | The 360 view: pets, visits, appointments, invoices, payments, vaccines, diagnoses, medications, documents, WhatsApp log, tasks and the tab badges |
| `/visits/exam/api/client` | POST | Create client + first pet |
| `/visits/exam/api/pet` | POST | Add another pet to the client on screen |
| `/visits/exam/api/task` | POST | Create a task, or tick one off |
| `/visits/exam/api/appointment` | POST | Book an appointment |

All of them sit behind the same `visits` grant as the screen itself.

> Source: `platform/blueprints/visits/routes.py:675-689` (`_services`, `_medications`),
> `:691-713` (`exam_pick`), `:716-731` (`_age_text`), `:733-825` (`_exam_context`),
> `:827-843` (`exam_form`), `:850-889` (search, pet API), `:921-1044` (`_owner_360`),
> `:1046-1060` (owner API), `:1062-1126` (walk-in), `:1128-1196` (tasks),
> `:1199-1257` (appointments), `:1259-1288` (add pet), `:1290-1299` (`_exam_num`),
> `:1301-1539` (`exam_submit`: visit `:1324`, diagnosis `:1340-1357`, vaccinations `:1359-1383`, follow-up `:1385-1402`, prescription `:1404-1451`, attachment `:1436-1451`, bill `:1453-1509`, money `:1511-1535`);
> `platform/templates/visits/exam.html:15-45` (client bar), `:47-95` (empty state and
> walk-in), `:97-108` (form, hidden action), `:109-143` (tabs), `:145-345` (visit tab),
> `:355-430` (prescription, vaccination, follow-up, attachment folds),
> `:433-806` (other tabs), `:808-840` (payment modal), `:1228-1312` (bill maths),
> `:1314-1385` (service picker), `:1443-1487` (vaccination rows),
> `:1512-1548` (prescription rows), `:2014-2049` (submit, shortcuts, unload guard),
> `:2051-2068` (vitals warnings), `:2226-2382` (invoices and payment modal),
> `:2400-2484` (history)

---

### 5.7 New Visit wizard — `/workflow/`

**What it is for.** The same consultation as §5.2 + §5.3, walked through in six numbered
steps on one page, ending with the invoice and the payment. It is the screen the
sidebar's **New Visit / زيارة جديدة** entry opens.

**How to reach it.** Sidebar → CLINIC → *New Visit / زيارة جديدة*, or the URL.

**Who can open it.** Any role holding the `visits` grant (the blueprint is mapped to
that key).

**How it relates to the other screens.** The wizard writes nothing of its own. It posts
to the existing routes — `/crm/owners/new`, `/crm/pets/new`, `/visits/new`,
`/visits/<id>/diagnosis`, `/visits/<id>/prescription`, `/clinical/vaccinations/new`,
`/visits/<id>/complete`, `/finance/invoices/<id>/pay` — so every rule described
elsewhere in this chapter applies unchanged. Its own five endpoints
(`/workflow/api/owners`, `/api/today`, `/api/owner/<id>/pets`, `/api/visit/<id>`,
`/api/pet/<id>/history`) are **read-only**.

A patient panel stays pinned beside the steps for the whole visit, carrying species,
weight and — most importantly — allergies.

#### Step 1 — Client / العميل

* **Today's queue** is listed first: every appointment booked for today that is not
  Completed, Cancelled or No-Show, checked-in patients first, then by time.
* **Search** (`Name or phone… / الاسم أو رقم الهاتف…`) needs 2 characters, is debounced,
  and returns at most 12 clients matched on name, Arabic name, phone or WhatsApp, each
  with a count of their pets.
* **New client** opens: **Full name / الاسم بالكامل** *, **Name (Arabic) / الاسم بالعربية**,
  **Phone / الهاتف** *, **WhatsApp / واتساب**, **Email / البريد**, **Address / العنوان** →
  posted to the CRM's own create-client route.

#### Step 2 — Patient / الحيوان

The client's animals as cards. **New pet**: **Name / الاسم** *, **Species / النوع** *,
**Breed / السلالة**, **Sex / الجنس**, **Weight (kg) / الوزن (كجم)**,
**Date of birth / تاريخ الميلاد**, **Allergies / الحساسية** ("anything that must never
be prescribed"). **Back / رجوع** returns to step 1.

#### Step 3 — Examination / الفحص

Above the fields: the animal's allergies as a warning, and its **last five visits** with
their first diagnosis.

| Field | Required |
|---|---|
| **Chief complaint / الشكوى الرئيسية** | yes — the page refuses with *"What is the animal here for?"* |
| **Symptoms / الأعراض** | no |
| **Visit type / نوع الزيارة** | no |
| **Doctor / الطبيب** | no, pre-filled with the signed-in user |
| **Weight (kg) / الوزن**, **Temperature (°C) / الحرارة**, **Heart rate / النبض**, **Respiratory rate / التنفس** | no |

**Save & continue** creates the visit through `/visits/new` and reads the new visit id
out of the redirect. Choosing visit type *Vaccination* automatically ticks the
vaccination box waiting in step 5.

#### Step 4 — Diagnosis / التشخيص

**Diagnosis / التشخيص** (required), **Severity / الشدة** (Mild / Moderate — the default —
/ Severe), **Notes / ملاحظات**. **Save diagnosis & continue / حفظ التشخيص والمتابعة**
posts it and then **re-reads the visit from the server**, refusing to advance if the
diagnosis did not save. **Suggest differentials / اقترح تشخيصات** asks
`/ai/suggest-diagnosis`; every suggestion has an explicit "use this" — nothing is typed
into the field automatically. The whole AI strip is hidden when the AI service is not
configured.

#### Step 5 — Treatment / العلاج

* Prescription rows: **Medication / الدواء**, **Dose / الجرعة**,
  **Frequency / التكرار**, **Duration / المدة**, **Qty / الكمية**, ✕ to remove;
  **+ Add medication / إضافة دواء**. Rows with no medication name are ignored. Every line
  is posted with route **Oral** and unit **unit** — this screen has no route selector.
* **Check interactions / فحص التداخلات** calls `/ai/drug-interactions`.
* **A vaccination was given / تم إعطاء تطعيم** reveals: **Vaccine / التطعيم** (Rabies,
  DHPP, Bordetella, Leptospirosis, Feline FVRCP, FeLV, *Other… / أخرى…*),
  **Vaccine name / اسم التطعيم** (when Other), **Brand / الماركة**,
  **Batch number / رقم التشغيلة**, **Dose number / رقم الجرعة**,
  **Site / موضع الحقن** (Subcutaneous / Intramuscular / Intranasal),
  **Given on / تاريخ الإعطاء** (today), **Next dose due / الجرعة القادمة** — pre-filled
  from the vaccine's usual interval and re-calculated when the vaccine or the given date
  changes. A note under it says the owner is reminded by WhatsApp when it falls due, and
  turns into a warning if the date is cleared. For a cat, Feline FVRCP is preselected.
* **Instructions / تعليمات** becomes the prescription's note.
* **Save prescription & continue / حفظ الروشتة والمتابعة** or
  **No medication — continue / بدون دواء — متابعة**: both then save the vaccination
  (verifying from the server that it was stored) and then complete the visit.

#### Step 6 — Invoice & Payment / الفاتورة والدفع

Completing the visit is what raises the invoice (§5.3.8), so the pricing rules and
caveats there apply here too. The step shows **Invoice**, **Total**, **Due** and
**Status**; when anything is owed it offers **Amount / المبلغ** (pre-filled with the
balance), **Method / طريقة الدفع** (the configured payment gateways), **Reference / مرجع**,
**Take payment / تحصيل الدفع** and **Open invoice / فتح الفاتورة**. Choosing *Instapay*
shows the clinic's handle, a **Show QR to client / اعرض الكود للعميل** full-screen view,
an **Open payment link** and **Copy link** button, and a reminder to confirm the transfer
before recording it. When nothing is owed: *"Settled in full."* with **Open visit** and
**Start another visit**.

After the payment the wizard re-reads the invoice; if the balance has not moved it says
*"The payment was not accepted. Check the amount against the balance due."* — which is
also what a user without the `invoicing` grant sees here.

> Source: `platform/blueprints/workflow/routes.py:36-53` (page, `ai_available`),
> `:57-95` (client search), `:98-128` (today's queue), `:131-145` (pets),
> `:148-197` (visit state), `:201-225` (pet history);
> `platform/templates/workflow/index.html:427-442` (steps), `:449-497` (step 1),
> `:499-546` (step 2), `:549-591` (step 3), `:594-627` (step 4), `:630-713` (step 5),
> `:716-719` (step 6), `:728` (patient aside), `:805-813` (`postForm`),
> `:992-1024` (create visit), `:1027-1046` (diagnosis), `:1049-1105` (prescription),
> `:1113-1131` (complete), `:1133-1246` (invoice and payment),
> `:1596-1676` (vaccination), `:1278-1280` (AI hidden when unconfigured)

---

### 5.8 Vaccinations — `/clinical/vaccinations`

**What it is for.** What is due in the next month, and every vaccination on record.

**How to reach it.** Launcher card *Vaccination & Preventive Care*; **Alert / Vaccine —
تنبيه / تطعيم** and the overdue alert on the exam screen; the *Vaccinations →* link on a
pharmacy prescription; `/clinical/` redirects here. Add `?pet_id=<id>` to narrow the
whole screen to one animal — a strip then reads *"Showing vaccinations for `<pet>`"* with
a **Show all pets / عرض كل الحيوانات** link back.

**Who can open it.** Any role holding the `visits` grant (the clinical blueprint maps to
that key).

#### Due-soon banner

*"⚠️ Vaccinations Due in Next 30 Days (n)"* (English only). One card per vaccination
whose `next_due_at` falls **between today and 30 days from today**, ordered by date,
showing the pet (linked to its record), the vaccine, the owner's name and WhatsApp
number, a **Due `<date>`** badge and a **Record / تسجيل** button that opens §5.9
pre-filled with that pet.

**Vaccinations whose due date has already passed are not in this banner** — the query
excludes anything earlier than today (Known limits L10). The green *"✅ No vaccinations
due in the next 30 days."* message therefore does not mean nothing is overdue.

#### All vaccination records

| Column | Contents |
|---|---|
| **Pet / الحيوان** | Pet name (linked), owner name underneath, and — in the unfiltered view — *All vaccinations for this pet → / كل تطعيمات هذا الحيوان ←* |
| **Vaccine / اللقاح** | Vaccine name, and *Dose #n* when a dose number was recorded |
| **Brand / Batch — الماركة / الدفعة** | Brand, and *Batch: …* underneath |
| **Date Given / تاريخ الإعطاء** | `administered_at`, first 10 characters |
| **Next Due / الجرعة التالية** | Bold red when the date is today or earlier, otherwise plain; `—` when blank |
| **Administered By / أعطاه** | The name recorded at the time |
| **Site / الموضع** | Injection site |
| **Certificate / الشهادة** | **PDF** button → §5.10 |

The unfiltered list is the **200 most recent** records (by date given) across all
animals; filtered by `?pet_id=` it is that animal's complete history, but the owner name
column is then blank because the pet-filtered query does not join the owner table.

There is no search, status filter or date filter on this screen.

> Source: `platform/blueprints/clinical/routes.py:228-248`,
> `platform/models/database.py:4106-4118` (`list_vaccinations`),
> `:4120-4129` (`get_upcoming_vaccines`),
> `platform/templates/clinical/vaccinations.html:63-185`

---

### 5.9 Record vaccination — `/clinical/vaccinations/new`

**What it is for.** Writing one vaccination into an animal's record and setting the date
its reminder fires.

**How to reach it.** **＋ Record Vaccination / ＋ تسجيل تطعيم** on §5.8, or **Record /
تسجيل** on a due-soon card (which appends `?pet_id=`). The wizard (§5.7) posts to this
same route.

**Who can open it.** Any role holding the `visits` grant.

When `?pet_id=` was supplied, a blue strip shows the patient, the owner and — in red —
the pet's allergies, and the pet id travels in a hidden field.

| Field | Name | Required | Notes |
|---|---|---|---|
| **Pet ID / رقم الحيوان** | `pet_id` | **yes** | Only shown when no pet was passed in the URL. It is the **numeric record id**, typed by hand — there is no picker or search (Known limits L11). |
| **Vaccine / اللقاح** | `vaccine_name` | yes (browser-level) | Rabies, DHPP (Distemper/Hepatitis/Parvovirus/Parainfluenza), Bordetella, Leptospirosis, Feline FVRCP, FeLV (Feline Leukemia), Custom |
| **Custom Vaccine Name / اسم لقاح مخصص** | `custom_vaccine` | required when Vaccine = Custom | Replaces the stored name |
| **Brand / Manufacturer — الماركة / المُصنّع** | `vaccine_brand` | no | |
| **Batch / Lot Number — رقم الدفعة / التشغيلة** | `batch_number` | no | |
| **Dose Number / رقم الجرعة** | `dose_number` | no | 1–10, default 1 |
| **Injection Site / موضع الحقن** | `site` | no | Subcutaneous / تحت الجلد (default), Intramuscular / عضلي, Intranasal / أنفي, Oral / فموي |
| **Date Administered / تاريخ الإعطاء** | `administered_at` | yes (browser-level); the server falls back to today | |
| **Next Due Date / تاريخ الجرعة التالية** | `next_due_at` | **no, but see below** | Auto-filled when a vaccine is chosen and the box is still empty: 12 months for Rabies, DHPP, FVRCP, Leptospirosis and FeLV, 6 months for Bordetella |
| **Notes / ملاحظات** | `notes` | no | Reactions, observations |

**💉 Record Vaccination / 💉 تسجيل تطعيم** saves the row, stamps the signed-in user as
the administering person, and returns to §5.8 with *"Vaccination '`<name>`' recorded."*
**If Next Due Date was left blank it also warns:** *"No next-due date was set, so no
reminder will be sent for this vaccination."* — the WhatsApp recall reads exactly that
column. **Cancel / إلغاء** goes back without saving.

Missing pet id is refused with *"Pet is required."* The visit link (`visit_id`) is only
filled when another screen supplies it — the exam screen and the wizard do; this form
does not offer it, so a vaccination recorded here is not attached to any consultation.

> Source: `platform/blueprints/clinical/routes.py:251-317`,
> `platform/templates/clinical/vaccination_form.html:13-158`

---

### 5.10 Vaccination certificate — `/clinical/vaccinations/<vacc_id>/certificate`

The **PDF** button on §5.8 (and every vaccination row on the exam screen's Medical tab)
downloads a certificate as `vacc_cert_<pet>_<id>.pdf`, built from the vaccination, the
pet (name, species, breed, sex, date of birth, microchip), the owner (name, phone,
address) and the clinic record. If the PDF library is not installed, or generation
fails, it flashes the reason and returns to §5.8 instead of downloading.

> Source: `platform/blueprints/clinical/routes.py:320-358`,
> `platform/models/pdf_generator.py:562-577`

---

### 5.11 Lab requests queue — `/clinical/lab`

**What it is for.** The laboratory work list, split by state.

**How to reach it.** Sidebar → CLINICAL → *Lab & Vaccines / المختبر والتطعيمات*;
launcher card *Laboratory & Diagnostics*; **View Lab Module → / عرض وحدة المختبر ←** on a
visit.

**Who can open it.** Any role holding the `visits` grant.

Three tabs — **Pending**, **In Progress**, **Completed** (English only) — each with a
count badge. The tabs are client-side: all three lists are loaded with the page, each
holding up to **200** requests, newest first. The screen takes no filter parameters.

| Column | Contents |
|---|---|
| **Date / التاريخ** | Request creation date |
| **Pet / الحيوان** | Pet name (linked to the pet record), then species · owner |
| **Test / الفحص** | Test name, with the test code underneath (Pending tab only) |
| **Priority / الأولوية** | Badge: grey Routine, amber Urgent, red STAT |
| **Status / الحالة** | Pending tab only |
| **Doctor / الطبيب** | The doctor on the linked visit — not the person who raised the request |
| **Actions / إجراءات** | **View / Enter Results**, **Enter Results** or **View Results** → §5.13 |

**Nothing in the application ever sets a request to "In Progress"** — a saved result goes
straight from Pending to Completed — so that middle tab stays empty unless the status is
changed in the database (Known limits L12).

> Source: `platform/blueprints/clinical/routes.py:46-90`,
> `platform/templates/clinical/lab_list.html:70-245`

---

### 5.12 New lab request — `/clinical/lab/new`

**What it is for.** Raising a test request against a visit.

**How to reach it.** **＋ New Lab Request / ＋ طلب مختبر جديد** on §5.11, or with
`?visit_id=<id>`.

**Who can open it.** Any role holding the `visits` grant.

**Read this first:** the route requires **both** a visit id and a pet id, and the form
only carries them when it was opened with `?visit_id=` (or a pet in context). Opened
plainly from the queue button, the form has nothing to submit and the save is refused
with *"Visit and pet are required."*, returning to a blank form (Known limits L13). In
practice a lab request can only be raised from a visit — and the visit screen's own lab
panel is broken (L2), so the working route is
`/clinical/lab/new?visit_id=<the visit id>`.

| Field | Name | Required | Notes |
|---|---|---|---|
| **Test Name / اسم الفحص** | `test_name` | **yes** — empty is refused with *"Test name is required."* | Twelve preset tests plus *Custom / Other — مخصص / أخرى* |
| **Custom Test Name / اسم فحص مخصص** | `custom_test` | required when Test Name = Custom | Replaces the name; if left blank the request is filed literally as "Custom" |
| **Test Code / كود الفحص** | `test_code` | no | |
| **Priority / الأولوية** | `priority` | yes | Routine / روتيني (default), Urgent / عاجل, STAT (فوري) |
| **Sample Type / نوع العينة** | `sample_type` | no | Blood (EDTA), Blood (Serum), Urine, Feces, Swab, Tissue Biopsy, Fluid (Pleural), Fluid (Abdominal), Skin Scraping, Other |
| **Notes / Instructions — ملاحظات / تعليمات** | `notes` | no | |

**Create Lab Request / إنشاء طلب مختبر** saves it with status **Pending**, stamps the
signed-in user as the requester, and returns to §5.11 with *"Lab request for '`<test>`'
created."* **Cancel / إلغاء** returns without saving.

> Source: `platform/blueprints/clinical/routes.py:18-31` (`COMMON_TESTS`), `:93-154`,
> `platform/templates/clinical/lab_form.html:41-112`

---

### 5.13 Lab request detail and results — `/clinical/lab/<lab_id>`

**What it is for.** Reading one request and entering its result.

**How to reach it.** The action button on any row of §5.11. An unknown id returns 404.

**Who can open it.** Any role holding the `visits` grant.

**Request Information / بيانات الطلب** shows the priority and status badges, then Test
Name, Test Code, Patient (linked), Owner (linked), Visit (linked to §5.3, or *"Not linked
to a visit"*), Requesting Doctor, Sample Type, Requested (date and time) and the notes.

**Results / النتائج** lists what has already been entered: an **⚠ ABNORMAL / غير طبيعي**
badge where flagged, who reviewed it and when, the numeric value with its unit and
reference range, and the result text.

The **✏️ Enter Results / إدخال النتائج** form is shown **only while the status is not
Completed**:

| Field | Name | Required | Notes |
|---|---|---|---|
| **Result Text / Report — نص النتيجة / التقرير** | `result_text` | no | Free text |
| **Numeric Value / القيمة الرقمية** | `result_value` | no | Stored as a number. The box is a browser number field, and the server converts without checking, so anything non-numeric reaching it (from a non-browser client) errors the save |
| **Unit / الوحدة** | `unit` | no | |
| **Reference Range / المدى المرجعي** | `reference_range` | no | |
| **Mark as Abnormal / تعليم كغير طبيعي** | `is_abnormal` | no | Checkbox |

**Save Results & Mark Complete / حفظ النتائج وإنهاء الطلب** writes the result, stamps the
signed-in user and the time, **sets the request to Completed** and flashes *"Lab results
saved."* — after which the entry form disappears and the card reads *"✅ This lab request
is complete."* Nothing on the screen can reopen it or correct a saved result; a second
result can only be added by changing the status in the database.

> Source: `platform/blueprints/clinical/routes.py:157-223`,
> `platform/templates/clinical/lab_detail.html:78-244`

---

### 5.14 Surgeries list — `/clinical/surgeries`

**What it is for.** The operations register.

**How to reach it.** Launcher card *Surgery & Procedures*, or the URL — there is no
sidebar entry and no link from the visit screens.

**Who can open it.** Any role holding the `visits` grant.

Columns: **Date / التاريخ**, **Patient / المريض** (pet name, then species · owner),
**Procedure / الإجراء** (with the anesthetist underneath), **Surgeon / الجراح**,
**Anesthesia / التخدير**, **Duration / المدة** (in minutes), **Outcome / النتيجة**,
**Follow-up / المتابعة**. Newest first, **200 rows maximum**, no filters, no search, and
**no way to open a single surgery record** — the list is all there is.

> Source: `platform/blueprints/clinical/routes.py:363-381`,
> `platform/templates/clinical/surgeries.html:38-92`

---

### 5.15 Record surgery — `/clinical/surgeries/new`

**What it is for.** Writing an operation into the register after the fact.

**How to reach it.** **＋ Record Surgery** on §5.14, or with `?pet_id=`.

**Who can open it.** Any role holding the `visits` grant.

| Field | Name | Required | Notes |
|---|---|---|---|
| **Pet ID / رقم الحيوان** | `pet_id` | **yes** | Numeric record id typed by hand, unless a pet came in the URL (same limitation as §5.9) |
| **Procedure Name / اسم الإجراء** | `procedure_name` | browser-level only | |
| **Surgeon / الجراح** | `surgeon` | browser-level only | Free text |
| **Anesthetist / طبيب التخدير** | `anesthetist` | no | Free text |
| **Surgery Date / تاريخ العملية** | `surgery_date` | yes, defaults to today | |
| **Duration (minutes) / المدة (دقائق)** | `duration_min` | no | Anything not a whole number is stored as blank |
| **Anesthesia Type / نوع التخدير** | `anesthesia_type` | no | General, Local, Sedation (English only); default General |
| **Outcome / النتيجة** | `outcome` | no | Successful / ناجحة (default), Complicated / بمضاعفات, Unsuccessful / غير ناجحة, Ongoing / مستمرة |
| **Follow-up Date / تاريخ المتابعة** | `followup_date` | no | Stored only — **no appointment is created and no reminder is sent** |
| **Pre-operative Notes / ملاحظات ما قبل الجراحة** | `pre_op_notes` | no | |
| **Intra-operative Notes / ملاحظات أثناء الجراحة** | `intra_op_notes` | no | |
| **Post-operative Notes / ملاحظات ما بعد الجراحة** | `post_op_notes` | no | |
| Consent checkbox | `consent_given` | no | Stored as a yes/no flag; nothing is uploaded or printed |

**🔧 Save Surgery Record** returns to §5.14 with *"Surgery record saved."* Missing pet id
is refused with *"Pet is required."* The record is filed against the **animal**, not
against a visit: there is no `visit_id` on this form, so a surgery never appears on the
visit screen or in the exam screen's history detail.

> Source: `platform/blueprints/clinical/routes.py:43` (`ANESTHESIA_TYPES`), `:384-434`,
> `platform/templates/clinical/surgery_form.html:47-161`

---

## 6. What each Save actually writes

| Button (screen) | Rows created or changed |
|---|---|
| **Create Visit** (§5.2) | one `visits` row, status `Open`, `visit_date = datetime('now')` (UTC) |
| **Save SOAP Notes** (§5.3.2) | the four `soap_*` columns on the visit, `updated_at`, one `audit_log` row |
| **Add Diagnosis** (§5.3.3) | one `diagnoses` row (pet id copied from the visit) |
| **Save Treatment Plan** (§5.3.4) | one `treatment_plans` row per visit — inserted the first time, updated afterwards |
| **Save Prescription** (§5.3.5) | one `prescriptions` row (status `Active`) plus one `prescription_items` row per filled line |
| **Complete Visit** (§5.3.8) | visit status `Completed`; an invoice with its lines, when none is linked yet |
| **Save visit / Save and print** (§5.6.8) | one `visits` row (status `Completed`), the pet's weight, optionally one `diagnoses` row, one `vaccinations` row per filled line, one `appointments` row for the follow-up, one `prescriptions` row plus items, one `attachments` row, one invoice with its lines, and one `payments` row |
| **Paid** in the exam payment modal (§5.6.10) | one `payments` row against an existing invoice |
| **Add task** / ticking a task (§5.6.3) | one `tasks` row, or its status, `done_at` and `done_by` |
| **Book it** (§5.6.11) | one `appointments` row, status `Scheduled` |
| **Save and start the exam** (§5.6.2) | one `owners` row (unless the phone already exists) and one `pets` row |
| **Add pet and open it** (§5.6.3) | one `pets` row |
| **Record Vaccination** (§5.9) | one `vaccinations` row |
| **Create Lab Request** (§5.12) | one `lab_requests` row, status `Pending` |
| **Save Results & Mark Complete** (§5.13) | one `lab_results` row; the request's status becomes `Completed` |
| **Save Surgery Record** (§5.15) | one `surgeries` row |

Nothing in this chapter deletes anything, and only the treatment plan and the SOAP notes
can be changed after they are saved.

---

## Known limits

Each of these is behaviour in the code today, not an opinion about the design.

**L1 — Reception cannot open the screens written for reception.** The `visits` grant is
not in reception's default permission set, but the sidebar shows *New Visit* and
*Medical Visits* to everyone and the launcher shows reception the *Hatem Way — One-Screen
Exam* and *Visits & Consultations* cards. A receptionist who clicks any of them is
returned to the dashboard with *"You don't have permission to access this page."* The fix
is to add **Medical Visits & SOAP** to the reception role on the Roles screen; nothing in
the clinical code needs changing.
*(`models/database.py:4365-4367`; `blueprints/launcher/routes.py:110-120,125-135`;
`templates/base.html:112-129`)*

**L2 — The lab-request panel on the visit screen does not work.** Its form tag has no
real action (`… if false else '#'`) and its handler posts to `/clinical/lab/request`,
which no blueprint defines. The request is never created; the browser shows *"Error
submitting lab request. Please try from the Lab module."* Raise the request from
`/clinical/lab/new?visit_id=<id>` instead.
*(`templates/visits/visit_detail.html:633,967-991`; no matching route in
`blueprints/clinical/routes.py`)*

**L3 — Completing a visit or saving an exam can end on a permission error.** Both
redirect to a Finance screen (the invoice detail, or its print view). Doctors, nurses and
pharmacists hold `visits` but not `invoicing`, so they are bounced to the dashboard with
a permission message. The visit, the invoice and any payment **were** saved — the error
is about the destination, not the save.
*(`blueprints/visits/routes.py:578-580,1537-1539`; `models/database.py:4359-4368`)*

**L4 — Auto-generated invoices bill one consultation per diagnosis, often at 0.00.**
`Complete Visit` writes a *"Consultation — `<diagnosis>`"* line for **every** diagnosis on
the visit, prices it by finding the first active catalogue service whose name contains the
visit type (then "consultation"), and prices medication lines by a name match on the
catalogue. No match means **0.00**. The invoice note says *"Auto-generated from visit #N.
Please update prices."* — take it literally.
*(`blueprints/visits/routes.py:497-546`)*

**L5 — "Create Invoice" on a completed visit does not carry the visit across.** The
shortcut sends the browser to `/finance/invoices/new?visit_id=<id>`, but that screen never
reads the parameter and its form has no `visit_id` field, so nothing is pre-filled and the
resulting invoice is not linked to the visit (which means the visit keeps offering
"Create Invoice").
*(`blueprints/visits/routes.py:591-605`; `blueprints/finance/routes.py:208-305`)*

**L6 — The prescriber rule is enforced on one screen only.** On the visit-detail form a
non-prescriber must pick an active veterinarian and the name is validated. The exam screen
(§5.6) writes `prescribed_by` from whatever free text sits in **Seen by / الطبيب المعالج**
— a datalist, not a closed list — with no check that the name belongs to an active
veterinarian, or to anyone at all.
*(`blueprints/visits/routes.py:326-352` versus `:1404-1435`)*

**L7 — In the wizard, a prescription written by a non-prescriber is silently lost.** Step
5 posts no `prescribed_by`. For a nurse, a pharmacist or a branch manager the route
refuses the prescription and redirects with a red message — but because a redirect is a
successful HTTP response, the wizard treats it as saved and moves on to the invoice. No
medication is recorded, and (unlike its vaccination step, which re-reads the server) the
page does not check. Doctors, clinic owners and super admins are unaffected.
*(`templates/workflow/index.html:1078-1092,805-813`;
`blueprints/visits/routes.py:326-352`)*

**L8 — A visit saved from the exam screen cannot be added to afterwards.** It is written
as `Completed`, and the visit-detail screen renders the SOAP, diagnosis, treatment,
prescription and lab-request forms **only while the status is `Open`**. Anything left out
of the one-screen save has to be handled outside that visit.
*(`blueprints/visits/routes.py:1324-1331`; `templates/visits/visit_detail.html:237,
313,372,480,627`)*

**L9 — The exam screen can report a payment that never happened.** Its inline **Pay**
posts to the Finance route. A user without the `invoicing` grant gets a redirect to the
dashboard, which the page sees as a 200 and reports as *"Settled in full"* while the
invoice remains unpaid. The wizard's payment step does not have this problem — it re-reads
the balance and says the payment was not accepted.
*(`templates/visits/exam.html:2345-2372`; `blueprints/auth/routes.py:129-134`;
`blueprints/finance/routes.py:368-370`)*

**L10 — The vaccination "due soon" banner hides everything already overdue.** It selects
`next_due_at` between **today** and today + 30 days, so a dose that lapsed last month is
not in it, and the green *"✅ No vaccinations due in the next 30 days."* message says
nothing about overdue animals. Overdue dates do appear in red in the records table below,
and as an alert on the exam screen.
*(`models/database.py:4120-4129`; `templates/clinical/vaccinations.html:76-106`)*

**L11 — The vaccination and surgery forms ask for a numeric Pet ID.** When they are not
opened with a pet in the URL there is no picker, no search and no name lookup: staff must
know the internal record number. A wrong number is rejected by the database's foreign key
and surfaces as a server error page, not a message.
*(`templates/clinical/vaccination_form.html:46-51`;
`templates/clinical/surgery_form.html:52-56`; `models/database.py:1094,1438`)*

**L12 — The lab queue's "In Progress" tab can never fill from the application.** Saving a
result moves a request straight from `Pending` to `Completed`; no screen writes
`In Progress`.
*(`blueprints/clinical/routes.py:218-220`; the only writers of that value are in the
doctor, grooming and telemedicine modules, for other tables)*

**L13 — "New Lab Request" from the queue button cannot be submitted.** The form only
carries the visit and pet when it was opened with `?visit_id=` (or a pet in context);
opened from the queue it has neither, and the save is refused with *"Visit and pet are
required."*
*(`blueprints/clinical/routes.py:96-127`; `templates/clinical/lab_form.html:42-48`)*

**L14 — The exam screen's prescription rows are narrower than the record.** They collect
medication, dose, frequency and duration only. The server also reads an instructions
value that the screen never renders, and route, quantity and unit are not captured at all
— so a prescription written on the exam screen reaches the pharmacy without them.
*(`templates/visits/exam.html:1512-1547`; `blueprints/visits/routes.py:1404-1435`)*

**L15 — Every list here is capped and none of them page.** Visits 50 rows, vaccinations
200, each lab tab 200, surgeries 200, exam history 200 visits, the exam client search 25
clients, the wizard's client search 12. Older records can only be reached by narrowing the
filters — and only the visits list has any.
*(`blueprints/visits/routes.py:45,761,1030`; `blueprints/clinical/routes.py:62,238,372`;
`models/database.py:4116`; `blueprints/workflow/routes.py:78`)*

**L16 — Follow-up fields that book nothing.** The visit-detail treatment plan's
*Follow-up in / المتابعة خلال* and the surgery form's *Follow-up Date / تاريخ المتابعة*
are stored and displayed, but create no appointment and no reminder. Only the exam
screen's **Book the follow-up** fold and the Planned tab actually book.
*(`blueprints/visits/routes.py:264-303` and `blueprints/clinical/routes.py:384-434`,
versus `blueprints/visits/routes.py:1385-1402`)*

**L17 — Nothing in this chapter can be corrected or deleted.** There is no edit or delete
control for a diagnosis, a prescription, a prescription line, a vaccination, a lab result
or a surgery. A mistake stays on the record; only the treatment plan and the SOAP notes
can be overwritten.
*(no delete or update route exists in `blueprints/clinical/routes.py` or
`blueprints/visits/routes.py` beyond `save_soap` and `save_treatment`)*

**L18 — The clinical forms need JavaScript to submit.** The vaccination, lab-request,
lab-result and surgery templates carry no CSRF field of their own; the shared bundle adds
it as the form is submitted. With scripting disabled these four forms return the 403
security-token page.
*(`templates/clinical/*.html` — no `_csrf_token`; `static/js/platform.js:129-146`)*

**L19 — There is no surgery detail screen.** The register lists operations and the form
records them; nothing opens one afterwards, and the notes captured (pre-op, intra-op,
post-op) are visible nowhere in the application.
*(`blueprints/clinical/routes.py:363-434`; `templates/clinical/surgeries.html`)*

**L20 — Respiratory rate is collected and never shown.** `/visits/new` and the wizard both
ask for it and store it; the visit detail's Vitals card and the printout show weight,
temperature and heart rate only.
*(`blueprints/visits/routes.py:126,151`; `templates/visits/visit_detail.html:137-155`;
`templates/visits/visit_print.html:78-85`)*

**L21 — The visit-detail diagnosis form has no "chronic" flag.** The column exists, the
exam screen writes it, and the exam screen's red *Chronic* alert reads it — but a
diagnosis added on the visit screen can never be marked chronic.
*(`templates/visits/visit_detail.html:319-347`; `blueprints/visits/routes.py:253-257`
versus `:1340-1357`)*

**L22 — `/visits/new` timestamps in UTC.** The visit date is written with
`datetime('now')`, which is three hours behind Cairo, so a visit created late in the
evening is dated the previous day. The exam screen does not have this problem: its
**Visit date** field is a real local date.
*(`blueprints/visits/routes.py:133-137`; `:1034-1037` names the same UTC/Cairo gap)*

**L23 — On the exam screen, a client with no animals still has a live keyboard save.**
The visit panel and its Save buttons are hidden until an animal exists, but Ctrl/⌘+Enter
only checks that the form is on screen, so it submits to `/visits/exam`, which accepts GET
only, and the browser shows a 405 error.
*(`templates/visits/exam.html:2025-2032`, `:881-885`; `blueprints/visits/routes.py:691-692`)*

---

## Related chapters

* **Pharmacy** — dispensing the prescriptions written here, `/pharmacy/`.
* **Finance** — the invoices and payments these screens raise, `/finance/`.
* **CRM** — owner and pet records, `/crm/`.
* **Appointments** — the follow-ups and bookings made from the exam screen,
  `/appointments/`.
* **Imaging** — the studies linked from the visit topbar, `/imaging/`.
