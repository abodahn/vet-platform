"""
Patient 360 — the pet record as a complete clinical picture, and the owner
record as a complete relationship.

SQLite, no network. Every fixture builds its own owner/pet so the session-scoped
database shared with the rest of the suite cannot make an assertion pass or fail
by accident.

`imaging_studies`, `telemedicine_sessions` and `ps_orders` are NOT in the core
schema — imaging_studies is only created by the PostgreSQL migration path and
the demo seed, the other two by their own blueprint the first time it is opened.
_optional_tables() creates them here so the populated case can be asserted, and
test_missing_optional_table_is_not_an_error drops one back out again to prove
the CRM page treats an unopened module as an expected state rather than a 500.
"""
import pytest

import models.database as db


# ── Fixtures ──────────────────────────────────────────────────────────────────

_IMAGING_DDL = """
CREATE TABLE IF NOT EXISTS imaging_studies (
    id INTEGER PRIMARY KEY AUTOINCREMENT, pet_id INTEGER NOT NULL,
    owner_id INTEGER, visit_id INTEGER, study_type TEXT NOT NULL,
    body_region TEXT, file_path TEXT, notes TEXT, ai_analysis TEXT,
    created_by TEXT, created_at TEXT)
"""
_TELEMED_DDL = """
CREATE TABLE IF NOT EXISTS telemedicine_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, owner_id INTEGER NOT NULL,
    pet_id INTEGER, doctor_name TEXT, scheduled_at TEXT NOT NULL,
    duration_min INTEGER, room_token TEXT, room_url TEXT, status TEXT,
    chief_complaint TEXT, notes TEXT, prescription_id INTEGER,
    invoice_id INTEGER, created_by TEXT, created_at TEXT,
    started_at TEXT, ended_at TEXT)
"""
_PS_ORDERS_DDL = """
CREATE TABLE IF NOT EXISTS ps_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT, order_number TEXT, owner_id INTEGER,
    pet_id INTEGER, source TEXT, status TEXT, subtotal REAL, discount_amount REAL,
    tax_amount REAL, total REAL, paid_amount REAL, change_amount REAL,
    payment_method TEXT, payment_ref TEXT, notes TEXT, served_by TEXT,
    invoice_id INTEGER, created_at TEXT, updated_at TEXT)
"""


def _optional_tables(conn):
    for ddl in (_IMAGING_DDL, _TELEMED_DDL, _PS_ORDERS_DDL):
        conn.execute(ddl)


