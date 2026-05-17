---
number: "187"
title: "Pipeline subprocess writes fixture artifacts into repo root; first surfaced in GR-038 integration/outcome stages"
severity: medium
status: proposed
kind: bug
author: claude
date: "2026-05-17"
tags: [gate, integration, outcome_verification, subprocess, cwd, workspace, GR-038]
related: ["170", "141"]
---

## Symptom

After GR-038 completed, four Python files appeared as untracked artifacts in the repo root:

```
/projects/software-factory-2/certificate_model.py  (1280 bytes, mtime 2026-05-17 18:56)
/projects/software-factory-2/database_layer.py     (1906 bytes, mtime 18:56)
/projects/software-factory-2/interface.py          (2753 bytes, mtime 18:56)
/projects/software-factory-2/test_interface.py     (3105 bytes, mtime 18:56)
```

These are cert-watch domain artifacts — certificate model, database layer, alert interface, and interface tests. They match the cert-watch fixture at `tests/fixtures/cert-watch/` thematically (the same AC references appear) but are not copies of those fixture files; they are model-generated artifacts that should have stayed inside the ephemeral `/tmp/sf2-golden-038/` workspace.

## Root cause

**Primary vector: `invocation_cwd` set to repo root in run config.**

`SubprocessChannel.invoke()` (`src/factory/subprocess_channel.py`, lines 87–89) determines the subprocess working directory:

```python
effective_cwd = str(outputs_dir)          # defaults to attempt dir under /tmp
if self._config.invocation_cwd is not None:
    effective_cwd = str(self._config.invocation_cwd)  # overridden by config
```

All GR-027-onward configs set `invocation_cwd: /projects/software-factory-2` (originally introduced in BC-141 to fix opencode's project-context requirement). This causes every model invocation subprocess — including opencode — to execute with the repo root as its cwd.

When opencode (or another agentic model channel) runs with `cwd=/projects/software-factory-2`, it may write intermediate or output files into that directory rather than solely returning content on stdout. At 18:56 during GR-038, work item `7f4dd85e-a8fc-47ed-a0f3-d9dbb4809176` (the cert-watch `interface.py` implementer task) exhausted its inner-gate retries and was submitted — the model had been invoked repeatedly with the repo root as cwd, and it wrote the four cert-watch source files there.

**Contributing vector: ruff subprocess calls in `gate.py` lack `cwd=` argument.**

`_run_ruff()` in `src/factory/gate.py` at lines 802–821 invokes `subprocess.run(["ruff", ...])` without a `cwd=` argument three times. This causes ruff to inherit whatever cwd the gate process has, which may also be the repo root. While ruff does not ordinarily write files (it operates on the path explicitly given), this is still a latent exposure point.

## GR-038 timeline at 18:56

- 18:51:56 — runner claimed WI `7f4dd85e` (cert-watch `interface.py` implementer, attempt 1)
- 18:53:14 — inner_mypy failed, retry 0
- 18:54:12 — inner_mypy failed, retry 1
- 18:55:02 — inner_mypy failed, retry 2
- 18:56:36 — `inner_gate_exhausted_retries` (max_retries=3); WI submitted
- Files appeared at mtime 18:56 — consistent with the final model invocation(s) during retry 2–3

The `unsupported_import_pattern` warnings in the runner log for `certificate_model` and `database_layer` (lines 58–65) confirm the model was generating cert-watch domain code and resolving those modules relative to its cwd (repo root), not the tmpdir.

## Why GR-038 was the first visible instance

GR-038 was the first run in which the cert-watch fixture work items reached the inner-gate retry loop at sufficient depth (N=4 concurrent, retry limit 3) to trigger the file-write behavior. Earlier GRs either succeeded on the first attempt or did not reach this work item type.

## Reproduction

1. Run the factory with a cert-watch work item targeting the `interface.py` implementer role.
2. Configure `invocation_cwd: /projects/software-factory-2` (as all GR-027+ configs do).
3. Arrange for the inner gate to fail at least once so the model retries.
4. Observe whether `certificate_model.py`, `database_layer.py`, `interface.py`, or `test_interface.py` appear in the repo root.

## Fix options

1. **Preferred — isolate `invocation_cwd` from the model's writable cwd.** Pass `invocation_cwd` only for PATH/project-context lookup, and set the actual subprocess `cwd` to the attempt's `outputs_dir` (or a dedicated sandbox dir). One approach: keep `invocation_cwd` for environment initialization but override `cwd` back to a temp sandbox in `SubprocessChannel.invoke()`.

2. **Alternative — use opencode's `--project-dir` flag (if available).** If opencode supports a `--project-dir` option to specify project context without changing cwd, use that instead of `invocation_cwd`.

3. **Defense-in-depth — gitignore the generated names.** Add known output filenames (`certificate_model.py`, `database_layer.py`, etc.) or a pattern (`.factory/` artifacts) to `.gitignore`. This does not prevent the leak, only prevents accidental commit.

4. **Add `cwd=` to ruff subprocess calls in `gate.py` lines 802–821.** These three `subprocess.run()` calls lack a `cwd=` argument; they should explicitly set `cwd=tmpdir` (the enclosing `tempfile.TemporaryDirectory` block already constructs `tmpdir`).

## Acceptance criteria

- No untracked `.py` files appear in the repo root after a full golden run.
- The model subprocess's writable cwd is isolated to an ephemeral temp directory.
- All three ruff `subprocess.run()` calls in `gate.py` include an explicit `cwd=` argument.

## Touched surface (estimated)

- `src/factory/subprocess_channel.py` — lines 87–89 (`effective_cwd` logic)
- `src/factory/gate.py` — lines 802, 809, 816 (ruff subprocess calls without `cwd=`)
- `.factory/golden-runs/golden-run-*-config.yaml` — `invocation_cwd` field
- `src/factory/config.py` — `invocation_cwd` field definition (line 134)

## Severity rationale

**Medium.** The files are leaked artifacts, not corrupted source. They are immediately visible as untracked, are not committed automatically, and do not break the pipeline's correctness — the correct artifact is still captured in the attempt dir under `/tmp`. However, they pollute the repo root, could confuse subsequent mypy/pytest runs if they happen to be on the Python path, and represent a process-isolation failure that could escalate to data corruption in a more adversarial environment.

## CLASS-008 membership

This is an instance of CLASS-008 (Gate Subprocess Execution and Environment Handling): a subprocess runs with wrong cwd, causing unwanted side effects. Adding as instance #12 to that class's table.
