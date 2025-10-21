"""
Migration script to add flash sales columns to existing database
Run this if you already have a database with products
"""
import sqlite3
import sys
from pathlib import Path


def migrate_flash_sales(db_path: str):
    """Add flash sale columns to product table"""
    conn = sqlite3.connect(db_path)
    
    try:
        # Check if columns already exist
        cursor = conn.execute("PRAGMA table_info(product)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'flash_price_cents' not in columns:
            print("Adding flash_price_cents column...")
            conn.execute("""
                ALTER TABLE product 
                ADD COLUMN flash_price_cents INTEGER CHECK(flash_price_cents >= 0)
            """)
            print("✓ Added flash_price_cents")
        else:
            print("✓ flash_price_cents already exists")
        
        if 'sale_start' not in columns:
            print("Adding sale_start column...")
            conn.execute("ALTER TABLE product ADD COLUMN sale_start TIMESTAMP")
            print("✓ Added sale_start")
        else:
            print("✓ sale_start already exists")
        
        if 'sale_end' not in columns:
            print("Adding sale_end column...")
            conn.execute("ALTER TABLE product ADD COLUMN sale_end TIMESTAMP")
            print("✓ Added sale_end")
        else:
            print("✓ sale_end already exists")
        
        # Create flash_sales_log table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flash_sales_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('SALE_START','SALE_END','RATE_LIMIT','CIRCUIT_OPEN')),
                event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE
            )
        """)
        print("✓ Created flash_sales_log table")
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_flash_log_product 
            ON flash_sales_log(product_id)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_flash_log_time 
            ON flash_sales_log(event_time)
        """)
        print("✓ Created indexes")
        
        conn.commit()
        print("\nFlash sales migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\nMigration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    db_path = root / "app.sqlite"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Please run the app first to create the database")
        sys.exit(1)
    
    print(f"Migrating database at: {db_path}\n")
    migrate_flash_sales(str(db_path))