# -*- coding: utf-8 -*-
"""Put the PROSPECT'S clinic name on the demo, before you walk in.

    python scripts/demo_brand.py --name-ar "عيادة النيل البيطرية" \
                                 --name "Nile Veterinary Clinic" \
                                 --doctor "د. أحمد سالم" --phone "01001234567"
    python scripts/demo_brand.py --reset

A vet looking at "عيادة أليفي التجريبية" is looking at somebody else's clinic.
The same screens with HIS clinic's name at the top of every page, on every
printed invoice and on the medical history PDF stop being a demonstration and
start being a preview. It costs one command and it is the cheapest thing in
this whole playbook.

Nothing else changes -- the 60 clients, the 393 visits, the overdue
vaccinations are all still synthetic, and the nightly 04:00 reset puts the
demo name back on its own. Re-run this before each meeting.

Only ever touches a clinic whose slug says demo/test/staging, so this can
never rename a real customer's clinic.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.database as db          # noqa: E402
from models import tenancy            # noqa: E402

DEMO_DEFAULTS = dict(
    name="Aleefy Veterinary Clinic",
    name_ar="عيادة أليفي التجريبية",
    doctor_name="Dr. Hossam Elmenshawy",
    phone="0226701234",
    address="12 Abbas El-Akkad St., Nasr City, Cairo",
    address_ar="١٢ شارع عباس العقاد، مدينة نصر، القاهرة",
)


def _guard(slug: str) -> None:
    """A rename is harmless; a rename of the wrong clinic is a support call
    from a customer whose system suddenly carries a stranger's name."""
    if not any(w in slug.lower() for w in ("demo", "test", "staging")):
        raise SystemExit(
            f"REFUSING to rebrand '{slug}': that is not a demo clinic.\n"
            "This command is for the sales demo only.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", default=os.environ.get("DEMO_SLUG", "demo"),
                   help="which clinic on this server (default: demo)")
    p.add_argument("--name-ar", help="the clinic's Arabic name — the one he reads")
    p.add_argument("--name", help="Latin name, for the English screens")
    p.add_argument("--doctor", help="his name, e.g. د. أحمد سالم")
    p.add_argument("--phone")
    p.add_argument("--address-ar")
    p.add_argument("--reset", action="store_true",
                   help="put the generic demo branding back")
    a = p.parse_args(argv)

    _guard(a.slug)

    fields = dict(DEMO_DEFAULTS) if a.reset else {}
    if not a.reset:
        if not (a.name_ar or a.name):
            p.error("give at least --name-ar (or --reset)")
        if a.name_ar:
            fields["name_ar"] = a.name_ar
            # The Latin column is what unlocalised screens fall back to, so
            # leaving it as "Aleefy Veterinary Clinic" puts the wrong clinic's
            # name on exactly the pages nobody thought to check.
            fields["name"] = a.name or a.name_ar
        elif a.name:
            fields["name"] = a.name
        if a.doctor:
            fields["doctor_name"] = a.doctor
        if a.phone:
            fields["phone"] = a.phone
        if a.address_ar:
            fields["address_ar"] = a.address_ar

    with tenancy.use(a.slug):
        conn = db.get_db()
        try:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE clinic SET {sets} WHERE id=1", tuple(fields.values()))
            conn.commit()
            row = conn.execute(
                "SELECT name, name_ar, doctor_name, phone FROM clinic WHERE id=1"
            ).fetchone()
        finally:
            conn.close()

    print()
    print("  The demo now reads:")
    print(f"    {row['name_ar']}")
    print(f"    {row['name']}  ·  {row['doctor_name']}  ·  {row['phone']}")
    print()
    print("  It goes back to the generic demo at 04:00, or run --reset now.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
