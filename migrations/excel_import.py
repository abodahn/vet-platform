#!/usr/bin/env python3
"""
Spreadsheet import engine — owners, pets and visits.

Pure logic: no Flask, no hardcoded paths, no `current_app`. The browser wizard
in `blueprints/migration` drives it; `python migrations/excel_import.py FILE`
runs the identical code from a shell.

The old version read fixed filenames out of C:\\vet\\ppc_diagnostics_work\\data
and assumed the legacy app's column names. Real clinics hand you one file with
whatever headers their receptionist typed, in Arabic or English, so the caller
now supplies the bytes and a column mapping.

Portable SQL only (`?` placeholders, timestamps computed in Python) — the same
statements run on SQLite and PostgreSQL through models.database.
"""

import csv
import io
import os
import re
import sys
import unicodedata
from datetime import date, datetime

# A 16 MB xlsx can hold far more rows than a clinic ever has. Refuse rather
# than let one upload chew all the RAM in the worker.
# ponytail: hard cap, no streaming. Raise it or chunk the import if a customer
# genuinely arrives with a bigger book.
MAX_ROWS = 20000

PREVIEW_ROWS = 20
MAX_ERRORS = 500          # keep the results page renderable
MAX_DUPLICATES = 300

STRATEGIES = ("skip", "update", "create")


# ════════════════════════════════════════════════════════════════════════
#  Target fields — what a source column can be mapped onto
# ════════════════════════════════════════════════════════════════════════
# (key, English label, Arabic label, group)
TARGET_FIELDS = [
    ("owner_name",      "Owner name",       "اسم العميل",          "owner"),
    ("owner_phone",     "Phone",            "رقم الهاتف",          "owner"),
    ("owner_email",     "Email",            "البريد الإلكتروني",    "owner"),
    ("owner_address",   "Address",          "العنوان",             "owner"),
    ("owner_notes",     "Owner notes",      "ملاحظات عن العميل",    "owner"),
    ("pet_name",        "Pet name",         "اسم الحيوان",          "pet"),
    ("pet_species",     "Species",          "النوع",               "pet"),
    ("pet_breed",       "Breed",            "السلالة",             "pet"),
    ("pet_sex",         "Sex",              "الجنس",               "pet"),
    ("pet_dob",         "Date of birth",    "تاريخ الميلاد",        "pet"),
    ("pet_weight",      "Weight (kg)",      "الوزن بالكيلوجرام",    "pet"),
    ("pet_color",       "Colour",           "اللون",               "pet"),
    ("pet_microchip",   "Microchip number", "رقم الشريحة",          "pet"),
    ("pet_notes",       "Pet notes",        "ملاحظات عن الحيوان",   "pet"),
    ("visit_date",      "Visit date",       "تاريخ الزيارة",        "visit"),
    ("visit_type",      "Visit type",       "نوع الزيارة",          "visit"),
    ("visit_doctor",    "Doctor",           "الطبيب",              "visit"),
    ("visit_complaint", "Reason / diagnosis", "سبب الزيارة أو التشخيص", "visit"),
    ("visit_notes",     "Visit notes",      "ملاحظات الزيارة",      "visit"),
]

FIELD_KEYS = [f[0] for f in TARGET_FIELDS]

GROUP_LABELS = {
    "owner": ("Owner", "العميل"),
    "pet":   ("Pet", "الحيوان"),
    "visit": ("Visit", "الزيارة"),
}

