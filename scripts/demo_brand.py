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
    # Cleared on --reset. Otherwise the last prospect's logo is still sitting
    # at the top of the page when the next one walks in.
    logo_data="",
)


# 220px is the largest the header or a PDF ever draws it, and the column holds
# base64 inside the clinic ROW - see models/backup.py, which backs up the
# database and nothing else, so a logo on disk would not survive a restore.
_LOGO_PX = 220
_LOGO_MAX_BYTES = 400_000


def _logo_data_uri(path: str) -> str:
    """Read an image file and return a data: URI, or raise SystemExit saying why.

    Square-ish and small on purpose. A 4 MB phone photograph in this column is
    carried in every page render and every backup, and the header draws it at
    44 pixels regardless.
    """
    import base64
    import mimetypes

    if not os.path.isfile(path):
        raise SystemExit("No such file: %s" % path)
    try:
        from PIL import Image
    except ImportError:
        # Without Pillow, pass the bytes through unchanged rather than refuse -
        # but only if they are already small enough to belong in a row.
        raw = open(path, "rb").read()
        if len(raw) > _LOGO_MAX_BYTES:
            raise SystemExit(
                "%s is %d KB and Pillow is not installed to shrink it. "
                "Install Pillow, or resize it to about %dpx first."
                % (path, len(raw) // 1024, _LOGO_PX))
        mime = mimetypes.guess_type(path)[0] or "image/png"
        return "data:%s;base64,%s" % (mime, base64.b64encode(raw).decode())

    import io as _io
    try:
        im = Image.open(path)
    except Exception as exc:
        raise SystemExit("Could not read %s as an image: %s" % (path, exc))
    im = im.convert("RGBA")
    im.thumbnail((_LOGO_PX, _LOGO_PX), Image.LANCZOS)
    buf = _io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    raw = buf.getvalue()
    if len(raw) > _LOGO_MAX_BYTES:
        raise SystemExit("That logo is still %d KB after resizing." % (len(raw) // 1024))
    return "data:image/png;base64,%s" % base64.b64encode(raw).decode()


def _configure_registry() -> None:
    """Point tenancy where create_app() points it.

    models.tenancy keeps the registry path in a module global that ONLY
    create_app() sets, and a CLI script never builds an app -- so without this
    every run dies with UnknownTenant on a server where the clinic plainly
    exists. scripts/preflight.py had the identical bug. Derived the same way
    add_clinic.py derives it, so the three agree.
    """
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
    p.add_argument("--logo", metavar="PATH",
                   help="their logo, as an image file. Resized and stored in "
                        "the clinic row, so it survives a restore.")
    p.add_argument("--reset", action="store_true",
                   help="put the generic demo branding back")
    a = p.parse_args(argv)

    _guard(a.slug)
    _configure_registry()

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
        if a.logo:
            fields["logo_data"] = _logo_data_uri(a.logo)

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
