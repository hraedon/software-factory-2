from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.decomposer_model import (
    DecomposeError,
    _extract_decomposition_json,
    _validate_decomposition,
    decompose_from_model,
)


class FakeChannel:
    def __init__(self, responses: list[str] | None = None, fail: bool = False):
        self._responses = list(responses) if responses else []
        self._index = 0
        self._fail = fail
        self.name = "test"
        self.family = "test-family"

    def invoke(self, role, prompt, outputs_dir, timeout, **kwargs):
        if self._fail:
            from factory.channel import InvocationResult

            return InvocationResult(
                success=False,
                error_message="test failure",
                exit_code=1,
            )
        resp = self._responses[self._index] if self._index < len(self._responses) else "{}"
        self._index += 1
        # Write response into outputs_dir so _invoke_decomposer_channel can read it back
        out = Path(outputs_dir) / "artifact.json"
        out.write_text(resp)
        from factory.channel import InvocationResult

        return InvocationResult(success=True)


class TestExtractDecompositionJson:
    def test_fenced_json(self):
        raw = '\n```json\n{"modules": []}\n```\n'
        assert _extract_decomposition_json(raw) == {"modules": []}

    def test_plain_json(self):
        raw = '{"modules": []}'
        assert _extract_decomposition_json(raw) == {"modules": []}

    def test_prefixed_text_before_json(self):
        raw = 'Some preamble\n```json\n{"a": 1}\n```\nMore text'
        assert _extract_decomposition_json(raw) == {"a": 1}

    def test_invalid_json_raises(self):
        with pytest.raises(DecomposeError):
            _extract_decomposition_json("not json at all")

    def test_empty_raises(self):
        with pytest.raises(DecomposeError):
            _extract_decomposition_json("")


class TestValidateDecomposition:
    def test_not_dict(self):
        results = _validate_decomposition([])
        assert any(not r.passed for r in results)
        assert results[0].diagnostic_kind == "schema"

    def test_empty_modules(self):
        results = _validate_decomposition({"modules": []})
        assert any(not r.passed for r in results)

    def test_missing_fields(self):
        results = _validate_decomposition({"modules": [{"module_name": "a"}]})
        assert any(not r.passed for r in results)
        assert any("missing fields" in r.diagnostic for r in results)

    def test_duplicate_module_name(self):
        data = {
            "modules": [
                _valid_module("m1", "FR-01"),
                _valid_module("m1", "FR-02"),
            ]
        }
        results = _validate_decomposition(data)
        assert any("Duplicate module_name" in r.diagnostic for r in results)

    def test_bad_dependency(self):
        data = {
            "modules": [
                _valid_module("m1", "FR-01", dependency_fr_ids=["FR-99"]),
            ]
        }
        results = _validate_decomposition(data)
        assert any("unknown fr_ids" in r.diagnostic for r in results)

    def test_cyclic_dependency(self):
        data = {
            "modules": [
                _valid_module("m1", "FR-01", dependency_fr_ids=["FR-02"]),
                _valid_module("m2", "FR-02", dependency_fr_ids=["FR-01"]),
            ]
        }
        results = _validate_decomposition(data)
        assert any("Cyclic" in r.diagnostic for r in results)

    def test_module_too_large(self):
        data = {
            "modules": [
                _valid_module("m1", "FR-01", ac_ids=[f"AC-{i:02d}" for i in range(14)]),
            ]
        }
        results = _validate_decomposition(data)
        assert any("max 12" in r.diagnostic for r in results)

    def test_module_small_is_warning(self):
        data = {"modules": [_valid_module("m1", "FR-01", ac_ids=["AC-01"])]}
        results = _validate_decomposition(data)
        # Should still pass overall
        assert any(r.passed and "module_small" in r.diagnostic_kind for r in results)

    def test_fr_shaped_name_fails(self):
        data = {"modules": [_valid_module("fr01", "FR-01")]}
        results = _validate_decomposition(data)
        assert any(
            r.gate_name == "semantic_naming" and "FR-shaped" in r.diagnostic for r in results
        )

    def test_fr_shaped_name_case_insensitive(self):
        data = {"modules": [_valid_module("FR01", "FR-01")]}
        results = _validate_decomposition(data)
        assert any(
            r.gate_name == "semantic_naming" and "FR-shaped" in r.diagnostic for r in results
        )

    def test_generic_suffix_fails(self):
        data = {"modules": [_valid_module("data_handler", "FR-01")]}
        results = _validate_decomposition(data)
        assert any(
            r.gate_name == "semantic_naming" and "generic suffix" in r.diagnostic for r in results
        )

    def test_valid_semantic_name_passes(self):
        data = {
            "modules": [
                _valid_module("rule_loader", "FR-01"),
                _valid_module("redaction_engine", "FR-02"),
            ]
        }
        results = _validate_decomposition(data)
        assert not any(r.gate_name == "semantic_naming" and not r.passed for r in results)

    def test_phase_a_does_not_reject_fr_names(self):
        data = {"modules": [_valid_module("fr01", "FR-01")]}
        results = _validate_decomposition(data, phase_b=False)
        assert not any(r.gate_name == "semantic_naming" for r in results)

    def test_too_long_name_fails(self):
        data = {"modules": [_valid_module("a" * 41, "FR-01")]}
        results = _validate_decomposition(data)
        assert any(
            r.gate_name == "semantic_naming" and "<=40 chars" in r.diagnostic for r in results
        )

    def test_non_snake_case_name_fails(self):
        data = {"modules": [_valid_module("RuleLoader", "FR-01")]}
        results = _validate_decomposition(data)
        assert any(
            r.gate_name == "semantic_naming" and "snake_case" in r.diagnostic for r in results
        )