# Header aliases used to pre-select the mapping. Order inside each list does
# not matter; order of the dict does — the first field that claims a column
# wins, so put the specific fields before the vague ones.
_HEADER_HINTS = {
    "owner_phone": [
        "phone", "mobile", "telephone", "tel", "phone number", "mobile number",
        "contact", "contact number", "whatsapp", "whatsapp number", "cell",
        "تليفون", "التليفون", "رقم التليفون", "هاتف", "الهاتف", "رقم الهاتف",
        "موبايل", "الموبايل", "جوال", "الجوال", "واتساب", "رقم الواتساب", "محمول",
    ],
    "owner_email": [
        "email", "e mail", "mail", "email address",
        "ايميل", "الايميل", "البريد", "البريد الالكتروني", "بريد الكتروني",
    ],
    "owner_address": [
        "address", "owner address", "location", "street",
        "عنوان", "العنوان", "عنوان العميل", "السكن",
    ],
    "pet_microchip": [
        "microchip", "microchip id", "microchip number", "chip", "chip id", "chip no",
        "شريحة", "الشريحة", "رقم الشريحة",
    ],
    "pet_dob": [
        "dob", "date of birth", "birth date", "birthdate", "birthday", "born",
        "تاريخ الميلاد", "الميلاد", "تاريخ الولادة", "المواليد",
    ],
    "pet_weight": [
        "weight", "weight kg", "kg", "wt",
        "وزن", "الوزن", "الوزن بالكيلو",
    ],
    "pet_species": [
        "species", "animal type", "pet type", "type", "animal",
        "النوع", "نوع", "نوع الحيوان", "الفصيلة", "فصيلة",
    ],
    "pet_breed": [
        "breed", "pet breed",
        "سلالة", "السلالة", "الفصيله",
    ],
    "pet_sex": [
        "sex", "gender", "pet sex", "male female",
        "جنس", "الجنس", "ذكر انثي", "النوع جنس",
    ],
    "pet_color": [
        "color", "colour", "pet color", "coat",
        "لون", "اللون",
    ],
    "pet_name": [
        "pet", "pet name", "petname", "animal name", "patient", "patient name",
        "اسم الحيوان", "الحيوان", "اسم الاليف", "الحيوان الاليف", "اسم القط",
        "اسم الكلب", "اسم المريض", "الاليف",
    ],
    "owner_name": [
        "name", "owner", "owner name", "ownername", "client", "client name",
        "customer", "customer name", "full name", "fullname",
        "اسم العميل", "العميل", "اسم المالك", "المالك", "الاسم", "اسم الزبون",
        "صاحب الحيوان", "اسم صاحب الحيوان", "اسم العميل بالكامل",
    ],
    "visit_date": [
        "visit date", "date of visit", "appointment date", "appointment",
        "exam date", "date", "visit", "checkup date",
        "تاريخ الزيارة", "الزيارة", "تاريخ الكشف", "تاريخ", "التاريخ",
        "موعد", "الموعد", "تاريخ الموعد",
    ],
    "visit_type": [
        "visit type", "appointment type", "service", "service type",
        "نوع الزيارة", "نوع الكشف", "الخدمة", "نوع الخدمة",
    ],
    "visit_doctor": [
        "doctor", "doctor name", "vet", "veterinarian", "vet name", "dr",
        "الطبيب", "طبيب", "الدكتور", "دكتور", "اسم الطبيب", "الطبيب المعالج",
    ],
    "visit_complaint": [
        "reason", "complaint", "chief complaint", "diagnosis", "symptoms",
        "case", "problem", "treatment",
        "الشكوى", "السبب", "سبب الزيارة", "التشخيص", "الاعراض", "الحالة", "العلاج",
    ],
    "owner_notes": [
        "owner notes", "client notes", "ملاحظات العميل",
    ],
    "pet_notes": [
        "pet notes", "notes", "note", "remarks", "comment", "comments",
        "ملاحظات", "ملحوظات", "ملاحظة",
    ],
    "visit_notes": [
        "visit notes", "ملاحظات الزيارة",
    ],
}


# ════════════════════════════════════════════════════════════════════════
#  Text / value normalisation
# ════════════════════════════════════════════════════════════════════════

# Arabic-Indic (٠-٩) and Extended Arabic-Indic (۰-۹) digits → ASCII.
# Egyptian sheets are full of these, especially in phone columns.
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

# Zero-width and bidi control characters. Excel sprinkles these through
# Arabic cells; left in place they make two identical-looking names unequal,
# which silently breaks duplicate detection.
_INVISIBLE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]")

# Arabic letter variants folded together for *matching only* — stored values
# keep the user's original spelling.
_AR_FOLD = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ئ": "ي", "ة": "ه", "ؤ": "و",
})
_HARAKAT = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u0640]")

_NULLISH = {"", "none", "nan", "null", "n/a", "na", "-", "--", "#n/a"}


