---
number: "230"
title: "agent_golden_run.py exits 1 on successful runs — cleanup refuses to rmtree the non-/tmp logs dir"
severity: low
status: proposed
kind: bug
author: claude-opus (GR-056/057 review session)
date: "2026-05-31"
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
