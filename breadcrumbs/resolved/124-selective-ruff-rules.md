---
number: "124"
title: "Selective ruff rule set for model output — relax non-critical rules"
severity: medium
status: resolved
kind: improvement
author: opencode-session-eval
date: "2026-05-12"
tags: [ruff, lint, gate, model-output, phase-3]
related: ["122", "123"]
---

## Problem

The inner gate runs `ruff check` with the full default rule set. Some rules are correctness-critical (F: Pyflakes — undefined names, unused imports). Others are stylistic (E: pycodestyle — line length, blank lines; I: isort — import ordering).

GR-015 logs show interface_architect and implementer artifacts failing primarily on stylistic rules (import ordering, blank lines between classes). The model then regenerates the entire artifact to fix these. This burns model budget on non-semantic issues.

## Proposed fix

Run inner-gate ruff with a reduced rule set focused on correctness:

```bash
ruff check --select E,W,F,I --ignore E501,E302,E305
```

Where:
- `E501` = line too long (model output often exceeds 88 chars; ruff format handles this)
- `E302` = expected 2 blank lines (stylistic)
- `E305` = expected 2 blank lines after class docstring (stylistic)

Keep:
- `F` rules (Pyflakes: undefined names, unused imports, syntax errors)
- `E9` rules (runtime errors: `SyntaxError`, `IndentationError`)
- `W` rules (warnings: invalid escape sequences, trailing whitespace)
- `I` rules (isort: import sorting is auto-fixable by `ruff check --fix`)

The outer gate can still run the full rule set as a stricter check, since outer gate failures are cheaper (no model invocation).

## Validation plan

1. Identify the most common ruff failure patterns from GR-015/016/017 telemetry
2. Adjust `_run_ruff_fast` in `pre_gate.py` to use the reduced rule set
3. Run a golden run and compare first-attempt pass rate
4. If the rate improves, keep the change; if not, the failures are F-rule shaped (real correctness issues)

## Affected files

- `src/factory/pre_gate.py` — `_run_ruff_fast`
- `src/factory/gate.py` — `_run_ruff` (outer gate, keep full ruleset)

## Phase placement

Phase 3. This is a gate configuration change with no prompt or model impact.

## Trade-offs

- **Pro:** Fewer retry cycles, faster pipeline
- **Con:** Accepts slightly less "polished" code. The principal may notice style inconsistencies in the final artifact. Mitigation: outer gate still checks full ruleset.
- **Con:** May mask real issues if model produces egregiously bad formatting. Mitigation: ruff format still runs.
