---
number: "150"
title: "Channel backoff creates permanent deadlock — once max_attempts reached, channel never retried"
severity: critical
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [runner, channel, race]
related: ["109", "136"]
---

## Summary

`runner.py` maintains `channel_consecutive_failures: dict[str, int]` in the worker loop (line 160). When a channel hits `max_attempts` consecutive failures (default 5), line 187 (`if backoff >= max_attempts`) skips all work items for that channel forever. The backoff counter is only **reset** on a successful invocation (line 254: `channel_consecutive_failures.pop(channel.name, None)`), but that reset never happens because all items for the channel are skipped before any claim is attempted.

**Root cause:** The backoff check at line 186-198 runs *before* `acquire_claim` at line 199. Once `backoff >= max_attempts`, every work item for that channel hits the `continue` at line 198 and no invocation is ever attempted. The counter is never decremented, the channel never recovers.

## Evidence

```python
# runner.py:160
channel_consecutive_failures: dict[str, int] = {}

# runner.py:186-198 — guards EVERY work item for the channel
backoff = channel_consecutive_failures.get(channel.name, 0)
if backoff >= max_attempts:
    backoff_seconds = min(backoff_base * (2 ** (backoff - max_attempts)), 300)
    log.warning("channel_backoff", ...)
    continue  # ← never reaches acquire_claim or process_work_item

# runner.py:254 — only reset path, unreachable when backoff >= max_attempts
channel_consecutive_failures.pop(channel.name, None)
```

## Impact

- A single transient failure burst (5 failed invocations) permanently disables a channel for the **entire run**.
- If the default OpenCode channel is the only channel bound to a role, the entire pipeline stalls.
- Golden runs with channel failover (BC-136) are partially protected, but the primary channel deadlock still prevents any attempt to re-try the primary.

## Fix

Two options:

1. **Time-based decay:** Decrement `channel_consecutive_failures` by 1 every `N` seconds since the last failure. Combined with a skip-some-items-instead-of-all approach.
2. **Probabilistic retry:** After `max_attempts`, skip only `backoff_seconds` worth of polling cycles, then try one item. On success, reset the counter.
