# -*- coding: utf-8 -*-
"""Build and work the target-market database.

    python scripts/market_db.py import clinics.csv
    python scripts/market_db.py score
    python scripts/market_db.py cohorts
    python scripts/market_db.py status
    python scripts/market_db.py export market.xlsx
    python scripts/market_db.py why "Cairo Vet Hospital"

WHY A DATABASE AND NOT AN AD AUDIENCE

There is a countable number of veterinary clinics in Cairo and Giza. Each one
either becomes a customer or does not. That is a list to be worked, not an
audience to be targeted, and the difference decides where the money goes: a
list costs time, an audience costs money you do not have.

THE CSV IT IMPORTS

One row per clinic. Only `name` is required; everything else improves the score
or makes the clinic reachable. Unknown columns are ignored rather than
refused, so a scrape can hand over whatever it found.

    name, name_ar, governorate, district, address, phone, whatsapp, email,
    website, facebook, instagram, maps_url, contact_name, contact_role,
    branches, vets, is_hospital, has_grooming, has_boarding, has_pharmacy,
    has_petshop, has_lab, current_software, notes, source, source_url

Booleans accept 1/0, yes/no, true/false, and Arabic نعم/لا.

Re-importing is safe: a clinic already present is updated, not duplicated,
matched on (name, district).
"""
import argparse
import csv
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402
from models import prospects as P   # noqa: E402

_TRUE = {"1", "y", "yes", "true", "t", "نعم", "ايوه", "أيوه"}
_INT_COLS = ("branches", "vets")
_BOOL_COLS = ("is_hospital", "has_grooming", "has_boarding",
              "has_pharmacy", "has_petshop", "has_lab")
_TEXT_COLS = ("name", "name_ar", "governorate", "district", "address", "phone",
              "whatsapp", "email", "website", "facebook", "instagram",
              "maps_url", "contact_name", "contact_role", "current_software",
              "notes", "source", "source_url", "status")


def _clean(raw: dict) -> dict:
    out = {}
    for k, v in raw.items():
        key = (k or "").strip().lower().replace(" ", "_")
        val = (v or "").strip() if isinstance(v, str) else v
        if key in _TEXT_COLS:
            out[key] = val
        elif key in _BOOL_COLS:
            out[key] = 1 if str(val).strip().lower() in _TRUE else 0
        elif key in _INT_COLS:
            try:
                out[key] = int(str(val).strip())
            except (TypeError, ValueError):
                pass
    return out


def cmd_import(conn, path: str) -> int:
    if not os.path.isfile(path):
        print("No such file: %s" % path)
        return 2
    new = updated = skipped = 0
    with io.open(path, encoding="utf-8-sig", newline="") as fh:
        for raw in csv.DictReader(fh):
            row = _clean(raw)
            if not row.get("name"):
                skipped += 1
                continue
            row.setdefault("source", os.path.basename(path))
            if P.upsert(conn, row) == "new":
                new += 1
            else:
                updated += 1
    conn.commit()
    print("  new      : %d" % new)
    print("  updated  : %d" % updated)
    if skipped:
        print("  skipped  : %d (no name)" % skipped)
    return 0


def cmd_score(conn) -> int:
    n = P.rescore_all(conn)
    print("  rescored : %d clinic(s)" % n)
    return 0


def cmd_cohorts(conn, strategy: str) -> int:
    out = P.assign_cohorts(conn, strategy=strategy)
    if not out:
        print("  Nothing to assign - no clinics with status 'new'.")
        return 0
    for c in sorted(out):
        print("  cohort %d : %d clinic(s)" % (c, out[c]))
    print("")
    if strategy == "spread":
        print("  Spread deliberately: cohort 1 gets a MIX of scores, so the")
        print("  best accounts are not spent on the least practised pitch.")
        print("  Use --strategy top to work best-first instead.")
    return 0


def cmd_status(conn) -> int:
    s = P.summary(conn)
    print("  clinics mapped     : %d" % s["total"])
    print("  with a score > 0   : %d" % s["scored"])
    print("  reachable by phone : %d" % s["contactable"])
    if s["total"] and s["contactable"] < s["total"]:
        print("                       (%d have no number - they are on the map"
              % (s["total"] - s["contactable"]))
        print("                        but cannot yet be worked)")
    print("")
    if s["by_governorate"]:
        print("  by territory:")
        for g, n in list(s["by_governorate"].items())[:8]:
            print("    %-22s %d" % (g, n))
    if s["by_cohort"]:
        print("")
        print("  by cohort: " + ", ".join("%d=%d" % (k, v)
                                          for k, v in sorted(s["by_cohort"].items())))
    if s["by_status"]:
        print("  by stage : " + ", ".join(
            "%s=%d" % (k, s["by_status"][k])
            for k in P.STAGES if k in s["by_status"]))
    return 0


