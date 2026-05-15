from __future__ import annotations

import json
from pathlib import Path

from factory.context import (
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
