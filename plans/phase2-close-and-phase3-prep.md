# Phase 2 Close + Phase 3 Prep — Implementation Plan

**Status:** ready to execute
**Author:** claude-opus-4-7
**Date:** 2026-05-09
**Origin:** synthesizes positions from `debate/positions/{claude-opus-4-7,gemini-cli,glm-5.1,deepseek-v4-pro}/` rounds 1 and 2, plus follow-on items 011, 012, NEW-001/002/003 and gemini's R2-001/005.

## Scope

This plan covers the bundle of work between "BC-068 done" (current state, commit `f0bf295`) and "Phase 3 fleet integration ready to start." It is organized into three execution windows:

- **Window A (Days 1–2):** prerequisites for GR006a — bundled telemetry refactor, venv shim, behavioral-gate stub, assertion-counting gate, GR006a fixtures and criteria tests.
- **Window B (Day 3):** execute GR006a; apply test-encoded thresholds; record Phase 2 close decision.
- **Window C (post-GR006a, pre-Phase 3):** channel-protocol cleanup, channel composition refactor, credentials, budget breaker, notification hook, golden-run automation.

Out-of-scope items (deferred-with-trigger) are listed in §4 with their trigger conditions.

## Current state recap (commit f0bf295)

- BC-068 resolved: `gate_name` lives in `ActorMetadata` (read primary) and `payload.diagnostics` (fallback); 5 data-quality tests added.
- BC-069 resolved: 23 `GATE_NAME_*` constants in `constants.py`.
- BC-070 resolved: `_gate_md()` test helper matches production event shapes.
- `prompt_template_hash` is *computed* in `context.py:derive_context()` (line 197) but only flows into the composite `context_hash` — not surfaced as a standalone telemetry dimension.
- Substrate `ActorMetadata` supports: `role`, `channel`, `model`, `family`, `gate_name`, `attempt_n`, `context_hash`. Anything beyond that goes through `payload` or `custom_fields`.
- Telemetry produces first-attempt and overall pass rates per `(role, channel, family, gate_name)`. Mean wall-clock and gate-failure breakdown (spec §7) are not implemented.
- 293 unit tests passing.

## 1. Window A — pre-GR006a (Days 1–2)

### 1.1 Bundled telemetry refactor (Day 1, ~1.5 days)

Single PR, single test-suite run. Touches `event_schemas.py` (new), `actor_metadata` flow, `telemetry.py`, `runner.py`, `gate_process.py`, all corresponding tests.

#### A1. Consumer-level event schemas (Debate 009)

Create `src/factory/event_schemas.py`:

- One dataclass per event payload sf2 produces: `SubmitPayload`, `GatePassPayload`, `GateFailPayload`, `ChannelFailPayload`, `CannotProceedPayload`. Each has `to_dict()` and `from_dict()`.
- `from_dict()` raises `EventSchemaError` on missing required fields, *warns* (via structlog) on unknown fields (forward-compatible).
- Required fields per type are derived from the existing event-write call sites — do not invent new contract; codify what's already produced.

Update producers (`gate_process.py`, `runner.py`, `scheduler.py`) to construct payloads via these dataclasses, not raw dicts.

Update `telemetry.py` and `failure_summary.py` to read payloads via `from_dict()`.

Tests:
- `tests/test_event_schemas.py` — round-trip per payload type: construct → `to_dict()` → `from_dict()` → assert equal.
- `tests/test_event_schemas_replay.py` — load anonymized event subset (5–10 events) captured from GR004 fixtures into `from_dict()`; assert no validation errors. Establishes the regression fixture for future shape drift.

#### A2. Prompt template hash in telemetry (debate items 011 + NEW-001)

GLM and Deepseek converged on this independently — the strongest "build it" signal of the round.

