"""
Demo seed script — populates the platform DB with realistic sample data.
Run:  python seed_demo.py
"""
import sqlite3, hashlib, os, random
from datetime import date, timedelta, datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "platform.db")
SALT    = "pah_platform_2026"

def _hash(pw): return hashlib.sha256(f"{SALT}{pw}".encode()).hexdigest()

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = OFF")

today = date.today()

# ── helpers ──────────────────────────────────────────────────────────────────
def d(offset=0):   return (today + timedelta(days=offset)).isoformat()
def dt(offset=0):  return (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d %H:%M:%S")
def rand_phone():  return f"010{random.randint(10000000, 99999999)}"

print("Seeding demo data …")

# ── STAFF ────────────────────────────────────────────────────────────────────
staff = [
    ("dr.sarah",  "Dr. Sarah Hassan",   "doctor",        "sarah@clinic.com"),
    ("dr.ahmed",  "Dr. Ahmed Nour",     "doctor",        "ahmed@clinic.com"),
    ("nurse.rana","Rana Mahmoud",       "nurse",         "rana@clinic.com"),
    ("recept.mai","Mai Khaled",         "reception",     "mai@clinic.com"),
    ("inv.omar",  "Omar Fathy",         "inventory_mgr", "omar@clinic.com"),
    ("fin.dina",  "Dina Mostafa",       "finance",       "dina@clinic.com"),
    ("grm.hana",  "Hana Samir",         "groomer",       "hana@clinic.com"),
    ("board.karim","Karim Ali",         "boarding_staff","karim@clinic.com"),
]
for uname, fname, role, email in staff:
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users(username,password_hash,full_name,email,role,is_active) VALUES(?,?,?,?,?,1)",
            (uname, _hash("demo1234"), fname, email, role))
    except: pass

# ── OWNERS & PETS ────────────────────────────────────────────────────────────
owners_data = [
    ("Ahmed Al-Rashidi",  "01012345678", "Dog",  "German Shepherd", "Rex",    "Male",   "2020-03-15", 28.5),
    ("Nour Khalil",       "01023456789", "Cat",  "Persian",         "Luna",   "Female", "2021-06-20", 4.2),
    ("Sara Hosny",        "01034567890", "Dog",  "Golden Retriever","Max",    "Male",   "2019-11-10", 32.0),
    ("Mohamed Farouk",    "01045678901", "Cat",  "Siamese",         "Miso",   "Female", "2022-01-05", 3.8),
    ("Layla Hassan",      "01056789012", "Dog",  "Poodle",          "Coco",   "Female", "2021-09-12", 6.5),
    ("Karim Mansour",     "01067890123", "Bird", "African Grey",    "Polly",  "Female", "2018-07-22", 0.4),
    ("Rania Ibrahim",     "01078901234", "Cat",  "British Shorthair","Oreo",  "Male",   "2020-12-01", 5.1),
    ("Tarek Soliman",     "01089012345", "Dog",  "Labrador",        "Buddy",  "Male",   "2020-05-18", 30.0),
    ("Dina Mostafa",      "01090123456", "Cat",  "Maine Coon",      "Simba",  "Male",   "2021-04-08", 6.8),
    ("Omar Sherif",       "01001234567", "Dog",  "Husky",           "Storm",  "Male",   "2019-08-25", 24.0),
    ("Heba Magdy",        "01112345678", "Cat",  "Russian Blue",    "Misty",  "Female", "2022-03-14", 4.0),
    ("Wael Fathi",        "01123456789", "Dog",  "Beagle",          "Snoop",  "Male",   "2020-10-30", 12.5),
    ("Amira Nabil",       "01134567890", "Bird", "Cockatiel",       "Tweety", "Female", "2021-01-19", 0.1),
    ("Sherif Adel",       "01145678901", "Dog",  "Rottweiler",      "Tank",   "Male",   "2019-06-05", 42.0),
    ("Mona Attia",        "01156789012", "Cat",  "Tabby",           "Whiskers","Female","2020-08-17", 3.5),
]

