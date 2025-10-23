```markdown
# ADR 0011: Feed versioning and adapter negotiation

Status: Accepted

Quality attribute(s): Modifiability

Context
-------
The platform will evolve the feed contract over time. We need a way to
introduce backward-compatible additions and manage breaking changes with
minimal disruption to partners.

Decision
--------
- Support feed versioning via `X-Feed-Version` header and/or a partner
  profile field.
- Implement versioned adapters and selective adapter dispatch based on the
  requested feed version.
- Use the normalized `extra` field to carry forward-compatible fields that
  newer adapters may populate but older consumers may ignore.

Consequences
------------
- Partners can opt into newer versions while older integrations continue to
  function.
- The system needs to maintain multiple adapters (or version-aware
  adapters) and tests that exercise each supported version.

Implementation
--------------
- Routes accept `X-Feed-Version` and pass it to adapter selection
  logic in `src/partners/routes.py`.
- Adapters per format/version live in `src/partners/partner_adapters.py`.
- Contract metadata reflects available versions (see
  `src/partners/integrability.py::get_contract`).

Testing
-------
- Add unit tests for adapter dispatch and an integration test that sends
  `X-Feed-Version: 2` to exercise v2 parsing behavior.

Related ADRs
-----------
- `docs/ADR/0010-contract.md` (contract publication)
- `docs/ADR/0007-modifiability.md` (adapter pattern)

``` 
