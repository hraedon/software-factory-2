# create_work_item with custom_fields — ADT Validation

## Source
regista spec §5, FR-01, FR-02

## Spec excerpt

**FR-01:** Define a work-item with project-declared workflow (pinned version), work-item-type, current state, custom-typed fields, links (derived from event stream), `needs_review` flag, `not_before` timestamp.

**FR-02:** Create a work-item — validates workflow registered, work-item-type declared in that workflow, generates ID, validates initial custom field values against type schema, records `created` event.

Custom field type vocabulary (closed set):
- `string`
- `integer`
- `boolean`
- `timestamp` (ISO 8601 / Postgres `timestamptz`)
- `json` (free-form jsonb)
- `enum` (declared values list)
- `work_item_ref` (constrained to a `work_item_id` in the same project DB)

**§8 Custom field type violation:** Field value doesn't match declared type at create or transition. Reject; field-specific error; no partial write. Caller sees error.

**AC-02:** Given an unregistered workflow, when create is called, the operation rejects with "workflow not registered." Given an undeclared work-item-type, rejection with "type not declared in workflow." Given invalid initial custom field values, rejection with field-specific error and no partial write.

## Work-item shape
ADT-validation — function whose contract requires defining structured custom_fields payload, field type validator, and a typed field schema

## AC IDs
AC-02
