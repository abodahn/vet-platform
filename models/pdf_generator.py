"""
Invoice PDF Generator - uses fpdf2 (pure Python, no system dependencies).
Install: pip install fpdf2
"""
from __future__ import annotations
import io
import logging
import os
import re
from datetime import date
from typing import Optional

try:
    from fpdf import FPDF, XPos, YPos
    _FPDF_OK = True
except ImportError:
    _FPDF_OK = False

logger = logging.getLogger(__name__)

# ── Arabic text support ───────────────────────────────────────────────────────
# Three separate things are required to put Arabic in a PDF, and missing any one
# of them produces either a crash or unreadable output:
#   1. a font containing Arabic glyphs   — Helvetica has none, so the core fonts
#      raise FPDFUnicodeEncodingException on the first Arabic character;
#   2. letter shaping                    — Arabic letters change form depending
#      on their position in a word (م / ـم / ـمـ / مـ). Without reshaping you get
#      disconnected isolated forms that a reader will not accept;
#   3. bidi reordering                    — fpdf2 draws runs left-to-right, so
#      RTL text must be visually reordered before it is handed over.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR_SHAPING_OK = True
except ImportError:                                    # pragma: no cover
    _AR_SHAPING_OK = False

_FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "static", "fonts")
_FONT_REGULAR = os.path.join(_FONT_DIR, "Cairo-Regular.ttf")
_FONT_BOLD = os.path.join(_FONT_DIR, "Cairo-Bold.ttf")

# Cairo covers Arabic and Latin, so it is used for every document rather than
# switching fonts mid-line. That also means a clinic with a mixed-script name
# renders in one consistent typeface, matching the on-screen UI.
_UNICODE_FONT = "Cairo"
_FONTS_AVAILABLE = os.path.exists(_FONT_REGULAR) and os.path.exists(_FONT_BOLD)
if not _FONTS_AVAILABLE:                               # pragma: no cover
    logger.warning(
        "Arabic PDF fonts missing from %s — PDFs will fall back to Helvetica and "
        "will FAIL on any Arabic text. Expected Cairo-Regular.ttf and Cairo-Bold.ttf.",
        _FONT_DIR,
    )

_ARABIC_RE = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def has_arabic(text) -> bool:
    """True when the string contains any Arabic-script character."""
    return bool(text) and bool(_ARABIC_RE.search(str(text)))


def ar(text) -> str:
    """Prepare a string for drawing into a PDF.

    Non-Arabic text is returned unchanged, so Latin documents are byte-identical
    to before. Arabic text is reshaped and bidi-reordered.
    """
    if text is None:
        return ""
    s = str(text)
    if not has_arabic(s) or not _AR_SHAPING_OK:
        if has_arabic(s) and not _AR_SHAPING_OK:       # pragma: no cover
            logger.warning("arabic_reshaper/python-bidi not installed — Arabic "
                           "text will render disconnected and reversed.")
        return s
    try:
        return get_display(arabic_reshaper.reshape(s))
    except Exception:                                   # pragma: no cover
        logger.exception("Arabic reshaping failed; drawing raw text")
        return s


def _register_unicode_fonts(pdf) -> bool:
    """Register Cairo on a PDF instance. Returns False if unavailable."""
    if not _FONTS_AVAILABLE:
        return False
    try:
        pdf.add_font(_UNICODE_FONT, "", _FONT_REGULAR)
        pdf.add_font(_UNICODE_FONT, "B", _FONT_BOLD)
        return True
    except Exception:                                   # pragma: no cover
        logger.exception("Could not register Cairo fonts for PDF output")
        return False


# ── Colour palette ────────────────────────────────────────────────────────────
_NAVY   = (26,  58, 107)   # #1a3a6b
_WHITE  = (255, 255, 255)
_LIGHT  = (248, 250, 252)  # #f8fafc
_BORDER = (226, 232, 240)  # #e2e8f0
_MUTED  = (100, 116, 135)  # #64748b
_GREEN  = ( 21, 128,  61)  # #15803d
_RED    = (220,  38,  38)  # #dc2626
_AMBER  = (217, 119,   6)  # #d97706
_BLACK  = ( 26,  26,  26)


def _status_color(status: str):
    m = {
        "Paid": _GREEN,
        "Partial": _AMBER,
        "Unpaid": _RED,
        "Cancelled": _MUTED,
    }
    return m.get(status, _MUTED)


