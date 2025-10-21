import pytest
import time
from src.flash_sales.rate_limiter import RateLimiter


def test_rate_limiter_allows_requests_under_limit():
    """Test that requests under limit are allowed"""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    
    assert limiter.is_allowed("user1") == True
    assert limiter.is_allowed("user1") == True
    assert limiter.is_allowed("user1") == True


def test_rate_limiter_blocks_requests_over_limit():
    """Test that requests over limit are blocked"""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    
    # Use up the limit
    limiter.is_allowed("user1")
    limiter.is_allowed("user1")
    limiter.is_allowed("user1")
    
    # This should be blocked
    assert limiter.is_allowed("user1") == False


def test_rate_limiter_different_users():
    """Test that different users have separate limits"""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    
    assert limiter.is_allowed("user1") == True
    assert limiter.is_allowed("user1") == True
    assert limiter.is_allowed("user1") == False  # user1 blocked
    
    # user2 should still be allowed
    assert limiter.is_allowed("user2") == True
    assert limiter.is_allowed("user2") == True


def test_rate_limiter_window_reset():
    """Test that window resets after time"""
    limiter = RateLimiter(max_requests=2, window_seconds=1)
    
    # Use up limit
    assert limiter.is_allowed("user1") == True
    assert limiter.is_allowed("user1") == True
    assert limiter.is_allowed("user1") == False
    
    # Wait for window to expire
    time.sleep(1.1)
    
    # Should be allowed again
    assert limiter.is_allowed("user1") == True


def test_rate_limiter_reset():
    """Test manual reset"""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    
    limiter.is_allowed("user1")
    limiter.is_allowed("user1")
    assert limiter.is_allowed("user1") == False
    
    # Reset
    limiter.reset("user1")
    
    # Should be allowed again
    assert limiter.is_allowed("user1") == True