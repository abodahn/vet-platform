"""The /healthz contract that the fleet tooling depends on.

Four places poll this — the container HEALTHCHECK, provision.sh, upgrade.sh
and inventory.py — all with `curl -fsS`, which treats any non-2xx as failure.

They previously polled /api/v1/health, which is a 404 because the api_v1
blueprint is deliberately unregistered. Consequences: every container
reported unhealthy, the fleet inventory reported nothing, and upgrade.sh
rolled back EVERY upgrade — after it had already applied the Alembic
revision, leaving a new schema running old code.

The second half of the bug: /healthz used to return 503 whenever no recent
backup existed, which is the normal state of a fresh install until the first
02:00 run. Fixing only the URL would have reproduced the rollback loop.

So the contract these tests pin is: the HTTP status answers "can this serve
traffic?" and nothing else. Degradation is reported in the body.
"""
import json


def test_healthz_exists_and_is_public(client):
    """The route the fleet scripts actually poll."""
    r = client.get("/healthz")
    assert r.status_code in (200, 503), r.status_code
    assert r.headers["Content-Type"].startswith("application/json")


def test_api_v1_health_is_still_a_404(client):
    """Pins WHY this bug happened, so re-pointing at it fails loudly."""
    assert client.get("/api/v1/health").status_code == 404


def test_a_missing_backup_does_not_fail_the_probe(client, monkeypatch):
    """A fresh install has no backup until 02:00. That must not read as
    'unhealthy', or curl -fsS restarts the container and rolls back upgrades."""
    import models.backup as bk
    monkeypatch.setattr(bk, "health",
                        lambda: {"ok": False, "age_hours": None})
    r = client.get("/healthz")
    assert r.status_code == 200, "a stale backup must not fail the probe"
    body = r.get_json()
    assert body["status"] == "degraded"
    assert "backup" in body.get("degraded", []), "degradation must still be visible"


def test_unreachable_database_does_fail_the_probe(client, monkeypatch):
    """The one condition that genuinely means 'cannot serve traffic'."""
    import models.database as db
    def boom():
        raise RuntimeError("connection refused")
    monkeypatch.setattr(db, "get_db", boom)
    r = client.get("/healthz")
    assert r.status_code == 503
    assert r.get_json()["status"] == "down"


def test_public_body_leaks_nothing(client):
    """No FLASK_ENV, no paths, no row counts, no clinic identity."""
    body = client.get("/healthz").get_json()
    assert set(body) <= {"status", "version", "degraded"}, body
    blob = json.dumps(body).lower()
    for leak in ("development", "production", "sqlite", "postgres",
                 "c:\\", "d:\\", "/srv", "traceback"):
        assert leak not in blob, f"/healthz leaked {leak!r}"


def test_operator_detail_requires_the_key(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "API_V1_KEY", "s3cret-operator-key")

    plain = client.get("/healthz").get_json()
    assert "checks" not in plain

    wrong = client.get("/healthz",
                       headers={"Authorization": "Bearer nope"}).get_json()
    assert wrong == plain, "a wrong key must be indistinguishable from none"

    right = client.get(
        "/healthz",
        headers={"Authorization": "Bearer s3cret-operator-key"}).get_json()
    assert "checks" in right
    assert {"database", "scheduler", "backup"} <= set(right["checks"])
