---
number: "RFC-011"
title: "Unified subprocess execution layer — eliminate gate/runner subprocess footguns by routing all calls through a typed wrapper"
severity: critical
status: implemented
kind: design
author: deepseek-v4-pro (adversarial review — Session 20); expanded claude (Session 25)
date: "2026-05-11"
updated: "2026-05-20"
tags: [gate, runner, subprocess, refactor, CLASS-005, CLASS-008]
related: ["082", "079", "059", "187", "RFC-012", "RFC-030", "CLASS-005", "CLASS-008"]
phase_needed: "Phase 3 (multi-channel gates)"
---

## Motivation

Two defect classes point at the same architectural hole — ad-hoc subprocess invocation scattered across `gate.py`, `pre_gate.py`, and `runner.py` with no shared execution layer.

**CLASS-005 — Inner/outer gate ruleset divergence (11 instances, critical)**

The inner gate (`pre_gate.py`) and outer gate (`gate.py`) are independently maintained. When one call site is updated the other is not, causing divergent behavior: tool path resolution differs (`shutil.which` vs `python -m ruff`), tool-not-found handling differs (BC-059 fix applied to outer only; inner silent-passed until BC-079), diagnostic truncation strategies differ, ruff auto-format runs in the outer gate but not the inner. Instances: BC-075, BC-079, BC-082, BC-085, BC-086, BC-114, BC-122, BC-123, BC-124, BC-131, BC-154.

**CLASS-008 — Gate subprocess execution and environment handling (12 instances, high)**

Gate subprocesses fail or misbehave because their execution environment is wrong: wrong `cwd`, wrong `PATH`, wrong env vars, tool not found, or the subprocess mutates files it should not. Each call site reconstructs subprocess invocation independently. The most recent instance — BC-187 — occurred in GR-038 when a subprocess inherited the caller's `cwd` (repo root) and wrote fixture artifacts into it. Instances: BC-059, BC-088, BC-093, BC-094, BC-099, BC-104, BC-114, BC-141, BC-142, BC-174, BC-187, RFC-012.

**The common root**: both classes exist because `cwd`, `env`, and `timeout` are optional in Python's `subprocess.run`. Every call site picks its own defaults, accumulates its own bugs, and never hears about fixes applied to the other copies. A single typed wrapper that requires all three as keyword-only arguments with no defaults turns the BC-187 class of bug into a `TypeError` at call time rather than a runtime failure discovered by a human reading a golden-run log.

## Proposed design

### `factory.subprocess` module

Introduce `src/factory/subprocess.py` (name chosen to shadow `subprocess` only within `factory/`; all internal imports use `from factory import subprocess as fsubprocess`).

Primary interface:

```python
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubprocessResult:
    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool


def run(
    *,
    cmd: list[str],
    cwd: Path,              # REQUIRED — no implicit caller cwd
    env: dict[str, str],    # REQUIRED — no implicit os.environ inherit; pass factory.subprocess.clean_env() for a safe baseline
    timeout_s: float,       # REQUIRED — no implicit timeout
    stdin: str | None = None,
    capture: bool = True,   # True: capture stdout/stderr; False: stream to caller
) -> SubprocessResult: ...


def clean_env() -> dict[str, str]:
    """Return a minimal safe environment (PATH, HOME, TMPDIR, LANG).
    Call sites that need additional vars extend this dict explicitly."""
    ...
```

Why keyword-only with no defaults for `cwd`, `env`, `timeout_s`: Python raises `TypeError` at call time if any of these is omitted. That is a compile-time-equivalent check — the BC-187 failure (cwd inherited from caller) and the BC-059 class of failures (no timeout) become impossible to introduce silently. The developer who forgets `cwd` gets a crash at import-time in tests, not a corrupted golden run.

The wrapper also owns:
- Uniform exception handling: `TimeoutExpired` → `SubprocessResult(timed_out=True)`; `OSError` on missing binary → `SubprocessResult(returncode=-1, stderr="binary not found: ...")`
- No mutation of the artifact path: callers must copy to a tempdir before passing that tempdir as `cwd`
- Credential stripping: delegate to `factory.sandbox.gate_subprocess_env()` as the recommended env source for gate calls (RFC-012 is already implemented)

### Relationship to `factory.sandbox`

`factory.sandbox.gate_subprocess_env()` (RFC-012, already implemented) returns an env dict with credentials stripped. Gate call sites should use `factory.subprocess.run(env=gate_subprocess_env(...), ...)`. The sandbox module continues to own the policy for which vars are stripped; `factory.subprocess` owns the mechanics of invocation.

## Migration plan

**Step 1 — introduce the wrapper (no behavior change)**

