from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

import structlog
import yaml

from factory.config import GateTimeouts
from factory.constants import GATE_NAME_CONFORMANCE, DiagnosticKind
from factory.gate._base import GateResult, _guard_artifact_size
from factory.sandbox import gate_subprocess_env
from factory.subprocess import run as run_subprocess

_log = structlog.get_logger()


def _extract_acs_from_spec(spec_text: str) -> list[dict]:
    """Extract acceptance criteria from a spec.yaml file.

    Returns a list of dicts with keys: id, fr, scenario, input, expected.
    Each AC is parsed from the structured YAML format.
    """
    try:
        spec = yaml.safe_load(spec_text)
    except Exception as exc:
        _log.warning("conformance_spec_parse_failed", error=str(exc))
        return []

    acs = spec.get("acceptance_criteria", [])
    if not acs:
        return []

    result = []
    for ac in acs:
        if not isinstance(ac, dict):
            continue
        ac_id = ac.get("id", "")
        frs = ac.get("functional_requirements", [])
        # Real spec.yaml uses "condition"; fixture/test data uses "scenario"
        scenario = ac.get("condition", "") or ac.get("scenario", "")
        result.append(
            {
                "id": ac_id,
                "fr": frs[0] if frs else "",
                "scenario": scenario,
            }
        )
    return result


def _derive_acceptance_tests(
    acs: list[dict],
    assembled_files: list[str],
    requirements_text: str = "",
) -> str:
    """Deterministically derive acceptance tests from AC scenarios.

    This is the AC -> acceptance-suite translation from RFC-038.
    Each AC scenario is translated into a concrete pytest test that exercises
    the assembled artifact via httpx ASGITransport (no running server needed).

    The tests MUST fail against unimplemented stubs (dep-v1-364 invariant):
    - If no FastAPI app exists, test_client fixture fails immediately
    - If endpoints don't exist, HTTP calls return wrong status
    - If behavior is wrong, assertions fail
    """
    has_fastapi = any(
        "fastapi" in requirements_text.lower() or "fastapi" in f.lower() for f in assembled_files
    )

    lines = [
        '"""Acceptance tests derived from spec ACs (RFC-038 conformance gate).',
        "",
        "These tests are generated deterministically from the spec's acceptance_criteria.",
        "They MUST fail against unimplemented stubs (dep-v1-364 invariant).",
        '"""',
        "",
        "import pytest",
        "",
    ]

    if has_fastapi:
        lines.extend(
            [
                "from httpx import ASGITransport, AsyncClient",
                "",
                "",
                "@pytest.fixture",
                "def app():",
                '    """Import the FastAPI app from the assembled artifact."""',
                "    from app import app  # noqa: F811",
                "    return app",
                "",
                "",
                "@pytest.fixture",
                "async def client(app):",
                '    """Create an async test client using ASGITransport."""',
                "    transport = ASGITransport(app=app)",
                "    async with AsyncClient(transport=transport, base_url='http://test') as c:",
                "        yield c",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "@pytest.fixture",
                "def app():",
                '    """No FastAPI detected in artifact — fixture fails immediately."""',
                "    pytest.fail('No FastAPI app found in assembled artifact')",
                "",
            ]
        )

    # Generate a test for each AC
    test_names = []
    for ac in acs:
        ac_id = ac["id"]
        scenario = ac["scenario"]
        test_name = f"test_{ac_id.lower().replace('-', '_')}"
        test_names.append(test_name)

        # Parse the scenario to extract HTTP method, path, body, and expected response
        test_body = _translate_scenario(ac_id, scenario, has_fastapi)
        lines.append("")
        lines.extend(test_body)

    return "\n".join(lines)


