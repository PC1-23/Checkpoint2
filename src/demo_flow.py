"""
Demo script to exercise checkout success and decline flows against the local DB.
Uses the DEV-ONLY seed data (Demo User, Demo Widget). For classroom demos only.

Run:
  python -m src.demo_flow
"""

from __future__ import annotations

import os
from pathlib import Path

from .dao import get_connection, SalesRepo, ProductRepo
from .payment import process as payment_process
from .main import init_db
from .seed import seed_users, seed_products


def main():
    root = Path(__file__).resolve().parents[1]
    db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        ensure_core_tables(conn)
        seed(conn)

        # Look up seeded IDs
        user_id = conn.execute("SELECT id FROM user WHERE name='Demo User'").fetchone()[0]
        product_id = conn.execute("SELECT id FROM product WHERE name='Demo Widget'").fetchone()[0]

        repo = SalesRepo(conn, ProductRepo())

        print("-- Success flow --")
        sale_id = repo.checkout_transaction(
            user_id=user_id,
            cart=[(product_id, 1)],
            pay_method="CARD",
            payment_cb=payment_process,
        )
        print(f"Sale created: {sale_id}")
        stock = conn.execute("SELECT stock FROM product WHERE id=?", (product_id,)).fetchone()[0]
        print(f"Stock after purchase: {stock}")

        print("-- Decline flow --")
        try:
            repo.checkout_transaction(
                user_id=user_id,
                cart=[(product_id, 1)],
                pay_method="DECLINE_TEST",
                payment_cb=payment_process,
            )
        except Exception as e:
            print(f"Declined as expected: {e}")
        cnt = conn.execute("SELECT COUNT(*) FROM sale").fetchone()[0]
        print(f"Total sales in DB: {cnt}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
