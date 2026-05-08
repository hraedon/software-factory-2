---
number: "054"
title: "No PipelineRuntime namespace — live objects mix with serializable state (v1 BC-361 pattern)"
severity: high
status: proposed
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [runner, state, dep-v1-361]
related: []
---

## Problem

v1's BC-361: live Python objects (`ObserverBus`, `PipelineContext`) were stored in the `state` dict under `_`-prefixed keys, stripped before YAML serialization by naming convention. This implicit separation meant any code iterating `state.items()` encountered live objects unexpectedly, and the convention was uncontracted.

Current v2 state: the runner passes `config`, `channel`, `sub` (Substrate handle), and `spec_content` as function parameters through `process_work_item`, `_handle_invoke_failure`, `_resume_and_submit`, etc. This works for Phase 2 single-channel mode but is already showing strain — `_resume_and_submit` takes 8 positional+keyword args, `process_work_item` takes 10. Each new concern (failure summaries, telemetry reporters, observer hooks) will either bloat the parameter list or get smuggled into some state-carrying structure.

v1's lesson: separate serializable state from runtime live-object context *at the type level* from day one. v2 does not yet have this.

## Fix

Introduce a `PipelineRuntime` dataclass (or equivalent) to carry live objects: `sub`, `config`, `channel`, `spec_content`, `actor_id`, and any future observers/hooks. Methods take `runtime: PipelineRuntime` plus work-item-specific args. Serializable state stays in substrate's custom_fields.

This is a low-risk refactor affecting only the function signatures in `runner.py`, `gate_process.py`, and `scheduler.py`. Do it now before Phase 3 adds more parameters.
