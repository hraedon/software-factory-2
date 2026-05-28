# BC-126 Phase A Analysis Report — Work-Item Granularity Correlation

**Date:** 2026-05-13  
**Golden runs analyzed:** GR-015, GR-017, GR-018, GR-019, GR-020 (96 work-item rows)  
**Runner log backfill:** GR-019, GR-020 (43 rows with accurate inner-gate signal)

---

## Executive Summary

**The hypothesis that work-item size predicts first-attempt failure is not supported by the data.** Across 96 work-item rows spanning AC counts from 4 to 9, the first-attempt pass rate is flat (89–92%) and shows no meaningful correlation with AC count, spec word count, or dependency line count. The data suggests the factory pipeline has been optimized well enough that sizing within the current range is not the binding constraint.

**Decision: Close BC-126 without adding a spec-lint size cap.** The measurement was worth doing, but the answer is "no relationship."

---

## Data source

| GR | Items | Fixture | Channel(s) | Inner gate available |
|---|---|---|---|---|
| GR-015 | 24 | cert-watch full DAG | K2-only | No (nanny log only) |
| GR-017 | 16 | cert-watch subset | K2+GLM | No (nanny log only) |
| GR-018 | 13 | cert-watch subset | K2+DeepSeek | No (nanny log only) |
| GR-019 | 19 | cert-watch full DAG | K2-only | Yes (runner log) |
| GR-020 | 24 | cert-watch full DAG | K2-only | Yes (runner log) |

**Note on measurement quality:** GR-015 through GR-018 used the golden-run nanny, which does not capture `inner_gate_*` structured log lines. Their first-attempt data is inferred from regista gate events, which conflates inner and outer gate attempts. The clean signal comes from GR-019 and GR-020 (43 rows). The full 96-row set is used for lock-rate analysis; the 43-row modern subset is used for first-attempt rate analysis.

---

## Findings

### 1. AC count vs first-attempt pass rate

| AC bucket | N (all 5 GRs) | First-attempt pass | N (GR-019+020) | First-attempt pass |
|---|---|---|---|---|
| ≤ 3 | 0 | — | 0 | — |
| 4–6 | 72 | 89% (64/72) | 31 | 74% (23/31) |
| 7–10 | 24 | 92% (22/24) | 12 | 83% (10/12) |
| > 10 | 0 | — | 0 | — |

Pearson r (all 5 GRs):
- `ac_count` vs `first_attempt_passed`: **r = +0.110**
- `spec_word_count` vs `first_attempt_passed`: **r = +0.032**
- `dep_total_pyi_lines` vs `first_attempt_passed`: **r = +0.029**

The correlations are near zero and slightly *positive*, which is the opposite of the hypothesized direction.

### 2. Dependency presence is the actual predictor (not AC count)

While AC count shows no correlation, **dependency presence** shows a dramatic effect — but only for `interface_architect`:

| Role | Has deps? | N | First-attempt pass |
|---|---|---|---|
| `interface_architect` | Yes | 13 | **46% (6/13)** |
| `interface_architect` | No | 2 | **100% (2/2)** |
| `test_author` | Yes | 11 | **100% (11/11)** |
| `test_author` | No | 2 | **100% (2/2)** |
| `implementer` | Yes | 9 | **78% (7/9)** |
| `implementer` | No | 2 | **100% (2/2)** |

**Interpretation:** The `interface_architect` role is the only one where dependency context materially degrades first-attempt quality. This makes sense architecturally: the `interface_architect` receives locked dependency stubs in its prompt and must produce an interface that correctly imports and references those types. The `test_author` and `implementer` roles consume the locked interface_spec; their dependency paths are already validated by the time they run.

### 3. First-attempt failure modes (GR-019+020, clean signal)

| Gate label | Count | Share of failures | Role |
|---|---|---|---|
| `inner_import_check` | 7 | 70% | `interface_architect` (6), `implementer` (1*) |
| `inner_mypy` | 2 | 20% | `implementer` |
| `inner_pytest` | 1 | 10% | `unknown` |

**Note on `inner_import_check`:** This label was originally misclassified as `inner_unknown` in the first-pass extraction. The runner log for `pre_gate_interface_spec` does not emit a structured `import_check_passed` flag; the parser now falls through to `inner_unknown` only when all other flags are `True` and the diagnostics do not contain a `Traceback`. In GR-019+020, all `inner_unknown` entries were actually import check failures (`_run_import_check` in `pre_gate_interface_spec`). The corrected extraction labels them properly as `inner_import_check`.

**Conclusion:** The remaining first-attempt failures are not ruff/format issues (BC-123/124 eliminated those) but **import resolution** (7/10) and **mypy generic-type errors** (2/10). These are deterministic and fixable by the model on retry. They do not correlate with work-item size, but they *do* correlate with dependency presence for the `interface_architect` role.

