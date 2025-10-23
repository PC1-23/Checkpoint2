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
    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),

    flash_sale_active INTEGER DEFAULT 0,
    flash_sale_price_cents INTEGER
);

-- Indexes for better performance
CREATE INDEX IF NOT EXISTS idx_product_active ON product(active);
CREATE INDEX IF NOT EXISTS idx_product_name ON product(name);


-- =============================
-- Partner integration tables
-- =============================

CREATE TABLE IF NOT EXISTS partner (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	name TEXT NOT NULL,
	format TEXT NOT NULL,
	endpoint TEXT,
	endpoint_auth TEXT, -- JSON blob describing auth: {"type":"basic","username":"u","password":"p"} or {"type":"bearer","token":"..."}
	endpoint_headers TEXT -- JSON blob of additional headers to send when fetching partner feed
);

CREATE TABLE IF NOT EXISTS partner_api_keys (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	partner_id INTEGER NOT NULL,
	api_key TEXT NOT NULL UNIQUE,
	description TEXT,
	FOREIGN KEY (partner_id) REFERENCES partner(id)
);

-- Track processed partner feed checksums to avoid re-processing the same feed
CREATE TABLE IF NOT EXISTS partner_feed_imports (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	partner_id INTEGER NOT NULL,
	feed_hash TEXT NOT NULL,
	inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(partner_id, feed_hash),
	FOREIGN KEY (partner_id) REFERENCES partner(id)
);

-- Durable jobs table for partner ingest (simple persistent queue)
CREATE TABLE IF NOT EXISTS partner_ingest_jobs (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	partner_id INTEGER NOT NULL,
	payload TEXT NOT NULL, -- JSON payload of products
	feed_hash TEXT,
	status TEXT NOT NULL DEFAULT 'pending', -- pending, in_progress, done, failed
	attempts INTEGER NOT NULL DEFAULT 0,
	diagnostics TEXT,
	next_run TIMESTAMP,
	max_attempts INTEGER NOT NULL DEFAULT 5,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	processed_at TIMESTAMP,
	error TEXT
);


-- Audit trail for partner operations (security / compliance)
CREATE TABLE IF NOT EXISTS partner_ingest_audit (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	partner_id INTEGER,
	api_key TEXT,
	action TEXT NOT NULL,
	payload TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Optional: store large diagnostics offloaded from partner_ingest_jobs
CREATE TABLE IF NOT EXISTS partner_ingest_diagnostics (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	job_id INTEGER NOT NULL,
	diagnostics TEXT NOT NULL,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (job_id) REFERENCES partner_ingest_jobs(id) ON DELETE CASCADE
);


-- Scheduled partner ingestion configuration
CREATE TABLE IF NOT EXISTS partner_schedules (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	partner_id INTEGER NOT NULL,
	schedule_type TEXT NOT NULL, -- 'interval' or 'cron'
	schedule_value TEXT NOT NULL, -- JSON encoded schedule details (seconds for interval or cron expr)
	enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
	last_run TIMESTAMP,
	FOREIGN KEY (partner_id) REFERENCES partner(id)
);



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
