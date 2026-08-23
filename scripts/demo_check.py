# -*- coding: utf-8 -*-
"""Will this demo embarrass you in front of a vet?

    python scripts/demo_check.py --tenant demo

A different question from scripts/preflight.py, which asks whether a deployment
is SAFE to hand to a clinic - secrets, passwords, cookies, backups. This asks
whether it will hold up in a room, with a clinic owner watching, on the twenty
minutes you get.

It checks the machine-checkable half of the pre-demo list in
docs/sales-kit/03_DEMO_SCRIPT.md, so the document and this script cannot drift.
The rest of that list - phone charged, hotspot ready, browser full screen - is
yours.

Exits 0 when nothing is FAIL. Warnings do not block: each is something a vet
might notice, not something that will stop the demo.

Read-only. It changes nothing.
"""
import argparse
import os
import re
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402

OK, WARN, FAIL = "ok  ", "WARN", "FAIL"
_results = []


def report(level, title, detail=""):
    _results.append((level, title, detail))


# ── the checks ───────────────────────────────────────────────────────────────

def check_clinic_identity(conn):
    """A demo that prints somebody else's name on the invoice is over before
    it starts. The vet is deciding whether this is THEIR system."""
    clinic = db.get_clinic() or {}
    name = (clinic.get("name") or "").strip()
    if not name:
        return report(FAIL, "Clinic name is empty",
                      "Settings -> Clinic. It prints on every invoice.")
    if name.lower() in ("aleefy", "animal hospital", "premium animal hospital"):
        return report(FAIL, "Clinic name is still the vendor default: %r" % name,
                      "Set it to the clinic you are showing this to. This is the "
                      "single most visible thing in the whole demo.")
    report(OK, "Clinic name: %s" % name)

    if not (clinic.get("phone") or "").strip():
        report(WARN, "No clinic phone number",
               "It prints on invoices and receipts, and its absence is noticed.")
    if not (clinic.get("logo_data") or "").strip():
        report(WARN, "No clinic logo",
               "The header of every printed document looks unfinished without it.")


def check_todays_board(conn):
    """The first screen anyone opens. An empty diary reads as broken software,
    not as a quiet day."""
    n = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE appt_date = ?",
        (date.today().isoformat(),)).fetchone()[0]
    if n == 0:
        report(FAIL, "Today's appointment board is EMPTY",
               "Re-seed, or book a few for today. This is the first screen a "
               "vet sees and an empty one ends the demo in the first minute.")
    elif n < 3:
        report(WARN, "Only %d appointment(s) today" % n,
               "A believable clinic day is 5 or more.")
    else:
        report(OK, "Today's board has %d appointment(s)" % n)


def check_it_looks_like_a_real_clinic(conn):
    """Three owners and one pet is a database, not a clinic."""
    for table, label, floor in (("owners", "clients", 40),
                                ("pets", "patients", 60),
                                ("invoices", "invoices", 50)):
        try:
            n = conn.execute("SELECT COUNT(*) FROM %s" % table).fetchone()[0]
        except Exception:
            report(WARN, "Could not count %s" % label)
            continue
        if n < floor // 4:
            report(FAIL, "Only %d %s" % (n, label),
                   "This looks like a test database, not a working clinic.")
        elif n < floor:
            report(WARN, "%d %s (thin)" % (n, label))
        else:
            report(OK, "%d %s" % (n, label))


def check_prices_look_egyptian(conn):
    """Every service priced at a round 100/200/300 reads as placeholder data,
    and a clinic owner prices things for a living - they notice immediately."""
    try:
        rows = conn.execute(
            "SELECT standard_price FROM service_catalog"
            " WHERE standard_price IS NOT NULL AND standard_price > 0").fetchall()
    except Exception:
        return report(WARN, "No service catalogue to check")
    prices = [float(r[0]) for r in rows]
    if not prices:
        return report(FAIL, "No priced services",
                      "The exam screen will show nothing to charge for.")
    round_ones = sum(1 for p in prices if p % 50 == 0)
    if round_ones == len(prices) and len(prices) > 4:
        report(WARN, "All %d service prices are round numbers" % len(prices),
               "150, 300, 450 everywhere reads as placeholder data. Vary a few.")
    else:
        report(OK, "%d services priced" % len(prices))


def check_whatsapp(conn):
    """The feature a vet asks to see first, and the one most likely to
    embarrass you live."""
    try:
        rows = dict(conn.execute(
            "SELECT key, value FROM settings WHERE category='wapilot'").fetchall())
    except Exception:
        rows = {}
    token = (rows.get("wapilot_token") or os.environ.get("WAPILOT_TOKEN", "")).strip()
    iid = (rows.get("wapilot_instance_id")
           or os.environ.get("WAPILOT_INSTANCE", "")).strip()
    if not token or not iid:
        return report(FAIL, "WhatsApp is not connected",
                      "Settings -> WhatsApp. Credentials from wapilot.net, then "
                      "scan the QR. DO NOT demo the reminder feature until you "
                      "have sent one real message to your own phone.")
    report(OK, "WhatsApp credentials are configured",
           "Still send yourself one real message before demoing it.")


