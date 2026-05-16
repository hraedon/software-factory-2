# Golden Run 008 — Kimi k2p6-turbo via OpenCode, cert-watch-mini fixture

**Date:** 2026-05-10
**Config:** `golden-run-008-config.yaml`
**Channel:** opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo)
**Fixture:** cert-watch-mini (3 work-items: certificate_model, FR-02, FR-03)

## Result

| Metric | Value |
|---|---|
| Total work items | 9 |
| Locked | 7 (78%) |
| Cannot proceed | 2 |
| Interface spec lock rate | 3/3 (100%) |
| Test suite lock rate | 3/3 (100%) |
| Implementation lock rate | 1/3 (33%) |

## Per-work-item detail

| WI | Type | State | Attempts | Notes |
|---|---|---|---|---|
| 4c37bb9f | interface_spec | locked | 2 | certificate_model |
| 35642a15 | interface_spec | locked | 2 | FR-02 TLS scan |
| 343cc699 | interface_spec | locked | 2 | FR-03 file upload |
| 36d16669 | test_suite | locked | 4 | FR-02 (required multiple attempts) |
| 8be5ef32 | test_suite | locked | 2 | certificate_model |
| e728518a | test_suite | locked | 2 | FR-03 |
| e8f9495b | implementation | locked | 2 | certificate_model — PASSED all gates |
| 2cc46a19 | implementation | cannot_proceed | 4 | FR-02 — mypy empty-body error |
| f5c167c1 | implementation | cannot_proceed | 4 | FR-03 — mypy empty-body error |

## Failure analysis

Both escalated implementations failed `implementation_mypy` with the same error:

```
certificate_model.py:22: error: Missing return statement  [empty-body]
certificate_model.py:27: error: Missing return statement  [empty-body]
```

This is the same root cause as GR006a/GR007: implementations that depend on `certificate_model` produce code where mypy's `empty-body` check fires on methods that use `...` (Ellipsis) or empty `pass` as stub implementations. The BC-072 fix (correct module name resolution for cross-module dependencies) is working — the issue is now specifically about how the implementer generates code that mypy considers incomplete.

The certificate_model implementation (which has no cross-module dependencies) locked successfully, confirming that single-module implementations work well.

## Telemetry

```
  Role                    Channel       Family      Gate                              Hash  Items  1st-Att  Overall  MeanDur
  ----------------------  ------------  ----------  ----------------------------  --------  -----  -------  -------  -------
  implementer             opencode      fireworks   implementation                16f480ba      1       0%     100%    85.5s
  implementer             opencode      fireworks   implementation_mypy           16f480ba      2       0%       0%   216.3s
  interface_architect     opencode      fireworks   interface_spec                45df1cbc      3       0%     100%    32.7s
  test_author             opencode      fireworks   test_suite                    7230fe58      3       0%     100%   147.1s
  test_author             opencode      fireworks   test_suite_collect            7230fe58      1       0%       0%   139.8s

  Overall: 10 items evaluated, 0% first-attempt pass, 70% overall pass
```

`telemetry --verify`: PASS (0 unknown gates, 0 orphans, 0 confounding warnings).

## Phase 2 exit criteria assessment

Per plan §2.3, the binding test is `test_gr006a_meets_phase2_exit_threshold` (impl lock rate >= 70%):

- **Implementation lock rate: 33% (1/3)** — FAILS the >=70% threshold
- **Implementation lock rate: 33% (1/3)** — also below the 40% "pause" threshold

Per the plan's decision matrix:
- `test_gr006a_meets_phase2_exit_threshold` fails (< 40% impl) → **PAUSE Phase 3; root-cause.**

## Root cause (recurring)

The mypy `empty-body` check is a consistent failure mode across GR006a, GR007, and now GR008. The implementer (regardless of channel — Claude Sonnet or Kimi k2p6) generates method stubs that mypy's `--strict` or `empty-body` check rejects. The fix is not in the gate (the gate is correct to reject incomplete-looking code) but in the implementer's prompt:

1. The implementer prompt should explicitly instruct: "Do not use `...` (Ellipsis) or empty `pass` as method bodies. Every method must have a concrete implementation that returns a value of the declared return type."
2. Alternatively, the mypy gate configuration could add `--no-strict-optional` or disable the `empty-body` error code (less desirable — it's catching real issues).

## Comparison with prior runs

| Run | Channel | Impl lock rate | Notes |
|---|---|---|---|
| GR004 | claude-code (Sonnet) | 12/15 (80%) | Curated primary-spec fixtures, no cross-module deps |
| GR005 | opencode (kimi-k2p6-turbo) | 13/15 (87%) | Curated primary-spec fixtures, no cross-module deps |
| GR006a | claude-code (Sonnet) | 1/3 (33%) | cert-watch-mini, cross-module deps; mypy empty-body |
| GR007 | opencode (kimi-k2p6-turbo) | 1/3 (33%)* | cert-watch-mini, BC-072 fixed; mypy empty-body |
| GR008 | opencode (kimi-k2p6-turbo) | 1/3 (33%) | Same fixture, same channel, same failure mode |

*GR007 had 2/9 locked (one implementation was locked but with an mypy error that was later caught).

The cross-module mypy issue is the consistent blocker. Single-module implementations lock at 80-87%; cross-module implementations lock at 33%.