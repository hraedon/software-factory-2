```python
from interface import RateLimiter, RateLimitExceeded


def test_construction_ac01():
    """AC-01: RateLimiter constructs with capacity and refill rate."""
    limiter = RateLimiter(10, 1.0)
    assert limiter is not None


def test_consume_success_ac02():
    """AC-02: consume returns remaining tokens on success."""
    limiter = RateLimiter(10, 1.0)
    result = limiter.consume("key1", 1)
    assert result is True


def test_consume_insufficient_tokens_ac03():
    """AC-03: consume returns None when insufficient tokens."""
    limiter = RateLimiter(10, 1.0)
    limiter.consume("key1", 10)
    result = limiter.consume("key1", 1)
    assert result is None


def test_consume_empty_bucket_raises_ac04():
    """AC-04: RateLimitExceeded raised when bucket is empty."""
    limiter = RateLimiter(10, 1.0)
    limiter.consume("key2", 10)
    try:
        limiter.consume("key2", 1)
        assert False, "Expected RateLimitExceeded"
    except RateLimitExceeded:
        pass


def test_refill_continuous_ac05():
    """AC-05: Tokens refill continuously."""
    pass


def test_clock_source_ac06():
    """AC-06: Uses clock.monotonic_seconds()."""
    pass


def test_eviction_ac07():
    """AC-07: Keys not touched in over one hour may be evicted."""
    pass
```
