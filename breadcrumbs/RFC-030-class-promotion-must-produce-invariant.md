---
number: "RFC-030"
title: "Class promotion must produce an invariant, not just an RFC"
severity: high
status: implemented
kind: design
author: claude
date: "2026-05-17"
tags: [process, defect-classes, breadcrumbs, v1-lesson, meta-defense]
related: ["RFC-016"]
---

## Motivation

CLASS-005 (Inner Gate vs Outer Gate Ruleset Divergence) has 11 instances, max severity critical, and an RFC — RFC-011 — already filed against it. RFC-011 is dormant. The class continues to accumulate instances. This is the v1 whack-a-mole pattern recurring inside the defense system itself.

v1's failure mode was that new problem classes surfaced faster than invariants could be built, so defenses accumulated per-symptom. The defect-class taxonomy introduced in RFC-016 was meant to break that loop by forcing class-level promotion into enforcement. It works as long as promotion actually converts to an invariant. It does not work when the trigger action is "file an RFC" and the RFC sits in `proposed` indefinitely. Filing an RFC diffuses ownership and has no time bound. The class keeps growing; the RFC stays dormant; reviewers keep adding symptom-fix BCs with a clear conscience because the RFC exists. Nothing forces movement.

## Proposal

Replace the existing promotion rule with the following three-part rule.

### Part 1 — Trigger (unchanged)

When a CLASS file accumulates ≥5 instances OR contains ≥2 high/critical instances, the next reviewer files an RFC against the class. This is the same trigger as today.

### Part 2 — Block rule (new)

Once an RFC has been filed against a class, no new BC may be added to that class's instances table until ONE of the following holds:

- **Invariant implemented**: the RFC's status flips to `implemented` and the class is moved to a "Stabilized Defect Classes" section of `breadcrumbs/README.md`, OR
- **Symptom-fixed rationale written**: the RFC is explicitly closed with a `symptom-fixed-because` rationale — a short paragraph in the CLASS file's body that answers: "what cost would the invariant carry that exceeds the cost of continuing to fix instances symptom-by-symptom?" The rationale must be signed by the principal. Once present, the block lifts and the class may continue accumulating symptom-fix BCs without a further RFC requirement.

### Part 3 — What the would-be BC filer does when blocked

Filing a new instance while an RFC is in flight (`proposed` or `in_progress`) is blocked. The would-be BC author must choose one of:

- (a) Drive RFC-NNN forward: assign ownership, set a target run for validation, move status to `in_progress`.
- (b) Request the symptom-fixed-because rationale from the principal; once the principal writes and signs it, file the BC normally.
- (c) Demonstrate that the new failure is genuinely a different class — document the distinction and file a new CLASS file or a new BC under a different class.

## Why this has teeth and the soft version does not

"File an RFC" diffuses ownership: there is no designated driver and no deadline. A reviewer can add another symptom-fix BC in good conscience because the RFC exists — they are not the one who failed to ship it. The block rule creates an explicit pressure point at exactly the moment we would otherwise add another symptom-fix. The person about to file the next BC becomes the forcing function. They must either move the RFC forward or formally record the decision to accept ongoing symptom-fixing. That decision is recorded in writing, is signed by the principal, and answers a specific cost question. There is no silent drift.

## Worked example: CLASS-005 today

11 instances, max severity critical, RFC-011 dormant. Under the new rule, the next inner/outer gate divergence finding cannot be filed as a new instance in CLASS-005's instances table until one of:

- RFC-011 ships its unified gate evaluation layer (status flips to `implemented`), or
- The principal writes and signs the symptom-fixed-because rationale in CLASS-005's body.

The next BC filer who encounters a gate divergence becomes the forcing function. They are blocked from the easy path (add a row) and must instead surface the dormancy explicitly.

## Operational cost

Small. The only new artifact is the symptom-fixed-because rationale, and it is required only if the principal decides against implementing the invariant. In most cases the RFC will be driven to implementation and the rationale is never written. The block rule costs the filer one round-trip conversation with the principal in the blocking case — a low price relative to the cost of unchecked class growth.

## Acceptance criteria

- **AC-1**: `breadcrumbs/README.md` is updated to replace the existing promotion rule text with the new three-part rule, citing RFC-030.
- **AC-2**: CLASS-005's body documents its status under the new rule, and the principal has either (a) assigned an owner and target run to RFC-011, or (b) written and signed the symptom-fixed-because rationale in CLASS-005. (Demonstrated via the worked example in deliverable 2 of the RFC-030 implementation session.)
- **AC-3**: `scripts/check_class_block_rule.py` exists and is wired into `make check` (via `class-block` target).
- **AC-4**: This RFC's status moves to `implemented` once AC-1, AC-2 and AC-3 are both satisfied.

## Out of scope

This RFC governs only class-level promotion and the blocking rule for class instances. Individual BC filing cadence, format, and review process are unchanged.
