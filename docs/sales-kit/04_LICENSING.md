# Licensing — how to actually use it

Activation is by phone. The clinic reads you a number, you read a code back.
No internet, no clock, no app for them to install.

---

## Once, ever

Create your master secret and store it properly.

```bash
python scripts/make_license.py --init
```

**Before you close that window:** save it in a password manager *and* somewhere
that survives your laptop dying.

This is not like a password. If it leaks, anyone can mint activation codes for
every clinic you have ever sold to, and you cannot revoke them without breaking
all your paying customers at once. **If you lose it, you can never issue another
code for anybody** — including clinics already paying you, at their next renewal.

`tests/test_no_credentials_in_repo.py` fails the build if it ever lands in a
tracked file. That guard was tested by planting a fake key and watching it fail.

---

## Each new clinic, at install

**1. Give that clinic its own secret.**

```bash
python scripts/make_license.py --derive --clinic hatem-vet
```

Put the printed line into **that clinic's `.env`**. Every clinic gets a
different one, derived from your master, so a secret lifted from one
installation is useless anywhere else.

> Write the clinic id down. `hatem-vet` must be spelled identically every time —
> a typo produces a code that looks fine and simply never works.

**2. Open the licence screen on their machine.**

`Settings → Licence`, or `/system/license`. It shows:

```
ALF-7706-4095
```

**3. Generate their code** — laptop or phone, whichever you have:

```bash
python scripts/make_license.py --clinic hatem-vet --machine ALF-7706-4095
```

**4. They type it in.** Done. It works on that computer and no other.

---

## From your phone

The same tool, served from **your own domain**:

```
https://demo.aleefy.online/static/tools/codes/index.html
```

Open it once on your phone and **Add to Home Screen**. After that first visit a
service worker holds the whole thing locally, so it opens **with no network at
all** — no signal, no server, nothing to log into. Just an icon that works.

It is on your infrastructure deliberately. A tool that issues revenue-critical
codes should not depend on anyone else's account staying active, including mine.

*(Backup copy, if your server is ever down:*
`https://claude.ai/code/artifact/67b07342-1fe5-4061-9ee5-2de48592488a` *— that
one needs you signed into Claude, which is exactly why it is the backup and not
the main one.)*

**Is it a problem that the URL is public?** No. The page is a calculator with no
key in it — it computes nothing without the master secret you type in, and that
lives only in your phone's encrypted storage. It carries `noindex` so it stays
out of search results, and the activation form in the app is rate limited so the
eight-digit code cannot be ground through by a script.

A normal authenticator app cannot do this. Those produce a code from a fixed
seed and the clock. Yours has to take *their machine number* as input and answer
for that machine, which is a different calculation.

**First time on the phone:** paste your master secret and choose a PIN. It is
encrypted with the PIN (PBKDF2, 250,000 rounds, then AES-GCM) and stored on that
device only. The HTML file itself contains no secret, which is why it is safe to
serve publicly and to keep in the repo.

**Every time after:** PIN → clinic → machine number → code.

The phone and the laptop are checked against each other by
`tests/test_licensing.py::test_phone_tool_issues_the_same_codes_as_python`,
over 192 vectors including Arabic clinic ids and a leap February. If the two
implementations ever drift, the build fails — because a mismatch would mean
reading a clinic a code the app refuses, with no way for either of you to tell
which side was wrong.

---

## Renewal, once a year

The system tells the clinic before you have to:

| When | What they see |
|---|---|
| 30 days before | "Your licence renews in N days." |
| Expiry to +60 days | **Nothing.** Silence, deliberately. |
| +60 to +90 days | "Expired on <date>. The system keeps working as normal." |
| After +90 days | **Nothing, ever again.** |

Issue the new code exactly as before. The clinic types it in and the banner
disappears.

---

## What it does not do, on purpose

**It never blocks anything.** Not one screen, not one record, at any stage. The
worst thing that happens is a banner.

That is a decision, not an omission. These are patient records and vaccination
histories. A vet locked out at 11pm with a sick animal on the table would tell
every other vet in the market, and in Egypt that is a small number of
conversations. Your leverage over a clinic that will not pay is the yearly phone
call, not a locked door — and for anyone you genuinely do not trust, host the
system yourself, where the code never leaves your server.

`tests/test_licensing.py` asserts this at every stage of expiry, out to 5,000
days past. If that test ever fails, somebody has locked a clinic out.

**A replaced computer is noted, not punished.** If the fingerprint changes, the
licence screen mentions it and logs it. Nothing stops. PCs die and get replaced,
and turning that into an emergency support call would mean you disabled the
check yourself by the third one.

**After 90 days of silence it gives up permanently.** If you are ill,
travelling, or unreachable, no clinic is left stranded — and a buyer asking
"what happens to our customers if he disappears" gets a real answer.

---

## What this honestly protects

**It stops casual copying.** A clinic cannot hand a working copy to a friend,
because the code only works on the machine that produced the challenge. That is
the realistic threat and it is genuinely covered.

**It does not stop a determined technical person.** For a code to be verified
offline, the verifying secret has to be on the clinic's machine — that is
arithmetic, not a weak choice of library. Someone who can read Python can
extract it, and that same person could just delete the check on the next line.

Nothing in the code claims otherwise, and neither should you. If a customer
worries you, the answer is hosting, not a better lock.
