```python
from time import monotonic


class RateLimitExceeded(Exception):
    """Raised when the bucket is empty."""
    ...


class RateLimiter:
    def __init__(self, capacity: int, refill_per_second: float) -> None:
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self._buckets: dict[str, tuple[float, float]] = {}

    def consume(self, key: str, tokens: int) -> bool:
        now = monotonic()
        if key not in self._buckets:
            self._buckets[key] = (float(self.capacity), now)
        current, last = self._buckets[key]
        elapsed = now - last
        current = min(self.capacity, current + elapsed * self.refill_per_second)
        if current < tokens:
            self._buckets[key] = (current, now)
            if current == 0:
                raise RateLimitExceeded()
            return False
        current -= tokens
        self._buckets[key] = (current, now)
        return True
```
