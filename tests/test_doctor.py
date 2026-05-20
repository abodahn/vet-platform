def test_doctor_workspace(auth_client):
    resp = auth_client.get("/doctor/")
    assert resp.status_code == 200


def test_doctor_queue(auth_client):
    resp = auth_client.get("/doctor/queue")
    assert resp.status_code == 200


def test_doctor_patients(auth_client):
    resp = auth_client.get("/doctor/patients")
    assert resp.status_code == 200


def test_doctor_schedule(auth_client):
    resp = auth_client.get("/doctor/schedule")
    assert resp.status_code == 200


def test_doctor_stats(auth_client):
    resp = auth_client.get("/doctor/stats")
    assert resp.status_code == 200
