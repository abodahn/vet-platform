"""Arabic text in generated PDFs.

Before this was fixed, every PDF generator raised FPDFUnicodeEncodingException
on the first Arabic character, because the core Helvetica fonts carry no Arabic
glyphs. A clinic only had to type its own name into Settings to break every
invoice, vaccination certificate and payslip it would ever issue.

Runs on SQLite with no PostgreSQL and no network.
"""
import pytest

pytest.importorskip("fpdf", reason="fpdf2 is required for PDF generation")

from models import pdf_generator as pg


CLINIC_AR = {
    "name": "مستشفى اليفي البيطري",
    "doctor_name": "د. حاتم الخطيب",
    "phone": "+20 100 000 0000",
    "address": "القاهرة، مصر",
    "currency": "EGP",
}
CLINIC_EN = {
    "name": "Aleefy Animal Hospital",
    "doctor_name": "Dr. Hatem El Khateeb",
    "phone": "+20 100 000 0000",
    "address": "Cairo, Egypt",
    "currency": "EGP",
}
INVOICE_AR = {
    "invoice_number": "INV-0001", "issue_date": "2026-07-28",
    "owner_name": "أحمد الجوهري", "pet_name": "لولو",
    "subtotal": 1250.75, "discount_amount": 50.0, "tax_amount": 0.0,
    "total": 1200.75, "paid_amount": 1200.75, "due_amount": 0.0,
    "status": "Paid", "notes": "شكراً لزيارتكم",
    "lines": [{"description": "كشف بيطري", "quantity": 1,
               "unit_price": 500.0, "total": 500.0}],
}


# ─── The shaping helper ───────────────────────────────────────────────────────

def test_latin_text_passes_through_untouched():
    """English documents must be unaffected by the Arabic support."""
    for s in ("Consultation", "INV-0001", "1,250.75 EGP", "", "Dr. Hatem"):
        assert pg.ar(s) == s


def test_none_becomes_empty_string():
    assert pg.ar(None) == ""


def test_has_arabic_detection():
    assert pg.has_arabic("لولو")
    assert pg.has_arabic("Rabies لقاح")      # mixed script
    assert not pg.has_arabic("Lulu")
    assert not pg.has_arabic("")
    assert not pg.has_arabic(None)


def test_arabic_is_reshaped_and_reordered():
    src = "كشف بيطري"
    out = pg.ar(src)
    assert out != src, "text was not transformed at all"
    # Reshaping maps base letters onto their positional presentation forms,
    # which live in the Arabic Presentation Forms blocks.
    assert any("ﹰ" <= ch <= "﻿" or "ﭐ" <= ch <= "﷿" for ch in out), \
        "no presentation forms produced — letters would render disconnected"


# ─── The three generators ─────────────────────────────────────────────────────

def test_invoice_with_arabic_clinic_and_customer():
    data = pg.generate_invoice_pdf(INVOICE_AR, CLINIC_AR)
    assert data[:4] == b"%PDF"
    assert len(data) > 5000
    assert b"Cairo" in data, "Arabic-capable font was not embedded"


def test_invoice_english_still_works():
    inv = {**INVOICE_AR, "owner_name": "Ahmed", "pet_name": "Lulu", "notes": "Thanks",
           "lines": [{"description": "Consultation", "quantity": 1,
                      "unit_price": 500.0, "total": 500.0}]}
    data = pg.generate_invoice_pdf(inv, CLINIC_EN)
    assert data[:4] == b"%PDF"


def test_vaccination_certificate_with_arabic():
    vacc = {"vaccine_name": "لقاح السعار", "date_given": "2026-07-28",
            "next_due": "2027-07-28", "batch_number": "B-2026-07",
            "vet_name": "د. حاتم الخطيب", "route": "تحت الجلد"}
    pet = {"pet_name": "لولو", "species": "قط", "breed": "شيرازي", "sex": "أنثى",
           "dob": "2023-01-15", "microchip": "900000000000001",
           "owner_name": "أحمد الجوهري", "color": "أبيض", "weight_kg": 4.2}
    data = pg.generate_vaccination_certificate_pdf(vacc, pet, CLINIC_AR)
    assert data[:4] == b"%PDF"
    assert b"Cairo" in data


def test_payslip_with_arabic():
    salary = {"month": "2026-07", "staff_name": "منى عبد الله",
              "job_title": "ممرضة بيطرية", "basic_salary": 9000.0,
              "allowances": 1500.0, "deductions": 500.0, "net_salary": 10000.0,
              "days_present": 26, "days_absent": 0}
    data = pg.generate_payslip_pdf(salary, CLINIC_AR)
    assert data[:4] == b"%PDF"
    assert b"Cairo" in data


# ─── The regression that started it ───────────────────────────────────────────

def test_clinic_typing_its_own_arabic_name_does_not_crash():
    """The exact reported failure: an Arabic clinic name in Settings."""
    data = pg.generate_invoice_pdf(
        {**INVOICE_AR, "owner_name": "Ahmed", "pet_name": "Lulu"},
        {"name": "مستشفى اليفي البيطري", "currency": "EGP"},
    )
    assert data[:4] == b"%PDF"


def test_fonts_are_present_in_the_repo():
    """The TTFs must ship — a deployment without them silently loses Arabic."""
    assert pg._FONTS_AVAILABLE, (
        "Cairo-Regular.ttf / Cairo-Bold.ttf missing from static/fonts — "
        "Arabic PDFs will fall back to Helvetica and crash"
    )
