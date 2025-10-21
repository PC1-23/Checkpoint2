
This document collects scenarios for the Security quality attribute for the
Partner Catalog Ingest feature. All scenarios below are examples of the
Security quality attribute and map to tactics/patterns and ADRs.

This document lists concrete security scenarios for the Partner Catalog Ingest
feature using the six-part template: Source, Stimulus, Environment, Artifact,
Response, Response-Measure.

## Table of Contents

- Security scenarios
- Modifiability scenarios
- Testability scenarios
- Usability scenarios
- Integrability scenarios
- ADR Index (linked list of ADRs referenced in this catalog)

## ADR Index

- [ADR 0001 - Database Choice](docs/ADR/0001-database-choice.md) — Choose SQLite for the prototype (simple, transactional, portable).
- [ADR 0002 - Persistence Style](docs/ADR/0002-persistence-style.md) — Use DAO pattern with raw SQL instead of an ORM for explicit control and testability.
- [ADR 0003 - API Key Rate Limiting](docs/ADR/0003-rate-limiting.md) — Per-API-key in-process rate limiter for demo; recommend shared store or gateway in prod.
- [ADR 0004 - Audit Trail & API Key Storage](docs/ADR/0004-audit-and-api-key-storage.md) — Append-only audit table and guidance to hash API keys for production.
- [ADR 0005 - Input Validation Policy](docs/ADR/0005-input-validation.md) — Strict validation-first policy for partner feeds; reject and audit invalid items.
- [ADR 0006 - Admin Access Control](docs/ADR/0006-admin-access-control.md) — Protect admin endpoints; demo uses admin API key, recommend OIDC/mTLS in prod.
- [ADR 0007 - Modifiability tactics](docs/ADR/0007-modifiability.md) — Adapter pattern, canonical product dict, strict/lenient validation, and defensive SQL.
- [ADR 0008 - Adapter & Feed Format Evolution (M1)](docs/ADR/0008-modifiability-m1-adapter-format.md) — Conventions and recipe for adding adapters and handling new fields/formats.
- [ADR 0010 - Contract publication and pre-validation](docs/ADR/0010-contract.md) — Publish a machine-readable contract at `/partner/contract` and provide lightweight validation.
- [ADR 0011 - Feed versioning and adapter negotiation](docs/ADR/0011-versioning.md) — Support `X-Feed-Version` and versioned adapters for backward compatibility.
- [ADR 0012 - Testability](docs/ADR/0012-testability.md) — Helpers for deterministic tests: test DB factory, seeding helpers, and `process_next_job_once`.
- [ADR 0013 - Usability](docs/ADR/0013-usability.md) — Publish example payloads, a quickstart help endpoint, and normalized JSON error responses.
- [ADR 0014 - Circuit Breaker Pattern](docs/ADR/0014-circuit-breaker-pattern.md) — Circuit breaker protects external payment services during flash sales.
- [ADR 0015 - Rate Limiting Strategy](docs/ADR/0015-rate-limiting-strategy.md) — Sliding-window rate limiter for flash checkout and abusive traffic protection.
- [ADR 0016 - Flash Sale Implementation](docs/ADR/0016-flash-sale-implementation.md) — Data model and manager for flash sale support.
- [ADR 0017 - Caching Strategy](docs/ADR/0017-caching-strategy.md) — Small in-process cache/tiered approach for hotspot flash products.

# Quality Scenarios Catalog

This document collects example quality scenarios for the Partner Catalog
Ingest feature and maps them to tactics, code locations, and ADRs. Each
scenario follows the six-part template: Source, Stimulus, Environment,
Artifact, Response, Response-Measure.

## Security scenarios

### Scenario S1: Credential theft via API key enumeration

- Source: External attacker
- Stimulus: Repeated automated requests presenting guessed API keys
- Environment: Public-facing ingest endpoint `/partner/ingest` over HTTP(S)
- Artifact: Partner API key validation and `partner_api_keys` table
- Response: Detect and limit enumeration attempts, log activity, and block
  offending callers
