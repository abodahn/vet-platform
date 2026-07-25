#!/usr/bin/env python3
"""
HR & Users Dummy Data Seed Script
Populates: staff, shifts, attendance (45 days), leave, performance,
           warnings, certifications, overtime, notes, salary grades.

Run:  cd C:/vet/platform && py seed_hr.py
"""

import psycopg2
import psycopg2.extras
import hashlib
import random
from datetime import date, timedelta

DSN   = "postgresql://waslny_app:WaslnyApp12345@127.0.0.1:5432/waslny_admin"
SALT  = "pah_platform_2026"
TODAY = date.today()

def _hash(pw):
    return hashlib.sha256(f"{SALT}{pw}".encode()).hexdigest()

def d(offset=0):
    return (TODAY + timedelta(days=offset)).isoformat()

def rand_phone():
    prefix = random.choice(["010", "011", "012", "015"])
    return f"{prefix}{random.randint(10000000, 99999999)}"

print("=" * 55)
print("  Aleefy HR Seed Script")
print("=" * 55)

conn = psycopg2.connect(DSN)
conn.autocommit = False
cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
print("Connected to PostgreSQL.\n")

# ─────────────────────────────────────────────────────────────────────────────
# 1. BRANCHES
# ─────────────────────────────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*) AS c FROM branches WHERE is_active=1")
if cur.fetchone()["c"] == 0:
    cur.execute("""
        INSERT INTO branches (name, name_ar, phone, address, is_active) VALUES
        ('Main Branch',       'الفرع الرئيسي',    '0222345678', 'Cairo, Nasr City',   1),
        ('Heliopolis Branch', 'فرع مصر الجديدة', '0223456789', 'Cairo, Heliopolis',  1)
    """)
    conn.commit()
    print("[1/10] Branches created.")
else:
    print("[1/10] Branches already exist — skipped.")

cur.execute("SELECT id FROM branches WHERE is_active=1 ORDER BY id")
branch_ids = [r["id"] for r in cur.fetchall()]
if not branch_ids:
    branch_ids = [None]

# ─────────────────────────────────────────────────────────────────────────────
# 2. SHIFTS
# ─────────────────────────────────────────────────────────────────────────────
cur.execute("SELECT COUNT(*) AS c FROM shifts WHERE is_active=1")
if cur.fetchone()["c"] == 0:
    cur.execute("""
        INSERT INTO shifts (name, name_ar, start_time, end_time, days_of_week, break_minutes, color, is_active) VALUES
        ('Morning Shift', 'وردية الصباح', '08:00', '16:00', '1,2,3,4,5',   30, '#3b82f6', 1),
        ('Evening Shift', 'وردية المساء', '16:00', '24:00', '1,2,3,4,5,6', 30, '#8b5cf6', 1),
        ('Weekend Shift', 'وردية الويكند','09:00', '17:00', '6,7',         30, '#f59e0b', 1)
    """)
    conn.commit()
    print("[2/10] Shifts created.")
else:
    print("[2/10] Shifts already exist — skipped.")

cur.execute("SELECT id FROM shifts WHERE is_active=1 ORDER BY id")
shift_ids = [r["id"] for r in cur.fetchall()]

