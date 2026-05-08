from __future__ import annotations

from factory.opencode_channel import (
    OpenCodeChannel,
    _derive_family,
)


class TestDeriveFamily:
    def test_zai_prefix(self):
        assert _derive_family("zai-coding-plan/glm-5.1") == "zai"

    def test_ollama_prefix(self):
        assert _derive_family("ollama-cloud/deepseek-v4-pro") == "ollama"

    def test_fireworks_prefix(self):
        assert _derive_family("fireworks-ai/accounts/fireworks/models/deepseek-v4-pro") == "fireworks"

    def test_opencode_prefix(self):
        assert _derive_family("opencode/nemotron-3-super-free") == "opencode-free"

    def test_mac_studio_prefix(self):
        assert _derive_family("mac-studio-lms/llama-3.1-8b") == "local-lms"

    def test_unknown_prefix(self):
        assert _derive_family("custom-provider/model") == "custom-provider"

    def test_none(self):
        assert _derive_family(None) == "opencode"

    def test_empty_string(self):
        assert _derive_family("") == "opencode"


class TestArtifactExtension:
    def test_interface_architect_gets_pyi(self):
        assert OpenCodeChannel._artifact_extension_for_role("interface_architect") == ".pyi"

    def test_test_author_gets_py(self):
        assert OpenCodeChannel._artifact_extension_for_role("test_author") == ".py"

    def test_implementer_gets_py(self):
        assert OpenCodeChannel._artifact_extension_for_role("implementer") == ".py"

    def test_unknown_role_gets_py(self):
        assert OpenCodeChannel._artifact_extension_for_role("unknown") == ".py"


class TestChannelProperties:
    def test_name(self):
        channel = OpenCodeChannel.__new__(OpenCodeChannel)
        assert channel.name == "opencode"

    def test_default_family(self):
        channel = OpenCodeChannel.__new__(OpenCodeChannel)
        channel._family = "opencode"
        assert channel.family == "opencode"
