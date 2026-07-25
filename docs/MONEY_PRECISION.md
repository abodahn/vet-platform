# Money precision — findings, recommendation, and rollout

**Status: migration written, tested, and NOT recommended for immediate release.**
**There is a separate one-line bug fix in this document that I do recommend, urgently.**

Audience: the person who has to authorise this. You do not need to be a database
engineer to read it. Technical detail is indented under each heading; the
plain-language summary is always the first paragraph.

---

## 1. The short version

Your database stores every amount of money as a "binary float" — a number format
that cannot represent most decimal fractions exactly. It is the same reason a
pocket calculator sometimes shows `0.30000000000000004` instead of `0.30`.

I looked for actual damage in your real data and, for the invoicing side,
**found none**. Your invoices all balance. That is a genuine null result and it
is good news.

But I did find one live bug that this format causes, it is reachable through
normal daily use, and it is the exact bug that generates customer complaints:
**an invoice that has been paid in full can stay marked "Partial" forever.**
It happens on roughly **1 in 7** invoices that are paid in instalments.

The good news is that this specific bug does **not** need the big migration to
fix. It needs one line changed. The big migration is a much larger, riskier
project, and my recommendation is to do the one-line fix now and defer the
migration. Sections 5 and 6 explain why.

---

## 2. What I measured (evidence)

All measurements were taken against the live `data/platform.db`, opened in
**read-only mode**. Nothing was written to it.

> Method note: the connection was opened as `file:...?mode=ro`, and I verified
> that this genuinely blocks writes (an attempted `CREATE TABLE` was rejected
> with `attempt to write a readonly database`). All migration testing was done
> on a throwaway copy.

### 2.1 How much data this is

This is a small database. Judge the strength of the evidence accordingly.

| Table | Rows |
|---|---|
| invoices | 15 |
| invoice_lines | 55 |
| payments | 30 |
| expenses | 42 |
| purchase_orders | 3 |
| po_lines | 18 |
| items | 15 |
| owners | 30 |
| service_catalog | 23 |
| ps_orders (pet shop POS) | 95 |
| ps_order_items | 230 |
| daily_closings | 0 |
| inpatient_stays | 0 |
| stock_movements | 0 |

**15 invoices is not enough to prove the system is healthy.** It is enough to
prove that no large corruption has happened yet, and it is enough to show which
code paths are dangerous. Treat section 2.4 (which does not depend on sample
size) as the stronger evidence.

### 2.2 Do the invoices balance? Yes — all of them

| Check | Mismatches | Largest discrepancy |
|---|---|---|
| `invoices.subtotal` = sum of its `invoice_lines.total` | **0 of 15** | 0.00 |
| `invoices.total` = subtotal − discount + tax | **0 of 15** | 0.00 |
| `invoices.paid_amount` = sum of its `payments.amount` | **0 of 15** | 0.00 |
| `invoices.due_amount` = total − paid | **0 of 15** | 0.00 |
| Invoices stuck with a balance smaller than one piastre | **0 of 15** | — |
| Fully paid but not marked Paid | **0 of 15** | — |

**No customer has been overcharged or undercharged by this defect. No invoice is
currently stuck.** This is an honest null result.

The reason it is clean is that the invoicing code already rounds to 2 decimal
places at almost every write — `models/database.py:2523-2526` and
`blueprints/finance/routes.py:349, 371-374`. Somebody was careful. That
discipline, not the column type, is what is protecting you today.

### 2.3 Values that are not exact to 2 decimal places

| Measure | Count |
|---|---|
| Money values examined | 499 |
| Not exactly 2 decimal places | **42** |
| Stored as a float that is not exactly the decimal it displays as | **93** |

All 42 are in **`expenses.amount`**, and they look like this:

```
expenses.amount = 8479.738821069359     (should be 8479.74)
expenses.amount = 968.2315890181488     (should be 968.23)
expenses.amount = 266.09512160445865    (should be 266.10)
```

These are not customer-facing invoice amounts — they are your own expense
records, and they came from the demo seed script, which generated random amounts
without rounding them. The practical effect today is that your **expense total
is wrong by 2.08 piastres**:

