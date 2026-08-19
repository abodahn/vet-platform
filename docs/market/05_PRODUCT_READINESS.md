# Aleefy — Commercial Readiness Audit

**Date:** 2026-07-28
**Scope:** `D:\vet\platform` — can this be sold to a paying Egyptian veterinary clinic, and what must be built first.
**Method:** Direct code inspection. Every claim below was verified by opening the file, running the code, or
executing a query. Where a thing could not be verified it is marked **not verified**. Nothing here is inferred
from a directory name — that mistake was made four times in the 2026-07-25 audit and is the reason this one
executes rather than greps.

**Builds on:** `docs/AUDIT_AND_PLAN_2026-07-25.md`, `platform/docs/MONEY_PRECISION.md`, `platform/MIGRATIONS.md`.
Defects already fixed there are not repeated. The engineering floor has genuinely been raised: 373 tests pass
(verified by running them, 98s), CI is wired, the app boots on SQLite with no PostgreSQL, connection leaks are
plugged, the invoice-rounding bug is fixed at `models/database.py:2847-2851` and `blueprints/petshop/routes.py:429-432`.

This report is about a different question: **not "is the code sound" but "can a stranger pay for this and be
glad they did."**

---

## 0. Executive summary

The product is real. 382 route definitions across 34 blueprints, 73 tables, deep domain logic — FEFO stock,
prescription→dispensing, attendance→payroll, POS→invoice. That is more veterinary ERP than most funded
competitors ship. **The features are not the problem.**

The problem is that everything *around* the features assumes exactly one clinic, run by the person who wrote it,
on a machine he can reach. There is no tenancy, no onboarding, no branding, no licensing, no update path, no
usable data import, no user documentation, and PDF generation crashes the moment anyone types Arabic into a
settings field. These are not polish items. They are the difference between software and a product.

**Three findings dominate everything else:**

1. **Single-tenant, definitively.** One deployment = one clinic. This is not a bug, but it is the fact that
   decides the business model, and it must be decided around rather than fixed. (§1.1)
2. **Arabic in any PDF is a hard failure, reachable in one keystroke.** Verified by execution. A Cairo clinic
   that types its own name in Arabic into Settings loses every invoice, vaccination certificate and payslip.
   (§2.5)
3. **Supporting 50 clinics with today's operational tooling is roughly 120 hours a month of pure reactive
   work.** There is no update mechanism, no fleet view, no error aggregation, and no version number. This is
   the thing that actually kills solo software businesses, and it is currently unmitigated. (§3)

**Sellable today: no.** Qualified answer and the single biggest blocker in the final section.

---

## 1. T1 — The "can you sell this on Monday" checklist

### 1.1 Multi-tenancy — **ABSENT. One deployment per clinic. Definitive.**

This is the answer that determines the business model, so here is the evidence rather than the conclusion.

**The `clinic` table is a hardcoded singleton.** `models/database.py:684` defines it. It is written in exactly
one place, `blueprints/system/routes.py:277`:

```sql
UPDATE clinic SET name=?, name_ar=?, ... WHERE id=1
```

`WHERE id=1`. Not `WHERE id = :current_clinic`. There is no route that creates a second clinic row, and
`models/database.py:2002` seeds one only if the count is zero.

**No table is scoped by tenant.** Grepping the entire Python tree for `clinic_id` returns **one** hit:
`models/database.py:701`, the column `branches.clinic_id INTEGER DEFAULT 1`. That column is never read, never
written, and never appears in a `WHERE` clause anywhere in the codebase. `tenant_id` and `organization_id`
return zero hits. Of the 73 tables, **zero** carry a tenant discriminator that is actually enforced.

`branch_id` exists on ~11 tables and is genuinely used — but only inside HR, for staff assignment
(`blueprints/hr/routes.py:354, 1278, 1290`). No clinical, financial, inventory or appointment query filters on
it. Multi-branch is not implemented either.

**Retrofitting it is not a weekend.** There is no ORM. `models/database.py` is a hand-rolled psycopg2/sqlite3
compatibility layer with raw SQL strings scattered across 34 blueprints — roughly 800 statements. SQLAlchemy
users retrofit tenancy with a global query filter hook; here there is no such hook and no place to put one.
Every `SELECT`, `INSERT` and `JOIN` would need a `clinic_id` predicate added by hand, and a single missed one is
a silent cross-clinic data leak in a system holding patient records. **Realistic effort: 40–60 developer-days,
with a high residual risk of leakage that no test suite would catch.**

**Consequence — accept it and design around it.** This is the right call, not a compromise:

- Sell it as **one container / one VM per clinic**, each with its own database and volume.
- Hosting cost is genuinely small: SQLite or a small Postgres per clinic; a €5–8/month VPS holds 5–10 clinics
  as separate containers. **Cost is not the problem — operations is.** See §3.
- The pricing model that follows is per-clinic hosted subscription, not seats-in-a-shared-SaaS.
- **What you must never do** is put two clinics in one database "temporarily." Nothing in the code would stop
  clinic A reading clinic B's patient records, and nothing would tell you it had happened.

### 1.2 Onboarding a new clinic — **ABSENT. Requires a developer, every time.**

Grep for `wizard`, `onboard`, `first_run`, `setup_wizard` across all `.py` and `.html`: **zero hits.**

What actually happens today to stand up a new clinic:

| Step | How it works now |
|---|---|
| Provision server | `deploy/deploy.sh`, run by hand over SSH |
| Create database | `db.init_db()` on boot, seeds admin + one clinic row |
| Clinic name / phone / address | `/system/settings` form — works, `blueprints/system/routes.py:269` |
| Logo | **impossible** (§1.7) |
| Services & price list | Manual entry, one row at a time, `/catalog` |
| Staff & roles | Manual entry, `/hr/staff` |
| Owners & pets | Manual entry, or the unusable import (§1.3) |

`deploy/deploy.sh` is worse than "requires a developer" — it is actively dangerous at scale. It hardcodes:

```bash
PLATFORM_DIR="/home/ahmed/vet/platform"
sudo -u postgres psql -c "CREATE USER vetapp WITH PASSWORD 'the previously-leaked admin password';"
echo "  Login:     admin / the previously-leaked admin password"
```

Every clinic deployed with this script gets **the same PostgreSQL password and the same admin password**, and
the script is committed to the repository. Customer #3 can read customer #7's database if they can reach it.
This is not a theoretical hardening item; it is a credential shared across your entire customer base, published.

The same hardcoding is in `deploy/vetplatform.service` (`User=ahmed`, `/home/ahmed/...`).

