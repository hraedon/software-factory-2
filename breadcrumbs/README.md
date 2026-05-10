# Breadcrumbs

Defects, design questions, and improvements for software-factory-2. One file per item, numbered for reference. Numbers do not imply priority — see `severity` in each file's frontmatter.

Schema follows substrate's breadcrumbs convention; see `/projects/substrate/breadcrumbs/README.md` for the canonical reference.

## Schema

```yaml
---
number: "001"
title: Short descriptive title
severity: critical | high | medium | low
status: proposed | in_progress | implemented | obsolete
kind: bug | design | improvement
author: who-raised-it
date: "YYYY-MM-DD"
tags: [topic, stage-N, dep-substrate-NNN]
related: ["002", "003"]
---
```

## Severity

- **critical** — blocks correct operation; v2 cannot be trusted for stated guarantees
- **high** — load-bearing spec property unfulfilled; silent-correctness risk
- **medium** — defect with workaround or limited blast radius
- **low** — edge case, polish, or minor ergonomics

## Tags

Reusable tags:
- `stage-0` through `stage-10` — pipeline stage from spec §4
- `dep-substrate-NNN` — blocks on substrate breadcrumb NNN
- `channel-claude`, `channel-k2`, `channel-glm`, `channel-deepseek`, `channel-gemini`, `channel-opencode`
- `tier-a`, `tier-b`, `tier-c` — capability tier (spec §5)
- `runner`, `telemetry`, `gate`, `jury`, `race`, `failure-routing`
- `dep-v1-NNN` — lesson from software-factory v1 breadcrumb NNN
- `rfc` — design proposal awaiting a future phase; not actionable yet

## Open

| ### Active Bugs & Improvements

| # | Title | Severity | Status |
|---|---|---|---|
| 076 | Dependency .pyi stub bodies are Ellipsis — gate copies stub as runtime dep, causing pytest failures | high | implemented |
| 073 | ensure_project_venv not invoked when workspace has no requirements.txt — mypy gate fails on project dependencies | medium | proposed |
| 071 | sub.transition(custom_fields=...) merges into WorkItem but API surface implies per-event storage — telemetry footgun | low | proposed |
| 058 | Stage handoff and diagnostic dispatch are parallel truth to FactoryConfig | medium | proposed |
| 063 | InMemorySubstrate drift history — integration test surface is 10x smaller than unit test surface | medium | proposed |
| 032 | Scheduler O(n) idempotency and hardcoded dispatch need hardening | medium | proposed |

### RFCs (awaiting upstream phases)

RFC breadcrumbs use the `RFC-` prefix to distinguish design proposals that cannot be acted on until later phases. They are candidates for improvement, not actionable defects.

| # | Title | Severity | Phase Needed |
|---|---|---|---|
| RFC-001 | Prompt conflict detection — v1 BC-383 shows silent failure when role prompts contradict | high | Phase 3 (multi-role prompts) |
| RFC-002 | Critical observer degradation — v1 BC-359 shows silent swallowing loses telemetry data | high | Phase 3 (hooks/observers) |
| RFC-003 | Channel adapter auth-mode detection — v1 BC-376 shows env var injection breaks native auth | high | Phase 3 (multi-channel adapters) |
| RFC-004 | Auto-generated pipeline documentation — v1 docs froze while pipeline grew | medium | Phase 3 (pipeline complexity) |
| RFC-005 | Composable failure/escalation architecture — v1 imperative if/elif chain grew unbounded | medium | Phase 4 (jury disagreement) |
| RFC-006 | Per-project venv isolation for subprocess gates — v1 BC-192, prevents ModuleNotFoundError in real workloads | medium | Phase 5 (first real workload) |
| RFC-007 | Test efficacy scoring via mutation testing gates — v1 BC-107/186, mechanical antidote to test theater | high | Phase 4–5 (jury / real workload) |
| RFC-008 | Pipeline checkpoint and surgical resume system — v1 BC-122, preserve progress across 30–50 min runs | medium | Phase 3–5 (fleet / real workload) |
| RFC-009 | Interactive debugging inner loop — channel tool-use surface for implementer | high | Phase 5+ (evidence threshold: 3+ golden runs with pytest-in-inner-loop still failing) |

## Resolved

