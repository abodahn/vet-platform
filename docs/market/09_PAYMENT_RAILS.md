# 09 — Payment Rails

**How a two-person Egyptian software business actually collects money, domestically and across borders.**

Research date: **28 July 2026**.
FX reference: **USD 1 ≈ EGP 51** (USD/EGP traded 50.53–51.35 in the week of 19–24 July 2026 — [exchangerates.org.uk USD/EGP 2026 history](https://www.exchangerates.org.uk/USD-EGP-spot-exchange-rates-history-2026.html)). All EGP↔USD conversions in this document use **51**.

Product context: perpetual licences at **EGP 12,000 / 30,000 / 60,000** per clinic (≈ **USD 235 / 590 / 1,175**), plus setup fees and annual support. The worked example throughout is **one payment of EGP 30,000**.

**Reading key**
- `[VERIFIED]` — a URL is cited that states the fact directly.
- `[UNVERIFIED]` — could not be sourced; treat as a hypothesis to test, not a fact.
- `[NOT PUBLIC]` — the provider does not publish the list or number; silence is *not* evidence of a yes.

---

## T1 — Domestic collection inside Egypt

### T1.0 The headline answer

**InstaPay. The prior research was right, and the margin is bigger than it looked.**

On a EGP 30,000 licence: InstaPay costs **EGP 20, paid by the clinic, settling instantly**. Paymob costs **EGP 828 — possibly EGP 944 — paid by you, settling weekly**. That is a **40x** difference in cost and it lands on the wrong side of the table.

The genuinely expensive part of collecting money in Egypt is not the payment rail. It is **VAT and ETA e-invoicing compliance**, which costs more in accountant time than every transaction fee in this document combined, and which carries penalties that dwarf them. See T1.6 and T4.

### T1.1 Business registration — a منشأة فردية is enough

**No شركة is required for any rail here.** Both card acquirers ask for the same three documents, all of which a sole establishment possesses:

- **Paymob:** *"All you will need is to upload your commercial registration, Tax ID and National ID"* ([Paymob POS](https://paymob.com/en/pos-solution)), plus a bank account; verification takes **up to 3 days** ([Paymob online payment](https://paymob.com/en/online-payment)).
- **Fawry:** merchant account needs a **سجل تجاري** and **بطاقة ضريبية**; their team makes contact within **two days** ([Fawry developer — get started](https://developer.fawrystaging.com/docs/get-started), [Fawry registration](https://fawrypay.online/register)).

Neither publishes a rule excluding sole traders, and Egypt PSP guidance confirms the standard document set is commercial registration + tax card + UBO ID, noting that *"having an Egyptian commercial registration significantly increases trust and reduces onboarding friction"* ([PayAtlas — Egypt](https://payatlas.com/countries/egypt-eg)).

InstaPay, bank transfer, wallets and cash need **no registration at all** to physically receive money — only to be legal about it.

#### Two registration routes — take the cheap one

**Route A — ordinary commercial registry (سجل تجاري فردي). This is what you want.**

| Item | EGP |
|---|---|
| Commercial register, individuals (9.5 register + 6 chamber + 25 services) | **40.5** ([Ahram Business](https://business.ahram.org.eg/News/3032.aspx)) |
| Tax card (بطاقة ضريبية) | 50–100 ([Diwan](https://diwan-egy.com/رسوم-تأسيس-شركة-فردية-في-مصر/)) |
| Chamber of commerce (capital under 10,000) | 55–75 ([Elma3rafa](https://www.elma3rafablog.com/2026/01/commercial-registration-fees.html)) |
| Lease registration | 50–150 |
| **DIY total** | **350–600** |
| **Realistic, with an accountant** | **2,000–5,000** |

**Timeline:** open the tax file first (~2 weeks), then chamber certificate, then the register issues in **2–7 business days** ([Ahram Business](https://business.ahram.org.eg/News/3032.aspx)). Register valid 5 years.

**The prerequisites are the real blocker, not the fees:** a certified lease on premises with a **commercial** electricity meter, a criminal record certificate, and you **cannot be a government employee or a privately-insured salaried employee**. For a two-person team where one has a day job, this needs checking before anything else.

**Route B — GAFI منشأة فردية under Investment Law 72/2017. Avoid.** Minimum capital **EGP 100,000** ([WomenConnect — Egypt sole corporation](https://www.womenconnect.org/ar/web/egypt/business-registration/-/asset_publisher/O3k1hY57P4s9/content/sole-corporation)). Fees total roughly 800–1,000 EGP ([Diwan](https://diwan-egy.com/رسوم-تأسيس-شركة-فردية-في-مصر/)). GAFI advertises **1 business day** ([GAFI e-services](https://www.gafi.gov.eg/Arabic/eServices/Pages/DepartmentService.aspx?DSID=1)); practitioners report 7–10. Only worth it for investment-law incentives you do not need yet.

**LLC for comparison:** EGP 3,000–5,000 minimum via GAFI ([Elma3rafa](https://www.elma3rafablog.com/2026/01/commercial-registration-fees.html)).

### T1.2 Fees on ONE payment of EGP 30,000

| Rail | Published fee | **Cost on EGP 30,000** | Who pays |
|---|---|---|---|
| **InstaPay (app)** | 0.1%, min 0.50, **max EGP 20** | **EGP 20** | **Clinic** |
| **Bank transfer — Banque Misr IPN** | 0.1%, min 0.50, max 20 | **EGP 20** | Clinic |
| **Bank transfer — Bank of Alexandria** | 0.15%, min 10, **max 50** | **EGP 45** | Clinic |
| **Bank transfer — NBE AlAhly Net** | free on digital channels | **EGP 0** | — |
| **Paymob (card)** | 2.75% + EGP 3 | **EGP 828** (→ ~**944** if +14% VAT) | **You** |
| **Fawry Accept — card / reference code** | 2.75% | **EGP 825** + 999 setup + 499/mo | **You** |
| **Fawry Accept — wallet QR** | 1.5% | **EGP 450** + 999 setup + 499/mo | **You** |
| **Fawry via Flutterwave** | 2.3% + 1.5, +14% VAT on fee | **~EGP 897** | You |
| **Vodafone Cash** | 0.5%, min 1, **max EGP 15** | **EGP 15** — but **cash-out 1% = EGP 300** | Clinic / you |
| **Cash** | 0 | **EGP 0** (plus risk and time) | — |

#### Verifying the prior claim

**"InstaPay caps its fee around EGP 20" — CONFIRMED, with two corrections.**

Since 1 April 2025 InstaPay charges **0.1%, minimum EGP 0.50, maximum EGP 20** ([Daily News Egypt](https://www.dailynewsegypt.com/2025/03/25/egypts-instapay-to-charge-transfer-fees-ranging-from-egp-0-5-20/)), still in force as of April 2026 ([EnterpriseAM, 6 Apr 2026](https://enterpriseam.com/egypt/2026/04/06/instapay-hits-profitability-as-demand-keeps-up-one-year-into-0-1-transaction-fee/)). Banque Misr mirrors it exactly, its own worked example stating a transfer of **EGP 20,000–70,000 costs LE 20** ([Egypt Independent](https://www.egyptindependent.com/e-transfer-fee-hike-banque-misr-bank-of-alexandria-follow-instapays-lead/)).

Corrections:
1. **The fee is charged to the sender.** Your receipt is free. This is not a cost to the business at all — it is EGP 20 of friction on the clinic.
2. **Bank of Alexandria is 0.15%, max EGP 50.** A clinic banking there pays EGP 45, not 20 (same source). Immaterial, but the "EGP 20" figure is bank-specific, not universal.

**"Paymob would take ~EGP 828" — CONFIRMED, and possibly understated.**

Paymob's published rate is **2.75% + EGP 3 per successful card charge** ([Paymob pricing](https://paymob.com/en/pricing)). 30,000 × 2.75% = 825, + 3 = **828**. Exactly right.

> **Pessimistic correction:** payment processing in Egypt is subject to **14% VAT**, and merchants are advised to confirm whether PSP fees are quoted inclusive or exclusive ([PayAtlas](https://payatlas.com/countries/egypt-eg)). Paymob does not state which. If 2.75% is ex-VAT, the real cost is **~EGP 944**. `[UNVERIFIED — VAT treatment not stated on Paymob's pricing page.]` Ask before signing.

#### InstaPay limits — EGP 30,000 fits, EGP 60,000 fits

From InstaPay's own Q&A ([instapay.eg](https://www.instapay.eg/?page_id=348&lang=en)), corroborated by [EnterpriseAM](https://enterpriseam.com/egypt/2026/04/06/instapay-hits-profitability-as-demand-keeps-up-one-year-into-0-1-transaction-fee/) and [Sada Elbalad](https://see.news/after-cbe-decision-instapay-transfer-fees-maximum-limits-explained):

- **EGP 70,000 per transaction**
- **EGP 120,000 daily debit per bank**
- **EGP 400,000 monthly debit per bank**
- **No stated restriction on receiving**

EGP 30,000 is 43% of the per-transaction cap. Even the **EGP 60,000 top tier clears in a single transfer.** No splitting required at any price point.

> **The caveat that matters.** InstaPay's published eligibility describes **individual customers only** — a bank account at a participating bank, a mobile registered with that bank, and a debit or Meeza card ([instapay.eg](https://www.instapay.eg/?page_id=348&lang=en)). **There is no documented business or merchant tier.** CBE has extended InstaPay QR toward merchant payments, but the announced feature was individual-to-individual, with merchant QR "to be introduced later" ([Egypt Today](https://www.egypttoday.com/Article/3/132704/CBE-enhances-InstaPay-with-QR-Code-feature-for-Instant-Payments), [Ahram Online](https://english.ahram.org.eg/News/524682.aspx)). `[UNVERIFIED — no published InstaPay merchant product or business account terms as of July 2026.]`
>
> **Practical consequence:** you will receive EGP 30,000 into a bank account with no merchant tooling and no automatic reconciliation. If that is a *personal* account, you have created a clean audit trail pointing at undeclared business income. **Open a business current account in the منشأة فردية's name and receive there.** This is the one place where skipping registration bites.

#### Fawry — do not use it

Fawry publishes no per-transaction ceiling for direct merchants; via Flutterwave the range is EGP 10–100,000 ([Flutterwave — Fawry FAQ](https://flutterwave.com/gh/support/payments/fawry-pay-faq-egypt)), which is Flutterwave's limit, not necessarily Fawry's. `[UNVERIFIED — Fawry pricing and limits are commercially negotiated, not published]` ([PayAtlas — Fawry](https://payatlas.com/payment-method/fawry-5047)).

Two things kill it regardless:

1. **Fixed cost.** The Startup plan (under EGP 500k/month) carries **EGP 999 one-time setup and a EGP 499 monthly minimum** ([Fawry pricing](https://atfawry.com/pricing)) — **EGP 5,988/year** before a single transaction. On ten licences a year that is more than a fifth of one licence, burned.
2. **Wrong shape.** Fawry's average ticket is around EGP 500. A EGP 30,000 payment at a kiosk is far outside normal use, and the reference code **expires in 30 days** ([Flutterwave](https://flutterwave.com/gh/support/payments/fawry-pay-faq-egypt)).

### T1.3 Recurring / card-on-file — available, and not worth it

**Technically available.** Paymob offers tokenization and subscriptions, with card details stored on Paymob's gateway; "Show Save Card" requires customer consent, "Force Save Card" does not ([Paymob subscriptions](https://paymob.com/en/subscriptions), [WooCommerce Paymob docs](https://woocommerce.com/document/paymob-for-woocommerce/)). Onboarding requirements are the same three documents.

**Practically not worth it.** Three reasons:

1. **Paymob publishes no pricing for Subscriptions** — no fees, no eligibility, no setup steps. `[UNVERIFIED — not published.]`
2. **The economics are inverted.** An annual support renewal billed by card costs 2.75% + EGP 3 *forever*, versus EGP 20 borne by the client on InstaPay.
3. **The market doesn't work that way.** Egyptian clinics predominantly hold debit rather than credit cards, and card-on-file for a B2B supplier is culturally unusual.

**Manual annual renewal is the practical reality, and that is fine.** Issue an e-invoice, send an InstaPay request, chase it by phone. Two people can chase several dozen renewals a year. **Do not build subscription billing.**

### T1.4 Settlement time

| Rail | Settlement |
|---|---|
| **InstaPay / IPN bank transfer** | **Instant, 24/7** ([CBE — Instant Payment Network](https://www.cbe.org.eg/en/payment-systems-and-services/instant-payment-network)) |
| **Paymob (online)** | **Weekly** — *"Your money will be settled in your bank account weekly"* ([Paymob pricing](https://paymob.com/en/pricing)) |
| **Paymob (POS)** | Claims *"guaranteed daily settlements"* ([Paymob POS](https://paymob.com/en/pos-solution)) — **contradicts the pricing page; get it in writing** |
| **Fawry Accept** | **Weekly** ([Fawry pricing](https://atfawry.com/pricing)) |
| **Fawry via Flutterwave** | **5 business days** ([Flutterwave](https://flutterwave.com/gh/support/payments/fawry-pay-faq-egypt)) |
| **Egypt PSPs generally** | 24–72h local merchants; 5–7 business days foreign entities ([PayAtlas](https://payatlas.com/countries/egypt-eg)) |
| **Vodafone Cash** | Instant to wallet; **1% min EGP 3 to cash out** = EGP 300 on 30,000 ([Vodafone Cash](https://web.vodafone.com.eg/en/money-transfer)) |
| **Cash** | Immediate, at the cost of carrying EGP 30,000 across Cairo |

Paymob therefore costs you EGP 828–944 **and** makes you wait a week. InstaPay costs the client EGP 20 and settles in seconds.

### T1.5 Wallets — a bridge, not a destination

Vodafone Cash limits ([Vodafone Cash](https://web.vodafone.com.eg/en/money-transfer)): min EGP 5, **max EGP 60,000 per transaction**, daily cap 60,000, monthly cap 200,000, wallet balance ceiling 100,000. Transfer fee 0.5%, min 1, **max EGP 15**.

EGP 30,000 fits but consumes half the clinic's daily wallet capacity, and the **EGP 60,000 tier sits exactly on the per-transaction ceiling** — no headroom. Worse, **cashing out costs 1%, turning a EGP 15 transfer into a EGP 315 round trip.**

Wallets are how money *reaches* InstaPay — 65% of InstaPay inflows already originate from MNO wallets ([EnterpriseAM](https://enterpriseam.com/egypt/2026/04/06/instapay-hits-profitability-as-demand-keeps-up-one-year-into-0-1-transaction-fee/)). Let the clinic use a wallet to fund an InstaPay transfer; do not accept wallet-to-wallet as the settlement rail.

### T1.6 Cash, and the invoice obligation

**Cash is legal, costs 0%, settles instantly — and changes none of your obligations.** The invoice is not optional.

- **The VAT threshold is EGP 500,000 — and it will not save you.** ETA's own site states 500,000 ([ETA](https://eta.gov.eg/ar/news/altsjyl-aldryby-lmn-lm-tblgh-mbyathm-hd-altsjyl-la-yntj-nh-thsyl-drybt-qymt-mdaft-aw-alaltzam)). **But Art. 16 of Law 67/2016 makes registration compulsory regardless of turnover for every exporter** ([law text](https://consortiolawfirm.com/egypt-vat-law-67-2016-english-translation/), [analysis](https://consortiolawfirm.com/vat-registration-egypt/)). **The moment you invoice one clinic in Amman you must register, at any turnover.** See T4.2 — this is the most consequential tax finding in the document.
  > `[CORRECTED]` A widely-repeated claim that Resolution No. 281/2025 cut the threshold to **EGP 250,000** from 1 January 2026 appears to be **wrong**. ETA's own page for Resolution 281/2025 describes it as *e-receipt system, phase 8 sub-phase 2*, effective 15 September 2025, and mentions no threshold ([ETA](https://www.eta.gov.eg/ar/news/sdwr-qrar-rqm-281-lsnt-2025-alkhas-balmrhlt-alfryt-althanyt-mn-almrhlt-alryysyt-althamnt)); Law 157/2025 did not change it either ([EY](https://www.ey.com/en_gl/technical/tax-alerts/egypt-introduces-significant-vat-updates-on-certain-goods-and-services)). It appears to be an error propagating between vendor blogs. **Moot in practice — as an exporter you register regardless.**
- **Software licences carry 14% VAT.** Software, software maintenance and consultancy are enumerated taxable services at the standard rate ([Andersen Egypt](https://eg.andersen.com/tax-digital-services-in-egypt/), [Anrok — Egypt](https://www.anrok.com/vat-software-digital-services/egypt)). **Decide now whether EGP 30,000 is VAT-inclusive (≈EGP 3,684 remitted) or plus-VAT, and put it in the contract.** Getting this wrong on the first ten deals is a five-figure mistake.
- **B2B e-invoicing is mandatory and real-time.** Mandatory since April 2023; paper invoices ceased to be valid for VAT purposes on **1 July 2023**; invoices must be JSON/XML with a UUID, electronically signed and submitted in real time ([VATupdate](https://www.vatupdate.com/2026/02/23/briefing-document-podcast-e-invoicing-e-reporting-in-egypt/), [Avalara — Egypt e-invoicing](https://www.avalara.com/us/en/vatlive/country-guides/africa-and-middle-east/egypt-vat/egyptian-e-invoicing.html)). **A compliant clinic will demand an e-invoice from you** — it cannot deduct input VAT on a handwritten receipt. This is a sales requirement, not just a tax one.
- **Penalties.** Failure to register: EGP 20,000 plus EGP 1,000/day. Invoicing outside the system: EGP 20,000–100,000. Repeat late reporting: EGP 10,000 per invoice, **uncapped** ([VATupdate](https://www.vatupdate.com/2026/02/23/briefing-document-podcast-e-invoicing-e-reporting-in-egypt/)). Records kept **5 years** ([Fonoa — Egypt](https://www.fonoa.com/resources/country-tax-guides/egypt)).

**On cash specifically:** Non-Cash Payment Law No. 18 of 2019 (effective 8 September 2021) mandates non-cash payment for salaries and public-sector disbursements, with private companies obliged where headcount exceeds 25 or monthly payroll exceeds EGP 100,000; penalties 2%–10% of the cash amount, capped at EGP 1m ([Andersen Egypt](https://eg.andersen.com/non-cash-payment-law-no-18-of-2019/), [Mondaq](https://www.mondaq.com/financial-services/1109694/non-cash-payment-law-no-18-of-2019-legal-alert-156)). A clinic paying a supplier EGP 30,000 in cash is **not** clearly caught by these specific provisions — but the policy direction is unambiguous, and accepting cash gives you no proof of payment unless you sign a receipt.

`[UNVERIFIED]` — no survey or industry data was found on cash norms for **B2B software** sales in Egypt specifically. What is documented is that Egypt remains cash-heavy at consumer level and that policy is deliberately pushing the other way.

### T1.7 Domestic verdict

1. **Collect via InstaPay into a business current account** in the منشأة فردية's name. EGP 20 to the client, zero to you, instant, comfortably inside limits at all three price tiers.
2. **Offer plain bank transfer** as the equal-cost alternative for clinics that don't use InstaPay.
3. **Skip Fawry entirely** — EGP 5,988/year fixed for a handful of transactions.
4. **Add Paymob only on demand**, when a specific client insists on paying by card, and **quote the 2.75% + EGP 3 (possibly +14% VAT) into that deal explicitly** rather than absorbing it.
5. **Do not build recurring billing.** Manual annual renewal invoices.
6. **The expensive part is VAT + ETA e-invoicing, not fees.** Budget accountant time, not gateway fees.

## T2 — Getting paid from abroad into Egypt

This is the section that decides whether Jordan and Morocco exist as markets at all.

### T2.0 The headline answer

**Yes — at least two merchant-of-record platforms document Egypt as an eligible seller location: Paddle and Polar.** Paddle is the stronger of the two on documentation quality; Polar is the stronger on explicitness.

This corrects the prior research gap. Stripe remains unavailable (confirmed), but Stripe is not the only door.

### T2.1 Merchant-of-record platforms — seller eligibility

A merchant of record (MoR) becomes the legal seller. The clinic pays the MoR; the MoR pays Ahmed. This sidesteps *every* problem in T2.3–T2.5: no correspondent banking, no per-country tax registration, no chasing a foreign clinic's bank. It is the single most important structural choice in this document.

The critical distinction — which almost every third-party "supported countries" article gets wrong — is between **countries an MoR can sell TO (buyers)** and **countries a seller can be BASED in**. Paddle's marketing "200+ countries" is a *buyer* number. Only the seller number matters here.

#### Paddle — **eligible, documented** `[VERIFIED]`

Paddle's own help centre states:

> "Paddle works with software businesses anywhere in the world with the exception of the unsupported countries listed below."
> — [Which countries are supported by Paddle?](https://www.paddle.com/help/start/intro-to-paddle/which-countries-are-supported-by-paddle)

The same page confirms the list applies to sellers, not just buyers: *"Paddle is unable to support suppliers operating from the below countries."* The 28 unsupported entries are:

> Afghanistan, Antarctica, Belarus, Burma (Myanmar), Central African Republic, Cuba, Crimea, Democratic Republic of Congo, Donetsk, Haiti, Iran, Iraq, Kherson, Libya, Luhansk, Mali, Netherlands Antilles, Nicaragua, North Korea, Russia, Somalia, South Sudan, Sudan, Syria, Venezuela, Yemen, Zaporizhzhia, Zimbabwe.

**Egypt is not on that list.** By Paddle's own rule ("anywhere in the world except…"), an Egyptian supplier is eligible.

Two further facts make Paddle unusually well-suited to a two-person shop:

1. **No company required.** Paddle's verification page lists three phases — domain review, business verification, identity verification — and explicitly annotates business verification as **"not required for individuals or sole traders."** ([Account verification](https://www.paddle.com/help/start/account-verification/what-is-account-verification)). A **منشأة فردية** — or even an unincorporated individual — can be a Paddle seller. This removes the "you must incorporate a شركة first" blocker entirely.
2. **Payout does not depend on an Egyptian card rail.** *"You can receive your payment either via wire transfer or Payoneer."* Minimum threshold **USD 100** (adjustable up to 100,000); balance converts on the 1st, payment sent by the **15th of the month**, arriving within ~3 working days. *"For most countries, Paddle will not charge you any fees on your payout. However, for certain countries, a $15 SWIFT fee may be applicable."* ([When and how do I get paid?](https://www.paddle.com/help/manage/get-paid/when-and-how-do-i-get-paid)) Payoneer works in Egypt (T2.2), so the payout leg is solved.

**Fees:** headline **5% + $0.50** per transaction, unchanged in 2026, covering processing, billing and global VAT/sales-tax as MoR ([Paddle fees 2026](https://dodopayments.com/blogs/paddle-fees-explained) — competitor-published, but consistent with Paddle's own materials). Third-party analysis puts the *effective* rate nearer **7%** once FX conversion and cross-border card costs are counted. On a USD 590 licence: **~USD 30 headline, ~USD 41 effective**.

**Paddle also supports invoiced B2B sales**, which matters for a clinic that wants a paper invoice rather than a card checkout. Wire transfer is available for **transactions over USD 100**; Paddle generates unique bank details per customer and reconciles automatically; invoices carry 7–14 day terms; bank transfers support **EUR, GBP and USD only**; the invoice also carries a checkout link so the clinic can pay by card or PayPal instead ([Bank transfer — Paddle developer docs](https://developer.paddle.com/concepts/payment-methods/wire-transfer/)). A EGP 30,000 licence at USD 590 clears the USD 100 wire minimum comfortably.

> **Pessimism note.** Paddle documents eligibility; it does not *guarantee* approval. Final acceptance runs through KYB/AML at Paddle's discretion, and Egypt is a higher-risk jurisdiction for compliance teams. Paddle also requires a real domain with a product description, Terms of Service and Privacy Policy before approval. **Treat approval as ~80% likely, not certain, and apply before you need it — not after a clinic has signed.** `[UNVERIFIED]` — no first-hand Egyptian-seller approval account was found in public sources; searches for one returned nothing.

#### Polar — **eligible, Egypt named explicitly** `[VERIFIED]`

Polar is the only platform reviewed that **names Egypt in writing**. Its MoR supported-countries page lists 🇪🇬 Egypt among the countries where *"sellers or organizations need to be established or have residency"* to receive payouts:

- [Polar — Supported countries](https://polar.sh/docs/merchant-of-record/supported-countries)
- [Polar — Supported countries (mirror)](https://polar.apidocumentation.com/documentation/polar-as-merchant-of-record/supported-countries)

Both hosts were fetched independently and agree. Also listed and relevant to expansion: **Morocco, Jordan, Saudi Arabia, UAE, Tunisia, Algeria**.

**Fees** ([Polar — Fees](https://polar.sh/docs/merchant-of-record/fees)):

| Plan | Rate | Monthly |
|---|---|---|
| Starter (free) | 5% + $0.50 | $0 |
| Pro | 3.8% + $0.40 | $20 |
| Growth | 3.6% + $0.35 | $100 |
| Scale | 3.4% + $0.30 | $400 |

Plus **+1.5% for international (non-US) cards** — which is every card Ahmed will ever see. Payout costs are Stripe pass-through with no Polar markup: **$2/month of active payouts, 0.25% + $0.25 per payout, 0.25%–1% currency conversion** outside the EU.

Realistic Polar cost on a USD 590 licence, Starter plan, international card: 5% + 1.5% + $0.50 ≈ **USD 39**.

> **Pessimism note — the load-bearing caveat.** Polar pays out via **Stripe Connect Express**, confirmed by Polar itself ([Polar on X](https://x.com/polar_sh/status/1915379610809782428)). Stripe's *direct merchant* coverage excludes Egypt; Connect Express coverage is broader and is what Polar's Egypt listing rests on. This is a documented statement about a third party's rail, not something Polar controls. **Verify by creating a free Starter account and completing Stripe Express onboarding before relying on it — the failure, if it comes, will surface at payout time, after the clinic has paid.** That is the worst possible moment to discover it. Cost of testing: zero, one hour.

#### Lemon Squeezy — **cannot confirm; strong negative indicators** `[NOT PUBLIC]` + `[UNVERIFIED]`

`docs.lemonsqueezy.com/help/getting-started/supported-countries` returned **HTTP 403** on every attempt (Cloudflare), as did the bank-payouts blog post and the 2026 update post. **The seller-country list could not be retrieved.** Stating this plainly, as instructed: *no verdict either way is available from the primary source.*

What can be established points the wrong way:

1. **The payout rule is the constraint.** Lemon Squeezy's documented rule is that you can sell if you can be paid into a bank or PayPal account in a supported country — **79 countries for bank payouts, 200+ for PayPal** ([Lemon Squeezy — bank payouts expansion](https://www.lemonsqueezy.com/blog/new-bank-payouts)). The PayPal leg is **useless in Egypt**, because Egyptian PayPal accounts cannot receive (T2.4). So everything depends on Egypt being in the 79-country bank list — which is exactly the list that could not be retrieved.
2. **Stripe acquired Lemon Squeezy** (July 2024) and is folding it into **Stripe Managed Payments**, which entered public preview in February 2026 at the same 5% + $0.50 ([Stripe acquires Lemon Squeezy](https://www.lemonsqueezy.com/blog/stripe-acquires-lemon-squeezy); [2026 update](https://www.lemonsqueezy.com/blog/2026-update)). Stripe Managed Payments sits on a Stripe account, and **Stripe does not support Egypt as a business location** ([Stripe supported countries 2026](https://dodopayments.com/blogs/stripe-supported-countries-alternatives)).

**Verdict: do not build on Lemon Squeezy.** Even in the best case it is a platform being migrated into a product Egypt cannot use.

#### Gumroad — **cannot confirm; likely blocked** `[NOT PUBLIC]`

`help.gumroad.com/article/13-getting-paid` renders behind a login wall; the country table could not be read. **The list could not be retrieved.**

Gumroad's documented rule is decisive in shape even without the list: *if your country is not on the direct-deposit list, you can only be paid via PayPal; if PayPal doesn't work in your country, Gumroad has no way to pay you* ([Getting paid by Gumroad](https://help.gumroad.com/article/13-getting-paid)). PayPal does not work for receiving in Egypt (T2.4), so **Egypt must be on the bank list or Gumroad is dead.** Gumroad's own payout-expansion announcement listing new countries named **Jordan, Bahrain, Nigeria, Mauritius and others — Egypt was not among them** ([Gumroad announcement](https://x.com/gumroad/status/1856525514275803638)). That is weak evidence, but it points one way.

Gumroad is in any case the wrong tool: it is built for creators selling digital downloads, not for a B2B ERP licence with setup and support.

#### Payhip — **not a merchant of record; wrong tool** `[VERIFIED]`

Payhip is a storefront that connects **your** gateway; it does not become the seller and does not handle tax. It supports 13 gateways including **PayTabs**, which does cover Egypt, UAE, Saudi Arabia, Oman, Jordan, Iraq and Kuwait ([Payhip payment gateways](https://payhip.com/payment-gateways)).

This solves nothing that matters. PayTabs Egypt requires an Egyptian merchant account, settles in EGP domestically, and leaves Ahmed as the legal seller with full VAT and withholding exposure in the buyer's country. Payhip + PayTabs is a *domestic* checkout with extra steps, not a cross-border solution.

#### Newer MoRs — worth a look, not worth a bet `[UNVERIFIED]`

**Dodo Payments** markets heavily to Egyptian SaaS founders and publishes a "Merchant of Record in Egypt" guide, but that page — read in full — only ever discusses Egypt as a **buyer** market (220+ countries for tax handling). It never states that Dodo onboards **Egypt-based sellers**, and gives no seller KYC or payout detail ([Dodo — MoR in Egypt](https://dodopayments.com/blogs/merchant-of-record-in-egypt)). **Marketing aimed at Egyptians is not the same as accepting Egyptians.** Treat as unconfirmed.

**Creem** covers roughly 100 countries with acknowledged gaps in Africa; Egypt not confirmed. `[UNVERIFIED]`

Both are young and thinly capitalised relative to Paddle. For a business whose entire foreign revenue would flow through one pipe, that is a real counterparty risk.

#### Summary table — MoR seller eligibility for Egypt

| Platform | Egypt as seller? | Evidence quality | Verdict |
|---|---|---|---|
| **Paddle** | **Yes** — not on the 28-country exclusion list; sole traders explicitly allowed | Primary source, explicit rule | **Primary choice** |
| **Polar** | **Yes** — Egypt named on the list | Primary source, two hosts | **Free backup; test now** |
| Lemon Squeezy | Unknown; PayPal leg unusable, Stripe migration blocks it | List unretrievable (403) | Avoid |
| Gumroad | Unknown; PayPal leg unusable, Egypt absent from expansion announcement | List behind login | Avoid |
| Payhip | N/A — not an MoR | Primary source | Wrong tool |
| Dodo / Creem | Unconfirmed for sellers | Marketing only | Do not bet |
| Stripe (direct) | **No** | Confirmed | Blocked |

### T2.2 Payout wallets — Payoneer, Wise, Deel, Skrill

These are the pipes that get MoR money, or direct client money, into Egypt.

**Payoneer — works, and is the default for Egypt** `[VERIFIED, mixed sourcing]`
Payoneer operates in Egypt: Egyptian users can receive international payments and withdraw to local bank accounts ([Grey — receiving freelance payments in Egypt](https://grey.co/blog/how-to-receive-freelance-payments-in-egypt)). It is also one of Paddle's two payout rails, which closes the loop cleanly.

The costs are heavy and compound:
- ~**1%** to receive
- up to **~3%** withdrawal
- **~2%–4.5%** conversion into EGP
- **USD 29.95/year** card fee
- **Total on a USD 1,000 withdrawal ≈ 5.7%** ([Payoneer fees 2026 breakdown](https://vaultleap.com/blog/payoneer-fees-explained-2026); [Cenoa — Payoneer alternatives Egypt 2026](https://www.cenoa.com/blog/payoneer-alternatives-egypt-2026-guide-freelancers))

**The important restriction:** when adding an Egyptian bank account in Payoneer, **the currency defaults to EGP and cannot be changed** — Egyptian users report being unable to withdraw USD as USD to a local USD account ([Payoneer community thread](https://community.payoneer.com/en/discussion/30412/how-can-i-withdraw-money-from-payoneer-account-to-usd-bank-account-in-a-bank-located-in-egypt)). **Money can be held in USD inside Payoneer, but arrives in Egypt as EGP.** This is a de-facto conversion requirement (T2.3), and it is the reason the effective cost is 5–6% rather than 1%.

**Wise — cannot confirm for Egypt** `[NOT PUBLIC]`
Wise's own country page lists unsupported countries — Afghanistan, Belarus, Burundi, CAR, Chad, Congo, DRC, Cuba, Eritrea, Iran, Iraq, North Korea, Libya, Myanmar, Somalia, South Sudan, Russia, Sudan, Syria, Yemen, Venezuela and occupied Ukrainian regions — and **Egypt is not among them** ([Which countries can I use Wise in](https://wise.com/uk/help/articles/2978049/which-countries-can-i-use-wise-in)). But Wise publishes **no positive list** of countries where an account can be opened and balances held; the page only says you can hold money "if you live in a country where you can open a Wise account," which is circular. Separately, Wise's currency page lists **EGP as send-only, "within Egypt"** ([Guide to EGP transfers](https://wise.com/help/articles/2932365/guide-to-egp-transfers)) — Wise moves money *to* Egypt, which is not the same as an Egyptian business holding a Wise Business account. **Absence from a blocklist is not presence on an allowlist.** Do not plan around Wise; test it if you want a second wallet.

**Deel** — Deel is a contractor-payment platform: it works when the *foreign party* is the one paying through Deel. A veterinary clinic in Amman buying a perpetual licence will not onboard to Deel to pay a USD 590 invoice. Structurally wrong for one-off software sales. `[UNVERIFIED for Egypt B2B receipt]`

**Skrill** — reportedly available in Egypt for sending and receiving ([Skrill serviced countries](https://www.skrill.com/en/support/question/11/which-countries-are-serviced-by-skrill/)). Not recommended: consumer-wallet positioning, poor B2B invoicing, weak acceptance among Gulf and Maghreb businesses, and it does nothing an MoR or Payoneer doesn't do better.

### T2.3 Direct SWIFT transfer into Egypt — what actually happens

This is the route people assume works. It works, but badly.

**Forced conversion.** An inbound foreign-currency wire landing on an **EGP-denominated** account is converted automatically at the bank's rate. To keep USD as USD, the business must hold a **foreign-currency account** at an Egyptian bank ([banker.news — receiving USD from abroad into an EGP account](https://www.banker.news/96634)). Opening one is the difference between keeping dollars and being converted at whatever the bank quotes.

**Correspondent friction.** A wire from a Gulf or Maghreb bank to Egypt passes through correspondent banks that each deduct roughly **USD 10–25** in transit; the Egyptian bank then converts at an internal rate typically **1%–3% below mid-market**, with the spread not disclosed before conversion ([Grey — Egypt's currency controls](https://grey.co/blog/what-egypts-currency-controls-mean-for-international-payments)). On a USD 590 invoice, USD 20–50 of correspondent fees plus a 1–3% spread is a **5–10% effective haircut** — comparable to an MoR, but with none of the MoR's tax and compliance coverage.

**Documentation.** Egyptian banks may require an invoice or contract explaining the purpose of an inbound transfer before releasing funds, and risk flags on the amount, counterparty, country or stated purpose can trigger a manual review lasting days ([Grey](https://grey.co/blog/what-egypts-currency-controls-mean-for-international-payments); [trade.gov Egypt Country Commercial Guide](https://www.trade.gov/country-commercial-guides/egypt-trade-financing)). **Always send a proper invoice with the payment, and put a clean, boring purpose-of-payment description on the wire** ("software licence fee, invoice #…"). Vague or unusual descriptions are what cause holds.

**The environment has improved.** Since the March 2024 float and subsequent easing, the CBE has removed the FX transfer limit, licensed banks to credit inbound remittances instantly ([CBE — availing inbound remittances instantly](https://www.cbe.org.eg/en/news-publications/news/2024/12/05/11/18/availing-inbound-remittances-to-customers-bank-accounts-instantly)), and banks have cut card FX markups (NBE 5%→3%, CIB to 3% from 13 Aug 2025 — [Ahram Online](https://english.ahram.org.eg/News/551158.aspx)). Receiving foreign currency for exported services is permitted through licensed banks, with individuals generally able to transfer up to **USD 100,000/year** without special CBE approval ([Egypt Today](https://www.egypttoday.com/Article/3/141676/Travelers-gain-easier-access-to-foreign-currency-as-banks-relax)). At USD 590 per licence, no plausible volume comes near any threshold. **The constraint is friction and cost, not legality.**

### T2.4 PayPal in Egypt — effectively dead for receiving

**An Egyptian PayPal account cannot receive money.** Egyptian accounts are limited to *sending* payments; funds cannot be received from other PayPal users or clients into an Egypt-registered account, and withdrawal is to an Egyptian Visa card rather than a bank account, taking up to 7 business days ([doola — PayPal in Egypt 2026](https://www.doola.com/paypal-guide/how-to-open-a-paypal-account-in-egypt/); [OneSafe — Does PayPal work in Egypt](https://www.onesafe.io/blog/does-paypal-work-in-egypt)).

PayPal's own Egypt page is unhelpfully vague — it notes that in some countries receiving money "requires linking your account to a licensed local partner" and gives Nigeria as the worked example, without stating Egypt's position ([PayPal EG — set up to receive and withdraw](https://www.paypal.com/eg/webapps/mpp/setup-to-receive-withdraw?locale.x=en_EG)). **PayPal does not publish a clear Egypt receiving policy.** `[NOT PUBLIC]` for the official position; `[VERIFIED]` by consistent secondary reporting that receiving does not work.

**Consequence:** every platform whose fallback payout is "PayPal in your country" — Gumroad, Lemon Squeezy's 200-country tier — is unusable in Egypt via that path. This is why the MoR question reduces to *bank/Payoneer payout availability*, and why Paddle (wire + Payoneer, no PayPal) is structurally the better fit.

### T2.5 Central Bank rules, and whether export-of-services registration helps

**CBE rules on receiving FX for services.** No CBE rule was found prohibiting or restricting an Egyptian business from receiving foreign currency for exported services. `[UNVERIFIED — no explicit CBE circular located]`; the position is inferred from the CBE permitting banks to credit inbound remittances instantly, FX forwards being permitted against "proceeds of exporting goods and services" ([Shalakany — CBE circular on FX forwards/swaps](https://shalakany.com/cbe-circular-amending-the-regulations-of-fx-forwards-and-fx-swaps-transactions-carried-out-by-banks/)), and the general permission to hold FX accounts. **Receiving is fine. Getting a good rate and keeping dollars is the hard part.**

**Export-of-services registration — the real prize is ITIDA, not FX relief.** Registration does not change what you are allowed to receive. It changes what you get *back*.

ITIDA's **Export IT** programme pays direct cash incentives on value-added ICT exports ([ITIDA — Export IT](https://itida.gov.eg/English/Programs/Export-IT/Pages/Default.aspx)):
- Eligibility: ICT company **headquartered in Egypt with >50% Egyptian ownership**, exporting ICT/ITES services
- **"There is no minimum with respect to the company's export proceeds, size, and number of employees"** — a two-person shop qualifies
- **Micro** = up to EGP 2m annual revenue; **Small** = EGP 2m–20m
- Main support **10%–35% of value-added exports** by company size, with **additional 10% or 5% for micro and small companies** under specific conditions
- Ceiling **EGP 2.5m per company**
- The programme was extended and broadened for FY 2025/2026 under an ITIDA–Export Development Fund protocol ([Zawya](https://www.zawya.com/en/economy/north-africa/egypt-adds-technology-services-to-export-development-program-under-itida-export-fund-deal-eibfsdkk))

On EGP 300,000 of foreign licence sales, a micro-company rebate in the 10–35% band is **EGP 30,000–105,000** — i.e. one to three extra licences' worth of margin, for paperwork. It does not change collection mechanics, so it is not week-one work, but it is the strongest argument for eventually incorporating rather than staying a منشأة فردية.

> `[UNVERIFIED]` — ITIDA's page says "companies" and does **not** state whether a **منشأة فردية** qualifies or whether a **شركة** is required. This needs a direct question to ITIDA before it drives any incorporation decision.

## T3 — What the buyer can actually pay with

### T3.0 The headline answer

**No market is killed by outward-remittance controls. The fear about Morocco was misplaced — and Morocco actually got *easier* on 1 January 2026.**

The thing that damages these markets is **withholding tax and reverse-charge machinery**, not exchange control. Ranked by what a USD 590 licence actually costs the buyer:

| Market | FX controls | Loaded cost to buyer | Verdict |
|---|---|---|---|
| **UAE** | None | ~USD 590 | **Cleanest market** |
| **Morocco** | Delegated to banks; software explicitly permitted | ~USD 650 (10% RAS) | **Open — go** |
| **Saudi Arabia** | None | USD 590–680 (0% or 15%, classification gamble) | Sell only to VAT-registered buyers |
| **Jordan** | **Freest of the four** | **~USD 790 (+31%)** | **Worst unit economics despite freest FX** |

The structural insight: **at a USD 600 ticket you are fighting machinery built for USD 600,000 deals.** That, not exchange control, is what pushes buyers to ask for a local reseller — and it is the strongest argument for the merchant-of-record route in T2.

### T3.1 Morocco — open, and the fear was misplaced

**Software is an explicitly named importable service.** The Office des Changes lists *"les services informatiques"* among importable services, defining them to cover *"l'acquisition de logiciels et des prestations qui y sont rattachées"*, with banks authorised to settle *"logiciels et/ou de prestations connexes acquis de l'étranger par téléchargement"* ([Office des Changes — nature et consistance des importations de services](https://www.oc.gov.ma/fr/personnes-morales/nature-et-consistance-des-importations-de-services)).

**No prior Office des Changes authorization is needed.** Authorization is required only for guaranteed minimum royalties and franchise entry fees. Software is not on that list ([Office des Changes FAQ](https://www.oc.gov.ma/fr/faq?field_categorie_target_id=29)). Trade.gov confirms the general delegation: *"the Foreign Exchange Office delegated to authorized Moroccan banks the power to freely carry out settlements relating to imports, exports, international transport, insurance and reinsurance, foreign technical assistance…"* ([trade.gov — Morocco trade financing](https://www.trade.gov/country-commercial-guides/morocco-trade-financing)). Morocco operates under IMF Article VIII, guaranteeing convertibility for current transactions.

**Can a clinic just pay by card? Yes.** Article 121 of IGOC 2026 sets the e-commerce dotation ([Office des Changes — commerce électronique à l'international](https://www.oc.gov.ma/fr/commerce-electronique-a-international), [FAQ — carte de paiement internationale](https://www.oc.gov.ma/fr/faq/les-entreprises-marocaines-peuvent-elles-regler-par-carte-de-paiement-internationale-leurs)):

| Beneficiary | Annual ceiling |
|---|---|
| Resident individuals | MAD 20,000 |
| **Companies without FX accounts** | **MAD 200,000 per calendar year per vendor** |
| Companies with IS/IR under 50,000, tax-exempt, or newly created | **MAD 50,000 floor** |
| Categorised operators | up to MAD 1,000,000 |
| ADD-labelled tech startups | MAD 2,000,000 |

The official text: *"les entités de droit marocain qui ne disposent pas de comptes en devises ou en dirhams convertibles, peuvent régler par carte de paiement internationale dans la limite de deux cent mille (200.000) dirhams par année civile et par bénéficiaire."*

**A EGP 30,000 licence is roughly MAD 6,000 — inside even the lowest MAD 50,000 floor, by a factor of eight.** There is no plausible clinic that cannot pay this by company card.

**IGOC 2026, in force 1 January 2026, loosened this further** — it *"improves the import service settlement regime by removing the limited list of operations delegated to banks"* and raised the dotations ([Office des Changes — IGOC 2026 press release (PDF)](https://www.oc.gov.ma/sites/default/files/2025-12/Release%20IGOC%202026_0.pdf); [publication notice](https://www.oc.gov.ma/en/actualites/publication-de-l-instruction-generale-des-operations-de-change-2026)).

> **Two operational traps that can manufacture the problem you feared:**
>
> 1. **Never ship physical media.** Download delivery needs no import title. Software on a USB stick or DVD triggers a domiciled *titre d'importation* plus customs clearance — turning a clean card payment into a customs file.
> 2. **The bank must verify that tax on the acquisition has been settled** (*"le paiement des impôts et taxes dus au titre de l'acquisition de logiciels"*) before releasing funds. **The 10% withholding must be paid first, or the transfer stalls.** Sequence this in the contract.

**Tax:** 10% *retenue à la source* under CGI Article 15 ([Fiscamaroc — CGI art. 15](https://www.fiscamaroc.com/l-impot-societes-1/produits-bruts-percus-personnes-20.htm)), plus 20% reverse-charge VAT (neutral for a VAT-registered clinic). The Egypt–Morocco treaty caps royalties at 10% — identical to domestic law, so **zero relief** (T4.1).

**Convertibility status:** full convertibility is *not* achieved and capital-account operations still need authorization; Bank Al-Maghrib's next flexibilisation stage resumes in 2026 targeting semi-liberalisation, not a float ([Hespress](https://fr.hespress.com/392925-bam-la-flexibilisation-du-regime-de-change-devrait-reprendre-en-2026.html), [LesEco](https://leseco.ma/maroc/assouplissement-du-regime-de-change-2026-comme-horizon.html)). **Irrelevant here** — a software licence is a current-account transaction, not a capital one.

`[UNVERIFIED]` — IGOC 2026 article numbers could not be quoted verbatim (the official [IGOC 2026 PDF](https://www.oc.gov.ma/sites/default/files/reglementation/pdf/2026-01/IGOC%202026.pdf) exceeds fetch limits); no DGI text expressly classifying a *perpetual* licence as a royalty was located; PayPal Morocco's status unconfirmed. Wise cannot send **from** MAD.

### T3.2 Jordan — freest FX, worst economics

**Exchange control: explicitly none.** CBJ Foreign Currency Instructions state verbatim that *"Visible and invisible payment transactions shall be fulfilled without any restrictions"* (Art. 2), and that withdrawals and transfers from resident FX accounts *"are allowed without any restrictions"* (Art. 7) ([CBJ — Foreign Currency Instructions (PDF)](https://www.cbj.gov.jo/ebv4.0/root_storage/en/eb_list_page/17911475-3a16-4cbe-ac16-a3ca0bc8a846.pdf)). A licence fee is an invisible transaction. Jordan accepted IMF Article VIII obligations in 1995 and the JOD is *"fully convertible for all commercial and capital transactions"* ([US State Dept — Jordan ICS 2025](https://www.state.gov/reports/2025-investment-climate-statements/jordan)). `[UNVERIFIED — the published CBJ PDF carries no instruction number or date.]`

**AML:** USD 590 ≈ JOD 426, below the JOD 700 enhanced-CDD threshold, but originator/beneficiary details including *"Purpose of the transfer"* remain mandatory ([CBJ AML/CFT Instructions 14/2018](https://www.amlu.gov.jo/ebv4.0/root_storage/en/eb_list_page/anti_money_laundering_and_counter_terrorist_financing_instructions_no.14-2018_of_banks.pdf)). Another reason to put a clean, boring purpose line on every invoice.

**Wire cost is trivial:** Arab Bank charges **JOD 6** for outward remittances up to JOD 500, SWIFT free ([Arab Bank fees and charges](https://www.arabbank.jo/footernavigation/fees-and-charges/retail-fees-and-charges)).

**And then the tax stack ruins it:**

- **11% withholding**, not 10% — 10% under Income Tax Law 34/2014 Art. 12(B)(1) plus a **1% national contribution tax** ([BDO Jordan Country Guide (PDF)](https://www.bdo.com.jo/getattachment/5d2913c1-424d-43d3-adfa-5bd134f114f1/CG_Jordan_2024_Final.pdf?lang=en-GB), [PwC Jordan](https://taxsummaries.pwc.com/jordan/corporate/withholding-taxes)). Declared within 30 days.
- **The treaty is dead weight** — the Egypt–Jordan royalty rate is 20%, above Jordan's own 10%, so it can never apply. **No relief whatsoever** (T4.1).
- **16% GST reverse charge**, GST Law arts. 4, 9(E), 26 — and **the ugly part: Art. 13(b) requires a service importer to register for GST within 30 days of the first import, regardless of value, with no threshold protection** ([BDO Jordan VAT Navigator (PDF)](https://www.bdo.com.jo/getattachment/827089db-2161-4aec-a718-03e0ce5307bb/VAT_Jordan_2024_Final3.pdf?lang=en-GB)).

**Loaded cost of a USD 590 licence to a Jordanian clinic: ~USD 790, a 31% premium.** Jordan was chosen as the "small, cheap test" market. On payment mechanics it is the **most expensive of the four** — worth knowing before treating a Jordanian pilot's conversion rate as representative.

**No local agent is legally required.** Law 28/2001 regulates who may *act as* an agent in Jordan; it does not stop an end user buying direct ([Chambers — Jordan commercial contracts 2025](https://practiceguides.chambers.com/practice-guides/commercial-contracts-2025/jordan)).

`[UNVERIFIED, and it decides whether the 16% is a real cost or a wash]` — whether veterinary clinical services are GST-**exempt** (no input credit, so the 16% sticks) or **zero-rated** (credit available). Also unverified: whether ISTD actually enforces Art. 13(b) against a one-off sub-threshold import.

### T3.3 Saudi Arabia — no FX controls, a real classification gamble

**No exchange controls:** *"There are currently no restrictions on converting and transferring funds… other than certain withholding taxes"* ([US State Dept — Saudi Arabia ICS](https://www.state.gov/reports/2024-investment-climate-statements/saudi-arabia)). Note the carve-out — the withholding *is* the story.

**The 0%-versus-15% question.** ZATCA's February 2024 software guideline draws a line that turns on one undefined word. It classifies as **commercial profits (0% WHT)**:

> "Granting non-exclusive, non-transferable license to access a **standardized** or customized software for business use."

but as a **royalty (15%)**:

> "Granting non-exclusive, non-transferable license to access a software for business use."

DLA Piper notes the guideline **never defines "standardized"**, leaving boundary cases genuinely uncertain ([DLA Piper — Gulf Tax Insights, February 2024](https://www.dlapiper.com/en/insights/publications/gulf-tax-insights/2024/gulf-tax-insights-february-2024/taxation-of-software-payments-in-saudi-arabia)).

> **Pessimistic read:** a standardised perpetual clinic licence *should* land at 0%. But a small clinic's bookkeeper facing a 1%-per-30-days penalty for under-withholding **will withhold 15% and will not argue.** Budget for 15%; treat 0% as upside. The Egypt–Saudi treaty caps royalties at 10%, but claiming it needs a residency certificate and ZATCA forms — **nobody does that paperwork for USD 90.**

**VAT 15% reverse charge**, net zero for a VAT-registered buyer ([ZATCA RCM circular via PwC (PDF)](https://www.pwc.com/m1/en/tax/documents/2021/saudi-arabia-circular-on-the-reverse-charge-mechanism-application.pdf)).

> **Trap:** if the clinic is **below SAR 375,000 and unregistered**, reverse charge does not apply and the **non-established supplier technically must register for Saudi VAT within 30 days** ([Grant Thornton — KSA indirect tax](https://www.grantthornton.global/en/insights/indirect-tax-guide/indirect-tax---Saudi-Arabia/)). **Sell only to VAT-registered Saudi buyers and put their VAT number on the invoice.** This is a hard rule, not a preference.

**No agent required:** *"American exporters are not required to appoint a local Saudi agent or distributor to sell to Saudi companies"* — recommended only for government business ([trade.gov — Saudi Arabia distribution](https://www.trade.gov/country-commercial-guides/saudi-arabia-distribution-and-sales-channels)). The same source notes face-to-face introduction is culturally expected.

**Instruments:** mada cards are co-badged Visa/Mastercard, so card payment works ([Checkout.com — mada](https://www.checkout.com/payment-methods/mada)). Wires are cheap — Al Rajhi ~SAR 40 online, SAB SAR 15–40 `[UNVERIFIED — blog-tier sourcing; official schedules unreachable]` ([Giraffy comparison](https://giraffy.com/ksa/en/learn/banking-money/money-transfers/bank-fees-comparison), [SAB](https://www.sab.com/en/personal/payments-and-transfers/international-remittance/)).

### T3.4 UAE — genuinely frictionless

- **No FX controls.** No restrictions on payments and transfers for international transactions ([US State Dept — UAE ICS 2025](https://www.state.gov/reports/2025-investment-climate-statements/united-arab-emirates)).
- **0% withholding tax**, with *"no registration or filing obligation"* expected ([PwC UAE](https://taxsummaries.pwc.com/united-arab-emirates/corporate/withholding-taxes)).
- **5% VAT reverse charge**, netting to zero; FTA Public Clarification **VATP044** (May 2025) confirms ([Andersen UAE](https://ae.andersen.com/insights/tax-updates/vaton-imported-servicesinthe-uae:ftaclarifies-reverse-charge-rules(vatp044))).
- **Actionable invoicing detail:** put supplier name, recipient name, date, description, value and currency on the invoice and the buyer needs no self-invoice under Art. 59 of the Executive Regulations ([CLA Emirates](https://www.claemirates.com/do-you-need-to-issue-a-tax-invoice-for-import-of-services-under-reverse-charge-mechanism-rcm-in-the-uae)). **No vendor TRN required.**
- **No local agent required** since Federal Law 3/2022 ([Pinsent Masons](https://www.pinsentmasons.com/out-law/guides/business-uae-distribution-products-without-local-agent)).
- **A 2027 tailwind:** Small Business Relief (0% corporate tax below AED 3m revenue) **expires 31 December 2026** ([gtag.ae](https://www.gtag.ae/post/small-business-relief-ends-31-december-2026-5-things-uae-smes-must-do-before-the-clock-runs-out)). From 2027 UAE clinics will want a properly documented invoice because the expense becomes a real deduction — a small but genuine selling point.
- **Al Ansari Exchange runs a proper Corporate Remittance product** for supplier payments, online platform, 2–4 day settlement ([Al Ansari](https://alansariexchange.com/service/corporate-remittance/)) — likely cheaper than a bank wire at this ticket size.

`[UNVERIFIED]` — the UAE's Peppol-based e-invoicing rollout phasing from 2026 and whether it touches inbound foreign purchases.

### T3.5 Instruments — what actually works, and what doesn't

**Buna (Arab Regional Payment System) is a dead end.** It is live but tiny — roughly 110 institutions and ~15,000 transactions/month ([Asian Banker](https://www.theasianbanker.com/updates-and-articles/buna-poised-to-transform-cross-border-payments-in-the-arab-region-and-beyond)) — and it is a **wholesale interbank FMI that an SME cannot address**: eligibility is *"central banks, commercial banks, or any other financial institution"* ([Buna — the organization](https://one.buna.co/the-organization)). Coverage ([participants](https://one.buna.co/participants), [currencies](https://one.buna.co/currencies)):

- **Egypt:** well represented (CBE, NBE, Banque Misr, CIB, Banque du Caire)
- **Jordan, UAE:** good coverage
- **Saudi Arabia:** exactly one commercial bank (SAB)
- **Morocco:** Bank Al-Maghrib and Attijariwafa only — **and MAD is not a Buna settlement currency.** Functionally zero.

Buna also still rides SWIFT for messaging and publishes no fee schedule. Treat it as "ask your relationship manager," never as a plan.

**SWIFT eats 6–12% of a USD 590 invoice.** Sending fees are modest (Jordan ~USD 8.5, UAE AED 73.50, Saudi ~USD 12–18, Morocco 1.5‰ min MAD 150), but correspondent hops deduct USD 15–25 each and the Egyptian receiving bank adds its own spread `[UNVERIFIED — no primary source for correspondent deductions on this specific corridor]`.

**PayPal is a trap on Ahmed's side, not the buyer's.** All four buyer countries are "send, receive and withdraw" — but **Egypt is absent from PayPal's country-feature table entirely** ([PayPal developer — country feature reference](https://developer.paypal.com/docs/payouts/standard/reference/country-feature/)), despite an Egypt merchant fee schedule existing. Even if it worked, fees stack to ~9–10%. **Do not architect around PayPal without a demonstrated withdrawal** (T2.4).

**Stripe supports none of the relevant seller markets.** Egypt, Jordan, Morocco and Saudi Arabia are all absent from [Stripe's global availability list](https://stripe.com/global); only UAE is supported.

**Wise is out for three of four:** AED and MAD are send-to-only; SAR and JOD unsupported ([Wise — currency matrix](https://wise.com/help/articles/2571907/what-currencies-can-i-send-to-and-from)). "Western Union Business Solutions" no longer exists — it became **Convera** ([Businesswire](https://www.businesswire.com/news/home/20230710685281/en/Convera-Announces-Final-Closing-of-Western-Union-Business-Solutions-Completing-Global-Transition)).

**Egypt is not sanctioned or FATF-listed** ([FATF — Egypt](https://www.fatf-gafi.org/en/countries/detail/Egypt.html)). No compliance blocker; correspondent-banking cost is the only issue.

**The two rails that actually work at this ticket size:**

1. **Paddle as merchant of record** — the buyer pays Paddle by card or by wire against a Paddle invoice, in local-feeling currency, with no withholding, no reverse charge and no residency certificate. **This is the answer.**
2. **Payoneer "Request a Payment"** — Ahmed issues a payment request; the buyer pays by Visa/Mastercard/Amex or local transfer from 190+ countries ([Payoneer — payment request](https://www.payoneer.com/get-paid-by-clients/payment-request/)). Open on both ends in all four countries. ~3–5%. **Good fallback, but it does not solve withholding** — Ahmed is still the seller of record.

### T3.6 The reseller question — the real finding

**No country legally requires a local agent** (sourced above for Jordan, Saudi Arabia and the UAE). But the tax analysis explains why buyers will *ask* for one anyway: **a local reseller invoicing in local currency eliminates the withholding, the reverse-charge entry, the residency-certificate exercise and the wire cost in a single move.** In Jordan it also sidesteps the Art. 13(b) registration trap; in Saudi Arabia it sidesteps both the 15%/0% classification gamble and the non-resident VAT registration exposure.

This is a commercial force, not a legal one — and **the MoR route neutralises most of it**, which is why Paddle is worth more than its 5%.

`[UNVERIFIED]` — whether SMEs in these markets *culturally* prefer buying direct versus through a local reseller. **No survey or trade report was found in any of the four countries. Do not let anyone represent this as sourced.**

## T4 — Tax and invoicing

### T4.1 Withholding tax the buyer's country deducts — verified rates

This is money that never arrives. The buyer deducts it and remits it to their own tax authority. On a USD 590 licence, 10% is USD 59 gone before Ahmed sees anything.

| Buyer country | Domestic WHT on services/royalties to non-residents | Egypt treaty royalty rate | **Effective loss** |
|---|---|---|---|
| **Morocco** | **10%** — *"all payments of all kinds of services rendered by non-resident entities are subject to WHT at the rate of 10%"* ([PwC Morocco](https://taxsummaries.pwc.com/morocco/corporate/withholding-taxes)) | **10%** (Egypt row: `12.5 / 10 / 10 / 10`) | **10% — treaty gives no relief** |
| **Jordan** | **10%** on royalties, technical service fees and imported services, **plus ~1% national contribution tax = ~11%** ([Deloitte Jordan Highlights 2025](https://www.deloitte.com/content/dam/assets-shared/docs/services/tax/2025/dttl-tax-jordanhighlights-2025.pdf), [PwC Jordan](https://taxsummaries.pwc.com/jordan/corporate/withholding-taxes)) | **20%** (Egypt row: in force 1/1/1998, `15 / 15 / 20`) | **~11% — treaty cap sits *above* domestic law and is therefore useless** |
| **Saudi Arabia** | **15% royalties**, 5% technical/consulting services, 20% management fees ([PwC Saudi Arabia](https://taxsummaries.pwc.com/saudi-arabia/corporate/withholding-taxes), [ITL art. 68](https://gcctaxlaws.com/articles/ksa-income-tax-law-of-2004-article-68)) | **10%** (Art. 12(2), treaty in force 1 July 2017 — [ZATCA](https://zatca.gov.sa/en/RulesRegulations/Agreements/Pages/egypt-convention.aspx)) | **Realistically 15%** — see below |
| **UAE** | **0%** — *"a WHT (currently set at 0%) will apply to certain types of UAE-sourced income derived by non-residents"*, with no expected registration or filing obligation ([PwC UAE](https://taxsummaries.pwc.com/united-arab-emirates/corporate/withholding-taxes)) | n/a | **0%** |

#### Does the India problem repeat? — **No. Both treaties have a royalty article. It changes nothing.**

Prior research found the India–Egypt treaty has **no royalty article**, leaving ~20% unrelieved. **Checked directly: neither the Egypt–Morocco nor the Egypt–Jordan treaty has that defect. Both contain a full Article 12 Royalties. Neither helps — for a different reason in each case.** Egypt's treaty texts are published at [eta.gov.eg — bilateral agreements](https://www.eta.gov.eg/en/content/bilateral-agreements).

- **Morocco — the article exists and is exactly redundant.** Treaty signed Rabat 22 March 1989, in force 21 September 1993 ([DGI conventions list](https://portail.tax.gov.ma/wps/wcm/connect/dgi-fr/dgi-vfr/documentation%20fiscale2/fiscalite%20internationale); [Arabic text](https://eta.gov.eg/sites/default/files/2024-09/almghrb.pdf)). Article 12 caps royalties at **10%** — *"بسعر لا يجاوز 10% من قيمتها الإجمالية"*. Morocco's domestic rate is also **10%**. **Zero relief.**
  > **And the business-profits escape is unavailable in Morocco.** CGI Article 15 category **X** is a catch-all — *"rémunérations des prestations de toute nature utilisées au Maroc ou fournies par des personnes non résidentes"* ([CGI 2026, p.47](https://www.tax.gov.ma/wps/wcm/connect/08712531-1e81-4e28-a38b-2bd9edf8e09e/CGI+2026+FR.pdf?MOD=AJPERES)). Morocco taxes the gross payment at source **without requiring any establishment**. Arguing "this is business profits, not a royalty" does not work there.
- **Jordan — the article exists and points the wrong way.** Treaty signed Amman 8 May 1996, effective 1 January 1998, modified by the BEPS MLI ([English text](https://eta.gov.eg/sites/default/files/2024-09/jordon.pdf)). Article 12 caps royalties at **20%** — *above* Jordan's own 10% domestic rate. A treaty caps tax and never increases it, so **Jordan simply applies ~11% and the treaty relieves nothing. Do not spend money on a residence certificate for Jordan.**
  > **Recharacterisation is also futile in Jordan**: domestic law applies 10% to royalties, to imported services, *and* as a catch-all to "other payments to non-residents" ([BDO Jordan §5.4–5.5](https://www.bdo.com.jo/getattachment/5d2913c1-424d-43d3-adfa-5bd134f114f1/CG_Jordan_2024_Final.pdf?lang=en-GB)). Every route lands on the same rate.
  >
  > `[DISCREPANCY NOTED]` an older ETA-hosted copy of the treaty extracted as "10 per cent" on the royalty article. PwC's two independent country tables both showing 20% is the stronger evidence. **Practically moot** — domestic 10% is below either figure.
- **Saudi Arabia — the treaty helps on paper and not in practice.** Egypt–Saudi Art. 12(2) caps royalties at **10%** against a domestic 15%. But **Art. 12(4) expressly names "برامج كمبيوتر" (computer programs)** in the royalty definition, so there is **no arguing Article 7 business profits at treaty level**. Best achievable is 10%, never 0%.
  > **The arithmetic kills it.** ZATCA's January 2025 bulletin allows relief at source (Form Q7/B + Egyptian tax residency certificate + **Saudi embassy attestation or Apostille** + Form Q7C undertaking signed by the Saudi buyer accepting liability) or a refund claim ([KPMG Saudi Arabia](https://kpmg.com/sa/en/insights/tax-insights/tax-alert-zatca-releases-a-tax-bulletin-on-the-application-of-wht-under-dtaas.html)). **The treaty saves USD 30 on a USD 590 sale. No Saudi finance department will apostille documents and sign a liability undertaking for a USD 590 vendor. Budget 15%.**
- **UAE — clean.** 0%, no filings, no registration obligation ([UAE MoF](https://mof.gov.ae/en/public-finance/tax/corporate-tax/), Art. 45 Federal Decree-Law 47/2022). ⚠️ Art. 45 delegates the rate to Cabinet Decision, so a future decision could impose a positive rate without amending the law.

#### Saudi Arabia deserves its own warning — ZATCA has ruled on exactly this product

ZATCA published a **Guideline for Taxation of Software Payments**, v1, January 2024, with 29 fact patterns ([ZATCA PDF](https://www.zatca.gov.sa/en/HelpCenter/guidelines/Documents/guidelines%20for%20Taxation%20of%20Software%20Payments%20in%20the%20context%20of%20domestic%20Income%20Tax%20Law%20%20En.pdf); [KPMG](https://kpmg.com/sa/en/insights/tax-insights/tax-alert-tax-treatment-of-software-payments-in-the-context-of-the-income-tax-law.html), [DLA Piper](https://www.dlapiper.com/en/insights/publications/gulf-tax-insights/2024/gulf-tax-insights-february-2024/taxation-of-software-payments-in-saudi-arabia)):

- **§3.3.11** — a non-exclusive, non-transferable licence to use standardised *or customised* software → **commercial profits, no WHT without a PE**. But add *"the right to modify certain features"* → **royalty, 15%**.
- **§3.3.5** — where the customer gets the right to **reproduce or install copies on its own infrastructure** (site / enterprise / network licence) → **royalty, 15%**, and ZATCA states explicitly that lump-sum versus periodic payment is irrelevant.
- **§3.3.9 mixed contracts** — a licence bundled with non-ancillary support, updates or training must be split and taxed element-by-element. **A single all-in USD 590 line invites ZATCA to apply the higher rate to the whole thing.**
- DLA Piper notes the guideline **never defines "standardized"**, leaving boundary cases genuinely uncertain.

> **Pessimistic read: an on-premise perpetual vet-clinic ERP almost certainly lands in §3.3.5 → 15%.** Any per-seat installation right or configuration right takes you there. Itemise licence, setup and support as separate lines on every Saudi invoice — that is free, and it is the only lever you have.
>
> **§3.3.6 classifies reseller/distributor arrangements as commercial profits**, which is the cleanest structural fix for Saudi Arabia if the market ever justifies one.

#### The commercial consequence — price for it

**Assume ~11% is lost in Jordan, 10% in Morocco, 15% in Saudi Arabia, and that no treaty claim will recover any of it.**

| Market | Withheld | Gross price needed for a net USD 590 |
|---|---|---|
| Egypt (domestic) | — | USD 590 |
| **UAE** | 0% | **USD 590** |
| Morocco | 10% | **USD 656** (+11.1%) |
| Jordan | ~11% | **USD 663** (+12.4%) |
| Saudi Arabia (realistic) | 15% | **USD 694** (+17.6%) |

**Gross up the foreign price by ~11% and say so in the contract.** A "net of all withholding taxes" clause is standard and shifts the deduction onto the buyer; without it, the deduction silently comes out of Ahmed's margin on every deal.

> **The characterisation risk, and why it is not worth fighting.** Whether a perpetual software licence is a **royalty** (WHT applies) or **business profits** (no WHT without a permanent establishment) is genuinely arguable, and in some jurisdictions a shrink-wrapped copy sold without transfer of copyright is business profits. **Do not build a plan on winning that argument.** A Moroccan or Jordanian clinic's accountant will deduct at source by default, and Ahmed has no leverage and no local counsel to contest it. Price at the pessimistic rate; treat any recovery as upside.

> **A merchant of record removes this problem entirely.** If Paddle is the legal seller, the Jordanian clinic is buying from Paddle — a UK/US entity with its own treaty network — not from an Egyptian vendor. The withholding question, the tax-residency certificate, and the gross-up all disappear. **This is the second-biggest argument for the MoR route after the collection mechanics themselves, and it is worth more than the 5% MoR fee.**

### T4.2 Egyptian VAT — 14% at home, 0% on exports if you keep the paperwork

**Domestic sales: 14%.** Egypt's standard VAT rate is 14% ([PwC Egypt — Other taxes](https://taxsummaries.pwc.com/egypt/corporate/other-taxes)), and software, software maintenance and consultancy are enumerated taxable services at that rate ([Andersen Egypt](https://eg.andersen.com/tax-digital-services-in-egypt/), [Anrok — Egypt](https://www.anrok.com/vat-software-digital-services/egypt)).

#### The registration rule that decides everything — Art. 16

**The threshold is EGP 500,000**, per ETA's own site ([ETA](https://eta.gov.eg/ar/news/altsjyl-aldryby-lmn-lm-tblgh-mbyathm-hd-altsjyl-la-yntj-nh-thsyl-drybt-qymt-mdaft-aw-alaltzam)). Art. 16 of Law 67/2016 requires registration within 30 days of sales reaching that figure over the preceding 12 months.

> **But Art. 16 also makes registration compulsory *regardless of turnover* for every importer for trading, every distribution agent, and — decisively — every exporter** ([law text](https://consortiolawfirm.com/egypt-vat-law-67-2016-english-translation/), [analysis](https://consortiolawfirm.com/vat-registration-egypt/)).
>
> **This is the single most important tax finding in this document. The moment Ahmed invoices one clinic in Amman, he is an exporter and must register for VAT from day one — even at EGP 200,000 of total turnover.** Once registered he must charge 14% on every *domestic* sale, file returns, and issue e-invoices. **There is no "stay small and invisible" option once you export.**

Late registration is worse than useless: the law deems you retroactively registered from the threshold date and charges the uncollected VAT plus penalties ([Consortio](https://consortiolawfirm.com/vat-registration-egypt/)).

`[CORRECTED]` The widely-repeated claim that Resolution 281/2025 cut the threshold to **EGP 250,000** from 1 January 2026 appears to be **an error propagating between vendor blogs**. ETA's own page for that resolution describes it as *e-receipt system, phase 8 sub-phase 2*, effective 15 September 2025, with no mention of a threshold ([ETA](https://www.eta.gov.eg/ar/news/sdwr-qrar-rqm-281-lsnt-2025-alkhas-balmrhlt-alfryt-althanyt-mn-almrhlt-alryysyt-althamnt)); Law 157/2025 amended construction, advertising and crude-oil excise but left software and the threshold untouched ([EY](https://www.ey.com/en_gl/technical/tax-alerts/egypt-introduces-significant-vat-updates-on-certain-goods-and-services), [KPMG](https://kpmg.com/us/en/taxnewsflash/news/2025/08/tnf-egypt-vat-amendments-to-certain-goods.html)). **Moot either way — the exporter rule catches you first.**

#### Exports of services: zero-rated, conditionally

Art. 3 of the VAT Law: *"The rate of Tax on goods and services exported outside the country shall be zero (0%)"* ([law text](https://consortiolawfirm.com/egypt-vat-law-67-2016-english-translation/)).

The operative rulebook is now **ETA Executive Instructions No. 45 of 2025, issued 27 November 2025**, with a bilingual guidance manual ([ETA announcement](https://www.eta.gov.eg/ar/news/asdar-altlymat-altnfydhyt-rqm-45-lsnt-2025-bshan-alyt-taml-almklwafyn-m-alkhdmat-almsdwart), [Matouk Bassiouny](https://matoukbassiouny.com/egypt-releases-new-vat-guidance-on-exported-services/), [Daily News Egypt](https://www.dailynewsegypt.com/2025/11/27/egypt-tax-authority-standardises-vat-treatment-for-exported-services-issues-guidance/)). A service supplied **from inside Egypt to a recipient located outside Egypt** is zero-rated with **full input VAT recovery and refund eligibility**.

Three mandatory documents ([PwC Egypt](https://taxsummaries.pwc.com/egypt/corporate/other-taxes), [Grant Thornton Egypt](https://www.grantthornton.eg/insights/vat-export-service-challenges/)):

1. **A written contract** naming the parties, service nature, payment terms and duration (the older Executive Regulations required it *authenticated*)
2. **An ETA-compliant export e-invoice** (see T4.3)
3. **Proof of payment** — bank transfer records or statements **from a bank supervised by the Central Bank of Egypt**

**This is the sharpest practical rule in the document.** Selling a licence to an Amman clinic remotely is zero-rated — but only if all three exist. Three traps:

> **ETA has form here.** In September 2019 it reclassified whole service categories as *local* rather than exported ([Grant Thornton](https://www.grantthornton.eg/insights/vat-export-service-challenges/)). **"Foreign currency received through a bank" is the condition that actually gets audited.** If a Jordanian clinic pays in cash or via a personal wallet, the sale is not an export and you owe 14%.

- **On-site installation kills it.** Services *"requiring physical presence of both supplier and recipient"* are excluded and treated as local taxable supplies. If Ahmed flies to Amman to install and configure, that portion is arguably a **local taxable service at 14%, not a zero-rated export.** Structure the contract so the licence and remote support are separated from any on-site work, and price on-site work separately.
- **Proof of payment means a traceable bank record.** Cash or an informal wallet transfer for a foreign sale will not satisfy condition 3. This is a second, independent reason to route foreign money through a bank, Payoneer or an MoR.

`[UNVERIFIED]` — how ETA treats an **MoR sale** for zero-rating purposes (where the customer of record is Paddle in the UK, not the clinic in Amman) was not established. In principle it is still an export of services to a non-resident and should qualify, with the Paddle payout statement serving as proof of payment. **Confirm with an Egyptian tax accountant before filing the first return** — this is the one open question that could cost 14% on all foreign revenue.

### T4.3 ETA e-invoicing — mandatory, real-time, and non-negotiable

- **Mandatory for B2B since April 2023.** Paper invoices ceased to be valid for VAT purposes on **1 July 2023** ([VATupdate](https://www.vatupdate.com/2026/02/23/briefing-document-podcast-e-invoicing-e-reporting-in-egypt/), [Avalara — Egyptian e-invoicing](https://www.avalara.com/us/en/vatlive/country-guides/africa-and-middle-east/egypt-vat/egyptian-e-invoicing.html)).
- **Format:** JSON/XML, carrying a UUID, **electronically signed**, submitted to ETA in **real time**.
- **Penalties, tiered from January 2026:** 1st offence warning; 2nd within 12 months **EGP 5,000 per late document**, capped at 50,000/month; 3rd and beyond **EGP 10,000 per invoice, uncapped**, plus possible suspension of invoicing rights. General violations EGP 20,000–100,000. Records retained **5 years** ([VATupdate](https://www.vatupdate.com/2026/02/23/briefing-document-podcast-e-invoicing-e-reporting-in-egypt/), [Fonoa — Egypt](https://www.fonoa.com/resources/country-tax-guides/egypt)).

#### Export invoices have their own document type — and it is fiddly

ETA publishes a dedicated **Export Invoice** type ([ETA SDK — export invoice v1.0](https://sdk.invoicing.eta.gov.eg/documents/export-invoice-v1-0/)):

- Receiver **type = "F"** (foreigner), receiver **ID** = the foreign company's identification/VAT number, **country code** ISO-3166-2, anything other than "EG"
- **Exchange rate is mandatory** when the sale currency is not EGP (max 5 decimals); amounts convert to EGP at the **Central Bank rate on the issuance date**
- `dateTimeIssued` in UTC, a valid `taxpayerActivityCode`, at least one invoice line
- **Issuer digital signature mandatory** (CAdES-BES / SHA-256)

**This export e-invoice is also condition #2 of the Instruction 45/2025 evidence pack. No valid export e-invoice, no 0% VAT** — get the receiver ID and country code right on the very first Amman invoice.

#### Cost for a two-person shop — small and knowable

ETA's **free** portal at `invoicing.eta.gov.eg` handles manual entry and is practical to roughly 200 invoices/month ([DataValue](https://datavalue.solutions/egypt-e-invoicing-eta-2026-sme-guide/)). At ~100 licences/year you never need ERP integration. The only unavoidable spend is the **electronic seal / USB token** ([eDariba](https://edariba.com/en/electronic-seal-price-2025-required-documents-egypt/)):

| Provider | 1 yr | 2 yr | 3 yr |
|---|---|---|---|
| Tawtheeq (Pioneers) | EGP 840 | 1,350 | 1,800 |
| Egypt Trust | 950 | 1,800 | 2,600 |
| MCDR | 1,800 | 2,700 | 3,600 |
| Orange | 2,000 | 3,000 | — |

For a منشأة فردية: tax card, owner's ID, company stamp, an official email registered in the commercial register, and a booked appointment; issuance in 24–48 hours. **Call it EGP 1,800 every three years** — noise against EGP 30,000 per licence. An HSM (EGP 8,000–12,000) is only for 500+ invoices/month and is not needed.

#### E-receipt (الإيصال الإلكتروني) — register anyway

A separate **B2C** system rolled out in named waves — Resolution 405/2024 (wave 6, from 15 Jan 2025) and Resolution 281/2025 (phase 8 sub-phase 2, from 15 Sep 2025) ([ETA](https://www.eta.gov.eg/ar/news/sdwr-qrar-rqm-281-lsnt-2025-alkhas-balmrhlt-alfryt-althanyt-mn-almrhlt-alryysyt-althamnt), [KPMG](https://kpmg.com/us/en/taxnewsflash/news/2025/01/tnf-egypt-taxpayers-required-comply-mandate-electronic-receipts-b2c-transactions.html)). The obligation attaches only if your name appears on a phase decree's annexed list; receipts must reach ETA within 72 hours. Selling B2B to clinics, e-**invoices** cover you — **but Law 6/2025 makes registration on *both* systems a condition of the simplified tax regime (T4.4), so register on both regardless.**

#### The commercial angle, which matters more than the compliance one

Per **Decree No. 188 of 2023**, from 1 July 2023 no document other than an e-invoice counts as evidence of a deductible cost or expense ([KPMG Egypt](https://kpmg.com/eg/en/home/insights/2023/04/decree-no-188-2023.html)). **Your customers need your e-invoice to deduct the EGP 30,000.** Being able to issue one is a precondition for selling to any serious clinic — a sales feature, not just a tax obligation.

### T4.4 Income tax on the business

A **منشأة فردية** is taxed on the owner's personal income tax brackets, not the 22.5% corporate rate. Current brackets ([PwC Egypt — personal income tax](https://taxsummaries.pwc.com/egypt/individual/taxes-on-personal-income)):

| Income (EGP) | Rate |
|---|---|
| 1 – 40,000 | 0% |
| 40,000 – 55,000 | 10% |
| 55,000 – 70,000 | 15% |
| 70,000 – 200,000 | 20% |
| 200,000 – 400,000 | 22.5% |
| 400,000 – 1,200,000 | 25% |
| Over 1,200,000 | 27.5% |

Plus an annual exemption of EGP 20,000 (so roughly EGP 60,000 effectively tax-free). An LLC pays a flat **22.5%** ([PwC Egypt — corporate income](https://taxsummaries.pwc.com/egypt/corporate/taxes-on-corporate-income)). Outside the regime below, a sole establishment wins below roughly EGP 400k of profit and loses above ~EGP 1.2m (27.5% > 22.5%).

#### But none of that matters, because of Law 6 of 2025

**Law 152/2020's SME regime has been superseded by Law No. 6 of 2025, effective 1 March 2025**, for turnover up to **EGP 20 million** ([Ministry of Finance](https://mof.gov.eg/en/posts/regulations/67bde91a9a68f40008ae1af8/), [EY](https://www.ey.com/en_gl/technical/tax-alerts/egypt-introduces-tax-incentives-and-benefits-for-small-enterprises)). Art. 10 taxes **turnover, not profit**:

| Annual turnover (EGP) | Tax |
|---|---|
| under 500,000 | **0.4%** |
| 500,000 – under 2m | **0.5%** |
| 2m – under 3m | **0.75%** |
| 3m – under 10m | **1%** |
| 10m – 20m | **1.5%** |

A two-person software shop qualifies — Art. 1 covers natural and juridical persons including professional activities, registered or not. Other provisions ([law text](https://alliedforlegalandtaxadvice.com/%D9%86%D8%B5-%D9%82%D8%A7%D9%86%D9%88%D9%86-%D8%B1%D9%82%D9%85-6-%D9%84%D8%B3%D9%86%D8%A9-2025/), [mnasserlaw](https://mnasserlaw.com/taxation-law-no-6-of-2025/)):

- **Art. 7** — exempt from the state resource development fee, **stamp tax**, and capital gains tax on fixed-asset disposals
- **Art. 9** — dividend distributions exempt
- **Art. 11** — **not subject to the advance-payment system nor to withholding-under-account-of-tax.** This kills the domestic 1%/3%/5% WHT that Egyptian clinic customers would otherwise deduct
- **Art. 12** — **VAT returns quarterly instead of monthly**; e-invoice and e-receipt compliance mandatory
- **Art. 3** — **five-year lock-in, cannot withdraw**
- VAT and payroll audits deferred five years
- Entry is **by application to ETA**, not automatic

**The arithmetic is decisive.** At EGP 2m turnover the tax is **EGP 10,000** (0.5%). Under the normal regime, the same business at a 50% margin pays personal income tax on EGP 1m — roughly **EGP 220,000+**. Law 6/2025 turns income tax into a rounding error. **Apply.**

> ⚠️ **Art. 4 exclusions — watch this one.** Professional and consulting outfits deriving **90% or more of revenue from one or two clients** are excluded, as are artificially fragmented businesses. **A two-person shop with a handful of clinic customers could plausibly be argued into the 90% test in a lean year** — and the regime has a five-year lock-in. Raise it explicitly with the accountant.

**Law 6/2025 does not exempt you from VAT.** You still register as an exporter, still charge 14% domestically, still zero-rate exports — just quarterly.

**Consequence for incorporation:** if you elect Law 6/2025, the sole-establishment-versus-LLC comparison largely dissolves, since both are taxed at 0.4–1.5% of turnover. The reasons to incorporate later remain **ITIDA export incentives** (T2.5) and **credibility with Gulf buyers**, not tax.

> **The one open question worth paying for an opinion on.** `[UNVERIFIED]` — whether a **foreign tax credit** for the 10–15% withheld in Jordan, Morocco and Saudi Arabia is available at all when you are taxed on *turnover* under Law 6/2025 rather than on profit. **If it is not creditable, that 10–15% is a pure, permanent loss** rather than a timing difference. Collect a withholding certificate from every foreign buyer regardless — without it there is no claim to make even if one exists.

### T4.5 The buyer's VAT status is a hard qualification rule

This is the trap most likely to turn a USD 590 sale into a five-figure problem, and it is identical in shape in three countries.

When the foreign buyer **is** VAT-registered, reverse charge applies, the buyer self-assesses, and Ahmed has no obligation. When the buyer is **not** registered, the reverse charge cannot operate — and the **non-resident supplier** picks up a registration obligation **with no threshold**:

| Country | Buyer VAT-registered | Buyer NOT registered |
|---|---|---|
| **Saudi Arabia** | 15% reverse charge, nothing for you | **You must register for Saudi VAT within 30 days of the first supply, no threshold** ([Grant Thornton](https://www.grantthornton.global/en/insights/indirect-tax-guide/indirect-tax---Saudi-Arabia/)) |
| **UAE** | 5% reverse charge, nothing for you | **You must register on the first dirham** — the FTA states plainly: *"The mandatory registration threshold is AED 375,000. This threshold is not applicable to foreign businesses"* ([FTA](https://tax.gov.ae/en/taxes/vat/vat.topics/registration.for.vat.aspx)) |
| **Morocco** | 20% self-assessed and deducted simultaneously, no cost | **CGI art. 117-III makes the client withhold 20% VAT at source on top of the 10% income WHT** |
| **Jordan** | 16% reverse charge | **GST Law Art. 13(b): the importer must register within 30 days of the first import, regardless of value** ([BDO Jordan VAT Navigator](https://www.bdo.com.jo/getattachment/827089db-2161-4aec-a718-03e0ce5307bb/VAT_Jordan_2024_Final3.pdf?lang=en-GB)) |

Legal basis for the UAE position: Art. 48(1) of Federal Decree-Law 8/2017 applies reverse charge only where the importer is a **Taxable Person**, and Art. 13(2) requires a non-resident to register *"where no other Person is obligated to pay the Due Tax"* ([FTA text](https://tax.gov.ae/DataFolder/Files/Legislation/Federal%20Decree-Law%20No.%208%20of%202017%20and%20amendments%20-%20For%20Publishing.pdf)). A software licence delivered electronically is an "electronic service" — Cabinet Decision 52/2017 art. 23 expressly lists *"supply and updating of software"* ([JCA](https://jcauaeaudit.com/uae-vat-on-electronic-services/)).

> **The rule, stated as a rule: do not sell direct to a clinic in Saudi Arabia or the UAE that is not VAT-registered.** Verify the buyer's VAT/TRN number, put it on the invoice, and treat "no VAT number" as a disqualifier. **A USD 590 sale is not worth a ZATCA or FTA registration.**
>
> **A merchant of record removes this too.** If Paddle is the seller, Paddle carries the VAT registration in every jurisdiction. This is the third independent reason the MoR route is worth more than its 5% fee.

`[UNVERIFIED]` — whether Moroccan veterinary clinics fall inside or outside Moroccan VAT scope (decides whether art. 117-III bites); whether Jordanian veterinary clinical services are GST-**exempt** (16% sticks) or **zero-rated** (credit available); whether ISTD actually enforces Art. 13(b) against a one-off sub-threshold import. **Check per customer.**

## T5 — The recommendation

> *"Ahmed has EGP 5,000 and one week. What does he set up, in what order, to collect EGP 30,000 from a Cairo clinic next month and EGP 30,000 from an Amman clinic six months later?"*

### The answer in one paragraph

**Register a منشأة فردية, open a business current account, collect the Cairo clinic by InstaPay for EGP 20 of the clinic's money, and — in the same week, because it is free and takes an hour — open Paddle and Polar accounts so the Amman deal six months out has a proven rail rather than a hope.** The domestic problem is already solved and costs nothing. The cross-border problem is solved by a merchant of record, which also erases the ~11% Jordanian withholding **and** the foreign VAT registration trap. The thing that will actually cost real money is **VAT registration and ETA e-invoicing**, and that is where the EGP 5,000 should go — because **the first foreign invoice forces VAT registration at any turnover** (T4.2).

### The EGP 5,000

| Item | EGP | Note |
|---|---|---|
| Commercial register + tax card + chamber (DIY) | 350–600 | T1.1 |
| Accountant: registration, VAT, ETA, Law 6/2025 application | 2,000–5,000 | The real cost; do not DIY the tax side |
| E-signature token (Tawtheeq, 1 yr) | 840 | Unavoidable for e-invoicing (T4.3) |
| Business current account + USD account | 0 | Some banks require a minimum balance |
| Paddle account | 0 | Free until you transact |
| Polar account | 0 | Free Starter plan |
| **Total** | **~3,200–6,400** | Tight; the accountant is the variable |

**The budget is adequate for the Cairo deal and for opening the cross-border rails. It is not adequate for a شركة, a UAE entity, or a tax adviser in Amman — and none of those are needed yet.** If money is short, take the 3-year token (EGP 1,800) later and the 1-year now; do not economise on the accountant.

---

## The one-week setup plan

Each step lists a **fallback**, because the primary option can be refused.

### Day 1 — Check the two things that can stop everything

Before spending anything, verify two facts that invalidate the plan if wrong:

1. **Is either founder a government employee or a privately-insured salaried employee?** If so, that person **cannot hold a commercial register** (T1.1). The register must go in the other founder's name.
2. **Is there premises with a certified lease and a *commercial* electricity meter?** A residential meter blocks the register.

> **Fallback:** if neither founder is eligible or there are no qualifying premises, use a **licensed co-working / business incubator address** that issues a commercial lease. `[UNVERIFIED — cost not researched.]` Do not proceed to Day 2 until this is resolved; everything downstream depends on the register.

### Day 1 (parallel, 1 hour, free) — Open Paddle and Polar

Do this on day one, not month five. **The whole point is to discover a refusal now rather than after the Amman clinic has signed a contract.**

- **Paddle** ([signup](https://www.paddle.com/)) — Egypt is not on the 28-country exclusion list, and business verification is **"not required for individuals or sole traders"**, so an individual can apply before the register exists. Requires a real domain with a product description, Terms of Service and Privacy Policy. Set payout method to **Payoneer**.
- **Polar** ([signup](https://polar.sh/)) — free Starter plan, Egypt explicitly listed. **Complete the Stripe Connect Express onboarding all the way through**, because that is the step that would fail, and it is the whole reason to test it now.

> **Fallback ladder if Paddle refuses:** Polar → Dodo Payments / Creem (unconfirmed for Egyptian sellers, ask before building) → direct SWIFT invoicing with a foreign-currency account (T2.3), accepting a 5–10% haircut and full withholding exposure.

### Day 2 — Payoneer

Open a **Payoneer** account. It is the payout leg for Paddle, works in Egypt, and is the least-bad general-purpose route for foreign money.

Know the costs going in: roughly **5.7% all-in** on a USD 1,000 withdrawal, and **withdrawals to an Egyptian bank convert to EGP automatically** — the currency field defaults to EGP and cannot be changed (T2.2).

> **Fallback:** Paddle also pays by **wire transfer** to any bank giving IBAN/SWIFT details. If Payoneer's verification stalls, switch the Paddle payout method to wire into a foreign-currency account (Day 4) and accept a possible **USD 15 SWIFT fee**.

### Days 2–5 — Register the منشأة فردية

Engage an accountant. Route A, ordinary commercial registry, **not** GAFI (which needs EGP 100,000 capital). Sequence: tax file → chamber certificate → commercial register (2–7 business days).

**Realistically this will not finish inside one week** — the tax file alone takes about two weeks. That is fine, because it does not block the Cairo deal (see Day 6).

> **Fallback:** if the register is delayed past the Cairo clinic's payment date, take the payment into a personal account **and issue a proper invoice the moment the register and ETA registration exist**. This is a deliberate, time-boxed corner-cut, not a plan — undeclared business income into a personal account is exactly the audit trail you do not want, and it also fails the "proof of payment" test for anything later.

### Day 4 — Two bank accounts, not one

At the same bank, open:

1. **An EGP business current account** in the establishment's name → InstaPay receipts, domestic revenue.
2. **A USD (foreign-currency) account** → so inbound wires are **not auto-converted at the bank's rate** (T2.3). This account costs nothing to hold and is the difference between keeping dollars and having them converted on arrival.

Ask two questions and write down the answers: the **inbound-wire fee**, and the **USD→EGP conversion spread** (expect 1–3% below mid-market, undisclosed).

> **Fallback:** if the business account is blocked pending the register, open the USD account personally now and add the business account later. NBE offers free digital-channel transfers; CIB and Banque Misr are the usual choices for FX accounts.

### Day 5 — VAT and ETA e-invoicing

**This is the step that costs the most and the step most likely to be skipped. Do not skip it.**

- The threshold is **EGP 500,000** — but **Art. 16 of Law 67/2016 forces registration at any turnover the moment you export**. Ahmed will be registered from the first Amman invoice regardless (T4.2).
- B2B e-invoicing is mandatory, real-time, JSON/XML, electronically signed. Penalties escalate to **EGP 10,000 per invoice, uncapped**.
- **Decide today whether EGP 30,000 is VAT-inclusive or plus-VAT, and put it in the contract template.** Getting this wrong on the first ten deals is a five-figure error.

**Buy the e-signature token** — EGP 840–2,000/year depending on provider, cheapest at Tawtheeq; issuance 24–48 hours (T4.3). Use ETA's free portal. **Do not build an integration** for a hundred invoices a year.

**Register on the e-receipt system too**, even though you sell B2B — it is a condition of Law 6/2025.

**Apply for the Law 6/2025 simplified regime.** This is the highest-return hour in the whole week: **0.4–0.5% of turnover** instead of 22.5–27.5% of profit, no domestic withholding deducted by clinic customers, quarterly rather than monthly VAT returns, and a five-year audit deferral (T4.4). Two cautions: **five-year lock-in**, and the **Art. 4 exclusion for businesses drawing 90%+ of revenue from one or two clients** — raise that with the accountant explicitly before applying.

> **Fallback:** if the token or ETA registration is delayed, the accountant can issue through their own credentials as an interim measure. `[UNVERIFIED — confirm this is permitted; do not assume it.]`

### Day 6 — Collect the Cairo clinic

**Send an ETA e-invoice and the business account's InstaPay details. Done.**

- Cost to Ahmed: **EGP 0**
- Cost to the clinic: **EGP 20** (EGP 45 at Bank of Alexandria)
- Settlement: **instant, 24/7**
- Limits: EGP 30,000 is 43% of the EGP 70,000 per-transaction cap — and the **EGP 60,000 tier also clears in one transfer**

> **Fallback ladder:** plain bank transfer (same EGP 20, or free on NBE digital) → Vodafone Cash **only** as a bridge to fund an InstaPay transfer, never as settlement (1% cash-out = EGP 300) → cash, legal but with no proof of payment and the same invoice obligation → **Paymob only if the clinic insists on a card**, in which case **add the EGP 828–944 to that quote explicitly rather than absorbing it.**
>
> **Do not open a Fawry account.** EGP 999 setup + EGP 499/month = **EGP 5,988/year** in fixed cost — more than your entire setup budget — for a handful of transactions.

### Day 7 — Write the export contract template

Six months of lead time on the Amman deal is worth exactly one hour now. The template must contain:

1. **A "net of all withholding taxes" clause.** Jordan deducts **~11%** (10% + 1% national contribution) and the Egypt–Jordan treaty is useless — its 20% royalty cap sits above Jordan's own domestic rate, so it can never apply. Without this clause the 11% comes out of Ahmed's margin. **Gross the foreign price up: +12% Jordan, +11% Morocco, +18% Saudi Arabia, +0% UAE** (T4.1).
2. **A clause requiring the buyer to supply a withholding tax certificate.** Without it there is no foreign tax credit claim to make — and it may not be claimable at all under Law 6/2025's turnover basis (T4.4). Collect it anyway; it costs nothing.
3. **The three documents Instruction No. 45 of 2025 requires for VAT zero-rating** (T4.2): a signed contract stating parties, service description, payment terms and duration; the ETA **export** e-invoice with receiver type "F", the buyer's ID, ISO country code and the CBE exchange rate; and **proof of payment through a CBE-supervised bank**. Missing any one costs **14%**.
4. **On-site work priced and invoiced separately** from the licence. Services requiring physical presence are **excluded from zero-rating** — flying to Amman to install can taint the export treatment of the whole invoice.
5. **Licence, setup and support as separate line items.** Free to do, and it is the only lever against ZATCA's §3.3.9 rule that a bundled contract can be taxed wholesale at the higher rate (T4.1).
6. **A buyer VAT-number field, and a rule that "no VAT number" disqualifies a Saudi or UAE clinic** (T4.5).

### Month 6 — Collect the Amman clinic

**Route 1 (preferred): sell through Paddle.** The clinic buys from Paddle, not from Ahmed. Consequences, all good:
- **No Jordanian withholding** — Paddle is the seller, so the ~11% question never arises
- **No Jordanian GST Art. 13(b) registration trap**, no foreign VAT registration, no tax-residency certificate, no local counsel
- Clinic pays by card, or by **wire against a Paddle invoice** (available above USD 100; a USD 590 licence qualifies, 7–14 day terms, USD/EUR/GBP)
- Cost **~5% headline, ~7% effective** — materially cheaper than the ~11% withholding it replaces, before counting the compliance it removes
- Payout: Payoneer or wire, USD 100 minimum, monthly by the 15th

**Route 2 (fallback): Polar**, if Paddle refused. Same structure, ~5% + 1.5% international-card surcharge on the free plan.

**Route 3 (last resort): direct invoice and SWIFT** into the USD account. Costs USD 20–50 in correspondent fees plus a 1–3% spread, **plus ~11% Jordanian withholding**, plus the Art. 13(b) GST registration exposure, plus the burden of proving the export to ETA. Roughly **16% all-in versus 7%.** Only if both MoRs refuse.

---

### Four things that would change this plan

1. **Paddle and Polar both refuse.** Cross-border collection drops to direct SWIFT at ~16% all-in with full withholding exposure and the Jordanian GST registration trap live. Jordan and Morocco stay viable but get materially less attractive. **This is why Day 1 opens both accounts.**
2. **ETA does not accept MoR sales as zero-rated exports.** Adds 14% to all foreign revenue (T4.2, `[UNVERIFIED]`). Confirm before the first return.
3. **Foreign withholding turns out not to be creditable under Law 6/2025.** Because that regime taxes *turnover*, not profit, the 10–15% withheld abroad may be a **permanent loss rather than a timing difference** (T4.4, `[UNVERIFIED]`). **This is the single open question most worth paying for an opinion on** — it decides whether foreign sales are 11% less profitable or 11% less profitable *forever*.
4. **Volume grows past a few dozen licences.** Then incorporate — for **ITIDA export incentives** (10–35% cash rebate on value-added exports for micro/small ICT companies, ceiling EGP 2.5m, no minimum export size — T2.5) and for credibility with Gulf buyers. **Not for tax:** under Law 6/2025 both a منشأة فردية and an LLC pay 0.4–1.5% of turnover, so the entity choice is commercially, not fiscally, driven.

### The five things to get wrong-proof

If everything else in this document is forgotten, these five survive:

1. **InstaPay into a business account.** EGP 20, paid by the clinic, instant. Nothing beats it domestically.
2. **Open Paddle and Polar in week one, not month five.** Both are free. Discovering a refusal after a clinic has signed is the worst outcome in this document.
3. **The first foreign invoice forces Egyptian VAT registration at any turnover.** Budget for it before, not after.
4. **Gross up foreign prices by 11–18% and put a "net of withholding" clause in the contract.** No treaty will save you in Jordan or Morocco.
5. **Never sell direct to a Saudi or UAE clinic without a VAT number.** No number, no deal — or sell through the MoR.
