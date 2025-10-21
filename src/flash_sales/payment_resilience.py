from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from .retry import retry
from typing import Tuple

_payment_attempt_counter = 0

# Mock payment service - in real app, this would call external API
class MockPaymentService:
    """Mock external payment service that can fail"""
    
    def __init__(self, failure_rate: float = 0.0):
        self.failure_rate = failure_rate
        self.call_count = 0
    
    def process_payment(self, method: str, amount_cents: int) -> Tuple[str, str]:
        """Simulate payment processing"""
        import random
        
        self.call_count += 1
        
        # Simulate random failures based on failure rate
        if random.random() < self.failure_rate:
            raise Exception("Payment service temporarily unavailable")
        
        # Simulate successful payment
        if amount_cents <= 0:
            return ("DECLINED", None)
        
        ref = f"PAY-{self.call_count:06d}"
        return ("APPROVED", ref)


# Global circuit breaker for payment service
payment_circuit_breaker = CircuitBreaker(
    failure_threshold=3,
    timeout_seconds=30,
    success_threshold=2
)


# @retry(max_attempts=3, delay_seconds=0.5, exceptions=(Exception,)) //test2
# def process_payment_with_retry(method: str, amount_cents: int) -> Tuple[str, str]:
#     """Payment processing with retry logic"""
#     # Force ALL attempts to fail
#     print(f"💥 Payment FAILED (forcing circuit breaker to open)")
#     raise Exception("Payment service is DOWN")

@retry(max_attempts=3, delay_seconds=0.5, exceptions=(Exception,))
def process_payment_with_retry(method: str, amount_cents: int) -> Tuple[str, str]:
    """Payment processing with retry logic"""
    # This wraps your existing payment.process function
    from ..payment import process as payment_process
    
    try:
        return payment_process(method, amount_cents)
    except Exception as e:
        # If your payment module raises exceptions, they'll be caught and retried
        print(f"Payment attempt failed: {e}")
        raise

# @retry(max_attempts=3, delay_seconds=0.5, exceptions=(Exception,)) //Test 1
# def process_payment_with_retry(method: str, amount_cents: int) -> Tuple[str, str]:
#     """Payment processing with retry logic"""
#     global _payment_attempt_counter
#     _payment_attempt_counter += 1
    
#     # Force failure on first 2 attempts
#     if _payment_attempt_counter <= 2:
#         print(f"Payment attempt {_payment_attempt_counter} FAILED (simulated)")
#         raise Exception("Payment service temporarily unavailable")
    
#     print(f"Payment attempt {_payment_attempt_counter} SUCCEEDED")
    
#     from ..payment import process as payment_process
#     return payment_process(method, amount_cents)


def process_payment_resilient(method: str, amount_cents: int) -> Tuple[str, str]:
    """
    Payment processing with both circuit breaker and retry
    This is the main entry point for flash sale checkouts
    """
    try:
        return payment_circuit_breaker.call(
            process_payment_with_retry,
            method,
            amount_cents
        )
    except CircuitBreakerOpenError:
        # Circuit is open, return immediate decline
        return ("DECLINED", "SERVICE_UNAVAILABLE")
    except Exception as e:
        # All retries failed
        print(f"Payment failed after retries: {e}")
        return ("DECLINED", f"ERROR: {str(e)}")