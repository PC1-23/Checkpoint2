import json
import pathlib
import sys

# Ensure repo root is on sys.path
root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from src.partners.integrability import get_contract


def test_contract_is_valid_jsonschema():
    contract = get_contract()
    schema = contract.get("schema")
    assert schema is not None

    # Validate schema using jsonschema
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        raise AssertionError("jsonschema is required for this test")

    # This will raise if the schema itself is invalid
    Draft202012Validator.check_schema(schema)


def test_contract_endpoint_returns_schema():
    # direct import of app and use Flask test client
    try:
        from src.partners.routes import app
        c = app.test_client()
    except Exception:
        raise AssertionError("Unable to import app for endpoint test")

    rv = c.get('/partner/contract')
    assert rv.status_code == 200
    assert rv.content_type == 'application/schema+json'
    schema = json.loads(rv.data)
    # schema should include $schema and required
    assert "$schema" in schema
    assert "required" in schema
