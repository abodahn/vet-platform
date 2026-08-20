# People — HR, Attendance & Payroll — Reference Manual

**Modules:** HR & Staff / الموارد البشرية · Attendance & Leave / الحضور والإجازات ·
Payroll & Salaries / الرواتب
**URL prefixes:** `/hr/` · `/attendance/` · `/payroll/`
**Blueprints:** `hr` (31 routes) · `attendance` (21 routes) · `payroll` (13 routes)

This chapter is a **screen-by-screen reference** for the three modules that deal
with the clinic's own staff rather than its clients. It describes only what the
code in `blueprints/hr/routes.py`, `blueprints/attendance/routes.py`,
`blueprints/payroll/routes.py` and the templates under `templates/hr/`,
`templates/attendance/` and `templates/payroll/` actually does today. A control
that exists on screen but does nothing, and a database column with no screen
behind it, is listed under [Known limits](#known-limits) rather than written up
as a working feature.

The three modules are documented together because they are one chain in
practice: HR assigns the shift, attendance measures the day against that shift,
and payroll pays for the hours attendance recorded. Where a number crosses a
module boundary, this chapter says which side computes it.

The **access-control parts of the staff record** — the role dropdown, the
password policy, the role-change guard — are also covered from the security side
in the [System chapter](system.md) § 5. This chapter covers the whole employee
record, and repeats only what is needed to describe the screen.

> Source: `platform/app.py:217`, `:229`, `:245`, `:257`, `:268-269` (blueprints
> registered), `platform/blueprints/hr/__init__.py:2`,
> `platform/blueprints/attendance/__init__.py:2`,
> `platform/blueprints/payroll/__init__.py:3` (URL prefixes)

---

## 1. Getting into the modules

| Door | Where | Goes to |
|---|---|---|
| Sidebar → TEAM / الفريق → **HR & Staff / الموارد البشرية** | every page | `/hr/staff` (Staff list — **not** the HR dashboard) |
| Sidebar → TEAM / الفريق → **Attendance / الحضور والإجازات** | every page | `/attendance/` |
| Sidebar → TEAM / الفريق → **Payroll / الرواتب** | every page | `/payroll/` |
| Launcher card **Admin & HR / الإدارة والموارد البشرية** (👥) | `/` | `/hr/staff` |
| Launcher card **Attendance & Leave Management / الحضور وإدارة الإجازات** (⏱) | `/` | `/attendance/` |
| Launcher card **Payroll & Salaries / الرواتب والأجور** (💵) | `/` | `/payroll/` |
| HR Dashboard → Quick Links | `/hr/dashboard` | Attendance Dashboard, Payroll Dashboard, Manage Shifts, Performance Reviews |
| Payslip / salary detail → attendance links | `/payroll/salaries/<id>` | the attendance rows and the monthly report behind that payslip |

The sidebar **TEAM** group is rendered only for roles
`super_admin`, `clinic_owner`, `branch_manager`, `support_admin`, `hr`. Two of
those five — `branch_manager` and `support_admin` — cannot open HR or Payroll at
all (§ 2); they see three links, and two of them bounce.

The launcher shows a card when the signed-in role is in that card's own
hardcoded list, which is **not** the permission system:

| Card | Card's role list | Reality |
|---|---|---|
| Admin & HR | super_admin, clinic_owner, branch_manager | `branch_manager` is bounced by the module gate; **`hr` is not offered the card at all**, although it is the one non-owner role that can use the module |
| Attendance & Leave | super_admin, clinic_owner, branch_manager, hr, staff, doctor, nurse, reception | `pharmacist`, `inventory_mgr`, `groomer`, `boarding_staff` all hold the `attendance` grant and can use the module, but get no card. `staff` is not a role that exists |
| Payroll & Salaries | super_admin, clinic_owner, branch_manager, hr, finance | `branch_manager` and `hr` are bounced from every payroll admin screen |

There is **no HR Dashboard link anywhere in the sidebar or the launcher**. The
only ways to reach `/hr/dashboard` are the *HR Dashboard / لوحة الموارد البشرية*
button in the topbar of the Staff list, Certifications, Roster, Overtime and HR
Attendance screens, or typing the URL. `GET /hr/` redirects there.

> Source: `platform/templates/base.html:226-249` (TEAM group and its role
> condition), `platform/blueprints/launcher/routes.py:431-475` (the three module
> cards), `:574-579` (`_visible_modules`),
> `platform/templates/launcher.html:609-627` (card link uses the card's `url`),
> `platform/blueprints/hr/routes.py:244-247` (`/hr/` → dashboard),
> `platform/templates/hr/staff_list.html:9-11`

---

## 2. Who can open what

Two independent gates apply to every screen in all three modules, and **both
must pass**:

1. **The module grant.** The role must hold the permission key for the
   blueprint: `hr`, `attendance` or `payroll`. This is checked inside
   `login_required`, so it applies to every route including those with no role
   list. `super_admin` bypasses it.
2. **The route's own role list**, where one is declared with `@role_required`.

A grant can only ever narrow; it never widens. A route decorated
`@self_service` is exempt from the module grant only — login is still required
and the route scopes its own query to the caller.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:72-86` (`self_service`), `:89-134` (`_permission_denied`, the module gate),
> `:167-194` (`role_required`),
> `platform/models/database.py:4302-4331` (`ALL_PERMISSIONS`),
> `:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

### Which roles hold which grant, out of the box

| Grant | Roles that hold it by default |
|---|---|
| `hr` | **clinic_owner**, **hr** — and nobody else |
| `attendance` | clinic_owner, branch_manager, doctor, nurse, reception, pharmacist, inventory_mgr, groomer, boarding_staff, hr |
| `payroll` | clinic_owner, finance, **hr** |

`super_admin` is exempt from the check entirely. `finance`, `support_admin` and
`auditor` do **not** hold `attendance`. `branch_manager` does **not** hold `hr`
or `payroll`.

The `hr` role is real and seeded — *HR Officer / موظف الموارد البشرية*, colour
`#7e22ce` — with grants `["hr", "attendance", "payroll"]`.

> Source: `platform/models/database.py:2435-2450` (`_SEED_ROLES`, `hr` at
> `:2445`), `:4346-4379`

### Effective access — HR (`/hr/`)

Verified by signing in as each seeded role and requesting each route.

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| Module entry | `GET /hr/` | none (login only) | super_admin, clinic_owner, hr |
| Dashboard | `GET /hr/dashboard` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| Staff list | `GET /hr/staff` | same five | super_admin, clinic_owner, hr |
| New staff | `GET/POST /hr/staff/new` | same five | super_admin, clinic_owner, hr |
| Staff detail | `GET /hr/staff/<id>` | same five | super_admin, clinic_owner, hr |
| Edit staff | `GET/POST /hr/staff/<id>/edit` | same five | super_admin, clinic_owner, hr |
| Reset password | `POST /hr/staff/<id>/reset-password` | super_admin, clinic_owner, support_admin | **super_admin, clinic_owner** — `hr` cannot reset a password |
| Assign shift | `POST /hr/staff/<id>/assign-shift` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| Roles list | `GET /hr/roles` | super_admin, clinic_owner, branch_manager, support_admin | **super_admin, clinic_owner** — `hr` is not on the list |
| Performance list | `GET /hr/performance` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| New review | `GET/POST /hr/performance/new` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| Review detail | `GET /hr/performance/<id>` | none (login only) + subject check | HR roles for anyone's review; every other role only their own |
| Edit review | `GET/POST /hr/performance/<id>/edit` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| Acknowledge review | `POST /hr/performance/<id>/acknowledge` | none, `@self_service` + subject check | the employee the review is about, or an HR role |
| Add warning | `POST /hr/staff/<id>/warnings/add` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| Acknowledge warning | `POST /hr/staff/<id>/warnings/<wid>/acknowledge` | none, `@self_service` + subject check | the employee the warning is about, or an HR role |
| Delete warning | `POST /hr/staff/<id>/warnings/<wid>/delete` | super_admin, clinic_owner | super_admin, clinic_owner |
| Certifications list | `GET /hr/certifications` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| Add certification | `POST /hr/staff/<id>/certifications/add` | same five | super_admin, clinic_owner, hr |
| Delete certification | `POST /hr/staff/<id>/certifications/<cid>/delete` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| Add HR note | `POST /hr/staff/<id>/notes/add` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| Delete HR note | `POST /hr/staff/<id>/notes/<nid>/delete` | super_admin, clinic_owner | super_admin, clinic_owner |
| Weekly roster | `GET /hr/roster` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| Overtime log | `GET /hr/overtime` | same five | super_admin, clinic_owner, hr |
| Log overtime | `POST /hr/staff/<id>/overtime/add` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| Approve / reject overtime | `POST /hr/overtime/<id>/approve`, `/reject` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| HR attendance search | `GET /hr/attendance` | super_admin, clinic_owner, branch_manager, support_admin, hr | super_admin, clinic_owner, hr |
| Log attendance | `POST /hr/attendance/add` | same five | super_admin, clinic_owner, hr |
| Delete attendance record | `POST /hr/attendance/<id>/delete` | super_admin, clinic_owner, branch_manager, hr | super_admin, clinic_owner, hr |
| Headcount JSON | `GET /hr/api/headcount` | none (login only) | super_admin, clinic_owner, hr |

**`branch_manager` and `support_admin` are named on almost every HR route and
can reach none of them.** Neither role holds the `hr` grant, so the module gate
rejects them first with *"You don't have permission to access this page."* and a
redirect to the launcher. To make those role lists mean anything, an
administrator must add the **HR & Staff** grant to the role on the Roles screen
(System § 4).

### Effective access — Attendance (`/attendance/`)

Attendance has no `@role_required` anywhere. Manager-only screens check
`_allowed_manager(user)` inside the function — role in
`super_admin, clinic_owner, branch_manager, hr` — and flash *"Access denied."*
otherwise.

| Screen / action | Route | Manager check? | Who can actually use it |
|---|---|---|---|
| Dashboard | `GET /attendance/` | no (panels differ) | every role holding `attendance` |
| Check in / out | `GET/POST /attendance/checkin` | recording for **someone else** requires it | everyone for themselves; managers for anyone |
| Records list | `GET /attendance/records` | no — non-managers are scoped to their own rows | everyone holding `attendance` |
| Edit record | `GET/POST /attendance/records/edit/<id>` | **yes** | super_admin, clinic_owner, branch_manager, hr |
| Leave requests | `GET /attendance/leaves` | no — non-managers see only their own | everyone holding `attendance` |
| New leave request | `GET/POST /attendance/leaves/new` | no | everyone holding `attendance`, for themselves only |
| Leave detail | `GET /attendance/leaves/<id>` | own request, or manager | own; managers see any |
| Approve / reject leave | `POST /attendance/leaves/<id>/approve`, `/reject` | **yes** | super_admin, clinic_owner, branch_manager, hr |
| Shifts | `GET /attendance/shifts`, `POST /shifts/save` | **yes** | super_admin, clinic_owner, branch_manager, hr |
| Leave types | `GET /attendance/leave-types`, `POST /leave-types/save` | **yes** | super_admin, clinic_owner, branch_manager, hr |
| Leave balances | `GET /attendance/balances`, `POST /balances/set` | **yes** | super_admin, clinic_owner, branch_manager, hr |
| Monthly report | `GET /attendance/report` | no — non-managers forced to their own id | everyone holding `attendance` |
| Public holidays | `GET /attendance/holidays`, `POST /holidays/save`, `/holidays/<id>/delete` | **yes** | super_admin, clinic_owner, branch_manager, hr |
| Excel export | `GET /attendance/export/xlsx` | no — non-managers scoped to their own rows | everyone holding `attendance` |
| Today JSON | `GET /attendance/api/today` | no | everyone holding `attendance` — **unscoped, see Known limits** |

`finance`, `support_admin` and `auditor` are bounced from every attendance
screen by the module gate.

### Effective access — Payroll (`/payroll/`)

Two role tuples govern this module:

- `_PAYROLL_ROLES` = super_admin, clinic_owner, branch_manager, **finance** — may create, edit, approve, pay, bulk-generate and set grades.
- `_PAYROLL_VIEW_ROLES` = the four above **plus support_admin** — may read another employee's pay.

`hr` is excluded from both **deliberately**: the comment in the source says HR
gets attendance and staff documents, not salary data. An HR officer still reads
their own payslip through the self-service routes.

| Screen / action | Route | Gate | Who can actually use it |
|---|---|---|---|
| Dashboard | `GET /payroll/` | `_PAYROLL_VIEW_ROLES` | **super_admin, clinic_owner, finance** |
| Salaries list | `GET /payroll/salaries` | login + `@self_service`, query scoped | **everyone signed in** — payroll roles see all rows, everybody else sees only their own |
| Excel export | `GET /payroll/salaries/export/xlsx` | login + `@self_service`, query scoped | same as the list |
| New salary | `GET/POST /payroll/salaries/new` | `_PAYROLL_ROLES` | super_admin, clinic_owner, finance |
| Salary detail | `GET /payroll/salaries/<id>` | login + `@self_service` + `_may_see_salary` | payroll/view roles for anyone; everyone else only their own |
| Edit salary | `GET/POST /payroll/salaries/<id>/edit` | `_PAYROLL_ROLES` | super_admin, clinic_owner, finance |
| Approve | `POST /payroll/salaries/<id>/approve` | `_PAYROLL_ROLES` | super_admin, clinic_owner, finance |
| Mark paid | `POST /payroll/salaries/<id>/pay` | `_PAYROLL_ROLES` | super_admin, clinic_owner, finance |
| Bulk generate | `POST /payroll/bulk-generate` | `_PAYROLL_ROLES` | super_admin, clinic_owner, finance |
| Salary grades | `GET/POST /payroll/grades` | `_PAYROLL_ROLES` | super_admin, clinic_owner, finance |
| Payslip PDF | `GET /payroll/salaries/<id>/payslip` | login + `@self_service` + `_may_see_salary` | payroll/view roles for anyone; everyone else only their own |
| Attendance summary JSON | `GET /payroll/api/attendance/<uid>/<y>/<m>` | login + `@self_service` + `_may_see_salary` | payroll/view roles for anyone; everyone else only their own uid, otherwise `403 {"error":"forbidden"}` |
| Grade JSON | `GET /payroll/api/grade/<role>` | `_PAYROLL_VIEW_ROLES` | super_admin, clinic_owner, finance |

**`branch_manager` and `support_admin` are named on the payroll role tuples and
can reach none of the admin screens** — neither holds the `payroll` grant.
**`hr` holds the `payroll` grant and is excluded by every role list**, so the
grant buys it nothing beyond its own payslip.

> Source: `platform/blueprints/payroll/routes.py:14-26` (both tuples and the
> comment excluding `hr`), `:140-143` (`_may_see_salary`), `:282-306`,
> `:325-340`, `:444-464`, `:670-689`, `:703-713`,
> `platform/blueprints/attendance/routes.py:319-320` (`_allowed_manager`),
> `platform/blueprints/hr/routes.py:49` (`STAFF_VIEW_ROLES`)

### Who may put somebody on which role

Every write to `users.role` or `users.is_active` — from New Staff and from Edit
Staff — passes through `guard_role_change`, which refuses four things:

1. a role name that does not exist: *"There is no role called 'x'."*
2. granting above your own rank, or granting `super_admin` when you are not one: *"Your role (hr) cannot grant branch_manager."*
3. changing **your own** role at any rank: *"You cannot change your own role. Ask another administrator."*, and deactivating yourself: *"You cannot deactivate your own account."*
4. demoting or deactivating the **last active super admin**: *"This is the last active super admin. Promote somebody else first, or nobody will be able to get back in."*

Ranks: super_admin 100, clinic_owner 90, support_admin 80, branch_manager 70,
**hr 60**, finance 60, auditor 50, everyone clinical or front-desk 10. Only
`super_admin`, `clinic_owner`, `support_admin`, `branch_manager` and `hr` may
grant a role at all. So an HR officer can create a doctor, a nurse, a
receptionist, another HR officer, a finance user or an auditor — and cannot
create a branch manager, a support admin or an owner.

The refusal arrives as a red flash reading *"Error creating user: …"* or
*"Error updating user: …"* with the guard's message appended, and the form is
re-rendered.

> Source: `platform/blueprints/auth/routes.py:294-311` (`ROLE_RANK`), `:322-338`
> (`may_grant_role`), `:341-403` (`guard_role_change`),
> `platform/blueprints/hr/routes.py:501-509`, `:626-634`, `:840-842`

---

## 3. Things that apply to every screen

- **Currency** is `EGP` / `جنيه`, hard-coded in every payroll and HR template.
  There is no currency setting in these modules.
- **Bilingual labels** come from the `t(en, ar)` helper and switch on the
  signed-in user's language; the page flips to RTL in Arabic. Where a template
  hard-codes English, this chapter says so — those strings stay English in
  Arabic mode. Attendance and Payroll hard-code noticeably more than HR does.
- **CSRF.** Every non-GET request is rejected unless it carries `_csrf_token` as
  a form field or `X-CSRF-Token` as a header. **The HR and Attendance templates
  contain no CSRF field at all** — the token is added by `app.min.js`, which
  hooks every form's submit event and appends a hidden input. The five Payroll
  forms carry the field in the HTML as well. With JavaScript disabled or the
  bundle failing to load, every HR and Attendance write returns the 403 page
  reading *"You don't have permission to enter this area / غير مصرح لك بالدخول"* —
  the underlying message *"Invalid or missing security token. Please go back and
  try again."* is never shown, because the error page prints its own text for
  code 403.
- **Schema is created lazily, per module.** Every `/hr/` request runs
  `_ensure_hr_tables()`, which adds eight columns to `users`
  (`hire_date`, `contract_type`, `national_id`, `emergency_contact`,
  `emergency_phone`, `job_title`, `gender`, `dob`) and creates
  `performance_reviews`, `staff_warnings`, `staff_certifications`,
  `staff_notes`, `overtime_log`. Every `/payroll/` request runs
  `_ensure_tables()`, which calls the HR one first and then creates
  `salary_grades` and `salaries`. Attendance creates nothing — its tables
  (`shifts`, `staff_shifts`, `attendance_records`, `leave_types`,
  `leave_balances`, `leave_requests`, `public_holidays`) are part of the base
  schema. Consequence: **on a clinic where `/payroll/` has never been opened,
  the HR dashboard's "Payroll This Month" card is silently absent** — the query
  fails with *no such table: salaries*, is logged, and the card is not rendered.
- **Audit.** Only three actions in these three modules write an audit row:
  staff create (`action=create`), staff update (`action=update`) and password
  reset (`action=reset_password`), all under module `hr`. Nothing in
  Attendance or Payroll is audited — not approving leave, not editing an
  attendance record, not approving or paying a salary.
- **The Egyptian week.** `days_of_week` is stored **Sun=0 … Sat=6**, the schema
  default is `'0,1,2,3,4'` (Sunday–Thursday), and the four seeded shifts follow
  it. Every day count that matters — leave days, payroll's working days —
  reads the employee's own shift through `working_weekdays()` and falls back to
  Sunday–Thursday when nothing is configured. Public holidays are excluded from
  those counts.
- **Two time formats live in `attendance_records`.** The app writes `HH:MM` at
  check-in; imported and seeded rows carry a full timestamp
  (`2026-08-12 09:27:00`). The `hhmm()` helper accepts either and returns
  `"HH:MM"` or `""`, and every calculation goes through it.
- **Lateness** is measured against the employee's own shift start plus a grace
  period, default **15 minutes**, set by the `ATTENDANCE_GRACE_MINUTES`
  environment variable.
- **A nightly job closes forgotten check-outs.** At **00:20** server time,
  `close_forgotten_checkouts()` runs for every clinic over *yesterday*: any row
  with a check-in and no check-out is closed at that employee's shift end, hours
  are computed, `recorded_by` is set to `system`, and the note gets
  ` [auto-closed at shift end HH:MM; no check-out was recorded]` appended.
- **Money typed into a box** goes through `money.form_amount()`, which accepts
  thousands separators, Arabic digits and a leading `EGP` / `ج.م` and returns an
  error string rather than guessing. HR's overtime form shows that error;
  Attendance's leave-type and balance forms discard it (see Known limits).

> Source: `platform/app.py:349-357` (CSRF check), `:406-408` (`t()`),
> `:812-827` (the 00:20 auto-close job),
> `platform/models/security.py:260-283` (token sources),
> `platform/templates/error.html:356-392` (403 wording),
> `platform/static/js/platform.js:129-146`, `:487` (`initCsrf`),
> `platform/blueprints/hr/routes.py:146-239`,
> `platform/blueprints/payroll/routes.py:50-118`,
> `platform/models/database.py:1982-2088` (attendance schema), `:2672-2699`
> (seeded shifts and leave types),
> `platform/blueprints/attendance/routes.py:19-55` (`hhmm`), `:136`
> (`LATE_GRACE_MINUTES`), `:172-227` (`close_forgotten_checkouts`), `:247-302`,
> `platform/models/money.py:55-83`

### What is seeded on a fresh clinic

| Table | Seeded rows |
|---|---|
| `shifts` | **Morning Shift** 08:00–16:00, 60 min break, Sun–Thu · **Evening Shift** 14:00–22:00, 60 min, Sun–Thu · **Night Shift** 22:00–06:00, 60 min, all seven days · **Weekend Morning** 09:00–15:00, 30 min, Fri+Sat |
| `leave_types` | Annual Leave / إجازة سنوية 21d paid · Sick Leave / إجازة مرضية 14d paid · Emergency Leave / إجازة طارئة 3d paid · Maternity Leave / إجازة أمومة 90d paid · Unpaid Leave / إجازة بدون راتب 30d unpaid · Study Leave / إجازة دراسية 5d paid |
| `public_holidays` | **nothing** — the Holidays screen ships a one-click list of eight Egyptian dates instead |
| `salary_grades` | **nothing** — every role reads 0 basic, 0 allowances, 0 overtime rate until the Grades screen is saved |
| `leave_balances` | **nothing** — a balance row is created the first time an employee requests that leave type, or when a manager sets one |

> Source: `platform/models/database.py:2672-2699`,
> `platform/blueprints/payroll/routes.py:63-84`,
> `platform/templates/attendance/holidays.html:82-91`

---

# Part A — HR & Staff / الموارد البشرية (`/hr/`)

---

## A1. Screen: HR Dashboard

**Purpose.** The people overview: up to eight counters, three alert strips, headcount
and contract charts, recent hires, birthdays, anniversaries, expiring
certifications and the last five disciplinary actions.

**How to reach it.** *HR Dashboard / لوحة الموارد البشرية* in the topbar of the
Staff list, Certifications, Roster, Overtime or HR Attendance screen; or
`GET /hr/` which redirects here. Nothing in the sidebar or launcher points at
it.

**Who can open it.** super_admin, clinic_owner, hr (§ 2).

### Topbar buttons

| Button | Effect |
|---|---|
| `+ New Staff` / `+ موظف جديد` | Opens the blank staff form (A3) |
| `Attendance` / `الحضور` | Opens HR Attendance search (A21) |
| `Weekly Roster` / `جدول المناوبات الأسبوعي` | Opens the roster (A18) |
| `Overtime` / `العمل الإضافي` | Opens the overtime log (A19) |
| `Certifications` | Opens the certifications list (A15). **English only** |
| `Staff List` | Opens the staff list (A2). **English only** |

### The counter cards

| Card | What it counts |
|---|---|
| **Active Staff / الموظفون النشطون** | `users` with `is_active=1`; the sub-line is the count of `is_active=0` |
| **Present Today / الحاضرون اليوم** | `attendance_records` for today with `status='Present'`; sub-line is the same for `status='Late'` |
| **On Leave / في إجازة** | Approved leave requests spanning today |
| **Leave Requests / طلبات الإجازة** | `leave_requests` with `status='Pending'`, all time |
| **Reviews Pending / تقييمات معلقة** | `performance_reviews` with `status='Draft'` |
| **No Shift Assigned / بدون مناوبة** | Active users with no `staff_shifts` row whose `effective_to` is NULL or ≥ today |
| **Payroll This Month / رواتب هذا الشهر** | `SUM(net)` over `salaries` for the current year and month, printed `EGP 1,234`; sub-line `paid/total`. **The card is not rendered at all if the query fails**, which is what happens until `/payroll/` has been opened once on this database |
| **Overtime Pending / عمل إضافي معلق** | `overtime_log` with `status='Pending'`. Rendered only when above zero |

"Today" is the server's local date (`date.today()`), not UTC.

### Alert strips

Rendered only when the count is above zero; each is a link:

- ⚠ *"N leave request(s) awaiting approval — click to review"* → `/attendance/leaves?status=Pending`
- 📅 *"N staff member(s) have no shift assigned"* → the **Staff list**, which has no shift column and no unassigned filter. The roster (A18) is the screen that actually lists them.
- ⏱ *"N overtime entr(y/ies) awaiting approval — click to review"* → `/hr/overtime?status=Pending`

### Headcount by Role / عدد الموظفين حسب الدور

A horizontal bar per role over active users, longest first, bar width relative
to the largest role, coloured from a fixed 13-role palette. A role not in the
palette — including `hr` — draws grey `#6b7280`.

### Contract Types / أنواع العقود

The same bar treatment over `COALESCE(contract_type,'Full-time')`. Below it a
**Quick Links / روابط سريعة** column: Attendance Dashboard, Payroll Dashboard,
Manage Shifts, Performance Reviews.

### Recent Hires (Last 90 Days) / التعيينات الحديثة

Up to six active users whose `hire_date` is within 90 days, newest first.
Avatar initials, name linking to the profile, role and job title, and a green
`Joined <date>` pill. The whole panel is hidden when empty.

### Birthdays This Month 🎂 · Anniversaries This Month 🎉 · Expiring Certifications ⚠

- **Birthdays** — active users whose `dob` month matches this month, ordered by
  day; pill reads `Day 14` / `يوم 14`. Empty: *"No birthdays this month. / لا أعياد ميلاد هذا الشهر."*
- **Anniversaries** — active users whose `hire_date` month matches this month
  and whose hire date is in the past; pill is the number of completed years
  (`this year − hire year`). Empty: *"No anniversaries this month."*
- **Expiring Certifications** — `staff_certifications` with `status='Active'`
  expiring within 30 days, soonest first, pill `Nd left` / `N ي متبقٍ`, red at
  7 days or fewer. `All → / الكل ←` opens the certifications list. Empty:
  *"No certs expiring soon. / لا شهادات تنتهي قريباً."*

### Recent Disciplinary Actions / الإجراءات التأديبية الأخيرة

The five newest `staff_warnings` by `created_at`: type chip (Verbal / شفهي,
Written / كتابي, Final Warning / إنذار نهائي, Suspension / إيقاف), employee name
linking to the profile, the reason, and the issue date. Hidden when empty.

Six of the panels on this page sit inside `try/except` blocks that log the
failure and render empty. A panel that is empty because its query failed looks
exactly like a panel that is empty because there is no data.

> Source: `platform/blueprints/hr/routes.py:250-454`;
> `platform/templates/hr/dashboard.html:1-324`

---

## A2. Screen: Staff Management / إدارة الموظفين

**Route.** `GET /hr/staff`
**Purpose.** Find an employee, filter the roster of people, open a profile or
the edit form.
**How to reach it.** Sidebar → TEAM → HR & Staff; launcher card *Admin & HR*;
`Staff List` on the HR dashboard; `← Back to Staff List` from the staff form.
**Who can open it.** super_admin, clinic_owner, hr.

### Topbar buttons

| Button | Effect |
|---|---|
| `HR Dashboard` / `لوحة الموارد البشرية` | Opens A1 |
| `+ New Staff` / `+ موظف جديد` | Opens the blank staff form |
| `View Roles` / `عرض الأدوار` | Opens the roles list (A8) |

### Filter bar (GET, applied server-side)

| Control | Parameter | Values | Behaviour |
|---|---|---|---|
| Role select | `role` | `All Roles / جميع الأدوار` + the **13 hardcoded role keys** | Exact match on `users.role`. Submits on change |
| Contract select | `contract` | `All Contracts / جميع العقود` + Full-time / دوام كامل, Part-time / دوام جزئي, Contract / عقد, Probation / تحت التجربة, Intern / متدرب | Exact match on `users.contract_type`. Submits on change |
| Status select | `status` | `Active / نشط` (**the default**), `Inactive / غير نشط`, `All / الكل` | `active` → `is_active=1`; `inactive` → `is_active=0`; anything else → no filter. Submits on change |
| Search box | `q` | free text | Case-insensitive substring (`ILIKE`) across `full_name`, `username`, `email`, `job_title` |
| `Search / بحث` | — | — | Submits the form |
| `x Clear / مسح` | — | — | Returns to the unfiltered list. Shown only when a filter is active |

The role dropdown lists the same 13 keys as the staff form, so **an HR officer
cannot be filtered for** — `hr` is not an option, and neither is any role
created on the Roles screen. Above the table: *"N staff member(s) found /
موظف موجود"*.

### Columns

| Column | Content |
|---|---|
| Staff Member / الموظف | Coloured initials avatar, `full_name` (or `—`), username underneath |
| Job Title / المسمى الوظيفي | `job_title` or `—` |
| Role / الدور | Coloured pill, key title-cased (`branch_manager` → `Branch Manager`) |
| Contract / العقد | Tinted pill, bilingual contract label, defaults to Full-time when NULL |
| Branch / الفرع | `branches.name` or `—` |
| Contact / التواصل | Email and phone stacked, `—` when both empty |
| Status / الحالة | `Active / نشط` green, `Inactive / غير نشط` red |
| Hired / تاريخ التعيين | `hire_date` or `—` |
| Actions / إجراءات | `View / عرض` → profile, `Edit / تعديل` → form |

Rows are ordered by `full_name`. There is no pagination — every matching row is
rendered. Empty state: 👥 *"No staff found / لا يوجد موظفون"* with a link to add
one.

> Source: `platform/blueprints/hr/routes.py:459-492`;
> `platform/templates/hr/staff_list.html:1-155`

---

## A3. Screen: New Staff Member / موظف جديد

**Route.** `GET/POST /hr/staff/new`
**Purpose.** Create a login and a full employee record in one form.
**How to reach it.** `+ New Staff` on the HR dashboard or the staff list.
**Who can use it.** super_admin, clinic_owner, hr.

The form is five cards. `*` marks a field the browser requires.

### Account Credentials / بيانات الحساب

| Field | Name | Required | Notes |
|---|---|---|---|
| Username / اسم المستخدم * | `username` | yes | Placeholder `e.g. dr.ahmed` / `مثال: dr.ahmed`. Must be unique — a clash surfaces as *"Error creating user: UNIQUE constraint failed: users.username"* |
| Password / كلمة المرور * | `password` | yes | Placeholder **`Min 6 characters` / `6 أحرف على الأقل` — wrong**; the server requires 12 characters with an uppercase, a lowercase, a digit and a special character |
| Confirm Password / تأكيد كلمة المرور * | `confirm_password` | yes | Must match |

### Personal Information / البيانات الشخصية

| Field | Name | Notes |
|---|---|---|
| Full Name (English) / الاسم الكامل (إنجليزي) | `full_name` | Placeholder `Dr. Ahmed Hassan` |
| Full Name (Arabic) / الاسم الكامل (عربي) | `full_name_ar` | RTL input, placeholder `د. أحمد حسن` |
| Email Address / البريد الإلكتروني | `email` | `type=email` |
| Phone Number / رقم الهاتف | `phone` | Placeholder `+20 10 xxxx xxxx` |
| Gender / النوع | `gender` | `— Not specified / غير محدد —`, Male / ذكر, Female / أنثى, Not specified / غير محدد |
| Date of Birth / تاريخ الميلاد | `dob` | Date picker. Feeds the dashboard birthday panel |
| National ID / الرقم القومي | `national_id` | Free text, placeholder *"National ID number / رقم البطاقة القومية"* |

### Emergency Contact / جهة الاتصال في الطوارئ

`emergency_contact` (name) and `emergency_phone`. Both appear on the profile as
one line; neither is used anywhere else.

### Employment Details / بيانات التوظيف

| Field | Name | Notes |
|---|---|---|
| Job Title / المسمى الوظيفي | `job_title` | Free text, e.g. *Senior Veterinarian / طبيب بيطري أول* |
| Contract Type / نوع العقد | `contract_type` | Full-time (default), Part-time, Contract, Probation, Intern — bilingual labels |
| Hire Date / تاريخ التعيين | `hire_date` | Feeds "Recent Hires" and "Anniversaries" |

### Role & Access Control / الدور والصلاحيات

| Field | Name | Notes |
|---|---|---|
| Role / الدور * | `role` | Dropdown of **13 hardcoded keys**: super_admin, clinic_owner, branch_manager, doctor, nurse, reception, inventory_mgr, pharmacist, finance, groomer, boarding_staff, support_admin, auditor. **`hr` is missing**, and so is every custom role |
| Branch / الفرع | `branch_id` | `— No Branch / بدون فرع —` plus every active branch |
| Work Shift / المناوبة | `shift_id` | `— No Shift / بدون مناوبة —` plus every active shift as `Name (start – end)`. Hint: *"Assigning a shift here will set it from today. / تعيين مناوبة هنا سيبدأ سريانها من اليوم."* |
| Account Status / حالة الحساب | `is_active` | Checkbox, ticked by default: *"Active — user can log in / نشط — يمكن للمستخدم تسجيل الدخول"* |

### Buttons

| Button | Effect |
|---|---|
| `Cancel` / `إلغاء` | Back to the staff list, nothing saved |
| `Create Staff Member` / `إنشاء موظف` | Validates and inserts |

### What Create actually does, in order

1. Username or password blank → *"Username and password are required."* and the
   form is re-rendered with what you typed.
2. Password ≠ confirmation → *"Passwords do not match."*, re-rendered.
3. `guard_role_change` runs (§ 2). A refusal is reported as
   *"Error creating user: &lt;reason&gt;"*.
4. Password strength is checked. A failure is reported the same way, e.g.
   *"Error creating user: Password must be at least 12 characters."*
5. The row is inserted with a **bcrypt** hash.
6. If a shift was chosen, the new user is looked up by username and a
   `staff_shifts` row is inserted with `effective_from` = today and no end date.
7. An audit row is written: `action=create`, `module=hr`, `entity_type=user`,
   details *"Created user: &lt;username&gt;"*.
8. Green flash *"Staff member 'x' created successfully."* and a redirect to the
   staff list.

Any other database error is caught and shown as *"Error creating user: …"* with
the raw exception text.

> Source: `platform/blueprints/hr/routes.py:20-24` (`_ROLES`), `:501-566`
> (`_save_staff_fields`), `:569-576`, `:581-639`;
> `platform/templates/hr/staff_form.html:36-197`;
> `platform/models/security.py:346-367` (the real password policy)

---

## A4. Screen: Staff profile / بيانات الموظف

**Route.** `GET /hr/staff/<user_id>`
**Purpose.** The whole employee record on one page, plus eight write forms that
post back to it.
**How to reach it.** `View / عرض` on the staff list; any employee-name link on
the HR dashboard, roster, overtime log, HR attendance, certifications list,
attendance records, leave screens, salaries list or payslip.
**Who can open it.** super_admin, clinic_owner, hr. A missing id flashes
*"User not found."* and returns to the list.

### Topbar buttons

`Edit / تعديل` (A5) · `+ Review / + تقييم` (opens the **blank** review form, not
pre-filled with this employee) · `← Back / ← رجوع`.

### Left column — Profile card

Avatar initials on the role colour, English name, Arabic name in RTL when set,
role pill, then a label/value list rendered only for the fields that are filled:
Username (monospace), Status (Active / نشط green, Inactive / غير نشط red), Job
Title, Contract, Hired, Gender, Date of Birth, Email, Phone, National ID,
Emergency (name · phone), Branch, Last Login (first 16 characters of
`last_login_at`, or *"Never / لم يسجل دخول"*), Created.

#### Reset Password / إعادة تعيين كلمة المرور

A password box and a button, wrapped in a JavaScript confirm reading
`Reset password for <username>?` (**English only**). The box's placeholder says
**`New password (min 6 chars)` / `كلمة مرور جديدة (6 أحرف على الأقل)`** and it
carries `minlength="6"` — both wrong; see A6.

**The panel is rendered for everybody who can open this page, including `hr`,
which the route rejects.**

#### Work Shift / المناوبة card

Shows the assignment in force today — shift name, `start – end`, `· From
<effective_from>` and the raw `days_of_week` string (e.g. `0,1,2,3,4`) — or
*"No shift assigned. / لا توجد مناوبة معينة."*

Below it the assign form (A7): a shift select whose first option is
`— Remove Shift —` (**English only**), an `effective_from` date box, and
`Update Shift / تحديث المناوبة`.

### Right column — panels

#### Attendance This Month / حضور هذا الشهر

Four mini-counters over `attendance_records` from the **1st of the current
month** to now: Present / حاضر, Late / متأخر, Absent / غائب, Hours / الساعات
(`SUM(hours_worked)`, one decimal). Link: *"Full attendance history → / سجل
الحضور الكامل ←"* → `/attendance/records?user_id=<id>`. The whole card is hidden
if the query failed.

#### Leave Balances (This Year) / أرصدة الإجازات (هذا العام)

One row per `leave_balances` row for the current year: type name, `used /
allocated days used`, and a pill of **`allocated − used`** computed in the
template — the stored `remaining` column is ignored here, so days reserved by a
pending request are not visible. Empty: *"No leave balance allocated yet. / لم
يُخصَّص رصيد إجازات بعد."* Link: *"View leave requests → / عرض طلبات الإجازة ←"*.

#### Performance Reviews / تقييمات الأداء

Last five reviews: period, date, five-star rating, status chip (Draft / مسودة,
Submitted / مُرسل, Acknowledged / مُعتمد) and `View / عرض`. `+ Add / + إضافة`
opens the blank review form. *"All reviews → / كل التقييمات ←"* filters the
review list by this employee.

#### Salary History (Last 6 Months) / سجل الرواتب (آخر 6 أشهر)

Last six `salaries` rows: `YYYY-MM`, `Basic: / الأساسي: EGP 12,000`, net in
green, a status chip, and `View / عرض` → the payslip screen. Hidden when there
are none — which includes the case where the `salaries` table does not exist
yet.

**This panel is rendered to anyone who can open the profile**, so an HR officer
— excluded from payroll by design — reads basic and net pay here. The `View`
link then lands on *"You don't have permission to view this salary record."*

#### Disciplinary Record / السجل التأديبي

Each warning: type chip, reason, `Action: <action_taken>` when set, then
`<issued_date> · by / بواسطة <issuer>` and `Acknowledged / مُعتمد` when
acknowledged. Buttons `Ack / اعتماد` (only while unacknowledged) and `Del / حذف`
(confirm *"Delete this warning?"*, English only). Empty: *"No disciplinary
records. / لا توجد سجلات تأديبية."*

**Issue Warning / إصدار إنذار** form: type select (Verbal, Written, Final
Warning, Suspension — **English only in the dropdown**), required `reason`
textarea, `action_taken` text, `issued_date` and `expiry_date` date boxes, and
the `Issue Warning / إصدار إنذار` button. See A14.

#### Certifications & Training

Header is **English only**. Each certification: name, then
`issuer · #number · Issued <date>`, then either `Exp: <expiry_date>` (red when
expired, green otherwise) or *"No expiry / بدون انتهاء"*, a status chip
(Active / Expired / other), and an `✕` delete button (confirm *"Remove this
certification?"*).

**Add Certification / Training / إضافة شهادة / تدريب** form: `cert_name`
(required), `issued_by`, `cert_number`, `issue_date`, `expiry_date`, a status
select (Active / سارية, Pending / قيد الانتظار, Expired / منتهية) and `notes`.
See A16.

#### HR Notes / ملاحظات الموارد البشرية *(private — managers only / خاصة — للمديرين فقط)*

Last 20 notes, newest first: the text, then `<author> · <created_at first 16
characters>` and a `Delete / حذف` button (confirm *"Delete this note?"*). Empty:
*"No notes yet. / لا توجد ملاحظات بعد."* The add form is a required textarea and
`Save Note / حفظ الملاحظة`. See A17.

The *"private — managers only"* label describes the page's audience — the notes
are visible to everyone who can open the profile, and the `is_private` column is
stored `TRUE` and never read.

#### Overtime / Extra Hours

Header **English only**. Up to five of the ten most recent entries: date, hours,
reason, status pill. `View All / عرض الكل` → `/hr/overtime?user_id=<id>`.

**Log Overtime / تسجيل عمل إضافي** form: `work_date` (defaults to today,
required), `hours` (number, step 0.5, min 0.5, max 24, required), `reason` text,
and the button. See A20.

#### Recent Activity (Last 30 Events) / النشاط الأخير (آخر 30 حدثاً)

The last 30 `audit_log` rows **matched by username**: Time (first 16
characters), Action chip, Module, Details (truncated, full text in the tooltip),
IP. Empty: 📭 *"No activity recorded yet. / لا يوجد نشاط مسجل بعد."* Because the
match is on the username string, a deleted-and-recreated account inherits the
old rows.

> Source: `platform/blueprints/hr/routes.py:644-797`;
> `platform/templates/hr/staff_detail.html:1-523`

---

## A5. Screen: Edit Staff Member / تعديل بيانات الموظف

**Route.** `GET/POST /hr/staff/<user_id>/edit`
**Purpose.** Change any part of the employee record except the username and the
password.
**Who can use it.** super_admin, clinic_owner, hr.

The same template as A3, with three differences:

- **Username is read-only** and greyed. The edit path never writes it.
- **The password and confirmation boxes are not rendered.** A password can only
  be changed by the reset form (A6).
- The **Work Shift** dropdown is pre-selected from `staff_shifts` — the
  assignment in force today — and the submit button reads `Save Changes / حفظ
  التغييرات`.

### What Save actually does

1. `guard_role_change` runs against the submitted `role` and `is_active`.
2. Every field on the form is written to `users`, plus `updated_at`.
3. **Only if `shift_id` was present in the submission**, the shift is changed:
   the running `staff_shifts` row is closed and a new one opened from today. A
   present-but-empty value is a deliberate *"— No Shift —"* and unassigns;
   absence of the field leaves the assignment alone.
4. Audit row `action=update`, `module=hr`, `entity_id=<id>`, details
   *"Updated user id=N"*.
5. Green flash *"Staff member updated successfully."* and a redirect to the
   profile.

On failure the flash is *"Error updating user: &lt;reason&gt;"* — and the form is
re-rendered **from the database row, not from what you typed**, so the rejected
edit is lost from the screen.

> Source: `platform/blueprints/hr/routes.py:802-847`, `:884-913`
> (`_current_shift_id`, `_set_shift`);
> `platform/templates/hr/staff_form.html:45-58`

---

## A6. Action: Reset a password

**Route.** `POST /hr/staff/<user_id>/reset-password`
**Who can use it.** super_admin and clinic_owner only. `support_admin` is on the
role list but cannot reach the module; **`hr` sees the form on the profile and
is refused**, landing on the launcher with *"You don't have permission to access
this page."*

The single field `new_password` must satisfy the platform policy: **at least 12
characters, one uppercase, one lowercase, one digit and one special character**.
The failure flash is the exact rule that was broken, e.g. *"Password must
contain at least one digit."*, and you are returned to the profile.

On success the bcrypt hash and `updated_at` are written, an audit row
`action=reset_password`, `module=hr` is recorded, and the flash reads *"Password
reset successfully."* Any exception flashes *"Error resetting password: …"*.

The form's own hint says six characters (A4). The browser therefore accepts a
six-character password and the server rejects it after the round trip.

> Source: `platform/blueprints/hr/routes.py:852-879`;
> `platform/models/security.py:346-367`;
> `platform/templates/hr/staff_detail.html:121-129`

---

## A7. Action: Assign or remove a shift

**Route.** `POST /hr/staff/<user_id>/assign-shift`
**Who can use it.** super_admin, clinic_owner, hr.

| Field | Effect |
|---|---|
| `shift_id` | Empty (`— Remove Shift —`) unassigns; otherwise assigns that shift |
| `effective_from` | Optional; defaults to today |
| `effective_to` | **Read by the route and not present on the form**, so an assignment made here never has an end date |

The write closes whatever assignment is currently running by setting its
`effective_to`, then inserts the new one. Flash on assign: *"Shift assigned
successfully."* (green). Flash on remove: *"Shift removed from staff member."*
(blue). Either way you land back on the profile.

The same `_set_shift` helper is used by Edit Staff, so the two screens cannot
disagree.

This is the most consequential setting in the three modules: the shift decides
what counts as late, how a night shift's hours are computed, which weekdays
count as working days for leave and payroll, and what the nightly auto-close
uses as the end of the day.

> Source: `platform/blueprints/hr/routes.py:894-929`

---

## A8. Screen: Roles & Permissions / الأدوار والصلاحيات

**Route.** `GET /hr/roles`
**Purpose.** A read-only card per row in the `roles` table.
**How to reach it.** `View Roles / عرض الأدوار` in the staff-list topbar.
**Who can open it.** super_admin and clinic_owner. `branch_manager` and
`support_admin` are on the role list and cannot reach the module; **`hr` is not
on the list at all**.

Header: *"Platform Role System / نظام أدوار المنصة"*, then *"N roles defined.
Roles control what each staff member can access across the platform. Super Admin
always has full access regardless of role restrictions."*

Each card shows an emoji (from a fixed 13-key map; an unmapped role such as a
custom one gets 👤), the display name, the raw key, the Arabic display name, a
hardcoded bilingual description, a count of **active** users on that role, and
a *"View Staff → / عرض الموظفين ←"* link that filters the staff list by
`?role=<key>`.

**Nothing on this screen can be edited**, the descriptions are a hardcoded map —
a role created on the System → Roles screen appears with the generic *"Platform
role with specific access permissions."* — and the granted permissions
themselves are not shown anywhere on the page. The editable version lives at
System → Roles & Permissions (System § 4).

> Source: `platform/blueprints/hr/routes.py:934-946`;
> `platform/templates/hr/roles_list.html:1-91`

---

## A9. Screen: Performance Reviews / تقييمات الأداء

**Route.** `GET /hr/performance`
**Purpose.** Every review in the clinic, filterable.
**How to reach it.** HR dashboard → Quick Links → Performance Reviews; *"All
reviews →"* on a staff profile.
**Who can open it.** super_admin, clinic_owner, hr.

### Topbar

`+ New Review / + تقييم جديد` · `HR Dashboard / لوحة الموارد البشرية`.

### Filter bar (GET)

| Control | Parameter | Behaviour |
|---|---|---|
| Period text box | `period` | **Exact match** on `performance_reviews.period`, not a substring. Placeholder *"Period (e.g. 2025-Q2) / الفترة (مثال: 2025-Q2)"* |
| Staff select | `user_id` | Exact match. Every active user |
| Status select | `status` | Draft / مسودة, Submitted / مُرسل, Acknowledged / مُعتمد — **the route never reads this parameter; choosing a status changes nothing** |
| `Filter / تصفية` | — | Submits |
| `Reset / إعادة تعيين` | — | Clears the filters |

### Columns

| Column | Content |
|---|---|
| Staff / الموظف | `full_name`. The second line renders `job_title`, which this query never selects, so it is always blank |
| Period / الفترة | The free-text period string |
| Rating / التقييم | Five stars, filled to the rating; `—` when NULL |
| Reviewer / المقيّم | The reviewer's full name, or `—` |
| Status / الحالة | Coloured chip |
| Date / التاريخ | `reviewed_at`, else the first 10 characters of `created_at` |
| (actions) | `View / عرض`; `Edit / تعديل` unless the status is Acknowledged |

Newest first, **capped at 100 rows** with nothing on screen to say so. Empty
state: 📋 *"No performance reviews found / لا توجد تقييمات أداء"* with a link to
create the first.

> Source: `platform/blueprints/hr/routes.py:951-983`;
> `platform/templates/hr/performance_list.html:1-118`

---

## A10. Screen: New Performance Review / تقييم أداء جديد

**Route.** `GET/POST /hr/performance/new`
**Who can use it.** super_admin, clinic_owner, hr.

| Field | Name | Required | Notes |
|---|---|---|---|
| Staff Member / الموظف * | `user_id` | yes | Every active user as `Name (Role)`. **Never pre-selected**, even when opened from a profile with `+ Review` |
| Review Period / فترة التقييم * | `period` | yes | Free text, e.g. `2025-Q2` or `2025-H1` |
| Review Date / تاريخ التقييم | `reviewed_at` | no | Defaults to today when left blank |
| Status / الحالة | `status` | no | Draft / مسودة (default), Submitted / مُرسل, Acknowledged / مُعتمد |
| Overall Rating / التقييم العام | `rating` | no | Five radio stars, 1–5, with the hint *"Click a star to rate (1 = Needs Improvement, 5 = Outstanding) / اضغط على نجمة للتقييم"*. **Defaults to 3 when nothing is chosen** — a review saved without touching the stars is stored as a 3, not as "no rating" |
| Strengths / نقاط القوة | `strengths` | no | Textarea |
| Areas for Improvement / مجالات التحسين | `improvements` | no | Textarea |
| Goals for Next Period / أهداف الفترة القادمة | `goals` | no | Textarea |
| Additional Comments / ملاحظات إضافية | `comments` | no | Textarea |

The reviewer is the signed-in user and cannot be chosen. Buttons: `Cancel /
إلغاء` and `Create Review / إنشاء تقييم`.

Success flashes *"Performance review created."* and returns to the list. Any
error flashes *"Error: &lt;exception&gt;"*.

> Source: `platform/blueprints/hr/routes.py:986-1026`;
> `platform/templates/hr/performance_form.html:1-125`

---

## A11. Screen: Performance review detail

**Route.** `GET /hr/performance/<rev_id>`
**Who can open it.** The route carries only `@login_required`, then checks the
subject: an HR role sees any review; everybody else only a review **about
themselves**. A stranger gets *"You don't have permission to view this review."*
and the launcher. A missing id flashes *"Review not found."*

Left column: the rating as five large stars plus `N/5`, then a card per filled
free-text field (Strengths, Areas for Improvement, Goals, Additional Comments) —
each hidden when empty, line breaks preserved.

Right column: **Review Info / بيانات التقييم** — Staff (linking to the profile,
which most viewers cannot open), Period, Reviewer, Review Date, Status chip,
Created. Then:

- when the status is **Submitted**, an **Acknowledge / الاعتماد** card reading
  *"Has the employee reviewed and acknowledged this evaluation? / هل اطلع الموظف
  على هذا التقييم واعتمده؟"* with a `Mark as Acknowledged / تعليم كمعتمد` button
  behind a confirm dialog (A13);
- when the status is anything other than Acknowledged, a card with `Edit Review
  / تعديل التقييم` and `New Review / تقييم جديد`.

The `Edit / تعديل` button also sits in the topbar for a non-acknowledged review.
Both are rendered for every viewer, including the employee, who is refused by
the edit route.

> Source: `platform/blueprints/hr/routes.py:1029-1049`, `:56-71` (`_may_act_on`);
> `platform/templates/hr/performance_detail.html:1-159`

---

## A12. Screen: Edit Performance Review / تعديل تقييم الأداء

**Route.** `GET/POST /hr/performance/<rev_id>/edit`
**Who can use it.** super_admin, clinic_owner, hr.

The same form as A10 with the button `Save Changes / حفظ التغييرات`.

The update writes `period`, `rating`, `strengths`, `improvements`, `goals`,
`comments`, `status`, `reviewed_at` and `updated_at`. It does **not** write
`user_id` or `reviewer_id`: the Staff Member dropdown is rendered and editable,
and choosing a different person changes nothing.

Success flashes *"Review updated."* and returns to the detail page; failure
flashes *"Error: …"*. A missing id flashes *"Review not found."*

> Source: `platform/blueprints/hr/routes.py:1052-1095`

---

## A13. Action: Acknowledge a review

**Route.** `POST /hr/performance/<rev_id>/acknowledge`
**Who can use it.** The subject of the review, or any HR role. The subject id is
read from the stored row, never from the URL. Anyone else gets *"You don't have
permission to acknowledge this review."* and the launcher.

Sets `status='Acknowledged'` and `updated_at`, flashes *"Review acknowledged."*,
returns to the detail page. There is no undo — an acknowledged review can no
longer be edited from the interface.

> Source: `platform/blueprints/hr/routes.py:1098-1117`

---

## A14. Actions: Warnings / disciplinary

All three post from the staff profile and return to it.

### Issue a warning — `POST /hr/staff/<user_id>/warnings/add`

super_admin, clinic_owner, hr. Fields: `warning_type` (Verbal / Written / Final
Warning / Suspension, default Verbal), `reason` (required by the browser),
`action_taken`, `issued_date` (defaults to today), `expiry_date` (optional).
`issued_by` is the signed-in user. Flash: *"Warning recorded."* in **amber**; on
error, *"Error: …"*.

`expiry_date` is stored and read by nothing — a warning does not expire.

### Acknowledge — `POST /hr/staff/<user_id>/warnings/<warn_id>/acknowledge`

The employee the warning belongs to, or an HR role; the subject comes from the
stored row, not the URL. Sets `acknowledged=TRUE`. Flash: *"Warning acknowledged
by employee."* Anyone else: *"You don't have permission to acknowledge this
warning."*

### Delete — `POST /hr/staff/<user_id>/warnings/<warn_id>/delete`

**super_admin and clinic_owner only** — the `Del / حذف` button is rendered for
every viewer including `hr`, which is refused. The delete is hard and matched on
both the warning id and the user id. Flash: *"Warning deleted."* No audit row is
written.

> Source: `platform/blueprints/hr/routes.py:1122-1179`;
> `platform/templates/hr/staff_detail.html:289-334`

---

## A15. Screen: Certifications & Training / الشهادات والتدريب

**Route.** `GET /hr/certifications`
**Purpose.** Every certification held by every employee, in one table.
**How to reach it.** `Certifications` in the HR dashboard topbar; *"All →"* on
the dashboard's expiry panel; *"All staff →"* on a profile.
**Who can open it.** super_admin, clinic_owner, hr.

### Summary row

Four counters computed in the template over the whole list: **Active / سارية**
(`status='Active'`), **Expiring Soon / تنتهي قريباً** (active with
`0 ≤ days_left ≤ 30`), **Expired / منتهية** (`status='Expired'` — the stored
status only, not the date), **Total Records / إجمالي السجلات**.

### Columns

Staff Member / الموظف (name linking to the profile, role underneath) ·
Certification / Training / الشهادة / التدريب · Cert Number / رقم الشهادة ·
Issuing Body / الجهة المانحة · Issue Date / تاريخ الإصدار · Expiry Date / تاريخ
الانتهاء (or *"No expiry / بدون انتهاء"*) · Status / الحالة.

The status cell is computed, not stored: **Expired / منتهية** when the stored
status says so *or* the expiry is in the past; **Expiring in Nd / تنتهي خلال N ي**
at 30 days or fewer; **Pending / قيد الانتظار**; otherwise **Active / سارية · Nd**.

Ordered by expiry date, nulls last. There is no filter, no search and no
pagination on this screen, and nothing can be added or deleted here — both
happen on the staff profile (A16). Empty state: 🏅 *"No certifications recorded
/ لا توجد شهادات مسجلة"*.

> Source: `platform/blueprints/hr/routes.py:74-87` (`_days_left`), `:1184-1197`;
> `platform/templates/hr/certifications_list.html:1-127`

---

## A16. Actions: Certifications on a profile

### Add — `POST /hr/staff/<user_id>/certifications/add`

super_admin, clinic_owner, hr. Fields: `cert_name` (required), `issued_by`,
`cert_number`, `issue_date`, `expiry_date`, `status` (Active default, Pending,
Expired), `notes`. Flash *"Certification added."*; errors *"Error: …"*.

`notes` is stored and rendered nowhere — neither the profile card nor the
certifications table shows it.

### Delete — `POST /hr/staff/<user_id>/certifications/<cert_id>/delete`

super_admin, clinic_owner, hr (not support_admin). Hard delete matched on both
ids. Flash *"Certification removed."*

> Source: `platform/blueprints/hr/routes.py:1200-1236`

---

## A17. Actions: HR notes

### Add — `POST /hr/staff/<user_id>/notes/add`

super_admin, clinic_owner, hr. A single `note` textarea; an empty or
whitespace-only note is rejected server-side with *"Note cannot be empty."*
`author_id` is the signed-in user; `is_private` defaults to TRUE and is never
read. Flash *"Note saved."*

### Delete — `POST /hr/staff/<user_id>/notes/<note_id>/delete`

**super_admin and clinic_owner only** — the `Delete / حذف` link is shown to
every viewer of the profile, and `hr` is refused. Flash *"Note deleted."*

> Source: `platform/blueprints/hr/routes.py:1241-1272`

---

## A18. Screen: Weekly Roster / جدول المناوبات الأسبوعي

**Route.** `GET /hr/roster?week=YYYY-MM-DD`
**Purpose.** A shift × day grid for one week showing who is on which shift and
what actually happened on each day.
**How to reach it.** `Weekly Roster` in the HR dashboard or overtime topbar;
*"Weekly roster →"* on the Attendance → Shifts screen.
**Who can open it.** super_admin, clinic_owner, hr.

`week` may be any date inside the target week; an unparseable value falls back
to today. The grid always starts on the **Monday** of that week and runs seven
days, with headers `Mon…Sun` / `إثنين…أحد`.

### Navigation

`← Prev Week / ← الأسبوع السابق` · the range label *"Week of 04 Aug 2026 – 10
Aug 2026"* · `Next Week → / الأسبوع التالي ←` · `Today / اليوم`.

### The grid

One row per **active** shift, ordered by start time. The left cell shows the
shift name in its colour, `start - end`, and how many people are assigned. Then
one cell per day:

- A day the shift does not work renders a grey cell reading `Off / إجازة`.
- Otherwise every assigned employee appears as a chip carrying their **first
  name only**, linking to their profile, coloured by what the day holds: blue
  *(Leave / إجازة)* for an approved leave covering that date, green for a
  `Present` attendance row, amber *(Late / متأخر)* for `Late`, red for any other
  status, grey when no record exists.

Assignments are those **overlapping** the week, so somebody rostered mid-week
appears in their own week. Today's column is highlighted.

**Which days count as "Off" is computed from the wrong numbering.** The template
compares Python's `isoweekday()` (Mon=1 … **Sun=7**) against `days_of_week`,
which is stored Sun=0 … Sat=6. The two agree for Monday–Saturday and disagree
about Sunday, so **a shift that works Sunday is always drawn as Off on Sunday**
— including the three seeded weekday shifts. The template's own fallback when
`days_of_week` is empty is `1,2,3,4,5`, i.e. Monday–Friday, which is not the
default the rest of the platform uses either.

### Legend and unassigned staff

A legend for the five chip colours (Present / حاضر, Late / متأخر, Absent / غائب,
On Leave / في إجازة, No record yet / لا يوجد سجل بعد), then **Staff without shift
assignment / موظفون بدون مناوبة (N)** — every active user with no overlapping
assignment, each a chip linking to their profile. This is the only screen that
lists them; the HR dashboard counts them and links to the staff list instead.

Empty state when no shifts exist: 📅 *"No shifts configured / لا توجد مناوبات
معرّفة"* with a link to Attendance → Shifts.

> Source: `platform/blueprints/hr/routes.py:1279-1369`;
> `platform/templates/hr/roster.html:47-164` (day numbering at `:91-92`)

---

## A19. Screen: Overtime Log / سجل العمل الإضافي

**Route.** `GET /hr/overtime`
**Purpose.** Every overtime entry in the clinic, with approve and reject.
**How to reach it.** `Overtime / العمل الإضافي` in the HR dashboard topbar; the
dashboard's pending-overtime alert; *"View All / عرض الكل"* on a profile.
**Who can open it.** super_admin, clinic_owner, hr.

### KPI row

| Card | Content |
|---|---|
| **Total Records / إجمالي السجلات** | Count of **all** rows matching the filters, computed in SQL |
| **Approved Hours / الساعات المعتمدة** | `SUM(hours)` over the approved rows matching the filters, in SQL |
| **Pending Approval / بانتظار الاعتماد** | Counted **in the template over the rows on screen**, so it is capped at 200 like the table |

### Filters (GET)

`user_id` (All Staff / جميع الموظفين + every active user) · `status` (All
Statuses / جميع الحالات, Pending / قيد الانتظار, Approved / معتمد, Rejected /
مرفوض) · `date_from` · `date_to` (both compared against `work_date`) ·
`Filter / تصفية` · `Clear / مسح`.

### Columns

Staff Member / الموظف (name → profile, role underneath) · Date / التاريخ ·
Hours / الساعات (`2.5h`) · Reason / السبب · Status / الحالة chip · Approved By /
اعتمده · Actions / إجراءات.

The actions cell shows `Approve / اعتماد` and `Reject / رفض` (the latter behind
a confirm *"Reject this overtime entry? / رفض سجل العمل الإضافي هذا؟"*) **only
while the row is Pending**; otherwise `—`.

The table is capped at **200 rows**, newest work date first. When more exist, a
line below reads *"Showing the most recent N of M records. The totals above
cover all of them. / يتم عرض أحدث N من M سجل."* Empty state: ⏱ *"No overtime
records found / لا توجد سجلات عمل إضافي"* with *"Add overtime entries from each
staff member's profile page."*

> Source: `platform/blueprints/hr/routes.py:1376-1444`;
> `platform/templates/hr/overtime.html:1-151`

---

## A20. Actions: Overtime

### Log overtime — `POST /hr/staff/<user_id>/overtime/add`

super_admin, clinic_owner, hr. Posted from the profile.

1. `hours` is parsed by `money.form_amount`; a value that is not a number
   flashes *"“abc” is not a valid overtime hours."* and returns to the profile.
2. Zero or negative hours flash *"Overtime hours must be greater than zero. To
   remove an entry, reject or delete it rather than logging a negative."*
3. A duplicate guard looks for a **Pending** row with the same user, work date
   and hours; a match flashes *"That overtime is already logged and awaiting
   approval."* in amber and writes nothing. A double-clicked submit therefore
   cannot produce two approvable entries.
4. Otherwise the row is inserted with status `Pending` and the flash reads
   *"2.5h overtime recorded."*

`work_date` defaults to today when blank.

### Approve — `POST /hr/overtime/<ot_id>/approve`

super_admin, clinic_owner, hr. Sets `status='Approved'` and `approved_by` to the
signed-in user, unconditionally — there is no check that the row is still
Pending, so a rejected entry can be approved afterwards. Flash *"Overtime
approved."*, redirect to the overtime log (**not** back to the filtered view you
came from).

### Reject — `POST /hr/overtime/<ot_id>/reject`

Sets `status='Rejected'` and leaves `approved_by` untouched, so the "Approved
By" column stays blank on a rejection. Flash *"Overtime rejected."*

**Approved overtime hours are not used by payroll.** Payroll computes overtime
itself from `attendance_records.hours_worked` beyond the shift's standard hours
(C1, C9). This log is a separate record that nothing else reads.

> Source: `platform/blueprints/hr/routes.py:1447-1522`;
> `platform/blueprints/payroll/routes.py:197-204`

---

## A21. Screen: Attendance Records — HR view / سجلات الحضور

**Route.** `GET /hr/attendance`
**Purpose.** The manager's attendance search: a live board for today, summary
statistics for the filtered range, a paged table, and a modal for entering a
record by hand.
**How to reach it.** `Attendance / الحضور` in the HR dashboard topbar.
**Who can open it.** super_admin, clinic_owner, hr.

This is a different screen from Attendance → Records (B3), which every employee
can open and which scopes non-managers to their own rows.

### Topbar

`HR Dashboard` · `Staff List` · `+ Log Attendance / + تسجيل حضور` (opens the
modal, A22).

### Today / اليوم — live board

A pulsing dot, today's date, the number of records, and — when there are any —
*"N not recorded / بدون تسجيل"* in red. Then a card per record: employee name
(linked, coloured by role), role, `In: / دخول: HH:MM → Out: / خروج: HH:MM` when
set, a status pill (Present / حاضر, Late / متأخر, On Leave / في إجازة, Absent /
غائب) and the hours worked. After those, one faded red card per **active user
with no record today**, reading *"No record / لا يوجد سجل"*.

### Summary statistics (over the filtered range, not today)

Total Records / إجمالي السجلات · Present / حاضر · Late / متأخر · Absent / غائب ·
On Leave / في إجازة · Avg Hours / متوسط الساعات (average of `hours_worked` over
rows where it is above zero).

### Filters (GET)

| Control | Parameter | Behaviour |
|---|---|---|
| Search box | `q` | Substring on the **record's own** `full_name` or `username` columns — the copies written at check-in, not the current `users` row |
| Status | `status` | All / Present / Late / Absent / On Leave, bilingual |
| Branch | `branch_id` | Matches `users.branch_id`, so it follows the employee's current branch, not the branch they worked in |
| Staff | `user_id` | Every active user |
| From / To | `date_from`, `date_to` | Default **the last 7 days** (today − 6 → today) |
| `Search / بحث` · `Reset / إعادة تعيين` | — | — |
| Quick range buttons | — | Today / اليوم, Yesterday / أمس, Last 7 Days / آخر 7 أيام, Last 2 Weeks / آخر أسبوعين, This Month / هذا الشهر, Last Month / الشهر الماضي — they set the two date boxes in JavaScript and submit, computing the dates from the **browser's** clock in UTC |

### Columns

Staff Member / الموظف (link + role chip) · Date / التاريخ · Check In / الدخول
(amber when the hour is 9 or later, green otherwise) · Check Out / الخروج ·
Hours / الساعات · Break / الاستراحة (`60 min` / `60 د`) · Status / الحالة pill ·
Branch / الفرع · Notes / ملاحظات (truncated, full text in the tooltip) ·
Recorded By / سجّله (the username, or `system` for an auto-closed row) · a `✕`
delete button.

Ordered by work date descending then name, **50 rows per page**, with
`← Prev / ← السابق`, `page / total`, `Next → / التالي ←` above the table and a
count reading *"Showing N of M records (from → to)"*.

`✕` posts to `POST /hr/attendance/<id>/delete` behind a confirm *"Delete this
attendance record? / حذف سجل الحضور هذا؟"*, restricted to super_admin,
clinic_owner, hr; flash *"Record deleted."* The delete is hard and unaudited.

> Source: `platform/blueprints/hr/routes.py:1527-1644`, `:1735-1743`;
> `platform/templates/hr/hr_attendance.html:1-402`

---

## A22. Action: Log Attendance Record / تسجيل سجل حضور

**Route.** `POST /hr/attendance/add`
**Who can use it.** super_admin, clinic_owner, hr.

The modal fields:

| Field | Name | Required | Notes |
|---|---|---|---|
| Staff Member / الموظف * | `user_id` | yes | Every active user. Missing → *"Select a staff member."* |
| Date / التاريخ * | `work_date` | yes | Defaults to today |
| Status / الحالة * | `status` | yes | Present / حاضر, Late / متأخر, Absent / غائب, On Leave / في إجازة |
| Check In / الدخول | `check_in` | no | `type=time` |
| Check Out / الخروج | `check_out` | no | `type=time` |
| Notes / ملاحظات | `notes` | no | Free text |

Buttons: `Cancel / إلغاء` and `Save Record / حفظ السجل`.

### What Save does

1. Looks for an existing record for that employee **on that date**.
2. If one exists, **times you leave blank are inherited from it** — so changing
   only the status does not erase the clock.
3. If both times are then present, hours are computed by the attendance
   module's own `_calc_hours`, deducting the employee's shift break and wrapping
   correctly for a night shift. Otherwise `hours_worked` is left NULL.
4. Existing record → UPDATE (status, both times, hours, notes, `recorded_by`,
   `updated_at`). No record → INSERT, copying `username` and `full_name` onto
   the row.
5. Flash *"Attendance record saved."*; any failure flashes *"Error: …"*.

`recorded_by` is set to the signed-in user's username either way, so a
hand-entered day is distinguishable from a clocked one and from an auto-closed
one (`system`).

The modal has no break field, so a brand-new row gets the column default of 0
minutes while its hours are calculated with the **shift's** break deducted; an
existing row keeps whatever break it already carried.

> Source: `platform/blueprints/hr/routes.py:1647-1732`;
> `platform/templates/hr/hr_attendance.html:326-373`

---

## A23. Endpoint: Headcount JSON

**Route.** `GET /hr/api/headcount`
**Who can call it.** Anyone holding the `hr` grant (login only on the route).

Returns `{"doctor": 4, "nurse": 6, …}` — a count of **active** users per role.
No screen in the platform calls it.

> Source: `platform/blueprints/hr/routes.py:1748-1756`

---

# Part B — Attendance & Leave / الحضور والإجازات (`/attendance/`)

Everything in this part is available to every role holding the `attendance`
grant, which is most of the clinic. The screens split into two kinds: the ones
an employee uses for themselves (dashboard, check-in, records, leave request),
and the ones only a manager can open (record edit, shifts, leave types,
balances, holidays, leave approval).

### How a day is measured

These five rules govern every number in this part.

1. **The shift is the employee's own.** `default_shift()` reads `staff_shifts`
   for the assignment in force on the date in question, and only falls back to
   the first active clinic-wide shift if the employee is unrostered — then to a
   hardcoded 08:00–17:00 with a 60-minute break if there are no shifts at all.
2. **Lateness** = arrival − shift start − grace (default 15 minutes,
   `ATTENDANCE_GRACE_MINUTES`). A night shift's wrap is handled: clocking in at
   00:10 on a 22:00 shift is ten minutes past midnight on a shift that started
   two hours ago, not fourteen hours early.
3. **Hours worked** = check-out − check-in − break, rounded to two decimals. On
   a day shift a check-out earlier than the check-in yields **0.0**, not a
   wrapped 21.98 — the ordering is treated as a typo, not as a night. Only a
   shift whose end time is at or before its start time wraps past midnight.
4. **Working days** for leave and payroll come from the employee's shift's
   `days_of_week`, minus rows in `public_holidays`. With nothing configured the
   fallback is **Sunday–Thursday**.
5. **hours_worked is only ever written at check-out** (or by the nightly
   auto-close, or by a manager editing the record). A day with a check-in and no
   check-out is worth zero hours to payroll until one of those three closes it.

> Source: `platform/blueprints/attendance/routes.py:58-83` (`_calc_hours`),
> `:86-126` (`default_shift`), `:129-131`, `:136`, `:148-169`
> (`status_for_checkin`), `:172-227` (`close_forgotten_checkouts`), `:232-302`
> (the week and business days)

---

## B1. Screen: Attendance Dashboard / الحضور والإجازات

**Route.** `GET /attendance/`
**Purpose.** Today at a glance, your own leave position, and — for a manager —
the queue of leave requests waiting on them.
**How to reach it.** Sidebar → TEAM → Attendance; launcher card; HR dashboard →
Quick Links → Attendance Dashboard; `← Dashboard / ← لوحة التحكم` from any other
attendance screen.
**Who can open it.** Every role holding `attendance`.

Sub-heading: *"Today: &lt;date&gt; — N active staff"* — **English only**.

### Topbar

`⏱ Check In / Out` / `⏱ الدخول / الخروج` · `📋 Request Leave` / `📋 طلب إجازة` ·
`📊 Monthly Report` / `📊 التقرير الشهري` (managers only).

### The five counters

| Card | What it counts |
|---|---|
| ✅ **Present / حاضر** | Today's records with `status='Present'` — **`Late` rows are not included** |
| ⏱ **Checked In / تم الوصول** | Today's records with a check-in and no check-out; sub-line *"still working / ما زال يعمل"* |
| 🏖 **On Leave / في إجازة** | Approved leave requests spanning today |
| ❌ **Absent / غائب** | Today's records with `status='Absent'` — only rows somebody created; nothing marks an absence automatically |
| 👥 **Total Staff / إجمالي الموظفين** | Active users |

### 📅 Today's Attendance / حضور اليوم

Every record for today ordered by check-in, with columns Staff / الموظف (name
and role), In / دخول, Out / خروج, Hours / الساعات (one decimal), Status / الحالة
(Present / Late / Absent / Leave badges). `View All / عرض الكل` opens the records
list. Empty: *"No attendance records for today yet."*

Times are printed **raw from the column**, so a seeded or imported row shows the
full timestamp here rather than `HH:MM`.

### 🏖 My Leave Balances — &lt;year&gt;

Header **English only**. One row per `leave_balances` row for the signed-in user
and the current year: a colour dot, the type name, `N used / M alloc` and the
remaining days in the type's colour. Empty: *"No balances set for &lt;year&gt;."*
`+ Request / + طلب` opens the leave form.

### 📋 My Recent Requests / طلباتي الأخيرة

The signed-in user's five most recent leave requests: Type / النوع, Dates /
التواريخ, Days / الأيام, Status / الحالة. `View All / عرض الكل` opens the leave
list. Empty: *"No leave requests yet. / لا توجد طلبات إجازة بعد."*

### ⏳ Pending Leave Approvals / طلبات إجازة بانتظار الاعتماد — managers only

Every `Pending` request in the clinic, oldest first: Staff / الموظف, Type /
النوع, Period / الفترة, Days / الأيام, Reason / السبب (first 60 characters),
Submitted / مُرسل, and a `Review / مراجعة` button opening the request. The whole
panel is hidden when the queue is empty.

### Quick links — managers only

Four cards: Attendance Records / سجلات الحضور, Leave Requests / طلبات الإجازة,
Leave Balances / أرصدة الإجازات, Shifts / المناوبات.

> Source: `platform/blueprints/attendance/routes.py:325-393`;
> `platform/templates/attendance/dashboard.html:1-209`

---

## B2. Screen: Check In / Out / الدخول / الخروج

**Route.** `GET/POST /attendance/checkin`
**Purpose.** Where an employee clocks in and out; where a manager clocks
somebody else in or out.
**Who can open it.** Everyone holding `attendance`. Recording for **another**
person requires a manager role — the POST checks this, so sending another
`user_id` by hand is refused with *"Access denied."*

The sub-heading shows today's date and a live clock that refreshes every ten
seconds.

### ⏱ My Status Today / حالتي اليوم — left card

Three states:

**Not checked in / لم يسجل الدخول** (🟡) — a *Notes (optional) / ملاحظات
(اختياري)* textarea (placeholder *"e.g. Working from home / مثال: العمل من
المنزل"*) and a full-width `✅ Check In Now / ✅ تسجيل الدخول الآن` button.

**Checked In / تم الوصول** (🟢) — *"Since HH:MM"* (English only), a *Break Time
(minutes) / وقت الاستراحة (دقائق)* number box **pre-filled with 0**, and
`🔴 Check Out Now / 🔴 تسجيل الخروج الآن`.

**Day Complete / اليوم مكتمل** (✅) — check-in, check-out and total hours in
three tiles, no further action.

### 👥 Record Attendance for Staff / تسجيل حضور الموظفين — managers only

A one-line form: Staff Member / الموظف select (every active user), Action /
الإجراء (Check In / تسجيل وصول, Check Out / الخروج), Break (min) / الاستراحة
(دقيقة) **pre-filled with 0**, Notes / ملاحظات, and a `Record / تسجيل` button.

### 📋 All Staff — Today / جميع الموظفين — اليوم — managers only

Today's records with Staff, Check In, Check Out, Break (`Nm`), Hours, Status and
an `Edit / تعديل` link to the record editor. Non-managers see a placeholder card
instead, pointing at *View My Records / عرض سجلاتي* and *My Leaves / إجازاتي*.

### What check-in does

Time is the **server's** clock, formatted `HH:MM`.

- Already a record for today → amber *"Already checked in today."* and nothing
  is written. There is no way to clock in twice in a day, and no way to correct
  a check-in from this screen.
- Otherwise the row is inserted with `username`, `full_name`, the time, the
  computed status and `recorded_by` = whoever pressed the button.
- If the arrival is late, the flash is amber and explicit: *"Checked in at 09:32
  — 17 minutes after the shift start (grace 15 min)."* Otherwise green
  *"Check-in recorded successfully."*

### What check-out does

- No record, or no check-in → *"No check-in record found for today."*
- Already checked out → amber *"Already checked out."*
- Otherwise hours are computed from the check-in, the break and the shift's
  overnight flag, and the flash reads *"Check-out recorded. Hours worked: 7.5h"*.

**The break defaults to the shift's break only when the box is left empty.** The
route falls back to the shift's `break_minutes` when the submitted value is not
a digit — but both forms pre-fill `0`, which *is* a digit, so an untouched form
records a zero-minute break and pays the lunch hour. Clearing the box entirely
is what triggers the shift default.

> Source: `platform/blueprints/attendance/routes.py:398-504` (break handling at
> `:418-428`); `platform/templates/attendance/checkin.html:1-182`
> (`value="0"` at `:49` and `:105`)

---

## B3. Screen: Attendance Records / سجلات الحضور

**Route.** `GET /attendance/records`
**Purpose.** The history, filtered by date and status; an employee's own by
default, everybody's for a manager.
**How to reach it.** Attendance dashboard → *View All* or the Records quick
card; *"Full attendance history →"* on a staff profile; *"View the days behind
this payslip →"* on a payslip.
**Who can open it.** Everyone holding `attendance`. **A non-manager is always
scoped to their own rows**, and passing `?user_id=` cannot widen that.

### Topbar

`Check In/Out / الدخول/الخروج` · `Export Excel / تصدير Excel` (carries the
current date range and staff filter, B14) · `← Dashboard / ← لوحة التحكم`.

### Filters (GET)

| Control | Parameter | Default |
|---|---|---|
| From / من | `date_from` | today − 29 days |
| To / إلى | `date_to` | today |
| Staff / الموظف | `user_id` | All Staff / جميع الموظفين — **managers only** |
| Status / الحالة | `status` | All / الكل; options Present, Late, Absent, Leave, Holiday (**English only**) |
| `Filter / تصفية` · `Reset / إعادة تعيين` | — | — |

The status list offers `Leave` and `Holiday`, which no route in the platform
ever writes — HR's manual entry writes `On Leave`, not `Leave`.

### Summary cards

Present / حاضر · Late / متأخر · Total Records / إجمالي السجلات · Total Hours /
إجمالي الساعات. All four are computed **in Python over the rows returned**, and
the query is unbounded, so they always match what is on screen.

### Columns

Staff / الموظف (managers only; a link to the profile when the viewer may open
it, plain text otherwise) · Date / التاريخ · Check In / تسجيل وصول · Check Out /
الخروج · Break / الاستراحة (`Nm`) · Hours / الساعات · Status / الحالة badge ·
Notes / ملاحظات · Edit / تعديل (managers only).

Ordered by work date descending, then check-in. **No pagination** — a wide date
range renders every row. Times print raw from the column. Empty state:
*"No attendance records found for the selected filters. / لا توجد سجلات حضور
للتصفية المحددة."*

> Source: `platform/blueprints/attendance/routes.py:509-560`;
> `platform/templates/attendance/records_list.html:1-134`

---

## B4. Screen: Edit Attendance Record / تعديل سجل الحضور

**Route.** `GET/POST /attendance/records/edit/<rec_id>`
**Who can use it.** super_admin, clinic_owner, branch_manager, hr. Anyone else
gets *"Access denied."* and the records list. A missing id: *"Record not
found."*

The sub-header shows the employee (linked when the viewer may open the profile),
the work date, and the shift that was in force **on that date** — name plus
`(start–end)` linking to the Shifts screen — or *"No shift assigned / لا توجد
مناوبة مسندة"*.

| Field | Name | Notes |
|---|---|---|
| Check In Time / وقت الدخول | `check_in` | `type=time`, pre-filled through `hhmm()` so a stored full timestamp renders correctly |
| Check Out Time / وقت الخروج | `check_out` | same |
| Break (minutes) / الاستراحة (دقائق) | `break_minutes` | number, 0–480, pre-filled from the row |
| Status / الحالة | `status` | Present, Late, Absent, Leave, Holiday (**English only**) |
| Notes / ملاحظات | `notes` | textarea |
| (hidden) | `_seen_updated_at` | the row's `updated_at` when the page was opened |

Buttons: `Save Changes / حفظ التغييرات` and `Cancel / إلغاء`.

### What Save does

1. **Concurrency guard.** If the row's `updated_at` has moved since the page was
   opened, nothing is written and the flash names the other editor:
   *"&lt;name&gt; changed this while you had it open (&lt;time&gt;). Your changes were NOT
   saved. Reopen it and apply them again so nothing of theirs is lost."*
2. The shift for that work date is resolved and its overnight flag computed.
3. **A check-out earlier than the check-in on a day shift is refused**:
   *"Check-out is before check-in. This employee is not on a night shift, so one
   of the two times is wrong."*
4. Hours are recomputed from the two times and the break; **if either time is
   blank the hours are written as 0**.
5. The row is updated and the flash reads *"Attendance record updated."*, back
   to the records list.

`recorded_by` is not changed by an edit, so a corrected row still shows whoever
originally created it.

> Source: `platform/blueprints/attendance/routes.py:563-644`;
> `platform/models/concurrency.py:72-96`;
> `platform/templates/attendance/record_edit.html:1-71`

---

## B5. Screen: Leave Requests / طلبات الإجازة

**Route.** `GET /attendance/leaves`
**Purpose.** The list of leave applications — your own, or everybody's for a
manager.
**How to reach it.** Attendance dashboard → *View All* or the Leave Requests
card; the HR dashboard's pending-leave alert; *"View leave requests →"* on a
staff profile.
**Who can open it.** Everyone holding `attendance`; **non-managers see only
their own rows**.

### Topbar

`+ New Request / + طلب جديد` · `← Dashboard / ← لوحة التحكم`.

### Filters (GET)

Staff / الموظف (managers only) · Status / الحالة (All / الكل, Pending, Approved,
Rejected — the options themselves are **English only**) · `Filter / تصفية` ·
`Reset / إعادة تعيين`.

### Stats row

Pending / قيد الانتظار, Approved / معتمد, Rejected / مرفوض — counted **in the
template over the rows on screen**, so they describe the filtered list, not the
clinic.

### Columns

Staff / الموظف (managers only) · Leave Type / نوع الإجازة (colour dot + name) ·
From / من · To / إلى · Days / الأيام · Reason / السبب (first 60 characters) ·
Status / الحالة badge · Submitted / مُرسل (first 10 characters of `created_at`) ·
`View / عرض`.

Newest first, no pagination. Empty state: *"No leave requests found. / لا توجد
طلبات إجازة."* with a link to submit one.

> Source: `platform/blueprints/attendance/routes.py:649-683`;
> `platform/templates/attendance/leaves_list.html:1-124`

---

## B6. Screen: New Leave Request / طلب إجازة جديد

**Route.** `GET/POST /attendance/leaves/new`
**Purpose.** An employee applies for leave **for themselves** — there is no
field for applying on somebody else's behalf, and the route always uses the
signed-in user.
**Who can use it.** Everyone holding `attendance`.

### 📋 Leave Application / نموذج طلب الإجازة

| Field | Name | Required | Notes |
|---|---|---|---|
| Leave Type / نوع الإجازة * | `leave_type_id` | yes | Every **active** leave type as `Name (Paid)` / `(Unpaid)` — that suffix is **English only** |
| Start Date / تاريخ البدء * | `start_date` | yes | `min` is today, so **retroactive leave cannot be requested from this form** |
| End Date / تاريخ الانتهاء * | `end_date` | yes | Same minimum |
| Reason / السبب | `reason` | no | Textarea |

Below the dates a preview strip appears reading *"Approx. N business days"*
followed by *"(business days, excl. weekends & holidays) / (أيام عمل، بدون
عطلات نهاية الأسبوع والعطلات الرسمية)"*. **That preview is computed in the
browser and excludes Saturday and Sunday** — the Western week. The server counts
the employee's real week (Sunday–Thursday by default) and excludes public
holidays, so the two numbers routinely differ; the server's number is the one
that is stored.

### ⚖️ My Balances / أرصدتي — right panel

One block per active leave type: colour dot, name, a Paid / مدفوع or Unpaid /
بدون أجر badge, a progress bar of `(allocated − remaining) / allocated`, and
`Used: N d` / `Remaining: N d` (**English only**). A type with no balance row
shows the type's `days_per_year` as both allocated and remaining. Selecting a
type in the form outlines its block.

Below it a **ℹ️ Notes / ملاحظات** card: *"Days counted are business days only /
تُحتسب أيام العمل فقط"*, *"Weekends and public holidays excluded"*, *"Manager
approval required"*, *"Balance deducted upon approval"*.

### What Submit Request / إرسال الطلب does

1. Missing type or dates → *"Leave type, start and end dates are required."*
2. End before start → *"End date must be on or after start date."*
3. The days are counted as **business days for this employee**, against their
   shift's week and the `public_holidays` table.
4. The balance row for **the year the leave starts in** is created if absent,
   allocated from the type's `days_per_year`.
5. If `remaining − pending` is less than the days requested, an amber flash
   reads *"Insufficient balance. Available: 3.5 days."* — **and the request is
   still submitted**. The shortfall is a warning, not a block.
6. The request is inserted with status `Pending`, and `pending` on the balance
   row is increased by the days requested.
7. Green flash *"Leave request submitted for 5 day(s). Awaiting approval."* and
   a redirect to the leave list.

> Source: `platform/blueprints/attendance/routes.py:686-773`, `:282-317`;
> `platform/templates/attendance/leave_form.html:1-137` (the browser preview at
> `:122-135`)

---

## B7. Screen: Leave request detail

**Route.** `GET /attendance/leaves/<req_id>`
**Who can open it.** The requester, or a manager. Anyone else: *"Access
denied."* A missing id: *"Request not found."*

Header: the type name with its colour dot and the word `Leave` (**English
only**), *"Submitted &lt;date&gt;"*, and a status badge — `⏳ Pending / قيد الانتظار`,
`✅ Approved / معتمد` or `❌ Rejected / مرفوض`.

Three tiles: **Start Date / تاريخ البدء**, **End Date / تاريخ الانتهاء**,
**Business Days / أيام العمل** (the stored `days_requested`, in the type's
colour). Then the **Reason / السبب** box (*"No reason provided."* when empty),
and — on a rejected request — a red **Rejection Reason / سبب الرفض** panel.

A line underneath reads either *"&lt;Status&gt; by &lt;approver&gt; on &lt;date&gt;"* — the
approver is looked up from the username stored in `approved_by` — or *"Not
reviewed by anyone yet. / لم تتم مراجعته من أي مسؤول بعد."*

### Manager actions — only while Pending

- `✅ Approve / ✅ اعتماد` — posts immediately, no confirmation.
- `❌ Reject / ❌ رفض` — reveals a panel with a **required** *Rejection Reason /
  سبب الرفض* textarea and `Confirm Rejection / تأكيد الرفض`.

### Sidebar

**👤 Staff / الموظف** — name (linked for HR roles), role, a link reading
*"Attendance over these dates → / الحضور خلال هذه التواريخ ←"* that opens the
records list filtered to this employee and this date range, and a Paid Leave /
إجازة مدفوعة or Unpaid Leave / إجازة بدون أجر badge.

**⚖️ Balance (&lt;year&gt;)** — Allocated, Used, Pending, Remaining in days, plus
*"All leave balances →"* for managers. When no balance row exists: *"No balance
has been allocated for this leave type. / لم يُخصَّص رصيد لهذا النوع من
الإجازات."* The row is looked up for **the current year**, while approval and
rejection settle against the year the leave starts in, so a request that spans a
new year shows one year's balance and moves another's.

> Source: `platform/blueprints/attendance/routes.py:776-813`;
> `platform/templates/attendance/leave_detail.html:1-156`

---

## B8. Actions: Approve / reject leave

### Approve — `POST /attendance/leaves/<req_id>/approve`

Managers only (*"Access denied."* otherwise). **Only acts when the request is
still `Pending`** — on anything else it silently redirects with no flash at all.

On a pending request: status becomes `Approved`, `approved_by` is set to the
approver's **username** and `approved_at` to now. The balance row for the year
the leave *starts in* is created if missing, then `used` is increased by the
days, `pending` is decreased (floored at 0) and `remaining` is decreased
(floored at 0). Flash: *"Leave request approved."*

### Reject — `POST /attendance/leaves/<req_id>/reject`

Managers only, pending-only, same silence otherwise. Status becomes `Rejected`,
`rejection_reason` is stored, and `pending` on the balance row is released
(floored at 0). `used` and `remaining` are untouched. Flash: *"Leave request
rejected."*

Neither action writes an audit row, and neither can be undone from the
interface: an approved or rejected request has no further buttons. The only way
back is a manager editing the balance by hand (B11).

**An approved leave does not create attendance records.** The days appear on the
roster and in the monthly report's leave table, but `attendance_records` gets no
`On Leave` rows, so payroll's absence maths does not see them either (C1).

> Source: `platform/blueprints/attendance/routes.py:816-877`

---

## B9. Screen: Work Shifts / مناوبات العمل

**Route.** `GET /attendance/shifts`
**Purpose.** Define the shifts everything else is measured against, and see who
is on each one today.
**How to reach it.** Attendance dashboard → Shifts card; HR dashboard → Quick
Links → Manage Shifts; the shift link on an attendance record editor.
**Who can open it.** super_admin, clinic_owner, branch_manager, hr. Anyone else:
*"Access denied."* and the attendance dashboard.

Sub-heading: *"N shift(s) configured"* — **English only**.

### 🕐 All Shifts / جميع المناوبات — the table

| Column | Content |
|---|---|
| Name / الاسم | Colour dot + name |
| Start / البداية · End / النهاية | The stored times |
| Break / الاستراحة | `Nm` |
| Days / الأيام | One chip per number in `days_of_week`, mapped **Sun=0 … Sat=6** — this screen reads the encoding correctly |
| On This Shift / على هذه المناوبة | Every active employee whose assignment is in force today, comma-separated and linked; *"Nobody assigned / لا أحد مسند"* otherwise, plus a *"Weekly roster → / جدول المناوبات الأسبوعي ←"* link |
| Status / الحالة | Active / نشط or Inactive / غير نشط |
| (action) | `Edit / تعديل` — loads the row into the form on the right |

**Inactive shifts are listed here** (the query has no `is_active` filter) but
are excluded from every dropdown that assigns one.

### ➕ Add Shift / إضافة مناوبة — the form

| Field | Name | Default | Notes |
|---|---|---|---|
| (hidden) | `shift_id` | empty | Set by `Edit`; present means update, absent means insert |
| Shift Name / اسم المناوبة * | `name` | — | Required; blank flashes *"Shift name required."* |
| Start Time / وقت البدء | `start_time` | `08:00` | |
| End Time / وقت الانتهاء | `end_time` | `17:00` | An end at or before the start makes it a **night shift** for every calculation |
| Break (minutes) / الاستراحة (دقائق) | `break_minutes` | `60` | 0–240 |
| Working Days / أيام العمل | `days_of_week` | **Sun–Thu ticked** | Seven checkboxes listed Sun, Mon, Tue, Wed, Thu, Fri, Sat and stored 0–6. Ticking none saves Sun–Thu |
| Color / اللون | `color` | `#3b82f6` | Used by the roster chips and the shift table |
| Active / نشط | `is_active` | ticked | Unticking hides the shift from assignment dropdowns |

Buttons: `Add Shift / إضافة مناوبة` (becomes `Update Shift` after pressing Edit)
and `Reset / إعادة تعيين`. Flashes: *"Shift added."* / *"Shift updated."*

**There is no delete.** A shift can only be deactivated. **There is no Arabic
name field** either, although `shifts.name_ar` exists in the schema — a shift's
name is whatever was typed, in one language.

> Source: `platform/blueprints/attendance/routes.py:882-941`;
> `platform/templates/attendance/shifts.html:1-162`;
> `platform/models/database.py:1982-1998`

---

## B10. Screen: Leave Types / أنواع الإجازات

**Route.** `GET /attendance/leave-types`, `POST /attendance/leave-types/save`
**Who can open it.** super_admin, clinic_owner, branch_manager, hr.
**How to reach it.** *"⚖️ Balances"* topbar of the balances screen links back and
forth; there is no link from the dashboard.

### Table

Name / الاسم (colour dot + English name) · Arabic / العربية (`name_ar`, in the
Arabic font) · Days/Year / أيام/سنة · Type / النوع (Paid / مدفوع or Unpaid /
بدون أجر) · Status / الحالة · `Edit / تعديل`.

### Form

| Field | Name | Default | Notes |
|---|---|---|---|
| (hidden) | `lt_id` | empty | Present = update |
| Name (English) / الاسم (إنجليزي) * | `name` | — | Required; blank flashes *"Leave type name required."*. The column is UNIQUE, so a duplicate raises |
| Name (Arabic) / الاسم (عربي) | `name_ar` | — | RTL input |
| Days Per Year / الأيام في السنة | `days_per_year` | `21` | 0–365, step 0.5. Parsed by `money.form_amount` — **a value it cannot parse silently becomes 0**, because the error is discarded |
| Color / اللون | `color` | `#6366f1` | |
| Paid Leave / إجازة مدفوعة | `is_paid` | ticked | Displayed only; nothing in payroll reads it |
| Active / نشط | `is_active` | ticked | Inactive types disappear from the request form and the balances matrix |

Flashes: *"Leave type added."* / *"Leave type updated."*

**There is no delete**, and the four schema columns `requires_approval`,
`min_notice_days`, `max_consecutive` and `attachment_name` are neither editable
here nor read anywhere in the platform.

`days_per_year` is the allocation a balance row is created with, so changing it
affects only balances created afterwards — existing rows keep their `allocated`.

> Source: `platform/blueprints/attendance/routes.py:946-988`;
> `platform/templates/attendance/leave_types.html:1-120`;
> `platform/models/database.py:2028-2039`

---

## B11. Screen: Leave Balances / أرصدة الإجازات

**Route.** `GET /attendance/balances?year=YYYY`, `POST /attendance/balances/set`
**Purpose.** A staff × leave-type matrix of allocations for one year, editable
cell by cell.
**How to reach it.** Attendance dashboard → Leave Balances card; *"All leave
balances →"* on a leave request; *"⚖️ Balances"* from Leave Types.
**Who can open it.** super_admin, clinic_owner, branch_manager, hr.

The topbar carries a **year select (2024–2027, hardcoded)** that reloads on
change, plus links to Leave Types and the dashboard.

### The matrix

Rows are every active user (name + role); columns are every **active** leave
type, each header showing the type's colour dot, name and `Nd/yr`. A cell with a
balance row shows the stored **remaining** in the type's colour over
`/ allocated`; a cell without one shows `—` and *"click to set / اضغط للتعيين"*.
The sub-title reads *"Click any cell to set/edit the balance for that staff
member / اضغط على أي خانة لتعيين/تعديل رصيد ذلك الموظف"*.

### ⚖️ Set Balance / تعيين الرصيد — the modal

Opened by clicking a cell, pre-filled from it. Fields: **Allocated / المخصص**,
**Used / المستخدم**, **Pending / قيد الانتظار** (all numbers, step 0.5, min 0),
with the year, user and leave type as hidden values. Buttons `Save Balance /
حفظ الرصيد` and `Cancel / إلغاء`.

The line under the fields reads **"Remaining = Allocated − Used − Pending /
المتبقي = المخصص − المستخدم − المعلق"**. **That is not what the server does.**
It stores `remaining = max(0, allocated − used)` and keeps `pending` as a
separate figure, exactly as approval and the request form treat it. Subtracting
pending twice was a real defect; the label was not updated.

The write is an upsert on `(user_id, leave_type_id, year)`, so saving the same
cell twice updates rather than duplicating. Flash: *"Balance updated."*

All three numbers go through `money.form_amount`, and **its error is discarded**
— a value it cannot parse is written as 0 with a success message.

> Source: `platform/blueprints/attendance/routes.py:993-1068`;
> `platform/templates/attendance/balances.html:1-129` (the label at `:48`)

---

## B12. Screen: Monthly Attendance Report / تقرير الحضور الشهري

**Route.** `GET /attendance/report?year=&month=&user_id=`
**Purpose.** One month of attendance per employee, with a per-person summary and
the approved leave that overlaps it.
**How to reach it.** `📊 Monthly Report` in the attendance dashboard topbar
(managers only); *"Monthly attendance report →"* on a payslip.
**Who can open it.** Everyone holding `attendance`. **A non-manager is forced to
their own id**, whatever `user_id` says.

### Filters

Year / السنة (**2024–2027, hardcoded**) · Month / الشهر (Jan–Dec, **English
only**) · Staff / الموظف (managers only) · `Generate / إنشاء`.

### Per-staff summary cards

One card per employee with records in the month: name, role, and four tiles —
Present / حاضر, Absent / غائب, Late / متأخر, Total Hrs / إجمالي الساعات (rounded
to a whole number). Statuses are counted from the stored string; a record whose
status is `On Leave` — what HR's manual entry writes — falls into none of the
four buckets and is counted only in the row list below.

### 🏖 Approved Leaves in &lt;month&gt;

Approved requests overlapping the month: Staff / الموظف, Type / النوع, Period /
الفترة, Days / الأيام. Hidden when there are none. Header **English only**.

### 📋 Daily Records — &lt;month&gt; &lt;year&gt;

Every record in the month ordered by employee then date: Staff (managers only),
Date / التاريخ, **Day / اليوم**, In / دخول, Out / خروج, Break / الاستراحة,
Hours / الساعات, Status / الحالة.

**The Day column repeats the date.** The template prepares a weekday-name list
and never uses it, printing `work_date` in both cells.

There is no export button on this screen; the Excel export lives on the records
list (B15). Empty: *"No attendance records for &lt;month&gt; &lt;year&gt;."*

> Source: `platform/blueprints/attendance/routes.py:1073-1145`;
> `platform/templates/attendance/report.html:1-153` (the Day column at `:127-130`)

---

## B13. Screen: Public Holidays / العطلات الرسمية

**Route.** `GET /attendance/holidays?year=YYYY`, `POST /attendance/holidays/save`,
`POST /attendance/holidays/<hid>/delete`
**Purpose.** The dates excluded from every business-day count — leave days and
payroll's working days.
**Who can open it.** super_admin, clinic_owner, branch_manager, hr.
**How to reach it.** No link from the sidebar, the launcher, the attendance
dashboard or the HR dashboard. **The URL is the only door.**

A **year select (2024–2027, hardcoded)** in the topbar reloads on change; the
list is filtered by the first four characters of `holiday_date`.

### Table

Date / التاريخ · Name / الاسم · Arabic / العربية · `Edit / تعديل` and
`Delete / حذف` (confirm *"Delete this holiday?"*, English only).

### ➕ Add Holiday / إضافة عطلة — the form

`holiday_date` (required), `name` (required, e.g. *National Day / العيد
الوطني*), `name_ar`. A missing name or date flashes *"Name and date required."*
Saving flashes *"Holiday saved."* and reloads the list at the saved date's year.
Deleting flashes *"Holiday removed."*

The insert is `INSERT OR IGNORE` on a table with `holiday_date UNIQUE`, so
**adding a second holiday on a date that already exists silently does nothing
and still reports success**.

### QUICK ADD — &lt;year&gt; Egyptian Holidays

A hardcoded one-click list, each a separate one-button form:

`2026-01-01` New Year / رأس السنة · `2026-01-07` Coptic Christmas / عيد الميلاد
القبطي · `2026-01-25` 25 January Revolution / ثورة 25 يناير · `2026-04-25`
Sinai Liberation Day / تحرير سيناء · `2026-05-01` Labour Day / عيد العمال ·
`2026-06-30` June 30 Revolution / ثورة 30 يونيو · `2026-07-23` Revolution Day /
ثورة 23 يوليو · `2026-10-06` Armed Forces Day / يوم القوات المسلحة.

**Every date is hardcoded to 2026**, and each button is rendered only when the
selected year matches — so the panel is empty for any other year, and the
moveable Islamic holidays (Eid al-Fitr, Eid al-Adha, the Islamic New Year, the
Prophet's Birthday) are not in the list at all and must be typed by hand every
year.

The `is_recurring` column exists in the schema, is never written and is never
read.

> Source: `platform/blueprints/attendance/routes.py:1150-1213`;
> `platform/templates/attendance/holidays.html:1-128` (the quick-add list at
> `:82-91`); `platform/models/database.py:2076-2083`

---

## B14. Endpoint: Attendance Excel export

**Route.** `GET /attendance/export/xlsx?date_from=&date_to=&user_id=`
**How to reach it.** `Export Excel / تصدير Excel` in the records-list topbar,
which passes the current range and staff filter.
**Who can use it.** Everyone holding `attendance`; **a non-manager's rows are
scoped to themselves**, and `user_id` cannot widen that.

Defaults: `date_from` = today − 29 days, `date_to` = today.

One sheet named **Attendance**, titled *"Attendance &lt;from&gt; to &lt;to&gt;"*, with the
columns **Date, Staff Name, Role, Check-In, Check-Out, Break (min), Hours
Worked, Status, Notes** — all **English only**. Times are exported as stored, so
imported rows carry their full timestamps. The file downloads as
`attendance_<from>_<to>.xlsx`.

If `openpyxl` is not installed the flash reads *"openpyxl is not installed. Run:
pip install openpyxl"* and you are returned to the records list.

> Source: `platform/blueprints/attendance/routes.py:1218-1261`;
> `platform/models/excel_export.py:50-64`

---

## B15. Endpoint: Today JSON

**Route.** `GET /attendance/api/today`
**Who can call it.** Everyone holding `attendance` — **with no scoping at all**.

Returns `{"date": "2026-08-19", "records": [{user_id, check_in, check_out,
status, hours_worked, full_name}, …]}` for every employee today. A nurse, whose
own records list hides colleagues, gets the whole clinic's arrival times from
this endpoint. No screen in the platform calls it.

> Source: `platform/blueprints/attendance/routes.py:1266-1277`

---

## B16. The nightly auto-close

Not a screen, but it writes to attendance every night and explains rows nobody
remembers creating.

At **00:20** server time, for every clinic, `close_forgotten_checkouts()` looks
at **yesterday's** records with a check-in and no check-out and closes each one:

- The close time is **that employee's own shift end**, not "now".
- On a day shift, an employee who arrived after the shift had already ended is
  closed at their arrival time, so the day is worth zero hours instead of a
  negative number. On a night shift the wrap past midnight is kept.
- The break is the row's own `break_minutes`, or the shift's if the row has
  none.
- The row is stamped `recorded_by='system'` and its notes get
  ` [auto-closed at shift end 16:00; no check-out was recorded]` appended.

So a forgotten check-out is paid as an estimate, and the estimate is
identifiable afterwards from the **Recorded By** column on the HR attendance
screen (A21) and from the note.

> Source: `platform/app.py:806-827`;
> `platform/blueprints/attendance/routes.py:172-227`

---

# Part C — Payroll & Salaries / الرواتب (`/payroll/`)

Payroll is one table, `salaries`, with one row per employee per month and a
UNIQUE constraint on `(user_id, period_year, period_month)` — the same person
cannot have two payslips for the same month.

### The salary statuses

| Status | Set by | What it allows |
|---|---|---|
| **Draft** | New Salary, Bulk Generate | Editable; can be approved |
| **Approved** | the Approve button (only from Draft) | Editable; can be marked paid |
| **Paid** | the Mark Paid button (only from Approved) | **Locked** — the edit route refuses with *"Cannot edit a paid salary."* |
| **Cancelled** | **nothing** | Offered as a filter option and given a colour; no route ever sets it |

There is **no delete and no un-approve** anywhere in the module. A Draft or
Approved row can be corrected; a Paid row is permanent.

### The arithmetic

```
gross = basic_salary + allowances + (overtime_hours × overtime_rate)
net   = gross − deductions − absence_deduction − tax_deduction
```

Both are rounded to two decimals and **stored** on the row, so a payslip does
not change if a grade is edited afterwards. Nothing computes tax: `tax_deduction`
is a number somebody types.

### Where the attendance figures come from

`_get_attendance_summary()` reads `attendance_records` for the employee between
the first and last calendar day of the period and returns:

| Figure | How |
|---|---|
| `total_days` | Rows found in the period |
| `present_days` | Rows with status `Present` **or** `Late` |
| `absent_days` | Rows with status `Absent` |
| `late_count` | Rows with status `Late` |
| `overtime_hours` | For each Present/Late row, `hours_worked − standard_hours` when positive, summed |
| `working_days` | Business days for **this employee's** shift week minus public holidays; falls back to the row count, then to the length of the month |
| `shift_name` | The shift assignment in force **today**, not during the period |

`standard_hours` is the employee's current shift, end − start − break, defaulting
to **8.0** when they are unrostered or the times cannot be parsed.

> Source: `platform/blueprints/payroll/routes.py:50-113` (schema), `:123-137`,
> `:146-232` (`_get_attendance_summary`)

---

## C1. Screen: Payroll Dashboard / لوحة الرواتب

**Route.** `GET /payroll/?year=&month=`
**Purpose.** One period's payroll at a glance, with the bulk-generate button.
**How to reach it.** Sidebar → TEAM → Payroll; launcher card; HR dashboard →
Quick Links → Payroll Dashboard.
**Who can open it.** super_admin, clinic_owner, finance (§ 2).

### Topbar

A year select (**this year ± 2**) and a month select with `Filter / تصفية`, then:

| Button | Effect |
|---|---|
| `+ New Salary` / `+ راتب جديد` | Opens the blank salary form (C4) |
| `⚙ Grades` / `⚙ الدرجات` | Opens the salary grades table (C10) |
| `⚡ Bulk Generate` / `⚡ إنشاء جماعي` | Behind a confirm *"Bulk-generate Draft salaries for all staff without records this period?"* (English only). Posts the displayed year and month (C9) |

### The six statistics

Total Records / إجمالي السجلات · Draft / مسودة · Approved / معتمد · Paid /
مدفوع · **Total Paid Out / إجمالي المصروف** (`SUM(net)` where status is Paid,
`EGP 1,234`) · **Pending Payment / في انتظار السداد** (`SUM(net)` where status is
Draft or Approved).

### Coverage warning

When the number of active non-`super_admin` users exceeds the number of salary
rows for the period, an amber strip reads *"⚠ **N** active staff have no salary
record for this period. Use **Bulk Generate / إنشاء جماعي** to create draft
records."* The count is a subtraction of two totals, so it is wrong if somebody
has a salary row but is no longer active.

### Salary Records — &lt;Mon&gt; &lt;year&gt;

The **20** most recently updated rows for the period: Staff / الموظف (linked for
HR roles, plain text otherwise), Role / الدور, Basic / الأساسي, Allowances /
البدلات, Deductions / الاستقطاعات (the three deduction fields added together, in
red), Gross / الإجمالي, Net / الصافي, Status / الحالة chip, and `View / عرض`.
All amounts are printed with **no decimals**. `View All → / عرض الكل ←` opens the
full list. Empty: *"No salary records for this period. / لا توجد سجلات رواتب
لهذه الفترة."*

> Source: `platform/blueprints/payroll/routes.py:237-277`;
> `platform/templates/payroll/dashboard.html:1-113`

---

## C2. Screen: Salaries / الرواتب

**Route.** `GET /payroll/salaries?year=&month=&status=`
**Purpose.** Every salary row for one period.
**How to reach it.** `View All →` on the payroll dashboard; the redirect after
creating, editing or bulk-generating.
**Who can open it.** **Everyone signed in.** Payroll roles see every row; every
other role — including a nurse or a groomer — sees **only their own**, which is
the only way an ordinary employee reaches their payslip.

### Topbar

`← Dashboard / ← لوحة التحكم` · `📊 Export Excel / 📊 تصدير Excel` (C3) ·
`+ New / + جديد` (which non-payroll roles cannot use).

### Filters (GET)

Year (**this year ± 2**) · Month (Jan–Dec) · Status (All status / كل الحالات,
Draft, Approved, Paid, Cancelled — **English only**) · `Filter / تصفية`.
Defaults are the current year and month.

### Columns

Staff / الموظف · Role / الدور · Basic / الأساسي · **OT / إضافي** (hours × rate,
computed in the template) · Allow. / بدلات · Deduct. / استقطاعات (the three
deduction fields added together) · Gross / الإجمالي · **Net / الصافي** (`EGP
12,345`) · Status / الحالة chip · Payment / الدفع (method and date) ·
Actions / إجراءات — `View / عرض`, plus `Edit / تعديل` when the status is not
Paid.

Ordered by employee name. **No pagination.** All amounts print with no decimals.
Empty: *"No records found. / لا توجد سجلات."*

> Source: `platform/blueprints/payroll/routes.py:282-320`;
> `platform/templates/payroll/salaries_list.html:1-79`

---

## C3. Endpoint: Payroll Excel export

**Route.** `GET /payroll/salaries/export/xlsx?year=&month=`
**Who can use it.** Everyone signed in, scoped exactly like the list — a
non-payroll role exports only their own row.

One sheet named **Salaries**, titled *"Payroll — &lt;Mon&gt; &lt;year&gt;"*, columns
**Name, Role, Year, Month, Basic, Allowances, OT Hrs, OT Rate, Gross,
Deductions, Absence Ded, Tax Ded, Net Salary, Status, Payment Date** — all
**English only**, month rendered as `Aug`. Downloads as
`payroll_<year>_<month>.xlsx`. The status filter on the list is **not** applied
to the export.

Without `openpyxl` the flash reads *"openpyxl is not installed. Run: pip install
openpyxl"* and you are returned to the list.

> Source: `platform/blueprints/payroll/routes.py:325-390`

---

## C4. Screen: New Salary Record / راتب جديد

**Route.** `GET/POST /payroll/salaries/new`
**Who can use it.** super_admin, clinic_owner, finance.
**How to reach it.** `+ New Salary` on the dashboard, `+ New` on the list.

| Field | Name | Notes |
|---|---|---|
| Staff Member * / الموظف * | `user_id` | Every active user as `Name (role)`. **Required** — the route reads it directly and a missing value is a server error |
| Year * / السنة * | `period_year` | Number, 2020–2035, defaults to this year |
| Month * / الشهر * | `period_month` | Jan–Dec, defaults to this month |
| Basic Salary (EGP) / الراتب الأساسي (جنيه) | `basic_salary` | Auto-filled from the role's grade when a staff member is chosen |
| Allowances (EGP) / البدلات (جنيه) | `allowances` | **Not** auto-filled from the grade on this form, even though the grade has an allowances column |
| Overtime Hours / ساعات العمل الإضافي | `overtime_hours` | Step 0.5 |
| Overtime Rate (EGP/hr) / سعر الساعة الإضافية | `overtime_rate` | Auto-filled from the grade |
| Deductions (EGP) / الاستقطاعات (جنيه) | `deductions` | |
| Absence Deduction (EGP) / استقطاع الغياب (جنيه) | `absence_deduction` | |
| Tax Deduction (EGP) / استقطاع الضريبة (جنيه) | `tax_deduction` | Typed by hand; nothing computes Egyptian income tax |
| Notes / ملاحظات | `notes` | Textarea |

A green strip under the fields shows **Gross: / الإجمالي:** and **Net: /
الصافي:** recalculated in the browser on every keystroke.

### 📊 Attendance banner

As soon as a staff member is chosen, the form fetches
`/payroll/api/attendance/<uid>/<year>/<month>` and shows a blue banner:
*"📊 Attendance — Aug 2026"* with ✅ Present, ❌ Absent, ⏰ Late and 🕐 Overtime
hours. It reloads when the year or month changes and hides itself when the
period has no records.

`⚡ Auto-fill from Attendance / ⚡ تعبئة تلقائية من الحضور` writes two fields:
`overtime_hours` from the summary, and `absence_deduction` as
`(absent_days ÷ working_days) × basic_salary`, rounded to two decimals. It does
not touch anything else, and it uses whatever is currently in the basic-salary
box.

### Save

`💾 Save Salary Record / 💾 حفظ سجل الراتب` inserts the row with status
**Draft**, `created_by` = you, and flashes *"Salary record created."*, then
redirects to the list for that period. A second row for the same person and
month violates the UNIQUE constraint and flashes *"Error: UNIQUE constraint
failed: …"*.

The seven money boxes are read with a bare `float()`, so a value the browser
lets through that Python cannot parse produces a server error rather than a
field-level message.

> Source: `platform/blueprints/payroll/routes.py:393-439`;
> `platform/templates/payroll/salary_form.html:1-180`

---

## C5. Screen: Salary record / سجل الراتب

**Route.** `GET /payroll/salaries/<sid>`
**Purpose.** One payslip, its attendance backing, and the approve/pay buttons.
**Who can open it.** Payroll and view roles for anyone's record; every other
role only their **own**, otherwise *"You don't have permission to view this
salary record."* and the launcher. A missing id: *"Record not found."*

A payslip whose employee has been deleted still opens: the name renders as
*"Former employee / موظف سابق"* in plain text.

### Topbar

`← Back / ← رجوع` · `Edit / تعديل` (hidden once Paid) · `Download Payslip PDF /
تحميل قسيمة الراتب PDF` (C11).

### The document

A two-column table: Role / الدور · Period / الفترة (`2026-08`) · Basic Salary /
الراتب الأساسي · Allowances / البدلات · **Overtime (Nh × EGP R)** (English
label) · Deductions / الاستقطاعات (red) · **Absence Deduction / استقطاع الغياب**
(red) — the label carries a link reading *"(N absent days / يوم غياب)"* that
opens the attendance records list filtered to this employee, this period and
`status=Absent` · Tax Deduction / استقطاع الضريبة (red) · **Gross / الإجمالي** ·
**Net Pay / صافي الراتب** in green. Every amount is `EGP 1,234.56`. Notes /
ملاحظات appear below when set.

### Sidebar

- **Approve Salary / اعتماد الراتب** — shown only while Draft: a single
  `✅ Approve / ✅ اعتماد` button (C7).
- **Mark as Paid / تعليم كمدفوع** — shown only while Approved: a payment-method
  select (Bank Transfer, Cash, Cheque, Wallet — **English only**), a payment date
  defaulting to today, and `💸 Mark Paid / 💸 تعليم كمدفوع` (C8).
- **✅ Paid / ✅ مدفوع** — shown once paid: method, date and *"By / بواسطة
  &lt;payer&gt;"*.
- **🗓 Attendance This Period / الحضور عن هذه الفترة** — Days Recorded / الأيام
  المسجلة, Days Present / أيام الحضور, Days Absent / أيام الغياب (red), Late
  Arrivals / مرات التأخير, Overtime Hours / ساعات العمل الإضافي, Shift /
  المناوبة (linked to the Shifts screen, or *"No shift assigned"*). When the
  period has no records: *"No attendance was recorded for this period. / لم
  يُسجَّل حضور عن هذه الفترة."* Two links follow: *"View the days behind this
  payslip → / عرض الأيام المحتسبة في هذه القسيمة ←"* and *"Monthly attendance
  report → / تقرير الحضور الشهري ←"*.
- A footer card with `Created` and `Updated` dates — **English only**.

**This panel is recomputed live from attendance every time the page opens.** The
stored row is what gets paid; the panel is what attendance says now. If somebody
edits an attendance record after the payslip was generated, the two disagree and
nothing on the screen points that out.

> Source: `platform/blueprints/payroll/routes.py:444-479`;
> `platform/templates/payroll/salary_detail.html:1-166`

---

## C6. Screen: Edit Salary Record

**Route.** `GET/POST /payroll/salaries/<sid>/edit`
**Who can use it.** super_admin, clinic_owner, finance.

Refuses a paid record before rendering anything: amber *"Cannot edit a paid
salary."* and back to the detail page. A missing id: *"Record not found."*

The same form as C4 with three differences: the staff member is a **disabled**
box showing `Name (role)` with the id in a hidden field, the heading reads
*"💰 Edit Salary Record"*, and the attendance banner and auto-fill button are
**not rendered** — auto-fill from attendance is available only when creating.

The update writes the seven money fields, the recomputed gross and net, the
notes and `updated_at`. **`period_year` and `period_month` are on the form and
are not written**, so moving a payslip to a different month is impossible from
here. Flash *"Salary updated."*, back to the detail page.

> Source: `platform/blueprints/payroll/routes.py:484-535`

---

## C7. Action: Approve a salary

**Route.** `POST /payroll/salaries/<sid>/approve`
**Who can use it.** super_admin, clinic_owner, finance.

Sets `status='Approved'` and `updated_at` **only where the row is still Draft**.
The flash is *"Salary approved."* **whether or not anything changed** — pressing
it on an already-approved or paid row reports success and writes nothing. No
audit row is written, and the approver is not recorded anywhere.

> Source: `platform/blueprints/payroll/routes.py:540-551`

---

## C8. Action: Mark a salary paid

**Route.** `POST /payroll/salaries/<sid>/pay`
**Who can use it.** super_admin, clinic_owner, finance.

| Field | Notes |
|---|---|
| `payment_method` | Bank Transfer, Cash, Cheque, Wallet. **Defaults to `Cash` if the field is missing** |
| `payment_date` | Defaults to today when blank |

Sets `status='Paid'`, the method, the date, `paid_by` = you and `updated_at`,
**only where the row is still Approved**. Flash *"Salary marked as paid."*
regardless — pressing it on a Draft row reports success and changes nothing.

**No money moves.** This is a status flag: nothing is written to the accounting
or finance modules, no expense is recorded, and payroll does not appear in the
Profit & Loss statement as a cost. A clinic that wants payroll in its books must
also record it as an expense in Accounting (Finance § 19).

> Source: `platform/blueprints/payroll/routes.py:554-568`

---

## C9. Action: Bulk Generate / إنشاء جماعي

**Route.** `POST /payroll/bulk-generate`
**Who can use it.** super_admin, clinic_owner, finance.
**How to reach it.** The `⚡ Bulk Generate` button on the payroll dashboard,
which posts the year and month currently displayed.

For **every active user whose role is not `super_admin` and who has no salary
row for that period**:

1. The role's grade supplies `basic_salary`, `allowances` and `overtime_rate` —
   **all three are 0 for a role with no row in `salary_grades`**, which is every
   role until the Grades screen is saved.
2. The attendance summary for the period supplies the overtime hours.
3. `absence_deduction = (absent_days ÷ working_days) × basic_salary`, rounded to
   two decimals; zero when there are no working days.
4. Gross and net are computed, `deductions` and `tax_deduction` are 0.
5. The row is inserted as **Draft** with the note
   *"Auto: 2 absent, 6.5h OT"* (**English only**) and `created_by` = you.

Rows that fail to insert are **silently skipped** — the `except` swallows them
and the counter is not incremented. The flash reads *"Bulk generated 14 salary
records for 2026-08."*

Running it twice in the same period is safe: the second run finds a row for
everybody and creates nothing.

> Source: `platform/blueprints/payroll/routes.py:573-630`

---

## C10. Screen: Salary Grades / درجات الرواتب

**Route.** `GET/POST /payroll/grades`
**Purpose.** The default pay per role, used by New Salary's auto-fill and by
Bulk Generate.
**How to reach it.** `⚙ Grades / ⚙ الدرجات` on the payroll dashboard.
**Who can use it.** super_admin, clinic_owner, finance.

Sub-title: *"Default basic salary and overtime rate per role. Used when
bulk-generating payroll. / الراتب الأساسي وسعر الساعة الإضافية الافتراضي لكل
دور. يُستخدم عند الإنشاء الجماعي للرواتب."*

One row per role in payroll's own hardcoded 13-key list — **the same list as the
staff form, so `hr` and every custom role are missing and can never be given a
grade here**. Each row has four inputs:

| Column | Field | Notes |
|---|---|---|
| Role / الدور | — | The raw key in a badge |
| Basic Salary (EGP/month) / الراتب الأساسي (جنيه/شهر) | `basic_<role>` | |
| Allowances (EGP/month) / البدلات (جنيه/شهر) | `allow_<role>` | |
| Overtime Rate (EGP/hour) / سعر الساعة الإضافية (جنيه/ساعة) | `ot_<role>` | |
| Notes / ملاحظات | `notes_<role>` | Free text, placeholder *"optional / اختياري"* |

`💾 Save All Grades / 💾 حفظ كل الدرجات` upserts **all thirteen rows at once**,
keyed on the role. Every empty box is saved as 0, so the form is the complete
statement of the grade table. Flash: *"Salary grades saved."*

**`salary_grades` starts empty.** Until this form is saved once, every role
reads 0 basic, 0 allowances and 0 overtime rate — so Bulk Generate produces a
page of zero payslips and New Salary auto-fills nothing. The two seeding scripts
that do populate it (`scripts/seed/demo_showcase.py`, `seed_hr.py`) insert only
`basic_salary` and `overtime_rate`, leaving **allowances at 0** on a demo
clinic. The per-role allowance exists as a column and a form field; it is zero
for every role until somebody sets it here.

The three money boxes go through `money.form_amount`, and **its error is
discarded** — a value it cannot parse is saved as 0 with a success message.

> Source: `platform/blueprints/payroll/routes.py:28-32` (`_ROLES`), `:63-84`
> (the table and the allowances migration), `:635-665`;
> `platform/templates/payroll/salary_grades.html:1-49`;
> `platform/scripts/seed/demo_showcase.py:1163-1167`; `platform/seed_hr.py:402-408`

---

## C11. Endpoint: Payslip PDF

**Route.** `GET /payroll/salaries/<sid>/payslip`
**Who can use it.** Payroll and view roles for anyone's payslip; everyone else
only their own — otherwise *"You don't have permission to view this salary
record."* A missing id is a 404.

The PDF is generated by `models.pdf_generator.generate_payslip_pdf` from the
salary row joined to the employee's `hire_date`, `contract_type`, `job_title`
and `national_id` (the columns HR's lazy migration adds), plus the clinic record
for the letterhead. It downloads as
`payslip_<Full_Name>_<year>-<month>.pdf`.

A generation failure flashes *"Payslip generation failed: &lt;error&gt;"* and returns
to the detail page.

> Source: `platform/blueprints/payroll/routes.py:670-698`;
> `platform/models/pdf_generator.py:738-741`

---

## C12. Endpoint: Attendance summary JSON

**Route.** `GET /payroll/api/attendance/<uid>/<year>/<month>`
**Who can call it.** Payroll and view roles for any uid; everybody else only
their own, otherwise `403 {"error": "forbidden"}`. A month outside 1–12 or a
year outside 1900–2200 returns `400 {"error": "bad period"}`.

Returns the whole summary described at the top of this part: `total_days`,
`present_days`, `absent_days`, `late_count`, `overtime_hours`, `working_days`,
`period_start`, `period_end`, `shift_name`. Used by the New Salary form's
attendance banner.

> Source: `platform/blueprints/payroll/routes.py:703-717`

---

## C13. Endpoint: Grade JSON

**Route.** `GET /payroll/api/grade/<role>`
**Who can call it.** super_admin, clinic_owner, finance.

Returns the whole `salary_grades` row for that role, or
`{"basic_salary": 0, "overtime_rate": 0}` when the role has no grade. **No
screen calls it** — the salary form embeds the whole grade table in the page
instead.

> Source: `platform/blueprints/payroll/routes.py:722-732`

---

# Part D — How the three modules feed each other

| From | To | What actually crosses |
|---|---|---|
| HR → Attendance | `staff_shifts` | The shift assignment decides the lateness threshold, the unpaid break, whether hours wrap past midnight, which weekdays are working days, and where the nightly auto-close puts the check-out |
| HR → Attendance | `/hr/attendance/add` | Hand-entered attendance rows, computed with the attendance module's own arithmetic |
| Attendance → Payroll | `attendance_records.hours_worked` | Overtime hours = hours beyond the shift's standard day, summed over Present and Late days |
| Attendance → Payroll | `attendance_records.status` | Absent days, and through them the absence deduction |
| Attendance → Payroll | `shifts.days_of_week` + `public_holidays` | The working-day denominator the absence deduction divides by |
| Payroll → HR | `salaries` | The last six months on the staff profile, and the "Payroll This Month" card on the HR dashboard |
| Payroll → Attendance | links | The payslip links to the exact attendance rows and the monthly report behind it |
| HR → everything | `users.role` | The role decides every permission in the platform, and is written from the staff form through the role-change guard |

**What does not cross:**

- **Approved overtime in `overtime_log` never reaches payroll.** Payroll derives
  its own overtime from attendance hours. An approved entry in the HR overtime
  log affects nothing except that screen's own totals.
- **Approved leave never reaches attendance.** No `On Leave` rows are created,
  so a day on approved leave has no attendance record, is not an absence, and
  simply does not appear in payroll's counts either way.
- **Paying a salary never reaches the books.** No expense, no journal entry, no
  effect on Profit & Loss or Cash Flow.
- **`leave_types.is_paid` reaches nothing.** Unpaid leave is not deducted from
  anybody's pay by any code path.

---

## Known limits

Everything below is a real behaviour of the current code, verified in the
source and, where the wording says so, by running it. None of it is speculation
about future work.

### Not implemented at all

- **Nothing in these modules can be deleted except a warning, a certification,
  an HR note and an attendance record.** There is no delete for a shift, a leave
  type, a public holiday's underlying record beyond its own button, a
  performance review, a leave request, a salary record or a staff account.
  Staff and shifts are deactivated instead; a leave request and a salary row are
  permanent once created.
- **A leave request cannot be cancelled or withdrawn**, by the employee or by a
  manager. Once submitted it sits as `Pending` — and its days sit reserved on
  the balance — until somebody approves or rejects it.
- **Approve and pay cannot be undone.** There is no un-approve, no un-pay and no
  way to reopen a Paid salary; the edit route refuses it outright.
- **The `Cancelled` salary status is never set.** It is a filter option on the
  salaries list and has a colour in the status map; no route writes it.
- **Marking a salary Paid moves no money and writes no accounting entry.** It
  sets a flag, a method and a date on the row. Payroll does not appear in the
  Profit & Loss statement, the Cash Flow screen or the expenses list unless
  somebody records it there by hand.
- **Approved overtime is never paid.** `overtime_log` is written, approved and
  totalled by HR, and payroll derives its own overtime hours from
  `attendance_records.hours_worked` instead. The two figures are unrelated.
- **Approved leave creates no attendance records.** A day on approved leave has
  no row in `attendance_records`, so it is neither present nor absent, appears
  in payroll's counts as nothing at all, and shows up only on the roster and in
  the monthly report's leave table.
- **`leave_types.is_paid` affects nobody's pay.** It is displayed on the leave
  type, the request form and the request detail, and no code path deducts for
  unpaid leave.
- **No employee can change their own password**, and no HR officer can reset
  one — see A6 and System § 5.
- **The Public Holidays screen has no link anywhere.** Not in the sidebar, the
  launcher, the attendance dashboard's quick cards or the HR dashboard. It must
  be reached by typing `/attendance/holidays`.
- **A shift has no Arabic name.** `shifts.name_ar` is in the schema and the
  Shifts form has no field for it, so shift names are single-language.
- **Eight database columns are dead:** `leave_types.requires_approval`,
  `.min_notice_days`, `.max_consecutive`; `leave_requests.attachment_name`;
  `public_holidays.is_recurring`; `staff_notes.is_private` (written TRUE, never
  read); `staff_warnings.expiry_date` (written, never read — a warning never
  expires); `staff_certifications.notes` (written by the add form, rendered on
  no screen).
- **`GET /hr/api/headcount`, `GET /attendance/api/today` and
  `GET /payroll/api/grade/<role>` are called by no screen in the platform.**
- **There is no export on the monthly attendance report** — the only Excel
  export of attendance is on the records list.

> Source: `platform/blueprints/payroll/routes.py:36-41`, `:484-500`, `:554-568`;
> `platform/blueprints/attendance/routes.py:816-877`, `:907-941`, `:958-988`;
> `platform/blueprints/hr/routes.py:1124-1149`, `:1200-1225`, `:1447-1522`;
> `platform/models/database.py:1982-1998`, `:2028-2039`, `:2055-2083`

### Permissions

1. **`branch_manager` and `support_admin` are named on nearly every HR route
   and can reach none of them.** Neither role holds the `hr` grant, so the
   module gate rejects them before the role list is read. The same is true of
   `branch_manager` and `support_admin` on every payroll role list.
2. **`hr` holds the `payroll` grant and is excluded from every payroll admin
   screen** by the role tuples. The grant buys an HR officer nothing except
   their own payslip, which `@self_service` would have given them anyway.
3. **An HR officer reads everybody's pay from the staff profile.** The *Salary
   History (Last 6 Months)* panel is rendered to every viewer of the profile and
   prints basic and net salary, although the same person is refused by the
   payroll module. The `View` button on that panel then lands on *"You don't
   have permission to view this salary record."*
4. **The staff profile shows `hr` four controls it cannot use:** Reset Password,
   `Del` on a warning, `Delete` on a note, and (via the Salary History panel)
   the payslip link. Each posts, is refused, and dumps the user on the launcher.
5. **`/attendance/api/today` is unscoped.** Every role holding the `attendance`
   grant — which is nearly the whole clinic — can read every colleague's arrival
   time, departure time, hours and status for today from it, while the same
   person's records screen shows only their own rows.
6. **The launcher's role lists disagree with the grants in four ways.** The
   *Admin & HR* card is not shown to `hr`, the only non-owner role that can use
   the module. It **is** shown to `branch_manager`, which is bounced. The
   *Attendance* card is withheld from `pharmacist`, `inventory_mgr`, `groomer`
   and `boarding_staff`, all of which hold the grant, and is offered to a role
   called `staff` that does not exist. The *Payroll* card is shown to
   `branch_manager` and `hr`, both of which are bounced.
7. **The sidebar's TEAM group shows all three links to `branch_manager` and
   `support_admin`**, and two of the three bounce for each of them.
8. **The `hr` role cannot be assigned from the staff form** — see the next
   section — so in a default installation nobody holds the one role the HR
   module was designed around, and the module is effectively owner-only.
9. If the `roles` table has never been seeded, the module gate falls open for
   every built-in role and all of the above widens to every signed-in user.

> Source: `platform/blueprints/auth/routes.py:89-134`, `:167-194`;
> `platform/models/database.py:4346-4379`;
> `platform/blueprints/launcher/routes.py:431-475`, `:574-579`;
> `platform/templates/base.html:226-249`;
> `platform/templates/hr/staff_detail.html:121-129`, `:261-280`, `:301-311`,
> `:405-414`; `platform/blueprints/attendance/routes.py:1266-1277`

### The staff form, roles and passwords

10. **`/hr/staff/new` cannot create an HR officer.** Its Role dropdown is a
    hardcoded list of thirteen keys — super_admin, clinic_owner, branch_manager,
    doctor, nurse, reception, inventory_mgr, pharmacist, finance, groomer,
    boarding_staff, support_admin, auditor — and **omits `hr`**, which is a
    real, seeded role (*HR Officer / موظف الموارد البشرية*) carrying the
    `hr`, `attendance` and `payroll` grants. It also omits every role created on
    the System → Roles screen. Verified by rendering the page: the option
    `<option value="hr"` is not present. The same list drives the staff-list
    role filter, so an HR officer cannot be filtered for either, and payroll's
    copy of it drives the Salary Grades table, so an HR officer can never be
    given a salary grade. The only way to put somebody on the role is the Staff
    Access tab in System.
    > `platform/blueprints/hr/routes.py:20-24`,
    > `platform/templates/hr/staff_form.html:146-152`,
    > `platform/models/database.py:2445`, `:4372`

11. **Both password hints say six characters and the server requires twelve.**
    The New Staff form's placeholder reads *"Min 6 characters / 6 أحرف على
    الأقل"*, and the Reset Password box on the staff profile reads *"New
    password (min 6 chars) / كلمة مرور جديدة (6 أحرف على الأقل)"* **and carries
    `minlength="6"`**, so the browser accepts a six-character password and
    submits it. `validate_password_strength` then requires **at least 12
    characters with an uppercase letter, a lowercase letter, a digit and a
    special character** and rejects it after the round trip — on create the
    failure arrives wrapped as *"Error creating user: Password must be at least
    12 characters."*, on reset as the bare rule.
    > `platform/templates/hr/staff_form.html:52`,
    > `platform/templates/hr/staff_detail.html:126` vs
    > `platform/models/security.py:346-367`

12. **A rejected staff edit loses what you typed.** On failure the edit route
    re-renders the form from the database row rather than from the submission,
    so the flash explains the problem and the form no longer contains the change
    that caused it.
    > `platform/blueprints/hr/routes.py:819-847`

### The Egyptian week and dates

13. **The Weekly Roster always draws Sunday as a day off.** The template
    compares `isoweekday()` (Mon=1 … Sun=7) against `days_of_week`, which is
    stored Sun=0 … Sat=6. The two agree for Monday to Saturday and disagree
    about Sunday, so a shift working Sunday — including the seeded Morning,
    Evening and Night shifts — shows `Off / إجازة` in the Sunday column while
    the rest of the platform treats it as a working day. Verified by assigning
    the seeded Morning Shift (`0,1,2,3,4`) and rendering the roster: twelve
    `Off` cells appear where nine are correct.
    > `platform/templates/hr/roster.html:91-92`
14. **The roster's fallback for a shift with no days is `1,2,3,4,5`** —
    Monday to Friday, the American week — while the schema default, the Shifts
    form and every calculation use Sunday to Thursday.
    > `platform/templates/hr/roster.html:84` vs
    > `platform/models/database.py:1994`
15. **The leave form's day preview counts the wrong weekend.** The
    *"Approx. N business days"* strip is computed in the browser and skips
    Saturday and Sunday; the server counts the employee's own shift week
    (Sunday–Thursday by default) and subtracts public holidays. The two numbers
    routinely differ by one or two days, and the server's is the one stored on
    the request.
    > `platform/templates/attendance/leave_form.html:122-135` vs
    > `platform/blueprints/attendance/routes.py:282-302`
16. **Three year selects are hardcoded to 2024–2027** — Leave Balances, Public
    Holidays and the monthly report. From 2028 the screens still work by URL
    (`?year=2028`) but no dropdown offers the year.
    > `platform/templates/attendance/balances.html:9`,
    > `platform/templates/attendance/holidays.html:9`,
    > `platform/templates/attendance/report.html:18`
17. **The Quick Add list of Egyptian holidays is hardcoded to 2026 and contains
    no Islamic dates.** Each of the eight buttons carries a literal 2026 date
    and is rendered only when the selected year is 2026, so the panel is empty
    for every other year. Eid al-Fitr, Eid al-Adha, the Islamic New Year and the
    Prophet's Birthday — which move every year and are the holidays a clinic
    most needs — are not offered at all and must be typed by hand.
    > `platform/templates/attendance/holidays.html:82-103`
18. **A duplicate holiday date is silently ignored.** `holiday_date` is UNIQUE
    and the insert is `INSERT OR IGNORE`, so adding a second holiday on a date
    that already has one writes nothing and still flashes *"Holiday saved."*
    > `platform/blueprints/attendance/routes.py:1190-1198`
19. **Retroactive leave cannot be requested.** Both date boxes carry
    `min="<today>"`, so an employee who was ill last week cannot file for it;
    only a manager writing the balance by hand can record it.
    > `platform/templates/attendance/leave_form.html:36-42`
20. **A leave request that crosses a new year shows one year's balance and
    settles another's.** The detail page looks the balance up for the *current*
    year, while approve and reject both settle against the year the leave
    *starts* in.
    > `platform/blueprints/attendance/routes.py:796-798` vs `:836`, `:869`

### Time, hours and status

21. **The break box defeats its own default.** The route uses the employee's
    shift break whenever the submitted `break_minutes` is not a digit — but the
    check-out form and the manager's record form both pre-fill `0`, which is a
    digit. An untouched form therefore records a zero-minute break and pays the
    lunch hour, while payroll's standard-hours figure subtracts the shift break;
    the difference is booked as overtime. Clearing the box entirely is what
    restores the intended default.
    > `platform/blueprints/attendance/routes.py:418-428` vs
    > `platform/templates/attendance/checkin.html:49`, `:105`
22. **Editing a record with one time blank writes zero hours.** The record
    editor recomputes hours only when both times are present; otherwise it
    stores `0`. Marking a day `Absent` from this screen while leaving a check-in
    in place therefore zeroes the hours. (HR's own *Log Attendance* modal is the
    opposite: it preserves the times it was not given.)
    > `platform/blueprints/attendance/routes.py:609-616`
23. **Nothing ever marks anybody Absent.** `Absent` is counted on four screens
    and set by exactly two paths, both manual: the record editor and HR's Log
    Attendance modal. An employee who simply does not come in has no row at all,
    so they are not absent for payroll either, and the absence deduction is zero.
    The HR attendance screen's *"N not recorded / بدون تسجيل"* strip is the only
    place a no-show is visible.
24. **The status vocabulary is inconsistent across screens.** The records list
    and the record editor offer `Leave` and `Holiday`, which no route writes; HR's
    modal writes `On Leave`, which those two screens have no option for; and the
    monthly report's per-person summary counts only `Present`, `Absent`, `Late`
    and `Leave`, so a day recorded as `On Leave` is counted in none of its four
    tiles.
    > `platform/templates/attendance/records_list.html:40`,
    > `platform/templates/attendance/record_edit.html:54` vs
    > `platform/templates/hr/hr_attendance.html:347-352` and
    > `platform/blueprints/attendance/routes.py:1111-1116`
25. **The attendance dashboard's "Present" counter excludes late arrivals.** It
    counts `status='Present'` only, so a clinic where several people arrived late
    shows fewer present than are in the building. The HR attendance screen counts
    them separately and says so; this one does not.
    > `platform/blueprints/attendance/routes.py:334-336`
26. **Three screens print times raw from the column.** The attendance dashboard,
    the records list and the Excel export render `check_in` and `check_out`
    unprocessed, so a seeded or imported row shows `2026-08-12 09:27:00` where a
    clocked row shows `09:27`. The record editor and the HR attendance screen
    normalise them through `hhmm()`.
27. **The monthly report's "Day" column repeats the date.** The template builds
    a weekday-name list and never uses it, printing `work_date` in both cells.
    > `platform/templates/attendance/report.html:121-130`
28. **The payslip's "Shift" line is the shift in force today, not during the
    period.** `_get_attendance_summary` resolves the shift name against today's
    date, so a payslip for March shows whatever shift the employee is on now —
    even though the standard-hours figure that produced the overtime came from
    that same current shift too.
    > `platform/blueprints/payroll/routes.py:171-190`

### Money and payroll

29. **`salary_grades` starts empty, so Bulk Generate produces zero payslips.**
    Nothing seeds the table on a fresh clinic. Until somebody opens Salary
    Grades and saves it, every role reads basic 0, allowances 0 and overtime rate
    0, and the flow an owner with twenty staff actually uses creates twenty rows
    of `EGP 0` that must each be corrected by hand.
    > `platform/blueprints/payroll/routes.py:590-604`, `:635-665`
30. **There is no per-role allowance until one is set, and the seeders do not
    set it.** The `allowances` column was added to `salary_grades` by migration
    and the Grades form has a box for it, but both seeding scripts
    (`scripts/seed/demo_showcase.py`, `seed_hr.py`) insert only `basic_salary`
    and `overtime_rate`, so a demo or seeded clinic has allowance 0 for every
    role. Bulk Generate then writes 0 allowances onto every payslip, and the New
    Salary form's auto-fill does not populate the allowances box from the grade
    at all — only basic salary and the overtime rate.
    > `platform/blueprints/payroll/routes.py:84`, `:599-604`;
    > `platform/scripts/seed/demo_showcase.py:1163-1167`;
    > `platform/seed_hr.py:402-408`;
    > `platform/templates/payroll/salary_form.html:123-132`
31. **The `hr` role has no row in the Salary Grades table.** The table iterates
    payroll's own hardcoded 13-key role list, which omits `hr` exactly as the
    staff form does, so an HR officer's grade cannot be entered and Bulk Generate
    gives them a zero payslip.
    > `platform/blueprints/payroll/routes.py:28-32`, `:640`
32. **Approve and Mark Paid always report success.** Both statements carry a
    status condition in the `WHERE` clause and neither checks how many rows
    changed, so pressing Approve on an already-paid record flashes *"Salary
    approved."* and pressing Mark Paid on a Draft flashes *"Salary marked as
    paid."*, in both cases having written nothing.
    > `platform/blueprints/payroll/routes.py:540-568`
33. **Nobody is recorded as having approved a salary.** `paid_by` is stored;
    there is no `approved_by`, and no audit row is written for approve or pay.
34. **The payslip's attendance panel is recomputed live and can contradict the
    payslip.** The stored row is what gets paid; the sidebar shows what
    attendance says at the moment you open the page. Editing an attendance record
    after a payslip was generated changes the panel and not the pay, with nothing
    on screen to indicate the divergence.
35. **Bulk Generate hides its failures.** Each insert is wrapped in a bare
    `except: pass`, and the counter is only incremented on success — so
    *"Bulk generated 14 salary records"* on a clinic of twenty means six failed
    silently, and nothing says which.
    > `platform/blueprints/payroll/routes.py:614-629`
36. **The salary form reads its seven money fields with a bare `float()`**,
    unlike every other money box in the platform. A value the browser lets
    through that Python cannot parse produces a server error rather than a
    field-level message.
    > `platform/blueprints/payroll/routes.py:402-408`, `:504-510`
37. **Three forms discard the money parser's error message.** Leave Types
    (`days_per_year`), Set Balance (`allocated`, `used`, `pending`) and Salary
    Grades (all three columns) call `money.form_amount` and throw the error away,
    so an unparseable value is **saved as 0 with a success flash**.
    > `platform/blueprints/attendance/routes.py:968`, `:1032-1034`;
    > `platform/blueprints/payroll/routes.py:641-643`
38. **Nothing computes tax.** `tax_deduction` is a number somebody types on the
    salary form; Bulk Generate writes 0.
39. **The payroll dashboard's coverage warning is a subtraction of two totals.**
    It compares active non-super-admin users against the number of salary rows
    for the period, so a row belonging to somebody who has since been
    deactivated makes the warning under-report.
    > `platform/blueprints/payroll/routes.py:266-269`

### Leave balances

40. **The Set Balance modal's formula line is wrong.** It reads *"Remaining =
    Allocated − Used − Pending / المتبقي = المخصص − المستخدم − المعلق"*, and the
    server stores `remaining = max(0, allocated − used)`. Subtracting pending a
    second time was a real defect that cost employees days; the label was never
    updated to match the fix.
    > `platform/templates/attendance/balances.html:48` vs
    > `platform/blueprints/attendance/routes.py:1047`
41. **The staff profile computes leave balances a third way.** It prints
    `allocated − used` in the template, ignoring both the stored `remaining` and
    `pending`, so days reserved by an unapproved request are invisible there.
    > `platform/templates/hr/staff_detail.html:212-215`
42. **An over-limit leave request is warned about and submitted anyway.** When
    `remaining − pending` is short, the flash reads *"Insufficient balance.
    Available: 3.5 days."* and the request is still inserted as `Pending` with
    the full day count reserved.
    > `platform/blueprints/attendance/routes.py:736-753`
43. **Rejecting a request releases `pending` and nothing else** — correct — but
    **approving one deducts from `remaining` and `used` with no ceiling check**,
    so an over-limit request that is approved drives `remaining` to 0 (it is
    floored) while `used` exceeds `allocated`.
    > `platform/blueprints/attendance/routes.py:841-846`

### Lists, filters and counts

44. **The Performance Reviews status filter does nothing.** The dropdown offers
    Draft, Submitted and Acknowledged, the value is passed to the template so the
    selection sticks, and the route never adds it to the query. Verified with two
    reviews in different statuses: `?status=Draft` returns both.
    > `platform/blueprints/hr/routes.py:964-983`
45. **The Performance Reviews list's job-title line is always blank.** The
    template renders `r.job_title`, which the query does not select.
    > `platform/templates/hr/performance_list.html:73`
46. **Changing the staff member on an existing review does nothing.** The edit
    form renders the dropdown and the UPDATE does not include `user_id`.
    > `platform/blueprints/hr/routes.py:1071-1081`
47. **The reviews list is capped at 100 rows with nothing on screen to say so.**
    The overtime log is capped at 200 and does say so — but its *Pending
    Approval* KPI is counted in the template over the visible rows, so it is
    capped too while the other two KPIs are not.
    > `platform/blueprints/hr/routes.py:969`, `:1405`;
    > `platform/templates/hr/overtime.html:51-55`
48. **Five lists have no pagination at all**: staff, attendance records, leave
    requests, salaries, certifications. Only the HR attendance search pages (50
    per page). A wide date range on the records list renders every matching row.
49. **The leave list's three stat cards count the rows on screen**, so they
    describe the current filter rather than the clinic.
    > `platform/templates/attendance/leaves_list.html:42-44`
50. **The Shifts table lists inactive shifts** (the query has no `is_active`
    filter) while every dropdown that assigns a shift excludes them, so a shift
    can appear on that screen and be unassignable.
    > `platform/blueprints/attendance/routes.py:889`
51. **The HR attendance quick-range buttons use the browser's UTC clock.** They
    build the dates with `toISOString()`, so late in the Cairo evening *Today*
    can resolve to yesterday.
    > `platform/templates/hr/hr_attendance.html:376-400`
52. **The HR attendance branch filter follows the employee's current branch**,
    not the branch they were working in — `attendance_records` carries no branch.
53. **The HR attendance name search matches the copies stored on the record**
    (`ar.full_name`, `ar.username`), so a staff member renamed since a record was
    written is not found by their new name.
54. **The Certifications list has no filter, no search and no pagination**, and
    nothing can be added or removed from it.
55. **The Performance Reviews period filter is an exact match**, not a
    substring, so `2025` finds nothing when the periods are `2025-Q1` and
    `2025-Q2`.

### Robustness

56. **Six HR dashboard panels fail silently.** Birthdays, anniversaries,
    expiring certifications, recent warnings, pending overtime and the payroll
    card each sit in a `try/except` that rolls back and renders empty. A panel
    that is empty because its query failed is indistinguishable from one that is
    empty because there is no data.
    > `platform/blueprints/hr/routes.py:360-431`
57. **The HR dashboard's "Payroll This Month" card does not exist until the
    payroll module has been opened once.** `salaries` is created by payroll's own
    lazy migration, so on a clinic where nobody has visited `/payroll/` the query
    fails with *no such table: salaries*, is logged, and the card is simply not
    rendered. Verified by loading `/hr/dashboard` on a fresh database.
    > `platform/blueprints/hr/routes.py:286-302`;
    > `platform/blueprints/payroll/routes.py:50-113`
58. **Every write in HR and Attendance depends on JavaScript.** Not one form in
    `templates/hr/` or `templates/attendance/` contains a `_csrf_token` field;
    the token is appended at submit time by `app.min.js`. With the bundle blocked
    or JavaScript off, every check-in, leave request, approval, shift save and
    staff edit returns the 403 page — which prints *"You don't have permission to
    enter this area / غير مصرح لك بالدخول"* rather than the real reason. The five
    Payroll forms carry the field in the HTML and are unaffected. Verified by
    posting to `/hr/staff/1/notes/add` without a token: 403.
    > `platform/static/js/platform.js:129-146`;
    > `platform/app.py:349-357`; `platform/templates/error.html:363`,
    > `:372` vs `platform/templates/payroll/salary_grades.html:16-20`
59. **The payslip route breaks badly when `fpdf2` is missing.** The generator
    guards itself with `if not _FPDF_OK: raise RuntimeError("fpdf2 is not
    installed…")`, but the module also defines `class _ArabicFPDF(..., FPDF)` at
    import time, so importing it without the dependency raises `NameError`
    **before** the route's `try` block is entered. The result is a 500 rather
    than the intended *"Payslip generation failed: …"* flash. `fpdf2>=2.7.0` is
    in `requirements.txt`, so this only bites an incomplete install.
    > `platform/models/pdf_generator.py:14-18`, `:299`, `:740-741`;
    > `platform/blueprints/payroll/routes.py:674-698`

### Bilingual coverage

The three modules are not equally translated. HR is close to complete; Attendance
and Payroll hard-code a good deal. English-only strings that appear on screen:

- **HR** — the `Certifications` and `Staff List` topbar buttons on the dashboard;
  `— Remove Shift —` in the shift assign dropdown; the *Certifications &
  Training* and *Overtime / Extra Hours* panel headings and the `Action:` prefix
  on the staff profile; the warning-type dropdown options; and the four
  `confirm()` dialogs on the staff profile (reset password, delete warning,
  remove certification, delete note) — the confirms on the overtime log,
  the review detail and the HR attendance table are bilingual.
- **Attendance** — the dashboard sub-heading *"Today: … — N active staff"*, the
  *My Leave Balances*, *Since HH:MM*, *Used/Remaining*, and *Approx. N business
  days* strings; the status dropdown options on the records list and the record
  editor (`Present`, `Late`, `Absent`, `Leave`, `Holiday`); the leave-status
  options (`Pending`, `Approved`, `Rejected`); the `(Paid)` / `(Unpaid)` suffix
  on leave types; the word `Leave` in the request detail heading; *"N shift(s)
  configured"*, *"N types configured"*, *"N requests"*, *"N holiday(s)"*; the
  month names; the Excel export's nine column headers.
- **Payroll** — the whole salary form heading (`New Salary Record` / `Edit Salary
  Record`); the `Overtime (Nh × EGP R)` row label; the payment-method options;
  the `Created` / `Updated` footer; the status names in every chip and filter;
  the Bulk Generate confirmation; the first sentence of the coverage warning
  (its *Bulk Generate* button name and closing clause are translated); the Excel
  export's fifteen column headers and the auto-generated note
  *"Auto: N absent, Nh OT"*.

---

## Where to look next

| You want | Chapter |
|---|---|
| Creating an account from the security side, roles and permissions, 2FA, the audit log | [System](system.md) § 4–7, § 12 |
| Recording payroll as a cost in the books | [Finance & Accounting](finance.md) § 19 |
| The same three modules walked end to end as tasks | [Workflow Book → People](../workflows/people.md) |

---

*Chapter verified against the source on 2026-08-19. Every route function and
template named in a `Source:` line was read; the permission tables, the roster's
Sunday behaviour, the performance status filter, the empty role dropdown, the
CSRF dependency and the missing `salaries` table were confirmed by running the
application.*
