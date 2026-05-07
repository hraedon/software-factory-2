---
model: deepseek-v4-pro
datetime: 2026-05-07T19:20 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-07

**Work summary:** Completed Phase 2 Waves 0-4 — multi-role pipeline infrastructure (interface_architect → test_author → implementer with gate at each stage + polling scheduler for inter-stage handoff). Migrated SF2 from hand-rolled MockSubstrate to substrate's InMemorySubstrate. Fixed register_actor_role idempotency in substrate (was a pending breadcrumb, now resolved as BC-039). All changes uncommitted as of session end (deferred to /end skill).

---

## On the project

The Phase 2 implementation plan (`plans/phase2-implementation.md`) was solid. Well-scoped, clear exit criteria, good plateau-handling strategy. The 8-wave structure with each wave producing a runnable artifact is the right way to build this kind of pipeline — it kept the session's cognitive load manageable and the test failures localized.

The codebase's discipline around spec authority and breadcrumbs continues to pay off. When I hit the MockSubstrate→InMemorySubstrate migration, every failure mode was obvious because InMemorySubstrate enforces constraints that existed in substrate's spec all along — SF2's tests had just been skating by on a lax double. That's exactly the divergence BC-018 predicted, and it's now permanently closed.

The prompts directory (`src/factory/prompts/` with one `.md` per role) is clean and extensible. Adding `test_author.md` and `implementer.md` was a copy-extend operation rather than a refactor.

## On the work done

The channel_fail reconciliation (Wave 0) was straightforward — one switch from `append_event` to `transition` plus test assertion updates. The gate expansion (Wave 1) added `evaluate_test_suite` and `evaluate_implementation` with appropriate diagnostic kinds. The role context derivation (Waves 2-3) with `extra_artifacts` for locked interface/test suite content is clean — the `render_prompt` appends them as sections, the prompt templates reference the named sections, and everything flows through `context_hash` determinism.

The scheduler is the weakest piece. It's polling-based (30s intervals) because hook integration is deferred. The idempotency check uses `has_link_type` which is correct for the single-project case but won't detect a scenario where the same source type+state produces multiple downstream items of the same type. Acceptable for Phase 2 — the Wave 4 plan explicitly allows polling as mitigation — but it should be replaced with hooks before Phase 3.

The InMemorySubstrate migration exposed an issue with `read_events`: it used mutually-exclusive filter branches, so `read_events(work_item_id=X, transition="channel_fail")` didn't work. Fixed by rewriting as a composable pipeline. This was a real bug in substrate's test double, not just a SF2 compatibility issue.

The register_actor_role fix is small but meaningful — removed 4 try/except wrappers across runner and gate_process. The change is purely behavioral (no API surface change), and the test was updated from "raises on duplicate" to "duplicate is no-op." Low-risk across both backends.

## On what remains

**Needed before Phase 2 exit (plan Waves 6-8):**

1. Wave 6: Integration hardening against real substrate. The pipeline smoke test uses InMemorySubstrate — it needs a live Postgres run with MockChannel to exercise the substrate API properly. Also, idempotency tests (kill-and-restart at each stage) across all three roles.

2. Wave 7: Golden-run-002. Requires Claude CC. Run all 16 items (10 primary + 3 secondary + 2 routing-stress + 1 adversarial) through the real channel end-to-end, record artifacts, replay with MockChannel. This is the acceptance test that gates Phase 2 exit.

3. Wave 8: Telemetry reporter skeleton. Extend `report.py` to read substrate events and produce `(role, channel) → first-attempt pass rate` tables. This establishes the baseline that Phase 3's channel additions will be measured against.

**Deferred cleanup:**

- `tests/_mock_substrate.py` is dead code. No test imports it. Delete it after confirming the InMemorySubstrate migration is stable through at least one full golden run.
- The `cannot_proceed` transition in runner.py still has a `release_claim` fallback path (line 257). This is correct for the case where the channel fails without writing `cannot_proceed.json`, but the double-release issue I fixed for `channel_fail` doesn't apply here because `cannot_proceed` goes to a terminal state, not a `transition` that auto-releases. Still, worth verifying the real substrate's behavior on `release_claim` after `cannot_proceed` transition.

## Gaps to flag

- **Scheduler idempotency is fragile** (`scheduler.py:85-89`). The `has_link_type` check prevents creating a second `test_suite` for the same `interface_spec`, but it's a global scan — if there are multiple `interface_spec` items locked simultaneously, it could skip some. Low probability in Phase 2's single-channel sequential mode, but worth hardening before parallel workers arrive.

- **InMemorySubstrate `read_events` filter composition** (`_in_memory.py:523-573`). My rewrite is correct for the SF2 use cases (work_item_id + transition), but I didn't add tests for the timerange filter composing with work_item_id. The existing substrate conformance tests pass, but they likely don't exercise the composite case. Not a SF2 issue — flag for substrate.

- **`evaluate_implementation` doesn't actually run mypy/pytest/ruff** (`gate.py:312-370`). It only checks file exists, non-empty, and syntax. The plan says Wave 1 adds these as deterministic gates, but I deferred them — they require subprocess integration and test fixture layout that the smoke tests don't exercise yet. The `DiagnosticKind.IMPL_MYPY/IMPL_PYTEST/IMPL_LINT` entries exist in the router dispatch table, but they're unreachable without the subprocess calls. This is the biggest gap between the plan and the implementation.

- **MockSubstrate file still exists** (`tests/_mock_substrate.py`). It's unreferenced but still on disk. Confusing to future agents. Delete after golden-run-002 confirms InMemorySubstrate migration is stable.

- **`phase2.yaml` version 2 pins `substrate_version: "0.1.0"`** — substrate may have bumped since. The SF2 roundtrip test (`test_phase2_workflow_roundtrip.py`) doesn't assert on substrate_version. Minor.
