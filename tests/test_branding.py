"""Per-clinic branding.

Every deployment used to print "Aleefy" on the invoice and the vaccination
certificate the clinic hands to its own customer. These tests pin the two halves
of the fix: the logo upload only accepts real, bounded images, and the clinic's
own identity actually reaches all three generated documents — in Arabic as well
as English.

Runs on SQLite with no network.
"""
import base64
import io

import pytest

pytest.importorskip("fpdf", reason="fpdf2 is required for PDF generation")

from blueprints.settings.routes import LOGO_MAX_UPLOAD, LogoError, encode_logo, sniff_image
from models import pdf_generator as pg


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

CLINIC = {
    "name": "Nile Vet Care",
    "name_ar": "نايل فيت كير",
    "doctor_name": "Dr. Salma Fouad",
    "phone": "+20 2 3333 4444",
    "address": "12 Corniche El Nil, Maadi, Cairo",
    "tax_number": "884-221-903",
    "license_number": "VET-EG-11902",
    "website": "nilevetcare.example",
    "currency": "EGP",
}
CLINIC_AR = {
    "name": "عيادة النيل البيطرية",
    "doctor_name": "د. سلمى فؤاد",
    "phone": "+20 2 3333 4444",
    "address_ar": "١٢ كورنيش النيل، المعادي، القاهرة",
    "tax_number": "884-221-903",
    "license_number": "VET-EG-11902",
    "currency": "EGP",
}

INVOICE = {
    "invoice_number": "INV-0042", "issue_date": "2026-07-28", "status": "Paid",
    "owner_name": "Ahmed Elgohary", "owner_phone": "+20 100 000 0000",
    "pet_name": "Lulu", "doctor_name": "Salma Fouad",
    "subtotal": 900.0, "total": 900.0, "paid_amount": 900.0, "due_amount": 0.0,
    "lines": [{"description": "Consultation", "quantity": 1,
               "unit_price": 900.0, "total": 900.0}],
}
VACC = {"id": 42, "vaccine_name": "Rabies", "batch_number": "B-2026-07",
        "administered_at": "2026-07-28", "next_due_at": "2027-07-28",
        "administered_by": "Salma Fouad"}
PET = {"pet_name": "Lulu", "species": "Cat", "breed": "Shirazi", "sex": "Female",
       "dob": "2023-01-15", "owner_name": "Ahmed Elgohary",
       "owner_phone": "+20 100 000 0000"}
