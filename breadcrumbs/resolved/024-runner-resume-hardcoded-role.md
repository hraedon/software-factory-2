---
number: "024"
title: "_resume_and_submit hardcodes role to interface_architect"
severity: high
status: implemented
kind: bug
author: test-audit
date: "2026-05-07"
tags: [runner, stage-1, resume]
resolution: parameterized-role-name
---

## Background

`_resume_and_submit` in `runner.py` hardcoded the actor metadata role:

```python
actor_metadata = ActorMetadata(
    role="interface_architect",  # HARDCODED
    channel=manifest.channel or channel.name,
    ...
).to_dict()
```

When resuming from a prior attempt, the `submit` transition event would always claim the actor's role was `interface_architect`, regardless of what role actually produced the artifact. This corrupts telemetry for any non-interface-architect role (e.g., `test_author` in Phase 2).

## Fix applied (2026-05-07)

Added a `role_name: str` parameter to `_resume_and_submit` with a default of `"interface_architect"` for backward compatibility. The caller in `process_work_item` (line 148) now passes `role_name=role_name`, propagating the actual role from the worker loop.

Added `test_resume_preserves_actor_metadata` in `test_runner_resume.py` to verify that a resumed artifact's original channel/family/context_hash are preserved, and that the role_name parameter is honored.
