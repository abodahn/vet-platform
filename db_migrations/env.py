"""Alembic environment for the Aleefy veterinary platform.

Two things make this env.py unusual, both forced by the codebase:

1. The database URL is derived from the *same* environment variables the Flask
   app reads, using the *same* DSN-validity test app.py applies. Alembic must
   never target a different database than the running app.

2. The project has no SQLAlchemy models. `init_db()` in models/database.py is
   the only description of the schema, so `--autogenerate` has nothing to point
   at. When ALEMBIC_AUTOGEN=1 we build the target MetaData by running init_db()
   against a throwaway SQLite file and reflecting it.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile

from alembic import context
from sqlalchemy import MetaData, create_engine, pool

HERE = os.path.dirname(os.path.abspath(__file__))
PLATFORM_ROOT = os.path.dirname(HERE)
if PLATFORM_ROOT not in sys.path:
    sys.path.insert(0, PLATFORM_ROOT)

config = context.config

# app.py only switches to PostgreSQL when the DSN matches this exact shape;
# anything else silently falls back to SQLite. Mirrored so alembic agrees.
_DSN_RE = re.compile(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)")


def database_url() -> str:
    """Same resolution order as app.create_app(): DSN, else PLATFORM_DB_PATH,
    else <platform>/data/platform.db."""
    dsn = os.environ.get("POSTGRES_DSN", "").strip()
    if dsn and _DSN_RE.match(dsn):
        return dsn
    path = os.environ.get("PLATFORM_DB_PATH") or os.path.join(
        PLATFORM_ROOT, "data", "platform.db"
    )
    return "sqlite:///" + os.path.abspath(path).replace("\\", "/")


def autogenerate_metadata():
    """Reflect a throwaway init_db() database as the autogenerate target.

    Only built when ALEMBIC_AUTOGEN=1, because it costs a full schema creation.
    Without it target_metadata is None and autogenerate produces an empty diff
    (alembic warns) — which is what you want for upgrade/downgrade/stamp runs.

    # ponytail: the reflected target is SQLite-flavoured, so autogenerate against
    # PostgreSQL reports type-affinity noise (TEXT vs VARCHAR, INTEGER vs BIGINT).
    # Ceiling: usable for structural drift (missing table / missing column /
    # missing index), not for type drift. Upgrade path: once init_db() stops
    # emitting DDL, replace this with hand-written MetaData in this file.
    """
    from models import database as db

    tmpdir = tempfile.mkdtemp(prefix="alembic_autogen_")
    probe = os.path.join(tmpdir, "reflect.db")
    db.set_path(probe)
    db.init_db(admin_user="alembic_probe", admin_pass="alembic_probe_not_a_login")

    md = MetaData()
    eng = create_engine("sqlite:///" + probe.replace("\\", "/"))
    md.reflect(bind=eng)
    eng.dispose()
    # alembic_version belongs to alembic, not to the app schema.
    if "alembic_version" in md.tables:
        md.remove(md.tables["alembic_version"])
    return md


target_metadata = (
    autogenerate_metadata() if os.environ.get("ALEMBIC_AUTOGEN") == "1" else None
)


def _configure_kwargs(url: str) -> dict:
    return dict(
        target_metadata=target_metadata,
        # SQLite cannot ALTER TABLE properly; batch mode rebuilds the table.
        render_as_batch=url.startswith("sqlite"),
        compare_type=True,
        compare_server_default=False,  # _fix_sql rewrites defaults per dialect
        include_object=lambda obj, name, type_, reflected, compare_to: name
        != "alembic_version",
    )


def run_migrations_offline() -> None:
    url = database_url()
    context.configure(url=url, literal_binds=True,
                      dialect_opts={"paramstyle": "named"},
                      **_configure_kwargs(url))
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = database_url()
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, **_configure_kwargs(url))
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
