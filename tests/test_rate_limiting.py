from src.partners import security


def setup_function(fn):
    # clear limiter state between tests
    security._limits.clear()


def test_rate_limiter_allows_until_limit():
    api_key = "rl-test-key"
    # allow 3 calls
    for i in range(3):
        assert security.check_rate_limit(api_key, max_per_minute=3) is True
    # next call should be rejected
    assert security.check_rate_limit(api_key, max_per_minute=3) is False
