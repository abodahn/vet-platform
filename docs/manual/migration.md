# Data Migration — Reference Manual

**Module:** Data Migration / ترحيل البيانات
**URL prefix:** `/migration/`
**Blueprint:** `migration`

This chapter is a **screen-by-screen reference**. It describes only what the code
in `blueprints/migration/routes.py`, `templates/migration/*.html` and
`migrations/excel_import.py` actually does today. Anything present in the
database but with no screen behind it, and any control that does not do what its
label suggests, is listed under [Known limits](#known-limits) rather than
described as working.

The module is a four-step wizard over five routes. It is normally the **first
thing a clinic uses**: they arrive with one spreadsheet of owners, pets and visit
history, and this is how it becomes platform data.

> Source: `platform/app.py:234`, `platform/app.py:262` (blueprint registered at
> `/migration`), `platform/blueprints/migration/__init__.py:1-3`

---

## 1. Getting into the module

Three doors, and unusually for this product all three agree with the route's own
permissions — nobody is shown a link they cannot open.

| Door | Where | Goes to |
|---|---|---|
| Sidebar → SYSTEM / النظام → **Data Migration / ترحيل البيانات** | every page | `/migration/` |
| Launcher card **🔄 Data Migration / ترحيل البيانات** (badge `Live`) | `/` | `/migration/` |
| Direct URL | — | `/migration/` |

The sidebar SYSTEM group is wrapped in
`{% if current_user and current_user.get('role') in ('super_admin','clinic_owner','support_admin') %}`,
and the launcher card declares
`"roles": ["super_admin","clinic_owner","support_admin"]` with
`"category": "system"` and the description *"Import legacy Excel clinic data into
the unified platform · Patients · Visits · Owners"*. Both match the read roles in §2.

There is also a **Backup Manager / مدير النسخ الاحتياطي** button in the top bar of
the landing screen, linking to `/system/backup`.

> Source: `platform/templates/base.html:289, 318-321`,
> `platform/blueprints/launcher/routes.py:507-521`,
> `platform/templates/migration/index.html:7-11`

---

## 2. Who can open what

Every other module in this product is governed by two gates — the module grant
checked in `login_required`, and the route's own `role_required` list. **For this
module only the second one operates.**

`migration` is not a key in `ALL_PERMISSIONS`, and `_permission_for()` returns
`""` for a blueprint with no grantable key, which `_permission_denied()` treats as
"nothing to enforce" and falls open. The practical consequence is that **Data
Migration does not appear on the Roles & Permissions screen at all** and cannot be
granted to, or revoked from, any role. Access is fixed in code.

> Source: `platform/blueprints/auth/routes.py:88-133` (`_permission_denied`),
> `:155-166` (`_permission_for`), `:167-194` (`role_required`),
> `platform/models/database.py:4302-4330` (`ALL_PERMISSIONS`)

```python
READ_ROLES  = ("super_admin", "clinic_owner", "support_admin")
WRITE_ROLES = ("super_admin", "clinic_owner")
```

### Effective access, per route

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| Landing page | `GET /migration/` | READ_ROLES | super_admin, clinic_owner, support_admin |
| Upload and map | `POST /migration/upload` | READ_ROLES | same |
| Preview (dry run) | `POST /migration/preview` | READ_ROLES | same |
| **Commit (writes)** | `POST /migration/commit` | **WRITE_ROLES** | **super_admin, clinic_owner only** |
| Failed-rows CSV | `GET /migration/failed-rows.csv` | READ_ROLES | super_admin, clinic_owner, support_admin |

**`support_admin` sees a button it cannot press.** The `Import now / تنفيذ
الاستيراد الآن` button at the bottom of the preview page is rendered
unconditionally. A support admin can upload, map and preview, but the commit
bounces to the launcher with *"You don't have permission to access this page."*
Nothing on screen warns before the click.

Every other role — doctor, nurse, reception, pharmacist, inventory_mgr, finance,
hr, groomer, boarding_staff, auditor — is refused on all five routes.

> Source: `platform/blueprints/migration/routes.py:38-39, 141, 172, 230, 284, 364`,
> `platform/blueprints/auth/routes.py:186-190`,
> `platform/templates/migration/preview.html:210-212`

---

## 3. Things that apply to every screen

- **Bilingual, with no English-only strings.** Every label on all four templates
  comes from `t(en, ar)` and flips with the signed-in user's language. Unusually,
  the bilingual coverage reaches into the engine: every row error and every
  duplicate note carries an `en` and an `ar` text and is rendered
  `{{ t(e.en, e.ar) }}`. The only English-only output in the module is inside the
  downloaded CSV (§8).
- **RTL.** The shell flips to RTL in Arabic. Two places deliberately opt out: the
  preview's phone column is `dir="ltr"` with a monospace font so a normalised
  Egyptian number reads left-to-right, and the map screen's `Example values`
  column renders raw cell text as-is.
- **CSRF.** All three POSTs carry a hidden `_csrf_token`. A missing or stale token
  produces a 403 page reading *"Invalid or missing security token. Please go back
  and try again."* The session lifetime is 24 hours.
- **Three of the five routes are POST-only** and have no URL you can navigate to.
  Refreshing the map, preview or result page re-posts.
- **No currency, anywhere.** This module carries no money field of any kind (§9).
- **Dates read day-first** — `03/04/2024` is 3 April — because that is how Egypt
  writes them.
- **`t()` only.** The data-localisation helper `loc()` is not used here, and the
  importer never writes the `_ar` name columns it reads from.

> Source: `platform/app.py:406-408` (`t`), `:350-357` (CSRF),
> `platform/config.py:120` (session lifetime),
> `platform/templates/migration/preview.html:169`,
> `platform/migrations/excel_import.py:235-242, 611-622`

### Where your file lives between steps

| | |
|---|---|
| Staged at | `<uploads>/import_staging/<32-hex-token>.xlsx` (or `.csv`) |
| `<uploads>` is | `<directory of DATABASE_PATH>/uploads` |
| Remembered in | the session, under `import_file` = `{token, name, ext}` |
| Re-read | on **every** later step — the parsed rows are never cached |
| Swept | files older than 24 h, but **only** when someone starts a new upload |
| Failed CSV | `<uploads>/import_staging/<token>.failed.csv`, UTF-8 with BOM |
| Session key cleared | **never**, not even after a successful commit |

> Source: `platform/blueprints/migration/routes.py:33-36, 44-72, 75-96, 125-137,
> 209-215`, `platform/app.py:294-295`

---

## 4. Screen: Import Your Data (Step 1)

**Purpose.** The landing page. It answers one question — *is it safe to run a
destructive import right now?* — and then lets you pick a file.

**How to reach it.** Sidebar → SYSTEM → Data Migration; the launcher card; or
`/migration/`. Also reached by every error path in the module, and by the
`Start over / البدء من جديد`, `Cancel / إلغاء` and `Import another file / استيراد
ملف آخر` buttons on later screens.

**Route.** `GET /migration/` · **Template.** `templates/migration/index.html`
**Who can open it.** super_admin, clinic_owner, support_admin.

**Page header.** Title `Import Your Data / استيراد بياناتك`, subtitle *"Bring your
existing owners, pets and visits in from Excel / انقل بيانات العملاء والحيوانات
والزيارات من ملفات إكسل"*.

**Top-bar button.** `Backup Manager / مدير النسخ الاحتياطي` → `/system/backup`.

### The information banner

A blue `pf-alert-info` headed `How this works / كيف تتم العملية`, carrying two
paragraphs verbatim:

> *"1. Upload your Excel or CSV file. 2. Tell us which column is which. 3. Review
> a preview — nothing is saved yet. 4. Confirm, and we import."*
> *"A full backup of your data is taken automatically before anything is written.
> If the backup fails, the import does not run."*

Both claims are true of the code: `/preview` passes `dry_run=True` and executes no
write statement, and `/commit` returns before touching the database if
`bk.run_backup()` does not report success.

### The file card — Step 1 — Choose your file / الخطوة ١ — اختيار الملف

Sub-heading: `Excel (.xlsx) or CSV (.csv), up to {max_mb} MB / إكسل ‎(.xlsx) أو
‎CSV، حتى {max_mb} ميجابايت`. `max_mb` is `MAX_CONTENT_LENGTH / 1024 / 1024`,
**16** as shipped.

| Control | Type | Behaviour |
|---|---|---|
| `Your spreadsheet / ملف البيانات` | `<input type="file" name="file" accept=".xlsx,.csv" required>` | `accept` filters the OS picker only; the server checks magic bytes, not the extension |
| helper text | — | *"The first row of the sheet must be the column titles. Arabic column names and Arabic data are fully supported. / يجب أن يحتوي الصف الأول على عناوين الأعمدة. أسماء الأعمدة والبيانات باللغة العربية مدعومة بالكامل."* |
| `Upload and continue / رفع الملف والمتابعة` | submit | `POST /migration/upload`, `enctype="multipart/form-data"` |

There is **no** sample-file download, no template, and no link to documentation.

### The four stat tiles

| Tile | Value |
|---|---|
| `Owners on file / عملاء مسجّلون` | `SELECT COUNT(*) FROM owners` |
| `Pets on file / حيوانات مسجّلة` | `SELECT COUNT(*) FROM pets` |
| `Visits on file / زيارات مسجّلة` | `SELECT COUNT(*) FROM visits` |
| `Last backup / آخر نسخة احتياطية` | the newest archive's `timestamp`, first 16 characters (`2026-08-20 14:22`), or `—` |

The three counters are the whole table, unfiltered. The backup tile is read inside
`with bk.for_current_clinic():`, so on a multi-tenant deployment it reports **this
clinic's** archive rather than the deployment's — a deliberate fix recorded in the
route's comment. A `—` here is the warning that step 4 will refuse.

### Previous imports / عمليات الاستيراد السابقة

The 20 most recent `audit_log` rows with `module='migration'`, newest first.

| Column | Content |
|---|---|
| `Time / الوقت` | `timestamp` first 16 characters, or `—` |
| `By / بواسطة` | `username` |
| `Details / التفاصيل` | the free-text summary written at commit, e.g. `Imported clients_2019_2026.xlsx: owners +612/~0, pets +840/~0, visits +4102; 18 rows failed; backup=platform_backup_20260820_142211.db` |

Only a **commit** writes here — a preview never appears. With no rows the card is
replaced by `No data has been imported yet. / لم يتم استيراد أي بيانات حتى الآن.`

There is no filter, no paging and no link from a row to anything.

> Source: `platform/blueprints/migration/routes.py:140-169`,
> `platform/templates/migration/index.html:1-115`,
> `platform/models/backup.py:105-138, 439-477`

---

## 5. Screen: Match your columns (Step 2)

**Purpose.** Confirm what each column of the uploaded file means, and decide what
happens to records that already exist.

**How to reach it.** Only by submitting the Step 1 form. It has no GET route.

**Route.** `POST /migration/upload` · **Template.** `templates/migration/map.html`
**Who can open it.** super_admin, clinic_owner, support_admin.

**Page header.** `Step 2 — Match your columns / الخطوة ٢ — مطابقة الأعمدة`,
subtitle `<filename> — <row_count> rows / صف`.

**Top-bar button.** `Choose a different file / اختيار ملف آخر` → `/migration/`.

### What the route did before rendering

1. Read the upload's bytes and validated them by magic byte, not extension.
2. Parsed the **first worksheet only** (`wb.active`), or decoded the CSV trying
   `utf-8-sig` → `utf-8` → `cp1256` and sniffing the delimiter across `, ; TAB |`.
3. Took row 1 as the column titles; an empty title becomes `Column 3`.
4. Dropped fully blank rows; padded short rows to the header width.
5. Purged staged uploads older than 24 h, then staged these bytes under a fresh
   token and put the token in the session.
6. Looked for a **remembered mapping** for this header layout; if none, guessed.

> Source: `platform/blueprints/migration/routes.py:171-227`,
> `platform/migrations/excel_import.py:325-482`

### The banner

Exactly one of two, chosen by whether a mapping was recalled:

| Condition | Banner |
|---|---|
| a saved mapping matched | green — *"We recognised this file layout from a previous import and filled in your earlier choices. Change any of them if you need to. / تعرّفنا على تنسيق هذا الملف من عملية استيراد سابقة وملأنا اختياراتك السابقة. يمكنك تعديل أي منها عند الحاجة."* |
| otherwise | blue — *"We have made a first guess for each column. Check them and correct anything that is wrong. Set a column to "Do not import" to leave it out. / قمنا بتخمين معنى كل عمود. راجع الاختيارات وصحّح ما يلزم. اختر «عدم الاستيراد» لتجاهل أي عمود."* |

The mapping is saved under `settings` key `import_map_<sha1-16>` where the
signature is a hash of the **folded** header titles. It is written at the end of
**preview**, not commit — previewing once is enough to teach it. One extra or
renamed column changes the signature and loses the memory.

> Source: `routes.py:104-122, 262`, `excel_import.py:519-524`

### Your columns / أعمدة ملفك

One row per column in the uploaded file.

| Column | Content |
|---|---|
| `Column in your file / العمود في ملفك` | the title as read from row 1, bold |
| `Example values / أمثلة من البيانات` | up to three non-empty values taken from the **first three data rows**, each truncated to 28 characters, joined with ` · `; `—` if all three are blank |
| `Import it as / استيراده كـ` | `<select name="col_{index}">` |

**The dropdown.** First option `Do not import / عدم الاستيراد` (value `""`), then
three `<optgroup>`s in this order:

| Group label | Options (English / Arabic) |
|---|---|
| `Owner / العميل` | `Owner name / اسم العميل`, `Phone / رقم الهاتف`, `Email / البريد الإلكتروني`, `Address / العنوان`, `Owner notes / ملاحظات عن العميل` |
| `Pet / الحيوان` | `Pet name / اسم الحيوان`, `Species / النوع`, `Breed / السلالة`, `Sex / الجنس`, `Date of birth / تاريخ الميلاد`, `Weight (kg) / الوزن بالكيلوجرام`, `Colour / اللون`, `Microchip number / رقم الشريحة`, `Pet notes / ملاحظات عن الحيوان` |
| `Visit / الزيارة` | `Visit date / تاريخ الزيارة`, `Visit type / نوع الزيارة`, `Doctor / الطبيب`, `Reason / diagnosis — سبب الزيارة أو التشخيص`, `Visit notes / ملاحظات الزيارة` |

Nineteen target fields, and that is the entire contract — see §10 for exactly
which database column each one lands in.

**How the guess is made.** `guess_mapping()` folds each header (lowercase, harakat
stripped, `أ إ آ ٱ → ا`, `ى ئ → ي`, `ة → ه`, `ؤ → و`, punctuation to spaces) and
matches it against ~120 English and Arabic aliases per field, in two passes:
exact matches across every field first, then substring matches. A column is
claimed once; the first field to claim it wins.

> Source: `excel_import.py:76-165, 200-206, 488-517`,
> `templates/migration/map.html:33-79`

### If a record is already in the system / إذا كان السجل موجوداً بالفعل

Sub-heading: *"Owners are matched by phone number, pets by name plus owner, visits
by pet plus date. / تتم مطابقة العملاء برقم الهاتف، والحيوانات بالاسم مع المالك،
والزيارات بالحيوان مع التاريخ."*

Three radios, `name="strategy"`, **`skip` pre-selected**:

| Value | Label | Description as written on screen | What it does |
|---|---|---|---|
| `skip` | `Leave it as it is / تركه كما هو` | *"keep what is already in the system and do not import that row again. This is the safe choice."* | matched owner/pet/visit untouched, counted as skipped |
| `update` | `Update it / تحديثه` | *"fill in details from the file. Empty cells in the file never erase information you already have."* | owner and pet receive an `UPDATE` built only from non-empty values (pets additionally drop `"Unknown"`), plus `updated_at`. **Visits are still skipped** |
| `create` | `Add it anyway / إضافته على أي حال` | *"create a second record. Only choose this if you know the matches are different people or animals."* | a second owner / pet / visit row is inserted regardless |

An unrecognised value posted for `strategy` silently falls back to `skip`.

> Source: `templates/migration/map.html:81-119`,
> `excel_import.py:36, 597-598, 726-747, 786-808, 832-864`

### Buttons

| Button | Effect |
|---|---|
| `Preview the import / معاينة الاستيراد` | `POST /migration/preview` |
| (text beside it) | *"Nothing is saved at this step. / لا يتم حفظ أي شيء في هذه الخطوة."* — accurate |
| `Choose a different file / اختيار ملف آخر` (top bar) | `GET /migration/` |

### The duplicate-field guard

An inline script on submit collects every `.mapsel` with a non-empty value and, if
any field is chosen twice, calls `e.preventDefault()` and alerts:

> *"Two columns are set to the same thing: {labels}. Please pick a different field
> for one of them."* / *"يوجد عمودان مضبوطان على نفس الحقل: {labels}. من فضلك اختر
> حقلاً مختلفاً لأحدهما."*

With JavaScript disabled nothing is reported: `clean_mapping()` keeps the first
column claiming a field and silently discards later ones.

> Source: `templates/migration/map.html:137-148`, `excel_import.py:526-547`

---

## 6. Screen: Preview (Step 3)

**Purpose.** A complete dry run. The identical function that performs the import
is executed with `dry_run=True`, so the numbers on this page come from the same
code path that will do the writing.

**How to reach it.** Only by submitting the Step 2 form.

**Route.** `POST /migration/preview` · **Template.** `templates/migration/preview.html`
**Who can open it.** super_admin, clinic_owner, support_admin.

**Page header.** `Step 3 — Preview / الخطوة ٣ — المعاينة`, subtitle
`<filename> — <rows_total> rows read / صف تمت قراءته`.

**Top-bar button.** `Start over / البدء من جديد` → `/migration/`.

### The banner

Yellow `pf-alert-warning`, bold lead **`Nothing has been saved yet. / لم يتم حفظ
أي شيء حتى الآن.`** followed by *"This is a preview of what will happen. Your
database has not been touched. Review the numbers below, then confirm at the
bottom of the page."*

### What the route did before rendering

Re-read the staged file from disk, rebuilt the mapping from every posted field
named `col_*`, took `strategy` (default `skip`), then:

1. **Refused** if neither `owner_name` nor `owner_phone` is mapped — see below.
2. Ran `run_import(..., dry_run=True)` on an open connection with no transaction.
3. Saved the mapping under its header signature.
4. Wrote or deleted `<token>.failed.csv`.

> Source: `routes.py:229-281`

### The three count cards

`Owners / العملاء`, `Pets / الحيوانات`, `Visits / الزيارات`, each a three-row table:

| Row | Colour | Meaning |
|---|---|---|
| `Will be created / سيتم إنشاؤها` | green | rows that will be inserted |
| `Will be updated / سيتم تحديثها` | accent | existing rows that will be modified |
| `Will be skipped / سيتم تخطّيها` | muted | existing rows left alone |

Counts are of **distinct records**, not of spreadsheet rows: a file with one row
per visit repeats the same owner dozens of times and counts that owner once. The
Visits card's `Will be updated` row **is always 0** — there is no update path for
a visit in the engine (§9).

### N rows cannot be imported / صفاً لا يمكن استيراده

Shown only when `rows_failed` is non-zero. Red title, sub-heading *"The rest of
the file will still import. Fix these rows in your file and upload it again
afterwards — nothing will be duplicated. / سيتم استيراد بقية الملف. صحّح هذه
الصفوف في ملفك ثم ارفعه مرة أخرى — لن يتم تكرار أي شيء."*

| Control / column | Content |
|---|---|
| `Download these rows / تنزيل هذه الصفوف` | → `/migration/failed-rows.csv`; rendered only when `has_failed_csv` |
| `Row in your file / الصف في ملفك` | the Excel row number, counted with the header as row 1 |
| `What to fix / ما يجب تصحيحه` | the bilingual reason, `t(e.en, e.ar)` |

The five reasons a row can fail, in the order they are checked (first hit ends the
row):

| Trigger | Message shown |
|---|---|
| phone cell with no digits | `The phone number 'X' has no digits in it. Fix that cell in your file, or clear it.` / `رقم الهاتف «X» لا يحتوي على أي أرقام. صحّح هذه الخانة في ملفك أو اتركها فارغة.` |
| pet with no owner name and no phone | `This row has a pet but no owner name and no phone number. Add the owner's name or phone to this row.` / `هذا الصف يحتوي على حيوان بدون اسم عميل وبدون رقم هاتف. أضف اسم العميل أو رقم هاتفه إلى هذا الصف.` |
| unreadable date of birth | `The date of birth 'X' is not a date we can read. Use the form DD/MM/YYYY, for example 05/03/2021.` / `تاريخ الميلاد «X» غير مفهوم. استخدم الصيغة يوم/شهر/سنة، مثال ‎05/03/2021.` |
| unreadable visit date | `The visit date 'X' is not a date we can read. Use the form DD/MM/YYYY, for example 05/03/2021.` / `تاريخ الزيارة «X» غير مفهوم…` |
| non-numeric weight | `The weight 'X' is not a number. Write it as a plain number such as 4.5.` / `الوزن «X» ليس رقماً. اكتبه كرقم بسيط مثل ‎4.5.` |

The table is capped at **500** entries; the CSV is not capped, and nothing says
the table was truncated.

> Source: `excel_import.py:33, 611-616, 641-694`, `preview.html:51-90`

### Records already in the system / سجلات موجودة بالفعل في النظام

Shown only when the run produced duplicate notes. The sub-heading changes with the
strategy: *"You chose to leave these as they are."* / *"You chose to update
these."* / *"You chose to add them anyway."*

| Column | Content |
|---|---|
| `Row / الصف` | Excel row number |
| `What we found / ما وجدناه` | the bilingual note |

The five notes the engine can produce:

| Entity | Note |
|---|---|
| owner, `update` | `Owner already on file (matched on phone 01012345678) — details will be updated.` / `العميل موجود بالفعل (تمت المطابقة على رقم الهاتف …) — سيتم تحديث بياناته.` |
| owner, `skip` | `Owner already on file (matched on name Mona Abdel-Rahman) — left unchanged.` / `… — لم يتم تغييره.` |
| pet, `update` | `'Simba' is already registered to this owner — details will be updated.` / `«Simba» مسجّل بالفعل لدى هذا العميل — سيتم تحديث بياناته.` |
| pet, `skip` | `'Simba' is already registered to this owner — left unchanged.` / `… — لم يتم تغييره.` |
| visit | `A Vaccination visit for this pet on 2024-04-03 is already recorded.` / `توجد بالفعل زيارة (Vaccination) لهذا الحيوان بتاريخ 2024-04-03.` |
| visit with no pet | `This row has a visit date but no pet name, so the visit was not imported.` / `هذا الصف يحتوي على تاريخ زيارة بدون اسم حيوان، لذلك لم يتم استيراد الزيارة.` |

The match phrase names the phone when the row had one and the name otherwise.
Capped at **300** entries, silently.

> Source: `excel_import.py:34, 617-622, 728-745, 793-807, 843-849, 865-869`

### First rows, exactly as they will be stored / أول الصفوف كما سيتم حفظها تماماً

Up to **20** rows — the first twenty *usable* rows, never a sample from the middle.
There is no paging.

The card's sub-heading is the phone-normalisation explanation, given in full in
both languages: *"Phone numbers are stored in one standard form: Arabic digits
become English digits, spaces and "+" are removed, and the country code 20 becomes
a leading 0. So 01012345678, +201012345678 and 0020 101 234 5678 are all stored as
01012345678 and count as the same person."*

| Column | Shows |
|---|---|
| `Row / الصف` | Excel row number |
| `Owner / العميل` | the cleaned owner name, **or the phone when the name is blank**; `—` if neither |
| `Phone / الهاتف` | the normalised number, `dir="ltr"` monospace; if it differs from the original the original follows in small grey brackets |
| `Pet / الحيوان` | cleaned pet name, or `—` |
| `Species / النوع` | the species cell, or `Unknown` when a pet name is present and the cell is blank |
| `Date of birth / تاريخ الميلاد` | normalised `YYYY-MM-DD`, or `—` |
| `Visit / الزيارة` | `<date> <type>`, or `—` when there is no visit date |
| `Action / الإجراء` | up to three badges — the owner, pet and visit decisions, each `created`, `updated` or `skipped` |

The `Action` badges are the raw English keys and are **not** translated.

> Source: `excel_import.py:32, 873-891`, `preview.html:131-189`

### Step 4 — Import for real / الخطوة ٤ — تنفيذ الاستيراد

The final card. Body text: *"A full backup will be taken first. If the backup
cannot be created, the import will not run and your data stays untouched.
Everything is imported in one go — if any part fails, nothing at all is saved."*
All three claims match the code.

| Control | Effect |
|---|---|
| `Import now / تنفيذ الاستيراد الآن` | `POST /migration/commit`, behind an `onsubmit` confirm: *"Import this file now? A backup will be taken first. / هل تريد استيراد هذا الملف الآن؟ سيتم أخذ نسخة احتياطية أولاً."* |
| `Cancel / إلغاء` | `GET /migration/index` |
| hidden fields | `_csrf_token`, `strategy`, and one `col_<index>` per **mapped** column — columns set to *Do not import* are simply not posted |

> Source: `preview.html:191-216`

### Error paths off this screen

| Situation | What happens |
|---|---|
| Neither owner name nor phone mapped | the **map screen is re-rendered** with a yellow flash *"Choose which column holds the owner's name or phone number — records cannot be imported without one of them. / اختر العمود الذي يحتوي على اسم العميل أو رقم هاتفه؛ لا يمكن استيراد السجلات بدون أحدهما."* Your other choices survive |
| The staged file is gone | yellow flash *"Your uploaded file is no longer available. Please upload it again. / لم يعد الملف الذي رفعته متاحاً. من فضلك ارفعه مرة أخرى."*, redirect to `/migration/` |
| The staged file no longer parses | red flash `{en} \| {ar}` from `SpreadsheetError`, redirect to `/migration/` |

> Source: `routes.py:232-255`

---

## 7. Screen: Import finished (Step 4 result)

**Purpose.** Confirm what was written, name the backup, and offer the failed rows.

**How to reach it.** Only by submitting the preview page's Import form.

**Route.** `POST /migration/commit` · **Template.** `templates/migration/result.html`
**Who can open it.** **super_admin, clinic_owner only.**

**Page header.** `Import finished / انتهى الاستيراد`, subtitle `<filename>`.
**Top-bar button.** `Import another file / استيراد ملف آخر` → `/migration/`.

### The order of operations

1. Re-read the staged file. If it is gone or unreadable → flash and redirect.
2. Rebuild the mapping from the posted `col_*` fields and read `strategy`.
3. **`bk.run_backup()` — the gate.** If it does not report `success`, log an error
   and stop. Nothing is written.
4. `with conn:` → `run_import(..., dry_run=False, created_by=f"import:{username}")`.
   Any exception rolls back the whole file.
5. Write the `audit_log` row.
6. Rewrite (or delete) `<token>.failed.csv`.
7. Render.

> Source: `routes.py:283-360`

### The success banner

Green, bold lead **`Your data is in. / تم إدخال بياناتك.`** then *"A backup was
taken before anything was written:"* followed by `backup.filename` in `<code>` and,
when `size_kb` is present, `(18432.6 KB)`.

### The three count cards

Identical layout to the preview, relabelled `Created / تم إنشاؤها`,
`Updated / تم تحديثها`, `Skipped / تم تخطّيها`. They come from the same
`report["counts"]` structure, so a matching preview and result is the expected
outcome. Visits `Updated` is always 0 here too.

### N rows were not imported / صفاً لم يتم استيراده

Same shape as the preview's failure card, with sub-heading *"Download them, fix
them in Excel, and upload the corrected file. Rows that came in successfully will
not be duplicated. / نزّلها وصحّحها في إكسل ثم ارفع الملف المصحَّح. الصفوف التي تم
استيرادها بنجاح لن تتكرر."* and a primary-styled `Download rows to fix / تنزيل
الصفوف المطلوب تصحيحها` button.

The duplicates card and the 20-row sample are **not** rendered on this page.

### Where to find your data / أين تجد بياناتك

| Button | Goes to |
|---|---|
| `Owners / العملاء` | `crm.owners_list` |
| `Visits / الزيارات` | `visits.visits_list` |

Below them, in small grey text: `Started / البداية: <report.started_at> · Finished
/ النهاية: <report.finished_at>` — both `YYYY-MM-DD HH:MM:SS` from the engine.

There is no link to the newly created pets, no per-record list, and no "undo".

### Error paths off this screen

| Situation | What happens |
|---|---|
| Role is `support_admin` | *"You don't have permission to access this page."*, redirect to launcher. Nothing written, **no backup taken** |
| Backup failed | red flash *"Nothing was imported. The safety backup could not be created, so we stopped before changing any of your data. Ask your administrator to check the Backup Manager. Reason: {reason} / لم يتم استيراد أي شيء. تعذّر إنشاء النسخة الاحتياطية، لذلك توقّفنا قبل تغيير أي من بياناتك. اطلب من مسؤول النظام مراجعة مدير النسخ الاحتياطي. السبب: {reason}"*, redirect to `/migration/`. One `{reason}` seen in practice: `A restore is in progress — backup skipped` |
| The import raised | full rollback, then red flash *"The import stopped and every change was undone — your data is exactly as it was before. Please send this message to support so they can help: {exc} / توقّف الاستيراد وتم التراجع عن كل التغييرات، وبياناتك كما كانت تماماً. من فضلك أرسل هذه الرسالة للدعم الفني: {exc}"*. The backup taken a moment earlier remains on disk |
| Staged file gone or unreadable | as on the preview screen |

> Source: `routes.py:290-329`, `platform/models/backup.py:180-182, 377-404`,
> `platform/blueprints/auth/routes.py:186-190`

---

## 8. Download: rows_to_fix.csv

**Route.** `GET /migration/failed-rows.csv`
**Who can use it.** super_admin, clinic_owner, support_admin.
**Reached from.** The `Download these rows` button on the preview and the
`Download rows to fix` button on the result page. There is no menu entry.

**Response.** `Content-Type: text/csv; charset=utf-8`,
`Content-Disposition: attachment; filename="rows_to_fix.csv"`, body encoded
`utf-8-sig` — the BOM is deliberate so Excel opens the Arabic columns as Arabic
rather than mojibake.

**Columns**, in order:

`Row in your file`, `Why it was not imported`, then all nineteen field keys as
literal keys: `owner_name`, `owner_phone`, `owner_email`, `owner_address`,
`owner_notes`, `pet_name`, `pet_species`, `pet_breed`, `pet_sex`, `pet_dob`,
`pet_weight`, `pet_color`, `pet_microchip`, `pet_notes`, `visit_date`,
`visit_type`, `visit_doctor`, `visit_complaint`, `visit_notes`.

A real line:

```
7,The weight 'heavy' is not a number. Write it as a plain number such as 4.5.,Hany Samir,01555000222,,,,Rex,,,,,heavy,,,,,,,,
```

**Values are the original cell contents**, cleaned but not normalised — `heavy`
above, not a corrected number — so the clinic can see what it typed.

**Round-tripping works.** Confirmed by running `guess_mapping()` over this file's
own header row: all nineteen field-key columns map straight back onto themselves,
and both report columns come back as *Do not import*. The corrected CSV can be
uploaded as-is without deleting the two extra columns.

**If the file is not there** — no token in the session, or the `.failed.csv` was
removed — the route flashes *"Your uploaded file is no longer available. Please
upload it again."* and redirects to `/migration/` rather than returning a 404.

> Source: `platform/blueprints/migration/routes.py:125-137, 363-380`,
> `platform/migrations/excel_import.py:897-911`

---

## 9. Command line: `migrations/excel_import.py`

The engine is deliberately free of Flask, so the same code runs from a shell.

```
python migrations/excel_import.py FILE --db data/platform.db [--apply] [--strategy skip|update|create]
```

| Flag | Meaning |
|---|---|
| `FILE` | path to the `.xlsx` or `.csv` |
| `--db` | SQLite path; may be replaced by `PLATFORM_DB_PATH`. Missing both → `no database given — pass --db or set PLATFORM_DB_PATH` |
| `--apply` | actually write, inside `with conn:`. Without it, dry run |
| `--strategy` | default `skip` |

Output: the guessed mapping one line per column (`'اسم العميل' -> owner_name`,
`(ignored)` for unmapped), the row totals, the per-entity counts, up to 20 row
errors, and on a dry run `Dry run — nothing was written. Re-run with --apply to
import.` An unreadable file prints `ERROR: <the same English message the wizard
shows>` and returns exit code 1.

**No backup, no audit row, no saved mapping, no way to correct the mapping, and
SQLite only** — `main()` calls `sqlite3.connect()` directly, so it cannot drive a
PostgreSQL deployment even though `run_import()` itself is portable SQL.

> Source: `platform/migrations/excel_import.py:915-968`

---

## 10. What an import actually writes

All three inserts happen inside the single `with conn:` transaction opened by
`/commit`. `run_import()` never opens one itself — the caller owns it, which is
why the CLI wraps it too.

### `owners`

| Column | Value |
|---|---|
| `full_name` | the cleaned owner name — **or the normalised phone when the name is blank** |
| `phone` | the normalised phone (`""` if none) |
| `whatsapp_phone` | **the same value as `phone`**, always |
| `email`, `address`, `notes` | from `owner_email`, `owner_address`, `owner_notes` |
| `created_by` | `import:<username>` |
| `created_at`, `updated_at` | run start time, `YYYY-MM-DD HH:MM:SS` |
| `full_name_ar`, `address_ar`, `preferred_contact`, `preferred_doctor`, `preferred_branch`, `vip_flag`, `outstanding_balance`, `marketing_consent` | **never written** — schema defaults (`WhatsApp`, `1`, `0`, `0.0`, `1`) |

### `pets`

| Column | Value |
|---|---|
| `owner_id` | the owner resolved for this row |
| `pet_name` | cleaned |
| `species` | from `pet_species`, or `Unknown` |
| `breed`, `color`, `microchip_id`, `notes` | cleaned text |
| `sex` | `normalize_sex()` **only if a `pet_sex` column was mapped**, otherwise `Unknown` |
| `dob` | normalised `YYYY-MM-DD` or NULL |
| `weight_kg` | float or NULL |
| `is_active` | `1` |
| `created_at`, `updated_at` | run start time |
| `created_by` | **not written — the table has no such column** |
| `neutered`, `allergies`, `chronic_conditions`, `diet_notes`, `insurance_number` | **never written** — schema defaults |

### `visits`

| Column | Value |
|---|---|
| `owner_id`, `pet_id` | resolved for this row |
| `visit_date` | normalised `YYYY-MM-DD` |
| `visit_type` | mapped through the vocabulary below |
| `status` | **`Completed`**, hardcoded |
| `doctor_name` | free text from `visit_doctor` |
| `chief_complaint` | from `visit_complaint` |
| `notes` | from `visit_notes` |
| `created_by` | `import:<username>` |
| `created_at`, `updated_at` | run start time |
| `appointment_id`, `doctor_id`, `room`, `symptoms`, `weight_kg`, `temp_c`, `heart_rate`, `respiratory_rate` | **never written** — NULL. `branch_id` defaults to `1` |

### Normalisation rules applied on the way in

| Field | Rule |
|---|---|
| any text | invisible/bidi characters stripped, NFC normalised, whitespace collapsed; `""`, `none`, `nan`, `null`, `n/a`, `na`, `-`, `--`, `#n/a` all become empty |
| phone | Arabic-Indic digits → ASCII; non-digits dropped; leading `00` removed; leading `20` + ≥9 digits → `0`; a `0` prepended if missing |
| date | eight formats, **day-first**; time part discarded; unparseable → the row fails |
| weight | Arabic digits → ASCII; everything except digits, `.` and `-` stripped; unparseable → the row fails |
| sex | `m`/`male`/`ذكر`/`زكر` → `Male`; `f`/`female`/`انثي`/`انثى`/`أنثى`/`انثه` → `Female`; blank → `Unknown`; **anything else stored verbatim** |
| visit type | `Consultation`, `Vaccination`, `Surgery`, `Follow-up`, `Emergency`, `Wellness` — anything unrecognised becomes `Consultation` |

### Duplicate keys

| Record | Matched on |
|---|---|
| owner | normalised phone against `owners.phone` **or** `owners.whatsapp_phone`; when the row has no phone, exact `owners.full_name` |
| pet | exact `pets.pet_name` **and** `owner_id` |
| visit | `pet_id` **and** `visit_date` **and** `visit_type` |

### Written outside the transaction

| What | Where |
|---|---|
| safety backup | `models/backup.py` archive, e.g. `platform_backup_20260820_142211.db`, plus an offsite copy if configured — taken **before** the import and kept either way |
| saved mapping | `settings` row `import_map_<sha1-16>`, category `migration`, `updated_by` = your username — written at **preview** |
| audit trail | `audit_log`: `action='data_import'`, `module='migration'`, `entity_type='import'`, `entity_id` = the staging token, `details` = the summary line shown on the landing page |
| failed rows | `<uploads>/import_staging/<token>.failed.csv` |

> Source: `platform/migrations/excel_import.py:186-306, 697-711, 749-757, 767-776,
> 786-822, 833-864`, `platform/blueprints/migration/routes.py:116-137, 294-360`,
> `platform/models/database.py:1212-1332, 2946-2976`

---

## 11. Where imported data shows up elsewhere

| Module | What appears |
|---|---|
| **CRM** | every owner in `/crm/owners`, every pet in `/crm/pets` and on its owner's page, each pet's record carrying its imported visit history |
| **Visits / Clinical** | rows across the clinic's whole history, all with status `Completed` |
| **Landing page** | the three counters rise; the run joins `Previous imports` |
| **Backup Manager** | one new archive per commit |
| **Audit Log** | one `data_import` row per commit |
| **WhatsApp** | every imported owner has a `whatsapp_phone` and `marketing_consent=1` by default, so they are inside reach of the campaign and reminder screens the moment the import finishes |
| **Finance / Accounting** | **nothing.** No invoice, payment, deposit or balance is created. Imported visits are medically complete and financially invisible |
| **Reports** | clinical and patient counts include them; anything joining `visits.doctor_id` does not, because it is NULL |

---

## Known limits

### Not implemented at all

- **No money, of any kind.** There is no price, fee, charge, paid, balance,
  discount or currency target field. **Service prices cannot be imported.** Neither
  can historic invoices, payments, deposits or outstanding balances. A `Fee (EGP)`
  or `المبلغ` column can only be set to *Do not import* or squeezed into
  `visit_notes` as free text.
- **No catalogue.** Services, service prices, products, product prices, stock
  levels and suppliers have no import path in this module or anywhere else.
- **No rest of the medical record.** No appointments, vaccinations, prescriptions,
  lab results, imaging studies, diagnoses rows, allergies, chronic conditions,
  neuter status, diet notes, insurance number, attachments, or visit vitals
  (weight, temperature, pulse, respiration on the *visit* — the pet's weight is
  the only vital that comes across, and it lands on the pet, not the visit).
- **No Arabic-name columns.** `owners.full_name_ar`, `owners.address_ar` and
  `pets.pet_name_ar` exist in the schema and are preferred by the app's `loc()`
  data-localisation helper, but nothing in the importer writes them. An Arabic name
  goes into `full_name` intact and displays by fallback; a *pair* of names cannot be
  imported.
- **No doctor link.** `visit_doctor` writes `visits.doctor_name` as free text;
  `visits.doctor_id` stays NULL, so imported visits are attached to no staff record.
- **No import template.** No blank template to download, no example file, no
  documentation link on any screen. A clinic discovers its column names were wrong
  only after uploading.
- **No undo.** Nothing here reverses an import. The only route back is Backup &
  Restore, restoring the archive the commit itself made — which discards everything
  else done since.
- **No progress indication.** A 20,000-row commit is one synchronous request. No
  spinner, no percentage, no job queue; the page simply does not answer until done.
- **No import provenance.** One line of audit text per import. No import id on the
  created records, so "which owners came from the March file" is unanswerable.

### Labels that do not match behaviour

- **`Will be updated` / `Updated` on the Visits card can never be non-zero.** There
  is no update branch for a visit: matched visits are skipped under both `skip` and
  `update`, and duplicated under `create`. The row is rendered on both the preview
  and the result page anyway.
  > `excel_import.py:832-864`, `preview.html:38-41`, `result.html:37-40`
- **"Anything unrecognised becomes Consultation, with the original text preserved
  in the visit notes by the caller"** — the caller does not do this. `visits.notes`
  is written from the `visit_notes` column only, so `Dental`, `X-Ray` and every
  other unmapped word is discarded.
  > `excel_import.py:288-290, 853-861`
- **The oversize-file flash in `upload()` is dead code** and says so in its own
  comment: Werkzeug rejects the body before the view runs, so the generic 413 page
  wins. The message a clinic actually sees is the one in `app.py`.
  > `routes.py:176-188`, `app.py:473-486`
- **`accept=".xlsx,.csv"` filters the OS picker only.** `.txt` is accepted by the
  server and read as CSV.
  > `index.html:45-46`, `excel_import.py:352`

### Column guessing

- **A column titled exactly `Type` is mapped to Species, not Visit type.** `"type"`
  is an exact alias of `pet_species`, and `pet_species` precedes `visit_type` in the
  alias dictionary. Confirmed by running `guess_mapping()`. Two harms at once: every
  pet gets a species of `Dental` or `Vaccination`, and with no `visit_type` mapped
  every visit becomes `Consultation` — which then triggers the collapse below.
- **The `Example values` column is the only defence.** It samples the first three
  data rows only, so a column that is blank at the top of the file shows `—` and
  tells you nothing.
- **The guess is not shown as a guess.** A pre-selected dropdown looks identical to
  a confirmed choice.

### Data fidelity

- **Three Arabic visit types never match and silently become `Consultation`.**
  `normalize_visit_type()` looks the *folded* value up in a table whose Arabic keys
  were never folded, so any key containing `ة` or `ئ` is unreachable. Verified
  against the table's own keys: `جراحة` (Surgery), `عملية` (Surgery) and `متابعة`
  (Follow-up) all return `Consultation`. `كشف`, `تطعيم`, `تحصين`, `طوارئ`, `طواري`,
  `تجميل`, `تحليل` do match.
  > `excel_import.py:291-305`
- **Two visits for the same pet on the same day of the same type become one, with
  no record anywhere.** The in-run key is `(pet_id, visit_date, visit_type)`; a
  repeat sets `visit_action = "skipped"` **without** a duplicate note and
  **without** incrementing any counter. Nothing on the preview, the result page or
  the CSV mentions it. Verified: three visit rows for one pet produced two visits.
  > `excel_import.py:833-864`
- **A comma decimal separator multiplies the weight by ten.** Verified: `4,5` is
  stored as `45.0` kg. No failure, no warning. `٤.٥` and `4.5 kg` are both correct.
  > `excel_import.py:264-276`
- **Almost any cell with a digit is accepted as a phone number.** Only a cell with
  *zero* digits fails. Verified: `2010` → `02010`, `20` → `020`. An extension or
  room number in the phone column becomes an owner's identity key, and two clients
  sharing such a value merge into one owner. No length check.
  > `excel_import.py:208-232`
- **Owner and pet matching is folded within a file but exact against the database.**
  The in-run cache keys on `fold(name)`; the lookups are
  `WHERE full_name=?` and `WHERE pet_name=? AND owner_id=?` on the cleaned,
  unfolded text. So `أحمد الجوهري` and `احمد الجوهري` are one owner within a single
  import and two owners across two imports.
  > `excel_import.py:697-711, 767-776`
- **An owner is matched by name only when the row has no phone.** With a phone
  present the name is never consulted, so the same person under two numbers becomes
  two owners — and there is nothing in this module to merge them afterwards.
- **An unrecognised sex value is stored verbatim.** `pets.sex` can end up holding
  `Neutered male` or `Male?`.
  > `excel_import.py:278-288`
- **Only the first worksheet is read**, with no list of the sheets ignored.
  > `excel_import.py:441`
- **`whatsapp_phone` is always set equal to `phone`**, with no way to import a
  separate WhatsApp number even though the schema has one.

### Lists and caps

- Errors on screen stop at **500**, duplicates at **300**, the sample table at
  **20** — none of the three says it was truncated. The failed-rows CSV is
  **uncapped**, so a file with 900 bad rows shows 500 and downloads 900.
  > `excel_import.py:32-34`
- The sample is always the *first* twenty usable rows; there is no paging and no
  way to sample from the middle of a large file.
- `Previous imports` is the newest 20 audit rows, unfiltered and unpaged, with no
  link from a row to anything.

### The downloaded CSV

- **The reason column is English only.** Both texts exist in the report and both
  are shown on screen, but `failed_rows_csv()` writes `item["reason"]`, which is
  the `en` text.
  > `excel_import.py:611-616, 897-911`
- **Column titles are field keys, not labels** — `owner_phone`, not
  `Phone / رقم الهاتف`.
- **Columns you did not map are absent.** The values come from `_row_values()`,
  which walks the mapping only, so a *Do not import* column is missing from the
  download. The CSV is not a faithful extract of the bad rows, only of their mapped
  parts.
  > `excel_import.py:557-559`
- **Rows dropped for other reasons never reach it** — a visit with no pet name, and
  a silently-collapsed same-day visit, are neither failures nor duplicates in the
  report's sense.
- **Re-previewing overwrites it, and deletes it when the new run has no failures.**
  Download before you re-preview.
  > `routes.py:125-137`

### Permissions

- **The module cannot be granted or revoked.** `migration` is absent from
  `ALL_PERMISSIONS`, so it never appears on Roles & Permissions and the module gate
  falls open. Changing who may import requires editing `routes.py:38-39`.
- **`support_admin` is shown a commit button it cannot use** (§2).

### Housekeeping and safety

- **Staged uploads are swept only as a side effect of a new upload**, and only when
  over 24 hours old. A one-off import leaves the clinic's entire client list
  unencrypted in `<uploads>/import_staging/` indefinitely. The code marks this a
  deliberate shortcut with a `ponytail:` note naming the ceiling.
  > `routes.py:53-72`
- **The `import_file` session key is never cleared**, including after a successful
  commit — which is what keeps the CSV download working, and also means a stale
  token survives until the session expires.
- **`import_map_*` settings rows accumulate**, one per distinct header layout ever
  previewed. Nothing lists or clears them and they are invisible outside the
  database.
- **`/commit` does not re-check the owner-name-or-phone rule** that `/preview`
  enforces. A hand-crafted POST straight to `/commit` with neither mapped is
  accepted; every row is then treated as blank and nothing is imported. Not
  reachable through the UI.
  > `routes.py:240-255` (present) vs `:290-292` (absent)
- **Preview and commit are two independent parses** of the file on disk. The commit
  re-reads and re-runs rather than replaying the preview's decisions.

### Bilingual coverage

This is one of the better-covered modules: **every** label, banner, button, flash,
row error and duplicate note across all four screens exists in both languages,
including the strings generated by the engine rather than the templates. Three
exceptions, all narrow:

- the `Action` badges on the preview sample table are the raw English keys
  `created` / `updated` / `skipped`;
- the CSV's column titles are English field keys;
- the CSV's reason column carries only the English text.

---

> Source: `platform/blueprints/migration/routes.py`,
> `platform/blueprints/migration/__init__.py`,
> `platform/templates/migration/index.html`, `map.html`, `preview.html`,
> `result.html`, `platform/migrations/excel_import.py`,
> `platform/models/backup.py`, `platform/models/database.py`,
> `platform/blueprints/auth/routes.py`, `platform/app.py`,
> `platform/templates/base.html`, `platform/blueprints/launcher/routes.py`.
