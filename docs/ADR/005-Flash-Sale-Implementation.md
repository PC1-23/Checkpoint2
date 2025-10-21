# ADR-005: Flash Sale Implementation Strategy

**Status:** Accepted

**Date:** 2025-10-21

**Decision Makers:** Flash Sales Team

---

## Context

The business requires a "flash sales" feature to offer time-limited discounts that drive urgency and boost sales. Flash sales have specific characteristics that create architectural challenges:

**Business Requirements:**
- Products available at discounted prices for limited time windows
- Clear visual indication of flash sale status (badges, countdown timers)
- Automatic price transitions (regular → flash → regular)
- High traffic spikes during active sales
- Fair inventory allocation under concurrent access

**Technical Challenges:**
- Determining "is sale active?" efficiently for every page load
- Applying correct pricing (flash vs. regular) consistently
- Handling timezone-aware sale windows
- Scaling to handle traffic surges
- Maintaining data integrity during concurrent checkouts

---

## Decision

We will implement flash sales using a **database-driven time window approach** with the following architecture:

### Data Model

**Extend Product Table:**
```sql
ALTER TABLE product ADD COLUMN flash_price_cents INTEGER;
ALTER TABLE product ADD COLUMN sale_start TIMESTAMP;
ALTER TABLE product ADD COLUMN sale_end TIMESTAMP;
```

**Key Design Principles:**
1. **Time-Window Based:** Sale active if `now >= sale_start AND now < sale_end`
2. **Database-Level Storage:** Flash sale attributes stored with product data
3. **Centralized Logic:** `FlashSaleManager` encapsulates all flash sale business rules
4. **Automatic Expiration:** No manual activation/deactivation required

### Component Architecture

**FlashSaleManager** (`src/flash_sales/flash_sale_manager.py`):
- Determines if flash sale is currently active
- Returns effective price (flash or regular)
- Queries active flash products
- Logs flash sale events for analytics

**Benefits:**
- Single source of truth for flash sale logic
- Easy to test in isolation
- Reusable across different endpoints
- Clear separation of concerns

---

## Rationale

### Why Database Columns Over Separate Table?

**Chosen: Extend Product Table**

**Pros:**
- Simpler queries (no joins needed)
- Atomic reads (flash price with product in one query)
- Better performance (fewer table scans)
- Easier to understand and maintain

**Cons:**
- Nullable columns (not all products have flash sales)
- Schema migration required

**Alternative: Separate FlashSale Table**

**Pros:**
- Normalized design
- No nullable columns
- Can track historical flash sales

**Cons:**
- Requires join for every product query
- More complex queries
- Performance overhead
- Overkill for current requirements

**Decision:** Simplicity and performance outweigh normalization benefits for this use case.

### Why Time-Window Approach Over Status Flag?

**Chosen: Time Windows (sale_start, sale_end)**

**Pros:**
- Automatic activation/deactivation (no cron jobs needed)
- Timezone-aware by design
- Predictable behavior
- Easy to query "all active sales"
- Can schedule sales in advance

**Cons:**
- Must check timestamps on every query
- Server time must be accurate

**Alternative: is_flash_sale Boolean Flag**

**Pros:**
- Simple boolean check
- No timestamp parsing

**Cons:**
- Requires manual activation/deactivation
- Needs scheduler/cron job for automation
- Prone to human error (forgot to deactivate)
- Can't schedule in advance easily

**Decision:** Automation and reliability outweigh simplicity of boolean flag.

### Why FlashSaleManager Class?

**Chosen: Dedicated Manager Class**

**Pros:**
- Encapsulates flash sale business logic
- Single responsibility (only flash sale concerns)
- Easy to test independently
- Can be mocked in other tests
- Centralized logic prevents duplication

**Cons:**
- Additional layer of abstraction
- Slightly more code

**Alternative: Inline Logic in Routes/Repo**

**Pros:**
- Fewer files
- Less abstraction

**Cons:**
- Logic scattered across codebase
- Difficult to test
- Violates DRY (duplication likely)
- Hard to modify flash sale rules

**Decision:** Maintainability and testability justify the abstraction.

---

