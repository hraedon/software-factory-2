from __future__ import annotations

from factory.telemetry import (
    GateAttempt,
    compute_pass_rates,
    format_pass_rate_table,
)


def test_mean_duration_computed() -> None:
    attempts = [
        GateAttempt(
            work_item_id="wi-1",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=10.0,
        ),
        GateAttempt(
            work_item_id="wi-2",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=20.0,
        ),
    ]
    rows = compute_pass_rates(attempts)
    assert len(rows) == 1
    assert rows[0].mean_duration_seconds == 15.0
    assert rows[0].median_duration_seconds == 15.0


def test_median_duration_with_even_count() -> None:
    attempts = [
        GateAttempt(
            work_item_id="wi-1",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=10.0,
        ),
        GateAttempt(
            work_item_id="wi-2",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=20.0,
        ),
        GateAttempt(
            work_item_id="wi-3",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=30.0,
        ),
        GateAttempt(
            work_item_id="wi-4",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=40.0,
        ),
    ]
    rows = compute_pass_rates(attempts)
    assert rows[0].median_duration_seconds == 25.0


def test_missing_duration_graceful() -> None:
    attempts = [
        GateAttempt(
            work_item_id="wi-1",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=None,
        ),
    ]
    rows = compute_pass_rates(attempts)
    assert rows[0].mean_duration_seconds is None
    assert rows[0].median_duration_seconds is None
    table = format_pass_rate_table(rows)
    assert "\u2014" in table


def test_duration_shown_in_table() -> None:
    attempts = [
        GateAttempt(
            work_item_id="wi-1",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=True,
            duration_seconds=12.5,
        ),
    ]
    rows = compute_pass_rates(attempts)
    table = format_pass_rate_table(rows)
    assert "12.5s" in table
    assert "MeanDur" in table
