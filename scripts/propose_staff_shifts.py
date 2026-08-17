# -*- coding: utf-8 -*-
"""Roster staff onto shifts using the hours they actually work.

Attendance now judges each employee against THEIR shift — lateness, the nightly
auto-close, and the overtime that becomes money all read staff_shifts. But
staff_shifts is empty on a clinic that has never opened the HR roster screen, so
everybody silently falls back to the clinic-wide first shift. For a day-shift
clinic that is harmless; for anyone working evenings or nights it means being
marked Late every day and auto-closed to the wrong hours.

Guessing who works when would be inventing clinic policy. So this does not
guess: it reads the times people have ALREADY clocked in at, takes the median
per person, and proposes the shift whose start is nearest.

    python scripts/propose_staff_shifts.py --tenant demo            # show
    python scripts/propose_staff_shifts.py --tenant demo --apply    # roster them

Only proposes where the evidence is good enough — see MIN_RECORDS and
MAX_DRIFT_MIN below. Anyone with too few records, or whose hours do not sit
near any shift, is listed and left alone: no assignment is better than a wrong
one, because a wrong one produces confident, wrong pay.

Never overwrites an existing assignment. A roster somebody set by hand is a
decision; this is a suggestion.
"""
import argparse
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402

# Fewer clock-ins than this and the median means nothing.
MIN_RECORDS = 5
# If the median sits further than this from every shift start, the person's
# hours do not match any shift the clinic has defined, and that is a question
# for a human rather than something to round away.
MAX_DRIFT_MIN = 90


def _mins(hhmm):
    try:
        h, m = str(hhmm)[:5].split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None


def _hhmm(mins):
    return "%02d:%02d" % (mins // 60, mins % 60)


def _gap(a, b):
    """Minutes between two times of day, the short way round the clock.

    22:10 against a 22:00 shift is ten minutes, not fourteen hours — without
    wrapping, every night worker looks like a terrible match for their own
    shift and gets left unassigned.
    """
    d = abs(a - b) % (24 * 60)
    return min(d, 24 * 60 - d)


def _run(conn, apply_it):
    shifts = [dict(r) for r in conn.execute(
        "SELECT id, name, start_time, end_time FROM shifts WHERE is_active=1"
        " ORDER BY id").fetchall()]
    if not shifts:
        print("  No active shifts to roster onto.")
        return

    starts = [(s, _mins(s["start_time"])) for s in shifts]
    starts = [(s, m) for s, m in starts if m is not None]

    staff = [dict(r) for r in conn.execute(
        "SELECT id, full_name, username, role FROM users WHERE is_active=1"
        " ORDER BY full_name").fetchall()]

    already = {r["user_id"] for r in conn.execute(
        "SELECT DISTINCT user_id FROM staff_shifts"
        " WHERE effective_to IS NULL OR effective_to >= ?",
        (date.today().isoformat(),)).fetchall()}

    proposals, skipped = [], []
    for u in staff:
        if u["id"] in already:
            skipped.append((u, "already rostered", "", 0))
            continue
        times = [_mins(r["check_in"]) for r in conn.execute(
            "SELECT check_in FROM attendance_records"
            " WHERE user_id=? AND check_in IS NOT NULL AND check_in <> ''"
            " ORDER BY check_in", (u["id"],)).fetchall()]
        times = [t for t in times if t is not None]
        if len(times) < MIN_RECORDS:
            skipped.append((u, "only %d clock-in(s)" % len(times), "", len(times)))
            continue

        median = sorted(times)[len(times) // 2]
        best, gap = None, None
        for s, m in starts:
            g = _gap(median, m)
            if gap is None or g < gap:
                best, gap = s, g
        if gap is None or gap > MAX_DRIFT_MIN:
            skipped.append((u, "usual start %s matches no shift" % _hhmm(median),
                            "", len(times)))
            continue
        proposals.append((u, best, median, gap, len(times)))

    print("  %-22s %-13s %-8s %-20s %s"
          % ("staff", "role", "usual in", "proposed shift", "off by"))
    for u, s, median, gap, n in proposals:
        print("  %-22s %-13s %-8s %-20s %d min  (%d days)"
              % ((u["full_name"] or u["username"])[:22], u["role"],
                 _hhmm(median), "%s %s" % (s["name"], s["start_time"]), gap, n))

    for u, why, _x, _n in skipped:
        print("  %-22s %-13s %s"
              % ((u["full_name"] or u["username"])[:22], u["role"], "- " + why))

    if not proposals:
        print("")
        print("  Nothing to roster.")
        return

    if not apply_it:
        print("")
        print("  %d proposal(s). Re-run with --apply to roster them. "
              "Nothing has been changed." % len(proposals))
        return

    print("")
    today = date.today().isoformat()
    for u, s, median, gap, n in proposals:
        conn.execute(
            "INSERT INTO staff_shifts(user_id, shift_id, effective_from)"
            " VALUES(?,?,?)", (u["id"], s["id"], today))
        print("  rostered %-22s -> %s" % ((u["full_name"] or u["username"])[:22],
                                          s["name"]))
    conn.commit()
    print("")
    print("  %d rostered from %s. Existing assignments were not changed, and no "
          "attendance record or payslip was rewritten." % (len(proposals), today))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the roster (default: show only)")
    ap.add_argument("--tenant", default="",
                    help="clinic slug on a multi-clinic deployment, or 'all'")
    args = ap.parse_args()

    app = create_app(Config)
    with app.app_context():
        from models import tenancy
        registered = [t.get("slug") for t in tenancy.all_tenants()]

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
            print("Clinic %s:" % (slug or "(default database)"))
            if slug is None:
                conn = db.get_db()
                try:
                    _run(conn, args.apply)
                finally:
                    conn.close()
            else:
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
