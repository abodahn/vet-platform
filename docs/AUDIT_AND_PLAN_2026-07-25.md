# Aleefy Platform — Full Technical Audit & Improvement Plan

**Date:** 2026-07-25
**Scope:** `D:\vet\platform` (the live app) + surrounding repository
**Method:** Static analysis of 103 Python files (27,761 LOC), 166 templates (33,605 LOC / 1.48 MB),
376 routes, 55 DB tables. Runtime checks attempted against the local environment.

---

## 1. Where We Are

### The product

Aleefy is a **veterinary clinic ERP** — not a small app. 28 modules, 27 marked active:

| Domain | Modules |
|---|---|
| Clinical | Visits, Clinical (labs/vaccinations/surgery), Doctor workspace, Inpatient, Pharmacy, Imaging (AI photo analysis), Telemedicine |
| Front desk | Appointments, Waiting-room TV, CRM (owners/pets), Catalog, Petsy chatbot |
| Money | Finance (invoices/payments), Accounting (P&L, cashflow, budget), Procurement, Petshop POS |
| People | HR, Attendance, Payroll, Roles |
| Ops | Inventory (batches/FEFO/expiry), Boarding, Grooming, Reports, Report Builder |
| Platform | Auth, Settings, Notifications, Uploads, WhatsApp, AI Assistant, System, Migration, Backup |

**Stack:** Flask 3 + Jinja2, PostgreSQL (psycopg2, hand-rolled SQLite-compat layer, no ORM),
APScheduler, bcrypt, fpdf2, openpyxl, OpenAI-compatible AI client, Wapilot WhatsApp API.
Server-rendered HTML, no SPA framework. Bilingual EN/AR with RTL.

### What is genuinely good

This is the honest half of the report. The following are done properly and should not be touched:

- **File uploads** (`blueprints/uploads/routes.py`) — extension whitelist + magic-byte MIME
  verification + `secure_filename` + entity-type whitelist against path traversal + per-role access
  matrix + authenticated serving. Textbook.
- **Security headers** (`app.py:208–235`) — CSP, HSTS (conditional on TLS), nosniff, frame options,
  Permissions-Policy, server-banner removal.
- **Password handling** — bcrypt with a transparent SHA-256 → bcrypt migration path on login
  (`models/database.py:1775`), 12-char complexity policy with all four character classes.
- **Audit log** — login, logout, failed login, password change, module opens all recorded with
  real client IP (correct `X-Forwarded-For` leftmost extraction).
- **Route protection coverage** — 347 of 376 routes carry `login_required` / `role_required`.
  The 29 that don't are mostly deliberate public endpoints.
- **Operational plumbing** — scheduled nightly backup with failure notification to managers,
  daily WhatsApp reminder job, in-app notification centre, PDF invoices, Excel exports.
- **Breadth of business logic** — FEFO stock deduction, prescription→dispensing, loyalty points,
  no-show risk scoring, attendance→payroll bridge, POS→invoice bridge. Real domain depth.

### Verdict

**Feature-complete, engineering-fragile.** The functionality is at the level of a commercial
product. The engineering foundation underneath it — version control, connection lifecycle,
migrations, tests, logging — is at the level of a prototype. Every serious risk in this report
comes from that gap, not from missing features.

**Scorecard**

| Dimension | Score | Note |
|---|---|---|
| Feature coverage | 9/10 | Broader than most commercial vet PMS |
| Domain logic | 8/10 | Real depth, real workflows |
| Security posture | 6/10 | Good primitives, one open redirect, RBAC not enforced |
| Reliability | 4/10 | Connection leak + no fallback + silent failures |
| Performance | 5/10 | 3–5 DB round-trips per query, 174 KB unminified CSS |
| Maintainability | 3/10 | No git, no migrations, 76 silent excepts, 4 forked copies |
| Testability | 3/10 | Suite cannot run without manual PostgreSQL setup, no CI |
| **Overall** | **5.5/10** | High ceiling, weak floor |