owner_ids = []
pet_ids   = []
for (fname, phone, species, breed, pname, sex, dob, weight) in owners_data:
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO owners(full_name,phone,whatsapp_phone,preferred_contact,marketing_consent,created_by) VALUES(?,?,?,'WhatsApp',1,'seed')",
            (fname, phone, phone))
        oid = cur.lastrowid or conn.execute("SELECT id FROM owners WHERE phone=?", (phone,)).fetchone()["id"]
    except:
        oid = conn.execute("SELECT id FROM owners WHERE phone=?", (phone,)).fetchone()["id"]
    owner_ids.append(oid)
    try:
        cur2 = conn.execute(
            "INSERT OR IGNORE INTO pets(owner_id,pet_name,species,breed,sex,dob,weight_kg,is_active) VALUES(?,?,?,?,?,?,?,1)",
            (oid, pname, species, breed, sex, dob, weight))
        pid = cur2.lastrowid or conn.execute("SELECT id FROM pets WHERE owner_id=? AND pet_name=?", (oid,pname)).fetchone()["id"]
    except:
        pid = conn.execute("SELECT id FROM pets WHERE owner_id=? AND pet_name=?", (oid,pname)).fetchone()["id"]
    pet_ids.append(pid)

# ── APPOINTMENTS ─────────────────────────────────────────────────────────────
doctors = ["Dr. Hatem El Khateeb", "Dr. Sarah Hassan", "Dr. Ahmed Nour"]
reasons = ["Annual checkup", "Vaccination", "Follow-up", "Skin issue", "Not eating well",
           "Limping", "Dental cleaning", "Post-surgery check", "Ear infection", "Eye discharge"]
statuses_appt = ["Scheduled","Scheduled","Scheduled","Confirmed","In Progress","Completed","Completed","Completed"]

for i, (oid, pid) in enumerate(zip(owner_ids, pet_ids)):
    offset = random.randint(-7, 7)
    appt_date = d(offset)
    appt_start = f"{random.randint(9,16):02d}:{random.choice(['00','15','30','45'])}"
    status = "Completed" if offset < 0 else ("In Progress" if offset == 0 else random.choice(["Scheduled","Confirmed"]))
    conn.execute(
        """INSERT OR IGNORE INTO appointments(owner_id,pet_id,doctor_name,appointment_type,priority,
           status,channel,appt_date,appt_start,reason,created_by)
           VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (oid, pid, random.choice(doctors), "Consultation", "Normal",
         status, random.choice(["Walk-in","Phone","WhatsApp"]),
         appt_date, appt_start, random.choice(reasons), "seed"))
    # Extra appointments for busy days
    if random.random() > 0.5:
        conn.execute(
            """INSERT OR IGNORE INTO appointments(owner_id,pet_id,doctor_name,appointment_type,priority,
               status,channel,appt_date,appt_start,reason,created_by)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (oid, pid, random.choice(doctors), "Vaccination", "Normal",
             "Completed", "Walk-in", d(random.randint(-30,-1)),
             f"{random.randint(9,17):02d}:00", "Vaccination due", "seed"))

