---
number: "090"
title: Structural semantics gate ignores keyword-only arguments
description: >
  _check_structural_semantics counted only node.args.args + node.args.posonlyargs
  when checking whether a function had parameters. A function with keyword-only
  arguments (e.g., def foo(*, bar: int) -> None) and a valid AC docstring was
  incorrectly rejected as "no parameters and no AC reference."
severity: high
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, interface_spec, structural-semantics, stage-2]
related: ["013"]
---

## Resolution

Added `node.args.kwonlyargs` to the `non_self_params` list in
`_check_structural_semantics`.

## Files changed

- `src/factory/gate.py` — `_check_structural_semantics` parameter enumeration
