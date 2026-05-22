from __future__ import annotations

import os
import signal
from pathlib import Path
from unittest.mock import patch

import pytest
from substrate import ActorMetadata
from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig
from factory.constants import (
    CUSTOM_FIELD_DIAGNOSTICS,
    CUSTOM_FIELD_REVIEW_FINDINGS,
    STATE_CANNOT_PROCEED,
    STATE_NEW,
    TRANSITION_GATE_PASS,
    WORK_ITEM_TYPE_IMPLEMENTATION,
)
from factory.gate_process import gate_loop, process_gate_item
from factory.runtime import PipelineRuntime

PHASE5_WORKFLOW = Path(__file__).parent.parent / "workflows" / "phase5.yaml"

REVIEW_FINDINGS_JSON = (
    '{"passed": false, "findings": '
    '[{"ac_id": "AC-01", "kind": "impl", "severity": "block", "body": "test"}]}'
)


@pytest.fixture()
def phase5_sub():
    sub = InMemorySubstrate()
    sub.register_workflow_file(str(PHASE5_WORKFLOW))
    yield sub
    sub.close()


@pytest.fixture()
def phase5_config(tmp_path):
    return FactoryConfig(
        dsn="",
        project_name="test",
        hmac_key_path="",
        workspace_root=tmp_path / "work",
        workflow_version=5,
    )


class TestReviewFindingsFilteredOnReviewType:
    def test_review_findings_not_written_to_review_wi(self, phase5_sub, phase5_config, tmp_path):
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        test_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
            },
        )
        impl_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(test_wi.work_item_id),
            },
        )
        review_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="review",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(test_wi.work_item_id),
                "implementation_ref": str(impl_wi.work_item_id),
            },
        )
        artifact_path = tmp_path / "review.json"
        artifact_path.write_text(REVIEW_FINDINGS_JSON)
        phase5_sub.transition(
            review_wi.work_item_id,
            "claim",
            "test-reviewer",
            actor_metadata={"role": "cross_family_reviewer"},
        )
        phase5_sub.transition(
            review_wi.work_item_id,
            "submit",
            "test-reviewer",
            actor_metadata={"role": "cross_family_reviewer"},
            custom_fields={
                "artifact_path": str(artifact_path),
                "artifact_hash": "abc",
            },
        )
        phase5_sub.register_actor_role("test-gate-rv", "mechanical_gate")
        claim = phase5_sub.acquire_claim(review_wi.work_item_id, "test-gate-rv", ttl_seconds=300)
        fresh = phase5_sub.get_work_item(review_wi.work_item_id)

        runtime = PipelineRuntime(sub=phase5_sub, config=phase5_config)
        process_gate_item(runtime, fresh, "test-gate-rv", claim)

        final = phase5_sub.get_work_item(review_wi.work_item_id)
        assert final.current_state == "new"
        custom_fields = final.custom_fields or {}
        # BC-185: review_findings now lives in routing_fields (not transition_fields),
        # so it must never appear in the review work item's stored custom fields.
        assert CUSTOM_FIELD_REVIEW_FINDINGS not in custom_fields, (
            f"review_findings should NOT be on review type (BC-185), but found: {custom_fields}"
        )
        assert CUSTOM_FIELD_DIAGNOSTICS in custom_fields, (
            f"diagnostics should be on review type, but missing: {custom_fields}"
        )


