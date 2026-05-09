from __future__ import annotations

from factory.telemetry import (
    GateAttempt,
    compute_pass_rates,
    format_pass_rate_table,
)


def test_same_hash_no_confounding_warning() -> None:
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
            prompt_template_hash="abc12345",
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
            prompt_template_hash="abc12345",
        ),
    ]
    rows = compute_pass_rates(attempts)
    table = format_pass_rate_table(rows)
    assert "WARNING" not in table
    assert "abc12345" in table


def test_different_hash_emits_confounding_warning() -> None:
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
            prompt_template_hash="abc12345",
        ),
        GateAttempt(
            work_item_id="wi-2",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=False,
            prompt_template_hash="def67890",
        ),
    ]
    rows = compute_pass_rates(attempts)
    table = format_pass_rate_table(rows)
    assert "WARNING" in table
    assert "results confounded" in table


def test_none_hash_handled_gracefully() -> None:
    attempts = [
        GateAttempt(
            work_item_id="wi-1",
            work_item_type="interface_spec",
            role="interface_architect",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="interface_spec",
            passed=True,
            prompt_template_hash=None,
        ),
    ]
    rows = compute_pass_rates(attempts)
    table = format_pass_rate_table(rows)
    assert "\u2014" in table  # dash for missing hash
    assert "WARNING" not in table


def test_compute_groups_by_hash() -> None:
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
            prompt_template_hash="hash-a",
        ),
        GateAttempt(
            work_item_id="wi-2",
            work_item_type="implementation",
            role="implementer",
            channel="claude-code",
            family="anthropic",
            attempt_n=1,
            gate_name="implementation_pytest",
            passed=False,
            prompt_template_hash="hash-b",
        ),
    ]
    rows = compute_pass_rates(attempts)
    assert len(rows) == 2
    hashes = {r.prompt_template_hash for r in rows}
    assert hashes == {"hash-a", "hash-b"}
