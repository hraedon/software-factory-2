from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


class ErrorCode(Enum):
    """Satisfies AC-17."""
    YAML_SYNTAX_ERROR = "yaml_syntax_error"
    SCHEMA_INVALID = "schema_invalid"
    UNREACHABLE_STATE = "unreachable_state"
    UNDECLARED_TERMINAL = "undeclared_terminal"
    UNDECLARED_ROLE = "undeclared_role"
    TYPE_VOCABULARY_VIOLATION = "type_vocabulary_violation"
    WORKFLOW_VERSION_CONFLICT = "workflow_version_conflict"


@dataclass(frozen=True)
class RegistrationError:
    """Structured registration error. Satisfies AC-17.

    `line` is populated for YAML syntax errors; `json_pointer` is populated
    for JSON Schema violations; `element_name` is populated for semantic
    errors (unreachable state, undeclared terminal, undeclared role).
    """
    code: ErrorCode
    message: str
    line: Optional[int]
    json_pointer: Optional[str]
    element_name: Optional[str]


@dataclass(frozen=True)
class Registration:
    """Successful workflow registration record. Satisfies AC-17."""
    workflow_name: str
    version: int
    content_hash: str
    created: bool


Result = Union[Registration, RegistrationError]


def register_workflow(definition: str) -> Result:
    """Satisfies AC-17."""
    ...
