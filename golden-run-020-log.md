# Golden Run 020 — Phase 3 Exit Criteria Validation

**Date:** 2026-05-12
**Config:** `golden-run-020-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks), K2-only
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Project:** `sf2_golden_020`
**Workflow version:** 3

## Purpose

Execute a clean golden run to validate Phase 3 exit criteria after BC-122/123/124 throughput improvements.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 8 | 0 | 100% |
| implementation | 8 | 8 | 0 | 100% |
| **Total** | **24** | **24** | **0** | **100%** |

**Wall clock:** ~52 min (23:23 – 00:15 UTC).
**Zero stuck items. Zero ruff failures.**

## Inner gate first-attempt analysis

| Metric | Value |
|---|---|
| Inner gate first-attempt pass (retry=0) | 20/26 (77%) |
| Inner gate first-attempt fail | 6/26 (23%) |
| Mean attempts to lock | 1.08 |

## First-attempt failure modes (clean signal)

| Gate label | Count | Share | Role |
|---|---|---|---|
| `inner_import_check` | 4 | 67% | interface_architect |
| `inner_mypy` | 2 | 33% | implementer |

All failures are deterministic and recover on retry=1.

## Telemetry verification

```
verify_passed: True
unknown_gate_name_count: 0
unknown_gate_name_rate: 0.0000
orphan_submit_count: 0
unmatched_gate_count: 0
confounding_warning_count: 0
```

## Phase 3 exit criteria assessment

| Criterion | Threshold | GR-020 | Met? |
|---|---|---|---|
| First-attempt mechanical-gate pass rate | ≥ 60% | **77%** | ✅ |
| Lock-within-budget rate | ≥ 90% | **100%** | ✅ |
| Mean attempts to lock | ≤ 2.0 | **1.08** | ✅ |
| ≤1 stuck item per 16-work-item DAG | ≤1 | **0** | ✅ |
| ≤10% unknown/tool_not_found gate failures | ≤10% | **0%** | ✅ |
| Spec lint wired and producing deterministic findings | Yes | **Met** | ✅ |

## BC-126 Phase A conclusion

Work-item size (AC count, spec word count, dep lines) **does not predict** first-attempt failure. Dependency presence (not AC count) is the actual stressor — but only for `interface_architect` (46% with deps vs 100% without).

## Files produced

- `.factory/analysis/2026-05-13-work-item-granularity.md` — BC-126 report
- `.factory/analysis/work_item_size_metrics.csv` — 96 rows across 5 GRs
- `.factory/analysis/work_item_size_metrics_clean.csv` — 43 clean-signal rows (GR-019+020)

## Breadcrumbs opened

- BC-131: Runtime import resolution feedback quality for dotted submodule imports (proposed narrow follow-up to RFC-015)

(End of file)
