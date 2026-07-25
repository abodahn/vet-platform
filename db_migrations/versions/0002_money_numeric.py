"""money columns: REAL (binary float) -> NUMERIC(12,2)

Every currency column in the schema is declared REAL, i.e. IEEE-754 double.
Binary floating point cannot represent most decimal fractions, so amounts that
are exact in EGP are inexact in storage. See docs/MONEY_PRECISION.md for the
measured damage and the rollout procedure.

Scope note — this revision changes CURRENCY columns only. Deliberately NOT
touched, because they are genuinely continuous quantities and REAL is correct
for them: weight_kg, temp_c, quantity/qty, hours_worked, days_per_year,
days_requested, leave_balances.*, result_value, fluid_input/output,
reorder_level, reorder_qty, max_stock, received_qty. Also NOT touched: the
various `tax_rate` columns — those are percentages, not money.

The pet-shop POS tables (ps_products, ps_orders, ps_order_items) hold money too
and are equally affected, but are deliberately out of scope — see the comment
under MONEY_COLUMNS for the two reasons, both of which were found by testing
this migration against a copy of production.

Idempotent: re-running is a no-op on columns that are already NUMERIC, and
tables that are not present are skipped. Verified by running upgrade twice.

Tested on a copy of the live database: 84 tables' row counts unchanged, all 499
money values round-trip to the same 2-dp amount, 70/70 indexes and every foreign
key (including ON DELETE CASCADE) preserved, upgrade->downgrade->compare clean,
and the 42 malformed expenses.amount values repaired. See docs/MONEY_PRECISION.md
section 6 for the full result table.

Revision ID: 0002_money_numeric
Revises: 0001_baseline
"""

from decimal import Decimal, ROUND_HALF_UP

import sqlalchemy as sa
from alembic import op

revision = "0002_money_numeric"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

PRECISION, SCALE = 12, 2
_QUANT = Decimal("0.01")

# table -> currency columns. Every one of these holds an amount of money.
MONEY_COLUMNS = {
    "owners":            ("outstanding_balance",),
    "items":             ("cost_price", "sell_price"),
    "batches":           ("unit_cost",),
    "stock_movements":   ("unit_cost",),
    # invoices.discount_value is dual-purpose: an amount when discount_type
    # ='value', a percentage when ='percent' (models/database.py:2523). Both
    # fit NUMERIC(12,2); a 2-dp percentage is what the UI already offers.
    "invoices":          ("subtotal", "discount_value", "discount_amount",
                          "tax_amount", "total", "paid_amount", "due_amount"),
    "invoice_lines":     ("unit_price", "discount", "total"),
    "payments":          ("amount",),
    "expenses":          ("amount",),
    "daily_closings":    ("cash_sales", "card_sales", "transfer_sales",
                          "total_sales", "total_expenses", "net_revenue",
                          "opening_cash", "closing_cash"),
    "purchase_orders":   ("subtotal", "tax_amount", "total"),
    "po_lines":          ("unit_cost", "total"),
    "grooming_services": ("price",),
    "boarding_rooms":    ("price_per_night",),
    "service_catalog":   ("standard_price",),
    "budget_targets":    ("monthly_egp",),
}

# DELIBERATELY EXCLUDED: the pet-shop POS tables ps_products / ps_orders /
# ps_order_items, which hold real money (95 orders, 230 lines in the current
# database) and are just as float-damaged as the rest.
#
# They are not excluded because they don't matter. They are excluded because
# alembic cannot own them. blueprints/petshop/routes.py:37 defines
# ensure_petshop_tables(), which runs CREATE TABLE IF NOT EXISTS on almost every
# petshop request (routes.py:142, 172, 202, ... — 16 call sites). On an existing
# database that is a no-op and a migration would hold; on a fresh one the app
# recreates all three tables with REAL columns the first time anybody opens the
# pet shop. Migrating them here produces a schema the application itself does
# not reproduce, which is worse than leaving them consistent and wrong.
#
# There is a second, sharper reason. ps_order_items declares its foreign key
# inline —
#     order_id INTEGER NOT NULL REFERENCES ps_orders(id) ON DELETE CASCADE
# — rather than as a table-level FOREIGN KEY clause like every baseline table.
# SQLAlchemy's SQLite reflection does not recover ON DELETE from the inline
# form, so the batch rebuild silently downgrades that CASCADE to NO ACTION and
# deleting an order starts orphaning its line items. This was measured, not
# assumed: T4 caught it on a copy (see docs/MONEY_PRECISION.md).
#
# Fixing the pet shop means editing routes.py:49-101 to declare NUMERIC(12,2)
# and a table-level FK, which is an application change, not a migration.


