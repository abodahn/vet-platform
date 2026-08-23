# -*- coding: utf-8 -*-
"""Fill today's appointment board on a demo, without reseeding.

    python scripts/demo_topup_today.py --slug demo
    python scripts/demo_topup_today.py --slug demo --count 8 --apply

The first screen anyone opens is the diary. A demo seeded three weeks ago has
nothing on today, and an empty board does not read as a quiet day - it reads as
software that does not work. That impression is formed in the first fifteen
seconds and it is not recovered.

Reseeding fixes it and throws away everything else: the branding you set for
this prospect, any record you created while showing somebody around. This only
adds appointments, to today, from clients and patients that already exist.

Idempotent. It counts what today already has and tops up to --count, so running
it twice does not produce sixteen appointments. Run it the morning of a demo.

Only ever touches a clinic whose slug says demo/test/staging, so it can never
invent appointments in a real clinic's diary.
"""
import argparse
import os
import random
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
logging.disable(logging.CRITICAL)

import models.database as db          # noqa: E402
from models import tenancy            # noqa: E402

# A believable clinic morning, not a wall of identical 30-minute slots.
_TYPES = [
    ("Consultation", "كشف", 30, "Normal"),
    ("Vaccination", "تطعيم", 20, "Normal"),
    ("Follow-up", "متابعة", 20, "Normal"),
    ("Surgery", "جراحة", 90, "High"),
    ("Grooming", "تجميل", 45, "Normal"),
    ("Dental", "أسنان", 60, "Normal"),
    ("Emergency", "طوارئ", 30, "Urgent"),
]

_REASONS = [
    "Vomiting since yesterday", "Annual vaccination", "Limping on the left hind",
    "Post-operative check", "Skin irritation", "Not eating for two days",
    "Ear infection follow-up", "Routine check-up", "Nail trim and wash",
    "Dental scaling", "Wound dressing change", "Weight check",
]

# The clinic day. Deliberately not starting at 00:00 - a board full of 3am
# appointments is worse than an empty one.
_DAY_START = 9
_DAY_END = 19


def _configure_registry() -> None:
    """Same derivation as demo_brand.py and add_clinic.py, for the same reason:
    tenancy keeps its registry path in a module global that only create_app()
    sets, and a CLI script never builds an app."""
    if tenancy._registry_path:
        return
    env = os.environ.get("TENANT_REGISTRY", "").strip()
    if env:
        tenancy.configure(env)
        return
    from config import Config
    tenancy.configure(os.path.join(
        os.path.dirname(Config.DATABASE_PATH) or ".", "tenants.db"))


def _guard(slug: str) -> None:
    if not any(w in (slug or "").lower() for w in ("demo", "test", "staging")):
        raise SystemExit(
            "REFUSING to add appointments to '%s': that is not a demo clinic.\n"
            "This command invents patient appointments. It is for the sales "
            "demo only." % slug)


def _pairs(conn, want):
    """(owner_id, pet_id, pet_name, owner_name) for real pets in this clinic."""
    rows = conn.execute(
        "SELECT p.id AS pet_id, p.owner_id, p.pet_name, o.full_name"
        "  FROM pets p JOIN owners o ON o.id = p.owner_id"
        " ORDER BY RANDOM() LIMIT ?", (want * 3,)).fetchall()
    return [dict(r) for r in rows]


def _doctors(conn):
    rows = conn.execute(
        "SELECT id, full_name FROM users"
        " WHERE role='doctor' AND is_active=1").fetchall()
    return [dict(r) for r in rows] or [{"id": None, "full_name": "Dr. On Duty"}]


def _run(conn, count, apply_it):
    today = date.today().isoformat()
    have = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE appt_date=?", (today,)).fetchone()[0]

    print("  today            : %s" % today)
    print("  already booked   : %d" % have)
    print("  target           : %d" % count)

    if have >= count:
        print("")
        print("  Nothing to add. The board already looks like a working day.")
        return 0

    need = count - have
    pairs = _pairs(conn, need)
    if not pairs:
        print("")
        print("  No pets in this clinic to book. Seed it first.")
        return 1

    docs = _doctors(conn)
    rnd = random.Random()          # not seeded: two runs should not collide

    # Spread across the day rather than stacking from 09:00, and avoid times
    # already taken so the board does not show two things at once.
    taken = {r[0] for r in conn.execute(
        "SELECT appt_start FROM appointments WHERE appt_date=?", (today,)).fetchall()}
    slots = []
    for hour in range(_DAY_START, _DAY_END):
        for minute in (0, 30):
            t = "%02d:%02d" % (hour, minute)
            if t not in taken:
                slots.append(t)
    rnd.shuffle(slots)

    planned = []
    for i in range(min(need, len(slots), len(pairs))):
        pair = pairs[i]
        kind, kind_ar, mins, priority = rnd.choice(_TYPES)
        doc = rnd.choice(docs)
        start = slots[i]
        end = (datetime.strptime(start, "%H:%M") + timedelta(minutes=mins)).strftime("%H:%M")
        # Earlier slots are likelier to have happened already - a board where
        # nothing has been seen yet at 4pm looks abandoned.
        hour = int(start[:2])
        status = "Completed" if hour < 12 else ("Arrived" if hour < 15 else "Scheduled")
        planned.append({
            "owner_id": pair["owner_id"], "pet_id": pair["pet_id"],
            "doctor_id": doc["id"], "doctor_name": doc["full_name"],
            "appointment_type": kind, "priority": priority, "status": status,
            "appt_date": today, "appt_start": start, "appt_end": end,
            "duration_min": mins, "reason": rnd.choice(_REASONS),
            "channel": rnd.choice(["Walk-in", "Phone", "WhatsApp"]),
            "pet_name": pair["pet_name"], "owner_name": pair["full_name"],
        })

    planned.sort(key=lambda a: a["appt_start"])
    print("")
    print("    %-6s %-10s %-16s %-22s %s"
          % ("time", "type", "patient", "client", "status"))
    for a in planned:
        print("    %-6s %-10s %-16s %-22s %s"
              % (a["appt_start"], a["appointment_type"],
                 (a["pet_name"] or "")[:16], (a["owner_name"] or "")[:22],
                 a["status"]))

    if not apply_it:
        print("")
        print("  Re-run with --apply to book them. Nothing has been changed.")
        return 0

    for a in planned:
        conn.execute(
            "INSERT INTO appointments (owner_id, pet_id, doctor_id, doctor_name,"
            " appointment_type, priority, status, channel, appt_date, appt_start,"
            " appt_end, duration_min, reason)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (a["owner_id"], a["pet_id"], a["doctor_id"], a["doctor_name"],
             a["appointment_type"], a["priority"], a["status"], a["channel"],
             a["appt_date"], a["appt_start"], a["appt_end"], a["duration_min"],
             a["reason"]))
    conn.commit()
    print("")
    print("  Booked %d. Today's board now shows %d." % (len(planned), have + len(planned)))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", default=os.environ.get("DEMO_SLUG", "demo"),
                   help="which clinic on this server (default: demo)")
    p.add_argument("--count", type=int, default=8,
                   help="how many appointments today should have (default: 8)")
    p.add_argument("--apply", action="store_true",
                   help="actually book them (default: show only)")
    a = p.parse_args(argv)

    _guard(a.slug)
    _configure_registry()

    print("Clinic %s:" % a.slug)
    with tenancy.use(a.slug):
        conn = db.get_db()
        try:
            return _run(conn, a.count, a.apply)
        finally:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
