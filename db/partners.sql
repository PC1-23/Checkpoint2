-- partners.sql: schema for partner integrations
CREATE TABLE IF NOT EXISTS partner (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    format TEXT NOT NULL,
    endpoint TEXT
);

CREATE TABLE IF NOT EXISTS partner_api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id INTEGER NOT NULL,
    api_key TEXT NOT NULL UNIQUE,
    description TEXT,
    FOREIGN KEY (partner_id) REFERENCES partner(id)
);
