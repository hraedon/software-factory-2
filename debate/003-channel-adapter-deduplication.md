---
number: "003"
title: "Channel adapter deduplication — extract SubprocessChannel before Phase 3"
author: opencode
date: "2026-05-09"
related: ["BC-061", "BC-060", "RFC-003"]
---

## Context

`ClaudeCodeChannel` (~145 lines) and `OpenCodeChannel` (~146 lines) are ~95% identical. They differ only in:
- CLI binary name (`"claude"` vs `"opencode"`) and flags
- Family derivation (static vs `_derive_family()` from model provider)
- Channel name constant

Everything else — subprocess.run, stdout capture, raw_stdout.txt write, artifact extraction, cannot_proceed JSON detection, error formatting, timeout handling, artifact naming — is duplicated verbatim.

Phase 3 will add 4 more channel adapters (K2 API, GLM, DeepSeek Ollama, Gemini CLI). That multiplies the duplication to 6 copies.

## Problem

Any fix to artifact extraction, error formatting, or output handling requires changes in N places. This is the "string constant gravity" problem from v1, but with control flow instead of strings. The spec §8 explicitly flags "runner complexity" as the most likely failure mode for v2.

## Position

**Extract a `SubprocessChannel` base class before any new channel adapter is written.** Do not add K2/GLM/DeepSeek/Gemini adapters on top of duplicated code.

### Proposed structure

```
channel/
  __init__.py
  base.py          # SubprocessChannel with shared invoke logic
  claude.py        # ClaudeCodeChannel extends base, adds --print --max-turns 1
  opencode.py      # OpenCodeChannel extends base, adds --dangerously-skip-permissions
  registry.py      # _create_channel factory reads config, returns correct subclass
```

`SubprocessChannel` base handles:
- `subprocess.run` with timeout, cwd, input prompt
- `raw_stdout.txt` capture
- `cannot_proceed` JSON detection and file write
- Artifact extraction via `output_extraction.py`
- Error formatting (timeout, non-zero exit, empty output, extraction failure)
- Attempt directory creation

Each subclass provides only:
- `cli_binary()` → str
- `cli_flags(role_config)` → list[str]
- `derive_family(role_config)` → str
- `artifact_extension(role)` → str

### Why this matters now

The next concrete step in v2 is Phase 3 fleet integration. If you write K2/GLM/DeepSeek/Gemini adapters by copy-pasting the existing channel files, you lock in 6× duplication for the lifetime of the project. Refactoring after 6 copies exist is harder and riskier than refactoring after 2.

### BC-061 relationship

BC-061 already identifies this as a high-severity improvement. This debate item adds the position: **do not write another channel adapter until the base class exists.** Treat BC-061 as a hard gate for Phase 3.

## Risks

| Risk | Mitigation |
|---|---|
| Base class over-generalizes and can't handle a future channel's quirks | Keep the base conservative; allow subclasses to override `invoke()` entirely if needed |
| Refactoring breaks existing tests | Both channels have comprehensive test coverage; run full test suite + a golden run before declaring done |
| Delay Phase 3 by 1 session | Acceptable. Phase 3 is fleet integration, not a deadline. Clean foundation > speed |

## Next step

1. Create `src/factory/channel/base.py` with `SubprocessChannel`
2. Refactor `claude_code_channel.py` and `opencode_channel.py` to thin subclasses
3. Update `_create_channel()` in `runner.py` to use registry pattern
4. Move BC-061 to `in_progress`, resolve in 1 session
5. Only then begin K2/GLM/DeepSeek/Gemini adapter stubs
