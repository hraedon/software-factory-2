---
number: "209"
title: "No real workload validation — all 39 golden runs use synthetic cert-watch fixtures"
severity: high
status: proposed
kind: design
author: adversarial-review
date: "2026-05-25"
tags: [phase-6, validation, workload]
related: ["RFC-023", "RFC-010"]
---

## Problem

The entire pipeline architecture is validated on synthetic `cert-watch-mini` and `cert-watch` fixtures. All 39 golden runs (GR-001 through GR-039) use these purpose-built workloads. The spec acknowledges this: "A real line-of-business workload has not yet been attempted" (spec §8.8).

This means:
- The decomposer has never processed a messy, real-world spec
- Integration gates have never assembled software with real dependency complexity
- Outcome verification has never produced a verdict on software someone would actually use
- The 88-91% lock rates may not generalize beyond the cert-watch pattern

## Impact

Without real workload validation, the pipeline's effectiveness is unknown. The Phase 6 exit criteria require "second and third workloads (not cert-watch), with patterns extracted into reusable role templates" (spec §10). This is the single highest-value gap in the project.

## Proposed fix

Run the pipeline on 2-3 real, non-trivial workloads:
1. A CLI tool (e.g., a log parser, a file converter)
2. A web service (e.g., a simple REST API)
3. A library module (e.g., a data validation library)

Each should have 5-10 work items with cross-module dependencies. Document which stages succeed, which fail, and why. Use the results to update the tier table, gate budget, and role prompts.

## Progress

**GR-040 (2026-05-26):** Phase A baseline on log-redact-cli (5 FRs). 96% lock rate (45/47). 2 integration failures from cross-module type incompatibility — expected Phase A limitation.

**GR-043 (2026-05-28):** Phase B with MiMo-V2.5-Pro decomposer on log-redact-cli. 97% lock rate (33/34). MiMo produced semantic module names (`rule_loader`, `log_reader`, `redaction_engine`, `output_emitter`); K2 could not (GR-041). 1 transient channel_fail on integration (unrelated to decomposition).

**Remaining:** dep-graph-viewer workload (4 FRs) not yet run. Need N=2 workloads for Phase 6 exit. Web-service archetype deferred to Phase 6.2.
