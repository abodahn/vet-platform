# -*- coding: utf-8 -*-
"""The History tab: the whole household, and what actually happened.

Two problems, one of them silent.

The loud one: five columns — date, symptom, weight, temp, doctor — is not a
history a vet can decide from. It never said what was diagnosed, what was
given, what it cost or whether it was paid, all of which the 360 payload was
already carrying.

The silent one: the tab was filled from `data.history`, which is the CURRENT
PET's visits, inside show(). So on a screen whose entire promise is "this
client and every animal they own", History showed one animal. A client with a
dog and two cats saw a third of their own record and nothing said so.
"""
import io
import re

from conftest import get_csrf

EXAM = "templates/visits/exam.html"


def _src():
    return io.open(EXAM, encoding="utf-8").read()


def _render_history():
    src = _src()
    i = src.index("function renderHistory(")
    return src[i:src.index("\n  // ── tasks", i)]


def test_history_is_drawn_from_the_owner_not_from_one_pet(auth_client, app):
    src = _src()
    assert "renderHistory(d)" in src, "the owner payload never reaches History"
    body = _render_history()
    assert "body.visits" in body, \
        "History still reads a single pet's history rather than the owner's visits"


def test_every_visit_names_its_animal():
    """The column that makes a household history readable at all."""
    body = _render_history()
    assert "v.pet_name" in body, "History does not say which animal each visit was for"


def test_history_shows_what_was_found_given_and_charged():
    body = _render_history()
    for field, why in [
        ("diagnoses", "no diagnosis column"),
        ("vaccines", "vaccines given are not shown"),
        ("meds", "medicines prescribed are not shown"),
        ("invoices", "what the visit cost is not shown"),
    ]:
        assert field in body, why
    assert "inv.status" in body, "whether the visit was paid is not shown"


def test_the_join_is_on_visit_id():
    """pet_id would smear another visit's medicines onto this one."""
    body = _render_history()
    assert body.count("'visit_id'") >= 4, \
        "the per-visit detail is not keyed on visit_id"


def test_the_invoice_query_carries_visit_id(auth_client, app):
    """Without it the join silently produces nothing and every row reads '—'."""
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                           ("صاحب السجل", "01000000988")).lastrowid
        pid = conn.execute("INSERT INTO pets(owner_id, pet_name, species, is_active)"
                           " VALUES(?,?,?,1)", (oid, "تيتو", "Dog")).lastrowid
        vid = conn.execute(
            "INSERT INTO visits(owner_id, pet_id, visit_date, visit_type,"
            " chief_complaint, doctor_name) VALUES(?,?,?,?,?,?)",
            (oid, pid, "2026-08-01", "Consultation", "سعال", "Dr. Test")).lastrowid
        conn.execute(
            "INSERT INTO invoices(owner_id, pet_id, visit_id, invoice_number,"
            " issue_date, total, paid_amount, due_amount, status)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (oid, pid, vid, "INV-HIST-1", "2026-08-01", 500, 500, 0, "Paid"))
        conn.commit()
        conn.close()

    data = auth_client.get("/visits/exam/api/owner/%d" % oid).get_json()
    inv = (data.get("invoices") or [])[0]
    assert "visit_id" in inv, \
        "the 360 payload drops visit_id, so History can never match an invoice"
    assert inv["visit_id"] == vid


def test_a_visit_with_no_extras_can_still_be_opened():
    """The regression this nearly shipped with.

    The link to the full visit lived in the expandable detail row, which is only
    built when there is something extra to show — so an ordinary consultation
    was not openable at all. That is worse than the flat table it replaced.
    """
    body = _render_history()
    open_link = body.index("'/visits/' + v.id")
    detail = body.index("hw-hist-detail")
    assert open_link < detail, \
        "the visit link is built inside the detail row, so plain visits cannot be opened"
    assert "stopPropagation" in body, \
        "clicking the date would both open the visit and toggle the row"


def test_history_renders_text_not_markup():
    """A symptom is free text somebody typed."""
    body = _render_history()
    assert "innerHTML" not in body, "History builds markup from stored text"
    assert "textContent" in body


def test_the_screen_still_renders(auth_client):
    r = auth_client.get("/visits/exam")
    assert r.status_code == 200
    assert 'id="hwHistBody"' in r.get_data(as_text=True)
