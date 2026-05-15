---
number: "CLASS-012"
title: "Single Source of Truth / String Constant Gravity"
severity: high
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [constants, defaults, config, single-source-of-truth]
related: ["056", "057", "065", "066", "069", "080", "151", "156", "157", "159"]
---

## Shape

Identifier strings, default values, config keys, or dispatch rules are duplicated across multiple files. When one copy is updated, others are not, causing silent divergence.

## Systemic cause

The codebase grew by copy-paste-modify rather than shared-constant extraction. There is no architectural rule enforcing that all identifiers live in constants.py or FactoryConfig. Default values are easy to inline and hard to detect when they drift.

## Systemic fix

BC-056 convention: all defaults in FactoryConfig, all identifier strings in constants.py. Vulture dead-code audit in CI. AGENTS.md mandates this rule.

## Trigger condition

≥5 instances (current: 10). Systemic fix deployed and enforced by CI.

## Instances

| BC   | Symptom |
|------|---------|
| 056  | No single-source-of-truth rule for defaults |
| 057  | Dead code audit — no CI enforcement |
| 065  | Scattered hardcoded page_size values |
| 066  | cannot_proceed string overloaded as state and transition name |
| 069  | Gate names are bare string literals |
| 080  | Router target_role is dead output |
| 151  | Integration success reports wrong gate name |
| 156  | _find_locked_impl uses hardcoded page_size=200 |
| 157  | Scheduler propagate_fields uses hardcoded index 0 |
| 159  | _resolve_extra_env called twice with same arguments |