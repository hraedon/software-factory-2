# Log Redaction CLI — Specification

## Overview

A CLI tool that reads structured JSONL logs, applies YAML redaction rules, and emits redacted JSONL plus an audit trail.

## Functional Requirements

### FR-01: Rule Loading
Given a YAML rules file, load and validate redaction rules. Invalid rules produce a structured error before processing.

### FR-02: Log Ingestion
Given JSONL input (file or stdin), read each line, parse as JSON, preserve line order. Malformed lines pass through with a warning.

### FR-03: Redaction Engine
Given a parsed log line and ruleset, evaluate rules in order. Apply replacement (mask, hash, or delete) and record audit entries. First matching rule wins per field.

### FR-04: Output Emission
Emit redacted JSON Lines to stdout or a file path, preserving order and count.

### FR-05: Audit Trail
Emit an audit JSONL stream describing every redaction: line number, rule id, field name, replacement type.

## Data Types

- `Rule`: `{id, scope, pattern, replacement_type, replacement_value}`
- `LogLine`: `{line_number, raw_text, parsed: dict | None, parse_error: str | None}`
- `RedactedLine`: `{line_number, data: dict, actions: list[AuditAction]}`
- `AuditAction`: `{line_number, rule_id, field_name, replacement_type}`

## Acceptance Criteria

- **AC-LOG-01** [FR-01]: Valid rules YAML loads as ordered Rule objects.
- **AC-LOG-02** [FR-01]: Missing 'rules' key raises `RulesFileError`.
- **AC-LOG-03** [FR-02]: 3 valid + 1 malformed line yields 4 LogLine objects; malformed has `parse_error`.
- **AC-LOG-04** [FR-03]: `email` field with `mask` replacement becomes `[REDACTED]`.
- **AC-LOG-05** [FR-03]: `ssn` field with `hash` replacement becomes SHA-256 hex.
- **AC-LOG-06** [FR-03]: Two rules matching same field apply only the first.
- **AC-LOG-07** [FR-04]: Redacted output is valid JSON Lines in original order.
- **AC-LOG-08** [FR-05]: Audit stream has one line per redaction action.
- **AC-LOG-09** [FR-05]: Zero redactions produces a `run_start` header only.

## Business Rules

1. Rule evaluation order is file-order, first-match-wins.
2. Scope `all` applies to every field except `timestamp` and `level`.
3. Hash replacement is SHA-256 hex of UTF-8 original value.
4. Missing rules file exits with code 2.
5. Default output is stdout; `--output` and `--audit` are optional.
