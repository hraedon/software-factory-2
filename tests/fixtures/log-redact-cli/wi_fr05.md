# Interface Specification: FR 05

## Dependencies

- `interface_ref`: `fr03`

## Glossary

- **audit entry**: A JSONL line emitted to the audit stream describing what was redacted: original line number, rule id, matched field, and replacement type (mask or hash).
- **redaction rule**: A declarative rule that matches a field or pattern and replaces matched content with a fixed string or a hash. Rules are ordered and evaluated in sequence.
- **replacement type**: One of: 'mask' (replaced with fixed string like '[REDACTED]'), 'hash' (SHA-256 hex digest of original value), or 'delete' (field removed entirely).
- **rule scope**: The set of field names a rule applies to. 'all' means every field; otherwise a list like ['message', 'user_agent'].
- **structured log**: A JSON object per line (JSON Lines) containing at minimum 'timestamp', 'level', and 'message' fields. Extra fields are allowed and preserved through redaction.

## FR-05

Given redaction actions performed during a run, the system emits an audit JSONL stream to a configurable audit file path. Each entry describes what was redacted: line number, rule id, field name, replacement type.

## AC-01: Audit stream has one line per redaction

Given redaction actions from a run, emit_audit writes one JSONL line per action containing line_number, rule_id, field_name, and replacement_type

## AC-02: Zero redactions emit header only

Given a run with no redactions, emit_audit writes a single header line with action='run_start' but no redaction entries