- Response-Measure: Rate limiter triggers within a configurable threshold
  (default 60 requests/min); audit entries recorded for blocked attempts

Selected tactics / patterns
- Rate limiting (throttling)
- Audit logging
- Fail-closed access control (deny on invalid key)

Implemented in
- Rate limiter: `src/partners/security.py::check_rate_limit`
- Audit recording: `src/partners/security.py::record_audit`, DB table
  `partner_ingest_audit` (`db/init.sql`)
- Integration (429/deny): `src/partners/routes.py::partner_ingest`

ADRs
- `docs/ADR/0003-rate-limiting.md`

### Scenario S2: Tampered feed ingestion (malicious/invalid payload)

- Source: Third-party partner or attacker with a valid API key
- Stimulus: Partner submits a feed containing crafted/invalid fields (e.g.
  SQL injection payload)
- Environment: Normal ingestion flow (sync or async) with DB-backed upsert
- Artifact: `product` table and ingestion logic in
  `src/partners/partner_ingest_service.py`
- Response: Validate and sanitize input, reject invalid items, log failures
  in audit, and never execute injected SQL
- Response-Measure: Invalid items rejected; no DB schema or data is lost;
  audit entry recorded

Selected tactics / patterns
- Input validation
- Parameterized SQL (defense-in-depth)
- Reject-and-log

Implemented in
- Validation & upsert: `src/partners/partner_ingest_service.py::validate_products`
  and `upsert_products`
- Audit logging on errors: `src/partners/security.py::record_audit`

ADRs
- (No dedicated ADR for input validation yet; consider `docs/ADR/0005-input-validation.md`)

### Scenario S3: Unauthorized admin operations

- Source: Remote actor without admin privileges
- Stimulus: Calls admin endpoints (`/partner/jobs`, `/partner/schedules`)
- Environment: Admin endpoints exposed on the same web interface
- Artifact: Admin endpoints and admin API key configuration
- Response: Deny access (401/403) and log the attempt in audit
- Response-Measure: Admin endpoints return 401/403 and an audit entry exists

Selected tactics / patterns
- Access control (admin API key check)
- Audit logging

Implemented in
- Admin key checks: `src/partners/routes.py` admin endpoints
- Audit logging: `src/partners/security.py::record_audit`

ADRs
- (No dedicated ADR for admin access control; consider documenting choices)

### Scenario S4: Compromised partner endpoint credentials

- Source: Partner credentials leaked
- Stimulus: Attacker attempts to use stored partner fetch credentials
- Environment: Scheduled fetches performed by `src/partners/scheduler.py`
- Artifact: `partner.endpoint` and `endpoint_auth`/`endpoint_headers` in DB
- Response: Store and use credentials securely; record every fetch in audit
- Response-Measure: Fetch attempts are logged; anomalous frequency can be
  detected via audit metrics

Selected tactics / patterns
- Secure credential storage guidance
- Per-fetch audit logging
- Monitoring for anomalous fetch frequency

Implemented in
- Scheduler uses `partner.endpoint`, `endpoint_auth`, `endpoint_headers`
  (`src/partners/scheduler.py`)
- Audit logging via `record_audit()` (scheduler logs can be extended)

ADRs
- `docs/ADR/0004-audit-and-api-key-storage.md`

## Modifiability scenarios

### Scenario M1: Partner changes feed format or adds new fields

- Source: Partner engineering team or third-party integrator
- Stimulus: Partner introduces a new field (e.g., `manufacturer`, `brand`,
  or a nested `dimensions` object), or switches from JSON to XML
- Environment: Live ingest endpoints and scheduled fetches
- Artifact: Feed parsers/adapters and normalization layer
  (`src/partners/partner_adapters.py`, `src/partners/partner_ingest_service.py`)
- Response: Allow new field/format to be supported by adding/extending an
  adapter and updating normalization/validation with minimal changes
- Response-Measure: New adapter/normalizer added and unit-tested with a
  small localized change; endpoints and worker require minimal/no change

Selected tactics / patterns
- Adapter pattern for feed formats (isolate parsing & normalization)
- Stable product-dict interface
- Strict/lenient validation modes for rollouts

