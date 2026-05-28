---
number: "RFC-008"
title: "Pipeline checkpoint and surgical resume system"
severity: medium
status: obsolete
kind: design
author: opencode
date: "2026-05-09"
tags: [rfc, runner, scheduler, stage-8, dep-v1-122]
related: ["003", "032", "058"]
---

## Summary

v2 currently has **runner idempotency on restart** (§9.12 / BC-003): if the runner crashes, it scans prior attempt directories for valid manifests and resumes from the highest valid attempt without re-invoking the channel. This is artifact-level resilience, not pipeline-level resilience.

What v2 lacks is a **checkpoint system** that captures the full pipeline state at stage boundaries, allowing:
- Resume after a runner/gate/scheduler process crash without re-scanning work item by work item
- Surgical retry of specific failed work-items without re-running the entire pipeline
- Preservation of successfully locked stages (e.g., all 15 interface_specs) while retrying only the downstream failures

v1's checkpoint system (BC-122) supports `--continue`, `--retry-failed=FR-04`, and granular per-phase checkpoints. Golden runs 004 and 005 take 30–50 minutes wall-clock. Losing that progress to a crash or a single bad config change is expensive.

## Proposed scope

1. **Checkpoint trigger points:**
   - Post-interface_spec lock (all interface_specs locked → checkpoint)
   - Post-test_suite lock (all test suites locked → checkpoint)
   - Post-implementation lock (all implementations locked → checkpoint)
2. **Checkpoint content:**
   - List of work-item IDs per stage and their current state
   - Successful artifact paths and hashes
   - Failure summaries for non-locked items
   - Config hash (to detect config drift between resume and original run)
3. **Resume modes:**
   - `--continue`: Resume from latest checkpoint; skip already-locked items
   - `--retry-failed=wi-id`: Reset specific work items to `new` and retry only them
   - `--retry-escalated`: Retry all `cannot_proceed` items (after prompt/config fixes)
4. **Storage:** A JSON/YAML file in `.factory/checkpoints/` keyed on workflow_name + workflow_version + timestamp, referenced by a "latest" symlink.

## Relationship to existing code

- `runner.py` already has `find_resumable_artifact()` and manifest scanning. A checkpoint layer would wrap this with a higher-level "what stage are we at?" query.
- `scheduler.py` already drives stage handoffs. It could write a checkpoint after each handoff batch completes.
- `FactoryConfig` could gain `checkpoint_root` and `checkpoint_interval` fields.

## Deferred decisions

- **Granularity:** Checkpoint per-work-item (fine-grained, large files) or per-stage (coarse-grained, simple)?
- **Retention:** How many checkpoints to keep? Rotate by count or age?
- **Cross-machine resume:** Checkpoints reference local filesystem paths. If the factory runs on different hosts, paths may not match.
- **Integration with regista:** Should checkpoint state also be stored as a regista work-item or event, or kept purely in local files?

## Phase needed

Phase 3 (fleet integration) or Phase 5 (first real workload). The value is highest when runs are long and expensive. Not needed for Phase 2's single-channel curated-fixture runs.

## Precedent

v1 BC-122: "Granular Checkpoint & Resume — Automatic checkpoints at post-skeleton, post-architect, post-attempt, post-merge. Resume interrupted phases or retry individual FRs without losing successful work."
