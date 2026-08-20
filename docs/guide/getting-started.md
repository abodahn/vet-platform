# Getting started / البدء

First-time setup, in the order it has to happen. Each step takes a few minutes;
the whole thing is an afternoon. Steps 1–4 must be done before anyone else signs
in. Steps 5–9 can wait until the day before you go live.

You need the `admin` account and its password. Provisioning prints those once,
at the end of `scripts/provision/provision.sh`, and writes them nowhere you can
read back. If nobody kept them, see [`../../PROVISIONING.md`](../../PROVISIONING.md).

*Source: `models/database.py:2553` (`init_db(admin_user="admin", …)`),
`:2657-2660` (the first user is created only when the users table is empty, as
`super_admin` / "Platform Administrator"); `scripts/provision/provision.sh:239-247`*

---

## Step 1 — Sign in and change the admin password

1. Open `/auth/login`.
2. Pick your language with **EN** / **عربي** above the form, and light or dark
   with the 🌓 button. Both stick for the session.
3. Username `admin`, the provisioned password, **Sign In / تسجيل الدخول**.
4. Change the password from `/hr/staff` → open the admin account →
   **Reset Password / إعادة تعيين كلمة المرور**.

**There is no change-password form on `/auth/profile`.** The profile page holds
theme, language and two-step verification only. `/hr/staff/<id>` →
**Reset Password** is the working path, and it is open to super admin, clinic
owner and support admin — including on their own account.

The new password must be at least 12 characters with an uppercase letter, a
lowercase letter, a digit and a special character, whatever the box says (its
placeholder claims six — the server rejects six). The same rule applies
everywhere a password is set, including when you create staff below.

Five wrong attempts in 15 minutes locks that username and that IP address for
15 minutes. There is no unlock button — it clears itself.

*Source: `blueprints/hr/routes.py:852-880`;
`templates/hr/staff_detail.html:121-131`; `templates/profile.html:17-194`
(no password form); `blueprints/auth/routes.py:533-616`, `:705-730` (the route
handles `change_password`, nothing posts it); `models/security.py:38-40`,
`:346-366`; `templates/login.html:715-795`*

## Step 2 — Turn on two-step verification for the admin accounts

`/auth/profile`:

1. **Set Up Two-Step Verification / إعداد التحقق بخطوتين** → a QR code and a
   typed-out key appear.
2. Scan it with an authenticator app, type the 6-digit code, then
   **Turn On Two-Step Verification / تفعيل التحقق بخطوتين**.
3. **Print or save the backup codes now.** They are rendered once, on that
   screen, and never shown again. Losing both the phone and the codes means an
   admin reset.

Afterwards the same card shows how many backup codes are left, with
**Generate New Backup Codes / إنشاء رموز احتياط جديدة** and
**Turn Off / الإيقاف** — both of which ask for your password first.

An owner or super admin can reset anyone's enrolment at `/auth/2fa/admin`.
Every reset is written to the audit log. That also means one compromised admin
account can strip 2FA from everybody, which is exactly why the admin accounts
are the ones that should enrol first.

*Source: `blueprints/auth/routes.py:733-786`, `:812-831`;
`templates/profile.html:110-190`*

## Step 3 — Fill in the clinic's identity

`/system/settings` — **Clinic Settings / إعدادات العيادة**. Owner and super
admin only.

| Section | What to fill |
|---|---|
| 🏥 Clinic Information / بيانات العيادة | **Clinic Name (English) \*** is the only required field. Also Arabic name, lead doctor, phone, email, website, tagline, address in both languages, license number, tax/VAT number. |
| 🖼️ Clinic Logo / شعار العيادة | PNG, JPEG, GIF or WebP, up to 2 MB. Resized to 400 px and stored inside the database, so it rides along in every backup. It appears on invoices, vaccination certificates and payslips. |
| 💳 Instapay / إنستاباي | Instapay address, a tappable payment link, and a QR image (up to 2 MB, kept at 800 px so it still scans). |
| 🌍 Preferences / التفضيلات | Currency (used on invoices and financial reports) and timezone. Defaults are EGP and Africa/Cairo. |
| 🎨 Appearance / المظهر | Default theme — **Medical (White / Navy / Gold)** or **Logo (Navy / Yellow / Blue)** — and default language, applied to new sessions. |

Press **💾 Save All Settings / حفظ كل الإعدادات**.

