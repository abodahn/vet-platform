-- 0001_baseline.sql — FROZEN SNAPSHOT. Do not edit; add a new revision instead.
--
-- Captured verbatim from models/database.py:_SCHEMA plus the ad-hoc ALTERs that
-- init_db() applies right after it. This is written in the SQLite dialect the
-- application itself uses; the revision script runs it through
-- models.database._fix_sql() when the target is PostgreSQL, exactly as the app does.
--
-- Seed data (roles, categories, WhatsApp templates, service catalog, shifts,
-- leave types, rooms, admin user) is deliberately NOT here — see MIGRATIONS.md.

-- ── CORE ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS clinic (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL DEFAULT 'Aleefy',
    name_ar     TEXT DEFAULT 'اليفي',
    phone       TEXT, email TEXT, address TEXT, address_ar TEXT,
    website     TEXT, tax_number TEXT, license_number TEXT,
    doctor_name TEXT DEFAULT 'Lead Veterinarian',
    tagline     TEXT DEFAULT 'Happy Pets, Healthy Lives',
    logo_data   TEXT,
    currency    TEXT DEFAULT 'EGP',
    timezone    TEXT DEFAULT 'Africa/Cairo',
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS branches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    clinic_id   INTEGER DEFAULT 1,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    phone       TEXT, address TEXT,
    manager_id  INTEGER,
    is_active   INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS departments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER DEFAULT 1,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    head_id     INTEGER,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT UNIQUE NOT NULL,
    password_hash    TEXT NOT NULL,
    full_name        TEXT,
    full_name_ar     TEXT,
    email            TEXT,
    phone            TEXT,
    role             TEXT NOT NULL DEFAULT 'staff',
    department_id    INTEGER,
    branch_id        INTEGER DEFAULT 1,
    is_active        INTEGER DEFAULT 1,
    theme_preference TEXT DEFAULT 'medical',
    language         TEXT DEFAULT 'en',
    last_login_at    TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS roles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT UNIQUE NOT NULL,
    display_name     TEXT,
    display_name_ar  TEXT,
    permissions_json TEXT DEFAULT '[]',
    color            TEXT DEFAULT '#1a3a6b',
    created_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    user_id     INTEGER,
    username    TEXT, role TEXT, action TEXT, module TEXT,
    entity_type TEXT, entity_id TEXT, details TEXT,
    ip TEXT, user_agent TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    category   TEXT DEFAULT 'general',
    updated_at TEXT DEFAULT (datetime('now')),
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_token TEXT UNIQUE,
    user_id       INTEGER,
    username      TEXT, role TEXT, ip TEXT, user_agent TEXT,
    created_at    TEXT DEFAULT (datetime('now')),
    last_seen_at  TEXT DEFAULT (datetime('now')),
    ended_at      TEXT
);

-- ── CRM ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS owners (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name         TEXT NOT NULL,
    full_name_ar      TEXT,
    phone             TEXT,
    whatsapp_phone    TEXT,
    email             TEXT,
    address           TEXT,
    address_ar        TEXT,
    preferred_contact TEXT DEFAULT 'WhatsApp',
    preferred_doctor  TEXT,
    preferred_branch  INTEGER DEFAULT 1,
    vip_flag          INTEGER DEFAULT 0,
    outstanding_balance REAL DEFAULT 0.0,
    marketing_consent INTEGER DEFAULT 1,
    notes             TEXT,
    created_by        TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS owner_phones (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    phone       TEXT NOT NULL,
    label       TEXT DEFAULT 'Mobile',
    is_whatsapp INTEGER DEFAULT 0,
    is_primary  INTEGER DEFAULT 0,
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id            INTEGER NOT NULL,
    pet_name            TEXT NOT NULL,
    species             TEXT,
    breed               TEXT,
    sex                 TEXT DEFAULT 'Unknown',
    dob                 TEXT,
    weight_kg           REAL,
    color               TEXT,
    microchip_id        TEXT,
    neutered            INTEGER DEFAULT 0,
    allergies           TEXT,
    chronic_conditions  TEXT,
    diet_notes          TEXT,
    insurance_number    TEXT,
    notes               TEXT,
    is_active           INTEGER DEFAULT 1,
    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS pet_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id      INTEGER NOT NULL,
    filename    TEXT, filetype TEXT, filedata TEXT,
    caption     TEXT,
    uploaded_by TEXT,
    uploaded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
);

-- ── APPOINTMENTS ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS appointments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id         INTEGER NOT NULL,
    pet_id           INTEGER NOT NULL,
    branch_id        INTEGER DEFAULT 1,
    doctor_id        INTEGER,
    doctor_name      TEXT,
    room             TEXT,
    appointment_type TEXT DEFAULT 'Consultation',
    priority         TEXT DEFAULT 'Normal',
    status           TEXT DEFAULT 'Scheduled',
    channel          TEXT DEFAULT 'Walk-in',
    appt_date        TEXT NOT NULL,
    appt_start       TEXT NOT NULL,
    appt_end         TEXT,
    duration_min     INTEGER DEFAULT 30,
    reason           TEXT,
    symptoms         TEXT,
    notes            TEXT,
    confirmed        INTEGER DEFAULT 0,
    reminder_sent    INTEGER DEFAULT 0,
    checked_in_at    TEXT,
    checked_out_at   TEXT,
    created_by       TEXT,
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id),
    FOREIGN KEY (pet_id)   REFERENCES pets(id)
);

