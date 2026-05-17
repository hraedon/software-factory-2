# Phase 5 Exit + First Real Workload Prep — Implementation Plan

**Status:** active
**Author:** claude-opus-4-7
**Date:** 2026-05-17
**Origin:** GR-038 (first ALL-PASS full DAG) lands the structural Phase 5 work; this plan covers the remaining slate before the "first real workload" gate from spec §10 Phase 5.

## Where we are

GR-038 delivered the first `Overall: ALL PASS` full-DAG run on this branch
(K2 workers + Sonnet cross-family reviewer + K2/Sonnet jury, cert-watch
fixture). Four independent lineages locked end-to-end through all seven
stages, with N=4 on jury, integration, and outcome_verification — first
adequate coverage of the late-stage surface.

**What this confirms is done:**
- Stage 8 (integration) and Stage 9 (outcome verification) — implemented,
  exit-validated across N=4 lineages, zero `cannot_proceed` events at
  either stage.
- BC-145 review/jury verdict routing — validated under two reviewer-family
  pairs with very different rejection rates (94% gemini, 45% sonnet).
- BC-180/181/182/183/184/185/186 — all structural fixes from the
  GR-035/036/037 sequence are landed and validated.
- All four Phase-5-dependency RFCs (017 operational survivability, 019
  artifact bundling, 020 archetype catalog, 021 spec mutation policy) —
  marked `implemented`.

**What remains for Phase 5 exit** (per spec §10): the "first real workload."
Everything else in Phase 5's scope has shipped.

## Scope

This plan covers three windows leading up to attempting a real workload.
Windows are dependency-ordered: each unblocks the next.

- **Window A** — Operational polish and harness debt (~1–2 sessions).
- **Window B** — Real-workload selection and pre-flight (~1 session of
  design, then 1 execution run).
- **Window C** — GR-039 execution against a real workload, decision gate
  on Phase 5 exit.

Out of scope: Phase 6 generalization (RFC-023 decomposer, RFC-024 coherence
reviewer, RFC-027 test efficacy, RFC-022 initiative primitive). Those
remain governed by spec §10 and are deferred until at least one real
workload has run end-to-end.

## Window A — Operational polish

These items are individually small (each fits in a single session) but
accumulate into a noticeably more robust harness before we point it at
real spec material.

### A1 — Guardrail lifecycle RFC

**Motivation:** Three wrapper guardrails decayed past usefulness this
week and falsely killed otherwise-healthy runs (commits 1710792, 6913f19,
f1fc1ef). The pattern is consistent: a guardrail added when its target
event was rare and load-bearing becomes a false-positive once the
underlying state machine matures.

**Output:** A short RFC under `breadcrumbs/` that codifies (a) every
guardrail must declare its preconditions (which BCs/state-machine
invariants make the original failure mode possible), and (b) the audit
trigger — when any cited BC is closed or any invariant changes,
re-evaluate the guardrail.

**Estimated effort:** 1 hour. One person, one short writeup.

**Acceptance:** RFC filed, status `proposed`. Existing guardrails in
`scripts/agent_golden_run.py` tagged with their preconditions in
inline comments.

### A2 — Synthetic-seed fixture for late-stage iteration

**Motivation:** A full-DAG run takes 90–180 min. Iterating on jury or
integration or outcome_verification behavior at this cadence is too slow.
A fixture that pre-populates substrate with items already in `locked`
state at impl or review level would let us exercise stages 5–7 in minutes.

**Output:** Substrate seeding utility (probably a small new module under
`src/factory/`) + a fixture schema extension that accepts `seed_state:`
on work-item definitions. New `tests/fixtures/late-stage-seeded/` fixture
demonstrating the pattern with 3 pre-locked implementations seeded into
substrate so a run starts directly at the review stage.

**Estimated effort:** Half a session. Requires care around substrate
state invariants (which we should not be bypassing carelessly).

**Acceptance:** A "fast-DAG" golden run (GR-039 if it makes sense to
number it that way, or just a manual exercise) that completes in <20 min
exercising jury/integration/outcome on seeded data.

**Risk:** Substrate may not permit external state seeding. Investigate
before committing to the design; if blocked, the alternative is a
substrate API addition, which is heavier and would push this item to
Window B or later.

### A3 — Mean-attempts threshold review

**Motivation:** GR-038 ended with `mean_attempts: 2.00 PASS [target:
<=2.0]` — pinned exactly at the threshold. One more retry on one more
item flips it to FAIL. Either the threshold is set too tight given an
inner-gate retry budget of 3, or there's real signal in items needing
2 attempts that we should be acting on.

**Output:** Audit of the 41 locked items from GR-038 by attempt count.
If most distribution is at 1 attempt with a long tail to 3, raise the
threshold to 2.2 or 2.3 and write the rationale into the telemetry
module comment. If there's a structural reason items consistently need
2 attempts, file a BC on the underlying cause.

**Estimated effort:** 1 hour, low-risk.

### A4 — Optional: claude-code channel timeout calibration

**Motivation:** GR-038 had zero channel timeouts. GR-037 had one
(cc11078f at 600s on opencode/K2). The current per-role timeout is
uniform 600s. With Sonnet via claude-code we don't have enough data to
say whether that's right for that channel.

**Output:** Defer to GR-039 data. Don't act yet. Listed here so it's not
forgotten.

