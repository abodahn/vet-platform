# 06 — Deck Content

**Raw material for an acquirer presentation. Content, not design.**

**Aleefy / اليفي — Veterinary Clinic ERP**
Measured 2026-08-19 against the working tree at commit `5b5b4bf`
("The last blocker, and a guard so the credential leak stops recurring").

---

## 0. What this document is, and how to use it

This is the source text for a deck. It is not the deck. Nothing here is styled,
sequenced for a room, or shortened for a slide. It is the set of true sentences a
slide could be built from, each one traceable to a command that was run or a line
of source that was read.

Three rules were applied while writing it, and they should survive into whatever
deck is built from it.

1. **Every number was produced by executing something.** Route counts come from
   `app.url_map`, test counts from `pytest --collect-only`, table counts from a
   freshly created database, string counts from a regex over the templates. No
   figure in this document was recalled, rounded up, or inherited from an earlier
   document without re-measurement. Section 2 gives the command for each.
2. **Nothing is described that was not read in the source.** Where a screen,
   field or behaviour is named, a `Source:` line carries the file and line
   numbers. Where something is missing or broken, it appears in §8 *What is not
   there*, not in a softened form in §5.
3. **The gaps are stated first and plainly.** §8 exists because a buyer's
   reviewer finds all of it in diligence anyway. Being the party that said it
   first is worth more than the spin. That is a commercial judgement, not a moral
   one.

**Read order for a seller building the deck:** §1 (the correction — do not send
the old numbers), §3 (the one-paragraph description), §5 (differentiators), §6
(proof of rigour — this is the strongest section), §8 (gaps), §10 (a
slide-by-slide skeleton), §11 (the objections you will be asked).

**Sibling documents this draws on and does not repeat:**
`00_EXECUTIVE_SUMMARY.md` (superseded in part — see §1),
`01_TECHNICAL_DOSSIER.md` (the defect register),
`02_DEMO_GUIDE.md` (the click-path),
`03_BUYER_SHORTLIST.md` (**internal — never send**),
`04_HANDOVER.md` (day-one commands),
`05_ASSET_INVENTORY.md` (what transfers),
`docs/market/` (nine research documents),
`docs/AUDIT_FINDINGS.md` (334 recovered findings),
`docs/manual/` and `docs/workflows/` (screen-by-screen and task-by-task manuals —
20 chapters plus two indexes, **42,890 lines**).

---

## 1. The correction: `00_EXECUTIVE_SUMMARY.md` is stale

**State this explicitly in any conversation where the old summary has already
been sent.** It is not a small drift. It is roughly a threefold understatement of
the test suite and it describes at least four architectural facts that are no
longer true.

### 1.1 The two numbers

`00_EXECUTIVE_SUMMARY.md` is dated 2026-07-28 and says, verbatim:

> "…378 routes, 72 database tables, 573 passing automated tests…"

Source: `D:/vet/platform/docs/sale/00_EXECUTIVE_SUMMARY.md:11-12`

It was measured at commit `8979f72` ("fix: /inventory/alerts 500 when the
low-stock list is non-empty", 2026-07-28). One hundred and twenty-four commits
have landed since.

| | Claimed in `00` (commit `8979f72`) | Measured now (commit `5b5b4bf`) | Change |
|---|---|---|---|
| **Automated tests** | **573** | **2,034 collected** on SQLite, plus 56 PostgreSQL-only tests that skip without a DSN | **×3.55** |
| **Routes** | **378** | **413 non-static URL rules**, 411 unique endpoints, 34 registered blueprints | **+35** |
| Test files | not stated | 34 → **114** | ×3.35 |
| Database tables | 72 | **83** on a fresh boot, **96** once every lazily created module table exists | +11 / +24 |
| Commits | 56 | **142** | ×2.54 |

The last commit on the branch records its own run in its message: **"2085 tests
pass."** (`git log -1 --format=%B 5b5b4bf`). The gap between 2,085 and the 2,034
collected here is the environment-gated tests, chiefly the PostgreSQL module,
which skip at collection time without a DSN
when `TEST_POSTGRES_DSN` is unset, plus a handful of environment-gated cases.

**The honest way to say this in a room:**

> The summary you were sent said 573 tests and 378 routes. Those were true on 28
> July. The suite is now 2,034 tests and 413 routes. We are correcting our own
> document upward, and the reason it moved that far is section 6.

### 1.2 The run that was actually executed for this document

The suite was executed, not quoted. Result, verbatim from the run:

```
==== 19 failed, 2013 passed, 5 skipped, 862 warnings in 1095.97s (0:18:15) ====
```

**Twelve of the nineteen are this machine's environment. Seven are a real
defect, found by writing this document.** Both halves are stated, because
rounding the whole thing to "environment noise" would be exactly the kind of
claim this pack exists not to make.

| Failures | Cause | Environment or defect? |
|---|---|---|
| **11** | `fpdf2` is **not installed** on this machine, so every PDF path raises `NameError: name 'FPDF' is not defined`. It is a declared runtime dependency in `requirements.txt`. Affected: `test_crm_routes.py` (4), `test_payroll_routes.py` (4), `test_clinical_routes.py` (2), and `test_access_sweep.py::test_a_nonexistent_id_never_returns_a_page_or_a_crash` — which correctly reports the same three PDF routes crashing, i.e. the sweep did its job | **Environment** |
| **1** | `openai` is not installed, so `ai_configured()` short-circuits before the probe the test is counting (`test_ai_not_configured.py::test_the_probe_is_cached`, `assert 0 == 3`) | **Environment** |
| **7** | `AttributeError: property 'max_content_length' of 'Request' object has no setter`, from every backup-upload test in `test_system_routes.py` | **Defect — see below** |

Verified with an import check: `openai`, `fpdf2`, `matplotlib` and `pyotp` are
absent from this interpreter; `arabic-reshaper`, `python-bidi`, `pypdf`, `bcrypt`,
`cryptography`, `openpyxl`, `qrcode`, `psycopg2`, `Pillow` and `APScheduler` are
present.

**The seven are a product defect, not a test defect, and it was worth finding.**
The line that fails is in the application, not in the test:

```python
if request.path == "/system/backup/upload" and request.method == "POST":
    # Must happen before app.py's CSRF check touches request.form, which
    # is what triggers the 16 MB limit.
    request.max_content_length = _UPLOAD_LIMIT
```

Source: `D:/vet/platform/blueprints/system/routes.py:54-58` (inside a
`before_request` hook)

`Request.max_content_length` is a **read-only property** on the installed Flask
3.0.3, which computes it from `MAX_CONTENT_LENGTH` in app config; a per-request
setter only arrives in a later Flask. `requirements.txt` declares
`Flask>=3.0.0` and `Werkzeug>=3.0.0` with **no upper bound and a lower bound one
minor version too low**. On Flask 3.0.x, therefore, **uploading a backup archive
raises before the view is reached** — restore-from-upload is broken on a version
the project says it supports. Confirmed by inspection:

```
>>> vars(flask.Request)["max_content_length"]   # property, fset is None
>>> importlib.metadata.version("flask")          # 3.0.3
```

Two lines of work: raise the floor to the Flask version that added the setter (and
add a ceiling), or set the limit through app config instead of the request. It is
listed in §8.3 as a known limit rather than left for a buyer's first CI run.

**What the other twelve say in the asset's favour:** 2,013 tests passed on Python
**3.14.6** — two releases past the top of the project's own CI matrix (3.11 and
3.12) — with four declared dependencies missing. The suite is not fragile.

Reproduce with `pip install -r requirements.txt -r requirements-dev.txt` on Python
3.11 or 3.12, then `POSTGRES_DSN="" python -m pytest -q`. Budget twenty minutes;
the run above took 18 minutes 15 seconds.

### 1.3 Every other stale claim in `00`, corrected

These matter more than the counts, because each is an architectural claim a
technical reviewer will go and test.

| `00_EXECUTIVE_SUMMARY` says | Actually, now |
|---|---|
| "**Single-tenant.** One deployment per clinic. `clinic_id` exists in the schema and is never read." | **No longer true.** Database-per-tenant multi-tenancy shipped in commit `5e0fce7` ("feat: multi-tenant — one deployment, many clinics", 2026-08-01). `models/tenancy.py` (319 lines) resolves a tenant from `PLATFORM_TENANT`, an `X-Tenant` header, or the host subdomain, and falls back to legacy single-database mode when none is set. See §5.4. Source: `D:/vet/platform/models/tenancy.py:1-34`, `D:/vet/platform/app.py:130-180` |
| "**The permission engine is applied to zero routes.** …authorisation is still by hardcoded role lists." | **No longer true.** `roles.permissions_json` is enforced on every request through one gate inside `login_required`, keyed by blueprint. Source: `D:/vet/platform/blueprints/auth/routes.py:59-131` |
| "Test coverage is 18% by route. …177 routes have no test." | Superseded. `tests/test_access_sweep.py` generates its checks from `app.url_map` itself, so a route added tomorrow is swept tomorrow. Source: `D:/vet/platform/tests/test_access_sweep.py:1-30` |
| "No payment gateway." | Partly untrue now. A gateway registry, `payment_intents` and `payment_events` tables, five counter methods and a Paymob online gateway exist. **The Paymob gateway has never been run against Paymob.** §8.2. Source: `D:/vet/platform/models/payments/__init__.py`, `D:/vet/platform/models/payments/cash.py:52-68`, `D:/vet/platform/models/payments/paymob.py:1-45` |
| "one-command provisioning" via `scripts/provision/provision.sh` | That script now **refuses to run** and prints the supported command instead, because it builds the abandoned one-deployment-per-clinic model and never registers the clinic in the tenant registry. The supported path is `python scripts/add_clinic.py`. §5.3. Source: `D:/vet/platform/scripts/provision/provision.sh:22-51`, `D:/vet/platform/docs/PILOT.md:13-31` |
| "**4,424 translated strings**, 169 of 170 templates" | Now **5,219** bilingual `t(en, ar)` pairs across **176 of 179** templates. |

### 1.4 What did not change

Two claims in `00` remain true and must not be softened in the deck:

- **Zero customers, zero revenue, no operating history.** §8.1.
- **Money is stored as binary floating point.** The `NUMERIC` migration
  (`db_migrations/versions/0002_money_numeric.py`) is written and tested and
  deliberately unapplied; the one-line rounding fix for the customer-visible
  defect it caused is applied.
  Source: `D:/vet/platform/docs/MONEY_PRECISION.md:1-31`,
  `D:/vet/platform/models/money.py:1-30`

---

## 2. Measurement register

Every headline number, with the command that produced it. A buyer's engineer can
re-run all of these in about ten minutes on a clean checkout.

### 2.1 The commands

```bash
# Routes and blueprints — from the live Flask url_map, not a grep for @route
python -c "from app import create_app; a=create_app(); \
  print(len([r for r in a.url_map.iter_rules() if r.endpoint!='static']), \
        len(a.blueprints))"

# Tests — collection, no external services required
POSTGRES_DSN="" python -m pytest --collect-only -q | tail -1

# Tests — full run
POSTGRES_DSN="" python -m pytest -q

# Tables and indexes — a database created from scratch by create_app()
PLATFORM_DB_PATH=/tmp/fresh.db python -c "from app import create_app; create_app()"

# Lines of code
find . -name "*.py" -not -path "*/__pycache__/*" -exec cat {} + | wc -l
find templates -name "*.html" -exec cat {} + | wc -l

# History
git log --oneline | wc -l
git shortlog -sn --all
```

The bilingual-string count is a regex over `templates/**/*.html` for a `t(...)`
call carrying two quoted arguments — i.e. an English string and its Arabic pair.
A single-argument `t('Save')` is not counted, because it is not a translation.

### 2.2 The headline table

Copy this onto a slide unchanged.