class TestGateBudgetGuardrail:
    def test_attempt_threshold_blocks_over_budget_items(self, phase5_sub, phase5_config):
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        phase5_sub.register_actor_role("test-gate-budget", "mechanical_gate")
        phase5_sub.transition(
            iface_wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        phase5_sub.transition(
            iface_wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/nonexistent.pyi", "artifact_hash": "abc"},
        )
        for _ in range(phase5_config.attempt_threshold):
            phase5_sub.acquire_claim(iface_wi.work_item_id, "test-gate-budget", ttl_seconds=300)
            phase5_sub.release_claim(iface_wi.work_item_id, "test-gate-budget")

        claim = phase5_sub.acquire_claim(iface_wi.work_item_id, "test-gate-budget", ttl_seconds=300)
        assert claim.attempt_number >= phase5_config.attempt_threshold

        wi = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert wi.current_state == "gating"

    def test_near_budget_items_remain_in_gating_state(self, phase5_sub, phase5_config):
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        phase5_sub.register_actor_role("test-gate-budget2", "mechanical_gate")
        phase5_sub.transition(
            iface_wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        phase5_sub.transition(
            iface_wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/nonexistent.pyi", "artifact_hash": "abc"},
        )
        claim = phase5_sub.acquire_claim(
            iface_wi.work_item_id, "test-gate-budget2", ttl_seconds=300
        )
        assert claim.attempt_number == 1
        assert claim.attempt_number < phase5_config.attempt_threshold

    def test_budget_exhausted_hard_transitions_to_cannot_proceed(
        self, phase5_sub, phase5_config, tmp_path
    ):
        """BC-186 AC-1: gate_loop hard-transitions to cannot_proceed (not just release) when
        attempt_number >= attempt_threshold, preventing indefinite acquire/release cycling."""
        import os
        import signal
        from unittest.mock import patch

        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        phase5_sub.register_actor_role("test-gate-bc186", "mechanical_gate")
        phase5_sub.transition(
            iface_wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        phase5_sub.transition(
            iface_wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/nonexistent.pyi", "artifact_hash": "abc"},
        )

        config = FactoryConfig(
            dsn="",
            project_name="test",
            hmac_key_path="",
            workspace_root=tmp_path / "work",
            workflow_version=5,
            attempt_threshold=3,
            poll_interval_seconds=0,
        )
        # Burn attempt_number up to the threshold via acquire/release cycles.
        for _ in range(config.attempt_threshold):
            phase5_sub.acquire_claim(iface_wi.work_item_id, "test-gate-bc186", ttl_seconds=300)
            phase5_sub.release_claim(iface_wi.work_item_id, "test-gate-bc186")

        # Confirm the item is still in gating and at threshold before gate_loop runs.
        wi = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert wi.current_state == "gating"

        runtime = PipelineRuntime(sub=phase5_sub, config=config)

        sleep_calls = [0]

        def _sleep_then_sigterm(*args, **kwargs):
            sleep_calls[0] += 1
            if sleep_calls[0] >= 1:
                os.kill(os.getpid(), signal.SIGTERM)

        with patch("factory.gate_process.time.sleep", side_effect=_sleep_then_sigterm):
            gate_loop(runtime)

        final = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert final.current_state == STATE_CANNOT_PROCEED, (
            f"BC-186: expected cannot_proceed after gate_near_budget at threshold, "
            f"got: {final.current_state}"
        )


def _make_crashy_wi(phase5_sub, tmp_path):
    """Create an interface_spec work item in gating state."""
    iface_wi, _ = phase5_sub.create_work_item(
        workflow_name="software_factory",
        work_item_type="interface_spec",
        actor_id="test-creator",
        custom_fields={
            "spec_section": "Test",
            "ac_ids": ["AC-01"],
            "artifact_path": str(tmp_path / "iface.pyi"),
            "artifact_hash": "abc",
        },
    )
    phase5_sub.transition(
        iface_wi.work_item_id,
        "claim",
        "test-worker",
        actor_metadata={"role": "interface_architect"},
    )
    phase5_sub.transition(
        iface_wi.work_item_id,
        "submit",
        "test-worker",
        actor_metadata={"role": "interface_architect"},
        custom_fields={
            "artifact_path": str(tmp_path / "iface.pyi"),
            "artifact_hash": "abc",
        },
    )
    return iface_wi


class TestGateCrashLoopCircuitBreaker:
    """AC-1: identical-error crash-loop escalates to cannot_proceed after gate_crash_threshold."""

    def _make_sleep_sentinel(self, max_sleeps: int):
        """Return a sleep mock that sends SIGTERM after max_sleeps calls."""
        sleep_calls = [0]

        def _sleep(*args, **kwargs):
            sleep_calls[0] += 1
            if sleep_calls[0] >= max_sleeps:
                os.kill(os.getpid(), signal.SIGTERM)

        return _sleep

    def test_identical_crash_escalates_to_cannot_proceed(self, phase5_sub, phase5_config, tmp_path):
        """AC-1: N identical crashes on the same item → gate_escalation → cannot_proceed."""
        iface_wi = _make_crashy_wi(phase5_sub, tmp_path)

        crash_threshold = 3
        config = FactoryConfig(
            dsn="",
            project_name="test",
            hmac_key_path="",
            workspace_root=tmp_path / "work",
            workflow_version=5,
            gate_crash_threshold=crash_threshold,
            attempt_threshold=20,
            poll_interval_seconds=0,
        )
        runtime = PipelineRuntime(sub=phase5_sub, config=config)

        call_count = [0]

        def _always_crash(rt, wi, actor_id, claim, **_kwargs):
            call_count[0] += 1
            raise RuntimeError("CUSTOM_FIELD_VIOLATION: field not found")

        # With crash_threshold=3:
        # - Crash 1: release claim, sleep (sleep #1)
        # - Crash 2: release claim, sleep (sleep #2)
        # - Crash 3: escalate (claimed=True, no sleep this iter),
        #   next query returns empty → sleep (sleep #3) → SIGTERM
        sleep_sentinel = self._make_sleep_sentinel(max_sleeps=crash_threshold)

        with patch("factory.gate_process.process_gate_item", side_effect=_always_crash):
            with patch("factory.gate_process.time.sleep", side_effect=sleep_sentinel):
                gate_loop(runtime)

        assert call_count[0] == crash_threshold, (
            f"Expected {crash_threshold} crash calls, got {call_count[0]}"
        )
        final = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert final.current_state == STATE_CANNOT_PROCEED, (
            f"Expected cannot_proceed after {crash_threshold} identical crashes, "
            f"got: {final.current_state}"
        )

    def test_differing_errors_do_not_prematurely_escalate(
        self, phase5_sub, phase5_config, tmp_path
    ):
        """Different errors reset the crash counter; escalation only fires on N *identical* errors.

        Sequence: alpha(1), beta(1), beta(2), beta(3=escalate)
        Total calls=4, not 3.
        """
        iface_wi = _make_crashy_wi(phase5_sub, tmp_path)

        crash_threshold = 3
        config = FactoryConfig(
            dsn="",
            project_name="test",
            hmac_key_path="",
            workspace_root=tmp_path / "work",
            workflow_version=5,
            gate_crash_threshold=crash_threshold,
            attempt_threshold=20,
            poll_interval_seconds=0,
        )
        runtime = PipelineRuntime(sub=phase5_sub, config=config)

        errors = [
            RuntimeError("error-alpha"),  # call 1: count_alpha=1 (no escalate)
            RuntimeError("error-beta"),  # call 2: count_beta=1  (no escalate, alpha reset)
            RuntimeError("error-beta"),  # call 3: count_beta=2  (no escalate)
            RuntimeError("error-beta"),  # call 4: count_beta=3  → escalate
        ]
        call_count = [0]

        def _sequence_crash(rt, wi, actor_id, claim, **_kwargs):
            idx = call_count[0]
            call_count[0] += 1
            raise errors[idx]

        # Sleeps: after call1(alpha), after call2(beta), after call3(beta).
        # Call4(beta) escalates → next query empty → sleep #4 → SIGTERM.
        sleep_sentinel = self._make_sleep_sentinel(max_sleeps=4)

        with patch("factory.gate_process.process_gate_item", side_effect=_sequence_crash):
            with patch("factory.gate_process.time.sleep", side_effect=sleep_sentinel):
                gate_loop(runtime)

        assert call_count[0] == 4, (
            f"Expected 4 crash calls (alpha+beta+beta+beta), got {call_count[0]}"
        )
        final = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert final.current_state == STATE_CANNOT_PROCEED, (
            f"Expected escalation after 3 identical 'beta' crashes, got: {final.current_state}"
        )

    def test_successful_gate_clears_crash_counter(self, phase5_sub, phase5_config, tmp_path):
        """A successful process_gate_item call resets the crash counter for that item."""
        iface_wi = _make_crashy_wi(phase5_sub, tmp_path)

        crash_threshold = 3
        config = FactoryConfig(
            dsn="",
            project_name="test",
            hmac_key_path="",
            workspace_root=tmp_path / "work",
            workflow_version=5,
            gate_crash_threshold=crash_threshold,
            attempt_threshold=20,
            poll_interval_seconds=0,
        )
        runtime = PipelineRuntime(sub=phase5_sub, config=config)

        call_count = [0]

        def _crash_then_succeed(rt, wi, actor_id, claim, **_kwargs):
            call_count[0] += 1
            if call_count[0] < crash_threshold:
                raise RuntimeError("CUSTOM_FIELD_VIOLATION: transient crash")
            # On the crash_threshold-th call, simulate a successful gate pass
            # by transitioning the item. gate_loop will see claimed=True and break.
            actor_metadata = ActorMetadata(
                role="mechanical_gate",
                channel="code",
                family="code",
                gate_name="interface_spec",
                attempt_n=claim.attempt_number,
            ).to_dict()
            rt.sub.transition(
                wi.work_item_id,
                TRANSITION_GATE_PASS,
                actor_id,
                actor_metadata=actor_metadata,
            )

        # Sleeps: after crash 1, after crash 2. On call 3 (success): claimed=True,
        # next query returns empty → sleep #3 → SIGTERM.
        sleep_sentinel = self._make_sleep_sentinel(max_sleeps=crash_threshold)

        with patch("factory.gate_process.process_gate_item", side_effect=_crash_then_succeed):
            with patch("factory.gate_process.time.sleep", side_effect=sleep_sentinel):
                gate_loop(runtime)

        # Item should be locked (gate_pass succeeded), not cannot_proceed
        final = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert final.current_state == "locked", (
            f"Expected locked (success cleared crash counter before threshold), "
            f"got: {final.current_state}"
        )
        assert call_count[0] == crash_threshold, (
            f"Expected {crash_threshold} calls "
            f"(crash x{crash_threshold - 1} + success x1), "
            f"got {call_count[0]}"
        )

    def test_legitimate_gate_fail_does_not_escalate(self, phase5_sub, phase5_config, tmp_path):
        """AC-2: A legitimate gate failure (mypy/pytest/ruff) routes through gate_fail → new,
        not through the crash-loop circuit breaker.
        """
        # Legitimate gate failures are handled inside process_gate_item — no exception is raised.
        # We verify this by calling process_gate_item with an artifact that fails the gate
        # and confirming: (a) no exception raised, (b) item lands in STATE_NEW.
        (tmp_path / "iface.pyi").write_text("# empty — triggers gate fail\n")
        iface_wi = _make_crashy_wi(phase5_sub, tmp_path)

        phase5_sub.register_actor_role("test-gate-legit", "mechanical_gate")
        claim = phase5_sub.acquire_claim(iface_wi.work_item_id, "test-gate-legit", ttl_seconds=300)
        fresh = phase5_sub.get_work_item(iface_wi.work_item_id)

        config = FactoryConfig(
            dsn="",
            project_name="test",
            hmac_key_path="",
            workspace_root=tmp_path / "work",
            workflow_version=5,
            gate_crash_threshold=3,
        )
        runtime = PipelineRuntime(sub=phase5_sub, config=config)

        raised = False
        try:
            process_gate_item(runtime, fresh, "test-gate-legit", claim)
        except Exception:
            raised = True

        assert not raised, (
            "Legitimate gate failures must not raise exceptions from process_gate_item"
        )
        final = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert final.current_state == STATE_NEW, (
            f"Legitimate gate fail should route to new via gate_fail, got: {final.current_state}"
        )


class TestBC185ReviewFoundDefectE2E:
    """AC-5: end-to-end review-found-defect path.

    Drives process_gate_item on a review work item with structured findings,
    then asserts:
    - review work item does NOT have review_findings in its stored custom_fields
    - a new implementation revision IS created with review_findings
    """

    def test_review_findings_on_impl_revision_not_on_review_wi(self, phase5_sub, tmp_path):
        # Use phase5() config so that implementation has a role mapping for ensure_upstream_revision
        config = FactoryConfig.phase5(
            dsn="",
            project_name="test",
            hmac_key_path="",
            workspace_root=tmp_path / "work",
        )
        # Set up the dependency chain: interface_spec → test_suite → implementation → review
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "FR-01", "ac_ids": ["AC-01"]},
        )
        test_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "FR-01",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
            },
        )
        impl_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            actor_id="test-creator",
            custom_fields={
                "spec_section": "FR-01",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(test_wi.work_item_id),
            },
        )
        review_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="review",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "FR-01",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(test_wi.work_item_id),
                "implementation_ref": str(impl_wi.work_item_id),
            },
        )

        # Write a review artifact with structured findings
        artifact_path = tmp_path / "review.json"
        artifact_path.write_text(REVIEW_FINDINGS_JSON)

        # Transition review into gating state
        phase5_sub.transition(
            review_wi.work_item_id,
            "claim",
            "test-reviewer",
            actor_metadata={"role": "cross_family_reviewer"},
        )
        phase5_sub.transition(
            review_wi.work_item_id,
            "submit",
            "test-reviewer",
            actor_metadata={"role": "cross_family_reviewer"},
            custom_fields={
                "artifact_path": str(artifact_path),
                "artifact_hash": "abc",
            },
        )

        phase5_sub.register_actor_role("test-gate-e2e", "mechanical_gate")
        claim = phase5_sub.acquire_claim(review_wi.work_item_id, "test-gate-e2e", ttl_seconds=300)
        fresh = phase5_sub.get_work_item(review_wi.work_item_id)

        runtime = PipelineRuntime(sub=phase5_sub, config=config)
        process_gate_item(runtime, fresh, "test-gate-e2e", claim)

        # AC-5a: review work item must NOT have review_findings
        final_review = phase5_sub.get_work_item(review_wi.work_item_id)
        assert final_review.current_state == STATE_NEW
        review_cf = final_review.custom_fields or {}
        assert CUSTOM_FIELD_REVIEW_FINDINGS not in review_cf, (
            f"review_findings must NOT be stored on the review work item (BC-185), "
            f"found: {review_cf}"
        )
        assert CUSTOM_FIELD_DIAGNOSTICS in review_cf, "diagnostics must be on review work item"

        # AC-5b: a new implementation revision must exist with review_findings
        impl_revisions = phase5_sub.query_work_items(
            workflow_name="software_factory",
            workflow_version=5,
            work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
            custom_field_filters={"upstream_revision_of": str(review_wi.work_item_id)},
            page_size=10,
        )
        assert impl_revisions.items, (
            "A new implementation revision must be created for the review-found-defect path"
        )
        impl_rev = impl_revisions.items[0]
        impl_cf = impl_rev.custom_fields or {}
        assert CUSTOM_FIELD_REVIEW_FINDINGS in impl_cf, (
            f"review_findings must be present on the new implementation revision (BC-185), "
            f"found: {impl_cf}"
        )
        # The findings should be the structured list, not a text-diagnostic fallback dict
        findings_value = impl_cf[CUSTOM_FIELD_REVIEW_FINDINGS]
        assert isinstance(findings_value, list), (
            f"review_findings on impl revision should be the structured list from routing_fields, "
            f"got: {type(findings_value)}: {findings_value}"
        )
