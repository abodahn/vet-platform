# Incident Response Plan — Aleefy Platform

**Owner:** Dr. Hatem El Khateeb  
**Last reviewed:** 2026-05-23

---

## 1. Incident Classification

| Severity | Description | Response Time |
|---------|-------------|--------------|
| P1 — Critical | Active breach, data exfiltration, system down | Immediate (< 1h) |
| P2 — High | Suspected unauthorized access, credentials compromised | Same day (< 4h) |
| P3 — Medium | Failed attack attempts, policy violation | Next business day |
| P4 — Low | Security configuration gap, non-critical finding | Within 1 week |

---

## 2. Incident Types and Playbooks

### 2.1 Suspected Credential Compromise (P1/P2)

**Indicators:**
- Admin reports password no longer works
- Unusual login in audit log (unexpected time, IP, country)
- API key showing unexpected usage in provider dashboard

**Response:**
1. **Contain** — Immediately revoke the compromised credential:
   - Database password: change in Neon.tech dashboard
   - Platform secret key: generate new key, update Koyeb env var, restart app
   - AI API key: regenerate in provider dashboard
   - Wapilot token: regenerate in Wapilot dashboard
2. **Assess** — Check audit log:
   ```sql
   SELECT * FROM audit_log
   WHERE created_at > NOW() - INTERVAL '48 hours'
   ORDER BY created_at DESC;
   ```
3. **Identify scope** — Which tables/records may have been accessed?
4. **Force logout** — Restart the application to invalidate all active sessions
5. **Reset** — Force password reset for affected user accounts
6. **Document** — Record timeline, credentials affected, records potentially accessed

---

### 2.2 Unauthorized Access Attempt (P2/P3)

**Indicators:**
- Rate limiter triggering repeatedly from same IP
- Failed login attempts in audit log for admin accounts
- Unexpected 403 errors in application logs

**Response:**
1. **Identify** — Query audit log for the suspicious IP:
   ```sql
   SELECT ip, COUNT(*) attempts, MAX(created_at) last_attempt
   FROM audit_log
   WHERE action = 'login_failed'
     AND created_at > NOW() - INTERVAL '1 hour'
   GROUP BY ip ORDER BY attempts DESC;
   ```
2. **Block** — If under active attack, add Cloudflare IP block rule
3. **Monitor** — Watch for successful logins from suspicious IPs
4. **Assess** — If any successful logins found, escalate to P1

---

### 2.3 Suspected Data Breach (P1)

**Indicators:**
- Patient data found outside the system
- Staff reports seeing others' data
- SQL injection attempt in logs

**Response:**
1. **Immediate containment:**
   - Take application offline if active exfiltration is confirmed
   - Take a read-only snapshot of the database: `pg_dump` to a separate file
   - Do NOT modify any data until forensic snapshot is complete
2. **Assess scope:**
   - Which tables were accessed? Check PostgreSQL query logs if enabled
   - How many patient records? Which fields?
3. **Legal notification:**
   - If patient personal data (name, phone, medical) was exposed:
     - Notify affected patients as soon as practicable
     - Notify Egyptian Data Protection Authority within 72 hours (if applicable)
4. **Remediate:**
   - Patch the vulnerability
   - Rotate all credentials
   - Force password reset for all users
5. **Review:**
   - Conduct post-incident review within 1 week
   - Update this plan if gaps are found

---

### 2.4 Ransomware / Server Compromise (P1)

**Response:**
1. **Isolate** — Take the server offline immediately (Koyeb: stop service)
2. **Do NOT pay** — Never pay ransom
3. **Restore from backup:**
   - Identify the last clean backup in `data/backups/`
   - Restore to a fresh database instance
   - Redeploy the application from git (from a known-clean commit)
4. **Investigate** — How did the attacker gain access? Check:
   - Git history for leaked secrets
   - Dependency vulnerabilities (`pip audit`)
   - Upload directory for web shells
5. **Harden** — Address the root cause before bringing the system back online

---

## 3. Evidence Collection

When an incident is suspected, collect the following BEFORE any remediation:

```bash
# Application logs
journalctl -u gunicorn --since "2 hours ago" > incident_app.log

# Database audit log
psql $POSTGRES_DSN -c "COPY (SELECT * FROM audit_log WHERE created_at > NOW() - INTERVAL '48 hours') TO STDOUT CSV HEADER" > incident_audit.csv

# Active sessions at time of incident
psql $POSTGRES_DSN -c "SELECT * FROM sessions" > incident_sessions.csv
```

Preserve all evidence in a separate secure location before making any changes.

---

## 4. Communication

### Internal
- Notify Dr. Hatem El Khateeb immediately (P1/P2)
- Brief clinical staff if patient data may be affected

### External (if patient data is involved)
- Patients: via WhatsApp/phone call to affected individuals
- Regulator: Egyptian Data Protection Authority (if applicable under current law)
- Partners: Notify any third-party systems (Wapilot, Neon.tech) if their credentials are involved

---

## 5. Post-Incident Review

Within 1 week of a P1 or P2 incident:

1. Timeline of events (when did the incident start? when detected? when contained?)
2. Root cause analysis
3. What data was accessed or exfiltrated?
4. What controls failed?
5. What new controls were implemented?
6. Update this incident response plan
7. Update the security checklist in SECURITY.md

---

## 6. Contact Information

| Role | Contact |
|------|---------|
| System Owner | Dr. Hatem El Khateeb |
| Hosting (Koyeb) | https://app.koyeb.com — support@koyeb.com |
| Database (Neon.tech) | https://console.neon.tech — support@neon.tech |
| AI Provider | Per provider dashboard |
| WhatsApp (Wapilot) | Per Wapilot dashboard |

---

## 7. Testing

This plan should be tested annually with a tabletop exercise:
- Scenario: "An admin account's password was found in a credential dump online"
- Walk through steps 2.1, verify contacts are reachable, verify backup restore works
- Document any gaps found and update this plan
