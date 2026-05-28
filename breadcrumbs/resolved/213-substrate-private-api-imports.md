---
number: "213"
title: "Regista private API imports in production code"
severity: medium
status: implemented
kind: bug
author: adversarial-review
date: "2026-05-25"
tags: [regista, api-coupling]
related: ["RFC-036"]
---

## Problem

Three production files imported from `regista._errors` (ErrorCode, SubstrateError) — a private module that could break on regista refactors. This contradicts RFC-036 which aimed to eliminate regista private-API imports.

Affected files:
- `runner.py:10`
- `heartbeat.py:27`
- `gate_process.py:11`

## Fix (Session 53)

Replaced `from regista._errors import ErrorCode, SubstrateError` with `from regista import ErrorCode, SubstrateError` in all three files. Both types are exported from regista's public `__init__.py`.
