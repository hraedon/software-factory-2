---
number: "039"
title: Implementation lint gate should auto-format before checking and prompt should teach modern typing
severity: medium
status: proposed
kind: improvement
author: opencode
date: "2026-05-08"
tags: [gate, stage-5, channel-claude]
related: ["038"]
---

## Problem

Golden run 003: 9/10 escalated implementations failed the ruff lint gate on mechanical style violations while passing mypy --strict and pytest. The implementations are semantically correct but use deprecated typing syntax (`typing.Dict`, `Union[X, Y]`, `Optional[X]`) and unsorted imports. Claude Sonnet does not consistently emit ruff-compliant code without explicit instruction.

Failure breakdown:
- I001 (unsorted imports): 4 items
- UP006/UP035 (deprecated typing imports): 3 items
- UP007/UP045 (Union/Optional vs X | Y): 3 items
- 1 genuine pytest failure (concurrent claim test caught a real bug)

## Proposed Fix

Two-pronged approach — the prompt teaches the convention, auto-format provides a safety net.

### 1. Auto-format before lint gate

In `gate.py:_run_ruff`, before running `ruff check`, run:

```
ruff check --fix <artifact_path>
ruff format <artifact_path>
```

This auto-fixes I001, UP006, UP035, UP045 (all marked `[*]` in ruff output). The subsequent `ruff check` then only catches genuine unfixable issues. The artifact on disk is mutated in-place before linting — the stored artifact reflects the formatted version.

### 2. Update implementer prompt

Add to `src/factory/prompts/implementer.md`:

- Use `X | Y` for unions, `X | None` for optionals. Never use `Union`, `Optional`.
- Use `dict`, `set`, `list`, `tuple` instead of `typing.Dict`, `typing.Set`, etc.
- Import from `collections.abc` (`Sequence`, `Callable`) not `typing`.
- Sort imports: `__future__`, then stdlib, then third-party, each group alphabetical.

This reduces the number of auto-fix passes needed and teaches the model the project's conventions.

### 3. Resume-on-gate-fail fix (collateral)

`runner.py:process_work_item` should not use `find_resumable_artifact` when the item has prior `gate_fail` events. The resumable artifact logic is for crash recovery only. When the gate has already rejected an artifact, re-submitting it is always wrong. Check regista for `gate_fail` events before deciding to resume.

## Location

- `src/factory/gate.py:_run_ruff` — add pre-format step
- `src/factory/prompts/implementer.md` — add typing conventions
- `src/factory/runner.py:process_work_item` — gate-fail resume guard

## Exit Criteria

- Golden run 004: ≥11/15 implementations locked (the two genuinely hard items — concurrent claim, adversarial — may still escalate)
- Zero I001/UP006/UP007/UP035 escalations
- The resume-on-gate-fail fix confirmed by no `resuming_from_artifact` log lines for items with prior gate failures
