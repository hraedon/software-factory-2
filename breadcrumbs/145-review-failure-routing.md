---
number: "145"
title: "cross_family_review failure is terminal — no route back to implementer for legitimate review-found defects"
severity: high
status: implemented
kind: design
author: agent
date: "2026-05-14"
tags: [pipeline, failure-routing, jury, review, stage-5]
related: ["139", "120"]
---

## Summary

When `cross_family_review` returns `passed=false` on a legitimate defect — e.g., the reviewer correctly identifies that the implementation is a stub or the tests don't exercise the required behavior — the only available paths are (a) retry the same review against the same artifacts, or (b) escalate to `cannot_proceed` once `attempt_threshold` is exhausted. There is no path that routes the review's findings back to the implementer (or, per Principle 8, to the interface architect) for a targeted revision.

Surfaced concretely in GR-027 item `52fae369` (review stage, FR involving `extract_chain`). DeepSeek's verdict was:

> AC-01: `extract_chain` implementation is a stub returning `[]` unconditionally — it never actually extracts certificates from DER data as required.
> AC-01: test suite never verifies core behavior — no test supplies valid DER certificate data and asserts on extracted Certificate objects.

The review was substantively correct. The pipeline had no use for that information beyond "fail this work item." A 3-attempt budget on the *review* role does nothing — the artifact under review doesn't change between attempts, so the reviewer will give the same verdict.

## Why this matters

The architecture's load-bearing claim (spec §3, Principle 3) is that frontier-model review replaces human review at phase boundaries. For that substitution to deliver value, review findings must be actionable upstream. Otherwise the system is a slop-detector that terminates work without learning.

BC-139 made review-failure escalation terminate cleanly (no infinite loop, no budget burn). It did **not** address the underlying shape: review verdicts are routing signals, not retry signals.

## Proposed direction (not a decided design)

Two options worth weighing:

1. **Review-driven implementation revision.** A `cross_family_review` failure with a defect kind that targets the implementation should produce a new claim for the *implementer* on the upstream work item, with the review's findings as structured feedback. Tracks the spec Principle 8 pattern ("errors loop back to contract revision, not worker retry") — but applied to artifact revision below the contract.

2. **Diagnostic-kind taxonomy.** Distinguish "review found a substantive defect in upstream artifacts" from "review itself was malformed / refused / produced bad JSON." Only the latter is a review-retry case; the former is a routing-back case. This dovetails with RFC-016 (defect-class taxonomy).

Both interact with BC-120 (implementer-initiated interface amendment) — there's a family of "routing failures back upstream" decisions the pipeline still needs.

## Reproduction

`.factory/gr027-workspace-backup/52fae369-60a9-480e-b206-cb9dee4653ed/attempt-0001/artifact.py` contains the verdict. The upstream implementation artifact (the actual `extract_chain` stub) is on the work item the review depends on.

## Phase 1 implementation (Session 34)

- **Diagnostic taxonomy**: `REVIEW_FOUND_DEFECT` vs `REVIEW_MALFORMED` — structured findings with `ReviewFinding` schema
- **Router dispatch**: `REVIEW_FOUND_DEFECT` routes to STATE_NEW with `review_feedback_pending=True`; not in `_ESCALATABLE_KINDS`
- **Context injection**: `_format_review_feedback()` renders findings into prompt; `render_prompt()` injects `## review_feedback`

## Phase 2 (deferred to RFC-025)

Phase 1 routes the REVIEW item back to STATE_NEW with feedback metadata, but does NOT create a new work item for the implementer/interface_architect. Actual upstream routing (creating new work items for upstream roles based on review findings) requires RFC-025 (stateful upstream routing) — the scheduler/router cannot currently create work items for different work_item_types based on gate diagnostics.

## Not in scope here

- The single-juror disagreement case (GR-027 item `06a56e11`) is a separate, healthier case: there, escalation is the right outcome because jurors disagree and quorum can't be reached. This breadcrumb is specifically about *successful* review verdicts that find defects, not about indeterminate ones.
