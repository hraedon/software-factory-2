# Software Factory v2 — Design Spec

**Status:** Phase 5 (integration and outcome verification; GR-038 first all-pass full-DAG run). Spec §10 phasing governs what is implemented vs. deferred.
**Authoritative:** this file for all implemented stages and roles. Phase 6+ content is explicitly labelled as future design; those sections are proposals, not current implementation. Machine-readable sidecar (`spec.yaml`) deferred until Phase 6.

---

## 1. Purpose

A pipeline for autonomously producing functional software from a specification, targeting the segment of work that today is either (a) sloppily produced by line-of-business folks asking ChatGPT in isolation, or (b) doesn't get built at all because engaging a developer costs too much. The win condition is *consistently better than that baseline*, not parity with senior-developer output.

The principal of this factory is a systems architect, not a developer. The architecture must not require human code review as a gate — that gate would always be rubber-stamped or skipped, providing false assurance. Where v1 needed a human-expert reviewer at every phase boundary and degraded badly without one, v2 substitutes model-as-expert review at the same boundaries.

## 2. Non-goals

- Production code for safety-critical, financial, or regulated domains.
- Frontier-quality artisanal code; correctness-by-style; long-term-maintainable architecture as a primary objective.
- Fully automated vibe-spec → working software (acknowledged unsolved; deferred).
- Throughput optimization. v2 prioritizes consistency over speed.
- Greenfield rewrites of existing software the principal already maintains.

## 3. Principles

1. **Regista is the spine.** All state, audit, coordination, validation, and hooks flow through regista. No ad-hoc event recorders, hook systems, or imperative workflow encoders inside the factory.
2. **Sequential by default.** Parallelism is a later optimization once the sequential pipeline is reliable. The cost of debugging concurrent agent failures at this scale is paid up front, before throughput is measured.
3. **Autonomy via model-as-expert.** The principal cannot review code; therefore the architecture must not require it. Frontier-model judges replace human gates at phase boundaries.
4. **AC-driven tests are the contract.** Tests are produced from acceptance criteria *before* implementation, by a frontier-class model. They serve as both the implementer's target and the gate's verifier. The principal can review ACs (in their domain); they cannot review code.
5. **Mechanical gates over LLM gates wherever possible.** Type checkers, schema validators, test runners, lint, and regista-level integrity checks run before any model-judge does. LLMs as primary verifiers compound errors; deterministic gates do not.
6. **Filling-in roles, not architectural roles.** Workers run with explicit constraints: do not introduce new modules, do not add abstractions, do not invent new types. The only latitude is filling in against a locked contract.
7. **Smaller-scoped roles than v1.** A role's scope is bounded such that drift between adjacent roles is structurally limited. "Skeleton for the whole feature" is too broad; v2 targets "skeleton for this single function with this signature."
8. **Errors loop back to contract revision, not worker retry.** When two roles' artifacts don't fit at the seam, the most likely cause is an ambiguous contract, not a bad worker. Failures route back to the contract (interface-architect role) with structured context. Only after multiple revisions does the spec surface to the principal.
9. **Jury-and-race for load-bearing gates.** With multiple Tier-A model channels available at marginal-cost-zero, frontier judgment is composed across model families. Single-model judgment is reserved for non-load-bearing checks.
10. **Per-(role, channel, model) telemetry drives model placement.** Regista's event log produces empirical pass-rate data for every (role, channel, model, gate, prompt-template-hash) tuple. The resolved model string is captured at invocation time (RFC-034) so that a channel whose underlying model snapshot changes (e.g. `kimi-k2.6-turbo` → `kimi-k2.7-turbo`) does not silently merge into one confounded bucket. Role-to-channel binding is configurable and updated based on data, not vibes. No silent promotion of cheaper models into load-bearing roles.
11. **Subscription-flat-rate cost model rewards aggressive gating.** All channels are flat-rate; the budget is wall-clock time and rate limits, not tokens. v2 should look paranoid by API-cost-economics standards: every artifact runs the full battery of gates.

## 4. Pipeline

### Stages

The pipeline has 7 implemented stages (workflow work-item types), preceded by two manual/external steps that the factory does not automate today.