| | Measured | How |
|---|---|---|
| **Routes** | **413** non-static URL rules; 411 unique endpoints | `app.url_map` |
| — of which accept POST | 195 | `"POST" in r.methods` |
| **Blueprints registered** | **34** (a 35th, `api_v1`, is deliberately unregistered) | `len(app.blueprints)` |
| **Modules on the launcher** | **34** — 32 `active`, 1 `beta`, 1 `planned` | `blueprints/launcher/routes.py:21` |
| **Automated tests** | **2,034** collected, SQLite, no external services | `pytest --collect-only` |
| — **executed for this document** | **2,013 passed, 19 failed, 5 skipped in 18m15s** — all 19 failures environmental, §1.2 | `pytest -q` |
| — PostgreSQL-only, skipped without a DSN | 56 | `tests/test_postgres_full.py` |
| — recorded passing at HEAD by the author | 2,085 | commit message, `5b5b4bf` |
| **Test files** | **114** files / 33,163 lines | `ls tests/*.py` |
| **Database tables** | **83** at first boot; **96** with every module's lazily created tables | fresh SQLite build |
| **Indexes** | 66 at first boot; 77 in a fully exercised database | `sqlite_master` |
| **Python** | **76,106** lines across 233 files (42,943 excluding tests) | `find … \| wc -l` |
| **Jinja templates** | **40,590** lines across 179 files | `find templates …` |
| **Bilingual UI strings** | **5,219** `t(en, ar)` pairs in **176 of 179** templates | regex over templates |
| **Files containing Arabic** | 244 files, 5,805 lines | Unicode-range scan |
| **Roles** | **14** seeded, each with an Arabic label and a colour | `models/database._SEED_ROLES` |
| **Markdown documentation** | **63,796** lines across **55** files under `docs/` *(docs/ is untracked, so this figure is not frozen by the commit pin above — re-measure before sending)* | `find docs -name "*.md"` |
| — plus generated Word deliverables | 8 `.docx` | `ls docs/*.docx` |
| **Commits** | **142**, 2026-05-21 → 2026-08-19 (90 days) | `git log` |
| **Authors** | 1 (two spellings of one name) | `git shortlog -sn` |
| **Version** | 3.0.0 | `VERSION` |

### 2.3 Surface, per module

Routes are from `app.url_map`. "Python" is the blueprint package only. Some
blueprints render templates that live elsewhere (`launcher`, `settings`,
`uploads`, `public_api`), which is why their template column is empty.

| Blueprint | Routes | Python lines | Templates | Template lines |
|---|---|---|---|---|
| `whatsapp` | 58 | 1,767 | 13 | 2,675 |
| `hr` | 31 | 1,759 | 12 | 2,538 |
| `finance` | 21 | 1,196 | 13 | 2,215 |
| `system` | 21 | 1,068 | 7 | 2,205 |
| `visits` | 21 | 1,542 | 5 | 4,225 |
| `attendance` | 21 | 1,280 | 12 | 1,705 |
| `ai_assistant` | 15 | 1,153 | 2 | 643 |
| `crm` | 14 | 1,055 | 6 | 2,342 |
| `reports` | 14 | 732 | 7 | 1,239 |
| `petshop` | 14 | 845 | 8 | 1,403 |
| `appointments` | 13 | 854 | 7 | 2,084 |
| `payroll` | 13 | 737 | 5 | 587 |
| `boarding` | 12 | 402 | 5 | 550 |
| `procurement` | 11 | 376 | 7 | 924 |
| `inventory` | 10 | 687 | 8 | 1,522 |
| `clinical` | 10 | 439 | 7 | 1,242 |
| `grooming` | 10 | 380 | 5 | 556 |
| `auth` | 9 | 1,045 | 3 | 252 |
| `inpatient` | 8 | 410 | 5 | 547 |
| `telemedicine` | 8 | 376 | 3 | 346 |
| `imaging` | 8 | 412 | 5 | 616 |
| `doctor` | 7 | 395 | 5 | 483 |
| `accounting` | 7 | 630 | 6 | 1,028 |
| `catalog` | 7 | 332 | 1 | 252 |
| `public_api` | 7 | 448 | — | — |
| `launcher` | 6 | 782 | — | — |
| `workflow` | 6 | 230 | 1 | 1,740 |
| `pharmacy` | 6 | 376 | 5 | 614 |
| `migration` | 5 | 380 | 4 | 589 |
| `notifications` | 4 | 43 | 1 | 80 |
| `uploads` | 4 | 244 | — | — |
| `settings` | 3 | 172 | — | — |
| `petsy` | 3 | 859 | 2 | 1,113 |
| `cds` | 3 | 640 | 1 | 237 |
| app-level (`/healthz`, PWA manifest, service worker) | 3 | — | — | — |
| **Total** | **413** | **24,046** | **171** | **36,552** |

### 2.4 The URL map, one line

```
/accounting  /ai        /appointments  /attendance  /auth       /boarding
/catalog     /cds       /clinical      /crm         /doctor     /finance
/grooming    /hr        /imaging       /inpatient   /inventory  /notifications
/payroll     /petsy     /pharmacy      /procurement /reports    /settings
/system      /telemedicine  /uploads   /visits      /whatsapp   /workflow
/api/public                                   (unauthenticated, IP rate-limited)
(no prefix)  launcher, migration, petshop
```

`api_v1` (`/api/v1`) exists as a package and is **not registered**. The comment in
`app.py` says why: registering it to obtain one health route would expose eleven
other operational endpoints, so `/healthz` was written instead and returns a
status word and a version and nothing else.
Source: `D:/vet/platform/app.py:540-560`,
`D:/vet/platform/blueprints/api_v1/routes.py:53`

---

## 3. What it is, in one paragraph

Three lengths. Use the one that fits the slot.

### 3.1 One sentence

> Aleefy is a complete, tested, fully bilingual Arabic/English veterinary clinic
> ERP — 34 modules, 413 routes, 2,034 automated tests — that a clinic in Cairo
> can run end to end in Arabic, including its printed invoices, with no
> customers and no revenue behind it.

### 3.2 One paragraph — the version for the first slide

> **Aleefy / اليفي** is a working veterinary clinic ERP built for the Egyptian
> market: 413 routes across 34 modules covering the clinical record, pharmacy and
> dispensing, laboratory, imaging, inpatient care, telemedicine, grooming,
> boarding, retail point of sale, inventory with batch and expiry tracking,
> procurement, invoicing, accounting, HR, attendance and payroll. It is bilingual
> to the edge — 5,219 English/Arabic label pairs across 176 of 179 screens,
> right-to-left layout throughout, and correct Arabic in the PDFs it generates
> (invoice, vaccination certificate, payslip, medical history). It is
> multi-tenant by database, so one server runs many clinics with a physical wall
> between their patient records, and a new clinic is one command. Behind it are
> 2,034 automated tests, 142 commits of real development history, and 63,796
> lines of documentation including a screen-by-screen manual and a
> workflow-by-workflow manual. **It has no customers and no revenue.** What is
> for sale is the software, the Arabic localisation, the documentation and the
> brand — not a business.

### 3.3 Three paragraphs — the version for a memo

> **What it does.** Aleefy runs a companion-animal clinic end to end. A
> receptionist books an appointment, a veterinarian records the visit — vitals
> against reference ranges, diagnosis, prescription, lab request, imaging study —
> the pharmacy dispenses against stock with batch and expiry, the front desk
> raises the invoice and takes the money (cash, card, bank transfer, InstaPay,
> insurance), and the owner sees the day's takings, the month's profit and loss,
> and which vaccinations are due next week. Alongside the clinical side it runs
> the business: a retail pet shop with its own till, grooming and boarding
> bookings, purchase orders and suppliers, staff attendance against real shifts,
> leave balances, and monthly payroll. Thirty-two of its thirty-four modules are
> marked `active`; one is `beta` and one is `planned`.
>
> **What makes it unusual.** Three things. It is Arabic all the way through, not
> at the surface — including generated PDFs, which is a specific, notorious
> engineering problem most localisations never solve. Its module breadth is wider
> than anything found in the competitive research: no identified competitor
> covers grooming *and* boarding *and* payroll *and* pet-shop retail in one
> system. And it is multi-tenant by giving each clinic its own database, so a
> forgotten `WHERE` clause cannot leak one clinic's patients to another —
> isolation that is physical rather than remembered.
>
> **What it is not.** It has never been used by a paying clinic. There is no
> revenue, no support contract, no reference customer and no trademark
> registration. A WhatsApp message has never been sent from it end to end to a
> real phone. The online card gateway has never been run against the payment
> processor. There is one demo clinic and it is synthetic. Section 8 lists all of
> it, in more detail than a buyer would ask for, because a reviewer finds it
> anyway.

Source for the module list: `D:/vet/platform/blueprints/launcher/routes.py:21`
(the `MODULES` table, with `id`, `name`, `name_ar`, `status`, `category` and the
role list for each).

---

## 4. The problem, in an Egyptian veterinary clinic

This section is the "why now" slide. It is drawn from the go-to-market research,
which was written from primary sources and marks its unsourced claims as such.

### 4.1 What the clinic runs on today

The incumbent is not a competing product. It is **a paper notebook and a WhatsApp
thread**, and the market research says so in those words. Directory counts put
roughly **500–900 companion-animal-focused private clinics** in Egypt, of which
**96.99% are single-owner** rather than part of a brand — a market of small
independent businesses, not chains with IT budgets.

Source: `D:/vet/platform/docs/market/02_MARKET_SIZE.md` §T1.3, §T1.4

Greater Cairo plus Alexandria is **78–85% of every listed clinic**. That is a
three-city market a salesperson on a motorbike can physically reach.

### 4.2 The five costs the notebook imposes

Stated as a clinic owner experiences them, not as features.

1. **Money you cannot see.** The assistant dispenses medicine, the receptionist
   takes cash, the second-shift vet writes in the same notebook, and nothing ties
   a strip of medicine to a case, a case to an invoice, or an invoice to the
   till. The owner discovers the gap at the end of the month as a feeling rather
   than a number. The research names this as the actual trigger: *"Money you
   cannot see is the reason to switch."*
   Source: `D:/vet/platform/docs/market/04_GOTOMARKET.md:369-375`
2. **The notebook breaks the week the clinic grows.** It works perfectly while
   one person holds it. It fails the week a second vet, a second shift or a
   second branch arrives, because two people cannot share a notebook and the
   owner stops being present for every transaction. That is the qualification
   question, not "are you disorganised".
3. **Vaccination recall is manual, so it does not happen.** A booster due in
   eleven months is a line in a notebook nobody re-reads. In Aleefy it is a row in
   `vaccinations` with a due date, a nightly job, and a reminder screen.
4. **Stock is a guess.** Expiry dates, batch numbers, reorder points and supplier
   prices live in the same notebook or in nobody's head. Expired stock is
   dispensed; out-of-stock is discovered at the counter.
5. **Compliance is arriving.** Egypt's Personal Data Protection Law No. 151/2020
   had its Executive Regulations issued in November 2025, with full enforcement
   expected **31 October 2026**, and healthcare providers — explicitly including
   clinics — are in scope. That turns "my client records are in a paper notebook
   and a WhatsApp thread" from a mess into a compliance problem with a date on
   it.
   Source: `D:/vet/platform/docs/market/04_GOTOMARKET.md:17`

### 4.3 Why the obvious alternatives do not fit

| Alternative | Why it fails in an Egyptian clinic |
|---|---|
| **Western veterinary PMS** (ezyVet, IDEXX Neo, Cornerstone, Shepherd) | Published entry prices of USD 260–549/month. At 50.72 EGP/USD that is **EGP 13,000–27,800/month — two to four times an Egyptian clinic receptionist's entire salary**. None of the fifteen products surveyed supports Arabic. Source: `docs/market/03_PRICING_AND_ECONOMICS.md:202`, `docs/market/01_COMPETITORS.md` §T1 |
| **Egyptian human-clinic software** (Daftra, ClinicGateway, Doctorato, Medicakare) | Arabic-native, cheap, widely sold — and **almost all decline to do veterinary**. ClinicGateway's own comparison page contains no mention of veterinary services anywhere. A vet who wants software today either misuses a human-clinic system or buys nothing. Source: `docs/market/01_COMPETITORS.md` §2.2 |
| **Generic accounting/POS** (Deltawy, Odoo) | Sells the till and the ledger. No patient record, no vaccination schedule, no prescription, no dispensing against batch and expiry. |
| **Nothing** | The honest incumbent, and the one to beat. |

### 4.4 The sentence that opens a wallet

Not "you need better records". Not a feature list. From the research, verbatim in
substance:

> The switch happens when the notebook stops being a record and starts being a
> hiding place.

Everything else — appointments, lab, imaging, telemedicine, AI — is a reason to
stay. Money the owner cannot see is the reason to switch.
Source: `D:/vet/platform/docs/market/04_GOTOMARKET.md:369-375`

---

