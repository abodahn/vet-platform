# 05 — Asset Inventory

**What actually transfers on completion.**

Every count in this document was produced by running a command against the
repository on 2026-07-28, at commit `cb11154`. Items that could not be verified
from the repository are marked **not verified** and are not asserted.

---

## 1. Code

### 1.1 The repository

| | |
|---|---|
| Remote | `https://github.com/abodahn/vet-platform.git` |
| Git root | the `platform/` directory — **not** its parent |
| Commits on the working branch | **51** |
| First commit | `b4b304f`, 2026-05-21, "Initial production deployment" |
| Latest verified | `cb11154`, "feat: genuinely usable on a tablet" |
| Branches on the remote | `main`, `feature/v3-complete-uiux-revamp` |

Full history transfers with the repository. It is a real development history,
not a squashed dump: the audit-remediation work, the money-precision
investigation and the market research are all traceable to individual commits.

**Transfer condition.** At the time of writing, the seller's working branch
`fix/audit-remediation` exists **locally only** — it is not on the remote — and
the working tree has 3 modified files plus 1 untracked test file
(`tests/test_wapilot_config.py`). Confirm the branch is pushed and the tree is
clean before you accept the handover, or that work does not transfer.

`D:\vet` (the parent of the repository on the seller's machine) is **not** part
of the deliverable and is deliberately untracked. It contains archived backups,
`node_modules`, an unrelated React project, and a set of mis-exported `.xlsx`
files. Nothing there is needed to build or run the product.

### 1.2 What is in the repository

| Artefact | Measured |
|---|---|
| Python files | 131 files / 38,314 lines |
| Jinja templates | 170 files / 33,883 lines |
| Blueprints (feature modules) | 33 registered |
| URL rules | 379 |
| Database tables in `_SCHEMA` | 55+ (73 after migrations) |
| Test modules | 33 files / 7,166 lines |
| **Tests passing** | **549** (SQLite, verified `103.40s`) |
| Alembic migrations | 3 revisions, 2 heads (deliberate) |
| Stylesheets | 5 sources + built `app.min.css` with a `build.py` pipeline |

### 1.3 Test suite

`platform/tests/` — 549 passing tests, runnable with no external services:

```bash
cd platform && POSTGRES_DSN="" python -m pytest -q
```

**Honest scope statement:** the suite runs on SQLite only. The product's intended
production database is PostgreSQL. Coverage of the PostgreSQL-specific code paths
is not exercised by a green run. See §8.3.

Coverage worth naming because it is regression-protective rather than
box-ticking: `test_role_consistency.py` (AST-scans role names against
`_SEED_ROLES`), `test_db_layer.py` (re-derives the id-less-table list from the
schema), `test_security.py` (path traversal, redirect validation), `test_2fa.py`,
`test_branding.py` (spies on what is actually drawn into a PDF).

### 1.4 CI configuration

`.github/workflows/ci.yml` — GitHub Actions, two jobs:

- `tests` — SQLite, Python 3.11 and 3.12 matrix. **Blocking.**
- `tests-postgres` — PostgreSQL 16 service container. **Non-blocking**
  (`continue-on-error: true`), because `tests/test_postgres_full.py` still
  targets a hardcoded database name rather than `TEST_POSTGRES_DSN`. Documented
  in the workflow file itself.

No repository secrets are consumed. The PostgreSQL service uses
`POSTGRES_HOST_AUTH_METHOD: trust`, so there is nothing to hand over.

### 1.5 Deployment and provisioning assets

| File | What it is |
|---|---|
| `Dockerfile`, `docker-compose.yml`, `Procfile` | Container build and local compose |
| `gunicorn.conf.py` | Production WSGI config |
| `deploy/deploy.sh` | One-time host setup: docker, postgres, nginx, ufw |
| `deploy/clinic-compose.yml` | Per-clinic container template |
| `deploy/nginx.conf`, `deploy/vetplatform.service` | Reverse proxy + systemd unit |
| `scripts/provision/provision.sh` | Per-clinic provisioning; generates all five secrets fresh |
| `scripts/provision/upgrade.sh` | Per-clinic upgrade with rollback state |
| `scripts/provision/clinic_env.py`, `inventory.py` | Supporting tooling |

All environment-variable placeholders in `docker-compose.yml` are shell defaults
(`${SECRET_KEY:-change-me-in-production}`), not real values — verified in both
the current tree and the initial commit.

---

## 2. Documentation

### 2.1 Technical

| File | Content |
|---|---|
| `docs/AUDIT_AND_PLAN_2026-07-25.md` | Full technical audit. 21 numbered defects with `file:line`, a 7-dimension scorecard (overall 5.5/10), a 4-phase plan, and a remediation-status table recording what has since been fixed. It also self-corrects four of its own findings. |
| `docs/MONEY_PRECISION.md` | The money-as-float investigation: measured failure rate (~1 in 7 instalment invoices), the applied one-line fix, the written-but-deferred `NUMERIC` migration, and a 3-step rollout with impact estimates (550–800 call sites). |
| `docs/GAP_ANALYSIS.md`, `docs/BRD.md`, `docs/HANDOVER.md` | Earlier-generation documents. Superseded in part by the above and by this pack; retained for history. |
| `docs/security/` | 5 documents: access-control matrix, API security checklist, data classification, deployment checklist, incident response. |
| `PROVISIONING.md` | The operator runbook: adding a clinic, secret handling, directory layout, upgrade and rollback. |
| `MIGRATIONS.md` | Alembic usage, the two-heads interlock, and the `stamp` procedure for an existing production database. Contains one stale line (claims Alembic is not in `requirements.txt`; it is). |
| `SECURITY.md` | Security policy. |
| `deploy/BACKUP_RUNBOOK.md` | Backup and restore procedure. |
| `deploy/KOYEB_NEON_SETUP.md` | Managed-hosting setup notes. |

Eight `.docx` deliverables also exist in `docs/` (BRD, Technical Architecture,
Deployment & Operations Guide, Security & Compliance, User Guide & Operations
Manual, Workflow Process Manual, Stability Assessment, Platform Intelligence
Report), generated by the `gen_*.js` scripts alongside them. Their contents are
**not verified** against the current codebase and at least one
(`User_Guide_Operations_Manual_v1.0.docx`) is explicitly flagged as unverified in
the readiness document. Treat them as sales collateral of unknown accuracy, not
as engineering documentation.

### 2.2 Market research

**Nine** documents in `docs/market/`, not five:

| File | Subject |
|---|---|
| `01_COMPETITORS.md` | Competitive landscape and price anchors |
| `02_MARKET_SIZE.md` | Addressable market sizing |
| `03_PRICING_AND_ECONOMICS.md` | Unit economics; the perpetual-licence vs SaaS decision |
| `04_GOTOMARKET.md` | Channel and sales approach |
| `05_PRODUCT_READINESS.md` | Feature-by-feature readiness with a "sellable today: no" verdict and developer-day estimates |
| `06_ARABIC_MARKETS.md` | Non-Gulf Arabic expansion assessment |
| `07_SUBSAHARAN_AFRICA.md` | Sub-Saharan assessment |
| `08_ASIA.md` | Asia assessment (nine countries, all rejected, with reasons) |
| `09_PAYMENT_RAILS.md` | Merchant-of-record and payment-collection analysis for an Egyptian seller |

These are primary-source research with citations, including negative findings
(markets ruled out and why). Their value to a buyer is mostly in the rejections —
they are the expensive part to reproduce.

**Caveat:** `05_PRODUCT_READINESS.md` is dated 2026-07-28 and is **partly
superseded**. Several features it lists as ABSENT have since shipped — Arabic PDF
rendering, per-clinic branding, a version string, PostgreSQL backup, the data
import wizard, one-command provisioning. See `04_HANDOVER.md` §7 for what was
verified as now working.

---

## 3. The Arabic localisation

This is the largest single piece of specialist work in the deliverable and it
should be valued separately from the code.

### 3.1 Measured

| Metric | Verified count |
|---|---|
| `t(en, ar)` call sites in templates | **4,410** |
| Templates carrying at least one | **169 of 170** |
| Distinct English/Arabic string pairs | **2,678** |
| Pairs whose Arabic argument contains Arabic script | **2,675** |

Method: regex extraction of the two-argument `t()` form across every
`templates/**/*.html`. Counting call sites rather than unique pairs is the
honest way to describe the *work*, since each site was individually placed and
reviewed in context; 2,678 is the size of the glossary.

There are **zero** `t()` call sites in Python — strings produced in a view are
English-only. That is a known gap, not a hidden one.

### 3.2 What makes it more than a string table

- **Full RTL layout.** The app switches direction from `user['language']`. The
  v3 shell, sidebar, tables and forms all have RTL rules.
- **Working Arabic PDF rendering.** This is the part that is genuinely hard.
  `models/pdf_generator.py` combines the bundled Cairo TTFs, `arabic-reshaper`
  for positional letter forms, and `python-bidi` for run reordering — and works
  around a specific defect in the Cairo font: it is missing 54 of the Arabic
  Presentation Forms-B codepoints (the isolated forms), so the reshaper must be
  configured with `use_unshaped_instead_of_isolated: True` or common letters
  render as `notdef` boxes. Invoices, vaccination certificates and payslips all
  render Arabic correctly, including a clinic's own Arabic name.
- **Arabic data handling.** `migrations/excel_import.py` strips the invisible
  bidi and zero-width marks Excel injects (U+200B–200F, U+202A–202E, U+2066–2069,
  U+FEFF), NFC-normalises, and folds أإآ→ا / ى→ي / ة→ه for *matching only* while
  storing the user's own spelling. It also decodes `utf-8-sig → utf-8 → cp1256`,
  because Arabic CSV exported from Windows Excel is cp1256.
- **Egyptian phone normalisation.** Arabic-Indic digits → ASCII, then a
  documented rule set that folds `01012345678`, `+201012345678` and
  `0020 101 234 5678` to one canonical form.
- **Self-hosted fonts.** Cairo and DM Sans in `static/fonts/`, no CDN
  dependency — which matters for a clinic on a poor connection and for the
  Content-Security-Policy the app sets.

### 3.3 Known limits

Server-generated strings (flash messages, error text, some report headers) are
English-only. Currency is hardcoded EGP in roughly 235 places and the
`clinic.currency` setting does nothing. Nothing in the in-app help is Arabic,
because there is no in-app help.

---

## 4. Brand

Verified by inspecting the repository, not assumed.

| Asset | Status |
|---|---|
| Name **Aleefy / اليفي** | Used throughout the app, the marketing site and the domain. Transfers as a common-law/unregistered mark. |
| Logo — SVG | `platform/static/images/aleefy-logo.svg` (1,596 bytes) and an identical copy at `marketing/assets/img/aleefy-logo.svg`. **Exists, verified.** |
| Logo — PNG | `platform/static/images/aleefy-logo.png` (904 KB). **Exists, verified.** |
| Secondary mark | `platform/static/petsy/petsy-icon.svg` — the Petsy chatbot icon. |
| Brand colour | Teal `#0D7560`, with gold `#C9A84C` reserved for exactly two semantic uses. |
| Domain **aleefy.online** | Referenced as canonical throughout `marketing/index.html`. **Registration, registrar and expiry not verified** — the repository cannot prove ownership. Require the registrar transfer code in the sale agreement. |
| Email addresses | `info@aleefy.online`, `sales@aleefy.online` — configured in the marketing site. Mailbox hosting **not verified**. |
| Phone | `+20 112 767 7015` (and `wa.me/201127677015`) — appears in the marketing site as a real contact. **This is a personal number.** Confirm whether it transfers. |

### 4.1 The marketing site

`marketing/` — a single static page, 721 lines, no build step, no npm, no
framework, no CDN. Zero-JS bilingual toggle. Ships with self-hosted Cairo woff2
and 4 compressed product images. Deploy instructions for Cloudflare Pages and
GitHub Pages are in `marketing/README.md`.

Also present: `marketing/assets/screenshots/` — a **105-file, 29 MB** source
screenshot library of the running product, plus capture scripts
(`capture_new_screenshots.py`, `verify_site.py`). The page does not reference it
and it should not be deployed, but it is a genuinely useful asset for producing
future sales material.

**Two encumbrances on this item, stated plainly:**

1. **`marketing/` is not in the git repository.** The git root is `platform/`.
   The marketing site lives in the untracked parent directory and must be
   transferred as a separate file delivery, with its own agreement clause.
2. **`marketing/index.html` is not what is currently live.** The live site at
   `https://aleefy.online/` is a different, 9-page build whose source **does not
   exist anywhere in the deliverable**. The single-page version in this repo is
   the intended replacement. A buyer acquiring "the marketing site" is acquiring
   the rebuild, not the thing currently serving.

---

## 5. Third-party dependencies and licences

Read from installed package metadata in the verification environment, not from
memory. Direct dependencies declared in `requirements.txt` / `requirements-dev.txt`:

| Package | Version | Licence |
|---|---|---|
| Flask | 3.1.3 | BSD-3-Clause |
| Werkzeug | 3.1.8 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| MarkupSafe | 3.0.3 | BSD-3-Clause |
| itsdangerous | 2.2.0 | BSD |
| gunicorn | 26.0.0 | MIT |
| alembic | 1.18.5 | MIT |
| APScheduler | 3.11.3 | MIT |
| Flask-Limiter | 4.1.1 | MIT |
| limits | 5.8.0 | MIT |
| openpyxl | 3.1.5 | MIT |
| pyotp | 2.10.0 | MIT |
| arabic-reshaper | 3.0.1 | MIT |
| pytest | 9.1.1 | MIT |
| qrcode | 8.2 | BSD |
| bcrypt | 5.0.0 | Apache-2.0 |
| openai | 2.48.0 | Apache-2.0 |
| requests | 2.34.2 | Apache-2.0 |
| cryptography | 49.0.0 | Apache-2.0 **OR** BSD-3-Clause (your choice) |
| Pillow | 12.3.0 | MIT-CMU (HPND) |
| matplotlib | 3.11.1 | PSF-based (BSD-compatible) |
| numpy | 2.5.1 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 |
| **psycopg2-binary** | 2.9.12 | **LGPL** (LGPL-3.0+, with an OpenSSL exception) |
| **fpdf2** | 2.8.7 | **LGPL-3.0-only** |
| **python-bidi** | 0.6.11 | **LGPL** |

### 5.1 The licence answer a buyer needs

**Nothing in the dependency tree is GPL.** There is no copyleft obligation on
the application's own source code.

**Three dependencies are LGPL** — `psycopg2-binary` (PostgreSQL driver),
`fpdf2` (PDF generation) and `python-bidi` (Arabic bidi reordering). The LGPL
attaches to *those libraries*, not to code that uses them. The obligations it
imposes are:

- distribute the LGPL libraries' own source or a written offer for it (in
  practice: they are unmodified public PyPI packages, so pointing at PyPI
  satisfies this);
