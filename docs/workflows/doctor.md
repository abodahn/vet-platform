# Doctor Portal — The Vet's Own Queue, Patients and Week

**Module:** `doctor` · **URL prefix:** `/doctor/` · **Blueprint:** `blueprints/doctor/routes.py` · **Templates:** `templates/doctor/`

This chapter documents **only what the code does today**. Where a screen promises
something it does not deliver, that is written down as a limit, not as a feature.
Every section ends with a `Source` line so the next writer can check the claim.

This is a small module — seven routes, five templates, one write. It is a **read-only
lens over data other modules create**, plus a single status button. Almost everything a
vet actually *does* happens in the Clinical module (`/visits/`), and the most important
thing to understand about this portal is which of its buttons hand you off there, and to
*which* of the two clinical front doors. That question has its own section (§4) because
getting it wrong produces two visit records for one animal in one day.

---

## 0. Before you start

### 0.1 The seven routes

| # | Screen | URL | What it is |
|---|--------|-----|------------|
| 1 | Doctor Workspace | `GET /doctor/` | The landing page: 3 counters, today's queue, open visits, vaccinations due |
| 2 | Today's Queue | `GET /doctor/queue` | The full queue for today, auto-refreshing |
| 3 | My Patients | `GET /doctor/patients` | Card grid of animals this vet has visit rows for |
| 4 | My Schedule | `GET /doctor/schedule` | A seven-column week of bookings |
| 5 | My Statistics | `GET /doctor/stats` | Personal counters, a bar chart, species split, top diagnoses |
| 6 | Quick visit | `GET /doctor/visit/<visit_id>/quick` | A bare redirect. No template, no inbound link — see §5 |
| 7 | Check in | `POST /doctor/appointment/<appt_id>/checkin` | The module's only write. **Broken as shipped — see §3** |

Source: `blueprints/doctor/routes.py:26, 131, 176, 218, 298, 278, 284`

Registered at `/doctor` with no extra prefix logic.
Source: `blueprints/doctor/__init__.py:2`; `app.py:226, 254`

### 0.2 Who can open it

One gate runs. `login_required` maps the blueprint name to a permission key, and for
this blueprint the key is deliberately **not** `doctor` — it is `visits`.

```
"doctor":       "visits",
```

Source: `blueprints/auth/routes.py:59-69, 88-133, 140-146`

So the portal opens for exactly the roles that hold the `visits` grant. Out of the box
that is:

| Role | Holds `visits`? | Can open `/doctor/`? |
|------|-----------------|----------------------|
| `super_admin` | bypasses both gates | ✅ |
| `clinic_owner` | holds every key | ✅ |
| `branch_manager` | yes | ✅ |
| `doctor` | yes | ✅ |
| `nurse` | yes | ✅ |
| `pharmacist` | yes | ✅ |
| `reception` | **no** | ❌ |
| `finance`, `hr`, `groomer`, `boarding_staff`, `inventory_mgr`, `auditor`, `support_admin` | no | ❌ |

Source: `models/database.py:4346-4379`

No route in this module carries a `role_required(...)` list, so there is no second,
narrower gate. Whoever can open the workspace can open every screen in it, including
the check-in POST.
Source: `blueprints/doctor/routes.py:27, 132, 177, 219, 279, 285, 299`

**What being denied looks like:** a red flash `You don't have permission to access this
page.` and a redirect to the launcher (`/`). Nothing is written.
Source: `blueprints/auth/routes.py:126-133`

**What being signed out looks like:** `Please log in to continue.` and a redirect to the
login page with `?next=` set to where you were going.
Source: `blueprints/auth/routes.py:62-64`

### 0.3 How to get in

- **Sidebar → CLINICAL / السريري → `Doctor Workspace / مساحة الطبيب`.** This link carries
  **no role condition at all** — it is rendered for every signed-in user. A receptionist,
  a groomer and the accountant all see it, click it, and are bounced to the launcher with
  the permission flash.
  Source: `templates/base.html:165-168`
- **Launcher tile `👨‍⚕️ Doctor Workspace / مساحة عمل الطبيب`**, badge `Live`, category
  *Workspaces*, description *"My patients today · Exam queue · Pet history · Quick
  prescription · Personal stats"*. The tile is filtered to
  `super_admin, clinic_owner, doctor, branch_manager`.
  Source: `blueprints/launcher/routes.py:325-338`

  ⚠️ That list and the real grant list disagree in one direction: **`nurse` and
  `pharmacist` genuinely have access but get no tile.** They must use the sidebar or type
  the URL. (The tile's description also advertises "Quick prescription", which does not
  exist anywhere in this module — see §7.)
- **Direct URL** — `/doctor/`, `/doctor/queue`, `/doctor/patients`, `/doctor/schedule`,
  `/doctor/stats`.

### 0.4 What "mine" means — the name match

Every screen except the check-in decides what is *yours* by one rule:

```python
def _doctor_name():
    user = session.get("user", {})
    return user.get("full_name") or user.get("username", "")
```

…and then filters with `LOWER(a.doctor_name) LIKE '%<that name lowercased>%'`.

Source: `blueprints/doctor/routes.py:17-19, 52-54, 82-84, 158-160, 201-203, 249-251, 319`

Three consequences a Cairo clinic will meet in its first week:

1. **It is a substring match, not an identity.** A vet whose profile full_name is
   `أحمد` (or `Ahmed`) matches every visit whose `doctor_name` contains it — including
   `Ahmed Hassan`, `Mohamed Ahmed` and `Dr. Ahmed Fathy`. Two doctors sharing a first
   name see each other's queues. Give every clinician a **full** name on their staff
   record, not a first name.
