---
number: "adv-001"
title: "Adversarial review: Phase 3 readiness is lower than metrics suggest"
author: adversarial-reviewer
status: open
date: "2026-05-12"
tags: [readiness, metrics, fleet, first-attempt, operational]
related: [BC-120, BC-126, BC-127, BC-108, RFC-007, RFC-008, RFC-010]
---

## Position

The Software Factory v2 project is **operationally unready for its stated mission** despite excellent code hygiene. The gap between "tests pass" and "produces reliable software" is real, unmeasured, and currently masked by three layers of telemetry theater: retry-budget recovery, hand-curated fixtures, and channel-adapter scaffolding for unvalidated models.

This is not a call to halt. It is a call to **stop trusting the metrics that are being reported as success signals** and replace them with operational readiness criteria that survive adversarial scrutiny.

## Seven critiques with evidence

### 1. Retry-budget recovery is not a success signal

**Evidence:**
- GR-015: 100% lock rate, **0% first-attempt pass rate** (24/24 required inner-gate retry)
- GR-019: 94% lock rate, **64% first-attempt pass rate** (7/11 on clean signal)

The project reports lock rate as the headline metric. A 100% lock rate with 0% first-attempt pass means the system succeeds by brute force — burning model budget, wall-clock time, and context-window capacity on repeated attempts. This contradicts §3.11 ("subscription-flat-rate cost model rewards aggressive gating") and §3.2 ("sequential by default"). If every work item needs 2–3 attempts, the effective pipeline is 2–3x slower and no cheaper.

**Remediation:**
Adopt a **three-layer metric framework** rather than a single headline number. First-attempt pass rate is a legitimate signal — the 0%→64% jump between GR-015 and GR-019 was real evidence that BC-122 (prompt pre-flight) improved contract quality — but it must not be the only metric, nor set at an unrealistic threshold.

| Layer | Metric | Target | Role |
|---|---|---|---|
| **Contract / prompt quality** | First-attempt mechanical-gate pass rate | ≥60–70% on cert-watch full DAG | **Leading indicator.** Measures whether prompts and specs are clean enough that the implementer can self-check before returning. |
| **Operational success** | Lock-within-budget rate | ≥90% | Did the system actually deliver? |
| **Efficiency / brute-force detector** | Mean attempts to lock | ≤2.0 | Catches "lock by burning retries." GR-015’s 100% lock rate with 24/24 items requiring retry is within budget but at the edge; ≥2.5 would signal brute-force recovery. |

**Rationale for the 60–70% target:** Factory’s production data (see §7 below) shows that adversarial validation — a separate agent with fresh context — "never succeeds on the first go." But that quote applies to the **jury / cross-family review layer** (Phase 4 in SF2), not the mechanical gate layer. SF2’s inner gate (ruff → mypy → pytest collect) measures whether the implementer can produce type-checking, lint-passing code on its own. That is a reasonable expectation for a slot-filling role, and 60–70% is achievable without weakening gates. When SF2 adds jury gates in Phase 4, first-attempt pass rate at the *jury* layer should be expected to drop sharply — that is when Factory’s wisdom applies.

**Telemetry changes:**
- Report all three metrics on every golden-run summary.
- Label first-attempt rate as "leading indicator (contract quality)," not as the headline.
- Expose `mean_attempts_to_lock` prominently so brute-force recovery is visible.

### 2. Three of five configurable channels are unviable or unvalidated

**Evidence:**

| Channel | Golden-run validation | Outcome |
|---|---|---|
| Claude CC headless | GR-001–GR-014 | Works |
| OpenCode (K2/Fireworks) | GR-014–GR-019 | Works |
| GLM-5.1 | GR-017 | Catastrophic: empty output, stuck at attempt 16 |
| DeepSeek V4 | GR-018 | ~50% implementer pass; type errors remain |
| Gemini CLI | None | 29-line adapter, zero golden-run evidence |

The spec §5 table presents a fleet of six channels with role bindings. The reality is two working channels and three liabilities that will silently fail if a config ever selects them. BC-108 admits Gemini is "essentially untested."

**Remediation:**
- Run a single-work-item smoke test for GeminiCLIChannel. If it fails or flakes, make `GeminiCLIChannel.invoke()` raise `NotImplementedError` with a clear message until validated.
- Do the same for GLM if GR-017 is reproducible.
- Remove unvalidated channels from the default config and from `_create_channel` factory mapping until they have ≥1 passing golden-run item.
- Update the spec §5 table with a "Validated" column that is mandatory for any entry.

### 3. Breadcrumb status drift undermines process integrity

**Evidence:**
- `breadcrumbs/README.md` lists BC-126 and BC-127 as `status: implemented`
- The canonical breadcrumb files (`126-work-item-granularity-correlation.md`, `127-spec-linting-upstream.md`) list `status: proposed`
- The code exists (`spec_lint.py`, `work_item_size_metrics.py`) but the breadcrumb files — the single-source-of-truth for status — disagree with the index

If the project's own quality-tracking system has inconsistencies in its five active items, the system is already experiencing the "string constant gravity" pattern it was designed to prevent.

**Remediation:**
- Audit every open breadcrumb file against the README index in the same session.
- Adopt a rule: the breadcrumb file is the canonical source; the README is derived. The README generator should read the files, not maintain a separate table.
- If a breadcrumb is implemented but the file says proposed, either update the file or revert the code and reopen the breadcrumb.

