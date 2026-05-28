---
number: "197"
title: "Dead code with broken regista API: store_spec_hash and load_spec_hash"
severity: low
status: proposed
kind: bug
author: self-audit
date: "2026-05-22"
tags: [dead-code]
related: []
---

## Problem

`spec_hash.py` functions `store_spec_hash()` and `load_spec_hash()` call non-existent regista methods: `query_work_items(workflow_run_id=..., state=..., limit=...)` and `update_work_item(...)`. These parameters don't exist in the regista API.

These functions are dead code — never called from production code or test code. Only `compute_spec_hash` and `compare_spec_hashes` (the pure functions) are used and tested.

## Fix

Remove `store_spec_hash` and `load_spec_hash`. If spec-hash persistence is needed later, implement it against the actual regista API.
