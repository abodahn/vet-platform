# Technical Due-Diligence Dossier

**Subject:** Aleefy — veterinary clinic ERP
**Repository:** `D:\vet\platform`, git, branch `fix/audit-remediation`, HEAD `cb11154` (2026-07-28 03:09 +0300)
**Prepared:** 2026-07-28
**Audience:** the buyer's technical reviewer

---

## How to read this

Every number here was produced by running a command against the repository at the
commit named above. Where a claim could not be executed it is marked **not verified**
and you should treat it as unproven.

Two prior internal audits exist in the tree —
`docs/AUDIT_AND_PLAN_2026-07-25.md` and `docs/market/05_PRODUCT_READINESS.md`. Both
contain corrections to their own earlier findings, and both are honest about it. That
history matters: **four findings in the first audit were wrong, and every one of them
was wrong because it was produced by pattern-matching rather than by execution.** This
document therefore separates, per module, what was *executed* from what was only
*read*. Where this dossier disagrees with either prior audit, the disagreement is
stated and the newer measurement wins.

Eleven commits landed after `05_PRODUCT_READINESS.md` was written. Several of its
headline defects are now fixed. Several are not. Three defects it does not contain
are recorded here for the first time, one of which is the most serious item in the
document (§3.1).

Effort figures are in developer-days for someone already fluent in this codebase, with
the reasoning shown. A stranger should apply the ramp-up in §6.

---

# 1. What it is

## 1.1 Stack

| Layer | Choice | Version constraint |
|---|---|---|
| Language | Python | CI runs 3.11 and 3.12; container is `python:3.11-slim`; the development machine runs 3.14.6 |
| Web framework | Flask 3 + Jinja2 | `Flask>=3.0.0` |
| Database | PostgreSQL via `psycopg2` | `psycopg2-binary>=2.9.0` |
| Dev/fallback database | SQLite via a hand-written compatibility layer | stdlib `sqlite3` |
| ORM | **none** | raw SQL strings throughout |
| Migrations | Alembic | `alembic>=1.13.0` |
| Server | gunicorn | `gunicorn>=21.0.0` |
| Scheduling | APScheduler in-process | `APScheduler>=3.10.0` |
| Front end | server-rendered Jinja templates, vanilla JS | no SPA framework, no build step for JS |
| Auth | bcrypt + Flask session cookies; optional TOTP 2FA | `bcrypt`, `pyotp`, `cryptography` |

There is no ORM and no query builder. `models/database.py` (3,264 lines) is a
hand-rolled dialect-translation layer that lets the same SQL strings run on both
psycopg2 and `sqlite3`. This is the single most consequential architectural fact in
the repository and most of §3 follows from it.

## 1.2 Architecture

Single Flask application, single process family, one deployment per clinic.

```
run.py / gunicorn ──► app.py:create_app()
                        ├── config.py               env-driven config + VERSION_INFO
                        ├── models/database.py      dialect layer + ~all SQL + init_db()
                        ├── models/{security,audit,backup,pdf_generator,
                        │           excel_export,logging_setup,logging_db,sync}.py
                        ├── 33 registered blueprints  (34 exist; api_v1 is not registered)
                        ├── APScheduler              backup 02:00, reminders 09:00,
                        │                            backup-health 09:05, cleanup
                        └── Jinja templates          170 files, all extending base.html
```

Deployment shape (`PROVISIONING.md`): one Docker Compose project per clinic, one
shared PostgreSQL server, one shared nginx, per-clinic port bound to `127.0.0.1`,
per-clinic `.env` at mode 0600, per-clinic database and role with `CONNECT` revoked
from `PUBLIC`.

## 1.3 Module inventory

Route counts are from `app.url_map` on a booted application, not from grep. 378
non-static rules, 33 blueprints.

| Blueprint | Routes | Blueprint py LOC | What it does |
|---|---:|---:|---|
| whatsapp | 58 | 1,573 | Wapilot instance management, templates, campaigns, logs |
| hr | 31 | 1,453 | Staff records, departments, branches, leave |
| attendance | 21 | 856 | Check-in/out, shifts, timesheets |
| system | 20 | 834 | Settings, roles, backup UI, audit log UI, monitor |
| ai_assistant | 14 | 953 | LLM assistant over clinic data |
| petshop | 14 | 684 | Retail POS, orders, stock, reports |
| reports | 14 | 703 | Canned reports + report builder |
| appointments | 13 | 796 | Booking, calendar, reception, waiting room |
| crm | 13 | 776 | Owners, pets, loyalty |
| finance | 13 | 763 | Invoices, payments, PDF invoices |
| payroll | 13 | 615 | Salaries, payslips |
| boarding | 12 | 392 | Boarding bookings and rooms |
| procurement | 11 | 315 | Purchase orders, suppliers, receiving |
| visits | 11 | 558 | Consultation record, the clinical daily driver |
| clinical | 10 | 412 | Labs, vaccinations, surgeries |
| grooming | 10 | 355 | Grooming bookings |
| inventory | 10 | 566 | Items, batches, FEFO, stock movements |
| imaging | 8 | 401 | Image upload + LLM photo analysis |
| inpatient | 8 | 394 | Stays, rounds, medication charts |
| telemedicine | 8 | 388 | Remote consultation records |
| accounting | 7 | 626 | P&L, cashflow, budgets, daily closing |
| doctor | 7 | 387 | Doctor workspace |
| auth | 6 | 590 | Login, 2FA, logout, permission engine |
| launcher | 6 | 644 | Module launcher / home |
| pharmacy | 6 | 338 | Prescriptions, dispensing |
| public_api | 6 | 349 | Public booking/contact/emergency, unauthenticated |
| catalog | 5 | 122 | Service catalog |
| migration | 5 | 375 | Excel data import |
| notifications | 4 | 43 | In-app notification centre |
| uploads | 4 | 245 | Authenticated file upload/serve |
| cds | 3 | 640 | Clinical decision support (drug data marked DRAFT) |
| petsy | 3 | 823 | Public AI marketing chatbot |
| settings | 3 | 150 | Theme/branding settings API |
| *(app-level)* | 1 | — | `/healthz` |
| **api_v1** | *(19 defined)* | 565 | **Not registered.** Ops telemetry, sync, diagnostics |

HTTP methods across the 378 rules: GET 243, POST 179, PUT 1, PATCH 2, DELETE 2. The
application is form-post driven, not REST.

## 1.4 Counts

| Measure | Value | How measured |
|---|---:|---|
| Git-tracked files | 386 | `git ls-files \| wc -l` |
| Registered routes (non-static) | 378 | booted app, `url_map.iter_rules()` |
| Blueprints registered | 33 | `len(app.blueprints)` |
| Blueprints present but unregistered | 1 (`api_v1`) | `"api_v1" in app.blueprints` → `False` |
| Database tables | 72 | `sqlite_master` on a freshly-initialised database; `grep -c '^CREATE TABLE' db_migrations/versions/0001_baseline.sql` also gives 72 |
| Foreign-key constraints | 52 | `PRAGMA foreign_key_list` over all 72 tables |
| Tables declaring **no** foreign key | **34** | same |
| Indexes | 60 | `sqlite_master WHERE type='index'` |
| `REAL` columns | 62 | `PRAGMA table_info` over all tables |
| …of which hold money | 34 | cross-referenced against `db_migrations/versions/0002_money_numeric.py` |
| Git commits | 51 | `git log --oneline \| wc -l` |
| Git history span | 2026-05-21 → 2026-07-28 (68 days) | `git log` |
| `.git` size | 3.9 MB | `du -sh .git` |
| Tests | 549, all passing | `pytest -q`, 103 s |
| Routes exercised by the suite | **69 of 378 (18%)** | see §2.2 |

Prior audits quote 55, 71 and 73 tables and 376, 379 and 382 routes at various dates.
The current figures are 72 and 378.

## 1.5 Lines of code

Git-tracked files only. Blank and comment lines included — this is `wc -l`, not a
logical-statement count.

| Language | Files | Lines |
|---|---:|---:|
| Python | 130 | 38,261 |
| HTML / Jinja | 170 | 33,866 |
| CSS | 7 | 7,657 |
| JavaScript | 11 | 7,039 |
| Markdown | 24 | 9,627 |
| SQL | 1 | 1,202 |
| JSON | 1 | 931 |
| **Total (these types)** | **344** | **98,583** |

Python breaks down as: blueprints 20,197; `models/` 6,911; tests 7,166; everything else
3,864 — `app.py` (447), `config.py`, `run.py`, four seed scripts (1,359 combined),
the four provisioning scripts (52 KB), Alembic and `static/css/build.py`.

The largest single files are `models/database.py` (3,264), `templates/base.html`
(1,275), `templates/visits/visit_detail.html` (1,126), `models/pdf_generator.py` (915)
and `models/backup.py` (754).

## 1.6 Dependency and licence audit

**Declared runtime dependencies: 19**, in `requirements.txt`. **Declared dev
dependencies: 1** (`pytest`). **Total packages installed in the working virtualenv,
including transitive: 70.**

Licences read from installed package metadata (`License-Expression`, then
`License ::` classifiers, then the free-text `License` field).

### The three that matter

| Package | Version | Licence | Assessment |
|---|---|---|---|
| **fpdf2** | 2.8.7 | **LGPL-3.0-only** | The only copyleft licence in the tree that is not merely a linking exception. Used by `models/pdf_generator.py` for every invoice, vaccination certificate and payslip. |
| psycopg2-binary | 2.9.12 | LGPL with exceptions | The psycopg exception explicitly permits use with software under other licences. Low concern. |
| python-bidi | 0.6.11 | LGPL | Used only for Arabic PDF text reordering. |

**There is no GPL, AGPL or SSPL dependency anywhere in the tree** — verified across all
70 installed distributions. Nothing forces the application's own source to be
disclosed.

