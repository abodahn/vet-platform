# Demo Guide — Aleefy Veterinary Platform

How to stand up a full working demo from nothing, and a 10-minute click-path
that shows the product at its best without walking into anything that is not
finished.

Read the **"Do not demo these"** section before your first pitch. Getting caught
claiming a feature that does not exist costs more than the feature would have won.

---

## 1. Stand it up from nothing

Three commands. Takes about a minute.

```powershell
cd D:\vet\platform

# 1. Environment (SQLite — no PostgreSQL needed for a laptop demo)
$env:FLASK_ENV      = "development"
$env:POSTGRES_DSN   = ""

# 2. Build the demo database
D:\vet\.venv\Scripts\python.exe scripts\seed\demo_showcase.py --db data\demo.db

# 3. Run the app against it
$env:PLATFORM_DB_PATH = "$PWD\data\demo.db"
D:\vet\.venv\Scripts\python.exe run.py
```

Open <http://localhost:5100>.

| Login          | Password    | Shows                                        |
|----------------|-------------|----------------------------------------------|
| `admin`        | *(see your demo credentials note)* | Everything (super_admin)                     |
| `dr.sara`      | *(see your demo credentials note)* | Doctor view — queue, patients, visits         |
| `rec.yasmine`  | *(see your demo credentials note)* | Reception — appointments, POS. UI in Arabic.  |
| `fin.dalia`    | *(see your demo credentials note)* | Finance — invoices, expenses, P&L             |
| `hr.marwa`     | *(see your demo credentials note)* | HR — staff, attendance, payroll               |

Override the admin password with `DEMO_ADMIN_PASS` if you want something else on
a machine you leave with a prospect.

### Resetting between demos

Re-running the seeder **is** the reset. It clears its own scope first, so a
database that has been clicked through goes back to byte-identical starting
counts:

```powershell
Remove-Item Env:PLATFORM_DB_PATH   # see note below
D:\vet\.venv\Scripts\python.exe scripts\seed\demo_showcase.py --db data\demo.db
```

`--wipe` clears the demo data without re-seeding, if you want an empty system to
show what a first-day clinic sees.

> **Why clear `PLATFORM_DB_PATH` first:** the seeder refuses to write to whatever
> database the app is *configured* to use, and to `data/platform.db`, whatever
> the environment says. That is deliberate — an environment variable must not be
> able to disarm the guard on a real clinic's data. With `PLATFORM_DB_PATH`
> still pointing at `demo.db`, the seeder will (correctly) ask for `--force`.

### The safety rule

`scripts/seed/demo_showcase.py` **will not** write to `data/platform.db` or to
the configured `PLATFORM_DB_PATH` without an explicit `--force`. It exits
non-zero and explains why. There is no path where forgetting `--db` destroys a
working database.

---

## 2. What is in the dataset

Entirely synthetic. No real owner, pet, phone number or clinical record. Written
to be plausible to an Egyptian vet: Cairo districts, `010/011/012/015` mobile
numbers, EGP at 2026 Egyptian price points (a consultation is **350 EGP**, not
$200), and species/breeds that actually walk through the door here — Baladi cats
and dogs, Shirazi, Griffon, budgerigars, red-eared sliders.

| | Count |
|---|---|
| Clinic branches | 2 (Nasr City, Heliopolis) |
| Staff users | 14, across 10 roles |
| Owners / pets | 60 / 83 |
| Appointments | 509 over ~6 months + 14 days forward |
| Completed visits | 393 |
| Diagnoses / treatment plans | 393 each |
| Prescriptions | 351, with 608 stock deductions behind them |
| Lab requests + results | 124 |
| Vaccinations | 67 |
| Surgeries | 34 |
| Follow-ups | 106 |
| Invoices | 393 |
| Payments | 329 |
| Inventory items / suppliers | 20 / 4 |
| Pet-shop products / POS orders | 14 / 175 |
| Grooming / boarding bookings | 73 / 24 |
| Inpatient stays | 3 (one still admitted) |
| Attendance records | 1,078 across 90 days |
| Payslips | 42 (3 months × 14 staff) |
| Expenses / daily closings | 48 / 51 |
| WhatsApp messages logged | 104 |
| Audit-log entries | 240 |

**Bilingual by design.** Every owner, staff member, inventory item, pet-shop
product and service carries both an English and an Arabic name. About a third of
pets are named in Arabic only (بسبس, مشمش, لولو) because that is how an Egyptian
receptionist actually types them. All Arabic is NFC-normalised with zero-width
and bidi marks stripped, so it compares and searches correctly rather than
looking right and matching wrong.

**Deliberately imperfect.** A dataset where everything is paid, present and
normal proves nothing:

- 64 unpaid and 55 partially-paid invoices — ~135,000 EGP outstanding
- 42 no-shows and 29 cancellations
- 37 of 124 lab results flagged abnormal
- 4 stock batches expiring inside 60 days; 4 items below reorder point
- Absences, late check-ins and pending leave requests in attendance
- One surgery outcome recorded as "Complicated"

The numbers above are stable — the generator is seeded, so every machine gets the
same dataset and you can rehearse against exact figures.

---

## 3. The 10-minute click-path

Login as **`admin`**. The story is *one clinic day, followed end to end* — that
is the thing competitors cannot show, because their modules do not talk.

### Minute 0–1 — Dashboard (`/`)

Open on the home dashboard. Point at: today's appointments, revenue this month,
outstanding balance, low-stock and expiry alerts, all live off the same data.

> "Nothing on this screen was typed in. It is all rolled up from what the clinic
> did this month."

### Minute 1–2 — Today's schedule (`/appointments/`)

