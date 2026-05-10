---
model: deepseek-v4-pro
datetime: 2026-05-10T20:00 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-10

**Work summary:** Resolved BC-061 (95% channel adapter code duplication) by extracting a `SubprocessChannel` base class. Performed a consumer audit of all `gate_name` event readers, fixing test data drift in `test_failure_summary.py` and adding `GATE_NAME_BEHAVIORAL` constant. Opened no new breadcrumbs.

---

## On the project

The project is in good structural health. The breadcrumb discipline that eluded v1 is holding — 4 open breadcrumbs remain (072, 071, 058, 063, 032... wait, let me check), all medium/low severity, plus 8 RFCs for deferred work. The spec-driven phasing continues to pay off: Phase 2 has been run to completion on curated fixtures (87–93% lock rates across GR004/005) and validated on an adversarial multi-module fixture (GR007 at 89%).

The architecture's biggest strength is its resistance to the principal's constraint (systems architect, not developer). The mechanical gates catch implementation drift at the byte level; the telemetry pipeline surfaces (role, channel, family) pass rates without asking anyone to review code. The factory is genuinely converging on its stated outcome: consistently better than a line-of-business person asking ChatGPT.

The biggest remaining structural risk is not a design flaw but a scaling concern: Phase 3 adds 4 channel adapters, and without the BC-061 fix just applied, that would have been 6 copies of the same 100+ line invoke() method. The SubprocessChannel base class eliminates that multiplier. Next in line: pipeline checkpoints to prevent losing 30–50 minute golden runs to crashes, and an adversarial fixture run to calibrate whether 87% on curated sets predicts real-world performance.

## On the work done

**BC-061 (SubprocessChannel base class):** This was clean. The two channel adapters were truly ~95% identical — the only real differences were the CLI binary name/flags and family derivation logic. The base class captures all shared behavior: `subprocess.run`, stdout capture, `raw_stdout.txt` write, artifact extraction via `output_extraction.py`, cannot_proceed JSON detection, error formatting, timeout handling, and `artifact{ext}` naming. Both adapters are now ~20 lines each. The `ClassVar` annotations on `CMD`, `_NAME`, `_DEFAULT_FAMILY` satisfy ruff's RUF012 and make the subclass contract explicit.

**Consumer audit:** Traced every reader of `gate_name` across the codebase. Found two fixable issues:
1. `behavioral_gate.py:25` — bare `"behavioral"` string. Added `GATE_NAME_BEHAVIORAL` to `constants.py` and referenced it.
2. `tests/test_failure_summary.py` — used `"syntax"` and `"ac_reference"` as fake gate names in test payload dicts. These didn't correspond to any real `GATE_NAME_*` constant. Replaced with `GATE_NAME_INTERFACE_SPEC_SYNTAX` and `GATE_NAME_INTERFACE_SPEC_STUB` (the closest actual gate name constants to the test's intent).

Verified that `telemetry.py` and `failure_summary.py` already have consistent three-tier gate_name fallback: `actor_metadata` → `payload.diagnostics` → `"unknown"`. The remaining bare `"g"` in `test_event_schemas.py:65` is intentional (schema warning test).

Backward compatibility maintained: `claude_code_channel.py` still re-exports `_extract_artifact_from_output` and `_extract_json_from_output` since 4 test files import them from there.

359 tests pass, 0 lint errors, 0 dead code. 309 lines deleted, 34 added.

## On what remains

1. **Pipeline checkpoints** (~100 lines). The most valuable pre-Phase 3 work. Golden runs at 30–50 minutes are too long to lose to a crash, and they will happen. A stage-level checkpoint that saves work-item state to disk and resumes from the last checkpoint would add resilience cheaply.

2. **Adversarial golden run** with a multi-module + stateful fixture. The GR007 (89% on 3-module cross-dependency fixture) is a partial calibration, but it still uses the cert-watch-mini domain which the codebase has been tuned against. A genuinely novel fixture would calibrate whether 87% on curated fixtures predicts success on real LoB work.

3. **Phase 3 channel adapter development.** BC-061 makes this dramatically cheaper — each new adapter (K2 API, GLM, DeepSeek Ollama, Gemini CLI) is now ~20 lines specifying CLI binary, flags, and family derivation. The `SubprocessChannel` base class handles everything else.

4. **BC-058** (Stage handoff/diagnostic dispatch parallel truth). Not a blocker for Phase 3 start, but the scheduler and router have two independent mechanisms for deciding what happens next. This is architecturally similar to the v1 problem of two parallel encodings of the same workflow — worth fixing before the dispatch logic gets more complex.

## Gaps to flag

- **No behavioral validation story.** Factory's Phase 3/4/5 add more roles but none of them test whether the running software *behaves* correctly. The behavioral gate stub exists but raises `NotImplementedError`. This becomes load-bearing in Phase 5 (first real workload). No mitigation in place.

- **Test-only prompt template hash mismatch risk.** The `prompt_template_hash` in telemetry groups results by prompt content, but prompt templates live under version control. If a test run uses a different prompt version than production, telemetry data is confounded. The confounding warning is in place, but there's no automated check that golden run configs reference the same prompt versions as production.

- **InMemorySubstrate drift surface (BC-063).** Every new substrate feature adds divergence risk between the InMemory test double and Postgres. The integration test surface is an order of magnitude smaller than the unit test surface. Not urgent for Phase 2, but as Phase 3 exercises substrate's API more aggressively (hooks, validators, dead-letter requeue), this gap widens.