- do not modify them and ship the modification without releasing it;
- do not statically link them into a form the recipient cannot replace.

This product ships as Python source with a `requirements.txt` — the libraries
are separately installed, unmodified, and trivially replaceable by the recipient.
That is the least-encumbered possible LGPL posture. **It stops being trivial if
you ever freeze the app into a single-file binary** (PyInstaller, Nuitka) for the
on-premise perpetual-licence model, at which point the relink obligation becomes
real and needs legal review. Flag it now so it is not discovered later.

`sentry-sdk` is listed but commented out; it is genuinely optional (no DSN means
the package is not even imported).

### 5.2 Bundled fonts

`platform/static/fonts/` and `marketing/assets/fonts/`:

- **Cairo** (`Cairo-Regular.ttf`, `Cairo-Bold.ttf`, plus woff2 subsets) —
  licence read directly from the font's `name` table: *"This Font Software is
  licensed under the SIL Open Font License, Version 1.1."* Copyright 2009 The
  Cairo Project Authors. Version 3.130.
- **DM Sans** (woff2 subsets) — Google Fonts, OFL. **Not independently verified
  from the file** (the woff2 subsets carry no name table entry that was read).
- **Bootstrap Icons** (`bootstrap-icons.woff2`, 52-glyph subset) — MIT.

