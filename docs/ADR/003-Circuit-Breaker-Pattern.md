# ADR-003: Circuit Breaker Pattern for Payment Service Resilience

**Status:** Accepted

**Date:** 2025-10-21

**Decision Makers:** Flash Sales Team

---

## Context

During flash sales, our system processes high volumes of payment transactions through an external payment service. External services can experience temporary outages, slowdowns, or intermittent failures. Without protection, these failures can:

- Cascade through our system causing widespread failures
- Waste resources retrying unavailable services indefinitely
- Degrade user experience with long timeouts
- Overwhelm the failing service, preventing recovery

We need a mechanism to detect service failures quickly, stop sending requests to failing services, and automatically recover when services become available again.

---

## Decision

We will implement the **Circuit Breaker Pattern** to wrap calls to the external payment service with three states:

1. **Closed (Normal):** Requests pass through normally; failures are counted
2. **Open (Failing):** Requests fail immediately without calling the service
3. **Half-Open (Testing):** Limited requests test if service has recovered

**Configuration:**
- Failure threshold: 3 consecutive failures trigger circuit opening
- Timeout: 30 seconds before attempting recovery (half-open state)
- Success threshold: 2 consecutive successes in half-open state close the circuit

**Implementation:** `src/flash_sales/circuit_breaker.py`

---

## Rationale

### Why Circuit Breaker?

**Prevents Cascade Failures:**
- Isolates failing external services from bringing down our entire system
- Fails fast instead of waiting for timeouts

**Resource Protection:**
- Stops wasting threads/connections on requests that will fail
- Allows system resources to serve successful requests

**Automatic Recovery:**
- Periodically tests if failed service has recovered
- No manual intervention required

**Observable Failure State:**
- Clear state transitions (Closed → Open → Half-Open → Closed)
- Easy to monitor and debug

### Alternatives Considered

**1. Simple Retry Without Circuit Breaker**
- Would continue hammering failing service
- Worsens the failure condition
- No automatic fail-fast behavior

**2. Manual Service Degradation**
- Requires human intervention
- Slow response to failures
- Not suitable for flash sale time-sensitivity

**3. Service Mesh (Istio, Linkerd)**
- Too complex for current project scale
- Significant operational overhead
- Good for microservices, but overkill for monolith

---

## Consequences

### Positive

 **Improved Availability:** System remains responsive even when payment service fails

 **Better User Experience:** Fast failures (immediate error) instead of hanging timeouts

 **Service Protection:** Prevents overwhelming already-failing services

**Observable:** Clear state transitions make debugging easier

**Automatic Recovery:** No manual intervention required

**Testable:** Easy to simulate failures and verify behavior

### Negative

⚠️ **Potential False Positives:** Short-lived glitches might open circuit unnecessarily
- *Mitigation:* Tuned thresholds (3 failures) to avoid hair-trigger opening

⚠️ **State Management Complexity:** Must track state across requests
- *Mitigation:* Simple state machine with clear transitions

⚠️ **Memory Overhead:** Stores failure counts and timestamps
- *Mitigation:* Minimal overhead (a few integers per breaker)

### Neutral

🔹 **Not a Silver Bullet:** Circuit breaker doesn't fix the underlying service failure, just protects from it

🔹 **Configuration Required:** Thresholds must be tuned for specific services

---

## Implementation Notes

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=3, timeout_seconds=30, success_threshold=2):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
```

**Key Design Decisions:**

1. **Thread-Safe:** Uses locks to handle concurrent requests safely
2. **Configurable Thresholds:** Can tune for different services
3. **Manual Reset:** Allows operators to manually close circuit if needed
4. **Exception-Based:** Raises `CircuitBreakerOpenError` when open

---

## Monitoring & Metrics

To effectively use the circuit breaker, monitor:

- Circuit state transitions (Closed → Open → Half-Open → Closed)
- Number of calls rejected while open
- Time spent in each state
- Success/failure rates in half-open state

**Logging:**
```python
logger.info(f"Circuit breaker opened after {self.failure_count} failures")
logger.info(f"Circuit breaker entering half-open state")
logger.info(f"Circuit breaker closed after successful recovery")
```

---

## Testing Strategy

Circuit breaker behavior is validated through:

1. **Unit Tests:** Verify state transitions and thresholds
2. **Failure Injection:** Simulate payment service failures
3. **Timeout Testing:** Verify half-open state timing
4. **Concurrent Testing:** Ensure thread safety

**Test Coverage:** `tests/flash_sales/test_circuit_breaker.py`

---

## Future Considerations

**Potential Enhancements:**

1. **Distributed Circuit Breaker:** Share state across multiple instances (Redis-backed)
2. **Per-User Circuit Breakers:** Different breakers for different payment methods
3. **Metrics Export:** Expose circuit breaker metrics to Prometheus/Grafana
4. **Adaptive Thresholds:** Adjust thresholds based on historical failure rates
5. **Health Check Endpoint:** API to query circuit breaker status

---

## References

- Michael T. Nygard, "Release It! Design and Deploy Production-Ready Software"
- Martin Fowler, "Circuit Breaker" pattern documentation
- Netflix Hystrix circuit breaker implementation (inspiration)

---

## Related ADRs

- **ADR-004:** Rate Limiting Strategy (complementary availability tactic)
- **ADR-005:** Flash Sale Implementation (context for why resilience matters)