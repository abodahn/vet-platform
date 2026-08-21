# -*- coding: utf-8 -*-
"""The demo's Today board must not open empty, whatever day it was seeded on.

The seeder skips Fridays because the clinic is closed, and that skip ran ahead
of the "never leave the Today board empty" guard — so a demo seeded on a Friday
opened on nothing. The two existing board tests only catch that one day in
seven, so this one pins the seeder's idea of today to a Friday.
"""
import importlib.util
import os
import sqlite3
import sys
from datetime import date

_PLATFORM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SEED_PY = os.path.join(_PLATFORM, "scripts", "seed", "demo_showcase.py")

FRIDAY = date(2026, 8, 21)


class _FrozenDate(date):
    """date.today() pinned to the clinic's closed day."""

    @classmethod
    def today(cls):
        return FRIDAY


def _load():
    """Import the seeder by path — scripts/ is not a package."""
    spec = importlib.util.spec_from_file_location("demo_showcase", _SEED_PY)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["demo_showcase"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_today_is_populated_even_when_the_seed_runs_on_a_closed_day(tmp_path, monkeypatch):
    import models.database as db
    assert FRIDAY.weekday() == 4, "the fixture date has to be the closed day"
    seeder = _load()
    monkeypatch.setattr(seeder, "date", _FrozenDate)
    # run() repoints models.database at the throwaway file; put it back.
    saved = (db._db_path, db._PG_CONFIG, db._POOL)
    path = str(tmp_path / "friday.db")
    try:
        seeder.run(path, quiet=True)
    finally:
        db._db_path, db._PG_CONFIG, db._POOL = saved

    conn = sqlite3.connect(path)
    try:
        today = conn.execute("SELECT COUNT(*) FROM appointments WHERE appt_date = ?",
                             (FRIDAY.isoformat(),)).fetchone()[0]
        ahead = conn.execute("SELECT COUNT(*) FROM appointments WHERE appt_date > ?",
                             (FRIDAY.isoformat(),)).fetchone()[0]
    finally:
        conn.close()
    assert today >= 5, f"seeded on a Friday, today's board has {today} rows"
    assert ahead >= 10, f"only {ahead} upcoming appointments"


def test_the_diary_outlives_a_demo_seeded_weeks_ago(tmp_path, monkeypatch):
    """A demo file is rarely seeded on the morning it is shown."""
    import models.database as db
    from datetime import timedelta
    seeder = _load()
    monkeypatch.setattr(seeder, "date", _FrozenDate)
    saved = (db._db_path, db._PG_CONFIG, db._POOL)
    path = str(tmp_path / "stale.db")
    try:
        seeder.run(path, quiet=True)
    finally:
        db._db_path, db._PG_CONFIG, db._POOL = saved

    conn = sqlite3.connect(path)
    try:
        for weeks in (1, 2, 3, 4):
            shown = (FRIDAY + timedelta(weeks=weeks)).isoformat()
            n = conn.execute("SELECT COUNT(*) FROM appointments WHERE appt_date >= ?",
                             (shown,)).fetchone()[0]
            assert n >= 5, f"seeded {weeks} week(s) before the demo, {n} rows left"
    finally:
        conn.close()