**What OFL permits, specifically:** the fonts may be used, studied, modified and
redistributed freely, including bundled with and sold as part of commercial
software. The conditions are that the font files are not sold *on their own*,
that any modified version is released under OFL too, and that a modified version
does not use the Reserved Font Name. This product embeds Cairo unmodified inside
an application, which OFL explicitly allows. There is no royalty and no
per-install fee.

**Gap:** no `OFL.txt` or `LICENSE` file is bundled alongside the fonts anywhere
in the repository. OFL requires the licence text to accompany redistribution.
This is a five-minute fix the buyer should make on day one.

---

## 6. What does NOT transfer

Stated explicitly so it cannot be inferred otherwise.

| | |
|---|---|
| **Customers** | None. There is no paying customer, no pilot, no letter of intent. |
| **Revenue** | None. |
| **Support contracts** | None exist. |
| **Trademark registration** | **None.** Verified: zero occurrences of "trademark", "®", "™" or "علامة تجارية" anywhere in the repository or marketing site. No registration is claimed and no evidence of one exists. The name transfers as an unregistered mark only. |
| **ETA / ZATCA e-invoicing accreditation** | **None.** ETA and e-invoicing appear **only** in `docs/market/*.md` as analysis. There is no implementation and no accreditation. Never present it as shipped. |
| **Deployed infrastructure** | Nothing is running that transfers. The live `aleefy.online` site is a different build whose source is not in the deliverable (§4.1). |
| **OpenRouter account** | The AI provider is OpenRouter (`AI_BASE_URL=https://openrouter.ai/api/v1`, default model `google/gemini-2.5-flash`). The account and its API key are the seller's personal account. The buyer must open their own. |
| **Wapilot account** | The WhatsApp gateway account (`api.wapilot.net`, ~800 EGP/month) is the seller's. See §8.4 — you may not want it. |
| **Sentry / S3 / any hosting account** | None configured in the deliverable; all are per-install env vars. |
| **The phone number `+20 112 767 7015`** | Personal. Confirm separately whether it is included. |
| **`D:\vet` parent directory** | Archives, `node_modules`, an unrelated React project. Not part of the sale. |

