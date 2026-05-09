---
number: "004"
title: "Pipeline checkpoints — preserve progress across 30–50 minute golden runs"
author: opencode
date: "2026-05-09"
related: ["RFC-008", "BC-003", "BC-046"]
---

## Context

v2 has artifact-level resilience: if the runner crashes, it scans prior attempt directories for valid manifests and resumes from the highest valid attempt without re-invoking the channel (§9.12 / BC-003). This is per-work-item resilience, not pipeline-level resilience.

Golden runs 004 and 005 take 30–50 minutes wall-clock. A crash, config change, or runner restart loses all in-flight progress. There is no way to:
- Resume a partially completed pipeline (12/15 implementations done, 3 in progress)
- Retry only the failed/escalated items without re-running successes
- Preserve checkpoint state across host restarts

v1's checkpoint system (BC-122) supports `--continue`, `--retry-failed=FR-04`, and granular per-phase checkpoints. v2 has no equivalent.

## Problem

As v2 moves to Phase 3 (fleet integration) and Phase 5 (first real workload), runs will get longer, not shorter. Multi-channel runs may involve sequential fallback chains (Claude → GLM → K2) that compound wall-clock time. Without checkpoints, a single failure at hour 4 of an 8-hour run loses everything.

## Position

**Implement a lightweight checkpoint system before Phase 3 fleet work begins.** Not the full v1 granularity, but enough to preserve stage-level progress.

### Minimum viable checkpoint

1. **Trigger points:**
   - All `interface_spec` items locked → checkpoint
   - All `test_suite` items locked → checkpoint
   - All `implementation` items locked → checkpoint

2. **Checkpoint content (JSON):**
   ```json
   {
     "workflow_name": "sf2",
     "workflow_version": 2,
     "config_hash": "sha256-of-config-yaml",
     "timestamp": "2026-05-09T12:00:00Z",
     "stages": {
       "interface_spec": {"locked": ["uuid1", "uuid2"], "escalated": ["uuid3"]},
       "test_suite": {"locked": ["uuid4"], "in_progress": ["uuid5"]},
       "implementation": {"locked": [], "in_progress": ["uuid6"]}
     }
   }
   ```

3. **Resume modes:**
   - `--continue`: Load latest checkpoint; skip already-locked items; resume in_progress items from manifest scan (existing BC-003 logic)
   - `--retry-escalated`: Reset all escalated items to `new` and retry
   - `--retry-failed=wi-id`: Reset specific item to `new`

4. **Storage:** `.factory/checkpoints/<workflow_name>-<workflow_version>-<timestamp>.json` with a `latest` symlink.

### Why not full per-work-item checkpointing

v1's checkpoint system is heavy (test architecture preservation, budget tracking, surgical FR redo). v2 doesn't need that yet. Stage-level checkpointing is ~100 lines of code and provides 80% of the value.

### Relationship to BC-003

BC-003 (runner idempotency on restart) handles the per-work-item resume. The checkpoint system is a higher-level wrapper that tells the runner *which* work-items to resume, not just *how* to resume one.

## Risks

| Risk | Mitigation |
|---|---|
| Checkpoints reference local filesystem paths that may not exist after restart | Store relative paths from workspace_root; validate on resume |
| Config changes between checkpoint and resume invalidate state | Include `config_hash`; refuse resume if config changed |
| Multiple concurrent checkpoint writes race | Write to temp file, atomic rename; only runner writes checkpoints |

## Blocking

Phase 3 (fleet integration) and Phase 5 (first real workload). Acceptable delay: 1 session.

## Next step

1. Add `checkpoint.py` with `write_checkpoint()`, `load_latest_checkpoint()`, `resume_from_checkpoint()`
2. Wire into `scheduler.py` after each stage handoff batch completes
3. Add `--continue` flag to runner `_main(argv)`
4. Add 2 integration tests: resume after crash, retry-escalated after checkpoint
5. Resolve RFC-008
