#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Demo-showcase seed — a believable Egyptian small-animal clinic.

Builds ~6 months of connected history so every dashboard, chart and report in
the platform has something to show, and so the module-to-module workflows are
visible: appointment -> visit -> diagnosis -> prescription -> stock deduction
-> invoice -> payment.

Everything here is SYNTHETIC. No real owner, pet, phone number or clinical
record is used or derived from one.

Usage
-----
    python scripts/seed/demo_showcase.py --db data/demo.db
    python scripts/seed/demo_showcase.py --db data/demo.db --wipe   # reset only

Re-running is the reset: the script clears its own scope first, so counts are
identical on every run.

Safety
------
The script REFUSES to touch the configured default database
(config.Config.DATABASE_PATH) unless --force is passed. A demo must never be
the thing that eats a developer's working data.
"""
from __future__ import annotations

import argparse
from urllib.parse import unquote, urlparse
import os
import sys
import unicodedata
from datetime import date, datetime, timedelta
from random import Random

_HERE = os.path.dirname(os.path.abspath(__file__))
_PLATFORM = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _PLATFORM not in sys.path:
    sys.path.insert(0, _PLATFORM)

import models.database as db  # noqa: E402
from config import Config     # noqa: E402

SEED = 20260728               # fixed -> identical dataset on every run
DEMO_EMAIL_DOMAIN = "demo.aleefy.local"
DEMO_PASSWORD = "Demo@1234"

# Invisible bidi / zero-width marks. Arabic pasted from anywhere carries them,
# and two visually identical names then compare unequal forever after.
_INVISIBLE = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x200E, 0x200F,
     0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
     0x2066, 0x2067, 0x2068, 0x2069, 0xFEFF]
)


def ar(text: str) -> str:
    """Normalise Arabic (or any) text for storage: NFC, no invisible marks."""
    return unicodedata.normalize("NFC", str(text).translate(_INVISIBLE)).strip()


# ── Tables this script owns, child-before-parent ──────────────────────────────
# Wiped on every run. Anything not listed is left alone.
WIPE_ORDER = [
    # payment_events -> payment_intents -> invoices. Children first, because
    # PostgreSQL enforces the foreign key and refuses to delete a parent that is
    # still referenced. SQLite let this pass only because a fresh file had no
    # rows to violate it — re-seeding a database that had ever taken a payment
    # failed with ForeignKeyViolation on the real engine.
    "payment_events", "payment_intents",
    "payments", "invoice_lines", "invoices",
    "prescription_items", "prescriptions",
    "lab_results", "lab_requests",
    "diagnoses", "treatment_plans", "vaccinations", "surgeries", "followups",
    "imaging_studies",
    "inpatient_meds", "inpatient_rounds", "inpatient_stays",
    "grooming_bookings", "boarding_bookings",
    "visits", "appointments",
    "reminders", "whatsapp_log", "loyalty_points", "notifications",
    "pet_attachments", "pets", "owner_phones", "owners",
    "ps_order_items", "ps_orders", "ps_stock_movements", "ps_products", "ps_categories",
    "dispensing_log", "stock_movements", "batches",
    "reorder_rules", "dosage_templates",
    "po_lines", "purchase_orders", "items", "suppliers",
    "expenses", "daily_closings",
    "attendance_records", "leave_requests", "leave_balances", "overtime_log",
    "performance_reviews", "staff_warnings", "staff_certifications", "staff_notes",
    "salaries", "salary_grades",
    "audit_log",
]


# ── Source data (synthetic) ───────────────────────────────────────────────────

# (latin, arabic, district_latin, district_arabic)
OWNERS = [
    ("Ahmed Abdelrahman",  "أحمد عبد الرحمن",  "Nasr City",       "مدينة نصر"),
    ("Mona Saad",          "منى سعد",           "Maadi",           "المعادي"),
    ("Mostafa El-Gohary",  "مصطفى الجوهري",     "Heliopolis",      "مصر الجديدة"),
    ("Nourhan Ashraf",     "نورهان أشرف",       "Dokki",           "الدقي"),
    ("Karim Abdelaziz",    "كريم عبد العزيز",   "Zamalek",         "الزمالك"),
    ("Salma Ibrahim",      "سلمى إبراهيم",      "6th of October",  "السادس من أكتوبر"),
    ("Hossam Farid",       "حسام فريد",         "Sheikh Zayed",    "الشيخ زايد"),
    ("Yasmine Adel",       "ياسمين عادل",       "New Cairo",       "القاهرة الجديدة"),
    ("Tarek Zaki",         "طارق زكي",          "Mohandessin",     "المهندسين"),
    ("Heba Mansour",       "هبة منصور",         "Shubra",          "شبرا"),
    ("Amr Gaber",          "عمرو جابر",         "Nasr City",       "مدينة نصر"),
    ("Dina Refaat",        "دينا رفعت",         "Maadi",           "المعادي"),
    ("Sherif Kamal",       "شريف كمال",         "Helwan",          "حلوان"),
    ("Rania Sobhy",        "رانيا صبحي",        "Faisal",          "فيصل"),
    ("Waleed Nagy",        "وليد ناجي",         "Ain Shams",       "عين شمس"),
    ("Nada Elshamy",       "ندى الشامي",        "Manial",          "المنيل"),
    ("Islam Badawy",       "إسلام بدوي",        "Haram",           "الهرم"),
    ("Sara Fouad",         "سارة فؤاد",         "Nasr City",       "مدينة نصر"),
    ("Mahmoud Elsayed",    "محمود السيد",       "Obour City",      "مدينة العبور"),
    ("Aya Hegazy",         "آية حجازي",         "Rehab City",      "مدينة الرحاب"),
    ("Khaled Anwar",       "خالد أنور",         "Madinaty",        "مدينتي"),
    ("Passant Wagdy",      "بسنت وجدي",         "Heliopolis",      "مصر الجديدة"),
    ("Ehab Serag",         "إيهاب سراج",        "Downtown",        "وسط البلد"),
    ("Marwa Sultan",       "مروة سلطان",        "Giza",            "الجيزة"),
    ("Youssef Halim",      "يوسف حليم",         "Garden City",     "جاردن سيتي"),
    ("Menna Elhossary",    "منة الحصري",        "Nasr City",       "مدينة نصر"),
    ("Ramy Hafez",         "رامي حافظ",         "Maadi",           "المعادي"),
    ("Doaa Elmasry",       "دعاء المصري",       "Imbaba",          "إمبابة"),
    ("Mohab Roshdy",       "مهاب رشدي",         "New Cairo",       "القاهرة الجديدة"),
    ("Laila Fahmy",        "ليلى فهمي",         "Zamalek",         "الزمالك"),
    ("Bassem Wahba",       "باسم وهبة",         "Shorouk City",    "مدينة الشروق"),
    ("Hala Elkholy",       "هالة الخولي",       "Agouza",          "العجوزة"),
    ("Omar Shaheen",       "عمر شاهين",         "Nasr City",       "مدينة نصر"),
    ("Nesma Talaat",       "نسمة طلعت",         "Hadayek Helwan",  "حدائق حلوان"),
    ("Fady Nabil",         "فادي نبيل",         "Shubra El-Kheima","شبرا الخيمة"),
    ("Ghada Elberry",      "غادة البري",        "Maadi",           "المعادي"),
    ("Seif Eldin Mokhtar", "سيف الدين مختار",   "Heliopolis",      "مصر الجديدة"),
    ("Reem Abdelhady",     "ريم عبد الهادي",    "Mokattam",        "المقطم"),
    ("Adham Riad",         "أدهم رياض",         "Sheikh Zayed",    "الشيخ زايد"),
    ("Habiba Selim",       "حبيبة سليم",        "Dokki",           "الدقي"),
    ("Mazen Okasha",       "مازن عكاشة",        "Nasr City",       "مدينة نصر"),
    ("Sondos Elnahas",     "سندس النحاس",       "Giza",            "الجيزة"),
    ("Hany Attia",         "هاني عطية",         "Mohandessin",     "المهندسين"),
    ("Nermeen Zahran",     "نرمين زهران",       "New Cairo",       "القاهرة الجديدة"),
    ("Zeyad Elhelw",       "زياد الحلو",        "Maadi",           "المعادي"),
    ("Farida Kassem",      "فريدة قاسم",        "Heliopolis",      "مصر الجديدة"),
    ("Sameh Lotfy",        "سامح لطفي",         "Ain Shams",       "عين شمس"),
    ("Alaa Elmenshawy",    "علاء المنشاوي",     "Haram",           "الهرم"),
    ("Toqa Elsherbiny",    "تقى الشربيني",      "Nasr City",       "مدينة نصر"),
    ("Ziad Barakat",       "زياد بركات",        "Rehab City",      "مدينة الرحاب"),
    ("Malak Elsawy",       "ملك الصاوي",        "Zamalek",         "الزمالك"),
    ("Hazem Elkady",       "حازم القاضي",       "6th of October",  "السادس من أكتوبر"),
    ("Aisha Darwish",      "عائشة درويش",       "Maadi",           "المعادي"),
    ("Sherine Ragab",      "شيرين رجب",         "Faisal",          "فيصل"),
    ("Moataz Elbanna",     "معتز البنا",        "Downtown",        "وسط البلد"),
    ("Yara Elmoallem",     "يارا المعلم",       "Mokattam",        "المقطم"),
    ("Kareem Elshafei",    "كريم الشافعي",      "New Cairo",       "القاهرة الجديدة"),
    ("Rowan Elgendy",      "روان الجندي",       "Sheikh Zayed",    "الشيخ زايد"),
    ("Bahaa Elmahdy",      "بهاء المهدي",       "Shubra",          "شبرا"),
    ("Jana Elhawary",      "جنى الهواري",       "Heliopolis",      "مصر الجديدة"),
]

# Species / breeds actually common in Egyptian small-animal practice.
BREEDS = {
    "Cat": ["Baladi (Domestic Shorthair)", "Shirazi (Persian)", "Himalayan",
            "Siamese", "British Shorthair", "Scottish Fold", "Turkish Angora"],
    "Dog": ["Baladi (Egyptian Street Dog)", "German Shepherd", "Griffon",
            "Golden Retriever", "Husky", "Rottweiler", "Chihuahua",
            "Poodle", "Pit Bull Terrier", "Labrador Retriever"],
    "Bird": ["Budgerigar", "Cockatiel", "African Grey", "Canary", "Lovebird"],
    "Rabbit": ["Dutch", "Angora", "Lop"],
    "Turtle": ["Red-Eared Slider", "Egyptian Tortoise"],
    "Hamster": ["Syrian", "Dwarf Roborovski"],
}
SPECIES_MIX = ["Cat"] * 9 + ["Dog"] * 7 + ["Bird"] * 2 + ["Rabbit", "Turtle", "Hamster"]

PET_NAMES_AR = ["بسبس", "لولو", "نونو", "مشمش", "زعتر", "فلفل", "قمر", "سكر",
                "توتة", "بندق", "عسل", "كوكي", "شيكو", "سمسم", "نمنم", "بطوطة",
                "لبن", "زيزو", "ميمي", "دودي", "خوخة", "جوجو"]
PET_NAMES_EN = ["Rex", "Luna", "Max", "Coco", "Simba", "Bella", "Milo", "Nala",
                "Rocky", "Daisy", "Zeus", "Molly", "Oscar", "Cleo", "Buddy",
                "Ruby", "Loki", "Pepper", "Shadow", "Kiwi"]

# (username, latin, arabic, role, job title)
STAFF = [
    ("owner.hossam",  "Dr. Hossam Elmenshawy", "د. حسام المنشاوي", "clinic_owner",   "Managing Partner"),
    ("dr.sara",       "Dr. Sara Elgohary",     "د. سارة الجوهري",  "doctor",         "Senior Veterinarian"),
    ("dr.mostafa",    "Dr. Mostafa Kamal",     "د. مصطفى كمال",    "doctor",         "Veterinary Surgeon"),
    ("dr.nourhan",    "Dr. Nourhan Fathy",     "د. نورهان فتحي",   "doctor",         "Internal Medicine"),
    ("nurse.mariam",  "Mariam Adly",           "مريم عدلي",        "nurse",          "Veterinary Nurse"),
    ("nurse.ali",     "Ali Sobhy",             "علي صبحي",         "nurse",          "Veterinary Technician"),
    ("rec.yasmine",   "Yasmine Nabil",         "ياسمين نبيل",      "reception",      "Front Desk"),
    ("rec.mahmoud",   "Mahmoud Rashad",        "محمود رشاد",       "reception",      "Front Desk"),
    ("pharm.rania",   "Rania Elsayed",         "رانيا السيد",      "pharmacist",     "Clinic Pharmacist"),
    ("inv.tamer",     "Tamer Abdelhamid",      "تامر عبد الحميد",  "inventory_mgr",  "Stores Supervisor"),
    ("fin.dalia",     "Dalia Serag",           "داليا سراج",       "finance",        "Accountant"),
    ("groom.nada",    "Nada Elshamy",          "ندى الشامي",       "groomer",        "Head Groomer"),
    ("board.sameh",   "Sameh Fahmy",           "سامح فهمي",        "boarding_staff", "Boarding Attendant"),
    ("hr.marwa",      "Marwa Ezzat",           "مروة عزت",         "hr",             "HR Officer"),
]
DOCTORS = ["dr.sara", "dr.mostafa", "dr.nourhan"]

# EGP price list, 2026 Egyptian small-animal market. Overrides the low
# placeholder prices in models.database._seed_services so the finance figures a
# buyer sees are the ones they would actually charge.
SERVICE_PRICES = {
    "CONS-GEN": 350, "CONS-EMG": 600, "CONS-FOL": 200,
    "VAC-RAB": 300, "VAC-DHPP": 450, "VAC-FVR": 400,
    "LAB-CBC": 450, "LAB-BIO": 750, "LAB-URI": 300, "LAB-XRY": 600, "LAB-ULT": 800,
    "SRG-SPN": 2500, "SRG-DEN": 1800, "SRG-MAS": 3500,
    "GRM-BTH": 300, "GRM-FUL": 600, "GRM-NAL": 120,
    "BRD-STD": 250, "BRD-PRM": 450, "HOSP-DAY": 500,
    "MED-ADM": 300, "MED-INJ": 100, "MED-WND": 200,
}

# (sku, name, name_ar, category, unit, cost, sell, reorder, is_med, rx_only)
ITEMS = [
    ("MED-AMOX",  "Amoxicillin 250mg Tablets", "أموكسيسيللين ٢٥٠ مجم", "Medications", "tablet", 4.5, 12, 100, 1, 1),
    ("MED-META",  "Metronidazole 250mg",       "ميترونيدازول ٢٥٠ مجم", "Medications", "tablet", 3.0, 9,  100, 1, 1),
    ("MED-MELO",  "Meloxicam Oral Suspension", "ميلوكسيكام شراب",       "Medications", "bottle", 210, 480, 8,  1, 1),
    ("MED-PRAZ",  "Praziquantel Dewormer",     "برازيكوانتيل طارد ديدان", "Medications", "tablet", 18, 45, 60, 1, 0),
    ("MED-DEXA",  "Dexamethasone Injection",   "ديكساميثازون حقن",      "Medications", "vial",   35, 90,  20, 1, 1),
    ("MED-CEFT",  "Ceftriaxone 1g Vial",       "سيفترياكسون ١ جم",      "Medications", "vial",   62, 150, 25, 1, 1),
    ("MED-OTIC",  "Otic Ear Drops",            "قطرة أذن",              "Medications", "bottle", 55, 140, 15, 1, 0),
    ("MED-OPHT",  "Antibiotic Eye Ointment",   "مرهم عين مضاد حيوي",    "Medications", "tube",   40, 110, 15, 1, 0),
    ("VAC-RABV",  "Rabies Vaccine Vial",       "لقاح السعار",           "Vaccines",    "dose",   95,  300, 20, 1, 1),
    ("VAC-DHPPV", "DHPP Combo Vaccine",        "لقاح رباعي للكلاب",     "Vaccines",    "dose",   170, 450, 15, 1, 1),
    ("VAC-FVRCP", "FVRCP Feline Vaccine",      "لقاح رباعي للقطط",      "Vaccines",    "dose",   150, 400, 15, 1, 1),
    ("CON-SYR",   "Disposable Syringe 5ml",    "سرنجة ٥ مل",            "Consumables", "unit",   1.8, 5,  300, 0, 0),
    ("CON-GLOV",  "Examination Gloves (box)",  "قفازات فحص (علبة)",     "Consumables", "box",    120, 220, 12, 0, 0),
    ("CON-GAUZ",  "Sterile Gauze Pack",        "شاش معقم",              "Consumables", "pack",   22,  55,  40, 0, 0),
    ("CON-IVSET", "IV Infusion Set",           "طقم محاليل وريدية",     "Consumables", "unit",   28,  70,  30, 0, 0),
    ("SRG-SUT",   "Absorbable Suture 3/0",     "خيط جراحي قابل للامتصاص", "Surgical Materials", "unit", 48, 120, 25, 0, 0),
    ("SRG-BLAD",  "Scalpel Blade #10",         "شفرة مشرط",             "Surgical Materials", "unit", 6, 18, 50, 0, 0),
    ("LAB-CBCK",  "CBC Reagent Kit",           "كاشف صورة دم",          "Lab Materials", "kit",  620, 0,   4,  0, 0),
    ("LAB-SLIDE", "Microscope Slides (box)",   "شرائح ميكروسكوب",       "Lab Materials", "box",  85,  0,   8,  0, 0),
    ("GRM-SHMP",  "Medicated Pet Shampoo",     "شامبو طبي",             "Grooming Products", "bottle", 95, 240, 15, 0, 0),
]

# (test, sample, unit, low, high, normal_text, abnormal_text)
LAB_TESTS = [
    ("CBC Blood Count",   "Whole Blood", "10^3/uL", 6.0, 17.0,
     "All haematology parameters within reference range.",
     "Leukocytosis with neutrophilia — consistent with active bacterial infection."),
    ("Biochemistry Panel", "Serum",      "mg/dL",   0.5, 1.6,
     "Renal and hepatic markers within reference range.",
     "Creatinine elevated — early renal compromise, recheck in 14 days."),
    ("Urinalysis",        "Urine",       "USG",     1.015, 1.045,
     "Urine concentrated, no crystals or casts seen.",
     "Struvite crystals present with alkaline pH — urolithiasis suspected."),
    ("Feline Leukemia Screen", "Serum",  "index",   0.0, 0.9,
     "FeLV antigen not detected.",
     "FeLV antigen detected — confirm with PCR before prognosis."),
]

# (complaint, complaint_ar, diagnosis, diagnosis_ar, severity, drug skus)
CASES = [
    ("Vomiting and reduced appetite for 3 days", "قيء وفقدان شهية منذ ٣ أيام",
     "Acute Gastroenteritis", "التهاب معوي حاد", "Moderate", ["MED-META", "MED-MELO"]),
    ("Scratching ears, head shaking", "هرش في الأذن وهز الرأس",
     "Otitis Externa", "التهاب الأذن الخارجية", "Mild", ["MED-OTIC", "MED-AMOX"]),
    ("Limping on right hind limb", "عرج في الطرف الخلفي الأيمن",
     "Soft Tissue Trauma", "إصابة أنسجة رخوة", "Moderate", ["MED-MELO"]),
    ("Routine annual check and vaccination", "فحص سنوي وتطعيم",
     "Healthy — Preventive Visit", "سليم — زيارة وقائية", "Mild", []),
    ("Hair loss and skin redness on the back", "تساقط شعر واحمرار الجلد",
     "Flea Allergy Dermatitis", "حساسية جلدية من البراغيث", "Moderate", ["MED-DEXA", "MED-AMOX"]),
    ("Straining to urinate, blood in urine", "صعوبة في التبول ودم في البول",
     "Feline Lower Urinary Tract Disease", "أمراض المسالك البولية السفلية", "Severe",
     ["MED-MELO", "MED-CEFT"]),
    ("Red, watery left eye", "احمرار ودموع في العين اليسرى",
     "Conjunctivitis", "التهاب الملتحمة", "Mild", ["MED-OPHT"]),
    ("Worms seen in stool", "ديدان في البراز",
     "Intestinal Parasitism", "إصابة بالديدان المعوية", "Mild", ["MED-PRAZ"]),
    ("Lethargy and high temperature", "خمول وارتفاع في الحرارة",
     "Pyrexia of Unknown Origin", "ارتفاع حرارة مجهول السبب", "Severe",
     ["MED-CEFT", "MED-MELO"]),
    ("Bad breath, difficulty chewing", "رائحة فم كريهة وصعوبة في المضغ",
     "Periodontal Disease Grade 2", "التهاب لثة درجة ٢", "Moderate", ["MED-AMOX"]),
]

SUPPLIERS = [
    ("Delta Veterinary Supplies", "دلتا للمستلزمات البيطرية", "Hossam Nagy", "01001122334", "Net 30"),
    ("Cairo Pharma Distribution", "القاهرة لتوزيع الأدوية",   "Ehab Selim",  "01223344556", "Net 45"),
    ("Nile Lab Solutions",        "النيل لحلول المعامل",       "Marwa Adel",  "01118899776", "Net 15"),
    ("Pet Care Egypt",            "بت كير إيجيبت",             "Ziad Hassan", "01555667788", "Prepaid"),
]

PS_CATEGORIES = [
    ("Dry Food", "دراي فود"), ("Wet Food", "طعام معلب"), ("Litter & Hygiene", "رمل ونظافة"),
    ("Toys", "لعب"), ("Accessories", "إكسسوارات"), ("Supplements", "مكملات غذائية"),
]
# (cat_index, sku, name, name_ar, brand, cost, sell, stock, reorder)
PS_PRODUCTS = [
    (0, "PS-DRY-CAT2", "Adult Cat Dry Food 2kg",   "دراي فود قطط ٢ كجم",   "Whiskas",  310, 480, 40, 10),
    (0, "PS-DRY-DOG10","Adult Dog Dry Food 10kg",  "دراي فود كلاب ١٠ كجم", "Pedigree", 980, 1450, 14, 5),
    (0, "PS-DRY-KIT",  "Kitten Dry Food 1.5kg",    "دراي فود قطط صغيرة",   "Royal Canin", 520, 790, 18, 6),
    (1, "PS-WET-TUNA", "Tuna Pouch 85g",           "كيس تونة ٨٥ جم",       "Whiskas",  14,  25,  220, 60),
    (1, "PS-WET-CHIK", "Chicken Pate Can 400g",    "علبة دجاج ٤٠٠ جم",     "Purina",   48,  85,  70, 20),
    (2, "PS-LIT-CLMP", "Clumping Cat Litter 10L",  "رمل متكتل ١٠ لتر",     "Cat's Best", 260, 420, 26, 8),
    (2, "PS-LIT-PADS", "Puppy Training Pads (50)", "فوط تدريب جراوي",      "Trixie",   190, 330, 15, 6),
    (3, "PS-TOY-BALL", "Rubber Chew Ball",         "كرة مطاطية للعض",      "Kong",     70,  145, 34, 12),
    (3, "PS-TOY-WAND", "Feather Teaser Wand",      "لعبة ريش للقطط",       "Trixie",   35,  80,  48, 15),
    (4, "PS-ACC-COLL", "Adjustable Nylon Collar",  "طوق نايلون",           "Trixie",   55,  120, 30, 10),
    (4, "PS-ACC-CARR", "Pet Carrier Medium",       "شنطة نقل متوسطة",      "Ferplast", 640, 990, 7,  3),
    (4, "PS-ACC-BOWL", "Stainless Steel Bowl",     "طبق ستانلس",           "Trixie",   45,  95,  40, 12),
    (5, "PS-SUP-OMEG", "Omega-3 Skin & Coat Oil",  "زيت أوميجا ٣",         "Beaphar",  180, 340, 16, 6),
    (5, "PS-SUP-CALC", "Calcium Tablets for Dogs", "أقراص كالسيوم",        "Beaphar",  120, 245, 22, 8),
]

EXPENSE_LINES = [
    ("Rent", "Clinic rent — Nasr City branch", 18000, "Landlord"),
    ("Utilities", "Electricity and water", 3400, "North Cairo Electricity"),
    ("Utilities", "Internet and phone lines", 950, "WE"),
    ("Medicines/Supplies", "Pharmacy restock", 22000, "Delta Veterinary Supplies"),
    ("Marketing", "Facebook and Instagram ads", 2500, "Meta"),
    ("Equipment", "Ultrasound probe maintenance", 4800, "Nile Lab Solutions"),
    ("Miscellaneous", "Medical waste disposal", 1600, "EcoMed"),
    ("Miscellaneous", "Cleaning and consumables", 1200, "Local supplier"),
]

# Basic monthly salary by role, EGP, small Cairo clinic 2026.
SALARY_GRADES = [
    ("clinic_owner", 35000, 0), ("doctor", 18000, 120), ("nurse", 9000, 60),
    ("reception", 7500, 50), ("pharmacist", 11000, 70), ("inventory_mgr", 10000, 60),
    ("finance", 12000, 70), ("groomer", 8500, 55), ("boarding_staff", 7000, 45),
    ("hr", 11000, 65),
]


# ── Small helpers ─────────────────────────────────────────────────────────────

def _one(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return row


def _ins(conn, sql, params):
    """INSERT and return the new row id (works on SQLite and PostgreSQL)."""
    return conn.execute(sql, params).lastrowid


def _dt(d: date, hh: int, mm: int = 0) -> str:
    return f"{d.isoformat()} {hh:02d}:{mm:02d}:00"


def _money(x) -> float:
    return round(float(x), 2)


def _phone(rnd: Random) -> str:
    return f"{rnd.choice(['010', '011', '012', '015'])}{rnd.randint(10000000, 99999999)}"


# ── Phases ────────────────────────────────────────────────────────────────────

def wipe(conn) -> None:
    for table in WIPE_ORDER:
        try:
            conn.execute(f"DELETE FROM {table}")
        except Exception as exc:                      # table not created yet
            if "no such table" in str(exc).lower() or "does not exist" in str(exc).lower():
                continue
            raise
    conn.execute("DELETE FROM users WHERE email LIKE ?", (f"%@{DEMO_EMAIL_DOMAIN}",))
    conn.commit()


def seed_clinic(conn) -> None:
    conn.execute(
        "UPDATE clinic SET name=?, name_ar=?, phone=?, email=?, address=?, address_ar=?,"
        " website=?, tax_number=?, license_number=?, doctor_name=?, tagline=?,"
        " currency=?, timezone=?, updated_at=datetime('now') WHERE id=1",
        ("Aleefy Veterinary Clinic", ar("عيادة أليفي البيطرية"),
         "0226701234", "info@aleefy-demo.local",
         "12 Abbas El-Akkad St., Nasr City, Cairo",
         ar("١٢ شارع عباس العقاد، مدينة نصر، القاهرة"),
         "https://aleefy.online", "512-874-336", "VET-CAI-2019-0447",
         "Dr. Hossam Elmenshawy", "Happy Pets, Healthy Lives",
         "EGP", "Africa/Cairo"))
    if _one(conn, "SELECT COUNT(*) FROM branches")[0] < 2:
        conn.execute("INSERT INTO branches (name, name_ar, phone, address) VALUES (?,?,?,?)",
                     ("Heliopolis Branch", ar("فرع مصر الجديدة"), "0224145566",
                      "7 Baghdad St., Korba, Heliopolis"))
    conn.execute("UPDATE branches SET name=?, name_ar=?, phone=?, address=? WHERE id=1",
                 ("Nasr City (Main)", ar("مدينة نصر (الرئيسي)"), "0226701234",
                  "12 Abbas El-Akkad St., Nasr City, Cairo"))
    # Re-price the catalog to Egyptian 2026 levels.
    for code, price in SERVICE_PRICES.items():
        conn.execute("UPDATE service_catalog SET standard_price=? WHERE code=?", (price, code))
    for name, price in [("Basic Bath", 300), ("Full Grooming", 600),
                        ("Nail Trim", 120), ("Ear Cleaning", 180)]:
        conn.execute("UPDATE grooming_services SET price=? WHERE name=?", (price, name))
    for rtype, price in [("Standard", 250), ("Premium", 450), ("ICU", 900)]:
        conn.execute("UPDATE boarding_rooms SET price_per_night=? WHERE room_type=?", (price, rtype))
    conn.commit()


def seed_staff(conn, rnd: Random, today: date) -> dict:
    """Create demo staff. Returns {username: user_row_dict}."""
    # ponytail: one bcrypt call reused for all 14 demo accounts (bcrypt-12 is
    # ~300 ms each, so per-user hashing would add ~4 s to every seed and every
    # test run). Ceiling: every demo account shares one password, and identical
    # hashes are visible in the users table. Give them distinct passwords the
    # day a demo needs to show per-user credential handling.
    pw_hash = db._hash(DEMO_PASSWORD)
    users = {}
    for i, (uname, latin, arabic, role, title) in enumerate(STAFF):
        hire = (today - timedelta(days=rnd.randint(200, 2100))).isoformat()
        _ins(conn,
             "INSERT INTO users (username,password_hash,full_name,full_name_ar,email,phone,"
             "role,branch_id,is_active,language,created_at) VALUES (?,?,?,?,?,?,?,?,1,?,?)",
             (uname, pw_hash, latin, ar(arabic), f"{uname}@{DEMO_EMAIL_DOMAIN}",
              _phone(rnd), role, 1 if i % 4 else 2,
              "ar" if role in ("nurse", "reception", "boarding_staff") else "en",
              _dt(today - timedelta(days=400), 9)))
        # These columns are added by blueprints.hr._ensure_hr_tables(), which
        # ensure_module_tables() has already run. If one is missing the ALTER
        # silently failed and the HR screens will be wrong — let it raise here
        # rather than at a demo.
        for col, val in [("hire_date", hire), ("job_title", title),
                         ("contract_type", "Full-time"),
                         ("gender", "Female" if i % 2 else "Male")]:
            conn.execute(f"UPDATE users SET {col}=? WHERE username=?", (val, uname))
        users[uname] = dict(_one(conn, "SELECT * FROM users WHERE username=?", (uname,)))
    conn.commit()
    return users


def seed_owners_pets(conn, rnd: Random, today: date):
    owners, pets = [], []
    for idx, (latin, arabic, district, district_ar) in enumerate(OWNERS):
        phone = _phone(rnd)
        oid = _ins(conn,
                   "INSERT INTO owners (full_name,full_name_ar,phone,whatsapp_phone,email,"
                   "address,address_ar,preferred_contact,vip_flag,marketing_consent,notes,"
                   "created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (latin, ar(arabic), phone, phone,
                    f"{latin.split()[0].lower()}{idx}@example.com",
                    f"{rnd.randint(3, 90)} {district}, Cairo",
                    ar(f"{district_ar}، القاهرة"),
                    rnd.choice(["WhatsApp", "WhatsApp", "Phone", "SMS"]),
                    1 if idx % 11 == 0 else 0,
                    0 if idx % 9 == 0 else 1,
                    ar("يفضل المواعيد المسائية") if idx % 7 == 0 else None,
                    "rec.yasmine",
                    _dt(today - timedelta(days=rnd.randint(190, 900)), 10, rnd.randint(0, 59))))
        owners.append(oid)
        for _ in range(rnd.choices([1, 2, 3], weights=[60, 30, 10])[0]):
            species = rnd.choice(SPECIES_MIX)
            use_ar = rnd.random() < 0.42
            name = ar(rnd.choice(PET_NAMES_AR)) if use_ar else rnd.choice(PET_NAMES_EN)
            dob = today - timedelta(days=rnd.randint(120, 4200))
            weight = {"Cat": (2.5, 7.5), "Dog": (4.0, 45.0), "Bird": (0.03, 1.2),
                      "Rabbit": (1.0, 3.0), "Turtle": (0.3, 4.0),
                      "Hamster": (0.05, 0.2)}[species]
            pid = _ins(conn,
                       "INSERT INTO pets (owner_id,pet_name,species,breed,sex,dob,weight_kg,"
                       "color,microchip_id,neutered,allergies,chronic_conditions,notes,"
                       "is_active,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                       (oid, name, species, rnd.choice(BREEDS[species]),
                        rnd.choice(["Male", "Female"]), dob.isoformat(),
                        round(rnd.uniform(*weight), 1),
                        rnd.choice(["White", "Black", "Ginger", "Grey", "Brown",
                                    "Tabby", "Black & White", "Cream"]),
                        f"EG{rnd.randint(100000000000000, 999999999999999)}" if rnd.random() < 0.35 else None,
                        1 if rnd.random() < 0.4 else 0,
                        rnd.choice([None, None, None, "Chicken protein", "Flea saliva"]),
                        rnd.choice([None, None, None, None, "Chronic renal disease",
                                    "Diabetes mellitus", "Hip dysplasia"]),
                        None,
                        _dt(today - timedelta(days=rnd.randint(150, 850)), 11)))
            pets.append((pid, oid, species, name))
    conn.commit()
    return owners, pets


def seed_inventory(conn, rnd: Random, today: date):
    cat_ids = {r["name"]: r["id"] for r in conn.execute(
        "SELECT id, name FROM item_categories").fetchall()}
    wh = _one(conn, "SELECT id FROM warehouses ORDER BY id LIMIT 1")["id"]

    supplier_ids = []
    for name, name_ar, contact, phone, terms in SUPPLIERS:
        supplier_ids.append(_ins(conn,
            "INSERT INTO suppliers (name,name_ar,contact_name,phone,email,address,"
            "payment_terms,is_active,created_at) VALUES (?,?,?,?,?,?,?,1,?)",
            (name, ar(name_ar), contact, phone,
             f"{contact.split()[0].lower()}@supplier.example",
             "Industrial Zone, Cairo", terms,
             _dt(today - timedelta(days=500), 9))))

    items = {}
    for i, (sku, name, name_ar, cat, unit, cost, sell, reorder, is_med, rx) in enumerate(ITEMS):
        iid = _ins(conn,
            "INSERT INTO items (category_id,sku,barcode,name,name_ar,unit,cost_price,"
            "sell_price,reorder_level,max_stock,is_medication,requires_rx,supplier_id,"
            "storage_notes,is_active,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
            (cat_ids.get(cat), sku, f"622{rnd.randint(1000000000, 9999999999)}",
             name, ar(name_ar), unit, cost, sell, reorder, reorder * 12,
             is_med, rx, supplier_ids[i % len(supplier_ids)],
             "Store below 25 C" if is_med else None,
             _dt(today - timedelta(days=460), 9)))
        items[sku] = {"id": iid, "sell": sell, "cost": cost, "unit": unit,
                      "name": name, "reorder": reorder, "is_med": is_med}
        conn.execute("INSERT INTO reorder_rules (item_id,reorder_point,reorder_qty,"
                     "preferred_supplier_id,auto_suggest) VALUES (?,?,?,?,1)",
                     (iid, reorder, reorder * 4, supplier_ids[i % len(supplier_ids)]))
        if is_med:
            conn.execute("INSERT INTO dosage_templates (item_id,species,dosage,frequency,route)"
                         " VALUES (?,?,?,?,?)",
                         (iid, "All", "10 mg/kg", "Every 12 hours", "Oral"))

        # Three deliveries spread over the history so the stock-movement chart
        # has inflow in every month, not one spike. Every fourth item gets a
        # batch expiring inside 60 days to populate the expiry widget.
        near_expiry = (i % 4 == 0)
        for b, days_ago in enumerate((165, 100, 35)):
            expiry = today + timedelta(days=(rnd.randint(12, 55) if (near_expiry and b == 0)
                                             else rnd.randint(200, 900)))
            received = today - timedelta(days=days_ago + rnd.randint(0, 8))
            qty = round(reorder * rnd.uniform(9.0, 16.0), 1)
            bid = _ins(conn,
                "INSERT INTO batches (item_id,warehouse_id,batch_number,lot_number,"
                "manufacture_date,expiry_date,quantity,unit_cost,received_at,received_by)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (iid, wh, f"B{today.year}{i:02d}{b}", f"LOT-{rnd.randint(1000, 9999)}",
                 (received - timedelta(days=rnd.randint(60, 300))).isoformat(),
                 expiry.isoformat(), qty, cost, _dt(received, 8), "inv.tamer"))
            conn.execute(
                "INSERT INTO stock_movements (item_id,batch_id,warehouse_id,movement_type,"
                "quantity,unit_cost,reference_type,reference_id,notes,created_by,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (iid, bid, wh, "in", qty, cost, "purchase", None,
                 "Opening stock" if b == 0 else "Supplier delivery", "inv.tamer",
                 _dt(received, 8)))
            items[sku].setdefault("batches", []).append(bid)

    # Purchase orders: two received, one still open.
    for n, (status, days_ago) in enumerate([("Received", 95), ("Received", 40), ("Sent", 6)]):
        order_date = today - timedelta(days=days_ago)
        sup = supplier_ids[n % len(supplier_ids)]
        po_id = _ins(conn,
            "INSERT INTO purchase_orders (po_number,supplier_id,branch_id,status,order_date,"
            "expected_date,received_date,subtotal,tax_amount,total,notes,created_by,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"PO-{order_date.strftime('%Y%m')}-{n + 1:03d}", sup, 1, status,
             order_date.isoformat(), (order_date + timedelta(days=7)).isoformat(),
             (order_date + timedelta(days=5)).isoformat() if status == "Received" else None,
             0, 0, 0, None, "inv.tamer", _dt(order_date, 10)))
        subtotal = 0.0
        for sku in rnd.sample(list(items), 5):
            it = items[sku]
            q = float(rnd.randint(10, 60))
            line = _money(q * it["cost"])
            subtotal += line
            conn.execute("INSERT INTO po_lines (po_id,item_id,quantity,unit_cost,total,"
                         "received_qty) VALUES (?,?,?,?,?,?)",
                         (po_id, it["id"], q, it["cost"], line,
                          q if status == "Received" else 0))
        tax = _money(subtotal * 0.14)
        conn.execute("UPDATE purchase_orders SET subtotal=?, tax_amount=?, total=? WHERE id=?",
                     (_money(subtotal), tax, _money(subtotal + tax), po_id))
    conn.commit()
    return items, supplier_ids, wh


def _deduct_stock(conn, wh, item, qty, ref_id, when, by, note):
    """FEFO deduction that can never drive a batch negative.

    Returns the quantity actually taken. Short-picks are left short on purpose:
    a demo where stock silently goes negative is worse than one that shows a
    line running out.

    # ponytail: one SELECT + one UPDATE per batch, per dispensed line — ~600
    # round-trips over a full seed. Fine at this size (whole run is <20 s).
    # Ceiling: a 10x larger dataset wants the batch quantities held in memory
    # and written back once at the end.
    """
    taken = 0.0
    rows = conn.execute(
        "SELECT id, quantity FROM batches WHERE item_id=? AND quantity > 0"
        " ORDER BY expiry_date", (item["id"],)).fetchall()
    for row in rows:
        if taken >= qty:
            break
        take = min(float(row["quantity"]), qty - taken)
        conn.execute("UPDATE batches SET quantity = quantity - ? WHERE id=?",
                     (take, row["id"]))
        conn.execute(
            "INSERT INTO stock_movements (item_id,batch_id,warehouse_id,movement_type,"
            "quantity,unit_cost,reference_type,reference_id,notes,created_by,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (item["id"], row["id"], wh, "out", take, item["cost"], "visit", ref_id,
             note, by, when))
        taken += take
    return taken, (rows[0]["id"] if rows else None)


def seed_clinical(conn, rnd: Random, today: date, users, owners, pets, items, services):
    """Appointments -> visits -> diagnoses -> prescriptions -> stock -> invoices."""
    stats = dict(appointments=0, visits=0, prescriptions=0, invoices=0,
                 payments=0, labs=0, vaccinations=0, surgeries=0, followups=0)
    wh = _one(conn, "SELECT id FROM warehouses ORDER BY id LIMIT 1")["id"]
    doctor_rows = {u: users[u] for u in DOCTORS}
    inv_seq = 0

    def next_invoice_no(d: date) -> str:
        nonlocal inv_seq
        inv_seq += 1
        return f"INV-{d.strftime('%Y%m')}-{inv_seq:04d}"

    days = list(range(-182, 15))
    for offset in days:
        day = today + timedelta(days=offset)
        if day.weekday() == 4:                      # Friday — clinic closed
            continue
        n_appt = rnd.choices([0, 1, 2, 3, 4, 5], weights=[3, 8, 16, 22, 18, 10])[0]
        if offset > 0:
            n_appt = rnd.choices([2, 3, 4, 5], weights=[15, 35, 30, 20])[0]
        elif offset == 0:
            # The Today board is the first screen anyone opens. Never let the
            # dice leave it empty.
            n_appt = 7
        for slot in range(n_appt):
            pid, oid, species, pet_name = rnd.choice(pets)
            uname = rnd.choice(DOCTORS)
            doc = doctor_rows[uname]
            hour = 10 + (slot * 2) % 10
            minute = rnd.choice([0, 15, 30, 45])
            case = rnd.choice(CASES)

            if offset > 0:
                status = rnd.choices(["Scheduled", "Confirmed"], weights=[40, 60])[0]
            elif offset == 0:
                status = ["Completed", "Completed", "Completed", "Checked-in",
                          "Checked-in", "Confirmed", "Scheduled"][slot % 7]
            else:
                status = rnd.choices(["Completed", "No-Show", "Cancelled"],
                                     weights=[84, 9, 7])[0]

            appt_type = rnd.choices(
                ["Consultation", "Vaccination", "Follow-up", "Surgery", "Emergency"],
                weights=[46, 20, 18, 8, 8])[0]
            appt_id = _ins(conn,
                "INSERT INTO appointments (owner_id,pet_id,branch_id,doctor_id,doctor_name,"
                "room,appointment_type,priority,status,channel,appt_date,appt_start,appt_end,"
                "duration_min,reason,symptoms,confirmed,reminder_sent,checked_in_at,"
                "created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (oid, pid, 1, doc["id"], doc["full_name"],
                 rnd.choice(["Exam Room 1", "Exam Room 2", "Surgery Suite"]),
                 appt_type, "Urgent" if appt_type == "Emergency" else "Normal",
                 status, rnd.choices(["WhatsApp", "Phone", "Walk-in", "Online"],
                                     weights=[42, 28, 22, 8])[0],
                 day.isoformat(), f"{hour:02d}:{minute:02d}",
                 f"{hour + (1 if minute >= 30 else 0):02d}:{(minute + 30) % 60:02d}",
                 30, case[0], ar(case[1]),
                 1 if status in ("Confirmed", "Checked-in", "Completed") else 0,
                 1 if offset <= 1 else 0,
                 _dt(day, hour, minute) if status in ("Checked-in", "Completed") else None,
                 "rec.yasmine", _dt(day - timedelta(days=rnd.randint(1, 9)), 12)))
            stats["appointments"] += 1

            # Reminder for anything recent or upcoming — this is what the
            # reminders queue and the WhatsApp log render.
            if offset >= -50 and rnd.random() < 0.62:
                due = _dt(day - timedelta(days=1), 18)
                sent = offset <= 0
                conn.execute(
                    "INSERT INTO reminders (owner_id,pet_id,appointment_id,reminder_type,"
                    "message,channel,scheduled_for,status,sent_at,created_by,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (oid, pid, appt_id, "appointment",
                     f"Reminder: {pet_name} has an appointment at Aleefy on "
                     f"{day.isoformat()} at {hour:02d}:{minute:02d}.",
                     rnd.choices(["WhatsApp", "SMS"], weights=[85, 15])[0], due,
                     "Sent" if sent else "Pending", due if sent else None,
                     "system", _dt(day - timedelta(days=2), 18)))

            if status != "Completed":
                continue

            # ── VISIT ────────────────────────────────────────────────────────
            weight = _one(conn, "SELECT weight_kg FROM pets WHERE id=?", (pid,))["weight_kg"]
            visit_id = _ins(conn,
                "INSERT INTO visits (appointment_id,owner_id,pet_id,doctor_id,doctor_name,"
                "branch_id,room,visit_date,visit_type,status,chief_complaint,symptoms,"
                "weight_kg,temp_c,heart_rate,respiratory_rate,notes,created_by,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (appt_id, oid, pid, doc["id"], doc["full_name"], 1, "Exam Room 1",
                 day.isoformat(), appt_type, "Completed", case[0], ar(case[1]),
                 round((weight or 5) * rnd.uniform(0.96, 1.04), 1),
                 round(rnd.uniform(37.8, 40.1), 1), rnd.randint(70, 160),
                 rnd.randint(16, 40),
                 "Owner counselled on home care and warning signs.",
                 uname, _dt(day, hour, minute)))
            stats["visits"] += 1

            conn.execute(
                "INSERT INTO diagnoses (visit_id,pet_id,diagnosis,severity,is_chronic,notes,"
                "created_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (visit_id, pid, case[2], case[4], 1 if case[4] == "Severe" and rnd.random() < 0.3 else 0,
                 ar(case[3]), uname, _dt(day, hour, minute + 5 if minute < 55 else 59)))
            conn.execute(
                "INSERT INTO treatment_plans (visit_id,pet_id,plan_text,goals,duration,"
                "followup_in,followup_unit,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (visit_id, pid,
                 f"Treat {case[2].lower()}; medication as prescribed, re-examine if no improvement.",
                 "Symptom resolution within 7 days", "7 days", 7, "days", uname,
                 _dt(day, hour, 59)))

            lines = []   # (line_type, item_id, description, qty, unit_price)
            svc_code = {"Consultation": "CONS-GEN", "Follow-up": "CONS-FOL",
                        "Emergency": "CONS-EMG", "Vaccination": "CONS-GEN",
                        "Surgery": "CONS-GEN"}[appt_type]
            svc = services[svc_code]
            lines.append(("service", None, svc["name"], 1.0, svc["standard_price"]))

            # ── PRESCRIPTION + STOCK DEDUCTION ───────────────────────────────
            if case[5]:
                rx_id = _ins(conn,
                    "INSERT INTO prescriptions (visit_id,pet_id,owner_id,prescribed_by,status,"
                    "notes,dispensed_at,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (visit_id, pid, oid, doc["full_name"], "Dispensed",
                     "Give with food. Complete the full course.",
                     _dt(day, hour + 1), _dt(day, hour, 59)))
                stats["prescriptions"] += 1
                for sku in case[5]:
                    it = items[sku]
                    qty = float(rnd.randint(1, 3) * (10 if it["unit"] == "tablet" else 1))
                    rx_item_id = _ins(conn,
                        "INSERT INTO prescription_items (prescription_id,item_id,"
                        "medication_name,dosage,frequency,duration,route,quantity,unit,"
                        "instructions,dispensed) VALUES (?,?,?,?,?,?,?,?,?,?,1)",
                        (rx_id, it["id"], it["name"], "10 mg/kg",
                         rnd.choice(["Every 12 hours", "Every 24 hours", "Every 8 hours"]),
                         "7 days", "Oral" if it["unit"] == "tablet" else "Injection",
                         qty, it["unit"], ar("يعطى بعد الأكل")))
                    taken, batch_id = _deduct_stock(
                        conn, wh, it, qty, visit_id, _dt(day, hour + 1), "pharm.rania",
                        f"Dispensed on visit #{visit_id}")
                    if taken:
                        conn.execute(
                            "INSERT INTO dispensing_log (prescription_item_id,item_id,batch_id,"
                            "visit_id,pet_id,quantity,dispensed_by,dispensed_at,notes)"
                            " VALUES (?,?,?,?,?,?,?,?,?)",
                            (rx_item_id, it["id"], batch_id, visit_id, pid, taken,
                             "pharm.rania", _dt(day, hour + 1), None))
                    lines.append(("medication", it["id"], it["name"], qty, it["sell"]))

            # ── LABS ─────────────────────────────────────────────────────────
            if rnd.random() < 0.34:
                test, sample, unit, lo, hi, ok_text, bad_text = rnd.choice(LAB_TESTS)
                abnormal = rnd.random() < 0.32
                req_id = _ins(conn,
                    "INSERT INTO lab_requests (visit_id,pet_id,test_name,priority,status,"
                    "sample_type,collected_at,notes,requested_by,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (visit_id, pid, test,
                     "Urgent" if appt_type == "Emergency" else "Routine",
                     "Completed", sample, _dt(day, hour, 40), None, uname,
                     _dt(day, hour, 35)))
                value = round(rnd.uniform(hi * 1.15, hi * 1.8) if abnormal
                              else rnd.uniform(lo, hi), 2)
                conn.execute(
                    "INSERT INTO lab_results (lab_request_id,pet_id,result_text,result_value,"
                    "unit,reference_range,is_abnormal,reviewed_by,reviewed_at,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (req_id, pid, bad_text if abnormal else ok_text, value, unit,
                     f"{lo} - {hi}", 1 if abnormal else 0, doc["full_name"],
                     _dt(day, hour + 2), _dt(day, hour + 1, 30)))
                stats["labs"] += 1
                lab_svc = {"CBC Blood Count": "LAB-CBC", "Biochemistry Panel": "LAB-BIO",
                           "Urinalysis": "LAB-URI"}.get(test, "LAB-CBC")
                s = services[lab_svc]
                lines.append(("service", None, s["name"], 1.0, s["standard_price"]))

            # ── VACCINATION ──────────────────────────────────────────────────
            if appt_type == "Vaccination":
                vac_sku, vac_code, vac_name = (
                    ("VAC-FVRCP", "VAC-FVR", "FVRCP Feline Vaccine") if species == "Cat"
                    else ("VAC-DHPPV", "VAC-DHPP", "DHPP Combo Vaccine"))
                it = items[vac_sku]
                conn.execute(
                    "INSERT INTO vaccinations (pet_id,visit_id,vaccine_name,vaccine_brand,"
                    "batch_number,dose_number,administered_by,administered_at,next_due_at,"
                    "site,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (pid, visit_id, vac_name, rnd.choice(["Nobivac", "Vanguard", "Purevax"]),
                     f"VB{rnd.randint(10000, 99999)}", rnd.randint(1, 3), doc["full_name"],
                     day.isoformat(), (day + timedelta(days=365)).isoformat(),
                     "Subcutaneous", None, _dt(day, hour + 1)))
                stats["vaccinations"] += 1
                _deduct_stock(conn, wh, it, 1.0, visit_id, _dt(day, hour + 1),
                              "nurse.mariam", "Vaccine administered")
                s = services[vac_code]
                lines.append(("service", None, s["name"], 1.0, s["standard_price"]))

            # ── SURGERY ──────────────────────────────────────────────────────
            if appt_type == "Surgery":
                proc, code = rnd.choice([("Spay / Neuter", "SRG-SPN"),
                                         ("Dental Scaling and Polishing", "SRG-DEN"),
                                         ("Mass Removal", "SRG-MAS")])
                conn.execute(
                    "INSERT INTO surgeries (pet_id,visit_id,procedure_name,surgeon,anesthetist,"
                    "surgery_date,duration_min,anesthesia_type,pre_op_notes,post_op_notes,"
                    "outcome,followup_date,consent_given,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                    (pid, visit_id, proc, doc["full_name"], "nurse.ali",
                     day.isoformat(), rnd.randint(45, 140), "General (isoflurane)",
                     "Pre-anaesthetic bloods within range. Fasted 10 hours.",
                     "Recovery uneventful. Analgesia continued for 5 days.",
                     rnd.choices(["Successful", "Successful", "Complicated"],
                                 weights=[85, 10, 5])[0],
                     (day + timedelta(days=10)).isoformat(), _dt(day, hour + 2)))
                stats["surgeries"] += 1
                s = services[code]
                lines.append(("service", None, s["name"], 1.0, s["standard_price"]))

            # ── FOLLOW-UP ────────────────────────────────────────────────────
            if rnd.random() < 0.28:
                due = day + timedelta(days=rnd.randint(7, 30))
                conn.execute(
                    "INSERT INTO followups (visit_id,pet_id,owner_id,due_date,reason,status,"
                    "reminder_sent,completed_at,notes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (visit_id, pid, oid, due.isoformat(), f"Re-check after {case[2]}",
                     "Completed" if due < today else "Pending",
                     1 if due <= today else 0,
                     _dt(due, 12) if due < today else None, None, _dt(day, hour + 1)))
                stats["followups"] += 1

            # ── INVOICE ──────────────────────────────────────────────────────
            subtotal = _money(sum(q * p for _, _, _, q, p in lines))
            disc = _money(subtotal * 0.1) if rnd.random() < 0.12 else 0.0
            total = _money(subtotal - disc)
            inv_id = _ins(conn,
                "INSERT INTO invoices (invoice_number,owner_id,pet_id,visit_id,branch_id,"
                "doctor_name,issue_date,due_date,status,subtotal,discount_type,discount_value,"
                "discount_amount,tax_rate,tax_amount,total,paid_amount,due_amount,notes,"
                "created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (next_invoice_no(day), oid, pid, visit_id, 1, doc["full_name"],
                 day.isoformat(), (day + timedelta(days=14)).isoformat(),
                 "Unpaid", subtotal, "percent", 10 if disc else 0, disc, 0, 0,
                 total, 0, total, None, "rec.mahmoud", _dt(day, hour + 1)))
            stats["invoices"] += 1
            for ltype, item_id, desc, qty, price in lines:
                conn.execute(
                    "INSERT INTO invoice_lines (invoice_id,line_type,item_id,description,"
                    "quantity,unit_price,discount,total) VALUES (?,?,?,?,?,?,0,?)",
                    (inv_id, ltype, item_id, desc, qty, price, _money(qty * price)))

            roll = rnd.random()
            if roll < 0.72:
                paid, pstatus = total, "Paid"
            elif roll < 0.86:
                paid, pstatus = _money(total * rnd.uniform(0.3, 0.7)), "Partial"
            else:
                paid, pstatus = 0.0, "Unpaid"
            if paid:
                method = rnd.choices(["Cash", "Card", "Transfer"], weights=[62, 22, 16])[0]
                conn.execute(
                    "INSERT INTO payments (invoice_id,owner_id,amount,method,channel,"
                    "reference,received_by,received_at) VALUES (?,?,?,?,?,?,?,?)",
                    (inv_id, oid, paid, method,
                     {"Cash": "Cash", "Card": "Visa", "Transfer": "Instapay"}[method],
                     f"REF{rnd.randint(100000, 999999)}" if method != "Cash" else None,
                     "rec.mahmoud", _dt(day, hour + 1, 30)))
                stats["payments"] += 1
            conn.execute("UPDATE invoices SET status=?, paid_amount=?, due_amount=? WHERE id=?",
                         (pstatus, paid, _money(total - paid), inv_id))
            if pstatus != "Paid":
                conn.execute("UPDATE owners SET outstanding_balance = outstanding_balance + ?"
                             " WHERE id=?", (_money(total - paid), oid))
            if pstatus == "Paid" and total >= 500:
                conn.execute(
                    "INSERT INTO loyalty_points (owner_id,points,reason,ref_type,ref_id,"
                    "created_by,created_at) VALUES (?,?,?,?,?,?,?)",
                    (oid, int(total // 100), "Invoice settled", "invoice", inv_id,
                     "system", _dt(day, hour + 2)))
        conn.commit()
    return stats


def finish_inventory(conn, rnd: Random, today: date, items):
    """Run AFTER dispensing: guarantee the low-stock and adjustment views populate.

    Doing it here rather than at batch creation means six months of dispensing
    cannot silently undo it, and nothing has to predict consumption in advance.
    """
    wh = _one(conn, "SELECT id FROM warehouses ORDER BY id LIMIT 1")["id"]
    conn.execute("UPDATE batches SET quantity = 0 WHERE quantity < 0")
    low = 0
    for n, (sku, it) in enumerate(sorted(items.items())):
        if n % 5:
            continue
        rows = conn.execute("SELECT id, quantity FROM batches WHERE item_id=?"
                            " ORDER BY expiry_date", (it["id"],)).fetchall()
        target = it["reorder"] * 0.4
        for row in rows:
            keep = min(float(row["quantity"]), max(target, 0))
            target -= keep
            written_off = round(float(row["quantity"]) - keep, 1)
            if written_off <= 0:
                continue
            conn.execute("UPDATE batches SET quantity=? WHERE id=?", (round(keep, 1), row["id"]))
            conn.execute(
                "INSERT INTO stock_movements (item_id,batch_id,warehouse_id,movement_type,"
                "quantity,unit_cost,reference_type,reference_id,notes,created_by,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (it["id"], row["id"], wh, "adjustment", written_off, it["cost"],
                 "adjustment", None, "Stock count correction", "inv.tamer",
                 _dt(today - timedelta(days=rnd.randint(2, 25)), 17)))
        low += 1
    conn.commit()
    return low


def seed_grooming_boarding(conn, rnd: Random, today: date, pets):
    gs = conn.execute("SELECT id, name, price FROM grooming_services").fetchall()
    rooms = conn.execute("SELECT id, name, room_type, price_per_night FROM boarding_rooms").fetchall()
    n_groom = n_board = 0
    for offset in range(-150, 12):
        if rnd.random() < 0.42:
            day = today + timedelta(days=offset)
            pid, oid, species, _ = rnd.choice(pets)
            svc = rnd.choice(gs)
            conn.execute(
                "INSERT INTO grooming_bookings (pet_id,owner_id,service_id,groomer_name,"
                "booking_date,status,notes,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (pid, oid, svc["id"], "Nada Elshamy", day.isoformat(),
                 "Completed" if offset < 0 else
                 rnd.choice(["Scheduled", "Scheduled", "Confirmed"]),
                 ar("القط حساس من مجفف الشعر") if rnd.random() < 0.2 else None,
                 _dt(day - timedelta(days=2), 13)))
            n_groom += 1
        if rnd.random() < 0.16:
            check_in = today + timedelta(days=offset)
            nights = rnd.randint(2, 9)
            check_out = check_in + timedelta(days=nights)
            pid, oid, species, _ = rnd.choice(pets)
            room = rnd.choice([r for r in rooms if r["room_type"] != "ICU"])
            status = ("Checked-out" if check_out < today else
                      "Checked-in" if check_in <= today else "Booked")
            conn.execute(
                "INSERT INTO boarding_bookings (pet_id,owner_id,room_id,check_in,check_out,"
                "actual_checkout,status,feeding_instructions,medication_instructions,"
                "vet_notes,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, oid, room["id"], check_in.isoformat(), check_out.isoformat(),
                 check_out.isoformat() if status == "Checked-out" else None, status,
                 ar("وجبتين يومياً — دراي فود فقط"),
                 "Meloxicam 0.5ml once daily" if rnd.random() < 0.25 else None,
                 None, _dt(check_in - timedelta(days=4), 11)))
            n_board += 1
    conn.commit()
    return n_groom, n_board


def seed_inpatient(conn, rnd: Random, today: date, users, pets):
    n = 0
    for offset, status in [(-40, "Discharged"), (-14, "Discharged"), (-2, "Admitted")]:
        pid, oid, species, name = rnd.choice(pets)
        admitted = today + timedelta(days=offset)
        stay_id = _ins(conn,
            "INSERT INTO inpatient_stays (pet_id,owner_id,visit_id,ward,cage_number,"
            "admitted_by,reason,diagnosis,treatment_plan,status,admitted_at,"
            "expected_discharge,discharged_at,discharge_notes,daily_rate,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, oid, None, "General", f"C{rnd.randint(1, 12)}",
             users["dr.sara"]["id"],
             "Dehydration secondary to persistent vomiting",
             "Acute Gastroenteritis",
             "IV fluids, antiemetics, monitor hydration every 4 hours.",
             status, _dt(admitted, 14),
             (admitted + timedelta(days=3)).isoformat(),
             _dt(admitted + timedelta(days=3), 11) if status == "Discharged" else None,
             "Eating and drinking normally at discharge." if status == "Discharged" else None,
             500, _dt(admitted, 14)))
        n += 1
        for r in range(rnd.randint(2, 5)):
            conn.execute(
                "INSERT INTO inpatient_rounds (stay_id,recorded_by,round_time,temp_c,"
                "heart_rate,resp_rate,weight_kg,pain_score,food_intake,fluid_input,"
                "observations,treatment_given,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (stay_id, users["nurse.mariam"]["id"], _dt(admitted + timedelta(days=r // 2), 8 + (r % 2) * 8),
                 round(rnd.uniform(37.6, 39.4), 1), rnd.randint(80, 150),
                 rnd.randint(18, 36), round(rnd.uniform(3, 25), 1), rnd.randint(0, 3),
                 rnd.choice(["None", "Partial", "Full"]), round(rnd.uniform(50, 250), 1),
                 "Bright, alert and responsive." if r else "Quiet, mildly dehydrated.",
                 "Ringer's lactate 40 ml/h", _dt(admitted + timedelta(days=r // 2), 8)))
            conn.execute(
                "INSERT INTO inpatient_meds (stay_id,given_by,medication,dose,route,given_at,notes)"
                " VALUES (?,?,?,?,?,?,?)",
                (stay_id, users["nurse.ali"]["id"], "Metronidazole", "10 mg/kg", "IV",
                 _dt(admitted + timedelta(days=r // 2), 9), None))
    conn.commit()
    return n


def seed_petshop(conn, rnd: Random, today: date, owners, pets):
    cat_ids = []
    for name, name_ar in PS_CATEGORIES:
        cat_ids.append(_ins(conn,
            "INSERT INTO ps_categories (name,name_ar,is_active,created_at) VALUES (?,?,1,?)",
            (name, ar(name_ar), _dt(today - timedelta(days=300), 9))))
    products = []
    for ci, sku, name, name_ar, brand, cost, sell, stock, reorder in PS_PRODUCTS:
        pid = _ins(conn,
            "INSERT INTO ps_products (category_id,name,name_ar,sku,barcode,brand,species,"
            "cost_price,sell_price,tax_rate,reorder_level,stock_qty,unit,is_active,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
            (cat_ids[ci], name, ar(name_ar), sku,
             f"622{rnd.randint(1000000000, 9999999999)}", brand, "all",
             cost, sell, 0, reorder, stock, "unit",
             _dt(today - timedelta(days=300), 9)))
        products.append({"id": pid, "name": name, "price": sell, "stock": stock})
        conn.execute("INSERT INTO ps_stock_movements (product_id,movement,qty,ref_type,"
                     "notes,created_by,created_at) VALUES (?,?,?,?,?,?,?)",
                     (pid, "in", stock, "opening", "Opening stock", "inv.tamer",
                      _dt(today - timedelta(days=300), 9)))
    n_orders = 0
    for offset in range(-170, 1):
        for _ in range(rnd.choices([0, 1, 2, 3], weights=[35, 34, 21, 10])[0]):
            day = today + timedelta(days=offset)
            n_orders += 1
            oid = rnd.choice(owners) if rnd.random() < 0.7 else None
            pet_id = None
            if oid:
                match = [p for p in pets if p[1] == oid]
                pet_id = match[0][0] if match else None
            chosen = rnd.sample(products, rnd.randint(1, 4))
            subtotal = 0.0
            order_id = _ins(conn,
                "INSERT INTO ps_orders (order_number,owner_id,pet_id,source,status,subtotal,"
                "discount_amount,tax_amount,total,paid_amount,change_amount,payment_method,"
                "notes,served_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (f"PS-{day.strftime('%Y%m')}-{n_orders:04d}", oid, pet_id,
                 rnd.choice(["in-clinic", "in-clinic", "walk-in"]), "completed",
                 0, 0, 0, 0, 0, 0,
                 rnd.choices(["Cash", "Card", "Transfer"], weights=[65, 22, 13])[0],
                 None, "rec.yasmine", _dt(day, rnd.randint(11, 20))))
            for prod in chosen:
                q = float(rnd.randint(1, 3))
                line = _money(q * prod["price"])
                subtotal += line
                conn.execute(
                    "INSERT INTO ps_order_items (order_id,product_id,product_name,qty,"
                    "unit_price,discount,tax_rate,line_total) VALUES (?,?,?,?,?,0,0,?)",
                    (order_id, prod["id"], prod["name"], q, prod["price"], line))
                conn.execute("UPDATE ps_products SET stock_qty = stock_qty - ? WHERE id=?",
                             (q, prod["id"]))
                conn.execute(
                    "INSERT INTO ps_stock_movements (product_id,movement,qty,ref_type,ref_id,"
                    "notes,created_by,created_at) VALUES (?,?,?,?,?,?,?,?)",
                    (prod["id"], "out", q, "order", order_id, "POS sale", "rec.yasmine",
                     _dt(day, 12)))
            conn.execute("UPDATE ps_orders SET subtotal=?, total=?, paid_amount=? WHERE id=?",
                         (_money(subtotal), _money(subtotal), _money(subtotal), order_id))
    conn.commit()
    return len(products), n_orders


def seed_hr(conn, rnd: Random, today: date, users):
    for role, basic, ot in SALARY_GRADES:
        conn.execute("INSERT INTO salary_grades (role,basic_salary,overtime_rate,created_at)"
                     " VALUES (?,?,?,?)", (role, basic, ot, _dt(today - timedelta(days=400), 9)))
    grades = {r: (b, o) for r, b, o in SALARY_GRADES}

    n_att = 0
    for uname, u in users.items():
        for offset in range(-89, 1):
            day = today + timedelta(days=offset)
            if day.weekday() == 4:
                continue
            roll = rnd.random()
            if roll < 0.045:
                status, cin, cout, hours = "Absent", None, None, 0.0
            elif roll < 0.075:
                status = "On Leave"
                cin = cout = None
                hours = 0.0
            elif roll < 0.20:
                status = "Late"
                cin, cout = _dt(day, 9, rnd.randint(15, 55)), _dt(day, 17, rnd.randint(0, 40))
                hours = round(rnd.uniform(7.0, 8.2), 2)
            else:
                status = "Present"
                cin, cout = _dt(day, 8, rnd.randint(0, 14)), _dt(day, 17, rnd.randint(0, 55))
                hours = round(rnd.uniform(8.0, 9.5), 2)
            conn.execute(
                "INSERT INTO attendance_records (user_id,username,full_name,work_date,check_in,"
                "check_out,break_minutes,hours_worked,status,recorded_by,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (u["id"], uname, u["full_name"], day.isoformat(), cin, cout,
                 60 if status in ("Present", "Late") else 0, hours, status,
                 "hr.marwa", _dt(day, 18)))
            n_att += 1
            if status == "Present" and hours > 9.0:
                conn.execute(
                    "INSERT INTO overtime_log (user_id,work_date,hours,reason,approved_by,"
                    "status,created_at) VALUES (?,?,?,?,?,?,?)",
                    (u["id"], day.isoformat(), round(hours - 8, 1), "Emergency case after hours",
                     users["hr.marwa"]["id"],
                     rnd.choices(["Approved", "Pending"], weights=[80, 20])[0],
                     _dt(day, 19)))
        conn.commit()

    leave_types = {r["name"]: r["id"] for r in conn.execute(
        "SELECT id, name FROM leave_types").fetchall()}
    n_leave = 0
    for uname, u in users.items():
        for lt_name, allocated in [("Annual Leave", 21), ("Sick Leave", 14)]:
            lt = leave_types.get(lt_name)
            if not lt:
                continue
            used = rnd.randint(0, 9)
            conn.execute(
                "INSERT INTO leave_balances (user_id,leave_type_id,year,allocated,used,"
                "pending,remaining) VALUES (?,?,?,?,?,?,?)",
                (u["id"], lt, today.year, allocated, used, 0, allocated - used))
        if rnd.random() < 0.6:
            lt_name = rnd.choice(["Annual Leave", "Sick Leave", "Emergency Leave"])
            start = today + timedelta(days=rnd.randint(-70, 25))
            days_req = rnd.randint(1, 5)
            status = ("Pending" if start > today else
                      rnd.choices(["Approved", "Rejected"], weights=[85, 15])[0])
            conn.execute(
                "INSERT INTO leave_requests (user_id,username,full_name,leave_type_id,"
                "leave_type_name,start_date,end_date,days_requested,reason,status,approved_by,"
                "approved_at,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (u["id"], uname, u["full_name"], leave_types.get(lt_name, 1), lt_name,
                 start.isoformat(), (start + timedelta(days=days_req - 1)).isoformat(),
                 days_req, "Family commitment", status,
                 "hr.marwa" if status != "Pending" else None,
                 _dt(start - timedelta(days=3), 10) if status != "Pending" else None,
                 _dt(start - timedelta(days=6), 10)))
            n_leave += 1

    n_pay = 0
    for back in (3, 2, 1):
        anchor = (today.replace(day=1) - timedelta(days=1)) if back == 1 else None
        month_end = today.replace(day=1) - timedelta(days=1)
        for _ in range(back - 1):
            month_end = month_end.replace(day=1) - timedelta(days=1)
        y, m = month_end.year, month_end.month
        for uname, u in users.items():
            basic, ot_rate = grades.get(u["role"], (8000, 50))
            ot_hours = round(rnd.uniform(0, 14), 1)
            allowances = round(basic * 0.1, 2)
            absence = round(rnd.choice([0, 0, 0, basic / 26]), 2)
            tax = round(basic * 0.05, 2)
            gross = _money(basic + allowances + ot_hours * ot_rate)
            net = _money(gross - absence - tax)
            conn.execute(
                "INSERT INTO salaries (user_id,period_year,period_month,basic_salary,allowances,"
                "overtime_hours,overtime_rate,deductions,absence_deduction,tax_deduction,gross,"
                "net,status,payment_method,payment_date,created_by,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (u["id"], y, m, basic, allowances, ot_hours, ot_rate, 0, absence, tax,
                 gross, net, "Paid" if back > 1 else "Approved", "Bank Transfer",
                 month_end.isoformat(), users["hr.marwa"]["id"], _dt(month_end, 15)))
            n_pay += 1
    conn.commit()

    n_cert = n_rev = 0
    for uname, u in users.items():
        if u["role"] in ("doctor", "nurse", "pharmacist"):
            expiry = today + timedelta(days=rnd.choice([21, 45, 300, 700]))
            conn.execute(
                "INSERT INTO staff_certifications (user_id,cert_name,issued_by,cert_number,"
                "issue_date,expiry_date,status,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (u["id"], "Egyptian Veterinary Syndicate Licence",
                 "Egyptian Veterinary Syndicate", f"EVS-{rnd.randint(10000, 99999)}",
                 (today - timedelta(days=700)).isoformat(), expiry.isoformat(),
                 "Active", _dt(today - timedelta(days=700), 10)))
            n_cert += 1
        if rnd.random() < 0.7:
            conn.execute(
                "INSERT INTO performance_reviews (user_id,reviewer_id,period,rating,strengths,"
                "improvements,goals,status,reviewed_at,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (u["id"], users["owner.hossam"]["id"], f"{today.year}-H1",
                 rnd.randint(3, 5), "Reliable, good client communication.",
                 "Record-keeping could be more consistent.",
                 "Complete two CPD courses this year.", "Submitted",
                 (today - timedelta(days=45)).isoformat(),
                 _dt(today - timedelta(days=45), 14)))
            n_rev += 1
    conn.commit()
    return n_att, n_leave, n_pay, n_cert + n_rev


def seed_finance_extras(conn, rnd: Random, today: date):
    n_exp = 0
    for back in range(6):
        month_ref = today.replace(day=1) - timedelta(days=1)
        for _ in range(back):
            month_ref = month_ref.replace(day=1) - timedelta(days=1)
        for cat, desc, amount, vendor in EXPENSE_LINES:
            d = month_ref.replace(day=min(rnd.randint(2, 27), 28))
            conn.execute(
                "INSERT INTO expenses (branch_id,category,description,amount,vendor,receipt_ref,"
                "expense_date,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (1, cat, desc, _money(amount * rnd.uniform(0.85, 1.2)), vendor,
                 f"RCP-{rnd.randint(10000, 99999)}", d.isoformat(), "fin.dalia", _dt(d, 16)))
            n_exp += 1

    n_close = 0
    for offset in range(-60, 0):
        day = today + timedelta(days=offset)
        if day.weekday() == 4:
            continue
        row = _one(conn, "SELECT COALESCE(SUM(amount),0) AS s, "
                         "COALESCE(SUM(CASE WHEN method='Cash' THEN amount ELSE 0 END),0) AS c, "
                         "COALESCE(SUM(CASE WHEN method='Card' THEN amount ELSE 0 END),0) AS d, "
                         "COALESCE(SUM(CASE WHEN method='Transfer' THEN amount ELSE 0 END),0) AS t "
                         "FROM payments WHERE received_at LIKE ?", (f"{day.isoformat()}%",))
        exp = _one(conn, "SELECT COALESCE(SUM(amount),0) AS s FROM expenses WHERE expense_date=?",
                   (day.isoformat(),))["s"]
        conn.execute(
            "INSERT INTO daily_closings (branch_id,closing_date,cash_sales,card_sales,"
            "transfer_sales,total_sales,total_expenses,net_revenue,opening_cash,closing_cash,"
            "closed_by,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (1, day.isoformat(), _money(row["c"]), _money(row["d"]), _money(row["t"]),
             _money(row["s"]), _money(exp), _money(row["s"] - exp), 2000,
             _money(2000 + row["c"] - exp), "fin.dalia", _dt(day, 21)))
        n_close += 1
    conn.commit()
    return n_exp, n_close


def seed_comms(conn, rnd: Random, today: date, users):
    """WhatsApp log, notifications and an audit trail so those screens are live."""
    n_wa = 0
    rows = conn.execute(
        "SELECT r.id, r.owner_id, r.pet_id, r.message, o.phone FROM reminders r"
        " JOIN owners o ON o.id = r.owner_id LIMIT 120").fetchall()
    for r in rows:
        conn.execute(
            "INSERT INTO whatsapp_log (reminder_id,owner_id,pet_id,phone,message,"
            "template_name,status,http_status,sent_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (r["id"], r["owner_id"], r["pet_id"], r["phone"], r["message"],
             "appointment_reminder",
             rnd.choices(["Sent", "Sent", "Failed"], weights=[88, 8, 4])[0],
             200, _dt(today - timedelta(days=rnd.randint(1, 60)), 18)))
        n_wa += 1

    n_notif = 0
    for uname in ("owner.hossam", "dr.sara", "inv.tamer", "fin.dalia"):
        u = users[uname]
        for title, body, module, icon in [
            ("Stock below reorder level", "5 items need reordering.", "inventory", "📦"),
            ("Batch expiring soon", "3 batches expire within 60 days.", "inventory", "⏳"),
            ("Unpaid invoices", "Outstanding balance across 18 invoices.", "finance", "💰"),
            ("Vaccinations due", "12 pets are due a booster this month.", "clinical", "💉"),
        ]:
            conn.execute(
                "INSERT INTO notifications (recipient_id,recipient_role,title,body,icon,module,"
                "is_read,created_at) VALUES (?,?,?,?,?,?,?,?)",
                (u["id"], u["role"], title, body, icon, module,
                 1 if rnd.random() < 0.4 else 0,
                 _dt(today - timedelta(days=rnd.randint(0, 6)), rnd.randint(9, 19))))
            n_notif += 1

    n_audit = 0
    actions = [("create", "invoice", "finance"), ("update", "pet", "clinical"),
               ("create", "appointment", "appointments"), ("login", "user", "auth"),
               ("update", "item", "inventory"), ("delete", "appointment", "appointments")]
    unames = list(users)
    for i in range(240):
        act, ent, mod = rnd.choice(actions)
        u = users[rnd.choice(unames)]
        d = today - timedelta(days=rnd.randint(0, 60))
        conn.execute(
            "INSERT INTO audit_log (timestamp,user_id,username,role,action,module,entity_type,"
            "entity_id,details,ip) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_dt(d, rnd.randint(8, 21), rnd.randint(0, 59)), u["id"], u["username"],
             u["role"], act, mod, ent, str(rnd.randint(1, 400)),
             f"{act} {ent} via UI", "192.168.1." + str(rnd.randint(2, 254))))
        n_audit += 1
    conn.commit()
    return n_wa, n_notif, n_audit


# ── Blueprint-owned tables ────────────────────────────────────────────────────

def ensure_module_tables() -> None:
    """Create the tables that live in blueprint DDL rather than models._SCHEMA.

    Reuses the blueprints' own _ensure functions so the demo cannot drift from
    the shape the app actually creates. Their module-level "already ran" latches
    are reset afterwards, because that flag is keyed to nothing — leaving it set
    would make a later caller in the same process skip the DDL for a different
    database.
    """
    from blueprints.petshop import routes as ps_routes
    from blueprints.hr import routes as hr_routes
    from blueprints.payroll import routes as pay_routes

    ps_routes.ensure_petshop_tables()
    hr_routes._hr_ready = False
    hr_routes._ensure_hr_tables()
    hr_routes._hr_ready = False
    pay_routes._payroll_ready = False
    pay_routes._ensure_tables()
    pay_routes._payroll_ready = False


# ── Entry point ───────────────────────────────────────────────────────────────

def protected_paths() -> list:
    """Databases this script must never write to without --force.

    Both the configured path AND the built-in default. Guarding only
    Config.DATABASE_PATH would let a stray PLATFORM_DB_PATH in the environment
    disarm the protection on the one file that actually matters.
    """
    return [
        os.path.abspath(Config.DATABASE_PATH),
        os.path.abspath(os.path.join(_PLATFORM, "data", "platform.db")),
    ]


def resolve_guard(target: str, force: bool) -> str:
    """Return the absolute target path, or raise if it is a protected database."""
    abs_target = os.path.abspath(target)
    if not force and abs_target in protected_paths():
        raise SystemExit(
            f"REFUSING to seed a live application database:\n  {abs_target}\n"
            "Pass --db <path> to seed a throwaway file, or --force if you really "
            "mean to overwrite this one.\n"
            "(If PLATFORM_DB_PATH is set to your demo file, clear it before "
            "re-seeding — the seeder protects whatever the app is configured to use.)"
        )
    return abs_target


def resolve_pg_guard(dsn: str, force: bool) -> str:
    """Refuse to seed a PostgreSQL database that looks like production.

    The SQLite path has had a guard since it was written; this one did not
    exist because PostgreSQL was not seedable at all. Same principle: the
    seeder WIPES before it writes, so the name is the only thing between it and
    a live clinic.
    """
    name = (urlparse(dsn).path or "").lstrip("/").lower()
    if not name:
        raise SystemExit(f"--postgres needs a database name: {dsn!r}")
    if not force and not ("test" in name or "demo" in name or "staging" in name):
        raise SystemExit(
            f"REFUSING to seed the PostgreSQL database {name!r}.\n"
            "This script WIPES before it seeds. Name the database with test/demo/"
            "staging in it, or pass --force if you really mean this one.")
    return dsn


def run(target: str, force: bool = False, wipe_only: bool = False,
        quiet: bool = False, postgres: str = "") -> dict:
    """Seed `target`. Returns a dict of row counts. Idempotent: wipes first.

    `postgres` seeds a PostgreSQL DSN instead of a SQLite file. It was
    SQLite-only, which meant the production engine could not be demonstrated or
    load-tested with realistic data — and, less obviously, that the PostgreSQL
    test suite's data-integrity checks could never pass against a throwaway
    database. Everything below is unchanged: it all goes through get_db(), and
    the dialect translator handles the difference.
    """
    if postgres:
        dsn = resolve_pg_guard(postgres, force)
        u = urlparse(dsn)
        db.configure_postgres(host=u.hostname, port=u.port or 5432,
                              dbname=u.path.lstrip("/"),
                              user=unquote(u.username or "postgres"),
                              password=unquote(u.password or ""))
        if not db._PG_CONFIG:
            raise SystemExit(f"could not reach PostgreSQL at {u.hostname}:{u.port}")
    else:
        path = resolve_guard(target, force)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # use_sqlite(), not set_path(). set_path only assigns _db_path, and
        # _connect() consults the PostgreSQL pool FIRST -- so on a process
        # already connected to PostgreSQL (a server with POSTGRES_DSN set, or
        # anything that imported the app) this function wiped and reseeded the
        # LIVE PostgreSQL database while resolve_guard() happily approved the
        # harmless-looking file path it was handed. run() wipes before it seeds,
        # so that was a demo-data overwrite of a clinic's real records.
        db.use_sqlite(path)

    db.init_db(admin_user="admin", admin_pass=os.environ.get("DEMO_ADMIN_PASS", DEMO_PASSWORD))
    ensure_module_tables()

    rnd = Random(SEED)
    today = date.today()
    conn = db.get_db()
    try:
        wipe(conn)
        if wipe_only:
            return {"wiped": True}

        seed_clinic(conn)
        users = seed_staff(conn, rnd, today)
        owners, pets = seed_owners_pets(conn, rnd, today)
        items, suppliers, _wh = seed_inventory(conn, rnd, today)
        services = {r["code"]: dict(r) for r in conn.execute(
            "SELECT code, name, name_ar, standard_price FROM service_catalog").fetchall()}
        clinical = seed_clinical(conn, rnd, today, users, owners, pets, items, services)
        n_low = finish_inventory(conn, rnd, today, items)
        n_groom, n_board = seed_grooming_boarding(conn, rnd, today, pets)
        n_inpatient = seed_inpatient(conn, rnd, today, users, pets)
        n_products, n_ps_orders = seed_petshop(conn, rnd, today, owners, pets)
        n_att, n_leave, n_pay, n_hr = seed_hr(conn, rnd, today, users)
        n_exp, n_close = seed_finance_extras(conn, rnd, today)
        n_wa, n_notif, n_audit = seed_comms(conn, rnd, today, users)

        counts = dict(
            staff=len(users), owners=len(owners), pets=len(pets),
            items=len(items), suppliers=len(suppliers), low_stock_items=n_low,
            grooming=n_groom, boarding=n_board, inpatient=n_inpatient,
            shop_products=n_products, shop_orders=n_ps_orders,
            attendance=n_att, leave_requests=n_leave, payslips=n_pay, hr_records=n_hr,
            expenses=n_exp, daily_closings=n_close,
            whatsapp=n_wa, notifications=n_notif, audit=n_audit,
            **clinical,
        )
    finally:
        conn.close()

    if not quiet:
        where = (f"PostgreSQL {urlparse(postgres).path.lstrip('/')}"
                 f" on {urlparse(postgres).hostname}" if postgres else path)
        print(f"\nDemo dataset written to {where}\n")
        for k in sorted(counts):
            print(f"  {k:<16} {counts[k]}")
        print(f"\n  login: admin / {os.environ.get('DEMO_ADMIN_PASS', DEMO_PASSWORD)}")
        print(f"  staff: dr.sara, rec.yasmine, fin.dalia, ... / {DEMO_PASSWORD}\n")
    return counts


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/demo.db",
                   help="target SQLite file (default: data/demo.db)")
    p.add_argument("--force", action="store_true",
                   help="allow writing to the configured application database")
    p.add_argument("--wipe", action="store_true",
                   help="clear the demo scope and stop, without re-seeding")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--postgres", default="", metavar="DSN",
                   help="seed a PostgreSQL database instead of a SQLite file, "
                        "e.g. postgresql://user:pass@host:5432/vetclinic_demo")
    a = p.parse_args(argv)
    run(a.db, force=a.force, wipe_only=a.wipe, quiet=a.quiet, postgres=a.postgres)
    return 0


if __name__ == "__main__":
    sys.exit(main())