# ─────────────────────────────────────────────────────────────────────────────
# 3. STAFF MEMBERS
# ─────────────────────────────────────────────────────────────────────────────
# (username, full_name, full_name_ar, role, job_title, contract_type,
#  hire_offset_days, gender, dob_offset_years, national_id, email, branch_idx)
staff_data = [
    ("dr.ahmed.hassan",  "Dr. Ahmed Hassan",  "د. أحمد حسن",     "doctor",        "Senior Veterinarian",  "Full-time",  -730, "Male",   35, "29001011234567", "ahmed.hassan@aleefyclinic.com",  0),
    ("dr.sara.ali",      "Dr. Sara Ali",      "د. سارة علي",      "doctor",        "Veterinary Surgeon",   "Full-time",  -365, "Female", 32, "29202041234568", "sara.ali@aleefyclinic.com",      0),
    ("dr.omar.sayed",    "Dr. Omar Sayed",    "د. عمر سيد",       "doctor",        "Veterinarian",         "Part-time",  -180, "Male",   28, "29408061234569", "omar.sayed@aleefyclinic.com",    1),
    ("nurse.rana",       "Rana Mahmoud",      "رنا محمود",        "nurse",         "Head Nurse",           "Full-time",  -540, "Female", 30, "29611091234570", "rana.mahmoud@aleefyclinic.com",  0),
    ("nurse.karim",      "Karim Ali",         "كريم علي",         "nurse",         "Veterinary Nurse",     "Full-time",  -200, "Male",   26, "29803111234571", "karim.ali@aleefyclinic.com",     0),
    ("recept.mai",       "Mai Khaled",        "مي خالد",          "reception",     "Front Desk Officer",   "Full-time",  -400, "Female", 27, "29912141234572", "mai.khaled@aleefyclinic.com",    0),
    ("recept.youssef",   "Youssef Ibrahim",   "يوسف إبراهيم",     "reception",     "Receptionist",         "Probation",   -60, "Male",   23, "30103161234573", "youssef@aleefyclinic.com",       1),
    ("pharma.dina",      "Dina Mostafa",      "دينا مصطفى",       "pharmacist",    "Clinical Pharmacist",  "Full-time",  -600, "Female", 31, "29301081234574", "dina.mostafa@aleefyclinic.com",  0),
    ("inv.fady",         "Fady Samir",        "فادي سمير",        "inventory_mgr", "Inventory Manager",    "Full-time",  -480, "Male",   33, "29007051234575", "fady.samir@aleefyclinic.com",    0),
    ("grm.hana",         "Hana Samir",        "هنا سمير",         "groomer",       "Senior Groomer",       "Full-time",  -300, "Female", 29, "29509071234576", "hana.samir@aleefyclinic.com",    1),
    ("board.tarek",      "Tarek Soliman",     "طارق سليمان",      "boarding_staff","Boarding Supervisor",  "Contract",    -90, "Male",   25, "30105021234577", "tarek@aleefyclinic.com",         1),
    ("fin.nour",         "Nour Hassan",       "نور حسن",          "finance",       "Finance Officer",      "Full-time",  -500, "Female", 34, "29006031234578", "nour.hassan@aleefyclinic.com",   0),
]

inserted_users = []
skipped = 0
for i, (uname, fname, fname_ar, role, job_title, ctype,
        hire_off, gender, dob_years, national_id, email, branch_idx) in enumerate(staff_data):

    branch_id  = branch_ids[branch_idx % len(branch_ids)]
    hire_date  = d(hire_off)
    dob        = (TODAY - timedelta(days=dob_years * 365)).isoformat()

    cur.execute("SELECT id FROM users WHERE username = %s", (uname,))
    row = cur.fetchone()
    if row:
        uid = row["id"]
        skipped += 1
    else:
        cur.execute("""
            INSERT INTO users (
                username, password_hash, full_name, full_name_ar, email, phone,
                role, branch_id, is_active, job_title, contract_type, hire_date,
                national_id, gender, dob, emergency_contact, emergency_phone
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (uname, _hash("demo1234"), fname, fname_ar, email, rand_phone(),
              role, branch_id, job_title, ctype, hire_date,
              national_id, gender, dob,
              f"Family of {fname.split()[-1]}", rand_phone()))
        uid = cur.fetchone()["id"]

    inserted_users.append((uid, uname, fname, role, i))

conn.commit()
created = len(inserted_users) - skipped
print(f"[3/10] Staff: {created} created, {skipped} already existed  ({len(inserted_users)} total)")

user_ids  = [u[0] for u in inserted_users]
admin_uid = user_ids[0]   # Dr. Ahmed — acts as approver / reviewer

# ─────────────────────────────────────────────────────────────────────────────
# 4. SHIFT ASSIGNMENTS
# ─────────────────────────────────────────────────────────────────────────────
assigned = 0
for uid, _, _, _, idx in inserted_users:
    s_id = shift_ids[idx % len(shift_ids)]
    cur.execute("""
        SELECT id FROM staff_shifts
        WHERE user_id=%s AND (effective_to IS NULL OR effective_to >= %s)
    """, (uid, TODAY.isoformat()))
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO staff_shifts (user_id, shift_id, effective_from) VALUES (%s,%s,%s)
        """, (uid, s_id, d(-700)))
        assigned += 1

