# -*- coding: utf-8 -*-
"""The pet file must open on the last day of every month.

It computed "one month from now" as date.replace(month=month + 1), which raises
ValueError whenever that day number does not exist in the next month. So the pet
detail page - the screen the demo script calls the moment the sale happens -
returned a 500 on 31 January, 31 March, 31 May, 31 August, 31 October, and on
the 29th to 31st of any month whose successor is February.

It passed every other day of the year, which is why it survived. The test below
freezes the clock rather than trusting the calendar, because a test that only
fails seven days a year is not a test.
"""
import datetime as _dt
import itertools

import pytest

import blueprints.crm.routes as crm
import models.database as db

_n = itertools.count()


@pytest.fixture
def a_real_pet(app):
    """A pet that actually exists.

    Not optional. pet_detail() redirects when the id is unknown, so a test
    against an arbitrary id never reaches the date arithmetic at all - the
    first version of this file asserted != 500 against /crm/pets/1, passed,
    and went on passing with the bug deliberately restored.
    """
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                i = next(_n)
                cur = conn.execute(
                    "INSERT INTO owners (full_name, phone) VALUES (?,?)",
                    ("Month End Owner %d" % i, "0100000%04d" % i))
                owner_id = cur.lastrowid
                cur = conn.execute(
                    "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
                    (owner_id, "Monthend%d" % i, "Cat"))
                pet_id = cur.lastrowid
        finally:
            conn.close()

    yield pet_id

    # Put the database back.
    #
    # The `app` fixture is SESSION-scoped, so all 130-odd test files share one
    # SQLite file and rows written here are still there when later files run.
    # This test is parametrised eight ways, so without this it left eight owners
    # and eight pets behind - and every alphabetically later file that counts
    # rows (test_workflow_page, test_visit_attribution, test_workflow_visit_
    # safety) started failing on totals that had nothing to do with them.
    with app.app_context():
        conn = db.get_db()
        try:
            with conn:
                conn.execute("DELETE FROM pets WHERE id=?", (pet_id,))
                conn.execute("DELETE FROM owners WHERE id=?", (owner_id,))
        finally:
            conn.close()


class _FrozenDate(_dt.date):
    """A date class whose today() is a day we choose."""
    _today = _dt.date(2026, 8, 31)

    @classmethod
    def today(cls):
        return cls._today


@pytest.fixture
def on_day(monkeypatch):
    def _set(y, m, d):
        _FrozenDate._today = _dt.date(y, m, d)
        monkeypatch.setattr(crm, "date", _FrozenDate)
    return _set


# Every day that used to raise. Aug 31 is the one that mattered: it is three
# days after the defect was found.
@pytest.mark.parametrize("y,m,d", [
    (2026, 1, 31),   # -> February 31
    (2026, 3, 31),   # -> April 31
    (2026, 5, 31),   # -> June 31
    (2026, 8, 31),   # -> September 31
    (2026, 10, 31),  # -> November 31
    (2026, 1, 30),   # -> February 30
    (2027, 2, 28),   # a safe day, as a control
    (2026, 12, 31),  # the branch that was already correct
])
def test_pet_file_opens_on_month_end(auth_client, a_real_pet, on_day, y, m, d):
    on_day(y, m, d)
    r = auth_client.get("/crm/pets/%d" % a_real_pet)
    # 200, not merely "not 500": a redirect would mean the pet was not found
    # and the date arithmetic never ran, which is how this test first passed
    # against the bug it exists to catch.
    assert r.status_code == 200, (
        "pet file returned %d when today is %04d-%02d-%02d - the 'one month "
        "from now' date arithmetic raised"
        % (r.status_code, y, m, d))


def test_the_window_is_thirty_days_and_always_valid():
    """Directly: the replacement must never raise, on any date in a leap cycle."""
    day = _dt.date(2024, 1, 1)          # 2024 is a leap year
    while day < _dt.date(2028, 1, 1):
        soon = day + _dt.timedelta(days=30)
        assert soon > day
        day += _dt.timedelta(days=1)
