# Phase 6 Readiness Audit

Date: 2026-05-22
Auditor: claude (Session 42)
Status: Phase 5 complete at GR-038; Phase 6 prerequisites assessed

## Summary

Phase 5 is substantively complete (all exit criteria met or near-miss accepted at GR-038).
Phase 6 = first real workload + generalization. This audit assesses which prerequisites are
done and what remains before a real workload can be attempted.

## Phase 5 Prerequisite RFCs — ALL COMPLETE

| RFC | Title | Status | Module | Tests |
|---|---|---|---|---|
| RFC-017 | Operational survivability | implemented | `src/factory/ops/` (4 modules) | 22 |
| RFC-019 | Artifact bundling | implemented | `src/factory/bundler.py` | 13 |
| RFC-020 | Archetype catalog | implemented | `src/factory/catalog.py` + `catalog/` | — |
| RFC-021 | Spec mutation/invalidation | implemented | `src/factory/spec_hash.py` | — |

## Phase 6 Prerequisites — STATUS

### Must-have for first real workload

| RFC | Title | Status | Gap | Effort |
|---|---|---|---|---|
| RFC-023 | Decomposer role | **proposed** | "Single largest architectural gap." Stage 1 has zero implementation. Pipeline currently consumes pre-authored fixture YAMLs via `populate_work_items.py`. Without this, pipeline cannot consume arbitrary specs. | High |
| RFC-026 | Principal review surface | **proposed** | No artifact summary format, no feedback intake mechanism. `report.py` hardcodes workflow_version=1 (BC-045). Telemetry produces per-role tables but no per-work-item artifact summary. | Medium |
| RFC-022 | Initiative primitive | **proposed** | Per-item monitoring is viable for cert-watch-mini (5 items) but noisy for real workloads (20+ items). No bundling or operational grouping exists. Phase A is factory-only (zero substrate work). | Low |

### Should-have for first real workload

| RFC | Title | Status | Gap | Effort |
|---|---|---|---|---|
| RFC-024 | Coherence reviewer | **proposed** | Declared in spec and `full_pipeline.yaml` but zero design or implementation. If used with `full_pipeline.yaml`, runtime failure expected. | Medium |
| RFC-027 | Test efficacy | **proposed** | No mechanical verification that tests actually validate behavior. Mutation testing gates not implemented. | High |
| RFC-028 | Per-role capability map | **proposed** | 5-point registration could be collapsed, but not blocking. | Low |

### Deferred (later phases)

| RFC | Title | Status | Phase Needed |
|---|---|---|---|
| RFC-002 | Critical observer degradation | proposed | Phase 3 |
| RFC-003 | Channel adapter auth detection | proposed | Phase 3 |
| RFC-007 | Test efficacy scoring | proposed | Phase 4-5 |
| RFC-009 | Interactive debugging inner loop | proposed | Phase 5+ |
| RFC-010 | Fixture taxonomy | proposed | Phase 2 exit |
| RFC-034 | Capture model identity in telemetry | proposed | Phase 3 |
| RFC-035 | Data-driven channel placement | proposed | Phase 3 |

### In-flight meta-defenses (implemented as practices, not code)

| RFC | Title | Status |
|---|---|---|
| RFC-030 | Class promotion must produce invariant | Active practice; CLASS-005/008 stabilized by RFC-011 |
| RFC-031 | Fix-family root-cause requirement | Active practice |
| RFC-032 | Breadcrumb-velocity circuit breaker | Active practice |
| RFC-033 | Guardrail lifecycle tagging | Implemented in code (tier tags on all gates) |
| RFC-037 | Detect-enforce-retire tiering | Lead example BC-194 implemented |

## Spec §10 Phase 6 Work Items

From `spec.md` lines 369-379:

| Item | Description | Status |
|---|---|---|
| Second and third workloads | Not cert-watch; patterns into reusable templates | Not started |
| v1 backlog decision | Whether v2 can attempt v1 backlog items | Not started |
| Machine-readable spec sidecar | `spec.yaml` from socratic-specification | Not started |
| coherence_reviewer role | Holistic long-context review (Gemini) | RFC-024 filed |
| Spec ambiguity resolver | Structured escalation to principal | Not started |
| Race (parallel execution) | Same role on two channels; first pass wins | Not started |

## Infrastructure Quality Gate

| Metric | Value | Target |
|---|---|---|
| Test count | 1040 | — |
| Lint errors | 0 | 0 |
| Open critical BCs | 0 | 0 |
| Open high BCs | 0 | 0 |
| Subprocess call sites via wrapper | 29/29 (100%) | 100% |
| Active defect classes (unstable) | 5 | — |
| Stabilized defect classes | 2 (CLASS-005, CLASS-008) | — |
| Validated channels | opencode, claude-code | — |
| Disabled channels | gemini-cli | — |

## Concrete "What Remains for First Real Workload" List

### Hard blockers (must complete before any real workload)

1. **RFC-023 (decomposer):** The pipeline cannot consume an arbitrary spec. `populate_work_items.py` reads hand-curated fixture YAMLs. A real workload requires model-driven spec decomposition into work items with dependency DAG. This is the single highest-priority item.

2. **RFC-026 (principal review surface):** The principal needs to receive and review pipeline output. Without this, there is no human gate. RFC-019 provides the bundling mechanism; RFC-026 provides the review intake.

### Strong recommendations (should complete before first real workload)

3. **RFC-022 (initiative primitive):** Real workloads will produce 20+ items; per-item monitoring is noisy. Initiative bundling provides operational grouping. Low effort (Phase A is factory-only, uses custom_fields).

4. **BC-045 (report.py workflow_version=1):** Report is stale; must be fixed before principal can receive meaningful output.

5. **Integration gate namespace validation in golden run:** BC-195 is implemented in code but not yet validated in a full golden run. GR-039 is in progress to confirm.

### Nice-to-have (can defer to post-first-workload iteration)

6. **RFC-024 (coherence reviewer):** Valuable but not blocking for first workload. Can run without holistic review.

7. **RFC-027 (test efficacy):** Mutation testing would improve confidence in generated tests, but the existing inner-gate pytest collect + assertion count checks provide a baseline.

8. **Race (parallel execution):** Not needed for first real workload. Single-channel execution is sufficient.

## Recommended Phase 6 Sequence

1. **GR-039:** Validate RFC-011 + BC-195 (in progress).
2. **RFC-023 (decomposer):** Design and implement Stage 1 spec decomposition. This is the highest-value architectural addition.
3. **RFC-026 (principal review surface):** Build the human-gate intake on top of RFC-019's bundling.
4. **First real workload:** Attempt a non-cert-watch spec through the full pipeline.
5. **RFC-022 (initiative):** Add operational grouping based on real-workload experience.
6. **v1 backlog decision:** Assess whether v2 is ready for v1 backlog items based on real-workload results.
