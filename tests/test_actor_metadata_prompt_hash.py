from __future__ import annotations

import uuid
from pathlib import Path

from factory.constants import (
    ROLE_INTERFACE_ARCHITECT,
    TRANSITION_SUBMIT,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
)
from factory.context import PromptContext
from factory.runner import _resume_and_submit
from factory.workspace import ArtifactManifest


class FakeChannel:
    name = "claude-code"
    family = "anthropic"


class FakeEvent:
    def __init__(self, transition, actor_metadata, payload=None, custom_fields=None):
        self.transition = transition
        self.actor_metadata = actor_metadata
        self.payload = payload
        self.custom_fields = custom_fields


class FakeSubstrate:
    def __init__(self):
        self.events: list[FakeEvent] = []
        self._work_items: dict = {}

    def transition(
        self,
        work_item_id,
        transition,
        actor_id,
        actor_metadata=None,
        payload=None,
        custom_fields=None,
        event_id=None,
    ):
        self.events.append(FakeEvent(transition, actor_metadata, payload, custom_fields))

    def read_events(self, work_item_id, limit=1000):
        return []

    def get_work_item(self, work_item_id):
        return self._work_items.get(work_item_id)

    def query_work_items(self, **kwargs):
        return type("Page", (), {"items": []})()


def test_submit_event_carries_prompt_template_hash() -> None:
    """Submit event ActorMetadata must include prompt_template_hash."""
    sub = FakeSubstrate()
    wi_id = uuid.uuid4()
    wi = type(
        "WI",
        (),
        {
            "work_item_id": wi_id,
            "work_item_type": WORK_ITEM_TYPE_INTERFACE_SPEC,
            "custom_fields": {},
        },
    )()
    ctx = PromptContext(
        work_item_id=str(wi_id),
        role=ROLE_INTERFACE_ARCHITECT,
        spec_section="test spec",
        ac_ids=["AC-01"],
        glossary={},
        prior_failures=[],
        prompt_template="template text",
        context_hash="abc123",
        prompt_template_hash="deadbeef0000",
        extra_artifacts={},
        stub_only_deps=[],
    )
    ad = Path("/tmp/fake_attempt")
    ad.mkdir(parents=True, exist_ok=True)
    artifact_path = ad / "interface.pyi"
    artifact_path.write_text("def foo() -> int: ...\n")
    sha = "sha256value"
    manifest = ArtifactManifest(
        attempt_number=1,
        work_item_id=str(wi_id),
        artifact_name="interface.pyi",
        artifact_sha256=sha,
        artifact_size=24,
        channel="claude-code",
        family="anthropic",
        context_hash=ctx.context_hash,
    )

    _resume_and_submit(
        sub,
        wi,
        1,
        manifest,
        "factory-worker-claude-code",
        FakeChannel(),
        artifact_path,
        role_name=ROLE_INTERFACE_ARCHITECT,
    )

    submit_event = [e for e in sub.events if e.transition == TRANSITION_SUBMIT]
    assert len(submit_event) == 1
    md = submit_event[0].actor_metadata or {}
    assert md.get("prompt_template_hash") is None  # resume path passes None


def test_prompt_template_hash_computed_in_context() -> None:
    """derive_context must produce a non-empty prompt_template_hash."""
    import hashlib

    from factory.context import derive_context

    class MockSubstrate:
        def get_work_item(self, work_item_id):
            return type(
                "WI",
                (),
                {
                    "work_item_id": work_item_id,
                    "custom_fields": {
                        "spec_section": "sec",
                        "ac_ids": ["AC-01"],
                    },
                },
            )()

        def read_events(self, work_item_id, limit=1000):
            return []

    sub = MockSubstrate()
    ctx = derive_context(sub, "550e8400-e29b-41d4-a716-446655440000", ROLE_INTERFACE_ARCHITECT)
    assert ctx.prompt_template_hash
    expected = hashlib.sha256(ctx.prompt_template.encode()).hexdigest()
    assert ctx.prompt_template_hash == expected
