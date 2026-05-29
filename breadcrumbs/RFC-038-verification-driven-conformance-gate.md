---
number: "RFC-038"
title: "Verification-driven conformance gate — execute the assembled artifact against AC-derived acceptance tests in a hermetic container"
severity: high
status: proposed
kind: design
author: claude-opus (review session)
date: "2026-05-29"
tags: [gates, jury, outcome-verification, docker, test-efficacy, web-service, v1-lesson, dep-v1-106, dep-v1-314, dep-v1-342, dep-v1-364, phase-6]
related: ["224", "222", "209", "RFC-027", "RFC-030", "RFC-031"]
---

## Motivation

GR-048 established (by reading the jury verdicts against ground truth) that on the url-shortener web-service workload the pipeline shipped stub-quality, non-HTTP code: no HTTP server anywhere despite the spec deciding FastAPI; FR-04 fabricated 25 in-memory links instead of reading SQLite; FR-05 was a bare `validate_url()` with no HTTP 422. Every mechanical inner gate passed (the stub tests are self-consistent with the stubs), `cross_family_reviewer` passed, and 2 of 3 jurors passed. Only `outcome_e2e` caught some of it — and it leaked FR-05.

The root cause (BC-224) is that **conformance is judged by LLM opinion** — review and jury read artifacts and decide whether they "meet the AC," and they share the worker's misreading of what an HTTP/persistence AC requires. GR-048 also proved that adding more LLM jurors makes this *worse*: a quorum out-votes the one juror that catches the gap.

The fix is to make conformance **executed, not judged**: run the assembled artifact against acceptance tests derived from the ACs, as real behavior, in an environment that matches the declared stack. This is "verification-driven development" — the AC-derived acceptance suite is the spine the pipeline serves, not an opinion layered on top.

## This is not a new idea — v1 already proved the thesis and the failure modes

Before designing, the lessons from `/projects/software-factory` (v1). The same disease appears there ~22 times across the breadcrumb corpus, fought incident-by-incident, never converged to one invariant (exactly the RFC-031 fix-family / RFC-030 promotion pathology, in v1 form). The load-bearing precedents:

1. **dep-v1-342 — "Real runs are the only reliable integration test."** v1 had *361 fast tests, all green*, yet the first real end-to-end run hit 4 distinct failure modes, *each in code fully covered by mocked tests*. This is GR-048's shape exactly (100% inner-gate pass, no working service). The empirical thesis of this RFC is v1's hard-won sentence: mocked/self-consistent tests do not establish conformance; execution does.

2. **dep-v1-106 — mutation testing was built (severity "very high", implemented) and did NOT stop test theater.** It was motivated by cert-watch-4 (247 tests pass, app broken), yet port-observer and cert-watch-11 still shipped broken code afterward. **Critical implication for sf2:** RFC-027 (our mutation gate) is necessary but *provably insufficient* for the GR-048 class. Mutation scores whether tests bite against *existing* code; it cannot detect that the code never implemented the contract — there is nothing meaningful to mutate in a stub. **Do not expect RFC-027 to catch url-shortener.** RFC-038 is the complement, not a duplicate, of RFC-027.

3. **dep-v1-314 — v1 designed almost exactly this gate (containerized validation environment) in full detail, and it died `in_progress`, never shipped.** Its design is sound and largely reusable: stack fingerprint → cached Docker image per fingerprint → generic boot probe → in-container test execution → in-container gates; Docker as a *soft* dependency with host-execution fallback; build cost amortized per fingerprint. **The lesson is the failure to land:** v1 scoped it as P1–P5, deferred P3–P5, and still didn't finish P1–P2. RFC-038 must therefore be *more* ruthless about MVP scope than v1 was, or it will be the next unfinished `in_progress`.

4. **dep-v1-364 — the "tests must fail against the stub" invariant.** v1's insight: run the test suite against the unimplemented skeleton; any test that *passes* is suspect, because a correct test must fail when the implementation is absent. v1 made this **warn-only** ("classifying test intent is fragile") — and it didn't hold. RFC-038 adopts the invariant but makes it **blocking**, tied to the AC.

5. **dep-v1-314's deeper framing:** "agents predict framework behavior from training data instead of observing it; accumulating framework rules in prompts does not converge." This is the argument against the prompt-only branch of BC-224's fix: better juror prompts won't converge either. Execution is the only thing that scales as workloads diversify.

## Proposal

A **verification-driven conformance gate** with four parts. The non-negotiable is part 1.

### 1. Deterministic AC → acceptance-suite translation (the make-or-break)

