---
number: "129"
title: "Regista actor_metadata API change breaks 10 integration tests — dict vs attribute access"
severity: high
status: resolved
kind: bug
author: glm-5.1
date: "2026-05-12"
tags: [regista, test, dep-regista, phase-3]
related: []
---

## Problem

10 tests fail against current regista with `AttributeError: 'dict' object has no attribute 'value'` in `regista/_events.py:226`. The regista API appears to have changed `actor_metadata` from an object with `.value` attribute to a plain dict, but the factory tests still pass dicts to regista APIs that expect the old shape.

## Resolution

Fixed on regista side. All 18 previously-failing tests pass on current regista HEAD. Regista's public API correctly wraps `dict` args into `Jsonb` at the boundary; factory code passes plain dicts and this works correctly. `make check` passes clean: 542 tests, 0 lint errors, 0 audit findings.
