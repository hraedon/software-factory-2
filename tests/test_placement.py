"""Tests for :mod:`factory.placement`.

No model invocation — pure data-driven placement proposer logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from factory.config import FactoryConfig, RoleConfig
from factory.placement import (
    PlacementDiff,
    PlacementPolicy,
    _rate_for_role_channel,
    apply,
    propose,
)
from factory.telemetry import PassRateRow


def _row(
    role: str = "interface_architect",
    channel: str = "opencode",
    model: str | None = "kimi",
    gate_name: str = "interface_spec",
    total_evaluations: int = 10,
    first_attempt_passes: int = 8,
) -> PassRateRow:
    return PassRateRow(
        role=role,
        channel=channel,
        family="moonshot",
        gate_name=gate_name,
        total_evaluations=total_evaluations,
        first_attempt_passes=first_attempt_passes,
        total_passes=first_attempt_passes,
        model=model,
    )


def make_config():
    return FactoryConfig(
        workflow_name="wf",
        workflow_version=1,
        project_name="proj",
        dsn="",
        hmac_key_path="",
        roles=(
            RoleConfig(role="interface_architect", channel="opencode", model="kimi"),
            RoleConfig(role="test_author", channel="opencode", model="kimi"),
        ),
    )


class TestRateForRoleChannel:
    def test_exact_match(self):
        rows = [
            _row(
                role="interface_architect",
                channel="opencode",
                model="kimi",
                first_attempt_passes=6,
                total_evaluations=10,
            )
        ]
        rate, total = _rate_for_role_channel("interface_architect", "opencode", "kimi", rows)
        assert rate == pytest.approx(0.6)
        assert total == 10

    def test_no_match_returns_zero(self):
        rows = [_row()]
        rate, total = _rate_for_role_channel("nonexistent", "opencode", "kimi", rows)
        assert rate == 0.0
        assert total == 0

    def test_model_none_ignored(self):
        rows = [_row(model="kimi", first_attempt_passes=5, total_evaluations=10)]
        rate, total = _rate_for_role_channel("interface_architect", "opencode", None, rows)
        assert rate == pytest.approx(0.5)
        assert total == 10

    def test_gate_filter(self):
        rows = [
            _row(gate_name="interface_spec", first_attempt_passes=5, total_evaluations=10),
            _row(gate_name="another", first_attempt_passes=10, total_evaluations=10),
        ]
        rate, total = _rate_for_role_channel(
            "interface_architect", "opencode", "kimi", rows, gate_filter="interface_spec"
        )
        assert rate == pytest.approx(0.5)
        assert total == 10


class TestPropose:
    def test_no_change_when_current_is_best(self):
        config = make_config()
        rows = [
            _row(
                role="interface_architect",
                channel="opencode",
                model="kimi",
                first_attempt_passes=9,
                total_evaluations=10,
            ),
        ]
        diff = propose(rows, config)
        assert diff.changes == ()
        assert "interface_architect" in diff.untouched

    def test_proposes_change_when_alternative_better(self):
        config = make_config()
        rows = [
            _row(
                role="interface_architect",
                channel="opencode",
                model="kimi",
                first_attempt_passes=5,
                total_evaluations=10,
            ),
            _row(
                role="interface_architect",
                channel="claude-code",
                model="sonnet",
                first_attempt_passes=9,
                total_evaluations=10,
            ),
        ]
        diff = propose(rows, config)
        assert len(diff.changes) == 1
        ch = diff.changes[0]
        assert ch.role == "interface_architect"
        assert ch.current_channel == "opencode"
        assert ch.proposed_channel == "claude-code"
        assert ch.proposed_model == "sonnet"
        assert ch.proposed_rate == pytest.approx(0.9)
        assert ch.current_rate == pytest.approx(0.5)

    def test_no_data_roles_tracked(self):
        config = make_config()
        diff = propose([], config)
        assert "interface_architect" in diff.no_data
        assert "test_author" in diff.no_data

    def test_min_samples_filter(self):
        config = make_config()
        rows = [
            _row(
                role="interface_architect",
                channel="claude-code",
                model="sonnet",
                first_attempt_passes=1,
                total_evaluations=2,
            ),
        ]
        policy = PlacementPolicy(min_samples=5)
        diff = propose(rows, config, policy=policy)
        # Alternative doesn't meet min_samples so it is skipped
        assert "interface_architect" in diff.untouched

    def test_confidence_threshold_keeps_current(self):
        config = make_config()
        rows = [
            _row(
                role="interface_architect",
                channel="opencode",
                model="kimi",
                first_attempt_passes=8,
                total_evaluations=10,
            ),
            _row(
                role="interface_architect",
                channel="claude-code",
                model="sonnet",
                first_attempt_passes=9,
                total_evaluations=10,
            ),
        ]
        policy = PlacementPolicy(confidence_threshold=0.15)
        diff = propose(rows, config, policy=policy)
        # 90% vs 80% difference is 0.10 <= 0.15, so current is preferred
        assert "interface_architect" in diff.untouched

    def test_code_role_ignored(self):
        config = FactoryConfig(
            workflow_name="wf",
            workflow_version=1,
            project_name="proj",
            dsn="",
            hmac_key_path="",
            roles=(RoleConfig(role="mechanical_gate", channel="code"),),
        )
        rows = [_row(role="mechanical_gate", channel="code", model=None)]
        diff = propose(rows, config)
        assert diff.changes == ()
        assert diff.untouched == ()
        assert diff.no_data == ()


class TestApply:
    def test_dry_run_returns_path(self, tmp_path: Path):
        diff = PlacementDiff()
        config = make_config()
        path = apply(diff, config, mode="dry-run", output_dir=tmp_path)
        assert path is not None
        assert path.exists()
        assert "placement-" in str(path.name)

    def test_live_mode_returns_none(self):
        diff = PlacementDiff()
        config = make_config()
        result = apply(diff, config, mode="live")
        assert result is None

    def test_invalid_mode_raises(self):
        diff = PlacementDiff()
        config = make_config()
        with pytest.raises(ValueError, match="Unknown mode"):
            apply(diff, config, mode="bad")
