from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Union


class ErrorCode(Enum):
    """Satisfies AC-06."""
    CLAIM_CONTESTED = "claim_contested"
    NOT_BEFORE_FUTURE = "not_before_future"
    STALE_HEARTBEAT = "stale_heartbeat"


@dataclass(frozen=True)
class Claim:
    """Successful claim on a work-item. Satisfies AC-06."""
    work_item_id: str
    agent_id: str
    attempt_number: int
    acquired_at: datetime
    lease_expires_at: datetime


@dataclass(frozen=True)
class Rejection:
    """Structured claim-acquisition rejection. Satisfies AC-06."""
    code: ErrorCode
    message: str
    work_item_id: str


Result = Union[Claim, Rejection]


def acquire_claim(work_item_id: str, agent_id: str, now: datetime) -> Result:
    """Satisfies AC-06."""
    ...
