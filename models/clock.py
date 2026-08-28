# -*- coding: utf-8 -*-
"""One source of "now", so replacing a deprecated call cannot change stored data.

WHY THIS EXISTS

`datetime.utcnow()` is deprecated and scheduled for removal. When it goes, an
application that still calls it stops booting. There were 33 calls in this
codebase.

The documented replacement is NOT a safe substitution here:

    datetime.utcnow()                        -> 2026-08-26T14:56:11
    datetime.now(timezone.utc)               -> 2026-08-26T14:56:11+00:00
    datetime.now(timezone.utc).replace(...)  -> 2026-08-26T14:56:11

utcnow() returns a NAIVE datetime; now(timezone.utc) returns an aware one, and
its isoformat() carries a "+00:00" suffix. Thirty of the thirty-three calls
write that string straight into a TEXT column, and date comparisons in this
schema are string comparisons. Half the rows in a column carrying a suffix the
other half does not is exactly the shape of defect that made `check_in` hold two
formats and every attendance calculation return zero.

So this returns naive UTC - byte-identical to what utcnow() produced - and the
migration becomes a rename rather than a change of behaviour. tests/test_clock.py
pins that, so if somebody later "modernises" this function the build says so
instead of the timestamps quietly changing shape.

WHAT THIS IS NOT

It is not a fix for the wider question of whether this application should store
naive UTC at all. It should probably store aware timestamps eventually. That is
a schema migration with a data backfill, not a find-and-replace, and doing it in
the same change as removing a deprecated call would make both impossible to
review.
"""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC, exactly as datetime.utcnow() returned it.

    Naive on purpose. See the module docstring: the stored string format must
    not change, and every caller here writes to a TEXT column that other rows
    already occupy.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcnow_iso(timespec: str = "seconds") -> str:
    """The form most callers actually wanted: an ISO string with no suffix."""
    return utcnow().isoformat(timespec=timespec)
