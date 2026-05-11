---
number: "118"
title: "golden_run_nanny.py lacks overall timeout and progress reporting"
severity: low
status: proposed
kind: improvement
author: glm-5-1
date: "2026-05-11"
tags: [golden-run, operations, stage-3]
related: ["106"]
---

## Problem

The nanny script replaces the raw `&/wait` pattern but has two gaps:

1. No overall timeout — if all three processes hang, the nanny runs forever with no output.
2. No progress reporting — it only logs to per-process files, not to stdout, so `make golden-run` appears frozen until processes exit.

## Affected files

- `scripts/golden_run_nanny.py`

## Proposed fix

1. Add `--timeout` flag (default: 60 minutes) that kills all processes if exceeded.
2. Add periodic stdout status (every 30s) showing PID status and elapsed time.