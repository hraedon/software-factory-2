---
number: "217"
title: "Adversarial review: 3 critical bugs + 8 high-severity issues found and fixed"
severity: critical
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-27"
tags: [telemetry, runner, gate, decomposer, subprocess, security, CLASS-012]
related: ["208", "200"]
---

## Summary

Comprehensive adversarial review of the full `src/factory/` codebase identified 3 critical bugs, 8 high-severity issues, 20+ medium issues, and 30+ low issues. All critical and high issues were fixed; remaining systemic patterns recorded as BC-218 and RFC-038.

## Critical bugs fixed

1. **telemetry.py `NameError`** — `ig_pass` variable only assigned inside `if inner_gate_evaluations > 0:` block but referenced unconditionally in `all_pass` calculation. Would crash any telemetry report for runs with no inner gate data.

2. **inner_gate.py `JSONDecodeError`** — `json.loads(cp_data)` on model-produced cannot_proceed.json without try/except. Error in error-handling path masks original failures. Fixed with `_safe_json_parse()` helper.

3. **populate_work_items.py dead code branch** — `elif args.decomposer_channel and (args.spec_yaml or args.spec_md)` was unreachable because earlier `if args.spec_yaml` and `elif args.spec_md` branches matched first. Model-driven decomposer (RFC-023 Phase B) could never be invoked. Reordered conditionals.

## High-severity issues fixed

4. **subprocess.py env={} leak** — `env if env else None` converted explicit empty dict to None, leaking full parent environment. Changed to `env if env is not None else None`.

5. **venv.py CalledProcessError wrong arg order** — 4 instances passed `result.stderr` as the `cmd` argument instead of `stderr=`, producing misleading error messages like `Command 'Traceback...' returned non-zero exit status 1`.

6. **Hardcoded strings (CLASS-012 instances)** — router.py `"implementation"`, telemetry.py 40+ gate-name strings, jury_orchestrator.py `"jury_aggregate"`/`"multi"`, review.py `"cross_family_reviewer"`, spec_review.py `"interface_architect"`, inner_gate.py `"cannot_proceed"`. All replaced with constants.

7. **review_surface.py wrong key** — Looked up `cannot_proceed_reason` but pipeline stores under `diagnostics`. Fixed to extract from diagnostics dict.

8. **gate/integration.py wrong timeout** — Import check used `pytest_timeout` (300s) instead of `import_timeout` (60s).

9. **jury.py fragile `fb_outputs`** — Variable only assigned in fallback branch but referenced unconditionally via lazy ternary. Initialized before branch.

10. **telemetry.py dead `TRANSITION_CHANNEL_FAIL` branch** — Code filtered for gate_pass/gate_fail transitions, making the channel_fail branch unreachable. Added `TRANSITION_CHANNEL_FAIL` to the filter set.

11. **decomposer_model.py / spec_review.py `idx += end` bug** — `raw_decode` returns absolute offset, not relative. `idx += end` overshoots past valid JSON objects. Changed to `idx = end`.

## Medium-severity issues fixed

12. **subprocess.py no try/finally** — Child process orphaned on unexpected exceptions. Added try/finally with cleanup.
13. **venv.py duplicate `import shutil`** — Redundant local import removed.
14. **telemetry.py redundant `from collections import defaultdict`** — Inline import removed.
15. **behavioral_gate.py wrong phase** — Error message said "Phase 5" but docstring says Phase 6.
16. **populate_work_items.py missing `phase5` choice** — Users couldn't select phase5 via `--workflow`.
17. **dep_resolution.py local `import re`** — Moved to module level.
18. **subprocess_channel.py duplicated credential prefixes** — Derived regex from shared `CREDENTIAL_KEY_PREFIXES`.
19. **subprocess_channel.py double UTF-8 encode** — Computed `output_text.encode("utf-8")` twice.
20. **subprocess_channel.py lazy FAMILY_BY_PROVIDER import** — Moved to module-level imports.

## Fix

All 20 issues fixed in single pass. 1107 tests pass, 0 lint errors, 0 audit findings.

### Why this isn't the previous fix recurring

BC-200 fixed env leaks in specific call sites. BC-212 added config validation. BC-207 added structured logging. This review found a different class of issues: logic bugs (NameError, dead branches, wrong arg order, off-by-one), not missing safeguards. The systematic review approach (parallel deep-exploration of all modules) was the key difference — individual bug fixes catch symptoms; this review caught structural gaps.