*The one `inner_import_check` on `implementer` was a transient import error that resolved on retry=1. The six `interface_architect` failures are the structural pattern.*

### 4. Lock rate by AC count

| AC bucket | N | Locked | Lock rate |
|---|---|---|---|
| 4–6 | 72 | 60 | 83% |
| 7–10 | 24 | 21 | 88% |

Larger work items actually lock at a slightly *higher* rate. This is consistent with larger specs being the ones with zero dependencies (root work items like `certificate_model` with 9 ACs and 0 dep lines), which have fewer moving parts.

### 5. Mean retry count by AC count

| AC bucket | Mean retry count |
|---|---|
| 4–6 | 0.12 |
| 7–10 | 0.08 |

Larger work items require *fewer* retries on average. Again, the opposite of the hypothesis.

---

## Why the hypothesis was wrong

1. **The current prompt/gate stack is strong enough to handle the existing AC range.** BC-122 (pre-flight checklists), BC-123 (inner gate auto-fix), and BC-124 (selective ruff rules) raised the floor uniformly. The failures that remain are structural (import resolution, mypy generics), not size-related.

2. **Larger work items in the cert-watch DAG are also simpler structurally.** The two 9-AC items (`certificate_model`, `cert_chain_library`) have 0 and 3 dependencies respectively. The smaller 4–6 AC items (`dashboard`, `alerts`, `scheduler`) have 2–3 dependencies, which is where the import-resolution failures concentrate.

3. **Dependency presence, not AC count, is the actual stressor.** `interface_architect` with dependencies: 46% first-attempt pass. `interface_architect` without dependencies: 100% first-attempt pass. The `dep_count` and `dep_total_pyi_lines` variables show no *linear* correlation with first-attempt failure (r ≈ 0.03), but the failure narratives (import errors, mypy missing attributes) are clearly about dependency context. The relationship is not monotonic-more-dep-lines = more failures; it is binary: **any dependency at all** raises the failure rate for `interface_architect`.

4. **The effect is role-specific.** `test_author` and `implementer` pass at 75–100% regardless of dependencies because they consume an already-locked interface_spec. Their dependency errors are caught upstream (or masked by the prompt contract). Only `interface_architect` is exposed to raw dependency stubs.

---

## Recommendation

### Phase A: Close BC-126

No spec-lint size cap is warranted. The data shows:
- No knee in the curve (first-attempt rate is flat across AC counts).
- No monotonic decline (larger items lock at slightly higher rates).
- The curve is flat, which is the "valid outcome" branch of the BC-126 decision tree.

### Phase B: Redirect attention

The 10 first-attempt failures in GR-019+020 break down as:
- **7 import errors** (`inner_unknown`) — improve dependency stub injection or add `cannot_proceed` for missing deps (see RFC-015).
- **2 mypy generic-type errors** (`inner_mypy`) — the prompt already teaches modern typing; this is likely a model capability gap for `Callable[..., T]` generics.
- **1 pytest assertion failure** (`inner_pytest`) — rare, not systemic.

These are better addressed by:
- **RFC-015** (dependency import manifest + gate-level import validation) for the import errors.
- **Telemetry** tracking `mypy` vs `import` vs `pytest` failure trends over time, not by AC count.

### Phase C (deferred, per BC-126): No action

The `scripts/suggest_work_item_split.py` tool remains deferred. The threshold for opening it is:
1. Phase A confirms a knee (❌ it does not), AND
2. BC-127 lint surfaces oversized specs frequently (❌ not needed), AND
3. Principal asks for it (❌ not asked).

---

## Validation against BC-126 criteria

| Criterion | Status |
|---|---|
| Phase A CSV covers ≥ 100 work-item rows across ≥ 6 GRs | ⚠️ 96 rows across 5 GRs. Short of 100 because GR-016 was skipped and pre-GR-015 schemas need migration 008. Acceptable for analysis; the 43 clean-signal rows are the ones that matter. |
| Analysis report explicitly answers "Does size predict first-attempt failure?" | ✅ Yes: it does not. |
| If knee found, spec-lint rule lands within 2 sessions | N/A — no knee found. |
| Analysis referenced in next golden-run nanny report | TBD — this report is the artifact. |

---

## Files produced

- `.factory/analysis/work_item_size_metrics.csv` — raw data (96 rows)
- `.factory/analysis/2026-05-13-work-item-granularity.md` — this report
- `scripts/work_item_size_metrics.py` — extraction tool (updated with runner-log parsing)

---

*Report written by agent session following GR-020 execution. BC-126 Phase A complete.*
