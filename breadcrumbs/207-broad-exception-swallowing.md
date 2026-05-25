---
number: "207"
title: Broad except Exception blocks silently swallow errors in 16 locations
severity: medium
status: proposed
kind: improvement
author: adversarial-review
date: "2026-05-25"
tags: [gate, runner, scheduler, telemetry, CLASS-001]
related: ["201"]
---

## Problem

16 bare `except Exception:` blocks across 12 files silently swallow errors without logging the exception type or traceback. The highest-risk locations:

- `scheduler.py` (4 instances): main loop body, work item claim, stuck-item detection, post-claim processing
- `gate/integration.py` (1 instance): integration gate execution
- `pre_gate.py` (2 instances): pre-gate execution, dependency resolution
- `jury_orchestrator.py` (1 instance): jury dispatch
- `runner.py` (1 instance): channel invocation fallback
- `inner_gate.py` (1 instance): gate export serialization

Many of these log a generic message and continue, losing the traceback and original exception type. This makes debugging failures significantly harder.

## Proposed fix

At minimum, replace all instances with:
```python
except Exception as exc:
    log.exception("descriptive_event_name", detail=...)
```

This preserves the `continue` behavior but adds full traceback visibility. For scheduler and integration gate blocks (highest risk), consider narrower exception types.
