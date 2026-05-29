---
number: "RFC-039"
title: "Deliverable-driven decomposition + walking skeleton — match work-unit altitude to AC altitude (hypothesis, not doctrine)"
severity: high
status: proposed
kind: design
author: claude-opus (review session)
date: "2026-05-29"
tags: [decomposition, walking-skeleton, web-service, test-efficacy, v1-lesson, dep-v1-314, dep-v1-342, phase-6]
related: ["224", "222", "209", "RFC-038", "RFC-023", "RFC-031"]
---

## Status: this is a hypothesis to validate, not a decision to implement

This RFC proposes a direction and a way to **falsify** it on one workload. It is explicitly *not* a mandate to rewrite the decomposer. The discipline that surfaced the underlying problem — build, run real workloads, read the evidence honestly, change one variable at a time — applies to the fix too. Adopt the *principle* (below); test the *prescription* before generalizing. See "Validation" and "How this could be wrong."

## Motivation — the altitude mismatch

GR-048 showed the pipeline shipped stub, non-HTTP code for a web service and most gates blessed it (BC-224). The proximate cause is the jury rubric; the root cause is upstream of any gate:

> **The work-unit altitude does not match the AC altitude.** Acceptance criteria are written at *deliverable* altitude (HTTP endpoints, status codes, DB state). Units are decomposed at *atom* altitude (one function-ish module per FR, judged in isolation).

Every downstream pathology flows from this single mismatch:

- The jury *must* reinterpret a service-level AC downward to "pass" it against a function-level unit (BC-224) — it has no other option.
- No unit owns the HTTP layer, so the assembled artifact has none.
- Tests are function-level theater: you cannot test "returns HTTP 422" without a running server, so the test author tests what the unit *can* do instead (dep-v1-342, dep-v1-364).

### Why CLI hid this and a web service exposed it

The atomic decomposition scored 96–97% lock on three CLI workloads (cert-watch, log-redact-cli, dep-graph-viewer). That was not the assumption being correct — it was the assumption's failure being *masked*. For a CLI tool the unit and the deliverable are nearly the same altitude: "the function redacts" and "the tool redacts" collapse together, and you can actually run the tool, so unit-tests ≈ acceptance-tests. The mismatch only bites when unit ≠ deliverable, i.e. when the AC is irreducibly about a *running multi-component system*. The honest framing of the prior result: **the atomic-decomposition assumption is archetype-dependent, and it was validated only on the archetype where it happens to hold** (this over-fit is recorded against BC-209).

This is the deeper inheritance from v1. The unexamined assumption v2 carried forward is not "atomic decomposition" per se — it is **"verification can be deferred and done by reading rather than by running."** Granularity is one expression (units too small to execute their ACs); the LLM jury is another (judge by inspection). v1 had already started rejecting this (BC-314, the infrastructure-bringup design doc: "make it real and executable early") and died before finishing. v2 rebuilt v1's *governance* discipline but not its half-finished move to *execution-first verification*.

## Principle (adopt) vs. prescription (test)

- **Principle — adopt now:** match unit altitude to AC altitude; a unit should be the *smallest thing that can satisfy and execute a real AC*. For service-level ACs that is a vertical slice, not a function and not the whole service.
- **Prescription — test before generalizing:** decompose web services as a *walking skeleton* + *vertical feature slices*.

## Proposal (the prescription to validate)

1. **Walking skeleton as deliverable-zero.** First produce the real runnable shell: the HTTP app boots, the SQLite schema exists, one health route answers — and this is *executed* (RFC-038 boot probe), not inspected. The skeleton owns the shared substrate (app object, DB schema, shared models) so that vertical slices plug into one real thing instead of each inventing their own.
2. **One vertical slice per FR.** Each slice owns its behavior end-to-end: route → validation → logic → persistence → response. It is implemented and tested *live* against its own AC scenario (`POST /links {url:123}` → assert 422). Because the slice owns the full stack for its FR, it *can* satisfy its ACs, and the acceptance suite *can* execute them — which is what makes RFC-038's interface-time placement possible at all.

This makes MiMo's "delegated, not verified" hand-off mechanism (BC-224) unnecessary: there is no horizontal seam for HTTP to fall through, so "the HTTP layer is someone else's job" stops being a way to silently pass.

## Relationship to other work

- **RFC-038 is the falsification instrument.** The ephemeral execution gate is built first and pointed at the *existing* atomic output (GR-049) to confirm the diagnosis, then at deliverable-decomposed output to test *this* RFC. Same gate, decomposition is the only variable.
- **RFC-023 (decomposer) is what changes.** Its job shifts from "name FR atoms semantically" (Phase B, just validated) to "carve a walking skeleton + vertical deliverables." This is the real cost of this RFC and the reason it is gated on evidence. The Phase A/B semantic-naming work is not wasted — naming still matters — but the grouping logic changes.
- **RFC-031 / RFC-030 lens:** v1 fought this disease as ~22 incident-level breadcrumbs and never converged to an invariant. This RFC is the attempt to name the invariant (altitude match) rather than file symptom #23.

## How this could be wrong (and what would falsify it)

Stated up front so the validation isn't graded on a curve:

- **Vertical slicing may not actually pass the gate either** — if the hard part turns out to be cross-slice consistency (shared schema, shared models) rather than ownership. Falsified if deliverable-decomposed url-shortener does not clear the RFC-038 gate.
- **God-agent regression.** Coarser units risk the v1 failure mode of "one agent does too much and fails opaquely" — the exact thing atomic decomposition was a reaction to. Watch-metric: per-slice attempt counts and failure legibility vs. the atomic baseline. If slices fail more opaquely than atoms, that is a real cost.
- **Parallelism / blast-radius loss.** Fewer, larger units mean less parallelism and bigger rework on failure. Acceptable only if conformance improves enough to justify it.
- **It may be web-service-specific.** The walking-skeleton pattern may not transfer to library-module or other archetypes. Do not generalize the decomposer until a second archetype confirms.

### Alternative considered and rejected

"Keep atomic units; add a strong integrator that builds the HTTP layer and wires them." Rejected: GR-048's integration stage already ran, locked, and produced no server. Beefing it up just moves the real deliverable-altitude work to the latest, most expensive moment — which *is* v1's merge-time failure cascade (dep-v1-342). Front-loading realness (vertical slices) is the point; deferring it to a fat integrator reproduces the disease.

## Validation plan

1. (RFC-038) Build the ephemeral execution gate; GR-049 confirms it fails the existing atomic url-shortener stubs deterministically.
2. Implement walking-skeleton + vertical-slice decomposition for url-shortener (decomposer change, scoped to this workload).
3. Run it (GR-050) through the *same* gate. Success = the units own and pass their ACs where atomic units could not, with per-slice failure legibility no worse than the atomic baseline.
4. Re-run one CLI workload (regression check) to confirm the principle didn't break the archetype where atomic already worked. (For CLI, unit ≈ deliverable, so a "vertical slice" may just be the existing unit — confirm no regression.)
5. Only then decide whether to generalize the decomposer or keep deliverable-decomposition archetype-gated.

## Open questions

- Who carves the skeleton vs. the slices — the decomposer, or a new skeleton stage (echoing v1's structure, which we are otherwise critiquing — proceed carefully)?
- How is shared substrate (schema, models) owned so slices don't diverge (the GR-048 evidence: link_creator used real sqlite, link_lister fabricated data — two atoms inventing persistence because nothing owned it)?
- Does the principle imply collapsing the current per-type stage topology (interface/test/impl per atom) for web services, or just regrouping what an "atom" is?