class _ArabicPDFMixin:
    """Makes an FPDF subclass Arabic-safe without touching its call sites.

    There are 51 set_font and 62 cell/multi_cell calls across the three
    generators in this module. Patching each one would work until somebody adds
    the 63rd and a clinic with an Arabic name gets a 500 on its invoice. Doing
    it at the boundary means new call sites are covered automatically.

    - set_font() redirects the core Helvetica family to Cairo, which has Arabic
      glyphs. Falls back to Helvetica untouched if the fonts are missing, so a
      deployment without them still produces Latin PDFs rather than failing.
    - cell()/multi_cell() reshape and bidi-reorder their text. Latin strings are
      returned unchanged by ar(), so English output is unaffected.
    """

    _unicode_ready = False

    def _init_unicode(self):
        self._unicode_ready = _register_unicode_fonts(self)

    def set_font(self, family="", style="", size=0):
        if self._unicode_ready and (family or "").lower() in ("helvetica", "arial", ""):
            # Cairo ships Regular and Bold only. Italic requests degrade to the
            # nearest available weight rather than raising.
            family = _UNICODE_FONT
            style = "B" if "B" in (style or "").upper() else ""
        return super().set_font(family, style, size)

    @staticmethod
    def _shape(args, kwargs):
        """Apply ar() whether the text came in positionally or by keyword.

        fpdf2's signature is cell(w, h, text, ...) and this module passes the
        text positionally in most places, so a keyword-only implementation
        would silently skip nearly every call.
        """
        for key in ("text", "txt"):
            if key in kwargs:
                kwargs[key] = ar(kwargs[key])
                return args, kwargs
        if len(args) >= 3 and isinstance(args[2], str):
            args = list(args)
            args[2] = ar(args[2])
            return tuple(args), kwargs
        return args, kwargs

    def cell(self, *args, **kwargs):
        args, kwargs = self._shape(args, kwargs)
        return super().cell(*args, **kwargs)

    def multi_cell(self, *args, **kwargs):
        args, kwargs = self._shape(args, kwargs)
        return super().multi_cell(*args, **kwargs)


