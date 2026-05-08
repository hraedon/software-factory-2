---
number: "049"
title: "_resume_and_submit has stale default role_name='interface_architect'"
severity: low
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [runner]
related: ["024"]
---

## Problem

`runner.py:328`:

```python
def _resume_and_submit(..., role_name: str = "interface_architect") -> None:
```

BC-024 was resolved — the summary says "Parameterized role_name in runner.py; added test." The caller at line 170 passes `role_name=role_name`, so the default is never exercised in the current code path. But the default remains a footgun: any future caller that omits the parameter will silently produce wrong `ActorMetadata` with `role="interface_architect"` regardless of the actual role.

## Fix

Remove the default value. Make `role_name` a required parameter.
