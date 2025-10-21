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

```
# NOTE: Superseded

This ADR was superseded by `ADR-0016` (Flash Sale Implementation Strategy).

Please see `docs/ADR/0016-flash-sale-implementation.md` for the canonical,
persistently-numbered ADR content.

---

Status: Superseded

Superseded-by: ADR-0016

Date superseded: 2025-10-21

Rationale: Consolidated ADR numbering and canonical location

---

For historical context, the original content has been preserved in
repository history. The canonical active ADR is:

- `docs/ADR/0016-flash-sale-implementation.md`

```

# --- Original ADR (archived below) ---

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