SALARY = {"full_name": "Mona Abdullah", "role": "nurse", "period_year": 2026,
          "period_month": 7, "basic_salary": 9000.0, "allowances": 1500.0,
          "deductions": 500.0, "status": "Paid"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _png(size=(64, 64), color=(200, 30, 60, 255)):
    """A real PNG, produced by the same library that will read it back."""
    Image = pytest.importorskip("PIL.Image", reason="Pillow required for logos")
    buf = io.BytesIO()
    Image.new("RGBA", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _spy_drawn(monkeypatch):
    """Record every string the generators draw.

    Text inside a PDF is compressed and re-encoded as font-subset glyph ids, so
    grepping the output bytes for a clinic name finds nothing even when it is
    printed. Every cell()/multi_cell() call routes its text through
    pdf_generator.ar(), which makes that the one honest place to observe from.
    """
    drawn = []
    real = pg.ar

    def spy(text):
        drawn.append("" if text is None else str(text))
        return real(text)

    monkeypatch.setattr(pg, "ar", spy)
    return drawn


def _contains(drawn, needle):
    return any(needle in s for s in drawn)


# ─── T1: upload validation ────────────────────────────────────────────────────

def test_sniff_recognises_real_images_and_nothing_else():
    assert sniff_image(_png()[:16]) == "PNG"
    assert sniff_image(b"\xff\xd8\xff\xe0" + b"\0" * 12) == "JPEG"
    assert sniff_image(b"GIF89a" + b"\0" * 10) == "GIF"
    assert sniff_image(b"%PDF-1.7" + b"\0" * 8) is None
    assert sniff_image(b"RIFF\0\0\0\0NOTW" + b"\0" * 4) is None, "RIFF alone is not WebP"


def test_non_image_upload_is_rejected():
    """A PDF renamed logo.png must not become the clinic's logo."""
    with pytest.raises(LogoError):
        encode_logo(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\nnot an image at all")
    with pytest.raises(LogoError):
        encode_logo(b"MZ\x90\x00\x03" + b"\0" * 512)   # a Windows executable
    with pytest.raises(LogoError):
        encode_logo(b"")


def test_oversized_upload_is_rejected():
    oversized = PNG_MAGIC + b"\0" * (LOGO_MAX_UPLOAD + 1)
    with pytest.raises(LogoError) as exc:
        encode_logo(oversized)
    assert "large" in str(exc.value).lower()


def test_png_magic_with_garbage_body_is_rejected():
    """Correct magic bytes are necessary, not sufficient — it must still decode."""
    with pytest.raises(LogoError):
        encode_logo(PNG_MAGIC + b"\x00garbage" * 40)


def test_accepted_logo_becomes_a_bounded_data_uri():
    uri = encode_logo(_png())
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1])[:8] == PNG_MAGIC


def test_large_dimensions_are_downscaled():
    """A 4 MB, 3000 px logo would ride along in every page load and every PDF."""
    from blueprints.settings.routes import LOGO_MAX_PX
    Image = pytest.importorskip("PIL.Image")
    uri = encode_logo(_png(size=(3000, 1500)))
    raw = base64.b64decode(uri.split(",", 1)[1])
    img = Image.open(io.BytesIO(raw))
    assert max(img.size) <= LOGO_MAX_PX
    assert len(raw) < 200 * 1024


# ─── T2: branding on the documents that leave the building ────────────────────

def test_invoice_carries_the_clinics_own_name(monkeypatch):
    drawn = _spy_drawn(monkeypatch)
    data = pg.generate_invoice_pdf(INVOICE, CLINIC)
    assert data[:4] == b"%PDF"
    assert _contains(drawn, "Nile Vet Care"), "clinic name missing from the invoice"
    assert not _contains(drawn, "Aleefy"), "another company's name reached the invoice"


def test_invoice_carries_contact_tax_and_licence(monkeypatch):
    drawn = _spy_drawn(monkeypatch)
    pg.generate_invoice_pdf(INVOICE, CLINIC)
    assert _contains(drawn, "+20 2 3333 4444")
    assert _contains(drawn, "Corniche El Nil")
    assert _contains(drawn, "884-221-903")
    assert _contains(drawn, "VET-EG-11902")


@pytest.mark.parametrize("gen", ["invoice", "certificate", "payslip"])
def test_every_document_type_is_branded(monkeypatch, gen):
    drawn = _spy_drawn(monkeypatch)
    data = {
        "invoice":     lambda: pg.generate_invoice_pdf(INVOICE, CLINIC),
        "certificate": lambda: pg.generate_vaccination_certificate_pdf(VACC, PET, CLINIC),
        "payslip":     lambda: pg.generate_payslip_pdf(SALARY, CLINIC),
    }[gen]()
    assert data[:4] == b"%PDF"
    assert _contains(drawn, "Nile Vet Care"), f"{gen} is not branded"
    assert _contains(drawn, "VET-EG-11902"), f"{gen} is missing the licence number"


@pytest.mark.parametrize("gen", ["invoice", "certificate", "payslip"])
def test_arabic_clinic_name_and_address_render_on_every_document(monkeypatch, gen):
    """The reported failure: a clinic types its own Arabic name into Settings."""
    drawn = _spy_drawn(monkeypatch)
    data = {
        "invoice":     lambda: pg.generate_invoice_pdf(INVOICE, CLINIC_AR),
        "certificate": lambda: pg.generate_vaccination_certificate_pdf(VACC, PET, CLINIC_AR),
        "payslip":     lambda: pg.generate_payslip_pdf(SALARY, CLINIC_AR),
    }[gen]()
    assert data[:4] == b"%PDF"
    assert b"Cairo" in data, "Arabic-capable font was not embedded"
    assert _contains(drawn, CLINIC_AR["name"]), f"Arabic clinic name missing from {gen}"
    assert _contains(drawn, CLINIC_AR["address_ar"]), f"Arabic address missing from {gen}"
    # ...and it left through the reshaper, not raw.
    assert pg.ar(CLINIC_AR["name"]) != CLINIC_AR["name"]


def test_arabic_name_ar_appears_alongside_a_latin_name(monkeypatch):
    drawn = _spy_drawn(monkeypatch)
    pg.generate_invoice_pdf(INVOICE, CLINIC)
    assert _contains(drawn, "نايل فيت كير")


# ─── T2: the logo, present and absent ─────────────────────────────────────────

@pytest.mark.parametrize("gen", ["invoice", "certificate", "payslip"])
def test_logo_is_embedded_when_present(gen):
    branded = {**CLINIC, "logo_data": encode_logo(_png())}
    call = {
        "invoice":     lambda c: pg.generate_invoice_pdf(INVOICE, c),
        "certificate": lambda c: pg.generate_vaccination_certificate_pdf(VACC, PET, c),
        "payslip":     lambda c: pg.generate_payslip_pdf(SALARY, c),
    }[gen]
    with_logo = call(branded)
    without   = call(CLINIC)
    assert with_logo[:4] == b"%PDF"
    assert len(with_logo) > len(without), f"{gen} did not grow — no image was placed"


@pytest.mark.parametrize("logo", [None, "", "not-a-data-uri",
                                  "data:image/png;base64,!!!not base64!!!"])
def test_missing_or_corrupt_logo_still_produces_a_valid_pdf(logo):
    """A broken logo must never stop an invoice from reaching a customer."""
    clinic = {**CLINIC, "logo_data": logo}
    for data in (pg.generate_invoice_pdf(INVOICE, clinic),
                 pg.generate_vaccination_certificate_pdf(VACC, PET, clinic),
                 pg.generate_payslip_pdf(SALARY, clinic)):
        assert data[:4] == b"%PDF"
        assert len(data) > 1000


def test_logo_decoder_tolerates_junk():
    assert pg._clinic_logo({}) is None
    assert pg._clinic_logo(None) is None
    assert pg._clinic_logo({"logo_data": "data:image/png;base64"}) is None


# ─── T4: defaults ─────────────────────────────────────────────────────────────

def test_empty_clinic_falls_back_to_a_neutral_name(monkeypatch):
    """A fresh install must not print a placeholder — or somebody else's brand."""
    assert pg._clinic_name({}) == "Veterinary Clinic"
    assert pg._clinic_name(None) == "Veterinary Clinic"
    assert pg._clinic_name({"name": "   "}) == "Veterinary Clinic"
    assert pg._clinic_name({"name": "", "name_ar": "عيادة النيل"}) == "عيادة النيل"

    drawn = _spy_drawn(monkeypatch)
    data = pg.generate_invoice_pdf(INVOICE, {})
    assert data[:4] == b"%PDF"
    assert _contains(drawn, "Veterinary Clinic")
    assert not _contains(drawn, "Aleefy")


# ─── T1/T3: the round trip through Settings ───────────────────────────────────

def _csrf(auth_client):
    from models.security import _CSRF_SESSION_KEY
    with auth_client.session_transaction() as sess:
        return sess.get(_CSRF_SESSION_KEY, "")


def _save_settings(auth_client, **extra):
    files = extra.pop("files", {})
    data = {
        "name": "Nile Vet Care", "name_ar": "نايل فيت كير",
        "tagline": "Care that travels home with you",
        "doctor_name": "Dr. Salma Fouad", "phone": "+20 2 3333 4444",
        "email": "hello@nilevetcare.example", "address": "12 Corniche El Nil, Cairo",
        "address_ar": "١٢ كورنيش النيل، القاهرة", "website": "https://nilevetcare.example",
        "license_number": "VET-EG-11902", "tax_number": "884-221-903",
        "currency": "EGP", "timezone": "Africa/Cairo",
        "_csrf_token": _csrf(auth_client),
    }
    data.update(extra)
    data.update(files)
    return auth_client.post("/system/settings", data=data,
                            content_type="multipart/form-data",
                            follow_redirects=True)


def test_settings_round_trip_stores_logo_tagline_and_arabic_address(auth_client):
    resp = _save_settings(auth_client, files={
        "logo": (io.BytesIO(_png()), "logo.png", "image/png")})
    assert resp.status_code == 200

    import models.database as db
    db.cache_invalidate("clinic_row")
    clinic = db.get_clinic()
    assert clinic["name"] == "Nile Vet Care"
    assert clinic["tagline"] == "Care that travels home with you"
    assert clinic["address_ar"] == "١٢ كورنيش النيل، القاهرة"
    assert (clinic["logo_data"] or "").startswith("data:image/png;base64,")

    # The saved logo must survive straight into a document.
    assert pg.generate_invoice_pdf(INVOICE, clinic)[:4] == b"%PDF"

    # ...and the settings page must show it back as a preview.
    page = auth_client.get("/system/settings").get_data(as_text=True)
    assert "data:image/png;base64," in page


def test_settings_rejects_a_non_image_logo_without_wiping_the_old_one(auth_client):
    _save_settings(auth_client, files={"logo": (io.BytesIO(_png()), "logo.png", "image/png")})
    import models.database as db
    db.cache_invalidate("clinic_row")
    before = db.get_clinic()["logo_data"]
    assert before

    resp = _save_settings(auth_client, files={
        "logo": (io.BytesIO(b"%PDF-1.7\nnope"), "logo.png", "image/png")})
    assert resp.status_code == 200
    db.cache_invalidate("clinic_row")
    assert db.get_clinic()["logo_data"] == before, "a rejected upload destroyed the logo"


def test_settings_can_remove_the_logo(auth_client):
    _save_settings(auth_client, files={"logo": (io.BytesIO(_png()), "logo.png", "image/png")})
    import models.database as db
    db.cache_invalidate("clinic_row")
    assert db.get_clinic()["logo_data"]

    _save_settings(auth_client, remove_logo="1")
    db.cache_invalidate("clinic_row")
    assert not db.get_clinic()["logo_data"]


def test_saving_settings_invalidates_the_clinic_cache(auth_client):
    """get_clinic() caches for 5 minutes — a save the owner cannot see is a bug."""
    import models.database as db
    _save_settings(auth_client, name="Cache Check Vet")
    assert db.get_clinic()["name"] == "Cache Check Vet"
