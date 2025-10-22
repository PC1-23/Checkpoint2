"""Idempotent runtime DB migrations for local dev.

Run this after pulling changes if your local `app.sqlite` predates schema updates.
It will add the `diagnostics` column to `partner_ingest_jobs` if missing and ensure
`partner_ingest_diagnostics` table exists.

Usage:
  python scripts/apply_migrations.py [--db PATH]

If APP_DB_PATH environment variable is set it will be used unless --db is provided.
"""
import sqlite3
import argparse
import os
from pathlib import Path

MIGRATION_SQL = {
    "add_diagnostics_column": "ALTER TABLE partner_ingest_jobs ADD COLUMN diagnostics TEXT;",
    "create_diagnostics_table": '''
CREATE TABLE IF NOT EXISTS partner_ingest_diagnostics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    diagnostics TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES partner_ingest_jobs(id) ON DELETE CASCADE
);
''',
}


def get_db_path(cli_db: str | None) -> str:
    if cli_db:
        return cli_db
    env = os.environ.get("APP_DB_PATH")
    if env:
        return env
    # default to repo root app.sqlite
    root = Path(__file__).resolve().parents[1]
    return str(root / "app.sqlite")


def has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    return column in cols


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", help="Path to sqlite DB file")
    args = p.parse_args()

    db_path = get_db_path(args.db)
    print(f"Using DB: {db_path}")

    if not Path(db_path).exists():
        print("DB file does not exist; no migrations applied. If you intended to use a different DB, pass --db or set APP_DB_PATH.")
        return

    conn = sqlite3.connect(db_path)
    try:
        # Ensure pragmas for FK enforcement
        conn.execute("PRAGMA foreign_keys = ON;")

        # 1) Ensure diagnostics column exists on partner_ingest_jobs
        if not table_exists(conn, "partner_ingest_jobs"):
            print("Table partner_ingest_jobs not found. Skipping column addition.")
        else:
            if not has_column(conn, "partner_ingest_jobs", "diagnostics"):
                print("Adding 'diagnostics' column to partner_ingest_jobs...")
                try:
                    conn.execute(MIGRATION_SQL["add_diagnostics_column"])
                    conn.commit()
                    print("Column added.")
                except Exception as e:
                    print("Failed to add column:", e)
            else:
                print("Column 'diagnostics' already present on partner_ingest_jobs.")

        # 2) Ensure partner_ingest_diagnostics table exists
        if not table_exists(conn, "partner_ingest_diagnostics"):
            print("Creating table partner_ingest_diagnostics...")
            conn.executescript(MIGRATION_SQL["create_diagnostics_table"])
            conn.commit()
            print("Table created.")
        else:
            print("Table 'partner_ingest_diagnostics' already exists.")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
