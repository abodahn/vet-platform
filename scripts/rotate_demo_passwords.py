# -*- coding: utf-8 -*-
"""Rotate any account still using a password that has been published.

WHY

Demo@1234 is in this repository's history and in docs/AUDIT_FINDINGS.md, which
is a file written to be handed to buyers. Scrubbing a file does not undo that:
git keeps the old blob and any fork keeps a copy. The only real remedy for a
published password is to stop it opening anything.

The highest privilege observed on these accounts is clinic_owner - which can
read the whole clinic's records, its finances and its clients. That is enough
to matter.

WHAT IT DOES

Tries each known-leaked password against every account. Where one opens an
account, that account gets a fresh random password. Accounts that do not use a
leaked password are not touched.

    python scripts/rotate_demo_passwords.py --tenant demo
    python scripts/rotate_demo_passwords.py --tenant demo --apply

Without --apply nothing is written: it lists what would change.

WITH --apply it writes the new passwords to a file YOU name, because a demo
account nobody can sign into is not a demo. Print it, put it in a password
manager, then delete the file. It never goes to stdout, so it cannot end up in
a terminal scrollback or a screen share.

The admin account is deliberately EXCLUDED. It has already been rotated to a
password chosen by the owner, and re-rotating it here would lock them out of
their own system without warning.
"""
import argparse
import io
import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402

# Every password known to have been published. A new one joins this list the
# day it leaks, not the day somebody remembers.
LEAKED = ["Demo@1234", "Ahmed@1122", "Aleefy@Demo2026", "1234", "demo", "admin"]

# Never rotated here. The owner chose this one and uses it.
PROTECTED_USERNAMES = {"admin"}

_ALPHABET = string.ascii_letters + string.digits


def _new_password() -> str:
    """Readable enough to type off paper, strong enough to matter."""
    body = "".join(secrets.choice(_ALPHABET) for _ in range(10))
    return "Aleefy-%s!" % body


def _run(conn, apply_it, out_path):
    rows = [dict(r) for r in conn.execute(
        "SELECT id, username, full_name, role, is_active FROM users"
        " ORDER BY role, username").fetchall()]

    affected = []
    for r in rows:
        if r["username"] in PROTECTED_USERNAMES:
            continue
        for pw in LEAKED:
            user = db.verify_credentials(r["username"], pw)
            if user:
                affected.append((r, pw))
                break

    print("  accounts            : %d" % len(rows))
    print("  opened by a leaked password : %d" % len(affected))
    if not affected:
        print("")
        print("  Nothing to rotate. No account is opened by a published password.")
        return 0

    print("")
    print("    %-20s %-18s %s" % ("username", "role", "opened by"))
    for r, pw in affected:
        print("    %-20s %-18s %s"
              % (r["username"], r["role"] or "-", pw))

    roles = sorted({(r["role"] or "-") for r, _ in affected})
    print("")
    print("  highest privilege exposed: %s" % max(roles, key=lambda x: (
        x == "super_admin", x == "clinic_owner", x == "branch_manager")))

    if not apply_it:
        print("")
        print("  Re-run with --apply to rotate them. Nothing has been changed.")
        return 0

    if not out_path:
        print("")
        print("  --apply needs --out <file> for the new passwords. A demo account")
        print("  nobody can sign into is not a demo.")
        return 2

    lines = ["Aleefy demo accounts - rotated passwords",
             "PRINT THIS, STORE IT, THEN DELETE THIS FILE.",
             ""]
    for r, _pw in affected:
        new = _new_password()
        conn.execute("UPDATE users SET password_hash=? WHERE id=?",
                     (db._hash_password(new), r["id"]))
        lines.append("%-20s %-18s %s"
                     % (r["username"], r["role"] or "-", new))
    conn.commit()

    io.open(out_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("")
    print("  rotated %d account(s)" % len(affected))
    print("  new passwords written to %s" % out_path)
    print("  They were NOT printed here, so they are not in your scrollback.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="write the new passwords (default: show only)")
    ap.add_argument("--tenant", default="",
                    help="clinic slug on a multi-clinic deployment, or 'all'")
    ap.add_argument("--out", default="",
                    help="file to write the new passwords to (required with --apply)")
    args = ap.parse_args()

    app = create_app(Config)
    with app.app_context():
        from models import tenancy
        registered = [t.get("slug") for t in tenancy.all_tenants()]

        if registered and not args.tenant:
            print("This deployment has %d clinic(s):" % len(registered))
            for s in registered:
                print("   %s" % s)
            print("")
            print("Name one with --tenant <slug>, or --tenant all.")
            return 2
        if args.tenant and args.tenant != "all" and args.tenant not in registered:
            print("No clinic registered as %r." % args.tenant)
            return 2

        targets = registered if args.tenant == "all" else (
            [args.tenant] if args.tenant else [None])

        rc = 0
        for slug in targets:
            print("Clinic %s:" % (slug or "(default database)"))
            if slug is None:
                conn = db.get_db()
                try:
                    rc |= _run(conn, args.apply, args.out)
                finally:
                    conn.close()
            else:
                with tenancy.use(slug):
                    conn = db.get_db()
                    try:
                        rc |= _run(conn, args.apply, args.out)
                    finally:
                        conn.close()
            print("")
        return rc


if __name__ == "__main__":
    sys.exit(main())