Implemented in
- Adapters/parsers: `src/partners/partner_adapters.py` (e.g.,
  `parse_json_feed`, `parse_csv_feed`, `parse_xml_feed`)
- Validation/normalization: `src/partners/partner_ingest_service.py::validate_products`
- Ingest paths: `src/partners/routes.py` and `src/partners/ingest_queue.py`

ADRs and docs
- `docs/ADR/0005-input-validation.md`, `docs/ADR/0007-modifiability.md`

### Scenario M2: Storage schema change or database migration

- Source: Platform engineering / operations
- Stimulus: Need to migrate product storage (add/rename columns, or change
  DB engine)
- Environment: Running system with ongoing ingest traffic and scheduled jobs
- Artifact: Database schema (`product`, `partner_feed_imports`,
  `partner_ingest_jobs`) and upsert logic
- Response: Support schema evolution with defensive SQL, scripted migrations
  and minimal downtime
- Response-Measure: Schema migration applied; ingestion continues without
  errors; tests cover old and new schema paths

Selected tactics / patterns
- Defensive SQL and feature-detection
- Scripted migrations (or migration tooling)
- Centralized DB access

Implemented in
- Schema: `db/init.sql` and migration scripts in `migrations/`
- Upsert resilience: `src/partners/partner_ingest_service.py::upsert_products`
- Job metadata and idempotency: `partner_feed_imports` and
  `partner_ingest_jobs` tables

ADRs and docs
- `docs/ADR/0004-audit-and-api-key-storage.md`, `docs/ADR/0005-input-validation.md`,
  `docs/ADR/0007-modifiability.md`

## Testability scenarios

### Scenario T1: Deterministic job processing and isolated DB for tests

- Source: Platform engineers and contributors writing automated tests
- Stimulus: Need to exercise the full ingest path (enqueue → process →
  verify) in CI/local dev without timing races or shared state
- Environment: Test runners (pytest) creating ephemeral databases and
  running helper functions synchronously
- Artifact: The `partner_ingest_jobs` queue, upsert logic in
  `src/partners/partner_ingest_service.py`, and test helpers
- Response: Provide test helpers that create an isolated sqlite DB from the
  canonical schema, utilities to seed partner and api keys, and a synchronous
  single-job processor that claims and processes a job deterministically.
- Response-Measure: Tests can enqueue a job, call the synchronous processor,
  and immediately assert DB state changes; no background threads or timing
  sleeps are required.

Selected tactics / patterns
- Test DB factory: initialize an isolated sqlite DB from `db/init.sql` so tests
  start from a known schema.
- Deterministic synchronous processor: expose `process_next_job_once(db_path)`
  that claims and processes a single pending job in-process.
- Test seeding helpers: helpers to insert a partner and API key for test use.
- Guarded background services startup: ensure auto-started worker/scheduler
  during app import are guarded so tests don't accidentally spawn threads.

Implemented in
- Test helpers: `src/partners/testing.py::create_test_db` and
  `src/partners/testing.py::seed_partner_and_key`.
- Synchronous processor: `src/partners/ingest_queue.py::process_next_job_once`.
- Schema: `db/init.sql` provides the canonical schema used by the test DB
  factory.
- Example test: `tests/test_testability_integration.py` demonstrates the
  pattern end-to-end (create DB, seed partner, enqueue job, process once,
  assert products table contains the new product).
- Guarded startup: `src/partners/routes.py` already guards worker/scheduler
  startup during import to avoid auto-spawning background threads when tests
  import the app.

ADRs and docs
- `docs/ADR/0012-testability.md` — records the Testability decision, tactics
  and rationale.

## Usability scenarios

These scenarios describe partner-facing usability improvements: examples,
quickstarts, and consistent error messages.

## Scenario U1: Quickstart, examples and predictable errors

- Source: Partner or internal engineer onboarding to the API
- Stimulus: Need a quick way to see example payloads, curl commands and
  machine-friendly error formats
