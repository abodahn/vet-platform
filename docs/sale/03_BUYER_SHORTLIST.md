# 03 — Named Buyer Shortlist

**Asset:** Aleefy — veterinary clinic ERP, Python/Flask + PostgreSQL, ~28,000 LOC, 170 templates, 73 tables, ~380 routes, 549 passing tests, CI, Alembic migrations, 28 modules, fully bilingual Arabic/English with real RTL including Arabic in generated PDFs (4,372 translated strings), one-command per-clinic provisioning, verified backup and restore.

**Status of the business, stated plainly and repeated everywhere in this document because it governs every conversation below:** **zero customers, zero revenue, no support organisation, no operating history.** **Multi-tenant since 2026-08:** one deployment serves many clinics, resolved by subdomain, each with its own database. (This document originally said single-tenant; that is no longer true.) Built in Egypt, priced for Egypt, targeting Egyptian and wider Arabic-speaking veterinary clinics.

**What is therefore actually for sale:** a finished, tested, localised codebase and the time it would take to reproduce it. Not a customer base, not a brand, not an income stream. Every buyer category below is assessed on that basis. Any pitch that implies otherwise will collapse in the first hour of diligence and cost the seller the deal.

**No price is estimated anywhere in this document.** Anchoring on an invented number is worse than none.

---

## 0. How to read this

### Confidence tags

| Tag | Meaning |
|---|---|
| `[V]` | Verified this session by fetching the named URL. Company exists, detail read off the page. |
| `[S]` | Search-derived. The company and URL are real; the specific detail (an email, a branch count) came from a search index or a third-party page rather than a fetch of the primary source. Verify before use. |
| `[P]` | Carried forward from prior research in `../market/`, verified there. |
| `[UNVERIFIED]` | Named for completeness; a claim about it could not be confirmed. |

### The rule that matters most

**Not one name, email address, phone number or URL in this document was invented.** Where a contact route could not be found, the entry says **"no public contact found"** and gives the best available alternative route (a LinkedIn company page, a contact form, a Facebook page). A fabricated contact does not merely fail — it bounces, and a bounced first email from an unknown solo seller is a credibility loss that cannot be recovered on the second attempt.

Where an email address is tagged `[S]`, treat it as a hypothesis. Send to it, but send the same message through the LinkedIn or contact-form route in parallel.

### What this document does *not* redo

`../market/01_COMPETITORS.md`, `02_MARKET_SIZE.md`, `04_GOTOMARKET.md` and `06_ARABIC_MARKETS.md` already establish the competitive field (VetICare, bAItari.vet, Yolo Clinic, Kawakeb, Holool Alghad, Al-Mukhtabarat, Odoo vet modules, Daftra and the human-clinic substitutes) and the Egyptian distributor channel. This document extends that work in one direction only: **who would write a cheque for the code.**

---

# T1 — Buyer categories, ranked by likely price paid

This ranking is mine and it **disagrees with the ordering in the brief.** The brief puts veterinary chains first. I put them fourth and fifth. The reason is structural and worth stating before the list:

> **An operator buys an outcome; a vendor buys an asset.** A clinic group that wants to stop paying per-seat licences does not want a 28,000-line Python repository — it wants someone to run it. Handed a codebase with no support organisation, the group's IT manager immediately reprices the deal downward by the cost of hiring a developer to own it forever. A software house, by contrast, *already has* that developer, so the same asset is worth more to it. **Willingness to pay tracks who already has the capacity to absorb the thing.**

The exception is the pet-care retail and services groups, which rank high not because they can absorb code better than a vet chain but because Aleefy's module coverage — retail POS, grooming, boarding, inventory with batch and expiry, *and* clinical — matches their business shape in a way no veterinary PIMS on the market does. That is a genuine, defensible, non-obvious fit and it is the most under-appreciated finding in this document.

---

## Rank 1 — MENA vertical-software houses and healthcare-IT vendors

**Who they are.** Companies that already build and sell clinic, laboratory, POS or ERP software in Arabic to Arabic-speaking SMEs, and that make money by selling the same system many times.

**The motive — what they get that they cannot easily build.** Three things, in descending order of how hard they are to replicate:

1. **The Arabic PDF problem, already solved.** This is the single most valuable line item in the asset and the one a technical buyer will recognise fastest. Bidirectional Arabic text with correct glyph shaping and joining inside a generated PDF is a notorious failure point — it is where most Arabic-localised products visibly break, and it breaks late, in production, in front of a customer holding an invoice. 4,372 translated strings with working RTL through to PDF output is not a translation task, it is months of the specific unglamorous work that a software house's own team will estimate accurately and dread.
2. **Domain breadth they would have to acquire.** 28 modules covering appointments, EMR, pharmacy with a drug workflow, lab, imaging, inpatient, telemedicine, grooming, boarding, invoicing, double-entry-grade accounting with P&L/cashflow/budget, inventory with batch and expiry, procurement, retail POS, HR, attendance, payroll, a report builder, audit trail, RBAC and TOTP 2FA. A house that sells human-clinic software has perhaps half of this and none of the veterinary specifics. Reproducing the veterinary domain model — species, breeds, weight-based dosing, vaccination schedules, boarding runs — requires access to veterinarians they do not have.
3. **A new vertical without a new product cycle.** They can put this in front of their existing SME sales channel next quarter rather than next year.

**Why they pay more than the others.** They amortise the purchase across every clinic they subsequently sell to. Everyone else amortises it across one deployment.

**Why they might not buy.** The Egyptian and Gulf software-house market has a strong build-it-ourselves reflex and a widespread belief that a junior team can rebuild anything in three months. The counter is the test suite and the CI configuration, not the feature list — see T3.

---

## Rank 2 — GCC pet-care retail and services groups

**Who they are.** Multi-country chains of pet shops that also run grooming salons, boarding, pet taxi, aquarium services and, increasingly, in-store veterinary clinics.

**The motive.** This is the fit that nobody has noticed. A pet retail group with 20+ stores needs, in one system: **retail POS, inventory with batch and expiry tracking, procurement, grooming bookings, boarding, a clinic module, CRM, HR, attendance, payroll, and consolidated accounting** — and it needs all of it in Arabic and English with an Arabic invoice that prints correctly. Today they run a retail ERP for the shops, a separate booking tool for grooming, and either nothing or a foreign PIMS for the clinic, with the accounting stitched together by hand.

Aleefy is one of very few products that covers **retail + grooming + boarding + clinical + accounting in one schema.** Veterinary PIMS vendors do not build retail POS. Retail ERP vendors do not build EMR. That gap is the entire pitch to this category, and it is the pitch that should be led with, verbatim.

**Why they pay well.** They have real capital, they operate across multiple GCC countries so per-seat licensing compounds painfully, and unlike a three-clinic Egyptian group they have an IT function that can own software.

**Why they might not buy.** ~~Single-tenant deployment~~ — **this objection has been answered.** One deployment now serves many clinics by subdomain, each with its own database, and there is a Multi-Branch Control Centre module. Still do not bluff the detail: isolation is database-per-clinic, which is stronger than row-level filtering (a missing WHERE cannot cross a database boundary) but means N databases to back up and migrate. For a 20-store chain that is a feature; for a vendor running hundreds of clinics it is an operating cost. Say which one they are.

---

## Rank 3 — Existing veterinary-software vendors

**Who they are.** VetICare, bAItari.vet, Yolo Clinic, Kawakeb Al-Teknologia, Holool Alghad (which straddles this and Rank 1), Happy Pet Tech, kumoVet, Vetmaster.

**The motive — three distinct ones, which must not be conflated:**

- **Acquire the Arabic work.** Relevant to the non-Arabic vendors: Happy Pet Tech (India, selling into Dubai), kumoVet (Malaysia), Vetmaster (South Africa). For these, Arabic + RTL + Arabic PDFs is the thing they would otherwise have to buy or botch, and it is their key to the GCC market they are already probing. This is the cleanest, least awkward version of the vendor conversation.
- **Acquire module breadth.** Relevant to VetICare and bAItari, who already have Arabic. What they lack is depth in accounting, payroll, procurement, report building and the boarding/grooming/retail side. Prior research records that VetICare's feature page does not surface grooming or telemedicine — both of which Aleefy has.
- **Remove a competitor.** **Be honest with yourself about this one: it is worth almost nothing.** A competitor pays to remove a threat. A product with zero customers and zero revenue is not a threat, and both VetICare (500+ claimed clients, operating since 2020, published $52/month entry pricing) and bAItari know it. Anyone who builds the pitch on "buy me or I'll compete with you" will be politely ignored, and will have shown a competitor the product for free. See T4 for how to handle this category without getting copied.

**Why they might pay.** Build-cost avoidance is a number their CTO can compute, and it is not small for 28 modules and 549 tests.

**Why they will pay less than Rank 1.** They know precisely what it cost to build because they built the same thing. There is no information asymmetry to work with, and they know the seller has no other bidders.

---

## Rank 4 — GCC veterinary clinic groups and hospitals

**Who they are.** Multi-branch veterinary groups in the UAE and Saudi Arabia — nine-branch and five-branch operators, 24-hour multi-specialty hospitals.

**The motive.** Total cost of ownership. A nine-branch UAE group on a foreign cloud PIMS pays per user, per site, per month, in USD or AED, forever, with annual increases and no negotiating leverage. Owning the source removes the licence line permanently and removes the vendor's ability to reprice. It also removes data-residency and export-lock concerns, which matter more in the Gulf than in Europe.