---

## 1a. Remediation Status (updated live)

Branch `fix/audit-remediation`. All work verified by booting the app and running the suite, not by
reading code.

| ID | Defect | Status |
|---|---|---|
| D-01 | Version control | ~~Wrong finding~~ → 79 uncommitted files baselined (`d183280`) |
| D-02 | Connection leak, 247 sites | **Fixed** — `teardown_appcontext`; 50 raising requests leak 0 |
| D-03 | SQLite fallback unreachable | **Fixed** — app boots with zero PostgreSQL |
| D-04 | Open redirect on login | **Fixed** — `safe_redirect_target()` |
| D-05 | RBAC not enforced | Engine built, fail-safe; 376-route rollout pending |
| D-06 | `receptionist` role typo | **Fixed** + regression test derived from `_SEED_ROLES` |
| D-07 | Password printed to disk | **Fixed** — logs deleted, gitignored, print removed |
| D-08 | 3–5 round-trips per query | **Fixed** — now 1. SELECT 3→1, INSERT 5→1, failing INSERT 7→1 |
| D-09 | 76 silent excepts | Partially — ~15 removed so far across DB core and routes |
| D-10 | In-memory rate limiting | **Fixed** — DB-backed, keyed on IP *and* username |
| D-11 | Waiting-room PII | Overstated — route never worked. Fixed + masked + token-gated |
| D-12 | api_v1 "unauthenticated" | ~~Wrong finding~~ → decorators existed but read wrong session keys |
| D-13 | SQL shim fragility | **Fixed** — literal `?` preserved, `None` params for literal `%` |
| D-14 | No application logging | **Fixed** — rotation, correlation IDs, `X-Request-ID` |
| D-15 | No migrations | **Fixed** — Alembic, zero-residue baseline, 73 tables |
| D-16/17 | CSS + CDN | In progress |
| D-18 | Arabic incomplete | ~~Wrong numbers~~ → real problem is far larger, in progress |
| D-19 | Suite cannot run | **Fixed** — 127 errors → 0, 8 passing → 175 |
| D-21 | Secrets | Hardcoded API key found and removed — **rotation still owed by owner** |
| **NEW** | Money stored as `REAL` | Under investigation — see §2a |
| **NEW** | DDL before authentication | In progress |
| **NEW** | Test suite pointed at production DB | **Fixed** — excluded from collection |

### Corrections to the original audit

Four findings were wrong or overstated. The pattern is consistent and worth recording: **every
error came from static pattern-matching, and every correction came from executing the code.**

1. **D-01** — claimed no version control; had checked only `D:\vet`, not `D:\vet\platform`.
2. **D-18** — the regex `t\(\s*['"]` matches the tail of any identifier ending in `t(`, so
   `format('...')`, `split('...')` and `count('...')` were counted as untranslated i18n calls.
   Reported 1,016 calls / 201 missing; truth is 787 / 0.
3. **D-12** — the route-decorator scan looked for `login_required` / `role_required` and did not
   know about `require_auth` / `require_admin`, so 12 protected routes were reported as open.
4. **D-11** — reported as an active PII leak. The query had been raising on every call since it
   was written (wrong column name, swallowed by `except: pass`), so nothing was ever served.

Treat any remaining un-actioned finding in this document as a hypothesis until executed.

---

## 2. Defect Register

Every item below was verified in the code. File and line references are exact.

### P0 — Critical (fix this week)

**D-01 — 71 uncommitted files. ~~No version control at all.~~** *(corrected 2026-07-25)*

> **Correction.** The original finding claimed the project had no version control. That was
> wrong — it checked only `D:\vet`. The live app `D:\vet\platform` **is** a git repository with
> 17 commits, remote `github.com/abodahn/vet-platform`, on branch
> `feature/v3-complete-uiux-revamp`, and a `.gitignore` that already excludes `.env*` and
> `data/`. Version control was in place all along.

