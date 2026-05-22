# RFC backlog — implementation plans

**Date:** 2026-05-22
**Author:** opus-4-7
**Source:** RFC review during BC-199 (substrate) / BC-194 (sf2) hardening pass
**Scope:** Plans for the seven RFCs the principal accepted in the 2026-05-22 review. RFC-032 deliberately omitted (decision: defer until RFC-030+031 have run for a few weeks).

## Tier legend

- **Opus** — load-bearing design judgment, irreversible architectural choices, or work where the first implementation sets a pattern that's expensive to retrofit
- **Sonnet** — well-scoped engineering with some judgment; multi-file refactors with clear shape; telemetry/aggregation work; mechanical changes that nonetheless need solid code synthesis
- **Kimi/GLM** — clear-acceptance-criteria changes against a known target: single-pattern fixes, dead-code removal, README/schema text edits, status-flip-only changes

---

## 1. RFC-030 — Class-promotion block rule

**Implementer: Sonnet** (most of the documentation is already in place; mechanical enforcement is the remaining work)

### Current state

`breadcrumbs/README.md` already documents the block rule textually. The rule is *stated* but not *enforced*. RFC-030 itself sits in `proposed`.

### Acceptance criteria

- **AC-1**: `scripts/check_class_block_rule.py` exists and exits non-zero when a CLASS file's instances table has grown while an open RFC (`status: proposed` or `in_progress`) is filed against that class and no `symptom-fixed-because` rationale is in the CLASS file body.
- **AC-2**: The script is wired into `make check` (or whatever pre-merge entrypoint exists).
- **AC-3**: RFC-030 status flips to `implemented`.

### Implementation steps

1. Walk `breadcrumbs/CLASS-*.md`. For each, parse the front-matter `status` (skip `stabilized`). Find any RFCs whose `related:` field references the CLASS, or whose body mentions the CLASS by name and is in `proposed`/`in_progress` status.
2. For each CLASS that has an open RFC against it, count rows in the instances table.
3. Compare against the value at HEAD (use `git show HEAD:breadcrumbs/CLASS-XXX.md` and run the same parse). If the trailing row count grew on the current branch and no `symptom-fixed-because` paragraph exists in the body, fail with a message naming the class and the open RFC.
4. Flip RFC-030 status to `implemented` and add an `## Implementation` section pointing at the script.

### Risks / notes

- The instances-table-row count is the simplest possible heuristic. False positives possible if someone renames the class file or restructures the table. Accept this — the rule's point is *forcing a conversation*, not airtight enforcement.
- `symptom-fixed-because` paragraph detection is a substring search for that exact phrase. Document the convention in the CLASS files README.

---

## 2. RFC-031 — Fix-family root-cause paragraph

**Implementer: Kimi/GLM** (one README edit + RFC status flip)

### Acceptance criteria

- **AC-1**: `breadcrumbs/README.md` Schema section documents the requirement: when a BC's `related:` field cites another BC that shares at least one tag, the `## Fix` section MUST contain a `### Why this isn't the previous fix recurring` subsection.
- **AC-2**: RFC-031 status flips to `implemented`.

### Implementation steps

1. Edit `breadcrumbs/README.md`: add a "Fix-family rule" subsection under Schema that quotes the requirement, names RFC-031 as the source, and gives the worked example from the RFC body.
2. Flip RFC-031 status.

### Risks / notes

- Mechanical enforcement is harder (requires comparing tags across cited BCs) and is *not* in this plan. The rule lives in the template; the next reviewer is expected to catch violations. If violations recur, a follow-up RFC can add a check script.

---

## 3. RFC-037 — Detect/enforce/retire tiering (and RFC-033 closure)

**Implementer: Opus (me)** for the framework + first tagged examples; Sonnet for the audit pass that tags existing checks once the pattern is set

### Why Opus

This RFC establishes a vocabulary that other RFCs (RFC-030, RFC-033) build on. The first few tagged examples set the pattern every subsequent author copies. A wrong choice on what counts as `detect` vs `enforce`, or what the precondition comment should look like, will propagate.

### Acceptance criteria

- **AC-1**: `breadcrumbs/README.md` documents the tier vocabulary (`detect`/`enforce`/`retire`), the mandatory inline-comment convention from the RFC body, and the detect→enforce promotion rule.
- **AC-2**: At least three existing constructs are tagged as worked examples, chosen to span the vocabulary: one `enforce` (e.g., `_create_channel`), one `detect` (e.g., a metric that warns but does not block), one `retire` (e.g., one of the retired guardrails RFC-033 names).
- **AC-3**: RFC-033 is moved to `resolved/` with a note: "Superseded by RFC-037; the guardrail-specific lifecycle is now a special case of the general tier vocabulary."
- **AC-4**: RFC-037 status flips to `implemented`.

### Implementation steps

1. Pick three constructs and tag them with the comment convention. Concrete candidates I'd start with:
   - `factory/runner.py:_create_channel` — `tier: enforce`, precondition `AGENTS.md channel status table`, audit trigger `re-evaluate when any channel moves between validated/unvalidated/disabled`.
   - The `claim_near_budget` log warning — `tier: detect` (signals but does not block; the surrounding state machine handles escalation).
   - The retired `max_idle_cycles` guardrail from `wrapper/` — `tier: retire` with a comment noting the precondition that justified retirement.
2. Edit `breadcrumbs/README.md` to introduce the tier vocabulary, citing the RFC and pointing at the three worked examples.
3. Move RFC-033 to `resolved/` with a one-paragraph `## Resolution` noting RFC-037 supersedes it.
4. Flip RFC-037 status.

