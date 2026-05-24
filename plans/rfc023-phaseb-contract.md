# RFC-023 Phase B — Contract Lock

**Status:** locked  
**Date:** 2026-05-24  
**Author:** Opus plan executor (K2)  
**Origin:** `plans/2026-05-24-phase6-second-domain-and-decomposer-b.md` W2.1

## Input Schema

- **`spec.yaml`** (preferred): structured YAML with `functional_requirements`, `acceptance_criteria`, `dependency_hints`, `glossary`.
- **`spec.md`** (fallback): freeform markdown with implied FR/AC structure parsed deterministically.
- **`prior_failures`** (optional): structured gate diagnostics from earlier attempts.

## Output Schema

Same as Phase A `DecompositionResult` — list of `DecomposedModule` objects — but with the following Phase B constraints:

| Field | Phase A (deterministic) | Phase B (model-driven) |
|---|---|---|
| `module_name` | `fr_id` lowercased (`fr01`, `fr02`) | **Semantic snake_case** (`rule_loader`, `dot_emitter`) |
| `fr_id` | Copied from spec | Copied from spec (primary owner) or synthesized for grouped modules |
| `fr_text` | Copied from spec | Summarized module purpose |
| `ac_ids` | Flat list per FR | Flat list per module (all ACs from grouped FRs) |
| `dependency_fr_ids` | Copied from spec hints | Derived by model from structural analysis |

### Semantic naming rules (enforced in prompt + gate)

1. **No FR identifiers in module names.** `fr01`, `fr02`, `fr03` are forbidden.
2. **No generic suffixes.** `module`, `handler`, `service`, `utils` are forbidden unless part of a compound (`redaction_engine` is OK; `service_module` is not).
3. **Prefer verb-noun or noun-noun compounds** that describe the capability: `rule_loader`, `event_reader`, `graph_builder`, `dot_emitter`.
4. **Max 40 chars, snake_case, unique within decomposition.**

## Channel Placement

- **Primary:** `cross_family_reviewer` tier reasoning (Sonnet recommended). The decompose step is high-leverage; one bad grouping propagates.
- **Review:** K2 cross-family review on the decomposition document itself (jury at the decomposer stage, not downstream).
- **Timeout:** 600 seconds (same as interface_architect).

## Co-design Discipline

No Phase B feature lands without producing **acceptable** decompositions for **both** cert-watch and both new workloads (log-redact-cli, dep-graph-viewer) without per-workload tuning.

### Definition of "acceptable"

- Module names are semantic (pass naming gate above).
- Dependency graph matches the spec's intended phasing (acyclic, respects the spec's `dependency_hints`).
- No module has <2 ACs or >12 ACs (soft gate, warn-only for 1-AC modules).
- The decomposition looks like what a senior engineer would write for a new codebase.

## Integration Point

Phase B consumes the same `populate_work_items.py` CLI surface:

```bash
populate_work_items.py \
  --spec-yaml tests/fixtures/log-redact-cli/spec.yaml \
  --decomposer-channel opencode \
  --decomposer-model <model> \
  --workspace-root /tmp/sf2-gr040
```

If `--decomposer-channel` is omitted, Phase A (deterministic) is used as fallback. Phase B becomes the default when both `--spec-yaml` and a channel are provided.

## Gate Points

Added to `_validate_decomposition()` in `decomposer_model.py`:

1. **semantic_naming_gate**: rejects module names that match `fr\d+`, contain forbidden suffixes, or are >40 chars.
2. **ac_coverage_gate**: warns (pass) on modules with <2 ACs; rejects >12 ACs.
3. **dependency_graph_gate**: unchanged (acyclic, no orphaned deps).

## Rollback Plan

If Phase B fails validation after `max_retries`, the decomposer **falls back to Phase A deterministic** rather than aborting the pipeline. This preserves the existing `populate_work_items.py` contract: "spec-yaml always produces fixtures."