@pytest.fixture(scope="module")
def full_pet(app):
    """An owner + pet carrying one record in every module the timeline covers.

    Module-scoped: invoice_number is UNIQUE, and rebuilding this per test would
    collide. The database is shared with the rest of the suite, so everything
    here is namespaced to its own owner.
    """
    with app.app_context():
        conn = db.get_db()
        _optional_tables(conn)
        with conn:
            cur = conn.execute(
                "INSERT INTO owners (full_name, phone, loyalty_balance) VALUES (?,?,?)",
                ("Three-Sixty Owner", "01000000360", 0))
            oid = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species, breed) VALUES (?,?,?,?)",
                (oid, "Kanaria", "Cat", "Shirazi"))
            pid = cur.lastrowid

            cur = conn.execute(
                "INSERT INTO visits (owner_id, pet_id, visit_date, visit_type,"
                " chief_complaint, status, weight_kg) VALUES (?,?,?,?,?,?,?)",
                (oid, pid, "2026-03-01", "Consultation", "Lethargy", "Completed", 4.2))
            vid = cur.lastrowid

            conn.execute(
                "INSERT INTO diagnoses (visit_id, pet_id, diagnosis, severity)"
                " VALUES (?,?,?,?)", (vid, pid, "Feline lower urinary tract disease", "Severe"))
            cur = conn.execute(
                "INSERT INTO prescriptions (visit_id, pet_id, owner_id, prescribed_by,"
                " status, created_at) VALUES (?,?,?,?,?,?)",
                (vid, pid, oid, "Dr. Sara", "Active", "2026-03-01"))
            rxid = cur.lastrowid
            conn.execute(
                "INSERT INTO prescription_items (prescription_id, medication_name,"
                " dosage) VALUES (?,?,?)", (rxid, "Meloxicam", "0.1 mg/kg"))
            conn.execute(
                "INSERT INTO vaccinations (pet_id, vaccine_name, administered_at,"
                " next_due_at) VALUES (?,?,?,?)",
                (pid, "Rabies", "2026-02-01", "2027-02-01"))
            conn.execute(
                "INSERT INTO surgeries (pet_id, procedure_name, surgery_date, outcome)"
                " VALUES (?,?,?,?)", (pid, "Cystotomy", "2026-03-05", "Successful"))
            conn.execute(
                "INSERT INTO lab_requests (visit_id, pet_id, test_name, status,"
                " created_at) VALUES (?,?,?,?,?)",
                (vid, pid, "Urinalysis", "Completed", "2026-03-02"))
            conn.execute(
                "INSERT INTO grooming_bookings (pet_id, owner_id, booking_date, status)"
                " VALUES (?,?,?,?)", (pid, oid, "2026-01-20", "Completed"))
            conn.execute(
                "INSERT INTO boarding_bookings (pet_id, owner_id, check_in, check_out,"
                " status) VALUES (?,?,?,?,?)",
                (pid, oid, "2026-02-10", "2026-02-14", "Checked-Out"))
            conn.execute(
                "INSERT INTO inpatient_stays (pet_id, owner_id, admitted_by, reason,"
                " ward, status, admitted_at) VALUES (?,?,?,?,?,?,?)",
                (pid, oid, 1, "Post-operative monitoring", "ICU", "Discharged", "2026-03-05"))
            conn.execute(
                "INSERT INTO followups (visit_id, pet_id, owner_id, due_date, reason,"
                " status) VALUES (?,?,?,?,?,?)",
                (vid, pid, oid, "2026-04-01", "Recheck urine", "Pending"))
            conn.execute(
                "INSERT INTO imaging_studies (pet_id, owner_id, visit_id, study_type,"
                " body_region, created_at) VALUES (?,?,?,?,?,?)",
                (pid, oid, vid, "Ultrasound", "Abdomen", "2026-03-03"))
            conn.execute(
                "INSERT INTO telemedicine_sessions (owner_id, pet_id, scheduled_at,"
                " room_token, room_url, status, chief_complaint) VALUES (?,?,?,?,?,?,?)",
                (oid, pid, "2026-03-20", "TOK360", "https://example.invalid/r", "Completed",
                 "Post-op check"))
            conn.execute(
                "INSERT INTO ps_orders (order_number, owner_id, pet_id, status, total,"
                " created_at) VALUES (?,?,?,?,?,?)",
                ("PS-360-1", oid, pid, "paid", 240.0, "2026-03-08"))

            # Two invoices: one settled, one still owed. Balance must be 150.00.
            conn.execute(
                "INSERT INTO invoices (invoice_number, owner_id, pet_id, issue_date,"
                " status, total, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?,?)",
                ("INV-360-1", oid, pid, "2026-03-01", "Paid", 500.0, 500.0, 0.0))
            conn.execute(
                "INSERT INTO invoices (invoice_number, owner_id, pet_id, issue_date,"
                " status, total, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?,?)",
                ("INV-360-2", oid, pid, "2026-03-06", "Partial", 400.0, 250.0, 150.0))
            # A cancelled invoice must NOT count towards the outstanding balance.
            conn.execute(
                "INSERT INTO invoices (invoice_number, owner_id, pet_id, issue_date,"
                " status, total, paid_amount, due_amount) VALUES (?,?,?,?,?,?,?,?)",
                ("INV-360-3", oid, pid, "2026-03-07", "Cancelled", 900.0, 0.0, 900.0))

            conn.execute(
                "INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
                " status, appointment_type) VALUES (?,?,?,?,?,?)",
                (oid, pid, "2026-02-20", "10:00", "No-Show", "Consultation"))
            conn.execute(
                "INSERT INTO appointments (owner_id, pet_id, appt_date, appt_start,"
                " status, appointment_type) VALUES (?,?,?,?,?,?)",
                (oid, pid, "2026-03-01", "11:00", "Completed", "Consultation"))
            conn.execute(
                "INSERT INTO whatsapp_log (owner_id, pet_id, phone, message,"
                " template_name, status, sent_at) VALUES (?,?,?,?,?,?,?)",
                (oid, pid, "01000000360", "Kanaria's results are ready.",
                 "lab_ready", "Sent", "2026-03-03"))
            conn.execute(
                "INSERT INTO reminders (owner_id, pet_id, reminder_type, message,"
                " channel, scheduled_for, status) VALUES (?,?,?,?,?,?,?)",
                (oid, pid, "followup", "Recheck due", "WhatsApp", "2026-04-01", "Pending"))
        conn.close()
    return {"owner_id": oid, "pet_id": pid, "visit_id": vid}


