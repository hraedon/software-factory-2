# Breadcrumbs

Defects, design questions, and improvements for software-factory-2. One file per item, numbered for reference. Numbers do not imply priority — see `severity` in each file's frontmatter.

Schema follows regista's breadcrumbs convention; see `/projects/regista/breadcrumbs/README.md` for the canonical reference.

## Schema

### Frontmatter

```yaml
---
number: "001"
title: Short descriptive title
severity: critical | high | medium | low
status: proposed | in_progress | implemented | obsolete | active
kind: bug | design | improvement | defect-class
author: who-raised-it
date: "YYYY-MM-DD"
tags: [topic, stage-N, dep-regista-NNN]
related: ["002", "003"]
---
```

### Fix section template

Every BC that is resolved with a code change must include a `## Fix` section.
If the BC's `related:` field cites another BC that shares at least one tag,
the `## Fix` section **must** include a subsection titled `### Why this isn't the previous fix recurring`.
That subsection must either:

1. Name the invariant that was absent in the prior fix, and explain how the new fix establishes it.
2. Explicitly state: "I don't have the invariant yet; this is another symptom fix." In that case the fix is held until someone proposes the invariant.

See RFC-031 for rationale and a worked example.

## Severity

- **critical** — blocks correct operation; v2 cannot be trusted for stated guarantees
- **high** — load-bearing spec property unfulfilled; silent-correctness risk
- **medium** — defect with workaround or limited blast radius
- **low** — edge case, polish, or minor ergonomics

## Tags

Reusable tags:
- `stage-0` through `stage-10` — pipeline stage from spec §4
- `dep-regista-NNN` — blocks on regista breadcrumb NNN
- `channel-claude`, `channel-k2`, `channel-glm`, `channel-deepseek`, `channel-gemini`, `channel-opencode`
- `tier-a`, `tier-b`, `tier-c` — capability tier (spec §5)
- `runner`, `telemetry`, `gate`, `jury`, `race`, `failure-routing`
- `dep-v1-NNN` — lesson from software-factory v1 breadcrumb NNN
- `rfc` — design proposal awaiting a future phase; not actionable yet

## Defect Classes

Classes group individual BCs that share the same shape (one-sentence pattern). See RFC-016 for rationale.

### Filing rule

Before filing a new BC, scan `CLASS-*.md` instances tables. If the defect matches an existing class, file the BC normally **and** append a row to the class's instances table. If it does not match, file the BC. If you have just filed the 3rd instance of an unclassified shape, file a CLASS-NNN file before closing the session.

### Promotion rule (RFC-030)

**Trigger**: When a CLASS file accumulates ≥5 instances OR contains ≥2 high/critical instances, the next reviewer files an RFC proposing the systemic fix and links it from the CLASS file.

**Block rule (new as of RFC-030)**: Once an RFC has been filed against a class, no new BC may be added to that class's instances table until ONE of the following holds:
- The RFC's invariant is implemented (status flips to `implemented`) and the class is moved to the "Stabilized Defect Classes" section below, OR
- The RFC is explicitly closed with a `symptom-fixed-because` rationale — a short paragraph in the CLASS file's body, signed by the principal, answering: "what cost would the invariant carry that exceeds the cost of continuing to fix instances symptom-by-symptom?"

**When blocked**: The would-be BC filer must either (a) drive the RFC forward (assign ownership, move to `in_progress`, set a target run), (b) request the symptom-fixed-because rationale from the principal, or (c) demonstrate the new failure is a genuinely different class.

Rationale: "file an RFC" diffuses ownership and has no time bound; the block rule creates a forcing function at the exact moment we would otherwise add another symptom-fix. See RFC-030 for full motivation and CLASS-005 as the worked example.

### Active Defect Classes

| Class | Title | Instances | Max Severity |
|---|---|---|---|
| CLASS-001 | JSONB / Contract Validation Entry-Point Drift | 10 | critical |
| CLASS-002 | Dependency Module Name Resolution | 5 | high |
| CLASS-010 | Channel Reliability and Failover | 8 | critical |
| CLASS-011 | Budget/Retry/Escalation Loop Control | 6 | critical |
| CLASS-012 | Single Source of Truth / String Constant Gravity | 10 | high |
| CLASS-014 | Test Coverage Gaps for Existing Code | 14 | high |
| CLASS-021 | Artifact Integrity and Immutability | 5 | critical |

### Stabilized Defect Classes

Systemic fix implemented via RFC-011 (unified subprocess execution layer). Instance tables unblocked per RFC-030 Path A.

| Class | Title | Instances | Max Severity | Stabilized By |
|---|---|---|---|---|
| CLASS-005 | Inner Gate vs Outer Gate Ruleset Divergence | 11 | critical | RFC-011 |
| CLASS-008 | Gate Subprocess Execution and Environment Handling | 12 | high | RFC-011 |

## Open

### Active Bugs & Improvements

| # | Title | Severity | Status |
|---|---|---|---|
| 224 | Jury/review accept stub, non-HTTP code as satisfying HTTP/persistence ACs — quorum buries the one juror that catches it | high | proposed |
| 223 | Golden-run RUNCARD status field not reconciled after run — audit trail self-contradicts | low | proposed |
| 222 | outcome_e2e gate on web-service workloads is unvalidated — GR-047 escalation, unknown root cause | medium | proposed |
| 221 | populate_work_items.py --spec-yaml mode has 3 bugs: workspace_root fallback, reset destroys files, requirements.txt not copied | high | in_progress |
| 215 | Scheduler dedup lock is single-process only — no HA support | low | proposed |
| 211 | No Prometheus metrics endpoint despite spec §7 claiming one | medium | proposed |
| 210 | No streaming/incremental telemetry — operators have no visibility during long runs | medium | proposed |
| 220 | Decomposer produces cross-workload contamination — hallucinated FR-05 with wrong-spec content | medium | proposed |
| 209 | No real workload validation — 4 non-cert-watch golden runs completed (96-97% lock), remaining gap is non-CLI workloads | medium | in_progress |

### RFCs (awaiting upstream phases)

RFC breadcrumbs use the `RFC-` prefix to distinguish design proposals that cannot be acted on until later phases. They are candidates for improvement, not actionable defects.

| # | Title | Severity | Phase Needed |
|---|---|---|---|
| RFC-037 | Detect → enforce → retire tiering — declared commitment level for gates, allowlists, and status fields (cross-project meta-defense; lead example BC-194 implemented) | medium | Phase 5 in-flight |
| RFC-035 | Data-driven channel placement layer — consume PassRateRow to propose role→channel config | high | Phase 3 (fleet integration) |
| RFC-034 | Capture model identity (resolved model string) in telemetry keys | high | Phase 3 (fleet integration) |
| RFC-033 | Guardrail lifecycle — tag preconditions, audit on invariant change (v1-lesson meta-defense) | medium | Phase 5 |
| RFC-032 | Breadcrumb-velocity circuit breaker — freeze new feature scope when arrival rate exceeds absorption (v1-lesson meta-defense) | medium | Phase 5 in-flight |
| RFC-031 | Fix-family root-cause requirement — BCs citing related BCs must explain missing invariant (v1-lesson meta-defense) | medium | Phase 5 |
| RFC-030 | Class promotion must produce an invariant, not just an RFC (v1-lesson meta-defense; CLASS-005/008 stabilized by RFC-011) | high | Phase 5 |
| RFC-028 | Per-role capability map — collapse 5-point registration into single declaration | medium | Phase 5 exit / Phase 6 |
| RFC-029 | Attempt-count telemetry bucketing — separate prompt calibration from gate-difficulty tail | medium | Phase 5 |
| RFC-026 | Principal review surface — pipeline needs artifact bundle format and feedback intake | high | Phase 6 (first real workload) |
| RFC-023 | Decomposer role — Stage 1 pipeline cannot consume arbitrary specs | high | Phase 6 (generalization) |
| RFC-002 | Critical observer degradation — v1 BC-359 shows silent swallowing loses telemetry data | high | Phase 3 (hooks/observers) |
| RFC-003 | Channel adapter auth-mode detection — v1 BC-376 shows env var injection breaks native auth | high | Phase 3 (multi-channel adapters) |
| RFC-007 | Test efficacy scoring via mutation testing gates — v1 BC-107/186, mechanical antidote to test theater | high | Phase 4–5 (jury / real workload) |
| RFC-009 | Interactive debugging inner loop — channel tool-use surface for implementer | high | Phase 5+ (evidence threshold: 3+ golden runs with pytest-in-inner-loop still failing) |
| RFC-010 | Fixture taxonomy — classify fixtures by architectural complexity class and gate Phase N exit criteria on the hardest exercised class | high | Phase 2 exit criteria |
| RFC-022 | Initiative primitive for work-item bundling and operational granularity | medium | Phase 5 (first real workload) |