2. **It matches text, not the doctor's id.** `appointments.doctor_id` and
   `visits.doctor_id` exist and are populated, and this module never reads either. If
   reception typed `د/ أحمد` into the booking and the vet's profile says `Ahmed Hassan`,
   the booking will not appear in his queue at all.
   Source: `models/database.py:1282-1283, 1313-1314`
3. **A user with neither `full_name` nor `username` filters on `'%%'`.** That matches
   every non-NULL `doctor_name` — the whole clinic's work shows as theirs. Rows where
   `doctor_name` is NULL still drop out, because `LOWER(NULL) LIKE '%%'` is NULL.

**Admins skip the filter entirely.** `super_admin`, `clinic_owner` and `branch_manager`
get the unfiltered clinic-wide query on every screen — the same page, but showing
everyone's work under the heading "My Patients" / "مرضاي".

```python
def _is_admin():
    return session.get("user", {}).get("role") in ("super_admin", "clinic_owner", "branch_manager")
```

Source: `blueprints/doctor/routes.py:22-23`

A **nurse** or **pharmacist** who opens the portal is filtered by *her* name against
`doctor_name`, a column that almost never holds a nurse's name. She will see an empty
workspace, an empty queue, an empty patient list and zeroed stats. That is the code
working as written, not a fault to report.

### 0.5 Dates, times and money

- **"Today" is the server's local date** (`date.today()`), while every timestamp the
  database writes is UTC (`datetime('now')`). Nothing in the app sets a timezone. On a
  host running Cairo time (UTC+2/+3), the `✅ Completed Today` counter compares a Cairo
  date against UTC timestamps, so a visit closed after 21:00–22:00 Cairo lands on the
  **next** day's count.
  Source: `blueprints/doctor/routes.py:29, 104-110`; `blueprints/visits/routes.py:492`
- **There is no money anywhere in this module.** No EGP figure is rendered on any of the
  five templates. Revenue per doctor lives in Insights (`/reports/doctor-revenue`), not
  here.
- **Appointment times are not displayed on any screen.** All three templates that show a
  time read `a.appointment_date`, a column that does not exist. See §6.

### 0.6 Arabic and English

The `t('English', 'العربية')` helper covers most chrome — page titles, table headers,
badges, buttons, empty states. What stays **English regardless of the language setting**:

| Screen | English-only string |
|--------|---------------------|
| Workspace | `Welcome, Dr. <name>`, `Good day, Dr. <name> 👨‍⚕️`, `No complaint noted` |
| Queue | `<date> · Current time: HH:MM` |
| My Patients | `All patients seen by Dr. <name>`, `<n> patient(s) found`, `Last visit: <date>` |
| Schedule | the weekday row (`Mon`, `Tue`, … from `strftime('%a')`), `<n> appt` / `appts` |
| Statistics | `Performance overview for Dr. <name>`, `<n> case` / `cases` |
| Workspace (vaccinations) | `Due:` |

Source: `templates/doctor/workspace.html:4,16,121,143`; `queue.html:4`;
`patients.html:4,13,36`; `schedule.html:4,26,30`; `stats.html:4,92`

Arabic *data* renders fine — pet names, owner names and doctor names are printed as
stored, and the page direction flips to RTL from the shell.

---

## Workflow 1 — Start your clinic day

### 1.1 Who, when, why

The vet, once, on arriving. Roles that can do it: **super_admin, clinic_owner,
branch_manager, doctor, nurse, pharmacist**. The goal is a single page that answers
three questions before the first client walks in: who is booked with me today, what did
I leave unfinished, and whose booster is due this week.

### 1.2 Preconditions

- You are signed in and your role holds the `visits` grant (§0.2).
- Your staff profile's **full name matches how reception types your name into bookings**
  (§0.4). Nothing on this page works without that.
- The bookings themselves are made in the Appointments module — this portal cannot
  create one. Source: `blueprints/doctor/routes.py` has no INSERT into `appointments`.

### 1.3 The happy path

Worked example: **Dr. Ahmed Hassan / د. أحمد حسن** arrives at the Nasr City branch on a
Sunday morning.

1. **Open the workspace.** Sidebar → `Doctor Workspace / مساحة الطبيب`, or the launcher
   tile `👨‍⚕️ Doctor Workspace`.
   *You see:* a blue gradient banner reading `Good day, Dr. Ahmed Hassan 👨‍⚕️` with today's
   appointment count on the right under `appointments today / موعد اليوم`.
   Source: `templates/doctor/workspace.html:14-23`

2. **Read the three counters.**

   | Card | What it counts | Filtered to you? |
   |------|----------------|------------------|
   | `📅 Today's Appointments / 📅 مواعيد اليوم` | rows in the queue list below it | ✅ yes (unless admin) |
   | `🔓 Open Visits / 🔓 زيارات مفتوحة` | rows in the Open Visits panel — **capped at 10** | ✅ yes (unless admin) |
   | `✅ Completed Today / ✅ اكتملت اليوم` | `visits` with `status='Completed'` and `DATE(updated_at)` = today | ❌ **no — clinic-wide for everyone** |

   The third card is the odd one out. Its query carries no doctor filter at all, so a
   vet who closed two visits in a nine-vet clinic sees `23`, not `2`.
   Source: `blueprints/doctor/routes.py:104-110, 112-116`; `templates/doctor/workspace.html:26-39`

