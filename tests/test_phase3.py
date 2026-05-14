from __future__ import annotations

import pytest

from factory.config import FactoryConfig, RoleConfig
from factory.constants import (
    CHANNEL_CLAUDE_CODE,
    CHANNEL_GEMINI_CLI,
    CHANNEL_OPENCODE,
    FAMILY_GEMINI,
    FAMILY_OPENCODE,
    ROLE_IMPLEMENTER,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_MECHANICAL_GATE,
    ROLE_TEST_AUTHOR,
)
from factory.gemini_channel import GeminiCLIChannel
from factory.runner import _create_channels


class TestPhase3Config:
    def test_phase3_config_has_three_model_channels(self):
        config = FactoryConfig.phase3()
        model_channels = set(rc.channel for rc in config.roles if rc.channel != "code")
        assert model_channels == {CHANNEL_OPENCODE}

    def test_phase3_config_workflow_version(self):
        config = FactoryConfig.phase3()
        assert config.workflow_version == 3

    def test_phase3_role_channel_binding(self):
        config = FactoryConfig.phase3()
        assert config.get_role_config(ROLE_INTERFACE_ARCHITECT).channel == CHANNEL_OPENCODE
        assert config.get_role_config(ROLE_TEST_AUTHOR).channel == CHANNEL_OPENCODE
        assert config.get_role_config(ROLE_IMPLEMENTER).channel == CHANNEL_OPENCODE
        assert config.get_role_config(ROLE_MECHANICAL_GATE).channel == "code"

    def test_phase3_model_assignment(self):
        config = FactoryConfig.phase3()
        interface_architect = config.get_role_config(ROLE_INTERFACE_ARCHITECT)
        assert interface_architect.model is not None
        assert "fireworks" in interface_architect.model
        test_author = config.get_role_config(ROLE_TEST_AUTHOR)
        assert test_author.model is not None
        assert "fireworks" in test_author.model
        implementer = config.get_role_config(ROLE_IMPLEMENTER)
        assert implementer.model is not None
        assert "fireworks" in implementer.model

    def test_phase3_family_derivation(self):
        config = FactoryConfig.phase3()
        assert config.get_role_config(ROLE_INTERFACE_ARCHITECT).family == FAMILY_OPENCODE
        assert config.get_role_config(ROLE_TEST_AUTHOR).family == FAMILY_OPENCODE
        assert config.get_role_config(ROLE_IMPLEMENTER).family == FAMILY_OPENCODE


class TestCreateChannels:
    def test_single_channel_creates_dict(self):
        config = FactoryConfig.phase2()
        channels = _create_channels(config)
        assert len(channels) == 1
        assert CHANNEL_CLAUDE_CODE in channels

    def test_multi_channel_creates_dict(self):
        config = FactoryConfig.phase3()
        channels = _create_channels(config)
        assert len(channels) == 1
        assert CHANNEL_OPENCODE in channels

    def test_unknown_channel_raises(self):
        config = FactoryConfig(
            roles=(
                RoleConfig(role=ROLE_INTERFACE_ARCHITECT, channel="nonexistent"),
                RoleConfig(role=ROLE_MECHANICAL_GATE, channel="code"),
            ),
        )
        with pytest.raises(ValueError, match="Unknown channel"):
            _create_channels(config)

    def test_no_model_channels_raises(self):
        config = FactoryConfig(
            roles=(RoleConfig(role=ROLE_MECHANICAL_GATE, channel="code"),),
        )
        with pytest.raises(ValueError, match="No model channels"):
            _create_channels(config)


