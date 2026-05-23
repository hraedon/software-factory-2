from __future__ import annotations

import uuid
from pathlib import Path

from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig
from factory.constants import (
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_UNKNOWN,
    TRANSITION_CLAIM,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
    TRANSITION_SUBMIT,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
)
from factory.telemetry import (
    ContractComplaintMetrics,
    GateAttempt,
    PassRateRow,
    RoutingHintMetrics,
    _looks_like_contract_complaint,
    collect_contract_complaints,
    collect_gate_attempts,
    collect_routing_hints,
    compute_pass_rates,
    format_contract_complaint_summary,
    format_pass_rate_table,
    format_routing_hint_summary,
)


def _make_config(sub: InMemorySubstrate) -> FactoryConfig:
    return FactoryConfig(
        workflow_name="software_factory",
        workflow_version=1,
        project_name=sub.project,
        dsn="",
        hmac_key_path="",
    )


def _worker_md(
    role: str = "interface_architect",
    channel: str = "claude-code",
    family: str = "anthropic",
    attempt_n: int = 1,
) -> dict:
    return {"role": role, "channel": channel, "family": family, "attempt_n": attempt_n}


def _gate_md(
    attempt_n: int = 1,
    gate_name: str = GATE_NAME_INTERFACE_SPEC_SYNTAX,
    passed: bool = True,
) -> tuple[str, dict, dict | None]:
    transition = TRANSITION_GATE_PASS if passed else TRANSITION_GATE_FAIL
    gate_actor_md = {
        "role": "mechanical_gate",
        "gate_name": gate_name,
        "attempt_n": attempt_n,
    }
    if passed:
        return (transition, gate_actor_md, None)
    payload = {"diagnostics": {"gate_name": gate_name, "passed": passed, "messages": []}}
    return (transition, gate_actor_md, payload)


def _seed_work_item(
    sub: InMemorySubstrate,
    work_item_type: str,
    worker_meta: dict | None = None,
    gate_events: list[tuple[str, dict, dict | None]] | None = None,
) -> str:
    wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=work_item_type,
        actor_id="test-actor",
        actor_kind="agent",
        custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
    )
    wid = wi.work_item_id
    wm = worker_meta or _worker_md()
    sub.transition(
        wid,
        TRANSITION_CLAIM,
        "test-actor",
        actor_metadata={"role": wm.get("role", "interface_architect")},
    )
    sub.transition(wid, TRANSITION_SUBMIT, "test-actor", actor_metadata=wm)
    for transition, gate_actor_md, payload in gate_events or []:
        sub.transition(
            wid,
            transition,
            "test-actor",
            actor_metadata=gate_actor_md,
            payload=payload,
        )
    return str(wid)


class TestCollectGateAttempts:
    def test_empty_substrate(self, mock_substrate):
        config = _make_config(mock_substrate)
        attempts = collect_gate_attempts(mock_substrate, config)
        assert attempts == []

    def test_collects_gate_pass_with_worker_role(self, mock_substrate):
        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
            ),
            gate_events=[_gate_md(passed=True)],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 1
        assert attempts[0].passed is True
        assert attempts[0].role == "interface_architect"
        assert attempts[0].channel == "claude-code"
        assert attempts[0].family == "anthropic"

    def test_collects_gate_fail(self, mock_substrate):
        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            gate_events=[_gate_md(attempt_n=1, passed=False)],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 1
        assert attempts[0].passed is False

    def test_ignores_non_gate_events(self, mock_substrate):
        config = _make_config(mock_substrate)
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": "interface_architect"},
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert attempts == []


