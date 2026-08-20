# Sale pack — how these documents fit together

Seven documents. They are written to be read in different orders by different
people, so start with the row that describes you.

| If you are… | Read, in this order |
|---|---|
| **A buyer, first contact** | `00_EXECUTIVE_SUMMARY` → stop. Everything else is for after interest is real. |
| **A buyer, evaluating seriously** | `00` → `02_DEMO_GUIDE` (see it run) → `01_TECHNICAL_DOSSIER` (see what is wrong with it) → `05_ASSET_INVENTORY` (see what you get) |
| **A buyer's engineer** | `04_HANDOVER` → `01_TECHNICAL_DOSSIER` → the code |
| **The seller, running a process** | `03_BUYER_SHORTLIST` → `00` → the checklist below |

---

## What each document is

| | Document | Purpose | Audience |
|---|---|---|---|
| **00** | `EXECUTIVE_SUMMARY.md` | The one document you send first. What it is, what it is not, what it is worth evaluating. | Buyer |
| **01** | `TECHNICAL_DOSSIER.md` | Measured statistics and the complete defect register with effort estimates. Deliberately unflattering. | Buyer's technical reviewer |
| **02** | `DEMO_GUIDE.md` | Stand up a realistic demo clinic and a 10-minute click-path. Includes a "do not demo these" table. | Both |
| **03** | `BUYER_SHORTLIST.md` | Named targets with real contact routes, what to lead with per category, disclosure sequencing. | Seller only — never send this |
| **04** | `HANDOVER.md` | Day-one commands, architecture, and the traps that will break a new developer. | Buyer's engineer |
| **05** | `ASSET_INVENTORY.md` | Exactly what transfers, what does not, and known encumbrances. | Buyer's lawyer and engineer |
| **06** | `DECK_CONTENT.md` | Raw material for an acquirer presentation: every headline number re-measured, the four proof-of-rigour stories, the gaps, and a slide-by-slide skeleton. **Corrects `00`'s stale figures.** | Seller, building the deck |

**`03_BUYER_SHORTLIST` is internal.** It names competitors as targets and
discusses what to withhold from them. Sending it to a buyer would be an
unforced error.

---

## How this connects to the market research

`docs/market/` (nine documents) is the evidence base underneath the commercial
claims in `00`. It is research, not sales material — send extracts, never the
folder.

| | Answers |
|---|---|
| `01_COMPETITORS` | Who else sells this, and why Arabic alone is not a moat |
| `02_MARKET_SIZE` | TAM/SAM/SOM with sensitivity analysis. The honest ceiling |
| `03_PRICING_AND_ECONOMICS` | Pricing model, unit economics, break-even |
| `04_GOTOMARKET` | Named channels and a costed launch plan |
| `05_PRODUCT_READINESS` | The pre-remediation state. **Partly superseded** — much has since shipped; `01_TECHNICAL_DOSSIER` is current |
| `06_ARABIC_MARKETS` | Morocco, Jordan, Tunisia. Which markets payment friction disqualifies |
| `07_SUBSAHARAN_AFRICA` | Verdict: no, and why |
| `08_ASIA` | Verdict: no. The e-invoicing wedge does not reach clinics there |
| `09_PAYMENT_RAILS` | **Read before running any process.** How an Egyptian seller gets paid |

And the engineering record: `docs/AUDIT_AND_PLAN_2026-07-25.md` (the original
technical audit, including four findings later proved wrong — corrections are
marked in place), `docs/MONEY_PRECISION.md`, `../MIGRATIONS.md`,
`../PROVISIONING.md`, `../deploy/BACKUP_RUNBOOK.md`.

---

## Before contacting anyone — seller checklist

These are ordered. Item 1 blocks the rest.

- [ ] **Set up a payment route that works from Egypt.** Escrow.com does not
      support Egyptian residents and PayPal cannot receive there, so the default
      settlement rail for every marketplace and most direct buyers is unavailable.
      `09_PAYMENT_RAILS` has the working options. A buyer asking "how do I pay
      you?" and hearing nothing is a dead deal.
- [ ] **Rotate the exposed credentials.** One is in git history and cannot be
      removed from it — disclose it rather than let a reviewer find it.
- [ ] **Run one real provision → upgrade → rollback → restore cycle on a Linux
      host and keep the log.** This is the direct answer to the strongest
      objection in `01_TECHNICAL_DOSSIER`.
- [ ] **Decide what is withheld until an NDA.** `03_BUYER_SHORTLIST` §4.
- [ ] Consider whether two or three pilot clinics are reachable first. The
      research is consistent that "working software" and "working software three
      clinics use daily" are different assets. If they are not reachable, sell
      now rather than let it age.

---

## The one thing that holds this together

Every document here was written to survive checking. Claims are measured, not
estimated; where an earlier document was contradicted by the code, the
contradiction is recorded rather than quietly edited out.

That is a commercial decision, not a moral one. An asset with no revenue is
bought on trust in the seller's description of it. A description that holds up
under a reviewer's scrutiny is worth more than a flattering one that does not.
