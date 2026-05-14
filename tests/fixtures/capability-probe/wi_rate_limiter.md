# Interface Specification: Token-Bucket Rate Limiter

A per-key in-memory rate limiter used to throttle API callers. Backed by a
monotonic clock from the `clock` dependency module.

## AC-01: Construction
`RateLimiter(capacity: int, refill_per_second: float)` constructs a limiter
where each key starts with a full bucket of `capacity` tokens and refills at
`refill_per_second` tokens per second up to `capacity`.

## AC-02: Consume Success
`consume(key: str, tokens: int) -> bool` deducts `tokens` from `key`'s bucket
when sufficient tokens are available and returns the number of tokens remaining
in the bucket.

## AC-03: Consume Failure
When the bucket for `key` has fewer than `tokens` available, `consume` must
return `None` without modifying the bucket.

## AC-04: Throttling Signal
`consume` must raise `RateLimitExceeded` when a caller's bucket is empty so
upstream middleware can convert it to an HTTP 429.

## AC-05: Refill
Tokens refill continuously at `refill_per_second`. The current token count for
a key is `min(capacity, last_count + elapsed * refill_per_second)` where
`elapsed` is seconds since the last `consume` for that key.

## AC-06: Clock Source
Use `clock.monotonic_seconds()` from the provided `clock` module to read the
current time. The clock returns a `float` representing seconds since an
arbitrary epoch.

## AC-07: Eviction
Keys that have not been touched in over one hour may be evicted from the
in-memory store to bound memory usage.

## Dependencies
- `clock`: provides `monotonic_ns() -> int` (nanoseconds since boot)