-- ── MEDICAL RECORDS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS visits (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id  INTEGER,
    owner_id        INTEGER NOT NULL,
    pet_id          INTEGER NOT NULL,
    doctor_id       INTEGER,
    doctor_name     TEXT,
    branch_id       INTEGER DEFAULT 1,
    room            TEXT,
    visit_date      TEXT NOT NULL,
    visit_type      TEXT DEFAULT 'Consultation',
    status          TEXT DEFAULT 'Open',
    chief_complaint TEXT,
    symptoms        TEXT,
    weight_kg       REAL,
    temp_c          REAL,
    heart_rate      INTEGER,
    respiratory_rate INTEGER,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id),
    FOREIGN KEY (pet_id)   REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER NOT NULL,
    pet_id      INTEGER NOT NULL,
    diagnosis   TEXT NOT NULL,
    diagnosis_code TEXT,
    severity    TEXT DEFAULT 'Moderate',
    is_chronic  INTEGER DEFAULT 0,
    notes       TEXT,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE,
    FOREIGN KEY (pet_id)   REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS treatment_plans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER NOT NULL,
    pet_id      INTEGER NOT NULL,
    plan_text   TEXT NOT NULL,
    goals       TEXT,
    duration    TEXT,
    followup_in INTEGER,
    followup_unit TEXT DEFAULT 'days',
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id       INTEGER NOT NULL,
    pet_id         INTEGER NOT NULL,
    owner_id       INTEGER NOT NULL,
    prescribed_by  TEXT,
    status         TEXT DEFAULT 'Active',
    notes          TEXT,
    dispensed_at   TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS prescription_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_id INTEGER NOT NULL,
    item_id         INTEGER,
    medication_name TEXT NOT NULL,
    dosage          TEXT,
    frequency       TEXT,
    duration        TEXT,
    route           TEXT DEFAULT 'Oral',
    quantity        REAL DEFAULT 1,
    unit            TEXT DEFAULT 'tablet',
    instructions    TEXT,
    dispensed       INTEGER DEFAULT 0,
    FOREIGN KEY (prescription_id) REFERENCES prescriptions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id    INTEGER NOT NULL,
    pet_id      INTEGER NOT NULL,
    test_name   TEXT NOT NULL,
    test_code   TEXT,
    priority    TEXT DEFAULT 'Routine',
    status      TEXT DEFAULT 'Pending',
    sample_type TEXT,
    collected_at TEXT,
    notes       TEXT,
    requested_by TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lab_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lab_request_id  INTEGER NOT NULL,
    pet_id          INTEGER NOT NULL,
    result_text     TEXT,
    result_value    REAL,
    unit            TEXT,
    reference_range TEXT,
    is_abnormal     INTEGER DEFAULT 0,
    reviewed_by     TEXT,
    reviewed_at     TEXT,
    report_data     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (lab_request_id) REFERENCES lab_requests(id)
);

CREATE TABLE IF NOT EXISTS vaccinations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id          INTEGER NOT NULL,
    visit_id        INTEGER,
    vaccine_name    TEXT NOT NULL,
    vaccine_brand   TEXT,
    batch_number    TEXT,
    dose_number     INTEGER DEFAULT 1,
    administered_by TEXT,
    administered_at TEXT NOT NULL,
    next_due_at     TEXT,
    site            TEXT DEFAULT 'Subcutaneous',
    notes           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS surgeries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id          INTEGER NOT NULL,
    visit_id        INTEGER,
    procedure_name  TEXT NOT NULL,
    surgeon         TEXT,
    anesthetist     TEXT,
    surgery_date    TEXT NOT NULL,
    duration_min    INTEGER,
    anesthesia_type TEXT,
    pre_op_notes    TEXT,
    intra_op_notes  TEXT,
    post_op_notes   TEXT,
    outcome         TEXT DEFAULT 'Successful',
    followup_date   TEXT,
    consent_given   INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id)
);