- `derive_context()` already computes `prompt_template_hash`. Keep it where it is; promote it into the producer payload.
- Add `prompt_template_hash: str | None` field to substrate's `ActorMetadata` dataclass (substrate change — coordinate with substrate maintainer; this is additive and backward-compatible).
- Pass `prompt_template_hash` into `ActorMetadata` at every `transition()` site that records work performed by a prompt-driven worker (the 5 ActorMetadata constructions in `runner.py`). Gate events do not get it (gates aren't prompt-driven).
- `GateAttempt` dataclass in `telemetry.py` gains `prompt_template_hash: str | None`.
- `compute_pass_rates()` groups by `(role, channel, family, gate_name, prompt_template_hash)`. Truncated 8-char prefix shown in the table to keep it readable.
- `format_pass_rate_table()` emits a warning row when a `(role, channel, family, gate_name)` group has multiple `prompt_template_hash` values: `"WARNING: prompt changed within comparison group; results confounded"`.

Implementation note: prefer GLM's content-hash design; use Deepseek's git-hash *only* if a `git rev-parse` succeeds within 100ms — otherwise fall back to content hash. This avoids forking behavior between checkout-clean and detached-HEAD environments.

Tests:
- `tests/test_actor_metadata_prompt_hash.py` — runner submits an event, asserts `prompt_template_hash` present in actor_metadata.
- `tests/test_telemetry_prompt_versioning.py` — synthetic events with two different hashes → confounding warning emitted; same hash → no warning.

#### A3. Attempt-level latency (debate item 012)

Spec §7 names `mean wall-clock` as a required telemetry column. Building it now closes that gap.

- Wrap `channel.invoke()` calls in `runner.py` with `time.monotonic()`. Record `invocation_start_time` and `invocation_end_time` (both monotonic) into `payload`, not `actor_metadata`. Substrate already takes opaque payload; no further substrate change.
- `GateAttempt` gains `duration_seconds: float | None`.
- `PassRateRow` gains `mean_duration_seconds: float`, `median_duration_seconds: float`.
- `format_pass_rate_table()` adds "Mean Duration" column.
- `FactoryConfig` gains `per_channel_timeout: dict[str, int] | None = None`. If set, `runner.py` resolves the per-channel value before falling back to `timeout_seconds`. Backward-compatible (default `None`).

Tests:
- `tests/test_telemetry_latency.py` — synthetic events with timing → mean duration computed; missing timing → graceful fallback to `None`.
- `tests/test_runner_per_channel_timeout.py` — per-channel timeout overrides global; missing override falls back.

#### A4. `telemetry --verify` CLI (Debate 002 follow-through)

Original BC-068 listed this as "Optional"; with GR006a coming, it must exist as a callable gate.

- Add `--verify` flag to `telemetry.py:_main()`.
- When set, reads the live substrate (or a passed event-dump path) and reports:
  - `unknown_gate_name_count` (must be 0 to pass)
  - `unknown_gate_name_rate` (must be < 0.01 to pass)
  - `orphan_submit_count` (submit events with no following gate event for the same work_item, beyond the in-progress set)
  - `unmatched_gate_count` (gate events with no preceding submit)
  - `confounding_warning_count` (multi-hash groups from A2)
- Exit code 0 on pass, 1 on fail. Designed to be called from a Makefile target as a hard gate.

Tests:
- `tests/test_telemetry_verify.py` — clean event log → exit 0; injected unknown gate name → exit 1; injected orphan submit → exit 1.

#### A5. Bundle deliverable

One commit (or one PR if cleaner). Test count target: +20 to +30 over the current 293. Run `make check` clean before merge. Replay-fixture test (from A1) is the keystone — without it, future shape drift recurs.

### 1.2 Per-project venv helper (Debate 006, 50-line variant)

Single-file utility in `src/factory/venv.py` (or appended to `workspace.py`):

```python
def ensure_project_venv(project_dir: Path) -> Path:
    """Return the python executable for the per-project venv,
    creating/refreshing it from <project_dir>/requirements.txt.
    Returns sys.executable if no requirements.txt exists.
    """
```

- Cache by SHA-256 of `requirements.txt`; rebuild on hash change (recorded in `.venv/.deps_hash`).
- Use `uv venv` if available; fall back to `python -m venv`. `uv pip install` if available; fall back to `pip install`.
- Pre-installs `pytest`, `mypy`, `ruff`.
- No `VenvManager` class. No state.

Modify `gate.py:_run_pytest`, `_run_mypy`, `_run_ruff` to accept optional `python_executable` parameter, default `None` → `sys.executable`. Update call sites to thread through `ensure_project_venv(workspace)` when `config.use_project_venv` is True.

`FactoryConfig` gains `use_project_venv: bool = False`. Default off through Phase 4. Flipped on for GR006a config.

Tests:
- `tests/test_venv.py` — empty requirements → empty venv created; with requirements → packages installed; hash unchanged → reuse; hash changed → rebuild.
- `tests/test_gate_with_project_venv.py` — pytest gate against a fixture importing `cryptography` succeeds with venv on, fails without.

### 1.3 Behavioral gate spec + stub + one failing Playwright test (Debate 001, deepseek's design)

Total cap: 3 hours. If exceeded, scope is wrong.

- Add §6.x subsection to `spec.md`: behavioral gate ordering (after mechanical, before frontier judge), failure routing (back to implementer with screenshots/DOM state), AC↔scenario binding contract.
- `src/factory/behavioral_gate.py` stub: `evaluate_behavioral(work_item, scenarios) -> GateResult`. Returns `GateResult(passed=True, gate_name="behavioral", skipped=True)` if `scenarios` is empty. Otherwise raises `NotImplementedError("behavioral gate scheduled for Phase 5; see plans/behavioral-gate.md")`.
- Add `behavioral_scenarios: list[dict] | None = None` field to work-item custom_fields schema (no producer or consumer beyond the stub yet).
- `tests/test_behavioral_gate_phase5.py`:
  - One Playwright scenario against a deliberately broken FastAPI fixture (`tests/fixtures/broken_fastapi/app.py` — returns `500` on `/`).
  - Marked `@pytest.mark.skip(reason="behavioral gate not yet implemented; this test is the spec for Phase 5")`. The skip reason *is* the accountability.
  - When the gate exists, remove the skip; the test should pass.

No Playwright dependency installed yet. The test imports Playwright behind `pytest.importorskip("playwright")` so `make check` does not require it.

### 1.4 Assertion-counting gate (Debate 005 part 1, GLM's design)

Cheap test-theater filter. ~20 lines.

- Extend `gate.py:evaluate_test_suite()` after existing collect-only check:
  - Parse each collected test file's AST.
  - Count `Assert` nodes per test function (including those inside `with` blocks and nested calls).
  - Fail if any test function has zero assertions, OR total assertions across the file < number of test functions.
- New constant `GATE_NAME_TEST_SUITE_ASSERTIONS` in `constants.py`.
- New `DiagnosticKind.TEST_NO_ASSERTIONS`.
- Router dispatch entry: `TEST_NO_ASSERTIONS` → `test_author`.

Tests:
- `tests/test_gate_assertion_count.py`: zero-assertion test → fail; one-assertion test → pass; mixed (some have, some don't) → fail with file-level diagnostic.

### 1.5 GR006a fixtures + criteria tests (Debate 008, deepseek's test-as-criteria)

#### Fixtures

`tests/fixtures/cert-watch-mini/`:
- `wi_certificate_model.md` — interface_spec for `Certificate` dataclass. ~5 ACs (subject DN, issuer DN, NotBefore/NotAfter, SANs, fingerprint_sha256, raw DER, `days_until_expiry()`, parse-from-DER, error-on-malformed).
- `wi_fr02_tls_scan.md` — interface_spec for FR-02 TLS scanning. ~6 ACs from cert-watch v1 spec FR-02 + glossary "scanned entry." `interface_ref: certificate_model`.
- `wi_fr03_file_upload.md` — interface_spec for FR-03 file upload + parse. ~5 ACs from cert-watch FR-03. `interface_ref: certificate_model`.

Source: `/projects/software-factory/projects/cert-watch/spec.md` §4 FR-02 and FR-03.

#### `golden-run-006a-config.yaml`

Mirror `golden-run-005-config.yaml` shape. Channel: claude-code, model: sonnet (match GR004 baseline so the comparison is clean). `use_project_venv: true`. `requirements.txt` for the workspace contains `cryptography>=42.0`.

#### Criteria tests

`tests/test_gr006a_criteria.py`:

```python
def test_gr006a_meets_phase2_exit_threshold():
    """GR006a must achieve >= 70% implementation lock rate
    across FR-02 and FR-03 to declare Phase 2 complete."""
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    impl_pass_rate = load_gr006a_telemetry()["implementation_pass_rate"]
    assert impl_pass_rate >= 0.70

def test_gr006a_produces_no_unknown_gate_names():
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    assert load_gr006a_telemetry()["unknown_gate_rate"] == 0.0

def test_gr006a_cross_module_imports_resolve():
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    assert load_gr006a_artifacts()["cross_module_import_success"]

def test_gr006a_telemetry_verify_passes():
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    # Calls `python -m factory.telemetry --verify`; asserts exit 0
    ...
```

Skip-when-absent + assert-when-present: lets `make check` stay green pre-run, then becomes the binding gate after the run.

### 1.6 Window A merge gate

Before Window B starts:
- All A1–A5 tests pass.
- `make check` clean.
- `python -m factory.telemetry --verify` against an existing GR005 event dump exits 0.
- `tests/test_gr006a_criteria.py` collects (skips, doesn't error) under `make check`.

## 2. Window B — execute GR006a (Day 3)

### 2.1 Pre-flight checklist

Run sequentially; stop on any failure:

1. `make check` clean.
2. `python -m factory.telemetry --verify` against GR005 event dump → exit 0.
3. `tests/fixtures/cert-watch-mini/` exists with all three spec files.
4. `golden-run-006a-config.yaml` validates against `FactoryConfig.from_yaml()`.
5. Project venv at `/tmp/sf2-gr006a/.venv` either absent (will be created) or has `cryptography>=42.0` installed.
6. Substrate fresh project `sf2_gr006a` is empty.

### 2.2 Run

```bash
python populate_work_items.py --reset --project sf2_gr006a \
    --fixtures tests/fixtures/cert-watch-mini

python -m factory.runner    --config golden-run-006a-config.yaml \
    --workspace /tmp/sf2-gr006a > /tmp/gr006a-runner.log 2>&1 &
python -m factory.gate_process --config golden-run-006a-config.yaml \
    --workspace /tmp/sf2-gr006a > /tmp/gr006a-gate.log 2>&1 &
python -m factory.scheduler --config golden-run-006a-config.yaml \
    > /tmp/gr006a-scheduler.log 2>&1 &
```

Monitor by polling `query_work_items` every 30s. Expected wall-clock: 30–90 min for 3 work-items (cert-watch ACs are denser than curated fixtures).

Hard kill threshold: 3 hours. If exceeded, kill, capture state, file breadcrumb.

### 2.3 Apply criteria

After the run completes (all items locked, escalated, or in_progress timeout):

1. Run `python -m factory.telemetry --verify` against the new event dump. Must exit 0.
2. Run `python -m factory.telemetry --config golden-run-006a-config.yaml > /tmp/gr006a-telemetry.md`.
3. Symlink/copy results into the location `tests/test_gr006a_criteria.py` reads from.
4. Run `pytest tests/test_gr006a_criteria.py -v`.

The pytest exit code is the Phase 2 close decision:

| Pytest result | Phase 2 decision |
|---|---|
| All pass | Close Phase 2; proceed to Window C |
| `test_gr006a_meets_phase2_exit_threshold` fails (40–70% impl) | Close with monitoring; file breadcrumb naming the specific gap |
| `test_gr006a_meets_phase2_exit_threshold` fails (<40% impl) | Pause Phase 3; root-cause |
| `test_gr006a_telemetry_verify_passes` fails | Stop. Telemetry corruption invalidates the result. Re-run after fix |

### 2.4 Record

Produce `golden-run-006a-log.md` (mirror GR005 log structure). Archive event dump + artifacts to `tests/fixtures/golden-run-006a/`. Commit `tests/test_golden_run_006a.py` replay regression.

Update `phase2-implementation.md` exit-criteria table with GR006a result. Update `.factory/worklog.md`.

## 3. Window C — pre-Phase 3 prep (post-GR006a)

Order matters here; each item depends on the previous landing cleanly.

### 3.1 NEW-002 — remove dead `inputs_dir` from `Channel` protocol (BC-060)

First commit of the channel work. Mechanical refactor.

- Remove `inputs_dir` from `Channel.invoke()` signature in `channel.py`.
- Remove from `ClaudeCodeChannel.invoke()` and `OpenCodeChannel.invoke()`.
- Remove from all call sites in `runner.py`.
- Update the ~10 tests passing dummy `inputs_dir`.
- Add `tests/test_channel_protocol_no_dead_params.py` (deepseek's introspection test) — fails if any param on `Channel.invoke()` is unused by all concrete adapters.

Move `breadcrumbs/060-channel-invoke-inputs-dir-dead-parameter.md` to `breadcrumbs/resolved/`.

### 3.2 Channel composition refactor (Debate 003, GLM's design)

- `tests/test_channel_contract_consistency.py` (deepseek's equivalency test) — first. Both `ClaudeCodeChannel` and `OpenCodeChannel` invoked with the same prompt + role_config + workspace must produce structurally equivalent results (same artifact count, same family derivation, same cannot_proceed detection). Mock the actual subprocess; assert the surrounding shape.
- Then create `src/factory/channel/_subprocess.py` — `run_with_timeout`, `capture_stdout`, `format_invoke_error` as standalone functions.
- And `src/factory/channel/_artifacts.py` — `extract_artifacts_from_output`, `detect_cannot_proceed` as standalone functions.
- Refactor `claude_code_channel.py` and `opencode_channel.py` to compose these (no inheritance, no `SubprocessChannel` base).
- Re-run the equivalency test; must still pass.

Move `breadcrumbs/061-channel-adapter-code-duplication.md` to `breadcrumbs/resolved/`.

Hard rule: do not write a 3rd channel adapter (K2/GLM/DeepSeek/Gemini) until this lands. Any future PR adding a new adapter without composing the shared utilities is rejected at review.

### 3.3 Credentials (Debate 007, schema only)

- New file `src/factory/credentials.py` (~80 lines):
  - `load_credentials(path: Path = DEFAULT_PATH) -> dict[str, str]` reading `~/.config/factory/credentials.yaml`.
  - `inject_into_env(creds: dict, provider: str) -> dict` — returns modified env dict for subprocess.
- `RoleConfig` gains optional `provider: str | None`. If set, runner injects `creds[provider]` into the channel adapter's invocation env.
- structlog redaction: register a processor that masks any value matching common key prefixes (`fk-`, `zai-`, `sk-`, `gsk-`, `pk-`) to `<redacted:XXXX****>`. Add `tests/test_log_redaction.py` greping logs for known prefixes.

Reject for now (per all 4 reviewers' synthesis): rotation detection, `key_id` audit, fallback-on-401 routing. Re-open as RFC if pain emerges in Phase 3.

### 3.4 R2-001 budget circuit breaker

- `FactoryConfig` gains `max_mission_budget_usd: float | None = None`, `max_work_item_retries: int = 5`.
- New `src/factory/budget.py` — `track_invocation(channel, model, tokens_in, tokens_out)` updates running cost using a per-provider price table (~10 entries; lives in `constants.py:PROVIDER_PRICE_PER_1K_TOKENS`).
- Scheduler polls budget every N events; when exceeded, transitions all `in_progress` items to `cannot_proceed` with `escalation_reason="budget_exhausted"`.
- `tests/test_budget.py` — synthetic invocations push cost over threshold → all in-progress items released and escalated.

Coarse cost model is fine. Don't model API rate limits; v1 had this and it was not load-bearing.

### 3.5 R2-005 notification hook (minimal)

- `src/factory/notifications.py` — `notify(event_type, payload)` function. Reads webhook URL from env (`FACTORY_NOTIFICATION_WEBHOOK_URL`). POSTs JSON. If env unset, no-op (warns once on startup).
- Wired to two events from scheduler: `cannot_proceed` (any reason) and `budget_exhausted`.
- One adapter: generic webhook. No Slack/Discord-specific code yet — operators can use Slack's incoming webhook URL or a relay.
- `tests/test_notifications.py` — webhook URL set → POST attempted; URL unset → no-op.

Pair with R2-001 — budget breaker without notification is silent failure.

### 3.6 NEW-003 `make golden-run` automation

Last item. Codifies the runbook only after the runbook is settled by the preceding work.

```makefile
# Makefile
golden-run:
	test -n "$(CONFIG)" || (echo "CONFIG=<path> required" && exit 1)
	python populate_work_items.py --config $(CONFIG) --reset
	python -m factory.runner --config $(CONFIG) &
	python -m factory.gate_process --config $(CONFIG) &
	python -m factory.scheduler --config $(CONFIG) &
	wait
	python -m factory.report --config $(CONFIG)
	python -m factory.telemetry --config $(CONFIG)
	python -m factory.telemetry --verify --config $(CONFIG)
```

`tests/test_golden_run_automation_smoke.py` — runs `make golden-run CONFIG=tests/fixtures/test-golden-run-config.yaml` against a 2-item InMemorySubstrate fixture; asserts exit 0; asserts telemetry rows produced.

The `--verify` step at the end is the data-quality gate: any unknown gate names or orphan events fail the run loudly.

## 4. Deferred (with named triggers)

| Item | Source | Trigger |
|---|---|---|
| Pipeline checkpoints | Debate 004 | Single GR exceeds 2h, OR mid-run crash loses meaningful work, OR Phase 3 fallback chains compound wall-clock |
| Mutation testing | Debate 005 part 2 | After Phase 3 multi-channel data exists; build with calibration fixture (deepseek's design): 5 ops, threshold from p25 of fixture runs |
| Substrate-side schema registry | Debate 009 part 2 | When a 2nd substrate consumer exists |
| Event log retention build | Debate 010 part 2 | Auto-breadcrumb fires (event_count > 5000 OR replay > 10s) |
| Behavioral gate (Playwright impl) | Debate 001 | GR006b prep; cert-watch FR-01 dashboard is the natural pilot |
| Spec mutability / `propose_spec_amendment` | R2-002 | When Socratic spec source exists (Phase 5+) |
| DB migration strategy / Alembic gate | R2-003 | Before GR006b (cert-watch full) |
| Security gates (bandit, pip-audit) | R2-004 | Bundle with GR006b prep; pairs with venv |
| Dead-code lifecycle automation | R2-006 | Trivial extension of `make audit`; bundle with NEW-003 if cheap |
| GR006b (full cert-watch) | `plans/gr006b-execution.md` | Phases 3+4 complete, behavioral gate exists, R2-003 migrations exist |

For each deferred item: open or update the corresponding RFC (RFC-006, RFC-007, RFC-008 already exist for venv, mutation, checkpoints) so the deferral is visible in `breadcrumbs/`.

## 5. Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Substrate `ActorMetadata` change for `prompt_template_hash` requires substrate maintainer coordination | Medium | Field is optional + additive; ship substrate change first as backward-compatible release; sf2 then consumes |
| Bundled telemetry refactor (A1–A4) introduces regression in existing tests | Medium | Each sub-item ships with its own tests; run full suite between sub-items, not only at end |
| GR006a venv setup fails on first run (compile of `cryptography`) | Low | Pre-build venv as part of pre-flight checklist (§2.1 step 5) |
| GR006a impl pass rate < 40% (curated fixtures don't generalize) | Medium-Low | This is the experiment's purpose. Failure path documented in §2.3 — not a project failure |
| Channel composition refactor (3.2) breaks existing channel tests | Low | Equivalency test (3.2 first step) catches regressions before they ship |
| Budget breaker false-fires during GR006a | Low | Set `max_mission_budget_usd` generously for first run ($25); calibrate after |
| `make golden-run` `&&` chain stops on transient failure | Low | Acceptable — silent partial completion is worse. If a step is genuinely flaky, fix the step |

## 6. Estimated total effort

| Window | Effort | Calendar |
|---|---|---|
| A (telemetry refactor + venv + behavioral stub + assertion gate + GR006a fixtures/tests) | ~2 days focused | 2 working days |
| B (GR006a execution + decision + record) | ~½ day | 1 working day (run is async-monitored) |
| C (BC-060 → composition → credentials → budget → notify → automation) | ~3 days focused | 3–4 working days |
| **Total** | **~5.5 days** | **6–7 working days** |

## 7. Done criteria

This plan is complete when:

1. All §1 items (A1–A5, 1.2–1.5) merged. `make check` clean. Test count ~325 (+30 from current 293).
2. GR006a executed; `tests/test_gr006a_criteria.py` collected (passing, failing, or skipped — not erroring); decision recorded in `phase2-implementation.md` and `.factory/worklog.md`.
3. All §3 items merged in order. `make check` clean.
4. `make golden-run CONFIG=...` runs end-to-end on at least one config (the GR006a config or the smoke fixture).
5. `breadcrumbs/060-...` and `breadcrumbs/061-...` moved to `resolved/`.
6. Phase 3 channel-adapter work (K2 first) has a clean foundation: composed utilities, prompt-versioned telemetry, latency-tracked telemetry, credentials infrastructure, budget circuit breaker, notification hook, and `make golden-run` to drive the comparison.
