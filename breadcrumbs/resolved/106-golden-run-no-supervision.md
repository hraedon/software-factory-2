---
number: "106"
title: make golden-run lacks process supervision
description: >
  The Makefile backgrounds runner, gate, and scheduler with &, then wait. If the
  runner dies early, gate and scheduler continue burning claims and model budget
  pointlessly. There is no health check, restart, or pipeline-failure stop.
severity: medium
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [ops, golden-run, process-supervision]
---

## Proposed fix

Add a small Python nanny script that launches all three processes, polls their
PIDs, and terminates the remaining ones if any process exits non-zero. Or
migrate to a process manager (systemd, supervisord) for production runs.

## Affected file

- `Makefile`

## Resolution

Created `scripts/golden_run_nanny.py` that launches all three processes, polls PIDs, and terminates remaining processes if any exits non-zero. `make golden-run` now uses nanny instead of raw `&`/`wait`.