CREATE TABLE IF NOT EXISTS followups (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id     INTEGER,
    pet_id       INTEGER NOT NULL,
    owner_id     INTEGER NOT NULL,
    due_date     TEXT NOT NULL,
    reason       TEXT,
    status       TEXT DEFAULT 'Pending',
    reminder_sent INTEGER DEFAULT 0,
    completed_at TEXT,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

-- ── INVENTORY ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS item_categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT UNIQUE NOT NULL,
    name_ar     TEXT,
    parent_id   INTEGER,
    description TEXT,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id     INTEGER,
    sku             TEXT UNIQUE,
    barcode         TEXT,
    name            TEXT NOT NULL,
    name_ar         TEXT,
    description     TEXT,
    unit            TEXT DEFAULT 'unit',
    cost_price      REAL DEFAULT 0.0,
    sell_price      REAL DEFAULT 0.0,
    reorder_level   REAL DEFAULT 10.0,
    max_stock       REAL DEFAULT 1000.0,
    is_medication   INTEGER DEFAULT 0,
    is_controlled   INTEGER DEFAULT 0,
    requires_rx     INTEGER DEFAULT 0,
    supplier_id     INTEGER,
    storage_notes   TEXT,
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (category_id) REFERENCES item_categories(id)
);

CREATE TABLE IF NOT EXISTS warehouses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id   INTEGER DEFAULT 1,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    description TEXT,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS batches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id        INTEGER NOT NULL,
    warehouse_id   INTEGER DEFAULT 1,
    batch_number   TEXT,
    lot_number     TEXT,
    manufacture_date TEXT,
    expiry_date    TEXT,
    quantity       REAL DEFAULT 0.0,
    unit_cost      REAL DEFAULT 0.0,
    received_at    TEXT DEFAULT (datetime('now')),
    received_by    TEXT,
    notes          TEXT,
    FOREIGN KEY (item_id)      REFERENCES items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL,
    batch_id        INTEGER,
    warehouse_id    INTEGER DEFAULT 1,
    movement_type   TEXT NOT NULL,  -- in/out/adjustment/transfer/expired/damaged
    quantity        REAL NOT NULL,
    unit_cost       REAL DEFAULT 0.0,
    reference_type  TEXT,           -- visit/purchase/adjustment/etc.
    reference_id    INTEGER,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS reorder_rules (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id         INTEGER NOT NULL UNIQUE,
    reorder_point   REAL DEFAULT 10.0,
    reorder_qty     REAL DEFAULT 50.0,
    preferred_supplier_id INTEGER,
    auto_suggest    INTEGER DEFAULT 1,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- ── PHARMACY ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dosage_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER NOT NULL,
    species     TEXT DEFAULT 'All',
    dosage      TEXT NOT NULL,
    frequency   TEXT,
    route       TEXT DEFAULT 'Oral',
    notes       TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

CREATE TABLE IF NOT EXISTS dispensing_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    prescription_item_id INTEGER,
    item_id             INTEGER NOT NULL,
    batch_id            INTEGER,
    visit_id            INTEGER,
    pet_id              INTEGER,
    quantity            REAL NOT NULL,
    dispensed_by        TEXT,
    dispensed_at        TEXT DEFAULT (datetime('now')),
    notes               TEXT,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- ── FINANCE ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS invoices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number  TEXT UNIQUE NOT NULL,
    owner_id        INTEGER NOT NULL,
    pet_id          INTEGER,
    visit_id        INTEGER,
    branch_id       INTEGER DEFAULT 1,
    doctor_name     TEXT,
    issue_date      TEXT NOT NULL,
    due_date        TEXT,
    status          TEXT DEFAULT 'Unpaid',   -- Unpaid/Paid/Partial/Cancelled
    subtotal        REAL DEFAULT 0.0,
    discount_type   TEXT DEFAULT 'value',
    discount_value  REAL DEFAULT 0.0,
    discount_amount REAL DEFAULT 0.0,
    tax_rate        REAL DEFAULT 0.0,
    tax_amount      REAL DEFAULT 0.0,
    total           REAL DEFAULT 0.0,
    paid_amount     REAL DEFAULT 0.0,
    due_amount      REAL DEFAULT 0.0,
    notes           TEXT,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

CREATE TABLE IF NOT EXISTS invoice_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   INTEGER NOT NULL,
    line_type    TEXT DEFAULT 'service',  -- service/product/medication
    item_id      INTEGER,
    description  TEXT NOT NULL,
    quantity     REAL DEFAULT 1.0,
    unit_price   REAL DEFAULT 0.0,
    discount     REAL DEFAULT 0.0,
    total        REAL DEFAULT 0.0,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id     INTEGER NOT NULL,
    owner_id       INTEGER NOT NULL,
    amount         REAL NOT NULL,
    method         TEXT DEFAULT 'Cash',   -- Cash/Card/Transfer/Insurance
    channel        TEXT DEFAULT 'Cash',   -- Cash/Visa/Instapay
    reference      TEXT,
    notes          TEXT,
    received_by    TEXT,
    received_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (owner_id)   REFERENCES owners(id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id    INTEGER DEFAULT 1,
    category     TEXT,
    description  TEXT NOT NULL,
    amount       REAL NOT NULL,
    vendor       TEXT,
    receipt_ref  TEXT,
    expense_date TEXT NOT NULL,
    notes        TEXT,
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_closings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    branch_id       INTEGER DEFAULT 1,
    closing_date    TEXT NOT NULL,
    cash_sales      REAL DEFAULT 0.0,
    card_sales      REAL DEFAULT 0.0,
    transfer_sales  REAL DEFAULT 0.0,
    total_sales     REAL DEFAULT 0.0,
    total_expenses  REAL DEFAULT 0.0,
    net_revenue     REAL DEFAULT 0.0,
    opening_cash    REAL DEFAULT 0.0,
    closing_cash    REAL DEFAULT 0.0,
    notes           TEXT,
    closed_by       TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ── PROCUREMENT ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS suppliers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    name_ar      TEXT,
    contact_name TEXT,
    phone        TEXT,
    email        TEXT,
    address      TEXT,
    tax_number   TEXT,
    payment_terms TEXT DEFAULT 'Net 30',
    notes        TEXT,
    is_active    INTEGER DEFAULT 1,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_number    TEXT UNIQUE NOT NULL,
    supplier_id  INTEGER NOT NULL,
    branch_id    INTEGER DEFAULT 1,
    status       TEXT DEFAULT 'Draft',  -- Draft/Sent/Received/Cancelled
    order_date   TEXT NOT NULL,
    expected_date TEXT,
    received_date TEXT,
    subtotal     REAL DEFAULT 0.0,
    tax_amount   REAL DEFAULT 0.0,
    total        REAL DEFAULT 0.0,
    notes        TEXT,
    created_by   TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS po_lines (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    po_id        INTEGER NOT NULL,
    item_id      INTEGER NOT NULL,
    quantity     REAL NOT NULL,
    unit_cost    REAL DEFAULT 0.0,
    total        REAL DEFAULT 0.0,
    received_qty REAL DEFAULT 0.0,
    FOREIGN KEY (po_id)    REFERENCES purchase_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)  REFERENCES items(id)
);

-- ── COMMUNICATIONS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reminders (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id        INTEGER NOT NULL,
    pet_id          INTEGER,
    appointment_id  INTEGER,
    reminder_type   TEXT NOT NULL,  -- appointment/followup/vaccine/medication/custom
    message         TEXT,
    channel         TEXT DEFAULT 'WhatsApp',
    scheduled_for   TEXT NOT NULL,
    status          TEXT DEFAULT 'Pending',  -- Pending/Sent/Failed/Cancelled
    sent_at         TEXT,
    api_response    TEXT,
    retry_count     INTEGER DEFAULT 0,
    created_by      TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

CREATE TABLE IF NOT EXISTS whatsapp_templates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT UNIQUE NOT NULL,
    scenario      TEXT,         -- appointment/followup/vaccine/invoice/custom
    language      TEXT DEFAULT 'en',
    template_text TEXT NOT NULL,
    variables_json TEXT DEFAULT '[]',
    is_active     INTEGER DEFAULT 1,
    is_default    INTEGER DEFAULT 0,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS whatsapp_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reminder_id  INTEGER,
    owner_id     INTEGER,
    pet_id       INTEGER,
    phone        TEXT,
    message      TEXT,
    template_name TEXT,
    status       TEXT DEFAULT 'Pending',
    http_status  INTEGER,
    response     TEXT,
    error        TEXT,
    sent_at      TEXT DEFAULT (datetime('now'))
);

-- ── GROOMING ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grooming_services (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    duration_min INTEGER DEFAULT 60,
    price       REAL DEFAULT 0.0,
    species     TEXT DEFAULT 'All',
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS grooming_bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id        INTEGER NOT NULL,
    owner_id      INTEGER NOT NULL,
    service_id    INTEGER,
    groomer_name  TEXT,
    booking_date  TEXT NOT NULL,
    status        TEXT DEFAULT 'Scheduled',
    notes         TEXT,
    before_photo  TEXT,
    after_photo   TEXT,
    invoice_id    INTEGER,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

-- ── BOARDING ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS boarding_rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    room_type   TEXT DEFAULT 'Standard',   -- Standard/Premium/ICU
    capacity    INTEGER DEFAULT 1,
    price_per_night REAL DEFAULT 0.0,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS boarding_bookings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id        INTEGER NOT NULL,
    owner_id      INTEGER NOT NULL,
    room_id       INTEGER,
    check_in      TEXT NOT NULL,
    check_out     TEXT,
    actual_checkout TEXT,
    status        TEXT DEFAULT 'Booked',
    feeding_instructions TEXT,
    medication_instructions TEXT,
    vet_notes     TEXT,
    invoice_id    INTEGER,
    created_at    TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id)
);

