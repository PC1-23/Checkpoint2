````markdown
# ADR-0015: Rate Limiting Strategy for Flash Sale Protection

**Status:** Accepted

**Date:** 2025-10-21

**Decision Makers:** Flash Sales Team

---

## Context

Flash sales create sudden traffic spikes that can overwhelm our system. During peak moments:

- Thousands of users access product listings simultaneously
- Hundreds attempt checkout concurrently
- Malicious actors may attempt to overwhelm the system (DoS attacks)
- Bots may attempt to purchase all inventory instantly

Without traffic control, these spikes can:
- Degrade response times for all users
- Cause database connection exhaustion
- Crash the application server
- Create unfair advantage for automated scripts over human users

We need a mechanism to protect system resources while maintaining fair access during flash sales.

---

## Decision

We will implement **Rate Limiting** using a **Sliding Window Algorithm** with the following configuration:

**Checkout Endpoint:**
- Maximum: 5 requests per user per 60-second window
- Identifier: Client IP address
- Response: HTTP 429 (Too Many Requests) with clear error message

**Implementation:**
- In-memory sliding window with timestamp tracking
- Thread-safe using locks for concurrent access
- Per-IP tracking to isolate users
- Automatic window expiration and cleanup

**Location:** `src/flash_sales/rate_limiter.py`

---

## Rationale

### Why Rate Limiting?

**System Protection:**
- Prevents resource exhaustion during traffic spikes
- Maintains consistent response times under load
- Protects database from excessive queries

**Fair Access:**
- Prevents bots from monopolizing limited inventory
- Gives human users fair chance to complete purchases
- Limits damage from malicious traffic

**Graceful Degradation:**
- System remains functional even when overloaded
- Clear feedback to users about rate limits
- Better than complete system failure

### Algorithm Choice: Sliding Window

We chose **Sliding Window** over alternatives:

**Sliding Window (Chosen)**
- Accurate rate limiting (no boundary issues)
- Smooth traffic distribution
- Memory-efficient for our scale

**Fixed Window**
- Burst problem at window boundaries
- Less accurate rate limiting
- Simpler but lower quality

**Token Bucket**
- Allows bursts (not ideal for flash sales)
- More complex implementation
- Better for APIs, not UI checkout

**Leaky Bucket**
- Constant rate (too restrictive for UI)
- Queuing adds latency
- Overkill for our needs

---

## Configuration Rationale

### Why 5 Requests Per 60 Seconds?

**Checkout Flow Analysis:**
1. Initial checkout attempt: 1 request
2. Payment retry (if needed): 1-2 requests
3. User correction (wrong card, etc.): 1-2 requests
4. Total legitimate use: 3-4 requests in quick succession

**Safety Margin:** 5 requests allows legitimate retries while blocking abuse

**Window Duration:** 60 seconds prevents rapid exhaustion but resets quickly enough for legitimate multi-purchase users

**Why IP-Based Tracking?**

... (rest unchanged) ...

---

## Related ADRs

- **ADR-0014:** Circuit Breaker Pattern (complementary availability tactic)
- **ADR-0016:** Flash Sale Implementation (context for rate limiting need)
- **ADR-0017:** Caching Strategy (performance optimization that benefits from rate limiting)
````
