---
number: "205"
title: "workspace.py and dep_resolution.py accept unvalidated paths — path traversal and process group kill risks"
severity: critical
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-25"
tags: [gate, runner, security, CLASS-021]
related: ["111", "188", "096"]
---

## Problem

Multiple path-handling functions accepted unvalidated strings used in path construction, creating path traversal vectors:

1. **workspace.py `attempt_dir()` and `find_resumable_artifact()`**: `work_item_id` (a free-form string from substrate) used directly in path construction. A crafted ID like `../../etc` would escape `work_root_path`.

2. **workspace.py `write_artifact()`**: `artifact_name` used directly in path construction without validation. Current callers generate safe names, but no defense-in-depth guard existed.

3. **dep_resolution.py `_safe_artifact_path()`**: Allowed absolute paths (like `/etc/passwd`), only blocking `..` segments. A crafted `artifact_path` custom field could read arbitrary files on the system when `resolve_dep_refs_for_context()` calls `path.read_text()`.

4. **gate_process.py `_resolve_ref_artifact()`**: Had its own incomplete path validation (blocked `..` in parts but allowed absolute paths), bypassing the shared `_safe_artifact_path` function.

5. **subprocess.py `_terminate()`**: Used `os.killpg(pgid, ...)` without verifying that `pgid == proc.pid`. With `start_new_session=True`, the pgid should always equal the PID, but if a child process changed groups before `getpgid`, `killpg` could signal an unrelated process group.

6. **agent_golden_run.py**: `shutil.rmtree(workspace_root)` used `Path(workspace_root)` without `.resolve()`, meaning a symlink in the path could redirect deletion. Also, `log_prefix` was used in path construction without sanitization. Three file descriptors were leaked in `_launch_processes()`.

7. **decomposer.py FR-ID regex**: `FR-\d+` pattern only matched numeric FR IDs (like `FR-01`), not alpha-numeric ones (like `FR-CERT-01`). Dependencies and ACs referencing such IDs were silently dropped.

8. **decomposer_model.py**: Duplicate `import yaml` — module-level import on line 10 and redundant try/except inside `_load_spec_text`.

9. **placement.py**: Used `__import__("time").time()` instead of a top-level `import time`.

### Why this isn't the previous fix recurring

BC-111 added `_safe_artifact_path` but only blocked `..` paths, leaving absolute paths as an open vector. BC-188 fixed integration gate path traversal for `assembled_tree` filenames but didn't address the wider pattern in dependency resolution. BC-096 fixed `populate_work_items --reset` directory deletion safety but `agent_golden_run.py` still had unprotected `shutil.rmtree` calls. Each prior fix addressed a specific manifestation without establishing the invariant that all paths entering the workspace/filesystem must be validated against the workspace root.

## Fix

1. **workspace.py**: Added `_validate_path_component()` that rejects strings containing `/`, `\`, or `..`. Applied to `work_item_id` in `attempt_dir()`, `find_resumable_artifact()`, and `list_attempt_dirs()`, and to `artifact_name` in `write_artifact()`. Added `is_symlink()` check in `find_resumable_artifact()`.

2. **dep_resolution.py**: `_safe_artifact_path()` now also rejects absolute paths, in addition to `..` segments.

3. **gate_process.py**: `_resolve_ref_artifact()` now uses `_safe_artifact_path()` from dep_resolution instead of its own inline validation.

4. **subprocess.py `_terminate()`**: Added `pgid == proc.pid` guard before using `killpg`. If pgid doesn't match, falls back to `proc.terminate()`/`proc.kill()`.

5. **agent_golden_run.py**: Added `_safe_rmtree()` that resolves paths and refuses to delete outside `/tmp/`. Replaced all `shutil.rmtree()` calls. Added `log_prefix` sanitization. Fixed FD leak in `_launch_processes()`.

6. **decomposer.py**: Changed `FR-\d+` patterns to `FR-(?:[A-Z]+-)?\d+`. Merged two `_parse_acs_from_md` regex loops into one unified pattern.

7. **decomposer_model.py**: Removed redundant `import yaml` try/except block.

8. **placement.py**: Replaced `__import__("time").time()` with top-level `import time`.

9. **tests/test_path_traversal.py**: Extended from 8 tests to 14, adding absolute-path rejection, workspace path validation, and artifact name validation tests.