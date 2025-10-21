import pytest
from src.flash_sales.retry import retry


class FailCounter:
    """Helper to track failures"""
    def __init__(self, fail_times=2):
        self.fail_times = fail_times
        self.attempts = 0
    
    def flaky_function(self):
        """Fails first N times, then succeeds"""
        self.attempts += 1
        if self.attempts <= self.fail_times:
            raise Exception(f"Failure {self.attempts}")
        return "success"


def test_retry_succeeds_eventually():
    """Test retry eventually succeeds"""
    counter = FailCounter(fail_times=2)
    
    @retry(max_attempts=5, delay_seconds=0.01)
    def test_func():
        return counter.flaky_function()
    
    result = test_func()
    assert result == "success"
    assert counter.attempts == 3  # Failed 2 times, succeeded on 3rd


def test_retry_fails_after_max_attempts():
    """Test retry gives up after max attempts"""
    counter = FailCounter(fail_times=10)  # Will never succeed
    
    @retry(max_attempts=3, delay_seconds=0.01)
    def test_func():
        return counter.flaky_function()
    
    with pytest.raises(Exception):
        test_func()
    
    assert counter.attempts == 3  # Tried 3 times


def test_retry_with_specific_exception():
    """Test retry only catches specific exceptions"""
    counter = FailCounter(fail_times=1)
    
    @retry(max_attempts=3, delay_seconds=0.01, exceptions=(ValueError,))
    def test_func():
        counter.attempts += 1
        raise RuntimeError("Different error")
    
    # Should not retry RuntimeError
    with pytest.raises(RuntimeError):
        test_func()
    
    assert counter.attempts == 1  # Only tried once


def test_retry_immediate_success():
    """Test function that succeeds immediately"""
    counter = FailCounter(fail_times=0)
    
    @retry(max_attempts=3, delay_seconds=0.01)
    def test_func():
        return counter.flaky_function()
    
    result = test_func()
    assert result == "success"
    assert counter.attempts == 1  # Only needed one attempt