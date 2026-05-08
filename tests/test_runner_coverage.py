from __future__ import annotations

import pytest

from factory.channel import InvocationResult
from factory.config import FactoryConfig, RoleConfig
from factory.runner import _create_channel, _role_for_type, process_work_item
from factory.runtime import PipelineRuntime


class TestCreateChannel:
    def test_default_config_returns_claude_code(self):
        config = FactoryConfig()
        channel = _create_channel(config)
        assert channel.name == "claude-code"

    def test_phase1_config_returns_claude_code(self):
        config = FactoryConfig(
            roles=(
                RoleConfig(role="interface_architect", channel="claude-code"),
                RoleConfig(role="mechanical_gate", channel="code"),
            ),
        )
        channel = _create_channel(config)
        assert channel.name == "claude-code"

    def test_phase2_opencode_config_returns_opencode(self):
        config = FactoryConfig(
            roles=(
                RoleConfig(role="interface_architect", channel="opencode"),
                RoleConfig(role="test_author", channel="opencode"),
                RoleConfig(role="implementer", channel="opencode"),
                RoleConfig(role="mechanical_gate", channel="code"),
            ),
        )
        channel = _create_channel(config)
        assert channel.name == "opencode"

    def test_multi_model_channel_raises(self):
        config = FactoryConfig(
            roles=(
                RoleConfig(role="interface_architect", channel="claude-code"),
                RoleConfig(role="implementer", channel="opencode"),
            ),
        )
        with pytest.raises(NotImplementedError):
            _create_channel(config)

    def test_unknown_single_channel_raises_value_error(self):
        config = FactoryConfig(
            roles=(RoleConfig(role="interface_architect", channel="kimi-api"),),
        )
        with pytest.raises(ValueError, match="Unknown channel: kimi-api"):
            _create_channel(config)


class TestRoleForType:
    def test_known_type_returns_role(self):
        config = FactoryConfig()
        assert _role_for_type("interface_spec", config) == "interface_architect"

    def test_unknown_type_returns_none(self):
        config = FactoryConfig()
        assert _role_for_type("nonexistent", config) is None

    def test_phase2_type_to_role(self):
        config = FactoryConfig(
            worker_roles=FactoryConfig.PHASE2_WORKER_ROLES,
            type_to_role=FactoryConfig.PHASE2_TYPE_TO_ROLE,
            roles=FactoryConfig.PHASE2_ROLES,
        )
        assert _role_for_type("interface_spec", config) == "interface_architect"
        assert _role_for_type("test_suite", config) == "test_author"
        assert _role_for_type("implementation", config) == "implementer"


class TestCannotProceedWithoutJson:
    def test_cannot_proceed_no_json_transitions_channel_fail(self, mock_substrate, workspace_root):
        class _CannotProceedNoJsonChannel:
            def __init__(self):
                self._name = "cp-no-json"
                self._family = "test"

            @property
            def name(self) -> str:
                return self._name

            @property
            def family(self) -> str:
                return self._family

            def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
                return InvocationResult(
                    success=False, artifact_name=None, error_message="cannot_proceed"
                )

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "No JSON", "ac_ids": ["AC-01"]},
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
        runtime = PipelineRuntime(
            sub=mock_substrate,
            config=config,
            spec_content="No JSON",
            channel=_CannotProceedNoJsonChannel(),
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        assert updated.claimed_by is None
