---
number: "051"
title: "spec.md still cites BC-021 as Phase 1 blocker — regista hooks appear to work"
severity: medium
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [dep-regista-021, spec]
related: []
---

## Problem

`spec.md:44`:

> **Blocking on:** regista Phase 2 stabilization. Specifically, BC-021 in regista (hook consumer no reconnect) is a hard prerequisite for v2's hook-based stage triggering.

And `spec.md:255-258`:

> **Phase 0 — Regista completion.**
> - BC-021 resolved (hook consumer reconnect).
> - Regista stable enough to depend on.

The factory has executed 3 golden runs with scheduler-driven handoffs between stages. The scheduler triggers downstream work-item creation based on upstream items reaching `locked` state. Whether BC-021 is resolved in regista is now an archaeological question — the factory operates in production without it. The spec's phasing says Phase 0 is blocking on BC-021, but Phase 2 is running.

## Investigation needed

1. Check regista breadcrumb BC-021 status.
2. If resolved: update spec.md §9 Phase 0 to reflect completion, and AGENTS.md to match.
3. If still open: document why the factory works without it (did v2 find a different hook approach?), and update the spec's dependency statement.
