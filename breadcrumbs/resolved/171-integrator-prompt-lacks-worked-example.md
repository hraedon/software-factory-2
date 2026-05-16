---
number: "171"
title: "Integrator role prompt lacks worked example — assembled_tree import resolution failures"
severity: medium
status: resolved
kind: improvement
author: opus-4-7
date: "2026-05-16"
tags: [prompt, integrator, stage-8, gate, phase-5-exit]
related: ["170", "155", "CLASS-014"]
---

## Problem

The integrator prompt (`src/factory/prompts/integrator.md`) describes the JSON output schema but contains no worked example of a complete `assembled_tree` artifact. Five of seven role prompts include a `## Worked example` section (interface_architect, test_author, cross_family_reviewer, frontier_judge, outcome_verifier). The two without — integrator and implementer — produce the artifacts most likely to fail outer gates.

## Impact

In GR-031, 2/3 integration items failed the outer gate after passing `inner_json_shape`:
- 1 failed `integration_import` — import resolution issues in the assembled module tree
- 1 failed `integration_mypy` — type errors in the assembled code

The JSON is structurally valid (so BC-170's pre-gate passes) but the assembled module boundaries, relative imports, and entry-point references don't compose. The model appears to be guessing at module structure rather than following a concrete example.

This is the swing factor on Phase 5 exit. GR-031 reached 89% lock rate (target 90%); a one-item improvement at the integration stage would clear it. GR-027 hit the same 88%-ish ceiling.

## Files / Lines

- `src/factory/prompts/integrator.md` — no `## Worked example` section
- For comparison: `src/factory/prompts/interface_architect.md:68`, `test_author.md:40`

## Fix

Add a worked example to `integrator.md` showing a complete assembled_tree for a small fixture (e.g., 2 modules + entry point). The example should demonstrate:

1. Module key naming (relative path strings, package vs. flat layout — see resolved BC about flat assembled_tree normalization)
2. Cross-module imports that resolve under the assembled layout
3. `entry_point` pointing to a real symbol in the tree
4. Type annotations consistent with the locked interface (so mypy passes)

The cert-watch-mini fixture used in GR-027 through GR-031 is a good source — the one locked integration item in GR-031 can be the example basis.

## Resolution

Added `## Worked example` section to `src/factory/prompts/integrator.md` with a cert-watch-style 2-module assembly (certificate_model + tls_scan) demonstrating: flat filename keys, cross-module `from certificate_model import Certificate` imports, `entry_point` as dotted callable, `__init__.py` re-exports, and integration_tests exercising both modules.

## Lesson

Prompt-quality bugs surface at the *outer* gate after the *inner* pre-gate has been hardened. CLASS-014 (test coverage gaps) and the prompt-example gap are sibling problems: both let the pipeline pass an artifact that doesn't actually compose. The next prompt added (coherence_reviewer per RFC-024) should include a worked example as a checklist item before the role is wired in.
