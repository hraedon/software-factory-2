# GR-059 — Web-service pipeline with K2 decomposer (Phase C); partial DAG, integration not reached

**Date:** 2026-06-02
**Config:** golden-run-059-config.yaml (archetype=web-service, K2 decomposer, 3-member jury: K2 + GLM-5.1 + MiMo)
**Fixture:** url-shortener (spec.yaml, Phase C decomposer — K2 kimi-k2p6-turbo)
**Workflow version:** 5 (full pipeline)

## Purpose

Validate the full 7-stage web-service pipeline after the WS-1/WS-2/WS-3 fixes from GR-056–058. Test whether the integrator can compose multiple HTTP modules into a single walking-skeleton app and whether the conformance gate correctly validates the assembled artifact.

## Result summary

| Metric | Value | Target | Pass? |
|---|---|---|---|
| Total work items | 18 | — | — |
| Locked | 13 (72%) | ≥90% | NEAR-MISS |
| Cannot proceed | 5 | — | — |
| Stuck items | 0 | ≤1/16 | PASS |
| Mean attempts | 2.39 | ≤2.0 | FAIL |
| First gate-eval pass rate | 72% (13/18) | ≥60% | PASS |
| Inner gate first-pass rate | 67% (12/18) | ≥60% | PASS |
| Unknown gate rate | 0% | <1% | PASS |
| Deterministic gate rate | 100% (43/43) | ≥80% | PASS |
| Telemetry verify | False (3 unmatched) | True | FAIL |
| Full DAG reached? | **NO** (stalled at review) | — | ❌ |

**Overall: SOME FAIL** — pipeline progresses through interface/test/implementation stages but cannot reach integration/outcome_verification.

## Per-stage detail

### Interface architect (5 items)

| Item | Result | Attempts | Notes |
|---|---|---|---|
| fr01 | **Locked** | 1 | K2 produced spec |
| fr02 | **Locked** | 2 | First attempt: inner_pytest retry (import error); second attempt: passed |
| fr03 | **Locked** | 1 | |
| fr04 | **Locked** | 1 | |
| fr05 | **Locked** | 2 | First attempt: mypy retry |

### Test author (5 items)

All 5 **Locked** on first attempt (100% pass rate).

### Implementer (5 items)

| Item | Result | Attempts | Notes |
|---|---|---|---|
| 3 items | **Locked** | 1–2 | Normal pass |
| 2 items | **Cannot proceed** | 3 | mypy failures: private symbol imports (`_DB`, `_ensure_db`). Same root cause as GR-051/052 — upstream revision context gap. |

### Review (3 items)

All 3 **Cannot proceed** — upstream implementations died, no locked implementation to review.

### Jury, Integration, Outcome verification

**None reached** — DAG stalled before jury items could be created.

## Failure analysis

### 1. Implementation mypy failures (2 items) — same root cause as GR-051

Models tried to import private symbols (`_DB`, `_ensure_db`) from dependency module stubs. The dependency resolution provides the interface `.pyi` stub but not the implementation, so private symbols are inaccessible. This is the same class of issue seen in GR-051 (item #2 in "Bugs discovered").

**Status:** Known issue. The decomposer produces substrate modules with private implementation details that downstream modules reference. Fix options: (A) make substrate exports public in the interface spec; (B) make the interface spec explicitly state which symbols are exported; (C) have the gate allow private access to implementation details.

### 2. Channel invoke failures (3 items) — model instability

Three review items failed with `channel_invoke_failed` (`Non-zero exit code` from opencode). These are transient model instability issues where the opencode channel returned a non-zero exit code without producing output.

**Status:** Known issue (BC-135 class). The pipeline correctly escalates these to `cannot_proceed` after exhausting the attempt budget.

### 3. Review items blocked (3 items) — downstream of implementation failure

All 3 review items were assigned to implementations that had already died. The scheduler correctly created upstream revisions, but the review items had no valid locked implementation to review.

**Status:** Expected cascade — not a bug.

### 4. Decomposer produced FR-based names (fr01–fr05) — not module names

The K2 decomposer generated 5 modules named `fr01` through `fr05` instead of semantic names like `link_creator`, `link_store`, etc. This is a known decomposer variance (same pattern in GR-058). The module names don't affect pipeline correctness but make post-run forensics harder.

**Status:** Cosmetic. MiMo-V2.5-Pro produces semantic names; K2 uses FR-based names. The pipeline handles both.

## Telemetry integrity

- unknown_gate_name_count: 0
- orphan_submit_count: 0
- unmatched_gate_count: 3 (review items with dead upstream implementations)
- confounding_warning_count: 0
- verify_passed: False (unmatched_gate_count > 0)

## Conformance gate

The conformance gate was **not exercised** in this run because no items reached the integration or outcome_verification stages. The YAML parse bug from GR-051 is confirmed fixed (tested in unit tests and GR-052), and the `uv pip install` fix from GR-056 is in place.

## Artifacts preserved

- Workspace: `/tmp/sf2-golden-059/` (preserved with --no-cleanup)
- Logs: `.factory/logs/gr059test/`

## Lessons and next steps

1. **Integration/outcome stages remain unvalidated.** GR-059 did not reach the integration composition stage because implementation failures starved downstream items. To validate the walking-skeleton model (GR-054's identified next step), the pipeline must produce locked implementations for enough modules to create integration items.

2. **Implementation mypy failures are the recurring blocker.** Private symbol imports from dependency stubs account for 2/5 cannot_proceed items across multiple GRs. A targeted fix would be to make the decomposer ensure that substrate modules expose all used symbols as public interfaces in the `.pyi` stub.

3. **Channel stability remains intermittent.** 3/5 cannot_proceed items are channel failures. This is within expected variance for the opencode channel with K2.

4. **Next concrete step: GR-060.** Either (A) use MiMo decomposer (which produces semantic module names and has a better track record) or (B) pre-decompose the url-shortener fixture manually to ensure all modules have locked implementations, then validate the integration + outcome stages.