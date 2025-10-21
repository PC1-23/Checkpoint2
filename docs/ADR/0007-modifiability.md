```markdown
# ADR 0007: Modifiability tactics for Partner Catalog Ingest

Status: Accepted

Context
-------
The Partner Catalog Ingest feature will evolve: partners will add fields,
change feed formats, and the platform may need to migrate database schemas
or swap storage engines. We need explicit tactics to keep the codebase
easy to change with low risk.

Decision
--------
Adopt the following modifiability tactics:

- Adapter pattern for feed parsing: isolate format-specific parsing in a
  dedicated module so new formats can be added without touching ingest
  control-flow or worker logic.
- Stable normalization interface: adapters produce a canonical product
  dictionary shape consumed by the rest of the pipeline.
- Validation 'modes': support a default lenient mode and an optional
  'strict' mode for partner-by-partner rollouts and verification.
- Defensive SQL & feature-detection: upsert logic should attempt the
  preferred path and fall back gracefully if schema differences exist.
- Centralized migration points: keep schema and DB-access patterns
  concentrated so migration scripts and testing are straightforward.

Consequences
------------
- Adding a new feed format requires only a new adapter function and a
  unit test; routes and workers are unchanged.
- Normalization reduces duplicated field handling and makes validation
  simpler and localized.
- Strict validation allows incremental tightening per-partner.
- Defensive SQL reduces deployment risk when migrating schema but may
  hide schema drift unless monitored.

Implementation (where in repo)
------------------------------
- Adapter pattern: `src/partners/partner_adapters.py` (new parsers belong
  here). Example: `parse_json_feed`, `parse_csv_feed`, added `parse_xml_feed`.
- Normalization & validation: `src/partners/partner_ingest_service.py`
  (`validate_products` supports a `strict` mode).
- Ingest control: `src/partners/routes.py` selects adapters by content-type
  and remains downstream-agnostic.
- Defensive upsert: `src/partners/partner_ingest_service.py::upsert_products`
  uses try/catch fallbacks for optional columns.
- Schema & migrations: `db/init.sql` is the canonical schema; write
  migration scripts against this file and centralize DB path with
  `APP_DB_PATH` environment variable.

Testing & rollout
-----------------
- Unit tests should be added for each adapter and for strict validation.
- Support a partner-level 'strict' flag in future partner profiles to
  migrate partners to strict mode gradually.

Related ADRs
-----------
- `docs/ADR/0005-input-validation.md` (validation rules and modes)
- `docs/ADR/0004-audit-and-api-key-storage.md` (migration and storage)

```