---
model: kimi-k2p6-turbo
project: software-factory-2
datetime: 2026-05-13T00:30Z
---

# Session Reflection — 2026-05-13

**Work summary:** Executed GR-020 (cert-watch full DAG, K2-only), achieving 100% lock rate and 77% inner-gate first-attempt pass rate. Built and ran BC-126 Phase A measurement (`scripts/work_item_size_metrics.py`), concluding that work-item size (AC count, spec words, dep lines) does not predict first-attempt failure. Filed BC-131 for the actual remaining failure mode: runtime import resolution feedback quality for dotted submodule imports.

---

## On the project

The factory is in a strong position. Phase 3 exit criteria are met on mechanical grounds (100% lock, 77% first-attempt, 1.08 mean attempts, 0 stuck). The architecture is holding: sequential pipeline, locked artifacts, substrate spine, inner gate retry loop. The remaining work is telemetry accounting and prompt engineering, not model capability or gate correctness.

The most important structural insight from this session is that **v2's simplicity is load-bearing because the contract is smaller**. The sequential pipeline and per-work-item locking eliminate the coordination problems that forced v1 into manifest generators, plan YAMLs, and contract challenge gates. The *only* place where v1's insight still applies is the `interface_architect` prompt — and the fix is a one-session prompt change, not a subsystem rebuild.

What feels fragile: the telemetry aggregation conflates inner and outer gate attempts, producing misleading 0% outer-gate first-attempt rates. This is a dashboard bug, not a pipeline bug, but it will confuse every future agent until fixed.

## On the work done

GR-020 was the cleanest golden run to date — 52 minutes, zero channel timeouts, all 24 items locked. The inner gate architecture (BC-122/123/124) has transformed the dominant failure mode from "ruff/format noise" to "actual semantic mistakes."

The BC-126 analysis was worth doing even though the answer was "no relationship." The measurement revealed that **dependency presence, not AC count, is the actual predictor** — but only for `interface_architect` (46% with deps vs 100% without). This is a role-specific prompt-context problem, not a universal size problem. The analysis report and extraction tool are solid artifacts.

BC-131 is correctly scoped: feedback quality for runtime import resolution, not gate logic extension. The RFC-015 review feedback (principal + deepseek) was rigorous about scope boundaries, and this session honored them.

What I'd want a second pair of eyes on: the `work_item_size_metrics.py` runner-log parser. It was iteratively fixed twice (AC counting, then gate label extraction). The current version is correct for GR-019+020 logs, but may drift if runner log format changes. A unit test against a frozen log fixture would be more robust.

## On what remains

**Before Phase 4:**
1. **Telemetry dimension fix** — Add `inner_gate_first_attempt` as a separate telemetry metric so future golden runs don't show misleading 0% outer-gate first-attempt rates. This is a `telemetry.py` change, one session.
2. **BC-131 implementation** — Parse `_run_import_check` Traceback into structured feedback for dotted submodule / module-not-found errors. Target: GR-021 `interface_architect` with deps ≥ 70% first-attempt.
3. **Deterministic gate classifier alignment** — `test_suite_assertions` is deterministic but telemetry reports 8% deterministic rate. Small taxonomy fix.

**Phase 4 readiness (not blocking):**
4. Fleet triage — smoke-test Gemini, GLM, DeepSeek adapters; disable untested ones.
5. No breadcrumb status drift — BC-121 is "implemented" but still in open table (minor cleanup).

**Nice to have:**
- A `scripts/suggest_work_item_split.py` tool remains deferred per BC-126. Not needed unless a future fixture shows a real size knee.

## Gaps to flag

- **Telemetry first-attempt metric is operationally useless** (`telemetry.py:38-112`). The outer gate conflates inner+outer attempts. Every future golden run will show ~0% first-attempt unless this is fixed. Location: `src/factory/telemetry.py:compute_exit_criteria()`.
- **Runner log format is not versioned.** The `work_item_size_metrics.py` parser depends on specific structured log line shapes (`inner_gate_failed_retry diagnostics=[...] imports_symbols_passed=...`). If runner logging changes, extraction will silently misclassify. Add a format version comment or a test fixture.
- **GR-020 telemetry reports 8% deterministic** but 0% unknown. The 2 `test_suite_assertions` failures are deterministic. The classifier needs to map `test_suite_assertions` → deterministic. Location: `src/factory/telemetry.py:119-149`.
- **BC-121 status drift** in `breadcrumbs/README.md:49` — shows "implemented" in open table, should be in resolved.
- **`tests/fixtures/refurb-watcher/`** appeared as untracked in `git status`. Not part of this session's work. Verify if it should be committed or `.gitignore`d.
- **GR-019/020 runner logs** are the only source of accurate inner-gate signal. Pre-GR-019 logs don't capture `inner_gate_*` structured lines. The 96-row CSV includes 53 rows with inferred (less reliable) first-attempt data. The 43-row modern subset is the clean signal.
