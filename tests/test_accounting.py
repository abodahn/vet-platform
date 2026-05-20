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
