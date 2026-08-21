# -*- coding: utf-8 -*-
"""The owner search behind every dropdown in the app.

Owner pickers used to render a capped slice of the table (LIMIT 200-500), so
once a clinic passed the cap its newer clients were simply unselectable, with
no error and no sign anything was missing. They now type into one shared
server-side search, which makes this endpoint load-bearing for booking a
grooming slot, admitting an inpatient, raising an invoice and starting a visit.

These pin the three defects found reviewing that change.
"""
import io

import pytest

from conftest import get_csrf     # noqa: F401  (kept for parity with siblings)

AR = "ياسمين عبد الودود"
LATIN = "Yasmine Abdelwadoud"


@pytest.fixture
def bilingual_owner(app):
    """A client recorded the way an Arabic-first clinic records one."""
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        cur = conn.execute(
            "INSERT INTO owners (full_name, full_name_ar, phone, whatsapp_phone)"
            " VALUES (?,?,?,?)",
            (LATIN, AR, "01097001100", "01097009900"))
        oid = cur.lastrowid
        conn.commit()
        conn.close()
    return oid


# ── the Arabic half ──────────────────────────────────────────────────────────

def test_an_arabic_name_can_be_searched_in_arabic(app, bilingual_owner):
    """The product's whole differentiator is being Arabic-first. The search
    matched full_name only, so a clinic could record a client in Arabic and
    then never find them again - the exact defect loc() was added to fix on
    the display side, reappearing on the input side."""
    import models.database as db
    with app.app_context():
        ids = {o["id"] for o in db.list_owners(search="ياسمين", limit=25)}
    assert bilingual_owner in ids, "an Arabic name is unsearchable in Arabic"


def test_the_endpoint_returns_the_arabic_name(auth_client, bilingual_owner):
    """Matching in Arabic and then labelling in Latin is only half a fix: the
    reader is shown a transliteration they never typed."""
    payload = auth_client.get("/crm/owners/search-json",
                              query_string={"q": "ياسمين"}).get_json()
    row = next((o for o in payload["owners"] if o["id"] == bilingual_owner), None)
    assert row is not None, "the endpoint cannot find the Arabic-named client"
    assert row.get("full_name_ar") == AR, (
        "the dropdown has no Arabic name to show, so it will print the Latin one")


def test_the_dropdown_prefers_the_clinics_own_spelling():
    src = io.open("static/js/platform.js", encoding="utf-8").read()
    assert "o.full_name_ar || o.full_name" in src, (
        "the option label ignores the Arabic name the clinic recorded")


# ── the count must agree with the rows ───────────────────────────────────────

@pytest.mark.parametrize("q", [LATIN, "ياسمين", "01097009900"])
def test_the_header_count_matches_the_rows(app, bilingual_owner, q):
    """bug-503. list_owners() matched whatsapp_phone and count_owners() did
    not, so the header said one number and the table showed another. They now
    share one clause; this fails if they drift again."""
    import models.database as db
    with app.app_context():
        rows = len(db.list_owners(search=q, limit=200))
        count = db.count_owners(search=q)
    assert rows == count, "searching %r: %d rows but a count of %d" % (q, rows, count)


def test_both_queries_use_the_one_shared_clause():
    src = io.open("models/database.py", encoding="utf-8").read()
    assert src.count("_owner_search_where(") >= 3, (
        "the search clause has been inlined again - that is how the count and "
        "the rows drifted apart the first time")


# ── the two failure modes in the browser ─────────────────────────────────────

def test_a_failed_search_is_not_shown_as_an_empty_result():
    """An empty dropdown and a broken server look identical. A receptionist who
    searches, sees nothing, and concludes the client does not exist will create
    a duplicate - which is the outcome this whole control exists to prevent.

    Same shape as bug-499: fetch() only rejects on network errors, so a 4xx or
    5xx takes the success branch unless something checks r.ok."""
    src = io.open("static/js/platform.js", encoding="utf-8").read()
    assert "if (!r.ok) throw" in src, "an HTTP error still reads as no results"
    assert "Search unavailable" in src, "a failed search says nothing to the user"


def test_an_edit_form_keeps_the_owner_it_arrived_with():
    """finance/invoice_edit.html gained the live search while its route still
    renders the record's current owner as the selected option. The rebuild
    wipes every option on the first keystroke, so without preserving it,
    typing in the search box silently drops the owner already on the invoice -
    and a single-match search can move the invoice to a different client."""
    src = io.open("static/js/platform.js", encoding="utf-8").read()
    assert "var preset" in src, "the pre-selected owner is not preserved"
    assert "if (preset" in src, "the preserved owner is never put back"
