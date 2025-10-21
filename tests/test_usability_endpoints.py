import json
from src.partners.routes import app


def test_help_endpoint():
    c = app.test_client()
    rv = c.get('/partner/help')
    assert rv.status_code == 200
    info = rv.get_json()
    assert 'post_example' in info


def test_help_and_error_format():
    c = app.test_client()
    rv = c.get('/partner/help')
    assert rv.status_code == 200
    help_json = rv.get_json()
    assert 'post_example' in help_json

    # trigger a 401 from ingest by calling without API key
    rv2 = c.post('/partner/ingest', data='[]', content_type='application/json')
    assert rv2.status_code in (401, 400)
    j = rv2.get_json()
    assert 'error' in j and 'details' in j
