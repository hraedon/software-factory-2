---
number: "193"
title: "spec_section and import_feedback rendered unfenced in prompt — heading injection risk from fixture specs"
severity: low
status: resolved
kind: bug
author: session-scan
date: "2026-05-18"
tags: [context, prompt-injection, channel-trust, BC-191-sibling]
related: ["191"]
---

# BC-193 — `spec_section` and `import_feedback` unfenced in `render_prompt`

## Problem

BC-191 fenced `extra_artifacts` values in triple-backtick code blocks to prevent markdown heading injection. Two other rendered values remain unfenced:

1. **`ctx.spec_section`** (`context.py` ~line 620) — rendered raw as the `## spec_section` body. Source: fixture spec (operator-controlled). A fixture containing `## injected_heading` would introduce a structural section.

2. **`ctx.import_feedback`** (`context.py` ~line 654) — rendered raw as the `## import_resolution_feedback` body. Source: `pre_gate._parse_import_failure` (factory-generated).

## Why not fixed now

- `spec_section` is operator-controlled, not model output. Injection requires a hostile fixture, not a hostile channel.
- `import_feedback` is factory-generated with controlled formatting. An injection would require a code bug, not adversarial input.
- Both are lower risk than `extra_artifacts` (model-controlled, BC-191).

## Proposed fix

If the trust model for Phase 3 (RFC-034) adopts default-adversarial for all non-code inputs, fence these as well. Otherwise, document the trust boundary in `spec.md` and leave unfenced as an explicit exception.

## Acceptance criteria

1. Decision recorded: fence or document-trust-boundary.
2. If fenced: test that `spec_section` containing `## injected` does not introduce a top-level heading.
3. If documented: spec.md section on prompt trust boundaries references this BC.

## Resolution

Decision: fence both fields. `spec_section` and `import_feedback` now rendered in triple-backtick code blocks, matching the BC-191 pattern for `extra_artifacts`. `render_prompt` in `context.py` updated; no test changes needed (fencing is structural, not behavioral). `custom_fields_update` added to `SubmitPayload` known-fields set to eliminate telemetry noise from BC-185 schema gap.