```
[Pre-pipeline, manual] Spec intake
  → Socratic elaboration via /spec skill (socratic-specification project)
  → Produces spec.md + AC list conforming to socratic-specification schema
  → Only step with a human gate; principal confirms intent before work items are created
  → Not implemented in the runner; principal-driven

[Pre-pipeline, manual] Work-item DAG creation
  → populate_work_items.py reads spec.md; creates work items in dependency order
  → MVP FRs first; each leaf work-item is small enough for a single interface-architect pass
  → Not a pipeline stage; operator-driven script

Stage 1: Interface architect  [work_item_type: interface_spec]
  → Per work-item: produces locked typed interface (.pyi stub)
  → Output: .pyi with full type annotations, errors enumerated, edge cases declared
  → All downstream roles consume this artifact; cannot modify it
  → Mechanical inner gate: syntax, stub structure, structural semantics, import check

Stage 2: Test authoring  [work_item_type: test_suite]
  → Per work-item: produces tests from AC + interface
  → Tests reference only the locked interface, not the implementation
  → Mechanical inner gate: syntax, pytest-collect, import-forbidden, assertion count

Stage 3: Implementation  [work_item_type: implementation]
  → Per work-item: produces code that passes the tests
  → Bounded by interface (cannot change signatures, types, errors)
  → Mechanical inner gate: syntax, import, mypy, ruff, pytest

Stage 4: Mechanical gates  [gate_process, runs after each stage above]
  → Type check (mypy --strict), test run (pytest), lint (ruff), import resolution
  → Deterministic; failures route back to the originating stage with diagnostics
  → Runs as a separate gate_process actor; not a separate work-item type

Stage 5: Cross-family review  [work_item_type: review]
  → Different-family model reviews implementation + tests against AC + interface
  → Catches contract drift the type checker misses (test theater, tautologies)
  → JSON verdict: {passed, findings, rationale}; structured findings route to implementer

Stage 6: Frontier judge (jury)  [work_item_type: jury]
  → 2+ Tier-A models independently answer: "do these tests, if they pass,
    demonstrate the AC is met?"
  → Quorum advances; disagreement routes back to Stage 1 (interface revision)

Stage 7: Integration  [work_item_type: integration]
  → Assembles locked implementations into a runnable module tree (assembled_tree JSON)
  → Mechanical gates: import resolution, mypy on assembled tree, cross-cutting pytest
  → Mechanical inner gate: JSON shape check

Stage 8: Outcome verification  [work_item_type: outcome_verification]
  → Runs the assembled software end-to-end against AC
  → Model-mediated verdict: {verdict: pass/fail/cannot_proceed, rationale, routing_hint}
  → Produces artifact bundle for principal review

[Post-pipeline, manual] Principal review
  → Does the running software do what was asked?
  → Yes → ship. No → feedback as new/revised AC, re-run affected stages.
  → Not a pipeline stage; principal-driven
```

### Failure routing

- **Stage 4 mechanical gate fail** → the originating stage (Stage 1/2/3) with diagnostics in prompt.
- **Stage 5 cross-family review fail** (`review_found_defect`) → Stage 3 (implementation) with structured findings via `routing_fields`; or Stage 2 (test_author) if the critique implicates tests. `review_malformed` → retry the review stage.
- **Stage 6 jury disagreement** → Stage 1 (interface architect), with juror rationale. The most likely cause of disagreement is an ambiguous interface, not a worker mistake.
- **Stage 1 interface revisions exhausted** (≥ `attempt_threshold`) → escalate to `cannot_proceed`. This is the primary way a work item surfaces to the principal mid-pipeline.
- **Stage 8 outcome verification fail** → `cannot_proceed` with `routing_hint` (work_item_type to route back to); principal can inspect the rationale and decide how to proceed.

### Regista workflow shape

Pipeline is a regista workflow YAML with:

- **Work-item types (implemented):** `interface_spec`, `test_suite`, `implementation`, `review`, `jury`, `integration`, `outcome_verification`
- **Link types (implemented):** `derived_from`, `implements`, `tested_by`, `reviews`, `judges`, `integrates`, `verified_by`
- **Roles (implemented):** `interface_architect`, `test_author`, `implementer`, `mechanical_gate`, `cross_family_reviewer`, `frontier_judge`, `integrator`, `outcome_verifier`
- **Custom fields per work-item type** enforce required artifact paths and schemas (regista validates pre-transition).
- **Validators** enforce artifact schema conformance before each transition.
- **Hooks** trigger downstream stages on transition via scheduler (e.g., `interface_spec` locked → `test_suite` creation; `test_suite` locked → `implementation` creation).

## 5. Fleet & role-to-channel binding

### Available channels (implemented)

| Channel name | Family | Access | Status | Notes |
|---|---|---|---|---|
| `claude-code` | Anthropic | Subscription, harness (`ClaudeCodeChannel`) | Validated | Frontier; slow in wall-clock, free at margin |
| `opencode` | Configurable per `model:` | Subscription/API, harness (`OpenCodeChannel`) | Validated | Wraps Kimi K2, DeepSeek, GLM, and other models via model-selector string |
| `gemini-cli` | Google | gemini-cli CLI | Validated (GR-032+), disabled by default | Requires Node 24; `GeminiCLIChannel` in code; not in PHASE*_ROLES defaults |

