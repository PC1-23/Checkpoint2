from .dao import ProductRepo

class AProductRepo(ProductRepo):
    """Partner A's implementation of the ProductRepo interface"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def get_product(self, product_id: int):
        """Get an active product by ID"""
        cursor = self.conn.execute(
            "SELECT id, name, price_cents, stock, active FROM product WHERE id = ? AND active = 1",
            (product_id,)
        )
        return cursor.fetchone()
    
    def check_stock(self, product_id: int, qty: int) -> bool:
        """Check if product has sufficient stock and is active"""
        cursor = self.conn.execute(
            "SELECT stock FROM product WHERE id = ? AND active = 1",
            (product_id,)
        )
        result = cursor.fetchone()
        if result is None:
            return False
        return result['stock'] >= qty
    
    def decrement_stock(self, product_id: int, qty: int) -> bool:
        """Atomically decrement stock, ensuring no negative values"""
        cursor = self.conn.execute(
            "UPDATE product SET stock = stock - ? WHERE id = ? AND stock >= ? AND active = 1",
            (qty, product_id, qty)
        )
        return cursor.rowcount == 1
    
    def search_products(self, query: str = ""):
        """Search products by name (bonus method for UI)"""
        if query:
            cursor = self.conn.execute(
                "SELECT id, name, price_cents, stock FROM product WHERE active = 1 AND name LIKE ? ORDER BY name",
                (f"%{query}%",)
            )
        else:
            cursor = self.conn.execute(
                "SELECT id, name, price_cents, stock FROM product WHERE active = 1 ORDER BY name"
            )
        return cursor.fetchall()
    
    def get_all_products(self):
        """Get all active products"""
        cursor = self.conn.execute(
            "SELECT id, name, price_cents, stock FROM product WHERE active = 1 ORDER BY name"
        )
        return cursor.fetchall()