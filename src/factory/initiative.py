from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from factory.constants import (
    CUSTOM_FIELD_INITIATIVE_ID,
    STATE_CANNOT_PROCEED,
    STATE_IN_PROGRESS,
    STATE_LOCKED,
    STATE_NEW,
    TRANSITION_REQUEUE,
    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
)
from factory.idempotency import make_event_id

_initiative_log = logging.getLogger("factory.initiative")


@dataclass(frozen=True)
class InitiativeSummary:
    initiative_id: str
    total_items: int
    locked_items: int
    cannot_proceed_items: int
    in_progress_items: int


def generate_initiative_id() -> str:
    return uuid.uuid4().hex[:12]


def query_initiatives(
    sub: Any,
    *,
    workflow_name: str | None = None,
    workflow_version: int | None = None,
) -> list[InitiativeSummary]:
    kwargs: dict[str, Any] = {}
    if workflow_name is not None:
        kwargs["workflow_name"] = workflow_name
    if workflow_version is not None:
        kwargs["workflow_version"] = workflow_version

    work_items = sub.query_work_items(**kwargs)
    by_initiative: dict[str, dict[str, int]] = {}

    for wi in work_items:
        custom: dict[str, Any] = wi.custom_fields or {}
        iid = custom.get(CUSTOM_FIELD_INITIATIVE_ID, "")
        if not iid:
            continue

        counts = by_initiative.setdefault(iid, {"total": 0, "locked": 0, "cp": 0, "other": 0})
        counts["total"] += 1
        state = wi.current_state
        if state == STATE_LOCKED:
            counts["locked"] += 1
        elif state == STATE_CANNOT_PROCEED:
            counts["cp"] += 1
        else:
            counts["other"] += 1

    return [
        InitiativeSummary(
            initiative_id=iid,
            total_items=counts["total"],
            locked_items=counts["locked"],
            cannot_proceed_items=counts["cp"],
            in_progress_items=counts["other"],
        )
        for iid, counts in sorted(by_initiative.items())
    ]


def cancel_initiative(
    sub: Any,
    initiative_id: str,
    reason: str,
    *,
    workflow_name: str | None = None,
    workflow_version: int | None = None,
) -> int:
    from regista import RegistaError

    kwargs: dict[str, Any] = {}
    if workflow_name is not None:
        kwargs["workflow_name"] = workflow_name
    if workflow_version is not None:
        kwargs["workflow_version"] = workflow_version

    work_items = sub.query_work_items(**kwargs)
    cancelled = 0

    expected_states = {STATE_IN_PROGRESS, STATE_NEW}
    transition_name = TRANSITION_ROUTE_TO_CANNOT_PROCEED

    for wi in work_items:
        custom: dict[str, Any] = wi.custom_fields or {}
        if custom.get(CUSTOM_FIELD_INITIATIVE_ID) != initiative_id:
            continue
        if wi.current_state in (STATE_LOCKED, STATE_CANNOT_PROCEED):
            continue
        if wi.current_state not in expected_states:
            _initiative_log.warning(
                "cancel_initiative_skip_state",
                work_item_id=str(wi.work_item_id),
                current_state=wi.current_state,
                expected_states=list(expected_states),
            )
            continue

        try:
            sub.acquire_claim(
                wi.work_item_id,
                "factory-initiative-cancel",
                event_id=make_event_id(
                    wi.work_item_id, "acquire_claim", 0, extra="cancel-initiative"
                ),
            )
        except RegistaError:
            continue

        sub.transition(
            wi.work_item_id,
            transition_name,
            "factory-initiative-cancel",
            custom_fields={"cannot_proceed_reason": reason},
            event_id=make_event_id(
                wi.work_item_id, transition_name, 0, extra=f"cancel-{initiative_id}"
            ),
        )
        cancelled += 1

    _initiative_log.info(
        "cancel_initiative: initiative=%s cancelled=%d reason=%s",
        initiative_id,
        cancelled,
        reason,
    )
    return cancelled


def requeue_initiative(
    sub: Any,
    initiative_id: str,
    *,
    workflow_name: str | None = None,
    workflow_version: int | None = None,
) -> int:
    from regista import RegistaError

    kwargs: dict[str, Any] = {}
    if workflow_name is not None:
        kwargs["workflow_name"] = workflow_name
    if workflow_version is not None:
        kwargs["workflow_version"] = workflow_version

    work_items = sub.query_work_items(**kwargs)
    requeued = 0
    transition_name = TRANSITION_REQUEUE

    for wi in work_items:
        custom: dict[str, Any] = wi.custom_fields or {}
        if custom.get(CUSTOM_FIELD_INITIATIVE_ID) != initiative_id:
            continue
        if wi.current_state != STATE_CANNOT_PROCEED:
            _initiative_log.warning(
                "requeue_initiative_skip_state",
                work_item_id=str(wi.work_item_id),
                current_state=wi.current_state,
                expected_state=STATE_CANNOT_PROCEED,
            )
            continue

        try:
            sub.acquire_claim(
                wi.work_item_id,
                "factory-initiative-requeue",
                event_id=make_event_id(
                    wi.work_item_id, "acquire_claim", 0, extra="requeue-initiative"
                ),
            )
        except RegistaError:
            continue

        sub.transition(
            wi.work_item_id,
            transition_name,
            "factory-initiative-requeue",
            event_id=make_event_id(
                wi.work_item_id, transition_name, 0, extra=f"requeue-{initiative_id}"
            ),
        )
        requeued += 1

    _initiative_log.info(
        "requeue_initiative: initiative=%s requeued=%d",
        initiative_id,
        requeued,
    )
    return requeued
