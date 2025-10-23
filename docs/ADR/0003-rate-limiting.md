# ADR 0003: API Key Rate Limiting

Status: Accepted

Quality attribute(s): Security

Context
-------
The partner ingest endpoints are publicly exposed and accept API keys that
authenticate partner uploads. To mitigate credential stuffing and enumeration
attacks, we need per-key rate limiting.

Decision
--------
Implement an in-process, per-API-key rate limiter for demo environments. For
production, adopt a Redis-backed leaky-bucket implementation or enforce
rate-limits at the API gateway.

Consequences
------------
- Simple, low-dependency solution useful for local testing and demos.
- Not suitable for multi-instance production without a shared store.

Implementation
--------------
- Code: the demo implementation lives in `src/partners/security.py` as
	`check_rate_limit(api_key, max_per_minute=60)` which uses an in-memory
	sliding-window counter keyed by API key.
- Enforcement: rate checks are applied in `src/partners/routes.py` on
	ingestion endpoints (calls to `check_rate_limit` happen early in request
	processing and will emit an audit event via `record_audit` when a
	limit is exceeded).
- Configuration: the per-key limit is configurable by changing the default
	in `check_rate_limit` or by providing an environment-backed configuration
	value; for production we recommend making this configurable via env.

Migration / Production Notes
---------------------------
- Multi-instance deployments must replace the in-process limiter with a
	shared store based implementation. Two recommended approaches:
	- Enforce rate limits at the API gateway (e.g., Kong, NGINX, AWS API
		Gateway) — easiest to operate and highly performant.
	- Use a Redis-backed leaky-bucket or token-bucket implementation (e.g.
		`limits` / `ratelimit` libraries with Redis or a custom Lua script
		implementing atomic counters).
- When migrating, keep the same semantics (per-API-key windows and hard
	429 responses) and add observability (metrics for throttled requests).

Testing
-------
- Add unit tests that exercise >limit behaviour (suggest `tests/test_rate_limiting.py`).
- Integration tests which exercise the full request path exist for scheduler
	and worker flows; extend them to assert throttling in CI after migration.