```
SUM(expenses.amount) as stored     = 73972.82917830236
SUM(expenses.amount) done exactly  = 73972.85
                        difference = −0.0208 EGP
```

Small. But it is a financial report disagreeing with itself, and it grows with
the number of rows.

### 2.4 The live bug — invoices that can never be marked Paid

This is the important finding, and it does **not** depend on the small sample
size, because it is a property of the code rather than of the current data.

When a payment is recorded, `models/database.py:2591-2594` does this:

```python
total    = float(row["total"] or 0)
new_paid = min(float(row["paid_amount"] or 0) + float(amount), total)
due      = max(0.0, total - new_paid)
status   = "Paid" if due == 0 else "Partial"
```

The last line asks whether the remaining balance is *exactly* zero. With binary
floats, a series of instalments that add up to the total on paper can land a
hair below it — leaving a balance like `0.00000000000045 EGP`. That is not zero,
so the invoice is marked **"Partial"**, and it stays that way permanently. No
further payment can clear it, because the customer owes nothing.

The screen shows a balance of `0.00` and a status of `Partial`. That is the
phone call.

I simulated the real cashier workflow — each payment re-reading the stored
balance, exactly as the application does — over 200,000 invoices, under two
different operator behaviours:

| Operator behaviour | Invoices left stuck on "Partial" after being paid in full |
|---|---|
| (a) Final payment = the remaining balance shown on screen | **28,342 of 200,000 — 14.17%** |
| (b) Final payment = operator's own "total minus what they've paid" | **28,687 of 200,000 — 14.34%** |

Real examples produced by the simulation:

```
total = 2259.28   paid = 2259.2799999999997   balance left = 0.00000000000045   -> "Partial"
total = 4431.89   paid = 4431.889999999999    balance left = 0.00000000000091   -> "Partial"
total = 1270.01   paid = 1270.0099999999998   balance left = 0.00000000000023   -> "Partial"
```

**About 1 in 7 instalment-paid invoices is affected.** You have not seen it yet
because your 15 invoices were all paid in ways that happened to land exactly.
Once real customers start paying in instalments, you will.

I also checked whether the `min(...)` clamp in that code protects you. It does
not — the strand rate is identical (14.38%) with and without it.

### 2.5 The one-line fix

Changing the accumulation to round to 2 decimal places eliminates it completely:

| Version of the code | Stuck invoices per 50,000 |
|---|---|
| Current: `min(paid + amount, total)` | 7,188 (14.38%) |
| Clamp removed: `paid + amount` | 7,188 (14.38%) |
| **Rounded: `round(paid + amount, 2)`** | **0 (0.00%)** |

**This fix requires no migration, no schema change, and no downtime.** See
section 6 for the exact diff.

### 2.6 Where money is still written without rounding

These are the places that will create new bad values. The invoicing path is
protected; the pet shop POS path is not.

| Location | Expression | Rounded? |
|---|---|---|
| `models/database.py:2520` | `subtotal = sum(float(l['total']) for l in lines)` | **no** |
| `models/database.py:2592` | `new_paid = min(paid + amount, total)` | **no** |
| `blueprints/petshop/routes.py:425` | `subtotal = sum(qty * unit_price)` | **no** |
| `blueprints/petshop/routes.py:426` | `tax_amt = sum(qty * price * tax_rate / 100)` | **no** |
| `blueprints/petshop/routes.py:427` | `total = subtotal - discount + tax` | **no** |
| `blueprints/petshop/routes.py:428` | `change = max(0, paid - total)` | **no** |

The VAT line is the worst of these. Simulating realistic pet-shop sales,
**65.9%** of them store a total that is not a whole number of piastres, because
14% VAT on a price like 19.99 gives `22.7886` and nothing rounds it:

```
1 x 19.99 @ 14% VAT -> total stored as 22.7886   (should be 22.79)
2 x 19.99 @ 14% VAT -> total stored as 45.5772   (should be 45.58)
```

Your pet shop currently has 0% tax rates configured, which is why the 95 stored
orders are clean. **The day you switch VAT on, this starts producing bad data
immediately.**

