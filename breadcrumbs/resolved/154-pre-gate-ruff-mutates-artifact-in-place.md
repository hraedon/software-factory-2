---
number: "154"
title: "_run_ruff_fast modifies artifact in-place inside inner gate — original model output lost"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [runner, gate, pre_gate, inner-gate]
related: []
---

## Summary

`_run_ruff_fast()` in `pre_gate.py:735-739` modifies the artifact file **in place** when ruff auto-fixes formatting or lint issues. This is called from `_inner_gate_loop` in `runner.py` on the `current_artifact` living in the workspace.

```python
# pre_gate.py:735-739
if fixed_content != original_content:
    orig_backup = artifact_path.parent / f".{artifact_path.name}{_RAW_ARTIFACT_SUFFIX}"
    orig_backup.write_text(original_content)
    artifact_path.write_text(fixed_content)
```

While a `.orig` backup file is created, the side effects are significant:

1. The model's raw output is silently replaced with ruff-formatted content.
2. If ruff introduces errors or changes semantics, those modified artifacts are what get submitted to the outer gate.
3. Subsequent inner gate retries operate on the *already-riffed* version, not the model's original output.
4. The `.orig` backup files accumulate in the workspace without cleanup.
5. This is a side effect in what appears to be a read-only check function — callers don't expect their files to be rewritten.

## Impact

- In GR-019, BC-123 was specifically validated as "auto-fix-back copies ruff-corrected artifacts back instead of retrying." The rationale was that auto-fix saves a model retry. But the side effect means the workspace no longer contains what the model produced.
- For forensic analysis of model output quality, the `.orig` files must be found and compared. There's no mechanism to correlate which `.orig` belongs to which attempt.
- If a future inner gate or prompt change depends on the exact model output (e.g., to analyze model behavior patterns), the data has been destroyed.

## Fix

Move the auto-fix-back logic to the *post-inner-gate* path in `runner.py` (`submit` path), not inside the gate check function. The check function should only report pass/fail; the apply-fix step should be explicit and logged.

## Resolution

_run_ruff_fast() is now side-effect-free — returns ruff_fixed_content in result dict instead of writing back to artifact_path. Calling functions (pre_gate_implementation, pre_gate_interface_spec, pre_gate_test_suite) explicitly apply fixes via _apply_ruff_fix() after ruff passes, making the side effect visible and logged.