def _present(bind):
    """{table: {column: (reflected type, nullable)}} for the tables that exist."""
    insp = sa.inspect(bind)
    have = set(insp.get_table_names())
    info = {}
    for table in MONEY_COLUMNS:
        if table in have:
            info[table] = {c["name"]: (c["type"], c["nullable"])
                           for c in insp.get_columns(table)}
    return info


def _is_numeric(coltype) -> bool:
    """True when the column already stores decimal, not binary float.

    sa.Numeric is the parent of sa.Float, so the isinstance test has to exclude
    Float explicitly or every REAL column reports as already-migrated.
    """
    return isinstance(coltype, sa.Numeric) and not isinstance(coltype, sa.Float)


def _round_half_up(bind, table: str, column: str) -> int:
    """Rewrite every value in `table.column` as its half-up 2-dp amount.

    Runs BEFORE the type change so the conversion has nothing left to truncate.

    Uses Decimal(repr(v)) rather than Decimal(v): repr() gives the shortest
    decimal that round-trips the double, i.e. the number the operator actually
    typed. A price entered as 2.675 is stored as 2.67499999999999982..., and
    the operator meant 2.68. Decimal(v) would see the exact binary value and
    round it down to 2.67, silently taking a cent off the invoice.

    Half-up, not Python's round(): round() is banker's rounding (half-to-even).
    Money convention is half-up, and it matches what PostgreSQL's own
    ::numeric(12,2) cast does, so the migrated value equals what the database
    would have produced had the column always been NUMERIC.
    """
    param = "%s" if bind.dialect.name == "postgresql" else "?"
    rows = bind.exec_driver_sql(
        f"SELECT id, {column} FROM {table} WHERE {column} IS NOT NULL"
    ).fetchall()
    changed = 0
    for row_id, value in rows:
        if isinstance(value, Decimal):
            current = value
        elif isinstance(value, (int, float)):
            current = Decimal(repr(float(value)))
        else:
            # TEXT or another affinity got in here somehow. Parse it — and let a
            # bad value raise InvalidOperation rather than guess at an amount.
            current = Decimal(str(value))
        exact = current.quantize(_QUANT, rounding=ROUND_HALF_UP)
        if exact != current:
            bind.exec_driver_sql(
                f"UPDATE {table} SET {column} = {param} WHERE id = {param}",
                (str(exact), row_id),
            )
            changed += 1
    return changed


# ponytail: row-at-a-time UPDATE keyed on `id`. Ceiling: every table here has an
# INTEGER PRIMARY KEY `id`, and clinic-scale tables are thousands of rows, so a
# full pass is seconds. Upgrade path: if a table ever reaches millions of rows,
# replace with a single `UPDATE t SET c = ROUND(c::numeric, 2)` on PostgreSQL —
# but only there, since SQLite's round() is not half-up on ties.


def _retype(to_numeric: bool) -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"
    target = (sa.Numeric(PRECISION, SCALE) if to_numeric
              else (sa.REAL() if is_sqlite else sa.Float(precision=53)))
    info = _present(bind)

    for table, columns in MONEY_COLUMNS.items():
        if table not in info:
            continue
        pending = [c for c in columns
                   if c in info[table]
                   and _is_numeric(info[table][c][0]) != to_numeric]
        if not pending:
            continue  # already in the target state — idempotent no-op

        if to_numeric:
            for column in pending:
                _round_half_up(bind, table, column)

        # batch mode rebuilds the table, which is the only way SQLite can change
        # a column type at all: it creates a new table, copies the rows, drops
        # the old one and renames. On PostgreSQL batch degrades to a plain
        # ALTER ... TYPE and the USING clause below does the cast.
        with op.batch_alter_table(table) as batch:
            for column in pending:
                batch.alter_column(
                    column,
                    type_=target,
                    existing_type=info[table][column][0],
                    existing_nullable=info[table][column][1],
                    postgresql_using=f"{column}::numeric({PRECISION},{SCALE})"
                    if to_numeric else f"{column}::double precision",
                )


def upgrade() -> None:
    _retype(to_numeric=True)


def downgrade() -> None:
    """Back to REAL / double precision.

    Lossless in the sense that matters: every value was quantised to 2 dp on the
    way up, and every 2-dp amount inside NUMERIC(12,2) survives the round trip
    through a double exactly (a double holds ~15-16 significant digits; the
    largest value this column can hold has 12). The amounts you get back are the
    amounts you put in. What you lose is the guarantee — arithmetic goes back to
    being approximate.
    """
    _retype(to_numeric=False)
