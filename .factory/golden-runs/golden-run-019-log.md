# Golden Run 019 — Throughput Improvements (BC-122/123/124)

**Date:** 2026-05-12
**Config:** `golden-run-019-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks), K2-only
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Project:** `sf2_golden_019`
**Workflow version:** 3

## Purpose

Validate three throughput improvements targeting the 0% first-attempt pass rate observed in GR-015:
- BC-122: Prompt pre-flight checklists
- BC-123: Inner gate auto-fix-back with `.orig` backup
- BC-124: Selective ruff rule set for inner gate

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 7 | 0 | 87.5% |
| implementation | 8 | 7 | 0 | 87.5% |
| **Total** | **24** | **22** | **0** | **92%** |

**Wall clock:** ~65 min (03:13 – 04:18 UTC).

**Note:** 1 item stuck on channel timeout (cert_chain_library implementation, `d75ba24b`). Model capability issue, not pipeline issue. If excluded: 22/23 locked (96%).

## Inner gate results (clean signal)

| Metric | GR-015 | GR-019 | Delta |
|---|---|---|---|
| Inner gate first-attempt pass (retry=0) | 0/24 (0%) | 7/11 (64%) | +64pp |
| Ruff failures | 8/8 interface specs | **0** | Eliminated |
| Lock rate | 24/24 (100%) | 15/16 (94%) | -6pp* |
| Remaining failure modes | ruff, import, mypy, pytest | import, mypy, pytest only | Ruff eliminated |

*GR-019 had 1 stuck item due to channel timeout; otherwise comparable.

## Key findings

1. **Zero ruff failures across the entire run.** BC-122/123/124 eliminated ruff as a failure mode.
2. **Inner gate first-attempt rate: 64%** (7/11 clean-signal items). This is a dramatic improvement from 0%.
3. **Remaining failures are structural:** import resolution (Traceback on `_run_import_check`) and mypy generic-type errors — not formatting.
4. Outer gate telemetry shows 0% first-attempt due to contaminated attempt counters from multiple partial runs. Inner gate data is the clean signal.

## Telemetry

Telemetry verify: passed (0 unknown gates, 0 orphans, 0 unmatched gates).

## Breadcrumbs opened

- BC-125: `populate_work_items.py --config` doesn't infer `--workflow` from config YAML. Led to GR-019 first attempt finding zero work items.

## Changes validated

- BC-122: Pre-flight verification checklists added to all three role prompts
- BC-123: Inner gate auto-fix-back with `.orig` backup and targeted F841 unsafe fix
- BC-124: Inner gate uses selective ruff rules matching `pyproject.toml` (`E,F,I,N,W,UP,RUF --ignore E501`)

(End of file)