### 4. The "550 tests, 0 lint" shield masks structural test gaps

**Evidence:**
- Integration tests share a module-scoped `real_sub` fixture (noted in Session 26 reflection as a fragility).
- No test covers a multi-channel race condition (Phase 4 doesn't exist yet).
- No test covers model behavior under genuine spec ambiguity (all fixtures are principal-authored with clean ACs).
- No behavioral gate is active — the `behavioral_gate.py` stub raises `NotImplementedError` when scenarios are present.

The test suite validates internal consistency. It does not validate whether the system can produce working software from a specification written by a non-technical stakeholder who thinks "robust" is measurable.

**Remediation:**
- Add a `test_behavioral_gate_phase5.py` skip-marked test (already exists — good). Ensure the skip marker is evaluated at every plan review, not ignored.
- Add an adversarial fixture: one work-item with intentionally ambiguous ACs. The expected outcome is escalation to `cannot_proceed`, not lock. Test that the pipeline escalates rather than hallucinates.
- Add a fixture with a deliberately broken interface spec (missing parameter). Test that the implementer either produces a `cannot_proceed` amendment request or fails the gate deterministically — not that it produces working code from a broken contract.

### 5. Load-bearing principles are deferred to phases that may never arrive

**Evidence:**

| Principle | Spec Section | Status |
|---|---|---|
| Jury-and-race for load-bearing gates | §3.9 | **Zero jury gates exist** |
| Test efficacy over theater | §3.4, §8.9 | Assertion-count gate only; RFC-007 deferred |
| Mechanical gates over LLM gates | §3.5 | True for syntax, false for semantics |
| Implementer reports broken contracts | §3.8 | BC-120 is still `proposed` |

The implementer is the cheapest party to detect a broken contract and the most expensive to silence. Currently, the implementer has two bad options: contort the code or die in `cannot_proceed`. BC-120 proposes a structured amendment request artifact, but it remains proposed despite being the only remaining high-severity open item.

**Remediation:**
- **Decision required:** Either implement BC-120 now (Phase 3) with manual principal review, or document in AGENTS.md that Phase 3 assumes interface specs are perfect on first draft and that any broken contract is a principal-level escalation.
- If the decision is "defer to Phase 4," add a telemetry metric: `interface_amendment_requests` (currently always 0). When it becomes nonzero, that is the signal to implement BC-120.

### 6. Operational risks are deferred without accountability triggers

**Evidence:**

| Risk | Tracking | Status |
|---|---|---|
| Credentials in gate subprocess | RFC-012 | Deferred to Phase 5+; no stripping today |
| Pipeline checkpoint/resume | RFC-008 | Deferred; 30–50 min runs lose all progress on crash |
| Interactive debugging inner loop | RFC-009 | Deferred; evidence threshold is 3+ GRs with pytest-in-inner-loop still failing |
| Per-project venv isolation | RFC-006 | Deferred; current gate uses shared `.venv-gate` |

The reflection from Session 26 notes: *"Substrate `__init__` indentation bug — I fixed it in this session but it's in the substrate repo, not the factory repo. If the substrate gets a revert... this will break `build_failure_corpus.py` again silently."* This is a dependency-management failure mode that is not tracked in any breadcrumb.

**Remediation:**
- For each deferred RFC, add an **evidence threshold** that triggers re-evaluation. Example: RFC-009 triggers when `pytest-in-inner-loop` failures exceed 20% of total gate failures across 3 consecutive GRs.
- Add a breadcrumb: "Substrate direct-connection constructor drift" — track the risk that substrate changes break factory tools.

### 7. The cert-watch fixture is not representative of the target domain

**Evidence:**
- All golden runs use hand-curated, self-contained, pure-Python fixtures.
- The principal authored every AC with clean boundaries.
- The true target domain is "line-of-business tooling produced by non-technical stakeholders asking ChatGPT in isolation" (spec §1).

A system that passes on cert-watch is not proven to work on a vague one-page spec from a product manager. The first real workload (Phase 5) is where the factory meets its actual mission.

**Remediation:**
- Add a "messy spec" fixture to the test suite: a deliberately under-specified work item with ambiguous verbs, mixed interface/implementation claims, and missing dependency declarations.
- The expected behavior is not "lock it anyway." The expected behavior is "escalate fast with structured ambiguity diagnostics."
- Make this fixture part of the Phase 3 exit criteria: the pipeline must escalate it within 2 attempts, not hallucinate a solution.

## Suggested resolution paths

This debate can resolve in three ways:

1. **Accept the critiques** → open specific, numbered remediations as plan windows (see companion plan `plans/phase3-exit-and-readiness-prep.md`).
2. **Partially accept** → demote some critiques to low-priority breadcrumbs, keep others as plan items.
3. **Reject** → document the rejection rationale in `debate/resolved/` and update AGENTS.md to explain why the current metrics are considered sufficient for Phase 3 exit.

## References

- spec.md §1 (Purpose), §3 (Principles), §5 (Fleet), §8 (Known risks)
- AGENTS.md (Status, Phase 3 exit criteria TBD)
- Session 26 reflection (substrate `__init__` bug, integration test fragility)
- Golden run logs: GR-015, GR-017, GR-018, GR-019
