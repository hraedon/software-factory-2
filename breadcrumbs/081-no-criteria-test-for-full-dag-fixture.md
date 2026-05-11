---
number: "081"
title: "No criteria test for cert-watch full DAG — structural gap in regression detection for multi-module pipelines"
severity: medium
status: proposed
kind: bug
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [test, gate, dep_resolution, stage-5]
related: ["077", "076", "078"]
---

## Problem

The codebase has 376 tests but the only criteria test that gates Phase 2 exit (`test_gr006a_criteria.py`) is:
1. `@pytest.mark.skip` when golden run artifacts aren't on disk (i.e., rarely runs)
2. Configured for the 3-spec cert-watch-mini fixture, not the 8-spec full-DAG cert-watch fixture

The cert-watch full DAG fixture (8 specs, 3 diamond consumers, non-FR library module, multi-hop chains) has **no corresponding criteria test**. This means:
- The most architecturally complete fixture has no automated regression gate.
- Problems in the full DAG (e.g., GR012's root-cause: topological ordering of interface_specs) only surface during expensive, manual golden runs.
- The gate tests in `test_gate_implementation_subprocess.py` use isolated `tmp_path` directories with matching import names — they don't exercise the cross-work-item, cross-attempt-directory resolution that fails in the real pipeline.

## Impact

There is a self-reinforcing gap:
1. Criteria tests require a full golden run (expensive, model budget)
2. So they're rarely executed (skip markers, manual setup)
3. So cross-module dependency resolution bugs surface late (GR012)
4. So Phase 2 exit criteria data is stale

## Proposed fix

1. Create a criteria test file `test_cert_watch_full_criteria.py` covering:
   - Interface spec lock rate on full DAG (8 specs)
   - Test suite lock rate (with cross-module imports)
   - Implementation lock rate (with real runtime dependency resolution)
   - No `ModuleNotFoundError` in any gate output
   - Telemetry verify passes
2. Define a `make golden-run-full-dag` target that runs the full fixture end-to-end and records artifacts.
3. Wire the criteria test into `make check` with a skip-when-absent marker, so it gates CI when artifacts are available.
4. Resolve BC-077 (topological ordering) first, as it is a prerequisite for the full DAG to run at all.
