from __future__ import annotations

from pathlib import Path

import pytest
from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runtime import PipelineRuntime

PHASE2_WORKFLOW = Path(__file__).parent.parent / "workflows" / "phase2.yaml"


def _claim_and_submit(
    sub: InMemorySubstrate,
    wi,
    role: str,
    artifact_path: str,
    artifact_hash: str = "abc",
):
    sub.transition(
        wi.work_item_id,
        "claim",
        "test-worker",
        actor_metadata={"role": role},
    )
    sub.transition(
        wi.work_item_id,
        "submit",
        "test-worker",
        actor_metadata={"role": role},
        custom_fields={
            "artifact_path": artifact_path,
            "artifact_hash": artifact_hash,
        },
    )


@pytest.fixture()
def mock_sub():
    sub = InMemorySubstrate()
    sub.register_workflow(PHASE2_WORKFLOW.read_text())
    yield sub
    sub.close()


@pytest.fixture()
def mock_config(tmp_path):
    return FactoryConfig(
        dsn="",
        project_name="test",
        hmac_key_path="",
        workspace_root=tmp_path / "work",
    )


def _make_and_submit(
    sub: InMemorySubstrate,
    work_item_type: str,
    custom_fields: dict,
    artifact_path: Path | None = None,
) -> tuple:
    wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=work_item_type,
        actor_id="test-creator",
        custom_fields=custom_fields,
    )
    sub.transition(
        wi.work_item_id,
        "claim",
        "test-worker",
        actor_metadata={"role": "test_author"},
    )
    submit_fields: dict = {}
    if artifact_path is not None:
        submit_fields["artifact_path"] = str(artifact_path)
        submit_fields["artifact_hash"] = "abc"
    sub.transition(
        wi.work_item_id,
        "submit",
        "test-worker",
        actor_metadata={"role": "test_author"},
        custom_fields=submit_fields,
    )
    sub.register_actor_role("test-gate", "mechanical_gate")
    claim = sub.acquire_claim(wi.work_item_id, "test-gate", ttl_seconds=300)
    fresh = sub.get_work_item(wi.work_item_id)
    return wi, fresh, claim


def _create_interface_spec(sub: InMemorySubstrate, artifact_path: str):
    iface_wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type="interface_spec",
        actor_id="test-creator",
        custom_fields={
            "spec_section": "S1",
            "ac_ids": ["AC-01"],
        },
    )
    _claim_and_submit(sub, iface_wi, "interface_architect", artifact_path)
    return iface_wi


def _create_test_suite(
    sub: InMemorySubstrate,
    iface_wi,
    artifact_path: str,
    iface_ref: str | None = None,
):
    ts_wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type="test_suite",
        actor_id="test-creator",
        custom_fields={
            "spec_section": "S1",
            "ac_ids": ["AC-01"],
            "interface_ref": iface_ref or str(iface_wi.work_item_id),
        },
    )
    _claim_and_submit(sub, ts_wi, "test_author", artifact_path)
    return ts_wi


def _gate_state(sub, work_item_id) -> tuple[str, dict]:
    wi = sub.get_work_item(work_item_id)
    return wi.current_state, wi.custom_fields or {}


