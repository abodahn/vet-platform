"""
Seed dummy data for the Pet Shop module.
Run: python seed_petshop.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
import models.database as db
from datetime import datetime, timedelta
import random

db.set_path(Config.DATABASE_PATH)
conn = db.get_db()

# ── Ensure tables exist ────────────────────────────────────────────────────────
conn.executescript("""
CREATE TABLE IF NOT EXISTS ps_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, name_ar TEXT, description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ps_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER, name TEXT NOT NULL, name_ar TEXT,
    sku TEXT UNIQUE, barcode TEXT, brand TEXT,
    species TEXT DEFAULT 'all', description TEXT,
    cost_price REAL DEFAULT 0, sell_price REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0, reorder_level INTEGER DEFAULT 5,
    stock_qty INTEGER DEFAULT 0, unit TEXT DEFAULT 'unit',
    is_active INTEGER DEFAULT 1, image_url TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ps_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number TEXT UNIQUE, owner_id INTEGER, pet_id INTEGER,
    source TEXT DEFAULT 'in-clinic', status TEXT DEFAULT 'draft',
    subtotal REAL DEFAULT 0, discount_amount REAL DEFAULT 0,
    tax_amount REAL DEFAULT 0, total REAL DEFAULT 0,
    paid_amount REAL DEFAULT 0, change_amount REAL DEFAULT 0,
    payment_method TEXT DEFAULT 'cash', payment_ref TEXT,
    notes TEXT, served_by TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS ps_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
    product_name TEXT, qty REAL DEFAULT 1,
    unit_price REAL DEFAULT 0, discount REAL DEFAULT 0,
    tax_rate REAL DEFAULT 0, line_total REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS ps_stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL, movement TEXT NOT NULL,
    qty REAL NOT NULL, ref_type TEXT, ref_id INTEGER,
    notes TEXT, created_by TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
