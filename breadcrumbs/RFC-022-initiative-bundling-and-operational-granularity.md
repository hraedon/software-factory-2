---
number: "RFC-022"
title: "Initiative primitive for work-item bundling and operational granularity"
severity: medium
status: proposed
kind: design
author: opus-4-7
date: "2026-05-13"
tags: [scheduler, telemetry, substrate, operations, phase-5, dep-substrate-future]
related: ["RFC-017", "RFC-018", "RFC-020"]
phase_needed: "Phase 5 (first real workload)"
---

## Problem

sf2 has work items as the atomic unit (substrate's `work_item`, ID-addressable, lifecycle-tracked via the event log). What it does not have is a first-class concept for "this set of related work items moves together and is operated on as a unit."

Today the implicit grouping is "all work items derived from one spec." That grouping is a query (`SELECT * FROM work_items WHERE workflow_run_id = ?`), not a tracked entity. Three consequences once Phase 5 lands and workloads grow:

1. **No aggregate stall detection.** Per-work-item retry budgets exist, but no signal for "the entire spec hasn't emitted a substrate event in 20 minutes." A wedged run that's silently stuck on inter-work-item scheduling is invisible until a human notices.
2. **Reporting requires JOINs.** "How did this fixture perform?" or "what was the lock rate for cert-watch full vs. cert-watch-mini?" is recomputed by hand for every analysis. Telemetry currently aggregates by role/channel/gate, not by spec/initiative.
3. **No bulk operations.** Cancelling, requeueing, or marking-failed a whole spec's worth of work items requires either substrate-level surgery or a custom script. There is no `cancel_initiative` primitive.

The gastown project's "convoy/bead" model is one expression of this idea. The bead half is already sf2's work item, so adoption is purely a question of whether the convoy-equivalent earns its keep. This RFC proposes a neutrally-named primitive (working term: **initiative**) and scopes what it should and should not do.

## Naming

Working name: **initiative**. Rationale:
- `feature` collides with `functional_requirement` (FR-NN) which is already a load-bearing term in spec.md vocabulary.
- `convoy` is gastown's term and carries opinionated semantics (mountain labels, auto-skip) that this RFC explicitly does not adopt.
- `bundle`, `batch`, `cohort` are workable alternatives if `initiative` reads too corporate.

Final naming is a bikeshed; the data model is the load-bearing decision.

## Scope

### In scope

1. **`initiative_id` attribute on work items**
   - Substrate adds an optional `initiative_id` column (or custom field, depending on substrate's preferred extension mechanism) on `work_items`.
   - `populate_work_items.py` assigns one initiative_id per spec invocation (default), with override capability for cross-spec or multi-fixture runs.
   - Backfill not required; old work items have `initiative_id = NULL` and are excluded from initiative-level queries.

2. **Initiative-level event aggregation**
   - Telemetry computes per-initiative rollups: lock rate, mean attempts, first-attempt pass rate, wall-clock duration.
   - These are derived from the existing event log; no new event types required.

3. **Stall detection at the initiative layer**
   - A periodic checker (could live in the scheduler or as a separate `factory.watchdog` module) computes `max(event_timestamp) WHERE initiative_id = ?` and flags initiatives whose freshest event is older than a configurable threshold (default 20 min).
   - Detection only. Response is to emit a structured log event and/or write a breadcrumb. Never silent action.

4. **Bulk operations**
   - `cancel_initiative(initiative_id, reason)` — marks all non-terminal work items in the initiative as `cannot_proceed` with a shared reason string. Emits substrate events for each.
   - `requeue_initiative(initiative_id)` — resets failed work items in the initiative to `new` for reprocessing. Idempotent.
   - Both are CLI-invoked, not autonomous.

### Deferred (later RFC if validated need emerges)

- **Initiative-level retry budgets.** Per-work-item budgets are working; an aggregate budget across an initiative would let us enforce "this spec gets at most $X of model spend" but it's a Phase 6+ concern.
- **Initiative-level gate decisions.** "Don't run downstream stages if more than 30% of upstream items failed" is a real escalation pattern but premature now.
- **Cross-initiative dependencies.** Multi-spec runs with explicit ordering between initiatives. Phase 6+.

### Explicitly out of scope (won't build)

- **Autonomous skip logic.** No "mountain label triggers smart skip of stalled work items and the system continues without them." The cost of orchestration making autonomous abandonment decisions, against partial information, without escalation, is exactly the v1 failure pattern. Stall detection is good; stall *response* is "page a human / file a breadcrumb," not "skip and continue."
- **Auto-classification of initiatives by size/complexity.** The principal labels (or doesn't); the system does not infer.
- **Vocabulary rename of work_item → bead.** No utility, only churn.

## Why this is a Phase 5 prerequisite, not now

Three thresholds need to cross before initiatives earn their keep, none of which is true today:

1. Workloads big enough that per-work-item monitoring is noisy. Current golden runs are 15–24 items; `tail -f` works.
2. Multi-spec or multi-fixture runs where initiative-level aggregation answers questions that are currently recomputed by hand.
3. Operational pain from manual stall recovery. Golden runs are short enough that wedges are caught within a few minutes.

Phase 5 plausibly crosses all three: real workloads will have more work items per spec (integrator + outcome_verifier add stages), workloads will need archetype-aware reporting per RFC-020, and operational survivability (RFC-017) explicitly contemplates longer-running scenarios where silent wedges become a real risk.

## Layering: what lives in factory vs. substrate

Substrate review (2026-05-13) confirmed the layering should sequence in two phases:

**Phase A — entirely in factory, zero substrate work.**

Substrate's existing `custom_fields` mechanism (validated per-work-item-type via `CustomFieldDef` schemas; already used by sf2 for `dependency_refs`, `ac_ids`, `spec_section`, etc.) is sufficient to store `initiative_id` today. Factory:

- Declares `initiative_id` as a custom field on relevant work_item types in `phase5.yaml` (and back-fillable in earlier workflow files if needed).
- Sets the field at `populate_work_items.py` time (one initiative_id per spec invocation by default; CLI override for cross-spec runs).
- Wraps read/write in a thin `factory/initiative.py` module so callers don't see substrate plumbing.
- Implements telemetry rollups by paging `query_work_items` and filtering client-side on `custom_fields["initiative_id"]`.
- Implements the watchdog (stall detector) the same way — page the event log per initiative, check freshest timestamp.
- Implements `cancel_initiative` / `requeue_initiative` as factory-side loops over substrate's existing per-item mutations.

This is correct for the scale Phase 5 will hit. It is *not* correct at large scale because:

- `query_work_items` (substrate/__init__.py:799) does not filter on custom_fields; client-side filtering means paging all items and discarding most.
- No bulk-update primitive exists; cancel_initiative is N individual mutations rather than one transaction.

**Phase B — substrate gains primitives, factory consumes them.**

Only when Phase A's limitations produce measurable pain (slow telemetry, watchdog DB thrash, cancellation latency), file substrate breadcrumbs requesting:

1. **Custom-field-filtered query — promoted out of this RFC.** Filed independently as substrate BC-139 (2026-05-13) because the gap is generic to any custom_fields consumer, not specific to initiatives. RFC-022 consumes whatever surface substrate ships; the design decisions (containment vs. per-key, validation strictness, etc.) belong to substrate.
2. **Bulk mutation primitive.** Generic `bulk_update_work_items(filter, mutation, reason)` that emits substrate events per item but executes in one transaction. The semantics question (one bulk event vs. N per-item events) is substrate's to decide; the resolution probably mirrors how substrate already handles bulk claim release. Stays speculative until Phase A demonstrates need.
3. **Optional: indexed first-class column.** Promote `initiative_id` from a custom field to a real column with an index, only if query plans show the JSONB lookup is the bottleneck after BC-139's GIN index is in place. This is the most invasive change and should be the last resort.

Substrate naming and concept ownership stays with factory throughout. Substrate provides typed group attribution + bulk-update primitives; substrate never knows what an "initiative" is, the same way it doesn't know what an interface_spec or jury_verdict is.

## Cost estimate

**Phase A:** small. 1–2 sessions if built standalone, less if folded into RFC-017 (operational survivability) work since RFC-017 already proposes a watchdog.

**Phase B:** moderate, substrate-side. Custom-field-filtered query is a query-builder change + tests. Bulk mutation primitive interacts with substrate's event-emission contract and replay semantics — non-trivial design work, exactly the kind of thing that should wait until Phase A proves the need.

## Open questions

1. Should initiative_id live on substrate's `work_item` table directly, or as a custom field? Substrate's data-model authority makes this their call.
2. Should the watchdog be a separate process (parallel to runner/gate/scheduler) or a periodic task in the scheduler? Argues for separate, but adds a process to the operational footprint.
3. Should `cancel_initiative` emit one bulk event or N per-item events? Bulk is cleaner for replay; N preserves per-item granularity. Substrate's event semantics probably dictate the answer.

## Relationship to other RFCs

- **RFC-017 (operational survivability):** the watchdog described there could naturally host the stall detector proposed here. Consider folding.
- **RFC-018 (live state reporter):** would consume initiative_id as a primary grouping dimension; RFC-022 is a structural prerequisite for the live reporter to answer "how is initiative X doing" without a JOIN.
- **RFC-020 (project archetype catalog):** initiatives are the natural carrier of archetype metadata.

## Decision criteria

This RFC moves from `proposed` to `accepted` only when at least one of:
- A Phase 5 golden run produces enough work items that per-item monitoring becomes operationally noisy.
- A multi-spec or multi-fixture run is on the near roadmap and would benefit from initiative-level reporting.
- Manual stall recovery becomes a recurring pain point in worklog entries.

Until then: filed, not built.
