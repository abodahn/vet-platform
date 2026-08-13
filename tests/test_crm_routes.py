# -*- coding: utf-8 -*-
"""CRM: owners, pets, and the loyalty ledger.

The product's differentiator is that an Egyptian clinic can run entirely in
Arabic. That only holds if an Arabic name survives the round trip through a web
form byte-for-byte — a name that comes back with a normalised, stripped or
re-encoded character is a name that will never match itself again, and
duplicate detection fails silently rather than loudly.

Every write is read back out of the database. The suite shares one database, so
each fixture creates its own owner and every assertion is scoped to it.
SQLite, no network.
"""
import pytest

import models.database as db


# ─── helpers ──────────────────────────────────────────────────────────────────

def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _row(sql, params=()):
    conn = db.get_db()
    try:
        r = conn.execute(sql, params).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _rows(sql, params=()):
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def _owner_by_phone(phone):
    return _row("SELECT * FROM owners WHERE phone=?", (phone,))


def _mk_owner(full_name, phone, **extra):
    cols = ["full_name", "phone"] + list(extra)
    vals = [full_name, phone] + list(extra.values())
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                f"INSERT INTO owners ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                vals)
            return cur.lastrowid
    finally:
        conn.close()


def _mk_pet(owner_id, pet_name, species="Cat"):
    conn = db.get_db()
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                (owner_id, pet_name, species))
            return cur.lastrowid
    finally:
        conn.close()


def _balance(owner_id):
    return _row("SELECT COALESCE(loyalty_balance,0) b FROM owners WHERE id=?",
                (owner_id,))["b"]


def _ledger(owner_id):
    return _rows("SELECT * FROM loyalty_points WHERE owner_id=? ORDER BY id",
                 (owner_id,))


# Arabic fixtures. RLM/ZWNJ are what Excel exports and RTL-aware browsers inject
# into a text field; they are invisible but they are part of the string.
AR_NAME    = "محمد عبد الرحمن الشاذلي"
AR_ADDRESS = "٣٤ شارع جامعة الدول العربية، المهندسين، الجيزة"
AR_PET     = "مشمشة"
AR_MARKED  = "‏سارة‌ الشناوي‎"     # RLM + ZWNJ + LRM


# ═══ Arabic round-trip ════════════════════════════════════════════════════════

def test_arabic_owner_round_trips_byte_identical(app, auth_client):
    """POST an Arabic owner through the real form, read the row back raw."""
    phone = "01000000801"
    with app.app_context():
        _post(auth_client, "/crm/owners/new", {
            "full_name": AR_NAME,
            "full_name_ar": AR_NAME,
            "phone": phone,
            "whatsapp_phone": phone,
            "email": "ar@example.com",
            "address": AR_ADDRESS,
            "address_ar": AR_ADDRESS,
            "preferred_contact": "WhatsApp",
            "notes": "ملاحظات",
        })
        o = _owner_by_phone(phone)

    assert o is not None, "the owner form rendered but wrote nothing"
    assert o["full_name"] == AR_NAME
    assert o["full_name"].encode("utf-8") == AR_NAME.encode("utf-8")
    assert o["full_name_ar"].encode("utf-8") == AR_NAME.encode("utf-8")
    assert o["address"].encode("utf-8") == AR_ADDRESS.encode("utf-8")
    assert o["address_ar"].encode("utf-8") == AR_ADDRESS.encode("utf-8")
    assert o["notes"] == "ملاحظات"


def test_arabic_name_with_invisible_marks_is_not_silently_rewritten(app, auth_client):
    """Bidi and zero-width marks must survive untouched.

    Not cosmetic: a form that strips or normalises them stores a name the
    receptionist can no longer find, and two records that look identical on
    screen stop comparing equal.
    """
    phone = "01000000802"
    with app.app_context():
        _post(auth_client, "/crm/owners/new",
              {"full_name": AR_MARKED, "phone": phone})
        o = _owner_by_phone(phone)

    assert o is not None
    assert o["full_name"].encode("utf-8") == AR_MARKED.encode("utf-8")
    assert "‏" in o["full_name"] and "‌" in o["full_name"]
    assert len(o["full_name"]) == len(AR_MARKED)


