#!/usr/bin/env python3
"""Delete or soft-disable products by name or sku.

Usage examples:
  # soft-disable by name (interactive)
  python scripts/delete_products.py --by name "widget a" "widget b"

  # soft-disable non-interactive (used by automation)
  python scripts/delete_products.py --mode soft --by name --yes "widget a" "widget b" "widget c"

  # hard delete by sku (requires no FK refs)
  python scripts/delete_products.py --mode hard --by sku --yes sku-123 sku-456

The script will back up the DB before making changes.
"""
from __future__ import annotations
import argparse
import sqlite3
import shutil
import datetime
import os
from pathlib import Path
from typing import List


def get_db_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    return Path(os.environ.get("APP_DB_PATH", str(root / "app.sqlite")))


def backup_db(db_path: Path) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    bak = db_path.with_name(db_path.name + f".bak.{ts}")
    shutil.copy2(db_path, bak)
    return bak


def rows_for_names(conn: sqlite3.Connection, names: List[str]) -> List[sqlite3.Row]:
    placeholders = ",".join(["?" for _ in names])
    q = f"SELECT id, name, sku, price_cents, stock, active FROM product WHERE lower(trim(name)) IN ({placeholders})"
    cur = conn.execute(q, [n.strip().lower() for n in names])
    return cur.fetchall()


def rows_for_skus(conn: sqlite3.Connection, skus: List[str]) -> List[sqlite3.Row]:
    placeholders = ",".join(["?" for _ in skus])
    q = f"SELECT id, name, sku, price_cents, stock, active FROM product WHERE lower(trim(sku)) IN ({placeholders})"
    cur = conn.execute(q, [s.strip().lower() for s in skus])
    return cur.fetchall()


def soft_disable_by_name(conn: sqlite3.Connection, names: List[str]) -> int:
    placeholders = ",".join(["?" for _ in names])
    q = f"UPDATE product SET active = 0 WHERE lower(trim(name)) IN ({placeholders})"
    conn.execute(q, [n.strip().lower() for n in names])
    cur = conn.execute("SELECT changes()")
    return cur.fetchone()[0]


def soft_disable_by_sku(conn: sqlite3.Connection, skus: List[str]) -> int:
    placeholders = ",".join(["?" for _ in skus])
    q = f"UPDATE product SET active = 0 WHERE lower(trim(sku)) IN ({placeholders})"
    conn.execute(q, [s.strip().lower() for s in skus])
    cur = conn.execute("SELECT changes()")
    return cur.fetchone()[0]


def hard_delete_by_name(conn: sqlite3.Connection, names: List[str]) -> int:
    placeholders = ",".join(["?" for _ in names])
    q = f"DELETE FROM product WHERE lower(trim(name)) IN ({placeholders})"
    conn.execute(q, [n.strip().lower() for n in names])
    cur = conn.execute("SELECT changes()")
    return cur.fetchone()[0]


def hard_delete_by_sku(conn: sqlite3.Connection, skus: List[str]) -> int:
    placeholders = ",".join(["?" for _ in skus])
    q = f"DELETE FROM product WHERE lower(trim(sku)) IN ({placeholders})"
    conn.execute(q, [s.strip().lower() for s in skus])
    cur = conn.execute("SELECT changes()")
    return cur.fetchone()[0]


def pretty_print(rows: List[sqlite3.Row]):
    if not rows:
        print("(no matching products)")
        return
    print("Matched products:")
    for r in rows:
        print(f"  id={r['id']}, name={r['name']!r}, sku={r['sku']!r}, price_cents={r['price_cents']}, stock={r['stock']}, active={r['active']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("items", nargs='+', help="Product names or SKUs depending on --by")
    p.add_argument("--by", choices=["name","sku"], default="name", help="Match by product name or sku (default name)")
    p.add_argument("--auto", action="store_true", help="Auto-detect whether to match by sku when possible")
    p.add_argument("--mode", choices=["soft","hard"], default="soft", help="soft = set active=0 (default), hard = DELETE row")
    p.add_argument("--yes", action="store_true", help="Skip confirmation and run immediately")
    args = p.parse_args()

    db_path = get_db_path()
    if not db_path.exists():
        print(f"DB file not found: {db_path}")
        return 2

    print(f"Using DB: {db_path}")
    bak = backup_db(db_path)
    print(f"Backup created: {bak}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Schema introspection: detect if `sku` column exists
        cur = conn.cursor()
        try:
            cur.execute("PRAGMA table_info(product)")
            cols = [r[1] for r in cur.fetchall()]
        except Exception:
            cols = []

        has_sku = 'sku' in cols

        # If --auto is set, and sku column exists, and items look like skus (simple heuristic), prefer sku
        if args.auto and has_sku:
            # heuristic: if all items contain a dash or look non-space, treat as sku
            def looks_like_sku(s: str) -> bool:
                s = s.strip()
                return bool(s) and ("-" in s or s.isalnum())

            if all(looks_like_sku(it) for it in args.items):
                chosen_by = 'sku'
            else:
                chosen_by = args.by
        else:
            chosen_by = args.by
        if chosen_by == 'name':
            found = rows_for_names(conn, args.items)
        else:
            # If sku column missing, fall back to name search
            if not has_sku:
                print("Warning: sku column not present in product table; falling back to name matching")
                found = rows_for_names(conn, args.items)
            else:
                found = rows_for_skus(conn, args.items)

        pretty_print(found)

        if not found:
            print("Nothing to do.")
            return 0

        if not args.yes:
            ans = input(f"Proceed with mode={args.mode} on {len(found)} rows? [y/N]: ")
            if ans.lower() != 'y':
                print("Aborted by user.")
                return 0

        conn.execute("BEGIN")
        if args.mode == 'soft':
            if chosen_by == 'name':
                changed = soft_disable_by_name(conn, args.items)
            else:
                if not has_sku:
                    print("Warning: sku column not present; soft-disabling by name")
                    changed = soft_disable_by_name(conn, args.items)
                else:
                    changed = soft_disable_by_sku(conn, args.items)
        else:
            if chosen_by == 'name':
                changed = hard_delete_by_name(conn, args.items)
            else:
                if not has_sku:
                    print("Warning: sku column not present; deleting by name")
                    changed = hard_delete_by_name(conn, args.items)
                else:
                    changed = hard_delete_by_sku(conn, args.items)

        conn.execute("COMMIT")
        print(f"OK. Rows affected: {changed}")

        # show after state (best-effort)
        if chosen_by == 'name':
            after = rows_for_names(conn, args.items)
        else:
            if not has_sku:
                after = rows_for_names(conn, args.items)
            else:
                after = rows_for_skus(conn, args.items)
        print("After:")
        pretty_print(after)

    finally:
        conn.close()


if __name__ == '__main__':
    main()
