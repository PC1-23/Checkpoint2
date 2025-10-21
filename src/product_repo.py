from .dao import ProductRepo

class AProductRepo(ProductRepo):
    """Partner A's implementation of the ProductRepo interface"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def get_product(self, product_id: int):
        """Get an active product by ID with flash sale price if applicable"""
        cursor = self.conn.execute(
            """SELECT id, name, price_cents, stock, active, 
                      flash_sale_active, flash_sale_price_cents 
               FROM product 
               WHERE id = ? AND active = 1""",
            (product_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Convert to dict so we can modify it
        product = dict(row)
        
        # Check if flash sale is active and apply flash price
        if product['flash_sale_active'] == 1 and product['flash_sale_price_cents']:
            product['original_price'] = product['price_cents']
            product['price_cents'] = product['flash_sale_price_cents']
            product['is_flash_sale'] = True
        else:
            product['is_flash_sale'] = False
        
        return product

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
        """Search products by name with flash sale prices"""
        if query:
            cursor = self.conn.execute(
                """SELECT id, name, price_cents, stock,
                          flash_sale_active, flash_sale_price_cents
                   FROM product 
                   WHERE active = 1 AND name LIKE ? 
                   ORDER BY name""",
                (f"%{query}%",)
            )
        else:
            return self.get_all_products()
        
        rows = cursor.fetchall()
        products = []
        for row in rows:
            product = dict(row)
            
            if product['flash_sale_active'] == 1 and product['flash_sale_price_cents']:
                product['original_price'] = product['price_cents']
                product['price_cents'] = product['flash_sale_price_cents']
                product['is_flash_sale'] = True
            else:
                product['is_flash_sale'] = False
            
            products.append(product)
        
        return products
        
    def get_all_products(self):
        """Get all active products with flash sale prices"""
        cursor = self.conn.execute(
            """SELECT id, name, price_cents, stock, 
                      flash_sale_active, flash_sale_price_cents 
               FROM product 
               WHERE active = 1 
               ORDER BY name"""
        )
        rows = cursor.fetchall()
        
        products = []
        for row in rows:
            product = dict(row)
            
            # Apply flash sale price if active
            if product['flash_sale_active'] == 1 and product['flash_sale_price_cents']:
                product['original_price'] = product['price_cents']
                product['price_cents'] = product['flash_sale_price_cents']
                product['is_flash_sale'] = True
            else:
                product['is_flash_sale'] = False
            
            products.append(product)
        
        return products