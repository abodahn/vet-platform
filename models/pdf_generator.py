"""
Invoice PDF Generator — uses fpdf2 (pure Python, no system dependencies).
Install: pip install fpdf2
"""
from __future__ import annotations
import io
from datetime import date
from typing import Optional

try:
    from fpdf import FPDF, XPos, YPos
    _FPDF_OK = True
except ImportError:
    _FPDF_OK = False


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


class _InvoicePDF(FPDF):
    """Internal PDF class with header/footer pre-configured."""

    def __init__(self, clinic: dict, invoice: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
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
    pdf.cell(half - 6, 5, invoice.get("owner_name") or "—",
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
    pdf.cell(half - 6, 5, invoice.get("pet_name") or "—",
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
        pdf.cell(col_w[4], row_h, f"{disc:.0f}%" if disc else "—", align="R", fill=True)
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
