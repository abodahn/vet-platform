# System — Reference Manual

**Modules covered:** System / النظام (`/system`), Settings / الإعدادات (`/settings`),
Sign-in & accounts / الحسابات (`/auth`), plus the staff-account screens that live
under HR (`/hr/staff`) because that is where user accounts are actually created.

This chapter is a **screen-by-screen reference**, not a walkthrough. Every field,
button, column and filter below was read out of the route functions and the
Jinja templates. Anything that is present in the database or on screen but does
**not** do what its label suggests is listed under
[Known limits](#20-known-limits) rather than described as working.

> Source: `platform/app.py:209-248` (blueprints imported and registered),
> `platform/blueprints/system/__init__.py:2` (`url_prefix="/system"`),
> `platform/blueprints/settings/__init__.py:3` (`url_prefix="/settings"`),
> `platform/blueprints/auth/__init__.py:3` (`url_prefix="/auth"`)

---

## 1. Getting into the module

### The sidebar SYSTEM group

The left sidebar shows a **SYSTEM / النظام** group only to users whose role is
`super_admin`, `clinic_owner` or `support_admin`. It has six entries:

| Sidebar entry | Goes to |
|---|---|
| Settings / الإعدادات | `/system/settings` |
| System Monitor / مراقبة النظام | `/system/monitor` |
| Roles & Permissions / الأدوار والصلاحيات | `/system/roles` |
| Backup Manager / مدير النسخ الاحتياطية | `/system/backup` |
| Audit Log / سجل المراجعة | `/system/audit` |
| Data Migration / ترحيل البيانات | `/migration/` (a different module, not covered here) |

> Source: `platform/templates/base.html:289-324`

### Other doors

| Door | Where | Goes to |
|---|---|---|
| Top-bar user menu → **Settings / الإعدادات** | every page, **no role check** | `/system/settings` |
| Top-bar user menu → **Profile / حسابي** | every page | `/auth/profile` |
| Top-bar user menu → **Add a user to this PC** | every page | `/auth/desk/add` |
| Launcher card **Data Migration** | `/` | `/migration/` |
| Launcher card **System Monitor & Diagnostics** | `/` | `/system/monitor` |
| Launcher card **Settings & Configuration** | `/` | `/system/settings` |
| Monitor top bar → **⚡ Sync Dashboard** | `/system/monitor` | `/system/sync` |
| Monitor / Settings top bar → **🔬 Diagnostics** | `/system/monitor`, `/system/settings` | `/system/diagnostics` |
| Monitor → Backup Status → **Export All Data** | `/system/monitor` | `/system/export/all` |
| Profile → Quick Links → **Staff Two-Step Verification** | `/auth/profile` (super_admin, clinic_owner only) | `/auth/2fa/admin` |

`/system/diagnostics`, `/system/sync`, `/system/export/all` and `/auth/2fa/admin`
have **no sidebar entry**. They are reachable only from the buttons above, or by
typing the URL.

`GET /system/` redirects to `/system/monitor`.

> Source: `platform/templates/base.html:444-475`,
> `platform/blueprints/launcher/routes.py:507-554`,
> `platform/templates/system/monitor.html:8-11`,
> `platform/templates/system/settings.html:8-9`,
> `platform/templates/profile.html:178-182`,
> `platform/blueprints/system/routes.py:70-73`

---

## 2. Who can open what

**Two independent gates apply to every screen, and both must pass.**

1. **The module grant.** Every route inside a blueprint is checked against one
   permission key derived from the blueprint name. For the whole `/system`
   blueprint that key is `system`. The grant list comes from
   `roles.permissions_json` in the database.
2. **The route's own role list**, declared with `@role_required(...)`.

`super_admin` bypasses both gates entirely.

A grant can only ever *narrow* access — it never widens it. If the role list on
a route does not include you, holding the grant does not help.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-134` (`_permission_denied`, the module gate), `:154-164`
> (`_permission_for`), `:167-194` (`role_required`)

### What "no usable permission data" means

If a role has no row in the `roles` table, or its `permissions_json` is empty:

* a **built-in** role name falls back to the hardcoded list in
  `DEFAULT_ROLE_PERMISSIONS` — so an upgrade cannot lock a clinic out;
* any **other** name is **denied everywhere**, and a warning is written to the
  server log.

> Source: `platform/blueprints/auth/routes.py:118-128`,
> `platform/blueprints/auth/routes.py:223-279`,
> `platform/models/database.py:4346-4379`

Permission lookups are cached in memory for **60 seconds** per role. Creating,
editing or deleting a role clears that cache immediately; editing
`roles.permissions_json` any other way takes up to a minute to take effect.

> Source: `platform/blueprints/auth/routes.py:212-221`, `:847`, `:897`, `:909`

### Effective access, screen by screen

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| System home (redirect) | `GET /system/` | none (login only) | super_admin, clinic_owner, support_admin |
| System Monitor | `GET /system/monitor` | super_admin, clinic_owner, support_admin | same |
| Audit Log | `GET /system/audit` | super_admin, clinic_owner, support_admin, **auditor** | super_admin, clinic_owner, support_admin — **auditor is blocked by the module gate**, see Known limits |
| Clinic Settings | `GET/POST /system/settings` | super_admin, clinic_owner | same |
| Roles & Permissions | `GET /system/roles` | super_admin, clinic_owner, support_admin | same |
| Staff list (JSON) | `GET /system/roles/users` | super_admin, clinic_owner, support_admin | same |
| Create role | `POST /system/roles/create` | super_admin, clinic_owner | same |
| Edit role | `POST /system/roles/<id>/edit` | super_admin, clinic_owner | same |
| Delete role | `POST /system/roles/<id>/delete` | **super_admin only** | super_admin |
| Assign role to a user | `POST /system/roles/assign` | super_admin, clinic_owner, support_admin | same |
| Backup & Restore page | `GET /system/backup` | super_admin, clinic_owner, support_admin | same |
| Back Up Now | `POST /system/backup/run` | super_admin, clinic_owner, support_admin | same |
| Check a backup | `POST /system/backup/<file>/verify` | super_admin, clinic_owner, support_admin | same |
| Download a backup | `GET /system/backup/<file>/download` | **super_admin, clinic_owner** | same |
| Upload a backup | `POST /system/backup/upload` | **super_admin, clinic_owner** | same |
| Restore | `POST /system/backup/<file>/restore` | **super_admin, clinic_owner** | same |
| Clear maintenance mode | `POST /system/backup/maintenance/off` | **super_admin, clinic_owner** | same |
| Diagnostics | `GET /system/diagnostics` | super_admin, clinic_owner, support_admin | same |
| Sync Dashboard | `GET /system/sync` | super_admin, clinic_owner, support_admin | same |
| Resolve a sync conflict | `POST /system/sync/conflicts/<id>/resolve` | super_admin, clinic_owner, support_admin | **nobody — the form fails CSRF**, see Known limits |
| Export all data | `GET /system/export/all` | **super_admin, clinic_owner** | same |
| My Profile | `GET/POST /auth/profile` | login only | everyone signed in |
| Staff 2FA admin | `GET /auth/2fa/admin` | super_admin, clinic_owner | same |
| Reset someone's 2FA | `POST /auth/2fa/admin/reset/<id>` | super_admin, clinic_owner | same |
| Add a user to this PC | `GET/POST /auth/desk/add` | login only | everyone signed in |
| Switch user on this PC | `POST /auth/desk/switch/<id>` | login only | everyone signed in |
| Sign a user off this PC | `POST /auth/desk/remove/<id>` | login only | everyone signed in |
| Theme switch | `POST /settings/theme` | **none at all** | anyone, signed in or not |
| Language switch | `POST /settings/lang` | **none at all** | anyone, signed in or not |
| Staff list | `GET /hr/staff` | super_admin, clinic_owner, branch_manager, support_admin, hr | same |
| New / edit staff | `GET/POST /hr/staff/new`, `/hr/staff/<id>/edit` | super_admin, clinic_owner, branch_manager, support_admin, hr | same |
| Reset a staff password | `POST /hr/staff/<id>/reset-password` | **super_admin, clinic_owner, support_admin** | same |

> Source: `platform/blueprints/system/routes.py:70-1065` (every `@role_required`
> line), `platform/blueprints/auth/routes.py:701`, `:827-835`, `:899`, `:970`,
> `:1009`, `platform/blueprints/settings/routes.py:107-167`,
> `platform/blueprints/hr/routes.py:459-460`, `:581-582`, `:802-803`, `:852-853`

### Who may hand out which role

Assigning a role is governed by **rank plus a "may manage people" list**, not by
permissions. Four rules are enforced on every write to `users.role` /
`users.is_active`, whether it comes from the Roles screen or the staff form:

1. The role must **exist** (built-in name, or a row in `roles`).
2. You may not grant a role **above your own rank**, and only a `super_admin`
   can create another `super_admin`.
3. You may **never change your own role**, at any rank, and you may not
   deactivate your own account.
4. The **last active `super_admin`** cannot be demoted or deactivated by anyone,
   including themselves.

Ranks: `super_admin` 100, `clinic_owner` 90, `support_admin` 80,
`branch_manager` 70, `hr` 60, `finance` 60, `auditor` 50, everyone else 10.
Only `super_admin`, `clinic_owner`, `support_admin`, `branch_manager` and `hr`
may grant anything at all — an unknown role ranks 0 and grants nothing.

Refusals come back as a red flash message naming the reason.

> Source: `platform/blueprints/auth/routes.py:294-338` (`ROLE_RANK`,
> `ROLE_GRANTERS`, `may_grant_role`), `:341-402` (`guard_role_change`),
> `platform/blueprints/system/routes.py:947-959`,
> `platform/blueprints/hr/routes.py:501-509`

---

## 3. Clinic Settings — `/system/settings`

**What it is for:** the clinic's own identity — the name, logo, licence and
payment details that appear on invoices, certificates and payslips.

**How to reach it:** Sidebar → SYSTEM → Settings, or the top-bar user menu →
Settings, or the launcher card *Settings & Configuration*.

**Who can open it:** `super_admin`, `clinic_owner`. (The top-bar menu link is
shown to everyone; other roles clicking it are bounced to the launcher with
*"You don't have permission to access this page."*)

**Top-bar buttons:** *🖥️ Monitor / المراقبة* → `/system/monitor`;
*🔬 Diagnostics / التشخيص* → `/system/diagnostics`.

It is one long form. **One Save button saves everything on the page.**

### Card 1 — 🏥 Clinic Information / بيانات العيادة

| Field | Name | Required | What it does |
|---|---|---|---|
| Clinic Name (English) / اسم العيادة (إنجليزي) | `name` | **Yes** (browser-side `required` only) | Written to `clinic.name`. Used across the app, invoices and certificates |
| Clinic Name (Arabic) / اسم العيادة (عربي) | `name_ar` | No | `clinic.name_ar`, RTL input |
| Lead Doctor / Owner / الطبيب المسؤول | `doctor_name` | No | `clinic.doctor_name` |
| Phone Number / رقم الهاتف | `phone` | No | `clinic.phone` |
| Email Address / البريد الإلكتروني | `email` | No | `clinic.email` |
| Website / الموقع الإلكتروني | `website` | No | `clinic.website` |
| Tagline / الشعار النصي | `tagline` | No | `clinic.tagline`. Shown beside the clinic name |
| Address (English) / العنوان (إنجليزي) | `address` | No | `clinic.address`, textarea |
| Address (Arabic) / العنوان (عربي) | `address_ar` | No | `clinic.address_ar`, RTL textarea |
| License Number / رقم الترخيص | `license_number` | No | `clinic.license_number` |
| Tax / VAT Number / الرقم الضريبي | `tax_number` | No | `clinic.tax_number` |

### Card 2 — 🖼️ Clinic Logo / شعار العيادة

Shows the current logo in a preview frame, or *No logo yet / لا يوجد شعار بعد*.

| Control | Name | What it does |
|---|---|---|
| Upload a New Logo / رفع شعار جديد | `logo` (file) | PNG, JPEG, GIF or WebP. Rejected above **2 MB**. The file type is checked by reading the first bytes, not the extension. The image is decoded, scaled so its longest side is **400 px**, re-encoded as PNG and stored as a `data:` URI in `clinic.logo_data` |
| Remove the current logo when saving / حذف الشعار الحالي | `remove_logo` (checkbox) | Only appears when a logo exists. Sets `clinic.logo_data` to NULL |

The logo lives **inside the database row**, not on disk, so it survives a backup
and restore. It appears on invoices, vaccination certificates and payslips.

If the image is rejected, a red flash names the reason ("Image is too large.
Maximum 2 MB.", "That file is not a PNG, JPEG, GIF or WebP image.", "That image
could not be read. Try re-saving it as a PNG.") and **nothing else on the page
is saved** — the whole submission is abandoned.

### Card 3 — 💳 Instapay / إنستاباي

Shows the current QR in a preview frame, or *No QR yet / لا يوجد كود بعد*.

| Control | Name | What it does |
|---|---|---|
| Instapay address / عنوان إنستاباي | `instapay_handle` | `clinic.instapay_handle`. Whitespace trimmed |
| Instapay payment link / رابط الدفع | `instapay_link` | `clinic.instapay_link`. Whitespace trimmed |
| Upload your Instapay QR / رفع كود إنستاباي | `instapay_qr` (file) | Same validation as the logo, but scaled to **800 px** so it still scans. Stored in `clinic.instapay_qr` |
| Remove the current QR when saving | `remove_instapay_qr` (checkbox) | Only appears when a QR exists. Sets `clinic.instapay_qr` to NULL |

### Card 4 — 🌍 Preferences / التفضيلات

| Field | Name | Options |
|---|---|---|
| Currency / العملة | `currency` | EGP, USD, EUR, GBP, SAR, AED (default EGP) |
| Timezone / المنطقة الزمنية | `timezone` | Africa/Cairo, UTC, Asia/Riyadh, Asia/Dubai, Europe/London, America/New_York |

Both are stored in the `clinic` row. **Neither is read anywhere else in the
application** — see Known limits.

### Card 5 — 🎨 Appearance / المظهر

| Field | Name | Options |
|---|---|---|
| Default Theme / الوضع الافتراضي | `default_theme` | Medical (White / Navy / Gold), Logo (Navy / Yellow / Blue) |
| Default Language / اللغة الافتراضية | `default_language` | English, Arabic (عربي) |

These two are written to the `settings` table (`category='appearance'`, stamped
with the saving user's username). **Nothing reads them back** — see Known limits.

### Save

**💾 Save All Settings / حفظ كل الإعدادات** writes the `clinic` row and the two
appearance rows, invalidates the 5-minute clinic cache so the new name appears
immediately, writes an audit entry (`module=system`, `entity_type=clinic`,
`action=update`, details "Updated clinic settings"), and flashes
*"Settings saved successfully."* On any database error it flashes
*"Error saving settings: …"* instead.

> Source: `platform/blueprints/system/routes.py:325-415`,
> `platform/blueprints/settings/routes.py:36-104` (`encode_logo`,
> `LOGO_MAX_UPLOAD`, `LOGO_MAX_PX`, `QR_MAX_PX`),
> `platform/templates/system/settings.html:47-254`,
> `platform/models/database.py:1110-1133` (clinic columns), `:1193-1199`
> (settings table), `:2883-2893` (`get_clinic`, 5-minute cache)

---

## 4. Roles & Permissions — `/system/roles`

**What it is for:** deciding which modules each role may enter, and putting
staff on roles.

**How to reach it:** Sidebar → SYSTEM → Roles & Permissions.

**Who can open it:** `super_admin`, `clinic_owner`, `support_admin`.

**Top-bar button:** *+ New Custom Role / + دور مخصص جديد* opens the create modal.
It is shown to all three roles, but only `super_admin` and `clinic_owner` can
actually submit it.

The page has two tabs: **Roles & Permissions / الأدوار والصلاحيات** and
**Staff Access / صلاحيات الموظفين**.

### Tab 1 — Roles & Permissions

Roles are listed in department sections. Each row shows:

| Element | Meaning |
|---|---|
| Coloured dot | The role's badge colour |
| Bold name, then a grey Arabic name | Display name (EN), display name (AR) |
| Small monospace line under it | The role **key** — the value actually stored in `users.role` |
| `N users` pill | Count of rows in `users` with that role, **active and inactive together** |
| `N perms` pill | Number of permission keys in the list this row is showing |
| `built-in / مدمج` badge | Present on the hardcoded department cards |
| `▼` chevron | Expands the row |

Clicking a row expands it and renders **all 25 permission keys**, each as a green
`✓ <label>` tag when granted or a faded `— <label>` when not. Only one row is
open at a time.

**Sections and their hardcoded cards:**

| Section | Roles shown |
|---|---|
| Management / الإدارة | Super Admin, Clinic Owner, Branch Manager |
| Clinical / السريري | Doctor / Vet, Nurse |
| Front Desk / الاستقبال | Receptionist |
| Pharmacy & Stock / الصيدلية والمخزون | Pharmacist |
| Services / الخدمات | Groomer |
| System & IT / النظام وتقنية المعلومات | HR, Support Admin |
| Custom Roles (N) | **every row in the `roles` table** |

The department cards are **read-only**. Their footer says *"System roles are
enforced in code and cannot be modified."* and they carry no buttons. The
permission list they display comes from a hardcoded table in the route file,
which is **not** what the system enforces — see Known limits.

Rows under **Custom Roles** carry:

| Button | Who sees it | Effect |
|---|---|---|
| **Edit Role / تعديل الدور** | everyone who can open the page | Opens the edit modal |
| **Delete / حذف** | `super_admin` only | Browser confirm "Delete role *name*?", then `POST /system/roles/<id>/delete` |

Because the `roles` table is seeded with all fourteen built-in roles, every
built-in role also appears here — see Known limits.

### The "New Custom Role" modal

| Field | Name | Required | Notes |
|---|---|---|---|
| Role Key * / مفتاح الدور | `name` | **Yes** | Browser pattern `[a-z0-9_]+`. The server lowercases it and replaces spaces with underscores |
| Display Name (EN) * / الاسم المعروض (إنجليزي) | `display_name` | **Yes** | |
| Display Name (AR) / الاسم المعروض (عربي) | `display_name_ar` | No | RTL input |
| Badge Color / لون الشارة | `color` | No | Colour picker, default `#1a3a6b` |
| Permissions / الصلاحيات | `permissions` | No | 25 checkboxes, one per permission key |

**Create Role / إنشاء دور** inserts the row, clears the permission cache, writes
an audit entry (`action=create_role`) and flashes *"Role 'X' created
successfully."* Missing key or display name flashes *"Role name and display name
are required."* A duplicate key fails at the database and flashes
*"Error creating role: …"*.

**Cancel / إلغاء** and the `×` close the modal. `Esc` closes any open modal.

### The "Edit Custom Role" modal

Same fields, except **Role Key is disabled** — a key cannot be changed after
creation. The permission checkboxes are pre-ticked from the role's stored list.

**Save Changes / حفظ التغييرات** posts to `/system/roles/<id>/edit`. It:

* refuses an empty display name — *"Display name is required."*;
* **refuses to save a role with no permissions at all** —
  *"A role must grant at least one module. To stop this role being used at all,
  move its staff to another role and delete it."*;
* otherwise writes the row, records a **field-level audit diff** showing the
  permission list before and after, clears the permission cache, and flashes
  *"Role updated successfully."*

### Deleting a role

`POST /system/roles/<id>/delete` **refuses while any active user still holds the
role** and names up to ten of them:
*"N staff member(s) still hold this role: a, b, c. Move them to another role
first."* Only after the last holder is moved does the delete succeed and flash
*"Role deleted."*

### Tab 2 — Staff Access / صلاحيات الموظفين

Loaded lazily the first time the tab is clicked, from
`GET /system/roles/users`, which returns **at most 300 users** ordered by full
name (id, username, full_name, role, is_active). All filtering and paging below
happens in the browser, on that 300-row set.

**Filters (all client-side, applied as you type/change):**

| Control | What it filters |
|---|---|
| Search name or username… / ابحث بالاسم أو اسم المستخدم | Substring match on full name + username, case-insensitive |
| Role dropdown | Exact match on `users.role`. Options: ten hardcoded built-in keys, then every row in `roles` labelled "*display name* (custom)" |
| Status dropdown | Any status / Active / Inactive |
| Grey counter on the right | "N staff members" after filtering |

**Table columns:**

| Column | Content |
|---|---|
| Staff Member / الموظف | Two-letter initials avatar + full name (falls back to username) |
| Username / اسم المستخدم | Monospace |
| Current Role / الدور الحالي | The raw role key in a pill |
| Status / الحالة | ● Active (green) or ● Inactive (red) |
| Assign Role / تعيين دور | A dropdown pre-set to the current role, plus a **Save** button |

**Save** posts `user_id` and `role` to `/system/roles/assign`. That route:

* refuses a role that does not exist — *"There is no role called 'x'. Pick one
  that exists, or create it first."*;
* applies the full [role-change guard](#who-may-hand-out-which-role) — self-
  promotion, over-rank grants and demoting the last super admin are all refused
  with a red flash;
* on success writes `users.role`, audits it (`action=assign_role`,
  `entity_type=user`) and flashes *"Role assigned successfully."*

Paging: 25 rows per page, with `‹ 1 2 3 … ›` buttons and an
"1–25 of N" counter. The pager disappears when there is only one page.

### The 25 permission keys

| Key | Label on screen |
|---|---|
| `patients` | Manage Patients & Owners |
| `appointments` | Manage Appointments |
| `visits` | Medical Visits & SOAP |
| `pharmacy` | Pharmacy & Dispensing |
| `invoicing` | Invoicing & Payments |
| `inventory` | Inventory & Stock |
| `procurement` | Procurement & Purchasing |
| `reports` | Reports & Analytics |
| `whatsapp` | WhatsApp Messaging |
| `catalog` | Service Catalog |
| `grooming` | Grooming |
| `boarding` | Boarding |
| `hr` | HR & Staff |
| `attendance` | Attendance & Leave |
| `accounting` | Accounting |
| `ai` | AI Assistant |
| `system` | System Admin |
| `backup` | Backup & Restore |
| `audit` | Audit Log |
| `settings` | Platform Settings |
| `payroll` | Payroll & Salaries |
| `inpatient` | Inpatient & Hospitalisation |
| `telemedicine` | Telemedicine |
| `imaging` | Imaging & Radiology |
| `petshop` | Pet Shop & Retail |

A key governs a whole blueprint, matched by blueprint name, with these
exceptions: `crm`→`patients`, `finance`→`invoicing`, `ai_assistant`→`ai`,
`clinical`→`visits`, `doctor`→`visits`, `workflow`→`visits`, `petsy`→`petshop`.
Blueprints with no matching key (`launcher`, `notifications`, `uploads`,
`migration`, `cds`, `api_v1`, `public_api`) are **not governed by any checkbox**
— they rely on their own route role lists.

### Default grants shipped with a new clinic

| Role | Keys granted out of the box |
|---|---|
| `super_admin` | *(bypasses the check entirely)* |
| `clinic_owner` | all 25 |
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

These are only a **starting point**. They are written into
`roles.permissions_json` on first start, and **only for roles whose list is
still empty**, so an administrator's own edits are never overwritten.

> Source: `platform/blueprints/system/routes.py:771-968`,
> `platform/templates/system/roles.html:137-551`,
> `platform/models/database.py:4302-4331` (`ALL_PERMISSIONS`), `:4346-4379`
> (`DEFAULT_ROLE_PERMISSIONS`), `:4382-4397` (`seed_default_permissions`),
> `:4400-4492` (`list_roles`, `create_role`, `update_role`, `role_holders`,
> `delete_role`, `assign_user_role`), `:2435-2450` (`_SEED_ROLES`),
> `platform/blueprints/auth/routes.py:140-164` (`_BP_PERMISSION`)

---

## 5. Staff accounts — `/hr/staff`

User accounts are **not** created on the System screens. They live under HR. Only
the access-control parts are documented here; the rest of the staff record
belongs to the HR chapter.

**Who can open the list and the form:** `super_admin`, `clinic_owner`,
`branch_manager`, `support_admin`, `hr`.

### Staff list — `GET /hr/staff`

**Filters (all in the query string, applied server-side):**

| Filter | Parameter | Values |
|---|---|---|
| Status | `status` | `active` (**the default**), `inactive`, anything else = both |
| Role | `role` | Exact match on `users.role` |
| Contract | `contract` | Exact match on `users.contract_type` |
| Search | `q` | Case-insensitive substring on full name, username, email, job title |

Rows are ordered by full name. Each row joins the branch name from `branches`.

### New / Edit staff — `/hr/staff/new`, `/hr/staff/<id>/edit`

Access-relevant fields on the form:

| Field | Name | Required | Notes |
|---|---|---|---|
| Username / اسم المستخدم | `username` | **Yes**, on create only | Not editable afterwards — the edit path never writes it |
| Password / كلمة المرور | `password` | **Yes**, on create only | Must pass the full password policy: **12+ characters, one uppercase, one lowercase, one digit, one special character**. The placeholder on the form says "Min 6 characters" — it is wrong, see Known limits |
| Confirm Password | `confirm_password` | **Yes**, on create only | Must match, else *"Passwords do not match."* |
| Role * / الدور | `role` | **Yes** | Dropdown of 13 hardcoded keys. Runs through the role-change guard |
| Branch / الفرع | `branch_id` | No | "— No Branch —" plus every **active** row in `branches` |
| Work Shift / المناوبة | `shift_id` | No | "— No Shift —" plus every active shift. On edit, only written when the field is present in the submission |
| Active / نشط | `is_active` | checkbox | Unchecked = 0. Runs through the role-change guard (you cannot deactivate yourself; you cannot deactivate the last super admin) |

The role dropdown offers: super_admin, clinic_owner, branch_manager, doctor,
nurse, reception, inventory_mgr, pharmacist, finance, groomer, boarding_staff,
support_admin, auditor. **`hr` and every custom role are missing** — see
Known limits.

Success on create audits `action=create`, `module=hr`, `entity_type=user` and
flashes *"Staff member 'x' created successfully."* Success on edit audits
`action=update` and flashes *"Staff member updated successfully."*

### Reset a password — `POST /hr/staff/<id>/reset-password`

Available on the staff detail page to `super_admin`, `clinic_owner`,
`support_admin` only. Field `new_password` must pass the same 12-character
policy; failures flash the exact rule that was broken. Success writes the hash,
audits `action=reset_password`, and flashes *"Password reset successfully."*

> Source: `platform/blueprints/hr/routes.py:20-24` (`_ROLES`), `:459-492`
> (staff list + filters), `:501-566` (`_save_staff_fields`, the guard and the
> password check), `:569-576` (branches and shifts for the form), `:581-639`
> (create), `:802-847` (edit), `:852-879` (password reset),
> `platform/templates/hr/staff_form.html:45-181`,
> `platform/models/security.py:346-367` (password policy)

---

## 6. Two-Step Verification, staff view — `/auth/2fa/admin`

**What it is for:** seeing who has 2FA switched on, and turning it off for
someone who lost their phone.

**How to reach it:** `/auth/profile` → Quick Links → *🔐 Staff Two-Step
Verification*. The link is only rendered for `super_admin` and `clinic_owner`.
There is no sidebar entry.

**Who can open it:** `super_admin`, `clinic_owner`.

Lists **every active user** ordered by username.

| Column | Content |
|---|---|
| User / المستخدم | Username, with full name underneath when set |
| Role / الدور | The role key |
| Two-Step / خطوتان | ✅ On / مفعّل, or — Off / غير مفعّل |
| Enabled On / تاريخ التفعيل | `totp_confirmed_at` |
| *(last column)* | **Reset / إعادة الضبط** button, only on rows where 2FA is on |

**Reset** asks "Turn off two-step verification for this user?", then posts to
`/auth/2fa/admin/reset/<id>`. It disables TOTP for that account, writes an audit
entry naming who reset whom, and flashes
*"Two-factor authentication reset for X. They can log in with their password and
enrol again."* If the id is not an active user it flashes *"No such active
user."*

The page carries a standing note that every reset is recorded in the audit log.

> Source: `platform/blueprints/auth/routes.py:827-853`,
> `platform/templates/auth/2fa_admin.html:13-70`,
> `platform/models/security.py:724-736` (`list_totp_users`),
> `platform/templates/profile.html:178-182`

---

## 7. My Profile — `/auth/profile`

**What it is for:** the signed-in user's own theme, language and two-step
verification.

**Who can open it:** everyone signed in — it serves only your own record.

### Account Profile card

Full Name, Username and Role are shown **disabled** (display only).

| Field | Name | Effect |
|---|---|---|
| Platform Theme / مظهر المنصة | `theme` radio | Only one option exists: **⚕️ Medical / طبي (White · Navy · Gold)**. Saved to `users.theme_preference` and the session |
| Language / اللغة | `lang` select | 🇬🇧 English or 🇸🇦 العربية. Saved to the **session only** — see Known limits |

**Save Preferences / حفظ التفضيلات** flashes *"Profile updated."*

### Two-Step Verification card

The card shows one of four states.

**Off.** *"Off. Your password alone signs you in."* with a
**Set Up Two-Step Verification / إعداد التحقق بخطوتين** button. Pressing it
generates a **new secret every time**, so an abandoned half-setup cannot be
resumed by anyone else, and reloads the page in setup mode.

**Setup in progress.** Three numbered instructions, a QR code image, the secret
in a click-to-select read-only box, and a 6-digit **Code from your app / الرمز من
التطبيق** field with a **Turn On Two-Step Verification** button. A wrong code
flashes *"That code was not accepted. Check your phone's clock is correct and
try the current code."* A correct code enables 2FA, audits it, and renders the
backup codes.

**Backup codes shown.** Rendered exactly once, never recoverable afterwards, with
the warning *"Save these backup codes now"* / *"Each code works once… They will
not be shown again."*

**On.** Shows ✅ On plus "*N* backup codes left", and a password box with two
buttons:

| Button | Effect |
|---|---|
| **Generate New Backup Codes / إنشاء رموز احتياط جديدة** | Requires the current password. Replaces all codes and shows the new set once |
| **Turn Off / الإيقاف** | Requires the current password. Disables 2FA and flashes *"Two-factor authentication is now off."* |

Both flash *"Current password is incorrect."* on a bad password.

**Unavailable.** If the server lacks the TOTP libraries:
*"Not available on this server yet. Ask your administrator."*

### Quick Links card

Module Launcher, Examination Module, Staff Two-Step Verification (super_admin /
clinic_owner only), Logout.

> Source: `platform/blueprints/auth/routes.py:701-807`,
> `platform/templates/profile.html:1-185`

---

## 8. The shared desk — `/auth/desk/add`

**What it is for:** up to **five** people stay signed in on one reception PC and
switch between them in one click, so "recorded by" names the right person.

**How to reach it:** top-bar user menu → *Add a user to this PC*.

**Who can open it:** everyone signed in.

The page lists who is already signed in on this PC, marking the one
*"— using this screen now"*, each with a **Sign off / تسجيل خروج** button.

| Field | Name | Required |
|---|---|---|
| Username / اسم المستخدم | `username` | Yes |
| Password / كلمة المرور | `password` | Yes |

**Sign in on this PC / تسجيل الدخول على هذا الجهاز** runs the **full**
credential check, the same rate limit and the same lockout as the normal login.
It refuses when:

* five people are already on the desk — *"This PC already has 5 people signed in.
  Sign one off first."*;
* the credentials are wrong — *"Invalid username or password."* (and the attempt
  is audited as `desk_add_failed`);
* the rate limit is active — *"Too many failed attempts. Try again in N
  minute(s)."*;
* **the account uses two-factor authentication** — *"This account uses two-factor
  authentication, so it cannot be added to a shared PC. Sign in to it directly
  instead."*

On success it adds the person to the desk **without** handing them the screen —
the active user does not change — audits `desk_add`, and flashes
*"X is now signed in on this PC."*

### Switching and signing off

**Switch** (`POST /auth/desk/switch/<id>`, from the top-bar menu) takes no
password. The role, active flag and clinic are **re-read from the database on
every switch**, so a deactivated or re-roled account takes effect immediately: an
inactive account is removed from the desk with *"That account is no longer
active. It has been removed from this PC."* Every switch is audited as
`desk_switch`.

**Sign off** (`POST /auth/desk/remove/<id>`) removes one person. If that person
was the active user, the next one on the desk takes over; if nobody is left, the
session is cleared and you land on the login page.

**The trade-off, stated on the page:** anyone standing at that PC can act as any
of the five without a password.

> Source: `platform/blueprints/auth/routes.py:856-1040`,
> `platform/templates/auth/desk_add.html:13-70`,
> `platform/templates/base.html:456-480`

---

## 9. Backup & Restore — `/system/backup`

**What it is for:** the one page that answers "is there a recent copy of our
records, and how do I get it back".

**How to reach it:** Sidebar → SYSTEM → Backup Manager, or Monitor → Backup
Status → *All Backups*.

**Who can open it:** `super_admin`, `clinic_owner`, `support_admin`.

Opening the page also **runs a health check and alerts managers** if the backup
is missing or stale — because a page view is the one thing that still happens
when the nightly scheduler has quietly died.

**Top-bar buttons:** *← Monitor / ← المراقبة*; **💾 Back Up Now / انسخ احتياطياً
الآن**.

### Maintenance banner

If a maintenance marker is present, a warning banner appears at the top:
*"The system is in maintenance mode."* plus the reason, how many minutes ago it
started, and *"Staff cannot use the platform until it clears."* It carries a
**Clear maintenance mode / إلغاء وضع الصيانة** button (`super_admin`,
`clinic_owner` only), which deletes the marker, audits
`maintenance_cleared` and flashes *"Maintenance mode cleared. The system is
serving again."*

A marker older than **15 minutes** clears itself automatically.

### Headline card — Last successful backup / آخر نسخة احتياطية ناجحة

Green left border when healthy, red when stale. Shows either:

* **"N hours ago"** (under 24 h) or **"N days ago"**, then the timestamp,
  filename and size in MB; or
* **"Never / أبداً"** with the red banner *"This server has no backup at all. If
  the disk fails today, every record is lost. Press 'Back Up Now'."*

Anything older than **2 days** (`BACKUP_STALE_DAYS`, default 2) is "stale" and
adds the red banner *"Backups appear to have stopped… Press 'Back Up Now', and
if it fails, call your IT support today."*

### Three summary cards

| Card | Content |
|---|---|
| **Copies kept / النسخ المحفوظة** | Count of archives in this clinic's backup folder, with the caption "30-day retention · daily at 02:00" |
| **Off-site copy / نسخة خارج الموقع** | Each configured target (📁 folder or ☁️ S3) — or, in amber, **"None configured / غير مُعدّة"** with *"Backups sit on the same disk as the database. One disk failure loses both. See deploy/BACKUP_RUNBOOK.md."* Off-site targets come from the `BACKUP_OFFSITE_DIR` and `BACKUP_S3_BUCKET` environment variables, not from any screen |
| **Restore from USB / استعادة من ذاكرة USB** | A file picker (`.db`, `.dump`) and an **Upload backup file / رفع ملف النسخة** button |

### Available backups table

| Column | Content |
|---|---|
| Date & time / التاريخ والوقت | Timestamp to the minute, with "N h ago" or "N days ago" underneath |
| File / الملف | The archive filename |
| Size / الحجم | MB, right-aligned |
| Type / النوع | **Automatic / تلقائي** (`platform_backup_*`), **Safety snapshot / لقطة أمان** (`pre_restore_*`), or **Uploaded / مرفوع** (`uploaded_*`) |
| Actions / إجراءات | Download, Check, Restore |

Empty state: *"No backups yet. Press 'Back Up Now' to make the first one."*

### The buttons

**💾 Back Up Now / انسخ احتياطياً الآن** (`POST /system/backup/run`) — creates a
timestamped archive of **this clinic's** database, then purges archives older
than **30 days**, then copies to every off-site target. On success it audits
`manual_backup` and flashes *"Backup completed: filename (N KB)"*. A failed
off-site copy adds a second, red flash: *"Off-site copy to X FAILED: … The local
backup is fine, but there is no second copy."* A failed backup flashes
*"Backup failed: …"* and notifies the managers. It refuses outright while a
restore is running.

**⬇ Download / ⬇ تنزيل** (`GET .../download`) — sends the file as an attachment,
audits `backup_download`.

**✓ Check / ✓ فحص** (`POST .../verify`) — reads the archive **without restoring
it**. For SQLite it rejects a file under 512 bytes, one without the
`SQLite format 3` header, one failing `PRAGMA integrity_check`, or one with no
tables. For PostgreSQL it runs `pg_restore --list` and requires table data.
Flashes *"filename is readable and complete."* or
*"filename is NOT usable: <reason>"*.

**Upload backup file / رفع ملف النسخة** (`POST /system/backup/upload`) — accepts
only `.db` or `.dump`. The stored name is **generated by the server**, never
taken from the upload. The file is **verified before it is kept**; a bad file is
deleted and the page says *"That file is not a usable backup (<reason>). It was
not kept."* The upload limit is raised to **2 GB** for this route only. Choosing
no file flashes *"Choose a backup file first."*

**↺ Restore / ↺ استعادة** — opens a confirmation dialog, it does not restore
directly.

### The restore dialog

Titled *⚠️ Read this before you restore / اقرأ هذا قبل الاستعادة*, it states
which backup date you are about to restore to and lists three consequences:

* every visit, invoice, payment and prescription entered **since that date will
  be gone**;
* staff will be locked out of the system for a few minutes;
* a safety snapshot of the current data is taken first, so this can be undone.

**Type the file name to confirm / اكتب اسم الملف للتأكيد** — the exact filename
is displayed above a text box, and you must type it. Typing anything else
cancels: *"Restore cancelled — the filename you typed did not match."*

**Restore and lose newer data / استعادة وفقدان البيانات الأحدث** runs, in this
order:

1. verify the archive — anything unreadable is refused, *nothing is changed*;
2. refuse if the archive's engine does not match the server's
   (*"That backup came from a different database engine than this server runs."*);
3. maintenance mode ON;
4. **snapshot the current database** as `pre_restore_*` — if the snapshot fails,
   nothing is overwritten;
5. restore;
6. maintenance mode OFF.

Success flashes *"Database restored from X. Your previous data was saved as
pre_restore_… — restore that file to undo this."* and audits `backup_restore`.
A restore already in progress is refused: *"Another restore is already running.
Wait for it to finish."*

**Cancel / إلغاء**, clicking the backdrop, or `Esc` closes the dialog.

### What "maintenance mode" does to everyone else

While the marker is present, every request outside `/static/`, `/auth/` and
`/system/backup*` gets a **503** page reading *"Maintenance in progress: …. The
system will be back in a few minutes."* A request already inside a view is not
interrupted.

> Source: `platform/blueprints/system/routes.py:33-67` (the maintenance gate),
> `:418-438` (`_archive_or_abort` — a bad name is a 400, a missing file a 404),
> `:453-573` (all six backup routes),
> `platform/templates/system/backup.html:6-238`,
> `platform/models/backup.py:45-63` (`RETENTION_DAYS=30`,
> `STALE_AFTER_DAYS`, `MAINTENANCE_MAX_MINUTES=15`), `:185-208`
> (`resolve_archive`), `:215-258` (maintenance marker), `:377-404`
> (`run_backup`), `:439-472` (`list_backups`), `:484-541` (verification),
> `:561-633` (`restore_backup`), `:636-674` (`accept_upload`), `:681-693`
> (`offsite_targets`), `:800-876` (`health`, `check_and_notify`)

---

## 10. System Monitor — `/system/monitor`

**What it is for:** production health at a glance.

**Who can open it:** `super_admin`, `clinic_owner`, `support_admin`.

**Top-bar buttons:** *⚡ Sync Dashboard*, *🔬 Diagnostics*, *📋 Audit Log*,
*↻ Refresh*. **The page reloads itself every 60 seconds.**

### The eight stat cards

Database Size (MB) · Synced Records · Pending Sync · Sync Failures (caption "max
5 retries") · Conflicts · Errors (24h) · Active Devices · Log Files.

"Errors (24h)" counts `backend_logs` rows at level ERROR or CRITICAL in the last
24 hours. "Active Devices" counts devices with `last_online_at` inside the last
hour.

### ⚡ Sync Queue

Four mini-cards — Pending, Synced, Failed, Conflicts — and an
**Open Dashboard → / فتح اللوحة ←** button.

### 🚀 Platform Version

Version, Build, Release Date, Python, Flask, Platform. These come from the
`APP_VERSION`, `BUILD_NUMBER` and `RELEASE_DATE` environment variables, falling
back to `1.0.0`, `production_final_v1`, `2026-05-24`.

### 🗄️ Database

Size in MB and KB, the database path (truncated to 42 characters), then
**Records by Module** — live `COUNT(*)` for owners, pets, appointments, visits,
invoices, items, users, reminders, whatsapp_log, audit_log, batches, payments.
A table that cannot be read shows 0 rather than failing the page.

### 💾 Backup Status

Buttons: **All Backups / جميع النسخ** → `/system/backup`;
**Export All Data / تصدير كل البيانات** → `/system/export/all`;
**💾 Now / 💾 الآن** → runs a backup after a browser confirm "Run backup now?".

Rows: Last Backup, File, Size, Integrity. **Last Backup and Integrity are always
blank / "?"** — see Known limits.

Footer caption: *"Schedule: Backup 02:00 · WhatsApp 09:00 · Log cleanup 03:00
UTC"*.

### 📁 Log Files

Up to ten `.log` files from `<database folder>/logs/backend`, newest first, each
with size, age and days until expiry. Retention comes from
`LOG_FILE_RETENTION_DAYS` (default **7**).

### 📱 Registered Devices

Online in the last hour, total registered, and a link through to the sync
dashboard.

### 📝 Recent Server Logs

The most recent **25** rows of `backend_logs` (falling back to `app_logs`),
with columns Time, Level, Module, Endpoint, Status, ms, User, Error.

### 🔗 Legacy App Status

Shown **only when `LEGACY_APP_ENABLED` is on**. Displays `LEGACY_APP_URL` and a
**Check Status / فحص الحالة** button that fetches it from the browser and reports
"Reachable" or "Unreachable".

> Source: `platform/blueprints/system/routes.py:76-228`,
> `platform/templates/system/monitor.html:145-420`

---

## 11. Diagnostics — `/system/diagnostics`

**What it is for:** eight pass/warn/fail health checks.

**How to reach it:** Monitor or Settings top bar → *🔬 Diagnostics*. No sidebar
entry.

**Who can open it:** `super_admin`, `clinic_owner`, `support_admin`.

**Buttons:** *🔄 Re-run Diagnostics* (reloads the page — the checks run on every
load), *🖥️ Monitor*, *⚙️ Settings*, *🔍 Test Connectivity*.

A banner at the top reads **All Systems Operational / جميع الأنظمة تعمل** (green),
*"Platform is operational but some items need attention."* (amber) or
*"Review the failed checks below and take corrective action."* (red), above four
counters: Total Checks, Passed, Warnings, Failed.

The results table has columns **# · Check / الفحص · Status / الحالة · Details /
التفاصيل**, with ✓ Pass / ✗ Fail / ⚠ Warning.

| # | Check | Passes when | On PostgreSQL it instead |
|---|---|---|---|
| 1 | Database File Writable | The SQLite file can be opened for append | **Database Server Reachable** — `SELECT version()` succeeds |
| 2 | Database Integrity (PRAGMA) | `PRAGMA integrity_check` returns `ok` | **Database Integrity** — the server answers a read |
| 3 | Database Tables | **30 or more** tables exist (fewer = Warning) | counts `information_schema.tables` |
| 4 | Super Admin User Exists | At least one active `super_admin` | same |
| 5 | Clinic Record | At least one row in `clinic` | same |
| 6 | Legacy App Directory | `LEGACY_APP_DIR` is set and exists (missing or unset = Warning) | same |
| 7 | Python Version | Always passes; reports the version | same |
| 8 | Static Folder | The static folder exists on disk | same |

If the database connection itself fails, a single **Database Connection — Fail**
row replaces checks 2–5.

Below the table, **🔗 Live Legacy App Connectivity** shows `LEGACY_APP_URL` and a
browser-side connectivity test.

> Source: `platform/blueprints/system/routes.py:576-654`,
> `platform/templates/system/diagnostics.html:50-145`

---

## 12. Audit Log — `/system/audit`

**What it is for:** who changed what, and when.

**How to reach it:** Sidebar → SYSTEM → Audit Log, or Monitor → *📋 Audit Log*.

**Who can open it:** `super_admin`, `clinic_owner`, `support_admin` in practice
(the route also names `auditor`, but that role cannot get past the module gate —
see Known limits).

**Top-bar buttons:** *🖥️ Monitor*, *⚙️ Settings*.

### Filters

| Filter | Parameter | Control |
|---|---|---|
| User / المستخدم | `user` | Dropdown of every distinct username in the log. Exact match |
| Module / الوحدة | `module` | Dropdown of every distinct module. Exact match |
| Action / الإجراء | `action` | Free text, **substring** match. Placeholder "e.g. update, delete" |
| Record type / نوع السجل | `entity_type` | Dropdown of every distinct entity type. Exact match |
| Record ID / رقم السجل | `entity_id` | Free text, exact match. Placeholder "e.g. 1042" |
| From date / من تاريخ | `date_from` | Date picker; matched from 00:00:00 that day |
| To date / إلى تاريخ | `date_to` | Date picker; matched to 23:59:59 that day |

**🔍 Filter / تصفية** submits. **✕ Clear / مسح** returns to the unfiltered page.

Above the table: *"Showing X–Y of N entries"*.

### Columns

| Column | Content |
|---|---|
| Time / الوقت | Timestamp to the minute |
| User / المستخدم | Username, with the role underneath (underscores replaced by spaces) |
| Action / الإجراء | Coloured badge — **red** for anything containing "delete" or "fail", **green** for "create" or "login", **amber** for "edit" or "update" |
| Module / الوحدة | The module name |
| Record / السجل | `entity_type #id` as a link. **Clicking it re-filters the page to that one record's whole history** |
| What changed / ما الذي تغيّر | A field-by-field diff (`old → new`, `←` in Arabic), with blank values shown as *empty / فارغ*. Older entries that carry only a sentence show the sentence instead |
| IP / عنوان الشبكة | The client IP |

### Paging

**50 entries per page**. The pager offers « First / Previous / "Page N / M" /
Next / Last », and preserves the active filters. Empty state: 📭 *"No audit
entries found"* / *"Try widening the filters or the date range."*

The page never selects the whole table — one page plus a count, no more.

> Source: `platform/blueprints/system/routes.py:231-322` (`AUDIT_PAGE_SIZE=50`),
> `platform/templates/system/audit_log.html:37-205`

---

## 13. Sync Dashboard — `/system/sync`

**What it is for:** the offline queue, conflicts and the device registry.

**How to reach it:** Monitor top bar → *⚡ Sync Dashboard*. No sidebar entry.

**Who can open it:** `super_admin`, `clinic_owner`, `support_admin`.

**Top-bar buttons:** *← System Monitor*, *↻ Refresh*.

Four chips at the top: Pending, Synced, Failed, Conflicts.

### Conflicts

Up to **50** rows where `resolution_status='PENDING'`, newest first. Each shows
the **Device version (local) / نسخة الجهاز** and the **Server version (current) /
نسخة الخادم** side by side, with two buttons:

| Button | Intended effect |
|---|---|
| **Keep Local / الاحتفاظ بالمحلية** | Closes the conflict marked KEPT LOCAL. **The server record is not changed** — the device's version is stored on the conflict for someone to copy across by hand. The flash message says so explicitly |
| **Keep Server / الاحتفاظ بالخادم** | Keeps the server version; flashes *"Conflict resolved — the server version is kept."* |

**Neither button currently works** — both forms send the CSRF token under the
wrong field name and are rejected with a 403 page. See Known limits.

Empty state: *"No unresolved conflicts — everything is in sync."*

### Sync queue

Filters: **Status**, **Device**, **Entity** dropdowns, a **Filter / تصفية**
button and a **Clear / مسح** link. Shows the **last 100** items, newest first.

Columns: Time · Status · Entity · Operation · Device · User · Retries ·
Payload (a **View / عرض** toggle) · Error.

### Registered devices

Up to **50** devices ordered by last-online. Each card shows Platform, App
Version, User ID, Last Online, Last Sync, Registered. Caption: *"Active = seen
within 1 hour"*. Empty state: *"No devices registered yet — appear when offline
sync first connects."*

> Source: `platform/blueprints/system/routes.py:661-764`,
> `platform/templates/system/sync.html:145-345`

---

## 14. Export all data — `/system/export/all`

**What it is for:** one file containing everything, readable without this
software.

**How to reach it:** Monitor → Backup Status → **Export All Data / تصدير كل
البيانات**. No sidebar entry.

**Who can use it:** `super_admin`, `clinic_owner`.

It streams a ZIP named `aleefy-data-YYYY-MM-DD.zip` containing **one CSV per
table** plus a bilingual `README.txt` listing every table and its row count.
CSVs are written UTF-8 **with a BOM**, so Arabic names open correctly in Excel
on Windows.

These tables are deliberately **excluded** as operational noise: `app_logs`,
`backend_logs`, `frontend_logs`, `audit_logs`, `sync_queue`, `sync_conflicts`,
`rate_hits`, `user_sessions`, `ai_conversations`, `petsy_usage`,
`login_attempts`, `sqlite_sequence`, and anything beginning `sqlite_`.

A table that cannot be read is skipped and logged — one bad table does not cost
you the rest. The export is audited as `data_export`.

> Source: `platform/blueprints/system/routes.py:988-1065`,
> `platform/templates/system/monitor.html:262`

---

## 15. Branches — الفروع

A `branches` table exists (`id`, `clinic_id`, `name`, `name_ar`, `phone`,
`address`, `manager_id`, `is_active`, `created_at`) and a new database is seeded
with exactly one row: **Main Branch / الفرع الرئيسي**.

**There is no screen anywhere in the platform for creating, editing, renaming or
deactivating a branch.** No route in any blueprint writes to the table.

What branches *do* affect today:

| Where | Effect |
|---|---|
| Staff form → **Branch / الفرع** dropdown | Sets `users.branch_id`. Lists every active branch |
| Staff list and staff detail | Shows the branch name next to each person |
| HR → Attendance | A **Branch** filter dropdown, and a Branch column in the attendance table |
| AI Assistant | A `doctor` whose account has a branch may only open visits from **their own branch** |

`branches.phone`, `branches.address`, `branches.manager_id` and
`branches.clinic_id` are never read by any screen.

> Source: `platform/models/database.py:1135-1144` (schema), `:2640-2643` (seed),
> `platform/blueprints/hr/routes.py:468`, `:569-576`, `:649-651`, `:1590-1615`,
> `platform/templates/hr/staff_form.html:154-164`,
> `platform/templates/hr/hr_attendance.html:197-200`, `:299`,
> `platform/blueprints/ai_assistant/routes.py:400-416`

---

## 16. Multi-clinic — one deployment, many clinics

The platform can host several clinics on one installation. **Each clinic gets its
own database**, so a missing `WHERE` clause cannot cross from one clinic's
records to another's.

### How a clinic is identified on each request

In this order:

1. the `PLATFORM_TENANT` environment variable — used by scripts, cron and
   single-clinic deployments;
2. the `X-Tenant` request header — internal calls and tests;
3. the **subdomain** of the host — `nilevet.aleefy.online` → clinic `nilevet`;
4. nothing — plain single-database mode, which is exactly how the platform
   behaves when no clinic has ever been registered.

Slugs must be lowercase letters, digits and hyphens, 3–32 characters. These host
names are never treated as a clinic: `www`, `app`, `api`, `admin`, `static`,
`cdn`, `mail`, `localhost`.

### There is no screen for this

Clinics are registered from the command line only, with
`platform/scripts/add_clinic.py`. Nothing in the web interface creates, renames,
suspends or lists clinics.

### What the platform enforces

* **A session belongs to the clinic it was issued for.** Presenting a cookie from
  clinic A on clinic B's subdomain clears the session and returns you to the
  sign-in page with *"Please sign in to this clinic."*
* An **unregistered subdomain** returns 404 on every URL, including the sign-in
  page.
* A **suspended** clinic has its own error handler.
* **Backups are per clinic.** Each clinic's archives live in their own
  subdirectory, so one clinic's 30-day purge cannot delete another's. The backup
  page, the monitor page and the health probe all report on *this* clinic's
  archives.
* The **nightly jobs loop over every clinic** — backup, backup health, WhatsApp
  reminders, rate-limit cleanup, attendance close-out and log retention each run
  once per clinic, and a failure names which clinic failed.

> Source: `platform/models/tenancy.py:1-35` (design and resolution order),
> `:55-63` (slug rules and reserved hosts), `:285-320` (`create`, `set_status`),
> `platform/app.py:130-181` (registry wiring and error handlers), `:301-339`
> (per-request tenant resolution and the session/tenant match),
> `platform/app.py:702-848` (`_for_every_clinic` and the six scheduled jobs),
> `platform/models/backup.py:80-137` (`for_clinic`, `for_current_clinic`),
> `platform/scripts/add_clinic.py`

---

## 17. Theme and language switches — `/settings/*`

| Route | Method | Field | Behaviour |
|---|---|---|---|
| `/settings/` | GET | — | Redirects to the launcher |
| `/settings/theme` | POST | `theme` | **Only `medical` is valid.** Anything else — including the removed `logo` theme — is silently normalised to `medical`. Saved to `users.theme_preference` and the session. Accepts JSON as well as a form |
| `/settings/lang` | POST | `lang` | Accepts `en` or `ar`; anything else becomes `en`. **Saved to the session only** |

Both routes redirect back through a same-site check, so a `next` value pointing
off-site is ignored. Both are **exempt from CSRF** and carry **no login or role
check at all**.

The language a visitor sees before signing in comes from the
`PLATFORM_DEFAULT_LANG` environment variable (default `en`), not from any screen.

> Source: `platform/blueprints/settings/routes.py:12-13` (`_VALID_THEMES`),
> `:107-167`, `platform/blueprints/auth/routes.py:26-52`
> (`safe_redirect_target`), `platform/models/security.py:261` (`_CSRF_EXEMPT`),
> `platform/app.py:376-379` (`PLATFORM_DEFAULT_LANG`)

---

## 18. Sign-in, lockout and session rules

These apply everywhere and are not configurable from any screen.

| Rule | Value | Source |
|---|---|---|
| Failed attempts before lockout | **5** | `models/security.py:38` |
| Lockout duration | **15 minutes** | `models/security.py:39` |
| Idle session timeout | **1 hour**, then *"Your session has expired. Please log in again."* | `models/security.py:40`, `app.py:341-345` |
| Password policy | 12+ chars, 1 uppercase, 1 lowercase, 1 digit, 1 special | `models/security.py:346-367` |
| 2FA challenge window | **5 minutes** between password and code | `blueprints/auth/routes.py:477` |
| 2FA code attempts | Rate-limited separately from the password step | `blueprints/auth/routes.py:637-646` |
| CSRF | Every POST outside `/api/public/`, `/petsy/chat`, `/auth/login`, `/settings/theme`, `/settings/lang` must carry `_csrf_token`. A failure returns a 403 page: *"Invalid or missing security token. Please go back and try again."* | `app.py:347-357`, `models/security.py:257-283` |

Rate limiting is keyed on **the IP and the account being targeted**, so an attack
on one account does not lock the whole clinic out.

If a user has 2FA enrolled but the server cannot do TOTP, the login is
**refused** rather than silently downgraded to password-only.

---

## 19. Scheduled jobs

One process owns the scheduler, chosen by a lock file in the backup directory,
so N gunicorn workers do not fire N concurrent backups.

| Job | Time | What it does |
|---|---|---|
| `daily_backup` | **02:00** | Backs up every clinic. A failure notifies managers with the clinic named |
| `attendance_close` | **00:20** | Closes yesterday's forgotten check-outs |
| `log_retention` | **03:30** | Deletes expired log files |
| `wa_reminders` | **09:00** | WhatsApp reminders |
| `backup_health` | **09:05** | Checks the archives on disk, so a dead scheduler is still noticed |
| `rl_cleanup` | every hour, on the hour | Clears expired rate-limit counters |

Times are the scheduler's own clock. The Monitor page labels them "UTC" and says
log cleanup runs at 03:00 — both are captions, not settings, and the second one
is wrong (it is 03:30).

Backup alerts to managers are throttled to **once per 24 hours per alert title**,
so a broken backup does not bury the notification bell.

> Source: `platform/app.py:668-848`, `platform/models/backup.py:55`
> (`ALERT_COOLDOWN_HOURS`)

---

## 20. Known limits

Everything below is a real behaviour of the code as it stands. None of it is
speculation.

### Roles & Permissions

1. **Every built-in role is listed twice on the Roles screen.** The `roles` table
   is seeded with all fourteen built-in roles, and the template renders that
   whole table under the heading **Custom Roles (14)** — with Edit and Delete
   buttons — *in addition to* the read-only "built-in" cards in the department
   sections above.
   *Which copy matters:* the row under **Custom Roles** is the one that governs
   access, because enforcement reads `roles.permissions_json`. The department
   cards above are decoration.
   > `platform/models/database.py:2435-2450`, `:2644-2648`,
   > `platform/blueprints/system/routes.py:802`,
   > `platform/templates/system/roles.html:233-249`

2. **The built-in role cards show a permission list that is not enforced.** They
   are drawn from a hardcoded table in the route file that has drifted from the
   list actually seeded into the database. For example the card for **Doctor**
   shows *WhatsApp Messaging* and omits *Catalog*, *Inpatient*, *Telemedicine*,
   *Imaging* and *Attendance* — the opposite of what a doctor really has. The
   card footer says these roles "cannot be modified", which is also untrue: the
   duplicate row under Custom Roles edits them.
   > `platform/blueprints/system/routes.py:771-783` vs
   > `platform/models/database.py:4346-4379`

3. **Four real roles have no card of their own:** `finance`, `inventory_mgr`,
   `boarding_staff` and `auditor` appear only in the Custom Roles list, not in
   any department section.

4. **The `auditor` role cannot open the Audit Log**, even though
   `/system/audit` names it. The whole `/system` blueprint is gated on the
   `system` permission key, and `auditor` is granted `reports`, `audit` and
   `accounting` — not `system`. Anyone on `auditor` is redirected to the launcher
   with *"You don't have permission to access this page."*
   > `platform/blueprints/system/routes.py:235`,
   > `platform/blueprints/auth/routes.py:110-134`,
   > `platform/models/database.py:4378`

5. **The `backup`, `audit` and `settings` checkboxes have no independent
   effect.** Every screen they name lives inside the `/system` blueprint, which
   is governed by the single `system` key. Nothing in the codebase ever checks
   `backup`, `audit` or `settings` on their own — the helper written for that
   (`permission_required`) has zero callers.
   > `platform/blueprints/auth/routes.py:431-461` (defined, never used)

6. **Creating a role with no permissions ticked locks its holders out of
   everything.** The *edit* modal refuses to save an empty permission list; the
   *create* modal does not. A role created with nothing ticked stores `[]`, which
   the loader reads as "no data", and since the name is not a built-in it is then
   denied everywhere.
   > `platform/blueprints/system/routes.py:833-853` (no check) vs `:880-884`
   > (the check on edit), `platform/blueprints/auth/routes.py:118-128`

7. **The Assign Role dropdown shows duplicates.** It is built from ten hardcoded
   built-in keys *plus* every row in `roles`, and the seeded rows repeat the same
   ten keys. So `super_admin` appears both as "super_admin" and as
   "Super Administrator".
   > `platform/templates/system/roles.html:472-480`

8. **The Staff Access tab only ever sees 300 users.** The JSON endpoint has a
   hard `LIMIT 300` and all filtering and paging happen in the browser on that
   set. A clinic with more staff silently cannot reach the rest.
   > `platform/blueprints/system/routes.py:826-828`

9. **The `N users` pill counts inactive staff too.** It has no `is_active`
   filter, so a role shows "3 users" when two of them left.
   > `platform/blueprints/system/routes.py:805-807`

10. **A separate, unlinked roles screen exists at `/hr/roles`.** It lists the same
    table with active-only user counts and no editing. Nothing links to it.
    > `platform/blueprints/hr/routes.py:934-946`

### Users

11. **The staff form cannot create an HR officer or assign any custom role.** Its
    role dropdown is a hardcoded list of thirteen keys that omits `hr` — a real,
    seeded role — and never includes roles created on the Roles screen. The only
    way to put someone on those roles is the Staff Access tab.
    > `platform/blueprints/hr/routes.py:20-24`,
    > `platform/templates/hr/staff_form.html:146-152`

12. **The password hint on the staff form is wrong.** It says
    *"Min 6 characters / 6 أحرف على الأقل"*. The server requires **12 characters
    with an uppercase, a lowercase, a digit and a special character**, and
    rejects anything less with a red flash after the form has been filled in.
    > `platform/templates/hr/staff_form.html:52` vs
    > `platform/models/security.py:346-367`

13. **There is no change-password form on the Profile page.** The route handles
    `action=change_password` (old password, new password, confirm, full strength
    validation) but no template renders it. A user cannot change their own
    password from the interface; only an owner or support admin can reset it from
    the staff detail page.
    > `platform/blueprints/auth/routes.py:707-731` (handler present),
    > `platform/templates/profile.html` (no such form)

14. **Language choice does not survive sign-out.** `users.language` exists in the
    schema, but no screen ever writes it — the Profile page saves only the theme,
    and both the Profile form and the top-bar switch keep the language in the
    session. Next sign-in reverts to the deployment default.
    > `platform/models/database.py:1168` (column), `:2876-2880`
    > (`update_user_theme` — theme only),
    > `platform/blueprints/auth/routes.py:787-794`,
    > `platform/blueprints/settings/routes.py:149-160`

### Settings

15. **The Currency setting does nothing.** It is saved to `clinic.currency` and
    read back only by the Settings page itself. Invoice PDFs hardcode "EGP".
    > `platform/models/pdf_generator.py:430`, `:501-537`

16. **The Timezone setting does nothing.** It is saved to `clinic.timezone` and
    read back only by the Settings page itself. No other code reads it.

17. **Default Theme and Default Language do nothing.** Both are written to the
    `settings` table and read back only to re-populate the same dropdowns.
    Nothing applies them to a new session. The actual pre-sign-in language comes
    from the `PLATFORM_DEFAULT_LANG` environment variable.
    > `platform/blueprints/system/routes.py:374-386`, `platform/app.py:376-379`

18. **Default Theme offers a theme that no longer exists.** The dropdown still
    lists "Logo (Navy / Yellow / Blue)". The theme switcher accepts only
    `medical` and silently normalises anything else.
    > `platform/templates/system/settings.html:229-231` vs
    > `platform/blueprints/settings/routes.py:12-13`

19. **Ticking "Remove the current logo" *and* choosing a new file removes the
    logo.** The removal branch is evaluated first and the upload is never read.
    The same applies to the Instapay QR.
    > `platform/blueprints/system/routes.py:334-352`

20. **The top-bar Settings link is shown to everyone.** It has no role condition,
    so a nurse or receptionist clicking it is bounced to the launcher with a
    permission error.
    > `platform/templates/base.html:448-451`

### Backup

21. **The Monitor page's "Last Backup" date is always blank and "Integrity"
    always reads "?" in a red badge.** The template asks for `created_at` and
    `integrity`; the backup listing supplies `timestamp` and no integrity field
    at all. The Backup page itself shows the correct values.
    > `platform/templates/system/monitor.html:270-277` vs
    > `platform/models/backup.py:458-470`

22. **A `support_admin` sees Download, Upload and Restore controls they cannot
    use.** The Backup page opens for `support_admin`, but those three routes
    allow only `super_admin` and `clinic_owner`. Clicking them ends on the
    launcher with a permission error.
    > `platform/blueprints/system/routes.py:454` vs `:510`, `:521`, `:539`

23. **In a multi-clinic deployment, maintenance mode does not actually hold
    traffic off.** The restore writes its marker into the clinic's own backup
    folder, but the app-wide gate looks for it in the deployment's top-level
    folder. The banner on the Backup page appears (it reads the scoped marker),
    but staff on other pages are **not** blocked during the restore. Single-clinic
    installations are unaffected.
    > `platform/blueprints/system/routes.py:61` (unscoped) vs `:546` and `:463-466`
    > (scoped), `platform/models/backup.py:215-258`

24. **Off-site backup targets cannot be configured from any screen.** They come
    from the `BACKUP_OFFSITE_DIR` and `BACKUP_S3_BUCKET` environment variables.
    The card simply reports what is or is not set.
    > `platform/models/backup.py:681-693`

25. **The "30-day retention · daily at 02:00" caption is hardcoded text.** It
    happens to match the defaults, but the retention period is a code constant
    and the schedule uses the server's own clock, not UTC.
    > `platform/templates/system/backup.html:74`,
    > `platform/models/backup.py:45`, `platform/app.py:773`

### Sync

26. **The Keep Local and Keep Server buttons do not work.** Both forms send the
    CSRF token as `csrf_token`; the validator reads `_csrf_token`. Every click
    returns the 403 page *"Invalid or missing security token. Please go back and
    try again."* The conflict is never resolved.
    > `platform/templates/system/sync.html:202`, `:208` vs
    > `platform/models/security.py:276`

27. **"Keep Local" never was a data merge, even when the form worked.** It closes
    the conflict and marks it KEPT LOCAL; the server record is left unchanged and
    the device's version is stored on the conflict row for somebody to copy by
    hand. The flash message says so.
    > `platform/blueprints/system/routes.py:753-761`

### Branches and multi-clinic

28. **There is no branch management screen.** Branches can only be added by
    writing to the database directly. A new clinic gets exactly one, "Main
    Branch / الفرع الرئيسي", and no screen can rename it.
    > `platform/models/database.py:2640-2643`

29. **`branches.phone`, `branches.address` and `branches.manager_id` are never
    read.** Nothing displays or uses them.

30. **There is no clinic-management screen.** Registering, renaming or suspending
    a clinic in a multi-clinic deployment is a command-line operation
    (`scripts/add_clinic.py`).

### Navigation

31. **The launcher's "System Monitor & Diagnostics" card is hidden from
    `clinic_owner`**, although the route allows that role and the sidebar shows
    the same page. A clinic owner must use the sidebar.
    > `platform/blueprints/launcher/routes.py:531` (the card's role list),
    > `:579` (the filter that hides it) vs
    > `platform/blueprints/system/routes.py:77`

32. **Diagnostics, Sync Dashboard, Export All Data and Staff Two-Step
    Verification have no sidebar entry.** They are reachable only from buttons on
    other pages, or by typing the URL.

---

*Verified against the source on 2026-08-19. Every claim above was read from the
route functions and templates cited beside it.*
