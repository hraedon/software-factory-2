from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class LinkError(Exception):
    """Base error for create_link failures. Satisfies AC-22."""
    ...


class CrossProjectLinkError(LinkError):
    """Raised when target work-item is in a different project. Satisfies AC-22."""
    ...


class TargetNotFoundError(LinkError):
    """Raised when target work-item does not exist in the project DB. Satisfies AC-22."""
    ...


class DisallowedLinkTypeError(LinkError):
    """Raised when link type is not allowed by workflow def for the work-item-type pair. Satisfies AC-22."""
    ...


@dataclass(frozen=True)
class LinkCreatedEvent:
    """Event emitted on successful link creation. Satisfies AC-22."""
    from_id: str
    to_id: str
    link_type: str
    project_id: str
    created_at: datetime


class WorkItemRepository(Protocol):
    """Read-side access for validating link endpoints. Satisfies AC-22."""

    def get_project_id(self, work_item_id: str) -> str | None:
        ...

    def get_work_item_type(self, work_item_id: str) -> str | None:
        ...


class WorkflowDefinition(Protocol):
    """Workflow definition exposing allowed link types per work-item-type pair. Satisfies AC-22."""

    def is_link_type_allowed(
        self,
        from_type: str,
        to_type: str,
        link_type: str,
    ) -> bool:
        ...


class EventSink(Protocol):
    """Sink for emitting domain events. Satisfies AC-22."""

    def emit(self, event: LinkCreatedEvent) -> None:
        ...


def create_link(
    from_id: str,
    to_id: str,
    link_type: str,
    project_id: str,
    repository: WorkItemRepository,
    workflow: WorkflowDefinition,
    events: EventSink,
    now: datetime,
) -> LinkCreatedEvent:
    """Satisfies AC-22."""
    ...
