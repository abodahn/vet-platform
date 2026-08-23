# 04 — Technical Handover

**For the engineer who inherits this codebase.**

Everything in this document was executed on 2026-07-28 against the repository as
it stands at commit `cb11154`. Where something could not be executed, it says
"not verified". Nothing here is aspirational.

Environment used for verification:

| | |
|---|---|
| Repo root | `D:\vet\platform` (this is the git root, **not** `D:\vet`) |
| Python | 3.14.6, virtualenv at `D:\vet\.venv` |
| OS | Windows 11, Git Bash / PowerShell |
| SQLite | 3.50.4 (bundled with CPython) |
| App version | `platform/VERSION` = `3.0.0` |

---

## 1. Day one

### 1.1 Get the code

```bash
git clone https://github.com/abodahn/vet-platform.git platform
cd platform
```

The repository root is the `platform` directory. `D:\vet` on the seller's
machine is a working junk drawer (archives, `node_modules`, an unrelated React
project) and is deliberately **not** under version control. Do not `git init` a
parent directory — it makes `platform` look like a submodule and breaks staging.

Branches present on the remote at handover:

```
main
feature/v3-complete-uiux-revamp
```

The working branch the seller was on is `fix/audit-remediation` (local only at
the time of writing — confirm it has been pushed before you accept the transfer;
see §7.1).

### 1.2 Install

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt -r requirements-dev.txt
```

51 packages resolve. `psycopg2-binary` ships wheels, so no PostgreSQL client
headers are needed to install. `pg_dump` **is** needed at runtime for PostgreSQL
backups (see §6.2).

### 1.3 Run the tests — verified

The suite runs entirely on SQLite. No PostgreSQL, no Docker, no fixtures to
seed. `tests/conftest.py` builds a throwaway database per session.

```bash
cd platform
POSTGRES_DSN="" python -m pytest -q
```

Verified output:

```
549 passed, 164 warnings in 103.40s
```

The 164 warnings are almost entirely `datetime.utcnow()` deprecations from
Python 3.12+. They are noise, not failures, but they will become errors when
`utcnow()` is finally removed — treat it as scheduled maintenance.

If you get `ModuleNotFoundError: playwright`, your shell's working directory is
`D:\vet`, not `D:\vet\platform`, and pytest has picked up the wrong `conftest.py`.
This is the single most common false alarm in this repo.

### 1.4 Boot it and log in — verified

The app runs with **no PostgreSQL at all**. Setting `POSTGRES_DSN` to an empty
string (or anything that does not match `postgresql://user:pass@host:port/db`)
makes `create_app` log a warning and fall through to SQLite.

```bash
cd platform
export FLASK_ENV=development
export POSTGRES_DSN=""
export PLATFORM_ADMIN_PASS='Choose-A-Real-Password!1'
python run.py
```

Then open `http://localhost:5100`, log in as `admin` with the password you just
set. Verified request trace on a clean database:

```
GET  /             -> 302  /auth/login
GET  /auth/login   -> 200
POST /auth/login   -> 302  /
GET  /             -> 200   (121,840 bytes)
```

`create_app` registers **33 blueprints** and **379 URL rules**.

Three things about that first boot that will confuse you:

- **`PLATFORM_ADMIN_PASS` only matters on the very first run.** `init_db()` seeds
  the admin user once. Changing the variable afterwards does nothing; you have to
  delete the database file to re-seed.
- **`run.py` tries to launch a Node server** called `freellmapi` from
  `~/freellmapi` before starting Flask (`run.py:78`). That directory does not
  exist in the deliverable, so it prints "server dir not found — skipping" and
  continues. It is a dead limb from an earlier AI-router design; the live AI
  provider is OpenRouter over HTTP. Deleting `_start_freellmapi`/`_stop_freellmapi`
  is safe, but nobody has done it.
- **`/healthz` returns HTTP 503 `{"status":"degraded"}` on a fresh install.**
  This is correct behaviour, not a bug: the health check requires database OK
  **and** scheduler running **and** a recent successful backup, and a brand-new
  install has never taken a backup. It goes green after the first nightly run at
  02:00 or a manual backup. Anything you wire to `/healthz` — a load balancer,
  an uptime monitor — must not be deployed before you understand this, or every
  new clinic will page you on day one.

### 1.5 `.env` loading is first-match, not merged

`run.py::_load_env()` looks for `.env.<FLASK_ENV>` first and **stops** if it
finds it. `.env` is never read in development because `.env.development` exists.
Adding a variable to `.env` and wondering why nothing changed has cost time
before. Edit the stage-specific file. Shell environment variables always win
over both.

---

## 2. The architecture in one page

Server-rendered Flask. No SPA, no API-first layer, no build step for the
application itself (there is one for CSS — see §5.6).

