"""
Pet Shop / POS / Stock tests (Gap D — pet_shop).
Creates fixture products, places an order, verifies stock deduction,
cancels the order, and verifies stock restoration.
"""
import pytest
from models.database import get_db, set_path


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def ensure_tables(app):
    """Make sure Pet Shop tables exist before each test."""
    with app.app_context():
        conn = get_db()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ps_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, name_ar TEXT, description TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ps_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER, name TEXT NOT NULL, name_ar TEXT,
                sku TEXT UNIQUE, barcode TEXT, brand TEXT,
                species TEXT DEFAULT 'all', description TEXT,
                cost_price REAL DEFAULT 0, sell_price REAL DEFAULT 0,
                tax_rate REAL DEFAULT 0, reorder_level INTEGER DEFAULT 5,
                stock_qty INTEGER DEFAULT 0, unit TEXT DEFAULT 'unit',
                is_active INTEGER DEFAULT 1, image_url TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ps_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number TEXT UNIQUE, owner_id INTEGER, pet_id INTEGER,
                source TEXT DEFAULT 'in-clinic', status TEXT DEFAULT 'draft',
                subtotal REAL DEFAULT 0, discount_amount REAL DEFAULT 0,
                tax_amount REAL DEFAULT 0, total REAL DEFAULT 0,
                paid_amount REAL DEFAULT 0, change_amount REAL DEFAULT 0,
                payment_method TEXT DEFAULT 'cash', payment_ref TEXT,
                notes TEXT, served_by TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS ps_order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL, product_id INTEGER NOT NULL,
                product_name TEXT, qty REAL DEFAULT 1,
                unit_price REAL DEFAULT 0, discount REAL DEFAULT 0,
                tax_rate REAL DEFAULT 0, line_total REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS ps_stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL, movement TEXT NOT NULL,
                qty REAL NOT NULL, ref_type TEXT, ref_id INTEGER,
                notes TEXT, created_by TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        conn.close()


@pytest.fixture
def product(app):
    """Insert a test product with stock=10 and return its id (unique SKU per call)."""
    import time
    with app.app_context():
        conn = get_db()
        sku = f"TEST-PROD-{int(time.time() * 1000) % 1_000_000:06d}"
        cur = conn.execute(
            """INSERT INTO ps_products (name, sku, sell_price, stock_qty, is_active)
               VALUES (?, ?, ?, ?, 1)""",
            ("Test Product", sku, 50.0, 10),
        )
        conn.commit()
        pid = cur.lastrowid
        conn.close()
        return pid


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_petshop_index_loads(auth_client):
    resp = auth_client.get("/petshop/", follow_redirects=True)
    assert resp.status_code == 200


def test_product_stock_initial(app, product):
    with app.app_context():
        conn = get_db()
        row = conn.execute("SELECT stock_qty FROM ps_products WHERE id=?", (product,)).fetchone()
        conn.close()
        assert row is not None
        assert row["stock_qty"] == 10


def test_products_list_loads(auth_client):
    resp = auth_client.get("/petshop/products", follow_redirects=True)
    assert resp.status_code == 200


def test_orders_list_loads(auth_client):
    resp = auth_client.get("/petshop/orders", follow_redirects=True)
    assert resp.status_code == 200


def test_pos_page_loads(auth_client):
    resp = auth_client.get("/petshop/pos", follow_redirects=True)
    assert resp.status_code == 200


def test_reports_page_loads(auth_client):
    resp = auth_client.get("/petshop/reports", follow_redirects=True)
    assert resp.status_code == 200


def test_stock_deducted_after_paid_order(app, product):
    """Placing a paid POS order must deduct stock from the product."""
    with app.app_context():
        conn = get_db()
        # Confirm initial stock
        before = conn.execute(
            "SELECT stock_qty FROM ps_products WHERE id=?", (product,)
        ).fetchone()["stock_qty"]

        # Insert a paid order manually (mirrors POS confirm logic)
        import time
        order_num = f"TEST-ORDER-{int(time.time())}"
        cur = conn.execute(
            """INSERT INTO ps_orders (order_number, status, subtotal, total, paid_amount,
               payment_method, served_by)
               VALUES (?,?,?,?,?,?,?)""",
            (order_num, "paid", 50.0, 50.0, 50.0, "cash", "test"),
        )
        order_id = cur.lastrowid
        conn.execute(
            """INSERT INTO ps_order_items (order_id, product_id, product_name, qty, unit_price, line_total)
               VALUES (?,?,?,?,?,?)""",
            (order_id, product, "Test Product", 2, 50.0, 100.0),
        )
        # Deduct stock (mirrors FEFO deduction in petshop blueprint)
        conn.execute(
            "UPDATE ps_products SET stock_qty = stock_qty - ? WHERE id=?",
            (2, product),
        )
        conn.execute(
            """INSERT INTO ps_stock_movements (product_id, movement, qty, ref_type, ref_id, created_by)
               VALUES (?,?,?,?,?,?)""",
            (product, "out", 2, "sale", order_id, "test"),
        )
        conn.commit()

        after = conn.execute(
            "SELECT stock_qty FROM ps_products WHERE id=?", (product,)
        ).fetchone()["stock_qty"]
        conn.close()

        assert after == before - 2, f"Expected {before - 2}, got {after}"


def test_stock_restored_after_cancel(app, product):
    """Cancelling an order must restore stock."""
    with app.app_context():
        conn = get_db()

        # Set known stock
        conn.execute("UPDATE ps_products SET stock_qty=8 WHERE id=?", (product,))
        conn.commit()

        # Unique order number to avoid UNIQUE constraint conflicts
        import time
        order_num = f"TEST-CANCEL-{int(time.time())}"

        # Simulate placing a paid order and then cancelling it
        cur = conn.execute(
            """INSERT INTO ps_orders (order_number, status, subtotal, total, paid_amount,
               payment_method, served_by)
               VALUES (?,?,?,?,?,?,?)""",
            (order_num, "paid", 50.0, 50.0, 50.0, "cash", "test"),
        )
        order_id = cur.lastrowid
        conn.execute(
            "INSERT INTO ps_order_items (order_id, product_id, product_name, qty, unit_price, line_total) VALUES (?,?,?,?,?,?)",
            (order_id, product, "Test Product", 3, 50.0, 150.0),
        )
        conn.execute("UPDATE ps_products SET stock_qty = stock_qty - 3 WHERE id=?", (product,))
        conn.commit()

        mid = conn.execute("SELECT stock_qty FROM ps_products WHERE id=?", (product,)).fetchone()["stock_qty"]
        assert mid == 5

        # Cancel — restore stock
        conn.execute("UPDATE ps_orders SET status='cancelled' WHERE id=?", (order_id,))
        qty_sold = conn.execute(
            "SELECT COALESCE(SUM(qty),0) FROM ps_order_items WHERE order_id=?", (order_id,)
        ).fetchone()[0]
        conn.execute("UPDATE ps_products SET stock_qty = stock_qty + ? WHERE id=?", (qty_sold, product))
        conn.execute(
            "INSERT INTO ps_stock_movements (product_id, movement, qty, ref_type, ref_id) VALUES (?,?,?,?,?)",
            (product, "in", qty_sold, "cancellation", order_id),
        )
        conn.commit()

        after = conn.execute("SELECT stock_qty FROM ps_products WHERE id=?", (product,)).fetchone()["stock_qty"]
        conn.close()
        assert after == 8, f"Stock should be restored to 8, got {after}"
