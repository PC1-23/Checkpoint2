from functools import wraps
from flask import request, jsonify
from datetime import datetime, timedelta
from collections import defaultdict
from threading import Lock


class RateLimiter:
    """Simple in-memory rate limiter for flash sale endpoints"""
    
    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(list)
        self.lock = Lock()
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if request from identifier is allowed"""
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Clean old requests
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > cutoff
            ]
            
            # Check if under limit
            if len(self.requests[identifier]) >= self.max_requests:
                return False
            
            # Add new request
            self.requests[identifier].append(now)
            return True
    
    def reset(self, identifier: str):
        """Reset rate limit for an identifier"""
        with self.lock:
            if identifier in self.requests:
                del self.requests[identifier]


# Global rate limiter instance
checkout_rate_limiter = RateLimiter(max_requests=5, window_seconds=60)


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """Decorator to apply rate limiting to routes"""
    limiter = RateLimiter(max_requests, window_seconds)
    
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Use IP address as identifier
            identifier = request.remote_addr
            
            if not limiter.is_allowed(identifier):
                return jsonify({
                    "error": "Rate limit exceeded. Please try again later."
                }), 429
            
            return f(*args, **kwargs)
        return wrapped
    return decorator