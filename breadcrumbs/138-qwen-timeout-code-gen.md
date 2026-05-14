---
number: "138"
title: Qwen 3.6-27b operational timeout on test_author and implementer roles (>600s)
severity: medium
status: proposed
kind: bug
author: principal
date: "2026-05-14"
tags: [channel-opencode, tier-c]
related: ["137", "135"]
---

## Problem

Qwen 3.6-27b (via `mac-studio-lms/qwen/qwen3.6-27b` through opencode channel) completed `interface_architect`, `cross_family_reviewer`, and `frontier_judge` roles successfully during the BC-137 capability probe, but **timed out at 600s** on both `test_author` and `implementer` roles. This makes it operationally unfit for code-generation roles at the current timeout configuration.

## Evidence

| Role | Timeout | Result | Elapsed |
|------|---------|--------|---------|
| interface_architect | 300s | success | 195s |
| test_author | 600s | timeout | 600s |
| implementer | 600s | timeout | 600s |
| cross_family_reviewer | 300s | success | 114s |
| frontier_judge | 300s | success | 78s |

The model produces output for review/judge roles (which require only a JSON block) but appears to hang or produce extremely slow output for code-generation roles (which require longer Python files).

## Options

1. **Disqualify from code-gen roles** — restrict Qwen 3.6-27b to review/judge roles only. Simple; no further investigation needed.
2. **Increase timeout** — test at 900s or 1200s to see if it eventually completes. Risk: if it does complete, wall-clock cost may be too high for pipeline economics.
3. **Investigate model-specific prompt shaping** — shorter prompts, fewer examples, or lower temperature may reduce latency. Requires per-model prompt tuning, which the pipeline does not currently support.
4. **Provider fallback** — if other Qwen providers (e.g., direct API) are faster, switch provider while keeping the same model weights.

## Recommendation

Option 1 for now. Qwen 3.6-27b is suitable for `cross_family_reviewer` and `frontier_judge` but not `test_author` or `implementer`. If a future golden run needs a third juror family, Qwen is a viable candidate for that role.