Also: `models/database.py:2520` sums line totals without rounding. Simulated
over 20,000 invoices, **13.7%** produce a subtotal that differs from the exact
sum of their own lines (worst case seen: 0.0000000000009 EGP).

### 2.7 A separate problem I found while I was in there

Unrelated to floats, but it is a financial data-integrity issue and you should
know about it.

**82 of your 95 pet shop orders have a subtotal that does not match their own
line items** — and these are not rounding-sized errors, they are large:

```
order #1: subtotal recorded 1980.00, but its line items add up to 2190.00  (off by 210.00)
order #2: subtotal recorded 1740.00, but its line items add up to  870.00  (off by 870.00)
order #4: subtotal recorded 1866.00, but its line items add up to 3118.00  (off by 1252.00)
```

**Cause: a bug in the demo seed script, not in the application.**
`seed_petshop.py:170` computes the order subtotal using one set of random
quantities, then `seed_petshop.py:187` draws *fresh* random quantities when
writing the line items. The two never agree.

The live application code (`blueprints/petshop/routes.py:425`) computes the
subtotal from the same items it writes, so it is consistent. **Real orders are
fine; the demo data is fiction.** But if any of those 95 orders are treated as
real revenue in a report, the numbers are meaningless. Worth confirming whether
this database has ever had real pet shop sales entered into it.

---

## 3. What the correct storage type is

### PostgreSQL (your production database) — `NUMERIC(12,2)`

Unambiguous. PostgreSQL's `NUMERIC` is a true decimal type: it stores 12.10 as
exactly 12.10, and `SUM()` over it is exact. `(12,2)` allows amounts up to
9,999,999,999.99, which is far beyond any veterinary invoice.

### SQLite (your development and current database) — no real answer exists

**This is the part that matters and it is easy to miss.** SQLite has no true
decimal type. Declaring a column `NUMERIC(12,2)` gives it *NUMERIC affinity*,
which for any fractional value **still stores a binary float**. It is a label,
not a guarantee.

So there are three honest options for SQLite, and only three:

| Option | What it means | Verdict |
|---|---|---|
| Integer piastres | Store 12.10 as the integer `1210` | Genuinely exact — but changes the meaning of every value in the database and every line of code that reads one. A far bigger project than the type change. |
| TEXT | Store `"12.10"` as a string | Exact, but arithmetic and `ORDER BY` in SQL break. |
| **Accept SQLite is dev-only** | Declare `NUMERIC(12,2)`, get the real guarantee only on PostgreSQL | **Recommended.** |

**My recommendation: the third.** Declare `NUMERIC(12,2)` on both engines. On
PostgreSQL you get a real guarantee. On SQLite you get a correct *declaration*
and a one-time cleanup of the stored values, but not a guarantee.

You must understand the consequence: **after this migration, SQLite and
PostgreSQL behave differently.** On PostgreSQL every amount read from the
database becomes a `Decimal` object; on SQLite it stays a float. Your test suite
runs on SQLite. **Your tests will pass and production can still break.** This is
the single largest risk in the whole exercise.

### The currency question

`clinic.currency` defaults to `'EGP'` (`models/database.py:444`) and the
settings page offers EGP, USD, EUR, GBP, SAR, AED
(`templates/system/settings.html:92-96`), described as "Used on invoices and
financial reports".

**That description is false.** Nothing in the application ever reads
`clinic.currency` to display an amount. The currency symbol is hardcoded as
`EGP` in **186 templates and 49 Python files** — 235 places. The setting is
write-only and has no effect.

All six currencies offered happen to use 2 decimal places, so `NUMERIC(12,2)` is
safe for all of them. But nothing in the codebase supports a currency with a
different number of decimals, and this migration hard-codes that assumption into
the storage layer as well. That is acceptable today and worth knowing.

---

## 4. What the application code would have to change

This is the part that decides the recommendation, so I am going to be blunt
about it rather than optimistic.

