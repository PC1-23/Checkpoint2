import pytest
from src.partners.partner_adapters import parse_json_feed, parse_csv_feed


def test_parse_json_feed():
    payload = b'[{"sku":"s1","name":" Item A ","price":1.23,"stock":2}]'
    out = parse_json_feed(payload)
    assert isinstance(out, list)
    assert out[0]["sku"] == "s1"
    assert out[0]["name"] == "Item A"
    assert out[0]["price_cents"] == 123


def test_parse_csv_feed():
    csv = "sku,name,price,stock\n s2, Item B ,2.5,3\n"
    out = parse_csv_feed(csv.encode())
    assert out[0]["sku"] == "s2"
    assert out[0]["name"] == "Item B"
    assert out[0]["price_cents"] == 250
