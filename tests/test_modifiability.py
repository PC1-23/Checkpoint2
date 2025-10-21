from src.partners.partner_adapters import parse_xml_feed
from src.partners.partner_ingest_service import validate_products


def test_parse_xml_feed_basic():
    payload = b"""
    <root>
      <item>
        <sku>xml-1</sku>
        <name>XML Product</name>
        <price>3.50</price>
        <stock>2</stock>
      </item>
    </root>
    """
    items = parse_xml_feed(payload)
    assert len(items) == 1
    assert items[0]["sku"] == "xml-1"
    assert items[0]["name"] == "XML Product"


def test_validate_products_strict_rejects_long_name():
    long_name = "x" * 300
    valid, errors = validate_products([{"sku": "s1", "name": long_name, "price_cents": 100, "stock": 1}], strict=True)
    assert len(valid) == 0
    assert any("name too long" in e for e in errors)
