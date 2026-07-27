# 07 — Sub-Saharan Africa Market Assessment

**Product:** Aleefy — veterinary clinic ERP, 28 modules, self-hosted or cloud, **English + Arabic only**
**Team:** two people, Cairo, no capital, no local presence anywhere
**Benchmark to beat:** Egypt-only year-3 ARR ≈ USD 25k
**Date of research:** July 2026

---

## 0. Verdict up front

**No.** Sub-Saharan Africa is not addressable for this team as currently constituted.

The single best country is **South Africa**, and even South Africa is not clearly better than Egypt on a risk-adjusted basis. Everything else in the region is either too small (East Africa companion-animal segment), structurally closed to a foreign vendor (Nigeria), or both.

The full reasoning is in section 11. Sections 1–10 are the evidence.

---

## 1. The constraint that governs everything

Arabic is spoken as a first language by effectively **zero** of the veterinary market in the fourteen countries in scope. Sudan and Somalia are Arabic-speaking and in Sub-Saharan Africa, but neither is on the list and neither is a viable software market.

So the product enters this region stripped of its differentiator. It is an English-language vet PMS from an unknown Egyptian vendor, competing against:

- Established local incumbents (South Africa)
- Global cloud products already selling here (ezyVet, Provet Cloud, VETport, Vetstoria)
- Free-or-cheap generic tools and paper (Kenya, Nigeria, and everywhere below the top tier)

The three assets that make Egypt work — Arabic UI, same-city support, and a regulatory wedge the team understands — are all absent. What remains is features and price, sold cold, across a border, by two people.

---

## 2. Livestock vs companion animal — the definitional trap

This is the single easiest way to manufacture a fake market in this region, so it is stated first.

Sub-Saharan African veterinary practice is dominated by **production animals**: cattle, poultry, small ruminants, and state disease-control work. A herd-health vet driving between farms in Nakuru or Limpopo has no use for a grooming module, a boarding module, a pet-shop POS, or a pet-owner telemedicine portal. That is roughly a third of Aleefy's 28 modules dead on arrival.

Concretely, from the South African facility register (section 4), the categories that are unambiguously **not** companion-animal practice — herd health, production animal, state control and regulatory, consultants in industry, research, laboratories — account for roughly **420 of 1,529 registered facilities (~27%)**. In Kenya and Nigeria the livestock share of the profession is far higher; Kenya's veterinary profession is structurally a livestock and public-health profession with a small urban companion-animal layer on top.

Every number below is kept on the companion-animal side of that line, or explicitly flagged when it is not.

---

## 3. Priority country — KENYA

### 3.1 Veterinary practitioner count (hard number)

The Kenya Veterinary Board publishes its statutory registers as downloadable spreadsheets.

| Register (2026) | Count |
|---|---|
| **Veterinary Surgeons** | **1,342** |
| Veterinary Technologists (Degree) | published, not counted here |
| Veterinary Technologists (Diploma) | published, not counted here |
| Veterinary Technicians (Certificate) | published, not counted here |