```
run.py                  entry point: loads .env, calls create_app, app.run
app.py                  the application factory + all cross-cutting middleware
config.py               Config / DevelopmentConfig / TestConfig / ProductionConfig
                        VERSION_INFO reads platform/VERSION at import
models/
  database.py           THE database layer. ~38k tokens. See §3.
  security.py           CSRF, login attempt throttling, 2FA (TOTP)
  pdf_generator.py      fpdf2 documents: invoice, vaccination cert, payslip
  backup.py             SQLite backup() / pg_dump, S3 upload signed by hand
  audit.py              the sanctioned writer for the `audit_log` table
  logging_setup.py      rotating logs, correlation IDs, optional Sentry
blueprints/<module>/    33 modules; each is __init__.py (Blueprint) + routes.py
templates/              170 Jinja templates, 33,883 lines
static/css/             5 source stylesheets + a built app.min.css
db_migrations/          Alembic. See §5.2.
migrations/             NOT Alembic — this is excel_import.py, the data importer
tests/                  33 test modules, 7,166 lines, 549 tests
```

Sizes: 131 Python files / 38,314 lines; 170 templates / 33,883 lines.

### 2.1 The app factory

`app.py::create_app(cfg)` does, in order:

1. If `FLASK_ENV=production`, calls `ProductionConfig.validate()` which raises
   `RuntimeError` on any missing required variable. This is the only place that
   stops a misconfigured production boot.
2. Initialises logging **before** the database, so the "falling back to SQLite"
   warning is actually captured.
3. Parses `POSTGRES_DSN` with a regex. A match calls `db.configure_postgres(...)`;
   anything else logs a warning and leaves the layer on SQLite. **A typo in the
   DSN does not fail — it silently downgrades you to a local SQLite file.** In
   production `ProductionConfig.validate()` catches an *absent* DSN but not a
   *malformed* one. Check the startup log line, every deploy.
4. `db.init_db()` — creates every table if missing and seeds roles + the admin
   user. This runs on **every boot**. It is idempotent but it is not a migration
   system; see §5.2 for how the two coexist.
5. `app.teardown_appcontext(db.close_context_connections)`. This one line is
   load-bearing: 247 route functions call `get_db()` with no `try/finally`, the
   PostgreSQL pool is capped at 20, and without this hook a single unhandled
   exception leaked a connection permanently. Do not remove it, and do not
   "clean up" the hundreds of missing `finally` blocks instead — the hook is the
   cheaper correct fix and it is already tested.
6. Registers the 33 blueprints.
7. Installs the context processor (§2.2) and the security middleware.

`blueprints/api_v1/` exists in the tree and is **deliberately not registered**.
Its `/api/v1/health` and `/api/v1/version` echo `FLASK_ENV` to unauthenticated
callers. Do not register it just to get a health endpoint — `/healthz` in
`app.py:243` is the one that is meant to be public.

### 2.2 The context processor is where half the app's globals come from

`app.py:~170-212` injects into **every** template: `clinic`, `current_user`,
`current_role`, `current_lang`, `current_theme`, `csrf_token`, `unread_count`,
and the i18n helper `t`. If you are looking for where a template variable comes
from and it is not in the view's `render_template(...)` call, it is here.

### 2.3 Auth and roles

- Login writes `session["user"] = {id, username, role, language, ...}`.
  It does **not** write `session["user_id"]` or `session["role"]`. Code that
  reads those keys (the unregistered `api_v1`) fails closed for everyone.
- Authorization is `@role_required("doctor", "nurse", ...)` — 89 call sites — a
  hardcoded list of role names per route. `super_admin` bypasses every check.
- 14 seeded roles: `super_admin, clinic_owner, branch_manager, doctor, nurse,
  reception, inventory_mgr, pharmacist, finance, hr, groomer, boarding_staff,
  support_admin, auditor`. The canonical front-desk role is **`reception`**, not
  `receptionist`; that typo has locked reception staff out of the POS before and
  is now guarded by `tests/test_role_consistency.py`.
- The data-driven RBAC engine exists (`has_permission`, `permission_required`,
  `roles.permissions_json`, the Roles admin UI) but is applied to **2 routes**.
  See §7.2.

---

## 3. The database layer — read this before you touch anything

There is **no ORM**. `models/database.py` is a hand-rolled layer that presents a
`sqlite3`-shaped API and runs on either SQLite or PostgreSQL. It is the single
highest-risk file in the repository and the one a new developer will most
reliably misunderstand.

### 3.1 It translates SQL in *both* directions

Two functions, and they are mirrors of each other:

| | |
|---|---|
| `_fix_sql(sql)` — `models/database.py:135` | SQLite-flavoured SQL → PostgreSQL. Applied by `_PGCursor.execute`/`executemany`. |
| `_fix_sql_sqlite(sql)` — `models/database.py:355` | PostgreSQL-flavoured SQL → SQLite. Applied by the sqlite3 cursor subclass at `:386`. |

**Every statement in the application passes through one of these.** The SQL you
write in a route is not the SQL the database executes.

`_fix_sql` (→ PostgreSQL) rewrites:

- `?` → `%s`, but never inside a single-quoted string literal (so
  `'Confirm? reply YES'` survives)
- `datetime('now')` → `NOW()`
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `INSERT OR IGNORE` / `INSERT OR REPLACE` → `INSERT ... ON CONFLICT DO NOTHING`

`_fix_sql_sqlite` (→ SQLite) handles `::casts`, `EXTRACT(... FROM ...)`,
`AGE(...)`, `INTERVAL` literals and `ILIKE`. Its governing rule is stated in the
source and is the right one: **anything that cannot be translated faithfully is
left alone so SQLite raises**, rather than silently returning a wrong number in
a financial or clinical report. Do not "helpfully" add a lossy translation.

