-- =============================
-- Flash Sales Schema
-- =============================

PRAGMA foreign_keys = ON;

-- Add flash sale columns to product table (if not exists)
-- Note: SQLite doesn't support ADD COLUMN IF NOT EXISTS in one statement
-- So we'll handle this in the migration/init

-- For new installs, we'll document the columns needed:
-- ALTER TABLE product ADD COLUMN flash_price_cents INTEGER CHECK(flash_price_cents >= 0);
-- ALTER TABLE product ADD COLUMN sale_start TIMESTAMP;
-- ALTER TABLE product ADD COLUMN sale_end TIMESTAMP;

-- Table: flash_sales_log (optional - for tracking load events)
CREATE TABLE IF NOT EXISTS flash_sales_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN ('SALE_START','SALE_END','RATE_LIMIT','CIRCUIT_OPEN')),
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_flash_log_product ON flash_sales_log(product_id);
CREATE INDEX IF NOT EXISTS idx_flash_log_time ON flash_sales_log(event_time);