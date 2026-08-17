# -*- coding: utf-8 -*-
"""Recompute hours_worked from the times actually recorded.

hours_worked is the column payroll pays overtime on, and it was written by
whatever put the row there — the app's check-out, an import, a seeder — each
using its own arithmetic. Where the stored figure disagrees with check_in,
check_out and the break on the same row, the row contradicts itself, and the
disagreement is invisible because nothing recalculates.

This makes the stored hours consistent with the recorded times, using the same
_calc_hours the application uses, including the overnight rule taken from the
employee's own shift.

    python scripts/recompute_attendance_hours.py --tenant demo
    python scripts/recompute_attendance_hours.py --tenant demo --apply

WITHOUT --apply nothing is written: it prints how many rows move, the total
before and after, and the largest individual changes.

WITH --apply it first writes every current (id, hours_worked) pair to a
rollback CSV and prints the path, because this is not otherwise reversible —
the previous value exists nowhere else.

ONLY hours_worked is touched. Not status: Present / Late / Absent / On Leave is
a judgement somebody made about the day, and recomputing lateness across months
of history would rewrite that judgement wholesale. Rows missing either time are
left alone — there is nothing to compute from.

THIS CHANGES PAY. Overtime is hours_worked minus the shift's standard hours, so
every row that moves changes what the next payroll run calculates for that
month. Existing generated payslips are NOT rewritten; regenerating one after
this will produce a different number than it did before, which is the point,
and is why the dry run shows the totals first.
"""
import argparse
import csv
import io
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402

# Anything smaller is rounding noise, not a disagreement worth rewriting a
# payroll input for.
EPSILON = 0.01


def _run(conn, apply_it, backup_dir):
    from blueprints.attendance.routes import (
        _calc_hours, default_shift, shift_crosses_midnight, hhmm)

    rows = [dict(r) for r in conn.execute(
        "SELECT id, user_id, work_date, check_in, check_out, break_minutes,"
        " hours_worked, status FROM attendance_records ORDER BY id").fetchall()]

    shift_cache = {}
    changes, skipped_no_times, unchanged = [], 0, 0

    for r in rows:
        if not hhmm(r["check_in"]) or not hhmm(r["check_out"]):
            skipped_no_times += 1
            continue
        key = r["user_id"]
        if key not in shift_cache:
            shift_cache[key] = default_shift(conn, r["user_id"], r["work_date"])
        overnight = shift_crosses_midnight(shift_cache[key])

        fresh = _calc_hours(r["check_in"], r["check_out"],
                            int(r["break_minutes"] or 0), overnight=overnight)
        old = float(r["hours_worked"] or 0)
        if abs(fresh - old) < EPSILON:
            unchanged += 1
            continue
        changes.append((r, old, fresh))

    total_old = sum(float(r["hours_worked"] or 0) for r in rows)
    delta = sum(new - old for _r, old, new in changes)

    print("  rows                    : %d" % len(rows))
    print("  no check-in/out (left)  : %d" % skipped_no_times)
    print("  already consistent      : %d" % unchanged)
    print("  would change            : %d" % len(changes))
    print("")
    print("  total hours now         : %.2f" % total_old)
    print("  total hours after       : %.2f  (%+.2f)" % (total_old + delta, delta))

    if changes:
        biggest = sorted(changes, key=lambda c: abs(c[2] - c[1]), reverse=True)[:8]
        print("")
        print("  largest changes:")
        print("    %-12s %-8s %-8s %8s %8s %8s"
              % ("date", "in", "out", "stored", "actual", "delta"))
        for r, old, new in biggest:
            print("    %-12s %-8s %-8s %8.2f %8.2f %+8.2f"
                  % (str(r["work_date"])[:10], hhmm(r["check_in"]),
                     hhmm(r["check_out"]), old, new, new - old))

    if not changes:
        print("")
        print("  Nothing to recompute: every row already agrees with its times.")
        return

    if not apply_it:
        print("")
        print("  Re-run with --apply to write them. Nothing has been changed.")
        print("  NOTE: overtime is hours_worked minus the shift standard, so this")
        print("        moves what the next payroll run calculates.")
        return

    # The previous value exists nowhere else once this runs.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(backup_dir, "attendance_hours_before_%s.csv" % stamp)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "user_id", "work_date", "hours_worked_before",
                    "hours_worked_after"])
        for r, old, new in changes:
            w.writerow([r["id"], r["user_id"], r["work_date"], old, new])
    print("")
    print("  rollback written to %s" % path)

    for r, _old, new in changes:
        conn.execute(
            "UPDATE attendance_records SET hours_worked=?,"
            " updated_at=datetime('now','localtime') WHERE id=?",
            (new, r["id"]))
    conn.commit()
    print("  %d row(s) recomputed. status was not touched, and no payslip was "
          "rewritten." % len(changes))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the recomputed hours (default: show only)")
    ap.add_argument("--tenant", default="",
                    help="clinic slug on a multi-clinic deployment, or 'all'")
    ap.add_argument("--backup-dir", default=".",
                    help="where to write the rollback CSV (default: cwd)")
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
                    _run(conn, args.apply, args.backup_dir)
                finally:
                    conn.close()
            else:
                with tenancy.use(slug):
                    conn = db.get_db()
                    try:
                        _run(conn, args.apply, args.backup_dir)
                    finally:
                        conn.close()
            print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
