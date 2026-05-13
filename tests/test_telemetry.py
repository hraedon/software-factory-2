from __future__ import annotations

from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig
from factory.constants import (
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_UNKNOWN,
    TRANSITION_CLAIM,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_SUBMIT,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
)
from factory.telemetry import (
    GateAttempt,
    PassRateRow,
    collect_gate_attempts,
    compute_pass_rates,
    format_pass_rate_table,
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