**On fpdf2 specifically.** LGPL-3.0 obliges you, when distributing, to let the
recipient replace the library with a modified version. In a Python application that
imports fpdf2 at runtime from a `pip`-installed package, that condition is met by
construction — the recipient can `pip install` a different fpdf2. Two obligations are
nonetheless *not* currently met: the LGPL text is not shipped with the software, and
no notice tells the recipient the library is used. Both are remedied by adding a
`THIRD_PARTY_NOTICES` file. **0.5 days.** The risk becomes real, not clerical, only
if fpdf2 is ever vendored into the source tree or statically bundled into a
single-file binary. It currently is not, and it should not be.

The remaining 67 packages are MIT, BSD (2/3-clause), Apache-2.0, MPL-2.0, PSF or
public-domain equivalents. Full list on request; produced by
`importlib.metadata.distributions()`.

### Fonts

| Asset | Identified as | Licence | Notice shipped? |
|---|---|---|---|
| `static/fonts/Cairo-Regular.ttf`, `Cairo-Bold.ttf` | Cairo v3.130 | **SIL OFL 1.1** — read from the fonts' own `name` table, ID 13 | **No** |
| `static/fonts/cairo-*.woff2` (3 subsets) | Cairo | SIL OFL 1.1 | **No** — the subsetting stripped the name table; the files carry no licence string at all |
| `static/fonts/dmsans-*.woff2` (4) | DM Sans 9pt | SIL OFL 1.1 | **No** — same |
| `static/fonts/bootstrap-icons.woff2` + `_bootstrap-icons-src.css` | bootstrap-icons | MIT | **No** |

**A repository-wide search for `LICENSE`, `LICENCE`, `OFL`, `COPYING` returns zero
files.** No third-party licence text of any kind ships with this software.

**Implications of OFL for the Cairo fonts, stated plainly:**

- OFL 1.1 permits bundling, embedding in documents and PDFs, and redistribution as
  part of a commercial product. **There is no fee and no restriction on commercial
  use.** This is not a licensing obstacle to the sale.
- OFL requires that the licence text accompany any redistribution of the font files,
  and that the copyright and licence notice be included. Shipping the TTFs and woff2
  subsets inside a Docker image is redistribution. **This obligation is currently
  unmet.**
- OFL forbids selling the font files *on their own*. Selling software that contains
  them is fine.
- OFL forbids using the Reserved Font Name ("Cairo") for a modified version. The
  woff2 files are Google Fonts subsets and still declare the name "Cairo"; subsetting
  is arguably a modification. This is a theoretical exposure, not a practical one,
  and it disappears if the subsets are regenerated or replaced with the full TTFs.
- The `.ttf` files are the ones embedded into every generated PDF. Every invoice this
  software produces contains a subset of an OFL font. That is expressly permitted by
  the OFL's document-embedding clause.

**Total remediation for the entire licence position: 0.5 developer-days** — one
`THIRD_PARTY_NOTICES.md` listing the 70 packages and their licences, plus
`OFL-1.1.txt` and the bootstrap-icons MIT notice in `static/fonts/`. This is the
cheapest item in this document and the one most likely to be raised by a buyer's
counsel.

## 1.7 What is *not* in the repository

Not tracked, by `.gitignore` and by design: `.env`, `.env.development`,
`.env.production`, `data/` (databases, uploads, backups), `logs/`, `.venv/`.

Not present at all: any mobile application source (no `pubspec.yaml`, `*.dart`,
`*.swift`, `AndroidManifest.xml`, no `ios/`, `android/` or `mobile/` directory),
any lab-instrument driver, any payment-gateway code, any e-invoicing code. See §3.9.

