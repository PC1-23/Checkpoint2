#!/usr/bin/env python3
import os
import sys
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

def get_connection(db_path):
    """Get database connection - copied from dao.py to avoid import issues"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def seed_users(conn):
    """Insert demo users with hashed passwords"""
    users = [
        ("John Doe", "john", "password123"),
        ("Jane Smith", "jane", "password123"), 
        ("Alice Johnson", "alice", "password123"),
    ]
    
    for name, username, password in users:
        # Check if user already exists
        existing = conn.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
        if not existing:
            # Hash the password before storing
            hashed_password = generate_password_hash(password)
            conn.execute(
                "INSERT INTO user (name, username, password) VALUES (?, ?, ?)",
                (name, username, hashed_password)
            )
            print(f"Inserted user: {username}")
    
    conn.commit()
    print(f"Seeded users with authentication")

def seed_products(conn):
    """Insert demo products (price in cents)"""
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
    print("Products seeded successfully!")

def main():
    """Main seeding function"""
    db_path = 'app.sqlite'
    print(f"Seeding database at: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"ERROR: Database file {db_path} not found!")
        print("Please run 'python -m src.main' first to initialize the database.")
        sys.exit(1)
    
    conn = get_connection(db_path)
    
    try:
        seed_users(conn)
        seed_products(conn)
        
        # Show what was inserted
        cursor = conn.execute("SELECT COUNT(*) FROM user")
        user_count = cursor.fetchone()[0]
        cursor = conn.execute("SELECT COUNT(*) FROM product WHERE active = 1")
        product_count = cursor.fetchone()[0]
        
        print(f"Total users: {user_count}")
        print(f"Total active products: {product_count}")
        
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()