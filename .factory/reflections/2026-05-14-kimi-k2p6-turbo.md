---
model: fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
datetime: 2026-05-14T03:30 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-14

**Work summary:** Validated and corrected the BC-137 capability-probe framework, then ran it against 5 of 6 requested models (Kimi K2.6 Ollama, GLM-5.1 z.ai, GLM-5.1 Ollama, DeepSeek v4 Pro Ollama, Qwen 3.6-27b Ollama). Produced per-role outputs, self-scored against the rubric, and wrote the deliverable report at `.factory/analysis/2026-05-14-model-capability-evaluation.md`. Fixed three probe inconsistencies: interface_architect rubric said `N/A` for contradictory ACs (wrong), test_author rubric said `Ignores or stubs` for impossible dependency (wrong), and test_author/implementer prompts lacked structured-failure channels (documented, not fixed in prompts). Added canonical flawed upstream artifacts to the fixture.

---

## On the project

The pipeline is impressively instrumented — 637 tests, telemetry, inner gates, multi-model jury. But the model-placement decisions in `spec.md` §5 are still largely theoretical. This session is the first time anyone has systematically evaluated whether the models assigned to roles can actually do those roles. The fact that GLM-5.1 (assigned to `cross_family_reviewer` and `frontier_judge` in the spec) **fails the hard floor on `interface_architect`** is not a surprise — it's not assigned to that role — but it's a data point the spec didn't have before.

The more uncomfortable finding: **Qwen 3.6-27b times out on code-generation roles even at 600s.** This means the "six validated model+provider combinations" claim in BC-137 is actually "five available, one broken (Gemini), one operationally unfit for half its potential roles (Qwen)." The pipeline's redundancy story is thinner than the spec suggests.

## On the work done

**What went well:**
- The probe design is sound. All five models that completed review/judge roles flagged all five planted defects. The cross-family reviewer role is genuinely the most reliable gate.
- DeepSeek v4 Pro's test_author output was the most rigorous — negative capacity, negative refill rate, tokens>capacity, negative tokens. That validated the probe's ability to discriminate rigorous from superficial.
- The canonical flawed upstream artifacts (`reference_flawed_interface.pyi`, `reference_flawed_tests.py`, `reference_flawed_implementation.py`) make the probe reproducible. Any future model can be run through the same inputs.

**What I'm unsure about:**
- **Self-scoring bias.** I (K2.6) scored all outputs, including my own and competitors'. I tried to be objective, but there's no external validator. The principal should spot-check 2-3 cells.
- **The "amend vs reject" gray zone.** GLM-5.1 amended the spec (changed `consume -> float | None`) rather than rejecting it. I scored this as "fail" on the hard floor because D2/D3 were not resolved. But a principal might disagree — the amended interface is arguably more useful than a rejection. The rubric should clarify whether amendment counts as resolution.
- **Prompt mismatch for test_author/implementer.** I identified that these roles have no `cannot_proceed` channel, so they can't formally refuse flawed specs. I documented this but didn't fix the production prompts. Fixing it would require adding JSON escape hatches to `test_author.md` and `implementer.md`, which is a real change with unknown side effects.

**What was awkward:**
- Running the evaluation was manual and slow. Each model×role invocation took 20–600s. The script I wrote (`scripts/capability_probe_eval.py`) is a one-off; it's not integrated into the runner or `make golden-run`. If the principal wants to re-run this monthly, it'll need babysitting.
- `ollama-cloud/kimi-k2.6:cloud` doesn't exist. The user requested it; I used `ollama-cloud/kimi-k2.6` instead. This is a small thing but it shows the model ID landscape is volatile.

## On what remains

1. **Evaluate Claude on the probe.** The spec assumes Claude is the best interface_architect. This is untested by the probe. Running Claude (CC headless) through the same 5 roles would either validate or challenge the current default bindings.
2. **Fix or replace Gemini CLI.** The Node.js regex error blocks all Gemini evaluation. This is a harness issue, not a model issue, but it means Gemini is unavailable for any role.
3. **Integrate findings into `FactoryConfig` defaults.** The report recommends binding changes (DeepSeek for test_author, GLM-5.1 Ollama for implementer). These are in the report but not in the config YAMLs yet.
4. **Decide on "amend" scoring.** If a model amends a flawed spec instead of rejecting it, does that count as Pass, Partial, or Fail? The current rubric says "Must resolve or reject" — amendment is a form of resolution. But the amendment may introduce new ambiguities. This needs a principal decision.
5. **Expand the probe (optional).** D6 (security flaw) or D7 (concurrency bug) would increase discrimination power, especially for frontier_judge selection.

## Gaps to flag

- **Self-scoring without validator:** `.factory/analysis/2026-05-14-model-capability-evaluation.md` §6 is scored by K2.6. No independent scorer reviewed the outputs. High risk of scorer bias on borderline cases (e.g., GLM-5.1's Partial vs Fail on D2).
- **No automated probe runner:** `scripts/capability_probe_eval.py` is a standalone script, not a pytest test or CI gate. If models change behavior, the probe won't catch drift automatically.
- **Qwen timeouts not investigated at longer durations:** `.factory/analysis/2026-05-14-model-capability-evaluation.md` §8.4 notes Qwen timed out at 600s. I did not test at 900s or 1200s. If it completes at 900s, the "operationally unfit" verdict may be too harsh.
- **DeepSeek implementer returned `None` from `-> bool`:** This is a mypy failure that the inner gate would catch in production. In the probe, I scored it as Partial (not Fail) because the model correctly used `clock.monotonic_ns`. But in production, this would trigger an inner gate retry, wasting budget.
- **GLM-5.1 z.ai vs Ollama provider difference:** Same model weights, different timeout behavior on implementer. This validates BC-135's lesson (provider reliability is a separate axis from model capability) but also means the probe should be run against both providers for any model that has multiple.
- **Gemini CLI still broken:** `breadcrumbs/108` documents this. No progress. The CLI crashes with `SyntaxError: Invalid regular expression flags` on current Node.js.
- **Missing fixture files in git:** `tests/fixtures/capability-probe/reference_flawed_*.py` are new. If not committed, future agents won't have the canonical upstream artifacts.
