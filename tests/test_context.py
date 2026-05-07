from __future__ import annotations

import json

import pytest

from factory.context import PromptContext, _serialize_bundle
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
        )
        with pytest.raises(AttributeError):
            ctx.role = "test_author"


class TestDeriveContextSpecContent:
    def test_work_item_spec_section_takes_priority(self, mock_substrate):
        from factory.context import derive_context

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Work item fixture content",
                "ac_ids": ["AC-01"],
            },
        )
        ctx = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content="Factory level spec",
        )
        assert ctx.spec_section == "Work item fixture content"

    def test_factory_spec_as_fallback_when_empty(self, mock_substrate):
        from factory.context import derive_context

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "",
                "ac_ids": ["AC-02"],
            },
        )
        ctx = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content="Factory level spec as fallback",
        )
        assert ctx.spec_section == "Factory level spec as fallback"

    def test_empty_spec_section_no_factory_spec(self, mock_substrate):
        from factory.context import derive_context

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "",
                "ac_ids": ["AC-03"],
            },
        )
        ctx = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content=None,
        )
        assert ctx.spec_section == ""

    def test_work_item_content_preserved_with_factory_spec_also_set(self, mock_substrate):
        from factory.context import derive_context

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "The real spec section from the work item",
                "ac_ids": ["AC-04"],
            },
        )
        ctx = derive_context(
            mock_substrate,
            wi.work_item_id,
            "interface_architect",
            spec_content="This should NOT appear in the context",
        )
        assert ctx.spec_section == "The real spec section from the work item"

    def test_context_hash_changes_with_different_spec_sources(self, mock_substrate):
        from factory.context import derive_context

        wi_1, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Content A",
                "ac_ids": ["AC-05"],
            },
        )
        wi_2, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Content B",
                "ac_ids": ["AC-05"],
            },
        )
        ctx_1 = derive_context(mock_substrate, wi_1.work_item_id, "interface_architect")
        ctx_2 = derive_context(mock_substrate, wi_2.work_item_id, "interface_architect")
        assert ctx_1.context_hash != ctx_2.context_hash