3. **Work down `📋 Today's Queue / 📋 قائمة اليوم`** on the left. Columns:
   `Time / الوقت`, `Pet / الحيوان`, `Owner / المالك`, `Reason / السبب`,
   `Status / الحالة`, and an action cell.
   *You see:* the pet name as a link to its CRM record with a species emoji beneath
   (🐶 Dog, 🐱 Cat, 🦜 Bird, 🐾 anything else), the owner name as a link to their CRM record
   with the phone under it, the booking reason truncated to one line, and a status badge.
   ⚠️ **The `Time / الوقت` column is always blank.** See §6.
   Source: `templates/doctor/workspace.html:50-94`

   Status badges on this panel:

   | Stored status | Badge shown |
   |---------------|-------------|
   | `Scheduled` | amber `Scheduled / مجدول` |
   | `In Progress` | blue `In Progress / جارٍ` |
   | `Completed` | green `Done / منتهٍ` |
   | anything else — including `Confirmed`, `Checked-in`, `Cancelled`, `No-Show` | **red "error" badge** printing the raw status |

   That last row matters: the status reception actually writes when a client arrives is
   `Checked-in`, and this panel paints it red as though something went wrong.
   Source: `templates/doctor/workspace.html:75-80`; `blueprints/appointments/routes.py:40`

4. **Check the right column.**
   - `🔓 Open Visits / 🔓 زيارات مفتوحة` — up to ten `visits` rows with `status='Open'`,
     newest first, each showing the pet, the owner, the chief complaint (or
     `No complaint noted`) and a `Continue → / متابعة ←` button straight to
     `/visits/<id>`. This is the panel that stops half-written consultations rotting.
     Source: `blueprints/doctor/routes.py:63-88`; `templates/doctor/workspace.html:109-131`
   - `💉 Vaccinations Due (7 days) / 💉 تطعيمات مستحقة (7 أيام)` — up to ten rows from
     `vaccinations` whose `next_due_at` falls between today and today+7, each showing
     pet, owner, vaccine name and the due date in red.
     ⚠️ **This panel is clinic-wide, never filtered to you**, even for a plain `doctor`
     role. Its query joins `pets` and `owners` only — it never touches `visits` or
     `doctor_name`. Every vet in the branch sees the same list.
     Source: `blueprints/doctor/routes.py:90-102`; `templates/doctor/workspace.html:134-150`
   - `⚡ Quick Actions / ⚡ إجراءات سريعة` — five buttons: `📋 New Visit / 📋 زيارة جديدة`,
     `👥 Queue / 👥 قائمة الانتظار`, `📅 Schedule / 📅 الجدول`, `📊 My Stats / 📊 إحصائياتي`,
     `🐾 My Patients / 🐾 مرضاي`.
     Source: `templates/doctor/workspace.html:152-162`

5. **Topbar.** Two buttons: `+ New Visit / + زيارة جديدة` (→ `/visits/new`, blank) and
   `📋 Queue / 📋 قائمة الانتظار` (→ `/doctor/queue`).
   Source: `templates/doctor/workspace.html:6-9`

### 1.4 The empty day

If nothing is booked for you today, the left panel replaces the table with 🗓️,
`No appointments today / لا مواعيد اليوم`,
`Enjoy the quiet — or add a walk-in. / استمتع بالهدوء — أو أضف مراجعاً بدون موعد.`
and a button `+ Walk-in Appointment / + موعد بدون حجز` → `/appointments/new`.
Source: `templates/doctor/workspace.html:95-102`

If you have no open visits: `✅ No open visits / ✅ لا توجد زيارات مفتوحة`.
If no boosters fall in the week: `✅ No vaccinations due this week / ✅ لا تطعيمات مستحقة هذا الأسبوع`.
Source: `templates/doctor/workspace.html:129, 148`

### 1.5 What a blank workspace usually means

In order of likelihood:

1. **Your profile name does not match `appointments.doctor_name`.** Open any of today's
   bookings in `/appointments/` and read the doctor field. It must *contain* your
   profile's full name as a substring.
2. **You are a nurse or a pharmacist.** See §0.4 — you are filtered against a column
   that carries vets' names.
3. **The query failed and was swallowed.** Every query on this page is wrapped in
   `try/except` that logs and substitutes an empty list. A schema drift shows up as an
   empty panel, never as an error message. The code comment on the first one says so
   plainly — that exact `except` hid a wrong column name for the module's whole life:

   > *"This swallow is why the queue was empty for the module's entire life: it queried
   > `a.appointment_date`, a column that does not exist (it is `appt_date`), and the
   > `OperationalError` vanished here."*

   Source: `blueprints/doctor/routes.py:56-61, 86-88, 101-102, 109-110`

   If a panel is empty and you cannot explain it, read the application log for
   `Doctor queue query failed` or `Open-visits query failed`.

---

## Workflow 2 — Work the queue

### 2.1 Who, when, why

The vet, between patients. The workspace panel is a summary; `/doctor/queue` is the
working view — wider, with the phone number and the breed, colour-coded rows, and a
60-second auto-refresh so it can sit on a second screen.

### 2.2 The screen

1. **Open it.** Topbar `📋 Queue`, quick action `👥 Queue`, or `Full Queue → / القائمة الكاملة ←`
   from the workspace panel header.
   *You see:* the subtitle `2026-08-20 · Current time: 09:14` (English-only), four
   counter cards, one table, and a footnote
   `Auto-refreshes every 60 seconds / تحديث تلقائي كل 60 ثانية`.
   Source: `templates/doctor/queue.html:2-12, 92`

