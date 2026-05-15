from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from factory.pipeline_docs import (
    extract_role_summaries,
    format_full_doc,
    format_pipeline_doc,
    generate_from_workflow,
    generate_full_doc,
    generate_router_table,
)


@pytest.fixture
def workflow_yaml(tmp_path) -> Path:
    data = {
        "version": 5,
        "states": ["new", "in_progress", "gating", "locked", "cannot_proceed"],
        "roles": ["interface_architect", "implementer", "mechanical_gate"],
        "work_item_types": [
            {
                "name": "interface_spec",
                "custom_fields": [
                    {"name": "spec_section"},
                    {"name": "ac_ids"},
                    {"name": "artifact_path"},
                ],
            },
            {
                "name": "implementation",
                "custom_fields": [
                    {"name": "artifact_path"},
                    {"name": "implementation_ref"},
                ],
            },
        ],
        "link_types": ["derived_from", "implements", "tested_by"],
        "transitions": [
            {"from": "new", "to": "in_progress", "role": "any"},
            {"from": "in_progress", "to": "gating", "role": "any"},
        ],
    }
    p = tmp_path / "phase5.yaml"
    with open(p, "w") as f:
        yaml.dump(data, f)
    return p


@pytest.fixture
def prompts_dir(tmp_path) -> Path:
    d = tmp_path / "prompts"
    d.mkdir()
    (d / "interface_architect.md").write_text(
        "# Role: interface_architect\n\n"
        "Produce .pyi stubs from specifications.\n\n"
        "## What you produce\n\nA .pyi file."
    )
    (d / "implementer.md").write_text(
        "# Role: implementer\n\n"
        "Fill in implementation from .pyi contracts.\n\n"
        "## What you produce\n\nA .py file."
    )
    return d


class TestGenerateFromWorkflow:
    def test_parses_version(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert doc.workflow_version == 5

    def test_parses_states(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert "new" in doc.states
        assert "locked" in doc.states

    def test_parses_work_item_types(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert "interface_spec" in doc.work_item_types
        assert "implementation" in doc.work_item_types

    def test_parses_custom_fields(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert "spec_section" in doc.custom_fields.get("interface_spec", [])
        assert "artifact_path" in doc.custom_fields.get("interface_spec", [])

    def test_parses_roles(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert "implementer" in doc.roles

    def test_parses_link_types(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert "derived_from" in doc.link_types

    def test_parses_transitions(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        assert len(doc.stage_handoffs) == 2


class TestGenerateRouterTable:
    def test_all_diagnostic_kinds_represented(self):
        routes, escalatable = generate_router_table()
        assert len(routes) > 10
        assert "impl_mypy" in escalatable
        assert "syntax" not in escalatable


class TestExtractRoleSummaries:
    def test_extracts_from_prompts(self, prompts_dir):
        summaries = extract_role_summaries(prompts_dir)
        assert "interface_architect" in summaries
        assert ".pyi" in summaries["interface_architect"]

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        summaries = extract_role_summaries(d)
        assert summaries == {}


class TestFormatPipelineDoc:
    def test_format_states(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        text = format_pipeline_doc(doc)
        assert "## States" in text
        assert "`new`" in text

    def test_format_work_item_types(self, workflow_yaml):
        doc = generate_from_workflow(workflow_yaml)
        text = format_pipeline_doc(doc)
        assert "## Work Item Types" in text
        assert "`interface_spec`" in text


class TestFormatFullDoc:
    def test_includes_router_table(self, workflow_yaml, prompts_dir):
        doc = generate_from_workflow(workflow_yaml)
        routes, escalatable = generate_router_table()
        summaries = extract_role_summaries(prompts_dir)
        text = format_full_doc(doc, routes, escalatable, summaries)
        assert "## Failure Routing Table" in text
        assert "## Role Summaries" in text
        assert "interface_architect" in text


class TestGenerateFullDoc:
    def test_generates_from_latest_phase(self):
        text = generate_full_doc()
        assert "# Pipeline Documentation" in text
        assert "interface_spec" in text
