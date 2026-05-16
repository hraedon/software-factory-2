---
number: "RFC-029"
title: "Attempt-count telemetry bucketing — separate prompt calibration from gate-difficulty tail"
severity: medium
status: proposed
kind: design
author: claude-opus-4-7
date: "2026-05-16"
tags: [telemetry, gate, inner-gate, observability, rfc]
related: ["adversarial-readiness-001", "RFC-011", "CLASS-005", "GR-034"]
---

## Problem

GR-034 reported a 95% first-attempt mechanical-gate pass rate, 100% integration lock (2/2), and a 73% inner-gate first-pass rate on implementations (1/3). The run log itself concedes that the `inner_gate_retries=3` change — not prompt improvements — was the load-bearing piece: the `fr02_tls_scan` artifact failed inner mypy on attempt 0, inner pytest on attempt 1, and passed both on attempt 2.

The active debate (`debate/adversarial-readiness-001`) argues this means current telemetry conflates two distinct signals into one aggregate inner-gate first-pass rate:

1. **Prompt calibration quality** — how often the implementer produces a correct artifact on first try for a *typical* item.
2. **Gate-difficulty tail** — how many retries a genuinely-hard item needs to converge, independent of prompt quality.

Across GR-030–GR-034, the same `fr02_tls_scan` item required three sequential fix iterations, each failing a *different* gate (mypy → pytest → both). This is not a repeated prompt regression; it is one hard item (Python 3.12 `_ssl.Certificate` runtime-vs-stub divergence) being averaged into the same metric as straightforward items that pass on attempt 0.

The result: a single number that cannot answer "is the implementer prompt under-calibrated, or are we just hitting a known-hard tail?"

## Proposal

Add per-attempt-count bucketing to `telemetry.py`. The data already exists — `SubmitPayload.inner_gate_attempts` (see `src/factory/event_schemas.py:28`) carries the full attempt history per submit. The change is aggregation, not collection.

New metric fields on the inner-gate telemetry summary:

```
inner_gate_attempt_0_pass_rate       # items that passed both inner gates on first eval
inner_gate_attempt_1_recovery_rate   # items that failed attempt 0, passed by attempt 1
inner_gate_attempt_2plus_rate        # items that needed ≥2 retries to converge
inner_gate_exhausted_budget_rate     # items that never passed within retries
```

Reported alongside the existing aggregate `inner_gate_first_pass_rate` (kept for continuity), with a one-line interpretation:

- **High attempt-1 recovery (e.g., >15%)** ⇒ prompt under-calibrated; the implementer is producing fixable-but-wrong artifacts. Investigate prompt rules.
- **Low attempt-1 recovery + nonzero attempt-2plus** ⇒ prompt is adequate; failures cluster on a hard tail. Look at *which items* (per-item attempt log), not the prompt.
- **Nonzero exhausted-budget rate** ⇒ neither prompt nor retries are converging; escalate to RFC-011 (unified gate evaluation) or per-item investigation.

Add a per-item attempt log to the run summary (already implicit in the data) so a hard-tail diagnosis can name names.

## Scope

Pure telemetry. No runner changes, no behavior changes. New aggregations in `telemetry.py` (`src/factory/telemetry.py:82-192`), surfaced in the existing summary formatter. Backfillable by replaying historical `SubmitPayload`s — should produce attempt-count buckets for GR-021 onward (when `inner_gate_attempts` started being recorded per BC-133).

## Validation experiment

Independent of this RFC, a single A/B run pair settles the underlying debate:

- 2 GRs at `inner_gate_retries=1`, same fixture (cert-watch-mini).
- 2 GRs at `inner_gate_retries=3`, same fixture.
- Compare lock rates and per-attempt buckets.

If retries=1 lock rate is materially lower (e.g., <80%) and the attempt-1 recovery bucket dominates, retries are *masking* a weak prompt. If retries=1 lock rate stays near 90% and only specific items (e.g., `fr02_tls_scan`) miss, retries are *compensating for a known hard tail* — which is fine and expected.

This experiment is cheap (4 short runs) and does not require this RFC to land first.

## Phase needed

Phase 5 in-flight. Bucketing is a small addition to existing telemetry and can land alongside any Phase 5 GR. The validation A/B can run independently.

## Risks

- **Bucket noise on small samples.** Phase 5 fixtures have 3 implementations per run; one item moving between buckets swings the rate by 33%. Mitigation: report raw counts alongside rates, and aggregate across N runs in the rolling summary.
- **Interpretation drift.** Without the explicit "prompt vs. hard-tail" framing in the run summary, future readers may treat attempt-1-recovery as a goal to minimize rather than a signal to investigate. The summary text matters as much as the numbers.
- **Doesn't resolve the underlying spec question.** Even with bucketing, no RFC currently states an *expected* attempt-0 pass rate for the implementer role. RFC-016 (defect-class taxonomy) and spec.md §3.11 (three-layer metrics) get close but stop at the aggregate. A follow-up to spec.md §3.11 should set a target attempt-0 floor (e.g., ≥85%) so the new buckets have a contract to fail against.
