# Interface Specification: FR-01 Rule Loader

## Dependencies
None.

## AC-01: Load Rules from YAML
A function `load_rules(path: Path) -> list[Rule]` must read a YAML file and return an ordered list of `Rule` objects.

## AC-02: Rule Structure
Each `Rule` must be a dataclass with fields: `id: str`, `scope: list[str] | str`, `pattern: str | None`, `replacement_type: str`, `replacement_value: str | None`.

## AC-03: Validate Required Fields
If a rule is missing `id`, `scope`, or `replacement_type`, `load_rules` must raise `RulesFileError` with the rule index in the message.

## AC-04: Validate Replacement Type
If `replacement_type` is not one of `mask`, `hash`, `delete`, `load_rules` must raise `RulesFileError` with the invalid value in the message.

## AC-05: Regex Compilation
If `pattern` is present and is not a valid Python regex, `load_rules` must raise `RulesFileError` with the rule id in the message.

## AC-06: Missing Rules Key
If the YAML top-level key is not `rules`, `load_rules` must raise `RulesFileError` with message containing `"missing top-level key: rules"`.
