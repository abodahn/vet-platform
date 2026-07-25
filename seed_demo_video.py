"""
Demo Video Seed Script â€” Aleefy Platform (PostgreSQL)
Populates the database with realistic demo data for sales videos.
Run: python seed_demo_video.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from datetime import date, timedelta

import app as _app
_flask_app = _app.create_app()
_ctx = _flask_app.app_context()
_ctx.push()

from models.database import get_db
conn = get_db()

def d(n): return (date.today() + timedelta(days=n)).isoformat()

def insert(sql, params):
    """INSERT ... RETURNING id â€” returns new row id."""
    row = conn.execute(sql + " RETURNING id", params).fetchone()
    conn.commit()
    return row["id"] if row else None

def get1(sql, params=()):
    return conn.execute(sql, params).fetchone()

print("Seeding demo data for Aleefy sales video...")
print(f"Connected to PostgreSQL DB\n")

# â”€â”€ 1. OWNERS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
owners_raw = [
    ("Ahmed Al-Rashidi",   "Ø£Ø­Ù…Ø¯ Ø§Ù„Ø±Ø§Ø´Ø¯ÙŠ",   "0501234567", "ahmed@email.com",   "Villa 12, Al Nakheel, Riyadh",    450),
    ("Sara Hassan",        "Ø³Ø§Ø±Ø© Ø­Ø³Ù†",        "0559876543", "sara@email.com",    "Apt 7, Zahra Tower, Dubai",       820),
    ("Mohammed Al-Zahrani","Ù…Ø­Ù…Ø¯ Ø§Ù„Ø²Ù‡Ø±Ø§Ù†ÙŠ",   "0533445566", "mzahrani@mail.com", "Flat 3, Al Hamra, Jeddah",        200),
    ("Fatima Al-Khateeb",  "ÙØ§Ø·Ù…Ø© Ø§Ù„Ø®Ø·ÙŠØ¨",   "0544332211", "fatima@email.com",  "House 5, Al Rawdah, Cairo",      1200),
    ("Khalid Ibrahim",     "Ø®Ø§Ù„Ø¯ Ø¥Ø¨Ø±Ø§Ù‡ÙŠÙ…",   "0522113344", "khalid@email.com",  "Street 9, Maadi, Cairo",          350),
    ("Layla Nasser",       "Ù„ÙŠÙ„Ù‰ Ù†Ø§ØµØ±",       "0566778899", "layla@email.com",   "Block 14, Al Amal, Kuwait",       600),
    ("Omar Suleiman",      "Ø¹Ù…Ø± Ø³Ù„ÙŠÙ…Ø§Ù†",      "0577889900", "omar@email.com",    "Villa 22, Green Zone, Abu Dhabi", 150),
    ("Rania Mahmoud",      "Ø±Ø§Ù†ÙŠØ§ Ù…Ø­Ù…ÙˆØ¯",     "0511223344", "rania@email.com",   "Apt 15, Marina Tower, Dubai",     750),
]
owner_ids = []
for name, name_ar, phone, email, addr, lp in owners_raw:
    row = get1("SELECT id FROM owners WHERE phone=%s", (phone,))
    if row:
        owner_ids.append(row["id"])
        print(f"  [exists] {name}")
    else:
        oid = insert("""
            INSERT INTO owners (full_name, full_name_ar, phone, email, address, loyalty_balance)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (name, name_ar, phone, email, addr, lp))
        owner_ids.append(oid)
        print(f"  [created] {name}")

