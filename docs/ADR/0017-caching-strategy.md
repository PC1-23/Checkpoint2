````markdown
# ADR-0017: Caching Strategy for Flash Sale Performance

**Status:** Accepted

**Date:** 2025-10-21

**Decision Makers:** Flash Sales Team

---

## Context

Flash sales create sudden read-heavy traffic patterns and repeated queries for the same active products. To reduce database load and improve response times, we need a simple caching strategy that complements rate limiting and other resilience tactics.

---

## Decision

Use a small in-process cache with TTL for active flash products and hotspot items. Implementation lives in `src/flash_sales/cache.py` and uses a thread-safe dict with expiration metadata. For production we recommend a Redis-backed cache.

---

## Related ADRs

- **ADR-0015:** Rate Limiting Strategy (works together with caching)
- **ADR-0016:** Flash Sale Implementation (primary use case for caching)
- **ADR-0014:** Circuit Breaker Pattern (caching reduces load on external services)
````
