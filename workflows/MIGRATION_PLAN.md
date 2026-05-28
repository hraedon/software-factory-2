# Plan: Adopting Regista Workflow Composition

**Goal:** Refactor the workflow definition files in `software-factory-2/workflows` to eliminate the ~58% structural duplication by utilizing Regista's new `extends:` composition feature.

## 1. Analysis of Current Duplication
The `phase1.yaml` through `phase5.yaml` files represent a strictly linear progression where each phase builds upon the previous one. 
- The `states:` block is identical across all 5 files.
- The base `transitions:` structure (`claim`, `submit`, `cannot_proceed`, `release`, `gate_pass`, `gate_fail`, `gate_escalation`, `channel_fail`) is identical in all 5 files.
- The `interface_spec` work-item type is identical.
- Each phase primarily bumps the `version`, adds new roles, appends those roles to the `allowed_roles` of the transitions, adds new `work_item_types`, and adds new `link_types`.

*Note on `full_pipeline.yaml`:* Its structure diverges significantly (it drops `release` and `channel_fail` transitions, and adds the `feature` work-item type). Extending `phase1.yaml` would require complex `__remove` directives. Therefore, **`full_pipeline.yaml` will remain standalone.**

## 2. Refactoring Strategy: Linear Inheritance

We will establish a single inheritance chain: `phase1` -> `phase2` -> `phase3` -> `phase4` -> `phase5`.

**Crucial Rules:**
1. **Top-Level Scalars:** Every child file MUST explicitly declare all three top-level scalars: `name`, `version`, and `regista_version`. Inheriting `regista_version` silently is a footgun.
2. **Relative Paths Only:** The composer rejects `extends:` in absolute-path form or paths that escape the compose root. Relative paths like `extends: ./phase1.yaml` are strictly required.

### Step 1: Base File (`phase1.yaml`)
`phase1.yaml` remains unchanged. It serves as the root definition.

### Step 2: `phase2.yaml`
Refactored to extend `phase1.yaml`.
```yaml
name: software_factory
version: 2
regista_version: "0.1.0"
extends: ./phase1.yaml

roles:
  - name: test_author
  - name: implementer

...

link_types:
  - name: implements
    source_type: implementation
    target_type: interface_spec
  # ... other link types ...
```

### Step 3: `phase3.yaml`
`phase3.yaml` is currently identical to `phase2` except for the version. It becomes an almost empty delta.
```yaml
name: software_factory
version: 3
regista_version: "0.1.0"
extends: ./phase2.yaml
```
*(Note: If no active runs rely on Phase 3, this file could theoretically be deleted. For this migration, we will preserve it as an artifact).*

### Step 4 & 5: `phase4.yaml` and `phase5.yaml`
Refactored to extend the previous phase, utilizing `allowed_roles__append` for new roles, and appending the new `work_item_types` and `link_types`.

## 3. Fixing the Silent Reader (Code Change)
Currently, `src/factory/pipeline_docs.py:16` reads raw workflow YAML using `yaml.safe_load()`. If it loads a refactored `phase5.yaml`, it will only see the delta and render an incomplete markdown document.
**Action:** Update `pipeline_docs.py` to use Regista's composition entry point. Specifically, call `regista._workflow_compose.resolve_includes(path)[0]` (which returns the composed dict from the `(dict, SourceMap)` tuple). Do not use `parse_file`, as it returns a `WorkflowDefinition` object and wraps validation/registration semantics that are unnecessary for documentation rendering.

## 4. Migration Execution

To avoid manual errors across multiple YAML files, we will generate the new files programmatically.

1. **Timing:** Execute this migration strictly between golden runs (after GR-031), not during active pipeline validation.
2. **Generate:** Write a script (`scripts/migrate_workflows.py`) that reads the monolithic files, computes the delta `extends:` files, and writes them to disk.
    - *Safety Check:* The migration script must detect any non-additive delta in named lists (e.g., modifying an inherited `link_type` or `work_item_type`) and fail loud. It should only silently emit pure additions or explicit appends to ensure we don't accidentally trample inherited properties.
3. **Verify via Hash:** The script MUST verify the migration by calling Regista's `parse_file()` on both the old (monolithic) and new (composed) workflows, then comparing their `WorkflowDefinition.content_hash`. The hash is computed over canonical JSON, making it order-insensitive for sets, and guarantees strict functional equivalence.
4. **Unit Tests:** Run `pytest tests/` before attempting a pipeline run. Tests like `test_context_phase5.py` and `test_pipeline_idempotency.py` call `register_workflow_file` on the migrated YAMLs and will exercise the composer transparently. This is the cheapest and most vital first check.
5. **Run Pipeline:** Execute a full pipeline run against the migrated workflows to ensure no subtle behavioral anomalies were introduced.
6. **Commits:** Commit the changes incrementally (one commit per phase file) rather than a single mega-commit. This allows future bisects to isolate any regressions to a specific phase.