On PostgreSQL, `NUMERIC` columns come back to Python as `Decimal` objects
instead of `float`. The word `Decimal` **does not appear anywhere in this
codebase today**. There is no conversion layer in `models/database.py` — no
`register_converter`, no `register_adapter`, no type casting. The values pass
straight through into templates, JSON responses, and exports.

| Area | Sites needing review | Will crash | Silent behaviour change |
|---|---|---|---|
| Python money arithmetic | 162 (up to 455) | ~0 | 172 `float()` downcasts |
| Money comparisons | 45 | 0 | 45 |
| Jinja templates | 333 across 61 files | `\|tojson` sites | **261 raw displays** |
| Custom money filter | **none exists** | — | no single place to fix |
| JSON API responses | 12 handlers | **6+ confirmed 500 errors** | 25 JS `toFixed(2)` downstream |
| CSV / Excel / PDF export | 5 | 0 | **3 (Excel totals row vanishes)** |
| Database helper functions | 17 + 42 SQL `SUM()`s | — | dev/prod divergence |

**Total: 550–800 call sites need review.**

The risk here is not shaped the way you would expect:

1. **Crashes are few and easy to find.** The code is already defensively wrapped
   in `float()` almost everywhere, which accidentally immunises the arithmetic.
   The known crash sites are about 6 JSON endpoints — including
   `blueprints/public_api/routes.py:72-84`, which is **public and
   unauthenticated** and would start returning HTTP 500 immediately.

2. **Silent changes are many and hard to find.** 261 template locations display
   money with no formatting at all. `{{ item.sell_price }}` renders `120.5`
   today and `120.50` after the migration. Nothing breaks, nothing is logged —
   the page just quietly looks different in 261 places.

3. **`models/excel_export.py:83, 95, 102`** check `isinstance(value, (int,
   float))`. A `Decimal` is neither. The result: **every financial Excel export
   silently stops emitting its TOTAL row.** No error. You find out when someone
   asks why the spreadsheet has no total.

4. **The migration as scoped does not actually buy you precision.** Storage
   becomes exact, and then those 172 `float()` calls convert every value
   straight back to binary float to do the arithmetic, round it, and write it
   back. To get the real benefit you have to remove those coercions too — which
   reintroduces the crash surface you are currently immune to.

Point 4 is the crux. **The migration alone is close to cosmetic.**

---

## 5. Recommendation

### Do this now — the one-line fix (recommended, low risk)

Fix the stuck-invoice bug. It is the only defect here with a proven,
customer-visible impact, and it is independent of the migration.

`models/database.py:2592-2594` — **note: I did not apply this; another agent
holds this file.**

```diff
-        total = float(row["total"] or 0)
-        new_paid = min(float(row["paid_amount"] or 0) + float(amount), total)
-        due = max(0.0, total - new_paid)
-        status = "Paid" if due == 0 else "Partial"
+        total = round(float(row["total"] or 0), 2)
+        new_paid = round(min(float(row["paid_amount"] or 0) + float(amount), total), 2)
+        due = round(max(0.0, total - new_paid), 2)
+        status = "Paid" if due < 0.005 else "Partial"
```

Two changes, both needed: rounding stops the residue being created, and
`< 0.005` (less than half a piastre) stops an exact `== 0` comparison being the
thing your invoice status depends on.

Verified: this takes the strand rate from 14.38% to **0 out of 50,000**.

While in the same file, `models/database.py:2520`:

```diff
-    subtotal = sum(float(l.get("total",0)) for l in lines)
+    subtotal = round(sum(float(l.get("total",0)) for l in lines), 2)
```

And the pet shop, `blueprints/petshop/routes.py:425-428`:

```diff
-        subtotal = sum(float(i["qty"]) * float(i["unit_price"]) for i in items)
-        tax_amt  = sum(float(i["qty"]) * float(i["unit_price"]) * float(i.get("tax_rate",0))/100 for i in items)
-        total    = subtotal - discount_g + tax_amt
-        change   = max(0, paid_amt - total)
+        subtotal = round(sum(float(i["qty"]) * float(i["unit_price"]) for i in items), 2)
+        tax_amt  = round(sum(float(i["qty"]) * float(i["unit_price"]) * float(i.get("tax_rate",0))/100 for i in items), 2)
+        total    = round(subtotal - discount_g + tax_amt, 2)
+        change   = round(max(0, paid_amt - total), 2)
```

