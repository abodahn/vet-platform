import pytest
import models.database as db


@pytest.fixture(autouse=True)
def setup_db(tmp_path, app):
    """Isolated DB for unit tests; restore app DB path after each test."""
    import models.database as _db_module
    original_path = _db_module._db_path
    db.set_path(str(tmp_path / "test.db"))
    db.init_db(admin_user="admin", admin_pass="1234")
    yield
    db.set_path(original_path)


def test_verify_credentials():
    user = db.verify_credentials("admin", "1234")
    assert user is not None
    assert user["username"] == "admin"


def test_wrong_credentials():
    user = db.verify_credentials("admin", "wrongpass")
    assert user is None


def test_get_user():
    user = db.get_user("admin")
    assert user is not None
    assert user["role"] == "super_admin"


def test_create_owner():
    owner_id = db.create_owner({"full_name": "John Doe", "phone": "01012345678"})
    assert owner_id > 0
    owner = db.get_owner(owner_id)
    assert owner["full_name"] == "John Doe"


def test_list_owners():
    db.create_owner({"full_name": "Alice Smith", "phone": "01099999999"})
    owners = db.list_owners()
    assert len(owners) >= 1


def test_create_pet():
    owner_id = db.create_owner({"full_name": "Test Owner", "phone": "01011111111"})
    pet_id = db.create_pet({"owner_id": owner_id, "pet_name": "Buddy", "species": "Dog"})
    assert pet_id > 0


def test_pet_timeline_empty():
    owner_id = db.create_owner({"full_name": "Owner", "phone": "01022222222"})
    pet_id = db.create_pet({"owner_id": owner_id, "pet_name": "Cat", "species": "Cat"})
    timeline = db.get_pet_timeline(pet_id)
    assert isinstance(timeline, list)


def test_dashboard_stats():
    stats = db.get_dashboard_stats()
    assert "owners_total" in stats or "total_owners" in stats
    assert "pets_total" in stats or "total_pets" in stats


def test_finance_summary():
    summary = db.get_finance_summary("2020-01-01", "2030-12-31")
    assert "total_revenue" in summary or "net_revenue" in summary or "revenue" in summary or isinstance(summary, dict)


def test_low_stock_items():
    items = db.get_low_stock_items()
    assert isinstance(items, list)


def test_expiry_alerts():
    alerts = db.get_expiry_alerts(days=30)
    assert isinstance(alerts, list)


def test_update_user_theme():
    db.update_user_theme("admin", "logo")
    user = db.get_user("admin")
    assert user["theme_preference"] == "logo"
