---
number: "RFC-012"
title: "Gate subprocess credential stripping and sandboxing — defense-in-depth against model output executing in gate context"
severity: medium
status: implemented
kind: design
author: gemini-adversarial-review (filtered)
date: "2026-05-11"
tags: [gate, security, rfc, phase5]
related: ["104"]
---

## Problem

Gate subprocesses (pytest, mypy, ruff) run on AI-generated code inside a `tempfile.TemporaryDirectory`. The subprocess inherits `os.environ`, which includes path variables that could allow a sufficiently malicious model output to read `~/.config/factory/credentials.yaml` or other sensitive files.

The existing import checks and size guards (BC-104) raise the bar, but `__import__('os')` bypasses the AST-level forbidden-module scan since it doesn't appear as an import statement.

## Threat model assessment

The practical risk is low for the current operating environment:

- The factory is a single-user local development tool, not a multi-tenant service.
- The LLM already has code execution capability via channel adapters (opencode, claude code) — gate subprocess output comes from a process that already had full host access during generation.
- Specs are authored by the principal, not arbitrary external users.
- The principal explicitly trusts the model channel.

However, defense-in-depth is still valuable: stripping sensitive environment variables from gate subprocesses is cheap and eliminates a real exfiltration vector regardless of how the model output became malicious.

## Proposed fix

1. **Strip credential-related env vars from gate subprocess environment.** Pass a filtered env dict to subprocess.run in gate.py and pre_gate.py that removes keys matching patterns like `*KEY*`, `*SECRET*`, `*TOKEN*`, `*CREDENTIAL*`, and `DATABASE_URL`. Keep PATH, HOME, PYTHONPATH, and other operational variables.

2. **Gate tool requirements file.** (Deferred) Replace the hardcoded `_GATE_TOOLS` list with a `gate-requirements.txt` that pins versions, enabling reproducible gate environments and audit.

3. **Sandboxed gate execution.** (Deferred, Phase 5+) Run gate subprocesses in a container or seccomp sandbox that restricts filesystem access to the tempdir and blocks network access. This is unnecessary until the factory processes untrusted specs from external sources.

## Why RFC, not active BC

The credential-stripping fix (item 1) is straightforward and low-risk, but it addresses a theoretical vector in a single-user local tool where the model already has host access. Filing as RFC to capture the design decision; the principal can promote it to active if the threat model changes (e.g., processing third-party specs).
