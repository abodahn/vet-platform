# Security Architecture — Aleefy Veterinary Platform

**Classification:** Internal — Restricted  
**Owner:** Dr. Hatem El Khateeb  
**Last reviewed:** 2026-05-23  
**Platform version:** v2.x (Flask + PostgreSQL on Koyeb/Render)

---

## 1. Security Architecture Overview

The Aleefy platform is a multi-tenant veterinary ERP accessible over HTTPS. The security model has three tiers:

```
[Internet / Website]
        |
        v
[Cloudflare CDN / Koyeb TLS Termination]
        |
        v
[Flask Application (Gunicorn)]
  ├── Public API blueprint (/api/public/*)  — unauthenticated, rate-limited
  ├── Auth blueprint (/login, /logout)       — session-based
  └── All other blueprints                  — @login_required + RBAC
        |
        v
[PostgreSQL (Neon.tech) — TLS in transit, encrypted at rest]
```

**Key security controls in the application layer:**
- Session-based authentication with bcrypt password hashing
- CSRF token validation on all state-changing requests
- Role-Based Access Control (RBAC) — 10 distinct roles
- In-memory rate limiting on login and public API endpoints
- Real client IP extraction (X-Forwarded-For) behind reverse proxy
- Security headers on every response (CSP, HSTS, X-Frame-Options, etc.)
- Audit log for all security-relevant events

---

## 2. Threat Model (Summary)

| Threat | Likelihood | Impact | Mitigation |
|--------|-----------|--------|-----------|
| Brute-force login | High | High | Rate limiting (5 attempts / 15 min), lockout |
| Session hijacking | Medium | High | HTTPS-only cookies, SameSite=Lax, session timeout (1h) |
| Cross-Site Request Forgery | Medium | High | CSRF token on all POST/PUT/DELETE |
| SQL Injection | Low | Critical | Parameterised queries throughout |
| XSS | Medium | High | CSP headers, template auto-escaping (Jinja2) |
| Path traversal (uploads) | Low | High | Entity-type whitelist, UUID filenames, path validation |
| IDOR (AI visit context) | Medium | High | Role check + branch check on /ai/context/visit |
| Secrets leakage | High | Critical | Env vars only, .env in .gitignore, no hardcoded keys |
| Denial of Service (public API) | High | Medium | Rate limiting on /book, /contact, /emergency |
| Privilege escalation | Low | Critical | RBAC enforced per route, super_admin role isolated |

---

## 3. Security Gap Analysis (with Risk Ratings)

### Fixed in this release (2026-05-23)

| # | Finding | Severity | Status |
|---|---------|----------|--------|
| 1 | CORS wildcard `*` in public API | High | Fixed — uses `CORS_ALLOWED_ORIGIN` env var |
| 2 | Exception details leaked (`str(exc)`) in public API | High | Fixed — generic safe message, real error logged |
| 3 | No rate limiting on public booking/contact/emergency | Critical | Fixed — `get_real_ip` + `is_rate_limited` applied |
| 4 | Hardcoded AI API key fallback | Critical | Fixed — empty string default, must set `AI_API_KEY` |
| 5 | Hardcoded emergency phone number | Medium | Fixed — uses `EMERGENCY_PHONE` env var |
| 6 | Missing HSTS header | High | Fixed — added when HTTPS detected |
| 7 | Missing Permissions-Policy header | Medium | Fixed — geolocation, camera, microphone, etc. disabled |
| 8 | `SEED_ADMIN_PASS` default = "admin" | Critical | Fixed — empty default forces explicit set |
| 9 | Rate limiting hit proxy IP not client IP | High | Fixed — `get_real_ip()` uses X-Forwarded-For |
| 10 | IDOR: `/ai/context/visit/<id>` no authorization | High | Fixed — role + branch check added |
| 11 | Path traversal in uploads (entity_type) | High | Fixed — whitelist validation before path join |
| 12 | Path traversal in uploads (filename from DB) | High | Fixed — `_safe_attachment_path()` validates before use |
| 13 | MIME type trusted from browser | Medium | Fixed — magic-byte header validation |
| 14 | `SELECT last_insert_rowid()` (SQLite-only) | Medium | Fixed — uses `cur.lastrowid` |
| 15 | Missing `frame-ancestors` in CSP | Medium | Fixed — added `frame-ancestors 'self'` |
| 16 | Missing font CDN in CSP `font-src` | Low | Fixed |
| 17 | Missing `@app.errorhandler(500)` | High | Fixed — generic 500 page, full trace logged only |
| 18 | AI chat: no message length limit | Medium | Fixed — max 2000 chars |
| 19 | Password change: weak complexity check | Medium | Fixed — `validate_password_strength()` (12 chars, upper/lower/digit/special) |
| 20 | Login/logout IP from `remote_addr` (proxy IP) | Medium | Fixed — `sec.get_real_ip(request)` |

