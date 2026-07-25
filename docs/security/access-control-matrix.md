# Access Control Matrix — Aleefy Platform RBAC

**Last reviewed:** 2026-05-23

---

## Role Definitions

| Role | Code | Description |
|------|------|-------------|
| Super Admin | `super_admin` | Full system access, manages all branches and users |
| Clinic Owner | `clinic_owner` | Business owner — full access except system config |
| Branch Manager | `branch_manager` | Full access within their branch |
| Doctor | `doctor` | Clinical access — visits, diagnoses, prescriptions |
| Nurse | `nurse` | Clinical support — visits read/update, vitals |
| Reception | `reception` | Appointments, CRM, basic invoicing |
| Inventory Manager | `inventory_mgr` | Stock management, procurement |
| Pharmacist | `pharmacist` | Pharmacy dispensing, prescription view |
| Finance | `finance` | Invoices, payments, financial reports |
| HR | `hr` | Staff records, attendance, payroll |

---

## Module Access Matrix

Legend: **W** = Write, **R** = Read, **-** = No access

| Module | super_admin | clinic_owner | branch_mgr | doctor | nurse | reception | inventory_mgr | pharmacist | finance | hr |
|--------|-------------|-------------|------------|--------|-------|-----------|--------------|------------|---------|-----|
| **Auth / Users** | W | R | - | - | - | - | - | - | - | - |
| **CRM (Owners/Pets)** | W | W | W | W | R | W | - | R | R | - |
| **Appointments** | W | W | W | W | W | W | - | - | - | - |
| **Clinical / Visits** | W | W | W | W | W | - | - | - | - | - |
| **Diagnoses** | W | W | W | W | R | - | - | - | - | - |
| **Prescriptions** | W | W | W | W | R | - | - | W | - | - |
| **Pharmacy** | W | W | W | R | - | - | - | W | - | - |
| **Inventory** | W | W | W | R | R | - | W | R | R | - |
| **Finance / Invoices** | W | W | W | - | - | W | - | - | W | - |
| **Payments** | W | W | W | - | - | W | - | - | W | - |
| **HR / Staff** | W | W | R | - | - | - | - | - | - | W |
| **Attendance** | W | W | W | - | - | - | - | - | - | W |
| **Payroll** | W | W | - | - | - | - | - | - | - | W |
| **Reports** | W | W | W | R | - | - | R | - | W | R |
| **System / Backup** | W | R | - | - | - | - | - | - | - | - |
| **WhatsApp** | W | W | W | - | - | W | - | - | - | - |
| **AI Assistant** | W | W | W | W | W | R | R | W | R | - |
| **Uploads** | W | W | W | W | W | W | W | - | W | - |
| **Settings** | W | W | W | - | - | - | - | - | - | - |
| **Migration** | W | - | - | - | - | - | - | - | - | - |
| **Petsy (public widget)** | W | W | W | - | - | - | - | - | - | - |

---

## Upload Entity Type Access

| Entity Type | Roles with Read/Write Access |
|------------|------------------------------|
| `pet` | super_admin, clinic_owner, branch_manager, doctor, nurse, reception |
| `visit` | super_admin, clinic_owner, branch_manager, doctor, nurse |
| `staff` | super_admin, clinic_owner, branch_manager, hr |
| `supplier` | super_admin, clinic_owner, branch_manager, inventory_mgr, finance |
| `invoice` | super_admin, clinic_owner, branch_manager, finance, reception |
| `lab` | super_admin, clinic_owner, branch_manager, doctor, nurse |

---

## AI Assistant Context Access

| Endpoint | Access Control |
|----------|---------------|
| `/ai/` (chat UI) | All authenticated users |
| `/ai/chat` | All authenticated users (rate-limited) |
| `/ai/context/visit/<id>` | Clinical roles only: super_admin, clinic_owner, branch_manager, doctor, nurse |
| `/ai/insights` | All authenticated users |
| `/ai/health-alerts` | All authenticated users |
| `/ai/pet-summary/<id>` | All authenticated users |
| `/ai/discharge-instructions/<id>` | All authenticated users |
| `/ai/outbreak-radar` | All authenticated users |
| `/ai/drug-interactions` | All authenticated users |
| `/ai/draft-message` | All authenticated users |
| `/ai/nl-report` | All authenticated users |
| `/ai/analyze-photo` | All authenticated users |

**Note:** The `/ai/context/visit/<id>` IDOR guard is the critical control here. It prevents a reception user or non-clinical role from accessing full medical records via the AI context endpoint.

---

## Password Policy

| Requirement | Value |
|------------|-------|
| Minimum length | 12 characters |
| Uppercase letters | At least 1 |
| Lowercase letters | At least 1 |
| Digits | At least 1 |
| Special characters | At least 1 |
| Maximum failed attempts | 5 |
| Lockout duration | 15 minutes |
| Session idle timeout | 60 minutes |

---

## Business Decisions Required

The following access control decisions require Dr. Hatem's input:

1. Should doctors be restricted to their branch's patients only, or may they view all branches? (Currently: branch check is a soft guard that allows access if branch schema doesn't match — needs business decision.)
2. Should the `reception` role be able to view AI chat history of other users? (Currently: each user sees only their own history.)
3. Should `nurse` role have write access to diagnoses, or read-only? (Currently: read-only — change if nurses record provisional diagnoses.)
