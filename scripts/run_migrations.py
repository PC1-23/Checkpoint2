#!/usr/bin/env python3
"""Simple migration runner for local/dev use.

Usage:
  python scripts/run_migrations.py

This runner applies all `.sql` files in `migrations/` in sorted order to
the DB pointed by the APP_DB_PATH env var or repo `app.sqlite`.
"""
import sqlite3
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = os.environ.get("APP_DB_PATH") or str(ROOT / "app.sqlite")
MIGRATIONS_DIR = ROOT / "migrations"


def apply_migration(path: Path, conn: sqlite3.Connection):
    sql = path.read_text()
    cur = conn.cursor()
    cur.executescript(sql)
    conn.commit()


def main():
    m = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not m:
        print("No migrations found")
        return
    print(f"Applying {len(m)} migrations to {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    try:
        for p in m:
            print(f"Applying {p.name}")
            apply_migration(p, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