The acceptance tests must be derived from the spec's AC scenarios by a **deterministic/templated** path, NOT authored by the worker model family. This is the crux: GR-048 failed because the workers who misread "HTTP 422" as "return an ErrorResponse" would, if they also wrote the harness, assert the wrong thing (`validate_url(...) is not None` instead of `client.post(...).status_code == 422`). v1's dep-v1-364 is the same failure: the test architect wrote mocked tests that passed against stubs.

Enabler: socratic-specification already emits ACs as concrete black-box scenarios ("Given a POST to /links with {...}, the response is HTTP 422 with error code 'invalid_url'"). These are nearly executable. The translator's job is mechanical: scenario → HTTP call + assertion, seeded fixtures ("Given 25 links in the database" → seed 25 rows). Where an AC is not mechanically translatable, it is explicitly recorded as untestable (the spec already has an `untestable_items` section) — never silently passed.

**Guard (from dep-v1-364, made blocking):** the generated acceptance suite must FAIL against the unimplemented skeleton. A scenario test that passes before any implementation exists is rejected as not testing the contract.

### 2. Hermetic containerized execution (adapt dep-v1-314, do not reinvent)

Run the assembled artifact against the acceptance suite in a container pinned to the spec's declared stack (FastAPI + SQLite here), with declared backing services via compose. Reuse v1's design: fingerprint → cached image → boot probe (does the service start and accept a request at all — this alone kills the "no HTTP server" case) → run acceptance suite → teardown. Docker is a **soft dependency**: absent Docker, degrade to host execution with a logged "approximate" warning (v1's deliberate zero-infra-dependency posture). This is also where BC-222's server-lifecycle concern becomes real and gets solved once, centrally (start, health-probe-before-call, guaranteed process-group teardown).

### 3. The gate is the conformance authority; the jury is demoted

`outcome_e2e` is already the most trustworthy gate in the pipeline (GR-048: it caught defects a unanimous jury missed). Make the AC-execution gate the *authority* for conformance and stop treating the LLM jury as a conformance oracle. The jury/review remain useful for things execution cannot judge (design quality, security smell, readability) — but "does it meet the AC" is decided by execution. This directly resolves the BC-224 tension: rather than trying to fix the jury rubric's altitude (a prompt fight that won't converge per dep-v1-314), make the jury non-load-bearing for conformance.

Sequencing note (from v1's bringup design doc): verification-driven means the acceptance suite should exist *before* implementation, derived from ACs at decomposition/interface time, so implementers code against an executable target — not a final-stage afterthought.

### 4. Feed failures back as structured upstream revisions

An acceptance-suite failure routes to the responsible upstream work item with the concrete failing scenario (the `Route` / `create_upstream_revision` mechanism RFC-027 already uses), e.g. "AC-07: POST /links {url:123} returned <no server> ; expected 422".

## What this does NOT fix (honest scope)

- **FR-03-class halts** — interface-stage ambiguity (worker correctly refuses on underspecified hit-entry structure) is upstream of execution; untouched.
- **Missing ACs** — if the spec doesn't assert a property, execution can't catch its absence. This is a socratic-specification concern.
- **Semantic correctness beyond the ACs** — execution proves the stated scenarios, not unstated intent.
- **It is not RFC-027.** Mutation testing (RFC-027) scores test bite on real code; this gate proves the artifact meets the contract. Both are needed; neither subsumes the other (dep-v1-106 is the proof that mutation alone is insufficient).

## Cost and risk (honest) — and where the work actually is

The instinct to treat this as "Docker integration" misplaces the effort. The container is ~20% of this and it is the boring, solved part. **We do NOT need v1's apparatus** (BC-314's stack-fingerprinting, image cache, registry pinning, soft-dependency-with-host-fallback). The MVP is one ephemeral container per factory run: start → health-probe-until-ready → run the acceptance suite → tear down → discard. The only lifecycle that can't be skipped is those four steps (and they become trivial precisely *because* nothing is kept warm — this is the easy version of the concern BC-222 was circling).

The cost and risk live in the other 80%, in two places:

- **AC → acceptance-suite translation (the load-bearing risk).** Doing this faithfully is genuinely hard and hard *for everyone* — it is an open problem, not an sf2-specific gap. If the worker model family authors the harness, it reimports the GR-048 blind spot (asserts `validate_url(...) is not None` instead of `POST → 422`). Current best guess: deterministic templating off the AC scenarios, guarded by the dep-v1-364 must-fail-against-stub check. This guess may prove brittle; it is the part to stay tentative about.
- **Decomposition altitude (RFC-039).** Whether units can even *own* the behavior an AC asserts.
- **Watch-item:** if effort drifts toward polishing container plumbing, that is the tell that it is avoiding the hard part. **Primary failure mode is still non-completion** (dep-v1-314 died `in_progress`); keeping the container dumb and ephemeral is how we avoid re-living that.

