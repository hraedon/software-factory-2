```python
import clock
import pytest

from interface import RateLimiter, RateLimitExceeded


def test_construction():
    """AC-01: Construction creates a RateLimiter instance."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    assert isinstance(limiter, RateLimiter)


def test_construction_zero_capacity():
    """AC-01: Construction with capacity zero creates an empty bucket."""
    limiter = RateLimiter(capacity=0, refill_per_second=1.0)
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key1", 1)


def test_independent_buckets_per_key():
    """AC-01: Different keys have independent token buckets."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    limiter.consume("key1", 5)
    result = limiter.consume("key2", 1)
    assert result is True


def test_consume_success_returns_true():
    """AC-02: Consume with sufficient tokens returns True."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    result = limiter.consume("key1", 5)
    assert result is True


def test_consume_allows_empty_key():
    """AC-02: Consume accepts an empty string key."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    result = limiter.consume("", 1)
    assert result is True


def test_consume_zero_tokens_succeeds():
    """AC-02: Consuming zero tokens succeeds without reducing capacity."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    limiter.consume("key1", 0)
    result = limiter.consume("key1", 5)
    assert result is True


def test_consume_failure_returns_false():
    """AC-03: Consume with insufficient but non-empty bucket returns False."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    limiter.consume("key1", 3)
    result = limiter.consume("key1", 3)
    assert result is False


def test_consume_empty_bucket_raises():
    """AC-04: Consume when bucket is empty raises RateLimitExceeded."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    limiter.consume("key1", 5)
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key1", 1)


def test_refill_calculation(monkeypatch):
    """AC-05: Tokens refill at refill_per_second up to capacity."""
    current_ns = [0]

    def mock_monotonic_ns():
        return current_ns[0]

    monkeypatch.setattr(clock, "monotonic_ns", mock_monotonic_ns)
    limiter = RateLimiter(capacity=10, refill_per_second=2.0)
    limiter.consume("key1", 8)
    current_ns[0] += 1_000_000_000
    result = limiter.consume("key1", 3)
    assert result is True
    current_ns[0] += 500_000_000
    result = limiter.consume("key1", 1)
    assert result is True


def test_uses_clock_source(monkeypatch):
    """AC-06: Implementation uses the clock module for time."""
    called = [False]

    def mock_monotonic_ns():
        called[0] = True
        return 0

    monkeypatch.setattr(clock, "monotonic_ns", mock_monotonic_ns)
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    limiter.consume("key1", 1)
    assert called[0]


def test_eviction_after_inactivity(monkeypatch):
    """AC-07: Keys untouched for over one hour may be evicted."""
    current_ns = [0]

    def mock_monotonic_ns():
        return current_ns[0]

    monkeypatch.setattr(clock, "monotonic_ns", mock_monotonic_ns)
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    limiter.consume("key1", 5)
    current_ns[0] += 3601 * 1_000_000_000
    result = limiter.consume("key1", 5)
    assert result is True
```
