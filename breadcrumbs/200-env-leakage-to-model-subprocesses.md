---
number: "200"
title: "subprocess_channel.py leaks full os.environ to model subprocesses"
severity: high
status: resolved
kind: bug
author: self-audit
date: "2026-05-22"
tags: [runner]
related: []
---

## Problem

`subprocess_channel.py:93` constructs `env_override = {**os.environ, **(extra_env or {})}` which passes the entire parent environment to model channel subprocesses. This includes `DATABASE_URL`, API keys, tokens, and any other sensitive env vars from the factory process.

The gate subprocess code uses `gate_subprocess_env()` which strips sensitive vars, but the runner-side channel code does not.

Same pattern in `venv.py:61,110,170` (leaks to pip/uv) and `credentials.py:44` (leaks when no env passed).

## Fix

Replaced raw `os.environ` dictionary copy with `strip_sensitive_env(os.environ)` in three locations:

1. **`subprocess_channel.py`** — `env_override` now uses `strip_sensitive_env()` as the base, then merges `extra_env` (which may contain the provider API key injected by `credentials.py`).
2. **`venv.py`** — All venv creation and pip/uv install subprocess calls (project venv and gate venv, creation and dependency install, version query) now use `strip_sensitive_env(os.environ)` instead of `dict(os.environ)`.
3. **`credentials.py`** — `inject_credentials_into_env()` now calls `strip_sensitive_env()` when `env=None` instead of copying `os.environ`. Explicit `env` dicts are unaffected (already non-leaking).

## Invariant

Every subprocess spawned by the factory (model channel, gate tooling, venv management) must build its environment map via an explicit allow-list or scrubbing function. `strip_sensitive_env()` is the central scrubber for cases that need to preserve operational variables (`PATH`, `HOME`, `LANG`, `TMPDIR`). Operational-only cases should use `factory.subprocess.clean_env()` which produces a minimal set of 4 vars.

## Regression tests

- `test_empty_output_retry.py::test_env_does_not_leak_sensitive_vars` — Asserts `DATABASE_URL` is absent, `PATH` is present in the `env` kwargs passed to `run_subprocess` from `SubprocessChannel.invoke`.
- `test_venv.py::test_venv_creation_does_not_leak_sensitive_env_vars` — Asserts all `run_subprocess` calls in `ensure_project_venv` strip `DATABASE_URL` and `MY_API_KEY` while retaining `PATH`.
- `test_credentials.py::test_none_env_strips_sensitive_but_keeps_operational` — Asserts `inject_credentials_into_env` with `env=None` strips `DATABASE_URL` / `MY_API_KEY` and keeps `PATH`.
