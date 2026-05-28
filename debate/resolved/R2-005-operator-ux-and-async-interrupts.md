---
number: "R2-005"
title: "Operator UX and Asynchronous Interrupts"
author: gemini-cli
date: "2026-05-09"
related: []
---

## Context
The transcript notes the value prop is to "approve the plan, and then go do something else." Yet, Regista and SF2 seem entirely focused on backend logs and Postgres events.

## Problem
If the system hits an escalation, there is no alerting abstraction (Slack, Webhooks, Email) or an approval dashboard. The Principal is reduced to polling the CLI, defeating the purpose of asynchronous autonomy.

## Position
**Build an event-driven notification sink in Regista to alert operators of critical escalations asynchronously.**

### Proposed design
1. Regista event hooks should publish `escalation` events to a notification bus.
2. Provide a simple adapter framework for Slack/Discord/Email.
3. Include actionable links or commands in the notification so the operator can quickly resolve the blocker.