Models accessed via `opencode` channel (selected via `model:` field in RoleConfig):

| Model | Family | Notes |
|---|---|---|
| `fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo` | Moonshot (Kimi) | Primary worker model for interface_architect, test_author, implementer, integrator, outcome_verifier in Phase 3–5 defaults |
| `ollama-cloud/deepseek-v4-pro` | DeepSeek | Used for cross_family_reviewer in Phase 5 defaults |
| GLM-5.1 (z.ai) | Zhipu | Available via opencode; used in earlier golden runs; not in current phase defaults |

### Current role-to-channel binding (Phase 5 defaults, from `config.py`)

| Role | Channel | Model | Tier | Notes |
|---|---|---|---|---|
| Interface architect | `opencode` | Kimi K2p6-turbo | A | Load-bearing; all downstream roles depend on this artifact |
| Test author | `opencode` | Kimi K2p6-turbo | A | Tests are the contract; produces the gate target |
| Implementer | `opencode` | Kimi K2p6-turbo | A | Slot-filling against locked interface and test suite |
| Cross-family reviewer | `opencode` | DeepSeek V4 Pro | A | Family-disjoint from Kimi; catches contract drift |
| Frontier judge | `claude-code` | Sonnet (default) | A | Anthropic-family; family-disjoint from Kimi/DeepSeek jurors |
| Integrator | `opencode` | Kimi K2p6-turbo | A | Assembles locked implementations into runnable tree |
| Outcome verifier | `opencode` | Kimi K2p6-turbo | A | End-to-end verdict against AC |
| Mechanical gate | `code` (subprocess) | — | — | Deterministic; no model invocation |

**Tier classification (empirical, as of Phase 5):**
- **Tier A** — load-bearing channels where the artifact is directly part of the pipeline contract. All currently active worker roles are Tier A by empirical validation (≥80% first-attempt pass rate on golden runs).
- **Tier B** — structured bulk / lower-judgment tasks. No roles are currently assigned Tier B in the active phase defaults; this tier was planned for cheap K2 slot-filling but K2 has proven Tier A capable on interface and test roles.
- **Tier C** — probationary. Gemini is the only current Tier C channel: validated in GR-032+ but disabled in default configs pending more data. Its cross-family-review pass rate was 6% in GR-037 (gemini-2.5-pro, strict mode).

This table is **configuration**, not contract. It is updated based on telemetry (§7) and in response to model upgrades. No silent promotion: any change must be backed by pass-rate data for the affected role.

**Historical note on K2 tier assignment.** Prior drafts of this spec listed K2 (Kimi) as Tier B ("slot-filling, bulk") and Claude CC as Tier A for interface_architect and test_author. Empirical telemetry (GR-021 through GR-038) showed K2 consistently performing at Tier A quality on all worker roles, including interface_architect and test_author. The tier table has been updated to reflect the empirical record. The principle "no silent promotion" applies: this update is backed by 38 golden runs of data.

### Channel adapter

The runner exposes one interface to all model channels:

```python
class Channel(Protocol):
    name: str
    family: str
    def invoke(
        self,
        role: str,
        prompt: str,
        inputs_dir: Path,
        outputs_dir: Path,
        timeout: int,
    ) -> InvocationResult
```

Three adapters are implemented: `ClaudeCodeChannel`, `OpenCodeChannel`, `GeminiCLIChannel`. The `OpenCodeChannel` adapter handles multiple model families (Kimi, DeepSeek, GLM, etc.) via the `model_override` parameter — there is no separate KimiAPIChannel, GLMChannel, or DeepSeekOllamaChannel. Adapters handle their own quirks (headless flags, prompt shape, output capture, exit-code interpretation). The runner sees only `InvocationResult`. Role-to-channel binding lives in `FactoryConfig` (or a YAML override), hot-reloadable.

## 6. Failure handling

- **Hard retry budget per transition.** N=3 by default; tunable per role. After N failures, escalation event.
- **Errors loop back to contract revision** (§4 failure routing).
- **Structured failure outputs are first-class.** Every role can return `{"status": "cannot_proceed", "reason": ..., "gaps": [...]}` as a valid terminal artifact. The next stage knows how to handle this.
- **Dead-letter for unrecoverable.** Regista's dead-letter mechanism captures items that exceeded their escalation budget at every level. These surface to the principal as a list, with full event trail.

## 7. Observability

