from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..dao import get_connection, SalesRepo
from ..product_repo import AProductRepo
from .flash_sale_manager import FlashSaleManager
from .rate_limiter import rate_limit, checkout_rate_limiter
from .cache import flash_sale_cache
from .payment_resilience import process_payment_resilient
import os
from pathlib import Path
from typing import Dict

# Create blueprint
flash_bp = Blueprint(
    'flash_sales',
    __name__,
    url_prefix='/flash',
    template_folder='templates'
)

# Get database path (same as main app)
root = Path(__file__).resolve().parents[2]
db_path = os.environ.get("APP_DB_PATH", str(root / "app.sqlite"))


def get_conn():
    return get_connection(db_path)


@flash_bp.route('/products')
def flash_products():
    """Show all active flash sale products"""
    # Try to get from cache first
    cached = flash_sale_cache.get('flash_products')
    if cached is not None:
        products = cached
    else:
        conn = get_conn()
        try:
            manager = FlashSaleManager(conn)
            products = manager.get_flash_products()
            # Cache for 30 seconds
            flash_sale_cache.set('flash_products', products, ttl=30)
        finally:
            conn.close()
    
    return render_template('flash_sales/flash_products.html', products=products)


@flash_bp.post('/cart/add')
@rate_limit(max_requests=10, window_seconds=60)
def flash_cart_add():
    """Add flash sale product to cart with rate limiting"""
    pid = int(request.form.get("product_id", 0))
    qty = int(request.form.get("qty", 1))
    
    if qty <= 0:
        flash("Quantity must be > 0", "error")
        return redirect(url_for("flash_sales.flash_products"))
    
    conn = get_conn()
    try:
        manager = FlashSaleManager(conn)
        
        # Check if flash sale is active
        if not manager.is_flash_sale_active(pid):
            flash("Flash sale is not active for this product", "error")
            return redirect(url_for("flash_sales.flash_products"))
        
        # Check stock
        repo = AProductRepo(conn)
        if not repo.check_stock(pid, qty):
            product = repo.get_product(pid)
            flash(f"Only {product['stock']} in stock", "error")
            return redirect(url_for("flash_sales.flash_products"))
        
        # Add to flash cart (separate from regular cart)
        flash_cart = session.get("flash_cart", {})
        flash_cart[str(pid)] = flash_cart.get(str(pid), 0) + qty
        session["flash_cart"] = flash_cart
        
        # Log event
        manager.log_event(pid, "RATE_LIMIT", f"Added {qty} to cart")
        
        flash(f"Added {qty} items to flash cart", "success")
        return redirect(url_for("flash_sales.flash_cart_view"))
    finally:
        conn.close()


@flash_bp.get('/cart')
def flash_cart_view():
    """View flash sale cart with discounted prices"""
    flash_cart: Dict[str, int] = session.get("flash_cart", {})
    conn = get_conn()
    items = []
    total = 0
    
    try:
        manager = FlashSaleManager(conn)
        
        for pid_str, qty in flash_cart.items():
            pid = int(pid_str)
            
            # Get product and effective price
            prod = conn.execute(
                "SELECT id, name, price_cents, flash_price_cents, stock FROM product WHERE id = ?",
                (pid,)
            ).fetchone()
            
            if not prod:
                continue
            
            # Use flash price if sale is active, otherwise regular price
            if manager.is_flash_sale_active(pid):
                unit = int(prod["flash_price_cents"])
                regular_price = int(prod["price_cents"])
                savings = (regular_price - unit) * qty
            else:
                unit = int(prod["price_cents"])
                regular_price = unit
                savings = 0
            
            items.append({
                "id": pid,
                "name": prod["name"],
                "qty": qty,
                "unit": unit,
                "regular_price": regular_price,
                "line": unit * qty,
                "savings": savings,
            })
            total += unit * qty
    finally:
        conn.close()
    
    return render_template('flash_sales/flash_cart.html', items=items, total=total)


@flash_bp.post('/cart/clear')
def flash_cart_clear():
    """Clear flash sale cart"""
    session.pop("flash_cart", None)
    flash("Flash cart cleared", "info")
    return redirect(url_for("flash_sales.flash_products"))


@flash_bp.post('/checkout')
@rate_limit(max_requests=5, window_seconds=60)
def flash_checkout():
    """
    Checkout flash sale cart with rate limiting, circuit breaker, and retry
    """
    if "user_id" not in session:
        flash("Please login to checkout", "error")
        return redirect(url_for("login"))
    
    pay_method = request.form.get("payment_method", "CARD")
    user_id = session["user_id"]
    flash_cart: Dict[str, int] = session.get("flash_cart", {})
    cart_list = [(int(pid), qty) for pid, qty in flash_cart.items()]
    
    if not cart_list:
        flash("Flash cart is empty", "error")
        return redirect(url_for("flash_sales.flash_products"))
    
    conn = get_conn()
    try:
        manager = FlashSaleManager(conn)
        product_repo = AProductRepo(conn)
        
        # Validate all items still have active flash sales
        for pid, _ in cart_list:
            if not manager.is_flash_sale_active(pid):
                flash(f"Flash sale ended for product {pid}", "error")
                return redirect(url_for("flash_sales.flash_cart_view"))
        
        # Create custom SalesRepo that uses flash prices
        repo = FlashSaleRepo(conn, product_repo, manager)
        
        # Use resilient payment processing
        sale_id = repo.checkout_transaction(
            user_id=user_id,
            cart=cart_list,
            pay_method=pay_method,
            payment_cb=process_payment_resilient,
        )
        
        # Clear flash cart on success
        session.pop("flash_cart", None)
        flash(f"Flash sale checkout success! Sale #{sale_id}", "success")
        return redirect(url_for("receipt", sale_id=sale_id))
        
    except Exception as e:
        flash(f"Checkout failed: {str(e)}", "error")
        return redirect(url_for("flash_sales.flash_cart_view"))
    finally:
        conn.close()


class FlashSaleRepo(SalesRepo):
    """Extended SalesRepo that uses flash sale prices"""
    
    def __init__(self, conn, product_repo, flash_manager: FlashSaleManager):
        super().__init__(conn, product_repo)
        self.flash_manager = flash_manager
    
    def _get_active_product(self, product_id: int):
        """Override to return product with flash price if active"""
        product = super()._get_active_product(product_id)
        if product and self.flash_manager.is_flash_sale_active(product_id):
            # Replace price with flash price
            product_dict = dict(product)
            effective_price = self.flash_manager.get_effective_price(product_id)
            if effective_price:
                product_dict["price_cents"] = effective_price
            # Convert back to Row-like object
            class FlashProduct:
                def __init__(self, d):
                    self.data = d
                def __getitem__(self, key):
                    return self.data[key]
            return FlashProduct(product_dict)
        return product