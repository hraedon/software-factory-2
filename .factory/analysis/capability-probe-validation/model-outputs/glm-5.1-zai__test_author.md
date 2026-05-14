Looking at the locked interface and the spec, I need to map the spec's return type descriptions to the interface's `bool` return type, and work around the lack of clock injection for time-based tests.
The interface has no `ErrorCode` enum, so that checklist item is vacuously satisfied. Now let me verify the spec section details and produce the test file.

```python
import time

import pytest

from interface import RateLimiter, RateLimitExceeded


def test_construction_creates_limiter():
    """AC-01: RateLimiter constructs with positive capacity and refill rate."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    assert limiter is not None


def test_construction_zero_refill():
    """AC-01: RateLimiter constructs with zero refill rate."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    assert limiter is not None


def test_construction_zero_capacity():
    """AC-01: RateLimiter constructs with zero capacity."""
    limiter = RateLimiter(capacity=0, refill_per_second=1.0)
    assert limiter is not None


def test_consume_success_returns_true():
    """AC-02: consume returns True when sufficient tokens available."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    result = limiter.consume("key-a", 5)
    assert result is True


def test_consume_exact_capacity():
    """AC-02: consume succeeds when requesting all tokens in bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    result = limiter.consume("key-a", 10)
    assert result is True


def test_consume_single_token():
    """AC-02: consume succeeds for a single token from full bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    result = limiter.consume("key-a", 1)
    assert result is True


def test_sequential_consumes_deduct_tokens():
    """AC-02: sequential consumes deduct tokens from the same bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    assert limiter.consume("key-a", 3) is True
    assert limiter.consume("key-a", 3) is True
    assert limiter.consume("key-a", 3) is True
    assert limiter.consume("key-a", 2) is False


def test_consume_insufficient_returns_false():
    """AC-03: consume returns False when fewer tokens than requested."""
    limiter = RateLimiter(capacity=3, refill_per_second=0.0)
    result = limiter.consume("key-a", 5)
    assert result is False


def test_consume_insufficient_does_not_modify():
    """AC-03: failed consume does not deduct tokens from the bucket."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    limiter.consume("key-a", 10)
    result = limiter.consume("key-a", 5)
    assert result is True


def test_consume_empty_bucket_raises():
    """AC-04: consume raises RateLimitExceeded when bucket is empty."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    limiter.consume("key-a", 5)
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key-a", 1)


def test_zero_capacity_raises_on_consume():
    """AC-04: zero-capacity limiter raises RateLimitExceeded immediately."""
    limiter = RateLimiter(capacity=0, refill_per_second=1.0)
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key-a", 1)


def test_rate_limit_exceeded_is_exception():
    """AC-04: RateLimitExceeded is an Exception subclass."""
    assert issubclass(RateLimitExceeded, Exception)


def test_refill_restores_tokens():
    """AC-05: tokens refill at refill_per_second rate over elapsed time."""
    limiter = RateLimiter(capacity=10, refill_per_second=20.0)
    limiter.consume("key-a", 10)
    time.sleep(0.5)
    result = limiter.consume("key-a", 5)
    assert result is True


def test_refill_capped_at_capacity():
    """AC-05: refilled tokens do not exceed capacity."""
    limiter = RateLimiter(capacity=10, refill_per_second=1000.0)
    limiter.consume("key-a", 5)
    time.sleep(0.1)
    result = limiter.consume("key-a", 10)
    assert result is True
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key-a", 1)


def test_no_refill_without_elapsed_time():
    """AC-06: no token refill when no time has elapsed between calls."""
    limiter = RateLimiter(capacity=10, refill_per_second=1000.0)
    limiter.consume("key-a", 7)
    result = limiter.consume("key-a", 4)
    assert result is False


def test_keys_are_independent():
    """AC-07: each key maintains independent bucket state."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    limiter.consume("key-a", 5)
    result = limiter.consume("key-b", 5)
    assert result is True
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key-a", 1)


def test_empty_string_key():
    """AC-07: empty string is a valid key."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    result = limiter.consume("", 5)
    assert result is True
    with pytest.raises(RateLimitExceeded):
        limiter.consume("", 1)
```
