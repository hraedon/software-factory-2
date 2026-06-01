---
number: "224"
title: "Jury/review accept stub, non-HTTP code as satisfying HTTP/persistence ACs — quorum buries the one juror that catches it"
severity: high
status: in_progress
kind: bug
author: claude-opus (review session)
date: "2026-05-29"
tags: [jury, review, stage-5, web-service, test-efficacy, phase-6]
related: ["209", "222", "227", "RFC-027"]
---

## Symptom

On the url-shortener web-service workload (GR-047, then GR-048 with artifacts preserved), the pipeline produced **stub-quality, non-HTTP code** for a spec that explicitly decided FastAPI + SQLite, and most gates passed it:

- No HTTP server anywhere in the run (FastAPI/Flask/http.server/WSGI = 0 files across all artifacts).
- FR-04 `get_links` fabricates 25 in-memory links inside the function and slices them — no DB, despite AC-06 saying "Given 25 links **in the database**".
- FR-05 `error_formatter` is a bare `validate_url(url) -> ErrorResponse | None` — no endpoint, no HTTP 422, despite AC-07 saying "the response is **HTTP 422**".

The mechanical inner gates (pytest/mypy/ruff) passed 100% first-attempt because the tests are self-consistent with the stubs (test theater — no test asserts an HTTP status code or DB integration). `cross_family_reviewer` (Sonnet) passed all modules. At the jury, **K2 correctly dissented** on FR-04 (DB) and FR-05 (HTTP 422); **Sonnet and MiMo both passed** them by grading against module-level behavior ("does the function return an ErrorResponse?") instead of the AC ("does a POST return HTTP 422?").

## Root cause (two coupled defects)

1. **Contract-altitude bug in the jury/review rubric.** Jurors judge a module bundle against module-level behavior and silently accept it as satisfying service-level ACs written in HTTP/DB terms. "This is a unit; the HTTP layer is someone else's job" is treated as a pass rather than an explicit, checked hand-off. Two of three jurors did this independently — it is a prompt/rubric problem, not a one-model fluke.

2. **Quorum masks a correct minority.** With a 3-member quorum-2 jury (GR-048), K2's correct spec-conformance dissent was simply out-voted (2-1) and the items locked. Majority rule is only safe when the majority is right about the contract; here it wasn't. The GR-047 2-member jury (quorum 2) had *correctly* blocked these same items — so moving to a 3-member panel made the jury stage strictly worse.

## Impact

High. This is the pipeline's core guarantee failing: it ships code that does not meet its acceptance criteria, and the review + jury gates rubber-stamp it. The failure is silent on CLI workloads (whose ACs happen to match function-level behavior) and only surfaced because a web-service spec writes ACs in HTTP/DB terms. `outcome_e2e` caught 2 of 3 known-bad modules downstream, but passed FR-05 — so it is not a reliable backstop.

## Proposed fix (directions, for principal decision)

1. **Raise judging altitude:** the jury/review prompt must judge each AC against behavior at the AC's stated altitude. An AC phrased "the response is HTTP 422" is not satisfied by a function returning an object; if the module under review legitimately cannot exercise HTTP, that must be recorded as an explicit deferred-to-integration claim and *verified* at integration/outcome, not passed.
2. **Conformance dissent is not out-votable by style.** Consider an asymmetric rule: a juror's *AC-conformance* objection (cites a specific AC the artifact fails) blocks unless explicitly refuted, even if out-numbered — distinct from style/preference votes that are subject to majority. (Counter-design to the current symmetric quorum.)
3. **Turn on RFC-027 (mutation/test-efficacy gate) and calibrate it on THIS workload** — the test theater here (suites that never assert HTTP status or DB integration) is exactly what mutation testing detects. url-shortener is a better calibration target than a clean CLI workload.
4. **Close the `outcome_e2e` error-path gap** that let FR-05 pass (see BC-222).

## Systemic fix

**RFC-038 (verification-driven conformance gate)** is the proposed systemic fix: make conformance *executed* against AC-derived acceptance tests in a hermetic container, rather than *judged* by an LLM jury. This makes the jury non-load-bearing for conformance (the better outcome than fixing its rubric by prompt — which v1 evidence, dep-v1-314, says won't converge). See RFC-038, which also incorporates the v1 lessons (dep-v1-106: mutation testing was insufficient; dep-v1-342: real runs are the only reliable integration test; dep-v1-364: the must-fail-against-stub invariant).

## Why this isn't the previous fix recurring

N/A — first instance of this defect shape (gate-rubric contract-altitude / quorum-masks-conformance-dissent). It is the upstream root cause that BC-222's symptom (outcome_e2e escalations) pointed back to.

## Progress (2026-05-30)

Implemented the substrate boot-AC invariant (per plan `plans/2026-05-30-substrate-boot-ac-invariant.md`). This addresses the GR-050 blocker where `link_store` (shared-infrastructure substrate) was emitted with `ac_ids: []`, causing `spec_lint` to fail and the DAG to stall at 80%. The fix:

1. Added `is_substrate: bool` to `DecomposedModule` and the decomposer JSON schema, with explicit validation (zero feature ACs + ≥2 dependents required).
2. System-owned `AC-BOOT-01` ("Walking-skeleton boot") is now injected into substrate module specs before `spec_lint`, discharged by the RFC-038 boot probe (not by jury/inspection).
3. The conformance gate routes AC-BOOT-01 to `test_ac_boot_01` (GET /healthz → 200).
4. Single-dependent substrates are inlined (Option 3 from the plan).

This does NOT resolve BC-224's root cause (jury altitude mismatch) — that requires RFC-038's full conformance gate. But it prevents the substrate-specific cannot_proceed stall and establishes the anti-vacuity guarantee for the boot AC.

## Progress (2026-06-01)

RFC-038 conformance gate implemented and validated end-to-end through GR-058 (ALL PASS). The gate (`src/factory/gate/conformance.py`) derives pytest tests from ACs, runs them against the assembled artifact in a hermetic subprocess, and deterministically rejects stubs (dep-v1-364 invariant). The jury is now non-load-bearing for conformance — the conformance gate is the authority. Remaining work: GR-055-scale confirmation run (BC-232). BC-224's root cause (jury altitude mismatch) is mitigated by making the jury advisory rather than authoritative for conformance; the rubric fix (directions 1-2 above) is lower priority now that the conformance gate exists.
