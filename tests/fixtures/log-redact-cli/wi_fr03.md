# Interface Specification: FR 03

## Dependencies

- `interface_ref`: `fr01`
- `interface_ref`: `fr02`

## Glossary

- **audit entry**: A JSONL line emitted to the audit stream describing what was redacted: original line number, rule id, matched field, and replacement type (mask or hash).
- **redaction rule**: A declarative rule that matches a field or pattern and replaces matched content with a fixed string or a hash. Rules are ordered and evaluated in sequence.
- **replacement type**: One of: 'mask' (replaced with fixed string like '[REDACTED]'), 'hash' (SHA-256 hex digest of original value), or 'delete' (field removed entirely).
- **rule scope**: The set of field names a rule applies to. 'all' means every field; otherwise a list like ['message', 'user_agent'].
- **structured log**: A JSON object per line (JSON Lines) containing at minimum 'timestamp', 'level', and 'message' fields. Extra fields are allowed and preserved through redaction.

## FR-03

Given a parsed log line and a loaded ruleset, the system evaluates rules in order. For each matching rule, it applies the configured replacement to the matched field(s) and records an audit entry.

## AC-01: Mask replacement redacts email field

Given a log line with field 'email' and a rule matching 'email' with replacement_type='mask', apply_rules replaces the email value with '[REDACTED]'

## AC-02: Hash replacement produces SHA-256 hex

Given a log line with field 'ssn' and a rule matching 'ssn' with replacement_type='hash', apply_rules replaces the ssn value with the SHA-256 hex digest of the original value

## AC-03: First matching rule wins per field

Given two rules where both match field 'message', apply_rules applies only the first matching rule and records a single audit entry