## Window B — Real-workload selection

The pivot from "validate the pipeline" to "use the pipeline." Two
sub-decisions:

### B1 — Pick a real workload candidate

**Output:** A spec document for a real (not synthetic) line-of-business
project, sized to be tractable but not trivial. Candidates worth
considering:
- A small internal tool already on the to-do list elsewhere.
- A documented utility that exists in software-factory v1's backlog (if
  any v1 BC pointed at v2 as the right home for a workload).
- Something from the principal's actual queue.

The size target: 3–6 modules, 8–15 interface specs, complete enough that
"does it run end-to-end" is a meaningful question. Roughly cert-watch
scale.

**Estimated effort:** Discussion with the principal, not coding. Likely
the most consequential decision of this window.

**Acceptance:** A spec file checked into the repo (or somewhere the
populator can read it from) plus a brief rationale doc explaining why
this workload is the right Phase 5 exit candidate.

### B2 — Pre-flight calibration mini-run

**Motivation:** GR-037 burned 3 hours discovering the K2-gemini pair
didn't converge. Worth spending 15 minutes up front for any new
reviewer/worker pairing to confirm the cross-family review rate is in
the convergent regime (Sonnet's 55% baseline from GR-038 is the
reference) before committing to a long full-DAG run.

**Output:** A small mini-fixture (2 impl/review pairs) and a wrapper
mode that runs just stages 3–4 and reports the cross-family review pass
rate. If <30%, abort and reconsider the pair before running the full
workload.

**Estimated effort:** Half a session. Can build on Window A2 (synthetic
seed) if that lands first.

## Window C — GR-039 execution + Phase 5 exit decision

### C1 — Run GR-039 against the real workload

**Output:** Golden run number 039, configured per the B1 spec, K2 +
Sonnet pair (the GR-038 validated configuration).

**Acceptance:** A `golden-run-039-log.md` summarising whether the
pipeline produced runnable software that satisfies its own acceptance
criteria, and what bugs/breadcrumbs surfaced. The lock rate is no
longer a PASS/FAIL gate — the actual quality of the output is.

### C2 — Phase 5 exit decision

**Output:** A short writeup (in the GR-039 log or alongside it) that
either:
- declares Phase 5 exit and lists what is now ready for Phase 6, or
- itemises the structural gaps that prevent exit and produces a
  Window-A-style follow-up plan for them.

Phase 6 is explicitly out of scope for this plan, but the decision gate
here determines whether Phase 6 work can begin.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Real workload spec is too complex for current pipeline; GR-039 fails in unrecoverable ways. | B2 pre-flight catches infeasibility cheaply. B1's size guidance (cert-watch-scale) keeps blast radius bounded. |
| Substrate seeding (A2) is harder than expected. | Pivot A2 to a substrate API addition; deprioritise it past B1. Window B does not strictly depend on A2. |
| Sonnet channel develops a stability issue under heavier load. | Channel health is reported in telemetry; if claude-code channel_invoke_failed rate climbs in A2/B2, fall back to a different reviewer family before B1. |
| Window C produces ambiguous results — pipeline runs but output is unclear quality. | C2 spec includes acceptance criteria *for the output*, not just for the pipeline. Define before C1 starts, not after. |

## Open questions (decisions before Window B)

1. **Which workload?** Principal selection. Recommend cert-watch-scale,
   not larger.
2. **Does Phase 5 exit require one real workload, or multiple?** Spec
   §10 says "first real workload deferred until integration stage is
   validated on synthetic multi-module fixtures" — i.e., the
   prerequisite is now met. Whether *one* successful real workload is
   enough for Phase 5 exit, or whether we want corroborating evidence
   (a second workload) before declaring exit, is a judgment call worth
   making explicit before C1.
3. **What's the right output-quality bar?** "Runnable software meeting
   its own ACs" is a clear floor. Whether we want anything more
   demanding (test coverage, code quality review, etc.) for Phase 5
   exit specifically is worth pinning down before B1.

## Estimated total effort

- Window A: 1–2 sessions across A1/A2/A3.
- Window B: discussion + 1 session for B2.
- Window C: 1 session prep + the GR-039 run itself (~2 hours under
  GR-038 cadence) + writeup.

Total: roughly a week of focused work, dominated by the real workload
spec selection in B1.

## Out of scope (will not be addressed by this plan)

- Phase 6 generalization (RFC-023 decomposer, RFC-024 coherence
  reviewer, RFC-027 test efficacy via mutation gates).
- RFC-022 initiative primitive (Phase 5 work-item bundling) — useful
  but not blocking real workload.
- RFC-025 stateful upstream routing — relevant to BC-145 refinement,
  not blocking real workload.
- RFC-026 principal review surface — relevant to Phase 6 when humans
  review pipeline output, but not blocking a single test workload.
- Multi-channel jury size > 2 — current quorum=2 is working; revisit
  if a workload exposes a need.

## Notes

- The "guardrail lifecycle" RFC (A1) is the only item here that ties
  back to a meta-lesson from GR-037/038. Worth not letting it slip — the
  next decayed guardrail will cost less time the second time we catch
  it.
- BC-186 is the most recent Phase-5 bug; with it resolved, the next
  potential gap is whatever GR-039 exposes. Plan accordingly.
