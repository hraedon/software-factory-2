---
number: "188"
title: "Integration gate writes LLM-controlled filenames without sandboxing — path traversal and arbitrary code execution"
severity: critical
status: implemented
kind: bug
author: claude
date: "2026-05-18"
tags: [security, gate, integration, channel-trust, phase-3-blocker]
related: ["177"]
---

# BC-188 — `evaluate_integration` is unsandboxed against the model's `assembled_tree`

## Symptom (latent)

In `src/factory/gate.py` (the integration-import block, ≈lines 1119–1132 in current main), the integrator's JSON `assembled_tree: { filename: source, ... }` is materialized into a temp directory and then executed via pytest. Filenames are model-controlled. Source bodies are model-controlled.

```python
with tempfile.TemporaryDirectory(prefix="sf2_integration_") as tmpdir:
    tmp_path = Path(tmpdir)
    for filename, source in assembled_tree.items():
        dest = tmp_path / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_text(str(source))
        ...
```

There is no `dest.resolve().is_relative_to(tmp_path.resolve())` guard before writing. A `filename` of `../../../etc/foo` (or any other traversal) writes outside the temp dir. A `filename` whose path coincides with a Python module on `sys.path` shadows that module when pytest runs the assembled tree.

`tests/test_path_traversal.py` covers `dep_resolution._safe_artifact_path`. It does not cover the integration gate.

## Why this matters

- **Today:** runs are local on the principal's box; the practical risk is data corruption (overwriting source files in `/projects/software-factory-2` if cwd differs) rather than exploitation.
- **Phase 3 / fleet integration:** channel adapters multiply. Each new channel is a fresh point at which a misconfigured or compromised model produces hostile JSON. Today's "trusted output" assumption is the wrong default the moment a non-Anthropic channel is in the pool.
- The integration gate already executes the assembled tree (`gate.py:1160+` runs pytest against it). Path traversal + arbitrary execution = RCE-equivalent in the sf2 process.

## Proposed fix

1. After computing `dest = tmp_path / filename`, require `dest.resolve().is_relative_to(tmp_path.resolve())`. On violation, return `GateResult(passed=False, ...)` with diagnostic kind `integration_unsafe_path`. Do not write the file.
2. Reject absolute paths in `filename` outright.
3. Reject any filename containing `..` segments (defense in depth).
4. Add a regression test mirroring `tests/test_path_traversal.py`'s shape against the integration gate: a fixture `assembled_tree` with `../escape.py` must fail the gate without writing.

## Phase-3 implications

Adopt a default-adversarial trust model for channel outputs by Phase 3 start. This BC is one instance; cf. BC-EEE (prompt-injection from upstream stages — see new BC for `extra_artifacts` duplication) and the broader RFC-034 (channel adapter trust boundaries) once filed.

## Acceptance criteria

1. Test: hostile `assembled_tree` filename rejected before any disk write.
2. Test: hostile `assembled_tree` source containing `import os; os.system(...)` runs only inside the gate's pytest invocation (existing behavior) and never modifies host outside `tmp_path`.
3. `diagnostic_kind="integration_unsafe_path"` is emitted on rejection and visible in telemetry.

## Resolution

Fixed in gate.py `evaluate_integration`: assembled_tree filenames validated with four checks — non-string rejection, absolute-path rejection, `..` segment rejection, and `resolve().is_relative_to()` sandbox containment. `diagnostic_kind="integration_unsafe_path"` emitted on rejection. 4 regression tests added to `test_integration_gates.py::TestIntegrationGatePathTraversal`.
