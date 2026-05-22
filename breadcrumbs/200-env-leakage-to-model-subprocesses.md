---
number: "200"
title: "subprocess_channel.py leaks full os.environ to model subprocesses"
severity: high
status: proposed
kind: bug
author: self-audit
date: "2026-05-22"
tags: [runner]
related: []
---

## Problem

`subprocess_channel.py:91` constructs `env_override = {**os.environ, **(extra_env or {})}` which passes the entire parent environment to model channel subprocesses. This includes `DATABASE_URL`, API keys, tokens, and any other sensitive env vars from the factory process.

The gate subprocess code uses `gate_subprocess_env()` which strips sensitive vars, but the runner-side channel code does not.

Same pattern in `venv.py:61,110,170` (leaks to pip/uv) and `credentials.py:44` (leaks when no env passed).

## Fix

Use `factory.sandbox.strip_sensitive_env()` or construct a minimal env dict with only the required vars for each subprocess type.
