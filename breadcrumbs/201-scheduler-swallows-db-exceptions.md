---
number: "201"
title: "Scheduler swallows database exceptions as 'not locked'"
severity: medium
status: proposed
kind: bug
author: self-audit
date: "2026-05-22"
tags: [runner, telemetry]
related: []
---

## Problem

`scheduler.py` has two `except Exception` blocks that silently swallow errors:

1. `_all_dep_specs_locked()` line 288: `except Exception: return False` — database connectivity failures, UUID parse errors, and schema errors are all treated as "dependencies not locked," preventing downstream item creation with no log output.

2. `_downstream_has_field()` line 302: `except Exception: pass` — `get_workflow()` errors silently stop dependency_refs propagation.

A transient Postgres timeout would cause the scheduler to stop creating downstream items with zero visibility.

## Fix

Replace bare `except Exception` with specific exception types (e.g., `SubstrateError`). Log warnings on unexpected errors. Only return `False` / skip on genuine "not found" conditions.