def clean_text(value) -> str:
    """Cell → trimmed unicode string. Arabic content passes through intact."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    if isinstance(value, float) and value.is_integer():
        value = int(value)          # 1234.0 in a phone column → "1234"
    s = _INVISIBLE.sub("", str(value))
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return "" if s.lower() in _NULLISH else s


def fold(value) -> str:
    """Aggressively folded form used only for comparing/guessing, never stored."""
    s = clean_text(value).lower()
    s = _HARAKAT.sub("", s).translate(_AR_FOLD)
    s = re.sub(r"[_\-./\\(),:;#]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalize_phone(value) -> str:
    """Egyptian phone numbers → one canonical local form.

    Rule (documented for the user on the mapping screen):
      1. Arabic-Indic digits become ASCII, then everything that is not a
         digit is dropped — spaces, dashes, brackets and the leading '+'.
      2. A leading international prefix '00' is removed.
      3. A leading country code '20' followed by at least 9 more digits is
         replaced by a single '0'.
      4. If the result does not already start with '0', one is added.

    So 01012345678, +201012345678 and '0020 101 234 5678' all end up as
    01012345678, which is what duplicate detection compares.
    """
    s = clean_text(value).translate(_AR_DIGITS)
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("20") and len(digits) >= 11:
        digits = digits[2:]
    if not digits.startswith("0"):
        digits = "0" + digits
    return digits


_DATE_FORMATS = (
    "%Y-%m-%d", "%Y/%m/%d",
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",     # Egypt writes day first
    "%m/%d/%Y",
    "%d/%m/%y", "%Y%m%d",
)


def normalize_date(value):
    """→ 'YYYY-MM-DD', or None when the cell is empty, or False when unparseable.

    Day-first is tried before month-first: 03/04/2024 is 3 April, the Egyptian
    reading. False (not None) is returned for junk so the caller can tell
    'nothing here' from 'the user typed something we cannot understand'.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()[:10]
    s = clean_text(value).translate(_AR_DIGITS)
    if not s:
        return None
    s = s.split(" ")[0].replace("T", " ").split(" ")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return False


def normalize_float(value):
    """→ float, None when empty, or False when unparseable."""
    s = clean_text(value).translate(_AR_DIGITS)
    if not s:
        return None
    s = re.sub(r"[^\d.\-]", "", s)
    if not s or s in ("-", ".", "-."):
        return False
    try:
        return float(s)
    except ValueError:
        return False


_SEX_MAP = {
    "m": "Male", "male": "Male", "ذكر": "Male", "زكر": "Male",
    "f": "Female", "female": "Female", "انثي": "Female", "انثه": "Female",
    "أنثى": "Female", "انثى": "Female",
}


def normalize_sex(value) -> str:
    return _SEX_MAP.get(fold(value), clean_text(value) or "Unknown")


# Platform visit_type vocabulary. Anything unrecognised becomes Consultation,
# with the original text preserved in the visit notes by the caller.
_VISIT_TYPES = {
    "consultation": "Consultation", "كشف": "Consultation", "استشارة": "Consultation",
    "vaccination": "Vaccination", "vaccine": "Vaccination", "تطعيم": "Vaccination",
    "تحصين": "Vaccination",
    "surgery": "Surgery", "operation": "Surgery", "جراحة": "Surgery", "عملية": "Surgery",
    "follow up": "Follow-up", "followup": "Follow-up", "متابعة": "Follow-up",
    "emergency": "Emergency", "طوارئ": "Emergency", "طواري": "Emergency",
    "wellness": "Wellness", "grooming": "Wellness", "lab test": "Wellness",
    "تجميل": "Wellness", "تحليل": "Wellness",
}


def normalize_visit_type(value) -> str:
    return _VISIT_TYPES.get(fold(value), "Consultation")


# ════════════════════════════════════════════════════════════════════════
#  Reading the file
# ════════════════════════════════════════════════════════════════════════

class SpreadsheetError(Exception):
    """Unreadable upload. Carries a bilingual, non-technical explanation."""

    def __init__(self, en, ar):
        super().__init__(en)
        self.en = en
        self.ar = ar


# Magic-byte signatures, same approach as blueprints/uploads/routes.py.
_ZIP_MAGIC = b"PK\x03\x04"          # xlsx is a zip container
_OLE_MAGIC = b"\xd0\xcf\x11\xe0"    # legacy .xls / .doc


