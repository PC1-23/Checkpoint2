-- =============================
-- Partner A: User & Product Schema  
-- =============================

-- Table: user
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT UNIQUE,
    password TEXT
);

-- Table: product
CREATE TABLE IF NOT EXISTS product (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT NOT NULL UNIQUE,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    stock INTEGER NOT NULL CHECK(stock >= 0),
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_product_active ON product(active);
CREATE INDEX IF NOT EXISTS idx_product_name ON product(name);


-- =============================
-- Partner B: Sales & Payment Schema
-- =============================

-- Ensure FK enforcement when running this script
PRAGMA foreign_keys = ON;

-- Table: sale
CREATE TABLE IF NOT EXISTS sale (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	user_id INTEGER NOT NULL,
	sale_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	total_cents INTEGER NOT NULL CHECK(total_cents >= 0),
	status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK(status IN ('COMPLETED','CANCELLED','REFUNDED')),
	FOREIGN KEY (user_id) REFERENCES user(id)
);

-- Table: sale_item
CREATE TABLE IF NOT EXISTS sale_item (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	sale_id INTEGER NOT NULL,
	product_id INTEGER NOT NULL,
	quantity INTEGER NOT NULL CHECK(quantity > 0),
	price_cents INTEGER NOT NULL CHECK(price_cents >= 0), -- price per item at time of sale
	FOREIGN KEY (sale_id) REFERENCES sale(id) ON DELETE CASCADE,
	FOREIGN KEY (product_id) REFERENCES product(id) ON DELETE RESTRICT,
	UNIQUE (sale_id, product_id)
);

-- Table: payment
CREATE TABLE IF NOT EXISTS payment (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	sale_id INTEGER NOT NULL,
	method TEXT NOT NULL,
	amount_cents INTEGER NOT NULL CHECK(amount_cents >= 0),
	status TEXT NOT NULL CHECK(status IN ('APPROVED','DECLINED')), -- APPROVED or DECLINED
	ref TEXT,
	processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (sale_id) REFERENCES sale(id) ON DELETE CASCADE,
	UNIQUE (sale_id)
);

-- Helpful indexes
CREATE INDEX IF NOT EXISTS idx_sale_user_id ON sale(user_id);
CREATE INDEX IF NOT EXISTS idx_sale_item_sale_id ON sale_item(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_item_product_id ON sale_item(product_id);
CREATE INDEX IF NOT EXISTS idx_payment_sale_id ON payment(sale_id);
