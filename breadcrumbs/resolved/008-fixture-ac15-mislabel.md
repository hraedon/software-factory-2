---
number: "008"
title: "Fixture AC-15 mislabel in 04-verify_event_errors.md"
severity: high
status: resolved
kind: bug
author: opcode-golden-run-001
date: "2026-05-07"
tags: [stage-2, fixtures, prompt]
related: ["BC-004"]
---

## Background

The fixture `04-verify_event_errors.md` includes AC-15 with text:

> **AC-15:** `requeue_dead_lettered_hook(id)` resets retry counter and re-enqueues.

This is dead-letter requeue text. It belongs to item 10 (`10-dead_letter.md`), not item 04 (`verify_event`).

The spec excerpt in this fixture is about event-signature verification (FR-15), and the rejection conditions (unknown key, revoked key, signature mismatch) are the core contract. AC-15 as written gives Claude a requirement that has nothing to do with the spec_section content provided.

## Impact

Claude receives conflicting signals: the spec_section describes event verification but AC-15 describes dead-letter requeue. The gate checks for `"AC-15" in content` — which passes trivially since Claude dutifully places `"""Satisfies AC-15, AC-26."""` in docstrings. But the prompt is incoherent. This is a fixture authoring error that makes the test less discriminating than it should be.

## Fix

Replace the AC-15 text with a description matching FR-15's verify_event behavior. The AC-15 identifier references FR-15's acceptance criterion, which should be about the three structured rejection paths and the deprecated-warning path.

## Acceptance criteria

- AC-15 text in `04-verify_event_errors.md` describes verify_event rejection behavior (unknown key, revoked key, signature mismatch) and deprecated-warning acceptance.
- A re-run of the golden run with the corrected fixture still produces a passing artifact.
