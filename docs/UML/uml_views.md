# UML Diagrams

## Logical View: Class Diagram

```mermaid
classDiagram
  class SalesRepo {
    +checkout_transaction(user_id, cart, pay_method, payment_cb)
    +create_sale(...)
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
  class PaymentResilience {
    +process_with_retry(method, total)
  }
  class CircuitBreaker {
    +allow_request()
    +record_success()
    +record_failure()
  }
  class FlashSaleManager {
    +is_flash_sale_active(product_id)
    +get_effective_price(product_id)
  }
  class RateLimiter {
    +allow(client_id)
  }
  class PartnerIngestService {
    +validate_products(feed)
    +enqueue_feed(feed)
  }
  class PartnerAdapter {
    +parse_feed(payload, content_type)
  }
  class IngestJob {
    +id
    +status
    +errors
    +diagnostics
  }
  class IngestWorker {
    +process_next_job_once()
  }
  class DiagnosticsOffload {
    +store(blob) : key
    +retrieve(key) : blob
  }

  SalesRepo --> ProductRepo
  SalesRepo --> PaymentAdapter
  PaymentResilience --> PaymentAdapter
  PaymentResilience --> CircuitBreaker
  FlashSaleManager --> ProductRepo
  FlashSaleManager --> RateLimiter
  PartnerIngestService --> PartnerAdapter
  PartnerIngestService --> IngestJob
  IngestWorker --> IngestJob
  IngestWorker --> DiagnosticsOffload
  ProductRepo <|-- AProductRepo
```

## Process View: System Sequence Diagram (Checkout)

```mermaid
sequenceDiagram
  participant U as User
  participant A as Flask App (Routes)
  participant R as SalesRepo + ProductRepo
  participant DB as SQLite
  participant PR as PaymentResilience
  participant CB as CircuitBreaker
  participant P as Payment Adapter

  U->>A: POST /checkout (cart, method)
  A->>R: checkout_transaction(user, cart, method)
  R->>DB: BEGIN IMMEDIATE
  loop each item
    R->>DB: SELECT stock FROM product WHERE id=?
    R->>DB: UPDATE product SET stock=stock-? WHERE id=?
    R->>DB: INSERT INTO sale_item(...)
  end
  R->>PR: process_with_retry(method, total)
  PR->>CB: allow_request()
  alt allowed
    PR->>P: process(method, total)
    alt payment ok
      PR->>CB: record_success()
      R->>DB: INSERT INTO sale(..., status='PAID')
      R->>DB: INSERT INTO payment(..., status='APPROVED')
      R-->>A: sale_id
    else decline/error
      PR->>CB: record_failure()
      R->>DB: ROLLBACK
      R-->>A: raise error
    end
  else open/short-circuit
    PR-->>A: payment service unavailable (circuit open)
  end
```

## Process View: Partner Ingest Sequence

```mermaid
sequenceDiagram
  participant Pn as Partner (HTTP)
  participant A as Flask App (Partner routes)
  participant SV as PartnerIngestService
  participant Q as Enqueue (module-level seam)
  participant J as IngestJob (DB)
  participant W as IngestWorker
  participant DO as DiagnosticsOffload

  Pn->>A: POST /partner/ingest (feed)
  A->>SV: parse_feed(payload)
  SV->>SV: validate_products(parsed)
  alt sync validation only
    SV-->>A: validation summary (accepted/rejected/errors)
  else async accept
    A->>Q: enqueue_feed(parsed)
    Q->>J: insert job (status=queued)
    J-->>A: job_id
    A-->>Pn: 202 Accepted (job_id)
  end

  note over W, J: Worker polls DB / queue
  W->>J: fetch next job
  W->>SV: validate_products(job.feed)
  alt validation errors
    W->>DO: store(large_diagnostics)
    DO-->>W: diagnostics_key
    W->>J: update(status='failed', diagnostics_key)
  else success
    W->>SV: upsert_products(cleaned)
    W->>J: update(status='completed', diagnostics=summary)
  end

  A->>J: GET /partner/jobs/<id>
  J-->>A: job metadata + diagnostics or diagnostics_key
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
    partners_routes["src/partners/routes.py\n- ingest endpoints, job status"]
    partners_svc["src/partners/partner_ingest_service.py\n- validation, upsert"]
    partners_adapters["src/partners/partner_adapters.py\n- feed parsers"]
    ingest_queue["src/partners/ingest_queue.py\n- enqueue, worker loop"]
    integrability["src/partners/integrability.py\n- contract, validator"]
    flash["src/flash_sales/\n- manager, cache, rate-limiter"]
    resilience["src/flash_sales/payment_resilience.py\n- retry & circuit breaker"]
    worker["Background Worker\n- ingest_queue.process_next_job_once"]
    diagnostics["DiagnosticsOffload (table/object store)"]
  end

  routes --> dao
  routes --> product_repo
  routes --> payment
  routes --> partners_routes
  partners_routes --> partners_svc
  partners_routes --> partners_adapters
  partners_svc --> ingest_queue
  partners_svc --> diagnostics
  ingest_queue --> worker
  worker --> partners_svc
  worker --> diagnostics
  routes --> flash
  flash --> resilience
  resilience --> payment
  dao --> dbNode
  payment --> extPay
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