@pytest.fixture(scope="module")
def bare_pet(app):
    """An owner + pet with a single visit and nothing else anywhere."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO owners (full_name, phone) VALUES (?,?)",
                ("Sparse Owner", "01000000001"))
            oid = cur.lastrowid
            cur = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                (oid, "Onlyvisit", "Dog"))
            pid = cur.lastrowid
            conn.execute(
                "INSERT INTO visits (owner_id, pet_id, visit_date, visit_type, status)"
                " VALUES (?,?,?,?,?)", (oid, pid, "2026-03-10", "Consultation", "Open"))
        conn.close()
    return {"owner_id": oid, "pet_id": pid}


# ── 1. The pet record shows every module ──────────────────────────────────────

def test_pet_page_shows_every_module(auth_client, full_pet):
    html = auth_client.get(f"/crm/pets/{full_pet['pet_id']}").get_data(as_text=True)

    # From db.get_pet_timeline()
    assert "Consultation" in html                 # visit
    assert "Rabies" in html                       # vaccination
    assert "Cystotomy" in html                    # surgery
    assert "Urinalysis" in html                   # lab request
    assert "INV-360-2" in html                    # invoice

    # Added by the CRM blueprint
    assert "Feline lower urinary tract disease" in html   # diagnosis
    assert "Prescription" in html
    assert "Ultrasound" in html                   # imaging study
    assert "Post-operative monitoring" in html    # inpatient stay
    assert "Boarding stay" in html
    assert "Telemedicine session" in html
    assert "PS-360-1" in html                     # pet shop purchase
    assert "Recheck urine" in html                # follow-up due


def _assert_resolves(adapter, url):
    """Raise unless `url` matches a real rule. A 308 slash-redirect still counts
    as resolving — Flask serves it — so only NotFound is a dead link."""
    from werkzeug.routing.exceptions import RequestRedirect
    try:
        adapter.match(url, method="GET", query_args="")
    except RequestRedirect:
        pass


def test_pet_page_links_all_resolve(app, auth_client, full_pet):
    """Every href the timeline emits must match a real rule in the URL map."""
    import re
    html = auth_client.get(f"/crm/pets/{full_pet['pet_id']}").get_data(as_text=True)
    adapter = app.url_map.bind("localhost")
    hrefs = {h.split("?")[0] for h in re.findall(r'href="(/[^"#]*)"', html)}
    for href in hrefs:
        _assert_resolves(adapter, href)


def test_pet_timeline_is_newest_first(auth_client, full_pet):
    html = auth_client.get(f"/crm/pets/{full_pet['pet_id']}").get_data(as_text=True)
    # Follow-up due 2026-04-01 sorts above the 2026-01-20 grooming booking.
    assert html.index("Recheck urine") < html.index("2026-01-20")


# ── 2. A pet with only a visit renders cleanly ────────────────────────────────

def test_bare_pet_renders_cleanly(auth_client, bare_pet):
    resp = auth_client.get(f"/crm/pets/{bare_pet['pet_id']}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Onlyvisit" in html
    # No empty tables or orphan headings for modules with nothing to show.
    for absent in ("Boarding stay", "Telemedicine session", "Inpatient admission",
                   "Imaging study", "Pet shop purchase", "Follow-up due"):
        assert absent not in html
    # The vaccination panel shows its empty state rather than a headerless table.
    assert "No vaccinations recorded yet." in html


def test_missing_optional_table_is_not_an_error(app, auth_client, bare_pet):
    """An unopened module has no table. That is a normal state, not a 500."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DROP TABLE IF EXISTS telemedicine_sessions")
        conn.close()
    try:
        assert auth_client.get(f"/crm/pets/{bare_pet['pet_id']}").status_code == 200
    finally:
        with app.app_context():
            conn = db.get_db()
            with conn:
                conn.execute(_TELEMED_DDL)
            conn.close()


# ── 3. The owner record ───────────────────────────────────────────────────────

def test_owner_page_outstanding_balance(auth_client, full_pet):
    """400 partly paid (150 due) + 500 paid + 900 cancelled  ->  150.00 due."""
    html = auth_client.get(f"/crm/owners/{full_pet['owner_id']}").get_data(as_text=True)
    assert "150.00" in html
    assert "900.00" not in html.split("Appointment History")[0].split("Outstanding")[1][:200]