class TestGeminiCLIChannel:
    def test_name_property(self):
        config = FactoryConfig()
        ch = GeminiCLIChannel(config)
        assert ch.name == CHANNEL_GEMINI_CLI

    def test_family_property(self):
        config = FactoryConfig()
        ch = GeminiCLIChannel(config)
        assert ch.family == FAMILY_GEMINI

    def test_build_cmd_without_model(self):
        config = FactoryConfig()
        ch = GeminiCLIChannel(config)
        role_config = config.get_role_config(ROLE_INTERFACE_ARCHITECT)
        cmd = ch._build_cmd(role_config)
        assert cmd == ["gemini", "-p", "-", "--yolo", "--skip-trust"]

    def test_build_cmd_with_model(self):
        config = FactoryConfig()
        ch = GeminiCLIChannel(config)
        role_config = RoleConfig(
            role=ROLE_INTERFACE_ARCHITECT,
            channel=CHANNEL_GEMINI_CLI,
            model="gemini-2.5-pro",
        )
        cmd = ch._build_cmd(role_config)
        assert cmd == ["gemini", "-p", "-", "--yolo", "--skip-trust", "-m", "gemini-2.5-pro"]


class TestChannelForRole:
    def test_single_channel_fallback(self):
        from factory.runtime import PipelineRuntime

        class SimpleChannel:
            @property
            def name(self):
                return "mock"

            @property
            def family(self):
                return "test"

        sub_mock = object()
        config = FactoryConfig.phase2()
        ch = SimpleChannel()
        runtime = PipelineRuntime(sub=sub_mock, config=config, channel=ch)
        assert runtime.channel_for_role(ROLE_INTERFACE_ARCHITECT) is ch

    def test_multi_channel_selection(self):
        from factory.runtime import PipelineRuntime

        class FakeChannel:
            def __init__(self, name, family="test"):
                self._name = name
                self._family = family

            @property
            def name(self):
                return self._name

            @property
            def family(self):
                return self._family

        opencode_ch = FakeChannel(CHANNEL_OPENCODE, FAMILY_OPENCODE)
        sub_mock = object()
        config = FactoryConfig.phase3()
        runtime = PipelineRuntime(
            sub=sub_mock,
            config=config,
            channels={CHANNEL_OPENCODE: opencode_ch},
        )
        assert runtime.channel_for_role(ROLE_INTERFACE_ARCHITECT) is opencode_ch
        assert runtime.channel_for_role(ROLE_TEST_AUTHOR) is opencode_ch
        assert runtime.channel_for_role(ROLE_IMPLEMENTER) is opencode_ch

    def test_no_channel_raises(self):
        from factory.runtime import PipelineRuntime

        sub_mock = object()
        config = FactoryConfig()
        runtime = PipelineRuntime(sub=sub_mock, config=config)
        with pytest.raises(ValueError, match="No channel"):
            runtime.channel_for_role(ROLE_INTERFACE_ARCHITECT)


class TestCredentials:
    def test_load_credentials_missing_file(self, tmp_path):
        from factory.credentials import load_credentials

        result = load_credentials(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_load_credentials_valid(self, tmp_path):
        from factory.credentials import load_credentials

        cred_file = tmp_path / "credentials.yaml"
        cred_file.write_text("version: 1\nproviders:\n  fireworks:\n    api_key: fk-test123\n")
        result = load_credentials(cred_file)
        assert result == {"fireworks": {"api_key": "fk-test123"}}

    def test_get_provider_credential(self):
        from factory.credentials import get_provider_credential

        creds = {"fireworks": {"api_key": "fk-test123"}}
        assert get_provider_credential(creds, "fireworks") == "fk-test123"
        assert get_provider_credential(creds, "nonexistent") is None

    def test_inject_credentials_into_env(self):
        from factory.credentials import inject_credentials_into_env

        creds = {"fireworks": {"api_key": "fk-test123"}}
        env = inject_credentials_into_env(creds, "fireworks", env={})
        assert env["FIREWORKS_API_KEY"] == "fk-test123"

    def test_inject_credentials_unknown_provider(self):
        from factory.credentials import inject_credentials_into_env

        creds = {"fireworks": {"api_key": "fk-test123"}}
        env = inject_credentials_into_env(creds, "unknown", env={})
        assert "UNKNOWN_API_KEY" not in env

    def test_redact_value(self):
        from factory.credentials import redact_value

        assert "****" in redact_value("fk-test123456")
        assert "fk-t" in redact_value("fk-test123456")
        assert redact_value("short") == "****"
