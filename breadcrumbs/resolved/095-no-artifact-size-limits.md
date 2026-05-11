---
number: "095"
title: No artifact size limits anywhere
description: >
  artifact_path.read_bytes() and channel stdout capture had no size bounds. A
  model channel emitting multi-megabyte output (accidentally or adversarially)
  could OOM the runner or gate process before any gate could reject it.
severity: high
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [runner, channel, DoS, resource-exhaustion]
---

## Resolution

Added `MAX_ARTIFACT_SIZE_BYTES = 1_000_000` (1 MB) to `factory.constants`. The
runner checks artifact size before `read_bytes()` and emits `channel_fail` if the
limit is exceeded. `SubprocessChannel.invoke` checks stdout size before writing
to `raw_stdout.txt`.

## Files changed

- `src/factory/constants.py` — new constant
- `src/factory/runner.py` — size check before ingestion
- `src/factory/subprocess_channel.py` — size check before raw stdout write