## Resolved

| # | Title | Severity | Resolution |
|---|---|---|---|
| 219 | spec_lint AC regex rejects AC-{PREFIX}-NN format; populate_work_items hardcodes ac_ids to AC-01 | high | Updated spec_lint regex to `AC-(?:[A-Z]+-)?\d+`, made colon optional; added `_extract_ac_ids_from_fixture()` to populate_work_items.py replacing hardcoded `["AC-01"]`; added AC enrichment and FR→module name mapping in decomposer_model.py; 1107 tests pass; GR-043 validated (97% lock rate) |
| 217 | Adversarial review: 3 critical bugs + 8 high-severity issues found and fixed | critical | 3 critical (telemetry NameError, inner_gate JSONDecodeError, dead decomposer branch), 8 high (subprocess env leak, venv CalledProcessError args, 6 string-constant-gravity fixes, review_surface wrong key, wrong timeout, jury unbound var, dead telemetry branch), 9 medium fixes; all 1107 tests pass |
| 216 | Spec review stage — model-mediated architectural review before decomposition | high | `spec_review.py` module + `prompts/spec_review.md` + 28 tests; model-mediated review with confidence-scored findings; Phase B.5 mechanical orphaned-module gate in `decomposer_model.py`; wired into `populate_work_items.py --spec-review`; socratic-spec process.md updated (composition checks blocking, cross-model requirement removed) |
| 208 | mutation_gate.py _run_pytest duplicates pre_gate and gate pytest logic | high | Unified three-way pytest duplication into single canonical `_run_pytest` in `gate/_subprocess.py` with `gate_name` parameter; mutation_gate delegates via import, pre_gate uses lazy-import wrapper; ~110 lines of duplication eliminated |
| 207 | Broad except Exception blocks silently swallow errors in 16 locations | medium | Added structured logging (exc_info=True) to all silent-swallowing locations in scheduler, pre_gate, context, review, integration; remaining locations return GateResult with error message or are in dead modules (BC-206) |
| 206 | Dead production modules with zero callers (~1300 lines) | medium | Removed 5 dead modules (state_reporter, bundler, spec_hash, prompt_audit, ops/) + dead `build_summarizer_prompt()` function; ~1300 lines production + 72 test cases removed; RFCs remain as design proposals |
| 214 | __import__('re') in subprocess_channel.py — code smell | low | Replaced with normal `import re` at top of file |
| 213 | Regista private API imports in production code | medium | Replaced `from regista._errors import` with `from regista import` in runner.py, heartbeat.py, gate_process.py |
| 212 | No config schema validation — invalid configs accepted without error | high | Added `FactoryConfig.validate()` checking attempt_threshold, inner_gate_retries, poll_interval_seconds, claim_ttl_seconds, jury_quorum, query_page_size, role-to-type consistency; `from_yaml()` raises ValueError on invalid configs |
| 200 | subprocess_channel.py leaks full os.environ to model subprocesses | high | Replaced `**os.environ` with `**strip_sensitive_env(os.environ)` in `subprocess_channel.py`, `venv.py`, and `credentials.py`; all model, gate-tool, and venv-management subprocesses now scrub `DATABASE_URL`, `*_API_KEY`, tokens, and password/credential/secret env vars; added 3 regression tests |
| 196 | Telemetry reads all events for all work items — O(n*m) scaling | medium | Added `_query_work_items_and_events()` cache; updated all four telemetry consumers to accept caches; 4×N → 1×N reduction |
| 195 | No idempotency keys on regista mutations — crash-retry creates duplicates | medium | Created `factory.idempotency.make_event_id()`; wired `event_id` into all regista mutation call sites; added thread-safe cache for UUID stability |
| 202 | inner_gate _should_failover triggers on any non-zero exit code — too aggressive | medium | Narrowed to retryable failures only: timeout, empty output, exit codes 126/127, transport keywords ("connection", "timeout", "not found in path"); exit code 1/2 and generic errors no longer trigger failover |
| 201 | Scheduler swallows database exceptions as 'not locked' | medium | Replaced bare `except Exception: return False` in `_all_dep_specs_locked()` with structured logging of the unexpected error; preserves the `return False` behavior but with visibility |
| 199 | Unscoped query_work_items() leaks cross-project data in initiative.py and review_surface.py | medium | Added optional `workflow_name`/`workflow_version` kwargs to `query_initiatives()`, `cancel_initiative()`, `requeue_initiative()`; `review_surface.generate_review_report()` now passes scoping filters to `query_work_items()` |
| 198 | Initiative requeue uses state name as transition name — no valid transition from cannot_proceed | high | Added `requeue` transition from `cannot_proceed` → `new` to all workflow YAMLs; `initiative.py` now uses `TRANSITION_REQUEUE` constant; `cancel_initiative()` validates current state and uses `TRANSITION_ROUTE_TO_CANNOT_PROCEED`; both functions log skip warnings for unexpected states |
| 194 | No heartbeat on long-running model claims — claim theft risk | high | `HeartbeatSession` context manager wraps claims in runner/gate; daemon thread calls `heartbeat_claim` periodically; `cancel_event` kills subprocess on `CLAIM_LOST`; `subprocess.run` refactored to Popen+poll for cancellation |
| 197 | Dead code with broken regista API: store_spec_hash and load_spec_hash | low | Removed `store_spec_hash` and `load_spec_hash` (never called from production or tests); removed unused `CUSTOM_FIELD_SPEC_HASH` constant |
| 203 | gemini_channel.py hardcodes Node v24.15.0 path — not in FactoryConfig | medium | Added `gemini_node_bin: Path | None` to `FactoryConfig`; channel reads from config with hardcoded fallback |
| 204 | context.py hardcodes page_size=200 with no pagination | low | Parameterized `page_size` in `_gather_other_locked_artifacts` and `derive_integrator_context`; default 200 preserved for integrator's full-scan |
| 205 | workspace.py and dep_resolution.py accept unvalidated paths — path traversal and process group kill risks | critical | Added `_validate_path_component()` rejecting `/`, `\`, `..` in workspace paths; `_safe_artifact_path()` now rejects absolute paths; `_resolve_ref_artifact()` uses shared validation; `_terminate()` validates pgid==pid before killpg; `_safe_rmtree()` with /tmp prefix guard in agent_golden_run.py; FR-ID regex widened to `FR-(?:[A-Z]+-)?\d+`; removed duplicate yaml import and `__import__("time")`; 14 path-traversal tests |
| 193 | spec_section and import_feedback rendered unfenced in prompt — heading injection risk from fixture specs | low | Both fields fenced in triple-backtick code blocks in `render_prompt`; `custom_fields_update` added to SubmitPayload known-fields |
| 195 | Integration gate subprocess namespace isolation — unshare --user --map-root-user --net | medium | `evaluate_integration` runs all subprocesses (import, mypy, pytest) under `unshare --user --map-root-user --net` when available; graceful degradation with structlog warning; PYTHONDONTWRITEBYTECODE set; validated in GR-039 |
| RFC-011 | Unified subprocess execution layer — typed wrapper eliminating gate/runner subprocess footguns | critical | `factory.subprocess.run` with keyword-only `cmd`/`cwd`/`env`/`timeout_s`; all 29 call sites in `src/factory/` migrated; CLASS-005 + CLASS-008 stabilized; validated in GR-039 |
| RFC-036 | Eliminate regista private-API imports; split gate.py into a gate/ package | medium | gate.py (1415 lines) split into gate/ package with 9 submodules; gate/__init__.py re-exports all public names for backward compat; runner.py split: inner_gate.py + jury_orchestrator.py; phase defaults extracted to phase_defaults.py; _PHASE2_DISPATCH → _KIND_DISPATCH |
| RFC-024 | Coherence reviewer — declared role with zero design or implementation | high | Role removed from all dead-configuration sites (constants.py, spec.md, full_pipeline.yaml) per RFC-024 Option A. May be reintroduced in Phase 6 with concrete evidence of a structural-coherence gap. See resolved/RFC-024-coherence-reviewer.md. |
| 194 | Channel status declaration vs. constructor divergence — GLM/DeepSeek/Gemini constructible despite "disabled"/"unvalidated" status | high | _CHANNEL_STATUS table adjacent to _register_channel with tier:enforce annotation; _create_channels raises ChannelDisabledError for disabled channels and warns for unvalidated; gemini-cli first enforced case; 2 regression tests (AC-2, AC-3) |
| 190 | Scheduler downstream dedup is racey and O(N); handoff iteration unfair | high | Per-(source_id, downstream_type) `threading.Lock` in WeakValueDictionary closes TOCTOU window; in-memory existence cache skips O(N) scan on repeat calls; `random.shuffle` per poll cycle for fairness; 5 tests |
| 192 | Telemetry verify and pass-rate formatter use different unknown-rate thresholds | low | `TELEMETRY_UNKNOWN_RATE_THRESHOLD = 0.01` constant in `constants.py`; both `format_pass_rate_table` and `run_telemetry_verify` use it; label updated to `[target: <1%]` |
| 191 | Context builder renders review_feedback twice and emits raw model text into prompt structure | medium | Deduped via `rendered_keys` set; all extra_artifact values fenced in triple-backtick code blocks; 4 tests |
| 189 | src/factory/checkpoint.py is dead code; RFC-008 unfulfilled or cancelled | medium | Option A: module + test deleted; RFC-008 marked obsolete |
| 188 | Integration gate writes LLM-controlled filenames without sandboxing — path traversal and arbitrary code execution | critical | `evaluate_integration` validates assembled_tree filenames (absolute, `..`, sandbox escape); `diagnostic_kind="integration_unsafe_path"`; 4 regression tests |
| 178 | Tighten upstream_revision_of to target_work_item_types: [review, jury] by moving declaration to phase4 | low | Moved `upstream_revision_of` (with `target_work_item_types: [review, jury]`) and `review_findings` from `phase2.yaml` to `phase4.yaml` via `custom_fields__append` |
| 187 | Pipeline subprocess writes fixture artifacts into repo root; first surfaced in GR-038 integration/outcome stages | medium | RFC-011 Step 3 (d8ab880): `SubprocessChannel.invoke()` now always uses `outputs_dir` as subprocess cwd; `invocation_cwd` override that forced cwd to repo root removed; all remaining `src/factory/` subprocess call sites migrated to `factory.subprocess.run` wrapper (explicit cwd/env/timeout required) |
| 186 | BC-181 gate_near_budget soft-stop never hard-transitions — indefinite acquire/release churn on items stuck in gating state | medium | gate_loop now hard-transitions items at `attempt_threshold` to `cannot_proceed` via `TRANSITION_GATE_ESCALATION` with `gate_name="gate_budget_exhausted"`, replacing the prior release-and-continue soft-stop that allowed infinite cycling |
| 185 | split GateResult.custom_fields into transition_fields and routing_fields | medium | GateResult now has separate `transition_fields` (current WI) and `routing_fields` (upstream revision) bags; `custom_fields` kept as one-cycle deprecation alias; gate_process filter helper from BC-180 removed as no longer needed |
| 184 | interface .pyi stubs with ellipsis bodies trigger mypy 'abstract attributes' retry-exhaustion for impls | high | `copy_dependency_pyis` AST-rewrites ellipsis bodies in the `.py` shadow to `raise NotImplementedError`; `--allow-empty-bodies` added to gate/pre_gate mypy invocations |
| 183 | unsupported_import_pattern classifier produces false-positive feedback for stdlib/third-party submodule imports | medium | pre_gate `_parse_import_failure` now consults `sys.stdlib_module_names` + parsed requirements.txt and downgrades safe top-levels to `_IMPORT_FEEDBACK_KIND_OTHER` |
| 182 | gate_process lacks self-circuit-breaker for repeated identical crashes on same item | medium | gate_loop tracks per-item `(crash_count, error_sig)`; after `gate_crash_threshold` (default 3) identical exceptions, hard-transitions the item to `cannot_proceed` via TRANSITION_GATE_ESCALATION |
| 181 | gate_process has no attempt budget guardrail — crash-looping items cycle indefinitely | high | gate_loop now checks `claim.attempt_number >= attempt_threshold` at top of page loop and releases the claim with `gate_near_budget` warning, mirroring runner's BC-139 pattern |
| 180 | gate_process writes review_findings to review work item type — CUSTOM_FIELD_VIOLATION crash-loop | critical | Resolved structurally by BC-185 (separate transition_fields/routing_fields bags); evaluate_review now puts `review_findings` in routing_fields so it never reaches the review WI transition payload |
| 174 | Integration gate import resolution runs in wrong Python environment — fails on project dependencies | high | evaluate_integration() now runs import resolution as subprocess under gate venv python (same as mypy/pytest); in-process sys.path mutation removed; CLASS-008 instance #11 |
| 173 | Workflow composition migration complete — extends: adopted for phase2-5 | low | phase2-5 use extends: inheritance; 1133→421 lines (63% reduction); pipeline_docs uses resolve_includes(); regista register_workflow_file resolves extends; semantic verification via scripts/migrate_workflows.py --verify |
| 172 | Pre-commit hook does not enforce `make check` — lint errors and broken tests landed in main | medium | Created .githooks/pre-commit running make check; git config core.hooksPath .githooks |
| 171 | Integrator role prompt lacks worked example — assembled_tree import/mypy failures at outer gate | medium | Added worked example to integrator.md with cert-watch-style 2-module assembly demonstrating flat keys, cross-module imports, entry_point, integration_tests |
| 170 | Pre-gate ruff mutates integrator JSON artifact — quote normalization corrupts .py-wrapped JSON | high | Fixed: _artifact_extension_for_role returns .json for integrator/outcome_verifier; dedicated pre_gate_integrator/pre_gate_outcome_verifier skip ruff/mypy/pytest (CLASS-021 #5) |
| 168 | Phase 5 link types had reversed source/target direction — scheduler create_link failed for integrates and verified_by | high | Reversed source/target in workflows/phase5.yaml; changed golden-run stage_topology link_type from derived_from to integrates/verified_by; validated in GR-030 |
| RFC-016 | Defect-class taxonomy — evolve breadcrumbs from per-defect entries to class-based corpus | medium | 9 CLASS-NNN files created; filing rule and promotion rule added to README schema; 24 classes identified across 171 resolved BCs |
| RFC-014 | Staff engineer summarizer — compress outer-path failure history into actionable constraints | medium | failure_summarizer.py with local constraint extraction (import refs, type mismatches, missing symbols, recurring errors); integrated into render_prompt for >=2 prior failures |
| RFC-004 | Auto-generated pipeline documentation — v1 docs froze while pipeline grew | medium | pipeline_docs.py generates documentation from workflow YAML, router dispatch table, and prompt templates; format_full_doc() produces complete pipeline reference |
| RFC-001 | Prompt conflict detection — v1 BC-383 shows silent failure when role prompts contradict | high | prompt_audit.py with typing-style conflict detection, directive gap analysis, orphaned artifact reference checks, worked-example style drift scanning |
| RFC-018 | Live state reporter — regista-derived project snapshot | medium | state_reporter.py with StateReporter, PipelineSnapshot, ProgressSummary; CLI with --json/--brief/--watch; markdown/JSON/brief render modes; 13 tests |
| RFC-008 | Pipeline checkpoint and surgical resume system | medium | checkpoint.py with write_checkpoint/load_checkpoint/compare_checkpoints/can_resume_from_checkpoint; per-stage state snapshots; config hash validation; latest.json symlink; 14 tests |
| RFC-005 | Composable failure/escalation architecture | medium | Router refactored to RouteHandler pipeline: RoutingHintHandler → EscalationHandler → DispatchHandler; new handlers add via _HANDLERS list without modifying dispatch table; 6 handler tests |
| RFC-025 | Stateful upstream routing — route() and scheduler need role-targeted work-item creation | high | Route extended with upstream fields; REVIEW_FOUND_DEFECT creates implementation revisions via scheduler.ensure_upstream_revision(); idempotency via upstream_revision_of custom field |
| RFC-021 | Spec mutation and invalidation policy | high | spec_hash.py module with SHA-256 tracking, store/load via regista custom fields, compare_spec_hashes for change detection |
| RFC-020 | Project archetype catalog for Phase 5 cold-start | high | catalog/ with 3 archetypes (cli-tool, web-service, library-module); catalog.py loader with skeleton application and validation |
| RFC-019 | Artifact bundling and output delivery | high | bundler.py with tar.gz/zip/dir output, MANIFEST.json, SHA-256 integrity verification; 13 tests |
| RFC-017 | Operational survivability — resource limits, disk monitoring, log rotation, workspace lifecycle | high | factory/ops/ package: cleanup.py, log_rotation.py, disk_monitor.py, resource_limits.py; OpsConfig in FactoryConfig; 22 tests |
| RFC-012 | Gate subprocess credential stripping and sandboxing | medium | sandbox.py with strip_sensitive_env/gate_subprocess_env; all gate.py and pre_gate.py subprocess calls use sanitized env |
| RFC-006 | Per-project venv isolation for subprocess gates | medium | Auto-detect requirements.txt via should_use_project_venv(); ensure_gate_venv installs project deps into gate venv |
| 145 | cross_family_review failure is terminal — no route back to implementer for legitimate review-found defects | high | Phase 1: REVIEW_FOUND_DEFECT/REVIEW_MALFORMED taxonomy, ReviewFinding schema, router dispatch to STATE_NEW with review_feedback_pending, context injection. Phase 2 deferred to RFC-025 |
| RFC-015 | Dependency import manifest + gate-level import validation | high | extract_exports() AST-walk, import symbol validation gate, manifest in prompts, stub-only tags. 491 tests pass |
| RFC-013 | Expanded inner-gate feedback for implementer retries — richer failure signal without infra overhead | medium | inner_gate_max_feedback_chars config, FailureEntry accumulation, gate output fed back to model in retry prompt |
| 166 | Interface architect inner_pytest first-pass rate dropped from 50% (GR-027) to 38% (GR-029) | medium | Closed as stochastic noise — 4/8 vs 3/8 is a difference of 1 item, consistent with K2 variance |
| 158 | Outcome-verifier routing_hint extracted in gate but never consumed by scheduler or router | high | OUTCOME_E2E with routing_hint routes directly to CANNOT_PROCEED; full upstream routing deferred to RFC-025 |
| 154 | _run_ruff_fast modifies artifact in-place inside inner gate — original model output lost | high | `_run_ruff_fast` is now side-effect-free; calling functions apply fixes via `_apply_ruff_fix()` |
| 149 | Model availability regression — DeepSeek and GLM both dead in opencode channel | high | Added pre-flight model ping to `agent_golden_run.py`; aborts if any model is unreachable |
| 148 | Scheduler crashes with exit code 1 during golden run — blocks outcome_verification stage | high | Already fixed by BC-161 — scheduler has try/except Exception handler in main loop |
| 147 | Scheduler stuck-item handling for small DAGs — review item orphaned in gating | medium | Subsumed by BC-164 fix — scheduler runs 3 drain cycles after SIGTERM |
| 138 | Qwen 3.6-27b operational timeout on test_author and implementer roles (>600s) | medium | Restrict Qwen to review/judge roles only; Gemini Pro viable alternative for code-gen |
| 167 | Monitor does not kill remaining processes on pipeline process crash | medium | Monitor now kills remaining processes and calls `_fatal()` when any process exits with non-zero code |
| 165 | Single-family jury with quorum=2 produces systematic disagreement | medium | Added `validate_jury_config()` to `FactoryConfig`; warns when `jury_quorum > distinct_models` |
| 163 | agent_golden_run.py danger signal checks have duplicate unreachable code blocks | low | Removed duplicate `gate_fail_*` and `channel_invoke_failed` checks |
| 162 | agent_golden_run.py auto-cleanup destroys scheduler crash forensics | high | Logs are now preserved when any process exits with non-zero code; workspace and opencode DB still cleaned |
| 161 | Scheduler main loop has no exception handler | high | Wrapped scheduler poll loop body in `try/except Exception` with `log.exception()` before continuing |
| 160 | ClaudeCodeChannel unused local alias re-exports | low | Removed unused `_extract_artifact_from_output` and `_extract_json_from_output` aliases; tests updated to import from `output_extraction` directly |
| 159 | _resolve_extra_env called twice with same arguments in process_work_item | low | Removed duplicate call at line 376; single call at line 396 serves both jury and non-jury paths |
| 157 | Scheduler propagate_fields access uses hardcoded index 0 instead of field name | medium | Changed `pf[0]` to explicit `CUSTOM_FIELD_INTERFACE_REF in pf` check followed by `custom.get(CUSTOM_FIELD_INTERFACE_REF)` |
| 156 | _find_locked_impl uses hardcoded page_size=200 instead of config value | medium | Added `page_size` parameter to `_find_locked_impl()` and `resolve_dep_artifacts()`; gate_process passes `config.query_page_size` |
| 155 | Integrator and OutcomeVerifier excluded from inner gate retries in Phase 5 | high | Added `ROLE_INTEGRATOR` and `ROLE_OUTCOME_VERIFIER` to `_INNER_GATE_ROLES` frozenset |
| 153 | Three test files have conditionally-skipped assertions — silently pass without testing | high | Changed `if not result.passed:` guards to `assert not result.passed`; updated test input to use unfixable F821 error |
| 152 | router.py _classify_diagnostic has unreachable dead code branches | low | Removed lines 72-83 — the enum-iteration loop at lines 51-54 already matches all `DiagnosticKind` values |
| 151 | Integration success reports wrong gate name | high | Added `GATE_NAME_INTEGRATION` constant; `evaluate_integration()` returns it on success instead of `GATE_NAME_INTEGRATION_IMPORT` |
| 150 | Channel backoff creates permanent deadlock | critical | Implemented time-based backoff with `channel_backoff_until` dict; after cooldown, one probe item is attempted; counter resets on success |
| 144 | agent_golden_run.py idle timeout too aggressive — killed working pipeline | medium | Increased `max_idle_cycles` from 3 to 10 (10min idle before declaring done); increased `claim_near_budget` fatal threshold from 3 to 5 |
| 143 | claim_near_budget releases claim without terminal transition — zombie items cycle forever | high | `claim_near_budget` now transitions claim → cannot_proceed (terminal) instead of just releasing; 4 items properly escalated in GR-027 |
| 142 | agent_golden_run.py launched processes from /tmp — broke opencode project context | high | Changed `_launch_processes()` to use `cwd=REPO_ROOT`; workspace isolation via config YAML workspace_root, not process cwd |
| 141 | opencode run returns empty output when cwd is not a project directory | high | Added `invocation_cwd: Path | None` to `FactoryConfig`; `SubprocessChannel` uses it for subprocess cwd; golden run configs set it to repo root |
| 140 | No standard invocation process for agent-mediated factory runs | high | Hardened `scripts/agent_golden_run.py` with incremental log reading, process crash detection, graceful wait/terminate; added `log_dir` parameter for testability; 18 new tests (preflight, config validation, danger signals, cleanup). 688 pass, 0 lint errors |
| 139 | Review and jury gate failures never escalate — infinite retry loop consumes unbounded sessions | critical | Added `DiagnosticKind.CROSS_FAMILY_REVIEW` and `DiagnosticKind.JURY`; updated `_classify_diagnostic()`; added both to `_ESCALATABLE_KINDS`; runner `claim_near_budget` warning is now a hard stop (releases claim + skips). 8 new tests. 670 pass, 0 lint errors |
| 136 | Channel failover — automatic backup channel on empty output, API errors, and timeouts | high | `RoleConfig` extended with `fallback_channel`/`fallback_model`; `_should_failover()` triggers on empty output, timeout, non-zero exit, missing binary; runner primary→fallback immediate retry; inner gate retries use fallback; jury juror fallback with `_fb` channel key; telemetry records fallback in `ChannelFailPayload.diagnostics`; 13 tests; 650 pass, 0 lint errors |
| 135 | glm-5.1 (z.ai) returns empty output for implementer role — model reliability issue | medium | Root cause: transient z.ai provider issue (13/16 failures during GR-024, 0/16 in post-hoc test). Mitigations: empty-output retry (configurable, default 1 retry / 3s delay); stderr capture in error message + `raw_stderr.txt`; 13 new tests |
| 134 | run_jury observability gap — disagreement_rationale empty on all-error/all-timeout | medium | `jury.py` always populates `disagreement_rationale` when quorum not met; `[all_against]` tag distinguishes all-failure from split; `evaluate_jury()` produces tagged diagnostics; 3 new evaluate_jury tests |
| 133 | Telemetry two-source-of-truth — inner-gate signal lives only in runner logs | high | `SubmitPayload.inner_gate_attempts` carries inner gate history in regista events; `telemetry.py` reads inner gate attempts from submit payloads; separate inner gate first-pass rate in exit criteria; report label "Phase 3" → "Pipeline" |
| 132 | Phase 4 jury and race architecture skeleton | medium | `jury.py`, `review.py`, prompt templates, `evaluate_review()`, `evaluate_jury()`, `process_jury_work_item()`, `phase4.yaml`, `FactoryConfig.phase4()`; 10 new tests; lint/test clean |
| 131 | Runtime import resolution feedback quality — dotted submodule and module-not-found errors | high | `_parse_import_failure()` in pre_gate.py classifies import failures as dotted_submodule/wrong_module_name/other_traceback; `import_feedback` field in PreGateResult and PromptContext injects actionable retry context; structlog `import_feedback_kind` dimension; GR-021 validated: 5/5 wrong_module_name failures recovered on retry=1; inner gate first-attempt rate 74% (20/27) |
| 108 | GeminiCLIChannel disabled — unvalidated in golden runs, removed from runner registration | medium | GeminiCLIChannel removed from `_register_channel()` calls; Phase 3 default config uses kimi-k2p6-turbo for all roles; unvalidated channels no longer in default bindings |
| 126 | Work-item granularity correlation — measure AC count vs first-attempt pass rate, then cap | high | Phase A measurement complete. 96 rows across 5 GRs. No relationship between AC count/spec words/dep lines and first-attempt failure. Curve is flat; no knee. No spec-lint size cap warranted. See `.factory/analysis/2026-05-13-work-item-granularity.md` |
| 130 | spec_lint only handled bulleted AC format — heading-per-AC specs were all ERROR | medium | Refactored `_extract_acs()` to handle both `## AC-NN:` heading format and `## Acceptance Criteria` bullet format; 7 new tests; all cert-watch specs lint cleanly |
| 127 | Spec linting — pre-flight pass over work-item specs before model invocation | high | `spec_lint.py` module with 7 checks; wired into `populate_work_items.py` with `--skip-lint`/`--strict-lint` flags; handles both AC formats; deterministic output verified |
| 129 | Regista actor_metadata API change breaks 10 integration tests — dict vs attribute access | high | Fixed on regista side; all 18 tests pass; make check clean |
| 128 | Cross-attempt defect taxonomy — classify model-attempt failures across GRs | high | Corpus builder (`build_failure_corpus.py`), report generator (`failure_corpus_report.py`), classification rules, 16 tests; regista syntax error blocking import fixed |
| 063 | InMemorySubstrate drift history — integration test surface is 10x smaller than unit test surface | medium | `make integration` target added; 8 new integration tests covering test_suite lifecycle, implementation lifecycle, scheduler DAG, channel failure retry, crash recovery on real Postgres |
| 125 | populate_work_items.py --config doesn't infer --workflow from config YAML | medium | --workflow defaults to None; inferred from config.workflow_version when --config provided; summary line prints resolved project name |
| 124 | Selective ruff rule set for model output — relax non-critical rules | medium | Inner gate uses `--select E,F,I,N,W,UP,RUF --ignore E501` matching pyproject.toml; GR-019 validated: zero ruff failures |
| 123 | Inner gate auto-fix: copy ruff-corrected artifacts back instead of retrying | medium | `_run_ruff_fast` auto-fixes and writes back with `.orig` backup; targeted F841 unsafe fix; GR-019 validated |
| 122 | Prompt pre-flight checklist to improve first-attempt pass rate | high | Pre-flight verification checklists added to all three role prompts; GR-019: inner gate first-attempt rate 0% → 64% |
| 121 | Gate process and runner use project venv instead of gate venv for gate tooling | critical | `ensure_gate_venv` now installs gate tools + project requirements into `.venv-gate`; `gate_process.py` and `runner.py` both use gate venv python for gate operations |
| 119 | Venv gate tool hash won't detect version changes — only covers tool name list | low | _gate_tools_hash() now queries pip show for installed versions; hash changes on version drift |
| 118 | golden_run_nanny.py lacks overall timeout and progress reporting | low | Added --timeout flag (default 60 min) and 30s periodic stdout status with PID/elapsed |
| 117 | Scheduler pagination has no integration test — requires >100 same-type work items to exercise | medium | Added `test_pagination_walks_all_pages_to_find_existing` with `query_page_size=2`; verifies scheduler walks all pages before creating new downstream item |
| 107 | Phase 3 GR-015 uses unvalidated channel adapters | high | GR-015 config switched to validated `fireworks-ai/kimi-k2p6-turbo` (opencode) for all three worker roles; DeepSeek/GLM adapters deferred to future golden runs after isolated smoke tests |
| 078 | Benchmark scope systematically excludes cross-module dependencies — Phase 2 exit criteria measured on easy case | high | GR-014 achieved 91% on cert-watch full DAG; criteria tests added; all 4 proposed fixes completed |
| 116 | _check_assertion_count returns passed=True on SyntaxError | medium | Changed SyntaxError handler to return passed=False with diagnostic_kind="syntax" |
| 115 | ensure_project_venv installs gate tooling into project venv | low | Gate tooling (pytest, mypy, ruff) now installed into separate .venv-gate; project venv stays pure |
| 114 | pre_gate _run_ruff_fast mutates artifact file in-place | medium | Both _run_ruff (gate.py) and _run_ruff_fast (pre_gate.py) now copy artifact to tempdir before ruff --fix |
| 113 | _resolve_extra_env uses unnecessary hasattr | low | Removed hasattr guard; config.credentials_path is a declared dataclass field |
| 112 | Missing DeepSeek standalone channel adapter | medium | Removed FAMILY_OLLAMA dead code from constants; DeepSeek accessible only via opencode channel |
| 111 | No path traversal tests for custom_fields | medium | Added _safe_artifact_path rejecting '..' paths; added test_path_traversal.py |
| 110 | Missing adversarial/fuzz tests for channel output parsing | medium | Added test_output_extraction_adversarial.py with adversarial parsing tests |
| 109 | No circuit breaker or backoff for failing channels | medium | Added per-channel consecutive failure tracking with exponential backoff (base 30s, max 300s) in runner.py |
| 106 | make golden-run lacks process supervision | medium | Created scripts/golden_run_nanny.py; make golden-run uses nanny instead of raw &/wait |
| 105 | ast.parse on arbitrary user code is a DoS vector | medium | Closed as subsumed by BC-104; size guard is primary defense |
| 104 | Gate layer reads artifacts without size limits | medium | Added GATE_MAX_ARTIFACT_SIZE_BYTES and _guard_artifact_size to all evaluate_* entry points |
| 103 | quarantine_attempt uses os.replace which can clobber | low | Added subsecond timestamp and collision counter to quarantine_attempt destination |
| 102 | Scheduler idempotency is pagination-unsafe O(N) | high | Added pagination loop with has_more/next_cursor in _ensure_downstream_item |
| 101 | JSON extraction regex matches invalid nested braces | medium | Replaced greedy regex with json.JSONDecoder.raw_decode scanning; handles nested braces correctly |
| 100 | Output extraction regex is fragile and easily gamed | medium | Prefer last python block, then last any-language block; fallback heuristic limited to 200 lines |
| 099 | SubprocessChannel.invoke replaces entire child environment | medium | SubprocessChannel.invoke now merges extra_env into os.environ explicitly |
| 098 | inject_credentials_into_env copies full os.environ when passed empty dict | low | Changed default env handling: empty dict no longer copies os.environ; only None falls back to os.environ |
| 097 | credentials.py redaction logic is buggy for short values | medium | Clamped visible to max(0, min(4, len(value)-4)); short values now fully redacted |
| 096 | populate_work_items --reset permits arbitrary directory deletion | high | Added _validate_workspace_root_for_reset guard refusing paths outside /tmp, /var/tmp, or project root; rejects '..' segments |
| 032 | Scheduler O(n) idempotency and hardcoded dispatch need hardening | medium | Added `ref_field` and `propagate_fields` to `StageHandoff`; removed `_ref_field_for` hardcoded if/elif; scheduler derives ref fields from `stage_topology`; removed `if next_type == "implementation"` hardcoded type check; O(n) idempotency accepted for Phase 3 single-runner mode |
| 071 | sub.transition(custom_fields=...) merges into WorkItem but API surface implies per-event storage — telemetry footgun | low | Added `test_substrate_event_contract.py` asserting Event has no `custom_fields` attribute; prevents future consumers from assuming per-event storage (Option c) |
| 081 | No criteria test for cert-watch full DAG — structural gap in regression detection for multi-module pipelines | medium | Created `test_gr015_criteria.py` with 7 skip-when-absent criteria tests for cert-watch full DAG golden run (interface_spec lock rate, no ModuleNotFoundError, cross-module imports, work item count, unknown gates, telemetry verify, multi-channel config) |
| 087 | Phase 3 workflow YAML missing — FactoryConfig.phase3() sets version=3 but no matching workflow file exists | high | Created `workflows/phase3.yaml` (v3, same shape as phase2); added "phase3" to `populate_work_items.py` --workflow choices; added `workflow_version` ternary; created `golden-run-015-config.yaml` with multi-channel bindings |
| 088 | Inner gate retry overwrites original artifact in-place | critical | Changed `_inner_gate_loop` to invoke retries into `ad/retry-{N}` subdirectory; original artifact preserved |
| 089 | .pyi stub gate allows docstring-only bodies | high | Rewrote `_check_pyi_stub` to require `ast.Constant(value=...)` or `ast.Pass`; docstring-only stubs now fail |
| 090 | Structural semantics gate ignores keyword-only arguments | high | Added `node.args.kwonlyargs` to `non_self_params` in `_check_structural_semantics` |
| 091 | Relative imports bypass forbidden-module checks | high | `_import_module_name` now falls back to alias name for relative imports without explicit module |
| 092 | SyntaxError swallowed in gate import checks | high | Replaced `except SyntaxError: pass` with explicit failure GateResults in both test-suite and implementation import gates |
| 093 | Command injection in pre_gate import smoke check | high | Added `str.isidentifier()` validation in `_run_import_check` before constructing import statement |
| 094 | Tests write to hardcoded /tmp paths | medium | Replaced hardcoded `/tmp` with `tmp_path` pytest fixture in `test_gate_assertion_count.py` |
| 150 | Isolate opencode session DB per golden run via XDG_DATA_HOME | medium | `scripts/agent_golden_run.py` sets `XDG_DATA_HOME` per run, cleans up isolated DB; `tests/test_agent_golden_run.py` coverage; docs updated |
| 095 | No artifact size limits anywhere | high | Added `MAX_ARTIFACT_SIZE_BYTES = 1_000_000` and size checks in runner and subprocess_channel |
| 086 | Test suite inner gate — pytest --collect-only before outer submission | medium | Added `pre_gate_test_suite()` to `pre_gate.py` running ruff + `pytest --collect-only`; inner gate loop now runs for all three worker roles; gate labels use `GATE_NAME_INNER_*` constants; 7 new tests |
| 085 | Interface spec inner gate — import smoke check before outer submission | medium | Added `pre_gate_interface_spec()` to `pre_gate.py` running ruff + `python -c "import <module>"` smoke check; prevents locked interface_specs with invalid Python from blocking downstream; 7 new tests |
| 058 | Stage handoff and diagnostic dispatch are parallel truth to FactoryConfig | medium | Added `StageHandoff` dataclass and `stage_topology` to `FactoryConfig`; scheduler derives `next_role` from `type_to_role` instead of hardcoded dict; removed `_STAGE_HANDOFF` module-level dict; added `role_for_type()` and `stage_handoff_for()` methods to config; tests updated to use `FactoryConfig.phase2()` and `StageHandoff` objects |
| 084 | _extract_module_name_from_spec derives module names from model-generated spec titles — fragile regex produces mangled names | high | Added `CUSTOM_FIELD_MODULE_NAME` constant; `populate_work_items.py` derives module name from fixture label (`label.removeprefix("wi_")`) and stores as `module_name` custom_field; `resolve_dep_artifacts()` reads `module_name` from custom_fields first, falls back to spec-title regex; parenthetical suffix case now returns canonical name from custom_field; 3 new tests |
| 077 | Runner processes interface_specs without dependency ordering — root deps processed last, cascading test_suite ImportErrors | high | Scheduler `_ensure_downstream_item` now checks `_all_dep_specs_locked()` before creating downstream items; defers test_suite/implementation creation until all dependency_refs point to locked interface_specs; validated by GR-013 (8/8 interface_specs locked, root dep processed first) |
| 083 | Channel base class mutable _family_override survives in invoke() — latent race condition for Phase 4+ parallel invocations | low | Removed `_family_override` instance variable and its mutation from `invoke()`; `family` property now returns `_DEFAULT_FAMILY` unconditionally; per-invocation family carried exclusively in `InvocationResult.family` |
| 082 | Outer gate (gate.py) and inner gate (pre_gate.py) have divergent tool path resolution, failure handling, and error surfaces | medium | BC-079 fixed tool-not-found and exception handling; added final `ruff check` to inner gate matching outer gate's three-step sequence (fix→format→check); remaining `shutil.which` vs `python -m` divergence is benign; full unification deferred to RFC-011 |
| 080 | Router target_role is dead output — architecture suggests capability that doesn't exist, ignored by every consumer | medium | Removed `target_role` from `Route` dataclass, `_PHASE2_DISPATCH`, `route()`, and `custom_fields_update` diagnostics; role dispatch is type-driven via `_role_for_type()`; added introspection test |
| 079 | Inner gate (pre_gate.py) silently passes on tool-not-found and exceptions — contradicts BC-059 fix scope, wastes model budget | high | Aligned inner gate tool-not-found handling with outer gate (BC-059): `_run_mypy_fast`, `_run_pytest_fast` return `passed=False` when tools missing; `_run_ruff_fast` bare exceptions replaced with explicit failure propagation; 4 new tests |
| 073 | ensure_project_venv not invoked when workspace has no requirements.txt — mypy gate fails on project dependencies | medium | `populate_work_items.py --fixtures` copies `requirements.txt` to workspace root; general fix for work-item directory propagation deferred to RFC-006 (Phase 5) |
| 077 | Runner processes interface_specs without dependency ordering — root deps processed last, cascading test_suite ImportErrors | high | Scheduler `_ensure_downstream_item` now checks `_all_dep_specs_locked()` before creating downstream items; defers test_suite/implementation creation until all dependency_refs point to locked interface_specs; 2 new tests, 2 existing tests updated; validated by GR-012 root cause analysis |
| 076 | Dependency .pyi stub bodies are Ellipsis — gate copies stub as runtime dep, causing pytest failures | high | dep_resolution.py resolves locked implementations over stubs; pre_gate.py copies impl .py + spec .pyi separately; stub_only_deps surfaced in prompt; cert-watch full fixture updated with 8 work-units, AC enforcement for runtime dep calls, non-FR library module, 3 diamond consumers |
| 075 | Inner gate loop — pre-submission mypy+ruff+pytest validation for implementer role | medium | Created pre_gate.py with pre_gate_implementation() running mypy+ruff+pytest (short-circuit order) before submit; added _inner_gate_loop() in runner.py with PreGateDeps NamedTuple and configurable inner_gate_retries (default 2); PreGateResult.gate_name now inner_mypy/inner_ruff/inner_pytest; _copy_dependency_pyis promoted to public copy_dependency_pyis; 7 new tests; RFC-009 filed for option #3 |
| 074 | Cross-module dependency types invisible to implementer and test_author | high | context.py now resolves CUSTOM_FIELD_DEPENDENCY_REFS and injects locked_dependency_<module> into extra_artifacts for both roles; gate.py _copy_dependency_pyis writes both .py and .pyi files; prompt templates updated; GR009 validated: impl lock rate 33%→67%, mypy empty-body eliminated; 3 context tests |
| 072 | Cross-module imports fail in gate temp directory | high | Module name derived from spec title via `_extract_module_name_from_spec()`; dependency refs now carry `(module_name, path)` tuples; `_copy_dependency_pyis` uses correct module names; populate_work_items fixes role-based transitions and requirements.txt copy; GR007 validated end-to-end (8/9 locked); 17 tests; 359 pass |
| 061 | 95% code duplication between ClaudeCodeChannel and OpenCodeChannel | high | Created `SubprocessChannel` base class with shared invoke(), error handling, artifact extraction; ClaudeCodeChannel and OpenCodeChannel now thin wrappers (~20 lines each); consumer audit: GATE_NAME_BEHAVIORAL constant added, test_failure_summary.py test data drift fixed; 359 tests pass, lint/audit clean |
| 070 | Telemetry test helper _gate_md always emits payload on pass events — diverges from real gate_process shape | medium | _gate_md() now matches production (pass events carry None payload; gate_name in actor_metadata); added test_gate_pass_event_with_no_payload_resolves_from_metadata data-quality test; 299 tests pass |
| 060 | Channel.invoke inputs_dir is a dead parameter — protocol contract is misleading | high | Removed from Channel protocol, both adapters, runner call site, 15+ test files; added `test_channel_protocol_no_dead_params.py` introspection test; 341 tests pass |
| 069 | Gate names are bare string literals scattered across gate.py — no constants or closed set | medium | Added 23 GATE_NAME_* constants to constants.py; replaced all bare string literals in gate.py, gate_process.py, telemetry.py, failure_summary.py; updated 6 test files; 299 tests pass |
| 068 | Telemetry reporter matches gate events with "unknown" gate name and 0% first-attempt pass rate | high | Added gate_name to ActorMetadata; gate_process emits it; telemetry reads from actor_metadata first with fallback to payload; failure_summary reads from actor_metadata first; logging on unknown; 5 data-quality tests; 298+293 tests pass |
| 067 | No FactoryConfig.phase2() constructor — requires manual setattr bypass | low | Added `FactoryConfig.phase2(**overrides)` classmethod returning pre-populated Phase 2 config |
| 066 | cannot_proceed string overloaded as both state name and transition name | low | Renamed `TRANSITION_CANNOT_PROCEED` to `TRANSITION_ROUTE_TO_CANNOT_PROCEED`; string value unchanged for regista compatibility |
| 064 | No automated channel adapter integration tests — regression detection requires full golden run | medium | Added `test_channel_integration.py` with CLI smoke tests (skipif) and golden-file extraction tests against golden-run-001 fixtures; 11 new tests |
| 065 | Scattered hardcoded page_size values — not derived from FactoryConfig | medium | Added `query_page_size` and `telemetry_event_limit` to `FactoryConfig`; all 5 hardcoded values replaced with config references |
| 062 | Resume-on-gate-fail still wastes Claude budget — BC-046 not fully resolved | high | `_has_prior_gate_fail()` guard now checked in `process_work_item` before resuming; skips resume with log message when prior gate/channel fail exists |
| 059 | Gate soft-fail on missing tooling — returns passed=True when pytest/mypy/ruff not in PATH | critical | Changed all four to passed=False with tool_not_found diagnostic_kind; switched to sys.executable -m for venv-safe tool discovery |
| 057 | Dead code audit — no CI enforcement for unused code accumulation | low | Removed dead code (KIND_TO_ROLE, work_root, redundant assignment); added vulture to CI via `make audit`; 282 tests pass |
| 033 | Telemetry reporter skeleton (Wave 8) | medium | Created telemetry.py with per-(role, channel, gate) pass-rate tables; factory-report CLI; 12 tests |
| 031 | Gate process/runner coverage stuck at 54% — CLI/poll loops need integration tests | medium | Extracted _main(argv) in runner.py, gate_process.py, scheduler.py, telemetry.py; 6 entry-point tests |
| 056 | No single-source-of-truth rule for default values — v1 'string constant gravity' pattern risk | high | Created factory/constants.py; all identifier strings centralized; FactoryConfig.gate_actor_id/worker_actor_id/scheduler_actor_id properties; RoleConfig.family property; 264 tests pass |
| 045 | report.py hardcodes workflow_version=1 — cannot report on Phase 2 runs | medium | report.py now reads workflow_name and workflow_version from FactoryConfig; remaining reporting improvements deferred to BC-033 |
| 054 | No PipelineRuntime namespace — live objects mix with serializable state (v1 BC-361 pattern) | high | Introduced PipelineRuntime frozen dataclass; refactored runner.py, gate_process.py, scheduler.py to use it; 256 tests pass |
| 055 | Stage contracts must be blocking from day one, not warn-and-continue (v1 BC-358 pattern) | high | Gate now fails on missing/absent required refs (missing_dependency, missing_artifact); added DiagnosticKind routing; 8 contract tests; 264 total pass |
| 051 | spec.md still cites BC-021 as Phase 1 blocker — regista hooks appear to work | medium | Updated spec.md §8 to reflect that BC-021 is historical; added cross-ref to BC-051 |
| 050 | interface_architect.md worked example uses deprecated typing — contradicts implementer rules and lint gate | medium | Replaced `Union[Range, Error]` with `Range | Error` and removed `from typing import Union` in worked example |
| 049 | _resume_and_submit has stale default role_name='interface_architect' | low | Removed default; made role_name a required parameter |
| 048 | _check_pyi_stub SyntaxError handler is dead code | low | Removed unreachable `try/except SyntaxError: pass`; `_check_syntax` already catches syntax errors before `_check_pyi_stub` |
| 047 | _create_channel raises 'Multi-channel dispatch not yet implemented' for unknown single channel | low | Added explicit `ValueError` for unknown single-channel names; `NotImplementedError` reserved for genuine multi-channel |
| 046 | Runner resubmits gate-rejected artifacts on subsequent claims — wastes Claude budget | high | Already fixed: `_has_prior_gate_fail` guard (BC-039/040 session) prevents resuming artifacts when gate_fail or channel_fail events exist |
| 044 | OpenCodeChannel mutates self._family on invoke() — race condition corrupts telemetry | high | Added `InvocationResult.family` field; both channels now derive family per-invocation and carry it in the result; runner uses `effective_family` from result; `_family` → `_family_override` pattern for `family` property |
| 043 | test_author.md prompt template truncated mid-file — broken prompt delivered to every test_author invocation | critical | Closed code fence and added closing sections (Reminders: follow interface, cover every AC, exercise ErrorCode variants, single-output-block rule) |
| 042 | AGENTS.md dangerously stale — claims Phase 0 design-only, repo is deep in Phase 2 | high | AGENTS.md already updated in prior session; status section accurately reflects Phase 2 state |
| 053 | evaluate_deterministic_gates is dead code — defined but never called | low | Removed function from gate.py; no callers in codebase or tests |
| 041 | _create_channel factory counts deterministic gate-channel as a second channel | high | Filtered `channel="code"` from channel set before adapter selection; added 4 unit tests covering default, Phase1, Phase2 opencode, and multi-channel configs |
| 040 | OpenCodeChannel adapter — invoke opencode CLI for models with generous usage limits | medium | Extracted output_extraction.py; created opencode_channel.py with per-role model selection; added channel factory in runner.py; family derived from model provider prefix; unit tests added |
| 039 | Implementation lint gate should auto-format before checking and prompt should teach modern typing | medium | Added ruff check --fix + ruff format before lint gate; updated implementer.md with modern typing conventions; added gate-fail resume guard in runner.py |
| 038 | test_suite gate doesn't verify pytest collectability — test-theater gap | medium | Added _run_pytest_collect() to evaluate_test_suite(); fails on 0 collected tests |
| 037 | Escalation routing is a no-op for non-interface_spec work item types | high | Added gate_escalation transition (gating → cannot_proceed); escalation now terminates item instead of cycling |
| 030 | Real Regista read_events should support composite filters (work_item_id + transition) | medium | Regista shipped read_events_composite with AND-composable SQL filters; InMemorySubstrate also supports multi-dimension filters |
| 029 | Test suite coverage gap closure — runner unit, IO failure, config malformed, prompt rendering, regista coupling | medium | Added 22 tests across 4 new files + 5 modified; extracted shared helper; added pytest-cov dep |
| 036 | InMemorySubstrate claim attempt_number resets after transition — escalation path untestable | high | Resolved by regista BC-054: persistent attempt_number on work_items_current in both Postgres and InMemory backends |
| 035 | InMemorySubstrate get_work_item rejects string UUIDs | high | Added `_to_uuid()` coercion in gate_process.py for all ref string lookups (test_suite + implementation gates) |
| 034 | Cannot_proceed without diagnostics file causes double-release | high | Changed else branch to channel_fail transition instead of bare release_claim |
| 028 | Dead MockSubstrate file — tests/_mock_substrate.py | low | Deleted after InMemorySubstrate migration confirmed stable |
| 027 | Wave 5 — cross-stage escalation routing | high | Escalation in router with attempt_threshold; CANNOT_PROCEED_SEAM kind |
| 026 | Scheduler idempotency — global has_link_type query skips unrelated sources | medium | Per-source custom_fields ref check in _ensure_downstream_item |
| 025 | evaluate_implementation missing subprocess gates | high | Added import/mypy/pytest/ruff gates with correct DiagnosticKind |
| 021 | Non-cannot_proceed channel failures produce no regista event for telemetry | high | Added sub.append_event(transition="channel_fail") in _handle_invoke_failure; updated MockSubstrate + tests |
| 024 | _resume_and_submit hardcodes role to interface_architect | high | Parameterized role_name in runner.py; added test |
| 023 | Structural semantics gate rejected module-level AC docstrings | high | Extended _check_structural_semantics to honor module docstrings |
| 022 | Integration tests access regista private API — _mgr._dsn and _project | medium | Introduced factory_config fixture using public regista.project |
| 020 | Config YAML loading untested — from_yaml, from_yaml_or_default | low | Added 6 tests in test_config.py |
| 019 | Channel failure modes untested — timeout, non-zero exit, extraction failure | high | Added 5 tests in test_channel_failures.py |
| 018 | MockSubstrate diverges from real regista — workflow_version filtering, event payload | medium | Fixed query_work_items filtering; removed state_map fallback; verified read_events signature |
| 017 | Router is dead code — route() never called by gate_process | medium | Wired route() into process_gate_item; diagnostics via routing table |
| 016 | AC reference check uses substring search — false positives likely | medium | Removed _check_ac_references; module docstring support added |
| 015 | Integration test private regista API coupling | medium | Public API workaround via factory_config fixture; regista-level request for Regista.dsn remains open |
| 014 | Resume path (_resume_and_submit) untested at integration level | high | Added 3 tests in test_runner_resume.py; fixed hardcoded role |
| 008 | Fixture AC-15 mislabel in 04-verify_event_errors.md | high | Fixed AC-15 text to describe verify_event rejection behavior |
| 009 | context_hash → artifact non-determinism; replay tests must assert structure | high | Added structural_signature() + structurally_equivalent_pyi() in gate.py with 10 tests |
| 010 | populate_work_items.py --reset does not clean workspace | high | Added --workspace-root argument; shutil.rmtree on --reset |
| 011 | Test gap — claim transition not asserted in worker loop tests | high | Added 3 tests (MockSubstrate + live) asserting claim transition event and in_progress state |
| 012 | Context derivation tests should exercise both spec_file paths | high | Added 5 tests covering work-item priority, factory fallback, empty, preservation, hash differentiation |
| 013 | Gate is syntactic-only — semantic gating strategy (option c: hybrid stopgaps) | high | Added structural-semantic checks: function count, return types, parameter presence, AC-to-function binding |
| 007 | Integration tests are stubs | medium | Replaced gate_process stub with real process_gate_item tests; Kimi fixed smoke test; added MockSubstrate pipeline tests |
| 006 | MockSubstrate needed for CI-portable tests | medium | Built MockSubstrate test double + 5 CI-portable pipeline tests |
| 005 | Spec content resolution for context derivation | high | Added spec_file config + loader; Phase 1 uses inline, Phase 2 needs section extraction |
| 004 | cannot_proceed routing has no workflow path | high | Added cannot_proceed terminal state + transition to both YAMLs; runner bypasses gate |
| 002 | Runner skeleton complexity risk | medium | Implemented: 7-module decomposition built per BC-002 spec |
| 003 | Runner idempotency on restart | high | Implemented: §9.12 spec amendment applied, workspace + tests done |
| 001 | Dead error codes: defined but never raised | low | Moved to regista/breadcrumbs/026 — not a factory issue |
