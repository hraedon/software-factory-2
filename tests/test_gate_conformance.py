from __future__ import annotations

import json
from pathlib import Path

import yaml

from factory.constants import GATE_NAME_CONFORMANCE, DiagnosticKind
from factory.gate._base import GateResult
from factory.gate.conformance import (
    _derive_acceptance_tests,
    _extract_acs_from_spec,
    _parse_scenario,
    _translate_scenario,
    evaluate_conformance,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_spec_yaml(acs: list[dict]) -> str:
    """Build a minimal spec.yaml with the given ACs."""
    spec = {
        "acceptance_criteria": acs,
        "decided_constraints": {
            "http_framework": "FastAPI",
            "database": "SQLite",
        },
    }
    return yaml.dump(spec)


def _make_integration_artifact(
    assembled_tree: dict[str, str],
    entry_point: str = "",
    integration_tests: str = "",
) -> str:
    """Build a minimal integration artifact JSON."""
    data = {
        "assembled_tree": assembled_tree,
        "entry_point": entry_point,
        "integration_tests": integration_tests,
    }
    return json.dumps(data)


def _write_artifact(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "artifact.json"
    p.write_text(content)
    return p


# URL-shortener AC fixtures
URL_SHORTENER_ACS = [
    {
        "id": "AC-01",
        "functional_requirements": ["FR-01"],
        "scenario": (
            'Given a POST to /links with {"url":"https://example.com"}, '
            "the response is HTTP 201 with a JSON body containing a 6-character slug"
        ),
    },
    {
        "id": "AC-02",
        "functional_requirements": ["FR-01"],
        "scenario": (
            'Given a POST to /links with {"url":"not-a-url"}, '
            "the response is HTTP 422 with error code 'invalid_url'"
        ),
    },
    {
        "id": "AC-03",
        "functional_requirements": ["FR-02"],
        "scenario": (
            "Given a GET to /abc123 (which maps to https://example.com), "
            "the response is HTTP 307 with Location header https://example.com"
        ),
    },
    {
        "id": "AC-04",
        "functional_requirements": ["FR-02"],
        "scenario": (
            "Given a GET to /nonexistent, the response is HTTP 404 with error code 'not_found'"
        ),
    },
    {
        "id": "AC-06",
        "functional_requirements": ["FR-04"],
        "scenario": (
            "Given 25 links in the database, GET /links returns 20 links "
            "(default limit). GET /links?offset=20 returns the remaining 5"
        ),
    },
    {
        "id": "AC-07",
        "functional_requirements": ["FR-05"],
        "scenario": (
            'Given a POST to /links with {"url": 123}, '
            "the response is HTTP 422 with error code 'invalid_url'"
        ),
    },
]

URL_SHORTENER_REQUIREMENTS = (
    "fastapi>=0.110.0\nuvicorn>=0.27.0\npydantic>=2.0.0\nhttpx>=0.27.0\npytest>=8.0.0\n"
)


# ---------------------------------------------------------------------------
# Test _extract_acs_from_spec
# ---------------------------------------------------------------------------


class TestExtractAcsFromSpec:
    def test_extracts_acs_from_yaml(self):
        spec_text = _make_spec_yaml(URL_SHORTENER_ACS)
        acs = _extract_acs_from_spec(spec_text)
        assert len(acs) == 6
        assert acs[0]["id"] == "AC-01"
        assert acs[0]["fr"] == "FR-01"

    def test_empty_spec(self):
        acs = _extract_acs_from_spec("acceptance_criteria: []")
        assert acs == []

    def test_no_ac_section(self):
        acs = _extract_acs_from_spec("name: test\nversion: 1")
        assert acs == []

    def test_invalid_yaml(self):
        acs = _extract_acs_from_spec("{{invalid yaml}}")
        assert acs == []

    def test_preserves_scenario(self):
        spec_text = _make_spec_yaml(URL_SHORTENER_ACS)
        acs = _extract_acs_from_spec(spec_text)
        assert "POST" in acs[0]["scenario"]
        assert "HTTP 201" in acs[0]["scenario"]


# ---------------------------------------------------------------------------
# Test _parse_scenario
# ---------------------------------------------------------------------------


class TestParseScenario:
    def test_post_with_body_and_status(self):
        scenario = (
            'Given a POST to /links with {"url":"https://example.com"}, the response is HTTP 201'
        )
        method, path, body, status, _expected = _parse_scenario(scenario)
        assert method == "POST"
        assert path == "/links"
        assert body == {"url": "https://example.com"}
        assert status == 201

    def test_get_with_path(self):
        scenario = "Given a GET to /abc123, the response is HTTP 307"
        method, path, body, status, _expected = _parse_scenario(scenario)
        assert method == "GET"
        assert path == "/abc123"
        assert body is None
        assert status == 307

    def test_error_code_extraction(self):
        scenario = (
            'Given a POST to /links with {"url":"not-a-url"}, '
            "the response is HTTP 422 with error code 'invalid_url'"
        )
        _method, _path, _body, status, expected = _parse_scenario(scenario)
        assert status == 422
        assert expected is not None
        assert expected["error_code"] == "invalid_url"

    def test_array_length_extraction(self):
        scenario = "Given 25 links in the database, GET /links returns 20 links"
        method, path, _body, _status, expected = _parse_scenario(scenario)
        assert method == "GET"
        assert path == "/links"
        assert expected is not None
        assert expected["array_length_lte"] == 20

    def test_at_most_extraction(self):
        scenario = "GET /links?limit=5 returns at most 5 links"
        _method, _path, _body, _status, expected = _parse_scenario(scenario)
        assert expected is not None
        assert expected["array_length_lte"] == 5

    def test_total_hits_extraction(self):
        scenario = "GET /links/abc123/stats with 5 hits, total_hits=5"
        _method, _path, _body, _status, expected = _parse_scenario(scenario)
        assert expected is not None
        assert expected["total_hits"] == 5

    def test_slug_extraction(self):
        scenario = 'POST /links {"url":"https://example.com"} -> HTTP 201 with "slug":"<6-char>"'
        _method, _path, _body, _status, expected = _parse_scenario(scenario)
        assert expected is not None
        assert expected["has_slug"] is True

    def test_no_method(self):
        scenario = "Something happens"
        method, path, _body, _status, _expected = _parse_scenario(scenario)
        assert method == ""
        assert path == ""

    def test_post_with_integer_body(self):
        scenario = 'Given a POST to /links with {"url": 123}, the response is HTTP 422'
        method, _path, body, status, _expected = _parse_scenario(scenario)
        assert method == "POST"
        assert body == {"url": 123}
        assert status == 422


# ---------------------------------------------------------------------------
# Test _translate_scenario
# ---------------------------------------------------------------------------


class TestTranslateScenario:
    def test_post_scenario_generates_test(self):
        lines = _translate_scenario(
            "AC-01",
            (
                'Given a POST to /links with {"url":"https://example.com"}, '
                "the response is HTTP 201 with a 6-character slug"
            ),
            has_fastapi=True,
        )
        code = "\n".join(lines)
        assert "async def test_ac_01" in code
        assert "client.post" in code
        assert "201" in code

    def test_get_scenario_generates_test(self):
        lines = _translate_scenario(
            "AC-03",
            (
                "Given a GET to /abc123 "
                "(which maps to https://example.com), "
                "the response is HTTP 307"
            ),
            has_fastapi=True,
        )
        code = "\n".join(lines)
        assert "async def test_ac_03" in code
        assert "client.get" in code
        assert "307" in code

    def test_no_fastapi_fails_immediately(self):
        lines = _translate_scenario(
            "AC-01",
            ('Given a POST to /links with {"url":"https://example.com"}, the response is HTTP 201'),
            has_fastapi=False,
        )
        code = "\n".join(lines)
        assert "pytest.fail" in code
        assert "No FastAPI app" in code


# ---------------------------------------------------------------------------
# Test _derive_acceptance_tests
# ---------------------------------------------------------------------------


class TestDeriveAcceptanceTests:
    def test_generates_test_file_with_fastapi(self):
        code = _derive_acceptance_tests(
            URL_SHORTENER_ACS,
            ["__init__.py", "app.py", "routes.py"],
            URL_SHORTENER_REQUIREMENTS,
        )
        assert "import pytest" in code
        assert "from httpx import ASGITransport, AsyncClient" in code
        assert "async def test_ac_01" in code
        assert "async def test_ac_02" in code
        assert "async def test_ac_03" in code
        assert "async def test_ac_06" in code
        assert "async def test_ac_07" in code

    def test_generates_test_file_without_fastapi(self):
        code = _derive_acceptance_tests(
            URL_SHORTENER_ACS,
            ["__init__.py", "link_creator.py", "link_resolver.py"],
            "",
        )
        assert "pytest.fail" in code
        assert "No FastAPI app" in code

    def test_empty_acs(self):
        code = _derive_acceptance_tests([], ["app.py"], URL_SHORTENER_REQUIREMENTS)
        assert "import pytest" in code
        # No test functions generated
        assert "async def test_" not in code

    def test_includes_pytest_mark(self):
        code = _derive_acceptance_tests(
            URL_SHORTENER_ACS,
            ["app.py"],
            URL_SHORTENER_REQUIREMENTS,
        )
        assert "@pytest.mark.anyio" in code


# ---------------------------------------------------------------------------
# Test evaluate_conformance (integration-level)
# ---------------------------------------------------------------------------


class TestEvaluateConformance:
    def test_no_fastapi_app_fails(self, tmp_path):
        """The dep-v1-364 invariant: tests MUST fail against stubs with no HTTP layer."""
        spec_text = _make_spec_yaml(URL_SHORTENER_ACS)
        artifact_content = _make_integration_artifact(
            assembled_tree={
                "__init__.py": "",
                "link_creator.py": "def create_link(url): return {'slug': 'abc123'}",
                "link_resolver.py": "def resolve_link(slug): return None",
            },
            entry_point="link_creator.create_link",
        )
        artifact_path = _write_artifact(tmp_path, artifact_content)

        result = evaluate_conformance(
            artifact_path,
            spec_text=spec_text,
            python_executable="python3",
        )
        assert not result.passed
        assert result.gate_name == GATE_NAME_CONFORMANCE
        assert result.diagnostic_kind == DiagnosticKind.CONFORMANCE

    def test_invalid_json_artifact(self, tmp_path):
        artifact_path = tmp_path / "bad.json"
        artifact_path.write_text("not json")

        result = evaluate_conformance(
            artifact_path,
            spec_text=_make_spec_yaml(URL_SHORTENER_ACS),
        )
        assert not result.passed
        assert "not valid JSON" in result.diagnostics[0]

    def test_empty_assembled_tree(self, tmp_path):
        artifact_path = _write_artifact(
            tmp_path,
            json.dumps({"assembled_tree": {}, "entry_point": ""}),
        )
        result = evaluate_conformance(
            artifact_path,
            spec_text=_make_spec_yaml(URL_SHORTENER_ACS),
        )
        assert not result.passed
        assert "missing 'assembled_tree'" in result.diagnostics[0]

    def test_no_acs_in_spec(self, tmp_path):
        artifact_path = _write_artifact(
            tmp_path,
            _make_integration_artifact({"app.py": "x = 1"}),
        )
        result = evaluate_conformance(
            artifact_path,
            spec_text="name: test\n",
        )
        assert not result.passed
        assert "No acceptance criteria" in result.diagnostics[0]

    def test_missing_artifact_file(self, tmp_path):
        result = evaluate_conformance(
            tmp_path / "nonexistent.json",
            spec_text=_make_spec_yaml(URL_SHORTENER_ACS),
        )
        assert not result.passed

    def test_unsafe_path_in_tree(self, tmp_path):
        artifact_path = _write_artifact(
            tmp_path,
            _make_integration_artifact({"../escape.py": "x = 1"}),
        )
        result = evaluate_conformance(
            artifact_path,
            spec_text=_make_spec_yaml(URL_SHORTENER_ACS),
        )
        assert not result.passed
        assert "unsafe path" in result.diagnostics[0].lower()


# ---------------------------------------------------------------------------
# Test router integration
# ---------------------------------------------------------------------------


class TestConformanceRouting:
    def test_conformance_in_kind_dispatch(self):
        from factory.constants import DiagnosticKind
        from factory.router import KIND_DISPATCH

        assert DiagnosticKind.CONFORMANCE in KIND_DISPATCH
        route = KIND_DISPATCH[DiagnosticKind.CONFORMANCE]
        assert route.target_state == "new"

    def test_conformance_in_escalatable_kinds(self):
        from factory.constants import DiagnosticKind
        from factory.router import ESCALATABLE_KINDS

        assert DiagnosticKind.CONFORMANCE in ESCALATABLE_KINDS

    def test_conformance_gate_result_routes_correctly(self):
        from factory.constants import STATE_GATING, TRANSITION_GATE_FAIL
        from factory.router import route

        gr = GateResult(
            passed=False,
            gate_name=GATE_NAME_CONFORMANCE,
            diagnostics=["test failed"],
            diagnostic_kind=DiagnosticKind.CONFORMANCE,
        )
        routing = route(
            STATE_GATING,
            TRANSITION_GATE_FAIL,
            gr,
            attempt_number=1,
            attempt_threshold=3,
        )
        assert routing.target_state == "new"

    def test_conformance_escalates_at_threshold(self):
        from factory.constants import STATE_GATING, TRANSITION_GATE_FAIL
        from factory.router import route

        gr = GateResult(
            passed=False,
            gate_name=GATE_NAME_CONFORMANCE,
            diagnostics=["test failed"],
            diagnostic_kind=DiagnosticKind.CONFORMANCE,
        )
        routing = route(
            STATE_GATING,
            TRANSITION_GATE_FAIL,
            gr,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert routing.target_state == "cannot_proceed"
