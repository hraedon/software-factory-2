from __future__ import annotations

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.runner import process_work_item
from tests._helpers import events_by_transition


class _FailingChannel:
    """Channel that returns configurable failure modes."""

    def __init__(self, result: InvocationResult):
        self._result = result
        self._name = "failing"
        self._family = "test"
        self._invocations: list = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        self._invocations.append((role, prompt, inputs_dir, outputs_dir))
        return self._result

    @property
    def was_invoked(self) -> bool:
        return len(self._invocations) > 0


class TestChannelFailureModes:
    def test_timeout_releases_claim_and_records_event(self, mock_substrate, workspace_root):
        """BC-019/BC-021: Timeout must release claim and write a channel_fail event."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Timeout test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        channel = _FailingChannel(
            InvocationResult(
                success=False,
                error_message="Timeout after 600s",
                exit_code=None,
                timed_out=True,
            )
        )
        config = FactoryConfig(workspace_root=workspace_root)
        process_work_item(
            mock_substrate,
            config,
            channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Timeout test",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        assert updated.claimed_by is None
        assert channel.was_invoked

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "channel_fail")
        assert len(events) == 1
        payload = events[0].payload or {}
        diagnostics = payload.get("diagnostics", {})
        assert diagnostics.get("error_message") == "Timeout after 600s"
        assert diagnostics.get("timed_out") is True
        meta = events[0].actor_metadata or {}
        assert meta.get("role") == "interface_architect"

    def test_non_zero_exit_releases_claim_and_records_event(self, mock_substrate, workspace_root):
        """BC-019/BC-021: Non-zero exit must release claim and write a channel_fail event."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Exit code test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        channel = _FailingChannel(
            InvocationResult(
                success=False,
                error_message="claude returned non-zero exit",
                exit_code=1,
                timed_out=False,
            )
        )
        config = FactoryConfig(workspace_root=workspace_root)
        process_work_item(
            mock_substrate,
            config,
            channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Exit code test",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        assert updated.claimed_by is None

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "channel_fail")
        assert len(events) == 1
        payload = events[0].payload or {}
        diagnostics = payload.get("diagnostics", {})
        assert diagnostics.get("error_message") == "claude returned non-zero exit"
        assert diagnostics.get("exit_code") == 1

    def test_empty_output_releases_claim_and_records_event(self, mock_substrate, workspace_root):
        """BC-019/BC-021: Empty output must release claim and write a channel_fail event."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Empty output test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        channel = _FailingChannel(
            InvocationResult(
                success=False,
                error_message="Empty output from claude",
                exit_code=0,
                timed_out=False,
            )
        )
        config = FactoryConfig(workspace_root=workspace_root)
        process_work_item(
            mock_substrate,
            config,
            channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Empty output test",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        assert updated.claimed_by is None

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "channel_fail")
        assert len(events) == 1

    def test_extraction_failure_releases_claim_and_records_event(
        self, mock_substrate, workspace_root
    ):
        """BC-019/BC-021: Artifact extraction failure must release claim and write
        a channel_fail event."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Extraction test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        channel = _FailingChannel(
            InvocationResult(
                success=False,
                error_message="Could not extract artifact from claude output",
                exit_code=0,
                timed_out=False,
            )
        )
        config = FactoryConfig(workspace_root=workspace_root)
        process_work_item(
            mock_substrate,
            config,
            channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Extraction test",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        assert updated.claimed_by is None

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "channel_fail")
        assert len(events) == 1

    def test_cannot_proceed_does_not_return_to_new(self, mock_substrate, workspace_root):
        """BC-019: cannot_proceed transitions to terminal state, not back to 'new'."""
        import json

        class _CannotProceedChannel:
            def __init__(self):
                self._name = "cp"
                self._family = "test"

            @property
            def name(self) -> str:
                return self._name

            @property
            def family(self) -> str:
                return self._family

            def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
                outputs_dir.mkdir(parents=True, exist_ok=True)
                cp = {"status": "cannot_proceed", "reason": "ambiguous", "gaps": ["AC conflict"]}
                (outputs_dir / "cannot_proceed.json").write_text(json.dumps(cp))
                return InvocationResult(
                    success=False, artifact_name=None, error_message="cannot_proceed"
                )

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "CP test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        config = FactoryConfig(workspace_root=workspace_root)
        process_work_item(
            mock_substrate,
            config,
            _CannotProceedChannel(),
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="CP test",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "cannot_proceed"
