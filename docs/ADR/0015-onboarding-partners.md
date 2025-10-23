# ADR 0015: Partner onboarding — streamline integrability for new partners

Status: Accepted

Quality attribute(s): Integrability

Context
-------
New partners need a low-friction onboarding experience to integrate their
product feeds with minimal engineering effort and support. Onboarding covers
contract discovery, sample payloads, API key provisioning, and a validation
loop that provides actionable feedback during initial integration.

Decision
--------
Adopt a small set of practical onboarding tactics to reduce time-to-first-success:

- Self-service API key provisioning: a protected onboarding endpoint allows
  authorized internal users (or automated partner portals) to create partner
  records and issue API keys for testing. Keys are stored hashed in production
  but may be plain for demo/local deployments.
- Sandboxed validation endpoint: provide `POST /partner/contract/validate` or
  equivalent that accepts a sample feed and returns a concise validation
  summary (counts, top errors, sample failing rows). This endpoint should be
  rate-limited and intended for pre-production validation only.
- Job-based asynchronous ingest with status: partner feeds may be enqueued for
  asynchronous processing; the job status endpoint (`GET /partner/jobs/<id>`)
  returns diagnostics and final status.

Implementation notes
--------------------
- Add an onboarding route in `src/partners/routes.py` (e.g. `POST /partner/onboard`) that:
  - Validates the requestor's identity (internal dashboard token or admin API key).
  - Creates a `partner` row and issues a new API key stored in `partner_api_keys`.
  - Returns the new API key (or pairing token) to the caller along with next steps.
- Reuse the existing contract publication and example endpoints already
  described in `docs/ADR/0013-usability.md` for contract + example access.
- Implement `POST /partner/contract/validate` to parse JSON/CSV via the adapter
  layer and call `validate_products` to return the structured validation summary
  (same schema as `docs/ADR/0018-upload-feedback.md`). Keep this endpoint
  lightweight and rate-limited to prevent abuse.
- Ensure API keys are hashed when persisted in production (note: plain keys may
  be emitted in demo/test environments). Store metadata (created_by, created_at,
  purpose) with the key to enable auditing and de-provisioning.
- Add audit entries for onboarding actions (partner created, key issued) and
  ensure secrets are not stored in plaintext in application logs or audit rows.

Consequences
------------
- Faster partner integration and reduced manual support.
- Requires careful handling of API keys and audit records to avoid leaking
  credentials or PII; production deployments should hash keys and require
  stronger admin authentication (OIDC, mTLS, or a secure admin portal).
- Adds endpoints that must be protected and rate-limited to prevent abuse.

Testing
-------
- Unit tests for onboarding route logic (partner creation, key issuance, audit
  record creation) and hashed key persistence.
- Integration tests that simulate a partner onboarding flow: call `POST /partner/onboard`,
  use returned API key to call `POST /partner/contract/validate` with a sample feed,
  assert validation diagnostics and ensure job enqueue/status flow works as expected.

Related ADRs
-----------
- `docs/ADR/0018-upload-feedback.md` (upload feedback / diagnostics)
- `docs/ADR/0013-usability.md` (contract publication and examples)
