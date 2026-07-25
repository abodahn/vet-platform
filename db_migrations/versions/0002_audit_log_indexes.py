"""audit_log indexes for the filtered, paginated audit view

`audit_log` is the live audit table, and nothing in the codebase indexes it —
`models/database.py` creates the table bare, while its dead sibling `audit_logs`
got four indexes. Any fresh install therefore has none. That was survivable
while the audit page did an unfiltered `LIMIT 200`. It is not survivable now
that the page filters by user / module / action / date / affected record and
pages through the whole table: every page load would be a sequential scan plus a
sort of every audit row ever written, and field-level change auditing makes that
table grow much faster than auth-only logging did.

Schema drift, recorded here because it is load-bearing for this file: the live
`data/platform.db` already has four of these indexes (`idx_auditlog_ts`,
`_user`, `_module`, `_action`) even though no source file creates them — they
were applied by hand or by a since-deleted script. This revision adopts those
exact names and definitions so it is a no-op against that database rather than a
source of duplicates, and it brings them under version control for every install
that does not have them.

Purely additive and idempotent — CREATE INDEX IF NOT EXISTS, no data touched, no
column altered, no table rewritten. Safe to run against production while the app
is up (see the CONCURRENTLY note below if the table is already large).

Nothing depends on these indexes for correctness. A fresh SQLite database
created by init_db() without ever running alembic is fully functional, just
slower on the audit page — which is why this is an index-only migration and the
storage format needed no schema change at all.

Revision ID: 0002_audit_log_indexes
Revises: 0001_baseline


APPLYING THIS REVISION
──────────────────────
There are deliberately TWO alembic heads off 0001_baseline, so plain
`upgrade head` is AMBIGUOUS AND WILL ERROR. That is the intended behaviour —
it stops an operator from applying a financial data migration by accident while
reaching for an index. Name this revision explicitly:

    alembic -c db_migrations/alembic.ini upgrade 0002_audit_log_indexes

The sibling head, 0002_money_numeric, retypes 34 money columns REAL ->
NUMERIC(12,2) and is ON HOLD — it is a prepared artefact, not something to run
(see docs/MONEY_PRECISION.md: ~550-800 call sites of blast radius, and 172
float() calls that would convert the Decimals straight back to binary float).
This revision is deliberately NOT chained behind it: adding an index to an audit
table must not require anyone to first run a deferred financial migration.

The two branches touch disjoint tables (audit_log here, invoices/payments/
salaries there) and never need to be merged. If money_numeric is ever applied,
alembic tracks both heads independently and no merge revision is required.
"""

from alembic import op

revision = "0002_audit_log_indexes"
# Parented on the baseline, NOT on 0002_money_numeric — see above. Numbered 0002
# rather than 0003 because it is a *sibling* of money_numeric, not its successor:
# both are children of 0001_baseline at the same depth, and the directory listing
# should say so.
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

# Ordered to match how the audit page actually queries:
#   - every query ends "ORDER BY timestamp DESC"         -> idx_auditlog_ts
#   - "what did this user do"                            -> idx_auditlog_user
#   - "what happened in finance"                         -> idx_auditlog_module
#   - filter by action                                   -> idx_auditlog_action
#   - "who changed THIS invoice" (the important one)     -> idx_auditlog_entity
#
# NAMES AND COLUMNS ARE NOT ARBITRARY. The live database already carries the
# first four under exactly these names and definitions — including the
# `timestamp DESC` — created ad hoc at some point by a script that exists
# nowhere in this repository. Reusing the names makes CREATE INDEX IF NOT EXISTS
# a genuine no-op there instead of laying a second, identical index beside each
# one under a different name. On a fresh install (which has none of them,
# because nothing in models/database.py creates them) all five are created.
#
# Only idx_auditlog_entity is actually new anywhere. It is also the one this
# feature needs most: "who changed this record" filters on entity_type +
# entity_id, and without it that query is a full scan.
_INDEXES = [
    ("idx_auditlog_ts",     "audit_log(timestamp DESC)"),
    ("idx_auditlog_user",   "audit_log(username)"),
    ("idx_auditlog_module", "audit_log(module)"),
    ("idx_auditlog_action", "audit_log(action)"),
    ("idx_auditlog_entity", "audit_log(entity_type, entity_id)"),
]


def upgrade() -> None:
    bind = op.get_bind()
    for name, target in _INDEXES:
        # ponytail: plain CREATE INDEX, which takes a write lock on PostgreSQL
        # for the duration. Ceiling: on an audit_log already holding millions of
        # rows that lock is a visible outage. Upgrade path: run these five by
        # hand as CREATE INDEX CONCURRENTLY (which cannot run inside alembic's
        # transaction) and then `alembic stamp 0002_audit_log_indexes`.
        bind.exec_driver_sql(f"CREATE INDEX IF NOT EXISTS {name} ON {target}")


def downgrade() -> None:
    bind = op.get_bind()
    for name, _ in reversed(_INDEXES):
        bind.exec_driver_sql(f"DROP INDEX IF EXISTS {name}")
