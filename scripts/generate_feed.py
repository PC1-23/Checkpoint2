"""Generate product feed files for testing partner ingest.

Usage:
  python scripts/generate_feed.py --count 1000 --out feeds/large_products.json

This script will create a JSON array of product objects.
"""
import json
import os
import argparse
from random import randrange, choice

NAMES = ["Widget", "Gadget", "Thingamajig", "Doodad", "Contraption"]


def make_product(i):
    sku = f"gen-{i:06d}"
    name = f"{choice(NAMES)} {i}"
    price_cents = randrange(100, 10000)
    stock = randrange(0, 100)
    return {"sku": sku, "name": name, "price_cents": price_cents, "stock": stock}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--out", type=str, default="feeds/large_products.json")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    items = [make_product(i) for i in range(1, args.count + 1)]
    with open(args.out, "w") as f:
        json.dump(items, f)
    print(f"Wrote {len(items)} products to {args.out}")


if __name__ == "__main__":
    main()
