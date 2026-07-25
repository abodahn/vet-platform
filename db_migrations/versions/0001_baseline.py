"""baseline — the schema exactly as it exists today

This revision is a *faithful photograph*, not a redesign. It replays the frozen
snapshot in 0001_baseline.sql, which is models/database.py:_SCHEMA verbatim plus
the ad-hoc ALTERs init_db() applies immediately after it (visits.soap_*,
owners.loyalty_balance, pets.insurance_*, imaging_studies).

Existing databases must be STAMPED, not upgraded:
    alembic -c db_migrations/alembic.ini stamp 0001_baseline
See MIGRATIONS.md.

Revision ID: 0001_baseline
Revises:
"""

import os
import re

from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_SQL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "0001_baseline.sql")

# Same naive comment-strip + semicolon split that _PGConn.executescript() uses
# (models/database.py ~304). Deliberately identical so the baseline reproduces
# exactly what the app produces — including the shared limitation.
# ponytail: splitting DDL on a bare ';' breaks if a future statement embeds one
# in a string literal or a trigger body. Ceiling: no triggers/functions in this
# schema today. Upgrade path: sqlparse.split() if that ever changes.
_COMMENT_RE = re.compile(r"--[^\n]*")


def _statements(is_postgres: bool):
    with open(_SQL_FILE, encoding="utf-8") as fh:
        raw = _COMMENT_RE.sub("", fh.read())
    if is_postgres:
        # The snapshot is written in the app's SQLite dialect; translate it with
        # the app's own translator so the PostgreSQL result is byte-identical to
        # what init_db() would have produced.
        from models.database import _fix_sql
    for stmt in raw.split(";"):
        stmt = stmt.strip()
        if stmt:
            yield _fix_sql(stmt) if is_postgres else stmt


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    for stmt in _statements(is_pg):
        # exec_driver_sql, not op.execute(): op.execute() wraps strings in
        # sqlalchemy.text(), which would try to parse ':' as a bind parameter.
        bind.exec_driver_sql(stmt)


def downgrade() -> None:
    raise RuntimeError(
        "0001_baseline cannot be downgraded — the only 'down' from the baseline "
        "is an empty database, i.e. dropping every patient record in the system. "
        "Restore from a backup instead (platform/backups/). See MIGRATIONS.md."
    )