def test_arabic_pet_name_round_trips_through_form_and_json(app, auth_client):
    phone = "01000000803"
    with app.app_context():
        oid = _mk_owner("Arabic Pet Owner", phone)
        _post(auth_client, f"/crm/pets/new?owner_id={oid}", {
            "owner_id": str(oid),
            "pet_name": AR_PET,
            "species": "Cat",
            "breed": "شيرازي",
            "sex": "Female",
            "microchip_id": "CHIP-AR-803",
            "diet_notes": "طعام جاف مرتين يومياً",
        })
        p = _row("SELECT * FROM pets WHERE microchip_id=?", ("CHIP-AR-803",))

    assert p is not None, "the pet form rendered but wrote nothing"
    assert p["pet_name"].encode("utf-8") == AR_PET.encode("utf-8")
    assert p["breed"] == "شيرازي"
    assert p["diet_notes"] == "طعام جاف مرتين يومياً"

    payload = auth_client.get(f"/crm/owners/{oid}/pets-json").get_json()
    names = [x["pet_name"] for x in payload["pets"]]
    assert AR_PET in names
    assert names[names.index(AR_PET)].encode("utf-8") == AR_PET.encode("utf-8")


def test_arabic_survives_the_edit_route_too(app, auth_client):
    """Editing is where a round trip usually breaks — the value goes out to a
    template and comes back in again."""
    phone = "01000000804"
    with app.app_context():
        oid = _mk_owner("Latin Name To Replace", phone)
        _post(auth_client, f"/crm/owners/{oid}/edit", {
            "full_name": AR_NAME,
            "full_name_ar": AR_NAME,
            "phone": phone,
            "address": AR_ADDRESS,
            "address_ar": AR_ADDRESS,
            "preferred_contact": "Phone",
        })
        o = _row("SELECT * FROM owners WHERE id=?", (oid,))

    assert o["full_name"].encode("utf-8") == AR_NAME.encode("utf-8")
    assert o["full_name_ar"].encode("utf-8") == AR_NAME.encode("utf-8")
    assert o["address_ar"].encode("utf-8") == AR_ADDRESS.encode("utf-8")
    assert o["preferred_contact"] == "Phone"


def test_owner_search_finds_the_arabic_name_it_stored(app, auth_client):
    """Storing it byte-identical is only useful if it is findable again."""
    phone = "01000000805"
    with app.app_context():
        _post(auth_client, "/crm/owners/new",
              {"full_name": "هالة منصور", "phone": phone})
        found = db.list_owners(search="هالة منصور")
    assert [o for o in found if o["phone"] == phone], \
        "an Arabic owner cannot be searched for by their own name"


# ═══ duplicate owners ═════════════════════════════════════════════════════════

def test_a_second_client_cannot_take_a_mobile_that_is_already_used(app, auth_client):
    """One mobile, one client — the owner asked for this deliberately.

    This test used to assert the OPPOSITE: that a re-used number quietly made
    a second record, on the reasoning that families share a phone. In practice
    that is how one household's pets ended up split across several records
    nobody could reconcile, so the rule is now uniqueness and a shared
    household is ONE client with several animals.

    The refusal has to be a message, never a 500 — a front desk hits this
    constantly — and it has to name who holds the number so the desk can open
    them instead of inventing a variant spelling.
    """
    phone = "01000000806"
    with app.app_context():
        _post(auth_client, "/crm/owners/new",
              {"full_name": "أول عميل", "phone": phone, "notes": "the original"})
        r = _post(auth_client, "/crm/owners/new",
                  {"full_name": "ثاني عميل", "phone": phone, "notes": "the duplicate"})
        rows = _rows("SELECT * FROM owners WHERE phone=? ORDER BY id", (phone,))

    # 409, not 500 and not 200: the front desk sees a rendered page either way,
    # but a script posting here has to be able to tell a refusal from a success.
    # While this was 200 the New Visit wizard read the refusal as a save and
    # carried on under the other client's name.
    assert r.status_code == 409, "the refusal must be a message a caller can read"
    assert r.status_code < 500, "the refusal must not be a crash"
    assert len(rows) == 1, "a duplicate mobile created a second client"
    assert rows[0]["full_name"] == "أول عميل"
    assert rows[0]["notes"] == "the original", "the first record was overwritten"

    body = r.get_data(as_text=True)
    assert "أول عميل" in body, "the refusal does not say who already has the number"


