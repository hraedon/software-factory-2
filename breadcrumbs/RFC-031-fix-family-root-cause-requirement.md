---
number: "RFC-031"
title: "Fix-family root-cause requirement: BCs that cite related BCs must explain the missing invariant"
severity: medium
status: implemented
kind: design
author: claude
date: "2026-05-17"
tags: [process, breadcrumbs, fix-quality, v1-lesson, meta-defense]
related: ["RFC-030", "RFC-016"]
---

## Motivation

BC-145 (field name typo in `GateResult`) seeded a five-bug family. BC-175 through BC-179 addressed ordering, idempotency, and propagation symptoms; BC-180 extended the fix to the source side; BC-185 finally introduced the structural split (`transition_fields`/`routing_fields`) that ended the family. Each intermediate fix made the next bug possible: the patch closed one leak and left the pressure intact. The root cause — producer/consumer field-ownership ambiguity in `GateResult.custom_fields` — was never named until the fifth iteration forced it.

This is the whack-a-mole loop at family scale. v1's version accumulated across classes over months; the BC-145 family ran through five GR cycles inside a single line of investigation. Same shape, smaller radius, same lost time.

## Proposal

When a new BC's `related:` field cites another BC that shares at least one tag with it, the BC's `## Fix` section must include a subsection titled `### Why this isn't the previous fix recurring`. That subsection must do one of two things:

1. Name the invariant that was absent in the prior fix, and explain how the new fix establishes it — not just patches around it.
2. Explicitly state: "I don't have the invariant yet; this is another symptom fix." In that case the fix is held until someone proposes the invariant. The BC may be filed and tracked, but the patch is not merged.

The trigger is structural: shared tag plus `related:` citation. The analysis is required at the *second* BC in the family, not the fifth.

## Worked Example

BC-180 cited BC-145 (and the BC-175–179 cluster) without an explicit missing-invariant analysis. Under RFC-031, BC-180's `## Fix` section would have included:

> **Why this isn't the previous fix recurring:** The invariant missing in BC-145 through BC-179 was producer/consumer field-ownership ambiguity in `GateResult.custom_fields`. Any consumer-side filter on that dict is a guard against mislabeled data, not an invariant over its schema. The prior fixes added guards; they left the schema ambiguity in place. This fix does the same — it is another symptom fix. The invariant would require separating transition-owned fields from routing-owned fields at the schema level.

That sentence, written at BC-180, would have identified BC-185's `transition_fields`/`routing_fields` split three iterations earlier.

## Why This Isn't Redundant with Code Review

Code review checks the patch. This rule checks the *understanding* behind the patch. A symptom fix can be technically correct, well-tested, and pass review while still propagating the loop — because the loop lives in what the fix left unaddressed, not in what it changed. The paragraph forces that gap into the record before the next bug arrives.

## Interaction with RFC-030

Complementary, different granularity. RFC-030 governs the class level: five or more instances of the same error pattern across the codebase forces an invariant decision. RFC-031 governs the family level: two or more related BCs sharing a tag forces an invariant analysis at the second BC. RFC-031 fires earlier and at finer scope; RFC-030 is the coarser backstop if RFC-031 is waived or missed.

## Operational Cost

Small. One paragraph per BC in a family. The hard part is the analysis — which is the point. If the paragraph is easy to write, the fix is probably sound. If it is hard to write, the fix probably isn't.

## Acceptance Criteria

- **AC-1**: This RFC filed and `breadcrumbs/README.md` Schema section updated to reference the new `### Why this isn't the previous fix recurring` requirement in the `## Fix` template.
- **AC-2**: The next BC filed with a `related:` field includes a worked example of the new paragraph; principal reviews and confirms it meets the intent.

## Out of Scope

Does not apply to BCs without `related:` fields. Does not replace existing fix documentation — one paragraph is added, nothing is removed. Does not retroactively require updates to closed BCs; the BC-145 family is an illustrative example, not a remediation target.
