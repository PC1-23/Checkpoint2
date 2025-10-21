-- partners.sql: lightweight / compatibility schema for partner integrations
-- NOTE: The canonical, full application schema is `db/init.sql`.
-- `partners.sql` is a small subset kept for quick reference or external tools.
-- If you need the authoritative schema (including job tables, schedules, and
-- extra columns such as endpoint_auth/endpoint_headers) use `db/init.sql`.
-- To initialize the DB with the full schema:
--   sqlite3 app.sqlite < db/init.sql
-- Or run the app initialization script: python -m src.main
--
-- The contents below are intentionally minimal and may be out-of-sync with
-- `db/init.sql` if the latter is updated. Prefer `db/init.sql` for migrations
-- and production use.
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
