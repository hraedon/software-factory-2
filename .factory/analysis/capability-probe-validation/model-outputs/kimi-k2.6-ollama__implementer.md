```python
from __future__ import annotations

import clock


class RateLimitExceeded(Exception):
    pass


class RateLimiter:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = capacity
        self._refill_per_second = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}

    def consume(self, key: str, tokens: int) -> bool:
        now = clock.monotonic_seconds()
        current_tokens = self._capacity
        bucket = self._buckets.get(key)
        if bucket is not None:
            last_tokens, last_time = bucket
            elapsed = now - last_time
            if elapsed > 3600.0:
                del self._buckets[key]
            else:
                current_tokens = min(
                    self._capacity,
                    last_tokens + elapsed * self._refill_per_second,
                )
        if current_tokens == 0:
            raise RateLimitExceeded()
        if current_tokens < tokens:
            return False
        new_tokens = current_tokens - tokens
        self._buckets[key] = (new_tokens, now)
        return True
```
