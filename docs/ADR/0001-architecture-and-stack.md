# ADR 0001: Architecture and Stack

Date: 2025-09-14

## Status
Accepted

## Context
We need a lightweight two-tier app for a retail prototype with a simple web UI, persistent storage, atomic checkout, and tests. The team is split: Partner A focuses on product/user, Partner B on sales/checkout.

## Decision
- Use Flask for the web layer and SQLite for persistence.
- Keep a DAO seam with `SalesRepo` and `ProductRepo` to separate app logic from storage.
- Model payment as a mock adapter (`payment.process`) to simulate approvals/declines.
- Store prices in cents (integers) and enforce unique product names.

## Consequences
- Simple setup and fast iteration (no external DB required).
- Easier to swap product repo or payment adapter if needed.
- SQLite constraints (FKs, UNIQUE) protect data integrity during checkout.
