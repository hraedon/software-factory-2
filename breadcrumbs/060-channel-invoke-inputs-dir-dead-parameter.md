---
number: "060"
title: "Channel.invoke inputs_dir is a dead parameter — protocol contract is misleading"
severity: high
status: proposed
kind: bug
author: adversarial-reviewer
date: "2026-05-08"
tags: [channel, runner, stage-2, stage-4]
related: ["032", "041"]
---

## Summary

The `Channel` protocol declares `inputs_dir: Path` as a required parameter on `invoke()`. `runner.py:202` creates this directory at `workspace_root / work_item_id / "inputs"` and passes it to `channel.invoke()`.

Neither `ClaudeCodeChannel` nor `OpenCodeChannel` reads from `inputs_dir`. Both pass the prompt as a CLI string argument; both use `outputs_dir` as their `cwd` for subprocess execution. The `inputs_dir` is created empty and never populated with files.

The `runner.py:_load_spec` function reads `spec_file` into memory but the result is passed through `PipelineRuntime.spec_content` → `derive_context()` → `render_prompt()` → the `prompt` string argument to `channel.invoke()`. No files are ever written to `inputs_dir`.

## Risk

If a future channel adapter reads files from `inputs_dir` (as the protocol suggests it should), it will find an empty directory. The actual prompt content is in the CLI string argument, which a file-reading channel would ignore. This creates a latent correctness failure that would only surface when the first file-reading channel is added (Phase 3).

The protocol type signature is misleading — it promises a richer interface than what exists, creating a false sense of generality.

## Options

1. Remove `inputs_dir` from the `Channel` protocol and pass prompt content through the existing string argument only. Simplest, most honest.
2. Populate `inputs_dir` with the rendered prompt and any extra_artifacts, making it the single source of input for all channels. More work but completes the protocol contract.
3. Defer to Phase 3 when multi-channel adapters need this decision. Annotate the protocol with `# TODO: resolve in Phase 3` and leave the dead parameter for now.

Option 3 is pragmatic for Phase 2 — the parameter is harmless deadweight, not an active bug. Option 1 or 2 should be decided before Phase 3 channel adapter work begins.
