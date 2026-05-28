# Interface Specification: FR 02

## Dependencies

None.

## Glossary

- **audit entry**: A JSONL line emitted to the audit stream describing what was redacted: original line number, rule id, matched field, and replacement type (mask or hash).
- **redaction rule**: A declarative rule that matches a field or pattern and replaces matched content with a fixed string or a hash. Rules are ordered and evaluated in sequence.
- **replacement type**: One of: 'mask' (replaced with fixed string like '[REDACTED]'), 'hash' (SHA-256 hex digest of original value), or 'delete' (field removed entirely).
- **rule scope**: The set of field names a rule applies to. 'all' means every field; otherwise a list like ['message', 'user_agent'].
- **structured log**: A JSON object per line (JSON Lines) containing at minimum 'timestamp', 'level', and 'message' fields. Extra fields are allowed and preserved through redaction.

## FR-02

Given a JSONL log file or stdin stream, the system reads each line, parses it as JSON, and preserves the line order. Malformed lines are passed through unmodified with a warning emitted to stderr.

## AC-01: Malformed lines preserved with parse_error

Given a JSONL file with 3 valid lines and 1 malformed line, read_log_lines yields 4 LogLine objects where the malformed line has parse_error set and raw_text preserved