class TestComputePassRates:
    def test_empty_attempts(self):
        rows = compute_pass_rates([])
        assert rows == []

    def test_single_first_attempt_pass(self):
        attempts = [
            GateAttempt(
                work_item_id="wi-1",
                work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
                attempt_n=1,
                gate_name="interface_spec_syntax",
                passed=True,
            ),
        ]
        rows = compute_pass_rates(attempts)
        assert len(rows) == 1
        assert rows[0].total_evaluations == 1
        assert rows[0].first_attempt_passes == 1
        assert rows[0].total_passes == 1

    def test_retry_then_pass(self):
        attempts = [
            GateAttempt(
                work_item_id="wi-1",
                work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
                attempt_n=1,
                gate_name="interface_spec_syntax",
                passed=False,
            ),
            GateAttempt(
                work_item_id="wi-1",
                work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
                attempt_n=2,
                gate_name="interface_spec_syntax",
                passed=True,
            ),
        ]
        rows = compute_pass_rates(attempts)
        assert len(rows) == 1
        assert rows[0].total_evaluations == 1
        assert rows[0].first_attempt_passes == 0
        assert rows[0].total_passes == 1

    def test_multiple_items_per_role_channel(self):
        attempts = [
            GateAttempt(
                work_item_id="wi-1",
                work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
                attempt_n=1,
                gate_name="interface_spec_syntax",
                passed=True,
            ),
            GateAttempt(
                work_item_id="wi-2",
                work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
                attempt_n=1,
                gate_name="interface_spec_syntax",
                passed=False,
            ),
        ]
        rows = compute_pass_rates(attempts)
        assert len(rows) == 1
        assert rows[0].total_evaluations == 2
        assert rows[0].first_attempt_passes == 1
        assert rows[0].total_passes == 1

    def test_groups_by_gate_name(self):
        attempts = [
            GateAttempt(
                work_item_id="wi-1",
                work_item_type="implementation",
                role="implementer",
                channel="claude-code",
                family="anthropic",
                attempt_n=1,
                gate_name="impl_mypy",
                passed=True,
            ),
            GateAttempt(
                work_item_id="wi-1",
                work_item_type="implementation",
                role="implementer",
                channel="claude-code",
                family="anthropic",
                attempt_n=1,
                gate_name="impl_pytest",
                passed=False,
            ),
        ]
        rows = compute_pass_rates(attempts)
        assert len(rows) == 2


class TestFormatPassRateTable:
    def test_empty(self):
        result = format_pass_rate_table([])
        assert "No gate evaluation data" in result

    def test_formats_table(self):
        rows = [
            PassRateRow(
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
                gate_name="interface_spec_syntax",
                total_evaluations=10,
                first_attempt_passes=8,
                total_passes=9,
            ),
        ]
        result = format_pass_rate_table(rows)
        assert "interface_architect" in result
        assert "claude-code" in result
        assert "80%" in result
        assert "90%" in result

    def test_pass_rate_row_zero_denominator(self):
        row = PassRateRow(
            role="r",
            channel="c",
            family="f",
            gate_name="g",
            total_evaluations=0,
            first_attempt_passes=0,
            total_passes=0,
        )
        assert row.first_attempt_rate == "\u2014"
        assert row.overall_rate == "\u2014"


class TestGateNameDataQuality:
    def test_gate_name_from_actor_metadata_on_pass(self, mock_substrate):
        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(),
            gate_events=[_gate_md(gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX, passed=True)],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 1
        assert attempts[0].gate_name == GATE_NAME_INTERFACE_SPEC_SYNTAX
        assert attempts[0].passed is True

    def test_gate_name_from_actor_metadata_on_fail(self, mock_substrate):
        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(),
            gate_events=[_gate_md(gate_name="interface_spec_ac_refs", passed=False)],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 1
        assert attempts[0].gate_name == "interface_spec_ac_refs"
        assert attempts[0].passed is False

    def test_gate_name_from_payload_fallback_when_missing_from_metadata(self, mock_substrate):
        config = _make_config(mock_substrate)
        gate_actor_md = {"role": "mechanical_gate", "attempt_n": 1}
        payload = {
            "diagnostics": {
                "gate_name": GATE_NAME_IMPLEMENTATION_MYPY,
                "passed": False,
                "messages": [],
            }
        }
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(),
            gate_events=[(TRANSITION_GATE_FAIL, gate_actor_md, payload)],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 1
        assert attempts[0].gate_name == GATE_NAME_IMPLEMENTATION_MYPY

    def test_gate_pass_event_with_no_payload_resolves_from_metadata(self, mock_substrate):
        config = _make_config(mock_substrate)
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=_worker_md(),
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_GATE_PASS,
            "test-actor",
            actor_metadata={
                "role": "mechanical_gate",
                "gate_name": GATE_NAME_INTERFACE_SPEC_SYNTAX,
                "attempt_n": 1,
            },
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 1
        assert attempts[0].gate_name == GATE_NAME_INTERFACE_SPEC_SYNTAX
        assert attempts[0].passed is True

    def test_no_unknown_gate_names_in_realistic_event_stream(self, mock_substrate):
        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
            ),
            gate_events=[
                _gate_md(gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX, passed=True),
            ],
        )
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
            ),
            gate_events=[
                _gate_md(gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX, passed=True),
            ],
        )
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(
                role="interface_architect",
                channel="claude-code",
                family="anthropic",
            ),
            gate_events=[
                _gate_md(gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX, passed=True),
            ],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        assert len(attempts) == 3
        unknown = [a for a in attempts if a.gate_name == GATE_NAME_UNKNOWN]
        assert not unknown, (
            f"Found unknown gate names: {[(a.work_item_id, a.gate_name) for a in unknown]}"
        )
        rows = compute_pass_rates(attempts)
        assert all(r.gate_name != GATE_NAME_UNKNOWN for r in rows)

    def test_first_attempt_pass_rate_above_zero(self, mock_substrate):
        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(),
            gate_events=[_gate_md(gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX, passed=True)],
        )
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(),
            gate_events=[_gate_md(gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX, passed=True)],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        rows = compute_pass_rates(attempts)
        assert len(rows) == 1
        assert rows[0].first_attempt_passes > 0


