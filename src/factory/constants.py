from __future__ import annotations

WORK_ITEM_TYPE_INTERFACE_SPEC = "interface_spec"
WORK_ITEM_TYPE_TEST_SUITE = "test_suite"
WORK_ITEM_TYPE_IMPLEMENTATION = "implementation"
WORK_ITEM_TYPE_REVIEW = "review"
WORK_ITEM_TYPE_JURY = "jury"
WORK_ITEM_TYPE_INTEGRATION = "integration"
WORK_ITEM_TYPE_OUTCOME_VERIFICATION = "outcome_verification"

ROLE_INTERFACE_ARCHITECT = "interface_architect"
ROLE_TEST_AUTHOR = "test_author"
ROLE_IMPLEMENTER = "implementer"
ROLE_MECHANICAL_GATE = "mechanical_gate"
ROLE_CROSS_FAMILY_REVIEWER = "cross_family_reviewer"
ROLE_FRONTIER_JUDGE = "frontier_judge"
ROLE_INTEGRATOR = "integrator"
ROLE_OUTCOME_VERIFIER = "outcome_verifier"
ROLE_COHERENCE_REVIEWER = "coherence_reviewer"

CHANNEL_CLAUDE_CODE = "claude-code"
CHANNEL_OPENCODE = "opencode"
CHANNEL_CODE = "code"
CHANNEL_GEMINI_CLI = "gemini-cli"

FAMILY_ANTHROPIC = "anthropic"
FAMILY_OPENCODE = "opencode"
FAMILY_CODE = "code"
FAMILY_GEMINI = "google"
FAMILY_ZAI = "zai"
FAMILY_FIREWORKS = "fireworks"

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
TRANSITION_REVIEW_PASS = "review_pass"
TRANSITION_REVIEW_FAIL = "review_fail"
TRANSITION_JURY_PASS = "jury_pass"
TRANSITION_JURY_FAIL = "jury_fail"
TRANSITION_JURY_DISAGREE = "jury_disagree"

LINK_TYPE_DERIVED_FROM = "derived_from"
LINK_TYPE_TESTED_BY = "tested_by"
LINK_TYPE_IMPLEMENTS = "implements"
LINK_TYPE_REVIEWS = "reviews"
LINK_TYPE_JUDGES = "judges"
LINK_TYPE_SUPERCEDES = "supersedes"

CUSTOM_FIELD_ARTIFACT_PATH = "artifact_path"
CUSTOM_FIELD_ARTIFACT_HASH = "artifact_hash"
CUSTOM_FIELD_INTERFACE_REF = "interface_ref"
CUSTOM_FIELD_TEST_SUITE_REF = "test_suite_ref"
CUSTOM_FIELD_SPEC_SECTION = "spec_section"
CUSTOM_FIELD_AC_IDS = "ac_ids"
CUSTOM_FIELD_DIAGNOSTICS = "diagnostics"
CUSTOM_FIELD_DEPENDENCY_REFS = "dependency_refs"
CUSTOM_FIELD_MODULE_NAME = "module_name"
CUSTOM_FIELD_IMPLEMENTATION_REF = "implementation_ref"
CUSTOM_FIELD_REVIEW_REF = "review_ref"
CUSTOM_FIELD_REVIEW_FEEDBACK = "review_feedback"
CUSTOM_FIELD_REVIEW_FEEDBACK_PENDING = "review_feedback_pending"
CUSTOM_FIELD_JURY_REF = "jury_ref"

ACTOR_ID_WORKER_PREFIX = "factory-worker"
ACTOR_ID_GATE = "factory-gate-code"
ACTOR_ID_SCHEDULER = "factory-scheduler"
ACTOR_KIND_AGENT = "agent"

ARTIFACT_FILENAME_RAW_STDOUT = "raw_stdout.txt"
ARTIFACT_FILENAME_RAW_STDERR = "raw_stderr.txt"
ARTIFACT_FILENAME_CANNOT_PROCEED = "cannot_proceed.json"
ARTIFACT_FILENAME_INTERFACE = "interface"
ARTIFACT_FILENAME_JURY_VERDICT = "jury_verdict.json"

TEMPFILE_PREFIX_COLLECT = "sf2_collect_"
TEMPFILE_PREFIX_MYPY = "sf2_mypy_"
TEMPFILE_PREFIX_PYTEST = "sf2_pytest_"

MAX_ARTIFACT_SIZE_BYTES = 1_000_000  # 1 MB

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
GATE_NAME_INNER_PYTEST = "inner_pytest"
GATE_NAME_INNER_IMPORT = "inner_import"
GATE_NAME_INNER_COLLECT = "inner_test_collect"
GATE_NAME_INNER_MYPY = "inner_mypy"
GATE_NAME_INNER_RUFF = "inner_ruff"
GATE_NAME_INNER_IMPORT_SYMBOLS = "inner_import_symbols"

GATE_NAME_CROSS_FAMILY_REVIEW = "cross_family_review"
GATE_NAME_JURY = "jury"
GATE_NAME_JURY_QUORUM = "jury_quorum"
GATE_NAME_JURY_DISAGREE = "jury_disagree"

GATE_NAME_UNKNOWN_TYPE = "unknown_type"
GATE_NAME_BEHAVIORAL = "behavioral"
GATE_NAME_UNKNOWN = "unknown"

CHANNEL_TO_FAMILY = {
    CHANNEL_CLAUDE_CODE: FAMILY_ANTHROPIC,
    CHANNEL_OPENCODE: FAMILY_OPENCODE,
    CHANNEL_CODE: FAMILY_CODE,
    CHANNEL_GEMINI_CLI: FAMILY_GEMINI,
}

INNER_GATE_RUFF_SELECT = "E,F,I,N,W,UP,RUF"
INNER_GATE_RUFF_IGNORE = "E501"
INNER_GATE_RUFF_UNSAFE_FIXES = "F841"

FAMILY_BY_PROVIDER = {
    "zai-coding-plan": FAMILY_ZAI,
    "fireworks-ai": FAMILY_FIREWORKS,
    "opencode": "opencode-free",
    "mac-studio-lms": "local-lms",
}

AC_SOFT_CAP = 8
SPEC_WORD_COUNT_SOFT_CAP = 800
