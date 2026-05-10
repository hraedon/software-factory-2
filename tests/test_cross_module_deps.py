from __future__ import annotations

import tempfile
import textwrap
from pathlib import Path

from factory.config import FactoryConfig
from factory.constants import (
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_INTERFACE_REF,
)
from factory.gate import (
    evaluate_implementation,
    evaluate_test_suite,
)
from factory.pre_gate import copy_dependency_pyis
from factory.runtime import PipelineRuntime
from factory.scheduler import _ensure_downstream_item


class TestModuleNameResolution:
    def test_dependency_pyi_named_artifact_gets_correct_module_name(self, tmp_path):
        artifact_pyi = tmp_path / "artifact.pyi"
        artifact_pyi.write_text("class Certificate:\n    subject_dn: str\n")
        test_suite = tmp_path / "test_tls.py"
        test_suite.write_text(
            "from interface import scan_host\n"
            "from certificate_model import Certificate\n\n"
            "def test_scan():\n    assert scan_host is not None\n"
        )
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def scan_host(host: str) -> dict: ...\n")
        result = evaluate_test_suite(
            test_suite,
            interface_ref_pyi_path=interface_pyi,
            dependency_pyi_paths=[("certificate_model", artifact_pyi)],
        )
        assert result.passed, f"Expected pass, got: {result.diagnostics}"

    def test_copy_dependency_pyis_uses_module_name(self, tmp_path):
        artifact_pyi = tmp_path / "artifact.pyi"
        artifact_pyi.write_text("class Certificate:\n    subject_dn: str\n")
        with tempfile.TemporaryDirectory(prefix="sf2_test_") as tmpdir:
            copy_dependency_pyis(
                tmpdir,
                [("certificate_model", artifact_pyi)],
            )
            module_file = Path(tmpdir) / "certificate_model.py"
            assert module_file.exists()
            assert "Certificate" in module_file.read_text()

    def test_extract_module_name_from_spec(self):
        from factory.dep_resolution import _extract_module_name_from_spec

        spec = "# Interface Specification: Certificate Model\n\n## AC-01\nFoo"
        assert _extract_module_name_from_spec(spec) == "certificate_model"

    def test_extract_module_name_from_spec_multi_word(self):
        from factory.dep_resolution import _extract_module_name_from_spec

        spec = "# Interface Specification: TLS Scanner Utils\n\n## AC-01\nBar"
        assert _extract_module_name_from_spec(spec) == "tls_scanner_utils"

    def test_extract_module_name_from_spec_no_title(self):
        from factory.dep_resolution import _extract_module_name_from_spec

        spec = "## AC-01\nNo title"
        assert _extract_module_name_from_spec(spec) is None


def _write(artifact_dir: Path, name: str, content: str) -> Path:
    p = artifact_dir / name
    p.write_text(textwrap.dedent(content))
    return p


class TestDependencyParsing:
    def test_parse_dependency_refs_from_spec(self):
        from populate_work_items import _parse_dependency_refs

        spec = textwrap.dedent("""\
            # Interface Specification: FR-02 TLS Scanning

            ## Dependencies
            - `interface_ref`: `certificate_model`

            ## AC-01: Scan Input
            A function scan_host() must exist.
        """)
        refs = _parse_dependency_refs(spec)
        assert refs == ["certificate_model"]

    def test_parse_multiple_dependencies(self):
        from populate_work_items import _parse_dependency_refs

        spec = textwrap.dedent("""\
            # Interface Specification: FR-02

            ## Dependencies
            - `interface_ref`: `certificate_model`
            - `interface_ref`: `tls_utils`

            ## AC-01: Scan Input
            A function scan_host() must exist.
        """)
        refs = _parse_dependency_refs(spec)
        assert refs == ["certificate_model", "tls_utils"]

    def test_parse_no_dependencies(self):
        from populate_work_items import _parse_dependency_refs

        spec = textwrap.dedent("""\
            # Interface Specification: Certificate Model

            ## AC-01: Subject DN
            The Certificate dataclass must expose the subject DN.
        """)
        refs = _parse_dependency_refs(spec)
        assert refs == []

    def test_parse_dependency_section_ends_at_next_heading(self):
        from populate_work_items import _parse_dependency_refs

        spec = textwrap.dedent("""\
            # Interface Specification: FR-02

            ## Dependencies
            - `interface_ref`: `certificate_model`

            ## AC-01: Scan Input
            A function scan_host() must exist.
        """)
        refs = _parse_dependency_refs(spec)
        assert refs == ["certificate_model"]