### Follow-up (Sonnet)

Once the pattern is established, hand Sonnet a scoped audit task: "go through `factory/gate/*.py` and tag each gate function with `# tier: enforce` and a precondition comment. Where the gate today reports a finding but does not block (i.e. acts as `detect`), tag it accordingly and file a BC for any that *should* be `enforce` but aren't." That audit produces concrete BCs and shouldn't be in this RFC's scope.

---

## 4. RFC-029 — Attempt-count telemetry bucketing

**Implementer: Sonnet** (pure aggregation refactor; existing data; clear inputs/outputs)

### Why Sonnet

The data is already collected (`SubmitPayload.inner_gate_attempts` in `event_schemas.py:28`). No behavior change. New aggregations on existing fields. The judgment calls (bucket boundaries, label names) are spelled out in the RFC. This is the kind of work Sonnet does well without supervision.

### Acceptance criteria

- **AC-1**: `factory/telemetry.py` adds the four bucket fields described in the RFC: `inner_gate_attempt_0_pass_rate`, `inner_gate_attempt_1_recovery_rate`, `inner_gate_attempt_2plus_rate`, `inner_gate_exhausted_budget_rate`.
- **AC-2**: The existing aggregate `inner_gate_first_pass_rate` is preserved (continuity).
- **AC-3**: A per-item attempt log is added to the run summary so hard-tail items can be named.
- **AC-4**: Backfill: the aggregator can be run against historical `SubmitPayload`s from GR-021 onward (when `inner_gate_attempts` started being recorded).
- **AC-5**: Tests covering the four buckets across synthetic event sequences.
- **AC-6**: RFC-029 status flips to `implemented`.

### Implementation steps

1. Read `telemetry.py:82-192` (the existing aggregation block).
2. Add per-attempt bucket computation alongside the existing aggregate. The data structure is `list[InnerGateAttempt]` from `SubmitPayload.inner_gate_attempts`.
3. Surface the new fields in the summary formatter.
4. Add per-item attempt log (sorted by total attempts descending, so hard-tail items are at the top).
5. Tests: synthetic SubmitPayloads exercising each bucket; backfill against a saved GR-038 dataset if available.
6. Flip RFC-029 status.

### Notes for the implementer

The validation experiment proposed at the end of RFC-029 (A/B at `inner_gate_retries=1` vs `=3`) is *not* part of this work — it's a separate run-the-pipeline exercise that consumes the new metric. Keep the implementation scoped to telemetry only.

---

## 5. RFC-035 — Data-driven channel placement layer

**Implementer: Opus (me)** for design + initial implementation; Sonnet for additional policy implementations once the framework is in place

### Why Opus

This is a phase-3-blocker with multiple still-open design questions in the RFC body (substrate vs. `runs/` as data source; how to compose with the principal-review surface in RFC-026; what policy primitives to expose). Implementing the wrong shape commits the principal to YAML-edit-by-hand workflows that the RFC is trying to replace.

### Acceptance criteria

- **AC-1**: `factory/placement.py` module exists with `propose`, `PlacementPolicy`, and `apply` per the RFC.
- **AC-2**: Three modes for `apply`: `dry-run` (default, writes diff to `runs/`), `propose-pr` (opens PR), `live` (rewrites YAML; gated behind explicit flag).
- **AC-3**: At least one `PlacementPolicy` implementation: "highest pass rate with ≥ N samples and ≥ K confidence; fall back to current."
- **AC-4**: Test on GR-038 dataset produces a non-empty diff with rationale per change.
- **AC-5**: RFC-035 status flips to `implemented`.

### Implementation steps

1. Resolve the substrate-vs-runs question first (RFC says substrate; needs verification that `compute_pass_rates` exposes everything needed).
2. Build the `Placement.propose` API. Returns a structured diff object, not a mutated config.
3. Implement the first `PlacementPolicy`. Defer cost-minimizing and Anthropic-preference policies to follow-ups.
4. Implement the three apply modes. `live` mode should require both a flag *and* a confirmation prompt in interactive contexts.
5. CLI: `factory placement propose --history-from substrate --policy highest-pass-rate --output runs/placement-NNN.diff`.
6. Tests on synthetic + GR-038 datasets.
7. Flip RFC-035 status.

### Dependencies