Both caches are keyed on the raw SQL string. `_FIX_CACHE` is unbounded;
`_SQLITE_FIX_CACHE` has a flat 5,000-entry cap. Both are safe only because SQL
text comes from a fixed set of call sites. If you ever generate SQL from
unbounded user input, that assumption dies.

### 3.2 The conventions that are enforced by review alone

These have failed in production before. There is no linter for them.

- **Write `?`, never `%s`.** `?` is portable in both directions. A raw `%s` in a
  query worked on PostgreSQL and broke SQLite silently for a long time —
  181 instances were fixed across 8 blueprints in one session. Current count of
  raw `%s` in `blueprints/`: **0**. Keep it there.
- **Write `datetime('now')`, never `NOW()`.** Better: compute the timestamp in
  Python and bind it.
- **Never inline a `LIKE '%foo%'` literal.** psycopg2 reads `%f` as a format
  placeholder and raises. Bind it: `LIKE ?` with `("%foo%",)`.
- **Use `DOUBLE PRECISION` for epoch floats, never `REAL`.** PostgreSQL `REAL` is
  a 4-byte float (~7 significant digits) and rounds a unix timestamp to the
  nearest ~128 seconds. SQLite gives anything containing "DOUB" REAL affinity, so
  `DOUBLE PRECISION` is correct on both.
- **`settings` is the only table without an `id` column.** `_PGCursor.execute`
  speculatively appends `RETURNING id` to every INSERT so `lastrowid` works;
  `_TABLES_WITHOUT_ID` is the exception list, and
  `tests/test_db_layer.py::test_no_id_table_list_matches_schema` fails if it drifts.
- **psycopg2 must receive `None`, not `()`, for parameterless SQL.** Otherwise a
  literal `%` in the statement raises.
- **`sqlite3.Row` has no `.get()`.** psycopg2's DictRow does. Any helper whose
  result feeds a `.get()` call site must return `dict(row)`.

### 3.3 Connections

`get_db()` checks a connection out of the pool (PostgreSQL) or opens a SQLite
connection, and registers it on Flask's `g` for release by
`close_context_connections` at the end of the request. Outside an app context
(scripts, seeders) that registration is a no-op and **you** must close it.

`_PGCursor.execute` runs bare — one round-trip. It used to wrap every statement
in `SAVEPOINT`/`RELEASE` on a separate admin cursor, which cost 3–5 round-trips
per query and was the main performance bottleneck. Only idempotent DDL that is
*expected* to fail needs `execute(sql, params, _protect=True)`, or the
`_try_stmt(conn, sql)` helper. **Never re-add blanket savepoints.**

---

## 4. The traps

These are the things that have actually broken this codebase. Most of them fail
*silently*, which is why they are worth a page.

### 4.1 `SERIAL PRIMARY KEY` is silently broken on SQLite

SQLite *parses* `SERIAL PRIMARY KEY` without complaint. It gives the column
NUMERIC affinity, which means it is not a rowid alias, which means it does not
autoincrement. Verified on SQLite 3.50.4:

```
CREATE TABLE t1 (id SERIAL PRIMARY KEY, x TEXT);  -- accepted
INSERT ... ; INSERT ... ;
SELECT id, x FROM t1;   ->  [(None, 'a'), (None, 'b')]
```

Every primary key is `NULL`. Compare `INTEGER PRIMARY KEY AUTOINCREMENT`, which
gives `[(1, 'a')]`. **An error would have been better than this.**

There is one live instance: `blueprints/telemedicine/routes.py:33` writes
`id SERIAL PRIMARY KEY` in a `CREATE TABLE`, with a comment claiming SQLite is
fine. It happens to work only because the *same statement* also contains
`created_at TIMESTAMP DEFAULT NOW()`, which SQLite genuinely rejects, so the
whole `CREATE` raises and the `except` block at `:54` runs a correct
AUTOINCREMENT version. It is right by accident. If someone "fixes" the `NOW()`
default without touching the `SERIAL`, telemedicine sessions start getting NULL
ids on SQLite.

### 4.2 SQLite accepts far more DDL than you expect

Verified empirically. Only **two** constructs actually raise on SQLite:

- `DEFAULT NOW()` — unparenthesised function default → `near "(": syntax error`
- `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`

All of these parse fine and must **not** be rewritten (that is churn with
type-change risk on PostgreSQL): `VARCHAR(n)`, `DATE`,
`DATE DEFAULT CURRENT_DATE`, `NUMERIC(p,s)`, `BOOLEAN DEFAULT FALSE/TRUE`,
`NULLS LAST`, `ON CONFLICT ... DO UPDATE ... EXCLUDED.`,
`COUNT(*) FILTER (WHERE ...)`.

Corollary: keep `DATE` columns as `DATE`. `blueprints/hr/routes.py` does
`expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days'` and
`expiry_date - CURRENT_DATE`. Both are PostgreSQL date arithmetic that fails on
a `TEXT` column in a fresh PostgreSQL database. "House-styling" dates to TEXT
breaks HR.

### 4.3 `before_request` runs before view decorators

A blueprint's `before_request` hook executes **before** `@login_required` on the
view. Several blueprints do lazy `_ensure_tables()` DDL in `before_request`,
which means an **anonymous HTTP request drives `CREATE TABLE` / `ALTER TABLE`**.

