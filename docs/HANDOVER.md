# Platform Handover Document
**Premium Animal Hospital — Dr. Hatem El Khateeb**
**Prepared:** 2026-05-17 | **Version:** 2.0 Production-Ready

---

## 1. How to Start the Platform

```bash
cd C:\vet\platform
python run.py
```

- Platform URL: **http://localhost:5100**
- Legacy App URL: **http://localhost:5000**
- Default login: **admin / 1234**

---

## 2. All Changed / New Files

### New Python Modules
| File | Purpose |
|------|---------|
| `models/security.py` | Rate limiting, CSRF tokens, session timeout |
| `models/backup.py` | SQLite online backup, integrity check, retention |
| `blueprints/catalog/__init__.py` + `routes.py` | Service & price catalog |
| `blueprints/notifications/__init__.py` + `routes.py` | In-app notification center |
| `blueprints/pharmacy/__init__.py` + `routes.py` | Prescription dispensing queue (FEFO) |
| `blueprints/uploads/__init__.py` + `routes.py` | Secure file attachments |
| `blueprints/whatsapp/scheduler.py` | Daily reminder jobs (appointments, vaccines, invoices) |

### Modified Python Files
| File | What Changed |
|------|-------------|
| `app.py` | Registers 4 new blueprints, APScheduler, CSRF middleware, backup config |
| `models/database.py` | bcrypt migration, 4 new tables, SOAP columns, notification/catalog helpers |
| `blueprints/auth/routes.py` | Rate limiting on login, bcrypt password change |
| `blueprints/visits/routes.py` | SOAP notes save route |
| `blueprints/reports/routes.py` | Period-comparison financial route |
| `blueprints/system/routes.py` | Backup panel routes (list + manual trigger) |
| `blueprints/whatsapp/routes.py` | Reminder settings route |
| `blueprints/launcher/routes.py` | 3 new modules: pharmacy dispense, service catalog, notifications |

### New Templates
| Template | Route |
|----------|-------|
| `templates/catalog/index.html` | `/catalog/` |
| `templates/notifications/index.html` | `/notifications/` |
| `templates/pharmacy/index.html` | `/pharmacy/` |
| `templates/pharmacy/history.html` | `/pharmacy/history` |
| `templates/pharmacy/rx_detail.html` | `/pharmacy/prescription/<id>` |
| `templates/pharmacy/label.html` | `/pharmacy/label/<rx>/<pi>` |
| `templates/system/backup.html` | `/system/backup` |
| `templates/whatsapp/reminder_settings.html` | `/whatsapp/reminder-settings` |

### Modified Templates
| Template | What Changed |
|----------|-------------|
| `templates/base.html` | CSRF token in theme form, notification bell, Pharmacy/Catalog/Backup/Reminder links |
| `templates/login.html` | CSRF token added |
| `templates/visits/visit_detail.html` | SOAP notes section, CSRF on all forms |
| `templates/reports/financial.html` | Period comparison banner + delta badges |
| `templates/system/monitor.html` | Backup status panel + manual backup button |

---

## 3. New Database Tables

| Table | Purpose |
|-------|---------|
| `notifications` | In-app alerts — role-based, per-user read tracking |
| `service_catalog` | Billable services with prices, tax, duration, species |
| `reminder_runs` | Deduplication log for WhatsApp reminders |
| `attachments` | File upload metadata (files stored in `data/uploads/`) |

### Schema Migrations (ALTER TABLE — safe, idempotent)
```sql
ALTER TABLE visits ADD COLUMN soap_subjective TEXT;
ALTER TABLE visits ADD COLUMN soap_objective  TEXT;
ALTER TABLE visits ADD COLUMN soap_assessment TEXT;
ALTER TABLE visits ADD COLUMN soap_plan       TEXT;
```
These run automatically on first startup via `init_db()`.

---

## 4. Security Features Active

| Feature | Details |
|---------|---------|
| **Rate Limiting** | 5 failed logins → 15-minute lockout per IP |
| **CSRF Protection** | All POST forms require `_csrf_token` session token |
| **Session Timeout** | 1-hour idle timeout, auto-redirect to login |
| **bcrypt Passwords** | SHA-256 hashes transparently migrated to bcrypt on next login |
| **Secure Uploads** | Files stored by UUID, served only through authenticated role-checked route |

---

## 5. Scheduled Jobs (APScheduler)

| Job | Schedule | What It Does |
|-----|----------|-------------|
| `daily_backup` | 02:00 every day | SQLite online backup → `data/backups/`, 30-day retention |
| `wa_reminders` | 09:00 every day | Appointment (next-day), vaccine due, overdue invoice WhatsApp messages |
| `rl_cleanup` | Every hour (minute=0) | Clears expired rate-limit entries from memory |

---

## 6. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `WAPILOT_TOKEN` | *(empty)* | WhatsApp API token — leave empty for stub/log-only mode |
| `DATABASE_PATH` | `data/platform.db` | SQLite database path |
| `SECRET_KEY` | auto-generated | Flask session key — set a fixed value in production |

---

## 7. Key URLs

| Module | URL |
|--------|-----|
| Launcher | `/` |
| Login | `/auth/login` |
| Pharmacy Queue | `/pharmacy/` |
| Service Catalog | `/catalog/` |
| Notifications | `/notifications/` |
| File Upload | `POST /uploads/upload` |
| Backup Manager | `/system/backup` |
| Reminder Settings | `/whatsapp/reminder-settings` |
| System Monitor | `/system/monitor` |
| Audit Log | `/system/audit` |

---

## 8. Rollback Instructions

If something goes wrong:

1. **Stop the server** (Ctrl+C)
2. **Restore from backup**: copy a `.db` file from `data/backups/` over `data/platform.db`
3. **Git rollback** (if using git): `git stash` or `git checkout <previous-commit>`
4. **Restart**: `python run.py`

The SOAP ALTER TABLE columns are safe to leave — they are nullable and won't break old queries.

---

## 9. Production Checklist

- [ ] Set `SECRET_KEY` to a fixed random string in `config.py`
- [ ] Set `SESSION_COOKIE_SECURE = True` (requires HTTPS)
- [ ] Configure `WAPILOT_TOKEN` env variable for real WhatsApp sending
- [ ] Verify backup directory `data/backups/` is included in server backup policy
- [ ] Change default admin password from `1234`
- [ ] Run behind a reverse proxy (nginx) with HTTPS
- [ ] Set `DEBUG = False` (already default)

---

## 10. Test Checklist

- [ ] Login with admin / 1234
- [ ] Create an owner, pet, appointment, and visit
- [ ] Write SOAP notes on a visit
- [ ] Add a prescription and dispense it via `/pharmacy/`
- [ ] Upload a file attachment on a pet record
- [ ] Check notification bell shows count
- [ ] View service catalog at `/catalog/`
- [ ] Run manual backup at `/system/backup`
- [ ] Verify backup file appears in `data/backups/`
- [ ] Create an invoice and confirm CSV export works
- [ ] Check financial report period comparison at `/reports/financial/compare`
