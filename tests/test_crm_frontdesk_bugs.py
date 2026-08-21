# -*- coding: utf-8 -*-
"""CRM front-desk bugs: what the clinic types, and what it hands the customer.

Three of these are about data or paper leaving the building wrong — insurance
details dropped on the floor, another company's name on a medical record, an
AI button that dies before it can say why. Phone numbers here start 01777504
so they cannot collide with any other module's fixtures.
"""
import unicodedata
from io import BytesIO

import pytest

import models.database as db
from conftest import get_csrf


# ─── helpers ──────────────────────────────────────────────────────────────────

def _post(client, url, data):
    payload = dict(data)
    payload["_csrf_token"] = get_csrf(client)
    return client.post(url, data=payload, follow_redirects=True)


def _row(sql, params=()):
    conn = db.get_db()
    try:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _mk_owner(full_name, phone, **extra):
    cols = ["full_name", "phone"] + list(extra)
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                f"INSERT INTO owners({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                [full_name, phone] + list(extra.values()))
            return cur.lastrowid
    finally:
        conn.close()


def _pdf_text(data: bytes) -> str:
    """Every character drawn into the PDF, as Unicode."""
    from pypdf import PdfReader
    return unicodedata.normalize("NFKC", "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages))


# ═══ bug-504 — insurance dropped on create ════════════════════════════════════

def test_new_pet_form_saves_the_insurance_details(app, auth_client):
    """db.create_pet() INSERTs no insurance columns, so the New Pet form used to
    accept the policy and throw it away — the clinic only found out when it had
    to claim."""
    with app.app_context():
        oid = _mk_owner("Insurance Owner", "01777504001")
        _post(auth_client, "/crm/pets/new", {
            "owner_id": oid,
            "pet_name": "Policywoof",
            "species": "Dog",
            "insurance_provider": "PetCare Egypt",
            "policy_number": "PCE-77-1234",
            "policy_expiry": "2027-01-31",
            "diet_notes": "Grain free",
        })
        pet = _row("SELECT * FROM pets WHERE owner_id=?", (oid,))

    assert pet is not None, "the pet was not created at all"
    assert pet["insurance_provider"] == "PetCare Egypt"
    assert pet["policy_number"] == "PCE-77-1234"
    assert pet["policy_expiry"] == "2027-01-31"
    assert pet["diet_notes"] == "Grain free"


# ═══ bug-501 — the clinic's own name on its own paperwork ═════════════════════

def test_history_pdf_is_headed_with_the_clinics_own_name(app, auth_client):
    """This sheet is handed to a customer. It must not carry a name the clinic
    never chose — `clinic_name` is not a column, so the literal fallback
    "Animal Hospital" printed on every one of them."""
    with app.app_context():
        before = db.get_clinic().get("name")
        db.update_clinic({"name": "Nile Veterinary Centre"})
        try:
            oid = _mk_owner("Pdf Header Owner", "01777504002")
            pid = _post(auth_client, "/crm/pets/new",
                        {"owner_id": oid, "pet_name": "Headerdog", "species": "Dog"})
            pet = _row("SELECT id FROM pets WHERE owner_id=?", (oid,))
            resp = auth_client.get(f"/crm/pets/{pet['id']}/history.pdf")
            assert resp.status_code == 200
            text = _pdf_text(resp.data)
        finally:
            db.update_clinic({"name": before or "Aleefy"})

    assert "Nile Veterinary Centre" in text
    assert "Animal Hospital" not in text


# ═══ bug-502 — the AI Summary button ══════════════════════════════════════════

def test_pet_page_actually_contains_the_ai_summary_modal(app, auth_client):
    """The button calls openPetSummary(), which reads #petSummaryModal. The
    markup sat between two blocks in a child template, where Jinja discards it,
    so the element never existed and the click threw on null — no error, no
    modal, no way for the page to say the AI is not configured."""
    with app.app_context():
        oid = _mk_owner("Ai Modal Owner", "01777504003")
        _post(auth_client, "/crm/pets/new",
              {"owner_id": oid, "pet_name": "Summarycat", "species": "Cat"})
        pet = _row("SELECT id FROM pets WHERE owner_id=?", (oid,))

    body = auth_client.get(f"/crm/pets/{pet['id']}").get_data(as_text=True)
    assert 'onclick="openPetSummary(' in body, "the button itself is gone"
    assert 'id="petSummaryModal"' in body
    assert 'id="petSummaryContent"' in body


def test_unconfigured_ai_says_so_instead_of_going_quiet(app, auth_client, monkeypatch):
    """With no AI backend, /ai/pet-summary must still answer with words the
    modal can print."""
    import blueprints.ai_assistant.routes as ai

    monkeypatch.setattr(ai, "ai_configured", lambda: False)
    monkeypatch.setattr(ai, "_client", lambda: (_ for _ in ()).throw(RuntimeError("no key")))

    with app.app_context():
        oid = _mk_owner("Ai Off Owner", "01777504004")
        _post(auth_client, "/crm/pets/new",
              {"owner_id": oid, "pet_name": "Quietdog", "species": "Dog"})
        pet = _row("SELECT id FROM pets WHERE owner_id=?", (oid,))

    resp = auth_client.post(f"/ai/pet-summary/{pet['id']}",
                            headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert resp.status_code == 200
    summary = resp.get_json().get("summary") or ""
    assert "not enabled" in summary.lower(), summary


# ═══ bug-503 — header count vs rows shown ═════════════════════════════════════

@pytest.mark.xfail(
    strict=True,
    reason="fix belongs in models/database.py count_owners (not owned by this "
           "agent): its WHERE omits whatsapp_phone, which list_owners searches. "
           "Add ` OR whatsapp_phone LIKE ?` and a fourth q. Remove this marker "
           "when that lands.",
)
def test_owner_search_count_matches_the_rows_it_returns(app):
    """Searching a WhatsApp-only number lists the client but heads the page
    "0 registered clients"."""
    with app.app_context():
        _mk_owner("Whatsapp Only Owner", "01777504005",
                  whatsapp_phone="01777504905")
        rows = db.list_owners(search="01777504905")
        total = db.count_owners(search="01777504905")

    assert len(rows) == 1, "list_owners no longer matches whatsapp_phone"
    assert total == len(rows)
