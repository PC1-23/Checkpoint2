# ADR 0005: Persistence Style – DAO vs ORM

**Status:** Accepted

## Context
We needed a way to access and manipulate persistent data (users, products, sales, payments) from our Flask application. The team is split: Partner A owns product/user, Partner B owns sales/checkout. We wanted clear boundaries and testability.

## Decision
We chose a DAO (Data Access Object) pattern. The `ProductRepo` and `SalesRepo` classes encapsulate all database access. No ORM (like SQLAlchemy) is used; instead, we use raw SQL queries and manage transactions explicitly.

## Consequences
- **Pros:**
  - Clear separation between business logic and persistence
  - Easy to swap implementations (e.g., for testing or future refactoring)
  - Full control over SQL and transactions
- **Cons:**
  - More boilerplate than using an ORM
  - Manual mapping between DB rows and Python objects
- **Trade-offs:**
  - Chose explicitness and control over rapid development with an ORM

## Alternatives Considered
- **ORM (e.g., SQLAlchemy):**
  - Would reduce boilerplate and provide object mapping
  - Would add complexity and hide some SQL details
- **Direct SQL in routes:**
  - Would reduce indirection, but mix business logic and persistence, making testing and maintenance harder