2. **The four counters** are computed in the template from the same list, not by
   separate queries:

   | Counter | Statuses it counts |
   |---------|--------------------|
   | `Waiting / في الانتظار` (amber) | `Scheduled`, `Confirmed`, `Waiting` |
   | `In Progress / جارٍ` (blue) | `In Progress` |
   | `Completed / مكتمل` (green) | `Completed` |
   | `Total / الإجمالي` | every row |

   Source: `templates/doctor/queue.html:15-33`

   ⚠️ **`Checked-in` is in none of the first three buckets.** It is the status the front
   desk writes when a client physically arrives, and on this queue it counts only toward
   `Total`, shows a plain grey badge with the raw text `Checked-in`, and — the part that
   costs you — **gets no action button**. See §3.
   Source: `blueprints/appointments/routes.py:40`; `templates/doctor/queue.html:63-75`

3. **The table.** Columns `#`, `Time / الوقت`, `Pet / الحيوان`, `Owner / المالك`,
   `Phone / الهاتف`, `Reason / السبب`, `Status / الحالة`, `Actions / إجراءات`.
   - `#` is the row number in the list, not a ticket number.
   - `Time` is **always blank** (§6).
   - The pet cell adds the breed after the species: `🐱 Cat · Persian`.
   - The phone is a `tel:` link — tap it on a tablet and the handset dials.
   - Rows with `In Progress` get a pale blue background; `Completed` rows are dimmed to
     60% opacity.

   Source: `templates/doctor/queue.html:37-79`

4. **Status badges** here are one step richer than the workspace panel:
   `Waiting / في الانتظار` (amber, for Scheduled/Confirmed/Waiting), `In Progress / جارٍ`
   (blue), `Done / منتهٍ` (green), `Cancelled / ملغى` (red), and a neutral badge printing
   the raw status for anything else.
   Source: `templates/doctor/queue.html:63-67`

5. **Two actions per row:**
   - `✓ In / ✓ دخول` — shown only when the status is `Scheduled`, `Confirmed` or
     `Waiting`. **This button does not work — see §3.**
   - `+ Visit / + زيارة` — always shown, on every row including `Completed` and
     `Cancelled` ones. It opens `/visits/new?appt_id=<id>&owner_id=<id>&pet_id=<id>`,
     the New Visit form pre-filled from the booking. This is the real handoff to the
     clinical record.

   Source: `templates/doctor/queue.html:69-78`

### 2.3 The empty queue

`🎉`, `Queue is empty today! / قائمة الانتظار فارغة اليوم!`,
`No appointments scheduled for today. / لا توجد مواعيد مجدولة اليوم.`
Source: `templates/doctor/queue.html:80-87`

### 2.4 The auto-refresh, and what it costs you

The refresh is a `<meta http-equiv="refresh" content="60">` emitted **inside the content
block**, so it fires on the whole page every 60 seconds. It is a full navigation, not a
fetch: anything you had typed into another part of the page is discarded, and the page
scrolls back to the top. It cannot be turned off from the UI.
Source: `templates/doctor/queue.html:12`

---

## Workflow 3 — Check a booked appointment in

### 3.1 Who, when, why

Nominally: the vet, when the client for a booked slot is in the room and the
consultation is starting. The button exists so the front desk board and the vet's queue
agree on who is currently being seen.

### 3.2 What the button is supposed to do

`POST /doctor/appointment/<appt_id>/checkin` runs three statements and redirects:

```python
conn.execute("UPDATE appointments SET status='In Progress' WHERE id=?", (appt_id,))
conn.commit()
flash("Patient checked in — appointment is now In Progress.", "success")
next_url = request.form.get("next") or url_for("doctor.queue")
return redirect(next_url)
```

Source: `blueprints/doctor/routes.py:284-295`

The forms that call it are on the workspace panel and the queue, both posting a hidden
`next` set to `request.path` so you land back where you were.
Source: `templates/doctor/workspace.html:83-87`; `templates/doctor/queue.html:71-74`

### 3.3 ⛔ What actually happens

**Neither form carries a CSRF token, so the POST is rejected before the route runs.**

The application validates a token on every non-GET request, sourced from a `_csrf_token`
form field, an `X-CSRF-Token` header, or a JSON body key. Only three paths are exempt —
`/auth/login`, `/settings/theme`, `/settings/lang` — plus `/api/public/*` and
`/petsy/chat`. `/doctor/appointment/<id>/checkin` is none of those.

Source: `app.py:349-357`; `models/security.py:261, 270-283`

Both check-in forms contain exactly one input:

```html
<form method="post" action="{{ url_for('doctor.checkin', appt_id=a.id) }}" style="display:inline">
  <input type="hidden" name="next" value="{{ request.path }}">
  <button type="submit" …>{{ t('✓ In', '✓ دخول') }}</button>
</form>
```

There is no `_csrf_token` field, and `base.html` has no script that injects one into
forms — the only two token consumers in the shell are the `fetch()` calls, which set the
header themselves, and one hand-written hidden field on an unrelated form.
Source: `templates/base.html:13, 461, 940, 1275`

**So pressing `Check In / تسجيل وصول` or `✓ In / ✓ دخول` gives you the dark 403 error
page reading:**

> **Invalid or missing security token. Please go back and try again.**

Source: `app.py:356-357`; `templates/error.html`

Nothing is written. The appointment status does not change.

### 3.4 What to do instead

**Check clients in from the front desk, not from here.** `/appointments/reception` has a
working `Check In / تسجيل وصول` button that posts a proper token, writes status
`Checked-in`, stamps `checked_in_at`, and writes an audit row. See the Front Desk
chapter, Workflow 5.
Source: `blueprints/appointments/routes.py:436`; `models/database.py:3340-3350`;
`templates/appointments/reception.html:413`

### 3.5 Why you would not want this button even if it worked

The status it writes, `In Progress`, is **not in the appointments module's status
vocabulary**:

```python
VALID_STATUSES = ["Scheduled", "Confirmed", "Checked-in", "Completed", "Cancelled", "No-Show"]
```

