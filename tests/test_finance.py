def test_finance_dashboard(auth_client):
    resp = auth_client.get("/finance/")
    assert resp.status_code == 200


def test_invoice_list(auth_client):
    resp = auth_client.get("/finance/invoices")
    assert resp.status_code == 200


def test_new_invoice_form(auth_client):
    resp = auth_client.get("/finance/invoices/new")
    assert resp.status_code == 200
