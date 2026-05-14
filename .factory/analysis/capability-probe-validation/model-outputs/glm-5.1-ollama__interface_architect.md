```python
class RateLimitExceeded(Exception):
    """Satisfies AC-04."""
    ...


class RateLimiter:
    """Token-bucket rate limiter. Satisfies AC-01, AC-02, AC-07."""

    capacity: int
    refill_per_second: float

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        """Satisfies AC-01."""
        ...

    def consume(self, key: str, tokens: int) -> float | None:
        """Satisfies AC-02, AC-03, AC-04, AC-05, AC-06."""
        ...
```
