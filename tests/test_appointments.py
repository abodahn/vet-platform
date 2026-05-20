def test_schedule_page(auth_client):
    resp = auth_client.get("/appointments/")
    assert resp.status_code == 200


def test_new_appointment_form(auth_client):
    resp = auth_client.get("/appointments/new")
    assert resp.status_code == 200


def test_calendar_page(auth_client):
    resp = auth_client.get("/appointments/calendar")
    assert resp.status_code == 200