Guard it with a module-level `_<bp>_ready` flag set only *after* `commit()`
succeeds. Per-gunicorn-worker flags are fine here — the DDL is `IF NOT EXISTS`,
so each worker ensuring once is idempotent. (Contrast with rate-limit counters,
which must **not** be per-worker; see §4.7.)

A related consequence: `@system_bp.before_app_request` lets a blueprint add
app-wide middleware without touching `app.py`, and it runs *before* `app.py`'s
own `_security_checks`, because blueprints are registered earlier in
`create_app`. That is how the restore maintenance gate and the
`request.max_content_length` bump for backup uploads work.

### 4.4 The i18n helper `t` is shadowable

Every bilingual string in the UI is `t('English', 'العربية')` — **4,410 call
sites across 169 templates**. `t` is not a Jinja filter or a real global; it is a
plain function injected by the context processor (`app.py:194`):

```python
def t(en, ar=""):
    return ar if (lang == "ar" and ar) else en
```

Because it lives in the template namespace, `{% for t in things %}` or
`{% set t = ... %}` **shadows it for the rest of the block** and every
subsequent `t(...)` call in that scope raises or misbehaves. There are currently
**0** occurrences (verified by AST-free regex scan of all 170 templates). Never
name a loop variable `t`. `item`, `row`, `tag` — anything else.

Two more i18n facts that waste an afternoon each:

- **UI language comes from `user['language']` first, then `session['lang']`**
  (`app.py:~183`). Setting `session['lang']='ar'` alone does nothing, because the
  user row defaults to `'en'`. To test RTL, set `session['user']['language']='ar'`,
  or hit `/settings/lang` which updates both.
- **`clinic.currency` is write-only.** EGP is hardcoded in roughly 235 places
  (186 templates, 49 Python files). The dropdown in Settings does nothing.

### 4.5 Arabic in PDFs needs three things, and Cairo has a hole in it

`models/pdf_generator.py` is the only place PDFs are produced. Arabic requires
all three of: the Cairo TTFs in `static/fonts/` (registered via `pdf.add_font`,
`:103`), `arabic-reshaper` (joins letters into positional forms), and
`python-bidi` (reorders RTL runs for a left-to-right renderer). Without them,
any Arabic — *including a clinic simply typing its own name into Settings* —
raises `FPDFUnicodeEncodingException`.

The trap: **`Cairo-*.ttf` lacks 54 of the Arabic Presentation Forms-B
codepoints — specifically the isolated forms.** Calling
`arabic_reshaper.reshape()` directly emits those isolated forms, and ordinary
letters (alef, dal, reh, yeh, teh marbuta) render as `notdef` boxes. The fix is
already in place at `pdf_generator.py:47` and must not be undone:

```python
arabic_reshaper.ArabicReshaper(
    configuration={'use_unshaped_instead_of_isolated': True})
```

Second trap: **you cannot grep a generated PDF for text.** fpdf2 compresses
content streams and re-encodes text as font-subset glyph ids, so
`b'ClinicName' in pdf_bytes` is `False` even when the name is visibly printed.
Every `cell()`/`multi_cell()` routes its text through `pdf_generator.ar()` —
monkeypatch *that* to observe what is actually drawn. See
`tests/test_branding.py::_spy_drawn` for the pattern.

### 4.6 Money is stored as binary float

**30 currency columns are `REAL`.** Exactly one — `inpatient_stays.daily_rate` —
is `NUMERIC(10,2)`. The affected columns include `amount`, `total`, `subtotal`,
`paid_amount`, `due_amount`, `discount`, `discount_amount`, `tax_amount`,
`unit_price`, `unit_cost`, `cost_price`, `sell_price`, `standard_price`,
`price_per_night`, `outstanding_balance`, `total_sales`, `total_expenses`.

The concrete failure this causes: an invoice paid in full stays marked
`"Partial"` forever, because the status test was `if due == 0` against a float.
Simulated over 200,000 invoices, this hit roughly **1 in 7** instalment-paid
invoices. The rounding fix **has been applied** —
`models/database.py:2847-2857` now rounds to 2dp and tests `due < 0.005`, and
`blueprints/petshop/routes.py:429-432` rounds its four POS values.

One recommended change did **not** land: `models/database.py:2776` in
`create_invoice()` still does
`subtotal = sum(float(l.get("total",0)) for l in lines)` without rounding.
Downstream discount/tax/total are rounded, so the residue is confined to the
stored `subtotal` column and any reconciliation query comparing it to
`SUM(invoice_lines.total)`. Low impact, but it is unfinished.

The full `REAL → NUMERIC(12,2)` migration is **written and deliberately not
released**: `db_migrations/versions/0002_money_numeric.py`. Read
`docs/MONEY_PRECISION.md` before you run it. The short reason to hold: the
migration touches 34 columns across 15 tables, ~550–800 call sites need review,
172 `float()` downcasts remain in the code, 261 templates display money raw and
would change appearance, and `models/excel_export.py:83,95,102` does
`isinstance(value, (int, float))` which **silently drops the Excel TOTAL row**
for a `Decimal`. Also: SQLite has no true decimal type, so `NUMERIC(12,2)` there
is a label, not a guarantee — which means your green test suite proves nothing
about this migration.

