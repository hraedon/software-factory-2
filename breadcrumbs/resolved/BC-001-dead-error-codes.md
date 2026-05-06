---
number: "BC-001"
title: "Dead error codes: defined but never raised"
severity: low
status: proposed
kind: design
author: opencode
date: "2026-05-06"
tags: [error-codes, cleanup]
related: []
---

## Problem

Six `ErrorCode` enum members in `_errors.py` are defined but never raised anywhere in the codebase:

| Code | Notes |
|------|-------|
| `CLAIM_NOT_EXPIRED` | No code path raises it |
| `IDEMPOTENCY_COLLISION` | Only `IDEMPOTENCY_COLLISION_WITH_DIFFERENT_PAYLOAD` is actually raised |
| `LIBRARY_IS_SOLE_SIGNER` | AC-33 is enforced structurally (no `signature` param on public methods), not via runtime raise |
| `DEPRECATED_KEY_ID` | `_keys.py:134` logs a warning but does not raise; spec says "deprecated key_id: accept; emit structured warning" — so not raising is correct per spec |
| `REPLAY_HALTED` | Replay uses `RuntimeError` internally instead |
| `HOOK_NOT_DEAD_LETTERED` | No code path raises it |

## Options

1. **Remove dead codes.** Delete enum members that have no raiser. Clean, but removes names that future code might use.
2. **Wire them up.** Add raises at the appropriate code points. Most straightforward for `DEPRECATED_KEY_ID` (would change behavior — spec says accept, so this is wrong), `REPLAY_HALTED` (replace RuntimeError), `LIBRARY_IS_SOLE_SIGNER` (add runtime check in addition to structural check).
3. **Document intent.** Add a comment on each dead code indicating whether it's reserved for future use or is dead code that should be removed.

## Recommendation

Option 3 is safest. Remove `CLAIM_NOT_EXPIRED`, `IDEMPOTENCY_COLLISION`, and `HOOK_NOT_DEAD_LETTERED` (these have no plausible future use that isn't covered by existing codes). Keep `DEPRECATED_KEY_ID` (correct not to raise per spec), `LIBRARY_IS_SOLE_SIGNER` (defense-in-depth if a future API change adds a signature param), and `REPLAY_HALTED` (replace RuntimeError with this in a cleanup pass).
