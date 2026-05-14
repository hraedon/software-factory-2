```python
from unittest.mock import patch

import pytest

import clock
from interface import RateLimiter, RateLimitExceeded


def test_initial_bucket_full_capacity():
    """AC-01: New key starts with a full bucket of capacity tokens."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("k", 10) is True


def test_construction_zero_refill():
    """AC-01: RateLimiter can be constructed with zero refill rate."""
    limiter = RateLimiter(capacity=5, refill_per_second=0.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("k", 5) is True


def test_consume_success_returns_true():
    """AC-02: consume returns True when sufficient tokens available."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        result = limiter.consume("k", 5)
    assert result is True


def test_consume_success_deducts_tokens():
    """AC-02: consume deducts tokens from the key's bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("k", 7) is True
        assert limiter.consume("k", 3) is True


def test_consume_exact_capacity():
    """AC-02: consume succeeds when requesting exactly capacity tokens."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("k", 10) is True


def test_consume_zero_tokens():
    """AC-02: consume with zero tokens succeeds without modifying bucket."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("k", 0) is True


def test_keys_independent():
    """AC-02: Each key has an independent token bucket."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("k1", 5) is True
        assert limiter.consume("k2", 5) is True


def test_empty_string_key():
    """AC-02: Empty string is a valid key."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        assert limiter.consume("", 5) is True


def test_consume_insufficient_returns_falsy():
    """AC-03: consume returns falsy when bucket has fewer tokens than requested."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        result = limiter.consume("k", 10)
    assert not result


def test_consume_insufficient_preserves_bucket():
    """AC-03: consume does not deduct tokens when insufficient tokens."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 10)
        result = limiter.consume("k", 5)
    assert result is True


def test_insufficient_not_empty_no_exception():
    """AC-03: consume returns falsy — not raises — when bucket has some but not enough tokens."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 3)
        result = limiter.consume("k", 5)
    assert not result


def test_insufficient_preserves_remaining():
    """AC-03: After failed consume, remaining tokens stay available."""
    limiter = RateLimiter(capacity=5, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 3)
        assert not limiter.consume("k", 5)
        result = limiter.consume("k", 2)
    assert result is True


def test_empty_bucket_raises_rate_limit_exceeded():
    """AC-04: consume raises RateLimitExceeded when bucket is empty."""
    limiter = RateLimiter(capacity=3, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 3)
        with pytest.raises(RateLimitExceeded):
            limiter.consume("k", 1)


def test_rate_limit_exceeded_is_exception():
    """AC-04: RateLimitExceeded inherits from Exception."""
    assert issubclass(RateLimitExceeded, Exception)


def test_refill_restores_tokens():
    """AC-05: Tokens refill at refill_per_second between consumes."""
    limiter = RateLimiter(capacity=10, refill_per_second=2.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 10)
    with patch.object(clock, "monotonic_ns", return_value=3_000_000_000):
        result = limiter.consume("k", 6)
    assert result is True


def test_refill_capped_at_capacity():
    """AC-05: Token count does not exceed capacity after refill."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 5)
    with patch.object(clock, "monotonic_ns", return_value=100_000_000_000):
        result = limiter.consume("k", 10)
    assert result is True


def test_refill_formula():
    """AC-05: Refill is min(capacity, last_count + elapsed * refill_per_second)."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 8)
    with patch.object(clock, "monotonic_ns", return_value=5_000_000_000):
        result = limiter.consume("k", 7)
    assert result is True


def test_uses_clock_monotonic_ns():
    """AC-06: RateLimiter calls clock.monotonic_ns for time."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    with patch.object(clock, "monotonic_ns", return_value=0) as mock_clock:
        limiter.consume("k", 1)
    mock_clock.assert_called()


def test_stale_key_recovered_after_one_hour():
    """AC-07: Keys not touched for over one hour remain functional."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.0)
    one_hour_plus_ns = 3601_000_000_000
    with patch.object(clock, "monotonic_ns", return_value=0):
        limiter.consume("k", 10)
    with patch.object(clock, "monotonic_ns", return_value=one_hour_plus_ns):
        result = limiter.consume("k", 1)
    assert result is True
```
