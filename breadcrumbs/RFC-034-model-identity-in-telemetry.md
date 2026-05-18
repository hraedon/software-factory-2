---
number: "RFC-034"
title: "Capture model identity (resolved model string) in telemetry keys"
severity: high
status: proposed
kind: design
author: claude
date: "2026-05-18"
tags: [telemetry, placement, phase-3-blocker, BC-068-followup]
related: ["192"]
---

# RFC-034 — Add `model` to telemetry keys; close the model-version drift gap

## Motivation

Spec principle 10: "Per-role per-channel telemetry drives model placement." The current pass-rate key is `(role, channel, family, gate_name, prompt_template_hash)` (see `src/factory/telemetry.py` — `GateAttempt`, `PassRateRow`, `compute_pass_rates`). `ArtifactManifest` is built with `model=None` (`src/factory/runner.py:545`); `ActorMetadata` does not carry a resolved model field.

Consequence: when a channel's underlying model version changes — e.g., `kimi-k2.6-turbo` → `kimi-k2.7-turbo` behind the same channel, or Anthropic transparently rolling Sonnet's snapshot — historical pass rates merge silently. Every placement decision is then made over a confounded sample. This is exactly the silent-data-degradation pattern BC-068 + prompt-template-hash plumbing was supposed to close, but one slice over (template held constant, model varied).

This is a Phase-3 blocker: without it, the entire "data-driven placement" premise is unsound.

## Proposal

1. Extend `ActorMetadata` with a `model: str` field. The channel adapter is responsible for resolving it at invocation time (subprocess channel reads the `--model` flag value; opencode channel reads its config; etc.).
2. Plumb `model` through `ArtifactManifest` (drop the `model=None` initializer in `runner.py:545`) and into `GateAttempt`.
3. Extend `PassRateRow`'s key to `(role, channel, model, family, gate_name, prompt_template_hash)`.
4. Migration: existing rows have `model=NULL`; new code treats NULL as a distinct bucket and emits a warning in `format_pass_rate_table` if NULL rows are present. After one golden run on the new schema, old rows can be archived.
5. Update `format_pass_rate_table` to include the `model` column, and update `run_telemetry_verify` to require it on new rows.

## Alternatives considered

- **Composite channel name.** Treat `kimi-k2.6-turbo` and `kimi-k2.7-turbo` as separate channels. Cheap but lies about the substrate: a "channel" is a transport (opencode subprocess, claude-code CLI), not a model. This conflation makes the per-(role, channel) table useless for the other thing it should answer ("is opencode-the-transport reliable").
- **Telemetry tag, not key.** Record model as a free-form tag; aggregate by key only. Cheap but defeats the placement use case — placement *needs* to compare by model.

## Acceptance criteria

1. `PassRateRow` carries `model`; verify pipeline rejects rows where `model is None and channel is not in known_legacy_set`.
2. A run where the model snapshot changes mid-run produces two distinct buckets in the pass-rate table.
3. Spec §10 updated.

## Open question

Should `prompt_template_hash` and `model` interact? A new model version may need a new prompt template. If both vary independently, the cardinality of the placement table grows; if we treat them as paired, we lose the ability to A/B test prompt changes against a fixed model. **Recommend: keep them independent; document the cardinality cost.**
