# Secure Deployment Checklist — Aleefy Platform

**Last reviewed:** 2026-05-23

Run through this checklist for every production deployment.

---

## Pre-Deployment

### Secrets
- [ ] All secrets are in environment variables on Koyeb (not in `.env` file on the server)
- [ ] `PLATFORM_SECRET_KEY` is set to a long random hex string (min 64 bytes)
- [ ] `POSTGRES_DSN` includes `?sslmode=require`
- [ ] `PLATFORM_ADMIN_PASS` is set and meets complexity requirements (never "admin" or "1234")
- [ ] `AI_API_KEY` is set (if AI features are used)
- [ ] `CORS_ALLOWED_ORIGIN` is set to the exact website domain (e.g. `https://aleefy.vet`)
- [ ] `EMERGENCY_PHONE` is set to the clinic emergency number
- [ ] `SESSION_COOKIE_SECURE=1`

### Code
- [ ] `.env` and `.env.production` are NOT committed in git (`git status` shows them ignored)
- [ ] `git log --all -S "npg_" --oneline` returns nothing (no DSN passwords in history)
- [ ] `git log --all -S "PLATFORM_SECRET_KEY=" --oneline` returns nothing
- [ ] `pip audit` shows no critical vulnerabilities
- [ ] All DEBUG logging disabled (`FLASK_ENV=production`)

### Database
- [ ] PostgreSQL is reachable from Koyeb with the DSN
- [ ] Database user has only DML privileges (SELECT/INSERT/UPDATE/DELETE) — not DDL (CREATE/DROP)
- [ ] Neon.tech project is set to require SSL connections

---

## Deployment Steps

1. Push code to git repository
2. Koyeb detects the push and builds the container
3. Set all environment variables in Koyeb dashboard (or via CLI):
   ```
   koyeb service update aleefy \
     --env FLASK_ENV=production \
     --env PLATFORM_SECRET_KEY=<generated> \
     --env POSTGRES_DSN=<neon-dsn> \
     --env PLATFORM_ADMIN_PASS=<strong-password> \
     --env CORS_ALLOWED_ORIGIN=https://aleefy.vet \
     --env AI_API_KEY=<key> \
     --env EMERGENCY_PHONE=+20XXXXXXXXXX \
     --env SESSION_COOKIE_SECURE=1
   ```
4. Trigger a new deployment
5. Monitor startup logs for `ProductionConfig.validate()` errors

---

## Post-Deployment Verification

### Functional checks
- [ ] `/api/public/health` returns `{"ok": true}`
- [ ] Login page loads and accepts valid credentials
- [ ] Rate limiting works: 6 failed logins → lockout message appears
- [ ] File upload accepts a JPEG image; rejects a `.php` file

### Security header checks
Run: `curl -I https://your-domain.com`

- [ ] `Strict-Transport-Security` is present
- [ ] `Content-Security-Policy` is present
- [ ] `X-Frame-Options: SAMEORIGIN`
- [ ] `X-Content-Type-Options: nosniff`
- [ ] `Permissions-Policy` is present
- [ ] `Server: PAH-Platform` (not `gunicorn` or `nginx`)

### CORS check
```bash
curl -H "Origin: https://evil.com" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://your-domain.com/api/public/book -I
```
- [ ] `Access-Control-Allow-Origin` should NOT be `*` in production
- [ ] It should match only your website domain

### Error page check
- [ ] Accessing a non-existent URL returns a branded 404 page (not a Python traceback)
- [ ] Triggering a 500 error returns the generic error page (not a stack trace)

---

## Rollback Procedure

If a deployment introduces a regression:

1. In Koyeb dashboard: go to Deployments → select previous working deployment → Redeploy
2. If database migration was run: restore from the most recent backup in `data/backups/`
3. Investigate the issue in the new deployment's logs before re-deploying

---

## Secret Rotation Procedure

When rotating a secret (e.g. after a suspected breach):

1. Generate the new secret
2. Update the environment variable on Koyeb
3. Trigger a rolling restart (no downtime on Koyeb with 2+ instances)
4. Verify the old secret no longer works (e.g. old JWT/session tokens are invalidated)
5. Update this document's rotation log

| Secret | Last Rotated | Rotated By |
|--------|-------------|-----------|
| PLATFORM_SECRET_KEY | 2026-05-23 (initial) | Dr. Hatem |
| POSTGRES_DSN password | 2026-05-23 (initial) | Dr. Hatem |
| AI_API_KEY | 2026-05-23 (initial) | Dr. Hatem |
| WAPILOT_TOKEN | 2026-05-23 (initial) | Dr. Hatem |

---

## Backup Verification

Run monthly:
- [ ] Check that a backup file was created in the last 24h
- [ ] Restore the backup to a test database and verify row counts match
- [ ] Confirm backup directory permissions: `ls -la data/backups/` — should not be world-readable
