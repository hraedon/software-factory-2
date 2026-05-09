---
number: "071"
title: "sub.transition(custom_fields=...) merges into WorkItem but API surface implies per-event storage — telemetry footgun"
severity: low
status: proposed
kind: design
author: opencode
date: "2026-05-09"
tags: [telemetry, substrate, dep-substrate]
related: ["068"]
---

## Summary

`Substrate.transition()` accepts a `custom_fields` keyword argument, and `gate_process.py` uses it to store diagnostics. The API surface suggests that custom_fields are per-event metadata, but the actual behavior is that `custom_fields` are **merged into the WorkItem** — they are not stored on the `Event` dataclass. The `Event` type has no `custom_fields` attribute.

This confused me during BC-068 implementation: I initially wrote a fallback in `telemetry.py` reading `ev.custom_fields`, assuming events carry the fields, before checking the `Event` dataclass and removing it.

## Impact

- Future telemetry consumers who read the `transition()` signature and assume they can reconstruct diagnostics from `event.custom_fields` will get `AttributeError` or `None`.
- The `InMemorySubstrate` stores custom_fields updates in the event's `payload["custom_fields_update"]` as an implementation detail, but this is not part of the public API contract and real Postgres events don't expose it the same way.

## Proposed improvement

Option a: Add `custom_fields` as a read-only property on `Event` that returns the merged custom fields at that point in time (requires substrate schema change). Option b: Document the merge semantics prominently in the `transition()` docstring and add a `⚠ custom_fields are merged into the WorkItem, not stored per-event` note. Option c: Accept the current design and add an integration test that asserts `Event` has no `custom_fields` attribute, preventing future consumers from assuming one exists.