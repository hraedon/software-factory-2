---
number: "018"
title: "MockSubstrate diverges from real substrate — workflow_version filtering, event payload"
severity: medium
status: proposed
kind: improvement
author: test-audit
date: "2026-05-07"
tags: [tests, stage-1]
---

## Background

MockSubstrate has several subtle divergences from real substrate:

1. `query_work_items` silently ignores `workflow_version` filtering — real substrate likely filters on it.
2. `transition` with no workflow loaded falls back to a hardcoded `state_map` instead of validating against the workflow definition.
3. `read_events` ignores unknown kwargs that the real substrate might reject.

These divergences mean tests that pass on MockSubstrate may fail on real substrate, and vice versa.

## Acceptance criteria

- MockSubstrate filters by `workflow_version` in `query_work_items`.
- MockSubstrate always requires a loaded workflow for `transition` (remove the hardcoded `state_map` fallback).
- Review `read_events` signature compatibility with real substrate.