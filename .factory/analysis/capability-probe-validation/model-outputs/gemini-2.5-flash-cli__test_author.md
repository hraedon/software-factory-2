```python
from unittest.mock import patch

import pytest

import clock
from interface import RateLimitExceeded, RateLimiter


def test_ac01_construction():
    """AC-01: RateLimiter(capacity, refill_per_second) initialization."""
    limiter = RateLimiter(capacity=10, refill_per_second=1.5)
    assert isinstance(limiter, RateLimiter)


def test_ac02_consume_success():
    """AC-02: consume returns True and deducts tokens when sufficient."""
    # Interface specifies bool return type; AC-02 specifies remaining count.
    # Following locked interface: asserting boolean success.
    limiter = RateLimiter(10, 1.0)
    assert limiter.consume("user1", 4) is True
    # Verify deduction: 10 - 4 = 6 remaining. Attempting to consume 7 should fail.
    assert limiter.consume("user1", 7) is False


def test_ac03_consume_failure_insufficient():
    """AC-03: consume returns False (per interface) if tokens are insufficient."""
    # AC-03 specifies return None; following locked interface (bool).
    limiter = RateLimiter(5, 1.0)
    assert limiter.consume("user2", 6) is False


def test_ac03_no_modification_on_failure():
    """AC-03: bucket is not modified when a consume call fails."""
    limiter = RateLimiter(10, 1.0)
    limiter.consume("user3", 5)  # 5 tokens remaining
    assert limiter.consume("user3", 6) is False  # Insufficient
    # Should still have 5 tokens
    assert limiter.consume("user3", 5) is True


def test_ac04_throttling_signal_when_empty():
    """AC-04: consume raises RateLimitExceeded when a caller's bucket is empty."""
    limiter = RateLimiter(10, 1.0)
    # Drain the bucket exactly
    assert limiter.consume("user4", 10) is True
    # Bucket is now empty. Next call must raise RateLimitExceeded.
    with pytest.raises(RateLimitExceeded):
        limiter.consume("user4", 1)


def test_ac05_ac06_refill_and_clock():
    """AC-05, AC-06: tokens refill continuously using clock.monotonic_seconds()."""
    with patch("clock.monotonic_seconds") as mock_time:
        mock_time.return_value = 100.0
        limiter = RateLimiter(capacity=10, refill_per_second=2.0)  # 2 tokens/sec
        
        # Initial drain
        limiter.consume("user5", 10)
        
        # 1.5 seconds pass -> 3.0 tokens refilled
        mock_time.return_value = 101.5
        assert limiter.consume("user5", 3) is True
        
        # Now empty again
        with pytest.raises(RateLimitExceeded):
            limiter.consume("user5", 1)


def test_ac05_refill_capped_at_capacity():
    """AC-05: current token count does not exceed capacity via refill."""
    with patch("clock.monotonic_seconds") as mock_time:
        mock_time.return_value = 0.0
        limiter = RateLimiter(capacity=5, refill_per_second=100.0)
        
        # Wait for massive refill
        mock_time.return_value = 3600.0
        
        # Capacity is 5, cannot consume 6
        assert limiter.consume("user6", 6) is False
        assert limiter.consume("user6", 5) is True


def test_ac07_eviction_window():
    """AC-07: keys not touched in over one hour may be evicted."""
    with patch("clock.monotonic_seconds") as mock_time:
        mock_time.return_value = 1000.0
        limiter = RateLimiter(10, 1.0)
        
        # Initial touch
        limiter.consume("user7", 10)
        
        # Advance time by > 1 hour (3601 seconds)
        mock_time.return_value = 4601.0
        
        # Key may have been evicted; if re-created or refilled, it should be full
        assert limiter.consume("user7", 10) is True


def test_boundary_multiple_keys_isolation():
    """AC-01, AC-02: verify rate limiting is per-key and isolated."""
    limiter = RateLimiter(10, 1.0)
    limiter.consume("alpha", 10)
    # "beta" should still have 10 tokens
    assert limiter.consume("beta", 10) is True
    # "alpha" is still empty
    with pytest.raises(RateLimitExceeded):
        limiter.consume("alpha", 1)


def test_boundary_floating_point_refill():
    """AC-05: refill handles floating point increments correctly."""
    with patch("clock.monotonic_seconds") as mock_time:
        mock_time.return_value = 0.0
        limiter = RateLimiter(10, 0.5)  # 1 token every 2 seconds
        
        limiter.consume("user8", 10)
        
        mock_time.return_value = 1.0  # 0.5 tokens refilled
        assert limiter.consume("user8", 1) is False
        
        mock_time.return_value = 2.0  # 1.0 tokens refilled
        assert limiter.consume("user8", 1) is True


def test_boundary_empty_key_string():
    """AC-02: verify consume handles empty string keys."""
    limiter = RateLimiter(10, 1.0)
    assert limiter.consume("", 5) is True
    assert limiter.consume("", 6) is False

```
