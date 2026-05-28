---
number: "RFC-015"
title: "Dependency import manifest + gate-level import validation"
severity: high
status: implemented
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

**Simpler regista:** V2's dependencies are locked `.pyi` stubs, not a full skeleton plan. The export map is a flat `module → {symbols}` dict, not a nested plan YAML with file-level entries. This is significantly simpler.

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

The v1 precedent table on lines 52-60 is the strongest section of the RFC. It converts "this feels like a good idea" into "v1 tried this, here's where it broke, here's why v2's regista is simpler." This pattern (explicit v1 breadcrumb cross-reference with failure analysis) should be mandatory for all future RFCs. Consider promoting it to the RFC template in `breadcrumbs/README.md`.

---

## Review feedback (2026-05-12, opus-4-7, principal review)

### Summary: accept. Deepseek's five notes all land. Five additional items below; treat them as implementation requirements, not suggestions.

### 1. Name the new gate so it does not collide with the existing one — and update the cascade explicitly

`constants.py:94` already defines `GATE_NAME_INNER_IMPORT` and `runner.py:512` already routes to it. That is the **runtime** `importlib.import_module()` check inherited from v1's BC-180. The RFC proposes a different check: **AST-only export-set membership**, which is cheaper, earlier, and catches a different failure (a wrong symbol name, before runtime import would even resolve).

Implementation directives:

- Add constant `GATE_NAME_INNER_IMPORT_SYMBOLS = "inner_import_symbols"` in `constants.py`. Do **not** rename `GATE_NAME_INNER_IMPORT`.
- In `runner.py:507-518`, the cascade is currently: `mypy_passed → ruff_passed → import_passed → collect_passed → pytest_passed → else pytest`. Insert `imports_symbols_passed` as the **first** check in the cascade (label `GATE_NAME_INNER_IMPORT_SYMBOLS`). Final order: `import_symbols → mypy → ruff → import (runtime) → collect → pytest`.
- The RFC body (around line 37) currently says "after ruff but before mypy/pytest." Replace that sentence to reflect the new ordering: "first in the cascade, before any subprocess gate."
- Add a one-line comment at the top of the new validator distinguishing it from the existing runtime check: `# AST-only symbol-membership check. Complements (does not replace) the runtime importlib check at GATE_NAME_INNER_IMPORT.`

### 2. Tighten the validation criterion — the 80% target alone is fragile

GR-019's 64% was 7/11 with one model-timeout item excluded. On N=11, the difference between "80%" and "73%" is one work item. Rewrite the validation criteria block (lines 99-104) as:

**Primary criterion (must hold):** Zero "Module X has no attribute Y" failures across the entire golden run. This is the actual claim the RFC makes.

**Secondary criterion (informational):** Inner gate first-attempt rate ≥ 80% sustained across **two consecutive** golden runs (GR-020 and GR-021). One run is noise; two is signal.

**Tertiary criterion:** Symbol-validation gate adds < 50ms per artifact (was 500ms; an AST walk on a single file is microseconds, and the export-map extraction is done once per work item and cached).

Do not declare success on a single run.

### 3. Report ALL mismatches per pass, not just the first

The example feedback on line 40 shows a single wrong import. In practice a confused model emits 2-4 bad imports in one artifact. If the gate bails on the first, the inner retry loop ping-pongs: fix one → surface next → fix one → surface next, burning the retry budget on a problem that could be reported once.

Implementation directives:

- The validator function (working name `validate_artifact_imports`) must walk **every** `ast.ImportFrom` node before returning, collect all mismatches into a list, and report all of them.
- Feedback shape (one block per offending module, sorted by module name for determinism):

```
artifact.py:12: 'certificate_model' imports the following unknown symbols: parse_certificate, build_chain
  available in certificate_model: Certificate, CertificateChain, CertStatus, verify

artifact.py:18: 'cert_parser' imports the following unknown symbols: parse_x509
  available in cert_parser: parse_pem, parse_der, CertFormat
```

- Line numbers come from `ast.ImportFrom.lineno`. Always include them — the model uses line numbers to locate fixes.
- The "available in" list must be alphabetically sorted (determinism for tests).
- If multiple bad symbols come from the same module on the same line (`from m import a, b, c`), group them on one line as shown.

### 4. Promote `stub_only_deps` integration from "implementation note" to a primary design element

