# Aleefy — Competitive Landscape

**Research date:** 2026-07-28
**Method:** WebSearch + WebFetch, English and Arabic queries. Every factual claim carries a URL. Claims I could not source are tagged `[UNVERIFIED]`.
**Reference exchange rate:** 1 USD ≈ **50.5 EGP** (2026 average) — https://www.exchange-rates.org/exchange-rate-history/egp-usd-2026

### How to read the confidence tags

| Tag | Meaning |
|---|---|
| **Vendor-published** | The number/claim appears on the vendor's own site. Highest confidence. |
| **Third-party** | From a review aggregator (Capterra, GetApp, SoftwareAdvice) or press. Aggregator pricing fields are frequently stale or mis-labelled. |
| **Not disclosed** | I looked at the vendor pricing page and it contains no numbers. This is a finding, not a gap. |
| `[UNVERIFIED]` | Inferred, from a search snippet I could not open, or absence-of-evidence rather than a positive statement. |

**Research limitation, stated up front:** the session's 200-query web-search budget was exhausted. Three things I wanted to check and could not: (a) explicit Arabic-support denials from Shepherd/Pulse/Neo, (b) IDEXX/Covetrus Middle East distributor lists, (c) an academic study on veterinary record-keeping in Egypt specifically. Where a section rests on absence-of-evidence I say so.

---

## T1 — Global / Western incumbents

### Summary table

| Product | Owner | Entry price | Price source | Arabic / RTL | On-premise | MENA presence |
|---|---|---|---|---|---|---|
| **ezyVet** | IDEXX (acq. Jun 2021) | **$260.50/mo** | **Vendor-published** | No | No | None found |
| **Provet Cloud** | Nordhealth (NO/FI) | **$99/vet/mo** (Core), $129 (Pro) | Third-party (Capterra/GetApp) | **No** — but ships **Hebrew** | No | None confirmed |
| **Covetrus Pulse** | Covetrus | Not disclosed | — | No evidence | No (cloud) | EMEA unit exists, product is *Ascend* not Pulse |
| **Covetrus AVImark** | Covetrus | Not disclosed | — | No evidence | **Yes — real Windows server install** | None |
| **Covetrus Impromed** | Covetrus | **$5,000 one-time** | Third-party (Capterra) | No evidence | Legacy on-prem | None |
| **IDEXX Neo** | IDEXX | **$290/mo** + $2,375 setup + $590 data conversion | Third-party (Capterra) | No evidence | No | None found |
| **IDEXX Cornerstone** | IDEXX | **$549/mo** (also cited $420, $399, and $15–25k perpetual) | Third-party, wide spread | No evidence | **Yes — officially documented** | None found |
| **IDEXX Animana** | IDEXX (acq. 2014) | Not disclosed (per-user model) | — | **No** — Dutch/English/German only | Listed but doubtful `[UNVERIFIED]` | NL/DE/UK only |
| **Shepherd** | Independent (US) | **$299/mo first vet + $99/additional vet** | Third-party, 4 sources agree | No evidence | No (anti-server positioning) | None |
| **Digitail** | Independent (RO/US) | **$289/user/mo** (Capterra); vendor blog says "$300 per FT DVM, +$150 additional" | Third-party + vendor blog; **pricing page has no numbers** | No `[UNVERIFIED]` | No | None |
| **VETport** | US (Ohio), est. 2002 | **$229/mo** usage-based | Third-party (Capterra); vendor page is a calculator showing $0 | No — EN/FR/DE only | No | **India office; UAE in country list** |
| **Vetspire** | US (Palo Alto) | **Not disclosed** | "$349/DVM/mo" cited by two *competitors'* blogs — treat as hostile source | No evidence | No | None |
| **Hippo Manager** | US (Lexington KY) | **$119/mo per FT veterinarian**, unlimited other seats; migration $1,750 one-time | Third-party (Capterra), most transparent | No evidence | No | None |
| **ezVetPro** | ezofficesystems Ltd (UK) | **Not disclosed**. GetApp shows "$600" **with no unit or period** | Third-party, unusable | No — English only | **Yes — on-prem or vendor-hosted** | None |
| **OpenVPMS** (open source, added for reference) | Not-for-profit (AU) | **A$450 + GST per FTE vet per year**; self-install for testing = $0 | **Vendor-published** | Not documented `[UNVERIFIED]` | **Yes — Tomcat + MySQL, self-hosted** | None |

### Notes that matter more than the table

