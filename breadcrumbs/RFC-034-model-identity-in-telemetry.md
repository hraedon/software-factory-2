---
number: "RFC-034"
title: "Capture model identity (resolved model string) in telemetry keys"
severity: high
status: implemented
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

## Resolution

Implemented as specified. `model` is independent of `prompt_template_hash` in the grouping key (per the open-question recommendation).

**Files changed:**

- `src/factory/channel.py`: `InvocationResult` dataclass gains `model: str | None = None`.
- `src/factory/subprocess_channel.py`: all 8 `InvocationResult(...)` return sites in `invoke()` pass `model=model` (where `model = model_override or role_config.model`). `opencode_channel.py` inherits from `SubprocessChannel` so no separate change needed.
- `src/factory/runner.py`: the worker-submit `ArtifactManifest(...)` and `ActorMetadata(...)` (line ~536, ~549) now set `model=invoke_result.model`. The jury-aggregate site (line ~1083) keeps `model=None` with a comment — it is genuinely multi-model, not a gap.
- `src/factory/telemetry.py`:
  - `GateAttempt` gains `model: str | None = None`.
  - `PassRateRow` gains `model: str | None = None`.
  - `collect_gate_attempts` reads `worker_meta.get("model")` for both inner-gate attempts and standalone `gate_pass`/`gate_fail` events.
  - `compute_pass_rates` adds `model` to the grouping key and the sort key (NULL-safe via `"" if x is None else x`).
  - `format_pass_rate_table` adds a Model column (18 chars), widens the divider to 138 chars, warns on multi-model comparison groups (mirroring the existing prompt-hash confound warning), and emits a NOTE when partial NULL-model rows are present.
- `spec.md` §10 (principle) and §7 (observability) rewritten to reflect the (role, channel, model, gate, prompt-template-hash) key.

**NULL-row handling:** Existing legacy rows (pre-RFC-034 events with no `model` in actor_metadata) become a distinct `model=None` bucket — *not* merged with any resolved-model bucket. The formatter emits a NOTE counting NULL rows so operators know whether the table is on the new or old basis.

**Migration story:** No explicit migration. After one full golden run on the new code, NULL-model rows can be filtered out by `--exclude-null-model` if added to the CLI (deferred). Pre-RFC-034 substrate event payloads remain readable; `to_dict()` on `ActorMetadata` already supported `model`, so the wire format is unchanged.

**Tests:** new `tests/test_rfc034_model_in_telemetry.py` covers (a) `InvocationResult` default + explicit, (b) `compute_pass_rates` produces separate buckets for distinct models on the same channel, (c) NULL model is a distinct bucket, (d) formatter emits the model-drift warning and the partial-NULL note. All 63 telemetry-related tests pass.

**Phase-3 implication:** with this in, the placement layer (RFC-035) has trustworthy comparison groups to make decisions over. Without it, placement was operating on confounded data.
