# Aleefy — Veterinary Clinic ERP

**Asset summary for prospective acquirers**
Prepared 2026-07-28 · All figures measured from commit `8979f72`, not estimated

---

## In one paragraph

Aleefy is a working, tested, fully bilingual (Arabic/English, right-to-left)
veterinary clinic ERP: 378 routes, 72 database tables, 573 passing automated
tests, and 28 functional modules covering clinical records, pharmacy, laboratory,
inventory, invoicing, accounting, HR, payroll, retail point-of-sale, grooming,
boarding and telemedicine. It installs on a single clinic PC or a shared server
with one command. **It has no customers and no revenue.** What is for sale is the
software, the documentation, the Arabic localisation, and the brand — not a
business.

---

## What is measured, and what it means

| | |
|---|---|
| Python | 40,035 lines |
| Templates | 33,891 lines across 170 files |
| Routes | **378** across 33 registered blueprints |
| Database | **72 tables**, 60 indexes, Alembic migrations with a verified baseline |
| Tests | **573 passing**, no external services required, CI on every push |
| Localisation | **4,424 translated strings**, 169 of 170 templates, incl. Arabic in generated PDFs |
| History | 56 commits over 68 days, one author |
| Licences | No GPL/AGPL. Three LGPL dependencies. Fonts are OFL (commercial use permitted) |

Two of those deserve emphasis, because they are the hardest to reproduce:

**The Arabic is real and it is complete.** Not a translation file — right-to-left
layout throughout, and correct Arabic rendering in generated PDF invoices,
vaccination certificates and payslips. Arabic in PDFs is a notorious failure
point: it requires a font with the right glyph coverage, letter-shaping, and
bidirectional reordering, and getting any one wrong produces either a crash or
unreadable output. This was found and fixed at exactly that level of detail.

**The module breadth is unusual.** Competitors in this category sell clinical
records plus billing. This also includes inventory with batch and expiry
tracking, procurement, retail POS, HR, attendance, payroll and double-entry-style
accounting (P&L, cash flow, budget, daily closing). No competitor identified in
the market research covers grooming *and* boarding *and* payroll *and* pet-shop
retail in one system.

---

## What is not true of it

Stated plainly, because a buyer's reviewer will find all of these and they cost
less disclosed than discovered.

- **Zero customers, zero revenue, no operating history.** Nothing here has been
  run by a paying clinic.
- **Single-tenant.** One deployment per clinic. `clinic_id` exists in the schema
  and is never read. Retrofitting multi-tenancy is estimated at 40–60 developer-
  days and carries a silent cross-clinic data-leak risk that no current test
  would catch.
- **Test coverage is 18% by route.** 573 tests is a real number; it is also
  concentrated. 177 routes have no test. The PostgreSQL CI job is non-blocking,
  so the green build is a statement about SQLite.
- **Money is stored as binary floating point** in 34 columns. One
  customer-visible defect this caused has been fixed and the corrective migration
  is written and tested, but deliberately unapplied — see `01_TECHNICAL_DOSSIER`
  §4 for why applying it without the surrounding work would achieve little.
- **The permission engine is applied to zero routes.** It exists and works;
  authorisation is still by hardcoded role lists. The administration screen
  therefore does not do what it appears to do.
- **A recurring pattern**: this codebase builds correct mechanisms and does not
  finish rolling them out. Permission engine, field-level audit, money migration
  and fleet tooling are all built and under-deployed. That is a fair criticism
  and also a short roadmap.
- **No lab-machine integration, no pet-owner mobile app, no payment gateway, no
  e-invoicing integration.** These are the four things a competing product is
  most likely to have.

---

## Market context

From primary research in `docs/market/` — sourced, with unverified figures marked
as such.

- Egypt has roughly **350–500 addressable companion-animal clinics**. Egypt-only
  revenue at 20% penetration in year three is approximately **USD 25,000/year** —
  a two-person business with a hard ceiling. The often-quoted "4,500 Egyptian vet
  clinics" figure is untraceable to any primary source.
- **Morocco** is the strongest adjacent market: 300–700 clinics at 2–3× Egyptian
  price points, in a currency that has not collapsed. It requires French.
- **Saudi Arabia** has 434 clinics at 5–9× Egyptian pricing, gated behind ZATCA
  Phase 2 e-invoicing, which is a substantial technical prerequisite.
- The category is **not empty**. VetICare ships Arabic RTL with lab-analyser
  integrations, a pet-owner app and named Egyptian customers. Being Arabic-first
  is not, by itself, a defensible position.
- **E-invoicing mandates are the strongest available wedge** — they make software
  a legal obligation with a deadline. Egyptian clinics were named in e-receipt
  Phase 7, effective March 2025. That integration is *not built*.

---

## Who this is for

Ranked by likely fit, from `03_BUYER_SHORTLIST`:

1. **MENA vertical-software houses and healthcare-IT vendors** — can absorb a
   Flask codebase without new hires, monetise it many times rather than once, and
   already know what Arabic-through-to-PDF costs to build.
2. **Regional pet-care groups** operating retail, grooming and boarding alongside
   clinical services — the only buyers who need the full module set.
3. **Existing veterinary software vendors** acquiring the localisation or the
   module breadth.
4. **Veterinary chains** — viable, but they reprice the deal by the cost of a
   developer they must then employ permanently.

---

## What transfers

Full source and git history, 573 automated tests, CI configuration, Alembic
migrations, the complete Arabic localisation, one-command provisioning with
per-clinic secret generation, verified backup and restore, a technical audit, six
market-research documents, and the brand (name, domain, marketing site).

**What does not transfer:** customers, revenue, support contracts, trademark
registration (none exists), e-invoicing accreditation (none exists), and any
third-party service account personal to the seller.

**Known encumbrance:** a credential appears in early git history and cannot be
removed from it. Any deployment derived from this code must rotate it. Details in
`05_ASSET_INVENTORY`.

---

## How to evaluate it

1. **`04_HANDOVER.md`** — clone, install, run the tests. Every command was
   executed on a clean machine before being written down. Budget 30 minutes.
2. **`02_DEMO_GUIDE.md`** — seed the demo clinic and follow the 10-minute
   click-path. It deliberately includes unpaid invoices, no-shows and abnormal
   lab results, because a dataset where everything is clean demonstrates nothing.
3. **`01_TECHNICAL_DOSSIER.md`** — the full defect register with effort estimates.
   Read this before making an offer, not after.

---

## A note on how these documents were written

Every claim here was verified by execution rather than by reading. Where a
previous document in this set was contradicted by the code, the contradiction is
recorded rather than quietly corrected — `01_TECHNICAL_DOSSIER` §"what a
reviewer will object to" names the single strongest argument against this asset,
including the fact that a large share of the commit history landed immediately
before these documents were written.

That is deliberate. An asset with no revenue is bought on trust in the seller's
description of it, and a description that survives checking is worth more than a
flattering one.

---

*Contact and technical questions: see `03_BUYER_SHORTLIST` §4 for the intended
disclosure sequence, including what is shared before and after an NDA.*