conn.commit()
print(f"[4/10] Shift assignments: {assigned} created")

# ─────────────────────────────────────────────────────────────────────────────
# 5. LEAVE TYPES
# ─────────────────────────────────────────────────────────────────────────────
leave_types_data = [
    ("Annual Leave",    "إجازة سنوية",       21, 1, "#6366f1"),
    ("Sick Leave",      "إجازة مرضية",        7, 1, "#ef4444"),
    ("Emergency Leave", "إجازة طارئة",        3, 1, "#f59e0b"),
    ("Unpaid Leave",    "إجازة بدون مرتب",   14, 0, "#6b7280"),
]
leave_type_ids = {}
for lname, lname_ar, days, is_paid, color in leave_types_data:
    cur.execute("SELECT id FROM leave_types WHERE name=%s", (lname,))
    row = cur.fetchone()
    if row:
        leave_type_ids[lname] = row["id"]
    else:
        cur.execute("""
            INSERT INTO leave_types (name, name_ar, days_per_year, is_paid, color, is_active)
            VALUES (%s,%s,%s,%s,%s,1) RETURNING id
        """, (lname, lname_ar, days, is_paid, color))
        leave_type_ids[lname] = cur.fetchone()["id"]

conn.commit()
print(f"[5/10] Leave types: {len(leave_type_ids)} ready")

# ─────────────────────────────────────────────────────────────────────────────
# 6. LEAVE BALANCES
# ─────────────────────────────────────────────────────────────────────────────
year = TODAY.year
for uid, *_ in inserted_users:
    for lname, _, days, _, _ in leave_types_data:
        lt_id = leave_type_ids[lname]
        used  = round(random.uniform(0, days * 0.4), 1)
        rem   = round(days - used, 1)
        cur.execute("""
            INSERT INTO leave_balances (user_id, leave_type_id, year, allocated, used, remaining)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id, leave_type_id, year) DO NOTHING
        """, (uid, lt_id, year, days, used, rem))

conn.commit()
print(f"[6/10] Leave balances: {len(inserted_users) * len(leave_types_data)} records")

# ─────────────────────────────────────────────────────────────────────────────
# 7. LEAVE REQUESTS
# ─────────────────────────────────────────────────────────────────────────────
leave_requests = [
    (0, "Annual Leave",    d(-20), d(-18), "Approved", "Family vacation",      3),
    (1, "Sick Leave",      d(-10), d(-9),  "Approved", "Flu and fever",        2),
    (2, "Emergency Leave", d(-5),  d(-5),  "Approved", "Family emergency",     1),
    (3, "Annual Leave",    d(3),   d(7),   "Pending",  "Wedding ceremony",     5),
    (4, "Sick Leave",      d(2),   d(2),   "Pending",  "Medical appointment",  1),
    (5, "Annual Leave",    d(-30), d(-28), "Rejected", "Short notice",         3),
    (6, "Unpaid Leave",    d(10),  d(12),  "Pending",  "Personal matters",     3),
    (7, "Annual Leave",    d(-45), d(-42), "Approved", "Training abroad",      4),
    (8, "Sick Leave",      d(-15), d(-15), "Approved", "Back pain",            1),
]
for (staff_idx, ltype, start, end, status, reason, days_req) in leave_requests:
    if staff_idx >= len(user_ids):
        continue
    uid   = user_ids[staff_idx]
    lt_id = leave_type_ids[ltype]
    cur.execute("SELECT username, full_name FROM users WHERE id=%s", (uid,))
    urow  = cur.fetchone()
    cur.execute("""
        INSERT INTO leave_requests
            (user_id, username, full_name, leave_type_id, leave_type_name,
             start_date, end_date, days_requested, reason, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (uid, urow["username"], urow["full_name"], lt_id, ltype,
          start, end, days_req, reason, status))

conn.commit()
print(f"[7/10] Leave requests: {len(leave_requests)} records")

# ─────────────────────────────────────────────────────────────────────────────
# 8. ATTENDANCE RECORDS  (last 45 calendar days, weekdays only)
# ─────────────────────────────────────────────────────────────────────────────
att_created = 0
for day_offset in range(-44, 1):
    work_date = TODAY + timedelta(days=day_offset)
    if work_date.weekday() >= 5:      # skip Fri/Sat (Egyptian weekend = Fri+Sat → use >=4)
        continue
    wds = work_date.isoformat()

    for uid, uname, fname, _, _ in inserted_users:
        cur.execute("SELECT id FROM attendance_records WHERE user_id=%s AND work_date=%s", (uid, wds))
        if cur.fetchone():
            continue

        status = random.choices(
            ["Present", "Present", "Late", "Absent", "On Leave"],
            weights=[65, 10, 15, 7, 3]
        )[0]

        check_in = check_out = hours_worked = None
        if status in ("Present",):
            h = random.randint(7, 8)
            m = random.randint(0, 30)
            check_in    = f"{h:02d}:{m:02d}"
            check_out   = f"{h+8:02d}:{random.randint(0,59):02d}"
            hours_worked = round(8.0 + random.uniform(-0.3, 1.0), 1)
        elif status == "Late":
            check_in    = f"09:{random.randint(15, 59):02d}"
            check_out   = f"17:{random.randint(0,  30):02d}"
            hours_worked = round(7.0 + random.uniform(0, 1.5), 1)

        cur.execute("""
            INSERT INTO attendance_records
                (user_id, username, full_name, work_date, status, check_in, check_out, hours_worked)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (uid, uname, fname, wds, status, check_in, check_out, hours_worked))
        att_created += 1

