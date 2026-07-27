# 08 — South and Southeast Asia Market Assessment

**Product:** Aleefy — veterinary clinic ERP. English and Arabic only.
**Team:** two people, Cairo (UTC+2/+3), no capital, no local presence anywhere in Asia.
**Benchmark to beat:** Egypt-only year-3 ARR ≈ USD 25k (see `03_PRICING_AND_ECONOMICS.md`).
**Countries assessed:** Pakistan, India, Bangladesh, Sri Lanka, Indonesia, Malaysia, Philippines, Vietnam, Thailand.

---

## 0. Verdict up front

**No. None of the nine is worth this team's attention as a market.**

Not one country clears all four gates simultaneously: (a) a companion-animal clinic base large enough to matter, (b) English sufficiency, (c) a workable support window, (d) a way to actually get paid. Every country clears one or two and fails the rest.

The single most damaging finding is that **the e-invoicing wedge — the thing that makes Aleefy differentiated in Egypt and the Gulf — does not reach veterinary clinics anywhere in Asia except Pakistan.** Every other mandate in the region carries a turnover threshold that sits above a typical small-animal practice, or is voluntary:

| Country | Mandate | Threshold that excludes small clinics |
|---|---|---|
| Malaysia | MyInvois | **Below RM1m turnover: fully exempt.** RM1m–5m: no penalty until 31 Dec 2027 |
| Indonesia | e-Faktur / Coretax | **Only PKP, i.e. > IDR 4.8bn (~USD 290k) revenue** |
| Philippines | BIR EIS | **Phase 1 is > PHP 1bn taxpayers.** Micro (< PHP 3m) exempt outright |
| Thailand | e-Tax Invoice | **Voluntary. No mandate at all** |
| Vietnam | Decree 70/2025 | Applies from VND 1bn (~USD 39k) — **does bite**, but requires a *locally authorised* provider |
| India | GST e-invoicing | **Veterinary clinical services are GST-exempt**, and e-invoicing exempts nil-rated and B2C supplies outright. Threshold ₹5 crore. **Legally cannot apply** |
| **Pakistan** | **FBR digital invoicing** | **All sales-tax-registered persons. No turnover carve-out.** |

Pakistan is the only market where the wedge is real. It then fails on the money: **Pakistani businesses cannot reliably pay a foreign software vendor in USD**, and no credible figure exists for the size of Pakistan's companion-animal clinic base.

**The second most important finding is that timezone was never the binding constraint — price and incumbency are.** India has the best timezone in the region (IST +3.5h, a 6.5-hour overlap) and workable English, and is still the clearest reject of all nine: the Indian vet software price ceiling is **US$12–36/month** against 115 competing products, veterinary clinical services are **GST-exempt** so the compliance wedge is legally impossible, and an Egyptian vendor specifically faces **20–21.84% unrelieved withholding** because the India–Egypt treaty has no royalty article.

**Best candidate if forced to name one: Pakistan.** Explained honestly in §3 — it would take a local partner entity and 12–18 months, to reach a market whose size cannot currently be measured.

**Asia as an engineering source: no.** Egypt is already at or below Asian developer cost, and this team has no capital to hire with. **Asia as a partnership source: also mostly no — and the traffic is currently going the other way.** Indian and Malaysian vet-software vendors are already selling into the Gulf, which is Aleefy's own second market (§11).

---

## 1. The constraints that decide this, applied first

Before any market data, three constraints eliminate most of the field. Applying them first is the only way to avoid inventing an opportunity.

### 1.1 Language is not a translation task

Aleefy ships English and Arabic. Arabic has **zero** utility across all nine countries. So the question everywhere is: does English alone suffice?