-- ── SYSTEM ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS app_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT DEFAULT (datetime('now')),
    severity    TEXT DEFAULT 'INFO',
    module      TEXT,
    message     TEXT,
    details     TEXT,
    username    TEXT,
    ip          TEXT
);

CREATE TABLE IF NOT EXISTS diagnostic_runs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT DEFAULT (datetime('now')),
    run_by         TEXT,
    overall_status TEXT,
    passed         INTEGER DEFAULT 0,
    warnings       INTEGER DEFAULT 0,
    failed         INTEGER DEFAULT 0,
    summary        TEXT,
    details_json   TEXT
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    username    TEXT,
    role        TEXT,
    module      TEXT,
    context_type TEXT,   -- visit/pet/inventory/finance/etc.
    context_id  INTEGER,
    prompt      TEXT,
    response    TEXT,
    model_used  TEXT,
    tokens_used INTEGER,
    action_taken TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ── ATTENDANCE & LEAVE MANAGEMENT ────────────────────────────
CREATE TABLE IF NOT EXISTS shifts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    name_ar       TEXT,
    start_time    TEXT NOT NULL DEFAULT '08:00',
    end_time      TEXT NOT NULL DEFAULT '17:00',
    break_minutes INTEGER DEFAULT 60,
    days_of_week  TEXT DEFAULT '1,2,3,4,5',
    color         TEXT DEFAULT '#3b82f6',
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS staff_shifts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    shift_id   INTEGER NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to   TEXT,
    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (shift_id) REFERENCES shifts(id)
);

