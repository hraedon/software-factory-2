from __future__ import annotations

from factory.pre_gate import pre_gate_implementation


class TestPreGateImplementation:
    def test_passes_on_clean_artifact(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert result.passed
        assert result.mypy_passed
        assert result.ruff_passed
        assert result.diagnostics == []

    def test_fails_on_mypy_error(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    pass\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert not result.passed
        assert not result.mypy_passed

    def test_fails_on_ruff_error(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    x=1+2\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert not result.passed
        assert not result.ruff_passed

    def test_skips_mypy_without_interface(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    return 'hello'\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=None)
        assert result.passed
        assert result.mypy_passed
        assert result.ruff_passed

    def test_passes_with_dependency(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text(
            "from certificate_model import Certificate, "
            "parse_certificate\n"
            "def hello() -> Certificate | None:\n"
            "    return None\n"
        )
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text(
            "from certificate_model import Certificate, "
            "parse_certificate\n"
            "def hello() -> Certificate | None: ...\n"
        )
        dep_pyi = tmp_path / "dep_certificate_model.pyi"
        dep_pyi.write_text(
            "class Certificate:\n"
            "    subject: str\n"
            "    issuer: str\n\n"
            "class MalformedCertificateError:\n"
            "    message: str\n\n"
            "def parse_certificate("
            "der_bytes: bytes"
            ") -> Certificate | MalformedCertificateError: ...\n"
        )
        result = pre_gate_implementation(
            artifact,
            interface_pyi_path=interface_pyi,
            dependency_pyi_paths=[("certificate_model", dep_pyi)],
        )
        assert result.mypy_passed
