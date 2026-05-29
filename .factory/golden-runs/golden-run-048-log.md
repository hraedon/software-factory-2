# GR-048: url-shortener re-run, 3-member jury (K2 + Sonnet + MiMo) — adjudicating the GR-047 disagreement

**Date:** 2026-05-29
**Config:** `.factory/golden-runs/golden-run-048-config.yaml`
**Fixture:** Phase B decomposer output from `tests/fixtures/url-shortener/spec.yaml` via MiMo-V2.5-Pro
**Channels:** K2 (opencode) workers; Sonnet (claude-code) reviewer; jury = K2 + Sonnet + **MiMo**, quorum 2
**Executor:** Claude Opus (review session), manual decompose + manual launch
**XDG_DATA_HOME:** `/tmp/sf2-golden-048-xdg` (session isolation)
**Artifacts:** preserved at `/tmp/sf2-golden-048` (107 MB) — NOT cleaned, per the run's purpose
**Wall clock:** ~25 min (18:07–18:32 UTC)

## Purpose

GR-047 locked only 88% on the first web-service workload: 2 of 4 modules escalated to `cannot_proceed` on a K2/Sonnet **jury disagreement**, despite 100% inner-gate first-pass. The GR-047 log framed this as *"the multi-model jury working as designed… meaningful signal, not a failure"* and *"the code quality is excellent; the disagreements are purely architectural"* — **but never read the verdicts**, and the artifacts were deleted. GR-048 reproduces GR-047's K2+Sonnet pair, adds MiMo as a third independent voice (quorum 2), and **preserves artifacts** so the disagreement can be adjudicated against the spec.

## Headline result (and why the headline is misleading)

| Stage | Locked | cannot_proceed |
|---|---|---|
| interface_spec | 4 | 1 (stats_reader) |
| test_suite | 4 | 0 |
| implementation | 4 | 0 |
| review | 4 | 0 |
| jury | **4** | 0 |
| integration | 4 | 0 |
| outcome_verification | 2 | **2** |

The jury locked 4/4 — which, taken alone, reads as "MiMo broke the deadlock, the disagreement is resolved, web services generalize." **That reading is wrong.** Reading the per-juror rationales and checking them against the spec shows the jury stage got *worse*, and the only reason the run didn't ship more defective code is that the `outcome_e2e` gate caught some of it downstream.

## Jury adjudication — the core finding

Both GR-047-style disagreements reproduced, and in both the dissenter was **K2** (the worker-family model); Sonnet and MiMo both passed. With quorum 2, K2 was outvoted and the items **locked**.

| FR / module | K2 | Sonnet | MiMo | Jury result | K2's stated objection |
|---|---|---|---|---|---|
| FR-01 link_creator | pass | pass | pass | locked (3-0) | — |
| FR-02 link_resolver | pass | pass | pass | locked (3-0) | — |
| FR-04 link_lister | **FAIL** | pass | pass | locked (2-1) | "hardcodes 25 in-memory links rather than reading from the database (AC-06); tests don't verify DB integration" |
| FR-05 error_formatter | **FAIL** | pass | pass | locked (2-1) | "AC-07 requires HTTP 422; bundle only implements validate_url returning ErrorResponse — no HTTP endpoint or status code" |

**K2 was right on both, verified against ground truth:**

- **Spec (`url-shortener/spec.yaml`) is unambiguously an HTTP+SQLite service.** Decided constraints: *"FastAPI as the HTTP framework"*, *"SQLite with WAL mode"*. AC-07 verbatim: *"Given a POST to /links with {"url": 123}, the response is **HTTP 422** with error code 'invalid_url'"*. AC-06 verbatim: *"Given **25 links in the database**, GET /links returns 20…"*.
- **The code has no HTTP server anywhere.** `grep` across every artifact: FastAPI/Flask/http.server/WSGI = **0 files**. The "web service" has no HTTP surface.
- **FR-04 `get_links` fabricates data:** it builds `[Link(url=f"https://example.com/{i:02d}") for i in range(25)]` inside the function and slices it. No DB, no input. (`/tmp/sf2-golden-048/d93c476c-.../artifact.py`)
- **FR-05 `error_formatter` is a bare function:** `validate_url(url) -> ErrorResponse | None`. No endpoint, no 422. (`.../e5e74179-.../artifact.py`)
- (For contrast, FR-01 `link_creator` *does* use real `sqlite3` — so module quality is uneven; there is no shared HTTP/DB scaffolding because no integrator ever produced a FastAPI app to wire the modules into.)

**Conclusion on the disagreement:** GR-047's jury blocks were **well-founded, not architectural taste.** K2 caught genuine spec-conformance failures — stub code, no HTTP layer, fabricated persistence — that Sonnet did not. GR-047's "code quality is excellent / 100% inner-gate first-pass" was true only in the hollow sense that **stub code with self-consistent stub tests passes mechanical gates**. This is test theater. The GR-047 framing was an over-claim.

## What the 3-member jury actually did: it made the jury stage worse

Adding MiMo did **not** adjudicate the disagreement on its merits. MiMo shared Sonnet's lenient reading — grading each module against module-level behavior ("does `validate_url` return an ErrorResponse?") instead of the actual AC ("does a POST return HTTP 422?"). With quorum 2, the two lenient votes **outvoted K2's correct dissent** and locked 2 modules the GR-047 2-member jury had correctly blocked. **Majority-rule quorum buries a correct minority objection.** A panel is only a truth-oracle if the majority is right about the contract; here it wasn't.