7 appointments on today's board, in mixed states: completed, checked-in,
confirmed, scheduled. Show the status colours and the channel column — WhatsApp,
phone, walk-in, online.

Then `/appointments/waiting-room` — the screen you put on a monitor in the
waiting area.

> "Reception books here. The doctor never asks who is next."

### Minute 2–4 — The connected chain (the money slide)

This is the part to slow down on. **Pick one completed appointment from an
earlier date and follow it.**

1. `/visits/` — open a completed visit. It carries the appointment it came from,
   vitals, chief complaint in Arabic and English.
2. Same page: the **diagnosis** and **treatment plan** the doctor recorded.
3. Same page: the **prescription**, with dose, frequency, route and duration.
4. `/inventory/movements` — filter by that item. The prescription **already
   deducted the stock**, FEFO, against a specific batch, with the visit id as
   the reference.
5. `/finance/invoices` — the invoice for that visit, with the consultation, the
   medication and any lab work as separate lines.
6. Open it — a partly-paid one is best. Payment method, reference, balance due.

> "One appointment. Four modules updated. Nobody re-typed anything. Ask the
> product you are using today how many places a dispensed antibiotic gets
> entered."

### Minute 4–5 — Bilingual, live

Log out. Log in as **`rec.yasmine`** — her account is set to Arabic. The whole
interface flips to RTL, Arabic labels, Arabic pet and owner names, and the
numbers stay the same.

> "Your receptionist works in Arabic. Your accountant works in English. Same
> database, same shift."

Log back in as `admin`.

### Minute 5–6 — Clinical depth (`/clinical/lab`, `/clinical/vaccinations`)

Lab results with reference ranges and abnormal flags in red. Vaccination register
with next-due dates. `/clinical/surgeries` for the surgical log.

> "The vaccine reminder that brings the client back next year is already
> scheduled from this row."

### Minute 6–7 — Stock and pharmacy (`/inventory/items`, `/pharmacy/history`)

Batches, expiry dates, reorder points. `/pharmacy/history` shows every dose
dispensed, by whom, from which batch.

> "When a batch is recalled you can answer 'which of my patients got it' in one
> query. On paper that question has no answer."

### Minute 7–8 — The modules competitors do not have

Fast — 15 seconds each, do not linger:

- `/petshop/pos` — a real point of sale. Barcode field, cart, change due.
- `/petshop/orders` — 175 shop orders; the revenue lands in Finance automatically.
- `/grooming/bookings` and `/boarding/bookings` — booked as services, invoiced
  like any other.
- `/inpatient/` — an admitted patient with nursing rounds and medication log.

> "This is a clinic *and* a shop *and* a boarding facility. Most vet software
> covers the first one and tells you to keep a notebook for the rest."

### Minute 8–9 — Staff (`/hr/dashboard`, `/attendance/records`, `/payroll/salaries`)

Headcount, 90 days of attendance with real absences and late arrivals, three
months of payslips, expiring syndicate licences under `/hr/certifications`.

> "Your accountant currently builds payroll from a WhatsApp group and a
> notebook. This builds it from the check-in clock."

### Minute 9–10 — Owner, close on control

`/reports/dashboard` and `/accounting/pl` — profit and loss with real expense
categories, cash-flow, daily closings.

Then `/system/audit` — 240 logged actions, who did what and when.

> "Every deletion, every price change, every discount. If a clinic owner asks me
> for one reason to buy, it is usually this screen."

**Close there.** Do not keep clicking.

---

## 4. Do not demo these — they do not exist

Say so plainly if asked. A prospect who catches an overclaim stops believing the
parts that are true.

| Claim | Reality |
|---|---|
| **Lab-machine integration** | Does not exist. Results are typed in or pasted. No analyser driver, no HL7, no LIS bridge. |
| **Pet-owner mobile app** | Does not exist. There is no app for clients, on any platform. |
| **Online payment gateway** | Does not exist. Payments are *recorded* — cash, card, InstaPay — not *taken*. Nothing charges a card. |
| **ETA / e-invoicing** | Not implemented. It appears only in internal market research. |

Two more worth being straight about:

- **WhatsApp** sends through an unofficial gateway, not the Meta Cloud API. It
  works, and it is against WhatsApp's terms. Do not promise it will never break.
- **Roles and permissions**: the roles screen renders and reads well, but the
  permission checkboxes are not yet wired to route authorisation — access is
  enforced by role name in code. Show `/system/roles` as *"roles per staff
  member"*, not as *"build your own permission set"*.

### Two screens to skip

- **`/inventory/alerts`** — errors out when the low-stock list is non-empty.
  Template reads `item.current_stock`; the query returns the column as
  `stock_qty`. Use `/inventory/items` and `/inventory/movements` instead; the
  same information is there and both render fine. (Pre-existing bug, unrelated
  to the demo data — the demo just makes it reachable by producing real alerts.)
- **`/telemedicine/`** — it works, but it opens a public Jitsi room. Do not start
  a call live in front of a prospect unless you have tested the room on that
  network.

---

## 5. Troubleshooting

**"REFUSING to seed a live application database"** — working as intended. Either
pass `--db <somewhere-else.db>`, or clear `PLATFORM_DB_PATH` from your shell.

**Blank dashboard / zero everywhere** — the app is pointed at a different file
from the one you seeded. Check `PLATFORM_DB_PATH` and that `POSTGRES_DSN` is
empty; a non-empty DSN sends the app to PostgreSQL and ignores the SQLite file
entirely.

**Arabic renders as boxes in a PDF** — the Cairo font subset. Unrelated to the
data; see `docs/` for the PDF font notes.

**Dates all look wrong** — the dataset is generated relative to *today* at seed
time. If you seeded a month ago, re-seed.
