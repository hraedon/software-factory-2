---
number: "RFC-009"
title: "Interactive debugging inner loop — channel tool-use surface for implementer"
severity: high
status: deferred
kind: design
author: claude-opus-4-7
date: "2026-05-10"
tags: [runner, gate, stage-5, dep-v1-383]
related: ["075"]
---

## Problem

When the implementer model produces code that fails pytest with a logic bug (e.g., returning `leaf=None` instead of the correct value), the inner gate loop with mypy+ruff+pytest diagnostics can retry 2 times, feeding the prior failure output back to the model. But some bugs require the model to *interact* with its own code — run it, inspect intermediate state, form a hypothesis, try again. Re-invoking with diagnostics is a poor substitute for tool use.

## Evidence threshold

This RFC is deferred until the inner gate loop with pytest has been validated on at least 3 golden runs, and there exists a concrete failure class where:

1. The model fails pytest on 2+ inner gate retries, AND
2. The failure is not a type error or format issue (which mypy/ruff catch), AND
3. The failure is not a simple logic error visible from the AssertionError traceback (which the pytest diagnostic would convey), AND
4. The failure persists even after the model sees the full traceback as prior_failures.

Current evidence: one logic bug (`leaf=None` on FR-03 in cert-watch-mini). One data point is not enough to justify the architectural cost.

## Proposed design (when activated)

Extend the channel adapter to expose a Python runtime to the model during its invocation. The implementer would be able to `run_tests()` and `inspect(variable)` during a single invocation, rather than relying on the multi-invoke retry loop. This requires:

- Sandbox execution (container or WASM)
- Channel adapter protocol change (tool-use surface)
- Prompt contract change (teach the model about available tools)
- Security review (arbitrary code execution risk)

## Why deferred

The inner gate loop extension (BC-075 + pytest) is the smallest change that addresses the known failure class. Adding tool-use is a larger architectural shift that should only be built when evidence shows it's necessary. The v1 lesson ("don't build the whole architecture at once") applies here.