conn.commit()
print(f"[8/10] Attendance: {att_created} records (45 days × {len(inserted_users)} staff)")

# ─────────────────────────────────────────────────────────────────────────────
# 9. PERFORMANCE REVIEWS
# ─────────────────────────────────────────────────────────────────────────────
reviews_data = [
    (0, "2026-Q1", 5, "Excellent clinical skills, thorough with every patient",
       "Could improve documentation speed",          "Achieve 100% digital records by Q3",     "Top performer this quarter — nominated for award"),
    (1, "2026-Q1", 4, "Strong surgical skills, calm under pressure",
       "Owner communication can be more detailed",   "Lead one training session for junior vets","Great potential for senior role"),
    (3, "2026-Q1", 4, "Exceptional patient care, strong team player",
       "Time management during peak hours",          "Complete advanced nursing certification",   "Consistently praised by clients"),
    (5, "2025-Q4", 3, "Good customer service skills",
       "Appointment scheduling efficiency needs work","Reduce no-show rate by 15% in Q2",        "Performance improving steadily"),
    (7, "2026-Q1", 5, "Flawless inventory control, zero stockouts",
       "None significant",                           "Implement automated reorder alerts",       "Best inventory manager in 3 years"),
    (1, "2025-Q4", 4, "Solid surgical technique",
       "Needs more client follow-up calls",          "Shadow senior vet for complex cases",      "Consistent performer"),
    (0, "2025-Q4", 4, "Strong leadership and mentoring of junior staff",
       "Occasionally overloaded — delegate more",   "Build mentorship programme for Q2",        "Dr. Ahmed continues to lead by example"),
]
for (staff_idx, period, rating, strengths, improvements, goals, comments) in reviews_data:
    if staff_idx >= len(user_ids):
        continue
    cur.execute("""
        INSERT INTO performance_reviews
            (user_id, reviewer_id, period, rating, strengths, improvements,
             goals, comments, status, reviewed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'Submitted',%s)
    """, (user_ids[staff_idx], admin_uid, period, rating,
          strengths, improvements, goals, comments, d(-15)))

conn.commit()
print(f"[9/10] Performance reviews: {len(reviews_data)} created")

# ─────────────────────────────────────────────────────────────────────────────
# 10. WARNINGS · CERTIFICATIONS · OVERTIME · NOTES · SALARIES
# ─────────────────────────────────────────────────────────────────────────────