def check_spreadsheet_bytes(data: bytes, filename: str) -> str:
    """Validate the upload really is a spreadsheet. Returns 'xlsx' or 'csv'.

    Raises SpreadsheetError with an explanation a vet can act on.
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not data:
        raise SpreadsheetError(
            "The file is empty. Open it in Excel, check your data is there, and save it again.",
            "الملف فارغ. افتحه في إكسل وتأكد من وجود البيانات ثم احفظه مرة أخرى.",
        )

    if ext == "xlsx":
        if data[:4] != _ZIP_MAGIC:
            if data[:4] == _OLE_MAGIC:
                raise SpreadsheetError(
                    "This is an old Excel file saved with an .xlsx name. Open it in "
                    "Excel and choose File → Save As → Excel Workbook (.xlsx).",
                    "هذا ملف إكسل قديم محفوظ باسم ‎.xlsx. افتحه في إكسل ثم اختر "
                    "ملف ← حفظ باسم ← مصنّف Excel ‏(.xlsx).",
                )
            raise SpreadsheetError(
                "This file is not a real Excel workbook, even though it is named .xlsx. "
                "Re-save it from Excel and upload it again.",
                "هذا الملف ليس مصنّف إكسل حقيقياً رغم أن امتداده ‎.xlsx. "
                "أعد حفظه من إكسل ثم ارفعه من جديد.",
            )
        return "xlsx"

    if ext in ("csv", "txt"):
        if data[:4] == _ZIP_MAGIC or data[:4] == _OLE_MAGIC:
            raise SpreadsheetError(
                "This is an Excel workbook named .csv. Rename it to .xlsx, or open it "
                "in Excel and choose File → Save As → CSV UTF-8.",
                "هذا مصنّف إكسل باسم ‎.csv. غيّر امتداده إلى ‎.xlsx، أو افتحه في إكسل "
                "واختر ملف ← حفظ باسم ← ‏CSV UTF-8.",
            )
        return "csv"

    if ext == "xls":
        raise SpreadsheetError(
            "Old .xls files cannot be read. Open the file in Excel and choose "
            "File → Save As → Excel Workbook (.xlsx), then upload the new file.",
            "لا يمكن قراءة ملفات ‎.xls القديمة. افتح الملف في إكسل واختر "
            "ملف ← حفظ باسم ← مصنّف Excel ‏(.xlsx) ثم ارفع الملف الجديد.",
        )

    raise SpreadsheetError(
        "Only Excel (.xlsx) and CSV (.csv) files can be imported. "
        f"You uploaded a .{ext or 'unknown'} file.",
        "يمكن استيراد ملفات إكسل ‎(.xlsx) وملفات ‎CSV فقط. "
        f"الملف الذي رفعته من نوع ‎.{ext or 'غير معروف'}.",
    )


def _decode_csv(data: bytes) -> str:
    """Decode CSV bytes without mangling Arabic.

    UTF-8 is strict, so it is tried first and fails loudly on anything else;
    cp1256 is what Arabic Windows Excel writes when you 'Save as CSV'.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp1256"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SpreadsheetError(
        "The text in this CSV file could not be read. In Excel choose "
        "File → Save As → CSV UTF-8, then upload the new file.",
        "تعذّرت قراءة النصوص في ملف ‎CSV. من إكسل اختر ملف ← حفظ باسم ← "
        "‏CSV UTF-8 ثم ارفع الملف الجديد.",
    )


def read_table(data: bytes, filename: str):
    """(headers, rows) from an uploaded spreadsheet.

    `headers` is a list of column titles, `rows` a list of value lists padded
    to the same width. Fully blank rows are dropped. Raises SpreadsheetError.
    """
    kind = check_spreadsheet_bytes(data, filename)

    if kind == "xlsx":
        try:
            import openpyxl
        except ImportError:  # pragma: no cover - openpyxl is in requirements
            raise SpreadsheetError(
                "Excel support is not installed on this server. Ask your "
                "administrator to install the 'openpyxl' package, or upload a CSV file.",
                "دعم ملفات إكسل غير مثبّت على الخادم. اطلب من مسؤول النظام تثبيت "
                "حزمة ‎openpyxl، أو ارفع ملفاً بصيغة ‎CSV.",
            )
        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise SpreadsheetError(
                "This Excel file could not be opened — it may be password protected "
                f"or damaged. Technical detail: {exc}",
                "تعذّر فتح ملف إكسل هذا؛ قد يكون محمياً بكلمة مرور أو تالفاً. "
                f"التفصيل الفني: {exc}",
            )
        try:
            ws = wb.active
            raw = []
            for row in ws.iter_rows(values_only=True):
                raw.append(list(row))
                if len(raw) > MAX_ROWS + 1:
                    break
        finally:
            wb.close()
    else:
        text = _decode_csv(data)
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            reader = csv.reader(io.StringIO(text), dialect)
        except csv.Error:
            reader = csv.reader(io.StringIO(text))
        raw = []
        for row in reader:
            raw.append(list(row))
            if len(raw) > MAX_ROWS + 1:
                break

    if not raw:
        raise SpreadsheetError(
            "The first sheet in this file has no rows.",
            "الورقة الأولى في هذا الملف لا تحتوي على أي صفوف.",
        )

    header_row = raw[0]
    headers = []
    for i, h in enumerate(header_row):
        title = clean_text(h)
        headers.append(title or f"Column {i + 1}")
    width = len(headers)

    rows = []
    for row in raw[1:]:
        if all(clean_text(v) == "" for v in row):
            continue
        padded = list(row[:width]) + [None] * max(0, width - len(row))
        rows.append(padded)

    if len(rows) > MAX_ROWS:
        raise SpreadsheetError(
            f"This file has more than {MAX_ROWS:,} rows. Split it into smaller "
            "files and import them one at a time.",
            f"يحتوي هذا الملف على أكثر من {MAX_ROWS:,} صف. قسّمه إلى ملفات أصغر "
            "واستوردها واحداً تلو الآخر.",
        )
    if not rows:
        raise SpreadsheetError(
            "This file has column titles but no data rows underneath them.",
            "يحتوي هذا الملف على عناوين أعمدة فقط بدون أي صفوف بيانات.",
        )
    return headers, rows