CREATE TABLE IF NOT EXISTS attendance_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    full_name       TEXT,
    work_date       TEXT NOT NULL,
    check_in        TEXT,
    check_out       TEXT,
    break_minutes   INTEGER DEFAULT 0,
    hours_worked    REAL DEFAULT 0,
    status          TEXT DEFAULT 'Present',
    notes           TEXT,
    recorded_by     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS leave_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT UNIQUE NOT NULL,
    name_ar         TEXT,
    days_per_year   REAL DEFAULT 21,
    is_paid         INTEGER DEFAULT 1,
    requires_approval INTEGER DEFAULT 1,
    min_notice_days INTEGER DEFAULT 1,
    max_consecutive INTEGER DEFAULT 30,
    color           TEXT DEFAULT '#6366f1',
    is_active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    leave_type_id   INTEGER NOT NULL,
    year            INTEGER NOT NULL,
    allocated       REAL DEFAULT 0,
    used            REAL DEFAULT 0,
    pending         REAL DEFAULT 0,
    remaining       REAL DEFAULT 0,
    UNIQUE(user_id, leave_type_id, year),
    FOREIGN KEY (user_id)       REFERENCES users(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    username        TEXT,
    full_name       TEXT,
    leave_type_id   INTEGER NOT NULL,
    leave_type_name TEXT,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    days_requested  REAL NOT NULL,
    reason          TEXT,
    status          TEXT DEFAULT 'Pending',
    approved_by     TEXT,
    approved_at     TEXT,
    rejection_reason TEXT,
    attachment_name TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id)       REFERENCES users(id),
    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id)
);

