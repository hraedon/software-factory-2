from __future__ import annotations

WORK_ITEM_TYPE_INTERFACE_SPEC = "interface_spec"
WORK_ITEM_TYPE_TEST_SUITE = "test_suite"
WORK_ITEM_TYPE_IMPLEMENTATION = "implementation"

ROLE_INTERFACE_ARCHITECT = "interface_architect"
ROLE_TEST_AUTHOR = "test_author"
ROLE_IMPLEMENTER = "implementer"
ROLE_MECHANICAL_GATE = "mechanical_gate"

CHANNEL_CLAUDE_CODE = "claude-code"
CHANNEL_OPENCODE = "opencode"
CHANNEL_CODE = "code"

FAMILY_ANTHROPIC = "anthropic"
FAMILY_OPENCODE = "opencode"
FAMILY_CODE = "code"

STATE_NEW = "new"
STATE_IN_PROGRESS = "in_progress"
STATE_GATING = "gating"
STATE_LOCKED = "locked"
STATE_CANNOT_PROCEED = "cannot_proceed"

TRANSITION_CLAIM = "claim"
TRANSITION_SUBMIT = "submit"
TRANSITION_GATE_PASS = "gate_pass"
TRANSITION_GATE_FAIL = "gate_fail"
TRANSITION_GATE_ESCALATION = "gate_escalation"
TRANSITION_CHANNEL_FAIL = "channel_fail"
TRANSITION_ROUTE_TO_CANNOT_PROCEED = "cannot_proceed"

LINK_TYPE_DERIVED_FROM = "derived_from"
LINK_TYPE_TESTED_BY = "tested_by"
LINK_TYPE_IMPLEMENTS = "implements"

CUSTOM_FIELD_ARTIFACT_PATH = "artifact_path"
CUSTOM_FIELD_ARTIFACT_HASH = "artifact_hash"
CUSTOM_FIELD_INTERFACE_REF = "interface_ref"
CUSTOM_FIELD_TEST_SUITE_REF = "test_suite_ref"
CUSTOM_FIELD_SPEC_SECTION = "spec_section"
CUSTOM_FIELD_AC_IDS = "ac_ids"
CUSTOM_FIELD_DIAGNOSTICS = "diagnostics"
CUSTOM_FIELD_DEPENDENCY_REFS = "dependency_refs"

ACTOR_ID_WORKER_PREFIX = "factory-worker"
ACTOR_ID_GATE = "factory-gate-code"
ACTOR_ID_SCHEDULER = "factory-scheduler"
ACTOR_KIND_AGENT = "agent"

ARTIFACT_FILENAME_RAW_STDOUT = "raw_stdout.txt"
ARTIFACT_FILENAME_CANNOT_PROCEED = "cannot_proceed.json"
ARTIFACT_FILENAME_INTERFACE = "interface"

TEMPFILE_PREFIX_COLLECT = "sf2_collect_"
TEMPFILE_PREFIX_MYPY = "sf2_mypy_"
TEMPFILE_PREFIX_PYTEST = "sf2_pytest_"

GATE_NAME_INTERFACE_SPEC = "interface_spec"
GATE_NAME_INTERFACE_SPEC_FILE_EXISTS = "interface_spec_file_exists"
GATE_NAME_INTERFACE_SPEC_NOT_EMPTY = "interface_spec_not_empty"
GATE_NAME_INTERFACE_SPEC_SYNTAX = "interface_spec_syntax"
GATE_NAME_INTERFACE_SPEC_STUB = "interface_spec_stub"
GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS = "interface_spec_structural_semantics"

GATE_NAME_TEST_SUITE = "test_suite"
GATE_NAME_TEST_SUITE_FILE_EXISTS = "test_suite_file_exists"
GATE_NAME_TEST_SUITE_NOT_EMPTY = "test_suite_not_empty"
GATE_NAME_TEST_SUITE_SYNTAX = "test_suite_syntax"
GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN = "test_suite_import_forbidden"
GATE_NAME_TEST_SUITE_COLLECT = "test_suite_collect"
GATE_NAME_TEST_SUITE_ASSERTIONS = "test_suite_assertions"
GATE_NAME_TEST_SUITE_DEPENDENCY = "test_suite_dependency"

GATE_NAME_IMPLEMENTATION = "implementation"
GATE_NAME_IMPLEMENTATION_FILE_EXISTS = "implementation_file_exists"
GATE_NAME_IMPLEMENTATION_NOT_EMPTY = "implementation_not_empty"
GATE_NAME_IMPLEMENTATION_SYNTAX = "implementation_syntax"
GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN = "implementation_import_forbidden"
GATE_NAME_IMPLEMENTATION_IMPORTS = "implementation_imports"
GATE_NAME_IMPLEMENTATION_MYPY = "implementation_mypy"
GATE_NAME_IMPLEMENTATION_PYTEST = "implementation_pytest"
GATE_NAME_IMPLEMENTATION_LINT = "implementation_lint"
GATE_NAME_IMPLEMENTATION_DEPENDENCY = "implementation_dependency"

GATE_NAME_UNKNOWN_TYPE = "unknown_type"
GATE_NAME_BEHAVIORAL = "behavioral"
GATE_NAME_UNKNOWN = "unknown"

FAMILY_BY_PROVIDER = {
    "zai-coding-plan": "zai",
    "ollama-cloud": "ollama",
    "fireworks-ai": "fireworks",
    "opencode": "opencode-free",
    "mac-studio-lms": "local-lms",
}
