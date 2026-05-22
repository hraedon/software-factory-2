---
number: "202"
title: "inner_gate _should_failover triggers on any non-zero exit code — too aggressive"
severity: medium
status: proposed
kind: bug
author: self-audit
date: "2026-05-22"
tags: [gate, failure-routing]
related: []
---

## Problem

`_should_failover()` at `inner_gate.py:47` returns `True` for any `exit_code not in (None, 0)`. Exit code 1 is a normal "model produced bad output" response — failover to another channel won't help because the same prompt may produce the same bad output. This causes unnecessary channel switches and budget burn.

Appropriate failover triggers: timeout, binary not found, empty output. Inappropriate: model error (exit 1), usage error (exit 2).

## Fix

Either narrow to known-retryable exit codes, or check the error message for transport-level failures (timeout, not-found, connection-refused) vs. model-level failures (refusal, malformed output).