**Verdict: absent, and the one script that exists must be rewritten before the first customer, not the tenth.**

### 1.3 Data import — **EXISTS ON PAPER, UNUSABLE BY A NON-DEVELOPER, AND SILENTLY UNSAFE.**

Two implementations, both examined in full.

**`migrations/excel_import.py` (338 lines)** — a CLI script. `python migrations/excel_import.py --dry-run`.
It reads from a path fixed at line 30:

```python
LEGACY_DATA = Path(__file__).parent.parent.parent / "ppc_diagnostics_work" / "data"
```

That is *the author's own previous Flask app*. It also opens the database with bare `sqlite3.connect()`
(line 35) — **it cannot import into a PostgreSQL deployment at all.** A clinic owner cannot run it. It is a
one-time personal migration tool, correctly written for that purpose, and irrelevant to a customer.

**`blueprints/migration/routes.py` (445 lines)** — the in-app version, with a UI at `/migration/`. Three
disqualifying problems:

1. **Line 13:** `LEGACY_DATA_DIR = r"C:\vet\ppc_diagnostics_work\data"`. A hardcoded Windows path, on a Linux
   deployment. `index()` checks `os.path.isdir()` on it (line 79) and will always report "not found."
2. **There is no file upload.** Not "a clumsy upload" — none. The clinic cannot give you their spreadsheet
   through the app. Someone must place `owners.xlsx`, `pets.xlsx`, `bookings.xlsx`, `services.xlsx` on the
   server filesystem, at that exact path, with those exact filenames, and with the exact column headers of the
   *previous legacy app* (`owner_name`, `appointment_start`, `spayed_neutered`, `visit_temp_c`…). No column
   mapping UI exists. A clinic's own Excel will not have those headers.
3. **The pre-import backup silently never runs.** Line 133:
   ```python
   bk.run_backup(current_app.config.get("DATABASE_PATH", ""))
   ```
   `models/backup.py:28` is `def run_backup() -> dict:` — **zero parameters**. Every invocation raises
   `TypeError`, which is caught at line 134 into `report["backup_error"]` and rendered somewhere in the report
   template. So the destructive import runs with no backup, and the operator is told about it only in a corner
   of a results page they see *after* it finished. This is a live defect and should be logged.

There is a `dry_run` mode, which is genuinely good design. It cannot compensate for the above.

**What a real importer needs:** browser upload → sheet/column mapping UI → validation preview with row-level
errors → dry-run diff → commit, with a real backup taken first and a working rollback. **5 developer-days.**
Without it, *you* personally perform every customer migration, and a switching clinic — the only kind worth
selling to — is a multi-day manual job each time.

### 1.4 Backup and restore — **EXISTS. A clinic owner CANNOT safely operate it, and PostgreSQL has no backup at all.**

`models/backup.py` (206 lines), read in full. The good parts are real: it uses SQLite's online backup API
(`src.backup(dst)`, line 45) rather than a file copy, runs `PRAGMA integrity_check` on the result (line 78),
enforces 30-day retention, and `restore_backup()` takes a `pre_restore_*.db` safety snapshot before overwriting
(line 190). Someone thought about this. There is a UI at `/system/backup` with list / run / restore buttons
(`blueprints/system/routes.py:319-370`), and a nightly 02:00 job that notifies managers on failure
(`app.py:276-290`). That is more than most products this size have.

Four problems, in descending severity:

**(a) PostgreSQL is not backed up. At all.** `run_backup()` unconditionally calls `sqlite3.connect(_db_path)`.
`app.py:65` configures it with `app.config["DATABASE_PATH"]` regardless of whether PostgreSQL is in use.
`restore_backup()` at least detects this and refuses politely (line 158) — but `run_backup()` does not. On a
PostgreSQL deployment the nightly job either fails or produces a backup of a stale/empty SQLite file, and the
"Backup OK" log line and the green UI say everything is fine. **Your recommended production configuration is
the one with no backups.**

**(b) Backups live on the same disk as the database.** `app.py:64` puts `backups/` next to
`data/platform.db`. No off-site copy, no object storage, no rotation off the box. A disk failure, a bad
`rm -rf`, or ransomware takes the database and all 30 days of backups in one event. **This is the single most
likely path to total data loss at a customer site.**

**(c) Restore over a running application will corrupt the database.** `restore_backup()` does
`shutil.copy2(backup_path, _db_path)` (line 193) while gunicorn workers hold open connections to that exact
file. On Linux `copy2` truncates and rewrites in place — open connections observe a half-written database
mid-transaction. There is no maintenance mode, no worker quiesce, no advisory lock, no restart. The button is
in the UI, labelled "Restore", available to `clinic_owner`.

**(d) Can a non-technical person operate it?** Backup: yes, one button, and it works on SQLite. Restore: the
button exists and the flash messages are in plain English, so they will *press* it confidently — and that is
the problem. There is no confirmation step explaining that everything since the backup will be lost, no
downloadable copy they can hand to someone else, and no "test restore" that proves the backup is good without
destroying the live one. `docs/BACKUP_RESTORE_GUIDE.md` (137 lines) is Windows-`.bat`-flavoured, English-only,
and tells them to `copy` the file by hand — advice that does not apply to a hosted deployment.

**Verdict: partially exists. Safe for the author, not safe for a customer.**

### 1.5 Licensing / activation — **ABSENT. Confirmed.**

