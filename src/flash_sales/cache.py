from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from threading import Lock


class SimpleCache:
    """Simple in-memory cache for flash sale products"""
    
    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl  # seconds
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self.lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if datetime.now() < expiry:
                    return value
                else:
                    # Remove expired entry
                    del self.cache[key]
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with TTL"""
        with self.lock:
            ttl = ttl or self.default_ttl
            expiry = datetime.now() + timedelta(seconds=ttl)
            self.cache[key] = (value, expiry)
    
    def delete(self, key: str):
        """Delete key from cache"""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
    
    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            self.cache.clear()


# Global cache instance
flash_sale_cache = SimpleCache(default_ttl=30)