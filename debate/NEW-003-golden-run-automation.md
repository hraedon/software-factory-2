---
number: "NEW-003"
title: "Golden run automation (`make golden-run`)"
author: deepseek-v4-pro
date: "2026-05-09"
related: ["008", "002"]
---

## Context

Golden runs are executed manually: `python populate_work_items.py` → `python -m factory.runner` → `python -m factory.report` → `python -m factory.telemetry`. The runbook is a markdown file. There is no Makefile target that chains these steps. Every golden run requires an agent or operator to remember the sequence and parameters.

## Problem

This works for Phase 2 (5 runs, all manual) but doesn't scale to Phase 3 (N channels × M config permutations × re-runs after prompt/fix changes). By Phase 4, the golden-run execution surface is unmanageable without automation.

## Position

**Add `make golden-run CONFIG=<config.yaml>` after GR006a.** Not before — the Phase 2 runs are one-offs that benefit from operator attention. After GR006a validates the pipeline shape, automation pays for itself.

## Proposed design

```makefile
# Makefile
golden-run:
    python populate_work_items.py --config $(CONFIG)
    python -m factory.runner --config $(CONFIG)
    python -m factory.report --config $(CONFIG)
    python -m factory.telemetry --config $(CONFIG)
    python -m factory.telemetry --verify --config $(CONFIG)
```

Chain the four commands with `&&` so any failure stops the run. The `telemetry --verify` step (Debate 002) gates the run on data quality before it's declared complete.

## Test to add

`test_golden_run_automation_smoke()` that runs `make golden-run CONFIG=test-golden-run-config.yaml` with a 2-item fixture and InMemorySubstrate, asserts exit code 0, asserts telemetry table has rows.

## Why this matters

- Phase 3 will re-run the Phase 2 workload on K2/GLM/DeepSeek/Gemini channels. That's 4+ re-runs of the same config. Manual execution for each is a waste of operator attention.
- Automation enforces the runbook: no one forgets `telemetry --verify` or runs steps out of order.
- The CI can run automated golden runs against InMemorySubstrate nightly, catching regressions before a human notices.

## Why defer until after GR006a

The current manual process works for 5 runs. GR006a is a calibration exercise that benefits from operator attention. Build automation when the number of expected golden runs exceeds the cost of building it — that's Phase 3.
