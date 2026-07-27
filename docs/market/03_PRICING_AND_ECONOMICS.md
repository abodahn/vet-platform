# Aleefy — Pricing, Packaging and Unit Economics (Egypt)

**Date:** 28 July 2026
**Product:** Aleefy — self-hostable veterinary clinic ERP (Python/Flask + PostgreSQL, 28 modules, EN/AR bilingual with RTL)
**Constraints assumed:** 1 developer + 1 veterinary partner, free/open-source tooling preferred, little or no capital, business must generate income.

**Exchange rate used throughout:** **1 USD = 50.72 EGP** — mid-market rate, [xe.com, 27 July 2026](https://www.xe.com/currencyconverter/convert/?Amount=1&From=USD&To=EGP). EGP has moved a lot; re-check before quoting a customer. All USD figures in this document are conversions at that rate unless a source quotes USD natively.

**Source discipline:** every external number below carries a link. Anything I could not source is explicitly marked `[UNSOURCED — estimate]`.

---

## T1 — Monetisation model: evaluation and recommendation

### 1.1 The buyer

An Egyptian small-animal vet clinic. Anchor on what they charge: a routine consult in Egypt runs **200–500 EGP**, with home visits 400–600 EGP ([The30 Vetcenter](https://the30vetcenter.com/%D8%B3%D8%B9%D8%B1-%D8%A7%D9%84%D9%83%D8%B4%D9%81-%D8%A7%D9%84%D8%A8%D9%8A%D8%B7%D8%B1%D9%8A-%D9%81%D9%8A-%D9%85%D8%B5%D8%B1/), [Petlivery](https://petlivery.net/%D8%B3%D8%B9%D8%B1-%D8%A7%D9%84%D9%83%D8%B4%D9%81-%D8%A7%D9%84%D8%A8%D9%8A%D8%B7%D8%B1%D9%8A-%D9%81%D9%8A-%D9%85%D8%B5%D8%B1/)).

A single-vet clinic doing ~12 consults/day at ~300 EGP over 26 days grosses roughly **93,000 EGP/month** before pharmacy and retail margin `[UNSOURCED — my arithmetic on the sourced consult fee]`. Software at 1–2% of gross revenue is the normal software-spend band, which puts the defensible ceiling at roughly **900–1,900 EGP/month** for a small clinic. That is the number every tier below is reasoned against.

Two behavioural facts matter more than the arithmetic:

1. **Egyptian SMEs buy capex, not opex.** The local market visibly prices this way. Pharmacy software is sold as a **perpetual licence at 5,000–12,000 EGP**, with advanced systems above 20,000 EGP upfront ([Aumet](https://aumet.com/%D8%A7%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A8%D8%B1%D8%A7%D9%85%D8%AC-%D8%A7%D9%84%D8%B5%D9%8A%D8%AF%D9%84%D9%8A%D8%A7%D8%AA-%D8%AF%D9%84%D9%8A%D9%84%D9%83-%D9%84%D8%A7%D8%AE%D8%AA%D9%8A%D8%A7%D8%B1-%D8%A7/)). POS/accounting is sold module-by-module as a perpetual buy — 1,000 EGP for customers/suppliers, 2,000 for warehouses, 7,000 for the Egyptian e-invoice integration, **43,000 EGP for the full system** ([Deltawy](https://deltawy.com/article/403/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D8%AC-%D8%A7%D9%84%D9%83%D8%A7%D8%B4%D9%8A%D8%B1)). The subscription-native vendors exist but are the minority of local sellers.
2. **They will ask "هو ده بتاعي ولا بتاعك؟"** — do I own this or am I renting it? Renting software is still culturally treated as a worse deal, particularly by owner-operators who bought their ultrasound outright.

### 1.2 Model-by-model evaluation

| Model | Fit with Egyptian SME behaviour | Cash flow for a founder with no capital | Piracy risk (self-hosted) | Support burden |
|---|---|---|---|---|
| **Monthly SaaS** | Poor–fair. Low entry price is attractive but the "forever payment" objection is real and monthly collection in Egypt is manual (see T3). | **Bad.** 10 clinics at 1,500 EGP = 15,000 EGP/month, and only after a full ramp. Starves the founder in year 1. | Low if hosted, high if self-hosted (nothing stops them cancelling and keeping the last build). | High — 12 collection events per customer per year, each a manual chase. |
| **Annual subscription** | Good. One payment per year matches how clinics budget, and it's a familiar shape (their accountant, their landlord). | **Fair–good.** Cash arrives upfront in a lump. | Moderate — after year 1 they hold a working copy and may simply not renew. | Moderate — one renewal conversation per year. |
| **Perpetual licence + annual support** | **Best.** Exactly the shape the local pharmacy/POS market already sells. Removes the ownership objection entirely. | **Best.** Largest day-1 cash per customer by a wide margin (see T2 arithmetic). This is what funds year 1. | Moderate — but the incentive to crack largely disappears once they legitimately own it. Risk shifts to *redistribution* to other clinics. | Moderate — support is explicitly a paid, scoped product rather than an implied obligation. |
| **Freemium / permanent free tier** | Poor for self-hosted. | **Bad.** Zero revenue, full support load. | N/A. | **Fatal for a one-person team.** A free self-hosted tier is a published free product with an implied support obligation and no revenue to pay for it. |
| **Open-core** | Poor *for this vertical*. Open-core works when the free tier creates distribution at scale. The Egyptian small-animal clinic market is small enough that there is no flywheel — you'd hand a complete 28-module vet ERP to any local competitor and receive approximately zero contributions back. | Bad. | You have *created* the copy problem. | High. |
| **Per-user pricing** | **Bad. Do not do this.** Egyptian clinics respond to per-seat pricing by sharing one login. That destroys the value of the audit log and RBAC (two of the 28 modules), and creates unwinnable billing disputes. | Neutral. | Neutral. | High — you end up policing seats. |
| **Per-clinic / per-branch pricing** | **Best.** A branch is a physical, countable, undeniable thing. Users inside it are unlimited, which makes the audit log honest. | Neutral. | Neutral. | Low. |
| **Transaction / usage fees** (cut of WhatsApp reminders or online payments) | **Poor.** Two problems: Egyptian SME owners react badly to "you take a cut of my money", and unpredictable bills kill the close. Worse — to bill a % of *their* payment volume you need them to trust your meter. | Neutral. | Neutral. | High — metering disputes are the worst kind of support ticket. |
| **One-off setup / migration fee** | **Good, and underused.** Clinics accept paying for a person to come, install, import their Excel patient list and train the staff. It is visible, tangible labour. | **Good.** Immediate cash, and it's paid by the customer at the moment of highest enthusiasm. | N/A. | It *is* the support, priced. |

### 1.3 Recommendation

> **Sell a perpetual, per-branch licence with the first 12 months of support and updates included, plus a separately-priced one-off setup/migration fee. Renew support annually at 25% of the licence price. Offer an annual subscription as the cash-flow alternative for clinics that cannot pay capex, priced so that three years of subscription equals the licence + two support renewals. Do not offer monthly at launch. Do not offer a permanent free tier. Do not open-source the core. Do not take a percentage of anything.**

Defence:

- **It is the only model that pays the founder in year 1.** T2 shows year-1 revenue from 10 clinics at roughly **312,000 EGP** under perpetual versus **~139,000 EGP** under monthly SaaS. With no capital, the difference between those two numbers is the difference between the business existing in month 9 and not.
- **It matches how this market already buys.** You are not educating the customer about a new commercial model at the same time as you are educating them about a new product. One fight at a time.
- **The recurring revenue is attached to things that cannot be copied.** See 1.4.
- **It converts support from an unbounded liability into a priced product.** For a one-person team that is not a pricing detail, it is a survival requirement.

Sequencing note: the honest first-year plan is **5–8 clinics, not 10**, at a 40–50% design-partner discount for the first five, in exchange for a named testimonial and a site visit for the next prospect. An unknown solo vendor with no reference customers does not close 30,000 EGP deals at list price. Price the discount in deliberately rather than discovering it in negotiation.

### 1.4 The piracy question — answered directly

The tension is real and cannot be engineered away. Aleefy is **Python running on a clinic PC**. The source is on the customer's disk. Anyone who wants to read it, can.

**What does not work:**

- **Phone-home activation.** Fails for clinics that run offline (which is a feature you are selling — "works when the internet is down"), and is removed from Python source in an afternoon by any competent local developer.
- **Signed licence keys as a hard block.** Same removability. Worse, a licence check that *blocks* the app is a catastrophic failure mode: the day it misfires, a vet is standing in front of a client unable to open a patient record. That single incident costs more in reputation than a year of piracy.
- **Obfuscation / compilation** (PyArmor, Nuitka). Raises the bar, does not close the door, and makes your own debugging materially harder. For a one-person support team that is self-inflicted injury.
- Egypt's unlicensed-software rate was **59% as of the last BSA study reported locally** ([Egypt Today](https://www.egypttoday.com/Article/3/57869/BSA-Egypt-sees-software-piracy-drop-by-2)). Note this figure is dated (2018 study) and the trend was improving, but plan as though copying is normal, not exceptional.

**What actually works — make the copy worth less than the licence:**

1. **Keep the un-copyable parts on your side.** The WhatsApp gateway account, the AI proxy key, off-site encrypted backups, and (critically) Egyptian Tax Authority e-invoice submission all run through *your* credentials. A pirated build boots, but it has no WhatsApp, no AI assistant, no backups, and cannot submit an e-receipt. That is most of what a modern clinic actually wants.
2. **Compliance rot.** Egyptian tax and e-invoicing rules change. A frozen pirated build silently goes out of compliance, and the clinic finds out from the tax authority rather than from you. Sell that risk honestly.
3. **Data gravity on the hosted tier.** Nothing local to copy.
4. **Social enforcement.** The Egyptian small-animal vet community is small and highly connected. Publish a list of licensed clinics (with permission) and a window sticker. Running an unlicensed copy of the system your peers paid for has a visible cost.
5. **Ship a licence file anyway — as accounting, not as a lock.** A signed JSON licence checked at startup that shows a non-blocking banner when expired. It costs a day, gives you a legal hook and tells you who is running what. It must never prevent the app from opening.
6. **Budget for leakage.** Assume 10–20% of installations will eventually be unlicensed `[UNSOURCED — planning assumption]`. Price for it. Do not spend a week building DRM that a determined copier defeats in an hour.

**Licence wording:** ship as **source-available, not open-source** — the customer receives readable Python (they will anyway), licensed for use at the named branch, redistribution prohibited. Do not pretend the source is hidden; sell on the honesty instead ("you can read every line, and you can leave with your data").

---

## T2 — Price points in EGP

### 2.1 Comparable anchors (sourced)

| Comparable | What it is | Price | Source |
|---|---|---|---|
| **Daftra** Basic | Egyptian SME accounting/ERP, cloud, 100 invoices/mo, 100 clients, 1 warehouse | 733 EGP/mo list (489.50 promo) · **5,874 EGP/yr** | [daftra.com/en/plans](https://www.daftra.com/en/plans) |
| **Daftra** Advanced | 500 invoices/mo, 300 clients, 3 warehouses | 1,225 EGP/mo list (977.58 promo) · **11,731 EGP/yr** | [daftra.com/en/plans](https://www.daftra.com/en/plans) |
| **Daftra** Premium | Unlimited invoices/clients, 5 warehouses | 2,448 EGP/mo list (1,960 promo) · **23,520 EGP/yr** | [daftra.com/en/plans](https://www.daftra.com/en/plans) |
| **ClinicGateway** | Human clinic management, Egypt, incl. ETA e-Receipt + WhatsApp + Arabic RTL | **2,500 EGP/mo**, no setup fee | [clinicgateway.ae](https://clinicgateway.ae/blog/best-clinic-management-software-egypt-2025/) |
| **Doctorato** | Human clinic management, Egypt | from **1,990 EGP/mo**, free setup, 30-day trial | [doctorato.com](https://doctorato.com/blog/best-dental-clinic-software-saudi-arabia-2026?lang=en) |
| **Remote Clinic** | Human clinic management, Egypt | from **3,999 EGP/mo** | [remoteclinic.co.uk](https://www.remoteclinic.co.uk/) |
| Egyptian mid-market clinic software (range) | — | 5,000–8,000 EGP/mo + setup | [clinicgateway.ae](https://clinicgateway.ae/blog/best-clinic-management-software-egypt-2025/) |
| Egyptian enterprise clinic software (range) | — | 8,000–15,000+ EGP/mo, setup 50,000–200,000+ EGP | [clinicgateway.ae](https://clinicgateway.ae/blog/best-clinic-management-software-egypt-2025/) |
| **Pharmacy software, Egypt — basic** | Sales, inventory, basic features | **5,000–12,000 EGP perpetual** | [Aumet](https://aumet.com/%D8%A7%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A8%D8%B1%D8%A7%D9%85%D8%AC-%D8%A7%D9%84%D8%B5%D9%8A%D8%AF%D9%84%D9%8A%D8%A7%D8%AA-%D8%AF%D9%84%D9%8A%D9%84%D9%83-%D9%84%D8%A7%D8%AE%D8%AA%D9%8A%D8%A7%D8%B1-%D8%A7/) |
| **Pharmacy software, Egypt — chains** | Cloud analytics, supplier integration | 20,000+ EGP upfront, **500–1,500 EGP/mo** | [Aumet](https://aumet.com/%D8%A7%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A8%D8%B1%D8%A7%D9%85%D8%AC-%D8%A7%D9%84%D8%B5%D9%8A%D8%AF%D9%84%D9%8A%D8%A7%D8%AA-%D8%AF%D9%84%D9%8A%D9%84%D9%83-%D9%84%D8%A7%D8%AE%D8%AA%D9%8A%D8%A7%D8%B1-%D8%A7/) |
| **Egyptian POS/accounting (Deltawy)** | Per-module perpetual: 1,000 EGP (customers/suppliers) … 7,000 EGP (ETA e-invoice) | **Full system 43,000 EGP perpetual** | [Deltawy](https://deltawy.com/article/403/%D8%A3%D8%B3%D8%B9%D8%A7%D8%B1-%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D8%AC-%D8%A7%D9%84%D9%83%D8%A7%D8%B4%D9%8A%D8%B1) |

**What the anchors tell you:** the perpetual band for a *complete* Egyptian business system tops out around **43,000 EGP**, and the recurring band for clinic-specific software sits at **1,990–3,999 EGP/month** for human clinics. Vet clinics are smaller businesses than human clinics and will not pay the top of that band. Aleefy's realistic recurring ceiling is **the bottom of the human-clinic range, not the middle**.

### 2.2 Recommended tiers

Unit of pricing: **one branch (one physical clinic location). Users unlimited within the branch.**

| | **Solo** | **Clinic** | **Hospital** | **Chain** |
|---|---|---|---|---|
| **Who** | 1 vet, 1–2 staff, single PC | 2–4 vets, front desk, pharmacy | Inpatient + lab + imaging, 24h | 2+ branches |
| **Perpetual licence (EGP)** | **12,000** | **30,000** | **60,000** | 60,000 + **20,000 / extra branch** |
| **Annual support & updates from yr 2 (EGP/yr)** | **3,000** | **7,500** | **15,000** | 15,000 + 5,000/branch |
| **Annual subscription alternative (EGP/yr)** | **6,000** | **15,000** | **30,000** | 30,000 + 10,000/branch |
| **Setup / migration one-off (EGP)** | **3,000** | **6,000** | **12,000** | 12,000 + 4,000/branch |
| **WhatsApp add-on (EGP/mo)** | **400** | **600** | **900** | 900 + 300/branch |
| **Hosted cloud add-on (EGP/mo)** | 350 | 600 | 1,200 | 1,200 + 400/branch |

**Included / excluded by tier**

| Module group | Solo | Clinic | Hospital | Chain |
|---|:--:|:--:|:--:|:--:|
| Appointments, EMR, invoicing, clients/pets | ✅ | ✅ | ✅ | ✅ |
| Inventory (batch/expiry), pharmacy, retail POS | ✅ | ✅ | ✅ | ✅ |
| Reports, audit log, RBAC, 2FA, backups | ✅ | ✅ | ✅ | ✅ |
| Bilingual EN/AR + RTL | ✅ | ✅ | ✅ | ✅ |
| Accounting, procurement | — | ✅ | ✅ | ✅ |
| Lab, grooming, boarding | — | ✅ | ✅ | ✅ |
| HR, attendance, payroll | — | ✅ | ✅ | ✅ |
| Inpatient, imaging (incl. AI assist), telemedicine | — | — | ✅ | ✅ |
| AI assistant + customer chatbot | — | metered | metered | metered |
| WhatsApp integration | add-on | add-on | add-on | add-on |
| Multi-branch consolidation & cross-branch reporting | — | — | — | ✅ |
| Priority same-day support | — | — | ✅ | ✅ |

**Reasoning for each number**

- **Solo at 12,000 EGP perpetual** sits just above the Egyptian *pharmacy* perpetual band (5,000–12,000) because Aleefy does materially more than pharmacy software, and just below the psychological 15,000 barrier. It is roughly 40 consults' worth of revenue — a defensible sentence in a sales conversation.
- **Clinic at 30,000 EGP** is 70% of the full-system Egyptian POS perpetual (43,000) and is the tier that should carry the business. Three years of the 15,000 EGP/yr subscription = 45,000, versus licence 30,000 + two support renewals 15,000 = 45,000. **The two paths cross exactly at year 3**, which is a clean, honest thing to put on the price page and removes the cannibalisation problem.
- **Hospital at 60,000 EGP** is above the local POS ceiling, justified by inpatient + imaging AI + telemedicine. Expect this tier to be a *negotiated* sale with a site visit, not a price-list purchase.
- **Annual support at 25% of licence** is the standard enterprise ratio and is the number your business actually runs on. **Be honest about the renewal rate: expect 40–60% in year 2** `[UNSOURCED — planning assumption]` unless support is bundled with things that stop working without it (WhatsApp account, hosted backups, ETA compliance updates). Bundle them. That is the single highest-leverage packaging decision in this document.
- **WhatsApp priced as a flat monthly add-on, not a per-message fee.** See T4 — the underlying provider cost is flat, so a flat resale price converts a scary variable into a predictable one and protects the margin.
- **Setup fee is non-negotiable and always charged.** It funds the founder's time at the moment of maximum customer enthusiasm, and a customer who paid for onboarding actually shows up to onboarding.

### 2.3 One-off vs recurring — year-1 arithmetic for 10 clinics

Same 10 clinics in every model: **4 Solo, 5 Clinic, 1 Hospital.** List prices, no discount, so the models are directly comparable.

Setup fees are identical across all three models: `4×3,000 + 5×6,000 + 1×12,000 = 12,000 + 30,000 + 12,000 =` **54,000 EGP**.

**Model A — Perpetual licence (year 1 of support included in the licence)**

```
Licences:  4 × 12,000  =  48,000
           5 × 30,000  = 150,000
           1 × 60,000  =  60,000
                        --------
                         258,000
Setup fees                54,000
                        --------
YEAR 1 TOTAL             312,000 EGP   (≈ USD 6,150)

Year 2 recurring (support @25% of licence, 50% renewal):
  258,000 × 0.25 × 0.50 =  32,250 EGP   ← thin, and the honest weakness of this model
```

**Model B — Monthly SaaS** (Solo 600 / Clinic 1,500 / Hospital 3,000 per month)

```
Full monthly run-rate: 4×600 + 5×1,500 + 1×3,000 = 2,400 + 7,500 + 3,000 = 12,900 EGP/mo
Clinics sign up through the year, so assume an average of 55% of full run-rate over 12 months:

  12,900 × 12 × 0.55  =  85,140
Setup fees               54,000
                        --------
YEAR 1 TOTAL            139,140 EGP   (≈ USD 2,744)

Exit run-rate: 12,900 × 12 = 154,800 EGP/yr recurring going into year 2.
```

**Model C — Annual subscription paid upfront** (Solo 6,000 / Clinic 15,000 / Hospital 30,000 per year)

```
Subscriptions: 4 ×  6,000 =  24,000
               5 × 15,000 =  75,000
               1 × 30,000 =  30,000
                            -------
                            129,000
Setup fees                   54,000
                            -------
YEAR 1 TOTAL                183,000 EGP   (≈ USD 3,608)

Year 2 recurring (70% renewal): 129,000 × 0.70 = 90,300 EGP, plus new sales.
```

**Reading the arithmetic honestly**

| | Year 1 cash | Year 2 recurring base | Verdict |
|---|---|---|---|
| **A — Perpetual** | **312,000 EGP** | 32,250 EGP | Best survival odds. Worst compounding. |
| **B — Monthly SaaS** | 139,140 EGP | 154,800 EGP | Best compounding. **Will not feed the founder in year 1.** |
| **C — Annual subscription** | 183,000 EGP | 90,300 EGP | The balanced option. |

Perpetual pays **2.24×** what monthly SaaS pays in year 1. For a founder with no capital that is decisive — but the year-2 column is the reason not to sell perpetual *alone*. The recommended structure is therefore **A as the headline offer, C available on request, B never** — with the deliberate design choice that support renewals are bundled with services that stop working if unpaid, which is what drags Model A's year-2 number up towards Model C's.

**Realistic version of the same table.** Ten clinics in year 1 for an unknown solo vendor is optimistic. At **6 clinics (3 Solo, 3 Clinic)** with a **40% design-partner discount on the first five**:

```
Licences at list:  3×12,000 + 3×30,000 = 36,000 + 90,000 = 126,000
Discount: 5 of 6 at −40%  ≈  −40% on ~105,000 of that   ≈  −42,000
Net licences                                            ≈   84,000
Setup fees (3×3,000 + 3×6,000)                          =   27,000
                                                           -------
REALISTIC YEAR 1                                        ≈  111,000 EGP  (≈ USD 2,189)
```

That is **~9,250 EGP/month** of gross revenue for the founder in a realistic year 1. Hold that number — T5 measures it against a developer salary.

---

## T3 — Collecting money in Egypt

### 3.1 Paymob

**Fees (first-party, official):** **2.75% + 3 EGP per transaction. No setup fee, no monthly fee, no subscription fee** — "You are only charged per transaction". Settlement is **weekly** to your bank account. ([paymob.com/en/pricing](https://paymob.com/en/pricing), [paymob.com/ar/pricing](https://paymob.com/ar/pricing))

No published fee split between cards and mobile wallets — it is presented as one rate across methods. A third-party directory lists the same flat rate across cards, wallets and cash/kiosk with T+1 settlement ([bilixe.com](https://bilixe.com/listing/paymob-payment-gateway/)) — but that contradicts Paymob's own "weekly", so trust Paymob.

**Documents (first-party):** "All you will need is to upload your **commercial registration, Tax ID and National ID**" ([paymob.com/en/pos-solution](https://paymob.com/en/pos-solution)) — i.e. **سجل تجاري + بطاقة ضريبية + بطاقة رقم قومي**.

**Is a شركة required, or will a منشأة فردية do?** The document list is entity-agnostic: a **منشأة فردية (sole proprietorship) produces a commercial register and a tax card in the owner's own name**, which satisfies all three items. `[INFERENCE — I could not find any first-party Paymob statement either accepting or rejecting sole traders as distinct from companies.]` What is clear is that a **bare freelancer with no commercial register cannot onboard.** No Paymob freelancer/individual tier exists in any documentation found.

**Timeline:** "Document verification takes up to 3 days" was indexed from Paymob's Egypt FAQ, but **that page now 404s and could not be verified** `[WEAKLY SOURCED — treat ~3 business days as indicative]`.

**Minimum volume:** none published. An Enterprise tier exists for high volume via sales conversation, meaning 2.75% + 3 EGP is the small-merchant default and you negotiate down only once you have volume.

### 3.2 Fawry

**Company registration required.** "A Fawry merchant account can only be opened by a company based in Egypt… It will require that you have a commercial register and a Tax ID" ([WHMCS Marketplace](https://marketplace.whmcs.com/product/5540-fawry-for-whmcs)). Corroborated by an integrator write-up: commercial registration, tax card, bank account for settlement, KYC via the business portal, then a merchant code + security key + staging/production credentials ([911digital.co](https://911digital.co/en/blogs/how-to-integrate-fawry-payment-in-your-website-or-app)). SME entry point: [fawry.com/sme-registration-form](https://www.fawry.com/sme-registration-form/).

**Fees — Fawry publishes nothing. All figures below are third-party estimates:**
- Per-transaction "typically ranges from **1.5% to 2.5%**", reference-number/retail at the low end, online cards at the high end ([911digital.co](https://911digital.co/en/blogs/how-to-integrate-fawry-payment-in-your-website-or-app)) `[THIRD-PARTY ESTIMATE]`
- Consumer-side kiosk cash-in commission "typically between **EGP 3 and EGP 25**" ([themiddleeastinsider.com](https://themiddleeastinsider.com/2026/05/28/best-fintech-apps-egypt-2026-instapay-fawry-vodafone-cash/)) `[THIRD-PARTY ESTIMATE]`
- Settlement: cards T+1, cash/reference T+2 `[THIRD-PARTY ESTIMATE]`
- **Setup cost, minimum volume and timeline: NOT SOURCED — nothing first-party exists publicly.**

**Two distinct products, and the difference matters:**
- **Reference codes / cash acceptance** — you issue a Fawry reference number, the clinic owner walks into any of ~250,000 retail points and pays cash. This is the only channel that reaches a clinic owner who will not touch a card.
- **Fawry Pay gateway** — online card + wallet checkout.

**Cash collection is a second approval on top of merchant onboarding:** "to receive payments using Fawry Pay Cash pick-up, you need to send an email requesting approval or contact your account manager" ([Flutterwave FawryPay FAQ](https://flutterwave.com/gh/support/payments/fawry-pay-faq-egypt)).

**Verdict:** higher friction, higher reach. No self-serve signup, no published price, a sales call and two approvals. Not a day-one channel for a two-person business.

### 3.3 InstaPay, bank transfer, wallets — the low-friction reality

**InstaPay (first-party):** fee **0.1%, minimum EGP 0.50, maximum EGP 20**. Limits **EGP 70,000 per transaction / 120,000 daily per bank / 400,000 monthly per bank** ([instapay.eg](https://www.instapay.eg/en); limits set by [CBE decision effective 15 March 2023](https://www.cbe.org.eg/en/news-publications/news/2023/03/09/17/45/cbe-raises-the-maximum-limit-of-transactions-through-the-instant-payment-network-instapay)).

**InstaPay is no longer free** — fees began **1 April 2025** after three years free from the April 2022 launch ([Egypt Independent, 26 Mar 2025](https://egyptindependent.com/instapay-updates-fees-and-tariffs-for-money-transfers/)).

**The 20 EGP cap is the single most important number in this section.** Collecting a 30,000 EGP annual licence costs **20 EGP on InstaPay** versus **828 EGP on Paymob** (2.75% × 30,000 + 3). That is a **41× difference** on exactly the transaction size this business runs on.

InstaPay is documented for **individual account holders** — no business account or merchant product. Its "collect request" feature (request money by mobile number or IPA) is P2P by design but is what small Egyptian operators actually use for invoice collection. **NOT SOURCED: any CBE rule permitting or forbidding business income arriving in a personal InstaPay/bank account.** That is a tax-registration and ETA e-invoicing question — ask an accountant, do not read my silence as permission.

**Plain bank transfer:** no platform fee beyond your bank's tariff, no caps beyond bank policy. Slowest, zero infrastructure, and the realistic default for the first paying clinic.

**Vodafone Cash** `[THIRD-PARTY — Vodafone's own pages were unreachable]`: **EGP 1 flat** to another Vodafone Cash wallet; **0.5% (min 1, max 15 EGP)** to other wallets or banks; limits **60,000/day, 200,000/month**, max balance 100,000; opening needs only a national ID and a registered line, no fee ([momocalc.com](https://momocalc.com/egypt/en/vodafone-cash-fees)). **Merchant wallet acceptance is normally obtained through a PSP (Paymob/Fawry), not the telco directly** — Paymob's flat rate already covers wallet acceptance. **NOT SOURCED: whether a personal wallet may legally receive business income.**

### 3.4 Recurring billing — the honest answer

Paymob markets a **Subscriptions** product with customer tokenisation and card-on-file ([paymob.com/en/subscriptions](https://paymob.com/en/subscriptions)), and the API surface is real — a Card Tokens API supporting both customer-initiated and merchant-initiated transactions for recurring, on-demand and one-click payments ([api-evangelist/paymob README](https://github.com/api-evangelist/paymob/blob/main/README.md)).

**But it is not a self-serve checkbox.** Paymob documentation indicates you must "ask your technical contact for recurring payment setup and receive an **extra integration ID**" — the recurring flow uses a different integration ID from your normal one. `[WEAKLY SOURCED — the underlying doc page 404s after Paymob's migration to a Theneo-hosted site. Strongly indicated, unverified.]`

**Fawry recurring: NOT SOURCED, no information either way.**

> **Practical conclusion: build manual renewal, not a billing engine.** Card-on-file requires a human at Paymob to enable a second integration ID, which for a two-person merchant with no volume means a sales conversation and a wait — and it only helps clinics that pay by card at all, which in this segment is the minority. The realistic v1 is: **invoice → InstaPay/bank transfer → you flip the licence expiry date.** Licence expiry is a `WHERE expires_at > now()`, not a subscription platform. Revisit recurring cards only when a customer asks for it.

### 3.5 Receiving from outside Egypt (Gulf clinics, later)

| Platform | Egyptian seller? | Detail |
|---|---|---|
| **Stripe** | **No** | Egypt is not a supported merchant country and Stripe Atlas is unavailable. Workaround is a US LLC + EIN, then Stripe against the US entity — roughly **$280–500** one-off plus ongoing US compliance `[THIRD-PARTY: [payoutmap](https://payoutmap.com/country/egypt), [persuasion-nation](https://persuasion-nation.com/is-stripe-available-in-egypt/) — stripe.com was unreachable]` |
| **Paddle** | **Yes, apparently** | "Paddle works with software businesses anywhere in the world with the exception of the unsupported countries listed below" — the list is ~29 sanctioned jurisdictions and **Egypt is not on it** ([paddle.com](https://www.paddle.com/help/start/intro-to-paddle/which-countries-are-supported-by-paddle)). **Payout methods and minimums for Egypt: NOT SOURCED.** |
| **Lemon Squeezy** | **Yes** | Egypt explicitly listed among supported **bank payout** countries ([docs.lemonsqueezy.com](https://docs.lemonsqueezy.com/help/getting-started/supported-countries)) |
| **Payoneer** | **Yes — the standard Egyptian answer** | Receive from clients/marketplaces, withdraw to a local Egyptian bank in EGP, typically 1–3 business days ([payoutmap](https://payoutmap.com/guide/egypt)) |
| **Wise** | **Send-only — effectively unusable for receiving** | Egyptian residents can open accounts and send, but Wise **does not provide Egyptian residents with local USD account details to receive payments** ([payoutmap](https://payoutmap.com/country/egypt)) |

**Payoneer fees (first-party, [payoneer.com/about/fees](https://www.payoneer.com/about/fees/)):** receiving by credit card **up to 3.99% + $0.49**; by ACH/EU/UK bank **1%**; currency conversion **0.50%**; withdrawal to local bank in local currency **$1.50**; **annual account fee $29.95, charged only if the account receives under $6,000 in any 12 consecutive months.**

Note the stacking: a Gulf clinic paying by card into Payoneer, then converting USD→EGP and withdrawing, pays 3.99% + $0.49 + conversion spread + $1.50. A direct SWIFT wire to CIB/NBE costs **$15–30 incoming** `[THIRD-PARTY]` — cheaper than Payoneer only on large amounts.

**CBE foreign-currency rules — MY SOURCES CONTRADICT EACH OTHER. Do not act on this without your bank or an accountant.** One source states mandatory conversion to EGP within a CBE-mandated period ([payoutmap country page](https://payoutmap.com/country/egypt)); a different page on the *same site* states the framework allows holding foreign currency without mandatory conversion ([payoutmap guide](https://payoutmap.com/guide/egypt)); a third agrees conversion is not strictly mandatory ([grey.co](https://grey.co/blog/what-egypts-currency-controls-mean-for-international-payments)). Consistent across all sources: FX flows go through CBE-licensed banks; banks require invoice documentation; amounts above **USD 10,000** need supporting documentation; and you must register with the Egyptian Tax Authority and file annually by **31 March**. Since November 2023 the CBE has permitted foreign-currency accounts for individuals and low-risk MSMEs ([egypt-business.com](https://www.egypt-business.com/)).

### 3.6 Cost of each option, and what is free to start

| Option | Setup cost | Monthly | Per transaction | Free to start? |
|---|---|---|---|---|
| **Bank transfer** | 0 | 0 | Bank tariff only | ✅ |
| **InstaPay** | 0 | 0 | **0.1%, max 20 EGP** | ✅ **Cheapest by far at this ticket size** |
| **Vodafone Cash** | 0 | 0 | 1 EGP same-network / 0.5% max 15 EGP cross | ✅ (legality for business income unverified) |
| **Paymob** | **0** | **0** | 2.75% + 3 EGP | ✅ **if you already hold CR + tax card** |
| **Fawry** | Unknown | Unknown | ~1.5–2.5% est. | ❌ Sales call + two approvals |
| **Lemon Squeezy / Paddle** | 0 | 0 | Merchant-of-record cut `[NOT SOURCED]` | ✅ |
| **Payoneer** | 0 | **$29.95/yr if you receive under $6,000/yr** | 1%–3.99% + $0.49 | ⚠️ The annual fee bites a pre-revenue seller |
| **Stripe via US LLC** | **$280–500** | US compliance | 2.9% + $0.30 | ❌ |

**The real gate is not the PSP — it is entity registration.** A **منشأة فردية** is cheap: name reservation **EGP 107**, commercial registry entry **~EGP 12.50**, certificate **EGP 100**, annual subscription 0.002% of declared capital (**min EGP 24, max EGP 2,000**), no fixed minimum capital, registrable in as little as one business day ([Deel](https://www.deel.com/blog/sole-proprietorship-egypt/), corroborating fee figures also reported by [Jobbers](https://www.jobbers.io/egypt-freelancers-cairo-tech-hub-complete-registration-guide-2026/)). **VAT registration becomes mandatory above EGP 500,000 turnover.** Freelancers earning above **EGP 60,000/year** must register with the Egyptian Tax Authority.

> **T3 recommendation:** Register a **منشأة فردية** (~EGP 250 in fees, about one day). Collect via **InstaPay or bank transfer against a manual invoice** — zero setup, zero monthly, **20 EGP maximum per collection**. Add **Paymob** later; it costs nothing to sit idle and only matters when a customer asks to pay by card. Add **Fawry cash codes** only when a clinic actually refuses everything else. **Skip recurring card billing entirely.** Defer the Gulf/Paddle question until a Gulf clinic has actually asked to pay you.

---

## T4 — Cost to run the business

### 4.1 The WhatsApp finding — read this first

**The product currently ships with Wapilot (`api.wapilot.net`), and that is both a margin problem and a product risk.**

- **Wapilot costs 800 EGP/month, unlimited messages** ([wapilot.net/pricing](https://wapilot.net/pricing)).
- Wapilot's own site describes itself as **"an alternative to the official WhatsApp Business API"** and is **not a Meta partner**. That means unofficial WhatsApp Web automation: no SLA, numbers get banned, and it violates WhatsApp's Terms of Service.

At the recommended add-on price of **600 EGP/month**, if Wapilot's 800 EGP is charged **per clinic**, the WhatsApp feature is sold at a **200 EGP/month loss per clinic** before any support cost. **This is the "priced wrong and it destroys the margin" scenario the brief asked about, and it is live in the product today.**

🔍 **Open question the founder must resolve before pricing this:** Wapilot's page says you can "run more than one WhatsApp number together from the same account." If N clinic numbers genuinely run on one 800 EGP account, the cost collapses to 800/N and the add-on becomes highly profitable. **Ask Wapilot directly. The answer swings this line item by an order of magnitude.** Until answered, model it as 800 EGP per clinic.

**The official path costs less and is not a ToS violation.** Meta moved to **per-message pricing effective 1 July 2025** ([Meta docs](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)). Critically for this product:

- **"Utility templates delivered within an open customer service window are free."** — direct from Meta's docs. An appointment reminder is a utility template.
- **All service (user-initiated) messages are free** since 1 Nov 2024. There is **no monthly free-conversation allowance any more** — several BSP blogs still cite "first 1,000 conversations free"; that is stale, do not model it.
- **Free entry point:** a user arriving via Click-to-WhatsApp ad or Page CTA opens a **72-hour window in which all message types are free**.

**Egypt per-message rates** `[THIRD-PARTY — Meta's Egypt rate card is behind a JS-rendered selector; four BSP tables disagree]`:

| Category | Rate to use | EGP @50.72 | Notes |
|---|---|---|---|
| **Utility (appointment reminder), inside open 24h window** | **$0.00** | **0.00** | Meta docs, confirmed |
| **Utility, cold** | **$0.0036** | **0.183** | Two independent sources agree ([whautomate](https://whautomate.com/whatsapp-business-api-pricing), [flowcall](https://www.flowcall.co/blog/whatsapp-business-api-pricing)) |
| Marketing | $0.0644 | 3.27 | Use this, not the legacy $0.1073 — Meta **lowered Egypt's marketing rate on 1 Jan 2026** ([uptail.ai](https://www.uptail.ai/blog/whatsapp-business-api-pricing-2026-what-it-costs-and-how-billing-works)) |
| Authentication, **Egypt-registered WABA** | $0.0036 | 0.183 | |
| Authentication, **foreign-registered WABA** | $0.0650 | 3.30 | ⚠️ Egypt is an *authentication-international* market ([blueticks](https://blueticks.co/blog/whatsapp-business-api-pricing-2026)) |

⚠️ **Register the WABA in Egypt.** A foreign-registered WABA turns $0.0036 OTPs into $0.0650 — an **18× penalty** on every OTP.

**BSP platform fees are the actual cost driver, not Meta:**

| Provider | Platform fee | Per-message markup |
|---|---|---|
| **Twilio** | **None** | **$0.005** in + out, on top of Meta ([twilio.com](https://www.twilio.com/en-us/whatsapp/pricing)) |
| **360dialog** | **€49/mo per number** (Regular) | **No markup on Meta fees** — explicit ([360dialog.com/pricing](https://360dialog.com/pricing)) |
| **Interakt** | **Starter free**; Growth $55/mo | Meta extra ([interakt.shop/pricing](https://www.interakt.shop/pricing/)) |
| **Wati** | $29/mo Growth | Meta pass-through ([wati.io/pricing](https://www.wati.io/pricing/)) |
| **Wapilot** (Egyptian, Giza) | **800 EGP/mo flat, unlimited** | N/A — **unofficial, ban risk** |

Note that **Twilio's $0.005 fee is larger than Meta's $0.0036 utility rate** — for Egyptian utility traffic the BSP fee dominates. All-in on Twilio: **$0.0086 ≈ 0.44 EGP per cold reminder, 0.25 EGP if inside an open window.**

**No official Meta-partner Egyptian BSP with published pricing was found.** (wachat.com is a parked domain, wachat.io 403s, Gupshup's pricing page 404s.)

### 4.2 AI / OpenRouter cost

The product defaults to **`gemini-2.5-flash`** across all three AI surfaces (`ai_assistant`, `petsy` chatbot, `imaging`), with `max_tokens` of 1024, 800 and 1200 respectively.

OpenRouter charges **5.5% on card credit top-ups ($0.80 minimum), 5% on crypto**, with **no markup on tokens** ([openrouter.ai/docs/faq](https://openrouter.ai/docs/faq)).

| Model | Input /1M | Output /1M | Source |
|---|---|---|---|
| **gemini-2.5-flash-lite** | **$0.10** | **$0.40** | [openrouter.ai](https://openrouter.ai/google/gemini-2.5-flash-lite) |
| gemini-2.5-flash (current default) | $0.30 | $2.50 | [openrouter.ai](https://openrouter.ai/google/gemini-2.5-flash) |
| deepseek-chat-v3.1 | $0.25 | $0.95 | [openrouter.ai](https://openrouter.ai/deepseek/deepseek-chat-v3.1) |
| gpt-5-mini | $0.25 | $2.00 | [openrouter.ai](https://openrouter.ai/openai/gpt-5-mini) |

**Cost per clinic per month** (2,000 turns × 1,500 in / 300 out = 3.0M in + 0.6M out, incl. 5.5% top-up fee):

| Model | Monthly | EGP |
|---|---|---|
| **gemini-2.5-flash-lite** | $0.57 | **~29 EGP** |
| deepseek-chat-v3.1 | $1.39 | ~71 EGP |
| **gemini-2.5-flash (current default)** | $2.53 | **~128 EGP** |

**Heavy-usage scenario** (a busy hospital: assistant + chatbot + 3 imaging calls/day at 1,200 output tokens): roughly **~170 EGP/clinic/month on flash**, and a genuinely unmetered assistant can exceed **300 EGP/clinic/month** `[MY ARITHMETIC on the sourced token prices]`.

**Two decisions follow:** (1) **switch the default to `gemini-2.5-flash-lite`** and escalate to `flash` only for imaging — a 4.4× cost reduction for chat; (2) **meter the AI assistant per tier** (already reflected in the T2 table) so a single heavy user cannot eat the tier's margin.

**Do not use OpenRouter `:free` models in production.** Limits are **50 requests/day** without credits, **1,000/day** with $10+ ([openrouter.ai/docs/faq](https://openrouter.ai/docs/faq)), and OpenRouter itself calls them unsuitable for production. `[NOT SOURCED, but flag it: free variants generally require opting into prompt logging — verify before putting any patient record through one.]`

**Planning number used below: 60 EGP/clinic/month** (flash-lite for chat, flash for imaging, metered).

### 4.3 Hosting — free tiers will fail, and here is the sourced reason

**Neon free tier** ([neon.com/pricing](https://neon.com/pricing)): **0.5 GB storage/project**, **100 CU-hours/project/month**, **scale-to-zero after 5 minutes idle**, 5 GB egress. Hitting any limit **suspends compute until the next billing month**.

**100 CU-hours ≈ 4.2 days of a single always-on CU.** A multi-user always-on clinic app does not fit — not "might struggle", *does not fit*. And scale-to-zero is a customer-facing defect in this specific product: a vet clinic goes 20 minutes idle, then the receptionist opens a record with a client at the counter and eats a cold start. "It's the free database" is not a sentence you can say to a paying customer. 0.5 GB is also a hard wall the moment imaging attachments land in Postgres (put them in object storage regardless).

**The Neon paid trap:** always-on Launch at 0.25 CU = 730h × 0.25 × $0.106 = **$19.35/month ≈ 981 EGP per clinic database**, plus $0.35/GB storage. **Per-clinic Neon destroys the hosted tier**, which is priced at 600 EGP/month.

**Koyeb** ([koyeb.com/pricing](https://www.koyeb.com/pricing)): cheapest paid plan **Pro $29/mo** (includes $10 compute); managed Postgres Small **$0.04/hr = $29.76/mo**. ⚠️ **The pricing page states no free-tier limits for serverless compute** — no instance hours, no idle behaviour. `[NOT VERIFIED — docs.koyeb.com does not resolve. I cannot confirm the Koyeb compute free tier still exists in 2026. Its absence from the pricing page alongside a $29/mo entry plan suggests it may have been curtailed. Check by signing up.]`

**The answer is one VPS.**

| Option | Spec | Price | Source |
|---|---|---|---|
| **Contabo Cloud VPS 4** | 4 vCPU, 8 GB RAM, 100 GB SSD, unlimited traffic | **€5.50/mo** (24-mo term) | [contabo.com/en/vps](https://contabo.com/en/vps/) |
| Hetzner Cloud (CX line) | — | **NOT SOURCED** — the pricing table is JS-rendered; hetzner.com/cloud returned categories with no prices. Check [console.hetzner.com](https://console.hetzner.com). Locations: Falkenstein, Nuremberg, Helsinki, Hillsboro, Ashburn | [hetzner.com/cloud](https://www.hetzner.com/cloud/) |

€5.50 ≈ **~310 EGP/month** `[EUR→EGP conversion is UNSOURCED — I only sourced USD/EGP. Verify.]`

One 8 GB box running the Flask app + Postgres + nightly `pg_dump` to object storage should carry **15–25 clinic instances** with schema separation `[UNSOURCED — engineering estimate; measure it]`. Per-clinic hosting cost then falls to **~16 EGP/month**, versus 981 EGP on per-clinic Neon. Pick the EU region — roughly 60–90 ms to Cairo `[UNSOURCED estimate]`, irrelevant for a CRUD app.

**Use the free tiers for staging only.**

### 4.4 Domain, email, SSL

| Item | Price | Source |
|---|---|---|
| **.com domain** | **$11.08/year** (Porkbun; registration = renewal, free WHOIS privacy, free Let's Encrypt SSL) ≈ **562 EGP/yr ≈ 47 EGP/mo** | [porkbun.com](https://porkbun.com/products/domains) |
| Alternative | Cloudflare Registrar sells **at cost, no markup** — but publishes no figure | [cloudflare.com/registrar](https://www.cloudflare.com/products/registrar/) |
| **Business email** | **Zoho Mail Forever Free — 5 users, 5 GB/user, 1 custom domain, web + mobile only (no IMAP/POP)** = **0 EGP** | [zoho.com/mail pricing](https://www.zoho.com/mail/zohomail-pricing.html) |
| Zoho paid (when you need IMAP) | ~$2/user/month annual | same |
| Google Workspace Starter | $7.00/user/month (USD pricing; Egypt EGP pricing **NOT SOURCED**) | [workspace.google.com/pricing](https://workspace.google.com/pricing.html) |
| **SSL** | **0** — Let's Encrypt / Cloudflare | — |

### 4.5 Support time and admin

- **Support: 1.5–2 hours per clinic per month in year 1**, falling to ~0.5 h once the product stabilises `[UNSOURCED — planning assumption; measure it from ticket one]`. This is the largest single variable cost after WhatsApp and the one people forget to price.
- **Founder time valued at 150 EGP/hour** `[UNSOURCED — planning assumption]`. Used only to make the support line visible in the table; it is opportunity cost, not cash out.
- **Accounting:** a small Egyptian accountant retainer, estimated **1,000–2,000 EGP/month** `[NOT SOURCED]`. Use 1,500.
- **Entity:** منشأة فردية one-off ~250 EGP + annual subscription up to 2,000 EGP ≈ **170 EGP/month** amortised (sourced in T3.6).

### 4.6 Unit-economics table

**Clinic tier, blended over a 3-year customer life.** Assumptions: 30,000 EGP licence and 6,000 EGP setup amortised over 36 months; support renewal 7,500 EGP/yr at a **50% renewal rate**; WhatsApp add-on at 600 EGP/mo with a **70% attach rate**; 500 reminder messages/clinic/month.

| | **Self-hosted clinic** | **Hosted clinic** |
|---|---:|---:|
| **REVENUE (EGP/clinic/month)** | | |
| Licence amortised (30,000 ÷ 36) | 833 | 833 |
| Setup amortised (6,000 ÷ 36) | 167 | 167 |
| Support renewal, expected (7,500 × 50% ÷ 12) | 313 | 313 |
| WhatsApp add-on (600 × 70% attach) | 420 | 420 |
| Hosted cloud add-on | — | 600 |
| **Total revenue** | **1,733** | **2,333** |
| **VARIABLE COST (EGP/clinic/month)** | | |
| WhatsApp — Twilio + Meta, 500 msgs × 70% attach (500 × 0.44 × 0.7) | −154 | −154 |
| AI (flash-lite chat + flash imaging, metered) | −60 | −60 |
| Hosting share (VPS 310 ÷ 20 clinics) | 0 | −16 |
| Payment collection (InstaPay, 20 EGP/yr ÷ 12) | −2 | −2 |
| Support time (1.5 h × 150 EGP) | −225 | −225 |
| **Total variable cost** | **−441** | **−457** |
| **GROSS MARGIN** | **1,292 EGP** | **1,876 EGP** |
| **Gross margin %** | **75%** | **80%** |

**The same table if WhatsApp stays on Wapilot at 800 EGP per clinic:**

| | Self-hosted | Hosted |
|---|---:|---:|
| WhatsApp cost (800 × 70% attach) | −560 | −560 |
| Total variable cost | −847 | −863 |
| **Gross margin** | **886 EGP (51%)** | **1,470 EGP (63%)** |

**The WhatsApp add-on itself, in isolation:** revenue 420 vs Wapilot cost 560 = **a 140 EGP/month loss per clinic**. On the official Twilio path: revenue 420 vs cost 154 = **266 EGP/month profit**. **Migrating off Wapilot to an official BSP is worth roughly 406 EGP per clinic per month and removes the ban risk.** That is the highest-value engineering change identified in this document.

**Be honest about what the margin is not.** The 75–80% figures above only hold **while you keep signing new clinics**, because 1,000 of the 1,733 EGP is amortised one-off revenue. The **true recurring** margin once a clinic has paid its licence is:

| | Self-hosted | Hosted |
|---|---:|---:|
| Recurring revenue (support renewal + WhatsApp) | 733 | 1,333 |
| Recurring variable cost | −441 | −457 |
| **True recurring margin** | **292 EGP/clinic/mo** | **876 EGP/clinic/mo** |

**A self-hosted clinic that has paid its perpetual licence and lets support lapse generates almost nothing.** To reach a 30,000 EGP/month draw on self-hosted recurring alone you would need **103 clinics**. That is not reachable for a one-person business. **The hosted tier is not an upsell — it is the only route to a business that survives without constant new sales.**

### 4.7 Fixed monthly running cost, year 1

| Item | EGP/month | Sourced? |
|---|---:|---|
| Contabo VPS 4 (production) | 310 | ✅ €5.50 (EUR→EGP unsourced) |
| Second VPS (staging/backup) — optional in month 1 | 310 | ✅ |
| Domain (.com amortised) | 47 | ✅ $11.08/yr |
| Email (Zoho free), SSL (Let's Encrypt) | 0 | ✅ |
| Object storage for backups (Cloudflare R2 / B2 free tier at this size) | 0 | `[UNSOURCED]` |
| Entity annual subscription amortised | 170 | ✅ |
| Accountant | 1,500 | `[NOT SOURCED — estimate]` |
| Contingency / tools | 500 | `[estimate]` |
| **Total fixed** | **~2,837 EGP/month (~USD 56)** | |

**Drop the staging VPS in month 1 and it is ~2,527 EGP/month.** This business has almost no fixed cost. That is its single greatest structural advantage and the reason it is survivable on no capital.

---

## T5 — Break-even

**Assumptions, stated:** self-hosted/hosted mix of 60/40 in year 1 → blended gross margin **(1,292 × 0.6) + (1,876 × 0.4) = 1,526 EGP per clinic per month**. Fixed cost **2,837 EGP/month**. WhatsApp on the **official BSP path** (if Wapilot is retained, use the 51%/63% figures and every clinic count below rises by roughly 40%).

### 5.1 Break-even on fixed costs

```
2,837 ÷ 1,526  =  1.86  →  2 clinics
```

**Two paying clinics and the business stops losing money.** With Wapilot retained: 2,837 ÷ 1,092 = 2.6 → **3 clinics**.

This is genuinely low, and it is the honest good news in this document. The risk in this business is not fixed cost — it is that the founder cannot eat.

### 5.2 Break-even on a founder salary

**I could not source a mid-level Egyptian developer salary.** Glassdoor Egypt returned HTTP 403, SalaryExplorer 523, Wuzzuf 404, and the session's search budget was exhausted. **Every salary figure below is an assumption, not a citation** — verify against Wuzzuf's salary section or a MENA developer salary survey before relying on it.

Clinics needed = (2,837 + monthly draw) ÷ 1,526

| Monthly draw (EGP) `[ASSUMED]` | Roughly | Clinics needed |
|---|---|---:|
| 20,000 | Modest professional | **15** |
| 30,000 | Comfortable mid-level developer | **22** |
| 45,000 | Senior developer | **31** |
| 50,000 (two founders at 25,000 each) | Dev + vet partner both full-time | **35** |

With **Wapilot retained** (blended margin 1,092), the 30,000 EGP line moves from 22 clinics to **30 clinics**. That single integration choice costs eight clinics of sales effort.

### 5.3 The ceiling nobody mentions

At **1.5 support hours per clinic per month**, 31 clinics is **46 hours/month of support** — more than a full working week, before any selling or any development. A one-person business realistically **tops out around 30–40 clinics** before support consumes the capacity that built the product. Beyond that you are hiring, and the model changes.

**The practical target is therefore ~22–25 clinics**, which pays a comfortable mid-level developer salary and leaves capacity to keep building.

**Sanity-check against the market.** `02_MARKET_SIZE.md` puts the directory-listed addressable base at roughly **1,463 clinics**, with ~80% inside Greater Cairo and Alexandria. **22 clinics is about 1.5% of that base** — and they are all reachable in person from one city. The break-even is not the hard part of this business. Sales cycle length and support capacity are.

### 5.4 The uncomfortable timeline

T2's realistic year-1 case is **6 clinics and ~111,000 EGP of revenue — about 9,250 EGP/month.** That is **below every salary line in the table above.**

```
Year 1:  6 clinics cumulative   →  draw ≈ 6,300 EGP/mo after fixed costs
Year 2: +12 → 18 cumulative     →  draw ≈ 24,600 EGP/mo
Year 3: +15 → 33 cumulative     →  draw ≈ 47,500 EGP/mo
```

**Year 1 does not pay a salary. Plan for 12 months of runway or a day job.** The business becomes self-supporting somewhere in **month 15–20** and reaches a comfortable developer salary around **month 24–30**. Anyone modelling this as a year-1 income replacement is modelling it wrong.

---

## Final recommendation

**Model — phased:**

1. **Year 1: lead with the perpetual, per-branch licence + one-off setup fee.** It matches how Egyptian SMEs already buy pharmacy and POS software, it removes the ownership objection, and it pays **2.24× what monthly SaaS pays in year 1** — which for a founder with no capital is the difference between existing in month 9 and not.
2. **From ~10 reference customers: shift the default offer to the hosted annual subscription.** T4.6 is unambiguous — a self-hosted clinic that has paid its licence throws off **292 EGP/month**, a hosted one throws off **876 EGP/month**. Hosted is the only path to a business that survives without constant new sales.
3. Keep both on the price list permanently, priced so the two paths **cross at exactly year 3**. That removes cannibalisation without a sales argument.
4. **Never per-user. Never a percentage of anything. Never a permanent free tier. Do not open-source the core.** Ship **source-available** and sell on the honesty.
5. **On piracy: do not build DRM.** Ship a signed licence file that warns and never blocks. Keep WhatsApp, AI, backups and ETA e-invoice submission running through your credentials so a pirated build boots but does nothing useful. Budget 10–20% leakage and move on.

**Price points (per branch, EGP):**

| | Solo | Clinic | Hospital | Chain |
|---|---:|---:|---:|---:|
| Perpetual licence (incl. year 1 support) | **12,000** | **30,000** | **60,000** | 60,000 + 20,000/branch |
| Annual support & updates, year 2+ | 3,000 | 7,500 | 15,000 | 15,000 + 5,000/branch |
| Annual subscription alternative | 6,000 | 15,000 | 30,000 | 30,000 + 10,000/branch |
| Setup / data migration (one-off) | 3,000 | 6,000 | 12,000 | 12,000 + 4,000/branch |
| WhatsApp add-on (per month) | 400 | 600 | 900 | 900 + 300/branch |
| Hosted cloud add-on (per month) | 350 | 600 | 1,200 | 1,200 + 400/branch |

First five customers at **40–50% off** in exchange for a named testimonial and a site visit.

**Break-even: 2 clinics to cover costs. 22 clinics to pay a 30,000 EGP/month developer salary. Practical ceiling ~30–40 clinics for a one-person operation.**

**Three things to do before selling anything:**

1. **Get off Wapilot.** It is unofficial, it violates WhatsApp's ToS, clinic numbers get banned, and at 800 EGP per clinic it makes the WhatsApp add-on loss-making. Move to Twilio (no monthly fee, $0.005/msg) with an **Egypt-registered WABA**. Worth ~406 EGP per clinic per month. *(First: ask Wapilot whether multiple clinic numbers share one 800 EGP account — the answer swings this by an order of magnitude.)*
2. **Switch the AI default from `gemini-2.5-flash` to `gemini-2.5-flash-lite`** for the assistant and chatbot, keeping `flash` for imaging. 4.4× cheaper on chat, and meter it per tier.
3. **Register a منشأة فردية (~250 EGP, one day) and collect on InstaPay.** 20 EGP maximum per collection versus 828 EGP on Paymob for a 30,000 EGP licence. Add Paymob later; it costs nothing idle.

**Numbers to verify before committing to a public price list:** Meta's official Egypt rate card (four third-party tables disagree on marketing); whether Koyeb's compute free tier still exists; Hetzner's actual CX pricing; the EUR→EGP rate; a real Egyptian developer salary figure; a small-business accountant's monthly retainer; and whether a personal InstaPay/wallet may legally receive business income — that last one needs an accountant, not a search engine.