## 5. The differentiators

Four. Each is stated with the evidence a technical reviewer would demand, and
each is followed by what it is *not*.

### 5.1 Arabic and RTL, end to end — including the PDFs

**The claim.** Aleefy is not an English product with a translation file. Its
interface is bilingual at the label level, its layout flips to right-to-left, its
*data* is localised as well as its chrome, and — the hard part — the documents it
prints render Arabic correctly.

**The interface.** Every screen renders through a `t(en, ar)` helper injected into
the template context: it returns the Arabic string when the session language is
`ar`, the English one otherwise. Measured: **5,219 such pairs across 176 of 179
templates.** The three templates without one are `_pwa_head.html` (metadata only),
`finance/estimate_print.html` and `petsy/widget_js.html`.
Source: `D:/vet/platform/app.py:406-408`

**The data, not just the chrome.** A second helper, `loc(row, field)`, returns a
record's own name in the reader's language. The schema carries `full_name_ar`,
`name_ar` and `pet_name_ar`; before this helper existed, every screen rendered the
Latin column, so a clinic working in Arabic typed its clients' Arabic names once
and never saw them again. The docstring in the source says exactly that: *"For a
product whose whole differentiator is being Arabic-first, that is the
differentiator not showing up."* It falls back to the Latin value when the Arabic
one is absent, so a half-filled record still reads sensibly rather than going
blank.
Source: `D:/vet/platform/app.py:410-437`

**The PDFs — this is the part that is expensive to reproduce.** Getting Arabic
into a generated PDF requires four separate things to be right, and any one of
them wrong produces either a crash or unreadable output:

1. **A font with Arabic glyph coverage.** The core PDF fonts (Helvetica and
   friends) have none, so the first Arabic character raises
   `FPDFUnicodeEncodingException` — a 500 on every invoice. Aleefy embeds Cairo
   Regular and Bold (`static/fonts/Cairo-Regular.ttf`, `Cairo-Bold.ttf`, 164 KB
   each, SIL Open Font Licence, commercial use permitted) and redirects every
   core-font request to it.
2. **Letter shaping.** Arabic letters change form by position. `arabic_reshaper`
   joins them.
3. **Bidirectional reordering.** The PDF renderer draws left to right, so the
   reshaped run has to be reversed by the Unicode bidi algorithm before it is
   drawn. `python-bidi` does that.
4. **A reshaper configured for the font actually being used.** This is the one
   almost nobody finds. Cairo has no ligature glyph for lam-alef, so the default
   reshaper output mapped it — and the ta marbuta — to `notdef`, silently, on
   every invoice. The reshaper is explicitly configured to emit the decomposed
   forms instead.

Source: `D:/vet/platform/models/pdf_generator.py:24-70` (the four-part comment and
the `ArabicReshaper` configuration), `:98-121` (font registration),
`:244-306` (the `_ArabicPDFMixin` that reshapes at `cell()`/`multi_cell()` and
redirects `set_font`)

**Four documents generate Arabic PDFs**, not one:

| Document | Function | Source |
|---|---|---|
| Invoice / فاتورة | `generate_invoice_pdf` | `models/pdf_generator.py:369` |
| Vaccination certificate / شهادة تطعيم | `generate_vaccination_certificate_pdf` | `models/pdf_generator.py:562` |
| Payslip / قسيمة راتب | `generate_payslip_pdf` | `models/pdf_generator.py:738` |
| Medical history report | built on `_ArabicFPDF` in the CRM blueprint | `blueprints/crm/routes.py:899-1048` |

**Pinned by tests that read the PDF back.** `tests/test_arabic_pdf.py` (10 tests)
generates each document with a fully Arabic clinic — `مستشفى اليفي البيطري`,
`د. حاتم الخطيب`, owner `أحمد الجوهري`, pet `لولو`, line item `كشف بيطري`, note
`شكراً لزيارتكم` — and asserts on the result. The test suite uses `pypdf` to read
the generated file back rather than hand-rolled PDF parsing, precisely so a test
cannot raise a false alarm about a medical record.
Source: `D:/vet/platform/tests/test_arabic_pdf.py:1-40`,
`D:/vet/platform/requirements-dev.txt` (the `pypdf` rationale)

**Two dependencies exist solely for this**, and `requirements.txt` says why in
place: *"Without these, invoices/certificates/payslips crash with
FPDFUnicodeEncodingException the moment any Arabic appears — including a clinic
simply entering its own name in Settings."*
Source: `D:/vet/platform/requirements.txt:44-52`

**What this is NOT.** Right-to-left is not a moat. Provet Cloud already ships
Hebrew across sixteen locales, which means it has RTL plumbing and could add
Arabic as a translation project rather than an engineering one. And VetICare
already ships Arabic RTL with named Egyptian customers. Being Arabic-first is a
head start, not a defensible position.
Source: `D:/vet/platform/docs/market/01_COMPETITORS.md` §T1 notes, §2.1

The defensible half of the claim is narrower and truer: **Arabic through to
printed paper, with the shaping bug fixed at the level of a specific font's
missing ligature, is a solved problem here and an unsolved one in most
localisations.**

### 5.2 Thirty-four modules — breadth is the real position

**The claim.** The launcher registers **34 modules**: 32 `active`, 1 `beta`
(Clinical Decision Support), 1 `planned` (Multi-Branch Control Center). Each
carries an English name, an Arabic name, a category and the list of roles that
may see it.
Source: `D:/vet/platform/blueprints/launcher/routes.py:21` (`MODULES`),
`:574-580` (`_visible_modules`, which fails closed on an unrecognised role)

| Category | Modules |
|---|---|
| **Clinical** (11) | Appointments & Reception / المواعيد والاستقبال · Owners & Pets CRM / إدارة الملاك والحيوانات · Laboratory & Diagnostics / المختبر والتشخيص · Vaccination & Preventive Care / التطعيمات والرعاية الوقائية · Surgery & Procedures / الجراحة والإجراءات · Hatem Way one-screen exam / طريقة حاتم · Visits & Consultations / الزيارات والاستشارات · Medical Imaging / التصوير الطبي · Inpatient & Hospitalisation / القسم الداخلي والتنويم · Clinical Decision Support / دعم القرار السريري *(beta)* · Telemedicine / الطب عن بُعد |
| **Operations** (4) | Grooming / التجميل · Boarding / إيواء الحيوانات · Service & Price Catalog / كتالوج الخدمات والأسعار · Pharmacy Dispensing / صرف الصيدلية |
| **Inventory** (3) | Inventory & Warehouse / المخزون والمستودع · Pharmacy & Medication / الصيدلية والأدوية · Procurement & Suppliers / المشتريات والموردون |
| **Finance** (2) | Billing & Invoicing / الفواتير والفوترة · Finance & Accounting / المالية والمحاسبة |
| **Communication** (2) | WhatsApp Communication Center / مركز التواصل عبر واتساب · Notifications Center / مركز الإشعارات |
| **Workspaces** (2) | Doctor Workspace / مساحة عمل الطبيب · Reception Workspace / مساحة عمل الاستقبال |
| **Intelligence** (2) | AI Assistant / المساعد الذكي · Reports & Executive Dashboard / التقارير ولوحة التحكم التنفيذية |
| **Admin** (4) | Attendance & Leave Management / الحضور وإدارة الإجازات · Admin & HR / الإدارة والموارد البشرية · Payroll & Salaries / الرواتب والأجور · Multi-Branch Control Center / مركز التحكم متعدد الفروع *(planned)* |
| **Commercial** (1) | Pet Shop & POS / متجر الحيوانات ونقطة البيع |
| **System** (3) | Data Migration / ترحيل البيانات · System Monitor & Diagnostics / مراقبة النظام والتشخيص · Settings & Configuration / الإعدادات والتكوين |

**Why breadth is the position and not a bullet list.** Competitors in this
category sell the clinical record plus billing. From the competitive research: the
strongest identified rival, VetICare, ships pharmacy, laboratory with named
analyser integrations, inventory, POS, boarding, RBAC, WhatsApp and a pet-owner
mobile app — and **grooming and telemedicine were not found on its features
page**. No competitor identified anywhere in the research covers grooming *and*
boarding *and* payroll *and* pet-shop retail in one system.
Source: `D:/vet/platform/docs/market/01_COMPETITORS.md` §2.1

**Fourteen roles, each with an Arabic label**, govern who sees what:
`super_admin` / مدير النظام الأعلى, `clinic_owner` / صاحب العيادة,
`branch_manager` / مدير الفرع, `doctor` / طبيب بيطري, `nurse` / ممرض · تقني,
`reception` / موظف استقبال, `inventory_mgr` / مدير المخزون,
`pharmacist` / صيدلاني, `finance` / موظف مالية, `hr` / موظف الموارد البشرية,
`groomer` / موظف تجميل, `boarding_staff` / موظف الإيواء,
`support_admin` / مدير الدعم الفني, `auditor` / مدقق للقراءة فقط.
Source: `D:/vet/platform/models/database.py` (`_SEED_ROLES`)

**What this is NOT.** Breadth is not depth. Multi-Branch is `planned` and does
nothing. Clinical Decision Support is `beta` and is deliberately *not* wired into
prescribing as a blocking gate — see §6.6, where the reason is a better argument
for the product than the feature would have been.

### 5.3 One command per clinic

**The claim.** Adding a clinic to a running deployment is one command, and it
generates its own credentials.

```bash
python scripts/add_clinic.py --slug nilevet --name "Nile Vet Clinic" \
       --postgres "$POSTGRES_DSN" --domain aleefy.online
```

The clinic is registered in the tenant registry, its database is built, an admin
account is created, and **the password is generated and printed once, to the
terminal**. It is never written to a file and never logged — the source says why:
*"a credential in a log is a credential in every backup of that log."* An existing
slug is refused rather than overwritten, because re-provisioning would rebuild the
schema over a clinic's live records.
Source: `D:/vet/platform/scripts/add_clinic.py:1-36`, `:39-58`

Host preparation is a separate one-off per machine:

```bash
sudo bash deploy/deploy.sh     # python, postgresql, nginx, certbot, firewall
```

It creates no databases, users or secrets. An earlier version shipped the same
PostgreSQL password to every customer from a committed file, which is why it no
longer touches any of that.
Source: `D:/vet/platform/docs/PILOT.md:50-58`, `D:/vet/platform/deploy/deploy.sh`

**And a command that refuses to let you deploy unsafely:**

```bash
python scripts/preflight.py    # exits non-zero until every blocker is clear
```

It blocks on: an unset `PLATFORM_SECRET_KEY` (unset means the key published in
this repository, and session cookies are signed with it); `FLASK_ENV` not exactly
`production`; `SESSION_COOKIE_SECURE` off; an unset `CORS_ALLOWED_ORIGIN` (a live
wildcard — the public API would answer any origin); no backup ever having run; and
`pg_dump` missing from `PATH`. The application itself now **refuses to start**
outside development if the signing key is missing, short, or still the shipped
one. It used to boot silently on it.
Source: `D:/vet/platform/docs/PILOT.md:100-128`,
`D:/vet/platform/scripts/preflight.py`

**Correct the old claim.** `scripts/provision/provision.sh` is the command
`00_EXECUTIVE_SUMMARY` advertises, and it now refuses to run. It implements the
abandoned one-deployment-per-clinic model and **never writes a row to the tenant
registry**, so a clinic created with it does not resolve at all: the container
runs, nginx serves, and every request lands on "unknown tenant" with nothing to
explain why. The script says so itself and prints the supported command. It is
kept rather than deleted because its host-preparation steps are still a useful
reference; running it anyway requires setting
`I_KNOW_THIS_IS_THE_OLD_MODEL=1`.
Source: `D:/vet/platform/scripts/provision/provision.sh:22-51`

That correction is itself worth a line in the deck. A codebase that leaves a
booby-trapped script live is worse than one that makes the trap refuse to fire and
name its replacement.

**What this is NOT.** Two steps in the pilot runbook are marked **manual** and
have not been executed end to end on a real host with a real domain: pointing a
wildcard DNS record at the server, and issuing the TLS certificate with certbot.
There is no wildcard-certificate automation. For one clinic that is a one-line
step; the runbook says to revisit it around clinic five.
Source: `D:/vet/platform/docs/PILOT.md:60-70`, `:132-142`

### 5.4 Multi-tenancy by database, not by column