class TestDecomposeFromModel:
    def test_success(self, tmp_path: Path):
        data = {
            "modules": [
                _valid_module("m1", "FR-01"),
                _valid_module("m2", "FR-02", dependency_fr_ids=["FR-01"]),
            ],
            "rationale": "Test rationale",
        }
        channel = FakeChannel([json.dumps(data)])
        result = decompose_from_model(
            channel,
            _fake_config(),
            tmp_path / "spec.md",
            None,
            tmp_path,
            max_retries=0,
        )
        assert len(result.modules) == 2
        assert result.modules[1].dependency_fr_ids == ["FR-01"]

    def test_retry_on_bad_output(self, tmp_path: Path):
        bad = {"modules": [{"module_name": "x"}]}
        good = {
            "modules": [_valid_module("m1", "FR-01")],
        }
        channel = FakeChannel([json.dumps(bad), json.dumps(good)])
        result = decompose_from_model(
            channel,
            _fake_config(),
            tmp_path / "spec.md",
            None,
            tmp_path,
            max_retries=1,
        )
        assert len(result.modules) == 1


class TestRenderYamlForPrompt:
    def test_loads_spec_yaml(self, tmp_path: Path):
        from factory.decomposer_model import _render_yaml_for_prompt

        spec_yaml = tmp_path / "spec.yaml"
        spec_yaml.write_text(
            "meta:\n  name: test\nfunctional_requirements:\n  - id: FR-01\n    text: do thing\n"
        )
        data = _render_yaml_for_prompt(spec_yaml)
        assert data["meta"]["name"] == "test"
        assert data["functional_requirements"][0]["id"] == "FR-01"


class TestBuildStructuredPrompt:
    def test_includes_spec_yaml_section(self):
        from factory.decomposer_model import _build_structured_prompt

        prompt = _build_structured_prompt(
            spec_data={"meta": {"name": "test"}, "functional_requirements": []},
            spec_md_text=None,
        )
        assert "## spec_yaml" in prompt
        assert "```yaml" in prompt
        assert "meta:" in prompt

        assert "## spec_text" not in prompt

    def test_includes_spec_text_section(self):
        from factory.decomposer_model import _build_structured_prompt

        prompt = _build_structured_prompt(
            spec_data=None,
            spec_md_text="# Hello\n\nWorld\n",
        )
        assert "## spec_text" in prompt
        assert "```" in prompt
        assert "Hello" in prompt

        assert "## spec_yaml" not in prompt

    def test_includes_prior_failures(self):
        from factory.decomposer_model import (
            DecompositionGateResult,
            _build_structured_prompt,
        )

        failures = [
            DecompositionGateResult(
                passed=False,
                gate_name="semantic_naming",
                diagnostic_kind="fr_shaped_name",
                diagnostic="Module name 'fr01' is FR-shaped",
            )
        ]
        prompt = _build_structured_prompt(
            spec_data={"meta": {"name": "test"}},
            spec_md_text=None,
            prior_failures=failures,
        )
        assert "## prior_failures" in prompt
        assert "semantic_naming" in prompt
        assert "FR-shaped" in prompt

    def test_empty_when_no_spec(self):
        from factory.decomposer_model import _build_structured_prompt

        prompt = _build_structured_prompt(spec_data=None, spec_md_text=None)
        # Should still have template + separators; no spec or text sections
        assert "## spec_yaml" not in prompt
        assert "## spec_text" not in prompt


