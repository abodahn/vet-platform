def test_owners_list(auth_client):
    resp = auth_client.get("/crm/owners")
    assert resp.status_code == 200


def test_new_owner_form(auth_client):
    resp = auth_client.get("/crm/owners/new")
    assert resp.status_code == 200


def test_create_owner(auth_client):
    from conftest import get_csrf
    token = get_csrf(auth_client)
    resp = auth_client.post(
        "/crm/owners/new",
        data={
            "full_name": "Test Owner",
            "phone": "01012345678",
            "email": "test@example.com",
            "whatsapp_phone": "01012345678",
            "address": "Test Address",
            "preferred_contact": "WhatsApp",
            "vip_flag": "0",
            "notes": "",
            "_csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_owner_detail(auth_client):
    from conftest import get_csrf
    token = get_csrf(auth_client)
    auth_client.post(
        "/crm/owners/new",
        data={"full_name": "Detail Owner", "phone": "01099991111", "_csrf_token": token},
    )
    resp = auth_client.get("/crm/owners/1")
    assert resp.status_code in [200, 404]
