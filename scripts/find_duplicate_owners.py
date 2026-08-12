# -*- coding: utf-8 -*-
"""Clients who share a mobile number, so they can be merged deliberately.

New records are refused a mobile that already belongs to somebody else
(models.database.assert_phone_is_free). That rule cannot be a UNIQUE index
because a real database already contains duplicates — adding a constraint over
them fails at startup and takes the clinic down. This lists what is already
there so a human can decide which record survives.

    python scripts/find_duplicate_owners.py

Read-only. It never merges anything: merging decides whose pets, invoices and
history win, and that is not a script's call.
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

from app import create_app          # noqa: E402
from config import Config           # noqa: E402
from models import database as db   # noqa: E402


def main():
    app = create_app(Config)
    with app.app_context():
        conn = db.get_db()
        owners = conn.execute(
            "SELECT id, full_name, phone, whatsapp_phone, created_at"
            " FROM owners ORDER BY id").fetchall()

        groups = defaultdict(list)
        for o in owners:
            key = db.normalise_phone(o["phone"]) or db.normalise_phone(o["whatsapp_phone"])
            if key:
                groups[key].append(dict(o))

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        if not dupes:
            print("No two clients share a mobile number.")
            conn.close()
            return 0

        print("%d mobile number(s) held by more than one client.\n" % len(dupes))
        for key, rows in sorted(dupes.items(), key=lambda kv: -len(kv[1])):
            print("+%s" % key)
            for o in rows:
                pets = conn.execute(
                    "SELECT COUNT(*) FROM pets WHERE owner_id=? AND is_active=1",
                    (o["id"],)).fetchone()[0]
                visits = conn.execute(
                    "SELECT COUNT(*) FROM visits WHERE owner_id=?",
                    (o["id"],)).fetchone()[0]
                owed = conn.execute(
                    "SELECT COALESCE(SUM(due_amount),0) FROM invoices"
                    " WHERE owner_id=? AND status IN ('Unpaid','Partial')",
                    (o["id"],)).fetchone()[0]
                print("    #%-6s %-28s %2d pet(s)  %3d visit(s)  %8.2f owed  since %s"
                      % (o["id"], (o["full_name"] or "")[:28], pets, visits,
                         float(owed or 0), (o["created_at"] or "")[:10]))
            print()

        print("Merge by hand: pick the record to keep, move the other's pets to "
              "it (CRM > pet > change owner), settle or reassign its invoices, "
              "then clear the losing record's phone so the pair stops colliding.")
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
