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

---

## Addendum — the decomposer evidence is weaker than "N=2 validated" implies (2026-05-29)

**Author:** Claude Opus (review session)

The "Phase B validated on N=2 workloads" finding above carries two confounds that materially affect the RFC-023 promotion recommendation. Stated plainly so the gate decision isn't made on the rosier reading:

### 1. The N=2 is two different decomposer models, one workload each — not one model across two workloads

| Workload | Decomposer | Result | N |
|---|---|---|---|
| log-redact-cli | MiMo-V2.5-Pro (GR-043) | clean semantic names, no contamination | 1 |
| dep-graph-viewer | Sonnet (GR-045) | semantic names **+ cross-workload contamination (BC-220)** | 1 |

No single decomposer model has been validated across both workloads. MiMo is validated on 1; Sonnet on 1 (with a defect). The run planned in GR-043 lesson #5 was *MiMo on dep-graph-viewer*; GR-045 substituted Sonnet. So the matched pair this gate appears to rest on **does not exist** — it's a mixed pair presented as a clean one.

### 2. The model scoreboard is not "MiMo/Sonnet good, K2 bad"

All three decomposer results are N=1, and the failure modes are not equivalent:

- **K2 / Kimi (GR-041):** declined to follow the semantic-naming instruction → degraded safely to deterministic Phase A. A benign, inert failure. (GR-041's ugly lock rate was largely the since-fixed `populate_work_items` AC-ID bug, BC-219, not K2's decomposition.) K2 is also the worker model carrying every stage of these pipelines at 96–97%.
- **MiMo (GR-043):** clean. The run's "SOME FAIL" was an unrelated channel hiccup, not the decomposition.
- **Sonnet (GR-045):** followed the instruction but injected another spec's content (BC-220). In an autonomous run this flows downstream; spec_lint only warns, it doesn't reject.

Ranked by danger, Sonnet's contamination is the **worst** of the three decomposer outcomes — more dangerous than K2's safe non-compliance, because it produces wrong content rather than no new content.

### Implication for the RFC-023 promotion recommendation

Promoting Phase B to "implemented" currently rests on (a) one model clean on one workload and (b) one model *defective* on the other. That is thinner than "validated on N=2." **Recommend gating the promotion on GR-046 (below)** producing one decomposer model clean across both workloads, with BC-220 either resolved or demonstrated to be session-specific.

What this addendum does **not** dispute: Phase A fallback robustness, lock-rate equivalence, and "model choice matters for instruction-following" all hold. The narrowing is specifically about the strength of the "Phase B generalizes" claim and the safety of the decomposer role. It also does not touch the separate, still-open question of whether semantic naming earns its complexity — GR-045 found the names are a readability gain, not a correctness gain.

### Recommended: GR-046 — MiMo on dep-graph-viewer, fresh session

**Purpose:** convert the confounded N=2 into one decomposer model (MiMo) clean across both workloads, and determine whether BC-220 contamination is session-driven or model-driven.

**Design:**
- Decomposer: MiMo-V2.5-Pro (`--decomposer-channel`/`--decomposer-model`) on `dep-graph-viewer/spec.yaml`.
- **Fresh session / no prior decomposition in context** — the key control. BC-220's root-cause hypothesis is session-context retention from GR-043 (log-redact-cli decomposed in the same context). A clean context is the only way to distinguish "MiMo is clean" from "the session leaked."
- Hold everything else at the GR-044/045 config (K2 workers, Sonnet review/jury) so the decomposer is the only variable.

**Decision value (either outcome is informative):**
- **Clean →** MiMo validated on 2 workloads; contamination looks session-specific (supports the BC-220 workaround); RFC-023 promotion is on firm ground.
- **Contaminated →** BC-220 is systemic across decomposer models, not a Sonnet quirk → promotion blocked, and the contamination is a higher-severity defect than its current `medium` rating.

**Optional GR-047:** re-run Sonnet on dep-graph-viewer in a *fresh* session to confirm BC-220 was the session artifact it hypothesizes (and not inherent Sonnet behavior). Cheap; fully separates model-quality from session-hygiene. Lower priority than GR-046.

**Caveat:** GR-046 strengthens the generalization + safety claim only. It does not address whether semantic naming is worth the added model dependency and contamination surface — that cost/benefit question is separate and remains open regardless of GR-046's outcome.
