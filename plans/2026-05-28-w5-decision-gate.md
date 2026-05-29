# W5 Decision Gate — Phase B Generalization Assessment

**Date:** 2026-05-28
**Author:** opencode (GLM-5.1)
**Status:** complete
**References:** GR-040, GR-043, GR-044, GR-045; plans/2026-05-24-phase6-second-domain-and-decomposer-b.md W5

---

## Question

> Did Phase B produce a sensible decomposition for both workloads without per-workload tuning?

**Yes.** The Phase B decomposer produced semantic module names on both workloads without any prompt changes between them. Lock rates are statistically identical to Phase A baselines.

### Evidence

| Workload | FRs | Phase A Lock | Phase B Lock | Phase B Module Names | Decomposer Model |
|---|---|---|---|---|---|
| log-redact-cli | 5 | 96% (GR-040) | 97% (GR-043) | `rule_loader`, `log_reader`, `redaction_engine`, `output_emitter` | MiMo-V2.5-Pro |
| dep-graph-viewer | 4 | 97% (GR-044) | 96% (GR-045) | `event_log_reader`, `graph_builder`, `graph_filter`, `dot_emitter` | claude-code Sonnet |

Key observations:
- **No prompt tuning between workloads.** The same `decomposer.md` prompt and structured prompt builder produced acceptable decompositions for both.
- **Semantic naming worked on both.** Module names reflect domain concepts (not FR numbers). FR grouping is architecturally sensible (`output_emitter` groups FR-04+FR-05 in log-redact-cli).
- **Lock rates are equivalent.** Phase B does not degrade pipeline reliability: 96-97% lock across both workloads, matching Phase A baselines.
- **Model choice matters.** K2 could not follow the semantic naming prompt (GR-041). MiMo-V2.5-Pro and Sonnet both followed it. The decomposer prompt requires models with strong instruction-following capability.
- **Phase A fallback is robust.** When the model can't produce semantic names, the deterministic Phase A output is still acceptable (96-97% lock).

---

## Question

> What new defect classes (if any) did the second workload surface?

One new defect and one latent risk:

1. **BC-220 — Decomposer cross-workload contamination.** The Sonnet decomposer produced a hallucinated FR-05 containing log-redact-cli content (AC-LOG-08/09) when decomposing dep-graph-viewer. This is a context pollution issue: the model retained information from a prior decomposition. Mitigation: the decomposer should filter output against the spec's declared FR IDs.

2. **Gate venv type stub gap (BC-008 class).** dep-graph-viewer's `psycopg2-binary` dependency required `types-psycopg2` stubs for mypy to pass. The fixture's `requirements.txt` didn't include type stubs. This is a known CLASS-008 instance (gate environment mismatch) — fixed by adding type stubs to the fixture's requirements.txt.

No new systemic defect classes emerged. The pipeline's error handling (inner gate retries, cannot_proceed transitions, claim_near_budget hard-stops) worked correctly on all runs.

---

## Question

> Are any RFCs newly unblocked or newly forced?

- **RFC-023 (decomposer): Phase B validated.** The decomposer produces sensible decompositions on N=2 workloads without tuning. Consider promoting RFC-023 from "Phase 6 in progress" to "implemented" for the Phase B component. The deterministic Phase A remains the default; Phase B is available via `--decomposer-channel`/`--decomposer-model` flags.

- **RFC-027 (test efficacy): Not forced.** All golden runs show 92-100% inner gate first-pass rates. The pipeline's test gates (inner_pytest, inner_mypy, inner_ruff) are catching real failures. No evidence of test theater (tests passing on code that doesn't meet ACs). The mutation_gate is available but not yet exercised in a golden run.

- **RFC-026 (principal review surface): Not forced.** The review_surface module generates `REVIEW.md` from regista state. No principal review was needed during these runs (all reviews passed on first attempt).

- **RFC-034 (capture model identity): Partially addressed.** Telemetry now captures per-role model/channel information. The `MODEL_MEDIATED_GATES` frozenset exists but is not yet wired into telemetry reporting (flagged in prior reflection).

---

## Question

> Phase 6 status: substantively underway, blocked, or done?

**Phase 6.1 — Generalization validated on N=2 workloads.**

The pipeline produces working software on three structurally different workloads (cert-watch, log-redact-cli, dep-graph-viewer) at ≥96% lock rate through the full 7-stage DAG. Phase B (model-driven decomposer) works on both non-cert-watch workloads without tuning.

### Recommended AGENTS.md update

Change:
```
- **Phase 6 in progress.** RFC-023 Phase A (deterministic decomposer) validated through GR-039...
```
To:
```
- **Phase 6.1 complete.** Pipeline generalized to 3 workloads (cert-watch, log-redact-cli, dep-graph-viewer) at ≥96% lock rate through full 7-stage DAG. Phase B decomposer validated on 2 workloads with semantic module naming (MiMo-V2.5-Pro, Sonnet). 45 golden runs executed (GR-001 through GR-045).
- **Phase 6.2 remaining:** Web-service archetype, library-module archetype, mutation_gate exercise, test-efficacy validation (RFC-027).
```

### Open items for Phase 6.2

1. **Web-service workload** — Exercise API-server module shape (HTTP handlers, auth, JSON I/O)
2. **Library-module workload** — Exercise pure-library module shape (no CLI, no I/O, public API surface)
3. **Mutation gate exercise** — Run mutation_gate in a golden run to validate test efficacy
4. **BC-220 resolution** — Filter decomposer output against spec's declared FR IDs
5. **Non-CLI workload validation** — BC-209's remaining gap: no workload exercises production complexity
