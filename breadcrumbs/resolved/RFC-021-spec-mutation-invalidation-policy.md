---
number: "RFC-021"
title: "Spec mutation and invalidation policy"
severity: high
status: implemented
kind: design
author: opencode-review
date: "2026-05-13"
tags: [spec, evolution, stage-0, stage-1, phase-5, dep-v1-spec-evolution]
related: ["120", "RFC-020", "RFC-019"]
phase_needed: "Phase 5 (first real workload)"
---

## Problem

Spec Principle 8 says: *"Errors loop back to contract revision, not worker retry."* Spec §9.10 says: *"Long-term memory is the spec."*

What is not documented anywhere:
- What happens when the principal edits `spec.md` mid-pipeline?
- Which work items invalidate?
- Does the pipeline restart from Stage 0, or surgically?
- Who triggers re-population?

v1 had `spec_evolution.py` — spec versioning, drift detection, and transformation rules between schema versions. It was likely overbuilt, but the underlying question is real. If v2's Phase 5 picks a real workload and the principal iterates on the spec (as they will), there must be a documented policy rather than each agent inventing a different answer.

Spec §10 does not address spec mutation post-Stage 0.

## Scope

### In scope

1. **Spec hash tracking**
   - `populate_work_items.py` computes a SHA-256 hash of the spec files (`spec.md` + `spec.yaml` + any sidecars in `spec_dir/`).
   - Stores `spec_hash` as a workflow-level custom field (or metadata field if regista supports it; otherwise as an annotation on the first work item).
   - On subsequent runs, compares the computed hash to the stored hash.

2. **Invalidation policy**
   - **If spec_hash matches**: no invalidation. Continue from current regista state.
   - **If spec_hash differs**: compute a fine-grained diff of `spec.yaml` work items.
     - Work items whose `AC` or `FR` entries changed → invalidate to `new`.
     - Work items whose `dependency_refs` changed → invalidate to `new` + invalidate all transitive descendants.
     - Work items unchanged → preserve state.
   - Unmatched changes (free-text in `spec.md` not reflected in `spec.yaml`) trigger a conservative fallback: invalidate all work items of the same `type` as the section that changed.

3. **Re-population trigger**
   - Manual: `populate_work_items.py --config <yaml> --invalidate-changed` (default: check hash, invalidate, exit with summary).
   - Opt-in automatic: if the runner detects `spec_hash` mismatch on startup, log a warning and continue with existing work items (never auto-invalidate; the principal must confirm).

4. **Principal interaction surface**
   - `populate_work_items.py` prints a diff summary:
     ```
     Spec hash changed (old: abc123, new: def456)
     Invalidated: 3 work items (wi_001, wi_005, wi_007)
     Preserved: 21 work items
     Run with --apply-invalidation to update regista state.
     ```
   - The principal reviews the summary, then runs with `--apply-invalidation`.

### Out of scope (future phases)

- Automatic semantic diff of natural-language `spec.md` (requires NLP or model assistance; too risky for Phase 5).
- Bidirectional sync (factory writes back to `spec.md`). The factory never writes to the principal's spec.
- Spec versioning with upgrade transformations (v1 `spec_evolution.py` scope).
- Merge conflict resolution if multiple principals edit the spec.

## Design

### `factory/spec_hash.py`

```python
@dataclass
class SpecHash:
    hash_hex: str
    files: list[Path]
    computed_at: datetime

class SpecHasher:
    def __init__(self, spec_dir: Path): ...
    def compute(self) -> SpecHash: ...
    def store(self, sub: Regista, workflow_id: str, spec_hash: SpecHash) -> None: ...
    def load(self, sub: Regista, workflow_id: str) -> SpecHash | None: ...
    def diff(
        self,
        sub: Regista,
        old: SpecHash,
        new: SpecHash,
    ) -> list[str]:  # work_item_ids to invalidate
        ...
```

### Invalidation logic

```
def invalidate_work_items(sub: Regista, old_work_items: list[WorkItem], new_spec: Spec) -> list[str]:
    # 1. Map old work items by their FR/AC identifier
    old_by_fr = {wi.custom_fields["fr_id"]: wi for wi in old_work_items}

    # 2. Compare new spec FRs to old
    changed_fr_ids = set()
    for fr in new_spec.functional_requirements:
        old_wi = old_by_fr.get(fr.id)
        if old_wi is None or old_wi.spec_hash != new_spec.hash:
            changed_fr_ids.add(fr.id)

    # 3. Collect transitive descendants
    to_invalidate = set(changed_fr_ids)
    for fr_id in changed_fr_ids:
        for desc in dependency_graph.descendants(fr_id):
            to_invalidate.add(desc)

    return list(to_invalidate)
```

### Regista interaction

- If regista adds a `workflow_metadata` field, `spec_hash` goes there.
- If not, `spec_hash` is stored as a custom field on the root work item (the first `interface_spec` created by `populate_work_items.py`).
- Invalidation is performed by `sub.transition(work_item_id, "invalidate")` or equivalent state reset. If regista does not support a dedicated transition, the fallback is to create new work items with incremented versions and link them as replacements (more conservative, more regista load).

## Configuration

```python
@dataclass
class SpecEvolutionConfig:
    spec_dir: Path | None = None  # defaults to fixture dir or workspace_root
    auto_detect_changes: bool = True  # hash check on populate; never auto-apply
    conservative_invalidation: bool = False  # if True, invalidate all on any change
```

## Phase placement

Phase 5 prerequisite. The principal will iterate on the spec during the first real workload. Without a policy, each agent will handle this differently.

## Validation criteria

1. Running `populate_work_items.py` twice with the same spec produces no invalidations.
2. Editing one AC in `spec.yaml` and re-running `populate_work_items.py` invalidates only the affected work item and its descendants.
3. The diff summary printed to stdout is accurate (verified against regista state after `--apply-invalidation`).
4. No regista API changes required for Phase 5 MVP (custom_field fallback is acceptable).

## Open questions

1. Should `spec.md` changes that do not affect `spec.yaml` (e.g., wording clarifications) trigger invalidation? Conservative answer: no, unless the principal explicitly passes `--force-invalidation`.
2. Should the factory support multiple spec files (modular specs)? Defer to Phase 6. Phase 5 assumes a single `spec.md` + `spec.yaml` pair.
3. What is the regista state transition for invalidation? If regista has no `invalidate` transition, is creating replacement work items acceptable? Yes for Phase 5.

## Precedent

- v1 `factory/spec_evolution.py` — spec versioning, drift detection, and transformation rules between schema versions. v2 intentionally narrows scope to hash-based invalidation, not full evolution.
- Regista's event sourcing model — invalidation is a new event, not a mutation, preserving audit trail.
