from __future__ import annotations

from pathlib import Path

import pytest

from factory.behavioral_gate import evaluate_behavioral


@pytest.mark.skip(reason="behavioral gate not yet implemented; this test is the spec for Phase 5")
def test_behavioral_gate_playwright_against_broken_fastapi() -> None:
    """When the behavioral gate exists, this test should pass.

    It asserts that a deliberately broken FastAPI fixture (returns 500 on /)
    fails a minimal Playwright scenario.  The skip is the accountability —
    removing the skip requires the gate to be real.
    """
    pytest.importorskip("playwright")

    fixture = Path(__file__).parent / "fixtures" / "broken_fastapi" / "app.py"
    scenarios = [
        {
            "name": "root_returns_200",
            "url": "http://127.0.0.1:8000/",
            "expected_status": 200,
        }
    ]

    # Start the broken app in a subprocess
    import subprocess
    import time

    proc = subprocess.Popen(
        [
            "python",
            "-m",
            "uvicorn",
            "tests.fixtures.broken_fastapi.app:app",
            "--port",
            "8999",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(1)
    try:
        result = evaluate_behavioral(fixture, scenarios=scenarios)
        # The app is deliberately broken (500 on /), so the gate should fail
        assert not result.passed
    finally:
        proc.terminate()
        proc.wait()


def test_behavioral_stub_skips_when_no_scenarios() -> None:
    result = evaluate_behavioral(Path("/dev/null"), scenarios=[])
    assert result.passed is True
    assert result.skipped is True


def test_behavioral_stub_raises_when_scenarios_present() -> None:
    with pytest.raises(NotImplementedError, match="behavioral gate scheduled for Phase 5"):
        evaluate_behavioral(Path("/dev/null"), scenarios=[{"name": "x"}])