Source: `blueprints/appointments/routes.py:40`

Three things follow from writing a status outside that list:

1. **The appointment vanishes from the reception waiting room.** The waiting-room query
   selects `WHERE a.status IN ('Scheduled','Confirmed','Checked-in')`. An `In Progress`
   booking matches none of them, so the client disappears from the display in the
   waiting area the moment the vet "checks them in".
   Source: `blueprints/appointments/routes.py:778-782`
2. **`checked_in_at` is never stamped.** The column exists and the front desk's own
   helper fills it; this route writes only `status`, and does not even touch
   `updated_at`.
   Source: `models/database.py:1298, 3340-3350`; `blueprints/doctor/routes.py:288-290`
3. **Nothing is audited.** The front desk path writes an `audit_log` row
   (`action='update_appointment_status'`); this one writes none.
   Source: `blueprints/appointments/routes.py:436`

### 3.6 One more thing about that route

`next_url = request.form.get("next") or url_for("doctor.queue")` takes the redirect
target straight from the posted form with no validation. The codebase has a `_safe_next`
helper written for exactly this — it rejects absolute URLs, protocol-relative URLs and
backslash tricks — and this route does not call it. Currently unreachable because of
§3.3, but it must be fixed at the same time as the token.
Source: `blueprints/doctor/routes.py:294`; `blueprints/auth/routes.py:40-52`

---

## Workflow 4 — Open the medical record (and the Hatem Way question)

### 4.1 The question this section answers

The vet has two ways to record a consultation, and this portal points at one of them:

- `+ Visit / + زيارة` on the queue → `/visits/new` → `/visits/<id>` — **the multi-step
  visit record.**
- `⚡ Hatem Way — One-Screen Exam / طريقة حاتم` on the launcher → `/visits/exam` — **the
  one-page exam.**

**Are they two routes to the same record, or two different things?**

Answer, from the code: **they write to the same table and are read back by the same
detail page, but they produce records of different shapes, and only one of them is
linked to the appointment.** They are the same *kind* of record reached through two
doors that leave it in different states.

### 4.2 What each one actually writes

Both end in an `INSERT INTO visits(...)`, and both redirect (eventually) to
`/visits/<visit_id>`, which is one `SELECT ... FROM visits v JOIN owners JOIN pets`.
There is no second table, no "exam" record type, no flag distinguishing them.
Source: `blueprints/visits/routes.py:133-160` (visit_new_submit),
`:1338-1345` (exam_submit), `:163-176` (visit_detail)

| | **Doctor-portal path** — `+ Visit` → `/visits/new` → `/visits/<id>` | **Hatem Way** — `/visits/exam/<pet_id>` |
|---|---|---|
| Row written | `visits` | `visits` — same table |
| `status` on insert | `'Open'` | `'Completed'` |
| `appointment_id` | **set** from `appt_id` | **never set — always NULL** |
| `visit_type` | whatever the form says | always `'Consultation'` |
| Vitals captured | weight, temp, heart rate, respiratory rate | weight and temp only |
| Diagnosis | added afterwards on the detail page, any number | one, typed on the same page |
| SOAP notes | yes, `POST /visits/<id>/soap` | **none** |
| Treatment plan | yes, `POST /visits/<id>/treatment` | **none** |
| Prescription | yes, on the detail page | yes, inline rows |
| Vaccination recorded | no — separate Clinical screen | yes, with `next_due_at` for the reminder job |
| Follow-up booked | no | yes — inserts an `appointments` row |
| Photo attached | separate uploads flow | yes, inline |
| Bill | only on `POST /visits/<id>/complete`, auto-built and **priced by keyword lookup**, notes read `Auto-generated from visit #N. Please update prices.` | in the same submit — real service lines, per-line % discount, cash tendered, change |
| Payment taken | no | yes, `Cash` or `Visa`, partial allowed |
| Editable after | **yes**, while `status='Open'` | **no** — it is born Completed |

Source: `blueprints/visits/routes.py:110-160, 465-590` (portal path);
`:1301-1331, 1349, 1375, 1390, 1424, 1498-1526` (Hatem Way);
`docs/workflows/clinical.md` Workflow 6 for the exam screen in full

### 4.3 Which to use when

| Situation | Use |
|-----------|-----|
| A booked appointment, and you want the visit tied to it | **`+ Visit` from the queue.** It passes `appt_id`, which is the only path that fills `visits.appointment_id`. |
| You need SOAP notes, a treatment plan, heart rate or respiratory rate | **`+ Visit`.** Hatem Way records none of them, ever. |
| More than one diagnosis, or a diagnosis you will refine later | **`+ Visit`.** The detail page takes diagnoses one at a time and stays open. |
| The consultation will span the day — bloods out, animal comes back | **`+ Visit`.** `status='Open'` is the whole point of the Open Visits panel. |
| A walk-in that starts and ends at the counter, money taken now | **Hatem Way.** One page, one save, invoice and cash in the same submit. |
| A booster to be recorded with its next-due date | **Hatem Way** — it is the only screen that writes a `vaccinations` row with `next_due_at`, which is what the reminder job reads. |
| Reception is doing it | **Neither, as shipped** — `reception` holds no `visits` grant, so both `/doctor/` and `/visits/exam` bounce her. |

### 4.4 The trap: do not use both for one encounter

If you open a `+ Visit` from the queue *and* run the same animal through Hatem Way, you
get **two `visits` rows for one animal on one day** — one `Open` with an
`appointment_id`, one `Completed` without. Nothing in either path detects the other. Both
appear in the visits list, both count in the vet's statistics (well — the `Completed` one
does), and the pet's history panel shows two consultations.

