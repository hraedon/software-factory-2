---
number: "054"
title: "No PipelineRuntime namespace — live objects mix with serializable state (v1 BC-361 pattern)"
severity: high
status: implemented
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [runner, state, dep-v1-361]
related: []
---

## Problem

v1's BC-361: live Python objects (`ObserverBus`, `PipelineContext`) were stored in the `state` dict under `_`-prefixed keys, stripped before YAML serialization by naming convention. This implicit separation meant any code iterating `state.items()` encountered live objects unexpectedly, and the convention was uncontracted.

Current v2 state: the runner passes `config`, `channel`, `sub` (Regista handle), and `spec_content` as function parameters through `process_work_item`, `_handle_invoke_failure`, `_resume_and_submit`, etc. This works for Phase 2 single-channel mode but is already showing strain — `_resume_and_submit` takes 8 positional+keyword args, `process_work_item` takes 10. Each new concern (failure summaries, telemetry reporters, observer hooks) will either bloat the parameter list or get smuggled into some state-carrying structure.

v1's lesson: separate serializable state from runtime live-object context *at the type level* from day one. v2 does not yet have this.

## Fix

Introduced `PipelineRuntime` frozen dataclass in `src/factory/runtime.py` carrying live objects: `sub`, `config`, `spec_content`, `channel`. Methods now take `runtime: PipelineRuntime` plus work-item-specific args.

Affected modules refactored:
- `runner.py`: `process_work_item`, `worker_loop`, `_derive_role_context` now take `PipelineRuntime`; `run_worker` constructs it.
- `gate_process.py`: `process_gate_item`, `gate_loop` now take `PipelineRuntime`; `run_gate` constructs it.
- `scheduler.py`: `_ensure_downstream_item`, `scheduler_loop` now take `PipelineRuntime`; `run_scheduler` constructs it.

All 256 tests updated to construct `PipelineRuntime` at call sites. Zero test regressions.
