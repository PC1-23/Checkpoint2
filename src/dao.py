from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Callable, Iterable, List, Tuple


CartItem = Tuple[int, int]  # (product_id, qty)
PaymentCallback = Callable[[str, int], Tuple[str, str | None]]


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    # BEGIN IMMEDIATE to lock for stock-consistency (A5)
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


class ProductRepo:
    """Partner A facade used by B. Implemented by A.

    Expected methods (stubs here for type/reference only):
      - get_product(id) -> {id:int, name:str, price_cents:int, active:int, stock:int}
      - check_stock(id, qty) -> bool
    """

    def get_product(self, product_id: int):  # pragma: no cover - implemented by Partner A
        raise NotImplementedError

    def check_stock(self, product_id: int, qty: int) -> bool:  # pragma: no cover - implemented by Partner A
        raise NotImplementedError

    def decrement_stock(self, product_id: int, qty: int):  # optional; or use raw SQL within B
        raise NotImplementedError


class SalesRepo:
    def __init__(self, conn: sqlite3.Connection, product_repo: ProductRepo):
        self.conn = conn
        self.product_repo = product_repo

    def checkout_transaction(
        self,
        user_id: int,
        cart: Iterable[CartItem],
        pay_method: str,
        payment_cb: PaymentCallback,
    ) -> int:
        """Atomically process checkout and return sale_id.

        Steps:
        - Validate cart non-empty; validate products and current prices; recompute total.
        - Call payment_cb(method, amount_cents) to simulate payment.
        - If APPROVED, insert sale, sale_items, payment and decrement stock within one transaction.
        - If DECLINED, do not persist sale/items/stock; optionally log elsewhere.
        """
        items: List[CartItem] = [(pid, qty) for pid, qty in cart if qty > 0]
        if not items:
            raise ValueError("Cart is empty")

        # Recompute totals from current product prices to handle A3
        line_prices: List[Tuple[int, int, int]] = []  # (product_id, qty, unit_price)
        total_cents = 0
        for product_id, qty in items:
            prod = self._get_active_product(product_id)
            if prod is None:
                raise ValueError(f"Product {product_id} not found or inactive")
            if qty <= 0:
                raise ValueError("Quantity must be > 0")
            unit_price = int(prod["price_cents"])  # assume cents stored by A
            total_cents += unit_price * qty
            line_prices.append((product_id, qty, unit_price))

        # Process payment first, but only capture/record if we can commit (A5 handling left to app policy)
        status, ref = payment_cb(pay_method, total_cents)
        if status != "APPROVED":
            # A4: payment declined – nothing persisted
            raise RuntimeError("Payment declined")

        # Persist sale + items + payment and decrement stock atomically
        with transaction(self.conn):
            # Double-check stock under transaction
            for product_id, qty, _ in line_prices:
                if not self._check_stock(product_id, qty):
                    raise RuntimeError("Insufficient stock at commit time")  # triggers rollback (A5)

            cur = self.conn.execute(
                "INSERT INTO sale(user_id, total_cents, status) VALUES(?, ?, 'COMPLETED')",
                (user_id, total_cents),
            )
            sale_id = cur.lastrowid

            for product_id, qty, unit_price in line_prices:
                self.conn.execute(
                    "INSERT INTO sale_item(sale_id, product_id, quantity, price_cents) VALUES(?, ?, ?, ?)",
                    (sale_id, product_id, qty, unit_price),
                )
                # Decrement stock using Partner A product table convention
                self.conn.execute(
                    "UPDATE product SET stock = stock - ? WHERE id = ?",
                    (qty, product_id),
                )

            self.conn.execute(
                "INSERT INTO payment(sale_id, method, amount_cents, status, ref) VALUES(?, ?, ?, 'APPROVED', ?)",
                (sale_id, pay_method, total_cents, ref),
            )

        return sale_id

    # --- helpers ---
    def _get_active_product(self, product_id: int):
        # Prefer Partner A repo if provided
        try:
            return self.product_repo.get_product(product_id)
        except NotImplementedError:
            pass
        row = self.conn.execute(
            "SELECT id, name, price_cents, stock, active FROM product WHERE id = ?",
            (product_id,),
        ).fetchone()
        if row and int(row["active"]) == 1:
            return row
        return None

    def _check_stock(self, product_id: int, qty: int) -> bool:
        # Prefer Partner A repo if provided
        try:
            return self.product_repo.check_stock(product_id, qty)
        except NotImplementedError:
            pass
        row = self.conn.execute(
            "SELECT stock FROM product WHERE id = ?",
            (product_id,),
        ).fetchone()
        return bool(row and int(row[0]) >= qty)
