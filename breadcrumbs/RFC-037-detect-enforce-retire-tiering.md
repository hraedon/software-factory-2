---
number: "RFC-037"
title: "Detect → enforce → retire: explicit tiering for gates, contracts, and status fields"
severity: medium
status: proposed
kind: design
author: claude
date: "2026-05-19"
tags: [process, gates, contracts, meta-defense, v1-lesson, dep-substrate]
related: ["RFC-030", "RFC-033", "RFC-032"]
---

## Motivation

A cross-project survey of sf2, substrate, and software-factory v1 turned up the same shape in many places: a check or contract exists, signals correctly, and is ignored at the point of action.

Examples:

- **sf2 channels**: AGENTS.md marks GLM-5.1, DeepSeek, Gemini as unvalidated, but `_create_channel` still constructs them and spec §5 still lists them in the capability table.
- **substrate `allowed_roles`**: workflow YAML declares allowed roles per transition; both InMemory and Postgres backends accept `transition(..., actor_metadata={"role": "X"})` even when `register_actor_role("X")` was never called.
- **sf v1 gates**: Stage 7.5 reported orphan-services with `severity: high` for four consecutive cert-watch-7 phases; the pipeline completed regardless. BC-190 calls the pattern "systemic" but treats each instance as a separate gate bug.
- **sf2 README vs files**: BC-126/127 listed as `implemented` in the index, `proposed` in the file (debate `adversarial-readiness-001`).
- **sf v1 fixit layer**: skeleton stubs aren't runnable; a fixit pass exists to bandage the symptom rather than fix stub generation.

In each case the signal exists; the *commitment level* of that signal does not. There is no shared language to ask "is this check informational, blocking, or obsolete?" and no rule that forces the answer to be written down.

RFC-033 covers exactly this problem for one class — heuristic guardrails. This RFC generalises the same shape (declare precondition, declare audit trigger) to the broader category of gates, allowlists, status fields, and contract assertions.

## Proposal

Every signal-emitting construct that gates, blocks, or describes operational state must carry a declared **tier** from this set:

- **detect** — observes a condition, emits a structured signal, never blocks. Suitable for new checks before calibration, or for diagnostic-only telemetry.
- **enforce** — observation produces a hard outcome: refuses an action, fails a build, fatally aborts a run, or refuses to construct an object. Suitable once the precondition is stable and the false-positive rate is acceptable.
- **retire** — the underlying failure mode is structurally eliminated; the construct exists only as a historical comment or test, and produces no live signal.

Three rules apply:

1. **Declared tier is mandatory.** No new check, gate, or status enum value lands without a tier declaration adjacent to its definition. The tier is part of the code, not a separate registry (same locality argument as RFC-033).
2. **Detect → enforce promotion requires a precondition statement.** Before a check moves from detect to enforce, its definition must name (a) the BC(s) or invariants that made the false-positive rate acceptable, and (b) an audit trigger (same form as RFC-033 §Proposal).
3. **A status field that says "X is disabled" must match the code that constructs X.** If `AGENTS.md`, a spec table, or a debate file declares something disabled/unvalidated/deprecated, the construction site (factory, registry, YAML allowlist) must either refuse to instantiate it or carry an inline `# tier: detect (status: $LABEL)` comment that names where the declared status lives. The cheap form of this rule: declared-disabled → constructor raises; declared-deprecated → constructor warns once; declared-experimental → constructor logs at info.

## What this retires

This RFC explicitly subsumes the following ad-hoc patterns and supersedes them where they conflict:

- The implicit assumption that a `status: high` gate output is action-forcing. Under this RFC, action-forcing requires `tier: enforce` at the gate definition. Pipelines that "complete with high-severity findings" are not bugs in the gate; they are gates wrongly tiered as `detect`.
- The convention of marking things "disabled" in prose docs without a matching code change. Under this RFC, the prose claim is unsupported unless the constructor enforces it.

## Worked examples

**sf2 channel registry (`_create_channel`):**

```python
# tier: enforce
# precondition: AGENTS.md "channel status" table is the source of truth
# audit trigger: re-evaluate when any channel moves between validated/unvalidated/disabled
def _create_channel(name: str) -> Channel:
    status = CHANNEL_STATUS[name]
    if status == "disabled":
        raise ChannelDisabled(name)
    if status == "unvalidated":
        warnings.warn(f"channel {name} is unvalidated; see AGENTS.md", stacklevel=2)
    return _BUILDERS[name]()
```

Result: GLM/DeepSeek/Gemini cannot be silently used; the spec §5 table and the constructor are forced into sync by the next test run.

**substrate `allowed_roles`:**

```python
# tier: detect (current)
# precondition for promote-to-enforce: BC-XXX (role-registration audit) closed
# audit trigger: re-evaluate when role-registration audit lands
```

Promotion path is documented in code; the gap (declared but not enforced) is no longer a silent surprise to second consumers like watchpost.

**sf v1 Stage 7.5 orphan-services check:**

```python
# tier: detect
# rationale: false-positive rate from skeleton-mode partial wiring still > 0
# promotion path: when BC-264 (per-FR deps files) lands, re-tier to enforce
```

The gate continues to emit signals, but the silence about whether the pipeline should stop is replaced by an explicit declaration.

## Why a unified tiering instead of per-construct policies

Because the failure mode is uniform. Across the three repos, the bug is never "the check was wrong" — it is "the commitment level of the check was undeclared, and a reader assumed the stronger meaning." A single shared vocabulary makes the assumption impossible to leave implicit, and lets a single grep (`# tier: detect`) audit every construct in a repo at once.

This RFC does not invent a new system; it is a naming + locality discipline imposed on constructs that already exist.

## Operational cost

- One-line tag per construct on first introduction.
- One audit pass per repo to tag existing constructs (estimated: sf2 ~30 sites, substrate ~15, v1 ~50, dominated by gates and channel-like registries). The audit can be incremental — touch a site, tag it.
- One CI rule (optional, deferred): a lint that fails if a new gate/check definition is added without a `# tier:` comment within N lines.

## Acceptance criteria

- **AC-1**: This RFC filed.
- **AC-2**: A short "Tiering" subsection added to `AGENTS.md` under the existing process section, with a pointer here and the three-line vocabulary (detect / enforce / retire).
- **AC-3**: The sf2 channel registry (`_create_channel`) tagged per the worked example above, and the GLM/DeepSeek/Gemini code paths reconciled with the AGENTS.md status table (either raise on construction or carry the warn-and-document path). Filed as a separate BC under this RFC.
- **AC-4**: One cross-repo note: substrate's `allowed_roles` enforcement gap (currently `tier: detect` implicitly) is filed as a substrate BC referencing this RFC, so consumers like watchpost have a tracked path to the eventual promotion.

## Out of scope

- Substrate state-machine invariants (claim TTL, schema isolation): these are not heuristic checks; they are hard semantic constraints. They are always `tier: enforce` by construction and do not need a declaration.
- Test-only assertions: tiering is for production constructs that affect operational state, not for in-test invariants.
- Retroactive tagging of *all* existing constructs in one pass: AC-3/4 cover the highest-leverage examples; the rest can be tagged incrementally as files are touched.