There is no merge, and no delete route for a visit in this codebase.

### 4.5 Neither path closes the appointment

This is the seam a Cairo clinic notices in week two. **Nothing in the clinical flow marks
the booking done.**

- `POST /visits/<id>/complete` updates `visits.status` and creates an invoice. It never
  touches the `appointments` row, even though the visit holds its `appointment_id`.
  Source: `blueprints/visits/routes.py:491-494`
- `exam_submit` never had an `appointment_id` to begin with.
  Source: `blueprints/visits/routes.py:1323-1331`

Grep confirms it: the only two places in the whole application that write
`appointments.status` are this module's broken check-in and
`db.update_appointment_status()`, which is called from the Appointments blueprint alone.
Source: `blueprints/doctor/routes.py:289`; `models/database.py:3340`;
`blueprints/appointments/routes.py:436`

**Consequence:** a booking stays `Scheduled` or `Checked-in` all day, so the doctor queue
keeps showing patients you have already seen and the `Completed / مكتمل` counter stays at
zero. Somebody at the front desk must set each booking to `Completed` by hand on
`/appointments/<id>` when the client leaves.

---

## Workflow 5 — My Patients and My Schedule

### 5.1 My Patients — `/doctor/patients`

**Who, when, why:** the vet, when a client rings and says "you saw my cat last month".
It is a browsable card grid of every animal that has a `visits` row naming you.

1. **Open it.** Quick action `🐾 My Patients / 🐾 مرضاي`, or the URL. Topbar has one
   button, `← Workspace / ← مساحة العمل`.
   Source: `templates/doctor/patients.html:6-8`

2. **The search box.** Placeholder `🔍 Search pet name or owner... / 🔍 ابحث باسم الحيوان أو المالك...`.
   It filters the cards **already on the page** with JavaScript — a lowercase substring
   match against `"<pet name> <owner name>"`. It does not query the server, so it can
   never reach a patient beyond the 100-row cap, and it does not search species, breed or
   phone.
   Source: `templates/doctor/patients.html:12, 54-62`

3. **The cards.** Each shows a large species emoji (🐶 Dog, 🐱 Cat, 🦜 Bird, 🐰 Rabbit,
   🐾 other), the pet name, `species · breed`, `👤 owner name`, `📞 phone` (or `—`), and
   `Last visit: 2026-07-14` if there is one. Two buttons:
   - `🐾 Pet record / 🐾 ملف الحيوان` → `/crm/pets/<pet_id>`
   - `Imaging / الأشعة` → the pet's imaging studies

   Source: `templates/doctor/patients.html:17-43`

4. **The count** beside the search box reads `<n> patient(s) found` — English-only, and
   it is the number of cards rendered, not the number matching your search. It does not
   change as you type.
   Source: `templates/doctor/patients.html:13`

**Two things to know about the list itself:**

- **It is capped at 100 patients**, ordered by most recent visit. A vet three years into
  practice cannot reach patient 101 from this screen at all — there is no paging, no
  "load more", and the search box cannot fetch them. Use the CRM patient list instead.
  Source: `blueprints/doctor/routes.py:191, 202`
- **The empty-state text is wrong.** It reads
  `Patients appear here after you complete visits. / يظهر المرضى هنا بعد إتمام الزيارات.`
  The query filters on `doctor_name` only and never on `v.status`, so a patient appears
  the moment you *open* a visit for them, completed or not.
  Source: `blueprints/doctor/routes.py:182-206`; `templates/doctor/patients.html:49`

Empty state: 🐾, `No patients found yet. / لا يوجد مرضى بعد.`

### 5.2 My Schedule — `/doctor/schedule`

**Who, when, why:** the vet, to see the shape of the week — which afternoons are heavy,
which are free.

1. **Open it.** Quick action `📅 Schedule / 📅 الجدول`. Topbar:
   `← Prev Week / ← الأسبوع السابق`, `This Week / هذا الأسبوع`, `Next Week → / الأسبوع التالي ←`.
   The offset rides in the URL as `?week=-1`, `?week=0`, `?week=2` and so on; there is no
   limit on how far you can page in either direction.
   Source: `templates/doctor/schedule.html:6-10`; `blueprints/doctor/routes.py:224`

2. **The grid.** Seven equal columns, **Monday first** (`today.weekday()`), each with a
   header showing the English weekday abbreviation, the day number, and
   `<n> appt` / `<n> appts` when there is anything booked. Today's column is filled and
   outlined in the primary colour with a pale blue body.
   Source: `blueprints/doctor/routes.py:225-227`; `templates/doctor/schedule.html:13-32`

3. **Each booking** is a small card with a coloured left edge, showing a time line (blank
   — §6), the pet name, the owner name and the reason. Empty days read
   `Free / متاح`.
   Source: `templates/doctor/schedule.html:35-45`

4. **The legend** — `Legend: / المفتاح:` `Scheduled / مجدول` (amber),
   `In Progress / جارٍ` (blue), `Completed / مكتمل` (green), `Cancelled / ملغى` (red).
   The edge colour is chosen by the same three-way test, with amber as the fallback, so a
   `Checked-in` or `No-Show` booking is drawn **amber and reads as Scheduled** — the
   legend has no entry for either.
   Source: `templates/doctor/schedule.html:37, 51-57`

5. **You cannot click a booking.** The cards are `<div>`s, not links. To open an
   appointment you must go to `/appointments/`.

**A parsing note that matters if data is ever inserted by hand:** grouping is done on
`(a["appt_date"] or "")[:10]` compared against `d.isoformat()`. Rows whose `appt_date` is
stored as anything other than `YYYY-MM-DD…` fall into no column and disappear from the
week silently.
Source: `blueprints/doctor/routes.py:256-263`