def _translate_scenario(ac_id: str, scenario: str, has_fastapi: bool) -> list[str]:
    """Translate a single AC scenario into pytest test code.

    The scenario format from socratic-specification is:
    "Given <precondition>, when <action>, then <expected>"
    or: "POST /path {body} -> HTTP status {response}"

    This is the deterministic translation (not LLM-authored).
    """
    test_name = f"test_{ac_id.lower().replace('-', '_')}"

    if not has_fastapi:
        return [
            "@pytest.mark.anyio",
            f"async def {test_name}():",
            f'    """{ac_id}: {scenario[:80]}"""',
            "    pytest.fail('No FastAPI app — cannot test HTTP behavior')",
        ]

    # Parse common patterns from the url-shortener AC scenarios
    # Pattern: "Given <precondition>, when/POST/GET <method> <path> <body>, then <expected>"
    lines = [
        "@pytest.mark.anyio",
        f"async def {test_name}(client):",
        f'    """{ac_id}: {scenario[:100]}"""',
    ]

    # Extract HTTP method and path from scenario
    method, path, body, expected_status, expected_body = _parse_scenario(scenario)

    if method == "POST" and body:
        lines.append(f"    payload = {body}")
        lines.append(f"    resp = await client.post('{path}', json=payload)")
    elif method == "GET":
        lines.append(f"    resp = await client.get('{path}')")
    else:
        lines.append(f"    # Scenario: {scenario[:80]}")
        lines.append(f"    pytest.fail('Scenario not yet translatable: {scenario[:60]}')")
        return lines

    # Assert status code
    if expected_status:
        lines.append(f"    assert resp.status_code == {expected_status}, (")
        lines.append("        f'Expected {expected_status}, got '")
        lines.append("        f'{{resp.status_code}}: {{resp.text[:200]}}'")
        lines.append("    )")

    # Assert response body properties
    if expected_body:
        for key, value in expected_body.items():
            if key == "error_code":
                lines.append("    data = resp.json()")
                lines.append(f"    assert data['error']['code'] == '{value}'")
            elif key == "has_slug":
                lines.append("    data = resp.json()")
                lines.append("    assert 'slug' in data")
                lines.append("    assert len(data['slug']) == 6")
            elif key == "array_length_lte":
                lines.append("    data = resp.json()")
                lines.append(f"    assert len(data) <= {value}")
            elif key == "total_hits":
                lines.append("    data = resp.json()")
                lines.append(f"    assert data['total_hits'] == {value}")

    return lines


def _parse_scenario(
    scenario: str,
) -> tuple[str, str, dict | None, int | None, dict | None]:
    """Parse an AC scenario into HTTP method, path, body, expected status, expected body.

    Returns (method, path, body, expected_status, expected_body).
    """
    method = ""
    path = ""
    body = None
    expected_status = None
    expected_body: dict | None = None

    # Extract method and path: POST /links, GET /abc123, POST to /links, etc.
    m = re.search(
        r"\b(POST|GET|PUT|DELETE|PATCH)\s+(?:to\s+)?"
        r"(/[\w?=&/]*(?=[\s,{(]|$))",
        scenario,
        re.IGNORECASE,
    )
    if m:
        method = m.group(1).upper()
        path = m.group(2)

    # Extract request body: {"url":"..."} or {"url": 123}
    m = re.search(r'\{[^}]*"url"[^}]*\}', scenario)
    if m:
        try:
            body = json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Extract expected status: HTTP 201, HTTP 422, HTTP 307, HTTP 404
    m = re.search(r"HTTP\s+(\d{3})", scenario)
    if m:
        expected_status = int(m.group(1))

    # Extract expected response properties
    expected_body = {}

    # Error code: error code 'invalid_url', error code 'not_found'
    m = re.search(r"error code ['\"]?(\w+)['\"]?", scenario)
    if m:
        expected_body["error_code"] = m.group(1)

    # Slug: "slug":"<6-char>"
    if '"slug"' in scenario or "slug" in scenario.lower():
        if "6-char" in scenario or "six" in scenario.lower():
            expected_body["has_slug"] = True

    # Array length: "returns 20", "at most 5 links"
    m = re.search(r"returns\s+(\d+)\s", scenario)
    if m and method == "GET" and "/links" in path:
        expected_body["array_length_lte"] = int(m.group(1))

    m = re.search(r"at most\s+(\d+)", scenario)
    if m:
        expected_body["array_length_lte"] = int(m.group(1))

    # Total hits: total_hits=5, total_hits incremented
    m = re.search(r"total_hits[=:]\s*(\d+)", scenario)
    if m:
        expected_body["total_hits"] = int(m.group(1))

    return method, path, body, expected_status, (expected_body or None)


