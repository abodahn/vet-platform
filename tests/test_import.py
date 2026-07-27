"""
Data import tests — SQLite only, no PostgreSQL needed.

Every test runs against a throwaway database created inside pytest's tmp_path,
never data/platform.db.
"""
import io
import os
import sqlite3

import pytest

from migrations import excel_import as xi


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def conn(tmp_path):
    """A minimal owners/pets/visits schema, matching models/database.py."""
    path = tmp_path / "import_test.db"
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE owners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL, phone TEXT, whatsapp_phone TEXT,
            email TEXT, address TEXT, notes TEXT,
            created_by TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL, pet_name TEXT NOT NULL,
            species TEXT, breed TEXT, sex TEXT, dob TEXT, weight_kg REAL,
            color TEXT, microchip_id TEXT, notes TEXT,
            is_active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL, pet_id INTEGER NOT NULL,
            doctor_name TEXT, visit_date TEXT NOT NULL, visit_type TEXT,
            status TEXT, chief_complaint TEXT, notes TEXT,
            created_by TEXT, created_at TEXT, updated_at TEXT
        );
    """)
    c.commit()
    yield c
    c.close()


def counts(conn):
    return tuple(
        conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("owners", "pets", "visits")
    )


def make_xlsx(headers, rows) -> bytes:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(list(headers))
    for row in rows:
        ws.append(list(row))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ARABIC_HEADERS = ["اسم العميل", "رقم الهاتف", "اسم الحيوان", "النوع"]
ARABIC_ROWS = [
    ["محمد عبد الرحمن", "01012345678", "لولو", "قطة"],
    ["فاطمة الزهراء السيد", "+201112223334", "بسبس", "قط"],
]


def _run(conn, headers, rows, **kw):
    mapping = xi.guess_mapping(headers)
    return xi.run_import(conn, headers, rows, mapping, **kw)


# ── T3: a dry run writes nothing ──────────────────────────────────────────

def test_dry_run_writes_nothing(conn):
    headers = ["Owner Name", "Mobile", "Pet Name", "Species", "Visit Date"]
    rows = [
        ["Ahmed Sami", "01012345678", "Rex", "Dog", "2024-03-05"],
        ["Mona Adel", "01298765432", "Luna", "Cat", "2024-04-11"],
    ]
    before = counts(conn)
    report = xi.run_import(conn, headers, rows, xi.guess_mapping(headers), dry_run=True)

    assert counts(conn) == before == (0, 0, 0)
    assert report["counts"]["owners"]["created"] == 2
    assert report["counts"]["pets"]["created"] == 2
    assert report["counts"]["visits"]["created"] == 2
    assert len(report["preview"]) == 2


def test_dry_run_preview_matches_what_gets_written(conn):
    headers = ["Owner Name", "Mobile", "Pet Name"]
    rows = [["Ahmed Sami", "0020 101 234 5678", "Rex"]]

    plan = _run(conn, headers, rows, dry_run=True)
    with conn:
        real = _run(conn, headers, rows, dry_run=False)

    assert plan["counts"] == real["counts"]
    assert conn.execute("SELECT phone FROM owners").fetchone()[0] == \
        plan["preview"][0]["owner_phone"]


# ── T4: Arabic survives end to end ────────────────────────────────────────

def test_arabic_names_round_trip_unchanged(conn):
    with conn:
        _run(conn, ARABIC_HEADERS, [list(r) for r in ARABIC_ROWS], dry_run=False)

    names = [r[0] for r in conn.execute("SELECT full_name FROM owners ORDER BY id")]
    pets = [r[0] for r in conn.execute("SELECT pet_name FROM pets ORDER BY id")]
    assert names == ["محمد عبد الرحمن", "فاطمة الزهراء السيد"]
    assert pets == ["لولو", "بسبس"]


def test_arabic_survives_the_xlsx_reader(tmp_path):
    data = make_xlsx(ARABIC_HEADERS, ARABIC_ROWS)
    headers, rows = xi.read_table(data, "clients.xlsx")
    assert headers == ARABIC_HEADERS
    assert rows[0][0] == "محمد عبد الرحمن"
    assert rows[0][2] == "لولو"


def test_arabic_headers_are_guessed(tmp_path):
    mapping = xi.guess_mapping(ARABIC_HEADERS)
    assert mapping[0] == "owner_name"
    assert mapping[1] == "owner_phone"
    assert mapping[2] == "pet_name"
    assert mapping[3] == "pet_species"


def test_arabic_csv_in_cp1256_is_decoded(tmp_path):
    text = "اسم العميل,رقم الهاتف\nمحمد عبد الرحمن,01012345678\n"
    headers, rows = xi.read_table(text.encode("cp1256"), "clients.csv")
    assert headers[0] == "اسم العميل"
    assert rows[0][0] == "محمد عبد الرحمن"


def test_invisible_bidi_marks_do_not_break_matching(conn):
    """Excel injects RLM/LRM into Arabic cells; two identical names must match."""
    headers = ["اسم العميل", "رقم الهاتف"]
    with conn:
        _run(conn, headers, [["محمد علي", "01012345678"]], dry_run=False)
        report = _run(conn, headers, [["‏محمد علي‎", "01012345678"]],
                      dry_run=False)
    assert report["counts"]["owners"]["created"] == 0
    assert counts(conn)[0] == 1


# ── T4: Egyptian phone normalisation ──────────────────────────────────────

@pytest.mark.parametrize("raw", [
    "01012345678",
    "+201012345678",
    "0020 101 234 5678",
    "0020-101-234-5678",
    "(+20) 101 234 5678",
    "٠١٠١٢٣٤٥٦٧٨",           # Arabic-Indic digits
])
def test_egyptian_phone_formats_normalise_to_one_value(raw):
    assert xi.normalize_phone(raw) == "01012345678"


def test_phone_formats_collapse_to_one_owner(conn):
    headers = ["Owner", "Phone"]
    rows = [["Ahmed Sami", "01012345678"],
            ["Ahmed S.", "+201012345678"],
            ["A. Sami", "0020 101 234 5678"]]
    with conn:
        report = _run(conn, headers, rows, dry_run=False)

    assert counts(conn)[0] == 1
    assert report["counts"]["owners"]["created"] == 1
    assert conn.execute("SELECT phone FROM owners").fetchone()[0] == "01012345678"


def test_landline_keeps_its_leading_zero():
    assert xi.normalize_phone("02 2345 6789") == "0223456789"
    assert xi.normalize_phone("+20 2 2345 6789") == "0223456789"


# ── T5: re-running the same file creates nothing ──────────────────────────

def test_reimporting_the_same_file_creates_nothing(conn):
    headers = ["Owner Name", "Mobile", "Pet Name", "Species", "Visit Date", "Visit Type"]
    rows = [
        ["Ahmed Sami", "01012345678", "Rex", "Dog", "2024-03-05", "Consultation"],
        ["Mona Adel", "01298765432", "Luna", "Cat", "2024-04-11", "Vaccination"],
    ]
    with conn:
        _run(conn, headers, rows, dry_run=False)
    first = counts(conn)
    assert first == (2, 2, 2)

    with conn:
        second = _run(conn, headers, rows, dry_run=False)

    assert counts(conn) == first
    assert second["counts"]["owners"]["created"] == 0
    assert second["counts"]["pets"]["created"] == 0
    assert second["counts"]["visits"]["created"] == 0
    assert second["counts"]["owners"]["skipped"] == 2


def test_same_owner_repeated_within_one_file_is_created_once(conn):
    headers = ["Owner", "Phone", "Pet"]
    rows = [["Ahmed", "01012345678", "Rex"],
            ["Ahmed", "01012345678", "Bella"],
            ["Ahmed", "01012345678", "Rex"]]
    with conn:
        _run(conn, headers, rows, dry_run=False)
    assert counts(conn)[:2] == (1, 2)


def test_update_strategy_fills_gaps_without_erasing(conn):
    headers = ["Owner", "Phone", "Email", "Address"]
    with conn:
        _run(conn, headers, [["Ahmed", "01012345678", "a@x.com", "Nasr City"]],
             dry_run=False)
    with conn:
        report = _run(conn, headers, [["Ahmed Sami", "01012345678", "", "Maadi"]],
                      dry_run=False, strategy="update")

    row = conn.execute("SELECT * FROM owners").fetchone()
    assert report["counts"]["owners"]["updated"] == 1
    assert counts(conn)[0] == 1
    assert row["address"] == "Maadi"        # non-empty value came through
    assert row["email"] == "a@x.com"        # empty cell did not wipe it


def test_create_strategy_adds_a_second_record(conn):
    headers = ["Owner", "Phone"]
    with conn:
        _run(conn, headers, [["Ahmed", "01012345678"]], dry_run=False)
    with conn:
        _run(conn, headers, [["Ahmed", "01012345678"]], dry_run=False, strategy="create")
    assert counts(conn)[0] == 2


# ── T3: bad rows are reported by row number and do not abort the file ─────

def test_malformed_row_is_reported_with_its_row_number(conn):
    headers = ["Owner Name", "Mobile", "Pet Name", "Date of Birth"]
    rows = [
        ["Ahmed Sami", "01012345678", "Rex", "2020-01-01"],
        ["Mona Adel", "01298765432", "Luna", "not a date at all"],   # sheet row 3
        ["Sara Nabil", "01555555555", "Simba", "2019-06-30"],
    ]
    with conn:
        report = _run(conn, headers, rows, dry_run=False)

    assert report["rows_failed"] == 1
    assert [e["row"] for e in report["errors"]] == [3]
    assert "date" in report["errors"][0]["en"].lower()
    assert report["errors"][0]["ar"]                       # Arabic text present
    # The good rows still went in — one bad row does not abort the file.
    assert counts(conn)[:2] == (2, 2)


def test_row_with_a_pet_but_no_owner_is_reported(conn):
    headers = ["Owner Name", "Mobile", "Pet Name"]
    rows = [["", "", "Rex"], ["Mona", "01298765432", "Luna"]]
    with conn:
        report = _run(conn, headers, rows, dry_run=False)
    assert [e["row"] for e in report["errors"]] == [2]
    assert counts(conn)[:2] == (1, 1)


def test_failed_rows_csv_lists_the_row_and_reason(conn):
    headers = ["Owner Name", "Mobile", "Pet Name", "Weight"]
    rows = [["Ahmed", "01012345678", "Rex", "heavy-ish"]]
    report = _run(conn, headers, rows, dry_run=True)
    csv_text = xi.failed_rows_csv(report["failed_rows"])
    assert "Row in your file" in csv_text
    assert ",2," in csv_text or csv_text.splitlines()[1].startswith("2,")


def test_blank_rows_are_ignored_not_failed(conn):
    headers = ["Owner Name", "Mobile", "Pet Name"]
    rows = [["", "", ""], ["Mona", "01298765432", "Luna"]]
    report = _run(conn, headers, rows, dry_run=True)
    assert report["rows_failed"] == 0
    assert report["counts"]["owners"]["created"] == 1


# ── file validation ───────────────────────────────────────────────────────

def test_rejects_a_non_spreadsheet_with_an_actionable_message():
    with pytest.raises(xi.SpreadsheetError) as exc:
        xi.read_table(b"%PDF-1.7 not a spreadsheet", "clients.xlsx")
    assert "Excel" in exc.value.en
    assert exc.value.ar


def test_rejects_legacy_xls_and_says_how_to_fix_it():
    with pytest.raises(xi.SpreadsheetError) as exc:
        xi.read_table(b"\xd0\xcf\x11\xe0" + b"\x00" * 20, "clients.xls")
    assert "Save As" in exc.value.en


def test_rejects_a_header_only_file():
    with pytest.raises(xi.SpreadsheetError):
        xi.read_table(make_xlsx(["Owner", "Phone"], []), "clients.xlsx")


def test_day_first_dates_are_read_the_egyptian_way():
    assert xi.normalize_date("03/04/2024") == "2024-04-03"
    assert xi.normalize_date("") is None
    assert xi.normalize_date("rubbish") is False


# ── T4: a failed backup blocks the import ────────────────────────────────

def _login(app):
    c = app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")   # seeds session["_csrf_token"] via the context processor
    with c.session_transaction() as sess:
        assert sess.get("user"), "login failed — check the seed admin password"
    return c


def _token(client):
    """The app checks _csrf_token itself, independently of WTF_CSRF_ENABLED."""
    from models.security import _CSRF_SESSION_KEY
    with client.session_transaction() as sess:
        return sess.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, **kw):
    payload = dict(data)
    payload["_csrf_token"] = _token(client)
    return client.post(url, data=payload, follow_redirects=True, **kw)


def _upload(client, data, filename="clients.xlsx"):
    return client.post(
        "/migration/upload",
        data={"file": (io.BytesIO(data), filename),
              "_csrf_token": _token(client)},
        content_type="multipart/form-data",
        follow_redirects=True,
    )


def test_failed_backup_blocks_the_import(app, monkeypatch):
    """A backup that does not succeed must stop the import before any write."""
    import models.backup as bk
    import models.database as db

    client = _login(app)
    payload = make_xlsx(["Owner Name", "Mobile", "Pet Name"],
                        [["Backup Gate Owner", "01099998888", "Gatekeeper"]])
    assert _upload(client, payload).status_code == 200

    called = {"n": 0}

    def _broken_backup(*a, **kw):
        called["n"] += 1
        return {"success": False, "error": "disk full", "filename": ""}

    monkeypatch.setattr(bk, "run_backup", _broken_backup)

    conn = db.get_db()
    try:
        before = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
    finally:
        conn.close()

    resp = _post(client, "/migration/commit",
                 {"strategy": "skip", "col_0": "owner_name",
                  "col_1": "owner_phone", "col_2": "pet_name"})
    assert resp.status_code == 200
    assert called["n"] == 1

    conn = db.get_db()
    try:
        after = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
        leaked = conn.execute(
            "SELECT COUNT(*) FROM owners WHERE full_name=?", ("Backup Gate Owner",)
        ).fetchone()[0]
    finally:
        conn.close()

    assert after == before, "import wrote rows even though the backup failed"
    assert leaked == 0
    body = resp.get_data(as_text=True)
    assert "backup" in body.lower() or "احتياطي" in body


def test_backup_runs_before_the_first_write(app, monkeypatch):
    """The backup must be taken before any row is inserted, not alongside it."""
    import models.backup as bk
    import models.database as db

    client = _login(app)
    payload = make_xlsx(["Owner Name", "Mobile", "Pet Name"],
                        [["Ordered Backup Owner", "01077776666", "Sequence"]])
    assert _upload(client, payload).status_code == 200

    order = []
    real_get_db = db.get_db

    def _watch_backup(*a, **kw):
        conn = real_get_db()
        try:
            present = conn.execute(
                "SELECT COUNT(*) FROM owners WHERE full_name=?",
                ("Ordered Backup Owner",),
            ).fetchone()[0]
        finally:
            conn.close()
        order.append(("backup", present))
        return {"success": True, "filename": "test_backup.db", "size_kb": 1,
                "integrity": "ok", "error": None}

    monkeypatch.setattr(bk, "run_backup", _watch_backup)

    resp = _post(client, "/migration/commit",
                 {"strategy": "skip", "col_0": "owner_name",
                  "col_1": "owner_phone", "col_2": "pet_name"})
    assert resp.status_code == 200
    assert order == [("backup", 0)], "backup did not run before the first write"

    conn = db.get_db()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM owners WHERE full_name=?",
            ("Ordered Backup Owner",),
        ).fetchone()[0] == 1
    finally:
        conn.close()


# ── wizard smoke tests ────────────────────────────────────────────────────

def test_index_page_loads(app):
    resp = _login(app).get("/migration/")
    assert resp.status_code == 200
    assert b"import" in resp.data.lower() or "استيراد".encode() in resp.data


def test_upload_then_preview_writes_nothing(app):
    import models.database as db

    client = _login(app)
    payload = make_xlsx(ARABIC_HEADERS, ARABIC_ROWS)
    resp = _upload(client, payload)
    assert resp.status_code == 200
    assert "اسم العميل".encode() in resp.data      # header echoed back for mapping

    conn = db.get_db()
    try:
        before = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
    finally:
        conn.close()

    resp = _post(client, "/migration/preview",
                 {"strategy": "skip", "col_0": "owner_name",
                  "col_1": "owner_phone", "col_2": "pet_name",
                  "col_3": "pet_species"})
    assert resp.status_code == 200

    conn = db.get_db()
    try:
        after = conn.execute("SELECT COUNT(*) FROM owners").fetchone()[0]
    finally:
        conn.close()
    assert after == before, "the preview step wrote to the database"


def test_upload_rejects_a_fake_spreadsheet(app):
    client = _login(app)
    resp = _upload(client, b"this is definitely not a workbook", "clients.xlsx")
    assert resp.status_code == 200
    assert b"Excel" in resp.data


def test_preview_without_an_uploaded_file_redirects(app):
    client = _login(app)
    resp = _post(client, "/migration/preview", {"strategy": "skip"})
    assert resp.status_code == 200


def test_staging_files_never_touch_the_live_database_path(app):
    """The wizard must stage uploads under UPLOADS_PATH, not next to platform.db."""
    client = _login(app)
    _upload(client, make_xlsx(["Owner", "Phone"], [["A", "01012345678"]]))
    with client.session_transaction() as sess:
        info = sess.get("import_file")
    assert info and info["token"]
    with app.app_context():
        from blueprints.migration.routes import _staging_dir
        staged = _staging_dir()
    assert os.path.isdir(staged)
    assert "platform.db" not in staged
