```markdown
# ADR 0012: Testability — Make the ingest pipeline easy to test

Status: Accepted

Context
-------
Reliable automated tests are essential for the Partner Catalog Ingest
feature. Tests must be able to exercise parsing, validation, upsert, queue
processing and scheduling without flakiness or hidden side-effects.

Decision
--------
Adopt a set of testability tactics that make the system deterministic and
easy to control from tests:

- Test DB factory: provide a helper to create an isolated sqlite DB using
  the canonical schema (`db/init.sql`) so tests get a fresh clean schema.
- Process-once worker helper: expose a synchronous helper to claim and
  process a single job (deterministic, no background threads required).
- Test seeding helpers: utilities to seed partners and API keys for tests.
- Feature toggles for background services: ensure tests can disable
  auto-start of workers/schedulers (the app already guards service startup
  — keep that behavior documented and controllable via env vars).

Consequences
------------
- Tests can create ephemeral DBs, seed required records, enqueue jobs and
  synchronously process them in a single-threaded manner, avoiding timing
  races and flaky tests.
- Small helpers reduce duplication across tests and make new tests easier
  to write.

Implementation
--------------
- `src/partners/testing.py` provides `create_test_db(db_path)` and seeding
  utilities.
- `src/partners/ingest_queue.py` exposes `process_next_job_once(db_path)`
  that claims one pending job and runs the same processing logic the
  background worker uses (no thread spawn required).

Testing
-------
- A new integration test `tests/test_testability_integration.py` demonstrates
  using the helpers: create a test DB, seed a partner and api key, enqueue a
  small JSON payload as a job, call `process_next_job_once` and assert the
  job completes and products are present in the `product` table.

Related ADRs
-----------
- `docs/ADR/0007-modifiability.md` (adapter pattern helps test small units)
- `docs/ADR/0010-contract.md` (contract-driven validation supports tests)

``` 
