# -*- coding: utf-8 -*-
"""Money that behaves the same on both database engines.

PostgreSQL returns NUMERIC columns as Decimal; SQLite returns them as float.
Every place that mixes the two — `db_amount + 0.0`, `total * tax_rate`, a sum
seeded with `0` — raises TypeError on one engine and works on the other. The
test suite runs on SQLite, so those failures are invisible until a clinic is
already on PostgreSQL.

Small on purpose. This is a conversion helper and a display filter, not a money
type; the schema is where exactness is actually won, and that is what
db_migrations/versions/0002_money_numeric.py does.
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

_TWO_PLACES = Decimal("0.01")


def to_decimal(value, places: int = 2) -> Decimal:
    """Any money-ish value as an exact Decimal, rounded half-up.

    Half-up, not Python's default banker's rounding: `round(2.5)` is 2 and
    `round(0.125, 2)` is 0.12, so a clinic's invoice could round a half-piastre
    down while the printed receipt rounded it up. That is an argument at the
    counter over a number nobody can explain.

    A float is converted via str() rather than directly, because
    Decimal(0.1) is 0.1000000000000000055511151231257827, and carrying that
    into a total then rounding at the end can move the last piastre.
    """
    if value is None or value == "":
        return Decimal("0").quantize(_exp(places))
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, float):
        dec = Decimal(str(value))
    else:
        try:
            dec = Decimal(str(value).strip())
        except (InvalidOperation, ValueError, TypeError):
            return Decimal("0").quantize(_exp(places))
    return dec.quantize(_exp(places), rounding=ROUND_HALF_UP)


def _exp(places: int) -> Decimal:
    return _TWO_PLACES if places == 2 else Decimal(1).scaleb(-places)


def format_money(value, places: int = 2) -> str:
    """Render for display. Identical output whatever the engine returned."""
    return f"{to_decimal(value, places):.{places}f}"


def init_app(app) -> None:
    """Register the `|money` filter and Decimal-safe JSON.

    Both are engine-independence measures, not formatting preferences: without
    the filter a page shows 120.5 on one engine and 120.50 on the other, and
    without the JSON hook every endpoint returning an amount becomes a 500 the
    day PostgreSQL is switched on.
    """
    app.jinja_env.filters["money"] = format_money

    provider = app.json
    if provider is not None and not getattr(provider, "_money_patched", False):
        original = provider.default

        def default(obj):
            if isinstance(obj, Decimal):
                # A JSON number, not a string: clients already parse these as
                # numbers, and quoting them would break every existing caller.
                return float(obj)
            return original(obj)

        provider.default = default
        provider._money_patched = True
