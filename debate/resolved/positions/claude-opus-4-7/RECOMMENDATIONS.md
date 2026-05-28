# Synthesis & Recommendations — Round 1 + R2 triage

**Author:** claude-opus-4-7
**Date:** 2026-05-09
**Inputs:** positions from claude-opus-4-7, gemini-cli, glm-5.1, deepseek-v4-pro on debates 001–010, plus deepseek's regista items 011–012 and gemini's six new R2 items.

This is a recommendation, not a decision. Final calls remain principal-led.

---

## 1. Consensus map

Three reviewer postures emerged consistently:

- **gemini-cli** is the *permissive maximalist* — agrees with most proposed builds, including the heavier ones (full `VenvManager`, stage checkpoints now). High-energy, high-variance.
- **glm-5.1** and **claude-opus-4-7** converged independently on a *minimum-viable, build-when-needed* posture. We agree on 9 of 10 items at the action level and largely on the framing.
- **deepseek-v4-pro** is the *test-first* voice — accepts most positions but insists each one come with a concrete failing test or measurement before any build. Often the most operationally rigorous of the four.

| # | Item | claude | gemini | glm | deepseek | **Recommended action** |
|---|---|---|---|---|---|---|
| 001 | Behavioral gate | spec stub | strong-agree (build) | spec + stub | **spec + 1 concrete failing test** | **Spec + stub + one failing Playwright test** (deepseek's framing) |
| 002 | Telemetry BC-068 | hard-block | blocker | hard-block | fix + replay test | **UNANIMOUS — hard-block Phase 3, fix this week** |
| 003 | Channel adapter dedup | conservative base | refactor before 3rd | **composition not inheritance** | refactor + equivalency test first | **Composition (glm) + equivalency test before extraction (deepseek)** |
| 004 | Pipeline checkpoints | defer | build MVP | defer | defer | **Defer 3-of-4** — regista state already is the checkpoint |
| 005 | Mutation testing | Phase 3→4 | shadow mode | **assertion gate first, mutation later** | calibration fixture first, 5 ops | **Two-stage: ship glm's assertion gate now; mutation Phase 3→4 with deepseek's calibration fixture** |
| 006 | Per-project venv | 50-line shim | strong-agree (full class) | 50-line helper | narrow + test | **3-of-4 → 50-line helper, no `VenvManager` class** |
| 007 | Credential mgmt | schema only | blocker (full schema) | schema only | schema + test | **UNANIMOUS schema; 3-of-4 reject rotation/audit machinery** |
| 008 | Cert-watch GR006a | accept (3-outcome table) | agree | accept (3-outcome table) | **accept + machine-enforced criteria in `tests/test_gr006a_criteria.py`** | **Accept + deepseek's test-as-criteria** |
| 009 | Event schema | consumer pilot | agree (consumer pilot) | consumer pilot | consumer + test | **UNANIMOUS — consumer-level pilot, defer regista registry** |
| 010 | Event log retention | instrument | agree (instrument now, build later) | instrument + thresholds | defer (insufficient data) | **UNANIMOUS — defer build, ship metrics + auto-breadcrumb thresholds** |

**Strong consensus (4-of-4 or 3-of-4 with the 4th not strongly opposed): 002, 004, 006, 007, 008, 009, 010.**

**Productive disagreement (the synthesis is better than any single view): 001, 003, 005.**

---

## 2. Items where the four-way review changed my position

### 003 — adapter dedup: switch from "conservative base class" to **composition**

GLM made the cleanest argument I missed: a `SubprocessChannel` base locks subprocess in as the abstraction. K2 is HTTP, not subprocess. If the base doesn't fit K2, then it isn't the common abstraction — it's an adapter for 2-of-6 channels masquerading as one.

Composition (`_subprocess.py` + `_artifacts.py` as utility modules; each adapter imports what it needs) avoids the inheritance trap entirely. K2 imports `extract_artifacts_from_output` and skips subprocess helpers. No template methods, no risk of base-class accretion.

Stack deepseek's "write an equivalency test for both adapters before extracting" on top of that. The equivalency test defines what "common" actually means.

**Updated recommendation:** Composition over inheritance. Write `test_channel_contract_consistency` first; let it define the shared API; then extract utility functions; then refactor both adapters to compose them. K2 starts independent; second refactor when it teaches you what else is shared.

### 005 — mutation testing: insert **assertion-counting gate** as Phase-3 cheap step

GLM's "assertion-counting gate first" is the cheap intermediate I should have proposed. Counting `Assert` AST nodes per test file catches the most common test-theater pattern (tests that run but never assert) at near-zero cost, ~20 lines, no calibration needed. BC-038 already has the collect-only check; this is a 1-hour extension.

Mutation testing remains Phase 3→4, but the assertion gate is independent value that ships now.

Deepseek's calibration-fixture-first approach for mutation testing is the correct sequencing: collect 10–15 GR004/005 (impl, test_suite) pairs, run candidate operators against them, *then* pick the operator set and threshold from data. Do not start with my recommended operator list, start with data.

**Updated recommendation:** Ship assertion-counting gate now (Phase 3 prep). Build mutation gate Phase 3→4 starting with calibration fixture (deepseek's design), 5 operators not 10 (deepseek), threshold from p25 of fixture runs.

### 001 — behavioral gate: deepseek's "one failing test" beats my "spec only"

Deepseek's critique lands: a spec section with no failing test is indistinguishable from a wish. Writing one Playwright scenario against a deliberately broken FastAPI fixture, letting it fail today, and committing the test gives Phase 5 something concrete to make pass.

Cost cap: 1 hour. If the test takes longer, scope is wrong.

GLM and I argued for stub-only; we were both leaving accountability on the table.

**Updated recommendation:** Spec subsection (1 hr) + behavioral_gate.py stub (1 hr) + one concrete failing Playwright test against a broken-on-purpose FastAPI fixture (1 hr). Total ~3 hours. The test serves as a phase-progress signal: when it passes, the gate exists.

---

## 3. Items where my position holds

### 002 (telemetry hard-block), 007 (credentials schema only), 008 (GR006a + GR006b split), 009 (consumer pilot), 010 (instrument-only)

Four-way agreement at the action level. Differences are framing-level. No change.

For 008, **deepseek's `tests/test_gr006a_criteria.py` is a clear improvement** — encode the threshold as an asserted test rather than a markdown table, so the principal can't accidentally proceed to Phase 3 with sub-threshold data. I'll fold this into the GR006a plan.

### 004 (defer checkpoints) and 006 (50-line venv helper)

3-of-4 consensus to defer/narrow. Gemini's maximalist position on both is internally consistent but builds infrastructure ahead of demonstrated need. Hold.

---

## 4. Sequencing recommendation

This week → end of Phase 2:

1. **Day 1:** Ship BC-068 fix + consumer-level event_schemas.py (Debate 002 + 009 land together — they're the same fix at different layers).
2. **Day 1:** Ship 50-line per-project venv helper (Debate 006). Required for cert-watch.
3. **Day 2:** Author cert-watch FR-02 + FR-03 + Certificate model fixtures. Author `tests/test_gr006a_criteria.py` with the three threshold assertions (deepseek's design).
4. **Day 2:** Spec subsection + stub + one failing Playwright test (Debate 001 — 3 hours).
5. **Day 2:** Ship assertion-counting gate (Debate 005 part 1 — 1 hour).
6. **Day 3:** Run GR006a. Apply threshold. Decide Phase 2 close.

Pre-Phase 3 (after GR006a):

7. Channel composition refactor + equivalency test (Debate 003).
8. credentials.yaml schema + structlog redaction (Debate 007).
9. Telemetry retention metrics + thresholds (Debate 010).

Phase 3 → Phase 4:

10. Calibration fixture + mutation operators + threshold from data (Debate 005 part 2).

Deferred-with-trigger:

11. Pipeline checkpoints (Debate 004) — when a single GR exceeds 2h or a real mid-run crash loses meaningful work.
12. Regista-side schema registry (Debate 009 part 2) — when a second regista consumer exists.
13. Event-log retention build (Debate 010 part 2) — when auto-breadcrumb threshold fires.

---

## 5. R2 items (gemini's new round) — quick triage

| # | Item | Position | Urgency | Recommended action |
|---|---|---|---|---|
| R2-001 | Infinite-spend circuit breaker | **Strong accept** | High (Phase 3) | Build before Phase 3 multi-channel runs. v1 had this; the cost of *not* having it is unbounded. ~50 lines: `max_mission_budget` + `max_work_item_retries` in FactoryConfig + scheduler check. Skip the cost-modeling rabbit hole; use a coarse `cost_estimate = tokens × $/token_per_provider` table. |
| R2-002 | Bidirectional spec mutability | **Defer to Phase 5+** | Low now | Real concern but premature. Today the spec is principal-authored, not Socratic-authored, so "spec is impossible" is principal's call to amend. Once Phase 5+ Socratic specs exist, revisit. Add to spec.md §11 (out of scope for Phase 2-4). |
| R2-003 | Database migration strategy | **Strong accept; gate Phase 5 cert-watch on it** | Medium (pre-Phase 5) | Cert-watch needs SQLite + repository pattern; migration story is load-bearing for GR006b. Use Alembic + a dedicated migration gate (not free-form LLM SQL). This is a *hard* problem for LLMs and a known v1 failure mode. Build before GR006b. |
| R2-004 | Security & supply-chain gates | **Accept; bundle with venv work (Debate 006)** | Medium (pre-Phase 5) | `bandit` + `pip-audit` are cheap mechanical gates. Add as part of `evaluate_implementation()` once per-project venv exists. `trufflehog`/`semgrep` later — start with the two with lowest false-positive rates. Failures route back to implementer with explicit diagnostics. |
| R2-005 | Operator UX & async interrupts | **Accept minimally; defer dashboard** | Medium (Phase 4) | Luke's "Mission Control" point hits here. But sf2 needs the *minimum* — a webhook/Slack event sink for `cannot_proceed` and budget-exhausted events. ~30 lines: a `notification_hook` in scheduler + one webhook adapter. Full dashboard is post-Phase-5. Pair with R2-001. |
| R2-006 | Dead code / refactoring lifecycle | **Accept; trivial extension of existing audit** | Low | sf2 already has `make audit` (vulture, BC-057). Extend: run audit at end of every GR; if dead-code count > N, file an auto-breadcrumb. The "consolidation agent" idea is heavier than needed; the audit is the value. |

**R2 act-now set:** R2-001 (budget breaker), R2-005-minimal (notification hook).

**R2 pre-Phase-5 set:** R2-003 (migrations), R2-004 (security gates).

**R2 defer:** R2-002, R2-006-extension-only.

R2-001 + R2-005 are both ~50-line additions. They should land together before Phase 3, because the budget breaker without notification is silent failure and the notification without a budget breaker has nothing important to alert on.

---

## 6. Regista items (deepseek 011 + 012)

I haven't read the regista debates directly; deferring detailed positions to a regista-context review. Based on deepseek's framing:

- **sub-001 (backend contract SSOT):** Deepseek's "measure before prescribing" approach is correct. Add `hypothesis`-based property tests for 1 month, then decide based on divergence rate. Don't build a 3rd source of truth on speculation.
- **sub-002 (workflow composition):** Deepseek's "lint at threshold, build composition when threshold breaks" matches the same pattern as my Debate 010 position (instrument first, build when threshold fires).

Both align with the broader "don't build infrastructure before demonstrated need" pattern that 3-of-4 reviewers converged on.

---

## 6a. Addendum — items 011, 012, NEW-001/002/003 (post-feedback round)

GLM and Deepseek added five items in lieu of weighing in on R2. Net effect: the Day-1 sequencing changes; the rest of the plan holds.

**011 (glm) and NEW-001 (deepseek) are the same item — prompt versioning.** Independent convergence from different framings; strongest possible "build it" signal. Use glm's content-hash rationale + deepseek's git-hash-with-fallback implementation + deepseek's CI presence test. Critical piece: the "hashes differ within comparison group → emit warning" check, without which Phase 3 placement silently confounds prompt vs channel.

**012 (glm) — attempt-level latency.** Finishes a half-built spec §7 feature ("mean wall-clock," "gate-failure breakdown" columns were named, never built). Per-channel timeout argument is a real Phase 3 risk (Kimi 68% slower than Sonnet → one timeout is wrong for both). Use `time.monotonic()` for duration. ~30 lines.

**NEW-002 (deepseek) — BC-060 dead `inputs_dir`.** Accept Option A (remove). Make it the first commit of the Debate 003 channel-dedup work so the equivalency test asserts the real contract, not one with a dead param. Keep the `test_channel_protocol_has_no_dead_parameters` introspection test as regression guard.

**NEW-003 (deepseek) — `make golden-run` automation.** Accept timing: defer until after GR006a, ship before Phase 3 channel re-runs. Chains naturally with the `telemetry --verify` gate from Debate 002 — the Makefile enforces the runbook including the verify step.

### Sequencing change

Day 1 in §4 was "BC-068 + consumer event_schemas." It should now be **one bundled telemetry refactor** covering BC-068 + event_schemas (009) + prompt_template_hash (011/NEW-001) + latency (012). All four touch the same `ActorMetadata` / `GateAttempt` / `compute_pass_rates` / `format_pass_rate_table` surface. Splitting is four merges, four test runs, four schema-coordination chances; bundling is ~1.5 days and produces an internally consistent telemetry contract.

Pre-Phase 3 ordering also gains two anchors:
- **NEW-002 first** (remove `inputs_dir` from protocol)
- then Debate 003 (composition + equivalency test)
- then 007, R2-001, R2-005
- **NEW-003 last** (codifies the runbook only after runbook is settled)

### Process note

011 and NEW-001 surfacing the same problem from different angles is the highest-confidence build signal the multi-reviewer loop has produced so far — higher than any individual position. Worth flagging in the next round's instructions: "if you converge with another reviewer's framing, say so explicitly" so the convergence is visible at submission time rather than synthesis time.

---

## 7. What this round revealed about our review process

Worth noting before the next round:

1. **Independent convergence is a strong signal.** GLM and I never coordinated and landed on near-identical positions on 9 of 10 items. That's evidence the underlying analysis is sound, not that we're in echo chamber (we used different reasoning paths).
2. **Deepseek's test-first lens caught real gaps.** On 001, 003, 005, and 008, deepseek's "where's the failing test that proves the gap?" question produced concretely better designs. Worth keeping that voice in future rounds.
3. **Gemini's permissive posture is high-variance — valuable for surfacing items (R2 round) but less reliable for build/defer calls.** Treat gemini's "strong-agree" as "this is real, decide carefully" rather than "ship it."
4. **The R2 items gemini surfaced are valuable catch-ups.** R2-001 (budget), R2-003 (migrations), R2-004 (security) are all genuine v1 lessons that none of the other reviewers (or I) raised. The R2 round was net-positive even where individual gemini positions were maximalist.