- **Regista event log** is authoritative. All actor metadata (role, channel, model, family, attempt #) is captured per event.
- **Per-(role, channel, model) pass-rate reporter** runs nightly (or on-demand), producing the table that drives role-binding decisions. Format: `(role, channel, model, gate, prompt_template_hash) → first-attempt pass rate, mean attempts to pass, mean wall-clock, gate-failure breakdown`. The formatter warns when a comparison group contains multiple prompt hashes OR multiple models — both are confounds for placement decisions (RFC-034).
- **Outcome dashboard** for the principal: per-spec status, per-stage timing, escalations, dead-letters. Built on regista's event store + Prometheus metrics. Exposes the *outcome*-level view, not code-level review.
- **Fleet health** monitor: per-channel uptime, rate-limit hits, average latency. Drives fallback decisions.

## 8. Open questions and known risks

1. **K2 tier assignment confirmed (resolved).** K2p6-turbo handles interface-architect and test-author roles at Tier A quality (≥80% first-attempt pass rate across GR-021 through GR-038). No further upgrade analysis needed for current workloads; update tier assignment only when telemetry changes.
2. **Long-context degradation.** Gemini and DeepSeek both nominally accept 1M context but quality drops sharply past ~200–300K tokens. Any long-context use must be benchmarked at varying context sizes; if degradation is severe, restrict to smaller windows or eliminate the role.
3. **Gemini-cli inconsistency.** Probationary placement; disabled in phase defaults. GR-037 measured 6% review pass rate for gemini-2.5-pro (strict mode). GR-032 validated the adapter. Re-enable only with a targeted capability probe showing ≥50% pass rate on a defined role. Gemini-cli's flakiness is largely harness-shaped — pure-text review tasks are more reliable than write-and-edit tasks.
4. **Regista dependencies.** v2 depends on regista's API surface (events, work items, claims, transitions). The factory has validated 38 golden runs against current regista. See BC-051 for the historical BC-021 note. The most active risk area is hooks/validators, dead-letter requeue, and replay correctness on long event histories.
5. **Runner complexity.** The channel-adapter + telemetry + failure-routing layer is a real engineering investment. At Phase 5 it is substantially complete (runner, gate_process, scheduler, router, pre_gate, jury, workspace modules). The primary remaining risk is integration-stage complexity for real (non-synthetic) workloads.
6. **Semantic AC ambiguity.** No structural defense; pushes responsibility to spec quality. The factory's job is to make ambiguity surface fast via `cannot_proceed` escalation. The principal's expertise *is* spec quality.
7. **Fleet management overhead.** With three active channel adapters and configurable models, time spent tuning model placement risks exceeding time spent producing software. Set a fleet-tuning budget cap (e.g., 10% of factory engineering time); if exceeded, freeze configuration.
8. **First-target application domain (partially resolved).** cert-watch has been the synthetic validation workload for Phases 2–5. A real line-of-business workload has not yet been attempted. Candidate criteria: self-contained, behavior-testable, recoverable on failure, valuable enough to justify running. *Not* socratic-specification or software-factory itself.
9. **Test theater.** Even with a frontier-judge gate explicitly checking "do these tests demonstrate AC met," subtle tautologies will get through. Mitigation: outcome verification (Stage 8) is the backstop, and the principal's outcome review is the final filter. Acknowledge this is incomplete.
10. **Cost of jury at scale.** Two-model juries on every jury work item are free per-invocation but costly in wall-clock. GR-038 first all-pass run took ~1h40m. Profile on real workloads; reduce jury size for stages where single-model judgment proves reliable.
11. **Outcome verification scope.** The `outcome_verifier` role is implemented and gated (Stage 8), but the role's model placement has not been empirically validated on a real workload. cert-watch golden runs exercise the infrastructure; real outcome verification requires a workload with a runnable assembled software artifact.

## 9. Memory and context

Memory in agent pipelines tends to fail because models cannot reliably maintain it as a separate invariant — graph stores, scratchpads, and "agent experience" surfaces accumulate inconsistencies that propagate silently through downstream roles. v2 avoids that failure mode by structural choice: regista's event log is the only authoritative state, and all "memory" is a deterministic derivation from it.

### 9.1 Regista is the memory

Per-work-item event log, custom_fields, links, workflow registry. Anything worth remembering about how a work-item got to its current state is captured at the byte level in regista — replayable, auditable, signed. v2 does not introduce a parallel knowledge store.

### 9.2 Context derivation as a deterministic function

The runner provides a `derive_context(work_item_id, role) -> PromptContext` library that builds the prompt input bundle from regista state. Per-role specifications declare what each role consumes (e.g., implementer: locked interface + tests + prior attempts + diagnostics; frontier_judge: spec section + AC + interface + tests + implementation; integrator: all locked implementations in the DAG). Versioned, tested, deterministic. Two invocations of `derive_context` on the same regista state produce byte-identical context bundles.

### 9.3 Caching as memoization, not as state

Expensive derivations (failure summaries, large context bundles) are cached, keyed on the underlying `event_seq` they were computed from. Cache invalidates automatically when regista moves. The cache never produces output not derivable from current regista state — it is a performance layer, not a parallel source of truth.

### 9.4 Failure summaries as first-class derived artifacts

When a work-item has multiple failed attempts, the next invocation receives a structured `failures.json` summarizing each: role, channel, gate, diagnostic, distinguishing feature. Generated by a small distillation step (K2-class, structured slot-filling) from the event log. Regenerated on demand; never separately stored as ground truth. This is the closest v2 comes to "the system learned from prior failures" — and it is explicitly a derived view, not an accumulated belief.

### 9.5 Glossary lives in spec.yaml

Canonical terms come from the spec's `glossary[]` (produced by socratic-specification at intake). Roles receive the relevant glossary excerpt in their context bundle. Not memory; context.

### 9.6 Role system prompts are code

Conventions like snake_case, no comments, frozen dataclasses, allowed import patterns — all live in role-specific system prompts under version control, not in any runtime-queryable knowledge surface. Updating a convention is a code change, reviewed and committed, with full history. Not memory; configuration.

### 9.7 No parallel knowledge store

Anything that would otherwise live in a graph database, vector store, or shared scratchpad must instead be one of:
- A `custom_field` on a work-item (structured, schema-validated, transactionally consistent).
- A typed link between work-items (relational, with an optional payload if regista gains link payloads).
- A derived artifact regenerated from regista state on demand.

Never free-floating mutable knowledge that workers can read and write. This is the v1 `memory_graph` trap; v2 closes it by construction.

### 9.8 No persistent role identity

Roles are stateless functions of their input bundle. The "implementer" does not accumulate experience across invocations. Regista's `actor_id` is for audit and per-attempt-channel telemetry, not identity-with-memory. Two invocations of the same role with the same input bundle should produce statistically equivalent outputs (modulo sampling); any divergence beyond that is a failure mode to investigate, not a feature.

### 9.9 No cross-project memory

Each project starts fresh. Cross-project lessons surface as:
- Principles added to this spec.
- Factory-level conventions added to AGENTS.md.
- Regista-level breadcrumbs that improve the coordination plane.

Never as runtime-queryable knowledge that the factory consults during a build. Cross-project pattern recognition is a research problem disguised as engineering, and v2 does not attempt it.

### 9.10 Long-term memory is the spec

The principal's spec is the long-term memory. Lessons accumulate there, by the principal's deliberate authoring, mediated by socratic-specification. The factory does not write to its own long-term memory because the principal cannot review what it would write.

### 9.11 Artifact addressing

Workspace artifacts are referenced from regista events by path. The runner uses a content-addressed convention for workspace paths (e.g., `.factory/work/<work_item_id>/<attempt_id>/<artifact_name>` with a per-attempt manifest containing sha256s). Regista events reference artifacts by path; replay can detect tampering by re-checking manifest hashes. Missing or tampered artifacts on a given attempt are recoverable by re-invoking the worker for that attempt — idempotent under regista's `event_id` dedup. This keeps regista's contract narrow (coordination state, not artifact bytes) while preserving auditability of artifact integrity.

### 9.12 Runner idempotency on restart

The runner must be safe to restart at any point. On re-claiming a work-item, the runner scans all prior attempt directories for a valid manifest. If a valid manifest is found (SHA-256 matches artifact on disk), the runner resumes from the highest-numbered valid attempt without re-invoking the channel. The `submit` event carries the original attempt's actor metadata (`channel`, `model`, `family`) from the manifest. If no valid manifest is found, all prior attempt directories are quarantined (renamed to `.corrupt/attempt-NNNN-YYYYmmdd-HHMMSS/`) and the runner invokes the channel fresh. The runner never overwrites an existing attempt directory. Each attempt directory maps to the regista attempt that produced it; later attempts may resume from earlier directories.

If the work-item is still in `in_progress` because the prior claim's TTL has not expired, the runner must wait for regista's `sweep_expired_claims` to return it to `new`, or an operator must force-expire the claim. The runner does not force-expire claims automatically.

## 10. Phasing

**Phase 0 — Regista completion. ✓ COMPLETE**
- Regista stable enough to depend on. Hook-based stage triggering works for current pipeline shape.
- Telemetry plumbing for actor metadata in events confirmed working (golden run 001).
- Historical note: BC-021 (hook consumer reconnect) was cited as blocker but the factory operates in production mode without it. Regista has advanced well past that breadcrumb. See factory BC-051.

**Phase 1 — Single-role end-to-end. ✓ COMPLETE**
- Runner skeleton built: runner, workspace, config, gate, gate_process, router modules.
- Channel adapter for Claude CC headless operational.
- Regista workflow with one role (interface_architect) validated.
- Exit criteria met: 12/15 interface_specs locked (>90% first-attempt pass rate on curated set).

**Phase 2 — Sequential single-channel pipeline. ✓ COMPLETE**
- test_author and implementer roles added, in pipeline order: interface → tests → impl → gates.
- Scheduler drives handoffs between stages (interface_spec locked → test_suite creation, test_suite locked → implementation creation).
- Single channel (`claude-code` or single `opencode`) to validate pipeline shape before adding fleet complexity.
- OpenCodeChannel adapter implemented as stub (BC-040).
- Telemetry shape established end-to-end (actor metadata with role/channel/family/attempt_n).
- Mechanical gates: syntax, stub, structural-semantics, import, mypy, pytest, ruff, pytest-collect.
- Cross-stage escalation routing functional (gate_escalation → cannot_proceed after attempt_threshold).
- 383 tests, 0 lint errors, 14 golden runs executed (GR-001 through GR-014).
- Best result: GR-014, 91% lock rate (20/22 items) on cert-watch full DAG.

**Phase 3 — Fleet integration. ✓ COMPLETE**
- Multi-channel dispatch: runner creates channel per role based on config binding.
- Channel adapters: ClaudeCodeChannel, OpenCodeChannel (K2/GLM/DeepSeek via model selection), GeminiCLIChannel.
- Per-role per-channel telemetry collected on the same workload as Phase 2.
- Credential infrastructure: `~/.config/factory/credentials.yaml` for provider API keys.
- Phase 3 config: interface_architect→Claude, test_author→K2 (Fireworks), implementer→GLM (z.ai).
- Began role promotion based on data (not vibes, not cost).
- Exit criteria met at GR-020 (commit 105c977).

**Phase 3 exit criteria (met by GR-020 on cert-watch full DAG):**

| Layer | Metric | Target | Rationale |
|---|---|---|---|
| Contract quality (leading indicator) | First-attempt mechanical-gate pass rate | ≥60% | Measures whether prompts and specs are clean enough that the implementer self-checks before returning. GR-019 achieved 64% on inner-gate data. |
| Operational success | Lock-within-budget rate | ≥90% | Did the system actually deliver? GR-014 achieved 91%. |
| Efficiency / brute-force detector | Mean attempts to lock | ≤2.0 | Catches "lock by burning retries." GR-015 achieved 100% lock with ~2.0 mean attempts — the boundary between structured retry and brute force. |

**Additional exit constraints:**
- Stuck/orphan rate: ≤1 stuck item per 16-work-item DAG, with automatic escalation after 2× mean wall-clock.
- Gate-failure mode breakdown: ≤10% of failures are "unknown" or "tool_not_found"; ≥80% are deterministic gate failures with clear `diagnostic_kind`.
- Spec lint integrated into `populate_work_items.py` and producing deterministic findings.
- BC-126 work-item size analysis report exists and has a conclusion.
- No breadcrumb status drift between files and README index.
- Default config binds only validated channels (K2 and Claude CC).

**Phase 4 — Jury and race. ✓ COMPLETE**
- Pipeline extended to 5 stages: interface_spec → test_suite → implementation → review → jury (workflow version 4, `workflows/phase4.yaml`).
- `cross_family_reviewer` role: different-family model reviews skeleton + tests against AC + interface.
- `frontier_judge` role with multi-channel jury: 2-3 Tier-A models independently judge; quorum advances, disagreement is recorded with rationale and the `[all_against]` tag distinguishes unanimous-fail from split votes.
- Multi-model jury: `model_override` on the Channel protocol allows distinct (channel, model) jurors in the same role; unique juror keys by channel+model; family derived from the actual model.
- Per-role channel failover: `fallback_channel`/`fallback_model` on RoleConfig; failover triggers on empty output, timeout, non-zero exit, or missing binary. Runner, inner gate, and jury jurors all honor the fallback. Telemetry records fallback in `ChannelFailPayload.diagnostics`.
- Capability-probe framework (BC-137) evaluates new models on all 5 roles before pipeline use. Gemini 2.5 Pro and Flash validated; Qwen 3.6-27b qualified for review/judge only (BC-138).
- Exit artifact: **GR-027** (cert-watch full DAG, dual-family jury K2+DeepSeek, 30/34 locked, 88%). The 88% lock rate is technically below the ≥90% threshold; the substantive exit criterion is the cause analysis (one gate bug now fixed, two correct-but-terminal review escalations, one model-ceiling) combined with the fact that all exit-constraint paths were exercised (jury_disagree, review rejection, channel failover, multi-family jury). See `golden-run-027-log.md`.

**Phase 4 exit criteria (met by GR-027 on cert-watch full DAG with dual-family jury):**

| Layer | Metric | Target | Actual | Status |
|---|---|---|---|---|
| Operational success | Lock-within-budget rate, 5 stages | ≥90% | 88% (30/34) | NEAR MISS* |
| Efficiency | Mean attempts to lock | ≤2.0 | 1.88 | PASS |
| Contract quality | Inner-gate first-pass rate | ≥60% | 71% (17/24) | PASS |
| Review reliability | Review first-attempt pass rate | ≥80% | 83% (5/6) | PASS |
| Jury reliability | Jury quorum-met rate | ≥90% | 80% (4/5) | NEAR MISS |
| Telemetry integrity (review/jury) | Unknown gate-name rate for review/jury events | 0% | 0% | PASS |

\* 88% lock rate: 1 test_suite item exhausted inner-gate retries (assertion count mismatch), 1 implementation item failed pytest gate (stub artifact), 1 review item was correctly rejected by DeepSeek reviewer (stub implementation — a valid verdict with no upstream routing), 1 jury item disagreed then exhausted retries. The latter two are structural routing gaps, not model quality gaps; they are accepted as Phase 5 work.

**Additional exit constraints (all met by GR-027):**
- **Multi-family jury exercised:** K2 (fireworks) + DeepSeek (ollama-cloud) families participate under `jury_quorum=2`.
- **Jury disagreement path exercised:** one `jury_disagree` transition occurred with `disagreement_rationale` populated.
- **Review rejection path exercised:** one `review_fail → new` retry occurred with structured diagnostics.
- **Channel failover exercised:** empty-output retries and fallback invocations recorded in telemetry.
- **Gate budget:** 13 deterministic + 2 model-mediated (`cross_family_review`, `jury_quorum`/`jury_disagree`), within Phase 4 budgets per §10.
- **Capability gate for new channels:** DeepSeek-v4-pro reviewed via capability probe before pipeline use.
- **Run-log discipline:** `golden-run-027-log.md` present.

**Phase 5 — Integration and outcome verification. ✓ COMPLETE (GR-038 first all-pass full-DAG run)**
- Implemented Stage 7 (integration) and Stage 8 (outcome verification) per §4.
- Cross-work-item linking: integration work items assemble locked implementations into a runnable module tree (assembled_tree JSON).
- Integration mechanical gates: import across modules, mypy on assembled tree, cross-cutting pytest — all three implemented in `evaluate_integration()`.
- Outcome verification: end-to-end model-mediated verdict of assembled software against AC — implemented in `evaluate_outcome_verification()`.
- Review/jury verdict routing (BC-145) — Phase 1 done (structured findings route to implementer via `routing_fields`); Phase 2 (upstream routing to test_author) deferred to RFC-025.
- Validated on cert-watch synthetic multi-module fixtures across GR-030 through GR-038.

**Phase 5 dependencies (from RFCs):**
- RFC-017 (operational survivability) — disk monitoring, log rotation, workspace lifecycle.
- RFC-019 (artifact bundling and output delivery) — Stage 8 (outcome_verification) artifact bundle for principal.
- RFC-020 (project archetype catalog) — cold-start templates for real workloads.
- RFC-021 (spec mutation and invalidation) — how spec changes mid-pipeline invalidate downstream work items.
- BC-145 (review/jury verdict routing) — structured upstream routing for review-found defects, not terminal retry. Phase 1 done; phase 2 deferred to RFC-025.

---

## Phase 6 and Beyond (future design — not yet implemented)

The following are design aspirations and recorded decisions for after Phase 5 exit. They are **proposals**, not implementation targets. Nothing in this section describes code that exists today.

**Phase 6 — Generalization and first real workload.**
- Second and third workloads (not cert-watch), with patterns extracted into reusable role templates.
- At this point, decide whether v2 is ready to attempt anything from the existing software-factory v1 backlog.
- Machine-readable spec sidecar (`spec.yaml`) produced by socratic-specification at intake; used as structured input to `populate_work_items.py` instead of freeform spec.md.
- Spec ambiguity resolver: structured escalation path that routes back to the principal with a focused question rather than a dump of diagnostics. Requires spec.yaml sidecar and socratic-spec integration.
- Race: running the same role on two channels in parallel; whichever produces a passing artifact first wins. Requires multi-channel dispatch refactor. Deferred until a workload demonstrates the wall-clock cost justifies the engineering complexity.

---

### Gate budget

The phasing exists to prevent the v1 mistake of trying to ship the whole architecture at once and discovering halfway that role boundaries don't work. **A second v1 mistake was an unbounded proliferation of mechanical gates: each time a new failure class was discovered, a new gate was added, which in turn exposed new failure classes, endlessly.** The budget below is the structural prevention.

Gates split into two kinds with different failure modes and therefore different budgets:

- **Deterministic gates** — any rule-based, non-model evaluation: syntax checks, type checks, linters, test runners, structural validators, import smoke tests, artifact size guards, and their inner-gate equivalents. Failure mode: accumulation of overlapping rules (the v1 failure). The budget is binding and triggers the bug-class response order below before a new gate is added.
- **Model-mediated gates** — verdicts produced by frontier-model judgment: `cross_family_review`, `jury_quorum`/`jury_disagree`, `outcome_e2e`. Each counts as one slot regardless of internal cardinality (channels, jurors, attempts). Failure mode: model-quality variance, not rule accumulation. Adding one requires a new role and a capability probe (BC-137), which is itself a higher bar than adding a rule; the budget here is informational.

| Phase | Max deterministic gates | Max model-mediated gates | Rationale |
|---|---|---|---|
| Phase 1 | 3 | 0 | Syntax, stub, structural semantics — the minimal set |
| Phase 2 | 8 | 0 | + import, mypy, pytest, ruff, pytest-collect; outer + inner gate variants |
| Phase 3 | 12 | 0 | + inner-gate variants for interface_spec and test_suite; pre-gate layers |
| Phase 4 | 13 | 2 | + jury + cross_family_review (model-mediated, capability-probed) |
| Phase 5 | 16 | 3 | + integration_import, integration_mypy, integration_pytest (deterministic); + outcome_e2e (model-mediated) |

**Default response to a new bug class is not a new gate.** When a bug class is discovered, the response order is:

1. **Prompt change** — clarify the role system prompt so the model avoids the class.
2. **Role boundary change** — move responsibility to a different role whose output shape prevents the class.
3. **Spec clarification** — amend the spec so the contract is unambiguous.
4. **Defect-class systemic fix** — if the class has ≥3 instances in the failure corpus (per RFC-016 / BC-128), file an RFC for the systemic fix.
5. **New deterministic gate** — justified only if steps 1–4 were attempted and the class recurs ≥3 additional times *after* those changes.

If a phase is at its deterministic-gate budget and a new gate is justified, the spec amendment must either (a) remove an existing deterministic gate that has not fired in the last 3 golden runs, or (b) escalate to the principal with the recurrence data and the attempted responses. Adding gates by accumulating `if/elif` branches without this process is the v1 failure mode; it is prevented by construction, not by reviewer discipline.

**Historical note (this amendment).** Phases 1–3 had no model-mediated gates; the Phase 4 figure of 15 in prior drafts reflected a single combined budget. The split here is retroactive accounting: Phase 4 ships 13 deterministic + 2 model-mediated, matching what GR-027 actually exercised. The amendment was made when Phase 5 surfaced that the v1 prevention rationale (rule accumulation) only applies to deterministic gates, not to model-mediated verdicts whose proliferation is naturally bounded by the cost of adding a new role.

## 11. Glossary

- **Channel** — an invocation path to a model (e.g., Claude via Claude Code headless, Kimi K2 via OpenCode). One channel per (adapter, model) pair; multiple models share the `opencode` adapter via `model:` selection.
- **Role** — a logical job in the pipeline (e.g., interface architect). Roles bind to channels via `FactoryConfig.roles`.
- **Tier** — empirical capability classification of a (role, channel, model) assignment. Tier A: load-bearing (confirmed at ≥80% first-attempt pass rate on golden runs — currently all active worker roles). Tier B: structured bulk / lower-judgment (no active assignments in Phase 5 defaults). Tier C: probationary (Gemini; validated but disabled in defaults).
- **Jury** — multi-model gate where 2+ Tier-A models independently judge an artifact and a quorum advances (`frontier_judge` role, `jury` work-item type). Juror identity is tracked per `(channel, model)` pair for family-disjoint judgment.
- **Race** — running the same role on two channels in parallel; whichever produces a passing artifact first wins. Not yet implemented in the runner; planned as a future optimization.
- **Family** — model lineage (Anthropic, Moonshot, DeepSeek, Zhipu, Google, etc.). "Family-disjoint" reviews and jury compositions use channels from different families to maximize uncorrelated failure modes.
- **Contract** — the locked typed interface (.pyi stub) produced by Stage 1 (interface_architect). All downstream roles read it; none may modify it without routing back to Stage 1.
- **Outcome verification** — Stage 8: end-to-end model-mediated verdict of assembled software against AC. The factory's primary correctness signal at the artifact level.
- **Principal review** — post-pipeline human gate at the behavior level. The factory's primary correctness signal at the intent level.
