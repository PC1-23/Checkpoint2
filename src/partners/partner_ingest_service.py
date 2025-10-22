"""Partner ingest service: validates adapter output and upserts into product catalog.

This module provides a safer upsert that:
- matches by SKU when provided
- falls back to matching by name
- uses a transaction for the entire batch and reports per-item errors
"""
from __future__ import annotations
from typing import List, Dict, Tuple
import sqlite3


def upsert_products(conn: sqlite3.Connection, products: List[Dict], partner_id: int | None = None, feed_hash: str | None = None) -> Tuple[int, List[str]]:
    """Upsert normalized product dicts into product table.

    Returns (count_upserted, errors)
    """
    upserted = 0
    errors: List[str] = []
    cur = conn.cursor()
    # Check idempotency: if partner_id and feed_hash provided and exists, skip
    if partner_id and feed_hash:
        try:
            r = cur.execute("SELECT 1 FROM partner_feed_imports WHERE partner_id = ? AND feed_hash = ? LIMIT 1", (partner_id, feed_hash)).fetchone()
            if r:
                return 0, ["Feed already processed"]
        except sqlite3.OperationalError:
            # table may not exist if schema not updated
            pass
    try:
        for idx, p in enumerate(products):
            try:
                sku = (p.get("sku") or "").strip()
                name = (p.get("name") or "").strip()
                # Support either price_cents (int) or price (float) from adapters
                if "price_cents" in p:
                    price_cents = int(p.get("price_cents", 0))
                else:
                    # convert dollars to cents
                    price_val = p.get("price", 0)
                    try:
                        price_cents = int(round(float(price_val) * 100))
                    except Exception:
                        price_cents = 0
                stock = int(p.get("stock", 0))

                # Prefer matching by sku if present (if schema supports it), otherwise match by name
                # Use case- and whitespace-insensitive name match to avoid missing existing products
                prod_id = None
                if sku:
                    try:
                        r2 = cur.execute("SELECT id FROM product WHERE sku = ?", (sku,)).fetchone()
                        if r2:
                            prod_id = r2[0]
                    except sqlite3.OperationalError:
                        # sku column not present; fall back to name
                        prod_id = None
                if not prod_id:
                    # normalize name lookup to lower(trim(name)) to match ingest normalization
                    try:
                        r = cur.execute("SELECT id FROM product WHERE lower(trim(name)) = lower(trim(?))", (name,)).fetchone()
                    except sqlite3.OperationalError:
                        # fallback to exact match if lower/trim unsupported for some reason
                        r = cur.execute("SELECT id FROM product WHERE name = ?", (name,)).fetchone()
                    if r:
                        prod_id = r[0]

                if prod_id:
                    cur.execute(
                        "UPDATE product SET price_cents = ?, stock = ?, active = 1 WHERE id = ?",
                        (price_cents, stock, prod_id),
                    )
                else:
                    # Attempt to insert; if schema includes sku, try to insert sku column
                    try:
                        cur.execute(
                            "INSERT INTO product (name, price_cents, stock, active, sku) VALUES (?, ?, ?, 1, ?)",
                            (name, price_cents, stock, sku if sku else None),
                        )
                    except sqlite3.OperationalError:
                        # fallback if sku column not present
                        cur.execute(
                            "INSERT INTO product (name, price_cents, stock, active) VALUES (?, ?, ?, 1)",
                            (name, price_cents, stock),
                        )
                upserted += 1
            except Exception as e:
                errors.append(f"Item {idx} error: {e}")
                conn.commit()
                # record feed import if provided
                if partner_id and feed_hash:
                    try:
                        cur.execute("INSERT INTO partner_feed_imports (partner_id, feed_hash) VALUES (?, ?)", (partner_id, feed_hash))
                        conn.commit()
                    except sqlite3.IntegrityError:
                        # ignore duplicate
                        pass
    except Exception as e:
        conn.rollback()
        errors.append(f"Batch error: {e}")
        return upserted, errors

    # commit the successful transaction
    try:
        conn.commit()
    except Exception:
        conn.rollback()

    # record partner_feed_imports if provided and at least one item upserted
    if partner_id and feed_hash and upserted > 0:
        try:
            cur.execute("INSERT INTO partner_feed_imports (partner_id, feed_hash) VALUES (?, ?)", (partner_id, feed_hash))
            conn.commit()
        except sqlite3.IntegrityError:
            # duplicate entry - ignore
            pass

    return upserted, errors


def validate_products(products: List[Dict], strict: bool = False) -> Tuple[List[Dict], List[str]]:
    """Validate normalized product dicts. Returns (valid_items, errors).

    Simple rules:
    - name required and non-empty
    - price_cents must be int >= 0
    - stock must be int >= 0
    - sku optional string
    """
    valid: List[Dict] = []
    errors: List[str] = []
    for idx, p in enumerate(products):
        try:
            name = (p.get("name") or "").strip()
            if not name:
                raise ValueError("name is required")
            # price_cents must be present and an integer >= 0. Treat missing/blank as error.
            if "price_cents" not in p or p.get("price_cents") in (None, ""):
                raise ValueError("price_cents is required")
            price = p.get("price_cents")
            if not isinstance(price, int):
                try:
                    price = int(price)
                except Exception:
                    raise ValueError("price_cents must be integer")
            if price < 0:
                raise ValueError("price_cents must be >= 0")
            stock = p.get("stock", 0)
            if not isinstance(stock, int):
                try:
                    stock = int(stock)
                except Exception:
                    raise ValueError("stock must be integer")
            if stock < 0:
                raise ValueError("stock must be >= 0")
            sku = (p.get("sku") or "").strip()
            # strict mode: enforce max lengths and character rules
            if strict:
                if len(name) > 256:
                    raise ValueError("name too long")
                if sku and len(sku) > 128:
                    raise ValueError("sku too long")

            valid.append({
                "sku": sku,
                "name": name,
                "price_cents": price,
                "stock": stock,
                "partner_id": p.get("partner_id", "unknown"),
                "extra": p.get("extra", {}),
            })
        except Exception as e:
            errors.append(f"Item {idx}: {e}")
    return valid, errors
