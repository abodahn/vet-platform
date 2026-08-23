# The 15-Minute Demo

A clinic owner will give you fifteen minutes and will decide in the first three.
This is the order to show things in, and — more importantly — what to leave out.

**The rule that matters:** you are not demonstrating software. You are showing a
vet that their own clinic, with their own patients in it, works better. Every
minute spent on a feature they did not ask about is a minute spent losing them.

---

## Before you walk in

Do not skip any of these. Each one has ended a demo.

| ✔ | Check |
|---|---|
| ☐ | **Their data is already loaded.** Ask for their Excel two days early. This is the whole trick — see below. |
| ☐ | **WhatsApp is connected and you have sent a real message today.** It has never been sent end to end. If it fails live, you lose the meeting. |
| ☐ | Clinic name, logo and phone set in Settings — **their** clinic, not "Aleefy" |
| ☐ | Prices in the catalogue look like Egyptian prices, not 100 / 200 / 300 |
| ☐ | Logged in already, on the right screen, browser full screen |
| ☐ | Phone charged and hotspot ready — never trust clinic wifi |
| ☐ | An invoice printed once today, so you know the printer path works |
| ☐ | Language set to Arabic |

**Most of that is machine-checkable, so check it by machine:**

```bash
python scripts/demo_check.py --tenant demo
```

It verifies the clinic's own name and logo, today's appointment board, whether
the database looks like a working clinic or a test fixture, whether prices read
as placeholders, WhatsApp, published passwords, the CDS warning, that the
invoice PDF actually renders, and the default language. It changes nothing, so
it is safe to run five minutes before a meeting.

It cannot check the four that matter most, and those stay yours: their data
loaded, one real WhatsApp message sent to your own phone, an invoice printed on
paper, and a charged phone with a hotspot.

### The trick that wins the meeting

**Load their real data before the demo.** When a vet sees their own patients'
names on the screen — Bella, Simba, the client who never pays — it stops being
software and becomes their clinic. Everything after that is detail.

Ask two days early:

> "عشان أوريك النظام وهو شغّال ببيانات عيادتك مش ببيانات وهمية،
> ابعتلي ملف الإكسل أو حتى كشف العملاء بأي شكل — وأنا أجهّزه قبل ما نتقابل."

If they have nothing digital, ask for **photos of one page of the appointment
book** and type twenty names in yourself. It is worth the hour.

---

## The 15 minutes

### 0:00 — 1:00 · Do not open the laptop yet

Ask, and listen:

> "قبل ما أوريك حاجة — إيه أكتر حاجة بتضيّع وقتك في العيادة دلوقتي؟"

Whatever they answer is what you demo. If they say stock, lead with stock. If
they say "الحسابات في آخر الشهر", lead with the daily close. The script below is
the default order for when they have no strong answer.

Write their answer down in front of them. It signals you are building for them,
not selling at them.

### 1:00 — 3:00 · Their own clinic, on screen

Open the dashboard. Say almost nothing. Let them notice the names.

> "دي بيانات عيادتك اللي بعتهالي. ٬دي كل العملاء والحيوانات."

Then search for a pet they know and open the file: history, vaccinations,
previous visits, invoices, all on one screen.

> "كل تاريخ الحالة في شاشة واحدة. مش هتفتح ٣ دفاتر."

**This is the moment the sale happens.** Do not rush it.

### 3:00 — 6:00 · The exam — طريقة حاتم

Open the one-screen exam. Show a whole visit without changing page: vitals,
symptoms, diagnosis, services, medicines, and the invoice at the end.

> "الكشف كله في شاشة واحدة — من غير ما تخرج ولا مرة.
> لما تحفظ، الفاتورة بتتعمل لوحدها والدوا بينزل من المخزن لوحده."

Then say the name:

> "الشاشة دي اتعملت بالظبط على كلام دكتور بيطري شغّال، وسميناها باسمه."

### 6:00 — 8:00 · Print the invoice

Print it. Actually print it, on paper, and hand it to them.

> "دي الفاتورة بالعربي، باسم عيادتك وشعارك."

**Why this matters more than it looks:** Arabic inside a generated PDF is where
almost every competing system breaks — the letters separate or come out
reversed. Most vets have been burned by this and will not expect it to work.
Handing them correct printed Arabic with their own clinic name on it does more
than ten minutes of talking.

### 8:00 — 10:00 · WhatsApp — the money feature

Book an appointment for tomorrow, then send the reminder **to their own phone,
in the room.** Let their phone buzz on the table.