# â”€â”€ 2. PETS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
pets_raw = [
    # oi, name, species, breed, sex, dob, kg, color, chip, neut, allergy, chronic, ins, pol_num, pol_exp
    (0,"Max",    "Dog",  "German Shepherd","Male",  "2020-03-15",28.5,"Black & Tan","981000012345",1,"",         "Hip dysplasia",     "AXA Pet","AXA-2024-00123",d(200)),
    (0,"Luna",   "Cat",  "Persian",       "Female","2021-07-20", 4.2,"White",       "981000012346",1,"Chicken",  "",                  "","",               ""),
    (1,"Bella",  "Dog",  "Golden Retriever","Female","2019-11-08",26.0,"Golden",    "981000012347",1,"",         "Diabetes mellitus", "MetLife","MET-PET-5543",  d(180)),
    (1,"Rocky",  "Dog",  "Rottweiler",    "Male",  "2022-01-12",42.0,"Black",       "981000012348",0,"Penicillin","",                "","",               ""),
    (2,"Mia",    "Cat",  "Siamese",       "Female","2020-09-03", 3.8,"Cream & Brown","981000012349",1,"",        "",                  "","",               ""),
    (3,"Leo",    "Dog",  "Labrador",      "Male",  "2018-05-22",32.0,"Yellow",      "981000012350",1,"",         "Arthritis, Obesity","AXA Pet","AXA-2024-00891",d(-30)),
    (3,"Coco",   "Rabbit","Holland Lop",  "Female","2023-02-14", 1.8,"Brown & White","",           0,"",         "",                  "","",               ""),
    (4,"Tiger",  "Cat",  "Maine Coon",    "Male",  "2021-04-17", 6.5,"Orange Tabby","981000012351",0,"Fish",     "",                  "","",               ""),
    (5,"Daisy",  "Dog",  "Beagle",        "Female","2022-08-30", 9.5,"Tricolor",    "981000012352",1,"",         "",                  "Allianz","ALZ-22-778899",d(25)),
    (6,"Simba",  "Cat",  "Bengal",        "Male",  "2020-12-01", 5.2,"Spotted Brown","981000012353",1,"",        "CKD Stage 2",       "","",               ""),
    (7,"Charlie","Dog",  "Poodle",        "Male",  "2023-06-11", 5.8,"White",       "981000012354",1,"",         "",                  "","",               ""),
    (7,"Nemo",   "Fish", "Clownfish",     "Male",  "2023-01-01",0.05,"Orange & White","",          0,"",         "",                  "","",               ""),
]
pet_ids = []
for row_data in pets_raw:
    oi,name,species,breed,sex,dob,kg,color,chip,neut,allergy,chronic,ins,pol,pol_exp = row_data
    oid = owner_ids[oi]
    row = get1("SELECT id FROM pets WHERE pet_name=%s AND owner_id=%s", (name, oid))
    if row:
        pet_ids.append(row["id"]); continue
    pid = insert("""
        INSERT INTO pets (owner_id,pet_name,species,breed,sex,dob,weight_kg,color,
                          microchip_id,neutered,allergies,chronic_conditions,
                          insurance_provider,policy_number,policy_expiry)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (oid,name,species,breed,sex,dob,kg,color,chip,neut,allergy,chronic,
          ins or None, pol or None, pol_exp or None))
    pet_ids.append(pid)
    print(f"  [created] {name} ({species})")
print(f"  {len(pet_ids)} pets ready\n")

# â”€â”€ 3. APPOINTMENTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating appointments...")
appts_raw = [
    # pi, oi, day, time, type, status, doctor
    (0,0, 0,  "09:00","Wellness Check",     "Confirmed","Dr. Hatem"),
    (2,1, 0,  "10:30","Follow-up",          "Confirmed","Dr. Hatem"),
    (4,2, 0,  "11:00","Vaccination",        "Confirmed","Dr. Hatem"),
    (7,4, 0,  "14:00","Dental Cleaning",    "Confirmed","Dr. Hatem"),
    (8,5, 0,  "15:30","Spay/Neuter Consult","Confirmed","Dr. Hatem"),
    (1,0, 1,  "09:30","Vaccination",        "Confirmed","Dr. Hatem"),
    (3,1, 1,  "11:00","Weight Check",       "Confirmed","Dr. Hatem"),
    (5,3, 2,  "10:00","Arthritis Follow-up","Confirmed","Dr. Hatem"),
    (9,6, 2,  "14:30","Kidney Check",       "Confirmed","Dr. Hatem"),
    (10,7,3,  "09:00","Grooming Consult",   "Confirmed","Dr. Hatem"),
    (0,0,-3,  "10:00","Wellness Check",     "Completed","Dr. Hatem"),
    (2,1,-5,  "11:30","Vaccination",        "Completed","Dr. Hatem"),
    (5,3,-7,  "09:00","Hip X-Ray",          "Completed","Dr. Hatem"),
    (8,5,-2,  "14:00","Annual Checkup",     "Completed","Dr. Hatem"),
    (4,2,-1,  "16:00","Deworming",          "Completed","Dr. Hatem"),
]
created_appts = 0
for pi,oi,day,t,atype,status,doc in appts_raw:
    if pi >= len(pet_ids) or oi >= len(owner_ids): continue
    ad = d(day)
    if get1("SELECT id FROM appointments WHERE pet_id=%s AND appt_date=%s AND appt_start=%s",
            (pet_ids[pi], ad, t)): continue
    insert("""
        INSERT INTO appointments (pet_id,owner_id,appt_date,appt_start,
                                   appointment_type,status,doctor_name,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (pet_ids[pi],owner_ids[oi],ad,t,atype,status,doc,f"{atype} for {pets_raw[pi][1]}"))
    created_appts += 1
print(f"  {created_appts} appointments created\n")

# â”€â”€ 4. VISITS + DIAGNOSES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating visits...")
visits_raw = [
    # pi,oi,day,kg,complaint,diagnosis,status,doctor
    (0,0,-3,28.5,"Annual wellness check, owner reports occasional limping",
     "Hip dysplasia â€” mild progression","Completed","Dr. Hatem"),
    (2,1,-5,26.1,"Diabetes monitoring, lethargy for 2 days",
     "Diabetes mellitus â€” adjust insulin dose","Completed","Dr. Hatem"),
    (5,3,-7,33.2,"Difficulty walking, joint pain in right hind leg",
     "Osteoarthritis Grade 2 â€” start NSAID therapy","Completed","Dr. Hatem"),
    (8,5,-2, 9.6,"Annual checkup, owner wants vaccination update",
     "Healthy â€” vaccinations updated","Completed","Dr. Hatem"),
    (9,6,-1, 5.1,"Increased thirst, decreased appetite",
     "CKD Stage 2 â€” dietary management","Completed","Dr. Hatem"),
    (4,2,-1, 3.9,"Sneezing, mild nasal discharge",
     "Upper respiratory infection â€” antibiotics prescribed","Completed","Dr. Hatem"),
    (1,0, 0, 4.3,"Routine vaccination and checkup",
     "Healthy â€” vaccines administered","Open","Dr. Hatem"),
    (7,4, 0, 6.6,"Dental cleaning consultation, bad breath",
     "Periodontal disease Grade 1 â€” cleaning recommended","Open","Dr. Hatem"),
]
created_v = 0
for pi,oi,day,kg,complaint,diag,status,doc in visits_raw:
    if pi >= len(pet_ids): continue
    vd = d(day)
    if get1("SELECT id FROM visits WHERE pet_id=%s AND visit_date=%s",
            (pet_ids[pi], vd)): continue
    vid = insert("""
        INSERT INTO visits (pet_id,owner_id,visit_date,weight_kg,chief_complaint,
                            status,doctor_name,visit_type)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, (pet_ids[pi],owner_ids[oi],vd,kg,complaint,status,doc,"OPD"))
    if vid and status == "Completed":
        try:
            insert("""
                INSERT INTO diagnoses (visit_id,diagnosis,severity)
                VALUES (%s,%s,%s)
            """, (vid, diag, "Moderate"))
        except Exception: pass
    created_v += 1
print(f"  {created_v} visits created\n")

# â”€â”€ 5. INVOICES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating invoices...")
invoices_raw = [
    (0,-3, [("Annual Wellness Exam",1,350),("Rabies Vaccine",1,120),("Hip X-Ray",1,450)], True),
    (1,-5, [("Diabetes Consultation",1,400),("Insulin Glargine 10ml",2,280),("Blood Glucose Test",1,180)], True),
    (3,-7, [("Orthopedic Consultation",1,500),("X-Ray (Hip+Spine)",2,500),("Meloxicam 1mg x30",1,95)], True),
    (5,-2, [("Annual Wellness Exam",1,350),("7-in-1 Vaccine",1,180),("Flea/Tick Treatment",1,90)], True),
    (6,-1, [("Nephrology Consultation",1,450),("Kidney Panel (Blood)",1,320),("Renal Diet Food 3kg",1,185)], False),
    (2,-1, [("Consultation",1,250),("Doxycycline 100mg x10",1,75),("Nebulization x3",3,120)], False),
    (4,-14,[("Dental Consultation",1,300),("Dental Cleaning",1,800),("Antibiotic Post-op",1,120)], True),
    (7,-20,[("Annual Checkup",1,350),("Core Vaccines",1,200),("Grooming",1,150)], True),
]
created_inv = 0
for oi,day,lines,paid in invoices_raw:
    if oi >= len(owner_ids): continue
    oid  = owner_ids[oi]
    idate = d(day)
    inum  = f"INV2026{oi+1:02d}{abs(day):02d}"
    if get1("SELECT id FROM invoices WHERE invoice_number=%s", (inum,)): continue
    total = sum(q*p for _,q,p in lines)
    status = "Paid" if paid else "Unpaid"
    inv_id = insert("""
        INSERT INTO invoices (owner_id,invoice_number,issue_date,total,due_amount,status,notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (oid, inum, idate, total, 0 if paid else total, status, "Demo invoice"))
    if inv_id:
        for desc,qty,price in lines:
            insert("""
                INSERT INTO invoice_lines (invoice_id,description,quantity,unit_price,total)
                VALUES (%s,%s,%s,%s,%s)
            """, (inv_id, desc, qty, price, qty*price))
        if paid:
            insert("""
                INSERT INTO payments (invoice_id,owner_id,amount,method,received_at,notes)
                VALUES (%s,%s,%s,%s,%s,%s)
            """, (inv_id, oid, total, "Card", idate+" 10:00:00","Demo payment"))
    created_inv += 1
print(f"  {created_inv} invoices created\n")

# â”€â”€ 6. VACCINATIONS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating vaccination records...")
vacc_raw = [
    (0,"Rabies",d(-180),d(185)),
    (0,"DHPP",d(-365),d(0)),
    (2,"Bordetella",d(-90),d(275)),
    (2,"Rabies",d(-180),d(185)),
    (4,"FVRCP",d(-270),d(95)),
    (8,"Rabies",d(-180),d(185)),
    (5,"Rabies",d(-365),d(-5)),
    (5,"DHPP",d(-200),d(165)),
    (9,"FVRCP",d(-120),d(245)),
    (1,"FVRCP",d(-30),d(335)),
    (10,"Rabies",d(-60),d(305)),
]
created_vacc = 0
for pi,vname,given,next_due in vacc_raw:
    if pi >= len(pet_ids): continue
    if get1("SELECT id FROM vaccinations WHERE pet_id=%s AND vaccine_name=%s AND administered_at=%s",
            (pet_ids[pi],vname,given)): continue
    insert("""
        INSERT INTO vaccinations (pet_id,vaccine_name,administered_at,next_due_at,administered_by)
        VALUES (%s,%s,%s,%s,%s)
    """, (pet_ids[pi],vname,given,next_due,"Dr. Hatem"))
    created_vacc += 1
print(f"  {created_vacc} vaccination records created\n")

# â”€â”€ 7. LAB REQUESTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating lab requests...")
# lab_requests requires a visit_id — use first available visit per pet
labs_raw = [
    (5,"CBC + Chemistry Panel","Pending","High"),
    (9,"Kidney Function Panel","Completed","Normal"),
    (2,"Glucose Curve","In Progress","Normal"),
    (0,"Hip Radiograph Analysis","Completed","Normal"),
    (7,"Dental X-Ray","Pending","Normal"),
]
created_labs = 0
for pi,test,status,priority in labs_raw:
    if pi >= len(pet_ids): continue
    if get1("SELECT id FROM lab_requests WHERE pet_id=%s AND test_name=%s",
            (pet_ids[pi],test)): continue
    visit_row = get1("SELECT id FROM visits WHERE pet_id=%s LIMIT 1", (pet_ids[pi],))
    if not visit_row: continue
    insert("""
        INSERT INTO lab_requests (pet_id,visit_id,test_name,status,priority,requested_by)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (pet_ids[pi],visit_row["id"],test,status,priority,"Dr. Hatem"))
    created_labs += 1
print(f"  {created_labs} lab requests created\n")

# â”€â”€ 8. GROOMING â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating grooming bookings...")
try:
    for svc,price in [("Full Bath & Blow Dry",150),("Haircut & Style",200),
                       ("Nail Trim",50),("Full Groom Package",350)]:
        if not get1("SELECT id FROM grooming_services WHERE name=%s",(svc,)):
            insert("INSERT INTO grooming_services (name,price,duration_min) VALUES (%s,%s,60)",(svc,price))
    srow = get1("SELECT id FROM grooming_services WHERE name=%s",("Full Groom Package",))
    if srow:
        for pi,oi,day in [(10,7,0),(8,5,1),(1,0,2)]:
            if pi >= len(pet_ids) or oi >= len(owner_ids): continue
            if not get1("SELECT id FROM grooming_bookings WHERE pet_id=%s AND booking_date=%s",
                        (pet_ids[pi],d(day))):
                insert("""
                    INSERT INTO grooming_bookings (pet_id,owner_id,service_id,booking_date,status)
                    VALUES (%s,%s,%s,%s,%s)
                """, (pet_ids[pi],owner_ids[oi],srow["id"],d(day),"Confirmed"))
    print("  Grooming bookings created")
except Exception as e:
    print(f"  Grooming skipped: {e}")

# â”€â”€ 9. BOARDING â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating boarding data...")
try:
    rrow = get1("SELECT id FROM boarding_rooms LIMIT 1")
    if rrow:
        for pi,oi,ci,co,status in [(3,1,d(-2),d(3),"Active"),(0,0,d(-5),d(-1),"Checked Out")]:
            if pi >= len(pet_ids) or oi >= len(owner_ids): continue
            if not get1("SELECT id FROM boarding_bookings WHERE pet_id=%s AND check_in=%s",
                        (pet_ids[pi],ci)):
                insert("""
                    INSERT INTO boarding_bookings (pet_id,owner_id,room_id,check_in,
                                                   check_out,status)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (pet_ids[pi],owner_ids[oi],rrow["id"],ci,co,status))
    print("  Boarding bookings created")
except Exception as e:
    print(f"  Boarding skipped: {e}")

# â”€â”€ 10. LOW STOCK INVENTORY â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
print("Creating inventory alerts...")
try:
    cat = get1("SELECT id FROM item_categories LIMIT 1")
    wh  = get1("SELECT id FROM warehouses LIMIT 1")
    if cat and wh:
        for name,sku,qty,reorder in [
            ("Amoxicillin 500mg Tabs x100","AMX500",8,20),
            ("Insulin Glargine 10ml","INS001",3,10),
            ("IV Fluid 0.9% NaCl 1L","IVF001",12,30),
            ("Rabies Vaccine Dose","RAB001",7,15),
        ]:
            if not get1("SELECT id FROM items WHERE sku=%s",(sku,)):
                item_id = insert("""
                    INSERT INTO items (name,sku,category_id,reorder_level,unit,is_active)
                    VALUES (%s,%s,%s,%s,'Unit',1)
                """, (name,sku,cat["id"],reorder))
                if item_id:
                    insert("""
                        INSERT INTO batches (item_id,warehouse_id,batch_number,quantity,
                                             unit_cost,expiry_date)
                        VALUES (%s,%s,%s,%s,%s,%s)
                    """, (item_id,wh["id"],f"BT{sku}01",qty,25.0,d(90)))
    print("  Low-stock inventory created")
except Exception as e:
    print(f"  Inventory skipped: {e}")

conn.close()
print("\n" + "="*55)
print("  Demo data seeded successfully!")
print("="*55)
print(f"  Owners        : {len(owner_ids)}")
print(f"  Patients      : {len(pet_ids)} (dogs, cats, rabbit, fish)")
print(f"  Appointments  : {created_appts} (today + upcoming + past)")
print(f"  Visits        : {created_v} (open + completed)")
print(f"  Invoices      : {created_inv} (paid + unpaid)")
print(f"  Vaccinations  : {created_vacc} (due + overdue)")
print(f"  Lab requests  : {created_labs}")
print("  + Grooming, Boarding, Low-stock alerts")
print("="*55)
print("\nReady to record your demo video!")