Add `src/factory/subprocess.py` with `run()` and `clean_env()`. No existing call sites are touched. Add `tests/test_subprocess_wrapper.py` with AC-3 tests. All CI checks pass; zero behavior change.

**Step 2 — migrate gate call sites (highest CLASS-005 / CLASS-008 density)**

Migrate all `subprocess.run(...)` and `subprocess.Popen(...)` calls in `gate.py` and `pre_gate.py` to `factory.subprocess.run`. These are the sites responsible for the majority of CLASS-005 and CLASS-008 instances:
- `gate.py`: mypy invocation, ruff lint, ruff format, pytest, pytest --collect-only
- `pre_gate.py`: ruff fast-check, import smoke-check, pytest --collect-only

Each migrated call must supply `cwd`, `env` (via `gate_subprocess_env()`), and `timeout_s` explicitly. The existing `GateSubprocessResult` shape is preserved at the gate module boundary; the wrapper result is translated there.

**Step 3 — migrate remaining call sites**

Migrate subprocess calls in `runner.py` and channel-side spawns. Channel-side subprocesses (e.g., opencode invocation) may use a thin specialization — `factory.subprocess.run` with a channel-specific env builder — but must still flow through the same wrapper. Add `# RFC-011-grandfathered: <reason>` inline comments for any call site that cannot be migrated (expected: zero in `src/factory/`; test-only sites are out of scope).

## Acceptance criteria

- **AC-1**: `factory.subprocess.run` exists with the strict interface; `cwd`, `env`, and `timeout_s` are keyword-only with no defaults; omitting any raises `TypeError`.
- **AC-2**: All `subprocess.run(...)` and `subprocess.Popen(...)` calls in `src/factory/` (excluding `tests/`) flow through `factory.subprocess.run` OR carry an inline `# RFC-011-grandfathered: <reason>` comment.
- **AC-3**: `tests/test_subprocess_wrapper.py` verifies that omitting `cwd`, `env`, or `timeout_s` raises `TypeError`; that a `TimeoutExpired` path returns `timed_out=True`; and that a missing binary returns `returncode=-1`.
- **AC-4**: GR-039 exercises the migrated code paths and shows zero subprocess-cwd/env regressions.
- **AC-5**: CLASS-005 and CLASS-008 instance-count growth stops post-migration, validated across GR-039 and one subsequent golden run.

## Target validation

GR-039 is the target validation run. Step 1 and Step 2 must land before GR-039 is launched. Step 3 can follow in GR-040 if Step 2 closes AC-4 cleanly. AC-5 is a trailing check across two runs.

## Interaction with RFC-030

RFC-011 is the systemic-fix invariant that unblocks CLASS-005 and CLASS-008's instance tables under RFC-030's promotion rule. Both classes are currently blocked from receiving new BC entries until this RFC moves from `proposed` to an implemented invariant. Moving status to `in_progress` with a concrete target (GR-039) satisfies RFC-030's Path A requirement for CLASS-005; CLASS-008 is carried along by the same migration.

## Out of scope

- Tests' own subprocess usage (pytest spawns its own subprocesses; that is pytest's contract with the OS, not factory's)
- Substrate-side subprocess work
- Model-channel-internal subprocess use (those are the channel's contract with the model binary, not factory's)
- Subprocess calls outside `src/factory/` (e.g., in `scripts/`)

## Historical note

The original RFC-011 text (Session 20) proposed a `GateRunner` class focused on extracting shared gate evaluation. That proposal correctly identified the symptom (inner/outer divergence) but underspecified the root fix. The `GateRunner` approach would still leave each call site choosing its own `cwd`, `env`, and `timeout`. This rewrite shifts the invariant from "shared gate logic" to "required subprocess parameters" — a smaller surface area with stronger enforcement guarantees.

v1 learned the same lesson via "string constant gravity" (BC-383): two copies of the same logic will diverge given enough time. The subprocess equivalent is: two call sites that both choose their own env will produce two different environments. The fix is not better coordination — it is eliminating the choice.

## Implementation status

All three migration steps complete. AC assessment:

- **AC-1**: `factory.subprocess.run` exists; `cmd`, `cwd`, `env`, `timeout_s` are keyword-only with no defaults; TypeError raised on omission.
- **AC-2**: Zero bare `subprocess.run`/`subprocess.Popen` calls in `src/factory/`. All 29 call sites route through the wrapper. No grandfathered exemptions.
- **AC-3**: 13 tests in `tests/test_subprocess_wrapper.py` cover TypeError on missing kwargs, timeout→`timed_out=True`, missing binary→`returncode=-1`, happy-path capture, cwd/env isolation, stdin.
- **AC-4**: Pending GR-039 validation.
- **AC-5**: Trailing check across GR-039 and one subsequent golden run.
