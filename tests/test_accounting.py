def test_accounting_dashboard(auth_client):
    resp = auth_client.get("/accounting/")
    assert resp.status_code == 200

def test_pl_report(auth_client):
    resp = auth_client.get("/accounting/pl")
    assert resp.status_code == 200

def test_expenses_list(auth_client):
    resp = auth_client.get("/accounting/expenses")
    assert resp.status_code == 200

def test_add_expense(auth_client):
    from conftest import get_csrf
    token = get_csrf(auth_client)
    resp = auth_client.post("/accounting/expenses/new", data={
        "category": "Medicines",
        "description": "Test expense",
        "amount": "500",
        "expense_date": "2026-01-15",
        "vendor": "Test Vendor",
        "payment_method": "Cash",
        "_csrf_token": token,
    }, follow_redirects=True)
    assert resp.status_code == 200

def test_cashflow(auth_client):
    resp = auth_client.get("/accounting/cashflow")
    assert resp.status_code == 200

def test_closing(auth_client):
    resp = auth_client.get("/accounting/closing")
    assert resp.status_code == 200

def test_budget_get(auth_client):
    resp = auth_client.get("/accounting/budget")
    assert resp.status_code == 200

def test_budget_post_persists(auth_client, app):
    """POSTing a target must actually change the row (regression: updated_at=NOW()
    once broke the whole UPDATE on the SQLite path)."""
    import models.database as db
    from conftest import get_csrf

    with app.app_context():
        conn = db.get_db()
        cat = conn.execute(
            "SELECT category FROM budget_targets ORDER BY id LIMIT 1"
        ).fetchone()["category"]
        conn.close()

    resp = auth_client.post("/accounting/budget", data={
        "category[]":    cat,
        "monthly_egp[]": "77777",
        "_csrf_token":   get_csrf(auth_client),
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Error saving budget" not in resp.data

    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT monthly_egp, updated_at FROM budget_targets WHERE category=?",
            (cat,)
        ).fetchone()
        conn.close()
    assert float(row["monthly_egp"]) == 77777.0
    assert row["updated_at"]
