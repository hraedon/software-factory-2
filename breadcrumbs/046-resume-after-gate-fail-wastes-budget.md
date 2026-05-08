---
number: "046"
title: "Runner resubmits gate-rejected artifacts on subsequent claims — wastes Claude budget"
severity: high
status: proposed
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [runner, failure-routing, channel-claude]
related: ["037"]
---

## Problem

Golden Run 003 Finding 2: when the worker claims an item that has a resumable artifact from a prior attempt, it immediately resubmits that artifact without re-invoking Claude. This is correct for crash recovery. But when the gate has already rejected the artifact (gate_fail) and sent the item back to `new`, the worker resubmits the identical artifact that just failed.

The `_has_prior_gate_fail` guard (runner.py:138-143, introduced in BC-039/040 session) prevents resume only when there's a gate_fail event, but the resumable logic at lines 159-180 runs first and only checks artifact integrity — not whether that artifact was already submitted to the gate.

Evidence from golden run 003: "Wasted invocations on retry: ~8 (resubmitted same bad artifact)." ~10% of Claude budget per run. Not catastrophic, but structurally wrong and will compound in Phase 3+ parallelism.

## Fix

The runner should clear or skip resumable artifacts when a gate_fail event exists for the current context. The `_has_prior_gate_fail` check at line 159 is insufficient because it guards against any prior gate_fail in history, but the resumable artifact from attempt N may have been produced before attempt N's gate evaluation. The guard needs to check: "was this specific artifact already submitted and rejected?"

Alternatively: clear the resumable artifact directory when gate_fail fires (gate_process.py side).
