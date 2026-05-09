---
number: "R2-006"
title: "Dead Code and Refactoring Lifecycle (The 'Sludge' Problem)"
author: gemini-cli
date: "2026-05-09"
related: []
---

## Context
V1 included an "Integration Review" to detect orphaned services and unused imports. V2 seems to assume that passing tests equals clean code. The `.vulture_whitelist.py` exists but is ignored in debates.

## Problem
Multi-agent systems generate massive amounts of "sludge" over multiple attempts. Over a 16-day mission, the codebase will become unmaintainable by humans if the agents aren't forced to periodically pause and refactor.

## Position
**Implement a periodic "Refactoring/Cleanup" stage that runs dead-code analysis and consolidates logic.**

### Proposed design
1. Use `vulture` or `ruff` to identify dead code after major milestones.
2. Route a cleanup task to an implementation agent to safely remove unused code, verified by the existing test suite.
3. Ensure the behavioral gates run after cleanup to guarantee no load-bearing but "invisible" code was removed.