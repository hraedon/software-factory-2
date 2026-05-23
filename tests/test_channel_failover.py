from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from factory.channel import InvocationResult
from factory.config import FactoryConfig, RoleConfig
from factory.constants import CHANNEL_OPENCODE, ROLE_IMPLEMENTER
from factory.jury import _invoke_juror
from factory.runner import _should_failover
from factory.runtime import PipelineRuntime


class TestShouldFailover:
    def test_success_returns_false(self):
        result = InvocationResult(success=True)
        assert _should_failover(result) is False

    def test_empty_output_returns_true(self):
        result = InvocationResult(success=False, error_message="Empty output from opencode")
        assert _should_failover(result) is True

    def test_nonzero_exit_model_error_returns_false(self):
        result = InvocationResult(success=False, exit_code=1)
        assert _should_failover(result) is False

    def test_exit_code_126_returns_true(self):
        result = InvocationResult(success=False, exit_code=126)
        assert _should_failover(result) is True

    def test_exit_code_127_returns_true(self):
        result = InvocationResult(success=False, exit_code=127)
        assert _should_failover(result) is True

    def test_tool_not_found_returns_true(self):
        result = InvocationResult(success=False, error_message="gemini not found in PATH")
        assert _should_failover(result) is True

    def test_connection_error_returns_true(self):
        result = InvocationResult(success=False, error_message="connection refused")
        assert _should_failover(result) is True

    def test_timeout_in_message_returns_true(self):
        result = InvocationResult(success=False, error_message="request timeout")
        assert _should_failover(result) is True

    def test_generic_error_returns_false(self):
        result = InvocationResult(success=False, error_message="some random failure")
        assert _should_failover(result) is False


class TestFallbackChannelForRole:
    def test_no_fallback_returns_none(self):
        config = FactoryConfig.phase3()
        runtime = PipelineRuntime(sub=MagicMock(), config=config, channels={})
        assert runtime.fallback_channel_for_role(ROLE_IMPLEMENTER) is None

    def test_fallback_present_returns_channel(self):
        primary = MagicMock()
        primary.name = CHANNEL_OPENCODE
        fallback = MagicMock()
        fallback.name = "claude-code"
        config = FactoryConfig.phase3()
        # Patch roles to include fallback
        roles = list(config.roles)
        for i, rc in enumerate(roles):
            if rc.role == ROLE_IMPLEMENTER:
                roles[i] = RoleConfig(
                    role=rc.role,
                    channel=rc.channel,
                    model=rc.model,
                    fallback_channel="claude-code",
                    fallback_model="claude-3-7-sonnet",
                )
        config = FactoryConfig(**{**config.__dict__, "roles": tuple(roles)})
        runtime = PipelineRuntime(
            sub=MagicMock(),
            config=config,
            channels={CHANNEL_OPENCODE: primary, "claude-code": fallback},
        )
        result = runtime.fallback_channel_for_role(ROLE_IMPLEMENTER)
        assert result is fallback

    def test_fallback_not_registered_returns_none(self):
        primary = MagicMock()
        primary.name = CHANNEL_OPENCODE
        config = FactoryConfig.phase3()
        roles = list(config.roles)
        for i, rc in enumerate(roles):
            if rc.role == ROLE_IMPLEMENTER:
                roles[i] = RoleConfig(
                    role=rc.role,
                    channel=rc.channel,
                    model=rc.model,
                    fallback_channel="unregistered-channel",
                )
        config = FactoryConfig(**{**config.__dict__, "roles": tuple(roles)})
        runtime = PipelineRuntime(
            sub=MagicMock(),
            config=config,
            channels={CHANNEL_OPENCODE: primary},
        )
        assert runtime.fallback_channel_for_role(ROLE_IMPLEMENTER) is None


class TestJurorFailover:
    def test_primary_success_no_fallback_invoked(self, tmp_path: Path):
        primary = MagicMock()
        primary.family = "fireworks"
        primary.invoke.return_value = InvocationResult(
            success=True, artifact_name="vote.json", family="fireworks"
        )
        fallback = MagicMock()
        ch_outputs = tmp_path / "primary"
        ch_outputs.mkdir()
        (ch_outputs / "vote.json").write_text('{"passed": true, "rationale": "ok"}')

        vote = _invoke_juror(
            "primary",
            primary,
            "prompt",
            tmp_path,
            30,
            fallback_channel=fallback,
        )
        assert vote.passed is True
        assert vote.channel == "primary"
        fallback.invoke.assert_not_called()

    def test_primary_failure_uses_fallback(self, tmp_path: Path):
        primary = MagicMock()
        primary.family = "fireworks"
        primary.invoke.return_value = InvocationResult(success=False, error_message="Empty output")
        fallback = MagicMock()
        fallback.family = "anthropic"
        fallback.invoke.return_value = InvocationResult(
            success=True, artifact_name="vote.json", family="anthropic"
        )
        fb_dir = tmp_path / "primary_fb"
        fb_dir.mkdir()
        (fb_dir / "vote.json").write_text('{"passed": true, "rationale": "fallback ok"}')

        vote = _invoke_juror(
            "primary",
            primary,
            "prompt",
            tmp_path,
            30,
            fallback_channel=fallback,
            fallback_model="claude-3-7-sonnet",
        )
        assert vote.passed is True
        assert vote.channel == "primary_fb"
        assert vote.family == "anthropic"
        fallback.invoke.assert_called_once()
        _, kwargs = fallback.invoke.call_args
        assert kwargs["model_override"] == "claude-3-7-sonnet"

    def test_both_primary_and_fallback_fail(self, tmp_path: Path):
        primary = MagicMock()
        primary.family = "fireworks"
        primary.invoke.return_value = InvocationResult(success=False, error_message="Empty output")
        fallback = MagicMock()
        fallback.family = "anthropic"
        fallback.invoke.return_value = InvocationResult(success=False, error_message="Timeout")

        vote = _invoke_juror(
            "primary",
            primary,
            "prompt",
            tmp_path,
            30,
            fallback_channel=fallback,
        )
        assert vote.passed is False
        assert vote.channel == "primary_fb"
        assert "Timeout" in vote.rationale

    def test_no_fallback_on_primary_failure(self, tmp_path: Path):
        primary = MagicMock()
        primary.family = "fireworks"
        primary.invoke.return_value = InvocationResult(success=False, error_message="Empty output")

        vote = _invoke_juror(
            "primary",
            primary,
            "prompt",
            tmp_path,
            30,
        )
        assert vote.passed is False
        assert vote.channel == "primary"