Grep for `license`, `licence`, `activation_key`, `subscription` across all `.py`: the only hits are the
`clinic.license_number` field (the clinic's *veterinary* licence, a text field on the settings page) and the
word "licensed" inside AI system prompts. There is no key check, no expiry, no activation, no phone-home, no
hardware binding, no version endpoint, no telemetry.

There is no version string anywhere in the codebase — `VERSION`, `__version__`, `app_version` all return zero
hits in `config.py`, `app.py`, `run.py`. (`api_v1` has a `/version` route, but that blueprint is not
registered — verified: `grep -c "blueprints.api_v1" app.py` → 0.)

**Consequence:** any self-hosted copy is a full, permanent, unlimited copy. A clinic owner who buys one licence
and runs a second branch on the same code is undetectable. So is a competitor who obtains a copy and resells it.
The `docker-compose.yml` makes duplication a two-command operation.

**The honest assessment:** licensing enforcement in self-hosted software is porous by nature — a signed licence
file with expiry and a heartbeat is ~4 developer-days and stops the casual copier, not a determined one. The
real answer is commercial, not technical: **host it yourself.** A hosted-only model makes the copying question
disappear, and it is also the only model under which §3's support numbers are survivable. If self-hosting must
be offered, price it as a much larger one-off and accept that you cannot police it.

### 1.6 Update / upgrade path — **ABSENT.**

`deploy/deploy.sh` is a first-install script — it runs `apt-get install`, creates the database and user,
installs the systemd unit, and configures nginx and ufw. There is no `update.sh`, no release tagging, no
`alembic upgrade` in any deployment script, no health-gated restart, no rollback.

Alembic itself is in place and correct (`platform/MIGRATIONS.md`, `db_migrations/`), which is the hard part —
but nothing calls it during a deployment. `app.py:53` still runs `db.init_db()` on every boot, which re-executes
the schema with `CREATE TABLE IF NOT EXISTS`; the Alembic revision is a parallel truth.

**What updating a deployed clinic looks like today:** SSH in, `git pull`, activate the venv, `pip install -r`,
`alembic -c db_migrations/alembic.ini upgrade head`, `systemctl restart vetplatform`, then log in and click
around to check nothing broke. 30–45 minutes if it goes well. If the migration fails halfway you are restoring
from a backup that may not exist (§1.4a). And because there is no version string, **you cannot tell which
version a given customer is running** without SSHing in and checking `git log`.

At 10 clinics that is a long evening per release. At 200 it is 133 hours of SSH.

### 1.7 Per-clinic branding — **ABSENT.**

The database has the column: `models/database.py:692`, `logo_data TEXT`. It is **never written and never read.**
Grep confirms zero references in any route or template.

`templates/system/settings.html` has no `<input type="file">` and no `enctype` — there is no upload field. The
POST handler at `blueprints/system/routes.py:277` does not touch `request.files`.

`templates/base.html` — the shell every one of the 158 templates extends — **never reads the `clinic` object at
all.** It hardcodes:

- line 71: `<img src="static/images/aleefy-logo.png" alt="Aleefy">`
- line 74: `<div class="v3-brand-name">Aleefy <span class="v3-brand-ar">اليفي</span></div>`
- line 12: `<title>… — Aleefy</title>`
- line 807: `Powered by Aleefy AI`
- line 13 and `templates/auth/two_factor.html:13`: favicon → `aleefy-logo.png`

So the clinic's own name appears **nowhere in the application UI**. Staff log into a product called Aleefy,
work in a product called Aleefy, and the clinic's identity appears only on printed documents.

On PDFs, the clinic name *is* used (`models/pdf_generator.py:60, 314, 495`) — and there it triggers §2.5.
`clinic.logo_data` is never rendered on a PDF either; the invoice header is a navy rectangle with text.

**Effort: 2 developer-days** — logo upload with the existing (genuinely good) upload validation in
`blueprints/uploads/routes.py`, a context processor injecting `clinic` into `base.html`, and
`pdf.image()` calls in the three generators.

### 1.8 User-facing documentation or help — **ABSENT in-app. Thin and mis-targeted out of app.**

Grep of `blueprints/` for a help, docs, guide or tutorial route: **zero.** No help route, no tooltips, no
onboarding tour, no empty-state guidance, no keyboard-shortcut reference.

What exists outside the app:

| Document | Lines | Audience | Problem |
|---|---|---|---|
| `docs/HANDOVER_GUIDE.md` | 182 | Admin | A table of module URLs. Addressed to "Dr. Hatem El Khateeb" by name. English only. |
| `docs/BACKUP_RESTORE_GUIDE.md` | 137 | Admin | Windows `.bat`, hardcoded `C:\vet\` paths. |
| `docs/README_PRODUCTION.md` | 128 | Developer | |
| `platform/docs/User_Guide_Operations_Manual_v1.0.docx` | — | Staff | **Not verified** — binary, not read. Generated by `docs/gen_user_guide.js`. |
| `platform/docs/HANDOVER.md` | 174 | Developer | |

**Nothing is in Arabic.** The receptionist and the nurse — the people who use this eight hours a day — will
work in Arabic and have no documentation in their language for a system with 34 modules. Nothing is written
for a clinic that is not the author's clinic.

---

## 2. T2 — The gaps that will lose deals

### 2.1 Mobile / tablet usability — **PARTIAL. The shell is responsive; the clinical screens are not.**

The app shell was built properly: `templates/base.html:9` has a correct viewport meta, and `static/css/v3.css`
has a real off-canvas drawer at `max-width: 768px` (`v3.css:1728-1736`) with an RTL variant. That part works.

Inside `.v3-content`, it falls apart. Findings, all with line references:

- **Only 3 media queries in the whole stylesheet stack actually fire** (`v3.css:1601`, `:1728`, `:1756`). The
  other ~10 target `.al-sidebar` / `.pf-layout` class names that no template uses — dead breakpoints from two
  superseded CSS generations. The "15 media queries" count is roughly double the truth.
- **`v3.css:65` sets `body.v3-body { overflow-x: hidden }`** while `.v3-content` has no `overflow-x: auto`.
  Content wider than the viewport is **clipped and unreachable**, not scrollable. That is strictly worse than a
  horizontal scrollbar.
- **118 `<table>` tags across 95 templates; 14 are inside a scroll wrapper.** `.v3-table-wrap` — the current-era
  wrapper with `overflow-x: auto` (`v3.css:1242`) — is used in **zero** templates. Combined with the point
  above, a 9-column inventory table on a 768px tablet loses its right-hand columns permanently.
- **`templates/visits/visit_detail.html` — the screen a vet lives in — has zero media queries in 1,114 lines.**
  Line 71 is an inline `grid-template-columns:300px 1fr`; line 490 is a six-column prescription editor
  (`2fr 1fr 1fr 1fr 1fr 1fr`); line 689 is a `width:400px` AI panel. On a phone the pet card takes 300 of 390
  pixels. Same story in `doctor/workspace.html:42` (`1fr 380px`) and `appointments/waiting_room.html:35`.
- **264 inline `grid-template-columns` across the templates; only 59 use `minmax()`. 80 of the 123 templates
  that use grid contain no media query at all.**
- **The 769–900px dead zone.** `base.html:1155` shows the hamburger at `innerWidth <= 900`, but the drawer CSS
  only exists at `max-width: 768px`, and the overlay rule `v3.css:96` is not media-gated. **An iPad Air in
  portrait is 820px.** Tapping the menu there drops a full-screen blurred overlay over the app while the
  sidebar collapses to a 64px rail. That is the single most common tablet width in the target market.
- **Touch targets: nothing reaches 40px.** `.v3-btn` is ~35px (`v3.css:1115-1121`), `.v3-btn-sm` ~26px
  (`:1168`), inputs ~35px (`:1214-1221`). Apple and Material both specify 44/48.
- **iOS zoom trap.** Every input is `font-size: 14px` (`v3.css:1220`). iOS Safari force-zooms on focus for
  anything under 16px. On an iPad, every tap into a field jerks the layout.
- **No PWA.** Zero hits for `manifest.json`, `serviceWorker`, `sw.js`, `apple-mobile-web-app`. There is an
  offline *banner* (`v3.css:851`) and a sync button (`base.html:383`) with no service worker behind them — it
  can detect offline, not survive it.

Some templates were done properly — `appointments/calendar.html`, `reception.html`, `crm/owner_detail.html`,
`crm/pet_detail.html` all collapse correctly. There is no shared responsive utility, so each author either
reinvented it or skipped it.

**Verdict: usable for looking things up on a tablet, not for entering things.** The five cheap fixes — 16px
inputs, 44px min-height, `overflow-x:auto` on `.v3-content`, change `900`→`768` in `base.html:1155`, wrap the
~104 bare tables — are ~2 days and remove most of the embarrassment. `visit_detail.html` is another ~2 days.

### 2.2 Pet-owner portal / mobile app — **ABSENT. ~5% of the designed app is backed by working API.**

`D:\vet\figma\` contains 26 PNG mockups (plus an identical `figma.zip`) — images only, no vectors or JSON, so
nothing is machine-consumable. They specify a **desktop-web** owner portal at 1440px, not a native app: top nav
`Home · Booking · Store · Hosting · Care · Shelters`, AR/EN toggle, cart, and a signed-in state ("Hi, Islam Magdi").

**Specified journeys:** owner signup/login; a 6-step booking wizard (specialty → appointment type incl. home
visit → date/time → pet selection → payment → QR check-in); an e-commerce store with cart and checkout; and a
12-item account sidebar — Dashboard (per-pet vitals tiles: HR, temp, BP, SpO2, BMI, glucose), My Appointments,
Favorites, Dependants (multi-pet CRUD), Medical Records (with prescriptions toggle and download), Wallet
(balance, saved cards, transaction ledger), Invoices, Messages (owner↔doctor), Vitals history, Settings.

**What the backend actually offers a client app:**

`/api/public/*` is registered (`app.py:122-123`), unauthenticated, CORS-open, IP rate-limited — 6 routes:
`GET /health`, `GET /services` (id, name, standard_price, category), `POST /book`, `POST /contact`,
`POST /emergency`, plus OPTIONS. `POST /book` finds-or-creates an owner by phone string, finds-or-creates a pet
by name, and inserts a `Pending` appointment. **No slot validation, no doctor availability, no payment, no
identity.** It is contact-form-grade lead capture.

`/api/v1/*` is **not registered** — verified, 0 occurrences of `blueprints.api_v1` in `app.py`. Its 12 routes
are ops telemetry (`/logs/*`, `/sync/*`, `/system/diagnostics`), zero owner resources. It is not a head start.

`/petsy/*` is the AI marketing chatbot, not the owner↔doctor inbox.

**The blocker: pet-owner authentication does not exist at any level.** The `owners` table
(`models/database.py:776-795`) has no password, no hash, no token, no verification column — it is a CRM contact
record. Zero hits platform-wide for `owner_session`, `owner_portal`, `owner_login`, `customer_login`,
`magic_link`, `client_portal`. Zero signup/register routes. Zero JWT. `session["user"]` is set in exactly one
place and always from the staff `users` table. The only bearer credential that exists is `API_V1_KEY`, which
maps to `super_admin` on an unmounted blueprint — handing that to a phone would give every pet owner full admin.

**14 of the 26 screens sit behind an account that cannot exist: 0% backed.** Booking is ~20% (services list
only). Store, wallet, invoices, messages, favorites: 0%, and wallet/messages/favorites have no tables either.

**The encouraging part:** the *data* exists — `visits.weight_kg/temp_c/heart_rate/respiratory_rate`,
`vaccinations`, `prescriptions`, `invoices`, `loyalty_points`. This is an auth-and-read-layer gap, not a
data-model gap. Owner identity by phone + OTP is the obvious fit (`owners.whatsapp_phone` and a WhatsApp sender
both already exist) — **~5 days** for that, then **25–40 days** for the portal itself.

### 2.3 Online payments — **ABSENT. Zero code.**

Grep for `paymob`, `fawry`, `stripe`, `paypal`, `payment_gateway`, `checkout_url` across `.py` and `.html`:
the only hits are the *strings* `"Stripe_Secret_Key"` inside `models/audit.py:51` (a redaction list) and
`tests/test_audit.py:121`. No gateway, no webhook handler, no payment intent, no reconciliation.

Payments today are recorded manually after the fact — `payments` table, cashier enters method and amount.
Which is fine for a front desk, and useless for the invoice link in a WhatsApp reminder or the wallet screen in
the Figma designs.

**Paymob is the correct choice for Egypt** (card + Vodafone Cash + Fawry references, local settlement).
**~8 developer-days** for hosted checkout + webhook + reconciliation into `payments` — but it is only
*valuable* after an owner portal exists to spend it in. Priority accordingly.

### 2.4 SMS / WhatsApp reminders — **PARTIAL, AND ONE PART ACTIVELY LIES TO THE CUSTOMER.**

**SMS: absent.** Zero hits for `twilio`, `send_sms`, `sms_gateway`, `vodafone`.

**WhatsApp: two incompatible implementations that do not agree with each other.**

*Implementation A — the interactive module.* `blueprints/whatsapp/wapilot.py`, a well-written client for
`https://api.wapilot.net/api/v2` with a `token:` header. 58 routes in `blueprints/whatsapp/routes.py` — instance
management, templates, campaigns, logs. This is what the UI drives.

*Implementation B — the automated reminders.* `blueprints/whatsapp/scheduler.py:_send_whatsapp` posts to
`https://api.wapilot.io/send` with `Authorization: Bearer`, reading `WAPILOT_TOKEN` from the environment.
**Different domain, different path, different auth scheme.** One of these two is wrong; they cannot both be
right. The scheduler version is the one that runs the daily 09:00 job, i.e. the one customers depend on.

**And it lies when unconfigured.** `blueprints/whatsapp/scheduler.py:51-52`:

```python
else:
    status = "Sent"   # stub mode — logged as sent
```

When `WAPILOT_TOKEN` is not set — which is the default, and which is what happens if a clinic never completes
WhatsApp setup — **every reminder is written to `whatsapp_log` with status `Sent`.** The clinic's WhatsApp
dashboard shows a green column of successfully delivered reminders. Nothing was sent. Owners do not show up,
the clinic does not know why, and the system tells them everything is fine. This is a defect that destroys trust
the first time it is discovered, and it is a one-line fix (`status = "Skipped (not configured)"`).

**Dedup has a race.** `_already_sent()` does a SELECT-then-INSERT against `reminder_runs` with **no unique
index** (verified: no UNIQUE constraint on that table in `models/database.py:1606`). Combined with the next
point, that matters.

**The scheduler runs in every gunicorn worker.** `_start_scheduler(app, backup_dir)` is called inside
`create_app()` (`app.py:157`) with no worker guard, and `gunicorn.conf.py:20` sets
`workers = (cpu_count() * 2) + 1`. On a 4-core box that is **9 schedulers**: 9 simultaneous nightly backups at
02:00, and 9 reminder runs at 09:00 racing on an unindexed dedup check. Duplicate WhatsApp messages to owners
are the visible symptom; nine concurrent SQLite backup handles are the invisible one.

**One more risk worth naming:** Wapilot is an unofficial WhatsApp automation gateway. WhatsApp bans numbers used
this way, and it happens without warning. Selling "WhatsApp reminders" as a headline feature on top of an
unofficial gateway means the feature can disappear for a customer overnight through no fault of yours. The
official WhatsApp Business Cloud API with approved message templates is the durable answer. **Not verified:**
whether Wapilot is itself a Business-API reseller — worth confirming before it goes on a price list.

### 2.5 Printing and PDFs — **EXISTS FOR ENGLISH. ARABIC IS A HARD FAILURE, VERIFIED BY EXECUTION.**

`models/pdf_generator.py` (671 lines) produces three documents, and they are genuinely well designed — coloured
header bands, status badges, line-item tables, totals blocks, payment history, signature lines:

- `generate_invoice_pdf` → `blueprints/finance/routes.py:513`
- `generate_vaccination_certificate_pdf` → `blueprints/clinical/routes.py:318`
- `generate_payslip_pdf` → `blueprints/payroll/routes.py:578`

**Prescriptions: no PDF.** **Labels (cage cards, medication labels): no code at all.** Grep found no label
generator.

**The Arabic problem.** Every one of the ~200 text calls in that file uses the built-in font:
`self.set_font("Helvetica", ...)`. There is **not a single `add_font()` call anywhere in the codebase**
(verified by grep). fpdf2's core Helvetica is Latin-1 only. `static/fonts/` contains Cairo and DM Sans, but as
**`.woff2`** — a web font format fpdf2 cannot load; it needs TTF/OTF. There is no `arabic_reshaper` and no
`python-bidi` in `requirements.txt` — the two libraries that do Arabic letter-joining and bidirectional
reordering, without which Arabic renders as disconnected, backwards letters even *with* a correct font.

**Tested, not assumed.** Running `generate_invoice_pdf` with an Arabic clinic name and Arabic line items:

```
fpdf.errors.FPDFUnicodeEncodingException: Character "\u0639" at index 0 in text is
outside the range of characters supported by the font used: "helveticaB".
Please consider using a Unicode font.
```

It fails at `pdf.add_page()` → `header()` → line 61 — **on the clinic name, before a single line item is
rendered.** The route catches it (`blueprints/finance/routes.py:523`) and flashes
`"PDF generation failed: Character \u0639 …"`, so it is not an HTTP 500 — it is a Python traceback fragment
shown to a receptionist, and no invoice.

**Blast radius.** The trigger is one field: a clinic typing its own name in Arabic at `/system/settings`. That
is not an edge case in Cairo — it is the default behaviour. The moment they do, **every invoice, every
vaccination certificate, and every payslip stops working**, including for their English-named customers,
because the failure is in the shared header. Arabic owner names, Arabic pet names, and Arabic service
descriptions each break it independently.

**A vaccination certificate is a document owners take to travel authorities and boarding facilities.** It is one
of the few outputs a clinic will genuinely judge you on in a demo, and it cannot render the name of the clinic
issuing it.

**Fix: 3 developer-days.** Ship an Arabic-capable TTF (Cairo or Amiri, ~400KB, embed with
`add_font(..., uni=True)`), add `arabic-reshaper` + `python-bidi`, wrap every text call in a
`_shape(text)` helper, and flip alignment to right for RTL runs. The bulk of the effort is not the font — it is
retrofitting ~200 `cell()` calls where a mixed LTR/RTL layout has to stay visually correct, plus visual QA on
all three documents in both languages.

### 2.6 Offline operation — **ABSENT on the client. Half-built plumbing on the server.**

There is a `sync_queue` table (`models/database.py:1788-1812`), a `models/sync.py` engine, and
`POST /api/v1/sync/push` — but **`api_v1` is not registered**, so all of it is dead code (this is D-12 from the
prior audit, still open).

On the client there is nothing: no service worker, no `manifest.json`, no IndexedDB, no cache strategy. Verified
by grep across `templates/` and `static/js/`. There is an offline *banner* CSS class and a sync button in the
UI that have nothing behind them — the app can tell you it is offline, and then do nothing about it.

**The honest recommendation: do not build this.** A true offline-first PWA with a write queue and conflict
resolution on a 34-module ERP is 15+ developer-days and a permanent source of "my data disappeared" support
calls — the worst possible category. For an Egyptian clinic the cheaper and more reliable answer is
infrastructure: a UPS, a 4G failover dongle, and — if the clinic is genuinely on bad internet — a local
on-premise install that syncs nothing. Sell that as an option instead. Revisit offline only when a specific
customer's connectivity is provably the thing blocking a sale.

---

## 3. T3 — Support and operational load for one person

This is the section that decides whether the business survives, so the numbers are built up rather than asserted.
They describe **the current state**, with no fleet tooling. §3.4 shows what changes with it.

### 3.1 The per-clinic cost drivers, today

| Activity | Frequency | Hours, today | Why |
|---|---|---|---|
| Onboard a new clinic | once | **8–12 h** | Manual provision, then hand-entering services, price list, staff, roles; data migration done personally (§1.3) |
| Apply a release | per release | **0.5–0.75 h** | SSH, pull, pip, alembic, restart, click-test. No script, no rollback (§1.6) |
| A release that goes wrong | ~1 in 8 | **+2–3 h** | Restore from a backup that may not exist on Postgres (§1.4a) |
| "It broke" call | ~1.5 /clinic /month | **0.5–1 h each** | No Sentry (`SENTRY_DSN` unset, `sentry-sdk` commented out of `requirements.txt:50`), no version string, no remote log access — so every diagnosis starts with a phone call and an SSH session |
| Backup / restore request | ~0.2 /clinic /month | **1 h** | Manual; restore is unsafe to run live (§1.4c) |
| Data question ("where did this number come from") | ~0.3 /clinic /month | **0.5 h** | |

### 3.2 The three scenarios

**10 clinics — feasible part-time, ~30 h/month.**
Steady state ≈ 10 × (1.5 × 0.75 h support + 0.2 h backups + 0.15 h data) ≈ 14 h/month, plus one release night at
10 × 0.6 h ≈ 6 h, plus ~1 onboarding at 10 h. **~30 h/month.** One person can do this alongside development,
and will personally know every customer. This is the comfortable zone and it lasts about a year.

**50 clinics — a full-time job with no development happening, ~120 h/month.**
Support ≈ 50 × 1.5 ≈ 75 h/month. One release ≈ 50 × 0.6 = 30 h, i.e. **an entire week of SSH per release**, so
releases become quarterly, so bugs live longer, so support rises. Onboarding 2/month ≈ 20 h. **~125 h/month.**
That is 0.75 FTE of pure reaction. Development stops. The failure mode is not dramatic — it is that you never
ship anything again, competitors do, and churn starts.

**200 clinics — impossible solo, ~400+ h/month.**
Support alone ≈ 300 h/month. A single release is **133 hours of SSH**, which means you stop releasing, which
means a security fix cannot be deployed. **200 clinics × 30-day backup retention with no off-site copy** is a
statistical certainty of at least one total data loss per year (§5.1). This is 2.5–3 FTE of support and it
arrives before the revenue does.

### 3.3 The thing that breaks first

Not support calls — **updates**. Support scales linearly and unpleasantly; updates scale linearly and become
*impossible*, because a release is one indivisible block of work you cannot spread across the month. The moment
a release takes more than a weekend, you stop doing them, and everything downstream degrades.

The second thing to break is **backups**, silently, because there is no alerting on a *missing* backup — only
on a *failed* one (`app.py:280`). A clinic whose scheduler died three weeks ago looks identical to a healthy one.

### 3.4 What the numbers become with fleet tooling

The investment is roughly **15 developer-days**: one-command update with health-gate and rollback (4 d), a fleet
dashboard showing every clinic's version / last backup / last error (5 d), automated off-site backup with
missing-backup alerting (3 d), Sentry wired and a version string (1 d), and remote log access (2 d).

With that in place, per-clinic monthly load drops to roughly 0.4–0.5 h:

| Fleet size | Today | With fleet tooling |
|---|---|---|
| 10 | ~30 h/month | ~10 h/month |
| 50 | ~125 h/month | ~30 h/month |
| 200 | ~400 h/month | ~110 h/month (needs one hire) |

**Those 15 days are the highest-leverage engineering in this entire document.** They are worth more than any
feature, and they should be built before customer 10 — not because customer 10 demands them, but because
customer 30 arrives before you have time to build them retroactively.

---

## 4. T4 — The minimum credible commercial release

Ruthlessly prioritised. Effort in developer-days, with reasoning. "Days" means focused days by someone who knows
this codebase.

### 4.1 MUST HAVE before the first paying customer — **~25 developer-days (≈5 weeks solo)**

| # | Item | Days | Why required / what breaks without it |
|---|---|---|---|
| 1 | **Arabic in PDFs** (TTF embed + reshaper + bidi + retrofit 3 generators) | 3 | §2.5. One settings keystroke destroys all invoices, certificates and payslips. Verified by execution. Non-negotiable in an Arabic market. |
| 2 | **Data import a clinic can run** (upload, column mapping, validation preview, dry-run diff, real backup first) | 5 | §1.3. Without it you personally do every migration, and a switching clinic — the only kind worth having — is a multi-day manual job. Also fixes the `run_backup()` TypeError that silently skips the pre-import backup. |
| 3 | **Backup for PostgreSQL + off-site copy + missing-backup alert** | 3 | §1.4a/b. Today the recommended production configuration has *no backups*, and where backups exist they die with the disk. This is the difference between a bad week and a destroyed clinic. |
| 4 | **Safe restore** (maintenance mode, quiesce workers, confirm-with-consequences, downloadable copy) | 1.5 | §1.4c. The button is in the UI, available to `clinic_owner`, and will corrupt a live database. |
| 5 | **Repeatable provisioning with unique per-install secrets** | 3 | §1.2. `deploy.sh` currently ships one admin password and one DB password to every customer, in a committed file. |
| 6 | **Per-clinic branding** (logo upload, clinic name in shell and on PDFs) | 2 | §1.7. Staff currently log into a product with someone else's name on it. Cheap, and it is the first thing seen in a demo. |
| 7 | **Tablet: the five cheap fixes** (16px inputs, 44px targets, `overflow-x:auto`, hamburger breakpoint 900→768, wrap ~104 tables) | 2 | §2.1. An 820px iPad — the most common tablet in the market — currently throws a blocking overlay when you tap the menu, and wide tables are clipped unreachably. |
| 8 | **`visit_detail.html` responsive** | 2 | §2.1. The screen a vet spends the day in, unusable on the device they hold. |
| 9 | **WhatsApp: stop the stub-mode lie; reconcile the two clients** | 1.5 | §2.4. `status = "Sent"` when nothing was sent is a trust-destroying defect. Two clients pointing at two different API hosts means one is dead. |
| 10 | **One scheduler, not one per worker** | 0.5 | §2.4. 9 concurrent nightly backups and racing duplicate reminders on a 4-core box. |
| 11 | **Sentry wired + a version string + `/health` reporting it** | 1 | §3.1. Without these, every support call starts with an SSH session. Cheapest support-cost reduction available. |
| 12 | **Cap the public AI endpoint** (`/petsy/chat` message length + off by default) | 0.5 | §5.6. Unauthenticated, burns your API key, no length limit. |
| | **Total** | **~25** | |

**Explicitly NOT in this list, and why:**
- *Multi-tenancy* — 40–60 days, high leak risk, and the business model works without it (§1.1).
- *Licensing* — customer 1 will not copy it; solve it commercially by hosting (§1.5).
- *RBAC rollout* — the Roles screen lies today, but at one customer you know the staff. Not at ten.
- *Owner portal, payments, offline* — none of these lose you customer 1.

### 4.2 MUST HAVE before customer 10 — **~35 developer-days**

| # | Item | Days | Why by customer 10 |
|---|---|---|---|
| 1 | **Fleet tooling**: one-command update with health-gate and rollback; fleet dashboard (version / last backup / last error per clinic); remote log access | 11 | §3.4. The single highest-leverage work in this document. Without it, releases stop happening somewhere between 20 and 40 customers, and everything degrades from there. |
| 2 | **RBAC rollout** — `permission_required` is implemented (`blueprints/auth/routes.py:181`) but applied to **2 routes**. 82 still use hardcoded `@role_required` role-name lists. | 6 | §1 note. The Roles editor tells an administrator they have restricted access when they have not. At ten customers, someone discovers a receptionist can open payroll. That is a breach conversation, not a bug report. |
| 3 | **Arabic UI completion** — `t()` is used in 24 of 166 templates; ~3,723 hardcoded English strings remain (per the prior audit, partially addressed) | 12 | Arabic-first staff cannot use 85% of the screens in their own language. Survivable when your customers are friends; not when they are strangers. Scope to the daily-driver screens first. |
| 4 | **Money migration** (`|money` filter + Decimal JSON provider + `excel_export.py` isinstance fix, *then* `NUMERIC(12,2)`) | 8 | `platform/docs/MONEY_PRECISION.md` — the plan is written and tested. Do it in the order that document specifies, at the PostgreSQL cutover. |
| 5 | **Make the PostgreSQL CI job blocking** (`.github/workflows/ci.yml` currently `continue-on-error: true`; `tests/test_postgres_full.py` targets a hardcoded database) | 2 | Tests run on SQLite; production runs PostgreSQL. Green tests are currently not evidence about production. |
| 6 | **User documentation in Arabic**, in-app help for the top 6 screens | 4 | Every hour of documentation is roughly 20 support calls avoided at this scale. |
| 7 | **Licensing** — signed licence file with expiry + heartbeat, graceful degrade | 4 (optional) | Only if self-hosting is sold. If everything is hosted, skip entirely. |

### 4.3 CAN WAIT

| Item | Days | When it becomes worth it |
|---|---|---|
| **Pet-owner auth** (phone + OTP over the existing WhatsApp sender) | 5 | The prerequisite for everything below. Cheap, and it unlocks the whole Figma set. |
| **Owner portal** (the 26 designed screens, or a credible subset) | 25–40 | When you have 20+ clinics and need a differentiator. Highest-ROI *feature* on the list — but only after §4.1 and §4.2. |
| **Online payments** (Paymob) | 8 | Only after the portal exists to spend it in. Before that it is a payment button with nowhere to sit. |
| **True offline / PWA** | 15+ | Probably never (§2.6). Sell a UPS and a 4G dongle instead. Revisit only when a named customer's connectivity provably blocks a sale. |
| **Multi-branch scoping** (real `branch_id` enforcement) | 12 | When you have a chain prospect. Not before. |
| **Lab machine integration** (IDEXX etc.) | 10+ | Asked about in demos, rarely decisive at the price point Egyptian single-site clinics pay. |
| **Multi-tenancy retrofit** | 40–60 | Almost certainly never (§1.1). One container per clinic is the correct architecture for this business. |
| **Label printing, prescription PDFs** | 3 | Genuinely useful, genuinely not a blocker. |
| **Clinical decision support wiring** | 5 | `blueprints/cds/` exists and is deliberately non-blocking because its drug data is marked DRAFT (`app.py:140-146`). That was the right call. Gate on data review, not on code. |

---

## 5. T5 — Honest risk register

Ordered by expected damage, not probability.

### 5.1 Data loss at a customer site — **HIGH probability, CATASTROPHIC impact**

Three independent paths, all live:

1. **PostgreSQL deployments have no backup.** `run_backup()` is SQLite-only (§1.4a). The nightly job reports
   success. Nobody finds out until they need a restore.
2. **Backups sit on the same disk as the database** (§1.4b). One disk failure, one bad `rm`, one ransomware
   event takes the database and all 30 days of history together.
3. **The Restore button corrupts a live database** (§1.4c) — `shutil.copy2` over an open SQLite file with
   gunicorn workers connected, no maintenance mode.

Add: no alert fires when backups simply *stop* (only when one fails), and no restore has ever been tested
end-to-end at a customer site.

*Impact:* a veterinary clinic that loses its patient records loses its practice. It is also the end of the
product's reputation in a market where every clinic owner in Cairo knows every other one.

*Mitigation:* §4.1 items 3 and 4 (4.5 days). **Nothing should be sold before these are done.** Then: a monthly
restore drill on a throwaway copy, and a monitored "no backup in 36h" alert.

### 5.2 A wrong clinical or financial number reaching a patient record — **MEDIUM probability, SEVERE impact**

The invoice-status rounding bug is fixed (`models/database.py:2847-2851`) and the POS is rounded
(`blueprints/petshop/routes.py:429-432`). Good. What remains:

- **All money is still stored as `REAL`.** 34 columns across 15 tables. `MONEY_PRECISION.md` correctly argues
  against migrating yet, and correctly warns that **your tests run on SQLite where the failure mode does not
  exist.** A migration done under production pressure is how this becomes an incident.
- **`clinic.currency` is write-only.** The settings page offers six currencies and says they are "Used on
  invoices and financial reports." **Nothing in the application reads it.** `EGP` is hardcoded in 186 templates
  and 49 Python files. A clinic that selects USD sees EGP everywhere. That is a settings screen that lies about
  money.
- **Clinical decision support is deliberately non-blocking** (`app.py:140-146`) because its drug data is DRAFT.
  That is the correct and honest call — but it means dosage and interaction checking is a reference page, not a
  safety net, and it must never be *marketed* as one.
- **The audit trail covers auth events only.** The prior audit noted this and it is unchanged: there is no
  field-level before/after on clinical or financial records. When a number is wrong, you cannot prove who
  changed it or what it was.

*Mitigation:* follow `MONEY_PRECISION.md`'s ordering exactly (filter → templates → migration, at the PostgreSQL
cutover). Either make `clinic.currency` work or delete the dropdown — a lying setting is worse than a missing
one. Never describe CDS as a safety check in sales material.

### 5.3 One person as the single point of failure — **CERTAIN, and it compounds**

There is no second person who can deploy, restore, or diagnose this system. There is no runbook that a stranger
could follow — `docs/HANDOVER_GUIDE.md` is a URL table addressed to a named doctor. There is no version string,
so even a competent contractor could not tell what a customer is running.

The compounding part: **every item in §4.1 that is skipped increases the amount of context that lives only in
one head.** Manual provisioning, manual migration, manual updates, manual diagnosis — each is a task that
cannot be delegated because it has never been written down.

*Impact:* an illness, a family emergency, or simply a two-week holiday becomes a customer-visible outage across
the whole fleet.

*Mitigation:* the §4.2 fleet tooling is also the documentation — a script that provisions a clinic *is* the
runbook. Beyond that: an operational runbook a stranger could execute, credentials in a shared vault with a
trusted second party, and a named contractor who has deployed it at least once. This is a business risk with an
engineering fix, and it is chronically underweighted by solo founders.

### 5.4 A customer copying the software — **MEDIUM probability, MODERATE impact**

Confirmed absent: no licensing, no activation, no phone-home, no version endpoint (§1.5). `docker-compose.yml`
makes duplication two commands. A self-hosted clinic can run a second branch free, or hand the code to a friend.

*Realistic assessment:* the loss is mostly *upside* rather than revenue you had — the second branch was probably
never going to pay separately. The real damage is a competitor obtaining a copy and undercutting you with your
own product, and unsupported copies in the wild damaging the brand.

*Mitigation, in order of effectiveness:* **host it yourself** (removes the risk entirely and is required by
§3.4 anyway); a contract with a per-site clause; and only as a distant third, 4 days of licence-file
enforcement that a determined copier defeats in an afternoon.

### 5.5 Support load exceeding available hours — **HIGH probability, EXISTENTIAL**

§3 quantifies it: 50 clinics is ~125 h/month today, which is a full-time job with zero development. The specific
mechanism is that **updates become indivisible and therefore impossible** (§3.3), after which security fixes
cannot be deployed and every other risk in this register gets worse simultaneously.

*The trap:* support load grows linearly with customers, but the *tooling* to reduce it only gets built when you
have spare time — which is exactly what growth removes. By the time it hurts, you cannot afford to fix it.

*Mitigation:* build the §4.2 fleet tooling at customer 5–10, when it feels premature. It is the only item in
this document where being early is the whole point.

### 5.6 AI features costing more than the subscription — **MEDIUM probability, MODERATE impact, and one live abuse vector**

- **`POST /petsy/chat` is public and unauthenticated** (`blueprints/petsy/routes.py:649-650`) and calls the LLM
  on your API key. Its only defence is `_allow(ip)` — 15 requests per 60 seconds, held in a **per-process
  in-memory dict** (`petsy/routes.py:30-40`). With 9 gunicorn workers the real limit is ~135/min, and it resets
  on every restart, and rotating IPs defeat it entirely.
- **There is no message-length limit on that endpoint.** `ai_assistant` has one (`routes.py:348`); petsy does
  not. `MAX_CONTENT_LENGTH` is 16 MB (`app.py:154`). A single request can push a very large prompt.
- **There is no metering of any kind.** Zero hits for `tokens_used`, `ai_usage`, or cost tracking anywhere. You
  cannot tell which clinic spent what, cannot cap a clinic, and cannot detect abuse until the provider bill
  arrives.
- **Imaging retries across four vision models** (`blueprints/imaging/routes.py:26`) — a failing image burns
  tokens on each attempt.
- **One shared `AI_API_KEY`** across all installs (`.env`), so cost is unattributable by construction.

*Impact:* a single discovered public endpoint can generate a bill larger than a month of subscriptions across
the entire customer base, with no way to identify the source.

*Mitigation:* the §4.1 item-12 cap (0.5 days) stops the bleeding. Then: per-clinic API keys or a metered proxy,
a hard monthly token budget per clinic with graceful degradation, and usage logged per request so AI can be
priced as a tier rather than absorbed.

### 5.7 Additional risks worth naming

- **WhatsApp number bans.** Wapilot is an unofficial gateway; WhatsApp bans numbers used this way without
  warning. A headline feature can vanish for a customer overnight. *Not verified* whether Wapilot fronts the
  official Business API — confirm before it appears on a price list.
- **The public booking API is open to abuse.** `POST /api/public/book` is unauthenticated with CORS defaulting
  to `*`, and it **creates owner and pet rows** by find-or-create on a phone string. A bot can pollute a
  clinic's CRM with thousands of fake owners and pets. IP rate-limiting is the only control.
- **A stale `.env` in the repository directory.** `.env`, `.env.development` and `.env.production` all live in
  the app directory. They are gitignored now, but the API key rotation owed from D-21 of the prior audit is
  marked **"rotation still owed by owner"** and has not been confirmed done. *Not verified.*

---

## Is this sellable today?

**No.**

Not "no, it needs polish" — no in the specific sense that a paying clinic would encounter a
product-destroying failure within their first week, and you would have no way to diagnose it, no reliable way to
restore from it, and no way to ship them the fix.

The product underneath is genuinely strong. 373 tests pass, the domain logic is deeper than most funded
competitors', and the 2026-07-25 remediation raised the engineering floor substantially. **This is a
five-week problem, not a rebuild.** The ~25 developer-days in §4.1 produce something you can sell without
embarrassment.

**The single biggest blocker: there is no dependable path from a customer's data to a restored copy of it.**

PostgreSQL deployments have no backup at all (`run_backup()` is SQLite-only, and reports success anyway).
Where backups exist, they sit on the same disk as the database. The Restore button will corrupt a live
database. And the one destructive operation that *does* try to back up first — the data import — calls
`run_backup()` with an argument the function does not accept, so it throws `TypeError` on every invocation and
imports with no backup at all.

Every other item in this document is a lost deal, a bad demo, or an expensive month. That one is a clinic
losing its patient records, permanently, with your name on the software. Fix §4.1 items 3 and 4 — four and a
half days — before any money changes hands. Then fix the Arabic PDFs, because the first clinic that types its
own name into the settings page will discover it on day one.

**Runner-up blocker, and the one to fix before you enjoy any success:** there is no way to update a deployed
clinic without SSH. That is a long evening at 10 customers, a full week at 50, and impossible at 200 — and it
is the mechanism through which every other risk in §5 eventually becomes unfixable.

---

*Note on scope: as instructed, nothing under `platform/` was modified — this audit is read-only. Per the
project's OpenWolf protocol, `.wolf/memory.md`, `.wolf/anatomy.md`, `.wolf/cerebrum.md` and `.wolf/buglog.json`
would normally be updated after work like this; that was deliberately skipped because the task restricted writes
to this file alone. Three defects found here are worth logging to `.wolf/buglog.json` by whoever picks this up:
the `run_backup()` TypeError at `blueprints/migration/routes.py:133`, the WhatsApp stub-mode false "Sent" at
`blueprints/whatsapp/scheduler.py:51`, and the Arabic PDF `FPDFUnicodeEncodingException` in
`models/pdf_generator.py`.*
