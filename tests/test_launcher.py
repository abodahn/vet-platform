"""
Launcher module-card tests.
Verifies the Pet Shop and Data Migration cards are present and their routes resolve.
"""


def test_launcher_loads(auth_client):
    resp = auth_client.get("/")
    assert resp.status_code == 200


def test_launcher_has_petshop_card(auth_client):
    resp = auth_client.get("/")
    body = resp.data.decode("utf-8", errors="replace")
    assert "Pet Shop" in body or "petshop" in body, "Pet Shop card missing from launcher"


def test_launcher_has_migration_card(auth_client):
    resp = auth_client.get("/")
    body = resp.data.decode("utf-8", errors="replace")
    assert "Migration" in body or "migration" in body, "Migration card missing from launcher"


def test_petshop_route_resolves(app):
    """url_for('petshop.index') must not raise BuildError."""
    with app.test_request_context("/"):
        from flask import url_for
        url = url_for("petshop.index")
        assert url.startswith("/")


def test_migration_route_resolves(app):
    """url_for('migration.index') must not raise BuildError."""
    with app.test_request_context("/"):
        from flask import url_for
        url = url_for("migration.index")
        assert url.startswith("/")


def test_petshop_page_loads(auth_client):
    resp = auth_client.get("/petshop/", follow_redirects=True)
    assert resp.status_code in (200, 302)


def test_migration_page_loads(auth_client):
    resp = auth_client.get("/migration/", follow_redirects=True)
    assert resp.status_code in (200, 302)
