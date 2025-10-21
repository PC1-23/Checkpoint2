# ADR 0006: Admin Access Control

Status: Accepted

Context
-------
Admin endpoints control scheduling, job requeueing and metrics. Access must
be restricted to authorized operators to prevent misuse.

Decision
--------
Use a simple API key for admin access in the demo. For production we propose:

- Use a centralized identity provider (OIDC) and issue short-lived OAuth2
  tokens or use mutual TLS for operator clients.
- Enforce RBAC: admin vs read-only roles for different endpoints.

Consequences
------------
- The demo uses `ADMIN_API_KEY` as an env var; this is acceptable for local
  demos but should be replaced in production by OIDC/JWT or mTLS.

Implementation
--------------
- Code: admin access checks are performed in `src/partners/routes.py`.
  Admin endpoints (schedule CRUD, job requeue, metrics) validate the
  request by calling `verify_api_key` for admin keys and/or checking the
  request header `X-Admin-Key` / environment var `ADMIN_API_KEY`.
  Audit events for admin actions are recorded by `record_audit`.
- RBAC model: the code uses a simple two-role model (admin / read-only)
  for demo; role checks are implemented inline in route handlers.
- Database: no dedicated admin user table is required for the demo. For
  production, store admin identities in a `users` table with role columns
  or integrate with an external IdP.

Migration / Production Notes
---------------------------
- Short-term (demo -> staging): Centralize admin keys into a `users`
  table with hashed credentials and migrate existing `ADMIN_API_KEY`
  values into the table. Implement a migration script that can be run as
  part of deployment.
- Long-term (recommended): Integrate with an OIDC provider (Auth0, Keycloak,
  corporate IdP). Use short-lived JWTs (validated via library) or mutual
  TLS for machine-to-machine admin calls. Apply RBAC at both application
  and gateway layers.

Testing
-------
- Add tests that assert admin endpoints are protected from unauthenticated
  calls (`tests/test_admin_auth.py`) and that successful admin actions
  produce audit entries and expected state changes (schedule create/delete,
  job requeue).