### 5.3 The `quick` route

`GET /doctor/visit/<visit_id>/quick` is two lines:

```python
def quick_visit(visit_id):
    return redirect(url_for("visits.visit_detail", visit_id=visit_id))
```

Source: `blueprints/doctor/routes.py:278-281`

It has no template, no query, no side effect, and **no template in the entire application
links to it** — the `Continue →` button on the workspace and the `+ Visit` buttons all
point at `visits.*` endpoints directly. It is a dead alias for `/visits/<id>`. Treat "the
quick-visit path" as the `+ Visit` button on the queue (§2.2, §4), not this route.

---

## Workflow 6 — My Statistics

**Who, when, why:** the vet or the branch manager, at month end.

Open with `📊 My Stats / 📊 إحصائياتي`. Topbar: `← Workspace`.

**Four KPI cards:**

| Card | Query | Filtered to you? |
|------|-------|------------------|
| `Total Visits (All Time) / إجمالي الزيارات (الإجمالي الكلي)` | `visits` where `status='Completed'` | ✅ yes (unless admin) |
| `This Month / هذا الشهر` | same, plus `DATE(visit_date) >= <1st of month>` | ✅ yes |
| `Avg Visits / Day / متوسط الزيارات / يوم` | `This Month ÷ today.day`, 1 dp | derived |
| `Unique Patients / مرضى فريدون` | `COUNT(DISTINCT pet_id)` on completed visits | ✅ yes |

Source: `blueprints/doctor/routes.py:321-337, 372-377`; `templates/doctor/stats.html:12-29`

⚠️ **`Avg Visits / Day` divides by the day of the month, not by days worked.** On the 2nd
of the month a vet who saw eleven patients on the 1st and none on the 2nd reads `5.5`. It
also counts Fridays and days off in the denominator.
Source: `blueprints/doctor/routes.py:336-337`

**`📈 Monthly Visits Trend / 📈 اتجاه الزيارات الشهري`** — an inline SVG bar chart, six
bars, labelled with English month abbreviations, the count printed above each non-zero
bar.

⚠️ **This chart is clinic-wide for everyone, including a plain `doctor`.** Its query is
the one statistic on the page with no `doctor_name` filter in either branch. A vet
reading `142` for July is reading the whole branch's July.
Source: `blueprints/doctor/routes.py:360-370`

The six months are stepped by subtracting 28 days at a time from the 1st of this month
and taking that date's month name, rather than by calendar arithmetic. It lands on the
right six months for ordinary calendars, but it is an approximation, not a month
calculation.
Source: `blueprints/doctor/routes.py:360-370`

**`🐾 Species Breakdown / 🐾 توزيع الأنواع`** — one bar per species with count and
percentage, six rotating colours. Filtered to you. Counts **all** your visits, not only
completed ones — unlike every card above it. Empty: `No data yet / لا توجد بيانات بعد`.
Source: `blueprints/doctor/routes.py:350-358`; `templates/doctor/stats.html:56-79`

**`🔬 Top 5 Diagnoses / 🔬 أكثر 5 تشخيصات`** — a ranked bar list. Filtered to you, and
again counts diagnoses on all your visits regardless of status.

⛔ **The diagnosis names are always blank.** The query selects `d.diagnosis`; the template
prints `d.diagnosis_text`. That key is not on the row, Jinja resolves it to Undefined,
and it renders as an empty string — so the screen shows
`1. ` `12 cases`, `2. ` `9 cases`, with the bars correct and the labels missing.

The same mismatch was already found and fixed in the Clinical module, which aliases it
explicitly and leaves a comment saying why:

> *"The column is `diagnosis`; both templates read `diagnosis_text`, so without this alias
> every diagnosis rendered as an empty line."*

This module never got the alias.
Source: `blueprints/doctor/routes.py:339-348`; `templates/doctor/stats.html:91`;
`models/database.py:1334-1338`; `blueprints/visits/routes.py:186-191`

Empty: `No diagnosis data yet / لا توجد بيانات تشخيص بعد`.

---

## Known limits

Everything below is confirmed in the source, not inferred.

### Broken

1. **Check-in cannot be used.** Both check-in forms omit `_csrf_token`, and the shell
   injects none, so every press returns the 403 page *"Invalid or missing security token.
   Please go back and try again."* Nothing is written. Check clients in from
   `/appointments/reception` instead.
   Source: `templates/doctor/workspace.html:83-87`; `templates/doctor/queue.html:71-74`;
   `app.py:349-357`; `models/security.py:261, 270-283`

2. **Every appointment time is blank.** The workspace panel, the queue table and the
   schedule cards all read `a.appointment_date`, a column that does not exist on
   `appointments` — the real columns are `appt_date` and `appt_start`, and the queries
   fetch them with `SELECT a.*`. The Jinja expression `(a.appointment_date or '')[-8:-3]`
   slices the empty string and prints nothing.
   Source: `templates/doctor/workspace.html:58`; `queue.html:45`; `schedule.html:38`;
   `models/database.py:1289-1290`

3. **Top-5 Diagnoses shows counts with no names.** Query selects `diagnosis`, template
   reads `diagnosis_text`.
   Source: `blueprints/doctor/routes.py:339-348`; `templates/doctor/stats.html:91`

### Filters that do not do what the heading says

4. **`✅ Completed Today` is clinic-wide** for every role, including a plain `doctor`.
   Source: `blueprints/doctor/routes.py:104-110`

5. **`💉 Vaccinations Due (7 days)` is clinic-wide** for every role.
   Source: `blueprints/doctor/routes.py:90-102`