def test_owner_page_shows_the_whole_relationship(auth_client, full_pet):
    html = auth_client.get(f"/crm/owners/{full_pet['owner_id']}").get_data(as_text=True)
    assert "Kanaria" in html               # their pets
    assert "INV-360-2" in html             # invoices
    assert "No-Show" in html               # appointment history including no-shows
    assert "lab_ready" in html             # communication history (sent)
    assert "followup" in html              # communication history (queued reminder)
    assert "Loyalty Points" in html


def test_owner_page_links_all_resolve(app, auth_client, full_pet):
    import re
    html = auth_client.get(f"/crm/owners/{full_pet['owner_id']}").get_data(as_text=True)
    adapter = app.url_map.bind("localhost")
    for href in {h.split("?")[0] for h in re.findall(r'href="(/[^"#]*)"', html)}:
        _assert_resolves(adapter, href)


def test_owner_stats_balance_matches_finance_definition(app, full_pet):
    from blueprints.crm.routes import _get_owner_stats
    with app.app_context():
        conn = db.get_db()
        stats = _get_owner_stats(conn, full_pet["owner_id"])
        conn.close()
    assert stats["balance"] == pytest.approx(150.0)
    assert stats["visit_count"] == 1


def test_owner_with_nothing_renders(auth_client, bare_pet):
    resp = auth_client.get(f"/crm/owners/{bare_pet['owner_id']}")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "No invoices issued yet." in html
    assert "No appointments booked yet." in html


# ── 4. Query cost — constant, not one per record ──────────────────────────────

def test_pet_page_query_count_does_not_grow_with_history(app, auth_client, full_pet):
    """The page must cost the same whether the animal has one record per module
    or fifty. A count that tracks row count means an N+1 crept in."""
    import models.database as m

    counter = {"n": 0}
    original = m._SQLiteCursor.execute

    def counting(self, sql, params=()):
        counter["n"] += 1
        return original(self, sql, params)

    m._SQLiteCursor.execute = counting
    try:
        auth_client.get(f"/crm/pets/{full_pet['pet_id']}")
        baseline = counter["n"]

        with app.app_context():
            conn = db.get_db()
            with conn:
                for i in range(40):
                    conn.execute(
                        "INSERT INTO diagnoses (visit_id, pet_id, diagnosis)"
                        " VALUES (?,?,?)",
                        (full_pet["visit_id"], full_pet["pet_id"], f"Extra dx {i}"))
                    conn.execute(
                        "INSERT INTO boarding_bookings (pet_id, owner_id, check_in,"
                        " status) VALUES (?,?,?,?)",
                        (full_pet["pet_id"], full_pet["owner_id"], "2026-01-01", "Booked"))
            conn.close()

        counter["n"] = 0
        auth_client.get(f"/crm/pets/{full_pet['pet_id']}")
        grown = counter["n"]
    finally:
        m._SQLiteCursor.execute = original

    assert grown == baseline, (
        f"query count grew from {baseline} to {grown} after adding 80 rows")


# ── 5. Discoverability — CDS reachable from the launcher ──────────────────────

def test_cds_is_in_the_launcher_for_a_doctor():
    from blueprints.launcher.routes import MODULES, _visible_modules
    ids = {m["id"] for m in _visible_modules("doctor")}
    assert "cds" in ids
    cds = next(m for m in MODULES if m["id"] == "cds")
    assert cds["url"] == "/cds/"


def test_new_module_roles_are_all_seeded_roles():
    """A role string that is not in _SEED_ROLES silently matches nobody.

    tests/test_role_consistency.py enforces this across the whole blueprint tree
    (with the pre-existing "staff" entry parked pending a product decision).
    This narrower check pins the modules added for discoverability so a typo in
    one of them fails here, next to the change that would cause it.
    """
    from blueprints.launcher.routes import MODULES
    seeded = {r[0] for r in db._SEED_ROLES}
    added = {"cds", "imaging", "inpatient", "telemedicine", "payroll", "visits"}
    for m in MODULES:
        if m["id"] not in added:
            continue
        unknown = set(m["roles"]) - seeded
        assert not unknown, f"module {m['id']} lists unseeded role(s): {sorted(unknown)}"


def test_launcher_module_urls_resolve(app):
    """Every non-legacy module url must be a real route."""
    from blueprints.launcher.routes import MODULES
    adapter = app.url_map.bind("localhost")
    for m in MODULES:
        url = m.get("url")
        if not url or m.get("legacy"):
            continue
        _assert_resolves(adapter, url.split("?")[0])


def test_cds_page_is_reachable(auth_client):
    assert auth_client.get("/cds/").status_code == 200
