```python
from __future__ import annotations

import clock


class RateLimitExceeded(Exception):
    """Satisfies AC-04."""


class RateLimiter:
    """Satisfies AC-01, AC-05, AC-06, AC-07."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        if capacity < 0 or refill_per_second <= 0:
            raise ValueError
        self.capacity = float(capacity)
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}

    def consume(self, key: str, tokens: int) -> bool:
        if tokens < 0:
            raise ValueError
        now = clock.monotonic_seconds()
        if key not in self._buckets:
            tokens_available = self.capacity
        else:
            last_tokens, last_time = self._buckets[key]
            elapsed = max(0.0, now - last_time)
            tokens_available = min(
                self.capacity, last_tokens + (elapsed * self.refill_per_second)
            )
        if tokens > tokens_available:
            if tokens_available <= 0:
                raise RateLimitExceeded
            return None
        tokens_available -= float(tokens)
        self._buckets[key] = (tokens_available, now)
        expired_keys = [k for k, v in self._buckets.items() if now - v[1] > 3600]
        for k in expired_keys:
            del self._buckets[k]
        return True
```
