```python
import time

import pytest

from interface import RateLimitExceeded, RateLimiter


def test_construction_valid_params():
    """AC-01: RateLimiter constructs with valid capacity and refill rate."""
    limiter = RateLimiter(capacity=100, refill_per_second=10.0)
    assert limiter is not None


def test_construction_negative_capacity():
    """AC-01: negative capacity should be rejected with ValueError."""
    with pytest.raises(ValueError):
        RateLimiter(capacity=-1, refill_per_second=1.0)


def test_construction_zero_capacity():
    """AC-01: zero capacity is valid and bucket starts empty."""
    limiter = RateLimiter(capacity=0, refill_per_second=1.0)
    assert limiter is not None
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key", 1)


def test_construction_negative_refill_rate():
    """AC-01: negative refill rate should be rejected with ValueError."""
    with pytest.raises(ValueError):
        RateLimiter(capacity=10, refill_per_second=-0.1)


def test_construction_zero_refill_rate():
    """AC-01: zero refill rate is valid, no tokens refill."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    assert limiter is not None
    limiter.consume("key", 5)
    assert limiter.consume("key", 6) is False


def test_consume_success():
    """AC-02: consume returns True when sufficient tokens available."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    assert limiter.consume("key1", 5) is True


def test_consume_exactly_capacity():
    """AC-02: consume all tokens in bucket returns True."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    assert limiter.consume("key1", 10) is True


def test_consume_single_token():
    """AC-02: consume one token returns True."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    assert limiter.consume("key1", 1) is True


def test_consume_multiple_keys_independent():
    """AC-02: each key has an independent token bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    limiter.consume("key_a", 8)
    assert limiter.consume("key_b", 10) is True
    assert limiter.consume("key_a", 2) is True


def test_consume_zero_tokens():
    """AC-02: consuming zero tokens returns True without side effects."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    assert limiter.consume("key1", 0) is True
    assert limiter.consume("key1", 10) is True


def test_consume_insufficient_tokens():
    """AC-03: consume returns False when fewer tokens available than requested."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    limiter.consume("key1", 6)
    assert limiter.consume("key1", 5) is False


def test_consume_insufficient_tokens_bucket_unchanged():
    """AC-03: failed consume does not deduct tokens from the bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    limiter.consume("key1", 4)
    limiter.consume("key1", 5)
    assert limiter.consume("key1", 2) is True


def test_consume_more_than_capacity():
    """AC-03: requesting more than capacity returns False."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    assert limiter.consume("key1", 11) is False


def test_consume_negative_tokens():
    """Consuming negative tokens should raise ValueError."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with pytest.raises(ValueError):
        limiter.consume("key1", -1)


def test_consume_empty_bucket_raises():
    """AC-04: empty bucket raises RateLimitExceeded on consume."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    limiter.consume("key1", 5)
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key1", 1)


def test_consume_empty_bucket_raises_after_refill_exhaustion():
    """AC-04: RateLimitExceeded raised after refill is consumed and bucket emptied."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    limiter.consume("key1", 3)
    limiter.consume("key1", 2)
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key1", 1)


def test_rate_limit_exceeded_is_exception():
    """AC-04: RateLimitExceeded subclasses Exception for framework compatibility."""
    assert issubclass(RateLimitExceeded, Exception)


def test_rate_limit_exceeded_message():
    """AC-04: RateLimitExceeded carries a descriptive message."""
    exc = RateLimitExceeded("rate limit exceeded for key")
    assert str(exc) == "rate limit exceeded for key"


def test_refill_restores_tokens():
    """AC-05: tokens refill over time according to refill_per_second."""
    limiter = RateLimiter(capacity=10, refill_per_second=50.0)
    limiter.consume("key1", 10)
    time.sleep(0.2)
    assert limiter.consume("key1", 5) is True


def test_refill_capped_at_capacity():
    """AC-05: refill never exceeds capacity even after long idle period."""
    limiter = RateLimiter(capacity=5, refill_per_second=100.0)
    limiter.consume("key1", 5)
    time.sleep(0.5)
    assert limiter.consume("key1", 5) is True
    assert limiter.consume("key1", 1) is False


def test_refill_after_partial_consume():
    """AC-05: refill adds to remaining tokens after a partial consume."""
    limiter = RateLimiter(capacity=10, refill_per_second=50.0)
    limiter.consume("key1", 7)
    time.sleep(0.2)
    assert limiter.consume("key1", 5) is True


def test_refill_zero_rate_no_restore():
    """AC-05: zero refill rate means no token restoration."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    limiter.consume("key1", 5)
    time.sleep(0.5)
    assert limiter.consume("key1", 6) is False


def test_new_key_starts_full():
    """AC-01: a previously unseen key starts with a full bucket of capacity tokens."""
    limiter = RateLimiter(capacity=8, refill_per_second=0.0)
    assert limiter.consume("newkey", 8) is True


def test_eviction_preserves_active_key():
    """AC-07: a key recently touched is not evicted and retains its bucket state."""
    limiter = RateLimiter(capacity=10, refill_per_second=0.0)
    limiter.consume("active_key", 5)
    limiter.consume("active_key", 3)
    assert limiter.consume("active_key", 2) is True


def test_eviction_stale_key_refills():
    """AC-07: a key untouched for over one hour refills to capacity after eviction."""
    limiter = RateLimiter(capacity=10, refill_per_second=1000.0)
    limiter.consume("stale_key", 10)
    time.sleep(5.0)
    assert limiter.consume("stale_key", 10) is True
```
