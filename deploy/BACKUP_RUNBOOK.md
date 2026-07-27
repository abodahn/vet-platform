# Backup & Restore Runbook

For the person who looks after the clinic's server. You do not need to be a
programmer to follow this. Read it once **before** you need it.

---

## 1. What is being protected

One database file holds everything: owners, pets, visits, prescriptions,
invoices, payments, stock, staff. Lose it and the clinic has no records.

Two possible setups:

| Setup | Where the data lives | Backup file |
|---|---|---|
| SQLite (single server, typical small clinic) | `data/platform.db` | `platform_backup_*.db` |
| PostgreSQL (hosted / multi-branch) | the PostgreSQL server named by `POSTGRES_DSN` | `platform_backup_*.dump` |

Uploaded documents and images in `data/uploads/` are **not** in these backups.
Copy that folder separately (see section 4).

---

## 2. Where backups go

* **Automatically, every night at 02:00**, into `data/backups/` next to the
  database. Kept for 30 days, then deleted.
* You can make one at any time: **System → Backup & Restore → "Back Up Now"**.

Three kinds of file appear in that folder:

| Name starts with | Means |
|---|---|
| `platform_backup_` | a normal scheduled or manual backup |
| `pre_restore_` | a safety snapshot taken automatically just before a restore |
| `uploaded_` | a file someone uploaded from a USB stick |

**A backup sitting next to the database is not yet a backup.** One dead disk,
one stolen server, one flood, and both are gone. Set up section 3.

---

## 3. Off-site copies (do this on day one)

Set environment variables in `.env` (or the systemd unit), then restart the
service. Both options are optional; unset means "skipped", not "failed".

### Option A — a second drive or a network share (recommended for a self-hosted clinic)

```
BACKUP_OFFSITE_DIR=/mnt/usb-backup          # Linux
BACKUP_OFFSITE_DIR=E:\ClinicBackups         # Windows USB drive
BACKUP_OFFSITE_DIR=//nas/backups/clinic     # network share
```

Every backup is copied there right after it is made, and the same 30-day
retention is applied so the drive does not fill up.

Practical advice: use **two** USB drives and swap them weekly, keeping one
outside the building. A USB stick permanently plugged into the server does not
survive a fire or a theft.

### Option B — cloud storage (Backblaze B2, Hetzner Storage Box, MinIO, any S3-compatible bucket)

```
BACKUP_S3_ENDPOINT=https://s3.eu-central-003.backblazeb2.com
BACKUP_S3_BUCKET=aleefy-clinic-backups
BACKUP_S3_KEY=<application key id>
BACKUP_S3_SECRET=<application key>
BACKUP_S3_REGION=eu-central-003
BACKUP_S3_PREFIX=cairo-branch                # optional folder inside the bucket
```

No extra software to install — this uses libraries the platform already ships.

Cost check for a typical clinic: a 200 MB database backed up nightly with 30-day
retention is about 6 GB stored, well inside the cheapest tier anywhere.

**Turn on the bucket's own versioning / object-lock if it is offered.** It is
the only thing that protects you from ransomware that encrypts the server and
then overwrites the cloud copies with encrypted ones.

### Checking it works

Open **System → Backup & Restore**. The "Off-site copy" card names each target.
Press "Back Up Now" — if a copy fails you get a red message on the page, an
entry in the log, and a notification for every manager. The local backup still
succeeds; you are never left with nothing because the USB drive was unplugged.

---

## 4. What is NOT covered

* `data/uploads/` — scanned documents, x-ray images, pet photos.
  Copy this folder to the same off-site drive on a schedule of your own
  (`robocopy` on Windows, `rsync` on Linux). It only grows, so a weekly
  incremental copy is enough.
* `.env` — contains the secret key and passwords. Keep **one** copy somewhere
  safe and offline. Without it, sessions and encrypted 2FA secrets break after
  a rebuild.

---

## 5. How to tell a backup is good, WITHOUT restoring it

Three levels, cheapest first.

**Level 1 — from the app (30 seconds).**
System → Backup & Restore → the "Check" button on any row. Green means the file
opens, is complete, and is not truncated. Red means do not rely on that file.

**Level 2 — from the command line, on any machine.**