Strategic upside: a sealed, reproducible verification container is the same hermetic-provenance primitive regista is built around. Verification-driven development and cryptographic agent-audit are one mechanism seen twice.

## AC translatability — first measurement (2026-05-29)

MiMo's review asked the right question: "how far does templating actually go — what fraction of real ACs are mechanically translatable vs. require judgment?" The untestable fraction *is* the gate's coverage ceiling. A first-pass classification across the three buildable fixtures:

| Fixture | `acceptance_criteria` | mechanically translatable | judgment-required | already quarantined (`untestable_items` / `nfr`) |
|---|---|---|---|---|
| url-shortener | 10 | 10 | 0 | 2 / 3 |
| log-redact-cli | 9 | 9 | 0 | 2 / 3 |
| dep-graph-viewer | 9 | 9 | 0 | 2 / 3 |
| **total** | **28** | **28 (~100%)** | **0** | **6 / 9** |

("Mechanically translatable" = concrete input → concrete observable: HTTP status/body, exception type + message substring, return-value shape, file/DOT output, counts, timing. Two are borderline-but-doable: DGV-07 needs DOT-attribute-aware assertions; DGV-08 needs the `graphviz` binary + a timing budget.)

**The finding reframes the risk.** The translatable fraction of the `acceptance_criteria` section is ~100% on this corpus — *because the spec format already pushes judgment-requiring items upstream into separate `untestable_items` and `nfr` sections* (each fixture quarantines ~2 untestable + 3 NFR: "visual aesthetics," "performance under concurrency," "human readability"). So the gate's coverage = the `acceptance_criteria` section, and the residual is out of scope *by spec construction*, not by gate failure.

This narrows the load-bearing risk from "AC translation is an open problem" to three bounded things:
1. **Faithful fixture seeding** — "Given 25 links in the database" must seed 25 real rows; this is the substantive translation work, not the assertion.
2. **Non-worker authorship** — the translator must not be the worker model family (else the GR-048 blind spot returns).
3. **Upstream discipline holding** — the ~100% depends on socratic-specification continuing to write concrete scenarios and quarantine the rest. If a real spec's `acceptance_criteria` carries fuzzy items, the number drops. **Caveat:** these are curated, buildable fixtures; treat 28/28 as "what the spec format affords when it works," not a universal constant.

Concrete next measurement: when a non-fixture / messier spec arrives, re-run this classification and watch whether the translatable fraction holds.

## MVP — and why it ships before RFC-039, not after

This gate is **the falsification instrument for RFC-039**, so it is built first and deliberately decoupled from the decomposition change. The sequencing is what makes the whole thing low-risk rather than a rearchitecting:

1. **Build the ephemeral execution gate** (one container per run; start → health-probe → run suite → discard). No v1 apparatus.
2. **Point it at the EXISTING (atomic-decomposed) url-shortener output first — GR-049.** Change nothing else. Expectation: the gate fails the GR-048 stub modules deterministically (no HTTP server → boot probe fails; no `POST→422` → AC scenario fails). This converts GR-048's hand-read finding into a mechanical, repeatable conformance signal **before** we touch the decomposer — confirming the diagnosis on its own.
3. **Then, separately, run deliverable-decomposed url-shortener through the same gate (RFC-039 validation).** If the diagnosis is right, those units can own and pass their ACs where the atomic ones could not. The gate is the same; the decomposition is the variable.
4. Wire the gate as the conformance authority for this one workload; leave the jury in place for non-conformance judgment (design/security/readability).

Deterministic translation of url-shortener's AC scenarios (already black-box HTTP) into the executable suite, guarded by the dep-v1-364 must-fail-against-stub check, is the load-bearing component (see Cost and risk). Decide on generalization (other archetypes, a general AC translator, demoting the jury-as-conformance) only after the MVP catches the observed failure in GR-049. Ship the minimum that closes the observed bug, then re-decide — the discipline v1's BC-314 stated and then failed to honor.

## Open questions

- Who owns the AC→suite translation — a deterministic module, or a tightly-constrained non-worker model? (dep-v1-364 warns against the worker family doing it.)
- Does the acceptance suite live at interface time (verification-first) or as a final gate (less invasive)? **Principal lean (2026-05-29): interface time** — the suite derived from ACs before implementation, so implementers code against an executable target. This is only *possible* once units are deliverable-altitude (RFC-039); with today's atomic units it cannot live at interface time (you can't HTTP-test a bare function). So the MVP starts as a gate (GR-049, existing output) and moves to interface-time as RFC-039 lands. v1's bringup doc argues for earlier and is the precedent.
- Relationship to `integration` and `outcome_verification` stages: does this replace `outcome_e2e`, or harden it? (GR-048 shows `outcome_e2e` is the right *concept*, executed by the wrong *oracle* — LLM rather than AC-execution.)
