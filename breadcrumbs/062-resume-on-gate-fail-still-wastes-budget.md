---
number: "062"
title: "Resume-on-gate-fail still wastes Claude budget — BC-046 not fully resolved"
severity: high
status: proposed
kind: bug
author: adversarial-reviewer
date: "2026-05-08"
tags: [runner, stage-4, channel-claude]
related: ["046"]
---

## Summary

BC-046 ("Runner resubmits gate-rejected artifacts on subsequent claims") was marked resolved in a prior session. Golden Run 003 Finding 2 documents that it is **still happening**:

> "With the current `attempt_threshold` of 3, each escalated item wastes exactly 1 Claude invocation (the third attempt is always a resume)."

The `_has_prior_gate_fail()` guard was supposed to prevent this, but either has a logic bug or doesn't fully cover the resume path.

## Evidence from golden-run-003-log.md

> Items at attempt 3 always show `resuming_from_artifact` followed by immediate submit. The gate then fails or escalates the same artifact again.

The flow is:
1. Claude produces artifact → gate rejects it (gate_fail) → item returns to `new`
2. Worker claims item → finds resumable artifact from attempt 1 → submits it without invoking Claude
3. Gate rejects identical artifact again
4. Repeat until escalation

The `_has_prior_gate_fail` check reads events to detect gate_fail events. The logic gap is likely that the check happens before the claim, but the resume path inside `process_work_item` doesn't re-check.

## Fix

The runner should only use resume semantics when the artifact has **never been submitted to a gate**. Check: no `gate_fail` or `gate_pass` events exist. If either exists, clear the resumable artifact (don't quarantine — it's valid, just already-rejected) and invoke Claude fresh.

Affected code: `runner.py:process_work_item` around the `_has_prior_gate_fail` / `find_resumable_artifact` interaction.
