"""Test helpers: create an isolated sqlite DB from schema and seed test data."""
from pathlib import Path
import sqlite3
import os


def create_test_db(db_path: str):
    """Create a sqlite DB at db_path and initialize schema from db/init.sql."""
    root = Path(__file__).resolve().parents[2]
    schema_file = root / "db" / "init.sql"
    if not schema_file.exists():
        raise FileNotFoundError("db/init.sql not found")
    with open(schema_file, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executescript(sql)
    conn.commit()
    conn.close()


def seed_partner_and_key(db_path: str, partner_name: str = "test-partner", api_key: str = "test-key") -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO partner (name, format) VALUES (?, 'json')", (partner_name,))
    pid = cur.lastrowid
    cur.execute("INSERT INTO partner_api_keys (partner_id, api_key, description) VALUES (?, ?, ?)", (pid, api_key, "test"))
    conn.commit()
    conn.close()
    return pid
