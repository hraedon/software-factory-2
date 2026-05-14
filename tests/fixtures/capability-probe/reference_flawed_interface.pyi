# Reference flawed interface for capability-probe downstream roles
# Preserves D1, D2, D3, D4, D5 as originally planted in wi_rate_limiter.md

class RateLimitExceeded(Exception):
    """Satisfies AC-04."""
    ...


class RateLimiter:
    """Satisfies AC-01, AC-05, AC-06, AC-07."""

    def __init__(self, capacity: int, refill_per_second: float) -> None:
        """Satisfies AC-01."""
        ...

    def consume(self, key: str, tokens: int) -> bool:
        """Satisfies AC-02, AC-03, AC-04."""
        ...