**Do this one before you enable VAT on the pet shop.** Right now your tax rates
are 0%, which is the only reason 65.9% of POS totals are not already wrong.

### Do NOT run the migration yet

The migration is written, tested, and ready (section 7). I recommend **against
releasing it now**, for four reasons:

1. **There is no damage to repair.** Every invoice balances. The migration fixes
   a theoretical exposure while the one real bug is fixed by section 6 above at
   roughly 1% of the risk.
2. **It buys little while the `float()` calls remain.** Exact storage feeding
   inexact arithmetic is exact storage of an inexact answer.
3. **Your tests cannot catch the failures.** Tests run on SQLite, where the
   behaviour does not change. The 500 errors appear only on PostgreSQL.
4. **The unsafe part is not the database, it is the 261 silent display changes
   and the vanishing Excel totals row** — none of which announce themselves.

### When it *should* be run

Run it as **step 3 of 3**, not step 1:

1. **First**, add a `|money` Jinja filter and a Flask JSON provider that knows
   how to serialise `Decimal`. Two registrations near `app.py:170`. This
   collapses ~350 of the 800 sites down to about 2. Also fix the three
   `isinstance` checks in `models/excel_export.py:83, 95, 102` to include
   `Decimal` — a three-token change guarding a silent data loss.
2. **Then**, move the 261 raw template displays onto that filter, and remove the
   `float()` coercions from the 17 money helpers in `models/database.py`.
3. **Then** run this migration — ideally in the same maintenance window as the
   PostgreSQL cutover, since that is when the type actually starts mattering.

Doing it in the other order means fixing 350 sites live, under production
pressure, with real customers waiting.

---

## 6. What the migration does, and proof that it works

`db_migrations/versions/0002_money_numeric.py`.

It converts **34 currency columns across 15 tables** from `REAL` to
`NUMERIC(12,2)`, rounding each stored value to 2 decimal places (half-up) on the
way.

**Not touched, deliberately:** measurement columns that are genuinely
continuous and where `REAL` is correct — `weight_kg`, `temp_c`, `quantity`,
`hours_worked`, `days_requested`, leave balances, `result_value`,
`fluid_input`/`fluid_output`, `reorder_level`, `reorder_qty`, `max_stock`. Also
not touched: the various `tax_rate` columns, which are percentages, not money.

**Also not touched: the pet shop tables** `ps_products`, `ps_orders`,
`ps_order_items` — even though they hold real money and are just as affected.
Two reasons, both discovered during testing:

- `blueprints/petshop/routes.py:37` (`ensure_petshop_tables()`) runs
  `CREATE TABLE IF NOT EXISTS` on nearly every pet shop request — 16 call sites.
  On a fresh database the application recreates those tables with `REAL` columns
  the first time anyone opens the pet shop, undoing the migration. Alembic
  cannot own a table the application recreates on demand.
- `ps_order_items` declares its foreign key inline
  (`order_id INTEGER ... REFERENCES ps_orders(id) ON DELETE CASCADE`) rather
  than as a table-level clause. SQLAlchemy's SQLite reflection does not recover
  `ON DELETE` from that form, so the table rebuild **silently downgraded the
  CASCADE to NO ACTION**, which would start orphaning order line items on
  delete. My verification caught this on the copy; it is why the pet shop is now
  out of scope. Fixing it properly means editing
  `blueprints/petshop/routes.py:49-101`, which is an application change.

### Rounding choice

Half-up (`ROUND_HALF_UP`), which is the money convention and matches what
PostgreSQL's own `::numeric(12,2)` cast does.

Values are converted via `Decimal(repr(v))`, not `Decimal(v)`. This matters: a
price typed as `2.675` is stored as `2.67499999999999982...`. Reading the exact
binary value and rounding gives `2.67` — silently taking a piastre off the
invoice. Reading the shortest decimal that round-trips gives `2.675`, which
rounds half-up to `2.68`, which is what the operator meant.

