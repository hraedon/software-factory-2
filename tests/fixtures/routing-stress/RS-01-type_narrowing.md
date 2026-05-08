# RS-01: Type-Narrowing Safe Compute — Routing Stress (mypy)

**Purpose:** A computation function that accepts `int | float | str` and must
return a typed result union. The interface is intentionally designed to reward
careful `@overload` signatures and `TypeIs`/`TypeGuard` usage — a naive
pass-through implementation will fail `mypy --strict`.

## Acceptance Criteria

### AC-RS1: safe_compute dispatches on input type without `Any`

`safe_compute(value: int | float | str, divisor: int) -> ComputeResult`

- If `value` is `int` and `divisor != 0`: return `IntResult` with
  `quotient: int` (floor division), `remainder: int`, `original: int`.
- If `value` is `float` and `divisor != 0`: return `FloatResult` with
  `quotient: float`, `original: float`.
- If `value` is `str`: attempt `float(value)`. If parsing succeeds and
  `divisor != 0`, return `FloatResult`. If parsing fails, return
  `ParseError` with `raw_input: str` and `message: str`.
- If `divisor == 0`: return `DivisionByZero` with `original_type: Literal["int", "float", "str"]`.

`ComputeResult` is a tagged union of `IntResult | FloatResult | ParseError | DivisionByZero`.
Each variant is a frozen dataclass. No `Any` types anywhere in the public
interface. The `original_type` field on `DivisionByZero` must use
`Literal["int", "float", "str"]`, not a bare string.

**Work-item shape:** pure-interface with type-narrowing stress. The contract
requires `@overload` or union narrowing that survives `mypy --strict`.

## Glossary

- **ComputeResult** — tagged union: `IntResult | FloatResult | ParseError | DivisionByZero`.
- **Floor division** — Python `//` semantics for `int // int`.
- **Tagged union** — each variant is a distinct frozen dataclass; callers
  pattern-match on type, not on attribute presence.
