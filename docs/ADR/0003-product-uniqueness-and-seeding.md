# ADR 0003: Product Uniqueness and Seeding

Date: 2025-09-14

## Status
Accepted

## Context
Seeding could create duplicate products if rerun. Duplicates break UX and complicate stock math.

## Decision
- Enforce `UNIQUE(name)` on `product.name` in the schema.
- Use `INSERT OR IGNORE` in seed script for products.

## Consequences
- Idempotent seeds; no duplicate products.
- Clearer cart behavior and consistent product lookups.
