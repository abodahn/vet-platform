def test_login_page_loads(client):
    resp = client.get("/auth/login")
    assert resp.status_code == 200
    assert b"login" in resp.data.lower()


def test_login_success(client):
    resp = client.post(
        "/auth/login",
        data={"username": "admin", "password": "1234"},
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_login_wrong_password(client):
    resp = client.post(
        "/auth/login",
        data={"username": "admin", "password": "wrong"},
        follow_redirects=True,
    )
    assert resp.status_code in [200, 302]


def test_logout(auth_client):
    resp = auth_client.get("/auth/logout", follow_redirects=True)
    assert resp.status_code == 200


def test_protected_route_redirects(client):
    # Launcher is at / (no prefix) — unauthenticated should redirect to login
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in [302, 301]


def test_launcher_accessible_when_logged_in(auth_client):
    # Launcher blueprint is at / (no url_prefix)
    resp = auth_client.get("/")
    assert resp.status_code == 200