# ── VISITS ───────────────────────────────────────────────────────────────────
diagnoses_list = [
    "Otitis externa", "Dermatitis", "Gastroenteritis", "Upper respiratory infection",
    "Conjunctivitis", "Hip dysplasia", "Dental disease", "Obesity", "Anxiety disorder",
    "Flea infestation", "Ringworm", "Urinary tract infection"
]
for i, (oid, pid) in enumerate(zip(owner_ids[:12], pet_ids[:12])):
    visit_date = d(random.randint(-60, -1))
    status = "Completed" if random.random() > 0.3 else "Open"
    cur = conn.execute(
        """INSERT INTO visits(owner_id,pet_id,doctor_name,visit_date,visit_type,status,
           chief_complaint,weight_kg,temp_c,heart_rate,notes,created_by)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (oid, pid, random.choice(doctors), visit_date, "Consultation", status,
         random.choice(reasons), round(random.uniform(3,35),1),
         round(random.uniform(37.5, 39.5),1), random.randint(60,120),
         "Patient examined. Treatment plan established.", "seed"))
    vid = cur.lastrowid
    # Diagnosis
    conn.execute(
        "INSERT INTO diagnoses(visit_id,pet_id,diagnosis,severity,created_by) VALUES(?,?,?,?,?)",
        (vid, pid, random.choice(diagnoses_list),
         random.choice(["Mild","Moderate","Severe"]), "seed"))

# ── VACCINATIONS ─────────────────────────────────────────────────────────────
vaccines = ["Rabies", "DHPP", "Bordetella", "Feline FVRCP", "FeLV", "Leptospirosis"]
for pid in pet_ids:
    for vac in random.sample(vaccines, 2):
        admin_date = d(random.randint(-365, -30))
        next_due   = d(random.randint(-14, 30))
        try:
            conn.execute(
                """INSERT INTO vaccinations(pet_id,vaccine_name,administered_by,administered_at,next_due_at,site)
                   VALUES(?,?,?,?,?,?)""",
                (pid, vac, random.choice(doctors), admin_date, next_due, "Subcutaneous"))
        except: pass

# ── INVENTORY ────────────────────────────────────────────────────────────────
items_data = [
    ("Amoxicillin 250mg", "Medications", "tablet",  12.5,  25.0, 1),
    ("Metronidazole 500mg","Medications","tablet",  18.0,  35.0, 1),
    ("Dexamethasone Inj", "Medications", "vial",    45.0,  90.0, 1),
    ("Cephalexin 500mg",  "Medications", "capsule", 22.0,  44.0, 1),
    ("Ivermectin 1%",     "Medications", "ml",       8.0,  20.0, 1),
    ("Rabies Vaccine",    "Vaccines",    "dose",    35.0,  80.0, 1),
    ("DHPP Vaccine",      "Vaccines",    "dose",    40.0,  90.0, 1),
    ("Feline FVRCP",      "Vaccines",    "dose",    38.0,  85.0, 1),
    ("Syringe 5ml",       "Consumables", "piece",    1.5,   3.5, 0),
    ("Gloves (box)",      "Consumables", "box",     25.0,  50.0, 0),
    ("IV Catheter 22G",   "Consumables", "piece",    8.0,  18.0, 0),
    ("Bandage Roll",      "Consumables", "roll",     5.0,  12.0, 0),
    ("Pet Shampoo 500ml", "Grooming Products","bottle",35.0, 70.0, 0),
    ("Ear Cleaner",       "Grooming Products","bottle",28.0, 60.0, 0),
    ("Royal Canin Dog",   "Pet Food",    "kg",      55.0, 110.0, 0),
]
item_ids = []
for (name, cat, unit, cost, sell, is_med) in items_data:
    cat_id = conn.execute("SELECT id FROM item_categories WHERE name=?", (cat,)).fetchone()
    cat_id = cat_id["id"] if cat_id else 1
    existing = conn.execute("SELECT id FROM items WHERE name=?", (name,)).fetchone()
    if existing:
        item_ids.append(existing["id"])
    else:
        cur = conn.execute(
            """INSERT INTO items(category_id,name,unit,cost_price,sell_price,reorder_level,is_medication,is_active)
               VALUES(?,?,?,?,?,10,?,1)""",
            (cat_id, name, unit, cost, sell, is_med))
        iid = cur.lastrowid
        item_ids.append(iid)
        # Add stock batch
        conn.execute(
            """INSERT INTO batches(item_id,warehouse_id,batch_number,expiry_date,quantity,unit_cost,received_by)
               VALUES(?,1,?,?,?,?,'seed')""",
            (iid, f"BATCH-{iid:03d}", d(random.randint(30,365)),
             random.randint(20,200), cost))

# ── SUPPLIERS ────────────────────────────────────────────────────────────────
suppliers_data = [
    ("MedVet Pharma",     "Khaled Saad",  "02012345678", "sales@medvet.com",   "Net 30"),
    ("VetSupply Egypt",   "Amr Ghaly",    "02023456789", "orders@vetsupply.eg","Net 15"),
    ("PharmaVet Co.",     "Dalia Nasser", "02034567890", "info@pharmvet.com",  "COD"),
    ("Animal Care Store", "Ramy Adel",    "02045678901", "shop@animalcare.eg", "Net 30"),
]
sup_ids = []
for (name, contact, phone, email, terms) in suppliers_data:
    existing = conn.execute("SELECT id FROM suppliers WHERE name=?", (name,)).fetchone()
    if existing:
        sup_ids.append(existing["id"])
    else:
        cur = conn.execute(
            "INSERT INTO suppliers(name,contact_name,phone,email,payment_terms,is_active) VALUES(?,?,?,?,?,1)",
            (name, contact, phone, email, terms))
        sup_ids.append(cur.lastrowid)

# ── PURCHASE ORDERS ──────────────────────────────────────────────────────────
po_statuses = ["Received","Received","Sent","Draft","Received"]
for i, (sid, status) in enumerate(zip(sup_ids[:3], po_statuses[:3])):
    po_date = d(random.randint(-45,-5))
    po_num  = f"PO-{today.year}-{(i+1):05d}"
    cur = conn.execute(
        """INSERT OR IGNORE INTO purchase_orders(po_number,supplier_id,order_date,status,total,notes,created_by)
           VALUES(?,?,?,?,?,?,?)""",
        (po_num, sid, po_date, status,
         round(random.uniform(500,5000),2),
         "Routine restocking order", "seed"))
    po_id = cur.lastrowid
    if po_id:
        # Add lines
        for item_id in random.sample(item_ids[:8], 3):
            qty = random.randint(10,50)
            unit_cost = round(random.uniform(10,80),2)
            conn.execute(
                "INSERT INTO po_lines(po_id,item_id,quantity,unit_cost,total) VALUES(?,?,?,?,?)",
                (po_id, item_id, qty, unit_cost, round(qty*unit_cost,2)))

# ── INVOICES ─────────────────────────────────────────────────────────────────
services = [
    ("Consultation",       200.0),
    ("Vaccination",        150.0),
    ("Laboratory Test",    300.0),
    ("Surgery",           1500.0),
    ("Grooming - Full",    350.0),
    ("X-Ray",              400.0),
    ("Dental Cleaning",    800.0),
    ("Boarding (per day)", 150.0),
]
inv_ids = []
for i, (oid, pid) in enumerate(zip(owner_ids, pet_ids)):
    inv_date = d(random.randint(-90, 0))
    num_services = random.randint(1, 3)
    chosen = random.sample(services, num_services)
    subtotal = sum(s[1] for s in chosen)
    disc_amt = round(subtotal * 0.05, 2) if random.random() > 0.7 else 0
    total    = round(subtotal - disc_amt, 2)
    paid     = total if random.random() > 0.25 else round(total * random.uniform(0, 0.8), 2)
    due      = round(total - paid, 2)
    inv_status = "Paid" if due == 0 else ("Partial" if paid > 0 else "Unpaid")
    inv_no   = f"INV-{today.year}-{(i+1):05d}"
    cur = conn.execute(
        """INSERT OR IGNORE INTO invoices(invoice_number,owner_id,pet_id,doctor_name,issue_date,
           status,subtotal,discount_amount,total,paid_amount,due_amount,created_by)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (inv_no, oid, pid, random.choice(doctors), inv_date,
         inv_status, subtotal, disc_amt, total, paid, due, "seed"))
    inv_id = cur.lastrowid
    if inv_id:
        inv_ids.append((inv_id, oid, paid))
        for svc_name, svc_price in chosen:
            conn.execute(
                "INSERT INTO invoice_lines(invoice_id,line_type,description,quantity,unit_price,total) VALUES(?,?,?,?,?,?)",
                (inv_id, "service", svc_name, 1, svc_price, svc_price))
        if paid > 0:
            conn.execute(
                "INSERT INTO payments(invoice_id,owner_id,amount,method,received_by) VALUES(?,?,?,?,?)",
                (inv_id, oid, paid, random.choice(["Cash","Card","Transfer"]), "seed"))