Source: [Kenya Veterinary Board — Registers](https://www.kenyavetboard.or.ke/en/registers); file `VET SURGEONS 2026 REGISTER_4.xlsx`, parsed directly — 1,342 numbered entries, highest KVB number 3484, register year 2026.

Cross-check: the Kenya Veterinary Association is cited as putting the working population at "fewer than 2,000 veterinarians in Kenya" ([Dogster / KVA](https://www.dogster.com/statistics/pet-industry-statistics-kenya)). The 1,342 figure is the *retention-compliant* register, i.e. those who paid their annual fee — consistent with KVB's own note that compliance rose from 38.8% at end-2024 to 52.5% by March 2025 ([Kenya Veterinary Board](https://kenyavetboard.or.ke/en/registration/retention)).

### 3.2 Companion-animal practices — the number that matters

**KVB does not publish a register of veterinary premises or practices.** The registers page carries only practitioner registers, no facility list ([KVB Registers](https://www.kenyavetboard.or.ke/en/registers)).

So the clinic count must be reasoned, not cited:

- 1,342 registered vets, of whom the large majority are in state veterinary services, livestock/poultry production, agribusiness, research, and public health.
- Companion-animal practice is concentrated almost entirely in Nairobi, with a thin presence in Mombasa, Nakuru, Kisumu and Eldoret.
- Nairobi's visible pet-services sector is small — the recurring names in local coverage are a handful of clinics and pet retailers (Petzone in Westlands, and similar) ([Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/)).

**Estimate: 60–150 companion-animal veterinary clinics in Kenya, of which perhaps 40–90 are commercially formalised enough to buy software.** `[UNVERIFIED — reasoned from the practitioner register and the absence of a premises register; no published facility count exists]`

### 3.3 Pet ownership and market size

| Metric | Value | Source |
|---|---|---|
| Households owning a pet (survey) | 54% owned animals; of owners 68% cats, 63% dogs | [TGM Research 2023 via Dogster](https://www.dogster.com/statistics/pet-industry-statistics-kenya) |
| Pet food market, 2029 | **USD 110.4m**, growing **9.16% p.a. (2025–29)** | [Statista Pet Food Kenya](https://www.statista.com/outlook/cmo/food/pet-food/kenya) |
| Africa + Middle East pet food, 2028 | USD 6.46bn | [Market Data Forecast via Dogster](https://www.dogster.com/statistics/pet-industry-statistics-kenya) |

Note carefully: the East African "65% of households own a dog" figures that circulate refer overwhelmingly to **free-roaming and guard dogs in rural and peri-urban settings**, not veterinary-clinic customers. A dog that has never seen a vet is not a market. The clinic-relevant population is the urban middle-class pet owner in Nairobi, which is a small fraction of that.

### 3.4 Ability to pay

| Item | Price | Source |
|---|---|---|
| Vet consultation, Nairobi | KES 1,000–3,000 (**USD 8–23**) | [Ducknet Vet Clinic](https://ducknetvetclinic.co.ke/how-much-vets-charge-in-nairobi/), [Dogster/DuckNetVet](https://www.dogster.com/statistics/pet-industry-statistics-kenya) |
| Dog vaccination course | KES 3,500 (~USD 30); boosters KES 1,000–3,000 | [Dogster/DuckNetVet](https://www.dogster.com/statistics/pet-industry-statistics-kenya) |
| Organic pet food, 5kg | KES 2,200–3,000 (USD 19–26) | [Dogster/Daily Business](https://www.dogster.com/statistics/pet-industry-statistics-kenya) |

A Nairobi clinic seeing 10–15 consults a day at USD 8–23 grosses on the order of USD 3,000–5,000/month. Realistic software budget: **USD 25–60/month**. `[UNVERIFIED — derived from consultation pricing; no published Kenyan vet-PMS price list found]`

**Kenya ARR ceiling, honest:** 40 clinics × USD 45/mo ≈ **USD 21k/year**. That is *below* the Egypt benchmark, for a market with no Arabic advantage, foreign-vendor tax registration obligations, and no local presence. Kenya does not clear the bar on arithmetic alone.

### 3.5 KRA eTIMS — assessed properly, because it is the supposed wedge

This is the strongest regulatory hook in the region, and it is real:

- **Scope is total.** "All persons engaged in business must onboard eTIMS, regardless of VAT registration status" — companies, partnerships, sole proprietorships, trusts, and even non-VAT sectors like hospitals and schools ([KRA — Learn about eTIMS](https://www.kra.go.ke/helping-tax-payers/faqs/learn-about-etims)).
- **It has teeth.** Expenses unsupported by a valid eTIMS invoice are **not deductible**, and the buyer cannot claim input VAT ([KRA FAQ](https://www.kra.go.ke/helping-tax-payers/faqs/learn-about-etims)). This is what forces adoption down the chain.
- **Integration is open to third parties.** "Taxpayers have an option to undertake self-integration or use a certified third party vendor... Persons intending to undertake self-integration or act as third party vendors are required to undergo a certification process prior to commencement of integration" ([KRA — eTIMS System to System Integration](https://www.kra.go.ke/business/etims-electronic-tax-invoice-management-system/learn-about-etims/etims-system-to-system-integration)).
- **Two integration modes.** OSCU (Online Sales Control Unit, hosted at KRA, for always-online systems) and VSCU (Virtual Sales Control Unit, hosted client-side, for bulk/offline invoicing) ([KRA](https://www.kra.go.ke/business/etims-electronic-tax-invoice-management-system/learn-about-etims/etims-system-to-system-integration)). Sandbox at `etims-sbx.kra.go.ke`, API at `etims-api-sbx.kra.go.ke` / `etims-api.kra.go.ke`.

**And here is why it is not the wedge it looks like.**

1. **Sign-up is PIN-bound.** The OSCU/VSCU sandbox sign-up requires "the PIN of the company" and OTP to a KRA-registered phone number, followed by a Service Request and a signed **eTIMS Commitment Form** ([KRA OSCU/VSCU Step-by-Step Guide, April 2023](https://www.kra.go.ke/images/publications/OSCU_VSCU_Step-by-Step_Guide-on-how-to-sign-up.pdf)). Every integration is scoped to an individual Kenyan taxpayer. A multi-tenant SaaS must hold and operate credentials on behalf of each clinic — workable, but it is per-customer onboarding paperwork forever, in a jurisdiction the team cannot visit.

2. **KRA gives the small taxpayer the tool for free.** The same guide lists **eTIMS Client** (free standalone Windows/Android app from KRA) and **eTIMS Online** (portal invoicing for service businesses issuing ≤10 invoices/month), plus **eTIMS Lite** via web, USSD `*222#`, and mobile app for small taxpayers ([KRA FAQ](https://www.kra.go.ke/helping-tax-payers/faqs/learn-about-etims); [OSCU/VSCU Guide](https://www.kra.go.ke/images/publications/OSCU_VSCU_Step-by-Step_Guide-on-how-to-sign-up.pdf)). Businesses under KES 5m turnover can also have the buyer invoice on their behalf.

   A small Nairobi vet clinic is squarely in the free-tool bracket. It will double-key invoices into a free KRA app before it pays a foreign vendor a monthly fee to avoid it. **The compliance pain that makes e-invoicing a wedge in Egypt has been deliberately removed at the bottom of the Kenyan market.**

3. **Credit notes are locked to the originating system**, which constrains multi-tenant design and correction workflows ([eTIMS API integration guide](https://invoicedataextraction.com/blog/kenya-etims-api-integration-guide)).

**Assessment: eTIMS is a genuine, mandatory, far-reaching regime and it is open to third-party integrators — but its free small-business tier neutralises it as a paid differentiator for exactly the customer segment Aleefy targets.**

### 3.6 Tax exposure of selling into Kenya from Egypt

This is a cost the team must price in before a single sale:

- **Significant Economic Presence (SEP) Tax** replaced the Digital Services Tax. It applies to non-residents earning from services delivered over the internet to users located in Kenya, explicitly including "software programmes, cloud computing, hosting" — direct-to-website sales count, not just marketplaces. Effective rate **≈3% of gross Kenyan revenue** (30% of a deemed 10% profit margin), filed **monthly** by the 20th ([Cliffe Dekker Hofmeyr](https://www.cliffedekkerhofmeyr.com/en/news/publications/2025/Practice/Tax-Exchange-Control/tax-and-exchange-control-alert-03-october-Kenya-issues-draft-Income-Tax-Significant-Economic-Presence-Tax-Regulations-2025); [KRA draft SEP regulations 2025](https://www.kra.go.ke/images/publications/Draft-Income-Tax-Signifficant-Economic-Presence-Tax-Regulations-2025.pdf)).
- **VAT on digital supplies at 16%**, non-resident registration required under the VAT (Amendment) Act 2023 ([ClearTax Kenya](https://www.cleartax.co.ke/kenya-vat-significant-economic-presence-sep-tax-digital-businesses.html)).

So: mandatory Kenyan tax registration, **monthly** filings, and ~19% of gross revenue in tax and VAT handling — for a market whose realistic ceiling is USD 21k ARR. Two people in Cairo cannot service that overhead.

### 3.7 Payments and reachability

- **M-Pesa** is the dominant rail but is a domestic consumer/merchant rail; a foreign vendor cannot collect into it without a Kenyan entity.
- **Flutterwave Kenya** requires a tenancy agreement showing the merchant's Kenyan address, shareholder structure, and a board resolution; USD payouts require a **USD account domiciled in a Kenyan bank** ([Flutterwave — Kenya onboarding](https://flutterwave.com/ng/support/onboarding/onboarding-requirements-for-using-flutterwave-in-kenya)).
- Practical route for a foreign vendor: international card via Stripe/Paddle/Lemon Squeezy. Card penetration among Kenyan SMEs is low; expect payment friction and involuntary churn.
- **Timezone: EAT (UTC+3) vs Cairo (UTC+2/+3). One hour or zero. Excellent.** Remote support is credible on hours.

---

## 4. Priority country — SOUTH AFRICA

### 4.1 Facility count (hard number, parsed from the statutory register)

The South African Veterinary Council publishes a complete register of active facilities. This is the best veterinary market data in the region by a wide margin. Both editions were downloaded and parsed directly.

Source: [SAVC — List of all practising professionals and registered facilities](https://savc.org.za/public-infomation/list-of-all-practising-professionals-and-registered-facilities/); files *Register of Active Facilities as on 01-Jul-2026* and [*Active-facilities-Apr-2024.pdf*](https://savc.org.za/wp-content/uploads/2024/04/Active-facilities-Apr-2024.pdf).

**Register of Active Facilities, 1 July 2026 — full breakdown**

| Facility type | Count | Companion-animal relevant? |
|---|---|---|
| Clinic | 287 | Yes |
| Small Animal Clinic | 234 | Yes |
| Animal Hospital | 105 | Yes |
| Small Animal Hospital | 88 | Yes |
| Mixed Practice | 84 | Partly |
| Consulting Rooms | 72 | Yes (mostly satellite) |
| Herd Health Practice [A] | 68 | **No — livestock** |
| Veterinary Laboratory | 65 | No |
| Consulting Room – Rule (various) | 60 + 30 + 6 = 96 | Yes (mostly satellite) |
| Hospital | 56 | Yes |
| Ccs and Regulatory (state vet offices) | 54 | **No — state** |
| Non-Practising Facilities | 53 | No |
| Herd Health Practice [B] | 50 | **No — livestock/wildlife** |
| Consultants in Industry | 43 | **No** |
| Animal Research | 39 | No |
| Veterinary Physiotherapy (4 sub-categories) | 38 | Adjacent |
| Primary Animal Health | 28 | Marginal |
| Non-Dispensing | 19 | No |
| Community | 17 | No |
| Veterinary Nursing | 10 | Adjacent |
| Equine Clinic / Equine Hospital | 12 | **No — equine** |
| Mobile Animal Services / Mobile Clinic | 5 | Yes |
| Veterinary Behavioural | 4 | Adjacent |
| Non-Invasive Consulting | 2 | No |
| **TOTAL ACTIVE FACILITIES** | **1,529** | |

**Companion-animal core (hospitals + clinics): 287 + 234 + 105 + 88 + 56 = 770 facilities.**
Adding mixed practice (84), consulting rooms and satellite consulting rooms (168), and mobile (5) gives an outer bound of **~1,030**, but consulting rooms are largely branch sites of practices already counted.

**Working number: 770 primary companion-animal practices; ~850–1,000 billable sites including branches.** This is a real, sourced, current figure.

**The base is not growing.** April 2024: **1,596** active facilities. July 2026: **1,529**. A net decline of ~4% over 27 months. `[Both figures parsed directly from the SAVC PDFs cited above.]`

### 4.2 Practitioner count

| Category | Count |
|---|---|
| Total registered with SAVC | 7,686 |
| **Veterinarians** | **4,315** |
| Animal health technicians | 2,013 |
| Veterinary nurses | 788 |
| Veterinary physiotherapists | 113 |
| Laboratory animal technologists | 23 |

Source: [Daily News / African News Agency, April 2025](https://dailynews.co.za/news/south-africa/2025-04-26-is-south-africas-veterinary-workforce-crisis-threatening-food-security-and-animal-health/). The same reporting cites the SAVC president on a ratio of **68 vets per million citizens** against an international norm of 200–400 — i.e. South Africa has a *shortage* of vets, which means practices are capacity-constrained and time-poor, not software-shopping.

### 4.3 Pet ownership and market size

| Metric | Value | Source |
|---|---|---|
| Households owning ≥1 pet | 55–60% | [Bonafide Research](https://www.bonafideresearch.com/product/6308186817/south-africa-veterinary-services-market) |
| Dogs | **7.4 million** | [Statista via Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |
| Cats | **2 million** across 1.3m households (6.4% of all households) | [Statistics South Africa via Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/africa-cat-food-market) |
| Pet food market 2025 | USD 596m (Statista) to USD 800m (DiMarket) | [Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |
| Pet food CAGR 2025–30 | 12.20% | [Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |
| Per-capita pet food spend | USD 9.21 | [Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |
| Veterinary services market CAGR to 2031 | 10.47% | [Bonafide Research](https://www.bonafideresearch.com/product/6308186817/south-africa-veterinary-services-market) |
| Share of Africa cat food market | 32.7% (largest), 10.0% CAGR to 2031 | [Mordor Intelligence](https://www.mordorintelligence.com/industry-reports/africa-cat-food-market) |

South Africa is **a genuinely different economy** from Kenya or Nigeria and must not be averaged with them. It has a real, formalised, insured companion-animal sector with pet insurance products, referral hospitals, and specialist practice.

### 4.4 Ability to pay

| Item | Price | Source |
|---|---|---|
| Routine consultation, major city | **R350–700 (USD ~19–38)** | [CoverSearch](https://coversearch.co.za/blog/how-much-is-vet-consultation-fee-south-africa/), [Dog Insurance SA](https://doginsurance.co.za/typical-vet-costs-in-south-africa-you-should-know-about/) |
| Consultation, typical range | R350–550 | [CoverSearch](https://coversearch.co.za/blog/how-much-is-vet-consultation-fee-south-africa/) |
| Vaccine per injection | R150–400 | [CoverSearch](https://coversearch.co.za/blog/how-much-is-vet-consultation-fee-south-africa/) |
| Spay/neuter | R1,500–4,000 | [CoverSearch](https://coversearch.co.za/blog/how-much-is-vet-consultation-fee-south-africa/) |

A South African consultation is **2–3× a Kenyan one in USD terms**. Realistic PMS budget for an SA practice: **R1,500–3,500/month (USD 80–190)**. `[UNVERIFIED — no public list price found for any South African vet PMS; derived from consultation economics and the VETport benchmark below]`

### 4.5 Existing veterinary software — South Africa is already served

This is the decisive finding for South Africa.

**Vetmaster** (Pretoria) — [vetmaster.co.za](https://www.vetmaster.co.za/), [Netcash partner listing](https://netcash.co.za/partners/vetmaster/)
- **~300 veterinary practices** already on it — roughly **39% of the 770-practice companion core**.
- Fully **cloud-based**, browser-only, any device.
- Modules: treatments, marketing, practice management, stock control, appointments, reminders/follow-ups, accounting, patient records, reporting.
- **Explicitly covers "vet shops, boarding kennels and grooming parlours."**
- Positions on price: "most competitive prices in the world."
- Already expanding into Africa via agencies; runs `lspca.vetmaster.africa`.

Read that module list again. **Retail POS, boarding, and grooming — three of Aleefy's differentiating modules — are already in the incumbent's product, at "most competitive prices in the world", from a local company with local support and a local payments integration.**

**Vetsoft** — [vetsoftza.co.za](https://vetsoftza.co.za/)
- Cloud-based, "tailored specifically for the South African veterinary industry."
- Patient, accounts, inventory, booking/calendar, leave management, SMS reminders, multi-owner pet facility, roles/security, reporting.
- Locally relevant features Aleefy does not have: **equine management**, **Debtors Age Analysis**, **South African VAT reports** ([GetApp ZA](https://www.getapp.za.com/directory/77/veterinary/software), [vetsoftza.co.za](https://vetsoftza.co.za/)).

**International products already selling into South Africa**
- **VETport** — cloud PMS, **from USD 229/month**, usage-based ([Capterra](https://www.capterra.com/p/92897/Vetport/)); listed on [GetApp South Africa](https://www.getapp.za.com/software/2063878/vetport).
- **Vetstoria** — online booking, 4,500+ teams globally, listed on [GetApp South Africa](https://www.getapp.za.com/software/107198/online-booking).
- Full South African vet software directories exist on [Capterra ZA](https://www.capterra.co.za/directory/30617/veterinary/software) and [GetApp ZA](https://www.getapp.za.com/directory/77/veterinary/software) — this is a mature, comparison-shopped category.

**Conclusion: South Africa is the one country in the region with real money, and it is precisely the country where the shelf is already full.**

### 4.6 E-invoicing — no wedge, and none until roughly 2028

- As of 2026, South Africa still runs on the VAT Act 89 of 1991 invoicing rules. **Paper, PDF and electronic invoices are all accepted. There is no structured-format mandate and no real-time reporting obligation** ([Fonoa](https://www.fonoa.com/resources/blog/south-africa-e-invoicing-real-time-vat-reporting)).
- SARS and National Treasury confirmed on **3 February 2026** a multi-year move to mandatory e-invoicing using a **Peppol-based five-corner model with a Central Tax Hub** ([KPMG](https://kpmg.com/us/en/taxnewsflash/news/2026/02/south-africa-tax-authority-confirms-multi-year-e-invoicing-digital-reporting-reform.html), [RTC Suite](https://rtcsuite.com/south-africa-confirms-a-multi-year-roadmap-for-mandatory-e-invoicing-and-real-time-vat-reporting/)).
- **Timeline: pilots and system design through 2026, phased rollout 2026–2029 starting with the largest VAT vendors, full operation anticipated 2028** ([Comarch](https://www.comarch.com/trade-and-services/data-management/legal-regulation-changes/south-africa-transitions-to-mandatory-e-invoicing-and-real-time-vat-reporting/), [VATupdate](https://www.vatupdate.com/2026/06/02/south-africas-e-invoicing-reform-2026-key-dates-and-requirements/)).

Small veterinary practices are at the **back** of a rollout that starts with the largest VAT vendors. There is no e-invoicing sale to be made in South Africa in this planning horizon. And when it arrives it is **Peppol** — an open international standard that every incumbent will implement, not a proprietary local moat.

### 4.7 Payments, repatriation and tax exposure — South Africa's one clear advantage

- **Card penetration is high** and Stripe/Paddle/Lemon Squeezy can bill South African cards without a local entity. Netcash is the local rail (and Vetmaster is already integrated with it — [Netcash](https://netcash.co.za/partners/vetmaster/)).
- **No non-resident VAT registration below R2.3m.** Foreign electronic-services suppliers must register for SA VAT once supplies exceed **R2.3 million** in any 12 months — raised from R1m on **1 April 2026** ([SARS VAT-REG-02-G02](https://www.sars.gov.za/wp-content/uploads/Ops/Guides/VAT-REG-02-G02-Foreign-Suppliers-of-Electronic-Services-External-Guide.pdf), [RSM South Africa](https://www.rsm.global/southafrica/insights/regulation-amending-vat-foreign-suppliers-electronic-services)). R2.3m ≈ **USD 125k** — comfortably above any realistic Aleefy revenue. **No registration required.**
- Further relief: **since 1 April 2025, foreign suppliers selling solely to VAT-registered businesses are excluded** — the customer self-assesses ([RSM South Africa](https://www.rsm.global/southafrica/insights/regulation-amending-vat-foreign-suppliers-electronic-services)). Veterinary practices above the R1m SA VAT threshold are VAT-registered businesses. So even at scale, the exclusion likely applies.
- **No FX repatriation problem.** The rand is freely convertible for this kind of trade.
- **Timezone: SAST is UTC+2 — identical to Cairo winter time, one hour behind Cairo summer time. The best overlap of any market outside MENA.** Remote support is fully credible.

**South Africa is the only country in the region where the mechanics of being a foreign vendor actually work.** The problem is not the plumbing. It is the competition.

### 4.8 South Africa ARR arithmetic

- Addressable: ~770 primary companion-animal practices.
- Realistically contestable after removing Vetmaster's ~300, plus practices on Vetsoft, VETport, ezyVet, Provet Cloud, and legacy desktop systems: perhaps **250–350 genuinely in play**.
- Foreign, unknown, English-only, no local presence, no local references, no local payment rail, no local VAT reports, no equine module: a **3–8% win rate against that contestable set over three years is optimistic.**
- **10–25 practices × USD 100–150/month ≈ USD 12k–45k ARR by year 3.**

Midpoint ≈ **USD 25–30k**. That is *the same as Egypt*, achieved in a harder market, in a second language, against an entrenched incumbent, while abandoning the Arabic differentiator. **The added complexity buys nothing.**

---

## 5. Priority country — NIGERIA

### 5.1 Veterinary practice count

The Veterinary Council of Nigeria maintains the statutory register but **does not publish counts or a downloadable register on its public site** ([vcn.gov.ng](https://www.vcn.gov.ng/)). The Council has previously issued 60-day ultimatums to unregistered operators, which tells you the register is incomplete relative to actual practice ([Vanguard](https://www.vanguardngr.com/2021/08/practice-veterinary-council-issues-60-days-ultimatum-to-operators-over-registration/)).

The one hard data point is Lagos, the largest and wealthiest state, at the point a regulatory task force was inaugurated:

| Lagos State registered veterinary premises (2021) | Count |
|---|---|
| Veterinary clinics | **26** |
| Veterinary hospitals | **6** |
| Veterinary pharmacies | 50 |
| Pet shops | 22 |
| Veterinary ambulatory points | 4 |
| Veterinary pharmaceutical companies | 2 |
| Private practising veterinarians (statewide, estimated) | ~500 |

Source: [Voice of Nigeria](https://von.gov.ng/lagos-inaugurates-task-force-on-veterinary-practice-premises/), [P.M. News](https://pmnewsnigeria.com/2021/08/05/lagos-inaugurates-task-force-to-regulate-veterinary-practices/), [The Eagle Online](https://theeagleonline.com.ng/lagos-inaugurates-task-force-on-veterinary-practice-premises/).

**Read this carefully. Nigeria's commercial capital, a city of over 15 million people, had 32 registered veterinary clinics and hospitals combined.** Extrapolating nationally with a generous multiplier for Abuja, Port Harcourt, Ibadan and the rest gives **perhaps 120–350 formal companion-animal practices in all of Nigeria.** `[UNVERIFIED — extrapolated from the Lagos 2021 figures; no national premises count is published]`

That is a smaller addressable base than South Africa, in a currency that has lost most of its dollar value, with the worst payment mechanics in the region.

### 5.2 Pet ownership and ability to pay

| Metric | Value | Source |
|---|---|---|
| Nigerians owning a pet (survey) | 42% | [TGM Statbox 2023 via Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |
| Urban households owning a pet | "nearly half" | [Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |
| Dog food price move | ₦40,000 → ₦70,000 (~USD 25.70) | [Top Africa News](https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/) |

A 75% naira price increase on dog food is the whole story: **input costs are inflating faster than incomes, and a USD-denominated software subscription is a rising real cost to a Nigerian clinic every single month.** Dollar-priced SaaS is the first thing cut.

### 5.3 FIRS e-invoicing — mandatory, and structurally closed to this team

Nigeria's mandate is real and is arriving fast:

- **Phase 1:** turnover ≥ ₦5bn — deadline extended to **1 November 2025** ([Global VAT Compliance](https://www.globalvatcompliance.com/globalvatnews/nigeria-e-invoicing-rollout-key-updates-2026/), [Deloitte Nigeria](https://www.deloitte.com/ng/en/services/tax/perspectives/FIRS-announces-e-invoicing-mandate-for-large-taxpayers-in-Nigeria.html)).
- **Phase 2:** all remaining VAT-registered businesses from **1 January 2026** ([Duplo](https://tryduplo.com/blog/firs-e-invoicing-in-nigeria-how-to-comply-2026)).
- **Phase 3:** non-resident companies, expected 2026, dates pending ([Global VAT Compliance](https://www.globalvatcompliance.com/globalvatnews/nigeria-e-invoicing-rollout-key-updates-2026/)).
- Platform: **FIRSMBS** (Merchant-Buyer Solution), real-time validation before delivery to buyer ([EY](https://www.ey.com/en_gl/technical/tax-alerts/nigerias-federal-inland-revenue-service-rolls-out-e-invoicing-platform), [Andersen Nigeria](https://ng.andersen.com/firs-implements-merchant-buyer-solution-and-e-invoicing-in-nigeria/)).
- Technical: UBL 3.0 XML/JSON, **55 mandatory fields across 8 categories**, OAuth 2.0, TLS 1.3, AES-256, ECDSA digital signatures ([Duplo](https://tryduplo.com/blog/firs-e-invoicing-in-nigeria-how-to-comply-2026)).

**The blocker:** invoices route through **certified Access Point Providers**, and software vendors/APPs must obtain **NITDA (National Information Technology Development Agency) accreditation** ([Duplo](https://tryduplo.com/blog/firs-e-invoicing-in-nigeria-how-to-comply-2026)).

A two-person Egyptian company with no Nigerian entity, no Nigerian director, and no capital will not obtain NITDA accreditation. The alternative — routing through a commercial APP — means paying a Nigerian intermediary per invoice, which destroys the margin on a USD 40/month subscription.

Penalties for the clinic are severe (₦1m first day, ₦10,000/day thereafter, ₦200,000 plus 100% of tax due for processing failures — [Duplo](https://tryduplo.com/blog/firs-e-invoicing-in-nigeria-how-to-comply-2026)), which means **no Nigerian clinic will trust its compliance to an unaccredited foreign vendor.** The regulatory hook that looks like an opportunity is in fact a licensing barrier.

### 5.4 FX and repatriation — the hard blocker

- All FX must transact through **NAFEM**, and only licensed institutions may intermediate ([CBN Nigeria FX Code, January 2025](https://www.cbn.gov.ng/Out/2025/CCD/Nigeria%20FX%20Code%20.pdf)).
- CBN **suspended approvals for extending repatriation timelines** for export proceeds in a January 2025 circular ([Mondaq](https://www.mondaq.com/nigeria/export-controls-trade-investment-sanctions/1580848/an-explanatory-note-on-the-cbns-suspension-of-time-extension-for-the-repatriation-of-export-proceeds)).
- Remittances must go through authorised dealer banks with AML and tax compliance documentation ([CBN Reforms](https://www.cbn.gov.ng/AboutCBN/Reforms.html); [Legal500 — Tax and Repatriation Strategies](https://www.legal500.com/developments/thought-leadership/tax-and-repatriation-strategies-for-foreign-owned-nigerian-businesses/)).
- **Flutterwave Nigeria** requires, for a foreign national, a residence permit and authorisation to live and work in Nigeria; USD payouts require a **Zenith Bank USD domiciliary account** ([Flutterwave — Nigeria onboarding](https://flutterwave.com/gh/support/onboarding/onboarding-requirements-for-using-flutterwave-in-nigeria)).
- **Paystack** grants international payments only after business activation and full compliance clearance ([Paystack](https://support.paystack.com/en/articles/2130690)).

**Practical translation: to collect naira from Nigerian clinics and convert it to hard currency, you need a Nigerian entity, a Nigerian resident director or permit, and a domiciliary account.** Without those, you are limited to the small subset of Nigerian clinics holding an international card — which is very few among small veterinary practices.

**Nigeria is not addressable. It fails on market size, ability to pay, currency risk, regulatory accreditation, and payment collection — five independent blockers, any one of which is disqualifying.**

### 5.5 Timezone

WAT is UTC+1 — one to two hours behind Cairo. Support is workable. It is the only thing that works.

---

## 6. Rest of East Africa — brief

| Country | Assessment |
|---|---|
| **Tanzania** | Livestock-dominated veterinary profession. Companion-animal practice is a handful of clinics in Dar es Salaam and Arusha, largely serving the expatriate and diplomatic community. No published companion-clinic count found. Addressable clinics likely **<30**. `[UNVERIFIED]` |
| **Uganda** | Same shape as Tanzania, smaller. Kampala only. Addressable clinics likely **<25**. `[UNVERIFIED]` |
| **Ethiopia** | Large veterinary workforce, overwhelmingly livestock and public sector. Companion-animal pet-keeping is culturally limited. Severe FX shortage and strict capital controls make collecting foreign currency impractical. **Not addressable.** |
| **Rwanda** | Small (~14m people), well-governed, strong e-government, but the companion-animal clinic base is Kigali-only and likely **<15 clinics**. Rwanda has an EBM (Electronic Billing Machine) regime analogous to eTIMS, which is a technical hook, but there is no revenue behind it at this scale. `[UNVERIFIED on clinic count]` |

**None of these individually or collectively reaches the Egypt benchmark.** Combined East Africa ex-Kenya is plausibly under USD 10k ARR at any realistic penetration.

---

## 7. Rest of West Africa — brief

| Country | Assessment |
|---|---|
| **Ghana** | The most navigable West African market after Nigeria — stable-ish cedi, English-speaking, functioning payment rails (MTN MoMo, Paystack Ghana). But the companion-animal clinic base is Accra-and-Kumasi only, likely **<40 clinics**. Ghana has an e-VAT / Certified Invoicing System rollout underway which is a technical parallel to eTIMS. Too small to justify entry alone. `[UNVERIFIED on clinic count]` |
| **Ivory Coast** | **Francophone.** The product ships English and Arabic. This is a hard disqualification, not a soft one — a francophone clinic will not adopt an English-only ERP. Add French and revisit; do not before. |
| **Senegal** | **Francophone.** Same disqualification. Smaller than Ivory Coast. |

Francophone West Africa is off the table until the product ships French. That is a substantial localisation project (UI, invoices, tax documents, support) for two people, aimed at markets smaller than Kenya.

---

## 8. Rest of Southern Africa — brief

| Country | Assessment |
|---|---|
| **Botswana** | ~2.7m people. High GDP per capita by regional standards, stable pula, English-speaking, well-regulated. But the companion-animal clinic base is Gaborone and Francistown — likely **15–30 clinics**. Practically, Botswana is served by South African vendors and South African referral hospitals. `[UNVERIFIED on clinic count]` |
| **Namibia** | ~2.6m people, similar profile to Botswana, similarly served out of South Africa. Likely **15–30 clinics**. `[UNVERIFIED]` |
| **Zambia** | Lusaka-centred, small formal companion sector, kwacha volatility. Likely **<25 clinics**. `[UNVERIFIED]` |
| **Zimbabwe** | Currency instability makes USD-priced subscriptions unpredictable and collection unreliable. A once-strong veterinary profession has been heavily eroded by emigration. **Not addressable.** |

**Critical structural point:** Botswana, Namibia, Zambia and Zimbabwe are, commercially, **satellites of South Africa**. They buy South African products through South African channels. The correct way to reach them is as an extension of a South African position — which the team does not have and cannot cheaply build. They are not independent market entries.

---

## 9. Cross-cutting: what "no local presence" actually costs here

| Requirement | Kenya | Nigeria | South Africa |
|---|---|---|---|
| Non-resident tax registration needed | **Yes** — VAT 16% + SEP 3%, monthly filings | Phase 3 non-resident e-invoicing expected 2026 | **No** — below R2.3m threshold |
| Local entity needed to collect payment | Effectively yes (M-Pesa, Flutterwave KE) | **Yes** (domiciliary account, permit) | **No** — cards work |
| FX repatriation friction | Moderate | **Severe** | **None** |
| Regulatory accreditation to sell the e-invoicing feature | Third-party vendor certification | **NITDA accreditation — closed** | N/A (no mandate yet) |
| Timezone overlap with Cairo | 0–1 hr | 1–2 hr | **0–1 hr** |
| Entrenched local vet software | No | No | **Yes — Vetmaster ~300 practices** |
| Language served by English-only | Yes | Yes | Yes |

The pattern is stark and it is a genuine dilemma: **the two markets where there is no entrenched competitor (Kenya, Nigeria) are the two where a foreign vendor cannot easily get paid or certified. The one market where the foreign-vendor mechanics work cleanly (South Africa) is the one that is already served.**

That is not an accident. Vetmaster exists in South Africa *because* South Africa has enough money to support a local vet software company. Kenya and Nigeria have no Vetmaster equivalent *because* the market cannot support one — which is also the reason it cannot support Aleefy.

---

## 10. What would have to change

Entry becomes rational only if **at least two** of the following are true:

1. **A South African reseller or partner is signed** who carries sales, first-line support, and local credibility, and who is compensated on revenue rather than retainer. This is the highest-leverage single change and the only realistic route into the region.
2. **South Africa's Peppol e-invoicing mandate reaches small VAT vendors** and the incumbents are slow to implement. This is a 2028–2029 event at the earliest, per SARS's own roadmap. It is a diary entry, not a plan.
3. **The product ships French**, opening Ivory Coast, Senegal, and francophone Central Africa — but these are smaller than the anglophone markets already rejected, so this only makes sense combined with #1.
4. **The team grows past two people** and can absorb monthly Kenyan SEP/VAT filings, per-clinic eTIMS onboarding, and cross-border support without starving the Egyptian business.
5. **A vertical-specific distribution channel appears** — e.g. a pet food or pharmaceutical distributor with an existing clinic relationship in South Africa willing to bundle software. Vetmaster's own "going international through the use of agencies" model shows this is how the region is actually sold.

**Absent those, every hour spent on Sub-Saharan Africa is an hour not spent on the Egyptian and Gulf markets where Arabic is worth something.**

---

## 11. Is Sub-Saharan Africa addressable for this team — yes or no

### **NO.**

Not for a two-person, Cairo-based, English-and-Arabic-only vendor with no capital and no local presence. Not in this planning horizon.

**The single best country if the team ignores this advice: South Africa.**

South Africa is the only defensible choice. It has 770 primary companion-animal practices (real, counted from the SAVC register), 7.4m dogs and 2m cats, consultations at USD 19–38, freely convertible currency, working card payments, an identical timezone to Cairo, and — critically — **no non-resident VAT registration obligation below R2.3m**. The mechanics of selling there from Egypt are the cleanest in the region.

But it should still be a no, because:

- **The market is already served, by a local incumbent with the same feature set.** Vetmaster has ~300 of the 770 practices, is cloud-based, is priced aggressively, and already ships boarding, grooming and retail — the modules Aleefy would lead with. Vetsoft covers the same ground with South African VAT reports and equine management that Aleefy lacks.
- **The facility base is shrinking, not growing:** 1,596 active facilities in April 2024 to 1,529 in July 2026.
- **There is no regulatory wedge.** SARS e-invoicing is not mandatory, will not reach small practices before roughly 2028, and will be Peppol-based — an open standard every incumbent will implement.
- **The arithmetic does not clear the bar.** A realistic year-3 outcome is USD 12k–45k ARR, midpoint ~USD 25–30k — the same as Egypt, in a foreign market, in a second language, with no Arabic advantage and no local support.

**Kenya** fails on size (60–150 companion clinics, realistic ceiling ~USD 21k ARR — *below* Egypt) and on cost of compliance (mandatory non-resident VAT registration plus 3% SEP tax with monthly filings). Its eTIMS mandate is genuinely far-reaching and genuinely open to third-party integrators, but **KRA hands small businesses free invoicing tools — eTIMS Lite, USSD `*222#`, a free Windows/Android client — which removes the pain that would make integration worth paying for.**

**Nigeria** fails on five independent blockers, any one of which is fatal: a tiny formal base (32 registered clinics and hospitals in all of Lagos), collapsing real purchasing power for USD-priced software, mandatory FIRS e-invoicing routed through **NITDA-accredited** Access Point Providers the team cannot become, severe CBN FX repatriation controls, and payment collection that requires a Nigerian entity and a domiciliary account.

Everything else in the region is smaller, francophone, or a commercial satellite of South Africa.

### The biggest structural blocker, stated once

**Every market in this region is gated either by a local incumbent or by a local licence — and the two are mutually exclusive by design.** Where a foreign vendor can get paid and comply without a local entity (South Africa), the shelf is already full. Where the shelf is empty (Kenya, Nigeria), the state requires accreditation, non-resident tax registration, or a domiciliary bank account that a two-person Egyptian company cannot obtain. There is no country in Sub-Saharan Africa where both doors are open at once.

**The precondition for this region is a local partner or entity. Without one, the answer is no — and with one, the correct first and only country is South Africa.**

---

## Appendix A — Source list

**Veterinary registers (primary, parsed directly)**
- Kenya Veterinary Board — Registers: https://www.kenyavetboard.or.ke/en/registers (`VET SURGEONS 2026 REGISTER_4.xlsx`, 1,342 entries)
- Kenya Veterinary Board — Retention/compliance: https://kenyavetboard.or.ke/en/registration/retention
- SAVC — Register of Active Facilities, 1 Jul 2026: https://savc.org.za/public-infomation/list-of-all-practising-professionals-and-registered-facilities/ (1,529 facilities)
- SAVC — Active Facilities, Apr 2024: https://savc.org.za/wp-content/uploads/2024/04/Active-facilities-Apr-2024.pdf (1,596 facilities)
- Veterinary Council of Nigeria: https://www.vcn.gov.ng/ (no published counts)

**Practitioner and workforce statistics**
- SAVC registration totals + vets-per-million ratio: https://dailynews.co.za/news/south-africa/2025-04-26-is-south-africas-veterinary-workforce-crisis-threatening-food-security-and-animal-health/
- Lagos registered veterinary premises 2021: https://von.gov.ng/lagos-inaugurates-task-force-on-veterinary-practice-premises/ | https://pmnewsnigeria.com/2021/08/05/lagos-inaugurates-task-force-to-regulate-veterinary-practices/
- VCN registration enforcement: https://www.vanguardngr.com/2021/08/practice-veterinary-council-issues-60-days-ultimatum-to-operators-over-registration/

**Market size and pet ownership**
- Kenya pet industry statistics: https://www.dogster.com/statistics/pet-industry-statistics-kenya
- Kenya pet food forecast: https://www.statista.com/outlook/cmo/food/pet-food/kenya
- African pet ownership and market data: https://www.topafricanews.com/2025/06/16/more-dogs-and-cats-move-in-as-household-disposable-income-grows-in-africa/
- Africa cat food market, SA share and StatsSA cat data: https://www.mordorintelligence.com/industry-reports/africa-cat-food-market
- SA veterinary services market: https://www.bonafideresearch.com/product/6308186817/south-africa-veterinary-services-market

**Pricing**
- Nairobi vet fees: https://ducknetvetclinic.co.ke/how-much-vets-charge-in-nairobi/
- SA vet consultation fees: https://coversearch.co.za/blog/how-much-is-vet-consultation-fee-south-africa/ | https://doginsurance.co.za/typical-vet-costs-in-south-africa-you-should-know-about/
- VETport pricing (USD 229/mo): https://www.capterra.com/p/92897/Vetport/

**Existing veterinary software**
- Vetmaster: https://www.vetmaster.co.za/ | https://netcash.co.za/partners/vetmaster/
- Vetsoft: https://vetsoftza.co.za/
- SA vet software directories: https://www.capterra.co.za/directory/30617/veterinary/software | https://www.getapp.za.com/directory/77/veterinary/software

**E-invoicing and fiscalisation**
- KRA eTIMS FAQ (scope, exemptions, deductibility, Lite/USSD): https://www.kra.go.ke/helping-tax-payers/faqs/learn-about-etims
- KRA eTIMS system-to-system integration and third-party certification: https://www.kra.go.ke/business/etims-electronic-tax-invoice-management-system/learn-about-etims/etims-system-to-system-integration
- KRA OSCU/VSCU step-by-step sign-up guide: https://www.kra.go.ke/images/publications/OSCU_VSCU_Step-by-Step_Guide-on-how-to-sign-up.pdf
- eTIMS API integration notes: https://invoicedataextraction.com/blog/kenya-etims-api-integration-guide
- Nigeria FIRS e-invoicing compliance and NITDA accreditation: https://tryduplo.com/blog/firs-e-invoicing-in-nigeria-how-to-comply-2026
- Nigeria rollout timeline: https://www.globalvatcompliance.com/globalvatnews/nigeria-e-invoicing-rollout-key-updates-2026/
- FIRSMBS platform: https://www.ey.com/en_gl/technical/tax-alerts/nigerias-federal-inland-revenue-service-rolls-out-e-invoicing-platform | https://ng.andersen.com/firs-implements-merchant-buyer-solution-and-e-invoicing-in-nigeria/
- Nigeria large taxpayer mandate: https://www.deloitte.com/ng/en/services/tax/perspectives/FIRS-announces-e-invoicing-mandate-for-large-taxpayers-in-Nigeria.html
- South Africa e-invoicing status and roadmap: https://www.fonoa.com/resources/blog/south-africa-e-invoicing-real-time-vat-reporting | https://kpmg.com/us/en/taxnewsflash/news/2026/02/south-africa-tax-authority-confirms-multi-year-e-invoicing-digital-reporting-reform.html | https://rtcsuite.com/south-africa-confirms-a-multi-year-roadmap-for-mandatory-e-invoicing-and-real-time-vat-reporting/ | https://www.comarch.com/trade-and-services/data-management/legal-regulation-changes/south-africa-transitions-to-mandatory-e-invoicing-and-real-time-vat-reporting/ | https://www.vatupdate.com/2026/06/02/south-africas-e-invoicing-reform-2026-key-dates-and-requirements/

**Non-resident tax and payments**
- SARS foreign suppliers of electronic services guide: https://www.sars.gov.za/wp-content/uploads/Ops/Guides/VAT-REG-02-G02-Foreign-Suppliers-of-Electronic-Services-External-Guide.pdf
- SA electronic services VAT threshold change to R2.3m: https://www.rsm.global/southafrica/insights/regulation-amending-vat-foreign-suppliers-electronic-services
- Kenya SEP tax regulations: https://www.cliffedekkerhofmeyr.com/en/news/publications/2025/Practice/Tax-Exchange-Control/tax-and-exchange-control-alert-03-october-Kenya-issues-draft-Income-Tax-Significant-Economic-Presence-Tax-Regulations-2025 | https://www.kra.go.ke/images/publications/Draft-Income-Tax-Signifficant-Economic-Presence-Tax-Regulations-2025.pdf
- Kenya VAT + SEP guide for digital businesses: https://www.cleartax.co.ke/kenya-vat-significant-economic-presence-sep-tax-digital-businesses.html
- CBN Nigeria FX Code Jan 2025: https://www.cbn.gov.ng/Out/2025/CCD/Nigeria%20FX%20Code%20.pdf
- CBN repatriation extension suspension: https://www.mondaq.com/nigeria/export-controls-trade-investment-sanctions/1580848/an-explanatory-note-on-the-cbns-suspension-of-time-extension-for-the-repatriation-of-export-proceeds
- Nigeria repatriation strategies: https://www.legal500.com/developments/thought-leadership/tax-and-repatriation-strategies-for-foreign-owned-nigerian-businesses/
- Flutterwave Kenya onboarding: https://flutterwave.com/ng/support/onboarding/onboarding-requirements-for-using-flutterwave-in-kenya
- Flutterwave Nigeria onboarding: https://flutterwave.com/gh/support/onboarding/onboarding-requirements-for-using-flutterwave-in-nigeria
- Paystack international payments: https://support.paystack.com/en/articles/2130690

## Appendix B — Items marked UNVERIFIED

| Claim | Why unverified |
|---|---|
| Kenya companion-animal clinic count 60–150 | KVB publishes no premises register; reasoned from the 1,342-vet register and Nairobi's visible pet-services sector |
| Kenya clinic software budget USD 25–60/mo | Derived from consultation pricing; no Kenyan vet-PMS price list is public |
| South Africa PMS budget R1,500–3,500/mo | No SA vet PMS publishes list pricing; Vetmaster and Vetsoft are quote-only |
| Nigeria national companion clinic count 120–350 | Extrapolated from Lagos 2021 premises data; no national count published |
| Clinic counts for Tanzania, Uganda, Rwanda, Ghana, Botswana, Namibia, Zambia | No published registers located for any of these |
| ARR projections (all countries) | Modelled from clinic counts × price points × assumed win rates; ranges given deliberately |