> One inconsistency worth noting: the application's own `round(x, 2)` calls use
> Python's built-in `round`, which is *banker's* rounding (half-to-even), not
> half-up. So the migration and the application would round `.005` ties in
> opposite directions. In practice exact ties essentially never occur in binary
> floats, and none exist in your current data, so this is a latent
> inconsistency rather than an active bug — but it should be reconciled if the
> money handling is ever overhauled properly.

### Verification results (T4)

The migration was run against a **copy** of the real database. The real file was
never opened for writing.

| Check | Result |
|---|---|
| 1. Row counts identical across all 84 tables | **PASS** |
| 2. All 34 money columns retyped; 0 still `REAL` | **PASS** |
| 3. All 499 money values round-trip to the same 2-decimal amount | **PASS** |
| 4. Reconciliation checks no worse (see below) | **PASS** |
| 5. Indexes preserved (70 → 70) | **PASS** |
| 6. Foreign keys unchanged, including `ON DELETE CASCADE` | **PASS** |
| 7. `downgrade()` restores `REAL` | **PASS** |
| 8. Amounts survive a full upgrade→downgrade round trip | **PASS** |
| 9. Row counts identical after round trip | **PASS** |
| 10. Running the upgrade twice is a no-op (idempotent) | **PASS** |

Reconciliation, before and after:

```
subtotal_vs_lines        0 ->  0   same
total_vs_parts           0 ->  0   same
paid_vs_payments         0 ->  0   same
due_vs_total_paid        0 ->  0   same
stuck_sub_cent           0 ->  0   same
values_not_2dp          42 ->  0   BETTER
```

The migration repairs the 42 malformed expense amounts and breaks nothing.

---

## 7. Rollout procedure (for when you decide to run it)

**Do not run this while the application is running.** During this investigation
the live database changed content twice within three seconds — it is being
actively written. Migrating a database that is being written to will lose data.

### Before you start

- [ ] Sections 5/6 (the one-line fixes) are already released and have been
      running in production for at least a week.
- [ ] A `|money` template filter and Decimal-aware JSON encoder are in place.
- [ ] You have a maintenance window with no staff using the system.
- [ ] You have tested the whole procedure on a copy first.

### Step 1 — Back up (do not skip)

```bash
# stop the application first
sqlite3 data/platform.db ".backup 'backups/platform_pre_0002_$(date +%Y%m%d_%H%M).db'"
```

PostgreSQL:

```bash
pg_dump -Fc -f backups/platform_pre_0002_$(date +%Y%m%d_%H%M).dump "$POSTGRES_DSN"
```

**Verify the backup file exists and is not zero bytes before continuing.** This
backup is your real rollback plan. The `downgrade()` is a convenience; the
backup is the guarantee.

### Step 2 — Stop the application

```bash
# systemd
sudo systemctl stop aleefy
# or docker
docker compose stop web
```

Confirm nothing is still connected before proceeding.

### Step 3 — Run the migration

```bash
cd platform
alembic -c db_migrations/alembic.ini upgrade 0002_money_numeric
```

**Expected downtime: under 1 minute** at your current data volume (499 money
values across 34 columns). The work is proportional to the number of rows; at
100× your current size expect a few minutes. The whole thing runs inside a
transaction.

### Step 4 — Verify before letting anyone back in

```bash
sqlite3 data/platform.db "
  SELECT COUNT(*) AS invoices_that_do_not_balance
    FROM invoices i
   WHERE ROUND(i.subtotal, 2) <>
         ROUND((SELECT COALESCE(SUM(l.total), 0)
                  FROM invoice_lines l WHERE l.invoice_id = i.id), 2);"
# expect: 0

sqlite3 data/platform.db "
  SELECT COUNT(*) AS invoices_with_a_sub_piastre_balance
    FROM invoices
   WHERE ABS(total - paid_amount) > 0 AND ABS(total - paid_amount) < 0.005;"
# expect: 0

sqlite3 data/platform.db "SELECT COUNT(*) FROM invoices;"   # expect: 15
sqlite3 data/platform.db "SELECT COUNT(*) FROM payments;"   # expect: 30
sqlite3 data/platform.db "PRAGMA table_info(invoices);"     # 'total' should read NUMERIC(12,2)
```