Related, and stricter: **clinical and dose data must never be stored as JSON
floats.** `blueprints/cds/drug_data.json` quotes every numeric as a string so
`Decimal(str)` is exact. `0.1 * 4.2` in binary float is `0.42000000000000004`.
Same reasoning as money, with physical consequences.

### 4.7 The rest of the trap list

- **Per-process state is a lie under gunicorn.** Rate-limit and lockout counters
  must live in the database. A module-level dict makes the effective threshold
  `MAX × N workers`, and a restart resets it. This was fixed; do not regress it.
- **CSRF field is `_csrf_token`, with the underscore.** `models/security.py`
  `validate_csrf()` reads only that name, the `X-CSRF-Token` header, or JSON
  `_csrf_token`. The wrong name gives a silent 403. `WTF_CSRF_ENABLED = False`
  in `TestConfig` does **not** disable it — `app.py:175` runs its own check. A
  test client must `GET /` after login to seed the token, read it via
  `models.security._CSRF_SESSION_KEY`, and post it on every write.
- **Two audit tables exist.** `audit_log` (singular, `database.py:499`) is
  **live**: written by `models.database.log_audit()` from ~25 call sites, read by
  the system UI, by `hr/routes.py`, and — load-bearing — by
  `blueprints/migration/routes.py` for idempotency. `audit_logs` (plural, `:1520`)
  is write-only, fed solely by the unregistered `api_v1`. They were deliberately
  not consolidated. Write new audit code against `audit_log` via `models/audit.py`.
- **A missing key in a Jinja dict lookup does not raise.** It yields `Undefined`,
  which survives until something forces it — typically `| tojson`, which then
  raises `TypeError: Object of type Undefined is not JSON serializable`. The
  traceback points at the filter, not the bad key.
- **A bare `except: pass` is hiding something.** 76 of them across 266 try blocks
  at last count; ~15 removed. Two production bugs were invisible for months
  behind them: `appointments` referenced a column that does not exist
  (`appt_time` — the column is `appt_start`), and `service_catalog.price` does not
  exist either (it is `standard_price`). A "PII leak" reported in the audit was
  never real because the query had never run at all.
- **Fixing one SQL bug unmasks the next.** Every petsy query was dying on a `%s`
  placeholder, so `_q1` always returned `None` and `or {}` covered a latent
  `.get()` on a `Row`. Converting to `?` made the queries succeed and the real
  `AttributeError` fire. After any "the SQL runs now" fix, **exercise the page**;
  do not just re-run the suite.
- **`html { overflow-x: clip }`, never `hidden`.** `hidden` creates a scroll
  container and breaks the `position:sticky` topbar; `clip` does not.
- **`.v3-main` / `.v3-content` need `min-width:0`.** They are flex items, so
  `min-width:auto` made every page as wide as its widest table. This is the first
  thing to check for any "the page scrolls sideways" report.
- **Do not hand-edit `static/css/app.min.css`.** Edit `tokens/icons/platform/
  aleefy/v3.css` and run `python static/css/build.py`, which also re-stamps
  `ASSET_V` in `base.html`. `build.py --check` verifies freshness (currently
  reports `build is current (v=cb571a99bb)`). Adding a new `<i class="bi bi-...">`
  without re-running the build renders nothing — the icon font is a 52-icon subset.
- **Do not write a stray `<` or `</` into template text.** `</` followed by a
  non-letter is an HTML5 *bogus comment* that runs to the next `>` and silently
  eats the following `</div>`. Jinja parses it fine; only the browser DOM shows
  the damage.
- **Arabic text from Excel carries invisible bidi marks** (U+200B–200F,
  U+202A–202E, U+2066–2069, U+FEFF). Left in, two visually identical names
  compare unequal and duplicate detection fails. `excel_import.clean_text()`
  strips and NFC-normalises them. Arabic CSV out of Windows Excel is **cp1256**,
  not UTF-8 — decode order `utf-8-sig → utf-8 → cp1256`; reverse that and every
  Arabic name mojibakes silently.

---

## 5. How to do common things

### 5.1 Add a route

Blueprints are `blueprints/<name>/__init__.py` (three lines) plus `routes.py`:

```python
# blueprints/imaging/__init__.py
from flask import Blueprint
imaging_bp = Blueprint("imaging", __name__, url_prefix="/imaging")
from . import routes          # noqa: E402 — must come last
```

Register it in `app.py::create_app` alongside the other 32. In `routes.py`:

```python
from . import imaging_bp
from blueprints.auth.routes import login_required, role_required
from models import database as db

@imaging_bp.route("/thing/<int:tid>")
@role_required("doctor", "nurse")          # super_admin bypasses automatically
def thing(tid):
    conn = db.get_db()                      # teardown hook closes it
    row = conn.execute(
        "SELECT * FROM things WHERE id=?", (tid,)   # ? — never %s
    ).fetchone()
    return render_template("imaging/thing.html", row=dict(row))
```

Use role names from the seeded 14 (§2.3) — `tests/test_role_consistency.py`
AST-scans `role_required(...)` calls and fails on an unknown name.

### 5.2 Add a table

Two systems coexist and you need to understand both.

