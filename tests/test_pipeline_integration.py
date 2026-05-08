from __future__ import annotations

from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.scheduler import _ensure_downstream_item


class _IntegrationChannel:
    def __init__(self, workspace_root: Path):
        self._workspace_root = workspace_root
        self._name = "integration-test"
        self._family = "test"
        self._invocations: list[tuple[str, int]] = []
        self._role_attempt_counts: dict[str, int] = {}
        self._fail_at: dict[tuple[str, int], str] = {}
        self._pending_ac_ids: list[str] = ["AC-01"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def scripted_failure(
        self,
        role: str,
        attempt_number: int,
        error: str = "scripted_failure",
    ) -> None:
        self._fail_at[(role, attempt_number)] = error

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        n = self._role_attempt_counts.get(role, 0) + 1
        self._role_attempt_counts[role] = n
        self._invocations.append((role, n))

        if (role, n) in self._fail_at:
            return InvocationResult(
                success=False,
                error_message=self._fail_at[(role, n)],
                exit_code=1,
            )

        outputs_dir.mkdir(parents=True, exist_ok=True)
        ac = self._pending_ac_ids[0] if self._pending_ac_ids else "AC-01"

        if role == "interface_architect":
            content = (
                "from dataclasses import dataclass\n"
                "def compute(x: int) -> str:\n"
                f'    """{ac}"""\n'
                "    ...\n"
            )
            name = "artifact.pyi"
        elif role == "test_author":
            content = (
                "def compute(x: int) -> str:\n"
                "    return str(x)\n\n"
                "def test_compute():\n"
                f'    """{ac}"""\n'
                '    assert compute(1) == "1"\n'
            )
            name = "test_suite.py"
        elif role == "implementer":
            content = "def compute(x: int) -> str:\n    return str(x)\n"
            name = "impl.py"
        else:
            return InvocationResult(
                success=False,
                error_message=f"unknown role {role}",
                exit_code=1,
            )

        (outputs_dir / name).write_text(content)
        return InvocationResult(success=True, artifact_name=name)

    @property
    def invocations(self) -> list[tuple[str, int]]:
        return list(self._invocations)


def _make_phase2_config(workspace_root: Path) -> FactoryConfig:
    return FactoryConfig(
        workspace_root=workspace_root,
        workflow_version=2,
        worker_roles=FactoryConfig.PHASE2_WORKER_ROLES,
        type_to_role=FactoryConfig.PHASE2_TYPE_TO_ROLE,
        roles=FactoryConfig.PHASE2_ROLES,
    )


def _register_roles(sub):
    for actor_id, role in [
        ("factory-arch", "interface_architect"),
        ("factory-tester", "test_author"),
        ("factory-impl", "implementer"),
        ("factory-gate", "mechanical_gate"),
    ]:
        sub.register_actor_role(actor_id, role)


def _run_worker_stage(sub, config, channel, wi, actor_id, role_name, spec_content="Test spec"):
    claim = sub.acquire_claim(wi.work_item_id, actor_id)
    sub.transition(
        wi.work_item_id,
        "claim",
        actor_id,
        actor_metadata={"role": role_name},
    )
    process_work_item(
        sub,
        config,
        channel,
        wi,
        actor_id,
        claim,
        role_name,
        spec_content=spec_content,
    )
    return sub.get_work_item(wi.work_item_id)


def _run_gate(sub, config, wi, actor_id="factory-gate"):
    claim = sub.acquire_claim(wi.work_item_id, actor_id)
    process_gate_item(sub, config, wi, actor_id, claim)
    return sub.get_work_item(wi.work_item_id)


def _create_downstream(sub, config, source_wi, source_type, source_state):
    handoff_map = {
        ("interface_spec", "locked"): {
            "next_type": "test_suite",
            "link_type": "derived_from",
            "next_role": "test_author",
        },
        ("test_suite", "locked"): {
            "next_type": "implementation",
            "link_type": "tested_by",
            "additional_links": ["implements"],
            "next_role": "implementer",
        },
    }
    handoff = handoff_map.get((source_type, source_state))
    if handoff is None:
        return None
    _ensure_downstream_item(sub, config, source_wi, handoff)

    downstream = None
    for wi in sub.query_work_items(current_states=["new"], page_size=50).items:
        if wi.work_item_type == handoff["next_type"]:
            ref_field = (
                "interface_ref" if handoff["next_type"] == "test_suite" else "test_suite_ref"
            )
            cf = wi.custom_fields or {}
            if cf.get(ref_field) == str(source_wi.work_item_id):
                downstream = wi
                break
    return downstream


def _drive_full_pipeline(sub, config, channel, spec_section="Compute function", ac_ids=None):
    if ac_ids is None:
        ac_ids = ["AC-01"]

    iface, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type="interface_spec",
        actor_id="test-creator",
        custom_fields={"spec_section": spec_section, "ac_ids": ac_ids},
    )

    # Stage 1: interface_architect
    wi = _run_worker_stage(
        sub,
        config,
        channel,
        iface,
        "factory-arch",
        "interface_architect",
        spec_section,
    )
    assert wi.current_state == "gating", f"Expected gating, got {wi.current_state}"
    wi = _run_gate(sub, config, wi)
    assert wi.current_state == "locked", f"Expected locked after gate, got {wi.current_state}"

    # Schedule + run test_suite
    ts_wi = _create_downstream(sub, config, wi, "interface_spec", "locked")
    assert ts_wi is not None, "test_suite work item not created"
    wi = _run_worker_stage(
        sub,
        config,
        channel,
        ts_wi,
        "factory-tester",
        "test_author",
        spec_section,
    )
    assert wi.current_state == "gating"
    wi = _run_gate(sub, config, wi)
    assert wi.current_state == "locked"

    # Schedule + run implementation
    impl_wi = _create_downstream(sub, config, wi, "test_suite", "locked")
    assert impl_wi is not None, "implementation work item not created"
    wi = _run_worker_stage(
        sub,
        config,
        channel,
        impl_wi,
        "factory-impl",
        "implementer",
        spec_section,
    )
    assert wi.current_state == "gating"
    wi = _run_gate(sub, config, wi)
    assert wi.current_state == "locked"

    return {
        "interface_spec": iface,
        "test_suite": ts_wi,
        "implementation": impl_wi,
    }


