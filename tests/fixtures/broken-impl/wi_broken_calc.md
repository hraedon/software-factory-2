# Interface Specification: Broken Calculator

A minimal arithmetic utility with subtle edge-case requirements.

## AC-01: Parse Integer

`parse_int(value: str) -> int | None` — Parse an integer from a string. Return `None` for non-numeric input including empty strings. Must handle leading/trailing whitespace. Must NOT raise `ValueError` for any input.

## AC-02: Safe Divide

`safe_divide(a: float, b: float) -> float` — Divide `a` by `b`. Return `float('inf')` when `b` is `0.0`. Must NOT use `try`/`except` — use a conditional guard instead.

## AC-03: Clamp

`clamp(value: float, lo: float, hi: float) -> float` — Clamp `value` to `[lo, hi]`. If `lo > hi`, swap them silently (do not raise).