class TestDecomposeFromModelRetriesWithFeedback:
    def test_prior_failures_passed_to_next_attempt(self, tmp_path: Path):
        """Second attempt should receive prompt including prior failures."""
        bad = {
            "modules": [
                {
                    "module_name": "fr01",
                    "fr_id": "FR-01",
                    "fr_text": "",
                    "ac_ids": [],
                    "dependency_fr_ids": [],
                }
            ]
        }
        good = {
            "modules": [
                {
                    "module_name": "rule_loader",
                    "fr_id": "FR-01",
                    "fr_text": "Load rules",
                    "ac_ids": ["AC-01"],
                    "dependency_fr_ids": [],
                }
            ]
        }
        channel = FakeChannel([json.dumps(bad), json.dumps(good)])
        result = decompose_from_model(
            channel,
            _fake_config(),
            tmp_path / "spec.yaml",
            None,
            tmp_path,
            max_retries=1,
        )
        assert result.modules[0].module_name == "rule_loader"
        # The channel was invoked twice
        assert channel._index == 2


class TestDecomposeFromModelSnapshotLogRedactCLI:
    def _make_snapshot_dir(self, tmp_path: Path) -> Path:
        snap = tmp_path / "snapshots"
        snap.mkdir()
        return snap

    def test_semantic_decomposition_log_redact_cli(self, tmp_path: Path):
        """Snapshot: Phase B produces semantic names for log-redact-cli spec."""
        data = {
            "modules": [
                {
                    "module_name": "rule_loader",
                    "fr_id": "FR-01",
                    "fr_text": "Load and validate redaction rules from YAML",
                    "ac_ids": ["AC-LOG-01", "AC-LOG-02"],
                    "dependency_fr_ids": [],
                },
                {
                    "module_name": "log_reader",
                    "fr_id": "FR-02",
                    "fr_text": "Read and parse JSONL log lines",
                    "ac_ids": ["AC-LOG-03"],
                    "dependency_fr_ids": [],
                },
                {
                    "module_name": "redaction_engine",
                    "fr_id": "FR-03",
                    "fr_text": "Apply redaction rules to parsed log lines",
                    "ac_ids": ["AC-LOG-04", "AC-LOG-05", "AC-LOG-06"],
                    "dependency_fr_ids": ["FR-01", "FR-02"],
                },
                {
                    "module_name": "output_emitter",
                    "fr_id": "FR-04",
                    "fr_text": "Emit redacted JSONL output",
                    "ac_ids": ["AC-LOG-07"],
                    "dependency_fr_ids": ["FR-03"],
                },
                {
                    "module_name": "audit_writer",
                    "fr_id": "FR-05",
                    "fr_text": "Emit audit trail of redactions",
                    "ac_ids": ["AC-LOG-08", "AC-LOG-09"],
                    "dependency_fr_ids": ["FR-03"],
                },
            ],
            "rationale": "Semantic decomposition grouping FRs by capability.",
        }
        channel = FakeChannel([json.dumps(data)])
        result = decompose_from_model(
            channel,
            _fake_config(),
            tmp_path / "spec.yaml",
            None,
            tmp_path,
            max_retries=0,
        )
        assert len(result.modules) == 5
        names = [m.module_name for m in result.modules]
        assert names == [
            "rule_loader",
            "log_reader",
            "redaction_engine",
            "output_emitter",
            "audit_writer",
        ]
        deps = {m.fr_id: m.dependency_fr_ids for m in result.modules}
        assert deps["FR-03"] == ["FR-01", "FR-02"]
        assert deps["FR-04"] == ["FR-03"]
        assert deps["FR-05"] == ["FR-03"]