The secondary motive is **customisation without a queue.** A group that wants a workflow changed on a commercial PIMS files a feature request and waits eighteen months. Owning the code means changing it on Tuesday.

**Why they rank fourth and not first.** Three reasons, all of which will surface in the first meeting:

1. **They must hire a developer, forever.** The moment this is understood, the group reprices the offer by the fully-loaded cost of one engineer. That is the single largest price-down lever anyone in this document holds.
2. **Migration risk.** A working nine-branch clinic group with live patient records and live billing does not rip out a functioning system for an unproven one. The realistic entry is a new branch or a second-line use, not a cutover.
3. **They already bought.** At least one confirmed target runs ezyVet (see T2). Displacing an incumbent is a far harder sale than filling a vacuum.

---

## Rank 5 — Egyptian veterinary clinic groups

**Who they are.** The honest finding of this section's research: **Egypt does not really have veterinary chains.** Extensive searching in Arabic and English returned a market of single-clinic practices with a small number of two-to-five-branch groups. The largest verified group found has five branches.

**The motive.** The same TCO logic as Rank 4, but at a scale where it barely works arithmetically, and denominated in EGP against an asset a Gulf or foreign buyer would pay for in hard currency.

**Why they rank last among the operators.** A three-branch Cairo group is not a buyer of a codebase. It is a buyer of a subscription, and the correct commercial action toward it is to sell it a licence, not the company. **Approaching Egyptian clinic groups as acquirers is very likely a waste of the seller's time** — but approaching them as *reference customers first* is exactly how the asset becomes worth more to every other category in this document. See T4.

There is one real exception: a group whose owner is themselves a technologist or has a software business on the side. Those exist and are worth identifying, but they cannot be found by search — they are found by asking.

---

## Rank 6 — Veterinary pharmaceutical distributors — **honest assessment: this category will not buy**

`04_GOTOMARKET.md` correctly identifies distributors as the highest-leverage *sales channel* in the Egyptian market. It does not follow that they are acquirers, and the shortlist should not pretend otherwise.

**Why the theory is attractive.** A distributor's rep already visits every clinic weekly. A distributor that bundled free clinic software with its product orders would create a retention lock on its own customers at near-zero marginal cost, and would acquire clinics for the seller at zero CAC.

**Why it does not translate into a purchase.**

- A distributor's business is working capital, logistics and margin on physical goods. Owning software means owning a support burden, and support of clinical software is a liability shape they have no appetite for and no insurance against.
- The decision-maker is a commercial director whose budget is measured in stock, not capex on intangibles.
- The bundle can be achieved by a **reseller or white-label agreement with no acquisition at all** — which is strictly better for the distributor, and any competent commercial director will say so within ten minutes.

**Therefore:** distributors belong in this document as **channel partners and as introducers to the clinic groups in Rank 4 and 5**, not as buyers. They are listed in T2 for that purpose, and the outreach in T4 treats them differently from everyone else. The only realistic acquisition scenario is a large distributor with an existing digital arm deciding it wants a software product line — possible, but a genuinely low-probability event, and not one to build a process around.

---

# T2 — Named targets with real contact routes

24 named organisations. Every URL was reachable at the time of writing unless noted.

---

## 2.1 — MENA vertical-software houses and healthcare-IT vendors *(Rank 1)*

### 1. Holool Alghad for Information Technology (حلول الغد لتقنية المعلومات) `[V]`

| | |
|---|---|
| **Site** | https://holoolalghad.com/veterinary-clinic |
| **Country** | Saudi Arabia — Riyadh, طريق الشيخ حسن بن حسين بن علي، الحمراء، الرياض 13271 |
| **Size** | Not disclosed. SME software house with a multi-product catalogue. |
| **Contact route** | Phone **+966 11 2244 776**; WhatsApp **+966 55 500 6347**; email address on the site is obfuscated against scraping — use the site contact form at https://holoolalghad.com/ or the LinkedIn link in the site footer. `[V]` |

**Why them specifically.** They are the strongest single fit in this document. They already sell a **veterinary clinic system** alongside a law-office system, POS, accounting, e-commerce and mobile development — i.e. they are a vertical-software house that has already decided veterinary is a market worth being in, and has already built a shallow product for it. Aleefy is the deep version of a product they have shipped a shallow version of. Their existing vet module covers appointments, records, inventory, purchasing, SMS and financial analysis; it does not appear to cover inpatient, telemedicine, boarding, grooming, payroll, a report builder or clinical decision support. They have a Saudi sales channel, Saudi customers and Saudi e-invoicing knowledge that the seller does not.

**The risk, stated plainly.** They are simultaneously the best-fit buyer and a competitor. They can look at Aleefy and choose to deepen their own module instead. Handle under the T4 competitor protocol.

---

### 2. Al-Mukhtabarat (شركة المختبرات) `[V]`

| | |
|---|---|
| **Site** | https://almukhtabarat.com/ · vet product: https://almukhtabarat.com/products/2/ |
| **Country** | **Egypt** — شارع الدكتور محي الدين، المبنى 2، الطابق الأول، الحي الرابع، 6 أكتوبر، الجيزة |
| **Size** | Not disclosed. Established healthcare-IT vendor with three product lines. |
| **Contact route** | Phones **+20 102 178 8994**, **+20 102 109 3626**, **+20 106 405 5136**; WhatsApp **+20 102 178 8994**; LinkedIn **@almukhtabarat**; email is obfuscated on the site — use WhatsApp or LinkedIn. Hours Sun–Thu 09:00–19:00 EET. `[V]` |

**Why them specifically.** The only genuinely Egyptian vendor found in all prior research that already sells into veterinary. Their line-up is a medical LIMS, a **veterinary laboratory and clinic system**, and a medical-device interface layer with named integrations to Roche, Abbott and Sysmex. They have therefore already solved the one thing Aleefy has not — analyser integration — and are missing most of what Aleefy has: full EMR, inpatient, pharmacy, telemedicine, grooming, boarding, retail POS, HR, payroll, accounting.

**This is the most complementary pairing in the document.** Their lab and device-interface strength plus Aleefy's clinic and back-office breadth is a whole product, and neither half competes with the other. They are also local, Arabic-native, Egyptian-priced and reachable by WhatsApp — the lowest-friction serious conversation available to an Egypt-based seller. **Open here.**

---

### 3. CompactSoft (Compact Information Systems) `[S]`

| | |
|---|---|
| **Site** | https://www.compactsoftint.com/ · legacy site http://compactsoft.net/ (TLS certificate mismatch on the legacy domain — use the `compactsoftint.com` site) |
| **Country** | Egypt — Cairo, Heliopolis / Obour Buildings, Salah Salem Street |
| **Size** | Established 1984. Microsoft Dynamics Gold partner. `[S]` |
| **Contact route** | Contact page **https://www.compactsoftint.com/contact** — the canonical route. Search-derived addresses `info@compactsoftint.com`, `sales@compactsoft.net`, `support@compactsoft.net`, and phones **+202 2401 1353** / **+202 2262 4554** `[S]` — **verify before sending; the direct fetch of the contact page failed.** |

