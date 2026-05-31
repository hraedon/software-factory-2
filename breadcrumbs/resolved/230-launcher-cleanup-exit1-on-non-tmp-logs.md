---
number: "230"
title: "agent_golden_run.py exits 1 on successful runs — cleanup refuses to rmtree the non-/tmp logs dir"
severity: low
status: resolved
kind: bug
author: claude-opus (GR-056/057 review session)
date: "2026-05-31"
resolved: "2026-05-31"
tags: [runner, golden-run, dev-ergonomics]
related: []
---

## Symptom

Both GR-056 and GR-057 ran to completion (pipeline drained, `verify_passed:
True`, telemetry emitted) yet `scripts/agent_golden_run.py` exited **1**, with:

```
[FATAL] Refusing to remove logs outside /tmp/: /projects/software-factory-2/.factory/logs/golden-run-0NN-config
```

`_safe_rmtree` (BC-205 safety guard, `/tmp/`-only) correctly refuses to delete
the logs dir — but the logs dir is `.factory/logs/...` *inside the repo*, not
under `/tmp/`. So the guard fires on every run and the launcher reports failure
on success.

## Impact

Low but real: a successful run looks failed to any caller checking the exit code
(including an agent monitoring the run — it triggered a "failed" notification both
times). Erodes trust in the run signal and risks masking a *real* non-zero exit.

## Fix (directions)

The launcher should not route the repo-internal logs dir through the `/tmp/`-only
`_safe_rmtree`. Options: (a) don't clean `.factory/logs/...` at all (it's
version-controlled run history, arguably keep it); (b) skip/relocate the cleanup
for non-`/tmp` paths instead of FATAL-ing; (c) treat "refused to clean a
non-tmp path" as a warning, not a fatal non-zero exit. The run already succeeded
by that point — cleanup failure should not flip the exit code.

## Why this isn't the previous fix recurring

Shares no tags requiring the recurrence subsection. Related in spirit to BC-205
(`_safe_rmtree` path-traversal hardening) but the opposite failure: there the
guard was too loose; here it is correctly strict but applied to a path that
shouldn't be cleaned at all, turning a successful run into a non-zero exit.

## Fix

**Root cause (confirmed):** `_cleanup_offered` called `_safe_rmtree(resolved_log_dir,
"remove logs")` unconditionally. `resolved_log_dir` is `.factory/logs/golden-run-NNN-config`
inside the repo (resolved from `_log_dir_for(log_prefix)`). The BC-205 guard in
`_safe_rmtree` correctly rejects paths outside `/tmp/` via `_fatal()`, which calls
`sys.exit(1)`. This fires on every successful run because the log dir is always
repo-internal.

**Fix chosen (option b — skip non-`/tmp/` log dirs with a warning):**
In `_cleanup_offered` (`scripts/agent_golden_run.py`), added a pre-check before
calling `_safe_rmtree` on the resolved log dir: if the path does not start with
`/tmp/`, emit a `[WARN]` and skip it instead of invoking `_safe_rmtree`. This
preserves the BC-205 safety invariant (the guard in `_safe_rmtree` is unchanged
and still fatals if called directly on a non-`/tmp/` path) while ensuring that
repo-internal log dirs — which are version-controlled run history and should not
be auto-deleted — silently survive cleanup without flipping the exit code.

**Why not option (a) — don't clean log dirs at all:** Option (a) would require
removing `_safe_rmtree` for log dirs entirely, which would also break the case
where `log_dir` is legitimately under `/tmp/` (e.g. in tests). Option (b) is more
targeted: it skips only non-`/tmp/` paths, preserving cleanup for any future case
where a run stores logs under `/tmp/`.

**Tests added** (`tests/test_agent_golden_run.py`):
- `test_cleanup_skips_non_tmp_log_dir_with_warning` — verifies a `[WARN]` is
  emitted when log dir is outside `/tmp/` and no `SystemExit` is raised.
- `test_cleanup_non_tmp_log_dir_does_not_exit_nonzero` — core regression: confirms
  no `SystemExit` with a non-`/tmp/` log dir.
- `test_safe_rmtree_still_rejects_non_tmp` — confirms the BC-205 guard in
  `_safe_rmtree` itself still `_fatal`s on non-`/tmp/` paths.
- `test_safe_rmtree_accepts_tmp_paths` — confirms `/tmp/` paths are still cleaned.