class TestTestSuiteContractEnforcement:
    def test_interface_ref_no_artifact_path_is_gate_fail(self, mock_sub, mock_config, tmp_path):
        iface_wi = _create_interface_spec(mock_sub, artifact_path="")

        artifact = tmp_path / "test_suite.py"
        artifact.write_text("def test_something(): pass\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "test_suite",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, custom = _gate_state(mock_sub, wi.work_item_id)
        assert state == "new"
        diagnostics = custom.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "missing_artifact"

    def test_interface_ref_artifact_not_on_disk_is_gate_fail(self, mock_sub, mock_config, tmp_path):
        iface_wi = _create_interface_spec(mock_sub, "/nonexistent/path/interface.pyi")

        artifact = tmp_path / "test_suite.py"
        artifact.write_text("def test_something(): pass\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "test_suite",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, custom = _gate_state(mock_sub, wi.work_item_id)
        assert state == "new"
        diagnostics = custom.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "missing_artifact"

    def test_valid_interface_ref_proceeds_to_gate_evaluation(self, mock_sub, mock_config, tmp_path):
        iface_artifact = tmp_path / "iface.pyi"
        iface_artifact.write_text('"""Satisfies AC-01."""\ndef foo(x: int) -> str: ...\n')
        iface_wi = _create_interface_spec(mock_sub, str(iface_artifact))

        artifact = tmp_path / "test_suite.py"
        artifact.write_text("def test_something(): pass\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "test_suite",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, _ = _gate_state(mock_sub, wi.work_item_id)
        assert state in ("locked", "new")


class TestImplementationContractEnforcement:
    def test_interface_ref_no_artifact_path_is_gate_fail(self, mock_sub, mock_config, tmp_path):
        iface_wi = _create_interface_spec(mock_sub, artifact_path="")

        ts_artifact = tmp_path / "test_foo.py"
        ts_artifact.write_text("def test_foo(): pass\n")
        ts_wi = _create_test_suite(mock_sub, iface_wi, str(ts_artifact))

        artifact = tmp_path / "impl.py"
        artifact.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "implementation",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(ts_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, custom = _gate_state(mock_sub, wi.work_item_id)
        assert state == "new"
        diagnostics = custom.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "missing_artifact"

    def test_interface_ref_artifact_not_on_disk_is_gate_fail(self, mock_sub, mock_config, tmp_path):
        iface_wi = _create_interface_spec(mock_sub, "/nonexistent/iface.pyi")

        ts_artifact = tmp_path / "test_foo.py"
        ts_artifact.write_text("def test_foo(): pass\n")
        ts_wi = _create_test_suite(mock_sub, iface_wi, str(ts_artifact))

        artifact = tmp_path / "impl.py"
        artifact.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "implementation",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(ts_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, custom = _gate_state(mock_sub, wi.work_item_id)
        assert state == "new"
        diagnostics = custom.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "missing_artifact"

    def test_test_suite_ref_no_artifact_path_is_gate_fail(self, mock_sub, mock_config, tmp_path):
        iface_artifact = tmp_path / "iface.pyi"
        iface_artifact.write_text("def foo(x: int) -> str: ...\n")
        iface_wi = _create_interface_spec(mock_sub, str(iface_artifact))

        ts_wi = _create_test_suite(mock_sub, iface_wi, artifact_path="")

        artifact = tmp_path / "impl.py"
        artifact.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "implementation",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(ts_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, custom = _gate_state(mock_sub, wi.work_item_id)
        assert state == "new"
        diagnostics = custom.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "missing_artifact"

    def test_test_suite_ref_artifact_not_on_disk_is_gate_fail(
        self, mock_sub, mock_config, tmp_path
    ):
        iface_artifact = tmp_path / "iface.pyi"
        iface_artifact.write_text("def foo(x: int) -> str: ...\n")
        iface_wi = _create_interface_spec(mock_sub, str(iface_artifact))

        ts_wi = _create_test_suite(mock_sub, iface_wi, "/nonexistent/test.py")

        artifact = tmp_path / "impl.py"
        artifact.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "implementation",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(ts_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, custom = _gate_state(mock_sub, wi.work_item_id)
        assert state == "new"
        diagnostics = custom.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "missing_artifact"

    def test_valid_refs_proceeds_to_gate_evaluation(self, mock_sub, mock_config, tmp_path):
        iface_artifact = tmp_path / "iface.pyi"
        iface_artifact.write_text('"""Satisfies AC-01."""\ndef foo(x: int) -> str: ...\n')
        iface_wi = _create_interface_spec(mock_sub, str(iface_artifact))

        ts_artifact = tmp_path / "test_foo.py"
        ts_artifact.write_text("def test_foo(): pass\n")
        ts_wi = _create_test_suite(mock_sub, iface_wi, str(ts_artifact))

        artifact = tmp_path / "impl.py"
        artifact.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        wi, fresh, claim = _make_and_submit(
            mock_sub,
            "implementation",
            {
                "spec_section": "S1",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(ts_wi.work_item_id),
            },
            artifact_path=artifact,
        )
        runtime = PipelineRuntime(sub=mock_sub, config=mock_config)
        process_gate_item(runtime, fresh, "test-gate", claim)

        state, _ = _gate_state(mock_sub, wi.work_item_id)
        assert state in ("locked", "new")
