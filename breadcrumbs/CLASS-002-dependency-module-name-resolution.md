---
number: "CLASS-002"
title: "Dependency Module Name Resolution"
severity: high
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [deps, module-name, cross-module]
related: ["072", "073", "074", "077", "084", "RFC-015"]
---

## Shape

The system needs to know the Python module name for a work item but derives it from an unreliable source (spec title regex, filesystem path, implied convention), causing name mismatches that cascade into import failures or gate errors.

## Systemic cause

Module names are a cross-cutting identifier that must be consistent across populate_work_items, context derivation, gate subprocess execution, dep resolution, and scheduler handoffs. No single canonical source of truth exists; each subsystem re-derives the name from different sources.

## Systemic fix

BC-084 fix: CUSTOM_FIELD_MODULE_NAME stored at populate time. All consumers read from custom_fields first, falling back to regex. RFC-015's import manifest provides additional validation.

## Trigger condition

≥3 instances (current: 5). Already has systemic fix deployed.

## Instances

| BC   | Symptom |
|------|---------|
| 072  | Cross-module imports fail in gate temp directory |
| 073  | ensure_project_venv not invoked when workspace lacks requirements.txt |
| 074  | Cross-module dependency types invisible to implementer and test_author |
| 077  | Runner processes interface_specs without dependency ordering |
| 084  | _extract_module_name_from_spec uses fragile regex |