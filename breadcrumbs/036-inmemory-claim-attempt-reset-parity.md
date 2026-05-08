---
number: "036"
title: "InMemorySubstrate claim attempt_number resets to 1 after every transition — escalation path untestable"
severity: high
status: proposed
kind: bug
author: opencode
date: "2026-05-08"
tags: [runner, gate, dep-substrate, failure-routing, testing]
related: ["027", "035"]
---

## Problem

InMemorySubstrate.transition() calls `self._claims.pop(work_item_id)`, removing the claim entry entirely. The next `acquire_claim` has `existing = None` and starts at `attempt_number = 1`. This means the escalation path in `router.route()` (`attempt_number >= attempt_threshold`) can never fire through normal pipeline flow with InMemorySubstrate.

The real Postgres Substrate likely preserves attempt counts across claim-release cycles (tracked in a separate column or derived from event history).

## Evidence

`test_e2e_escalation_through_three_gate_failures` had to inject a `SimpleNamespace(attempt_number=3)` fake claim on the 3rd gate cycle to trigger escalation. The real pipeline with InMemorySubstrate would never escalate because every gate_fail→new→claim cycle resets to attempt 1.

## Fix options

(a) InMemorySubstrate: preserve attempt counter on the work item state dict instead of only in the claim entry. Increment on each `acquire_claim` regardless of whether the previous claim was released or expired.
(b) Derive attempt_number from event history (count claim_acquired/claim_stolen events) instead of tracking it in the claim.
(c) Accept the parity gap and document it; rely on the real-Postgres test for escalation coverage once BC-035 is fixed and the full 3-stage pipeline can run against Postgres.

Option (a) is the most straightforward fix. Requires a substrate change.
