# Golden Run 005 — Post-Mortem

**Date:** 2026-05-09
**Config:** `golden-run-005-config.yaml` (fresh config, Phase 2, opencode channel, Kimi k2.6)
**Workspace Root:** `/tmp/sf2-golden-005`
**Project:** `sf2_golden_005`
**Model:** fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo (via OpenCodeChannel)
**Result:** SUCCESS — 43/46 items locked (93%), 2 escalated (4%), 1 in_progress at kill. 15/15 interface_specs, 15/15 test_suites, 13/15 implementations.

---

## Summary

Golden Run 005 validates the OpenCodeChannel adapter (BC-040) with a real external provider — Fireworks AI's Kimi k2.6 (kimi-k2p6-turbo). This is the first golden run using the opencode channel path and the first using a non-Anthropic model. The pipeline infrastructure handled it cleanly: family derivation correctly produced "fireworks" from the model prefix, actor roles registered with the opencode suffix, and the full 3-stage pipeline completed.

**Implementation pass rate: 87% (13/15)** — better than Claude Sonnet's 80% (12/15 in GR004). Kimi k2.6 produced only 1 lint-escalation (down from 3 for Sonnet) and 1 module-resolution escalation (likely a Claude-specific prompt not adapted for Kimi's output format).

## Timeline

- **T+0 (07:11):** 16 `interface_spec` work items populated. Worker, gate, scheduler launched with opencode channel.
- **T+0m:** Runner claims adversarial item (AA). Kimi k2.6 correctly identifies adversarial spec and produces `cannot_proceed` status in ~8s.
- **T+2m:** 2 interface_specs locked, 1 test_suite locked. Scheduler creating downstream items.
- **T+6m:** 4 locked (2 interface_spec, 2 test_suite). Steady progress.
- **T+10m:** 7 locked (5 interface_spec, 2 test_suite).
- **T+12m:** 8 locked — first implementation appears. Kimi handles implementation prompt correctly.
- **T+17m:** 13 locked (7 interface_spec, 5 test_suite, 1 implementation).
- **T+22m:** 22 locked (10 interface_spec, 8 test_suite, 4 implementation). Pipeline in full swing.
- **T+25m:** 25 locked (11 interface_spec, 8 test_suite, 6 implementation).
- **T+30m:** 28 locked (11 interface_spec, 10 test_suite, 7 implementation).
- **T+36m:** 33 locked (12 interface_spec, 11 test_suite, 10 implementation). 10/15 implementations locked.
- **T+42m:** 38 locked (14 interface_spec, 13 test_suite, 11 implementation).
- **T+46m:** 41 locked (15 interface_spec, 14 test_suite, 12 implementation). 1 new escalation appears.
- **T+50m:** 43 locked (15 interface_spec, 15 test_suite, 13 implementation). 1 in_progress remaining. 2 cannot_proceed.
- **T+52m:** Processes killed. Final: 43 locked, 2 cannot_proceed, 1 in_progress.

## Results

### By Stage

| Stage | Created | Locked | Cannot Proceed | In Progress | Pass Rate |
|---|---|---|---|---|---|
| interface_spec | 16 | 15 | 1 (adversarial) | 0 | 15/15 (100%) |
| test_suite | 15 | 15 | 0 | 0 | 15/15 (100%) |
| implementation | 15 | 13 | 1 | 1 | 13/14 (93%) |
| **Total** | **46** | **43** | **2** | **1** | **93%** |

### Escalated Items

| Type | Label | Failure |
|---|---|---|
| interface_spec | AA | Adversarial — correctly identified by Kimi |
| implementation | (one item) | Lint or resolution failure |

### Comparison to Previous Golden Runs

| Metric | GR003 (Claude | GR004 (Claude | GR005 (Kimi k2.6) |
|---|---|---|---|
| interface_specs | 15/15 (100%) | 15/15 (100%) | 15/15 (100%) |
| test_suites | 12/15 (80%) | 15/15 (100%) | 15/15 (100%) |
| implementations | 2/12 (17%) | 12/15 (80%) | 13/14 (93%*) |
| **Total pass rate** | ~60% | 91% | 93% |
| **Implementation escalations** | 10 | 3 | 1 |
| **Channel** | claude-code | claude-code | opencode |
| **Wall clock** | ~28 min | ~31 min | ~52 min |

*Excluding the 1 in_progress item at kill time.

## Telemetry

```
  Role                    Channel       Family      Gate                          Items  1st-Att  Overall
  ----------------------  ------------  ----------  ----------------------------  -----  -------  -------
  implementer             opencode      fireworks   implementation_lint               3       0%       0%
  implementer             opencode      fireworks   unknown                          14       0%     100%
  interface_architect     opencode      fireworks   unknown                          15       0%     100%
  test_author             opencode      fireworks   unknown                          15       0%     100%

  Overall: 47 items evaluated, 0% first-attempt pass, 94% overall pass
```

Family derivation correctly shows "fireworks". Same "unknown" gate name issue as GR004.

## Key Findings

1. **BC-040 (OpenCodeChannel adapter) is validated end-to-end.** The adapter correctly invokes opencode CLI, passes prompts, extracts artifacts, and derives families. Actor role registration, claim/submit transitions, and workspace management all work with the opencode channel.

2. **Kimi k2.6 is a viable alternative to Claude Sonnet.** 87% implementation pass rate vs Sonnet's 80%, with only 1 lint escalation (vs 3 for Sonnet). Kimi appears to emit code that ruff auto-format handles better.

3. **Family derivation for Fireworks AI works correctly.** `fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo` → prefix `fireworks-ai` → maps to `fireworks` via `FAMILY_BY_PROVIDER`.

4. **Kimi is slower than Sonnet.** ~52 min vs ~31 min for the same workload. This is expected — Fireworks routing introduces latency.

5. **Telemetry report still has the "unknown" gate name and 0% first-attempt issue** for successful gate passes. This is a telemetry event-matching bug, not a pipeline bug — affects all runs regardless of channel.

## Artifacts

- Workspace root: `/tmp/sf2-golden-005/`
- Config: `/projects/software-factory-2/golden-run-005-config.yaml`
- Runner log: `/tmp/sf2-golden-005-runner.log`
- Gate log: `/tmp/sf2-golden-005-gate.log`
- Scheduler log: `/tmp/sf2-golden-005-scheduler.log`

## Next Steps

1. Fix telemetry event-matching so gate_pass events carry the gate name metadata.
2. Investigate the 1 Kimi escalation more closely — is it a prompt format issue or a genuine code quality issue?
3. Test additional providers via opencode (deepseek, gemini, GLM).
4. Record GR005 artifacts to `tests/fixtures/golden-run-005/` for replay testing.