# ── Warnings ─────────────────────────────────────────────────────────────────
warnings_data = [
    (6, "Verbal",        "Repeated tardiness — 3 instances in one month",    "Counselled and placed on attendance watch",     -35),
    (4, "Written",       "Left patient area without handover to colleague",  "Written warning issued, incident documented",   -20),
    (9, "Verbal",        "Dress code violation — incorrect uniform worn",    "Reminded of clinic policy, acknowledged",       -60),
    (2, "Verbal",        "Missed mandatory training session without notice", "Informal warning, rescheduled training",        -15),
]
for (staff_idx, wtype, reason, action, days_ago) in warnings_data:
    if staff_idx >= len(user_ids):
        continue
    cur.execute("""
        INSERT INTO staff_warnings
            (user_id, issued_by, warning_type, reason, action_taken, issued_date)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (user_ids[staff_idx], admin_uid, wtype, reason, action, d(days_ago)))

# ── Certifications ────────────────────────────────────────────────────────────
certs_data = [
    (0, "DVM License",              "Egyptian Veterinary Syndicate", "EGY-VET-2021-4521", d(-365*3),   d(365)),
    (0, "Orthopedic Surgery Cert.", "Cairo University",              "CU-ORTH-2023-0112", d(-365),     d(365*3)),
    (1, "DVM License",              "Egyptian Veterinary Syndicate", "EGY-VET-2022-6712", d(-365*2),   d(365*2)),
    (1, "Emergency Care (WSAVA)",   "WSAVA",                         "WSAVA-EMG-2024-033",d(-200),     d(365+150)),
    (3, "Veterinary Nursing Lic.",  "Egyptian Nursing Syndicate",    "NURS-2020-7821",    d(-365*4),   d(180)),
    (7, "Pharmacy License",         "Egyptian Pharmacy Syndicate",   "PHARM-2019-3344",   d(-365*5),   d(55)),
    (7, "Cold Chain Certification", "WHO Egypt",                     "WHO-CC-2023-9901",  d(-365),     d(365*2)),
    (8, "CIPS Supply Chain Cert.",  "CIPS UK",                       "CIPS-2022-11231",   d(-365*2),   d(365)),
    (11,"CPA Certificate",          "ICPAI",                         "CPA-2021-4421",     d(-365*3),   d(365*2)),
    (4, "BLS Certification",        "Red Crescent Egypt",            "BLS-2024-0078",     d(-120),     d(245)),
]
for (staff_idx, cert_name, issued_by, cert_no, issue_date, expiry_date) in certs_data:
    if staff_idx >= len(user_ids):
        continue
    cur.execute("""
        INSERT INTO staff_certifications
            (user_id, cert_name, issued_by, cert_number, issue_date, expiry_date, status)
        VALUES (%s,%s,%s,%s,%s,%s,'Active')
    """, (user_ids[staff_idx], cert_name, issued_by, cert_no, issue_date, expiry_date))

# ── Overtime log ──────────────────────────────────────────────────────────────
ot_data = [
    (0,  -5,  3.0, "Emergency surgery — complex case after hours",  "Approved", admin_uid),
    (1,  -8,  2.5, "Complex dental procedure ran overtime",         "Approved", admin_uid),
    (3,  -3,  4.0, "Covered evening shift during staff shortage",   "Approved", admin_uid),
    (4,  -1,  2.0, "Post-operative monitoring — ICU patient",       "Pending",  None),
    (5,  -7,  1.5, "Month-end reception reports",                   "Pending",  None),
    (9,  -2,  3.0, "Large group grooming session — holiday prep",   "Approved", admin_uid),
    (10, -12, 2.5, "Holiday boarding overflow weekend",             "Approved", admin_uid),
    (0,  -15, 3.5, "Specialist consultation — emergency cover",     "Approved", admin_uid),
    (7,  -4,  2.0, "Controlled drug audit and reconciliation",      "Approved", admin_uid),
    (2,  -9,  1.5, "Emergency consultation — after-hours call",     "Pending",  None),
]
for (staff_idx, days_ago, hours, reason, status, approver) in ot_data:
    if staff_idx >= len(user_ids):
        continue
    cur.execute("""
        INSERT INTO overtime_log (user_id, work_date, hours, reason, status, approved_by)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (user_ids[staff_idx], d(days_ago), hours, reason, status, approver))

