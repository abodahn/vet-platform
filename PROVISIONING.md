# Provisioning — running clinics

This is the runbook. It assumes you are tired, it is late, and something needs
to happen now. Commands first, reasons after.

**One clinic = one container = one database = one set of secrets.** The app is
single-tenant: no table has a `clinic_id`, so two clinics sharing one instance
would share one patient list. That is why every clinic gets its own everything.

Everything lives under `/srv/aleefy` (override with `ALEEFY_ROOT`):

```
/srv/aleefy/clinics/<slug>/
    .env                  secrets, mode 0600         <- never copy, never commit
    docker-compose.yml    this clinic's container
    data/                 SQLite file (if used) + uploads
    data/backups/         this clinic's backups only
    logs/
    .upgrade-state        how to roll back (no secrets in it)
```

---

## Adding a clinic

Once per machine:

```bash
sudo bash deploy/deploy.sh          # docker, postgres, nginx, ufw. Nothing else.
```

Then per clinic:

```bash
scripts/provision/provision.sh --clinic happytails --domain happytails.aleefy.vet
sudo certbot --nginx -d happytails.aleefy.vet      # TLS, once DNS points here
```

That is the whole thing. It picks a free port, generates every secret fresh,
creates the database and role, writes `.env` at 0600, starts the container,
waits for `/api/v1/health`, and prints the credentials **once**.

**Store the printed credentials immediately.** They are shown on the terminal
and written nowhere you can read them back except `.env` (root-only). Close the
terminal after you have them in the password manager.

On a clinic's own PC with no PostgreSQL:

```bash
scripts/provision/provision.sh --clinic happytails --sqlite
```

Useful flags: `--title "Happy Tails Vet"`, `--phone +20...`, `--root /other/path`,
`--no-start` (set up but do not launch), `--image aleefy:v1.4.0` (reuse a built
image instead of building).

### If it fails halfway

Nothing needs undoing. Re-run the same command — a directory without a `.env`
is treated as an abandoned attempt and continues. A directory **with** a `.env`
is refused (see below).

---

## Secret handling — the rules

| Secret | What it is | If it changes |
|---|---|---|
| `PLATFORM_SECRET_KEY` | signs session cookies | everyone is logged out |
| `PLATFORM_ADMIN_PASS` | first-run admin seed | only matters before first login |
| `POSTGRES_DSN` | contains the DB password | the clinic loses its own records |
| `WAITING_ROOM_TOKEN` | gates the public TV display | the waiting-room screen goes blank |
| `API_V1_KEY` | Bearer token for `/api/v1` | any integration stops working |

All five are generated per install, from `secrets` (the CSPRNG), never copied
between clinics, never defaulted. `AI_API_KEY`, `WAPILOT_TOKEN`,
`BACKUP_S3_*`, `SENTRY_DSN` and friends are yours to paste in when a clinic
buys the feature — provisioning never invents them and never wipes them.

1. **Never redirect provisioning output to a file.** The credentials print to
   the terminal. `provision.sh > out.txt` puts them on disk forever; the script
   warns you when it cannot find a terminal, and that warning is real.
2. **Never copy a `.env` to another clinic.** That is exactly the bug this
   replaced: the old `deploy.sh` shipped one PostgreSQL password to everyone.
3. **Rotating one secret** = edit that one line in `.env`, then
   `docker compose -f /srv/aleefy/clinics/<slug>/docker-compose.yml up -d`.
   Rotating the DSN password also needs
   `sudo -u postgres psql -c "ALTER ROLE clinic_<slug> WITH PASSWORD '...'"`.
4. `/srv/aleefy` is mode 700 and every `.env` is 0600. If you ever see one at
   644, something copied it wrong — regenerate rather than chmod.

---

## Upgrading one clinic

```bash
scripts/provision/upgrade.sh --clinic happytails --ref v1.4.0
```

With a schema change:

```bash
scripts/provision/upgrade.sh --clinic happytails --ref v1.4.0 \
    --alembic 0002_audit_log_indexes
```