# ── EXPENSES ─────────────────────────────────────────────────────────────────
expense_data = [
    ("Rent",           "Monthly clinic rent",              8500.0),
    ("Utilities",      "Electricity & water",               950.0),
    ("Supplies",       "Office and medical consumables",    1200.0),
    ("Marketing",      "Social media advertising",          600.0),
    ("Maintenance",    "Equipment maintenance",             450.0),
    ("Cleaning",       "Cleaning service",                  350.0),
    ("Internet",       "Internet subscription",             250.0),
]
for i in range(3):  # 3 months
    for cat, desc, amt in expense_data:
        conn.execute(
            "INSERT INTO expenses(branch_id,category,description,amount,expense_date,created_by) VALUES(1,?,?,?,?,?)",
            (cat, desc, amt + random.uniform(-50,50), d(-30*i + random.randint(-5,0)), "seed"))

# ── GROOMING ─────────────────────────────────────────────────────────────────
grm_statuses = ["Completed","Completed","Scheduled","In Progress","Cancelled"]
svc_ids = [r["id"] for r in conn.execute("SELECT id FROM grooming_services LIMIT 4").fetchall()]
for i, (oid, pid) in enumerate(zip(owner_ids[:10], pet_ids[:10])):
    if not svc_ids: break
    bdate = d(random.randint(-30, 7))
    status = "Completed" if bdate < d(0) else "Scheduled"
    conn.execute(
        """INSERT INTO grooming_bookings(pet_id,owner_id,service_id,groomer_name,booking_date,status,notes)
           VALUES(?,?,?,?,?,?,?)""",
        (pid, oid, random.choice(svc_ids), "Hana Samir", bdate, status,
         "Regular grooming appointment"))