# ── Staff notes (private HR) ──────────────────────────────────────────────────
notes_data = [
    (0,  "Nominated for Senior Veterinarian promotion in Q3 2026. Exceptional client feedback scores."),
    (1,  "Interested in orthopedic surgery specialization. Approved training budget request."),
    (3,  "On track for Head Nurse promotion. Nursing License expiring in ~6 months — send renewal reminder."),
    (6,  "Probation ends 2026-09-10. Punctuality has improved since verbal warning in June."),
    (7,  "Pharmacy License expires in ~55 days. Renewal reminder sent on last review date."),
    (10, "Contract renewal due in 90 days. Discuss full-time conversion with clinic owner."),
    (11, "Completed advanced Excel & accounting software training. Strong candidate for Finance Manager."),
]
for (staff_idx, note_text) in notes_data:
    if staff_idx >= len(user_ids):
        continue
    cur.execute("""
        INSERT INTO staff_notes (user_id, author_id, note, is_private) VALUES (%s,%s,%s,TRUE)
    """, (user_ids[staff_idx], admin_uid, note_text))

conn.commit()
print(f"[10/10] Warnings: {len(warnings_data)} · Certs: {len(certs_data)} · OT: {len(ot_data)} · Notes: {len(notes_data)}")

# ─────────────────────────────────────────────────────────────────────────────
# 11. SALARY GRADES + 3 MONTHS PAYROLL  (safe — skips if table missing)
# ─────────────────────────────────────────────────────────────────────────────
role_grade = {
    "doctor":        (25000, 150),
    "nurse":         (12000, 75),
    "reception":     ( 9000, 50),
    "pharmacist":    (18000, 100),
    "inventory_mgr": (14000, 80),
    "groomer":       (10000, 60),
    "boarding_staff":( 9500, 55),
    "finance":       (16000, 90),
    "branch_manager":(22000, 130),
    "support_admin": (11000, 65),
}
try:
    for role, (basic, ot_rate) in role_grade.items():
        cur.execute("""
            INSERT INTO salary_grades (role, basic_salary, overtime_rate)
            VALUES (%s,%s,%s) ON CONFLICT (role) DO NOTHING
        """, (role, basic, ot_rate))
    conn.commit()

    sal_created = 0
    for uid, _, _, role, _ in inserted_users:
        basic, ot_rate = role_grade.get(role, (10000, 60))
        for mb in range(1, 4):              # last 3 months
            m = (TODAY.month - mb - 1) % 12 + 1
            y = TODAY.year if (TODAY.month - mb) > 0 else TODAY.year - 1
            ot_hrs    = round(random.uniform(0, 8), 1)
            allowances= round(random.uniform(500, 2000), 2)
            deductions= round(random.uniform(200, 800), 2)
            gross     = round(basic + allowances + ot_hrs * ot_rate, 2)
            net       = round(gross - deductions, 2)
            status    = "Paid" if mb > 1 else "Approved"
            cur.execute("""
                INSERT INTO salaries
                    (user_id, period_year, period_month, basic_salary,
                     allowances, overtime_hours, overtime_rate, gross, deductions, net, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (uid, y, m, basic, allowances, ot_hrs, ot_rate,
                  gross, deductions, net, status))
            sal_created += 1

    conn.commit()
    print(f"       Salary grades + {sal_created} payroll records created.")
except Exception as e:
    conn.rollback()
    print(f"       Salary skipped (table may not exist yet): {e}")

# ─────────────────────────────────────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────────────────────────────────────
cur.close()
conn.close()

print()
print("=" * 55)
print("  Seed complete!")
print("=" * 55)
print(f"  Staff members   : {len(inserted_users)}")
print(f"  Shifts          : {len(shift_ids)}")
print(f"  Attendance days : 45 (weekdays)")
print(f"  Leave requests  : {len(leave_requests)}")
print(f"  Perf. reviews   : {len(reviews_data)}")
print(f"  Warnings        : {len(warnings_data)}")
print(f"  Certifications  : {len(certs_data)}")
print(f"  Overtime entries: {len(ot_data)}")
print(f"  HR notes        : {len(notes_data)}")
print()
print("  Login with any staff username, password = demo1234")
print("  e.g.  dr.ahmed.hassan / demo1234")
print("        nurse.rana       / demo1234")
print("        recept.mai       / demo1234")