# ════════════════════════════════════════════════════════════════════════
#  Column mapping
# ════════════════════════════════════════════════════════════════════════

def guess_mapping(headers) -> dict:
    """{column index: field key} — a starting point the user can override.

    Exact alias matches are taken first across every field, then substring
    matches, so a column literally called 'Phone' always beats a column called
    'Emergency phone contact' for the phone slot.
    """
    folded = [fold(h) for h in headers]
    mapping = {}
    used_cols = set()

    for exact_pass in (True, False):
        for field, aliases in _HEADER_HINTS.items():
            if field in mapping.values():
                continue
            folded_aliases = [fold(a) for a in aliases]
            for idx, head in enumerate(folded):
                if idx in used_cols or not head:
                    continue
                hit = (
                    head in folded_aliases
                    if exact_pass
                    else any(a and (a in head or head in a) for a in folded_aliases)
                )
                if hit:
                    mapping[idx] = field
                    used_cols.add(idx)
                    break
    return mapping


def mapping_signature(headers) -> str:
    """Stable id for 'a file shaped like this one', used to recall a mapping."""
    import hashlib
    joined = "\u0001".join(fold(h) for h in headers)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def clean_mapping(raw_mapping, headers) -> dict:
    """Coerce form input to {int column: valid field key}, one column per field."""
    mapping = {}
    taken = set()
    for key, value in (raw_mapping or {}).items():
        try:
            idx = int(key)
        except (TypeError, ValueError):
            continue
        field = str(value or "").strip()
        if field not in FIELD_KEYS or not (0 <= idx < len(headers)):
            continue
        if field in taken:
            continue
        taken.add(field)
        mapping[idx] = field
    return mapping


# ════════════════════════════════════════════════════════════════════════
#  The import itself
# ════════════════════════════════════════════════════════════════════════

def _blank_counts():
    return {"created": 0, "updated": 0, "skipped": 0}


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row_values(row, mapping):
    """One sheet row → {field key: raw cell value}."""
    return {field: row[idx] for idx, field in mapping.items() if idx < len(row)}


def _update_sql(table, values, row_id):
    cols = list(values.keys())
    sql = f"UPDATE {table} SET " + ", ".join(f"{c}=?" for c in cols) + " WHERE id=?"
    return sql, tuple(values[c] for c in cols) + (row_id,)


