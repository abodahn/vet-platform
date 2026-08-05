# -*- coding: utf-8 -*-
"""Putting the prospect's clinic name on the demo.

A vet looking at "عيادة أليفي التجريبية" is looking at somebody else's clinic.
The same screens carrying HIS clinic's name stop being a demonstration and
start being a preview.

The only thing that must never happen is this command pointing at a real
clinic, so the slug guard gets more tests than the rename does.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "scripts"))

import demo_brand  # noqa: E402
import models.database as db  # noqa: E402
from models import tenancy  # noqa: E402


@pytest.fixture
def demo_tenant(app, tmp_path):
    """One clinic called 'demo', with a real schema behind it."""
    saved = tenancy._registry_path
    tenancy.configure(str(tmp_path / "tenants.db"))
    path = str(tmp_path / "demo.db")
    with tenancy._registry() as conn:
        conn.execute(
            "INSERT INTO tenants (slug, name, db_path, status) VALUES (?,?,?,?)",
            ("demo", "Demo", path, "active"))
        conn.commit()
    with tenancy.use("demo"):
        db.use_sqlite(path)
        db.init_db(admin_user="admin", admin_pass="brand-fixture-pass")
    yield "demo"
    tenancy.configure(saved)


def _clinic(slug):
    with tenancy.use(slug):
        conn = db.get_db()
        try:
            return dict(conn.execute(
                "SELECT name, name_ar, doctor_name, phone FROM clinic WHERE id=1"
            ).fetchone())
        finally:
            conn.close()


# ── the guard ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("slug", ["nilevet", "cairo-vet", "hatem", "clinic1"])
def test_it_refuses_to_rename_a_real_clinic(slug):
    """The failure this prevents is a paying customer opening their system to
    find a stranger's clinic name on every page and every printed invoice."""
    with pytest.raises(SystemExit):
        demo_brand.main(["--slug", slug, "--name-ar", "عيادة النيل"])


@pytest.mark.parametrize("slug", ["demo", "demo2", "vet-demo", "staging", "test-clinic"])
def test_it_allows_obvious_demo_slugs(slug):
    demo_brand._guard(slug)   # must not raise


# ── the rename ───────────────────────────────────────────────────────────────

def test_it_puts_the_arabic_name_on_the_clinic(demo_tenant):
    demo_brand.main(["--slug", "demo", "--name-ar", "عيادة النيل البيطرية"])
    assert _clinic("demo")["name_ar"] == "عيادة النيل البيطرية"


def test_the_latin_name_does_not_keep_saying_aleefy(demo_tenant):
    """Screens that are not localised fall back to the Latin column. Leaving it
    behind puts the wrong clinic's name on exactly the pages nobody checks."""
    demo_brand.main(["--slug", "demo", "--name-ar", "عيادة النيل البيطرية"])
    assert "Aleefy" not in _clinic("demo")["name"]


def test_the_doctor_and_phone_come_along(demo_tenant):
    demo_brand.main(["--slug", "demo", "--name-ar", "عيادة النيل",
                     "--doctor", "د. أحمد سالم", "--phone", "01001234567"])
    c = _clinic("demo")
    assert c["doctor_name"] == "د. أحمد سالم"
    assert c["phone"] == "01001234567"


def test_reset_puts_the_generic_demo_back(demo_tenant):
    """The nightly job re-seeds anyway, but you need this between two meetings
    on the same afternoon."""
    demo_brand.main(["--slug", "demo", "--name-ar", "عيادة النيل"])
    demo_brand.main(["--slug", "demo", "--reset"])
    c = _clinic("demo")
    assert c["name_ar"] == demo_brand.DEMO_DEFAULTS["name_ar"]
    assert c["name"] == demo_brand.DEMO_DEFAULTS["name"]


def test_it_needs_a_name_or_reset(demo_tenant):
    with pytest.raises(SystemExit):
        demo_brand.main(["--slug", "demo"])


# ── it has to find the registry on its own ───────────────────────────────────
#
# The first version of this script died with UnknownTenant on the live server
# while the clinic plainly existed: models.tenancy keeps its registry path in a
# module global that only create_app() sets, and a CLI script never builds an
# app. scripts/preflight.py had the identical bug, found the same day. The
# fixture above configured tenancy by hand, so the tests passed and the command
# did not work.

def test_it_configures_the_registry_itself(app, tmp_path, monkeypatch):
    """No create_app, no fixture setting it up -- exactly how it runs in a car
    outside a clinic."""
    import demo_brand
    from models import tenancy

    registry = tmp_path / "tenants.db"
    monkeypatch.setattr(tenancy, "_registry_path", "")
    monkeypatch.setenv("TENANT_REGISTRY", str(registry))

    demo_brand._configure_registry()
    assert tenancy._registry_path == str(registry)


def test_it_falls_back_to_the_path_create_app_uses(app, tmp_path, monkeypatch):
    import demo_brand
    from config import Config
    from models import tenancy

    monkeypatch.setattr(tenancy, "_registry_path", "")
    monkeypatch.delenv("TENANT_REGISTRY", raising=False)
    monkeypatch.setattr(Config, "DATABASE_PATH", str(tmp_path / "platform.db"))

    demo_brand._configure_registry()
    assert tenancy._registry_path == os.path.join(str(tmp_path), "tenants.db")