def check_no_published_password(conn):
    """A vet will not type a password in front of you, but a technical buyer
    will look, and these are on GitHub."""
    from scripts.rotate_demo_passwords import LEAKED, PROTECTED_USERNAMES
    rows = conn.execute("SELECT username FROM users").fetchall()
    hits = []
    for r in rows:
        u = r[0]
        if u in PROTECTED_USERNAMES:
            continue
        for pw in LEAKED:
            if db.verify_credentials(u, pw):
                hits.append(u)
                break
    if hits:
        report(FAIL, "%d account(s) still open with a published password" % len(hits),
               "python scripts/rotate_demo_passwords.py --tenant <slug> --apply --same "
               "--out <file>. These are in the public repository.")
    else:
        report(OK, "No account opens with a published password")


def check_cds_is_marked(conn):
    """It ships DRAFT and unreviewed. If it is demoed as a finished clinical
    feature, that is a liability, not a sale."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tpl = os.path.join(root, "templates", "cds", "index.html")
    try:
        body = open(tpl, encoding="utf-8").read()
    except OSError:
        return report(WARN, "Could not read the CDS template")
    if "not reviewed by a licensed" not in body:
        report(FAIL, "The CDS module does not warn that it is unreviewed",
               "Its rule set ships DRAFT. Do not demo it.")
    else:
        report(OK, "CDS carries its DRAFT warning",
               "Still keep it out of the demo until a vet has signed off the rules.")


def check_arabic_pdf(conn):
    """Arabic inside a generated PDF is where competing systems break, and it
    is the ten seconds of the demo that convinces people. Prove it renders
    BEFORE you are standing in the room."""
    try:
        from models.pdf_generator import generate_invoice_pdf
    except Exception as exc:
        return report(WARN, "PDF generator unavailable: %s" % exc)
    row = conn.execute(
        "SELECT id FROM invoices ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return report(WARN, "No invoice to render")
    try:
        inv = db.get_invoice(row[0])
        pdf = generate_invoice_pdf(inv, db.get_clinic())
        if not pdf or len(pdf) < 800:
            report(FAIL, "The invoice PDF came back empty")
        else:
            report(OK, "Invoice PDF renders (%d KB)" % (len(pdf) // 1024),
                   "Print one on paper before the meeting anyway.")
    except Exception as exc:
        report(FAIL, "The invoice PDF FAILED to render: %s" % exc,
               "This is the ten seconds that convinces people. Fix it first.")


def check_language(conn):
    lang = os.environ.get("PLATFORM_DEFAULT_LANG", "en")
    if lang != "ar":
        report(WARN, "Default language is %r, not Arabic" % lang,
               "PLATFORM_DEFAULT_LANG=ar. An Egyptian vet should not have to "
               "find the language switch to see the thing you are selling.")
    else:
        report(OK, "Default language is Arabic")


CHECKS = [
    check_clinic_identity,
    check_todays_board,
    check_it_looks_like_a_real_clinic,
    check_prices_look_egyptian,
    check_whatsapp,
    check_no_published_password,
    check_cds_is_marked,
    check_arabic_pdf,
    check_language,
]


def run(conn):
    for fn in CHECKS:
        try:
            fn(conn)
        except Exception as exc:
            report(WARN, "%s could not run" % fn.__name__, str(exc)[:90])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tenant", default="", help="clinic slug, or 'all'")
    args = ap.parse_args()

    app = create_app(Config)
    with app.app_context():
        from models import tenancy
        registered = [t.get("slug") for t in tenancy.all_tenants()]
        if registered and not args.tenant:
            print("This deployment has %d clinic(s):" % len(registered))
            for s in registered:
                print("   %s" % s)
            print("\nName one with --tenant <slug>.")
            return 2

        targets = registered if args.tenant == "all" else (
            [args.tenant] if args.tenant else [None])

        for slug in targets:
            print("=" * 66)
            print("DEMO READINESS - %s" % (slug or "default database"))
            print("=" * 66)
            _results.clear()
            if slug is None:
                conn = db.get_db()
                try:
                    run(conn)
                finally:
                    conn.close()
            else:
                with tenancy.use(slug):
                    conn = db.get_db()
                    try:
                        run(conn)
                    finally:
                        conn.close()

            for level, title, detail in _results:
                print("  [%s] %s" % (level, title))
                if detail:
                    for line in _wrap(detail, 62):
                        print("         %s" % line)

            fails = sum(1 for l, _, _ in _results if l == FAIL)
            warns = sum(1 for l, _, _ in _results if l == WARN)
            print("")
            if fails:
                print("  %d FAIL, %d warning(s). Do not demo until the FAILs are clear."
                      % (fails, warns))
            elif warns:
                print("  0 FAIL, %d warning(s). Demoable - each warning is something "
                      "a vet might notice." % warns)
            else:
                print("  Everything checkable is ready.")
            print("")
            print("  Not checkable from here, and still on you:")
            print("    - their own data loaded before the meeting")
            print("    - one real WhatsApp message sent to your own phone")
            print("    - an invoice printed on actual paper")
            print("    - phone charged, hotspot ready, browser full screen")
            print("")
            if fails:
                return 1
    return 0


def _wrap(text, width):
    words, line, out = text.split(), "", []
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    if line:
        out.append(line)
    return out


if __name__ == "__main__":
    sys.exit(main())
