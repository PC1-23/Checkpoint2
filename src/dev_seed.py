"""
DEV-ONLY SEED HELPER (temporary until Partner A provides user/product schema & seed)
-------------------------------------------------------------------------------
This module creates minimal 'user' and 'product' tables and inserts demo rows so
Partner B can run the UI and tests locally. REMOVE once Partner A adds the official
schema and seed process.

Run:
  python -m src.dev_seed

Environment:
  APP_DB_PATH  - path to SQLite file (default: ./app.sqlite)
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3

from .main import init_db
from .dao import get_connection


def ensure_core_tables(conn: sqlite3.Connection):
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL,
            stock INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        """
    )


def seed(conn: sqlite3.Connection):
    # idempotent-ish seed
    u = conn.execute("SELECT id FROM user WHERE name = ?", ("Demo User",)).fetchone()
    if not u:
        conn.execute("INSERT INTO user(name) VALUES(?)", ("Demo User",))
    p = conn.execute("SELECT id FROM product WHERE name = ?", ("Demo Widget",)).fetchone()
    if not p:
        conn.execute(
            "INSERT INTO product(name, price_cents, stock, active) VALUES(?, ?, ?, 1)",
            ("Demo Widget", 1299, 10),
        )
    conn.commit()


def main():
    root = Path(__file__).resolve().parents[1]
    db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        ensure_core_tables(conn)
        seed(conn)
    finally:
        conn.close()
    print(f"Seeded demo data in {db_path} (DEV-ONLY).")


if __name__ == "__main__":
    main()
