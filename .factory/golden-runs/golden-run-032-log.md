# Golden Run 032 — Phase 5 multi-family validation: Claude + Gemini + K2, cert-watch-mini

**Date:** 2026-05-16
**Config:** `golden-run-032-config.yaml`
**Channels:**
- `claude-code` (sonnet) — interface_architect, frontier_judge (juror 1)
- `opencode` (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — test_author, implementer, integrator, outcome_verifier
- `gemini-cli` (gemini-2.5-pro) — cross_family_reviewer, frontier_judge (juror 2)
**Fixture:** cert-watch-mini (3 work-items: certificate_model, fr02_tls_scan, fr03_file_upload)
**Executed by:** OpenCode agent via `scripts/agent_golden_run.py`
**Wall clock:** ~23 minutes

## Purpose

Validate Phase 5 pipeline with a **new multi-family model combination**:
- First pipeline use of **Claude sonnet** for interface_architect (Anthropic family)
- First pipeline use of **Gemini 2.5 Pro** for cross_family_reviewer and frontier_judge (Google family)
- First **Anthropic + Google dual-family jury**
- Baseline comparison against GR-031 (K2 + Qwen) to measure model-family impact on Phase 5 outcomes.

## Result

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 15 | — | — |
| Locked | 12 (80%) | ≥90% | **FAIL** |
| Cannot proceed | 3 | — | Properly escalated |
| Stuck | 0 | ≤1 per 16-item DAG | **PASS** |
| Mean attempts to lock | 1.93 | ≤2.0 | **PASS** |
| First gate-evaluation pass rate | 80% (12/15) | ≥60% | **PASS** |
| Inner gate first-pass rate | 73% (8/11) | ≥60% | **PASS** |
| Unknown gate rate | 0.0% (0/29) | ≤10% | **PASS** |
| Deterministic gate rate | 100% (29/29) | ≥80% | **PASS** |
| Verify passed | True | — | **PASS** |

**Overall: FAIL** (lock rate 80%, below 90% target; integration stage is the swing factor)

## Per-stage detail

### Interface specs (3 items)
3/3 locked. **Claude sonnet as interface_architect.**
- Inner gate: 1/3 first-pass (2 items had `wrong_module_name` import error, recovered on retry=1).
- Outer gate: 3/3 first-pass.
- Claude performed comparably to K2 on this role (inner first-pass 33% vs K2's historical ~50%).

### Test suites (3 items)
3/3 locked. K2 as test_author.
- Inner gate: 3/3 first-pass.
- Outer gate: 3/3 first-pass.

### Implementations (3 items)
2/3 locked. K2 as implementer.
- Inner gate: 2/3 first-pass. One item (`2b4eb342`, certificate_model) failed `inner_mypy` on both retry=0 and retry=1 with `dict` invariance errors (`dict[str, str | tuple[...]]` incompatible with `dict[str, object]`).
- Outer gate: `implementation_mypy` failed on the same item after exhausting inner-gate retries.
- **Budget exhausted at attempt=3** → `cannot_proceed` transition (BC-139/BC-143 fix working correctly).
- The other 2 implementations locked cleanly.

### Reviews (2 items)
2/2 locked. **Gemini 2.5 Pro as cross_family_reviewer.**
- 1st gate pass: 2/2 (100% first-pass).
- Gemini successfully reviewed both implementations and approved them.
- No `REVIEW_FOUND_DEFECT` or upstream routing triggered (implementations were clean).

### Jury (2 items)
2/2 locked. **Dual-family jury: Claude sonnet + Gemini 2.5 Pro.**
- 1st gate pass: 2/2 (100% quorum).
- Both juries reached quorum on first evaluation. No disagreements.
- First-ever Anthropic + Google dual-family jury in the project.

### Integration (2 items)
0/2 locked. K2 as integrator.
- Inner gate: 2/2 first-pass (`inner_json_shape` passed).
- Outer gate: 2/2 failed `integration_import`.
- The integrator produced valid JSON artifacts but the assembled code had import resolution issues when the gate tried to execute the assembled tree.
- Both items exhausted budget at attempt=3 → `cannot_proceed`.
- **No outcome_verification items created** (blocked by integration failures).

## Failure analysis

### 1. Implementation mypy failure (`2b4eb342`, certificate_model)
**Root cause:** K2 implementer produced a type annotation that mypy rejected due to `dict` invariance. The function signature used `dict[str, str | tuple[...]]` but mypy expected `dict[str, object]` or `Mapping`.

**Diagnostic excerpt:**
```
interface.py:78: error: Argument 1 to "_build_certificate" has incompatible type
  "dict[str, str | tuple[tuple[tuple[str, str], ...], ...] | tuple[tuple[str, str], ...]]";
  expected "dict[str, object]"  [arg-type]
interface.py:78: note: "dict" is invariant -- see https://mypy.readthedocs.io/en/stable/common_issues.html#variance
```

**Classification:** Model-shaped type-safety failure, not prompt-shaped. K2 has historically handled cert-watch cleanly; this is a stochastic regression on one item.

**Mitigation already in place:** Inner gate retries (2 attempts) did not recover. The failure is in the structural type annotation, which the model would need to reformulate using `Mapping` instead of `dict`. This is a known class of mypy failures that inner gate feedback surfaces but does not always fix.

### 2. Integration import failures (`183479b6`, `f087ae3c`) — **CORRECTED: BC-174 discovered and fixed post-run**

**Original (incorrect) assessment:** Prompt-shaped integrator failure — integrator produces bad import paths.

**Corrected root cause (discovered during post-run forensics):** The `integration_import` gate runs **in-process** inside the gate process, using `sys.executable` (the factory's own `.venv/bin/python`). That venv lacks project dependencies like `cryptography`. The **gate venv** (`.venv-gate` under the workspace) *does* have `cryptography>=42.0` installed, but the import-resolution loop never uses it.

**Evidence:**
- Reproducing the exact gate logic with the gate venv python: imports succeed.
- Reproducing with the factory venv python: `ModuleNotFoundError: No module named 'cryptography'`.
- The workspace's `.venv-gate/lib/python3.12/site-packages/` contains `cryptography-48.0.0.dist-info`.
- `evaluate_integration()` uses `python_executable` (gate venv) for mypy and pytest (subprocesses), but `sys.path` + `importlib.util` (in-process) for import resolution.

**Classification:** CLASS-008 instance #11 — gate execution environment mismatch. Same shape as BC-121 (gate process used wrong venv for tooling).

**Fix implemented (BC-174, same session):**
- Replaced the in-process `importlib.util` loop with a subprocess invocation under `python_executable` (the gate venv).
- The subprocess receives a self-contained `-c` script that performs the import loop and prints a JSON array of errors.
- Direct validation: assembled tree importing `cryptography.x509` now passes `integration_import` when using the gate venv.
- `py_files` is computed once and reused by all three gates.
- All 947 tests pass; ruff clean.

**Impact on prior runs:** This bug likely explains GR-030's 0/2 integration failures and 2/3 of GR-031's integration failures (the 1/3 that locked had no external deps). The integrator prompt was never the primary problem — the gate was.

## Model-family performance comparison

| Role | GR-031 (K2+Qwen) | GR-032 (Claude+Gemini+K2) | Delta |
|---|---|---|---|
| interface_architect | K2, 3/3 locked | **Claude, 3/3 locked** | Equivalent |
| test_author | K2, 3/3 locked | K2, 3/3 locked | Same |
| implementer | K2, 3/3 locked | K2, 2/3 locked | **-1** (stochastic) |
| cross_family_reviewer | Qwen, 3/3 locked | **Gemini, 2/2 locked** | Equivalent (fewer items) |
| frontier_judge | K2+Qwen, 3/3 locked | **Claude+Gemini, 2/2 locked** | Equivalent |
| integrator | K2, 1/3 locked | K2, 0/2 locked | **-1** (fewer items, same shape) |
| outcome_verifier | K2, 1/1 locked | K2, N/A | Not reached |
| **Total locked** | **17/19 (89%)** | **12/15 (80%)** | **-9%** |

**Key finding:** The model-family change (Claude architect, Gemini reviewer/judge) did **not** degrade upstream stages. The 9% lock-rate difference is driven by:
1. One stochastic K2 implementer mypy failure (would have happened with GR-031's binding too)
2. Integration stage still failing at 0% (same as GR-030, worse than GR-031's 33%)

The integration stage is the **dominant swing factor** for Phase 5 lock rate regardless of model family.

## BC-145 upstream routing

No `REVIEW_FOUND_DEFECT` events occurred in this run (reviews passed cleanly). BC-145 Phase 1 infrastructure remains unexercised in a real golden run. The `routing_hint` telemetry table is empty.

## Claim-near-budget behavior

The wrapper logged `claim_near_budget` warnings for all 3 cannot_proceed items. The runner correctly:
1. Detected `attempt=3 >= threshold=3`
2. Released the claim
3. Transitioned to `cannot_proceed` (terminal)

No zombie cycling. BC-139/BC-143 fixes validated.

## Channel health

| Channel | Family | Outcomes | Notes |
|---|---|---|---|
| claude-code | Anthropic | 5/5 locked (architect + 2 juries) | No timeouts, no empty output |
| opencode (K2) | Moonshot | 7/8 locked (3 test, 2 impl, 2 integration inner) | 1 mypy failure, 2 integration outer failures |
| gemini-cli | Google | 4/4 locked (2 review, 2 juries) | No timeouts, no empty output |

All three channels were stable. No `channel_invoke_failed` events. No failover triggered.

## Telemetry integrity

- `unknown_gate_name_count`: 0
- `orphan_submit_count`: 0
- `unmatched_gate_count`: 0
- `verify_passed`: True

## Post-run work (same session)

1. **BC-174 filed and fixed:** Root-cause analysis traced `integration_import` failures to gate environment mismatch. Fixed `evaluate_integration()` to run import resolution as a subprocess under the gate venv.
2. **CLASS-008 updated:** Instance count incremented from 10 → 11; BC-174 appended to instances table.
3. **Tests:** 947 passed, 13 skipped; ruff clean; direct validation confirms fix.

## Artifacts preserved

Workspace preserved at `/tmp/sf2-golden-032` (since `--no-cleanup` was used). Logs preserved at `.factory/logs/gr032/`.

## Lessons and next steps

1. **Claude sonnet is viable for interface_architect in Phase 5.** Performance equivalent to K2 on this fixture.
2. **Gemini 2.5 Pro is viable for cross_family_reviewer and frontier_judge.** 100% first-pass rate on both roles in this run.
3. **Anthropic + Google dual-family jury works.** First clean run with this family pair; quorum reached on all items.
4. **BC-174: Integration gate import resolution ran in wrong Python environment.** Fixed by running import checks as a subprocess under the gate venv (same as mypy/pytest). This was a gate infrastructure bug masquerading as a model-quality problem. GR-033 should validate the fix on cert-watch-mini with project dependencies.
5. **Implementation mypy stochastic failures persist.** Even with inner-gate retries, some type-annotation errors are not recoverable. This is a model-capability ceiling, not a pipeline bug.
6. **No BC-145 upstream routing exercised.** Reviews passed cleanly; we still lack a golden run where review finds a substantive defect and routes structured feedback upstream. This may require a synthetic bad-impl fixture.
