---
number: "162"
title: "agent_golden_run.py auto-cleanup destroys scheduler crash forensics"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [golden-run, observability, scheduler]
related: ["148", "161"]
---

## Summary

`agent_golden_run.py` auto-cleans workspace, logs, and isolated opencode DB on every run (line 369: `_info("Auto-cleaning...")`, line 370-378: `shutil.rmtree` + `unlink`). When the scheduler crashed in GR-029 with exit code 1, all three log files (`/tmp/gr029-{runner,gate,scheduler}.log`) were destroyed before any post-mortem could be conducted.

```python
# agent_golden_run.py:369-378
_info("Auto-cleaning workspace + logs + isolated DB (non-interactive mode)...")
if wr.exists():
    shutil.rmtree(wr)
for log in logs:
    log.unlink(missing_ok=True)
```

The crash was recorded only as "Root cause unknown — logs were auto-cleaned before inspection" in the golden run log.

## Impact

- Every golden run that crashes is a black box — no traceback, no last log lines, no workspace state.
- The scheduler crash (BC-148, BC-161) cannot be diagnosed without re-running and preserving logs.
- This compounds with the missing exception handler (BC-161): even if the scheduler printed a traceback to stderr, the `subprocess.STDOUT` redirect captures it, and the auto-cleanup destroys it.

## Fix

At minimum, preserve logs when any process exits with non-zero exit code. Options:

1. **Conditional preservation** — Add a `--preserve-on-error` flag. When any `p.returncode != 0`, copy logs to `.factory/crash-NNN/` before cleaning.
2. **Don't auto-clean by default** — Change default to `--no-cleanup`, require explicit opt-in for cleanup.
3. **Capture stderr separately** — Direct process stderr to a separate file from stdout so tracebacks are preserved even if auto-cleanup runs.
