# Working without internet

**Decided 2026-08-26: one clinic, one building, one network.**

That decision is what makes the rest of this short. Write it down, because the
answer changes completely if it ever stops being true.

---

## The answer for one building

**Install the app on a PC inside the clinic.** Staff connect to it over the
local network — the reception desktop, the vet's laptop, a tablet on the wifi.

The internet is not in the path of any of it. When the line drops, and in Egypt
it will, nothing changes: consultations, prescriptions, invoices, the till, all
keep working. Nobody notices.

This is not a feature that had to be built. It is how the app deploys.

## The risk that creates, and the fix

One PC now holds every patient record the clinic has. Fire, theft, a dead disk,
a stolen laptop — all of it gone at once.

So the nightly backup at 02:00 also sends an **encrypted** copy off-site
whenever the internet happens to be up. If the line is down at 02:00 the local
backup still succeeds and the off-site copy goes the next night. An off-site
failure never turns a good local backup into a reported failure: one copy beats
zero copies.

### Turning it on at a clinic

```bash
python scripts/verify_backup_key.py --init      # once, per clinic
```

Put the key in that clinic's `.env` as `BACKUP_ENCRYPTION_KEY`, **and in your
password manager**. Then pick where the copy goes:

```
BACKUP_OFFSITE_DIR=D:/backup          # a USB drive or NAS - simplest
```

or any S3-compatible bucket via `BACKUP_S3_*`. Then prove the key works:

```bash
python scripts/verify_backup_key.py
python scripts/verify_backup_key.py --check-latest    # against the real archive
```

**With no key set, the off-site copy is not sent.** That is deliberate. The
archive holds every patient record and every client phone number; refusing to
send it is recoverable, and sending it in the clear to a bucket or a USB stick
that somebody already has is not.

The LOCAL copy stays readable on purpose. It sits on the clinic's own disk
beside the database it came from, and an encrypted local backup whose key has
been lost is not a backup at all.

---

## What is NOT built, and why that is correct here

There is no offline **sync** — no writing on a disconnected device that
uploads later, and no two-way flow between a clinic and a cloud copy.

For one building on one network there is nothing for it to do. The staff are
all on the same network as the server; if that network is up they are online in
every sense that matters, and if it is down they are standing in a clinic with
no computers working, which sync does not help with either.

### When that stops being true

Two situations would change the answer:

- **A vet doing home visits** who needs to record a consultation on a tablet
  with no signal and have it appear back at the clinic.
- **A second branch** sharing one patient list.

Either of those makes sync necessary rather than decorative.

### What already exists for that day

Roughly 80% of the machinery is in the tree, disconnected:

| Piece | State |
|---|---|
| `models/sync.py` — queue, conflicts, device registry, retries | built, 265 lines |
| `/api/v1/sync/push`, `/api/v1/sync/status` | built, **blueprint not registered** |
| IndexedDB store and flush loop in `base.html` | built |
| `window.v3QueueOffline(...)` | defined, **no callers** |
| Sync dashboard at `/system/sync` | built |

Somebody wired the pipes and never connected the taps. Finishing it is not the
hard part.

### The hard part, recorded now so it is not rediscovered later

The plumbing is easy. These are the decisions that make offline sync dangerous
in medical software, and every one needs an answer from the owner, not from a
developer:

- **Two devices create invoice 501 offline.** Both sync. Which is real?
- **A payment syncs before the invoice it pays.** Ordering is not free.
- **Two vets edit the same patient offline.** Last-write-wins silently destroys
  a clinical note.
- **The last unit of a drug is sold twice offline.** Stock goes negative — the
  exact defect fixed in the POS in August.
- **A cached record shown as current.** `static/sw.js` refuses to cache pages
  today, and its comment explains why: *a cached HTML page is a stale medical
  record*. That reasoning does not stop being true because offline is wanted.

Do not start this until there is a real second location. It is weeks of work
and it introduces failure modes the single-building setup simply does not have.