class _BadImplIntegrationChannel(_IntegrationChannel):
    """Produces implementation artifacts that trigger impl_lint gate failures
    (unused import) for escalation testing."""

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        result = super().invoke(role, prompt, inputs_dir, outputs_dir, timeout)
        if role == "implementer" and result.success:
            name = result.artifact_name
            (outputs_dir / name).write_text(
                "import os\n\ndef compute(x: int) -> str:\n    return str(x)\n"
            )
        return result


class TestPipelineIntegration:
    def test_three_item_subset_end_to_end(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        results = _drive_full_pipeline(
            mock_substrate,
            config,
            channel,
            spec_section="Given int x, return str(x).",
            ac_ids=["AC-01"],
        )

        assert results["interface_spec"]
        assert results["test_suite"]
        assert results["implementation"]

        iface_events = mock_substrate.read_events(
            work_item_id=results["interface_spec"].work_item_id
        )
        ts_events = mock_substrate.read_events(work_item_id=results["test_suite"].work_item_id)
        impl_events = mock_substrate.read_events(
            work_item_id=results["implementation"].work_item_id
        )

        assert any(e.transition == "gate_pass" for e in iface_events)
        assert any(e.transition == "gate_pass" for e in ts_events)
        assert any(e.transition == "gate_pass" for e in impl_events)
        assert any(e.transition == "claim" for e in iface_events)
        assert any(e.transition == "submit" for e in iface_events)
        assert len(channel.invocations) == 3

    def test_three_distinct_specs_end_to_end(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        specs = [
            ("Pure interface: def parse(s: str) -> int", ["AC-01"]),
            ("Error taxonomy: def validate(x: int) -> str | None", ["AC-02"]),
            ("ADT: def transform(data: list[int]) -> dict[str, int]", ["AC-03"]),
        ]
        all_results = []
        for spec_text, acs in specs:
            channel._pending_ac_ids = acs
            results = _drive_full_pipeline(
                mock_substrate,
                config,
                channel,
                spec_section=spec_text,
                ac_ids=acs,
            )
            all_results.append(results)

        assert len(all_results) == 3
        assert len(channel.invocations) == 9

        for results in all_results:
            for key in ("interface_spec", "test_suite", "implementation"):
                wi = mock_substrate.get_work_item(results[key].work_item_id)
                assert wi.current_state == "locked"

    def test_implementer_failure_then_recovery(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        channel.scripted_failure("implementer", 1)
        _register_roles(mock_substrate)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        # Stage 1: interface_architect
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            iface,
            "factory-arch",
            "interface_architect",
        )
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        # Stage 2: test_author
        ts_wi = _create_downstream(mock_substrate, config, wi, "interface_spec", "locked")
        assert ts_wi is not None
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            ts_wi,
            "factory-tester",
            "test_author",
        )
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        # Stage 3: implementer attempt 1 — fails
        impl_wi = _create_downstream(mock_substrate, config, wi, "test_suite", "locked")
        assert impl_wi is not None
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "new"

        impl_wi = mock_substrate.get_work_item(impl_wi.work_item_id)
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        impl_invocations = [i for i in channel.invocations if i[0] == "implementer"]
        assert len(impl_invocations) == 2
        assert impl_invocations[0] == ("implementer", 1)
        assert impl_invocations[1] == ("implementer", 2)

    def test_interface_architect_failure_then_recovery(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        channel.scripted_failure("interface_architect", 1)
        _register_roles(mock_substrate)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        # Attempt 1: channel fail
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            iface,
            "factory-arch",
            "interface_architect",
        )
        assert wi.current_state == "new"

        # Attempt 2: succeeds
        iface = mock_substrate.get_work_item(iface.work_item_id)
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            iface,
            "factory-arch",
            "interface_architect",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        arch_invocations = [i for i in channel.invocations if i[0] == "interface_architect"]
        assert len(arch_invocations) == 2

    def test_cross_stage_escalation_after_attempt_threshold(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        # Drive interface_spec to locked
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            iface,
            "factory-arch",
            "interface_architect",
        )
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        # Drive test_suite to locked
        ts_wi = _create_downstream(mock_substrate, config, wi, "interface_spec", "locked")
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            ts_wi,
            "factory-tester",
            "test_author",
        )
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        # Create implementation — then manually simulate 3 gate_fail cycles
        # to trigger escalation
        impl_wi = _create_downstream(mock_substrate, config, wi, "test_suite", "locked")
        assert impl_wi is not None

        # Attempt 1: submit + gate_fail
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "gating"

        # Manually gate_fail with attempt_threshold=3 — this simulates the 3rd attempt
        from factory.gate import GateResult
        from factory.router import DiagnosticKind

        _ = mock_substrate.acquire_claim(wi.work_item_id, "factory-gate")
        gate_result = GateResult(
            passed=False,
            gate_name="implementation_mypy",
            diagnostics=["error: Incompatible return value type"],
            diagnostic_kind="impl_mypy",
        )

        from factory.router import route

        routing = route(
            "gating",
            "gate_fail",
            gate_result,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert routing.diagnostic_kind == DiagnosticKind.CANNOT_PROCEED_SEAM
        assert routing.target_role == "interface_architect"

    def test_event_sequence_complete_per_stage(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        results = _drive_full_pipeline(mock_substrate, config, channel)

        for key in ("interface_spec", "test_suite", "implementation"):
            wi = results[key]
            events = mock_substrate.read_events(work_item_id=wi.work_item_id)
            transitions = [e.transition for e in events]
            assert "claim" in transitions, f"{key}: missing claim"
            assert "submit" in transitions, f"{key}: missing submit"
            assert "gate_pass" in transitions, f"{key}: missing gate_pass"

    def test_artifact_paths_propagate_through_chain(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        results = _drive_full_pipeline(mock_substrate, config, channel)

        # Each item should have an artifact_path after submission
        for key in ("interface_spec", "test_suite", "implementation"):
            wi = mock_substrate.get_work_item(results[key].work_item_id)
            artifact_path = (wi.custom_fields or {}).get("artifact_path", "")
            assert artifact_path, f"{key}: no artifact_path"
            assert Path(artifact_path).exists(), f"{key}: artifact file missing at {artifact_path}"

        # test_suite should carry interface_ref pointing to the interface_spec
        ts = mock_substrate.get_work_item(results["test_suite"].work_item_id)
        assert (ts.custom_fields or {}).get("interface_ref") == str(
            results["interface_spec"].work_item_id,
        )

        # implementation should carry both refs
        impl = mock_substrate.get_work_item(results["implementation"].work_item_id)
        assert (impl.custom_fields or {}).get("interface_ref") == str(
            results["interface_spec"].work_item_id,
        )
        assert (impl.custom_fields or {}).get("test_suite_ref") == str(
            results["test_suite"].work_item_id,
        )

    def test_e2e_escalation_through_repeated_gate_failures(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _BadImplIntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            iface,
            "factory-arch",
            "interface_architect",
        )
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        ts_wi = _create_downstream(mock_substrate, config, wi, "interface_spec", "locked")
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            ts_wi,
            "factory-tester",
            "test_author",
        )
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "locked"

        impl_wi = _create_downstream(mock_substrate, config, wi, "test_suite", "locked")
        assert impl_wi is not None

        # Attempt 1: worker produces bad artifact (unused import), gate fails impl_lint
        # Worker claim=attempt1, Gate claim=attempt2. attempt2 < 3, normal gate_fail.
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "new"
        diags = (wi.custom_fields or {}).get("diagnostics", {})
        assert diags.get("diagnostic_kind") == "impl_lint"

        # Attempt 2: worker resumes bad artifact, gate fails impl_lint again.
        # Worker claim=attempt3, Gate claim=attempt4. attempt4 >= 3, escalation fires.
        # Item transitions to cannot_proceed (terminal), stopping the retry loop.
        impl_wi = mock_substrate.get_work_item(impl_wi.work_item_id)
        wi = _run_worker_stage(
            mock_substrate,
            config,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(mock_substrate, config, wi)
        assert wi.current_state == "cannot_proceed"
        diags = (wi.custom_fields or {}).get("diagnostics", {})
        assert diags.get("diagnostic_kind") == "cannot_proceed_seam"
        assert diags.get("target_role") == "interface_architect"
        assert diags.get("escalated_from_kind") == "impl_lint"
        assert diags.get("escalated_after_attempts") == 4

        impl_events = mock_substrate.read_events(work_item_id=impl_wi.work_item_id)
        gate_fails = [e for e in impl_events if e.transition == "gate_fail"]
        assert len(gate_fails) == 1
        gate_escalations = [e for e in impl_events if e.transition == "gate_escalation"]
        assert len(gate_escalations) == 1
