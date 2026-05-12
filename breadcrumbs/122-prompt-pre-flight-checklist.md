---
number: "122"
title: "Prompt pre-flight checklist to improve first-attempt pass rate"
severity: high
status: proposed
kind: improvement
author: opencode-session-eval
date: "2026-05-12"
tags: [prompt, first-attempt, inner-gate, phase-3, phase-4]
related: ["075", "RFC-013"]
---

## Problem

GR-015 telemetry shows 0% first-attempt pass rate across all three roles:
- interface_architect: 8/8 interface_specs required inner-gate retry (ruff lint errors)
- test_author: 8/8 test_suites required inner-gate retry (pytest collect or assertion failures)
- implementer: 8/8 implementations required inner-gate retry (mypy/ruff failures)

Overall pass rate is 100% (all artifacts pass on retry=1 or retry=2), but every work item burns 2-3 model invocations where 1 should suffice. At current pace (~100s per invocation), this adds ~3-5 minutes per work item.

## Root cause analysis

The role prompts describe what to produce and mention the gate checks abstractly, but they do not teach the model to simulate the checks before returning output. The model generates semantically-correct code that fails syntactic/tooling checks it cannot "see."

Examples from GR-015 logs:
- interface_architect: `ruff check reported errors` on first attempt (import ordering, blank lines)
- test_author: `pytest --collect-only` fails (import errors, bad test structure)
- implementer: `mypy` or `ruff` failures

## Proposed fix

Add a "Pre-flight verification" checklist to the end of each role prompt. This is a pure prompt-engineering change with no code impact.

**interface_architect prompt addition:**
```markdown
## Pre-flight verification
Before returning your `.pyi`, verify:
1. [ ] The file parses as valid Python
2. [ ] Every function/class body is `...` or a docstring (no implementation)
3. [ ] Imports are sorted: `__future__`, stdlib, third-party
4. [ ] No unused imports
5. [ ] Two blank lines between top-level definitions
6. [ ] Every public symbol has a docstring referencing its AC IDs
```

**test_author prompt addition:**
```markdown
## Pre-flight verification
Before returning your test file, verify:
1. [ ] `pytest --collect-only` would succeed (all imports resolve)
2. [ ] Every test function name starts with `test_`
3. [ ] No imports from modules other than `interface` and declared dependencies
4. [ ] Every `ac_ids` value is covered by at least one test
```

**implementer prompt addition:**
```markdown
## Pre-flight verification
Before returning your implementation, verify:
1. [ ] `mypy --strict` would pass (every function has a concrete return)
2. [ ] `pytest` would pass against the provided test suite
3. [ ] `ruff check` would pass (no unused imports, no bad naming)
4. [ ] Every function signature matches the `.pyi` contract exactly
```

## Validation plan

1. Update all three prompt templates
2. Run a quick golden run (GR-019) on cert-watch-mini or a 2-item subset
3. Measure first-attempt pass rate before/after
4. If first-attempt rate improves to >30%, the fix is prompt-shaped (proceed)
5. If it stays at 0%, the problem is model-shaped (need Phase 4 mechanisms: self-critique, race)

## Affected files

- `src/factory/prompts/interface_architect.md`
- `src/factory/prompts/test_author.md`
- `src/factory/prompts/implementer.md`

## Phase placement

Phase 3. This is a lightweight prompt fix that improves throughput before Phase 4 jury/race work begins. If it fails, the breadcrumb is still valuable as evidence that the models cannot self-check, justifying the Phase 4 investment in multi-model critique.
