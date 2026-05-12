---
model: fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
datetime: 2026-05-12T01:30 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-12

**Work summary:** Executed three golden runs (GR-015 K2-only, GR-017 GLM implementer, GR-018 DeepSeek implementer) to validate Phase 3 multi-channel dispatch. Discovered and fixed critical regression BC-121 (gate venv isolation). Filed BC-122/123/124 for prompt and gate throughput improvements.

---

## On the project

The Phase 3 machinery works. GR-015 proved multi-role dispatch end-to-end at 100% lock rate. The telemetry pipeline is clean. The gate venv isolation (BC-121) was the only critical regression, and it's now fixed.

But the 0% first-attempt pass rate across all roles is a real throughput problem. The pipeline is functionally correct but economically inefficient — every work item burns 2-3 model invocations where 1 should suffice. This isn't a code architecture problem; it's a prompt engineering problem. The prompts don't teach the model to simulate gate checks mentally.

The GLM implementer failure was the most surprising finding. GLM handled interface specs fine but completely broke on implementation prompts — empty output or unparseable artifacts. This suggests long-context degradation or provider-side tuning bias. DeepSeek was better but still made substantive type/API errors K2 doesn't make.

K2 is the only model that reliably handles all three roles on this workload. That validates the spec's initial binding table recommendation, but it's also a single-point-of-failure risk.

## On the work done

**Confident in:** BC-121 fix. The root cause was clear (project venv used instead of gate venv), the fix was surgical (3 files, ~20 lines changed), and the re-run validated it immediately (GR-015 went from 0% to 100% lock rate). The telemetry also confirms it — no more "pytest not installed" errors.

**Less confident in:** The prompt pre-flight checklist proposal (BC-122). I haven't tested it. It might improve first-attempt rate or it might not. If it doesn't, the problem is that models genuinely can't self-check, and we'll need Phase 4 mechanisms (self-critique, race) instead.

**Awkward:** The GR-017 and GR-018 nanny timeouts. Both runs were killed at 60 minutes with incomplete state. The nanny timeout is correct for CI, but it means partial telemetry. I had to manually query substrate to get final state counts.

**Not sure about:** Whether DeepSeek's implementer failures are model-shaped or prompt-shaped. The mypy errors were real coding mistakes (wrong cryptography API, missing type annotations), not harness issues. More data needed — a shorter-workload run would clarify.

## On what remains

1. **Test BC-122 (prompt pre-flight checklists)** — Quick validation run with updated prompts to see if first-attempt rate improves. If yes, deploy to all prompts. If no, file a note and move to Phase 4.

2. **Define Phase 3 exit criteria quantitatively** — Currently implicit. Need explicit numbers: how many model-family datapoints per role, minimum lock rate, maximum acceptable first-attempt failure rate.

3. **Fleet health monitoring** — No dashboard for per-channel uptime, rate-limit hits, average latency. BC-109 added circuit breaker backoff in runner.py but no telemetry on it.

4. **Run GR-018 to completion** — Currently incomplete. Either restart with cleared stuck item, or accept partial data. DeepSeek implementer data is still useful even at 50%.

5. **Phase 4 jury/race** — Blocked on having enough comparative data to identify "uncertain" roles. Need at least two validated models per role to find disagreement.

## Gaps to flag

- **GLM implementer is not viable** on current prompts/workload. Do not promote GLM to implementer slot without a shorter-workload validation or prompt redesign. Evidence: GR-017, 16 consecutive failures on same work item.
- **0% first-attempt rate** costs 2-3x model budget. At scale, this matters. BC-122/123/124 are all attempts to fix this; none are validated yet.
- **Golden run nanny timeout is too aggressive** for implementer-heavy runs. GLM/DeepSeek runs take longer than K2-only. Consider making timeout model-aware or workload-aware.
- **Telemetry doesn't capture partial runs cleanly** — nanny kills processes mid-flight, leaving work items in `in_progress`. The telemetry reporter counts only completed items, understating the true work done.
- **`event_schema_unknown_fields` warnings** on every telemetry run — `SubmitPayload` has `custom_fields_update` field that the schema doesn't expect. Harmless but noisy; should be cleaned up.
