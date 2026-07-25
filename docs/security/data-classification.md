# Data Classification Policy — Aleefy Platform

**Owner:** Dr. Hatem El Khateeb  
**Last reviewed:** 2026-05-23

---

## Classification Levels

| Level | Label | Description | Examples |
|-------|-------|-------------|---------|
| L1 | **Public** | Safe to share publicly | Service names, clinic hours, general info |
| L2 | **Internal** | Staff use only | Staff schedules, internal reports, stock levels |
| L3 | **Confidential** | Restricted to relevant role | Patient medical records, invoices, prescriptions |
| L4 | **Secret** | Named individuals or admins only | Credentials, API keys, DSN, session secrets |

---

## Data Inventory by Table

| Table | Classification | Contains PII? | Retention | Access Roles |
|-------|---------------|---------------|-----------|-------------|
| `owners` | L3 | Yes — name, phone, email | Indefinite (medical records law) | All clinical roles |
| `pets` | L3 | Indirect (via owner) | Indefinite | All clinical roles |
| `visits` | L3 | Yes — medical data | 7 years minimum | Doctor, Nurse, Branch Manager+ |
| `diagnoses` | L3 | Yes — health data | 7 years minimum | Doctor, Nurse |
| `prescriptions` | L3 | Yes — health + contact | 7 years minimum | Doctor, Pharmacist |
| `vaccinations` | L3 | Yes — health data | 7 years minimum | Doctor, Nurse |
| `appointments` | L3 | Yes — name, phone | 3 years | All clinical + Reception |
| `invoices` | L3 | Yes — financial + contact | 7 years (tax law) | Finance, Branch Manager+ |
| `payments` | L3 | Yes — financial | 7 years | Finance, Branch Manager+ |
| `staff` | L3 | Yes — employee data | Duration of employment + 5 years | HR, Super Admin |
| `users` | L4 | Yes — credentials (hashed) | Duration of employment | Super Admin only |
| `audit_log` | L3 | Yes — IP address, actions | 2 years | Super Admin, Clinic Owner |
| `ai_conversations` | L3 | Yes — medical queries | 1 year | Own user only |
| `attachments` (files) | L3 | Yes — potentially | 7 years | Role-based (see _ACCESS map) |
| `service_catalog` | L1 | No | Indefinite | Public API |
| `inventory_items` | L2 | No | Indefinite | Inventory, Manager+ |
| `contact_messages` | L3 | Yes — name, phone, email | 1 year | Reception, Manager+ |

---

## Handling Rules by Classification

### L1 — Public
- May be served via public API without authentication
- No special handling required

### L2 — Internal
- Requires authenticated session
- No encryption-at-rest beyond database-level
- Do not export to personal devices

### L3 — Confidential
- Requires authenticated session with appropriate role
- Do not log content to application logs (log IDs only)
- Exports must be password-protected
- Do not cache in browser (use `Cache-Control: no-store` on sensitive API responses)
- Patient medical data covered by Egyptian health data regulations

### L4 — Secret
- Must be stored as environment variables only
- Must never appear in source code, logs, or error messages
- Must never be transmitted unencrypted
- Rotate on: staff departure, suspected compromise, annually
- Access limited to named system administrator

---

## Personal Data (PII) Under Egyptian Law

The platform processes personal data of pet owners and staff including:
- Full name, phone number, email address
- Location (branch/governorate)
- Payment history
- Medical-adjacent data (pet health linked to owner)

**Data Controller:** Dr. Hatem El Khateeb / clinic legal entity  
**Retention:** Follow Egyptian health records and tax requirements  
**Subject Rights:** Owners may request correction or deletion of contact data (not medical records)

---

## Notes

- All L3/L4 data is transmitted over HTTPS (TLS 1.2+)
- Database at rest: Neon.tech provides AES-256 encryption at rest
- Backups: stored locally in `data/backups/` — **ensure backup directory has restricted filesystem permissions**
- File uploads: stored in `data/uploads/` — **restrict directory to application user only**
