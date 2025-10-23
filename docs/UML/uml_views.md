# UML Diagrams

## Logical View: Class Diagram

```mermaid
classDiagram
    %% ====== FLASH SALES MODULE (Your Work) ======
    
    %% Core Business Logic
    class FlashSaleManager {
        -conn: Connection
        +is_flash_sale_active(product_id: int) bool
        +get_effective_price(product_id: int) int
        +get_flash_products() List~Product~
        +log_event(product_id: int, event_type: str, details: str)
    }

    %% Performance Tactics
    class RateLimiter {
        -max_requests: int
        -window_seconds: int
        -requests: Dict
        -lock: Lock
        +is_allowed(identifier: str) bool
        +reset(identifier: str)
        +get_remaining(identifier: str) int
    }

    class SimpleCache {
        -default_ttl: int
        -cache: Dict
        -lock: Lock
        +get(key: str) Any
        +set(key: str, value: Any, ttl: int)
        +delete(key: str)
        +clear()
    }

    %% Availability Tactics
    class CircuitBreaker {
        -failure_threshold: int
        -timeout_seconds: int
        -state: CircuitState
        -failure_count: int
        +call(func: Callable) Any
        +record_success()
        +record_failure()
        +reset()
        +get_state() CircuitState
    }

    class CircuitState {
        <<enumeration>>
        CLOSED
        OPEN
        HALF_OPEN
    }

    class RetryDecorator {
        <<function>>
        +retry(max_attempts, delay_seconds, exceptions)
    }

    class PaymentResilience {
        -circuit_breaker: CircuitBreaker
        +process_payment_with_retry(method: str, amount_cents: int) Tuple
    }

    %% ====== PARTNER INTEGRATION MODULE (Vanessa's Work) ======
    
    class PartnerIngestService {
        -conn: Connection
        +validate_products(feed) ValidationResult
        +enqueue_feed(feed) JobId
    }

    class PartnerAdapter {
        +parse_feed(payload, content_type) List~Product~
    }

    class IngestQueue {
        +insert_job(status: str) JobId
        +fetch_next_job_once() Job
    }

    class IngestWorker {
        +process_next_job_once()
        +validate_products(job_feed)
        +store_diagnostics(diagnostics)
    }

    class DiagnosticsOffload {
        +store(blob: bytes) str
        +retrieve(key: str) bytes
    }

    class AuthMiddleware {
        +verify_api_key(key: str) bool
    }

    class InputValidator {
        +validate_feed(data) ValidationResult
        +sanitize_input(data) str
    }

    %% ====== SHARED MODULES ======
    
    class ProductRepo {
        -conn: Connection
        +get_all_products() List~Product~
        +search_products(query: str) List~Product~
        +get_product(id: int) Product
        +check_stock(id: int, qty: int) bool
    }

    class AProductRepo {
        -conn: Connection
        +get_all_products() List~Product~
        +get_product(id: int) Product
        +check_stock(id: int, qty: int) bool
    }

    class SalesRepo {
        -conn: Connection
        +checkout_transaction(user_id, cart, method, payment_cb)
        +create_sale(user_id, cart, payment_info)
    }

    class PaymentAdapter {
        +process(method: str, total: int) Tuple
    }

    %% ====== RELATIONSHIPS ======
    
    %% Flash Sales relationships
    FlashSaleManager --> ProductRepo : uses
    FlashSaleManager --> SimpleCache : caches results
    ProductRepo <|-- AProductRepo : inherits
    
    SalesRepo --> PaymentAdapter : uses
    SalesRepo --> RateLimiter : protected by
    
    PaymentResilience --> CircuitBreaker : uses
    PaymentResilience --> RetryDecorator : applies
    PaymentResilience --> PaymentAdapter : wraps
    CircuitBreaker --> CircuitState : has state
    
    %% Partner Integration relationships
    PartnerIngestService --> PartnerAdapter : uses
    PartnerIngestService --> IngestQueue : enqueues to
    PartnerIngestService --> AuthMiddleware : protected by
    PartnerIngestService --> InputValidator : validates with
    
    IngestWorker --> IngestQueue : polls from
    IngestWorker --> PartnerAdapter : uses
    IngestWorker --> DiagnosticsOffload : logs to
    IngestWorker --> ProductRepo : updates
    
    PartnerAdapter --> InputValidator : uses

    %% Notes
    note for FlashSaleManager "Flash Sales Module:\nManages time-based discounts"
    note for PartnerIngestService "Partner Integration Module:\nIngests external product feeds"
    note for RateLimiter "Shared Tactic:\nProtects both flash sales\nand partner endpoints"
    note for CircuitBreaker "Availability Pattern:\nPayment service protection"
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