6. **`📈 Monthly Visits Trend` is clinic-wide** for every role.
   Source: `blueprints/doctor/routes.py:360-370`

7. **"Mine" is a name substring, never an id.** `doctor_id` exists on both
   `appointments` and `visits` and is never used here. Two vets sharing a first name see
   each other's work; a booking typed as `د/ أحمد` does not match a profile reading
   `Ahmed Hassan`; a user with no name at all matches everyone.
   Source: `blueprints/doctor/routes.py:17-19, 52, 82, 158, 201, 249, 319`; `models/database.py:1282-1283, 1313-1314`

8. **`My Patients` counts open visits too**, contradicting its own empty-state sentence
   *"Patients appear here after you complete visits."*
   Source: `blueprints/doctor/routes.py:182-206`; `templates/doctor/patients.html:49`

9. **`Species Breakdown` and `Top 5 Diagnoses` count all visits**, while the four KPI
   cards above them count only `Completed` ones. The two halves of the statistics page do
   not agree.
   Source: `blueprints/doctor/routes.py:321-358`

### Status vocabulary mismatches

10. **`Checked-in` — what the front desk actually writes — is handled by no screen here.**
    On the workspace panel it renders as a **red error badge**; on the queue it gets a
    plain badge, is counted only in `Total`, and gets **no `✓ In` button**; on the
    schedule it is drawn amber and reads as `Scheduled`.
    Source: `templates/doctor/workspace.html:75-80`; `queue.html:15, 63-75`;
    `schedule.html:37`; `blueprints/appointments/routes.py:40`

11. **`In Progress` — what check-in would write — is not a valid appointment status.**
    Writing it removes the booking from the reception waiting-room query
    (`status IN ('Scheduled','Confirmed','Checked-in')`).
    Source: `blueprints/appointments/routes.py:40, 778-782`

12. **The check-in route does not stamp `checked_in_at`, does not touch `updated_at`, and
    writes no audit row** — all three of which the front desk's own status helper does.
    Source: `blueprints/doctor/routes.py:288-290`; `models/database.py:3340-3350`

13. **Nothing marks an appointment `Completed` when its visit is finished.** Neither
    `POST /visits/<id>/complete` nor the Hatem Way submit touches the `appointments` row.
    The front desk must close each booking by hand.
    Source: `blueprints/visits/routes.py:491-494, 1338-1345`

### Missing, capped, or dead

14. **`My Patients` is capped at 100** with no paging, and the search box filters only
    the cards already rendered.
    Source: `blueprints/doctor/routes.py:191, 202`; `templates/doctor/patients.html:54-62`

15. **`🔓 Open Visits` is capped at 10** with no "see all" link. A vet with fifteen open
    visits cannot see five of them from this module.
    Source: `blueprints/doctor/routes.py:72, 83`

16. **`GET /doctor/visit/<id>/quick` is dead.** A bare redirect to `/visits/<id>` that no
    template links to.
    Source: `blueprints/doctor/routes.py:278-281`

17. **Schedule cards are not clickable.** No link to the appointment, the pet or the
    owner.
    Source: `templates/doctor/schedule.html:35-45`

18. **The launcher tile advertises "Quick prescription".** There is no prescription route,
    form or link anywhere in this blueprint or its templates.
    Source: `blueprints/launcher/routes.py:329`

19. **The check-in redirect target is unvalidated.** `request.form.get("next")` is passed
    straight to `redirect()` without the `_safe_next` helper the codebase already has.
    Source: `blueprints/doctor/routes.py:294`; `blueprints/auth/routes.py:40-52`

20. **The sidebar link is ungated; the launcher tile is under-granted.** Every signed-in
    user sees `Doctor Workspace / مساحة الطبيب` in the sidebar and most are bounced;
    `nurse` and `pharmacist` can use the module but get no tile.
    Source: `templates/base.html:165-168`; `blueprints/launcher/routes.py:333`;
    `models/database.py:4359-4368`

21. **The queue's 60-second meta refresh is a full page reload** and cannot be turned off.
    Source: `templates/doctor/queue.html:12`

22. **Failures are invisible.** Every query on the workspace, queue, patients and schedule
    screens is wrapped in a bare `except` that substitutes an empty list. A broken query
    looks exactly like a quiet day. The statistics page does the same through its
    `safe_query` / `safe_scalar` helpers.
    Source: `blueprints/doctor/routes.py:56-61, 86-88, 101-102, 109-110, 162-163, 205-206, 253-254, 306-317`

23. **No branch scoping.** `appointments.branch_id` and `visits.branch_id` exist; no query
    in this module reads either. A multi-branch clinic's admin roles see every branch's
    work merged into one queue.
    Source: `models/database.py:1281, 1315`

24. **Timezone.** `date.today()` is the server's local date; `updated_at` is UTC. Nothing
    in the app sets a timezone. On a Cairo-time host the `Completed Today` counter is
    wrong for the last 2–3 hours of the day.
    Source: `blueprints/doctor/routes.py:29, 104-110`

---

## Cross-references

- **The exam screen itself (Hatem Way / طريقة حاتم)**, field by field —
  [`clinical.md`](clinical.md), Workflow 6.
- **The visit record, SOAP, diagnosis, prescriptions, completing and billing a visit** —
  [`clinical.md`](clinical.md), Workflows 1–5.
- **Booking, rescheduling, real check-in, and closing a booking** —
  [`frontdesk.md`](frontdesk.md), Workflows 1–5.
- **Revenue per doctor** — [`insights.md`](insights.md), Workflow 6. That report, not
  `/doctor/stats`, is where money per clinician lives.
- **Roles and grants, and how to give `reception` the `visits` key** —
  [`system.md`](system.md).
