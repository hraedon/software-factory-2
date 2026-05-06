# Phase 1 Implementation Plan — Single-role end-to-end

**Status:** draft
**Author:** claude-opus-4-7
**Date:** 2026-05-06

## Goal

Get one role (`interface_architect`) through the full substrate-mediated loop reliably. Per `spec.md` §10, exit criterion is **>90% first-attempt pass on a curated test set** of `interface_spec` work-items. No other roles, no other channels, no jury, no race.

## Exit criteria

1. A `factory` CLI can register `phase1.yaml` against substrate, create `interface_spec` work-items from a spec file, and drive them to `locked` end-to-end without human intervention.
2. `>90%` first-attempt `gate_pass` rate on a curated 10-item test set drawn from the substrate spec itself (substrate is conveniently a real, decomposable spec).
3. Runner survives mid-flight kill-and-restart at every stage of the loop without artifact corruption or duplicate substrate events. `tests/test_runner_idempotency.py` (per BC-003) passes.
4. Golden-run replay test reproduces a recorded run with byte-identical context bundles and event sequence.

## Prerequisites (must land before code starts)

| Item | Where | Why blocking |
|---|---|---|
| substrate BC-027 (SF2 workflow round-trip) | substrate | `phase1.yaml` must register and validate before runner depends on it. |
| BC-003 spec amendment (§9.12 idempotency mechanics) | this repo's `spec.md` | Runner restart logic is load-bearing; deciding it post-code is a rewrite. |
| substrate BC-029 (events-since cursor) | substrate | Runner's hook-loss recovery primitive. *Soft* prerequisite — Phase 1 has only one stage so a missed hook does not stall a pipeline. Can ship ahead of it but recovery story is incomplete until BC-029 lands. |
| substrate BC-028 (actor_metadata contract) | substrate | *Soft* prerequisite — Phase 1 single-channel makes drift unlikely, but populating the canonical shape from day one prevents a Phase 3 retrofit. |

BC-027 and the §9.12 amendment are hard blockers. BC-028/BC-029 are not — Phase 1 can start as soon as the hard blockers clear, with awareness that those two will land before Phase 2.

## Build order

Six waves. Each wave ends with a runnable, testable artifact. Earlier waves do not depend on later waves; later waves consume earlier ones strictly.

### Wave 0 — Repo skeleton (½ day)

