````markdown
# ADR-0016: Flash Sale Implementation Strategy

**Status:** Accepted

**Date:** 2025-10-21

**Decision Makers:** Flash Sales Team

---

## Context

The business requires a "flash sales" feature to offer time-limited discounts that drive urgency and boost sales. Flash sales have specific characteristics that create architectural challenges:

**Business Requirements:**
- Products available at discounted prices for limited time windows
- Clear visual indication of flash sale status (badges, countdown timers)
- Automatic price transitions (regular → flash → regular)
- High traffic spikes during active sales
- Fair inventory allocation under concurrent access

**Technical Challenges:**
- Determining "is sale active?" efficiently for every page load
- Applying correct pricing (flash vs. regular) consistently
- Handling timezone-aware sale windows
- Scaling to handle traffic surges
- Maintaining data integrity during concurrent checkouts

... (rest unchanged) ...

## Related ADRs

- **ADR-0015:** Rate Limiting Strategy (protects flash sale endpoints)
- **ADR-0017:** Caching Strategy (optimizes flash product queries)
- **ADR-0014:** Circuit Breaker Pattern (payment resilience during sales)
````
