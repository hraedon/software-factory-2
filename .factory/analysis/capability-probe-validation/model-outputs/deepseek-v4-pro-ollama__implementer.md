```python
from clock import monotonic_ns


_EVICTION_NS = 3_600_000_000_000


class RateLimitExceeded(Exception):
    pass


class RateLimiter:

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self._capacity = float(capacity)
        self._refill = refill_per_second
        self._buckets: dict[str, float] = {}
        self._touched: dict[str, int] = {}

    def consume(self, key: str, tokens: int) -> bool:
        now = monotonic_ns()
        bucket = self._buckets.get(key, self._capacity)
        last = self._touched.get(key)

        if last is not None:
            diff = now - last
            if diff > _EVICTION_NS:
                self._buckets.pop(key, None)
                self._touched.pop(key, None)
                bucket = self._capacity
            else:
                elapsed = diff / 1e9
                if elapsed < 0.0:
                    elapsed = 0.0
                bucket = min(self._capacity, bucket + elapsed * self._refill)

        if bucket >= tokens:
            self._buckets[key] = bucket - tokens
            self._touched[key] = now
            return True

        if bucket <= 0.0:
            raise RateLimitExceeded()

        return None
```
