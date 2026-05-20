def test_inventory_dashboard(auth_client):
    resp = auth_client.get("/inventory/")
    assert resp.status_code == 200


def test_items_list(auth_client):
    resp = auth_client.get("/inventory/items")
    assert resp.status_code == 200


def test_alerts_page(auth_client):
    resp = auth_client.get("/inventory/alerts")
    assert resp.status_code == 200