### Remaining — Requires Operational/Manual Action

| # | Finding | Severity | Action Required |
|---|---------|----------|----------------|
| A | Real credentials in `.env`/`.env.production` on disk | **Critical** | Rotate ALL secrets immediately; confirm .env is not committed to git |
| B | `pet_attachments.filedata TEXT` stores base64 in DB | High | Migrate to filesystem storage; drop the filedata column |
| C | `unsafe-inline` in CSP script-src | Medium | Requires refactoring inline `<script>` tags to external files + nonces |
| D | AI history: 200 rows returned at once | Low | Add pagination parameter to `/ai/history` |
| E | No HSTS preload | Low | Submit domain to hstspreload.org after 6 months of clean HSTS |
| F | OPTIONS handler on `/<path:p>` | Low | Consider restricting to known paths if CORS origin is locked down |

---

## 4. Implemented Security Controls

### Authentication & Session
- bcrypt password hashing (cost factor ≥ 12)
- Session stored server-side (Flask server-side session via signed cookie)
- Session timeout: 1 hour idle
- Session cookie flags: `HttpOnly`, `SameSite=Lax`, `Secure` (production)
- `validate_password_strength()`: min 12 chars, upper + lower + digit + special char

### CSRF Protection
- Synchronizer token pattern — `_csrf_token` in session, validated on all POST/PUT/DELETE
- Public API endpoints explicitly exempted (they are rate-limited instead)

### Rate Limiting
- In-memory, thread-safe rate limiter
- 5 failed attempts → 15-minute lockout
- Applied to: `/login`, `/api/public/book`, `/api/public/contact`, `/api/public/emergency`, `/ai/chat`
- Uses `get_real_ip()` — trusts first X-Forwarded-For address (correct for Koyeb/Cloudflare)

### RBAC (Role-Based Access Control)
- 10 roles: `super_admin`, `clinic_owner`, `branch_manager`, `doctor`, `nurse`, `reception`, `inventory_mgr`, `pharmacist`, `finance`, `hr`
- `@login_required` decorator on all authenticated routes
- `@role_required(*roles)` decorator for fine-grained access
- Upload access matrix: each entity type mapped to permitted roles

### Security Headers (every response)
```
X-Content-Type-Options: nosniff
X-Frame-Options: SAMEORIGIN
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Content-Security-Policy: default-src 'self'; ... frame-ancestors 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains  (HTTPS only)
Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(), usb=()
Server: PAH-Platform  (fingerprint removed)
```

### Upload Security
- Allowed extensions whitelist (image + document types only)
- Entity-type whitelist prevents path traversal
- Magic-byte MIME validation (independent of browser-reported content-type)
- UUID-based filenames — no user-controlled path component
- Filesystem storage only — no base64 in database for new uploads

### Database Security
- All queries use parameterised placeholders (`%s` / `?`)
- No string-formatted SQL in application code
- PostgreSQL over TLS (Neon.tech `sslmode=require`)
- Least-privilege DB user (application should not have DDL rights in production)

