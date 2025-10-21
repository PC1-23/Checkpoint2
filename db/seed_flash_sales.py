"""
Seed script to add flash sale products for testing
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def seed_flash_sales(db_path: str):
    """Add sample flash sale products"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    try:
        # First, run migration if needed
        cursor = conn.execute("PRAGMA table_info(product)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'flash_price_cents' not in columns:
            print("⚠️  Flash sale columns not found. Run migration first:")
            print("python -m db.migrate_flash_sales")
            return
        
        # Create flash sale products
        now = datetime.now()
        
        flash_products = [
            {
                'name': 'Lightning Laptop Pro',
                'price_cents': 129999,  # $1,299.99
                'flash_price_cents': 99999,  # $999.99 (23% off)
                'stock': 15,
                'sale_start': now - timedelta(hours=1),  # Started 1 hour ago
                'sale_end': now + timedelta(hours=2),  # Ends in 2 hours
            },
            {
                'name': 'Flash Gaming Mouse',
                'price_cents': 7999,  # $79.99
                'flash_price_cents': 4999,  # $49.99 (38% off)
                'stock': 50,
                'sale_start': now - timedelta(minutes=30),
                'sale_end': now + timedelta(hours=4),
            },
            {
                'name': 'Quick Charge Power Bank',
                'price_cents': 4999,  # $49.99
                'flash_price_cents': 2999,  # $29.99 (40% off)
                'stock': 8,  # Low stock for urgency
                'sale_start': now - timedelta(minutes=15),
                'sale_end': now + timedelta(hours=1),
            },
            {
                'name': 'Wireless Earbuds Flash',
                'price_cents': 15999,  # $159.99
                'flash_price_cents': 11999,  # $119.99 (25% off)
                'stock': 100,
                'sale_start': now,
                'sale_end': now + timedelta(hours=6),
            },
            {
                'name': '4K Monitor Deal',
                'price_cents': 39999,  # $399.99
                'flash_price_cents': 29999,  # $299.99 (25% off)
                'stock': 25,
                'sale_start': now - timedelta(hours=2),
                'sale_end': now + timedelta(hours=3),
            },
        ]
        
        print("Seeding flash sale products...\n")
        
        for product in flash_products:
            # Check if product already exists
            existing = conn.execute(
                "SELECT id FROM product WHERE name = ?",
                (product['name'],)
            ).fetchone()
            
            if existing:
                # Update existing product with flash sale
                conn.execute("""
                    UPDATE product 
                    SET flash_price_cents = ?,
                        sale_start = ?,
                        sale_end = ?,
                        active = 1,
                        stock = ?
                    WHERE name = ?
                """, (
                    product['flash_price_cents'],
                    product['sale_start'].isoformat(),
                    product['sale_end'].isoformat(),
                    product['stock'],
                    product['name']
                ))
                print(f"✓ Updated: {product['name']}")
            else:
                # Insert new product
                conn.execute("""
                    INSERT INTO product (name, price_cents, flash_price_cents, stock, sale_start, sale_end, active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (
                    product['name'],
                    product['price_cents'],
                    product['flash_price_cents'],
                    product['stock'],
                    product['sale_start'].isoformat(),
                    product['sale_end'].isoformat()
                ))
                print(f"✓ Created: {product['name']}")
            
            # Show details
            savings = product['price_cents'] - product['flash_price_cents']
            savings_pct = (savings / product['price_cents']) * 100
            print(f"   Regular: ${product['price_cents']/100:.2f}")
            print(f"   Flash: ${product['flash_price_cents']/100:.2f}")
            print(f"   Savings: {savings_pct:.0f}% off")
            print(f"   Stock: {product['stock']}")
            print(f"   Ends: {product['sale_end'].strftime('%Y-%m-%d %H:%M')}")
            print()
        
        conn.commit()
        print("Flash sale products seeded successfully!\n")
        print("Start your app and visit: http://127.0.0.1:5000/flash/products")
        
    except Exception as e:
        conn.rollback()
        print(f"Seeding failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    db_path = root / "app.sqlite"
    
    if not db_path.exists():
        print("Database not found at", db_path)
        print("Run the app first to create the database")
    else:
        seed_flash_sales(str(db_path))