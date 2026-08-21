"""models/database.py spine: audit logging, clinic update, fresh-install seed.

bug-086 / bug-146 / bug-147.
"""
import logging

import pytest

import models.database as db


# ── bug-086: a silent audit log is worse than no audit log ────────────────────

def test_log_audit_writes_a_row(auth_client):
    db.log_audit(username="audit-probe-086", role="super_admin",
                 action="probe", module="tests")
    conn = db.get_db()
    n = conn.execute("SELECT COUNT(*) FROM audit_log WHERE username=?",
                     ("audit-probe-086",)).fetchone()[0]
    conn.close()
    assert n == 1


def test_log_audit_failure_is_logged_not_swallowed(app, monkeypatch, caplog):
    """A broken audit write must shout in the log and still not raise."""
    def boom():
        raise RuntimeError("audit table is gone")

    monkeypatch.setattr(db, "get_db", boom)
    with caplog.at_level(logging.ERROR, logger="models.database"):
        db.log_audit(username="u", action="delete", module="crm",
                     entity_type="owner", entity_id="7")

    errors = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert errors, "audit failure was swallowed silently"
    assert "audit" in errors[0].getMessage().lower()
    # The exception itself must reach the log, not just a bare message.
    assert errors[0].exc_info is not None


def test_log_audit_does_not_break_the_callers_operation(app, monkeypatch):
    monkeypatch.setattr(db, "get_db", lambda: (_ for _ in ()).throw(
        RuntimeError("no connection")))
    db.log_audit(username="u", action="create", module="crm")  # must not raise


# ── bug-146: update_clinic must work on the engine it is running on ───────────

def test_update_clinic_roundtrip_invalidates_the_cache(app):
    """get_clinic() caches for 5 min, so a write that forgets to invalidate is
    invisible to every reader — the context_processor included — until the TTL
    expires. Prime the cache first so this test can see that."""
    db.get_clinic()
    db.update_clinic({"name": "Bug146 Veterinary", "phone": "0100000146"},
                     updated_by="tests")
    row = db.get_clinic()
    assert row["name"] == "Bug146 Veterinary"
    assert row["phone"] == "0100000146"
    assert row["updated_at"]  # datetime('now'), not NOW()


def test_update_clinic_ignores_unknown_columns(app):
    """Column names are interpolated, so anything unrecognised must be dropped
    rather than reaching the SQL string."""
    db.update_clinic({"name": "Bug146 Two", "id=1; DROP TABLE clinic; --": "x"})
    assert db.get_clinic()["name"] == "Bug146 Two"


# ── bug-147: a fresh install must not carry the vendor's brand ────────────────

def test_fresh_install_does_not_seed_vendor_brand(tmp_path):
    fresh = str(tmp_path / "fresh_install.db")
    db.use_sqlite(fresh)          # _restore_db_globals puts the target back
    db.init_db(admin_user="admin", admin_pass="admin1234")
    db.cache_invalidate("clinic_row")
    clinic = db.get_clinic()
    assert clinic, "fresh install seeded no clinic row"
    for field in ("name", "name_ar", "doctor_name"):
        assert "aleefy" not in (clinic.get(field) or "").lower(), (
            f"fresh install seeds the vendor brand in clinic.{field}")


# ── gaps the adversarial verifier found in the first pass ────────────────────

def test_a_fresh_install_ships_no_vendor_tagline(app):
    """bug-147, second half. The seeded VALUES were fixed but the column
    DEFAULT behind them still wrote 'Happy Pets, Healthy Lives' — so a clinic
    that installs this prints somebody else's slogan on its own pages until it
    finds Settings."""
    import io
    src = io.open("models/database.py", encoding="utf-8").read()
    assert "TEXT DEFAULT 'Happy Pets, Healthy Lives'" not in src
    assert "TEXT DEFAULT 'Lead Veterinarian'" not in src


def test_the_paths_that_must_be_audible_are_audible(app):
    """bug-086 covered log_audit and left the same bare `except: pass` in the
    notification writers and the password-hash upgrade.

    Deliberately NOT a blanket ban on bare excepts in this file: six of them
    are correct. rollback_quietly() is quiet by design and says so in its name,
    _verify_dummy() does nothing on purpose to keep bcrypt timing flat, and a
    cursor close() in a wrapper has nothing to report. A rule that failed on
    those would push the next person to add noise to silence it.

    This checks only the paths where silence hides a real loss: an audit row, a
    notification, or a password hash that never got upgraded.
    """
    import io
    lines = io.open("models/database.py", encoding="utf-8").read().split(chr(10))

    # No regex: an earlier attempt used one and its own escapes turned
    # into a literal backspace, so the test passed against the bug it was
    # written to catch. Reading the next line is unambiguous.
    def swallows(fn):
        """Line number of a silent handler in fn(), or 0.

        Looks for the first real STATEMENT after the except, not the next
        line: a comment sits between the two in the fixed version, and an
        earlier attempt at this test read that comment, found it was not
        "pass", and passed against the very bug it exists to catch.
        """
        start = next(i for i, l in enumerate(lines)
                     if l.startswith("def " + fn + "("))
        for i in range(start, min(start + 90, len(lines) - 1)):
            head = lines[i].strip()
            if not (head.startswith("except Exception") and head.endswith(":")):
                continue
            for j in range(i + 1, min(i + 12, len(lines))):
                nxt = lines[j].strip()
                if not nxt or nxt.startswith("#"):
                    continue
                if nxt == "pass":
                    return j + 1
                break
        return 0
    # create_notification() is the one that actually writes the row;
    # notify_role() and notify_managers() fan out through it.
    for fn in ("log_audit", "create_notification", "notify_role",
               "notify_managers", "_verify_and_migrate"):
        line = swallows(fn)
        assert not line, (
            "%s() swallows failures silently at models/database.py:%d - "
            "anyone relying on it would never learn it had stopped "
            "working" % (fn, line))


def test_a_notification_failure_does_not_break_the_caller(app, monkeypatch):
    """The other half of the contract: audible, but never fatal. The operation
    that triggered the notification must still succeed."""
    import models.database as db
    monkeypatch.setattr(db, "get_db",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    with app.app_context():
        db.notify_role("reception", "title", "body")     # must not raise
