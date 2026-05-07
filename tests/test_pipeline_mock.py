from __future__ import annotations

import json

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.context import derive_context, render_prompt
from factory.gate_process import process_gate_item
from factory.runner import process_work_item


class FakeChannel:
    def __init__(self, ac_ids: list[str] | None = None):
        self._name = "fake"
        self._family = "test"
        self._ac_ids = ac_ids or []
        self._invocations: list[tuple[str, str, object, object]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        self._invocations.append((role, prompt, inputs_dir, outputs_dir))
        outputs_dir.mkdir(parents=True, exist_ok=True)
        ac_doc = ", ".join(self._ac_ids) if self._ac_ids else "AC-01"
        content = f'def foo(x: int) -> str:\n    """Satisfies {ac_doc}."""\n    ...\n'
        (outputs_dir / "artifact.pyi").write_text(content)
        return InvocationResult(success=True, artifact_name="artifact.pyi")


class CannotProceedChannel:
    def __init__(self):
        self._name = "cp-fake"
        self._family = "test"

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        outputs_dir.mkdir(parents=True, exist_ok=True)
        cp = {
            "status": "cannot_proceed",
            "reason": "Spec is ambiguous",
            "gaps": ["Conflicting AC"],
        }
        (outputs_dir / "cannot_proceed.json").write_text(json.dumps(cp))
        return InvocationResult(success=False, artifact_name=None, error_message="cannot_proceed")


class TestMockSubstrateFullPipeline:
    def test_new_to_locked(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test spec", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")

        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        config = FactoryConfig(workspace_root=workspace_root)
        channel = FakeChannel(ac_ids=["AC-01"])
        process_work_item(
            mock_substrate,
            config,
            channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Test spec",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "gating"

        mock_substrate.register_actor_role("test-gate", "mechanical_gate")
        gate_claim = mock_substrate.acquire_claim(wi.work_item_id, "test-gate")
        fresh = mock_substrate.get_work_item(wi.work_item_id)
        process_gate_item(mock_substrate, config, fresh, "test-gate", gate_claim)

        final = mock_substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "locked"

    def test_gate_fail_returns_to_new(self, mock_substrate, workspace_root, tmp_path):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01", "AC-02"]},
        )
        artifact_path = tmp_path / "partial.pyi"
        artifact_path.write_text('"""Satisfies AC-01."""\ndef foo() -> int: ...\n')

        mock_substrate.register_actor_role("test-worker", "interface_architect")
        mock_substrate.transition(wi.work_item_id, "claim", "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            custom_fields={"artifact_path": str(artifact_path), "artifact_hash": "abc"},
        )

        mock_substrate.register_actor_role("test-gate", "mechanical_gate")
        gate_claim = mock_substrate.acquire_claim(wi.work_item_id, "test-gate")
        fresh = mock_substrate.get_work_item(wi.work_item_id)

        config = FactoryConfig(workspace_root=workspace_root)
        process_gate_item(mock_substrate, config, fresh, "test-gate", gate_claim)

        final = mock_substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "new"

    def test_cannot_proceed_terminates(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Ambiguous", "ac_ids": ["AC-99"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        config = FactoryConfig(workspace_root=workspace_root)
        channel = CannotProceedChannel()
        process_work_item(
            mock_substrate,
            config,
            channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Ambiguous",
        )

        final = mock_substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "cannot_proceed"

    def test_derive_context_with_mock(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Parse range", "ac_ids": ["AC-01", "AC-02"]},
        )
        ctx = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content="Parse range",
        )
        assert ctx.context_hash is not None
        assert ctx.ac_ids == ["AC-01", "AC-02"]
        prompt = render_prompt(ctx)
        assert "Parse range" in prompt
        assert "AC-01" in prompt

    def test_context_determinism(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Same content", "ac_ids": ["AC-01"]},
        )
        ctx1 = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content="Same content",
        )
        ctx2 = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content="Same content",
        )
        assert ctx1.context_hash == ctx2.context_hash
