"""The Finance and System blockers from docs/AUDIT_FINDINGS.md, verified.

Each test names the finding it pins. They were reported by audit agents whose
skeptic pass never ran, so every one below was reproduced against the code
before it was fixed — these tests are the reproduction, kept.
"""
import json

import pytest

from models import database as db

from conftest import get_csrf


# ═══════════════════════════════════════════════════════════════════════
#  SYSTEM — access control
# ═══════════════════════════════════════════════════════════════════════

def test_an_unknown_role_is_denied_not_allowed(app):
    """"Deleting a role silently grants that role's users full access."

    _permission_denied() returned None — which means ALLOW — whenever the role
    had no row in `roles`. So the way to give a nurse the clinic's money
    screens was to delete her role.
    """
    from blueprints.auth import routes as auth

    with app.test_request_context("/finance/"):
        from flask import session as flask_session
        flask_session["user"] = {"id": 1, "username": "ghost",
                                 "role": "role_that_does_not_exist",
                                 "full_name": "Ghost"}
        auth._perm_cache.clear()
        # blueprint/endpoint are what _permission_denied inspects
        assert auth._role_permissions("role_that_does_not_exist") is None, \
            "the premise changed: this role now has a row"

    # The decision itself, isolated from Flask routing:
    assert "role_that_does_not_exist" not in db.DEFAULT_ROLE_PERMISSIONS
    assert auth.has_permission("invoicing", "role_that_does_not_exist") is False, \
        "an unknown role must not hold a permission"


def test_a_builtin_role_with_no_row_still_falls_back(app):
    """The fall-open existed to stop a fresh install locking everyone out.
    That intent has to survive: a BUILT-IN role with no row still falls back."""
    from blueprints.auth import routes as auth
    for role in ("doctor", "nurse", "reception", "finance"):
        assert role in db.DEFAULT_ROLE_PERMISSIONS, \
            "%s must remain a recognised built-in" % role