def evaluate_conformance(
    artifact_path: Path,
    spec_text: str,
    requirements_text: str = "",
    python_executable: str | None = None,
    gate_timeouts: GateTimeouts | None = None,
) -> GateResult:
    """RFC-038 conformance gate: execute assembled artifact against AC-derived tests.

    # tier: enforce
    # precondition: assembled artifact may contain stub code that passes
    #   mechanical gates but does not implement the spec's HTTP/DB contract
    # audit trigger: re-evaluate when AC translation becomes unreliable or
    #   when the gate no longer catches stub implementations

    This gate replaces LLM-opinion-based outcome_e2e with execution-based
    conformance verification. The acceptance tests are derived deterministically
    from the spec's AC scenarios (not authored by the worker model family).

    The tests MUST fail against unimplemented stubs (dep-v1-364 invariant).
    """
    t = gate_timeouts or GateTimeouts()
    exe = python_executable or sys.executable

    size_guard = _guard_artifact_size(artifact_path)
    if size_guard is not None:
        return size_guard

    # Parse the integration artifact
    try:
        text = artifact_path.read_text()
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_CONFORMANCE,
            diagnostics=[f"Conformance artifact is not valid JSON: {exc}"],
            diagnostic_kind=DiagnosticKind.CONFORMANCE,
        )
    except Exception as exc:
        _log.debug("conformance_artifact_read_failed", exc_info=True, error=str(exc))
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_CONFORMANCE,
            diagnostics=[f"Failed to read conformance artifact: {exc}"],
            diagnostic_kind=DiagnosticKind.CONFORMANCE,
        )

    assembled_tree = data.get("assembled_tree")
    if not isinstance(assembled_tree, dict) or not assembled_tree:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_CONFORMANCE,
            diagnostics=["Conformance artifact missing 'assembled_tree' field or empty"],
            diagnostic_kind=DiagnosticKind.CONFORMANCE,
        )

    # Extract ACs from spec
    acs = _extract_acs_from_spec(spec_text)
    if not acs:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_CONFORMANCE,
            diagnostics=["No acceptance criteria found in spec"],
            diagnostic_kind=DiagnosticKind.CONFORMANCE,
        )

    # Derive acceptance tests deterministically from ACs
    acceptance_tests = _derive_acceptance_tests(
        acs,
        list(assembled_tree.keys()),
        requirements_text,
    )

    # Check the dep-v1-364 invariant: tests must fail against unimplemented stubs
    # If the artifact has no FastAPI app, the test_client fixture fails immediately

    with tempfile.TemporaryDirectory(prefix="sf2_conformance_") as tmpdir:
        tmp_path = Path(tmpdir).resolve()

        # Write assembled tree files
        for filename, source in assembled_tree.items():
            if not isinstance(filename, str):
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_CONFORMANCE,
                    diagnostics=[f"assembled_tree key {filename!r} is not a string"],
                    diagnostic_kind=DiagnosticKind.CONFORMANCE,
                )
            if Path(filename).is_absolute() or ".." in Path(filename).parts:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_CONFORMANCE,
                    diagnostics=[f"assembled_tree key {filename!r} has unsafe path"],
                    diagnostic_kind=DiagnosticKind.CONFORMANCE,
                )
            dest = tmp_path / filename
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(str(source))

        # Write acceptance tests
        test_file = tmp_path / "test_conformance.py"
        test_file.write_text(acceptance_tests)

        # Write pytest config
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\nasyncio_mode = 'auto'\n"
        )

        # Install requirements if provided
        if requirements_text:
            req_path = tmp_path / "requirements.txt"
            req_path.write_text(requirements_text)
            install_result = run_subprocess(
                cmd=[exe, "-m", "pip", "install", "-q", "-r", str(req_path)],
                cwd=tmp_path,
                env=gate_subprocess_env(),
                timeout_s=60,
            )
            if install_result.returncode != 0:
                _log.warning(
                    "conformance_pip_install_failed",
                    stderr=install_result.stderr[:500],
                )

        # Run acceptance tests
        pytest_result = run_subprocess(
            cmd=[
                exe,
                "-m",
                "pytest",
                str(test_file),
                "-x",
                "--tb=short",
                "-q",
                f"--rootdir={tmp_path}",
                "-p",
                "no:cacheprovider",
            ],
            cwd=tmp_path,
            env=gate_subprocess_env(PYTHONPATH=str(tmp_path)),
            timeout_s=t.pytest_timeout,
        )

        if pytest_result.timed_out:
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_CONFORMANCE,
                diagnostics=[
                    f"Conformance tests timed out after {t.pytest_timeout}s",
                    "timed_out: True",
                ],
                diagnostic_kind=DiagnosticKind.CONFORMANCE,
            )

        if pytest_result.returncode != 0:
            lines = pytest_result.stdout.strip().splitlines()
            err_lines = pytest_result.stderr.strip().splitlines()
            diagnostics = (lines + err_lines)[:15] or ["Conformance tests failed"]
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_CONFORMANCE,
                diagnostics=diagnostics,
                diagnostic_kind=DiagnosticKind.CONFORMANCE,
            )

    return GateResult(
        passed=True,
        gate_name=GATE_NAME_CONFORMANCE,
        diagnostics=[],
    )
