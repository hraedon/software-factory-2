---
number: "137"
title: Model capability evaluation — flawed-spec probe for pipeline role suitability
severity: medium
status: implemented
kind: design
author: principal
date: "2026-05-14"
tags: [runner, channel-opencode, channel-gemini, jury, review]
related: ["136", "135"]
---

## Problem

We have six validated model+provider combinations (K2 via Fireworks, K2 via Ollama, GLM-5.1 via z.ai, GLM-5.1 via Ollama, DeepSeek v4 Pro via Ollama, Gemini Pro) but no systematic way to assess which models are suitable for which pipeline roles. Provider reliability (BC-135) is one axis; model capability is another. A model that reliably produces syntactically correct code may still fail to spot contradictions in a spec, produce shallow reviews, or miss edge cases in test authoring.

## Proposal

Design a single deliberately flawed spec fixture and run each candidate model through each pipeline role against it. The spec should contain known defects that a competent model should catch:

### Candidate spec flaws

1. **Contradictory ACs** — two acceptance criteria that cannot both be satisfied (e.g., "returns None for empty string" and "raises ValueError for empty string")
2. **Underspecified edge case** — an AC that doesn't address an obvious boundary (e.g., integer overflow, unicode digits)
3. **Impossible dependency** — references a function signature that doesn't exist in the provided dependency
4. **Type ambiguity** — return type that could be `int | None` or `Result<int, Error>` depending on interpretation
5. **Missing error case** — spec describes happy path only, silent on failure modes

### Evaluation matrix

For each model × role combination, score:

| Criterion | interface_architect | test_author | implementer | cross_family_reviewer | frontier_judge |
|-----------|--------------------|-------------|-------------|-----------------------|----------------|
| Spots contradictory ACs | Must resolve or reject | N/A | N/A | Must flag | Must flag |
| Handles underspecified edge | Makes explicit | Tests the gap | Defensive impl | Notes the gap | Notes the gap |
| Detects impossible dependency | Rejects or amends | N/A | N/A | Must flag | Must flag |
| Type consistency | Produces coherent .pyi | Tests both paths | Matches .pyi | Validates | Validates |
| Spots missing error cases | Makes explicit | Tests negatives | Defensive impl | Must flag | Must flag |
| Output format compliance | Single code block | Single code block | Single code block | Single code block | Valid JSON |

### Methodology

1. Write the flawed spec as a fixture (e.g., `tests/fixtures/capability-probe/`)
2. Run each model through each role with a fixed prompt (no inner gate, single attempt)
3. Score outputs against the rubric
4. Produce a capability matrix: model × role → pass/fail per criterion

### Models to evaluate

| Model | Provider | Model ID |
|-------|----------|----------|
| Kimi K2.6 | Fireworks | `fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo` |
| Kimi K2.6 | Ollama | `ollama-cloud/kimi-k2.6` |
| GLM-5.1 | z.ai | `zai-coding-plan/glm-5.1` |
| GLM-5.1 | Ollama | `ollama-cloud/glm-5.1` |
| DeepSeek v4 Pro | Ollama | `ollama-cloud/deepseek-v4-pro` |
| Gemini Pro | Google | `pro` (via gemini CLI) |

### Why this matters

- Pipeline reliability depends on model quality, not just channel reliability
- BC-135 showed provider outages; this evaluates the other axis (model reasoning quality)
- BC-136 failover assumes a competent backup; a model that silently accepts contradictory specs is not a reliable fallback
- Jury quality requires models that can spot spec flaws — a juror that rubber-stamps bad specs provides no value
- Results inform default role bindings and failover pair selection

### Deliverable

A report at `.factory/analysis/YYYY-MM-DD-model-capability-evaluation.md` with:
- The flawed spec
- Per-model raw outputs for each role
- The capability matrix
- Recommended role bindings by model