| # | Title | Severity | Resolution |
|---|---|---|---|
| 075 | Inner gate loop — pre-submission mypy+ruff+pytest validation for implementer role | medium | Created pre_gate.py with pre_gate_implementation() running mypy+ruff+pytest (short-circuit order) before submit; added _inner_gate_loop() in runner.py with PreGateDeps NamedTuple and configurable inner_gate_retries (default 2); PreGateResult.gate_name now inner_mypy/inner_ruff/inner_pytest; _copy_dependency_pyis promoted to public copy_dependency_pyis; 7 new tests; RFC-009 filed for option #3 |
| 074 | Cross-module dependency types invisible to implementer and test_author | high | context.py now resolves CUSTOM_FIELD_DEPENDENCY_REFS and injects locked_dependency_<module> into extra_artifacts for both roles; gate.py _copy_dependency_pyis writes both .py and .pyi files; prompt templates updated; GR009 validated: impl lock rate 33%→67%, mypy empty-body eliminated; 3 context tests |
| 072 | Cross-module imports fail in gate temp directory | high | Module name derived from spec title via `_extract_module_name_from_spec()`; dependency refs now carry `(module_name, path)` tuples; `_copy_dependency_pyis` uses correct module names; populate_work_items fixes role-based transitions and requirements.txt copy; GR007 validated end-to-end (8/9 locked); 17 tests; 359 pass |
| 061 | 95% code duplication between ClaudeCodeChannel and OpenCodeChannel | high | Created `SubprocessChannel` base class with shared invoke(), error handling, artifact extraction; ClaudeCodeChannel and OpenCodeChannel now thin wrappers (~20 lines each); consumer audit: GATE_NAME_BEHAVIORAL constant added, test_failure_summary.py test data drift fixed; 359 tests pass, lint/audit clean |
| 070 | Telemetry test helper _gate_md always emits payload on pass events — diverges from real gate_process shape | medium | _gate_md() now matches production (pass events carry None payload; gate_name in actor_metadata); added test_gate_pass_event_with_no_payload_resolves_from_metadata data-quality test; 299 tests pass |
| 060 | Channel.invoke inputs_dir is a dead parameter — protocol contract is misleading | high | Removed from Channel protocol, both adapters, runner call site, 15+ test files; added `test_channel_protocol_no_dead_params.py` introspection test; 341 tests pass |
| 069 | Gate names are bare string literals scattered across gate.py — no constants or closed set | medium | Added 23 GATE_NAME_* constants to constants.py; replaced all bare string literals in gate.py, gate_process.py, telemetry.py, failure_summary.py; updated 6 test files; 299 tests pass |
| 068 | Telemetry reporter matches gate events with "unknown" gate name and 0% first-attempt pass rate | high | Added gate_name to ActorMetadata; gate_process emits it; telemetry reads from actor_metadata first with fallback to payload; failure_summary reads from actor_metadata first; logging on unknown; 5 data-quality tests; 298+293 tests pass |
| 067 | No FactoryConfig.phase2() constructor — requires manual setattr bypass | low | Added `FactoryConfig.phase2(**overrides)` classmethod returning pre-populated Phase 2 config |
| 066 | cannot_proceed string overloaded as both state name and transition name | low | Renamed `TRANSITION_CANNOT_PROCEED` to `TRANSITION_ROUTE_TO_CANNOT_PROCEED`; string value unchanged for substrate compatibility |
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
| 051 | spec.md still cites BC-021 as Phase 1 blocker — substrate hooks appear to work | medium | Updated spec.md §8 to reflect that BC-021 is historical; added cross-ref to BC-051 |
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
| 030 | Real Substrate read_events should support composite filters (work_item_id + transition) | medium | Substrate shipped read_events_composite with AND-composable SQL filters; InMemorySubstrate also supports multi-dimension filters |
| 029 | Test suite coverage gap closure — runner unit, IO failure, config malformed, prompt rendering, substrate coupling | medium | Added 22 tests across 4 new files + 5 modified; extracted shared helper; added pytest-cov dep |
| 036 | InMemorySubstrate claim attempt_number resets after transition — escalation path untestable | high | Resolved by substrate BC-054: persistent attempt_number on work_items_current in both Postgres and InMemory backends |
| 035 | InMemorySubstrate get_work_item rejects string UUIDs | high | Added `_to_uuid()` coercion in gate_process.py for all ref string lookups (test_suite + implementation gates) |
| 034 | Cannot_proceed without diagnostics file causes double-release | high | Changed else branch to channel_fail transition instead of bare release_claim |
| 028 | Dead MockSubstrate file — tests/_mock_substrate.py | low | Deleted after InMemorySubstrate migration confirmed stable |
| 027 | Wave 5 — cross-stage escalation routing | high | Escalation in router with attempt_threshold; CANNOT_PROCEED_SEAM kind |
| 026 | Scheduler idempotency — global has_link_type query skips unrelated sources | medium | Per-source custom_fields ref check in _ensure_downstream_item |
| 025 | evaluate_implementation missing subprocess gates | high | Added import/mypy/pytest/ruff gates with correct DiagnosticKind |
| 021 | Non-cannot_proceed channel failures produce no substrate event for telemetry | high | Added sub.append_event(transition="channel_fail") in _handle_invoke_failure; updated MockSubstrate + tests |
| 024 | _resume_and_submit hardcodes role to interface_architect | high | Parameterized role_name in runner.py; added test |
| 023 | Structural semantics gate rejected module-level AC docstrings | high | Extended _check_structural_semantics to honor module docstrings |
| 022 | Integration tests access substrate private API — _mgr._dsn and _project | medium | Introduced factory_config fixture using public substrate.project |
| 020 | Config YAML loading untested — from_yaml, from_yaml_or_default | low | Added 6 tests in test_config.py |
| 019 | Channel failure modes untested — timeout, non-zero exit, extraction failure | high | Added 5 tests in test_channel_failures.py |
| 018 | MockSubstrate diverges from real substrate — workflow_version filtering, event payload | medium | Fixed query_work_items filtering; removed state_map fallback; verified read_events signature |
| 017 | Router is dead code — route() never called by gate_process | medium | Wired route() into process_gate_item; diagnostics via routing table |
| 016 | AC reference check uses substring search — false positives likely | medium | Removed _check_ac_references; module docstring support added |
| 015 | Integration test private substrate API coupling | medium | Public API workaround via factory_config fixture; substrate-level request for Substrate.dsn remains open |
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
| 001 | Dead error codes: defined but never raised | low | Moved to substrate/breadcrumbs/026 — not a factory issue |