class TestDecomposeFromModelSnapshotDepGraphViewer:
    def test_semantic_decomposition_dep_graph_viewer(self, tmp_path: Path):
        """Snapshot: Phase B produces semantic names for dep-graph-viewer spec."""
        data = {
            "modules": [
                {
                    "module_name": "event_reader",
                    "fr_id": "FR-01",
                    "fr_text": "Read substrate event log from PostgreSQL",
                    "ac_ids": ["AC-DGV-01", "AC-DGV-02"],
                    "dependency_fr_ids": [],
                },
                {
                    "module_name": "graph_builder",
                    "fr_id": "FR-02",
                    "fr_text": "Build graph of work items and typed links",
                    "ac_ids": ["AC-DGV-03", "AC-DGV-04"],
                    "dependency_fr_ids": [],
                },
                {
                    "module_name": "graph_filter",
                    "fr_id": "FR-03",
                    "fr_text": "Filter nodes by type and edges by link type",
                    "ac_ids": ["AC-DGV-05", "AC-DGV-06"],
                    "dependency_fr_ids": ["FR-02"],
                },
                {
                    "module_name": "dot_emitter",
                    "fr_id": "FR-04",
                    "fr_text": "Emit valid DOT syntax",
                    "ac_ids": ["AC-DGV-07", "AC-DGV-08", "AC-DGV-09"],
                    "dependency_fr_ids": ["FR-03"],
                },
            ],
            "rationale": "Semantic decomposition: reader, builder, filter, emitter stages.",
        }
        channel = FakeChannel([json.dumps(data)])
        result = decompose_from_model(
            channel,
            _fake_config(),
            tmp_path / "spec.yaml",
            None,
            tmp_path,
            max_retries=0,
        )
        assert len(result.modules) == 4
        names = [m.module_name for m in result.modules]
        assert names == ["event_reader", "graph_builder", "graph_filter", "dot_emitter"]
        deps = {m.fr_id: m.dependency_fr_ids for m in result.modules}
        assert deps["FR-03"] == ["FR-02"]
        assert deps["FR-04"] == ["FR-03"]


class TestDecomposeFromModelSnapshotCertWatch:
    def test_semantic_decomposition_cert_watch(self, tmp_path: Path):
        """Snapshot: Phase B produces semantic names for cert-watch spec."""
        data = {
            "modules": [
                {
                    "module_name": "certificate_model",
                    "fr_id": "FR-01",
                    "fr_text": "Model and parse X.509 certificates",
                    "ac_ids": ["AC-01", "AC-02", "AC-03", "AC-04", "AC-05"],
                    "dependency_fr_ids": [],
                },
                {
                    "module_name": "cert_chain_library",
                    "fr_id": "FR-02",
                    "fr_text": "Validate certificate chains",
                    "ac_ids": ["AC-06", "AC-07"],
                    "dependency_fr_ids": ["FR-01"],
                },
                {
                    "module_name": "tls_scanner",
                    "fr_id": "FR-03",
                    "fr_text": "Scan TLS endpoints and retrieve certificates",
                    "ac_ids": ["AC-08", "AC-09", "AC-10"],
                    "dependency_fr_ids": ["FR-01", "FR-02"],
                },
                {
                    "module_name": "file_uploader",
                    "fr_id": "FR-04",
                    "fr_text": "Upload and parse certificate files",
                    "ac_ids": ["AC-11", "AC-12"],
                    "dependency_fr_ids": ["FR-01"],
                },
                {
                    "module_name": "alert_notifier",
                    "fr_id": "FR-05",
                    "fr_text": "Send expiry alerts via configured channels",
                    "ac_ids": ["AC-13", "AC-14"],
                    "dependency_fr_ids": ["FR-01"],
                },
                {
                    "module_name": "scan_scheduler",
                    "fr_id": "FR-06",
                    "fr_text": "Schedule periodic TLS scans",
                    "ac_ids": ["AC-15", "AC-16"],
                    "dependency_fr_ids": ["FR-03", "FR-05"],
                },
            ],
            "rationale": "Semantic decomposition mapping FRs to domain concepts.",
        }
        channel = FakeChannel([json.dumps(data)])
        result = decompose_from_model(
            channel,
            _fake_config(),
            tmp_path / "spec.yaml",
            None,
            tmp_path,
            max_retries=0,
        )
        assert len(result.modules) == 6
        names = [m.module_name for m in result.modules]
        assert "fr01" not in names
        assert "certificate_model" in names
        assert "tls_scanner" in names
        assert "scan_scheduler" in names


# Helpers


def _valid_module(
    name: str,
    fr_id: str,
    dependency_fr_ids: list[str] | None = None,
    ac_ids: list[str] | None = None,
) -> dict:
    return {
        "module_name": name,
        "fr_id": fr_id,
        "fr_text": f"Implement {fr_id}",
        "ac_ids": ac_ids if ac_ids is not None else ["AC-01", "AC-02"],
        "dependency_fr_ids": dependency_fr_ids if dependency_fr_ids is not None else [],
    }


def _fake_config():
    from factory.config import FactoryConfig

    return FactoryConfig(
        dsn="postgresql://localhost/test",
        project_name="test",
        hmac_key_path=Path("/dev/null"),
        workspace_root=Path("/tmp"),
    )
