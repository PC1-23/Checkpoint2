-- Migration: add diagnostics column to partner_ingest_jobs
ALTER TABLE partner_ingest_jobs ADD COLUMN diagnostics TEXT;
