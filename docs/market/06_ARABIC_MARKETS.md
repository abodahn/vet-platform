# 06 — Arabic-Speaking Markets Outside the Gulf

**Prepared:** July 2026
**Product:** Aleefy — Flask/PostgreSQL veterinary clinic ERP, 28 modules, fully bilingual Arabic/English with RTL, self-hosted or cloud.
**Team:** two people, Cairo, no capital. Every market must be sellable and supportable **remotely, from Egypt**.
**Scope:** Morocco, Algeria, Tunisia, Libya, Sudan, Jordan, Lebanon, Iraq, Syria, Palestine.
**Method:** desk research in English, French and Arabic. Every number carries a URL. Anything unsourced is marked `[UNVERIFIED]` or `[NO DATA]`.

---

## 0. Read this first — four honesty warnings

**1. Nobody publishes a companion-animal clinic count for any of these ten countries.** Not one. Every number below is a proxy: veterinary-order membership (which is dominated by livestock and government vets), a directory scrape (which counts who bothered to list themselves), or a press figure with no stated methodology. Treat all clinic counts as order-of-magnitude.

**2. Veterinary orders are the wrong denominator.** In every country in this study the veterinary profession is overwhelmingly livestock, poultry, food inspection and public service. Lebanon is the only country with a published split, and it is instructive: **384 active vets, of whom 150 self-identify as small-animal** ([Juniper Publishers](https://juniperpublishers.com/jdvs/JDVS.MS.ID.555922.php)). Roughly 40%. Apply that kind of haircut everywhere, and then haircut again for vets who share premises.

**3. Pet-care *retail* market size is not veterinary *services* revenue.** This matters enormously for the Morocco finding in §1. Retail pet food flows through supermarkets. A clinic ERP is sold against clinic revenue. The two are only loosely correlated.

**4. Where data does not exist, this document says so.** Libya, Sudan, Syria and Palestine are largely blanks. That is a finding, not a gap to be filled with an estimate.

---

## 1. THE MOROCCO FINDING — verified, explained, and partly misleading

### 1.1 The claim is true as stated

| Country | Pet retail sales, 2025 | Forecast 2026 | 2021 baseline | Source |
|---|---|---|---|---|
| **Morocco** | **€62.5m** ($72.8m) | +4–6% | — | [GlobalPETS, "North African pet industry"](https://globalpetindustry.com/article/north-african-pet-industry-a-fast-growing-region-with-untapped-potential/) |
| **Egypt** | **€23m** ($26.8m) | €27.4m ($31.9m), +19% | €10.5m | [same source](https://globalpetindustry.com/article/north-african-pet-industry-a-fast-growing-region-with-untapped-potential/) |

Both figures come from **the same publisher, the same article, the same year (2025), the same basis (retail sales), and the same underlying data provider (Euromonitor)**. This is not a year mismatch or a methodology mismatch. Morocco is **2.7×** Egypt on this measure with roughly one third of the population.

Morocco's population is ~38m against Egypt's ~107m. So on a per-capita basis Morocco outspends Egypt by roughly **7–8×**.

### 1.2 It is not because Morocco has more pets — it has fewer

| | Morocco | Egypt |
|---|---|---|
| Pet population | **2.65m** (2023 forecast) [GlobalPETS Morocco](https://globalpetindustry.com/article/pet-industry-morocco/) | **4.0–4.2m** (Euromonitor, 2022–2025) [GlobalPETS Egypt](https://globalpetindustry.com/article/pet-industry-egypt/) |
| Households owning a pet | 34% (2022) [GlobalPETS Morocco](https://globalpetindustry.com/article/pet-industry-morocco/) | not published |
| Implied retail spend per pet per year | **~€24** | **~€5.5** |

Egypt has roughly **1.6× more pets** than Morocco and spends roughly **one quarter as much per pet**. The entire gap is **monetisation per animal**, not animal count.

### 1.3 The mechanism — five compounding causes, in order of size

**(a) Egyptian pound devaluation destroyed the euro-denominated figure.** The EGP went from ~LE18–19/USD in mid-2022, to LE30.9, to over **LE50 after the March 2024 float** — a **>70% depreciation since March 2022** ([Ahram Online](https://english.ahram.org.eg/News/519335.aspx), [2023–2024 Egyptian financial crisis](https://en.wikipedia.org/wiki/2023%E2%80%932024_Egyptian_financial_crisis)). Morocco's dirham did not move materially over the same period. **Any Egyptian market measured in euros shrank by more than half without a single lost customer.** Egypt going €10.5m → €23m in euros over 2021–2025 through a 70% devaluation implies local-currency growth on the order of 6–8×. Held at 2021 FX, Egypt's 2025 figure would land somewhere near **€55–70m** — i.e. roughly level with Morocco. This single factor probably accounts for most of the headline gap. `[ESTIMATE — arithmetic on the sourced figures above, not a published number]`

**(b) Egypt's import channel was deliberately shut.** After the 2022 capital flight, Egyptian banks stopped allocating hard currency to non-essential imports — pet food named explicitly. Imported pet food prices rose **up to 100%**, import tariffs and taxes rose **~40%**, and general inflation hit **40.3%** (May 2023) ([GlobalPETS Egypt](https://globalpetindustry.com/article/pet-industry-egypt/)). Local brands went from **<5% to >30%** share. That last number is usually read as a success story; in market-size terms it is a **downgrade** — consumers moved from Royal Canin and Hill's to Alpha, Migma and Ozzo. Same pets, cheaper bags, smaller market.

**(c) Morocco sits inside the EU pet-food supply chain; Egypt does not.** Morocco imported **€107.5m ($118.4m) of pet food in 2022, up 11.3%, sourced 30% from France and 22.4% from Spain** ([GlobalPETS Morocco](https://globalpetindustry.com/article/pet-industry-morocco/)). Mars holds 33% and Nestlé 10% of category revenue. Morocco is a short truck-and-ferry ride from the two largest pet-food exporters in Europe, with the trade agreements and the francophone retail buying culture to match. Egypt is not.

**(d) Formal-retail penetration differs, and Euromonitor measures formal retail.** Morocco's pet food is **60–70% sold through supermarkets** — Marjane, Carrefour/Label'Vie ([GlobalPETS North Africa](https://globalpetindustry.com/article/north-african-pet-industry-a-fast-growing-region-with-untapped-potential/)). Egypt's pet food moves through vet clinics, independent pet shops and bulk repackaging, much of it informal and invisible to a retail-audit methodology. Part of the "gap" is a measurement artefact: **Egypt's market is partly unmeasured, not absent.**

**(e) Egypt's animal population is largely outside the money economy.** The Egyptian SPCA estimates **~50m stray dogs and 100m+ stray cats** ([GlobalPETS Egypt](https://globalpetindustry.com/article/pet-industry-egypt/)). Those animals generate no retail spend, and — critically for this business — no clinic revenue either.

### 1.4 Three reasons to distrust the *level*, though not the *ratio*

The Morocco number is internally inconsistent across sources by up to 6×:

| Source | Morocco figure | Year | Scope |
|---|---|---|---|
| GlobalPETS / Euromonitor | €62.5m | 2025 | "pet retail sales" |
| GlobalPETS / Euromonitor | **$110.1m (€99.2m)** turnover | 2023 | "turnover" |
| GlobalPETS / USDA FAS | **€107.5m** | 2022 | pet food **imports** |
| Statista Consumer Market Outlook | **$384m** → $590.8m (2029) | 2024 | "pet food" |

[GlobalPETS Morocco](https://globalpetindustry.com/article/pet-industry-morocco/), [Statista Morocco pet food](https://www.statista.com/outlook/cmo/food/pet-food/morocco).

Note that **2022 imports (€107.5m) exceed 2025 retail sales (€62.5m)**, which is impossible on its face. These are different measurement scopes wearing the same label. Statista's Algeria figure ($292.1m in 2024, [Statista](https://www.statista.com/outlook/cmo/food/pet-food/algeria)) sits in the same incompatible universe. **Do not average across these sources.**

**What survives:** the €62.5m vs €23m comparison is apples-to-apples because it is one source, one year, one method. The **ratio is trustworthy; the absolute level is not.**

### 1.5 The part that actually matters — and it changes the conclusion

**Pet retail spend flows through supermarkets. Aleefy is sold against clinic revenue.** A 2.7× gap in supermarket pet food tells you almost nothing directly about whether a Moroccan vet clinic can pay more per month than an Egyptian one.

The number that does tell you that is the **consultation fee**:

| Country | Standard consultation | Emergency / night | Source |
|---|---|---|---|
| **Morocco** | **150–250 MAD** (~$16–27) | 300 MAD emergency / 500 MAD night | [SPA du Maroc, survey of private clinic rates](https://spadumaroc.com/resources/moroccan-vets/tarifs-veterinaires-au-maroc/) |
| **Egypt** | **300–500 EGP** (~$6–10) | — | [the30vetcenter.com](https://the30vetcenter.com/%D8%B3%D8%B9%D8%B1-%D8%A7%D9%84%D9%83%D8%B4%D9%81-%D8%A7%D9%84%D8%A8%D9%8A%D8%B7%D8%B1%D9%8A-%D9%81%D9%8A-%D9%85%D8%B5%D8%B1/) |

(One lower Moroccan list showing 50 MAD consultations exists — [expat.com forum](https://www.expat.com/forum/viewtopic.php?id=482542) — but the 150–250 MAD survey is the better-documented private-clinic range.)

**The conclusion survives, but for a different reason than the headline suggested.** Moroccan clinics charge roughly **2–3× Egyptian clinics per consultation**, in a currency that has not collapsed. That is a real, defensible reason to expect Moroccan clinics to bear a higher subscription price. It is *not* 2.7× because of pet food in Marjane; it is 2–3× because Moroccan household incomes are higher, more stable, and denominated in a managed currency.

**Verdict on the prior data point: TRUE, IMPORTANT, AND FOR THE WRONG REASON.** Use the consultation-fee gap in any pricing model. Do not use the retail-market gap.

---

## 2. COUNTRY FILES

### 2.1 MOROCCO 🇲🇦

**Clinic count**

| Figure | Value | Date | Source |
|---|---|---|---|
| Total registered veterinarians (ONV) | ~1,400 | **2013** | [La Vie Éco](https://www.lavieeco.com/affaires/lactivite-des-veterinaires-evolue-favorablement-27779/) |
| — of which private practice | **948** | 2013 | same |
| — public sector (Min. Agriculture / ONSSA) | ~400 | 2013 | same |
| — teaching at IAV Hassan II | ~50 | 2013 | same |
| "Cabinets et cliniques vétérinaires" | **~1,964** | 2025 | [LesEco.ma](https://leseco.ma/maroc/cliniques-veterinaires-au-maroc-un-marche-en-plein-essor.html) (retrieved via search index; site unreachable directly) |
| Telecontact business directory listings, "vétérinaire" | **450** | Jul 2026 | [Telecontact.ma](https://www.telecontact.ma/maroc/veterinaire-.html) |

⚠️ **The 1,964 figure is suspect.** It exceeds the ONV's own private-vet count (948) by 2×. Either the ONV number is a decade stale (likely — it is from 2013), or LesEco is counting registered business entities including livestock practice, mobile services and pharmacies. The **ONV publishes no current headcount** ([veterinaires.ma](https://www.veterinaires.ma/)).

**Working estimate of addressable companion-animal clinics: 300–700**, concentrated in Casablanca, Rabat, Marrakech, Tangier and Agadir. `[ESTIMATE — triangulated from the four sources above, not published]` This is **the largest addressable base in the entire study, and larger than Egypt's 350–500.**

Sector direction is confirmed: the profession is shifting from rural/livestock to urban companion-animal, with specialised clinics multiplying in major cities and equipment investment accelerating ([LesEco.ma](https://leseco.ma/maroc/cliniques-veterinaires-au-maroc-un-marche-en-plein-essor.html)).

**Market size** — see §1. €62.5m retail (2025), 2.65m pets, 34% household ownership, 60–70% supermarket channel.

**Ability to pay** — GDP/capita ~**$4,840–5,150** ([Trading Economics](https://tradingeconomics.com/morocco/gdp-per-capita), [Statista/IMF](https://www.statista.com/statistics/502801/gross-domestic-product-gdp-per-capita-in-morocco/)). Consultation **150–250 MAD**; dog castration from 800 MAD; bitch spay 900–1,500 MAD ([SPA du Maroc](https://spadumaroc.com/resources/moroccan-vets/tarifs-veterinaires-au-maroc/)). No Morocco-specific vet software pricing found. The dirham is a managed float and has not devalued — **you can price in MAD without FX risk destroying the contract value**, which is not true of EGP.

**E-invoicing — the wedge, arriving January 2027**

| Phase | Date | Who |
|---|---|---|
| 1 | **1 Jan 2026** | Large companies subject to corporate tax (IS) |
| 2 | **1 Jul 2026** | Medium enterprises |
| 3 | **1 Jan 2027** | **SMEs/VSEs with turnover < 10M MAD**, and auto-entrepreneurs > 500,000 MAD |

Legal basis: Article 145-9 CGI framework, operationalised via the **2024 Finance Law**, DGI-run. Model: **clearance** — every invoice must be validated by the DGI platform before it is legally valid. Format: **UBL 2.1 or CII** XML with qualified electronic signature, submitted via API to the DGI "xHub" platform.
Sources: [Sage Maroc](https://www.sage.com/fr-ma/blog/facturation-electronique-maroc-2026/), [EDICOM](https://edicomgroup.com/blog/morocco-electronic-invoicing), [Upsilon Consulting](https://www.upsilon-consulting.com/facturation-electronique-maroc-2026/).

**A veterinary clinic lands squarely in the January 2027 wave.** That is an ~18-month runway — enough to build and be first, and short enough that the pain is already being talked about.

**Two caveats.** (i) The full technical API specification was **not yet published** at time of writing; integrators say they will build connectors "once DGI publishes the technical specifications" ([tax2gov](https://tax2gov.com/morocco-dgi-e-invoicing-api/), [Oasis Techno Cloud](https://oasistechnocloud.com/blog/facturation-electronique-b2b-maroc/)). (ii) An **"approved dematerialization operator"** accreditation concept exists but its requirements are not detailed in any primary DGI document reached here — `[UNVERIFIED — check dgi.gov.ma directly before committing engineering time]`. Sage states certified service providers "could eventually" assume the clearance role, with DGI providing it directly at launch.

**Language — the real barrier, and it is not technical**

- **Legally, French is not required.** Article 145 CGI does not mandate an invoice language; Arabic, French and English are all acceptable ([FatouraPlus on Art. 145](https://fatouraplus.com/guide-auto-entrepreneur/mentions-obligatoires-facture-maroc-art-145/)).
- **In practice, French is the working language of business.** Moroccan invoicing/accounting SaaS is French-first — FactureGo markets itself as "the only Moroccan invoicing software with native Arabic support," which tells you Arabic is the *exception* ([FactureGo](https://facturego.ma/facture-en-arabic-maroc)).
- **Veterinary clinical staff are trained entirely in French.** IAV Hassan II's veterinary programme, curriculum and materials are French-medium ([IAV Hassan II](https://iav.ac.ma/fr/medecine-veterinaire)). A Moroccan vet writes clinical notes in French, not Arabic.
- **Accountants work in French.** Amazigh has no presence in business software despite official co-status.

**Split verdict: clinical staff = French. Accountants = French. Arabic is legal but not the norm anywhere in the workflow.** Aleefy does **not** work unchanged in Morocco. It needs a full French locale — which, given the product already handles two locales including RTL, is the cheapest class of i18n work (a third LTR locale on existing infrastructure). But the *product* is the easy part. **Sales calls, support tickets, onboarding, documentation and marketing must all be in French.** One of the two founders must be able to run a support conversation in French. That is the gate.

**Competition** — French veterinary PMS vendors are present and priced aggressively: **Vetup** from **€19/month HT** ([vetup.com](https://www.vetup.com/)), plus **Vétocom** ([vetocom.fr](https://www.vetocom.fr/)) and **Vet'Phi** ([logphi.com](https://www.logphi.com/logphi_web/fr/logiciel-vetphi.awp)). **MedERP** claims production deployments in 10+ countries including Morocco and Algeria ([mederp.net](https://www.mederp.net/)). These are real incumbents — but they are built for French tax law, not Moroccan DGI clearance, and none has an Arabic interface. **No Arabic-language vet PMS and no Gulf vendor was found operating in Morocco.**

**Payment** — 31.7% debit card ownership, 1.05% credit card ([Findex 2021 via TheGlobalEconomy](https://www.theglobaleconomy.com/rankings/people_with_debit_cards/)). PayPal supported ([supportedcountries.com](https://supportedcountries.com/paypal/)). Functioning banking, no sanctions, no exotic FX controls. **Lowest payment friction in the study, alongside Jordan and Tunisia.**

---

### 2.2 JORDAN 🇯🇴

**Clinic count** — Jordan Veterinary Association (نقابة الأطباء البيطريين الأردنيين), founded 1972 with ~50 members; **current membership is not published** and the official site returned a certificate error ([jordan-vet.org](https://www.jordan-vet.org/mjless.php)). The only directory proxy found lists **11 clinics for the entire country**, nearly all in Amman ([evcindex.com Jordan](https://www.evcindex.com/loc/%D8%B9%D9%8A%D8%A7%D8%AF%D8%A9-%D8%A8%D9%8A%D8%B7%D8%B1%D9%8A%D8%A9-%D9%81%D9%8A-%D8%A7%D9%84%D8%A3%D8%B1%D8%AF%D9%86/)) — obviously a thin directory, not a census.

**Working estimate: 15–40 companion-animal clinics**, Amman-dominant with a handful in Irbid and Zarqa. `[ESTIMATE — NO SOURCE]` **This is a very small market.**

**Market size** — no country figure available. Proxy: Jordan imported **5.6k tonnes of dog and cat food in 2024, 8.8% of Middle East imports**, projected to grow from ~2.4m kg (2023) to ~2.9m kg (2028) ([IndexBox](https://www.indexbox.io/blog/dog-and-cat-food-middle-east-market-overview-2024-5/), [Reportlinker](https://www.reportlinker.com/clp/country/5704/726417)). The same source notes non-GCC markets including Jordan have **per-capita pet food consumption below 0.5 kg/year**.

**Ability to pay** — GDP/capita **$4,579** (2025, [Trading Economics](https://tradingeconomics.com/jordan/gdp-per-capita)); IMF-basis figures run higher (~$5,600), so treat as a **$4,600–5,600 band**. **No Jordanian clinic publishes a standalone consultation fee.** One Amman clinic bundles: vaccination package **15 JOD**, grooming ~**20 JOD** ([vet-man.com](https://vet-man.com/)). No Jordanian clinic-software vendor publishes monthly pricing — every one found (Daftra, Easy Clinic, Medicakare, MDAD Tech) routes to "request a demo."

**E-invoicing — the strongest wedge in the study, and it is already live**

**JoFotara**, run by the Income and Sales Tax Department (ISTD). Registration deadline was **31 May 2024**; **Phase 2 became fully mandatory on 1 April 2025** across B2B, B2C and B2G. Clearance model — ISTD validates in real time. **Only invoices issued through JoFotara are valid for VAT deduction or expense recognition**; non-compliant firms lose eligibility for government tenders.
Sources: [invoiceq.com/connecting-to-jofotara](https://jo.invoiceq.com/en/e-invoicing/connecting-to-jofotara/), [flick.network](https://www.flick.network/en-jo/e-invoicing-jordan-jofotara), [EDICOM](https://edicomgroup.com/blog/jordan-prepares-to-launch-the-electronic-invoice).

**ISTD has stated no sector or entity type is exempt.** The narrow turnover carve-outs that exist — retail under **JOD 75,000/yr**, bakeries under **JOD 150,000/yr**, restaurants under **JOD 75,000/yr** — **explicitly do not extend to medical, legal, financial, engineering, accounting or consulting professionals** ([flick.network](https://www.flick.network/en-jo/e-invoicing-jordan-jofotara)). A veterinary clinic is a professional service. **It is in scope regardless of size, and it is in scope today.**

A public API for third-party integration exists and multiple vendors document connecting to it. Whether ISTD publishes a full open specification without a gatekeeping step is `[UNVERIFIED]` — the integration guides found are on vendor sites, not istd.gov.jo.

**This is the only market in the study where the compliance pain is present-tense rather than future-tense.**

**Language** — Arabic and English. **The product works completely unchanged.** No French, no new locale, no new documentation set. Jordanian Arabic is close enough to Egyptian for support to run without friction, and Egyptian professional Arabic is universally understood in Jordan.

**Competition — and this is the problem.** **bAItari is built in Amman.** Its own site states it was built "in Amman... for the Arab World," Arabic and English interface, cloud vet PMS with records, booking, owner communication and billing ([baitari.vet](https://baitari.vet/en), [Arabic pets page](https://baitari.vet/use-cases/pets)). No pricing is disclosed and no client countries are named. **Entering Jordan means fighting the closest direct competitor on its home ground, in a market of perhaps 30 clinics.**

By contrast, **VetICare names only Saudi Arabia, UAE, Oman and Egypt** among its 500+ clients — **no Jordan, Lebanon or Iraq presence found** ([veticareapp.com](https://veticareapp.com/)). **Yolo Clinic** targets the UAE specifically (DHA and UAE VAT references, +971 contact) ([yolo.clinic](https://yolo.clinic/ar/%D8%A8%D8%B1%D9%86%D8%A7%D9%85%D8%AC-%D8%A7%D8%AF%D8%A7%D8%B1%D8%A9-%D8%B9%D9%8A%D8%A7%D8%AF%D8%A9-%D8%A8%D9%8A%D8%B7%D8%B1%D9%8A%D8%A9/)). **VetC** (Saudi, 65+ clinics, integrated accounting and tax reporting) is Gulf-focused ([Haraj listing](https://haraj.com.sa/en/1187110156/)). Global vendors (ezyVet, Provet Cloud, Vetstoria, Shepherd) show **no Levant marketing, clients or localisation**.

**Payment** — **32.4% debit card ownership, the highest in the study** ([Findex 2021](https://www.theglobaleconomy.com/rankings/people_with_debit_cards/)). Functioning banking, no sanctions. PayPal allows sign-up but has reported withdrawal restrictions ([jeecart.com](https://jeecart.com/top-paypal-banned-countries-list-2025-updated-guide-for-users-worldwide/)) — `[UNVERIFIED]`, verify directly. **Low friction.**

---

### 2.3 TUNISIA 🇹🇳

**Clinic count** — `[NO USABLE DATA]`. The CNOMVT (Conseil National de l'Ordre des Médecins Vétérinaires de Tunisie) maintains a "Statistiques de la profession" page which **could not be retrieved** — the domain timed out on repeated attempts ([veterinaire.tn](http://www.veterinaire.tn/services/les-statistiques-de-la-profession.html)). The only sourced total is **"more than 1,500 veterinarians"**, from a 2013 article ([Leaders.com.tn, Oct 2013](https://www.leaders.com.tn/article/12394-la-medecine-veterinaire-en-tunisie-radioscopie-d-une-profession-meconnue)). No private/public split, no small-animal split.

**Working estimate: 100–250 companion-animal clinics** in an 12m-person country. `[ESTIMATE — NO SOURCE. This is the weakest number in the document.]`

**Market size** — `[NO DATA]`. No Euromonitor, Statista or GlobalPETS Tunisia figure was found.

**Ability to pay** — GDP/capita **~$4,660 (2025)** ([IMF](https://www.imf.org/external/datamapper/profile/TUN)). Consultation **30–80 TND** (~$10–26), commonly quoted 50–80 TND; vaccination 40–60 TND; sterilisation 150–250 TND ([Proxity.tn](https://proxity.tn/visite-veterinaire-tunisie-prix-guide/)). **Best software price anchor in the whole study:** Tunisian medical practice software **Olycab charges 50 TND/month (~$16)** for a solo-practitioner plan with two licences, +20 TND per additional licence, 14-day free trial ([olycab.com/tarif](https://olycab.com/tarif)). That is a real, published, local benchmark for what a small clinic pays for practice-management software in the Maghreb.

**E-invoicing — live now, and the most technically accessible mandate anywhere in this study**

**Article 53 of the 2026 Finance Law** extended mandatory e-invoicing to **all service-sector providers and liberal professions from 1 January 2026** — an estimated 380,000+ businesses, ~85% of the services economy. **No turnover carve-out was found.** Previously mandatory scope was B2G plus B2B sales of medicines and fuels.
Sources: [VATupdate, Jan 2026](https://www.vatupdate.com/2026/01/29/337288/), [VATupdate on the services expansion](https://www.vatupdate.com/2026/01/14/tunisia-expands-mandatory-e-invoicing-to-all-vat-service-transactions-from-january-2026/), [Luca Pacioli guide](https://lucapacioli.com.tn/blog/electronic-invoicing-tunisia-2026-complete-guide-for-service-providers-el-fatoora-ttn-compliance).

**A veterinary clinic is a liberal profession. It is in scope now.**

Platform: **Tunisie TradeNet (TTN)**, product name **"El Fatoora,"** with DGI and ANCE. Format: **TEIF** (Tunisian Electronic Invoice Format) — XML governed by a **public XSD schema**, digital signature via **TUNTRUST**, unique invoice ID, QR code. Public developer integration guides exist, and there is **open-source TEIF middleware on GitHub** ([noqta.tn TEIF spec guide](https://noqta.tn/fr/tutorials/format-teif-specifications-techniques-tunisie-2026), [noqta.tn TTN API guide](https://noqta.tn/fr/tutorials/integration-api-ttn-facturation-electronique-tunisie-2026), [tekru-labs/elfatoora-middleware](https://github.com/tekru-labs/elfatoora-middleware)).

Accreditation is **platform onboarding, not third-party vendor certification** — you register on the TTN El Fatoora portal. This is materially lighter than Saudi ZATCA. Penalties: audits, exclusion from public tenders, administrative sanctions, reportedly with no grace period ([VATupdate](https://www.vatupdate.com/2026/01/01/tunisia-2026-electronic-invoicing-el-fatoora-ttn-compliance-guide-for-service-providers/)).

**Of all ten countries, Tunisia has the mandate that is simultaneously (a) in force, (b) covering small clinics, and (c) documented well enough that a two-person team could integrate against it without a partner.**

**Language** — same French/Arabic split as Morocco. **No Tunisia-specific legal citation on invoice language was retrieved** — this is inferred from the regional pattern (French-medium veterinary and higher education, French-dominant private-sector accounting software) rather than confirmed. `[UNVERIFIED — treat as regional inference]` Assume French is required in practice.

**Competition** — no Tunisia-specific vet PMS found. French vendors (Vetup, Vétocom) are the notional incumbents. **Effectively white space.**

**Payment** — **20.5% debit card, 2.4% credit card** ([Findex 2021](https://www.theglobaleconomy.com/rankings/people_with_debit_cards/)) — the weakest card penetration of the three payable markets. PayPal supported ([supportedcountries.com](https://supportedcountries.com/paypal/)). ⚠️ **Tunisia operates exchange controls and the dinar is not freely convertible** — this was **not verified with a primary source in this research** and is `[UNVERIFIED]`. **Check before committing.** If outbound payment for foreign SaaS requires Central Bank approval, Tunisia's ranking drops sharply.

---

### 2.4 LEBANON 🇱🇧

**Clinic count — the best-documented country in the study.** Lebanese Veterinary Association (est. 1995, de facto registrar under the Ministry of Agriculture): **432 registered veterinarians (2023), 384 active.** Of the active: **150 self-identify as small-animal**, 200 large-animal, 50 Ministry of Agriculture, 35 municipal slaughterhouses, 100 recent graduates unclassified (subgroups overlap and sum above 384, as reported). **25 private practices** are used for clinical student training ([Juniper Publishers](https://juniperpublishers.com/jdvs/JDVS.MS.ID.555922.php)).

**Working estimate: 60–120 companion-animal clinic premises.** `[ESTIMATE from the 150 small-animal vets above]`

**Market size** — no value figure. Import proxy: **12k tonnes of dog and cat food in 2024**, more than Saudi Arabia's 30k relative to population and ahead of every other non-GCC Arab market ([IndexBox](https://www.indexbox.io/blog/dog-and-cat-food-middle-east-market-overview-2024-5/)). **Lebanon has, per capita, the strongest pet culture in the Arab world outside the Gulf.**

**Ability to pay — this is the problem, and one figure settles it.** GDP/capita **$5,391 (2024), down from $5,835** ([Trading Economics](https://tradingeconomics.com/lebanon/gdp-per-capita)). During the collapse a 10 kg bag of Royal Canin cat food cost **772,000 LBP against a 700,000 LBP minimum monthly wage**; roughly **60 veterinarians left their clinics** and dozens of pet-supply stores closed ([Xinhua, Sept 2022](https://english.news.cn/20220918/e96254b4b7294c7999b14d8d82fb15cf/c.html)); rescue groups reported 30–40% increases in abandonment. Most telling: **the LVA cut its own annual membership fee from US$233 to US$35** because members could not pay it ([Juniper Publishers](https://juniperpublishers.com/jdvs/JDVS.MS.ID.555922.php)). **If a vet cannot afford $233 a year for their licence, they cannot afford $60 a month for software.**

**E-invoicing** — **no comprehensive mandate.** The 2026 Budget Law introduces a **monthly electronic declaration** for stamp-duty-liable invoices to the Ministry of Finance — a reporting obligation, not a clearance mandate. `[UNVERIFIED in detail — no primary MoF document was retrieved; only the general direction is corroborated]` **No wedge.**

**Language** — Arabic, French and English all function. Lebanese business runs comfortably in English. **Product works unchanged.**

**Competition** — white space. No vendor of any kind found operating in Lebanon.

**Payment — conditional and unreliable.** **15.9% debit card ownership, lowest of the Levant** ([Findex 2021](https://www.theglobaleconomy.com/rankings/people_with_debit_cards/)). Since October 2019 banks have imposed **informal capital controls never formalised into law**, blocking nearly all external transfers from pre-October-2019 accounts; an estimated **$72 billion in deposits remains frozen** ([EX NIHILO](https://exnihilomagazine.com/lebanon-banking-crisis-capital-controls/)). The workaround is the **"fresh dollar" account** — opened after Oct 2019 and funded with new cash or wire — which can transfer relatively freely. As of 2026 international dollar wires out of Lebanese accounts remain heavily restricted with no normalisation timeline ([Middle East Insider, Apr 2026](https://themiddleeastinsider.com/2026/04/05/lebanon-currency-collapse-2026-lira-crisis-war/)).

**Net: a Lebanese clinic with a fresh-dollar account can pay you. One without cannot. You will not know which until you ask.**

---

### 2.5 IRAQ 🇮🇶

**Clinic count — beware the trap number.** A syndicate-linked report states Iraq has **1,500 officially licensed veterinary clinics, of which 300–350 in Baghdad**, and that private clinics cover **90% of livestock veterinary services** ([Zagros News](https://zagrosnews.net/ar/news/65248)). **That 1,500 is overwhelmingly livestock practice. Do not present it as companion-animal clinic density.** One secondary claim puts total Iraqi veterinarians at "approaching 5,000" `[UNVERIFIED]`. The Iraqi Veterinary Syndicate publishes no membership figure; the Kurdistan Veterinarians Syndicate site returned 403.

Directory proxy is useless: evcindex lists **one clinic in all of Iraq**.

Named companion-animal operations found: Erbil Pet Company (est. 2008, clinic + shop), Pet Vet Clinic Erbil, Finest Veterinary (Sulaymaniyah); VetCity operates branches in Erbil, Sulaymaniyah, Kirkuk and Baghdad but is primarily a pharma distributor ([vetcityiq.com](https://www.vetcityiq.com/en)).

**Working estimate: low hundreds of companion-animal clinics nationwide**, Baghdad + Erbil + Sulaymaniyah. `[ESTIMATE — NO SOURCE]`

**Market size** — `[NO DATA]`. Statista's Iraq pet supplies outlook is fully paywalled ([Statista](https://www.statista.com/outlook/cmo/pet-animal-supplies/iraq)). Qualitative evidence of a real and growing market: Kurdistan reporting describes a genuine cultural shift toward dog and cat ownership, with imported small breeds from Ukraine, Russia, Serbia and Belarus, demand highest in Sulaimani then Duhok, Kirkuk and Erbil ([Rudaw](https://www.rudaw.net/english/business/06022018), [Kurdish Globe](https://kurdishglobe.krd/growing-trend-of-pet-ownership-in-kurdistan/)). Baghdad's al-Ghazil market remains the central pet bazaar, and an exotic-pet trend has emerged with **lion and tiger cubs at $2,000–$4,000 each** ([Shafaq News](https://shafaq.com/en/society/Lions-in-houses-exotic-pet-trend-grows-in-Iraq)). **There is discretionary money here.**

**Ability to pay** — GDP/capita **$4,005 (2025)** ([Trading Economics](https://tradingeconomics.com/iraq/gdp-per-capita)); IMF-basis quotes ran to $5,803, so treat as a **$4,000–5,800 band**. **No Iraqi vet clinic publishes a consultation fee** and no Iraqi clinic-software vendor publishes monthly pricing — targeted Arabic searches returned only human medical fees. `[NO DATA — any figure quoted for Iraq vet fees would be fabricated]`

**E-invoicing** — **none.** The General Commission for Taxes has no formal e-invoicing system, attributed to infrastructure constraints; vendor marketing describing a future rollout is speculative with no confirmed government dates ([tax2gov](https://tax2gov.com/iraq-gct-e-invoicing-api/)). **No wedge.**

**Language** — Arabic. **Product works unchanged.** Best pure language fit in the study alongside Jordan.

**Competition** — **complete white space.** No Gulf vendor, no global vendor, no local vet PMS found.

**Payment — this is what kills it.** **9.8% debit card ownership, the lowest in the entire study** ([Findex 2021](https://www.theglobaleconomy.com/rankings/people_with_debit_cards/)). The Central Bank of Iraq runs a **daily dollar auction** that effectively sets the rate ([MyFXBuddies, Jul 2026](https://www.myfxbuddies.com/2026/07/iraq-shocks-banks-central-bank-reverses.html)) and maintains an **active list of Iraqi banks barred from USD transactions**, still being amended as of February 2026 ([Iraq Business News](https://www.iraq-businessnews.com/2026/02/23/iraqi-banks-restricted-from-us-dollar-transactions-full-list/)). A July 2026 directive loosened cash-dollar withdrawals only under narrow conditions. An economist quoted **20 July 2026** cautioned that full dollar integration remains "out of reach" because major US banks refuse correspondent relationships with restricted Iraqi banks over compliance risk ([Iraqi News](https://www.iraqinews.com/iraq/ziad-al-hashemi-iraq-banking-reform-us-dollar-restrictions-2026/)). **PayPal does not support Iraq. Wise does not offer business accounts in Iraq** ([iraqtech.io](https://iraqtech.io/how-to-get-paid-as-an-online-freelancer-in-iraq/)).

**Iraq is the most frustrating entry in this study: perfect language fit, real money, zero competition, growing pet culture — and no way for a two-person Cairo company to collect a recurring monthly fee.** The only viable route is a local partner who collects cash and settles periodically, which requires capital and trust this team does not have. **Park it. Revisit if a credible partner appears.**

---

### 2.6 ALGERIA 🇩🇿 — **DISQUALIFIED ON PAYMENT**

**Clinic count** — no functioning veterinary order existed for years. A 2019 law amending Law 88-08 created an **Ordre National des Vétérinaires**, with registration proceeding via the "Autorité Nationale Vétérinaire" portal rather than a public roll ([APS](https://www.aps.dz/sante-science-technologie/90883-le-texte-de-loi-relative-a-la-medecine-veterinaire-adopte-par-le-conseil-de-la-nation), [MADR portal](https://psl.madr.gov.dz/dsv/inscription-alautorite-nationale-veterinaire-avn/)). A widely-repeated claim of **~20,000 vets with >60% in private practice** could not be corroborated against any primary source and is inconsistent with Morocco and Tunisia at comparable population — **treat with real scepticism** `[UNVERIFIED]`. **No companion-animal split exists.**

**Market size** — Statista puts Algerian pet food at **$292.1m (2024) → $506.1m (2029), 11.6% CAGR** ([Statista](https://www.statista.com/outlook/cmo/food/pet-food/algeria)). As noted in §1.4, this figure lives in a different measurement universe from the GlobalPETS/Euromonitor retail numbers and cannot be compared to them. On its face Algeria looks like the second-biggest North African market after Morocco.

**Ability to pay** — GDP/capita **~$4,880 (2026 forecast)** ([Trading Economics](https://tradingeconomics.com/algeria/gdp-per-capita/forecast)). **No Algerian vet consultation fee was found in French or Arabic** — directories list clinics but no prices. `[NO DATA]`

**E-invoicing** — **nothing mandatory.** The planned January 2026 mandate **slipped**; no binding legislation has been published and implementation is now considered unlikely before **2027**, and that date is indicative rather than law. Only a **voluntary B2G pilot** launched in 2023. **Paper invoices remain legally accepted.** ([vatcalc.com](https://www.vatcalc.com/algeria/algeria-e-invoicing-mandate-slips/), [sharedserviceslink](https://sharedserviceslink.com/news/algeria-s-e-invoicing-mandate-slips-beyond-2026-as-regulatory-framework-lags)). **No wedge.**

**Language** — Arabic is nominally the legal accounting language, but **French is the de facto working language and regulators accept it without issue**; software vendors build bilingual FR/AR interfaces as standard, partly because Algerian invoices must carry NIF/NIS/RC/AI identifiers for different customer bases ([Merbouhi DGI guide](https://merbouhi.com/blog/mentions-obligatoires-facture-algerie.html), [Symloop](https://www.symloop.com/blog/logiciel-comptabilite-algerie-2024/)). French required in practice.

**Competition** — **VetPro** (vetpro.ink) is a French-language vet PMS explicitly stocking **Algerian medicines** — a genuine local incumbent. **MedERP** also claims Algerian deployments ([mederp.net](https://www.mederp.net/)).

**Payment — the disqualifier, on four independent counts:**

1. **The dinar is non-convertible outside Algeria.** Exporting more than 10,000 DZD in cash is illegal; exchanging DZD abroad is illegal.
2. **Business FX transfers take 1–6 months or longer** through an "almost 30-step" bureaucratic process. Non-hydrocarbon exporters may retain only 50% of export earnings in USD.
3. **There is no legal parallel market** for individuals or businesses to remit funds.
   ([US State Dept Investment Climate Statement 2025](https://www.state.gov/wp-content/uploads/2025/09/638719_2025-Algeria-Investment-Climate-Statement.pdf), [International Trade Administration](https://trade.my.site.com/article?id=Algeria-Foreign-Exchange-Controls))
4. **Crypto is a criminal offence.** The 2018 Financial Law ban was hardened by **Law No. 25-10 (July 2025)** into a sweeping criminal prohibition on all crypto activity — possession, trading, mining, stablecoins — with up to **1 year imprisonment and fines to ~1,000,000 DZD (~$7,700)** ([Decrypt](https://decrypt.co/332890/algeria-bans-all-crypto-activities-including-ownership-and-mining), [CoinsPaid Media](https://coinspaidmedia.com/news/crypto-officially-banned-algeria/)). **USDT is not a workaround; suggesting it exposes your customer to prosecution.**

Card ownership: 22.9% debit, 2.8% credit ([Findex 2021](https://www.theglobaleconomy.com/rankings/people_with_debit_cards/)).

**Algeria is the clearest "good on paper, cannot get paid" market in this study.** 45 million people, a large pet food market, French-speaking, an incumbent you could out-build — and no legal mechanism by which a small Algerian clinic can send you $60 a month. **Do not enter.**

---

### 2.7 LIBYA 🇱🇾

**Clinic count** — `[NO DATA]` on private practice. The only figure found is public infrastructure: the Ministry of Agriculture's National Center for Animal Health runs **~50 local offices and ~300 public veterinary clinics** — livestock and public health, not companion animal ([FAO Libya REMESA plan](https://www.fao.org/fileadmin/user_upload/remesa/library/Libya_REMESA%20RECOMSA%20Com%20Plan%20Final___.pdf)). No veterinary order membership data exists.

**Market size** — `[NO DATA]`. **Consultation fees** — `[NO DATA]`. **Card ownership** — `[NO DATA]`.

**Ability to pay** — GDP/capita **~$6,800 (2025)**, nominally the highest in this study ([Trading Economics](https://tradingeconomics.com/libya/gdp-per-capita)).

**E-invoicing** — none found. Government focus in 2026 is FX stabilisation, not tax digitalisation.

**Payment** — improving but unreliable. The dinar carries a persistent parallel-market gap: **LYD 8.63/USD parallel vs LYD 6.60 official as of 25 July 2026** ([Libya Observer](https://x.com/Lyobserver/status/2080999130847977601)). The Central Bank devalued **14.7% in January 2026** and injected **~$6bn over May–June 2026** ([Libya Herald](https://libyaherald.com/2026/06/central-bank-of-libya-source-to-libya-herald-us-6-billion-injected-over-two-months-measures-expected-to-curb-speculation/)). Genuine 2026 improvements: a **direct FX transfer service for small traders up to $100,000** under Circular 14 of 2026, a reopened **Personal Currency Allocation at $2,000/year**, and a business FX purchase permit of **$8,000–10,000/year** ([Libya Herald, May 2026](https://libyaherald.com/2026/05/central-bank-of-libya-source-to-libya-herald-direct-transfers-will-effectively-end-the-black-markets-monopoly-on-foreign-currency/), [IMF Article IV, Apr 2026](https://www.imf.org/en/news/articles/2026/04/10/mcs-04102026-libya-staff-concluding-statement-of-the-2026-article-iv-consultation-mission)). But the structural shortfall persists — 2025 FX usage ~$31.1bn against oil revenue ~$22.1bn ([Libya Tribune](https://en.minbarlibya.org/2026/03/24/libyas-fx-gap-the-structural-arithmetic-behind-dinar-instability/)).

**Verdict: no data on which to base any decision, moderate-to-high payment friction. Not assessable, therefore not enterable.**

---

### 2.8 SUDAN 🇸🇩 — **DISQUALIFIED**

**Clinic count** — `[NO DATA]`. No veterinary order membership or clinic count exists in any public source. Qualitative: the profession is overwhelmingly livestock; one study of new graduates found only ~27% reported skills gains in companion-animal medicine ([Springer](https://link.springer.com/article/10.1007/s44217-025-00826-7)).

**Market size** — `[NO DATA]`, and any pre-war baseline is meaningless now.

**Ability to pay** — GDP/capita **~$624 (2025)**, reflecting wartime collapse ([Trading Economics](https://tradingeconomics.com/sudan/gdp-per-capita)). Projected GDP contraction of ~42% ([IFPRI](https://www.ifpri.org/blog/sudans-war-is-an-economic-disaster-heres-how-bad-it-could-get/)). Veterinary infrastructure has been severely degraded since April 2023; the central vaccine laboratory was damaged and halted production.

**E-invoicing** — none.

**Payment** — Executive Orders **14098 and 13400 remain in effect**; OFAC added further designations as recently as **29 June 2026** tied to the SAF–RSF conflict ([Federal Register, Feb 2026](https://www.federalregister.gov/documents/2026/02/27/2026-03966/notice-of-ofac-sanctions-actions), [US Treasury](https://home.treasury.gov/news/press-releases/sb0544)). **No clean international payment rail exists for a Sudanese counterparty in 2026.**

**Verdict: disqualified on payment and on active conflict. There is no market to assess.**

---

### 2.9 SYRIA 🇸🇾 — **DISQUALIFIED (improving, but not yet)**

**Clinic count** — `[CONFIRMED BLANK]`. The Syrian Veterinary Medical Association is active but state-linked and livestock/poultry focused. **No membership numbers, no companion-animal clinic counts, no pet-market data of any kind exist in public sources.** This is a genuine data void, not a search failure.

**Ability to pay** — GDP/capita **$670 (2023), down from a 2011 peak of $1,543** ([Trading Economics](https://tradingeconomics.com/syria/gdp-per-capita)). Lowest but one in the study.

**E-invoicing** — none.

**Payment — improving, still binding.** The US **ended comprehensive OFAC Syria sanctions effective 1 July 2025** (EO of 30 June 2025); FinCEN issued exceptive relief in late May 2025 for correspondent accounts with the Commercial Bank of Syria, and Syrian banks have returned to SWIFT ([OFAC FAQ topic 1571](https://ofac.treasury.gov/faqs/topic/1571), [Federal Register, Sept 2025](https://www.federalregister.gov/documents/2025/09/25/2025-18618/amendment-to-the-syria-related-sanctions-regulations)). **However, as of 2026 only 3 of Syria's 12 major commercial banks have relationships with international payment processors**; most cannot do direct fiat transactions and users rely on P2P and neighbouring-country banking ([ClefinCode](https://clefincode.com/blog/global-digital-vibes/en/from-isolation-to-integration-sanctions-lifting-on-syria-the-global-rise-of-syrian-expertiseandmarketpotential)). Targeted sanctions remain on numerous categories of persons. PayPal explicitly unsupported.

**Verdict: no data, no money, fragile rails. Revisit in 3–5 years, not now.**

---

### 2.10 PALESTINE 🇵🇸 — **DISQUALIFIED ON PAYMENT, ACTIVELY WORSENING**

**Clinic count** — **358 registered veterinarians at end of 2023**, per the Palestinian Veterinarians Syndicate cited in a 2024 academic survey ([PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12087241/)). **No small-animal split published.** The Palestinian veterinary literature is entirely production-animal focused, suggesting companion-animal practice is a very small undocumented niche in the Ramallah/Jerusalem area.

**Ability to pay** — GDP/capita **$2,592 (2024), down ~16% year on year** (World Bank).

**E-invoicing** — none. VAT exists at 16% ([PwC Tax Summaries](https://taxsummaries.pwc.com/palestinian-territories/corporate/other-taxes)) and a 2022–2026 tax revenue strategy exists, but conflict has halted tax administration reform.

**Payment — the most acute constraint in the study, and it is live.** Palestinian banks depend on correspondent relationships with **Bank Hapoalim and Bank Discount** operating under Israeli Ministry of Finance indemnity waivers, covering shekel settlement, import payments and wages ([IndraStra, Jul 2026](https://www.indrastra.com/2026/07/when-banking-becomes-geopolitics.html)). **As of July 2026 both Israeli banks have notified Palestinian counterparts of intent to sever these links**, with cutoffs reported for **13 August 2026** and **1 September 2026** ([Middle East Eye](https://www.middleeasteye.net/news/severed-banking-ties-could-hit-aid-palestine-deepen-economic-crisis), [Eshraag News, 23 Jul 2026](https://e.eshraag.com/2026/07/23/israeli-banks-intend-to-cut-off-their-services-from-palestinian-banks-within-weeks-economy/)).

**Verdict: disqualified. Cross-border payment capability is being removed within weeks of this document's date.**

---

## 3. THE PAYMENT PROBLEM ON YOUR OWN SIDE

Before ranking destinations, one structural issue that applies to **every** market equally:

**Stripe does not support Egypt as a merchant country** ([Dodo Payments tracker](https://dodopayments.com/blogs/stripe-supported-countries-alternatives)). Paddle, Lemon Squeezy and 2Checkout merchant eligibility for Egyptian sellers **could not be confirmed either way** in this research `[UNVERIFIED — check each platform's live onboarding flow directly; this is a two-hour task and it gates everything]`.

Egyptian companies **can** legally retain and receive foreign currency; banks are the only permitted channel for outbound transfers, and SWIFT wires convert at the receiving bank's internal rate with a hidden margin ([Andersen Egypt](https://eg.andersen.com/individual-rights-protection/), [Grey.co](https://grey.co/blog/what-egypts-currency-controls-mean-for-international-payments)). Payoneer and Wise are both used by Egyptian freelancers, though Wise has Egypt-specific restrictions — no Wise card for Egyptian residents, cannot send from EGP ([Cenoa](https://www.cenoa.com/blog/payoneer-alternatives-egypt-2026-guide-freelancers)).

Payoneer's per-country support could not be resolved: aggregator sites **contradicted each other directly**, and Payoneer itself states you only learn during sign-up. **All Payoneer country claims in this document are `[UNVERIFIED]`.**

**The honest framing:** for most of these markets the binding question is less "can the customer's country send money out" and more **"can any card acquirer or merchant-of-record accept an Egyptian merchant at all."** Resolve that first. It is cheap to resolve and it determines whether *any* of this is actionable.

---

## 4. RANKING

### 4.1 Weighting, stated explicitly

**Gate (binary, applied before scoring):** can a small clinic in this country legally and practically send a recurring monthly payment to a Cairo company? **No = eliminated regardless of every other factor.**

For markets that pass the gate:

| Factor | Weight | Why this weight |
|---|---|---|
| **Language fit / does the product work unchanged** | **25%** | A two-person team's scarcest resource is time. A market requiring a third locale plus French-language sales, support and docs is not 20% more work — it is a different business. |
| **Addressable clinic count** | **20%** | Egypt-only year-3 ARR is ~$25k. Only a market of comparable or larger size changes the outcome. Anything under ~50 clinics is a rounding error. |
| **Ability to pay per clinic** | **20%** | Price × count is the whole model. A market at 2–3× Egyptian price points is worth two markets at Egyptian prices. |
| **E-invoicing wedge** | **20%** | This is the product's differentiator against both incumbents and inertia. A live mandate converts a "nice to have" into a deadline. Weighted below language and size because a wedge into a market you cannot serve is worthless. |
| **Competition** | **10%** | Real but recoverable. A two-person team can out-support an incumbent locally; it cannot out-spend one. |
| **Practical reachability** | **5%** | Timezone, flight, dialect, diaspora. Matters, but least. |

### 4.2 The ranking

| # | Country | Gate | Clinics | Pay/clinic | Language | Wedge | Competition | Verdict |
|---|---|---|---|---|---|---|---|---|
| **1** | **Morocco** | ✅ Pass | **300–700** — largest in study | 2–3× Egypt, stable MAD | ❌ **French required** | ✅ Jan 2027, 18mo runway, spec immature | ⚠️ French vendors, no Arabic PMS | **Enter — the only market that changes the outcome** |
| **2** | **Jordan** | ✅ Pass | 15–40 — tiny | Unpublished; GDP $4.6–5.6k | ✅ **Works unchanged** | ✅✅ **JoFotara live since Apr 2025** | ❌ bAItari is based in Amman | **Enter — free option, cannot be the growth story** |
| **3** | **Tunisia** | ⚠️ FX controls `[UNVERIFIED]` | 100–250 `[weak estimate]` | 30–80 TND consult; $16/mo software anchor | ❌ French required | ✅✅ **Live Jan 2026, public TEIF spec** | ✅ White space | **Rider on Morocco — once French exists, this is nearly free** |
| **4** | **Lebanon** | ⚠️ Fresh-dollar accounts only | 60–120 | ❌ LVA cut its own fee $233→$35 | ✅ Works unchanged | ❌ None | ✅ White space | Best pet culture, no money, no wedge. Skip. |
| **5** | **Iraq** | ❌ **Fail** | Low hundreds | Real cash, unpublished | ✅ Perfect Arabic fit | ❌ None | ✅✅ Total white space | **The one that hurts.** Park until a local partner exists. |
| **6** | **Libya** | ⚠️ FX rationing | `[NO DATA]` | `[NO DATA]` | Arabic ✅ | ❌ None | `[NO DATA]` | Not assessable. |
| **7** | **Algeria** | ❌ **Fail** | `[UNVERIFIED]` | `[NO DATA]` | ❌ French | ❌ Slipped past 2026 | ⚠️ VetPro, MedERP | **Disqualified. Best "looks good, cannot get paid" example.** |
| **8** | **Palestine** | ❌ **Fail, worsening** | 358 vets, tiny pet niche | $2,592 GDP/cap, falling | ✅ Arabic | ❌ None | ✅ | **Disqualified — banking severed Aug/Sep 2026.** |
| **9** | **Syria** | ❌ **Fail** | `[CONFIRMED BLANK]` | $670 GDP/cap | ✅ Arabic | ❌ None | ✅ | Disqualified. Revisit 3–5 years. |
| **10** | **Sudan** | ❌ **Fail** | `[NO DATA]` | $624 GDP/cap, war | ✅ Arabic | ❌ None | `[NO DATA]` | Disqualified — sanctions + active war. |

### 4.3 Markets disqualified because you cannot get paid, regardless of demand

**In severity order:**

1. **Palestine** — Israeli correspondent banking being severed on stated dates in **August and September 2026**. Time-critical and worsening.
2. **Algeria** — non-convertible dinar, no legal parallel market, months-long FX approval, **crypto criminalised with prison exposure**. The largest market in this study that you must simply walk away from.
3. **Sudan** — active OFAC designations (most recent June 2026) plus civil war. No rail exists.
4. **Iraq** — CBI dollar auction, blacklisted banks, no PayPal, no Wise business accounts, 9.8% card ownership. **Not sanctions — pure banking friction — but the effect on a two-person company with no local presence is the same.**
5. **Syria** — 3 of 12 major banks connected to international processors. Improving, not there.
6. **Libya** — FX rationing with a persistent 30% parallel-market gap; genuine 2026 improvements but access not guaranteed.
7. **Lebanon** — *conditional*, not absolute. A fresh-dollar account works; a pre-2019 account does not.

---

## 5. WHICH TWO COUNTRIES AFTER EGYPT, AND WHY

### #1 — MOROCCO. Because it is the only country in this study that is bigger than Egypt.

Everything else on this list is a rounding error against your existing base. Jordan might be 30 clinics. Tunisia perhaps 150. Lebanon 100 clinics that cannot pay. Morocco is **300–700 addressable companion-animal clinics charging 2–3× Egyptian consultation fees in a currency that has not lost 70% of its value.** If the goal is to get past $25k ARR and support more than two people, **Morocco is the only door in this building.**

The e-invoicing timing is close to ideal. The **January 2027 SME wave lands squarely on veterinary clinics** — turnover under 10M MAD — and it is a **clearance model**, the same architecture as Egypt's ETA, which you have already built against. You have roughly 18 months: long enough to build and be first in a market where every incumbent is a French vendor with no Moroccan tax integration, short enough that clinic owners are already anxious about it.

**The condition, stated bluntly: one of you must be able to work in French.** Not read it — run a support call, write onboarding docs, argue about an invoice. Moroccan veterinarians are trained in French at IAV Hassan II and write their clinical notes in French. Moroccan accountants work in French. Arabic is legally sufficient and practically absent from the workflow, and Moroccan Darija is not a language Egyptian Arabic gets you into anyway. **If neither of you can operate in French, Morocco is not available and this recommendation collapses to a one-country answer.**

The build cost is smaller than it looks. You already ship two locales including a right-to-left one; a third left-to-right locale is the cheapest kind of i18n work you will ever do. **The expensive part is not the product. It is you.**

Two things to verify before committing engineering time: (i) whether the DGI's **"approved dematerialization operator"** accreditation is a real gate or a formality, and (ii) when the **technical API specification actually publishes** — every integrator in the market is currently waiting on it, which is both a risk and your window.

### #2 — JORDAN. Because it costs you almost nothing and the deadline already passed.

Jordan is not a growth market. Fifteen to forty clinics is not a business. Take it anyway, and take it **first**, for three reasons:

**It requires zero product work.** Arabic and English, which you already ship. No new locale, no new documentation set, no translated marketing. The only build is a **JoFotara connector** — and JoFotara has been **mandatory since 1 April 2025** for every VAT-registered taxpayer, with the small-business carve-outs **explicitly not extending to professional services**. A Jordanian vet clinic is out of compliance *today*. Every other market in this study offers you a future deadline; Jordan offers a present one.

**It is your cheapest test of whether you can sell and support across a border at all.** Same timezone, a short flight, mutually intelligible Arabic, a large Egyptian professional presence. If remote cross-border sales does not work in Jordan, it will not work in Morocco either — and you will have learned that for the price of one API integration instead of a French rewrite.

**Payment friction is the lowest in the study.** 32.4% debit card ownership, functioning banks, no sanctions, no exchange controls.

**Go in knowing the catch: bAItari is headquartered in Amman.** You will be fighting the closest Arabic-language competitor on its home ground in a market of perhaps thirty clinics. Do not plan to win Jordan. Plan to **learn** Jordan, bank whatever revenue it yields, and use the JoFotara clearance integration as reusable engineering — the same clearance pattern you will need for Morocco's DGI and Tunisia's TTN.

### The sequencing that follows from this

**Jordan first (months 0–6), Morocco second (months 6–24).** Jordan validates the remote-sales motion at near-zero engineering cost against a live deadline. Morocco is where the revenue is, and its deadline is January 2027 — so the French locale work needs to start no later than early 2026 to land ahead of it.

### And the reason to build French properly rather than cheaply

**Tunisia is the free third market.** Its mandate is already in force (1 January 2026, all liberal professions, no turnover floor), its **TEIF specification is public with an open XSD schema and open-source middleware on GitHub** — the most integrable mandate anywhere in this study — and there is no vet-specific competitor. It is a small market, and its FX convertibility needs checking before you count on it. But once the French locale exists for Morocco, Tunisia costs you one more tax connector.

**The French locale is not a Morocco expense. It is the key to Morocco plus Tunisia — and to Algeria, if that country ever becomes payable.** Budget it as infrastructure, not as a country-specific feature.

### Two things to check this week, before anything else

1. **Can an Egyptian company be a merchant on Paddle, Lemon Squeezy or 2Checkout?** Stripe is confirmed unavailable. If none of the merchant-of-record platforms accept Egyptian sellers, the whole cross-border question is moot and the answer becomes "collect by bank transfer and annual invoice." Two hours of work; it gates everything above.
2. **Can either of you actually run a support call in French?** Answer honestly. It decides whether recommendation #1 exists.

---

## 6. WHAT THIS DOCUMENT DOES NOT KNOW

Stated plainly so no one mistakes silence for absence of risk:

- **No companion-animal clinic count is published for any of the ten countries.** Every count here is a proxy or an estimate. Morocco's — the number the entire #1 recommendation rests on — is triangulated from a 2013 order figure, a press claim that contradicts it by 2×, and a 450-entry business directory.
- **Tunisia's clinic count (100–250) has no source at all.** It is the weakest number in this document.
- **No vet consultation fee is published in Jordan, Iraq, Algeria, Libya or Sudan.** Any figure quoted for those would be invented.
- **No clinic-software monthly price is published in Jordan, Iraq or Morocco.** The only real anchor found anywhere is Tunisian: **Olycab at 50 TND (~$16)/month**.
- **Tunisia's FX convertibility was not verified.** If outbound SaaS payment requires Central Bank approval, Tunisia's ranking falls hard.
- **Morocco's DGI accreditation regime and API specification are both unpublished** as of this writing.
- **Payoneer country support could not be resolved** — public trackers contradicted one another and Payoneer publishes no authoritative list.
- **The €62.5m Morocco figure is internally inconsistent with three other Morocco figures from the same publisher and from Statista**, spanning a 6× range. The *ratio* to Egypt is sound; the *level* is not.