EF English Proficiency Index 2025 ([en.wikipedia.org/wiki/EF_English_Proficiency_Index](https://en.wikipedia.org/wiki/EF_English_Proficiency_Index), 2025 edition, 2.2m test takers in 2024):

| Country | Rank | Score | Band |
|---|---|---|---|
| Malaysia | 22 | 581 | **High** |
| Philippines | 28 | 569 | **High** |
| Pakistan | 49 | 493 | Low |
| Vietnam | 50 | 500 | Moderate |
| Bangladesh | 60 | 506 | Moderate |
| Sri Lanka | 67 | 486 | Low |
| India | 71 | 484 | Low |
| Indonesia | 73 | 471 | Low |
| Thailand | 117 | 402 | **Very low** |

English is genuinely adequate for business software in **Malaysia and the Philippines only**. Pakistan is a special case — the EF score is low but English is an official language and veterinary/medical education is English-medium, so clinical screens are fine while owner-facing output (receipts, WhatsApp messages) needs Urdu.

Note what "needs a new language" actually costs: not just a string file. Thai needs script rendering, Thai word-break, Buddhist-era dates. Vietnamese needs full diacritics. Indonesian needs IDR formatting and, in practice, WhatsApp-equivalent channel work. And every one of them needs **support in that language, forever**, from two people who don't speak it.

### 1.2 The support window is worse than the raw hour count suggests

Cairo works **09:00–17:00**, weekend **Friday–Saturday**. Clinics work roughly **09:00–19:00** local, weekend **Saturday–Sunday** (Pakistan Sat–Sun; Indonesia, Philippines, Thailand, Vietnam, India Sat–Sun; most Malaysian states Sat–Sun, four states Fri–Sat).

| Market | Offset from Cairo | Clinic's day in Cairo time | Overlap with a Cairo 09:00–17:00 day |
|---|---|---|---|
| Karachi / Lahore | +3h | 06:00–16:00 | **7h** |
| Delhi | +3.5h | 05:30–15:30 | 6.5h |
| Dhaka / Colombo | +4h / +3.5h | 05:00–15:00 | ~6h |
| Jakarta / Bangkok / Hanoi | +5h | 04:00–14:00 | 5h |
| Kuala Lumpur / Manila | +6h | 03:00–13:00 | **4h** |

Two things this table hides, and they matter more than the raw number:

1. **You always lose the customer's morning.** In Manila the clinic opens at 09:00 = 03:00 Cairo. Clinic software fails at opening: the till won't open, yesterday's close is wrong, the first appointment won't load. Those calls land at 3–6am Cairo, every day. The overlap you *do* have is the clinic's late afternoon — the calmest part of their day.
2. **Friday.** Egypt's weekend includes Friday; almost all of Asia works Friday. So the practical coverage is **four fully-staffed days a week (Mon–Thu)**, with Friday unstaffed from Cairo and Sunday staffed but half of Asia off. For a system running a clinic's cash register, four days of cover is not a support offering.

### 1.3 Twenty-five thousand dollars is a higher bar than it looks

Egypt year-3 ARR ≈ USD 25k. To *materially* beat that — say 2× — in a market with a new language, a new tax integration, a 4-hour support window and an entrenched local incumbent, at the prices Asian clinics actually pay (§below, USD 28–115/month), you need roughly **35–70 paying clinics**. In Malaysia that is 5–11% of the entire national companion-animal practice base. There is no plausible path to that from Cairo with no local presence.

---

## 2. The definitional trap: livestock is not companion animal

South and Southeast Asia have enormous *veterinary* sectors that are almost entirely **livestock and poultry**. Pakistan's Punjab, Indonesia's poultry industry, Vietnam's commune-level animal-health workers, India's dairy sector — these produce big-sounding veterinarian counts and big-sounding "animal health market" figures that have nothing to do with a companion-animal clinic buying practice-management software.

Two concrete traps found in this research:

- **Pakistan.** A directory scrape returns **1,267 "animal hospitals"**, of which **857 are in Punjab** ([rentechdigital.com](https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-pakistan), 1 Apr 2026). Punjab is Pakistan's livestock heartland and runs a large network of government veterinary dispensaries for cattle and buffalo. That number is not 1,267 pet clinics.
- **Philippines.** "Veterinary services grew to about USD 1.4bn (2022)" and "Philippines veterinary medicine market USD 650m" ([kenresearch.com](https://www.kenresearch.com/philippines-veterinary-medicine-market)) are dominated by livestock and poultry health, in a country with a very large poultry industry.

**Also: the directory-scrape proxy is not comparable across countries.** The same scraper returns 1,267 for Pakistan, 544 for Indonesia, 454 for the Philippines and **66 for Malaysia** — while Malaysia's own veterinary council data shows **more than 650** licensed companion-animal practices. The scraper is picking up different Google business categories in different countries. Treat all scrape figures as order-of-magnitude only.

**Honest position: reliable companion-animal clinic counts do not exist in open sources for any of these nine countries except Malaysia.** Everything else in this document that looks like a clinic count is a proxy, and is labelled as such.

---

## 3. Priority country — PAKISTAN

The most plausible candidate, and it still fails.

### 3.1 Clinic count — not measurable

- **Pakistan Veterinary Medical Council** is the statutory registrar of veterinary practitioners, established 1999 under the PVMC Act 1996 ([en.wikipedia.org/wiki/Pakistan_Veterinary_Medical_Council](https://en.wikipedia.org/wiki/Pakistan_Veterinary_Medical_Council)). **It publishes no registration count I could reach.** `[UNVERIFIED — no figure found]`
- Directory scrape: **1,267 "animal hospitals"**, Punjab 857 / Sindh 173 / KP 134 / Islamabad 58 ([rentechdigital.com](https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-pakistan), 1 Apr 2026). **Heavily livestock-contaminated** — see §2.
- A curated vet directory lists only **73 clinics** for the whole of Pakistan ([veterinby.com](https://www.veterinby.com/veterinary-clinic-pakistan/), returned HTTP 403 on direct fetch; figure from search index) `[PARTIALLY UNVERIFIED]`.
- **Best honest estimate: the companion-animal clinic base is in the low hundreds, concentrated in Karachi, Lahore and Islamabad.** `[UNVERIFIED — this is an inference, not a source]`

### 3.2 Pet market size — no usable figure exists

- The 6Wresearch Pakistan Pet Care Market page is a **paywalled teaser with no numbers disclosed** (report priced USD 1,995–3,795) ([6wresearch.com](https://www.6wresearch.com/industry-report/pakistan-pet-care-market)).
- Statista's pet food outlook has **no Pakistan-specific data** on the public page ([statista.com](https://www.statista.com/outlook/cmo/food/pet-food/pakistan)).
- A widely-copied blog figure of "USD 1.8m today, USD 5m by 2027" ([dogster.com](https://www.dogster.com/statistics/pakistan-pet-industry-statistics/)) is **implausibly small** for a country of 240m and should be treated as junk.
- Policy signal against the category: the **Finance Bill 2024 imposed a 50% regulatory duty on imported pet food** `[PARTIALLY UNVERIFIED — from search index, primary text not fetched]`. Governments do not tax categories they consider strategic.

**Conclusion: Pakistan's companion-animal market cannot be sized from public sources. That is itself a finding — you would be entering blind.**

### 3.3 Ability to pay

- **No Pakistani veterinary practice-management software with published pricing was found.** `[UNVERIFIED — no product found, which may mean the category is genuinely empty, or merely invisible to search]`
- **No sourced vet consultation fee for Pakistan.** `[UNVERIFIED]`
- Context that matters more than any price point: the PKR has depreciated heavily and a USD-denominated subscription is a compounding, visible cost to the customer. Any Pakistani pricing would have to be PKR-denominated and re-priced regularly.

### 3.4 E-invoicing — **the only genuine wedge found anywhere in Asia**

This is where Pakistan is materially different from every other country in this document.

- **S.R.O. 69(I)/2025, 29 January 2025** substituted Chapter XIV of the Sales Tax Rules 2006 (Rules 150Q–150ZQ) under s.50 of the Sales Tax Act 1990, mandating electronic sales tax invoicing ([rtcsuite.com summary](https://rtcsuite.com/pakistans-digital-tax-evolution-the-e-invoicing-notification-that-will-reshape-compliance/); FBR SRO index at [download1.fbr.gov.pk](https://download1.fbr.gov.pk/)).
- Integration deadlines: **corporate registered persons 1 July 2025, non-corporate 1 August 2025**, after extensions announced 20 June 2025 ([profit.pakistantoday.com.pk](https://profit.pakistantoday.com.pk/2025/08/02/fbr-mandates-phased-integration-of-electronic-invoicing-system-for-sales-tax-registered-entities/)).
- **SRO 1852(I)/2025, 24 September 2025** brings **every** sales-tax-registered person into scope — **no turnover carve-out** ([rtcsuite.com](https://rtcsuite.com/pakistan-extends-e-invoicing-integration-deadlines-for-taxpayers-under-rule-150q/)).

**Is third-party integration open? Yes — and this is the good news.**

- Registered persons integrate "through a licensed integrator **or PRAL**" (Pakistan Revenue Automation Ltd, the FBR's own IT arm).
- **PRAL provides licensed-integrator services free of charge**, with a published **Digital Invoicing API (DI API v1.12)**, client ID/secret credentials, a sandbox and a production endpoint ([FBR technical specification PDF](https://download1.fbr.gov.pk/Docs/20257301172130815TechnicalDocumentationforDIAPIV1.12.pdf); [FBR DI user manual](https://download1.fbr.gov.pk/Docs/20254171643756444DI-User-Manual.pdf)). Sandbox endpoint `https://gw.fbr.gov.pk/di_data/v1/di/postinvoicedata_sb`.
- **Practical catch: FBR/PRAL require a static IP to be whitelisted** for API access ([logiclayer.com.pk integration guide](https://logiclayer.com.pk/blog/how-to-integrate-fbr-digital-invoicing-api-pral-guide)). Workable for cloud, awkward for self-hosted clinics on consumer connections.

**Becoming a *licensed integrator* yourself is closed to this team.** Requirements include: **a company registered in Pakistan**, **minimum paid-up capital of PKR 10 million** (~USD 35k), PSEB or ICAP registration, audited financials, and demonstrated ERP/payment integration experience ([difbr.pk](https://difbr.pk/blog/pakistan-e-invoicing-integrator-licensing-fbr-rules-33m-v); [tmrconsult.com](https://tmrconsult.com/fbr-licensed-integrator-in-pakistan-for-digital-invoicing/)). Not needed if you route through PRAL — but it is the barrier to becoming the *compliance* vendor rather than merely a compliant one.

**The wedge is narrower than it first appears, for two reasons:**

1. **This is federal sales tax, which covers goods.** A vet clinic's *medicine and product sales* fall here. **Veterinary *services* are taxed provincially** and separately — Punjab Revenue Authority at 16%, Sindh Revenue Board at 15% with a **reduced 3% rate for hospitals and clinics**, each with its own rules and systems ([conseric.pk PRA guide](https://conseric.pk/punjab-sales-tax-on-services/); [srb.gos.pk taxable services](https://www.srb.gos.pk/srb/taxable-services/)). Sindh has signalled that "reduced rates and thresholds for pet care will be notified" `[PARTIALLY UNVERIFIED]`. A clinic ERP would have to handle **one federal + four provincial** regimes.
2. **A small clinic may simply not be sales-tax registered.** The mandate binds registered persons; Pakistan's small-business informality is high. No source found on what fraction of vet clinics are registered. `[UNVERIFIED]`

### 3.5 Language — the one place Aleefy's existing work transfers

- EF EPI: rank 49, score 493, "Low" ([wikipedia](https://en.wikipedia.org/wiki/EF_English_Proficiency_Index)).
- But English is an official language of Pakistan and veterinary education is English-medium. **Clinical screens in English are realistic.**
- Owner-facing output — receipts, SMS/WhatsApp reminders, invoices — wants **Urdu**. Urdu is written in Arabic script, right-to-left. **Aleefy already has RTL layout, Arabic-script rendering and Arabic numeral handling built for Egypt.** The infrastructure transfers; the vocabulary does not. This is the only country in the nine where existing Arabic work has any carry-over at all. It is a real, if modest, advantage.

### 3.6 Existing veterinary software

**None found with a published product or pricing.** Searches surfaced clinic websites and pharma companies, not practice-management vendors. This is either a genuine gap or a search-visibility artefact. `[UNVERIFIED — treat "no competitor" claims with suspicion]`

### 3.7 Payment rails — **the disqualifier**

This is where Pakistan dies.

- **Getting paid** requires the Pakistani clinic to send USD abroad. Under State Bank of Pakistan rules, outward remittance requires a **Form-A**, a matching **SBP purpose code**, and supporting documentation; **individuals and sole proprietors face an annual outward limit of roughly USD 10,000**; and **banks routinely reject requests** where "the purpose isn't clearly stated, the documentation is incomplete, or the provided purpose code doesn't align" ([tencoconsulting.com](https://tencoconsulting.com/freelance-payments-pakistan/), summarising SBP rules; see also [SBP FE Manual](https://www.sbp.org.pk/fe_manual/chapters/chapter10.htm)). Pakistani businesses routinely find card payments for foreign SaaS blocked outright.
- **On the Egyptian side**, Stripe does not support Egypt as a seller country at all ([stripe.com/global](https://stripe.com/global)). Aleefy would need a merchant-of-record — Paddle appears open to Egyptian sellers and Lemon Squeezy explicitly lists Egypt for bank payouts (both already sourced in `03_PRICING_AND_ECONOMICS.md` §payment rails).
- **Net: even a willing Pakistani clinic may be structurally unable to pay you.** The workaround is a local reseller who bills in PKR and remits in bulk — which requires exactly the local entity and capital the team does not have.

### 3.8 Pakistan scorecard

| Gate | Result |
|---|---|
| Timezone | ✅ Best in Asia — 7h overlap, only Friday lost |
| Language | 🟡 English clinical + Urdu owner-facing; **RTL/Arabic-script work reuses** |
| E-invoicing wedge | ✅ **Real, mandatory, no threshold, PRAL API open and free** |
| Clinic base | ❌ Unmeasurable; probably low hundreds |
| Ability to pay | ❌ No evidence; weak currency |
| Competition | 🟡 None found, but absence of evidence |
| **Payment rails** | ❌ **Clinics cannot reliably pay a foreign vendor** |

---

## 4. Priority country — MALAYSIA

The best-run market and the most payable customers. It is simply too small, and already served.

### 4.1 Clinic count — the only trustworthy number in this document

- **More than 650 companion-animal practices** operating in Malaysia, with **61 new clinics licensed between January and May** alone, and **3,463 veterinarians registered with the Malaysian Veterinary Council**, of whom only **2,236 held a current annual practising certificate** ([malaysiakini.com](https://www.malaysiakini.com/letters/679109), 2023).
- The Malaysian Veterinary Council registers **companion-animal practice premises** specifically, under the Ministerial Directive 2015 ([mvc.gov.my](https://www.mvc.gov.my/registration)) — so the 650 figure is genuinely companion-animal, not livestock.

**650 practices is the whole market.** At the prices below, 100% of the market is roughly USD 250k–450k of ARR — for *every* vendor combined. A realistic foreign-entrant share of 3–5% is USD 8–22k. **That is at or below the Egypt-only benchmark.**

### 4.2 Pet market size

`[UNVERIFIED — no Malaysia-specific pet care market figure sourced. Search budget exhausted before this could be resolved.]`

### 4.3 Ability to pay — **good, and it sets a hard price ceiling**

**kumoVet published pricing** (Malaysia, per clinic/branch, annual, [kumovet.com/pricing](https://kumovet.com/pricing/)):

| Plan | MYR/year | ≈ USD/month |
|---|---|---|
| kumoVet VET | 1,780 | ~USD 32 |
| kumoVet GROOM | 2,380 | ~USD 43 |
| kumoVet VET PLUS (vet + groom) | 3,280 | ~USD 58 |

All plans include **up to 18 users per clinic**, unlimited storage, a dedicated account manager and technical support.

**Vet consultation fees:** RM35–80 standard at a private KL/Selangor clinic; RM150–350 for emergency hours ([oyen.my](https://www.oyen.my/post/vet-cost-malaysia-2026)). A second source gives RM50–150 for a standard consultation ([trustytails.vet](https://www.trustytails.vet/blog/vet-visit-cost-kl-malaysia-2026)).

**Read the kumoVet number carefully: USD 32–58/month buys a full vet+grooming+boarding+POS+telehealth suite with 18 users, from a local vendor, in the customer's timezone, with local support.** That is the price Aleefy would have to match or beat while operating from 6 hours away.

### 4.4 E-invoicing — the wedge closed in December 2025

MyInvois phases by turnover ([cleartax.com/my](https://www.cleartax.com/my/en/e-invoicing-malaysia)):

| Phase | From | Turnover | Relaxation ends |
|---|---|---|---|
| 1 | 1 Aug 2024 | > RM100m | 31 Jan 2025 |
| 2 | 1 Jan 2025 | RM25m–100m | 30 Jun 2025 |
| 3 | 1 Jul 2025 | RM5m–25m | 31 Dec 2025 |
| 4 | 1 Jan 2026 | RM1m–5m | **31 Dec 2027** |

- **On 6 December 2025 the Cabinet raised the exemption threshold from RM500,000 to RM1,000,000 in annual turnover**, and **cancelled Phase 5 entirely** ([vatupdate.com](https://www.vatupdate.com/2025/12/18/malaysia-raises-e-invoicing-exemption-threshold-to-rm1-million-key-changes-for-2026-rollout/); [sovos.com](https://sovos.com/regulatory-updates/vat/malaysia-mandatory-e-invoicing-exemption-threshold-increased/); [globalvatcompliance.com](https://www.globalvatcompliance.com/globalvatnews/malaysia-e-invoicing-myinvois-rm1m-rm5m-deferred-2027/)).
- **Businesses below RM1m are fully exempt.** RM1m ≈ USD 220k of annual revenue — a single-vet practice is plausibly under it.
- Penalties: RM200–20,000 fine, or up to 6 months imprisonment, per instance ([cleartax.com/my](https://www.cleartax.com/my/en/e-invoicing-malaysia)).
- **Integration is open**: MyInvois Portal for manual, or direct API with a published SDK. MDEC accredits solution providers (e.g. ClearTax) but the sources do not state that accreditation is a precondition for direct API integration `[UNVERIFIED on the foreign-vendor accreditation question specifically]`.

**Why this kills the wedge:** the small clinics that would be Aleefy's entry customers are exempt; the mid-size ones face no penalty until 2028; and **the local incumbent already ships it** — see below.

### 4.5 Existing veterinary software — the market is taken

- **kumoVet** — Malaysian, based in Petaling Jaya, operating in **11 countries across Southeast Asia and beyond**. Feature list overlaps Aleefy almost exactly: appointments, pet EMR with photo annotation, multi-outlet inventory sync, packages, vaccination reminders, **AI speech-to-text case notes**, **telehealth**, multi-branch, Google review management. And explicitly: **"e-Invoicing management with a fully connected and automated submission experience… Stay compliant with LHDN e-Invoicing requirements effortlessly"** ([kumovet.com](https://kumovet.com/solutions/vet-clinic-management-system/)).
- **Kreloses** — "built for Asian businesses", explicitly compliant with **Malaysia's LHDN e-Invoice** and **Indonesia's SATUSEHAT**; pricing behind a country/industry/branch/staff calculator, no public figures ([kreloses.com/vet](https://kreloses.com/vet), [kreloses.com/home/price](https://kreloses.com/home/price)).
- Global players (ezyVet, VETport) also present.

**kumoVet is Aleefy, built by Malaysians, in Malaysia, already regionalised, already e-invoicing compliant, at USD 32–58/month.** There is no differentiated angle left.

### 4.6 Language and rails

- English is fine (EF rank 22, "High").
- **Stripe supports Malaysia** for merchants ([stripe.com/global](https://stripe.com/global)) — so Malaysian clinics are easy to charge by card. The constraint is the Egyptian seller side, solvable via merchant-of-record.

### 4.7 Malaysia scorecard

| Gate | Result |
|---|---|
| Language | ✅ English works |
| Ability to pay | ✅ Real, published, USD 32–58/mo |
| Payment rails | ✅ Easiest of the nine |
| Timezone | ❌ 6h — worst tier, lose the clinic's morning |
| Market size | ❌ **~650 practices total.** Whole market ≈ USD 250–450k ARR |
| E-invoicing wedge | ❌ Small clinics exempt; incumbent already compliant |
| Competition | ❌ kumoVet is a direct, local, cheaper equivalent |

---

## 5. Priority country — INDONESIA

Largest population, largest growth story, and the least accessible of the four.

### 5.1 Clinic count — no official figure

- **PDHI (Indonesian Veterinary Medical Association)** has 53 regional branches; **~15,000–20,000 veterinarians** in Indonesia, against an estimated need of ~70,000 ([en.wikipedia.org/wiki/Veterinary_medicine_in_Indonesia](https://en.wikipedia.org/wiki/Veterinary_medicine_in_Indonesia); PDHI 2020 data). **13 universities** offer veterinary programmes as of 2024 (same source). No companion/livestock split given.
- The Indonesian government **does** maintain a dataset of animal hospitals, animal clinics, ambulatory services and independent veterinary practices — but **publishes only metadata, no figures, on the open-data portal** ([data.go.id](https://data.go.id/dataset/dataset/jumlah-eksisting-rumah-sakit-hewan-klinik-hewan-ambulatori-praktik-dokter-hewan-mandiri-puskesw3)).
- Directory scrape: **544 animal hospitals**, West Java 97 / East Java 92 / Central Java 53 / Jakarta 44 ([rentechdigital.com](https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-indonesia), 1 Apr 2026). Order-of-magnitude only.

### 5.2 Pet market — the figures are irreconcilable

Published 2025 market size estimates range from **USD 605m to USD 2.8bn** depending on the vendor ([market.us](https://market.us/report/indonesia-pet-care-market/) USD 2.8bn 2025 → USD 4.8bn 2034 at 8.1% CAGR; [marknteladvisors.com](https://www.marknteladvisors.com/research-library/pet-care-market-indonesia) USD 4.45bn by 2032 at 8.59%; [futuremarketinsights.com](https://www.futuremarketinsights.com/reports/indonesia-pet-care-market) USD 3.1bn 2026 → USD 7.6bn 2036). **A 4.6× spread between vendors means none of them knows.** All are press-release tier.

The one figure with a plausible shape: Indonesia's **pet population grew 75.7% between 2017 and 2022, to roughly 7.8m pets** (2022) `[press-release tier, treat as directional only]`.

**The growth is real. The measurement is not.**

### 5.3 E-invoicing — does not reach small clinics

- **e-Faktur is mandatory only for PKP** (VAT-registered entrepreneurs), i.e. businesses with **annual revenue above IDR 4.8 billion (~USD 290k)** ([cleartax.com/id](https://www.cleartax.com/id/en/e-invoicing-indonesia); [letsmoveindonesia.com](https://www.letsmoveindonesia.com/tax-in-indonesia-guide-to-e-faktur-system-for-pkp-businesses/)).
- **Coretax** (live 2025) replaced the legacy desktop e-Faktur and DJP Online, centralising clearance: supplier generates XML → uploads to Coretax → real-time validation → **NSFP serial number + QR code** returned → cleared PDF sent to customer ([xpnd.co.id](https://xpnd.co.id/blogs/e-faktur-indonesia-coretax-2026/); [edicomgroup.com](https://edicomgroup.com/electronic-invoicing/indonesia)).

**A typical Indonesian vet clinic is nowhere near IDR 4.8bn. The wedge does not apply.**

### 5.4 Language and support — hard fail

- EF EPI rank 73, score 471, **"Low proficiency"**. Bahasa Indonesia is not optional for clinic staff.
- Jakarta is **UTC+7, five hours ahead**; a clinic's 09:00 opening is 04:00 in Cairo.
- Indonesia is also an archipelago with three time zones (WIB/WITA/WIT), widening the problem.

### 5.5 Competition

- **Kreloses** explicitly targets Indonesia and claims **SATUSEHAT** (Ministry of Health interoperability platform) compliance ([kreloses.com/vet](https://kreloses.com/vet)).
- **kumoVet** operates in 11 SE Asian countries ([kumovet.com](https://kumovet.com/solutions/vet-clinic-management-system/)).
- Local Indonesian-language vet PMS products exist but could not be priced. `[UNVERIFIED — search budget exhausted]`

### 5.6 Ability to pay

Vet consultation in Jakarta/Bali: **IDR 100,000–300,000** routine (~USD 6–19), up to IDR 500,000 depending on clinic tier; emergency IDR 500,000–2,000,000 ([dearpetz.com](https://dearpetz.com/blog/pet-vet-costs-indonesia-id)). A USD 6 consultation is a low revenue base to support a foreign-currency subscription.

### 5.7 Indonesia scorecard — **disqualified on language and timezone before economics matter**

Growth story: ✅. Everything else: ❌ or unmeasurable.

---

## 6. Priority country — PHILIPPINES

English works, the timezone is the worst in the set, and the incumbent has already won.

### 6.1 Clinic count — and an incumbent that already claims more than all of them

- **Bureau of Animal Industry registered veterinary clinics and hospitals: 45**, as of 31 October 2019 ([scribd copy of BAI list](https://www.scribd.com/document/465936597/Registered-Veterinary-Clinics-and-Hospitals-as-of-October-2019)). Obviously reflects under-registration, not the real base.
- **Metro Manila alone: 400+ clinics** across 17 LGUs ([clinicfinderph.com](https://www.clinicfinderph.com/blog/best-vet-clinics-metro-manila)) `[directory-derived]`.
- Directory scrape: **454 nationwide**, Metro Manila 138 / Central Luzon 72 / Davao 18 ([rentechdigital.com](https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-philippines), 1 Apr 2026).
- **VetCloud, a Philippine vendor, claims 600+ veterinary clinics in the Philippines and abroad** ([vetcloudsoftware.org](https://vetcloudsoftware.org/); characterised as "the #1 veterinary clinic management software in the Philippines").

**The incumbent's stated customer count exceeds the countable clinic universe.** Whatever the precise numbers, the formal Philippine clinic market is measured in the hundreds and one local vendor has most of it.

### 6.2 Pet market

- Pet spending **~USD 1.7bn (2023) → USD 2.1bn (2026)** `[press-release tier]`.
- Pet population **9.2m dogs + 3.3m cats = ~12.5m (2023)**; 41% of households own a dog, 8% a cat ([gitnux.org](https://gitnux.org/philippines-pet-industry-statistics/)) `[aggregator, primary source not verified]`.
- "Philippines veterinary medicine market USD 650m" ([kenresearch.com](https://www.kenresearch.com/philippines-veterinary-medicine-market)) — **livestock-dominated, see §2.**

### 6.3 Ability to pay

- Consultation fees: **PHP 300–800** in Manila and Quezon City, **PHP 500–1,500** across Metro Manila, specialists to PHP 2,500; after-hours surcharge PHP 300–800 ([clinicfinderph.com](https://www.clinicfinderph.com/blog/best-vet-clinics-quezon-city)).
- **VetCloud publishes no pricing** — "Subscription Package Pricing… Contact Us" ([vetcloudsoftware.org](https://vetcloudsoftware.org/)). A third-party listing shows a starting price of £99/month flat rate ([capterra.com](https://www.capterra.com/p/147757/VetCloud/alternatives/)) which looks like a listing artefact rather than a real PHP price. `[UNVERIFIED]`
- VetCloud's feature list includes **unlimited users, unlimited storage, unlimited SMS and 24/7 support** — an aggressive bundle to compete against.

### 6.4 E-invoicing — does not reach clinics, and vendors aren't the ones certified

- Legal basis: NIRC ss.237/237-A as amended by the **CREATE MORE Act**, implemented via **Revenue Regulations No. 11-2025** (27 Feb 2025) ([rtcsuite.com](https://rtcsuite.com/e-invoicing-philippines/)).
- **Phase 1 covers**: large taxpayers under the LTS (**> PHP 1bn gross sales**), e-commerce businesses, exporters, and users of Computerized Accounting Systems ([vatupdate.com](https://www.vatupdate.com/2025/10/17/bir-e-invoicing-philippines-2026-compliance-guide-for-electronic-invoice-system-eis/)).
- **Deadline extended from March 2026 to 31 December 2026** ([comarch.com](https://www.comarch.com/trade-and-services/data-management/legal-regulation-changes/philippines-e-invoicing-mandate-extended-new-2026-compliance-deadline/)).
- **Micro taxpayers — broadly below PHP 3m gross sales — are exempt** under the Ease of Paying Taxes framework ([rtcsuite.com](https://rtcsuite.com/e-invoicing-philippines/)).
- **The BIR does not broadly accredit invoicing software vendors.** Certification obligations — **EIS Certification** and a **Permit to Transmit** — sit with the *mandated taxpayer*, not the software provider ([rtcsuite.com](https://rtcsuite.com/e-invoicing-philippines/)). Whether a foreign vendor's system can be certified on a taxpayer's behalf is not stated `[UNVERIFIED]`.

**Net: a PHP 300–800-per-consultation vet clinic is a micro or small taxpayer. It is exempt. There is no compliance urgency to sell against.**

### 6.5 Language and timezone

- English is genuinely fine (EF rank 28, score 569, "High"). This is the Philippines' real strength.
- **Manila is UTC+8 — six hours ahead of Cairo, the largest gap in the set.** Clinic opens 09:00 PHT = **03:00 Cairo**. Overlap is 4 hours, all in the clinic's late afternoon.

### 6.6 Payment rails

**Stripe does not list the Philippines as a supported merchant country** ([stripe.com/global](https://stripe.com/global)) — so card acceptance would run through a merchant-of-record or a local processor. Philippine SMBs transact heavily on GCash and local rails. Chargeable, but not frictionless.

### 6.7 Philippines scorecard

| Gate | Result |
|---|---|
| Language | ✅ Best in the set alongside Malaysia |
| Clinic base | 🟡 Hundreds, growing |
| **Timezone** | ❌ **6h — worst. Clinic opens at 03:00 Cairo** |
| E-invoicing wedge | ❌ Micro/small taxpayers exempt; vendor isn't the certified party |
| Competition | ❌ VetCloud claims 600+ clinics with an unlimited-everything bundle |
| Rails | 🟡 No Stripe; MoR or local processor needed |

---

## 7. Rest of South Asia — India, Bangladesh, Sri Lanka

### 7.1 INDIA — disqualified, and not narrowly

India deserves more than a brief because it is the one country where the timezone is *good* (IST is only 3.5h ahead — a 6.5-hour overlap, better than any Southeast Asian market) and English works in professional software. It fails anyway, on economics and tax plumbing, decisively.

**Clinic count — nobody counts it.**

| Metric | Figure | Source |
|---|---|---|
| Registered veterinary practitioners (VCI) | **67,784** (~2015) | [pib.gov.in](https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=147765) — stale, overwhelmingly livestock; VCI's own register publishes no total ([vci.dahd.gov.in/ivpr](https://vci.dahd.gov.in/ivpr)) |
| "Veterinary hospitals and polyclinics" | ~12,000 (FY2022) | Statista via search index — **government livestock institutions**, not addressable |
| Scraped "animal hospitals" | 9,829 (Apr 2026) | [rentechdigital](https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-india) — top states Rajasthan 1,133, UP 959, TN 955. **A companion-animal distribution would be Maharashtra/Karnataka/Delhi-led. This is livestock infrastructure.** |
| **Mumbai, bottom-up** | **~120 private small-animal clinics**, >700 vets | [WSAVA 2018 via VIN](https://www.vin.com/apputil/content/defaultadv1.aspx?id=8896947&pid=22915) — best primary datapoint; Mumbai is India's richest pet metro |
| Companion-animal entry rate | **~5% of 3,500 annual veterinary graduates ≈ 175/year** | [mordorintelligence.com](https://www.mordorintelligence.com/industry-reports/india-veterinary-healthcare-market-industry) |

**Honest estimate: low single-digit thousands of private companion-animal clinics nationally, concentrated in ~8 metros** `[UNVERIFIED — extrapolated from the Mumbai figure; no source publishes this]`. Not 9,829.

**Market size.** The credible source is **Redseer, "From Kibble to Care" (2024): US$3.6bn (2024) → US$7bn (2028)**, 48% products / 52% services, from a US$1.6bn 2019 baseline ([consultancy.in](https://www.consultancy.in/news/4276/indias-pet-care-market-to-see-steady-growth-to-7-billion-market); [india-briefing.com](https://www.india-briefing.com/news/indias-pet-care-economy-2025-an-overview-37234.html/)). Press-release figures contradict it outright — IMARC puts *pet care products alone* at US$8.6bn in 2025 ([imarcgroup.com](https://www.imarcgroup.com/india-pet-care-products-market)), i.e. a sub-segment larger than the whole market. Discard those.

**Ability to pay — the core disqualifier.** Published Indian vet PMS pricing:

| Product | Price | Source |
|---|---|---|
| **Vetlify** | **₹1,000/mo** Basic (2 users), **₹2,000/mo** Pro (5 users) + ₹22,500 one-time registration | [vetlify.in](https://vetlify.in/) |
| **PetAladdin** | **₹999 / ₹1,999 / ₹2,999 per month**; extra doctor ₹499/mo | [petaladdin.com/pricing](https://petaladdin.com/pricing) |
| **Petofy OPHR** | **$20–24/mo** | [softwaresuggest.com](https://www.softwaresuggest.com/veterinary-software) |
| VETport (US, sells into India) | $199/mo listed | [vetport.com/pricing](https://www.vetport.com/pricing) |

**The Indian vet PMS band is ₹1,000–3,000/month (US$12–36).** The adjacent anchors are lower still: **Vyapar** GST billing from **₹699/year** ([x.vyaparapp.in/pricing](https://x.vyaparapp.in/pricing)); **Marg ERP** — the dominant Indian pharmacy software — is a **perpetual licence at ₹8,100–25,200 one-time plus ~₹3,500/yr AMC** ([itforsme.in](https://www.itforsme.in/pricing/marg-erp-india/)), and a pharmacy-heavy Indian buyer *expects* perpetual, not SaaS. Vet consultation: ₹500–2,500 private, ₹50 government ([hdfcergo.com](https://www.hdfcergo.com/blogs/general-insurance/dog-vet-costs-in-india-2025-a-comprehensive-guide-to-bills)); the largest chain, Vetic (65 clinics, 11 cities), runs **₹299 vet-at-home** ([vetic.in](https://vetic.in/)).

**E-invoicing — the wedge does not merely miss the buyer; it cannot reach them.**

- **Veterinary clinical services are GST-EXEMPT.** Entry 46 of Notification No. 12/2017-Central Tax (Rate) zero-rates "services by a veterinary clinic in relation to health care of animals or birds" — consultation, diagnostics, imaging, surgery, inpatient care, inpatient medicines (SAC 999311/999312/999313) ([taxguru.in](https://taxguru.in/goods-and-service-tax/veterinary-healthcare-services-gst-perspective.html); [casahuja.com](https://www.casahuja.com/2025/12/gst-classification-and-taxability.html)). Taxable: OP pharmacy 12%, grooming/boarding 18%.
- **GST registration threshold: ₹20 lakh for services.** ([cleartax.in](https://cleartax.in/s/gst-registration))
- **E-invoicing threshold: ₹5 crore AATO since 1 Aug 2023** (history: ₹500cr → ₹100cr → ₹50cr → ₹20cr → ₹10cr → ₹5cr) ([cleartax.in](https://cleartax.in/s/e-invoicing-gst); [gimbooks.com](https://www.gimbooks.com/blog/e-invoice-limit-in-india/)). A widely-blogged reduction to ₹2 crore from 1 Oct 2025 is **contradicted by current tax-portal pages** `[UNVERIFIED / conflicting — treat as not in force]`.
- **E-invoicing exempts nil-rated/exempt supplies and all B2C entirely** ([cleartax.in](https://cleartax.in/s/e-invoicing-gst)).

**So an Indian vet clinic would need >₹5 crore turnover *and* taxable B2B supplies to be in scope. Essentially none are. There is no compliance forcing-function to sell against, at all.** And becoming a GST Suvidha Provider is closed: it requires an India-registered company with **₹5 crore paid-up capital and ₹10 crore average 3-year turnover** ([indiafilings.com](https://www.indiafilings.com/learn/gst-suvidha-provider-gsp)).

**Payment and tax friction — worse for an Egyptian vendor than for almost any other origin.**

- ✅ **Good news: the Equalisation Levy is gone.** The 2% e-commerce/SaaS levy was **abolished 1 August 2024** ([india-briefing.com](https://www.india-briefing.com/news/india-to-abolish-2-percent-equalisation-levy-on-foreign-digital-companies-from-august-1-2024-33736.html/)); the 6% ad levy from 1 April 2025 ([business-standard.com](https://www.business-standard.com/industry/news/india-equalisation-levy-removed-tax-impact-2025-125040100810_1.html)).
- ❌ **OIDAR.** Since 1 Oct 2023, the exemption for supplies to unregistered recipients is withdrawn. B2B to a GST-registered buyer is reverse-charge (fine). **But selling to a non-registered recipient means you must register for GST in India from the first transaction, with no threshold, file GSTR-5A monthly, and appoint an Indian representative** ([india-briefing.com](https://www.india-briefing.com/news/oidar-compliance-india-gst-registration-ntor-gstr5a-digital-tax-43951.html/)). **A vet clinic whose output is GST-exempt and under ₹20 lakh is precisely such a recipient.** The exemption that makes your customer cheap to run makes you a monthly Indian tax filer.
- ❌ **Withholding.** The **India–Egypt (UAR) treaty contains no withholding rates for royalty, interest or dividend** — Articles 11/12/13 are blank on rates, so domestic rates apply: **royalty/FTS 20% under s.115A, effectively 21.84% for foreign companies** with surcharge and cess ([taxguru.in DTAA chart](https://taxguru.in/income-tax/countrywise-withholding-tax-rates-chart-dtaa.html); [azbpartners.com](https://www.azbpartners.com/bank/increase-in-domestic-tax-rate-on-royalty-and-fees-for-technical-services-impact-on-non-residents/)). Indian case law is favourable — the Supreme Court in *Engineering Analysis* (2021) held software licence payments are not royalty, and the Delhi HC extended this to standardised cloud in *CIT v. Amazon Web Services* — **but those wins ran through treaty articles that Egypt does not have.** Assume a 20%+ haircut unless the buyer's chartered accountant is unusually brave.
- ❌ **Per-payment paperwork.** Every remittance to a non-resident needs **Form 15CA**; above ₹5 lakh cumulative it needs **Form 15CB, a chartered accountant's certificate** ([incometax.gov.in](https://www.incometax.gov.in/iec/foportal/help/statutory-forms/popular-forms/form-15ca-um)). For a ₹2,000/month invoice.
- ❌ **Recurring cards break.** RBI requires e-mandate registration with AFA/3DS, 24-hour pre-debit notification, and additional factor authentication on every transaction above ₹15,000 — explicitly applying to non-India merchants charging Indian cards. Without a registered mandate, off-session payments are **declined** ([docs.stripe.com/india-recurring-payments](https://docs.stripe.com/india-recurring-payments)). No naive "enter card, bill monthly".
- Stripe lists India as **Preview** only ([stripe.com/global](https://stripe.com/global)).

**Competition.** Slashdot lists **115 veterinary software products** available in India ([slashdot.org](https://slashdot.org/software/veterinary/in-india/)). Indian-origin: Vetlify, PetAladdin, Petofy, Koko (GST billing + WhatsApp + multi-language), Vets and Care. Foreign entrants: VETport (with an Indian phone line), Digitail, ezyVet, IDEXX Neo. Below them, Marg ERP and Vyapar already deliver GST billing, pharmacy batch/expiry, inventory and accounting for ₹700–4,400/**year**.

**Every feature Aleefy would lead with in India — GST billing, WhatsApp, batch/expiry, multi-language — is table stakes at ₹1,000/month.**

### 7.2 BANGLADESH — disqualified on size, then again on payment

1. **~45 identifiable companion-animal clinics nationwide** (Dhaka 28, Sylhet 7, Mymensingh 3) ([amarpet.com](https://amarpet.com/blogs/vets-near-me)). Bangladesh Veterinary Council registrants are overwhelmingly poultry and dairy; the commonly quoted ~3,812 could not be verified `[UNVERIFIED — discard]`.
2. **Market: Tk 200 crore (~US$16m)** pet food and accessories, growing >20%/yr ([thedailystar.net](https://www.thedailystar.net/business/economy/news/market-pet-food-accessories-growing-3422306)). Vendor reports disagree by ~30×; discard.
3. **No wedge.** VAT 15%, mandatory registration at **BDT 3 crore (~US$246k)** ([taxdo.com](https://taxdo.com/resources/countries/ap/bangladesh)) — a vet clinic is far below it and out of EFD scope. The EFD system is a **closed single-vendor concession** (NBR contracted Genex Infosys as sole EFDMS operator; ~11,000 of a 60,000 target installed) ([thedailystar.net](https://www.thedailystar.net/business/economy/news/electronic-fiscal-device-60000-be-installed-dhaka-ctg-fy-3400661); [tbsnews.net](https://www.tbsnews.net/nbr/nbr-looks-alternatives-its-vat-machine-fails-boost-collection-923376)). **No open foreign-vendor accreditation route found.**
4. **Price anchor US$8–15/month** — PharmaPOS from ৳1,000/month ([pharmapos.bd](https://www.pharmapos.bd)); pharmacy POS from ৳3,000 one-time ([bdstall.com](https://www.bdstall.com/details/pharmacy-management-pos-software-159132/)).
5. **Payment is the hard stop, and the dollar crisis easing does not fix it.** Reserves have recovered past US$35bn ([newagebd.net](https://www.newagebd.net/post/economy/292183/forex-reserves-cross-35b-after-40-months)), but **FE Circular 38 (5 Oct 2025) caps an SME's total annual bona fide foreign current expenses — including software — at US$3,000/year**, with a card sub-limit around US$600; the US$40,000/yr window is **IT/software firms only** ([bb.org.bd PDF](https://www.bb.org.bd/mediaroom/circulars/fepd/oct052025fepd38e.pdf)). Individual online card purchases are capped at **US$300/transaction**, most BD debit cards are not internationally enabled by default, and **recurring monthly billing frequently fails at renewal** ([tbsnews.net](https://www.tbsnews.net/economy/banking/banks-cutting-credit-card-limits-foreign-currency-719490)). On top: **20% withholding** on royalty/licence/technical services to non-residents (s.119, Income Tax Act 2023) plus **15% reverse-charge VAT on imported services** ([taxsummaries.pwc.com](https://taxsummaries.pwc.com/bangladesh/corporate/other-taxes)), and **no Egypt–Bangladesh tax treaty** — Egypt is absent from NBR's 43-country DTAA list ([nbr.gov.bd](https://nbr.gov.bd/information-library/double-taxation-avoidance-agreement/eng)). **Full 20%, no relief.**

   On a US$30/month invoice: the clinic withholds 20% (you net US$24), self-accounts 15% import VAT (their real cost US$34.50), and burns AD-bank paperwork against a US$3,000/yr ceiling. Stripe does not support Bangladesh ([stripe.com/global](https://stripe.com/global)).

### 7.3 SRI LANKA — disqualified on size and price, not on FX

1. **No credible companion-animal clinic count.** DAPH runs **337 government veterinary offices** with a 900-approved/680-serving state cadre — livestock and public sector ([themorning.lk](https://www.themorning.lk/articles/AjDtULKVvnCWBvOtZ3Fv)). The SLVC register is searchable but publishes no total ([slvetcouncil.org/members](https://www.slvetcouncil.org/members)). Identifiable private companion-animal hospitals (PetVet, Pets V Care, Vets & Pets, Rover, City Pet) are **order-of-magnitude dozens, Colombo-concentrated**.
2. **Market: US$55.8m "Pet & Animal Supplies" 2025** ([statista.com](https://www.statista.com/outlook/cmo/pet-animal-supplies/sri-lanka)) — a **model, not a survey**. The only uncontradicted signal points the wrong way: **pet food imports fell 10.7% 2023→2024, −9.31% CAGR 2020–24** ([6wresearch.com](https://www.6wresearch.com/industry-report/sri-lanka-pet-food-market-outlook)). Shrinking.
3. **No wedge.** VAT 18%; registration threshold LKR 60m/yr, dropping to **LKR 36m/yr from 1 Apr 2026** ([ird.gov.lk](https://www.ird.gov.lk/en/Type%20of%20Taxes/SitePages/Value%20Added%20Tax%20(VAT).aspx)). **No e-invoicing mandate exists** — post-audit only, with a 2025–26 pilot (tea auction, garment exporters) and a B2C/POS phase announced with no date ([Thomson Reuters](https://europe.thomsonreuters.com/no/compliance/regulatory-updates/sri-lanka)). Nothing to sell against before ~2028.
4. **Price anchor US$2–4/month** — Hyper Selo mobile POS LKR 499/mo, desktop LKR 990/mo ([hyperselo.com](https://www.hyperselo.com)) `[figures from indexed listing; live pricing page 404s]`.
5. **FX is genuinely fine now** — the 2021 overseas card prohibition was relaxed in 2023 and banks removed overseas spending caps in March 2023; the remaining 2025 controls suspend Outward Investment Account *capital* transactions only, irrelevant to a subscription ([desaram.com](https://www.desaram.com/foreign-exchange-regulations-sri-lanka-outward-remittances-2025/)). **WHT 14%** on royalties and non-resident service fees ([bizadvisor.lk](https://bizadvisor.lk/handbook/guide-to-WHT-AIT)), with **no Egypt–Sri Lanka tax treaty** — Egypt is absent from Sri Lanka's ~44 DTAs ([taxadvisor.lk](https://www.taxadvisor.lk/tax/double-taxation)). Survivable. It just doesn't matter, because the market is dozens of clinics at US$2–4/month.

### 7.4 What South Asia adds to the picture

India is the reason to take the "no" seriously rather than treat it as timezone-driven pessimism. **India has the best timezone in the entire region and workable English, and it is still the clearest reject** — because the price ceiling is US$12–36/month, 115 competing products already exist, the compliance wedge is legally impossible (vet services are GST-exempt), and the tax plumbing for an *Egyptian* vendor specifically is punitive (no treaty royalty article → 20–21.84% unrelieved withholding, plus mandatory GST registration with no threshold and monthly filings).

**Timezone was never the binding constraint. Price and incumbency are.**

---

## 8. Rest of Southeast Asia — Vietnam and Thailand

### 8.1 VIETNAM — disqualified

**Clinic count:** no official register found. The Vietnamese vet PMS **VetGo claims "3000+" veterinary clinics *and pet shops*** as customers ([vetgo.vn](https://vetgo.vn/)) — a conflated figure, useful only as an upper bound on one vendor's base. A Ken Research page asserting "over 5,500 clinics" also values a "Vietnam Veterinary Rehabilitation Services Market" at **USD 165m** — roughly 1.75× the entire Vietnamese pet-care market per Euromonitor. **Internally inconsistent; treat as junk** ([kenresearch.com](https://www.kenresearch.com/vietnam-veterinary-rehabilitation-services-market)).

**Market size (the best-measured in the region):** pet care **USD 54.5m (2020) → USD 94.2m (2025 projected), CAGR 5.7%**; dogs 3.4m, cats 3.4m (2020) ([petfair-sea.com, Euromonitor/Mordor](https://petfair-sea.com/asia-markets/southeast-asia-pet-market/vietnam-pet-market/)). Roughly **85% of that is pet food**, so the veterinary services slice is plausibly **USD 10–20m nationally**. Household pet ownership 67% (2023) → 74.5% (2024) ([b-company.jp, citing TGM Statbox](https://b-company.jp/vietnams-pet-care-products-services-market-key-trends-and-implications-for-foreign-investors/)).

**Ability to pay:** Vietnamese SMB SaaS anchors at roughly **USD 4–15/seat/month** (MISA eShop from ~VND 100,000/month; KiotViet from VND 6,000/day) `[PARTIALLY UNVERIFIED — vendor pages returned 403]`. VetGo publishes no price.

**E-invoicing — a real mandate, already occupied:** Decree 123/2020 made e-invoicing mandatory from 1 July 2022; **Decree 70/2025, effective 1 June 2025**, requires business households and individual businesses with **annual revenue ≥ VND 1 billion (~USD 38,800)** to issue e-invoices from **POS cash registers electronically connected to the General Department of Taxation**, covering retail, F&B, hotels, transport and "other personal services" ([vietnam-briefing.com](https://www.vietnam-briefing.com/news/decree-70-key-amendments-to-invoice-regulations-in-vietnam.html/); [kpmg.com](https://kpmg.com/us/en/taxnewsflash/news/2025/04/tnf-vietnam-amendments-to-regulations-on-electronic-invoices.html)). Invoices are XML, digitally signed, tax-authority-coded, retained 10 years ([edicomgroup.com](https://edicomgroup.com/electronic-invoicing/vietnam)). **Transmission runs directly or through an *authorised* e-invoicing service provider** — no public list, no published open API, and no statement that a foreign vendor may integrate directly `[UNVERIFIED, but every practitioner source describes going through a local licensed provider: Viettel, MISA meInvoice, VNPT, BKAV]`. **VetGo already ships Viettel e-invoice integration.**

**Language:** EF score 500, "Moderate". Every Vietnamese vet PMS found (VetGo, [Faceworks](https://faceworks.vn/phan-mem-quan-ly-phong-kham-thu-y/), [VietMIS eHealth Thú y](https://www.vietmis.com/ehealth-phong-kham.html)) is **Vietnamese-only**, and VetGo explicitly markets to clinic staff who are *not* tech-savvy. English-only is a non-starter.

**Rails — actively hostile:** foreign digital suppliers must register with the Vietnamese tax authority **from the first sale, with no threshold**, via the GDT foreign-supplier portal, filing quarterly ([fonoa.com](https://www.fonoa.com/resources/country-tax-guides/vietnam/tax-on-digital-services)). VAT **10% from July 2025** ([vatabout.com](https://vatabout.com/vietnam-ecommerce-vat-rules-2025-2026)). **If you don't register, your Vietnamese customers and their banks must withhold VAT and CIT on your behalf** — making you a compliance problem for every customer you sign. The **Vietnam–Egypt tax treaty is signed but not in force** ([taxsummaries.pwc.com](https://taxsummaries.pwc.com/vietnam/corporate/withholding-taxes)), so no treaty relief. The new **Law on E-Commerce (adopted 10 Dec 2025, effective 1 July 2026)** pushes foreign cross-border platforms toward a Vietnamese legal entity or local authorised representative `[scope for pure B2B SaaS unclear]`.

### 8.2 THAILAND — disqualified

**Clinic count:** the Department of Livestock Development registers สถานพยาบาลสัตว์ (animal treatment establishments) but publishes per-region documents with **no aggregate** ([vetservice.dld.go.th](https://vetservice.dld.go.th/index.php/th/sthan-phyabal-satw/khx-cad-tang-danein-kar-sthan-phyabal-satw)). Best proxy: **DRX Veterinary System claims 1,300+ Thai veterinary hospitals and clinics** as customers ([drxsystem.com](https://drxsystem.com/)). So the national universe is plausibly low thousands, **with one vendor already holding a large share of it**.

**Market size:** KResearch (2025) — **5.38m pets (3.45m dogs, 1.94m cats), +6% YoY; pet food THB 46bn, +12%; total pet industry THB 250bn, +5.8%** ([nationthailand.com](https://www.nationthailand.com/news/general/40049540)). A separate Hypercube/TPIA dataset gives 8.9m dogs, 3.3m cats and a **USD 1.06bn total market (2019)** with pet services at USD 337.8m ([petfair-sea.com](https://petfair-sea.com/asia-markets/southeast-asia-pet-market/thailand-pet-market/)). **The two datasets use different definitions — do not stack them.** Directionally, Thailand's pet market is roughly **10× Vietnam's**.

**Ability to pay — the best-evidenced in the region:**

| Vendor | Plan | THB/year | ≈ USD/month |
|---|---|---|---|
| [Vetpresso](https://vetpresso.com/price) | Basic (1–2 staff, 1 branch) | 12,000 | ~28 |
| Vetpresso | Standard (3–6) | 49,000 | ~115 |
| Vetpresso | Premium (7–15) | 149,000 | ~350 |
| [Vettale](https://vettale.com/pricing/) | Starter (3 users) | 12,000 | ~28 |
| Vettale | Plus (5 users) | 16,000 | ~37 |
| Vettale | Pro (15 users) | 36,000 | ~85 |

Thai SMB accounting SaaS for comparison: **FlowAccount THB 1,990–5,490/year** ([flowaccount.com](https://flowaccount.com/en/pricing)). Procedure prices: rabies vaccination THB 300–600, neuter THB 1,200–4,000, ultrasound THB 600–1,500 ([thailandstarterkit.com](https://www.thailandstarterkit.com/lifestyle/bangkok-veterinarians/)).

**E-invoicing — there is no wedge at all.** Thailand's **e-Tax Invoice & e-Receipt is voluntary**, open to any VAT-registered business since 2012, post-audit rather than clearance; XML per ETDA Standard 3-2560, digitally signed with a certificate from an RD-approved CA, transmitted to the Revenue Department by the 15th of the following month ([edicomgroup.com](https://edicomgroup.com/electronic-invoicing/thailand); [vatupdate.com](https://www.vatupdate.com/2026/07/09/thailand-e-invoicing-e-reporting-country-booklet/)). **No regulatory forcing function to sell against.**

**Language — hard blocker:** EF score **402, "Very low proficiency"** — the lowest tier of the nine. Every Thai vet PMS is Thai-language and **LINE-integrated** for client reminders (Vetpresso, Vettale, DRX, [VETMANAGE](https://vetmanage.co/), [Aristo Petshop](https://www.aristosoft.org/petshop/)). LINE — not WhatsApp, not SMS — is the customer channel. That is a product requirement, not a translation task. Aleefy's WhatsApp integration is the wrong channel for Thailand.

**Rails — ironically the friendliest tax regime found:** Thailand's VAT for Electronic Service (VES) requires registration only above **THB 1.8m/year (~USD 50,000)** of sales to non-VAT-registered Thai customers, 7% VAT, effective 1 Sept 2021 ([rd.go.th PDF](https://www.rd.go.th/fileadmin/download/eService.pdf)); the RD's own registration instructions indicate **no local agent is required** ([eservice.rd.go.th PDF](https://eservice.rd.go.th/rd-ves-web/assets/pdf/registration_instruction.pdf)) `[CONTESTED — one RD guide reads the other way; verify with a Thai adviser]`. B2B sales to VAT-registered clinics fall outside VES via reverse charge (PP.36). **Thailand is a supported Stripe country — but Egypt is not, so this doesn't help the Egyptian seller directly** ([stripe.com/global](https://stripe.com/global)).

**Thailand fails on language, competition and the total absence of a compliance wedge — not on money.**

---

## 9. Cross-cutting: the e-invoicing wedge does not survive contact with Asia

This is the most important finding in the document, because e-invoicing is Aleefy's stated differentiator.

In Egypt and the Gulf the wedge works because the mandate reaches down to small businesses and integration is a genuine burden. In Asia, tested against all nine countries:

- **Seven of nine exclude small clinics by threshold, or are voluntary, or are legally inapplicable** — Malaysia RM1m exemption; Indonesia IDR 4.8bn PKP threshold; Philippines PHP 3m micro exemption plus a PHP 1bn Phase 1; Thailand voluntary; **India, where veterinary clinical services are GST-exempt and e-invoicing excludes nil-rated and B2C supplies outright**; Bangladesh's BDT 3 crore VAT threshold plus a single-vendor closed EFD concession; Sri Lanka, which has no mandate at all before roughly 2028.
- **One (Vietnam) reaches small businesses but requires a locally authorised provider**, and the local vet PMS incumbent already integrates with Viettel.
- **One (Pakistan) genuinely reaches every registered person with an open, free government API** — and is the country where customers can least easily pay you.

Where the wedge is closed to foreigners by capital requirement, the numbers are consistent and prohibitive: **Pakistan licensed integrator PKR 10m paid-up capital and a Pakistani company; India GSP ₹5 crore paid-up capital plus ₹10 crore average turnover and an Indian company; Bangladesh EFD a sole-operator concession; Vietnam a locally authorised provider.** In every case the compliance layer is reserved for locally-capitalised entities.

There is also a structural point worth stating plainly: **where an e-invoicing mandate exists and bites, local vendors ship compliance within a year.** kumoVet has LHDN e-invoicing. Kreloses has LHDN and SATUSEHAT. VetGo has Viettel. Compliance is a race a foreign two-person team starts late and loses, because the local vendor is in the same timezone as the tax authority's helpdesk.

---

## 10. Cross-cutting: what "no local presence" costs specifically in Asia

Beyond the timezone arithmetic in §1.2:

- **Payment collection.** Stripe supports **Malaysia and Thailand**; lists **India and Indonesia as Preview**; and **does not list the Philippines, Pakistan or Vietnam** ([stripe.com/global](https://stripe.com/global)). Egypt is not supported at all, so Aleefy needs a merchant-of-record regardless — Paddle appears open to Egyptian sellers and Lemon Squeezy explicitly supports Egyptian bank payouts (sourced in `03_PRICING_AND_ECONOMICS.md`). An MoR solves the foreign-VAT registration problem in Thailand, Malaysia and Indonesia by absorbing it — but **it does not solve Vietnam's register-from-first-sale rule cleanly, and it cannot solve Pakistan's outward-remittance blockage**, which sits on the customer's side of the transaction, not yours.
- **Local channel.** Every one of these markets sells clinic software through relationships: distributor reps who also sell the ultrasound machine, veterinary association conferences, WhatsApp/LINE/Zalo groups. None of that is reachable from Cairo without a person on the ground.
- **The channel is the wrong one.** Aleefy's WhatsApp integration is a strength in Egypt and the Gulf. In Thailand the channel is **LINE**; in Vietnam it is **Zalo**. Both would need building. WhatsApp is dominant in Malaysia, Indonesia and Pakistan `[UNVERIFIED — not separately sourced in this pass]`.

---

## 11. Is Asia better as a source of engineering or partnership than as a market?

Assessed separately, because it is a genuinely different question — and the answer is more interesting than the market answer.

### 11.1 As a source of cheap engineering — no

- Aleefy's own economics model a mid-level Egyptian developer at **~30,000 EGP/month (~USD 600–650/month)** (`03_PRICING_AND_ECONOMICS.md` §T5) — and the doc itself flags that this figure is an assumption, not a citation.
- **Egypt is already at or below Indian, Vietnamese and Philippine developer cost.** `[UNVERIFIED — no fetchable rate table was obtainable this session; Accelerance, Codica, Daxx and Arc all returned 404/301/522. This should be verified before any hiring decision.]`
- More decisively: **the team has no capital.** The binding constraint is not the hourly rate of a developer somewhere else; it is that there is no money to pay any developer anywhere. Offshoring to a cheaper country than Egypt solves a problem the team does not have.

### 11.2 As a source of partnership — mostly no, and the traffic is going the other way

The one thing this research surfaced that genuinely matters strategically is **not an Asian opportunity but an Asian threat**:

- **Happy Pet Tech**, an **Indian** vet clinic software vendor, is expanding into **UAE (Dubai), Australia, the Philippines and Thailand**, and sells in Dubai at **AED 149/month or AED 1,499/year per branch** (~USD 41/month) with WhatsApp integration ([happypet.tech](https://www.happypet.tech/vet-clinic-software), [happypet.tech/pricing](https://www.happypet.tech/pricing)).
- **kumoVet** (Malaysia) already operates in **11 countries** ([kumovet.com](https://kumovet.com/solutions/vet-clinic-management-system/)).
- **Kreloses** markets itself as built for "Asian businesses" across multiple countries ([kreloses.com/vet](https://kreloses.com/vet)).

**Read that Dubai price again.** An Indian vendor is selling a WhatsApp-integrated vet ERP into the Gulf at USD 41/month per branch. That is a direct competitive data point for Aleefy's *own* second market, and it is a more actionable finding than anything on the sell-into-Asia side. Indian vendors have the cost base to price the Gulf aggressively and the English capability to support it, and Dubai is only 1–2 hours from Indian time.

**The legitimate partnership shapes, honestly assessed:**

| Shape | Verdict |
|---|---|
| Pakistani reseller/white-label with local entity | The only one that makes structural sense — a Pakistani company with the PKR 10m capital could hold licensed-integrator status, bill in PKR, handle Urdu support and solve the remittance problem. **But it gives away most of the margin in a market whose size cannot be measured.** |
| Malaysian/Indonesian reseller | Pointless — kumoVet and Kreloses are already there and cheaper |
| Indian dev shop as capacity | No — no capital, and Egypt is not more expensive |
| Reselling *someone else's* Asian product into Egypt/Gulf | Not evaluated here, but note it is the direction the market is already flowing |

**The defensive conclusion is more valuable than the offensive one: Asia is best understood as the source of Aleefy's future Gulf competition, and worth monitoring for that reason rather than entering.**

---

## 12. What would have to change for the answer to become yes

Stated so the conclusion is falsifiable rather than merely pessimistic.

**For Pakistan (the only live candidate):**
1. A credible, sourced count of companion-animal clinics in Karachi, Lahore, Islamabad and Faisalabad showing **500+ addressable practices**. Today this number does not exist.
2. Evidence that those clinics are **sales-tax registered** and therefore actually in scope of the FBR mandate.
3. A **local partner or entity** able to bill in PKR — this solves the remittance blockage, the Urdu support burden and the channel problem in one move, and is a precondition, not an optimisation.
4. Evidence that a Pakistani clinic will pay **USD 20–40/month equivalent** in PKR, sustained through devaluation.

**For any of the others:** the language and the timezone would both have to change, which they will not. Malaysia and the Philippines fail on market size and incumbency even with English; Indonesia, Vietnam and Thailand fail on language before anything else is considered.

**A third person, resident in the target country, would change the analysis for exactly one country — Pakistan.** Everywhere else, adding a person does not fix a 650-clinic market or a USD 32/month incumbent.

---

## 13. Is Asia worth it — yes or no

**No.**

Not one of the nine countries is worth this team's attention as a market to sell into, and the reasoning is not close in any single case:

- **Thailand, Vietnam, Indonesia** — eliminated by language before economics are reached. Thai (EF 402, "Very low"), Vietnamese and Bahasa are all mandatory for clinic staff, all require ongoing support in-language, and all have entrenched local-language incumbents. Thailand additionally has **no e-invoicing mandate at all**, and its client-communication channel is LINE, not WhatsApp.
- **Malaysia** — English works, clinics genuinely pay, rails are the easiest of the nine. Eliminated by **size and incumbency**: ~650 practices total, and kumoVet is a functionally identical local product at **USD 32–58/month** with LHDN e-invoicing already shipped. The whole national market at those prices is USD 250–450k of ARR for all vendors combined.
- **Philippines** — English works. Eliminated by the **worst timezone gap in the set** (clinic opens at 03:00 Cairo) and by VetCloud, which claims more clinics than can be counted nationally, on an unlimited-users/storage/SMS bundle.
- **India** — the most instructive rejection, because it has the **best timezone in the region** (IST +3.5h, a 6.5-hour overlap) and workable English, and still fails outright. The price ceiling is **₹1,000–3,000/month (US$12–36)** against 115 competing products; **veterinary clinical services are GST-exempt**, so the e-invoicing wedge is not merely out of reach but legally inapplicable; and the tax plumbing is punitive for an *Egyptian* vendor specifically — the **India–Egypt treaty has no royalty article**, so unrelieved withholding of **20–21.84%** applies, on top of mandatory OIDAR GST registration with **no threshold**, monthly GSTR-5A filings, an Indian representative, Form 15CA/15CB on every remittance, and RBI e-mandate rules that break naive recurring card billing.
- **Bangladesh** — ~45 identifiable companion-animal clinics; **20% unrelieved withholding** (no Egypt treaty) plus 15% import VAT; and an SME outward-payment ceiling of **US$3,000/year** with cards that routinely fail on renewal.
- **Sri Lanka** — cleanest FX story of the three and survivable 14% withholding, but the market is dozens of clinics, the local price anchor is **US$2–4/month**, pet food imports are **shrinking**, and there is no e-invoicing mandate to sell against before ~2028.
- **Pakistan** — the closest thing to a candidate, and the honest answer is still no. It has the **best timezone in Asia** (7-hour overlap), the **only e-invoicing mandate that actually reaches small businesses with a free open government API** (PRAL DI API v1.12), and the **only language where Aleefy's existing Arabic-script RTL work transfers** (Urdu). It fails on money from both directions: the market size cannot be measured from any public source, and **SBP outward-remittance rules mean a willing Pakistani clinic may be structurally unable to pay a foreign vendor**. Fixing that requires a local partner entity — which is capital and a third person, neither of which exists.

**The structural reason all of this fails is one sentence:** Aleefy's differentiator is compliance-driven, and in Asia the e-invoicing mandates either don't reach veterinary clinics or are already shipped by a local vendor who is in the customer's timezone and speaks the customer's language.

**And on the second question — market or partnership source?** Neither, but if forced: **Asia is more useful as intelligence than as either.** Egypt is already cost-competitive with Asian engineering and the team has no capital to hire with, so the offshore-engineering angle is moot. The genuinely actionable finding is defensive: **Indian and Malaysian vet-software vendors are already selling into the Gulf** — Happy Pet Tech at **AED 149/month per branch in Dubai**, with WhatsApp integration, from a lower cost base and a 1.5-hour timezone gap. That is a competitor entering Aleefy's own second market. Watching it is worth more than entering theirs.

**Recommendation: close the Asia question. Do not revisit unless a Pakistani co-founder or partner entity materialises, in which case reopen Pakistan only.**

---

## Appendix A — Source list

**Language / proficiency**
- EF English Proficiency Index 2025 — https://en.wikipedia.org/wiki/EF_English_Proficiency_Index · https://www.ef.com/wwen/epi/

**Pakistan**
- Pakistan Veterinary Medical Council — https://en.wikipedia.org/wiki/Pakistan_Veterinary_Medical_Council · https://pvmc.gov.pk/
- Clinic proxy (scrape) — https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-pakistan
- Directory — https://www.veterinby.com/veterinary-clinic-pakistan/
- Pet market (paywalled teaser, no figures) — https://www.6wresearch.com/industry-report/pakistan-pet-care-market
- E-invoicing phased mandate — https://profit.pakistantoday.com.pk/2025/08/02/fbr-mandates-phased-integration-of-electronic-invoicing-system-for-sales-tax-registered-entities/
- SRO 69(I)/2025 and SRO 1852(I)/2025 analysis — https://rtcsuite.com/pakistans-digital-tax-evolution-the-e-invoicing-notification-that-will-reshape-compliance/ · https://rtcsuite.com/pakistan-extends-e-invoicing-integration-deadlines-for-taxpayers-under-rule-150q/
- PRAL DI API technical spec — https://download1.fbr.gov.pk/Docs/20257301172130815TechnicalDocumentationforDIAPIV1.12.pdf
- PRAL DI user manual — https://download1.fbr.gov.pk/Docs/20254171643756444DI-User-Manual.pdf
- Integration walkthrough / static IP requirement — https://logiclayer.com.pk/blog/how-to-integrate-fbr-digital-invoicing-api-pral-guide
- Licensed integrator requirements — https://difbr.pk/blog/pakistan-e-invoicing-integrator-licensing-fbr-rules-33m-v · https://tmrconsult.com/fbr-licensed-integrator-in-pakistan-for-digital-invoicing/
- Provincial services tax — https://conseric.pk/punjab-sales-tax-on-services/ · https://www.srb.gos.pk/srb/taxable-services/
- SBP outward remittance — https://tencoconsulting.com/freelance-payments-pakistan/ · https://www.sbp.org.pk/fe_manual/chapters/chapter10.htm

**Malaysia**
- Clinic and vet counts — https://www.malaysiakini.com/letters/679109
- MVC premises registration — https://www.mvc.gov.my/registration
- kumoVet product — https://kumovet.com/solutions/vet-clinic-management-system/
- kumoVet pricing — https://kumovet.com/pricing/
- Kreloses — https://kreloses.com/vet · https://kreloses.com/home/price
- MyInvois phases and penalties — https://www.cleartax.com/my/en/e-invoicing-malaysia
- RM1m threshold increase — https://www.vatupdate.com/2025/12/18/malaysia-raises-e-invoicing-exemption-threshold-to-rm1-million-key-changes-for-2026-rollout/ · https://sovos.com/regulatory-updates/vat/malaysia-mandatory-e-invoicing-exemption-threshold-increased/ · https://www.globalvatcompliance.com/globalvatnews/malaysia-e-invoicing-myinvois-rm1m-rm5m-deferred-2027/
- Vet consultation fees — https://www.oyen.my/post/vet-cost-malaysia-2026 · https://www.trustytails.vet/blog/vet-visit-cost-kl-malaysia-2026

**Indonesia**
- Veterinary profession — https://en.wikipedia.org/wiki/Veterinary_medicine_in_Indonesia
- Government clinic dataset (metadata only) — https://data.go.id/dataset/dataset/jumlah-eksisting-rumah-sakit-hewan-klinik-hewan-ambulatori-praktik-dokter-hewan-mandiri-puskesw3
- Clinic proxy (scrape) — https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-indonesia
- Pet market estimates — https://market.us/report/indonesia-pet-care-market/ · https://www.marknteladvisors.com/research-library/pet-care-market-indonesia · https://www.futuremarketinsights.com/reports/indonesia-pet-care-market
- e-Faktur / Coretax — https://www.cleartax.com/id/en/e-invoicing-indonesia · https://xpnd.co.id/blogs/e-faktur-indonesia-coretax-2026/ · https://edicomgroup.com/electronic-invoicing/indonesia · https://www.letsmoveindonesia.com/tax-in-indonesia-guide-to-e-faktur-system-for-pkp-businesses/
- Vet costs — https://dearpetz.com/blog/pet-vet-costs-indonesia-id

**Philippines**
- BAI registered clinics 2019 — https://www.scribd.com/document/465936597/Registered-Veterinary-Clinics-and-Hospitals-as-of-October-2019
- Clinic proxy (scrape) — https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-philippines
- Metro Manila clinics and consultation fees — https://www.clinicfinderph.com/blog/best-vet-clinics-metro-manila · https://www.clinicfinderph.com/blog/best-vet-clinics-quezon-city
- VetCloud — https://vetcloudsoftware.org/ · https://www.capterra.com/p/147757/VetCloud/alternatives/
- Pet statistics aggregator — https://gitnux.org/philippines-pet-industry-statistics/
- Veterinary medicine market (livestock-weighted) — https://www.kenresearch.com/philippines-veterinary-medicine-market
- BIR EIS — https://rtcsuite.com/e-invoicing-philippines/ · https://www.vatupdate.com/2025/10/17/bir-e-invoicing-philippines-2026-compliance-guide-for-electronic-invoice-system-eis/ · https://www.comarch.com/trade-and-services/data-management/legal-regulation-changes/philippines-e-invoicing-mandate-extended-new-2026-compliance-deadline/

**Vietnam**
- VetGo — https://vetgo.vn/ · Faceworks — https://faceworks.vn/phan-mem-quan-ly-phong-kham-thu-y/ · VietMIS — https://www.vietmis.com/ehealth-phong-kham.html
- Pet market — https://petfair-sea.com/asia-markets/southeast-asia-pet-market/vietnam-pet-market/ · https://b-company.jp/vietnams-pet-care-products-services-market-key-trends-and-implications-for-foreign-investors/
- Decree 70/2025 — https://www.vietnam-briefing.com/news/decree-70-key-amendments-to-invoice-regulations-in-vietnam.html/ · https://kpmg.com/us/en/taxnewsflash/news/2025/04/tnf-vietnam-amendments-to-regulations-on-electronic-invoices.html
- E-invoice technical — https://edicomgroup.com/electronic-invoicing/vietnam
- Foreign supplier tax — https://www.fonoa.com/resources/country-tax-guides/vietnam/tax-on-digital-services · https://vatabout.com/vietnam-ecommerce-vat-rules-2025-2026 · https://taxsummaries.pwc.com/vietnam/corporate/withholding-taxes
- Discredited clinic/market claim — https://www.kenresearch.com/vietnam-veterinary-rehabilitation-services-market

**Thailand**
- DLD establishment register — https://vetservice.dld.go.th/index.php/th/sthan-phyabal-satw/khx-cad-tang-danein-kar-sthan-phyabal-satw
- DRX — https://drxsystem.com/ · Vetpresso — https://vetpresso.com/price · Vettale — https://vettale.com/pricing/ · VETMANAGE — https://vetmanage.co/ · Aristo — https://www.aristosoft.org/petshop/
- Pet market — https://www.nationthailand.com/news/general/40049540 · https://petfair-sea.com/asia-markets/southeast-asia-pet-market/thailand-pet-market/
- Procedure prices — https://www.thailandstarterkit.com/lifestyle/bangkok-veterinarians/
- e-Tax Invoice (voluntary) — https://edicomgroup.com/electronic-invoicing/thailand · https://www.vatupdate.com/2026/07/09/thailand-e-invoicing-e-reporting-country-booklet/
- VES — https://www.rd.go.th/fileadmin/download/eService.pdf · https://eservice.rd.go.th/rd-ves-web/assets/pdf/registration_instruction.pdf · https://www.bdo.global/en-gb/microsites/tax-newsletters/indirect-tax-news/issue-3-2021/thailand-foreign-providers-of-digital-services-covered-by-vat-and-7-vat-rate-extended
- SMB SaaS anchor — https://flowaccount.com/en/pricing

**India**
- VCI registered practitioners — https://www.pib.gov.in/newsite/PrintRelease.aspx?relid=147765 · https://vci.dahd.gov.in/ivpr
- Mumbai bottom-up clinic count — https://www.vin.com/apputil/content/defaultadv1.aspx?id=8896947&pid=22915
- Clinic proxy (scrape) — https://rentechdigital.com/smartscraper/business-report-details/list-of-animal-hospitals-in-india
- Companion-animal entry rate / vet healthcare market — https://www.mordorintelligence.com/industry-reports/india-veterinary-healthcare-market-industry
- Pet market (Redseer) — https://www.consultancy.in/news/4276/indias-pet-care-market-to-see-steady-growth-to-7-billion-market · https://www.india-briefing.com/news/indias-pet-care-economy-2025-an-overview-37234.html/
- Contradicting press-release figure — https://www.imarcgroup.com/india-pet-care-products-market
- Vet software pricing — https://vetlify.in/ · https://petaladdin.com/pricing · https://www.softwaresuggest.com/veterinary-software · https://www.vetport.com/pricing · https://slashdot.org/software/veterinary/in-india/ · https://koko.vet/blogs/veterinary-clinic-management-software-in-india-complete-guide.html
- Adjacent SMB software anchors — https://x.vyaparapp.in/pricing · https://www.itforsme.in/pricing/marg-erp-india/ · https://technologycounter.com/products/practo-ray
- Vet consultation fees / largest chain — https://www.hdfcergo.com/blogs/general-insurance/dog-vet-costs-in-india-2025-a-comprehensive-guide-to-bills · https://vetic.in/
- **Veterinary services GST-exempt (Entry 46, Notification 12/2017)** — https://taxguru.in/goods-and-service-tax/veterinary-healthcare-services-gst-perspective.html · https://www.casahuja.com/2025/12/gst-classification-and-taxability.html
- GST registration and e-invoicing thresholds — https://cleartax.in/s/gst-registration · https://cleartax.in/s/e-invoicing-gst · https://www.gimbooks.com/blog/e-invoice-limit-in-india/
- GSP capital requirements — https://www.indiafilings.com/learn/gst-suvidha-provider-gsp
- Equalisation Levy abolition — https://www.india-briefing.com/news/india-to-abolish-2-percent-equalisation-levy-on-foreign-digital-companies-from-august-1-2024-33736.html/ · https://www.business-standard.com/industry/news/india-equalisation-levy-removed-tax-impact-2025-125040100810_1.html
- OIDAR registration for non-registered recipients — https://www.india-briefing.com/news/oidar-compliance-india-gst-registration-ntor-gstr5a-digital-tax-43951.html/ · https://taxguru.in/goods-and-service-tax/gst-oidar-services-foreign-firms-oct-1-2023.html
- India–Egypt treaty has no royalty rate; s.115A 20% — https://taxguru.in/income-tax/countrywise-withholding-tax-rates-chart-dtaa.html · https://www.azbpartners.com/bank/increase-in-domestic-tax-rate-on-royalty-and-fees-for-technical-services-impact-on-non-residents/
- Software-as-business-income case law — https://www.indialawoffices.com/legal-articles/no-tds-on-use-of-foreign-software · https://taxguru.in/income-tax/cloud-service-payments-taxable-royalty-due-transfer-ip-rights-sc.html
- Form 15CA/15CB — https://www.incometax.gov.in/iec/foportal/help/statutory-forms/popular-forms/form-15ca-um · https://www.xflowpay.com/blog/what-is-form-15ca-and-15cb
- RBI e-mandate / recurring payments — https://docs.stripe.com/india-recurring-payments

**Bangladesh**
- Companion-animal clinic directory — https://amarpet.com/blogs/vets-near-me
- Market size — https://www.thedailystar.net/business/economy/news/market-pet-food-accessories-growing-3422306
- VAT thresholds — https://taxdo.com/resources/countries/ap/bangladesh · https://rakibhassan.eu/vat-rate-bangladesh-2025-guide/
- EFD sole-operator concession — https://www.thedailystar.net/business/economy/news/electronic-fiscal-device-60000-be-installed-dhaka-ctg-fy-3400661 · https://www.tbsnews.net/nbr/nbr-looks-alternatives-its-vat-machine-fails-boost-collection-923376
- Local software pricing — https://www.pharmapos.bd · https://www.bdstall.com/details/pharmacy-management-pos-software-159132/
- Reserves recovery — https://www.newagebd.net/post/economy/292183/forex-reserves-cross-35b-after-40-months
- **FE Circular 38 (5 Oct 2025), US$3,000/yr SME ceiling** — https://www.bb.org.bd/mediaroom/circulars/fepd/oct052025fepd38e.pdf
- Card limits / recurring failures — https://www.tbsnews.net/economy/banking/banks-cutting-credit-card-limits-foreign-currency-719490
- Withholding and import VAT — https://taxpertbd.com/tds-rates-chart-fy-2025-26/ · https://taxsummaries.pwc.com/bangladesh/corporate/other-taxes
- No Egypt DTAA — https://nbr.gov.bd/information-library/double-taxation-avoidance-agreement/eng

**Sri Lanka**
- DAPH offices and state cadre — https://www.themorning.lk/articles/AjDtULKVvnCWBvOtZ3Fv · https://www.slvetcouncil.org/members
- Market model — https://www.statista.com/outlook/cmo/pet-animal-supplies/sri-lanka
- Pet food imports declining — https://www.6wresearch.com/industry-report/sri-lanka-pet-food-market-outlook
- VAT thresholds — https://www.ird.gov.lk/en/Type%20of%20Taxes/SitePages/Value%20Added%20Tax%20(VAT).aspx · https://bpc.lk/whats-changing-under-vat-sscl-from-1-april-2026/
- No e-invoicing mandate — https://europe.thomsonreuters.com/no/compliance/regulatory-updates/sri-lanka
- Local POS pricing — https://www.hyperselo.com · https://possrilanka.com
- FX relaxation — https://www.desaram.com/foreign-exchange-regulations-sri-lanka-outward-remittances-2025/ · https://www.dfe.lk
- WHT and absence of Egypt DTA — https://bizadvisor.lk/handbook/guide-to-WHT-AIT · https://www.taxadvisor.lk/tax/double-taxation

**Cross-cutting**
- Stripe country availability — https://stripe.com/global
- Indian vendor entering the Gulf — https://www.happypet.tech/vet-clinic-software · https://www.happypet.tech/pricing
- Egypt-side payment rails and developer cost anchor — `platform/docs/market/03_PRICING_AND_ECONOMICS.md`

---

## Appendix B — Items marked UNVERIFIED

| Item | Status |
|---|---|
| Pakistan — PVMC registered veterinarian count | No public figure found |
| Pakistan — companion-animal clinic count | No reliable source; "low hundreds" is an inference |
| Pakistan — pet care market size | No usable public figure; 6W paywalled, Statista has no PK data |
| Pakistan — 50% regulatory duty on imported pet food (Finance Bill 2024) | From search index; primary text not fetched |
| Pakistan — vet consultation fees | Not found |
| Pakistan — local vet software / competition | None found; absence of evidence, not evidence of absence |
| Pakistan — share of vet clinics that are sales-tax registered | Not found |
| Malaysia — pet care market size | Not sourced (search budget exhausted) |
| Malaysia — whether MDEC accreditation is required for a foreign vendor to use the MyInvois API directly | Not stated in sources |
| Indonesia — companion-animal clinic count | Government dataset publishes metadata only |
| Indonesia — pet market size | 4.6× spread between vendors; all press-release tier |
| Indonesia — local vet PMS pricing | Not sourced |
| Philippines — VetCloud actual PHP pricing | Only a third-party £99/month listing, likely an artefact |
| Philippines — whether a foreign vendor's system can obtain EIS Certification on a taxpayer's behalf | Not stated in sources |
| Vietnam — list of authorised e-invoice providers / open API availability | No public list found |
| Vietnam — scope of the 2026 E-Commerce Law for pure B2B SaaS | Unclear |
| Vietnam — MISA/KiotViet pricing | Vendor pages returned 403; figures from search index |
| Vietnam / Thailand — vet consultation fee | Not found |
| Thailand — whether a local agent is required for VES registration | **CONTESTED** — RD sources read both ways; verify with a Thai adviser |
| Thailand — DRX pricing | Pricing page is an image; no THB figures extractable |
| India — companion-animal clinic count | **Extrapolated** from one 2018 Mumbai paper (~120 clinics). Nobody publishes a national figure |
| India — reduction of e-invoicing threshold to ₹2 crore from 1 Oct 2025 | **CONFLICTING** — asserted by blogs, contradicted by current ClearTax/GimBooks pages. Treat as not in force |
| India — "12,000 veterinary hospitals and polyclinics" | Statista via search index; primary DAHD/BAHS source 404s. Livestock-dominated regardless |
| India — RBI/FEMA sub-limits on paying foreign SaaS | No specific prohibition found; FEMA master direction not retrieved |
| India — pet market size | Redseer US$3.6bn is the only credible figure; press releases contradict it by 2–3× |
| Bangladesh — registered veterinarian count | The commonly quoted ~3,812 could not be verified against BVC; discarded |
| Bangladesh / Sri Lanka — vet consultation fees | Not found |
| Sri Lanka — Hyper Selo pricing | From indexed listing; live pricing page 404s |
| Sri Lanka — non-resident digital services VAT threshold (from 1 Jul 2026) | Reported inconsistently across secondary sources |
| Regional — WhatsApp vs local channel dominance in Malaysia, Indonesia, Pakistan | Not separately sourced |
| Cross-cutting — software developer hourly rates by country | **Not obtainable this session.** Accelerance 404, Codica 301, Daxx 522, Arc incomplete. The claim "Egypt is at or below Asian dev cost" is an inference from the repo's own EGP 30,000/month anchor, which is itself flagged as an assumption in `03_PRICING_AND_ECONOMICS.md` |
| Cross-cutting — Paddle seller eligibility for Egypt | Sourced in `03_PRICING_AND_ECONOMICS.md`; Paddle help URLs returned 404 in this session |