The order is fixed: **backup → verify the backup → build → migrate → restart →
health check**. A failed backup aborts before anything is touched. A failed
health check rolls the image back automatically.

> **`--alembic head` is refused, on purpose.** There are two deliberate heads
> (`0002_audit_log_indexes` and `0002_money_numeric`) and they must not both be
> applied — `0002_money_numeric` is an on-hold financial migration. Name the
> revision you want. Read `MIGRATIONS.md` before naming anything other than
> `0002_audit_log_indexes`.

## Upgrading all of them

```bash
scripts/provision/upgrade.sh --all --ref v1.4.0
```

One clinic at a time, and it **stops at the first failure**. Clinics already
upgraded stay upgraded and running; the rest stay on the old version until
someone looks. That is intentional — marching on turns one bad release into
twenty broken clinics.

Check what happened:

```bash
python3 scripts/provision/inventory.py
```

---

## Rolling back

**Code only** (the common case — new version misbehaves, data is fine):

```bash
scripts/provision/upgrade.sh --clinic happytails --rollback
```

Reads `.upgrade-state`, puts the previous image back, restarts. Seconds.

**Data too** (a migration or a bug corrupted records). This is destructive and
deliberately not automatic:

1. Find the pre-upgrade backup — its filename is in
   `/srv/aleefy/clinics/<slug>/.upgrade-state`.
2. Roll the code back first (above), so the old code meets the old schema.
3. Restore, either from the app (**System → Backup → Restore**, which is the
   path with the maintenance lock and the safety pre-restore snapshot), or:

```bash
cd /path/to/platform
set -a; . /srv/aleefy/clinics/happytails/.env; set +a
PLATFORM_DB_PATH=/srv/aleefy/clinics/happytails/data/platform.db python3 - <<'PY'
import os, models.backup as bk
db = os.environ["PLATFORM_DB_PATH"]
bk.configure(db, os.path.join(os.path.dirname(db), "backups"))
print(bk.restore_backup("platform_backup_YYYYmmdd_HHMMSS.dump"))
PY
```

4. If a migration was applied, undo it explicitly:
   `alembic -c db_migrations/alembic.ini downgrade <the PREV_ALEMBIC in .upgrade-state>`.

Everything between the backup and the restore is lost. That is the trade and
there is no version of it where it is not.

---

## Who is up, on what, backed up when

```bash
python3 scripts/provision/inventory.py            # table
python3 scripts/provision/inventory.py --json     # for a monitor
python3 scripts/provision/inventory.py --quiet    # only what is broken
```

```
CLINIC            PORT   VERSION       DB        UP   LAST BACKUP       NOTES
happytails        5100   v1.4.0        postgres  yes  2026-07-27T02:00
riverside         5101   v1.3.2        postgres  NO   2026-07-25T02:00  DOWN, backup 2.4d old
```

Exit code is non-zero when any clinic needs attention, so cron only mails you
when something is wrong:

```
0 8 * * * python3 /path/to/platform/scripts/provision/inventory.py --quiet
```

"Last backup" is the newest archive actually on disk, not a status row. A
status row that can disagree with the filesystem is how "nightly backup OK"
gets logged while no file exists.

At a glance, without the script: `docker compose ls` shows one project per
clinic and whether it is running.

---

## Decommissioning a clinic

A clinic that leaves owns its data. Give it to them before you delete anything.