The real defect: **71 modified and 8 untracked files sat uncommitted**, including three whole
modules (`blueprints/imaging/`, `blueprints/api_v1/`, `models/sync.py`) that existed only in the
working tree. Weeks of work with no rollback point. Additionally `startup.log` and
`startup_err.log` were untracked *and* unignored while containing the plaintext admin credential
printed by `run.py:160`.

*Status:* **FIXED.** Both log files deleted and gitignored, all 79 files committed as
`d183280 chore: baseline commit before audit remediation`, work proceeding on branch
`fix/audit-remediation`. Note for future sessions: never `git init` at `D:\vet` — it makes
`platform` register as a submodule and silently stages nothing.

**D-02 — Database connection leak in 247 route functions.**
`models/database.py:56–81` caps the pool at 20 connections. 247 functions across the blueprints
call `get_db()` with **no `try/finally`**. Any exception raised between checkout and `conn.close()`
leaks that connection permanently. After ~20 unhandled errors the pool is exhausted and every
request fails until the process restarts. This is the most likely cause of "the app hangs after a
few hours."
*Fix:* make `get_db()` usable as a context manager everywhere and convert the call sites
mechanically (`with get_db() as conn:`), or register a Flask `teardown_appcontext` that returns any
connection stashed on `g`. The second is a ~20-line change that fixes all 247 sites at once.

**D-03 — The advertised SQLite fallback is dead code.**
`config.py:86–89` gives `DevelopmentConfig.POSTGRES_DSN` a hardcoded default, so `_PG_CONFIG` is
*always* populated (`app.py:36–41`). `get_db()` therefore never reaches its SQLite branch
(`models/database.py:339–350`). When PostgreSQL is unreachable the app does not degrade — it hard
crashes. Verified live: PostgreSQL on this machine refuses connections, and `bcrypt` is not even
installed, so the app **cannot currently boot**.
*Fix:* only call `configure_postgres()` when a DSN was explicitly supplied; on pool-creation
failure clear `_PG_CONFIG` so the SQLite path is genuinely reachable. Also pin and install
`requirements.txt` into a venv so the boot path is reproducible.