**`init_db()` runs on every boot** and creates `_SCHEMA` if missing. **Alembic
in `db_migrations/` handles changes to databases that already exist.** A fresh
SQLite test database is built entirely by `init_db()` and never sees Alembic —
which is why a change made *only* as a migration is missing exactly where the
tests run. For a new table, add it to `_SCHEMA` **and** write the migration.

All Alembic commands need an explicit `-c`, run from the platform root:

```bash
alembic -c db_migrations/alembic.ini current    # which revision this DB is at
alembic -c db_migrations/alembic.ini history
alembic -c db_migrations/alembic.ini heads
```

`db_migrations/env.py` resolves the database URL with the *same* rules
`create_app` uses — `POSTGRES_DSN` if it matches the regex, else
`PLATFORM_DB_PATH`, else `<platform>/data/platform.db` — so the two can never
disagree. No credentials live in `alembic.ini`.

**There are deliberately TWO heads, and `upgrade head` correctly errors.**
Verified:

```
$ alembic -c db_migrations/alembic.ini heads
0002_audit_log_indexes (head)
0002_money_numeric (head)
```

Both descend from `0001_baseline`. This is a safety interlock, not a mistake:
`0002_audit_log_indexes` is safe to apply, `0002_money_numeric` is the deferred
money migration (§4.6) that must not run by accident. Upgrade the one you want
by name:

```bash
alembic -c db_migrations/alembic.ini upgrade 0002_audit_log_indexes
```

For an existing production database that `init_db()` already built, use
`stamp`, not `upgrade` — it writes the version row and executes no DDL:

```bash
alembic -c db_migrations/alembic.ini stamp 0001_baseline
```

Note: `MIGRATIONS.md` still says "Alembic is not yet in `requirements.txt`".
That is stale — `alembic>=1.13.0` is there. Fix the doc when you touch it.

### 5.3 Add a translated string

In a template, wrap it:

```jinja
{{ t('Save changes', 'حفظ التغييرات') }}
```

That is the whole mechanism — no `.po` files, no extraction step, no
`Flask-Babel`. The English is the key and the Arabic sits next to it. There is
no Python-side `t()`; strings produced in a view are English-only (verified: 0
`t(...)` call sites in `.py` files). If you need a translated string from Python,
pass both and let the template choose.

Do not name any variable in scope `t` (§4.4).

### 5.4 Generate a PDF

`models/pdf_generator.py` exposes three public generators, all returning `bytes`:

```python
generate_invoice_pdf(invoice, clinic=None)
generate_vaccination_certificate_pdf(vacc, pet, clinic=None)
generate_payslip_pdf(salary, clinic=None)
```

Pass the `clinic` dict from `db.get_clinic()` so branding is applied.
`_draw_clinic_brand()` is the single shared header for all three — deliberately
one helper, because three separate headers is exactly how two documents end up
branded and the third does not.

Any Arabic must go through `pdf_generator.ar()` (§4.5). To test what was drawn,
spy on `ar()`; do not grep the bytes.

The clinic logo lives in `clinic.logo_data` as a full
`data:image/png;base64,...` URI **in the database**, not on disk. That is
deliberate: `models/backup.py` archives the database only, so a filesystem logo
would survive a backup and vanish on restore. Cost of the choice: the blob is
inlined into every page that renders it, which is why uploads are capped at 2 MB,
magic-byte checked, downscaled to 400px and re-encoded PNG
(`blueprints/settings/routes.py::encode_logo`).

### 5.5 Add a permission

Two answers, because the system is half-migrated.

**What every route actually does today** — a hardcoded role list:

```python
@role_required("doctor", "nurse", "clinic_owner")
```

89 call sites. Add your role name to the list. Nothing else is consulted.

**What the RBAC engine offers** — `blueprints/auth/routes.py:181`:

```python
@permission_required("visits.edit", "doctor", "nurse")
```

It reads `roles.permissions_json` (a **flat JSON array of bare module keys**,
e.g. `["patients","appointments","invoicing"]` — module-level only, no
`module.action` granularity, though `has_permission` accepts the dotted form and
satisfies it from the module prefix). The 20 valid keys are
`db.ALL_PERMISSIONS` (`models/database.py:3179`): `patients, appointments,
visits, pharmacy, invoicing, inventory, procurement, reports, whatsapp, catalog,
grooming, boarding, hr, attendance, accounting, ai, system, backup, audit,
settings`.

Critical semantics: `_SEED_ROLES` inserts roles **without** `permissions_json`,
so every seeded role defaults to `'[]'`. `permission_required` therefore treats
"no usable data" as *fall back to the hardcoded role list*, never as "deny all".
Get that backwards during a rollout and every role is locked out on upgrade.
(`has_permission` used directly fails **closed** — that asymmetry is intentional
and documented in its docstring.)

To add a new permission key: add it to `ALL_PERMISSIONS`, and it appears
automatically as a checkbox in `templates/system/roles.html`.

### 5.6 Rebuild the CSS

```bash
python static/css/build.py            # rebuild + re-stamp ASSET_V in base.html
python static/css/build.py --check    # verify freshness (CI-friendly)
```

---

## 6. Running it for a customer

Do not improvise this. Two runbooks already exist and are the authority:

