# GR-041: log-redact-cli Phase B (model-driven decomposer) — partial run

**Date:** 2026-05-27
**Config:** `.factory/golden-runs/golden-run-041-config.yaml`
**Fixture:** Phase B decomposer output from `tests/fixtures/log-redact-cli/spec.yaml`
**Channels:** K2 (opencode) for worker roles, Sonnet (claude-code) for cross_family_reviewer + jury
**Executor:** manual (populate + runner/gate/scheduler)
**Wall clock:** ~25 min (00:09–00:33 UTC)

## Purpose

Phase B validation for RFC-023. Run the same log-redact-cli workload through the model-driven decomposer to test whether semantic module naming and improved decomposition reduce cross-module type incompatibility (the failure mode observed in GR-040).

## Result Summary

| Metric | GR-041 (Phase B) | GR-040 (Phase A) | Target |
|---|---|---|---|
| Lock-within-budget | 57% (4/7) | 96% (45/47) | — |
| Mean attempts | 2.40 | 1.76 | ≤2.0 |
| First gate pass | 80% (4/5) | 100% (45/45) | ≥60% |
| Inner gate first-pass | 80% (4/5) | 91% (31/34) | ≥60% |
| Cannot proceed | 2 | 2 | — |
| Deterministic gate rate | 100% (12/12) | 76% (60/79) | ≥80% |
| Stuck items | 1 | 0 | ≤1 |

**Overall: SOME FAIL** — pipeline stalled after implementation stage.

## Key Finding: Phase B Decomposer Did Not Produce Semantic Names

The model-driven decomposer (K2) produced **identical output** to the deterministic decomposer:
- Module names: `fr01`, `fr02`, `fr03`, `fr04`, `fr05` (no semantic names)
- AC format: `## AC-LOG-01` (not `## AC-01:` as the linter expects)
- Spec structure: identical to Phase A output

This means Phase B's semantic naming gates never fired because the model produced the same content. The decomposer prompt's semantic naming rules (`no fr\d+`, `no generic suffixes`) were not followed by K2.

## Failure Analysis

### 1 interface_spec cannot_proceed (fr02)
- fr02 (log ingestion) went to cannot_proceed early
- Root cause unclear from logs — likely a model error in the spec generation

### 1 implementation cannot_proceed (fr03 dependency)
- Implementation for fr03's downstream work item exhausted inner gate retries
- 3 inner_mypy failures:
  1. `types-PyYAML` missing (pre-existing — gate venv created before the stub fix)
  2. Real type error: `Incompatible types in assignment (list[Any] vs str)` and `Argument "scope" to "Rule" has incompatible type`
  3. `types-PyYAML` missing again
- The model generated code with type mismatches that it couldn't self-correct

### 1 stuck item
- The implementation that went to cannot_proceed left a downstream test_suite item orphaned

## Comparison with GR-040

Phase B performed **worse** than Phase A on this workload:
- GR-040 achieved 96% lock rate; GR-041 achieved 57%
- GR-040's 2 cannot_proceed items were at integration (expected); GR-041's were earlier
- The model-driven decomposer didn't produce different content from the deterministic one

This suggests either:
1. The decomposer prompt's semantic naming rules are not strong enough for K2
2. K2 defaults to the `fr\d+` pattern when the spec uses FR-NN numbering
3. The Phase B value proposition (shared types, semantic names) requires a different prompt strategy or a stronger model

## Lessons

1. **Phase B needs prompt tuning.** K2 didn't follow the semantic naming rules. The decomposer prompt may need few-shot examples or explicit negative examples.
2. **The gate venv stub fix works but requires venv recreation.** The existing venv from GR-040 didn't pick up the `types-PyYAML` fix because the requirements.txt hash didn't change.
3. **Phase A is already good.** GR-040's 96% lock rate on a non-trivial workload is strong. Phase B's value needs to be demonstrated with a workload where Phase A's cross-module types actually fail at integration.
4. **The spec lint AC format gap is real.** Both Phase A and Phase B produce `## AC-LOG-01` format, but the linter expects `## AC-01:`. The decomposer (both phases) should normalize AC format.

## Artifacts

- Workspace: `/tmp/sf2-golden-041` (--no-cleanup)
- Logs: `.factory/logs/gr041/`
- Config: `.factory/golden-runs/golden-run-041-config.yaml`
- Decomposed fixtures: `/tmp/.decomposed/`