**Why them specifically.** A 40-year-old Egyptian ERP house with a Microsoft Dynamics practice and an existing **outpatient clinic management** product (http://compactsoft.net/products-hospital-out-patient-clinic.html). They already sell clinical software to Egyptian and Middle Eastern buyers, already have implementation and support staff, and already have a healthcare sales motion. Aleefy is a vertical extension they could resell through an existing channel.

**Honest caveat.** A Dynamics house is architecturally invested in the Microsoft stack. A Python/Flask codebase is not a natural fit for their delivery team, and that is a real objection, not a soft one. Rank this below Al-Mukhtabarat and Holool Alghad for that reason alone.

---

### 4. Izam / Daftra (دفترة) `[S]` / `[P]`

| | |
|---|---|
| **Site** | https://www.daftra.com/ · company: https://www.daftra.com/en/about-daftra-en/ · parent: izam.co |
| **Country** | Egypt (Cairo), with stated US presence and phone lines for Egypt, KSA, UAE, Jordan, Oman, Qatar, Bahrain, Kuwait `[P]` |
| **Size** | 12+ years as a SaaS provider per their own About page `[S]` |
| **Contact route** | Site contact form at https://www.daftra.com/ ; CEO listed publicly on LinkedIn at https://eg.linkedin.com/in/mohamed-azzam-izam `[S]`. No published direct email found — **no public contact email found.** |

**Why them specifically.** Daftra is the closest thing to an Arabic-native SME business-management platform with published EGP pricing (Basic ~489.50 EGP/mo through Comprehensive ~1,960 EGP/mo per prior research). They have invoicing, inventory, accounting, HR and CRM — and **no veterinary module**. Their entire growth model is adding verticals to an Arabic SME platform. Aleefy is a vertical they do not have, aimed at a customer type they already reach.

**Honest caveat.** They are a horizontal platform; deep clinical modules may be strategically off-thesis for them, and they would likely want the domain model rather than the Flask application. That is still a sale, but a smaller one.

---

### 5. Egyptian Odoo implementation partners — Macrofix, OEC-EG `[P]`

| | |
|---|---|
| **Reference** | Prior research (`01_COMPETITORS.md`) identifies Egyptian Odoo partners selling Arabic-localised ERP implementations. The official partner directory is at https://www.odoo.com/partners/country/egypt-66 |
| **Country** | Egypt |
| **Contact route** | Via the Odoo partner directory listing for each firm — **individual partner contact details not verified this session.** `[UNVERIFIED]` |

**Why them.** An Odoo partner sells Arabic ERP to Egyptian SMEs and is already asked for veterinary by clients (the $272 Odoo vet module exists precisely because that demand exists). A partner that owned a real veterinary product could stop reselling a thin third-party module.

**Honest caveat — this is the weakest entry in Rank 1.** An Odoo partner's whole economics are Odoo. Buying a standalone Flask application means running a second stack, a second support process and a second sales story. More likely they would want to port the domain model into Odoo, which values the asset as specification rather than as software. Approach only after the stronger names have been worked.

---

## 2.2 — GCC pet-care retail and services groups *(Rank 2)*

### 6. Petzone `[V]`

| | |
|---|---|
| **Site** | https://petzone.com/ · UAE https://petzone.com/uae/en/ · KSA https://petzone.com/ksa/en/ |
| **LinkedIn** | https://www.linkedin.com/company/petzone-kuwait `[V]` |
| **Country** | HQ **Kuwait** (Alrai, Street 22). Stores in UAE, Bahrain, Saudi Arabia. |
| **Size** | **201–500 employees** (309 listed on LinkedIn); founded **2001**; describes itself as the largest pet store chain in the Middle East. `[V]` |
| **Contact route** | LinkedIn company page above `[V]`. The `petzone.com` store-locator page returned HTTP 403 to automated fetch — visit in a browser for the published head-office contact details. No verified head-office email found this session. |

**Why them specifically.** The single best structural fit for the product's *full* module set in this document. A 200–500-person, four-country pet specialty retailer running stores, grooming and services needs retail POS, batch-and-expiry inventory, procurement, grooming bookings, boarding, CRM, HR, attendance, payroll and consolidated multi-country accounting — in Arabic and English, with correct Arabic invoices. That is Aleefy's module list almost line for line, plus a clinical module they can grow into. No veterinary PIMS vendor sells them retail POS; no retail ERP vendor sells them a grooming and boarding schedule.

**The objection to prepare for.** Multi-branch. A four-country retailer will not accept one deployment per store. Establish what the product actually supports before this conversation, and do not overstate it.

---

### 7. Pet Corner (Pet Corner Trading L.L.C) `[S]`

| | |
|---|---|
| **Site** | https://petcorner.ae/ · https://petcornerdubai.com/contact |
| **Country** | UAE — head office Al Fardan Building, Sheikh Zayed Road, Dubai `[S]` |
| **Size** | **20+ branches** across Dubai, Abu Dhabi and Fujairah `[S]` |
| **Contact route** | Contact page **https://petcornerdubai.com/contact** — the canonical route. Search-derived: email `info@petcornerdubai.com`, toll-free **800 PET CORNER**, WhatsApp **+971 56 401 3533**, head office **+971 4 614 7058** `[S]` — verify on the contact page before sending. Facebook https://www.facebook.com/petcorner/ `[S]` |

**Why them specifically.** Same thesis as Petzone, and arguably sharper: Pet Corner's published service list spans retail, **in-store grooming, mobile grooming, aquarium services, pet sitting, pet taxi, pet boarding and veterinary care** `[S]`. That is four of Aleefy's modules plus retail, in one operator, across 20+ sites. They also opened a large experiential centre in Dubai Investment Park, which signals capex appetite and a systems-consolidation moment.

---

### 8. The Petshop (UAE) `[S]`

| | |
|---|---|
| **Reference** | Industry coverage: https://globalpetindustry.com/article/pet-retail-revolutions-in-the-uae-and-saudi-arabia/ |
| **Country** | UAE — Dubai, Abu Dhabi, Sharjah |
| **Size** | Not verified. Reported as running 60-minute delivery across three emirates and an app with boarding, grooming and pet relocation booking, CEO named as Amr Hazem `[S]` |
| **Contact route** | **No public contact route verified this session.** The company website was not confirmed; approach via the LinkedIn search for the named CEO, or via the GlobalPETS article's coverage as a conversation opener. `[UNVERIFIED]` |

**Why them.** They have already built a consumer app booking grooming, boarding and relocation — meaning they have already decided services are a business line and have already spent money on software. They are the buyer type that understands why a services back-office matters. **Listed with a warning: contact route unconfirmed. Do not spend time here until the company entity is verified.**

---

### 9. Pets Lounge (Egypt) `[S]`

| | |
|---|---|
| **Site** | https://pets-lounge.com/lounge/ · contact https://pets-lounge.com/lounge/contact/ |
| **Country** | Egypt — Cairo |
| **Size** | Branches in Sheikh Zayed, Nasr City, New Cairo and Concord Plaza Mall, plus nationwide delivery `[S]` |
| **Contact route** | Contact page above `[S]`. Search-derived email `info@pets-lounge.com`, phone **01227780018**, branch lines **0106 664 4041** (Sheikh Zayed), **0106 664 4044** (Nasr City), **0102 084 6456** (New Cairo) `[S]` |

**Why them.** Egypt's clearest multi-branch pet retail operation with an online shop plus grooming and medical services. Realistically a **licence customer rather than an acquirer** — but a strong early reference customer, and Egyptian references are what make every Gulf conversation in this document credible. Treat as customer-first.

---

### 10. Zima Pets Center (Egypt) `[S]`

| | |
|---|---|
| **Site** | https://zimapets.com/ · contact https://zimapets.com/pages/contact-us · grooming https://zimapets.com/pages/grooming-services |
| **Country** | Egypt — New Cairo (Dana Mall), Rehab City, North Coast (Livios Mall) |
| **Size** | Three branches identified `[S]` |
| **Contact route** | Contact page above `[S]`; customer service **01007223289** `[S]`; Facebook https://www.facebook.com/zimapets/ `[S]`; Instagram https://www.instagram.com/zimapets_center/ `[S]` |

**Why them.** Retail plus grooming plus boarding across three sites including a seasonal North Coast location — a genuinely awkward operation to run on spreadsheets, and a good product-fit story. Again: **licence customer, almost certainly not an acquirer.** Listed for completeness of the category.

---

## 2.3 — Existing veterinary-software vendors *(Rank 3)*

> **Read T4's competitor protocol before contacting anyone in this subsection.** Everyone here can copy the product. Some of them can copy it cheaply.

### 11. VetICare Connect / QuadInsight `[V]`

| | |
|---|---|
| **Site** | https://veticareapp.com/ · features https://veticareapp.com/features/ · pricing https://veticareapp.com/price |
| **Country** | **Not disclosed anywhere on the site** — a persistent credibility flag noted in prior research. Named customer countries: KSA, UAE, Oman, Egypt. |
| **Size** | Claims 500+ clients, operating since 2020 `[P]` |
| **Contact route** | Email **support@quadinsight.com** `[V]` — note the parent-company domain, which is the most useful single finding here. LinkedIn **https://www.linkedin.com/company/veticare-connect/** `[V]`; Facebook https://www.facebook.com/VetIcareConnect `[V]`; Instagram https://www.instagram.com/vet.icare/ `[V]`. `/contact` returns 404 — the LinkedIn page is the better route for a commercial approach. |

**Why them specifically.** The direct competitor, with paying Egyptian customers by name. What Aleefy has that they demonstrably do not surface: **grooming, boarding depth, telemedicine, payroll, procurement, a report builder, budgeting and cashflow, clinical decision support, and an on-premise deployment model** for buyers who will not accept cloud. What they have that Aleefy does not: named lab-analyser integrations (Exigo, Edan), a pet-owner mobile app, ZATCA e-invoicing, and 500 customers.

**The honest read.** They are the most likely of any vendor to understand the asset instantly and the least likely to pay well for it, because they know the build cost and they know you have no customers. The realistic deal shape here is not an acquisition of the company but a **purchase of specific components** — the Arabic PDF pipeline, the accounting module, the grooming/boarding subsystem — or an acqui-hire of the developer. Structure the approach around that, not around a whole-asset sale.

---

### 12. bAItari.vet (بيطري) `[V]`

| | |
|---|---|
| **Site** | https://baitari.vet/ · contact https://baitari.vet/contact |
| **Country** | Site states **"صُمِّم في عمان"** — designed in Oman. The contact form defaults to a **+966** (Saudi) country code, which suggests Saudi commercial focus or a Saudi entity. `[V]` |
| **Size** | Not disclosed. Live signup and login; early-stage in presentation. |
| **Contact route** | Email **info@baitari.vet** `[V]`; LinkedIn **https://www.linkedin.com/company/baitari/** `[V]`; Instagram https://www.instagram.com/baitari.vet `[V]`; Facebook https://www.facebook.com/profile.php?id=61587907514319 `[V]`. Contact form states a one-business-day response commitment and explicitly invites **partnership** enquiries `[V]` — use that word. |

**Why them specifically.** They are telling the exact story Aleefy wants to tell — "the digital future of veterinary medicine in the Arab world" — with an Arabic-first product, AI documentation, EHR, a field-examination module and annotated imaging. They appear **narrower and earlier than Aleefy**: strong on clinical and AI, thin on the entire back office (accounting, payroll, HR, procurement, inventory, POS, boarding, grooming). If they have funding and Aleefy has breadth, this is the most natural strategic fit of any vendor on the list.

**Their contact page explicitly solicits partnership enquiries.** That is a lower-risk opening than a cold acquisition pitch and it is the door to use.

---

### 13. Yolo Clinic / Yolo Healthcare `[V]`

| | |
|---|---|
| **Site** | https://yolo.clinic/ar/ |
| **Country** | Regional MENA presence; UAE WhatsApp line; social handle **@yologmbh** implies a German legal entity `[V]` |
| **Size** | Not disclosed. Claims ISO 27001 and ISO 9001, 24/7 support. |
| **Contact route** | Email **info@yolo.clinic** `[V]`; LinkedIn, Facebook, Instagram, YouTube, TikTok linked from the site under **@yolo.healthcare** and **@yologmbh** `[V]` |

**Why them specifically.** They run a human-medical clinic platform *and* a veterinary line, multi-branch, Arabic + English, with mobile apps and ZATCA-oriented tax reporting. Their veterinary line is the smaller sibling of their medical line — exactly the situation where buying a finished vertical product beats funding an internal team to catch up. They also have the ISO posture and support organisation that Aleefy conspicuously lacks, which makes them a buyer who can actually operationalise it.

---

### 14. Kawakeb Al-Teknologia (كواكب التقنية) `[P]`

| | |
|---|---|
| **Site** | https://www.const-tech.org/public/products/5 |
| **Country** | Saudi Arabia |
| **Size** | Not disclosed |
| **Contact route** | Site contact page at https://www.const-tech.org/ — **specific email/phone not verified this session.** `[UNVERIFIED]` |

**Why them.** Their vet module runs **"على الويب مباشرة أو شبكة داخلية"** — web or internal LAN, i.e. **on-premise capable** `[P]`. That is the same deployment philosophy Aleefy supports, which means no architectural argument to have. Their module covers records, appointments, radiology, lab, pharmacy, accounting, RBAC, vaccination tracking and WhatsApp notifications — real overlap, but narrower.

---

### 15. Happy Pet Tech `[V]`

| | |
|---|---|
| **Site** | https://www.happypet.tech/ · demo booking https://www.happypet.tech/book-demo |
| **Country** | India — Bengaluru (New 3169/F, HAL 2nd Stage, Indiranagar, Karnataka 560038) `[S]` |
| **Size** | Founder **Anil Reddy** `[S]`. Sells into **India, UAE, Australia, Philippines, Thailand** `[V]` |
| **Contact route** | LinkedIn **https://www.linkedin.com/company/happy-pet-tech** `[V]`; demo-booking form `/book-demo` `[V]`; Instagram https://www.instagram.com/happypet.tech `[V]`; YouTube https://www.youtube.com/@Happy-Pet-Tech `[V]`. **No published email or phone on the site** — LinkedIn or the demo form are the only routes. |

**Why them specifically.** This is the cleanest, least awkward vendor conversation available, and the one to run first in this subsection. They sell **grooming, boarding, daycare, veterinary and pet-store software** — the same unusual module combination as Aleefy — and they are already selling into the UAE at AED-denominated pricing per prior research. What they cannot have, coming from Bengaluru, is **credible Arabic with correct RTL and correct Arabic PDFs.** They need exactly the one thing Aleefy has that is hardest to buy, they are not competing in Egypt, and they have nothing to gain from copying a product they cannot localise themselves.

**Frame the conversation as Arabic-market entry, not as selling them a company.**

---

### 16. kumoVet (Kumo) `[S]`

| | |
|---|---|
| **Site** | https://kumovet.com/ · group https://kumoteam.co/about/ |
| **Country** | Malaysia — B2-11-01 Meritus Towers @ Oasis Corporate Park, Jalan PJU 1A/2 Ara Damansara, 47301 Petaling Jaya `[S]` |
| **Size** | Group operating since 2015 across beauty/wellness, medical aesthetics, dental and veterinary verticals `[S]`. Prior research records presence in 11 countries `[P]` |
| **Contact route** | Site contact form at https://kumovet.com/ and https://kumoteam.co/ ; LinkedIn presence via the Kumo group. **No published email address found** — `[S]` |

**Why them.** A multi-vertical clinic-software group that has already done the "same platform, different vertical" move four times. They understand vertical acquisition as a growth mechanism. Aleefy would be a fifth vertical *and* a new language region.

**Honest caveat.** No Arabic-market motivation is evident. Malaysia's own market is Malay/English. This is a speculative approach with a real but low probability, and it is a long way to send an email from Egypt.

---

### 17. Vetmaster (South Africa) `[S]`

| | |
|---|---|
| **Site** | https://www.vetmaster.co.za/ |
| **Country** | South Africa — Pretoria, Gauteng `[S]` |
| **Size** | Describes itself as the leading provider to South African veterinary professionals `[S]` |
| **Contact route** | Search-derived: `info@vetmaster.co.za`, `support@vetmaster.co.za` `[S]` — **verify on the site before sending.** LinkedIn showcase page https://za.linkedin.com/showcase/vetmaster-online-agencies/ `[S]` |

**Why them.** Their product explicitly serves **veterinary practices, vet shops, boarding kennels and grooming parlours** `[S]` — the same four-way module fit again. An Africa-facing vendor looking north into Arabic-speaking Africa (Egypt, Morocco, Sudan) would need exactly Aleefy's localisation.

**Honest caveat.** South African software vendors buying in USD/EGP terms is not a common pattern, and no evidence of MENA ambition was found. Low probability. Listed because the module fit is unusually exact.

---

## 2.4 — GCC veterinary clinic groups and hospitals *(Rank 4)*

### 18. The City Vet Clinic `[V]`

| | |
|---|---|
| **Site** | https://www.thecityvetclinic.com/ · contact https://www.thecityvetclinic.com/contact |
| **Country** | UAE |
| **Size** | **9 branches** — Al Wasl, Mirdif, Al Warqa, JVT, Al Barsha, Meydan, DSO (Dubai), plus one each in Al Ain and Abu Dhabi. Open 07:00–21:00 daily. `[V]` |
| **Contact route** | Email **info@thecityvetclinic.com** `[V]`; branch email **alwasl@thecityvetclinic.com** `[V]`; main **04 388 3990**, toll-free **800 3990**, emergency **+971 50 366 5985** `[V]` |

**Why them specifically — and the reason this entry is the most instructive in the document.** Their client booking portal runs at **`thecityvetclinic.euw1.ezyvet.com`** `[V]`. They are a **confirmed ezyVet customer**, on the EU-West cluster, across nine sites. That is a per-user, per-site, USD-denominated recurring bill, and it is exactly the TCO argument Rank 4 exists for.

**And the reason to be honest with yourself:** they are also therefore the hardest sale in the document. Nine live branches with patient records, billing and an integrated booking portal do not migrate to an unsupported single-developer Flask application on the strength of a cold email. The realistic ask here is **not** "replace ezyVet." It is a paid pilot at one branch, or a conversation about the modules ezyVet does not give them.

---

### 19. Modern Vet `[S]`

| | |
|---|---|
| **Site** | https://modernvet.com/ · locations https://modernvet.com/all-locations/ |
| **Country** | UAE — Dubai |
| **Size** | Founded **1995**; described as the oldest and largest veterinary group in the UAE; the Jumeirah flagship is the country's only 24-hour multi-specialty hospital, with in-house cardiology, neurology, orthopaedics, oncology and ophthalmology. Branches include JLT, JVC, Downtown, The Palm, Al Khawaneej. `[S]` |
| **Contact route** | Per-branch pages under https://modernvet.com/all-locations/ carry branch contacts; e.g. Al Khawaneej lists **khawaneej@modernvet.com** and Downtown lists **+971 4 5971 000** `[S]`. General line **800 82** `[S]`. The `/contact-us/` path returns 404 — **use the locations pages.** |

**Why them specifically.** A 30-year-old multi-specialty group with oncology, neurology and 24-hour inpatient care is the one clinical operator in this document that would genuinely exercise Aleefy's **inpatient, imaging, lab, clinical decision support and telemedicine** modules rather than just its front desk. They also have the scale to justify owning software.

**Honest caveat.** Same as City Vet, plus: a group of this stature will expect enterprise support, SLAs and integrations with imaging hardware. "No support organisation" is a much heavier objection here than anywhere else on the list.

---

### 20. Specialized Veterinary Clinics Centers (مراكز العيادات البيطرية التخصصية) `[V]`

| | |
|---|---|
| **Site** | https://svclinicksa.com/ · about https://svclinicksa.com/about-us/ |
| **Country** | Saudi Arabia — Riyadh |
| **Size** | Single Riyadh location; operating over a decade; departments: diagnostic, surgery, intensive care, **grooming**, emergency `[V]` |
| **Contact route** | Email **info@svclinicksa.com** and **support@svclinicksa.com** `[V]`; phone **920012674** (Saudi unified number) `[V]` |

**Why them specifically.** An established Riyadh centre running **intensive care and grooming under one roof** — the inpatient plus grooming combination that most PIMS products handle badly and Aleefy handles natively. A Saudi unified 9200 number indicates a properly constituted commercial entity rather than a single-vet practice. Arabic-first buyer, Arabic-first product, no language friction in the sales conversation.

**Honest caveat.** Single site. Realistically a licence customer and a Saudi reference, not an acquirer — but a Saudi reference is worth a great deal to every Rank 1 and Rank 3 conversation.

---

## 2.5 — Egyptian veterinary clinic groups *(Rank 5)*

> **The category finding first: Egypt has almost no veterinary chains.** Arabic and English searching returned a market of single practices. The largest verified group has five branches. Prior research separately records that **Pets Zone, Dr Men3am Pet Hospital, Almotawakkel Pet Center and Mojo Veterinary are already named VetICare customers** `[P]` — i.e. the most software-ready Egyptian clinics have already bought from the direct competitor. Note that Egypt's **Petzone Clinics** below is a name collision with the Kuwaiti retailer **Petzone** at entry 6; they are unrelated.

### 21. American Vet Center `[V]`

| | |
|---|---|
| **Site** | https://www.americanvetcenter.com/ |
| **Country** | Egypt — Cairo and Alexandria |
| **Size** | **5 branches** — Zamalek, Maadi (Degla), Sheikh Zayed, Sheraton, New Cairo (Rehab). Open 24/7 with a 22:00–10:00 emergency service. `[V]` |
| **Contact route** | Email **a.v.c.1@hotmail.com** `[V]`; hotline **+20 121 082 6108** `[V]`; branch lines published per site, e.g. Zamalek **01110801801 / (02) 2737 6664** `[V]` |

**Why them specifically.** The largest verified Egyptian veterinary group found, and a 24/7 operation across five sites — meaning shift handover, inpatient continuity and cross-branch record access are genuine daily problems for them, not hypothetical ones. Expatriate-facing locations (Zamalek, Maadi, Sheikh Zayed) mean higher-paying, more software-tolerant clientele. **They are the best Egyptian flagship-reference target in the document.**

**Read the contact address honestly:** the group's published general email is a Hotmail account. That tells you their software maturity, and it tells you the pitch should be about operations, not architecture.

---

### 22. Petzone Clinics (Egypt) `[V]`

| | |
|---|---|
| **Site** | https://petzoneclinics.com/ · about https://petzoneclinics.com/about-us/ |
| **Country** | Egypt — Cairo and Giza |
| **Size** | **3 branches** — New Cairo (opened 2010, original site), Dokki/Mohandessin, Heliopolis. Specialist departments including orthopaedic surgery, cardiology, dermatology, dentistry, and gynaecology/AI. `[V]` |
| **Contact route** | Email **info@petzoneclinics.com** `[V]`; main **01211288882** `[V]`; branches **02 2560 6590** (New Cairo), **0109 997 5999** (Dokki), **0109 039 0071** (Heliopolis) `[V]` |

**Why them.** The most clinically specialised Egyptian group found — multiple named specialties across three sites means referral flow between branches, which is a records problem Aleefy's EMR and cross-branch reporting address directly.

**Important caution.** Prior research names **"Pets Zone"** among VetICare's Egyptian customers `[P]`. It is not confirmed whether that refers to this group or to a different business with a similar name. **Verify before approaching** — walking into a pitch against an incumbent you did not know about is avoidable.

---

### 23. Pet Cure Veterinary Clinics `[V]`

| | |
|---|---|
| **Site** | https://petcureclinics.com/ · about https://petcureclinics.com/about-us |
| **Country** | Egypt — New Cairo and Madinaty `[S]` |
| **Size** | 2 locations `[S]`; site does not disclose staff size `[V]` |
| **Contact route** | Phones **+20 109 098 0050** and **+20 101 139 6672**, both WhatsApp-capable `[V]`; Facebook https://www.facebook.com/petcureclinics `[V]`; Instagram https://www.instagram.com/petcureclinic/ `[V]`. **No published email address and no street address on the site** `[V]` — WhatsApp is the working route. |

**Why them.** Two new-build satellite-city locations (New Cairo, Madinaty) serving the highest-income residential developments in Egypt. A young group without legacy systems is an easier first sale than an established one. **Licence customer, not an acquirer.**

---

### 24. Vetwork `[P]` / `[S]`

| | |
|---|---|
| **Site** | vetwork.co · coverage https://www.menabytes.com/vetwork-seed/ · https://thestartupscene.me/INVESTMENTS/Egyptian-Petcare-Startup-Vetwork-Launches-in-Saudi-Arabia |
| **Country** | Egypt (Cairo, Alexandria, North Coast) and Saudi Arabia (Riyadh); UAE referenced `[S]` |
| **Size** | **11–50 employees** `[S]`; founded 2017 by veterinarians Abdelrheem Hussein, Fady Azzouny and Zeinab ElGeziry; 100+ service providers, ~600 requests/day, 12,000 pets served, >$1M raised including backing associated with Nestlé Purina `[P]` |
| **Contact route** | LinkedIn **https://ae.linkedin.com/company/vetworkapp** `[S]`; Facebook https://www.facebook.com/VetworkAPP/ `[S]`; careers page https://wuzzuf.net/jobs/careers/Vetwork-Egypt-35784 `[S]`; address 171 El Tahrir, Greek Campus, Abdeen, Cairo, phone **+20 110 527 2790** `[S]` |

**Why them — the most interesting non-obvious name in this document.** Vetwork is a **consumer marketplace, not a PIMS**. They have the vet network, the brand, the funding, the Saudi expansion and the Purina relationship. They have **no clinic back-office product**. Every marketplace of this kind eventually discovers that owning the supply side's operating system is how it stops being disintermediated — and building one takes a year they would rather not spend.

They are founded by three veterinarians, based in Cairo, and reachable in Arabic without a time zone. Of everyone listed, they are the buyer most likely to grasp the value in a single meeting.

**Honest caveat.** Prior research notes that Egypt's most-funded pet-tech company found (VetCode) was valued at **$450,000 pre-money** `[P]`. That is the scale of capital in Egyptian pet-tech. Vetwork can have this conversation; they may not be able to fund a large one.

*(Adjacent, same logic, lower priority: **VetCode** — Cairo, founded 2018, 200+ clinics in network, 30,000+ users, 12 cities, seed from Pmaestro at $450k pre-money `[P]`, https://www.menabytes.com/vetcode-seed/. **No public contact route verified this session.**)*

---

## 2.6 — Veterinary pharmaceutical distributors *(Rank 6 — channel partners, not buyers)*

Listed for the introductions they can make, not for the cheques they will not write. All carried from `04_GOTOMARKET.md` `[P]`; the first was re-verified this session.

| Company | Site | Contact route | Note |
|---|---|---|---|
| **Animal Health Egypt** | https://www.animalhealthegypt.com/ | Email **info@animalhealthegypt.com**, phone **+20 12 22851666**, form at `/contactus`, Facebook/Twitter/LinkedIn linked `[V]` | Online veterinary pharmacy selling **to clinics** — their customer list is the target list. Best introducer in Egypt. |
| **Isovet Egypt** | https://isovet-eg.com/indexEn.html | Site contact page `[P]` | 10+ years, products for vets and animal-health professionals |
| **Apex Vet Company (AVC)** | https://www.apexvet-eg.com/ | Site contact page `[P]` | Egyptian manufacturer since 2014 |
| **Al Walaa Co. for Veterinary Drugs** | https://alwalaaeg.com/ | Site contact page `[P]` | Agent for major veterinary drug brands |
| **MSD Animal Health Egypt** | https://egypt.msd-animal-health.com/ | Site contact page `[P]` | Multinational. Their Egypt marketing team funds vet CPD events — that is the door, not procurement. |
| **Karaman Veterinary Medicines** | https://www.karamanvet.com/ | Site contact page `[P]` | Regional |

**Extension to the prior list — a directory rather than more names.** `../market/04_GOTOMARKET.md` already cites https://ensun.io/search/animal-health as a directory of ~28 animal-health companies in Egypt `[P]`. Rather than pad this shortlist with distributor names that will not buy, **use that directory to build the channel list and keep this document for buyers.** That is the correct division of labour between the two documents.

---

## 2.7 — Summary table

| # | Target | Country | Category | Rank | Contact confidence |
|---|---|---|---|---|---|
| 1 | Holool Alghad | Saudi Arabia | Software house | 1 | Phone/WhatsApp `[V]` |
| 2 | Al-Mukhtabarat | **Egypt** | Healthcare IT | 1 | Phone/WhatsApp/LinkedIn `[V]` |
| 3 | CompactSoft | Egypt | ERP house | 1 | Contact page `[S]` |
| 4 | Izam / Daftra | Egypt | SaaS platform | 1 | Form + CEO LinkedIn `[S]` |
| 5 | Odoo partners EG | Egypt | Implementers | 1 | Directory only `[UNVERIFIED]` |
| 6 | Petzone | Kuwait/GCC | Pet retail | 2 | LinkedIn `[V]` |
| 7 | Pet Corner | UAE | Pet retail | 2 | Contact page `[S]` |
| 8 | The Petshop | UAE | Pet retail | 2 | **None found** `[UNVERIFIED]` |
| 9 | Pets Lounge | Egypt | Pet retail | 2 | Contact page `[S]` |
| 10 | Zima Pets | Egypt | Pet retail | 2 | Contact page `[S]` |
| 11 | VetICare / QuadInsight | Undisclosed | Vet vendor | 3 | Email + LinkedIn `[V]` |
| 12 | bAItari.vet | Oman/Saudi | Vet vendor | 3 | Email + LinkedIn `[V]` |
| 13 | Yolo Clinic | MENA/DE | Clinic vendor | 3 | Email `[V]` |
| 14 | Kawakeb Al-Teknologia | Saudi Arabia | Vet vendor | 3 | Site only `[UNVERIFIED]` |
| 15 | Happy Pet Tech | India/UAE | Pet-biz vendor | 3 | LinkedIn + form `[V]` |
| 16 | kumoVet | Malaysia | Clinic vendor | 3 | Form only `[S]` |
| 17 | Vetmaster | South Africa | Vet vendor | 3 | Email `[S]` |
| 18 | The City Vet Clinic | UAE | Vet group (9) | 4 | Email + phone `[V]` |
| 19 | Modern Vet | UAE | Vet group | 4 | Branch emails `[S]` |
| 20 | Specialized Vet Clinics | Saudi Arabia | Vet centre | 4 | Email + phone `[V]` |
| 21 | American Vet Center | Egypt | Vet group (5) | 5 | Email + phone `[V]` |
| 22 | Petzone Clinics | Egypt | Vet group (3) | 5 | Email + phone `[V]` |
| 23 | Pet Cure Clinics | Egypt | Vet group (2) | 5 | WhatsApp `[V]` |
| 24 | Vetwork | Egypt/Saudi | Pet marketplace | — | LinkedIn + phone `[S]` |

---

# T3 — What each category will pay attention to

For each: **what to lead with**, **what they will actually verify**, and **what they will use to argue the price down.** The third column is the one that matters, because it is the one that will happen.

---

## Software houses and healthcare-IT vendors (Rank 1)

**Lead with:** *"549 passing tests, CI configured, Alembic migrations, and 4,372 translated strings with working Arabic RTL through to PDF output."* In that order. Not the module list — the module list is what everyone claims. **The test count is the credibility instrument.** A software house has been burned by acquired code before, and the number that predicts whether a handover succeeds is not lines of code, it is whether the thing has a suite that goes green on their machine on day one.

**What they will verify:**
- Run the test suite themselves, on their infrastructure, before any money is discussed. Make this easy — a documented one-command setup that produces 549 green tests on a clean machine is worth more than any deck.
- Test coverage *shape*, not just count: do the 549 tests cover the accounting and invoicing paths, or are they mostly route smoke tests? Know the answer before they ask it.
- Migration history integrity — whether Alembic actually reconstructs the 73-table schema from zero.
- The Arabic PDF, personally, in the language they read. They will generate an invoice and look at it.
- Dependency currency and licence hygiene across the Python dependency tree.

**What they will argue the price down with:**
- **"Flask, not Django/Laravel/.NET — our team doesn't work in this."** A real objection with a real cost. Prepare an honest answer about what the handover actually requires.
- ~~**"Single-tenant means we can't run this as SaaS."**~~ **No longer true, and this was previously the strongest technical lever in the document.** Multi-tenancy shipped in August 2026: subdomain routing, a database per clinic, tenant-scoped sessions, and tenant-aware migrations and backups, covered by `tests/test_tenancy.py`, `test_backup_tenant_scope.py` and `test_tenant_migrations.py`. What honestly survives of the objection is narrower: isolation is database-per-tenant, so a vendor at hundreds of clinics carries N databases to operate rather than one. That is a cost argument, not an architecture rewrite.
- **"170 templates is a maintenance liability, not an asset."** Server-rendered templates in a market that expects an SPA and a mobile app.
- **"No customers means no product-market fit evidence — we're buying your guess."** Unanswerable. Do not try to answer it; concede it and reprice the conversation around build-cost avoidance instead.
- **"No mobile app."** Both major Arabic competitors ship one.

---

## Pet-care retail and services groups (Rank 2)

**Lead with:** *"One system for the shop, the grooming salon, the boarding kennel, the clinic and the accounts — in Arabic, with an Arabic invoice that prints correctly."* Then the specific pain: **batch and expiry tracking on pet food and medication**, which is a compliance and shrinkage problem they have, and which generic retail POS handles badly.

**What they will verify:**
- Whether the POS is a real POS — barcode, shift close, cash drawer reconciliation, returns — or a form that writes an invoice row.
- Whether the accounting is real double-entry with P&L, cashflow and budget, or a reporting veneer.
- Multi-branch consolidation. **This is where the deal lives or dies.**
- Arabic invoice output, in a browser, in front of you.

**What they will argue the price down with:**
- ~~**"Single-tenant across 20 stores is a non-starter."**~~ Answered — subdomain-routed multi-tenancy plus a Multi-Branch Control Centre. Was the category's defining objection.
- **"We already have an ERP for retail."** Displacement, not greenfield.
- **"Who supports this at 9pm on a Friday when the POS won't close?"** Retail runs at consumer hours. "No support organisation" is more damaging in this category than in any other on the list.
- **"No e-invoicing integration for our tax authority."** ZATCA in Saudi, and the Egyptian Tax Authority e-receipt regime in Egypt. Competitors ship this. Check what exists before the meeting.

---

## Existing veterinary-software vendors (Rank 3)

**Lead with — and this differs by sub-type:**
- **Non-Arabic vendors (Happy Pet Tech, kumoVet, Vetmaster):** lead with **Arabic market entry**. "You are selling into Dubai already. Here is Arabic, RTL and correct Arabic PDFs, finished and tested, plus a veterinary domain model built by people who work with Arabic-speaking vets." Their alternative is an 18-month localisation project they will underestimate and then abandon.
- **Arabic vendors (VetICare, bAItari, Yolo, Kawakeb, Holool Alghad):** lead with **the modules they don't have** — accounting with P&L/cashflow/budget, payroll, HR, attendance, procurement, retail POS, boarding, grooming, telemedicine, report builder, clinical decision support, audit trail, TOTP 2FA. Be specific and be checkable; they will verify against their own roadmap.

**What they will verify:** everything a software house verifies, plus their own domain judgement — species and breed modelling, weight-based dosing, vaccination scheduling, controlled-substance handling. A veterinary vendor can tell in twenty minutes whether the domain model was built by someone who talked to vets.

**What they will argue the price down with:**
- **"We know what this costs to build, because we built it."** No information asymmetry. Accept it.
- **"You have zero customers. There is nothing to acquire but code."** Correct.
- **"We already have Arabic."** True of VetICare, bAItari, Yolo, Kawakeb. The counter is *Arabic in PDFs*, which is where most implementations quietly fail — but check theirs first, because if theirs works, the argument evaporates and you should know that before you make it.
- **"We can hire two developers in Cairo for a year for less than you're asking."** They can, and they will say so. The counter is time-to-market and the 549 tests, not effort.

---

## Veterinary clinic groups (Ranks 4–5)

**Lead with:** total cost of ownership, in their currency, over five years — licence, per-user, per-branch, annual increase, and the fact that at the end of it they own nothing. Against: buy once, own the source, no vendor able to reprice, data stays where they want it.

**What they will verify:**
- Whether it runs. A live demo instance with their own data in it beats every document.
- Whether their receptionist can use it without training, in Arabic.
- Whether the historical data comes across. Migration is the number one operational fear of any clinic switching systems.
- Backup and restore — demonstrate it, do not describe it.

**What they will argue the price down with:**
- **"We would have to hire and keep a developer forever."** The single biggest lever in the entire document. It is legitimate, it is quantifiable, and every group will use it.
- **"You have no other customers — who else has run this in production?"** Nobody. Concede immediately; a hedge here destroys trust for the rest of the meeting.
- **"What happens to us if you get a job abroad?"** The key-person risk question. It is the real question behind all the others, and it deserves a real answer — an escrowed handover, a documented runbook, a named local developer who can take over.
- **"No lab-analyser integration."** VetICare ships named Exigo and Edan integrations `[P]`. A hospital with in-house diagnostics will raise this.
- **"No pet-owner app."** Both major Arabic competitors have one.

---

## Distributors (Rank 6)

**Lead with:** nothing about acquisition. Lead with *"a free tool your clinics will thank you for, and 30% of the first year per clinic that signs"* — the offer already written in `04_GOTOMARKET.md` `[P]`, aimed at **an individual rep, not the company.**

**What they will argue with:** *"Why would we buy it when you'll happily let us resell it?"* They are right. Take the reseller deal.

---

# T4 — Approach

## The situation, without flattery

A solo seller, in Egypt, with no broker, no revenue, no customers, no operating history, selling a pre-customer Flask codebase, to buyers who are mostly abroad. Every structural advantage belongs to the other side. The process therefore has to be run on the two things the seller does control: **preparation quality and sequencing.**

## 4.1 Do these three things before sending any message

1. **Stand up a live demo instance with realistic Arabic data in it.** Not screenshots. A URL, credentials, a seeded clinic with Arabic client names, Arabic patient records, and an Arabic invoice that prints correctly. Every category in T3 asks to see the software working; the seller who can answer "here, log in" in the first reply converts at a rate the others do not. This is the highest-return item in this document.
2. **Make the test suite reproducible by a stranger.** `git clone`, one command, 549 green tests on a clean machine, documented. This is the entire credibility case with Rank 1 and Rank 3, and it is worthless if it only runs on the seller's laptop.
3. **Get one live clinic, even unpaid.** One Egyptian clinic using it daily converts "zero customers" from a disqualifying fact into "early, with a reference site." The gap between zero and one is larger than the gap between one and ten in every conversation in this document. `04_GOTOMARKET.md` names the warm routes.

## 4.2 The first message

Short. Specific. Sent to a named human, not to `info@`. Roughly:

> **Subject:** Arabic veterinary practice system — asking whether it's useful to you
>
> [Name] — I built a veterinary clinic management system in Arabic and English, with full RTL including Arabic in generated PDFs. It covers [the three or four modules that matter *to them specifically*]. It's finished and tested — 549 automated tests, CI, migrations — but it has no customers and I'm not building a company around it.
>
> I noticed [one specific, true, checkable thing about their business — the ezyVet portal, the missing grooming module, the UAE expansion, the vet product line next to the medical one].
>
> If it's useful to you, I'm open to selling it outright or licensing it. Live demo here: [URL], login [credentials]. Happy to walk you through the code.
>
> If it isn't, no need to reply.

**Why each part is there.** The disclosure of zero customers goes in the first message, not the third — it will be discovered in ten minutes of diligence, and volunteering it is the only way it costs nothing. The one specific observation about their business is what separates this from the twelve other cold emails they got that week. The "no need to reply" removes the pressure that makes people not reply.

## 4.3 What is attached, what is shown, what is held back

| Stage | What they get |
|---|---|
| **First contact, no NDA** | Live demo URL with credentials to a **seeded demo instance** (never a real clinic's data). Module list. The verified metrics: LOC, tables, routes, test count, string count. Screenshots of Arabic PDF output. A short architecture summary — stack, database, deployment model. |
| **After a reply showing genuine interest, still no NDA** | A screen-shared walkthrough, live, driven by the seller. Answers to technical questions. The reproducible test run — **executed on the seller's screen**, not handed over. Anonymised schema overview at table-name level. |
| **After a signed mutual NDA** | Read-only repository access, time-limited. Full schema. Dependency manifest. The provisioning and backup/restore procedure. Known-defect list. |
| **After a signed LOI or a paid technical-diligence deposit** | Full repository, commit history, credentials, deployment automation, everything. |

**The rule that holds this together:** *nothing that can be copied leaves the seller's control until there is either a signature or money.* A live demo cannot be copied. A screen share cannot be copied. A repository can.

## 4.4 The awkward one — approaching a direct competitor

**State the risk accurately rather than dramatically.** Showing a veterinary product to VetICare, bAItari, Holool Alghad or Kawakeb means showing it to an organisation with the team, the domain knowledge and the motive to reimplement it. This is a real risk. It is also **smaller than it feels**, for a reason worth internalising:

> **A competent competitor does not need to see Aleefy to build what Aleefy does.** VetICare has shipped Arabic RTL, pharmacy, lab, POS, inventory, boarding, RBAC and a mobile app to 500 claimed clients since 2020. They know what a veterinary ERP contains. What they would gain from a demo is a **feature checklist and a UX reference** — helpful, but not the expensive part. The expensive part is 28,000 lines and 549 tests, and that is precisely what stays behind the NDA.

So the risk is not "they steal the product." The risk is **"they take the roadmap and skip a year of deciding what to build."** Manage that, specifically:

**What to withhold from competitors, and when:**

- **Never, at any stage before a signed LOI:** repository access. Not read-only, not time-limited, not "just the templates." Competitors are the one category where read-only access under NDA is not enough, because an NDA against a competitor is expensive and slow to enforce across borders and the seller has neither money nor a legal entity positioned to do it.
- **Not before a signed mutual NDA:** the schema. 73 tables is the distilled domain model — the most copyable, most valuable, least protectable artefact in the asset. It is a design document, and it can be reimplemented from a screenshot of an ERD in a week.
- **Not before a signed mutual NDA:** the implementation of the Arabic PDF pipeline. Which library, which shaping approach, which font-embedding strategy, which workarounds. **This is the crown jewel and it is a handful of files.** Demonstrate the output freely; never discuss the method. If asked directly, say: "That's the part I'm selling."
- **Not in the first contact:** the complete module list at sub-feature granularity. Give categories, not the roadmap. "Accounting including P&L, cashflow and budgeting" — not the full table of every report.
- **Freely, at any stage, to anyone:** the headline metrics, the demo, the Arabic PDF *output*, and screenshots. These are what get a reply, and none of them are the asset.

**Sequencing rule — the only real protection available:**

> **Approach competitors last, never first.**

Work Rank 1 and Rank 2 to a conclusion before opening a competitor conversation. Three reasons: a competitor approached while other conversations are live behaves differently from one approached in a vacuum; the seller who has already had four technical diligence conversations is far better prepared for the one adversarial one; and if a non-competitor deal closes, the competitor conversation never has to happen.

**Within the competitor category, sequence by copy risk, lowest first:** Happy Pet Tech and kumoVet and Vetmaster (different languages, different continents, cannot easily copy the thing that matters) → bAItari and Yolo (adjacent, partnership-shaped, and bAItari's own contact page invites partnership enquiries) → Holool Alghad and Kawakeb → VetICare last. **VetICare is the highest-risk conversation in this document and should be the final one initiated.**

## 4.5 Cross-border practicalities for an Egypt-based seller

- **Payment rail — check this before negotiating, not after.** `../market/09_PAYMENT_RAILS.md` establishes that **PayPal cannot receive into Egypt** `[P]`, that **Payoneer works but converts to EGP on arrival at an effective cost around 5–6%** `[P]`, and that **Wise cannot be confirmed for Egyptian receiving** `[P]`. And see T5: **Escrow.com does not support Egypt** `[V]`. For a one-off sale, the realistic mechanisms are a **direct bank wire to an Egyptian bank** or **Payoneer**. Know which one before a buyer asks, because "how do I pay you" is a deal-stalling question if the answer is improvised.
- **Time zones are in the seller's favour for the targets that matter.** Egypt (EET) overlaps the Gulf, Saudi and Oman almost entirely, and covers Indian business hours in the morning. Only kumoVet (Malaysia) and Vetmaster (South Africa) are awkward, and both are low-priority.
- **Language.** Write to Egyptian, Saudi, Omani and Emirati targets in Arabic, with an English version below. Write to Happy Pet Tech, kumoVet and Vetmaster in English. The Arabic-first approach signals the exact competence being sold.
- **Legal.** A cross-border asset sale needs a written asset-purchase agreement naming what transfers (code, IP, domain, trademark, documentation) and what does not. This does not require a broker. It does require a lawyer for one document, and that is a cost worth accepting.
- **Third-party IP.** Before anything ships, audit the licences of every dependency and every UI asset in those 170 templates. A GPL-licensed dependency or an unlicensed icon set discovered during diligence kills deals. This is a two-hour job that prevents a total loss.

---

# T5 — Marketplaces

## The verdict first

**For this asset, in this situation, marketplaces are close to worthless — and for an Egypt-based seller, one of them is structurally unusable.** Direct outreach to the 24 names in T2 is a better use of every hour. The reasoning follows, with the actual published rules and fees.

---

## 5.1 Acquire.com (formerly MicroAcquire)

**Note:** MicroAcquire and Acquire.com are the same company; MicroAcquire rebranded. There is no separate MicroAcquire to consider.

**Their published position on pre-revenue listings** `[V]` (https://blog.acquire.com/what-types-of-startups-can-you-list-on-acquire/):

- *"We seldom list startups with no revenue."*
- The exception exists only for **valuations under $20,000**, where the **average is $7,500**.
- **"Beta or coming soon startups won't be listed."**
- Founders are advised to *"demonstrate viability by launching an MVP to paying customers"* before applying.
- Their curation team has final say regardless.

**Fees** `[V]` (https://acquire.com/seller-pricing/): **8% closing fee** on deals under $250k, plus a **$25/month listing fee**; 7% + $50/mo for $250k–$1M; 6% + $100/mo above $1M. The advisory service, "Guided by Acquire," is **restricted to profitable SaaS with $100k+ revenue** — explicitly unavailable here.

**Honest assessment.** Aleefy is not merely pre-revenue, it is pre-customer. Acquire's own stated exception band tops out at a $20,000 valuation and averages $7,500 — which is the platform telling sellers, in public, what a no-revenue listing is worth on it. Listing here would either be rejected at curation or would **publicly anchor the asset in a band the seller should not accept.** That anchoring damage is the real cost, and it is larger than the $25/month.

**One narrow, legitimate use:** the platform's free valuation tooling and published acquisition-multiple reports are useful **reading**, and cost nothing. Read them; do not list.

---

## 5.2 Flippa

**Fees** `[S]` (https://flippa.com/pricing and multiple 2026 fee analyses):

| Item | Cost |
|---|---|
| Entry listing (asking price under $10,000) | **$29** |
| Standard listing ($10,000–$999,999) | **$59–$99** |
| Success fee under $50k | **10%** |
| Success fee $50k–$100k | **7.5%** |
| Success fee above $100k | **5%** |
| Confidential listing (hides name/URL publicly) | **$199** |
| Premium / Marketing / Ultimate boost packages | **$295 / $450 / $950** |
| Broker service (assets $100k+) | **$999**, 9-month term, non-refundable |

**Listing fees are non-refundable whether or not the asset sells** `[S]`.

**Requirements.** No published minimum business value `[S]`. Flippa will list pre-revenue assets, including codebases and app source. It is the more permissive of the two.

**The disqualifying finding, and it is not about fees.** Flippa's standard settlement rail is **Escrow.com**. Escrow.com publishes a list of unsupported countries, and **Egypt is on it** `[V]` (https://www.escrow.com/support/faqs/what-countries-regions-are-not-supported-by-escrowcom). The full list: Afghanistan, Algeria, Angola, Azerbaijan, Burundi, Cambodia, Central African Republic, Chad, Congo, DR Congo, Côte d'Ivoire, **Egypt**, Equatorial Guinea, Eritrea, Ethiopia, Guinea, Guinea-Bissau, Haiti, Honduras, Iraq, Kazakhstan, Kyrgyzstan, Laos, Lebanon, Liberia, Libya, Moldova, Nigeria, Pakistan, Panama, Sierra Leone, Somalia, Sudan, Suriname, Tajikistan, Uganda, Ukraine, Uzbekistan, Venezuela, Yemen, Zimbabwe.

Their stated policy for residents of those countries: *"they may create an account with Escrow.com but they must provide a bank account in a supported country to receive payments from us"* `[V]`.

**Read that carefully, because it is the single most consequential operational fact in this document.** An Egypt-resident seller **cannot be paid through the standard marketplace escrow rail without a foreign bank account.** That is not a fee to absorb; it is a structural blocker on the settlement leg. It affects Flippa and every other marketplace that settles through Escrow.com, and it applies equally to any direct-sale buyer who proposes Escrow.com as neutral ground — which a cautious foreign buyer very reasonably might.

**Plan for this now:** either establish a compliant foreign receiving account before running a process, or specify the settlement mechanism (direct wire, staged payments, Payoneer) in the seller's own first proposal so the question is never opened by the buyer. Being the party who proposes a workable rail is far better than being the party who discovers a broken one mid-deal.

---

## 5.3 What a marketplace would and would not achieve

**What it would not achieve:**
- **A price.** Marketplace pricing on these platforms is anchored to revenue multiples. There is no revenue. The valuation engine has nothing to compute against, and buyers on those platforms are shopping for cashflow, not for codebases.
- **The right buyers.** Not one of the 24 targets in T2 shops on Acquire or Flippa. Al-Mukhtabarat in 6th October City, Holool Alghad in Riyadh, Petzone in Kuwait, and a nine-branch Dubai vet group are not browsing a startup marketplace for an Arabic veterinary ERP. **The buyer pool for this asset is a list, not a market** — and the list is above.
- **Credibility.** A public listing that sits unsold for six months is discoverable, and it is a negotiating gift to any of the named targets who finds it.

**What it might achieve, narrowly:**
- **Inbound from an unanticipated direction** — an Indian or Southeast Asian vet-software vendor, a pet-tech operator in a market not researched here.
- **Price discovery**, cheaply, if any inbound arrives.

**The proportionate action, if the seller wants marketplace exposure at all:** a **$29 Flippa entry listing** — the cheapest available option — placed **only after** the T2 direct outreach has been worked for eight to twelve weeks and produced no interest, **and only after** the settlement-rail problem is solved. Treat it as a lottery ticket bought with the change, not as a channel. Do not buy boosts, do not buy the confidential option, do not buy the broker package — those are $199 to $999 spent advertising an asset to an audience that structurally does not want it.

**And do not list on Acquire.com at all.** Their own published rules put a no-revenue listing in a sub-$20,000 band. There is nothing to be gained from having that number attached to this asset in public.

---

# Final assessment

## Top 5 named targets

**1. Al-Mukhtabarat (شركة المختبرات) — Giza, Egypt.** https://almukhtabarat.com/ · WhatsApp **+20 102 178 8994** · LinkedIn @almukhtabarat `[V]`
The most complementary buyer found and the lowest-friction serious conversation available. Egyptian, Arabic-native, already selling a veterinary laboratory and clinic system, already integrated with Roche/Abbott/Sysmex analysers — which is the one significant capability Aleefy lacks. They are strong exactly where Aleefy is weak and absent exactly where Aleefy is strong (EMR depth, inpatient, pharmacy, telemedicine, retail POS, HR, payroll, accounting). Same city, same currency, same language, reachable on WhatsApp this week. **Start here.**

**2. Holool Alghad (حلول الغد) — Riyadh, Saudi Arabia.** https://holoolalghad.com/veterinary-clinic · **+966 11 2244 776** · WhatsApp **+966 55 500 6347** `[V]`
A vertical software house that has already decided veterinary is a market worth entering and has shipped a shallow product into it. Aleefy is the deep version of what they already sell, with a Saudi channel and Saudi customers already in place to sell it through. Highest willingness-to-pay of any single name. Carries competitor risk — apply the T4 protocol.

**3. Petzone — Kuwait, operating UAE / KSA / Bahrain.** https://petzone.com/ · LinkedIn https://www.linkedin.com/company/petzone-kuwait · 201–500 employees, founded 2001 `[V]`
The best fit for the *entire* module set rather than a slice of it. A four-country pet retail and services group needs retail POS, batch-and-expiry inventory, procurement, grooming, boarding, CRM, HR, payroll and multi-country consolidated accounting in Arabic — which is Aleefy's module list. No vet PIMS vendor offers them retail; no retail ERP offers them grooming and boarding. Real capital, real multi-country licensing pain. The multi-branch question decides it.

**4. Happy Pet Tech — Bengaluru, India, selling into the UAE.** https://www.happypet.tech/ · LinkedIn https://www.linkedin.com/company/happy-pet-tech `[V]`
The cleanest vendor conversation on the list and the safest one to open first. They already sell the same unusual combination — grooming, boarding, daycare, veterinary, pet store — and are already selling into Dubai. What they cannot manufacture from Bengaluru is credible Arabic with correct RTL and correct Arabic PDFs. They need precisely the hardest-to-copy thing in the asset, they do not compete in Egypt, and they have little to gain from copying a localisation they cannot maintain.

**5. Vetwork — Cairo and Riyadh.** LinkedIn https://ae.linkedin.com/company/vetworkapp · **+20 110 527 2790** `[S]`
The non-obvious one. A funded, vet-founded Egyptian pet-care marketplace, expanded into Saudi Arabia, with a Purina-associated backer, no clinic back-office product, and the strategic logic of every marketplace that eventually needs to own its supply side's operating system. Three veterinarian founders in Cairo will understand the product in one meeting. **The caution is capital, not comprehension** — Egyptian pet-tech valuations are small.

*Honourable mention:* **bAItari.vet** — https://baitari.vet/contact · info@baitari.vet `[V]` — whose own contact page explicitly invites partnership enquiries, and whose narrow clinical/AI product is the mirror image of Aleefy's broad back office. Kept off the top five only because it is a competitor and belongs late in the sequence.

## The single most likely buyer category

**MENA vertical-software houses and healthcare-IT vendors — Rank 1.**

Because they are the only category that (a) can absorb a 28,000-line Flask codebase without hiring anyone new, (b) monetises it many times rather than once, so the same asset is simply worth more to them than to any operator, (c) can read a 549-test suite and correctly value what it de-risks, and (d) knows from experience exactly how expensive Arabic RTL through to PDF actually is — which is the one part of this asset that is genuinely hard to reproduce and genuinely painful to get wrong.

Every other category has a structural reason to discount: operators must hire a developer forever, competitors know the build cost precisely and have no information asymmetry to lose, and distributors do not want a support liability at all.

**With one honest qualification.** "Most likely" here is relative, not absolute. A pre-customer, single-developer asset is a hard sale in every category, and the most probable outcome of any process — direct or marketplace — is **no sale at the seller's expected price.** The three preparation steps in T4.1 exist because they are what change that: a live demo, a stranger-reproducible test run, and one real clinic using the software. **The third is worth more than the other two combined**, and it is worth more than every name in this document.

## Are marketplaces worth the effort?

**No.**

Acquire.com states in public that it seldom lists no-revenue startups, that the exception band is under $20,000 with a $7,500 average, and that beta or pre-launch products are not listed at all `[V]`. Listing there would either be rejected at curation or would publicly anchor the asset in a band the seller should not accept — and that anchoring is a real cost, not a hypothetical one.

Flippa will take the listing for $29, but its buyers price on revenue multiples and there is no revenue to multiply. More decisively: **Escrow.com — Flippa's settlement rail — does not support Egypt** `[V]`. An Egypt-resident seller cannot be paid through it without a bank account in a supported country. That is a structural blocker on the settlement leg, not a fee to absorb, and it applies to any buyer who proposes Escrow.com as neutral ground in a direct sale too. **Solve the payment rail before running any process, by whatever route.**

Set against that: the actual buyer pool for an Arabic veterinary ERP is **twenty-four named organisations, not a market**, and none of them shop on these platforms. Direct outreach dominates on every axis — cost, control, buyer quality, and the ability to withhold what should be withheld.

**The proportionate position:** work the T2 list directly for eight to twelve weeks. If it produces nothing, spend $29 on a Flippa entry listing as a lottery ticket, once the settlement rail is fixed. Never list on Acquire.com. Never buy a boost package.

---

## Appendix — what this research could not establish

Stated so no one re-runs it expecting a different answer.

- **The Petshop (UAE)** — no verifiable company website or contact route found. Entry retained but flagged; verify the entity before spending time.
- **Kawakeb Al-Teknologia** — product page reachable, no direct email or phone verified.
- **VetCode (Egypt)** — company confirmed via press coverage; no public contact route found.
- **Egyptian Odoo partners** — the official Odoo partner directory for Egypt is the route; individual firm contacts not verified.
- **kumoVet** — office address published, **no email address found anywhere**; contact form only.
- **VetICare's country of incorporation** — still not disclosed anywhere on their site. The `quadinsight.com` support domain is the only lead, and it is a real one worth pulling.
- **Egyptian veterinary chains beyond five branches** — searched in Arabic (`سلسلة عيادات بيطرية`, `مستشفى بيطري فروع`, `فروعنا`) and English. **They do not appear to exist.** The Egyptian market is single-practice. This is a finding, not a gap.
- **Whether Egypt's Petzone Clinics is the "Pets Zone" named as a VetICare customer** in prior research — unresolved, and worth resolving before any approach.
- **Multi-branch capability of Aleefy itself** — not assessed here; it is the central objection for Ranks 2 and 4 and should be established from `../market/05_PRODUCT_READINESS.md` or the code before those conversations open.

---

*Compiled 2026-07-28. Every company name, URL and contact detail above was returned by a live search or a live page fetch on that date. Nothing was invented. Entries tagged `[S]` were search-derived and should be re-verified against the primary source before an email is sent; entries tagged `[UNVERIFIED]` have no confirmed contact route and say so.*
