# -*- coding: utf-8 -*-
"""Create a clinic. The entry point that did not exist.

models/provisioning.py has been able to do this for a while, but nothing except
the test suite could reach it -- so "add a clinic" meant opening a Python shell
and importing internals correctly. That is not a thing to be doing on a live
server at 9pm with a clinic waiting.

    python scripts/add_clinic.py --slug nilevet --name "Nile Vet Clinic"
    python scripts/add_clinic.py --slug nilevet --name "Nile Vet" --postgres "$POSTGRES_DSN"
    python scripts/add_clinic.py --list

The password is generated and printed ONCE, to the terminal. It is never
written to a file and never logged: a credential in a log is a credential in
every backup of that log.

Slug rules are the tenancy module's, not this script's -- the slug becomes a
subdomain (nilevet.aleefy.online), so it has to survive DNS.
"""
import argparse
import os
import secrets
import string
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models.database as db          # noqa: E402
from models import provisioning, tenancy  # noqa: E402


def _password(n: int = 16) -> str:
    """Generated, not chosen. The first admin owns the clinic's whole medical
    record, and a human choosing under time pressure picks something weak."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_"
    return "".join(secrets.choice(alphabet) for _ in range(n))


def _configure_registry(registry: str) -> None:
    """Point at a registry only when one was actually named.

    tenancy.configure("") CLEARS the registry, so calling it unconditionally
    would wipe whatever the process had already been given -- which is exactly
    what you do not want a clinic-creation command to do on the way in.
    """
    if registry:
        tenancy.configure(registry)
        return
    if tenancy._registry_path:
        return
    # Standalone run with nothing configured. The default MUST be derived the
    # same way create_app() derives it -- next to DATABASE_PATH -- or the two
    # disagree the moment PLATFORM_DB_PATH is set, which it always is in
    # production. The clinic would be written into a registry the server never
    # reads, the subdomain would not resolve, and nothing would say why.
    from config import Config
    tenancy.configure(os.path.join(
        os.path.dirname(Config.DATABASE_PATH) or ".", "tenants.db"))


def cmd_list() -> int:
    rows = tenancy.all_tenants(active_only=False)
    if not rows:
        print("No clinics registered yet.")
        return 0
    width = max(len(r["slug"]) for r in rows)
    print(f"{'SLUG'.ljust(width)}  {'STATUS'.ljust(9)}  NAME")
    for r in rows:
        status = "active" if r.get("is_active", 1) else "suspended"
        print(f"{r['slug'].ljust(width)}  {status.ljust(9)}  {r.get('name','')}")
    return 0


def cmd_add(args) -> int:
    existing = tenancy.get(args.slug)
    if existing:
        # Refused, never overwritten: re-provisioning would rebuild the schema
        # over a clinic's live records.
        print(f"ERROR: '{args.slug}' already exists ({existing.get('name','')}).",
              file=sys.stderr)
        print("       Pick another slug, or remove it deliberately first.",
              file=sys.stderr)
        return 1

    password = args.admin_pass or _password()
    try:
        row = provisioning.provision(
            args.slug, args.name, args.admin_user, password,
            db_dir=args.db_dir, pg_dsn=args.postgres,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # provision() already rolled the registry back, so the operator is not
        # left with a half-made clinic; say so, because "it failed" and "it
        # failed and left something behind" need different next steps.
        print(f"ERROR: provisioning failed and was rolled back: {exc}",
              file=sys.stderr)
        return 1

    where = args.postgres or row.get("db_path", "")
    print()
    print("  Clinic created.")
    print()
    print(f"    Name      : {args.name}")
    print(f"    Slug      : {args.slug}")
    print(f"    Database  : {where}")
    print(f"    Sign in as: {args.admin_user}")
    print(f"    Password  : {password}")
    print()
    print("  This password is shown once and is not stored anywhere.")
    print("  Give it to the clinic owner and have them change it at first login.")
    print()
    if args.domain:
        print(f"    URL       : https://{args.slug}.{args.domain}")
        print(f"  Point DNS at this server and issue a certificate before handing it over:")
        print(f"    sudo certbot --nginx -d {args.slug}.{args.domain}")
        print()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Create a clinic on this deployment.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--slug", help="subdomain-safe id, e.g. nilevet")
    p.add_argument("--name", help='display name, e.g. "Nile Vet Clinic"')
    p.add_argument("--admin-user", default="admin", help="first admin username")
    p.add_argument("--admin-pass", default="",
                   help="leave unset to generate a strong one (recommended)")
    p.add_argument("--postgres", default="",
                   help="DSN for this clinic's PostgreSQL database; omit for SQLite")
    p.add_argument("--db-dir", default="",
                   help="where SQLite tenant databases live (default: data/tenants)")
    p.add_argument("--registry", default=os.environ.get("TENANT_REGISTRY", ""),
                   help="tenant registry path (default: $TENANT_REGISTRY)")
    p.add_argument("--domain", default=os.environ.get("PLATFORM_DOMAIN", ""),
                   help="base domain, to print the clinic URL and certbot line")
    p.add_argument("--list", action="store_true", help="list existing clinics and exit")
    args = p.parse_args(argv)

    _configure_registry(args.registry)

    if args.list:
        return cmd_list()
    if not args.slug or not args.name:
        p.error("--slug and --name are required (or use --list)")
    return cmd_add(args)


if __name__ == "__main__":
    raise SystemExit(main())
