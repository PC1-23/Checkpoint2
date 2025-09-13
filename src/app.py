from __future__ import annotations
from .product_repo import AProductRepo


import os
from pathlib import Path
from typing import Dict

from flask import Flask, redirect, render_template, request, session, url_for, flash
import sqlite3

from .dao import SalesRepo, ProductRepo, get_connection
from .payment import process as payment_process
from .main import init_db


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates")
    app.secret_key = os.environ.get("APP_SECRET_KEY", "dev-insecure-secret")

    root = Path(__file__).resolve().parents[1]
    db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))
    init_db(db_path)

    def get_conn():
        return get_connection(db_path)

    def get_repo(conn: sqlite3.Connection) -> SalesRepo:
        return SalesRepo(conn, AProductRepo(conn))

    @app.route("/")
    def index():
        return redirect(url_for("products"))

    @app.route("/products")
    def products():
        conn = get_conn()
        try:
            try:
                rows = conn.execute(
                    "SELECT id, name, price_cents, stock, active FROM product WHERE active = 1 ORDER BY id"
                ).fetchall()
            except Exception as e:
                rows = []
                flash(
                    "Product table not available. Partner A needs to add user/product schema and seed.",
                    "error",
                )
            return render_template("products.html", products=rows)
        finally:
            conn.close()

    @app.post("/cart/add")
    def cart_add():
        pid = int(request.form.get("product_id", 0))
        qty = int(request.form.get("qty", 1))
        if qty <= 0:
            flash("Quantity must be > 0", "error")
            return redirect(url_for("products"))
        cart: Dict[str, int] = session.get("cart", {})
        cart[str(pid)] = cart.get(str(pid), 0) + qty
        session["cart"] = cart
        flash("Added to cart", "info")
        return redirect(url_for("cart_view"))

    @app.get("/cart")
    def cart_view():
        cart: Dict[str, int] = session.get("cart", {})
        conn = get_conn()
        items = []
        total = 0
        try:
            for pid_str, qty in cart.items():
                pid = int(pid_str)
                prod = conn.execute(
                    "SELECT id, name, price_cents, stock, active FROM product WHERE id = ?",
                    (pid,),
                ).fetchone()
                if not prod:
                    continue
                unit = int(prod["price_cents"])
                items.append({
                    "id": pid,
                    "name": prod["name"],
                    "qty": qty,
                    "unit": unit,
                    "line": unit * qty,
                })
                total += unit * qty
        finally:
            conn.close()
        return render_template("cart.html", items=items, total=total)

    @app.post("/cart/clear")
    def cart_clear():
        session.pop("cart", None)
        flash("Cart cleared", "info")
        return redirect(url_for("products"))

    @app.post("/checkout")
    def checkout():
        pay_method = request.form.get("payment_method", "CARD")
        user_id = int(os.environ.get("APP_DEMO_USER_ID", "1"))
        cart: Dict[str, int] = session.get("cart", {})
        cart_list = [(int(pid), qty) for pid, qty in cart.items()]

        conn = get_conn()
        repo = get_repo(conn)
        try:
            sale_id = repo.checkout_transaction(
                user_id=user_id,
                cart=cart_list,
                pay_method=pay_method,
                payment_cb=payment_process,
            )
        except Exception as e:
            flash(str(e), "error")
            return redirect(url_for("cart_view"))
        finally:
            conn.close()

        session.pop("cart", None)
        flash(f"Checkout success. Sale #{sale_id}", "success")
        return redirect(url_for("receipt", sale_id=sale_id))

    @app.get("/receipt/<int:sale_id>")
    def receipt(sale_id: int):
        conn = get_conn()
        try:
            sale = conn.execute(
                "SELECT id, user_id, sale_time, total_cents, status FROM sale WHERE id = ?",
                (sale_id,),
            ).fetchone()
            items = conn.execute(
                "SELECT product_id, quantity, price_cents FROM sale_item WHERE sale_id = ?",
                (sale_id,),
            ).fetchall()
            payment = conn.execute(
                "SELECT method, amount_cents, status, ref FROM payment WHERE sale_id = ?",
                (sale_id,),
            ).fetchone()
        finally:
            conn.close()
        return render_template("receipt.html", sale=sale, items=items, payment=payment)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