class TestDeterministicGateParity:
    def test_all_gate_name_constants_in_deterministic_set(self):
        """Every GATE_NAME_* constant (except known non-deterministic ones)
        must appear in telemetry's deterministic_gates set.
        """
        import factory.constants as constants
        import factory.telemetry as telemetry

        gate_constants = {
            name: value for name, value in vars(constants).items() if name.startswith("GATE_NAME_")
        }
        known_non_deterministic = {
            constants.GATE_NAME_UNKNOWN,
            constants.GATE_NAME_UNKNOWN_TYPE,
            constants.GATE_NAME_BEHAVIORAL,
            constants.GATE_NAME_OUTCOME_E2E,
        }
        missing = []
        for name, value in gate_constants.items():
            if value in known_non_deterministic:
                continue
            if value not in telemetry.DETERMINISTIC_GATES:
                missing.append(name)
        assert not missing, (
            f"Gate-name constants missing from telemetry.DETERMINISTIC_GATES: {missing}"
        )

    def test_deterministic_set_has_no_orphan_names(self):
        """Every entry in telemetry's deterministic_gates must correspond to
        a GATE_NAME_* constant (or a composite gate name like 'interface_spec').
        """
        import factory.constants as constants
        import factory.telemetry as telemetry

        constant_values = {
            value for name, value in vars(constants).items() if name.startswith("GATE_NAME_")
        }
        # Composite gate names that are intentionally in the set but not constants
        # (they are umbrella names used when actor_metadata lacks a specific gate)
        composite_exceptions = {
            "interface_spec",
            "test_suite",
            "implementation",
            "inner_import",
        }
        orphans = []
        for gate in telemetry.DETERMINISTIC_GATES:
            if gate not in constant_values and gate not in composite_exceptions:
                orphans.append(gate)
        assert not orphans, (
            f"telemetry.DETERMINISTIC_GATES contains entries with no matching "
            f"GATE_NAME_* constant: {orphans}"
        )


