# Doctor Portal — Reference Manual

**Module:** Doctor Workspace / مساحة الطبيب
**URL prefix:** `/doctor/`
**Blueprint:** `doctor`

This chapter is a **screen-by-screen reference**. It describes only what the
code in `blueprints/doctor/routes.py` and `templates/doctor/*.html` actually
does today. Anything that is present in the database but has no screen, or a
control that does not do what its label suggests, is listed under
[Known limits](#known-limits) rather than described as working.

> Source: `platform/app.py:226`, `platform/app.py:254` (blueprint registered),
> `platform/blueprints/doctor/__init__.py:1-3` (prefix `/doctor`)

The module is small: **seven routes, five templates, one database write.** Six
of the seven routes are read-only views assembled from data other modules
create. The seventh — check-in — is the only write, and it cannot be used as
shipped (§ 11).

---

## 1. Getting into the module

There are three doors:

| Door | Where | Goes to |
|---|---|---|
| Sidebar → CLINICAL / السريري → **Doctor Workspace / مساحة الطبيب** | every page | `/doctor/` |
| Launcher card **👨‍⚕️ Doctor Workspace / مساحة عمل الطبيب** (badge `Live`) | `/` | `/doctor/` |
| Direct URL | — | `/doctor/queue`, `/doctor/patients`, `/doctor/schedule`, `/doctor/stats` |

The sidebar entry carries **no role condition** — it is rendered for every
signed-in user. A user whose role does not hold the `visits` grant sees the
link, clicks it, and is bounced to the launcher with
*"You don't have permission to access this page."* — see § 2.

The launcher card's description reads *"My patients today · Exam queue · Pet
history · Quick prescription · Personal stats"*. **There is no prescription
route, form or link anywhere in this blueprint or its templates.**

> Source: `platform/templates/base.html:165-168` (sidebar, no role guard),
> `platform/blueprints/launcher/routes.py:325-338` (module card)

---

## 2. Who can open what

One gate applies. `login_required` maps the blueprint name to a permission key
before the route body runs. For this blueprint the key is **not** `doctor` — it
is deliberately `visits`:

```python
_BP_PERMISSION = {
    …
    "doctor":       "visits",
    …
}
```

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:88-133` (`_permission_denied`), `:140-146` (`_BP_PERMISSION`),
> `platform/models/database.py:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

**No route in this module declares a `role_required(...)` list.** There is no
second, narrower gate — whoever can open the workspace can open every screen and
issue the check-in POST.

> Source: `platform/blueprints/doctor/routes.py:27, 132, 177, 219, 279, 285, 299`

### Effective access

| Role | Holds `visits` by default | Can open any `/doctor/` screen |
|---|---|---|
| `super_admin` | exempt from the gate | ✅ |
| `clinic_owner` | holds every key | ✅ |
| `branch_manager` | yes | ✅ |
| `doctor` | yes | ✅ |
| `nurse` | yes | ✅ |
| `pharmacist` | yes | ✅ |
| `reception` | no | ❌ |
| `finance` | no | ❌ |
| `hr` | no | ❌ |
| `groomer` | no | ❌ |
| `boarding_staff` | no | ❌ |
| `inventory_mgr` | no | ❌ |
| `auditor` | no | ❌ |
| `support_admin` | no | ❌ |

**The launcher card and the real grants disagree.** The card is filtered to
`super_admin, clinic_owner, doctor, branch_manager`. So `nurse` and
`pharmacist` hold the grant but **get no card** — they must use the sidebar or
type the URL. No role gets a card it cannot use.

> Source: `platform/blueprints/launcher/routes.py:333`

**A grant is not the same as useful data.** `nurse` and `pharmacist` can open
every screen, but every screen filters on `doctor_name` (§ 3), a column that
carries vets' names. Both roles will see empty panels and zeroed counters. That
is the code behaving as written.

**Denied looks like:** red flash `You don't have permission to access this page.`,
redirect to `/`. Nothing is written.
**Signed out looks like:** `Please log in to continue.`, redirect to
`/auth/login?next=<path>`.

> Source: `platform/blueprints/auth/routes.py:62-64, 126-133`

---

## 3. The `doctor_name` filter — how "mine" is decided

Every read screen uses the same two helpers:

```python
def _doctor_name():
    user = session.get("user", {})
    return user.get("full_name") or user.get("username", "")

def _is_admin():
    return session.get("user", {}).get("role") in ("super_admin", "clinic_owner", "branch_manager")
```

> Source: `platform/blueprints/doctor/routes.py:17-19, 22-23`

Each query has two branches. **If `_is_admin()` is true the query runs with no
doctor filter at all** — clinic-wide, every branch, every vet — under headings
that still say "My Patients / مرضاي" and "My Schedule / جدولي". Otherwise the
query adds:

```sql
AND LOWER(<table>.doctor_name) LIKE '%<full_name lowercased>%'
```

> Source: `platform/blueprints/doctor/routes.py:52-54, 82-84, 158-160,
> 201-203, 249-251, 319`

Four properties of that filter that matter operationally:

1. **It is a substring match.** A profile name of `Ahmed` matches
   `Ahmed Hassan`, `Mohamed Ahmed` and `Dr. Ahmed Fathy`. Give clinicians full
   names on their staff records.
2. **It never uses `doctor_id`.** Both `appointments.doctor_id` and
   `visits.doctor_id` exist and are written by the booking and visit flows.
   This module reads neither. If reception typed `د/ أحمد` and the profile says
   `Ahmed Hassan`, nothing matches.
   > Source: `platform/models/database.py:1282-1283, 1313-1314`
3. **An empty name matches everything.** With no `full_name` and no `username`
   the pattern is `'%%'`, matching every non-NULL `doctor_name`. Rows where
   `doctor_name` is NULL still drop out (`LOWER(NULL) LIKE '%%'` is NULL).
4. **Three panels ignore it entirely even for non-admins** — see § 4 (Completed
   Today, Vaccinations Due) and § 8 (Monthly Visits Trend).

---

## 4. Things that apply to every screen

- **Every query is wrapped in a bare `except`** that logs and substitutes an
  empty list or zero. A broken query renders as an empty panel, never as an
  error. The comment on the first one records that this exact swallow hid a
  wrong column name (`a.appointment_date` for `appt_date`) for the module's
  entire life.
  > Source: `platform/blueprints/doctor/routes.py:56-61, 86-88, 101-102,
  > 109-110, 162-163, 205-206, 253-254, 306-317`
- **No CSRF-bearing forms except one, and that one omits the token.** The five
  view screens are all `GET`. The single `POST` (check-in) is rendered without a
  `_csrf_token` field, and the application shell injects none — so it always
  returns the 403 page *"Invalid or missing security token. Please go back and
  try again."*
  > Source: `platform/app.py:349-357`, `platform/models/security.py:261, 270-283`,
  > `platform/templates/base.html:13, 461` (the only token sources in the shell)
- **No audit rows.** Nothing in this blueprint calls the audit logger.
- **No money.** No EGP figure appears on any of the five templates.
- **No branch scoping.** `appointments.branch_id` and `visits.branch_id` exist
  and are read by no query here.
  > Source: `platform/models/database.py:1281, 1315`
- **Bilingual labels** come from the `t(en, ar)` helper. Where a template
  hard-codes English, this manual says so — those strings stay English in Arabic
  mode.
- **Dates.** `date.today()` is the *server's local* date; every timestamp the
  database writes is UTC (`datetime('now')`). Nothing in the application sets a
  timezone.

---

## 5. Screen: Doctor Workspace

**Route.** `GET /doctor/` → `workspace()` → `templates/doctor/workspace.html`
**Purpose.** The landing page: three counters, today's queue, unfinished visits,
boosters due this week, and a quick-nav block.

> Source: `platform/blueprints/doctor/routes.py:26-128`

### Header

Page title `Doctor Workspace / مساحة الطبيب`. Subtitle
`Welcome, Dr. <name>` — **English only**. A blue gradient banner repeats
`Good day, Dr. <name> 👨‍⚕️` (**English only**) with today's appointment count on
the right under `appointments today / موعد اليوم`.

> Source: `platform/templates/doctor/workspace.html:2-4, 14-23`

### Toolbar buttons

| Button | Effect |
|---|---|
| `+ New Visit / + زيارة جديدة` | `/visits/new` with nothing pre-filled |
| `📋 Queue / 📋 قائمة الانتظار` | `/doctor/queue` |

> Source: `platform/templates/doctor/workspace.html:6-9`

### The three counters

| Card | What it counts | Doctor-filtered? |
|---|---|---|
| `📅 Today's Appointments / 📅 مواعيد اليوم` | `len(todays_appointments)` — the rows in the panel below | yes, unless admin |
| `🔓 Open Visits / 🔓 زيارات مفتوحة` | `len(open_visits)` — **capped at 10, so it never reads above 10** | yes, unless admin |
| `✅ Completed Today / ✅ اكتملت اليوم` | `SELECT COUNT(*) FROM visits WHERE status='Completed' AND DATE(updated_at)=?` | **no — clinic-wide for every role** |

> Source: `platform/blueprints/doctor/routes.py:104-110, 112-116`;
> `platform/templates/doctor/workspace.html:26-39`

### Panel: `📋 Today's Queue / 📋 قائمة اليوم`

Query: today's `appointments` joined to `owners` and `pets`, ordered by
`appt_date, appt_start`. No row cap.

> Source: `platform/blueprints/doctor/routes.py:32-61`

Header carries a `Full Queue → / القائمة الكاملة ←` link to `/doctor/queue`.

| Column | Contents |
|---|---|
| `Time / الوقت` | **always blank** — reads `a.appointment_date`, a column that does not exist |
| `Pet / الحيوان` | pet name linked to `/crm/pets/<pet_id>`, species emoji + species beneath (🐶 Dog, 🐱 Cat, 🦜 Bird, 🐾 anything else) |
| `Owner / المالك` | owner name linked to `/crm/owners/<owner_id>`, phone beneath (plain text, not a link) |
| `Reason / السبب` | `appointments.reason`, truncated to one line with an ellipsis; `—` if empty |
| `Status / الحالة` | badge, see below |
| (unlabelled) | `Check In / تسجيل وصول` and `+ Visit / + زيارة` |

> Source: `platform/templates/doctor/workspace.html:50-94`

**Status badges on this panel:**

| Stored status | Badge |
|---|---|
| `Scheduled` | amber, `Scheduled / مجدول` |
| `In Progress` | blue, `In Progress / جارٍ` |
| `Completed` | green, `Done / منتهٍ` |
| **anything else** — `Confirmed`, `Checked-in`, `Cancelled`, `No-Show` | **red "error" badge** printing the raw status |

`Checked-in` is the status the front desk writes when a client physically
arrives, so an arrived client is painted red on this panel as though something
had gone wrong.

> Source: `platform/templates/doctor/workspace.html:75-80`,
> `platform/blueprints/appointments/routes.py:40`

**Actions:**

| Button | Shown when | Effect |
|---|---|---|
| `Check In / تسجيل وصول` | status is `Scheduled` or `Confirmed` | **403 error page — see § 11** |
| `+ Visit / + زيارة` | always, every row including `Completed` and `Cancelled` | `/visits/new?appt_id=<id>&owner_id=<id>&pet_id=<id>` — the New Visit form pre-filled from the booking |

> Source: `platform/templates/doctor/workspace.html:81-90`

**Empty state:** 🗓️, `No appointments today / لا مواعيد اليوم`,
`Enjoy the quiet — or add a walk-in. / استمتع بالهدوء — أو أضف مراجعاً بدون موعد.`,
and a button `+ Walk-in Appointment / + موعد بدون حجز` → `/appointments/new`.

> Source: `platform/templates/doctor/workspace.html:95-102`

### Panel: `🔓 Open Visits / 🔓 زيارات مفتوحة`

Query: `visits` with `status='Open'`, joined to `pets` and `owners`, ordered
`visit_date DESC`, **`LIMIT 10`**. A count badge sits in the header.

> Source: `platform/blueprints/doctor/routes.py:63-88`

Each row shows `🐾 <pet name>`, the owner name, the chief complaint (or
`No complaint noted`, **English only**), and a `Continue → / متابعة ←` button
linking straight to `/visits/<visit_id>`.

**There is no "see all" link.** A vet with fifteen open visits cannot reach five
of them from this module. Use `/visits/?status=Open`.

**Empty state:** `✅ No open visits / ✅ لا توجد زيارات مفتوحة`.

> Source: `platform/templates/doctor/workspace.html:109-131`

### Panel: `💉 Vaccinations Due (7 days) / 💉 تطعيمات مستحقة (7 أيام)`

Query: `vaccinations` joined to `pets` and `owners`, where
`DATE(next_due_at) BETWEEN today AND today+7`, ordered by `next_due_at`,
**`LIMIT 10`**.

**This panel is clinic-wide for every role, including a plain `doctor`.** Its
query joins `pets` and `owners` only; it never touches `visits` or
`doctor_name`, and there is no `_is_admin()` branch. Every vet in the branch
sees the same list.

Each row: `<pet name> — <owner name>` then `<vaccine name> · Due: <date>` with
the date in red. `Due:` is **English only**. The owner's phone is fetched by the
query and **never rendered**.

**Empty state:** `✅ No vaccinations due this week / ✅ لا تطعيمات مستحقة هذا الأسبوع`.

> Source: `platform/blueprints/doctor/routes.py:90-102`;
> `platform/templates/doctor/workspace.html:134-150`

### Panel: `⚡ Quick Actions / ⚡ إجراءات سريعة`

Five links, no logic: `📋 New Visit / 📋 زيارة جديدة` (`/visits/new`),
`👥 Queue / 👥 قائمة الانتظار`, `📅 Schedule / 📅 الجدول`,
`📊 My Stats / 📊 إحصائياتي`, `🐾 My Patients / 🐾 مرضاي`.

> Source: `platform/templates/doctor/workspace.html:152-162`

---

## 6. Screen: Today's Queue

**Route.** `GET /doctor/queue` → `queue()` → `templates/doctor/queue.html`
**Purpose.** The working view of today — wider than the workspace panel, with
phone and breed, colour-coded rows, and an automatic refresh.

> Source: `platform/blueprints/doctor/routes.py:131-173`

### Header and toolbar

Page title `Today's Queue / قائمة اليوم`. Subtitle
`<YYYY-MM-DD> · Current time: HH:MM` — **English only**. The time is the
server's clock at the moment the page was rendered
(`datetime.now().strftime("%H:%M")`), not the client's, and not necessarily
Cairo time.

| Button | Effect |
|---|---|
| `← Workspace / ← مساحة العمل` | `/doctor/` |
| `+ New Visit / + زيارة جديدة` | `/visits/new`, blank |

> Source: `platform/blueprints/doctor/routes.py:137, 170`;
> `platform/templates/doctor/queue.html:2-9`

### Auto-refresh

`<meta http-equiv="refresh" content="60">` is emitted **inside the content
block**, so the whole page reloads every 60 seconds. It is a navigation, not a
fetch: scroll position is lost and any in-page state is discarded. **There is no
control to switch it off.** A footnote reads
`Auto-refreshes every 60 seconds / تحديث تلقائي كل 60 ثانية`.

> Source: `platform/templates/doctor/queue.html:12, 92`

### The four counters

Computed in the template from the one list, not by separate queries:

| Counter | Statuses counted |
|---|---|
| `Waiting / في الانتظار` (amber) | `Scheduled`, `Confirmed`, `Waiting` |
| `In Progress / جارٍ` (blue) | `In Progress` |
| `Completed / مكتمل` (green) | `Completed` |
| `Total / الإجمالي` | every row |

**`Checked-in` is in none of the first three.** The status the front desk
actually writes on arrival counts only toward `Total`.

> Source: `platform/templates/doctor/queue.html:15-33`,
> `platform/blueprints/appointments/routes.py:40`

### The table

| Column | Contents |
|---|---|
| `#` | `loop.index` — the row's position in the list, not a ticket number |
| `Time / الوقت` | **always blank** — reads `a.appointment_date` |
| `Pet / الحيوان` | pet name linked to `/crm/pets/<pet_id>`; beneath, species emoji + `species · breed` |
| `Owner / المالك` | owner name linked to `/crm/owners/<owner_id>` |
| `Phone / الهاتف` | a `tel:` link — tap on a tablet to dial |
| `Reason / السبب` | truncated to one line; `—` if empty |
| `Status / الحالة` | badge, see below |
| `Actions / إجراءات` | `✓ In / ✓ دخول` and `+ Visit / + زيارة` |

Row shading: `In Progress` rows get a pale blue background; `Completed` rows are
dimmed to 60% opacity.

> Source: `platform/templates/doctor/queue.html:37-79`

**Status badges here** are richer than the workspace panel's:

| Stored status | Badge |
|---|---|
| `Scheduled`, `Confirmed`, `Waiting` | amber, `Waiting / في الانتظار` |
| `In Progress` | blue, `In Progress / جارٍ` |
| `Completed` | green, `Done / منتهٍ` |
| `Cancelled` | red, `Cancelled / ملغى` |
| anything else, **including `Checked-in`** | neutral badge printing the raw status |

> Source: `platform/templates/doctor/queue.html:63-67`

**Actions:**

| Button | Shown when | Effect |
|---|---|---|
| `✓ In / ✓ دخول` | status is `Scheduled`, `Confirmed` or `Waiting` — **not** `Checked-in` | **403 error page — see § 11** |
| `+ Visit / + زيارة` | always | `/visits/new?appt_id=&owner_id=&pet_id=` |

> Source: `platform/templates/doctor/queue.html:69-78`

**Empty state:** 🎉, `Queue is empty today! / قائمة الانتظار فارغة اليوم!`,
`No appointments scheduled for today. / لا توجد مواعيد مجدولة اليوم.`

> Source: `platform/templates/doctor/queue.html:80-87`

---

## 7. Screen: My Patients

**Route.** `GET /doctor/patients` → `my_patients()` →
`templates/doctor/patients.html`
**Purpose.** A browsable card grid of animals with a `visits` row naming this
doctor.

> Source: `platform/blueprints/doctor/routes.py:176-215`

### Query

```sql
SELECT DISTINCT p.id, p.pet_name, p.species, p.breed,
       o.full_name owner_name, o.phone, MAX(v.visit_date) last_visit
FROM visits v JOIN pets p ON p.id = v.pet_id
              JOIN owners o ON o.id = v.owner_id
WHERE LOWER(v.doctor_name) LIKE ?      -- omitted for admin roles
GROUP BY p.id ORDER BY last_visit DESC LIMIT 100
```

Two things to note: **no `v.status` condition** (an open visit counts), and a
hard **`LIMIT 100`** with no paging.

> Source: `platform/blueprints/doctor/routes.py:182-206`

### Header and toolbar

Title `My Patients / مرضاي`. Subtitle `All patients seen by Dr. <name>` —
**English only**. One toolbar button, `← Workspace / ← مساحة العمل`.

### Search box

Placeholder `🔍 Search pet name or owner... / 🔍 ابحث باسم الحيوان أو المالك...`.

It is **client-side only**: an `oninput` handler lowercases what you typed and
hides any card whose `data-name` attribute (`"<pet name> <owner name>"`, both
lowercased) does not contain it. It never queries the server, so it cannot reach
a patient beyond the 100-row cap, and it does not match species, breed or phone.

Beside it: `<n> patient(s) found` — **English only**, and it is the number of
cards *rendered*, not the number matching your search. It does not change as you
type.

> Source: `platform/templates/doctor/patients.html:12-13, 54-62`

### Each card

| Element | Contents |
|---|---|
| Emoji | 🐶 Dog · 🐱 Cat · 🦜 Bird · 🐰 Rabbit · 🐾 anything else |
| Name line | pet name, then `species · breed` beneath |
| Owner | `👤 <owner name>` |
| Phone | `📞 <phone>` or `📞 —` |
| Last visit | `Last visit: YYYY-MM-DD` (**English only**), omitted when null |
| `🐾 Pet record / 🐾 ملف الحيوان` | `/crm/pets/<pet_id>` |
| `Imaging / الأشعة` | the pet's imaging studies (`imaging.pet_studies`) |

A template comment records that `p.id` here is the **pet** id, so the button
must go to `pet_detail`, not `owner_detail`.

> Source: `platform/templates/doctor/patients.html:17-43`

**Empty state:** 🐾, `No patients found yet. / لا يوجد مرضى بعد.`,
`Patients appear here after you complete visits. / يظهر المرضى هنا بعد إتمام الزيارات.`

That sentence is **wrong**: the query has no status condition, so a patient
appears the moment you open a visit for them.

> Source: `platform/templates/doctor/patients.html:45-51`

---

## 8. Screen: My Schedule

**Route.** `GET /doctor/schedule` → `my_schedule()` →
`templates/doctor/schedule.html`
**Purpose.** One week of bookings in seven columns.

> Source: `platform/blueprints/doctor/routes.py:218-275`

### Week arithmetic

```python
week_offset  = int(request.args.get("week", 0))
today        = date.today()
start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
week_days    = [start_of_week + timedelta(days=i) for i in range(7)]
```

`today.weekday()` makes **Monday the first column**. There is no clamp on
`week_offset` — `?week=-500` and `?week=500` both render. A non-integer `week`
raises `ValueError` before any `try` block and produces a 500.

> Source: `platform/blueprints/doctor/routes.py:224-229`

### Grouping

Bookings are bucketed with `(a["appt_date"] or "")[:10]` compared against
`d.isoformat()`. A row whose `appt_date` is not stored as `YYYY-MM-DD…` matches
no column and **disappears from the week silently**.

> Source: `platform/blueprints/doctor/routes.py:256-263`

### Header and toolbar

Title `My Schedule / جدولي`. Subtitle `Weekly view for Dr. <name>` —
**English only**.

| Button | Effect |
|---|---|
| `← Prev Week / ← الأسبوع السابق` | `?week=<offset-1>` |
| `This Week / هذا الأسبوع` | `?week=0` |
| `Next Week → / الأسبوع التالي ←` | `?week=<offset+1>` |

> Source: `platform/templates/doctor/schedule.html:6-10`

### Each column

- **Header:** the weekday abbreviation from `strftime('%a')` (**English only**:
  `Mon`, `Tue`, …), the day number, and `<n> appt` / `<n> appts` when the day
  has bookings (**English only**).
- **Today's column** is drawn in the primary colour with white header text and a
  pale blue body.
- **Body:** one card per booking, minimum height 120px. Empty days show
  `Free / متاح`.

> Source: `platform/templates/doctor/schedule.html:13-46`

### Each booking card

Four stacked lines: the time (**always blank** — reads `a.appointment_date`), the
pet name, the owner name, and the reason truncated to one line. A coloured left
edge encodes status:

| Status | Edge colour |
|---|---|
| `Completed` | green |
| `In Progress` | blue |
| `Cancelled` | red |
| **anything else**, including `Scheduled`, `Confirmed`, `Checked-in`, `No-Show` | amber |

**The cards are `<div>`s, not links.** There is no way to open the appointment,
the pet or the owner from this screen.

The legend beneath reads `Legend: / المفتاح:` `Scheduled / مجدول` (amber),
`In Progress / جارٍ` (blue), `Completed / مكتمل` (green), `Cancelled / ملغى`
(red) — it has no entry for `Checked-in` or `No-Show`, both of which are drawn
amber and read as `Scheduled`.

> Source: `platform/templates/doctor/schedule.html:35-45, 51-57`

---

## 9. Screen: My Statistics

**Route.** `GET /doctor/stats` → `my_stats()` → `templates/doctor/stats.html`
**Purpose.** Personal workload counters, a six-month bar chart, a species split
and a top-five diagnosis list.

> Source: `platform/blueprints/doctor/routes.py:298-390`

Every query on this page goes through `safe_query` / `safe_scalar`, which return
`[]` / `0` on any exception. Failure is indistinguishable from no data.

> Source: `platform/blueprints/doctor/routes.py:306-317`

Header title `My Statistics / إحصائياتي`, subtitle
`Performance overview for Dr. <name>` (**English only**), one toolbar button
`← Workspace / ← مساحة العمل`.

### The four KPI cards

| Card | Query | Doctor-filtered? |
|---|---|---|
| `Total Visits (All Time) / إجمالي الزيارات (الإجمالي الكلي)` | `COUNT(*) FROM visits WHERE status='Completed'` | yes, unless admin |
| `This Month / هذا الشهر` | same + `DATE(visit_date) >= <1st of this month>` | yes, unless admin |
| `Avg Visits / Day / متوسط الزيارات / يوم` | `This Month ÷ today.day`, rounded to 1 dp | derived |
| `Unique Patients / مرضى فريدون` | `COUNT(DISTINCT pet_id) … status='Completed'` | yes, unless admin |

**`Avg Visits / Day` divides by the day of the month, not by days worked.** On
the 2nd, a vet who saw eleven patients on the 1st and none on the 2nd reads
`5.5`. Fridays and days off are in the denominator.

> Source: `platform/blueprints/doctor/routes.py:321-337, 372-377`;
> `platform/templates/doctor/stats.html:12-29`

### `📈 Monthly Visits Trend / 📈 اتجاه الزيارات الشهري`

An inline SVG bar chart, six bars, each labelled with an English month
abbreviation (`strftime('%b')`) and the count printed above it when non-zero.
Bar heights are scaled to the largest value, with a floor of 1 so an all-zero
chart does not divide by zero.

**This chart is clinic-wide for every role, including a plain `doctor`.** It is
the one statistic on the page whose query has no `doctor_name` condition in
either branch.

The six month boundaries are produced by subtracting `i * 28` days from the 1st
of this month and taking that date's month, then bounding each bucket as
`[first-of-that-month, first-of-next-month)`. It is a 28-day step, not calendar
arithmetic.

> Source: `platform/blueprints/doctor/routes.py:360-370`;
> `platform/templates/doctor/stats.html:34-53`

### `🐾 Species Breakdown / 🐾 توزيع الأنواع`

One horizontal bar per species with count and percentage of the total, cycling
six colours. Species emoji: 🐶 Dog, 🐱 Cat, 🦜 Bird, 🐾 other; a NULL species
renders as `Unknown`.

Doctor-filtered, but **counts every visit regardless of status** — unlike the
four KPI cards above, which count only `Completed`. The two halves of the page
do not agree.

**Empty state:** `No data yet / لا توجد بيانات بعد`.

> Source: `platform/blueprints/doctor/routes.py:350-358`;
> `platform/templates/doctor/stats.html:56-79`

### `🔬 Top 5 Diagnoses / 🔬 أكثر 5 تشخيصات`

A ranked bar list, five rows, scaled to the top row. Doctor-filtered; again
counts diagnoses on all visits regardless of status. The count badge reads
`<n> case` / `<n> cases` — **English only**.

⛔ **The diagnosis names are always blank.** The query selects `d.diagnosis`;
the template prints `d.diagnosis_text`. That key is not on the row, Jinja
resolves it to Undefined, and it renders as an empty string — so the list shows
`1. ` `12 cases`, `2. ` `9 cases`, bars correct, labels missing.

The same mismatch exists in the Clinical module, where it was found and fixed by
aliasing the column in the query, with a comment saying why:

> *"The column is `diagnosis`; both templates read `diagnosis_text`, so without
> this alias every diagnosis rendered as an empty line."*

This module never got the alias.

**Empty state:** `No diagnosis data yet / لا توجد بيانات تشخيص بعد`.

> Source: `platform/blueprints/doctor/routes.py:339-348`;
> `platform/templates/doctor/stats.html:83-102`;
> `platform/models/database.py:1334-1338` (the column is `diagnosis`);
> `platform/blueprints/visits/routes.py:186-191` (the alias, in the other module)

---

## 10. Route: Quick visit

**Route.** `GET /doctor/visit/<int:visit_id>/quick` → `quick_visit()`

```python
@doctor_bp.route("/visit/<int:visit_id>/quick")
@login_required
def quick_visit(visit_id):
    return redirect(url_for("visits.visit_detail", visit_id=visit_id))
```

> Source: `platform/blueprints/doctor/routes.py:278-281`

No template, no query, no side effect. **No template in the application links to
it** — the `Continue →` button on the workspace and both `+ Visit` buttons point
at `visits.*` endpoints directly. It is a dead alias for `/visits/<id>`, and a
302 to a URL the caller could have used.

It does **not** validate that the visit exists: a bad id redirects to
`/visits/<bad id>`, where `visit_detail` flashes `Visit not found.` and sends the
user to the visits list.

> Source: `platform/blueprints/visits/routes.py:179-181`

---

## 11. Route: Check in — the module's only write

**Route.** `POST /doctor/appointment/<int:appt_id>/checkin` → `checkin()`

```python
conn.execute("UPDATE appointments SET status='In Progress' WHERE id=?", (appt_id,))
conn.commit()
flash("Patient checked in — appointment is now In Progress.", "success")
next_url = request.form.get("next") or url_for("doctor.queue")
return redirect(next_url)
```

> Source: `platform/blueprints/doctor/routes.py:284-295`

Called from two forms — the workspace queue panel and the queue table — each
posting a hidden `next` set to `request.path`.

> Source: `platform/templates/doctor/workspace.html:83-87`,
> `platform/templates/doctor/queue.html:71-74`

### ⛔ It cannot be used as shipped

**Neither form carries a `_csrf_token` field.** The application validates a token
on every non-GET request, sourced from a `_csrf_token` form field, an
`X-CSRF-Token` header, or a JSON body key. The exempt paths are `/auth/login`,
`/settings/theme`, `/settings/lang`, `/api/public/*` and `/petsy/chat`. This
route is none of them, and `base.html` contains no script that injects a token
into forms.

**Result:** every press renders the dark 403 error page reading

> **Invalid or missing security token. Please go back and try again.**

Nothing is written; the appointment status does not change.

> Source: `platform/app.py:349-357`, `platform/models/security.py:261, 270-283`,
> `platform/templates/base.html:13, 461, 940, 1275`, `platform/templates/error.html`

### Three further defects in the same route

Relevant when the token is added:

1. **`In Progress` is not a valid appointment status.** The Appointments module
   declares `VALID_STATUSES = ["Scheduled", "Confirmed", "Checked-in",
   "Completed", "Cancelled", "No-Show"]`. Writing `In Progress` **removes the
   booking from the reception waiting room**, whose query is
   `WHERE a.status IN ('Scheduled','Confirmed','Checked-in')`.
   > Source: `platform/blueprints/appointments/routes.py:40, 778-782`
2. **No timestamp, no audit.** The route writes `status` alone — not
   `checked_in_at`, not `updated_at` — and logs nothing. The front desk's own
   helper `update_appointment_status()` does all three.
   > Source: `platform/models/database.py:1298, 3340-3350`,
   > `platform/blueprints/appointments/routes.py:436`
3. **Unvalidated redirect.** `request.form.get("next")` goes straight to
   `redirect()`. The codebase has a `_safe_next` helper written for exactly this
   — rejecting absolute URLs, protocol-relative URLs and backslash tricks — and
   this route does not call it.
   > Source: `platform/blueprints/doctor/routes.py:294`,
   > `platform/blueprints/auth/routes.py:40-52`

### What to use instead

`/appointments/reception` has a working check-in that posts a proper token,
writes `Checked-in`, stamps `checked_in_at`, and writes an audit row. See the
Front Desk chapter.

> Source: `platform/blueprints/appointments/routes.py:436`,
> `platform/templates/appointments/reception.html:413`

---

## 12. This module and the exam screen (`/visits/exam`, "Hatem Way / طريقة حاتم")

A reader arriving here needs one question answered: the doctor portal's
`+ Visit` button and the launcher's `⚡ Hatem Way — One-Screen Exam` tile both
lead to "recording a consultation" — **are they two routes to the same record,
or two different things?**

**Verified in the source: they write to the same table and are read back by the
same detail page, but they leave the record in different states, and only one of
them links the appointment.**

- `POST /visits/new` (what the portal's `+ Visit` leads to) inserts into
  `visits`. > Source: `platform/blueprints/visits/routes.py:133-160`
- `POST /visits/exam/<pet_id>` inserts into `visits`.
  > Source: `platform/blueprints/visits/routes.py:1323-1331`
- `GET /visits/<id>` reads both with one query. There is no second table, no
  record type flag, no "exam" entity.
  > Source: `platform/blueprints/visits/routes.py:163-176`

### What differs

| | **Doctor-portal path**<br>`+ Visit` → `/visits/new` → `/visits/<id>` | **Hatem Way**<br>`/visits/exam/<pet_id>` |
|---|---|---|
| `visits.status` on insert | `'Open'` | `'Completed'` |
| `visits.appointment_id` | **set** from `appt_id` | **never set — always NULL** |
| `visits.visit_type` | from the form | always `'Consultation'` |
| Vitals stored | weight, temp, heart rate, respiratory rate | weight and temp only |
| Diagnoses | any number, added on the detail page | one, typed on the same page |
| SOAP notes | yes (`POST /visits/<id>/soap`) | **none** |
| Treatment plan | yes (`POST /visits/<id>/treatment`) | **none** |
| Prescription | yes, on the detail page | yes, inline rows |
| Vaccination record with `next_due_at` | no | **yes** — the only screen that writes one |
| Follow-up booking | no | yes — inserts an `appointments` row |
| Photo attachment | separate uploads flow | yes, inline |
| Invoice | only on `POST /visits/<id>/complete`; auto-built from diagnoses and prescription items, priced by a keyword lookup against `service_catalog`, notes read *"Auto-generated from visit #N. Please update prices."* | in the same submit; real service lines, per-line % discount |
| Payment | no | yes — `Cash` or `Visa`, partial allowed, change computed |
| Editable afterwards | yes, while `status='Open'` | no — born `Completed` |

> Source: `platform/blueprints/visits/routes.py:110-160` (visit_new_submit),
> `:465-590` (complete_visit and its auto-invoice), `:1301-1331` (exam_submit's
> visit insert), `:1349, 1375, 1390, 1424` (diagnosis, vaccination, follow-up,
> prescription), `:1498-1526` (invoice and payment)

### Which to use when

| Situation | Screen |
|---|---|
| A booking exists and the visit should be tied to it | **`+ Visit` from the doctor queue** — it passes `appt_id`, the only path that fills `visits.appointment_id` |
| SOAP notes, treatment plan, heart rate or respiratory rate needed | **`+ Visit`** — Hatem Way records none of them |
| More than one diagnosis, or one to be refined later | **`+ Visit`** |
| The consultation spans the day (bloods out, animal returns) | **`+ Visit`** — `status='Open'` is what the Open Visits panel is for |
| Walk-in that starts and ends at the counter, money taken now | **Hatem Way** |
| A booster to be recorded with its next-due date | **Hatem Way** — the only screen that writes `vaccinations.next_due_at`, which the reminder job reads |
| `reception` is doing it | **Neither, as shipped** — `reception` holds no `visits` grant, so `/doctor/` and `/visits/exam` both bounce her |

### Two consequences to plan around

1. **Using both for one encounter produces two `visits` rows** for one animal on
   one day — one `Open` with an `appointment_id`, one `Completed` without.
   Neither path detects the other. There is no merge and no visit-delete route.
2. **Neither path closes the appointment.** `complete_visit` updates
   `visits.status` and creates an invoice but never touches the `appointments`
   row, even though the visit carries its `appointment_id`; `exam_submit` never
   had one. The only two writers of `appointments.status` in the whole
   application are this module's broken check-in and
   `db.update_appointment_status()`, called from the Appointments blueprint
   alone. Someone at the front desk must set each booking to `Completed` by hand.
   > Source: `platform/blueprints/visits/routes.py:491-494, 1338-1345`,
   > `platform/blueprints/doctor/routes.py:289`,
   > `platform/models/database.py:3340`,
   > `platform/blueprints/appointments/routes.py:436`

The exam screen itself is documented field by field in the **Clinical** chapter.

---

## 13. Bilingual coverage

The `t(en, ar)` helper covers page titles, table headers, badges, buttons and
empty states across all five templates. Strings that stay **English regardless
of the language setting**:

| Screen | String |
|---|---|
| Workspace | `Welcome, Dr. <name>` (subtitle) |
| Workspace | `Good day, Dr. <name> 👨‍⚕️` (banner) |
| Workspace | `No complaint noted` (open-visit fallback) |
| Workspace | `Due:` (vaccination line) |
| Queue | `<date> · Current time: HH:MM` (subtitle) |
| My Patients | `All patients seen by Dr. <name>` (subtitle) |
| My Patients | `<n> patient(s) found` |
| My Patients | `Last visit: <date>` |
| Schedule | `Weekly view for Dr. <name>` (subtitle) |
| Schedule | weekday abbreviations `Mon`…`Sun` (`strftime('%a')`) |
| Schedule | `<n> appt` / `<n> appts` |
| Statistics | `Performance overview for Dr. <name>` (subtitle) |
| Statistics | month abbreviations `Jan`…`Dec` (`strftime('%b')`) |
| Statistics | `<n> case` / `<n> cases` |

> Source: `platform/templates/doctor/workspace.html:4, 16, 121, 143`;
> `queue.html:4`; `patients.html:4, 13, 36`; `schedule.html:4, 26, 30`;
> `stats.html:4, 46, 92`

Arabic **data** renders correctly throughout — pet names, owner names, doctor
names and diagnosis text are printed as stored, and page direction flips to RTL
from the shell. There are no Arabic-only input fields in this module; it writes
no free text at all.

---

## 14. What this module writes

| Table | Column | Written by | Working? |
|---|---|---|---|
| `appointments` | `status` ← `'In Progress'` | `POST /doctor/appointment/<id>/checkin` | ❌ blocked by CSRF (§ 11) |

That is the complete list. Everything else in the module is a `SELECT`.

---

## Known limits

### Broken

1. **Check-in returns 403 on every press.** Both forms omit `_csrf_token` and
   the shell injects none. The user sees *"Invalid or missing security token.
   Please go back and try again."* Nothing is written.
   > `templates/doctor/workspace.html:83-87`, `queue.html:71-74`,
   > `app.py:349-357`, `models/security.py:261, 270-283`

2. **Every appointment time renders blank**, on all three screens that show one.
   The templates read `a.appointment_date`; the column is `appt_date`, with the
   time in `appt_start`. The queries fetch both via `SELECT a.*` and neither is
   ever printed. `(a.appointment_date or '')[-8:-3]` slices the empty string.
   > `templates/doctor/workspace.html:58`, `queue.html:45`, `schedule.html:38`,
   > `models/database.py:1289-1290`

3. **`Top 5 Diagnoses` shows counts with no names.** Query selects `diagnosis`,
   template reads `diagnosis_text`.
   > `blueprints/doctor/routes.py:339-348`, `templates/doctor/stats.html:91`

### Filters that contradict their headings

4. **`✅ Completed Today` is clinic-wide** for every role, under a
   personal-looking card on a personal-looking page.
   > `blueprints/doctor/routes.py:104-110`

5. **`💉 Vaccinations Due (7 days)` is clinic-wide** for every role.
   > `blueprints/doctor/routes.py:90-102`

6. **`📈 Monthly Visits Trend` is clinic-wide** for every role.
   > `blueprints/doctor/routes.py:360-370`

7. **"Mine" is a substring of a name, never an id.** Two vets sharing a first
   name see each other's work; a booking naming `د/ أحمد` does not match a
   profile reading `Ahmed Hassan`; a user with no name matches everyone.
   `doctor_id` exists on both tables and is read by nothing here.
   > `blueprints/doctor/routes.py:17-19, 52, 82, 158, 201, 249, 319`,
   > `models/database.py:1282-1283, 1313-1314`

8. **The statistics page counts two different things.** The four KPI cards count
   `Completed` visits; the species split and the diagnosis list count all
   visits.
   > `blueprints/doctor/routes.py:321-358`

9. **`My Patients` counts open visits**, contradicting its own empty-state text
   *"Patients appear here after you complete visits."*
   > `blueprints/doctor/routes.py:182-206`, `templates/doctor/patients.html:49`

10. **`Avg Visits / Day` divides by the day of the month**, not by days worked.
    > `blueprints/doctor/routes.py:336-337`

### Status vocabulary mismatches

11. **`Checked-in` — the status the front desk actually writes — is handled by
    no screen.** Workspace panel: **red error badge**. Queue: plain badge,
    counted only in `Total`, **no `✓ In` button**. Schedule: amber, indistinguishable
    from `Scheduled`, and absent from the legend.
    > `templates/doctor/workspace.html:75-80`, `queue.html:15, 63-75`,
    > `schedule.html:37, 51-57`, `blueprints/appointments/routes.py:40`

12. **`In Progress` — what check-in would write — is not in
    `VALID_STATUSES`,** and writing it drops the booking out of the reception
    waiting-room query.
    > `blueprints/appointments/routes.py:40, 778-782`

13. **Check-in stamps no `checked_in_at`, no `updated_at`, and no audit row.**
    > `blueprints/doctor/routes.py:288-290`, `models/database.py:3340-3350`

14. **Nothing marks an appointment `Completed` when its visit finishes** —
    neither `POST /visits/<id>/complete` nor the exam submit. The front desk must
    close each booking by hand, or the doctor queue keeps showing patients
    already seen.
    > `blueprints/visits/routes.py:491-494, 1338-1345`

### Caps, dead routes, missing links

15. **`My Patients` is capped at 100** with no paging; the search box filters
    only the cards already rendered and cannot reach past the cap.
    > `blueprints/doctor/routes.py:191, 202`, `templates/doctor/patients.html:54-62`

16. **`🔓 Open Visits` is capped at 10** with no "see all" link, and the counter
    card above it therefore never reads higher than 10.
    > `blueprints/doctor/routes.py:72, 83`

17. **`GET /doctor/visit/<id>/quick` is dead** — a bare redirect to
    `/visits/<id>` that no template links to.
    > `blueprints/doctor/routes.py:278-281`

18. **Schedule cards are not clickable** — no link to the appointment, the pet or
    the owner.
    > `templates/doctor/schedule.html:35-45`

19. **The vaccination panel fetches `o.phone` and never renders it**, so the vet
    cannot ring the owner from the panel telling her to.
    > `blueprints/doctor/routes.py:92`, `templates/doctor/workspace.html:140-145`

20. **The launcher card advertises "Quick prescription".** No such route, form or
    link exists in this module.
    > `blueprints/launcher/routes.py:329`

21. **`nurse` and `pharmacist` hold the grant but get no launcher card**; every
    signed-in user gets the ungated sidebar link and most are bounced.
    > `blueprints/launcher/routes.py:333`, `templates/base.html:165-168`,
    > `models/database.py:4359-4368`

22. **The check-in redirect target is unvalidated** — `request.form.get("next")`
    is passed straight to `redirect()` without `_safe_next`.
    > `blueprints/doctor/routes.py:294`, `blueprints/auth/routes.py:40-52`

23. **`?week=` is unbounded and unguarded.** No clamp on the offset; a
    non-integer value raises before any `try` and produces a 500.
    > `blueprints/doctor/routes.py:224`

### Silent failure and scope

24. **Every query failure is swallowed** and rendered as an empty panel or a
    zero. A code comment records that this exact pattern hid a wrong column name
    for the module's entire life. Diagnose empty panels from the application log
    (`Doctor queue query failed`, `Open-visits query failed`).
    > `blueprints/doctor/routes.py:56-61, 86-88, 101-102, 109-110, 162-163,
    > 205-206, 253-254, 306-317`

25. **No branch scoping.** `appointments.branch_id` and `visits.branch_id` exist
    and are read by no query here — a multi-branch clinic's admin roles get every
    branch merged into one queue.
    > `models/database.py:1281, 1315`

26. **Timezone.** `date.today()` is the server's local date; `updated_at` is UTC.
    Nothing sets a timezone. On a Cairo-time host the `Completed Today` counter
    is wrong for the last 2–3 hours of the day.
    > `blueprints/doctor/routes.py:29, 104-110`

27. **The queue's 60-second `<meta refresh>` is a full page reload** and cannot
    be turned off from the UI.
    > `templates/doctor/queue.html:12`

28. **The queue subtitle clock is the server's**, rendered once at page load and
    only refreshed by the meta reload.
    > `blueprints/doctor/routes.py:137, 170`

---

## Related chapters

| For | See |
|---|---|
| The one-screen exam (Hatem Way / طريقة حاتم), field by field | **Clinical** |
| Visit record, SOAP, diagnosis, prescriptions, completing and billing a visit | **Clinical** |
| Booking, rescheduling, real check-in, closing a booking, the waiting room | **Front Desk** |
| Revenue per doctor | **Insights** (`/reports/doctor-revenue`) |
| Roles and grants — including giving `reception` the `visits` key | **System** |
| Pet and owner records reached from the patient cards | **Front Desk** (CRM) |
