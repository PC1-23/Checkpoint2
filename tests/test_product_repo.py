import pytest
import sqlite3
import os
import sys
from pathlib import Path

# Simple test that doesn't rely on complex imports
def get_test_connection():
    """Create test database connection"""
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def create_test_schema(conn):
    """Create test schema"""
    conn.execute('''
        CREATE TABLE product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
            stock INTEGER NOT NULL CHECK(stock >= 0),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        )
    ''')
    
    # Insert test data
    conn.execute("INSERT INTO product (name, price_cents, stock, active) VALUES (?, ?, ?, ?)", 
                 ("Test Product", 1999, 10, 1))
    conn.execute("INSERT INTO product (name, price_cents, stock, active) VALUES (?, ?, ?, ?)", 
                 ("Inactive Product", 999, 5, 0))
    conn.commit()

def test_product_database_schema():
    """Test that product table can be created and queried"""
    conn = get_test_connection()
    create_test_schema(conn)
    
    # Test basic query
    cursor = conn.execute("SELECT COUNT(*) FROM product WHERE active = 1")
    count = cursor.fetchone()[0]
    assert count == 1
    
    # Test product retrieval
    cursor = conn.execute("SELECT name, price_cents, stock FROM product WHERE id = 1")
    product = cursor.fetchone()
    assert product['name'] == "Test Product"
    assert product['price_cents'] == 1999
    assert product['stock'] == 10
    
    conn.close()

def test_product_stock_operations():
    """Test stock decrement operations"""
    conn = get_test_connection()
    create_test_schema(conn)
    
    # Test stock decrement
    cursor = conn.execute("UPDATE product SET stock = stock - ? WHERE id = ? AND stock >= ?", (3, 1, 3))
    assert cursor.rowcount == 1
    
    # Verify stock changed
    cursor = conn.execute("SELECT stock FROM product WHERE id = 1")
    stock = cursor.fetchone()[0]
    assert stock == 7
    
    # Test insufficient stock
    cursor = conn.execute("UPDATE product SET stock = stock - ? WHERE id = ? AND stock >= ?", (10, 1, 10))
    assert cursor.rowcount == 0  # Should not update
    
    conn.close()

def test_product_active_filtering():
    """Test that inactive products are filtered out"""
    conn = get_test_connection()
    create_test_schema(conn)
    
    # Test that only active products are returned
    cursor = conn.execute("SELECT COUNT(*) FROM product WHERE active = 1")
    active_count = cursor.fetchone()[0]
    assert active_count == 1
    
    cursor = conn.execute("SELECT COUNT(*) FROM product")
    total_count = cursor.fetchone()[0]
    assert total_count == 2
    
    conn.close()