Deepseek flagged this but framed it as note 3. It is actually the highest-leverage piece of the RFC: it collapses two separate prompt signals (the manifest and the `## stub_only_dependencies` warning block) into one place the model is already reading.

Implementation directives:

- Modify the manifest emitter in the prompt-rendering code (search for `stub_only_deps` consumers, currently in `runner.py:545` and rendered in `render_prompt`). The compact manifest line for a stub-only module must be:
  - `- module_name (stub-only): Sym1, Sym2, Sym3`
- Keep the existing `## stub_only_dependencies` block in `render_prompt` as a fallback. Do **not** remove it in this RFC. (Removal is a separate change after 2 GRs prove the inline tag is read.)
- Add a test in `tests/test_pre_gate.py` (or a new `tests/test_import_manifest.py`) that asserts the `(stub-only)` tag appears in the rendered prompt when `stub_only_deps` contains the module.

### 5. Scope-boundary enforcement — be specific about what "loud failure" looks like

Deepseek note 5 says "log-and-skip, breadcrumb if skip count > threshold." Make this concrete so it is not interpreted as "log a warning and forget."

Implementation directives:

- For every unsupported pattern encountered during validation, emit a structured log line on `factory.pre_gate` logger at WARNING level: `unsupported_import_pattern pattern=<name> module=<module> file=<artifact_path>`. Patterns to detect: `submodule_dotted` (`from a.b import c`), `relative` (`from . import x`), `star` (`from x import *`), `type_checking_block` (any `ImportFrom` inside an `if TYPE_CHECKING:` block — detect by walking parents).
- Counter: increment a per-run counter in the runner (existing `telemetry` dict pattern). Field name: `import_validation_skipped_patterns`.
- Threshold for breadcrumb: if `import_validation_skipped_patterns > 5` in a single golden run, the nanny prints a "scope creep warning" line at end-of-run pointing at this RFC. Do **not** auto-file a breadcrumb (that is a 2026 problem); the warning is enough.
- The `GateScope` dataclass deepseek proposed: define it in `pre_gate.py` with one field `strict_imports: bool = True`. Wire it through `PreGateResult` construction. Do not add other fields speculatively.

### 6. Reuse `structural_signature`, but adapt the output shape

Deepseek note 2 is correct that `gate.py:782` already does the parsing. Specifics for the implementer:

- Add `extract_exports(pyi_content: str) -> set[str]` in `gate.py` immediately after `structural_signature` (so they live together).
- Implementation: call `structural_signature(pyi_content)` to get the list of typed tokens (`fn:foo(...)`, `class:Bar`, `enum_member:Status.OK=1`, `type_alias:Id=int`). Strip the prefix and any trailing `(...)` / `=...`. Return the bare names as a `set[str]`.
- For `enum_member:Status.OK=1`, the **exported name** is `Status` (the class), not `Status.OK`. The member is accessed via attribute, not import. Dedupe.
- Add a unit test in `tests/test_gate.py` (or wherever `structural_signature` is tested): assert `extract_exports` on a fixture `.pyi` with class, function, enum, and type-alias yields the expected flat set.

### 7. Caching — do not re-parse `.pyi` per attempt

The export map for a work item's dependencies is constant across retry attempts (dependencies are locked). Re-parsing on each attempt is wasted work.

Implementation directives:

- Build the export map **once** when the runner assembles the dependency context for a work item. Pass it into `PreGateResult` / the validator alongside `stub_only_deps`.
- The cache key is the work-item ID, not the artifact path. Do not cache across work items (deps differ).
- Do **not** add an LRU or a global cache. One dict, scoped to the inner-gate loop for a single work item, is all that is needed.

### 8. Test list (mandatory before merge)

The implementer must add the following tests. List is exhaustive; if a test is judged unnecessary, justify in the PR.

In `tests/test_pre_gate.py` (or new `tests/test_import_validation.py`):

