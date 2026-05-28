---
number: "207"
title: Broad except Exception blocks silently swallow errors in 16 locations
severity: medium
status: resolved
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

## Fix

Added structured logging to all silent-swallowing locations:

**Session 53 (partial):**
1. `scheduler.py:314` — `_downstream_has_field()`: bare `except Exception: pass` → now logs warning with exc_info
2. `pre_gate.py:667` — `ast.unparse()` fallback → now logs debug with exc_info
3. `pre_gate.py:888` — artifact read for feedback → now logs debug with exc_info
4. `context.py:578` — integration artifact JSON parse → now logs warning with exc_info
5. `gate/review.py:22` — review artifact file read → now logs debug with exc_info

**Session 54 (remaining):**
6. `gate/integration.py:117` — artifact read failure → now logs debug with exc_info
7. `gate/integration.py:169` — artifact write failure → now logs debug with exc_info

The following locations already logged properly and needed no change:
- `scheduler.py:118,127` (log.exception), `scheduler.py:299` (log.warning with exc_info=True)
- `runner.py:282` (log.exception)
- `jury_orchestrator.py:125` (log.exception)
- `heartbeat.py:82` (log.exception)
- `context.py:351` (logging.warning)
- `jury.py:150` (log.exception)

The remaining locations are acceptable:
- `gate/_subprocess.py` (4 instances): all return `GateResult` with error message — correct pattern for gate subprocesses
- `gate/integration.py:54`: unshare feature-detection probe — broad catch is appropriate for feature detection
- `state_reporter.py` (2 instances): dead module (BC-206), no production callers
