from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime

from substrate._types import Claim, Event, QueryPage, WorkItem


@dataclass
class _WorkflowState:
    states: list[str]
    initial_state: str
    terminal_states: set[str]
    transitions: dict[tuple[str, str], str]
    transition_roles: dict[str, list[str]]


@dataclass
class _WorkItemState:
    work_item: WorkItem
    events: list[Event] = field(default_factory=list)
    event_seq: int = 0


class MockSubstrate:
    def __init__(self, workflow_yaml: str | None = None):
        self._work_items: dict[uuid.UUID, _WorkItemState] = {}
        self._actor_roles: dict[str, set[str]] = defaultdict(set)
        self._claims: dict[uuid.UUID, Claim] = {}
        self._attempt_counts: dict[uuid.UUID, int] = defaultdict(int)
        self._workflow = self._parse_workflow(workflow_yaml) if workflow_yaml else None
        self._closed = False

    @staticmethod
    def _parse_workflow(yaml_content: str) -> _WorkflowState:
        import yaml

        data = yaml.safe_load(yaml_content)
        states = {s["name"]: s for s in data.get("states", [])}
        initial = next(s["name"] for s in data.get("states", []) if s.get("initial"))
        terminal = {s["name"] for s in data.get("states", []) if s.get("terminal")}
        transitions = {}
        transition_roles = {}
        for t in data.get("transitions", []):
            transitions[(t["from"], t["name"])] = t["to"]
            transition_roles[t["name"]] = t.get("allowed_roles", [])
        return _WorkflowState(
            states=list(states.keys()),
            initial_state=initial,
            terminal_states=terminal,
            transitions=transitions,
            transition_roles=transition_roles,
        )

    def close(self) -> None:
        self._closed = True

    def register_workflow_file(self, path: str) -> None:
        from pathlib import Path

        self._workflow = self._parse_workflow(Path(path).read_text())

    def register_workflow(self, yaml_content: str) -> None:
        self._workflow = self._parse_workflow(yaml_content)

    def register_actor_role(self, actor_id: str, role: str) -> None:
        self._actor_roles[actor_id].add(role)

    def create_work_item(
        self,
        workflow_name: str,
        work_item_type: str,
        actor_id: str,
        actor_kind: str = "agent",
        actor_metadata: dict | None = None,
        *,
        custom_fields: dict | None = None,
        **kwargs,
    ) -> tuple[WorkItem, Event]:
        wi_id = uuid.uuid4()
        initial_state = self._workflow.initial_state if self._workflow else "new"
        now = datetime.now(UTC)
        wi = WorkItem(
            work_item_id=wi_id,
            workflow_name=workflow_name,
            workflow_version=1,
            work_item_type=work_item_type,
            current_state=initial_state,
            custom_fields=custom_fields or {},
            needs_review=False,
            not_before=None,
            last_event_seq=0,
            last_event_at=now,
            next_event_seq=1,
            claimed_by=None,
            claim_expires_at=None,
        )
        event = Event(
            event_id=uuid.uuid4(),
            work_item_id=wi_id,
            event_seq=1,
            actor_id=actor_id,
            actor_kind=actor_kind,
            actor_metadata=actor_metadata or {},
            key_id="mock",
            workflow_name=workflow_name,
            workflow_version=1,
            timestamp=now,
            transition="created",
            payload=None,
            payload_canonical_hash=None,
            signature="mock",
            canonical_envelope=None,
        )
        self._work_items[wi_id] = _WorkItemState(work_item=wi, events=[event])
        return wi, event

    def get_work_item(self, work_item_id: uuid.UUID) -> WorkItem | None:
        state = self._work_items.get(work_item_id)
        if state is None:
            return None
        return state.work_item

    def transition(
        self,
        work_item_id: uuid.UUID,
        transition_name: str,
        actor_id: str,
        actor_kind: str = "agent",
        actor_metadata: dict | None = None,
        *,
        payload: dict | None = None,
        custom_fields: dict | None = None,
        **kwargs,
    ) -> Event:
        state = self._work_items[work_item_id]
        wi = state.work_item
        if self._workflow:
            target_state = self._workflow.transitions.get((wi.current_state, transition_name))
            if target_state is None:
                raise ValueError(
                    f"No transition '{transition_name}' from state '{wi.current_state}'"
                )
        else:
            state_map = {
                "created": "new",
                "claim": "in_progress",
                "submit": "gating",
                "gate_pass": "locked",
                "gate_fail": "new",
                "cannot_proceed": "cannot_proceed",
            }
            target_state = state_map.get(transition_name, wi.current_state)

        state.event_seq += 1
        now = datetime.now(UTC)
        event = Event(
            event_id=uuid.uuid4(),
            work_item_id=work_item_id,
            event_seq=state.event_seq,
            actor_id=actor_id,
            actor_kind=actor_kind,
            actor_metadata=actor_metadata or {},
            key_id="mock",
            workflow_name=wi.workflow_name,
            workflow_version=wi.workflow_version,
            timestamp=now,
            transition=transition_name,
            payload=payload,
            payload_canonical_hash=None,
            signature="mock",
            canonical_envelope=None,
        )
        state.events.append(event)

        merged_custom = dict(wi.custom_fields)
        if custom_fields:
            merged_custom.update(custom_fields)

        updated = WorkItem(
            work_item_id=wi.work_item_id,
            workflow_name=wi.workflow_name,
            workflow_version=wi.workflow_version,
            work_item_type=wi.work_item_type,
            current_state=target_state,
            custom_fields=merged_custom,
            needs_review=wi.needs_review,
            not_before=wi.not_before,
            last_event_seq=state.event_seq,
            last_event_at=now,
            next_event_seq=state.event_seq + 1,
            claimed_by=None,
            claim_expires_at=None,
        )
        state.work_item = updated
        return event

    def acquire_claim(
        self,
        work_item_id: uuid.UUID,
        actor_id: str,
        ttl_seconds: int = 300,
        **kwargs,
    ) -> Claim:
        self._attempt_counts[work_item_id] += 1
        now = datetime.now(UTC)
        from datetime import timedelta

        claim = Claim(
            work_item_id=work_item_id,
            actor_id=actor_id,
            acquired_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            attempt_number=self._attempt_counts[work_item_id],
        )
        self._claims[work_item_id] = claim
        state = self._work_items.get(work_item_id)
        if state is not None:
            updated = WorkItem(
                work_item_id=state.work_item.work_item_id,
                workflow_name=state.work_item.workflow_name,
                workflow_version=state.work_item.workflow_version,
                work_item_type=state.work_item.work_item_type,
                current_state=state.work_item.current_state,
                custom_fields=state.work_item.custom_fields,
                needs_review=state.work_item.needs_review,
                not_before=state.work_item.not_before,
                last_event_seq=state.work_item.last_event_seq,
                last_event_at=state.work_item.last_event_at,
                next_event_seq=state.work_item.next_event_seq,
                claimed_by=actor_id,
                claim_expires_at=claim.expires_at,
            )
            state.work_item = updated
        return claim

    def release_claim(self, work_item_id: uuid.UUID, actor_id: str, **kwargs) -> None:
        self._claims.pop(work_item_id, None)
        state = self._work_items.get(work_item_id)
        if state is not None:
            updated = WorkItem(
                work_item_id=state.work_item.work_item_id,
                workflow_name=state.work_item.workflow_name,
                workflow_version=state.work_item.workflow_version,
                work_item_type=state.work_item.work_item_type,
                current_state=state.work_item.current_state,
                custom_fields=state.work_item.custom_fields,
                needs_review=state.work_item.needs_review,
                not_before=state.work_item.not_before,
                last_event_seq=state.work_item.last_event_seq,
                last_event_at=state.work_item.last_event_at,
                next_event_seq=state.work_item.next_event_seq,
                claimed_by=None,
                claim_expires_at=None,
            )
            state.work_item = updated

    def read_events(
        self, *, work_item_id=None, transition=None, limit=100, **kwargs
    ) -> list[Event]:
        if work_item_id is not None:
            state = self._work_items.get(work_item_id)
            if state is None:
                return []
            events = state.events
            if transition is not None:
                events = [e for e in events if e.transition == transition]
            return events[-limit:]
        all_events = []
        for s in self._work_items.values():
            all_events.extend(s.events)
        if transition is not None:
            all_events = [e for e in all_events if e.transition == transition]
        return all_events[-limit:]

    def query_work_items(self, *, current_states=None, page_size=100, **kwargs) -> QueryPage:
        items = []
        for state in self._work_items.values():
            wi = state.work_item
            if current_states and wi.current_state not in current_states:
                continue
            if kwargs.get("claimable_now") and wi.claimed_by is not None:
                continue
            if kwargs.get("workflow_name") and wi.workflow_name != kwargs["workflow_name"]:
                continue
            items.append(wi)
        return QueryPage(items=items[:page_size], cursor=None, has_more=False)