def run_import(conn, headers, rows, mapping, strategy="skip", dry_run=True,
               created_by="import"):
    """Plan (dry_run=True) or perform (dry_run=False) the import.

    With dry_run=True not one statement that changes data is executed — every
    write sits behind `if not dry_run`, and the counts come from the same code
    path that does the writing, so the preview cannot drift from reality.

    The caller owns the transaction. For a real import wrap this in
    `with conn:` so a failure half way through rolls the whole file back.

    Duplicate keys:
      owner  — normalised phone against owners.phone / owners.whatsapp_phone,
               falling back to an exact full_name match when the row has no
               phone at all
      pet    — pet_name + owner_id
      visit  — pet_id + visit_date + visit_type

    `strategy` decides what happens on a match: 'skip' leaves the existing
    record alone, 'update' fills in non-empty incoming values, 'create' adds a
    second record regardless.
    """
    if strategy not in STRATEGIES:
        strategy = "skip"

    mapped_fields = set(mapping.values())
    result = {
        "dry_run": dry_run,
        "strategy": strategy,
        "rows_total": len(rows),
        "rows_ok": 0,
        "rows_failed": 0,
        "counts": {"owners": _blank_counts(), "pets": _blank_counts(),
                   "visits": _blank_counts()},
        "errors": [],
        "duplicates": [],
        "preview": [],
        "failed_rows": [],
        "mapped_fields": sorted(mapped_fields),
        "started_at": _now(),
        "finished_at": None,
    }

    def fail(row_no, en, ar, values):
        result["rows_failed"] += 1
        if len(result["errors"]) < MAX_ERRORS:
            result["errors"].append({"row": row_no, "en": en, "ar": ar})
        result["failed_rows"].append({"row": row_no, "reason": en, "values": values})

    def note_dup(row_no, entity, en, ar, action):
        if len(result["duplicates"]) < MAX_DUPLICATES:
            result["duplicates"].append({"row": row_no, "entity": entity,
                                         "en": en, "ar": ar, "action": action})

    # In-run caches. A file with one row per visit repeats the same owner and
    # pet dozens of times; without these, re-running the same file would be
    # safe but the same file's own repeats would not.
    owner_cache = {}      # owner key -> id (negative = created in this dry run)
    pet_cache = {}        # (owner key, folded pet name) -> id
    visit_cache = set()   # (pet key, date, type)
    pseudo = [0]          # dry-run id generator

    def next_pseudo():
        pseudo[0] -= 1
        return pseudo[0]

    now = _now()

    for offset, row in enumerate(rows):
        row_no = offset + 2         # +1 for the header, +1 because Excel is 1-based
        raw = _row_values(row, mapping)

        owner_name = clean_text(raw.get("owner_name"))
        phone_in = clean_text(raw.get("owner_phone"))
        phone = normalize_phone(phone_in)
        pet_name = clean_text(raw.get("pet_name"))

        if not owner_name and not phone and not pet_name:
            continue        # blank-ish row, nothing to say about it

        if phone_in and not phone:
            fail(row_no,
                 f"The phone number '{phone_in}' has no digits in it. "
                 "Fix that cell in your file, or clear it.",
                 f"رقم الهاتف «{phone_in}» لا يحتوي على أي أرقام. "
                 "صحّح هذه الخانة في ملفك أو اتركها فارغة.",
                 raw)
            continue

        if not owner_name and not phone:
            fail(row_no,
                 "This row has a pet but no owner name and no phone number. "
                 "Add the owner's name or phone to this row.",
                 "هذا الصف يحتوي على حيوان بدون اسم عميل وبدون رقم هاتف. "
                 "أضف اسم العميل أو رقم هاتفه إلى هذا الصف.",
                 raw)
            continue

        dob = normalize_date(raw.get("pet_dob"))
        if dob is False:
            fail(row_no,
                 f"The date of birth '{clean_text(raw.get('pet_dob'))}' is not a date "
                 "we can read. Use the form DD/MM/YYYY, for example 05/03/2021.",
                 f"تاريخ الميلاد «{clean_text(raw.get('pet_dob'))}» غير مفهوم. "
                 "استخدم الصيغة يوم/شهر/سنة، مثال ‎05/03/2021.",
                 raw)
            continue

        visit_date = normalize_date(raw.get("visit_date"))
        if visit_date is False:
            fail(row_no,
                 f"The visit date '{clean_text(raw.get('visit_date'))}' is not a date "
                 "we can read. Use the form DD/MM/YYYY, for example 05/03/2021.",
                 f"تاريخ الزيارة «{clean_text(raw.get('visit_date'))}» غير مفهوم. "
                 "استخدم الصيغة يوم/شهر/سنة، مثال ‎05/03/2021.",
                 raw)
            continue

        weight = normalize_float(raw.get("pet_weight"))
        if weight is False:
            fail(row_no,
                 f"The weight '{clean_text(raw.get('pet_weight'))}' is not a number. "
                 "Write it as a plain number such as 4.5.",
                 f"الوزن «{clean_text(raw.get('pet_weight'))}» ليس رقماً. "
                 "اكتبه كرقم بسيط مثل ‎4.5.",
                 raw)
            continue

        # ── owner ────────────────────────────────────────────────────────
        owner_key = f"p:{phone}" if phone else f"n:{fold(owner_name)}"
        owner_action = "created"
        owner_id = owner_cache.get(owner_key)

        if owner_id is None:
            existing = None
            if phone:
                existing = conn.execute(
                    "SELECT id FROM owners WHERE phone=? OR whatsapp_phone=?",
                    (phone, phone),
                ).fetchone()
            elif owner_name:
                existing = conn.execute(
                    "SELECT id FROM owners WHERE full_name=?", (owner_name,)
                ).fetchone()

            owner_values = {
                "full_name": owner_name or phone,
                "phone": phone,
                "whatsapp_phone": phone,
                "email": clean_text(raw.get("owner_email")),
                "address": clean_text(raw.get("owner_address")),
                "notes": clean_text(raw.get("owner_notes")),
            }

            if existing and strategy != "create":
                owner_id = existing["id"]
                match_on = f"phone {phone}" if phone else f"name {owner_name}"
                match_ar = f"رقم الهاتف {phone}" if phone else f"الاسم {owner_name}"
                if strategy == "update":
                    owner_action = "updated"
                    changes = {k: v for k, v in owner_values.items() if v}
                    changes["updated_at"] = now
                    note_dup(row_no, "owner",
                             f"Owner already on file (matched on {match_on}) — details will be updated.",
                             f"العميل موجود بالفعل (تمت المطابقة على {match_ar}) — سيتم تحديث بياناته.",
                             "update")
                    if not dry_run:
                        sql, params = _update_sql("owners", changes, owner_id)
                        conn.execute(sql, params)
                else:
                    owner_action = "skipped"
                    note_dup(row_no, "owner",
                             f"Owner already on file (matched on {match_on}) — left unchanged.",
                             f"العميل موجود بالفعل (تمت المطابقة على {match_ar}) — لم يتم تغييره.",
                             "skip")
            else:
                owner_action = "created"
                if dry_run:
                    owner_id = next_pseudo()
                else:
                    cur = conn.execute(
                        """INSERT INTO owners(full_name, phone, whatsapp_phone, email,
                                              address, notes, created_by, created_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?)""",
                        (owner_values["full_name"], owner_values["phone"],
                         owner_values["whatsapp_phone"], owner_values["email"],
                         owner_values["address"], owner_values["notes"],
                         created_by, now, now),
                    )
                    owner_id = cur.lastrowid
            owner_cache[owner_key] = owner_id
            result["counts"]["owners"][owner_action] += 1
        else:
            owner_action = "skipped"        # already handled earlier in this file

        # ── pet ──────────────────────────────────────────────────────────
        pet_id = None
        pet_action = None
        if pet_name:
            pet_key = (owner_key, fold(pet_name))
            pet_id = pet_cache.get(pet_key)
            if pet_id is None:
                existing = None
                if owner_id is not None and owner_id > 0:
                    existing = conn.execute(
                        "SELECT id FROM pets WHERE pet_name=? AND owner_id=?",
                        (pet_name, owner_id),
                    ).fetchone()

                pet_values = {
                    "species": clean_text(raw.get("pet_species")) or "Unknown",
                    "breed": clean_text(raw.get("pet_breed")),
                    "sex": normalize_sex(raw.get("pet_sex")) if "pet_sex" in mapped_fields else "Unknown",
                    "dob": dob,
                    "weight_kg": weight,
                    "color": clean_text(raw.get("pet_color")),
                    "microchip_id": clean_text(raw.get("pet_microchip")),
                    "notes": clean_text(raw.get("pet_notes")),
                }

                if existing and strategy != "create":
                    pet_id = existing["id"]
                    if strategy == "update":
                        pet_action = "updated"
                        changes = {k: v for k, v in pet_values.items()
                                   if v not in (None, "", "Unknown")}
                        changes["updated_at"] = now
                        note_dup(row_no, "pet",
                                 f"'{pet_name}' is already registered to this owner — details will be updated.",
                                 f"«{pet_name}» مسجّل بالفعل لدى هذا العميل — سيتم تحديث بياناته.",
                                 "update")
                        if not dry_run:
                            sql, params = _update_sql("pets", changes, pet_id)
                            conn.execute(sql, params)
                    else:
                        pet_action = "skipped"
                        note_dup(row_no, "pet",
                                 f"'{pet_name}' is already registered to this owner — left unchanged.",
                                 f"«{pet_name}» مسجّل بالفعل لدى هذا العميل — لم يتم تغييره.",
                                 "skip")
                else:
                    pet_action = "created"
                    if dry_run:
                        pet_id = next_pseudo()
                    else:
                        cur = conn.execute(
                            """INSERT INTO pets(owner_id, pet_name, species, breed, sex, dob,
                                                weight_kg, color, microchip_id, notes,
                                                is_active, created_at, updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                            (owner_id, pet_name, pet_values["species"], pet_values["breed"],
                             pet_values["sex"], pet_values["dob"], pet_values["weight_kg"],
                             pet_values["color"], pet_values["microchip_id"],
                             pet_values["notes"], now, now),
                        )
                        pet_id = cur.lastrowid
                pet_cache[pet_key] = pet_id
                result["counts"]["pets"][pet_action] += 1
            else:
                pet_action = "skipped"

        # ── visit ────────────────────────────────────────────────────────
        visit_action = None
        if visit_date and pet_id is not None:
            visit_type = normalize_visit_type(raw.get("visit_type"))
            vkey = (pet_id, visit_date, visit_type)
            if vkey in visit_cache:
                visit_action = "skipped"
            else:
                existing = None
                if pet_id > 0:
                    existing = conn.execute(
                        "SELECT id FROM visits WHERE pet_id=? AND visit_date=? AND visit_type=?",
                        (pet_id, visit_date, visit_type),
                    ).fetchone()
                if existing and strategy != "create":
                    visit_action = "skipped"
                    note_dup(row_no, "visit",
                             f"A {visit_type} visit for this pet on {visit_date} is already recorded.",
                             f"توجد بالفعل زيارة ({visit_type}) لهذا الحيوان بتاريخ {visit_date}.",
                             "skip")
                else:
                    visit_action = "created"
                    if not dry_run:
                        conn.execute(
                            """INSERT INTO visits(owner_id, pet_id, doctor_name, visit_date,
                                                  visit_type, status, chief_complaint, notes,
                                                  created_by, created_at, updated_at)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                            (owner_id, pet_id, clean_text(raw.get("visit_doctor")),
                             visit_date, visit_type, "Completed",
                             clean_text(raw.get("visit_complaint")),
                             clean_text(raw.get("visit_notes")),
                             created_by, now, now),
                        )
                visit_cache.add(vkey)
                result["counts"]["visits"][visit_action] += 1
        elif visit_date and pet_id is None:
            note_dup(row_no, "visit",
                     "This row has a visit date but no pet name, so the visit was not imported.",
                     "هذا الصف يحتوي على تاريخ زيارة بدون اسم حيوان، لذلك لم يتم استيراد الزيارة.",
                     "skip")

        result["rows_ok"] += 1

        if len(result["preview"]) < PREVIEW_ROWS:
            result["preview"].append({
                "row": row_no,
                "owner_name": owner_name or phone,
                "owner_phone": phone,
                "owner_phone_original": phone_in,
                "owner_email": clean_text(raw.get("owner_email")),
                "owner_address": clean_text(raw.get("owner_address")),
                "pet_name": pet_name,
                "pet_species": clean_text(raw.get("pet_species")) or ("Unknown" if pet_name else ""),
                "pet_sex": normalize_sex(raw.get("pet_sex")) if pet_name and "pet_sex" in mapped_fields else "",
                "pet_dob": dob or "",
                "pet_weight": "" if weight is None else weight,
                "visit_date": visit_date or "",
                "visit_type": normalize_visit_type(raw.get("visit_type")) if visit_date else "",
                "owner_action": owner_action,
                "pet_action": pet_action or "",
                "visit_action": visit_action or "",
            })

    result["finished_at"] = _now()
    return result


