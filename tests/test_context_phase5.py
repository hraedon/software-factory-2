from __future__ import annotations

import json
from pathlib import Path

from factory.context import (
    _gather_other_locked_artifacts,
    _infer_module_name_from_artifact_path,
    derive_integrator_context,
    derive_outcome_verifier_context,
)


class TestDeriveIntegratorContext:
    def test_includes_focal_artifact_from_review_chain(self, mock_substrate, tmp_path):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")
        )

        iface_pyi = tmp_path / "iface.pyi"
        iface_pyi.write_text("def compute(x: int) -> str: ...\n")
        ts_pyi = tmp_path / "test_compute.py"
        ts_pyi.write_text("def test_compute(): assert True\n")
        impl_py = tmp_path / "impl.py"
        impl_py.write_text("def compute(x: int) -> str:\n    return str(x)\n")

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "artifact_path": str(iface_pyi),
            },
        )
        ts, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "artifact_path": str(ts_pyi),
            },
        )
        impl, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="coder",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
                "artifact_path": str(impl_py),
            },
        )
        review, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="review",
            actor_id="reviewer",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
                "implementation_ref": str(impl.work_item_id),
            },
        )
        jury, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="jury",
            actor_id="judge",
            custom_fields={
                "review_ref": str(review.work_item_id),
            },
        )
        integration, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="integrator",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "integration_ref": str(jury.work_item_id),
            },
        )

        ctx = derive_integrator_context(mock_substrate, str(integration.work_item_id))
        assert ctx.role == "integrator"
        assert "focal_implementation" in ctx.extra_artifacts
        assert "focal_interface" in ctx.extra_artifacts
        assert "focal_test_suite" in ctx.extra_artifacts
        assert ctx.extra_artifacts["focal_implementation"] == impl_py.read_text()

    def test_missing_refs_produces_empty_extras(self, mock_substrate):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")
        )
        integration, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="integrator",
            custom_fields={
                "spec_section": "Section B",
                "ac_ids": ["AC-02"],
            },
        )
        ctx = derive_integrator_context(mock_substrate, str(integration.work_item_id))
        assert ctx.role == "integrator"
        assert "focal_implementation" not in ctx.extra_artifacts


class TestDeriveOutcomeVerifierContext:
    def test_includes_assembled_modules(self, mock_substrate, tmp_path):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")
        )

        integration_json = tmp_path / "integration.json"
        integration_json.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "module_a.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
                        "module_b.py": (
                            "import module_a\n\n"
                            "def compute(x: int) -> int:\n"
                            "    return module_a.add(x, x)\n"
                        ),
                    },
                    "entry_point": "module_b.compute",
                    "integration_tests": "def test_cross_module(): pass\n",
                }
            )
        )

        integration, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={
                "spec_section": "Section C",
                "ac_ids": ["AC-03"],
                "artifact_path": str(integration_json),
            },
        )
        outcome, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verify",
            custom_fields={
                "spec_section": "Section C",
                "ac_ids": ["AC-03"],
                "integration_ref": str(integration.work_item_id),
            },
        )

        ctx = derive_outcome_verifier_context(mock_substrate, str(outcome.work_item_id))
        assert ctx.role == "outcome_verifier"
        assert "assembled_module_module_a.py" in ctx.extra_artifacts
        assert "assembled_module_module_b.py" in ctx.extra_artifacts
        assert "integration_tests" in ctx.extra_artifacts

    def test_missing_integration_ref_produces_empty_extras(self, mock_substrate, tmp_path):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")
        )
        # Create dummy integration so the integration_ref is valid and
        # outcome_verification custom_fields do not complain.
        integration, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={
                "spec_section": "Section D",
                "ac_ids": ["AC-04"],
            },
        )
        outcome, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verify",
            custom_fields={
                "spec_section": "Section D",
                "ac_ids": ["AC-04"],
                "integration_ref": str(integration.work_item_id),
            },
        )
        ctx = derive_outcome_verifier_context(mock_substrate, str(outcome.work_item_id))
        assert ctx.role == "outcome_verifier"
        assert not ctx.extra_artifacts