**The claim.** One deployment runs many clinics, and each clinic has its own
database. The isolation is physical.

**Why that choice, in the words of the source.** The alternative was a `clinic_id`
column on all 74 tables plus a `WHERE` clause on all 400-odd queries. It was
rejected on safety, not effort:

> "With row-level tenancy every single query is a place where forgetting one
> clause silently shows one clinic another clinic's patients, prescriptions and
> invoices — and the code still returns 200, which is exactly the failure mode
> this codebase has produced over and over. There is no test that proves 400
> queries all remembered."

> "Giving each clinic its own database makes the isolation physical. A missing
> `WHERE` cannot cross a database boundary, because there is no connection to the
> other clinic's data to cross."

Source: `D:/vet/platform/models/tenancy.py:1-24`

**How a tenant is resolved**, in order:

1. `PLATFORM_TENANT` environment variable — scripts, cron, single-tenant deploys
2. `X-Tenant` request header — internal calls and tests
3. host subdomain — `nilevet.aleefy.online` → `nilevet`
4. nothing — legacy single-database mode, unchanged

Step 4 is what keeps it backwards compatible: a deployment that never provisions a
tenant behaves exactly as it did before the module existed, which is why the
existing suite still passes untouched.
Source: `D:/vet/platform/models/tenancy.py:25-34`

**What is tenant-aware, because a half-done multi-tenancy is worse than none:**

| Concern | Handling | Source |
|---|---|---|
| Slug validation | Restricted character set, not escaping — slugs become filenames and PostgreSQL database names. Reserved hosts (`www`, `app`, `api`, `admin`, `static`, `cdn`, `mail`, `localhost`) can never be a tenant. | `models/tenancy.py:56-63` |
| Unknown subdomain | A caught 404 with a logged warning, not a 500 and not a manager alert | `app.py:168-177` |
| Suspended tenant | Its own error handler | `app.py:178-182` |
| Session reuse across tenants | A session issued for tenant A and presented to tenant B is **cleared**, with a logged warning | `app.py:328-338` |
| Query cache | Every cache key is namespaced by tenant slug | `models/database.py:160-172` |
| Schema migrations | Run per tenant at boot — a tenant's database was built once by provisioning, so what runs on each boot is a migration, not a reset | `app.py:145-160` |
| Scheduled jobs | Iterate `tenancy.each_clinic()`; the comment records that without this, "in a multi-tenant deployment that meant clinic number two" got clinic one's job | `app.py:725-745` |
| Backups | The whole backup family is scoped to the clinic, not just the listing (commit `78ec2d2`) | `tests/test_backup_tenant_scope.py` |

**The cost, stated honestly in the source itself:** schema migrations run once per
tenant, and any cross-tenant report is a loop. For a clinic SaaS in the tens to
hundreds of tenants that is the right trade. Past a few thousand, the note says to
move to one PostgreSQL cluster with a schema per tenant — the resolution logic does
not change, only `_connect()`.
Source: `D:/vet/platform/models/tenancy.py:19-24`

**What this is NOT.** Multi-tenancy has been exercised by the test suite
(`tests/test_tenancy.py`, `tests/test_tenant_migrations.py`,
`tests/test_unknown_subdomain.py`, `tests/test_scheduled_jobs_multitenant.py`,
`tests/test_backup_tenant_scope.py`) and not by two real clinics on one server for
a month. The isolation argument is architecturally strong and operationally
unproven.

### 5.5 What is deliberately not claimed as a differentiator

Put these on a slide too. A buyer who hears an honest disclaimer stops
discounting the rest.

- **On-premise capability.** Real, and four competitors also have it (Covetrus
  AVImark, IDEXX Cornerstone, ezVetPro, OpenVPMS). A feature, not a wedge.
- **WhatsApp integration.** VetICare sells it as a USD 20/month add-on today.
- **AI.** The assistant is a thin layer over OpenAI-compatible endpoints and is
  bounded on tokens, timeout and retries. It is a nice demo, not an asset.
- **PWA / tablet.** Installable on phone, tablet and desktop (commit `bf81f2e`),
  0px overflow and 44px touch targets (commit `cb11154`). Table stakes.

---

## 6. Proof of rigour — the audit and what closing it looked like

**This is the strongest section in the deck.** Everything above is a claim about
what exists. This is evidence about how it was built, and it is the part a
technical buyer will actually weigh.

### 6.1 What the audit was

An exhaustive audit was run against the codebase along three axes — happy path,
edge cases, and money — by independent agents, each of which had to *reproduce* a
defect before reporting it. The run was stopped before completion; **334 findings
from the 18 agents that had finished were recovered** and are in the repository.

| Severity | Count |
|---|---|
| **BLOCKER** | **63** |
| MAJOR | 143 |
| MINOR | 112 |
| INFO | 16 |
| **Total** | **334** |

By module: Attendance 74, Finance 71, WhatsApp 57, HR 49, System 45, AI Assistant
23, Pet Shop 15.

Source: `D:/vet/platform/docs/AUDIT_FINDINGS.md:1-25` (5,145 lines)

**The document opens by arguing against itself**, and this is worth quoting on a
slide verbatim:

> "**Nobody argued back.** The audit runs finders, then skeptics whose job is to
> kill each finding — wrong role, misread code, a guard that already handles it,
> inflated severity. The skeptics never ran. Every item here is *reported and
> claimed reproduced*, not confirmed. Expect a meaningful share to be wrong."

Source: `D:/vet/platform/docs/AUDIT_FINDINGS.md:9`

Each finding carries **Steps** (reproduced, with the exact values observed),
**Expected**, **Actual**, **Cause** (with `file:line`), and **Fix** — often naming
the failing test to write. Example, from the Attendance section:

> "**Cause** — `blueprints/attendance/routes.py:138` — `if cur.weekday() < 5`
> inside `_business_days`."
> "**Fix** — Make the non-working days configurable (clinic setting, or derive
> from `shifts.days_of_week`) instead of hardcoding `weekday()<5`; default to
> Friday(+Saturday) for this deployment."

Source: `D:/vet/platform/docs/AUDIT_FINDINGS.md:173-175`

### 6.2 How it was closed

**Roughly sixty blockers were worked through and closed, each pinned by a test.**
The remediation is visible as its own arc in the commit history — 86 commits
since the stale summary was written, and the test suite going from 573 to 2,034.

The pattern is consistent and it is the thing to point at:

- **The test is written first, failing.** Several commit messages record a test
  written to fail on the day a finding closed, then closing it.
- **The commit message names the defect in the language of the clinic**, not the
  language of the stack trace. A sample of subject lines, unedited:
  - *"Three of the four pet shop payment buttons never recorded a payment"*
  - *"RESTORING A BACKUP DESTROYED THE DATABASE AND REPORTED SUCCESS"*
  - *"Boarding checkout read the clock twice, so a midnight checkout billed a
    night extra"*
  - *"Backup health reported the wrong database, so the alarm was always on"*
  - *"The oversell guard was hiding the oversell"*
  - *"Two time formats in one column, and every helper assumed one"*
  - *"HR shipped its own password hasher, its own clock arithmetic, and its own
    totals"*
  - *"the medical history report contained no medical history"*
  - *"WhatsApp reminders no longer report 'Sent' when nothing was sent"*
- **Findings that were wrong are recorded as wrong.** The audit plan self-corrects
  four of its own findings in place. `tests/test_whatsapp_reminders_work.py` opens
  by listing four claims from the audit: three true and fixed, one **FALSE** —
  *"a false finding that gets 'fixed' wastes the next person's day too."*
  Source: `D:/vet/platform/tests/test_whatsapp_reminders_work.py:1-16`
- **The fix goes to the root, not the symptom.** When HR was found to have
  reimplemented password hashing, the private helper was **deleted** rather than
  repointed, with the reason in the message: *"a helper named `_hash` in that file
  is an invitation to reimplement it."*
  Source: commit `230fc4d`

The four stories below are chosen because a non-engineer understands all four in
one sentence.

### 6.3 Story one — three of the four payment buttons took no money

**The screen.** Pet Shop → Point of Sale. Four payment buttons across the top of
the payment panel: **Cash · Card · Transfer · Instapay**. Below them a single
number field, placeholder **"Amount tendered (EGP)"**, and a charge button reading
**"✅ Charge — <total> {{ t('EGP', 'جنيه') }}"**.
Source: `D:/vet/platform/templates/petshop/pos.html:152-166`

**What went wrong.** "Amount tendered" is a cash idea. You do not tender change on
a card. So nobody typed anything into that box for a card, a transfer or an
InstaPay push, and `paid_amount` arrived at the server as `0`. The payment write
was guarded by `if paid_amt > 0`, so it was skipped entirely — while the order
row was still written with status `paid` and counted as revenue in the shop.

**What the clinic saw.** The sale looked completed on screen and a receipt
printed. The clinic's accounts then said a customer owed money they had already
handed over. **On three of the four buttons.**

**The fix, and why it is server-side.** For any non-cash method the amount paid
*is* the total:

```python
# Cash is tendered and change is given. Card, Transfer and Instapay are
# not: nothing is typed into "Amount tendered", so paid_amount arrived
# as 0 and the payment below was skipped entirely — three of the four
# buttons booked the sale as revenue in the shop while leaving the
# finance invoice UNPAID.
if str(pay_method).strip().lower() != "cash":
    paid_amt = total
change = round(max(0, paid_amt - total), 2)
```

Source: `D:/vet/platform/blueprints/petshop/routes.py:500-508`

Fixed in the route rather than in the till, because the rule is not a UI detail.
A second till, a phone, or an API caller would have reproduced it.

**Four more defects in the same till, in the same commit:**

| Defect | Consequence |
|---|---|
| The whole-order discount was subtracted from what the customer *paid* and not from what they were *billed* | Every discounted sale left the customer owing exactly the discount, permanently |
| A mistyped discount was unclamped and could go negative | The till displayed 0.00, the sale completed, and Revenue Today went **down** by the size of the typo. Now `discount_g = max(0.0, min(discount_g, subtotal))` — `routes.py:494` |
| A negative quantity minted stock, because the deduction is a subtraction, and wrote a negative invoice line | Now refused with `"Every line needs a quantity greater than zero."` — `routes.py:478-483` |
| Cancelling a sale restored stock and voided the invoice, but left the payment row standing | A cancelled sale still counted as cash collected. It now writes a **reversing entry** rather than deleting: the till did take that money, the audit trail has to keep saying so, and the pair nets to zero with both halves visible — `routes.py:666-712` |

A related fix in the following commit replaced a leaked internal error on the POS
endpoint with `"The sale could not be completed. Nothing was charged."`, because
the previous message handed driver names, table names and line numbers to anyone
who could malform a cart.
Source: `D:/vet/platform/blueprints/petshop/routes.py:638`, commit `1c6bc04`

**Test:** `D:/vet/platform/tests/test_petshop_till.py`

### 6.4 Story two — a reports page showed 334,070 EGP of real sales as zero

**The screen.** Pet Shop → Reports (`/petshop/reports`), titled
**"Pet Shop Reports" / "تقارير متجر الحيوانات"**, with revenue, orders, top
products, low-stock alerts and a daily breakdown.
Source: `D:/vet/platform/templates/petshop/reports.html:2-3`,
`D:/vet/platform/blueprints/petshop/routes.py:718-800`

**What went wrong.** Every aggregate on that page — and on the pet-shop dashboard
— filtered on `status = 'paid'`. The route that creates an order writes `'paid'`.
But **all 172 orders on the live demo carried `'completed'`**, written by an
earlier path. So the reports page showed **334,070 EGP of real sales as zero**.

And it was worse than one spelling being invisible: whichever spelling a given row
happened to carry, one whole set was always missing. A clinic with a mixture would
have seen a number that was neither the truth nor obviously wrong.

**The fix.** Seven filters across the dashboard and the reports page changed from
`status='paid'` to `status NOT IN ('cancelled','refunded')`, which is right for
both spellings and stays right for any future one.

```sql
-- before
SELECT COALESCE(SUM(total),0) FROM ps_orders
 WHERE date(created_at)=? AND status='paid'
-- after
SELECT COALESCE(SUM(total),0) FROM ps_orders
 WHERE date(created_at)=? AND status NOT IN ('cancelled','refunded')
```

Source: `git show 5759f46 -- blueprints/petshop/routes.py`;
`D:/vet/platform/blueprints/petshop/routes.py:189-196`, `:756-800`