### Secrets Management
- All secrets via environment variables — see Section 7
- `.env` and `.env.production` in `.gitignore`
- `.env.example` with placeholder values is the only committed template

### Error Handling
- `@app.errorhandler(500)`: generic "internal error" page shown to users
- Full stack traces logged server-side only (not exposed in HTTP responses)
- Public API errors return generic safe messages; real errors go to server log

### Audit Logging
- `log_audit()` called on: login, login_failed, logout, password_change, file_upload, file_delete
- Logged fields: username, role, action, module, IP address, user-agent, timestamp

---

## 5. Remaining Manual / Operational Controls

The following cannot be enforced in code and require operational discipline:

1. **Rotate secrets immediately** — the credentials previously committed to disk (Neon.tech DSN, Wapilot token, AI API key, admin password) must be rotated.
2. **Verify .env is not in git history** — run `git log --all --full-history -- .env` and if found, use `git filter-repo` or BFG Repo Cleaner.
3. **CSP `unsafe-inline`** — requires migrating inline `<script>` blocks to external files or using nonces.
4. **DB filedata column** — `pet_attachments.filedata TEXT` should be migrated to filesystem and the column dropped.
5. **Penetration testing** — schedule an annual third-party pentest.
6. **Dependency scanning** — run `pip audit` regularly; integrate into CI.
7. **Backup encryption** — ensure database backups are encrypted at rest.
8. **Staff security training** — phishing awareness, password hygiene.

---

## 6. Compliance Mapping

### OWASP ASVS (Level 2)

| ASVS Control | Description | Status |
|-------------|-------------|--------|
| V2.1.1 | Passwords ≥ 12 chars | Implemented |
| V2.1.7 | Password complexity (upper/lower/digit/special) | Implemented |
| V2.1.12 | No password hints | N/A (no hints feature) |
| V3.2.1 | Session tokens not exposed in URLs | Implemented |
| V3.3.1 | Session invalidation on logout | Implemented |
| V3.3.2 | Session timeout | Implemented (1h) |
| V4.1.1 | Access control enforced server-side | Implemented (RBAC) |
| V4.2.1 | IDOR prevention | Implemented (role + branch check) |
| V5.1.3 | Parameterised queries | Implemented |
| V5.3.4 | Output encoding (XSS) | Implemented (Jinja2 auto-escape) |
| V7.1.1 | No sensitive data in logs | Partial (passwords not logged; tokens TBC) |
| V7.4.1 | Generic error messages | Implemented |
| V11.1.4 | CSRF on state-changing requests | Implemented |
| V13.2.3 | CORS — not wildcard in production | Implemented (env var controlled) |
| V14.4.1 | Security headers | Implemented |
| V14.4.3 | HSTS | Implemented |

### NIST CSF (v1.1)

| Function | Category | Status |
|---------|---------|--------|
| Identify | Asset Management | Partial (no formal asset inventory) |
| Protect | Access Control | Implemented |
| Protect | Data Security | Partial (encryption at rest TBC for uploads) |
| Protect | Information Protection | Implemented (secrets in env vars) |
| Detect | Anomalies / Events | Partial (audit log; no SIEM integration) |
| Respond | Response Planning | See Section 8 |
| Recover | Recovery Planning | Partial (daily backup job) |

### ISO/IEC 27001 (relevant controls)

| Control | Description | Status |
|---------|-------------|--------|
| A.9.1 | Access control policy | Implemented (RBAC) |
| A.9.2.3 | Management of privileged access | Partial (super_admin role exists, no MFA) |
| A.9.4.2 | Secure log-on procedures | Implemented |
| A.10.1 | Cryptographic controls | Implemented (bcrypt, TLS) |
| A.12.1.2 | Change management | Manual |
| A.12.3.1 | Information backup | Implemented (daily backup) |
| A.14.2.1 | Secure development policy | Partial |
| A.16.1 | Incident management | See Section 8 |
| A.18.1.4 | Privacy (personal data) | Partial — see data-classification.md |

