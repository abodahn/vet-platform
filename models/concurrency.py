# -*- coding: utf-8 -*-
"""Stop two people silently overwriting each other.

A clinic runs one PC at reception and more in the back, and the shared desk now
puts up to five accounts on each of them. So two people opening the same client
— or the same attendance record, which is somebody's pay — is not a rare race,
it is Tuesday.

Every edit form in this codebase reads a row, shows it, and writes the whole
thing back. Whoever presses Save second wins, and the first person's change
disappears with nothing on screen and nothing in the record to show it ever
existed. That is the worst shape a data-loss bug can take: silent, ordinary
looking, and discovered weeks later by someone who cannot reconstruct it.

The fix is the classic one and it is small. The edit form carries the row's
`updated_at` as a hidden field; on save, if the stored value has moved, the row
changed under the editor and the save is refused with who did it and when.

Deliberately NOT a lock. A held lock needs releasing, and a receptionist who
opens a client and then goes to lunch would block the clinic until it timed
out. Refusing the rare colliding save costs one retry; locking costs a
workflow.
"""
from typing import Optional


class StaleRecord(Exception):
    """The row changed after the editor loaded it."""

    def __init__(self, message: str, changed_by: str = "", changed_at: str = ""):
        super().__init__(message)
        self.changed_by = changed_by
        self.changed_at = changed_at


# Only tables that actually carry updated_at, named explicitly rather than
# interpolated from a caller — this builds SQL by concatenation, so the table
# name must never come from a request.
_GUARDED = {
    "owners", "pets", "visits", "invoices", "attendance_records", "tasks",
}


def stamp_of(conn, table: str, row_id) -> Optional[str]:
    """The row's current updated_at, or None if there is no such row."""
    if table not in _GUARDED:
        raise ValueError("table %r is not guarded" % table)
    row = conn.execute(
        "SELECT updated_at FROM " + table + " WHERE id=?", (row_id,)).fetchone()
    return None if row is None else (row["updated_at"] or "")


def _who_last_touched(conn, table: str, row_id) -> tuple:
    """Best effort: who the audit log says last changed this row.

    Best effort on purpose. Not every write is audited, and a name is a
    courtesy here — the refusal itself is what protects the data, so a missing
    name must never turn a safe refusal into an error.
    """
    try:
        row = conn.execute(
            "SELECT username, timestamp FROM audit_log"
            " WHERE entity_type=? AND entity_id=?"
            " ORDER BY id DESC LIMIT 1", (table, str(row_id))).fetchone()
    except Exception:
        return "", ""
    if not row:
        return "", ""
    return (row["username"] or ""), (row["timestamp"] or "")


def guard(conn, table: str, row_id, seen_stamp) -> None:
    """Raise StaleRecord if the row moved since the editor loaded it.

    A blank `seen_stamp` means the form predates this check — those pass, so
    adding the guard to a route never breaks a page that has not been updated
    yet. Rolling it out screen by screen is the point.
    """
    if seen_stamp is None or str(seen_stamp).strip() == "":
        return
    current = stamp_of(conn, table, row_id)
    if current is None:
        raise StaleRecord("That record no longer exists — somebody deleted it "
                          "while you had it open.")
    if str(current).strip() == str(seen_stamp).strip():
        return

    who, when = _who_last_touched(conn, table, row_id)
    if who:
        msg = ("%s changed this while you had it open (%s). Your changes were "
               "NOT saved. Reopen it and apply them again so nothing of theirs "
               "is lost." % (who, when or current))
    else:
        msg = ("Somebody else changed this while you had it open. Your changes "
               "were NOT saved. Reopen it and apply them again.")
    raise StaleRecord(msg, changed_by=who, changed_at=when or str(current))
