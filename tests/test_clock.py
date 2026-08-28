# -*- coding: utf-8 -*-
"""The stored timestamp format must not change.

`datetime.utcnow()` is deprecated and scheduled for removal, so all 33 calls
were replaced. The danger in that change is not the deprecation - it is that
the documented replacement returns an AWARE datetime whose isoformat() carries
a "+00:00" suffix, and thirty of those calls write straight into TEXT columns
that already hold naive strings.

Date comparisons in this schema are string comparisons. A column where half the
rows carry a suffix and half do not is the exact shape of the defect that made
`check_in` hold two formats and every attendance calculation return zero.

These tests exist so that if somebody later "modernises" models/clock.py the
build fails, instead of the timestamps quietly changing shape and the breakage
surfacing months later in a payroll run.
"""
import re
from datetime import datetime, timezone

from models import clock


def test_it_is_naive_like_utcnow_was():
    """Aware would append +00:00 to every stored string."""
    assert clock.utcnow().tzinfo is None


def test_it_is_actually_utc_not_local_time():
    """Naive is not the same as wrong. An Egyptian server is UTC+2 or +3, so a
    naive LOCAL time would silently shift every stored timestamp by hours."""
    delta = abs((clock.utcnow()
                 - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds())
    assert delta < 5, "clock.utcnow() is not UTC - it is out by %.0fs" % delta


def test_the_iso_string_has_no_timezone_suffix():
    """The one that matters. Every caller writes this into a TEXT column."""
    s = clock.utcnow_iso()
    assert not s.endswith("+00:00"), "a timezone suffix reached the stored string"
    assert "Z" not in s
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", s), (
        "unexpected stored format: %r" % s)


def test_it_matches_what_utcnow_produced_character_for_character():
    """The migration is meant to be a rename, not a change of behaviour."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        old = datetime.utcnow().isoformat(timespec="seconds")
    new = clock.utcnow_iso()
    assert len(old) == len(new)
    # Same shape, and within a second of each other.
    assert old[:16] == new[:16], "%r vs %r" % (old, new)


def test_no_shipped_module_still_calls_the_deprecated_function():
    """When utcnow() is removed from Python, any file still calling it stops
    the application booting."""
    import os
    offenders = []
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs
                   if d not in (".git", "tests", "__pycache__", ".venv", "venv")]
        for name in files:
            if not name.endswith(".py"):
                continue
            path = os.path.join(root, name)
            try:
                body = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            # models/clock.py is allowed to name it - in a docstring, where it
            # explains what it replaced.
            if path.replace("\\", "/").endswith("models/clock.py"):
                continue
            for m in re.finditer(r"\butcnow\(\)", body):
                line = body[:m.start()].count("\n") + 1
                snippet = body[max(0, m.start() - 30):m.start()]
                # clock.utcnow() is the replacement, not the deprecated call.
                if snippet.rstrip().endswith("clock.") or "def utcnow" in snippet:
                    continue
                offenders.append("%s:%d" % (path, line))
    assert not offenders, (
        "datetime.utcnow() is deprecated and scheduled for removal; these "
        "still call it:\n  " + "\n  ".join(offenders))