def test_duplicates_that_already_exist_stay_findable(app, auth_client):
    """The rule applies to new writes. Records already in the database keep
    their numbers — a constraint added over them would fail at startup — so
    both must still surface when somebody searches that number."""
    phone = "01000000899"
    with app.app_context():
        conn = db.get_db()
        for name in ("قديم واحد", "قديم اتنين"):
            conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                         (name, phone))
        conn.commit()
        conn.close()
        hits = db.list_owners(search=phone)

    assert len([h for h in hits if h["phone"] == phone]) == 2,         "searching a shared number does not surface both legacy records"


def test_owner_without_a_name_is_rejected(app, auth_client):
    before = _row("SELECT COUNT(*) n FROM owners")["n"]
    _post(auth_client, "/crm/owners/new", {"full_name": "   ", "phone": "01000000807"})
    assert _owner_by_phone("01000000807") is None
    assert _row("SELECT COUNT(*) n FROM owners")["n"] == before


# ═══ crm.owner_edit ═══════════════════════════════════════════════════════════

def test_owner_edit_form_renders(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Editable Owner", "01000000808")
    resp = auth_client.get(f"/crm/owners/{oid}/edit")
    assert resp.status_code == 200
    assert "Editable Owner" in resp.get_data(as_text=True)


def test_owner_edit_persists_every_field(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Before Edit", "01000000809")
        _post(auth_client, f"/crm/owners/{oid}/edit", {
            "full_name": "After Edit",
            "phone": "01000000810",
            "whatsapp_phone": "01000000811",
            "email": "after@example.com",
            "address": "New Cairo",
            "preferred_contact": "Phone",
            "preferred_doctor": "Dr. Mona",
            "vip_flag": "1",
            "marketing_consent": "1",
            "notes": "upgraded to VIP",
        })
        o = _row("SELECT * FROM owners WHERE id=?", (oid,))

    assert o["full_name"] == "After Edit"
    assert o["phone"] == "01000000810"
    assert o["whatsapp_phone"] == "01000000811"
    assert o["email"] == "after@example.com"
    assert o["preferred_contact"] == "Phone"
    assert o["preferred_doctor"] == "Dr. Mona"
    assert o["vip_flag"] == 1
    assert o["notes"] == "upgraded to VIP"


def test_owner_edit_rejects_blank_name_without_writing(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Keep My Name", "01000000812")
        _post(auth_client, f"/crm/owners/{oid}/edit",
              {"full_name": "", "phone": "01099999999"})
        o = _row("SELECT * FROM owners WHERE id=?", (oid,))
    assert o["full_name"] == "Keep My Name"
    assert o["phone"] == "01000000812", "a rejected edit still changed the phone"


def test_owner_edit_writes_an_audit_entry(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Audited Owner", "01000000813")
        _post(auth_client, f"/crm/owners/{oid}/edit",
              {"full_name": "Audited Owner v2", "phone": "01000000813"})
        entry = _row(
            "SELECT * FROM audit_log WHERE action='update_owner' AND entity_id=?"
            " ORDER BY id DESC", (str(oid),))
    assert entry is not None, "editing an owner left no audit trail"
    assert entry["module"] == "crm"


# ═══ crm.owner_pets_json ══════════════════════════════════════════════════════

def test_owner_pets_json_lists_exactly_that_owners_pets(app, auth_client):
    with app.app_context():
        mine = _mk_owner("JSON Owner", "01000000814")
        other = _mk_owner("Other Owner", "01000000815")
        a = _mk_pet(mine, "Alpha")
        b = _mk_pet(mine, "Beta")
        c = _mk_pet(other, "Gamma")

    payload = auth_client.get(f"/crm/owners/{mine}/pets-json").get_json()
    ids = {p["id"] for p in payload["pets"]}
    assert ids == {a, b}
    assert c not in ids


def test_owner_pets_json_empty_for_owner_without_pets(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Petless", "01000000816")
    assert auth_client.get(f"/crm/owners/{oid}/pets-json").get_json() == {"pets": []}


# ═══ crm.pet_edit ═════════════════════════════════════════════════════════════

def test_pet_edit_form_renders(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Pet Edit Owner", "01000000817")
        pid = _mk_pet(oid, "Rocky", "Dog")
    resp = auth_client.get(f"/crm/pets/{pid}/edit")
    assert resp.status_code == 200
    assert "Rocky" in resp.get_data(as_text=True)


def test_pet_edit_persists_clinical_and_insurance_fields(app, auth_client):
    """The insurance/diet update sits behind a bare `except: pass`, so a silent
    failure there would be invisible without reading the row back."""
    with app.app_context():
        oid = _mk_owner("Insured Owner", "01000000818")
        pid = _mk_pet(oid, "Old Name", "Dog")
        _post(auth_client, f"/crm/pets/{pid}/edit", {
            "pet_name": "بيسكوت",
            "species": "Dog",
            "breed": "Golden Retriever",
            "sex": "Male",
            "dob": "2021-05-04",
            "weight_kg": "27.5",
            "color": "Cream",
            "microchip_id": "CHIP-818",
            "neutered": "1",
            "allergies": "حساسية من الدجاج",
            "chronic_conditions": "Hip dysplasia",
            "diet_notes": "Grain free",
            "insurance_provider": "PetCare Misr",
            "policy_number": "POL-818",
            "policy_expiry": "2027-01-01",
            "notes": "friendly",
        })
        p = _row("SELECT * FROM pets WHERE id=?", (pid,))

    assert p["pet_name"].encode("utf-8") == "بيسكوت".encode("utf-8")
    assert p["breed"] == "Golden Retriever"
    assert p["dob"] == "2021-05-04"
    assert float(p["weight_kg"]) == 27.5
    assert p["microchip_id"] == "CHIP-818"
    assert p["neutered"] == 1
    assert p["allergies"] == "حساسية من الدجاج"
    assert p["diet_notes"] == "Grain free"
    assert p["insurance_provider"] == "PetCare Misr"
    assert p["policy_number"] == "POL-818"
    assert p["policy_expiry"] == "2027-01-01"


def test_pet_edit_rejects_blank_name_without_writing(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Blank Pet Owner", "01000000819")
        pid = _mk_pet(oid, "Keeper", "Cat")
        _post(auth_client, f"/crm/pets/{pid}/edit", {"pet_name": "", "species": "Bird"})
        p = _row("SELECT * FROM pets WHERE id=?", (pid,))
    assert p["pet_name"] == "Keeper"
    assert p["species"] == "Cat", "a rejected edit still changed the species"


# ═══ crm.pet_history_pdf ══════════════════════════════════════════════════════

def _pdf_text(data: bytes) -> str:
    """Every character drawn into a PDF, as Unicode.

    This used to be ninety lines of hand-rolled PDF: inflate the page streams,
    scrape /ToUnicode CMaps, undo string escaping, map 2-byte glyph ids back to
    characters. It got the answer wrong in both directions. First it decoded
    every literal with every font's map and asked whether ANY result contained
    the needle -- so the wrong subset's numbering produced plausible garbage
    that happened to contain "Patient:", and the test passed on an artifact.
    Then, when the page data shifted, the same garbage stopped containing it
    and the suite reported "Arabic letters are being dropped from medical
    records" about a PDF that was correct all along.

    A test helper that can raise a false alarm about a medical record is worse
    than no helper. pypdf resolves fonts to their CMaps properly; the whole
    thing is now one line, and it is right.

    NFKC because the shaper writes Arabic as presentation forms (U+FE70..FEFF).
    "did any letter get dropped" is a question about letters, not about which
    contextual form they were drawn in.
    """
    import unicodedata
    from io import BytesIO

    from pypdf import PdfReader

    return unicodedata.normalize("NFKC", "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(data)).pages))


def _pdf_has(data: bytes, *needles) -> bool:
    text = _pdf_text(data)
    return all(n in text for n in needles)


def test_pdf_text_helper_reads_back_what_was_drawn():
    """Guard the guard: a decoder that silently returned "" would make every
    PDF assertion below vacuously true."""
    from models.pdf_generator import _ArabicFPDF
    pdf = _ArabicFPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, "Cranial cruciate rupture", ln=True)
    pdf.cell(0, 8, "دودو", ln=True)
    data = bytes(pdf.output())
    assert _pdf_has(data, "Cranial cruciate rupture")
    assert _pdf_has(data, "د", "و")
    assert not _pdf_has(data, "Cranial cruciate ruptures")
    assert _pdf_text(data).strip(), "the decoder returned nothing at all"


def test_pet_history_pdf_contains_the_medical_record(app, auth_client):
    """A "Medical History Report" that omits the diagnosis is not a record.

    The route reads v["diagnosis"] and v["treatment"], neither of which is a
    column on `visits` — they live in `diagnoses` and `treatment_plans`.
    """
    with app.app_context():
        oid = _mk_owner("Pdf Owner", "01000000820")
        pid = _mk_pet(oid, "Pdfdog", "Dog")
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO visits (owner_id, pet_id, visit_date, visit_type,"
                " chief_complaint, weight_kg, doctor_name) VALUES (?,?,?,?,?,?,?)",
                (oid, pid, "2026-05-01", "Consultation", "Limping on hind leg",
                 14.0, "Nabil"))
            vid = cur.lastrowid
            conn.execute(
                "INSERT INTO diagnoses (visit_id, pet_id, diagnosis, severity)"
                " VALUES (?,?,?,?)", (vid, pid, "Cranial cruciate rupture", "Severe"))
            conn.execute(
                "INSERT INTO treatment_plans (visit_id, pet_id, plan_text)"
                " VALUES (?,?,?)",
                (vid, pid, "TPLO surgery then eight weeks crate rest"))
            conn.execute(
                "INSERT INTO vaccinations (pet_id, vaccine_name, administered_at,"
                " next_due_at) VALUES (?,?,?,?)",
                (pid, "Rabies", "2026-05-01", "2027-05-01"))
        conn.close()

    resp = auth_client.get(f"/crm/pets/{pid}/history.pdf")
    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/pdf"
    assert resp.data[:4] == b"%PDF"
    assert "attachment" in resp.headers["Content-Disposition"]

    # The report has no "Patient:" label -- the pet's name is a heading under
    # "Patient Medical History Report". The old assertion only ever passed
    # because a mis-decoded glyph run happened to spell it.
    assert _pdf_has(resp.data, "Patient Medical History Report", "Pdfdog")
    assert _pdf_has(resp.data, "01000000820"), \
        "the owner's phone is missing from the report"
    assert _pdf_has(resp.data, "Rabies"), \
        "vaccination history is missing from the report"
    assert _pdf_has(resp.data, "Limping on hind leg", "Cranial cruciate rupture",
                    "TPLO surgery"), (
        "the medical history report carries no diagnosis and no treatment plan: "
        "the route reads v['diagnosis'] and v['treatment'], and neither is a "
        "column on `visits`")


def test_pet_history_pdf_handles_an_arabic_patient(app, auth_client):
    """An Arabic-only pet is 27 of the 83 animals in the demo clinic. The core
    Helvetica font carries no Arabic glyphs, so a generator that does not switch
    fonts raises FPDFUnicodeEncodingException on the first character — a 500 on
    the medical record of a third of the practice."""
    with app.app_context():
        oid = _mk_owner(AR_NAME, "01000000821")
        pid = _mk_pet(oid, AR_PET, "Cat")
        conn = db.get_db()
        with conn:
            cur = conn.execute(
                "INSERT INTO visits (owner_id, pet_id, visit_date, visit_type,"
                " chief_complaint) VALUES (?,?,?,?,?)",
                (oid, pid, "2026-06-01", "كشف", "قيء متكرر"))
            vid = cur.lastrowid
            conn.execute(
                "INSERT INTO diagnoses (visit_id, pet_id, diagnosis) VALUES (?,?,?)",
                (vid, pid, "التهاب معوي"))
        conn.close()

    resp = auth_client.get(f"/crm/pets/{pid}/history.pdf")
    assert resp.status_code == 200, "Arabic patient history PDF failed to generate"
    assert resp.data[:4] == b"%PDF"


# ا د ذ ر ز و ة never join to the left, so a reshaper emits their *isolated*
# presentation forms — and Cairo is missing 55 codepoints in FE70..FEFF, all of
# them isolated forms. A name built only from connecting letters renders fine
# while that bug is live, which is exactly how it survived. Every letter here is
# non-connecting on purpose.
AR_NOTDEF_BAIT = "دودو"


def test_arabic_letters_that_do_not_join_are_not_dropped_from_the_pdf(app, auth_client):
    """Not "does it render" — does every letter of the name survive.

    Missing glyphs are dropped silently: "عيادة النيل" came out as "ﻋﻴﺎ ﻟﻨﻴﻞ",
    with the alef, dal and teh marbuta simply gone. Still a 200, still a valid
    PDF, still the wrong patient's name on a medical record.
    """
    with app.app_context():
        oid = _mk_owner("رشا عبد الرازق", "01000000831")
        pid = _mk_pet(oid, AR_NOTDEF_BAIT, "Dog")

    resp = auth_client.get(f"/crm/pets/{pid}/history.pdf")
    assert resp.status_code == 200
    text = _pdf_text(resp.data)
    assert "Patient Medical History Report" in text, \
        "the report did not render its own header"

    missing = sorted(set(AR_NOTDEF_BAIT) - set(text))
    assert not missing, (
        f"{missing} dropped to notdef from {AR_NOTDEF_BAIT!r} — the pet's name "
        f"is wrong on the printed record. Extracted: {text[:400]!r}")

    # Not just the letters in isolation: the name must survive as one word, or
    # a reordered "دودو" would pass a per-letter check while printing nonsense.
    assert AR_NOTDEF_BAIT in text, (
        f"every letter of {AR_NOTDEF_BAIT!r} is present but the name is not "
        f"intact. Extracted: {text[:400]!r}")

    # The owner's name is drawn by the same shaper, in a different weight.
    assert "رشا عبد الرازق" in text, "the owner's Arabic name did not survive"


# ═══ loyalty — redeem ═════════════════════════════════════════════════════════

def test_redeem_deducts_points_and_writes_the_ledger(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Loyal Client", "01000000822", loyalty_balance=150)
        _post(auth_client, f"/crm/owners/{oid}/redeem-points", {})
        assert _balance(oid) == 50
        led = _ledger(oid)

    assert len(led) == 1
    assert led[0]["points"] == -100
    assert led[0]["ref_type"] == "redemption"
    assert led[0]["created_by"], "redemption is not attributable to anyone"
    assert "100" in (led[0]["reason"] or "")


def test_redeem_leaves_exactly_zero_never_negative(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Exact Hundred", "01000000823", loyalty_balance=100)
        _post(auth_client, f"/crm/owners/{oid}/redeem-points", {})
        assert _balance(oid) == 0

        # a second attempt on an empty account must not push it below zero
        _post(auth_client, f"/crm/owners/{oid}/redeem-points", {})
        assert _balance(oid) == 0
        assert len(_ledger(oid)) == 1, "a refused redemption still wrote a ledger row"


def test_redeem_refused_below_the_minimum(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Almost There", "01000000824", loyalty_balance=99)
        _post(auth_client, f"/crm/owners/{oid}/redeem-points", {})
        assert _balance(oid) == 99
        assert _ledger(oid) == []


def test_redeem_on_missing_owner_is_not_a_500(auth_client):
    resp = _post(auth_client, "/crm/owners/99999999/redeem-points", {})
    assert resp.status_code == 200


# ═══ loyalty — adjust ═════════════════════════════════════════════════════════

def test_adjust_credits_points_and_records_who_and_why(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Adjusted Client", "01000000825", loyalty_balance=10)
        _post(auth_client, f"/crm/owners/{oid}/adjust-points",
              {"points": "75", "reason": "تعويض عن خطأ في الفاتورة"})
        assert _balance(oid) == 85
        led = _ledger(oid)

    assert len(led) == 1
    assert led[0]["points"] == 75
    assert led[0]["ref_type"] == "manual"
    assert led[0]["reason"] == "تعويض عن خطأ في الفاتورة"
    assert led[0]["created_by"], "a manual points adjustment has no author recorded"
    assert led[0]["created_at"], "a manual points adjustment has no timestamp"


def test_adjust_can_deduct(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Clawback Client", "01000000826", loyalty_balance=200)
        _post(auth_client, f"/crm/owners/{oid}/adjust-points",
              {"points": "-60", "reason": "reversal"})
        assert _balance(oid) == 140
        assert _ledger(oid)[0]["points"] == -60


def test_adjust_defaults_the_reason_rather_than_leaving_it_blank(app, auth_client):
    with app.app_context():
        oid = _mk_owner("No Reason Given", "01000000827", loyalty_balance=0)
        _post(auth_client, f"/crm/owners/{oid}/adjust-points",
              {"points": "5", "reason": "   "})
        assert _ledger(oid)[0]["reason"] == "Manual adjustment"


def test_adjust_of_zero_writes_nothing(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Zero Adjust", "01000000828", loyalty_balance=40)
        _post(auth_client, f"/crm/owners/{oid}/adjust-points",
              {"points": "0", "reason": "noop"})
        assert _balance(oid) == 40
        assert _ledger(oid) == []


def test_adjust_of_garbage_writes_nothing(app, auth_client):
    with app.app_context():
        oid = _mk_owner("Garbage Adjust", "01000000829", loyalty_balance=40)
        _post(auth_client, f"/crm/owners/{oid}/adjust-points",
              {"points": "abc", "reason": "typo"})
        assert _balance(oid) == 40
        assert _ledger(oid) == []


def test_ledger_and_balance_never_diverge(app, auth_client):
    """The invariant that makes the ledger worth keeping: whatever the balance
    says, the ledger must explain it."""
    with app.app_context():
        oid = _mk_owner("Ledger Truth", "01000000830", loyalty_balance=300)
        _post(auth_client, f"/crm/owners/{oid}/adjust-points", {"points": "50"})
        _post(auth_client, f"/crm/owners/{oid}/adjust-points", {"points": "-30"})
        _post(auth_client, f"/crm/owners/{oid}/redeem-points", {})
        _post(auth_client, f"/crm/owners/{oid}/adjust-points", {"points": "0"})

        moved = sum(r["points"] for r in _ledger(oid))
        assert moved == 50 - 30 - 100
        assert _balance(oid) == 300 + moved


def test_adjust_on_missing_owner_is_not_a_500(auth_client):
    resp = _post(auth_client, "/crm/owners/99999999/adjust-points", {"points": "10"})
    assert resp.status_code == 200


# ═══ owner search — what every owner dropdown in the app now runs on ══════════

def _search(client, q):
    payload = client.get("/crm/owners/search-json",
                         query_string={"q": q}).get_json()
    return {o["id"] for o in payload["owners"]}


def test_owner_search_reaches_a_client_that_no_dropdown_would_have_rendered(app,
                                                                           auth_client):
    """Position in the table must not decide who is selectable.

    The dropdowns this replaces rendered `ORDER BY full_name LIMIT 200..500`.
    The owner below is created last and sorts last, so under the old scheme it
    was the first client to disappear; the search has to find it anyway.
    """
    with app.app_context():
        oid = _mk_owner("Zzz Search Target", "01099887766")
    assert oid in _search(auth_client, "Zzz Search Target")


def test_owner_search_matches_phone_and_arabic_names(app, auth_client):
    with app.app_context():
        oid = _mk_owner(AR_NAME + " سيرش", "01234500099")
    assert oid in _search(auth_client, "01234500099"), "phone search found nothing"
    assert oid in _search(auth_client, AR_NAME + " سيرش"), "Arabic name search found nothing"


def test_owner_search_ignores_a_query_too_short_to_narrow_anything(auth_client):
    """One character would return an arbitrary 25 owners and read as 'no match'."""
    assert auth_client.get("/crm/owners/search-json",
                           query_string={"q": "a"}).get_json() == {"owners": []}
    assert auth_client.get("/crm/owners/search-json").get_json() == {"owners": []}


# ═══ auth ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("url", [
    "/crm/owners/1/edit",
    "/crm/owners/1/pets-json",
    "/crm/owners/search-json",
    "/crm/pets/1/edit",
    "/crm/pets/1/history.pdf",
])
def test_crm_routes_require_login(client, url):
    resp = client.get(url)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")