- **`platform/PROVISIONING.md`** — adding a clinic, secret handling, the
  directory layout under `/srv/aleefy`, upgrades and rollback.
- **`platform/deploy/BACKUP_RUNBOOK.md`** — backup and restore.

They are not duplicated here. What a new operator must understand *before*
touching a live clinic:

### 6.1 The app is multi-tenant, by database, not by column

**This section said the opposite until 2026-08-23, and the old advice would now
be wrong.** Multi-tenancy shipped: `models/tenancy.py` resolves a clinic from
the request subdomain and each clinic gets **its own database**.

Isolation is therefore *physical, not conditional*. The reason that matters, in
the module's own words: a missing `WHERE` cannot cross a database boundary,
because there is no connection to the other clinic's data in the first place.
Row-level `clinic_id` filtering — the approach this section previously assumed
would be needed — fails open the moment one query forgets its filter. This
fails closed.

What a new operator must know:

- **One clinic still equals one database.** That has not changed, and it is the
  design, not a limitation. What changed is that one *deployment* now serves
  many of them.
- **Migrations run per clinic.** `create_app()` migrates every registered
  clinic, not only the default one. A clinic added while the app was down still
  gets its schema on the next boot.
- **Sessions are tenant-scoped.** One `SECRET_KEY` signs every clinic's cookies,
  so `session['tenant']` is checked on every request. Without that check a
  cookie minted at clinic A authenticated against clinic B's database at clinic
  A's privilege level — this was found live and fixed, and it is the failure
  mode to keep in mind when touching auth.
- **Backups are tenant-scoped too** (`models/backup.py`, and
  `tests/test_backup_tenant_scope.py` proves it). N clinics means N backups to
  verify, not one.
- **An unknown subdomain 404s before any database is touched**, deliberately —
  see the comment in `app.py`'s `before_request`.

Covered by `tests/test_tenancy.py`, `tests/test_tenant_migrations.py`,
`tests/test_backup_tenant_scope.py` and `tests/test_unknown_subdomain.py`.

The 40–60 developer-day estimate that used to appear here, and in
`docs/market/05_PRODUCT_READINESS.md`, no longer applies.

### 6.2 Backups are the thing that will end you

- Backups are `sqlite3.Connection.backup()` for SQLite (`_sqlite_copy()`), never
  `shutil.copy2` — the database runs in WAL mode with live gunicorn connections
  and a byte copy of it is torn.
- PostgreSQL backups shell out to `pg_dump -Fc`. **`pg_dump` must be on the
  `PATH` of the process running the app.** If it is not, `models/backup.py:215`
  reports a clear failure — but it is a runtime dependency your container image
  must actually contain.
- "Last successful backup" is **derived from the newest archive on disk**, not
  stored in a table. That is deliberate: tracked state that can drift from the
  files it describes is exactly how "nightly backup OK" gets logged while no file
  exists.
- `/healthz` reports `degraded` when the backup is stale (§1.4). Wire your
  monitoring to it, but only after the first backup has run.
- Never validate a backup file with `PRAGMA integrity_check` alone — sqlite3
  opens a zero-byte path as a fresh empty database and reports "ok". Check size,
  the `SQLite format 3 ` magic, and a non-zero `sqlite_master` count.
- Generated archive names need a uniquifier beyond `%Y%m%d_%H%M%S`. Two archives
  in the same second collided once, and the pre-restore snapshot overwrote the
  archive being restored — the restore silently put back the data it was meant to
  replace.

### 6.3 Secrets are per-install and printed once

`scripts/provision/provision.sh` generates `PLATFORM_SECRET_KEY`,
`PLATFORM_ADMIN_PASS`, `POSTGRES_DSN`, `WAITING_ROOM_TOKEN` and `API_V1_KEY`
fresh per clinic from the CSPRNG, writes `.env` at mode 0600, and prints them
**once**. Capture them into a password manager immediately.

**Never redirect provisioning output to a file.** The seeded admin password has
been leaked to `startup.log` this way before; both log files are now deleted and
gitignored, and the print removed, but the failure mode is a redirection away.

### 6.4 Upgrades

`scripts/provision/upgrade.sh` and the `.upgrade-state` file per clinic. Read
`PROVISIONING.md`. There is no in-app update mechanism and no phone-home — every
upgrade is an SSH operation. At scale this is the single biggest operational cost
in the product, and `docs/market/05_PRODUCT_READINESS.md` estimates the fleet
tooling to fix it at ~15 developer-days.

---

## 7. What will bite you

Sources, in order of usefulness: `docs/AUDIT_AND_PLAN_2026-07-25.md` (21
numbered defects with file:line and a remediation-status table),
`docs/MONEY_PRECISION.md`, `docs/market/05_PRODUCT_READINESS.md`.

**Read the audit's remediation table, not just its findings.** Most P0s are
fixed. The document also self-corrects four of its own findings (D-01, D-11,
D-12, D-18) that turned out to be wrong or overstated, and states the reason:
"every error came from static pattern-matching, and every correction came from
executing the code." Apply the same standard to anything below that you have not
personally run.