**D-04 — Open redirect on the login page.**
`blueprints/auth/routes.py:92–95` validates the `next` parameter with `next_page.startswith("/")`.
The string `//evil.com` passes that check and is a protocol-relative URL — the browser navigates
off-site. A phishing link `…/auth/login?next=//attacker.site` sends a user off the platform
immediately after they authenticate.
*Fix:* reject anything starting with `//` or containing `\`, or use
`urlparse(next).netloc == ""` as the test. One line.

**D-05 — Roles & Permissions administration does nothing.**
There is a `roles` table with a `permissions_json` column, a seeding routine
(`models/database.py:2876`), and a 28 KB admin screen (`templates/system/roles.html`). Grepping
the entire codebase for `has_permission` / `permission_required` returns **zero results**. All
authorization is hardcoded role-name lists inside `role_required(...)` decorators. Editing
permissions in the UI changes nothing whatsoever. This is a correctness bug *and* a trust problem —
an administrator believes they have restricted access when they have not.
*Fix:* implement `permission_required("module.action")` reading `permissions_json` (cached, it is
tiny), then migrate the 347 decorated routes to it. Roughly 3 days. Interim mitigation: hide the
Roles editor behind a "coming soon" flag so it stops lying.

**D-06 — Role name mismatch locks reception staff out of the POS.**
Canonical role in `_SEED_ROLES` is `reception`. `blueprints/petshop/routes.py:200` and `:244` gate
on `"receptionist"` — a role that does not exist. Reception staff get 403 on Pet Shop order
routes. The same stale name appears at `blueprints/system/routes.py:481` and `:495`.
*Fix:* rename to `reception` at those four sites. 10 minutes.

**D-07 — Admin password written to disk in plaintext.**
`run.py:160` prints `Default login: {user} / {password}` to stdout, which the launcher redirects
into `platform/startup.log`. That file currently contains a live admin credential.
*Fix:* delete the line (or print only the username). Delete and rotate the exposed credential.

### P1 — High (this month)

**D-08 — 3–5 database round-trips per logical query.**
`_PGCursor.execute` (`models/database.py:157–201`) opens a fresh admin cursor and issues
`SAVEPOINT` … `RELEASE SAVEPOINT` around *every single statement*. Every INSERT additionally opens
a nested savepoint and speculatively retries with `RETURNING id`. A page issuing 20 queries costs
60–100 network round-trips. This is the dominant cause of slow page loads and it is entirely
self-inflicted by the compatibility shim.
*Fix:* drop the per-statement savepoint. It exists only so that `executescript` can ignore DDL
errors — scope savepoints to `executescript` alone and let ordinary queries run bare. Expect a
2–4× latency improvement on query-heavy pages for a ~30-line change.

**D-09 — 76 silent `except: pass` blocks across 266 try blocks.**
Failures vanish. `blueprints/appointments/routes.py:652–676` renders an *empty* waiting room
instead of surfacing a database error. `_PGConn.executescript` (`models/database.py:284–287`)
swallows every DDL exception, so a broken schema migration is completely invisible. Debugging in
production is close to impossible.
*Fix:* replace `except Exception: pass` with `logger.exception(...)` plus a real fallback. Start
with the DB layer and the ten highest-traffic routes.

**D-10 — Login rate limiting does not survive multiple workers.**
`models/security.py:15–16` keeps attempt counters in a per-process dict. Under gunicorn with N
workers the real threshold is 5 × N attempts, and every restart resets it to zero. It is also
purely per-IP with no per-account lockout, so a distributed attempt against one account is
unimpeded.
*Fix:* move counters to a `login_attempts` table (or Redis) keyed on both IP and username. Half a
day.

**D-11 — Patient PII on an unauthenticated URL.**
`blueprints/appointments/routes.py:648` (`/waiting-room`) and `:695` (`/api/queue`) are
deliberately public and return **owner full names** alongside pet names and doctor names.
Anyone who guesses the URL reads today's client list.
*Fix:* show pet name + owner initial only, and gate the display behind a rotating display token or
an allowlist of clinic-LAN IPs.

**D-12 — 498 lines of unregistered, unauthenticated API shipped in the tree.**
`blueprints/api_v1/` is never registered in `app.py`. It contains 12 routes with no auth
decorator, including `POST /sync/push`, `POST /logs/cleanup` and `GET /system/diagnostics`. Its
dependencies `models/logging_db.py` and `models/sync.py` are dead for the same reason. The day
somebody registers that blueprint the platform acquires 12 open endpoints.
*Fix:* either delete the three files, or add authentication and register it deliberately. Do not
leave it as-is.

**D-13 — SQL translation layer is textually fragile.**
`_fix_sql` (`models/database.py:103`) does a blind `sql.replace("?", "%s")` — any literal `?` in a
query string is silently corrupted. Separately, a literal `%` in SQL executed with an empty
parameter tuple makes psycopg2 raise on the format character; there is one live instance at
`blueprints/telemedicine/routes.py:254` (`LIKE '%tele%'`), currently masked by a surrounding
`try/except`, so the telemedicine auto-pricing lookup silently never works.
*Fix:* short term, escape it (`LIKE '%%tele%%'`) and pass `None` rather than `()` when there are no
parameters. Long term this whole shim is the thing to retire (see §4).

**D-14 — No application logging.**
`platform/logs/` contains only `.gitkeep`. All output goes to stdout and is captured by a shell
redirect into `startup_err.log`. No rotation, no levels, no request correlation IDs, no error
aggregation. When a user reports "it broke this morning" there is nothing to read.
*Fix:* `RotatingFileHandler` to `logs/app.log`, structured formatter with a per-request UUID, plus
Sentry (free tier) for exception aggregation. Half a day.

**D-15 — No schema migration system.**
`init_db()` re-executes the full 55-table schema on every boot (`app.py:48`). Schema changes are
ad-hoc `ALTER TABLE` calls wrapped in `try/except` (`models/database.py:1599`, `:1614`). There is
no version number, no up/down, and no way to know which schema a given database is at.
*Fix:* adopt Alembic. Baseline the current schema as revision 0001 and require a migration for
every future change.

### P2 — Medium (quality and cost)

**D-16 — Three generations of CSS load on every page.**
`templates/base.html:21–23` loads `platform.css` (36 KB) + `aleefy.css` (71 KB) + `v3.css` (67 KB)
= **174 KB of unminified CSS**, plus 66 KB of JS. Two competing token systems coexist (`--cl-*`
from the old sheets, `--surface`/`--c-primary` from v3), which is why dark mode has historically
needed special-casing. No cache-busting query string, so users get stale CSS after a deploy.
*Fix:* audit which `--cl-*` rules are still live, fold everything into one sheet, minify, append
`?v={{ asset_version }}`.

**D-17 — Hard dependency on external CDNs.**
`base.html:15–19` pulls Google Fonts (DM Sans + Cairo) and jsdelivr bootstrap-icons. A clinic with
a poor connection — the normal case in the target market — gets a UI with no icons and fallback
typography. It is also an unnecessary third-party data leak on every page view.
*Fix:* self-host both. Adds ~400 KB to `static/`, removes two external dependencies and two CSP
exceptions.

**D-18 — Arabic mode is ~85% untranslated.** *(corrected 2026-07-25 — original finding was wrong)*

> **Correction.** The original claim was "1,016 `t()` calls, 201 missing Arabic (19%)". Both
> numbers were artefacts of a faulty scan: the regex `t\(\s*['"]` matches the tail of *any*
> identifier ending in `t(` — `format('...')`, `split('...')`, `count('...')`, `print('...')` —
> so it counted non-i18n code as untranslated strings. A proper quote/paren state-machine parser,
> self-checked against 14 synthetic edge cases, gives the true figures: **787 `t()` calls, 100%
> with an Arabic argument, 0 missing.** The 4 calls with a non-Arabic second argument are
> legitimate dynamic pass-throughs (`t(mod.name, mod.name_ar)`).

The real defect is larger and structural: **`t()` is used in only 24 of 166 templates.** The other
141 contain roughly **3,723 hardcoded English strings** with no i18n call at all. Worst screens:
`visits/visit_detail.html` (149), `hr/staff_detail.html` (107), `system/monitor.html` (76),
`hr/hr_attendance.html` (67), `inpatient/stay_detail.html` (62), `whatsapp/campaign_detail.html`
(61), `system/roles.html` (51), `landing.html` (50).

Compounding it, the dynamic `t(x, x_ar)` calls read `*_ar` database columns that are **empty in
seed data** — `users.full_name_ar` 10/10 blank, `owners.full_name_ar` 30/30, `items.name_ar`
15/15, `suppliers.name_ar` 4/4. So even the translated paths fall back to English for real records.
That is a data problem, not a template one, and needs its own fix.

*Status:* in progress on `visits/`, `crm/`, `hr/` — the daily-driver screens. The established
translation conventions (MSA register, masdar for buttons, Latin acronyms, transliterated brands,
mirrored directional arrows) have been documented from the existing 787 strings so the new work is
indistinguishable from the old. Remaining 141 files are a scoping decision, not a technical one.

**D-19 — The test suite cannot be run.**
`platform/tests/conftest.py` requires a live PostgreSQL at `localhost:5432` with credentials
`postgres/1234` hardcoded, and drops/recreates a database. PostgreSQL is currently down and
`bcrypt` is not installed, so the suite fails at import. The separate Playwright suite in
`D:\vet\tests` hardcodes the real admin password at `tests/conftest.py:12`. There is no CI, so
nothing enforces any of it.
*Fix:* make the suite run against SQLite or a throwaway container, read credentials from env, and
wire GitHub Actions to run it on push (which requires D-01 first).

**D-20 — Repository hygiene.**
Sitting in the working directory alongside the live app: four archived full copies, an entire
separate React/Vite project (`premium_pet_clinic_full_project/`), the legacy Flask app
(`ppc_diagnostics_work/`), `production_final_v1/`, a `node_modules/`, 15 mis-exported
extensionless `.xlsx` files at root, and the artifacts `C:vet.claude` / `C:vetlegacy_app.log` from
an old path bug. `.wolf/anatomy.md` still indexes the pre-reorganisation layout.
*Fix:* after D-01, move archives out of the working tree entirely (git history replaces them),
`.gitignore` the rest, re-scan anatomy.

**D-21 — Secrets in the working tree.**
Dev PostgreSQL password `1234` is hardcoded at `config.py:88` and `platform/tests/conftest.py:22`.
`.env`, `.env.development` and `.env.production` all live in the app directory. `.env.production`
holds `AI_API_KEY`. With no git, nothing is ignored yet — the moment D-01 happens these must be
excluded first.
*Fix:* `.gitignore` before the first commit; rotate the AI key and the admin password.

---

## 3. What to Add — Path to Best-in-Class

The competitive set is ezyVet, Provet Cloud, Covetrus Pulse, VetLinkPRO. Aleefy already matches or
beats them on module breadth. These are the gaps that decide deals.

### Tier 1 — Genuine differentiators (build these)

1. **Pet-owner mobile app / PWA.** The single biggest gap. Owners should book, see vaccination
   history, receive reminders, view invoices and pay, all from their phone. The Figma designs in
   `D:\vet\figma\` (26 screens: booking flow, wallet, medical records, vitals, dependants) already
   specify this — it is designed and not built. The public API foundation exists in
   `blueprints/public_api/`. **This is the highest-ROI thing on the list.**
2. **Online payments.** Paymob or Fawry integration (correct choice for the Egyptian market) —
   payment links inside WhatsApp reminders, card/wallet at the front desk, automatic
   reconciliation into Finance. Turns invoices into collected cash.
3. **Multi-branch, properly.** A `branches` table exists but `branch_id` is not enforced through
   queries. Real branch scoping — per-branch stock, per-branch P&L, cross-branch patient
   transfer — is what lets you sell to chains instead of single clinics.
4. **Clinical decision support on the AI you already have.** Drug interaction warnings,
   species/weight-based dosage calculation, breed-specific risk flags at the point of prescribing.
   You have the AI client and the visit data; this is wiring, not research.
5. **Lab machine integration.** Direct results from IDEXX / in-house analysers straight onto the
   visit record. This is the feature veterinarians ask about first in demos.

### Tier 2 — Table stakes for scale

6. **True offline mode.** Clinics lose internet. `models/sync.py` was started and abandoned. A
   service-worker PWA shell with an IndexedDB write queue and conflict resolution on reconnect.
7. **Two-factor authentication** for admin, finance, and owner roles. TOTP; ~1 day of work.
8. **Client self-service portal** (web sibling of the mobile app) — records, invoices, booking.
9. **Automated recall campaigns** — vaccination due, annual check-up, chronic-medication refill,
   driven off existing data through the existing WhatsApp channel. Direct revenue.
10. **Insurance claim workflow** — pre-authorisation, claim submission, settlement tracking.

### Tier 3 — Polish that wins demos

11. **Dashboard as a real BI surface** — cohort retention, revenue per doctor, service mix trends,
    no-show patterns. The no-show risk score already exists and is barely surfaced.
12. **Digital consent forms** with signature capture on a tablet, attached to the visit.
13. **Voice-to-text clinical notes** (Whisper) — the single biggest time-saver for a working vet.
14. **Full audit trail UI** — who changed which field, when, before/after. The audit table exists;
    only login events are written to it.
15. **Public API + webhooks** for third-party integration. `api_v1` is 80% written already (D-12).

---

## 4. The Plan

### Phase 0 — Stop the bleeding (Week 1, ~3 days)

| # | Task | Defect | Effort |
|---|---|---|---|
| 1 | `git init` + `.gitignore` + first commit + private remote | D-01, D-21 | 2 h |
| 2 | Fix the connection leak via `teardown_appcontext` | D-02 | 4 h |
| 3 | Fix the open redirect | D-04 | 15 m |
| 4 | Fix `receptionist` → `reception` (4 sites) | D-06 | 15 m |
| 5 | Remove password printing; rotate the credential | D-07 | 30 m |
| 6 | Make the SQLite fallback actually reachable | D-03 | 2 h |
| 7 | Restrict `/waiting-room` and `/api/queue` | D-11 | 2 h |
| 8 | Delete or authenticate `api_v1` + `logging_db` + `sync` | D-12 | 1 h |
| 9 | Rotate the AI API key and the admin password | D-21 | 30 m |

**Exit criterion:** the app boots from a clean checkout on a machine that has never run it, and
survives a forced exception without degrading.

### Phase 1 — Make it trustworthy (Weeks 2–4)

- Strip per-statement savepoints from `_PGCursor` (D-08) — biggest single performance win.
- Replace the 76 silent excepts with logging + real fallbacks, DB layer first (D-09).
- File logging with rotation and request IDs; add Sentry (D-14).
- Move rate limiting into the database, keyed on IP *and* username (D-10).
- Adopt Alembic; baseline the current schema (D-15).
- Make the test suite runnable without a manual PostgreSQL; wire CI on push (D-19).

**Exit criterion:** green CI on every push, and a real error log to read when something breaks.

### Phase 2 — Make the security real (Weeks 5–7)

- Implement `permission_required` reading `permissions_json`; migrate all 376 routes (D-05).
- Add TOTP 2FA for admin, finance, and owner roles.
- Extend the audit trail beyond auth events — field-level before/after on clinical and financial
  records — and build the audit UI.
- Independent security review of the public endpoints (`public_api`, `petsy`) before any mobile
  app talks to them.

**Exit criterion:** the Roles screen does what it says, and every clinical/financial mutation is
attributable.

### Phase 3 — Make it fast and beautiful (Weeks 8–10)

- Consolidate three CSS generations into one minified sheet with cache-busting (D-16).
- Self-host fonts and icons (D-17).
- Complete the 201 missing Arabic strings; evaluate Flask-Babel (D-18).
- Split `base.html` (56 KB) and `visit_detail.html` (51 KB) into components; move inline scripts
  into `static/js/`.
- Add DB indexes for the slow report queries; cache dashboard aggregates.

**Exit criterion:** first contentful paint under 1.5 s on a clinic-grade connection; Arabic mode
100% translated.

### Phase 4 — Grow the product (Months 4–6)

- Pet-owner PWA against a hardened `api_v1`, built to the existing Figma designs.
- Paymob/Fawry payments end to end.
- Proper multi-branch scoping.
- Clinical decision support on the existing AI client.
- Automated recall campaigns over the existing WhatsApp channel.

---

## 5. Recommended First Move

`git init`. Everything else in this document is a change to code that currently has no undo.

The three highest-leverage fixes after that — in order — are the connection leak (D-02, the thing
most likely to be causing real outages today), the savepoint overhead (D-08, the thing most likely
to be causing complaints about speed), and the permission system (D-05, the thing that turns a
convincing demo into a defensible product).
