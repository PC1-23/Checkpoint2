import os
import sqlite3
import threading
from pathlib import Path

# Ensure we can import from src/
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DB_SQL = ROOT / "db" / "init.sql"
if str(SRC) not in sys.path:
	sys.path.insert(0, str(SRC))

from dao import SalesRepo, ProductRepo, get_connection  # type: ignore  # noqa: E402
from payment import process as payment_process  # type: ignore  # noqa: E402


def create_core_tables(conn: sqlite3.Connection):
	# Partner A stubs for tests
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


def apply_b_schema(conn: sqlite3.Connection):
	# Execute the Partner B schema from db/init.sql
	with open(DB_SQL, "r", encoding="utf-8") as f:
		sql = f.read()
	conn.executescript(sql)


def seed_user_product(conn: sqlite3.Connection, *, user_name: str = "Alice", product_name: str = "Widget", price_cents: int = 1000, stock: int = 10) -> tuple[int, int]:
	cur = conn.execute("INSERT INTO user(name) VALUES(?)", (user_name,))
	user_id = cur.lastrowid
	cur = conn.execute(
		"INSERT INTO product(name, price_cents, stock, active) VALUES(?, ?, ?, 1)",
		(product_name, price_cents, stock),
	)
	product_id = cur.lastrowid
	conn.commit()
	return user_id, product_id


def test_checkout_success(tmp_path):
	db_path = tmp_path / "test_success.sqlite"
	conn = get_connection(str(db_path))
	create_core_tables(conn)
	apply_b_schema(conn)
	user_id, product_id = seed_user_product(conn, price_cents=1234, stock=5)

	repo = SalesRepo(conn, ProductRepo())
	sale_id = repo.checkout_transaction(
		user_id,
		cart=[(product_id, 2)],
		pay_method="CARD",
		payment_cb=payment_process,
	)

	# Verify sale
	sale = conn.execute("SELECT id, user_id, total_cents, status FROM sale WHERE id = ?", (sale_id,)).fetchone()
	assert sale is not None
	assert sale["user_id"] == user_id
	assert sale["total_cents"] == 2 * 1234
	assert sale["status"] == "COMPLETED"

	# Verify sale items
	items = conn.execute("SELECT product_id, quantity, price_cents FROM sale_item WHERE sale_id = ?", (sale_id,)).fetchall()
	assert len(items) == 1
	assert items[0]["product_id"] == product_id
	assert items[0]["quantity"] == 2
	assert items[0]["price_cents"] == 1234

	# Verify payment
	pay = conn.execute("SELECT method, amount_cents, status, ref FROM payment WHERE sale_id = ?", (sale_id,)).fetchone()
	assert pay is not None
	assert pay["method"] == "CARD"
	assert pay["amount_cents"] == 2 * 1234
	assert pay["status"] == "APPROVED"
	assert isinstance(pay["ref"], str) and pay["ref"].startswith("REF-")

	# Stock decremented
	stock = conn.execute("SELECT stock FROM product WHERE id = ?", (product_id,)).fetchone()[0]
	assert stock == 3


def test_checkout_decline(tmp_path):
	db_path = tmp_path / "test_decline.sqlite"
	conn = get_connection(str(db_path))
	create_core_tables(conn)
	apply_b_schema(conn)
	user_id, product_id = seed_user_product(conn, price_cents=500, stock=3)

	repo = SalesRepo(conn, ProductRepo())
	try:
		repo.checkout_transaction(
			user_id,
			cart=[(product_id, 1)],
			pay_method="DECLINE_TEST",
			payment_cb=payment_process,
		)
		assert False, "Expected payment decline exception"
	except RuntimeError as e:
		assert "Payment declined" in str(e)

	# No sale or payment should be persisted
	cnt = conn.execute("SELECT COUNT(*) FROM sale").fetchone()[0]
	assert cnt == 0
	cnt = conn.execute("SELECT COUNT(*) FROM payment").fetchone()[0]
	assert cnt == 0
	# Stock unchanged
	stock = conn.execute("SELECT stock FROM product WHERE id = ?", (product_id,)).fetchone()[0]
	assert stock == 3


def test_checkout_concurrency_race(tmp_path):
	# Setup a file-backed DB so two connections can race
	db_path = tmp_path / "test_race.sqlite"
	main_conn = get_connection(str(db_path))
	create_core_tables(main_conn)
	apply_b_schema(main_conn)
	user_id, product_id = seed_user_product(main_conn, price_cents=200, stock=1)
	main_conn.close()

	results = []

	def worker(name: str):
		conn = get_connection(str(db_path))
		repo = SalesRepo(conn, ProductRepo())
		try:
			sale_id = repo.checkout_transaction(
				user_id,
				cart=[(product_id, 1)],
				pay_method="CARD",
				payment_cb=payment_process,
			)
			results.append((name, "ok", sale_id))
		except Exception as e:  # could be RuntimeError (insufficient) or sqlite3.OperationalError (locked)
			results.append((name, "err", str(e)))
		finally:
			conn.close()

	t1 = threading.Thread(target=worker, args=("t1",))
	t2 = threading.Thread(target=worker, args=("t2",))
	t1.start(); t2.start(); t1.join(); t2.join()

	oks = [r for r in results if r[1] == "ok"]
	errs = [r for r in results if r[1] == "err"]
	assert len(oks) == 1, f"expected exactly one success, got: {results}"
	assert len(errs) == 1, f"expected exactly one failure, got: {results}"

	# Validate final state
	check = get_connection(str(db_path))
	sale_cnt = check.execute("SELECT COUNT(*) FROM sale").fetchone()[0]
	assert sale_cnt == 1
	stock = check.execute("SELECT stock FROM product WHERE id = ?", (product_id,)).fetchone()[0]
	assert stock == 0
	check.close()

