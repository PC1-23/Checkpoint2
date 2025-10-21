"""Partner adapters for CSV and JSON feeds (normalized output).
This module is used by src.partners.routes.py.
"""
from __future__ import annotations
import json
import csv
from io import StringIO
from typing import List, Dict

def parse_json_feed(payload: bytes) -> List[Dict]:
    data = json.loads(payload.decode("utf-8"))
    out = []
    for item in data:
        sku = str(item.get("sku") or item.get("id") or "").strip()
        name = str(item.get("name", "")).strip()
        price = item.get("price_cents") if item.get("price_cents") is not None else item.get("price", 0)
        # Normalize price to integer cents
        if isinstance(price, int):
            price_cents = price
        elif isinstance(price, float):
            price_cents = int(round(price * 100))
        else:
            try:
                price_cents = int(price)
            except Exception:
                try:
                    price_cents = int(float(price) * 100)
                except Exception:
                    price_cents = 0

        out.append({
            "sku": sku,
            "name": name,
            "price_cents": price_cents,
            "stock": int(item.get("stock", 0)),
            "partner_id": item.get("partner_id", "unknown"),
            "extra": item,
        })
    return out

def parse_csv_feed(payload: bytes) -> List[Dict]:
    s = payload.decode("utf-8")
    reader = csv.DictReader(StringIO(s))
    out = []
    for row in reader:
        price = row.get("price_cents") or row.get("price") or "0"
        try:
            price_cents = int(price)
        except ValueError:
            try:
                price_cents = int(float(price) * 100)
            except Exception:
                price_cents = 0
        sku = str(row.get("sku") or row.get("id") or "").strip()
        name = str(row.get("name", "")).strip()
        out.append({
            "sku": sku,
            "name": name,
            "price_cents": price_cents,
            "stock": int(row.get("stock", 0)),
            "partner_id": row.get("partner_id", "unknown"),
            "extra": row,
        })
    return out
