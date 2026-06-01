---
number: "233"
title: "agent-wake notification for golden-run monitoring (event-driven, vs cron/poll)"
severity: low
status: deferred
kind: improvement
author: opus-strategic-review
date: "2026-05-31"
tags: [golden-run, nanny, agent-wake, observability, deferred, dep-agent-wake]
related: ["231"]
---

## Problem

Monitoring a detached golden run today is poll-based: an operator or an agent
session tails `/tmp/gr-nanny-*.log`, or sets a cron / `ScheduleWakeup` loop that
re-wakes on an interval and mostly finds "still running." The stated goal is to
let *agents* monitor factory runs without dumb crons — i.e. event-driven
notification on completion / stall / `cannot_proceed` escalation.

[[project-agent-wake]] (external-to-session signaling) is the apparent fit. This
breadcrumb records why it is **deferred**, not built, and the condition that
flips it.

## Assessment (2026-05-31)

Three findings argue against building it now:

1. **sf2's core loop has nothing in agent-wake's shape.** Workers are blocking
   subprocesses; the runner waits on a 5s poll of regista; the workflow never
   parks on a human (terminal states are `locked` / `cannot_proceed`, both
   `terminal: true`). There is no idle session for a signal to unblock. If the
   5s poll is ever the pain, the fix is regista-native LISTEN/NOTIFY
   (`regista/_hooks.py` already emits `NOTIFY channel, event_id`), **not**
   agent-wake — wrong layer.

2. **The harness already does completion-wake for free.** A GR launched locally
   via the agent's own background-process primitive re-invokes the agent on
   exit (no cron, no agent-wake). agent-wake's *residual* value is only the
   cases the harness can't watch: mid-run **stall**, live `cannot_proceed`
   **escalations**, and **cross-machine / cross-harness** runs.

3. **Robustness asymmetry.** Polling fails safe (finds out late, self-heals);
   wake fails silent (dead daemon/socket/config -> never notified -> silent
   hang). For *monitoring*, a missed signal is the worst outcome — so a lazy
   fallback poll is mandatory regardless, which caps the marginal gain of the
   wake path to "react in seconds, not up to N minutes." BC-231 is direct
   evidence the wake substrate breaks silently (it cost a GR work item).

## Build sketch (when promoted)

- **Tier 1 (operator/agent ping):** emit an HMAC-signed event to the agent-wake
  ingest from `golden_run_nanny.py` at its terminal / timeout / no-progress
  branches (it already tracks `start_time` / `last_progress`). Behind a config
  flag; missing daemon degrades to no-notification, never a crash (fail-safe).
- **Tier 2 (live escalations):** a small forwarder LISTENs on regista's NOTIFY
  channel, filters `-> cannot_proceed`, POSTs to agent-wake. Template already
  exists: `agent-notes/bridge.py` (LISTEN -> HMAC POST -> agent-wake).
- Add an `sf2` source + route + HMAC secret to
  `~/.config/agent-wake/config.json`; **provision it reproducibly** (not in any
  repo today — see BC-231).

## Promotion trigger (build when BOTH hold)

1. **Run economics change** — GRs run *concurrently* or *long enough*
   (multi-hour / overnight) that poll overhead is a real tax and stall-latency
   actually costs, AND
2. **Substrate hardened** — agent-wake config/daemon/socket provisioned
   reproducibly, health-checked, and failing *safe* (missing daemon -> fall
   back to poll). Gate on BC-231 closure holding across multiple GRs.

Until then: use the harness background-completion wake for monitoring; this stays
deferred. A tightly-scoped Tier-1 is also acceptable purely as a stack-composition
/ dogfooding artifact — but label it as such, not as an operational need.