CREATE TABLE IF NOT EXISTS public_holidays (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    name_ar     TEXT,
    holiday_date TEXT NOT NULL UNIQUE,
    is_recurring INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attendance_user ON attendance_records(user_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance_records(work_date);
CREATE INDEX IF NOT EXISTS idx_leave_user      ON leave_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_leave_dates     ON leave_requests(start_date, end_date);

-- ── INDEXES ───────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pets_owner         ON pets(owner_id);
CREATE INDEX IF NOT EXISTS idx_appts_date         ON appointments(appt_date);
CREATE INDEX IF NOT EXISTS idx_appts_pet          ON appointments(pet_id);
CREATE INDEX IF NOT EXISTS idx_visits_pet         ON visits(pet_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_visit    ON diagnoses(visit_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_visit ON prescriptions(visit_id);
CREATE INDEX IF NOT EXISTS idx_stock_item         ON stock_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_stock_date         ON stock_movements(created_at);
CREATE INDEX IF NOT EXISTS idx_invoices_owner     ON invoices(owner_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date      ON invoices(issue_date);
CREATE INDEX IF NOT EXISTS idx_payments_invoice   ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_reminders_date     ON reminders(scheduled_for);
CREATE INDEX IF NOT EXISTS idx_batches_expiry     ON batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_owners_phone       ON owners(phone);
CREATE INDEX IF NOT EXISTS idx_owners_name        ON owners(full_name);
-- hot FK joins (detail rows fetched per parent record)
CREATE INDEX IF NOT EXISTS idx_appts_owner        ON appointments(owner_id);
CREATE INDEX IF NOT EXISTS idx_visits_owner       ON visits(owner_id);
CREATE INDEX IF NOT EXISTS idx_treatment_visit    ON treatment_plans(visit_id);
CREATE INDEX IF NOT EXISTS idx_rx_items_rx        ON prescription_items(prescription_id);
CREATE INDEX IF NOT EXISTS idx_labreq_visit       ON lab_requests(visit_id);
CREATE INDEX IF NOT EXISTS idx_labres_request     ON lab_results(lab_request_id);
CREATE INDEX IF NOT EXISTS idx_vaccinations_pet   ON vaccinations(pet_id);
CREATE INDEX IF NOT EXISTS idx_surgeries_pet      ON surgeries(pet_id);
CREATE INDEX IF NOT EXISTS idx_followups_pet      ON followups(pet_id);
CREATE INDEX IF NOT EXISTS idx_invlines_invoice   ON invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS idx_payments_owner     ON payments(owner_id);
CREATE INDEX IF NOT EXISTS idx_po_lines_po        ON po_lines(po_id);
-- date-range report / due-list filters
CREATE INDEX IF NOT EXISTS idx_visits_date        ON visits(visit_date);
CREATE INDEX IF NOT EXISTS idx_payments_date      ON payments(received_at);
CREATE INDEX IF NOT EXISTS idx_expenses_date      ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_followups_due      ON followups(due_date);
CREATE INDEX IF NOT EXISTS idx_vaccinations_due   ON vaccinations(next_due_at);

-- ── NOTIFICATIONS ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id INTEGER NOT NULL,
    recipient_role TEXT,
    title        TEXT NOT NULL,
    body         TEXT,
    icon         TEXT DEFAULT '🔔',
    link         TEXT,
    module       TEXT,
    entity_type  TEXT,
    entity_id    INTEGER,
    is_read      INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (recipient_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient_id, is_read);

-- ── SERVICE / PRICE CATALOG ───────────────────────────────────
CREATE TABLE IF NOT EXISTS service_catalog (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT UNIQUE,
    name         TEXT NOT NULL,
    name_ar      TEXT,
    category     TEXT DEFAULT 'Consultation',
    description  TEXT,
    standard_price REAL DEFAULT 0,
    tax_rate     REAL DEFAULT 0,
    duration_min INTEGER DEFAULT 0,
    species      TEXT DEFAULT 'All',
    is_active    INTEGER DEFAULT 1,
    sort_order   INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now')),
    updated_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_svc_category ON service_catalog(category, is_active);

-- ── REMINDER RUNS (deduplication) ─────────────────────────────
CREATE TABLE IF NOT EXISTS reminder_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type     TEXT NOT NULL,
    entity_id    INTEGER,
    entity_type  TEXT,
    status       TEXT DEFAULT 'sent',
    run_at       TEXT DEFAULT (datetime('now')),
    UNIQUE(run_type, entity_id, entity_type)
);

-- ── FILE ATTACHMENTS ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attachments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type  TEXT NOT NULL,
    entity_id    INTEGER NOT NULL,
    filename     TEXT NOT NULL,
    original_name TEXT,
    mime_type    TEXT,
    size_bytes   INTEGER DEFAULT 0,
    category     TEXT DEFAULT 'general',
    caption      TEXT,
    uploaded_by  TEXT,
    uploaded_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_attach_entity ON attachments(entity_type, entity_id);

-- ── BUDGET TARGETS ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS budget_targets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT NOT NULL UNIQUE,
    monthly_egp REAL NOT NULL DEFAULT 0,
    updated_by  TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);

-- ── LOYALTY POINTS ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS loyalty_points (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    points      INTEGER NOT NULL,
    reason      TEXT,
    ref_type    TEXT DEFAULT 'manual',
    ref_id      INTEGER,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (owner_id) REFERENCES owners(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_loyalty_owner ON loyalty_points(owner_id);

-- ── INPATIENT / HOSPITALISATION ───────────────────────────────
CREATE TABLE IF NOT EXISTS inpatient_stays (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id          INTEGER NOT NULL,
    owner_id        INTEGER NOT NULL,
    visit_id        INTEGER,
    ward            TEXT DEFAULT 'General',
    cage_number     TEXT,
    admitted_by     INTEGER NOT NULL,
    reason          TEXT NOT NULL,
    diagnosis       TEXT,
    treatment_plan  TEXT,
    status          TEXT NOT NULL DEFAULT 'Admitted',
    admitted_at     TEXT DEFAULT (datetime('now')),
    expected_discharge DATE,
    discharged_at   TEXT,
    discharge_notes TEXT,
    daily_rate      NUMERIC(10,2) DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id)   REFERENCES pets(id),
    FOREIGN KEY (owner_id) REFERENCES owners(id),
    FOREIGN KEY (admitted_by) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_inpatient_pet    ON inpatient_stays(pet_id);
CREATE INDEX IF NOT EXISTS idx_inpatient_status ON inpatient_stays(status);

CREATE TABLE IF NOT EXISTS inpatient_rounds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stay_id     INTEGER NOT NULL,
    recorded_by INTEGER NOT NULL,
    round_time  TEXT DEFAULT (datetime('now')),
    temp_c      REAL,
    heart_rate  INTEGER,
    resp_rate   INTEGER,
    weight_kg   REAL,
    pain_score  INTEGER,
    food_intake TEXT,
    fluid_input REAL,
    fluid_output REAL,
    observations TEXT,
    treatment_given TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (stay_id) REFERENCES inpatient_stays(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inpatient_meds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    stay_id     INTEGER NOT NULL,
    given_by    INTEGER,
    medication  TEXT NOT NULL,
    dose        TEXT,
    route       TEXT DEFAULT 'PO',
    given_at    TEXT DEFAULT (datetime('now')),
    notes       TEXT,
    FOREIGN KEY (stay_id) REFERENCES inpatient_stays(id) ON DELETE CASCADE
);

-- ── PRODUCTION LOGGING TABLES ─────────────────────────────────

CREATE TABLE IF NOT EXISTS backend_logs (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id            TEXT,
    request_id                TEXT,
    user_id                   INTEGER,
    username                  TEXT,
    level                     TEXT DEFAULT 'INFO',
    module_name               TEXT,
    action_name               TEXT,
    http_method               TEXT,
    endpoint                  TEXT,
    status_code               INTEGER,
    duration_ms               INTEGER,
    ip_address                TEXT,
    user_agent                TEXT,
    request_payload_summary   TEXT,
    response_payload_summary  TEXT,
    error_message             TEXT,
    stack_trace               TEXT,
    metadata                  TEXT DEFAULT '{}',
    created_at                TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_blog_level    ON backend_logs(level);
CREATE INDEX IF NOT EXISTS idx_blog_created  ON backend_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_blog_endpoint ON backend_logs(endpoint);
CREATE INDEX IF NOT EXISTS idx_blog_user     ON backend_logs(user_id);

CREATE TABLE IF NOT EXISTS frontend_logs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id    TEXT,
    session_id        TEXT,
    user_id           INTEGER,
    username          TEXT,
    level             TEXT DEFAULT 'INFO',
    page_url          TEXT,
    route_name        TEXT,
    component_name    TEXT,
    event_name        TEXT,
    message           TEXT,
    browser_name      TEXT,
    browser_version   TEXT,
    device_type       TEXT,
    os_name           TEXT,
    network_status    TEXT DEFAULT 'online',
    api_endpoint      TEXT,
    api_status_code   INTEGER,
    error_stack       TEXT,
    metadata          TEXT DEFAULT '{}',
    created_at        TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_flog_level   ON frontend_logs(level);
CREATE INDEX IF NOT EXISTS idx_flog_created ON frontend_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_flog_user    ON frontend_logs(user_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT,
    user_id        INTEGER,
    username       TEXT,
    action_type    TEXT NOT NULL,
    entity_name    TEXT,
    entity_id      TEXT,
    old_value      TEXT,
    new_value      TEXT,
    ip_address     TEXT,
    user_agent     TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_alog_action  ON audit_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_alog_entity  ON audit_logs(entity_name, entity_id);
CREATE INDEX IF NOT EXISTS idx_alog_user    ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_alog_created ON audit_logs(created_at);

-- ── OFFLINE SYNC TABLES ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS sync_queue (
    id                 TEXT PRIMARY KEY,
    local_uuid         TEXT NOT NULL,
    server_uuid        TEXT,
    device_id          TEXT NOT NULL,
    user_id            INTEGER,
    entity_name        TEXT NOT NULL,
    operation_type     TEXT NOT NULL,
    payload            TEXT NOT NULL,
    status             TEXT DEFAULT 'PENDING',
    retry_count        INTEGER DEFAULT 0,
    last_error         TEXT,
    priority           INTEGER DEFAULT 5,
    created_offline_at TEXT,
    last_attempt_at    TEXT,
    synced_at          TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sq_status    ON sync_queue(status);
CREATE INDEX IF NOT EXISTS idx_sq_device    ON sync_queue(device_id);
CREATE INDEX IF NOT EXISTS idx_sq_entity    ON sync_queue(entity_name);
CREATE INDEX IF NOT EXISTS idx_sq_priority  ON sync_queue(priority, created_offline_at);

CREATE TABLE IF NOT EXISTS sync_conflicts (
    id                TEXT PRIMARY KEY,
    sync_queue_id     TEXT NOT NULL,
    entity_name       TEXT,
    local_payload     TEXT,
    server_payload    TEXT,
    conflict_type     TEXT,
    resolution_status TEXT DEFAULT 'PENDING',
    resolved_by       TEXT,
    resolved_at       TEXT,
    created_at        TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_sc_status ON sync_conflicts(resolution_status);

CREATE TABLE IF NOT EXISTS devices (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id     TEXT UNIQUE NOT NULL,
    device_name   TEXT,
    branch_id     INTEGER,
    user_id       INTEGER,
    platform      TEXT,
    app_version   TEXT,
    last_online_at TEXT,
    last_sync_at  TEXT,
    is_active     INTEGER DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now')),
    updated_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_dev_device ON devices(device_id);
CREATE INDEX IF NOT EXISTS idx_dev_user   ON devices(user_id);

-- ══════════════════════════════════════════════════════════════
-- Ad-hoc ALTERs applied by init_db() after _SCHEMA (models/database.py ~1700-1733).
-- They are part of the real current schema and therefore part of the baseline.
-- ══════════════════════════════════════════════════════════════

ALTER TABLE visits ADD COLUMN soap_subjective TEXT;
ALTER TABLE visits ADD COLUMN soap_objective TEXT;
ALTER TABLE visits ADD COLUMN soap_assessment TEXT;
ALTER TABLE visits ADD COLUMN soap_plan TEXT;

ALTER TABLE owners ADD COLUMN loyalty_balance INTEGER DEFAULT 0;

ALTER TABLE pets ADD COLUMN insurance_provider TEXT;
ALTER TABLE pets ADD COLUMN policy_number TEXT;
ALTER TABLE pets ADD COLUMN policy_expiry TEXT;

CREATE TABLE IF NOT EXISTS imaging_studies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pet_id      INTEGER NOT NULL,
    owner_id    INTEGER,
    visit_id    INTEGER,
    study_type  TEXT NOT NULL,
    body_region TEXT,
    file_path   TEXT,
    notes       TEXT,
    ai_analysis TEXT,
    created_by  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (pet_id) REFERENCES pets(id) ON DELETE CASCADE
);
