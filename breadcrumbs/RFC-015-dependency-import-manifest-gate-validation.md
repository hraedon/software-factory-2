---
number: "RFC-015"
title: "Dependency import manifest + gate-level import validation"
severity: high
status: proposed
kind: design
author: principal
date: "2026-05-12"
tags: [gate, runner, implementer, test_author, interface_architect, dep-resolution, stage-2, stage-3, rfc]
related: ["074", "084", "120", "RFC-013"]
---

## Problem

GR-019's inner gate first-attempt pass rate is 64% (7/11). Of the 4 failures, 3 were import errors — the model generated code referencing symbols that don't exist in dependency modules. Example: `Module "certificate_model" has no attribute "parse_certificate"`.

The model already receives full `.pyi` content for each dependency module in the prompt via `locked_dependency_<module>`. But with 3-4 dependency modules, that's hundreds of lines the model must parse linearly. It guesses instead of reads.

## Proposed design

Two complementary mechanisms:

### 1. Dependency import manifest in prompt

AST-walk each locked `.pyi` stub, extract top-level public names (classes, functions, type aliases, enum values). Inject a compact summary into the prompt:

```
## available_dependency_imports
- certificate_model: Certificate, CertificateChain, CertStatus
- cert_parser: parse_pem, parse_der, CertFormat, parse_certificate
```

This gives the model a scannable overview (~15 lines) instead of the full `.pyi` text (~200 lines).

### 2. Gate-level import validation with targeted feedback

New gate check in `pre_gate.py` that runs after ruff (syntactically valid) but before mypy/pytest:
1. Parse the artifact's `from <module> import <symbol>` statements via AST
2. Cross-reference against the pre-computed export map from the `.pyi` stubs
3. On failure, emit specific feedback: `"artifact.py imports 'parse_certificate' from 'certificate_model', but 'certificate_model' only exports: Certificate, CertificateChain, CertStatus"`

The inner gate retry loop already feeds gate output back to the model. This makes the feedback actionable — the model sees exactly which symbol is wrong and what's available.

### Optional: move full `.pyi` content out of prompt, onto disk

Once the manifest + gate are validated, the full `.pyi` content could be written to the attempt directory instead of injected into the prompt. The model reads it via filesystem tools when needed. The gate catches wrong guesses and teaches the correct symbols. This reduces prompt token count significantly but introduces model-behavior risk.

## v1 precedent — CAUTION

V1 built nearly this exact system across at least 7 breadcrumbs:

| V1 BC | Mechanism | V2 equivalent |
|-------|-----------|---------------|
| BC-199 | Interface manifest — AST-walked src/, full signatures + compact index | Dependency import manifest |
| BC-366 | Skeleton symbol manifest — compact one-line-per-symbol in test architect prompt | Same concept, per-role |
| BC-367 | Contract challenge gate — AST-parsed imports vs skeleton exports, 1 retry | Gate-level import validation |
| BC-299 | Import hygiene pass — ruff --fix at emission time | BC-123/124 (already done) |
| BC-180 | Runtime import check gate — importlib.import_module() on every .py | `_run_import_check` (already exists) |
| BC-290 | Reusable import validation utilities | Would be new in pre_gate.py |
| BC-380 | Dependency hygiene gate — reverse check for unused deps | Not proposed |

V1's system worked in three layers: prevention (prompt manifest), emission (auto-generated imports from symbol table), validation (contract challenge gate). V2's proposal has the same shape.

### Where v1 went wrong

The v1 manifest system was built on top of the skeleton plan system (BC-294), which was a complex code-generation pipeline. The manifest, symbol table, contract challenge, and import hygiene pass created deep coupling between the pipeline's structural assumptions and model behavior. As the system grew, the symbol resolution logic became a maintenance burden — every new module type or import pattern needed special handling. The contract challenge gate had to handle submodule imports, re-exports, and type-checking imports (`TYPE_CHECKING` blocks), each requiring bespoke resolution logic.

### Where v2 differs (and where it doesn't)

**Simpler substrate:** V2's dependencies are locked `.pyi` stubs, not a full skeleton plan. The export map is a flat `module → {symbols}` dict, not a nested plan YAML with file-level entries. This is significantly simpler.

**Mechanical gate:** The proposed gate is `ast.walk` + `set` membership. V1's contract challenge gate also resolved submodule imports and cross-file type references — complexity that grew over time.

**Inner gate retry:** V2 has a bounded retry loop (2 retries). V1's BC-367 had 1 retry but the overall retry architecture was less controlled.

**Same risk:** The slippery slope is real. V1 started with "just a symbol manifest" and ended with a full import resolution system. The RFC-015 scope must stay bounded: flat module → symbol set, `from X import Y` checking only, no submodule resolution, no re-export tracking, no `TYPE_CHECKING` handling.

## Proposed scope boundary

