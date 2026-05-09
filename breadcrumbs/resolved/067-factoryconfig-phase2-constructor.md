---
number: "067"
title: "No FactoryConfig.phase2() constructor — requires manual setattr bypass"
severity: low
status: resolved
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [runner, config]
related: ["032", "058"]
---

## Summary

`FactoryConfig` is a frozen dataclass with Phase 1 defaults (single role, `interface_architect` only). Phase 2 configuration required manually setting static class attributes after construction, which needed `object.__setattr__` bypass since the dataclass is frozen.

## Fix

Added `FactoryConfig.phase2(**overrides)` classmethod that returns a frozen instance pre-populated with Phase 2 roles, type-to-role mapping, and worker roles.