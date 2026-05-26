---
number: "215"
title: "Scheduler dedup lock is single-process only — no HA support"
severity: low
status: proposed
kind: design
author: adversarial-review
date: "2026-05-25"
tags: [scheduler, concurrency, phase-6]
related: ["BC-190"]
---

## Problem

The scheduler's `_dedup_lock_registry` (BC-190) uses an in-memory `WeakValueDictionary` to prevent duplicate downstream work item creation. This only guards against races within a single scheduler process. Multi-process deployments (e.g., for HA or scaling) would require a distributed lock (e.g., Postgres advisory lock).

The comment was updated in Session 53 to reflect Phase 5 status (was incorrectly citing Phase 2/3).

## Impact

Currently acceptable — Phase 5 runs a single scheduler. If the factory is deployed with multiple scheduler instances (for HA), duplicate downstream items will be created silently.

## Proposed fix

When multi-scheduler mode is needed:
1. Use Postgres advisory locks (`pg_try_advisory_lock`) keyed on `(source_id, downstream_type)`
2. Or use substrate's existing claim mechanism as a distributed mutex