**In scope:**
- AST-walk `.pyi` stubs for top-level public names (class, function, type alias, Enum members)
- Inject compact manifest into prompt for implementer and test_author roles
- Gate check: `from <known_module> import <symbol>` where `<symbol>` not in exports
- Feedback includes available symbol list

**Explicitly out of scope (guardrails against v1 scope creep):**
- No submodule import resolution (`from a.b import c`)
- No re-export tracking (`__all__`, re-exports)
- No `TYPE_CHECKING` block handling
- No attribute access checking (`module.symbol` — only `from module import symbol`)
- No import auto-generation (v1's `resolve_cross_file_imports`)
- No reverse check for unused deps (v1's BC-380)
- No manifest file on disk (that's a separate optimization after this is validated)

## Phase placement

Phase 3 (current). The import error pattern is the dominant remaining failure mode. The fix is prompt-side + gate-side, both within existing infrastructure. No new transitions, no new state machine states, no new channel adapters.

## Validation criteria

- GR-020 (clean run) shows inner gate first-attempt rate >= 80% (up from 64%)
- Zero "Module X has no attribute Y" failures across the entire run
- Import validation gate adds < 0.5s per work item
- No new breadcrumbs filed for submodule/re-export edge cases (scope discipline)

---

## Review feedback (2026-05-12, deepseek-v4-pro)

### Summary: accept. The design is sound, the v1 precedent analysis is honest, and the scope boundaries are specific enough to enforce.

### Three implementation notes:

**1. Short-circuit order should be `import_validation → ruff → mypy → pytest`, not `ruff → import_validation → mypy → pytest`.**

The RFC places import validation after ruff on the rationale that the artifact must be syntactically valid first. But: (a) ruff cannot fix a broken import — if the model invents `parse_certificate`, ruff has nothing to do with that line; (b) import validation is a pure AST walk (microseconds), not a subprocess; (c) catching the import error first avoids burning mypy subprocess time on code that can't possibly type-check. Reorder to first position.

**2. Reuse `structural_signature` from `gate.py:782-855` for the export-map extraction.**

That function already extracts `fn:<name>(...)`, `class:<name>`, `enum_member:<Class.name>=<value>`, and `type_alias:<name>=<type>` from `.pyi` files. These are exactly the public names the manifest needs. Add a flat `extract_exports(pyi_content: str) -> set[str]` wrapper that calls it and strips the type prefixes, returning just the names. One function, zero new parsing logic.

**3. Integrate `stub_only_deps` into the manifest.**

Modules known to be stub-only should be marked in the compact summary so the model doesn't attempt runtime calls:

```
## available_dependency_imports
- certificate_model: Certificate, CertificateChain, CertStatus
- cert_parser (stub-only): parse_pem, parse_der, CertFormat
```

This replaces the separate `## stub_only_dependencies` warning block in `render_prompt` — the signal lives where the model is actually looking. (Keep the block as a fallback for models that ignore the manifest.)

**4. `PreGateResult` needs a new `imports_passed` field.**

The inner gate loop in `runner.py` already has a cascade for labeling which gate failed first (`mypy_passed → inner_mypy`, `ruff_passed → inner_ruff`, `pytest_passed → inner_pytest`). An `imports_passed` field and corresponding `GATE_NAME_INNER_IMPORT_VALIDATION` constant follow the same pattern exactly. One extra branch in the cascade, no structural change.

**5. Enforce scope boundaries with assertions, not comments.**

The out-of-scope list on lines 87-93 is the most important section of this RFC. Make it load-bearing: the import validation function should `assert "." not in module_name, "submodule imports not supported"` for `from a.b import c` patterns. It should log-and-skip (not fail) on unsupported patterns like `__all__` or `TYPE_CHECKING`, producing a breadcrumb only if the skip count exceeds a threshold. V1's scope creep was silent — make v2's loud. Use the `GateTimeouts` pattern we just established (a new `GateScope` dataclass with a `strict_imports` boolean, defaulting True) so this can be relaxed later without a code change.

### Risks accepted:

- The "Optional: move `.pyi` content to disk" section (lines 44-46) is correctly deferred. Do not touch it until 3+ golden runs validate the manifest alone.
- The 80% first-attempt rate target is aggressive but reachable — the manifest eliminates the "guess wrong symbol" class entirely. The remaining 20% will be genuine mypy/pytest failures that need model reasoning, not symbol lookup.
- The `.5s performance budget is generous for a pure AST walk. This won't be the bottleneck.

### One meta-note:

The v1 precedent table on lines 52-60 is the strongest section of the RFC. It converts "this feels like a good idea" into "v1 tried this, here's where it broke, here's why v2's substrate is simpler." This pattern (explicit v1 breadcrumb cross-reference with failure analysis) should be mandatory for all future RFCs. Consider promoting it to the RFC template in `breadcrumbs/README.md`.
