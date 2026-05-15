---
number: "166"
title: "Interface architect inner_pytest first-pass rate dropped from 50% (GR-027) to 38% (GR-029) — retrogression with no investigation"
severity: medium
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [golden-run, inner-gate, retrogression]
related: []
---

## Summary

The interface_architect role's inner gate first-pass rate on `inner_pytest` (import smoke check) dropped from 50% (4/8, GR-027) to 38% (3/8, GR-029). This is a ~12 percentage point regression with no apparent cause investigation in the golden run log.

Both runs used the same config (K2-only interface_architect, cert-watch fixture). The GR-027 log notes this as "50% first-pass" and the GR-029 "lessons" section mentions "The prompt may need stronger guidance on import resolution" but doesn't investigate why a K2-only run with the same prompt and fixture regressed.

## Evidence

- GR-027: "interface_architect: inner_pytest — 8 items, 50% first-pass, 100% overall"
- GR-029: "Interface specs: 8/8 locked. Inner gate first-pass: 3/8 (38%) — 5 items required retry on inner_pytest (import smoke check)."

The same rate for test_author was consistent (GR-027: 100%, GR-029: 71% but that's a different role with different tests). For interface_architect the regression is specific and unexplained.

## Impact

- Every retry costs ~60s of model time (mean duration from GR-027: 61.9s per interface_architect invocation). The extra 1 retry across 5 items = ~300s of wasted budget.
- If this regression is systematic (prompt drift, model behavior change, or fixture issue), it will continue to degrade Phase 5 runs.
- Without investigation, the regression may deepen or a future fix may accidentally target the wrong cause.

## Fix

Compare the GR-027 and GR-029 artifacts (workspace backups) to see what changed between the two runs. Specific questions:
1. Did the fixture change between runs?
2. Did the prompt change between runs?
3. Is this stochastic noise (expected variance for K2)?

## Resolution

Closed as stochastic noise. 50% (4/8, GR-027) vs 38% (3/8, GR-029) is a difference of 1 item, consistent with expected K2 variance on import smoke checks. No fixture or prompt change between runs.