class TestGatherOtherLockedArtifacts:
    def _create_and_lock_impl(self, mock_substrate, tmp_path, mod_name, actor_id_suffix):
        iface_pyi = tmp_path / f"{mod_name}_iface.pyi"
        iface_pyi.write_text(f"def {mod_name}() -> None: ...\n")
        impl_py = tmp_path / f"{mod_name}.py"
        impl_py.write_text(f"def {mod_name}(): pass\n")

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id=f"arch-{actor_id_suffix}",
            custom_fields={
                "spec_section": f"Section {mod_name}",
                "ac_ids": [f"AC-{actor_id_suffix}"],
                "module_name": mod_name,
                "artifact_path": str(iface_pyi),
            },
        )
        mock_substrate.transition(
            work_item_id=iface.work_item_id,
            transition_name="claim",
            actor_id="worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            work_item_id=iface.work_item_id,
            transition_name="submit",
            actor_id="worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            work_item_id=iface.work_item_id,
            transition_name="gate_pass",
            actor_id="gate",
            actor_metadata={"role": "mechanical_gate"},
        )

        ts_py = tmp_path / f"test_{mod_name}.py"
        ts_py.write_text(f"def test_{mod_name}(): pass\n")
        ts, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id=f"tester-{actor_id_suffix}",
            custom_fields={
                "spec_section": f"Section {mod_name}",
                "ac_ids": [f"AC-{actor_id_suffix}"],
                "interface_ref": str(iface.work_item_id),
                "artifact_path": str(ts_py),
            },
        )
        mock_substrate.transition(
            work_item_id=ts.work_item_id,
            transition_name="claim",
            actor_id="worker",
            actor_metadata={"role": "test_author"},
        )
        mock_substrate.transition(
            work_item_id=ts.work_item_id,
            transition_name="submit",
            actor_id="worker",
            actor_metadata={"role": "test_author"},
        )
        mock_substrate.transition(
            work_item_id=ts.work_item_id,
            transition_name="gate_pass",
            actor_id="gate",
            actor_metadata={"role": "mechanical_gate"},
        )

        impl, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id=f"coder-{actor_id_suffix}",
            custom_fields={
                "spec_section": f"Section {mod_name}",
                "ac_ids": [f"AC-{actor_id_suffix}"],
                "module_name": mod_name,
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
                "artifact_path": str(impl_py),
            },
        )
        mock_substrate.transition(
            work_item_id=impl.work_item_id,
            transition_name="claim",
            actor_id="worker",
            actor_metadata={"role": "implementer"},
        )
        mock_substrate.transition(
            work_item_id=impl.work_item_id,
            transition_name="submit",
            actor_id="worker",
            actor_metadata={"role": "implementer"},
        )
        mock_substrate.transition(
            work_item_id=impl.work_item_id,
            transition_name="gate_pass",
            actor_id="gate",
            actor_metadata={"role": "mechanical_gate"},
        )
        return impl, impl_py

    def test_finds_other_locked_implementations(self, mock_substrate, tmp_path):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")
        )
        _impl, impl_py = self._create_and_lock_impl(mock_substrate, tmp_path, "other_module", "10")

        impls, _ifaces = _gather_other_locked_artifacts(mock_substrate, exclude_impl_id=None)
        assert "other_module" in impls
        assert impls["other_module"] == impl_py.read_text()

    def test_excludes_focal_implementation(self, mock_substrate, tmp_path):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")
        )
        impl, _ = self._create_and_lock_impl(mock_substrate, tmp_path, "focal", "20")

        impls, _ifaces = _gather_other_locked_artifacts(
            mock_substrate, exclude_impl_id=str(impl.work_item_id)
        )
        assert "focal" not in impls


class TestInferModuleNameFromArtifactPath:
    def test_extracts_stem(self):
        assert (
            _infer_module_name_from_artifact_path("/tmp/wi_abc/ad/attempt-0001/my_module.py")
            == "my_module"
        )

    def test_extracts_from_wi_prefix(self):
        assert (
            _infer_module_name_from_artifact_path(
                "/tmp/wi_certificate_model/ad/attempt-0001/artifact.py"
            )
            == "certificate_model"
        )

    def test_empty_for_none(self):
        assert _infer_module_name_from_artifact_path(None) == ""
