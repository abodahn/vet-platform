# API Security Checklist — Aleefy Platform

**Last reviewed:** 2026-05-23

Use this checklist when adding new API endpoints or reviewing existing ones.

---

## Public API Endpoints (`/api/public/*`)

These endpoints are unauthenticated and accessible from the internet.

| Check | Required | Status |
|-------|----------|--------|
| Rate limiting applied | YES | `/book`, `/contact`, `/emergency` — done |
| Error messages are generic (no `str(exc)`) | YES | Done — real errors logged server-side |
| CORS origin restricted to website domain | YES | Done — uses `CORS_ALLOWED_ORIGIN` env var |
| No sensitive data in response | YES | Phone number removed; medical data never returned |
| Input validated and length-limited | YES | Required fields checked |
| Parameterised SQL queries | YES | `%s` placeholders throughout |
| No session or CSRF required (by design) | YES | Public endpoints — exempt from CSRF |

### Adding a new public endpoint

Before merging:
- [ ] Add `rl = _check_rate_limit(); if rl: return rl` at the top
- [ ] Wrap all DB calls in try/except; log real error; return generic message
- [ ] Ensure no internal data (stack traces, table names, IDs) leaks in error responses
- [ ] Update CORS OPTIONS handler if new methods are needed
- [ ] Document the endpoint in this file

---

## Authenticated API Endpoints

All internal API endpoints returning JSON (`/ai/*`, `/crm/*`, etc.)

| Check | Required | Status |
|-------|----------|--------|
| `@login_required` decorator | YES | Applied to all internal routes |
| Role check (`@role_required`) where data is sensitive | YES | Applied per blueprint |
| CSRF token validated | YES | `before_request` middleware |
| IDOR check: user can only access their own/branch data | YES | Must verify per endpoint |
| Parameterised queries | YES | Must verify per endpoint |
| Error responses don't leak stack traces | YES | 500 handler + generic messages |
| Rate limiting for expensive operations (AI, reports) | Recommended | Applied to `/ai/chat` |

### IDOR Checklist

For any endpoint that takes an ID parameter (`<int:pet_id>`, `<int:visit_id>`, etc.):

- [ ] Does the endpoint verify the requesting user has access to that record?
- [ ] If the user is branch-scoped (doctor, nurse), does it check the record belongs to their branch?
- [ ] If the user is owner-facing, does it check the record belongs to that owner?

**High-risk endpoints to verify:**
- `/visits/<id>` — verify branch access
- `/crm/owners/<id>` — verify branch access
- `/finance/invoice/<id>` — verify branch access
- `/ai/context/visit/<id>` — **done**: clinical role + branch check
- `/uploads/file/<id>` — **done**: entity_type role check

---

## File Upload Endpoints

| Check | Required | Status |
|-------|----------|--------|
| Entity type validated against whitelist | YES | Done |
| Filename sanitised (UUID-based, no user input) | YES | Done |
| File extension allowed | YES | Allowlist check |
| MIME type validated from file header bytes | YES | Done (magic bytes) |
| Max file size enforced | YES | 16 MB via `MAX_CONTENT_LENGTH` |
| Files served only through authenticated route | YES | `/uploads/file/<id>` |
| No path separators in stored filenames (double-check) | YES | Done |
| `lastrowid` used (not `SELECT last_insert_rowid()`) | YES | Done |

---

## Response Headers Checklist

Applied automatically by `_security_headers()` in `app.py`:

| Header | Value | Purpose |
|--------|-------|---------|
| `Content-Security-Policy` | Restrictive policy | Prevent XSS |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Legacy XSS filter |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Privacy |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | HTTPS enforcement |
| `Permissions-Policy` | Deny geolocation/camera/mic/payment/USB | Reduce attack surface |
| `Server` | `PAH-Platform` | Hide real server fingerprint |

---

## Input Validation Standards

| Field Type | Validation |
|-----------|-----------|
| IDs (int) | Type-cast by Flask route converter `<int:id>` |
| Names | Strip whitespace; no length limit currently — consider adding |
| Phone numbers | Strip whitespace; no format validation — consider E.164 |
| Dates | Validated by DB constraints |
| Free text (notes) | Strip whitespace; no length limit currently |
| AI messages | Max 2000 chars enforced |
| Passwords | `validate_password_strength()` — 12 chars, complexity |
| File content | Magic-byte MIME check + extension allowlist |

---

## Logging Requirements

Every security-relevant API action MUST be logged via `db.log_audit()`:

| Action | Logged? |
|--------|---------|
| Successful login | Yes |
| Failed login (with username) | Yes |
| Logout | Yes |
| Password change | Yes |
| File upload | Yes |
| File delete | Yes |
| CSRF failure | Yes (warning log) |
| Rate limit hit | Recommended (add to public API) |
| IDOR attempt | Yes (warning log, added) |
| Upload MIME mismatch | Yes (warning log, added) |