class TestCrossModuleImportInCollect:
    def test_pytest_collect_with_dependency_modules(self, tmp_path):
        cert_model_pyi = _write(
            tmp_path,
            "certificate_model.pyi",
            """\
            from datetime import datetime

            class Certificate:
                subject_dn: str
                issuer_dn: str
                not_before: datetime
                not_after: datetime
                fingerprint_sha256: str

            class MalformedCertificateError(Exception):
                message: str
            """,
        )
        test_suite = _write(
            tmp_path,
            "test_tls_scan.py",
            """\
            from interface import scan_host
            from certificate_model import Certificate

            def test_scan_success():
                result = scan_host("example.com", 443)
                assert result is not None
            """,
        )
        interface_pyi = _write(
            tmp_path,
            "interface.pyi",
            """\
            from certificate_model import Certificate
            from typing import Union

            def scan_host(hostname: str, port: int = 443) -> Union[dict, str]: ...
            """,
        )
        result = evaluate_test_suite(
            test_suite,
            interface_ref_pyi_path=interface_pyi,
            dependency_pyi_paths=[("certificate_model", cert_model_pyi)],
        )
        assert result.passed, f"Expected pass, got: {result.diagnostics}"

    def test_pytest_collect_fails_without_dependency(self, tmp_path):
        test_suite = _write(
            tmp_path,
            "test_tls_scan.py",
            """\
            from interface import scan_host
            from certificate_model import Certificate

            def test_scan_success():
                result = scan_host("example.com", 443)
                assert result is not None
            """,
        )
        interface_pyi = _write(
            tmp_path,
            "interface.pyi",
            """\
            from certificate_model import Certificate
            from typing import Union

            def scan_host(hostname: str, port: int = 443) -> Union[dict, str]: ...
            """,
        )
        result = evaluate_test_suite(
            test_suite,
            interface_ref_pyi_path=interface_pyi,
            dependency_pyi_paths=[],
        )
        assert not result.passed
        assert result.gate_name == "test_suite_collect"
        diag = " ".join(result.diagnostics).lower()
        assert "import" in diag or "error" in diag

    def test_pytest_collect_multiple_dependency_modules(self, tmp_path):
        cert_model_pyi = _write(
            tmp_path,
            "certificate_model.pyi",
            """\
            class Certificate:
                subject_dn: str
            """,
        )
        tls_utils_pyi = _write(
            tmp_path,
            "tls_utils.pyi",
            """\
            def handshake(host: str, port: int) -> dict: ...
            """,
        )
        test_suite = _write(
            tmp_path,
            "test_scan.py",
            """\
            from interface import scan_host
            from certificate_model import Certificate
            from tls_utils import handshake

            def test_combined():
                assert True
            """,
        )
        interface_pyi = _write(
            tmp_path,
            "interface.pyi",
            """\
            def scan_host(hostname: str, port: int = 443) -> dict: ...
            """,
        )
        result = evaluate_test_suite(
            test_suite,
            interface_ref_pyi_path=interface_pyi,
            dependency_pyi_paths=[
                ("certificate_model", cert_model_pyi),
                ("tls_utils", tls_utils_pyi),
            ],
        )
        assert result.passed, f"Expected pass, got: {result.diagnostics}"