This is a direct hit on the project's own watch-metric (rate of self-caught over-claims): the jury quorum *manufactured* false confidence, and the only thing that caught the over-claim was reading the rationales + checking the spec by hand — not any pass/lock number.

## The backstop held — partially

`outcome_e2e` (the end-to-end behavioral gate) was the one gate that judged against real behavior, and it caught defects the jury missed:

- **FR-01 link_creator → cannot_proceed**, despite a **unanimous 3-0 jury pass**. Even all three jurors were wrong; the behavioral gate was right.
- **FR-04 link_lister → cannot_proceed** — the same module K2 flagged and the jury overruled. The outer gate compensated for the jury's error.

But it is a leaky backstop:

- **FR-05 error_formatter → locked.** A module K2 correctly flagged for having no HTTP 422 endpoint passed review, jury (overruled), integration, **and** outcome_verification. A defective module shipped clean.

So `outcome_e2e` caught 2 of 3 known-bad modules. It is a stronger oracle than the jury, but not a reliable one.

## BC-222 reframed (outcome_e2e escalations)

Two `outcome_e2e` escalations (work items `9ca72c3d` = FR-04, `b5d2e952` = FR-01) → `cannot_proceed`. The BC-222 hypothesis was a server-lifecycle/subprocess-handling gap (uvicorn startup/teardown). **That hypothesis is likely wrong.** The escalations are the verifier *correctly failing* because there is no runnable HTTP service to exercise end-to-end — the workers never built one. BC-222 updated with this reframing: the gap is upstream (no HTTP service produced), not in the gate's subprocess management. The latent server-lifecycle concern is unproven and should not be assumed until a workload actually produces a server to verify.

## Telemetry integrity

- jury verdict artifacts: 4, all `attempt-0001` (no retries — every jury item resolved first attempt, because quorum was met immediately).
- stats_reader (FR-03) died at `interface_spec` → `cannot_proceed` (1 item), so only 4 modules reached the jury. **Root cause (investigated):** the interface_architect (K2) refused to proceed, citing a real underspecification — FR-03/AC-05 require returning "up to 10 recent hits" / "a hits array with up to 10 entries" but never define the *structure* of a single hit entry, so a precise type can't be written "without inventing fields" (`cannot_proceed.json`). The glossary *does* define a hit (timestamp, source IP, user-agent), so a more thorough architect could have resolved it by reference; flagging it is defensible but conservative.

### The epistemic calibration is inverted — the run's sharpest finding

Put FR-03 next to FR-01/04/05 and the pattern is stark:

- **FR-03 (small, arguably resolvable ambiguity):** worker is uncertain → correctly **halts** (the epistemic-honesty behavior RFC-030 wants).
- **FR-01/04/05 (wholly unmet HTTP+SQLite contract):** worker is confidently wrong → produces stubs, and review + 2/3 of the jury **pass** them.

The system halts on a minor gap it could resolve from the glossary, but ships code that doesn't implement the service at all. Uncertainty is firing on the wrong things. This is not a tuning nit — it says the gates' notion of "am I meeting the contract?" is anchored to surface readability (types are precise, tests are green) rather than to behavioral conformance against the AC. It is the same root cause as BC-224, seen from the interface stage.

## Lessons and next steps

1. **The pipeline does NOT generalize to web services as currently built.** It silently produces stub-quality, non-HTTP code; inner gates and the majority of the jury bless it; only `outcome_e2e` catches some of it. The "Phase 6.2 web-service archetype" should be considered **failing**, not "near pass."
2. **Reverse the GR-047 narrative in the record.** Its "jury working as designed / excellent code quality" reading was an over-claim produced by not reading the verdicts. (This run is the worked counter-example.)
3. **The jury rubric has a contract-altitude bug.** Jurors judge a module bundle against module-level behavior and accept it as satisfying service-level HTTP/persistence ACs. Sonnet and MiMo both did this. File a BC against the jury/review prompt: ACs written in HTTP/DB terms must be judged against HTTP/DB behavior, and "this is a unit, the HTTP layer is someone else's job" must be an explicit, checked hand-off — not a silent pass. (Filed as BC-224.)
4. **Quorum masks correct minorities.** A 3-member quorum-2 jury is *not* a safe way to "break ties" when the dissent may be the correct one. Consider: dissent on a spec-conformance objection should require explicit refutation, not just out-voting (an "any-juror-blocks-on-AC-conformance" rule, vs. majority on style). (Captured in BC-224.)
5. **This is the concrete motivating case for RFC-027 (mutation/test-efficacy gate), currently wired but disabled.** The failure mode is exactly test theater: green suites that never assert HTTP status or DB integration. Mutation testing on these suites would likely show low efficacy. Recommend the RFC-027 calibration run use this url-shortener workload, not a clean CLI one — it has real test theater to detect.
6. **`outcome_e2e` is the most trustworthy gate and the leakiest-but-best backstop.** Worth understanding why it passed FR-05 (no HTTP 422) — that is a gap in the e2e gate's AC coverage for error paths.

## Artifacts

- Workspace (preserved): `/tmp/sf2-golden-048`
- Logs: `/tmp/gr048-runner.log`, `/tmp/gr048-gate.log`, `/tmp/gr048-scheduler.log`, `/tmp/gr048-populate.log`
- Jury verdicts: `/tmp/sf2-golden-048/{0071513c,44c4aa4d,9221df6a,a36368d9}/attempt-0001/jury_verdict.json`
- Config: `.factory/golden-runs/golden-run-048-config.yaml`