1. `test_import_validation_happy_path` — artifact imports only known symbols, gate passes.
2. `test_import_validation_unknown_symbol_single` — one bad import, feedback contains module, symbol, available list, and line number.
3. `test_import_validation_unknown_symbol_multiple` — three bad imports across two modules, **all three** reported in one feedback block, alphabetically sorted per module.
4. `test_import_validation_grouped_on_one_line` — `from m import a, b, c` where b and c are unknown — reported as one line, both names listed.
5. `test_import_validation_skips_unknown_module` — `from third_party import x` where `third_party` is not in the export map — must NOT fail (only validate modules we have an export map for).
6. `test_import_validation_skips_submodule_import` — `from a.b import c` increments `submodule_dotted` skip counter, does not fail.
7. `test_import_validation_skips_type_checking_block` — import inside `if TYPE_CHECKING:` increments `type_checking_block` counter, does not fail.
8. `test_import_validation_skips_star_import` — `from m import *` increments `star` counter, does not fail.
9. `test_import_validation_skips_relative_import` — `from . import x` increments `relative` counter, does not fail.
10. `test_extract_exports_strips_type_prefixes` — `extract_exports` on a known fixture returns the expected flat set with no `fn:` / `class:` / `enum_member:` / `type_alias:` prefixes.
11. `test_extract_exports_enum_members_collapse_to_class` — `.pyi` with `class Status(Enum): OK = 1; ERR = 2` yields `{"Status"}`, not `{"Status.OK", "Status.ERR"}`.
12. `test_manifest_includes_stub_only_tag` — rendered prompt for a stub-only module contains `(stub-only)` on the manifest line.
13. `test_manifest_excludes_stub_only_tag_for_runtime_module` — non-stub module manifest line has no `(stub-only)` tag.
14. `test_pregate_cascade_import_symbols_first` — when both symbol-mismatch and mypy error are present, gate reports `inner_import_symbols`, not `inner_mypy`.
15. `test_export_map_cached_per_work_item` — given two attempts on the same work item, `extract_exports` is called exactly once per dependency (mock and count calls).

### 9. Out-of-scope reminder (re-statement for the implementer)

The implementer (glm or kimi) MUST NOT add any of the following, even if it seems trivial:

- Resolution of `from a.b import c` (submodule). Skip and count.
- Tracking of `__all__`. The export map is everything `structural_signature` finds, period.
- Re-export handling (`from x import y` then someone imports `y` from this module). Not handled.
- `TYPE_CHECKING` block resolution. Skip and count.
- Attribute access checking (`module.symbol` style usage in the artifact body). Out of scope; only `ImportFrom` nodes.
- Auto-fix of bad imports. The gate **reports**; the model fixes on retry.
- Reverse "unused dependency" check (v1 BC-380). Not in this RFC.

If any of these seem necessary mid-implementation, **stop and file a follow-up RFC**. Do not extend scope inside this one.

### 10. PR shape

One PR, in this order of files (so reviewers can read top-down):

1. `src/factory/constants.py` — add `GATE_NAME_INNER_IMPORT_SYMBOLS`.
2. `src/factory/gate.py` — add `extract_exports`.
3. `src/factory/pre_gate.py` — add validator function, `GateScope` dataclass, `PreGateResult.imports_symbols_passed` field, skip-counter dict.
4. `src/factory/runner.py` — wire export-map construction (once per work item), cascade insertion, telemetry counter, end-of-run scope-creep warning.
5. `src/factory/prompts/*.md` — manifest section, `(stub-only)` tag (keep the legacy block).
6. Tests (the 15 above).
7. `breadcrumbs/RFC-015-*.md` — flip `status: proposed` to `status: implemented`, add a one-line "implemented in commit <sha>" entry at the bottom.

Do **not** delete the legacy `## stub_only_dependencies` block in this PR.

---

## Implementation (2026-05-12)

Implemented by GLM-5.1. Files changed:

- `src/factory/constants.py` — added `GATE_NAME_INNER_IMPORT_SYMBOLS`
- `src/factory/gate.py` — added `extract_exports()` (AST-walk for top-level public names)
- `src/factory/pre_gate.py` — added `GateScope`, `validate_artifact_imports()`, `PreGateResult.imports_symbols_passed`, TYPE_CHECKING block detection
- `src/factory/runner.py` — added `_build_export_map()`, export-map passed through `_inner_gate_loop` and `_run_pre_gate`, cascade: `import_symbols → mypy → ruff → import (runtime) → collect → pytest`
- `src/factory/context.py` — added `export_map` to `PromptContext`, `_build_export_map_from_contents()`, `available_dependency_imports` section in `render_prompt` with `(stub-only)` tags
- `tests/test_import_validation.py` — 15 mandatory tests
- 491 tests pass, 0 lint errors, 0 audit findings