```bash
SLUG=happytails; DIR=/srv/aleefy/clinics/$SLUG

# 1. Final backup, while it is still running.
cd /path/to/platform
set -a; . $DIR/.env; set +a
PLATFORM_DB_PATH=$DIR/data/platform.db python3 -c "
import os, models.backup as bk
db=os.environ['PLATFORM_DB_PATH']
bk.configure(db, os.path.join(os.path.dirname(db),'backups'))
r=bk.run_backup(); print(r); raise SystemExit(0 if r['success'] else 1)"

# 2. Hand over: the backup archive AND their uploaded files.
tar czf /root/$SLUG-handover.tar.gz -C $DIR data
#    Deliver it, then get written confirmation they have it and can open it.

# 3. Stop and remove the container (data still on disk).
cd $DIR && docker compose down

# 4. Nginx.
sudo rm -f /etc/nginx/sites-enabled/clinic-$SLUG /etc/nginx/sites-available/clinic-$SLUG
sudo nginx -t && sudo systemctl reload nginx

# 5. Only after step 2 is confirmed: database, then directory.
sudo -u postgres dropdb clinic_${SLUG//-/_}
sudo -u postgres dropuser clinic_${SLUG//-/_}
rm -rf $DIR
```

Do not skip step 2 and do not compress steps 2 and 5 into one session. The
usual failure is deleting on the day they ask and discovering a week later
that the handover archive was truncated.

---

## Why this shape

**docker-compose project per clinic, one shared PostgreSQL, one shared nginx.**

Considered and rejected:

- *systemd unit per clinic* — no isolation of Python or system dependencies
  (every clinic upgrades when you `pip install`), and it cannot run on a clinic
  PC, which is half the deployment story.
- *plain directories behind a proxy* — same dependency coupling, plus nothing
  restarts a crashed clinic.
- *PostgreSQL container per clinic* — the honest version of full isolation, and
  it does not fit. Ten postgres containers plus ten app containers do not run
  on a €5–7 VPS. Isolation you cannot afford is isolation you do not have.

**How clinic A's outage stays clinic A's.** Separate container with a 512 MB
memory limit, a CPU cap, a PID limit and capped logs — a runaway report gets
its own container OOM-killed and restarted while the neighbours keep serving.
Separate database and separate role, with `CONNECT` revoked from `PUBLIC`, so
clinic A's credentials cannot open clinic B's database even if leaked.
Separate ports bound to `127.0.0.1`, so nothing is reachable except through
nginx.

**The one shared failure domain is the PostgreSQL server.** If it dies, every
clinic on that host is down. That is the price of fitting ten clinics on a €5
VPS, and it is a real risk, not a rounding error. A clinic that cannot tolerate
it goes on its own box, or on `--sqlite` on its own PC where the only thing it
shares is nothing.

**At a glance:** `docker compose ls`, or `inventory.py`.

---

## Known gaps — what still needs a human

- **The app image has no `postgresql-client`.** `models/backup.py` shells out to
  `pg_dump`, so backups run from the **host** (which has it), not inside the
  container. That works and is what `upgrade.sh` does. Adding
  `postgresql-client` to the `Dockerfile` would let the container back itself
  up; the Dockerfile is outside this change's scope. **Report it.**
- **TLS is manual.** `certbot --nginx -d <domain>` per clinic, once. Renewal is
  automatic after that.
- **No secret store.** Secrets live in each clinic's `.env` at 0600 and in your
  password manager. At twenty clinics that is twenty rows a human maintains.
- **No automated off-site backup by default.** `BACKUP_OFFSITE_DIR` and
  `BACKUP_S3_*` exist and work; provisioning leaves them blank because the
  destination is per-customer. Set them per clinic, or the only copy of a
  clinic's records is on the same disk as the clinic.
- **Provisioning is Linux-only.** `provision.sh` refuses to run elsewhere,
  because 0600 does not exist on Windows and the secrets would be readable by
  every account on the machine. `clinic_env.py` is importable and testable
  anywhere; that is for development, not for standing up a real clinic.

### Where this breaks

Somewhere between **10 and 15 clinics on one VPS**: RAM, and one PostgreSQL
serving all of them. Past that, split across hosts — the scripts take `--root`
and do not care which machine they run on, so the next step is a second VPS,
not a rewrite.

Past roughly **20 clinics total**, the manual parts stop being tolerable:
credentials in a password manager by hand, certbot per domain, one operator
running `--all` and watching it. That is the point to buy a secret store and
wire the inventory into a monitor — not before.
