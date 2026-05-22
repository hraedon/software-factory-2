from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from factory.constants import (
    CUSTOM_FIELD_INITIATIVE_ID,
    STATE_CANNOT_PROCEED,
    STATE_LOCKED,
)

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


def query_initiatives(sub: Any, project_name: str) -> list[InitiativeSummary]:
    work_items = sub.query_work_items(project_id=project_name)
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


def cancel_initiative(sub: Any, project_name: str, initiative_id: str, reason: str) -> int:
    work_items = sub.query_work_items(project_id=project_name)
    cancelled = 0

    for wi in work_items:
        custom: dict[str, Any] = wi.custom_fields or {}
        if custom.get(CUSTOM_FIELD_INITIATIVE_ID) != initiative_id:
            continue
        if wi.current_state in (STATE_LOCKED, STATE_CANNOT_PROCEED):
            continue

        claim = sub.acquire_claim(
            work_item_id=wi.work_item_id,
            actor_id="factory-initiative-cancel",
            role="initiative_cancel",
        )
        if claim:
            sub.transition(
                work_item_id=wi.work_item_id,
                claim_id=claim.claim_id,
                transition="cannot_proceed",
                payload={},
                custom_fields={"cannot_proceed_reason": reason},
            )
            cancelled += 1

    _initiative_log.info(
        "cancel_initiative: initiative=%s cancelled=%d reason=%s",
        initiative_id,
        cancelled,
        reason,
    )
    return cancelled


def requeue_initiative(sub: Any, project_name: str, initiative_id: str) -> int:
    work_items = sub.query_work_items(project_id=project_name)
    requeued = 0

    for wi in work_items:
        custom: dict[str, Any] = wi.custom_fields or {}
        if custom.get(CUSTOM_FIELD_INITIATIVE_ID) != initiative_id:
            continue
        if wi.current_state != STATE_CANNOT_PROCEED:
            continue

        claim = sub.acquire_claim(
            work_item_id=wi.work_item_id,
            actor_id="factory-initiative-requeue",
            role="initiative_requeue",
        )
        if claim:
            sub.transition(
                work_item_id=wi.work_item_id,
                claim_id=claim.claim_id,
                transition="new",
                payload={},
                custom_fields={},
            )
            requeued += 1

    _initiative_log.info(
        "requeue_initiative: initiative=%s requeued=%d",
        initiative_id,
        requeued,
    )
    return requeued