SQLite:
```bash
sqlite3 platform_backup_20260728_020000.db "PRAGMA integrity_check;"
# must print exactly: ok
sqlite3 platform_backup_20260728_020000.db "SELECT COUNT(*) FROM pets;"
# must print a number close to what the clinic actually has
```

PostgreSQL:
```bash
pg_restore --list platform_backup_20260728_020000.dump | head -30
# must list tables; if it errors, the dump is unreadable
```

**Level 3 — the only real proof: a test restore, quarterly.**
See section 7. Put it in the calendar. A backup you have never restored is a
hope, not a backup.

---

## 6. Restoring on this server (something went wrong today)

1. **Do it out of hours.** Staff are locked out during the restore.
2. System → Backup & Restore.
3. Find the row for the date you want. Check the date column carefully —
   everything entered *after* that moment will be gone.
4. Press **Restore**. Read the warning. Type the file name to confirm.
5. The platform:
   * refuses if the file is unreadable, so a bad file cannot destroy a good
     database;
   * puts the system into maintenance mode (staff see a "back in a few minutes"
     page);
   * **takes a snapshot of the current data first**, named `pre_restore_…`;
   * replaces the database;
   * comes back online.
6. **If you restored the wrong file**: restore the `pre_restore_…` file that
   was just created. That undoes it.

If the page ever says the system is stuck in maintenance mode, there is a
"Clear maintenance mode" button on the same page. The marker also clears itself
after 15 minutes.

---

## 7. Restoring onto a fresh machine (the server is dead)

You need: the backup file, the `.env` file, and the application code.

1. Install the platform on the new machine as per `deploy/deploy.sh`.
   **Do not start it yet.**
2. Copy your `.env` back into place.
3. **SQLite:** copy the backup file to `data/platform.db`.
   ```bash
   mkdir -p data
   cp /mnt/usb-backup/platform_backup_20260728_020000.db data/platform.db
   sqlite3 data/platform.db "PRAGMA integrity_check;"     # must print: ok
   ```
   **PostgreSQL:** create an empty database, then:
   ```bash
   pg_restore --no-owner --clean --if-exists \
              -d "$POSTGRES_DSN" platform_backup_20260728_020000.dump
   ```
4. Copy `data/uploads/` back from your off-site drive.
5. Start the service. Log in. Check the newest few visits and invoices are
   there and match what you expect.
6. Immediately press **Back Up Now**, and confirm the off-site card is green.

Expect this to take 30–60 minutes on a machine that already has the OS
installed. Time it once so you can tell the clinic owner a real number.

---

## 8. How you find out backups have stopped

* The backup page shows **"Last successful backup — N hours/days ago"** in large
  type, red once it is older than `BACKUP_STALE_DAYS` (default 2).
* The same figure appears on the System Monitor page.
* Every manager gets a notification when a backup fails, when an off-site copy
  fails, or when no backup has succeeded within the stale window. Sent at most
  once a day so it is not ignored as noise.
* Everything is also written to the application log with `BACKUP ALERT`.
  If you run any log monitoring, alert on that string.

**Nothing here helps if the whole server is off.** Also set up an external
uptime check (any free service pinging the login page) so a dead machine is
noticed by someone other than the machine itself.

---

## 9. Quarterly drill — 20 minutes, once every three months

1. Take the newest off-site backup to a different computer.
2. Follow section 7 onto a spare machine or a virtual machine.
3. Log in and check five recent invoices against the live system.
4. Write down the date and how long it took.
5. Destroy the test copy — it holds real patient data and is subject to the
   same confidentiality rules as the live system.

If step 2 fails, you have found the problem on a quiet Tuesday instead of on
the day the server died.

---

## 10. Quick reference

| Setting | Default | What it does |
|---|---|---|
| `BACKUP_OFFSITE_DIR` | unset | second folder/drive to copy every backup to |
| `BACKUP_S3_ENDPOINT` / `_BUCKET` / `_KEY` / `_SECRET` / `_REGION` / `_PREFIX` | unset | S3-compatible bucket |
| `BACKUP_STALE_DAYS` | `2` | how old the last backup gets before it is flagged and managers are notified |

Retention is 30 days, nightly at 02:00, in `data/backups/`.
