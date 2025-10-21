# ADR 0004: Audit Trail & API Key Storage

Status: Accepted

Context
-------
We need to keep an auditable record of partner operations and protect
API keys stored in the database. Audit records help forensics and compliance.

Decision
--------
- Add an append-only audit table `partner_ingest_audit` and write best-effort
  audit records for important actions (ingest, enqueue, admin access attempts).
- Store API keys in `partner_api_keys` as cleartext for the demo. For production,
  they should be hashed with a slow KDF (PBKDF2 / bcrypt) and compared with a
  time-constant comparison.

Consequences
------------
- Audit table increases storage but provides an immutable record for events.
- Storing cleartext API keys is acceptable for demo purpose only. Replace with
  hashed keys before production.

Implementation
--------------
- Database: the audit table is `partner_ingest_audit` (see `db/init.sql`).
  It is append-only by convention and is written to by the `record_audit`
  helper.
- Code: `src/partners/security.py` implements `record_audit(partner_id,
  api_key, action, payload=None)` and `verify_api_key(db_path, api_key)`.
  Routes and workers call `record_audit` for key events: ingest attempts,
  enqueue, worker processing, scheduler fetch results and admin actions.
- Tests: existing integration tests exercise ingest and scheduler flows.
  Add targeted tests that assert audit rows are created for:
  - invalid API key usage
  - rate-limited requests
  - worker processing failures and retries
  Suggested test file: `tests/test_audit_entries.py`.

Migration / Production Notes
---------------------------
- API keys must not be stored in plaintext in production. Recommended plan:
  1. Add a new column `api_key_hash` and a KDF parameters column (e.g.
     `api_key_salt` or `kdf_version`) to `partner_api_keys`.
  2. Introduce a migration that, for existing keys, computes and stores
     PBKDF2/bcrypt hashes of the current plaintext keys and then clears the
     `api_key_plaintext` column.
  3. Update `verify_api_key` to first look up by identifier (id or key id)
     and then verify the provided key using the stored hash with a
     time-constant comparison.
- Audit retention / export: For production, plan for retention, export to a
  SIEM, and log rotation/archival policies. The audit table should be
  immutable from the application layer; administrative tools may export or
  delete old rows following policy.
