```markdown
# ADR 0008: Adapter & Feed Format Evolution (M1)

Status: Accepted

Context
-------
Partners will occasionally change feed formats or add new fields to their
product feeds (e.g., adding `manufacturer`, switching to XML, introducing
nested structures). We must be able to add support for new formats and
fields with minimal system-wide changes and low risk.

Decision
--------
Adopt an explicit Adapter pattern and a small set of conventions for
extending parsing and normalization.

- All format-specific parsing lives in `src/partners/partner_adapters.py`.
- Each adapter must produce a canonical product dict with at least the
  keys: `sku`, `name`, `price_cents`, `stock`, `partner_id`, `extra`.
- Validation and upsert consume this canonical shape and should not be
  coupled to specific formats.
- New adapters are added behind feature flags or via partner profile
  configuration during rollout; unit tests and integration tests must be
  added alongside them.

Implementation
--------------
- Code locations:
  - Adapters: `src/partners/partner_adapters.py` (add `parse_<format>_feed`)
  - Routes: `src/partners/routes.py` selects adapter by content-type; this
    remains format-agnostic.
  - Normalization/Validation: `src/partners/partner_ingest_service.py::validate_products`
  - Worker: `src/partners/ingest_queue.py` consumes normalized dicts unchanged.

- How to add a new format (recipe):
  1. Implement `parse_newformat_feed(payload: bytes) -> List[Dict]` in
     `partner_adapters.py`. Normalize fields and place raw data in `extra`.
  2. Add unit tests under `tests/` (adapter test, round-trip with
     validation). Keep the adapter small (<= ~100 LOC ideal).
  3. If new fields require DB changes, coordinate with migration plan
     (see ADR 0009). Otherwise keep fields in `extra` until schema
     changes are scheduled.
  4. Add integration test against `src/partners/routes.py` (Flask client)
     to ensure end-to-end ingest works.

Migration / Rollout Notes
------------------------
- Prefer non-breaking additions: store unknown/new fields in `extra`
  (JSON column) until a schema migration is scheduled.
- Use partner-level flags to enable `strict` validation mode for a
  partner to verify they conform to new requirements before making
  schema changes.

Testing
-------
- Unit tests for the new adapter (happy path + malformed examples).
- Integration tests asserting successful ingest via the HTTP endpoint.
- Optional: add contract tests that verify the canonical dict shape.

Consequences
------------
- Adding adapters is low-risk and localized, enabling rapid support for
  new formats.
- Slight duplication of parsing logic across adapters is acceptable; keep
  common helpers in adapters module.

Related ADRs
-----------
- `docs/ADR/0005-input-validation.md` (validation expectations and rules)
- `docs/ADR/0007-modifiability.md` (overall modifiability tactics)

```
