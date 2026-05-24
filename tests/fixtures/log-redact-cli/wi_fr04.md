# Interface Specification: FR 04

## Dependencies

- `interface_ref`: `fr03`

## Glossary

- **audit entry**: A JSONL line emitted to the audit stream describing what was redacted: original line number, rule id, matched field, and replacement type (mask or hash).
- **redaction rule**: A declarative rule that matches a field or pattern and replaces matched content with a fixed string or a hash. Rules are ordered and evaluated in sequence.
- **replacement type**: One of: 'mask' (replaced with fixed string like '[REDACTED]'), 'hash' (SHA-256 hex digest of original value), or 'delete' (field removed entirely).
- **rule scope**: The set of field names a rule applies to. 'all' means every field; otherwise a list like ['message', 'user_agent'].
- **structured log**: A JSON object per line (JSON Lines) containing at minimum 'timestamp', 'level', and 'message' fields. Extra fields are allowed and preserved through redaction.

## FR-04

Given redacted log lines, the system emits JSON Lines to stdout or an optional output file path, preserving line order and valid JSON for every successfully parsed input line.

## AC-LOG-07

Given redacted lines, emit_redacted writes valid JSON Lines preserving the original line order and count