**And note that `05_PRODUCT_READINESS.md` is partly superseded.** It is dated
2026-07-28 but several of its "ABSENT" verdicts have since shipped. Verified as
now working: Arabic PDF rendering (`pdf_generator.py` registers the Cairo TTFs
and reshapes), per-clinic branding (`base.html` references `clinic` 20 times),
a version string (`platform/VERSION` = 3.0.0, surfaced in `/healthz`),
PostgreSQL backup via `pg_dump`, the browser-based data-import wizard
(`blueprints/migration/routes.py`, no hardcoded path remains), and one-command
provisioning. Treat that document as a snapshot, not current state.

### 7.1 Outstanding — engineering

| | Status |
|---|---|
| **RBAC is decorative.** The Roles admin UI writes `permissions_json` that 89 of 91 protected routes never read. Editing permissions in the UI does essentially nothing. | D-05, outstanding. Engine built and fail-safe; the 379-route rollout is not done. |
| **76 bare `except: pass`** across 266 try blocks; ~15 removed. Each one can hide a live bug indefinitely (§4.7). | D-09, partial. |
| **Money as `REAL`** — 30 columns. Rounding fixes applied; the `NUMERIC` migration is written and deliberately unreleased. `create_invoice()` subtotal still unrounded. | §4.6. |
| **Hardcoded EGP** in ~235 places; `clinic.currency` is a lying setting. | `docs/MONEY_PRECISION.md`. |
| **PostgreSQL CI job is non-blocking** (`continue-on-error: true`) because `tests/test_postgres_full.py` calls `configure_postgres(dbname="vetclinic")` at **module scope with hardcoded credentials** — importing it points the whole suite at production. It is excluded from collection by `pytest_ignore_collect`. **The 549 green tests are SQLite-only and are not evidence about PostgreSQL.** | Live. |
| **`api_v1` (498 LOC) is unregistered dead code**, along with `models/logging_db.py`. `models/sync.py` is *not* dead — `blueprints/system/routes.py:14` imports from it. | Live. |
| **`run.py` still tries to spawn a Node `freellmapi` server** that is not in the deliverable. | Live, harmless. |
| **`blueprints/visits/routes.py:294`** INSERTs `created_by` into `prescriptions`, which has no such column, and the schema marks `pet_id`/`owner_id` NOT NULL. Read before assuming the prescribing flow works end to end. | Reported; not verified as fixed by me. |
| **`petsy` remains PostgreSQL-leaning** — `SUBSTRING(col::text,1,10)` and `ILIKE`. On SQLite those log and return empty: degraded, not crashed. | Live. |
| **`db.update_clinic()` is broken** — emits `%s` and `NOW()`, which the SQLite path cannot run. Write the UPDATE inline with `?` and `datetime('now')`. | Live. |
| **Clinic branding is cached 300s** under `clinic_row`. Any write to the clinic table must call `db.cache_invalidate('clinic_row')` or the change is invisible for five minutes. | Live. |
| **164 `datetime.utcnow()` deprecation warnings.** These become errors when the function is removed. | Scheduled maintenance. |

### 7.2 Outstanding — product

From `docs/market/05_PRODUCT_READINESS.md`, still absent at handover: multi-tenancy,
multi-branch (a `branch_id` exists on ~11 tables but is used only by HR), a
pet-owner portal (owners have no password, hash or token — authentication does
not exist at any level), online payments (zero code), SMS, offline/PWA support,
in-app help, licensing/activation/telemetry, and AI usage metering. Field-level
audit history exists in `audit_log.details` as JSON but the trail is
auth-event-centric.

### 7.3 The patient-safety one

`/ai/drug-interactions` (`blueprints/ai_assistant/routes.py:874`) is a pure-LLM
check with a **fail-open** default. On parse failure it returns
`severity: "unknown"`, and when `current_medications` is empty it returns
`safe: true` without asking anything. `templates/visits/visit_detail.html:1094`
paints anything not severe/moderate/mild as a green
"✅ No significant interactions found. Safe to prescribe." A vet reads that as
cleared.

Relatedly, the CDS module is deliberately non-blocking (`app.py:140-146`) because
its drug data is DRAFT. `docs/market/05_PRODUCT_READINESS.md` states it
explicitly: **never describe CDS as a safety check in sales material.**

Treat both as defects to fix before the product is in front of a prescribing
vet, not as features.

### 7.4 The WhatsApp integration is not the official API

`api.wapilot.net` is an **unofficial WhatsApp Web gateway**, not the Meta Cloud
API. It violates WhatsApp's terms of service and a clinic's number can be
banned. There are also two incompatible client variants in the tree
(`api.wapilot.net` and `api.wapilot.io`). Whether Wapilot fronts the official
Business API is **not verified**. Confirm before this appears on any price list.

---

## 8. First week, suggested order

1. Run §1.3 and §1.4 yourself. Do not accept this document's numbers.
2. Read `models/database.py` §3 top-to-bottom. Nothing else in the codebase
   makes sense until the two translation functions do.
3. Read `docs/AUDIT_AND_PLAN_2026-07-25.md` remediation table.
4. Rotate every credential in `05_ASSET_INVENTORY.md` §7 before you deploy
   anything.
5. Fix the PostgreSQL CI job (`tests/test_postgres_full.py` → honour
   `TEST_POSTGRES_DSN`, then drop `continue-on-error`). Until that is green you
   have no automated evidence about the database you actually ship on.
6. Decide on §7.3 before a vet uses it.
