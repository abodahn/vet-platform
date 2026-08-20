# Pet Shop — Reference Manual

**Module:** Pet Shop & Orders / متجر الحيوانات والطلبات
**URL prefix:** `/petshop/`
**Blueprint:** `petshop`

This chapter is a **screen-by-screen reference**. It describes only what the
code in `blueprints/petshop/routes.py` and `templates/petshop/*.html` actually
does today. Anything that is present in the database but has no screen, or a
control that does not do what its label suggests, is listed under
[Known limits](#known-limits) rather than described as working.

> Source: `platform/app.py:235`, `platform/app.py:263` (blueprint registered at
> `/petshop`), `platform/blueprints/petshop/__init__.py:1-3`

---

## 1. Getting into the module

There are three doors into the Pet Shop:

| Door | Where | Goes to |
|---|---|---|
| Sidebar → BUSINESS / الأعمال → **Pet Shop / متجر الحيوانات** | every page | `/petshop/` (Dashboard) |
| Sidebar → BUSINESS / الأعمال → **Point of Sale / نقطة البيع** | every page | `/petshop/pos` |
| Launcher card **Pet Shop / متجر الحيوانات** (🛒) | `/` | `/petshop/` |

The two sidebar entries are shown to **every signed-in user**, with no role
condition on them. A user whose role does not hold the `petshop` grant will see
the links, click one, and be bounced to the launcher with
*"You don't have permission to access this page."* — see §2.

> Source: `platform/templates/base.html:201-209` (sidebar, no role guard on the
> BUSINESS group), `platform/templates/launcher.html:472-476`,
> `platform/blueprints/launcher/routes.py:491-505` (module card)

---

## 2. Who can open what

Two independent gates apply to every Pet Shop screen, and **both must pass**:

1. **The module grant.** The role must hold the `petshop` permission key. This
   is checked for every route in the blueprint, including the ones that carry
   no role list. `super_admin` bypasses it.
2. **The route's own role list**, where one is declared.

> Source: `platform/blueprints/auth/routes.py:60-69` (`login_required`),
> `:88-133` (`_permission_denied`, the module gate), `:167-194` (`role_required`),
> `platform/models/database.py:4346-4379` (`DEFAULT_ROLE_PERMISSIONS`)

Roles that hold `petshop` by default: **clinic_owner** (holds everything),
**branch_manager**, **reception**, **inventory_mgr** — plus **super_admin**,
which is exempt from both gates.

### Effective access, per screen

| Screen / action | Route | Role list on the route | Who can actually use it |
|---|---|---|---|
| Dashboard | `GET /petshop/` | none (login only) | super_admin, clinic_owner, branch_manager, reception, inventory_mgr |
| Products list | `GET /petshop/products` | none | same as above |
| New product | `GET/POST /petshop/products/new` | super_admin, clinic_owner, branch_manager, reception, support_admin | super_admin, clinic_owner, branch_manager, reception |
| Edit product | `GET/POST /petshop/products/<pid>/edit` | same as above | super_admin, clinic_owner, branch_manager, reception |
| Stock adjust | `POST /petshop/products/<pid>/stock` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Categories | `GET/POST /petshop/categories` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Orders list | `GET /petshop/orders` | none | super_admin, clinic_owner, branch_manager, reception, inventory_mgr |
| Point of Sale | `GET /petshop/pos` | none | same as above |
| Charge a sale | `POST /petshop/orders/create` | none | same as above |
| Order detail | `GET /petshop/orders/<oid>` | none | same as above |
| Cancel order | `POST /petshop/orders/<oid>/cancel` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Reports | `GET /petshop/reports` | super_admin, clinic_owner, branch_manager, support_admin | super_admin, clinic_owner, branch_manager |
| Product search API | `GET /petshop/api/products/search` | none | super_admin, clinic_owner, branch_manager, reception, inventory_mgr |
| Owner search API | `GET /petshop/api/owners/search` | none | same as above |

**`support_admin` is named on five route role lists but cannot reach any of
them.** Its default permission set is `["system","backup","audit","settings"]`,
which does not include `petshop`, so the module gate rejects it before the role
list is consulted. To make those role lists meaningful, an administrator must
add the `petshop` grant to the `support_admin` role on the Roles screen.

**Reception and inventory_mgr see buttons they cannot use.** The `+ In` / `- Out`
stock buttons on the Products screen, and the `+ Add Product` button in the
Dashboard and Products toolbars, are rendered unconditionally. Reception can use
Add Product but not the stock buttons; inventory_mgr can use neither, and gets
the permission flash and a redirect to the launcher.

> Source: `platform/blueprints/petshop/routes.py:187-189, 217-219, 247-249,
> 291-293, 332-334, 361-363, 402-404, 439-441, 457-459, 642-644, 666-668,
> 718-720, 815-817, 832-834`

---

## 3. Things that apply to every screen

- **Currency** is hard-coded as `EGP` / `جنيه` in every template. There is no
  currency setting in this module.
- **Bilingual labels** come from the `t(en, ar)` helper and switch on the
  signed-in user's language. Where a template hard-codes English, this manual
  says so — those strings stay English in Arabic mode.
- **CSRF.** Every POST carries `_csrf_token` as a hidden form field; the POS
  sends it as an `X-CSRF-Token` header. A POST without it renders a 403 page
  reading *"Invalid or missing security token. Please go back and try again."*
- **Tables are created on first use.** Opening most Pet Shop screens runs
  `ensure_petshop_tables()`, which creates `ps_categories`, `ps_products`,
  `ps_orders`, `ps_order_items`, `ps_stock_movements` if absent and adds the
  `ps_orders.invoice_id` and `ps_order_items.unit_cost` columns to older
  databases. Two routes do **not** call it: order cancel and the owner-search
  API.
- **Audit.** Product create/update, stock adjustment, order create and order
  cancel each write an audit row under module `petshop`. Category add/delete
  does **not**.

> Source: `platform/blueprints/petshop/routes.py:22-29` (`_log`), `:38-124`
> (`ensure_petshop_tables`), `platform/app.py:349-357` (CSRF),
> `platform/models/security.py:270-283` (token sources)

---

## 4. Screen: Dashboard

**Purpose.** The landing page of the module: four counters, the ten newest
orders, the ten lowest-stock products, and a quick-nav row.

**How to reach it.** Sidebar → Pet Shop; launcher card; or `← Dashboard /
← لوحة التحكم` from any other Pet Shop screen.

**Who can open it.** Any role holding the `petshop` grant (see §2).

### Toolbar buttons

| Button | Effect |
|---|---|
| `🛒 New Sale (POS)` / `🛒 عملية بيع جديدة (نقطة البيع)` | Opens the Point of Sale screen |
| `+ Add Product` / `+ إضافة منتج` | Opens the blank product form. Shown to everyone; denied for inventory_mgr |

### The four counters

| Card | What it counts |
|---|---|
| **Active Products / المنتجات النشطة** | Rows in `ps_products` with `is_active=1`. Stock level is irrelevant |
| **Sales Today / مبيعات اليوم** | Orders whose `date(created_at)` equals today's **UTC** date and whose status is not `cancelled` or `refunded` |
| **Revenue Today / إيرادات اليوم** | `SUM(total)` over the same set, printed with no decimals |
| **Low Stock Items / أصناف منخفضة المخزون** | Active products where `stock_qty <= reorder_level`. The card turns red when this is above zero |

Note both "today" figures use the **UTC** calendar day, not the clinic's local
day.

### Recent Orders / الطلبات الأخيرة

Ten most recent orders by `created_at`, **regardless of status** — a cancelled
order appears here even though it is excluded from the counters above.

| Column | Content |
|---|---|
| Order # / طلب رقم | `order_number`, links to the order detail screen |
| Customer / العميل | Owner's full name linking to their CRM record, or the plain text `Walk-in / عميل عابر` when the order has no `owner_id` |
| Total / الإجمالي | `total`, two decimals, + EGP |
| Status / الحالة | The raw status word, in a coloured pill |

`View all → / عرض الكل ←` opens the Orders list.

### Low Stock Alerts / تنبيهات نقص المخزون

Up to ten active products where `stock_qty <= reorder_level`, lowest stock
first. Columns: **Product / المنتج**, **Stock / المخزون** (quantity + unit, in a
red pill), **Reorder At / إعادة الطلب عند** (`≤ reorder_level`). When the list is
empty the panel reads `✅ All stock levels healthy / ✅ جميع مستويات المخزون جيدة`.
`All products → / كل المنتجات ←` opens the Products list.

### Quick nav

Five tiles — Point of Sale, Products, Orders, Categories, Reports — linking to
the corresponding screens. **These five labels are English-only.** Categories
and Reports are denied to reception and inventory_mgr.

> Source: `platform/blueprints/petshop/routes.py:187-212`;
> `platform/templates/petshop/dashboard.html:1-135`

---

## 5. Screen: Products

**Purpose.** Browse and filter the product catalogue as cards, adjust stock, and
jump to the edit form.

**How to reach it.** Dashboard → Products tile, or `All products →` in the
low-stock panel; `📦 Products / 📦 المنتجات` from the Categories screen;
`← Products` from the product form.

**Who can open it.** Any role holding the `petshop` grant. The stock buttons on
each card are restricted further (see below).

Only products with `is_active=1` are ever listed. There is no way to see or
restore a deactivated product from any screen in this module.

### Toolbar buttons

| Button | Effect |
|---|---|
| `+ Add Product` / `+ إضافة منتج` | Opens the blank product form |
| `🏷️ Categories` (English-only) | Opens the Categories screen |
| `← Dashboard` / `← لوحة التحكم` | Back to the module dashboard |

### Filter bar

All three filters are combined with AND and submitted by **GET**, so the
resulting URL can be bookmarked.

| Control | Field | What it does |
|---|---|---|
| Search box (`q`) | free text, English-only placeholder *"Search by name, SKU, barcode…"* | Substring match (`LIKE %q%`) against **name**, **SKU** or **barcode** |
| Category dropdown (`cat`) | `All Categories / جميع الفئات` plus every active category | Exact match on `category_id` |
| Species dropdown (`species`) | `All Species` (English-only) plus dog, cat, bird, rabbit, fish, exotic, all | Matches products whose species equals the choice **or** is `all` |
| `Search / بحث` | — | Applies the filters |
| `Clear / مسح` | — | Only rendered when at least one filter is set; returns to the unfiltered list |

Results are ordered by product name. There is **no pagination and no result
cap** — every matching active product is rendered.

Above the grid: *"N product(s) found"* (English-only). With no matches, an empty
state offers `Add First Product`.

### What each product card shows

| Element | Source |
|---|---|
| Species badge | `species`, or `all` when blank |
| Product name | `name` (the English name only; `name_ar` is never displayed) |
| `SKU: …` | `sku`, shown only when set |
| Brand line | `brand`, shown only when set |
| Price | `sell_price`, two decimals + EGP |
| `Cost: … | Margin: …%` | `cost_price`, and `(sell − cost) / sell × 100` rounded to a whole number. Margin shows `0%` when the sell price is 0 |
| Footer stock chip | `stock_qty` + `unit`, green with `✓`, or red with `⚠️` when `stock_qty <= reorder_level` |
| `Edit / تعديل` | Opens the edit form for that product |

### Quick stock adjust (per card)

A small form on every card:

- **Quantity box** — `name=qty`, numeric, `min="1"`, pre-filled with `1`.
  Required in practice: the server rejects a blank or non-numeric value and any
  quantity of zero or less with *"Enter a quantity greater than zero."* and
  returns you to the unfiltered Products list.
- **`+ In`** — submits `movement=in`. Adds the quantity to `stock_qty` and writes
  a stock movement of type `in`, ref_type `manual_adjustment`.
- **`- Out`** — submits `movement=out`. Subtracts the quantity, floored at zero
  (`MAX(0, stock_qty − qty)`), and writes a movement of type `out`.

Either button flashes *"Stock updated."* and redirects to `/petshop/products`
**with the filters dropped**. The route also reads a `notes` field for the
movement record, but no screen supplies one, so it is always stored empty.

> Source: `platform/blueprints/petshop/routes.py:217-244` (list), `:332-356`
> (stock adjust); `platform/templates/petshop/products.html:1-105`

---

## 6. Screen: New / Edit Product

**Purpose.** Create a product, or change an existing one.

**How to reach it.** `+ Add Product` from the Dashboard or Products toolbar
(new); `Edit / تعديل` on a product card (edit).

**Who can open it.** super_admin, clinic_owner, branch_manager, reception.
(`support_admin` is on the route's list but blocked by the module gate.)

The page title and the save button change with the mode: *New Product* /
`➕ Create Product` versus *Edit Product* / `💾 Save Changes`. Opening the edit
form for an id that does not exist flashes *"Product not found."* and returns to
the Products list.

### Fields

Section **📦 Basic Information** (heading English-only):

| Label | Field | Required | Notes |
|---|---|---|---|
| `Product Name (EN) *` | `name` | Yes (browser-enforced `required`) | Stored as `name`. This is the only name any Pet Shop screen displays |
| `Product Name (AR)` | `name_ar` | No | RTL input. Stored, but never displayed on any screen in this module |
| `SKU / Code` | `sku` | No | Must be **unique across all products**. Blank is stored as NULL, so many products may have no SKU |
| `Barcode` | `barcode` | No | Placeholder is bilingual (`Optional / اختياري`). Searchable on the Products screen and by the search API, but not shown anywhere |
| `Brand` | `brand` | No | Shown on the product card |
| `Category / الفئة` | `category_id` | No | Dropdown of active categories, with `— No Category —` as the default |
| `Description / الوصف` | `description` | No | Stored, never displayed |

Section **🐾 Species & Unit**:

| Label | Field | Required | Notes |
|---|---|---|---|
| `Species Applicability` (English-only) | `species` | No | Fixed list: all, dog, cat, bird, rabbit, fish, exotic. Defaults to `all` |
| `Unit / الوحدة` | `unit` | No | Fixed list: unit, bag, bottle, box, pack, kg, gram, litre, ml, piece, pair, set. Defaults to `unit`. Display only — it does not change how quantities are counted |

Section **💰 Pricing**:

| Label | Field | Required | Notes |
|---|---|---|---|
| `Cost Price (EGP)` | `cost_price` | No, defaults to 0 | Used for the margin on the card and for the cost/profit figures in Reports |
| `Sell Price (EGP) *` | `sell_price` | Yes (browser-enforced) | The price the POS charges |
| `Tax Rate (%) / نسبة الضريبة (%)` | `tax_rate` | No, defaults to 0 | Per-product percentage, applied per line at the till. Hint: `0 = tax-free` |

Section **📊 Stock**:

| Label | Field | Shown | Notes |
|---|---|---|---|
| `Opening Stock Qty` | `stock_qty` | **New product only** | Defaults to 0. When greater than 0, an `in` stock movement with ref_type `opening_stock` is written alongside the product |
| `Reorder Level (alert when ≤)` | `reorder_level` | Always | Defaults to 5. Drives the low-stock chip, the dashboard counter and the low-stock lists |

### Buttons

| Button | Effect |
|---|---|
| `➕ Create Product` / `💾 Save Changes` | Saves and returns to the Products list with *"Product 'X' created."* / *"Product updated."* |
| `Cancel / إلغاء` | Returns to the Products list without saving |
| `← Products` (toolbar, English-only) | Same as Cancel |

**Editing never changes stock.** The update statement writes category, both
names, SKU, barcode, brand, species, description, cost, sell price, tax rate,
reorder level and unit. `stock_qty` is deliberately not in the list — use the
`+ In` / `- Out` buttons on the Products screen.

**Error handling is raw.** A duplicate SKU, or a non-numeric price typed past
the browser's validation, is caught and flashed as `Error: <the database or
Python message>` — for example *"Error: UNIQUE constraint failed:
ps_products.sku"*. On the new-product form the entries you typed are lost; on
the edit form the page re-renders with the stored values, not your edits.

> Source: `platform/blueprints/petshop/routes.py:247-288` (new), `:291-329`
> (edit); `platform/templates/petshop/product_form.html:1-165`

---

## 7. Screen: Categories

**Purpose.** Add and delete product categories. There is no edit.

**How to reach it.** Dashboard → Categories tile, or `🏷️ Categories` in the
Products toolbar.

**Who can open it.** super_admin, clinic_owner, branch_manager. Reception and
inventory_mgr are shown the Categories tile on the dashboard but are denied.

### Left panel — All Categories / جميع الفئات

Every category in `ps_categories`, ordered by name, **including inactive ones**
(the query does not filter on `is_active`).

| Column | Content |
|---|---|
| `Name / الاسم` | `name` |
| `Description / الوصف` | `description`, or `—` |
| `Products / المنتجات` | Count of **active** products in that category, in a pill |
| (unlabelled) | Delete button |

`Delete / حذف` asks *"Delete category 'X'?"* in a browser confirm. The button is
rendered **disabled** when the category has at least one active product, and the
server refuses the same case with *"Cannot delete: category has products."*.
Deletion is permanent — the row is removed, not deactivated.

### Right panel — Add Category / إضافة فئة

| Label | Field | Required | Notes |
|---|---|---|---|
| `Category Name * / اسم الفئة *` | `name` | Yes | The browser marks it required; the server also silently ignores a submission whose name is blank or whitespace-only — no error is shown, the page just reloads unchanged |
| `Name (AR) / الاسم (عربي)` | `name_ar` | No | RTL input. Stored, but never displayed anywhere |
| `Description / الوصف` | `description` | No | Shown in the list |

`➕ Add Category / ➕ إضافة فئة` saves and flashes *"Category 'X' created."*.

A `💡 TIPS / 💡 نصائح` box appears under the form once at least one category
exists, restating the three rules above.

> Source: `platform/blueprints/petshop/routes.py:361-397`;
> `platform/templates/petshop/categories.html:1-116`

---

## 8. Screen: Point of Sale

**Purpose.** Ring up a counter sale: pick products, set a discount, choose a
payment method, optionally attach a customer, and charge.

**How to reach it.** Sidebar → Point of Sale; Dashboard → `🛒 New Sale (POS)` or
the Point of Sale tile; `🛒 New Sale / 🛒 عملية بيع جديدة` from the Orders list or
an order detail.

**Who can open it.** Any role holding the `petshop` grant — including
inventory_mgr and reception. There is **no separate cashier permission**: anyone
who can open this screen can charge a sale.

The page loads **only products that are active and have `stock_qty > 0`**. A
product that has run out disappears from the grid entirely until stock is
adjusted and the page is reloaded.

### Left half — product picker

| Control | What it does |
|---|---|
| Search box (English-only placeholder *"🔍 Search product by name, SKU, or barcode…"*) | Filters the tiles **already on the page**, in the browser, by **product name only**. SKU and barcode are not matched despite the placeholder. No request is sent |
| Category tabs — `All / الكل` plus one per active category | Filters the tiles by category, in the browser. Combined with the search box using AND |
| Product tile | Click adds one unit to the cart |

Each tile shows an emoji chosen from the product name (🥩 for a name containing
"food", 🧴 "shampoo", 🦮 "collar", 🧸 "toy", 💊 "supplement"/"vitamin", 📦
otherwise), the product name, the sell price, and `Stock: N unit`.

Clicking a tile whose quantity in the cart already equals its stock does
nothing — no message is shown.

### Right half — cart

`🛒 Cart` (English-only) with a `Clear / مسح` link that empties it.

Per line: product name, `−` / quantity / `+` buttons, the line amount
(`price × qty`, no discount or tax), and `×` to remove the line. `+` will not
push the quantity past the stock figure loaded with the page; `−` below 1
removes the line.

Empty cart state: *"Tap a product to add it"* (English-only).

### Totals block

| Row | Meaning |
|---|---|
| `Subtotal / المجموع الفرعي` | Σ price × qty, before discount and tax |
| `Discount / الخصم` | **Editable box** — a whole-order discount in EGP. `min=0`, `step=0.5`, starts at 0 |
| `Tax / الضريبة` | Σ price × qty × the product's own tax rate. Not editable |
| `TOTAL / الإجمالي` | Subtotal − discount + tax, floored at 0 on screen |

### Payment block

| Control | What it does |
|---|---|
| Customer box (English-only placeholder *"👤 Search customer (optional)…"*) | Waits 300 ms after you stop typing, then queries the owner API and shows a dropdown of `name — phone`. Any non-empty text triggers a search. Click a result to attach it; the dropdown closes when you click elsewhere. Leaving it blank makes the sale a walk-in |
| Payment method — `Cash`, `Card`, `Transfer`, `Instapay` (English-only, Cash pre-selected) | Sets the method stored on the order and the payment |
| `Amount tendered (EGP)` (English-only placeholder) | Cash tendered. `min=0`, `step=0.5` |
| Change line | Under the tendered box: `Change: N EGP` in green, or `⚠️ Underpaid by N EGP` in red. **Only shown when the method is Cash and a tendered amount has been typed** |
| `✅ Charge — <total> EGP` | Submits the sale. Disabled while the cart is empty |

**Cash is the only method that uses the tendered box.** For Card, Transfer and
Instapay the server overwrites the paid amount with the order total, so change
is always 0 and the invoice is recorded as fully paid.

For Cash, the browser refuses to submit when the tendered amount is below the
total: *"Amount tendered is less than total. Please enter the correct amount."*

### What Charge actually does

In one database transaction:

1. Writes a row in `ps_orders` with status **`paid`** (there is no draft step),
   source `in-clinic`, `served_by` = your username, and an order number of the
   form `PS-YYYYMM-NNNN`.
2. Writes one `ps_order_items` row per line, stamping the product's **current
   cost price** onto the line so later cost changes cannot rewrite past profit.
3. Deducts stock with a conditional update — if another till sold the last unit
   in the meantime the whole sale is rolled back and you get a 409 with
   *"<product> is out of stock — another till may have just sold the last one.
   Refresh and try again."*
4. Writes an `out` stock movement per line, ref_type `sale`.

Then, outside that transaction, the **finance bridge**: it creates an invoice
for the owner (or for the shared auto-created owner record **"Walk-in
Customer"** when no customer was attached), carries the order-level discount to
the invoice as a value discount, records a payment for the paid amount capped at
the total, and links the invoice id back to the order. If any of this fails the
sale still stands — the failure is logged as a warning and the order simply
shows *"Not invoiced"*.

Server-side arithmetic, which is what gets stored:

- Subtotal = Σ `qty × unit_price × (1 − line discount %/100)`, rounded to 2 dp.
- Tax = Σ the same line net × `tax_rate/100`, rounded to 2 dp.
- The order discount is clamped to `0 … subtotal`, so a mistyped discount can
  never produce a negative total.
- Total = subtotal − discount + tax.
- Change = `max(0, paid − total)`.

Quantities are validated: any line with a quantity of zero or less is refused
with *"Every line needs a quantity greater than zero."* and nothing is written.

### Receipt modal

On success a modal appears: `✅ Sale Complete!` with the order number, total and
change.

| Button | Effect |
|---|---|
| `🖨️ Print Receipt / 🖨️ طباعة الإيصال` | Opens `/petshop/orders/<id>` — the order detail screen — in a new tab. It is not a printable receipt |
| `+ New Sale` (English-only) | Closes the modal, empties the cart, resets discount, tendered amount and customer |

There is no other way to dismiss the modal — no close button, no click-outside.

### Errors you can see at the till

| Situation | Message |
|---|---|
| Empty cart | The Charge button is disabled |
| A line with quantity ≤ 0 | `Error: Every line needs a quantity greater than zero.` |
| No items reached the server | `Error: No items` |
| Stock gone since the page loaded | `Error: <product> is out of stock — another till may have just sold the last one. Refresh and try again.` |
| Anything else | `Error: The sale could not be completed. Nothing was charged.` |
| Connection dropped | `Network error: …` |

> Source: `platform/blueprints/petshop/routes.py:439-454` (screen), `:457-639`
> (charge), `:127-132` (order number), `:138-160` (walk-in owner);
> `platform/templates/petshop/pos.html:1-387`

---

## 9. Screen: Orders

**Purpose.** Search the sales history.

**How to reach it.** Dashboard → Orders tile or `View all →` on Recent Orders;
`🧾 Orders / 🧾 الطلبات` from the POS or Reports toolbars.

**Who can open it.** Any role holding the `petshop` grant.

### Toolbar

`🛒 New Sale / 🛒 عملية بيع جديدة` → POS. `← Dashboard / ← لوحة التحكم` → module
dashboard.

### Filters (GET, combined with AND)

| Control | Field | What it does |
|---|---|---|
| Search box (English-only placeholder *"Search order #, customer name…"*) | `q` | Substring match against `order_number` **or** the owner's full name |
| Status dropdown | `status` | `All Statuses / جميع الحالات`, or one of **paid**, **draft**, **cancelled**. Exact match |
| From date | `date_from` | `date(created_at) >= ` this date, inclusive |
| To date | `date_to` | `date(created_at) <= ` this date, inclusive |
| `Search / بحث` | — | Applies the filters |
| `Clear / مسح` | — | Rendered only when a filter is set; returns to the unfiltered list |

Sorted newest first and **capped at 200 rows**. There is no pagination: when
more than 200 orders match, the oldest of them are silently not shown. The
count line above the table (*"N order(s) found"*, English-only) reports the
number of rows displayed, not the number that matched.

### Columns

| Column | Content |
|---|---|
| `Order # / طلب رقم` | `order_number`, monospace, links to the order detail |
| `Date / التاريخ` | First 16 characters of `created_at` (date and time to the minute) |
| `Customer / العميل` | Owner name linking to the CRM record, or `Walk-in / عميل عابر` |
| `Items / الأصناف` | Number of `ps_order_items` rows on the order, or `—` |
| `Payment / الدفع` | `payment_method`, capitalised, in a pill; falls back to `Cash` when empty |
| `Total / الإجمالي` | `total`, two decimals + EGP |
| `Status / الحالة` | The raw status word in a coloured pill — green for `paid`, amber for `draft`, red for `cancelled` |
| (unlabelled) | `View → / عرض ←` link to the order detail |

Empty state: `No orders found`, with either *"Try adjusting your filters"* or a
`Create First Sale` button.

> Source: `platform/blueprints/petshop/routes.py:402-436`;
> `platform/templates/petshop/orders.html:1-107`

---

## 10. Screen: Order detail

**Purpose.** Read one order in full and, if you have the role for it, cancel it.

**How to reach it.** Any order number or `View →` link in the Dashboard, the
Orders list, or the POS receipt modal. Direct URL `/petshop/orders/<oid>`. An id
that does not exist flashes *"Order not found."* and returns to the Orders list.

**Who can open it.** Any role holding the `petshop` grant. The Cancel button is
restricted to super_admin, clinic_owner and branch_manager.

The sub-heading shows the order date and time and the capitalised status.

### Order Items / بنود الطلب

| Column | Content |
|---|---|
| `Product / المنتج` | `product_name` **as it was at the time of sale** — renaming the product later does not change it |
| `Qty / الكمية` | `qty` |
| `Unit Price / سعر الوحدة` | `unit_price` + EGP |
| `Line Total / إجمالي البند` | `line_total` — quantity × price after the line's own discount, **before** tax |

Per-line discount and per-line tax rate are stored but not shown in this table.

### Totals / الإجماليات

- `Subtotal / المجموع الفرعي` — always shown.
- `Discount / الخصم` — shown in red with a leading `−`, only when greater than 0.
- `Tax / الضريبة` — only when greater than 0.
- `Grand Total` (English-only) — the stored `total`.
- `Cash Tendered` and `Change` (English-only) — shown together **only when the
  method is Cash and the tendered amount exceeds the total**. An exact-cash sale
  therefore shows neither line.

### Details

| Row | Content |
|---|---|
| `Status / الحالة` | Coloured pill |
| `Customer / العميل` | Owner link, or `Walk-in / عميل عابر` |
| `Pet / الحيوان` | Link to the pet — only rendered when the order carries a pet id |
| `Invoice / الفاتورة` | `🧾 #<id>` linking to the finance invoice, or `Not invoiced / بدون فاتورة` |
| `Payment / الدفع` | `payment_method`, capitalised |
| `Date / التاريخ` | `created_at` to the minute |
| `Notes / ملاحظات` | Only rendered when the order has notes |

`served_by`, `source` and `payment_ref` are stored on the order but shown on no
screen.

### Actions

| Button | Effect |
|---|---|
| `🖨️ Print Receipt / 🖨️ طباعة الإيصال` | Opens this same page with `?print=1` in a new tab. The route ignores the parameter — the page renders identically |
| `❌ Cancel Order` (English-only) | Only rendered when the status is `paid`. Confirms with *"Cancel this order and restore stock?"* |

When the status is `cancelled`, the actions panel shows the static text
*"Order has been cancelled"* instead of the button.

**What Cancel does**, in one transaction: sets the order status to `cancelled`;
if the order is linked to an invoice, sets that invoice to `Cancelled` and
writes a **negative reversing payment row** for each positive payment against it
(referenced *"Reversal of pet shop order N"*), so the cash ledger and the invoice
agree; then adds each line's quantity back to `ps_products.stock_qty` and writes
an `in` stock movement with ref_type `cancellation`. Flash: *"Order cancelled and
stock restored."* and you stay on the order.

Cancelling is safe to repeat: an order already `cancelled` or `refunded` is
skipped, so stock is only restored once. It cannot be undone from any screen.

> Source: `platform/blueprints/petshop/routes.py:642-663` (detail), `:666-713`
> (cancel); `platform/templates/petshop/order_detail.html:1-180`

---

## 11. Screen: Reports

**Purpose.** Revenue, cost, profit, best sellers, daily breakdown, payment mix
and low stock for a chosen date range.

**How to reach it.** Dashboard → Reports tile, or `/petshop/reports`.

**Who can open it.** super_admin, clinic_owner, branch_manager only. Reception
and inventory_mgr see the Reports tile on the dashboard but are denied.

### Period filter

| Control | Behaviour |
|---|---|
| `date_from` date box | Defaults to the **1st of the current UTC month** |
| `date_to` date box | Defaults to **today, UTC** |
| `Apply / تطبيق` | Reloads with the chosen range |
| `Reset / إعادة تعيين` | Returns to the defaults |

Both bounds are inclusive. Clearing a box is treated as "no bound given" and
falls back to that box's default rather than erroring.

Every figure on this page excludes orders whose status is `cancelled` or
`refunded`; every other status — `paid`, and any other spelling present in the
data — is counted.

### KPI cards (all English-only labels)

| Card | Definition |
|---|---|
| `Total Orders` | Number of counted orders in the range |
| `Revenue (EGP)` | `SUM(total)` — already net of discount, inclusive of tax |
| `Cost (EGP)` | `SUM(qty × unit_cost)` per line, falling back to the product's **current** cost price for lines written before per-line cost was recorded |
| `Gross Profit (EGP)` | Revenue − Cost |
| `Margin %` | Gross Profit ÷ Revenue × 100; the card turns red below 20% |
| `Avg Order (EGP)` | Revenue ÷ Total Orders |

### 🏆 Top Products by Revenue

Top 10 by revenue, grouped by product. Columns: rank badge (top three
highlighted), `Product / المنتج` with a bar scaled against the number-one row,
`Qty Sold` (English-only) = `SUM(qty)`, and `Revenue / الإيرادات` =
`SUM(line_total)` with no decimals. Note this revenue column is the **pre-tax**
line total, so it will not add up to the Revenue KPI when any product carries a
tax rate. Empty state: *"No sales data in this period"*.

### ⚠️ Low Stock Alerts / تنبيهات نقص المخزون

Every active product where `stock_qty <= reorder_level`, lowest first —
**unfiltered by date**, so this panel ignores the period at the top of the page.
Columns as on the dashboard.

### 📅 Daily Sales Breakdown

One row per calendar day that had at least one counted order, newest first.
Columns: `Date / التاريخ`, `Orders / الطلبات` (count), `Revenue / الإيرادات`
(`SUM(total)`, no decimals), `Avg Order` (revenue ÷ count), and a bar scaled
against the busiest day in the range.

### 💳 Payment Method Breakdown

One tile per payment method actually used, ordered by revenue. Methods are
lower-cased before grouping, so `Cash` and `cash` merge. Each tile shows an icon
(💵 cash, 💳 card, 📱 instapay, 🔄 anything else), the method name, the revenue,
and the order count. The whole panel is hidden when there is nothing to show.

> Source: `platform/blueprints/petshop/routes.py:718-810`;
> `platform/templates/petshop/reports.html:1-208`

---

## 12. Background endpoints

These are JSON endpoints, not screens. Both require sign-in and the `petshop`
grant.

| Endpoint | Query | Returns |
|---|---|---|
| `GET /petshop/api/owners/search?q=` | Substring match on owner full name **or** phone | Up to 10 objects: `id`, `full_name`, `phone`. Used by the POS customer box |
| `GET /petshop/api/products/search?q=` | Substring on name, SKU or barcode; active products with stock only | Up to 20 objects: `id`, `name`, `sku`, `sell_price`, `stock_qty`, `tax_rate`, `unit` |

The product search endpoint is **not called by any screen** — the POS filters its
already-loaded tiles in the browser instead.

The owner search returns every owner, including the auto-created *"Walk-in
Customer"* record used to bill counter sales, so that name can be selected as if
it were a real customer.

> Source: `platform/blueprints/petshop/routes.py:815-827`, `:832-842`;
> `platform/templates/petshop/pos.html:300-332`

---

## 13. Where a Pet Shop sale shows up elsewhere

| Where | What appears |
|---|---|
| Finance → the invoice | One invoice per sale, notes *"Pet Shop Order PS-…"*, one line per product, plus the order-level discount as a value discount. Linked back from the order detail |
| Finance → payments | One payment row per sale, reference = the payment reference or the order number. Cancelling the order adds a matching negative row rather than deleting it |
| CRM → owner record | The invoice, via finance |
| CRM → pet timeline | A `🛍️ purchase` event for orders that carry a pet id. **The POS never sets one**, so POS sales do not appear on any pet timeline |

> Source: `platform/blueprints/petshop/routes.py:568-618`, `:692-702`;
> `platform/blueprints/crm/routes.py:135-137, 161-162`

---

## Known limits

Things in this module that do not work, are unfinished, or do not match their
own labels. Each is stated with where to verify it.

### Not implemented at all

1. **There is no receipt printout.** Both `🖨️ Print Receipt` buttons — the one in
   the POS modal and the one on the order detail — open the ordinary order
   detail page in a new tab. The order detail's version appends `?print=1`, which
   the route reads nowhere and no template branches on, and there is no print
   stylesheet. (`routes.py:642-663`, `order_detail.html:158-162`, `pos.html:178`)
2. **There is no refund.** The status `refunded` is excluded from every report
   aggregate but nothing in the module can set it. The only reversal available is
   Cancel, which is all-or-nothing and only offered on a `paid` order.
   (`routes.py:666-713`)
3. **There is no stock-movement history screen.** Every sale, cancellation,
   opening stock and manual adjustment writes a `ps_stock_movements` row, and no
   page in the platform displays that table. The only way to read it is directly
   against the database. (verified: `ps_stock_movements` appears in no template)
4. **Orders cannot be edited.** No screen adds, removes or re-prices a line after
   the sale; there is no partial return.
5. **Products cannot be deactivated or deleted.** Every list filters on
   `is_active=1`, and no route ever writes `is_active=0`. A discontinued product
   stays in the catalogue and in the POS grid for ever.
   (`routes.py:291-320` — `is_active` is absent from the UPDATE)
6. **Categories cannot be edited.** Only add and delete. A typo in a category
   name can only be fixed by deleting the category — which is blocked while it
   has products — and re-creating it. (`routes.py:361-397`)
7. **`image_url` exists on the product table and no screen sets or shows it.**
   The POS picks an emoji by matching English words in the product name instead.
   (`routes.py:67`, `pos.html:101-108`)
8. **The draft status is unreachable.** Orders are written directly as `paid`;
   the Orders filter offers a `Draft` option that can never match anything the
   POS creates. (`routes.py:521`, `orders.html:38`)

### Labels that do not match behaviour

9. **The POS search box does not search SKU or barcode.** Its placeholder says
   *"Search product by name, SKU, or barcode…"*, but the filter compares only
   `data-name`. The endpoint that does search all three
   (`/petshop/api/products/search`) is never called by any page.
   (`pos.html:85`, `:201-211`, `routes.py:815-827`)
10. **The launcher card advertises FEFO.** Its description reads *"Products ·
    Stock management · Point-of-sale · Orders · Revenue reports · FEFO"*. There is
    no batch, lot, expiry date or FEFO logic anywhere in the module — stock is a
    single integer per product. (`launcher/routes.py:496`)
11. **The launcher card lists roles that cannot use the module.** It offers the
    Pet Shop card to `finance`, `support_admin` and `staff`, none of which hold
    the `petshop` grant by default; they reach the module gate and are redirected.
    (`launcher/routes.py:500` versus `database.py:4346-4379`)
12. **A per-line discount column is stored but has no interface.** The order
    creation code fully supports a per-line discount percentage; the POS always
    sends `discount: 0` for every line, and the order detail never shows the
    column. Only the whole-order discount box is reachable.
    (`pos.html:360`, `order_detail.html:39-61`)
13. **The SKU line on the order detail can never render.** The template prints
    `it.sku` for each item, but the query is `SELECT * FROM ps_order_items`, which
    has no `sku` column. (`routes.py:658`, `order_detail.html:53`)

### Permissions

14. **`support_admin` is named on five route role lists but is blocked by the
    module gate**, because its default grant set has no `petshop` key. Until an
    administrator grants it, those role lists have no effect.
    (`routes.py:248, 292, 333, 362, 667, 719` versus `database.py:4376`)
15. **`inventory_mgr` holds the `petshop` grant but is denied every write.** It
    can open the dashboard, products, orders, order details and the POS — and
    charge sales — but not add or edit a product, adjust stock, manage
    categories, cancel an order or view reports.
16. **The sidebar shows Pet Shop and Point of Sale to every signed-in user**,
    with no role condition. Doctors, nurses, pharmacists, finance, HR, groomers,
    boarding staff and auditors all see the links and are bounced to the launcher
    when they click. (`base.html:200-209`)
17. **Buttons are rendered without checking the role behind them.** `+ Add
    Product` on the dashboard and products toolbars, the `+ In` / `- Out` stock
    buttons on every product card, and the Categories and Reports quick-nav tiles
    are all shown to users who will be refused.

### Money and counting

18. **Cash underpayment is only blocked in the browser.** The server accepts any
    tendered amount for a cash sale, marks the order `paid`, and records a
    payment of the smaller of tendered and total — leaving a partly paid invoice
    behind an order that reads as paid. (`routes.py:509-511`, `:604-612`)
19. **The order discount is clamped against the subtotal, not the total.** A
    discount equal to the subtotal on a taxed sale leaves the tax still payable.
    (`routes.py:499-501`)
20. **Both "today" figures on the dashboard use the UTC calendar day**, not the
    clinic's local day, so late-evening sales in Egypt land on the next day's
    counters. The reports screen defaults to a UTC month and a UTC "today" for
    the same reason. (`routes.py:192`, `:728-729`)
21. **Order numbers are derived from `MAX(id)`, not from a per-month counter.**
    `PS-YYYYMM-NNNN` carries the current month but the sequence never resets, so
    the number does not restart at 0001 each month. If the highest-id order were
    ever removed from the database, the next sale would attempt a duplicate
    number and fail the UNIQUE constraint. (`routes.py:127-132`)
22. **Reports "Top Products" revenue is pre-tax while the Revenue KPI is
    post-tax.** The two columns will not reconcile on any product with a non-zero
    tax rate. (`routes.py:733-736` versus `:766-776`)
23. **Money is stored as floating point.** The module rounds each written value
    to two decimals, which is only safe while tax rates are zero; the project's
    own note flags that the fix is a numeric column type end to end. See
    `docs/MONEY_PRECISION.md`. (`routes.py:487-501`)

### Lists and filters

24. **The Orders list is capped at 200 rows with no pagination and no warning.**
    Beyond that, older matching orders are simply absent and the "N order(s)
    found" line reports only what is displayed. (`routes.py:429`)
25. **The Products list has no cap and no pagination** — a large catalogue is
    rendered as one page of cards. (`routes.py:236-237`)
26. **The Orders status filter offers only paid, draft and cancelled.** Orders
    carrying any other status word — older data uses `completed` — cannot be
    filtered for, and their status pill renders unstyled because no matching CSS
    class exists. (`orders.html:26-28, 38`)
27. **The Categories list does not filter on `is_active`**, so a deactivated
    category would still be listed, while the product form and the POS category
    tabs only offer active ones. (`routes.py:390-393` versus `:283`, `:449`)
28. **Adjusting stock throws away your filters** — it always redirects to the
    unfiltered `/petshop/products`. (`routes.py:340`, `:356`)
29. **A blank category name is discarded silently.** The server checks for it and
    simply redirects, with no error flash. (`routes.py:379-386`)

### Point of Sale behaviour

30. **After a failed charge the till stops updating.** The error handler replaces
    the whole Charge button's content, destroying the `btn-total` element that
    `recalc()` writes to; every later recalculation throws at that line, so the
    change display stops responding. Reload the page after any charge error.
    (`pos.html:369`, `:282`)
31. **On a network error the button text stays "Processing…"** even though the
    button is re-enabled. (`pos.html:374`)
32. **Stock figures on the tiles go stale after a sale.** `+ New Sale` clears the
    cart without reloading the page, so the tiles still show the pre-sale stock
    and a sold-out product remains clickable until the page is refreshed — the
    server will then refuse it with the out-of-stock message.
    (`pos.html:377-385`)
33. **The receipt modal has no close control** other than `+ New Sale`.
    (`pos.html:172-182`)
34. **The POS never records a pet, a note, a payment reference or a source other
    than `in-clinic`.** All four columns exist on the order and three of them
    have no display anywhere either. (`pos.html:359-366`)
35. **A product with zero stock is invisible in the POS**, rather than shown
    greyed out. The template has a disabled "out" style for such tiles, but the
    query that feeds it excludes them, so that style is never used.
    (`routes.py:444-448`, `pos.html:96`)

### Bilingual coverage

36. **Several screens are English-only despite the product being bilingual.**
    The whole product form's field labels and section headings, the Products
    page title and search placeholder, the POS payment method names, cart
    heading, tendered-amount placeholder, receipt modal and `+ New Sale` button,
    the Orders page title and search placeholder, the entire Reports KPI row and
    section titles, and the five dashboard quick-nav labels all stay English when
    the interface language is Arabic.
37. **Arabic product and category names are captured but never displayed.**
    `ps_products.name_ar` and `ps_categories.name_ar` have input fields on their
    forms and appear on no list, card, receipt, order or report.
    (`product_form.html:43-46`, `categories.html:92-95`)

---

*Verified against the source on 2026-08-19. Every screen section above ends with
the file and line range it was written from; if a screen disagrees with this
text, the code is the authority and this file is stale.*
