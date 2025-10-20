from __future__ import annotations
from .product_repo import AProductRepo

from werkzeug.security import generate_password_hash, check_password_hash

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
        return redirect(url_for("login"))

    @app.route("/products")
    def products():
        q = request.args.get("q", "").strip()
        conn = get_conn()
        try:
            try:
                repo = AProductRepo(conn)
                if q:
                    rows = repo.search_products(q)
                else:
                    rows = repo.get_all_products()
            except Exception:
                rows = []
                flash(
                    "Product table not available. Partner A needs to add user/product schema and seed.",
                    "error",
                )
            return render_template("products.html", products=rows, q=q)
        finally:
            conn.close()

    @app.post("/cart/add")
    def cart_add():
        pid = int(request.form.get("product_id", 0))
        qty = int(request.form.get("qty", 1))
        
        if qty <= 0:
            flash("Quantity must be > 0", "error")
            return redirect(url_for("products"))
        
        # Check if product exists and is active
        conn = get_conn()
        try:
            repo = AProductRepo(conn)
            product = repo.get_product(pid)
            
            if not product:
                flash(f"Product ID {pid} not found", "error")
                return redirect(url_for("products"))
            
            # Check if sufficient stock
            if not repo.check_stock(pid, qty):
                flash(f"Only {product['stock']} in stock for {product['name']}", "error")
                return redirect(url_for("products"))
            
            # Add to cart if everything is valid
            cart = session.get("cart", {})
            cart[str(pid)] = cart.get(str(pid), 0) + qty
            session["cart"] = cart
            flash(f"Added {qty} x {product['name']} to cart", "info")
            return redirect(url_for("cart_view"))
            
        except ValueError:
            flash("Invalid product ID", "error")
            return redirect(url_for("products"))
        finally:
            conn.close()

    @app.get("/cart")
    def cart_view():
        cart: Dict[str, int] = session.get("cart", {})
        conn = get_conn()
        items = []
        total = 0
        try:
            repo = AProductRepo(conn)  # Use your repo instead of raw SQL
            for pid_str, qty in cart.items():
                pid = int(pid_str)
                prod = repo.get_product(pid)  # This returns flash price if active!
                
                if not prod:
                    continue
                
                unit = int(prod["price_cents"])
                items.append({
                    "id": pid,
                    "name": prod["name"],
                    "qty": qty,
                    "unit": unit,
                    "line": unit * qty,
                    "is_flash_sale": prod.get("is_flash_sale", False),
                    "original_price": prod.get("original_price", unit)
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

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            
            conn = get_conn()
            try:
                user = conn.execute(
                    "SELECT id, username, password FROM user WHERE username = ?", 
                    (username,)
                ).fetchone()
                
                if user:
                    try:
                        ok = check_password_hash(user["password"], password)
                    except ValueError as e:
                        # Handle unsupported hash types (e.g., scrypt) gracefully
                        flash("Your account uses an unsupported password hash. Please reset your password or contact support.", "error")
                        ok = False
                    if ok:
                        session["user_id"] = user["id"]
                        session["username"] = user["username"]
                        flash("Login successful!", "success")
                        return redirect(url_for("products"))
                
                flash("Invalid username or password", "error")
            finally:
                conn.close()
        
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been logged out", "info")
        return redirect(url_for("login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            name = request.form["name"]
            username = request.form["username"]
            password = request.form["password"]
            
            conn = get_conn()
            try:
                # Check if username exists
                existing = conn.execute("SELECT id FROM user WHERE username = ?", (username,)).fetchone()
                if existing:
                    flash("Username already exists", "error")
                else:
                    # Create user with PBKDF2 for compatibility across environments
                    hashed_password = generate_password_hash(password, method="pbkdf2:sha256")
                    conn.execute(
                        "INSERT INTO user (name, username, password) VALUES (?, ?, ?)",
                        (name, username, hashed_password)
                    )
                    conn.commit()
                    flash("Registration successful! Please login.", "success")
                    return redirect(url_for("login"))
            finally:
                conn.close()
        
        # Return register template (you'd need to create this)
        return render_template("register.html")

    # Add login requirement to protected routes
    def login_required(f):
        from functools import wraps
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please login to access this page", "error")
                return redirect(url_for("login"))
            return f(*args, **kwargs)
        return decorated_function
    @app.post("/checkout")
    def checkout():
        pay_method = request.form.get("payment_method", "CARD")
        user_id = session["user_id"]
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
    @app.post("/cart/remove")
    def cart_remove():
        pid = request.form.get("product_id")
        cart = session.get("cart", {})
        
        if pid in cart:
            del cart[pid]
            session["cart"] = cart
            flash("Item removed from cart", "info")
        
        return redirect(url_for("cart_view"))


    

    @app.get("/receipt/<int:sale_id>")
    def receipt(sale_id: int):
        conn = get_conn()
        try:
            sale = conn.execute(
                "SELECT id, user_id, sale_time, total_cents, status FROM sale WHERE id = ?",
                (sale_id,),
            ).fetchone()
            items = conn.execute(
                "SELECT si.product_id, p.name as product_name, si.quantity, si.price_cents "
                "FROM sale_item si JOIN product p ON si.product_id = p.id "
                "WHERE si.sale_id = ?",
                (sale_id,),
            ).fetchall()
            payment = conn.execute(
                "SELECT method, amount_cents, status, ref FROM payment WHERE sale_id = ?",
                (sale_id,),
            ).fetchone()
        finally:
            conn.close()
        return render_template("receipt.html", sale=sale, items=items, payment=payment)


    @app.get("/admin/flash-sale")
    def admin_flash_sale():
        """Admin page to manage flash sales"""
        conn = get_conn()
        try:
            cursor = conn.execute("""
                SELECT id, name, price_cents, flash_sale_active, flash_sale_price_cents
                FROM product 
                WHERE active = 1
                ORDER BY name
            """)
            products = cursor.fetchall()
            return render_template("admin_flash_sale.html", products=products)
        finally:
            conn.close()

    @app.post("/admin/flash-sale/set")
    def admin_flash_sale_set():
        """Set a product as flash sale"""
        product_id = int(request.form.get("product_id"))
        flash_price = float(request.form.get("flash_price"))
        flash_price_cents = int(flash_price * 100)
        
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE product 
                SET flash_sale_active = 1, flash_sale_price_cents = ?
                WHERE id = ?
            """, (flash_price_cents, product_id))
            conn.commit()
            flash("Flash sale activated!", "success")
        finally:
            conn.close()
        
        return redirect(url_for("admin_flash_sale"))

    @app.post("/admin/flash-sale/remove")
    def admin_flash_sale_remove():
        """Remove flash sale from product"""
        product_id = int(request.form.get("product_id"))
        
        conn = get_conn()
        try:
            conn.execute("""
                UPDATE product 
                SET flash_sale_active = 0, flash_sale_price_cents = NULL
                WHERE id = ?
            """, (product_id,))
            conn.commit()
            flash("Flash sale removed", "info")
        finally:
            conn.close()
        
        return redirect(url_for("admin_flash_sale"))

    return app
    

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="127.0.0.1", port=int(os.environ.get("PORT", "5000")))
