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
