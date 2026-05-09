---
number: "R2-002"
title: "Bidirectional Spec Mutability (The Two-Way Street)"
author: gemini-cli
date: "2026-05-09"
related: []
---

## Context
The current architecture assumes a strict linear flow: `Spec (Socratic) -> Implementer -> Gates`.

## Problem
In real-world software, developers frequently realize a spec is contradictory or relies on a deprecated third-party API once they start writing code. If the `spec.yaml` is immutable after Phase 1, the implementer is trapped trying to satisfy an impossible contract. The workflow lacks a mechanism to formally flag an impossible constraint and negotiate an updated `spec.yaml` with the Orchestrator/Interface Architect.

## Position
**Introduce a formal `propose_spec_amendment` transition.**

### Proposed design
1. Allow implementations to fail with a specific `spec_invalid` reason.
2. Route this back to the spec generation phase (Orchestrator).
3. Record the amendment in the event log to track *why* the spec changed, preserving the history of adjustments.