---
number: "011"
title: "Prompt versioning in telemetry — confounded channel comparisons"
author: glm-5.1
date: "2026-05-09"
related: ["002", "009", "BC-068", "BC-039"]
---

## Context

The telemetry reporter (`telemetry.py`) computes first-attempt and overall pass rates per `(role, channel, family, gate_name)`. This data drives Phase 3 fleet placement decisions (spec §5: *"Per-role per-channel telemetry drives model placement... updated based on data, not vibes"*).

The factory has three role-specific prompt templates (`interface_architect.md`, `test_author.md`, `implementer.md`) loaded by role name from `src/factory/prompts/`. These templates are unversioned markdown files with no changelog header or semantic version.

Between golden runs, prompts change. BC-039 updated `implementer.md` with modern typing conventions and ruff-format instructions. Future changes are inevitable as prompt quality improves based on escalation analysis.

## Problem

GR004 and GR005 produced different pass rates (80% vs 87% implementations). The telemetry attributes this difference to the channel (Sonnet vs Kimi k2.6). But if the implementer prompt changed between the two runs, the comparison is confounded: is the 7-point improvement due to the channel or the prompt?

More broadly: the telemetry report groups by `(role, channel, family, gate_name)` but ignores the prompt template version. Any comparison across golden runs — or across Phase 3 channel configurations — may be confounded by untracked prompt changes.

This is the same class of problem as BC-068 (silent data degradation): the data looks valid (gate names are correct, pass rates compute) but the analytical conclusion is wrong because a confounding variable is unmeasured.

## Position

**Add prompt template hash to telemetry grouping.** Track which prompt version produced each outcome so channel comparisons control for prompt changes.

### Proposed design

1. **At invocation time:** compute `prompt_template_hash = sha256(prompt_template.read_text())` per role. Store in `actor_metadata.prompt_template_hash` alongside the existing `context_hash`.

2. **In telemetry:** add `prompt_template_hash` to `GateAttempt`. Group pass rates by `(role, channel, family, gate_name, prompt_template_hash)`.

3. **In the pass rate report:** if a `(role, channel)` group has multiple `prompt_template_hash` values, emit a warning: "Prompt changed mid-comparison. Results may be confounded."

4. **In golden run configs:** optionally record `prompt_template_hash` for each role. This allows post-hoc verification that the config's hash matches the run's hash.

### Why hash, not version number

A semantic version (v1, v2) requires manual maintenance — someone must bump the version when the prompt changes. A content hash is automatic and tamper-evident. The telemetry report can show the hash (or a truncated prefix) alongside the pass rate table. When two runs share the same hash, the comparison is clean. When hashes differ, the reader knows to investigate.

### Why not the existing `context_hash`

`context_hash` in `context.py` is a composite SHA-256 of the entire prompt bundle (template + spec section + AC IDs + glossary + prior failures). It changes on every invocation because prior failures differ. It cannot be used to group outcomes by prompt version — it conflates prompt changes with retry-context changes.

`prompt_template_hash` hashes only the template file content. It changes only when the prompt template changes. This is the correct granularity for deconfounding.

### Cost

~20 lines of code. No new dependencies. No changes to prompt files themselves (no version headers needed).

## Risks

| Risk | Mitigation |
|---|---|
| Hash doesn't tell you WHAT changed | Store the hash; when hashes differ, diff the prompt files manually. This is an investigation, not a pipeline operation |
| Prompts change frequently during development | During Phase 2-3, prompt churn is expected. The hash makes churn visible, which is the point |
| Grouping by hash fragments the telemetry table | If N hashes exist for the same role, the table has N rows. This is correct — it shows that the data is partitioned |

## Blocking

Phase 3 (fleet integration). The first multi-channel comparison is the most critical — if it's confounded by an untracked prompt change, the fleet placement decision is based on faulty data and the error propagates through Phase 4 and Phase 5.

## Next step

1. Add `prompt_template_hash` to `derive_context()` output and `ActorMetadata`
2. Add `prompt_template_hash` to `GateAttempt` dataclass
3. Update `compute_pass_rates()` to group by hash
4. Add confounding warning to `format_pass_rate_table()`
5. One test: synthetic events with two different hashes → warning emitted