class TestCrossModuleImportInImplementation:
    def test_implementation_mypy_with_dependency(self, tmp_path):
        cert_model_pyi = _write(
            tmp_path,
            "certificate_model.pyi",
            """\
            class Certificate:
                subject_dn: str
                issuer_dn: str
            """,
        )
        impl = _write(
            tmp_path,
            "impl.py",
            """\
            from certificate_model import Certificate

            def scan_host(hostname: str, port: int = 443) -> dict[str, object]:
                return {"host": hostname, "port": port}
            """,
        )
        test_suite = _write(
            tmp_path,
            "test_scan.py",
            """\
            from impl import scan_host

            def test_scan():
                result = scan_host("example.com", 443)
                assert result is not None
            """,
        )
        interface_pyi = _write(
            tmp_path,
            "interface.pyi",
            """\
            from certificate_model import Certificate

            def scan_host(hostname: str, port: int = 443) -> dict[str, object]: ...
            """,
        )
        result = evaluate_implementation(
            impl,
            test_suite_path=test_suite,
            interface_pyi_path=interface_pyi,
            dependency_pyi_paths=[("certificate_model", cert_model_pyi)],
        )
        assert result.passed, f"Expected pass, got: {result.diagnostics}"

    def test_implementation_pytest_with_dependency(self, tmp_path):
        cert_model_pyi = _write(
            tmp_path,
            "certificate_model.pyi",
            """\
            class Certificate:
                subject_dn: str
            """,
        )
        impl = _write(
            tmp_path,
            "compute.py",
            """\
            from certificate_model import Certificate

            def make_cert(subject: str) -> str:
                return subject
            """,
        )
        test_suite = _write(
            tmp_path,
            "test_compute.py",
            """\
            from compute import make_cert

            def test_make_cert():
                result = make_cert("test")
                assert result == "test"
            """,
        )
        interface_pyi = _write(
            tmp_path,
            "interface.pyi",
            """\
            from certificate_model import Certificate

            def make_cert(subject: str) -> str: ...
            """,
        )
        result = evaluate_implementation(
            impl,
            test_suite_path=test_suite,
            interface_pyi_path=interface_pyi,
            dependency_pyi_paths=[("certificate_model", cert_model_pyi)],
        )
        assert result.passed, f"Expected pass, got: {result.diagnostics}"


class TestSchedulerDependencyPropagation:
    def test_dependency_refs_propagated_to_test_suite(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(workspace_root=workspace_root, workflow_version=2)

        source, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
                CUSTOM_FIELD_DEPENDENCY_REFS: ["dep-uuid-1", "dep-uuid-2"],
            },
        )

        handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, source, handoff)

        ts_page = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        assert len(ts_page.items) == 1
        ts = ts_page.items[0]
        assert ts.custom_fields.get(CUSTOM_FIELD_DEPENDENCY_REFS) == [
            "dep-uuid-1",
            "dep-uuid-2",
        ]

    def test_dependency_refs_propagated_to_implementation(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(workspace_root=workspace_root, workflow_version=2)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
            },
        )
        iface_id = str(iface.work_item_id)

        ts, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="test",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
                CUSTOM_FIELD_INTERFACE_REF: iface_id,
                CUSTOM_FIELD_DEPENDENCY_REFS: ["dep-uuid-1"],
            },
        )

        impl_handoff = {
            "next_type": "implementation",
            "link_type": "tested_by",
            "additional_links": ["implements"],
            "next_role": "implementer",
        }
        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, ts, impl_handoff)

        impl_page = mock_substrate.query_work_items(
            work_item_types=["implementation"],
            page_size=10,
        )
        assert len(impl_page.items) == 1
        impl = impl_page.items[0]
        deps = impl.custom_fields.get(CUSTOM_FIELD_DEPENDENCY_REFS)
        assert deps == ["dep-uuid-1"]

    def test_no_dependency_refs_propagated_when_empty(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(workspace_root=workspace_root, workflow_version=2)

        source, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
            },
        )

        handoff = {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        }

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, source, handoff)

        ts_page = mock_substrate.query_work_items(
            work_item_types=["test_suite"],
            page_size=10,
        )
        ts = ts_page.items[0]
        custom = ts.custom_fields or {}
        dep_refs = custom.get(CUSTOM_FIELD_DEPENDENCY_REFS)
        assert dep_refs is None or dep_refs == []
