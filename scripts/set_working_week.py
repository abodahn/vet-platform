# -*- coding: utf-8 -*-
"""Show — and optionally correct — a clinic's configured working week.

The calculations now READ shifts.days_of_week instead of hardcoding Monday to
Friday. That fixes the code, but a clinic created before this release still has
whatever our seeder wrote, and the seeder wrote the American week: Mon-Fri, with
a "Weekend Morning" shift on Saturday and Sunday.

Left alone, such a clinic keeps treating Friday as a working day — so every
employee is marked absent on their day off and docked for it about four times a
month — and never counts Sunday, which is a normal working day in Egypt.

    python scripts/set_working_week.py                        # show what is configured
    python scripts/set_working_week.py --apply                # correct the untouched rows
    python scripts/set_working_week.py --tenant demo --apply  # a specific clinic

On a multi-clinic deployment every clinic has its OWN database, and without
--tenant this reads the default one — which on a live server is not the clinic
anybody is using. It refuses to guess: if clinics are registered and none is
named, it lists them and stops.

Read-only without --apply. With --apply it changes ONLY rows still holding the
exact value our seeder wrote; a week somebody chose by hand is never
overwritten. Attendance records and already-generated payslips are not rewritten
either — the change affects future leave counts and future payroll runs.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402

_DAY_NAMES = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}

# What our seeder wrote  ->  what it should have been for Egypt.
# Keyed on the exact string, so an edited row never matches.
_SEEDED_FIX = {
    "1,2,3,4,5":     "0,1,2,3,4",      # Mon-Fri             -> Sun-Thu
    "1,2,3,4,5,6,7": "0,1,2,3,4,5,6",  # every day, ISO      -> every day, Sun=0
    "6,7":           "5,6",            # Sat+Sun ("weekend") -> Fri+Sat
}


def _pretty(raw):
    out = []
    for part in str(raw or "").split(","):
        part = part.strip()
        if part.lstrip("-").isdigit():
            out.append(_DAY_NAMES.get(int(part) % 7, part))
    return " ".join(out) or "(none set)"


def _run(conn, apply_it):
    """Show the configured week, and correct the untouched rows when asked."""
    rows = [dict(r) for r in conn.execute(
        "SELECT id, name, start_time, end_time, days_of_week, is_active"
        " FROM shifts ORDER BY id").fetchall()]

    if not rows:
        print("  No shifts are configured, so the built-in default applies: "
              "Sun Mon Tue Wed Thu.")
        return

    print("  %-4s %-18s %-13s %-26s %s"
          % ("id", "shift", "hours", "working days", ""))
    changes = []
    for r in rows:
        raw = (r["days_of_week"] or "").strip()
        target = _SEEDED_FIX.get(raw)
        if not r["is_active"]:
            note = "(inactive)"
        elif target:
            note = "-> " + _pretty(target)
            changes.append((r["id"], r["name"], raw, target))
        else:
            note = "(set by hand - left alone)"
        print("  %-4s %-18s %-13s %-26s %s" % (
            r["id"], (r["name"] or "")[:18],
            "%s-%s" % (r["start_time"], r["end_time"]),
            _pretty(raw), note))

    if not changes:
        print("")
        print("  Nothing to correct: no shift still holds the seeded "
              "Monday-to-Friday week.")
        return

    if not apply_it:
        print("")
        print("  %d shift(s) still hold the seeded American week." % len(changes))
        print("  Re-run with --apply to correct them. Nothing has been changed.")
        return

    print("")
    for sid, name, before, after in changes:
        conn.execute("UPDATE shifts SET days_of_week=? WHERE id=?", (after, sid))
        print("  #%-3s %-18s %-26s -> %s"
              % (sid, (name or "")[:18], _pretty(before), _pretty(after)))
    conn.commit()
    print("")
    print("  %d shift(s) corrected. Attendance records and existing payslips "
          "were not touched; future leave counts and payroll runs use the "
          "corrected week." % len(changes))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the corrected week (default: show only)")
    ap.add_argument("--tenant", default="",
                    help="clinic slug on a multi-clinic deployment, or 'all'")
    args = ap.parse_args()

    app = create_app(Config)
    with app.app_context():
        from models import tenancy

        registered = [t.get("slug") for t in tenancy.all_tenants()]

        # Each clinic has its OWN database. Reading the default one on a live
        # multi-clinic server means reporting on a database nobody uses — and
        # with --apply, writing to it. Refuse to guess.
        if registered and not args.tenant:
            print("This deployment has %d clinic(s), each with its own database:"
                  % len(registered))
            for slug in registered:
                print("   %s" % slug)
            print("")
            print("Name one with --tenant <slug>, or --tenant all.")
            return 2

        if args.tenant and args.tenant != "all" and args.tenant not in registered:
            print("No clinic registered as %r." % args.tenant)
            return 2

        targets = registered if args.tenant == "all" else (
            [args.tenant] if args.tenant else [None])

        for slug in targets:
            if slug is None:
                print("Default database:")
                conn = db.get_db()
                try:
                    _run(conn, args.apply)
                finally:
                    conn.close()
                continue
            print("Clinic %s:" % slug)
            with tenancy.use(slug):
                conn = db.get_db()
                try:
                    _run(conn, args.apply)
                finally:
                    conn.close()
            print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
