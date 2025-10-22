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
        # don't default missing price to 0; let validator report missing/blank
        if "price_cents" in item:
            price = item.get("price_cents")
        elif "price" in item:
            price = item.get("price")
        else:
            price = None
        # Normalize price to integer cents when possible. If parsing fails,
        # keep the original value so validation can reject it with a
        # structured validation error instead of raising here.
        price_cents = None
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
                    # leave as raw value (could be string) and let validator handle it
                    price_cents = price

        # stock: attempt to coerce to int, otherwise keep raw value for validation
        # stock: only coerce if present; leave as None when missing so validator can enforce presence
        raw_stock = item.get("stock") if "stock" in item else None
        try:
            stock_val = int(raw_stock) if raw_stock is not None and raw_stock != "" else None
        except Exception:
            stock_val = raw_stock

        obj = {
            "sku": sku,
            "name": name,
            "partner_id": item.get("partner_id", "unknown"),
            "extra": item,
        }
        # include price_cents and stock keys only when present (may be None to signal missing)
        obj["price_cents"] = price_cents
        obj["stock"] = stock_val
        out.append(obj)
    return out

def parse_csv_feed(payload: bytes) -> List[Dict]:
    # tolerate BOM and various delimiters (comma, semicolon, tab, pipe)
    s = payload.decode("utf-8-sig")
    # try to detect delimiter using csv.Sniffer; fall back to comma
    delimiter = ','
    try:
        sample_lines = s.splitlines()
        sample = '\n'.join(sample_lines[:2]) if sample_lines else s
        dialect = csv.Sniffer().sniff(sample, delimiters=[',', ';', '\t', '|'])
        delimiter = dialect.delimiter
    except Exception:
        # couldn't sniff reliably; keep comma
        delimiter = ','

    reader = csv.DictReader(StringIO(s), delimiter=delimiter)
    out = []
    for row in reader:
        # prefer explicit price_cents, then price. Keep raw if parsing fails so
        # validate_products can report an error instead of this function raising.
        # prefer explicit price_cents, then price. Leave as None when blank so validator rejects missing price
        if "price_cents" in row and row.get("price_cents") != "":
            price = row.get("price_cents")
        elif "price" in row and row.get("price") != "":
            price = row.get("price")
        else:
            price = None
        price_cents = None
        if price is not None and price != "":
            try:
                price_cents = int(price)
            except Exception:
                try:
                    price_cents = int(float(price) * 100)
                except Exception:
                    price_cents = price
        sku = str(row.get("sku") or row.get("id") or "").strip()
        name = str(row.get("name", "")).strip()

        # stock: attempt to coerce to int, otherwise keep raw value for validation
        raw_stock = row.get("stock") if "stock" in row else None
        try:
            stock_val = int(raw_stock) if raw_stock is not None and raw_stock != "" else None
        except Exception:
            stock_val = raw_stock

        obj = {
            "sku": sku,
            "name": name,
            "partner_id": row.get("partner_id", "unknown"),
            "extra": row,
        }
        obj["price_cents"] = price_cents
        obj["stock"] = stock_val
        out.append(obj)
    return out


# XML adapter removed in moderate prune; keep JSON and CSV only


def parse_feed(payload: bytes, content_type: str = "application/json", feed_version: str | None = None) -> List[Dict]:
    """Dispatch to the appropriate adapter based on content type and optional feed_version.

    This keeps a single call site for routes and allows future versioned
    adapters to be added without changing route logic.
    """
    # normalize content type
    ct = (content_type or "").lower()
    # Currently support JSON and CSV only
    if ct.startswith("application/json") or ct.endswith("+json"):
        # future: dispatch by feed_version if needed
        return parse_json_feed(payload)
    # fallback to csv parser for other content types / form uploads
    return parse_csv_feed(payload)
