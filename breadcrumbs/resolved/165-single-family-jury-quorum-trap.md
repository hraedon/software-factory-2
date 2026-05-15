---
number: "165"
title: "Single-family jury with quorum=2 produces systematic disagreement — same model contradicts itself"
severity: medium
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [jury, golden-run, stage-7]
related: []
---

## Summary

When `frontier_judge` has two jurors on the same model (K2-only config, `jury_quorum=2`), the same model invoked twice with identical prompts yields divergent outputs systematically. In GR-029's third launch attempt, this triggered the `gate_fail_jury` guardrail at ≥3 occurrences, aborting the run.

This is stochastic behavior from non-deterministic model output, but it's a trap for config authors: the `jury_quorum` field defaults to 2 in `FactoryConfig.phase5()` but single-family configurations will always hit the disagreement path. The config YAML doesn't validate this.

## Evidence

GR-029: "When both frontier_judge jurors use the same K2 model, jury_quorum=2 produces systematic disagreement (the same model invoked twice with identical prompts yields divergent outputs). This triggered the gate_fail_jury guardrail at ≥3 occurrences, aborting the run. Setting jury_quorum=1 resolved this but means the disagreement path is unexercised."

GR-027 avoided this because it had dual-family jury (K2 + DeepSeek) with `jury_quorum=2`, which worked — the two models produced different enough outputs to agree more often than disagree.

## Impact

- Single-family jury configurations are effectively restricted to `jury_quorum=1`, which means the jury_disagree path cannot be exercised in single-family setups.
- Config authors may not realize this trap — `FactoryConfig.phase5()` defaults to `jury_quorum=2`, but K2-only configs will always fail.
- The `gate_fail_jury` guardrail in `agent_golden_run.py` kills the run on ≥3 occurrences, making this a hard failure rather than a soft one.

## Fix

Two options:
1. **Config validation** — Validate that `jury_quorum <= number_of_distinct_families` (or `<= number_of_distinct_models`).
2. **Same-model jury deduplication** — When all jurors use the same model, set implicit `quorum=1` since a single model's repeated invocation doesn't provide independent judgment.
