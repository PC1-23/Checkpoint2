from functools import wraps
from typing import Callable, Tuple, Type
import time


def retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Retry decorator with exponential backoff
    
    Args:
        max_attempts: Maximum number of attempts
        delay_seconds: Initial delay between retries
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            current_delay = delay_seconds
            
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        # Last attempt failed, re-raise
                        raise e
                    
                    # Log retry attempt (in production, use proper logging)
                    print(f"Attempt {attempt} failed: {str(e)}. Retrying in {current_delay}s...")
                    
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
                    attempt += 1
            
        return wrapper
    return decorator