---

## 7. Known encumbrances — credentials to rotate

**Rotate all of these before deploying anything.** Two categories.

### 7.1 In git history — cannot be un-published

The password **`Ahmed@1122`** was committed. Verified present in:

| Commit | Files |
|---|---|
| `b4b304f` (initial) | `config.py`, `deploy/deploy.sh`, `deploy/KOYEB_NEON_SETUP.md` |
| `d183280` | `deploy/deploy.sh`, `deploy/KOYEB_NEON_SETUP.md` |
| `HEAD` (current) | `docs/market/05_PRODUCT_READINESS.md` — quoted there as an *example of the defect*, lines 107–108 |

It was used as **both** the seeded admin password and the PostgreSQL role
password, and it was shipped identically to every customer from a committed file
until commit `ad3ac4a` ("remove shipped credentials") removed it from the deploy
scripts. It remains recoverable from history forever unless the history is
rewritten. The audit register (D-21) records rotation as *"still owed by owner"*.

**Action for the buyer:** treat `Ahmed@1122` as public. Any environment that ever
used it must have both the admin password and the PostgreSQL role password
changed. Optionally scrub it from `docs/market/05_PRODUCT_READINESS.md`, though
leaving the documented example is defensible now that it is burned.

Checked and **clean**: no API key, token or DSN with a real value was ever
committed. `docker-compose.yml`'s `SECRET_KEY`, `SEED_ADMIN_PASS`,
`ANTHROPIC_API_KEY` and `WAPILOT_TOKEN` entries are shell-default placeholders in
every commit, including the first. `.env`, `.env.development` and
`.env.production` have never been tracked — only `.env.example`.