- RFC-034 (model identity in telemetry) is already `implemented` per the RFC backlog — confirmed precondition met.
- Coordinate with RFC-026 (principal review surface): placement diffs should be a first-class object in the principal's review bundle. If RFC-026 lands first, slot in; if RFC-035 lands first, leave a hook.

---

## 6. RFC-024 — Coherence reviewer (force the decision)

**Implementer: Kimi/GLM (delete path) OR Opus + principal (build path)**

### The decision

`coherence_reviewer` is currently dead configuration declared in three places (`spec.md §4`, `spec.md §5`, `constants.py:28`, `workflows/full_pipeline.yaml`) with zero implementation. This is simultaneously a CLASS-001 instance (entry-point drift) and a CLASS-012 instance (string-constant gravity). The current state is the worst of both worlds.

Principal must choose:

#### Path A — delete (Kimi/GLM, ~30 minutes)

- Remove `ROLE_COHERENCE_REVIEWER` from `constants.py`.
- Remove the role from `workflows/full_pipeline.yaml`.
- Remove the spec.md §4 line 103 reference and §5 line 135 entry.
- Move RFC-024 to `resolved/` with a `## Resolution` noting the role was removed pending evidence of need.

#### Path B — build (Opus + principal, weeks)

- RFC-024 body needs to be completed — the design questions in §"Design questions" are real and unanswered.
- The principal needs to commit to the placement (after integration, before outcome verification per the RFC's suggestion).
- Build prompts, routing, tests.
- Phase 6+ work; nothing should be added to the codebase before the design questions are answered.

### Recommendation

Path A. Phase 5 fixtures don't exercise multi-module structural coherence at a scale where this role's "long-context advantage" matters. If real workloads in Phase 6 demonstrate a coherence gap that the integrator + outcome_verifier miss, file a new RFC then with concrete evidence. Premature roles are CLASS-012 fuel.

---

## 7. RFC-026 — Principal review surface

**Implementer: Opus + principal** (design-heavy; needs principal input on bundle format and feedback intake mechanism)

### Why this isn't Sonnet

The four open design questions in the RFC body are all decisions the principal owns:
1. What goes in the bundle?
2. How is it presented (tarball, directory, CLI)?
3. How does feedback enter (spec edit + re-run, structured CLI, diff format)?
4. How does re-run work (full reset vs. surgical)?

These are not implementation choices — they're product-design choices that bind future workflows. Sonnet can implement once the answers exist, but cannot answer them.

### Acceptance criteria (deferred until design questions resolved)

- **AC-1**: A design memo lives at `plans/principal-review-surface.md` answering the four questions above, signed by the principal.
- **AC-2**: `factory/report.py` is updated to produce the agreed bundle format (this fixes BC-045 in the process — the `workflow_version=1` hardcode that the RFC body cites).
- **AC-3**: A feedback intake CLI exists.
- **AC-4**: RFC-026 status flips to `implemented`.

### Implementation steps

1. **Design phase (Opus + principal):** Write the memo. Likely takes one synchronous session with the principal.
2. **Implementation phase (Sonnet, once design is locked):** Implement the bundle producer, feedback intake CLI, and re-run logic against the design.

### Note

The RFC marks itself "Phase 6 needed." I'd push back: Phase 5 (synthetic fixture validation) is still the right time to *design* this. Phase 6 (first real workload) is when the implementation must exist. If the design lags into Phase 6, the workload arrives without a review surface.

---

## Tier summary

| RFC | Implementer | Effort | Blocker for |
|---|---|---|---|
| RFC-030 enforcement | Sonnet | ~half-day | Meta-defense cluster |
| RFC-031 schema | Kimi/GLM | ~30 min | — |
| RFC-037 framework | Opus | ~half-day | RFC-033 closure |
| RFC-033 closure | Kimi/GLM | ~15 min | — |
| RFC-029 telemetry | Sonnet | ~half-day | Adversarial-readiness-001 debate |
| RFC-035 placement | Opus | ~2 days | Phase 3 expansion |
| RFC-024 path A | Kimi/GLM | ~30 min | — |
| RFC-024 path B | Opus + principal | weeks | (only if chosen) |
| RFC-026 design | Opus + principal | ~half-day session | RFC-026 implementation |
| RFC-026 implementation | Sonnet | ~1 day | First real workload |

## Suggested ordering

1. **Now (Kimi/GLM):** RFC-031 schema, RFC-033 closure, RFC-024 path A.
2. **This week (Sonnet):** RFC-030 enforcement, RFC-029 telemetry.
3. **This week (Opus):** RFC-037 framework + first tagged examples.
4. **Next (Opus + principal):** RFC-026 design memo session.
5. **After RFC-026 design lands (Sonnet):** RFC-026 implementation.
6. **Before Phase 3 expansion (Opus):** RFC-035 placement layer.

This ordering keeps the meta-defense cluster (RFC-030/031/037) landing first — they're the cheapest and they're the prerequisite for not re-creating the same RFC pileup with the next round of work.
