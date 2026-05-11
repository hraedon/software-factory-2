---
number: "096"
title: populate_work_items --reset permits arbitrary directory deletion
description: >
  The --reset flag calls shutil.rmtree(workspace_root, ignore_errors=True) where
  workspace_root is read from the config YAML. A malicious or mistyped config can
  point at any filesystem path (e.g., /home/user/projects), causing destructive data
  loss.
severity: high
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [populate, security, data-loss, stage-0]
---

## Proposed fix

Add a guard in populate_work_items.py that refuses to delete paths outside a
known factory tree or containing .. segments. Options:

1. Resolve the path and require it to be under /tmp or the project root.
2. Require an explicit --allow-any-workspace-root flag to opt out.
3. Use a dedicated factory temp prefix and validate against it.

## Affected file

- `populate_work_items.py`
