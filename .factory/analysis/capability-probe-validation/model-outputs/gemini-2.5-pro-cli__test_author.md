```python
import pytest
from unittest.mock import MagicMock

# The 'clock' module is a dependency, so we mock it.
# We are creating a mock object that can be controlled within the tests.
clock = MagicMock()

# The interface to be tested.
# In a real pytest environment, this would be an installed package.
# For this exercise, we assume `from interface import ...` works.
from interface import RateLimiter, RateLimitExceeded


def test_construction_and_initial_state_ac01():
    """AC-01: A new key should start with a full bucket of tokens."""
    limiter = RateLimiter(capacity=100, refill_per_second=10)
    # The first consumption should succeed as the bucket is full.
    assert limiter.consume("new_key", 100) is True


def test_consume_success_ac02():
    """AC-02: consume returns True when sufficient tokens are available."""
    limiter = RateLimiter(capacity=50, refill_per_second=10)
    assert limiter.consume("key1", 20) is True
    # After consuming 20, there should be 30 left, so consuming 30 should also succeed.
    assert limiter.consume("key1", 30) is True


def test_consume_failure_insufficient_tokens_ac03():
    """AC-03: consume returns False when there are not enough tokens."""
    limiter = RateLimiter(capacity=20, refill_per_second=10)
    # Consume 15, leaving 5.
    assert limiter.consume("key2", 15) is True
    # Trying to consume 10 more should fail.
    assert limiter.consume("key2", 10) is False


def test_consume_failure_does_not_modify_bucket_ac03():
    """AC-03: A failed consume does not change the token count."""
    limiter = RateLimiter(capacity=30, refill_per_second=5)
    # Consume 20, leaving 10.
    limiter.consume("key3", 20)
    # This should fail.
    assert limiter.consume("key3", 15) is False
    # This should succeed, as the previous failure didn't alter the bucket.
    assert limiter.consume("key3", 10) is True


def test_throttling_signal_on_empty_bucket_ac04():
    """AC-04: consume raises RateLimitExceeded when the bucket is empty."""
    limiter = RateLimiter(capacity=10, refill_per_second=1)
    # Drain the bucket.
    limiter.consume("key4", 10)
    # Any further attempt should raise the exception.
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key4", 1)


@pytest.mark.parametrize("elapsed_ns, refilled_tokens", [
    (1_000_000_000, 10),      # 1 second
    (5_000_000_000, 50),      # 5 seconds
    (500_000_000, 5),         # 0.5 seconds
])
def test_token_refill_over_time_ac05_ac06(monkeypatch, elapsed_ns, refilled_tokens):
    """
    AC-05: Tokens refill based on elapsed time.
    AC-06: The implementation must use the provided clock source.
    """
    monkeypatch.setattr("interface.clock", clock)
    
    start_time_ns = 100_000_000_000
    clock.monotonic_ns.return_value = start_time_ns
    
    limiter = RateLimiter(capacity=100, refill_per_second=10)

    # Consume the entire bucket.
    assert limiter.consume("key5", 100) is True
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key5", 1)
        
    # Advance the mocked time.
    clock.monotonic_ns.return_value = start_time_ns + elapsed_ns

    # The bucket should have refilled, allowing consumption again.
    # We check if we can consume *exactly* the expected refilled amount.
    assert limiter.consume("key5", refilled_tokens) is True


def test_refill_does_not_exceed_capacity_ac05(monkeypatch):
    """AC-05: The token count cannot exceed the bucket's capacity."""
    monkeypatch.setattr("interface.clock", clock)

    start_time_ns = 200_000_000_000
    clock.monotonic_ns.return_value = start_time_ns
    
    limiter = RateLimiter(capacity=100, refill_per_second=10)

    # Consume some tokens to make space for refilling.
    limiter.consume("key6", 20)

    # Advance time far into the future, enough to refill well past capacity.
    clock.monotonic_ns.return_value = start_time_ns + 100 * 1_000_000_000

    # Bucket should be full, but not over-full. Consuming full capacity works.
    assert limiter.consume("key6", 100) is True
    
    # Bucket is now empty, so next consume raises.
    with pytest.raises(RateLimitExceeded):
        limiter.consume("key6", 1)


def test_key_eviction_ac07(monkeypatch):
    """
    AC-07: Keys untouched for over an hour may be evicted.
    A re-request for an evicted key should treat it as a new key with full capacity.
    """
    monkeypatch.setattr("interface.clock", clock)

    start_time_ns = 300_000_000_000
    clock.monotonic_ns.return_value = start_time_ns

    limiter = RateLimiter(capacity=100, refill_per_second=10)

    # Use a key, partially draining its bucket.
    limiter.consume("key-to-evict", 50)

    # Advance time by more than an hour (3601 seconds).
    one_hour_one_sec_ns = 3601 * 1_000_000_000
    clock.monotonic_ns.return_value = start_time_ns + one_hour_one_sec_ns

    # Because the key should have been evicted, it now acts like a new key.
    # We should be able to consume the full capacity.
    assert limiter.consume("key-to-evict", 100) is True


def test_multiple_keys_are_independent():
    """AC-01, AC-02, AC-03: Different keys have independent token buckets."""
    limiter = RateLimiter(capacity=100, refill_per_second=10)

    # Consume from two different keys.
    assert limiter.consume("user_A", 70) is True
    assert limiter.consume("user_B", 40) is True

    # user_A has 30 left.
    assert limiter.consume("user_A", 30) is True
    with pytest.raises(RateLimitExceeded):
        limiter.consume("user_A", 1)
        
    # user_B has 60 left, and is unaffected by user_A's activity.
    assert limiter.consume("user_B", 60) is True
    with pytest.raises(RateLimitExceeded):
        limiter.consume("user_B", 1)

```
