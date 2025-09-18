# ADR 0001: Database Choice – SQL (SQLite) vs NoSQL

**Status:** Accepted

## Context
We needed a persistent data store for users, products, sales, and payments. The requirements included relational data (users make sales, sales have items, products are referenced, payments are linked to sales), atomic transactions (for checkout), and easy local development.

## Decision
We chose SQLite, a lightweight SQL database, as our persistent store. All data is stored in a single file (`app.sqlite`), and the schema is defined in SQL (`db/init.sql`).

## Consequences
- **Pros:**
  - Simple setup (no server required)
  - Supports transactions and foreign keys
  - Easy to inspect and debug
  - Portable and cross-platform
- **Cons:**
  - Not suitable for high-concurrency or large-scale deployments
  - No horizontal scaling
- **Trade-offs:**
  - Chose simplicity and reliability for a prototype over scalability

## Alternatives Considered
- **NoSQL (e.g., MongoDB):**
  - Would simplify some data modeling, but would complicate transactions and joins
  - Would require running a separate server
- **Other SQL DBs (e.g., PostgreSQL, MySQL):**
  - More scalable, but overkill for a local prototype