def failed_rows_csv(failed_rows) -> str:
    """The rows that could not be imported, as a CSV the user can fix and re-upload."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Row in your file", "Why it was not imported"] + FIELD_KEYS)
    for item in failed_rows:
        values = item.get("values") or {}
        writer.writerow(
            [item.get("row", ""), item.get("reason", "")]
            + [clean_text(values.get(k)) for k in FIELD_KEYS]
        )
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════
#  Command line — same engine, no browser
# ════════════════════════════════════════════════════════════════════════

def main(argv=None):
    import argparse
    import sqlite3

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("file", help="Path to the .xlsx or .csv file to import")
    parser.add_argument("--db", default=os.environ.get("PLATFORM_DB_PATH", ""),
                        help="Path to the SQLite database (or set PLATFORM_DB_PATH)")
    parser.add_argument("--apply", action="store_true",
                        help="Actually write. Without this it is a dry run.")
    parser.add_argument("--strategy", choices=STRATEGIES, default="skip")
    args = parser.parse_args(argv)

    if not args.db:
        parser.error("no database given — pass --db or set PLATFORM_DB_PATH")

    with open(args.file, "rb") as fh:
        data = fh.read()
    try:
        headers, rows = read_table(data, os.path.basename(args.file))
    except SpreadsheetError as exc:
        print(f"ERROR: {exc.en}")
        return 1

    mapping = guess_mapping(headers)
    print("Column mapping:")
    for idx, head in enumerate(headers):
        print(f"  {head!r:<30} -> {mapping.get(idx, '(ignored)')}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        if args.apply:
            with conn:
                report = run_import(conn, headers, rows, mapping,
                                    strategy=args.strategy, dry_run=False,
                                    created_by="cli_import")
        else:
            report = run_import(conn, headers, rows, mapping,
                                strategy=args.strategy, dry_run=True)
    finally:
        conn.close()

    print(f"\nRows: {report['rows_total']} total, {report['rows_ok']} usable, "
          f"{report['rows_failed']} with problems")
    for entity, counts in report["counts"].items():
        print(f"  {entity:<8} created={counts['created']} "
              f"updated={counts['updated']} skipped={counts['skipped']}")
    for err in report["errors"][:20]:
        print(f"  row {err['row']}: {err['en']}")
    if not args.apply:
        print("\nDry run — nothing was written. Re-run with --apply to import.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
