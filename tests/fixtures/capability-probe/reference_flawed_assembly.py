"""Reference flawed assembly for outcome_verifier capability probe.

This module tree deliberately preserves the planted defects from wi_rate_limiter.md
so the outcome verifier can be scored on end-to-end detection.

Planted defects in assembly:
- D1: `consume` returns `bool` instead of `int` (AC-02 says it returns tokens remaining).
- D2: Only AC-04 is honored (raises on empty); AC-03 (return None on insufficient) is ignored.
- D3: Imports `clock.monotonic_seconds()` which does not exist (only `monotonic_ns` exists).
- D4: No clamp for negative elapsed; no guard for refill_per_second <= 0.
- D5: No validation for tokens <= 0 or tokens > capacity.
"""

# clock.py — dependency module (only has monotonic_ns, not monotonic_seconds)
def monotonic_ns() -> int:
    return 0


# rate_limiter.py — assembled implementation
class RateLimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, tuple[float, int]] = {}

    def consume(self, key: str, tokens: int) -> bool:
        # D5: No validation for tokens <= 0 or tokens > capacity
        # D3: calls nonexistent clock.monotonic_seconds
        now = clock.monotonic_seconds()  # type: ignore[name-defined]
        if key not in self._buckets:
            self._buckets[key] = (now, self.capacity)
        last_time, last_count = self._buckets[key]
        elapsed = now - last_time
        # D4: no clamp for negative elapsed; no guard for refill_per_second <= 0
        current = min(self.capacity, last_count + int(elapsed * self.refill_per_second))
        if current < tokens:
            # D2: AC-04 only — raises on empty bucket; AC-03 (return None) ignored
            if current == 0:
                raise RateLimitExceeded()
            return False  # D1: returns bool instead of int (tokens remaining)
        new_count = current - tokens
        self._buckets[key] = (now, new_count)
        return True  # D1: returns bool instead of int


# __init__.py — wiring
from .rate_limiter import RateLimiter, RateLimitExceeded

__all__ = ["RateLimiter", "RateLimitExceeded"]
