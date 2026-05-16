---
number: "176"
title: "integration_mypy --strict rejects interface-spec ellipsis-body stubs as empty-body errors"
severity: high
status: proposed
kind: bug
author: gr035-post-mortem
date: "2026-05-16"
tags: [stage-8, gate, integration, mypy, interface-architect, integrator, CLASS-008]
related: ["175", "174"]
---

## Symptom

Once BC-175 is fixed (mypy actually runs), `integration_mypy` reports
`[empty-body]` errors on every function in the assembled tree whose body is
`...` and whose declared return type is not `None`:

```
fr01_dashboard.py:31: error: Missing return statement  [empty-body]
fr02_tls_scan.py:29: error: Missing return statement  [empty-body]
fr02_tls_scan.py:33: error: Missing return statement  [empty-body]
fr03_upload.py:26: error: Missing return statement  [empty-body]
fr05_scheduler.py:3: error: Missing return statement  [empty-body]
cert_chain_library.py:8: error: Missing return statement  [empty-body]
```

This pattern is pervasive: it's how the `interface_architect` role
expresses interface stubs (e.g. `def scan_host(...) -> ScannedEntry: ...`),
and the integrator carries those stubs into the assembled tree.

mypy `--strict` (which enables `--strict-equality`, `--no-implicit-reexport`,
*and* the implicit `[empty-body]` check) treats `...` bodies as missing
returns unless the function is `@abstractmethod` or lives in a `.pyi` stub.

## Evidence

- GR-035 attempt 4, integration item `b77419a6-...` once BC-175 mock-fix is
  applied locally: 7 of the 18 mypy errors are `[empty-body]`. After
  filtering the BC-175 noise, this is the dominant remaining failure class.
- Reproduction with the preserved artifact reproduces the same set of
  `[empty-body]` errors deterministically.
- Same artifact + `--allow-empty-bodies` passes those checks; remaining
  errors are tractable (untyped tests, `Callable` type-arg).

## Why GR-034 didn't hit this

GR-034 (`cert-watch-mini`) had small interfaces with fewer stub-only
functions exposed to the integration stage. The ratio of body-bearing
implementations to ellipsis stubs was high enough that no `[empty-body]`
errors fired in the assembled tree.

## Root cause

Design mismatch between role outputs and gate flags:

- `interface_architect` legitimately emits ellipsis-body stubs as the spec
  contract.
- `implementer` body-fills those stubs in its own module, but the
  integrator's assembled tree keeps the interface modules side-by-side with
  the implementations for boundary verification.
- `integration_mypy` runs with `--strict`, which makes ellipsis stubs an
  error unless `@abstractmethod` or `.pyi`.

There's no role error to blame here — the integrator is faithfully
re-presenting the input. The gate is choosing the wrong subset of
`--strict`.

## Fix

Add `--allow-empty-bodies` to the mypy invocation in `evaluate_integration`
(`gate.py:1215-1222`), keeping `--strict` for everything else. Available in
mypy ≥ 0.981 (`mypy 1.0+` in our pyproject).

Consider applying the same flag to:

- `implementation_mypy` (`gate.py:614-680`)
- `pre_gate_implementation` inner mypy (`pre_gate.py:813-852`)

…on the same rationale (ellipsis stubs from interface modules referenced by
the implementation file). This is part of why GR-035 implementations also
saw mypy noise. Audit those call sites and decide per-call.

## Acceptance criteria

- AC-1: `integration_mypy` no longer fails with `[empty-body]` on
  ellipsis-body stub functions emitted by `interface_architect`.
- AC-2: Real `--strict` checks (e.g. missing return annotations,
  type-arg on generics) still fire and still fail the gate.
- AC-3: Regression test in `tests/test_gate_integration.py` includes a
  module with `def foo() -> T: ...` and asserts the gate passes when the
  rest of the tree is well-typed.

## Touched surface

- `src/factory/gate.py` — `evaluate_integration` mypy args, `_run_mypy` for
  `implementation_mypy`.
- `src/factory/pre_gate.py` — `_run_mypy_fast` (decide).
- `tests/test_gate_integration.py` — regression fixture.

## Open question

Should `--allow-empty-bodies` apply uniformly across mypy gates, or only at
the integration boundary where interface modules and implementation modules
co-exist? Recommendation: uniform — the cost of a stub slipping through is
caught by other gates (`pytest`, `outcome_verifier`), and the cost of
gate-by-gate divergence is high.

## Related

- BC-175 — must be fixed first; otherwise mypy bails before reaching these.
- BC-177 — separate pytest-side concern surfacing in the same gate stack.

## Resolution

Implemented in the BC-175/176/177 bundle session. Discovered during GR-035 forensics.

**Decision on uniform application:** Applied `--allow-empty-bodies` uniformly
to all three mypy call sites:
- `evaluate_integration` Gate 2 (`gate.py`) — primary fix site.
- `_run_mypy` for `implementation_mypy` (`gate.py:651`).
- `_run_mypy_fast` for `pre_gate_implementation` (`pre_gate.py:834`).

Rationale: the BC recommendation is uniform; gate-by-gate divergence creates
confusion and mismatched feedback for the same codebase pattern. The cost of
an ellipsis stub surviving the pre/implementation gate is low — `pytest` and
`outcome_verifier` catch functional gaps.

**Side-effect:** Two existing pre-gate tests used `def f() -> str: pass` as
the trigger for a mypy failure. Those tests were updated to use a genuine type
error (`return 42` where `-> str`) so they remain valid regression tests.

**Regression tests** locked in by `tests/test_integration_gates.py`:
- `TestBC176AllowEmptyBodies::test_ellipsis_stub_passes_mypy_gate`
- `TestBC176AllowEmptyBodies::test_real_type_error_still_fails_despite_empty_body_flag`

Status: `status: resolved`
