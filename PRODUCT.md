# Aleefy — veterinary clinic management

**Register:** product. Design serves the task. Staff are mid-shift with an animal
on the table and an owner waiting.

## What it is

A single system a veterinary clinic runs its whole day on: reception, clinical
records, pharmacy dispensing, inpatient, grooming, boarding, retail, HR,
payroll, accounting. 34 modules, 376 routes, Flask + Jinja + raw SQL, SQLite in
development and PostgreSQL in production.

Egypt-first. Bilingual English/Arabic with full RTL, Arabic PDFs, WhatsApp
reminders, EGP, cash as the primary payment method.

## Who uses it

| | Doing what | Under what pressure |
|---|---|---|
| **Reception** | Books, registers walk-ins, bills, takes cash | An owner at the counter and a phone ringing |
| **Veterinarian** | Examines, diagnoses, prescribes | Animal on the table, 12 more booked today |
| **Nurse** | Vitals, medication rounds, inpatient care | Moving between cages |
| **Pharmacist** | Dispenses against prescriptions, tracks batches | Expiry and stock accuracy matter clinically |
| **Owner / manager** | Accounts, payroll, stock, reports | End of day, wants numbers to reconcile |

The common thread: **nobody is browsing.** Every screen is opened to finish
something. Speed and legibility beat elegance every time.

## Physical scene

A small Cairo clinic. Bright fluorescent light, a desktop at reception with a
mid-range monitor, a tablet in the consult room, phones in pockets. Screens are
read at arm's length, often at a glance, sometimes with one hand while the other
holds an animal. Daytime, always.

That scene forces **light theme** as the default: the room is bright, the
documents printed are white, and a dark UI would fight both. Dark mode exists
for night shift and is a real theme, not an inversion.

## Design constraints that are not negotiable

- **Bilingual, RTL-complete.** Arabic is not a translation layer bolted on; it
  is half the users. Every layout must survive `dir="rtl"`, and Arabic text must
  never be truncated mid-word.
- **Money is read, not skimmed.** Amounts are tabular, two decimals, always with
  the currency implied by context. A misread total is a dispute at the counter.
- **Clinical safety information outranks aesthetics.** Allergies, drug
  interactions and dosages get the strongest available treatment, and must
  appear *before* the action they protect against — not after.
- **Never imply a check ran that did not.** An empty result and an unverified
  result must look different. A green "safe" badge on a check that never
  executed is worse than no badge.
- **Works on a phone.** Vets use tablets in the consult room; the waiting-room
  kiosk is a screen on the wall. 375px is a real target, not a courtesy.

## Design system in place

CSS custom properties in `platform/static/css/tokens.css`, mirrored into
`app.min.css`.

- **Primary** `--c-primary` `#0B7A6B` — a clinical teal. Actions, current step,
  selection. Not decoration.
- **Accent** `--c-gold` `#D4A017` — used sparingly, mostly for Arabic wordmarks
  and highlights.
- **Semantic** `--c-success / --c-warning / --c-danger / --c-info`, each with a
  `-bg` and `-bd` companion so states are a triple, never a lone colour.
- **Surfaces** `--bg` `#F7F5F1`, `--surface` `#FFFFFF`, `--surface-sunk`,
  `--surface-hover`. Sidebar is its own darker layer (`--sidebar-bg` `#0A1F17`).
- **Type** DM Sans for Latin, Cairo for Arabic, one family per script, weights
  carrying hierarchy. Fixed rem scale.
- **Radii** `--r-sm` 6 / `--r-md` 10 / `--r-lg` 16. **Spacing** `--sp-1..12` on a
  4px base.

Strategy: **Restrained.** Tinted neutrals, one accent for actions and state.
The colour in a clinic screen should come from the data — a red overdue balance,
an amber expiring batch — not from the chrome.

## Where the design has to be best

`/workflow/` — the one-page visit. A walk-in goes from unknown client to settled
invoice without navigating away. It is the most-used screen in the building and
the one a buyer is shown first. Everything above applies to it hardest.
