---
number: "213"
title: "Substrate private API imports in production code"
severity: medium
status: implemented
kind: bug
author: adversarial-review
date: "2026-05-25"
tags: [substrate, api-coupling]
related: ["RFC-036"]
---

## Problem

Three production files imported from `substrate._errors` (ErrorCode, SubstrateError) — a private module that could break on substrate refactors. This contradicts RFC-036 which aimed to eliminate substrate private-API imports.

Affected files:
- `runner.py:10`
- `heartbeat.py:27`
- `gate_process.py:11`

## Fix (Session 53)

Replaced `from substrate._errors import ErrorCode, SubstrateError` with `from substrate import ErrorCode, SubstrateError` in all three files. Both types are exported from substrate's public `__init__.py`.