class TestComputeExitCriteria:
    def test_first_gate_evaluation_counts_attempt_n_two(self, mock_substrate):
        """Production gate claims happen at attempt_n>=2; first-gate-evaluation
        rate must still be computed correctly."""
        from factory.telemetry import compute_exit_criteria

        config = _make_config(mock_substrate)
        _seed_work_item(
            mock_substrate,
            WORK_ITEM_TYPE_INTERFACE_SPEC,
            worker_meta=_worker_md(),
            gate_events=[
                _gate_md(
                    attempt_n=2,
                    gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
                    passed=True,
                ),
            ],
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        metrics = compute_exit_criteria(mock_substrate, config, attempts)
        assert metrics.first_gate_evaluation_passes == 1
        assert metrics.first_gate_evaluation_evaluations == 1
        assert metrics.first_gate_evaluation_pass_rate == 1.0

    def test_first_gate_evaluation_with_retry(self, mock_substrate):
        """A work item that fails first gate then passes on retry."""
        from factory.telemetry import compute_exit_criteria

        config = _make_config(mock_substrate)
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        wid = wi.work_item_id
        wm = _worker_md()
        gate_md = {
            "role": "mechanical_gate",
            "gate_name": GATE_NAME_INTERFACE_SPEC_SYNTAX,
        }
        fail_payload = {
            "diagnostics": {
                "gate_name": GATE_NAME_INTERFACE_SPEC_SYNTAX,
                "passed": False,
                "messages": [],
            },
        }
        # First attempt: claim → submit → gate_fail
        mock_substrate.transition(
            wid,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": wm["role"]},
        )
        mock_substrate.transition(
            wid,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=wm,
        )
        mock_substrate.transition(
            wid,
            TRANSITION_GATE_FAIL,
            "test-actor",
            actor_metadata={**gate_md, "attempt_n": 2},
            payload=fail_payload,
        )
        # Second attempt: claim → submit → gate_pass
        mock_substrate.transition(
            wid,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": wm["role"]},
        )
        mock_substrate.transition(
            wid,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=wm,
        )
        mock_substrate.transition(
            wid,
            TRANSITION_GATE_PASS,
            "test-actor",
            actor_metadata={**gate_md, "attempt_n": 3},
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        metrics = compute_exit_criteria(mock_substrate, config, attempts)
        assert metrics.first_gate_evaluation_passes == 0
        assert metrics.first_gate_evaluation_evaluations == 1
        assert metrics.first_gate_evaluation_pass_rate == 0.0
        assert metrics.lock_within_budget_rate == 1.0

    def test_inner_gate_attempts_extracted_from_submit_payload(self, mock_substrate):
        from factory.telemetry import compute_exit_criteria

        config = _make_config(mock_substrate)
        wm = _worker_md(role="interface_architect", channel="opencode", family="opencode")
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        wid = wi.work_item_id
        mock_substrate.transition(
            wid,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": wm["role"]},
        )
        mock_substrate.transition(
            wid,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=wm,
            payload={
                "duration_seconds": 42.0,
                "inner_gate_attempts": [
                    {
                        "retry": 0,
                        "gate_name": "inner_pytest",
                        "passed": False,
                        "diagnostics": ["fail"],
                    },
                    {
                        "retry": 1,
                        "gate_name": "inner_pytest",
                        "passed": True,
                        "diagnostics": [],
                    },
                ],
            },
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        inner = [a for a in attempts if a.gate_name.startswith("inner_")]
        assert len(inner) == 2
        assert inner[0].gate_name == "inner_pytest"
        assert inner[0].passed is False
        assert inner[1].gate_name == "inner_pytest"
        assert inner[1].passed is True

        metrics = compute_exit_criteria(mock_substrate, config, attempts)
        assert metrics.inner_gate_evaluations == 1
        assert metrics.inner_gate_first_passes == 0
        assert metrics.inner_gate_first_pass_rate == 0.0

        # RFC-029 buckets: retry=0 failed, retry=1 passed
        assert metrics.inner_gate_attempt_1_recovery_count == 1
        assert metrics.inner_gate_attempt_1_total == 1
        assert metrics.inner_gate_attempt_1_recovery_rate == 1.0
        assert metrics.inner_gate_attempt_0_passes == 0
        assert metrics.inner_gate_attempt_2plus_count == 0
        assert metrics.inner_gate_exhausted_budget_count == 0
        assert len(metrics.inner_gate_item_attempts) == 1
        assert metrics.inner_gate_item_attempts[0][1] == 2  # 2 evals

    def test_rfc029_attempt_0_pass_bucket(self, mock_substrate):
        """Item that passes inner gate on first evaluation → bucket_0."""
        from factory.telemetry import compute_exit_criteria

        config = _make_config(mock_substrate)
        wm = _worker_md()
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        wid = wi.work_item_id
        mock_substrate.transition(
            wid, TRANSITION_CLAIM, "test-actor", actor_metadata={"role": wm["role"]}
        )
        mock_substrate.transition(
            wid,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=wm,
            payload={
                "inner_gate_attempts": [
                    {"retry": 0, "gate_name": "inner_mypy", "passed": True, "diagnostics": []},
                ]
            },
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        metrics = compute_exit_criteria(mock_substrate, config, attempts)
        assert metrics.inner_gate_attempt_0_passes == 1
        assert metrics.inner_gate_attempt_1_total == 0
        assert metrics.inner_gate_attempt_2plus_total == 0
        assert metrics.inner_gate_exhausted_budget_total == 0

    def test_rfc029_attempt_2plus_bucket(self, mock_substrate):
        """Item needing retry 0 fail, retry 1 fail, retry 2 pass → bucket_2plus."""
        from factory.telemetry import compute_exit_criteria

        config = _make_config(mock_substrate)
        wm = _worker_md()
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        wid = wi.work_item_id
        mock_substrate.transition(
            wid, TRANSITION_CLAIM, "test-actor", actor_metadata={"role": wm["role"]}
        )
        mock_substrate.transition(
            wid,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=wm,
            payload={
                "inner_gate_attempts": [
                    {
                        "retry": 0,
                        "gate_name": "inner_mypy",
                        "passed": False,
                        "diagnostics": ["err"],
                    },
                    {
                        "retry": 1,
                        "gate_name": "inner_mypy",
                        "passed": False,
                        "diagnostics": ["err"],
                    },
                    {"retry": 2, "gate_name": "inner_mypy", "passed": True, "diagnostics": []},
                ]
            },
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        metrics = compute_exit_criteria(mock_substrate, config, attempts)
        assert metrics.inner_gate_attempt_2plus_count == 1
        assert metrics.inner_gate_attempt_2plus_total == 1
        assert metrics.inner_gate_attempt_2plus_rate == 1.0
        assert metrics.inner_gate_attempt_0_passes == 0
        assert metrics.inner_gate_attempt_1_total == 0
        assert metrics.inner_gate_exhausted_budget_total == 0
        assert len(metrics.inner_gate_item_attempts) == 1
        assert metrics.inner_gate_item_attempts[0][1] == 3

    def test_rfc029_exhausted_budget_bucket(self, mock_substrate):
        """Item that never passes within retries → exhausted."""
        from factory.telemetry import compute_exit_criteria

        config = _make_config(mock_substrate)
        wm = _worker_md()
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        wid = wi.work_item_id
        mock_substrate.transition(
            wid, TRANSITION_CLAIM, "test-actor", actor_metadata={"role": wm["role"]}
        )
        mock_substrate.transition(
            wid,
            TRANSITION_SUBMIT,
            "test-actor",
            actor_metadata=wm,
            payload={
                "inner_gate_attempts": [
                    {
                        "retry": 0,
                        "gate_name": "inner_mypy",
                        "passed": False,
                        "diagnostics": ["err"],
                    },
                    {
                        "retry": 1,
                        "gate_name": "inner_pytest",
                        "passed": False,
                        "diagnostics": ["err"],
                    },
                ]
            },
        )
        attempts = collect_gate_attempts(mock_substrate, config)
        metrics = compute_exit_criteria(mock_substrate, config, attempts)
        assert metrics.inner_gate_exhausted_budget_count == 2
        assert metrics.inner_gate_exhausted_budget_total == 2
        assert metrics.inner_gate_exhausted_budget_rate == 1.0
        assert metrics.inner_gate_attempt_0_passes == 0
        assert metrics.inner_gate_attempt_1_total == 0
        assert metrics.inner_gate_attempt_2plus_total == 0
        assert len(metrics.inner_gate_item_attempts) == 2

    def test_signature_match(self):
        assert _looks_like_contract_complaint("function signature is wrong") is True
        assert _looks_like_contract_complaint("signature mismatch") is True

    def test_parameter_missing_match(self):
        assert _looks_like_contract_complaint("parameter missing from interface") is True
        assert _looks_like_contract_complaint("parameter wrong type") is True
        assert _looks_like_contract_complaint("parameter extra") is True

    def test_interface_broken_match(self):
        assert _looks_like_contract_complaint("interface broken") is True
        assert (
            _looks_like_contract_complaint("interface is invalid") is False
        )  # pattern requires keyword directly after whitespace
        assert _looks_like_contract_complaint("interface wrong") is True
        assert _looks_like_contract_complaint("interface mismatch") is True

    def test_wrong_return_type_match(self):
        assert _looks_like_contract_complaint("wrong return type") is True
        assert (
            _looks_like_contract_complaint("return type mismatch") is True
        )  # "type mismatch" pattern covers this

    def test_should_return_match(self):
        assert _looks_like_contract_complaint("function should return int") is True

    def test_contract_broken_match(self):
        assert _looks_like_contract_complaint("contract broken") is True
        assert _looks_like_contract_complaint("contract is wrong") is True

    def test_type_mismatch_match(self):
        assert _looks_like_contract_complaint("type mismatch") is True

    def test_incompatible_signature_match(self):
        assert _looks_like_contract_complaint("incompatible signature") is True

    def test_function_signature_match(self):
        assert _looks_like_contract_complaint("function signature changed") is True

    def test_negative_cases(self):
        assert _looks_like_contract_complaint("import error") is False
        assert _looks_like_contract_complaint("syntax error at line 5") is False
        assert _looks_like_contract_complaint("mypy failed") is False
        assert _looks_like_contract_complaint("test timed out") is False
        assert _looks_like_contract_complaint("") is False
        assert (
            _looks_like_contract_complaint("wrong parameter name") is False
        )  # pattern requires "parameter" prefix

    def test_collects_contract_complaints(self, mock_substrate):
        config = _make_config(mock_substrate)
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_ROUTE_TO_CANNOT_PROCEED,
            "test-actor",
            actor_metadata={"role": "interface_architect", "attempt_n": 1},
            custom_fields={"diagnostics": {"rationale": "function signature is wrong"}},
        )
        metrics = collect_contract_complaints(mock_substrate, config)
        assert metrics.total_cannot_proceed == 1
        assert metrics.contract_shaped == 1
        assert len(metrics.samples) == 1

    def test_no_contract_complaint_for_generic_failure(self, mock_substrate):
        config = _make_config(mock_substrate)
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            actor_id="test-actor",
            actor_kind="agent",
            custom_fields={"spec_section": "test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_CLAIM,
            "test-actor",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_ROUTE_TO_CANNOT_PROCEED,
            "test-actor",
            actor_metadata={"role": "interface_architect", "attempt_n": 1},
            custom_fields={"diagnostics": {"rationale": "import error"}},
        )
        metrics = collect_contract_complaints(mock_substrate, config)
        assert metrics.total_cannot_proceed == 1
        assert metrics.contract_shaped == 0

    def test_format_summary(self):
        metrics = ContractComplaintMetrics(
            total_cannot_proceed=2,
            contract_shaped=1,
            cross_family_review_agreed=0,
            samples=["function signature is wrong"],
        )
        summary = format_contract_complaint_summary(metrics)
        assert "Contract Complaint Telemetry" in summary
        assert "Total cannot_proceed events:        2" in summary
        assert "Contract-shaped rationales:         1" in summary
        assert "function signature is wrong" in summary

    def test_zero_events_summary(self):
        metrics = ContractComplaintMetrics(
            total_cannot_proceed=0,
            contract_shaped=0,
            cross_family_review_agreed=0,
            samples=[],
        )
        summary = format_contract_complaint_summary(metrics)
        assert "Total cannot_proceed events:        0" in summary
        assert "Contract-shaped rationales:         0" in summary


class TestRoutingHintTelemetry:
    def _p5_sub(self):
        from pathlib import Path

        phase5_path = Path(__file__).parent.parent / "workflows" / "phase5.yaml"
        sub = InMemorySubstrate()
        sub.register_workflow_file(str(phase5_path))
        return sub

    def test_collects_routing_hint_on_outcome_verification_fail(self):
        sub = self._p5_sub()
        config = FactoryConfig(
            dsn="",
            project_name=sub.project,
            hmac_key_path="",
            workspace_root=Path("/tmp/telemetry_test"),
            workflow_version=5,
        )
        int_wi, _ = sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={"spec_section": "T", "ac_ids": []},
        )
        wi, _ = sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verifier",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "integration_ref": str(int_wi.work_item_id),
            },
        )
        sub.register_actor_role("gate", "mechanical_gate")
        sub.transition(
            wi.work_item_id,
            "claim",
            "worker",
            actor_metadata={"role": "outcome_verifier"},
        )
        sub.transition(
            wi.work_item_id,
            "submit",
            "worker",
            actor_metadata={"role": "outcome_verifier"},
        )
        sub.acquire_claim(wi.work_item_id, "gate", ttl_seconds=300)
        sub.transition(
            wi.work_item_id,
            TRANSITION_GATE_FAIL,
            "gate",
            actor_metadata={"role": "mechanical_gate", "gate_name": "outcome_e2e"},
            payload={
                "diagnostics": {
                    "message": "Outcome verification failed: coverage gap",
                    "routing_hint": {"work_item_type": "implementation", "reason": "stub missing"},
                }
            },
        )
        metrics = collect_routing_hints(sub, config)
        assert metrics.total_outcome_fail == 1
        assert metrics.routing_hint_present == 1
        assert metrics.routing_hint_by_type == {"implementation": 1}
        assert len(metrics.samples) == 1
        assert metrics.samples[0]["hint_type"] == "implementation"
        sub.close()

    def test_no_routing_hint_when_absent(self):
        sub = self._p5_sub()
        config = FactoryConfig(
            dsn="",
            project_name=sub.project,
            hmac_key_path="",
            workspace_root=Path("/tmp/telemetry_test"),
            workflow_version=5,
        )
        int_wi, _ = sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={"spec_section": "T", "ac_ids": []},
        )
        wi, _ = sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verifier",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "integration_ref": str(int_wi.work_item_id),
            },
        )
        sub.register_actor_role("gate", "mechanical_gate")
        sub.transition(
            wi.work_item_id,
            "claim",
            "worker",
            actor_metadata={"role": "outcome_verifier"},
        )
        sub.transition(
            wi.work_item_id,
            "submit",
            "worker",
            actor_metadata={"role": "outcome_verifier"},
        )
        sub.acquire_claim(wi.work_item_id, "gate", ttl_seconds=300)
        sub.transition(
            wi.work_item_id,
            TRANSITION_GATE_FAIL,
            "gate",
            actor_metadata={"role": "mechanical_gate", "gate_name": "outcome_e2e"},
            payload={"diagnostics": {"message": "Just failed"}},
        )
        metrics = collect_routing_hints(sub, config)
        assert metrics.total_outcome_fail == 1
        assert metrics.routing_hint_present == 0
        assert metrics.routing_hint_by_type == {}
        assert metrics.samples == []
        sub.close()

    def test_ignores_non_outcome_verification_items(self, mock_substrate):
        config = _make_config(mock_substrate)
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="arch",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("gate", "mechanical_gate")
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_CLAIM,
            "worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_SUBMIT,
            "worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.acquire_claim(wi.work_item_id, "gate", ttl_seconds=300)
        mock_substrate.transition(
            wi.work_item_id,
            TRANSITION_GATE_FAIL,
            "gate",
            actor_metadata={"role": "mechanical_gate", "gate_name": "interface_spec_syntax"},
            payload={"diagnostics": {"routing_hint": {"work_item_type": "test_suite"}}},
        )
        metrics = collect_routing_hints(mock_substrate, config)
        assert metrics.total_outcome_fail == 0
        assert metrics.routing_hint_present == 0

    def test_format_routing_hint_summary(self):
        metrics = RoutingHintMetrics(
            total_outcome_fail=3,
            routing_hint_present=2,
            routing_hint_by_type={"implementation": 1, "test_suite": 1},
            samples=[
                {
                    "work_item_id": str(uuid.uuid4()),
                    "rationale": "coverage gap",
                    "hint_type": "implementation",
                    "hint_reason": "stub missing",
                }
            ],
        )
        summary = format_routing_hint_summary(metrics)
        assert "Routing Hint Telemetry (BC-145)" in summary
        assert "Total outcome_verification gate_fail events: 3" in summary
        assert "implementation: 1" in summary
        assert "test_suite: 1" in summary

    def test_zero_events_summary(self):
        metrics = RoutingHintMetrics(
            total_outcome_fail=0,
            routing_hint_present=0,
            routing_hint_by_type={},
            samples=[],
        )
        summary = format_routing_hint_summary(metrics)
        assert "Total outcome_verification gate_fail events: 0" in summary
        assert "Routing hints present:                        0" in summary