## Alternatives Considered

### 1. Redis-Based Flash Sale State
- Very fast access
- Can handle extreme scale
- Additional dependency (Redis)
- Complexity overkill for current scale
- Requires state synchronization with database
- **Future consideration** if scale demands it

### 2. Event-Driven Architecture (Pub/Sub)
- Real-time notifications of sale start/end
- Decoupled components
- Significant complexity increase
- Requires message broker (RabbitMQ, Kafka)
- Overkill for current requirements
- **Production enhancement** for real-time updates

### 3. External Flash Sale Service
- Specialized functionality
- Offload complexity
- Additional cost
- Network dependency
- Less control
- Not suitable for educational project

---

## Implementation Details

### Flash Sale Manager Core Logic

```python
class FlashSaleManager:
    def is_flash_sale_active(self, product_id: int) -> bool:
        """Check if flash sale is currently active"""
        product = self.conn.execute(
            "SELECT sale_start, sale_end FROM product WHERE id = ?",
            (product_id,)
        ).fetchone()
        
        if not product or not product['sale_start'] or not product['sale_end']:
            return False
        
        now = datetime.now()
        start = datetime.fromisoformat(product['sale_start'])
        end = datetime.fromisoformat(product['sale_end'])
        
        return start <= now < end
```

### Pricing Logic

```python
def get_effective_price(self, product_id: int) -> int:
    """Get current effective price (flash or regular)"""
    product = self.conn.execute(
        "SELECT price_cents, flash_price_cents FROM product WHERE id = ?",
        (product_id,)
    ).fetchone()
    
    if not product:
        raise ValueError(f"Product {product_id} not found")
    
    # Return flash price if sale is active, otherwise regular price
    if self.is_flash_sale_active(product_id):
        return product['flash_price_cents']
    
    return product['price_cents']
```

**Key Implementation Features:**

1. **Automatic Time-Based Activation:** No manual intervention needed
2. **Centralized Logic:** All flash sale rules in one manager class
3. **Database-Driven:** Persistent state, survives app restarts
4. **Simple Queries:** Efficient SQL without complex joins

---

## Consequences

### Positive

**Automatic Activation/Deactivation:** Time windows eliminate need for manual intervention or cron jobs

**Simple Implementation:** No complex state machines or external dependencies

**Predictable Behavior:** Clear rules based on timestamps

**Easy Scheduling:** Can schedule flash sales weeks in advance

**Testable:** Easy to test by manipulating timestamps

**Maintainable:** Centralized logic in FlashSaleManager makes changes easy

**Scalable:** Database-backed approach works for moderate traffic

### Negative

⚠️ **Database Load:** Every product view requires timestamp comparison
- *Mitigation:* Caching flash products reduces database queries (see ADR-006)

⚠️ **Server Time Dependency:** Relies on accurate server clock
- *Mitigation:* Use NTP to ensure time accuracy in production

⚠️ **No Real-Time Notifications:** Users don't get instant notifications when sales start/end
- *Mitigation:* Client-side countdown timers provide visual feedback

⚠️ **Schema Changes Required:** Adding flash sale columns requires database migration
- *Mitigation:* Migration script handles this cleanly

### Neutral

🔹 **Not Suitable for Extreme Scale:** For millions of concurrent users, would need distributed caching or event-driven architecture

🔹 **Timezone Handling:** All timestamps in UTC; client-side conversion needed for local display

---

## User Interface Design

### Flash Sale Badges

Products in active flash sales display:
- ⚡ Lightning bolt icon indicating flash sale
- Original price with strikethrough
- Flash sale price prominently displayed
- Countdown timer showing time remaining
- "Limited Time" urgency messaging

**Implementation:** `src/templates/flash_sales/flash_products.html`

### Visual Hierarchy

```
┌─────────────────────────────┐
│  ⚡ FLASH SALE - 2h 15m left │
│                              │
│  Lightning Laptop Pro        │
│  $1,299.99  →  $999.99      │
│  Save $300 (23% off)         │
│                              │
│  [Add to Cart]               │
└─────────────────────────────┘
```

---

## Performance Optimization

Flash sales create predictable traffic spikes. Several tactics optimize performance:

1. **Caching** (see ADR-006): Cache active flash products
2. **Rate Limiting** (see ADR-004): Prevent checkout overload
3. **Database Indexing:** Index on `sale_start` and `sale_end` columns

---

## Future Enhancements

**Potential Improvements:**

1. **Event-Driven Architecture:** Publish sale start/end events for real-time notifications
2. **Redis Integration:** Cache flash sale state in Redis for extreme scale
3. **Historical Tracking:** Separate table for flash sale history and analytics
4. **A/B Testing:** Test different discount strategies
5. **Inventory Reservation:** Reserve items for time period during checkout
6. **Email/Push Notifications:** Alert users when sales start
7. **Dynamic Pricing:** Adjust flash prices based on demand

---

## Production Considerations

For production deployment:

1. **Time Synchronization:** Ensure all servers use NTP for accurate time
2. **Monitoring:** Alert on flash sale start/end events
3. **Load Testing:** Simulate traffic spikes before major flash sales
4. **Database Optimization:** Add indexes, consider read replicas
5. **CDN Integration:** Serve static flash sale assets from CDN
6. **Graceful Degradation:** Handle database failures gracefully

---

## Security Considerations

**Price Manipulation Prevention:**
- All price calculations done server-side
- Flash prices validated before checkout
- Transaction timestamps recorded for audit
- No client-side price overrides allowed

**Inventory Protection:**
- Database transactions prevent race conditions
- Stock checks happen atomically during checkout
- No overselling even under high concurrency

---

## Testing Strategy

Flash sale functionality validated through:

1. **Unit Tests:** FlashSaleManager logic (`test_flash_sale_manager.py`)
2. **Time-Based Tests:** Mock current time to test activation windows
3. **Integration Tests:** End-to-end checkout with flash pricing
4. **Manual Testing:** UI verification of badges, timers, pricing

**Test Coverage:** Comprehensive tests ensure:
- Active sales return flash price
- Expired sales return regular price
- Future sales return regular price
- Edge cases (null timestamps, etc.) handled

---

## Monitoring & Metrics

**Key Metrics to Track:**

- Number of active flash sales
- Flash sale conversion rate vs. regular products
- Average discount percentage
- Revenue per flash sale
- Traffic spikes during sales
- Checkout success rate during flash sales

**Logging:**
```python
logger.info(f"Flash sale started: product_id={product_id}, discount={discount_pct}%")
logger.info(f"Flash sale ended: product_id={product_id}, units_sold={units_sold}")
```

---

## Migration Strategy

To add flash sales to existing system:

1. **Database Migration:** Add columns with migration script
2. **Deploy Code:** Roll out FlashSaleManager and routes
3. **Test with One Product:** Start with single low-value item
4. **Monitor Performance:** Watch for issues before scaling
5. **Gradual Rollout:** Increase number of flash sale products over time

**Migration Script:** `db/migrate_flash_sales.py`

---

## References

- "Building Microservices" by Sam Newman (Event-Driven Architecture)
- E-commerce flash sale case studies from Amazon, Alibaba
- Database transaction isolation levels for concurrent access
- Time synchronization best practices (NTP)

---

## Related ADRs

- **ADR-004:** Rate Limiting Strategy (protects flash sale endpoints)
- **ADR-006:** Caching Strategy (optimizes flash product queries)
- **ADR-003:** Circuit Breaker Pattern (payment resilience during sales)

---

## Appendix: Database Schema

```sql
-- Flash sale columns in product table
ALTER TABLE product ADD COLUMN flash_price_cents INTEGER;
ALTER TABLE product ADD COLUMN sale_start TIMESTAMP;
ALTER TABLE product ADD COLUMN sale_end TIMESTAMP;

-- Optional: Event log table for analytics
CREATE TABLE flash_sales_log (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    details TEXT,
    FOREIGN KEY (product_id) REFERENCES product(id)
);

-- Indexes for performance
CREATE INDEX idx_product_sale_times ON product(sale_start, sale_end);
```

---

**Document Status:** Final  
**Last Updated:** October 21, 2025  
**Approved By:** Flash Sales Team