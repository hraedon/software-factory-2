# register_workflow — Pure Interface

## Source
regista spec §5, FR-17

## Spec excerpt

**FR-17:** Parse and validate workflow definition (YAML + JSON Schema). Declares: `version` (required integer), `regista_version` (required, semver), states, transitions, role-gating per transition, custom typed fields per work-item-type (each field has `type` + `ui_visible` flag, default `false`), link types per work-item-type pair, attempt threshold, per-hook retry overrides.

Custom field type vocabulary (closed set): `string`, `integer`, `boolean`, `timestamp`, `json`, `enum`, `work_item_ref`.

Validation passes: (a) YAML syntactic — rejects with line-numbered error. (b) JSON Schema — rejects with JSON-pointer error. (c) Structural / semantic — reachability, terminal-state declaration consistency, role-binding consistency, type-vocabulary consistency.

Registry uniqueness: `(workflow_name, version)` is unique within a project DB. Content-based idempotency: re-registration of the same `(name, version)` with identical content (SHA-256 of JCS-canonicalized definition) returns the existing row; re-registration with different content rejects with `WORKFLOW_VERSION_CONFLICT`.

**AC-17:** Workflow file with YAML syntax error rejects with line number. Schema-invalid file rejects with JSON pointer. Semantically broken file (unreachable state, undeclared terminal, undeclared role) rejects with element-named error. Valid file registers and is callable.

## Work-item shape
pure-interface — single function that accepts a workflow definition string and returns a registration result

## AC IDs
AC-17
