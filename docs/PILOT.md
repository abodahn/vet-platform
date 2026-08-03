# Putting clinic #1 online

The exact path from a bare server to a clinic using Aleefy. Written for one
person supporting one clinic, because that is what the first pilot is.

Everything here has been run except the parts marked **manual** — those are
steps that need a real server and a real domain, and the commands are given
so they can be followed rather than reconstructed.

---

## 0. The decision this document makes for you

There were two ways to run clinics, and they disagreed:

| | One deployment per clinic | One deployment, many clinics |
|---|---|---|
| How | `provision.sh` builds a container + nginx site each | tenant registry, subdomain routing |
| Upgrading 20 clinics | 20 deploys | 1 deploy |
| Backups | 20 places to check | 1 job, 20 databases |
| Isolation | container-level | database-level |

**Use the second.** With one person supporting the business, support load is
the constraint, and per-clinic deployments make it scale linearly with
customers. Database-per-tenant already gives the isolation that matters: a
forgotten `WHERE` cannot cross a database boundary.

`provision.sh` implements the first model and **does not register the clinic in
the tenant registry**, so a clinic created with it will not resolve by
subdomain. Do not mix the two.

---

## 1. Before anything else — rotate the admin password

The old seed password is in **5 commits** of this repository's history. Anyone
you hand the code to has a working credential.

```bash
git log --oneline --all -S "Ahmed@1122" | wc -l
```

Change it wherever it is still set, and never put the replacement in a file
that gets committed. `.env.development` is gitignored and must stay that way.

This is ten minutes and it gates everything else.

---

## 2. Bootstrap the host — once per machine

```bash
sudo bash deploy/deploy.sh
```

Installs Python, PostgreSQL, nginx, certbot and the firewall. It creates no
databases, users or secrets — an earlier version shipped the same PostgreSQL
password to every customer from a committed file, which is why it no longer
touches any of that.

---

## 3. Point DNS at the server — **manual**

For `aleefy.online`, add a wildcard A record so every future clinic works
without another DNS change:

```
*.aleefy.online.   A   <server-ip>
aleefy.online.     A   <server-ip>
```

---

## 4. Create the clinic

```bash
python scripts/add_clinic.py \
    --slug nilevet \
    --name "Nile Vet Clinic" \
    --postgres "$POSTGRES_DSN" \
    --domain aleefy.online
```

Prints the admin password **once**. It is generated, not chosen, and is never
written to a file or a log. Give it to the clinic owner and have them change it
at first login.

To see what exists:

```bash
python scripts/add_clinic.py --list
```

An existing slug is refused, never overwritten — re-provisioning would rebuild
the schema over a clinic's live records.

---

## 4b. Check the deployment is safe

```bash
python scripts/preflight.py
```

Exits non-zero until every blocking problem is clear. It checks the things that
are invisible until they matter:

| Check | Why it blocks |
|---|---|
| `PLATFORM_SECRET_KEY` | Unset means the key published in this repo. Session cookies are signed with it, so anyone could forge a login as the clinic owner. |
| `FLASK_ENV=production` | Production validation is skipped unless it is exactly this, and `DEBUG` stays on. |
| `SESSION_COOKIE_SECURE` | Off means the session cookie travels in plain HTTP. |
| `CORS_ALLOWED_ORIGIN` | Unset is a live wildcard — the public API answers any origin. |
| Backups | Never having backed up is the one mistake you cannot apologise your way out of. |
| `pg_dump` on PATH | Without it, PostgreSQL backups fail every night. |

The app also now **refuses to start** outside development if the signing key is
missing, short, or still the shipped one. It used to boot silently on it.

Everything preflight needs is named in `.env.example`. Copy it to
`.env.production` (gitignored) and fill it in.

---

## 5. Issue the certificate — **manual**

```bash
sudo certbot --nginx -d nilevet.aleefy.online
```

Handing over a clinic without this is handing over a browser warning page.

There is no wildcard certificate automation yet. For one clinic that is a
one-line step; revisit it around clinic five.

---

## 6. Load the clinic's existing records

The clinic will not start from zero — they have clients in Excel, or in another
system, or on paper.

**System → Data Migration** takes `.xlsx` and `.csv`, previews what it parsed,
and writes a `.failed.csv` of rows it could not take so nothing is lost
silently.

Do this **with the clinic owner sitting next to you**, on their real data,
before go-live day. It is where you will find out what their data actually
looks like, and it is much cheaper to discover that a week early.

---

## 7. Before you hand it over

- [ ] Owner has changed the admin password
- [ ] Staff accounts created with the right roles — a groomer should not reach `/finance/`
- [ ] Clinic name, logo, address and phone set (System → Settings) — these appear on every invoice
- [ ] Services and prices loaded (Catalog)
- [ ] Instapay handle and QR uploaded, if they take Instapay
- [ ] A backup has actually run, and you have opened the archive
- [ ] You are a manager-level user on their instance, so error alerts reach you

---

## 8. When it breaks

It will. The point of a pilot is to find out how.

**You will be told.** An unhandled error now notifies every manager-level user
with the page that failed and a link to the logs, rate-limited to one notice
per page-and-error-type per hour. Before this, errors went to a log table
nobody opens, and the clinic would mention it three days later as "the system
was being weird" — by which point the trace had rotated away.

Where to look, in order:

1. **System → Monitor** — recent errors, row counts, backup age
2. **System → Diagnostics** — is the database reachable, is the schema complete,
   does an admin exist
3. `logs/backend/` on the server for the full traceback

Backups run nightly at 02:00, per clinic. A backup that has not run is alerted
on separately — a silent missing backup is worse than a loud failed one,
because nothing prompts anyone to look.

---

## What is still missing at pilot scale

Stated plainly so it is a decision rather than a surprise:

- **No wildcard TLS automation** — one certbot line per clinic
- **Paymob is unverified** — sandbox credentials exist, `scripts/verify_paymob.py`
  closes it out. Cash and Instapay both work end to end, so this only matters
  when a clinic wants card payments
- **No owner-facing portal or online booking** — the thing competitors lead
  with, and weeks of work rather than days
- **`provision.sh` still implements the other deployment model** — it should be
  either deleted or rewritten to register the tenant, before it confuses
  somebody at clinic three
