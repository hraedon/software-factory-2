from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from factory.context import (
    PromptContext,
    _serialize_bundle,
    derive_context,
    render_prompt,
)
from factory.failure_summary import FailureEntry


class TestSerializeBundle:
    def test_deterministic_same_inputs(self):
        bundle1 = _serialize_bundle(
            spec_section="spec content",
            ac_ids=["AC-01", "AC-02"],
            glossary={"term": "definition"},
            failures=[],
            prompt_template="template",
        )
        bundle2 = _serialize_bundle(
            spec_section="spec content",
            ac_ids=["AC-01", "AC-02"],
            glossary={"term": "definition"},
            failures=[],
            prompt_template="template",
        )
        assert bundle1 == bundle2

    def test_different_content_different_hash(self):
        bundle1 = _serialize_bundle(
            spec_section="content A",
            ac_ids=["AC-01"],
            glossary={},
            failures=[],
            prompt_template="template",
        )
        bundle2 = _serialize_bundle(
            spec_section="content B",
            ac_ids=["AC-01"],
            glossary={},
            failures=[],
            prompt_template="template",
        )
        assert bundle1 != bundle2

    def test_ac_ids_sorted(self):
        bundle1 = _serialize_bundle(
            spec_section="s",
            ac_ids=["AC-02", "AC-01"],
            glossary={},
            failures=[],
            prompt_template="t",
        )
        bundle2 = _serialize_bundle(
            spec_section="s",
            ac_ids=["AC-01", "AC-02"],
            glossary={},
            failures=[],
            prompt_template="t",
        )
        assert bundle1 == bundle2

    def test_glossary_sorted(self):
        bundle1 = _serialize_bundle(
            spec_section="s",
            ac_ids=["AC-01"],
            glossary={"z": "z", "a": "a"},
            failures=[],
            prompt_template="t",
        )
        bundle2 = _serialize_bundle(
            spec_section="s",
            ac_ids=["AC-01"],
            glossary={"a": "a", "z": "z"},
            failures=[],
            prompt_template="t",
        )
        assert bundle1 == bundle2

    def test_failures_included(self):
        failures = [
            FailureEntry(
                attempt_number=1,
                role="gate",
                channel="code",
                gate_name="syntax",
                diagnostic="bad",
            )
        ]
        bundle = _serialize_bundle(
            spec_section="s",
            ac_ids=[],
            glossary={},
            failures=failures,
            prompt_template="t",
        )
        parsed = json.loads(bundle)
        assert len(parsed["prior_failures"]) == 1
        assert parsed["prior_failures"][0]["gate_name"] == "syntax"


class TestPromptContext:
    def test_frozen(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="content",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc123",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
        )
        with pytest.raises(AttributeError):
            ctx.role = "test_author"


class TestDeriveContextSpecContent:
    def test_work_item_spec_section_takes_priority(self, mock_regista):
        from factory.context import derive_context

        wi, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Work item fixture content",
                "ac_ids": ["AC-01"],
            },
        )
        ctx = derive_context(
            mock_regista,
            wi.work_item_id,
            "interface_architect",
            spec_content="Factory level spec",
        )
        assert ctx.spec_section == "Work item fixture content"

    def test_factory_spec_as_fallback_when_empty(self, mock_regista):
        from factory.context import derive_context

        wi, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "",
                "ac_ids": ["AC-02"],
            },
        )
        ctx = derive_context(
            mock_regista,
            wi.work_item_id,
            "interface_architect",
            spec_content="Factory level spec as fallback",
        )
        assert ctx.spec_section == "Factory level spec as fallback"

    def test_empty_spec_section_no_factory_spec(self, mock_regista):
        from factory.context import derive_context

        wi, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "",
                "ac_ids": ["AC-03"],
            },
        )
        ctx = derive_context(
            mock_regista,
            wi.work_item_id,
            "interface_architect",
            spec_content=None,
        )
        assert ctx.spec_section == ""

    def test_work_item_content_preserved_with_factory_spec_also_set(self, mock_regista):
        from factory.context import derive_context

        wi, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "The real spec section from the work item",
                "ac_ids": ["AC-04"],
            },
        )
        ctx = derive_context(
            mock_regista,
            wi.work_item_id,
            "interface_architect",
            spec_content="This should NOT appear in the context",
        )
        assert ctx.spec_section == "The real spec section from the work item"

    def test_context_hash_changes_with_different_spec_sources(self, mock_regista):
        from factory.context import derive_context

        wi_1, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Content A",
                "ac_ids": ["AC-05"],
            },
        )
        wi_2, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Content B",
                "ac_ids": ["AC-05"],
            },
        )
        ctx_1 = derive_context(mock_regista, wi_1.work_item_id, "interface_architect")
        ctx_2 = derive_context(mock_regista, wi_2.work_item_id, "interface_architect")
        assert ctx_1.context_hash != ctx_2.context_hash