""")

# ── Categories ─────────────────────────────────────────────────────────────────
categories = [
    ("Dog Food",      "طعام الكلاب",    "Dry and wet food for dogs"),
    ("Cat Food",      "طعام القطط",     "Dry and wet food for cats"),
    ("Treats",        "مكافآت",         "Snacks and training treats"),
    ("Accessories",   "إكسسوارات",      "Collars, leashes, beds, toys"),
    ("Grooming",      "العناية",        "Shampoos, brushes, nail clippers"),
    ("Health & Care", "الصحة والعناية", "Vitamins, dewormers, flea control"),
    ("Bird Supplies", "مستلزمات الطيور","Seeds, cages, perches"),
    ("Aquarium",      "الأحواض",        "Fish food, filters, decorations"),
]
cat_ids = {}
for name, name_ar, desc in categories:
    cur = conn.execute(
        "INSERT OR IGNORE INTO ps_categories(name,name_ar,description) VALUES(?,?,?)",
        (name, name_ar, desc)
    )
    if cur.lastrowid:
        cat_ids[name] = cur.lastrowid
    else:
        row = conn.execute("SELECT id FROM ps_categories WHERE name=?", (name,)).fetchone()
        cat_ids[name] = row[0]

conn.commit()
print(f"  OK {len(cat_ids)} categories")

# ── Products ───────────────────────────────────────────────────────────────────
products = [
    # (name, name_ar, sku, brand, species, category, cost, sell, stock, unit, reorder)
    ("Royal Canin Adult Dog 3kg",    "رويال كانين كلاب بالغة 3كج",  "RC-DOG-AD-3KG",  "Royal Canin", "dog",    "Dog Food",      180, 280, 25, "bag",    5),
    ("Royal Canin Adult Dog 10kg",   "رويال كانين كلاب بالغة 10كج", "RC-DOG-AD-10KG", "Royal Canin", "dog",    "Dog Food",      520, 780, 12, "bag",    3),
    ("Purina Pro Plan Puppy 3kg",    "بيورينا برو بلان جرو 3كج",    "PP-PUP-3KG",     "Purina",      "dog",    "Dog Food",      160, 250, 18, "bag",    5),
    ("Hills Science Diet Dog 4kg",   "هيلز سايانس دايت كلاب 4كج",  "HS-DOG-4KG",     "Hill's",      "dog",    "Dog Food",      220, 340, 10, "bag",    3),
    ("Royal Canin Adult Cat 2kg",    "رويال كانين قطط بالغة 2كج",   "RC-CAT-AD-2KG",  "Royal Canin", "cat",    "Cat Food",      130, 210, 30, "bag",    8),
    ("Royal Canin Kitten 2kg",       "رويال كانين هرايرة 2كج",      "RC-CAT-KIT-2KG", "Royal Canin", "cat",    "Cat Food",      140, 220, 20, "bag",    5),
    ("Whiskas Adult Pouch 85g",      "ويسكاس أكياس بالغة 85جم",     "WK-CAT-P85G",    "Whiskas",     "cat",    "Cat Food",       8,  15, 60, "unit",  15),
    ("Friskies Cat Dry 1.5kg",       "فريسكيز قطط جاف 1.5كج",       "FR-CAT-1.5KG",   "Friskies",    "cat",    "Cat Food",       55,  90, 35, "bag",    8),
    ("Pedigree Dentastix Dog",       "بيديجري عيدان أسنان كلاب",    "PD-DOG-DSTX",    "Pedigree",    "dog",    "Treats",         35,  60, 40, "pack",  10),
    ("Temptations Cat Treats 85g",   "تيمبتيشنز مكافآت قطط 85جم",   "TM-CAT-85G",     "Temptations", "cat",    "Treats",         18,  35, 50, "pack",  10),
    ("Milk-Bone Dog Biscuits",       "ميلك بون بسكويت كلاب",        "MB-DOG-BISC",    "Milk-Bone",   "dog",    "Treats",         25,  45, 30, "pack",   8),
    ("Dog Collar Adjustable Medium", "طوق كلب متعدد الأحجام وسط",   "COL-DOG-MED",    "PetSafe",     "dog",    "Accessories",    40,  85,  8, "unit",   3),
    ("Cat Collar with Bell",         "طوق قطة مع جرس",              "COL-CAT-BL",     "Trixie",      "cat",    "Accessories",    20,  45, 12, "unit",   4),
    ("Retractable Dog Leash 5m",     "سير كلب متراجع 5 متر",        "LSH-DOG-5M",     "Flexi",       "dog",    "Accessories",    85, 160,  6, "unit",   2),
    ("Cat Scratching Post 60cm",     "عمود خدش قطط 60سم",           "SCR-CAT-60",     "Trixie",      "cat",    "Accessories",    90, 175,  5, "unit",   2),
    ("Dog Shampoo Anti-Flea 250ml",  "شامبو كلاب مضاد للبراغيث 250مل","SH-DOG-AFL",   "Virbac",      "dog",    "Grooming",       45,  90, 20, "bottle", 5),
    ("Cat Shampoo 200ml",            "شامبو قطط 200مل",              "SH-CAT-200",     "Beaphar",     "cat",    "Grooming",       35,  70, 15, "bottle", 5),
    ("Pet Nail Clipper",             "مقص أظافر حيوانات",           "NC-PET-STD",     "Safari",      "all",    "Grooming",       25,  55, 10, "unit",   3),
    ("Slicker Brush Dog/Cat",        "فرشاة تنظيف متعددة الاستخدام","BR-PET-SL",      "Safari",      "all",    "Grooming",       30,  65, 14, "unit",   4),
    ("Frontline Spot-On Dog M",      "فرونت لاين نقط للكلاب M",     "FL-DOG-M",       "Frontline",   "dog",    "Health & Care",  65, 130,  3, "unit",   2),
    ("Frontline Spot-On Cat",        "فرونت لاين نقط للقطط",        "FL-CAT",         "Frontline",   "cat",    "Health & Care",  55, 115,  3, "unit",   2),
    ("Drontal Dog Dewormer",         "درونتال مضاد الديدان كلاب",   "DW-DOG-DRN",     "Bayer",       "dog",    "Health & Care",  20,  45, 15, "unit",   5),
    ("Drontal Cat Dewormer",         "درونتال مضاد الديدان قطط",    "DW-CAT-DRN",     "Bayer",       "cat",    "Health & Care",  18,  40, 12, "unit",   5),
    ("Canvit Multi Vitamin Dog",     "كانفيت فيتامينات متعددة كلاب","VIT-DOG-CV",     "Canvit",      "dog",    "Health & Care",  55, 110, 10, "unit",   3),
    ("Budgie Seed Mix 500g",         "بذور بادجي مخلوطة 500جم",     "BD-SEED-500",    "Versele-Laga","bird",   "Bird Supplies",  15,  30, 20, "bag",    5),
    ("Parrot Pellets 1kg",           "حبيبات ببغاء 1كج",            "PR-PELL-1KG",    "Harrison's",  "bird",   "Bird Supplies",  60, 120,  8, "bag",    3),
    ("Cuttlefish Bone",              "عظمة السيبيا للطيور",          "CTF-BONE",       "Trixie",      "bird",   "Bird Supplies",   8,  18, 25, "unit",   8),
    ("Tropical Fish Food 100g",      "طعام أسماك استوائية 100جم",   "FF-TROP-100",    "Tetra",       "fish",   "Aquarium",       20,  40, 18, "unit",   5),
    ("Aquarium Filter Sponge",       "إسفنجة فلتر أكواريوم",        "AQ-FILT-SP",     "Tetra",       "fish",   "Aquarium",       12,  28, 10, "unit",   4),
    ("Water Conditioner 100ml",      "معالج مياه أكواريوم 100مل",   "AQ-COND-100",    "API",         "fish",   "Aquarium",       25,  55,  8, "bottle", 3),
]

prod_ids = []
for (name, name_ar, sku, brand, species, cat_name, cost, sell, stock, unit, reorder) in products:
    cat_id = cat_ids.get(cat_name)
    try:
        cur = conn.execute(
            """INSERT OR IGNORE INTO ps_products
               (category_id,name,name_ar,sku,brand,species,cost_price,sell_price,
                stock_qty,unit,reorder_level,is_active)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,1)""",
            (cat_id, name, name_ar, sku, brand, species, cost, sell, stock, unit, reorder)
        )
        if cur.lastrowid:
            prod_ids.append((cur.lastrowid, name, sell, stock))
            # Opening stock movement
            conn.execute(
                "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,created_by) VALUES(?,?,?,?,?)",
                (cur.lastrowid, "in", stock, "opening_stock", "seed")
            )
        else:
            row = conn.execute("SELECT id,name,sell_price,stock_qty FROM ps_products WHERE sku=?", (sku,)).fetchone()
            if row:
                prod_ids.append((row[0], row[1], row[2], row[3]))
    except Exception as e:
        print(f"  Skip {sku}: {e}")

conn.commit()
print(f"  OK {len(prod_ids)} products")

# ── Orders (last 30 days) ──────────────────────────────────────────────────────
pay_methods = ["cash", "cash", "cash", "card", "instapay"]
statuses    = ["paid", "paid", "paid", "paid", "cancelled"]

order_count = 0
for days_ago in range(29, -1, -1):
    num_orders = random.randint(1, 5)
    for _ in range(num_orders):
        dt = datetime.utcnow() - timedelta(days=days_ago,
             hours=random.randint(8,20), minutes=random.randint(0,59))
        dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")

        items = random.sample(prod_ids, random.randint(1, 4))
        pay   = random.choice(pay_methods)
        stat  = random.choice(statuses)
        disc  = random.choice([0, 0, 0, 10, 20, 50])

        subtotal = sum(p[2] * random.randint(1, 3) for p in items)
        total    = max(0, subtotal - disc)
        paid     = total if pay != "cash" else total + random.choice([0, 5, 10, 25, 50])
        change   = max(0, paid - total)

        order_num = f"PS-{dt.strftime('%Y%m')}-{order_count+1:04d}"
        cur = conn.execute(
            """INSERT INTO ps_orders
               (order_number,status,subtotal,discount_amount,total,
                paid_amount,change_amount,payment_method,served_by,created_at,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
            (order_num, stat, subtotal, disc, total,
             paid, change, pay, "admin", dt_str, dt_str)
        )
        oid = cur.lastrowid

        for pid, pname, price, _ in items:
            qty   = random.randint(1, 3)
            ltotal = qty * price
            conn.execute(
                """INSERT INTO ps_order_items
                   (order_id,product_id,product_name,qty,unit_price,line_total)
                   VALUES(?,?,?,?,?,?)""",
                (oid, pid, pname, qty, price, ltotal)
            )
            if stat == "paid":
                conn.execute(
                    "INSERT INTO ps_stock_movements(product_id,movement,qty,ref_type,ref_id,created_by,created_at) VALUES(?,?,?,?,?,?,?)",
                    (pid, "out", qty, "sale", oid, "admin", dt_str)
                )

        order_count += 1

conn.commit()
print(f"  OK {order_count} orders (last 30 days)")
conn.close()
print("")
print("Pet Shop dummy data seeded successfully!")
print("Open http://localhost:5100/petshop/ to see it.")