> "كل عميل بيوصله التذكير ده قبل معاده. الحالات اللي كانت بتنسى وما بتجيش — بترجع."

Then bring it back to money:

> "لو رجّعلك ٥ حالات بس في الشهر بـ ٣٠٠ جنيه، يبقى ١٬٥٠٠ جنيه.
> النظام بيدفع تمن نفسه في أقل من ٥ شهور."

⚠️ **Do not attempt this until you have sent a real WhatsApp message yourself.**
As of today `wapilot settings rows: 0` — no message has ever gone end to end.

### 10:00 — 12:00 · The owner's screen

Now sell to the businessman, not the doctor. Open the dashboard and the daily
close.

> "في آخر اليوم، ده اللي دخل، وده اللي اتصرف، وده اللي في الدرج.
> ومن غير ما تسأل حد."

Show one more thing that only matters to an owner — pick **one**:
- **Stock about to expire** (money about to be thrown away)
- **Who came in late this month** (attendance)
- **Which service makes the most money** (reports)

### 12:00 — 14:00 · Their question, answered live

Go back to what they said at minute one and show exactly that.

If they ask for something the system does not do, **do not invent it**:

> "دي مش موجودة دلوقتي. أقدر أعملها، وهقولك بالظبط هتاخد كام ساعة."

An honest no makes every yes believable. A vet who catches you exaggerating once
will not buy anything.

### 14:00 — 15:00 · Close with the trial, not the price

Do not push for a signature. Push for the next step:

> "خلّي النظام عندك ببيانات عيادتك، جرّبه أسبوع.
> لو مظبطش، مش هتخسر حاجة. لو ظبط، نتكلم في التفاصيل."

Then hand over the one-page price sheet **on the way out**, not before. Price
discussed after they have already imagined using it is a different conversation
entirely.

---

## Never demo these

| Module | Why not |
|---|---|
| **دعم القرار السريري (CDS)** | Ships marked `DRAFT — NOT REVIEWED BY A LICENSED VETERINARIAN`. Four of its six drug classes are referenced by no rule, so real combinations produce no warning. A vet who trusts it and is not warned is a liability you cannot afford. **Leave it out entirely.** |
| **المساعد الذكي (AI)** | Needs a paid API key configured. It will look broken. |
| **الطب عن بُعد** | Impressive in theory, nobody buys because of it, and it takes time you do not have. |
| Anything you have not personally opened this week | It may have changed. |

---

## The five objections, and the answers

**"عندي بياناتي في إكسل من ٦ سنين، مش هعيد إدخالهم."**
> "متعيدش. ابعتهولي دلوقتي وترجعلك بكرة جوّه النظام. مجاناً، وقبل ما تدفع."

*(This is your strongest card. Play it early and often.)*

**"الموظفين عندي مش هيعرفوا يستخدموه."**
> "الاستقبال بيتعلم في نص ساعة، والدكتور في شاشة واحدة بس.
> وأنا بجيلكم مرتين أدرّبهم — داخلة في السعر."

**"البرامج دي غالية."**
> "٧٬٠٠٠ مرة واحدة. لو رجّعلك ٥ حالات في الشهر بس، رجّع تمنه في ٥ شهور.
> ولو المبلغ كتير مرة واحدة، في اشتراك ٦٠٠ في الشهر من غير مقدم."

**"ولو النت وقع؟"**
> "لو النظام على جهاز العيادة، النت مالوش دخل — بيشتغل عادي داخل العيادة."

**"ولو حصلك حاجة؟ أعمل إيه ببياناتي؟"**
> "بياناتك تخرج إكسل في أي وقت بضغطة، وتاخدها معاك.
> ومعاك نسخة احتياطية على جهازك."

*(Never dodge this one. Being asked it means they are taking you seriously.)*

---

## After the demo — the same day

Send this on WhatsApp within two hours, while it is still fresh:

> "دكتور [الاسم]، شكراً لوقت حضرتك النهاردة.
> النظام جاهز ببيانات العيادة على الرابط ده: [link]
> اسم المستخدم: [x] · الباسورد: [y]
> جرّبه براحتك أي وقت، وأنا موجود لأي سؤال.
> وعلى موضوع [الحاجة اللي قالها في الدقيقة الأولى] — عملتها، وهتلاقيها جوّه."

Doing the small thing they mentioned, before they ask again, closes more deals
than any discount.

**Then follow up on day 3 and day 7.** Not more. If there is no answer after
two follow-ups, leave it and go to the next clinic — and check back in three
months. A no today is often a yes after their next bad month.