# ── BOARDING ─────────────────────────────────────────────────────────────────
room_ids = [r["id"] for r in conn.execute("SELECT id FROM boarding_rooms LIMIT 4").fetchall()]
boarding_data = [
    (owner_ids[0],  pet_ids[0],  d(-5),  d(2),   "Checked-in"),
    (owner_ids[1],  pet_ids[1],  d(-3),  d(1),   "Checked-in"),
    (owner_ids[2],  pet_ids[2],  d(-10), d(-3),  "Checked-out"),
    (owner_ids[3],  pet_ids[3],  d(1),   d(5),   "Booked"),
    (owner_ids[4],  pet_ids[4],  d(-7),  d(-1),  "Checked-out"),
]
for i, (oid, pid, ci, co, status) in enumerate(boarding_data):
    rid = room_ids[i % len(room_ids)] if room_ids else None
    conn.execute(
        """INSERT INTO boarding_bookings(pet_id,owner_id,room_id,check_in,check_out,
           feeding_instructions,status)
           VALUES(?,?,?,?,?,?,?)""",
        (pid, oid, rid, ci, co, "Standard diet, twice daily", status))

# ── LAB REQUESTS ─────────────────────────────────────────────────────────────
lab_tests = ["CBC", "Blood Chemistry", "Urinalysis", "Fecal Exam", "Skin Scraping",
             "Culture & Sensitivity", "Thyroid Panel", "X-Ray Chest"]
for pid, oid in list(zip(pet_ids[:8], owner_ids[:8])):
    vrow = conn.execute("SELECT id FROM visits WHERE pet_id=? LIMIT 1", (pid,)).fetchone()
    if not vrow: continue
    vid = vrow["id"]
    test = random.choice(lab_tests)
    status = random.choice(["Pending","In Progress","Completed","Completed"])
    cur = conn.execute(
        """INSERT INTO lab_requests(visit_id,pet_id,test_name,priority,status,requested_by)
           VALUES(?,?,?,?,?,?)""",
        (vid, pid, test, "Routine", status, random.choice(doctors)))
    if status == "Completed" and cur.lastrowid:
        conn.execute(
            "INSERT INTO lab_results(lab_request_id,pet_id,result_text,reviewed_by,reviewed_at) VALUES(?,?,?,?,?)",
            (cur.lastrowid, pid, f"Normal range. No significant findings.", random.choice(doctors), dt(-1)))

# ── WHATSAPP REMINDERS ────────────────────────────────────────────────────────
for i, (oid, pid) in enumerate(zip(owner_ids[:8], pet_ids[:8])):
    conn.execute(
        """INSERT INTO reminders(owner_id,pet_id,reminder_type,message,channel,scheduled_for,status)
           VALUES(?,?,'appointment','Your pet appointment is tomorrow. Please confirm.','WhatsApp',?,?)""",
        (oid, pid, dt(random.randint(-2, 5)),
         "Sent" if random.random() > 0.4 else "Pending"))

conn.commit()
conn.close()

print("DONE! Demo data seeded successfully!")
print(f"   - {len(owners_data)} owners & pets")
print(f"   - Appointments, visits, diagnoses")
print(f"   - Vaccinations, lab requests")
print(f"   - {len(items_data)} inventory items with stock")
print(f"   - {len(suppliers_data)} suppliers + purchase orders")
print(f"   - {len(owners_data)} invoices with payments")
print(f"   - Grooming bookings & boarding stays")
print(f"   - 8 staff users (password: demo1234)")
print()
print("Login: admin / 1234")
