---
number: "055"
title: "Stage contracts must be blocking from day one, not warn-and-continue (v1 BC-358 pattern)"
severity: high
status: implemented
kind: design
author: adversarial-review
date: "2026-05-08"
tags: [gate, failure-routing, dep-v1-358]
related: ["037"]
---

## Problem

v1's BC-358: `PhaseStage.validate_inputs()` checked that all `reads` keys existed in state, but the runner logged a warning and continued when keys were missing. A stage declaring `reads: ["spec", "phases"]` that executed against state without `"phases"` would proceed, produce wrong output, and the pipeline would continue with corrupt state. The decision to make contract violation blocking was deferred and "never happened because it would break stages that had drifted."

v2 is at a design inflection point. The workflow YAML declares states and transitions (phase2.yaml, full_pipeline.yaml) and the router enforces allowed transitions. But there is no equivalent of **artifact contract enforcement** — a test_suite must reference a locked interface_spec, an implementation must reference both interface_spec and test_suite. These references exist as custom_fields but are resolved with fallback-to-None logic:

```python
# gate_process.py:100-108
interface_ref = custom.get("interface_ref")
interface_pyi_path = None
if interface_ref:
    ref_wi = sub.get_work_item(_to_uuid(interface_ref))
    if ref_wi and ref_wi.custom_fields:
        ref_path = ref_wi.custom_fields.get("artifact_path")
        if ref_path:
            interface_pyi_path = Path(ref_path)
```

If `interface_ref` is missing or references a non-existent item, the gate silently skips interface-dependent checks (no mypy, no import validation). This is exactly the v1 "warn-and-continue" pattern: the contract says "this item needs an interface" but the system silently degrades rather than blocking.

## Fix

Make missing required references a **gate_fail** rather than silent degradation. The gate should distinguish:
- **Required reference missing** → gate_fail, diagnostic_kind="missing_dependency"
- **Reference resolves but artifact missing** → gate_fail, diagnostic_kind="missing_artifact"
- **Optional reference missing** → skip that check only

Concretely: `gate_process.py` should fail `test_suite` items without `interface_ref`, and `implementation` items without both `interface_ref` and `test_suite_ref`. The `interface_ref` and `test_suite_ref` fields are declared `required: true` in phase2.yaml — the gate should enforce that.

## Resolution

Implemented in gate_process.py. The gate now blocks on contract violations instead of silently degrading:

- **missing_dependency**: Required ref field is empty/None → gate_fail with `diagnostic_kind="missing_dependency"`. Routes to `cannot_proceed` (item cannot self-correct).
- **missing_artifact**: Ref resolves but the referenced work item has no `artifact_path`, or the artifact file doesn't exist on disk → gate_fail with `diagnostic_kind="missing_artifact"`. Routes to `new` (may be a timing issue — retry after upstream artifact arrives).
- **Optional reference missing**: Not yet applicable (no optional refs exist yet); the gate would skip that check per the original BC-055 spec.

Added `missing_dependency` and `missing_artifact` to `DiagnosticKind` enum and `_PHASE2_DISPATCH` in router.py. Extracted `_resolve_ref_artifact()` helper to reduce duplication. Added `diagnostic_kind` propagation to the diagnostics dict in `process_gate_item`, with guard to not overwrite router-provided kinds (e.g., `cannot_proceed_seam`).

8 new contract-enforcement tests in `test_gate_process_contract.py`, all passing. 264 total tests pass, 0 lint errors.
