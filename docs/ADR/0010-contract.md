```markdown
# ADR 0010: Contract publication and pre-validation

Status: Accepted

Quality attribute(s): Integrability, Usability, Testability

Context
-------
Partners need a stable, machine-readable contract to validate product
feeds before submission. A clear contract reduces integration friction and
support load.

Decision
--------
Publish a discoverable, machine-readable contract that describes the
canonical product document accepted by the ingest pipeline.

- Expose the contract at `GET /partner/contract`.
- Provide a lightweight, repo-side validator for CI and test convenience.
- Return a `contract_version` alongside the contract so partners can detect
  changes programmatically.

Consequences
------------
- Partners can fetch the contract and validate feeds in CI before sending.
- The platform must keep the contract updated and communicate version bumps
  when breaking changes are required.

Implementation
--------------
- Contract: implemented as a JSON-like dict (candidate for full JSON Schema)
  in `src/partners/integrability.py::get_contract`.
- Endpoint: `src/partners/routes.py::partner_contract` returns the contract and
  `contract_version`.
- Validator: lightweight `validate_against_contract` in
  `src/partners/integrability.py` for tests and partner reference. Partners
  are encouraged to use full JSON Schema tooling in their CI.

Testing
-------
- Unit tests: `tests/test_integrability.py` should verify the contract
  endpoint and validator behavior.

Related ADRs
-----------
- `docs/ADR/0005-input-validation.md` (validation rules)

``` 