### 7.2 In the working tree — never committed, but present on the seller's disk

If the deliverable is handed over as a directory copy rather than a clean clone,
these files come with it. They hold live values:

| File | Live secrets it contains |
|---|---|
| `.env` | `POSTGRES_DSN`, `PLATFORM_SECRET_KEY` (128 chars), `PLATFORM_ADMIN_PASS` (= `Ahmed@1122`) |
| `.env.production` | `POSTGRES_DSN`, `PLATFORM_SECRET_KEY`, `PLATFORM_ADMIN_PASS`, **`AI_API_KEY`** (24 chars) |
| `.env.development` | `POSTGRES_DSN`, `PLATFORM_SECRET_KEY`, `PLATFORM_ADMIN_PASS`, **`AI_API_KEY`** (73 chars — an OpenRouter key) |

The two `AI_API_KEY` values bill the **seller's** OpenRouter account. Delete
these files on receipt and generate fresh values; `scripts/provision/provision.sh`
does this correctly for every new install.

A related historical leak, already remediated: `startup.log` /
`startup_err.log` used to capture the seeded admin password because `run.py`
printed it and the `.bat` launchers redirect stdout. The print is removed and
both filenames are gitignored. `PROVISIONING.md` restates the rule: **never
redirect provisioning output to a file.**

