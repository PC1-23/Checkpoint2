from src.partners.partner_ingest_service import validate_products


def test_validate_products_happy_path():
    items = [{"sku": "s1", "name": "Product 1", "price_cents": 100, "stock": 5}]
    valid, errors = validate_products(items)
    assert len(valid) == 1
    assert errors == []


def test_validate_products_rejects_missing_name():
    items = [{"sku": "s2", "name": "", "price_cents": 50, "stock": 1}]
    valid, errors = validate_products(items)
    assert len(valid) == 0
    assert any("name is required" in e for e in errors)


def test_validate_products_rejects_negative_price_stock():
    items = [{"sku": "s3", "name": "P", "price_cents": -10, "stock": 1}, {"sku": "s4", "name": "P2", "price_cents": 10, "stock": -2}]
    valid, errors = validate_products(items)
    assert len(valid) == 0
    assert any("price_cents must be >= 0" in e for e in errors)
    assert any("stock must be >= 0" in e for e in errors)
