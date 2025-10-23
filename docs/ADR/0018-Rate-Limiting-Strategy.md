# ADR-0018: Rate Limiting Strategy for Flash Sale Protection

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

### Why IP-Based Tracking?

**Pros:**
No authentication required (works for anonymous users)
Simple to implement and debug
Effective against simple bot attacks
No additional database lookups

**Cons:**
⚠️ Shared IPs (NAT, corporate networks) may affect multiple users
⚠️ Sophisticated attackers can rotate IPs

**Mitigation for Cons:**
- Generous per-IP limits (5 requests) accommodate shared IPs
- Future enhancement: session-based tracking for authenticated users

---

## Alternatives Considered

### 1. No Rate Limiting
- System vulnerable to DoS attacks
- Poor performance during spikes
- Unfair advantage to bots
- Unacceptable for flash sales

### 2. Session-Based Rate Limiting
- More accurate per-user tracking
- Requires user authentication
- Can't protect anonymous browsing
- More complex implementation
- **Future enhancement** for authenticated endpoints

### 3. Third-Party Service (Cloudflare, AWS WAF)
- More sophisticated protection
- Handles DDoS at network level
- Additional cost
- External dependency
- Overkill for current project scope
- **Production consideration** for real deployment

### 4. Database-Based Rate Limiting
- Persistent across app restarts
- Can share across multiple instances
- Adds database load (defeats purpose)
- Higher latency
- More complex

---

## Consequences

### Positive

**System Stability:** Prevents resource exhaustion during flash sales

**Predictable Performance:** Response times remain consistent under load

**Fair Access:** Legitimate users have equal opportunity to purchase

**DoS Protection:** Basic defense against traffic-based attacks

**Clear User Feedback:** Users understand why they're rate-limited

**Simple Implementation:** Easy to understand, test, and maintain

**No External Dependencies:** Self-contained solution

### Negative

⚠️ **Shared IP Impact:** Corporate networks or NAT may affect multiple users
- *Mitigation:* Generous limits (5 per minute) accommodate shared IPs

⚠️ **Memory Usage:** Stores timestamps for each IP
- *Mitigation:* Automatic cleanup of expired entries

⚠️ **Not Distributed:** Single-instance tracking (doesn't work across multiple servers)
- *Mitigation:* Acceptable for current monolithic deployment
- *Future:* Redis-backed rate limiting for distributed systems

⚠️ **Sophisticated Bypass:** IP rotation can evade rate limits
- *Mitigation:* Additional security layers (CAPTCHA, account verification) for production

### Neutral

🔹 **Configuration Required:** Limits must be tuned based on actual traffic patterns

🔹 **Monitoring Needed:** Must track rate limit hits to detect attacks

---

## Implementation Details

```python
class RateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)  # ip -> [timestamps]
        self.lock = Lock()  # Thread safety
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed"""
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Remove old timestamps
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > cutoff
            ]
            
            # Check limit
            if len(self.requests[identifier]) >= self.max_requests:
                return False
            
            # Record request
            self.requests[identifier].append(now)
            return True
```

**Key Design Decisions:**

1. **Thread-Safe:** Uses locks for concurrent request handling
2. **Automatic Cleanup:** Removes expired timestamps during checks
3. **Graceful Failure:** Returns HTTP 429 with clear message
4. **Configurable:** Easy to adjust limits per endpoint

---

## Usage Example

```python
from flask import request, jsonify
from src.flash_sales.rate_limiter import checkout_rate_limiter

@app.post("/flash/checkout")
def flash_checkout():
    if not checkout_rate_limiter.is_allowed(request.remote_addr):
        return jsonify({
            "error": "Rate limit exceeded. Please try again in a moment."
        }), 429
    
    # Process checkout...
```

---

## Monitoring & Alerts

**Metrics to Track:**
- Number of rate-limited requests per minute
- Top rate-limited IP addresses
- Ratio of rate-limited to successful requests
- Average requests per user

**Alert Thresholds:**
- >10% of requests rate-limited → possible attack
- Single IP with >50 rate-limited requests → investigate
- Sudden spike in unique IPs → DDoS attempt

---

## Testing Strategy

Rate limiter validation includes:

1. **Unit Tests:** Verify limit enforcement and window expiration
2. **Concurrent Tests:** Ensure thread safety under load
3. **Integration Tests:** Validate decorator application to routes
4. **Manual Testing:** Browser-based rapid clicking

**Test Coverage:** `tests/flash_sales/test_rate_limiter.py`

---

## Future Enhancements

**Potential Improvements:**

1. **Distributed Rate Limiting:** Redis-backed for multi-instance deployments
2. **Adaptive Limits:** Adjust based on current system load
3. **User-Based Tracking:** Session-based limits for authenticated users
4. **Tiered Limits:** Different limits for different user types (guest vs. authenticated)
5. **CAPTCHA Integration:** Challenge suspicious traffic patterns
6. **Geographic Rate Limiting:** Different limits based on region
7. **Metrics Export:** Expose rate limit metrics to monitoring systems

---

## Production Considerations

For production deployment, consider:

1. **Distributed Storage:** Move to Redis for multi-instance deployments
2. **WAF Integration:** Add Cloudflare or AWS WAF for network-level protection
3. **Bot Detection:** Integrate specialized bot detection services
4. **Logging:** Comprehensive logging of rate-limited requests for security analysis
5. **A/B Testing:** Experiment with different limits to find optimal values

---

## References

- OWASP Rate Limiting Best Practices
- "Designing Data-Intensive Applications" by Martin Kleppmann (Chapter on Rate Limiting)
- Redis Rate Limiting Patterns
- Kong API Gateway rate limiting strategies

---

## Related ADRs

- **ADR-003:** Circuit Breaker Pattern (complementary availability tactic)
- **ADR-005:** Flash Sale Implementation (context for rate limiting need)
- **ADR-006:** Caching Strategy (performance optimization that benefits from rate limiting)

---

**Document Status:** Final  
**Last Updated:** October 21, 2025  
**Approved By:** Flash Sales Team