- `pyproject.toml` with substrate dependency pinned to a substrate commit that includes BC-027 and BC-028 if landed.
- `src/factory/` package with empty `__init__.py`.
- `tests/` directory with `conftest.py` providing a project-scoped substrate fixture (mirrors substrate's `_testing` module pattern).
- CI config sufficient to run `pytest -m "not slow"`.

**Done when:** `pytest` runs and reports zero collected tests without error.

### Wave 1 — Workspace + manifest (1 day)

Build `workspace.py` first because every subsequent module reads from or writes to it.

- `workspace.py`:
  - `attempt_dir(work_item_id, attempt_number) -> Path` — content-addressed paths per spec §9.11.
  - `write_artifact(attempt_dir, name, bytes) -> ArtifactManifest` — atomic temp-then-rename.
  - `find_resumable_artifact(work_item_id) -> Optional[(attempt_number, ArtifactManifest)]` — scans existing dirs, validates SHA-256, returns highest valid attempt. Per BC-003 mechanics.
  - `quarantine_attempt(attempt_dir)` — rename to `.corrupt/<attempt>-<ts>/` rather than delete, per BC-003 audit-trail requirement.
- `tests/test_workspace.py`:
  - Round-trip: write → manifest → read back, hash matches.
  - Resume: prior valid attempt detected.
  - Resume with multiple priors: highest valid wins.
  - Tampered artifact: detected, quarantined, `find_resumable_artifact` returns None.

**Done when:** workspace tests pass without any other factory module imported.

### Wave 2 — Channel interface + MockChannel (1 day)

- `channel.py`:
  - `Channel` Protocol per spec §5.
  - `InvocationResult` dataclass.
  - `MockChannel` (in `tests/_mock_channel.py`, not `src/`) that reads pre-recorded artifacts from a fixture directory keyed by `(work_item_id, role, attempt_number)`.
  - `MockChannel.scripted_failure(attempt_n)` for retry-loop tests.
- `tests/_mock_channel.py` and `tests/fixtures/golden-run-001/` skeleton (real fixtures populated in Wave 6).

**Done when:** `MockChannel` round-trips an artifact through `workspace.py`. No `ClaudeCodeChannel` yet — that's Wave 5.

### Wave 3 — Context derivation (1.5 days)

Hardest pure-function module. Build before runner so the runner can compose it.

- `context.py`:
  - `derive_context(substrate, work_item_id, role) -> PromptContext`.
  - Pure function: same substrate state → byte-identical bundle (spec §9.2).
  - Returns `context_hash` (sha256 of serialized bundle), to be written into `actor_metadata` on the resulting event (per substrate BC-028 contract).
  - Phase 1 only implements the `interface_architect` role's bundle: spec section + AC list + glossary excerpt + prior-attempt failure summary if any.
- `failure_summary.py`:
  - `derive_failures(substrate, work_item_id) -> dict` per spec §9.4.
  - Phase 1: distillation is naive (a Python function, not a model call). Phase 2 may swap in a K2-class distillation step.
- `tests/test_context.py`:
  - Determinism: invoke twice, assert byte-identical bundle and identical hash.
  - State change: append a new event, re-derive, assert hash changes.
- `tests/test_failure_summary.py`:
  - No prior attempts → empty dict.
  - One failed attempt → one entry with role/channel/diagnostic.
  - Multiple failures → all included, ordered.

**Done when:** context determinism test is green and the context bundle is consumable by the (still-stub) runner.

### Wave 4 — Gate engine + router (1 day)

- `gate.py`:
  - `evaluate_interface_spec(artifact_path) -> GateResult` (per BC-002 dataclass shape).
  - Phase 1 gates: (a) valid Python syntax via `ast.parse`, (b) parses as a `.pyi` stub, (c) references all `ac_ids` declared in the work-item's custom fields.
- `router.py`:
  - Phase 1 routing table: `gate_fail → new` only.
  - Returns the next substrate transition + diagnostics payload to attach.
  - Structured for Phase 2 expansion (Stage 5/6/7 routing per spec §4) but only Phase 1 rules wired.
- `tests/test_gate_interface_spec.py`: happy path + 3 failure modes per BC-002 AC.
- `tests/test_router.py`: gate_fail → new with diagnostics propagation.

**Done when:** gate + router are independently testable with hand-crafted artifacts.

### Wave 5 — Runner loop + gate process + Claude CC channel (2.5 days)

The integration point. Brings together waves 1–4.

- `runner.py` (worker process):
  - Main loop: `claim → check resumable → derive_context → invoke → workspace.write → submit`.
  - Polls (or subscribes to hooks once BC-029 lands) for claimable items in `new` state matching its registered worker roles. Phase 1: just `interface_architect`.
  - Exits the loop on `submit`. Does NOT run gates — that is the gate process's job.
- `gate_process.py` (separate process, separate entry point):
  - Polls/subscribes for claimable items in `gating` state matching `mechanical_gate` role.
  - Claims, evaluates via `gate.py`, writes `GateResult` into `diagnostics` custom field, calls `gate_pass` or `gate_fail`.
  - Phase 1 ships as a separate Python entry point (`factory-gate`) launched alongside the worker (`factory-run`). Two processes, one runner per role-set.
  - Rationale for separate process up front: substrate already models these as different roles; collapsing them in the runner re-couples what substrate deliberately separated. Phase 2 will add `cross_family_reviewer` and `frontier_judge` as additional gate-side actors — designing the gate as a separate process now avoids re-architecting then. Coordination cost is small because substrate mediates it.
- All substrate transitions in both processes wrapped to populate `actor_metadata` per BC-028 contract: `{role, channel, model, family, attempt_n, context_hash}`. Transition wrappers are the mechanism, not call-site discipline (per BC-002 §"Critical changes #3").
- `channel.py` extension:
  - `ClaudeCodeChannel`: spawn `claude-code` headless, inject prompt, capture stdout/stderr/exit code, write artifact to `outputs_dir`. Timeout per role from `config.py`.
- `config.py`:
  - Single dataclass loaded at startup. Channel binding map (Phase 1: `interface_architect → claude-code`), per-role timeout, workspace root, role set per process (worker registers `[interface_architect]`; gate registers `[mechanical_gate]`).
- `channel.py` extension:
  - `ClaudeCodeChannel`: spawn `claude-code` headless, inject prompt, capture stdout/stderr/exit code, write artifact to `outputs_dir`. Timeout per role from `config.py`.
- `config.py`:
  - Single dataclass loaded at startup. Channel binding map (Phase 1: `interface_architect → claude-code`), per-role timeout, workspace root.
- `tests/test_runner_smoke.py`:
  - End-to-end with `MockChannel`: spawn worker + gate processes, create work-item, assert state reaches `locked` without manual intervention.
  - Failure path: `MockChannel.scripted_failure(1)` then succeed at attempt 2.
- `tests/test_runner_idempotency.py` (per BC-003 ACs):
  - Worker crash before `submit`: re-claim resumes from manifest.
  - Worker crash mid-write: discard, quarantine, re-invoke.
  - Tampered manifest: discard, quarantine, re-invoke.
  - Resumed `submit` carries original attempt's actor metadata, not the resumer's.
  - Gate process crash mid-evaluation: re-claim re-runs gates (gate evaluation is pure, so re-run is safe and cheap).
- `tests/test_gate_process.py`:
  - Gate process claims a `gating` item, evaluates, transitions correctly.
  - Gate process refuses items it is not registered for (only `mechanical_gate` role).

**Done when:** smoke + idempotency + gate-process tests green; `factory-run` and `factory-gate` CLIs can run a single work-item end-to-end against a real Claude CC instance with the two processes coordinating via substrate.

### Wave 6 — Golden-run + curated test set (1.5–3 days, see plateau handling)

The exit-criterion validation.

#### Test set composition

The pass-rate measurement is meaningful only if the test set spans multiple work-item shapes. Otherwise "Claude is good at this role" really means "Claude is good at one shape of this role," which Phase 5 will discover the hard way.

**Primary set (10 items, drawn from substrate's spec):**

- ≥3 categories of work-item shape. Suggested split:
  - **Pure-interface** (3+): single function or class, signature + types only (e.g., `acquire_claim`, `register_workflow`).
  - **Interface-with-error-taxonomy** (3+): function whose contract centrally includes an enumerated error set (e.g., `verify_event` with its `ErrorCode` returns).
  - **Interface-with-ADT-validation** (3+): function whose contract requires defining or consuming a structured payload (e.g., `create_link` with `payload`, replay's `DriftReport`).
- The category split is part of the AC. A 10/10 pass on only pure-interface items does not satisfy the exit criterion.

**Secondary set (3 items, hand-authored LoB-flavored spec):**

- A 1-page spec for a small line-of-business utility (suggested: a CSV-to-typed-records validator, or a date-range parser library). 3 work-items.
- Purpose: detect "Claude does fine on substrate-style specs and falls apart on anything else" before Phase 5 surfaces it.
- Pass rate is reported separately. Not a hard gate (3 items is too small for a 90% bar), but **<2/3 pass on the secondary set blocks Phase 1 exit pending diagnosis.**

**Adversarial item (1 item):**

- One work-item with intentionally ambiguous AC (e.g., "the function should return reasonable results for edge cases").
- Pass criterion is *not* a passing artifact — it is a structured `cannot_proceed` response per spec §6 ("Structured failure outputs are first-class").
- Confirms the role does not hallucinate a contract under ambiguity. Single-item; binary pass/fail.

#### Recording and replay

- Run all 14 items through the real `ClaudeCodeChannel` end-to-end. Record artifacts + manifests + substrate event dumps into `tests/fixtures/golden-run-001/`.
- `tests/test_golden_run.py`:
  - Replays the recorded run with `MockChannel` + `MockSubstrate`.
  - Asserts byte-identical context bundles per work-item.
  - Asserts identical sequence of substrate transitions.

#### Exit criteria

1. Primary set: ≥9/10 first-attempt pass, with at least 2/3+ in each shape category. (A 9/10 that's all pure-interface does not pass.)
2. Secondary set: ≥2/3 first-attempt pass.
3. Adversarial item: structured `cannot_proceed` returned (not a hallucinated artifact).

#### Plateau handling — what to do if pass rate stalls

Iterating role prompts is the right first response. But iterating *forever* is a failure mode; it masks structural problems as prompt-engineering problems. **Set a budget: 3 prompt revisions, max.** If after 3 revisions the bar is not met:

1. **Stop iterating prompts.**
2. **Diagnose the failure mode.** Categorize the failures:
   - *Spec ambiguity* — multiple ACs unclear, model produces divergent reasonable interpretations.
   - *Role scope too broad* — single work-item asking for too much; the contract is fine but the work doesn't fit one pass.
   - *Channel mis-suited* — Claude CC headless harness is hitting timeouts, output corruption, or instruction-following gaps that aren't prompt-fixable.
   - *Gate too strict* — gates are rejecting artifacts a human reviewer would call correct.
3. **Open a breadcrumb** in this repo describing the failure mode with concrete examples. Do not push past the bar.
4. **Surface to principal.** Phase 1 exit is a decision point: if structural changes are needed (split work-item type, change channel, revise spec, loosen gates), the principal makes the call. The factory should not silently ship at 7/10.

**The bar exists to protect Phase 2.** Phase 2 expands the role set; if Phase 1's single-role baseline is shaky, every Phase 2 addition compounds the noise. Better to spend a week diagnosing here than three weeks debugging a multi-role pipeline whose foundation was already weak.

**Done when:** golden-run test green AND all three exit criteria met AND (if there were >0 prompt revisions) the revisions are committed with rationale.

## Test strategy summary

- Unit-level: each wave's tests run with no substrate or model dependencies (workspace, gate, router, failure_summary).
- Integration-level: context, runner, idempotency tests use a real substrate against the docker-compose-test Postgres but a `MockChannel`.
- Acceptance: golden-run uses real Claude CC for fixture creation, `MockChannel` for replay. The first-attempt-pass-rate measurement is the only test that requires a live Claude CC at runtime.

## Out of scope for Phase 1 (explicitly deferred)

- Any role beyond `interface_architect`.
- Any channel beyond `claude-code`.
- Hot-reloadable config.
- Per-role per-channel pass-rate aggregator (the *reporter*; substrate captures the *data* from day one).
- Outcome dashboard / web UI.
- Stage 0 (socratic-specification integration) — Phase 1 reads pre-existing spec.md.
- Stage 8/9/10 (integration, outcome verification, principal review).
- v1 prompt-corpus / gate-library survey (BC-002's "What this first-pass survey missed") — that's a Phase 2 prerequisite.

## Open questions to resolve before Wave 5

1. **Where does the role prompt live?** Proposal: `factory/prompts/interface_architect.md` as a static markdown file, loaded at startup, hash recorded in `actor_metadata.prompt_hash`. Alternative: prompt-as-code in `context.py`. Static file is more reviewable.
2. **Project workspace root convention.** SF2 needs a per-project workspace separate from substrate's project schema. Proposal: `$FACTORY_HOME/projects/<project_name>/.factory/work/` matching the path convention in spec §9.11.
3. **Mechanical_gate role: same-process or separate?** **Resolved: separate process.** Worker (`factory-run`) and gate (`factory-gate`) are independent entry points coordinating only via substrate. Pays the small up-front complexity to avoid Phase 2 re-architecting and to honor substrate's role separation.

## Estimated total

8.5–10 days of focused work, assuming hard prerequisites are clear. Wave 5 grew to 2.5 days for the gate process. Wave 6 is variable on prompt quality — if the first-pass prompt hits the bar it's 1.5 days; if it needs the full 3 revisions it's ~3 days; if it plateaus below the bar, the work shifts to diagnosis and principal escalation rather than further iteration.

## After Phase 1

Phase 2 starts only when:
- Phase 1 exit criteria are met sustainably (not "passed once").
- BC-002's deferred Phase-2-review breadcrumbs (prompt corpus, gate library, failure taxonomies, spec evolution) are open and triaged.
- Substrate BC-028 and BC-029 have landed.

The single most important Phase 1 → Phase 2 handoff artifact is the **first-attempt pass-rate baseline per gate type**. Without it, "Claude is good enough at this role" is a vibe; with it, it's a data point that Phase 3's fleet integration can be measured against.