def cmd_why(conn, name: str) -> int:
    P.ensure_tables(conn)
    row = conn.execute("SELECT * FROM prospects WHERE name LIKE ? LIMIT 1",
                       ("%" + name + "%",)).fetchone()
    if not row:
        print("No clinic matching %r." % name)
        return 1
    row = dict(row)
    print("  %s  (%s, %s)" % (row["name"], row.get("district") or "?",
                              row.get("governorate") or "?"))
    print("  score %d" % (row.get("score") or 0))
    print("")
    for line in P.explain_score(row):
        print("    %s" % line)
    if row.get("current_software"):
        print("")
        print("  Already using: %s" % row["current_software"])
        print("  Not scored, deliberately - it points both ways. They have")
        print("  proven they will pay for software, and they are mid-contract.")
    return 0


def cmd_export(conn, path: str) -> int:
    """An Excel workbook to actually make calls from.

    A CLI is the wrong tool for a person with a phone in one hand. This is
    sorted the way the calls should be made, and has the columns that get
    written in during the call.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    P.ensure_tables(conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM prospects ORDER BY cohort, governorate, district,"
        " score DESC, name").fetchall()]
    if not rows:
        print("  Nothing to export yet - import a CSV first.")
        return 1

    wb = Workbook()
    ws = wb.active
    ws.title = "Call list"
    heads = ["Cohort", "Score", "Clinic", "الاسم", "Governorate", "District",
             "Phone", "WhatsApp", "Signals", "Already using",
             "Status", "Last contact", "Next action", "When", "Notes"]
    widths = [8, 7, 30, 26, 14, 18, 16, 16, 34, 16, 14, 14, 30, 12, 40]
    for i, (h, w) in enumerate(zip(heads, widths), start=1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1B6B5C")
        c.alignment = Alignment(vertical="center", wrap_text=True)
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "C2"

    def signals(r):
        got = []
        if int(r.get("branches") or 1) > 1:
            got.append("%s branches" % r["branches"])
        for key, label in (("is_hospital", "hospital"), ("has_grooming", "grooming"),
                           ("has_boarding", "boarding"), ("has_pharmacy", "pharmacy"),
                           ("has_petshop", "shop"), ("has_lab", "lab")):
            if int(r.get(key) or 0):
                got.append(label)
        if r.get("vets"):
            got.append("%s vets" % r["vets"])
        return " · ".join(got)

    for n, r in enumerate(rows, start=2):
        vals = [r.get("cohort"), r.get("score"), r.get("name"), r.get("name_ar"),
                r.get("governorate"), r.get("district"), r.get("phone"),
                r.get("whatsapp"), signals(r), r.get("current_software"),
                r.get("status"), r.get("last_contact"), r.get("next_action"),
                r.get("next_action_on"), r.get("notes")]
        for i, v in enumerate(vals, start=1):
            c = ws.cell(row=n, column=i, value=v)
            c.font = Font(name="Arial", size=10)
            c.alignment = Alignment(vertical="top", wrap_text=(i in (9, 15)))
        # A clinic with no number cannot be called, however good it looks.
        if not (r.get("phone") or r.get("whatsapp")):
            for i in range(1, len(heads) + 1):
                ws.cell(row=n, column=i).fill = PatternFill("solid", fgColor="FDECEA")

    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(heads)), len(rows) + 1)

    # A second sheet that says where every number came from, because the first
    # wrong phone number destroys trust in the whole list.
    src = wb.create_sheet("Sources")
    for i, h in enumerate(["Clinic", "Source", "URL"], start=1):
        c = src.cell(row=1, column=i, value=h)
        c.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1B6B5C")
    for w, col in zip((30, 24, 70), "ABC"):
        src.column_dimensions[col].width = w
    for n, r in enumerate(rows, start=2):
        src.cell(row=n, column=1, value=r.get("name")).font = Font(name="Arial", size=10)
        src.cell(row=n, column=2, value=r.get("source")).font = Font(name="Arial", size=10)
        src.cell(row=n, column=3, value=r.get("source_url")).font = Font(name="Arial", size=10)

    wb.save(path)
    reachable = sum(1 for r in rows if r.get("phone") or r.get("whatsapp"))
    print("  wrote %s" % path)
    print("  %d clinic(s), %d reachable by phone" % (len(rows), reachable))
    print("  Rows shaded red have no number yet.")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command",
                    choices=["import", "score", "cohorts", "status", "export", "why"])
    ap.add_argument("arg", nargs="?", default="")
    ap.add_argument("--strategy", default="spread", choices=["spread", "top"],
                    help="cohort fill order (default: spread)")
    a = ap.parse_args()

    app = create_app(Config)
    with app.app_context():
        conn = db.get_db()
        try:
            if a.command == "import":
                return cmd_import(conn, a.arg)
            if a.command == "score":
                return cmd_score(conn)
            if a.command == "cohorts":
                return cmd_cohorts(conn, a.strategy)
            if a.command == "status":
                return cmd_status(conn)
            if a.command == "export":
                return cmd_export(conn, a.arg or "market.xlsx")
            if a.command == "why":
                if not a.arg:
                    print("  why needs a clinic name")
                    return 2
                return cmd_why(conn, a.arg)
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
