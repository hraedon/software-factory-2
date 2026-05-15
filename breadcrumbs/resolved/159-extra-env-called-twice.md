---
number: "159"
title: "_resolve_extra_env called twice with same arguments in process_work_item"
severity: low
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [runner, performance]
related: []
---

## Summary

`process_work_item()` in `runner.py:376,396` calls `_resolve_extra_env(config, role_name)` twice with identical arguments. The first call's result is never used between lines 376 and 396, making it dead computation.

```python
# runner.py:376 — first call, result stored in extra_env
extra_env = _resolve_extra_env(config, role_name)

# runner.py:378-389 — jury special case, doesn't use extra_env

# runner.py:396 — second call, overwrites the first result
extra_env = _resolve_extra_env(config, role_name)
```

`_resolve_extra_env` loads credentials from disk and injects them as environment variables, so each call is a filesystem read.

## Impact

- Double filesystem I/O on every work item submission (reading `credentials.yaml` and building env dict twice).
- The first result is completely unused — if someone later modified `extra_env` between lines 376 and 396 thinking it was mutable, they'd get a surprise when line 396 overwrites it.

## Fix

Remove the first call at line 376. The jury special case at lines 378-389 does not use `extra_env` (it passes `timeout` and `extra_env` to `_process_jury_work_item` which receives its own parameter), so the first result is genuinely dead.