class TestRenderPrompt:
    def test_render_prompt_with_empty_fields(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="",
            ac_ids=[],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert "work_item_id: wi-1" in rendered
        assert "## spec_section" in rendered
        assert "## glossary" not in rendered
        assert "## prior_failures" not in rendered
        assert "## extra_artifacts" not in rendered

    def test_render_prompt_with_glossary(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={"term": "definition"},
            prior_failures=[],
            prompt_template="template",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert "## glossary" in rendered
        assert "**term**: definition" in rendered

    def test_render_prompt_with_failures(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[
                FailureEntry(
                    attempt_number=1,
                    role="gate",
                    channel="code",
                    gate_name="syntax",
                    diagnostic="bad syntax",
                )
            ],
            prompt_template="template",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert "## prior_failures" in rendered
        assert "syntax — bad syntax" in rendered

    def test_render_prompt_with_extra_artifacts(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="template",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={"locked_interface": "def foo(): ..."},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert "## locked_interface" in rendered
        assert "def foo(): ..." in rendered

    def test_render_prompt_includes_prompt_template(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="System prompt goes here.",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        lines = rendered.splitlines()
        assert lines[0] == "System prompt goes here."

    def test_render_prompt_preserves_spec_section_order(self):
        spec = "This is the spec section content.\nLine two."
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section=spec,
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert spec in rendered

    def test_review_feedback_rendered_once(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={"review_feedback": "AC-01: missing edge case"},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        count = rendered.count("## review_feedback")
        assert count == 1, f"review_feedback section rendered {count} times, expected 1"

    def test_review_feedback_contains_guidance(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={"review_feedback": "AC-01: missing edge case"},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert "block-severity" in rendered

    def test_extra_artifact_value_fence_prevents_heading_injection(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={"locked_interface": "## injected_section\nmalicious content"},
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        in_fence = False
        headings = []
        for line in rendered.splitlines():
            if line.strip() == "```":
                in_fence = not in_fence
            elif not in_fence and line.startswith("## "):
                headings.append(line)
        assert "## injected_section" not in headings, (
            f"Injected heading found outside code fences. Headings: {headings}"
        )

    def test_all_extra_artifacts_fenced(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={
                "alpha": "value_a",
                "beta": "value_b",
            },
            stub_only_deps=[],
        )
        rendered = render_prompt(ctx)
        assert "```\nvalue_a\n```" in rendered
        assert "```\nvalue_b\n```" in rendered


class TestDeriveContextMissingWorkItem:
    def test_missing_work_item_raises(self, mock_regista):
        with pytest.raises(ValueError, match=r"Work item .* not found"):
            derive_context(mock_regista, str(uuid.uuid4()), "interface_architect")


class TestMissingPromptTemplate:
    def test_missing_prompt_file_raises(self, mock_regista):
        wi, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Section X",
                "ac_ids": ["AC-01"],
            },
        )
        with pytest.raises(FileNotFoundError, match="nonexistent_role"):
            derive_context(mock_regista, wi.work_item_id, "nonexistent_role")


class TestDeriveTestAuthorContext:
    def test_includes_locked_interface(self, mock_regista, tmp_path):
        from factory.context import derive_test_author_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        iface_pyi = tmp_path / "iface.pyi"
        iface_pyi.write_text("def compute(x: int) -> str: ...\n")

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "artifact_path": str(iface_pyi),
                "artifact_hash": "sha256:abc",
            },
        )

        ts, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
            },
        )

        ctx = derive_test_author_context(mock_regista, ts.work_item_id)
        assert ctx.extra_artifacts.get("locked_interface") == "def compute(x: int) -> str: ...\n"
        assert ctx.role == "test_author"

    def test_missing_interface_ref_handled_gracefully(self, mock_regista):
        from factory.context import derive_test_author_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
            },
        )

        ts, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section A",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
            },
        )

        ctx = derive_test_author_context(mock_regista, ts.work_item_id)
        assert ctx.extra_artifacts.get("locked_interface", "") == ""