---

## 7. Secrets Inventory

**IMPORTANT: This table lists secret categories and their environment variable names ONLY. Real values must NEVER appear in this document.**

| Secret | Environment Variable | Rotation Frequency | Owner |
|--------|---------------------|-------------------|-------|
| Platform secret key (Flask sessions) | `PLATFORM_SECRET_KEY` | Annually (or on breach) | Dr. Hatem |
| PostgreSQL DSN (includes password) | `POSTGRES_DSN` | Annually (or on breach) | Dr. Hatem |
| Admin seed password | `PLATFORM_ADMIN_PASS` | After first login | Dr. Hatem |
| AI API key | `AI_API_KEY` | Annually (or on breach) | Dr. Hatem |
| WhatsApp / Wapilot token | `WAPILOT_TOKEN` | Annually (or on breach) | Dr. Hatem |
| Emergency phone number | `EMERGENCY_PHONE` | On staff change | Dr. Hatem |

---

## 8. Incident Response Steps

### Suspected Credential Compromise

1. **Immediate**: Rotate the compromised credential in Neon.tech / Wapilot / AI provider dashboard
2. **Immediate**: Update the environment variable on Koyeb (or hosting platform)
3. **Immediate**: Restart the application to pick up new credentials
4. **Within 1h**: Check audit log (`/system/monitor` or `audit_log` table) for suspicious activity in the past 24h
5. **Within 4h**: Review git history for accidental secret commits — run `git log --all -S "suspicious_string"`
6. **Within 24h**: Notify affected parties if patient data was accessed

### Suspected Unauthorised Access

1. Identify the session/IP in audit_log
2. Force-expire session: delete row from sessions table or restart app
3. Reset the user's password
4. Document timeline and affected records
5. Assess whether patient data (PII, medical records) was accessed — notify if required by local law

### Data Breach

1. Contain: revoke all active sessions (`DELETE FROM sessions` or app restart)
2. Assess scope: which tables were accessed, which patients affected
3. Notify: Egyptian Data Protection Authority (if applicable) within 72h
4. Preserve: take a read-only snapshot of the database before any cleanup
5. Remediate: patch the vulnerability, rotate all secrets, force password resets

---

## 9. Security Checklist

| Item | Status |
|------|--------|
| All secrets in environment variables (no hardcoded values) | Completed (code) / **Manual: rotate old secrets** |
| `.env` files in `.gitignore` | Completed |
| `.env.example` with placeholder values committed | Completed |
| CORS origin restricted to website domain | Completed (env var) / **Manual: set in production** |
| Rate limiting on public API endpoints | Completed |
| Rate limiting uses real client IP (X-Forwarded-For) | Completed |
| IDOR check on AI visit context endpoint | Completed |
| Message length limit on AI chat | Completed |
| MIME validation on file uploads | Completed |
| Path traversal prevention on uploads | Completed |
| HSTS header (HTTPS responses) | Completed |
| Permissions-Policy header | Completed |
| `frame-ancestors 'self'` in CSP | Completed |
| Generic 500 error page (no stack trace to user) | Completed |
| Password strength validation (12 chars, complexity) | Completed |
| `SEED_ADMIN_PASS` no longer defaults to "admin" | Completed |
| Production startup validation of required env vars | Completed |
| Audit logging on security events | Completed |
| `unsafe-inline` removed from CSP | **Not started — requires JS refactor** |
| `pet_attachments.filedata` column removed | **Not started — requires migration** |
| HSTS preload submitted | **Manual: submit after 6 months clean HSTS** |
| MFA for admin accounts | **Not implemented** |
| Dependency vulnerability scanning (pip audit) | **Manual: run regularly** |
| Annual penetration test | **Manual: schedule** |
