import pytest
import sqlite3
from datetime import datetime, timedelta
from src.flash_sales.flash_sale_manager import FlashSaleManager


@pytest.fixture
def db_conn():
    """Create in-memory test database"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Create product table with flash sale columns
    conn.execute("""
        CREATE TABLE product (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            flash_price_cents INTEGER,
            stock INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            sale_start TIMESTAMP,
            sale_end TIMESTAMP
        )
    """)
    
    # Create flash_sales_log table
    conn.execute("""
        CREATE TABLE flash_sales_log (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        )
    """)
    
    yield conn
    conn.close()


def test_is_flash_sale_active(db_conn):
    """Test flash sale active check"""
    now = datetime.now()
    
    # Insert active flash sale
    db_conn.execute("""
        INSERT INTO product (name, price_cents, flash_price_cents, stock, sale_start, sale_end, active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (
        "Test Product",
        10000,
        7500,
        10,
        (now - timedelta(hours=1)).isoformat(),
        (now + timedelta(hours=1)).isoformat()
    ))
    db_conn.commit()
    
    manager = FlashSaleManager(db_conn)
    assert manager.is_flash_sale_active(1) == True


def test_is_flash_sale_inactive_expired(db_conn):
    """Test expired flash sale"""
    now = datetime.now()
    
    # Insert expired flash sale
    db_conn.execute("""
        INSERT INTO product (name, price_cents, flash_price_cents, stock, sale_start, sale_end, active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (
        "Expired Product",
        10000,
        7500,
        10,
        (now - timedelta(hours=3)).isoformat(),
        (now - timedelta(hours=1)).isoformat()
    ))
    db_conn.commit()
    
    manager = FlashSaleManager(db_conn)
    assert manager.is_flash_sale_active(1) == False


def test_get_flash_products(db_conn):
    """Test getting all active flash products"""
    now = datetime.now()
    
    # Insert multiple products
    products = [
        ("Active Flash 1", 10000, 7500, (now - timedelta(hours=1)), (now + timedelta(hours=1))),
        ("Active Flash 2", 20000, 15000, (now - timedelta(minutes=30)), (now + timedelta(hours=2))),
        ("Expired Flash", 15000, 12000, (now - timedelta(hours=3)), (now - timedelta(hours=1))),
    ]
    
    for name, price, flash_price, start, end in products:
        db_conn.execute("""
            INSERT INTO product (name, price_cents, flash_price_cents, stock, sale_start, sale_end, active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (name, price, flash_price, 10, start.isoformat(), end.isoformat()))
    
    db_conn.commit()
    
    manager = FlashSaleManager(db_conn)
    flash_products = manager.get_flash_products()
    
    # Should only return 2 active flash sales
    assert len(flash_products) == 2
    assert all(p['flash_price_cents'] is not None for p in flash_products)


def test_get_effective_price(db_conn):
    """Test getting effective price (flash or regular)"""
    now = datetime.now()
    
    # Active flash sale
    db_conn.execute("""
        INSERT INTO product (name, price_cents, flash_price_cents, stock, sale_start, sale_end, active)
        VALUES (?, ?, ?, ?, ?, ?, 1)
    """, (
        "Flash Product",
        10000,
        7500,
        10,
        (now - timedelta(hours=1)).isoformat(),
        (now + timedelta(hours=1)).isoformat()
    ))
    
    # Regular product (no flash sale)
    db_conn.execute("""
        INSERT INTO product (name, price_cents, stock, active)
        VALUES (?, ?, ?, 1)
    """, ("Regular Product", 10000, 10))
    
    db_conn.commit()
    
    manager = FlashSaleManager(db_conn)
    
    # Flash product should return flash price
    assert manager.get_effective_price(1) == 7500
    
    # Regular product should return regular price
    assert manager.get_effective_price(2) == 10000


def test_log_event(db_conn):
    """Test logging flash sale events"""
    # Insert a product
    db_conn.execute("""
        INSERT INTO product (name, price_cents, stock, active)
        VALUES (?, ?, ?, 1)
    """, ("Test Product", 10000, 10))
    db_conn.commit()
    
    manager = FlashSaleManager(db_conn)
    manager.log_event(1, "SALE_START", "Flash sale started")
    
    # Check log entry was created
    log = db_conn.execute(
        "SELECT * FROM flash_sales_log WHERE product_id = 1"
    ).fetchone()
    
    assert log is not None
    assert log['event_type'] == "SALE_START"
    assert log['details'] == "Flash sale started"