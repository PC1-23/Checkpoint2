import pytest
import time
from src.flash_sales.circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState


def failing_function():
    """Function that always fails"""
    raise Exception("Service unavailable")


def succeeding_function():
    """Function that always succeeds"""
    return "success"


def test_circuit_breaker_closed_state():
    """Test circuit breaker in closed state"""
    breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
    
    result = breaker.call(succeeding_function)
    assert result == "success"
    assert breaker.get_state() == CircuitState.CLOSED


def test_circuit_breaker_opens_after_failures():
    """Test circuit breaker opens after threshold failures"""
    breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=60)
    
    # Trigger failures
    for _ in range(3):
        with pytest.raises(Exception):
            breaker.call(failing_function)
    
    # Circuit should be open now
    assert breaker.get_state() == CircuitState.OPEN


def test_circuit_breaker_rejects_when_open():
    """Test circuit breaker rejects calls when open"""
    breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_function)
    
    # Should raise CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        breaker.call(succeeding_function)


def test_circuit_breaker_half_open_after_timeout():
    """Test circuit breaker goes to half-open after timeout"""
    breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1)
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_function)
    
    assert breaker.get_state() == CircuitState.OPEN
    
    # Wait for timeout
    time.sleep(1.1)
    
    # Next call should be allowed (half-open)
    result = breaker.call(succeeding_function)
    assert result == "success"


def test_circuit_breaker_closes_after_success_in_half_open():
    """Test circuit closes after successes in half-open"""
    breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=1, success_threshold=2)
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_function)
    
    # Wait for timeout
    time.sleep(1.1)
    
    # Succeed twice to close circuit
    breaker.call(succeeding_function)
    breaker.call(succeeding_function)
    
    assert breaker.get_state() == CircuitState.CLOSED


def test_circuit_breaker_reset():
    """Test manual circuit breaker reset"""
    breaker = CircuitBreaker(failure_threshold=2, timeout_seconds=60)
    
    # Open the circuit
    for _ in range(2):
        with pytest.raises(Exception):
            breaker.call(failing_function)
    
    assert breaker.get_state() == CircuitState.OPEN
    
    # Manual reset
    breaker.reset()
    
    assert breaker.get_state() == CircuitState.CLOSED
    result = breaker.call(succeeding_function)
    assert result == "success"