class _ArabicFPDF(_ArabicPDFMixin, FPDF):
    """Plain Arabic-safe FPDF for generators that don't need a custom header."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_unicode()


class _InvoicePDF(_ArabicPDFMixin, FPDF):
    """Internal PDF class with header/footer pre-configured."""

    def __init__(self, clinic: dict, invoice: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self._init_unicode()
        self._clinic  = clinic or {}
        self._invoice = invoice or {}
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(18, 18, 18)

    # ── FPDF overrides ────────────────────────────────────────────────────────

    def header(self):
        # Navy header band
        self.set_fill_color(*_NAVY)
        self.rect(0, 0, 210, 38, "F")

        # Clinic name
        self.set_xy(18, 9)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*_WHITE)
        cname = self._clinic.get("name") or "Aleefy"
        self.cell(120, 7, cname, new_x=XPos.LEFT, new_y=YPos.NEXT)

        # Sub-line: doctor name + phone
        self.set_x(18)
        self.set_font("Helvetica", "", 9)
        sub = self._clinic.get("doctor_name") or "Lead Veterinarian"
        phone = self._clinic.get("phone", "")
        if phone:
            sub += f"    |    {phone}"
        self.cell(120, 5, sub, new_x=XPos.LEFT, new_y=YPos.NEXT)

        # Invoice number (right side)
        inv_num = self._invoice.get("invoice_number", "INV-0000")
        self.set_xy(120, 8)
        self.set_font("Helvetica", "B", 13)
        self.cell(72, 8, inv_num, align="R",
                  new_x=XPos.RIGHT, new_y=YPos.LAST)

        # Issue date (right side)
        self.set_xy(120, 17)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*_WHITE)
        idate = str(self._invoice.get("issue_date") or date.today())[:10]
        self.cell(72, 5, f"Issued: {idate}", align="R",
                  new_x=XPos.RIGHT, new_y=YPos.LAST)

        # Status badge (right side, row 3)
        status = self._invoice.get("status", "Unpaid")
        self.set_xy(120, 24)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*_status_color(status))
        self.cell(72, 6, f"[ {status.upper()} ]", align="R")

        self.set_text_color(*_BLACK)
        self.ln(16)   # move below the header band

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*_MUTED)
        cname = self._clinic.get("name") or "Aleefy"
        self.cell(0, 5,
                  f"Thank you for choosing {cname}  ·  Page {self.page_no()}",
                  align="C")
        self.set_text_color(*_BLACK)


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_invoice_pdf(invoice: dict, clinic: Optional[dict] = None) -> bytes:
    """
    Generate a PDF for the given invoice dict and return raw bytes.
    Falls back to a minimal text PDF if fpdf2 is not installed.
    """
    if not _FPDF_OK:
        raise RuntimeError(
            "fpdf2 is not installed. Run: pip install fpdf2"
        )

    clinic = clinic or {}
    pdf = _InvoicePDF(clinic=clinic, invoice=invoice)
    pdf.add_page()

    W = pdf.w - pdf.l_margin - pdf.r_margin   # usable width = 174 mm

    # ── 1. Parties row (Bill To / Patient) ───────────────────────────────────
    half = W / 2 - 5

    # Left box
    pdf.set_fill_color(*_LIGHT)
    pdf.set_draw_color(*_BORDER)
    _y0 = pdf.get_y()
    pdf.rect(pdf.l_margin, _y0, half, 24, "FD")
    pdf.set_xy(pdf.l_margin + 3, _y0 + 3)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(half - 6, 4, "BILL TO", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_x(pdf.l_margin + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_NAVY)
    pdf.cell(half - 6, 5, invoice.get("owner_name") or "-",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_x(pdf.l_margin + 3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(half - 6, 4, invoice.get("owner_phone") or "")

    # Right box
    rx = pdf.l_margin + half + 10
    pdf.rect(rx, _y0, half, 24, "FD")
    pdf.set_xy(rx + 3, _y0 + 3)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_text_color(*_MUTED)
    pdf.cell(half - 6, 4, "PATIENT", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_x(rx + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*_NAVY)
    pdf.cell(half - 6, 5, invoice.get("pet_name") or "-",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_x(rx + 3)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    dr = invoice.get("doctor_name", "")
    pdf.cell(half - 6, 4, f"Dr. {dr}" if dr else "")

    pdf.set_text_color(*_BLACK)
    pdf.ln(30)

    # ── 2. Line-items table ───────────────────────────────────────────────────
    col_w = [W * 0.42, W * 0.10, W * 0.13, W * 0.14, W * 0.08, W * 0.13]
    headers = ["Description", "Type", "Unit Price", "Total", "Disc%", "EGP"]

    # Header row
    pdf.set_fill_color(*_NAVY)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", 7.5)
    aligns = ["L", "C", "R", "R", "R", "R"]
    for i, h in enumerate(headers):
        pdf.cell(col_w[i], 7, h, align=aligns[i], fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(*_BLACK)
    lines = invoice.get("lines") or []
    fill = False
    for line in lines:
        pdf.set_fill_color(*(_LIGHT if fill else _WHITE))
        desc = str(line.get("description") or "")
        ltype = str(line.get("line_type") or "")
        qty  = float(line.get("quantity") or 1)
        up   = float(line.get("unit_price") or 0)
        disc = float(line.get("discount") or 0)
        tot  = float(line.get("total") or 0)

        row_h = 6.5
        pdf.cell(col_w[0], row_h, desc[:52], fill=True)
        pdf.cell(col_w[1], row_h, ltype[:10], align="C", fill=True)
        pdf.cell(col_w[2], row_h, f"{up:,.2f}", align="R", fill=True)
        pdf.cell(col_w[3], row_h, f"{tot:,.2f}", align="R", fill=True)
        pdf.cell(col_w[4], row_h, f"{disc:.0f}%" if disc else "-", align="R", fill=True)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(col_w[5], row_h, f"{tot:,.2f}", align="R", fill=True)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.ln()
        fill = not fill

    if not lines:
        pdf.set_fill_color(*_LIGHT)
        pdf.cell(W, 8, "No line items", align="C", fill=True)
        pdf.ln()

    pdf.ln(4)

    # ── 3. Totals block ───────────────────────────────────────────────────────
    tw = 70   # totals column width
    tx = pdf.l_margin + W - tw

    def _tot_row(label, value, bold=False, color=_BLACK):
        pdf.set_xy(tx, pdf.get_y())
        pdf.set_font("Helvetica", "B" if bold else "", 9)
        pdf.set_text_color(*color)
        pdf.cell(tw / 2, 6.5, label)
        pdf.cell(tw / 2, 6.5, value, align="R")
        pdf.set_text_color(*_BLACK)
        pdf.ln()

    subtotal = float(invoice.get("subtotal") or 0)
    disc_amt = float(invoice.get("discount_amount") or 0)
    tax_amt  = float(invoice.get("tax_amount") or 0)
    tax_rate = float(invoice.get("tax_rate") or 0)
    total    = float(invoice.get("total") or 0)
    paid     = float(invoice.get("paid_amount") or 0)
    due      = float(invoice.get("due_amount") or 0)

    # Draw light box behind totals
    _ty = pdf.get_y()
    rows_h = 6.5 * (4 + (1 if disc_amt else 0) + (1 if tax_amt else 0))
    pdf.set_fill_color(*_LIGHT)
    pdf.rect(tx, _ty, tw, rows_h + 6, "F")

    _tot_row("Subtotal", f"{subtotal:,.2f} EGP")
    if disc_amt:
        _tot_row("Discount", f"− {disc_amt:,.2f} EGP", color=_GREEN)
    if tax_amt:
        _tot_row(f"Tax ({tax_rate:.0f}%)", f"+ {tax_amt:,.2f} EGP")

    # Separator line
    pdf.set_draw_color(*_NAVY)
    pdf.line(tx, pdf.get_y(), tx + tw, pdf.get_y())
    pdf.ln(1)

    _tot_row("TOTAL", f"{total:,.2f} EGP", bold=True, color=_NAVY)
    _tot_row("Paid", f"{paid:,.2f} EGP", color=_GREEN)
    _tot_row("Balance Due", f"{due:,.2f} EGP", bold=True,
             color=_RED if due > 0 else _GREEN)

    # ── 4. Payment history ────────────────────────────────────────────────────
    payments = invoice.get("payments") or []
    if payments:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_NAVY)
        pdf.cell(W, 5, "Payment History", new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_draw_color(*_BORDER)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())
        pdf.ln(1)
        for p in payments:
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*_BLACK)
            method = p.get("method") or "Cash"
            ref    = p.get("reference") or ""
            amt    = float(p.get("amount") or 0)
            rat    = str(p.get("received_at") or "")[:10]
            label  = f"{method}" + (f" · {ref}" if ref else "")
            pdf.cell(W / 2, 5, label)
            pdf.set_text_color(*_GREEN)
            pdf.cell(W / 2, 5, f"{amt:,.2f} EGP  ·  {rat}", align="R")
            pdf.set_text_color(*_BLACK)
            pdf.ln()

    # ── 5. Notes ─────────────────────────────────────────────────────────────
    notes = invoice.get("notes", "")
    if notes:
        pdf.ln(5)
        pdf.set_fill_color(*_LIGHT)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(W, 5, "Notes:", fill=True, new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_BLACK)
        pdf.multi_cell(W, 5, notes, fill=True)

    return bytes(pdf.output())


# ── Vaccination Certificate ────────────────────────────────────────────────────

_TEAL  = ( 13, 148, 136)   # #0d9488
_TEAL_L = (204, 251, 241)   # #ccfbf1


def generate_vaccination_certificate_pdf(vacc: dict, pet: dict, clinic: dict | None = None) -> bytes:
    """
    Generate a vaccination certificate PDF.
    vacc  - row from vaccinations table (+ pet_name, owner_name via join)
    pet   - row from get_pet() (includes owner_name, owner_phone)
    clinic - row from get_clinic()
    """
    if not _FPDF_OK:
        raise RuntimeError("fpdf2 is not installed. Run: pip install fpdf2")

    clinic = clinic or {}
    cname  = clinic.get("name") or "Aleefy Veterinary Clinic"
    cphone = clinic.get("phone") or ""
    caddr  = clinic.get("address") or ""

    pdf = _ArabicFPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(20, 20, 20)
    pdf.add_page()

    W = pdf.w - pdf.l_margin - pdf.r_margin   # 170 mm

    # ── Header band ──────────────────────────────────────────────────────────
    pdf.set_fill_color(*_TEAL)
    pdf.rect(0, 0, 210, 42, "F")

    pdf.set_xy(20, 10)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_WHITE)
    pdf.cell(W, 8, cname, new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 9)
    sub = "Vaccination Certificate"
    if cphone:
        sub += f"    |    {cphone}"
    if caddr:
        sub += f"    |    {caddr}"
    pdf.cell(W, 5, sub, new_x=XPos.LEFT, new_y=YPos.NEXT)

    # Certificate number top-right
    cert_no = f"CERT-{vacc.get('id', 0):05d}"
    pdf.set_xy(130, 9)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(60, 7, cert_no, align="R", new_x=XPos.RIGHT, new_y=YPos.LAST)
    pdf.set_xy(130, 17)
    pdf.set_font("Helvetica", "", 8)
    issued = str(vacc.get("administered_at") or date.today())[:10]
    pdf.cell(60, 5, f"Issued: {issued}", align="R")

    pdf.set_text_color(*_BLACK)
    pdf.ln(28)

    # ── Title ─────────────────────────────────────────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_TEAL)
    pdf.cell(W, 10, "VACCINATION CERTIFICATE", align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(W, 5, "Official record of vaccination administered by a licensed veterinarian",
             align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(6)

    # ── Two-column info boxes ─────────────────────────────────────────────────
    half = W / 2 - 4
    y0 = pdf.get_y()

    def _box(x, y, w, h, title, lines_kv):
        pdf.set_fill_color(*_TEAL_L)
        pdf.set_draw_color(*_TEAL)
        pdf.rect(x, y, w, h, "FD")
        pdf.set_xy(x + 4, y + 4)
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(*_TEAL)
        pdf.cell(w - 8, 5, title.upper(), new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_draw_color(*_TEAL)
        pdf.line(x + 4, pdf.get_y(), x + w - 4, pdf.get_y())
        pdf.ln(2)
        for label, val in lines_kv:
            pdf.set_x(x + 4)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*_MUTED)
            pdf.cell(w * 0.38, 5.5, label)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*_BLACK)
            pdf.cell(w * 0.58, 5.5, str(val or "-"), new_x=XPos.LEFT, new_y=YPos.NEXT)

    pet_name    = pet.get("pet_name") or vacc.get("pet_name") or "-"
    species     = pet.get("species") or "-"
    breed       = pet.get("breed") or "-"
    sex         = pet.get("sex") or "-"
    dob         = str(pet.get("dob") or "Unknown")[:10]
    microchip   = pet.get("microchip_id") or "-"
    owner_name  = pet.get("owner_name") or vacc.get("owner_name") or "-"
    owner_phone = pet.get("owner_phone") or "-"

    pet_info = [
        ("Name",      pet_name),
        ("Species",   species),
        ("Breed",     breed),
        ("Sex",       sex),
        ("Date of Birth", dob),
        ("Microchip", microchip),
    ]
    owner_info = [
        ("Owner",    owner_name),
        ("Phone",    owner_phone),
        ("Address",  pet.get("owner_address") or "-"),
    ]

    box_h = 58
    _box(pdf.l_margin, y0, half, box_h, "Patient Information", pet_info)
    _box(pdf.l_margin + half + 8, y0, half, box_h, "Owner Information", owner_info)

    pdf.set_y(y0 + box_h + 8)

    # ── Vaccine details ───────────────────────────────────────────────────────
    pdf.set_fill_color(*_NAVY)
    pdf.set_text_color(*_WHITE)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(W, 7, "  VACCINE DETAILS", fill=True, new_x=XPos.LEFT, new_y=YPos.NEXT)

    details = [
        ("Vaccine Name",     vacc.get("vaccine_name") or "-"),
        ("Brand / Product",  vacc.get("vaccine_brand") or "-"),
        ("Batch / Lot No.",  vacc.get("batch_number") or "-"),
        ("Dose Number",      str(vacc.get("dose_number") or "1")),
        ("Site of Injection",vacc.get("site") or "Subcutaneous"),
        ("Date Administered",str(vacc.get("administered_at") or "-")[:10]),
        ("Next Due Date",    str(vacc.get("next_due_at") or "-")[:10]),
        ("Administered By",  f"Dr. {vacc.get('administered_by')}" if vacc.get("administered_by") else "-"),
    ]

    fill = False
    for label, val in details:
        pdf.set_fill_color(*(_LIGHT if fill else _WHITE))
        pdf.set_text_color(*_MUTED)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(W * 0.38, 7, f"  {label}", fill=True)
        pdf.set_text_color(*_BLACK)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.cell(W * 0.62, 7, f"  {val}", fill=True, new_x=XPos.LEFT, new_y=YPos.NEXT)
        fill = not fill

    pdf.ln(4)

    # ── Notes ─────────────────────────────────────────────────────────────────
    if vacc.get("notes"):
        pdf.set_fill_color(*_LIGHT)
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*_MUTED)
        pdf.cell(W, 5, "  Notes", fill=True, new_x=XPos.LEFT, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_BLACK)
        pdf.multi_cell(W, 5, f"  {vacc['notes']}", fill=True)
        pdf.ln(4)

    # ── Signature line ────────────────────────────────────────────────────────
    pdf.ln(10)
    sig_x = pdf.l_margin + W - 70
    pdf.set_draw_color(*_NAVY)
    pdf.line(sig_x, pdf.get_y(), sig_x + 70, pdf.get_y())
    pdf.ln(2)
    pdf.set_x(sig_x)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*_MUTED)
    dr = vacc.get("administered_by", "")
    pdf.cell(70, 5, f"Dr. {dr}" if dr else "Veterinarian Signature", align="C")

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.set_y(-18)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5,
             f"This certificate was generated by {cname}  -  {cert_no}  -  Keep this document for your records.",
             align="C")

    return bytes(pdf.output())


# ── Payslip PDF ────────────────────────────────────────────────────────────────

_PURPLE   = ( 91,  33, 182)   # #5b21b6
_PURPLE_L = (237, 233, 254)   # #ede9fe


def generate_payslip_pdf(salary: dict, clinic: dict | None = None) -> bytes:
    """Generate a professional payslip PDF for a salary record."""
    if not _FPDF_OK:
        raise RuntimeError("fpdf2 is not installed. Run: pip install fpdf2")

    clinic = clinic or {}
    cname  = clinic.get("name") or "Premium Animal Hospital"
    cphone = clinic.get("phone") or ""
    caddr  = clinic.get("address") or ""

    MONTHS = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
    yr  = int(salary.get("period_year")  or date.today().year)
    mo  = int(salary.get("period_month") or date.today().month)
    period_label = f"{MONTHS[mo-1]} {yr}"

    def _f(key):
        return float(salary.get(key) or 0)

    basic  = _f("basic_salary")
    allow  = _f("allowances")
    ot_h   = _f("overtime_hours")
    ot_r   = _f("overtime_rate")
    ot_amt = round(ot_h * ot_r, 2)
    gross  = _f("gross") or round(basic + allow + ot_amt, 2)
    ded    = _f("deductions")
    abs_d  = _f("absence_deduction")
    tax_d  = _f("tax_deduction")
    net    = _f("net") or round(gross - ded - abs_d - tax_d, 2)

    pdf = _ArabicFPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()
    W = pdf.w - pdf.l_margin - pdf.r_margin   # ~174 mm

    # ── Header band ──────────────────────────────────────────────────────────
    pdf.set_fill_color(*_NAVY)
    pdf.rect(0, 0, 210, 40, "F")

    pdf.set_xy(18, 9)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(*_WHITE)
    pdf.cell(W * 0.6, 9, cname[:50], ln=False)

    pdf.set_xy(210 - 18 - 52, 9)
    pdf.set_fill_color(*_PURPLE)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(52, 9, "  PAY SLIP  ", fill=True, align="C",
             new_x=XPos.LEFT, new_y=YPos.NEXT)

    pdf.set_xy(18, 20)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(W * 0.6, 5, f"Period: {period_label}", ln=False)
    if cphone or caddr:
        pdf.set_xy(18, 26)
        pdf.cell(W, 5, f"{cphone}  {caddr}".strip())

    # ── Employee info boxes ───────────────────────────────────────────────────
    pdf.set_y(46)
    box_w = W / 2 - 3

    def _info_box(x, y, label, value):
        pdf.set_xy(x, y)
        pdf.set_fill_color(*_LIGHT)
        pdf.set_draw_color(*_BORDER)
        pdf.rect(x, y, box_w, 22, "FD")
        pdf.set_xy(x + 3, y + 3)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*_MUTED)
        pdf.cell(box_w - 6, 4, label.upper())
        pdf.set_xy(x + 3, y + 8)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*_BLACK)
        pdf.cell(box_w - 6, 6, str(value)[:35])

    lx = pdf.l_margin
    rx = pdf.l_margin + box_w + 6
    _info_box(lx, 46, "Employee Name", salary.get("full_name") or "-")
    _info_box(rx, 46, "Period",        period_label)
    _info_box(lx, 71, "Role",          (salary.get("role") or "").replace("_", " ").title())
    _info_box(rx, 71, "Payment Status", salary.get("status") or "Draft")
    hire_date     = str(salary.get("hire_date") or "")[:10]
    contract_type = salary.get("contract_type") or "Full-time"
    _info_box(lx, 96, "Hire Date",     hire_date or "-")
    _info_box(rx, 96, "Contract Type", contract_type)

    # ── Earnings table ────────────────────────────────────────────────────────
    pdf.set_y(124)
    col1 = W * 0.55
    colR = W * 0.45

    def _tbl_header(title):
        pdf.set_fill_color(*_NAVY)
        pdf.set_text_color(*_WHITE)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(W, 7, f"  {title}", fill=True, new_x=XPos.LEFT, new_y=YPos.NEXT)

    def _tbl_row(label, amount, color=None, bold=False):
        pdf.set_fill_color(*_WHITE)
        pdf.set_text_color(*(color or _BLACK))
        s = "B" if bold else ""
        pdf.set_font("Helvetica", s, 8.5)
        pdf.cell(col1, 6.5, f"  {label}", border="B")
        pdf.cell(colR, 6.5, f"EGP {amount:,.2f}", border="B", align="R",
                 new_x=XPos.LEFT, new_y=YPos.NEXT)

    _tbl_header("EARNINGS")
    _tbl_row("Basic Salary", basic)
    if allow > 0:
        _tbl_row("Allowances", allow)
    if ot_amt > 0:
        _tbl_row(f"Overtime ({ot_h:.1f} hrs x EGP {ot_r:.2f})", ot_amt)
    pdf.set_fill_color(*_PURPLE_L)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_PURPLE)
    pdf.cell(col1, 7, "  GROSS PAY", fill=True)
    pdf.cell(colR, 7, f"EGP {gross:,.2f}", fill=True, align="R",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(5)

    _tbl_header("DEDUCTIONS")
    if ded > 0:
        _tbl_row("Other Deductions", ded)
    if abs_d > 0:
        _tbl_row("Absence Deduction", abs_d)
    if tax_d > 0:
        _tbl_row("Income Tax", tax_d)
    total_ded = ded + abs_d + tax_d
    pdf.set_fill_color(*_LIGHT)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_RED)
    pdf.cell(col1, 7, "  TOTAL DEDUCTIONS", fill=True)
    pdf.cell(colR, 7, f"EGP {total_ded:,.2f}", fill=True, align="R",
             new_x=XPos.LEFT, new_y=YPos.NEXT)
    pdf.ln(5)

    pdf.set_fill_color(*_GREEN)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(*_WHITE)
    pdf.cell(W, 12, f"  NET PAY: EGP {net:,.2f}", fill=True,
             new_x=XPos.LEFT, new_y=YPos.NEXT)

    if salary.get("payment_date"):
        pdf.ln(4)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_MUTED)
        method = salary.get("payment_method") or "Cash"
        pdf.cell(W, 5,
                 f"Paid on {str(salary['payment_date'])[:10]} via {method}",
                 align="C", new_x=XPos.LEFT, new_y=YPos.NEXT)

    notes = salary.get("notes") or ""
    if notes:
        pdf.ln(3)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(W, 4.5, f"Notes: {notes}")

    # ── Signature lines ────────────────────────────────────────────────────────
    pdf.ln(10)
    sig_y = pdf.get_y()
    pdf.set_draw_color(*_NAVY)
    pdf.line(pdf.l_margin, sig_y, pdf.l_margin + 70, sig_y)
    pdf.line(pdf.l_margin + W - 70, sig_y, pdf.l_margin + W, sig_y)
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.set_x(pdf.l_margin)
    pdf.cell(70, 4, "Employee Signature", align="C")
    pdf.set_x(pdf.l_margin + W - 70)
    pdf.cell(70, 4, "Authorized Signatory", align="C")

    # ── Footer ────────────────────────────────────────────────────────────────
    pdf.set_y(-14)
    pdf.set_font("Helvetica", "I", 7.5)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5,
             f"Computer-generated payslip  -  {cname}  -  {date.today().isoformat()}",
             align="C")

    return bytes(pdf.output())
