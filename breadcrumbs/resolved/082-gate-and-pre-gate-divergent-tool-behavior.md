---
number: "082"
title: "Outer gate (gate.py) and inner gate (pre_gate.py) have divergent tool path resolution, failure handling, and error surfaces"
severity: medium
status: resolved
kind: bug
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [gate, runner, stage-5]
related: ["059", "075", "079"]
---

## Problem

The outer gate (`gate.py`) and inner gate (`pre_gate.py`) contain near-duplicate implementations of mypy, ruff, and pytest subprocess execution with systematic divergence:

| Dimension | Outer gate (`gate.py`) | Inner gate (`pre_gate.py`) |
|---|---|---|
| ruff path resolution | `shutil.which("ruff")` with fallback to `<prefix>/bin/ruff` | `python -m ruff` |
| ruff --fix | Yes (line 666) | Not called — only `check --fix` (line 188) |
| ruff format | Called separately (line 671) | Not called |
| pytest path resolution | `python -m pytest` | `python -m pytest` |
| mypy path resolution | `python -m mypy` | `python -m mypy` |
| Tool-not-found handling | `passed=False, tool_not_found` (per BC-059) | `passed=True` (silent, see BC-079) |
| Exception handling | Explicit failure + diagnostics | Bare `except Exception: passed=True` |
| Diagnostic truncation | First 10 lines | Last 3 lines (pytest) / first 10 lines (mypy) |

These divergences mean:
- A ruff path that works in one gate may not work in the other.
- A tool-failure bug fixed in the outer gate won't automatically carry to the inner gate.
- The inner gate doesn't run `ruff format`, so formatting issues aren't caught until the outer gate.

## Impact

Each fix to one gate's subprocess execution requires a parallel fix to the other. This has already happened once: BC-059 was applied to `gate.py` only, creating BC-079. Without structural unification, the two code paths will continue to drift.

## Proposed fix

Extract a shared subprocess execution layer (`gate_runner.py`?) with:
- Unified tool discovery (ruff path, mypy module, pytest module)
- Unified tool-not-found handling
- Unified exception propagation
- Unified diagnostic truncation
- Configurable ruff auto-format behavior

Then refactor both `gate.py` and `pre_gate.py` to delegate to the shared layer. This is a moderate refactor but pays off as more gates are added (Phase 3+ multi-channel, Phase 4 jury, Phase 5 behavioral).

Alternatively: inline the inner gate into `gate.py` itself, so there's one source file for all subprocess-based evaluation. Simpler but larger file.

See also RFC-011 (unify gate evaluation).

## Resolution

Closed the three divergences that affect golden run outcomes:

1. **Tool-not-found handling** (BC-079): Inner gate now returns `passed=False` when mypy/pytest/ruff are missing, matching outer gate.
2. **Exception handling** (BC-079): Bare `except Exception: passed=True` replaced with explicit failure propagation, matching outer gate.
3. **Final ruff check**: Inner gate now runs `ruff check --fix` → `ruff format` → `ruff check` (final), matching the outer gate's three-step sequence. Previously missing the final check, so unfixable lint issues (bare `except`, etc.) passed the inner gate and only failed at the outer gate, wasting model budget.

Remaining divergence (ruff path: `shutil.which` vs `python -m`) is benign — `python -m` is more venv-safe. Full structural unification (shared subprocess layer) deferred to RFC-011 (Phase 3).
