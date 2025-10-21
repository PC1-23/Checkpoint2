```markdown
# ADR 0013: Usability — Make integration easier for partner engineers

Status: Accepted

Quality attribute(s): Usability, Integrability, Supportability

Context
-------
Partners and internal engineers need clear, discoverable guidance to use the
ingest API. Usability includes examples, clear error messages, and quickstart
help so partners can integrate quickly and with minimal support.

Decision
--------
Adopt a few pragmatic usability tactics:

- Publish example payloads alongside the machine-readable contract.
- Provide a human-focused help endpoint with quickstart curl/sample requests.
- Return consistent, machine-friendly JSON error responses for API errors.

Consequences
------------
- Partners can copy example payloads into their CI/tests and reproduce
  expected behavior quickly.
- Support load is reduced because common questions are answered by the
  quickstart help and examples.

Implementation
--------------
- Add `example` to the contract returned by `src/partners/integrability.py`.
- Add endpoints in `src/partners/routes.py`:
  - `GET /partner/contract/info` — returns contract metadata and example (JSON)
  - `GET /partner/contract/example` — returns a single example product (JSON)
  - `GET /partner/help` — returns a small quickstart guide with curl commands
  - JSON error handler to normalize HTTP errors into `{error, details}` shape

Testing
-------
- Unit tests: `tests/test_usability_endpoints.py` verifies the endpoints and
  that missing API key errors are returned as JSON with `error` and `details`.

Related ADRs
-----------
- `docs/ADR/0010-contract.md` (contract publication)

``` 
