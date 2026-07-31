# -*- coding: utf-8 -*-
"""Create a new clinic: registry row + its own database + its first admin.

Kept separate from models/tenancy.py so that module stays a pure registry a
test can drive on its own without building a 74-table schema every time.
"""
import logging
import os

import models.database as db
from models import tenancy

logger = logging.getLogger(__name__)


def provision(slug: str, name: str, admin_user: str, admin_pass: str,
              *, db_dir: str = "", pg_dsn: str = "") -> dict:
    """Register a clinic and build its schema. Returns the registry row.

    Rolls the registry row back if the schema build fails. A half-provisioned
    tenant is worse than none: the subdomain would resolve, the clinic would
    reach a login page, and every query behind it would fail on a database with
    no tables.
    """
    if not admin_pass or len(admin_pass) < 8:
        # This is the account that owns a clinic's entire medical record.
        raise ValueError("the first admin password must be at least 8 characters")

    db_dir = db_dir or _default_db_dir()
    if not pg_dsn:
        os.makedirs(db_dir, exist_ok=True)

    row = tenancy.create(slug, name, db_dir=db_dir, pg_dsn=pg_dsn)
    try:
        with tenancy.use(slug):
            db.init_db(admin_user, admin_pass)
            # The clinic row carries the name shown in the UI, the PDF header
            # and the installed PWA icon. Without this every new clinic would
            # come up branded as whatever the schema's placeholder is.
            conn = db.get_db()
            with conn:
                conn.execute("UPDATE clinic SET name=?", (name,))
            conn.close()
    except Exception:
        logger.exception("provisioning %s failed — rolling back the registry", slug)
        _rollback(slug, row)
        raise
    logger.info("tenant provisioned: %s (%s)", slug, name)
    return tenancy.get(slug)


def _rollback(slug: str, row: dict) -> None:
    try:
        with tenancy._lock, tenancy._registry() as conn:
            conn.execute("DELETE FROM tenants WHERE slug=?", (slug,))
            conn.commit()
    except Exception:
        logger.exception("could not roll back the registry row for %s", slug)
    path = (row or {}).get("db_path")
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            # Windows keeps a handle open until the connection is collected;
            # a stale file is harmless because the registry row is gone.
            logger.warning("left a partial database behind at %s", path)


def _default_db_dir() -> str:
    """Tenant databases sit next to the single-tenant one."""
    base = os.path.dirname(db._db_path) or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
    return os.path.join(base, "tenants")
