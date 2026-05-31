---
number: "232"
title: "GR-056/057/058 ran at 11–18 items vs GR-055's 50 — lock-rate recovery is unproven at scale (decomposer divergence)"
severity: medium
status: proposed
kind: defect
author: claude-opus (GR-058 review session)
date: "2026-05-31"
tags: [decomposer, golden-run, validation, phase-c, rfc-039]
related: ["227"]
---

## Symptom

The AC-BOOT-01 vacuity fixes (WS-1/2/3, BC-227) were validated across GR-056/057/058,
culminating in GR-058 **ALL PASS** (lock 79%, mean-attempts 2.00, unknown-gate 0%).
But every one of those runs decomposed the url-shortener `spec.yaml` into a **much
smaller work-item set than GR-055**:

| run | work items |
|---|---|
| GR-055 | 50 |
| GR-056 | 11 |
| GR-057 | 18 |
| GR-058 | 14 |

All used Form A (Phase C model decomposition) with `--decomposer-channel opencode
--decomposer-model …kimi-k2p6-turbo` (see the launch log in
`plans/2026-05-31-ac-boot-01-vacuity-gap.md`). So the "fixes work and the pipeline
is healthy" claim is well-proven, but **"lock-rate recovery (56% → 79%) holds at
GR-055 scale" is not** — the green runs are ~3–4× smaller, where a handful of items
swing the percentages and fewer failure paths are exercised.

## Open questions

1. Why does the kimi opencode decomposer produce a variable, much smaller
   decomposition (11/14/18) than whatever GR-055 used (50)? Candidates: a different
   decomposer model/channel in GR-055 (the exact GR-055 invocation was never
   recovered — see launch log caveat), nondeterminism in the Phase C decomposer, or
   a genuine deliverable-altitude difference (RFC-039 deliverable units are larger/
   fewer by design — in which case 50 was the anomaly, not 14).
2. Is the small decomposition *correct* (faithful deliverable decomposition of the
   spec) or *lossy* (dropping FRs/ACs)? If lossy, the green runs are passing because
   they're doing less work — a confound that would invalidate the recovery claim.

## Next step

Run a GR-055-scale comparison: either recover/identify GR-055's actual decomposer
and re-run with it, or run the existing kimi decomposition and verify the decomposed
item set covers all spec FRs/ACs (no loss). Confirm the lock-rate recovery and ALL
PASS hold at ~50 items before treating the BC-227 remediation as proven at scale.

## Why this isn't the previous fix recurring

N/A — first instance. This is a validation-completeness gap, not a recurrence; it is
the explicit remaining gate on closing BC-227 (whose own criterion requires a
055-scale confirmation).
