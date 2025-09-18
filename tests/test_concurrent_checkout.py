"""
Integration/concurrency test: Simulates two users attempting to checkout the last item in stock at the same time.
Run directly: python -m tests.test_concurrent_checkout
"""
import threading
import sqlite3
from src.dao import SalesRepo, get_connection
from src.product_repo import AProductRepo
from src.payment import process as payment_process

DB_PATH = "app.sqlite"
USER_IDS = [1, 2]  # john, jane (assumes seeded users)
PRODUCT_NAME = "USB Cable"

def get_product_id():
    with get_connection(DB_PATH) as conn:
        row = conn.execute("SELECT id FROM product WHERE name=?", (PRODUCT_NAME,)).fetchone()
        return row[0] if row else None

def do_checkout(user_id, product_id, result_list, idx):
    try:
        with get_connection(DB_PATH) as conn:
            repo = SalesRepo(conn, AProductRepo(conn))
            sale_id = repo.checkout_transaction(
                user_id=user_id,
                cart=[(product_id, 1)],
                pay_method="CARD",
                payment_cb=payment_process,
            )
            result_list[idx] = f"User {user_id}: SUCCESS (sale_id={sale_id})"
    except Exception as e:
        result_list[idx] = f"User {user_id}: FAILED ({e})"

def main():
    # Reset USB Cable stock to 1 before running the test
    with get_connection(DB_PATH) as conn:
        conn.execute("UPDATE product SET stock=1 WHERE name=?", (PRODUCT_NAME,))
        conn.commit()
    product_id = get_product_id()
    if not product_id:
        print(f"Product '{PRODUCT_NAME}' not found.")
        return
    results = [None, None]
    threads = []
    for i in range(2):
        t = threading.Thread(target=do_checkout, args=(USER_IDS[i], product_id, results, i))
        threads.append(t)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for r in results:
        print(r)

if __name__ == "__main__":
    main()