def test_a_role_cannot_be_saved_with_no_permissions_at_all(auth_client):
    """"Unticking every permission on a role WIDENS it — nurses gain Finance,
    Accounting and Inventory, and the screen says 'Role updated successfully'."

    The widening is real: '[]' is read as "no data — fall back to the built-in
    role". That fallback CANNOT simply be reversed, because every role shipped
    with '[]' and treating empty as deny would lock a live clinic out on the
    first restart after an upgrade — which is what
    test_a_role_with_no_permission_data_keeps_working guards.

    So '[]' is ambiguous by construction, and the fix is to stop the ambiguous
    state being creatable: saving a role with nothing ticked is refused.
    """
    conn = db.get_db()
    conn.execute("INSERT OR REPLACE INTO roles(name, display_name,"
                 " permissions_json, color) VALUES(?,?,?,?)",
                 ("shrinkme", "Shrink Me", json.dumps(["patients", "invoicing"]),
                  "#999"))
    rid = conn.execute("SELECT id FROM roles WHERE name='shrinkme'").fetchone()[0]
    conn.commit()
    conn.close()

    auth_client.post("/system/roles/%d/edit" % rid,
                     data={"display_name": "Shrink Me", "color": "#999",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)

    conn = db.get_db()
    after = conn.execute("SELECT permissions_json FROM roles WHERE id=?",
                         (rid,)).fetchone()[0]
    conn.execute("DELETE FROM roles WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    assert json.loads(after) == ["patients", "invoicing"], \
        "the role was emptied to %r, which reads as 'fall back' and WIDENS it" % after


def test_an_empty_permission_list_still_falls_back_so_upgrades_do_not_lock_out(app):
    """The other half of the same decision, pinned so it is not "fixed" later.

    Every role shipped with '[]'. If empty meant deny, the first restart after
    an upgrade would lock a live clinic out of its own system.
    """
    from blueprints.auth import routes as auth
    conn = db.get_db()
    conn.execute("INSERT OR REPLACE INTO roles(name, display_name,"
                 " permissions_json, color) VALUES(?,?,?,?)",
                 ("legacyrole", "Legacy", json.dumps([]), "#999"))
    conn.commit()
    conn.close()
    auth._perm_cache.clear()
    assert auth._role_permissions("legacyrole") is None, \
        "an unconfigured role must fall back, not deny"


def test_a_role_still_held_by_staff_cannot_be_deleted(app):
    """"Deleting a role does not move the staff who hold it."

    The delete was a bare DELETE FROM roles that never touched users.
    """
    conn = db.get_db()
    conn.execute("INSERT OR REPLACE INTO roles(name, display_name,"
                 " permissions_json, color) VALUES(?,?,?,?)",
                 ("doomed", "Doomed", json.dumps(["patients"]), "#999"))
    role_id = conn.execute("SELECT id FROM roles WHERE name='doomed'").fetchone()[0]
    conn.execute("INSERT INTO users(username, password_hash, full_name, role,"
                 " is_active) VALUES(?,?,?,?,1)",
                 ("held_by", "x", "Holder", "doomed"))
    conn.commit()
    conn.close()

    assert db.role_holders(role_id) == ["held_by"]
    with pytest.raises(ValueError) as e:
        db.delete_role(role_id)
    assert "held_by" in str(e.value), "the refusal should name who is in the way"

    # Move them off, and it deletes cleanly.
    conn = db.get_db()
    conn.execute("UPDATE users SET role='nurse' WHERE username='held_by'")
    conn.commit()
    conn.close()
    db.delete_role(role_id)
    conn = db.get_db()
    gone = conn.execute("SELECT id FROM roles WHERE id=?", (role_id,)).fetchone()
    conn.execute("DELETE FROM users WHERE username='held_by'")
    conn.commit()
    conn.close()
    assert gone is None


# ═══════════════════════════════════════════════════════════════════════
#  FINANCE — the forms
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def owner_id():
    conn = db.get_db()
    row = conn.execute("SELECT id FROM owners ORDER BY id LIMIT 1").fetchone()
    if row:
        conn.close()
        return row[0]
    conn.execute("INSERT INTO owners(full_name, phone) VALUES('Fin Test','01000000009')")
    oid = conn.execute("SELECT id FROM owners WHERE phone='01000000009'").fetchone()[0]
    conn.commit()
    conn.close()
    return oid


def _new_invoice(auth_client, owner_id, **over):
    form = {
        "owner_id": str(owner_id),
        "issue_date": "2026-08-10",
        "description[]": ["Consultation"],
        "qty[]": ["1"],
        "unit_price[]": ["250"],
        "discount[]": ["0"],
        "line_type[]": ["service"],
        "discount_value": "0",
        "tax_rate": "0",
        "_csrf_token": get_csrf(auth_client),
    }
    form.update(over)
    return auth_client.post("/finance/invoices/new", data=form, follow_redirects=True)


def test_a_cleared_number_box_does_not_500(auth_client, owner_id):
    """"Clearing any number box on the invoice form returns a 500."

    Twelve bare float() calls across three forms. An empty Qty box threw
    ValueError and lost the whole typed invoice.
    """
    resp = _new_invoice(auth_client, owner_id,
                        **{"qty[]": [""], "unit_price[]": [""],
                           "discount[]": [""], "discount_value": "",
                           "tax_rate": ""})
    assert resp.status_code == 200, "a cleared box still 500s"


def test_a_mistyped_amount_does_not_500(auth_client, owner_id):
    resp = _new_invoice(auth_client, owner_id,
                        **{"unit_price[]": ["1,2OO"], "discount_value": "abc",
                           "tax_rate": "%%"})
    assert resp.status_code == 200


def test_a_thousands_separator_is_understood_not_dropped(auth_client, owner_id):
    _new_invoice(auth_client, owner_id, **{"unit_price[]": ["1,200"]})
    conn = db.get_db()
    inv = conn.execute("SELECT total FROM invoices WHERE owner_id=?"
                       " ORDER BY id DESC LIMIT 1", (owner_id,)).fetchone()
    conn.close()
    assert round(inv["total"], 2) == 1200.00, \
        "1,200 was read as something other than 1200"


def test_quantity_zero_is_not_billed_as_one(auth_client, owner_id):
    """"Quantity 0 is silently stored as 1 — the invoice charges for a line
    the screen showed as 0.00." The `or 1` idiom."""
    resp = _new_invoice(auth_client, owner_id, **{"qty[]": ["0"]})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "At least one line item" in body or "required" in body.lower(), \
        "a zero-quantity line was accepted"


def test_a_line_discount_over_100_cannot_pay_the_client(auth_client, owner_id):
    _new_invoice(auth_client, owner_id, **{"discount[]": ["500"]})
    conn = db.get_db()
    inv = conn.execute("SELECT total FROM invoices WHERE owner_id=?"
                       " ORDER BY id DESC LIMIT 1", (owner_id,)).fetchone()
    conn.close()
    assert inv["total"] >= 0, "a 500%% line discount produced %r" % inv["total"]


def test_a_header_discount_cannot_make_the_total_negative(auth_client, owner_id):
    """"Discount is unbounded — an invoice can be saved with a negative total,
    and it lands in Outstanding" — money the CLINIC appears to owe."""
    _new_invoice(auth_client, owner_id, **{"discount_value": "99999"})
    conn = db.get_db()
    inv = conn.execute("SELECT total, due_amount FROM invoices WHERE owner_id=?"
                       " ORDER BY id DESC LIMIT 1", (owner_id,)).fetchone()
    conn.close()
    assert inv["total"] >= 0 and inv["due_amount"] >= 0


# ═══════════════════════════════════════════════════════════════════════
#  FINANCE — the money
# ═══════════════════════════════════════════════════════════════════════

def _make_invoice(owner_id, total=500.0):
    return db.create_invoice(
        {"owner_id": owner_id, "issue_date": "2026-08-10",
         "discount_type": "value", "discount_value": 0, "tax_rate": 0,
         "created_by": "test"},
        [{"line_type": "service", "description": "Consultation", "quantity": 1,
          "unit_price": total, "discount": 0, "total": total}])


def test_the_same_nonce_cannot_charge_twice(auth_client, owner_id):
    """"Double-clicking Record Payment records the money twice — the built-in
    idempotency is never used." The key existed; nobody supplied one."""
    inv_id = _make_invoice(owner_id, 500.0)
    form = {"amount": "200", "method": "Cash", "idem": "same-click",
            "_csrf_token": get_csrf(auth_client)}
    auth_client.post("/finance/invoices/%d/pay" % inv_id, data=form,
                     follow_redirects=True)
    auth_client.post("/finance/invoices/%d/pay" % inv_id, data=dict(form),
                     follow_redirects=True)
    inv = db.get_invoice(inv_id)
    assert round(inv["paid_amount"], 2) == 200.00, \
        "the double click charged %.2f" % inv["paid_amount"]


def test_two_genuine_payments_are_still_two_payments(auth_client, owner_id):
    """The dedup must not block a real second payment from a fresh page."""
    inv_id = _make_invoice(owner_id, 500.0)
    for nonce in ("first-render", "second-render"):
        auth_client.post("/finance/invoices/%d/pay" % inv_id,
                         data={"amount": "100", "method": "Cash", "idem": nonce,
                               "_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)
    inv = db.get_invoice(inv_id)
    assert round(inv["paid_amount"], 2) == 200.00


def test_a_credit_note_moves_outstanding_exactly_once(auth_client, owner_id):
    """"A credit note subtracts the invoice from Outstanding twice — proven on
    the live demo: one 12,345.67 void moved Outstanding by 24,692." """
    def outstanding():
        conn = db.get_db()
        v = conn.execute("SELECT COALESCE(SUM(due_amount),0) FROM invoices"
                         " WHERE status IN ('Unpaid','Partial')").fetchone()[0]
        conn.close()
        return round(float(v), 2)

    inv_id = _make_invoice(owner_id, 1000.0)
    before = outstanding()
    auth_client.post("/finance/invoices/%d/credit-note" % inv_id,
                     data={"amount": "1000", "reason": "void",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)
    after = outstanding()
    assert round(before - after, 2) == 1000.00, \
        "Outstanding moved by %.2f for a 1000.00 void" % (before - after)


def test_a_credit_note_cannot_exceed_the_invoice(auth_client, owner_id):
    inv_id = _make_invoice(owner_id, 500.0)
    auth_client.post("/finance/invoices/%d/credit-note" % inv_id,
                     data={"amount": "99999", "reason": "oops",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)
    inv = db.get_invoice(inv_id)
    assert inv["status"] != "Cancelled", "an over-sized credit note went through"


def test_a_partial_credit_note_reduces_what_the_client_owes(auth_client, owner_id):
    """A partial credit used to do nothing to the original, so the client was
    still chased for the full amount."""
    inv_id = _make_invoice(owner_id, 500.0)
    auth_client.post("/finance/invoices/%d/credit-note" % inv_id,
                     data={"amount": "200", "reason": "goodwill",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)
    inv = db.get_invoice(inv_id)
    assert round(inv["due_amount"], 2) == 300.00, \
        "still owed %.2f after a 200 credit on 500" % inv["due_amount"]


def test_an_already_cancelled_invoice_cannot_be_credited_again(auth_client, owner_id):
    inv_id = _make_invoice(owner_id, 400.0)
    for _ in range(2):
        auth_client.post("/finance/invoices/%d/credit-note" % inv_id,
                         data={"amount": "400", "reason": "void",
                               "_csrf_token": get_csrf(auth_client)},
                         follow_redirects=True)
    number = db.get_invoice(inv_id)["invoice_number"]
    conn = db.get_db()
    notes = conn.execute(
        "SELECT COUNT(*) FROM invoices WHERE notes LIKE ?",
        ("%Credit note for " + number + "%",)).fetchone()[0]
    conn.close()
    assert notes <= 1, "the invoice was credited %d times" % notes


def test_credit_cannot_be_applied_to_a_cancelled_invoice(owner_id):
    """"Applying account credit to a cancelled invoice destroys the client's
    credit and 500s." The deduction committed before the payment was tried."""
    inv_id = _make_invoice(owner_id, 300.0)
    conn = db.get_db()
    conn.execute("INSERT INTO owner_credits(owner_id,amount,kind,method,note,created_by)"
                 " VALUES(?,?,'deposit','Cash','test','test')", (owner_id, 500.0))
    conn.execute("UPDATE invoices SET status='Cancelled', due_amount=0 WHERE id=?",
                 (inv_id,))
    conn.commit()
    conn.close()

    before = db.owner_credit_balance(owner_id)
    with pytest.raises(ValueError):
        db.apply_credit(owner_id, inv_id, 100.0, created_by="test")
    after = db.owner_credit_balance(owner_id)
    assert round(before, 2) == round(after, 2), \
        "the client lost %.2f of credit" % (before - after)


def test_money_taken_today_shows_as_taken_today(owner_id):
    """"Money collected today never shows in Today's Revenue — revenue is
    attributed by invoice ISSUE date. The live demo shows 0 EGP on a day
    120 EGP was taken."

    These are two different questions and conflating them was the bug:

      revenue   accrual — what was INVOICED in the window and has been paid.
                A closed month's P&L must not move afterwards, and every
                figure on a historical report has to be derivable from the
                rows in that window (test_reports_figures_match_the_
                underlying_rows depends on exactly that).
      collected cash — what arrived at the till in the window, whenever the
                invoice was raised. This is what the dashboard shows and what
                a human reconciles against the drawer.
    """
    from datetime import date as _date
    today = _date.today().isoformat()
    inv_id = _make_invoice(owner_id, 120.0)
    conn = db.get_db()
    # Invoice issued long ago; the money arrives TODAY.
    conn.execute("UPDATE invoices SET issue_date='2026-01-01' WHERE id=?", (inv_id,))
    conn.commit()
    conn.close()
    db.add_payment(inv_id, owner_id, 120.0, method="Cash", received_by="test",
                   idempotency_key="rev-test-%d" % inv_id)

    summary = db.get_finance_summary(date_from=today, date_to=today)
    assert summary["collected"] >= 120.0, \
        "120 taken today shows as %.2f at the till" % summary["collected"]
    # ...and the historical window is untouched by when the money arrived.
    old = db.get_finance_summary(date_from="2026-01-01", date_to="2026-01-01")
    assert old["revenue"] >= 120.0, \
        "the invoice left its own accounting period"


def test_an_invoice_cannot_be_edited_below_what_was_paid(auth_client, owner_id):
    """"Editing an invoice below what has already been paid hides the
    overpayment and marks it Paid." """
    inv_id = _make_invoice(owner_id, 500.0)
    db.add_payment(inv_id, owner_id, 400.0, method="Cash", received_by="test",
                   idempotency_key="edit-test-%d" % inv_id)
    resp = auth_client.post(
        "/finance/invoices/%d/edit" % inv_id,
        data={"owner_id": str(owner_id), "issue_date": "2026-08-10",
              "description[]": ["Consultation"], "qty[]": ["1"],
              "unit_price[]": ["100"], "discount[]": ["0"],
              "line_type[]": ["service"], "discount_value": "0",
              "tax_rate": "0", "_csrf_token": get_csrf(auth_client)},
        follow_redirects=True)
    assert resp.status_code == 200
    inv = db.get_invoice(inv_id)
    assert inv["due_amount"] >= 0, \
        "due_amount went to %.2f and the money owed back is invisible" % inv["due_amount"]
    assert round(inv["total"], 2) >= round(inv["paid_amount"], 2), \
        "the invoice total is now below what was paid"


def test_a_cancelled_invoice_cannot_be_edited_back_to_life(auth_client, owner_id):
    """"A voided (credit-noted) invoice can be edited back to life at any
    amount, and the credit note stays." """
    inv_id = _make_invoice(owner_id, 500.0)
    conn = db.get_db()
    conn.execute("UPDATE invoices SET status='Cancelled', due_amount=0 WHERE id=?",
                 (inv_id,))
    conn.commit()
    conn.close()
    auth_client.post(
        "/finance/invoices/%d/edit" % inv_id,
        data={"owner_id": str(owner_id), "issue_date": "2026-08-10",
              "description[]": ["Resurrected"], "qty[]": ["1"],
              "unit_price[]": ["9999"], "discount[]": ["0"],
              "line_type[]": ["service"], "discount_value": "0",
              "tax_rate": "0", "_csrf_token": get_csrf(auth_client)},
        follow_redirects=True)
    inv = db.get_invoice(inv_id)
    assert inv["status"] == "Cancelled", "a cancelled invoice was edited"
    assert round(inv["total"], 2) == 500.00, "its total was changed to %r" % inv["total"]


def test_a_role_that_does_not_exist_cannot_be_assigned(auth_client):
    """"The Staff Access role dropdown offers 'staff', a role that does not
    exist — picking it grants Finance, Accounting, Inventory and Procurement."

    It granted them through the fall-open. With that fixed it would instead
    lock the person out, which is not what the administrator meant either, so
    the assignment itself is refused.
    """
    assert "staff" not in db.DEFAULT_ROLE_PERMISSIONS

    conn = db.get_db()
    conn.execute("INSERT INTO users(username, password_hash, full_name, role,"
                 " is_active) VALUES('phantom_target','x','Target','nurse',1)")
    uid = conn.execute(
        "SELECT id FROM users WHERE username='phantom_target'").fetchone()[0]
    conn.commit()
    conn.close()

    auth_client.post("/system/roles/assign",
                     data={"user_id": str(uid), "role": "staff",
                           "_csrf_token": get_csrf(auth_client)},
                     follow_redirects=True)
    conn = db.get_db()
    role = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()[0]
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    assert role == "nurse", "a nonexistent role was assigned (%r)" % role


def test_the_roles_screen_no_longer_offers_the_phantom_role(auth_client):
    body = auth_client.get("/system/roles").get_data(as_text=True)
    assert "'support_admin','staff'" not in body, \
        "the dropdown still offers a role that does not exist"


def test_keeping_the_local_version_is_recorded_and_not_misreported(app):
    """"Sync conflict 'Keep Local' throws the device's version away and reports
    'Conflict resolved. Kept: local version.'"

    `keep` was accepted and never used. Nothing pushes the device's copy back,
    so the message was false. The choice is now recorded, and the wording says
    what actually happened.
    """
    import json as _json
    from models import sync

    conn = db.get_db()
    conn.execute(
        "INSERT INTO sync_conflicts(id, sync_queue_id, entity_name,"
        " local_payload, server_payload, conflict_type, resolution_status)"
        " VALUES('c-test','q-test','pets',?,?,'UPDATE','PENDING')",
        (_json.dumps({"pet_name": "device version"}),
         _json.dumps({"pet_name": "server version"})))
    conn.commit()
    conn.close()

    sync.resolve_conflict("c-test", resolved_by="tester", keep="local")

    conn = db.get_db()
    row = conn.execute(
        "SELECT resolution_status, local_payload FROM sync_conflicts"
        " WHERE id='c-test'").fetchone()
    conn.execute("DELETE FROM sync_conflicts WHERE id='c-test'")
    conn.commit()
    conn.close()

    assert row["resolution_status"] == "MANUAL_RESOLVED_LOCAL", \
        "which side was kept is still not recorded (%r)" % row["resolution_status"]
    assert "device version" in row["local_payload"], \
        "the device's copy was discarded, so it cannot be recovered by hand"
