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
flowchart TD
  %% Deployment diagram with web tier, worker, storage, cache and external services
  subgraph Internet[Internet]
    UB["User Browser\n(Client)"]
  end

  subgraph Edge[Edge / Ingress]
    LB["Load Balancer / CDN / API Gateway"]
  end

  subgraph AppTier[Application Tier]
    WA["Web App (Flask)\n- routes\n- auth\n- templates"]
    WK["Background Worker\n- ingest queue\n- diagnostics processor"]
  end

  subgraph DataTier[Data & Cache]
    DB[("SQLite DB")]
    Cache["Redis / Cache (demo: in-memory)"]
    OBJ["Object store (diagnostics offload)\n(e.g. S3) - optional"]
  end

  subgraph External[External Services]
    PAY["Payment Provider"]
    PARTNER["Partner Feed (HTTP/SFTP)"]
  end

  UB --> LB
  LB --> WA
  LB --> WK
  WA --> DB
  WA --> Cache
  WK --> DB
  WK --> OBJ
  WA --> PAY
  WA --> PARTNER
  style Internet fill:#f9f,stroke:#333,stroke-width:1px
  style Edge fill:#eef,stroke:#333,stroke-width:1px
  style AppTier fill:#efe,stroke:#333,stroke-width:1px
  style DataTier fill:#ffe,stroke:#333,stroke-width:1px
  style External fill:#fef,stroke:#333,stroke-width:1px
```

## Implementation View: Package / Module Diagram

```mermaid
flowchart TB
  subgraph App[Application Modules]
    routes["src/app.py / src/main.py\n- HTTP routes / blueprints"]
    dao["src/dao.py\n- SalesRepo, DB access"]
    product_repo["src/product_repo.py\n- ProductRepo"]
    payment["src/payment.py\n- Payment Adapters & resilience"]
    partners["src/partners/\n- routes, adapters, ingest queue"]
    flash["src/flash_sales/\n- manager, cache, rate-limiter"]
    worker["Background Worker\n- ingest_queue.process_next_job_once"]
  end

  routes --> dao
  routes --> product_repo
  routes --> payment
  routes --> partners
  routes --> flash
  partners --> worker
  worker --> dao
  worker --> payment
  partners --> product_repo
  payment --> "External: Payment Provider"
  dao --> "SQLite DB (persist)"
```


## Use-Case View

```mermaid
%% Use-case style layout: system boundary with actors left/right and vertical use-cases
flowchart LR
  actorUser[(User)]
  actorPartner[(Partner)]
  actorAdmin[(Admin)]

  subgraph SystemBoundary["Online Shop System"]
    direction TB
    UC1((Register))
    UC2((Login))
    UC3((Browse Products))
    UC4((Search Products))
    UC5((Add to Cart))
    UC6((View Cart))
    UC7((Checkout))
    UC8((View Receipt))
    UC9((Partner Catalog Ingest))
    UC10((Admin Onboard Partner))
  end

  actorUser --> UC1
  actorUser --> UC2
  actorUser --> UC3
  actorUser --> UC4
  actorUser --> UC5
  actorUser --> UC6
  actorUser --> UC7
  actorUser --> UC8

  actorPartner --> UC9
  actorAdmin --> UC10

  style SystemBoundary fill:#fff7e6,stroke:#333,stroke-width:1px
```

---