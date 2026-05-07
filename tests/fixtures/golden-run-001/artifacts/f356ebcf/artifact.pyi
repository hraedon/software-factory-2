from dataclasses import dataclass
from enum import Enum
from typing import Union


class ErrorCode(Enum):
    """Transition validation error taxonomy. Satisfies AC-11, AC-12."""
    INVALID_TRANSITION = "invalid_transition"
    ROLE_NOT_PERMITTED = "role_not_permitted"
    WORKFLOW_NOT_REGISTERED = "workflow_not_registered"
    TYPE_NOT_DECLARED = "type_not_declared"


@dataclass(frozen=True)
class TransitionOk:
    """Successful transition outcome. Satisfies AC-11, AC-12."""
    work_item_id: str
    from_state: str
    to_state: str
    workflow_name: str
    workflow_version: str


@dataclass(frozen=True)
class TransitionError:
    """Structured transition error. Satisfies AC-11, AC-12."""
    code: ErrorCode
    message: str
    work_item_id: str


TransitionResult = Union[TransitionOk, TransitionError]


def attempt_transition(
    work_item_id: str,
    to_state: str,
    actor_id: str,
    actor_role: str,
) -> TransitionResult:
    """Satisfies AC-11, AC-12."""
    ...