---

## 8. Other encumbrances

### 8.1 Dependency on a service the seller controls — none material

Verified: there is no phone-home, no licence server, no telemetry, no activation
check, and no hardcoded endpoint pointing at seller-owned infrastructure. The
application runs entirely on the buyer's hosts. This is a genuine strength and it
is worth stating in the sale.

The only seller-side artefact the code reaches for is the `freellmapi` Node
server that `run.py:78` tries to spawn from `~/freellmapi`. That directory is not
in the deliverable, the code handles its absence cleanly ("server dir not found —
skipping"), and the live AI path is plain HTTP to OpenRouter. It is dead code,
not a dependency.

### 8.2 The product is single-tenant, structurally

No table carries an enforced `clinic_id`. One clinic = one deployment. The
readiness document estimates a multi-tenancy retrofit at 40–60 developer-days.
This constrains the hosting model and therefore the unit economics — it is a
commercial fact, not just an engineering one.

### 8.3 The green test suite does not cover the production database

549 tests pass on SQLite. The PostgreSQL CI job is non-blocking because
`tests/test_postgres_full.py` calls `configure_postgres(dbname="vetclinic")` at
module scope with hardcoded credentials — importing it would point the whole
suite at a production database, so it is excluded from collection. Until that is
fixed, there is no automated evidence about PostgreSQL behaviour.

### 8.4 The WhatsApp integration carries terms-of-service risk

`api.wapilot.net` is an **unofficial WhatsApp Web gateway**, not the Meta Cloud
API. Using it violates WhatsApp's terms and a clinic's number can be banned.
Two incompatible client variants exist in the tree (`.net` and `.io`). Whether
Wapilot fronts the official Business API is **not verified**. A buyer should
assume this feature needs replacing with the official API before it can be sold
with a straight face.

### 8.5 Clinical-safety items the buyer inherits

`/ai/drug-interactions` is an LLM check with a fail-open default that the UI
renders as a green "Safe to prescribe". The CDS module ships with DRAFT drug data
and is deliberately non-blocking. Both are documented in `04_HANDOVER.md` §7.3.
These are liabilities, and a buyer selling to prescribing veterinarians should
price the fix in.

### 8.6 Unrounded invoice subtotal

`models/database.py:2776` in `create_invoice()` sums line totals without
rounding. The related rounding fixes landed; this one did not. Confined to the
stored `subtotal` column and reconciliation queries against
`SUM(invoice_lines.total)`. Small, but it is a money bug that is still open.

---

## 9. Transfer checklist

- [ ] `fix/audit-remediation` pushed to the remote; working tree clean
- [ ] GitHub repository ownership transferred (`abodahn/vet-platform`)
- [ ] `marketing/` delivered separately — it is outside the git root
- [ ] `aleefy.online` registrar transfer code provided; DNS control confirmed
- [ ] `info@` / `sales@` mailbox hosting resolved
- [ ] Decision recorded on the `+20 112 767 7015` number
- [ ] Buyer opens their own OpenRouter account; seller's key deleted
- [ ] All `.env*` files deleted on receipt and regenerated via `provision.sh`
- [ ] `Ahmed@1122` treated as public; every environment that used it rotated
- [ ] `OFL.txt` added alongside `static/fonts/` (OFL redistribution requirement)
- [ ] Written confirmation that no customer, contract, trademark registration or
      e-invoicing accreditation is included
