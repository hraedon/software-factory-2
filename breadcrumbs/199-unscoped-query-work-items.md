---
number: "199"
title: "Unscoped query_work_items() leaks cross-project data"
severity: medium
status: proposed
kind: bug
author: self-audit
date: "2026-05-22"
tags: [runner, telemetry]
related: []
---

## Problem

`initiative.py` and `review_surface.py` call `sub.query_work_items()` with zero arguments. This returns ALL work items across ALL workflows in the project. While the project is already scoped by the Regista constructor, these calls still fetch every workflow's items when they only need one workflow's items.

In a multi-workflow deployment, `cancel_initiative("abc")` would iterate over items from all workflows (including unrelated ones), and `generate_review_report()` would include items from all workflow versions.

## Fix

Pass `workflow_name=..., workflow_version=...` to scope queries to the intended workflow. Derive these from `FactoryConfig`.
