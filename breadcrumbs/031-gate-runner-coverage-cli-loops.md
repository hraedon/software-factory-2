---
number: "031"
title: "Gate process runner coverage stuck at 54% — CLI/poll loops need integration tests"
severity: medium
status: proposed
kind: improvement
author: opencode
date: "2026-05-07"
tags: [gate, runner, testing]
related: ["029"]
---

## Problem

`gate_process.py` and `runner.py` are both at ~54-58% coverage. The uncovered lines are exclusively CLI entry points (`main()`), signal handlers (`_handle_signal`), and poll loops (`gate_loop`/`worker_loop`). These cannot be unit-tested with InMemorySubstrate alone — they require subprocess spawning or signal simulation.

## Proposal

Two approaches:
1. Extract `main()` into thin wrappers that call `_main(argv)` with injectable args, then unit-test `_main()`
2. Add `@pytest.mark.integration` tests that run `factory-run` and `factory-gate` as subprocesses against Postgres

Approach 1 is lower-effort and covers the arg-parsing; approach 2 covers the full loop but requires Postgres.

## Impact

Low blast-radius — the uncovered code is CLI plumbing, not business logic. The business logic (`process_gate_item`, `process_work_item`) is well-covered.