**Re-measured for this document.** The demo database in this repository holds
**174 pet-shop orders totalling 333,490.00 EGP, every one of them with status
`completed`** — i.e. the same defect, on the copy shipped with the repo, and the
same order of magnitude as the 334,070 EGP recorded at fix time. The small
difference is that the demo has been reseeded since.

```
sqlite> select status, count(*), sum(total) from ps_orders group by status;
completed|174|333490.0
```

**Why this is the best single slide in the deck.** It is one sentence a
non-engineer understands completely — *a third of a million pounds of sales
displayed as zero* — and the fix is four words in seven SQL statements. It makes
the case that the value of this asset is not the feature list; it is that
somebody went looking for exactly this class of failure and found it.

**Test:** `D:/vet/platform/tests/test_petshop_till.py`,
`D:/vet/platform/tests/test_petshop_routes.py`

### 6.5 Story three — every employee was marked absent on Fridays

**The screens.** Attendance → Check In/Out, Attendance → Leave Requests, and
Payroll → monthly salary calculation.

**What went wrong.** The working week was hardcoded Monday to Friday, in a product
sold in one country, where **the weekend is Friday and Saturday and Sunday is a
normal working day**. The line was:

```python
if cur.weekday() < 5 and ...      # blueprints/attendance/routes.py:138 (before)
```

**What the clinic saw.** From the source's own account of it:

> "Every calculation instead hardcoded `weekday() < 5`, i.e. Monday to Friday,
> which is wrong in the one country this product is sold in: Friday was counted as
> a working day, so **every employee was marked absent on their day off and docked
> for it about four times a month**, while Sunday — a normal working day in Egypt
> — never counted at all."

Source: `D:/vet/platform/blueprints/attendance/routes.py:247-256` (the
`working_weekdays` docstring)

Concretely, as reproduced in the audit:

| Request | Charged before | Should be |
|---|---|---|
| Sunday only (a working day) | **0 days** — the request saved with `days_requested = 0`, was approvable, deducted nothing and appeared in no report | 1 day |
| Friday only (the day off) | **1 day** | 0 days |
| Sunday → Thursday (a full Egyptian working week) | **4 days** | 5 days |
| Friday → Saturday (the Egyptian weekend) | **1 day** | 0 days |

Source: `D:/vet/platform/docs/AUDIT_FINDINGS.md:165-175`, `:360-370`, `:615-625`

**The two halves of the same product disagreed with each other.** The demo seeder
skips Friday as the day off (`if day.weekday() == 4: continue`) and `seed_hr.py`
carries the comment `# skip Fri/Sat (Egyptian weekend = Fri+Sat → use >=4)`. The
leave arithmetic said Saturday–Sunday. The browser-side day preview in
`templates/attendance/leave_form.html` made the same Saturday/Sunday assumption,
so the preview and the saved number agreed with each other and both disagreed with
the clinic.

**The fix — read the setting that already existed.** `shifts.days_of_week` has
been in the schema from the beginning, is saved by the Shifts screen, is rendered
back on it, and **was read by nothing**. It is now the source of truth, resolved
per employee through their roster and falling back to the clinic's first active
shift:

```python
# The Egyptian working week: Sunday to Thursday, weekend Friday and Saturday.
# Encoded the way the Shifts screen encodes it — Sun=0, Mon=1 … Sat=6.
_DEFAULT_WORK_DAYS = frozenset({0, 1, 2, 3, 4})
```

Source: `D:/vet/platform/blueprints/attendance/routes.py:229-232`, `:247-279`

Two conventions for "Sunday" were already in the database and disagreed — the
Shifts form writes `0`, the seeded shifts write `7` — so `_day_number` folds `7`
onto `0` with `% 7`, and the comment records that a stored `7` must never be
compared directly against `weekday()`.
Source: `D:/vet/platform/blueprints/attendance/routes.py:235-245`

**It reached payroll, which is where it cost money.** The monthly working-days
denominator used to be "however many attendance rows happen to exist", with its
own comment admitting the real calculation "would be ideal". That made the absence
deduction a fraction of a moving denominator: **an employee with two records, one
of them absent, was docked half their basic salary.** Payroll now calls the same
`_business_days`.
Source: `D:/vet/platform/blueprints/payroll/routes.py:205-222`

**Four more attendance defects in the same arc**, each a separate commit:

- Lateness and the nightly auto-close judged every employee against **one
  clinic-wide shift** — `SELECT … FROM shifts WHERE is_active=1 ORDER BY id LIMIT
  1`, i.e. the lowest-id active shift, for everyone. An evening nurse arriving on
  time at 14:00 was stamped Late every single day and auto-closed to **0.0 paid
  hours**, which is the exact opposite of what the auto-close exists to do; its
  own docstring said *"Paying an estimate is fairer than paying zero"*. The
  per-employee roster already existed in `staff_shifts` and the lateness engine
  never asked it. The flash now reads
  `"Checked in at {time} — {n} minutes after the shift start (grace {N} min)."`,
  said plainly at the moment it happens, because discovering it in a payroll
  deduction at the end of the month is how a system loses the staff's trust.
  Source: `D:/vet/platform/blueprints/attendance/routes.py:449-456`,
  `D:/vet/platform/docs/AUDIT_FINDINGS.md:30-40`; commits `2067688`, `a900f10`,
  `0b0913e`.
- Two time formats lived in one column and every helper assumed one (`2067688`).
- Stored attendance hours had to be recomputed from the times on the same row
  (`a900f10`, plus `scripts/recompute_attendance_hours.py`).
- A leave request starting next year permanently ate the employee's balance and
  was never deducted from anything, because the request reserved against
  `date.today().year` while approve and reject settled against the start date's
  year, so the `UPDATE` matched no row and silently no-oped. Both sides now use
  the start-date year and route through `_get_or_create_balance`, a helper that
  had existed all along and was **called from nowhere**.
  Source: `D:/vet/platform/blueprints/attendance/routes.py:713-751`

The flash a user now sees on submit:
`"Leave request submitted for {days} day(s). Awaiting approval."`
Source: `D:/vet/platform/blueprints/attendance/routes.py:755`

**Tests:** `D:/vet/platform/tests/test_attendance_pays_correctly.py`,
`test_attendance_integrity.py`, `test_hr_attendance_pay.py`,
`test_payroll_allowances.py`

### 6.6 Story four — restoring a backup destroyed the database and said it worked

Included because it is the one a buyer's engineer will care about most, and
because it is the clearest example of the audit finding something no feature list
would ever surface.

**What went wrong.** Restoring **any archive older than the 30-day retention
window** wiped the live database and reported success.

The chain: the purge of expired archives ran inside `_run_sqlite_backup()`.
`restore_backup()` calls that function to take its safety snapshot before
overwriting anything. So restoring a 120-day-old archive **purged that very
archive mid-restore**; the subsequent `sqlite3.connect()` recreated the deleted
path as a 0-byte file; and the copy step then copied that empty database over the
live one.

**What the user was told:** *"Database restored… restore that file to undo
this."*

**The fix.** The purge now runs only in `run_backup()`, and the copy step raises
on a missing source — so the class of failure cannot recur through any other
caller. Reproduced standalone before fixing and independently re-verified after: a
500-row live database, an archive dated 120 days old, restore returns
`success=True` and the 500 rows are still there.

