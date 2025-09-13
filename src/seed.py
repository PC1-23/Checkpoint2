#!/usr/bin/env python3
import os
import sys
import sqlite3
from pathlib import Path

def get_connection(db_path):
    """Get database connection - copied from dao.py to avoid import issues"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def main():
    print("Starting seed script...")
    
    db_path = 'app.sqlite'
    print(f"Connecting to database: {db_path}")
    
    try:
        conn = get_connection(db_path)
        print("Database connection successful")
        
        # Insert multiple products
        products = [
            ("Laptop", 99999, 10),
            ("Wireless Mouse", 2999, 25),
            ("USB Cable", 1299, 50),
            ("Keyboard", 7999, 15),
            ("Monitor", 24999, 8),
        ]
        
        for name, price, stock in products:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO product (name, price_cents, stock) VALUES (?, ?, ?)",
                (name, price, stock)
            )
            print(f"Inserted {name} - rowcount: {cursor.rowcount}")
        
        conn.commit()
        print("Changes committed")
        
        # Check total products
        cursor = conn.execute("SELECT COUNT(*) FROM product")
        count = cursor.fetchone()[0]
        print(f"Total products: {count}")
        
        conn.close()
        print("Seed completed successfully!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