class TestDeriveImplementerContext:
    def test_includes_locked_interface_and_test_suite(self, mock_regista, tmp_path):
        from factory.context import derive_implementer_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        iface_pyi = tmp_path / "iface2.pyi"
        iface_pyi.write_text("def compute(x: int) -> str: ...\n")
        ts_file = tmp_path / "test_compute.py"
        ts_file.write_text("def test_compute(): assert True\n")

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section B",
                "ac_ids": ["AC-01"],
                "artifact_path": str(iface_pyi),
            },
        )
        ts, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section B",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "artifact_path": str(ts_file),
            },
        )

        impl, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="impl",
            custom_fields={
                "spec_section": "Section B",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
            },
        )

        ctx = derive_implementer_context(mock_regista, impl.work_item_id)
        assert ctx.extra_artifacts.get("locked_interface") == "def compute(x: int) -> str: ...\n"
        assert ctx.extra_artifacts.get("test_suite") == "def test_compute(): assert True\n"
        assert ctx.role == "implementer"

    def test_missing_refs_handled_gracefully(self, mock_regista):
        from factory.context import derive_implementer_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section C",
                "ac_ids": ["AC-01"],
            },
        )
        suite, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section C",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
            },
        )

        impl, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="impl",
            custom_fields={
                "spec_section": "Section C",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(suite.work_item_id),
            },
        )

        ctx = derive_implementer_context(mock_regista, impl.work_item_id)
        assert ctx.extra_artifacts == {}

    def test_dependency_contents_injected_into_implementer(self, mock_regista, tmp_path):
        from factory.context import derive_implementer_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        dep_pyi = tmp_path / "certificate_model.pyi"
        dep_pyi.write_text("class Certificate:\n    subject: str\n    issuer: str\n")

        iface_pyi = tmp_path / "iface.pyi"
        iface_pyi.write_text(
            "from certificate_model import Certificate\ndef scan(host: str) -> Certificate: ...\n"
        )
        ts_file = tmp_path / "test_scan.py"
        ts_file.write_text("def test_scan(): assert True\n")

        dep, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "# Interface Specification: Certificate Model\n\nAC-01: Subject DN",
                "ac_ids": ["AC-01"],
                "artifact_path": str(dep_pyi),
            },
        )

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section D",
                "ac_ids": ["AC-01"],
                "artifact_path": str(iface_pyi),
            },
        )

        ts, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section D",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "artifact_path": str(ts_file),
            },
        )

        impl, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="impl",
            custom_fields={
                "spec_section": "Section D",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
                "dependency_refs": [str(dep.work_item_id)],
            },
        )

        ctx = derive_implementer_context(mock_regista, impl.work_item_id)
        assert "locked_dependency_certificate_model" in ctx.extra_artifacts
        assert "Certificate" in ctx.extra_artifacts["locked_dependency_certificate_model"]

    def test_dependency_contents_injected_into_test_author(self, mock_regista, tmp_path):
        from factory.context import derive_test_author_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        dep_pyi = tmp_path / "certificate_model.pyi"
        dep_pyi.write_text("class Certificate:\n    subject: str\n    issuer: str\n")

        iface_pyi = tmp_path / "iface.pyi"
        iface_pyi.write_text(
            "from certificate_model import Certificate\ndef scan(host: str) -> Certificate: ...\n"
        )

        dep, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "# Interface Specification: Certificate Model\n\nAC-01: Subject DN",
                "ac_ids": ["AC-01"],
                "artifact_path": str(dep_pyi),
            },
        )

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section E",
                "ac_ids": ["AC-01"],
                "artifact_path": str(iface_pyi),
            },
        )

        ts, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section E",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "dependency_refs": [str(dep.work_item_id)],
            },
        )

        ctx = derive_test_author_context(mock_regista, ts.work_item_id)
        assert "locked_dependency_certificate_model" in ctx.extra_artifacts
        assert "Certificate" in ctx.extra_artifacts["locked_dependency_certificate_model"]

    def test_no_dependency_refs_produces_no_locked_dependencies(self, mock_regista, tmp_path):
        from factory.context import derive_implementer_context

        mock_regista.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )

        iface_pyi = tmp_path / "iface_no_dep.pyi"
        iface_pyi.write_text("def compute(x: int) -> str: ...\n")
        ts_file = tmp_path / "test_compute.py"
        ts_file.write_text("def test_compute(): assert True\n")

        iface, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={
                "spec_section": "Section F",
                "ac_ids": ["AC-01"],
                "artifact_path": str(iface_pyi),
            },
        )
        ts, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="tester",
            custom_fields={
                "spec_section": "Section F",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "artifact_path": str(ts_file),
            },
        )

        impl, _ = mock_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="impl",
            custom_fields={
                "spec_section": "Section F",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
            },
        )

        ctx = derive_implementer_context(mock_regista, impl.work_item_id)
        dep_keys = [k for k in ctx.extra_artifacts if k.startswith("locked_dependency_")]
        assert dep_keys == []
