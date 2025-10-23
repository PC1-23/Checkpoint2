# ADR 0014: Upload feedback — Structured validation summaries for partner uploads

Status: Accepted

Quality attribute(s): Usability

Context
-------
Partners need timely, actionable feedback when they upload feeds. A simple
"accepted/rejected" response isn't enough; partners benefit from a concise
validation summary and machine-readable details so CI can assert success/failure.

Decision
--------
Provide immediate, structured upload feedback for partner ingest flows:

- For synchronous ingest (sync path), return a detailed validation summary
  that includes counts (accepted, rejected), top error types, and a small
  sample of failing rows (or a location to fetch full diagnostics).
- For async ingest (enqueue), return 202 Accepted with a job id and a
  status endpoint (`GET /partner/jobs/<id>`) that returns the same summary
  once processing finishes.
- Always return machine-friendly JSON for feedback (fields: `job_id`,
  `status`, `accepted`, `rejected`, `errors_summary`, `errors_link`).

Implementation notes
--------------------
- Reuse existing helpers: `enqueue_feed` / `process_next_job_once` already
  persist jobs and call `validate_products`. Extend `process_next_job_once`
  to persist a small validation summary in the `partner_ingest_jobs` row
  (e.g., a JSON `diagnostics` column) or in `partner_ingest_audit`.
- For synchronous flows, build the summary from `validate_products` and
  include it in the immediate HTTP 200 response.
- Provide an optional `errors_link` for large feeds that points to a
  temporary artifact (object store or admin-only endpoint) containing full
  error details.

Consequences
------------
- Partners get fast feedback and can automate retries or fixes in CI.
- Requires adding lightweight storage for summaries (small JSON column or
  append-only diagnostics table) and ensuring audit records do not leak PII.

Testing
-------
- Unit tests for summary generation and sample error contents.
- Integration tests that upload a small mixed payload and assert the
  response's `accepted/rejected` counts match DB state.
