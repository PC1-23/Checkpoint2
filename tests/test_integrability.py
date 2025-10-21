from src.partners.integrability import get_contract, validate_against_contract
from src.partners.routes import app


def test_get_contract_endpoint():
    client = app.test_client()
    rv = client.get('/partner/contract')
    assert rv.status_code == 200
    data = rv.get_json() if hasattr(rv, 'get_json') else rv.get_data(as_text=True)
    # get_contract returns a dict; ensure contract_version present
    contract = get_contract()
    assert contract.get('contract_version') == '1.0'


def test_validator_rejects_invalid_item():
    item = {"sku": "", "name": "", "price_cents": -1, "stock": -1}
    ok, errs = validate_against_contract(item)
    assert not ok
    assert any('is required' in e or 'must be' in e for e in errs)