The parent directory `D:\vet\` contains four archived full copies of earlier
generations of this application, a separate React/Vite project, the author's previous
Flask app (`ppc_diagnostics_work/`), a `node_modules/`, and 15 mis-exported
extensionless spreadsheet files. **None of this is inside the git repository being
sold.** A buyer should confirm in writing which directory constitutes the asset. This
dossier describes `D:\vet\platform` only.

---

# 2. What actually works

## 2.1 Module-by-module

The distinction below is strict:

- **Executed** — I booted the application against a throwaway SQLite database, logged
  in as the seeded admin, and requested the route. It returned 2xx or 3xx.
- **Read** — I read the code and found no defect. I did not run it.
- **Tested** — the shipped test suite covers it, and the suite passes.

Method for "executed": every one of the 174 GET routes that takes no path parameter
was requested with an authenticated session. **173 of 174 returned 2xx/3xx.** The one
failure is `/healthz`, and it is discussed in §3.1. Routes taking a path parameter
(e.g. `/visits/<id>`) were not exercised, because inventing identifiers against an
empty seeded database proves nothing. That is roughly half the surface, and it is the
half where the interesting logic lives — **treat "executed" below as "the page
renders", not "the workflow is correct".**

| Module | Executed | Tested | Assessment |
|---|---|---|---|
| auth (login, 2FA, logout) | 5/5 | **6/6 routes, `test_auth.py`, `test_auth_security.py`, `test_2fa.py`, `test_csrf.py`** | The best-covered area in the product. TOTP enrolment, backup codes, single-use enforcement, bcrypt migration from SHA-256, CSRF, DB-backed rate limiting keyed on IP *and* username — all executed by tests. |
| accounting | 6/6 | 6/7 routes | P&L, cashflow, budget, daily closing. |
| appointments | 9/9 | 8/13 routes | Booking, calendar, reception. Waiting-room and queue endpoints are public (§3.6). |
| cds | 1/1 | 3/3 routes | Deliberately advisory, not blocking, because its drug data is marked DRAFT (`app.py:140-146`). That was the right call. **It must never be described as a safety check.** |
| crm | 5/5 | 5/13 routes | Owners, pets, loyalty. |
| doctor | 5/5 | 5/7 routes | |
| finance | 6/6 | 3/13 routes | Invoice creation, payment recording, PDF invoice. The invoice-status rounding fix is present and tested. |
| inventory | 8/8 | 3/10 routes | FEFO logic read, not executed end to end. |
| migration (data import) | 2/2 | `test_import.py` | Rewritten today: real browser upload, staged with a UUID token, backup now gates the import. |
| petshop (POS) | 9/9 | 5/14 routes | Money rounding at the write is present (`blueprints/petshop/routes.py:428-431`). |
| system | 9/9 | 8/20 routes | Settings, roles, backup UI, audit log UI. |
| backup / restore | — | **`test_backup.py`, `test_provisioning.py`** | Rewritten today (§4.3). |
| PDF generation | — | **`test_arabic_pdf.py` — executed, 10 tests** | See below. |
| hr | 12/12 | **1 of 31 routes** | 1,453 lines, 31 routes, essentially untested. |
| whatsapp | 21/21 | **0 of 58 routes** | The largest blueprint in the product. Zero test coverage. Two incompatible API clients (§3.7). |
| attendance | 12/12 | **0 of 21 routes** | Feeds payroll. Untested. |
| payroll | 5/5 | 2 of 13 routes | |
| reports | 10/10 | **0 of 14 routes** | |
| clinical (labs, vaccinations, surgery) | 7/7 | **0 of 10 routes** | Vaccination certificate PDF is covered by `test_arabic_pdf.py`; the routes are not. |
| pharmacy | 3/3 | **0 of 6 routes** | Prescription → dispensing is a described strength; it is not tested. |
| boarding, grooming, procurement, telemedicine, imaging, catalog, notifications, uploads, public_api | all render | **0 routes each** | |
| **api_v1** | **not reachable** | — | Not registered. 565 lines, 19 routes, dead. Its dependencies `models/logging_db.py` (259 lines) and `models/sync.py` (249 lines) are dead for the same reason. |

**Two things are genuinely well built and I verified both by execution:**

1. **Arabic in PDFs.** The readiness audit (written today, earlier) records this as a
   hard failure — `FPDFUnicodeEncodingException` on the first Arabic character,
   triggered by a clinic typing its own name into Settings. It has since been fixed
   and the fix is real: `static/fonts/Cairo-{Regular,Bold}.ttf` ship,
   `arabic-reshaper` and `python-bidi` are declared in `requirements.txt`, and
   `tests/test_arabic_pdf.py` generates actual invoice, vaccination-certificate and
   payslip bytes with Arabic clinic names, owner names, pet names and line items,
   asserting `%PDF` and that `Cairo` is embedded. That is a test that fails if the
   fix regresses. **This is now a solved problem, not an open one.**

2. **Arabic user interface.** Quantified in §5.4. This is the single largest asset in
   the repository and it is real.

## 2.2 The test suite — the real number

```
549 passed, 164 warnings in 102.66s
```

Run with `pytest -q` on Python 3.14.6 against a throwaway SQLite database created by
`tests/conftest.py`. No PostgreSQL, no network, no manual setup. 32 test modules,
7,166 lines of test code.

CI (`.github/workflows/ci.yml`) runs on every push and pull request, on Python 3.11
and 3.12, and runs the same suite.

**What the suite covers.** Authentication and session security (login, logout,
lockout, CSRF, TOTP enrolment and backup-code single-use, bcrypt upgrade-on-login,
open-redirect rejection), the SQL dialect-translation layer in both directions, role
seeding consistency, the backup/restore module, Arabic PDF generation, structured
logging configuration, theme and branding settings, the money-rounding regression, and
a workflow test that walks owner → pet → appointment → visit → invoice → payment.

**What the suite does not cover, and this is the material fact:**

> **The suite dispatches 69 of the 378 registered routes. 18%.**

Measured by monkeypatching `flask.Flask.full_dispatch_request` to record
`request.url_rule.endpoint` for the duration of a full run.

| 0% route coverage | Routes |
|---|---:|
| whatsapp | 58 |
| attendance | 21 |
| reports | 14 |
| boarding | 12 |
| procurement | 11 |
| clinical | 10 |
| grooming | 10 |
| telemedicine | 8 |
| imaging | 8 |
| pharmacy | 6 |
| public_api | 6 |
| catalog | 5 |
| notifications, uploads | 4 each |
| **Subtotal** | **177 routes, 47% of the surface, zero coverage** |

`hr` is 1/31. `inpatient` 1/8. `ai_assistant` 2/14. `payroll` 2/13.

Additional gaps:

- **PostgreSQL is not tested in CI.** The `tests-postgres` job exists and spins up
  PostgreSQL 16, but carries `continue-on-error: true` (`ci.yml:45`) because
  `tests/test_postgres_full.py` still targets a hardcoded database name instead of
  `TEST_POSTGRES_DSN`. **Production runs PostgreSQL; the green tick is about SQLite.**
  This is the single most important caveat about the test suite: for any defect whose
  failure mode differs between the two engines — and the money question in §3.2 is
  exactly that — a green suite is not evidence.
- No lint, no type check, no coverage gate, no security scan, no build or deploy job.
- No browser/end-to-end suite in CI. A Playwright suite exists at `D:\vet\tests`
  (outside the repository) and is deliberately excluded.
- No load or concurrency testing. Nothing tests the behaviour of the connection pool
  under contention, nor the scheduler lock under multiple workers.
- Fixtures use a fresh, near-empty database. Nothing tests behaviour at data volume.

**Honest summary of the suite:** it is a good regression harness for the things that
were recently broken and fixed, and for the security primitives. It is not a
correctness proof of the business logic, and it does not touch half the application.

---

# 3. Defect register

Severity is stated as impact on a buyer, not on the current author. Effort is in
developer-days with reasoning. "What breaks" describes the consequence of shipping
without the fix.

---

## 3.1 The fleet-operations layer polls an endpoint that returns 404

**Severity: critical. This is the most serious finding in the document, and it is not
in either prior audit.**

`blueprints/api_v1/` is deliberately not registered. `app.py:241` states the reason
explicitly: *"api_v1 stays unregistered; registering it to get a health route would
expose eleven other endpoints."* That decision is defensible.

Four separate consumers were nonetheless written against `/api/v1/health`:

| Consumer | Line | Consequence |
|---|---|---|
| `deploy/clinic-compose.yml` | `:37` | Docker healthcheck. Every clinic container reports **`unhealthy`** permanently. |
| `scripts/provision/provision.sh` | `:179` | Every install polls for 60 seconds, then prints `not healthy after 60s`. |
| `scripts/provision/upgrade.sh` | `:143` | `healthy` never becomes 1, so `:154-163` runs: **every upgrade automatically rolls the code back and exits non-zero**, having already applied any Alembic revision it was told to apply. |
| `scripts/provision/inventory.py` | `:39` | Fleet dashboard reports `http 404` and no version for every clinic. |

Verified by execution:

```
GET /api/v1/health -> 404
GET /healthz       -> 503
"api_v1" in app.blueprints -> False
```

The working endpoint is `/healthz` (`app.py:243`). Nothing points at it.

**What this means.** `PROVISIONING.md` and `docs/market/05_PRODUCT_READINESS.md`
both identify fleet tooling — one-command upgrade, health-gated restart, automatic
rollback, fleet inventory — as the highest-leverage engineering in the product, the
thing that decides whether a solo operation survives past 20 clinics. That layer was
built. **It has never been executed end to end.** The upgrade path, as shipped,
cannot succeed; it is a script whose only reachable outcome is "roll back and report
failure", and in the schema-change case it leaves the migration applied while the code
goes backwards.

A second, independent defect compounds it: `/healthz` returns **503** on a freshly
provisioned clinic, because `models/backup.py:health()` reports `ok: False` until the
first backup exists, and the first scheduled backup is at 02:00. So correcting the URL
alone still leaves a new install reporting `degraded` for up to 24 hours.

**Effort: 1 day.** The URL change is minutes. The day is the cost of what was
actually missing — standing up a Linux host with Docker, provisioning a clinic,
upgrading it, rolling it back, and watching `inventory.py` report the truth. The
development machine is Windows and `provision.sh` refuses to run there by design, which
is why none of this was caught.

**What breaks if not fixed:** the buyer inherits an upgrade mechanism that reverts
every release, a container orchestrator that believes every clinic is sick, and a
fleet dashboard that reports nothing. The support-cost model in
`05_PRODUCT_READINESS.md` §3.4 — which is the commercial case for the product being
operable by a small team — is contingent on this layer working, and it does not.

---

## 3.2 Single-tenant. `clinic_id` exists in one place and is never read

**Severity: high — architectural, and it decides the business model rather than being
a bug to fix.**

Verified exhaustively. `clinic_id` occurs **twice in the entire tree**, both of them
schema declarations of the same column:

- `models/database.py:701` — `clinic_id INTEGER DEFAULT 1,` on `branches`
- `db_migrations/versions/0001_baseline.sql:29` — the same column

Zero reads. Zero `WHERE` clauses. Zero explicit writes. `tenant_id` and
`organization_id` return zero hits. Of 72 tables, **none** carries an enforced tenant
discriminator.

The `clinic` table is a hardcoded singleton: written in exactly one place,
`blueprints/system/routes.py`, as `UPDATE clinic SET ... WHERE id=1`. No route creates
a second row.

`branch_id` exists on **10** tables (`departments`, `users`, `appointments`, `visits`,
`warehouses`, `invoices`, `expenses`, `daily_closings`, `purchase_orders`, `devices`).
It appears in exactly **one** filtering predicate in the whole codebase —
`blueprints/hr/routes.py:1290`, `base += " AND u.branch_id=?"` — against **328** SQL
statements that read or write those ten tables. Multi-branch is not implemented
either.

`CLINIC_ID` as an environment variable does exist (`config.py:95`) but is a telemetry
tag: it appears in log lines, Sentry tags and the authenticated `/healthz` body. It
never reaches a SQL statement.

**Effort to retrofit: 40–60 developer-days, with residual risk that no test suite
catches.**

Reasoning: there is no ORM, therefore no global query-filter hook and nowhere to put
one. Roughly 800 raw SQL strings are distributed across 34 blueprints; 328 of them
touch the ten tables that already have a branch column, and the rest would need a new
column plus a predicate. At a realistic 15–20 statements per day including reading the
join paths, adding the predicate, and writing a test that would catch its absence,
that is 40–55 days, plus schema migration, plus a leakage-detection harness. The
residual risk is the part that matters: **a single missed predicate is a silent
cross-clinic disclosure of patient records, and nothing in the system would report
it.** In a product holding animal medical histories and owner contact details, that is
a regulatory and reputational event, not a bug.

**What breaks if not fixed:** nothing, provided the deployment model stays one
container per clinic. The architecture in `PROVISIONING.md` is coherent and correct
for this codebase. **What must never happen is two clinics sharing one database
"temporarily"** — there is no mechanism that would prevent or detect clinic A reading
clinic B's patients. A buyer intending to run a shared multi-tenant SaaS should price
this as a rewrite of the data-access layer, not a feature.

---

## 3.3 Money stored as `REAL` in 34 columns across 15 tables

**Severity: high (latent). Currently no measured damage. Deliberately not migrated.**

Measured: 62 `REAL` columns exist; **34 of them hold currency amounts**. The rest are
genuine continuous measurements (`weight_kg`, `temp_c`, `hours_worked`, fluid
balances, lab result values, reorder levels) where `REAL` is correct.

The money columns, by table: `invoices` (7), `daily_closings` (8), `invoice_lines`
(3), `purchase_orders` (3), `items` (2), `po_lines` (2), `batches`, `boarding_rooms`,
`budget_targets`, `expenses`, `grooming_services`, `owners.outstanding_balance`,
`payments.amount`, `service_catalog.standard_price`, `stock_movements.unit_cost`.

`docs/MONEY_PRECISION.md` (682 lines) contains the measured analysis. Its findings,
which I have reviewed and which are internally consistent:

- Against the live database, **all 15 invoices balance**. Subtotal vs lines, total vs
  parts, paid vs payments, due vs total−paid: zero mismatches. That is an honest null
  result, and the reason for it is that the invoicing code already rounds at almost
  every write.
- 42 of 499 stored money values are not exact to 2 decimal places. All 42 are in
  `expenses.amount` and all 42 came from the demo seed script.
- The one live, customer-visible bug — an invoice paid in full that stays "Partial"
  forever because `due == 0` is an exact float comparison — was measured by simulating
  200,000 instalment-paid invoices: **14.17% became permanently stuck.** That bug has
  since been **fixed** (`models/database.py:2853-2857`, now `round(...)` plus
  `due < 0.005`), and the pet-shop VAT write path is rounded too
  (`blueprints/petshop/routes.py:428-431`).

**Why the prepared migration was deliberately not applied.** The migration exists —
`db_migrations/versions/0002_money_numeric.py`, 34 columns, ROUND_HALF_UP via
`Decimal(repr(v))`, verified against a copy of the real database across ten checks
including an upgrade→downgrade round trip and idempotency. It is on hold for four
reasons the document states and I find sound:

1. There is no damage to repair. Every invoice balances.
2. On PostgreSQL, `NUMERIC` returns `Decimal`, and the code contains **172 `float()`
   coercions** that would immediately convert those Decimals back to binary floats.
   Exact storage feeding inexact arithmetic buys nothing. The migration alone is close
   to cosmetic.
3. **The test suite runs on SQLite, where the failure mode does not exist.** SQLite has
   no true decimal type — `NUMERIC(12,2)` is an affinity label, and fractional values
   are still stored as binary floats. So the tests would stay green while PostgreSQL
   broke. Six JSON endpoints are identified as confirmed 500s, one of them the
   unauthenticated `blueprints/public_api/routes.py:72-84`.
4. The unsafe surface is not the database. It is **261 template locations that display
   money with no formatting** (`120.5` becomes `120.50`, silently, in 261 places) and
   `models/excel_export.py:83, 95, 102`, which test `isinstance(value, (int, float))`
   — a `Decimal` fails that test, and **every financial Excel export silently stops
   emitting its TOTAL row.** No error, no log.

Deferring it was the correct call, and the reasoning is documented rather than
implicit. A buyer should read that as a positive signal about engineering judgement,
and as an inherited obligation.

**Effort to complete properly: 10–14 developer-days.** Reasoning: 1 day for a `|money`
Jinja filter, a Decimal-aware Flask JSON provider and the three `isinstance` fixes in
`excel_export.py` — this alone collapses roughly 350 of the ~800 affected call sites to
about 3. Then 5–7 days to move the 261 raw template displays onto the filter and strip
the 172 `float()` coercions from the 17 money helpers. Then 0.5 days to run the
prepared migration. Then **2–3 days of manual QA against a real PostgreSQL instance**,
because the suite cannot verify it — that is unavoidable and it is the reason this is
not a 5-day job. Add 2 days for the pet-shop tables, which the migration deliberately
excludes because `blueprints/petshop/routes.py:37` runs `CREATE TABLE IF NOT EXISTS`
on nearly every request and would undo the migration; fixing that is an application
change.

**What breaks if not fixed:** nothing today. The exposure appears when transaction
volume rises and when pet-shop VAT is switched on — at 14% VAT, simulation shows
**65.9% of POS line totals** would not be representable to two decimal places, were
the rounding not now in place. The residual risk is that the migration is eventually
done under production pressure, at the PostgreSQL cutover, by someone who has not read
`MONEY_PRECISION.md`.

---

## 3.4 RBAC: the permission engine is applied to **zero** routes

**Severity: high. This is worse than the prior characterisation and worse than the
briefing note that prompted this dossier.**

The engine exists and is well built. `blueprints/auth/routes.py`: `_role_permissions`
(`:110`), `has_permission` (`:155`), `permission_required` (`:181`), a 60-second cache
(`:99-101`), `clear_permission_cache` (`:104`). Schema and CRUD in
`models/database.py`: `permissions_json` (`:743`), `ALL_PERMISSIONS` (`:3179`),
`create_role` (`:3234`), `update_role` (`:3245`).

Decorator census across 389 route decorators in `blueprints/`:

| Decorator | Count |
|---|---:|
| `@permission_required(...)` | **0** |
| `@role_required(...)` | 88 |
| `@login_required` only | 271 |
| none of the three | 30 |

The single grep hit for `@permission_required` is a **docstring example inside its own
definition** (`blueprints/auth/routes.py:188, 190`). `has_permission` has no caller
outside the engine itself. `clear_permission_cache` is called only from
`tests/test_auth_security.py`.

Of the 30 undecorated routes, 11 use `api_v1`'s own `require_auth`/`require_admin` and
are unreachable anyway. **19 are genuinely unauthenticated**: three auth routes
(expected), `launcher/routes.py:494`, three `petsy` routes, six `public_api` routes,
three `settings` routes, `api_v1` health and version, and —
`appointments/routes.py:743` (`waiting_room`) and `:784` (`api_queue`).

`05_PRODUCT_READINESS.md` §4.2 states `permission_required` is "applied to 2 routes".
That is the docstring. The correct number is zero.

**Fail-open or fail-closed?** Both, deliberately, and neither is reachable.
`has_permission` fails **closed** (`:173-174`). `permission_required` degrades to the
hardcoded role list when `permissions_json` is missing or unparseable (`:138`,
`:202-203`) — it is not open to everyone, it falls back to `role_required` semantics.
The comment at `:93-97` explains the intent: seed roles ship with no
`permissions_json`, so empty must mean "no data, fall back", not "deny all".

**The Roles administration screen is write-only.** `templates/system/roles.html:333,
383` post the checkboxes; `blueprints/system/routes.py:757, 778` read them;
`models/database.py:3239, 3250` persist them. The only reader is `_role_permissions`,
reached only from the two functions no route calls. **An administrator who restricts a
role in that UI has changed nothing whatsoever, and the UI tells them they have.**
Additionally, the 60-second cache is never invalidated in production, so even a wired
engine would take up to a minute to honour an edit.

**Effort: 7–9 developer-days.** Reasoning: 1 day to define the permission vocabulary
against `ALL_PERMISSIONS` and reconcile it with the 88 existing role lists; 5 days to
classify and convert 359 decorated routes at roughly 70/day, which is achievable only
because the fallback semantics make the conversion non-breaking; 1 day to wire
`clear_permission_cache` into the role-update path; 2 days for a per-module regression
test asserting that each role can reach exactly what it should — without which the
conversion is unverifiable, since the suite currently exercises 18% of routes.

**What breaks if not fixed:** at one customer, whose staff you know, nothing. At ten,
somebody discovers that a receptionist can open payroll, and the conversation is about
a breach rather than a bug — made materially worse by the fact that the Roles screen
told the clinic owner they had prevented it.

---

## 3.5 Two audit tables, one live and one an orphan — and the field-level audit engine is applied to one route

**Severity: medium.**

**`audit_log` (singular) is live.** Created `models/database.py:748` and
`0001_baseline.sql:76`; indexed only by `db_migrations/versions/0002_audit_log_indexes.py:84-88`.
45 of the 49 `log_audit(` call sites write to it, across 17 files. Read by the
paginated UI at `blueprints/system/routes.py:228`, by `models/database.py:2249`, by
`blueprints/hr/routes.py:582` and `blueprints/migration/routes.py:149`. It has a
template, a nav link, and an export.

**`audit_logs` (plural) is an orphan.** Created `models/database.py:1769` with four
indexes. Written from exactly one function, `models/logging_db.py:243`, which is
imported only by `blueprints/api_v1/routes.py` — **which is not registered.** It is
therefore never written to at runtime. It is never `SELECT`ed for content at all; the
only read is a row count in an unreachable diagnostics endpoint. Four indexes are
maintained on a table that receives no rows.

**A related and more consequential finding.** `models/audit.py` (322 lines) implements
field-level before/after auditing — `diff()`, `record_change()`, `snapshot()`,
`audit_row()`, with redaction of sensitive field names and a filterable history UI.
Commit `feat: field-level audit trail with filterable history UI` shipped it on
2026-07-25. **`audit_row` is called from exactly one file**
(`blueprints/system/routes.py`, on role update). `diff`, `is_redacted` and
`_current_user` have zero callers outside the module. Against roughly 200 mutating
routes, field-level auditing covers one.

**Effort: 0.5 days** to delete `audit_logs`, `models/logging_db.py` and the four
indexes — *if* `api_v1` is also deleted (see §3.10). **1 day** if `api_v1` is kept and
the two audit paths are reconciled instead. Separately, **6–8 days** to roll
`audit_row` across the clinical and financial write paths: the mechanism is done, so
this is call-site work at roughly 25–30 routes/day plus a test per module.

**What breaks if not fixed:** the orphan table costs nothing but reviewer confidence —
it is exactly the kind of thing a buyer's engineer finds in the first hour and uses to
argue that the schema is not understood. The audit *coverage* gap is the real cost:
when a clinical or financial number is wrong, you can prove who logged in, and nothing
else. No before/after, no attribution.

---

## 3.6 34 of 72 tables declare no foreign key

**Severity: medium.**

Measured with `PRAGMA foreign_key_list` over every table of a freshly initialised
database: 52 foreign-key constraints exist; 34 tables declare none.

The 34: `ai_conversations`, `app_logs`, `attachments`, `audit_log`, `audit_logs`,
`backend_logs`, `boarding_rooms`, `branches`, `budget_targets`, `clinic`,
`daily_closings`, `departments`, `devices`, `diagnostic_runs`, `expenses`,
`frontend_logs`, `grooming_services`, `item_categories`, `leave_types`, `owners`,
`public_holidays`, `reminder_runs`, `roles`, `service_catalog`, `settings`, `shifts`,
`suppliers`, `sync_conflicts`, `sync_queue`, `user_sessions`, `users`, `warehouses`,
`whatsapp_log`, `whatsapp_templates`.

That list needs splitting before it is used as a criticism. Roughly half are
legitimately reference-free: `clinic`, `settings`, `roles`, `leave_types`,
`public_holidays`, `item_categories`, `shifts`, `service_catalog`, `grooming_services`,
`boarding_rooms`, `suppliers` and `warehouses` are lookup or configuration tables with
no natural parent, and the five log tables (`app_logs`, `backend_logs`,
`frontend_logs`, `audit_log`, `audit_logs`) are deliberately unconstrained so that
logging cannot fail because a referenced row was deleted. That is correct design.

The ones that matter are the transactional tables with real parents that are not
declared: `expenses` (has `branch_id`, `category_id`), `daily_closings` (`branch_id`),
`departments` (`branch_id`), `devices` (`branch_id`), `budget_targets`,
`attachments`, `user_sessions` (`user_id`), `users` (`branch_id`, `department_id`),
`whatsapp_log`, `reminder_runs`, and — most significantly — **`owners`**, the root of
the entire clinical graph.

Two further points a reviewer will raise:

- **SQLite does not enforce foreign keys unless `PRAGMA foreign_keys = ON` is set per
  connection.** Whether the 52 declared constraints are enforced on the SQLite path is
  **not verified** in this dossier. On PostgreSQL they are enforced unconditionally.
- The prepared money migration already demonstrated the specific hazard here: rebuilding
  a SQLite table via SQLAlchemy reflection **silently downgraded an inline
  `ON DELETE CASCADE` to `NO ACTION`** (`docs/MONEY_PRECISION.md` §6). Any FK-addition
  migration on SQLite must be written and verified with that in mind.

**Effort: 4–6 developer-days.** Reasoning: writing the constraints is perhaps a day.
The work is (a) auditing existing production databases for orphan rows that would make
the constraint fail to apply, (b) deciding `ON DELETE` semantics per relationship —
which is a domain question, not a technical one, and the wrong answer deletes clinical
records — and (c) writing an Alembic revision that is safe on both engines, given that
SQLite requires a full table rebuild and the one prior attempt silently lost a cascade.

**What breaks if not fixed:** orphan rows accumulate silently. A deleted owner leaves
pets, visits, invoices and payments pointing at nothing; reports built on those joins
quietly drop or duplicate rows. Because there is no field-level audit (§3.5), the
cause is not recoverable after the fact.

---

## 3.7 Integrations that do not exist

**Severity: commercial, not technical. Each was confirmed absent by search.**

| Capability | Evidence |
|---|---|
| **Lab-machine / analyser integration** | Zero hits for HL7, ASTM, IDEXX or any instrument driver in code. Every `IDEXX`/`analyser` match is prose in `docs/`. The only "analyzer" in code is `blueprints/imaging/routes.py:326-389` — an LLM that describes an uploaded photograph. Unrelated. |
| **Mobile app** | No `pubspec.yaml`, `*.dart`, `*.swift`, `AndroidManifest.xml`, `app.json`; no `ios/`, `android/` or `mobile/` directory. 26 PNG mockups exist at `D:\vet\figma\` — images only, no vectors, no JSON, nothing machine-consumable, and **outside the repository**. |
| **Payment gateway** | Zero hits for Paymob, Fawry, Stripe, PayPal, Braintree, Checkout.com in `.py`, `.html` or `.js`. The only matches are the literal string `"Stripe_Secret_Key"` inside a redaction list at `models/audit.py:51`. Payments are recorded manually by a cashier after the fact. |
| **ETA e-invoicing (Egypt)** | Zero implementation. The only code hit for `eta` is a query-string parameter `eta='Q3 2026'` on a coming-soon page (`blueprints/launcher/routes.py:632`). |
| **SMS** | Zero hits for Twilio, `send_sms`, `sms_gateway`. |
| **Pet-owner authentication** | The `owners` table has no password, hash, token or verification column. Zero hits for `owner_login`, `owner_session`, `client_portal`, `magic_link`, JWT. `session["user"]` is set from the staff `users` table only. |

**Effort, for scoping only** — these are new products, not fixes:

| | Days | Reasoning |
|---|---:|---|
| Pet-owner auth (phone + OTP over the existing WhatsApp sender) | 5 | The sender and `owners.whatsapp_phone` already exist. Prerequisite for everything below. |
| Payment gateway (hosted checkout + webhook + reconciliation into `payments`) | 8 | One provider, one flow. Valuable only once there is somewhere for an owner to pay from. |
| Owner portal / PWA (26 designed screens or a credible subset) | 25–40 | 14 of the 26 screens sit behind an account that does not exist. The *data* exists; this is an auth-and-read-layer build. |
| ETA e-invoicing | 10–15 | **Not verified** against current ETA specifications. Involves accredited digital signing and an approved document schema; the estimate is indicative only and should be re-scoped by someone who has done one. |
| Lab-machine integration | 10–20 per instrument family | Serial/TCP driver plus result mapping onto the visit record. Cost is per analyser family, not one-and-done. |

**What breaks if not built:** nothing in the product. These are the items competitors
list on a comparison sheet. `docs/market/01_COMPETITORS.md` addresses their commercial
weight; this dossier only certifies their absence.

---

## 3.8 Two WhatsApp clients that cannot both be correct

**Severity: high — WhatsApp reminders are a headline feature.**

| | Host | Path | Auth header |
|---|---|---|---|
| `blueprints/whatsapp/wapilot.py:11, :24` — drives the 58-route UI | `api.wapilot.**net**` | `/api/v2` | `token: <key>` |
| `blueprints/whatsapp/scheduler.py:40, :42` — the daily 09:00 job | `api.wapilot.**io**` | `/send` | `Authorization: Bearer` |

Different domain, different TLD, different path, different authentication scheme, and
the scheduler uses raw `urllib.request` rather than the client module. One of these is
dead. The scheduler is the one customers depend on, and it is the one not shared with
the tested UI path. **Which one is correct is not verified** — it requires a live
Wapilot account.

The related defect *has* been fixed: the scheduler no longer writes `status = "Sent"`
when `WAPILOT_TOKEN` is unset. It now writes `"Not Configured"` with an explanatory
error (`blueprints/whatsapp/scheduler.py:50-62`). Before that fix, an unconfigured
clinic saw a green column of delivered reminders that had never been sent.

The whatsapp blueprint is 58 routes — **15% of the entire route surface — with zero
test coverage** (§2.2).

**Effort: 2 days.** Half a day to determine which endpoint is live and delete the
other; one day to route the scheduler through the tested client module; half a day for
a contract test against a recorded response.

**Additional risk, not a defect:** Wapilot is an unofficial WhatsApp automation
gateway. WhatsApp bans numbers used this way, without warning and without appeal. A
customer's headline feature can disappear overnight through no fault of the software.
**Not verified** whether Wapilot fronts the official WhatsApp Business Cloud API.
This should be established before the feature appears on any price list.

---

## 3.9 `clinic.currency` is a setting that does nothing

**Severity: medium — a settings screen that lies about money.**

The settings page offers EGP, USD, EUR, GBP, SAR and AED, described as "Used on
invoices and financial reports". The value is written
(`blueprints/system/routes.py:342, 348`) and read in exactly one place: to pre-select
its own dropdown (`templates/system/settings.html:145`).

Nothing formats money with it. No `format_currency`, `format_money` or
`currency_symbol` helper exists anywhere in the application. `EGP` is hardcoded in
**186 places across 59 templates and 53 places in non-test Python**, including inside
the AI prompt construction (`blueprints/petsy/routes.py:371-421`).

A clinic that selects USD sees EGP on every screen, every invoice and every report.

**Effort: 4 days** to introduce a currency-aware money filter and convert 239 sites —
or **0.5 days** to delete the dropdown and state that the product is EGP-only. The
second is the honest option and probably the right one; every currency in the list has
two decimal places, so nothing else in the storage layer would need to change.

**What breaks if not fixed:** a customer outside Egypt discovers it during their
first month. Given that `docs/market/06_ARABIC_MARKETS.md` scopes Gulf expansion, this
is on the critical path for that plan, not a cosmetic issue.

---

## 3.10 `api_v1` — 565 lines of unregistered, largely unauthenticated code in the tree

**Severity: medium.**

`blueprints/api_v1/` defines 19 routes and is not registered. Its dependencies
`models/logging_db.py` (259 lines) and `models/sync.py` (249 lines) are dead for the
same reason, along with the `sync_queue` and `sync_conflicts` tables and the
`audit_logs` table (§3.5). Roughly 1,073 lines of Python plus three tables.

11 of its routes use its own `require_auth`/`require_admin` decorators, which map a
single `API_V1_KEY` bearer token to `super_admin`. Two are public by design. **The day
somebody registers this blueprint to obtain a health route — which is exactly what
four other files already assume has happened (§3.1) — the platform acquires 19
endpoints, including `POST /sync/push`, `POST /logs/cleanup` and
`GET /system/diagnostics`, behind one shared static token.**

`app.py:241` documents the decision not to register it. The decision is right; leaving
the code in the tree while four consumers point at it is not.

**Effort: 1 day** to delete the blueprint, `logging_db.py`, `sync.py`, the three
tables and the four consumer references — or **3 days** to authenticate it properly,
register it deliberately, and give it a test.

---

## 3.11 Alembic has two heads; `upgrade head` fails

**Severity: low — deliberate, documented, but an operational trap.**

```
$ alembic -c db_migrations/alembic.ini heads
0002_audit_log_indexes (head)
0002_money_numeric (head)

$ alembic -c db_migrations/alembic.ini upgrade head
FAILED: Multiple head revisions are present for given argument 'head'
```

Both revisions declare `down_revision = "0001_baseline"`. This is intentional:
`0002_money_numeric` is the on-hold migration from §3.3 and must not be applied
alongside the index migration. `MIGRATIONS.md:68-106` explains it, and
`scripts/provision/upgrade.sh` refuses `--alembic head` on purpose.

It is recorded here because `alembic upgrade head` is the reflex command, it is what
every other project's runbook says, and it exits non-zero with a message that reads
like a broken repository. Anyone who has not read `MIGRATIONS.md` first will conclude
the migrations are corrupt.

**Effort: 0 days** if the documentation is trusted. **0.5 days** to add an explicit
merge revision or a branch label, which would remove the trap.

---

## 3.12 Silent exception handling

**Severity: medium.**

**58** occurrences across `platform/**/*.py` of an `except` whose body is nothing but
`pass` (53 on the following line, 3 inline `except Exception: pass`, 2 bare
`except: pass`). Concentrated in `blueprints/system/routes.py` (12),
`blueprints/hr/routes.py` (10), `models/database.py` (7),
`blueprints/ai_assistant/routes.py` (5), `blueprints/public_api/routes.py` and
`models/logging_db.py` (3 each).

This is down from the 76 recorded in the July audit, so the direction is right. It also
**understates the true surface**: the count includes only literal `pass` bodies, not
`except Exception: return None`, `except Exception: continue`, or log-and-swallow.

The category matters because the July audit's own D-11 finding is the proof: a
waiting-room query had been raising on **every** call since it was written, because of
a wrong column name, swallowed by `except: pass`. The feature had never worked and
nobody knew. That is what these 58 are hiding, on average.

**Effort: 4–5 days** to replace them with `logger.exception(...)` plus a real fallback,
DB layer and highest-traffic routes first. The cost is not the edit; it is deciding
what the correct fallback is at each site.

---

## 3.13 Smaller findings

| Finding | Evidence | Severity | Effort |
|---|---|---|---|
| **Patient queue data on unauthenticated routes** | `blueprints/appointments/routes.py:743` (`waiting_room`), `:784` (`api_queue`). A `WAITING_ROOM_TOKEN` is provisioned and names are masked, but the routes carry no auth decorator. **Not verified** whether the token is enforced on both. | Medium | 0.5 d |
| **`/petsy/chat` is public and spends the vendor's LLM budget** | `blueprints/petsy/routes.py:719`. Materially hardened today: 1,500-char message cap (`:61`), 6,000-char history cap (`:62`), and a **cross-worker daily spend ceiling counted in a database table** (`:76-110`). The per-IP limiter remains an in-process dict (`:34-45`), so with N gunicorn workers the per-IP rate is N× the intended value. | Medium | 0.5 d |
| **One shared `AI_API_KEY` across all installs; no token metering** | `.env`. Zero hits for `tokens_used` or any cost tracking. Cost is unattributable to a clinic by construction. | Medium | 3 d |
| **Public booking API creates rows** | `POST /api/public/book` is unauthenticated and does find-or-create on an owner by phone string and a pet by name. A bot can fill a clinic's CRM with fabricated owners and pets. IP rate-limiting is the only control. | Medium | 1 d |
| **Runtime table wrapping for responsive tables** | `templates/base.html:1246-1266` walks the DOM after load and injects a scroll container around every `<table>`. **126 `<table>` tags; 25 have a static wrapper class**, so ~101 depend entirely on that JavaScript. Self-documented at `:1245`: tables injected later by AJAX are **not** wrapped, and there is no MutationObserver. | Low | 0.5 d |
| **Documentation drift** | `PROVISIONING.md:278` lists "the app image has no `postgresql-client`" as a known gap; the `Dockerfile` installs it. `05_PRODUCT_READINESS.md` states Arabic PDFs fail and `permission_required` is on 2 routes; both are now wrong. Docs written the same day as the code they describe are already stale. | Low | 1 d |
| **`Dockerfile` bypasses `gunicorn.conf.py`** | `CMD` hardcodes `--workers 2`; `gunicorn.conf.py:20` computes `(cpu*2)+1`. Whichever is intended, two sources of truth exist. | Low | 0.25 d |
| **No lint, no type checking, no dependency scanning, no coverage gate in CI** | `.github/workflows/ci.yml` | Low | 1 d |
| **Deprecation debt** | 164 warnings per test run, dominated by `datetime.utcnow()`, removed in a future Python. `models/database.py:2171`, `models/security.py:602, 643, 703`, `blueprints/petshop/routes.py:144, 572, 573` and others. | Low | 1 d |

## 3.14 The pattern a reviewer should notice

Three of the findings above are the same shape, and the shape is the most useful single
observation in this dossier:

| Mechanism | Quality of the mechanism | Rollout |
|---|---|---|
| Permission engine (§3.4) | Good — cached, fail-closed, documented | **0 of 359 decorated routes** |
| Field-level audit trail (§3.5) | Good — diffing, redaction, filterable UI | **1 of ~200 mutating routes** |
| Money migration (§3.3) | Good — verified across 10 checks, reversible | **0 columns, deliberately** |
| Fleet operations (§3.1) | Good design — health-gated, auto-rollback | **Never executed; points at a 404** |

This codebase builds correct mechanisms and does not roll them out. Some of that is
sound judgement under time pressure — the money deferral is explicitly reasoned and
right. Some of it is not: the Roles screen actively misinforms an administrator, and
the upgrade script cannot succeed.

For a buyer this cuts both ways, and both directions are real. The hard part —
designing the mechanism correctly — is frequently done. The remaining work is call-site
conversion, which is predictable, parallelisable and cheap to estimate. That is a
better position to inherit than the reverse. But **a demo of any of these four features
will show something that does not do what it appears to do**, and the total conversion
backlog is roughly 25–30 developer-days on top of everything else in §4.

---

# 4. Operational reality

## 4.1 Deployment

`PROVISIONING.md` (306 lines) is the runbook, and it is unusually good for a
single-developer project: written for someone tired at 2am, commands before
explanations, an explicit "Known gaps — what still needs a human" section, and a
"Why this shape" section that records the alternatives considered and rejected.

Shape: **one clinic = one Docker Compose project = one database = one set of secrets**,
under `/srv/aleefy/clinics/<slug>/`. One shared PostgreSQL server, one shared nginx.
Each container: loopback-only port bind, 512 MB memory limit, CPU cap, PID limit,
capped JSON logs. Each database: its own role, with `CONNECT` revoked from `PUBLIC`, so
clinic A's leaked credentials cannot open clinic B's database.

`deploy/deploy.sh` is now host bootstrap only — packages, Docker, the PostgreSQL
server, ufw, `/srv/aleefy` at mode 700. **It contains no passwords.** The prior version
shipped one PostgreSQL password and one admin password to every customer, in a
committed file; that is fixed.

Per-clinic secrets are generated fresh by `scripts/provision/clinic_env.py`:
`token_hex(64)` for the session key (`:84`), `token_urlsafe` (`:89`), and a
CSPRNG-generated class-mixed admin password (`:97-114`). Five secrets per install —
`PLATFORM_SECRET_KEY`, `PLATFORM_ADMIN_PASS`, `POSTGRES_DSN`, `WAITING_ROOM_TOKEN`,
`API_V1_KEY` — never defaulted, never copied. `.env` at 0600. Credentials printed once
to `/dev/tty`, deliberately not to stdout, so `| tee` cannot capture them.

`provision.sh` is idempotent: role creation is `CREATE … ELSE ALTER`, `createdb` is
guarded, a re-run of a half-finished install continues, and a directory that already
has a `.env` is refused.

**Provisioning is Linux-only by design** — `provision.sh` refuses to run elsewhere,
because mode 0600 does not exist on Windows and the secrets would be world-readable.
The development machine is Windows. **Nothing in this layer has ever been executed on
a real host**, and §3.1 is the consequence.

TLS is manual: `certbot --nginx -d <domain>`, once per clinic. There is no secret
store; secrets live in each clinic's `.env` and in the operator's password manager.

## 4.2 Upgrade path

```
scripts/provision/upgrade.sh --clinic <slug> --ref v1.4.0 [--alembic <revision>]
scripts/provision/upgrade.sh --all --ref v1.4.0
scripts/provision/upgrade.sh --clinic <slug> --rollback
```

Designed order: **backup → verify the backup → build → migrate → restart → health
check.** A failed backup aborts before anything is touched. A failed health check
rolls the image back automatically and warns that an applied migration is *not*
undone. `--all` stops at the first failure rather than marching on and breaking twenty
clinics. `--alembic head` is refused on purpose (§3.11).

That design is correct. **As shipped it cannot succeed**, because the health check
polls `/api/v1/health` and that route does not exist (§3.1). The only reachable outcome
of `upgrade.sh` today is the rollback branch.

`app.py` also still runs `db.init_db()` on every boot, re-executing the schema with
`CREATE TABLE IF NOT EXISTS`. So the Alembic revision and `models/database.py:_SCHEMA`
are two parallel definitions of the same schema, and `MONEY_PRECISION.md` §8 notes they
already disagree about column types. A fresh install creates `REAL` money columns
regardless of what the migrations say.

## 4.3 Backup and restore

`models/backup.py` is 754 lines and was rewritten today. Verified by reading and by
`tests/test_backup.py`:

- **PostgreSQL is now backed up.** `_run_pg_backup()` shells out to
  `pg_dump --no-password -Fc` (`:203-242`); the engine is selected at `:253`/`:266`. A
  missing `pg_dump` returns a failure rather than a false success (`:214-216`). The
  container image installs `postgresql-client`. This was previously the single most
  serious risk in the product — the recommended production configuration had no
  backups and reported success — and it is now closed.
- **Off-site copies exist.** `copy_offsite()` (`:574`) to a folder
  (`BACKUP_OFFSITE_DIR`) or to any S3-compatible bucket via hand-rolled SigV4
  (`_s3_sign` `:614`, `_s3_put` `:642`), invoked on every successful backup (`:285`).
  **Both are unset by default**, and `PROVISIONING.md:288` says so plainly: without
  configuring one, the only copy of a clinic's records is on the same disk as the
  clinic.
- **Restore is now safe.** No `shutil.copy2` over a live database. SQLite goes through
  `sqlite3.Connection.backup` (`:162-178`), PostgreSQL through
  `pg_restore --clean --single-transaction` (`:434-444`). A **file-based** maintenance
  marker (`:112-131`) is visible to every gunicorn worker, auto-expires after 15
  minutes (`:59`), and blocks `run_backup()` while active (`:279`). Order:
  verify → maintenance on → pre-restore snapshot → restore → maintenance off
  (`:490-519`).
- **Staleness is alerted on, not just failure.** `health()` (`:678`) and
  `check_and_notify()` (`:743`), threshold `BACKUP_STALE_DAYS` (default 2), run as a
  09:05 scheduled job (`app.py:422`), with a 24-hour alert cooldown. This closes the
  previous failure mode where a scheduler that died three weeks ago looked identical
  to a healthy clinic.

`deploy/BACKUP_RUNBOOK.md` (226 lines) is written for a non-programmer, covers
verifying a backup without restoring it, restoring onto a fresh machine, and a
quarterly restore drill.

**What is still uncovered:** `data/uploads/` — scanned documents, radiographs, pet
photos — is **not** in any backup. The runbook says so and tells the operator to copy
it separately with `rsync` or `robocopy` on a schedule of their own. That is an honest
disclosure of a real gap, and it means an automated restore recovers the records but
not the images attached to them.

**Not verified:** no restore has been executed end to end by this review, on either
engine. The S3 path in particular is hand-rolled SigV4 against an unspecified provider
and I would not consider it proven until a buyer has run it against their own bucket.

## 4.4 Monitoring

| Signal | State |
|---|---|
| `/healthz` | Exists (`app.py:243`). Public body is `{status, version}` only; `checks`, `clinic`, `last_backup_hours` and `commit` are gated behind an `hmac.compare_digest` comparison against `API_V1_KEY`. Probes the database, the scheduler lock and backup age. Returns 503 when degraded — **including on every fresh install** (§3.1). |
| Version identity | `VERSION` file → `config.py:61-80` → `VERSION_INFO` → `/healthz`. Reports `3.0.0+b1479fdfaab1`. Verified by execution. |
| Structured logging | `models/logging_setup.py`. Rotation, retention, per-request correlation IDs, `X-Request-ID`. |
| Error aggregation | Sentry is **wired but not installed**. `_init_sentry()` (`logging_setup.py:273-304`) no-ops unless `SENTRY_DSN` is set, warns if the DSN is set but the package is missing, scrubs clinical/financial values via `_scrub_event`, tags clinic and release. `sentry-sdk>=2.0.0` is deliberately left commented out in `requirements.txt:68`. **A buyer must uncomment it and set a DSN, per clinic, or there is no error aggregation.** |
| Fleet inventory | `scripts/provision/inventory.py` — port, version, up/down, last backup on disk (not a status row), non-zero exit when anything needs attention, `--json` for a monitor. Sound design; currently reports `http 404` for every clinic (§3.1). |
| Uptime monitoring | None. `BACKUP_RUNBOOK.md:198` correctly notes that nothing here helps if the machine is off, and recommends an external uptime check. Not provided. |
| APM / metrics / tracing | None. |

The scheduler now runs in exactly one process: `_acquire_scheduler_lock`
(`app.py:327-358`) takes an OS-level exclusive file lock (`msvcrt.locking` on Windows,
`fcntl.flock` elsewhere) on `<backup_dir>/.scheduler.lock`, losers return at `:366-369`,
and the lock releases automatically on crash. `/healthz` distinguishes "another worker
owns it" from "dead" (`:259-266`). This replaces the prior behaviour where a 4-core box
ran nine schedulers — nine concurrent nightly backups and nine racing reminder runs.

## 4.5 Support burden per clinic

`docs/market/05_PRODUCT_READINESS.md` §3 builds a model: roughly **30 h/month at 10
clinics, 125 h/month at 50, 400+ h/month at 200** with no fleet tooling, falling to
10 / 30 / 110 with it.

I have not independently validated those figures — they are built from assumed call
rates (1.5 support calls per clinic per month) with **no operating history behind
them**, and a buyer should treat them as a model, not a measurement. There are no
customers and therefore no observed support data (§5.2).

What I can state from the code:

- Onboarding requires an operator with SSH and Docker on a Linux host. It is now one
  command plus a manual `certbot`. The 8–12 hours in the model assumed manual
  everything and pre-dates `provision.sh`; the provisioning half of it is genuinely
  reduced. Hand-entering a clinic's service catalogue, price list, staff and roles is
  not, and there is no catalogue import.
- Applying a release is one command **once §3.1 is fixed**. Until then it is manual
  SSH, and there is no `update.sh` alternative.
- Diagnosing a fault requires Sentry to have been enabled per clinic, and it is off by
  default.
- 47% of the route surface has no test coverage (§2.2), so regressions in those modules
  will be found by customers rather than by CI.

**The load-bearing assumption in the whole support model is that `upgrade.sh --all`
works.** It does not, today.

## 4.6 Scaling ceiling

`PROVISIONING.md:296-306` states the ceiling and where it comes from, and I agree with
both:

- **10–15 clinics per VPS.** Constraint: RAM (each clinic is a container with a 512 MB
  limit) and one shared PostgreSQL server. Beyond that, add a host — the scripts take
  `--root` and do not care which machine they run on, so this is horizontal and does
  not require a rewrite.
- **~20 clinics total** before the manual parts stop being tolerable: credentials
  maintained by hand in a password manager, `certbot` per domain, one operator running
  `--all` and watching it.
- **The shared PostgreSQL server is a single failure domain.** If it dies, every clinic
  on that host is down. `PROVISIONING.md:266` names this explicitly as the price of
  fitting ten clinics on a €5 VPS, and offers `--sqlite` on a clinic's own PC as the
  alternative for a customer who cannot tolerate it.

Per-clinic scaling — how many concurrent users or how much data one clinic instance
supports — is **not verified and not measured.** There is no load test, no query plan
analysis, no index review against realistic data volumes, and 60 indexes across 72
tables is thin for a reporting-heavy application. The largest known dataset is a demo
database of 15 invoices and 95 POS orders. **Any performance claim about this product
is currently unsupported by evidence, and a buyer should not accept one.**

---

# 5. What a buyer inherits

## 5.1 Included

| Asset | Detail |
|---|---|
| **Source repository** | Git, 386 tracked files, 51 commits, 3.9 MB of history, branches `main`, `feature/v3-complete-uiux-revamp`, `fix/audit-remediation` (current). Remote `github.com/abodahn/vet-platform`. |
| **Working tree state** | 3 modified files and 1 untracked test file are uncommitted at HEAD. Trivial, but confirm the sale is of a specific commit. |
| **~98,600 lines** | 38,261 Python, 33,866 templates, 7,657 CSS, 7,039 JS, 9,627 markdown, 1,202 SQL. |
| **Test suite** | 549 tests, 7,166 lines, all passing, no external services required. |
| **CI** | GitHub Actions on push and PR, Python 3.11 and 3.12. A PostgreSQL job exists but is non-blocking. |
| **Alembic baseline** | `0001_baseline` — 72 tables, described in `MIGRATIONS.md` as a verified zero-residue baseline. Plus `0002_audit_log_indexes` (safe to apply) and `0002_money_numeric` (prepared, tested, deliberately on hold — see §3.3). |
| **Documentation** | 24 markdown files, 9,627 lines, in the repository. Notably: `PROVISIONING.md` (306), `MIGRATIONS.md` (258), `SECURITY.md` (301), `deploy/BACKUP_RUNBOOK.md` (226), `docs/MONEY_PRECISION.md` (682), `docs/AUDIT_AND_PLAN_2026-07-25.md` (447), plus nine market-research documents totalling ~600 KB. Eight generated `.docx` deliverables (BRD, architecture, security, deployment, user guide, workflow manual) with their generator scripts, all tracked in git. |
| **Provisioning and fleet scripts** | `provision.sh`, `upgrade.sh`, `inventory.py`, `clinic_env.py` (~45 KB total). Designed correctly; §3.1 applies. |
| **Arabic localisation** | See §5.4. |
| **Self-hosted fonts and icons** | Cairo, DM Sans, bootstrap-icons — no CDN dependency at runtime, no third-party data leak on page view. Licence notices missing (§1.6). |
| **Figma designs** | 26 PNG mockups of a pet-owner portal. **Located at `D:\vet\figma\`, outside the repository.** Images only — no vectors, no JSON, nothing machine-consumable. Confirm explicitly whether they are in scope. |

## 5.2 Not included — state this plainly

- **No customers.** Zero. There is no customer list, no contract, no pilot.
- **No revenue.** None, at any point.
- **No operating history.** The software has never run at a paying clinic. Every
  operational number in every document in this repository, including the support model
  in §4.5, is a model rather than an observation.
- **No support organisation.** One developer, no second engineer, no on-call, no
  ticketing, no SLA.
- **No brand recognition.** "Aleefy" has no market presence. `templates/base.html:829`
  still carries "Powered by Aleefy AI" as vendor attribution, which a buyer will want
  to change.
- **No trademark, domain or app-store presence** established or transferred by the
  code.
- **No security certification, penetration test, or third-party audit.** `SECURITY.md`
  is a self-assessment. No independent review of the public endpoints has been done —
  `05_PRODUCT_READINESS.md` recommends one before any mobile client talks to them.
- **No data-protection assessment.** The product stores animal medical records and
  owner contact details. No DPIA, no retention policy beyond the 30-day backup
  window, no documented lawful basis, no data-subject-request mechanism.
- **No SLA, uptime record or incident history**, because there has been no operation to
  produce one.

## 5.3 Provenance and history quality

51 commits over 68 days (2026-05-21 → 2026-07-28), by one person under two git
identities (`Ahmed ElGohary <ahmed.elgohary@tandc.local>`, 34 commits;
`Ahmed Elgohary <Ahmed.lgohary.am@gmail.com>`, 17).

The history is short relative to the code volume. The first commit
(`Initial production deployment`) already contained most of the application: the
project existed for months before it was placed under version control, and the July
audit records the correction — 79 files, including three entire modules, sat
uncommitted at the point of baselining. **Pre-2026-05-21 development history does not
exist and is not recoverable.**

Commit message quality from 2026-07-25 onward is high and honest — messages name
defects rather than describe features (`fix: PostgreSQL had no backup at all`,
`fix: WhatsApp reminders no longer report 'Sent' when nothing was sent`). Messages
before that date are conventional feature/fix labels.

**A buyer should note that 16 of the 51 commits — nearly a third of the entire recorded
history — landed on 2026-07-28, the day this dossier was prepared.** Those commits
contain the backup rewrite, the provisioning system, per-clinic branding, the Arabic
PDF fix and the tablet work. That is a large body of substantially untested change
(§3.1 is one consequence) shipped immediately before a sale. **Weight it accordingly,
and consider requiring a stabilisation period or a warranty on that specific window.**

## 5.4 The Arabic work — quantified

This is the most defensible asset in the repository and it deserves a number.

Measured by parsing every template and Python file for `t('<en>', '<ar>')` calls:

| Measure | Value |
|---|---:|
| `t()` calls with two string literals | **4,424** |
| …whose second argument contains Arabic script | **4,421 (99.93%)** |
| Templates using `t()` | **169 of 170** |
| Files containing Arabic script | 178 |
| Arabic characters in the tree | 54,870 |

The three calls without an Arabic second argument are dynamic pass-throughs of the form
`t(mod.name, mod.name_ar)`, which is correct usage.

For context on how far this moved: the July audit measured `t()` in **24 of 166
templates**, with roughly **3,723 hardcoded English strings** in the remaining 141. The
commit `i18n: complete Arabic across all 166 templates` (2026-07-25) closed that. The
translation is consistent in register — Modern Standard Arabic, masdar forms for
buttons, Latin acronyms retained, brand names transliterated, directional arrows
mirrored — and RTL is implemented in the stylesheet, not bolted on.

Replacing this from scratch would be substantial: 4,400 UI strings translated and
placed, plus RTL layout work across 170 templates. At a professional rate for
technical MSA localisation this is a five-figure line item on its own, and it is the
single hardest asset in the repository for a competitor to replicate quickly.

**Two caveats that limit its value, both verified:**

1. The dynamic `t(x, x_ar)` calls read `*_ar` database columns that are **empty in seed
   data** — `users.full_name_ar`, `owners.full_name_ar`, `items.name_ar`,
   `suppliers.name_ar` were all measured blank in the July audit. Arabic *chrome* over
   English *data*. Fixing that is a data-entry problem at each clinic, not a code one,
   but it means the Arabic experience is incomplete out of the box.
2. **No documentation exists in Arabic.** Not the user guide, not the backup runbook,
   not the handover guide. The receptionist and the nurse who use this eight hours a
   day in Arabic have nothing to read in their own language.

---

# 6. Key-person and reconstruction risk

## 6.1 One developer, and what that means concretely

Every line was written by one person. There is no second engineer who has deployed,
restored or diagnosed this system. `docs/HANDOVER.md` and `docs/HANDOVER_GUIDE.md`
are module-URL tables, one of them addressed to a named doctor. Neither is a runbook a
stranger could execute.

The specific risk is not that the author leaves. It is that **the operational knowledge
that was never written down is invisible until it is needed.** §3.1 is the proof: four
files were written against an endpoint that does not exist, and the reason nobody
noticed is that the person who wrote them is the only person who would run them, on a
platform he does not have.

## 6.2 What is undocumented

| Area | State |
|---|---|
| Provisioning, upgrade, rollback, decommission | **Documented well** — `PROVISIONING.md`. Untested (§3.1). |
| Backup and restore | **Documented well** — `deploy/BACKUP_RUNBOOK.md`. |
| Migration policy and the two-head situation | **Documented well** — `MIGRATIONS.md`. |
| Money handling and the deferred migration | **Documented exceptionally well** — `docs/MONEY_PRECISION.md`. |
| The SQL dialect-translation layer in `models/database.py` | **Barely documented.** 3,264 lines, no ORM, the single highest-risk file in the repository. There is no architecture note explaining how `?` → `%s` translation, the savepoint policy, `RETURNING id` speculation or the connection lifecycle interact. `tests/test_sqlite_compat.py` and `test_db_layer.py` are the closest thing to a specification. |
| Which of the two WhatsApp endpoints is correct | **Undocumented and unknown** (§3.8). |
| Business logic — FEFO deduction, loyalty accrual, no-show risk scoring, attendance→payroll bridge, POS→invoice bridge | **Undocumented.** These are the domain rules that make the product valuable, and they exist only as code, largely untested (§2.2). |
| The permission vocabulary — what `ALL_PERMISSIONS` entries are meant to mean | Undocumented beyond the constant itself. |
| Deployment credentials for the existing GitHub remote, any DNS, any cloud accounts | Not in the repository. Must be transferred separately. |

## 6.3 What lives only in `.wolf/cerebrum.md`

The repository is managed with an AI-assistant context system. `D:\vet\.wolf\` holds
`cerebrum.md` (49 KB), `memory.md` (117 KB), `buglog.json` (105 KB), `anatomy.md`
(11 KB) and a token ledger.

These are **outside the `platform/` repository** and are not tracked by its git.

Their contents are a genuine but awkward asset. `cerebrum.md` accumulates project
conventions, prior corrections and do-not-repeat entries; `buglog.json` is a
structured history of defects with root causes and fixes. Together they are the closest
thing to a decision log this project has — and they are written for an AI assistant, in
a format that assumes a tool that reads them automatically. A human successor gets
value from them, but has to mine it.

Two concrete problems for a buyer:

1. **`anatomy.md` is broken.** It claims to index every file with a description and
   token estimate. As it stands it contains **four real file entries**; everything else
   is 600 lines of empty section headers, many of them for archived directories that no
   longer matter. The navigation aid the protocol depends on does not work.
2. **These files must be explicitly included in the sale.** They are in the parent
   directory, not the repository. If the asset transferred is `platform/` alone, the
   buyer gets the code and loses the accumulated reasoning behind it. **Ask for them.**

## 6.4 Time for a competent Python developer to become productive

Assuming a mid-to-senior developer fluent in Python and comfortable with Flask, SQL and
Docker, working full time, with the author available for questions:

| Milestone | Time | Reasoning |
|---|---|---|
| Environment running, tests green, application booting locally | **1–2 days** | Genuinely easy. `tests/conftest.py` builds a throwaway SQLite database, no external services, `pytest` just works. This is better than most projects of this size. |
| Can fix a bug in a single blueprint without breaking anything | **1–2 weeks** | Blueprints are consistent in shape and mostly independent. The templates are large but conventional. |
| Understands `models/database.py` well enough to change it safely | **3–4 weeks** | 3,264 lines, no ORM, a dialect-translation layer with non-obvious interactions between SQL rewriting, savepoints, `RETURNING id` speculation and connection lifecycle. Almost undocumented. This is the gate on everything else, because nearly every change touches it. |
| Can deploy, upgrade, roll back and restore a clinic unsupervised | **+1 week** | The documentation is good; the scripts have never run (§3.1), so the first week is spent making them work and building the confidence that comes from having done it. |
| Fully productive — can take a feature from request to deployed | **8–10 weeks** | Sum of the above plus the domain: veterinary workflow, Egyptian VAT, the Arabic conventions, and the undocumented business rules in §6.2. |

**Without the author available, add 3–4 weeks**, concentrated almost entirely in the
dialect layer and the undocumented business logic. There is no second person to ask,
and the tests cover 18% of the routes, so a stranger cannot use the suite to learn what
the system is supposed to do.

**Recommendation:** make a transition period contractual. Four to six weeks of the
author's availability, structured as: a joint provisioning run on a real host, a joint
restore drill, and a written architecture note on `models/database.py` — not general
availability, which tends to go unused until it has expired.

---

# 7. Summary for the reviewer

## The five things that matter most

1. **The fleet-operations layer has never been executed and cannot succeed as
   shipped** (§3.1). Four consumers poll a route that returns 404 because the blueprint
   providing it is deliberately unregistered. `upgrade.sh` therefore rolls back every
   upgrade. 1 day to fix; the finding matters more than the fix, because it shows the
   operational layer was written and not run.
2. **Single-tenant, definitively** (§3.2). `clinic_id` occurs twice, both times as a
   schema declaration, and is never read. 40–60 days to retrofit, with a residual
   cross-clinic patient-data-leak risk that no test would catch. The one-container-per-clinic
   architecture is the correct answer; a buyer planning shared multi-tenant SaaS should
   price a data-access-layer rewrite.
3. **The permission engine is applied to zero routes** (§3.4), and the Roles screen
   tells administrators otherwise. Worse than previously recorded. 7–9 days.
4. **Money is stored as binary float in 34 columns** (§3.3). No measured damage, the
   one live bug is fixed, the migration is written and tested and deliberately on hold
   for four sound reasons — the most important being that the test suite runs on SQLite,
   where the failure mode does not exist. 10–14 days to complete properly.
5. **18% route coverage** (§2.2). 549 tests pass, but 177 routes across 14 blueprints
   have zero coverage, including the 58-route WhatsApp module and the 31-route HR
   module. The CI PostgreSQL job is non-blocking, so a green tick is a statement about
   SQLite.

## Licence position

Clean. No GPL, AGPL or SSPL anywhere in 70 installed packages. fpdf2 is LGPL-3.0-only
and is dynamically imported from a pip-installed package, which satisfies the
relinking obligation by construction. Cairo and DM Sans are SIL OFL 1.1, which permits
commercial bundling and PDF embedding without fee. The only defect is clerical: **no
third-party licence notice of any kind ships with the software.** 0.5 days.

## What I would expect a buyer's reviewer to object to hardest

**That 16 of 51 commits — nearly a third of the entire recorded history — landed on the
day the sale documentation was written, and that the largest of them is the operational
layer, which does not work.**

The backup rewrite, the provisioning system, per-clinic branding, the Arabic PDF fix
and the responsive work all shipped on 2026-07-28. Some of it is excellent and
properly tested — `test_arabic_pdf.py` generates real PDF bytes and would catch a
regression. Some of it was never run at all: `provision.sh`, `upgrade.sh`,
`clinic-compose.yml` and `inventory.py` all target `/api/v1/health`, which 404s, and
`upgrade.sh` consequently reverts every upgrade it performs.

A reviewer will read that as evidence that the seller improved the asset immediately
before valuing it, and that the improvements were not validated. **That reading is
correct**, and it is why this dossier reports the code as it currently executes rather
than as the same-day documentation describes it — `PROVISIONING.md` already contains a
"known gaps" entry that the `Dockerfile` contradicts, and `05_PRODUCT_READINESS.md`
already contains two claims that its own repository disproved within hours.

The defensible response is not to argue. It is to fix §3.1, run a provisioning and
upgrade cycle on a real Linux host, and offer the buyer the log. That is one day of
work and it converts the single most damaging finding in this document into evidence
that the operational layer works.

---

*Prepared by direct measurement against commit `cb11154`. Every count in this document
is reproducible with the commands described. Where something could not be executed it
is marked "not verified" and should be treated as unproven.*
