---
model: deepseek-v4-pro
datetime: 2026-05-07T05:55 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-07

**Work summary:** Closed all 7 open breadcrumbs from the Phase 1 audit (BC-014 through BC-020 plus BC-021 opened+closed in the same session), raised 4 new ones (BC-022 through BC-024), added 31 tests across 3 new test files, and made 3 code fixes in the runner, gate, and gate process. 125/125 tests pass.

---

## On the project

The codebase is in a healthy spot post-Phase 1 exit. The architecture is tightly constrained by the spec (a good thing), and the 7-module decomposition (runner, gate, context, workspace, channel, config, router) has held up under scrutiny. The phase-1-exit tag means the golden-run criteria are met; the risk now is architectural drift as Phase 2 roles are added.

Two things feel fragile:
1. **MockSubstrate is a real liability.** It's a hand-rolled test double that now has ~290 lines of branching logic. Every time we add a substrate feature to the production code, MockSubstrate needs a corresponding change. The `append_event` method I added today is the latest example. If substrate adds new behavior, MockSubstrate will silently diverge again (BC-018 was exactly this). Consider whether substrate's own test fixtures could be reused.
2. **The router abstraction is still weak.** I wired it into `gate_process.py`, but the `route()` function only knows about Phase 1 transitions (`gating` → `locked`/`new`). When Phase 2 adds `gate_fail → test_author` or `jury_disagree → interface_architect`, the `_PHASE1_ROUTING` dict will need to grow or be replaced. The current design doesn't cleanly handle conditional routing (e.g., "route to test_author if the critique implicates tests, else to implementer"). This is flagged in the spec §4 but not yet in code.

## On the work done

The breadcrumbs were all honest gaps — none was padding. The fixes were straightforward:

- **BC-014 (resume path untested):** The new tests found a real bug (hardcoded `role="interface_architect"` in `_resume_and_submit`). This validates the value of the breadcrumb system — the AC was "test the resume path" and the test immediately found an issue that would have corrupted telemetry in Phase 2.
- **BC-016 (AC substring false positives):** Removing `_check_ac_references` was the right call. The structural semantics check is strictly stronger and produces no false positives. I was slightly nervous breaking backwards compatibility with tests that relied on substring matching, but the module-docstring discovery (BC-023) confirmed the structural check was incomplete.
- **BC-017 (router dead code):** Wiring the router in was cheap and sets up Phase 2. I'm moderately confident the router abstraction will survive, but see "On the project" above.
- **BC-018 (MockSubstrate divergence):** The `transition` removal of the hardcoded `state_map` was the most invasive change — it required that all MockSubstrate tests register a workflow. Thankfully they already did (via `conftest.py` or explicit `register_workflow_file`).
- **BC-021 (channel_fail telemetry gap):** This was the most substantive design work of the session. Using `append_event` (rather than `transition`) is correct: it records an event without forcing a workflow state change, which would have required updating both YAMLs and potentially breaking Phase 1's simplicity. The diagnostics payload shape is intentionally minimal — it can be enriched when the telemetry reporter is built.

What I'm less confident in:
- The `channel_fail` event is not consumed by anything yet. `derive_failures()` only looks at `gate_fail` events. A Phase 2 telemetry ticket should explicitly call out `channel_fail` as a source.
- The `FailingChannel` test double in `test_channel_failures.py` is clean but duplicates logic from `MockChannel`. Consolidating test doubles might be worth a small refactor before Phase 2.

## On what remains

Immediate next steps (Phase 2 prep):
1. **Add `channel_fail` to `derive_failures()`** — The failure summary library should aggregate both `gate_fail` and `channel_fail` events so the context derivation logic can include channel failures in `prior_failures`.
2. **Expand `evaluate_interface_spec` for new role types** — Test author and implementer will need their own gate functions. The current `evaluate_interface_spec` is hardcoded for `interface_spec`; `process_gate_item` has a placeholder `else` branch for unknown types.
3. **Add channel adapters for K2, GLM, DeepSeek, Gemini** — Spec §5 Phase 3, but the adapter interface is already defined in `channel.py`. The work is mechanical: each needs a `invoke()` implementation that knows its harness quirks.
4. **Telemetry reporter skeleton** — Spec §7 calls for a nightly pass-rate reporter. It doesn't need to run automatically yet, but a script that reads substrate events and produces the `(role, channel) → pass rate` table would validate the event schema.

Structural gaps (not blocking but worth tracking):
- MockSubstrate will need another round of alignment when substrate adds link payloads or validator callbacks. Set a policy: every substrate version bump requires a MockSubstrate audit.
- The factory's `tests/conftest.py` depends on a live Postgres instance. For CI portability, consider whether the `mock_substrate` fixture should be the default for unit tests, with integration tests gated behind `--integration`.

## Gaps to flag

- `derive_failures()` ignores `channel_fail` events (`src/factory/failure_summary.py:19-39`). When Phase 2 adds retry logic, channel failures need to surface in prompt context.
- `_PHASE1_ROUTING` in `src/factory/router.py:16-22` will need conditional routes for Phase 2. The current `Route` dataclass has no `condition` field.
- `process_gate_item` has an `unknown_type` fallback at `src/factory/gate_process.py:95-100` that just fails. Each new role type will need its own gate function.
- `tests/test_gate_interface_spec.py` does not test module-level docstring AC binding directly. I added module-docstring support to `_check_structural_semantics` but the existing tests only exercise function/class docstrings. The `test_gate_process.py` integration artifacts exercise it indirectly.
- `MockSubstrate.append_event` does not update `last_event_seq`, `last_event_at`, or `next_event_seq` on the `WorkItem`. This is fine for current tests (they don't assert on those fields) but could cause divergence if a future test does.
- `sub.close()` is never explicitly tested — no test asserts that `Substrate.close()` is called on worker/gate process exit. The `try/finally` blocks in `run_worker` and `run_gate` are coverage blind spots.
