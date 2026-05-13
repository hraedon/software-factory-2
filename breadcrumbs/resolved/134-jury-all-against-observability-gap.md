---
number: "134"
title: run_jury observability gap — disagreement_rationale empty on all-error/all-timeout
severity: medium
status: implemented
kind: bug
author: agent
date: "2026-05-13"
tags: [jury, telemetry, gate, stage-4]
related: ["132", "RFC-005"]
---

## Problem

`run_jury()` only populated `disagreement_rationale` when there were mixed votes (`votes_for > 0 and votes_against > 0`). When all jurors errored or timed out (votes_for=0, votes_against=N), the rationale was an empty string and the gate output said only "Jury quorum not met (0 for, N against)." — indistinguishable from a genuine unanimous rejection without inspecting individual verdict rationales.

## Fix

### `jury.py`: Always populate rationale when quorum not met

`disagreement_rationale` is now populated for ALL non-quorum cases:
- **Split vote**: `For: a: yes | Against: b: no` (unchanged)
- **All against**: `[all_against] a: rationale; b: rationale` (new)

The `[all_against]` tag allows downstream consumers (gate, telemetry) to distinguish infrastructure failures from genuine model disagreement by inspecting individual vote rationales.

### `gate.py`: `evaluate_jury()` uses tag for diagnostics

When the rationale starts with `[all_against]`, diagnostics now read "All jurors against: ..." instead of "Disagreement: ...", making the gate output self-describing.

## Validation

- 608 tests pass, 13 skipped, 0 lint errors
- New test `test_all_channels_fail` verifies all-error case populates rationale
- Updated `test_unanimous_against` verifies `[all_against]` tag
- New `TestEvaluateJury` class with 3 tests covering all-against, split, and pass cases
