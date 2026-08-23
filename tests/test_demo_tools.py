# -*- coding: utf-8 -*-
"""The two tools you run in the half hour before a demo.

scripts/demo_check.py reports what is wrong. These two fix the parts of it that
are fixable from a keyboard: the prospect's logo, and today's appointment board.

Both invent or overwrite clinic data, so both refuse to run against anything
whose slug does not say demo/test/staging. That guard is the reason these tests
exist - a rename is harmless, a rename of the wrong clinic is a support call
from a customer whose system suddenly carries a stranger's name.
"""
import io
import os

import pytest


@pytest.fixture
def clinic_with_patients(app):
    """Owners and pets to book. Without these the top-up correctly does
    nothing - and three of the tests below would pass vacuously against an
    empty board, which is worse than failing."""
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM pets").fetchone()[0]
        for i in range(max(0, 12 - n)):
            cur = conn.execute(
                "INSERT INTO owners (full_name, phone) VALUES (?,?)",
                ("Topup Client %d" % i, "0109955%04d" % i))
            conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                (cur.lastrowid, "Topup Pet %d" % i, "Dog"))
        conn.commit()
        conn.close()
    return app


# ── the guard, on both tools ─────────────────────────────────────────────────

@pytest.mark.parametrize("slug", ["hatem-vet", "nilevet", "production", "clinic1"])
def test_neither_tool_will_touch_a_real_clinic(slug):
    from scripts.demo_brand import _guard as brand_guard
    from scripts.demo_topup_today import _guard as topup_guard
    for guard, name in ((brand_guard, "demo_brand"), (topup_guard, "demo_topup_today")):
        with pytest.raises(SystemExit) as exc:
            guard(slug)
        assert slug in str(exc.value), (
            "%s refused without naming the clinic, which is the one thing the "
            "reader needs to know" % name)


@pytest.mark.parametrize("slug", ["demo", "demo2", "acme-test", "staging"])
def test_both_tools_allow_a_demo_clinic(slug):
    from scripts.demo_brand import _guard as brand_guard
    from scripts.demo_topup_today import _guard as topup_guard
    brand_guard(slug)
    topup_guard(slug)


# ── the logo ─────────────────────────────────────────────────────────────────

def test_a_logo_becomes_a_small_data_uri():
    """It is stored in the clinic ROW, not on disk, because models/backup.py
    backs up the database and nothing else - a logo on the filesystem would not
    survive a restore. So it has to be small enough to belong in a row."""
    from scripts.demo_brand import _logo_data_uri, _LOGO_MAX_BYTES
    src = "static/images/aleefy-logo.png"
    uri = _logo_data_uri(src)
    assert uri.startswith("data:image/"), "not a usable data URI"
    assert len(uri) < _LOGO_MAX_BYTES, "the logo is too big for the clinic row"
    assert len(uri) < os.path.getsize(src), (
        "the logo was not shrunk - a phone photograph in this column is carried "
        "in every page render and every backup")


def test_a_missing_logo_file_says_so():
    from scripts.demo_brand import _logo_data_uri
    with pytest.raises(SystemExit) as exc:
        _logo_data_uri("static/images/does-not-exist.png")
    assert "No such file" in str(exc.value)


def test_reset_clears_the_logo():
    """Otherwise the last prospect's logo is still at the top of the page when
    the next one walks in."""
    from scripts.demo_brand import DEMO_DEFAULTS
    assert "logo_data" in DEMO_DEFAULTS, "--reset does not clear the logo"
    assert DEMO_DEFAULTS["logo_data"] == ""


# ── the appointment board ────────────────────────────────────────────────────

def test_topping_up_is_idempotent(clinic_with_patients, app):
    """Run it twice on the morning of a demo and the board must not show
    sixteen appointments."""
    from datetime import date
    from scripts.demo_topup_today import _run
    import models.database as db

    with app.app_context():
        conn = db.get_db()
        try:
            _run(conn, 5, True)
            after_first = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE appt_date=?",
                (date.today().isoformat(),)).fetchone()[0]
            _run(conn, 5, True)
            after_second = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE appt_date=?",
                (date.today().isoformat(),)).fetchone()[0]
        finally:
            conn.close()
    assert after_first >= 5, "the board was not filled"
    assert after_second == after_first, (
        "running twice booked more: %d then %d" % (after_first, after_second))


def test_a_dry_run_books_nothing(clinic_with_patients, app):
    from datetime import date
    from scripts.demo_topup_today import _run
    import models.database as db

    with app.app_context():
        conn = db.get_db()
        try:
            before = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE appt_date=?",
                (date.today().isoformat(),)).fetchone()[0]
            _run(conn, before + 6, False)
            after = conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE appt_date=?",
                (date.today().isoformat(),)).fetchone()[0]
        finally:
            conn.close()
    assert before == after, "a dry run changed the database"


def test_appointments_land_inside_clinic_hours(clinic_with_patients, app):
    """A board with a 03:00 appointment on it is worse than an empty one.

    Scoped to the rows THIS tool created. An earlier version asserted about
    every appointment today and failed in the full suite on an 08:45 booked by
    another test - a claim about data it did not own, which passed alone and
    only broke once something else shared the database.
    """
    from datetime import date
    from scripts.demo_topup_today import _run, _DAY_START, _DAY_END
    import models.database as db

    today = date.today().isoformat()
    with app.app_context():
        conn = db.get_db()
        try:
            before = {r[0] for r in conn.execute(
                "SELECT id FROM appointments WHERE appt_date=?", (today,)).fetchall()}
            _run(conn, len(before) + 6, True)
            rows = conn.execute(
                "SELECT id, appt_start FROM appointments WHERE appt_date=?",
                (today,)).fetchall()
        finally:
            conn.close()
    mine = [str(start) for (aid, start) in rows if aid not in before]
    assert mine, "the tool booked nothing, so this asserted nothing"
    for start in mine:
        hour = int(start[:2])
        assert _DAY_START <= hour < _DAY_END, (
            "the tool booked %s, outside clinic hours" % start)


def test_it_does_not_double_book_a_slot(clinic_with_patients, app):
    from datetime import date
    from scripts.demo_topup_today import _run
    import models.database as db

    with app.app_context():
        conn = db.get_db()
        try:
            before = {r[0] for r in conn.execute(
                "SELECT id FROM appointments WHERE appt_date=?",
                (date.today().isoformat(),)).fetchall()}
            _run(conn, len(before) + 9, True)
            rows = conn.execute(
                "SELECT id, appt_start FROM appointments WHERE appt_date=?",
                (date.today().isoformat(),)).fetchall()
        finally:
            conn.close()
    # Only the rows this tool created. Another test is free to double-book its
    # own fixtures; that is not this tool's contract.
    mine = [str(start) for (aid, start) in rows if aid not in before]
    assert mine, "the tool booked nothing, so this asserted nothing"
    assert len(mine) == len(set(mine)), (
        "the tool booked two appointments at the same time: %s"
        % sorted(t for t in mine if mine.count(t) > 1))