- Environment: Partner dev machines, CI, or quick manual tests
- Artifact: Contract endpoint, help pages, API error responses
- Response: Provide contract metadata and example payloads, a small
  quickstart help endpoint, and normalized JSON error responses so partners
  can parse and act on errors programmatically.
- Response-Measure: Partners can fetch `/partner/contract/example` and copy
  a payload that validates, and all error responses follow `{error, details}`.

Selected tactics / patterns
- Publish example payloads alongside the machine-readable contract.
- Provide a human-focused help endpoint with cURL quickstarts.
- Return consistent, machine-friendly JSON error responses for API errors.

Implemented in
- Contract example: `src/partners/integrability.py::CONTRACT["example"]`.
- Endpoints: `src/partners/routes.py::partner_contract_info`,
  `partner_contract_example`, `partner_help`.
- JSON error handler: `src/partners/routes.py::json_error_handler`.

ADRs and docs
- `docs/ADR/0013-usability.md` — records the Usability decision and tactics.

## Integrability scenarios

These scenarios cover partner-facing integration concerns: contract
discovery, pre-validation, and version negotiation.

## Scenario I1: Contract discovery and pre-validation

- Source: Partner engineering team
- Stimulus: Partner wants to validate feeds locally/CI before sending to
  reduce integration errors and manual back-and-forth.
- Environment: Partner dev and CI environments
- Artifact: Machine-readable contract exposed by the platform
- Response: The platform exposes a contract endpoint and a lightweight
  validator so partners can fetch the contract (`contract_version`) and
  locally validate their payloads prior to submission.
- Response-Measure: Partners can run validation in CI; contract includes
  `contract_version` and required properties.

Selected tactics / patterns
- Contract-first integration (publish a machine-readable contract).
- Discoverable contract endpoint for programmatic validation.

Implemented in
- Contract & validator: `src/partners/integrability.py::get_contract` and `validate_against_contract`
- Endpoint: `src/partners/routes.py::partner_contract` (`GET /partner/contract`)
- ADR: `docs/ADR/0010-contract.md`

## Scenario I2: Feed version negotiation and backward compatibility

- Source: Partner engineering team / Platform ops
- Stimulus: Platform introduces a new feed version adding optional fields
  without breaking existing partners still sending older versions.
- Environment: Live ingestion endpoint with multiple partners
- Artifact: Versioned feed contracts and adapter selection
- Response: The system supports `X-Feed-Version` header or partner
  profile version to select appropriate adapter and uses `extra` for
  forward-compatible fields until schema migration.
- Response-Measure: Partners using `X-Feed-Version: 2` are handled by
  v2 adapters; v1 partners remain working; contract endpoint reflects
  available versions.

Selected tactics / patterns
- Versioned contracts and adapter selection.
- Forward-compatibility using `extra` field in normalized dicts.

Implemented in
- Contract & version info: `src/partners/integrability.py::get_contract` (includes `contract_version`)
- Adapter selection & feed header: `src/partners/routes.py` (supports `X-Feed-Version`)
- Adapters: `src/partners/partner_adapters.py` (implement parsers per format/version)
- ADRs: `docs/ADR/0011-versioning.md`, `docs/ADR/0010-contract.md`

Mapping additions

- I1: Contract discovery and pre-validation
  - Selected tactics: Contract-first integration, discoverable endpoint
  - Implemented in:
    - Contract & validator: `src/partners/integrability.py::get_contract` and `validate_against_contract`
    - Endpoint: `src/partners/routes.py::partner_contract` (`GET /partner/contract`)
  - ADRs: `docs/ADR/0010-integrability.md`, `docs/ADR/0005-input-validation.md`

- I2: Feed version negotiation and backward compatibility
  - Selected tactics: Versioned contracts, adapter selection, `extra` for forward compatibility
  - Implemented in:
    - Contract: `src/partners/integrability.py` (contract_version)
    - Adapter selection & header support: `src/partners/routes.py` (supports `X-Feed-Version`)
    - Adapters: `src/partners/partner_adapters.py` (format/version parsers)
  - ADRs: `docs/ADR/0010-integrability.md`, `docs/ADR/0007-modifiability.md`



