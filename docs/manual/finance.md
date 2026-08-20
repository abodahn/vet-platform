# Finance & Accounting — Reference Manual

**Modules:** Finance / الفواتير والمالية · Accounting / المحاسبة
**URL prefixes:** `/finance/` and `/accounting/`
**Blueprints:** `finance`, `accounting`

This chapter is a **screen-by-screen reference**. It describes only what the code
in `blueprints/finance/routes.py`, `blueprints/accounting/routes.py` and
`templates/finance/*.html`, `templates/accounting/*.html` actually does today.
Anything that is present in the database but has no screen, or a control that
does not do what its label suggests, is listed under
[Known limits](#known-limits) rather than described as working.

Money is EGP throughout. There is no currency selector on any finance screen;
`clinic.currency` exists in the schema and no finance template reads it.

> Source: `platform/app.py:244`, `platform/app.py:255` (blueprints registered),
> `platform/blueprints/finance/__init__.py:1-5`,
> `platform/blueprints/accounting/__init__.py:1-5`

---

## 1. Getting into the modules

| Door | Where | Goes to |
|---|---|---|
| Sidebar → BUSINESS / الأعمال → **Finance / الفواتير والمالية** | every page | `/finance/` (Finance Dashboard) |
| Sidebar → BUSINESS / الأعمال → **Accounting / المحاسبة** | every page | `/accounting/` (Accounting Dashboard) |
| Launcher card **Billing & Invoicing / الفواتير والفوترة** (🧾) | `/` | `/finance/invoices` |
| Launcher card **Finance & Accounting / المالية والمحاسبة** (💰) | `/` | `/accounting/` |
| Client record → **Account / الحساب** button | `/crm/owners/<id>` | `/finance/owners/<id>/credit` |
| Visit record → invoice chip | `/visits/<id>` | `/finance/invoices/<inv_id>` |

Both sidebar entries are shown to **every signed-in user** — the BUSINESS group
carries no role condition. A user whose role does not hold the grant will see
the link, click it, and be bounced back to the launcher with *"You don't have
permission to access this page."* See §2.

The two launcher cards *are* role-filtered, but by a hardcoded list that does
not match the permission grants — see [Known limits](#permissions).

> Source: `platform/templates/base.html:182-224` (BUSINESS sidebar group, no
> role guard), `platform/blueprints/launcher/routes.py:277-306` (module cards),
> `:579` (`_visible_modules`), `platform/templates/crm/owner_detail.html:11`

---

## 2. Who can open what

Two independent gates apply to every screen in both modules, and **both must
pass**:

1. **The module grant**, checked for every route in the blueprint including
   routes that carry no role list of their own. `finance` maps to the
   `invoicing` grant key; `accounting` maps to `accounting`. `super_admin`
   bypasses this gate entirely.
2. **The route's own role list**, where one is declared with `@role_required`.

A grant can only ever narrow. It never widens.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-131` (`_permission_denied`), `:140-151` (`_BP_PERMISSION`, maps
> `finance → invoicing`), `:167-190` (`role_required`),
> `platform/models/database.py:4302-4329` (`ALL_PERMISSIONS`),
> `:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

Roles holding **`invoicing`** by default: clinic_owner, branch_manager,
reception, finance (plus super_admin, exempt).
Roles holding **`accounting`** by default: clinic_owner, branch_manager,
finance, auditor (plus super_admin).

Note the asymmetry: **reception can bill but cannot open Accounting**, and
**auditor can open Accounting but cannot open any `/finance/` page at all.**

### Effective access, per screen

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| Finance Dashboard | `GET /finance/` | none (login only) | super_admin, clinic_owner, branch_manager, reception, finance |
| Invoices list | `GET /finance/invoices` | none | same as above |
| New invoice | `GET/POST /finance/invoices/new` | none | same as above |
| Invoice detail | `GET /finance/invoices/<id>` | none | same as above |
| Record payment | `POST /finance/invoices/<id>/pay` | none | same as above |
| Edit invoice | `GET/POST /finance/invoices/<id>/edit` | none | same as above |
| Print invoice | `GET /finance/invoices/<id>/print` | none | same as above |
| Invoice PDF | `GET /finance/invoices/<id>/pdf` | none | same as above |
| Send invoice on WhatsApp | `POST /finance/invoices/<id>/whatsapp` | none | same as above |
| Apply account credit | `POST /finance/invoices/<id>/apply-credit` | none | same as above |
| Client account / deposits | `GET/POST /finance/owners/<id>/credit` | none | same as above |
| Estimates list | `GET /finance/estimates` | none | same as above |
| New estimate | `GET/POST /finance/estimates/new` | none | same as above |
| Estimate detail | `GET /finance/estimates/<id>` | none | same as above |
| Estimate decision | `POST /finance/estimates/<id>/decide` | none | same as above |
| Convert estimate | `POST /finance/estimates/<id>/convert` | none | same as above |
| Estimate print | `GET /finance/estimates/<id>/print` | none | same as above |
| **Credit note** | `POST /finance/invoices/<id>/credit-note` | super_admin, clinic_owner, branch_manager, finance | super_admin, clinic_owner, branch_manager, finance — **not reception** |
| **Finance Expenses** | `GET/POST /finance/expenses` | super_admin, clinic_owner, branch_manager, finance, auditor | super_admin, clinic_owner, branch_manager, finance |
| **Financial Reports** | `GET /finance/reports` | same as above | same as above |
| **Reports Excel export** | `GET /finance/reports/export/xlsx` | same as above | same as above |
| Accounting Dashboard | `GET /accounting/` | none | super_admin, clinic_owner, branch_manager, finance, auditor |
| P&L report | `GET /accounting/pl` | none | same as above |
| Cash flow | `GET /accounting/cashflow` | none | same as above |
| Accounting Expenses | `GET /accounting/expenses` | none | same as above |
| Add expense | `POST /accounting/expenses/new` | none | same as above |
| Daily closing | `GET/POST /accounting/closing` | none | same as above |
| Budget | `GET/POST /accounting/budget` | none | same as above |

**`auditor` is named on three `/finance/` route role lists but cannot reach any
of them.** Its default grant set is `["reports","audit","accounting"]`, which
does not include `invoicing`, so the module gate rejects it before the role
list is read. To make those role lists meaningful an administrator must add
the `invoicing` grant to the `auditor` role on the Roles screen.

If the `roles` table has never been seeded (`permissions_json` empty), the
module gate **falls open** for every built-in role, and the effective sets
above widen to everyone signed in. On the database inspected while writing
this chapter the defaults were seeded, so the table above holds.

> Source: `platform/blueprints/auth/routes.py:223-250` (`_role_permissions`,
> `None` = fall open), `:405-428` (`has_permission`),
> `platform/models/database.py:4381-4394` (`seed_default_permissions`)

---

## 3. Things that apply to every screen

- **Bilingual.** Every label goes through `t('English', 'العربية')`. The page
  switches to Arabic and RTL when the signed-in user's language is `ar`. Where
  a label below is given as *English / Arabic*, that is the pair in the
  template. Labels with no Arabic given are English-only in the code.
- **CSRF.** Every POST form is protected. Some templates carry an explicit
  `_csrf_token` hidden input; the rest rely on `platform.js`, which injects one
  into any POST form on submit. **JavaScript is therefore required to save
  anything.**
- **Owner pickers search the server.** Owner dropdowns on the invoice and
  estimate forms render **no options at all** on page load. Type two or more
  characters and the box queries `/crm/owners/search-json`, which returns the
  first 25 matches from the whole owners table. With JavaScript off, no owner
  can be selected and the form cannot be submitted.
- **Money parsing.** The payment, credit-note, deposit, refund and apply-credit
  boxes accept thousands separators (`1,500`), Arabic-Indic digits (`٥٠٠`), a
  leading `EGP` / `ج.م` / `£` / `$`, and stray spaces. A value that still will
  not parse is **rejected with a message**, never silently treated as zero.
  Line-item Qty / Unit Price / Disc% boxes on the invoice and estimate forms
  use a more forgiving parser that falls back to a default instead of erroring.
- **Money is stored as floating point** and rounded to 2 decimals at each step.
  See `docs/MONEY_PRECISION.md`.

> Source: `platform/app.py:359-366`, `:369-459` (context processor: `t`, `loc`,
> `clinic`, `csrf_token`, `payment_methods`),
> `platform/static/js/platform.js:129-146` (CSRF auto-inject),
> `:405-441` (`_remoteSearch`), `:442-475` (`initSearchableSelect`),
> `platform/blueprints/crm/routes.py:545-560` (`owner_search_json`),
> `platform/models/money.py:55-82` (`form_amount`),
> `platform/blueprints/finance/routes.py:35-54` (`_num`)

### Invoice statuses

| Status | Meaning | Set by |
|---|---|---|
| `Unpaid` | nothing paid | `create_invoice` |
| `Partial` | some paid, balance remains | payment reconciliation |
| `Paid` | balance below half a piastre | payment reconciliation |
| `Cancelled` | fully credited | credit-note route |

Statuses are stored in English in the database and rendered untranslated on
every list and badge, in both languages.

> Source: `platform/models/database.py:3578-3618` (`create_invoice`),
> `platform/models/payments/__init__.py:437-471` (`_reconcile_invoice`),
> `platform/blueprints/finance/routes.py:625-635`

### How money actually gets recorded

Recording a payment does **not** just bump a number on the invoice. It creates
a *payment intent* (one row per attempt, including failures), captures it
through a *gateway*, writes a *ledger row* in `payments`, and then recomputes
`paid_amount` / `due_amount` / `status` by **summing the ledger**. Refunds are
written as negative ledger rows rather than as edits.

`received_at` on the ledger row is stamped in **clinic-local time**, which is
what "Today's Revenue" and the Daily Closing compare against.

> Source: `platform/models/payments/__init__.py:130-190` (`create_intent`,
> idempotent), `:193-223` (`capture`), `:382-423` (`_succeed`, the ledger row),
> `:437-471` (`_reconcile_invoice`),
> `platform/models/database.py:3911-3938` (`add_payment`, a thin wrapper)

### Payment methods

The **Method / طريقة الدفع** dropdown on the invoice screen is built from the
gateway registry, not a hardcoded list. Over-the-counter methods always appear;
an online gateway appears only once its keys are configured.

| Value | Label (EN / AR) | Type |
|---|---|---|
| `cash` | Cash / نقدي | counter |
| `card` | Card (terminal) / بطاقة (ماكينة) | counter |
| `transfer` | Bank transfer / تحويل بنكي | counter |
| `instapay` | InstaPay / إنستاباي | counter |
| `insurance` | Insurance / تأمين | counter |
| `paymob` | Card / Wallet — بطاقة / محفظة | online, hidden unless `PAYMOB_SECRET_KEY`, `PAYMOB_PUBLIC_KEY` and `PAYMOB_HMAC_SECRET` are all set |

If the registry cannot be read the dropdown falls back to a single **Cash /
نقداً** option.

> Source: `platform/models/payments/cash.py:22-66`,
> `platform/models/payments/paymob.py:68-99`,
> `platform/models/payments/__init__.py:113-127` (`available`),
> `platform/templates/finance/invoice_detail.html:243-256`

---

## 4. Screen: Finance Dashboard

**What it is for:** the day's money at a glance, and the way into invoicing.
**How to reach it:** sidebar → BUSINESS → Finance, or `/finance/`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

Page title **Finance Dashboard / لوحة تحكم المالية**; the subtitle is today's
date.

### Toolbar buttons

| Button | Goes to |
|---|---|
| **+ New Invoice / فاتورة جديدة** | `/finance/invoices/new` |
| **All Invoices / جميع الفواتير** | `/finance/invoices` |

### The four counters

| Card | Shows | Computed from |
|---|---|---|
| 💵 **Today's Revenue / إيرادات اليوم**<br><small>Payments received today / المدفوعات المستلمة اليوم</small> | money that **arrived** today, whichever invoice it settled | `SUM(payments.amount)` where `DATE(received_at)` is today |
| 📅 **Month Revenue / إيرادات الشهر**<br><small>This calendar month / هذا الشهر الميلادي</small> | money that arrived since the 1st | same, from the 1st of this month to today |
| ⏳ **Outstanding / المستحق**<br><small>Unpaid + partial invoices / فواتير غير مدفوعة + جزئية</small> | total still owed, all time — **not** limited to a date range | `SUM(due_amount)` over invoices with status `Unpaid` or `Partial` |
| ✅ **Payments Today / مدفوعات اليوم**<br><small>Transactions / المعاملات</small> | a **count of invoices issued today** whose status is `Paid` or `Partial` — see [Known limits](#money-and-counting) | `COUNT(*)` on invoices |

All amounts are rendered with no decimals (`{:,.0f}`).

### 📈 Revenue — Last 30 Days / الإيرادات — آخر 30 يوم

A bar per day for the last 30 days. Hovering a bar shows `date: amount EGP`.
The two labels below the bars are the first and last dates in the series.

This chart is **accrual**, not cash: each day's bar is the sum of
`paid_amount` on invoices **issued** that day. It therefore does not match the
"Today's Revenue" counter above it, which is cash-basis. Days with no invoices
are absent from the series entirely rather than drawn as zero.

The card header carries a **Full Report / التقرير الكامل →** link to
`/finance/reports`. The whole card, link included, is hidden when there is no
revenue data at all.

### 🧾 Recent Invoices / الفواتير الأخيرة

The 10 most recently created invoices, newest first.

| Column | Content |
|---|---|
| Invoice # / رقم الفاتورة | invoice number, links to the invoice |
| Owner / المالك | client name, links to `/crm/owners/<id>`; `—` if absent |
| Pet / الحيوان | patient name, links to `/crm/pets/<id>`; `—` if absent |
| Date / التاريخ | issue date |
| Total / الإجمالي | invoice total, no decimals |
| Due / المستحق | balance outstanding, amber |
| Status / الحالة | `Paid` / `Unpaid` / `Partial` / `Cancelled` badge |
| (last) | **View / عرض →** link |

Header link **View All / عرض الكل →** goes to the invoices list. Empty state:
*"No invoices yet / لا توجد فواتير بعد"*.

> Source: `platform/blueprints/finance/routes.py:94-146`,
> `platform/models/database.py:3940-3991` (`get_finance_summary`),
> `:4016-4028` (`get_revenue_by_day`),
> `platform/templates/finance/dashboard.html:1-139`

---

## 5. Screen: Invoices list

**What it is for:** finding an invoice, and seeing what is owed across a set.
**How to reach it:** Finance Dashboard → *All Invoices*, or the launcher card
**Billing & Invoicing**, or `/finance/invoices`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

Subtitle shows *"N result(s) / نتيجة"*.

### Toolbar buttons

| Button | Goes to |
|---|---|
| 📋 **Estimates / عروض الأسعار** | `/finance/estimates` |
| **+ New Invoice / فاتورة جديدة** | `/finance/invoices/new` |

### Filter bar (GET)

| Control | Query param | Effect |
|---|---|---|
| **Search / بحث** (text, placeholder *Owner / Invoice # — المالك / رقم الفاتورة*) | `q` | case-insensitive substring match on owner name, invoice number **or** pet name. Applied **in Python after** the 200-row database fetch — see [Known limits](#lists-and-filters) |
| **Status / الحالة** (select) | `status` | exact match. Options: *All Statuses / جميع الحالات*, `Paid`, `Unpaid`, `Partial`, `Cancelled` |
| **From / من** (date) | `date_from` | `issue_date >=` |
| **To / إلى** (date) | `date_to` | `issue_date <=` |
| **Filter / تصفية** (submit) | — | applies all four |
| **Reset / إعادة تعيين** (link) | — | clears every filter, including the client filter |

There is **no page-size control and no pagination**. The query is hard-capped
at **200 rows**, ordered by `created_at` descending.

`owner_id` is a fifth, URL-only filter. It is not exposed as a form control; it
arrives from the *All invoices for this client* link on an invoice, or from the
P&L report. When present, a second bar appears reading **Filtered to client /
مصفّاة على عميل** with the client's name linking to their record, or *Client
not found / العميل غير موجود* if the id matches nothing, plus a **Clear /
إلغاء التصفية** button. The value is carried through the filter form as a
hidden field.

### Columns

| Column | Content |
|---|---|
| Invoice # / رقم الفاتورة | number, links to the invoice |
| Owner / المالك | client, links to their record |
| Pet / الحيوان | patient, links to its record |
| Date / التاريخ | issue date |
| Doctor / الطبيب | free-text doctor name stored on the invoice, or `—` |
| Total / الإجمالي | 2 decimals |
| Paid / مدفوع | 2 decimals, green |
| Due / المستحق | 2 decimals, amber when > 0, green when 0 |
| Status / الحالة | badge |
| (last) | **View / عرض →** |

A **Totals / الإجماليات** row closes the table showing the invoice count and
the sums of Total, Paid and Due **for the rows currently displayed** — that is,
after the 200-row cap and after the text search. It is not a whole-ledger
total.

Empty state: *"No invoices found / لا توجد فواتير"*.

> Source: `platform/blueprints/finance/routes.py:149-197`,
> `platform/models/database.py:3636-3648` (`list_invoices`),
> `platform/templates/finance/invoices_list.html:1-132`

---

## 6. Screen: New Invoice

**What it is for:** billing a client for services, products or medication.
**How to reach it:** *+ New Invoice* on the dashboard or the invoices list, or
`/finance/invoices/new`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

Two columns: the form on the left, a live-calculating **Summary / الملخص** on
the right.

### Patient / المريض

| Field | Name | Required | Notes |
|---|---|---|---|
| **Owner / المالك** * | `owner_id` | **yes** | server-searched select. Renders empty; type ≥ 2 characters. Choosing an owner filters the Pet list to that owner's pets |
| **Pet / الحيوان** | `pet_id` | no | all **active** pets are rendered, then hidden by owner via JavaScript. Optional — an invoice with no pet saves fine |

### Invoice Header / رأس الفاتورة

| Field | Name | Required | Default |
|---|---|---|---|
| **Issue Date / تاريخ الإصدار** * | `issue_date` | browser-required | today |
| **Due Date / تاريخ الاستحقاق** | `due_date` | no | empty → stored as NULL |
| **Doctor / الطبيب** | `doctor_name` | no | free text, placeholder *Doctor name / اسم الطبيب*. Not a picklist and not linked to the staff table |

### Line Items / بنود الفاتورة

One row is present on load. **+ Add Line Item / إضافة بند** clones it; the red
**×** removes a row but refuses to remove the last one.

| Column | Name | Input | Notes |
|---|---|---|---|
| Description / الوصف | `description[]` | text, browser-required | a row whose description is blank after trimming is **silently dropped** on save |
| Type / النوع | `line_type[]` | select | *Service / الخدمة* (`service`), *Product / منتج* (`product`), *Medication / دواء* (`medication`) |
| Qty / الكمية | `qty[]` | number, min 0.01, step 0.01, default 1 | a row with **qty ≤ 0 is silently dropped** |
| Unit Price / سعر الوحدة | `unit_price[]` | number, min 0, step 0.01, default 0 | a row with a **negative price is silently dropped**; 0 is allowed |
| Disc % / خصم % | `discount[]` | number, 0–100, step 0.1, default 0 | clamped server-side to 0–100 |
| Total / الإجمالي | — | read-only cell | `qty × price × (1 − disc/100)`, recalculated as you type |
| (last) | — | **×** button | |

There is **no catalogue picker and no stock link** on this form: every line is
typed by hand, and billing a product here does **not** decrement inventory.

### Adjustments / التعديلات

| Field | Name | Input | Effect |
|---|---|---|---|
| **Discount Type / نوع الخصم** | `discount_type` | select: *Fixed Amount (EGP) / مبلغ ثابت (جنيه)* (`value`) or *Percentage (%) / نسبة مئوية (%)* (`percent`) | decides how the next box is read |
| **Discount Value / قيمة الخصم** | `discount_value` | number, min 0, step 0.01 | invoice-level discount, applied to the subtotal. Clamped server-side so it can never exceed the subtotal or go negative |
| **Tax Rate (%) / نسبة الضريبة (%)** | `tax_rate` | number, 0–100, step 0.1 | applied to (subtotal − discount) |
| **Notes / ملاحظات** | `notes` | textarea, 3 rows | printed on the invoice |

### Summary / الملخص panel

Live totals: **Subtotal / المجموع الفرعي**, **Discount / خصم** (green, shown as
`— x`), **Tax / الضريبة** (shown as `+ x`), **TOTAL / الإجمالي**. All in EGP,
2 decimals. Client-side only — the server recomputes on save.

### 🧾 Create Invoice / إنشاء الفاتورة

On submit the server:

1. rejects with *"Owner is required."* if no owner was chosen, re-rendering the
   form (**every field you typed is lost** — the form is re-rendered blank);
2. builds the line list, dropping blank / zero-qty / negative-price rows;
3. rejects with *"At least one line item is required."* if nothing survived,
   again re-rendering blank;
4. calls `create_invoice`, which allocates the number, recomputes subtotal,
   discount, tax and total, clamps the discount, and stores the invoice as
   `Unpaid` with `due_amount = total`;
5. flashes *"Invoice created successfully."* and redirects to the new invoice.

Any database error is flashed as *"Error creating invoice: …"* and the blank
form is re-rendered.

**Invoice numbers** are `INV-<year>-<NNNNN>` where the number is
`COUNT(*) + 1` over the whole invoices table — so the counter does not reset
each year, and it repeats a number after any invoice is deleted (see
[Known limits](#money-and-counting)).

The route reads a `visit_id` form field, but the template has no such input, so
an invoice raised here is never linked to a visit. Visit-linked invoices come
from the Visits, Boarding, Grooming, Telemedicine and Pet Shop modules.

> Source: `platform/blueprints/finance/routes.py:206-306`,
> `platform/models/database.py:3572-3618` (`_next_invoice_number`,
> `create_invoice`),
> `platform/templates/finance/invoice_form.html:1-232`

---

## 7. Screen: Invoice detail

**What it is for:** the invoice document, and everything you do to it —
take money, apply credit, print, send, credit off.
**How to reach it:** any invoice link, or `/finance/invoices/<id>`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance. An unknown id returns 404.

Page title is the invoice number; the subtitle is `issue date · status`.

### Toolbar buttons

| Button | Effect | Shown when |
|---|---|---|
| ← **Invoices / الفواتير** | back to the list | always |
| 🖨 **Print / طباعة** | opens `/finance/invoices/<id>/print` in a new tab | always |
| ⬇ **Download PDF / تحميل PDF** | downloads `invoice-<number>.pdf` | always |
| ✏️ **Edit / تعديل** | opens the edit form | only when status is **not** `Paid` or `Cancelled` |

### The document (left column)

- **Header:** clinic name, lead-veterinarian line and phone from Settings,
  falling back to the app title / tagline when the clinic row is empty; invoice
  number; **Issued / تاريخ الإصدار**; status badge.
- **Bill To / فاتورة إلى:** client name (links to the client record), phone,
  and an **All invoices for this client / كل فواتير هذا العميل →** link that
  opens the invoices list filtered to them.
- **Patient / المريض:** pet name (links to the pet), `Dr. <doctor_name>` if one
  was typed, and a **Visit / الزيارة `<date> · <type>` →** link when the
  invoice carries a `visit_id` that still resolves to a live visit. A deleted
  visit renders no link rather than a dead one.
- **Line table:** Description / الوصف, Type / النوع, Qty / الكمية, Unit Price /
  سعر الوحدة, Disc % / خصم % (`—` when zero), Total / الإجمالي. Empty state
  *"No line items / لا توجد بنود"*.
- **Totals block:** Subtotal / المجموع الفرعي; Discount / خصم (only when
  non-zero); Tax / الضريبة `(rate%)` (only when non-zero); **TOTAL /
  الإجمالي**; Paid / مدفوع; **Balance Due / الرصيد المستحق** (amber when
  positive, green at zero); then Notes / ملاحظات if any.

### 💳 Payments / المدفوعات (right column)

Every ledger row against this invoice, oldest first: amount in EGP, then
`method · date` plus `· reference` when one was entered, and who took it.
Refunds appear here as negative rows. Empty state *"No payments yet / لا توجد
مدفوعات بعد"*.

### 💳 Client has credit / للعميل رصيد

Shown **only** when the client has a positive account balance **and** the
invoice is not `Paid` or `Cancelled`. Displays the balance, then:

| Control | Name | Default / limit |
|---|---|---|
| **Apply amount / المبلغ المستخدم** | `amount` | pre-filled and capped at the **lesser** of the balance and the outstanding due |
| **Apply** button | — | posts to `/finance/invoices/<id>/apply-credit` |
| **link** | — | opens the client's account page |

Applying credit writes a negative row on the client's credit ledger *and* a
normal payment against the invoice, so it reconciles like any other payment.
It is refused, with the reason flashed, when the amount is more than the client
holds, more than the invoice owes, not positive, or when the invoice is
cancelled. If the payment leg then fails, the credit deduction is rolled back.

Applying credit does **not** award loyalty points.

### + Record Payment / تسجيل دفع

Shown only when the invoice is not `Paid` or `Cancelled`.

| Field | Name | Required | Notes |
|---|---|---|---|
| **Amount (EGP) / المبلغ (جنيه)** * | `amount` | yes | step 0.01, min 0.01. Placeholder is the outstanding balance, but the box is **empty** — the balance is not pre-filled |
| **Method / طريقة الدفع** | `method` | no | the gateway list from §3; defaults to the first entry (Cash) |
| **Reference / Receipt # — المرجع / رقم الإيصال** | `reference` | no | placeholder *Optional / اختياري*. For a counter method this is the reconciliation key and is preserved on the ledger row |
| ✅ **Record Payment / تسجيل الدفع** | — | — | submits |

A hidden per-render nonce makes the button **idempotent**: double-clicking
posts the same key and the second click returns the existing payment instead of
charging twice. Loading the page again produces a fresh nonce, so a genuine
second payment is not blocked.

Outcomes:

| Situation | What you see |
|---|---|
| Amount will not parse | *"…" is not a valid payment amount.* (red), nothing recorded |
| Amount ≤ 0 | *Payment amount must be greater than zero.* (red) |
| More than is owed | *That is more than the N.NN still owed on this invoice.* (amber) |
| Invoice already cancelled | *That invoice has been cancelled.* (amber) |
| Success | *Payment of N.NN recorded. +P loyalty points awarded.* (green) |
| Success, loyalty write failed | *Payment of N.NN recorded successfully.* (green) |
| Anything else | *The payment could not be recorded. Nothing was charged — please try again, or record it in cash.* (red) |

**Loyalty points** are awarded on every successful payment here at 1 point per
10 EGP, minimum 1 point, credited to the client's balance with the reason
`Invoice #<id> payment`. Redemption is not on this screen — it lives in CRM.

### 📱 Send via WhatsApp / إرسال واتساب

One button, **📱 Send WhatsApp / إرسال**, with the explanatory line *"Send
invoice summary to owner via WhatsApp / إرسال ملخص الفاتورة عبر واتساب"*.

It sends the client a message containing the invoice number, issue date, every
line with its total, subtotal, discount and tax when non-zero, total, paid and
balance due, to the phone on `owners.phone`. Results:

| Situation | Message |
|---|---|
| No phone on file | *Owner has no phone number on file.* (amber) |
| Sent | *Invoice sent via WhatsApp to `<phone>`.* (green) |
| Queued or rejected | *WhatsApp queued / failed — check message log.* (amber) |
| Exception | *WhatsApp error: …* (red) |

The message body is **English-only and hardcoded to "Aleefy" branding** — it
does not use the clinic's own name and is not translated for Arabic clinics.

### ↩️ Credit Note / Refund — إشعار دائن

Shown whenever the invoice is not already `Cancelled`. **Only super_admin,
clinic_owner, branch_manager and finance can actually use it** — the panel is
rendered for reception too, and posting it returns a permission error.

| Field | Name | Default |
|---|---|---|
| **Amount (EGP) / المبلغ** | `amount` | pre-filled with the invoice total; step 0.01, min 0.01 |
| **Reason / السبب** | `reason` | free text, placeholder *Refund / cancellation reason / سبب الاسترداد / الإلغاء*. Blank becomes `Credit note` |
| ↩️ **Issue Credit Note / إصدار إشعار دائن** | — | a browser confirm dialog appears first: *"Issue a credit note for this invoice?"* (English only) |

What it does:

1. refuses if the amount will not parse, is ≤ 0, exceeds the invoice total, or
   the invoice is already `Cancelled`;
2. creates a **second invoice** for the same client with one negative line
   reading `Credit note — <original number>: <reason>`, notes recording the
   original and the reason, and no tax or discount;
3. settles that credit document at zero (`due_amount 0`, `paid_amount 0`,
   status `Paid`) so it does not distort Outstanding;
4. if the credit is **for the full total**, marks the original `Cancelled` with
   `due_amount 0`; if it is **partial**, reduces the original's `due_amount`
   and re-derives its status;
5. writes an audit-log entry (`credit_note`, module `finance`);
6. flashes *"Credit note created successfully."* and **redirects you to the
   credit note**, not to the original invoice.

The credit note is a normal invoice with a normal `INV-` number and appears in
the invoices list with a negative total. There is no separate credit-note
series, no credit-note list, and **no way to reverse one**.

> Source: `platform/blueprints/finance/routes.py:318-364` (detail),
> `:368-428` (payment), `:562-660` (credit note), `:707-763` (WhatsApp),
> `:1177-1191` (apply credit), `:65-85` (`_award_points`),
> `platform/models/database.py:3828-3891` (`apply_credit`),
> `platform/templates/finance/invoice_detail.html:1-304`

---

## 8. Screen: Edit Invoice

**What it is for:** correcting an invoice that has not been settled.
**How to reach it:** the ✏️ **Edit / تعديل** button on the invoice, or
`/finance/invoices/<id>/edit`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

A `Paid` or `Cancelled` invoice cannot be opened here. Attempting it flashes
*"`<Status>` invoices cannot be edited. Issue a credit note instead."* and
returns you to the invoice.

Page title *Edit `<number>`*, subtitle `status · issue date`. Toolbar: **←
Back to Invoice / العودة إلى الفاتورة**.

### 👤 Owner & Patient / المالك والمريض

| Field | Name | Notes |
|---|---|---|
| **Owner * / المالك** | `owner_id` | server-searched select, pre-selected to the invoice's current owner (only that one owner is rendered). Blank falls back to the existing owner on save |
| **Pet / الحيوان** | `pet_id` | all active pets, current one pre-selected. Clearing it saves NULL |
| **Doctor / الطبيب** | `doctor_name` | free text |
| **Due Date / تاريخ الاستحقاق** | `due_date` | date; empty saves NULL |

The **issue date cannot be changed** here — there is no field for it and the
update statement does not touch it.

### 📋 Line Items / البنود

The existing lines, editable, one row each; **+ Add Line Item / إضافة بند**
appends a blank row; **✕** deletes a row immediately (no confirmation and no
minimum — you can delete them all, which the server then rejects).

Columns match the New Invoice form, except:

- the **Type / النوع** select offers five values — `service` / خدمة,
  `product` / منتج, `lab` / تحليل, `vaccine` / لقاح, `medication` / دواء — and
  none of the options carry a `value` attribute, so what is submitted is the
  **visible label**. In Arabic that means the Arabic word is stored as the line
  type (see [Known limits](#money-and-counting));
- there is a read-only **Total** input (`line_total[]`) which is posted but
  ignored: the server recomputes every line total.

### 🧮 Totals & Discount / الإجماليات والخصم

**Discount Type / نوع الخصم**, **Discount Value / قيمة الخصم**, **Tax Rate (%)
/ نسبة الضريبة (%)** exactly as on the New Invoice form, plus a read-only
**Estimated Total / الإجمالي التقديري** and **Notes / ملاحظات**.

### Buttons

| Button | Effect |
|---|---|
| 💾 **Save Changes / حفظ التغييرات** | validates and saves |
| **Cancel / إلغاء** | returns to the invoice, discarding edits |

On save the server deletes the invoice's lines and re-inserts them, recomputes
subtotal / discount / tax / total, then re-derives `due_amount` and status
against the amount already paid. Rejections:

| Situation | Message |
|---|---|
| No usable lines | *At least one line item is required.* (red), back to the edit form |
| New total below what is already paid | *This invoice already has X paid against it. Lowering it to Y would owe the client Z — issue a credit note or a refund instead.* (red) |
| Database error | *Error updating invoice: …* (red) |
| Success | *Invoice updated successfully.* (green), back to the invoice |

Unlike `create_invoice`, the edit path does **not** clamp the invoice-level
discount to the subtotal — see [Known limits](#money-and-counting).

> Source: `platform/blueprints/finance/routes.py:431-555`,
> `platform/templates/finance/invoice_edit.html:1-174`

---

## 9. Screens: Invoice print & PDF

### Print — `/finance/invoices/<id>/print`

A standalone printable page (it does not use the app shell), opened in a new
tab by the 🖨 **Print / طباعة** button. `lang` and `dir` follow the signed-in
user's language, so an Arabic user gets an RTL document.

Three on-screen controls, hidden when printing:

| Button | Effect |
|---|---|
| 🖨 **Print / طباعة** | `window.print()` |
| ⬇ **Download PDF / تحميل PDF** | goes to the PDF route |
| ✕ **Close / إغلاق** | `window.close()` |

The document shows clinic name, lead veterinarian, phone and email; invoice
number; `Issued:` and `Due:` (English-only labels); status badge; Bill To /
فاتورة إلى and Patient / المريض blocks; the line table; the totals block; a
**Payment History / سجل المدفوعات** section; Notes; and a thank-you footer.

The **Payment History section never renders** — the print route does not load
the ledger rows. See [Known limits](#printing-and-export).

### PDF — `/finance/invoices/<id>/pdf`

Streams `invoice-<number>.pdf` as an attachment. Built with fpdf2 using the
bundled Cairo font, with Arabic reshaping and bidi reordering, so Arabic client
and clinic names render correctly.

| Failure | What you get |
|---|---|
| fpdf2 not installed | flash *"fpdf2 is not installed. Run: pip install fpdf2"*, redirected to the print page |
| Any other error | flash *"PDF generation failed: …"*, redirected to the print page |

> Source: `platform/blueprints/finance/routes.py:663-704`,
> `platform/models/pdf_generator.py:22-70`, `:369-382`,
> `platform/models/database.py:3620-3634` (`get_invoice`, `payments` always `[]`),
> `platform/templates/finance/invoice_print.html:1-137`

---

## 10. Screen: Estimates list

**What it is for:** priced plans a client agrees to *before* the work happens —
surgery, hospitalisation.
**How to reach it:** 📋 **Estimates / عروض الأسعار** on the invoices list, or
`/finance/estimates`. There is no sidebar or launcher entry.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

Subtitle *"N result(s) / نتيجة"*. Toolbar: **+ New Estimate / عرض سعر جديد**.

### Filter

One control: **Status / الحالة**, a select that submits on change. Options:
*All / الكل*, `Draft`, `Sent`, `Approved`, `Declined`, `Expired`, `Converted`.
There is no date filter and no owner filter, and the list is capped at **100
rows**, newest first.

### Columns

Number / الرقم · Owner / المالك · Pet / الحيوان (`—` when absent) · Issued /
تاريخ الإصدار · Valid Until / صالح حتى (`—` when absent) · Total / الإجمالي
(2 decimals) · Status / الحالة (coloured pill).

The whole row is clickable and opens the estimate.

Empty state: *"No estimates yet. Create one before a surgery or hospital stay
so the client agrees the price in advance. / لا توجد عروض أسعار بعد. أنشئ عرضاً
قبل الجراحة أو الإقامة ليوافق العميل على السعر مسبقاً."*

`Expired` is one of the filter options but **nothing ever sets it** — see
[Known limits](#not-implemented-at-all).

> Source: `platform/blueprints/finance/routes.py:991-1000`,
> `platform/models/database.py:3728-3739` (`list_estimates`),
> `platform/templates/finance/estimates_list.html:1-79`

---

## 11. Screen: New Estimate

**What it is for:** quoting a price before doing the work.
**How to reach it:** *+ New Estimate* on the estimates list, or
`/finance/estimates/new`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

The layout, the line-item table, the Adjustments block and the live Summary are
**identical to the New Invoice form** (§6), including the same silent dropping
of blank / zero-qty / negative-price rows and the same 0–100 discount clamp.
The differences:

| Field | Name | Notes |
|---|---|---|
| **Valid Until / صالح حتى** | `valid_until` | date, replaces *Due Date*. Pre-filled to **today + 14 days** |
| **Notes for the client / ملاحظات للعميل** | `notes` | placeholder *What this covers, and what could change it… / ما يغطيه العرض، وما قد يغيّره…* |

The Summary panel carries the standing note *"An estimate is not revenue.
Nothing is billed until the client approves it and you convert it to an
invoice. / عرض السعر ليس إيراداً. لا تتم أي فوترة حتى يوافق العميل ويتم تحويله
إلى فاتورة."*

Submit button: 📋 **Create Estimate / إنشاء عرض السعر**. Validation messages
are *"Owner is required."* and *"At least one line item is required."*, both
re-rendering the form **blank**. Success flashes *"Estimate created."* and
opens the new estimate.

Estimates are numbered `EST-<year>-<NNNNN>` from `MAX(id) + 1`, which — unlike
invoice numbering — does not repeat after a deletion. The money arithmetic is
shared with `create_invoice`, deliberately, so an approved quote and the
invoice it becomes cannot total differently. New estimates are created with
status `Draft`.

> Source: `platform/blueprints/finance/routes.py:978-1064`,
> `platform/models/database.py:3653-3664` (`_next_estimate_number`),
> `:3667-3682` (`_money`), `:3683-3709` (`create_estimate`),
> `platform/templates/finance/estimate_form.html:1-222`

---

## 12. Screen: Estimate detail

**What it is for:** recording the client's answer and turning an approved quote
into a bill.
**How to reach it:** any row on the estimates list, or
`/finance/estimates/<id>`. An unknown id flashes *"Estimate not found."* and
returns you to the list.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance.

Page title is the estimate number; subtitle is `owner · pet`.
Toolbar: **← Estimates / عروض الأسعار** and 🖨 **Print / طباعة** (new tab).

### Expiry banner

When the estimate has a `valid_until` in the past **and** its status is `Draft`
or `Sent`, an amber banner appears: *"⚠️ This estimate passed its valid-until
date on `<date>`. Prices may need re-checking before you approve it. / انتهت
صلاحية هذا العرض في … قد تحتاج الأسعار إلى مراجعة قبل الموافقة."* It is a
warning only — nothing is blocked and the status is not changed.

### 📋 Estimate / عرض السعر card

Status pill in the header; then the line table — Description / الوصف, Type /
النوع, Qty / الكمية, Unit / سعر الوحدة, Disc % / خصم %, Total / الإجمالي —
then Notes / ملاحظات when present.

### 💰 Summary / الملخص

Subtotal / المجموع الفرعي, Discount / خصم (`— x`), Tax / الضريبة (`+ x`),
**TOTAL / الإجمالي** in EGP. Static, read from the stored estimate.

### ⚡ Actions / الإجراءات

Which buttons appear depends on the status:

| Button | Posts | Shown when status is |
|---|---|---|
| 📤 **Mark as sent to client / تم إرساله للعميل** | `decision=Sent` | `Draft` |
| ✓ **Client approved / وافق العميل** | `decision=Approved` | `Draft`, `Sent`, `Declined`, `Expired` |
| ✕ **Client declined / رفض العميل** | `decision=Declined` | `Draft`, `Sent`, `Approved` |
| 🧾 **Convert to invoice / تحويل إلى فاتورة** | convert | `Approved` only |

When the status is not `Approved`, an informational note stands in place of the
convert button: *"An estimate becomes an invoice only after the client approves
it. / يتحول عرض السعر إلى فاتورة فقط بعد موافقة العميل."*

When the status is `Converted`, all action buttons are replaced by *"Invoiced.
This estimate is locked so the bill and the quote cannot drift apart. / تمت
الفوترة. هذا العرض مقفل حتى لا يختلف عن الفاتورة."* and a 🧾 **Open the invoice
/ فتح الفاتورة** link.

Recording a decision stamps `decided_at` and `decided_by` and flashes
*"Estimate marked `<decision>`."*. A converted estimate refuses further
decisions with *"This estimate is already invoiced and cannot be changed."*
An unrecognised decision value flashes *"Unknown decision."*

**Convert** creates a real invoice dated **today** (not the estimate's issue
date) with the same lines, discount and tax, notes prefixed `From estimate
<number>.`, then marks the estimate `Converted` and stores the invoice id. It
is guarded against double-conversion: a second click returns the existing
invoice. Converting a non-approved estimate flashes *"only an approved estimate
can be converted"*. Success flashes *"Invoice created from estimate."* and
opens the invoice.

### Meta card

Issued / تاريخ الإصدار · Valid until / صالح حتى · Doctor / الطبيب · Created by
/ أنشأه · Decision recorded / تم تسجيل القرار (`decided_at · decided_by`, when
a decision exists).

### Estimate print — `/finance/estimates/<id>/print`

A standalone bilingual A4 quote: clinic block, Estimate / عرض سعر heading,
number and issue date, Client / العميل, Patient / المريض, Valid Until / صالح
حتى, a four-column line table (Description, Qty, Unit Price, Total — no Type
and no discount column), the totals block, the notes, a standing disclaimer
that this is a quote and not an invoice and that prices may change, and a
signature strip for **Client signature / توقيع العميل**, **Date / التاريخ** and
**Veterinarian / الطبيب**.

There is no print/close toolbar on this page — use the browser's own print
command.

> Source: `platform/blueprints/finance/routes.py:1067-1127`,
> `platform/models/database.py:3742-3787` (`decide_estimate`,
> `convert_estimate`),
> `platform/templates/finance/estimate_detail.html:1-167`,
> `platform/templates/finance/estimate_print.html:1-109`

---

## 13. Screen: Client account (deposits & credit)

**What it is for:** money taken from a client before there is anything to bill
it against — boarding and surgery deposits — and giving unspent money back.
**How to reach it:** the **Account** button on a client's record, the *link*
in the credit panel on an invoice, or `/finance/owners/<owner_id>/credit`.
**Who can open it:** super_admin, clinic_owner, branch_manager, reception,
finance. An unknown owner flashes *"Owner not found."* and returns you to the
invoices list.

Page title is the client's name; subtitle *"Deposits and account credit /
الدفعات المقدمة ورصيد الحساب"*. Toolbar: **← Finance / المالية**.

The balance is **always derived** by summing the client's credit ledger. It is
never stored on the client record.

### 📒 Account History / سجل الحساب

Every credit-ledger row, newest first, capped at 100.

| Column | Content |
|---|---|
| When / التاريخ | created-at timestamp |
| Type / النوع | `deposit`, `applied` or `refund` — **stored and displayed in English only** |
| Note / ملاحظة | the note, plus `(reference)` in italics when one exists |
| By / بواسطة | who recorded it |
| Amount / المبلغ | signed; `+` and green for money in, plain for money out |

Empty state: *"No deposits recorded for this client yet. / لا توجد دفعات مقدمة
لهذا العميل بعد."*

### 🧾 Apply credit to an unpaid invoice / استخدام الرصيد في فاتورة غير مدفوعة

Shown only when the balance is positive **and** the client has at least one
invoice with a balance. Lists Invoice / الفاتورة (linked), Issued / التاريخ,
Still owed / المتبقي, and an inline amount box + **Apply / استخدام** button per
row. The box is pre-filled and capped at the lesser of the balance and that
invoice's outstanding amount.

The open-invoice list is drawn from the client's most recent **100** invoices.

### On account / الرصيد

The balance in EGP, with the explanation *"Money the client has paid that is
not yet against any invoice. / أموال دفعها العميل ولم تُخصم بعد من أي فاتورة."*

### ➕ Take a deposit / تسجيل دفعة مقدمة

| Field | Name | Required | Notes |
|---|---|---|---|
| **Amount / المبلغ** * | `amount` | yes | step 0.01, min 0.01 |
| **Method / طريقة الدفع** | `method` | no | a **hardcoded** list — `Cash` / نقدي, `Instapay`, `Card` / بطاقة, `Transfer` / تحويل بنكي. Not the gateway registry used on the invoice screen |
| **Reference / المرجع** | `reference` | no | placeholder *Transaction no. / رقم العملية* |
| **Note / ملاحظة** | `note` | no | placeholder *e.g. boarding deposit / مثال: دفعة إقامة* |
| **Record deposit / تسجيل الدفعة** | — | — | posts `action=deposit` |

Success: *"Deposit recorded."*. A non-positive amount raises *"a deposit must
be a positive amount"*, flashed as-is.

### ↩ Refund credit / رد الرصيد

Shown only when the balance is positive.

| Field | Name | Required | Notes |
|---|---|---|---|
| **Amount / المبلغ** * | `amount` | yes | capped at the balance |
| **Reason / السبب** | `note` | no | free text |
| **Record refund / تسجيل الرد** | — | — | posts `action=refund`, after a browser confirm: *"Refund this amount to the client? / رد هذا المبلغ للعميل؟"* |

Success: *"Refund recorded."*. Over-refunding raises *"only N.NN is available
to refund"*.

A deposit and a refund are **ledger entries only** — the money moving in the
real world is the clinic's business. Neither writes to the `payments` table,
so deposits do **not** appear in Cash Flow or in the Daily Closing until they
are applied to an invoice.

> Source: `platform/blueprints/finance/routes.py:1130-1174`,
> `platform/models/database.py:3792-3809` (`owner_credit_balance`,
> `list_owner_credits`), `:3811-3825` (`add_deposit`), `:3891-3907`
> (`refund_credit`),
> `platform/templates/finance/owner_credit.html:1-181`

---

## 14. Screen: Finance → Expenses

**What it is for:** recording what the clinic spends.
**How to reach it:** **there is no link to this screen anywhere in the
application.** Type `/finance/expenses`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance.
Reception is excluded; auditor is named on the route but blocked by the module
gate.

This screen and the Accounting → Expenses screen (§19) read and write the
**same `expenses` table** with different forms and different category lists.

Page title **Expenses / المصروفات**, subtitle *"Record and track clinic
expenses / تسجيل ومتابعة مصروفات العيادة"*. Toolbar: **← Dashboard / لوحة
التحكم**.

### Filters (GET)

**From / من** (`date_from`) and **To / إلى** (`date_to`), a **Filter / تصفية**
button and a **Reset / إعادة تعيين** link. There is **no category filter here**
(the Accounting screen has one). Results are capped at **200 rows**, newest
first.

### Columns

Date / التاريخ · Category / الفئة (badge; `General` / عام when empty) ·
Description / الوصف · Vendor / المورد · Amount (EGP) / المبلغ (جنيه) (red,
2 decimals) · Ref / المرجع.

The **Vendor** cell becomes a link to `/procurement/suppliers/<id>` only when
the free-text vendor name matches a supplier row **exactly**; otherwise it is
plain text.

A **Total / الإجمالي** row closes the table with the record count and the sum
of the rows displayed.

Empty state: *"No expenses recorded yet / لا توجد مصروفات مسجلة بعد"*.

### ➕ Record Expense / تسجيل مصروف

| Field | Name | Required | Notes |
|---|---|---|---|
| **Category / الفئة** * | `category` | browser-required | a fixed 10-item list: Supplies / المستلزمات, Medications / الأدوية, Utilities / المرافق, Salaries / الرواتب, Rent / الإيجار, Maintenance / الصيانة, Equipment / المعدات, Marketing / التسويق, Lab / المختبر, Other / أخرى. **The options carry no `value`, so the visible label is submitted** — in Arabic the Arabic word is stored |
| **Description / الوصف** * | `description` | yes | placeholder *What was purchased/paid? / ما الذي تم شراؤه/دفعه؟* |
| **Amount (EGP) / المبلغ (جنيه)** * | `amount` | yes | number, min 0.01, step 0.01 |
| **Date / التاريخ** * | `expense_date` | yes | defaults to today |
| **Vendor / Supplier — المورد / المزود** | `vendor` | no | free text, no supplier picker |
| **Receipt / Reference # — الإيصال / رقم المرجع** | `receipt_ref` | no | |
| **Notes / ملاحظات** | `notes` | no | 2-row textarea. **Only this form saves notes** — the Accounting form has no notes field and never shows them |
| 💾 **Save Expense / حفظ المصروف** | — | — | |

Outcomes: *"Description and valid amount are required."* (red) when either is
missing; *"Expense recorded."* (green) on success; *"Error saving expense: …"*
(red) on a database failure. Either way you are returned to the unfiltered
list.

An empty category is stored as `General`. There is **no way to edit or delete
an expense** from any screen.

> Source: `platform/blueprints/finance/routes.py:766-843`,
> `platform/templates/finance/expenses_list.html:1-149`,
> `platform/models/database.py:1762-1774` (`expenses` schema)

---

## 15. Screen: Financial Reports

**What it is for:** revenue, expenses and net over a date range, plus an Excel
extract.
**How to reach it:** the **Full Report / التقرير الكامل →** link in the revenue
chart on the Finance Dashboard (which only appears when there is revenue data),
or `/finance/reports`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance.

Page title **Financial Reports / التقارير المالية**.

### Toolbar

| Button | Effect |
|---|---|
| ← **Dashboard / لوحة التحكم** | back to `/finance/` |
| 📊 **Export Excel / تصدير Excel** | downloads the current range as `.xlsx` |

### Date range

**From / من** (`date_from`) and **To / إلى** (`date_to`) with an **Apply /
تطبيق** button. Defaults: the 1st of this month to today. There is no reset
button.

### The six KPI cards

| Card | Meaning |
|---|---|
| **Revenue / الإيرادات** | `SUM(paid_amount)` on `Paid`/`Partial` invoices **issued** in the range — accrual |
| **Invoiced / الفواتير** | `SUM(total)` on non-cancelled invoices issued in the range |
| **Outstanding / المستحق** | `SUM(due_amount)` over all `Unpaid`/`Partial` invoices — **all time, ignores the date range** |
| **Expenses / المصروفات** | `SUM(amount)` on expenses dated in the range |
| **Net / الصافي** | Revenue − Expenses; green when ≥ 0, red below |
| **Invoices / الفواتير** | count of non-cancelled invoices issued in the range |

All amounts are rendered with no decimals.

### 📈 Daily Revenue — Last 30 Days / الإيرادات اليومية — آخر 30 يوم

A bar per day. **Always the last 30 days — it ignores the date range above.**

### Revenue by Line Type / الإيرادات حسب النوع

A horizontal bar per `line_type` across all invoice lines on non-cancelled
invoices issued in the range, largest first. The type name is shown
capitalised, exactly as stored — so mixed English and Arabic type values
(§8) appear as separate bars. Empty state *"No data for this period / لا توجد
بيانات لهذه الفترة"*.

Note this is **invoiced** value, not collected — unlike the Revenue KPI beside
it.

### Expenses by Category / المصروفات حسب الفئة

The same treatment for expenses in the range, red bars, `General` used where
the category is empty. Empty state *"No expenses for this period / لا توجد
مصروفات لهذه الفترة"*.

### 🏆 Top Services / أبرز الخدمات

Service / الخدمة · Count / العدد · Revenue (EGP) / الإيرادات (جنيه), the top 10
by revenue.

This table is grouped by the **typed description string** across `service`
lines only, and it is **all-time — it ignores the date range and it includes
cancelled invoices.** The whole card is hidden when there are no service lines
at all.

### Excel export — `/finance/reports/export/xlsx`

Downloads `finance_report_<from>_<to>.xlsx`, one sheet named *Invoices*, titled
`Financial Report — <from> to <to>`, with **English-only** headers:

`Invoice #` · `Date` · `Owner` · `Total` (the subtotal) · `Discount` · `Tax` ·
`Net` (the invoice total) · `Status`

One row per invoice **issued** in the range, ordered by issue date, **including
cancelled invoices and credit notes**. Expenses, payments and the P&L figures
are **not** exported. If openpyxl is missing or the query fails, the error text
is flashed and you are returned to the report page.

> Source: `platform/blueprints/finance/routes.py:846-897` (report),
> `:912-959` (export),
> `platform/models/database.py:3940-3991` (`get_finance_summary`),
> `:4048-4055` (`get_top_services`, no date filter),
> `platform/models/excel_export.py:50-68` (`make_workbook`),
> `platform/templates/finance/reports.html:1-190`

---

## 16. Screen: Accounting Dashboard

**What it is for:** the clinic's own books — profit, spend and trend.
**How to reach it:** sidebar → BUSINESS → Accounting, launcher card **Finance &
Accounting**, or `/accounting/`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance,
auditor. **Reception cannot.**

Page title **Accounting Dashboard / لوحة تحكم المحاسبة**, subtitle today's
date.

### Toolbar

| Button | Goes to |
|---|---|
| **Expenses / المصروفات** | `/accounting/expenses` |
| **Daily Closing / الإغلاق اليومي** | `/accounting/closing` |

### The four stat cards

| Card | Computed from |
|---|---|
| 💵 **Total Revenue (This Month) / إجمالي الإيرادات (هذا الشهر)**<br><small>Paid invoices month-to-date / الفواتير المدفوعة حتى اليوم</small> | `SUM(paid_amount)` on `Paid`/`Partial` invoices whose **`created_at`** falls on or after the 1st |
| 🧾 **Total Expenses (This Month) / إجمالي المصروفات (هذا الشهر)** | `SUM(amount)` on expenses dated on or after the 1st |
| 📈 **Net Profit (This Month) / صافي الربح (هذا الشهر)** | revenue − expenses, green when ≥ 0 |
| 📊 **Profit Margin / هامش الربح** | net ÷ revenue as a percentage, 1 decimal; `0` when revenue is zero |

The revenue basis here (`invoices.created_at`) is a **third** basis, different
from both the Finance Dashboard (payments received) and the Finance Reports
page (invoice issue date). The three screens will disagree.

Every query on this page is wrapped in a bare `try/except` that falls back to
zero or an empty list, so a broken query shows as **0 EGP with no error
message**.

### 📊 12-Month Revenue vs Expenses / الإيرادات مقابل المصروفات — 12 شهرًا

A paired green/red bar per month with a legend (**Revenue / الإيرادات**,
**Expenses / المصروفات**). The month buckets are produced by stepping back in
**28-day** increments from the 1st of this month, so the labels can repeat a
month and skip another over a 12-month window.

### 🔴 Top Expense Categories / أبرز فئات المصروفات

The top 5 categories by spend this month as horizontal red bars, with a **View
All / عرض الكل →** link to the expenses list. Empty state *"No expenses this
month / لا توجد مصروفات هذا الشهر"*.

### ⚡ Recent Transactions / المعاملات الأخيرة

The 5 most recent paid/partial invoices and the 5 most recent expenses, merged
and sorted by date descending, capped at 10.

| Column | Content |
|---|---|
| Date / التاريخ | first 10 characters of the row's date |
| Description / الوصف | invoice number (linked) or the expense description |
| Type / النوع | **Revenue / إيرادات** or **Expense / مصروف** badge |
| Amount (EGP) / المبلغ (جنيه) | `+` green for revenue, `-` red for expense |

Header link **Full Cash Flow / التدفق النقدي الكامل →**. Empty state *"No
transactions yet / لا توجد معاملات بعد"*.

Invoice rows show the invoice's whole `paid_amount`, dated by `created_at`,
not the individual payment — a partially-paid invoice appears once at its
running total.

### 🔗 Quick Access / وصول سريع

Five links: 📋 **P&L Report / الأرباح والخسائر**, 💧 **Cash Flow / التدفق
النقدي**, 🧾 **Expenses / المصروفات**, 🔒 **Daily Closing / الإغلاق اليومي**,
🎯 **Budget / الميزانية**.

> Source: `platform/blueprints/accounting/routes.py:21-152`,
> `platform/templates/accounting/dashboard.html:1-222`

---

## 17. Screen: Profit & Loss report

**What it is for:** what was earned and what was spent over a range.
**How to reach it:** Accounting Dashboard → Quick Access → *P&L Report*, or
`/accounting/pl`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance,
auditor.

Page title **Profit & Loss Report / تقرير الأرباح والخسائر**. Toolbar: **←
Dashboard / لوحة التحكم**.

### Date range

**From / من**, **To / إلى**, **Apply Filter / تطبيق الفلتر**, and a **Reset /
إعادة تعيين** link that clears back to the default (1st of this month → today).

### Summary tiles

| Tile | Meaning | Links to |
|---|---|---|
| **Total Revenue / إجمالي الإيرادات** | sum of the revenue table below | the invoices list, filtered to the same range (*View invoices / عرض الفواتير →*) |
| **Total Expenses / إجمالي المصروفات** | sum of the expenses table below | the accounting expenses list, same range (*View expenses / عرض المصروفات →*) |
| **Net Profit / صافي الربح** | revenue − expenses | — |
| **Profit Margin / هامش الربح** | net ÷ revenue, 1 decimal | — |

Below the tiles: *"* Export to PDF or Excel — use browser print / save as PDF /
تصدير إلى PDF أو Excel — استخدم طباعة المتصفح / حفظ كـ PDF"*. **There is no
export button on this screen** — the note is telling you to use the browser.

### Revenue table

Every invoice line on `Paid` or `Partial` invoices **issued** in the range,
grouped by description + type, largest first.

Service / Item — الخدمة / الصنف · Type / النوع (badge) · Count / العدد ·
Amount (EGP) / المبلغ (جنيه). A **Total Revenue / إجمالي الإيرادات** footer
row closes it. Empty state *"No revenue data / لا توجد بيانات إيرادات"*.

This counts the **full line value** of any partially-paid invoice, so "revenue"
here is larger than the money actually collected.

### Expenses table

Expenses in the range grouped by category, largest first. Category / الفئة
(linked to the expenses list pre-filtered to that category and range) · Count /
العدد · Amount (EGP) / المبلغ (جنيه), with a **Total Expenses / إجمالي
المصروفات** footer. Empty state *"No expenses in range / لا توجد مصروفات في
هذه الفترة"*.

> Source: `platform/blueprints/accounting/routes.py:156-223`,
> `platform/templates/accounting/pl_report.html:1-169`

---

## 18. Screen: Cash Flow

**What it is for:** the individual movements of money in and out over a range.
**How to reach it:** Accounting Dashboard → *Full Cash Flow* or Quick Access →
*Cash Flow*; also from the Daily Closing tiles; or `/accounting/cashflow`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance,
auditor.

Page title **Cash Flow / التدفق النقدي**. Toolbar: **← Dashboard / لوحة
التحكم**.

### Date range

**From / من**, **To / إلى**, **Filter / تصفية**, **Reset / إعادة تعيين**.
Defaults to the 1st of this month → today. The range is matched against the
first 10 characters of `payments.received_at` for money in, and against
`expenses.expense_date` for money out.

### Three totals

**💵 Total Cash In / إجمالي النقد الوارد**, **🔴 Total Cash Out / إجمالي النقد
الصادر**, **📊 Net Flow / صافي التدفق**.

### Movements table

Every payment ledger row and every expense in the range, merged and sorted by
date ascending.

| Column | Content |
|---|---|
| Date / التاريخ | first 10 characters of the date |
| Description / الوصف | for money in: the invoice number (linked) plus the client name (linked); for money out: the expense description, or its category, or `Expense` |
| Payment Method / طريقة الدفع | for money in: the method on the ledger row; for money out: **always the literal `Cash`** — expenses have no payment-method column |
| Direction / الاتجاه | **↑ In / ↑ وارد** or **↓ Out / ↓ صادر** badge |
| Amount (EGP) / المبلغ (جنيه) | `+` / `-`, no decimals |
| Running Balance / الرصيد الجاري | cumulative in − out, **starting from zero at the beginning of the range**. It is a within-window running total, not a bank or till balance |

Empty state *"No transactions in this period / لا توجد معاملات في هذه الفترة"*.

If either query fails you get an amber flash — *"Cash-in could not be read: …"*
or *"Cash-out could not be read: …"* — and the page renders with the other half
only.

Because money in is read from the **payments ledger**, refunds appear as
negative "In" rows, and client deposits that have not yet been applied to an
invoice do **not** appear at all.

> Source: `platform/blueprints/accounting/routes.py:227-312`,
> `platform/templates/accounting/cashflow.html:1-118`

---

## 19. Screen: Accounting → Expenses

**What it is for:** the expense ledger with a category filter, plus a second
entry form.
**How to reach it:** Accounting Dashboard toolbar or Quick Access → *Expenses*;
the P&L expense links; the Daily Closing tile; or `/accounting/expenses`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance,
auditor.

Same underlying table as §14. Toolbar: **← Dashboard / لوحة التحكم**.

### Filters (GET)

| Control | Param | Effect |
|---|---|---|
| **Category / الفئة** | `category` | exact match; options are the **distinct categories already present in the data**, plus *All Categories / جميع الفئات* |
| **From / من** | `date_from` | `expense_date >=` |
| **To / إلى** | `date_to` | `expense_date <=` |
| **Filter / تصفية** | — | applies |
| **Reset / إعادة تعيين** | — | clears |

Capped at **300 rows**, newest first.

### Columns

Date / التاريخ · Category / الفئة · Description / الوصف · Amount (EGP) /
المبلغ (جنيه) (red) · Vendor / المورد (linked when it matches a supplier
exactly) · Receipt # / رقم الإيصال · **Method / طريقة الدفع**.

The **Method column is always `—`**: the expenses table has no
`payment_method` column, so nothing is ever stored there.

A **Total / الإجمالي** footer sums the displayed rows, with no decimals.

### ➕ Add Expense / إضافة مصروف

| Field | Name | Required | Notes |
|---|---|---|---|
| **Category / الفئة** | `category` | no (defaults to `General` when blank) | six built-ins — Medicines/Supplies / أدوية/مستلزمات, Staff Salaries / رواتب الموظفين, Utilities / المرافق, Equipment / المعدات, Marketing / التسويق, Miscellaneous / متنوع — plus any other category already in the data. **These options carry no `value` either**, so the visible label is submitted. They do **not** match the Finance form's ten categories |
| **Description / الوصف** * | `description` | yes | |
| **Amount (EGP) / المبلغ (جنيه)** * | `amount` | yes | min 0.01, step 0.01. A value that will not parse is treated as 0 and rejected as missing |
| **Date / التاريخ** * | `expense_date` | yes | defaults to today |
| **Vendor / المورد** | `vendor` | no | free text |
| **Receipt # / رقم الإيصال** | `receipt_ref` | no | |
| **Payment Method / طريقة الدفع** | `payment_method` | no | Cash / نقداً, Bank Transfer / تحويل بنكي, Credit Card / بطاقة ائتمان, Cheque / شيك, Other / أخرى — **this value is never stored**, see [Known limits](#expenses) |
| **Save Expense / حفظ المصروف** | — | — | |

Outcomes: *"Description and valid amount are required."*, *"Expense recorded
successfully."*, or *"Error saving expense: …"*. You are returned to the
unfiltered list either way.

There is no notes field here, and no way to edit or delete an expense.

> Source: `platform/blueprints/accounting/routes.py:316-428`,
> `platform/templates/accounting/expenses_list.html:1-174`

---

## 20. Screen: Daily Closing

**What it is for:** the end-of-day till check and a written handover note.
**How to reach it:** Accounting Dashboard toolbar or Quick Access → *Daily
Closing*, or `/accounting/closing`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance,
auditor.

Page title **Daily Closing / الإغلاق اليومي**. Toolbar: **← Dashboard / لوحة
التحكم**. The screen is **fixed to today** — there is no date picker and you
cannot review or close a past day.

### 🔒 Today's Closing Summary / ملخص إغلاق اليوم — `<date>`

| Tile | Meaning | Links to |
|---|---|---|
| 💵 **Cash Collected / النقد المحصّل** | `SUM(payments.amount)` where the payment was received today | Cash Flow filtered to today (*View payments / عرض المدفوعات →*) |
| 🧾 **Expenses Paid / المصروفات المدفوعة** | `SUM(expenses.amount)` dated today | Expenses filtered to today (*View expenses / عرض المصروفات →*) |
| 📊 **Net Cash / صافي النقد** | collected − expenses, shown with an explicit sign | — |
| 🔢 **Transactions / المعاملات** | payment count + expense count, with `N in / وارد` and `N out / صادر` underneath | — |

Cash Collected is on the same basis as Cash Flow, so the figure and the rows
behind the link agree. Payment timestamps are written in clinic-local time
specifically so an evening's takings land on the right day.

### Previous closings table

The last **7** closing notes, newest first: Date / التاريخ · Note / الملاحظة ·
Recorded By / سجّله · Time / الوقت (first 16 characters of the timestamp).

### 📝 Add Closing Note / إضافة ملاحظة إغلاق

A single textarea, `closing_note`, labelled **Closing Note for / ملاحظة
الإغلاق ليوم `<date>`**, placeholder *"Summarize today: cash on hand, any
discrepancies, notes for manager... / لخّص اليوم: النقد الموجود، أي فروقات،
ملاحظات للمدير..."*, and 💾 **Save Closing Note / حفظ ملاحظة الإغلاق**.

An empty note is silently ignored — no message, nothing saved. A saved note
flashes *"Closing note saved."*; a failure flashes *"Error saving note: …"*.

**Notes accumulate; they do not replace.** Saving twice today produces two rows
for today in the history, and there is no edit or delete.

Saving a note does **not** close, lock or freeze anything. There is no
cash-counted field, no variance calculation, and nothing prevents payments or
expenses being recorded for a day that has already been "closed". The
`daily_closings` table in the schema, which has `cash_sales` / `card_sales` /
`transfer_sales` columns, is **not used by this screen** — closing notes go to
a separate `closing_notes` table created on first use.

### Quick Links / روابط سريعة

Links to Cash Flow and to the P&L report.

> Source: `platform/blueprints/accounting/routes.py:443-536`,
> `platform/models/database.py:1776-1790` (unused `daily_closings` table),
> `platform/templates/accounting/closing.html:1-146`

---

## 21. Screen: Monthly Budget

**What it is for:** monthly spend targets per expense category, and how the
month is tracking against them.
**How to reach it:** Accounting Dashboard → Quick Access → *Budget*, or
`/accounting/budget`.
**Who can open it:** super_admin, clinic_owner, branch_manager, finance,
auditor.

Page title **Monthly Budget / الميزانية الشهرية**. Toolbar: **← Dashboard /
لوحة التحكم**.

Header reads **🎯 Budget vs. Actuals / الميزانية مقابل الفعلي — `<Month
Year>`** with the sub-line *"Month-to-date spending against monthly targets /
الإنفاق حتى اليوم مقابل الأهداف الشهرية"*, and three totals: **Total Budget /
إجمالي الميزانية**, **Total Actual / الإجمالي الفعلي** (red when over) and
**Remaining / المتبقي**.

The month label is the current month; you cannot look at another month.

### The table

One row per stored budget target, in insertion order.

| Column | Content |
|---|---|
| Category / الفئة | the target's category name |
| Budget (EGP) / الميزانية (جنيه) | the monthly target |
| Actual (EGP) / الفعلي (جنيه) | `SUM(expenses.amount)` from the 1st to today where `category` matches this target **exactly** |
| Variance (EGP) / الفرق (جنيه) | budget − actual, signed; green when ≥ 0 |
| % Used / نسبة الاستخدام | actual ÷ budget as a percentage, 1 decimal, with a progress bar capped at 100% width; `0` when the budget is zero |
| (status) | **On Track / في المسار** below 75%, **Near Limit / قريب من الحد** at 75–99%, **Over Budget / تجاوز الميزانية** at 100%+ |

A **TOTAL / الإجمالي** footer repeats the three totals.

Six categories are seeded on a fresh database: Medicines/Supplies (50 000),
Staff Salaries (120 000), Utilities (15 000), Equipment (25 000), Marketing
(10 000), Miscellaneous (8 000).

### ⚙️ Edit Budget Targets / تعديل أهداف الميزانية

A collapsed `<details>` panel. Opening it shows one **Monthly Budget (EGP) /
الميزانية الشهرية (جنيه)** number box per existing category (step 100, the
category itself is fixed text plus a hidden field), then one blank row for a
**New category name (optional) / اسم فئة جديدة (اختياري)** and its amount.

💾 **Save Budget Targets / حفظ أهداف الميزانية** writes every changed target
and inserts or updates the new category if a name was given. A value that will
not parse becomes 0. Flashes *"Budget targets saved."* or *"Error saving
budget: …"*, then reloads the page. The note beside the button reads *"Changes
take effect immediately on the dashboard. / تسري التغييرات فوراً على لوحة
التحكم."*

There is **no way to delete a budget target** from this screen.

The save uses PostgreSQL-only SQL — see [Known limits](#expenses).

> Source: `platform/blueprints/accounting/routes.py:540-625`,
> `platform/models/database.py:2190-2197` (schema), `:2614-2629` (seed),
> `platform/templates/accounting/budget.html:1-199`

---

## 22. Where finance data comes from and goes to

| Source | Effect |
|---|---|
| Visits, Boarding, Grooming, Telemedicine, Pet Shop | each can create an invoice directly; those invoices carry a `visit_id` where applicable and show the **Visit →** link on the invoice screen |
| Estimates | *Convert to invoice* creates one |
| Credit notes | create a second, negative invoice |
| Procurement suppliers | only ever matched to an expense by an exact **name string** — there is no supplier id on an expense |
| CRM | loyalty points earned on payment are spent on the client's CRM record, not here |
| Reports module (`/reports/`) | a separate module with its own revenue figures; not covered in this chapter |

> Source: `platform/blueprints/visits/routes.py:575`, `:1498`,
> `platform/blueprints/boarding/routes.py:302`,
> `platform/blueprints/grooming/routes.py:288`,
> `platform/blueprints/telemedicine/routes.py:290`,
> `platform/blueprints/petshop/routes.py:602`,
> `platform/blueprints/crm/routes.py:450-476` (loyalty redemption)

---

## Known limits

Everything below is a real behaviour of the current code, verified in the
source. None of it is speculation about future work.

### Not implemented at all

- **No expense edit and no expense delete.** Neither expenses screen has one,
  and no route exists. A mistyped expense is permanent.
- **No estimate edit and no estimate delete.** Once created, an estimate can
  only be decided, converted or printed.
- **No invoice delete or void beyond the credit note.** And a credit note
  cannot itself be reversed.
- **No refund from the invoice screen.** `models.payments` implements full and
  partial refunds against a payment intent, but **no route calls it** — the
  only user-facing refunds are a credit note (which does not move money) and a
  client-credit refund on the account page.
- **`Expired` estimates never happen.** The status is a filter option and has a
  colour, but nothing — no route, no scheduled job — ever sets it. Expiry is
  surfaced only as an on-screen banner on the estimate detail page.
- **No Daily Closing lock.** Saving a note does not close the day, does not
  record counted cash, and does not compute a variance. Transactions can still
  be posted to a "closed" day.
- **The `daily_closings` table is dead.** It has `cash_sales`, `card_sales`,
  `transfer_sales` and more, and nothing in the finance or accounting modules
  reads or writes it. The Daily Closing screen uses `closing_notes` instead.
- **No inventory link on invoicing.** Billing a `product` or `medication` line
  on the New Invoice form does not touch stock.
- **No catalogue picker on invoice or estimate lines.** Every description and
  price is typed by hand, even though a Price Catalog module exists.
- **`_REDEEM_RATE` and `_MIN_REDEEM` in the finance blueprint are dead code** —
  redemption is implemented in CRM with its own copies of the constants.
- **The P&L "Export to PDF or Excel" note is not a button.** It instructs you
  to use the browser's print dialog.

> Source: `platform/models/payments/__init__.py:225-276` (`refund`, no caller
> in any blueprint), `platform/blueprints/finance/routes.py:58-61`,
> `platform/models/database.py:1776-1790`,
> `platform/templates/accounting/pl_report.html:84`

### Permissions

- **`auditor` cannot open any `/finance/` screen**, despite being named on the
  role lists of `/finance/expenses`, `/finance/reports` and the Excel export.
  Its default grants are `reports`, `audit`, `accounting` — not `invoicing` —
  and the module gate rejects it first.
- **`auditor` can write in Accounting.** Every `/accounting/` route carries
  only `@login_required`, so a role documented in the code as *"read-only by
  role"* can add expenses, save closing notes and change budget targets.
- **`reception` sees the Credit Note panel but cannot use it.** The panel has
  no role guard in the template; the route does. Reception gets *"You don't
  have permission to access this page."* and is sent to the launcher, losing
  what was typed.
- **The sidebar shows Finance and Accounting to everyone.** The BUSINESS group
  has no role condition, so a nurse or groomer sees both links and is bounced
  when clicking either.
- **The launcher cards use a hardcoded role list that disagrees with the
  grants.** The *Billing & Invoicing* card is shown to `doctor`, which does not
  hold `invoicing` and is bounced. The *Finance & Accounting* card is **not**
  shown to `auditor`, which does hold `accounting` and could open it by URL.
- If the `roles` table has never been seeded, the module gate falls open for
  every built-in role and all of the above widens to every signed-in user.

> Source: `platform/blueprints/auth/routes.py:89-131`, `:223-250`,
> `platform/models/database.py:4346-4379`,
> `platform/blueprints/launcher/routes.py:277-306`, `:579`,
> `platform/templates/base.html:182-224`,
> `platform/templates/finance/invoice_detail.html:280-300`

### Money and counting

- **"Payments Today" on the Finance Dashboard is not a payment count.** It
  counts invoices *issued today* whose status is `Paid` or `Partial`. A payment
  taken today against last week's invoice does not increment it; an invoice
  raised and paid today counts as one whatever the number of instalments.
- **Three screens compute "revenue" three different ways** and will not agree:
  Finance Dashboard = payments received (cash basis); Finance Reports =
  `paid_amount` on invoices issued in the range (accrual); Accounting Dashboard
  = `paid_amount` on invoices whose `created_at` falls in the month.
- **The P&L revenue table overstates.** It sums whole invoice lines for any
  invoice whose status is `Paid` **or `Partial`**, so a barely-paid invoice
  contributes its full value.
- **Invoice numbering repeats after a deletion.** `INV-<year>-<N>` is derived
  from `COUNT(*) + 1` over the whole table. Delete any invoice and the next
  insert collides with the UNIQUE constraint. The year prefix also does not
  reset the counter, so `INV-2027-00412` can follow `INV-2026-00411`. Estimate
  numbering uses `MAX(id) + 1` and is not affected.
- **Editing an invoice does not clamp the invoice-level discount.**
  `create_invoice` clamps it to the subtotal; the edit route does not, so a
  discount larger than the subtotal saved from Edit Invoice produces a negative
  total.
- **The Edit Invoice line-type select stores the visible label.** Its options
  have no `value` attribute. Under Arabic the stored `line_type` becomes
  `خدمة`, `منتج`, `تحليل`, `لقاح` or `دواء`, which then appears as a separate
  category in *Revenue by Line Type* and breaks *Top Services* (which matches
  `line_type='service'` literally). The same defect applies to both expense
  category selects.
- **`Top Services` ignores the date range and includes cancelled invoices.**
- **`Outstanding` on the Reports page ignores the date range** — it is always
  the all-time figure.
- **The Reports revenue chart ignores the date range** — always the last 30
  days.
- **The Excel export includes cancelled invoices and credit notes** and has no
  status filter.
- **The Accounting 12-month chart steps back in 28-day increments**, so month
  labels can repeat and months can be skipped.
- **Money is stored as floating point.** See `docs/MONEY_PRECISION.md` for the
  known consequences.

> Source: `platform/blueprints/finance/routes.py:113-116`, `:441-543`,
> `platform/blueprints/accounting/routes.py:29-37`, `:69-95`, `:160-178`,
> `platform/models/database.py:3572-3576`, `:4048-4055`,
> `platform/templates/finance/invoice_edit.html:85`

### Expenses

- **The Accounting "Payment Method" field is never stored.** The `expenses`
  table has no `payment_method` column. The insert tries it first and falls
  back to a version without it — but on PostgreSQL the failed statement aborts
  the transaction, so **the fallback fails too and the whole save is lost with
  *"Error saving expense: …"***. On SQLite the fallback succeeds and the method
  is silently discarded. The deployment configured in `.env` is PostgreSQL.
- **Two expense entry forms with different category lists.** Finance offers ten
  categories (Supplies, Medications, Utilities, Salaries, Rent, Maintenance,
  Equipment, Marketing, Lab, Other); Accounting offers six
  (Medicines/Supplies, Staff Salaries, Utilities, Equipment, Marketing,
  Miscellaneous). They write to the same column, so the same clinic ends up
  with overlapping, non-matching category names — which then fragment the P&L
  grouping and the budget matching.
- **Budget matching is an exact string match** on the category, so an expense
  filed under `Supplies` never counts against a `Medicines/Supplies` target.
- **The Finance expense form parses the amount with a bare `float()`.** A
  posted value that is not a number raises and returns a 500. The browser's
  `type="number"` guard normally prevents this; a submission that bypasses it
  does not.
- **The Budget save uses PostgreSQL-only SQL** — `NOW()` and `ON CONFLICT …
  EXCLUDED`. On a SQLite deployment `NOW()` does not exist and the save fails
  with *"Error saving budget: …"*.
- **The Vendor → Supplier link is a name string match.** Rename a supplier and
  every historical expense stops linking.
- Notes typed on the Finance expense form are stored but **never displayed
  anywhere**.

> Source: `platform/blueprints/accounting/routes.py:382-428`, `:540-570`,
> `platform/blueprints/finance/routes.py:771`,
> `platform/models/database.py:1762-1774`,
> `platform/templates/finance/expenses_list.html:101-141`,
> `platform/templates/accounting/expenses_list.html:124-167`

### Lists and filters

- **No pagination anywhere.** Hard caps: invoices 200, expenses 200 (Finance)
  and 300 (Accounting), estimates 100, credit-ledger entries 100, open
  invoices on the account page 100, recent invoices on the dashboard 10.
- **The invoice search runs after the cap.** `q` is applied in Python to the
  200 rows already fetched, so an invoice older than the most recent 200 cannot
  be found by searching for it. Narrow with the date filters first.
- **The invoices list totals row is not a ledger total** — it sums only the
  rows currently shown.
- **Estimates cannot be filtered by client or date**, only by status.
- **The Cash Flow running balance starts at zero** at the beginning of the
  chosen range. It is not a bank or till balance.
- **Client deposits do not appear in Cash Flow or Daily Closing** until they
  are applied to an invoice, because those screens read the payments ledger.
- **`/finance/expenses` has no link anywhere in the application.** It is
  reachable only by typing the URL. `/finance/reports` is reachable only via
  the dashboard revenue chart, which is itself hidden when there is no revenue
  data.
- **The Accounting dashboard swallows every query error** in a bare
  `try/except` and renders `0 EGP` with no indication that anything failed.

> Source: `platform/blueprints/finance/routes.py:151-197`, `:820-829`,
> `platform/blueprints/accounting/routes.py:23-152`, `:336`,
> `platform/models/database.py:3728-3739`, `:3802-3808`

### Printing and export

- **The Payment History block on the printed invoice never renders.** The print
  route loads the invoice through `get_invoice`, which sets `payments` to an
  empty list unconditionally; only the on-screen detail page re-reads the real
  rows.
- **The estimate print header renders an empty clinic name.** The template
  reads `clinic.clinic_name`, and the column is called `name`. The `else`
  fallback never fires because the clinic row exists, so the heading and the
  footer print blank.
- **The estimate print page has no print or close buttons** — use the browser.
- **The Excel export is English-only** and exports invoices only. Expenses,
  payments and the P&L are not exported anywhere.
- **PDF generation depends on fpdf2 and the bundled Cairo fonts.** With the
  fonts missing, any Arabic content fails; the module logs a warning at
  start-up.

> Source: `platform/blueprints/finance/routes.py:663-675`,
> `platform/models/database.py:3620-3634`,
> `platform/templates/finance/estimate_print.html:6`, `:36`, `:107`,
> `platform/models/database.py:1110-1133` (clinic schema),
> `platform/models/pdf_generator.py:52-67`

### Bilingual coverage

- **Statuses are never translated.** `Paid` / `Unpaid` / `Partial` /
  `Cancelled` on invoices and `Draft` / `Sent` / `Approved` / `Declined` /
  `Expired` / `Converted` on estimates render in English in both languages.
- **Line types render untranslated** on the invoice detail, the print view and
  the reports — the raw stored string.
- **Credit-ledger `kind` values** (`deposit`, `applied`, `refund`) render in
  English.
- **The WhatsApp invoice message is English-only** and hardcoded to "Aleefy"
  branding, ignoring the clinic's configured name.
- **The credit-note confirm dialog is English-only**: *"Issue a credit note for
  this invoice?"*
- **All flash messages from both blueprints are English-only** — every
  validation error, every success message, every permission refusal.
- **The Excel export headers and sheet title are English-only.**
- On the printed invoice, `Issued:` and `Due:` are English-only labels while
  everything around them is translated.

> Source: `platform/blueprints/finance/routes.py:709-736` (WhatsApp body),
> `platform/templates/finance/invoice_detail.html:285`,
> `platform/templates/finance/invoice_print.html:56-57`,
> `platform/templates/finance/owner_credit.html:54`,
> `platform/blueprints/finance/routes.py:912-959` (export headers)
