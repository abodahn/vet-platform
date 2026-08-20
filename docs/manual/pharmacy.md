# Pharmacy, Inventory and Procurement — Reference Manual

**Modules:** Pharmacy / الصيدلية · Inventory / المخزون · Procurement / المشتريات
**URL prefixes:** `/pharmacy/` · `/inventory/` · `/procurement/`
**Blueprints:** `pharmacy`, `inventory`, `procurement`

This chapter is a **screen-by-screen reference**. It describes only what the code
in `blueprints/pharmacy/routes.py`, `blueprints/inventory/routes.py`,
`blueprints/procurement/routes.py` and their templates actually does today.
Fields that exist in the database but have no screen, and controls that do not do
what their label suggests, are listed under [Known limits](#known-limits) rather
than described as working.

> Source: `platform/app.py:215,228,232` (imports), `platform/app.py:243,256,260`
> (registration), `platform/blueprints/pharmacy/__init__.py:1-3`,
> `platform/blueprints/inventory/__init__.py:1-5`,
> `platform/blueprints/procurement/__init__.py:1-3`

---

## 1. Getting into the modules

| Door | Where | Goes to |
|---|---|---|
| Sidebar → CLINIC / العيادة → **Pharmacy / الصيدلية** | every page | `/pharmacy/` |
| Sidebar → BUSINESS / الأعمال → **Inventory / المخزون** | every page | `/inventory/` |
| Sidebar → BUSINESS / الأعمال → **Procurement / المشتريات** | every page | `/procurement/` |
| Launcher quick card **Inventory / المخزون** (📦) | `/` | `/inventory/` |
| Launcher module card **Inventory & Warehouse / المخزون والمستودع** | `/` | `/inventory/` |
| Launcher module card **Pharmacy & Medication / الصيدلية والأدوية** | `/` | `/inventory/items?is_medication=1` |
| Launcher module card **Pharmacy Dispensing / صرف الصيدلية** | `/` | `/pharmacy/` |
| Launcher module card **Procurement & Suppliers / المشتريات والموردون** | `/` | `/procurement/` |

The three sidebar entries carry **no role condition**. Every signed-in user sees
them. A user whose role does not hold the matching grant will click, and be
bounced back to the launcher with *"You don't have permission to access this
page."* — see §2.

Note that the launcher card called **Pharmacy & Medication** does *not* open the
pharmacy module. It opens the inventory items list pre-filtered to medications.
The dispensing queue is the separate **Pharmacy Dispensing** card.

> Source: `platform/templates/base.html:130-133` (Pharmacy),
> `:197-200` (Inventory), `:211-214` (Procurement);
> `platform/templates/launcher.html:466-470` (quick card),
> `platform/templates/launcher.html:606-616` (card link uses `mod.url`);
> `platform/blueprints/launcher/routes.py:231-274, 400-415` (card definitions)

---

## 2. Who can open what

Two independent gates apply to every screen in all three modules, and **both must
pass**:

1. **The module grant.** The signed-in role must hold the permission key that
   matches the blueprint name — `pharmacy`, `inventory`, `procurement`. This is
   checked inside `login_required`, so it applies to every route in the module,
   including routes that carry no role list of their own. `super_admin` bypasses
   it.
2. **The route's own role list**, where one is written into the route.

Grants are editable per role on the Roles screen. The table below is the
**shipped default**.

> Source: `platform/blueprints/auth/routes.py:59-69` (`login_required`),
> `:89-134` (`_permission_denied`, the module gate),
> `:140-163` (blueprint → permission key mapping),
> `platform/models/database.py:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

Roles holding each grant by default:

| Grant | Roles (plus `super_admin`, which is exempt from both gates) |
|---|---|
| `pharmacy` | clinic_owner, branch_manager, doctor, nurse, pharmacist |
| `inventory` | clinic_owner, branch_manager, pharmacist, inventory_mgr |
| `procurement` | clinic_owner, branch_manager, inventory_mgr |

### Route-level role lists

| Constant | Value | Guards |
|---|---|---|
| `_DISPENSER_ROLES` | super_admin, clinic_owner, branch_manager, pharmacist, inventory_mgr, nurse, doctor | the **Dispense** button on the prescription page, the dispense POST, and the Narcotics Register |
| `_allowed` (transfer) | super_admin, clinic_owner, branch_manager, inventory_mgr, pharmacist | Stock Transfer (GET and POST) |

> Source: `platform/blueprints/pharmacy/routes.py:12-15`,
> `platform/blueprints/inventory/routes.py:541`

### Effective access, per screen

| Screen | Route | Who can actually use it |
|---|---|---|
| Dispensing Queue | `GET /pharmacy/` | clinic_owner, branch_manager, doctor, nurse, pharmacist, super_admin |
| Prescription detail | `GET /pharmacy/prescription/<rx_id>` | same as above |
| Dispense (submit) | `POST /pharmacy/dispense/<rx_id>` | same as above |
| Dispensing History | `GET /pharmacy/history` | same as above |
| Narcotics Register | `GET /pharmacy/narcotics` | same as above |
| Label | `GET /pharmacy/label/<rx_id>/<pi_id>` | same as above |
| All `/inventory/*` except Transfer | various | clinic_owner, branch_manager, pharmacist, inventory_mgr, super_admin |
| Stock Transfer | `GET`/`POST /inventory/transfer` | same as above (the route's own list is a superset of the grant list) |
| All `/procurement/*` | various | clinic_owner, branch_manager, inventory_mgr, super_admin |

`inventory_mgr` appears in `_DISPENSER_ROLES` but does **not** hold the `pharmacy`
grant by default, so an inventory manager is stopped at the module gate before
the dispenser check is ever reached. Granting `pharmacy` to that role on the
Roles screen makes the dispenser check meaningful for them.

---

# PART A — PHARMACY

## A1. Dispensing Queue / قائمة صرف الصيدلية

**Route:** `GET /pharmacy/` — endpoint `pharmacy.index`
**Purpose:** every prescription that is not yet fully dispensed.

### What is listed

All rows from `prescriptions` **whose status is not `Dispensed`**, newest first
by `created_at`, capped at **100 rows**. There is no filter, no search and no
paging on this screen.

### Columns

| Column (EN / AR) | Meaning |
|---|---|
| **#** | `RX-<prescription id>` |
| **Pet / Owner** — الحيوان / المالك | Pet name (links to the pet record when the pet row still exists) + species badge; owner name (links to the owner) and phone underneath. If the pet or owner row was deleted, the name shows as plain text or `—` and does not link. |
| **Doctor** — الطبيب | `visits.doctor_name` of the linked visit, or `—` |
| **Visit Date** — تاريخ الزيارة | `visits.visit_date`, linked to the visit. `—` if the visit row is gone. |
| **Items** — الأصناف | `dispensed / total` badge. Green when all items are dispensed, amber when some are, plain when none are. |
| **Status** — الحالة | `prescriptions.status` verbatim: normally `Active` or `Partial`. |
| **Created** — تاريخ الإنشاء | first 10 characters of `created_at` (the date) |
| **Action** — الإجراء | **Dispense / صرف** button → the prescription detail page |

Because the queue joins visit, pet and owner with LEFT JOINs, a prescription
whose visit, pet or owner record was deleted **still appears** and can still be
opened.

### Top-bar buttons

| Button | Effect |
|---|---|
| **Dispensing History / سجل الصرف** | → `/pharmacy/history` |
| **Narcotics Register / سجل المخدرات** | → `/pharmacy/narcotics` |

### Empty state

💊 *"Queue is clear / قائمة الانتظار فارغة"*.

> Source: `platform/blueprints/pharmacy/routes.py:18-42`,
> `platform/templates/pharmacy/index.html:1-78`

---

## A2. Prescription detail / dispense screen

**Route:** `GET /pharmacy/prescription/<rx_id>` — endpoint `pharmacy.rx_detail`
**Reached from:** the Dispense button in the queue; the RX Ref link in the
Narcotics Register.
**Purpose:** see what was prescribed, pick batches, and dispense.

If the prescription id does not exist: flash *"Prescription not found."* and
redirect to the queue.

### Header cards

| Card | Contents |
|---|---|
| **Patient / المريض** | pet name (linked when the pet row exists), species, weight in kg (`?` when unknown), plus links **Imaging → / الأشعة ←** and **Vaccinations → / التطعيمات ←** for that pet |
| **Owner / المالك** | owner name (linked when the owner row exists) and phone |
| **Doctor / Visit — الطبيب / الزيارة** | `visits.doctor_name`, `visits.visit_date`, and a link **"Open the visit that prescribed this →"**. When no visit row is linked it says *"No visit record is linked to this prescription."* |
| **Status / الحالة** | `prescriptions.status` badge, plus `dispensed_at` (first 16 characters) when set |

A **Chief Complaint / الشكوى الرئيسية** card appears below when the linked visit
has one.

### Prescription Items table / بنود الوصفة

| Column | Meaning |
|---|---|
| **Medication / دواء** | `prescription_items.medication_name`, falling back to the linked stock item's name. A red **Controlled / خاضع للرقابة** badge appears when the linked stock item has `is_controlled`. Unit underneath. |
| **Prescribed Qty / الكمية الموصوفة** | `prescription_items.quantity` |
| **Instructions / التعليمات** | `prescription_items.instructions` |
| **Stock / المخزون** | Sum of **all** batches for the linked item (expired batches included). Red at zero, amber when below the prescribed quantity, green otherwise. `—` for a free-text medication with no linked stock item. |
| **Batch / الدفعة** *(only when you may dispense and the RX is not fully dispensed)* | see below |
| **Dispense Qty / كمية الصرف** *(same condition)* | number input, pre-filled with the prescribed quantity, `min=0.01`, `step=0.01` |
| **Status / الحالة** | `Dispensed` or `Pending` |
| **Label / الملصق** | **🖨 Label / 🖨 ملصق** → opens the printable label in a new tab |

Rows for already-dispensed items are tinted green.

### The Batch selector

Four possible states per row:

| State | What you see |
|---|---|
| Item already dispensed | green **Dispensed / تم الصرف** badge |
| Item linked to stock **and** at least one batch has quantity > 0 | a dropdown. First option is **Auto (FEFO) / تلقائي (FEFO)**. Then one option per batch, ordered by expiry ascending, reading `<batch number or "Batch #id"> · exp <expiry> · <qty> <unit> · <warehouse>` |
| Item is free text with no stock item | *"No inventory item / لا يوجد صنف بالمخزون"* |
| Item linked to stock but every batch is empty | red **No stock / لا يوجد مخزون** badge |

The dropdown lists **every** batch with quantity > 0, including expired ones.
Choosing an expired batch is rejected at submit time (see A3).

### Form controls at the foot of the card

| Control | Required | Effect |
|---|---|---|
| **Dispensing Notes / ملاحظات الصرف** (text) | no | stored on every `dispensing_log` row written by this submit |
| **💊 Dispense Selected / 💊 صرف المحدد** (submit) | — | posts to `/pharmacy/dispense/<rx_id>` |

The whole form — batch selects, quantity inputs, notes and button — is rendered
only when the signed-in role is in `_DISPENSER_ROLES` **and** the prescription
status is not `Dispensed`. Otherwise the page is read-only.

### The "Not screened" panel / لم يتم الفحص

A grey panel at the bottom states that the prescription has **not** been checked
against species contraindications, drug interactions or dosing. Its button
**"Open drug reference for this patient →"** POSTs the medication names, species,
breed and weight to `/cds/`. The panel's own text says the reference data is a
DRAFT that has not been reviewed by a licensed veterinarian, and that opening it
does not check, clear or approve the prescription. Nothing on this screen
performs any safety screening.

> Source: `platform/blueprints/pharmacy/routes.py:72-124`,
> `platform/templates/pharmacy/rx_detail.html:1-208`

---

## A3. What the Dispense button actually does

**Route:** `POST /pharmacy/dispense/<rx_id>` — endpoint `pharmacy.dispense`
Always redirects back to the prescription detail page.

Roles outside `_DISPENSER_ROLES` get *"Access denied."* and a redirect.

For each prescription item that is **not already** marked dispensed:

**1. Free-text medication (no linked stock item).**
The item is marked dispensed, and an `audit_log` row is written with action
`dispensed_untracked_medication`. **No stock is deducted and no `dispensing_log`
row is written** — there is no stock item to move. Such a hand-over therefore
never appears in Dispensing History or the Narcotics Register; it exists only in
the audit log.

**2. A batch was chosen explicitly.** The batch is rejected, with a red flash and
that item left pending, if:
   - it does not belong to this item — *"Invalid batch for …"*
   - its expiry date is earlier than today — *"Batch … expired on … — cannot dispense"*
   - it holds less than the quantity being dispensed — *"Insufficient stock in selected batch for … (have X, need Y)"*

**3. No batch chosen — Auto (FEFO).** The system picks **one** batch that
(a) belongs to the item, (b) holds at least the whole requested quantity on its
own, and (c) is not already expired, taking the nearest expiry first. If no
single batch satisfies all three, the item fails with *"Insufficient stock for …"*.
**Quantities are never split across two batches on this path.**

On success, per item, four things are written:
- `batches.quantity` is reduced by the dispensed quantity
- a `stock_movements` row, `movement_type = 'Dispensed'`, `reference_type = 'prescription'`, `reference_id = <rx_id>`
- a `dispensing_log` row carrying item, batch, visit, pet, quantity, dispenser and the notes field
- `prescription_items.dispensed = 1`
- and, when the item is flagged `is_controlled`, an extra `audit_log` row with action `controlled_drug_dispensed`

**Quantity behaviour:** the Dispense Qty box defaults to the prescribed quantity
but is not capped by it. Entering a larger number dispenses the larger number, as
long as the batch holds it.

**After the loop:**
- **If there were no errors** — the prescription is set to `Dispensed` when no
  items remain pending, otherwise `Partial`; `dispensed_at` is stamped; an audit
  entry `prescription_dispensed` is written; you get a green
  *"Prescription fully / partially dispensed."*
- **If there were any errors** — every error is flashed in red, and the
  prescription's **status is left unchanged**. Items that succeeded in the same
  submit are still committed. So a partly-failed dispense leaves the queue
  showing e.g. `2/3 dispensed` while the Status column still reads `Active`.

> Source: `platform/blueprints/pharmacy/routes.py:127-280`

---

## A4. Dispensing label / ملصق الصرف

**Route:** `GET /pharmacy/label/<rx_id>/<pi_id>` — endpoint `pharmacy.label`
Opens in a new browser tab as a standalone print page (no sidebar).

Shows: clinic name, address and phone from clinic settings; `Rx #<id>`;
**Patient / المريض** (pet name, species, weight); **Owner / المالك**;
**Medication / دواء** (with unit); **Quantity / الكمية**;
**Instructions / التعليمات** and **Frequency / التكرار** when present; and a
footer line reading `Dispensed: <today> | Doctor: … | Visit: …`.

Two buttons, both hidden when printing: **🖨 Print Label / 🖨 طباعة الملصق**
(browser print dialog) and **Close / إغلاق**.

If the prescription or the item cannot be found, you are redirected to the
prescription page with *"Label data not found."*

The label uses `datetime.date.today()` for the dispensed date — it is the date
the label was **printed**, not the date the medicine was dispensed.

See [Known limits](#known-limits) for the Doctor, Visit and Duration fields.

> Source: `platform/blueprints/pharmacy/routes.py:349-373`,
> `platform/templates/pharmacy/label.html:1-101`

---

## A5. Dispensing History / سجل الصرف

**Route:** `GET /pharmacy/history` — endpoint `pharmacy.history`
**Purpose:** every stock-backed dispensing event, newest first.

### Filter

| Field | Default | Behaviour |
|---|---|---|
| **From Date / من تاريخ** (`date_from`) | **today** | shows events on or after this date |

There is a **Filter / تصفية** button and no reset link. There is no "to" date.
The list is capped at **200 rows**.

Because the default is today, this screen opens showing only today's dispensing.
Set the date back to see more.

### Columns

| Column (EN / AR) | Meaning |
|---|---|
| **Time / الوقت** | `dispensed_at`, first 16 characters (date + time) |
| **Pet / Owner — الحيوان / المالك** | pet name; owner name underneath. Not links. |
| **Medication / دواء** | stock item name; unit underneath |
| **Batch / الدفعة** | batch number, or `—` |
| **Expiry / الانتهاء** | batch expiry date |
| **Qty / الكمية** | quantity dispensed |
| **Dispensed By / صُرف بواسطة** | username of the dispenser |
| **RX Status / حالة الوصفة** | the parent prescription's current status |

**Top bar:** **← Queue / ← قائمة الانتظار**.

This list is built from `dispensing_log` joined to prescription, pet, owner and
item with **inner** joins. A row whose pet or item record has since been deleted
disappears from the list.

> Source: `platform/blueprints/pharmacy/routes.py:45-69`,
> `platform/templates/pharmacy/history.html:1-75`

---

## A6. Narcotics & Controlled Drugs Register / سجل المخدرات والمواد الخاضعة للرقابة

**Route:** `GET /pharmacy/narcotics` — endpoint `pharmacy.narcotics`
Restricted to `_DISPENSER_ROLES`; anyone else is redirected to the queue with
*"Access denied."*

A purple **Regulatory Notice / إشعار تنظيمي** banner states that the register
records all controlled-substance dispensing events, must be kept accurate, is
subject to inspection, and is generated automatically from dispensing records.

### KPI cards

| Card (EN / AR) | What it counts |
|---|---|
| **Dispensing Events / عمليات الصرف** | number of rows currently shown (after filters, capped at 500) |
| **Total Units Dispensed / إجمالي الوحدات المصروفة** | sum of the quantity column of the rows shown, to 2 decimals |
| **Controlled Substances / المواد الخاضعة للرقابة** | count of **all** active items flagged `is_controlled` — **not** affected by the filters |

### Filters

| Field | Default |
|---|---|
| **From / من** (`date_from`) | first day of the current month |
| **To / إلى** (`date_to`) | today |
| **Substance / المادة** (`item_id`) | *All Controlled Substances / جميع المواد الخاضعة للرقابة* — the dropdown lists active `is_controlled` items by name |

Buttons: **Filter / تصفية** and **Reset / إعادة تعيين** (returns to the defaults).

### Columns

`#` (row number within the page), **Date & Time / التاريخ والوقت** (date on top,
`HH:MM` underneath), **Substance / Drug — المادة / الدواء** (name, with unit and
category underneath), **Batch / الدفعة** (batch number, with `Exp: <date>`
underneath), **Qty / الكمية**, **Patient / المريض** (name and species),
**Owner / المالك**, **Doctor / الطبيب** (from the visit),
**Dispensed By / صُرف بواسطة**, **RX Ref / مرجع الوصفة** (links to the
prescription).

### Buttons

| Button | Effect |
|---|---|
| **Dispensing Queue / قائمة الصرف** | → `/pharmacy/` |
| **Full History / السجل الكامل** | → `/pharmacy/history` |
| **Print Register / طباعة السجل** | browser print dialog; sidebar, topbar, filters and buttons are hidden in print |

The register is built from `dispensing_log` with inner joins to item, pet, owner,
prescription and **visit**. Only stock-backed dispensing appears here — a
controlled drug prescribed as free text and handed over is not in this register
(see A3, case 1).

> Source: `platform/blueprints/pharmacy/routes.py:283-346`,
> `platform/templates/pharmacy/narcotics.html:1-152`

---

# PART B — INVENTORY

## B1. Inventory Dashboard / لوحة تحكم المخزون

**Route:** `GET /inventory/` — endpoint `inventory.dashboard`
Page title **Inventory & Pharmacy / المخزون والصيدلية**.

### Stat cards

| Card (EN / AR) | What it shows |
|---|---|
| **Total Active Items / إجمالي الأصناف النشطة** | `COUNT(*)` of items with `is_active = 1` |
| **Low Stock Alerts / تنبيهات المخزون المنخفض** | number of items whose total batch quantity is **at or below** their reorder level |
| **Expiry Alerts (30 days) / تنبيهات انتهاء الصلاحية (30 يوم)** | number of batches with stock left whose expiry date is on or before today + 30 days |
| **Total Inventory Value / إجمالي قيمة المخزون** | `SUM(quantity × unit_cost)` over batches with quantity > 0 belonging to active items, shown with no decimals. Sub-label: **EGP (cost basis) / جنيه مصري (بالتكلفة)** |

### Sections

- **🔴 Low Stock Items / أصناف المخزون المنخفض** — up to **8** cards; each shows
  the item name, its current stock, its reorder level, and a
  **View Item → / عرض الصنف →** link. Header link **View all alerts →**.
- **🟡 Expiring Soon (30 days) / تنتهي صلاحيتها قريباً** — up to **6** cards, each
  showing item name, remaining quantity, batch number and expiry date. Header
  link **View all →**.
- **📋 Recent Stock Movements / حركات المخزون الأخيرة** — the **last 10**
  movements. Columns: **Date / التاريخ**, **Item / الصنف**, **Type / النوع**
  (colour badge: green `IN` / وارد, red `OUT` / صادر, amber `ADJ` / تسوية, grey
  for anything else, uppercased), **Quantity / الكمية**,
  **Reference / المرجع** (plain reference type text on this screen — the
  clickable version is on the item and movements pages), **By / بواسطة**.
  Header link **View all →**.

Both alert sections are hidden entirely when empty.

### Top-bar buttons

| Button | Goes to |
|---|---|
| **+ New Item / + صنف جديد** | `/inventory/items/new` |
| **Receive Stock / استلام مخزون** | `/inventory/batches/new` (no item preselected) |
| **Transfer Stock / نقل مخزون** | `/inventory/transfer` |

> Source: `platform/blueprints/inventory/routes.py:92-120`,
> `platform/templates/inventory/dashboard.html:1-195`

---

## B2. Inventory Items / أصناف المخزون

**Route:** `GET /inventory/items` — endpoint `inventory.items_list`
Lists **active items only** (`is_active = 1`), ordered by name. No paging, no row
cap.

### Filters (all in the query string, all optional)

| Field (EN / AR) | Parameter | Behaviour |
|---|---|---|
| **Search / بحث** | `q` | case-insensitive substring match against **name**, **SKU** or **barcode** ("Name, SKU, barcode… / الاسم، الرمز، الباركود…") |
| **Category / الفئة** | `category_id` | exact category; default *All Categories / كل الفئات* |
| **Type / النوع** | `is_medication` | `1` = *Medications Only / الأدوية فقط*, `0` = *Non-Medication / غير دوائي*, blank = *All Types / كل الأنواع* |

Buttons: **Search / بحث**, and **Clear / مسح** which appears only when at least
one filter is set. A counter line above the table reads *"N item(s) found"*.

### Columns

| Column (EN / AR) | Meaning |
|---|---|
| **SKU / رمز المنتج** | `items.sku` or `—` |
| **Name / الاسم** | English name, with the Arabic name underneath when present |
| **Category / الفئة** | category name or `—` |
| **Stock Level / مستوى المخزون** | a bar filled to `stock ÷ max_stock`, capped at 100%, plus the number to 1 decimal, plus *"Reorder: N"* underneath. **Red** when stock ≤ reorder level, **amber** when stock ≤ 2 × reorder level, **green** above that. |
| **Unit / الوحدة** | `items.unit` |
| **Sell Price / سعر البيع** | `sell_price` to 2 decimals (no currency symbol on this screen) |
| **Type / النوع** | 💊 **Medication / دواء** badge, plus a red **Controlled / مادة خاضعة للرقابة** badge underneath when flagged; otherwise a grey **Supply / مستلزمات** badge |
| **Actions / إجراءات** | **View / عرض** → item detail · **Edit / تعديل** → edit form · **+Stock / +مخزون** → receive-stock form for this item |

The stock figure on this screen counts only batches whose quantity is greater
than zero.

**Top bar:** **+ New Item / + صنف جديد**, **Dashboard / لوحة التحكم**.
**Empty state:** *"No items found. / لا توجد أصناف."* with an **Add the first
item →** link.

> Source: `platform/blueprints/inventory/routes.py:127-170`,
> `platform/templates/inventory/items_list.html:1-177`

---

## B3. New Item / Edit Item

**Routes:**
`GET|POST /inventory/items/new` — endpoint `inventory.item_new`
`GET|POST /inventory/items/<item_id>/edit` — endpoint `inventory.item_edit`

Both use the same form. The heading is **New Item** or **Edit: \<name\>**. Edit
on a non-existent id returns 404.

### Fields

| Section | Field (EN / AR) | Name | Required | Stored as |
|---|---|---|---|---|
| 📦 Basic Information / المعلومات الأساسية | **Item Name (English) / اسم الصنف (إنجليزي)** | `name` | **yes** (browser `required`) | `items.name` |
| | **Item Name (Arabic) / اسم الصنف (عربي)** | `name_ar` | no | `items.name_ar`, blank → NULL. Input is RTL. |
| | **SKU / Item Code — رمز المنتج / كود الصنف** | `sku` | no | `items.sku`, blank → NULL. The column is UNIQUE — reusing an SKU fails (see below). |
| | **Barcode / الباركود** | `barcode` | no | `items.barcode` |
| | **Category / الفئة** | `category_id` | no | `items.category_id`; blank → NULL |
| | **Unit of Measure / وحدة القياس** | `unit` | dropdown, always sends a value | one of `tablet, capsule, vial, bottle, ampoule, bag, box, tube, unit, ml, mg, g, kg, L, piece`. Default on a new item: `unit`. |
| 💰 Pricing / التسعير | **Cost Price (EGP) / سعر التكلفة (جنيه)** | `cost_price` | no | `items.cost_price`; blank → 0 |
| | **Sell Price (EGP) / سعر البيع (جنيه)** | `sell_price` | no | `items.sell_price`; blank → 0 |
| 📊 Stock Rules / قواعد المخزون | **Reorder Level / مستوى إعادة الطلب** | `reorder_level` | no | blank → **10** |
| | **Maximum Stock / الحد الأقصى للمخزون** | `max_stock` | no | blank → **1000** |
| 🏷️ Item Flags / خصائص الصنف | **💊 Medication / دواء** | `is_medication` | checkbox | *"This item is a veterinary medication or drug."* |
| | **🔒 Controlled Substance / مادة خاضعة للرقابة** | `is_controlled` | checkbox | drives the Controlled badge and the Narcotics Register |
| | **📋 Requires Prescription / يستلزم وصفة طبية** | `requires_rx` | checkbox | *"Cannot be dispensed without a valid prescription."* — stored and displayed only; nothing in the pharmacy module enforces it |
| 🌡️ Storage Notes / ملاحظات التخزين | **Storage Instructions / تعليمات التخزين** | `storage_notes` | no | free text |

Numeric fields are `type=number`; the server converts with a plain `float(... or 0)`,
so a value the browser lets through but Python cannot parse raises the error
handler described below.

### Buttons

| Button | Effect |
|---|---|
| **Cancel / إلغاء** | back to the items list, nothing saved |
| **✅ Create Item / إنشاء الصنف** (new) | inserts the item with `is_active = 1`, flashes *"Item created successfully."*, redirects to the new item's detail page |
| **💾 Save Changes / حفظ التغييرات** (edit) | updates the row and `updated_at`, flashes *"Item updated successfully."*, redirects to the item detail page |

On a database error (duplicate SKU is the common one) the form is re-rendered
with a red flash reading *"Error creating item: …"* / *"Error saving item: …"*
carrying the raw database message. **On the create path the values you typed are
not returned to the form** — `item=None` is passed back, so the form comes up
blank and everything must be retyped.

> Source: `platform/blueprints/inventory/routes.py:177-235` (new),
> `:325-384` (edit), `platform/templates/inventory/item_form.html:1-199`

---

## B4. Item detail / تفاصيل الصنف

**Route:** `GET /inventory/items/<item_id>` — endpoint `inventory.item_detail`
404 on an unknown id.

### Top-bar buttons

**+ Receive Stock / + استلام مخزون** (→ receive form for this item),
**Edit Item / تعديل الصنف**, **← Items / ← الأصناف**.

### 📦 Item Information / معلومات الصنف

SKU, Barcode, Category, Unit, **Cost Price / سعر التكلفة** and
**Sell Price / سعر البيع** (both prefixed `EGP`), **Reorder Level**,
**Max Stock**, **Type** (the same badge set as the list, plus a
📋 **Rx Required / يستلزم وصفة طبية** badge), **Arabic Name** and
**Storage Notes** when present.

### 📊 Current Stock / المخزون الحالي

A big total (sum of batch quantities greater than zero) with a badge:
**Below Reorder Level / أقل من مستوى إعادة الطلب** (red) when total ≤ reorder,
**Low Stock / مخزون منخفض** (amber) when ≤ 2 × reorder, **Stock OK / المخزون جيد**
(green) otherwise. Then one row per warehouse holding stock, or
*"No stock in warehouses"*.

Two buttons:

| Button | Effect |
|---|---|
| **+ Receive Stock / + استلام مخزون** | receive form, this item preselected |
| **🛒 Order \<N\> \<unit\> → / 🛒 طلب …** | opens the New Purchase Order form with this item already on a line, quantity **N**, and the item's preferred supplier preselected |

**N** is the suggested order quantity: enough to reach `max_stock` from current
stock, but never below the reorder level and never below 1.

### 📋 Stock Batches / دفعات المخزون

Every batch of this item — **including exhausted ones (quantity 0)** — ordered by
expiry date ascending, NULLs last.

Columns: **Batch # / رقم الدفعة**, **Lot # / رقم الحزمة**,
**Expiry Date / تاريخ انتهاء الصلاحية**, **Quantity / الكمية**,
**Unit Cost / تكلفة الوحدة** (`EGP`), **Warehouse / المستودع** (`Main / الرئيسي`
when unset), **Received / تاريخ الاستلام**.

The expiry cell is tagged **(EXPIRED) / (منتهي الصلاحية)** in red when the date is
before today and **(Soon) / (قريباً)** in amber when it is near — see
[Known limits](#known-limits) about the "Soon" calculation.

### 🏭 Suppliers / الموردون

The item's preferred supplier plus everyone who has ever shipped it on a purchase
order. Columns: **Supplier / المورد** (with a **Preferred / المفضل** badge on the
item's own supplier), **Phone**, **Email**, **Orders for this item / طلبات هذا
الصنف**, and a **View supplier → / عرض المورد ←** link. Empty state links to the
supplier directory.

### 🧾 Purchase Orders / أوامر الشراء

The **last 10** purchase orders carrying this item. Columns: **PO # / أمر الشراء**,
**Supplier / المورد** (linked), **Order Date / تاريخ الطلب**,
**Status / الحالة** (Received / Sent / Cancelled / Draft badges), **Qty Ordered /
الكمية المطلوبة**, and a link reading **Receive → / استلام ←** for a Draft or Sent
order and **View order → / عرض الطلب ←** otherwise. Empty state offers
**Order it now →**.

### 🔄 Movement History (Last 20) / سجل الحركات (آخر 20)

Columns: **Date / التاريخ**, **Type / النوع** (badges for `in`, `out`,
`adjustment`, `expired`; anything else uppercased),
**Quantity / الكمية**, **Reference / المرجع**, **Notes / ملاحظات**,
**By / بواسطة**.

The **Reference** cell becomes a link only for `visit`, `prescription` and
`purchase_order` references **whose target row still exists**; every other
reference type, and any dangling reference, stays as plain text.

> Source: `platform/blueprints/inventory/routes.py:242-318`,
> `:33-37` (linkable reference types), `:40-72`, `:75-85` (suggested quantity),
> `platform/templates/inventory/item_detail.html:1-375`

---

## B5. Receive Stock / استلام مخزون

**Route:** `GET|POST /inventory/batches/new` — endpoint `inventory.batch_new`
**Purpose:** book a delivery in as a new batch. This is the manual intake path;
receiving against a purchase order is a different screen (see C7).

Reached with `?item_id=<id>` from the item detail page, the items list `+Stock`
link and the low-stock cards; or with no item from the dashboard button, in which
case the form shows an item picker.

### Fields

| Field (EN / AR) | Name | Required | Notes |
|---|---|---|---|
| **Item * / الصنف *** | `item_id` | **yes** | shown as a dropdown of up to 1000 active items (`name · SKU`) **only when no item was preselected**. When an item was passed in the URL it becomes a hidden field and a blue context banner shows the item name, SKU and unit instead. |
| **Batch Number / رقم الدفعة** | `batch_number` | no | e.g. `BATCH-2024-001` |
| **Lot Number / رقم التشغيلة** | `lot_number` | no | manufacturer lot |
| **Manufacture Date / تاريخ التصنيع** | `manufacture_date` | no | date picker |
| **Expiry Date / تاريخ الانتهاء** | `expiry_date` | no | date picker. Leaving it blank creates a batch with **no expiry**, which FEFO treats as never expiring and sorts last. |
| **Quantity Received * / الكمية المستلمة *** | `quantity` | **yes** | must be > 0 |
| **Unit Cost (EGP) / تكلفة الوحدة (جنيه)** | `unit_cost` | no | feeds the inventory valuation on the dashboard |
| **Warehouse / المخزن** | `warehouse_id` | no | dropdown of active warehouses; falls back to warehouse **1** if nothing is sent |
| **Notes / ملاحظات** | `notes` | no | "Supplier info, delivery notes…" |

Quantity and unit cost are parsed leniently: thousands separators, Arabic digits,
spaces and a leading `EGP`, `ج.م`, `£` or `$` are all accepted. Anything that is
still not a number is **rejected with a red flash naming the field** — it is never
silently read as zero.

### Buttons

| Button | Effect |
|---|---|
| **💾 Receive Stock / 💾 استلام مخزون** | validates, then inserts one `batches` row and one `stock_movements` row (`movement_type = 'in'`, `reference_type = 'receiving'`, `created_by` = your **full name**), flashes *"Stock received: N units added."*, redirects to the item detail page |
| **Cancel / إلغاء** | shown only when an item was preselected; returns to the item detail page |

Failure paths:
- unparseable quantity or cost → red flash, back to where you came from
- missing item or quantity ≤ 0 → *"Item and positive quantity are required."*
- database error → *"Error receiving stock: …"*, redirect to the item detail page

> Source: `platform/blueprints/inventory/routes.py:391-468`,
> `platform/templates/inventory/batch_form.html:1-117`,
> `platform/models/money.py:55-82` (number parsing)

---

## B6. Stock Alerts / تنبيهات المخزون

**Route:** `GET /inventory/alerts` — endpoint `inventory.alerts`
No filters on this screen.

### 🔴 Low Stock / مخزون منخفض (N items)

One card per item whose total batch quantity is at or below its reorder level.
Each card shows: item name, category and unit, a red progress bar
(`stock ÷ reorder level`, capped at 100%), **Current: / الحالي:** *N* and
**Reorder at:** *N*, then two links —
**View Item → / عرض الصنف ←** and **Order \<qty\> \<unit\> → / طلب …** which opens
the New Purchase Order form pre-loaded with that item, the suggested quantity, and
the item's preferred supplier.

Next to the section heading, when the list is not empty:
**Order All Short Items → / طلب جميع الأصناف الناقصة** — one purchase order form
carrying **every** short item with its own suggested quantity.

Empty state: ✅ *"No low stock items. All inventory levels are healthy."*

### ⚠️ Expiring Soon (N batches)

A table of every batch with stock left whose expiry is on or before today + 30
days. **This includes batches that already expired** — there is no lower bound on
the date.

| Column (EN / AR) | Meaning |
|---|---|
| **Item / الصنف** | item name, linked to the item |
| **Batch / الدفعة** | batch number, linked to the item page's batch section |
| **Expiry Date / تاريخ الانتهاء** | the date |
| **Qty / الكمية** | remaining quantity, whole numbers |
| **Status / الحالة** | **Expired / منتهية** (red) when the date is today or earlier; **Critical / حرج** (amber) when it falls inside the 7-day window; **Warning / تحذير** (yellow) otherwise |
| **Action / الإجراء** | **Batch → / الدفعة ←** (item page) and **Replace → / استبدال ←** (new purchase order for that item, quantity pre-filled with the expiring batch's quantity) |

Empty state: ✅ *"No items expiring within the next 30 days."*

**Top bar:** **← Dashboard / ← لوحة التحكم**, **View All Items / عرض كل الأصناف**.

There is **no write-off, disposal or quarantine action** anywhere on this screen —
the only offered response to expiring stock is to order a replacement.

> Source: `platform/blueprints/inventory/routes.py:475-496`,
> `platform/models/database.py:3534-3544`,
> `platform/templates/inventory/alerts.html:1-160`

---

## B7. Stock Movements / حركات المخزون

**Route:** `GET /inventory/movements` — endpoint `inventory.movements`
**Purpose:** the full movement ledger.

### Filters

| Field (EN / AR) | Parameter | Options |
|---|---|---|
| **Item / الصنف** | `item_id` | *All Items / جميع الأصناف*, then every active item by name |
| **Type / النوع** | `type` | *All Types*, **Stock In / وارد** (`in`), **Stock Out / منصرف** (`out`), **Adjustment / تسوية** (`adjustment`), **Expired / منتهية** (`expired`), **Damaged / تالف** (`damaged`) |
| **Limit / الحد** | `limit` | **Last 50 / آخر 50**, **Last 100** (default), **Last 500** |

Buttons **Filter / تصفية** and **Reset / إعادة تعيين**.

The Type filter is applied **in Python after** the limit has been applied by the
database. Fetching the last 100 movements and then filtering to `out` gives you
the `out` rows *within those 100*, not the last 100 `out` rows. Raise the limit to
500 when filtering by type.

The dropdown does not offer the `Dispensed` or `Transfer` types that the pharmacy
and transfer screens actually write — see [Known limits](#known-limits).

### Columns

**Date/Time / التاريخ/الوقت** (first 16 characters), **Item / الصنف**,
**Type / النوع** (badge, lower-case, coloured per type),
**Qty / الكمية** (prefixed `+` and green for `in`, `−` and red for **everything
else**, rounded to a whole number), **Reference / المرجع** (a link for `visit`,
`prescription` and `purchase_order` references whose target still exists, plain
text otherwise), **By / بواسطة**, **Notes / ملاحظات**.

**Top bar:** **← Dashboard / ← لوحة التحكم**.
**Empty state:** *"No movements found / لا توجد حركات"*.

> Source: `platform/blueprints/inventory/routes.py:503-529`,
> `platform/models/database.py:3546-3557`,
> `platform/templates/inventory/movements.html:1-108`

---

## B8. Stock Transfer / تحويل مخزون

**Route:** `GET|POST /inventory/transfer` — endpoint `inventory.transfer`
**Purpose:** move a quantity of one batch from its warehouse to another.
Restricted to super_admin, clinic_owner, branch_manager, inventory_mgr,
pharmacist. Anyone else gets *"Access denied."* and the inventory dashboard.

### Left panel — From — Source / من — المصدر

| Field (EN / AR) | Name | Required | Behaviour |
|---|---|---|---|
| **Item / Product — الصنف / المنتج** | *(not submitted)* | yes (browser) | dropdown of all active items (`name (unit) — category`). Choosing one loads that item's batches over AJAX. |
| **Source Batch / الدفعة المصدر** | `batch_id` | **yes** | disabled until an item is chosen. Lists only batches with quantity > 0, nearest expiry first, labelled `<batch#> \| Wh: <warehouse> \| Qty: <n> \| Exp: <date>`. Shows *"No stock available"* when the item has none. |
| **Quantity to Transfer / الكمية المراد تحويلها** | `quantity` | **yes** | `min 0.01`, `step 0.01`. The browser caps it at the selected batch's quantity and blocks submit with an alert if it is exceeded; the server re-checks. |
| **Transfer Note (optional) / ملاحظة التحويل (اختياري)** | `notes` | no | appended to both movement records |

Choosing a batch reveals a summary box: **Batch No / رقم الدفعة**,
**Expiry / الانتهاء**, **Warehouse / المخزن**, **Available Stock / المخزون المتاح**.

### Right panel — To — Destination / إلى — الوجهة

| Field | Name | Required |
|---|---|---|
| **Destination Warehouse / المخزن الوجهة** | `to_warehouse_id` | **yes** |

**Transfer Stock → / تحويل المخزون ←** submits.

### What the transfer does

Rejections, each a red flash and a return to the empty form:
- quantity not a positive number → *"Invalid quantity."*
- batch id not found → *"Batch not found."*
- batch holds less than the quantity → *"Insufficient stock: only N available."*
- destination missing, or the same warehouse the batch is already in → *"Select a different destination warehouse."*

On success, in one transaction:
- the source batch is reduced by the quantity
- a batch at the destination with the **same item, batch number and expiry** is
  topped up; if there is none, a new batch is created there carrying the same
  batch number, expiry and unit cost, with today as the received date
- two `stock_movements` rows are written, both `movement_type = 'Transfer'` and
  `reference_type = 'transfer'`: one **negative** against the source batch, one
  positive against the destination batch. The notes name the other warehouse.
- an audit entry `stock_transfer` is written
- green flash *"Transferred N units to \<warehouse\> successfully."*

Any exception rolls the whole thing back with *"Transfer failed: …"*.

Lot number, manufacture date and the original notes are **not** copied to a newly
created destination batch.

### Supporting endpoint

`GET /inventory/transfer/batches-json?item_id=<id>` — endpoint
`inventory.transfer_batches_json`. Returns JSON: batch id, batch number, expiry,
quantity, unit cost, warehouse name and warehouse id, for batches with quantity
> 0, nearest expiry first. Used by the page's own JavaScript; it is not a screen.
Returns `[]` when `item_id` is missing.

**Top bar:** **Inventory Dashboard / لوحة المخزون**, **Movement Log / سجل الحركات**.

> Source: `platform/blueprints/inventory/routes.py:536-682`,
> `platform/templates/inventory/transfer.html:1-191`

---

# PART C — PROCUREMENT

## C1. Procurement Dashboard / لوحة المشتريات

**Route:** `GET /procurement/` — endpoint `procurement.dashboard`
Page title **Procurement & Suppliers / المشتريات والموردون**.

### Stat cards

| Card (EN / AR) | What it counts |
|---|---|
| **Suppliers / الموردون** | suppliers with `is_active = 1`. Links **Manage → / إدارة ←**. |
| **Open Orders / الطلبات المفتوحة** | purchase orders in status `Draft` **or** `Sent`. Links **View → / عرض ←** to the orders list filtered to `Draft` only. |
| **Items Received This Month / الأصناف المستلمة هذا الشهر** | despite the label, this is the **number of purchase orders** with status `Received` whose *order date* falls in the current calendar month — not a count of items, and not keyed on the received date. |
| **Total Spend EGP (Month) / إجمالي الإنفاق بالجنيه (الشهر)** | sum of `total` over the same set of orders, to 2 decimals |

### Recent Purchase Orders / أوامر الشراء الأخيرة

The **last 10** orders by creation time. Columns: **PO # / أمر شراء** (shown as
`#<database id>`, not the PO number), **Supplier / المورد**, **Date / التاريخ**,
**Items / الأصناف** (line count), **Total (EGP) / الإجمالي (جنيه)**,
**Status / الحالة** badge, and a **View / عرض** button.
Header link **View All / عرض الكل**.

Empty state: *"No purchase orders yet."* with **Create your first order →**.

**Top bar:** **+ New Order / + طلب جديد**, **Suppliers / الموردون**,
**All Orders / جميع الطلبات**.

> Source: `platform/blueprints/procurement/routes.py:11-47`,
> `platform/templates/procurement/dashboard.html:1-100`

---

## C2. Suppliers directory / الموردون

**Route:** `GET /procurement/suppliers` — endpoint `procurement.suppliers_list`
Two panels: the list on the left, an add form on the right. **All** suppliers are
listed, active and inactive, ordered by name. No filters, no search.

### List columns

**Name / الاسم**, **Contact**, **Phone / الهاتف**, **Email / البريد الإلكتروني**,
**Payment Terms / شروط الدفع**, **Active / نشط** (green **Yes / نعم** or red
**No / لا**), **# Orders** (purchase orders placed with this supplier), and a
**View / عرض** button.

### Add New Supplier form → `POST /procurement/suppliers/new`

| Field (EN / AR) | Name | Required | Notes |
|---|---|---|---|
| **Name / الاسم** * | `name` | **yes** — server-checked | empty name → *"Supplier name is required."* and back to this page |
| **Contact Person / مسؤول التواصل** | `contact_person` | no | stored in `suppliers.contact_name` |
| **Phone / الهاتف** | `phone` | no | |
| **Email / البريد الإلكتروني** | `email` | no | `type=email` |
| **Address / العنوان** | `address` | no | |
| **Payment Terms / شروط الدفع** | `payment_terms` | no | dropdown: *(blank)*, `Net 30`, `Net 60`, `COD (Cash on Delivery)`, `Prepaid`. Blank is stored as blank, **not** as the `Net 30` default. |
| **Notes / ملاحظات** | `notes` | no | |
| **Active Supplier** | `is_active` | checkbox, checked | **ignored** — every supplier is created active regardless (see Known limits) |

**Add Supplier** saves and returns to this page with *"Supplier 'X' added."*

There is no GET form at `/procurement/suppliers/new`; the route accepts POST only.

> Source: `platform/blueprints/procurement/routes.py:52-88`,
> `platform/templates/procurement/suppliers_list.html:1-128`

---

## C3. Supplier detail / بيانات المورد

**Route:** `GET /procurement/suppliers/<supplier_id>` — endpoint
`procurement.supplier_detail`. Unknown id → *"Supplier not found."* and back to
the directory.

**Top bar:** **← Suppliers / ← الموردون**, **✏️ Edit Supplier / ✏️ تعديل المورد**,
**+ New Order / + طلب جديد**.

### Supplier Information / بيانات المورد

An **Active / نشط** or **Inactive / غير نشط** badge in the header, then:
**Contact Person / مسؤول التواصل**, **Phone / الهاتف**,
**Email / البريد الإلكتروني**, **Payment Terms / شروط الدفع**,
**Address / العنوان**, **Member Since / مورد منذ** (first 10 characters of
`created_at`), and **Notes / ملاحظات** when present.

### Purchase Orders (N)

Every order for this supplier, newest first. Columns:
**PO # / أمر شراء** (linked; falls back to `#<id>` when the PO number is missing,
with the line count underneath), **Order Date / تاريخ الطلب**,
**Expected Date / التاريخ المتوقع**, **Status / الحالة** badge,
**Total (EGP) / الإجمالي (جنيه)**, **Notes / ملاحظات**, and a **View / عرض**
button. Header button **+ New Order / + طلب جديد**.

### Items Supplied / الأصناف المورَّدة (N)

The supplier's preferred items plus anything they have shipped on a PO, by name.
Columns: **Item / الصنف**, **In Stock / المتوفر** (total batch quantity, with a red
**Low / منخفض** badge when at or below the reorder level),
**Reorder Level / مستوى إعادة الطلب**, **Orders / الطلبات** (POs to this supplier
carrying this item), and a **View item → / عرض الصنف ←** link.

Header button **+ Order from this supplier / + الطلب من هذا المورد** — opens the
New Purchase Order form with this supplier selected and **one line per supplied
item**, each with quantity 1 and the item's cost price.

> Source: `platform/blueprints/procurement/routes.py:91-121`,
> `platform/templates/procurement/supplier_detail.html:1-183`

---

## C4. Edit Supplier / تعديل المورد

**Route:** `GET|POST /procurement/suppliers/<supplier_id>/edit` — endpoint
`procurement.supplier_edit`. Unknown id → back to the directory.

| Field (EN / AR) | Name | Required |
|---|---|---|
| **Supplier Name** * | `name` | **yes** — empty name is rejected server-side and you are sent back to this form |
| **Contact Person / مسؤول التواصل** | `contact_person` | no |
| **Phone / الهاتف** | `phone` | no |
| **Email / البريد الإلكتروني** | `email` | no |
| **Payment Terms / شروط الدفع** | `payment_terms` | no — dropdown: `Net 30`, `Net 15`, `Net 60`, `Due on Receipt`, `Prepaid` |
| **Address / العنوان** | `address` | no |
| **Notes / ملاحظات** | `notes` | no |
| **Active / نشط** | `is_active` | checkbox — here it **is** honoured; unchecking it sets the supplier inactive, which removes them from the supplier dropdown on the new-order form |

**💾 Save Changes / 💾 حفظ التغييرات** → *"Supplier 'X' updated."* and back to the
supplier page. **Cancel / إلغاء** discards.

Note the payment-terms list here differs from the one on the add form: this one
offers `Net 15` and `Due on Receipt`, the add form offers `COD`.

> Source: `platform/blueprints/procurement/routes.py:124-162`,
> `platform/templates/procurement/supplier_edit.html:1-64`

---

## C5. Purchase Orders list / أوامر الشراء

**Route:** `GET /procurement/orders` — endpoint `procurement.orders_list`
All orders, newest first by creation time. No row cap, no paging.

### Filters

| Field (EN / AR) | Parameter | Behaviour |
|---|---|---|
| **Status / الحالة** | `status` | *All Statuses / جميع الحالات* (value `All`, no filtering), `Draft` / مسودة, `Sent` / مُرسل, `Received` / مستلم, `Cancelled` / ملغى |
| **From Date / من تاريخ** | `date_from` | `order_date >=` |
| **To Date / إلى تاريخ** | `date_to` | `order_date <=` |

Buttons **Filter / تصفية** and **Clear / مسح**. The card header shows the active
status and the row count.

### Columns

**PO # / أمر شراء** — shown as `#<database id>`, **Date / التاريخ**,
**Supplier / المورد**, **Expected Date / التاريخ المتوقع**,
**Items / الأصناف** (line count), **Total (EGP) / الإجمالي (جنيه)**,
**Status / الحالة** badge, **View / عرض**.

**Top bar:** **+ New Order / + طلب جديد**, **← Dashboard / ← لوحة التحكم**.

> Source: `platform/blueprints/procurement/routes.py:167-191`,
> `platform/templates/procurement/orders_list.html:1-107`

---

## C6. New Purchase Order / أمر شراء جديد

**Routes:** `GET /procurement/orders/new` — endpoint `procurement.order_new_form`
`POST /procurement/orders/new` — endpoint `procurement.order_new_submit`

### Pre-filling from other screens

The GET form accepts repeatable query parameters so other screens can hand it a
ready-made order:

| Parameter | Effect |
|---|---|
| `item_id` (repeatable) | one line per id, in order. Ids that do not match an item are silently dropped. |
| `qty` (repeatable) | quantities, matched **positionally** to `item_id`. If the two lists are different lengths the whole quantity list is discarded and every line defaults to 1. A quantity of 0 or less also falls back to 1. |
| `supplier_id` | preselects the supplier |

Each prefilled line's unit price is the item's `cost_price`.

Screens that use this: the item detail **Order N** button, the low-stock cards and
**Order All Short Items**, the expiry table's **Replace**, and the supplier page's
**Order from this supplier**.

### 📦 Order Lines / بنود الطلب

One row per line, indexed from 1:

| Column (EN / AR) | Field name | Notes |
|---|---|---|
| **Item * / الصنف *** | `item_id_<n>` | dropdown of **all** items (`name (unit)`), including inactive ones. First option *— Select Item — / — اختر الصنف —*. |
| **Qty * / الكمية *** | `quantity_<n>` | `step 0.01`, `min 0` |
| **Unit Price / سعر الوحدة** | `unit_price_<n>` | `step 0.01`, `min 0` |
| **Total / الإجمالي** | — | computed in the browser as qty × price |
| ✕ | — | removes the row. Not shown on row 1. |

A hidden `description_<n>` field is submitted with every row; it is always empty
and is discarded on the server.

**+ Add Line / + إضافة بند** appends a row. **Total: / الإجمالي:** at the foot is
recalculated in the browser as you type.

### 🏷 Order Details / تفاصيل الطلب

| Field (EN / AR) | Name | Required |
|---|---|---|
| **Supplier * / المورد *** | `supplier_id` | **yes** — the dropdown lists **active** suppliers only |
| **Expected Delivery / التسليم المتوقع** | `expected_date` | no |
| **Status / الحالة** | `status` | no — only two choices here: **Draft / مسودة** (default) and **Sent to Supplier / أُرسل إلى المورد** |
| **Notes / ملاحظات** | `notes` | no |

**Create Order / إنشاء طلب** submits. **Cancel / إلغاء** returns to the orders
list.

### What Create Order does

1. No supplier → *"Please select a supplier."* and back to the form.
2. Every line index actually present in the submission is read (removing a middle
   row does not truncate the rest). A line is kept only when it has an item **and**
   a quantity greater than zero; everything else is dropped **without a warning**.
3. No usable line → *"Please add at least one line item."* and back to the form.
4. A PO number is generated as `PO-<current year>-<count of all POs + 1, 5 digits>`,
   e.g. `PO-2026-00042`.
5. The order is inserted with today as the order date, the chosen status, and
   `total` = the sum of the line totals. Each line is inserted into `po_lines`
   with quantity, unit cost and line total.
6. Green flash *"Purchase Order \<number\> created."* and you land on the order.

Nothing is reserved, ordered or emailed. Creating a PO does not touch stock.

> Source: `platform/blueprints/procurement/routes.py:194-295`,
> `platform/templates/procurement/order_form.html:1-197`

---

## C7. Purchase Order detail / receiving

**Route:** `GET /procurement/orders/<order_id>` — endpoint
`procurement.order_detail`. Unknown id → back to the orders list.

Header: `Purchase Order #<id>`, sub-heading `<PO number> · <supplier name>`.

### 📦 Order Lines / بنود الطلب

`#`, **Item / الصنف** (linked to the item; a line whose item row was deleted shows
**Deleted item / صنف محذوف** as plain text), **Unit / الوحدة**,
**Qty / الكمية**, **Unit Cost / تكلفة الوحدة**, **Total / الإجمالي** in EGP, and a
**Grand Total / الإجمالي الكلي** footer taken from the order header.

A **📝 Notes / 📝 ملاحظات** card appears below when the order has notes.

### 📋 Order Info / بيانات الطلب

**PO Number / رقم أمر الشراء**, **Status / الحالة** badge,
**Order Date / تاريخ الطلب**, **Expected / المتوقع** (when set),
**Received / مستلم** (when set), **Created By / أنشأه**.

### 🏭 Supplier / المورد

Name, contact name, phone, email, payment terms, and
**View Supplier → / عرض المورد ←**. Hidden when the supplier row is missing.

### Buttons

| Button | Shown when | Effect |
|---|---|---|
| **← Orders / ← الطلبات** | always | orders list |
| **✅ Mark Received / ✅ تعليم كمستلم** | status is `Draft` or `Sent` | browser confirm *"Mark this order as Received and update inventory?"*, then `POST /procurement/orders/<id>/receive` |
| **🔄 Update Status / 🔄 تحديث الحالة** card | status is not `Received` or `Cancelled` | dropdown of `Draft`, `Sent`, `Cancelled` + **Update / تحديث** → `POST /procurement/orders/<id>/status` |

### What Mark Received does

- If the order is **already `Received`**, nothing happens: amber flash
  *"Purchase Order #N was already received."* This guard is what stops a
  double-click doubling the stock.
- Otherwise, for **every** line with an item:
  - a `stock_movements` row, `movement_type = 'in'`, quantity and unit cost from
    the line, `reference_type = 'purchase_order'`, `reference_id` = the order id
  - a **new `batches` row** for that item, holding the full ordered quantity at
    the line's unit cost, in **warehouse 1**, with **no batch number, no lot
    number and no expiry date**
- the order's status becomes `Received` and `received_date` is set to today
- green flash *"Purchase Order #N marked as Received. Stock updated."*

Receiving is **all-or-nothing at the ordered quantity**. There is no screen to
record a short delivery, a batch number or an expiry date at receiving time. If
you need those, receive the delivery through **Receive Stock** (B5) instead and
leave the PO alone, or correct the batch afterwards — bearing in mind there is no
batch-edit screen either.

### What Update Status does

Accepts only `Draft`, `Sent`, `Received`, `Cancelled`; anything else →
*"Invalid status."* It changes `purchase_orders.status` and nothing else — it
writes no stock, no `received_date` and no audit entry. Flash
*"Status updated to X."*

> Source: `platform/blueprints/procurement/routes.py:298-373`,
> `platform/templates/procurement/order_detail.html:1-145`

---

# PART D — Reference

## D1. How stock actually changes

Every quantity change is a `stock_movements` row plus an edit to a `batches` row.
The writers, and what they record:

| Screen | `movement_type` | `reference_type` | `reference_id` | Batch effect |
|---|---|---|---|---|
| Receive Stock (B5) | `in` | `receiving` | *(none)* | creates a new batch |
| Purchase Order → Mark Received (C7) | `in` | `purchase_order` | the PO id | creates a new batch, warehouse 1, no expiry |
| Pharmacy dispense (A3) | `Dispensed` | `prescription` | the prescription id | deducts from the chosen or FEFO batch |
| Stock Transfer (B8) | `Transfer` | `transfer` | *(none)* | two rows: negative at source, positive at destination |

Only `visit`, `prescription` and `purchase_order` references are rendered as
clickable links, and only while the target row still exists.

The Point of Sale screen in the Pet Shop module also deducts stock; it is
documented in the Pet Shop chapter.

> Source: `platform/blueprints/inventory/routes.py:16-37` (the reference-type
> map and its own notes), `:446`, `:620-637`;
> `platform/blueprints/pharmacy/routes.py:226-233`;
> `platform/blueprints/procurement/routes.py:342-354`

## D2. FEFO in one paragraph

FEFO means *first expiry, first out*. When you dispense without picking a batch,
the system looks for the single batch of that item that is not expired and holds
at least the whole quantity you are dispensing, taking the nearest expiry first.
A batch with no expiry date sorts last and is never treated as expired.

## D3. Reorder level, max stock, suggested quantity

- **Reorder level** — an item is "low" when its total batch quantity is at or
  below this. Default 10.
- **Max stock** — the target the suggested order quantity aims for. Default 1000.
- **Suggested quantity** = `max_stock − current stock`, but never below the
  reorder level and never below 1. If `max_stock` is 0, twice the reorder level is
  used as the target.

> Source: `platform/blueprints/inventory/routes.py:75-85`

---

# Known limits

Everything below is current behaviour in the code as read, not a wish list.

### Pharmacy

1. **FEFO never splits across batches.** The automatic path needs one batch that
   holds the entire quantity on its own. An item with 5 units in each of two
   batches will fail with *"Insufficient stock"* for a request of 8, even though
   the Stock column on the same row says 10. Workaround: dispense in two passes
   picking batches explicitly, or pick a batch manually.
   `pharmacy/routes.py:210-217`
2. **The Stock column counts expired batches.** The figure shown next to each
   prescription item is the sum of *all* batches, so an item can read healthy
   green and still fail to dispense because every batch is expired.
   `pharmacy/routes.py:98`
3. **The batch dropdown offers expired batches.** They are listed and selectable;
   the rejection only happens after you press Dispense.
   `pharmacy/rx_detail.html:119-128`
4. **Dispense Qty is not capped by the prescribed quantity.** You can dispense
   more than was prescribed if the batch holds it. `pharmacy/routes.py:187`
5. **A partly-failed dispense leaves the prescription status stale.** When any
   item errors, the successful items are still committed and marked dispensed but
   the prescription's status is not recalculated — the queue can show
   `2/3 dispensed` with a status of `Active`. `pharmacy/routes.py:260-278`
6. **Free-text medications are recorded only in the audit log.** A prescription
   item with no linked stock item is marked dispensed and written to `audit_log`
   with action `dispensed_untracked_medication`. It never reaches
   `dispensing_log`, so it appears in **neither** Dispensing History **nor** the
   Narcotics Register, even if the drug is controlled. There is no screen in this
   module that shows those audit entries. `pharmacy/routes.py:160-185`
7. **The printed label always shows `Doctor: —` and `Visit: —`.** The label query
   does not join the visits table, so those two fields resolve to nothing on
   every label. `pharmacy/routes.py:354-360` vs `pharmacy/label.html:88-92`
8. **The label's Duration field never appears.** The template reads
   `item.duration_days`; the column is `prescription_items.duration`. The block is
   always skipped. `pharmacy/label.html:83-86` vs
   `models/database.py:1376-1390`
9. **The label's "Dispensed" date is today's date**, taken at print time, not the
   date the medicine was actually dispensed. `pharmacy/routes.py:373`
10. **The narcotics "Controlled Substances" KPI ignores the filters.** It counts
    every active controlled item in the catalogue, regardless of the date range or
    substance selected. `pharmacy/routes.py:332-334`
11. **Both pharmacy registers are hard-capped** — 200 rows for History, 500 for
    the Narcotics Register — with no paging and no warning when the cap is hit.
    Narrow the date range to be sure you are seeing everything.
    `pharmacy/routes.py:65,324`
12. **Dispensing History defaults to today only** and has no "to" date.
    `pharmacy/routes.py:50`
13. **No safety screening exists.** The panel on the prescription page says so
    itself; the drug reference it opens is marked DRAFT and unreviewed.
    `pharmacy/rx_detail.html:184-207`
14. **There is no way to reverse a dispense**, void a dispensing record, or return
    stock to a batch from the pharmacy module.
15. **`requires_rx` is never enforced.** The flag is stored and shown as a badge;
    no code path checks it before allowing a sale or a dispense.
16. **A non-numeric `qty_` value in a crafted POST raises an unhandled error.**
    The quantity is converted with a plain `float()`. The on-screen input is
    `type=number`, so this is not reachable through normal use.
    `pharmacy/routes.py:187`

### Inventory

17. **Low-stock detection is capped at the first 500 items by name.** The
    underlying query fetches 500 items ordered by name and *then* filters them for
    low stock, so an item alphabetically past the 500th can never raise a low-stock
    alert. This affects the dashboard counter, the dashboard cards and the Alerts
    page. `models/database.py:3534-3535` with `:3445-3463`
18. **The Movements type filter is applied after the row limit.** Filtering to
    `out` with the default limit of 100 shows only the `out` rows among the last
    100 movements of any type. `inventory/routes.py:508-513`
19. **The Movements type dropdown does not list the types the system writes.**
    It offers `in`, `out`, `adjustment`, `expired`, `damaged`, but dispensing
    writes `Dispensed` and transfers write `Transfer` — neither is selectable, and
    both are case-sensitive mismatches for the options offered.
    `inventory/movements.html:43-50` vs `pharmacy/routes.py:229`,
    `inventory/routes.py:624,634`
20. **Movements list every non-`in` type as a negative.** The quantity column
    prefixes `−` and colours red for anything that is not exactly `in`, including
    the positive half of a transfer. `inventory/movements.html:86-89`
21. **`adjustment` and `damaged` movements can be filtered for but never
    created.** No screen writes them.
22. **There is no stock-count / adjustment screen.** A miscount can only be
    corrected by receiving more stock; there is no way to reduce a batch outside
    of dispensing or transferring.
23. **There is no write-off or disposal action for expired stock.** Expired
    batches keep their quantity forever and keep inflating the inventory
    valuation. The only offered response on the Alerts page is to order a
    replacement. `inventory/alerts.html:140-147`
24. **The Expiring Soon table includes already-expired batches** — the query has
    no lower date bound. `models/database.py:3537-3544`
25. **The item page's "(Soon)" expiry tag is computed by string arithmetic** that
    appends 30 to the day-of-month, so near the end of a month it produces an
    invalid date and mislabels batches. The red `(EXPIRED)` tag is unaffected.
    `inventory/item_detail.html:215`
26. **There is no way to deactivate or delete an item.** `is_active` is set to 1
    at creation and never appears on the edit form; the items list only ever shows
    active items. An item created by mistake stays forever.
    `inventory/routes.py:340-362`
27. **The create-item form loses your input on error.** A duplicate SKU
    re-renders the form empty. The edit form does not have this problem.
    `inventory/routes.py:215-224`
28. **There is no batch edit or batch delete screen.** A batch received with the
    wrong expiry date or quantity cannot be corrected through the UI.
29. **`items.supplier_id` has no field on the item form.** The preferred supplier
    drives the Preferred badge and the supplier preselection on order links, but
    can only be set outside the UI. `inventory/routes.py:188-208`
30. **`item_categories` and `warehouses` have no management screens in this
    module.** Categories and warehouses can be selected but not created, renamed
    or deactivated here.
31. **Stock figures are computed three slightly different ways.** The items list
    and the item total count only batches with quantity > 0; the low-stock and
    supplier-page figures sum all batches including any negative ones. In a clean
    database these agree.
32. **Transfers do not copy lot number, manufacture date or notes** to a newly
    created destination batch. `inventory/routes.py:609-617`
33. **The transfer page carries styles for a "recent transfers" table that is
    never rendered.** There is no transfer history screen; transfers are only
    visible in the movements log. `inventory/transfer.html:42-46`
34. **Movements whose item row was deleted disappear from every movement list** —
    the query inner-joins `items`. `models/database.py:3546-3557`
35. **`reorder_rules` is a real table with no screen at all.** Reorder points,
    reorder quantities and preferred suppliers per item live only in
    `items.reorder_level` / `max_stock`. `models/database.py:1553-1561`

### Procurement

36. **Receiving a PO creates batches with no expiry date, no batch number and no
    lot number, always in warehouse 1.** Those batches are invisible to expiry
    alerts and sort last in FEFO. For anything with a shelf life, use
    **Receive Stock** (B5) instead. `procurement/routes.py:350-354`
37. **Receiving is all-or-nothing.** There is no partial-receipt screen. The
    `po_lines.received_qty` column exists in the database and is never written.
    `procurement/routes.py:339-354`, `models/database.py:1827-1837`
38. **A `Cancelled` order can still be received by a direct POST.** The guard
    only blocks orders already in `Received`. The button is hidden in the UI, so
    this is not reachable by clicking. `procurement/routes.py:331-334`
39. **Status can be moved back off `Received`, which re-enables the Mark Received
    button and lets the same delivery be booked into stock a second time.**
    `order_update_status` accepts any of the four statuses with no guard against
    the current one. `procurement/routes.py:361-373`
40. **A PO line with an unparseable quantity or price is silently dropped or
    zeroed.** The parse helper returns an error message that this route discards;
    a bad quantity becomes 0 and the line is then dropped without any warning, and
    a bad price becomes 0.00. `procurement/routes.py:262-269`
41. **`subtotal` and `tax_amount` on a purchase order are never written.** There
    is no VAT or tax handling on POs; only `total` is stored.
    `procurement/routes.py:280-285`
42. **Purchase orders cannot be edited or deleted after creation.** There is no
    edit route — only the status dropdown.
43. **The PO number is generated from a count of all purchase orders**, so
    deleting rows directly in the database, or two people creating an order at the
    same moment, can collide on a column that is UNIQUE.
    `procurement/routes.py:277-278`
44. **The line-item dropdown on the new-order form lists inactive items too**,
    unlike every other item picker in the system. `procurement/routes.py:206`
45. **The "Active Supplier" checkbox on the add-supplier form does nothing.** New
    suppliers are always created active. Use Edit Supplier to deactivate.
    `procurement/routes.py:74-84`
46. **The payment-terms lists differ between the add form and the edit form.**
    Add offers `Net 30 / Net 60 / COD / Prepaid`; edit offers
    `Net 30 / Net 15 / Net 60 / Due on Receipt / Prepaid`. Choosing `COD` then
    opening the edit form will silently show `Net 30` selected.
    `suppliers_list.html:103-109` vs `supplier_edit.html:37-39`
47. **`suppliers.name_ar` and `suppliers.tax_number` have no field on any form.**
    `models/database.py:1794-1806`
48. **Suppliers cannot be deleted.** Only deactivated.
49. **The dashboard's "Items Received This Month" counts orders, not items**, and
    it keys on the **order** date, not the received date — an order placed last
    month and received today is not counted. `procurement/routes.py:21-24`
50. **PO # is displayed as the internal database id** on the procurement
    dashboard and the orders list, while the supplier page and the order detail
    page show the real `po_number`. `dashboard.html:66`, `orders_list.html:70`

### Cross-cutting

51. **The sidebar shows Pharmacy, Inventory and Procurement to every signed-in
    user**, including roles that cannot open them. They find out by being bounced
    to the launcher. `base.html:130,197,211`
52. **Several launcher module cards list roles that do not hold the matching
    grant** and will therefore be bounced: the Inventory card lists `doctor`, the
    Procurement card lists `finance`, and the Pharmacy Dispensing card lists
    `inventory_mgr`. `launcher/routes.py:240,270,409` vs
    `models/database.py:4346-4379`
53. **The `url_key` values in the launcher module list are dead configuration** —
    the template links `mod.url` directly. `inventory.index` and
    `inventory.items_medications` are not real endpoints, but nothing tries to
    resolve them. `launcher.html:606-616`
54. **None of these modules is branch-aware in the UI.** `warehouses.branch_id`
    and `purchase_orders.branch_id` exist and default to 1; no screen sets or
    filters on them.

---

*This chapter documents the code as it stands in
`platform/blueprints/{pharmacy,inventory,procurement}/routes.py` and
`platform/templates/{pharmacy,inventory,procurement}/`. Every claim above was
read out of those files; the Source lines give the exact locations so the next
writer can check.*
