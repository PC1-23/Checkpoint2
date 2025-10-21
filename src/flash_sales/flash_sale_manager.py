from datetime import datetime
from typing import Optional, Dict, List
import sqlite3


class FlashSaleManager:
    """Determines if a flash sale is active for products"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
    
    def is_flash_sale_active(self, product_id: int) -> bool:
        """Check if a flash sale is currently active for a product"""
        now = datetime.now()
        
        row = self.conn.execute(
            """
            SELECT flash_price_cents, sale_start, sale_end 
            FROM product 
            WHERE id = ? AND active = 1
            """,
            (product_id,)
        ).fetchone()
        
        if not row:
            return False
        
        flash_price = row["flash_price_cents"]
        sale_start = row["sale_start"]
        sale_end = row["sale_end"]
        
        # Flash sale is active if price exists and current time is within window
        if flash_price is None or sale_start is None or sale_end is None:
            return False
        
        start = datetime.fromisoformat(sale_start)
        end = datetime.fromisoformat(sale_end)
        
        return start <= now <= end
    
    def get_flash_products(self) -> List[Dict]:
        """Get all products with active flash sales"""
        now = datetime.now().isoformat()
        
        rows = self.conn.execute(
            """
            SELECT id, name, price_cents, flash_price_cents, 
                   stock, sale_start, sale_end
            FROM product 
            WHERE active = 1 
              AND flash_price_cents IS NOT NULL
              AND sale_start <= ?
              AND sale_end >= ?
            ORDER BY sale_end ASC
            """,
            (now, now)
        ).fetchall()
        
        return [dict(row) for row in rows]
    
    def get_effective_price(self, product_id: int) -> Optional[int]:
        """Get the effective price (flash or regular) for a product"""
        if self.is_flash_sale_active(product_id):
            row = self.conn.execute(
                "SELECT flash_price_cents FROM product WHERE id = ?",
                (product_id,)
            ).fetchone()
            return row["flash_price_cents"] if row else None
        else:
            row = self.conn.execute(
                "SELECT price_cents FROM product WHERE id = ?",
                (product_id,)
            ).fetchone()
            return row["price_cents"] if row else None
    
    def log_event(self, product_id: int, event_type: str, details: str = ""):
        """Log a flash sale event"""
        self.conn.execute(
            """
            INSERT INTO flash_sales_log (product_id, event_type, details)
            VALUES (?, ?, ?)
            """,
            (product_id, event_type, details)
        )
        self.conn.commit()