# UML Diagrams

## Logical View: Class Diagram

```mermaid
classDiagram
    class SalesRepo {
        +checkout_transaction(user_id, cart, pay_method, payment_cb)
    }
    class ProductRepo {
        +get_all_products()
        +search_products(q)
        +get_product(id)
        +check_stock(id, qty)
    }
    class AProductRepo {
        +get_all_products()
        +search_products(q)
        +get_product(id)
        +check_stock(id, qty)
    }
    class PaymentAdapter {
        +process(method, total)
    }
    SalesRepo --> ProductRepo
    SalesRepo --> PaymentAdapter
    ProductRepo <|-- AProductRepo
```

## Process View: System Sequence Diagram (Checkout)

```mermaid
sequenceDiagram
  participant U as User
  participant A as Flask App (Routes)
  participant R as SalesRepo + ProductRepo
  participant DB as SQLite
  participant P as Payment Adapter

  U->>A: POST /checkout (cart, method)
  A->>R: checkout_transaction(user, cart, method)
  R->>DB: BEGIN IMMEDIATE
  loop each item
    R->>DB: SELECT stock FROM product WHERE id=?
    R->>DB: UPDATE product SET stock=stock-? WHERE id=?
    R->>DB: INSERT INTO sale_item(...)
  end
  R->>P: process(method, total)
  alt payment ok
    R->>DB: INSERT INTO sale(..., status='PAID')
    R->>DB: INSERT INTO payment(..., status='APPROVED')
    R-->>A: sale_id
  else decline/error
    R->>DB: ROLLBACK
    R-->>A: raise error
  end
```

## Deployment View

```mermaid
deploymentDiagram
  node Client {
    UserBrowser
  }
  node Server {
    FlaskApp
  }
  database SQLite
  UserBrowser --> FlaskApp
  FlaskApp --> SQLite
```

## Implementation View: Package/Module Diagram

```mermaid
flowchart TD
  src["src/"]
  app["app.py"]
  dao["dao.py"]
  product_repo["product_repo.py"]
  payment["payment.py"]
  main["main.py"]
  seed["seed.py"]
  src --> app
  src --> dao
  src --> product_repo
  src --> payment
  src --> main
  src --> seed
  app --> dao
  app --> product_repo
  app --> payment
  app --> main
```

## Use-Case View

```mermaid
usecaseDiagram
  actor User
  User --> (Register)
  User --> (Login)
  User --> (Browse Products)
  User --> (Search Products)
  User --> (Add to Cart)
  User --> (Checkout)
  User --> (View Receipt)
  User --> (View Cart)
  User --> (Remove from Cart)
  User --> (Clear Cart)
```

---

Each diagram above fulfills a specific UML view as required. You can copy these Mermaid diagrams into your documentation or render them using a Mermaid-compatible tool.
