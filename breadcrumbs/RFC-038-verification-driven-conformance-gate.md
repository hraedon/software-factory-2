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

## Cost and risk (honest)

- Real infrastructure: image build/caching, compose for backing services, container lifecycle, per-archetype acceptance drivers (web service vs CLI vs library exercise differently). This is a build, not a flag.
- **Primary risk is non-completion** (dep-v1-314 died `in_progress`). Mitigation: ship the smallest thing that would have caught GR-048 first — the boot probe + a deterministic translation of url-shortener's already-executable ACs, host-execution fallback acceptable — and measure before building the general translator or per-archetype drivers.
- Strategic upside: a sealed, reproducible verification container is the same hermetic-provenance primitive regista is built around. Verification-driven development and cryptographic agent-audit are one mechanism seen twice.

## MVP (deliberately smaller than v1's P1+P2)

1. Boot probe in a container for the web-service archetype: assemble the modules, start the service, assert it accepts one request. This alone fails GR-048's three bad modules.
2. Deterministic translation of url-shortener's AC scenarios (they are already black-box HTTP) into an executable acceptance suite; the dep-v1-364 "must-fail-against-stub" guard as a blocking pre-check.
3. Wire results as the conformance authority for this one workload; leave the jury in place for non-conformance judgment.
4. Re-run url-shortener (GR-049) and confirm the bad modules are caught at this gate, not leaked.

Decide on generalization (other archetypes, the general AC translator, deprecating the jury-as-conformance) only after the MVP catches the observed failure in a real run. Ship the minimum that closes the observed bug, then re-decide — the same discipline v1's BC-314 stated and then failed to honor.

## Open questions

- Who owns the AC→suite translation — a deterministic module, or a tightly-constrained non-worker model? (dep-v1-364 warns against the worker family doing it.)
- Does the acceptance suite live at interface time (verification-first) or as a final gate (less invasive)? v1's bringup doc argues for earlier; sf2's stage topology currently favors a gate.
- Relationship to `integration` and `outcome_verification` stages: does this replace `outcome_e2e`, or harden it? (GR-048 shows `outcome_e2e` is the right *concept*, executed by the wrong *oracle* — LLM rather than AC-execution.)