**ezyVet, Neo, Cornerstone and Animana are one company.** IDEXX acquired ezyVet in June 2021 (https://www.prnewswire.com/news-releases/idexx-acquires-ezyvet-301304524.html). Four SKUs, one vendor, one diagnostics moat. Treating them as four competitors overstates the fragmentation of the market.

**ezyVet is the only major that publishes a price on its own site** — "Get started for as little as $260.50 per month," six-month initial term then three-month rolling, implementation billed separately and not quoted (https://www.ezyvet.com/pricing/us). Note the conflict: the vendor says *per month*, Capterra and GetApp both render it as *per user, per month* (https://www.capterra.com/p/99977/ezyVet-Cloud-Vet-Software/). Unresolved. If the aggregators are right, a 6-seat Egyptian clinic pays ~$1,563/mo ≈ **79,000 EGP/mo**, which is roughly the entire startup capital of an Egyptian vet clinic every month (see T3).

**Provet Cloud has already solved RTL — for Hebrew, not Arabic.** Capterra UK lists its languages verbatim as "Czech, Danish, Dutch, English, Finnish, French, German, **Hebrew**, Hungarian, Italian, Norwegian, Portuguese, Russian, Spanish, Swedish, Traditional Chinese" (https://www.capterra.co.uk/software/137569/provet-cloud). This is the single most important line in T1 for Aleefy: **RTL is not a technical moat.** A vendor with 16 locales and existing RTL plumbing can add Arabic as a translation project, not an engineering project. Provet's pricing structure — per-vet, all other seats free — is also the most Egypt-compatible of the Western majors.

**On-premise is not a differentiator; it is a legacy artifact.** Two majors genuinely support it: Covetrus AVImark (documented Windows server install, files under `C:\Avimark\My Documents`, peer-to-peer capped at nine thick clients — https://covetrus.com/wp-content/uploads/Recommended-Settings-2024.pdf) and IDEXX Cornerstone (IDEXX publishes a document literally titled "On-premises Cornerstone Software and Cornerstone Cloud Software" — https://www.idexx.com/media/filer_public/15/bc/15bce970-f82f-4c82-b84b-fca67e83cef6/art-06-6000042-24_cs_premise_and_cloud_hw_os_guidelines.pdf). Both are products their owners are actively migrating customers *off*. Also on-prem: ezVetPro (UK) and OpenVPMS (open source). Aleefy's self-hosting is a real capability that four other products also have — it is a feature, not a wedge.

**Pricing opacity is the industry norm.** Of fifteen products, exactly three publish a real number on their own site: ezyVet ($260.50/mo), OpenVPMS (A$450/FTE-vet/yr), and VetICare (see T2). Digitail and VETport both operate "pricing pages" that display no prices — VETport's is a JavaScript calculator that renders "$0" and funnels to "Get a Quote" (https://www.vetport.com/pricing).

**Nobody supports Arabic.** Across all fifteen products, Arabic support was found **zero** times. Capterra's own **UAE** veterinary directory (https://www.capterra.ae/directory/30617/veterinary/software) lists 25 products, shows a price for exactly one (Hippo Manager, "$119 per month, per FT veterinarian"), and does not offer Arabic as a site language.

**MENA presence, honestly assessed:** Covetrus is closest — it runs a business unit branded "UK, Europe, Middle East and Africa" (https://software.covetrus.com/emea/) whose cloud product is *Ascend*, launched May 2022 for "the United Kingdom, EMEA and Asia Pacific" (https://www.businesswire.com/news/home/20220505005902/en/). But no Arabic and no confirmed Arab-country deployment. VETport is second — 37 countries claimed, a real India office (+91 809-526-2222), UAE in its country dropdown (https://www.vetport.com/VETport-Launched-in-India). Everyone else: nothing.

---

## T2 — Regional and Egyptian competitors

**This is the section that changes the investment case, and not in the direction you were hoping.**

### 2.1 The headline finding: the Arabic vet-software niche is NOT empty

I expected to report that it was. It is not.

#### VetICare — the direct competitor

- **Site:** https://veticareapp.com/ · features https://veticareapp.com/features/ · pricing https://veticareapp.com/price
- **Arabic/RTL:** explicit and marketed. Feature page states verbatim **"Arabic Language Support (RTL)"** under a "Multilingual Support" heading, with dynamic language switching and multi-language reports. French and German listed as coming soon. (https://veticareapp.com/features/)
- **Egypt:** not aspirational — **operating**. The homepage names Egyptian clinic customers: **Pets Zone, Dr Men3am Pet Hospital, Almotawakkel Pet Center, Mojo Veterinary**. Countries named: KSA, UAE, Oman, **Egypt**. Operating since 2020, claims 500+ clients. (https://veticareapp.com/)
- **Pricing — VENDOR-PUBLISHED, the only Arabic-capable vet vendor with public numbers** (https://veticareapp.com/price):
  - **Basic — $52.00/month for 5 users** (≈ 2,630 EGP/mo), all features, unlimited bills and items, standard support
  - **Professional — 20 users**, price not shown
  - **Enterprise — unlimited users**, price not shown
  - **WhatsApp vaccination alerts: +$20/month add-on**
  - 14-day free trial, **3-month minimum commitment**, 10% annual discount
- **Modules confirmed on the features page:** pharmacy/e-prescriptions with drug database, laboratory **with named analyser integrations (Exigo, Edan)**, inventory, POS, boarding, HR with 4 roles / 180+ permissions, WhatsApp. **Saudi ZATCA offline QR e-invoicing.** Not found: grooming, telemedicine.
- **Also ships a pet-owner mobile app** ("Squeak") with appointment booking, vaccination reminders, invoice history, and an AI symptom checker/triage.
- **Deployment:** cloud-native only. HQ country not disclosed anywhere on the site — a mild credibility flag.

**Read this carefully.** VetICare occupies, today, with paying Egyptian customers: Arabic + RTL, WhatsApp integration, pharmacy, lab-machine integration, inventory, POS, boarding, RBAC, a pet-owner mobile app, AI triage, and a published price of $52/month. Four of the six things listed in the brief as Aleefy's genuine advantages are already shipped by an incumbent at 2,630 EGP/month. It also does two things the brief lists as Aleefy weaknesses (lab-machine integration, mobile app).

#### Other Arabic-capable vet products

| Product | Origin | Arabic/RTL | Pricing | Assessment |
|---|---|---|---|---|
| **bAItari.vet** (بيطري) — https://baitari.vet/ | **"صُمِّم في عمان"** — designed in Oman | Arabic-primary, English toggle | **Not disclosed** | Arabic-first vet platform, cloud, AI documentation, EHR + field-exam module + annotated imaging. Tagline: "the digital future of veterinary medicine in the Arab world." Live signup/login. **Serious positional competitor for the same story Aleefy wants to tell.** |
| **Yolo Clinic** — https://yolo.clinic/ar/ | UAE WhatsApp contact (+971) | Arabic + English | **Not disclosed** (free trial offered) | Vet-specific product line plus human-medical line. Android/iOS/Huawei apps. ZATCA-oriented tax reporting. Marketed into Egypt-facing Arabic search results. |
| **Kawakeb Al-Teknologia (كواكب التقنية)** — https://www.const-tech.org/public/products/5 | Saudi Arabia | Arabic | **Not disclosed** | Vet clinic module: records, appointments, radiology, lab, pharmacy, accounting, RBAC, vaccination tracking, WhatsApp notifications. Runs "على الويب مباشرة او شبكة داخلية" — **web or internal LAN, i.e. on-premise capable**. |
| **Holool Alghad (حلول الغد)** — https://holoolalghad.com/veterinary-clinic | Riyadh, Saudi Arabia | Arabic + English | **Not disclosed** | Vet clinic system: appointments, records, inventory, purchasing, SMS, financial analysis, device integration. |
| **Al-Mukhtabarat (شركة المختبرات)** — https://almukhtabarat.com/products/2/... | **EGYPT — Dr. Mohiuddin St., 4th District, 6 October, Giza** | Arabic + English | **Not disclosed** | **The one genuinely Egyptian vet-adjacent vendor found.** Veterinary lab + clinic system: blood/chemistry/parasite/brucellosis panels, ultrasound, surgery, vaccination, **barcode + medical-device result capture**, WhatsApp result delivery, deferred payments, multi-branch stock transfer. Lab-lab focus, but overlaps Aleefy's lab and clinical modules directly. |
| **Petsphere (2t Interactive)** — https://2tinteractive.com/solutions/petsphere/ | Lebanon | Reported EN/FR/**Arabic-Lebanese with RTL**, dual currency USD/LBP | Not found | `[UNVERIFIED]` — site returned 404 at fetch time; details from search index only. |
| **Veterical** (App Store) — https://apps.apple.com/us/app/.../id6736607434 | "Gamma Investments LLC" | App Store lists 33 languages **including Arabic** | App free; no pricing disclosed | Thin web presence, RTL quality unverified. |
| **vetPMS Cloud** (Advitech), via **Medical Plus EQ Trading LLC**, Dubai — https://medicalplus.ae/product/vetpms-cloud-veterinary-practice-management-software/ | Reseller: UAE | **Arabic not mentioned** | **Not disclosed** | Illustrates the actual MENA channel model: a local medical-equipment distributor reselling a foreign PIMS across UAE/Qatar/Kuwait/Saudi/Oman. This is how software reaches Gulf clinics — through distributors, not direct. |
| **GVET** — https://www.gvetsoft.com/en/ | Latin America (LatAm e-invoicing, LatAm testimonials) | **Lists Arabic** among Spanish/English/Portuguese/French/Italian/German/Tagalog | Not disclosed (3-month free trial) | Cloud, WhatsApp notifications, telemedicine. Arabic is a translation checkbox, not a market focus. Low threat today; proof that adding Arabic is cheap for an existing product. |

### 2.2 The real substitute: human-medical clinic systems

Egyptian and Gulf clinic-management vendors are numerous, Arabic-native, cheap, and **almost all decline to do veterinary**. That is the actual competitive terrain — a vet who wants software today either buys a human-clinic system and misuses it, or buys nothing.

| Product | Origin | Pricing | Vet coverage |
|---|---|---|---|
| **Daftra** — https://www.daftra.com/ | Regional; phone lines for **Egypt**, KSA, UAE, Jordan, Oman, Qatar, Bahrain, Kuwait | **VENDOR-PUBLISHED in EGP** (https://www.daftra.com/plans/): Basic **489.50 EGP/mo** (list 733), Advanced **977.58 EGP/mo** (list 1,225), Comprehensive **1,960 EGP/mo** (list 2,448). Annual: 5,874 / 11,731 / 23,520 EGP. Extra user **294–392 EGP/mo**; extra branch **980–1,293.60 EGP/mo**; storage 24.5 EGP/GB. 14-day trial. | **No veterinary module mentioned** |
| **Medicakare** — https://www.medicakare.com/ar/ | Offices Riyadh, **Cairo**, Dubai, London | **Free tier for one clinic.** Paid multi-clinic plans, prices not disclosed | **No** — human specialties only |
| **Fekra IT (فكرة)** — https://fekrait.com/ | Al-Madinah, Saudi Arabia | Not disclosed | **No.** Notable: **Windows desktop, on-premise, works with no internet** — the on-prem model Aleefy assumes is what regional buyers already recognise |
| **ClinicGateway** — https://clinicgateway.ae/blog/best-clinic-management-software-saudi-arabia-2025/ | Saudi/UAE | **From 2,500 SAR/month.** Same page benchmarks internationals: Kareo 2,800+, eClinicalWorks 3,800+, Greenway 4,200+, AdvancedMD 5,000+, Allscripts 6,000+ SAR/mo; enterprise 8,000–15,000+ SAR/mo plus 50,000–200,000+ SAR setup | **"No mention of veterinary services appears anywhere."** Full Arabic + RTL + Hijri calendar |
| **Nitco (نتكو)** — https://nitcotek.com/ | Egypt | Publishes an article titled "أسعار برامج إدارة العيادات في مصر" that **contains no prices** | Human clinics |
| **Odoo vet modules** — https://apps.odoo.com/apps/modules/13.0/bi_veterinary_management | BrowseInfo (India) et al. | **$272.20 one-time** for the v13 module. Odoo core is natively Arabic + RTL | Full vet module: pets, appointments, hospitalisation with bed transfer, lab, imaging, prescriptions, invoicing, reports. Egyptian Odoo partners (Macrofix, OEC-EG) sell Arabic-localised ERP implementations |

**The Odoo line is the most dangerous entry in this document.** A $272 module on a platform that already has Arabic, RTL, accounting, inventory, POS, HR, and a network of Egyptian implementation partners is not a toy. An Egyptian clinic chain that wants what Aleefy offers can get 70% of it from an Odoo partner tomorrow, with an ERP vendor's support contract behind it.

### 2.3 What the Egyptian vet-specific market actually looks like

It is not empty. It is **thin, unbranded, and served by adjacent vendors** — which is worse than empty, because "empty" implies latent demand while "thin" may imply the demand was tested and found small.

Searches run (Arabic and English), all returning the same ~8 names:
- `برنامج إدارة عيادات بيطرية`
- `نظام إدارة عيادة بيطرية مصر`
- `برنامج بيطري مصر شركة برمجيات عيادة بيطرية سعر النظام`
- `برنامج إدارة العيادات مصر أسعار اشتراك شهري`
- `"برنامج" "عيادة بيطرية" جنيه سعر شهري اشتراك مصر نظام بيطري`
- `شركة برمجيات مصرية نظام عيادات ERP بيطري "بيطرية" حلول برمجية القاهرة`
- `برنامج عيادة بيطرية السعودية الامارات نظام بيطري سحابي`
- plus English equivalents for Egypt / Cairo / MENA / UAE / Saudi.

**Not one Egyptian company was found selling a branded, vet-specific practice management product with a public price.** The closest is Al-Mukhtabarat (Giza) selling a vet *laboratory* system. Everything else Egyptian is a human-clinic vendor or an Odoo partner.

**But the demand-side evidence is equally discouraging.** The two clearest signals of unmet demand I found are freelance-marketplace briefs, and both point to one-off custom builds rather than a subscription market:

- **Mostaql** (https://mostaql.com/project/591364-...): a client — Saudi, inferred from the ZATCA requirement — requests a *complete* vet clinic system: HR, payroll with commissions and deductions, clients and pets, medical records, appointments, exams/surgery/vaccination/**grooming/boarding**, prescriptions, lab, invoicing, inventory, insurance, supply sales, accounting, reports, notifications, remote monitoring, ZATCA-approved, with support. **Budget: "$1000.00 - $2500.00."** ~30 offers received. Posted ~3 years ago, now closed.
- **Khamsat** (https://khamsat.com/community/requests/405150-...): a vet ("Drahmed B") requesting case registration, vaccination dates, appointment alerts, and medication inventory. 10 developer responses. **No budget stated.** Posted ~6 years ago.

That Mostaql brief is, feature-for-feature, roughly Aleefy. Someone in the Gulf specified it and expected to pay **$1,000–$2,500 once, forever**. Thirty developers competed for it.

**Adjacent Egyptian pet-tech that exists:** VetCode (Cairo, founded 2018, seed round from Pmaestro Dec 2018 at a **$450,000 pre-money valuation**, 200+ clinics in its network, 30,000+ users, 12 cities — https://www.menabytes.com/vetcode-seed/). It is a **consumer marketplace, not a PIMS.** Vezeeta lists veterinary as a bookable specialty in Egypt (https://www.vezeeta.com/en/doctor/veterinary/egypt) — the front-desk booking layer is already occupied by a company with far more distribution than a new PIMS will have. Note the valuation: the most-funded Egyptian pet-tech company found was worth $450k pre-money.

---

## T3 — The real incumbent: paper, Excel, and WhatsApp

I could not find a study measuring software adoption in Egyptian veterinary practice specifically. **That data does not exist**, and I am not going to invent a proxy and dress it up. What follows is the circumstantial evidence that does exist.

### The economics of the buyer

| Fact | Figure | Source |
|---|---|---|
| Capital to open a vet clinic in Egypt | **≈ 60,000 EGP** (≈ $1,190) | small-projects.org feasibility study, via search result summary — **domain would not resolve for direct fetch** `[UNVERIFIED — single-source, snippet only]` |
| Typical consultation fee | **150 EGP** (≈ $3.00) | same source `[UNVERIFIED]` |
| Syndicate clinic registration | **605 EGP** first time, **505 EGP** renewal | https://www.youm7.com/story/2024/8/13/...6671405 — **verified by direct fetch** |
| Max clinics per veterinarian | **2** | same, verified |
| Rabies/tetanus vaccination price | **≈ 800 EGP** ($16.82); vet medicine prices **+50% in one year** | https://egyptianstreets.com/2025/10/26/navigating-change-the-transformation-of-egypts-pet-industry.../ |
| Egyptian inflation | **40.3%** (May 2023) | https://globalpetindustry.com/article/pet-industry-egypt/ |
| Egypt pet food market | **$13.7m** (2022), → $15.3m (2023), Euromonitor | same |
| Registered veterinarians in Egypt | **≈ 56,000**, ~4,000 graduates/yr from 13 faculties | via search summary of youm7/elbalad `[UNVERIFIED — snippet only]` |

**The two figures that matter most are the least verified.** If the 60,000 EGP / 150 EGP numbers are roughly right, then: a whole clinic costs ~$1,190 to open, and a consultation grosses $3. ezyVet's entry price ($260.50/mo) is **88 consultations a month before the vet earns anything**. Even VetICare's $52/mo is 17.5 consultations. Aleefy's addressable price point is bounded by this, not by what the software is worth.

### What regional software actually costs — the ceiling on Aleefy's pricing

The best anchor found is from an Egyptian pharmacy-software market article (https://aumet.com/اسعار-برامج-الصيدليات-دليلك-لاختيار-ا/):

- Basic pharmacy management software: **5,000–12,000 EGP as a permanent (perpetual) licence** — i.e. **$99–$238 once**
- Advanced systems for chains: **over 20,000 EGP** initial
- Subscription model where offered: **500–1,500 EGP/month** ($10–$30/mo)
- Local alternatives: **from ~7,000 EGP**

Cross-checked against Daftra, the one regional vendor publishing EGP prices for a clinic product: **489.50–1,960 EGP/month** (https://www.daftra.com/plans/). Both sources land in the same band.

**So the Egyptian ceiling is roughly 500–2,000 EGP/month, or a 5,000–12,000 EGP perpetual licence — and the market's default expectation is the perpetual licence, not the subscription.** That is $10–$40/month, or $100–$240 once. Aleefy's 28 modules and 73 tables do not change this number; the buyer's cash flow sets it.

### Pet ownership: real growth, unmeasured base

- Registered dog owners: **2,000 (2016) → 860,000+ (2019)** — https://egyptianstreets.com/2025/10/26/...
- Euromonitor 2023: **10 million people keep pets** in Egypt, top of the Arab region — via search summary `[UNVERIFIED — snippet]`
- But the estimates disagree by 2×: Euromonitor counted **4 million pets** (2022) while the Egyptian SPCA estimates **8 million household pets** (5m cats, 3m dogs) — https://globalpetindustry.com/article/pet-industry-egypt/
- Egyptian Streets, on the industry's own data quality: *"the lack of comprehensive data on the pet population complicates market analysis."*

**The growth story is real. The measurement is not.** A 2× disagreement on the base is itself the finding: nobody knows how big this market is, including the people selling into it.

### Digitisation baseline

- **Digital payments (the closest available proxy):** Visa/MSMEDA 2025 study of Egyptian merchants — **53%** adopted digital payments in the last two years, **77%** consider them crucial to growth, **55% of cash-only merchants** are interested in adopting. https://km.visamiddleeast.com/en_KM/about-visa/newsroom/press-releases/prl-28072025.html · https://english.ahram.org.eg/NewsContentP/3/553109/Business/-of-Egyptian-SMEs-adopt-digital-payments.aspx
  - **Inverted: roughly 47% of Egyptian merchants are still cash-only in 2025.** Aleefy has no payment gateway; in this market that is less of a gap than it looks, but it also means invoicing modules compete with a cash drawer.
- **EMR research in Egypt is nearly non-existent.** A systematic review of EMR adoption in developing economies found **Egypt has one study** on physician EMR adoption, versus five for Ethiopia (https://pmc.ncbi.nlm.nih.gov/articles/PMC10787531/). The Egyptian EHR evaluation literature notes paper-based systems are "still in use today" (https://www.semanticscholar.org/paper/Evaluation-of-Electronic-Health-Records-Adoption-in-Eldin-Saad/8d4052ad0bc74d5c8856f65e8888092006b10dbe). A demand-side survey of 559 Egyptian respondents found **price value** among the determining factors in EHR adoption (https://www.sciencedirect.com/science/article/abs/pii/S030859611830212X).
- **On Egyptian veterinary practice specifically: no data found.** Not thin — absent.

### The honest characterisation

The competitor is not paper *in the abstract*. It is: a 150 EGP consultation, a paper card file, a cash drawer, a personal WhatsApp thread with the owner, and — for the clinics that have digitised at all — an Excel sheet and a distributor-installed Windows POS. Every regional vendor found (Al-Mukhtabarat, VetICare, Kawakeb, GVET) leads with **WhatsApp integration**, which tells you what the incumbent workflow is. Aleefy's WhatsApp module is table stakes in this market, not a differentiator.

---

## T4 — Feature gap table

Aleefy vs the four most relevant competitors. **VetICare** is the direct competitor; **Daftra** is the realistic substitute an Egyptian clinic actually buys; **Odoo + partner** is the credible build-alternative; **ezyVet** is the aspirational Western benchmark that will never reach this market at its price.

| | **Aleefy** | **VetICare** | **Daftra** | **Odoo vet module + EG partner** | **ezyVet** |
|---|---|---|---|---|---|
| Vet-specific | Yes | Yes | **No** | Yes | Yes |
| **Price** | Undecided | **$52/mo, 5 users** (vendor-published) | **489.50–1,960 EGP/mo** (vendor-published) | **$272 module** + partner implementation | **$260.50/mo** (vendor-published) |
| **Arabic + RTL** | Yes — 4,372 strings, every screen | **Yes — marketed "Arabic Language Support (RTL)"** | Yes | Yes (Odoo core) | **No** |
| Deployment | **Self-host or cloud** | Cloud only | Cloud only | Either | Cloud only |
| Per-seat cost | **None** | $52 covers 5; tiers at 20/unlimited | **294–392 EGP per extra user/mo** | Per Odoo user | Possibly per-user (vendor/aggregator conflict) |
| Appointments + waiting-room TV | Yes | Appointments yes; TV display not found | Appointments | Appointments | Yes |
| EMR / SOAP | Yes | Yes | Human EMR | Yes | Yes (best in class) |
| CRM owners/pets | Yes | Yes | Patients only | Yes | Yes |
| Pharmacy + dispensing | Yes | Yes, + drug database | Partial | Yes | Yes |
| Lab requests/results | Yes | Yes | No | Yes | Yes |
| **Lab-machine integration** | **No** | **Yes — Exigo, Edan named** | No | No | **Yes — IDEXX owns the analysers** |
| Medical imaging | Yes, + AI photo analysis | Imaging listed | No | Yes | Yes |
| Inpatient / hospitalisation | Yes | Boarding module | No | **Yes, incl. bed transfer** | Yes (Vet Radar) |
| Telemedicine | **Yes — Jitsi, no per-seat cost** | Not found | No | No | Add-on |
| Grooming | Yes | **Not found** | No | No | No |
| Boarding | Yes | Yes | No | No | No |
| Finance / invoicing | Yes | Yes | **Yes — core strength** | Yes | Yes |
| Accounting (P&L, cashflow, budget, daily close) | **Yes** | Not detailed | **Yes — core strength** | **Yes — full ERP** | No (integrations) |
| Inventory, batch/FEFO/expiry | **Yes** | Inventory yes; FEFO not stated | Warehouses, limited | Yes | Yes |
| Procurement | Yes | Not stated | Yes | Yes | Yes |
| Retail POS + pet shop | Yes | **Yes** | Yes (1 POS incl.) | Yes | Limited |
| HR / attendance / payroll | **Yes** | HR roles/permissions only | No | **Yes** | No |
| Reports + self-service builder | Yes | Reports | Yes | Yes | Yes |
| **WhatsApp** | Yes | **Yes (+$20/mo)** | Yes | Via partner | No |
| AI assistant | Yes | AI triage in owner app | AI credits | No | Add-on |
| Customer chatbot | Yes ("Petsy") | AI Symptom Checker in Squeak app | No | No | No |
| **Pet-owner mobile app** | **No** | **Yes — "Squeak"** | Mobile app (iOS/Android) | Odoo mobile | ezyVet Go / Connect |
| **Payment gateway** | **No** | Not stated | Yes | Yes | IDEXX Payments |
| E-invoicing compliance | Not stated | **Saudi ZATCA offline QR** | Regional tax support | Egyptian tax localisation via partner | US/NZ/AU |
| Audit log, backups, RBAC, TOTP 2FA | Yes | RBAC: 4 roles, 180+ permissions | Yes | Yes | Yes |
| **Multi-site / chains** | **Single-clinic focus** | Enterprise tier, unlimited users | Multi-branch (paid) | Multi-company | **Best in class** |
| **Track record** | **Zero paying customers** | Since 2020, claims 500+ clients, 4 named Egyptian clinics | Established regional SaaS | Odoo: global, thousands of partners | Since 2006, IDEXX-owned |
| **Support organisation** | **None** | Standard / Priority / 24/7 tiers | Regional phone lines in 8 countries | Local partner SLA | 24/7 included |

### Where Aleefy is genuinely ahead

1. **Module breadth is real and unmatched at this price point.** Nobody else in the Arabic segment ships grooming *and* boarding *and* telemedicine *and* payroll *and* full accounting *and* pet-shop POS in one system. VetICare has no grooming and no telemedicine found; Daftra has no vet anything; Odoo needs a partner to assemble it.
2. **Self-hosting with no per-seat cost.** VetICare charges by user band. Daftra charges 294–392 EGP per extra user per month. A 10-person Egyptian clinic on Daftra pays more in seat fees than in base subscription. Aleefy's flat, self-hosted, unlimited-user model is the cleanest cost story in the set, and it works when the internet doesn't.
3. **Depth of Arabic.** 4,372 strings across every screen is more thorough than a "language switcher" bolt-on. Whether a buyer can perceive that difference before purchase is a separate question, and the answer is probably no.
4. **Accounting + HR + payroll integrated.** This is the one place Aleefy beats an ERP-lite substitute rather than merely matching a vet-lite one.
5. **Jitsi telemedicine at zero marginal cost** is a structurally cheaper approach than per-seat video.

### Where Aleefy is genuinely behind

1. **No lab-machine integration** — and VetICare names Exigo and Edan, the exact bench analysers a mid-tier Egyptian clinic owns. This is the demo-killer. A vet who has to retype CBC results will notice within ten minutes.
2. **No mobile app of any kind** — no vet app, no owner app. VetICare ships "Squeak" with AI triage. Daftra ships iOS/Android. In a market where the owner's phone *is* the channel, this is a first-order gap.
3. **No payment gateway.** Less fatal in a 47%-cash market than elsewhere, but it blocks the segment most able to pay.
4. **Single-clinic focus.** The Syndicate permits 2 clinics per vet (verified), so single-clinic is defensible for the long tail — but it also caps deal size at the exact clinics with the least money. The chains are where the revenue is and Aleefy cannot serve them.
5. **Zero customers, zero support organisation, unproven at scale.** 28,000 lines of Python written by one person has never survived a Saturday at a busy Cairo clinic. Every competitor listed has a support tier; Aleefy has a person.
6. **No e-invoicing compliance.** Egypt's ETA e-invoicing mandate is a hard requirement for registered businesses, and VetICare already ships ZATCA for Saudi. Compliance work is unglamorous, non-negotiable, and never finished.
7. **RTL is not a moat.** Provet already ships Hebrew — the RTL engineering exists in the majors and is dormant, not absent. Adding Arabic to Provet Cloud is a translation contract.

---

## What this means for Aleefy

**1.** The thesis that Egypt has no Arabic vet software is **false** — VetICare ships Arabic with RTL, integrates named lab analysers, has a pet-owner mobile app, publishes a $52/month price, and lists four Egyptian clinics as customers on its homepage; bAItari is doing the same story out of Oman.

**2.** The pricing ceiling is brutal and it is set by the buyer's cash flow, not by feature count: Egyptian clinic and pharmacy software sells for a **5,000–12,000 EGP perpetual licence or 500–1,500 EGP/month**, and the market's default expectation is the perpetual licence — meaning 28 modules and 376 routes have to be sold for roughly $100–$240 once, or $10–$40 a month, to a business whose consultation grosses about $3.

**3.** The single most damaging artefact in this research is the Mostaql brief: a Gulf clinic specified almost exactly Aleefy's feature list — HR, payroll, pets, EMR, grooming, boarding, lab, inventory, insurance, accounting, e-invoicing compliance — and budgeted **$1,000–$2,500 as a one-time build**, attracting thirty competing developers; that is the market's revealed price for this entire product.

**4.** RTL and Arabic are not defensible: Provet Cloud already ships Hebrew and sixteen locales, GVET already lists Arabic from Latin America, and Odoo has native Arabic RTL with a $272 vet module and a bench of Egyptian implementation partners — anyone who wants this market can have Arabic in a quarter.

**5.** The features that would actually win an Egyptian demo — analyser integration, an owner-facing mobile app, ETA e-invoicing — are the three Aleefy does not have, while the features it does have in surplus (telemedicine, AI photo analysis, a self-service report builder, a customer chatbot) are ones a 150-EGP-consultation clinic will never pay extra for.

**6.** Self-hosting is not the wedge it appears to be: AVImark, Cornerstone, ezVetPro and OpenVPMS all offer it, Saudi vendor Fekra IT actively markets a Windows-desktop clinic system that works offline, and on-premise means *you* own the backups, the Postgres upgrades, and the 11pm phone call — which is a support liability, not a moat, for a one-person company.

**7.** The market's own size estimates disagree by 2× (Euromonitor's 4 million pets vs the Egyptian SPCA's 8 million), the pet food market is only **$13.7m**, and the best-funded Egyptian pet-tech startup found was valued at **$450,000 pre-money** — the ceiling on this entire vertical may be smaller than a single Western vendor's ARR from one mid-size hospital.

**8.** There is no data on Egyptian veterinary software adoption because nobody has bothered to collect it, and the EMR research literature for Egypt as a whole amounts to roughly one study — an absence that reads less like an undiscovered opportunity and more like a market too small to have attracted an analyst.

**9. The strongest argument that Aleefy should not be commercialised:** the product is a technically impressive answer to a question the market has already answered more cheaply — VetICare occupies the Arabic vet niche today with lab integration and a mobile app at $52/month, Odoo occupies the breadth-and-accounting niche at $272 plus a partner who provides the support contract Aleefy cannot, and the residual segment is single-clinic Egyptian vets who expect to pay a one-time 5,000–12,000 EGP licence, cannot be reached without a distribution channel that does not exist, and will generate support load that a solo maintainer cannot absorb — so the realistic outcome is not a business but a second unpaid job, and the disciplined move is to sell the first ten clinics *manually, at the perpetual-licence price, before writing another line of code*, and treat failure to close those ten as the answer.

**10.** If it proceeds anyway, the only defensible positioning found in this research is **the accounting-and-operations depth**, not the vet clinical features — Daftra and Odoo prove Egyptian buyers will pay monthly for financial control, while every vet-specific competitor treats accounting as an afterthought.

---

## Appendix — all sources cited

**T1 vendors:** https://www.ezyvet.com/pricing/us · https://www.ezyvet.com/ · https://www.prnewswire.com/news-releases/idexx-acquires-ezyvet-301304524.html · https://www.provet.com/pricing · https://www.capterra.co.uk/software/137569/provet-cloud · https://www.getapp.com/industries-software/a/provet-cloud/ · https://developers.provetcloud.com/restapi/0.1/ · https://covetrus.com/covetrus-platform/workflow-and-productivity-tools/covetrus-pulse/ · https://covetrus.com/wp-content/uploads/Recommended-Settings-2024.pdf · https://software.covetrus.com/emea/ · https://www.businesswire.com/news/home/20220505005902/en/ · https://software.idexx.com/products/neo/pricing · https://www.idexx.com/media/filer_public/15/bc/15bce970-f82f-4c82-b84b-fca67e83cef6/art-06-6000042-24_cs_premise_and_cloud_hw_os_guidelines.pdf · https://www.shepherd.vet/ · https://costbench.com/software/veterinary-software/shepherd/ · https://digitail.com/plans/ · https://digitail.com/blog/best-veterinary-software-guide/ · https://www.vetport.com/pricing · https://www.vetport.com/VETport-Launched-in-India · https://www.vetspire.ai/ · https://www.vetsoftwarehub.com/product/vetspire/pricing · https://www.hippomanager.com/ · https://www.ezofficesystems.com/ · https://privatepracticesoftware.org.uk/veterinary-private-practice-software/ezvetpro-review.html · https://openvpms.org/subscription

**Aggregator pricing tables:** https://www.capterra.com/veterinary-software/ · https://www.capterra.ae/directory/30617/veterinary/software · https://www.softwareadvice.com/veterinary/ · https://www.capterra.com/p/99977/ezyVet-Cloud-Vet-Software/ · https://www.capterra.com/p/145988/IDEXX-Neo/pricing/ · https://www.capterra.com/p/99976/Cornerstone-Practice-Management/ · https://www.capterra.com/p/95888/ImproMed/ · https://www.capterra.com/p/172485/Shepherd-App/pricing/ · https://www.capterra.com/p/167764/Digitail/pricing/ · https://www.capterra.com/p/92897/Vetport/ · https://www.capterra.com/p/134667/Hippo-Manager/pricing/ · https://www.capterra.co.uk/software/92895/animana · https://www.softwareadvice.com/veterinary/ezyvet-profile/

**T2 regional/Egyptian:** https://veticareapp.com/ · https://veticareapp.com/features/ · https://veticareapp.com/price · https://baitari.vet/ · https://baitari.vet/use-cases/pets · https://yolo.clinic/ar/برنامج-ادارة-عيادة-بيطرية/ · https://www.const-tech.org/public/products/5 · https://holoolalghad.com/veterinary-clinic · https://almukhtabarat.com/products/2/ · https://www.gvetsoft.com/en/ · https://medicalplus.ae/product/vetpms-cloud-veterinary-practice-management-software/ · https://2tinteractive.com/solutions/petsphere/ (404) · https://apps.apple.com/us/app/برنامج-إدارة-العيادة-البيطرية/id6736607434 · https://www.daftra.com/plans/ · https://www.daftra.com/برنامج-إدارة-العيادات-والمراكز-الطبية/ · https://www.medicakare.com/ar/ · https://fekrait.com/ · https://clinicgateway.ae/blog/best-clinic-management-software-saudi-arabia-2025/ · https://nitcotek.com/ · https://apps.odoo.com/apps/modules/13.0/bi_veterinary_management · https://www.odoo.com/partners/country/egypt-64 · https://macrofix.com/odoo/odoo-partners-egypt/ · https://mostaql.com/project/591364-برنامج-إدارة-عيادة-بيطرية-بالكامل · https://khamsat.com/community/requests/405150-برنامج-لإدارة-عيادة-بيطرية · https://www.menabytes.com/vetcode-seed/ · https://www.vezeeta.com/en/doctor/veterinary/egypt

**T3 market/adoption:** https://www.youm7.com/story/2024/8/13/...6671405 · https://egyptianstreets.com/2025/10/26/navigating-change-the-transformation-of-egypts-pet-industry-amid-economic-challenges-and-shifting-consumer-preferences/ · https://globalpetindustry.com/article/pet-industry-egypt/ · https://www.grandviewresearch.com/horizon/outlook/animal-health-market/egypt · https://aumet.com/اسعار-برامج-الصيدليات-دليلك-لاختيار-ا/ · https://km.visamiddleeast.com/en_KM/about-visa/newsroom/press-releases/prl-28072025.html · https://english.ahram.org.eg/NewsContentP/3/553109/Business/-of-Egyptian-SMEs-adopt-digital-payments.aspx · https://pmc.ncbi.nlm.nih.gov/articles/PMC10787531/ · https://www.sciencedirect.com/science/article/abs/pii/S030859611830212X · https://www.semanticscholar.org/paper/Evaluation-of-Electronic-Health-Records-Adoption-in-Eldin-Saad/8d4052ad0bc74d5c8856f65e8888092006b10dbe · https://www.africanews.com/2022/10/13/dog-ownership-has-soared-in-egypt-in-the-past-decade/ · https://www.exchange-rates.org/exchange-rate-history/egp-usd-2026
