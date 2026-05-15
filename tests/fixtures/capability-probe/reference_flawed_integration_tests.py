"""Flawed integration tests for outcome_verifier capability probe.

These tests pass on the flawed assembly (they don't catch D1–D5) so the
outcome verifier must detect defects by code inspection, not test failure.
This mirrors the real pipeline where integration tests may be incomplete
and the outcome verifier is the backstop.
"""

import pytest
from rate_limiter import RateLimiter, RateLimitExceeded


def test_construction():
    rl = RateLimiter(capacity=10, refill_per_second=1.0)
    assert rl.capacity == 10
    assert rl.refill_per_second == 1.0


def test_consume_success():
    rl = RateLimiter(capacity=10, refill_per_second=1.0)
    result = rl.consume("user-1", tokens=3)
    assert result is True


def test_consume_failure_empty_bucket_raises():
    rl = RateLimiter(capacity=2, refill_per_second=0.0)
    rl.consume("user-2", tokens=2)
    with pytest.raises(RateLimitExceeded):
        rl.consume("user-2", tokens=1)


def test_refill_basic():
    rl = RateLimiter(capacity=10, refill_per_second=2.0)
    rl.consume("user-3", tokens=5)
    # Wait for refill (simulated by direct manipulation in real tests)
    # This test is weak — it does not verify elapsed-time calculation
    result = rl.consume("user-3", tokens=1)
    assert result is True
