---
model: fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
datetime: 2026-05-14T19:25Z
project: software-factory-2
---

# Session Reflection — 2026-05-14

**Work summary:** Post-mortem and remediation of GR-026 (GLM-attempted Phase 4 golden run). Resolved BC-139 (critical: review/jury infinite retry loop), filed BC-140 (agent-mediated run protocol), implemented `agent_golden_run.py` wrapper, preserved workspace and drafted golden-run report. 670 tests pass, 13 skipped.

---

## On the project

This codebase is impressively hardened for its phase. The architecture (runner/gate/scheduler/telemetry) cleanly separates concerns, and the breadcrumb discipline is real — not just issue tracking but an explicit refusal to let v1's "string constant gravity" recur. The constants.py centralization, the `FactoryConfig` single-source-of-truth, and the per-session worklog all signal a team that learned from prior pain.

What's fragile is the boundary between the pipeline's internal retry logic and external agent execution. BC-139 revealed that the router's `_ESCALATABLE_KINDS` is a closed set that must be manually kept in sync with every new gate kind. The `GENERIC` fallback to `Route(target_state=STATE_NEW)` is a footgun — any new diagnostic kind that isn't explicitly added to both the classification logic and the escalation set will loop forever. This is the v1 pattern of "imperative if/elif chain grew unbounded" (RFC-005) playing out in miniature.

The telemetry system is solid but has a data-quality gap: the "unknown" gate name in GR-026's telemetry came from looping items where the runner skipped resume, creating unmatched gate events. This is a subtle signal that the telemetry event pairing isn't robust to the runner bypassing its normal submit path.

## On the work done

The BC-139 fix is clean and minimal — two new `DiagnosticKind` values, classification logic updates, escalation set membership, and a hard stop in the runner. I'm confident it's correct. The 8 new tests cover both classification and escalation at/below threshold.

The `agent_golden_run.py` wrapper is a pragmatic band-aid, not architecture. It duplicates some runner logic (attempt threshold checking, log tailing) because the pipeline lacks a proper event bus or status endpoint. If this project moves to Phase 5 and gets real workloads, the wrapper will become a maintenance burden — but for now it prevents the exact failure mode that just cost 32M tokens and a working session.

The golden-run report for GR-026 captures what matters: the loop dynamics, the token burn analysis, the comparison with prior runs, and the post-run fix. I wrote it following the GR-008 format which has proven useful for cross-run comparison.

What I'm less confident about: the `agent_golden_run.py` pre-flight breadcrumb scanner is regex-based and brittle. If the breadcrumbs README format changes, the scanner will silently fail open. It needs a test, but that's out of scope for this session.

## On what remains

Immediate (before next GR):
1. **GR-027 re-run with BC-139 fix and agent wrapper** — validate that review/jury failures now escalate cleanly.
2. **Exercise `jury_disagree` path** — GR-026 had 0 disagreement cases. Need a fixture with intentional defects to force multi-family divergence.

Short-term (Phase 4 validation):
3. **Gemini CLI validation** — adapter exists but disabled. The Node 24 PATH fix is documented; needs a smoke test.
4. **BC-140 hardening** — Add `--no-cleanup` flag preservation, wrapper timeout, and maybe a JSON status output for programmatic monitoring.

Medium-term (Phase 5 prep):
5. **RFC-002 (observer/event system)** — The wrapper's log-grep monitoring is a hack. A real event bus would make BC-140's guardrails machine-implementable rather than regex-based.
6. **RFC-005 (composable failure/escalation architecture)** — `_ESCALATABLE_KINDS` should not be a hand-maintained set. The router should derive escalatability from gate metadata or config.

## Gaps to flag

- **`src/factory/router.py:64`**: The `GENERIC` fallback is a trap. Any new gate kind that forgets to add itself to `_classify_diagnostic` and `_ESCALATABLE_KINDS` will loop. Consider a default `cannot_proceed` for unknown kinds beyond threshold, or a CI test that asserts every gate name emitted by `gate.py` has a matching `DiagnosticKind`.
- **`scripts/agent_golden_run.py:85-100`**: Breadcrumb scanning is regex-based. No test coverage. If README format drifts, pre-flight checks will silently pass dangerous runs.
- **`src/factory/runner.py:192-198`**: The `claim_near_budget` hard stop is a belt-and-suspenders fix, but the runner still transitions the claim before checking. The ordering (claim → check → release) is correct but a race condition exists if the gate process claims the same item between release and next poll. In practice negligible at 5s poll interval, but worth noting.
- **Telemetry unknown gate**: `cross_family_review` appeared as "unknown" in telemetry because looping items produced gate events without matching submit events. The telemetry pairing logic (`test_telemetry.py`) doesn't account for runner-bypassed submits.
- **Workspace backup is uncommitted**: `.factory/gr026-workspace-backup/` is 119MB and not in git. This is correct (don't bloat repo), but there's no `.gitignore` entry for `.factory/gr*-workspace-backup/`. Add it.