Then, by hand in the application:

- [ ] Open an existing invoice — the total matches what it was before.
- [ ] Create a new invoice with a discount and a tax rate; check the arithmetic.
- [ ] Record a partial payment, then pay the remainder. **The invoice must flip
      to "Paid".**
- [ ] Open the finance dashboard — no 500 error, and figures look sane.
- [ ] Export an invoice to PDF and to Excel. **Confirm the Excel TOTAL row is
      still there** (see section 4, point 3).
- [ ] Load the public services endpoint (`/api/public/services` or equivalent) —
      it must return JSON, not a 500.

### Step 5 — Restart

```bash
sudo systemctl start aleefy
```

Watch `logs/` for `TypeError` and for `Object of type Decimal is not JSON
serializable` for the first hour. That specific error is the expected failure
mode and tells you exactly which endpoint was missed.

### How to roll back

If verification fails, in order of preference:

1. **Restore the backup** — the safe option, and the only one that is certain:
   ```bash
   sudo systemctl stop aleefy
   cp backups/platform_pre_0002_<timestamp>.db data/platform.db
   sudo systemctl start aleefy
   ```
   You lose any transactions entered since the backup, which is why this happens
   in a maintenance window with nobody using the system.

2. **Run the downgrade** — faster, keeps data entered since the migration:
   ```bash
   alembic -c db_migrations/alembic.ini downgrade 0001_baseline
   ```
   Tested and verified to restore `REAL` and preserve every amount exactly. Use
   this if the problem is application errors rather than wrong data.

---

## 8. What could still go wrong

Honest list. None of these were hypothetical — each is either measured or
identified in the code.

1. **The Excel totals row disappears silently.**
   `models/excel_export.py:83, 95, 102` test `isinstance(value, (int, float))`.
   `Decimal` fails that test. No error is raised, the file still downloads, the
   total is just gone. **Highest-probability real-world failure.**

2. **The public API returns 500.**
   `blueprints/public_api/routes.py:72-84` puts `standard_price` straight into a
   JSON response. Unauthenticated, so if anything external consumes it, it
   breaks for them first. Same risk at `blueprints/payroll/routes.py:609`,
   `blueprints/inventory/routes.py:561`, `blueprints/petshop/routes.py:511, 661,
   676`.

3. **Amounts start displaying differently in 261 places.** `120.5` becomes
   `120.50`. Not a fault, but it is 261 unreviewed visual changes and somebody
   will report it as a bug.

4. **Your tests will not catch any of the above**, because they run against
   SQLite where values stay floats. Green tests are not evidence here. The only
   meaningful test run is against a real PostgreSQL instance.

5. **The pet shop stays on floats** and will produce bad data the moment VAT is
   switched on (section 2.6). The migration does not help it — section 6
   explains why it cannot.

6. **A fresh install still creates `REAL` columns.**
   `db_migrations/versions/0001_baseline.sql` and `models/database.py:_SCHEMA`
   both still declare `REAL`. A brand-new database gets the old types and then
   this migration corrects them. That works, but the two definitions now
   disagree, and `models/database.py` should be updated to match so the
   application and the migrations tell the same story.

7. **SQLite gives you a label, not a guarantee** (section 3). If you never move
   to PostgreSQL, this migration cleans up your existing values once and
   prevents nothing thereafter.

8. **Half-up vs banker's rounding disagreement** between the migration and the
   application's `round()` calls. Latent, not currently triggered.

---

## 9. If you only read one paragraph

Your invoices currently balance and no customer has been charged incorrectly.
But roughly 1 in 7 instalment-paid invoices will get permanently stuck showing
"Partial" after being paid in full — that is a real bug, live today, and it is
fixed by changing **one line** in `models/database.py:2592-2594`. Do that. The
34-column database migration is written, tested and ready, but it touches 550 to
800 places in the application, your test suite cannot verify it, and it fixes a
risk rather than an actual injury. Hold it until you move to PostgreSQL, and do
the display and JSON-encoding work first.