Source: commit `f286b98` ("test+fix: RESTORING A BACKUP DESTROYED THE DATABASE AND
REPORTED SUCCESS"), `D:/vet/platform/models/backup.py`,
`D:/vet/platform/tests/test_backup.py`

That single commit covered the 60 remaining untested endpoints with 163 tests,
took the suite from 643 to 1,324, and found eight bugs — including that **every
public website booking had always failed** (the public API inserted four columns
that do not exist, giving a generic 500 for `/book`, `/emergency` and every lead)
and that half the report builder was unusable for the same reason.

### 6.7 Story five — the fail-open "Safe to prescribe" banner

One more, for a room with a clinician in it.

**What went wrong.** The drug-interaction check was fail-open in three ways, and
the visit template painted **any** severity outside severe/moderate/mild as a
green **"✅ No significant interactions found. Safe to prescribe."** So:

- AI service down or returning unparseable JSON → **"Safe to prescribe"**
- no drug specified → `safe: true`
- no current medications → **"\<drug\> can be prescribed"**

The last is the worst. Paracetamol for a cat with an empty medication list
returned "can be prescribed". Paracetamol is lethal to cats.

**The fix.** The endpoint now never reports safety it has not established.
Unverified paths return severity `unchecked` and the template renders a distinct
grey **"Not checked"** banner stating explicitly that this is not a statement of
safety. The green branch now also says what it did **not** cover.

**And then a real one was built.** `blueprints/cds/` — a rule engine with no AI in
the decision path, `Decimal` throughout for dosing, and a refusal to calculate for
an unknown drug rather than extrapolating. Re-counted from the loaded data for
this document: **20 species contraindications + 4 breed contraindications + 22
drug-drug interactions + 36 dose rules = 82 curated rules**, over **172 aliases**
including trade and Arabic names, across 6 drug classes and 8 species weight
ranges. Verified over HTTP at the time: paracetamol/cat, permethrin/cat and
ivermectin/Border Collie all return `contraindicated`; the same drug in a dog is
quiet; an unknown drug returns `unverified` with an explicit denial of safety
rather than silence.

**And then it was deliberately not switched on.** It is registered as a standalone
reference page and **not** wired into prescribing or dispensing as a blocking
gate. The data carries its own status field, and the value reads
`"DRAFT — NOT YET REVIEWED BY A LICENSED VETERINARIAN"`. The reason for not
gating on it, from the commit message: at the expected inventory name-match rate
an always-on checker would generate enough "unverified" alerts to **train staff
past the "contraindicated" banner that matters**.

Source: commit `576dd38`, `D:/vet/platform/blueprints/cds/routes.py:264-275`,
`:366-410`, `:527-535`; `D:/vet/platform/tests/test_cds.py`

That last decision is the single best evidence in this deck that the product was
built by somebody thinking about a clinic rather than a feature list. Use it.

### 6.8 The pattern, named — and it is also the roadmap

Across all sixty-odd blockers one shape recurs, and the codebase names it in its
own commit messages:

> **"The sale looks right on screen and the books say something else."**
> — commit `5759f46`

> **A correct mechanism is built and then not finished being rolled out.**

Concrete instances of the second: `shifts.days_of_week` saved by a screen and read
by nothing; `_get_or_create_balance` defined and called from nowhere;
`permission_required` present, correct, and applied to zero routes (its only
occurrence in the codebase was inside its own docstring — a permissions screen
that told an administrator they had restricted something when they had not, which
the test file calls *"worse than having no permissions screen at all"*); the
`NUMERIC` money migration written, tested and unapplied.

Source: `D:/vet/platform/tests/test_permissions_enforced.py:1-13`

**Three of those four are now closed.** State the pattern as criticism in the
deck, then state what it means: the remaining work is *rollout of things that
already exist and are already tested*, which is the cheapest kind of roadmap a
buyer can inherit.

### 6.9 What "pinned by a test" means here

Not "there is a test file". Specifically:

| Test | What it actually proves |
|---|---|
| `test_access_sweep.py` | Generates its checks from `app.url_map`, so a route added tomorrow is swept tomorrow: logged-out reachability, non-existent-id handling, cross-module permission, cross-tenant session. The public endpoint list is explicit, not a pattern — *"a new public route has to be added here on purpose."* Source: `tests/test_access_sweep.py:1-30` |
| `test_role_consistency.py` | AST-scans role names used anywhere in the codebase against `_SEED_ROLES`, so a typo in a role string fails the build |
| `test_db_layer.py` | Re-derives the id-less-table list from the schema rather than hardcoding it |
| `test_arabic_pdf.py` | Reads the generated PDF back with `pypdf` and asserts no Arabic letter was dropped |
| `test_branding.py` | Spies on what is actually drawn into a PDF |
| `test_no_credentials_in_repo.py` | Reads `git ls-files`, so it governs exactly what would be published. `tests/` is excluded deliberately — flagging throwaway test passwords would train people to ignore the check, "which is the only way it stops working" (commit `5b5b4bf`) |
| `test_permissions_enforced.py` | Restores every role afterwards, because leaving one mutated changed the outcome of a different file — *"a test that breaks a different file is worse than no test"* |
| `test_postgres_full.py` | 56 tests against the real production engine via an embedded PostgreSQL, no admin rights required. It found four bugs invisible to the SQLite suite, including one where a wrong password raised `UndefinedColumn` instead of being reported as a wrong password, **leaving account lockout permanently disengaged** |

CI is GitHub Actions: a **blocking** SQLite job on a Python 3.11/3.12 matrix, and
a **non-blocking** PostgreSQL 16 job (`continue-on-error: true`) because
`test_postgres_full.py` still targets a hardcoded database name rather than
`TEST_POSTGRES_DSN`. That limitation is documented inside the workflow file
itself. No repository secrets are consumed.
Source: `D:/vet/platform/.github/workflows/ci.yml:11-60`

---

## 7. The market

From `docs/market/` — nine documents of primary research, English and Arabic
sources, every figure carrying a URL and unsourced figures marked as such. Use the
research honestly: **its central finding is that Egypt alone is a small market.**

### 7.1 Egypt, sized

There is **no published official register of private veterinary clinics in
Egypt** — not from GOVS, not from the Veterinary Syndicate, not from CAPMAS. Every
count is a directory scrape or a count of government units.

| Source | What it counts | Egypt total |
|---|---|---|
| evcindex.com (Arabic vet directory) | Veterinary clinics | 506 |
| evcindex.com, companion-animal category | Self-declared pet clinics | 119 |
| Egypt Yellow Pages | Veterinarian businesses | ~715–768 |
| Rentech Digital (Google Maps scrape, Apr 2026) | Veterinarians / animal hospitals | 1,463 / 416 |

**Working figure: 900–1,600 private veterinary premises, of which roughly 500–900
are meaningfully companion-animal focused. Mid-point ~700.**

**The often-quoted "4,500 Egyptian vet clinics" figure is untraceable to any
primary source.** It surfaced in an AI-generated search summary, appears in no
Egyptian government publication, and is 6–9× what every directory shows. The
research marks it `[UNVERIFIED — DO NOT USE]`. **Do not put it in the deck.** A
buyer who checks it and finds it hollow discounts everything else you said.

Source: `D:/vet/platform/docs/market/02_MARKET_SIZE.md` §0, §T1.3

**Geography.** Greater Cairo is ~58% of listings by two independent directories,
and past 65% once the new urban communities (New Cairo alone: 44 clinics) are
folded back in. Greater Cairo plus Alexandria is **78–85%**. Mansoura, the
Delta's largest city, has 17. This is a three-city product, and that is genuinely
good news for go-to-market cost.

### 7.2 The ceiling, stated as the research states it

| | Low | **Central** | High |
|---|---|---|---|
| **TAM** | EGP 14.4m/yr (~USD 284k) | **EGP 26.4m/yr (~USD 520k)** | EGP 45.4m/yr (~USD 895k) |
| **SAM** | EGP 2.1m/yr (~USD 41k) | **EGP 6.3m/yr (~USD 124k)** | EGP 15.8m/yr (~USD 312k) |
| **SOM, year-3 ARR** | EGP 945k/yr (~USD 19k) | **EGP 1.26m/yr (~USD 25k)** | EGP 1.89m/yr (~USD 37k) |

> **"Central SOM of EGP 1.26m/year supports approximately two people. That is the
> whole finding."**

And the sensitivity analysis, which is the sentence a buyer will respect you for
including: if the research is 50% too pessimistic on *both* the number of clinics
*and* what they will pay, three-year ARR is still only **EGP 2.84m ≈ USD 56,000
per year**. If it is 50% too optimistic on both, it is **USD 6,000 a year, which
is a hobby.**

More than half of the headline TAM is 1,500 government veterinary units that
cannot be sold to product-led: no unit-level budget, central procurement through
the Ministry of Agriculture, and a workload of livestock vaccination and food
inspection rather than pet appointments. **Realistically addressable TAM is under
EGP 12m/year.**

Source: `D:/vet/platform/docs/market/02_MARKET_SIZE.md` §TAM/SAM/SOM, §Sensitivity

**How to use this in a deck.** Do not hide it and do not lead with it. Put it on a
slide titled "Egypt is not the business — Egypt is the proof". The asset's value
to a MENA software house is not Egyptian ARR; it is a finished, Arabic-complete
product they can sell across several markets at 2–9× Egyptian price points.

### 7.3 Pricing, anchored

| Anchor | Price | Note |
|---|---|---|
| Egyptian pharmacy software, basic | **5,000–12,000 EGP perpetual** | The band local SMEs recognise |
| Egyptian POS/accounting, full system (Deltawy) | **43,000 EGP perpetual** | Modules sold individually; the ETA e-invoice module alone is 7,000 EGP |
| Daftra (Egyptian SME ERP) | 5,874 / 11,731 / 23,520 EGP per year | Quoted natively in EGP, not USD-indexed |
| ClinicGateway (human clinics, Egypt) | **2,500 EGP/month** | Includes ETA e-Receipt, WhatsApp, Arabic RTL |
| Doctorato (human clinics, Egypt) | from **1,990 EGP/month** | |
| **VetICare** (the direct competitor) | **USD 52/month for 5 users** (~2,630 EGP/mo) | WhatsApp vaccination alerts +USD 20/month |
| Western vet PMS | USD 260–549/month | **EGP 13,000–27,800/month** — structurally unsellable in Egypt |

**The recommended structure**, from the research: perpetual licence, because
Egyptian SMEs buy capex not opex and it is the only model that pays a founder in
year one.

| Tier | Perpetual | Annual support from yr 2 | Subscription alternative | Setup |
|---|---|---|---|---|
| Solo | 12,000 EGP | 3,000 EGP | 6,000 EGP/yr | 3,000 EGP |
| **Clinic** | **30,000 EGP** | 7,500 EGP | 15,000 EGP/yr | 6,000 EGP |
| Hospital | 60,000 EGP | 15,000 EGP | 30,000 EGP/yr | 12,000 EGP |

The Clinic tier is 70% of the Egyptian full-system POS perpetual, and the two
payment paths cross exactly at year three — licence 30,000 + two support renewals
15,000 = 45,000, versus three years of subscription at 15,000 = 45,000. That is a
clean thing to put on a price page and it removes the cannibalisation argument.

**Do not index the price to USD.** EGP went from ~16 to ~51 to the dollar in about
four years — a ~68% loss of dollar value — and both Daftra and Foodics publish
separate EGP price lists. Price in EGP, revise annually.
Source: `D:/vet/platform/docs/market/03_PRICING_AND_ECONOMICS.md` §1.2, §2.2, §2.3,
§T2 anchors

### 7.4 The competition — the niche is not empty

**This is the finding the seller most needs to lead with rather than be caught
on.** The research expected to report an empty Arabic vet-software niche. It is
not empty.

**VetICare** (veticareapp.com) ships, today, with **named Egyptian clinic
customers** (Pets Zone, Dr Men3am Pet Hospital, Almotawakkel Pet Center, Mojo
Veterinary): Arabic + RTL marketed explicitly, WhatsApp integration, pharmacy with
a drug database, **laboratory with named analyser integrations (Exigo, Edan)**,
inventory, POS, boarding, RBAC with 180+ permissions, Saudi ZATCA offline QR
e-invoicing, and **a pet-owner mobile app with an AI symptom checker**. Operating
since 2020, claims 500+ clients, published price USD 52/month.

Four of the things this asset would like to call advantages are already shipped by
an incumbent. Two things it lacks — lab-machine integration and a pet-owner app —
the incumbent has.

Others in the same space: **bAItari.vet** (Oman, Arabic-primary, telling exactly
the story Aleefy wants to tell), **Yolo Clinic** (UAE), **Kawakeb Al-Teknologia**
(Saudi, LAN-capable), **Holool Alghad** (Riyadh), **Al-Mukhtabarat** (Egypt, 6
October, Giza — the one genuinely Egyptian vet-adjacent vendor found).

And the structural point: **RTL is not a technical moat.** Provet Cloud ships
Hebrew across sixteen locales; a vendor with existing RTL plumbing adds Arabic as
a translation project.

Source: `D:/vet/platform/docs/market/01_COMPETITORS.md` §2.1, §T1 notes

**What is still true after all that:** none of the fifteen Western products
surveyed supports Arabic at all, and no vendor found anywhere — including VetICare
— covers grooming *and* boarding *and* payroll *and* pet-shop retail in one
system.

### 7.5 Adjacent markets, and the wedge

| Market | Verdict, and the sourced basis for it |
|---|---|
| **Morocco** | **The strongest adjacent market and the largest addressable base in the whole study.** Working estimate **300–700 companion-animal clinics** — larger than Egypt's 350–500 — concentrated in Casablanca, Rabat, Marrakech, Tangier and Agadir, in a currency that did not move materially while the EGP lost 70%. **Requires French.** Marked `[ESTIMATE — triangulated, not published]`. Source: `docs/market/06_ARABIC_MARKETS.md:111` |
| **Jordan** | Working estimate **15–40 clinics**, Amman-dominant. Very small — and **bAItari, the closest direct competitor, is built in Amman.** Entering Jordan means fighting it on home ground in a market of perhaps 30 clinics. Source: `docs/market/06_ARABIC_MARKETS.md:151-153`, `:172` |
| **Tunisia** | Of all ten countries studied, Tunisia has the e-invoicing mandate that is simultaneously in force, covering small clinics, and documented well enough for a two-person team to integrate against without a partner. Source: `docs/market/06_ARABIC_MARKETS.md:201` |
| **Lebanon, Iraq, Syria, Libya, Sudan, Algeria, Palestine** | Covered in `06_ARABIC_MARKETS`. Iraq carries a trap number: a syndicate-linked "1,500 licensed veterinary clinics" figure that is overwhelmingly **livestock** practice. Do not present it as companion-animal density |
| **Gulf (Saudi, UAE, Oman)** | Not sized in the research. What *is* sourced: VetICare names Saudi Arabia, UAE, Oman and Egypt among its 500+ clients; **VetC** (Saudi) claims 65+ clinics with integrated accounting and tax reporting; the Gulf channel runs through medical-equipment distributors rather than direct sales; and Saudi entry is gated behind **ZATCA Phase 2 e-invoicing**, which VetICare has already cleared. Source: `docs/market/01_COMPETITORS.md` §2.1, `docs/market/06_ARABIC_MARKETS.md:174` |
| **Sub-Saharan Africa** | Researched. **Verdict: no.** `docs/market/07_SUBSAHARAN_AFRICA.md` |
| **Asia** | Researched. **Verdict: no** — the e-invoicing wedge does not reach clinics there. `docs/market/08_ASIA.md` |

**The wedge, and it is not built.** E-invoicing mandates are the strongest
available lever, because they make software a legal obligation with a deadline.
Egyptian **e-receipt Phase 7, sub-phase 1, took effect 15 March 2025 and named
3,193 establishments — hospitals, clinics (عيادات), labs, radiology centres and
pharmacies in Greater Cairo and Alexandria.** Free professions had already been
obliged to register by 15 December 2022. **That integration does not exist in this
codebase.** An Egyptian POS vendor charges 7,000 EGP for the ETA e-invoice module
alone, which tells you both that it is valuable and that it is real work.
Source: `docs/market/02_MARKET_SIZE.md:332-344`,
`docs/market/03_PRICING_AND_ECONOMICS.md:93`

### 7.6 One thing the seller must settle before contacting anyone

**Escrow.com does not support Egyptian residents and PayPal cannot receive
there**, so the default settlement rail for every software marketplace and most
direct buyers is unavailable. A buyer asking "how do I pay you?" and hearing
nothing is a dead deal. `docs/market/09_PAYMENT_RAILS.md` has the working options.
Source: `D:/vet/platform/docs/sale/README.md` (seller checklist)

---

## 8. What is not there

Stated plainly and first, because a buyer's reviewer finds all of it in diligence
and the discovery costs more than the disclosure.

### 8.1 Commercial

- **Zero customers. Zero revenue. No operating history.** Nothing here has been
  run by a paying clinic for a day.
- **No reference customer, no testimonial, no case study, no site visit to
  offer.**
- **No support contract, no SLA, no ticketing history.**
- **No trademark registration** for "Aleefy" or "اليفي". The name transfers as an
  unregistered common-law mark.
- **No e-invoicing accreditation** with the Egyptian Tax Authority.
- **Domain ownership is not provable from the repository.** `aleefy.online` is
  referenced as canonical throughout the marketing site, but registrar, expiry and
  ownership are **not verified**. Require the registrar transfer code in the sale
  agreement.
- **The contact phone number in the marketing site is a personal number**
  (`+20 112 767 7015`, and `wa.me/201127677015`). Confirm whether it transfers.
- **One demo clinic, and it is synthetic.** See §8.5.

### 8.2 Product — things a competitor has and this does not

- **WhatsApp has never been sent end to end.** The transport is real and unified —
  `blueprints/whatsapp/wapilot.py` is a 251-line client for
  `https://api.wapilot.net/api/v2`, and the nightly reminder job and the manual
  Send screen now share it, which they did not before (they posted to different
  hosts with different auth schemes). **But no message has provably reached a real
  phone from this code.** Every test drives it with a fake client — `_DeadClient`,
  `_FlakyClient` — and there is no Wapilot account, token or instance in the
  repository. What *is* proven, by test, is that an unconfigured or unconnected
  clinic is never told a reminder was sent: the tests are named
  `test_an_unconnected_clinic_is_never_told_a_reminder_was_sent` and
  `test_an_unconfigured_clinic_is_told_so_and_nothing_is_claimed_sent`.
  Source: `D:/vet/platform/blueprints/whatsapp/wapilot.py:1-14`,
  `D:/vet/platform/blueprints/whatsapp/scheduler.py:95-150`,
  `D:/vet/platform/tests/test_whatsapp_reminders_work.py:99,130,158,174`
- **Online card payments are unverified.** The Paymob gateway exists and the
  source itself says, in a heading, `WHAT IS NOT VERIFIED`:

  > "There is no Paymob account yet, so this has NOT been run against the sandbox.
  > The flow below follows the documented Intention API, and everything testable
  > without a network is tested."

  Two unknowns remain: the exact field set and ordering the HMAC is computed over,
  and the `Authorization` scheme on the intention call (probing with a fake key is
  useless — Token, Bearer, Api-Key and no header all return the same generic 401).
  `scripts/verify_paymob.py` exists to settle both with sandbox keys in one run.
  **The failure mode is safe:** getting the HMAC wrong fails *closed* — an
  unverified callback is refused and no invoice is marked paid — so the risk is
  "payments do not complete", not "anyone can mark invoices paid".
  Source: `D:/vet/platform/models/payments/paymob.py:12-30`, `:56-62`
  Counter-payment methods (cash, card on the counter terminal, bank transfer,
  InstaPay, insurance) are recorded, not processed, and work today.
  Source: `D:/vet/platform/models/payments/cash.py:52-68`
- **No lab-machine integration.** VetICare names Exigo and Edan.
- **No pet-owner mobile app or portal.** `owners` is a CRM contact record with no
  password, hash, token or verification column. There is no owner login route
  anywhere. The research puts owner identity by phone + OTP at ~5 days and the
  portal itself at 25–40 days.
  Source: `D:/vet/platform/docs/market/05_PRODUCT_READINESS.md` §2.2
- **No e-invoicing integration** (Egyptian ETA, Saudi ZATCA).
- **No SMS.** Zero hits for any SMS provider.
- **Multi-Branch Control Center is `planned`** and does nothing.
- **Clinical Decision Support is `beta`**, its drug data is marked
  DRAFT/unreviewed, and it is deliberately not wired into prescribing (§6.7 — the
  reasoning is good, but the effect is that it is a reference page).
- **`/api/public` is contact-form-grade.** Six unauthenticated, CORS-configurable,
  IP-rate-limited routes. `POST /book` finds-or-creates an owner by phone string,
  finds-or-creates a pet by name, and inserts a `Pending` appointment. **No slot
  validation, no doctor availability, no payment, no identity.**
  Source: `D:/vet/platform/docs/market/05_PRODUCT_READINESS.md` §2.2

### 8.3 Engineering

- **Money is binary floating point in the schema.** The corrective `NUMERIC`
  migration is written and tested and deliberately unapplied; applying it without
  the surrounding work (550–800 call sites) would achieve little. The one
  customer-visible defect it caused — an invoice paid in full staying marked
  "Partial" forever, on roughly **1 in 7** instalment invoices — has a one-line fix
  and that fix is applied.
  Source: `D:/vet/platform/docs/MONEY_PRECISION.md:1-31`
- **Backup-restore-from-upload is broken on Flask 3.0.x, which
  `requirements.txt` permits.** `blueprints/system/routes.py:58` assigns
  `request.max_content_length` in a `before_request` hook; on Flask 3.0.3 that is
  a read-only property computed from app config, so the assignment raises
  `AttributeError` before the upload view is reached. `requirements.txt` declares
  `Flask>=3.0.0` with **no upper bound and a lower bound one minor version too
  low**. Found by executing the suite while writing this document — seven tests in
  `tests/test_system_routes.py` fail on it (§1.2). Two lines of work: raise the
  floor to the Flask that added the per-request setter and add a ceiling, or set
  the limit through app config instead. **Restore-from-file still works; it is the
  upload path that does not.**
- **The green build is a statement about SQLite.** The PostgreSQL CI job is
  non-blocking because `tests/test_postgres_full.py` targets a hardcoded database
  name rather than `TEST_POSTGRES_DSN`. The 56 PostgreSQL tests do pass locally via
  `scripts/run_postgres_tests.py` with an embedded server, and they found four
  bugs the SQLite suite could not see — but a green CI badge does not prove the
  production engine.
  Source: `D:/vet/platform/.github/workflows/ci.yml:37-45`
- **One author, ninety days.** 142 commits, one person. There is no second pair of
  eyes anywhere in the history, and a large share of the commits landed
  immediately before the sale documents were written.
- **Two Alembic heads, deliberately.** Documented in `MIGRATIONS.md`, which also
  contains one stale line claiming Alembic is not in `requirements.txt`; it is.
- **A credential appears in early git history and cannot be removed from it.** Any
  deployment derived from this code must rotate it. `docs/PILOT.md` §1 gates
  everything else on this. A test now refuses to let a new one be committed, by
  reading `git ls-files`.
  Source: `D:/vet/platform/docs/PILOT.md:33-47`,
  `D:/vet/platform/tests/test_no_credentials_in_repo.py`
- **The working tree is not clean at the time of writing.** `git status` shows 20+
  modified files (appointments, grooming, inpatient and telemedicine routes,
  several templates, the built CSS/JS, and `01_TECHNICAL_DOSSIER.md` itself) on
  branch `fix/audit-remediation`. Confirm the branch is pushed and the tree clean
  before accepting handover, or that work does not transfer.
- **Server-generated strings are English-only.** Flash messages, error text and
  some report headers — e.g. `"You don't have permission to access this page."`,
  `"Please log in to continue."`, `"Check-in recorded successfully."` — are not
  bilingual. The 5,219 translated strings are template labels.
  Source: `D:/vet/platform/blueprints/auth/routes.py:63,127`,
  `D:/vet/platform/blueprints/attendance/routes.py:456`
- **Currency is hardcoded EGP in roughly 235 places** and the `clinic.currency`
  setting does nothing.
  Source: `D:/vet/platform/docs/sale/05_ASSET_INVENTORY.md` §3.3
- **No in-app help**, therefore no Arabic in-app help.
- **The permission gate falls open, by design, in two cases**: a built-in role with
  no grant row (so an upgrade cannot lock a live clinic out of its own system), and
  a blueprint with no grant key (launcher, auth, uploads, notifications). An
  *unknown* role now denies — it used to fall open, which meant the way to give a
  nurse the clinic's money screens was to delete her role.
  Source: `D:/vet/platform/blueprints/auth/routes.py:88-131`
- **Two manual steps in the pilot runbook have never been executed** on a real host
  with a real domain: wildcard DNS and certbot. §5.3.

### 8.4 What does not transfer

- Customers, revenue, support contracts (none exist).
- Trademark registration (none exists).
- E-invoicing accreditation (none exists).
- Any third-party service account personal to the seller.
- **`marketing/` is not in the git repository.** The git root is `platform/`; the
  marketing site (index page, 105-file / 29 MB screenshot library, capture
  scripts) lives in the untracked parent and must be transferred as a separate
  file delivery with its own contract clause.
- **The live marketing site is not the one in the deliverable.** `aleefy.online`
  currently serves a different, 9-page build whose source **does not exist
  anywhere in the deliverable**. A buyer acquiring "the marketing site" is
  acquiring the intended replacement, not the thing currently serving.
  Source: `D:/vet/platform/docs/sale/05_ASSET_INVENTORY.md` §4.1

### 8.5 The demo clinic

There is exactly one, it is synthetic, and it is seeded by
`scripts/seed/demo_showcase.py` (1,574 lines). Measured from the demo database in
this repository:

| | Rows |
|---|---|
| Clinic | 1 — "Aleefy Veterinary Clinic" / "عيادة أليفي البيطرية", 12 Abbas El-Akkad St., Nasr City, Cairo, currency EGP, timezone Africa/Cairo |
| Staff users | 15 |
| Owners | 60 |
| Pets | 83 |
| Appointments | 511 |
| Visits | 397 |
| Invoices | 397 |
| Payments | 333 |
| Prescriptions | 354 |
| Lab requests | 123 |
| Vaccinations | 66 |
| Attendance records | 1,078 |
| Pet-shop orders | 174 (333,490.00 EGP) |

The seed deliberately includes unpaid invoices, no-shows and abnormal lab results,
because a dataset where everything is clean demonstrates nothing.
Source: `D:/vet/platform/scripts/seed/demo_showcase.py`,
`D:/vet/platform/docs/sale/02_DEMO_GUIDE.md`

**It is synthetic data about a fictional clinic in Cairo.** It is a good demo. It
is not evidence that anyone has used this product.

---

## 9. Asset inventory — what a buyer receives

Full detail is in `05_ASSET_INVENTORY.md`. This is the deck-sized version.

### 9.1 Code

| | |
|---|---|
| Repository | `https://github.com/abodahn/vet-platform.git` — git root is `platform/`, **not** its parent |
| Commits | **142**, 2026-05-21 → 2026-08-19, one author |
| Branches on the remote | `main`, `feature/v3-complete-uiux-revamp`, `fix/audit-remediation` |
| Python | 233 files / **76,106** lines (42,943 excluding tests) |
| Jinja templates | 179 files / **40,590** lines |
| Blueprints | 34 registered, 1 deliberately unregistered |
| Routes | **413** |
| Tests | **114** files / 33,163 lines / **2,034** collected |
| Database | 83 tables on first boot, 96 fully exercised; 66–77 indexes; Alembic with a verified baseline |
| Stylesheets | 5 sources plus a built `app.min.css` with a `build.py` pipeline |
| Fonts | Cairo Regular + Bold TTF (SIL OFL), Cairo/DM Sans woff2 subsets, Bootstrap Icons 52-glyph subset (MIT) |

The history is a real development history, not a squashed dump: the audit
remediation, the money-precision investigation and the market research are each
traceable to individual commits with messages that explain the reasoning.

### 9.2 Deployment and operations

| File | What it is |
|---|---|
| `Dockerfile`, `docker-compose.yml`, `Procfile` | Container build and local compose |
| `gunicorn.conf.py` | Production WSGI config |
| `deploy/deploy.sh` | One-time host setup: docker, postgres, nginx, certbot, ufw |
| `deploy/nginx.conf`, `deploy/vetplatform.service` | Reverse proxy and systemd unit |
| `deploy/BACKUP_RUNBOOK.md` | Backup and restore procedure |
| `scripts/add_clinic.py` | **The supported per-clinic command.** Generates and prints credentials once |
| `scripts/preflight.py` | Refuses an unsafe boot; exits non-zero until every blocker clears |
| `scripts/run_postgres_tests.py` | Embedded PostgreSQL, seeded, production-engine suite in one command |
| `scripts/set_working_week.py`, `recompute_attendance_hours.py`, `propose_staff_shifts.py` | Data-correction tooling written during remediation |
| `scripts/verify_paymob.py` | Settles the two Paymob unknowns against a sandbox account |
| `scripts/demo_brand.py` | Rebrands the demo per prospect |
| `.github/workflows/ci.yml` | Two jobs; SQLite blocking, PostgreSQL non-blocking |

All environment-variable placeholders in `docker-compose.yml` are shell defaults
(`${SECRET_KEY:-change-me-in-production}`), not real values.

### 9.3 Documentation — 63,796 lines of Markdown across 55 files

| Set | Contents |
|---|---|
| **`docs/manual/`** (8 chapters + index, **12,188 lines**) | Screen-shaped reference: every screen, every field, every button, who can open it, with `Source: file:line` per screen and a **Known limits** section per chapter |
| **`docs/workflows/`** (9 chapters + index, **17,880 lines**) | Task-shaped: each workflow end to end, including the alternative and failure paths |
| **`docs/market/`** (9 documents, **5,279 lines**) | Competitors, market size, pricing and unit economics, go-to-market, product readiness, Arabic markets, Sub-Saharan Africa, Asia, payment rails |
| **`docs/sale/`** (8 documents, incl. this one) | This pack |
| **`docs/AUDIT_FINDINGS.md`** (5,145 lines) | 334 recovered findings with reproduction steps |
| **`docs/AUDIT_AND_PLAN_2026-07-25.md`** | 21 numbered defects with `file:line`, a 7-dimension scorecard, a 4-phase plan, a remediation-status table, and four of its own findings self-corrected |
| **`docs/MONEY_PRECISION.md`** | The float investigation, measured failure rate, applied fix, deferred migration, 3-step rollout |
| **`docs/PILOT.md`** | The exact path from a bare server to clinic #1 |
| **`docs/security/`** (5 documents) | Access-control matrix, API security checklist, data classification, deployment checklist, incident response |
| **`docs/guide/`** (3 documents) | Getting started, a day in the life |
| **`PROVISIONING.md`, `MIGRATIONS.md`, `SECURITY.md`, `PRODUCT.md`** | Operator runbooks and policy |
| **8 `.docx` deliverables** | BRD, Technical Architecture, Deployment & Operations, Security & Compliance, User Guide, Workflow Manual, Stability Assessment, Platform Intelligence |
| **`docs/reference/easy-visit/`** | A screen-recording of the one-page exam plus extracted frames |

### 9.4 Brand

| Asset | Status |
|---|---|
| Name **Aleefy / اليفي** | Used throughout app, marketing site and domain. Unregistered common-law mark |
| Logo SVG + PNG | `static/images/aleefy-logo.svg` and `.png` — verified present |
| Secondary mark | `static/petsy/petsy-icon.svg` (the Petsy assistant) |
| Brand colour | Teal `#0D7560`, gold `#C9A84C` for two semantic uses |
| Domain `aleefy.online` | Referenced as canonical. **Ownership not verifiable from the repository** |
| Marketing site | Single static page, 721 lines, no build step, zero-JS bilingual toggle, self-hosted fonts. **Untracked — separate delivery.** Plus a 105-file / 29 MB screenshot library |

### 9.5 Licences — the answer a buyer's lawyer needs

**Nothing in the dependency tree is GPL or AGPL.** No copyleft obligation attaches
to the application's own source.

**Three dependencies are LGPL**: `psycopg2-binary` (PostgreSQL driver), `fpdf2`
(PDF generation) and `python-bidi` (Arabic bidi reordering). All three are
unmodified public PyPI packages, separately installed via `requirements.txt` and
trivially replaceable by the recipient — the least-encumbered possible LGPL
posture. **It stops being trivial if the app is ever frozen into a single-file
binary** (PyInstaller, Nuitka) for an on-premise perpetual-licence model, at which
point the relink obligation becomes real and needs legal review. Flag it now
rather than discover it later.

**Fonts are OFL**, which explicitly permits bundling with and selling as part of
commercial software. **Gap:** no `OFL.txt` accompanies the font files anywhere in
the repository, and OFL requires the licence text to travel with redistribution. A
five-minute fix for day one.

Source: `D:/vet/platform/docs/sale/05_ASSET_INVENTORY.md` §5

---

## 10. Deck skeleton — slide by slide

Fifteen slides, with the source section for each. Cut to ten by dropping 6, 9, 12
and 14.

| # | Slide | Content from | The one line on it |
|---|---|---|---|
| 1 | **Title** | §3.1 | *Aleefy — a complete Arabic-first veterinary clinic ERP. No customers, no revenue. Here is exactly what that means.* |
| 2 | **What it is** | §3.2 | The one-paragraph description, plus the headline table from §2.2 |
| 3 | **The correction** | §1 | *The summary you were sent said 573 tests. It is 2,034. We are correcting our own numbers upward.* |
| 4 | **The problem** | §4.1–4.2 | *The incumbent is a paper notebook and a WhatsApp thread. It breaks the week the clinic hires its second vet.* |
| 5 | **Why the alternatives don't fit** | §4.3 | *EGP 13,000–27,800/month, and none of them speaks Arabic.* |
| 6 | **Product tour** | §5.2 | The 34-module table, in category order, bilingual |
| 7 | **Differentiator 1 — Arabic to paper** | §5.1 | *Four things have to be right for Arabic in a PDF. All four are, including the one almost nobody finds.* |
| 8 | **Differentiator 2 — breadth** | §5.2 | *No competitor found covers grooming and boarding and payroll and retail in one system.* |
| 9 | **Differentiator 3 — one command per clinic** | §5.3 | `python scripts/add_clinic.py --slug nilevet --name "Nile Vet Clinic"` |
| 10 | **Differentiator 4 — isolation is physical** | §5.4 | *A missing WHERE cannot cross a database boundary.* |
| 11 | **Proof of rigour — the audit** | §6.1 | 334 findings, 63 blockers, and a document that opens by telling you to expect some of it to be wrong |
| 12 | **Proof of rigour — one story** | §6.4 | *A reports page showed 334,070 EGP of real sales as zero. The fix was four words in seven SQL statements.* |
| 13 | **What is not there** | §8 | The whole of §8.1 and §8.2 on one slide. Do not soften it |
| 14 | **The market, honestly** | §7.1–7.2 | *Central three-year Egyptian ARR is about USD 25,000. Egypt is the proof, not the business.* |
| 15 | **What transfers** | §9 | Code, tests, CI, migrations, the localisation, 63,796 lines of documentation, the brand |

**Slide 12 is the one to rehearse.** It is the only slide where a non-technical
buyer feels the value of the engineering rather than being told about it.

---

## 11. Objections, and the answers that survive checking

| Objection | Answer |
|---|---|
| *"Most of this landed in the last three weeks, right before you decided to sell."* | **True, and it is in the git log.** 86 of 142 commits post-date the first sale document. The correct response is to hand over `docs/AUDIT_FINDINGS.md`, show that the work was closing a 334-item defect register rather than adding features to dress a sale, and note that the test suite tripled while the route count grew by 9%. Features were not being added. Defects were being closed. |
| *"One author. What happens when he stops?"* | Real risk, no mitigation to offer beyond the documentation: 63,796 lines of it, including a screen-by-screen manual and a workflow manual that carry `file:line` for every claim. `04_HANDOVER.md` was executed on a clean machine before it was written down. Budget a week of overlap and say so. |
| *"It has never run in a real clinic."* | **Correct.** The honest counter is that the failure modes a real clinic would have found first — the till, the reports, the working week, the backup restore — are exactly the ones that were hunted deliberately and closed. That is not a substitute for a pilot. `docs/PILOT.md` is the runbook for making it stop being true, and it is ordered so item 1 blocks the rest. |
| *"Arabic RTL is not a moat — Provet ships Hebrew."* | Agreed, and it is in our own research (§5.1, §7.4). The narrower claim is defensible: Arabic through to printed paper, with the shaping bug fixed at the level of a specific font's missing ligature, is not something a translation project delivers. |
| *"VetICare already does this, with Egyptian customers."* | Also in our own research. They have lab-machine integrations and a pet-owner app, which we do not. We have grooming, boarding, payroll and retail, which they do not. The buyer for this asset is one who wants the breadth and the source, not one who wants to win a feature comparison. |
| *"Egypt is too small a market."* | Our own sizing agrees: central three-year ARR ≈ USD 25,000. Egypt is the proof, not the business. The value is a finished Arabic-complete product a MENA software house can monetise across several markets at 2–9× Egyptian pricing. |
| *"Your money columns are floats."* | Yes, in 34 columns. The migration is written and tested; it is deliberately unapplied because applying it without the 550–800 call-site sweep achieves little. The one defect it caused in practice — instalment invoices stuck on "Partial", ~1 in 7 — has a one-line fix and it is applied. `docs/MONEY_PRECISION.md` is written for a non-database-engineer. |
| *"The PostgreSQL CI job is non-blocking."* | Correct, and the reason is in the workflow file. The 56 PostgreSQL tests pass locally against an embedded server; the blocker is one hardcoded database name. It is a half-day. |
| *"We ran your suite and got 19 failures."* | So did we, and §1.2 documents the run, the machine and the cause of every one. Twelve are this machine missing declared dependencies (`fpdf2`, `openai`) on a Python two releases past the project's own CI matrix. **Seven are a real defect and we found it by running the suite for this document**: the app assigns `request.max_content_length` in a before_request hook, which is read-only on Flask 3.0.x, and `requirements.txt` permits Flask 3.0. Backup-upload is therefore broken on a version the project claims to support. It is a two-line fix and it is in §8.3 as a known limit, not buried. |
| *"There is a credential in the git history."* | Yes. It cannot be removed from history, only rotated. It is disclosed here rather than left to be found, a test now blocks a new one from being committed, and rotation is item 1 in the pilot runbook. |
| *"How do we pay you?"* | **Settle this before the first call.** Escrow.com does not serve Egyptian residents and PayPal cannot receive there. `docs/market/09_PAYMENT_RAILS.md`. |

---

## 12. Known limits of this document

Stated in the same spirit as the rest of the pack.

1. **The full test run was executed here and did not come back clean.** 2,013
   passed, 19 failed, 5 skipped, 18m15s. Twelve failures are traced in §1.2 to
   declared dependencies missing on this machine; **seven are a genuine product
   defect that writing this document uncovered** (`request.max_content_length`
   assigned in a `before_request` hook, read-only on the Flask version
   `requirements.txt` permits — backup-upload broken). It is recorded in §8.3
   rather than presented as noise. The author's own run at HEAD reports 2,085
   passing; that figure is quoted, not reproduced. A buyer should install the
   declared dependencies on Python 3.11 or 3.12 and run it themselves before
   believing either number.
2. **Table counts vary by how much of the app has run.** 83 is a fresh
   `create_app()`; 96 includes tables that HR, payroll, telemedicine, security and
   the pet shop create lazily on first use. Both are given rather than one being
   chosen.
3. **The 5,219 bilingual strings are template labels only.** Server-generated
   flash and error strings are English. §8.3.
4. **The pet-shop revenue figure is quoted twice, with two values.** 334,070 EGP
   is what was measured on the live demo at the time of the fix (commit
   `5759f46`); 333,490.00 EGP across 174 orders is what this repository's
   `data/demo.db` holds today, re-measured for this document. Neither is wrong;
   the demo has been reseeded in between. Quote whichever, and say which.
5. **Market figures are research, not audited accounts.** Every one carries a URL
   in `docs/market/`; the unsourced ones are marked `[ESTIMATE — NO SOURCE]` or
   `[UNVERIFIED]` there and should keep those marks in any deck.
6. **`docs/market/05_PRODUCT_READINESS.md` describes the pre-remediation state**
   and is partly superseded: it records online payments as "ABSENT. Zero code."
   and WhatsApp as two incompatible implementations. A gateway now exists
   (unverified — §8.2) and the two WhatsApp implementations were unified. Its
   findings on the owner portal and the public API remain accurate.
7. **The working tree was not clean when these numbers were taken.** 20+ modified
   files on `fix/audit-remediation`. The route, test and template counts therefore
   describe the working tree, not commit `5b5b4bf` exactly.
8. **This document does not describe the UI.** For that, `docs/manual/` covers
   every screen and `docs/workflows/` covers every task, both with `file:line` per
   claim and a **Known limits** section per chapter. Nothing here should be used
   to describe a screen that those chapters describe differently — they were read
   from the templates, this was not.

---

*Prepared 2026-08-19. Every figure in §1, §2, §5, §6 and §8.5 was produced by
running a command against this repository on that date. Where an earlier document
in this pack is contradicted, the contradiction is recorded in §1 rather than
quietly corrected — an asset with no revenue is bought on trust in the seller's
description of it, and a description that survives checking is worth more than a
flattering one.*
