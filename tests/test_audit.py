"""Self-check for the field-level audit trail (models/audit.py).

Runs on SQLite only — no PostgreSQL, no fixtures beyond conftest's app/client.

Covers the four properties the audit trail is worthless without:
  1. the diff records only the fields that actually changed
  2. redacted fields never leak a value into the trail
  3. a failing audit write does not break the operation being audited
  4. the audit page's filters return the right rows
"""
import json

import pytest

import models.audit as audit
import models.database as db


# ─── helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_audit(app):
    """Empty audit_log around each test so row counts are deterministic."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM audit_log")
        conn.close()
    yield


def _rows(app, **where):
    with app.app_context():
        conn = db.get_db()
        q = "SELECT * FROM audit_log"
        params = []
        if where:
            q += " WHERE " + " AND ".join(f"{k}=?" for k in where)
            params = list(where.values())
        q += " ORDER BY id"
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]
        conn.close()
    return rows


# ═══ 1. the diff records only what changed ════════════════════════════════════

def test_diff_records_only_changed_fields():
    before = {"name": "Rex", "weight": 12.0, "notes": "healthy", "owner_id": 4}
    after  = {"name": "Rex", "weight": 14.5, "notes": "healthy", "owner_id": 4}

    d = audit.diff(before, after)

    assert set(d) == {"weight"}
    assert d["weight"] == {"from": 12.0, "to": 14.5}


def test_diff_is_empty_when_nothing_changed():
    row = {"name": "Rex", "weight": 12.0}
    assert audit.diff(row, dict(row)) == {}


def test_diff_ignores_type_churn_not_real_edits():
    """SQLite hands back 1 / 100.0; a form posts "1" / "100.0". Not an edit."""
    assert audit.diff({"is_active": 1, "total": 100.0},
                      {"is_active": "1", "total": "100.0"}) == {}


def test_diff_ignores_updated_at_noise():
    d = audit.diff({"updated_at": "2026-01-01", "price": 5},
                   {"updated_at": "2026-07-25", "price": 5})
    assert d == {}


def test_diff_captures_added_and_removed_fields():
    d = audit.diff({"diagnosis": None}, {"diagnosis": "otitis externa"})
    assert d == {"diagnosis": {"from": None, "to": "otitis externa"}}


def test_diff_truncates_huge_values():
    huge = "x" * 5000
    d = audit.diff({"soap_plan": ""}, {"soap_plan": huge})
    stored = d["soap_plan"]["to"]
    assert len(stored) < 400
    assert "+4700 chars" in stored


def test_record_change_writes_only_the_diff(app, clean_audit):
    with app.app_context():
        audit.record_change(
            "invoices", 42,
            {"total": 100.0, "status": "draft", "owner_id": 7},
            {"total": 250.0, "status": "paid",  "owner_id": 7},
            action="update", module="finance", user="dr_hatem", role="doctor",
        )

    rows = _rows(app, entity_type="invoices")
    assert len(rows) == 1
    stored = json.loads(rows[0]["details"])
    assert set(stored) == {"total", "status"}          # owner_id excluded
    assert stored["total"] == {"from": 100.0, "to": 250.0}
    assert rows[0]["entity_id"] == "42"
    assert rows[0]["username"] == "dr_hatem"
    assert rows[0]["module"] == "finance"


def test_record_change_writes_nothing_when_unchanged(app, clean_audit):
    with app.app_context():
        result = audit.record_change("invoices", 42, {"total": 100.0},
                                     {"total": 100.0}, user="u", role="r")
    assert result == {}
    assert _rows(app) == []


# ═══ 2. redaction ═════════════════════════════════════════════════════════════

@pytest.mark.parametrize("field", [
    "password_hash", "password", "totp_secret", "api_key", "api_token",
    "whatsapp_api_token", "reset_token", "session_token", "private_key",
    "card_number", "cvv", "iban", "national_id", "passport_no",
    "PASSWORD_HASH", "Stripe_Secret_Key",
])
def test_sensitive_fields_are_recognised(field):
    assert audit.is_redacted(field), f"{field} must be redacted"


@pytest.mark.parametrize("field", [
    "full_name", "phone", "email", "address", "diagnosis", "total", "notes",
])
def test_ordinary_fields_are_not_redacted(field):
    assert not audit.is_redacted(field)


def test_redacted_values_never_reach_the_diff():
    d = audit.diff(
        {"username": "vet1", "password_hash": "pbkdf2:sha256:600000$OLDHASH"},
        {"username": "vet1", "password_hash": "pbkdf2:sha256:600000$NEWHASH"},
    )
    # The *fact* of the change is recorded — that is what an auditor needs.
    assert "password_hash" in d
    assert d["password_hash"] == {"from": audit.REDACTED, "to": audit.REDACTED}
    assert "OLDHASH" not in json.dumps(d)
    assert "NEWHASH" not in json.dumps(d)


def test_redacted_secret_never_lands_in_the_database(app, clean_audit):
    with app.app_context():
        audit.record_change(
            "users", 3,
            {"totp_secret": "JBSWY3DPEHPK3PXP", "full_name": "Vet One"},
            {"totp_secret": "NEWSECRETVALUE99", "full_name": "Vet Uno"},
            module="hr", user="admin", role="super_admin",
        )
    raw = json.dumps(_rows(app))
    assert "JBSWY3DPEHPK3PXP" not in raw
    assert "NEWSECRETVALUE99" not in raw
    assert "Vet Uno" in raw              # non-sensitive change still recorded
    assert audit.REDACTED in raw


# ═══ 3. a failing audit write must not break the caller ═══════════════════════

def test_failing_audit_write_does_not_raise(app, monkeypatch, caplog):
    """The invoice must still save when the audit INSERT explodes."""
    def boom():
        raise RuntimeError("audit_log is on fire")

    monkeypatch.setattr(audit.db, "get_db", boom)

    with app.app_context(), caplog.at_level("ERROR"):
        result = audit.record_change("invoices", 99, {"total": 1}, {"total": 2},
                                     user="u", role="r")

    assert result == {"total": {"from": 1, "to": 2}}   # caller gets its answer
    assert "AUDIT WRITE FAILED" in caplog.text          # loud, not silent
    assert "invoices" in caplog.text


def test_failing_snapshot_does_not_raise(app, monkeypatch, caplog):
    def boom():
        raise RuntimeError("no database")

    monkeypatch.setattr(audit.db, "get_db", boom)
    with app.app_context(), caplog.at_level("ERROR"):
        assert audit.snapshot("roles", 1) == {}
    assert "AUDIT SNAPSHOT FAILED" in caplog.text


def test_audit_row_still_runs_the_mutation_when_auditing_fails(app, monkeypatch):
    """The whole point: broken auditing must not break the business operation."""
    ran = []

    def boom():
        raise RuntimeError("db down for audit only")

    monkeypatch.setattr(audit.db, "get_db", boom)
    with app.app_context():
        with audit.audit_row("roles", 1, module="system"):
            ran.append("mutation happened")

    assert ran == ["mutation happened"]


def test_snapshot_rejects_an_unsafe_table_name(app):
    with app.app_context():
        with pytest.raises(ValueError):
            audit.snapshot("roles; DROP TABLE users", 1)


# ═══ audit_row end to end ═════════════════════════════════════════════════════

def test_audit_row_records_a_real_update(app, clean_audit):
    with app.app_context():
        role_id = db.create_role("test_auditrole", "Test Audit Role", "دور تجريبي",
                                 ["patients"], "#123456")
        try:
            with audit.audit_row("roles", role_id, module="system",
                                 action="edit_role", user="admin", role="super_admin"):
                db.update_role(role_id, "Renamed Role", "دور معاد تسميته",
                               ["patients", "invoicing"], "#654321")
        finally:
            db.delete_role(role_id)

    rows = _rows(app, entity_type="roles")
    assert len(rows) == 1
    stored = json.loads(rows[0]["details"])
    assert "display_name" in stored
    assert stored["display_name"] == {"from": "Test Audit Role", "to": "Renamed Role"}
    assert "invoicing" in stored["permissions_json"]["to"]
    assert "id" not in stored           # unchanged primary key not reported
    assert rows[0]["action"] == "edit_role"


# ═══ parse_details ════════════════════════════════════════════════════════════

def test_parse_details_round_trips_a_diff():
    d = {"total": {"from": 1, "to": 2}}
    assert audit.parse_details(json.dumps(d)) == d


@pytest.mark.parametrize("legacy", [
    "Updated clinic settings",
    "Restored from: backup-2026-07-25.db",
    "1234",
    "",
    None,
    "{not json at all",
    '{"a": 1}',            # dict, but not a diff shape
])
def test_parse_details_rejects_non_diff_text(legacy):
    assert audit.parse_details(legacy) is None


# ═══ 4. the audit page filters ════════════════════════════════════════════════

@pytest.fixture
def seeded_audit(app, clean_audit):
    """Three distinguishable audit rows to filter against."""
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.executemany(
                "INSERT INTO audit_log"
                "(timestamp,username,role,action,module,entity_type,entity_id,details,ip)"
                " VALUES(?,?,?,?,?,?,?,?,?)",
                [
                    ("2026-01-10 09:00:00", "alice", "doctor", "update",
                     "finance", "invoices", "1001",
                     json.dumps({"total": {"from": 100, "to": 200}}), "10.0.0.1"),
                    ("2026-03-15 10:00:00", "bob", "reception", "create",
                     "crm", "owners", "55", "Created owner", "10.0.0.2"),
                    ("2026-06-20 11:00:00", "alice", "doctor", "delete",
                     "finance", "invoices", "1002", "Deleted invoice", "10.0.0.3"),
                ],
            )
        conn.close()
    yield


def _audit_page(auth_client, **query):
    resp = auth_client.get("/system/audit", query_string=query)
    assert resp.status_code == 200, resp.status_code
    return resp.get_data(as_text=True)


def test_filter_by_user(auth_client, seeded_audit):
    body = _audit_page(auth_client, user="bob")
    assert "10.0.0.2" in body
    assert "10.0.0.1" not in body
    assert "10.0.0.3" not in body


def test_filter_by_module(auth_client, seeded_audit):
    body = _audit_page(auth_client, module="finance")
    assert "10.0.0.1" in body and "10.0.0.3" in body
    assert "10.0.0.2" not in body


def test_filter_by_action(auth_client, seeded_audit):
    body = _audit_page(auth_client, action="delete")
    assert "10.0.0.3" in body
    assert "10.0.0.1" not in body


def test_filter_by_affected_record(auth_client, seeded_audit):
    """The important one: who changed THIS invoice?"""
    body = _audit_page(auth_client, entity_type="invoices", entity_id="1001")
    assert "10.0.0.1" in body
    assert "10.0.0.2" not in body
    assert "10.0.0.3" not in body


def test_filter_by_date_range(auth_client, seeded_audit):
    body = _audit_page(auth_client, date_from="2026-03-01", date_to="2026-04-01")
    assert "10.0.0.2" in body
    assert "10.0.0.1" not in body
    assert "10.0.0.3" not in body


def test_filters_combine(auth_client, seeded_audit):
    body = _audit_page(auth_client, user="alice", module="finance", action="update")
    assert "10.0.0.1" in body
    assert "10.0.0.3" not in body


def test_no_filter_shows_everything(auth_client, seeded_audit):
    body = _audit_page(auth_client)
    assert "10.0.0.1" in body and "10.0.0.2" in body and "10.0.0.3" in body


def test_diff_is_rendered_as_old_and_new(auth_client, seeded_audit):
    body = _audit_page(auth_client, entity_type="invoices", entity_id="1001")
    # Assert on the rendered <dd> elements, not the bare class names — those
    # also appear in the page's <style> block and would pass on an empty table.
    assert 'class="audit-val-old' in body
    assert 'class="audit-val-new' in body
    assert "<dt>total</dt>" in body
    old_cell = body.split('class="audit-val-old', 1)[1][:200]
    assert "100" in old_cell
    assert "200" in body.split('class="audit-val-new', 1)[1][:200]


def test_legacy_free_text_details_still_render(auth_client, seeded_audit):
    body = _audit_page(auth_client, entity_type="owners")
    assert "Created owner" in body


# ═══ pagination ═══════════════════════════════════════════════════════════════

def test_pagination_never_loads_the_whole_table(app, auth_client, clean_audit):
    from blueprints.system.routes import AUDIT_PAGE_SIZE

    n = AUDIT_PAGE_SIZE * 2 + 5
    with app.app_context():
        conn = db.get_db()
        with conn:
            conn.executemany(
                "INSERT INTO audit_log(timestamp,username,action,module,entity_type,entity_id,details)"
                " VALUES(?,?,?,?,?,?,?)",
                [(f"2026-05-{(i % 28) + 1:02d} 12:00:00", "bulk", "update",
                  "crm", "pets", str(i), f"row-marker-{i}") for i in range(n)],
            )
        conn.close()

    page1 = _audit_page(auth_client)
    assert page1.count("row-marker-") <= AUDIT_PAGE_SIZE * 2  # marker appears in cell + title
    assert f"1 / 3" in page1 or "Page" in page1

    page3 = _audit_page(auth_client, page=3)
    assert "row-marker-" in page3
    # Page 3 holds the last 5 rows only — it must not be a full-table dump.
    assert page3.count("<tr>") < n


def test_page_number_is_sanitised(auth_client, seeded_audit):
    # Negative / absurd page numbers must not 500 or produce a negative OFFSET.
    assert auth_client.get("/system/audit?page=-4").status_code == 200
    assert auth_client.get("/system/audit?page=abc").status_code == 200
    assert auth_client.get("/system/audit?page=99999").status_code == 200


def test_audit_page_requires_authorisation(client):
    resp = client.get("/system/audit")
    assert resp.status_code in (302, 401, 403)
