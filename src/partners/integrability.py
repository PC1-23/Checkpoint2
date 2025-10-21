"""Contract publication and lightweight validator for partner feeds.

Provides a machine-readable contract and a small validator used by tests
and the `/partner/contract/validate` sandbox endpoint.
"""
from __future__ import annotations
from typing import Dict, Any, List, Tuple

CONTRACT = {
    "contract_version": "1.0",
    "example": {
        "sku": "sku-example-123",
        "name": "Sample Product",
        "price_cents": 1999,
        "stock": 10
    },
    "required": ["name", "price_cents"],
    "fields": {
        "sku": {"type": "string", "max_length": 128},
        "name": {"type": "string", "max_length": 256},
        "price_cents": {"type": "integer", "minimum": 0},
        "stock": {"type": "integer", "minimum": 0}
    }
}


def get_contract() -> Dict[str, Any]:
    return CONTRACT


def validate_against_contract(items: List[Dict]) -> Tuple[List[Dict], List[str]]:
    """A tiny validator returning (valid_items, errors).

    This intentionally mirrors `validate_products` semantics but is
    lightweight and intended for partner consumption/sandbox validation.
    """
    valid = []
    errors = []
    for i, it in enumerate(items):
        try:
            name = (it.get("name") or "").strip()
            if not name:
                raise ValueError("name is required")
            price = it.get("price_cents", None)
            if price is None:
                raise ValueError("price_cents is required")
            if not isinstance(price, int):
                try:
                    price = int(price)
                except Exception:
                    raise ValueError("price_cents must be integer")
            if price < 0:
                raise ValueError("price_cents must be >= 0")
            stock = it.get("stock", 0)
            if not isinstance(stock, int):
                try:
                    stock = int(stock)
                except Exception:
                    raise ValueError("stock must be integer")
            valid.append({
                "sku": (it.get("sku") or "").strip(),
                "name": name,
                "price_cents": price,
                "stock": stock,
                "extra": it.get("extra", {})
            })
        except Exception as e:
            errors.append(f"Item {i}: {e}")
    return valid, errors
