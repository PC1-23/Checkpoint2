# Database Schema (UML-ish)

```mermaid
erDiagram
  USER ||--o{ SALE : makes
  SALE ||--|{ SALE_ITEM : contains
  PRODUCT ||--o{ SALE_ITEM : included_in
  SALE ||--o{ PAYMENT : recorded_by

  USER {
    int id PK
    text name
    text username UNIQUE
    text password
  }
  PRODUCT {
    int id PK
    text name UNIQUE
    int price_cents
    int stock
    int active (0/1)
  }
  SALE {
    int id PK
    int user_id FK
    datetime sale_time
    int total_cents
    text status
  }
  SALE_ITEM {
    int sale_id FK
    int product_id FK
    int quantity
    int price_cents
  }
  PAYMENT {
    int sale_id FK
    text method
    int amount_cents
    text status
    text ref
  }
```
