# Interface Specification: FR 01

## Dependencies

None.

## Glossary

- **audit entry**: A JSONL line emitted to the audit stream describing what was redacted: original line number, rule id, matched field, and replacement type (mask or hash).
- **redaction rule**: A declarative rule that matches a field or pattern and replaces matched content with a fixed string or a hash. Rules are ordered and evaluated in sequence.
- **replacement type**: One of: 'mask' (replaced with fixed string like '[REDACTED]'), 'hash' (SHA-256 hex digest of original value), or 'delete' (field removed entirely).
- **rule scope**: The set of field names a rule applies to. 'all' means every field; otherwise a list like ['message', 'user_agent'].
- **structured log**: A JSON object per line (JSON Lines) containing at minimum 'timestamp', 'level', and 'message' fields. Extra fields are allowed and preserved through redaction.

## FR-01

Given a YAML rules file path, the system loads, validates, and orders redaction rules. Invalid rules files produce a structured error before any log processing begins.

## AC-LOG-01

Given a valid rules YAML with two rules, load_rules returns an ordered list of Rule objects with correct scopes and replacement types

## AC-LOG-02

Given a rules YAML missing the 'rules' top-level key, load_rules raises RulesFileError with message containing 'missing top-level key: rules'