Two things worth knowing. A rejected image aborts the whole save, so the text
fields do not half-write — you get a red message naming the reason. And the
clinic record is cached; saving clears the cache immediately, so the new name
shows at once.

*Source: `blueprints/system/routes.py:325-416`;
`templates/system/settings.html:51-252`*

## Step 4 — Check the roles before you create anybody

`/system/roles` — **Roles & Permissions / الأدوار والصلاحيات**.

Fourteen roles are seeded: Super Administrator / مدير النظام الأعلى, Clinic
Owner / صاحب العيادة, Branch Manager / مدير الفرع, Doctor / طبيب بيطري,
Nurse / ممرض / تقني, Receptionist / موظف استقبال, Inventory Manager / مدير
المخزون, Pharmacist / صيدلاني, Finance User / موظف مالية, HR Officer / موظف
الموارد البشرية, Groomer / موظف تجميل, Boarding Staff / موظف الإيواء, Support
Admin / مدير الدعم الفني, Read-only Auditor / مدقق للقراءة فقط.

Each starts with a default set of modules — see the table in
[README § Troubleshooting](README.md#4-troubleshooting--what-people-actually-get-stuck-on).

**Read this before you edit anything.** The screen shows every role twice:

- The cards under **Management**, **Clinical**, **Front Desk** and so on are a
  hardcoded display, marked *"System roles are enforced in code and cannot be
  modified."* They are not what the permission check reads, and they do not
  always match it.
- The rows under **Custom Roles** are the database rows. Those are what is
  enforced, and those are the ones with an **Edit Role / تعديل الدور** button.

So to give reception access to visits, edit `reception` **under Custom Roles**.

A role cannot be saved with nothing ticked — an empty grant is read as "no data,
fall back to the built-in list", which would widen the role rather than narrow
it. To retire a role, move its staff off it and delete it (super admin only).

Every edit clears the permission cache immediately and records the before-and-
after permission list in the audit log.

*Source: `blueprints/system/routes.py:771-783` (display map),
`:799-818`, `:856-901`, `:906-919`; `models/database.py:2435-2450`, `:4346-4379`;
`templates/system/roles.html:147-249`*

## Step 5 — Create the staff logins

`/hr/staff` — **Staff Management / إدارة الموظفين** → **+ New Staff / موظف
جديد**. Open to super admin, clinic owner, branch manager, support admin and HR.

Required: **username** and **password** (12+ characters, mixed case, digit,
special character), plus the confirmation. Everything else — full name in both
languages, email, phone, role, branch, job title, contract type, hire date,
national ID, emergency contact, gender, date of birth, opening shift — is
optional but worth doing.

Two things to expect:

- The role dropdown here lists 13 roles and **does not include `hr`**. To make
  someone an HR Officer, create them as something else, then change the role on
  `/system/roles` → **Staff Access / صلاحيات الموظفين**, which lists it.
- Four things are refused outright, with a message: assigning a role that does
  not exist; granting a role above your own rank (only a super admin makes a
  super admin); changing **your own** role; and demoting or deactivating the
  last active super admin.

To reset a password later: `/hr/staff/<id>` → **Reset Password / إعادة تعيين
كلمة المرور** (super admin, clinic owner and support admin only). Ignore the
"min 6 chars" placeholder — the server enforces the full 12-character rule and
tells you so.

*Source: `blueprints/hr/routes.py:20-24` (the dropdown list), `:459-644`,
`:501-566` (password rule), `:852-882`; `blueprints/auth/routes.py:345-404`
(the role guard); `templates/system/roles.html:472-478`*

## Step 6 — Load the price list

`/catalog/` — **Price Catalog / كتالوج الأسعار**. Editable by super admin,
clinic owner, branch manager and finance; everyone else sees it read-only.

Per service: code (uppercased, optional — leave blank if you have no codes),
name, Arabic name, category, description, standard price, tax rate, duration in
minutes, species, active flag, sort order. Only **name** is required. A
duplicate code is refused by name.

Categories default to Consultation, Vaccination, Laboratory, Surgery, Grooming,
Boarding, Treatment, Hospitalization until you create your own.

Bulk load with `POST /catalog/import` (CSV) and get it back with
`/catalog/export.csv`. Columns: `code, name, name_ar, category,
standard_price, tax_rate, duration_min, species, description, is_active`.

The list also shows how often each service has been billed, matched on the
description written onto invoice lines.

*Source: `blueprints/catalog/routes.py:19-124`, `:166-190` (export),
`:202-243` (import)*

## Step 7 — Load stock and medications

1. **Items** — `/inventory/items/new`. Category, SKU, barcode, name, Arabic
   name, unit, cost price, sell price, reorder level (defaults to 10), max stock
   (defaults to 1000), and the three flags that matter: **is medication**,
   **is controlled**, **requires prescription**. Plus storage notes.
2. **Opening stock** — `/inventory/batches/new?item_id=<id>` for each item:
   batch number, lot number, manufacture date, expiry date, quantity, unit cost,
   warehouse. A non-numeric quantity is refused by name rather than booked as
   zero.
3. Ten item categories are seeded (Medications / أدوية, Vaccines / تطعيمات,
   Consumables / مستهلكات, Surgical Materials / مواد جراحية, Lab Materials /
   مواد مخبرية, Grooming Products / منتجات تجميل, Pet Food / غذاء حيوانات, Pet
   Accessories / إكسسوارات, Cleaning / مواد تنظيف, Office Supplies / مستلزمات
   مكتبية), and one warehouse: **Main Pharmacy / الصيدلية الرئيسية**.
4. Check `/inventory/alerts` once loaded — that is where short and expiring
   stock surfaces from then on.

*Source: `blueprints/inventory/routes.py:177-241`, `:391-473`, `:475-502`;
`models/database.py:2452-2458`, `:2666-2669`*

## Step 8 — Set up only the services you actually sell

Skip any of these you do not offer.

- **Grooming** — `/grooming/services`: name (required), species, duration
  (default 60 min), price, active, description.
  *Source: `blueprints/grooming/routes.py:326-376`*
- **Boarding** — `/boarding/rooms`: room name/number (required), room type
  (default Standard), capacity (default 1), daily rate, active.
  *Source: `blueprints/boarding/routes.py:344-380`*
- **Pet shop** — `/petshop/categories` then `/petshop/products/new`. Restricted
  to super admin, clinic owner, branch manager, support admin (and reception for
  products). Remember: the POS only shows products that are active **and** have
  stock above zero.
  *Source: `blueprints/petshop/routes.py:247-290`, `:333-400`, `:439-455`*

## Step 9 — Waiting-room TV, backups, and the first check

**Waiting-room TV.** Open `/appointments/waiting-room?t=<WAITING_ROOM_TOKEN>`
once on the display machine; the token is stored in a cookie for a year and the
page's own polling stays authorised. Provisioning mints a token per clinic. With
no token set, the page returns 404 to anyone not signed in — deliberately, so a
clinic's schedule is never published by accident. Client names on the display
are shortened to "Ahmed E.".

*Source: `blueprints/appointments/routes.py:709-841`*

**Backups.** `/system/backup` — owner, super admin, support admin. Loading the
page runs a health check, which is how a silently dead scheduler gets noticed.
Take one manual backup now with **💾 Back Up Now / انسخ احتياطياً الآن**, then
**✓ Check / فحص** it. The page also states the retention policy on screen:
30-day retention, daily at 02:00, and warns in red when nothing recent exists. If off-site
copies are configured, a failed copy is reported in red while the local backup
still succeeds.

*Source: `blueprints/system/routes.py:453-520`*

**Last check.** `/system/diagnostics` for the environment, `/system/monitor` for
live health, `/system/audit` for who did what. And `/system/export/all` produces
one file containing the clinic's whole record set, for the day you want to prove
the data is yours.

*Source: `blueprints/system/routes.py:234-326`, `:578-662`, `:1012-1065`*

---

## Shared reception PC

If several people work one machine, they do not have to log each other out.
Under the user menu, **Add a user to this PC / إضافة مستخدم لهذا الجهاز**
(`/auth/desk/add`) signs a second person into the same browser; switching
between them is one click. Up to five accounts.

*Source: `blueprints/auth/routes.py:880-1011`; `templates/base.html:456-478`*

## What is deliberately not here

- **Creating the very first admin account.** It exists already, made when the
  database was initialised. There is no sign-up screen.
- **Branches.** One branch, **Main Branch / الفرع الرئيسي**, is seeded. See
  `../manual/system.md` § 15 for what branch support does and does not do today.
- **Multi-clinic.** One clinic is one deployment with its own database — see
  [`../../PROVISIONING.md`](../../PROVISIONING.md).

*Source: `models/database.py:2640-2643`, `:2657-2660`*

---

Next: **[A day in the life](day-in-the-life.md)** — what this looks like once
the clinic is open.
