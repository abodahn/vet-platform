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

def test_duplicate_phone_creates_a_second_owner_and_both_survive(app, auth_client):
    """Phone is the only reliable key in this domain and the routes do not
    enforce it. That is tolerable — families share a number — but only if the
    second create never overwrites the first, and both are findable."""
    phone = "01000000806"
    with app.app_context():
        _post(auth_client, "/crm/owners/new",
              {"full_name": "أول عميل", "phone": phone, "notes": "the original"})
        _post(auth_client, "/crm/owners/new",
              {"full_name": "ثاني عميل", "phone": phone, "notes": "the duplicate"})
        both = _rows("SELECT * FROM owners WHERE phone=? ORDER BY id", (phone,))

    assert len(both) == 2, "expected two rows for a re-used phone number"
    assert both[0]["full_name"] == "أول عميل"
    assert both[0]["notes"] == "the original", \
        "the second create overwrote the first owner's record"
    assert both[1]["full_name"] == "ثاني عميل"

    # and the desk can actually see the collision
    with app.app_context():
        hits = db.list_owners(search=phone)
    assert len([h for h in hits if h["phone"] == phone]) == 2, \
        "searching the shared phone number does not surface both owners"


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

_PDF_ESCAPES = {0x6E: 10, 0x72: 13, 0x74: 9, 0x62: 8, 0x66: 12}   # n r t b f


def _pdf_unescape(lit: bytes) -> bytes:
    """Undo PDF string escaping inside a `( ... )` literal.

    Glyph ids are 2-byte big-endian, so a glyph whose low byte happens to be
    0x0D arrives as the two characters `\\r` and a naive "drop the backslash"
    turns it into 0x72 — silently decoding to the wrong letter. That is how the
    letter `د` (glyph 0x000D here) went missing from this decoder's output.
    """
    out = bytearray()
    i = 0
    while i < len(lit):
        if lit[i] != 0x5C:                       # not a backslash
            out.append(lit[i])
            i += 1
            continue
        i += 1
        if i >= len(lit):
            break
        if 0x30 <= lit[i] <= 0x37:               # \ooo octal, up to 3 digits
            j = 0
            while j < 3 and i + j < len(lit) and 0x30 <= lit[i + j] <= 0x37:
                j += 1
            out.append(int(lit[i:i + j], 8) & 0xFF)
            i += j
        elif lit[i] == 0x0A:                     # line continuation
            i += 1
        else:
            out.append(_PDF_ESCAPES.get(lit[i], lit[i]))
            i += 1
    return bytes(out)


def _pdf_variants(data: bytes) -> list:
    """The text drawn into a PDF, decoded back to Unicode — one string per font.

    Nothing in this repo can parse a PDF, and `b"Limping" in data` is always
    False: fpdf2 deflates every page stream and writes embedded-font text as
    2-byte glyph ids. zlib plus the document's own /ToUnicode CMaps is enough to
    read it back, which is what makes it possible to assert that a report
    contains a diagnosis rather than only that it is 4 KB of something.

    Regular and Bold are separate subsets with separate glyph numbering, and the
    page stream switches between them mid-page, so no single map decodes the
    whole page. Decoding once per map and letting the caller ask "does any one
    variant contain all of these" is the cheap correct answer — text drawn in
    one weight always lands in one variant together.
    """
    import re
    import zlib

    # No `\r?\n` required before `endstream`. fpdf2 does not always write one --
    # whether it does depends on the compressed byte length, which changes with
    # the DATA on the page. So this decoder silently returned "" for some pet
    # names and not others, and the test read as "Arabic letters are being
    # dropped from medical records" when the PDF was correct all along.
    # A decoder that fails by returning nothing makes every assertion built on
    # it either vacuous or alarming, and there is no way to tell which.
    streams = []
    for raw in re.findall(rb"stream\r?\n(.*?)endstream", data, re.S):
        raw = raw.rstrip(b"\r\n")
        try:
            streams.append(zlib.decompress(raw))
        except Exception:
            streams.append(raw)

    # /ToUnicode: `<glyph-id> <utf-16be codepoint(s)>`
    maps = []
    for s in streams:
        pairs = re.findall(rb"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{4,})>", s)
        if pairs:
            maps.append({int(g, 16): "".join(
                chr(int(u[i:i + 4], 16)) for i in range(0, len(u), 4))
                for g, u in pairs})

    # Both text operators. `Tj` draws one string; `TJ` draws an array of strings
    # with kerning numbers between them, and fpdf2 emits either depending on the
    # run. Reading only Tj means a page drawn as TJ decodes to nothing.
    literals = []
    for s in streams:
        for lit in re.findall(rb"\((.*?)\)\s*Tj", s, re.S):
            literals.append(_pdf_unescape(lit))
        for arr in re.findall(rb"\[(.*?)\]\s*TJ", s, re.S):
            joined = b"".join(re.findall(rb"\((.*?)\)", arr, re.S))
            if joined:
                literals.append(_pdf_unescape(joined))

    return ["\n".join(
        "".join(gid.get(int.from_bytes(lit[i:i + 2], "big"), "�")
                for i in range(0, len(lit) - 1, 2))
        for lit in literals) for gid in maps]


def _pdf_has(data: bytes, *needles) -> bool:
    """True when one single decoding contains every needle."""
    return any(all(n in v for n in needles) for v in _pdf_variants(data))


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

    assert _pdf_has(resp.data, "Patient:", "Pdfdog")
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
    variants = _pdf_variants(resp.data)
    assert any("Patient:" in v for v in variants), \
        "the report did not render its own patient header"

    # every letter, in the same weight as the "Patient:" label it sits next to
    assert _pdf_has(resp.data, "Patient:", *set(AR_NOTDEF_BAIT)), (
        f"a letter of {AR_NOTDEF_BAIT!r} was dropped to notdef — the pet's name "
        f"is wrong on the printed record. Decoded: "
        f"{[v for v in variants if 'Patient:' in v]}")


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


# ═══ auth ═════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("url", [
    "/crm/owners/1/edit",
    "/crm/owners/1/pets-json",
    "/crm/pets/1/edit",
    "/crm/pets/1/history.pdf",
])
def test_crm_routes_require_login(client, url):
    resp = client.get(url)
    assert resp.status_code in (301, 302)
    assert "/auth/login" in resp.headers.get("Location", "")
