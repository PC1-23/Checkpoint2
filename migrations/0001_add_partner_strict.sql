-- Migration: add 'strict' column to partner table (non-destructive)
-- This migration is safe for SQLite: ALTER TABLE ADD COLUMN is supported.

BEGIN TRANSACTION;
ALTER TABLE partner ADD COLUMN strict INTEGER NOT NULL DEFAULT 0 CHECK(strict IN (0,1));
COMMIT;
